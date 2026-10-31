"""Stopped-client preference merges with disposable BetterDiscord homes."""
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import discord_theme as theme


class DiscordThemeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='yuru-discord-test-')
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.settings = self.home / theme.DATA / 'settings.json'
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({'window': {'transparency': False, 'frame': True},
                                             'other': {'enabled': True}}))
        self.themes = self.settings.with_name('themes.json')
        css = self.home / theme.CSS
        css.parent.mkdir(parents=True)
        css.write_text('/** @name Yuru Kitty */\n')

    def test_apply_repeat_restore_preserves_original_and_later_unrelated_preferences(self):
        self.themes.write_text(json.dumps({'Other Theme': False}))
        theme.apply(self.home)
        path = theme.backup_path(self.home)
        initial_backup = path.read_bytes()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertNotIn('Other Theme', path.read_text())
        settings = json.loads(self.settings.read_text())
        settings['newPreference'] = 7
        self.settings.write_text(json.dumps(settings))
        self.themes.write_text(json.dumps({'Other Theme': True, theme.THEME: True}))
        theme.apply(self.home)
        self.assertEqual(path.read_bytes(), initial_backup)
        theme.restore(self.home)
        settings = json.loads(self.settings.read_text())
        self.assertIs(settings['window']['transparency'], False)
        self.assertIs(settings['window']['frame'], True)
        self.assertEqual(settings['newPreference'], 7)
        self.assertEqual(json.loads(self.themes.read_text()), {'Other Theme': True})
        self.assertFalse(path.exists())

    def test_restore_missing_keys_and_files_without_deleting_new_preferences(self):
        self.settings.write_text('{"other": true}')
        theme.apply(self.home)
        theme.restore(self.home)
        self.assertEqual(json.loads(self.settings.read_text()), {'other': True})
        self.assertFalse(self.themes.exists())
        theme.apply(self.home)
        self.themes.write_text(json.dumps({theme.THEME: True, 'New Theme': True}))
        settings = json.loads(self.settings.read_text())
        settings['window']['frame'] = True
        self.settings.write_text(json.dumps(settings))
        theme.restore(self.home)
        self.assertEqual(json.loads(self.themes.read_text()), {'New Theme': True})
        self.assertEqual(json.loads(self.settings.read_text())['window'], {'frame': True})

    def test_external_managed_edit_blocks_apply_and_restore(self):
        theme.apply(self.home)
        path = theme.backup_path(self.home)
        original_backup = path.read_bytes()
        self.themes.write_text(json.dumps({theme.THEME: False}))
        for operation in (theme.apply, theme.restore):
            with self.assertRaisesRegex(RuntimeError, 'changed since installation'):
                operation(self.home)
            self.assertEqual(path.read_bytes(), original_backup)
            self.assertIs(json.loads(self.themes.read_text())[theme.THEME], False)

    def test_interrupted_apply_and_restore_can_recover(self):
        self.themes.write_text('{}')
        real_write = theme.atomic_write
        def fail_themes(path, *args):
            if path == self.themes:
                raise OSError('fixture write failure')
            return real_write(path, *args)
        with patch.object(theme, 'atomic_write', side_effect=fail_themes):
            with self.assertRaisesRegex(OSError, 'fixture write failure'):
                theme.apply(self.home)
        self.assertEqual(theme.status(self.home)['phase'], 'prepared')
        theme.apply(self.home)
        with patch.object(theme, 'atomic_write', side_effect=fail_themes):
            with self.assertRaisesRegex(OSError, 'fixture write failure'):
                theme.restore(self.home)
        self.assertEqual(theme.status(self.home)['phase'], 'restoring')
        theme.restore(self.home)
        self.assertIs(json.loads(self.settings.read_text())['window']['transparency'], False)
        self.assertEqual(json.loads(self.themes.read_text()), {})

    def test_stopped_guard_checks_uid_comm_and_renderer_executable(self):
        proc = self.home / 'proc'
        process = proc / '123'
        process.mkdir(parents=True)
        (process / 'comm').write_text('Discord\n')
        account = SimpleNamespace(pw_dir=str(self.home))
        with patch.object(theme.pwd, 'getpwuid', return_value=account):
            with self.assertRaisesRegex(RuntimeError, 'Discord is running'):
                theme.stopped_guard(self.home, proc)
            (process / 'comm').write_text('CrRendererMain\n')
            (process / 'exe').symlink_to('/opt/discord/Discord')
            with self.assertRaisesRegex(RuntimeError, 'Discord is running'):
                theme.stopped_guard(self.home, proc)
            with patch.object(theme.os, 'getuid', return_value=os.getuid() + 1):
                theme.stopped_guard(self.home, proc)
            theme.stopped_guard(self.home / 'another-home', proc)

    def test_apply_requires_css_and_initialized_settings(self):
        (self.home / theme.CSS).unlink()
        with self.assertRaisesRegex(RuntimeError, 'Install'):
            theme.apply(self.home)
        (self.home / theme.CSS).write_text('/** @name Yuru Kitty */')
        self.settings.unlink()
        with self.assertRaisesRegex(RuntimeError, 'Initialize BetterDiscord'):
            theme.apply(self.home)
        self.assertFalse(theme.backup_path(self.home).exists())


if __name__ == '__main__':
    unittest.main()
