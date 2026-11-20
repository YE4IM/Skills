# Upstream evidence and compatibility boundaries

The source reviews below are dated 2026-11-10 unless a later date is stated.
Verify compatibility against the selected image digest and installed component
versions before deployment. Historical observations are not a guarantee for a
new host, architecture, or digest.

## Support matrix

Keep author records, independent corroboration, later isolated repairs, and this
package's local tests separate. Do not promote one column into another. Local
Python tests in this skill do not certify SMTP, TLS, Docker, or inbox delivery.
The proxy application's PHP test suite is also separate evidence: 123 tests
(672 assertions) passed on PHP 8.4.27 and 8.5.12 in the code-fix workflow, using
Laravel's array transport, not Docker or a live mail sink. Never pin `latest`.
Never treat a local image ID as a published registry manifest digest.

### Published images recorded on 2026-11-19 (linux/amd64)

| Component | Runtime and image |
|---|---|
| Ghost | 6.78.0, `ghost@sha256:baa6dbff91a28ba36c526d1f6e761deb2efe3c238c630c3f318b62f258c2d76e` |
| Proxy (known failure with Ghost 6.78.0 native preview) | Laravel 13.6.0, Symfony Mailer 8.0.8, `ghcr.io/eznix86/mailgun-proxy-for-ghost@sha256:d3fbcd4f209ec27dbce81f8ff013ae8d09b833bbe5ac72715706b39fc575e33c` (no OCI source revision label) |
| Bridge | Package `3.19.0-1`, `shenxn/protonmail-bridge@sha256:3717b4441130675dc9131196de9f9c5287d2ea21b138d83b0486429e1737638a` (OCI revision `540ba69528378b4fd7d557807d69ee9a03a64dcf`) |

That published proxy image's installed Laravel version differs from the Git
lockfile reviewed below (13.9.0 at `fb35a74000fe70e7d49f46cae3c895674571ea20`).
A repository revision does not prove a registry image contains the same code.

| Check | Author isolated run (2026-11-19) | Independent corroboration (2026-11-19) | Later isolated repair (2026-11-19) | This skill package |
|---|---|---|---|---|
| Simple authenticated proxy POST on the published digest | HTTP `200`, literal `id` `message-id`, one correlated `accepted` event, one fixture capture | Not re-executed | Not re-executed on that digest | Helper tests only, with synthetic data |
| Event pagination | With `limit=1`, `/events/<cursor>` links; three pages, intended subject matched once | Not re-executed | Not re-executed | Helper pagination tests use synthetic pages |
| Ghost config precedence | Complete env triple overrode Admin; removing env used Admin; expected `401` on the second key | Not re-executed | Not re-executed | Not re-executed |
| Ghost 6.78.0 native preview with the published proxy digest above | Ghost returned `204`; proxy accepted the HTTP request; both previews failed delivery with zero captures; Ghost supplied `h:Message-Id`; worker passed `UnstructuredHeader` where Symfony required `IdentificationHeader` | Worker logs on the same digest pair showed `App\Mail\GhostNewsletter` failing with that exact header-type error | The published digest was not re-run as a success. Public `main` and revision `fb35a74000fe70e7d49f46cae3c895674571ea20` still set those headers through `Headers(text: ...)`. See the fork-commit row below for a later isolated pass on a different image | Documented only. This skill does not patch a running image |
| Bridge default certificate | Offline export had only IP SAN `127.0.0.1` | Confirmed on the same digest | Unchanged default | Documented |
| Import from a path the resident process cannot read | Fresh-process export could show the new SAN | Resident startup logged `Failed to read certificate from file, using default` | Confirmed as a failed persistence setup | Documented as a failure mode |
| Import from a persistent `/root` path, resident restart, export | Not completed in the author table as a resident-log check | — | Resident logs for the new session had no default-fallback line; same-volume export matched the intended fingerprint and DNS SAN | Documented. Still not live STARTTLS |
| Live Bridge STARTTLS, untrusted CA, wrong hostname, Proton inbox | Offline SMTP did not serve a peer certificate; live STARTTLS and authenticated send need an initialized account | Failure traces were consistent with no peer certificate | SMTP could listen without advertising STARTTLS when no account was logged in. Handshake tests were recorded as blocked, not invented | Unproven |
| SQLite rollback rehearsal | Three held jobs; quarantined handed-off and unknown rows; only the confirmed-unsent job captured | Not re-executed | Not re-executed | Not re-executed |

