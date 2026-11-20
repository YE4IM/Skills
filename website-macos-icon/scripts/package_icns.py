#!/usr/bin/env python3
"""Package a prepared icon; source choice and background design happen beforehand."""
import argparse
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


ICON_POINT_SIZES = (16, 32, 128, 256, 512)
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def run(args):
    # Leave stdout/stderr inherited so tool diagnostics stay visible on the terminal.
    subprocess.run([str(a) for a in args], check=True)


def tool_failure_message(error):
    tool = error.cmd[0] if error.cmd else 'command'
    captured = error.stderr if error.stderr else error.output
    if captured is None:
        captured = ''
    elif isinstance(captured, bytes):
        captured = captured.decode('utf-8', 'replace')
    captured = captured.strip()
    detail = f'\n{captured}' if captured else ''
    return (f'error: {tool} failed (exit {error.returncode}). '
            f'Resolve the tool error and retry with the same output name.{detail}\n')


def name_error(name):
    if not name or Path(name).name != name or name in ('.', '..'):
        return '--name must be a single filename stem'
    return None


def body_size_error(body_size):
    if body_size is not None and not 1 <= body_size <= 1024:
        return '--body-size must be between 1 and 1024'
    return None


def option_combo_error(preserve_layout, body_size):
    if preserve_layout and body_size is not None:
        return '--body-size cannot be combined with --preserve-layout'
    return None


def existing_outputs(targets):
    return [target for target in targets if target.exists() or target.is_symlink()]


def read_icon_container(path):
    """Return 'ICO' or 'CUR' when the file starts with a valid icon directory."""
    data = path.read_bytes()
    if len(data) < 6:
        return None
    reserved, kind, count = struct.unpack_from('<HHH', data, 0)
    if reserved != 0 or kind not in (1, 2) or not 1 <= count <= 1024:
        return None
    if len(data) < 6 + 16 * count:
        return None
    return 'ICO' if kind == 1 else 'CUR'


def icon_container_kind(path, frames=None):
    kind = read_icon_container(path)
    if kind:
        return kind
    formats = {frame[1].upper() for frame in frames or ()}
    if 'ICO' in formats:
        return 'ICO'
    if 'CUR' in formats:
        return 'CUR'
    return None


def list_frames(source):
    output = subprocess.check_output(
        ['magick', str(source), '-format', '%m %w %h\\n', 'info:'], text=True)
    frames = []
    for index, line in enumerate(output.splitlines()):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f'could not inspect source frames: {line}')
        try:
            frames.append((index, parts[0], int(parts[1]), int(parts[2])))
        except ValueError as error:
            raise ValueError(f'could not inspect source frames: {line}') from error
    if not frames:
        raise ValueError('source has no images')
    return frames


def choose_largest_frame(frames):
    usable = [frame for frame in frames if frame[2] > 0 and frame[3] > 0]
    if not usable:
        raise ValueError('source has no usable frames')
    return max(usable, key=lambda frame: (frame[2] * frame[3], min(frame[2], frame[3]), frame[0]))


def format_source_report(meta):
    width, height = meta['width'], meta['height']
    if meta.get('svg'):
        line = f'Source: {width}x{height} SVG render'
    else:
        line = f'Source: {width}x{height} raster'
    kind = meta.get('icon_kind')
    count = meta.get('icon_frame_count') or 0
    if kind and count > 1:
        line += f' (largest {kind} frame {meta["selected_index"] + 1}/{count})'
    elif kind:
        line += f' ({kind})'
    if meta.get('preserve_layout'):
        line += ', layout preserved'
    elif meta.get('upsampled'):
        line += f', upsampled to {meta["body_size"]}px body'
    return line


