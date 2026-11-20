# Verification, repair, upgrade and rollback

Contents: acceptance scope; acceptance layers; private correlated test; concrete version checks;
redacted Ghost check; failure map; retries and ambiguous sends; backup;
upgrades/rollback; health diagnostics; provider migration.
See also the [verification, rollback, and packaging checklist](checklist.md).

## Acceptance scope

| Work requested | Required acceptance | Preserve / do not infer |
|---|---|---|
| New newsletter deployment | Proxy auth, migrations, live worker, scoped events, one received proxy test before cutover, then one received Ghost native test | Transactional configuration and credentials; login test is not a newsletter prerequisite |
| Local repair | Effective configuration and observable recovery of the affected layer; if sending was affected, one received authorized test through that path | Do not initialize stores, rotate keys or migrate the other mail path |
| Upgrade | Isolated target checks, native configuration/TLS checks and queue reconciliation, then relevant native test after cutover | Upgrade one layer; login test only for affected transactional path |
| Transactional setup/repair | Actual Ghost loaded transport, TLS policy and one received authorized Ghost login email | Newsletter settings unless separately requested/affected |

A shared Bridge change can affect both clients: inspect both paths, and test both
if they use that Bridge. This does not authorize replacing unrelated credentials
or reconfiguring a working path. Record required checks as pass, fail, blocked or
not applicable. Never convert a blocked inbox/SMTP check into a pass.

## Acceptance layers

Judge each layer independently. A pass at one layer never fills a later layer.
Record every required check as pass, fail, blocked, or not applicable. Never
convert a blocked inbox or SMTP check into a pass.

| Layer | Pass evidence | Does not prove |
|---|---|---|
| HTTP enqueue | Helper `queued` exit 0: HTTP `200` and a nonempty response `id` | Queue processing, SMTP, receipt |
| Queue handoff | Helper `poll` exit 0: exactly one correlated `accepted` event, zero `failed` or `unknown`, and the specific job has left pending/reserved/retryable work | Fixture capture or inbox receipt |
| Ghost native preview | Preview or equivalent native payload is processed without worker error, plus the queue-handoff evidence above | Inbox receipt. HTTP `204` alone is only the Ghost API call |
| Isolated capture | Exactly one matching message in the isolated SMTP capture sink for the unique test ID (unique subject and, when present, trace or delivery headers). Prefer internal STARTTLS with verification enabled. An `accepted` event without a captured MIME message is not a pass | Real provider or inbox delivery |
| Real inbox receipt | The authorized recipient confirms the unique test in the mailbox | Future deliverability or other recipients |

Helper exit codes, used consistently:

- `0`: exactly one correlated `accepted` event and no failed or unknown matches. This is queue handoff, not final delivery.
- `1`: failed or unrecognized matches, duplicate `accepted`, invalid or incomplete responses, pagination errors, or transport errors. Investigate; do not POST again from this run directory.
- `2`: zero matches when the polling deadline is reached. Delivery remains unproven. Do not automatically resend. Keep `.post-attempt` and the original evidence and reconcile with read-only checks.

Zero matches, a missing queued ID, an HTTP timeout, an unknown job state, or any other ambiguous result is not authorization to replay or to start a second POST in the same directory. `accepted` is SMTP-or-transport handoff evidence only.

## Acceptance: use an authorized test recipient

Use curl **7.76.0 or later** for `--fail-with-body` and Python 3. Set `skill_dir` to the absolute path of the unpacked skill. In a fresh private run directory, install a mode-600 `proxy-test.netrc` with machine `mg.example.com`, login `api` and the shared password. Record baseline pending, reserved and failed job counts. Keep credentials out of arguments, history and HTTP logs. Run this block for one authorized recipient. It reserves the directory for one POST attempt, including when two invocations start concurrently.

