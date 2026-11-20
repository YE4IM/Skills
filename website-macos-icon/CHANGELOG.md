# website-macos-icon 修订说明

保留仅在 macOS 上用 `iconutil` 打包 ICNS，没有增加跨平台或 Linux 打包退路。

## 改动

- 多尺寸 ICO/CUR（含被 ImageMagick 标成 PNG 的 256×256 压缩帧）会自动选用面积最大、更接近正方形的那一帧；动画 GIF 及其他多帧文件仍会拒绝。
- 成功打包后会打印源图尺寸、是否上采样，以及选中的 ICO 帧。
- 核对过 subprocess：`run()` 未 capture 时工具的 stderr 会继承到终端，并不丢失。脚本只在异常对象里已有捕获文本时才附加到错误信息中。
- 先校验输出路径是否已存在，再检查依赖工具，避免误报，也避免覆盖已有 PNG/ICNS/iconset。
- Skill 明确了 `originals/`、`work/`、`outputs/` 交付目录，以及默认 100 px 透明边距；补充了仅在用户明确要求时使用的、可逆的 Finder「显示简介」粘贴/删除流程，不涉及修改系统应用或清理图标缓存。
- 默认提示覆盖「下载候选并挑选」和「把指定图像做成 ICNS」；描述补了中文触发词。Finder 尺寸仍标明为本地测量近似值。

## 测试

在 Linux 开发机上安装 ImageMagick 7.1.1 与 `rsvg-convert` 后运行：

`python3 -m unittest discover -s tests -v`

结果：**30 项中 27 通过、3 跳过、0 失败**。

跳过的 3 项是真正依赖 macOS `iconutil` 的集成测试（ICNS 往返、失败回滚清理、CLI 选择 ICO 并不留下失败输出）。它们在本环境无法运行，跳过或 mock 都不能代替在 macOS 上用 `iconutil` 做端到端验证。已运行的部分包括参数校验、ICO 帧选择、空图、preserve-layout、损坏 PNG/ICNS 头、发布不覆盖与回滚，以及用 ImageMagick 生成的真实 ICO/GIF/SVG/PNG 预处理与 iconset 图层检查。
