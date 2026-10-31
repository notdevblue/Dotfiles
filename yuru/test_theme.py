"""Offline installer round-trip and configuration tests; never uses the real home."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import theme


class OfflineThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = theme.build()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='yuru-test-')
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.original = {
            '.bashrc': 'alias keep="true"\nPS1="old"\n',
            '.config/sway/config': 'set $mod Mod4\ninclude config.d/*.conf\n',
            '.config/sway/config.swayfx': 'include config.detached\nfor_window [app_id="^kitty$"] blur enable\n',
            '.config/gtk-3.0/settings.ini': '# preserve comment\n[Settings]\ngtk-im-module=fcitx\n',
            '.config/fcitx5/conf/classicui.conf': 'Font=Old 10\nKeepMe=True\n[Other]\nKey=untouched\n',
            '.config/Code - OSS/User/settings.json': json.dumps({
                'workbench.colorTheme': 'existing', 'unrelated.setting': True,
                'workbench.colorCustomizations': {'button.foreground': '#FFFFFF'}}),
            'dotfiles/kitty.conf': 'background_opacity 0.90\ncustom_option yes\n',
        }
        for name, text in self.original.items():
            p = self.home / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        (self.home / '.config/kitty').mkdir(parents=True)
        (self.home / '.config/kitty/kitty.conf').symlink_to(self.home / 'dotfiles/kitty.conf')

    def assert_original(self):
        for name, text in self.original.items():
            self.assertEqual((self.home / name).read_text(), text, name)
        self.assertTrue((self.home / '.config/kitty/kitty.conf').is_symlink())

    def test_install_restore_preserves_symlinks_and_unrelated_settings(self):
        count = theme.install(self.home, self.output)
        self.assertGreater(count, 20)
        self.assertTrue((self.home / '.config/kitty/kitty.conf').is_symlink())
        self.assertIn('custom_option yes', (self.home / 'dotfiles/kitty.conf').read_text())
        self.assertIn('gtk-im-module=fcitx', (self.home / '.config/gtk-3.0/settings.ini').read_text())
        fcitx = (self.home / '.config/fcitx5/conf/classicui.conf').read_text()
        self.assertIn('KeepMe=True', fcitx)
        self.assertIn('[Other]\nKey=untouched', fcitx)
        settings = json.loads((self.home / '.config/Code - OSS/User/settings.json').read_text())
        self.assertTrue(settings['unrelated.setting'])
        self.assertEqual(settings['workbench.colorTheme'], 'existing')
        self.assertEqual(settings['workbench.colorCustomizations']['button.foreground'], '#FFFFFF')
        self.assertEqual(settings['workbench.colorCustomizations']['editor.background'], '#1E191F')
        self.assertEqual(theme.restore(self.home), count)
        self.assert_original()
        self.assertFalse((self.home / '.config/gtk-3.0/gtk.css').exists())
        self.assertFalse(theme.state_directory(self.home).exists())

    def test_restore_refuses_subsequent_edits_before_restoring_anything(self):
        theme.install(self.home, self.output)
        p = self.home / '.config/rofi/config.rasi'
        p.write_text(p.read_text() + '\n/* user edit */\n')
        current = (self.home / '.bashrc').read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'Post-install edits'):
            theme.restore(self.home)
        self.assertEqual((self.home / '.bashrc').read_bytes(), current)
        self.assertTrue(theme.state_directory(self.home).exists())

    def test_restore_refuses_retargeted_symlink(self):
        theme.install(self.home, self.output)
        link = self.home / '.config/kitty/kitty.conf'
        link.unlink()
        link.symlink_to(self.home / '.bashrc')
        with self.assertRaisesRegex(RuntimeError, 'symlink changed'):
            theme.restore(self.home)

    def test_interrupted_install_rolls_back(self):
        original_write = theme.atomic_write
        failed = False
        def fail_once(path, data, mode=0o644):
            nonlocal failed
            if path == self.home / '.config/rofi/config.rasi' and not failed:
                failed = True
                raise OSError('injected write failure')
            return original_write(path, data, mode)
        with patch.object(theme, 'atomic_write', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'injected'):
                theme.install(self.home, self.output)
        self.assert_original()
        self.assertFalse(theme.state_directory(self.home).exists())

    def test_plan_has_no_home_writes_and_blocks_escape_symlink(self):
        first = theme.deployment(self.home, self.output)
        self.assert_original()
        self.assertEqual(first, theme.deployment(self.home, self.output))
        self.assertFalse(theme.state_directory(self.home).exists())
        link = self.home / '.config/kitty/kitty.conf'
        link.unlink()
        link.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(RuntimeError, 'outside user home'):
            theme.install(self.home, self.output)
        self.assertFalse(theme.state_directory(self.home).exists())

    def test_jsonc_code_profile_stays_untouched(self):
        p = self.home / '.config/Code - OSS/User/settings.json'
        p.write_text('{\n// existing comment\n"keep": true,\n}\n')
        self.assertNotIn('.config/Code - OSS/User/settings.json', theme.deployment(self.home, self.output))

    def test_ini_updates_all_duplicate_managed_keys(self):
        result = theme.ini_merge('[Settings]\nFont=Old\nFont=Last\n[Settings]\nFont=Again\n', {'Settings': {'Font': 'New'}})
        self.assertEqual(result.count('Font=New'), 3)
        self.assertNotIn('Old', result)

    def test_swaynag_merges_colors_and_preserves_output_and_custom_types(self):
        original = '# placement\noutput=DP-5\nedge=bottom\n[warning]\nfont=Other 10\nbackground=ffffff\n[custom]\ntext=abcdef\n'
        path = self.home / '.config/swaynag/config'
        path.parent.mkdir(parents=True)
        path.write_text(original)
        theme.install(self.home, self.output)
        result = path.read_text()
        self.assertIn('output=DP-5\nedge=bottom', result)
        self.assertIn('[custom]\ntext=abcdef', result)
        self.assertIn('font=Other 10', result)
        self.assertIn('background=1E191F', result)
        self.assertIn('button-background=88D4CC', result)
        theme.restore(self.home)
        self.assertEqual(path.read_text(), original)

    def test_chrome_native_theme_uses_rgb_and_restores_files(self):
        manifest = '.local/share/yuru-theme/chrome/manifest.json'
        wallpaper = '.local/share/yuru-theme/chrome/wallpaper.png'
        theme.install(self.home, self.output)
        data = json.loads((self.home / manifest).read_text())
        self.assertEqual(data['theme']['colors']['frame'], [30, 25, 31])
        self.assertEqual(data['theme']['colors']['toolbar_button_icon'], [136, 212, 204])
        self.assertNotIn('permissions', data)
        self.assertNotIn('background', data)
        self.assertEqual((self.home / wallpaper).read_bytes(), (self.output / 'wallpaper.png').read_bytes())
        theme.restore(self.home)
        self.assertFalse((self.home / manifest).exists())
        self.assertFalse((self.home / wallpaper).exists())

    def test_file_restore_preserves_pending_chatgpt_backup(self):
        theme.install(self.home, self.output)
        backup = theme.state_directory(self.home) / 'chatgpt-before.json'
        backup.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'Restore ChatGPT appearance first'):
            theme.restore(self.home)
        self.assertEqual(backup.read_text(), '{}')
        self.assertTrue((self.home / '.config/swaynag/config').exists())
        backup.unlink()
        theme.restore(self.home)

    def test_state_symlink_and_repository_refused(self):
        state = self.home / '.local/state/yuru-theme'
        state.parent.mkdir(parents=True)
        state.symlink_to(self.home / 'backups')
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            theme.install(self.home, self.output)
        state.unlink()
        (self.home / '.git').mkdir()
        with self.assertRaisesRegex(RuntimeError, 'Git repository'):
            theme.install(self.home, self.output)

    def test_interrupted_install_can_be_recovered(self):
        original_write = theme.atomic_write
        def interrupt(path, data, mode=0o644):
            if path == self.home / '.config/rofi/config.rasi':
                raise KeyboardInterrupt('simulated abrupt stop')
            return original_write(path, data, mode)
        with patch.object(theme, 'atomic_write', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                theme.install(self.home, self.output)
        theme.restore(self.home)
        self.assert_original()

    def test_interrupted_restore_can_be_retried(self):
        theme.install(self.home, self.output)
        original_write = theme.atomic_write
        def interrupt(path, data, mode=0o644):
            if path == self.home / '.bashrc':
                raise KeyboardInterrupt('simulated abrupt restore stop')
            return original_write(path, data, mode)
        with patch.object(theme, 'atomic_write', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                theme.restore(self.home)
        theme.restore(self.home)
        self.assert_original()

    def test_live_guard_uses_account_home_instead_of_home_environment(self):
        import os
        import pwd
        fake_proc = self.home / '123'
        fake_proc.mkdir()
        (fake_proc / 'comm').write_text('sway\n')
        actual_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
        with patch.dict(os.environ, {'HOME': str(self.home)}):
            with patch.object(Path, 'iterdir', return_value=iter([fake_proc])):
                with self.assertRaisesRegex(RuntimeError, 'Sway is running'):
                    theme.idle_guard(actual_home)

    def test_authorized_live_install_does_not_call_idle_guard_or_restart_apps(self):
        with patch.object(theme, 'idle_guard', side_effect=RuntimeError('running')):
            with self.assertRaisesRegex(RuntimeError, 'running'):
                theme.install(self.home, self.output)
            theme.install(self.home, self.output, allow_live=True)
            theme.restore(self.home, allow_live=True)
        self.assert_original()

    def test_update_retains_original_backups_and_adds_new_files(self):
        theme.install(self.home, self.output)
        targets = theme.deployment(self.home, self.output)
        targets['.config/rofi/config.rasi'] += b'\n/* updated contrast */\n'
        targets['.config/new-theme-file'] = b'new\n'
        with patch.object(theme, 'deployment', return_value=targets):
            theme.amend(self.home, self.output)
        self.assertIn('updated contrast', (self.home / '.config/rofi/config.rasi').read_text())
        theme.restore(self.home)
        self.assert_original()
        self.assertFalse((self.home / '.config/new-theme-file').exists())

    def test_interrupted_update_can_restore_initial_installation(self):
        theme.install(self.home, self.output)
        targets = theme.deployment(self.home, self.output)
        targets['.local/share/yuru-theme/sway.conf'] += b'\n# changed\n'
        targets['.config/rofi/config.rasi'] += b'\n/* contrast */\n'
        original_write = theme.atomic_write
        def interrupt(path, data, mode=0o644):
            if path == self.home / '.config/rofi/config.rasi':
                raise KeyboardInterrupt('interrupted update')
            return original_write(path, data, mode)
        with patch.object(theme, 'deployment', return_value=targets):
            with patch.object(theme, 'atomic_write', side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    theme.amend(self.home, self.output)
        theme.restore(self.home)
        self.assert_original()

    def test_firefox_profile_scope_and_import_order(self):
        profile = self.home / '.config/mozilla/firefox/test.default'
        (profile / 'chrome').mkdir(parents=True)
        ini = profile.parent / 'profiles.ini'
        ini.write_text('[Profile0]\nIsRelative=1\nPath=test.default\nDefault=1\n')
        (profile / 'chrome/userChrome.css').write_text('@namespace url("legacy");\n')
        targets = theme.deployment(self.home, self.output)
        css = targets['.config/mozilla/firefox/test.default/chrome/userChrome.css'].decode()
        self.assertLess(css.index('@import'), css.index('@namespace'))
        content = targets['.config/mozilla/firefox/test.default/chrome/userContent.css'].decode()
        (profile / 'chrome/userContent.css').write_text(content)
        # The theme's own import must not cause Firefox to vanish from updates.
        updated = theme.deployment(self.home, self.output)
        self.assertIn('.config/mozilla/firefox/test.default/chrome/yuru-content.css', updated)
        self.assertEqual(updated['.config/mozilla/firefox/test.default/chrome/yuru-newtab.png'],
                         (self.output / 'wallpaper.png').read_bytes())
        (profile / 'chrome/userContent.css').write_text('body {color:red;}')
        targets = theme.deployment(self.home, self.output)
        self.assertNotIn('.config/mozilla/firefox/test.default/user.js', targets)

    def test_selected_update_preserves_unrelated_post_install_edits(self):
        theme.install(self.home, self.output)
        kitty = self.home / '.config/kitty/kitty.conf'
        edited = kitty.read_bytes() + b'\n# independent user edit\n'
        kitty.write_bytes(edited)
        relative = '.config/gtk-3.0/yuru.css'
        targets = theme.deployment(self.home, self.output)
        targets[relative] += b'\n/* updated menubar */\n'
        with patch.object(theme, 'deployment', return_value=targets):
            theme.amend(self.home, self.output, only=[relative])
            with self.assertRaisesRegex(ValueError, 'Unknown update target'):
                theme.amend(self.home, self.output, only=['missing-target'])
        self.assertEqual((self.home / relative).read_bytes(), targets[relative])
        self.assertEqual(kitty.read_bytes(), edited)

    def test_file_restore_retains_original_runtime_preferences(self):
        theme.install(self.home, self.output)
        before = {'gsettings': {'color-scheme': "'default'"}, 'thunar': {'last-view': None}}
        (theme.state_directory(self.home) / 'runtime-before.json').write_text(json.dumps(before))
        theme.restore(self.home)
        retained = self.home / '.local/state/yuru-theme-preferences-before.json'
        self.assertEqual(json.loads(retained.read_text()), before)
        self.assert_original()

    def test_closed_firefox_uses_install_default_before_legacy_default(self):
        base = self.home / '.config/mozilla/firefox'
        (base / 'release').mkdir(parents=True)
        (base / 'legacy').mkdir()
        (base / 'profiles.ini').write_text('[Profile0]\nIsRelative=1\nPath=release\n'
                                         '[InstallTEST]\nDefault=release\nLocked=1\n'
                                         '[Profile1]\nIsRelative=1\nPath=legacy\nDefault=1\n')
        targets = theme.deployment(self.home, self.output)
        self.assertIn('.config/mozilla/firefox/release/user.js', targets)
        self.assertNotIn('.config/mozilla/firefox/legacy/user.js', targets)

    def test_generated_formats_and_lock_protection(self):
        import configparser
        for major, count in [(5, 21), (6, 22)]:
            config = configparser.ConfigParser()
            config.read(self.output / f'qt{major}ct/colors/yuru.conf')
            for key in ['active_colors', 'inactive_colors', 'disabled_colors']:
                self.assertEqual(len(config['ColorScheme'][key].split(',')), count)
        for major in [3, 4]:
            css = (self.output / f'gtk-{major}.0/gtk.css').read_text()
            self.assertIn('window#DP-5, window#DP-6', css)
            self.assertIn('background-color: #000000', css)
        waybar = json.loads((self.output / 'waybar/config.jsonc').read_text())
        self.assertEqual(waybar['modules-right'], ['clock'])
        self.assertNotIn('exec', json.dumps(waybar))
        for p in self.output.rglob('*'):
            if p.is_file() and p.suffix not in ['.png', '.xpi']:
                self.assertNotRegex(p.read_text(), r'@[A-Z0-9_]+@', str(p))


if __name__ == '__main__':
    unittest.main()
