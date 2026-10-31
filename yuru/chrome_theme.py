"""Finalize the rendered native Chrome theme; never access Chrome profiles.

Chrome colors use RGB arrays rather than CSS hex strings. Keep palette tokens in
the manifest template, then convert them after the ordinary template renderer.
Load the resulting stable directory with chrome://extensions > Load unpacked.
"""
import json
from pathlib import Path
import re
import shutil


def finalize(directory):
    directory = Path(directory)
    manifest = directory / 'manifest.json'
    data = json.loads(manifest.read_text())
    for name, value in data['theme']['colors'].items():
        if not isinstance(value, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            raise ValueError('Expected rendered Chrome hex color: ' + name)
        data['theme']['colors'][name] = [int(value[i:i + 2], 16) for i in (1, 3, 5)]
    shutil.copy2(directory.parent / 'wallpaper.png', directory / 'wallpaper.png')
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
