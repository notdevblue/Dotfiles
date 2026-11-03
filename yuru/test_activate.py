"""Cursor activation/restoration against an isolated preference/service backend."""
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import activate


class CursorActivationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='yuru-activation-test-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.state = self.home / '.local/state/yuru-theme'
        self.state.mkdir(parents=True)
        (self.state / 'transaction.json').write_text('{"status":"installed"}')
        cursor = self.home / f'.local/share/icons/{activate.THEME}/cursors/left_ptr'
        cursor.parent.mkdir(parents=True)
        cursor.write_bytes(b'Xcur')
        qt = self.home / '.local/share/yuru-theme/qt-env.sh'
        qt.parent.mkdir(parents=True)
        qt.write_text('export QT_QPA_PLATFORMTHEME=qt5ct\n')
        self.env = {'SWAYSOCK': '/no-live-session'}
        self.settings = dict(activate.GTK, **{'cursor-theme': "'Adwaita'", 'cursor-size': '32'})
        self.services = {'KEEP': 'unchanged'}
        self.calls = []
        for name, value in [('HOME', self.home), ('STATE', self.state), ('run', self.run_command)]:
            mock = patch.object(activate, name, value)
            mock.start()
            self.addCleanup(mock.stop)

    def run_command(self, args, env, check=True):
        self.calls.append(list(args))
        stdout = ''
        if args[0] == 'gsettings':
            if args[1] == 'get':
                stdout = self.settings[args[3]] + '\n'
            else:
                self.settings[args[3]] = args[4]
        elif args[:3] == ['systemctl', '--user', 'show-environment']:
            stdout = '\n'.join(f'{k}={v}' for k, v in self.services.items())
        elif args[:3] == ['systemctl', '--user', 'unset-environment']:
            self.services.pop(args[3], None)
        elif args[:3] == ['systemctl', '--user', 'set-environment']:
            key, value = args[3].split('=', 1)
            self.services[key] = value
        elif args[0] == 'dbus-update-activation-environment':
            if '--systemd' in args:
                for key in args[2:]:
                    self.services[key] = env[key]
        elif args[0] == 'swaymsg':
            if 'get_config' in args:
                # An explicit seat theme differs from the GTK baseline.
                stdout = json.dumps({'config': 'exec "unrelated quotation\nseat seat0 xcursor_theme "Original Cursor" 32\n'})
            elif 'get_version' in args:
                stdout = '{}'
            else:
                stdout = '[{"success":true}]'
        elif args[0] == 'xfconf-query':
            return subprocess.CompletedProcess(args, 1, '', '')
        else:
            raise AssertionError(f'Unexpected action: {args}')
        return subprocess.CompletedProcess(args, 0, stdout, '')

    def test_cursor_only_applies_without_reloading_or_changing_other_preferences(self):
        activate.apply(self.env, cursors_only=True)
        self.assertEqual(self.settings['cursor-theme'], repr(activate.THEME))
        self.assertEqual(self.settings['cursor-size'], str(activate.DEFAULT_SIZE))
        self.assertEqual(self.services, {'KEEP': 'unchanged', **activate.CURSOR_ENV})
        changed = [args[3] for args in self.calls if args[:2] == ['gsettings', 'set']]
        self.assertEqual(set(changed), {'cursor-theme', 'cursor-size'})
        self.assertFalse(any(args[0] in ('xfconf-query', 'dunstctl', 'gdbus') for args in self.calls))
        before = (self.state / 'runtime-before.json').read_bytes()
        activate.apply(self.env, cursors_only=True)
        self.assertEqual((self.state / 'runtime-before.json').read_bytes(), before)

    def test_restore_returns_seat_preferences_and_absent_service_environment(self):
        activate.apply(self.env, cursors_only=True)
        activate.restore_settings(self.env)
        self.assertEqual(self.settings['cursor-theme'], "'Adwaita'")
        self.assertEqual(self.settings['cursor-size'], '32')
        self.assertEqual(self.services, {'KEEP': 'unchanged'})
        seat = [args[-1] for args in self.calls if args[0] == 'swaymsg' and '--' in args][-1]
        self.assertEqual(shlex.split(seat), ['seat', '*', 'xcursor_theme', 'Original Cursor', '32'])

    def test_restore_preserves_later_user_cursor_selection_and_environment(self):
        activate.apply(self.env, cursors_only=True)
        self.settings['cursor-theme'] = "'Other'"
        self.services['XCURSOR_THEME'] = 'Other'
        before_seat_calls = sum(args[0] == 'swaymsg' and '--' in args for args in self.calls)
        activate.restore_settings(self.env)
        self.assertEqual(self.settings['cursor-theme'], "'Other'")
        self.assertEqual(self.services['XCURSOR_THEME'], 'Other')
        self.assertEqual(sum(args[0] == 'swaymsg' and '--' in args for args in self.calls), before_seat_calls)

    def test_missing_assets_fail_before_saving_or_mutating_preferences(self):
        (self.home / f'.local/share/icons/{activate.THEME}/cursors/left_ptr').unlink()
        with self.assertRaisesRegex(RuntimeError, 'Install the Yuru cursor'):
            activate.apply(self.env, cursors_only=True)
        self.assertFalse((self.state / 'runtime-before.json').exists())
        self.assertFalse(any(args[:2] == ['gsettings', 'set'] for args in self.calls))

    def test_restore_from_tty_restores_preferences_without_a_running_seat(self):
        activate.apply(self.env, cursors_only=True)
        self.calls.clear()
        activate.restore_settings({})
        self.assertEqual(self.settings['cursor-theme'], "'Adwaita'")
        self.assertFalse(any(args[0] == 'swaymsg' for args in self.calls))

    def test_cursor_only_restore_preserves_preexisting_qt_environment(self):
        self.services['QT_QPA_PLATFORMTHEME'] = 'qt5ct'
        activate.apply(self.env, cursors_only=True)
        activate.restore_settings({})
        self.assertEqual(self.services['QT_QPA_PLATFORMTHEME'], 'qt5ct')

    def test_known_qt_environment_baseline_is_restored(self):
        activate.apply(self.env, cursors_only=True)
        before = json.loads((self.state / 'runtime-before.json').read_text())
        before['qt_environment'] = 'previous-platform'
        (self.state / 'runtime-before.json').write_text(json.dumps(before))
        self.services['QT_QPA_PLATFORMTHEME'] = 'qt5ct'
        activate.restore_settings({})
        self.assertEqual(self.services['QT_QPA_PLATFORMTHEME'], 'previous-platform')


if __name__ == '__main__':
    unittest.main()
