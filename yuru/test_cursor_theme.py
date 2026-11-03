"""Independent format fixtures test cursor verification failure modes."""
from pathlib import Path
import struct
import tempfile
import unittest

from verify_cursors import Decoder, REQUIRED, SIZES, inspect_theme, optical_metrics, rgba


def fixture(animated=False, bad_hotspot=False):
    chunks, toc = [], []
    count = len(SIZES) * (2 if animated else 1)
    offset = 16 + count * 12
    for size in SIZES:
        for frame in range(2 if animated else 1):
            pixels = [0] * (size * size)
            pixels[0] = 0xffffffff
            pixels[1] = 0x80402010 if frame == 0 else 0x80201008
            chunk = struct.pack('<9I', 36, 0xfffd0002, size, 1, size, size,
                                size if bad_hotspot else 0, 0, 90 if animated else 0)
            chunk += struct.pack(f'<{len(pixels)}I', *pixels)
            chunks.append(chunk)
            toc.append(struct.pack('<3I', 0xfffd0002, size, offset))
            offset += len(chunk)
    return struct.pack('<4I', 0x72756358, 16, 0x10000, count) + b''.join(toc + chunks)


class CompiledCursorVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='yuru-cursor-test-')
        self.addCleanup(self.temporary.cleanup)
        self.theme = Path(self.temporary.name) / 'Yuru-Cursors'
        self.cursors = self.theme / 'cursors'
        self.cursors.mkdir(parents=True)
        (self.theme / 'index.theme').write_text('[Icon Theme]\nName=Fixture\n')
        (self.cursors / 'left_ptr').write_bytes(fixture())
        (self.cursors / 'wait').write_bytes(fixture(animated=True))
        (self.cursors / 'progress').write_bytes(fixture(animated=True))
        for name in REQUIRED:
            path = self.cursors / name
            if not path.exists():
                path.symlink_to('left_ptr')

    def test_libxcursor_decodes_all_sizes_frames_hotspots_and_timing(self):
        frames, evidence = inspect_theme(self.theme)
        self.assertEqual(len(frames[evidence['aliases'].get('left_ptr', 'left_ptr')]), 4)
        self.assertEqual(len(frames['wait']), 8)
        self.assertEqual(evidence['aliases']['default'], 'left_ptr')
        self.assertEqual(frames['wait'][0]['delay_ms'], 90)
        self.assertEqual(frames[evidence['aliases'].get('left_ptr', 'left_ptr')][0]['hotspot'], [0, 0])

    def test_regular_aliases_are_deduplicated_by_binary_content(self):
        (self.cursors / 'arrow').write_bytes(fixture())
        frames, evidence = inspect_theme(self.theme)
        self.assertEqual(len(frames), 2)
        self.assertEqual(evidence['aliases']['arrow'], 'left_ptr')
        self.assertEqual(evidence['alias_storage']['arrow'], 'identical binary')
        self.assertEqual(set(evidence['files']), set(frames))
        self.assertEqual(evidence['checked_cursor_files'], len(REQUIRED) + 1)

    def test_rgba_unpremultiplies_loaded_pixels(self):
        frame = Decoder().decode(filename=self.cursors / 'left_ptr')[0]
        self.assertEqual(rgba(frame).getpixel((1, 0)), (128, 64, 32, 128))

    def test_native_selected_size_decoder_filters_animation_frames(self):
        frames = Decoder().decode(filename=self.cursors / 'wait', size=32)
        self.assertEqual([frame['size'] for frame in frames], [32, 32])
        self.assertEqual([frame['delay_ms'] for frame in frames], [90, 90])

    def test_invalid_hotspot_is_rejected_before_native_decoder(self):
        (self.cursors / 'left_ptr').write_bytes(fixture(bad_hotspot=True))
        with self.assertRaises(AssertionError):
            inspect_theme(self.theme)

    def test_alias_escape_is_rejected(self):
        outside = self.theme.parent / 'outside'
        outside.write_bytes(fixture())
        (self.cursors / 'default').unlink()
        (self.cursors / 'default').symlink_to(outside)
        with self.assertRaisesRegex(AssertionError, 'escapes theme'):
            inspect_theme(self.theme)

    def test_truncated_binary_is_rejected(self):
        (self.cursors / 'left_ptr').write_bytes(fixture()[:-4])
        with self.assertRaises(AssertionError):
            inspect_theme(self.theme)

    def test_static_busy_cursor_is_rejected(self):
        (self.cursors / 'wait').write_bytes(fixture())
        with self.assertRaisesRegex(AssertionError, 'Expected animated wait'):
            inspect_theme(self.theme)


class OpticalMetricsTests(unittest.TestCase):
    def frame(self, alpha):
        return {'size': 4, 'width': 4, 'height': 3, 'hotspot': [1, 1],
                'pixels': [a << 24 for a in alpha]}

    def test_strong_bounds_exclude_shadow_but_area_keeps_fractional_coverage(self):
        metrics = optical_metrics(self.frame([127, 0, 0, 0, 0, 128, 255, 0, 0, 0, 0, 1]))
        self.assertEqual(metrics['bounds'], [1, 1, 3, 2])
        self.assertEqual(metrics['alpha_nonzero_bounds'], [0, 0, 4, 3])
        self.assertEqual(metrics['strong_margins'], [1, 1, 1, 1])
        self.assertEqual(metrics['width_over_height'], 2.0)
        self.assertEqual(metrics['strong_pixels'], 2)
        self.assertEqual(metrics['opaque_pixels'], 1)
        self.assertEqual(metrics['antialiased_pixels'], 3)
        self.assertAlmostEqual(metrics['ink_area_px2'], 511 / 255, places=6)

    def test_transparent_cursor_has_empty_bounds_and_no_aspect_ratio(self):
        metrics = optical_metrics(self.frame([0] * 12))
        self.assertIsNone(metrics['bounds'])
        self.assertIsNone(metrics['alpha_nonzero_bounds'])
        self.assertIsNone(metrics['width_over_height'])
        self.assertEqual(metrics['width'], 0)
        self.assertEqual(metrics['height'], 0)
        self.assertEqual(metrics['ink_area_px2'], 0)

    def test_threshold_boundary_is_inclusive_and_invalid_threshold_rejected(self):
        frame = self.frame([127, 0, 0, 0, 0, 128, 255, 0, 0, 0, 0, 0])
        self.assertEqual(optical_metrics(frame, 127)['bounds'], [0, 0, 3, 2])
        with self.assertRaises(ValueError):
            optical_metrics(frame, 0)


if __name__ == '__main__':
    unittest.main()