def rasterize_source(source, workdir):
    meta = {
        'svg': False,
        'icon_kind': None,
        'icon_frame_count': 0,
        'selected_index': 0,
        'preserve_layout': False,
        'upsampled': False,
        'body_size': None,
    }
    if source.suffix.lower() == '.svg':
        raster = workdir / 'rendered.svg.png'
        run(['rsvg-convert', '--keep-aspect-ratio', '-w', '1024', '-h', '1024',
             source, '-o', raster])
        frames = list_frames(raster)
        if len(frames) != 1:
            raise ValueError('SVG render must contain exactly one image/frame')
        meta.update(svg=True, width=frames[0][2], height=frames[0][3])
        return raster, meta

    frames = list_frames(source)
    kind = icon_container_kind(source, frames)
    if kind and len(frames) > 1:
        chosen = choose_largest_frame(frames)
        raster = workdir / 'selected-frame.png'
        run(['magick', f'{source}[{chosen[0]}]', '+repage', raster])
        meta.update(icon_kind=kind, icon_frame_count=len(frames),
                    selected_index=chosen[0], width=chosen[2], height=chosen[3])
        return raster, meta
    if len(frames) != 1:
        fmt = frames[0][1] if frames else 'source'
        raise ValueError(
            f'source must contain exactly one image/frame (found {len(frames)} in {fmt})')
    if kind:
        meta.update(icon_kind=kind, icon_frame_count=1, selected_index=0)
    meta.update(width=frames[0][2], height=frames[0][3])
    return source, meta


def normalize(source, png, body_size=824):
    # A black border makes the bounding box measurable even for a fully opaque mask.
    geometry = subprocess.check_output(
        ['magick', str(source), '+repage', '-alpha', 'extract', '-threshold', '50%',
         '-bordercolor', 'black', '-border', '1', '-format', '%@', 'info:'],
        text=True).strip()
    bounds = re.fullmatch(r'(\d+)x(\d+)\+(\d+)\+(\d+)', geometry)
    if not bounds:
        raise ValueError(f'could not measure alpha bounds: {geometry}')
    width, height, x, y = map(int, bounds.groups())
    if not width or not height:
        raise ValueError('source has no visible content at alpha >= 50%')
    source_width, source_height = map(int, subprocess.check_output(
        ['magick', str(source), '-format', '%w %h', 'info:'], text=True).split())
    scale = body_size / max(width, height)
    resized_width = max(1, round(source_width * scale))
    resized_height = max(1, round(source_height * scale))
    # Measure the body, but transform the full image so faint edges survive.
    offset_x = round(512 - (x - 1 + width / 2) * resized_width / source_width)
    offset_y = round(512 - (y - 1 + height / 2) * resized_height / source_height)
    run(['magick', '-size', '1024x1024', 'xc:none', '(', source, '+repage',
         '-filter', 'Lanczos', '-resize', f'{resized_width}x{resized_height}!', ')',
         '-geometry', f'{offset_x:+d}{offset_y:+d}', '-compose', 'over', '-composite', png])
    return scale


def prepare_master(raster, png, preserve_layout, body_size, meta):
    meta['preserve_layout'] = preserve_layout
    meta['body_size'] = body_size
    if preserve_layout:
        if (meta['width'], meta['height']) != (1024, 1024):
            raise ValueError('--preserve-layout requires a 1024x1024 source')
        run(['magick', raster, png])
        meta['upsampled'] = False
        return
    scale = normalize(raster, png, body_size)
    meta['upsampled'] = (not meta.get('svg')) and scale > 1


def png_dimensions(path):
    with path.open('rb') as image:
        header = image.read(24)
    if len(header) != 24 or header[:8] != PNG_MAGIC:
        raise ValueError(f'invalid PNG or dimensions for {path.name}')
    return struct.unpack('>II', header[16:24])


def parse_icns_tags(data):
    if len(data) < 8 or data[:4] != b'icns' or int.from_bytes(data[4:8], 'big') != len(data):
        raise ValueError('invalid ICNS header')
    index, tags = 8, set()
    while index < len(data):
        if index + 8 > len(data):
            raise ValueError('invalid ICNS entry size')
        size = int.from_bytes(data[index + 4:index + 8], 'big')
        if size < 8 or index + size > len(data):
            raise ValueError('invalid ICNS entry size')
        tags.add(data[index:index + 4])
        index += size
    return tags


