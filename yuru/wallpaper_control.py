#!/usr/bin/env python3
"""Install, start, stop, or remove the optional Yuru ASCII desktop layer."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Controller:
    def __init__(self, home=None, source=None):
        self.home = Path(home or Path.home()).absolute()
        self.source = Path(source or __file__).resolve().parent
        self.share = self.home / '.local/share/yuru-ascii'
        self.wrapper = self.home / '.local/bin/yuru-wallpaper'
        self.config = self.home / '.config/sway/config.d/95-yuru-ascii.conf'
        self.state = self.home / '.local/state/yuru-ascii'
        self.manifest = self.state / 'installed.json'
        self.runtime = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
        self.pidfile = self.runtime / 'yuru-ascii.json'

    def files(self):
        files = {}
        for name in ('ascii_wallpaper.py', 'wallpaper_control.py', 'palette.json', 'assets/rin-cutout.png'):
            files[self.share / name] = ((self.source / name).read_bytes(), 0o644)
        wrapper = '#!/bin/sh\nexec /usr/bin/python3 ' + shlex.quote(str(self.share / 'wallpaper_control.py')) + ' "$@"\n'
        files[self.wrapper] = (wrapper.encode(), 0o755)
        command = shlex.quote(str(self.wrapper)) + ' _run'
        files[self.config] = (('# Managed by yuru-wallpaper; existing swaybg remains the fallback.\n'
                               'exec_always ' + command + '\n').encode(), 0o644)
        return files

    def records(self):
        return json.loads(self.manifest.read_text()) if self.manifest.exists() else {}

    @staticmethod
    def verify(path, expected):
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
            raise RuntimeError(f'Preserving externally changed file: {path}')

    def install(self):
        # Preflight every destination before making any changes. Unknown files are never replaced.
        files, records = self.files(), self.records()
        for path in files:
            if str(path) in records:
                self.verify(path, records[str(path)])
            elif path.exists() or path.is_symlink():
                raise RuntimeError(f'Unmanaged destination already exists: {path}')
        previous = {path: (path.read_bytes(), path.stat().st_mode & 0o777)
                    if path.exists() else None for path in files}
        written = []
        try:
            for path, (data, mode) in files.items():
                atomic_write(path, data, mode)
                written.append(path)
            atomic_write(self.manifest, (json.dumps({str(p): digest(d) for p, (d, _) in files.items()}, indent=2) + '\n').encode(), 0o600)
        except OSError:
            for path in reversed(written):
                if previous[path] is None:
                    path.unlink()
                else:
                    atomic_write(path, *previous[path])
            raise
        print('Installed. Run yuru-wallpaper start; future Sway starts/reloads start the layer automatically.')

    def process(self):
        try:
            record = json.loads(self.pidfile.read_text())
            pid = int(record['pid'])
            proc = Path('/proc') / str(pid)
            # comm may contain spaces and parentheses; fields after its final ')' begin at field 3.
            started = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
            argv = (proc / 'cmdline').read_bytes().split(b'\0')
            if (proc.stat().st_uid == os.getuid() and started == record['started']
                    and str(self.share / 'wallpaper_control.py').encode() in argv and b'_run' in argv):
                return pid
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def stop(self):
        pid = self.process()
        if pid:
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 5
            while self.process() == pid:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Wallpaper did not stop; installed files have been preserved')
                time.sleep(.05)
        print('ASCII layer stopped; the existing static wallpaper remains visible.')

    def restore(self):
        records = self.records()
        if not records:
            print('No wallpaper installation to restore.')
            return
        # Reject edited files before stopping the layer or deleting any owned files.
        for name, expected in records.items():
            self.verify(Path(name), expected)
        self.stop()
        for name in records:
            Path(name).unlink()
        self.manifest.unlink()
        print('Removed ASCII autostart and installed files. Existing wallpaper configuration is unchanged.')

    def start(self):
        records = self.records()
        if not records:
            raise RuntimeError('Run install first')
        for name, expected in records.items():
            self.verify(Path(name), expected)
        observed = self.process()
        if not observed:
            env = os.environ.copy()
            if not env.get('SWAYSOCK'):
                sockets = list(self.runtime.glob('sway-ipc.*.sock'))
                if len(sockets) != 1:
                    raise RuntimeError('Run start in the intended Sway session (SWAYSOCK is required)')
                env['SWAYSOCK'] = str(sockets[0])
            command = 'exec ' + shlex.quote(str(self.wrapper)) + ' _run'
            result = subprocess.run(['swaymsg', '-s', env['SWAYSOCK'], '-r', '--', command],
                                    env=env, capture_output=True, text=True, check=True, timeout=8)
            if not all(item.get('success') for item in json.loads(result.stdout)):
                raise RuntimeError(result.stdout)
        deadline = time.monotonic() + 8
        readyfile = self.runtime / 'yuru-ascii-ready.json'
        while True:
            pid = self.process()
            if pid:
                observed = pid
                try:
                    record = json.loads(self.pidfile.read_text())
                    ready = json.loads(readyfile.read_text())
                    if (record['pid'] == pid and ready['pid'] == record['renderer_pid']
                            and self.process() == pid):
                        break
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            elif observed:
                raise RuntimeError(f'Wallpaper exited before becoming ready; inspect {self.state / "renderer.log"}')
            if time.monotonic() >= deadline:
                raise RuntimeError(f'Wallpaper did not become ready; inspect {self.state / "renderer.log"}')
            time.sleep(.05)
        print('ASCII desktop layer started.')

    def run(self):
        # Sway executes this under its own current Wayland environment. Keep the lock in this
        # supervisor, rather than relying on process names or killing unrelated wallpaper tools.
        with (self.runtime / 'yuru-ascii.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            readyfile = self.runtime / 'yuru-ascii-ready.json'
            readyfile.unlink(missing_ok=True)
            self.state.mkdir(parents=True, exist_ok=True)
            with (self.state / 'renderer.log').open('ab') as log:
                child = subprocess.Popen(['/usr/bin/python3', str(self.share / 'ascii_wallpaper.py'),
                                          '--ready-file', str(readyfile)],
                                         cwd=self.share, stdout=log, stderr=log)
                def terminate(_signum, _frame):
                    child.terminate()
                signal.signal(signal.SIGTERM, terminate)
                signal.signal(signal.SIGINT, terminate)
                started = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]
                atomic_write(self.pidfile, json.dumps({'pid': os.getpid(), 'started': started,
                                                       'renderer_pid': child.pid}).encode(), 0o600)
                try:
                    child.wait()
                finally:
                    self.pidfile.unlink(missing_ok=True)
                    readyfile.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'start', 'stop', 'restore', 'status', '_run'])
    args = parser.parse_args()
    control = Controller()
    try:
        if args.command == 'status':
            print(json.dumps({'installed': control.manifest.exists(), 'running_pid': control.process(),
                              'autostart': control.config.exists()}))
        elif args.command == '_run':
            control.run()
        else:
            # Serialise installer/start/restore operations; the runtime supervisor has its own lock.
            control.state.mkdir(parents=True, exist_ok=True)
            with (control.state / 'control.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                getattr(control, args.command)()
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
