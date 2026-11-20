# Source versus image address policy

Do not treat a source-repository fork as an image publisher. Use the YE4IM
source only for a project that is actually being maintained there with a
fix. The unmodified Bridge project stays at its original upstream. Historical
upstream links, licenses, official vendor manuals, and actually published
registry paths stay with their real origin. Never invent a YE4IM registry tag
or digest.

## Proxy

| Role | Recorded value |
|---|---|
| Default source and maintenance entry | [YE4IM/mailgun-proxy-for-ghost](https://github.com/YE4IM/mailgun-proxy-for-ghost), default branch `main` |
| Original upstream and license | [eznix86/mailgun-proxy-for-ghost](https://github.com/eznix86/mailgun-proxy-for-ghost), AGPL-3.0 |
| Merged pull request | [PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1), merged into fork `main` on 2026-11-20 09:43 Asia/Shanghai |
| Merge commit (fork `main` tip at that merge) | `391256f764979101c4c23b4a410a7de4d3183115` (parents `fb35a74000fe70e7d49f46cae3c895674571ea20` and `e31299823886f4db9d026054632907924eb02d49`) |
| Verified fix commit | `e31299823886f4db9d026054632907924eb02d49`. The 2026-11-19 isolated linux/amd64 Ghost 6.78.0 native preview and internal STARTTLS capture used a local build of this commit only |
| Shared Git tree | `779b7f9a59d9474942bb78739901695396f9b81a`. Tree equality is source equivalence. The merge commit was not separately rebuilt or retested |
| Preferred build pin | The verified fix commit, because that is the tested revision and the only archive with a recorded official GitHub tarball SHA-256 (`96b2654d7cc0254dcdcd7efc55c1f1cf7e2fffe6a49095db3ecc7fe22bf2c9fc`, 2026-11-19). If building from the merge commit, record a new archive hash; do not reuse the fix-commit hash |
| YE4IM published image | None as of the 2026-11-20 check: no GitHub Releases and no tags. The inherited Release workflow would publish to `ghcr.io/${{ github.repository }}` only on a `v*` tag. Do not invent or pull `ghcr.io/ye4im/mailgun-proxy-for-ghost` |
| Known failing published image (retain as failure evidence) | `ghcr.io/eznix86/mailgun-proxy-for-ghost@sha256:d3fbcd4f209ec27dbce81f8ff013ae8d09b833bbe5ac72715706b39fc575e33c`. Do not use this as the default deploy image |
| Unfixed upstream `main` | Still `fb35a74000fe70e7d49f46cae3c895674571ea20` as of 2026-11-19, confirmed again on 2026-11-20. Historical evidence links stay pinned to that revision on the upstream origin |

Default `PROXY_IMAGE` in this skill is the local tag
`mailgun-proxy-for-ghost:ghost-message-id-e312998` after a source-verified
local build. It is not a pullable registry image. If a later published digest
actually contains the fix, pin that new digest and re-run acceptance.

## Bridge

This project has no Message-Id fix and no local maintenance PR in this skill.
The default source and maintenance entry is the original upstream, not a
YE4IM fork. v5 briefly used a YE4IM Bridge source entry; that is historical
only and is not the current default.

| Role | Recorded value |
|---|---|
| Default source and maintenance entry | [shenxn/protonmail-bridge-docker](https://github.com/shenxn/protonmail-bridge-docker), default branch `master`, GPL-3.0 |
| Published image used for pulls | `shenxn/protonmail-bridge`, third-party publisher, unofficial Proton container. This is not a Proton official image. Do not invent a YE4IM Bridge registry path |
| Recorded digest and verification scope | `shenxn/protonmail-bridge@sha256:3717b4441130675dc9131196de9f9c5287d2ea21b138d83b0486429e1737638a` (package `3.19.0-1`, OCI revision `540ba69528378b4fd7d557807d69ee9a03a64dcf`). Recorded checks cover offline certificate SAN and persistence. Live Bridge STARTTLS, untrusted-certificate rejection, wrong-hostname rejection, and Proton inbox receipt remain unproven |
| Historical source-review links | Keep the previously reviewed [shenxn README](https://github.com/shenxn/protonmail-bridge-docker#readme) and entrypoint links as the documents actually inspected |

## Keep unchanged

- Official Ghost and Proton manuals, and locked Laravel or Symfony framework pins.
- Historical evidence links at `eznix86/mailgun-proxy-for-ghost` revision
  `fb35a74000fe70e7d49f46cae3c895674571ea20`.
- Example hosts such as `mg.example.com`. Do not substitute private inventory.
- The local image ID
  `sha256:4188afefc32d858a55e5787a5549b5f0665bd236aed7bc9640882f5906b15b96`,
  labeled only as a local `docker image inspect` ID, never as a registry
  manifest digest.

A merged pull request, a shared Git tree, or a passing isolated capture does
not make production newsletter delivery ready.
