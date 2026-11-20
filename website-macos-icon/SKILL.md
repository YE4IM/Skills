---
name: website-macos-icon
description: Download official website favicons or brand icons, or turn a specified image into a macOS ICNS icon sized for Finder and the Dock. Use when the user asks for a favicon, site icon, ICNS, Dock or app icon, 网站图标, 网站 favicon, ICNS 图标, or Dock 图标. When a website offers multiple visually distinct candidates and the user has not selected one, deliver the originals for selection before making the ICNS.
---

# Website Icons for macOS

Match the language of the user's request. Preserve the brand mark. Installing or replacing an application's icon requires an explicit request; packaging an ICNS is not permission to install it.

This packaging workflow requires macOS `iconutil` and is not a cross-platform ICNS builder.

## Choose the workflow

- **Download only.** Deliver the original files and source URLs. Finish after delivery.
- **Specified source.** If the user provides a local image or explicitly selects an asset, start preparing the icon. Treat a homepage URL as a request to discover assets.
- **Website to ICNS.** Find the relevant official assets and deliver the originals. If the user asks to choose or there are multiple visually distinct candidates and the user has not picked one, stop after delivery and wait for an explicit selection. If there is one visual-design group and the user requested an ICNS without asking to review the source first, continue with that candidate.

## Find and deliver official assets

1. Open the official site using the browser guidance for the environment. Check the homepage for `rel=icon`, `shortcut icon`, `apple-touch-icon`, `mask-icon`, icons in a declared web app manifest, and the homepage brand mark.
2. Group candidates by visual design: different formats and resolutions of the same mark are one choice; distinct marks or color treatments are separate choices. Choose the best-quality source within each group automatically. Prefer an SVG favicon, followed by PNG and ICO. Label monochrome Safari mask icons and include the color candidate when available. Verify that each candidate represents the requested brand.
3. Download the unmodified files, verify that their contents match the format, and record their source URLs. Use safe filenames and download only relevant candidates.
4. Use a per-request folder with three subdirectories:
   - `originals/` — unmodified downloads; never overwrite or edit these files
   - `work/` — intermediate renders, crops, and experiments
   - `outputs/` — final master PNG, iconset, and ICNS
   Provide clickable absolute paths, source URLs, file formats, available dimensions or SVG viewBox, and whether each candidate is monochrome or color. Show previews when possible.

## Prepare the icon

Prepare a square icon in `work/`, then pass that file to the packaging script. The script accepts a single still image, or a multi-size ICO/CUR, from which it automatically uses the largest frame, including PNG-compressed 256×256 entries. Do not pass an animated GIF, animated WebP, APNG, or other multi-frame file; extract a single still first. The script reports the original raster or SVG render size and whether a raster was upsampled.

### Canvas, margins, and shape

- Default packaging measures the alpha ≥ 50% body, fits it proportionally within an 824×824 area, and centers it on a 1024×1024 transparent canvas. A square body therefore has 100 px of transparent margin on each side. Faint shadows below the 50% alpha threshold are kept when they fit on the canvas and are clipped if they would extend outside it. Use `--body-size` when a different margin is needed; use `--preserve-layout` for an already checked 1024×1024 design whose spacing, edges, or shadows should stay unchanged.
- The 824/100 px figures come from a local Finder measurement of a 206×206 pixel body with 25 px margins in a 256×256 layer, using an alpha threshold of 50%. Treat them as a local approximation, not an Apple-published spec. A simple corner radius of 185 px is also only a visual approximation. If you extract Finder layers for comparison, use `iconutil -c iconset /System/Library/CoreServices/Finder.app/Contents/Resources/Finder.icns -o /absolute/path/work/Finder.iconset`, compare only the outline of the largest available layer, and measure the body at alpha ≥ 50% so soft shadows do not affect the measurement. Report local measurements only if they were actually made.
- Size the mark separately from the backplate. A mark height of 550–600 px is a useful starting point. Preserve its proportions and center it visually with enough room around it. Reuse a suitable existing backplate and scale the complete icon. If the outline needs adjustment, keep the full brand mark visible.

### Backplate and color

