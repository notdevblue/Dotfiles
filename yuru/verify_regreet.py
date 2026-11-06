#!/usr/bin/env python3
"""Exercise the installed ReGreet in private Sway/DBus sessions using demo auth only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from PIL import Image, ImageChops

from verify_ascii_wallpaper import wallpaper_environment, wait_for
from verify_native import stop_group

ROOT = Path(__file__).resolve().parent


def run_once(binary, source, background_path, iteration):
    with tempfile.TemporaryDirectory(prefix='yuru-regreet-') as directory:
        temporary = Path(directory)
        env = wallpaper_environment(temporary)
        env.update(WLR_HEADLESS_OUTPUTS='2', GSK_RENDERER='cairo', GTK_A11Y='none',
                   GDK_DEBUG='no-portals', GIO_USE_VFS='local')
        config = temporary / 'sway.conf'
        config.write_text('xwayland disable\nseat seat0 fallback true\n'
                          'output HEADLESS-1 mode 3440x1440 disable\n'
                          'output HEADLESS-2 mode 1440x3440 position 0 0\n'
                          'focus output HEADLESS-2\n')
        # Only relocate the installed wallpaper. Do not consult or modify greetd's
        # authentication socket, logs, session state or the live desktop runtime.
        regreet_config = temporary / 'regreet.toml'
        text = (source / 'regreet.toml').read_text()
        text = text.replace('/etc/greetd/background.png', str(background_path))
        regreet_config.write_text(text)
        background = Image.open(background_path).convert('RGB')
        assert background.size == (1440, 3440), background.size
        children = []
        with (temporary / 'process.log').open('w+') as log:
            demo_log = temporary / 'demo.log'
            try:
                compositor = subprocess.Popen(
                    ['dbus-run-session', '--', 'sh', '-c',
                     'printf "%s" "$DBUS_SESSION_BUS_ADDRESS" > "$1"; exec sway -c "$2"',
                     'private-regreet', str(temporary / 'bus-address'), str(config)],
                    env=env, stdout=log, stderr=log, start_new_session=True)
                children.append(compositor)
                runtime = Path(env['XDG_RUNTIME_DIR'])

                def ready():
                    ipc = list(runtime.glob('sway-ipc.*.sock'))
                    displays = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
                    address = temporary / 'bus-address'
                    if not ipc or not displays or not address.exists():
                        return False
                    env.update(SWAYSOCK=str(ipc[0]), WAYLAND_DISPLAY=displays[0].name,
                               DBUS_SESSION_BUS_ADDRESS=address.read_text())
                    return subprocess.run(['swaymsg', '-t', 'get_outputs'], env=env,
                                          capture_output=True, timeout=2).returncode == 0

                wait_for(ready)
                # Keep one virtual keyboard attached, as a physical keyboard
                # would be. Removing the last keyboard resets GTK key focus.
                keyboard = subprocess.Popen(['wtype', '-s', '60000'], env=env,
                                            stdout=log, stderr=log, start_new_session=True)
                children.append(keyboard)
                time.sleep(.2)
                process = subprocess.Popen(
                    [str(binary), '--demo', '-c', str(regreet_config), '-s',
                     str(source / 'regreet.css'), '-l', str(demo_log)],
                    env=env, stdout=log, stderr=log, start_new_session=True)
                children.append(process)

                def messages():
                    return demo_log.read_text() if demo_log.exists() else ''

                def capture():
                    target = temporary / 'portrait.png'
                    subprocess.run(['grim', '-o', 'HEADLESS-2', str(target)], env=env,
                                   check=True, capture_output=True, timeout=5)
                    return Image.open(target).convert('RGB')

                def keys(*args):
                    subprocess.run(['wtype', *args], env=env, check=True,
                                   capture_output=True, timeout=5)
                    time.sleep(.2)

                wait_for(lambda: 'Run as demo' in messages())
                time.sleep(.7)
                if 'One-Time Password:' not in messages():
                    keys('-k', 'Return')
                wait_for(lambda: 'One-Time Password:' in messages())
                time.sleep(.3)
                before = capture()
                bounds = ImageChops.difference(before, background).crop((0, 0, 1440, 2000)).getbbox()
                assert bounds is not None, 'Login panel is missing'
                x1, y1, x2, y2 = bounds
                assert 420 <= x1 <= 500 and 940 <= x2 <= 1020, bounds
                assert 1250 <= y1 <= 1400 and 1480 <= y2 <= 1620, bounds
                for box in [(0, 0, 1440, 1000), (0, 2000, 1440, 3300)]:
                    assert ImageChops.difference(before.crop(box), background.crop(box)).getbbox() is None
                keys('wrong-demo-code')
                typed = capture()
                assert ImageChops.difference(before, typed).crop((x1, y1 + 100, x2, y2)).getbbox(), 'Entry did not accept keyboard input'
                keys('-k', 'Return')
                wait_for(lambda: 'AUTH_ERR' in messages())
                error = capture()
                assert ImageChops.difference(before, error).getbbox(), 'Demo error did not change the visible UI'
                # ReGreet cancels a rejected authentication automatically and
                # focuses Login again. Retry from that selection screen.
                assert 'Cancelling greetd session' in messages().split('AUTH_ERR', 1)[1]
                keys('-k', 'Return')
                wait_for(lambda: messages().count('One-Time Password:') >= 2)
                keys('0248', '-k', 'Return')
                wait_for(lambda: 'secret auth input: Password:' in messages())
                keys('-M', 'ctrl', 'a', '-m', 'ctrl', '-k', 'BackSpace')
                time.sleep(5)  # Let the initial session-selection notification clear.
                final = capture()
                keys('-M', 'ctrl', 'a', '-m', 'ctrl', 'pass', '-k', 'Return')
                wait_for(lambda: 'Session successfully started' in messages())
                wait_for(lambda: process.poll() is not None)
                assert process.returncode == 0, process.returncode
                assert 'Saving cache to disk' not in messages(), 'Demo wrote real session state'
                log.flush(); log.seek(0)
                diagnostics = log.read()
                assert 'Theme parsing error' not in diagnostics, diagnostics
                assert 'panicked' not in diagnostics, diagnostics
                return {'iteration': iteration, 'panel_bbox': bounds,
                        'native_sky_and_character_pixels_match_gtklock': True,
                        'private_keyboard_input_changes_entry': True,
                        'demo_error_visible_cancel_and_retry_succeed': True,
                        'demo_otp_and_password_flow_completed': True,
                        'cache_save_skipped': True}, final
            except BaseException:
                log.flush(); log.seek(0)
                print(log.read()[-5000:])
                print(messages()[-5000:])
                raise
            finally:
                for child in reversed(children):
                    stop_group(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path('/usr/local/lib/regreet-yuru/regreet'))
    parser.add_argument('--source', type=Path, default=Path('/etc/greetd'))
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'verification')
    args = parser.parse_args()
    binary, source = args.binary.resolve(), args.source.resolve()
    background_path = source / 'background.png'
    if not background_path.exists():
        background_path = source.parent / 'config/gtklock/background.png'
    files = ['regreet.toml', 'regreet.css']
    report = {'date': time.strftime('%Y-%m-%d'),
              'binary': str(binary),
              'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'scope': 'two fresh private CPU Sway/DBus sessions; ReGreet demo authentication',
              'sha256': {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in files},
              'background_sha256': hashlib.sha256(background_path.read_bytes()).hexdigest(),
              'runs': [],
              'not_tested': ['live greetd/PAM authentication', 'logout/login', 'OS reboot',
                             'physical monitor reconnect', 'physical OLED power state']}
    for iteration in (1, 2):
        run, screenshot = run_once(binary, source, background_path, iteration)
        report['runs'].append(run)
    # Publish artifacts only after both complete native runs pass.
    args.output_dir.mkdir(parents=True, exist_ok=True)
    screenshot.save(args.output_dir / 'regreet-msi.png')
    (args.output_dir / 'regreet.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
