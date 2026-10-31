#!/usr/bin/env python3
"""Native Firefox chrome checks in a disposable profile and private CPU Wayland.

Only the test process enables Marionette on loopback. No live profile, tabs,
preferences, browser login or desktop session are touched.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

from verify_native import ROOT, BUILD, isolated_environment, stop_group, run, child_limits


class Marionette:
    def __init__(self, port):
        self.socket = socket.create_connection(('127.0.0.1', port), timeout=8)
        self.sequence = 0
        self.read()
        self.call('WebDriver:NewSession', {'capabilities': {'alwaysMatch': {}}})
        self.call('Marionette:SetContext', {'value': 'chrome'})

    def read(self):
        size = b''
        while (byte := self.socket.recv(1)) != b':':
            if not byte:
                raise EOFError('Marionette disconnected')
            size += byte
        remaining = int(size)
        data = b''
        while remaining:
            chunk = self.socket.recv(remaining)
            if not chunk:
                raise EOFError('Marionette disconnected')
            data += chunk
            remaining -= len(chunk)
        return json.loads(data)

    def call(self, name, params=None):
        self.sequence += 1
        body = json.dumps([0, self.sequence, name, params or {}]).encode()
        self.socket.sendall(str(len(body)).encode() + b':' + body)
        response = self.read()
        if response[1] != self.sequence or response[2]:
            raise RuntimeError(str(response))
        result = response[3]
        return result.get('value', result) if isinstance(result, dict) else result

    def script(self, script):
        return self.call('WebDriver:ExecuteScript', {'script': script, 'args': [],
                         'newSandbox': True, 'sandbox': 'default', 'filename': 'yuru-check', 'line': 1})


def wait_until(check, seconds=12):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(.1)
    raise TimeoutError('Private Firefox did not become ready')


def main():
    artifacts = ROOT / 'verification'
    with tempfile.TemporaryDirectory(prefix='yuru-firefox-') as directory:
        temporary = Path(directory)
        env = isolated_environment(temporary)
        env.update(MOZ_ENABLE_WAYLAND='1', MOZ_WEBRENDER_SOFTWARE='1',
                   MOZ_REMOTE_ALLOW_SYSTEM_ACCESS='1', GTK_USE_PORTAL='0', GSETTINGS_BACKEND='memory')
        # Font files and GTK CSS are the only user assets made visible to the fixture.
        fonts = Path(env['HOME']) / '.local/share/fonts/yuru'
        fonts.parent.mkdir(parents=True)
        fonts.symlink_to(Path.home() / '.local/share/fonts/yuru', target_is_directory=True)
        gtk = Path(env['XDG_CONFIG_HOME']) / 'gtk-3.0'
        gtk.mkdir(parents=True)
        shutil.copy2(BUILD / 'gtk-3.0/gtk.css', gtk / 'gtk.css')
        (gtk / 'settings.ini').write_text('[Settings]\ngtk-theme-name=Adwaita\ngtk-application-prefer-dark-theme=1\n')
        profile = temporary / 'profile'
        (profile / 'chrome').mkdir(parents=True)
        shutil.copy2(BUILD / 'firefox/userChrome.css', profile / 'chrome/userChrome.css')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        prefs = {'toolkit.legacyUserProfileCustomizations.stylesheets': True,
                 'marionette.port': port, 'browser.shell.checkDefaultBrowser': False,
                 'browser.aboutwelcome.enabled': False, 'browser.startup.page': 0,
                 'browser.startup.homepage_override.mstone': 'ignore',
                 'browser.newtabpage.enabled': False, 'browser.tabs.warnOnClose': False,
                 'browser.toolbars.bookmarks.visibility': 'always',
                 'browser.urlbar.suggest.searches': False,
                 'datareporting.policy.dataSubmissionEnabled': False,
                 'browser.safebrowsing.downloads.enabled': False,
                 'browser.safebrowsing.phishing.enabled': False,
                 'browser.safebrowsing.malware.enabled': False,
                 'app.update.disabledForTesting': True}
        (profile / 'user.js').write_text(''.join(f'user_pref({json.dumps(k)}, {json.dumps(v)});\n' for k,v in prefs.items()))
        page = temporary / 'fixture.html'
        page.write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>문서 · 시마린</title>'
                        '<style>body{font:18px serif;background:#fafafa;color:#111}button{border-radius:9px}</style>'
                        '<h1>한글 문서</h1><button>본문 버튼</button></html>')
        config = temporary / 'sway.conf'
        config.write_text('xwayland disable\noutput HEADLESS-1 mode 1280x800\nseat seat0 fallback true\n'
                          'default_border pixel 1\nclient.focused #712F3E #2A222B #E1DBD1 #88D4CC #712F3E\n')
        log = (temporary / 'sway.log').open('w+')
        server = subprocess.Popen(['/usr/bin/sway', '--config', str(config)], env=env,
                                  stdout=log, stderr=log, start_new_session=True, preexec_fn=child_limits)
        browser = None
        records = []
        try:
            def compositor_ready():
                runtime = Path(env['XDG_RUNTIME_DIR'])
                sockets = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
                ipc = list(runtime.glob('sway-ipc.*.sock'))
                if sockets and ipc:
                    env.update(WAYLAND_DISPLAY=sockets[0].name, SWAYSOCK=str(ipc[0]))
                    try:
                        return bool(run(['swaymsg', '-t', 'get_outputs', '-r'], env))
                    except RuntimeError:
                        return False
            wait_until(compositor_ready)
            for attempt in range(2):
                browser_log = (temporary / f'firefox-{attempt}.log').open('w+')
                browser = subprocess.Popen(['/usr/bin/firefox', '--no-remote', '--profile', str(profile),
                                            '--offline', '--marionette', '--new-window', page.as_uri()],
                                           env=env, stdout=browser_log, stderr=browser_log,
                                           start_new_session=True, preexec_fn=child_limits)
                def remote_ready():
                    if browser.poll() is not None:
                        browser_log.seek(0)
                        raise RuntimeError(browser_log.read())
                    try:
                        return Marionette(port)
                    except (OSError, EOFError):
                        return False
                client = wait_until(remote_ready, seconds=20)
                wait_until(lambda: client.script('return !!document.querySelector(".tab-label");'))
                if attempt == 0:
                    client.script('''return (async () => {
                      for (const [title, url] of [['문서','docs'],['다운로드','downloads'],['작업 기록','notes']]) {
                        await PlacesUtils.bookmarks.insert({parentGuid:PlacesUtils.bookmarks.toolbarGuid,
                          title, url:'https://example.test/' + url});
                      } return true;
                    })();''')
                wait_until(lambda: client.script('return document.querySelectorAll("#PersonalToolbar .bookmark-item").length >= 3;'))
                # A Korean tab and ASCII tab exercise the same real browser controls.
                client.script('gBrowser.addTab("about:blank", {triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()}).label = "bash / notes";')
                values = client.script('''
                  const tab = document.querySelector('.tabbrowser-tab[selected] .tab-background');
                  const label = document.querySelector('.tabbrowser-tab[selected] .tab-label');
                  const field = document.querySelector('#urlbar-background, .urlbar-background');
                  return {tabRadius:getComputedStyle(tab).borderTopLeftRadius,
                    tabBorder:getComputedStyle(tab).borderBottomColor,
                    urlbarRadius:getComputedStyle(field).borderTopLeftRadius,
                    font:getComputedStyle(label).fontFamily,
                    tabHeight:document.querySelector('#TabsToolbar').getBoundingClientRect().height,
                    toolboxHeight:document.querySelector('#navigator-toolbox').getBoundingClientRect().height,
                    bookmarkRadius:getComputedStyle(document.querySelector('#PersonalToolbar toolbarbutton.bookmark-item:not(#bookmarks-toolbar-placeholder)')).borderRadius,
                    backAppearance:getComputedStyle(document.querySelector('#back-button')).appearance};
                ''')
                assert values['tabRadius'] == values['urlbarRadius'] == '0px', values
                assert values['tabBorder'] == 'rgb(136, 212, 204)', values
                assert 'Sarasa Mono K' in values['font'], values
                assert values['bookmarkRadius'] == '0px', values
                assert values['backAppearance'] == 'none', values
                client.call('Marionette:SetContext', {'value': 'content'})
                wait_until(lambda: client.script('return document.querySelector("button") !== null;'))
                content = client.script('return {font:getComputedStyle(document.body).fontFamily, radius:getComputedStyle(document.querySelector("button")).borderRadius};')
                assert content['font'] == 'serif' and content['radius'] == '9px', content
                client.call('Marionette:SetContext', {'value': 'chrome'})
                records.append({'startup': attempt + 1, 'chrome': values, 'content': content})
                if attempt == 1:
                    client.call('WebDriver:DeleteSession')
                    client.socket.close()
                    time.sleep(.5)
                    run(['grim', '-g', '0,0 1280x150', str(artifacts / 'native-firefox.png')], env)
                    client = Marionette(port)
                    client.script('PanelUI.show();')
                    client.call('WebDriver:DeleteSession')
                    time.sleep(.5)
                    run(['grim', '-o', 'HEADLESS-1', str(artifacts / 'native-firefox-menu.png')], env)
                client.socket.close()
                stop_group(browser)
                browser = None
            # Capture an ordinary startup so the test-only remote-control warning
            # is not mistaken for the theme's normal URL-bar appearance.
            with (profile / 'user.js').open('a') as prefs_file:
                prefs_file.write('user_pref("marionette.enabled", false);\n')
            ordinary_env = dict(env)
            ordinary_env.pop('MOZ_REMOTE_ALLOW_SYSTEM_ACCESS')
            browser_log = (temporary / 'firefox-ordinary.log').open('w+')
            browser = subprocess.Popen(['/usr/bin/firefox', '--no-remote', '--profile', str(profile),
                                        '--offline', '--new-window', page.as_uri()],
                                       env=ordinary_env, stdout=browser_log, stderr=browser_log,
                                       start_new_session=True, preexec_fn=child_limits)
            time.sleep(3)
            if browser.poll() is not None:
                browser_log.seek(0)
                raise RuntimeError(browser_log.read())
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    raise RuntimeError('Marionette unexpectedly active during ordinary capture')
            except OSError:
                pass
            height = min(200, round(records[-1]['chrome']['toolboxHeight']) + 2)
            run(['grim', '-g', f'0,0 1280x{height}', str(artifacts / 'native-firefox.png')], env)
            (artifacts / 'firefox.json').write_text(json.dumps({'date': '2026-10-31',
                'firefox': '158.0.1', 'scope': 'disposable profile; two native startups; local page only',
                'normal_startup_capture': True, 'live_profile_restart': False, 'results': records}, indent=2) + '\n')
            print('PASS Firefox: square tabs/urlbar, Sarasa UI font, unchanged content, two startups')
        finally:
            if browser is not None:
                stop_group(browser)
            stop_group(server)


if __name__ == '__main__':
    main()
