#!/usr/bin/env python3
"""Validate the saved SDR brightness launcher with isolated IPC/profile mocks.

An optional launcher path supports restoration layouts that store the launcher
separately from the compositor integration and these tests.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile


def verify_slider(launcher):
    """Canonical launcher, isolated saved profile and mocked compositor IPC."""
    import contextlib
    import copy
    import io
    import runpy
    from unittest.mock import patch

    namespace = runpy.run_path(str(launcher))
    # run_path returns a copy; functions retain the actual module globals.
    slider = namespace['apply'].__globals__
    displays = [dict(name='DP-1', make='Example', model='OLED', serial='ONE',
                     active=True, focused=False, hdr=True, hdr_configured=True,
                     sdr_white_level=603),
                dict(name='DP-2', make='Example', model='LCD', serial='TWO',
                     active=True, focused=True, hdr=True, hdr_configured=True,
                     sdr_white_level=300)]
    profile = ('# unchanged header\ninclude ~/.config/sway/config.detached\n'
               'output "Example OLED ONE" {\n    render_bit_depth 10\n'
               '    hdr on\n    sdr_white_level 603\n}\n'
               'output "Example LCD TWO" {\n    hdr on\n'
               '    sdr_white_level 300\n}\n# unchanged footer\n')
    commands = []
    def ipc(*args):
        if args == ('-t', 'get_outputs'):
            return copy.deepcopy(displays)
        commands.append(args[0])
        words = shlex.split(args[0])
        display = next(o for o in displays if o['name'] == words[1])
        display['sdr_white_level'] = float(words[3])
        return [{'success': True}]
    def fails(action):
        try:
            action()
        except (RuntimeError, ValueError, OSError):
            return
        raise AssertionError('unsafe operation succeeded')
    with tempfile.TemporaryDirectory(prefix='sdr-slider-') as temp:
        saved = Path(temp) / 'profile'
        slider.update(PROFILE=saved, ipc=ipc)
        saved.write_text(profile)
        saved.chmod(0o640)
        assert slider['output']()['name'] == 'DP-2'
        assert slider['output']('Example OLED ONE')['name'] == 'DP-1'
        slider['apply']('DP-2', 410)
        assert saved.read_text() == profile.replace('sdr_white_level 300', 'sdr_white_level 410')
        assert saved.stat().st_mode & 0o777 == 0o640
        assert commands == ['output "DP-2" sdr_white_level 410']
        slider['apply']('DP-1', 550)
        assert 'sdr_white_level 410' in saved.read_text()
        assert displays[0]['sdr_white_level'] == 550
        # DPMS off retains configured HDR and can update the pending policy.
        displays[1]['hdr'] = False
        displays[1]['power'] = False
        slider['apply']('DP-2', 390)
        with patch.object(sys, 'argv', ['sdr-brightness', '--status', '--output', 'DP-2']):
            with contextlib.redirect_stdout(io.StringIO()) as status:
                slider['main']()
        assert json.loads(status.getvalue())['hdr_configured'] is True
        assert json.loads(status.getvalue())['hdr'] is False
        with patch.object(sys, 'argv', ['sdr-brightness', '--set', '380', '--output',
                                       'Example LCD TWO']):
            slider['main']()
        assert displays[1]['sdr_white_level'] == 380
        # The dialog labels the selected screen and Cancel restores that screen.
        from types import SimpleNamespace
        child = SimpleNamespace(stdout=io.StringIO('350\n'), wait=lambda: 1,
                                poll=lambda: 1)
        with patch.object(sys, 'argv', ['sdr-brightness', '--output', 'DP-2']):
            with patch.object(subprocess, 'Popen', return_value=child) as dialog:
                slider['main']()
        text = next(arg for arg in dialog.call_args.args[0] if arg.startswith('--text='))
        assert 'LCD' in text and 'DP-2' in text
        assert displays[1]['sdr_white_level'] == 380
        assert 'sdr_white_level 550' in saved.read_text()
        displays[1]['hdr_configured'] = False
        fails(lambda: slider['output']())  # Never fall back to the other monitor.
        displays[1]['hdr_configured'] = True
        displays[1]['focused'] = False
        fails(lambda: slider['output']())
        fails(lambda: slider['output']('missing'))
        displays.append(dict(displays[0], name='DP-3'))
        fails(lambda: slider['output']('Example OLED ONE'))
        displays.pop()
        # Unknown/overlapping saved policy must leave both live and disk intact.
        invalid = [profile + 'output "Example LCD TWO" {\n hdr on\n sdr_white_level 22\n}\n',
                   profile.replace('sdr_white_level 300', 'sdr_white_level 300; hdr off'),
                   profile.replace('sdr_white_level 300', 'sdr_white_level 300\n sdr_white_level 22'),
                   profile.replace('Example LCD TWO', '*'),
                   profile.replace('hdr on\n    sdr_white_level 300', 'hdr off\n    sdr_white_level 300'),
                   profile + 'output DP-2 sdr_white_level 50\n',
                   profile + 'output DP-2 hdr off\n',
                   profile[:-22] + 'output DP-2 {\n']
        for content in invalid:
            saved.write_text(content)
            before = copy.deepcopy(displays)
            count = len(commands)
            fails(lambda: slider['apply']('DP-2', 222))
            assert saved.read_text() == content and displays == before
            assert len(commands) == count
        saved.write_text(profile)
        before = copy.deepcopy(displays)
        with patch.object(os, 'replace', side_effect=OSError('replace failed')):
            fails(lambda: slider['apply']('DP-2', 222))
        assert displays == before and saved.read_text() == profile
        assert not list(Path(temp).glob('.sdr-brightness-*'))
        # A failed compositor command also leaves the saved policy intact.
        real_set = slider['set_live']
        def rejected(name, value):
            if value == 222:
                raise RuntimeError('IPC failure')
            real_set(name, value)
        slider['set_live'] = rejected
        fails(lambda: slider['apply']('DP-2', 222))
        assert displays == before and saved.read_text() == profile
        assert not list(Path(temp).glob('.sdr-brightness-*'))
    print('PASS: slider focused/explicit dual HDR selection, DPMS, scoped persistence, '
          'ambiguous/invalid policy rejection and atomic-save rollback')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('launcher', nargs='?', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'bin/sdr-brightness')
    verify_slider(parser.parse_args().launcher)