```bash
set -eu
umask 077
if ! mkdir .post-attempt 2>/dev/null; then
  echo 'Cannot reserve this run directory. If a request already exists, use read-only reconciliation.' >&2
  exit 1
fi
for evidence in request.private send-status.private send-response.private.json queued-id.private; do
  if [ -e "$evidence" ] || [ -L "$evidence" ]; then
    echo 'Existing send evidence. Reconcile this request with read-only checks.' >&2
    exit 1
  fi
done
test_id="newsletter-check-$(python3 -c 'import uuid; print(uuid.uuid4())')"
test_to='<authorized-test-recipient>'
test_begin=$(date +%s)
printf '%s\n' "$test_to" "$test_id" "$test_begin" > request.private
if ! curl --disable --fail-with-body --silent --globoff --proto '=https' \
  --connect-timeout 5 --max-time 30 --netrc-file ./proxy-test.netrc \
  --output ./send-response.private.json --write-out '%{http_code}' \
  --url 'https://mg.example.com/v3/example.com/messages' \
  --form-string 'from=Example Site <mail@example.com>' \
  --form-string "to=$test_to" \
  --form-string "subject=$test_id" \
  --form-string 'html=<p>Newsletter route test</p>' > send-status.private; then
  echo 'POST outcome unconfirmed. Reconcile this request before any resend.' >&2
  exit 1
fi
python3 "$skill_dir/scripts/check_acceptance.py" queued
```

The helper requires HTTP `200` and a nonempty response `id` before writing the queued ID. Verify this status and response contract on the selected proxy release before using the example. A different status with an `id` still requires reconciliation.

A POST timeout can follow API acceptance. Keep `.post-attempt` and the original evidence even after a timeout, interruption, or invalid response. Use the saved recipient, subject and start time for read-only investigation. If `request.private` is missing, inspect the evidence and establish that no handoff occurred before authorizing a new attempt in a fresh directory. For a new shell, reload the private values as shown. This polling block issues GET requests only:

```bash
(
  set -eu
  umask 077
  { IFS= read -r test_to && IFS= read -r test_id && IFS= read -r test_begin; } < request.private
  python3 "$skill_dir/scripts/check_acceptance.py" poll \
    'https://mg.example.com/v3/example.com/events' "$test_to" "$test_id" "$test_begin"
)
```

Use --form-string: curl -F treats a leading `<` as a file read. Response bodies
remain private. The helper requires only a nonempty response `id` on HTTP `200`;
that value is not required to be the literal string `message-id`. On the
published failing digest, successful simple POSTs did return that literal. On
the source-verified local build of `e31299823886f4db9d026054632907924eb02d49`,
the HTTP `id` was a batch-style identifier. Record whatever `id` is returned as
response evidence only.

Correlate the unique subject, recipient, and time window with the specific
database request, queue jobs, and delivery records. Use `X-Proxy-Trace` or
`X-Newsletter-Delivery-Id` when those headers are present. Do not assume the
POST `id` equals the MIME `Message-Id`. The `deliveries.mailgun_message_id`
column may also be a separate token (a 19-character value was observed on the
local build) and is not the MIME `Message-Id`. The event header can carry a
different ID.

The verified event filters are `to`, `begin`, `end`, `message-id`, and `event`;
`tags` is not applied. This example scopes by recipient/time and matches the unique
subject locally. If using a stored message-id filter, first establish its mapping
from this request's delivery record and captured MIME headers; never blindly
filter using the POST response ID or `deliveries.mailgun_message_id`.

Each polling sweep fixes the recipient, begin/end times and page size. Follow
`paging.next` even if `items` is empty. The helper reconstructs the URL on the
original HTTPS origin and event path using the original filters. It accepts
either one `page`/`cursor` query parameter or one opaque path segment appended
to `/events`. It rejects changed filters, mixed cursor formats and repeated
cursors. A same-scope `paging.first` link may omit its cursor and is never
fetched. Bound page count and total time, and use connection and total timeouts
for each GET. The helper does not follow HTTP redirects (`--max-redirs 0`) and
rejects non-HTTPS, credentialed, or malformed event URLs. A missing `subject`
(or other required event field) fails the whole page rather than skipping the
item, because the inspected resource omits empty fields. Path cursors are a
single token matching `[A-Za-z0-9_+-]+={0,2}` and therefore reject `/`; if a
later digest uses standard Base64 in the path, retest or treat the walk as
blocked. Keep the private `poll-*` directory. The helper publishes matched
evidence after a complete walk and prints only counts or fixed diagnostics.
A subsequent sweep may advance `end`. Verify response shapes and pagination
boundaries on the selected digest before cutover.
[Acceptance helper](../scripts/check_acceptance.py) and the
[verification checklist](checklist.md)

