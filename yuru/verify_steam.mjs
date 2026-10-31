#!/usr/bin/env node
/** Isolated Chromium regression fixture; never connects to the running Steam client.
 * Run after `python theme.py build`: node verify_steam.mjs [--output-dir DIR].
 * Native source CSS is intentionally loaded before the generated theme: these
 * checks exercise real cascade, pseudo elements, fonts and box geometry.
 */
import { spawn } from 'node:child_process';
import { access, mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { tmpdir, homedir } from 'node:os';
import { dirname, resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const root = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
if (args.length && (args[0] !== '--output-dir' || args.length !== 2)) {
  throw new Error('Usage: node verify_steam.mjs [--output-dir DIR]');
}
const output = resolve(args[1] ?? join(root, 'verification'));
const native = join(homedir(), '.local/share/Steam/steamui/css');
const sources = [join(native, 'library.css'), join(native, 'sp.css'), join(root, 'build/steam/client.css')];
await Promise.all(sources.map(p => access(p)));
const palette = JSON.parse(await readFile(join(root, 'palette.json'), 'utf8'));
const working = await mkdtemp(join(tmpdir(), 'yuru-steam-render-'));
const widths = [777, 1280, 1600];
const c = {
  top: '_3Z7VQ1IMk4E3HsHvrkLNgo', title: '_39oUCO1OuizVPwcnnv88no',
  rail: '_3Z3ohQ8-1NKnCZkbS6fvy', nav: '_2D64jIEK7wpUR_NlObDW76',
  menu: '_7AlhCx3XGzBeIrQaCneUD', label: '_19axKcqYRuaJ8vdYKYmtTQ', selected: '_1gqEjB5QsKT_NftD1dEsdZ',
  browser: '_1bGewp3tfzqAF6fVTFFUOz', address: 'UkR3sY319PuaUNuUWks2K', reload: '_3KaB94Jl4r0hFkthDPJy09',
  addressText: '_2m_orETo6AghzAnc0sISCt', url: 'MZPxEZcxAGtPDf1NYtouS', certError: '_2T8z7cCQDhMeevnGu74365',
  search: '_20QAC4WMXm8qFE8waUT5oo', searchInput: '_12vo5L1hsNGdao6_ssuirS', clear: '_38tIMc-4Ug-Akpa1pYlN0R',
  dropdown: '_1ZpBQtDqcKBbfIIv01Vs1R', dropdownItem: '_1ZtpSq62fy_8W-_0pMn5cu',
  context: '_2EstNjFIIZm_WUSKm5Wt7n', contextItem: '_1n7Wloe5jZ6fSuvV18NNWI',
  selectMenu: '_30wJO3MC4x-I1OWpy1TAeE', selectItem: '_2oAiZidGyUxL-hfupFDQ2m',
  footer: '_3vCzSrrXZzZjVJFZNg9SGu', download: '_2EQ7ghgqIdjKv9jsQC0Zq9', downloadContent: 'ip-YZhijAMZcuRoXBGiye',
  detail: '_2VtAqT03BpBsVdmxwptn9D', progressWrapper: '_2_FomluqqgQ2Hx8ON3AVep', statusLine: '_1xCcFYWIrJ7W8WRDmGvR3y',
  status: '_1sCy-pm412Smb0wJx0W-4', percent: '_1-TLiuTZBQNz2fvBGj6aq-', bar: 'wi0pDywRgOCxhG7OqQNaA', track: '_3szjUMH5QeRwtXAsLRcWt9',
};
const fixture = `<!doctype html><html class="DesktopUI"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' file:; font-src file: data:; img-src file: data:; connect-src 'none'">
${sources.map(p => `<link rel="stylesheet" href="${pathToFileURL(p).href}">`).join('\n')}
<style>
/* Harness placement only: no tested colors, font families, control heights or
   pseudo-element styles are supplied here. Native/theme CSS owns those. */
html,body{margin:0;width:100%;min-height:100%;}body{display:flex;flex-direction:column;min-height:850px}
#workspace{flex:1;padding:20px;display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}
.fixture-panel{width:300px;max-width:100%;}#search-panel{width:340px}.fixture-note{margin:10px 0;font-size:12px}
#dropdown{margin-inline-start:0;min-width:230px;position:relative;transform:none}#cover{width:220px;height:130px;position:relative}
#cover ._3CMVjtuNkVqNt8MqgR3j3j{position:relative;inset:auto}#footer{flex-shrink:0}#browser{flex-shrink:0}
#placeholder-host{flex:none}
</style></head><body class="DesktopUI">
<div id="top" class="${c.top}"><div id="title" class="${c.title}"><div class="_3s0lkohH8wU2do0K1il28Y"><div>Steam　View　Friends　Games　Help</div></div></div>
<div id="rail" class="${c.rail}"><div id="nav" class="${c.nav}">
${['STORE','LIBRARY','COMMUNITY'].map((name,i) => `<div id="tab-${i}" tabindex="0" class="${c.menu} ${i===1?c.selected:''}"><span id="label-${i}" class="${c.label}">${name}</span></div>`).join('')}
<div id="tab-disabled" tabindex="-1" class="${c.menu} _2cO0HdvLEGAdhosLekWsmo"><span id="label-disabled" class="${c.label}">OFFLINE</span></div>
</div></div></div>
<div id="placeholder-host" class="RGNMWtyj73_-WdhflrmuY"><div id="replacement" class="_2CmrnGY-Amtd83ScJkFvx2"></div></div>
<div id="browser" class="${c.browser}"><div id="address" class="${c.address}"><div id="reload" tabindex="0" class="${c.reload}">↻</div><div id="address-text" tabindex="0" class="${c.addressText}"><svg class="_3izqEKa-zuPIrUDSm1bRvf" width="14" height="14" viewBox="0 0 14 14"><rect x="3" y="5" width="8" height="7" fill="currentColor"/></svg><div id="url" class="${c.url}">https://store.steampowered.com/</div></div></div></div>
<main id="workspace"><section id="search-panel" class="fixture-panel"><div class="fixture-note">Library search / native fixed cover metrics</div>
<div id="search" class="${c.search}"><div id="search-input" class="${c.searchInput}"><div id="input-wrapper" class="DialogInput_Wrapper"><input id="input" class="DialogInput DialogTextInputBase" type="text" placeholder="Search games 검색" value="Library 검색"></div></div><div class="${c.clear}">×</div></div>
<div id="cover" class="_3vyTQYwBNtW_e953TTBg9D"><div id="cover-text" class="_3CMVjtuNkVqNt8MqgR3j3j"><span>Native generated cover<br>게임 제목</span></div></div></section>
<section class="fixture-panel"><div class="fixture-note">Supernav dropdown (native !important child)</div><div id="dropdown" class="${c.dropdown}"><div id="dropdown-surface"><div id="dropdown-first" tabindex="0" class="${c.dropdownItem} Focusable">Featured 추천</div><div tabindex="0" class="${c.dropdownItem} Focusable">Collections</div></div></div>
<div class="fixture-note">Native dropdown keyboard focus</div><div id="select-menu" class="${c.selectMenu} _DialogInputContainer"><button id="select-first" class="${c.selectItem}">Alphabetical 이름순</button><button class="${c.selectItem}">Recently played</button></div></section>
<section class="fixture-panel"><div class="fixture-note">Context menu / disabled / keyboard navigation</div><div id="menu-frame" class="PP7LM0Ow1K5qkR8WElLpt visible" style="display:inline-block"><div id="context" class="${c.context}"><div id="context-first" tabindex="0" class="${c.contextItem}">Properties 속성</div><div id="context-disabled" tabindex="-1" class="${c.contextItem} disabled" aria-disabled="true">Unavailable</div><div id="context-aria-disabled" tabindex="-1" class="${c.contextItem}" aria-disabled="true">Unavailable (ARIA only)</div><div id="context-destructive" tabindex="0" class="_34o03-8cUc3fQX1u650c0L _1HXm3O7vOzyuTFDaKPNUxy">Remove shortcut</div></div></div></section></main>
<section id="primary-fixture" class="_2iE-78WxX2Pj4GHbq7YJiA" style="display:flex;gap:24px;padding:20px">
${[['install',''],['play','_3cI5TXsFX3bvpR-7EBOtxq'],['unavailable','_1Pb6PMh_3L5p5NzuUz0Pp9 _3cI5TXsFX3bvpR-7EBOtxq']].map(([id,state])=>`<div class="_1FnJ6dPuknQFQ2RTpKTI16 ${state}"><div id="primary-${id}" class="_3ydigb6zZAjJ0JCDgHwSYA _2AzIX5kl9k6JnxLfR5H4kX"><span class="_33cnXIqTRgRr49_FNXIHj6">${id}</span></div></div>`).join('')}
</section>
<div id="footer" class="${c.footer}"><div class="_2foCkpRXhqq0UGVE50BWqj">＋ Add a Game</div><div id="downloads" class="${c.download}"><div id="download-content" class="${c.downloadContent}"><div id="detail" class="${c.detail}"><div id="progress-wrapper" class="${c.progressWrapper}"><div id="status-line" class="${c.statusLine}"><div id="status" class="${c.status}">Patching 패치 중</div><div id="percent" class="${c.status} ${c.percent}">34%</div></div><div id="progress" class="${c.bar} ${c.track}" style="--percent:0.34"></div></div></div></div></div><div class="_1TdaAqMFadi0UTqilrkelR">Friends & Chat</div></div>
</body></html>`;

let chrome, ws;
let stderr = '';
const controller = new AbortController();
const deadline = setTimeout(() => controller.abort(new Error('Isolated Steam renderer exceeded 90 seconds')), 90000);
const checks = [];
const report = { date: new Date().toISOString(), scope: 'Isolated anonymized HTML fixture with installed native Steam CSS; no live Steam or login/reboot validation', sources, widths, checks };
report.sourceHashes = Object.fromEntries(await Promise.all(sources.map(async p => [p, createHash('sha256').update(await readFile(p)).digest('hex')])));
function expect(name, pass, details) { checks.push({ name, pass: !!pass, details }); }
function near(a, b, tolerance=1) { return Math.abs(a-b)<=tolerance; }
const rgb = hex => { const h=hex.slice(1); return `rgb(${[0,2,4].map(i=>parseInt(h.slice(i,i+2),16)).join(', ')})`; };
try {
  const html = join(working, 'steam-fixture.html');
  await writeFile(html, fixture);
  chrome = spawn('google-chrome-stable', ['--headless', '--disable-gpu', '--allow-file-access-from-files', '--remote-debugging-port=0', `--user-data-dir=${join(working,'profile')}`, '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update', '--disable-sync', '--disable-extensions', '--disable-default-apps', '--metrics-recording-only', '--host-resolver-rules=MAP * ~NOTFOUND', 'about:blank'], { stdio:['ignore','ignore','pipe'], signal:controller.signal });
  chrome.stderr.on('data', data => { stderr += data; });
  chrome.on('error', () => {});
  const active = join(working,'profile/DevToolsActivePort');
  let port;
  for (let i=0;i<200;i++) {
    if (controller.signal.aborted) throw controller.signal.reason;
    if (chrome.exitCode !== null) throw new Error(`Chrome exited before CDP was ready: ${stderr.slice(-1200)}`);
    try { port = (await readFile(active,'utf8')).split('\n')[0]; break; } catch {}
    await new Promise(r=>setTimeout(r,50));
  }
  if (!port) throw new Error('Chrome CDP port did not appear');
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`, {signal:controller.signal})).json();
  const target=targets.find(t=>t.type==='page');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res,rej) => { ws.addEventListener('open',res,{once:true}); ws.addEventListener('error',rej,{once:true}); });
  let next=0;
  const pending=new Map();
  ws.addEventListener('message',event => {const m=JSON.parse(event.data); if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}}});
  ws.addEventListener('close',()=>{for(const p of pending.values())p.reject(new Error('CDP closed'));pending.clear();});
  function call(method,params={}) {
    if(controller.signal.aborted) return Promise.reject(controller.signal.reason);
    return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
  }
  async function evaluate(expression) {
    const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
    if(r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  }
  await call('Page.enable'); await call('Runtime.enable'); await call('DOM.enable'); await call('CSS.enable'); await call('Network.enable');
  // A background headless target can update activeElement while :focus stays
  // false (document.hasFocus() is false). Emulate the active native popup window
  // explicitly; this preserves real CSS :focus matching instead of faking it.
  await call('Emulation.setFocusEmulationEnabled',{enabled:true});
  await call('Network.setBlockedURLs',{urls:['http://*','https://*','ws://*','wss://*']});
  await call('Page.navigate',{url:pathToFileURL(html).href});
  for(let i=0;i<100;i++) {if(await evaluate('document.readyState === "complete"'))break;await new Promise(r=>setTimeout(r,50));}
  await evaluate('document.fonts.ready.then(()=>true)');
  const inspect=`(id,pseudo=null)=>{const e=document.getElementById(id),s=getComputedStyle(e,pseudo),r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom,background:s.backgroundColor,color:s.color,font:s.fontFamily,fontSize:s.fontSize,lineHeight:s.lineHeight,shadow:s.boxShadow,textShadow:s.textShadow,radius:s.borderRadius,outline:s.outlineStyle,outlineWidth:s.outlineWidth,position:s.position,pseudoWidth:s.width,percent:s.getPropertyValue('--percent'),foreground:s.getPropertyValue('--color-progress-bar-foreground'),track:s.getPropertyValue('--color-progress-bar-background'),activeElement:document.activeElement?.id,documentFocused:document.hasFocus(),focus:e.matches(':focus'),focusVisible:e.matches(':focus-visible'),display:s.display,visibility:s.visibility,hiddenAncestors:Array.from((function*(n){while(n){yield n;n=n.parentElement}})(e)).filter(n=>{const t=getComputedStyle(n);return t.visibility!=='visible'||t.display==='none'||n.inert||n.hidden}).map(n=>({id:n.id,tag:n.tagName,classes:n.className,visibility:getComputedStyle(n).visibility,display:getComputedStyle(n).display,inert:n.inert,hidden:n.hidden}))}}`;
  async function metrics(ids){return evaluate(`Object.fromEntries(${JSON.stringify(ids)}.map(id=>[id,(${inspect})(id)]))`);}
  async function settle(){await evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');await new Promise(r=>setTimeout(r,180));}
  async function hover(id,enabled=true){const {root}=await call('DOM.getDocument');const {nodeId}=await call('DOM.querySelector',{nodeId:root.nodeId,selector:'#'+id});await call('CSS.forcePseudoState',{nodeId,forcedPseudoClasses:enabled?['hover']:[]});await settle();}
  const snapshots=[];
  for(const width of widths) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:850,deviceScaleFactor:1,mobile:false});
    await evaluate(`document.activeElement?.blur();document.getElementById('url').textContent='https://store.steampowered.com/';document.getElementById('url').classList.remove('${c.certError}')`);
    await settle();
    const m=await metrics(['title','rail','nav','tab-1','label-1','replacement','address','address-text','url','input','input-wrapper','search-input','dropdown-surface','context','context-disabled','progress-wrapper','status-line','status','percent','progress','cover-text','reload']);
    snapshots.push({width,metrics:m});
    const prefix=`${width}px`;
    expect(`${prefix}: isolated target has an active document focus context`,await evaluate('document.hasFocus()'),{focusEmulation:true});
    const top=m['tab-1'].y-m.rail.y,bottom=m.rail.bottom-m['tab-1'].bottom;
    expect(`${prefix}: navigation has balanced >=8px vertical space`,top>=7.9&&bottom>=7.9&&near(top,bottom),{top,bottom,rail:m.rail.height,tab:m['tab-1'].height});
    expect(`${prefix}: native title rail remains 32px`,near(m.title.height,32),m.title);
    expect(`${prefix}: selected label is centered`,near(m['label-1'].y+m['label-1'].height/2,m['tab-1'].y+m['tab-1'].height/2,1.5),{label:m['label-1'],tab:m['tab-1']});
    const underline=await evaluate(`(${inspect})('label-1','::after')`);
    expect(`${prefix}: underline consumes no label flow`,underline.position==='absolute'&&parseFloat(underline.pseudoWidth)>0&&underline.radius==='0px',underline);
    expect(`${prefix}: selected label has no native blue glow`,m['label-1'].textShadow==='none',m['label-1'].textShadow);
    expect(`${prefix}: library URL placeholder consumes no height`,near(m.replacement.height,0),m.replacement);
    expect(`${prefix}: search input fits real un-hashed input wrapper`,m.input.x>=m['input-wrapper'].x-1&&m.input.right<=m['input-wrapper'].right+1&&m.input.right<=m['search-input'].right+1,{input:m.input,wrapper:m['input-wrapper'],search:m['search-input']});
    expect(`${prefix}: short URL background uses full available slot`,m['address-text'].width>=m.address.width-85&&m['address-text'].right>=m.address.right-14,{row:m.address,field:m['address-text']});
    await evaluate(`document.getElementById('url').textContent='https://store.steampowered.com/'+ 'long-path-segment/'.repeat(30)`); await settle();
    const long=await metrics(['address-text','url']);
    expect(`${prefix}: URL slot width is independent of content length`,near(m['address-text'].width,long['address-text'].width)&&long.url.right<=long['address-text'].right+1,{short:m['address-text'].width,long:long['address-text'].width,url:long.url});
    await evaluate(`document.getElementById('input').focus()`); await settle();
    const focus=(await metrics(['input'])).input;
    expect(`${prefix}: search focus has a filled surface without clipped outline`,focus.background===rgb(palette.focus_surface)&&(focus.outline==='none'||parseFloat(focus.outlineWidth)===0),focus);
    await evaluate(`document.getElementById('address-text').focus()`); await settle();
    const urlFocus=(await metrics(['address-text']))['address-text'];
    expect(`${prefix}: address field receives a full focus surface`,urlFocus.background===rgb(palette.focus_surface),urlFocus);
    await evaluate(`document.activeElement.blur();document.getElementById('url').classList.add('${c.certError}')`); await settle();
    const cert=(await metrics(['url'])).url;
    expect(`${prefix}: certificate error retains native warning text`,cert.color==='rgb(222, 54, 24)',cert);
    await evaluate(`document.getElementById('url').classList.remove('${c.certError}')`);
    expect(`${prefix}: native important dropdown child is themed`,m['dropdown-surface'].background===rgb(palette.bg),m['dropdown-surface']);
    expect(`${prefix}: context surface is themed`,m.context.background===rgb(palette.bg),m.context);
    for(const id of ['dropdown-first','select-first','context-first']) {
      await evaluate(`document.getElementById('${id}').focus()`);await settle();
      const state=(await metrics([id]))[id];
      expect(`${prefix}: ${id} uses the configured UI font`,state.font.includes(palette.browser_font),state.font);
      expect(`${prefix}: ${id} keyboard focus is visible`,state.activeElement===id&&state.focus&&state.background===rgb(palette.mint)&&state.color===rgb(palette.bg),state);
    }
    await evaluate('document.activeElement.blur()');
    await hover('context-first');
    const hovered=(await metrics(['context-first']))['context-first'];
    expect(`${prefix}: context hover is mint with dark text`,hovered.background===rgb(palette.mint)&&hovered.color===rgb(palette.bg),hovered);await hover('context-first',false);
    await hover('context-disabled');
    const disabled=(await metrics(['context-disabled']))['context-disabled'];
    expect(`${prefix}: disabled menu does not become active on hover`,disabled.color===rgb(palette.muted)&&disabled.background!==rgb(palette.mint),disabled);await hover('context-disabled',false);
    await hover('context-aria-disabled');
    const ariaDisabled=(await metrics(['context-aria-disabled']))['context-aria-disabled'];
    expect(`${prefix}: aria-only disabled menu does not activate on hover`,ariaDisabled.color===rgb(palette.muted)&&ariaDisabled.background!==rgb(palette.mint),ariaDisabled);await hover('context-aria-disabled',false);
    await hover('tab-disabled');
    const navDisabled=await metrics(['tab-disabled','label-disabled']);
    expect(`${prefix}: native disabled top navigation remains muted`,navDisabled['label-disabled'].color===rgb(palette.muted)&&navDisabled['tab-disabled'].background!==rgb(palette.surface)&&navDisabled['tab-disabled'].background!==rgb(palette.focus_surface),navDisabled);await hover('tab-disabled',false);
    await evaluate(`document.activeElement.blur();document.getElementById('context-destructive').classList.add('_2XVTVAadkIvrBujZYN5jbL')`);await settle();
    const destructive=(await metrics(['context-destructive']))['context-destructive'];
    expect(`${prefix}: destructive synthetic keyboard focus keeps semantic color`,destructive.background===rgb(palette.burgundy)&&destructive.color===rgb(palette.fg),destructive);
    await evaluate(`document.getElementById('context-destructive').classList.remove('_2XVTVAadkIvrBujZYN5jbL')`);
    expect(`${prefix}: progress status and percentage use the mint text token`,m.status.color===rgb(palette.mint)&&m.percent.color===rgb(palette.mint),{status:m.status.color,percentage:m.percent.color});
    expect(`${prefix}: progress text wrapper stays transparent`,m['progress-wrapper'].background==='rgba(0, 0, 0, 0)',m['progress-wrapper']);
    expect(`${prefix}: progress status/percentage fit their wrapper`,m.status.x>=m['progress-wrapper'].x-1&&m.percent.right<=m['progress-wrapper'].right+1&&m.status.right<=m.percent.x+1,{wrapper:m['progress-wrapper'],status:m.status,percentage:m.percent});
    expect(`${prefix}: live progress text fits vertically above track`,m.status.y>=m['progress-wrapper'].y-1&&m.percent.y>=m['progress-wrapper'].y-1&&m.status.bottom<=m.progress.y+1&&m.percent.bottom<=m.progress.y+1,{wrapper:m['progress-wrapper'],status:m.status,percentage:m.percent,track:m.progress});
    for(const ratio of [0,.34,.75,1]) {
      await evaluate(`document.getElementById('progress').style.setProperty('--percent','${ratio}');document.getElementById('percent').textContent='${Math.round(ratio*100)}%'`);await settle();
      const track=(await metrics(['progress'])).progress;
      const fill=await evaluate(`(${inspect})('progress','::after')`);
      expect(`${prefix}: ${ratio*100}% native fill width follows --percent`,near(parseFloat(fill.pseudoWidth),track.width*ratio,1),{ratio,trackWidth:track.width,fillWidth:fill.pseudoWidth});
      expect(`${prefix}: ${ratio*100}% track/fill retain distinct theme colors`,track.background===rgb(palette.window_border)&&fill.background===rgb(palette.mint),{track:track.background,fill:fill.background});
    }
    const menuWidths=[];
    for(const text of ['A','A longer library dropdown label that exceeds the normal minimum menu width']) {
      await evaluate(`document.getElementById('context-first').textContent=${JSON.stringify(text)}`);await settle();
      const frame=await evaluate(`(()=>{const e=document.getElementById('menu-frame'),s=getComputedStyle(e),r=e.getBoundingClientRect(),children=[...document.querySelectorAll('#context > div')].map(n=>{const q=n.getBoundingClientRect();return {left:q.left,right:q.right}});return {left:r.left,right:r.right,width:r.width,borders:[s.borderTopWidth,s.borderRightWidth,s.borderBottomWidth,s.borderLeftWidth],color:s.borderTopColor,children}})()`);
      menuWidths.push(frame.width);
      expect(`${prefix}: popup outline encloses ${text.length}-character item`,frame.borders.every(b=>b==='1px')&&frame.color===rgb(palette.window_border)&&frame.children.every(r=>r.left>=frame.left+1&&r.right<=frame.right-1),frame);
      await hover('context-first');
      const edge=await evaluate(`(()=>{const f=document.getElementById('menu-frame').getBoundingClientRect(),r=document.getElementById('context-first').getBoundingClientRect();return {left:r.left-f.left,right:f.right-r.right}})()`);
      expect(`${prefix}: hovered menu item cannot cover outside border`,edge.left>=1&&edge.right>=1,edge);await hover('context-first',false);
    }
    expect(`${prefix}: popup frame follows the longest label`,menuWidths[1]>menuWidths[0],menuWidths);
    await evaluate(`document.documentElement.classList.add('_14wqdluDeDnnEcg3OSLEmd')`);await settle();
    const viewportFrame=await evaluate(`(()=>{const s=getComputedStyle(document.documentElement,'::after'),m=getComputedStyle(document.getElementById('menu-frame'));return {position:s.position,inset:[s.top,s.right,s.bottom,s.left],borders:[s.borderTopWidth,s.borderRightWidth,s.borderBottomWidth,s.borderLeftWidth],color:s.borderTopColor,width:parseFloat(s.width),height:parseFloat(s.height),viewportWidth:innerWidth,viewportHeight:innerHeight,pointerEvents:s.pointerEvents,contentBorder:m.borderRightWidth}})()`);
    expect(`${prefix}: separate native popup frames all viewport edges`,viewportFrame.position==='fixed'&&viewportFrame.inset.every(v=>v==='0px')&&viewportFrame.borders.every(v=>v==='1px')&&viewportFrame.color===rgb(palette.window_border)&&near(viewportFrame.width,viewportFrame.viewportWidth)&&near(viewportFrame.height,viewportFrame.viewportHeight),viewportFrame);
    expect(`${prefix}: native popup frame cannot affect hit testing or content sizing`,viewportFrame.pointerEvents==='none'&&viewportFrame.contentBorder==='0px',viewportFrame);

    await evaluate(`document.documentElement.classList.remove('_14wqdluDeDnnEcg3OSLEmd');document.getElementById('context-first').textContent='Properties 속성'`);
    const primary=await metrics(['primary-install','primary-play','primary-unavailable']);
    expect(`${prefix}: install action uses the main accent`,primary['primary-install'].background===rgb(palette.mint)&&primary['primary-install'].color===rgb(palette.bg),primary['primary-install']);
    expect(`${prefix}: play action retains positive meaning in the palette`,primary['primary-play'].background===rgb(palette.ansi[2])&&primary['primary-play'].color===rgb(palette.bg),primary['primary-play']);
    await hover('primary-unavailable');
    const unavailable=(await metrics(['primary-unavailable']))['primary-unavailable'];
    expect(`${prefix}: unavailable primary action stays muted on hover`,unavailable.background===rgb(palette.surface)&&unavailable.color===rgb(palette.muted),unavailable);await hover('primary-unavailable',false);
    expect(`${prefix}: generated cover keeps native proportional family`,!/Sarasa|Ubuntu Mono/i.test(m['cover-text'].font),m['cover-text'].font);
    expect(`${prefix}: real input uses configured browser font`,m.input.font.includes(palette.browser_font),m.input.font);
    await evaluate(`document.getElementById('progress').style.setProperty('--percent','.34');document.getElementById('percent').textContent='34%';document.getElementById('url').textContent='https://store.steampowered.com/';document.activeElement.blur()`);
    if(width===1280) {await settle();const capture=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await mkdir(output,{recursive:true});await writeFile(join(output,'steam-layout.png'),Buffer.from(capture.data,'base64'));}
  }
  report.snapshots=snapshots;
  report.passed=checks.filter(x=>x.pass).length;report.failed=checks.filter(x=>!x.pass).length;
  await mkdir(output,{recursive:true});await writeFile(join(output,'steam-layout.json'),JSON.stringify(report,null,2)+'\n');
  console.log(`Steam fixture: ${report.passed}/${checks.length} checks passed; ${report.failed} failed. Artifacts: ${output}`);
  for(const item of checks.filter(x=>!x.pass))console.error(`FAIL ${item.name}: ${JSON.stringify(item.details)}`);
  if(report.failed)process.exitCode=1;
} finally {
  clearTimeout(deadline);
  ws?.close();
  if(chrome&&chrome.exitCode===null){chrome.kill('SIGTERM');await Promise.race([new Promise(r=>chrome.once('exit',r)),new Promise(r=>setTimeout(r,1500))]);if(chrome.exitCode===null)chrome.kill('SIGKILL');}
  await rm(working,{recursive:true,force:true});
}
