#!/usr/bin/env python3
"""Neural-upscale character RGB 2x and preserve alpha separately.

Use the official portable waifu2x-ncnn-vulkan 20250915 release. Its native
RGBA Vulkan path produced an incomplete alpha plane on this host, so keep
alpha outside inference and resize only the coverage mask with bicubic.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def upscale(binary, source, output):
    binary, source, output = map(lambda path: Path(path).resolve(), (binary, source, output))
    model = binary.parent / 'models-cunet'
    with tempfile.TemporaryDirectory(prefix='yuru-upscale-') as temporary:
        work = Path(temporary)
        rgb, rgb2, alpha = [work / name for name in ('rgb.png', 'rgb2.png', 'alpha.png')]
        subprocess.run(['magick', str(source), '-alpha', 'off', 'PNG24:' + str(rgb)], check=True)
        subprocess.run([str(binary), '-i', str(rgb), '-o', str(rgb2), '-n', '-1', '-s', '2',
                        '-m', str(model), '-g', '0', '-t', '256', '-j', '1:1:1'], check=True)
        subprocess.run(['magick', str(source), '-alpha', 'extract', '-filter', 'Cubic',
                        '-resize', '200%', str(alpha)], check=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        fd, staged = tempfile.mkstemp(prefix='.' + output.name, suffix='.png', dir=output.parent)
        os.close(fd)
        try:
            subprocess.run(['magick', str(rgb2), str(alpha), '-alpha', 'off',
                            '-compose', 'CopyOpacity', '-composite', 'PNG32:' + staged], check=True)
            os.chmod(staged, 0o644)
            os.replace(staged, output)
        finally:
            if os.path.exists(staged):
                os.unlink(staged)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path.home() / '.local/lib/yuru-upscale/waifu2x-ncnn-vulkan-20250915-linux/waifu2x-ncnn-vulkan')
    parser.add_argument('--source', type=Path, default=Path(__file__).parent / 'assets/rin-cutout-source.png')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'assets/rin-cutout.png')
    args = parser.parse_args()
    upscale(args.binary, args.source, args.output)
