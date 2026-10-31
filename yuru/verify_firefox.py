#!/usr/bin/env python3
"""Native Firefox chrome checks in a disposable profile and private CPU Wayland.

Only the test process enables Marionette on loopback. No live profile, tabs,
preferences, browser login or desktop session are touched.
"""
import json
from datetime import date
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


def urlbar_geometry(client):
    return client.script('''
      const rect = node => {
        const r = node.getBoundingClientRect();
        return {top:r.top, left:r.left, right:r.right, bottom:r.bottom};
      };
      return {
        input:rect(gURLBar.querySelector('.urlbar-input-container')),
        background:rect(gURLBar.querySelector('.urlbar-background')),
        resultsBackground:rect(gURLBar.querySelector('.urlbarView-background')),
        toolbar:rect(document.querySelector('#nav-bar')),
        popupOpen:gURLBar.hasAttribute('popover-open')
      };
    ''')


def main():
    artifacts = ROOT / 'verification'
    palette = json.loads((ROOT / 'palette.json').read_text())
    with tempfile.TemporaryDirectory(prefix='yuru-firefox-') as directory:
        temporary = Path(directory)
        env = isolated_environment(temporary)
        env.update(MOZ_ENABLE_WAYLAND='1', MOZ_WEBRENDER_SOFTWARE='1',
                   MOZ_REMOTE_ALLOW_SYSTEM_ACCESS='1', GTK_USE_PORTAL='0', GSETTINGS_BACKEND='memory')
        # Font files and GTK CSS are the only user assets made visible to the fixture.
        gtk = Path(env['XDG_CONFIG_HOME']) / 'gtk-3.0'
        gtk.mkdir(parents=True)
        shutil.copy2(BUILD / 'gtk-3.0/gtk.css', gtk / 'gtk.css')
        (gtk / 'settings.ini').write_text('[Settings]\ngtk-theme-name=Adwaita\ngtk-application-prefer-dark-theme=1\n')
        profile = temporary / 'profile'
        (profile / 'chrome').mkdir(parents=True)
        shutil.copy2(BUILD / 'firefox/userChrome.css', profile / 'chrome/userChrome.css')
        shutil.copy2(BUILD / 'firefox/userContent.css', profile / 'chrome/userContent.css')
        shutil.copy2(BUILD / 'wallpaper.png', profile / 'chrome/yuru-newtab.png')
        shutil.copy2(BUILD / 'wallpaper-portrait.png', profile / 'chrome/yuru-newtab-portrait.png')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        prefs = {'toolkit.legacyUserProfileCustomizations.stylesheets': True,
                 # Marionette's recommended prefs suppress New Tab feed startup.
                 # Test native New Tab initialization, not that automation shortcut.
                 'remote.prefs.recommended': False,
                 'browser.newtabpage.activity-stream.testing.shouldInitializeFeeds': True,
                 'marionette.port': port, 'browser.shell.checkDefaultBrowser': False,
                 'browser.aboutwelcome.enabled': False, 'browser.startup.page': 0,
                 'browser.startup.homepage_override.mstone': 'ignore',
                 'browser.newtabpage.enabled': True, 'browser.tabs.warnOnClose': False,
                 'browser.newtabpage.activity-stream.feeds.topsites': False,
                 'browser.newtabpage.activity-stream.feeds.section.topstories': False,
                 'browser.newtabpage.activity-stream.feeds.section.highlights': False,
                 'browser.newtabpage.activity-stream.widgets.enabled': False,
                 'browser.newtabpage.activity-stream.showWeather': False,
                 'browser.toolbars.bookmarks.visibility': 'always',
                 'browser.urlbar.suggest.searches': False,
                 'datareporting.policy.dataSubmissionEnabled': False,
                 'app.update.disabledForTesting': True}
        (profile / 'user.js').write_text(''.join(f'user_pref({json.dumps(k)}, {json.dumps(v)});\n' for k,v in prefs.items()))
        page = temporary / 'fixture.html'
        page.write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>Notes 문서 · 시마린</title>'
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
                                            '--marionette', '--new-window', page.as_uri()],
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
                  const action = document.querySelector('#star-button-box');
                  return {tabRadius:getComputedStyle(tab).borderTopLeftRadius,
                    tabBorder:getComputedStyle(tab).borderBottomColor,
                    tabOutline:getComputedStyle(tab).outlineStyle,
                    tabTopBorder:getComputedStyle(tab).borderTopWidth,
                    urlbarRadius:getComputedStyle(field).borderTopLeftRadius,
                    urlbarBorder:getComputedStyle(field).borderColor,
                    actionOutline:getComputedStyle(action).outlineStyle,
                    font:getComputedStyle(label).fontFamily,
                    fontSize:getComputedStyle(label).fontSize,
                    fontWeight:getComputedStyle(label).fontWeight,
                    usedFonts:(() => {
                      const range=document.createRange();
                      range.selectNodeContents(label);
                      const faces=InspectorUtils.getUsedFontFaces(range);
                      return Array.from(faces, face => {
                        return {name:face.name, family:face.CSSFamilyName};
                      });
                    })(),
                    tabHeight:document.querySelector('#TabsToolbar').getBoundingClientRect().height,
                    navHeight:document.querySelector('#nav-bar').getBoundingClientRect().height,
                    navBackground:getComputedStyle(document.querySelector('#nav-bar')).backgroundColor,
                    bookmarkBackground:getComputedStyle(document.querySelector('#PersonalToolbar')).backgroundColor,
                    toolboxHeight:document.querySelector('#navigator-toolbox').getBoundingClientRect().height,
                    bookmarkRadius:getComputedStyle(document.querySelector('#PersonalToolbar toolbarbutton.bookmark-item:not(#bookmarks-toolbar-placeholder)')).borderRadius,
                    backAppearance:getComputedStyle(document.querySelector('#back-button')).appearance};
                ''')
                assert values['tabRadius'] == values['urlbarRadius'] == '0px', values
                assert values['tabBorder'] == 'rgb(136, 212, 204)', values
                assert values['tabOutline'] == values['actionOutline'] == 'none', values
                assert values['tabTopBorder'] == '0px', values
                assert values['urlbarBorder'] == 'rgba(0, 0, 0, 0)', values
                assert values['tabHeight'] == 32 and 36 <= values['navHeight'] <= 40, values
                assert values['navBackground'] == values['bookmarkBackground'] == 'rgb(42, 34, 43)', values
                assert palette['browser_font'] in values['font'], values
                assert values['fontSize'] == '14px' and values['fontWeight'] == '400', values
                assert {face['family'] for face in values['usedFonts']} == {
                    palette['browser_font'], palette['fallback_font']}, values
                assert all('Bold' not in face['name'] for face in values['usedFonts']), values
                assert values['bookmarkRadius'] == '0px', values
                assert values['backAppearance'] == 'none', values
                # Flatten idle chrome without losing the multi-selection marker.
                controls = client.script('''
                  const tab = gBrowser.selectedTab;
                  gBrowser.addToMultiSelectedTabs(tab);
                  const multiOutline = getComputedStyle(tab.querySelector('.tab-background')).outlineStyle;
                  gBrowser.clearMultiSelectedTabs();
                  return {multiOutline};
                ''')
                assert controls['multiOutline'] == 'solid', controls
                client.call('Marionette:SetContext', {'value': 'content'})
                wait_until(lambda: client.script('return document.querySelector("button") !== null;'))
                content = client.script('return {font:getComputedStyle(document.body).fontFamily, radius:getComputedStyle(document.querySelector("button")).borderRadius};')
                assert content['font'] == 'serif' and content['radius'] == '9px', content
                client.call('WebDriver:Navigate', {'url': 'about:newtab'})
                wait_until(lambda: client.script('return !!document.querySelector("content-search-handoff-ui")?.shadowRoot?.querySelector(".search-handoff-button");'))
                newtab = client.script('''
                  const host=document.querySelector('content-search-handoff-ui');
                  const field=host.shadowRoot.querySelector('.search-handoff-button');
                  const logo=document.querySelector('.logo-and-wordmark');
                  const customize=document.querySelector('.open-customization-button');
                  const customizeBox=customize?.shadowRoot?.querySelector('.button-background');
                  const r=field.getBoundingClientRect();
                  return {background:getComputedStyle(document.body).backgroundColor,
                    wallpaper:getComputedStyle(document.body).backgroundImage.includes('yuru-newtab.png'),
                    searchRadius:getComputedStyle(field).borderRadius,
                    searchHeight:r.height, searchWidth:r.width, searchLeft:r.left, searchTop:r.top,
                    font:getComputedStyle(field).fontFamily,
                    fontSize:getComputedStyle(field).fontSize,
                    fontWeight:getComputedStyle(field).fontWeight,
                    customizeRadius:customizeBox ? getComputedStyle(customizeBox).borderRadius : 'missing',
                    customizeColor:customizeBox ? getComputedStyle(customizeBox).backgroundColor : 'missing',
                    logo:logo ? getComputedStyle(logo).display : 'absent'};
                ''')
                assert newtab['background'] == 'rgb(30, 25, 31)' and newtab['wallpaper'], newtab
                assert palette['browser_font'] in newtab['font'], newtab
                assert newtab['fontSize'] == '14px' and newtab['fontWeight'] == '400', newtab
                assert newtab['searchRadius'] == '0px' and newtab['searchHeight'] == 40, newtab
                assert newtab['searchWidth'] <= 522 and newtab['searchLeft'] >= 24, newtab
                assert newtab['logo'] in ('none', 'absent'), newtab
                assert newtab['customizeRadius'] == '0px' and newtab['customizeColor'] == 'rgb(42, 34, 43)', newtab
                # Native hidden helper text must not overlap the engine dropmarker.
                client.call('Marionette:SetContext', {'value': 'chrome'})
                switcher = client.script('''
                  const helper = document.querySelector('#urlbar .urlbar-visually-hidden');
                  const arrow = document.querySelector('#urlbar .searchmode-switcher-dropmarker');
                  return {helperFontSize:getComputedStyle(helper).fontSize,
                    helperWidth:helper.getBoundingClientRect().width,
                    arrowWidth:arrow.getBoundingClientRect().width,
                    arrowHeight:arrow.getBoundingClientRect().height};
                ''')
                assert switcher['helperFontSize'] == '0px' and switcher['helperWidth'] == 0, switcher
                assert switcher['arrowWidth'] == switcher['arrowHeight'] == 12, switcher
                button = client.script("return document.querySelector('#urlbar .searchmode-switcher');")
                client.call('WebDriver:ElementClick', {'id': button['element-6066-11e4-a52e-4f735466cecf']})
                wait_until(lambda: client.script('return document.querySelector("#urlbar .searchmode-switcher-panel").state === "open";'))
                switcher['menuOpened'] = True
                client.script('return document.querySelector("#urlbar .searchmode-switcher-panel-list").hide(null, {force:true});')
                wait_until(lambda: client.script('return document.querySelector("#urlbar .searchmode-switcher-panel").state === "closed";'))
                client.call('Marionette:SetContext', {'value': 'content'})
                # Clicking the native search retains its URL-bar handoff behavior.
                search_element = client.script("return document.querySelector('content-search-handoff-ui').shadowRoot.querySelector('.search-handoff-button');")
                element_id = search_element['element-6066-11e4-a52e-4f735466cecf']
                client.call('WebDriver:ElementClick', {'id': element_id})
                client.call('Marionette:SetContext', {'value': 'chrome'})
                wait_until(lambda: client.script('return gURLBar.focused;'))
                client.script('gURLBar.value="example.test"; gURLBar.startQuery({searchString:"example.test",allowAutofill:false});')
                wait_until(lambda: client.script('return gURLBar.view.isOpen;'))
                focus = client.script('''
                  const describe=n=>{const s=getComputedStyle(n);return {
                    background:s.backgroundColor,borderColor:s.borderColor,
                    outline:s.outlineStyle,outlineWidth:s.outlineWidth,caret:s.caretColor};};
                  return {input:describe(gURLBar.inputField),
                    container:describe(document.querySelector('#urlbar .urlbar-input-container')),
                    background:describe(document.querySelector('#urlbar-background, #urlbar .urlbar-background'))};
                ''')
                assert focus['container']['background'] == 'rgb(53, 56, 60)', focus
                assert focus['input']['caret'] == 'rgb(136, 212, 204)', focus
                assert all(v['outline'] == 'none' for v in focus.values()), focus
                assert focus['background']['borderColor'] == 'rgba(0, 0, 0, 0)', focus
                # Match the reported small-window case as well as a wide window.
                if attempt == 1:
                    run(['swaymsg', 'output HEADLESS-1 mode 909x731'], env)
                    time.sleep(.3)
                client.script('gURLBar.view.close();')
                wait_until(lambda: client.script('return !gURLBar.hasAttribute("popover-open");'))
                idle_geometry = urlbar_geometry(client)
                client.script('gURLBar.startQuery({searchString:"example.test",allowAutofill:false});')
                wait_until(lambda: client.script('return gURLBar.hasAttribute("popover-open");'))
                open_geometry = urlbar_geometry(client)
                geometry = {'outputSize': [1280, 800] if attempt == 0 else [909, 731],
                            'idle': idle_geometry, 'open': open_geometry}
                assert open_geometry['popupOpen'], geometry
                assert idle_geometry['input'] == open_geometry['input'], geometry
                for edge in ('top', 'left', 'right'):
                    assert open_geometry['background'][edge] == open_geometry['input'][edge], geometry
                for edge in ('left', 'right'):
                    assert abs(open_geometry['resultsBackground'][edge] - open_geometry['input'][edge]) < .02, geometry
                assert open_geometry['background']['top'] >= open_geometry['toolbar']['top'], geometry
                records.append({'startup': attempt + 1, 'chrome': values, 'controls': controls, 'switcher': switcher,
                                'content': content, 'newtab': newtab, 'focus':focus, 'geometry':geometry})
                if attempt == 1:
                    run(['swaymsg', 'output HEADLESS-1 mode 1280x800'], env)
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
                                        '--new-window', page.as_uri()],
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
            # Leave the virtual keyboard alive until Firefox consumes the keys.
            run(['/usr/bin/wtype', '-s', '100', '-M', 'ctrl', '-k', 'l', '-m', 'ctrl',
                 '-s', '100', 'about:newtab', '-k', 'Return', '-s', '500'], env)
            time.sleep(1)
            run(['grim', '-o', 'HEADLESS-1', str(artifacts / 'native-firefox-newtab.png')], env)
            # Real keyboard focus/popup capture, with no automation warning.
            # Keep the virtual keyboard connected during capture. On an otherwise
            # input-less headless seat, removing it also clears browser focus.
            keyboard = subprocess.Popen(['/usr/bin/wtype', '-s', '100', '-M', 'ctrl', '-k', 'l', '-m', 'ctrl',
                                         '-s', '100', '문서', '-s', '2000'], env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                        start_new_session=True, preexec_fn=child_limits)
            try:
                time.sleep(.7)
                if keyboard.poll() is not None:
                    raise RuntimeError(keyboard.stderr.read().decode())
                run(['grim', '-o', 'HEADLESS-1', str(artifacts / 'native-firefox-focus.png')], env)
                run(['swaymsg', 'output HEADLESS-1 mode 909x731'], env)
                time.sleep(.3)
                run(['grim', '-o', 'HEADLESS-1', str(artifacts / 'native-firefox-focus-compact.png')], env)
            finally:
                stop_group(keyboard)
            run(['/usr/bin/wtype', '-k', 'Escape', '-k', 'Escape'], env)
            run(['swaymsg', 'output HEADLESS-1 mode 800x1100'], env)
            time.sleep(.7)
            run(['grim', '-o', 'HEADLESS-1', str(artifacts / 'native-firefox-newtab-portrait.png')], env)
            (artifacts / 'firefox.json').write_text(json.dumps({'date': date.today().isoformat(),
                'firefox': '158.0.1', 'scope': 'disposable profile; two native startups; local fixture and built-in New Tab',
                'newtab_capture_sizes': [[1280,800], [800,1100]],
                'normal_startup_capture': True, 'live_profile_restart': False, 'results': records}, indent=2) + '\n')
            print('PASS Firefox: chrome, Rin New Tab/search handoff, unchanged websites, two startups')
        finally:
            if browser is not None:
                stop_group(browser)
            stop_group(server)


if __name__ == '__main__':
    main()