Use the [acceptance-layer](#acceptance-layers) exit codes. Exit 2 (zero matches at the deadline) leaves delivery unproven and must not trigger a resend. Exit 1 requires investigation of failed or unrecognized matching events, duplicate acceptance, invalid responses, incomplete pagination or transport errors. The SMTP fixture check treats `accepted` as handoff evidence and `failed` as failure. Other correlated event names are counted as `unknown` and require checking the selected release's event contract. Exit 0 requires exactly one `accepted` event and zero failed or unknown matches; it still does not prove capture or inbox receipt. For this single-recipient test, also require the specific job out of pending/reserved work and no unexplained failures or backlog growth. Reconcile a missing queued ID, HTTP timeout, zero matches, unknown jobs, or any ambiguous attempt before considering a new attempt in a fresh directory. Confirm isolated SMTP capture or recipient receipt separately and identify which was observed. A Laravel `mailbox` driver that returns `accepted` but writes no mailbox store is not capture proof; use an internal SMTP STARTTLS sink instead. Remove temporary credentials and retain private recipient-bearing files only for the agreed evidence period. [Reconciliation](#ambiguous-sends-automatic-retry-versus-manual-resend)

For duplicate or rollback acceptance, record the effective worker retry schedule and the last time a relevant job could have been reserved or released. Verify the correlated job has left pending, reserved and retryable work. After the configured reservation/retry window, rerun the read-only polling block with the original start time and compare SMTP capture counts for the whole window. The first successful sweep is early handoff evidence.

Distinguish these results:

| Evidence | What it establishes | What remains unproven |
|---|---|---|
| /up succeeds | Application liveness | Worker, SMTP, inbox receipt |
| POST returns queued ID | API authenticated and accepted request | SMTP handoff |
| Correlated accepted event / MessageSent | Transport accepted that send | Recipient delivery, opens |
| Test present in recipient mailbox | Receipt for this recipient | All recipients, future deliverability |
| Ghost native Send test received | Ghost-to-proxy send path | A real campaign's scale |
| Ghost native preview returns HTTP `204` | Ghost completed the preview API call | Proxy worker processing, SMTP handoff, inbox receipt |
| Ghost login email received | Ghost's transactional SMTP path | Bulk path |

### Isolated SMTP capture (recommended)

Prefer a private, internal SMTP listener that offers STARTTLS, requires TLS,
and keeps peer and hostname verification enabled in the proxy. Bind it only on
an isolated Docker network. Do not publish capture ports on a public address.
Correlate the captured MIME message by unique subject and, when present,
`X-Proxy-Trace` or `X-Newsletter-Delivery-Id`. Inspect the captured
`Message-Id` header: expect exactly one legal, bracketed identification value
for that unique test.

This package does not ship a previously executed capture fixture. If you
adapt the generic [SMTP capture template](smtp-capture-template.md), review it
before use. The template has not been executed as part of this skill package.

Do not treat the Laravel `mailbox` mailer as a proven capture path. In the
2026-11-19 isolated build, a request could be accepted without a mailbox
SQLite file appearing.

Confirm migrations and actual queue process health; a bare `compose ps` is
insufficient. Inspect delivery records for the test ID. If queued work does not
advance, inspect the bundled queue process and sanitized error details first.
Do not substitute a custom SMTP probe that silently changes TLS options. Use
Ghost's native test/login flow, or a probe built from its actual loaded transport.
If click stats matter, click one authorized test link and verify Ghost's result;
proxy provider-event clicks and Ghost's rewritten-link tracking are distinct.

## Concrete checks for the inspected source

These commands target proxy revision `fb35a74000fe70e7d49f46cae3c895674571ea20`,
Laravel 13.9.0 and Symfony Mailer 8.0.8 in its lockfile, not a certified image.
Run from the actual Compose project, adapting inspected service names/paths.
Keep detailed output private; report only booleans/counts/status.

| Check | Method | Pass condition |
|---|---|---|
| Migrations | `docker compose exec -T newsletter-proxy php artisan migrate:status --no-ansi > migration-status.private` | Command succeeds, every migration is Ran; no Pending or DB errors |
| Worker | Save `docker top "$(docker compose ps -q newsletter-proxy)" -eo pid,comm,args` privately; inspect Procfile/process manager and restart state | Live queue:work process with expected connection/queue, stable across the test; correlated test actually progresses |
| Queue | Correlate private request/delivery/job records with saved queued ID and subject; inspect failed job details privately | The test job has left pending/reserved/retryable work and produced the expected handoff event; no unexplained test failures or increasing backlog |
| TLS | Verify native MAIL_URL support, then bootstrap Laravel and inspect the actual transport below | require_tls true, runtime reports TLS required; peer/name verification remains on for both routes; real test follows that transport |
| Registration | After first admin, privately check `App\Support\Registration::available()` and unauthenticated GET /register without following redirects | available is false and GET redirects to /login; existing admin login still works |

Run this PHP inside `/var/www/html` in the actual proxy container (e.g. through
`docker compose exec -T newsletter-proxy php` with stdin). It neither sends nor
prints credentials:

```php
<?php
require 'vendor/autoload.php';
$app = require 'bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
$config = (new Illuminate\Support\ConfigurationUrlParser)->parseConfiguration(
    config('mail.mailers.smtp')
);
$transport = $app->make('mail.manager')->mailer('smtp')->getSymfonyTransport();
echo json_encode([
    'requireTlsConfig' => ($config['require_tls'] ?? false) === true,
    'requireTlsRuntime' => method_exists($transport, 'isTlsRequired')
        ? $transport->isTlsRequired() : null,
    'verifyPeerConfigured' => filter_var($config['verify_peer'] ?? true, FILTER_VALIDATE_BOOL),
    'socketTimeout' => $transport->getStream()->getTimeout(),
    'registrationClosed' => !App\Support\Registration::available(),
]), PHP_EOL;
```

The locked Laravel resolves MAIL_URL before constructing the transport; checking
raw `config('mail.mailers.smtp')` alone misses URL query options. Its Symfony factory
supports `require_tls`; Laravel applies the parsed `timeout` to the socket. Inspect
stream SSL options privately for any legacy overrides disabling peer/name checks.
The summary above establishes configuration only, not certificate acceptance.
Setting MAIL_REQUIRE_TLS or MAIL_VERIFY_PEER alone has no effect in upstream mail.php.
To verify fail-closed STARTTLS behavior, use an isolated capture server lacking
STARTTLS: sending must fail without handoff. Never redirect production credentials
for this test. Test untrusted certificates/hostname mismatch separately: both must
fail, followed by one authorized receipt on the intended trusted transport.

The pinned registration tests expect an additional POST /register to return 403
and leave the user count unchanged. Verify that behavior with the upstream
RegistrationTest in an isolated test database, not by creating another production
account. Review registration middleware/action and route names in a different
revision; do not invent a registration-disable env variable.

For an image/runtime that differs, extract its config and composer.lock, inspect
MailManager, EsmtpTransportFactory/EsmtpTransport and registration/process startup
code before using these commands or URL options. If methods/options differ, adapt
and validate in isolation or mark the check blocked. `/up` alone never satisfies
any worker, TLS, registration or delivery acceptance requirement.

## Redacted Ghost runtime check

Save the code below into a private file, copy it into the actual Ghost container,
and run it there from `/var/lib/ghost` with the correct loader path for that version.
Pass a private JSON file with `baseUrl`, `domain`, `apiKey` on stdin, for example
`docker compose exec -T ghost node /tmp/check-mailgun.cjs < expected.private.json`.
Generate the expected file from the intended configuration, with mode `0600`.

```javascript
process.env.NODE_ENV = 'production';
const c = require('/var/lib/ghost/current/core/shared/config/loader.js').loadNconf();
const bulk = c.get('bulkEmail')?.mailgun || {};
const mail = c.get('mail') || {};
const o = mail.options || {};
const expected = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
for (const key of ['baseUrl', 'domain', 'apiKey']) {
  if (typeof expected[key] !== 'string' || expected[key].trim() === '') {
    throw new Error(`Missing expected ${key}`);
  }
}
const bulkMatches = Object.fromEntries(['baseUrl', 'domain', 'apiKey'].map(
  key => [key, bulk[key] === expected[key]]
));
console.log(JSON.stringify({
  bulk: bulkMatches,
  mail: {transport: mail.transport, host: o.host, port: o.port,
         secure: o.secure, requireTLS: o.requireTLS,
         rejectUnauthorized: o.tls?.rejectUnauthorized,
         userPresent: Boolean(o.auth?.user), passPresent: Boolean(o.auth?.pass)}
}));
```

These exact comparisons cover the configuration loader; a native draft preview
and the proxy request establish what Ghost actually uses at send time. Compare
sender separately for the affected mail path. Never dump nconf, Docker inspect environment,
expanded Compose, or auth payload. A stale JSON `transport: Direct` is inconclusive
when env overrides it; effective loader output and real sends are the evidence.

## Failure map

| Symptom | Check and scoped repair |
|---|---|
| ESOCKET / self-signed certificate | Check CA trust and hostname against the Bridge certificate; repair only that transport without disabling verification |
| Proxy STARTTLS verification failure | Confirm native MAIL_URL parsing, actual transport and CA/hostname trust; remove bypasses only with a tested replacement |
| libfido2.so.1 missing | Inspect runtime and architecture; use a fixed upstream image or documented upstream build, retaining volume backup |
| Another Bridge instance running | Find every owner of the actual shared volume before considering a stale lock |
| Queued indefinitely | Confirm queue process, migration completion, DB access, error details and connection; restart affected process after repair |
| Native preview returns `204`, with failed `Message-Id` delivery | Check for `h:Message-Id` privately and the worker's `IdentificationHeader` / `UnstructuredHeader` error. That failure is confirmed on the published digest in the [support matrix](upstream.md#support-matrix). Do not patch the running image. Rebuild from the documented fork commit, or wait for a published image that contains the fix, then repeat the exact native preview and capture on new isolated volumes before cutover. |
| `accepted` event, but no captured MIME message | Do not treat Laravel `mailbox` acceptance as capture proof. Switch to an internal STARTTLS SMTP sink, keep verification enabled, and correlate by unique subject or trace headers. |
| HTTP or delivery IDs do not match the MIME `Message-Id` | Expected on the fixed local build. Correlate by unique subject and optional `X-Proxy-Trace` / `X-Newsletter-Delivery-Id`. Do not filter events blindly with the POST `id` or `deliveries.mailgun_message_id`. |
| 401 / proxy not configured | Compare keys privately; confirm nonempty MAILGUN_API_KEY and Basic username api |
| Ghost asks to configure Mailgun | Reconcile incomplete bulkEmail blocks, env injection and config precedence |
| curl exit 26 | Replace -F HTML fields with --form-string |

For Bridge locks, inspect the resident container's **Mounts only** to identify
/root's volume name/source; do not assume /var/lib/docker or a project prefix.
Find running containers using that volume (`docker ps --filter volume=<name>`),
including aborted one-off sessions. Stop the intended resident service and only
identified obsolete sessions; check for other processes using bind-mounted data.
If ownership is uncertain, stop recovery and report it. After proving no
Bridge process owns the store, back up its state and follow the selected Bridge
release's documented recovery or maintainer guidance. Without such evidence,
report recovery blocked; do not prescribe manual lock-file deletion. Do not use wildcard container
removal, delete the whole cache, or remove an active lock.

## Throttling, retries, bounces and duplicates

The inspected upstream Procfile uses `queue:work --sleep=3 --tries=3 --timeout=90`.
These are implementation defaults, not a Proton sending policy. `--sleep` delays
an empty queue; it does not throttle outgoing SMTP. Upstream documents Resend
rate controls, not a general SMTP rate-limit setting. Do not apply
OUTBOX_RESEND_BATCH_PAUSE_MS to Proton SMTP or invent a SMTP_RATE_LIMIT variable.

Before a campaign, verify the selected SMTP provider/job path, worker concurrency,
retry_after, timeout, backoff and actual pacing. Keep SMTP/network timeout below
the job/worker timeout, and worker timeout comfortably below retry_after, accounting
for shutdown latency. The inspected database default retry_after=90 equals the
bundled worker timeout=90; the new-deploy example sets DB_QUEUE_RETRY_AFTER=180.
This reduces reservation overlap risk but does not make SMTP retries idempotent. Concurrency of one alone does not
limit sends per second. The locked Symfony factory also supports `max_per_second` through MAIL_URL; this
is per transport/process, not an account-wide limiter. Do not assume it remains
effective across short-lived jobs, new processes or multiple workers; measure the
actual send path. If account-wide pacing cannot be established with upstream
configuration, use a backend with documented controls within the user's scope;
do not start an unbounded campaign and hope account limits enforce safe pacing.

### Ambiguous sends: automatic retry versus manual resend

A worker's automatic retry can occur without a second operator action. Its three
attempts and queue reservation expiry remain active even if nobody clicks retry.
A manual resend (dashboard retry, queue retry or campaign resubmission) is an
additional send path, not a substitute for reconciling automatic attempts.

When a timeout or crash may have followed SMTP acceptance:

1. Pause new campaign dispatch/API submissions for the affected route. Pause its
   workers through the inspected process manager and suppress their automatic
   restart. In the bundled image, if independent worker control is unavailable,
   stop newsletter-proxy with a grace period sufficient for the known job timeout;
   note that this also pauses its API/dashboard. Avoid abrupt kills. A shutdown
   timeout still leaves the send ambiguous. Other consumers of the same queue must
   also be paused; confirm no worker remains. Do not stop an unrelated transactional
   mail path or Bridge merely to pause the newsletter queue.
   Include downstream SMTP child jobs when checking for live consumers and
   replayable work. One request can queue both a listener and a separate mail job.
2. Preserve private request IDs, recipients, attempts, reservation timestamps,
   job/failure state and SMTP errors before editing the queue. Record the pause
   time. Do not delete jobs or restore an old queue snapshot as a shortcut.
3. Reconcile each attempt against delivery events, provider/Sent-folder evidence
   and recipient receipt where available. Neither a failed job nor absence from
   Sent proves non-delivery. Classify confirmed sent, confirmed unsent and unknown.
4. Quarantine unknown and confirmed-sent work from automatic replay using a
   reviewed, version-specific queue procedure while workers remain stopped. Also
   resolve Ghost-side pending submissions. Retain a reversible snapshot and audit
   trail; do not invent a generic job-deletion SQL command. If safe quarantine is
   unavailable, keep the affected path paused and report what remains uncertain.
5. Resume only after accounting for reserved/retryable jobs and confirming that
   no unknown or confirmed-sent attempt will be replayed. Retry only confirmed
   unsent recipients through one deliberate route, with bounded attempts and a
   unique audit identifier. Recheck worker concurrency and timing before resuming.

SMTP does not provide exactly-once delivery here. Evidence may remain incomplete;
report uncertainty and duplicate risk instead of automatically resuming or retrying.

SMTP currently has no remote bounce/complaint/open ingestion in this proxy. Watch
the return mailbox/provider signals and reconcile hard bounces and complaints
with Ghost member suppression before further sends. The upstream suppression
DELETE endpoints acknowledge requests as logged no-ops; they do not clear an
actual provider suppression. Do not purge test records to hide operational errors.

## Back up before edits or upgrades

1. Record nonsecret versions/digests, Bridge runtime, network topology and modified
   files. Save the Ghost mail config, Compose/env files, legacy overrides (for rollback only), reverse-proxy
   config and affected DNS values in a private timestamped backup directory.
2. Pause campaign creation/dispatch and stop the proxy's worker/container. Resolve
   in-flight sends before snapshotting. Back up the entire proxy-data volume while
   quiescent (or use a verified SQLite online backup), not a live database copy
   that omits WAL files. Preserve APP_KEY with the matching database.
3. Stop all Bridge owners before backing up bridge-data; this contains account
   state, GPG/pass material and possibly updated binaries. Keep volume ownership
   and permissions. Do not delete GPG/pass state to fix a lock.
4. Verify backups are readable and restorable into separate volumes; record the
   restore procedure and prior image references. Treat backups as secrets too.

## Upgrade and rollback

1. **Before downtime**, start the candidate by digest in a separate Compose project with its own network, aliases, empty volumes, test domain, API key and SMTP capture fixture. Keep production dispatch running during this stage. Verify target config, startup, migrations, worker and a correlated fixture handoff. Record both image digests and the target platform. Inspect how the target starts its bundled worker and demonstrate a maintenance entrypoint with zero consumers before attaching any restored queue. [Startup gates](deployment.md#6-start-proxy)
2. **Enter the cutover window.** Pause Ghost newsletter scheduling, outstanding dispatch and other API producers. Gracefully stop every consumer of the affected queue, including restart supervisors. Record the cutoff time, in-flight attempts and outcomes. With writers stopped, preserve the original `APP_KEY`, exact prior images, configuration and a quiescent snapshot of the complete affected stores. Verify the snapshot can be read. Keep it separate from the writable candidate volumes. [Backup procedure](#back-up-before-edits-or-upgrades)
3. Restore the snapshot into fresh candidate volumes. With producers and workers held, check mounts, the original key, migrations and effective configuration. Account for pending, reserved and failed jobs and external handoffs across the cutoff. Resume the worker only after excluding confirmed-sent and unknown work from replay. Run one authorized native test with scheduling paused, check the relevant queue and receipt, then resume dispatch. [Ambiguous send reconciliation](#ambiguous-sends-automatic-retry-versus-manual-resend)
4. **On failure**, pause producers and consumers again. Preserve the failed candidate volumes and its private job/event records. Restore the previous pinned images, matching configuration, original key and pre-upgrade snapshot into **new rollback volumes**. Keep the snapshot intact. Restore the prior authoritative Ghost settings, reverse-proxy config and any DNS changes within scope. Before starting any worker, compare restored jobs and Ghost submissions with all handoffs since the snapshot, including attempts on the failed candidate. Quarantine handed-off and unknown attempts. If reconciliation or quarantine is incomplete, keep consumers and dispatch paused. Verify the restored path with a single authorized test before releasing scheduling.

**Synthetic rollback rehearsal.** In the isolated project, hold consumers and
queue three uniquely tagged requests. Take the quiescent snapshot before any
worker runs. On the candidate, allow only the first request and its downstream
SMTP child jobs to run. Keep the second confirmed unsent. Withhold the third
request's outcome from the recovery operator to exercise unknown-state handling.
Preserve the failed candidate and record fixture counts, then restore into a
fresh volume. Match each request to its queue payload and reconcile against
post-snapshot handoffs. Preserve the quarantined payloads and timestamps
privately. After worker restart, require a single new capture for the eligible
request, zero for both quarantined requests across the configured retry window
and no residual retryable work. Record the image digests, matching `APP_KEY`
result, before/after counts and private recovery locations.

For the tested SQLite image, the maintenance project ran nginx and PHP-FPM
from a private copy of `/etc/Procfile` with its `queue:` entry omitted. The
ordinary image entrypoint starts its bundled worker. Check every container's
process list, stop the maintenance HTTP service, and then snapshot the database
while writers are held. Place the restored copy in a fresh volume with the
inspected runtime's ownership and verify the effective `APP_KEY` matches
privately before starting a worker.

On the isolated restored copy, match the test subject and recipient in
`newsletter_requests.original_request` to the request ID, then confirm that ID
and its model type in the JSON job payload. Verify each exact job's queue,
attempt count, reservation and availability. Preserve the full rows and payloads
of the reconciled handed-off and unknown jobs privately. Quarantine only those
rows from the runnable queue in one SQLite transaction. Require the expected
row identities and counts, or roll back the transaction and leave the worker
stopped. Retain the untouched snapshot and failed candidate for comparison.
These checks were exercised on three fresh unreserved jobs. For reserved,
released or nested jobs on a deployed queue, identify and reconcile every
related payload against the deployed job schema before adapting the procedure.
[Tested image and counts](upstream.md#support-matrix)

In the rehearsal, `php artisan queue:work --stop-when-empty --tries=3
--timeout=90` processed the eligible request and its SMTP child work. A
subsequent live worker observed the restored queue for at least the configured
180-second retry window. Verify counts and job state after the window before
resuming dispatch.

## Health diagnostics without source modifications

If /health reports Resend-specific warnings on an SMTP route, compare the selected
release's controller and documented checks. Report irrelevant warnings separately
from SMTP failures; do not edit the controller or suppress checks to obtain a green
page. Use a fixed upstream release when available. /up remains a liveness check,
never an end-to-end health guarantee.

## Migrate when volume or analytics require it

Back up before switching. Verify the provider domain, quota and credentials, then set both selectors in the proxy environment:

```dotenv
MAIL_MAILER=resend
OUTBOX_PROVIDER=resend
```

Supply `RESEND_API_KEY` and `RESEND_WEBHOOK_SECRET` privately and expose `/api/webhook/resend` over HTTPS. The controller at the inspected revision handles these subscriptions:

| Resend event | Signal to exercise |
|---|---|
| `email.bounced` | Bounce |
| `email.clicked` | Provider-tracked click when enabled |
| `email.complained` | Complaint |
| `email.delivered` | Delivery |
| `email.delivery_delayed` | `failed` event with `temporary` severity |
| `email.failed` | Delivery failure |
| `email.opened` | Provider-tracked open when enabled |

Subscribe to `email.delivery_delayed` and include a signed delay event in acceptance when delay visibility is required. Omitting this subscription leaves the other recognized events independently processable. Enable provider open tracking if needed and disable provider click tracking to preserve Ghost's link rewriting. Validate signatures, correlated ingestion and Ghost polling with the selected image and real signed provider events. Preserve the existing Ghost proxy origin/key when applicable and retain the separate transactional transport unless its migration is in scope. [Pinned controller](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/app/Http/Controllers/Webhooks/ResendWebhookController.php)
