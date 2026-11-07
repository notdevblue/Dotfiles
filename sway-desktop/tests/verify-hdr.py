#!/usr/bin/env python3
"""Validate saved SDR white policy, IPC changes, reload and fresh starts."""
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(sys.argv[1]).resolve()
for restart in range(2):
    with tempfile.TemporaryDirectory(prefix='sway-hdr-config-') as temp:
        runtime = Path(temp)
        config = runtime / 'config'
        config.write_text('''output * mode 640x480
output HEADLESS-1 sdr_white_level 300
xwayland disable
seat seat0 fallback true
''')
        env = dict(os.environ, XDG_RUNTIME_DIR=temp, WLR_BACKENDS='headless',
                   WLR_HEADLESS_OUTPUTS='2', WLR_RENDERER='vulkan')
        for key in ('SWAYSOCK', 'WAYLAND_DISPLAY', 'DISPLAY', 'WAYLAND_SOCKET'):
            env.pop(key, None)
        with (runtime / 'sway.log').open('w') as log:
            process = subprocess.Popen([str(root / 'build/sway/sway'),
                '--unsupported-gpu', '-c', str(config)], env=env,
                stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 15
                sock = None
                while time.monotonic() < deadline:
                    sock = next(runtime.glob('sway-ipc.*.sock'), None)
                    if sock:
                        break
                    if process.poll() is not None:
                        raise AssertionError((runtime / 'sway.log').read_text()[-5000:])
                    time.sleep(0.05)
                assert sock, 'No isolated compositor socket'

                def ipc(command=None, kind=None, expected=True):
                    args = ['swaymsg', '-s', str(sock), '-r']
                    args += ['-t', kind] if kind else [command]
                    result = subprocess.run(args, capture_output=True, text=True)
                    data = json.loads(result.stdout)
                    if not kind:
                        assert all(row.get('success', False) == expected for row in data), data
                    return data

                def expect(first, second=203):
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        outputs = {o['name']: o for o in ipc(kind='get_outputs')}
                        if (outputs.get('HEADLESS-1', {}).get('sdr_white_level') == first
                                and outputs.get('HEADLESS-2', {}).get('sdr_white_level') == second):
                            return
                        time.sleep(0.03)
                    raise AssertionError(outputs)

                # Build a real client with the installed protocol definition, then
                # exercise v1/v2 creation and the required no-information error.
                protocol = Path(subprocess.check_output([
                    'pkg-config', '--variable=pkgdatadir', 'wayland-protocols'],
                    text=True).strip()) / 'staging/color-management/color-management-v1.xml'
                header = runtime / 'color-management-v1-client-protocol.h'
                protocol_code = runtime / 'color-management-v1-protocol.c'
                subprocess.run(['wayland-scanner', 'client-header', str(protocol), str(header)], check=True)
                subprocess.run(['wayland-scanner', 'private-code', str(protocol), str(protocol_code)], check=True)
                flags = shlex.split(subprocess.check_output(
                    ['pkg-config', '--cflags', '--libs', 'wayland-client'], text=True))
                client = runtime / 'windows-scrgb-client'
                subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + [
                    '-Wall', '-Wextra', '-Wno-unused-parameter', '-I' + str(runtime),
                    str(Path(__file__).with_name('windows-scrgb-client.c')),
                    str(protocol_code), '-o', str(client)] + flags, check=True)
                wayland = next(p.name for p in runtime.glob('wayland-*') if p.suffix != '.lock')
                subprocess.run([str(client)], env=dict(env, WAYLAND_DISPLAY=wayland), check=True)
                assert 'hdr2' in ipc(kind='get_version')['human_readable']
                expect(300)
                ipc('output HEADLESS-1 sdr_white_level 400')
                expect(400)
                for bad in ('nan', 'inf', '-1', '0', '1001', 'nope', '300junk'):
                    ipc('output HEADLESS-1 sdr_white_level ' + bad, expected=False)
                expect(400)
                ipc('output HEADLESS-1 sdr_white_level default')
                expect(203)
                ipc('output * sdr_white_level 250')
                expect(250, 250)
                ipc('output HEADLESS-1 sdr_white_level 350 scale 1')
                expect(350, 250)
                ipc('reload')
                expect(300)
                print(f'PASS: Vulkan start {restart + 1}, saved policy, runtime changes, '
                      'invalid input, wildcard merge and reload')
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
