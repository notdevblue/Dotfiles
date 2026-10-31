"""Controller installation ownership and lifecycle regression checks."""
import json
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from wallpaper_control import Controller, atomic_write


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        for name in ('ascii_wallpaper.py', 'wallpaper_control.py', 'palette.json', 'assets/rin-cutout.png'):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('fixture ' + name).encode())
        self.control = Controller(home=self.root / 'home', source=self.source / 'wallpaper_control.py')
        self.control.runtime = self.root / 'runtime'
        self.control.runtime.mkdir()
        self.control.pidfile = self.control.runtime / 'yuru-ascii.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_install_update_restore_preserves_static_fallback(self):
        fallback = self.control.home / '.config/sway/config.d/90-yuru.conf'
        fallback.parent.mkdir(parents=True)
        fallback.write_text('output * bg original.png fill\n')
        self.control.install()
        self.assertEqual(self.control.wrapper.stat().st_mode & 0o777, 0o755)
        self.assertIn('exec_always ', self.control.config.read_text())
        self.assertNotIn('swaybg', self.control.wrapper.read_text())
        (self.source / 'palette.json').write_text('updated palette')
        self.control.install()
        self.assertEqual((self.control.share / 'palette.json').read_text(), 'updated palette')
        self.control.restore()
        self.assertFalse(self.control.config.exists())
        self.assertFalse(self.control.wrapper.exists())
        self.assertEqual(fallback.read_text(), 'output * bg original.png fill\n')

    def test_unknown_destination_is_preserved_without_partial_install(self):
        self.control.config.parent.mkdir(parents=True)
        self.control.config.write_text('user config')
        with self.assertRaisesRegex(RuntimeError, 'Unmanaged'):
            self.control.install()
        self.assertEqual(self.control.config.read_text(), 'user config')
        self.assertFalse(self.control.wrapper.exists())

    def test_external_edit_blocks_update_and_restore_before_any_deletion(self):
        self.control.install()
        self.control.config.write_text('user edit')
        with self.assertRaisesRegex(RuntimeError, 'externally changed'):
            self.control.install()
        with self.assertRaisesRegex(RuntimeError, 'externally changed'):
            self.control.restore()
        self.assertTrue(self.control.wrapper.exists())
        self.assertTrue(self.control.manifest.exists())
        self.assertEqual(self.control.config.read_text(), 'user edit')

    def test_symlink_destination_is_never_followed(self):
        other = self.root / 'other'
        other.write_text('untouched')
        self.control.wrapper.parent.mkdir(parents=True)
        self.control.wrapper.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, 'Unmanaged'):
            self.control.install()
        self.assertEqual(other.read_text(), 'untouched')

    def test_write_failure_rolls_back_new_installation(self):
        def fail_at_wrapper(path, data, mode=0o644):
            if path == self.control.wrapper:
                raise OSError('simulated storage failure')
            atomic_write(path, data, mode)
        with patch('wallpaper_control.atomic_write', side_effect=fail_at_wrapper):
            with self.assertRaisesRegex(OSError, 'storage failure'):
                self.control.install()
        self.assertFalse(self.control.manifest.exists())
        self.assertFalse((self.control.share / 'ascii_wallpaper.py').exists())

    def test_stale_pid_cannot_signal_unrelated_process(self):
        self.control.pidfile.write_text(json.dumps({'pid': os.getpid(), 'started': 'wrong'}))
        self.assertIsNone(self.control.process())
        with patch('wallpaper_control.os.kill') as kill:
            self.control.stop()
            kill.assert_not_called()

    def test_run_singleton_and_targeted_stop(self):
        # Use the real installed supervisor and a harmless fake renderer, with two starts.
        source_controller = Path(__file__).with_name('wallpaper_control.py')
        (self.source / 'wallpaper_control.py').write_bytes(source_controller.read_bytes())
        (self.source / 'ascii_wallpaper.py').write_text('import time\ntime.sleep(60)\n')
        self.control.install()
        env = dict(os.environ, HOME=str(self.control.home), XDG_RUNTIME_DIR=str(self.control.runtime))
        command = [str(self.control.wrapper), '_run']
        first = subprocess.Popen(command, env=env)
        try:
            deadline = time.monotonic() + 3
            while not self.control.process() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertEqual(self.control.process(), first.pid)
            second = subprocess.run(command, env=env, timeout=3)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(self.control.process(), first.pid)
            self.control.stop()
            first.wait(timeout=3)
            self.assertFalse(self.control.pidfile.exists())
            self.assertFalse((self.control.runtime / 'yuru-ascii-ready.json').exists())
        finally:
            if first.poll() is None:
                first.terminate()
                first.wait(timeout=3)

    def start_renderer(self, script):
        """Exercise start and the real supervisor; substitute only Sway's exec IPC."""
        (self.source / 'wallpaper_control.py').write_bytes(Path(__file__).with_name('wallpaper_control.py').read_bytes())
        (self.source / 'ascii_wallpaper.py').write_text(script)
        self.control.install()
        env = dict(os.environ, HOME=str(self.control.home), XDG_RUNTIME_DIR=str(self.control.runtime),
                   SWAYSOCK='/fixture-sway')
        def launch(*args, **kwargs):
            proc = subprocess.Popen([str(self.control.wrapper), '_run'], env=env)
            def cleanup():
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=3)
            self.addCleanup(cleanup)
            return subprocess.CompletedProcess(args[0], 0, '[{"success": true}]', '')
        with patch.dict(os.environ, env), patch('wallpaper_control.subprocess.run', side_effect=launch):
            self.control.start()

    def test_start_waits_for_matching_renderer_readiness(self):
        readyfile = self.control.runtime / 'yuru-ascii-ready.json'
        readyfile.write_text(json.dumps({'pid': 123, 'outputs': ['stale']}))
        self.start_renderer('''import json, os, pathlib, sys, time
ready = pathlib.Path(sys.argv[2])
assert not ready.exists(), 'stale readiness was not removed'
ready.write_text(json.dumps({'pid': os.getpid() + 1000000, 'outputs': ['wrong']}))
time.sleep(.2)
ready.write_text(json.dumps({'pid': os.getpid(), 'outputs': ['fixture']}))
time.sleep(60)
''')
        record = json.loads(self.control.pidfile.read_text())
        ready = json.loads(readyfile.read_text())
        self.assertEqual(ready['pid'], record['renderer_pid'])
        self.assertEqual(ready['outputs'], ['fixture'])
        self.control.stop()
        self.assertFalse(readyfile.exists())

    def test_start_reports_renderer_failure_before_readiness(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(RuntimeError, 'before becoming ready; inspect .*renderer.log'):
                self.start_renderer('import time\ntime.sleep(.2)\nraise RuntimeError("startup failure")\n')
        self.assertNotIn('ASCII desktop layer started.', output.getvalue())
        self.assertIn('startup failure', (self.control.state / 'renderer.log').read_text())
        self.assertFalse(self.control.pidfile.exists())
        self.assertFalse((self.control.runtime / 'yuru-ascii-ready.json').exists())

    def test_start_reuses_ready_supervisor_without_queued_exec(self):
        self.control.install()
        self.control.pidfile.write_text(json.dumps({'pid': 4321, 'renderer_pid': 1234}))
        (self.control.runtime / 'yuru-ascii-ready.json').write_text(json.dumps({'pid': 1234}))
        with patch.dict(os.environ, {'SWAYSOCK': '/fixture-sway'}), \
                patch.object(self.control, 'process', return_value=4321), \
                patch('wallpaper_control.subprocess.run') as run:
            self.control.start()
        run.assert_not_called()

    def test_start_waits_for_existing_initializing_supervisor_without_queued_exec(self):
        self.control.install()
        self.control.pidfile.write_text(json.dumps({'pid': 4321, 'renderer_pid': 1234}))
        readyfile = self.control.runtime / 'yuru-ascii-ready.json'
        with patch.dict(os.environ, {'SWAYSOCK': '/fixture-sway'}), \
                patch.object(self.control, 'process', return_value=4321), \
                patch('wallpaper_control.time.sleep', side_effect=lambda _: readyfile.write_text(json.dumps({'pid': 1234}))) as sleep, \
                patch('wallpaper_control.subprocess.run') as run:
            self.control.start()
        sleep.assert_called_once()
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
