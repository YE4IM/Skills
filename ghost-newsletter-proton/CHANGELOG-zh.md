# ghost-newsletter-proton v6 改动说明

日期：2026-11-20（Asia/Shanghai）

本包从 v5 调整而来，只改地址策略中的默认源码入口：有 PR 修复维护的代理项目继续指向用户 Fork；没有本地维护变动的 Bridge 项目恢复为原上游地址。这是可下载的通用 Skill 包候选，不是对已安装技能库的更新，也不是镜像发布，更不是生产路径已经修通的声明。原 v5 包未被覆盖。v5 正文作为历史保留。

## 本版修改

- 代理项目默认源码与维护入口保持 [YE4IM/mailgun-proxy-for-ghost](https://github.com/YE4IM/mailgun-proxy-for-ghost)（默认分支 `main`）。[PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1) 仍记录为已于 2026-11-20 09:43（Asia/Shanghai）合并进 `main`，合并提交 `391256f764979101c4c23b4a410a7de4d3183115`。
- 未修改的 Bridge 项目默认源码与维护入口恢复为 [shenxn/protonmail-bridge-docker](https://github.com/shenxn/protonmail-bridge-docker)（默认分支 `master`，GPL-3.0）。现势文档不再把 YE4IM Bridge Fork 当作默认入口。v5 曾改用该 Fork 的表述仅保留在本 changelog 的历史节。
- 构建、镜像与验收边界不变：优先从已验证修复提交 `e31299823886f4db9d026054632907924eb02d49` 做本地构建；默认 `PROXY_IMAGE` 仍是本地标签 `mailgun-proxy-for-ghost:ghost-message-id-e312998`；不把已知故障上游 digest 当作默认拉取值，也不杜撰 YE4IM 镜像。Bridge 拉取镜像仍为第三方发布者 `shenxn/protonmail-bridge`，已记录 digest 的验证范围仍是离线证书检查，不是实时 TLS 或 Proton 收件。
- 合并提交与修复提交共享 Git 树的说明、隔离验收归属、以及“不能宣称生产 newsletter 路径已经修通”的门禁均保持不变。
- 同步 SKILL、地址策略、部署、上游、清单、场景与离线回归测试。本地 Python 测试为 48 项（38 项助手回归，10 项合并状态与地址策略回归），全部通过，只覆盖包内文档与合成数据，不联网、不发信。本包未重新连接服务器、未发信、未发布镜像、未提交上游 issue。

## 未解决 / 未测

- 修复镜像尚未发布到 registry。不能把本地镜像 ID 当作可拉取的 digest，也不能把合并后的 `main` 当作已发布镜像。
- 真实 Proton Bridge STARTTLS、不受信任证书应失败、错误主机名应失败，以及 Proton 收件箱收到测试邮件，**仍未验证**。隔离捕获通过不能代替真实收件。合并本身也不改变这些门槛。
- 因此**不能宣称生产 newsletter 路径已经修通**。生产切换前，必须在实际要部署的镜像上再次通过原生 preview、隔离捕获，以及（若走 Proton）真实收件和 Route B 的实时 TLS 正反验收。
- 上游 `main` 与 `fb35a74000fe70e7d49f46cae3c895674571ea20` 仍包含旧的文本头实现；已发布失败 digest 仍然失败。
- 本地 unittest 不能替代部署验收。
- 路径游标仍不接受含 `/` 的 Base64；若未来分页格式改变，需要重测。
- 官方全厂商支持与 Proton 群发适用性边界依旧存在。

# ghost-newsletter-proton v5 改动说明（历史）

日期：2026-11-20（Asia/Shanghai）

本包从 v4 更新而来，只同步合并状态与源码/镜像地址策略。这是可下载的通用 Skill 包候选，不是对已安装技能库的更新，也不是镜像发布，更不是生产路径已经修通的声明。原 v4 包未被覆盖。

## 本版修改

- 更新合并状态：[PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1) 已于 2026-11-20 09:43（Asia/Shanghai）合并进用户 Fork 的 `main`，合并提交为 `391256f764979101c4c23b4a410a7de4d3183115`。v4 中“尚未合并”的表述仅作为历史保留。
- 明确验收归属：2026-11-19 隔离环境中的 Ghost 6.78.0 原生 preview 与内部 STARTTLS 捕获，针对的是修复提交 `e31299823886f4db9d026054632907924eb02d49` 的本地构建。合并提交与该修复提交共享 Git 树 `779b7f9a59d9474942bb78739901695396f9b81a`，这只说明源码树相同，不是对 `391256f` 的重新构建或重新验收，也不是真实 Proton 收信或 Bridge 实时 TLS 证据。
- 默认源码与维护入口改为用户 Fork：[YE4IM/mailgun-proxy-for-ghost](https://github.com/YE4IM/mailgun-proxy-for-ghost)（默认分支 `main`）和 [YE4IM/protonmail-bridge-docker](https://github.com/YE4IM/protonmail-bridge-docker)（默认分支 `master`）。构建示例继续使用已记录归档哈希的修复提交 tarball，而不改用未记录哈希的合并提交归档。
- 区分源码 Fork 与镜像发布者。2026-11-20 核查时，两个 YE4IM Fork 均无 GitHub Releases、无 tags。代理仓库继承的 Release 工作流只会在推送 `v*` 标签时发布到 `ghcr.io/${{ github.repository }}`，因此不把 `ghcr.io/ye4im/mailgun-proxy-for-ghost` 写成可拉取镜像。Bridge Fork 当时也没有 Actions workflows，不杜撰 YE4IM Bridge 镜像。
- 部署默认 `PROXY_IMAGE` 改为已验证修复提交的本地标签 `mailgun-proxy-for-ghost:ghost-message-id-e312998`，不再把已知故障上游镜像 `ghcr.io/eznix86/mailgun-proxy-for-ghost@sha256:d3fbcd4f209ec27dbce81f8ff013ae8d09b833bbe5ac72715706b39fc575e33c` 当作默认拉取值。该 digest 仍作为已知失败行保留。
- Bridge 拉取镜像仍为第三方发布者 `shenxn/protonmail-bridge`，并标注供应来源与验证范围：已记录 digest 的离线证书检查有效，实时 STARTTLS、负面 TLS 和 Proton 收件仍未验证。2026-11-20 核查时，YE4IM Bridge Fork 停在 `5874fde`（v3.27.1），上游 `master` 已到 `ae5d201`（v3.27.2）；源码构建前须核对其新鲜度。
- 保留真实上游出处、许可证、官方文档、锁定框架出处，以及钉在 `eznix86` 修订 `fb35a74000fe70e7d49f46cae3c895674571ea20` 上的历史证据链接。2026-11-20 再次确认上游 `main` 仍是该提交。
- 新增 [源码与镜像地址策略](references/address-policy.md)，并补齐合并状态与地址策略的离线回归测试。本地 Python 测试现为 47 项（保留原 38 项助手回归，新增 9 项策略回归），全部通过，只覆盖包内文档与合成数据，不联网、不发信。本包未重新连接服务器、未发信、未发布镜像。

## 未解决 / 未测

- 修复镜像尚未发布到 registry。不能把本地镜像 ID 当作可拉取的 digest，也不能把合并后的 `main` 当作已发布镜像。
- 真实 Proton Bridge STARTTLS、不受信任证书应失败、错误主机名应失败，以及 Proton 收件箱收到测试邮件，**仍未验证**。隔离捕获通过不能代替真实收件。合并本身也不改变这些门槛。
- 因此**不能宣称生产 newsletter 路径已经修通**。生产切换前，必须在实际要部署的镜像上再次通过原生 preview、隔离捕获，以及（若走 Proton）真实收件和 Route B 的实时 TLS 正反验收。
- 上游 `main` 与 `fb35a74000fe70e7d49f46cae3c895674571ea20` 仍包含旧的文本头实现；已发布失败 digest 仍然失败。
- 本地 unittest 不能替代部署验收。
- 路径游标仍不接受含 `/` 的 Base64；若未来分页格式改变，需要重测。
- 官方全厂商支持与 Proton 群发适用性边界依旧存在。

# ghost-newsletter-proton v4 改动说明（历史）

日期：2026-11-19（Asia/Shanghai）

本包从 v3 完善而来，同步了代理仓库副本上已隔离验证的 `Message-Id` 修复证据，并更正验收标识约定。这是可下载的通用 Skill 包，不是对上游仓库的合并，也不是共享 Skill 的安装更新，更不是生产路径已经全部修通的声明。原 v3 包未被覆盖。

以下条目保持 v4 发布时的原文，包括当时“尚未合并”的表述。

## 本版修改

- 更新支持状态：已发布 digest `ghcr.io/eznix86/mailgun-proxy-for-ghost@sha256:d3fbcd4f209ec27dbce81f8ff013ae8d09b833bbe5ac72715706b39fc575e33c` 与 Ghost 6.78.0 的原生 preview 失败仍作为**已知失败行**保留；不再把该失败泛称为所有代理版本失败。
- 记录用户 fork [YE4IM/mailgun-proxy-for-ghost](https://github.com/YE4IM/mailgun-proxy-for-ghost) 的修复提交 `e31299823886f4db9d026054632907924eb02d49` 与未合并的 [PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1)。官方提交归档 SHA-256 为 `96b2654d7cc0254dcdcd7efc55c1f1cf7e2fffe6a49095db3ecc7fe22bf2c9fc`。
- 区分两类测试证据：代码修复工作流中 123 项 PHP 测试（672 个断言）在 PHP 8.4.27 与 8.5.12 上通过，使用 Laravel array transport，不涉及 Docker 发信；本 Skill 包的本地 Python 测试为 38 项（含 2 项新增标识约定回归），全部通过，只覆盖验收助手与合成数据，不联网、不发信。
- 记录 2026-11-19 源码核验后的本地构建（PHP 8.5.13，Laravel 13.9.0，linux/amd64，未推送）。本地镜像 ID `sha256:4188afefc32d858a55e5787a5549b5f0665bd236aed7bc9640882f5906b15b96` 仅作为本地 ID 记载，**不得当作 registry manifest digest**。该镜像在隔离环境中通过了合成原生形态 POST，以及 Ghost 6.78.0 原生 preview，并各与一封内部 STARTTLS 捕获、唯一合法 MIME `Message-Id` 相关联。
- 补充未发布镜像的部署步骤：必须从固定提交构建并核验归档来源；`--load` 后可能出现的 RepoDigest 样式值仍不是已发布 digest。
- 更正标识约定：修复后的 HTTP 响应 `id` 不必是字面量 `message-id`；`deliveries.mailgun_message_id` 可以是独立的 19 位令牌，不等于 MIME `Message-Id`。验收须用唯一主题，以及出现时的 `X-Proxy-Trace` / `X-Newsletter-Delivery-Id` 关联。
- 不再承诺 Laravel `mailbox` 驱动捕获已通过：该路径曾出现 `accepted` 但未生成 mailbox SQLite。推荐已验证的内部 SMTP STARTTLS 捕获。包内仅提供通用、未执行过的捕获模板，不把未打包的夹具脚本当作可调用文件。
- 补齐本地回归：助手接受非字面量批次 `id`；事件中的存储 ID 与唯一主题不一致时仍按主题匹配。
- 全文去掉“代码缺陷仍完全未修、因此整条链路不可用”的过时表述，同时明确生产切换仍受真实收件与 Bridge TLS 门槛约束。

## 未解决 / 未测

- [PR #1](https://github.com/YE4IM/mailgun-proxy-for-ghost/pull/1) 尚未合并，修复镜像尚未发布到 registry。不能把本地镜像 ID 当作可拉取的 digest。
- 真实 Proton Bridge STARTTLS、不受信任证书应失败、错误主机名应失败，以及 Proton 收件箱收到测试邮件，**仍未验证**。隔离捕获通过不能代替真实收件。
- 因此**不能宣称生产 newsletter 路径已经修通**。生产切换前，必须在实际要部署的镜像上再次通过原生 preview、隔离捕获，以及（若走 Proton）真实收件和 Route B 的实时 TLS 正反验收。
- 上游 `main` 与 `fb35a74000fe70e7d49f46cae3c895674571ea20` 仍包含旧的文本头实现；已发布失败 digest 仍然失败。
- 本包未重新连接服务器、未合并代码、未推送镜像。本地 unittest 不能替代部署验收。
- 路径游标仍不接受含 `/` 的 Base64；若未来分页格式改变，需要重测。
- 官方全厂商支持与 Proton 群发适用性边界依旧存在。
