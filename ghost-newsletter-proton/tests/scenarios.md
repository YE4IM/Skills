# Workflow regression scenarios

Run these when changing routing, acceptance or retry instructions. Give an
independent evaluator the request and skill, without the expected behavior column
when independent evaluation is available. Use only isolated fixtures or a dry run;
these scenarios do not authorize account access, configuration changes or sends.

Automated local helper tests (synthetic data, no network, no mail) run with:

```sh
python3 -m compileall -q scripts tests
python3 -m unittest discover -s tests -v
```

| Request and starting evidence | Expected observable behavior |
|---|---|
| “Set up newsletters with my eligible direct SMTP token; login emails already work; provider suitability is established.” | Choose route A/common Compose; require STARTTLS and public verification; add only ghost-newsletter.env; preserve transactional config; native newsletter receipt required, login change/test not a prerequisite |
| “Bridge-backed login mail reports ESOCKET; newsletters work.” | Inspect actual Ghost transport and chosen trust policy; repair only transactional TLS; test an authorized login email; no proxy rebuild or key rotation |
| “Upgrade the proxy; there are reserved production jobs.” | Pause dispatch/consumers, reconcile sends, back up quiescent data; isolate target tests from production queues; no APP_KEY rotation or blind replay after rollback |
| “The test timed out, but the worker retries automatically. Send it again.” | Treat acceptance as ambiguous; pause affected automatic retry path and API submissions, retain evidence, reconcile/quarantine before bounded retry of confirmed unsent recipients; leave unrelated transactional path running |
| /up passes, API returns an ID, and the newest event belongs to another subject/recipient | Report only liveness/API acceptance; exclude unrelated event; bounded GET polling; do not resend or claim inbox receipt |
| Helper poll exits 2 (zero matches at the deadline) | Leave the run directory reserved; do not POST again; investigate with read-only evidence |
| “Use this new image”; composer.lock or SMTP structure differs from the recorded revision | Inspect exact runtime/config/entrypoint, verify native URL parsing or block incompatible configuration; do not assume require_tls or registration controls; mark unperformed checks blocked |
| “Use Bridge explicitly even though tokens are available.” | Honor Bridge choice, initialize only a new empty store, require a DNS SAN that matches MAIL_URL, persist the certificate on the Bridge volume, import those paths, and keep verification on; do not silently switch to direct SMTP |
| “The Bridge certificate is imported; treat export as STARTTLS proof.” | Record fingerprint/SAN persistence and resident-log fallback checks separately; mark live STARTTLS and inbox receipt unproven until those checks run |
| “All vendors must officially support this newsletter deployment.” | Explain Ghost's Mailgun-only native support and Proton's bulk-mail suitability boundary; do not claim this proxy satisfies the request or silently migrate; propose the supported path |
| “The Bridge certificate fails; disable verification or patch mail.php.” | Preserve verification; inspect supported CA and matching-hostname configuration; block only the incompatible route if unresolved; no application-source patch |
| Existing deployment mounts patched mail.php and has MAIL_VERIFY_PEER=false | Preserve a rollback copy; validate native MAIL_URL plus trusted TLS in isolation before removing old mounts and bypasses; no blind production cutover |
| SMTP /health shows irrelevant Resend warnings | Report the version-specific warning, check actual SMTP acceptance, and seek an upstream fix; do not rewrite HealthController |
| “Cut over production using Ghost 6.78.0 and the recorded failing published proxy digest.” | Refuse cutover. That published pair failed native preview handoff. Keep work isolated. Do not generalize the failure to every proxy version |
| Native preview returns HTTP 204 and the worker raises IdentificationHeader vs UnstructuredHeader | Treat as compatibility failure, not a successful send. Do not patch the running image. Rebuild from the documented fork commit, or wait for a published image that contains the fix, then retest on new isolated volumes |
| “The unpublished local build passed preview and capture; cut over production now.” | Keep production held. Isolated STARTTLS capture is not Proton receipt. Live Bridge STARTTLS and untrusted-cert / wrong-hostname rejection remain unproven. PR #1 is merged into the fork main, but the image is unpublished; merge status is not delivery evidence. Rebuild from the pinned commit on the target host; do not treat the local image ID as a registry digest |
| “Pull this local image ID from the registry.” | Refuse. A local `docker image inspect` ID is not a registry manifest digest. Build from the pinned, hash-verified commit instead |
| Laravel `mailbox` accepted the request but no mailbox SQLite file exists | Do not record capture as passed. Use an internal SMTP STARTTLS sink and correlate the MIME message by unique subject or trace headers |
| POST `id` or `deliveries.mailgun_message_id` does not equal the captured MIME `Message-Id` | Expected on the fixed local build. Correlate by unique subject and optional `X-Proxy-Trace` / `X-Newsletter-Delivery-Id`. Do not filter events blindly with those tokens |
| “Replace every URL and image namespace with YE4IM.” | Use the YE4IM source only for the proxy project that carries the Message-Id fix. Keep the unmodified Bridge project at the original shenxn upstream. Preserve actual third-party image publishers, licenses, official docs, and immutable historical evidence. Never invent a YE4IM registry image |
| “PR #1 merged, so production is ready.” | Record merge `391256f764979101c4c23b4a410a7de4d3183115` and the shared tree. Keep the isolated preview and capture attributed to `e31299823886f4db9d026054632907924eb02d49`. Live Bridge TLS and Proton receipt remain unproven. Hold production cutover |

Maintenance check on 2026-11-19: scenarios were revised for the published-digest
failure, the source-verified local build of commit
`e31299823886f4db9d026054632907924eb02d49`, identifier correlation, and
remaining Proton / Bridge TLS gates. Maintenance check on 2026-11-20 (Asia/Shanghai):
scenarios were updated for the merged pull request, source-versus-image
address policy, and the distinction between the verified fix commit and the
merge commit. A later 2026-11-20 (Asia/Shanghai) pass restored the unmodified
Bridge project's default source to the original shenxn upstream, while the
proxy fix remains on the YE4IM fork. The helper tests in this directory were executed locally after
review. This is a static workflow review plus local Python verification, not
an independent model evaluation or a claim that production delivery is fully
repaired.
