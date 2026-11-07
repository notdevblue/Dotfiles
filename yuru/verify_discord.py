#!/usr/bin/env python3
"""Verify authored Discord component contracts against externally supplied public CSS.

Run with a Python environment containing playwright, tinycss2 and Pillow. No Discord
profile, account, authentication, messages, or browser session is loaded.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from PIL import Image
import tinycss2

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / 'verification/fixtures/discord.html'


def betterdiscord_components(source):
    """Keep only public BD notification/toast rules, never captured Yuru/app CSS."""
    output = []
    has_notification = False
    for rule in tinycss2.parse_stylesheet(source, skip_comments=True, skip_whitespace=True):
        if rule.type != 'qualified-rule':
            continue
        selector = tinycss2.serialize(rule.prelude)
        if all(item.strip().startswith(('.bd-notification', '.bd-toast')) for item in selector.split(',')):
            output.append(tinycss2.serialize([rule]))
            has_notification |= '.bd-notification' in [item.strip() for item in selector.split(',')]
    if not has_notification:
        raise ValueError('BetterDiscord source must contain native .bd-notification styling')
    return '\n'.join(output)


def sidebar_border_regression(page, theme, check, result):
    """Sample the rendered seam through transparent account art, not CSS text.

    A negative control removes only the repair rule. Its native border must
    reproduce the line through the transparent avatar in both panel heights.
    """
    rules = tinycss2.parse_stylesheet(theme, skip_comments=False, skip_whitespace=False)
    repair = [rule for rule in rules if rule.type == 'qualified-rule'
              and '.sidebarList__5e434' in tinycss2.serialize(rule.prelude)
              and '--custom-app-panels-height' in tinycss2.serialize(rule.content)]
    check('sidebar line negative control locates exactly one repair rule', len(repair) == 1)
    without_repair = tinycss2.serialize([rule for rule in rules if rule not in repair])
    theme_style = page.locator('style').last
    cases = []
    for repaired, css in ((False, without_repair), (True, theme)):
        theme_style.evaluate('(e,css)=>e.textContent=css', css)
        for name, collapsed, height in (('collapsed', True, 57), ('normal', False, 57), ('expanded', False, 190)):
            page.locator('#border-sidebar').evaluate('''(e,state)=>{
                e.setAttribute('data-collapsed',String(state.collapsed));
                e.style.setProperty('--custom-app-panels-height',state.height+'px');
            }''', {'collapsed': collapsed, 'height': height})
            page.locator('#border-sidebar').scroll_into_view_if_needed()
            geometry = page.evaluate('''()=>{
                const root=document.querySelector('#border-sidebar'),list=document.querySelector('#border-list'),avatar=document.querySelector('#border-avatar'),panel=document.querySelector('#border-panel'),button=document.querySelector('#border-control');
                const r=root.getBoundingClientRect(),l=list.getBoundingClientRect(),a=avatar.getBoundingClientRect(),p=panel.getBoundingClientRect(),b=button.getBoundingClientRect();
                const probe=document.createElement('canvas').getContext('2d');probe.canvas.width=probe.canvas.height=1;probe.fillStyle=getComputedStyle(root).getPropertyValue('--yuru-border');probe.fillRect(0,0,1,1);
                return {sidebarWidth:r.width,listWidth:l.width,borderWidth:getComputedStyle(list).borderInlineStartWidth,lineX:Math.round(l.x-r.x),aboveY:Math.floor(p.y-r.y-10),avatarY:Math.floor(a.y-r.y+a.height/2),belowY:Math.floor(p.bottom-r.y-5),nameplate:getComputedStyle(document.querySelector('#border-nameplate')).backgroundImage,border:[...probe.getImageData(0,0,1,1).data].slice(0,3),controlHit:document.elementFromPoint(b.x+b.width/2,b.y+b.height/2)===button};
            }''')
            shot = Image.open(BytesIO(page.locator('#border-sidebar').screenshot())).convert('RGB')
            x = geometry['lineX']
            sampled = {key: {'line': list(shot.getpixel((x, geometry[key]))),
                             'neighbor': list(shot.getpixel((x - 2, geometry[key])))}
                       for key in ('aboveY', 'avatarY', 'belowY')}
            below_clear = all(sampled[key]['line'] == sampled[key]['neighbor'] for key in ('avatarY', 'belowY'))
            case = {'state': name, 'repaired': repaired, 'height': height, 'geometry': geometry, 'pixels': sampled}
            cases.append(case)
            if repaired:
                original = next(item for item in cases if not item['repaired'] and item['state'] == name)
                check('sidebar ' + name + ': repair retains native layout widths', geometry['sidebarWidth'] == original['geometry']['sidebarWidth'] and geometry['listWidth'] == original['geometry']['listWidth'] and geometry['borderWidth'] == original['geometry']['borderWidth'])
                check('sidebar ' + name + ': no painted seam through transparent account avatar/nameplate', below_clear, sampled)
                check('sidebar ' + name + ': nameplate gradient remains unchanged', geometry['nameplate'] == original['geometry']['nameplate'])
                check('sidebar ' + name + ': account control remains pointer target', geometry['controlHit'])
                if not collapsed:
                    check('sidebar ' + name + ': upper divider still paints exactly one border pixel', sampled['aboveY']['line'] == geometry['border'] and sampled['aboveY']['neighbor'] != geometry['border'], sampled['aboveY'])
            elif not collapsed:
                check('sidebar ' + name + ': old native border reproduces reported avatar seam', not below_clear and sampled['avatarY']['line'] == geometry['border'], sampled)
    page.locator('#border-control').click()
    check('sidebar account control still receives real pointer click', page.evaluate('window.fixtureBorderControlClicks') == 1)
    result['sidebarBorderPixels'] = cases

COMPOSER_METRICS = r"""() => {
 const area=document.querySelector('#composer-area'),editor=document.querySelector('#editor'),placeholder=document.querySelector('#composer-placeholder');
 const prompt=getComputedStyle(area,'::before'),field=getComputedStyle(editor),hint=getComputedStyle(placeholder);
 // A text probe with the pseudo-element's computed geometry lets Range compare
 // glyph boxes. No fixed pixel offset is asserted as the desired alignment.
 const probe=document.createElement('span');probe.textContent='>';
 Object.assign(probe.style,{position:'absolute',top:prompt.top,left:prompt.left,font:prompt.font,visibility:'hidden'});
 area.append(probe);
 const firstGlyph=e=>{const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode()){if(node.textContent.length){const r=document.createRange();r.setStart(node,0);r.setEnd(node,1);return r.getBoundingClientRect().y;}}return null;};
 const target=editor.textContent.length?editor:placeholder;
 const delta=firstGlyph(probe)-firstGlyph(target);probe.remove();
 return {delta,promptFont:prompt.font,editorFont:field.font,placeholderFont:hint.font,promptTop:prompt.top,paddingTop:field.paddingTop,editorHeight:editor.getBoundingClientRect().height,promptPointerEvents:prompt.pointerEvents};
}"""

FORUM_METRICS = r"""() => {
 const area=document.querySelector('#forum-area'),editor=document.querySelector('#forum-editor'),placeholder=document.querySelector('#forum-placeholder');
 const prompt=getComputedStyle(area,'::before'),field=getComputedStyle(editor),hint=getComputedStyle(placeholder);
 const probe=document.createElement('span');probe.textContent='>';
 Object.assign(probe.style,{position:'absolute',top:prompt.top,left:prompt.left,font:prompt.font,visibility:'hidden'});
 area.append(probe);
 const glyph=e=>{const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode()){if(node.textContent.length){const r=document.createRange();r.setStart(node,0);r.setEnd(node,1);return r.getBoundingClientRect();}}return null;};
 const target=editor.textContent.length?editor:placeholder;
 const promptBox=glyph(probe),targetBox=glyph(target);probe.remove();
 return {delta:promptBox.y-targetBox.y,gap:targetBox.x-(promptBox.x+promptBox.width),promptFont:prompt.font,editorFont:field.font,placeholderFont:hint.font,promptTop:prompt.top,paddingTop:field.paddingTop,promptPointerEvents:prompt.pointerEvents};
}"""


def composer_regression(page, check, result):
    """Exercise the native Slate/placeholder structure missing from the old fixture."""
    cases = []
    for width, font in ((800, 16), (1280, 16), (800, 20), (1280, 20)):
        page.set_viewport_size({'width': width, 'height': 1000})
        page.evaluate('(font)=>document.documentElement.style.fontSize=font+"px"', font)
        for height in (44, 56, 72):
            page.locator('#composer-area').evaluate('(e,height)=>e.style.setProperty("--custom-channel-textarea-text-area-height",height+"px")', height)
            for state, text in (('placeholder', ''), ('single', 'Message sample'), ('multiline', 'First line\nSecond line\nThird line')):
                page.locator('#editor').fill(text)
                metrics = page.evaluate(COMPOSER_METRICS)
                name = f'composer {width}px / root {font}px / height {height}px / {state}'
                check(name + ': prompt and first glyph align', abs(metrics['delta']) < .1, metrics)
                check(name + ': shared font and native padding', metrics['promptFont'] == metrics['editorFont'] == metrics['placeholderFont'] and metrics['promptTop'] == metrics['paddingTop'])
                check(name + ': prompt cannot intercept clicks', metrics['promptPointerEvents'] == 'none')
                cases.append({'width': width, 'rootFont': font, 'height': height, 'state': state, **metrics})
    old_prompt = page.add_style_tag(content='.channelTextArea__74017 .textArea__74017::before{top:12px;font:16px/22px var(--font-code)}')
    check('composer negative control reproduces old baseline mismatch', abs(page.evaluate(COMPOSER_METRICS)['delta']) > 2)
    old_prompt.evaluate('(e)=>e.remove()')
    page.set_viewport_size({'width': 1280, 'height': 1000})
    page.evaluate('document.documentElement.style.fontSize="16px"')
    page.locator('#composer-area').evaluate('(e)=>e.style.removeProperty("--custom-channel-textarea-text-area-height")')
    page.locator('#editor').fill('Offline fixture text — never sent')
    result['composerAlignment'] = cases
    forum_cases = []
    for width, font in ((800, 16), (1280, 20)):
        page.set_viewport_size({'width': width, 'height': 1000})
        page.evaluate('(font)=>document.documentElement.style.fontSize=font+"px"', font)
        for height in (44, 88):
            page.locator('#forum-area').evaluate('(e,height)=>e.style.setProperty("--custom-channel-textarea-text-area-height",height+"px")', height)
            for state, text in (('placeholder', ''), ('single', 'Enter a message sample')):
                page.locator('#forum-editor').fill(text)
                metrics = page.evaluate(FORUM_METRICS)
                name = f'forum composer {width}px / root {font}px / height {height}px / {state}'
                check(name + ': prompt and first glyph align', abs(metrics['delta']) < .1, metrics)
                check(name + ': prompt shares the zeroed first-line padding', metrics['promptTop'] == metrics['paddingTop'] == '0px' and metrics['promptFont'] == metrics['editorFont'] == metrics['placeholderFont'])
                check(name + ': prompt stays left of the text', metrics['gap'] > 2, metrics)
                check(name + ': prompt cannot intercept clicks', metrics['promptPointerEvents'] == 'none')
                forum_cases.append({'width': width, 'rootFont': font, 'height': height, 'state': state, **metrics})
    centered = page.add_style_tag(content='.channelTextArea__74017 .textArea__74017:has(.textAreaForPostCreation__74017)::before{top:calc((var(--custom-channel-textarea-text-area-height) - var(--chat-markup-line-height)) / 2)}')
    page.locator('#forum-editor').fill('')
    check('forum composer negative control reproduces the centering offset', abs(page.evaluate(FORUM_METRICS)['delta']) > 2)
    centered.evaluate('(e)=>e.remove()')
    page.set_viewport_size({'width': 1280, 'height': 1000})
    page.evaluate('document.documentElement.style.fontSize="16px"')
    page.locator('#forum-area').evaluate('(e)=>e.style.removeProperty("--custom-channel-textarea-text-area-height")')
    page.locator('#forum-editor').fill('')
    result['forumComposerAlignment'] = forum_cases


def grouped_timestamp_regression(page, check, result):
    """The tightened cozy inset must not land on the gutter timestamp."""
    page.locator('#grouped-message').scroll_into_view_if_needed()
    metrics = page.evaluate(r"""() => {
      const time = document.querySelector('#grouped-time'), text = document.querySelector('#grouped-text');
      const glyph = element => {
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        let node;
        while (node = walker.nextNode()) {
          if (node.textContent.length) {
            const range = document.createRange();
            range.setStart(node, 0);
            range.setEnd(node, node.textContent.length);
            return range.getBoundingClientRect();
          }
        }
        return null;
      };
      const timeBox = glyph(time), textBox = glyph(text);
      return {gap: textBox.x - timeBox.right, timeWidth: getComputedStyle(time).width, contentInset: getComputedStyle(time.closest('.wrapper_c19a55')).paddingInlineStart};
    }""")
    check('grouped timestamp stays clear of the message', metrics['gap'] > 8, metrics)
    forced = page.add_style_tag(content='.cozy_c19a55 .timestamp_c19a55.alt_c19a55{width:56px}')
    collapsed = page.evaluate(r"""() => {
      const time = document.querySelector('#grouped-time'), text = document.querySelector('#grouped-text');
      const box = element => { const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT); const node = walker.nextNode(); const range = document.createRange(); range.setStart(node, 0); range.setEnd(node, node.textContent.length); return range.getBoundingClientRect(); };
      return box(text).x - box(time).right;
    }""")
    check('grouped timestamp negative control reproduces the missing gap', collapsed < 4, collapsed)
    forced.evaluate('(e)=>e.remove()')
    result['groupedTimestamp'] = metrics


METRICS = r"""() => {
 const rgba=value=>{const c=document.createElement('canvas');c.width=c.height=1;const x=c.getContext('2d');x.fillStyle=value;x.fillRect(0,0,1,1);return [...x.getImageData(0,0,1,1).data].map((v,i)=>i===3?v/255:v);};
 const style=selector=>getComputedStyle(document.querySelector(selector));
 const box=selector=>{const r=document.querySelector(selector).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};
 const luminance=c=>c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
 const contrast=(a,b)=>{a=luminance(a);b=luminance(b);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);};
 const effectiveBackground=element=>{for(let e=element;e;e=e.parentElement){const c=rgba(getComputedStyle(e).backgroundColor);if(c[3]>.98)return c;}return rgba(getComputedStyle(document.querySelector('#canvas')).backgroundColor);};
 const pair=selector=>{const element=document.querySelector(selector),s=getComputedStyle(element),fg=rgba(s.color),bg=effectiveBackground(element);return {color:s.color,background:s.backgroundColor,contrast:contrast(fg,bg),alpha:rgba(s.backgroundColor)[3]};};
 const media={};for(const selector of ['#media','#video','#activity','#avatar','#decoration','#nameplate','#friend-stream','#friend-stream-wrapper','#product-art']){const s=style(selector);let opacity=1;for(let e=document.querySelector(selector);e;e=e.parentElement)opacity*=Number(getComputedStyle(e).opacity);media[selector]={filter:s.filter,opacity:s.opacity,effectiveOpacity:opacity,maskImage:s.maskImage,clipPath:s.clipPath,backgroundImage:s.backgroundImage,borderRadius:s.borderRadius,aspectRatio:s.aspectRatio,overflow:s.overflow};}
 const nested={};for(const selector of ['html','body','#app-mount','#shell','.sidebar__5e434','.chat_f75fb0','.members_c8ffbb'])nested[selector]=rgba(style(selector).backgroundColor)[3];
 const profile=selector=>{const s=style(selector+' .inner_c0bea0'),text=style(selector+' h2').color;return {background:s.backgroundImage,text,contrastStart:contrast(rgba(text),rgba(s.getPropertyValue('--profile-gradient-start'))),contrastEnd:contrast(rgba(text),rgba(s.getPropertyValue('--profile-gradient-end')))};};
 const controls={};for(const selector of ['#primary','#danger','#focused-menu','#focused-label','#focused-subtext','#focused-caret','#focused-check','#modal-footer'])controls[selector]=pair(selector);
 const modal={...pair('#modal .markup__75297'),alpha:rgba(style('#modal').backgroundColor)[3]};
 const menu={...pair('#menu .markup__75297'),alpha:rgba(style('#menu').backgroundColor)[3]};
 const geometry={};for(const selector of ['#friend-row','#friend-action','#activity-card','#bd-notification','.bd-notification-content','.bd-notification-footer','#bd-progress'])geometry[selector]={radius:style(selector).borderRadius,shadow:style(selector).boxShadow,...box(selector)};
 const friends={addFriend:pair('#add-friend'),selectedTab:pair('#friends-online'),tabMarker:style('#friends-online').boxShadow,navMarker:style('#friends-nav').boxShadow,premiumName:{color:style('#premium-name').color,font:style('#premium-name').fontFamily},notification:pair('#bd-notification .bd-notification-content-text'),notificationAlpha:rgba(style('#bd-notification').backgroundColor)[3],progressColor:style('#bd-progress').backgroundColor,geometry};
 const switchTrack=style('#switch-track'),switchKnob=style('#switch-knob');
 const audited={pickerSurface:pair('#picker-surface'),pickerSurfaceColor:rgba(style('#picker-surface').backgroundColor),expectedSurface:rgba(style('html').getPropertyValue('--yuru-surface')),pickerActive:pair('#picker-active'),pickerActiveColor:rgba(style('#picker-active').color),settingsActiveColor:rgba(style('#settings-active').color),pickerMarker:style('#picker-active').boxShadow,pickerSearchBorder:rgba(style('#picker-search').borderTopColor),expectedMint:rgba(style('html').getPropertyValue('--yuru-mint')),expectedBackground:rgba(style('html').getPropertyValue('--yuru-bg')),expectedForeground:rgba(style('html').getPropertyValue('--yuru-fg')),pickerOutsideApp:!document.querySelector('#picker-portal').closest('#app-mount'),pickerLightProfile:profile('#picker-light-profile'),settingsMarker:style('#settings-active').boxShadow,switch:{track:switchTrack.backgroundColor,knob:switchKnob.fill,trackColor:rgba(switchTrack.backgroundColor),knobColor:rgba(switchKnob.fill),contrast:contrast(rgba(switchTrack.backgroundColor),rgba(switchKnob.fill)),...box('#switch-track'),checked:document.querySelector('#switch-input').checked},disabledSwitch:{checked:document.querySelector('#disabled-switch-input').checked,disabled:document.querySelector('#disabled-switch-input').disabled,...box('#disabled-switch-track')},readonlyPrompt:getComputedStyle(document.querySelector('#readonly-text-area'),'::before').content,enabledPrompt:getComputedStyle(document.querySelector('.fixture-chat .textArea__74017'),'::before').content,productRadii:['#product-shell','#product-container','#product-card'].map(q=>style(q).borderRadius)};
 return {viewport:{width:innerWidth,height:innerHeight},rootFont:style('html').fontSize,messageFont:style('#message-text').fontSize,headerLine:style('.header_c19a55').lineHeight,bodyScroll:document.body.scrollWidth,canvasAlpha:rgba(style('#canvas').backgroundColor)[3],nested,modal,menu,controls,friends,audited,role:style('#role-name').color,spoilerOpacity:style('#spoiler-secret').opacity,media,avatar:box('#avatar'),decoration:box('#decoration'),message:box('#message'),editor:box('#editor'),lightProfile:profile('#light-profile'),darkProfile:profile('#dark-profile'),lightPreviewText:style('#light-preview-text').color,disabled:document.querySelector('#disabled').disabled};
}"""


def verify_navigation(browser_path):
    """Exercise semantic controls and app canvas under native resets/hash changes."""
    from theme import render
    palette = json.loads((ROOT / 'palette.json').read_text())
    css = render((ROOT / 'templates/discord/YuruKitty.theme.css').read_text(), palette)
    fixture = """<html class="theme-dark"><style>
      .boundary {--control-primary-background-default:#5865f2;--control-primary-background-hover:#4452bb;
       --text-brand:#5865f2;--background-mod-strong:rgba(88,101,242,.16)}
      .native.native.native {background:var(--control-primary-background-default);color:white}
      .native.native.native:hover {background:var(--control-primary-background-hover);color:white}
      .native.native.native[aria-selected=true] {background:var(--background-mod-strong);color:var(--text-brand)}
      [role=tab] {display:inline-block;padding:8px;outline:2px solid transparent}
      [role=tab]:focus-visible {outline-color:#abcdef}
      #profile {--text-normal:#152030;background:white;color:var(--text-normal)}
    </style><section class="theme-dark boundary"><nav role="tablist">
      <div id="online" role="tab" tabindex="0" data-tab-id="ONLINE" aria-selected="true">Online</div>
      <div id="cta" role="tab" tabindex="0" data-tab-id="ADD_FRIEND" class="native" aria-selected="false">Add Friend</div>
    </nav></section><section class="theme-light" id="profile">Unrelated profile</section></html>"""
    report = {'fixture': 'authored semantic controls and app layouts; no account data', 'checks': []}
    def check(name, condition):
        report['checks'].append({'name': name, 'passed': bool(condition)})
    with sync_playwright() as engine:
        browser = engine.chromium.launch(executable_path=str(browser_path), headless=True,
                                          args=['--no-sandbox', '--disable-dev-shm-usage'])
        page = browser.new_page()
        page.set_content(fixture)
        def colors(selector):
            return page.locator(selector).evaluate('(e)=>{const s=getComputedStyle(e);return {background:s.backgroundColor,color:s.color,radius:s.borderRadius,shadow:s.boxShadow}}')
        baseline_profile = colors('#profile')
        check('native default reproduces blue CTA', colors('#cta')['background'] == 'rgb(88, 101, 242)')
        page.add_style_tag(content=css)
        def resolved(name):
            return page.evaluate('(name)=>{const e=document.createElement("i");e.style.color="var("+name+")";document.body.append(e);const c=getComputedStyle(e).color;e.remove();return c}', name)
        mint, background = resolved('--yuru-mint'), resolved('--yuru-bg')
        for suffix in ('old_hash', 'current_hash', 'unknown_future_hash'):
            page.locator('#cta').evaluate('(e,s)=>e.className="native addFriend_"+s', suffix)
            for state in ('normal', 'hover', 'selected', 'selected-hover'):
                page.locator('#cta').evaluate('(e,s)=>e.setAttribute("aria-selected",String(s))', state.startswith('selected'))
                page.mouse.move(900, 600)
                if 'hover' in state:
                    page.locator('#cta').hover()
                actual = colors('#cta')
                label = suffix + '/' + state
                check(label + ': paired Yuru foreground', actual['color'] == (mint if state.startswith('selected') else background))
                check(label + ': native blue/white reset does not win', actual['background'] not in ('rgb(88, 101, 242)', 'rgb(68, 82, 187)'))
                check(label + ': corners stay square', actual['radius'] == '0px')
        check('selected Online uses mint marker', mint in colors('#online')['shadow'])
        check('unrelated nested profile remains unchanged', colors('#profile') == baseline_profile)
        page.locator('#cta').focus()
        check('keyboard focus remains visible', page.locator('#cta').evaluate('(e)=>document.activeElement===e&&getComputedStyle(e).outlineColor==="rgb(171, 205, 239)"'))
        page.locator('#cta').evaluate('(e)=>{e.removeAttribute("data-tab-id");e.setAttribute("aria-selected","false")}')
        page.mouse.move(900, 600)
        check('unknown semantic identity falls back to native appearance', colors('#cta')['background'] == 'rgb(88, 101, 242)')
        # The Electron window can be ARGB while opaque application layers hide
        # its alpha. Hash-independent owner scoping must clear only layout paint.
        for suffix in ('old_hash', 'current_hash', 'future_hash'):
            layout = f"""<html><style>.paint {{background:#1e191f;background-image:linear-gradient(#1e191f,#1e191f)}}
              #popup {{background:#123456}} #profile-bg {{background:#abcdef;color:#152030}}</style>
              <div id="app-mount"><div class="app_{suffix} paint" id="app-shell">
              <div class="bg_{suffix} paint" id="canvas"></div><div class="layers_{suffix} paint" id="layers">
              <div class="layer_{suffix} paint" id="layer"><div class="sidebar_{suffix}">
                <nav class="wrapper_{suffix} guilds_{suffix} paint" id="guilds"><div role="tree" class="tree_{suffix} paint" id="guild-tree"></div></nav>
                <div class="sidebarList_{suffix}"><nav class="container_{suffix} paint" id="channel-nav"></nav></div>
                <section class="panels_{suffix} paint" id="account-panel"></section></div>
              <div class="chat_{suffix} paint" id="chat-shell">
                <div class="subtitleContainer_{suffix}"><section class="title_{suffix} paint" id="chat-header"></section></div>
                <div class="content_{suffix} paint" id="chat-content"><main class="chatContent_{suffix} paint" id="messages"></main>
                <div class="container_{suffix} paint" id="member-container"><aside class="membersWrap_{suffix} paint" id="member-wrap"><div class="members_{suffix} paint" role="list" id="members"></div></aside></div></div></div>
              <main class="container_{suffix} paint" id="friends-main"><section role="navigation"><div role="tablist"><div role="tab" data-tab-id="ADD_FRIEND"></div></div></section></main>
              <div id="popup" role="dialog">Opaque popup</div><section class="theme-light"><div class="bg_{suffix}" id="profile-bg">Profile background</div></section>
              </div></div></div></div></html>"""
            page.set_content(layout)
            popup, profile = colors('#popup'), colors('#profile-bg')
            check(suffix + ': negative control has opaque application layers', colors('#app-shell')['background'] == 'rgb(30, 25, 31)')
            page.add_style_tag(content=css)
            for selector in ('#app-shell', '#layers', '#layer', '#guilds', '#guild-tree', '#channel-nav',
                             '#account-panel', '#chat-shell', '#chat-header', '#chat-content', '#messages',
                             '#member-container', '#member-wrap', '#members', '#friends-main'):
                painted = page.locator(selector).evaluate('(e)=>{const s=getComputedStyle(e);return [s.backgroundColor,s.backgroundImage]}')
                check(suffix + selector + ': layout cannot hide desktop alpha', painted == ['rgba(0, 0, 0, 0)', 'none'])
            alpha = page.locator('#canvas').evaluate('(e)=>{const c=document.createElement("canvas").getContext("2d");c.fillStyle=getComputedStyle(e).backgroundColor;c.fillRect(0,0,1,1);return c.getImageData(0,0,1,1).data[3]}')
            check(suffix + ': exactly one .80 alpha canvas', alpha == 204)
            check(suffix + ': popup paint remains opaque', colors('#popup')['background'] == popup['background'])
            check(suffix + ': unrelated profile bg module is not recolored', colors('#profile-bg') == profile)
        browser.close()
    report['passed'] = sum(item['passed'] for item in report['checks'])
    report['failed'] = len(report['checks']) - report['passed']
    (ROOT / 'verification/discord-compatibility.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(bool(report['failed']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--navigation-only', '--compatibility-only', action='store_true')
    parser.add_argument('--discord-css', required=False, type=Path, help='Public native Discord CSS; never copied into the repository')
    parser.add_argument('--betterdiscord-css', required=False, type=Path, help='Public BD CSS capture; only notification/toast rules are used')
    parser.add_argument('--browser', type=Path, default=Path('/opt/google/chrome/chrome'))
    args = parser.parse_args()
    if args.navigation_only:
        verify_navigation(args.browser)
    if not args.discord_css or not args.betterdiscord_css:
        parser.error('--discord-css and --betterdiscord-css are required for the full component suite')
    native = args.discord_css.read_text()
    bd_components = betterdiscord_components(args.betterdiscord_css.read_text())
    theme = (ROOT / 'build/discord/YuruKitty.theme.css').read_text()
    errors = [item.message for item in tinycss2.parse_stylesheet(theme, skip_comments=True, skip_whitespace=True) if item.type == 'error']
    result = {'fixture': 'authored offline component contracts; no account data or real entitlement calls',
              'verifiedAt': datetime.now(timezone.utc).isoformat(),
              'limitations': ['Does not emulate Discord React logic, server APIs, checkout, uploads, streaming or Nitro entitlement.',
                              'SVG/media/iframe sentinels establish CSS preservation, not playback or activity functionality.',
                              'Animations and transitions are disabled for stable measurements and screenshots; runtime motion is not verified.',
                              'Root font scaling is simulated; real accessibility preferences require live verification.'],
              'nativeCssSha256': hashlib.sha256(native.encode()).hexdigest(),
              'betterDiscordComponentCssSha256': hashlib.sha256(bd_components.encode()).hexdigest(),
              'cssProvenance': 'Native CSS is the supplied official linked-stylesheet capture. BetterDiscord notification/toast rules alone are parsed from the separate public BD capture; captured Yuru styles are excluded.',
              'themeCssSha256': hashlib.sha256(theme.encode()).hexdigest(),
              'checks': [], 'cases': []}

    def check(name, condition, detail=None):
        result['checks'].append({'name': name, 'passed': bool(condition), **({'detail': detail} if detail is not None else {})})

    check('theme CSS parses without syntax errors', not errors, errors)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(args.browser), headless=True,
                                    args=['--no-sandbox', '--disable-dev-shm-usage'])
        result['browserVersion'] = browser.version
        context = browser.new_context(viewport={'width': 1280, 'height': 1000}, offline=True,
                                      reduced_motion='reduce', color_scheme='dark')
        context.route('**/*', lambda route: route.abort())
        page = context.new_page()
        page.set_content(SAMPLE.read_text(), wait_until='domcontentloaded')
        layout = page.locator('head style').text_content()
        page.add_style_tag(content=native)
        page.add_style_tag(content=bd_components)
        page.add_style_tag(content=layout)
        # Freeze transition interpolation before comparing computed colors.
        page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important}')
        page.evaluate("document.documentElement.style.fontSize='16px'")
        baseline = page.evaluate(METRICS)
        page.add_style_tag(content=theme)
        for width, font in [(800, 16), (800, 20), (1280, 16), (1280, 20), (1600, 16), (1600, 20)]:
            page.set_viewport_size({'width': width, 'height': 1000})
            page.evaluate('(font)=>document.documentElement.style.fontSize=font+"px"', font)
            metrics = page.evaluate(METRICS)
            result['cases'].append(metrics)
            name = f'{width}px / root {font}px'
            check(name + ': no horizontal document overflow', metrics['bodyScroll'] <= width, metrics['bodyScroll'])
            check(name + ': exactly one translucent canvas', .78 <= metrics['canvasAlpha'] <= .82 and all(v == 0 for v in metrics['nested'].values()), metrics['nested'])
            check(name + ': opaque readable modal and menu', metrics['modal']['alpha'] == 1 and metrics['menu']['alpha'] == 1 and metrics['modal']['contrast'] >= 4.5 and metrics['menu']['contrast'] >= 4.5, {'modal': metrics['modal'], 'menu': metrics['menu']})
            for selector, pair in metrics['controls'].items():
                check(name + ': paired control contrast ' + selector, pair['contrast'] >= 4.5, round(pair['contrast'], 2))
            check(name + ': explicit role color retained', metrics['role'] == baseline['role'], metrics['role'])
            check(name + ': media/decoration/nameplate styling untouched', metrics['media'] == baseline['media'])
            check(name + ': paid profile gradients/text preserved', metrics['lightProfile'] == baseline['lightProfile'] and metrics['darkProfile'] == baseline['darkProfile'], {'light': metrics['lightProfile'], 'dark': metrics['darkProfile']})
            check(name + ': paid profile text contrasts both gradient ends', all(metrics[profile][end] >= 4.5 for profile in ('lightProfile', 'darkProfile') for end in ('contrastStart', 'contrastEnd')))
            check(name + ': native light theme preview retained', metrics['lightPreviewText'] == baseline['lightPreviewText'], metrics['lightPreviewText'])
            avatar, decoration = metrics['avatar'], metrics['decoration']
            check(name + ': avatar decoration ratio retained', abs(decoration['width'] / avatar['width'] - 1.2) < .02, {'avatar': avatar, 'decoration': decoration})
            check(name + ': decoration centered horizontally', abs(avatar['x'] + avatar['width']/2 - decoration['x'] - decoration['width']/2) < 1)
            check(name + ': decoration centered vertically', abs(avatar['y'] + avatar['height']/2 - decoration['y'] - decoration['height']/2) < 1)
            message = metrics['message']
            check(name + ': decoration fits message geometry', decoration['x'] >= message['x'] and decoration['y'] >= message['y'] - 1 and decoration['y'] + decoration['height'] <= message['y'] + message['height'] + 1)
            check(name + ': disabled control remains disabled', metrics['disabled'])
            check(name + ': spoiler remains concealed', float(metrics['spoilerOpacity']) < .01)
            check(name + ': editor has usable geometry', metrics['editor']['width'] > 120 and metrics['editor']['height'] >= 32)
            friends = metrics['friends']
            check(name + ': native high-specificity Add Friend CTA contrast', friends['addFriend']['contrast'] >= 4.5, round(friends['addFriend']['contrast'], 2))
            check(name + ': selected Friends tab/nav have cursor markers', 'inset' in friends['tabMarker'] and 'inset' in friends['navMarker'])
            check(name + ': selected DM premium name color/font retained', friends['premiumName'] == baseline['friends']['premiumName'])
            check(name + ': activity and notification shells are square', all(item['radius'] == '0px' for item in friends['geometry'].values()))
            action = friends['geometry']['#friend-action']
            check(name + ': Friend action keeps native 36px hit target', action['width'] == 36 and action['height'] == 36)
            check(name + ': activity card has no added shadow', friends['geometry']['#activity-card']['shadow'] == 'none')
            check(name + ': BetterDiscord notification stays opaque/readable', friends['notificationAlpha'] == 1 and friends['notification']['contrast'] >= 4.5)
            check(name + ': notification severity progress color retained', friends['progressColor'] == baseline['friends']['progressColor'])
            audited = metrics['audited']
            check(name + ': portalled picker resets to opaque Yuru surface', audited['pickerOutsideApp'] and audited['pickerSurface']['alpha'] == 1 and audited['pickerSurfaceColor'] == audited['expectedSurface'])
            check(name + ': picker active tab/settings have mint markers', 'inset' in audited['pickerMarker'] and 'inset' in audited['settingsMarker'] and audited['pickerActiveColor'] == audited['expectedMint'] and audited['settingsActiveColor'] == audited['expectedMint'])
            check(name + ': picker nested light profile stays native', audited['pickerLightProfile'] == baseline['audited']['pickerLightProfile'])
            check(name + ': checked modern switch overrides inline blue/white pair', audited['switch']['contrast'] >= 4.5 and audited['switch']['trackColor'] == audited['expectedMint'] and audited['switch']['knobColor'] == audited['expectedBackground'])
            check(name + ': modern switch retains native hit geometry', audited['switch']['width'] == baseline['audited']['switch']['width'] and audited['switch']['height'] == baseline['audited']['switch']['height'])
            check(name + ': disabled modern switch keeps checked/disabled semantics', audited['disabledSwitch']['checked'] and audited['disabledSwitch']['disabled'] and audited['disabledSwitch']['width'] == baseline['audited']['disabledSwitch']['width'] and audited['disabledSwitch']['height'] == baseline['audited']['disabledSwitch']['height'])
            check(name + ': read-only composer has no decorative prompt', audited['readonlyPrompt'] == 'none' and audited['enabledPrompt'] == '">"')
            check(name + ': product shells are square', all(radius == '0px' for radius in audited['productRadii']))
        sizes = {case['viewport']['width']: [] for case in result['cases']}
        for case in result['cases']:
            sizes[case['viewport']['width']].append(float(case['messageFont'].removesuffix('px')))
        for width, values in sizes.items():
            check(f'{width}px: messages follow root accessibility scale', abs(values[1] / values[0] - 1.25) < .02, values)
        page.set_viewport_size({'width': 1280, 'height': 1000})
        page.evaluate("document.documentElement.style.fontSize='16px'")
        for namespace in ('theme-dark', 'theme-darker', 'theme-midnight', 'theme-light'):
            page.evaluate('(name)=>document.documentElement.className=name+" mouse-mode full-motion"', namespace)
            metrics = page.evaluate(METRICS)
            check(namespace + ': main canvas stays translucent', .78 <= metrics['canvasAlpha'] <= .82)
            check(namespace + ': native nested paid palettes remain scoped', metrics['lightProfile'] == baseline['lightProfile'] and metrics['darkProfile'] == baseline['darkProfile'])
            check(namespace + ': ordinary controls remain readable', all(pair['contrast'] >= 4.5 for pair in metrics['controls'].values()))
        page.evaluate('document.documentElement.className="theme-dark mouse-mode full-motion"')
        page.locator('#picker-search-input').fill('Authored emoji search')
        focused_picker = page.evaluate(METRICS)['audited']
        check('portalled picker search accepts text and mint focus', page.locator('#picker-search-input').input_value() == 'Authored emoji search' and focused_picker['pickerSearchBorder'] == focused_picker['expectedMint'])
        page.locator('#switch-label').click()
        off_audit = page.evaluate(METRICS)['audited']
        off = off_audit['switch']
        check('modern native switch toggles off with dark track/cream knob', not off['checked'] and off['contrast'] >= 4.5 and off['trackColor'] == off_audit['expectedBackground'] and off['knobColor'] == off_audit['expectedForeground'])
        page.locator('#switch-label').click()
        check('modern native switch toggles back on', page.locator('#switch-input').is_checked())
        page.locator('#switch-input').focus()
        check('modern switch has visible keyboard focus', page.locator('#switch-track').evaluate('(e)=>{const s=getComputedStyle(e);return s.outlineStyle!=="none"&&parseFloat(s.outlineWidth)>=1}'))
        # Intentionally bypass automation's enabled check to test the browser's
        # native disabled-input behavior under an actual pointer click.
        page.locator('#disabled-switch-label').click(force=True)
        check('disabled modern switch does not toggle on label click', page.locator('#disabled-switch-input').is_checked() and page.locator('#disabled-switch-input').is_disabled())
        check('read-only composer remains noneditable', not page.locator('#readonly-editor').is_editable())
        for state in ('normal', 'hover', 'pressed', 'selected', 'selected-hover'):
            page.locator('#add-friend').evaluate('(e,selected)=>e.setAttribute("aria-selected",String(selected))', state.startswith('selected'))
            if state != 'normal':
                page.locator('#add-friend').hover()
            else:
                page.mouse.move(0, 0)
            if state == 'pressed':
                page.mouse.down()
            cta = page.evaluate(METRICS)['friends']['addFriend']
            check('Add Friend ' + state + ': paired contrast', cta['contrast'] >= 4.5, round(cta['contrast'], 2))
            if state.startswith('selected'):
                check('Add Friend ' + state + ': selected tab is not filled CTA', cta['alpha'] < 1)
            if state == 'pressed':
                page.mouse.up()
        page.locator('#add-friend').evaluate('(e)=>e.setAttribute("aria-selected","false")')
        for selector in ('#primary', '#danger'):
            page.locator(selector).hover()
            hovered = page.evaluate(METRICS)['controls'][selector]
            check(selector + ': hover contrast remains paired', hovered['contrast'] >= 4.5, round(hovered['contrast'], 2))
            page.mouse.down()
            pressed = page.evaluate(METRICS)['controls'][selector]
            check(selector + ': pressed contrast remains paired', pressed['contrast'] >= 4.5, round(pressed['contrast'], 2))
            page.mouse.up()
        page.evaluate('window.fixtureClicks=0')
        page.locator('#editor').click()
        page.locator('#editor').fill('Offline fixture text — never sent')
        check('editor accepts click and text entry', page.locator('#editor').inner_text() == 'Offline fixture text — never sent')
        page.locator('#reaction').click()
        check('reaction remains clickable', page.locator('#reaction').inner_text() == '✨ 3')
        page.locator('#spoiler').click()
        page.wait_for_timeout(150)
        check('spoiler reveal remains functional', float(page.locator('#spoiler-secret').evaluate('(e)=>getComputedStyle(e).opacity')) == 1)
        page.locator('#disabled').evaluate('(e)=>e.click()')
        check('disabled button did not dispatch click', page.evaluate('window.fixtureClicks') == 1)
        page.locator('#bd-update').click()
        check('authored notification action remains clickable', page.evaluate('window.fixtureUpdateActions') == 1)
        page.locator('#bd-close').click()
        check('authored notification close remains clickable', not page.locator('#bd-notification').is_visible())
        page.locator('#bd-notification').evaluate('(e)=>e.style.removeProperty("display")')
        page.evaluate("document.documentElement.classList.add('keyboard-mode');document.documentElement.classList.remove('mouse-mode')")
        page.locator('#focused-menu').focus()
        check('keyboard focus has visible native indicator', page.locator('#focused-menu').evaluate('(e)=>{const s=getComputedStyle(e);return document.activeElement===e&&s.outlineStyle!=="none"&&parseFloat(s.outlineWidth)>=1}'))
        sidebar_border_regression(page, theme, check, result)
        composer_regression(page, check, result)
        grouped_timestamp_regression(page, check, result)
        # Capture only authored public fixture content, never the live client.
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(ROOT / 'verification/native-discord.png'))
        page.locator('#components').screenshot(path=str(ROOT / 'verification/discord-components.png'))
        context.close()
        browser.close()
    result['passed'] = sum(check['passed'] for check in result['checks'])
    result['failed'] = len(result['checks']) - result['passed']
    destination = ROOT / 'verification/discord.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(f"Discord authored fixture: {result['passed']} passed, {result['failed']} failed; {destination}")
    for item in result['checks']:
        if not item['passed']:
            print('FAIL:', item['name'], item.get('detail', ''))
    raise SystemExit(bool(result['failed']))


if __name__ == '__main__':
    main()
