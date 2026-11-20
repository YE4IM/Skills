import importlib.util
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/package_icns.py'
spec = importlib.util.spec_from_file_location('package_icns', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

HAS_MAGICK = shutil.which('magick') is not None
HAS_RSVG = shutil.which('rsvg-convert') is not None
HAS_ICONUTIL = shutil.which('iconutil') is not None


def skip_unless_magick(test):
    return unittest.skipUnless(HAS_MAGICK, 'requires ImageMagick magick')(test)


def skip_unless_rsvg(test):
    return unittest.skipUnless(HAS_MAGICK and HAS_RSVG,
                               'requires ImageMagick and rsvg-convert')(test)


def skip_unless_iconutil(test):
    return unittest.skipUnless(HAS_MAGICK and HAS_ICONUTIL,
                               'requires ImageMagick and macOS iconutil')(test)


def png_header(width, height):
    return (b'\x89PNG\r\n\x1a\n'
            + struct.pack('>I', 13) + b'IHDR'
            + struct.pack('>II', width, height))


def icon_container_bytes(kind=1, count=1, directory_only=False):
    header = struct.pack('<HHH', 0, kind, count)
    entries = b''
    payload = b''
    offset = 6 + 16 * count
    for index in range(count):
        size = 16
        if not directory_only:
            payload += b'\x00' * size
        entries += struct.pack('<BBBBHHII', 16, 16, 0, 0, 1, 32, size, offset)
        offset += size
    data = header + entries
    return data if directory_only else data + payload


def icns_bytes(entries):
    body = b''
    for tag, payload in entries:
        body += tag + struct.pack('>I', 8 + len(payload)) + payload
    return b'icns' + struct.pack('>I', 8 + len(body)) + body


class ArgAndPathTests(unittest.TestCase):
    def test_body_size_and_option_combo(self):
        self.assertIsNone(mod.body_size_error(None))
        self.assertIsNone(mod.body_size_error(1))
        self.assertIsNone(mod.body_size_error(1024))
        self.assertIn('between 1 and 1024', mod.body_size_error(0))
        self.assertIn('between 1 and 1024', mod.body_size_error(1025))
        self.assertIsNone(mod.option_combo_error(False, 700))
        self.assertIsNone(mod.option_combo_error(True, None))
        self.assertIn('cannot be combined', mod.option_combo_error(True, 700))

    def test_name_validation(self):
        self.assertIsNone(mod.name_error('Brand-macOS'))
        for name in ('', '.', '..', 'a/b'):
            with self.subTest(name=name):
                self.assertIsNotNone(mod.name_error(name))

    def test_existing_outputs_detects_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            png = root / 'Test-1024.png'
            icns = root / 'Test.icns'
            iconset = root / 'Test.iconset'
            self.assertEqual(mod.existing_outputs((png, icns, iconset)), [])
            icns.write_bytes(b'keep me')
            self.assertEqual(mod.existing_outputs((png, icns, iconset)), [icns])
            broken = root / 'broken.icns'
            broken.symlink_to(root / 'missing-target')
            self.assertEqual(mod.existing_outputs((broken,)), [broken])


class CliValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.bin'
        self.source.write_bytes(b'not-an-image')
        self.out = self.root / 'out'

    def cli(self, *args, source=None, name='Test'):
        return subprocess.run(
            ['python3', str(SCRIPT), str(source or self.source),
             '--output-dir', str(self.out), '--name', name, *args],
            capture_output=True, text=True)

    def test_invalid_options_do_not_need_mac_tools(self):
        cases = [
            (('--body-size', '0'), 'between 1 and 1024'),
            (('--body-size', '1025'), 'between 1 and 1024'),
            (('--body-size', '700', '--preserve-layout'), 'cannot be combined'),
            ((), 'single filename stem', '..'),
        ]
        for extra, message, *name in cases:
            with self.subTest(extra=extra, message=message):
                result = self.cli(*extra, name=name[0] if name else 'Test')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_existing_output_not_overwritten(self):
        self.out.mkdir()
        existing = self.out / 'Test.icns'
        existing.write_bytes(b'keep me')
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already exists', result.stderr)
        self.assertEqual(existing.read_bytes(), b'keep me')
        self.assertEqual(list(self.out.iterdir()), [existing])


class FrameSelectionTests(unittest.TestCase):
    def test_choose_largest_frame_area_tie_and_index(self):
        frames = [(0, 'ICO', 16, 16), (1, 'ICO', 32, 32), (2, 'PNG', 64, 64)]
        self.assertEqual(mod.choose_largest_frame(frames)[0], 2)
        tied = [(0, 'ICO', 64, 16), (1, 'ICO', 32, 32)]
        self.assertEqual(mod.choose_largest_frame(tied)[0], 1)
        same = [(0, 'ICO', 32, 32), (1, 'PNG', 32, 32)]
        self.assertEqual(mod.choose_largest_frame(same)[0], 1)

    def test_choose_largest_frame_rejects_empty(self):
        with self.assertRaisesRegex(ValueError, 'no usable frames'):
            mod.choose_largest_frame([(0, 'ICO', 0, 16), (1, 'ICO', 32, 0)])

    def test_icon_container_header_and_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ico = root / 'icon.ico'
            ico.write_bytes(icon_container_bytes(kind=1, count=3))
            self.assertEqual(mod.read_icon_container(ico), 'ICO')
            cur = root / 'icon.cur'
            cur.write_bytes(icon_container_bytes(kind=2, count=1))
            self.assertEqual(mod.read_icon_container(cur), 'CUR')
            png = root / 'plain.png'
            png.write_bytes(png_header(16, 16))
            self.assertIsNone(mod.read_icon_container(png))
            self.assertIsNone(mod.icon_container_kind(png, [(0, 'PNG', 16, 16)]))
            self.assertEqual(
                mod.icon_container_kind(png, [(0, 'ICO', 16, 16), (1, 'PNG', 256, 256)]),
                'ICO')
            truncated = root / 'short.ico'
            truncated.write_bytes(icon_container_bytes(count=3, directory_only=True)[:10])
            self.assertIsNone(mod.read_icon_container(truncated))


class ContainerParseTests(unittest.TestCase):
    def test_parse_icns_tags_accepts_ic10(self):
        data = icns_bytes([(b'ic10', b'\x00' * 8), (b'TOC ', b'\x00' * 4)])
        self.assertIn(b'ic10', mod.parse_icns_tags(data))

    def test_parse_icns_tags_rejects_damaged_containers(self):
        valid = icns_bytes([(b'ic10', b'\x00' * 8)])
        cases = [
            b'short',
            b'ICNS' + struct.pack('>I', 8),
            valid[:8] + struct.pack('>I', 99) + valid[8:12],
            b'icns' + struct.pack('>I', 16) + b'ic10\x00\x00\x00',
        ]
        # Wrong length field.
        bad_length = bytearray(valid)
        bad_length[4:8] = struct.pack('>I', len(valid) + 5)
        cases.append(bytes(bad_length))
        for data in cases:
            with self.subTest(data=data[:8]):
                with self.assertRaises(ValueError):
                    mod.parse_icns_tags(data)

    def test_missing_ic10_is_reported(self):
        data = icns_bytes([(b'ic09', b'\x00' * 8)])
        tags = mod.parse_icns_tags(data)
        self.assertNotIn(b'ic10', tags)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'broken.icns'
            path.write_bytes(data)
            with patch.object(mod, 'run', side_effect=AssertionError('iconutil must not run')):
                with self.assertRaisesRegex(ValueError, '1024x1024 layer'):
                    mod.validate_icns(path)

    def test_png_header_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'icon.png'
            path.write_bytes(png_header(64, 64) + b'\x00' * 8)
            self.assertEqual(mod.png_dimensions(path), (64, 64))
            path.write_bytes(png_header(32, 16) + b'\x00' * 8)
            self.assertEqual(mod.png_dimensions(path), (32, 16))
            path.write_bytes(b'not-a-png' + b'\x00' * 20)
            with self.assertRaisesRegex(ValueError, 'invalid PNG'):
                mod.png_dimensions(path)
            path.write_bytes(png_header(64, 64)[:10])
            with self.assertRaisesRegex(ValueError, 'invalid PNG'):
                mod.png_dimensions(path)


class ReportAndErrorTests(unittest.TestCase):
    def test_format_source_report_variants(self):
        base = dict(width=256, height=256, svg=False, icon_kind=None,
                    icon_frame_count=0, selected_index=0, preserve_layout=False,
                    upsampled=False, body_size=824)
        self.assertEqual(mod.format_source_report(base), 'Source: 256x256 raster')
        ico = dict(base, icon_kind='ICO', icon_frame_count=3, selected_index=2,
                   upsampled=True)
        self.assertEqual(
            mod.format_source_report(ico),
            'Source: 256x256 raster (largest ICO frame 3/3), upsampled to 824px body')
        svg = dict(base, svg=True, width=1024, height=512)
        self.assertEqual(mod.format_source_report(svg), 'Source: 1024x512 SVG render')
        preserved = dict(base, width=1024, height=1024, preserve_layout=True)
        self.assertEqual(
            mod.format_source_report(preserved),
            'Source: 1024x1024 raster, layout preserved')

    def test_tool_failure_message_includes_captured_text_only(self):
        inherited = subprocess.CalledProcessError(1, ['magick', 'in', 'out'])
        message = mod.tool_failure_message(inherited)
        self.assertIn('magick failed (exit 1)', message)
        self.assertNotIn('unable to open', message)
        captured = subprocess.CalledProcessError(
            2, ['iconutil', '-c', 'icns'], output=None,
            stderr='Invalid Iconset.\n')
        self.assertIn('Invalid Iconset.', mod.tool_failure_message(captured))


class PublishTests(unittest.TestCase):
    def test_publish_rollback_leaves_no_partial_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging = root / 'staging'
            staged_set = staging / 'Test.iconset'
            staged_set.mkdir(parents=True)
            (staging / 'Test-1024.png').write_bytes(b'png')
            (staging / 'Test.icns').write_bytes(b'icns')
            (staged_set / 'icon_16x16.png').write_bytes(b'layer')
            dest_png = root / 'Test-1024.png'
            dest_icns = root / 'Test.icns'
            dest_set = root / 'Test.iconset'

            real_link = os.link

            def fail_link(source, target):
                if Path(target) == dest_icns:
                    raise OSError('injected failure')
                return real_link(source, target)

            with patch.object(mod.os, 'link', side_effect=fail_link):
                with self.assertRaises(OSError):
                    mod.publish(staging, dest_png, dest_icns, dest_set)
            self.assertFalse(dest_png.exists())
            self.assertFalse(dest_icns.exists())
            self.assertFalse(dest_set.exists())


class MagickPrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.png'

    def image(self, *args, dest=None):
        mod.run(['magick', *args, dest or self.source])

    def prepare(self, source=None, preserve_layout=False, body_size=824):
        work = self.root / 'work'
        work.mkdir(exist_ok=True)
        raster, meta = mod.rasterize_source(Path(source or self.source), work)
        dest = work / 'master.png'
        mod.prepare_master(raster, dest, preserve_layout, body_size, meta)
        return dest, meta, work

    @skip_unless_magick
    def test_shadow_survives_normalization(self):
        self.image('-size', '1024x1024', 'xc:none', '-fill', 'rgba(0,0,0,0.2)',
                   '-draw', 'rectangle 90,90 933,933', '-fill', 'red',
                   '-draw', 'rectangle 100,100 923,923')
        dest = self.root / 'normalized.png'
        mod.normalize(self.source, dest)
        alpha = subprocess.check_output(['magick', str(dest), '-format',
                                         '%[fx:p{95,512}.a]', 'info:'], text=True)
        self.assertGreater(float(alpha), 0.1)
        self.assertLess(float(alpha), 0.5)

    @skip_unless_magick
    def test_transparent_input_fails(self):
        self.image('-size', '64x64', 'xc:none')
        with self.assertRaisesRegex(ValueError, 'no visible content'):
            self.prepare()

    @skip_unless_magick
    def test_animated_gif_rejected(self):
        self.source = self.root / 'source.gif'
        self.image('-size', '16x16', 'xc:red', 'xc:blue')
        with self.assertRaisesRegex(ValueError, 'exactly one image/frame'):
            mod.rasterize_source(self.source, self.root)

    @skip_unless_magick
    def test_single_frame_gif_accepted(self):
        self.source = self.root / 'still.gif'
        self.image('-size', '32x32', 'xc:red')
        raster, meta = mod.rasterize_source(self.source, self.root)
        self.assertEqual(raster, self.source)
        self.assertEqual((meta['width'], meta['height']), (32, 32))

    @skip_unless_magick
    def test_ico_selects_largest_distinct_frame(self):
        self.source = self.root / 'multi.ico'
        self.image('-size', '16x16', 'xc:red', '-size', '32x32', 'xc:blue',
                   '-size', '64x64', 'xc:lime')
        dest, meta, work = self.prepare()
        self.assertEqual((meta['width'], meta['height']), (64, 64))
        self.assertEqual(meta['icon_kind'], 'ICO')
        self.assertEqual(meta['selected_index'], 2)
        self.assertTrue((work / 'selected-frame.png').is_file())
        color = subprocess.check_output(
            ['magick', str(dest), '-format', '%[hex:u.p{512,512}]', 'info:'],
            text=True).strip()
        self.assertTrue(color.upper().startswith('00FF00'), color)
        self.assertTrue(meta['upsampled'])
        self.assertIn('largest ICO frame 3/3', mod.format_source_report(meta))

    @skip_unless_magick
    def test_png_compressed_ico_frame_is_selected(self):
        self.source = self.root / 'with256.ico'
        self.image('-size', '16x16', 'xc:red', '-size', '256x256', 'xc:yellow')
        dest, meta, _ = self.prepare()
        self.assertEqual((meta['width'], meta['height']), (256, 256))
        color = subprocess.check_output(
            ['magick', str(dest), '-format', '%[hex:u.p{512,512}]', 'info:'],
            text=True).strip()
        self.assertTrue(color.upper().startswith('FFFF00'), color)

    @skip_unless_magick
    def test_upsample_flag_depends_on_body_scale(self):
        self.image('-size', '64x64', 'xc:red')
        _, small, _ = self.prepare(body_size=824)
        self.assertTrue(small['upsampled'])
        large = self.root / 'large.png'
        self.image('-size', '900x900', 'xc:red', dest=large)
        _, fitted, _ = self.prepare(source=large, body_size=824)
        self.assertFalse(fitted['upsampled'])
        self.assertNotIn('upsampled', mod.format_source_report(fitted))

    @skip_unless_magick
    def test_preserve_layout_and_wrong_size(self):
        self.image('-size', '1024x1024', 'xc:none', '-fill', 'red',
                   '-draw', 'rectangle 20,30 70,90')
        dest, meta, _ = self.prepare(preserve_layout=True)
        self.assertFalse(meta['upsampled'])
        comparison = subprocess.run(
            ['magick', 'compare', '-metric', 'AE', str(self.source), str(dest), 'null:'],
            capture_output=True, text=True)
        self.assertEqual(comparison.returncode, 0, comparison.stderr)
        self.assertIn('layout preserved', mod.format_source_report(meta))
        small = self.root / 'small.png'
        self.image('-size', '64x64', 'xc:red', dest=small)
        with self.assertRaisesRegex(ValueError, '1024x1024'):
            self.prepare(source=small, preserve_layout=True)

    @skip_unless_magick
    def test_custom_body_size_on_master(self):
        self.image('-size', '64x64', 'xc:red')
        dest, _, _ = self.prepare(body_size=700)
        bounds = subprocess.check_output(
            ['magick', str(dest), '-alpha', 'extract', '-threshold', '50%',
             '-format', '%@', 'info:'], text=True)
        self.assertEqual(bounds, '700x700+162+162')

    @skip_unless_magick
    def test_write_iconset_ten_validated_layers(self):
        self.image('-size', '64x64', 'xc:red')
        dest, _, _ = self.prepare()
        iconset = self.root / 'Test.iconset'
        mod.write_iconset(dest, iconset)
        layers = sorted(path.name for path in iconset.glob('*.png'))
        self.assertEqual(len(layers), 10)
        self.assertIn('icon_16x16.png', layers)
        self.assertIn('icon_512x512@2x.png', layers)

    @skip_unless_magick
    def test_truncated_png_rejected(self):
        self.image('-size', '64x64', 'xc:red')
        self.source.write_bytes(self.source.read_bytes()[:24])
        with self.assertRaises(subprocess.CalledProcessError):
            mod.validate_png(self.source, 64)

    @skip_unless_rsvg
    def test_rectangular_svg_keeps_proportions(self):
        self.source = self.root / 'source.svg'
        self.source.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">'
            '<rect width="200" height="100" fill="red"/></svg>')
        dest, meta, _ = self.prepare()
        self.assertTrue(meta['svg'])
        self.assertFalse(meta['upsampled'])
        bounds = subprocess.check_output(
            ['magick', str(dest), '-alpha', 'extract', '-threshold', '50%',
             '-format', '%@', 'info:'], text=True)
        self.assertEqual(bounds, '824x412+100+306')
        self.assertIn('SVG render', mod.format_source_report(meta))


class PackagingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.png'

    def image(self, *args):
        mod.run(['magick', *args, self.source])

    def cli(self, *args, source=None, name='Test'):
        return subprocess.run(
            ['python3', str(SCRIPT), str(source or self.source),
             '--output-dir', str(self.root / 'out'), '--name', name, *args],
            capture_output=True, text=True)

    @skip_unless_iconutil
    def test_roundtrip_and_custom_body_size(self):
        self.image('-size', '64x64', 'xc:red')
        result = self.cli('--body-size', '700')
        self.assertEqual(result.returncode, 0, result.stderr)
        out = self.root / 'out'
        mod.validate_icns(out / 'Test.icns')
        self.assertEqual(len(list((out / 'Test.iconset').glob('*.png'))), 10)
        bounds = subprocess.check_output(
            ['magick', str(out / 'Test-1024.png'),
             '-alpha', 'extract', '-threshold', '50%',
             '-format', '%@', 'info:'], text=True)
        self.assertEqual(bounds, '700x700+162+162')
        self.assertIn('upsampled to 700px body', result.stdout)

    @skip_unless_iconutil
    def test_failed_packaging_cleans_staging(self):
        self.image('-size', '64x64', 'xc:red')
        argv = ['package_icns', str(self.source), '--output-dir', str(self.root / 'out'),
                '--name', 'Test']
        with patch('sys.argv', argv), patch.object(
                mod, 'validate_icns', side_effect=ValueError('injected failure')) as validate:
            with self.assertRaises(SystemExit):
                mod.main()
            validate.assert_called_once()
        self.assertEqual(list((self.root / 'out').iterdir()), [])

    @skip_unless_iconutil
    def test_cli_ico_selection_and_transparent_failure_leave_outputs_clean(self):
        ico = self.root / 'multi.ico'
        mod.run(['magick', '-size', '16x16', 'xc:red', '-size', '32x32', 'xc:blue',
                 '-size', '64x64', 'xc:lime', ico])
        result = self.cli(source=ico)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('largest ICO frame 3/3', result.stdout)
        empty = self.root / 'empty.png'
        mod.run(['magick', '-size', '64x64', 'xc:none', empty])
        failed = self.cli(source=empty, name='Empty')
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('no visible content', failed.stderr)
        self.assertFalse((self.root / 'out' / 'Empty.icns').exists())
        self.assertFalse((self.root / 'out' / 'Empty-1024.png').exists())


if __name__ == '__main__':
    unittest.main()
