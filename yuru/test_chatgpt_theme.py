"""Native app-server config integration in disposable CODEX_HOME directories."""
import json
from pathlib import Path
import shutil
import stat
import tempfile
import tomllib
import unittest

import chatgpt_theme as theme


@unittest.skipUnless(shutil.which('codex'), 'codex app-server is required')
class ChatGPTThemeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='yuru-chatgpt-test-')
        self.home = Path(self.temporary.name)
        self.codex = self.home / '.codex'
        self.codex.mkdir()
        self.config = self.codex / 'config.toml'
        self.original = ('# Preserve the unrelated configuration and comments.\n'
                         'model_verbosity = "low"\n[desktop]\n'
                         'appearanceTheme = "system"\nnotifyOnTurnComplete = false\n')
        self.config.write_text(self.original)

    def tearDown(self):
        self.temporary.cleanup()

    def test_persistent_apply_update_restore_preserves_user_preferences(self):
        theme.apply(self.home)
        # Each operation starts a fresh real app-server. This verifies config
        # persistence across process launches, not a mocked in-memory response.
        with theme.AppServer(self.codex) as server:
            selected, _ = server.read()
            self.assertEqual(selected, theme.desired())
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(data['model_verbosity'], 'low')
        self.assertIs(data['desktop']['notifyOnTurnComplete'], False)
        self.assertIn('# Preserve', self.config.read_text())
        backup = theme.backup_path(self.home)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(backup.parent.stat().st_mode), 0o700)
        stored = json.loads(backup.read_text())
        self.assertEqual(set(stored['before']), set(theme.KEYS))
        self.assertNotIn('notifyOnTurnComplete', backup.read_text())
        theme.apply(self.home)  # Updating keeps the original before values.
        theme.restore(self.home)
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(data['desktop']['appearanceTheme'], 'system')
        self.assertNotIn('appearanceDarkChromeTheme', data['desktop'])
        self.assertIs(data['desktop']['notifyOnTurnComplete'], False)
        self.assertFalse(backup.exists())

    def test_restore_refuses_post_install_appearance_changes(self):
        theme.apply(self.home)
        with theme.AppServer(self.codex) as server:
            current, version = server.read()
            current['appearanceTheme']['value'] = 'light'
            server.write(current, version)
        with self.assertRaisesRegex(RuntimeError, 'changed since installation'):
            theme.restore(self.home)
        self.assertTrue(theme.backup_path(self.home).exists())
        self.assertEqual(tomllib.loads(self.config.read_text())['desktop']['appearanceTheme'], 'light')

    def test_optimistic_version_prevents_unrelated_concurrent_overwrite(self):
        with theme.AppServer(self.codex) as server:
            _, version = server.read()
            self.config.write_text(self.original + 'unrelatedSetting = 7\n')
            with self.assertRaisesRegex(RuntimeError, 'RPC failed'):
                server.write(theme.desired(), version)
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(data['desktop']['unrelatedSetting'], 7)
        self.assertEqual(data['desktop']['appearanceTheme'], 'system')


if __name__ == '__main__':
    unittest.main()