### Isolated source-verified local build (2026-11-19, linux/amd64)

This row is not a published GHCR digest and must not be used as one.

| Item | Recorded value |
|---|---|
| Fork | [YE4IM/mailgun-proxy-for-ghost](https://github.com/YE4IM/mailgun-proxy-for-ghost) |
| Pull request | [PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1) (historically unmerged on 2026-11-19; merged into fork `main` on 2026-11-20 09:43 Asia/Shanghai) |
| Merge commit | `391256f764979101c4c23b4a410a7de4d3183115` (parents `fb35a74000fe70e7d49f46cae3c895674571ea20` and `e31299823886f4db9d026054632907924eb02d49`; this is the fork `main` tip as of that merge) |
| Fix commit (the isolated build that was tested) | `e31299823886f4db9d026054632907924eb02d49` (base `fb35a74000fe70e7d49f46cae3c895674571ea20`) |
| Shared Git tree | `779b7f9a59d9474942bb78739901695396f9b81a` (source equivalence only; the merge was not separately rebuilt or retested) |
| Official commit archive SHA-256 | `96b2654d7cc0254dcdcd7efc55c1f1cf7e2fffe6a49095db3ecc7fe22bf2c9fc` (fix-commit tarball of 2026-11-19 only; do not reuse it for the merge-commit archive) |
| Built runtime | PHP 8.5.13, Laravel 13.9.0, Symfony Mailer and Mime 8.0.8, image User 82 |
| Local image ID | `sha256:4188afefc32d858a55e5787a5549b5f0665bd236aed7bc9640882f5906b15b96` (local `docker image inspect` ID from `--load`; not a registry manifest digest). Local tag used: `mailgun-proxy-for-ghost:ghost-message-id-e312998` |
| Image publish | Not pushed |

| Check | Isolated result on the local build above (2026-11-19) | This skill package |
|---|---|---|
| Application test suite at the fix commit | 123 tests, 672 assertions, passed on PHP 8.4.27 and 8.5.12 in the code-fix workflow (array transport; no Docker mail sink) | Not re-run here |
| Synthetic native-shape POST into the local image | HTTP `200` with a nonempty batch-style response `id` (not the literal string `message-id`); one correlated `accepted` event; one internal STARTTLS capture; a single legal bracketed MIME `Message-Id`; no `IdentificationHeader` worker error | Helper tests only, with synthetic data |
| Laravel `mailbox` driver as a capture sink | HTTP accepted, but no mailbox SQLite file was produced. That path is **not** a proven MIME capture | Do not treat mailbox as a passed capture method |
| Ghost 6.78.0 native preview (`email_previews` HTTP `204`) into the local image | Preview handed off; unique subject present in the delivery row and in one internal STARTTLS capture; one legal MIME `Message-Id`; `failed_jobs` did not increase | Documented. Local Python tests do not run Ghost |
| Correlation identifiers | Correlate by unique subject, and by `X-Proxy-Trace` / `X-Newsletter-Delivery-Id` when present. `deliveries.mailgun_message_id` was a separate 19-character token and is **not** the MIME `Message-Id`. Do not assume the POST `id` equals either value | Helper tests correlate on unique subject; they do not require the POST `id` to be the literal `message-id` |
| Live Bridge STARTTLS, untrusted CA, wrong hostname, Proton inbox | Not run against this image | Unproven |

**Default rule:** do not cut over production newsletters on Ghost 6.78.0 plus the
published proxy digest listed above. That known failure is specific to that
digest (and to unfixed revisions that still build `h:Message-Id` as a text
header). It does not mean every proxy version fails.

A simple POST success or a Ghost preview HTTP `204` is still not a pass. The
fork commit plus this local build passed isolated preview and local STARTTLS
capture only. It does not prove real Proton receipt, live Bridge TLS, or a
published image. Hold production cutover until the [required layers](#compatibility-exit-and-retest)
pass on the image that will actually be deployed, including authorized inbox
receipt when a real Proton route is in scope.

To use the unpublished fix, [build from the pinned commit](deployment.md#build-an-unpublished-fixed-proxy)
and verify the archive source. Do not pull a guessed tag, and do not record the
local image ID as a GHCR or other registry digest.

## Compatibility exit and retest

Stop the affected route and keep the workload isolated when any of the following
is true:

- A native draft preview or equivalent Ghost payload causes the worker to fail
  with `IdentificationHeader` versus `UnstructuredHeader`, or another MIME header
  class error, including `h:Message-Id`.
- The preview API returns HTTP `204` (or the proxy returns HTTP `200`) but the
  correlated job fails, no capture appears, or receipt is unconfirmed.
- Bridge resident logs contain `Failed to read certificate from file, using default`,
  or a post-restart export fingerprint or SAN does not match the intended certificate.
- Peer or hostname verification cannot be kept enabled, or STARTTLS is required
  but not offered.
- Image user, entrypoint, CLI path, event schema, or mailer options differ from
  the inspected evidence and have not been re-validated.

To accept a later candidate pair, use new isolated volumes that do not overwrite
the previous lab. Pin every image by digest, never `latest`. Record digest,
architecture, source revision if labeled, test date, and which layers passed,
failed, or were not run. Use a unique test ID for each POST and do not retry a
POST while the outcome is unknown. Required layers for a native newsletter claim:

1. Isolated native preview (or the exact Ghost payload) processed without worker error.
2. Queue handoff: helper exit 0 and the job has left pending/reserved work.
3. Isolated capture of that unique test, recorded separately from inbox receipt.
   Prefer an internal SMTP STARTTLS capture with peer and hostname verification
   enabled. An `accepted` event with a Laravel `mailbox` driver and no mailbox
   store is not capture proof.
4. Authorized inbox receipt if a real Proton route is in scope.
5. When STARTTLS is actually offered (including a real Bridge listener), an
   untrusted CA and a wrong hostname must each fail, followed by one authorized
   trusted-transport send.

Publish or switch production only after those layers pass on the candidate
image that will actually be deployed. Author success on one pair, or on a
local unpublished build, does not extend to an untested pair or to a later
registry image. If the candidate is an unpublished local build, pin and verify
the source commit, record the local image ID as a local ID only, and rebuild
from that commit rather than moving the ID between hosts as if it were a
digest.

## Source and image address policy

The default source and maintenance entry for the Message-Id-fixed proxy is
the YE4IM fork. The unmodified Bridge project's default source is
[shenxn/protonmail-bridge-docker](https://github.com/shenxn/protonmail-bridge-docker).
Immutable upstream evidence links below retain their original provenance.
Published container paths stay with their actual publishers; do not invent a
YE4IM registry image. See [source versus image address policy](address-policy.md).
The merge and the tested fix share Git tree
`779b7f9a59d9474942bb78739901695396f9b81a`. That is source equivalence, not a
fresh image test and not proof of Proton delivery.

## Source authority and limits

Product support boundaries come from Ghost and Proton; the proxy and Bridge
container maintainers define their community integration contracts. Locked Laravel
and Symfony source establishes native option handling, not vendor endorsement.
If documentation and the selected release disagree, record the conflict and resolve
it before mutation. Never silently substitute local patches for upstream behavior.

- [Ghost's newsletter support boundary](https://docs.ghost.org/faq/mailgun-newsletters):
  native newsletters officially support the Mailgun bulk API. This community proxy
  does not become an official backend by reproducing that interface.
- [Proton sending limits](https://proton.me/support/email-sending-limits): Mail is
  not designed for bulk mailing. Token eligibility and successful tests alone do
  not establish suitability for a production newsletter. Check current guidance
  and account-specific suitability; no universal safe subscriber count is known.
- [Proton Bridge TLS model](https://proton.me/support/bridge-ssl-connection-issue):
  official Bridge uses a local loopback connection and a generated certificate.
  Docker relaying is the unofficial container project's extension, not Proton's
  documented official topology. Validate certificate trust and hostname; the skill
  no longer offers verification bypasses.

## Source revision

The previous review recorded the inspected proxy source tree as
`fb35a74000fe70e7d49f46cae3c895674571ea20`. Downloaded README, five docs, .env.example,
mail.php, queue.php, Dockerfile, entrypoint and Procfile were checked against their Git blob
hashes in that tree. Links below use that immutable revision where applicable.
The deployed image must be checked independently; a repository revision does not
prove a registry image contains the same code.

## Manual-to-skill checks

| Topic | Primary source | Result and treatment |
|---|---|---|
| Native newsletters vs transactional SMTP | [Ghost FAQ](https://docs.ghost.org/faq/mailgun-newsletters) | Preserved the separate paths; proxy is a community workaround |
| Nested env and precedence | [Ghost configuration](https://docs.ghost.org/config#running-ghost-with-config-env-variables) | Double underscores and env priority confirmed; explicit Compose injection added |
| Proxy auth, mailers and analytics | [Configuration](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/docs/configuration.md) | MAILGUN_API_KEY is shared Basic password; MAIL_MAILER and OUTBOX_PROVIDER aligned; SMTP has local accepted/failure events, no remote analytics ingestor |
| Origin and Ghost config | [Ghost setup](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/docs/ghost-setup.md) | Dedicated origin root and complete configuration confirmed; upstream recommends config file, while this recipe uses explicitly injected env as a deliberate Docker choice |
| Database, worker and dashboard | [Deployment](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/docs/deployment.md) | /data SQLite, startup migrations, bundled worker and first-user registration confirmed; create admin before public access |
| Send/event contract | [How it works](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/docs/how-it-works.md) | SMTP is per-recipient; Resend batch idempotency must not be generalized to SMTP |
| Suppression and click tracking | [Troubleshooting](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/docs/troubleshooting.md) | Suppression-removal routes are logged no-ops; provider click tracking should stay off when Ghost rewrites links |
| Native SMTP configuration | [mail.php](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/config/mail.php) | Upstream exposes MAIL_URL; locked Laravel parses its query into SMTP options. Use native require_tls/timeout options, no source patch |
| Container bootstrap | [Dockerfile](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/Dockerfile), [entrypoint](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/docker/fpm/entrypoint-fpm.sh) | Config path, UID 82 and env-based key persistence checked; extract from stopped container; retain key in private env configuration |
| Retry defaults | [Procfile](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/docker/fpm/Procfile) | Bundled worker uses three tries, 90-second timeout; sleep is not SMTP pacing |
| Bridge tags and initialization | [Bridge README](https://github.com/shenxn/protonmail-bridge-docker#readme), [entrypoint](https://github.com/shenxn/protonmail-bridge-docker/blob/master/build/entrypoint.sh) | Architecture differs by tag; init creates GPG/pass state; runtime relays internal 25 to 1025. Existing stores use scoped re-login, not fresh init |
| SMTP token entitlement | [Proton SMTP manual](https://proton.me/support/smtp-submission) | Current manual includes paid Mail plans with custom-domain addresses, port 587 STARTTLS; removed business-only assertion |

## Local choices and unresolved runtime checks

These are local integration guidance, not upstream feature promises:

- A missing Bridge dependency is a release/architecture compatibility failure.
  Choose a fixed upstream release or documented build; do not prescribe local
  package injection based on the historical Bridge 3.27.1 observation.
- Bridge trust requires both trusted certificate material and a matching hostname.
  If those cannot be configured through the selected runtime's supported interface,
  report the route blocked rather than disabling peer or hostname verification.
- HealthController warning scoping is an upstream issue; report irrelevant
  Resend warnings without rewriting application checks.
- The inspected proxy docs have no general Proton SMTP limiter setting. See
  [operations](operations.md#throttling-retries-bounces-and-duplicates) for worker
  defaults, local retry_after tuning, timeout ordering and ambiguous-send handling;
  compare the deployed image's [queue configuration](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/config/queue.php)
  before applying that guidance.
- Upstream text mentions both provider event clicks and Ghost's own rewritten links.
  Treat these as separate paths and test the latter; do not promise universal click
  statistics solely because an SMTP send succeeded.
- No verified daily sending quota or safe list-size threshold is supplied. Check
  the live account's limits, provider terms and measured delivery before a campaign.
- Direct SMTP is an optional simplification supported by Proton's current manual;
  it still needs the Mailgun-compatible proxy for Ghost native newsletters.

## Recheck during deployment

Recheck the affected contract when any trigger below occurs; unchanged evidence
can be reused when its source/image mapping and deployment assumptions still hold.
Check live account entitlements/limits before a new deployment or campaign regardless
of code pinning. A dated source review is not a runtime acceptance result.

| Trigger | Recheck |
|---|---|
| Proxy image digest, architecture or source changes | Image/source mapping, config, entrypoint, internal port, migrations, worker/retry behavior, API/event schema, registration; isolated target acceptance |
| PHP, Laravel/Symfony lockfile, mail.php or MAIL_URL changes | Exact supported options and effective transport; native URL parsing, certificate/hostname verification, fail-closed STARTTLS and one intended-transport test |
| Bridge image, runtime binary, persisted store or certificate changes | CLI/init behavior, library needs, store compatibility, locks, fingerprint/SAN/trust and affected clients |
| Ghost or Nodemailer changes, mail source/precedence changes | Effective bulk/transactional configuration for the affected path, TLS options, native tests, event polling/link behavior when relevant |
| SMTP provider, credentials/sender, network/origin or trust route changes | Entitlements/DNS, reachability, origin/auth, transport/TLS, correlation and authorized receipt; preserve unrelated paths |
| Worker concurrency, timeout, retry_after, job code or pacing changes | Retry timing, pause/quarantine procedure, reservation overlap and measured pacing before dispatch |

## Targeted source review on 2026-11-10

The previous review recorded re-fetching selected proxy files at the same immutable
revision and checking their Git blob hashes against its tree. Its composer.lock pins Laravel 13.9.0 and
Symfony Mailer 8.0.8; their exact locked source was inspected for option handling.
This adds source evidence only, without certifying an image or SMTP delivery.

- [Event query](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/app/Actions/Mailgun/ListMailgunEvents.php)
  filters recipient, time and stored message ID; tags are not filtered. The
  [contract tests](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/tests/Feature/GhostMailgunEventsContractTest.php)
  document why POST response ID and event message-id need not round-trip.
- [Registration](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/app/Support/Registration.php)
  is available only with no users. Its
  [tests](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/tests/Feature/Auth/RegistrationTest.php)
  expect an existing-user GET to redirect and POST to return 403.
- Locked [Laravel MailManager](https://github.com/laravel/framework/blob/a0c6ad03b380287015287d8d5a0fa2459e2332fd/src/Illuminate/Mail/MailManager.php)
  passes SMTP config to Dsn options. Locked
  [Symfony factory](https://github.com/symfony/mailer/blob/ca5f6edaf8780ece814404b58a4482b22b509c56/Transport/Smtp/EsmtpTransportFactory.php)
  honors require_tls and exposes per-transport max_per_second; its
  [transport](https://github.com/symfony/mailer/blob/ca5f6edaf8780ece814404b58a4482b22b509c56/Transport/Smtp/EsmtpTransport.php)
  exposes isTlsRequired and rejects a connection without required TLS.

## Native-configuration revision on 2026-11-10

Re-fetched the pinned proxy deployment/configuration/Ghost-setup docs, mail.php,
Dockerfile and entrypoint, plus the locked MailManager, ConfigurationUrlParser and
EsmtpTransportFactory, SocketStream and KeyGenerateCommand; the composer.lock
versions/references were also reconfirmed. This pass checked their contents; it did not repeat the
previous tree-wide Git blob verification or run an image. Bridge README/entrypoint
were read from mutable master and must be checked against the selected image.

The locked [ConfigurationUrlParser](https://github.com/laravel/framework/blob/a0c6ad03b380287015287d8d5a0fa2459e2332fd/src/Illuminate/Support/ConfigurationUrlParser.php)
merges URL host/port and query options over the base mailer config, retaining
username/password when URL userinfo is absent. Query `true` becomes boolean true.
MailManager resolves that URL before constructing the SMTP transport and applies
`timeout` to its socket. This supports a credential-free endpoint URL such as
`smtp://smtp.protonmail.ch:587?require_tls=true&timeout=30` together with separate
MAIL_USERNAME/MAIL_PASSWORD, without replacing mail.php. The timeout value is a
local choice; native support does not make it an upstream recommended value.

Removed the local PHP patch helper and its tests because native configuration now
owns TLS settings. Removed application-controller edits, dependency injection and
manual lock removal as prescribed operations. Existing deployment overrides must
be backed up and replaced only after isolated acceptance, not deleted blindly.

No PHP/Docker runtime was available in this maintenance environment. URL behavior
above is source-verified; negative TLS tests and real delivery remain deployment
acceptance requirements. Local Python checks do not certify this transport.

Keep concrete commands/pass conditions in
[operations](operations.md#concrete-checks-for-the-inspected-source), route examples
and trust setup in [deployment](deployment.md), and core boundaries in SKILL.md.
Resolve images to digests and inspect source labels, configuration and bundled
runtime. Record date, architecture, Ghost version, proxy digest/source, Bridge image
and runtime, configuration hashes and acceptance results. If source and image differ,
resolve the mismatch before proceeding. Stop production sending when upstream
support requirements, provider suitability, pacing or delivery status are unresolved.

## Isolated runtime notes on 2026-11-19

The [support matrix](#support-matrix) is the authoritative split of author
records, independent log corroboration, later repair evidence, and the
source-verified local build. Additional author-run detail:

- A separate HTTPS `302` containing an `id` was rejected by the acceptance helper.
- Effective Symfony settings on the published proxy digest required TLS and peer
  verification, with a 30-second socket timeout. The later local build used the
  same require_tls and verify_peer settings against an internal STARTTLS sink.
- The redacted Ghost loader probe reported exact match and mismatch booleans
  without printing secret values.
- Offline export of a default Bridge certificate had only the `127.0.0.1` IP SAN.
  A later export could be validated for the intended hostname and fail for a
  different hostname, but that offline check is not a live SMTP proof.
- In the SQLite rollback rehearsal, after 185 seconds with the restored worker
  active and `retry_after=180`, counts were still 1 handed off before rollback,
  1 eligible and 0 unknown. Both `jobs` and `failed_jobs` were empty.
- On the published digest, a successful simple POST could return the literal
  response `id` `message-id`. On the local build of
  `e31299823886f4db9d026054632907924eb02d49`, the HTTP `id` was a batch-style
  identifier, not that literal string, and `deliveries.mailgun_message_id` was
  a separate 19-character token. Correlate by unique subject and optional
  delivery or trace headers.

The published-digest incompatibility lives in the proxy newsletter mailer
([`app/Mail/GhostNewsletter.php`](https://github.com/eznix86/mailgun-proxy-for-ghost/blob/fb35a74000fe70e7d49f46cae3c895674571ea20/app/Mail/GhostNewsletter.php)
at `fb35a74000fe70e7d49f46cae3c895674571ea20` and still on upstream `main` as
of 2026-11-19, confirmed again on 2026-11-20). This skill must not patch a
running image or rewrite that application source in place. The documented fix
is the fork commit `e31299823886f4db9d026054632907924eb02d49`, now also
present on the fork `main` via merge `391256f764979101c4c23b4a410a7de4d3183115`.
Until a published image contains that change, follow
[build an unpublished fixed proxy](deployment.md#build-an-unpublished-fixed-proxy)
and [compatibility exit and retest](#compatibility-exit-and-retest) on new
isolated volumes. Do not treat the merged pull request or a local image ID as
a production registry pin.
