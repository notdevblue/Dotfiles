"""Disposable launch-path restoration and checked package staging regressions."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import discord_runtime as runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.desktop = self.root / 'discord.desktop'
        self.desktop.write_text('[Desktop Entry]\nExec=/usr/bin/discord --url -- %u\nMimeType=x-scheme-handler/discord;\n')

    def apply(self, restore=False):
        runtime.manage_launchers(self.home, restore=restore, desktop=self.desktop)

    def test_normal_menu_and_terminal_paths_restore_previous_content(self):
        launcher = self.home / '.local/bin/discord'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/sh\nexec custom-discord "$@"\n')
        launcher.chmod(0o750)
        original = runtime.capture_file(launcher)
        self.apply()
        journal = runtime.journal_path(self.home).read_bytes()
        self.assertEqual(launcher.readlink(), Path('/usr/bin/discord-yuru'))
        desktop = self.home / '.local/share/applications/discord.desktop'
        self.assertIn('Exec=/usr/bin/discord-yuru --url -- %u', desktop.read_text())
        self.assertIn('MimeType=x-scheme-handler/discord;', desktop.read_text())
        self.apply()
        self.assertEqual(runtime.journal_path(self.home).read_bytes(), journal)
        self.apply(restore=True)
        self.assertEqual(runtime.capture_file(launcher), original)
        self.assertFalse(desktop.exists())
        self.assertFalse(runtime.journal_path(self.home).exists())

    def test_official_desktop_update_refreshes_owned_entry_and_retains_original_backup(self):
        self.apply()
        before = json.loads(runtime.journal_path(self.home).read_text())['entries']
        self.desktop.write_text(self.desktop.read_text() + 'StartupNotify=true\n')
        self.apply()
        after = json.loads(runtime.journal_path(self.home).read_text())['entries']
        self.assertEqual([e['before'] for e in before.values()], [e['before'] for e in after.values()])
        self.assertIn('StartupNotify=true', (self.home / '.local/share/applications/discord.desktop').read_text())
        self.apply(restore=True)
        self.assertFalse((self.home / '.local/share/applications/discord.desktop').exists())

    def test_external_launcher_edit_blocks_restore_before_any_mutation(self):
        self.apply()
        launcher = self.home / '.local/bin/discord'
        desktop = self.home / '.local/share/applications/discord.desktop'
        desktop.write_text('user changed this')
        before = runtime.capture_file(launcher)
        with self.assertRaisesRegex(RuntimeError, 'externally changed'):
            self.apply(restore=True)
        self.assertEqual(runtime.capture_file(launcher), before)
        self.assertEqual(desktop.read_text(), 'user changed this')
        self.assertTrue(runtime.journal_path(self.home).exists())

    def test_partial_install_can_retry_and_restore(self):
        write = runtime.write_record
        calls = 0
        def interrupted(path, value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('interrupted second write')
            return write(path, value)
        with patch.object(runtime, 'write_record', side_effect=interrupted):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(json.loads(runtime.journal_path(self.home).read_text())['phase'], 'prepared')
        self.apply()
        self.apply(restore=True)
        self.assertFalse((self.home / '.local/bin/discord').exists())

    def test_changed_official_desktop_is_preserved(self):
        self.desktop.write_text('[Desktop Entry]\nExec=/different/path\n')
        with self.assertRaisesRegex(RuntimeError, 'desktop entry changed'):
            self.apply()
        self.assertFalse(runtime.journal_path(self.home).exists())

    def test_release_tag_rejects_shell_or_branch_before_git(self):
        with patch.object(runtime.subprocess, 'check_output') as call:
            for value in ('main', 'v1.2.3;touch /tmp/no', '$(id)', '../v1.2.3'):
                with self.assertRaises(RuntimeError):
                    runtime.release_commit(value)
            call.assert_not_called()

    def test_annotated_release_uses_peeled_commit(self):
        first, peeled = 'a' * 40, 'b' * 40
        text = first + '\trefs/tags/v1.2.3\n' + peeled + '\trefs/tags/v1.2.3^{}\n'
        with patch.object(runtime.subprocess, 'check_output', return_value=text):
            self.assertEqual(runtime.release_commit('v1.2.3'), peeled)

    def test_flat_restore_bundle_works_without_installed_package_or_checkout(self):
        source = self.root / 'backup';source.mkdir()
        for name in runtime.FILES:
            (source / name).write_text('restored build resource')
        with patch.object(runtime, '__file__', str(source / 'discord_runtime.py')):
            self.assertEqual(set(runtime.resources().values()), {source / n for n in runtime.FILES})

    def test_stage_pins_candidate_and_checksums_every_local_resource(self):
        source = self.root / 'files';source.mkdir()
        files = {}
        for name in runtime.FILES:
            p = source / name
            p.write_text('fixture ' + name)
            files[name] = p
        files['PKGBUILD'].write_text("source=('git+https://example.invalid/repo#commit=" + 'a' * 40 + "')\nsha256sums=('SKIP')\n")
        destination = self.root / 'stage'
        runtime.stage_build(files, destination, 'b' * 40)
        content = (destination / 'PKGBUILD').read_text()
        self.assertIn('#commit=' + 'b' * 40, content)
        for name in runtime.FILES[1:]:
            self.assertIn(hashlib.sha256(files[name].read_bytes()).hexdigest(), content)
        self.assertNotIn('a' * 40, content)

    def test_failed_patch_build_never_reaches_privileged_install(self):
        with patch.object(runtime, 'build', side_effect=RuntimeError('patch no longer applies')), \
             patch.object(runtime, 'latest_release', return_value='v1.2.3'), \
             patch.object(runtime.Path, 'home', return_value=self.home), \
             patch.object(runtime.subprocess, 'run') as call, \
             patch('sys.argv', ['yuru-discord-update', 'update']):
            with self.assertRaisesRegex(RuntimeError, 'patch no longer applies'):
                runtime.main()
            call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
