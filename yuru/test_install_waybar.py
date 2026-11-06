"""Owned Waybar upgrades stay atomic and preserve edited or foreign installs."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import install_waybar as installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='waybar-installer-test-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.target = root / 'lib' / installer.RELEASE
        self.legacy = self.target.parent / installer.LEGACY_RELEASE
        self.link = root / 'bin/waybar'
        self.link.parent.mkdir()
        self.patch = root / 'actions.patch'
        self.patch.write_text('test patch')
        self.binary = root / 'built-waybar'
        self.binary.write_bytes(b'new binary')
        self.license = root / 'source-LICENSE'
        self.license.write_text('license')
        for name, value in [('TARGET', self.target), ('LEGACY', self.legacy), ('LINK', self.link), ('PATCH', self.patch)]:
            change = patch.object(installer, name, value)
            change.start()
            self.addCleanup(change.stop)

    def old_installation(self):
        self.legacy.mkdir(parents=True)
        (self.legacy / 'waybar').write_bytes(b'old binary')
        (self.legacy / 'LICENSE').write_text('license')
        record = {'version': installer.LEGACY_RELEASE, 'source_sha256': installer.SHA256,
                  'patch_sha256': installer.LEGACY_PATCH_SHA256,
                  'binary_sha256': installer.digest(self.legacy / 'waybar'),
                  'license_sha256': installer.digest(self.legacy / 'LICENSE')}
        (self.legacy / 'installation.json').write_text(json.dumps(record))
        self.link.symlink_to(self.legacy / 'waybar')

    def test_upgrade_and_idempotent_reinstall(self):
        self.old_installation()
        installer.install(self.binary, self.license)
        self.assertEqual(self.link.readlink(), self.target / 'waybar')
        self.assertEqual(self.link.read_bytes(), b'new binary')
        self.assertFalse(self.legacy.exists())
        self.assertEqual((self.target / 'waybar').stat().st_mode & 0o777, 0o755)
        installer.install(self.binary, self.license)
        installer.check_existing()

    def test_failed_staging_keeps_working_launcher(self):
        self.old_installation()
        with patch.object(installer.shutil, 'copy2', side_effect=OSError('full disk')):
            with self.assertRaisesRegex(OSError, 'full disk'):
                installer.install(self.binary, self.license)
        self.assertEqual(self.link.read_bytes(), b'old binary')
        self.assertEqual(self.link.readlink(), self.legacy / 'waybar')
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.iterdir()), [self.legacy])

    def test_edited_old_binary_or_extra_file_is_never_removed(self):
        self.old_installation()
        original = (self.legacy / 'waybar').read_bytes()
        (self.legacy / 'waybar').write_bytes(b'edited')
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            installer.install(self.binary, self.license)
        (self.legacy / 'waybar').write_bytes(original)
        (self.legacy / 'keep').write_text('user content')
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            installer.install(self.binary, self.license)
        self.assertTrue((self.legacy / 'keep').exists())
        self.assertFalse(self.target.exists())

    def test_foreign_launcher_and_symlink_directory_are_refused(self):
        foreign = self.link.parent / 'foreign'
        foreign.write_bytes(b'not ours')
        self.link.symlink_to(foreign)
        with self.assertRaisesRegex(RuntimeError, 'another installation'):
            installer.install(self.binary, self.license)
        self.link.unlink()
        self.target.parent.mkdir()
        self.target.symlink_to(foreign)
        with self.assertRaisesRegex(RuntimeError, 'symlink installation'):
            installer.install(self.binary, self.license)
        self.assertEqual(foreign.read_bytes(), b'not ours')

    def test_remove_cleans_only_verified_installation(self):
        installer.install(self.binary, self.license)
        with patch('sys.argv', ['install_waybar.py', '--remove']):
            installer.main()
        self.assertFalse(self.target.exists())
        self.assertFalse(self.link.is_symlink())
        self.assertEqual(self.binary.read_bytes(), b'new binary')


if __name__ == '__main__':
    unittest.main()