def validate_icns(icns):
    tags = parse_icns_tags(icns.read_bytes())
    if b'ic10' not in tags:
        raise ValueError('ICNS is missing its 1024x1024 layer')
    with tempfile.TemporaryDirectory(prefix='decoded-', dir=icns.parent) as temp:
        decoded = Path(temp) / 'decoded.iconset'
        run(['iconutil', '-c', 'iconset', icns, '-o', decoded])
        largest = decoded / 'icon_512x512@2x.png'
        validate_png(largest, 1024, require_visible=True)


def validate_png(path, pixels, require_visible=False):
    if png_dimensions(path) != (pixels, pixels):
        raise ValueError(f'invalid PNG or dimensions for {path.name}')
    # Force a complete pixel decode, rather than relying on metadata alone.
    run(['magick', '-regard-warnings', path, 'null:'])
    if require_visible:
        alpha = subprocess.check_output(
            ['magick', str(path), '-alpha', 'extract', '-format', '%[fx:maxima]', 'info:'],
            text=True).strip()
        if float(alpha) <= 0:
            raise ValueError('decoded largest ICNS layer has no visible content')


def write_iconset(png, iconset):
    iconset.mkdir()
    for base in ICON_POINT_SIZES:
        for scale in (1, 2):
            suffix = '@2x' if scale == 2 else ''
            target = iconset / f'icon_{base}x{base}{suffix}.png'
            pixels = base * scale
            run(['magick', png, '-filter', 'Lanczos', '-resize', f'{pixels}x{pixels}', target])
            validate_png(target, pixels)


def publish(staging, png, icns, iconset):
    # Claim this name without replacing a directory created by another run.
    iconset.mkdir()
    published = []
    try:
        for target in (png, icns):
            os.link(staging / target.name, target)
            published.append(target)
        for layer in (staging / iconset.name).iterdir():
            layer.rename(iconset / layer.name)
    except (OSError, KeyboardInterrupt):
        for target in published:
            target.unlink()
        shutil.rmtree(iconset)
        raise


def package(source, png, icns, iconset, preserve_layout, body_size=824):
    raster, meta = rasterize_source(source, png.parent)
    prepare_master(raster, png, preserve_layout, body_size, meta)
    write_iconset(png, iconset)
    run(['iconutil', '-c', 'icns', iconset, '-o', icns])
    validate_icns(icns)
    return format_source_report(meta)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--body-size', type=int, default=None,
                        help='Visible body size in pixels, 1–1024 (default: 824)')
    parser.add_argument('--preserve-layout', action='store_true',
                        help='Keep an already verified 1024x1024 layout unchanged')
    args = parser.parse_args()
    if error := body_size_error(args.body_size):
        parser.error(error)
    if error := option_combo_error(args.preserve_layout, args.body_size):
        parser.error(error)
    if error := name_error(args.name):
        parser.error(error)
    if not args.source.is_file():
        parser.error('source does not exist')
    out = args.output_dir.resolve()
    png = out / f'{args.name}-1024.png'
    icns = out / f'{args.name}.icns'
    iconset = out / f'{args.name}.iconset'
    if existing := existing_outputs((png, icns, iconset)):
        parser.error(f'output already exists; choose a new name: {existing[0]}')
    needed = ['magick', 'iconutil']
    if args.source.suffix.lower() == '.svg':
        needed.append('rsvg-convert')
    for tool in needed:
        if not shutil.which(tool):
            parser.error(f'missing required tool: {tool}')
    try:
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.macos-icon-', dir=out) as temp:
            staging = Path(temp)
            report = package(args.source.absolute(), staging / png.name, staging / icns.name,
                             staging / iconset.name, args.preserve_layout,
                             args.body_size if args.body_size is not None else 824)
            publish(staging, png, icns, iconset)
    except subprocess.CalledProcessError as error:
        parser.exit(1, tool_failure_message(error))
    except (ValueError, OSError) as error:
        parser.exit(1, f'error: {error}\n')
    print(f'Validated: {icns}\nPreview: {png}\nSizes: {iconset}')
    print(report)


if __name__ == '__main__':
    main()
