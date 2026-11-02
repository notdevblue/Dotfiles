#!/usr/bin/env python3
"""Run the installed gtklock in two private Sway sessions; never lock the desktop."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from PIL import Image, ImageChops

from verify_ascii_wallpaper import wallpaper_environment, wait_for
from verify_native import stop_group

ROOT = Path(__file__).resolve().parent


def run_once(source, iteration):
    with tempfile.TemporaryDirectory(prefix='yuru-gtklock-') as directory:
        temporary = Path(directory)
        env = wallpaper_environment(temporary)
        env['WLR_HEADLESS_OUTPUTS'] = '2'
        config = temporary / 'sway.conf'
        config.write_text('xwayland disable\nseat seat0 fallback true\n'
                          'output HEADLESS-1 mode 3440x1440 position 0 0\n'
                          'output HEADLESS-2 mode 1440x3440 position 3440 0\n')
        home = Path(env['HOME'])
        lock = home / '.config/gtklock'
        lock.mkdir(parents=True)
        # Headless wlroots assigns HEADLESS names. Change selectors only; retain
        # actual installed styles, relative artwork URI and user-CSS priority.
        css = (source / 'gtklock/style.css').read_text().replace('DP-5', 'HEADLESS-2')
        (lock / 'style.css').write_text(css)
        shutil.copy2(source / 'gtklock/background.png', lock / 'background.png')
        shutil.copy2(source / 'gtklock/yuru-output-names.so', lock / 'yuru-output-names.so')
        gtk = home / '.config/gtk-3.0'
        gtk.mkdir()
        (gtk / 'gtk.css').write_text((source / 'gtk-3.0/yuru.css').read_text()
                                    .replace('DP-6', 'HEADLESS-1').replace('DP-5', 'HEADLESS-2'))
        marker = temporary / 'locked'
        (lock / 'config.ini').write_text('[main]\ngtk-theme=Adwaita-dark\n'
                                       'monitor-priority=HEADLESS-2;\nfollow-focus=false\n'
                                       f'modules={lock}/yuru-output-names.so;\n'
                                       'time-format=%H:%M\ndate-format=%Y-%m-%d %a\n'
                                       f'lock-command=touch {marker}\n')
        children = []
        with (temporary / 'process.log').open('w+') as log:
            try:
                compositor = subprocess.Popen(['sway', '-c', str(config)], env=env,
                                              stdout=log, stderr=log, start_new_session=True)
                children.append(compositor)
                runtime = Path(env['XDG_RUNTIME_DIR'])

                def ready():
                    ipc = list(runtime.glob('sway-ipc.*.sock'))
                    displays = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
                    if not ipc or not displays:
                        return False
                    env.update(SWAYSOCK=str(ipc[0]), WAYLAND_DISPLAY=displays[0].name)
                    result = subprocess.run(['swaymsg', '-t', 'get_outputs'], env=env,
                                            capture_output=True, timeout=2)
                    return result.returncode == 0

                wait_for(ready)
                process = subprocess.Popen(['gtklock'], env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                children.append(process)
                wait_for(marker.exists)
                time.sleep(.7)

                def capture(output):
                    target = temporary / f'{output}.png'
                    subprocess.run(['grim', '-o', output, str(target)], env=env,
                                   check=True, capture_output=True, timeout=5)
                    return Image.open(target).convert('RGB')

                def check_black():
                    image = capture('HEADLESS-1')
                    assert image.getextrema() == ((0, 0),) * 3, image.getextrema()

                check_black()
                before = capture('HEADLESS-2')
                background = Image.open(lock / 'background.png').convert('RGB')
                # Native-sized image must retain both sky and the lower character.
                for box in [(0, 0, 1440, 900), (0, 2000, 1440, 3440)]:
                    assert ImageChops.difference(before.crop(box), background.crop(box)).getbbox() is None
                assert ImageChops.difference(before, background).getbbox() is not None
                # Create a private virtual keyboard. Never submit to PAM or use credentials.
                subprocess.run(['wtype', 'preview'], env=env, check=True,
                               capture_output=True, timeout=5)
                time.sleep(.2)
                check_black()
                assert ImageChops.difference(before, capture('HEADLESS-2')).getbbox() is not None
                subprocess.run(['wtype', '-M', 'ctrl', 'a', '-m', 'ctrl', '-k', 'BackSpace'],
                               env=env, check=True, capture_output=True, timeout=5)
                # Both monitor selectors must also survive new lock surfaces.
                for output in ['HEADLESS-1', 'HEADLESS-2']:
                    for action in ['disable', 'enable']:
                        result = subprocess.run(['swaymsg', '-r', '--', f'output {output} {action}'],
                                                env=env, check=True, capture_output=True,
                                                text=True, timeout=3)
                        assert all(r['success'] for r in json.loads(result.stdout))
                        time.sleep(.35)
                check_black()
                after = capture('HEADLESS-2')
                assert (ImageChops.difference(after, background).getbbox() ==
                        ImageChops.difference(before, background).getbbox()), 'MSI input form lost focus'
                assert ImageChops.difference(after.crop((0, 2000, 1440, 3440)),
                                            background.crop((0, 2000, 1440, 3440))).getbbox() is None
                assert process.poll() is None
                subprocess.run(['wtype', 'after-reconnect'], env=env, check=True,
                               capture_output=True, timeout=5)
                time.sleep(.2)
                check_black()
                if iteration == 2:
                    after.save(ROOT / 'verification/gtklock-msi.png')
                log.flush()
                log.seek(0)
                diagnostics = log.read()
                assert 'Theme parsing error' not in diagnostics, diagnostics
                assert 'Failed to load' not in diagnostics, diagnostics
                return {'iteration': iteration, 'session_lock_acquired': True,
                        'lg_all_pixels_black_before_and_during_typing': True,
                        'msi_native_sky_and_character_match_desktop_still': True,
                        'password_entry_accepts_private_virtual_keyboard': True,
                        'msi_input_form_focus_restored_after_reconnect': True,
                        'both_virtual_outputs_reconnected': True}
            except BaseException:
                log.flush()
                log.seek(0)
                print(log.read()[-5000:])
                raise
            finally:
                for child in reversed(children):
                    stop_group(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path.home() / '.config',
                        help='configuration root, defaults to installed .config')
    args = parser.parse_args()
    files = ['gtklock/style.css', 'gtklock/background.png', 'gtklock/yuru-output-names.so',
             'gtklock/config.ini', 'gtk-3.0/yuru.css']
    report = {'date': time.strftime('%Y-%m-%d'),
              'gtklock_version': subprocess.check_output(['gtklock', '--version'], text=True).strip(),
              'scope': 'installed files in two fresh CPU-only private Sway sessions; selector names remapped',
              'sha256': {name: hashlib.sha256((args.source / name).read_bytes()).hexdigest()
                         for name in files},
              'runs': [run_once(args.source, i) for i in (1, 2)],
              'not_tested': ['live desktop lock/unlock', 'PAM authentication', 'OS reboot',
                             'logout/login', 'physical monitor reconnect']}
    (ROOT / 'verification/gtklock.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
