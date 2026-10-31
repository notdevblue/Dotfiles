#!/usr/bin/env python3
"""Apply/restore native ChatGPT desktop appearance through config/batchWrite.

Only appearance keys are backed up. No chats, accounts or whole configuration
files are copied. Running this helper never restarts the desktop application.
"""
import argparse
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time

from theme import ROOT, atomic_write, render, state_directory

KEYS = ('appearanceTheme', 'appearanceDarkChromeTheme')


def native_json(value):
    # Installed app-server config layers can expose serde's arbitrary-precision
    # number wrapper. Restore ordinary JSON scalars before comparing snapshots.
    if isinstance(value, dict):
        if set(value) == {'$serde_json::private::Number'}:
            return json.loads(value['$serde_json::private::Number'])
        return {key: native_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [native_json(item) for item in value]
    return value


class AppServer:
    def __init__(self, codex_home):
        self.home = Path(codex_home).resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.path = self.home / 'config.toml'
        self.process = subprocess.Popen(
            ['codex', 'app-server'], cwd=self.home,
            env=dict(os.environ, CODEX_HOME=str(self.home)),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True)
        self.sequence = 0
        self.buffer = b''
        try:
            self.call('initialize', {'clientInfo': {'name': 'yuru-theme', 'version': '1.0'}})
            self.send({'method': 'initialized'})
        except BaseException:
            self.close()
            raise

    def send(self, message):
        self.process.stdin.write((json.dumps(message) + '\n').encode())
        self.process.stdin.flush()

    def call(self, method, params):
        if method not in ('initialize', 'config/read', 'config/batchWrite'):
            raise ValueError('Unsupported theme RPC')
        self.sequence += 1
        self.send({'id': self.sequence, 'method': method, 'params': params})
        deadline = time.monotonic() + 20
        while True:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                response = json.loads(line)
                if response.get('id') != self.sequence:
                    continue
                if 'error' in response:
                    # Avoid echoing arbitrary private configuration in server errors.
                    raise RuntimeError('App-server theme RPC failed: ' + method)
                return response['result']
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise TimeoutError('App-server theme RPC timed out: ' + method)
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('App-server exited before theme RPC completed')
            self.buffer += chunk

    def read(self):
        result = self.call('config/read', {'includeLayers': True})
        for layer in result.get('layers') or []:
            name = layer['name']
            if name['type'] == 'user' and Path(name['file']) == self.path and not name.get('profile'):
                desktop = native_json(layer['config'].get('desktop', {}))
                return {key: {'existed': key in desktop, 'value': desktop.get(key)} for key in KEYS}, layer['version']
        raise RuntimeError('Cannot identify versioned user configuration layer')

    def write(self, values, version):
        return self.call('config/batchWrite', {
            'filePath': str(self.path), 'expectedVersion': version,
            'edits': [{'keyPath': 'desktop.' + key, 'mergeStrategy': 'replace',
                       'value': value['value'] if value['existed'] else None}
                      for key, value in values.items()]})

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=3)
        self.process.stdin.close()
        self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def desired():
    palette = json.loads((ROOT / 'palette.json').read_text())
    data = json.loads(render((ROOT / 'templates/chatgpt/theme.json').read_text(), palette))
    return {'appearanceTheme': {'existed': True, 'value': 'dark'},
            'appearanceDarkChromeTheme': {'existed': True, 'value': data}}


def backup_path(home):
    state = state_directory(Path(home))
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.chmod(0o700)
    path = state / 'chatgpt-before.json'
    if path.is_symlink():
        raise RuntimeError('ChatGPT backup must not be a symlink')
    return path


def apply(home, codex_home=None):
    path = backup_path(home)
    with AppServer(codex_home or Path(home) / '.codex') as server:
        current, version = server.read()
        owned = desired()
        if path.exists():
            backup = json.loads(path.read_text())
            if backup['configPath'] != str(server.path):
                raise RuntimeError('ChatGPT backup belongs to another configuration')
            if current != backup['owned']:
                raise RuntimeError('ChatGPT appearance changed since installation; backup retained')
            before = backup['before']
        else:
            before = current
        backup = {'configPath': str(server.path), 'before': before, 'owned': owned,
                  'previousOwned': current, 'status': 'prepared'}
        atomic_write(path, (json.dumps(backup, indent=2) + '\n').encode(), 0o600)
        server.write(owned, version)
        installed, _ = server.read()
        if installed != owned:
            raise RuntimeError('ChatGPT appearance readback mismatch; backup retained')
        backup['status'] = 'installed'
        backup.pop('previousOwned')
        atomic_write(path, (json.dumps(backup, indent=2) + '\n').encode(), 0o600)


def restore(home, codex_home=None):
    path = backup_path(home)
    backup = json.loads(path.read_text())
    with AppServer(codex_home or Path(home) / '.codex') as server:
        current, version = server.read()
        if backup['configPath'] != str(server.path):
            raise RuntimeError('ChatGPT backup belongs to another configuration')
        allowed = [backup['owned'], backup['before']]
        if backup.get('status') == 'prepared':
            allowed.append(backup['previousOwned'])
        if current not in allowed:
            raise RuntimeError('ChatGPT appearance changed since installation; backup retained')
        server.write(backup['before'], version)
        restored, _ = server.read()
        if restored != backup['before']:
            raise RuntimeError('ChatGPT restoration readback mismatch; backup retained')
    path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['apply', 'restore'])
    parser.add_argument('--home', type=Path, default=Path.home())
    args = parser.parse_args()
    {'apply': apply, 'restore': restore}[args.command](args.home.expanduser().resolve())
    print('ChatGPT appearance ' + ('saved' if args.command == 'apply' else 'restored') + '; application was not restarted.')


if __name__ == '__main__':
    main()
