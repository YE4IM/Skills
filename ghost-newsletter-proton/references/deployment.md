# Deployment reference

Contents: route selection; common Compose; native TLS configuration; Bridge; TLS trust;
startup; origin/admin; unpublished local proxy builds; newsletter cutover; optional transactional mail.
Commands run on the deployment host in its private deployment directory. Replace
service names and example values with inspected values. This document is a
version-sensitive recipe; see [upstream evidence](upstream.md).

## 1. Prepare and select the SMTP route

Use a separate directory such as `/opt/newsletter`; retain the existing Ghost
stack. Set `umask 077`. Back up as described in [operations](operations.md).
Validate domain records against Proton's domain dashboard, including the actual
DKIM selectors (DKIM can be CNAME, so a TXT-only probe is insufficient).

For **direct SMTP**, verify the account can generate a token for the intended
custom-domain sender. Proton's documented endpoint is `smtp.protonmail.ch:587`
with STARTTLS; use the token's address and password, never the account password.
Use a separate token for each client/address as Proton recommends; do not reuse
an unrelated transactional client's token. Skip Bridge initialization and trust setup.
This endpoint supports application SMTP; it does not establish bulk-mail suitability.
Apply the compliance gate in SKILL.md before planning a production campaign.

For **Bridge**, inspect the chosen image's architecture and entrypoint. Use an
upstream image that runs successfully on the target architecture. If a dependency
such as libfido2 is missing, record the failure and use a fixed upstream release
or its documented build procedure; do not install ad hoc packages into the image.
Inspect runtime version too: Bridge can update binaries inside `/root`, independently
of the image digest. Image pinning alone cannot roll that update back.

## 2. Private configuration and Compose

