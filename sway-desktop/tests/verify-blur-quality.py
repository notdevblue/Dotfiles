#!/usr/bin/env python3
"""Compare real Kitty backdrop quality against the installed SwayFX reference.

Usage: verify-blur-quality.py SWAYFX_BINARY VULKAN_SWAY_BINARY ARTIFACT_DIR
       verify-blur-quality.py --target-only VULKAN_SWAY_BINARY ARTIFACT_DIR
The reference uses the original two-pass/radius-three kernel. All surfaces are
private headless native-resolution 1280x800 outputs; no user content is captured.
Profiles are normalized because GLES and HDR Vulkan blend in different spaces.
"""
import glob
import glob
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont
from statistics import pstdev

WIDTH, HEIGHT = 1280, 800


def wait_for(probe):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if result := probe():
            return result
        time.sleep(.08)
    raise TimeoutError('Private quality capture timed out')


def nodes(tree):
    yield tree
    for child in tree.get('nodes', []) + tree.get('floating_nodes', []):
        yield from nodes(child)


def stop(child):
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=4)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=4)


def create_pattern(destination):
    image = Image.new('RGB', (WIDTH, HEIGHT), '#0c101c')
    draw = ImageDraw.Draw(image)
    # Fine periodic structures expose an underfiltered blit immediately.
    for y in range(80, 400):
        for x in range(80, 640):
            value = 235 if (x // 4 + y // 4) % 2 else 20
            image.putpixel((x, y), (value, value, value))
    font_path = subprocess.check_output(['fc-match', 'Ubuntu Mono:style=Bold', '-f', '%{file}'], text=True).strip()
    font = ImageFont.truetype(font_path, 11)
    for row, y in enumerate(range(80, 400, 12)):
        text = ''.join(' .,:;+*%#@'[(column * 7 + row * 3) % 10] for column in range(105))
        draw.text((640, y), text, font=font, fill='#aec8ce', stroke_width=0)
    # Isolated bright lines give an impulse response and anisotropy check.
    draw.rectangle((80, 400, 639, 719), fill='#202020')
    draw.line((320, 430, 320, 690), fill='#e0e0e0', width=1)
    draw.line((120, 560, 590, 560), fill='#e0e0e0', width=1)
    # A broad vertical step measures width without relying on RGB matching.
    draw.rectangle((640, 400, 919, 719), fill='#202020')
    draw.rectangle((920, 400, 1199, 719), fill='#e0e0e0')
    image.save(destination)


def capture(binary, renderer, label, artifact_dir, neutral=False):
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sway-blur-quality-') as directory:
        root = Path(directory)
        home, runtime = root / 'home', root / 'runtime'
        home.mkdir(mode=0o700);runtime.mkdir(mode=0o700)
        pattern = artifact_dir / 'pattern.png'
        create_pattern(pattern)
        env = dict(PATH='/usr/bin:/bin', HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
                   XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
                   XDG_DATA_HOME=str(home / '.local/share'), XDG_DATA_DIRS='/usr/local/share:/usr/share',
                   LC_ALL='C.UTF-8', WLR_BACKENDS='headless', WLR_HEADLESS_OUTPUTS='1',
                   WLR_RENDERER=renderer, WLR_RENDER_DRM_DEVICE=(os.environ.get('SWAY_TEST_RENDER_NODE') or
                       os.environ.get('WLR_RENDER_DRM_DEVICE') or
                       next(path for path in sorted(glob.glob('/dev/dri/renderD*'))
                            if os.access(path, os.R_OK | os.W_OK))),
                   WLR_LIBINPUT_NO_DEVICES='1', WLR_SCENE_DEBUG_DAMAGE='rerender',
                   WAYLAND_DISPLAY='no-live-display', NO_AT_BRIDGE='1',
                   DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'no-dbus'))
        blur_command = 'blur' if renderer == 'gles2' else 'background_blur'
        extra = ''
        if renderer == 'gles2':
            extra = 'blur disable\nblur_passes 2\nblur_radius 3\n'
            if neutral:
                extra += 'blur_noise 0\nblur_brightness 1\nblur_contrast 1\nblur_saturation 1\n'
        config = root / 'sway.conf'
        config.write_text('xwayland disable\nseat seat0 fallback true\n'
                          f'output HEADLESS-1 mode {WIDTH}x{HEIGHT} position 0 0\n'
                          f'output * bg {pattern} stretch\n' + extra +
                          'for_window [app_id="^kitty$"] floating enable, border none, '
                          f'resize set 1120 640, move position 80 80, {blur_command} enable\n')
        children = []
        log = (artifact_dir / f'{label}.log').open('w+')
        def launch(command):
            child = subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
            children.append(child)
            return child
        try:
            compositor = launch([str(binary), '--unsupported-gpu', '-c', str(config), '-d'])
            def ready():
                if compositor.poll() is not None:
                    raise RuntimeError('Private compositor exited; inspect ' + str(log.name))
                ipc = list(runtime.glob('sway-ipc.*.sock'))
                displays = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
                if ipc and displays:
                    env.update(SWAYSOCK=str(ipc[0]), WAYLAND_DISPLAY=displays[0].name)
                    return True
            wait_for(ready)
            def ipc(command=None, kind=None):
                args = ['swaymsg', '-r'] + (['-t', kind] if kind else ['--', command])
                data = json.loads(subprocess.check_output(args, env=env, text=True, timeout=5))
                if not kind:
                    assert all(result.get('success') for result in data), data
                return data
            kitty = launch(['/usr/bin/kitty', '--config', 'NONE', '--app-id', 'kitty',
                            '--override', 'background_opacity=0.80', '--override', 'background=#1E191F',
                            '--override', 'foreground=#E1DBD1', '--override', 'font_family=Ubuntu Mono',
                            '--override', 'font_size=14', '--override', 'window_padding_width=0',
                            '--override', 'enable_audio_bell=no', '--override', 'cursor_blink_interval=0',
                            '/usr/bin/python3', '-c',
                            'import time;print("Foreground: ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789",flush=True);time.sleep(30)'])
            wait_for(lambda: any(node.get('app_id') == 'kitty' for node in nodes(ipc(kind='get_tree'))))
            time.sleep(.8)
            for mode in ('off', 'on'):
                ipc(f'[app_id="^kitty$"] {blur_command} ' + ('enable' if mode == 'on' else 'disable'))
                time.sleep(.3)
                subprocess.run(['grim', '-o', 'HEADLESS-1', str(artifact_dir / f'{label}-{mode}.png')],
                               check=True, env=env, capture_output=True, timeout=5)
            assert kitty.poll() is None
        finally:
            for child in reversed(children):
                stop(child)
            log.close()
    return analyze(label, artifact_dir)


