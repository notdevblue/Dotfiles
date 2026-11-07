#!/usr/bin/env python3
"""Exercise scoped backdrop blur in two fresh private Sway/Vulkan sessions.

Usage: verify-background-blur.py SWAY_SOURCE_ROOT
No user session, configuration or physical display is modified. Requires the
local HDR build and its wlroots backdrop-blur extension, GTK3, Pillow and Kitty.
"""
import glob
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageStat


FIXTURE = '''import gi,sys
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk,GLib
GLib.set_prgname(sys.argv[1])
Gtk.init([])
w=Gtk.Window(title='backdrop blur fixture')
w.set_app_paintable(True)
w.set_visual(w.get_screen().get_rgba_visual())
w.set_default_size(320,200)
def draw(widget,ctx):
    ctx.set_operator(1)
    ctx.set_source_rgba(.03,.04,.07,.45);ctx.paint()
    ctx.set_source_rgba(1,1,1,1);ctx.rectangle(16,16,32,16);ctx.fill()
    return False
w.connect('draw',draw)
w.connect('destroy',Gtk.main_quit)
w.show_all();Gtk.main()
'''


def wait_for(probe, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = probe()
        if result:
            return result
        time.sleep(.08)
    raise TimeoutError('Private background blur verification timed out')


def nodes(node):
    yield node
    for child in node.get('nodes', []) + node.get('floating_nodes', []):
        yield from nodes(child)


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def run_once(source, iteration):
    with tempfile.TemporaryDirectory(prefix='sway-background-blur-') as tmp:
        root = Path(tmp)
        home, runtime = root / 'home', root / 'runtime'
        home.mkdir(mode=0o700)
        runtime.mkdir(mode=0o700)
        render_node = (os.environ.get('SWAY_TEST_RENDER_NODE') or
                       os.environ.get('WLR_RENDER_DRM_DEVICE') or
                       next(p for p in sorted(glob.glob('/dev/dri/renderD*'))
                            if os.access(p, os.R_OK | os.W_OK)))
        env = dict(PATH='/usr/bin:/bin', HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
                   XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'),
                   XDG_DATA_HOME=str(home / '.local/share'), XDG_DATA_DIRS='/usr/local/share:/usr/share',
                   LC_ALL='C.UTF-8', WLR_BACKENDS='headless', WLR_HEADLESS_OUTPUTS='2',
                   WLR_RENDERER='vulkan', WLR_RENDER_DRM_DEVICE=render_node,
                   WLR_LIBINPUT_NO_DEVICES='1', WLR_SCENE_DEBUG_DAMAGE='none',
                   GDK_BACKEND='wayland', WAYLAND_DISPLAY='no-live-display', NO_AT_BRIDGE='1',
                   DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'no-dbus'))
        for name in ('VK_INSTANCE_LAYERS', 'VK_LAYER_ENABLES'):
            if name in os.environ:
                env[name] = os.environ[name]
        artifact_dir = os.environ.get('SWAY_BLUR_ARTIFACT_DIR')
        if artifact_dir:
            artifact_dir = Path(artifact_dir)
            artifact_dir.mkdir(parents=True, exist_ok=True)
        pattern = Image.new('RGB', (64, 64))
        for y in range(64):
            for x in range(64):
                value = 235 if (x // 4 + y // 4) % 2 else 20
                pattern.putpixel((x, y), (value, value, value))
        wallpaper = root / 'checkerboard.png'
        pattern.save(wallpaper)
        config = root / 'sway.conf'
        config.write_text('xwayland disable\nseat seat0 fallback true\n'
                          'output HEADLESS-1 mode 800x600 position 0 0\n'
                          'output HEADLESS-2 mode 800x600 transform 270 scale 1.25 position 800 0\n'
                          f'output * bg {wallpaper} tile\n'
                          'for_window [app_id="^kitty$"] floating enable, border none, '
                          'resize set 320 200, move position 80 80, background_blur enable\n'
                          'for_window [app_id="^blur-control$"] floating enable, border none, '
                          'resize set 320 200, move position 80 320\n')
        children = []
        log = (root / 'session.log').open('w+')
        def launch(command):
            child = subprocess.Popen(command, env=env, stdout=log, stderr=log,
                                     start_new_session=True)
            children.append(child)
            return child
        try:
            compositor = launch([str(source / 'build/sway/sway'), '-c', str(config), '-d', '-D', 'txn-timeout=5000'])
            def ready():
                ipc = list(runtime.glob('sway-ipc.*.sock'))
                displays = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
                if compositor.poll() is not None:
                    raise RuntimeError('Private Sway exited before becoming ready')
                if not ipc or not displays:
                    return False
                env.update(SWAYSOCK=str(ipc[0]), WAYLAND_DISPLAY=displays[0].name)
                return True
            wait_for(ready)
            def ipc(command=None, kind=None, success=True):
                args = ['swaymsg', '-r']
                args += ['-t', kind] if kind else ['--', command]
                result = subprocess.run(args, env=env, capture_output=True, text=True,
                                        timeout=5, check=success)
                data = json.loads(result.stdout)
                if not kind:
                    assert all(item.get('success') is success for item in data), data
                return data
            def view(app_id):
                return next((n for n in nodes(ipc(kind='get_tree')) if n.get('app_id') == app_id), None)
            def capture(output):
                destination = root / 'capture.png'
                subprocess.run(['grim', '-o', output, str(destination)], env=env,
                               check=True, capture_output=True, timeout=5)
                return Image.open(destination).convert('RGB')
            def crop(image, node, box, output):
                origin = output['rect']
                scale = output['scale']
                rect = node['rect']
                window = node['window_rect']
                x = rect['x'] + window['x'] - origin['x']
                y = rect['y'] + window['y'] - origin['y']
                return image.crop(tuple(round(v * scale) for v in
                    (x + box[0], y + box[1], x + box[2], y + box[3])))
            fixture = launch(['/usr/bin/python3', '-c', FIXTURE, 'kitty'])
            wait_for(lambda: view('kitty'))
            wait_for(lambda: view('kitty')['background_blur'])
            control = launch(['/usr/bin/python3', '-c', FIXTURE, 'blur-control'])
            wait_for(lambda: view('blur-control'))
            assert view('blur-control')['background_blur'] is False
            ipc('[app_id="^kitty$"] background_blur banana', success=False)
            ipc('[app_id="^kitty$"] background_blur enable extra', success=False)
            results = []
            for output_name in ('HEADLESS-1', 'HEADLESS-2'):
                ipc(f'[app_id="^kitty$"] move to output {output_name}')
                ipc('[app_id="^kitty$"] move position 80 80')
                ipc(f'[app_id="^blur-control$"] move to output {output_name}')
                ipc('[app_id="^blur-control$"] move position 80 320')
                time.sleep(.5)
                output = next(o for o in ipc(kind='get_outputs') if o['name'] == output_name)
                ipc('[app_id="^kitty$"] background_blur disable')
                time.sleep(.2)
                unblurred = capture(output_name)
                ipc('[app_id="^kitty$"] background_blur enable')
                time.sleep(.2)
                blurred = capture(output_name)
                if artifact_dir:
                    unblurred.save(artifact_dir / f'{iteration}-{output_name}-plain.png')
                    blurred.save(artifact_dir / f'{iteration}-{output_name}-blur.png')
                node = view('kitty')
                plain = crop(unblurred, node, (80, 60, 240, 160), output)
                soft = crop(blurred, node, (80, 60, 240, 160), output)
                plain_std, soft_std = ImageStat.Stat(plain).stddev[0], ImageStat.Stat(soft).stddev[0]
                assert plain_std > 25, (output_name, plain_std)
                assert soft_std < plain_std * .45, (output_name, plain_std, soft_std)
                # Opaque application content must stay sharp and retain its white value.
                before_marker = crop(unblurred, node, (22, 20, 40, 28), output)
                after_marker = crop(blurred, node, (22, 20, 40, 28), output)
                assert min(ImageStat.Stat(after_marker).mean) > 245
                assert before_marker.tobytes() == after_marker.tobytes()
                # Enabling one view must leave the unrelated translucent app unblurred.
                control_crop = crop(blurred, view('blur-control'), (80, 60, 240, 160), output)
                assert ImageStat.Stat(control_crop).stddev[0] > 25
                # Trigger damage underneath the view without a full repaint override.
                ipc('output * bg #000000 solid_color')
                time.sleep(.25)
                dark = capture(output_name)
                assert ImageStat.Stat(crop(dark, node, (80, 60, 240, 160), output)).mean[0] < 30
                ipc('reload')
                time.sleep(.5)
                assert view('kitty')['background_blur'] is True
                assert view('blur-control')['background_blur'] is False
                restored = capture(output_name)
                assert ImageStat.Stat(crop(restored, node, (80, 60, 240, 160), output)).stddev[0] < plain_std * .45
                ipc('[app_id="^kitty$"] fullscreen enable')
                time.sleep(.2)
                assert view('kitty')['background_blur'] is True
                assert view('kitty')['fullscreen_mode'] == 1
                ipc('[app_id="^kitty$"] fullscreen disable')
                time.sleep(.2)
                results.append({'output': output_name, 'scale': output['scale'],
                                'transform': output['transform'], 'plain_stddev': plain_std,
                                'blurred_stddev': soft_std})
            # A stalled configure keeps the transaction snapshot visible. Runtime
            # toggles must change its main buffer as well as the hidden live tree.
            os.kill(fixture.pid, signal.SIGSTOP)
            try:
                ipc('[app_id="^kitty$"] resize set 340 220')
                time.sleep(.12)
                ipc('[app_id="^kitty$"] background_blur disable')
                time.sleep(.12)
                saved_plain = capture('HEADLESS-2')
                ipc('[app_id="^kitty$"] background_blur enable')
                time.sleep(.12)
                saved_blur = capture('HEADLESS-2')
                snapshot_node = view('kitty')
                output = next(o for o in ipc(kind='get_outputs') if o['name'] == 'HEADLESS-2')
                saved_plain_std = ImageStat.Stat(crop(saved_plain, snapshot_node, (80, 60, 240, 160), output)).stddev[0]
                saved_blur_std = ImageStat.Stat(crop(saved_blur, snapshot_node, (80, 60, 240, 160), output)).stddev[0]
                assert saved_plain_std > 25, saved_plain_std
                assert saved_blur_std < saved_plain_std * .45, (saved_plain_std, saved_blur_std)
            finally:
                os.kill(fixture.pid, signal.SIGCONT)
            time.sleep(.2)
            stop(fixture)
            stop(control)
            wait_for(lambda: view('kitty') is None and view('blur-control') is None)
            # A real Kitty instance must also match the stored rule after fixture removal.
            kitty = launch(['/usr/bin/kitty', '--config', 'NONE', '--app-id', 'kitty',
                            '--override', 'background_opacity=0.45', '--override', 'font_size=12',
                            '--override', 'enable_audio_bell=no', '/usr/bin/sleep', '20'])
            wait_for(lambda: view('kitty'))
            assert view('kitty')['background_blur'] is True
            output = next(o for o in ipc(kind='get_outputs') if o['name'] == 'HEADLESS-2')
            ipc('[app_id="^kitty$"] move to output HEADLESS-2')
            ipc('[app_id="^kitty$"] move position 80 80')
            time.sleep(.3)
            ipc('[app_id="^kitty$"] background_blur disable')
            assert view('kitty')['background_blur'] is False
            time.sleep(.2)
            kitty_plain = capture('HEADLESS-2')
            ipc('[app_id="^kitty$"] background_blur enable')
            assert view('kitty')['background_blur'] is True
            time.sleep(.2)
            kitty_blur = capture('HEADLESS-2')
            node = view('kitty')
            kitty_plain_std = ImageStat.Stat(crop(kitty_plain, node, (80, 60, 240, 160), output)).stddev[0]
            kitty_blur_std = ImageStat.Stat(crop(kitty_blur, node, (80, 60, 240, 160), output)).stddev[0]
            assert kitty_plain_std > 25, kitty_plain_std
            assert kitty_blur_std < kitty_plain_std * .45, (kitty_plain_std, kitty_blur_std)
            if artifact_dir:
                kitty_plain.save(artifact_dir / f'{iteration}-kitty-plain.png')
                kitty_blur.save(artifact_dir / f'{iteration}-kitty-blur.png')
            assert kitty.poll() is None
            log.flush();log.seek(0)
            session_log = log.read()
            if artifact_dir:
                (artifact_dir / f'{iteration}-session.log').write_text(session_log)
            assert not any(token in session_log for token in
                           ('Validation Error', 'SYNC-HAZARD', 'VUID-')), session_log[-12000:]
            print(json.dumps({'iteration': iteration, 'outputs': results,
                              'actual_kitty_rule_and_runtime_toggle': True,
                              'actual_kitty_stddev': [kitty_plain_std, kitty_blur_std],
                              'foreground_preserved': True, 'unrelated_app_preserved': True,
                              'reload_and_fullscreen': True, 'partial_damage': True,
                              'stalled_transaction_toggle': [saved_plain_std, saved_blur_std]}))
        except BaseException:
            log.flush();log.seek(0)
            print(log.read()[-10000:])
            raise
        finally:
            for child in reversed(children):
                stop(child)
            log.close()


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    source = Path(sys.argv[1]).resolve()
    for iteration in (1, 2):
        run_once(source, iteration)


if __name__ == '__main__':
    main()
