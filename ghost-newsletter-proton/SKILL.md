---
name: ghost-newsletter-proton
description: >-
  Deploy, repair, or upgrade a Mailgun-compatible proxy for self-hosted Ghost
  newsletters sent through Proton Mail, using direct SMTP tokens where available
  or headless Proton Bridge. Diagnose Bridge locks, SMTP certificate failures,
  and Ghost ESOCKET errors. Not for Ghost(Pro) hosting, unrelated Proton setup,
  or production cutover until the selected Ghost and proxy pair passes native
  preview, capture, and receipt checks. Ghost 6.78.0 with the recorded published
  proxy digest remains a known native-preview failure. A fork commit has passed
  isolated preview plus local capture only after a source-verified local build;
  real Proton receipt and live Bridge TLS are still unproven.
---

# Ghost newsletters through Proton

Ghost's native newsletter pipeline uses the Mailgun API; transactional mail has
its own SMTP configuration. Use a compatible proxy for newsletters. Modify
transactional SMTP only when requested or implicated in the reported fault;
otherwise preserve its configuration and credentials. This is a community
integration, not an officially supported alternative Ghost backend. The Bridge
container is also unofficial.

## Support status

Treat the [support matrix](references/upstream.md#support-matrix) as binding.
Author records, independent log corroboration, isolated repairs, and this
package's local tests are listed separately. The proxy application's 123
automated tests and this skill's local Python tests are different evidence;
neither certifies live Proton delivery.

Ghost 6.78.0
(`ghost@sha256:baa6dbff91a28ba36c526d1f6e761deb2efe3c238c630c3f318b62f258c2d76e`)
with the published proxy
`ghcr.io/eznix86/mailgun-proxy-for-ghost@sha256:d3fbcd4f209ec27dbce81f8ff013ae8d09b833bbe5ac72715706b39fc575e33c`
failed native preview handoff (`h:Message-Id` built as `UnstructuredHeader`).
**Do not cut over production on that published pair.** That failure does not
mean every proxy revision fails.

A Message-Id fix exists on the fork commit
`e31299823886f4db9d026054632907924eb02d49`
([YE4IM/mailgun-proxy-for-ghost](https://github.com/YE4IM/mailgun-proxy-for-ghost)).
[PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1) merged that
commit into the fork `main` on 2026-11-20 09:43 Asia/Shanghai as
`391256f764979101c4c23b4a410a7de4d3183115`. The merge and the fix share Git
tree `779b7f9a59d9474942bb78739901695396f9b81a`. On 2026-11-19 an isolated
linux/amd64 build of `e31299823886f4db9d026054632907924eb02d49` (PHP 8.5.13,
Laravel 13.9.0, no image publish) passed a synthetic native-shape POST and a
Ghost 6.78.0 native preview, each correlated with one local STARTTLS capture
and a single legal MIME `Message-Id`. The merge commit was not separately
rebuilt or retested; tree equality is not a new runtime result. A local image
ID is not a registry manifest digest. Upstream `main` and
`fb35a74000fe70e7d49f46cae3c895674571ea20` were not re-declared fixed. Prefer
building the verified pin `e31299823886f4db9d026054632907924eb02d49` and
verify its recorded archive hash before use.

A simple proxy POST or a Ghost preview HTTP `204` is still not a pass. Isolated
capture is not real Proton receipt. Live Bridge STARTTLS, untrusted-certificate
rejection, and wrong-hostname rejection remain unproven. **Do not describe
production newsletter delivery as fully repaired.** See
[compatibility exit and retest](references/upstream.md#compatibility-exit-and-retest).

## Upstream compliance gate

Use the selected upstream release's documented interfaces and verified dependency
configuration. Do not rewrite application source, patch health checks, disable
certificate verification, or invent environment switches to make a check pass.
If the installed release cannot meet a requirement through supported configuration,
report the incompatibility and select a compatible upstream release or route within
the user's scope. Preserve existing changes until a tested replacement is ready.
Run a native draft preview in isolation before cutover. Confirm the proxy worker
can process the exact payload Ghost sends, including `h:Message-Id` where present.

Ghost officially supports Mailgun for native bulk delivery; this proxy provides a
community compatibility contract only. Proton states that Mail is not designed
for bulk mailing. SMTP-token eligibility does not establish newsletter suitability.
For production Proton campaigns, establish account-specific suitability with current
provider guidance/support before proceeding; never infer it from a small successful
test or an invented list-size threshold. If all-vendor official support is required,
this integration cannot satisfy it: explain the conflict and propose Ghost's
supported Mailgun route without silently migrating the user's service. See
[source authority and limits](references/upstream.md).

## Choose the work before changing anything

- **New deployment:** read [deployment](references/deployment.md), then
  [verification and operations](references/operations.md).
- **Repair:** inspect the existing services and effective configuration; read
  the symptom in [operations](references/operations.md). Change only the failing
  layer; do not repeat initialization or replace working credentials.
- **Upgrade:** read the backup and rollback sections in operations first. Replace
  legacy patches with verified native configuration in isolation before removing
  their mounts; never mount old source over a new release.
- **Provider choice or uncertain compatibility:** consult
  [upstream evidence](references/upstream.md). Recheck current manuals and the
  selected versions using its recheck triggers; historical observations are not guarantees.

Prefer the existing compatible proxy and network configuration. The default
source and maintenance entry for the Message-Id-fixed proxy is
[YE4IM/mailgun-proxy-for-ghost](https://github.com/YE4IM/mailgun-proxy-for-ghost)
(default branch `main`). The unmodified Bridge project's default source and
maintenance entry is
[shenxn/protonmail-bridge-docker](https://github.com/shenxn/protonmail-bridge-docker)
(GPL-3.0, default branch `master`). The proxy's original upstream is
`eznix86/mailgun-proxy-for-ghost` (AGPL-3.0). A source fork is not an image
publisher. See [source versus image address policy](references/address-policy.md).
Switching projects requires checking their API, queue, TLS, persistence,
authentication, and event contracts.

## Preflight decisions

1. Inventory Ghost version, Compose service names, networks, reverse proxy,
   active mail configuration, existing jobs, and current image digests. Read
   secrets locally without printing them. Preserve the current working mail path.
2. Check the account's actual SMTP-token and Bridge entitlements. Proton's
   current SMTP manual includes paid Mail plans with custom domain addresses;
   the former business-only assumption is obsolete. Prefer direct SMTP for a
   new send-only setup if available, unless the user explicitly chose Bridge.
3. Confirm the authorized sender and Proton domain DNS instructions. Assess
   sending volume against current account limits and acceptable-use terms.
   There is no verified universal safe subscriber threshold or daily quota here.
4. Select pinned image digests and supported CPU architecture, or a source-verified
   local build of a pinned commit. Record image, source revision where known,
   Bridge runtime version, configuration hashes, check date, and acceptance
   results locally without secrets. Never pin `latest`. Never treat a local
   image ID as a published registry digest.
5. Back up affected configuration and persistent data before mutation. Prepare a
   rollback target before modifying Ghost or exposing the proxy.
6. If the selected pair is the known-failed published digest above, keep work
   isolated and do not plan production cutover on that pair. If using the
   local build of the verified fix commit, still hold production cutover until
   native preview, capture, and real receipt (and Route B live TLS) pass on
   that deployment. The merged pull request is not a published image.

## Required invariants

- Proxy owns a dedicated HTTPS origin root, never a sub-path. Ghost reaches its
  `/v3/...` endpoints; Basic username is `api`, password matches `MAILGUN_API_KEY`.
- Ghost and SMTP clients share the necessary Docker networks. The reverse proxy
  reaches the proxy on its actual internal port; no Bridge host ports are needed.
- Create configuration files before bind-mounting them. Keep upstream application
  files intact. Generate APP_KEY before first proxy startup and retain it.
- Ghost `.env` variables must be explicitly injected via Compose `env_file` or
  `environment`. Choose one authoritative bulkEmail configuration source and
  verify the effective values without disclosing keys or passwords.
- Require TLS and certificate/hostname verification for SMTP. For Bridge, generate
  a certificate with a DNS SAN that matches the hostname in `MAIL_URL`, store it on
  the persistent Bridge volume, import those paths with the selected CLI, and mount
  a PHP or Node trust bundle without disabling verification. Offline fingerprint
  checks are not SMTP or inbox proof. See
  [Bridge certificates](references/deployment.md#5-tls-options).
- Bridge account data is in a persistent volume; application env files still hold
  SMTP secrets in plaintext. Protect both and their backups. Avoid command-line
  passwords, transcript capture, full configuration dumps, and public admin signup.
- A running container or `/up` response does not prove the worker or delivery works.
  Judge [acceptance layers](references/operations.md#acceptance-layers) separately:
  HTTP enqueue, queue handoff, Ghost native preview, isolated SMTP capture, and
  real receipt. `accepted` is not final delivery. Correlate with a unique subject
  or trace header, not by assuming the POST `id` or `deliveries.mailgun_message_id`
  equals the MIME `Message-Id`. Zero matches and unknown job state do not
  authorize a resend or replay.
- Send only to the authorized test recipient during validation. Reserve each
  [acceptance run directory](references/operations.md#acceptance-use-an-authorized-test-recipient)
  for one POST attempt and keep the original evidence for read-only reconciliation.
  Investigate ambiguous outcomes before any new attempt.

## Finish criteria

Apply the scope-specific [acceptance matrix](references/operations.md#acceptance-scope)
and the [verification checklist](references/checklist.md). Newsletter deployment
requires proxy authentication, queue processing, correlated event polling, a
native Ghost preview that actually hands off, isolated capture of that unique
test, and confirmed receipt (fixture capture and real inbox are recorded
separately). Test a real Ghost login email only when transactional mail is in
scope. Check a Ghost-rewritten link if click analytics matter. Report versions,
changes, evidence, analytics limits, remaining failures, and the rollback
location. If a required external check cannot run, state that limitation rather
than claim end-to-end success. Do not send a production campaign as a validation
step.

For each run, record the platform, component versions, image digests or local
build IDs (labeled as such), verification results, private evidence locations
and rollback location.

## Offline tests and packaging

From the unpacked skill directory, after any edit of the helper or tests:

```sh
python3 -m compileall -q scripts tests
python3 -m unittest discover -s tests -v
```

These tests use synthetic data and must not use the network or send mail. Do not
run other package scripts against a live deployment as a substitute for this check.

To package the skill, write the archive outside this directory, with no symbolic
links, caches, private keys, credentials, backups, or runtime evidence:

```sh
COPYFILE_DISABLE=1 zip -rX ../ghost-newsletter-proton.zip SKILL.md CHANGELOG-zh.md references scripts tests \
  -x '*/__pycache__/*' '*.pyc' '.DS_Store' '*/.DS_Store'
```

If `zip` is unavailable, `COPYFILE_DISABLE=1 tar --exclude='.DS_Store' --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' -czf ../ghost-newsletter-proton.tar.gz SKILL.md CHANGELOG-zh.md references scripts tests` is an equivalent source archive. Record the SHA-256 of the archive after packing.