def to_luminance(path):
    return Image.open(path).convert('L')


def analyze(label, root):
    root = Path(root)
    off, on = [to_luminance(root / f'{label}-{mode}.png') for mode in ('off', 'on')]
    result = {'label': label, 'regions': {}}
    for name, box in {'checker4': (120, 160, 600, 360), 'ascii': (680, 160, 1160, 360)}.items():
        raw, soft = off.crop(box), on.crop(box)
        # Neighbor differences expose visible grains and periodic edges.
        def gradient(image):
            width, height = image.size
            data = list(image.tobytes())
            dx = [(data[y * width + x + 1] - data[y * width + x]) ** 2
                  for y in range(height) for x in range(width - 1)]
            dy = [(data[(y + 1) * width + x] - data[y * width + x]) ** 2
                  for y in range(height - 1) for x in range(width)]
            return math.sqrt((sum(dx) / len(dx) + sum(dy) / len(dy)) / 2)
        raw_std, soft_std = pstdev(raw.tobytes()), pstdev(soft.tobytes())
        result['regions'][name] = {'off_std': raw_std, 'on_std': soft_std,
                                  'std_ratio': soft_std / raw_std,
                                  'gradient_rms': gradient(soft), 'off_gradient_rms': gradient(raw)}
    profile = [sum(on.getpixel((x, y)) for y in range(460, 660)) / 200 for x in range(840, 1000)]
    low, high = sum(profile[:20]) / 20, sum(profile[-20:]) / 20
    normalized = [max(0, min(1, (value - low) / (high - low))) for value in profile]
    def position(level):
        above = [i for i, value in enumerate(normalized) if value >= level]
        if not len(above):
            raise AssertionError('Edge profile does not cross ' + str(level))
        i = above[0]
        return float(i if i == 0 else i - 1 + (level - normalized[i - 1]) /
                     (normalized[i] - normalized[i - 1]))
    width = position(.9) - position(.1)
    result['edge_10_90_px'] = width
    result['gaussian_equivalent_sigma_px'] = width / 2.5631031311
    result['edge_profile'] = normalized
    result['edge_baseline'] = [low, high]
    (root / f'{label}-metrics.json').write_text(json.dumps(result, indent=2) + '\n')
    # Full-size terminal crops: no thumbnail smoothing to hide alias patterns.
    for mode in ('off', 'on'):
        Image.open(root / f'{label}-{mode}.png').crop((80, 80, 1200, 720)).save(root / f'{label}-{mode}-crop.png')
    return result