First complete [Build an unpublished fixed proxy](#build-an-unpublished-fixed-proxy).
The default below is a local tag built from the verified fixed commit, not a
pullable registry image. Create `.env` for Compose interpolation:

```dotenv
PROXY_IMAGE=mailgun-proxy-for-ghost:ghost-message-id-e312998
GHOST_NETWORK=<existing-network-name>
```

Only the Bridge route adds BRIDGE_IMAGE (see its block below). Do not paste
unresolved placeholders into a live deployment. Label `PROXY_IMAGE` as a
local build of `e31299823886f4db9d026054632907924eb02d49`, not a registry
digest. Do not default this value to the published digest recorded as a known
native-preview failure in the [support matrix](upstream.md#support-matrix),
and do not invent a YE4IM registry tag. If a later published image actually
contains the fix, pin that new digest and re-run acceptance; ignore the
earlier local ID.

Create `newsletter-proxy.env` with mode 600. Its directory must be private;
secret env files remain 600. Mounted trust files must be readable by the client UID:

```dotenv
APP_NAME=NewsletterProxy
APP_ENV=production
APP_DEBUG=false
APP_KEY=<generated-before-start>
APP_URL=https://mg.example.com
LOG_CHANNEL=stderr
LOG_LEVEL=info
DB_CONNECTION=sqlite
DB_DATABASE=/data/database.sqlite
SESSION_DRIVER=database
QUEUE_CONNECTION=database
DB_QUEUE_RETRY_AFTER=180
CACHE_STORE=database
MAIL_MAILER=smtp
OUTBOX_PROVIDER=smtp
MAIL_FROM_ADDRESS=mail@example.com
MAIL_FROM_NAME='Example Site'
MAILGUN_API_KEY=<random-shared-secret>
```

DB_QUEUE_RETRY_AFTER=180 is a local tuning choice for the inspected worker's
90-second timeout, not an upstream default. Confirm timeout ordering as described
in operations before sending.

Choose **exactly one** route block and append it to the common proxy env.
Use the upstream `MAIL_URL` entry for endpoint/TLS/timeout, with credentials in
`MAIL_USERNAME` and `MAIL_PASSWORD`. The locked Laravel parser retains those
credentials when the URL omits userinfo. Remove conflicting endpoint variables;
never copy credentials into URL query parameters. This uses existing upstream
configuration, not a new `MAIL_REQUIRE_TLS` or `MAIL_VERIFY_PEER` switch.

### Route A: direct SMTP (default for a new eligible send-only setup)

```dotenv
MAIL_SCHEME=smtp
MAIL_URL='smtp://smtp.protonmail.ch:587?require_tls=true&timeout=30'
MAIL_USERNAME='<SMTP token address>'
MAIL_PASSWORD='<SMTP token password>'
```

Use the common Compose alone, bootstrap below, then skip Bridge initialization
and trust setup. Keep peer and hostname verification enabled. Remove legacy
verification bypasses and source mounts only after the native replacement passes
isolated acceptance. The 30-second socket timeout is local tuning, not a provider
limit or a total job deadline; verify worker timing in operations.

### Route B: Bridge (when explicitly chosen or direct SMTP is unavailable)

```dotenv
MAIL_SCHEME=smtp
MAIL_URL='smtp://protonmail-bridge:25?require_tls=true&timeout=30'
MAIL_USERNAME='<Bridge SMTP username>'
MAIL_PASSWORD='<Bridge SMTP password>'
```

Add `BRIDGE_IMAGE=shenxn/protonmail-bridge@sha256:<resolved-compatible-digest>`
to Compose's `.env` (or the versioned local image for a reproduced dependency
fix). This image is supplied by the third-party publisher `shenxn`, not by
Proton. The default source and maintenance entry is the unmodified upstream
[shenxn/protonmail-bridge-docker](https://github.com/shenxn/protonmail-bridge-docker)
(default branch `master`). Do not invent a YE4IM Bridge registry path.
Recorded Bridge checks cover offline certificate persistence only, not live
TLS or inbox receipt. See
[source versus image address policy](address-policy.md). Then merge these
additions into the common Compose, without replacing existing maps:

```yaml
services:
  protonmail-bridge:
    image: ${BRIDGE_IMAGE:?set a pinned Bridge image}
    restart: unless-stopped
    volumes:
      - bridge-data:/root
    networks: [ghost_net]
volumes:
  bridge-data:
```

Initialize only a new empty store in step 4. Configure certificate trust in step 5.
The hostname in `MAIL_URL` must appear as a DNS SAN on the certificate served by
Bridge. Issue and import that certificate rather than trying to work around the
default `127.0.0.1` IP SAN with a Docker network alias; an alias cannot make a
container IP match that default SAN. Do not bypass hostname checks.
Both routes require the native URL parsing and TLS support verified in operations;
unknown mailer versions follow its source-inspection gate before startup.

Handle special characters according to Docker Compose env-file parsing. Prefer
single-quoted literal passwords when representable; do not source these files as
shell scripts. Validate a secret containing `$` without logging it or expanding it.

Common `compose.yml` below contains only the proxy. Route B merges in Bridge.
Do not add application-source bind mounts:

```yaml
services:
  newsletter-proxy:
    image: ${PROXY_IMAGE:?set a pinned proxy image}
    restart: unless-stopped
    env_file: [newsletter-proxy.env]
    expose: ["8080"]
    volumes:
      - proxy-data:/data
    networks: [ghost_net]
volumes:
  proxy-data:
networks:
  ghost_net:
    external: true
    name: ${GHOST_NETWORK:?set the existing network}
```

Retain the proxy's network link to Ghost and the reverse proxy. Do not start
services until bootstrap is complete.

## 3. Bootstrap without starting an incomplete application

Pull the selected images, then extract configuration from a **stopped** temporary
container; this does not need Compose, credentials, mounts, a worker, or migrations:

```bash
# PROXY_IMAGE is the resolved pinned value, set separately in this shell.
docker pull "$PROXY_IMAGE"
bootstrap_id=$(docker create "$PROXY_IMAGE")
docker cp "$bootstrap_id:/var/www/html/config/mail.php" ./mail.php.orig
docker cp "$bootstrap_id:/var/www/html/composer.lock" ./composer.lock.reference
docker rm "$bootstrap_id"
```

Use a unique temporary container and remove only the recorded ID on failure.
On reruns extract into a new version-specific staging directory; do not overwrite
an earlier backup. Inspect the extracted files to confirm native MAIL_URL and locked dependency support.

Record the target platform, repository digest or local image ID (labeled as
such), OCI revision label (or “missing”), source commit if this is a local
build, and installed component versions together. Inspect the image with
`docker image inspect --format '{{.Os}}/{{.Architecture}} {{.Id}} {{json .RepoDigests}} {{index .Config.Labels "org.opencontainers.image.revision"}}' "$PROXY_IMAGE"`.
`.Id` is the local image ID. `RepoDigests` is a published registry manifest
digest only when the image was actually pulled or pushed through that
registry; a digest-like value that appears after a local `--load` is still
not a published manifest digest. Read installed PHP, Laravel, Symfony Mailer
and SQLite versions inside that image. Record Ghost/Node and Bridge
package/runtime versions for the selected route.

Generate APP_KEY with the upstream Laravel command before first boot, bypassing
the normal process manager; write only to a private file:

```bash
docker run --rm --network none --entrypoint php "$PROXY_IMAGE" artisan key:generate --show --no-ansi > app-key.private
openssl rand -hex 24 > mailgun-key.private
```

Check command success and key format privately before transferring values to the
env file; remove temporary files afterward. Retain the existing APP_KEY for repairs
and upgrades. Do not use a transient container's .env as persistent key storage.

The locked runtime's `MAIL_URL` parser passes `require_tls=true` to Symfony and
`timeout=30` to the SMTP socket. No mail.php patch or bind mount is needed. Verify
actual transport settings using [operations](operations.md#concrete-checks-for-the-inspected-source).
Validate Compose using `docker compose config --quiet`; do not print the rendered
configuration, which contains secrets. Before production cutover, confirm the
route fails closed when STARTTLS is unavailable in an isolated test.

## 4. Initialize Bridge once

On a new empty volume, run initialization before starting the resident service:

```bash
docker compose run --rm --no-deps protonmail-bridge init
```

Use `login`, complete CAPTCHA/2FA interactively, then `info` and `exit`. Store
SMTP Settings privately; the username may differ from the account login address.
Use a persistent PTY for remote interaction without recording password input.
Fill the proxy env file with Bridge's SMTP credentials, not the Proton password.
Then start Bridge and check the sanitized startup logs and SMTP reachability:

```bash
docker compose up -d protonmail-bridge
```

For existing volumes, do not blindly rerun `init`: the upstream entrypoint
initializes GPG/pass each time. Stop the resident service, check for other owners
of the volume, and use the selected image's Bridge CLI directly for re-login
with `docker compose run --rm --no-deps --entrypoint /usr/bin/protonmail-bridge protonmail-bridge --cli`
for the tested `3.19.0-1` package. See operations for locks.

## 5. TLS options

Direct SMTP uses normal public certificate validation. For Bridge, keep peer and
hostname verification enabled on every client. The default Bridge certificate
contains only the IP SAN `127.0.0.1`. A Docker network alias cannot make a
container hostname match that SAN.

On the tested Bridge digest, two persistence behaviors were distinguished:

- Importing a certificate from a temporary path that the resident container does
  not mount can produce a later export that looks correct, while the resident
  process logs `Failed to read certificate from file, using default` and falls
  back to the `127.0.0.1` certificate. Treat that log line as a failed trust setup.
- Storing the leaf certificate and key on the persistent `/root` volume (for
  example `/root/certs/cert.pem` and `/root/certs/key.pem`), importing those
  resident-visible paths, and restarting the resident process left no default
  fallback in that session's logs. A same-volume export then matched the intended
  fingerprint and DNS SAN.

Those checks prove certificate persistence only. They are not live STARTTLS,
hostname-rejection, or inbox proof. On the same digest, SMTP could listen while
STARTTLS was still unadvertised when no Bridge account was logged in. If STARTTLS
is not offered, mark the handshake tests blocked; do not invent a pass.

### 5.1 Generate a matching certificate (private, not in this package)

Create a private operator directory of mode `700`. Do not copy private keys,
CA keys, or issued certificates into this skill. The commands below are a
template: replace host paths and the DNS SAN, then confirm the issued SAN
before import. They are not executed by this skill.

`$BRIDGE_CERT_DIR` must be a directory on the persistent volume that the
resident Bridge container mounts at `/root`, so the files remain readable after
the one-off CLI exits. Do not import from a temporary `/import` mount that the
resident service does not also mount.

```bash
install -d -m 700 "$TRUST_DIR" "$BRIDGE_CERT_DIR"

openssl genrsa -out "$TRUST_DIR/ca.key" 3072
chmod 600 "$TRUST_DIR/ca.key"
openssl req -new -x509 -sha256 -days 825 -key "$TRUST_DIR/ca.key" \
  -subj "/CN=NewsletterBridgeTestCA" -out "$TRUST_DIR/ca.crt"

openssl genrsa -out "$BRIDGE_CERT_DIR/key.pem" 3072
chmod 600 "$BRIDGE_CERT_DIR/key.pem"

# DNS.1 must be the hostname used in MAIL_URL (example service name below).
cat > "$TRUST_DIR/leaf.cnf" <<'EOF'
[req]
distinguished_name = req_dn
prompt = no
[req_dn]
CN = protonmail-bridge
[v3_leaf]
subjectAltName = DNS:protonmail-bridge
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
EOF

openssl req -new -sha256 -key "$BRIDGE_CERT_DIR/key.pem" \
  -config "$TRUST_DIR/leaf.cnf" -out "$TRUST_DIR/leaf.csr"
openssl x509 -req -sha256 -days 825 \
  -in "$TRUST_DIR/leaf.csr" -CA "$TRUST_DIR/ca.crt" -CAkey "$TRUST_DIR/ca.key" \
  -CAcreateserial -extfile "$TRUST_DIR/leaf.cnf" -extensions v3_leaf \
  -out "$BRIDGE_CERT_DIR/cert.pem"
chmod 644 "$BRIDGE_CERT_DIR/cert.pem"
chmod 700 "$BRIDGE_CERT_DIR"

openssl x509 -in "$BRIDGE_CERT_DIR/cert.pem" -noout -sha256 -fingerprint \
  -dates -subject -ext subjectAltName
```

If the printed SAN does not include the `MAIL_URL` hostname, stop and reissue.
Record the SHA-256 fingerprint privately.

### 5.2 Import with the selected CLI, then prove the resident uses it

Stop the resident Bridge first. Inspect the selected image for the CLI binary
before using a path from this text. The tested `3.19.0-1` package provided
`/usr/bin/protonmail-bridge`. The published GitHub entrypoint still refers to
`/protonmail/proton-bridge`. If the binary is missing, do not substitute a guess.

```bash
# Prerequisite: inspect, do not assume the path.
docker image inspect --format '{{json .Config.Entrypoint}} {{json .Config.Cmd}} {{json .RepoDigests}}' "$BRIDGE_IMAGE"
# Then list candidate binaries from a throwaway, non-network, stopped-style run
# only if needed, for example:
# docker run --rm --network none --entrypoint sh "$BRIDGE_IMAGE" -c 'command -v protonmail-bridge; command -v /usr/bin/protonmail-bridge; command -v /protonmail/proton-bridge; ls /usr/lib/protonmail/bridge 2>/dev/null || true'
```

When the inspected CLI path is confirmed, run it against the same `/root` volume
and user as the resident service, with a PTY, without recording secret input.
Use the image's `cert import` flow and, when prompted, supply the
resident-visible paths such as `/root/certs/cert.pem` and `/root/certs/key.pem`.
On the tested package the CLI reported that the TLS certificate was imported and
that Bridge must be restarted. If the selected image uses different subcommands
or prompts, stop and follow that image's help.

Start the resident service on the same volume, with no extra transient certificate
mounts required for the imported paths. Inspect sanitized logs from the new
session only. **Fail the setup** if those logs contain
`Failed to read certificate from file, using default`.

Stop the resident if a same-volume export requires a quiet store, then run
`cert export` into a fresh directory on that volume. Compare:

```bash
openssl x509 -in "$INTENDED_CERT" -noout -sha256 -fingerprint -dates -ext subjectAltName
openssl x509 -in "$EXPORTED_CERT" -noout -sha256 -fingerprint -dates -ext subjectAltName
```

Require identical fingerprints, current validity, and the exact DNS SAN the
client will use. A later export without a resident restart and a clean log check
is not sufficient.

### 5.3 Mount client trust and keep verification on

The locked Symfony SMTP factory at the reviewed revision has no `cafile` DSN
option. For the official PHP image family used by the proxy, supply the CA with
PHP's OpenSSL configuration and recreate the proxy so the worker reloads it.

Create `./trust/ca.crt` (the CA certificate only) and
`./trust/openssl-ca.ini` of mode `644` on the host. The ini contains one
directive, using the in-container path:

```ini
openssl.cafile=/etc/ssl/newsletter-bridge-ca.crt
```

Merge these read-only mounts into the proxy service without replacing the data
volume:

```yaml
services:
  newsletter-proxy:
    volumes:
      - proxy-data:/data
      - ./trust/ca.crt:/etc/ssl/newsletter-bridge-ca.crt:ro
      - ./trust/openssl-ca.ini:/usr/local/etc/php/conf.d/zz-newsletter-bridge-ca.ini:ro
```

Do not set `verify_peer=false`, `MAIL_VERIFY_PEER`, or
`rejectUnauthorized=false`. After recreate, use the
[transport probe](operations.md#concrete-checks-for-the-inspected-source) to
confirm `require_tls` and peer verification remain enabled, then prove trust
with the actual client.

If transactional Ghost mail through Bridge is independently in scope, mount the
same CA into Ghost and set `NODE_EXTRA_CA_CERTS` to that in-container path, then
recreate Ghost so Node loads it at process start. Recheck `rejectUnauthorized`.

When STARTTLS is actually offered, an untrusted CA and a wrong hostname must
each fail, followed by one authorized send on the intended trusted transport.
If STARTTLS is not offered, record those handshake tests as blocked. Offline
fingerprint equality is not SMTP handoff and not inbox receipt.

If the certificate does not match any reachable name, or the client cannot trust
it through supported configuration, stop the Bridge route and report the
incompatibility. A successful unverified connection is not acceptance. Do not
silently switch an explicitly requested Bridge route.

## 6. Start proxy

1. On a clean isolated project, complete the private key bootstrap above. Inspect
   the selected image before using one-off flags; do not assume a user ID or a
   Docker `ENTRYPOINT` for every tag:

   ```bash
   docker image inspect --format '{{json .Config.User}} {{json .Config.Entrypoint}} {{json .Config.Cmd}}' "$PROXY_IMAGE"
   ```

   At source revision `fb35a74000fe70e7d49f46cae3c895674571ea20` and the current
   published `Dockerfile`/`Procfile` (re-read 2026-11-19), `Config.User` is `82`,
   `Config.Entrypoint` is empty, and `Config.Cmd` is
   `hivemind /etc/Procfile`. `/entrypoint.sh` is the **php-fpm Procfile process**,
   not a Docker entrypoint: it may create the SQLite file, run migrations, and
   then `exec php-fpm`. `queue:work` starts in parallel with that script, so a
   first `up -d` can race the worker against an unready database. A named volume
   mounted at `/data` also hides the image's pre-chowned `/data` directory.

   `--entrypoint php` therefore replaces an empty Docker entrypoint and runs
   Artisan without `/entrypoint.sh`. That is useful for a one-off migrate after
   the database file is already writable, but it does **not** create the SQLite
   file or fix volume ownership. A Compose `command` override leaves a real
   image entrypoint active *if the selected image defines one*; confirm that
   from inspect rather than from this paragraph. A separate running worker must
   also be stopped before touching an existing queue.
   For an isolated rollback rehearsal that needs HTTP without consumers, inspect
   the image supervisor configuration and stage a private copy with the queue
   entry omitted. Verify the process list before submitting any synthetic jobs.
2. On a **new** SQLite volume, prepare the configured database path as the
   inspected runtime user before any `--entrypoint php` migrate. Preserve
   existing databases. The following is a worked example after inspect has
   confirmed `Config.User` and `DB_DATABASE` (defaults shown are from the
   reviewed Dockerfile; if User is empty or the paths differ, stop and adapt):

   ```bash
   image_user=$(docker image inspect --format '{{.Config.User}}' "$PROXY_IMAGE")
   case "$image_user" in
     '') echo 'Image user is empty; do not guess. Stop.' >&2; exit 1 ;;
     *:*) chown_spec=$image_user ;;
     *) chown_spec=$image_user:$image_user ;;
   esac
   docker compose run --rm --no-deps --user 0 -e CHOWN_SPEC="$chown_spec" \
     --entrypoint sh newsletter-proxy -c 'set -eu
   db="${DB_DATABASE:-/data/database.sqlite}"
   mkdir -p "$(dirname "$db")" /data/sessions /data/uploads
   if [ ! -f "$db" ]; then
     touch "$db"
   fi
   chown -R "$CHOWN_SPEC" /data
   chmod 775 /data
   chmod 664 "$db"'
   ```

   Pass the inspected user as `CHOWN_SPEC`. If Compose or the volume path
   differs, adjust only after confirming the mount. Then, with the default
   image user and the service stopped, run:

   ```bash
   docker compose run --rm --no-deps --entrypoint php newsletter-proxy artisan migrate --force
   docker compose run --rm --no-deps --entrypoint php newsletter-proxy artisan migrate:status
   ```

   Require every target migration to be `Ran`. If file creation, ownership, or
   migrate fails, leave the service stopped and report it; do not start the
   bundled worker against an unready volume.
3. Start `docker compose up -d newsletter-proxy`. Require HTTPS `/up` = 200,
   all migrations still applied, and a stable `queue:work` process across repeated
   samples with no restart loop.
4. Complete the private registration and API authentication checks below. Then
   submit one authorized proxy test and correlate the unique subject, queue
   records, SMTP event and capture. Check real Proton receipt separately and
   run the native Ghost preview gate before enabling a live newsletter path.
   [Runtime and queue checks](operations.md#concrete-checks-for-the-inspected-source)

## 7. Origin, DNS and initial admin

Provision a dedicated DNS name with valid HTTPS. Example for an existing Caddy
installation on the same Docker network:

```caddyfile
mg.example.com {
    reverse_proxy newsletter-proxy:8080
}
```

Keep existing DNS-01 settings if required; do not assume custom snippet imports
or Cloudflare modules exist. Validate Caddy configuration before reload. Preserve
forwarded scheme/client headers. Scope DNS changes to the new host and record
previous values for rollback; leave the domain's mail records unchanged.

Before general access, restrict admin routes to the operator, create the first
admin through upstream's initial registration, then apply the registration
checks in operations before removing the access restriction.
Supply name, email, password and matching `password_confirmation` privately.
Use a generated password of at least 16 characters with uppercase and lowercase
letters, digits and symbols. Inspect the target's production `Password::defaults`
and registration action for minimum length and compromised-password checks.
Confirm that repeat registration is blocked and the initial user can log in.
For both message POST and event GET require 401
with missing credentials, incorrect password and incorrect username before
testing the valid credentials. Keep fixture traffic confined to the private sink.
Use /up for unauthenticated liveness. Do not use broad raw User::create examples.
If restricting routes to /v3, also allow required health/admin routes privately
and provider webhooks when that backend is enabled.

Verify HTTPS /up, authenticated proxy API access from Ghost, queue processing,
and receipt of one authorized proxy test before changing Ghost.

## Build an unpublished fixed proxy

Use this path only when you need the documented Message-Id fix and no published
image yet contains commit `e31299823886f4db9d026054632907924eb02d49` from
[YE4IM/mailgun-proxy-for-ghost](https://github.com/YE4IM/mailgun-proxy-for-ghost)
([PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1), merged into fork `main` on 2026-11-20 09:43 Asia/Shanghai;
merge `391256f764979101c4c23b4a410a7de4d3183115`). Do not patch a running container. Do not treat a local image ID
as a registry manifest digest. Do not push the image unless the operator has
explicitly chosen to publish it.

Prefer the verified pin `e31299823886f4db9d026054632907924eb02d49`. The
merge commit shares the same Git tree
`779b7f9a59d9474942bb78739901695396f9b81a`, but the isolated preview and capture
were run against a local build of the fix commit, not a rebuild of
`391256f764979101c4c23b4a410a7de4d3183115`. The recorded official GitHub
archive SHA-256 applies only to the fix-commit tarball. If you build from the
merge commit instead, record a new archive hash; do not reuse the e312998
hash, and do not treat tree equality as a new runtime result.

1. Download the official commit archive, not an unpinned branch tip:

   ```bash
   curl --fail --location --output proxy-src.tar.gz \
     https://github.com/YE4IM/mailgun-proxy-for-ghost/archive/e31299823886f4db9d026054632907924eb02d49.tar.gz
   ```

2. Verify the archive SHA-256 against the recorded value in the
   [support matrix](upstream.md#support-matrix)
   (`96b2654d7cc0254dcdcd7efc55c1f1cf7e2fffe6a49095db3ecc7fe22bf2c9fc` for this
   commit on 2026-11-19). Confirm the top directory name contains the commit
   prefix. If the hash or layout differs, stop.

3. Confirm the lockfile versions (Laravel 13.9.0, Symfony Mailer and Mime
   8.0.8) and inspect `app/Mail/GhostNewsletter.php` for dedicated
   identification-header handling of `h:Message-Id`.

4. Build locally with BuildKit / `docker buildx build --load`. The Dockerfile
   uses cache mounts; a classic `docker build` may fail if the buildx
   component is missing. Tag the result with a local name that includes the
   commit, for example `mailgun-proxy-for-ghost:ghost-message-id-e312998`.

5. Record `docker image inspect --format '{{.Id}}'` as a **local image ID**.
   After `--load`, a RepoDigest-like value may appear; that is still not a
   published registry manifest digest. Set `PROXY_IMAGE` to the local tag or
   local ID for isolated Compose, and label the record "local build of
   e31299823886f4db9d026054632907924eb02d49".

6. Inspect `User`, `Entrypoint`, `Cmd`, and the installed PHP version in the
   built image before first start. The 2026-11-19 linux/amd64 build reported
   PHP 8.5.13 and User 82. One-off migrate commands still use
   `--entrypoint php`. Follow the SQLite first-start sequence in this file.

7. Accept the image only on new isolated volumes. A synthetic POST is not
   enough. Require a Ghost native preview (or the exact Ghost payload),
   helper handoff, and one internal STARTTLS capture of that unique test,
   correlated by subject or trace headers. Do not send to real addresses
   until those layers pass and a separately authorized receipt test is in
   scope. Live Bridge STARTTLS and negative TLS checks remain unproven for
   this commit unless you run them.

If you later pull a published image that claims this fix, ignore the earlier
local ID and pin the new registry digest, then re-run the acceptance layers.

## 8. Configure and cut over Ghost

Test the selected Ghost image and proxy image together in isolation before
changing production. Ghost 6.78.0 sends `h:Message-Id` in a native preview.
The published proxy digest in the [support matrix](upstream.md#support-matrix)
failed to build that MIME header. A source-verified local build of
`e31299823886f4db9d026054632907924eb02d49` passed isolated native preview and
local STARTTLS capture with that Ghost image on 2026-11-19. That pass does not
include real Proton receipt or live Bridge TLS. PR #1 is now merged into the
fork main, but the image was not published; the merge was not separately deployed.

A successful simple proxy POST and a native preview HTTP `204` can both
precede a failed handoff on an unfixed image, and they still do not prove
inbox receipt on a fixed image. Hold production cutover until the image you
will actually run passes native preview, isolated capture, and receipt
checks, plus Route B live TLS when Bridge is in scope.

Create a private `ghost-newsletter.env` beside the existing Ghost Compose file:

```dotenv
bulkEmail__mailgun__baseUrl=https://mg.example.com/
bulkEmail__mailgun__apiKey=<same-shared-secret>
bulkEmail__mailgun__domain=example.com
```

Append only `ghost-newsletter.env` to the existing Ghost service's `env_file` list;
preserve existing entries and all transactional `mail` settings. Remove conflicting
**bulkEmail** keys from `environment` (which overrides env_file), and reconcile
JSON/Admin UI bulk configuration. A project `.env` only supplies interpolation by
default and does not inject arbitrary variables. Run `docker compose config --quiet`
in the Ghost stack, then recreate only Ghost using its inspected service name.
Verify effective bulk configuration and a native Ghost test per operations.

Use one complete source for all three `bulkEmail.mailgun` fields. For the env
example, save a private rollback copy, inventory Ghost JSON, Compose overrides
and persisted newsletter Mailgun settings in Admin, and clear conflicting values.
Test precedence on an isolated Ghost database with HTTPS origins A and B, each
restricted to a private capture sink. Configure the full env triple for A and
record a baseline native draft preview. Set the supported Admin fields to
distinct B values, keeping both sets of credentials local. Verify the loaded
config with a redacted exact-match probe. Send one new tagged preview and check
the origin, domain path and credential match at the receiving endpoint. Then
recreate the isolated Ghost with the env block removed and repeat against the
complete Admin configuration. The Admin API may return a masked key. Compare
the request's auth at B privately, using the result only as routing evidence if
the backend rejects it. If the UI cannot set a custom origin, check domain and
key at the controlled endpoint and prevent requests to public endpoints.
Restore the intended single source and repeat with a fresh marker. Record the
actual origin, domain and key match for each case.

For each native preview record the draft, unique subject marker, authorized test
recipient and time window privately. Capture the Admin API status, correlated
proxy request and event, queue baseline and final pending/reserved/failed counts,
and exactly one matching captured message. Require handoff, job clearance and no
unexplained failure or backlog growth. Reconcile ambiguous requests before
sending again. Verify inbox receipt independently with the authorized recipient.

## 9. Transactional SMTP, only when independently in scope

Do not add this file for a newsletter-only deployment, repair or upgrade. If the
user requests transactional setup or the fault concerns it, use a separate private
`ghost-transactional.env`. Common settings:

```dotenv
mail__transport=SMTP
mail__options__secure=false
mail__options__requireTLS=true
mail__from=mail@example.com
```

Append exactly one route block:

```dotenv
# Direct SMTP
mail__options__host=smtp.protonmail.ch
mail__options__port=587
mail__options__auth__user='<SMTP token address>'
mail__options__auth__pass='<SMTP token password>'
```

```dotenv
# Bridge
mail__options__host=protonmail-bridge
mail__options__port=25
mail__options__auth__user='<Bridge SMTP username>'
mail__options__auth__pass='<Bridge SMTP password>'
```

For Bridge, configure trust and a matching hostname in step 5. Keep certificate
verification enabled on both routes. Confirm the actual Ghost/Nodemailer version
honors requireTLS. Append this file separately to Ghost's env_file, reconcile only
conflicting transactional keys, validate Compose quietly and recreate only Ghost.
Verify the actual loaded transport and receipt of a real authorized login email.