- A complete icon can already have a backplate surrounded by transparency. When the source is a standalone transparent mark, add a rounded-square backplate by default. Honor explicit requests about transparency or color.
- Pick a subtle light or dark color with clear contrast against the brand mark. For example, a purple Proton mark can sit on a soft gradient from `#FAF8FF` to `#EDE7FF`. Choose a reasonable color directly unless the user asks to review it.
- Preserve the mark's shape, proportions, and colors. Keep any border or shadow subtle and omit added text. Simple backplates can be drawn with SVG geometry. For creative raster edits, follow the environment's image-editing guidance and check the result for distortion and stray edge pixels.

## Package and verify

- Render SVGs at high resolution and downsample with a high-quality filter. Use the best available PNG resolution and preserve alpha.
- Use [scripts/package_icns.py](scripts/package_icns.py) with an already designed square icon. The script requires Python 3, ImageMagick (`magick`), and macOS `iconutil`. SVG input also requires `rsvg-convert` from librsvg. Point `--output-dir` at the absolute `outputs/` path. The script refuses to overwrite an existing PNG, ICNS, or iconset of the same name; choose a new `--name` instead.
- It writes a 1024 master PNG, ten iconset PNGs (16, 32, 128, 256, and 512 points at 1× and 2×), and an ICNS. After a successful run it prints the original raster or SVG render size, whether a raster was upsampled, and which ICO frame was selected. It fully decodes the layer PNGs, checks their dimensions and the ICNS structure, then extracts and decodes the 1024×1024 ICNS layer and checks for visible content before publishing.
- If `iconutil` reports `Invalid Iconset`, check filenames, PNG format, and dimensions. The execution environment can produce this error for a valid iconset. Follow the environment's approval process if a run outside the sandbox is needed. After resolving a packaging failure, retry using the same output name.
- Inspect the master PNG for transparency, smooth corners, stray pixels, and correct mark proportions. Compare with Finder at the same canvas size if a reference is available. The script verifies decoding of the largest ICNS layer; visually inspect it too if the preview or packaging result looks unexpected. Report actual Dock appearance only if observed.
- Deliver clickable absolute paths to the ICNS and master PNG. Identify the source asset, original pixel size, whether it was upsampled, backplate color, and any approximation used. Save new versions under new names and retain the originals.

Normalize a prepared icon to the default bounds.

```sh
python3 scripts/package_icns.py /absolute/path/prepared-icon.svg \
  --output-dir /absolute/path/outputs --name Brand-macOS
```

Preserve a checked 1024×1024 layout with a soft shadow.

```sh
python3 scripts/package_icns.py /absolute/path/prepared-shadow.png \
  --output-dir /absolute/path/outputs --name Brand-macOS-shadow --preserve-layout
```

## Install or restore an icon in Finder

Only follow this section when the user explicitly asks to install, apply, or replace an icon on a named app, folder, or file. Do not modify apps in `/System`, do not disable System Integrity Protection, and do not delete or rebuild icon caches or use `sudo` to force an icon change.

These Finder steps are user-visible and reversible:

1. Open the master 1024 PNG in Preview, select all, and copy. Alternatively, select the ICNS file in Finder and copy it.
2. In Finder, select the target application, folder, or file and choose Get Info (⌘I).
3. Click the small icon in the top-left corner of the Get Info window so it is highlighted, then paste (⌘V). Replacing an icon inside `/Applications` may prompt for an administrator password.
4. To restore the original icon, open Get Info again, select that small icon, and press Delete.

App updates may replace a custom icon. If the icon cannot be applied with the steps above, stop and tell the user; do not escalate to cache clearing or system-file edits.

## Apple references

This workflow targets ICNS files for manual app-icon replacement. For a modern macOS app shipped through Xcode, use the current Icon Composer workflow for layered app icons. Apple documents a 1024×1024 Mac canvas and system masking. Treat 824 px, 100 px, and the example corner radius as local design guidance. [App icons HIG](https://developer.apple.com/design/human-interface-guidelines/app-icons) · [Icon Composer](https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer) · [Apple Design Resources](https://developer.apple.com/design/resources/)

## Regression checks

Run `python3 -m unittest discover -s tests -v` after changing the packaging script. Argument, header, and frame-selection tests run without macOS tools. Tests that need ImageMagick, `rsvg-convert`, or `iconutil` are skipped when the tool is missing. Skipped or mocked tests are not a substitute for a real `iconutil` verification on macOS. Tests use temporary files and must not overwrite user data.