def compare(reference, candidate, output):
    relative_width = candidate['edge_10_90_px'] / reference['edge_10_90_px']
    differences = [(a - b) ** 2 for a, b in zip(candidate['edge_profile'], reference['edge_profile'])]
    profile_rmse = math.sqrt(sum(differences) / len(differences))
    report = {'reference': reference, 'candidate': candidate,
              'edge_width_ratio': relative_width, 'normalized_edge_rmse': profile_rmse}
    (Path(output) / 'quality-comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('reference', 'candidate')}, indent=2))
    assert .8 <= relative_width <= 1.25, ('Blur spread differs from original SwayFX', relative_width)
    assert profile_rmse <= .07, ('Normalized edge response differs', profile_rmse)
    for name in ('checker4', 'ascii'):
        ref = reference['regions'][name]
        cand = candidate['regions'][name]
        assert cand['std_ratio'] <= max(.04, ref['std_ratio'] * 2), (name, ref, cand)
        assert cand['gradient_rms'] <= max(.5, ref['gradient_rms'] * 2), (name, ref, cand)
    return report


def assert_target(candidate, output):
    # Measured original SwayFX 0.6 / SceneFX 0.5, passes=2, radius=3,
    # real Kitty opacity=.80, 1280x800. Original edge width is 16.20px;
    # checker/ASCII residual ratios .00272/.06133 and gradients .0713/.2311.
    # Leave quantization and linear-vs-gamma compositing room, while rejecting
    # the previous bilinear-blit implementation (width4.475px, grid RMS4.14).
    limits = {'edge_10_90_px': [12.96, 20.25],
              'checker4_std_ratio': .04, 'checker4_gradient_rms': .5,
              'ascii_std_ratio': .1227, 'ascii_gradient_rms': .5}
    report = {'candidate': candidate, 'reference': 'SwayFX passes2 radius3 Kitty opacity.80',
              'limits': limits}
    (Path(output) / 'quality-target.json').write_text(json.dumps(report, indent=2) + '\n')
    assert limits['edge_10_90_px'][0] <= candidate['edge_10_90_px'] <= limits['edge_10_90_px'][1], candidate
    for name in ('checker4', 'ascii'):
        region = candidate['regions'][name]
        assert region['std_ratio'] <= limits[name + '_std_ratio'], (name, region)
        assert region['gradient_rms'] <= limits[name + '_gradient_rms'], (name, region)
    print(json.dumps({'quality_target_pass': True, 'edge_10_90_px': candidate['edge_10_90_px'],
                      'regions': candidate['regions']}, indent=2))
    return report


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    if sys.argv[1] == '--target-only':
        candidate, output = Path(sys.argv[2]), Path(sys.argv[3])
        cand = capture(candidate.resolve(), 'vulkan', 'vulkan', output)
        assert_target(cand, output)
    else:
        reference, candidate, output = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
        ref = capture(reference.resolve(), 'gles2', 'swayfx-original', output)
        cand = capture(candidate.resolve(), 'vulkan', 'vulkan', output)
        compare(ref, cand, output)


if __name__ == '__main__':
    main()
