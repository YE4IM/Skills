# Skills

这里是我个人的 Skill 存留地。每个 Skill 都放在仓库根目录下的独立文件夹里，源文件直接入库，不使用压缩包，也不通过 GitHub Release 分发。

## 目录约定

- 一个 Skill 一个目录，目录名与 Skill 名称一致
- 每个目录以 `SKILL.md` 为入口，需要时再配 `scripts/`、`tests/`、`references/` 等
- 新增 Skill 时新建独立目录，不要覆盖已有 Skill

## 当前 Skill

- [ghost-newsletter-proton](./ghost-newsletter-proton) — 为自托管 Ghost 通过 Proton Mail 发送 newsletter：部署、修复或升级 Mailgun 兼容代理（支持直接 SMTP token 或 Proton Bridge）。不适用于 Ghost(Pro)。
- [website-macos-icon](./website-macos-icon) — 下载官网 favicon 或品牌图标，或把指定图片做成适用于 Finder 和 Dock 的 macOS ICNS 图标。打包需要在 macOS 上使用 `iconutil`。
