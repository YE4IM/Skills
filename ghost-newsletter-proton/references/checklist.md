# Verification, rollback, and packaging checklist

Use this list with [operations](operations.md) and the
[support matrix](upstream.md#support-matrix). Record each item as pass, fail,
blocked, or not applicable. Do not convert a blocked SMTP or inbox check into
a pass.

## Before mutation

- [ ] Use the YE4IM source and maintenance entry only for the proxy project that carries the Message-Id fix. Use the original [shenxn/protonmail-bridge-docker](https://github.com/shenxn/protonmail-bridge-docker) project as the default Bridge source. Do not invent a YE4IM image. Follow [source versus image address policy](address-policy.md); preserve upstream evidence and actual image publishers.
- [ ] Record [PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1) as merged into the fork `main` on 2026-11-20 09:43 Asia/Shanghai (`391256f764979101c4c23b4a410a7de4d3183115`). The merge is not a published or production-verified image.
- [ ] Inventory Ghost version, Compose services, networks, image digests, and the working mail path without printing secrets.
- [ ] Confirm SMTP-token or Bridge entitlements and sender DNS against current provider documentation.
- [ ] Pin published images by digest, never `latest`. For an unpublished fix, build from the pinned commit after verifying the archive hash; record the local image ID as a local ID, not as a registry manifest digest.
- [ ] Record architecture and any OCI revision label, or that it is missing. After a local `--load`, do not treat a RepoDigest-like value as a published digest.
- [ ] Back up configuration and persistent data. Record a rollback target and location privately.
- [ ] If the selected pair is Ghost 6.78.0 plus the recorded failing published proxy digest, keep the work isolated and do not plan production cutover on that pair.
- [ ] If using a local build of the verified fix commit, still hold production cutover until native preview, isolated SMTP capture, and real receipt (and Route B live TLS) pass on the image that will be deployed.

## Bridge certificate (Route B only)

- [ ] Leaf certificate DNS SAN includes the exact hostname used in `MAIL_URL`.
- [ ] Certificate and key live on the persistent `/root` volume at a stable path the resident process can read.
- [ ] Selected-image CLI path was inspected, not guessed.
- [ ] `cert import` used those resident-visible paths.
- [ ] After resident restart, new-session logs do **not** contain `Failed to read certificate from file, using default`.
- [ ] Post-restart export fingerprint and SAN match the intended certificate.
- [ ] Proxy (and Ghost, if in scope) mounts the CA and keeps peer and hostname verification enabled.
- [ ] Live STARTTLS, untrusted-CA rejection, wrong-hostname rejection, and inbox receipt are recorded separately. Offline export equality is not a pass for those items. If STARTTLS is not offered, mark handshake tests blocked.

## Proxy first start (SQLite)

- [ ] Image `User`, `Entrypoint`, and `Cmd` were inspected for the selected digest.
- [ ] On a new volume, the database file and `/data` ownership were prepared for the inspected user before `--entrypoint php` migrate.
- [ ] `artisan migrate --force` and `migrate:status` show every target migration `Ran` while the bundled worker is stopped.
- [ ] After `up -d`, `/up` returns 200 and `queue:work` is stable across repeated samples.

## Acceptance layers

- [ ] HTTP enqueue: helper `queued` exit 0 (HTTP 200 and a nonempty `id`). The `id` need not be the literal string `message-id`.
- [ ] Queue handoff: helper `poll` exit 0, and the specific job has left pending or reserved work. Correlate by unique subject and optional trace or delivery headers; do not assume the POST `id` or `deliveries.mailgun_message_id` equals the MIME `Message-Id`.
- [ ] Zero matches (exit 2) or unknown job state: no second POST from the same run directory.
- [ ] Ghost native preview (or the exact Ghost payload) processed without worker error, including `h:Message-Id` when present.
- [ ] Isolated SMTP capture of the unique test, recorded separately from inbox receipt. Prefer internal STARTTLS with verification enabled. Do not treat a Laravel `mailbox` `accepted` event with no mailbox store as capture proof.
- [ ] Authorized inbox receipt, only when a real provider route is in scope and allowed. Isolated capture is not Proton receipt.
- [ ] Transactional login mail tested only when that path is in scope.

## Rollback

- [ ] Services that would write to the restore target are stopped first.
- [ ] Restore configuration and volumes from the recorded backup, including the same `APP_KEY` when the proxy database is restored.
- [ ] Quarantine already handed-off or unknown jobs before starting a worker. Do not replay them.
- [ ] Only confirmed-unsent work may be retried, in a fresh acceptance directory, with a new unique ID if a new POST is authorized.
- [ ] Re-run the acceptance layers that the change could have affected. Leave unrelated mail paths untouched.

## Offline helper tests and packaging

From the unpacked skill directory:

```sh
python3 -m compileall -q scripts tests
python3 -m unittest discover -s tests -v
```

These tests use synthetic data, mock transport, and must not use the network or
send mail. They do not replace deployment acceptance.

To build a release archive outside this directory, with no symbolic links,
caches, keys, credentials, backups, or runtime evidence:

```sh
COPYFILE_DISABLE=1 zip -rX ../ghost-newsletter-proton.zip SKILL.md CHANGELOG-zh.md references scripts tests \
  -x '*/__pycache__/*' '*.pyc' '.DS_Store' '*/.DS_Store'
```

Record the SHA-256 of the archive and the complete file list after packing.
