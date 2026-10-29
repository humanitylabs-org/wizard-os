/* Real-browser fixtures for the Appearance v1 app client (style/appearance-client.js + boot.js + tokens.css + ui.css).
 * Serves this folder on two loopback origins: a fixture host page on one, the same demo on a second foreign origin.
 * The fixture host only posts messages; the real shell host is covered by qa-live.cjs.
 * Requires: PLAYWRIGHT_PATH (or a resolvable `playwright`). Optional: QA_SHOTS (screenshot folder). */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), assert = require('node:assert/strict');
const pw = require('../tools/acceptance/router/qa-playwright.cjs');
const root = process.env.STYLE_ROOT || __dirname;
const shots = path.resolve(process.env.QA_SHOTS || 'style-browser-shots'); fs.mkdirSync(shots, { recursive: true });
const tokens = JSON.parse(fs.readFileSync(path.join(root, 'tokens.json')));
const NAMES = ['canvas','base','chrome','overlay','surface','surface-raised','text','text-secondary','text-muted','border','accent','accent-soft','on-accent','reader-surface'];
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
const checks = []; const mark = (name, ok) => { assert(ok, name); checks.push(name); };
const transparent = 'rgba(0, 0, 0, 0)';
const ctx = (revision, skin, extra = {}) => ({ version: 1, revision, skin, colorScheme: 'dark', presentation: 'window', tokens: { ...tokens.skins[skin].tokens, canvas: 'transparent' }, ...extra });
const LIGHT = { canvas: 'transparent', base: '#f6f3ec', chrome: 'rgba(250,248,242,.86)', overlay: 'rgba(255,253,248,.92)', surface: 'color-mix(in srgb, #1d1a16 6%, transparent)',
  'surface-raised': 'color-mix(in srgb, #1d1a16 10%, transparent)', text: '#1d1a16', 'text-secondary': '#4c463d', 'text-muted': '#7a7266', border: 'rgba(29,26,22,.18)',
  accent: '#7a4dff', 'accent-soft': 'color-mix(in srgb, #7a4dff 16%, transparent)', 'on-accent': '#fffdf8', 'reader-surface': 'transparent' };

function serve(port, hostPage) {
  return new Promise(res => {
    const s = http.createServer((req, rsp) => {
      const u = new URL(req.url, 'http://x');
      if (u.pathname === '/host.html') { rsp.writeHead(200, { 'content-type': 'text/html' }); return rsp.end(hostPage); }
      const f = path.join(root, path.normalize(u.pathname).replace(/^\/+/, ''));
      if (!f.startsWith(root) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { rsp.writeHead(404); return rsp.end(); }
      rsp.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' }); rsp.end(fs.readFileSync(f));
    }).listen(port, '127.0.0.1', () => res(s));
  });
}

(async () => {
  const A = 47191, B = 47192;
  const hostPage = `<!doctype html><meta charset=utf-8><body style="margin:0;background:#123">
<iframe id=same src="http://127.0.0.1:${A}/demo.html" style="width:412px;height:700px;border:0"></iframe>
<iframe id=sib src="http://127.0.0.1:${A}/demo.html" style="width:10px;height:10px;border:0"></iframe>
<iframe id=foreign src="http://127.0.0.1:${B}/demo.html" style="width:10px;height:10px;border:0"></iframe>
<script>window.acks=[];window.readies=[];addEventListener('message',e=>{if(e.data?.type==='wizard:appearance:ack')acks.push({origin:e.origin,src:e.source===same.contentWindow?'same':e.source===foreign.contentWindow?'foreign':'other',revision:e.data.revision});if(e.data?.type==='wizard:appearance:ready')readies.push({origin:e.origin});});
window.send=(id,a,origin)=>document.getElementById(id).contentWindow.postMessage({type:'wizard:appearance',appearance:a},origin||'*');</script>`;
  const sa = await serve(A, hostPage), sb = await serve(B, hostPage);
  const browser = await pw.chromium.launch();
  try {
    const context = await browser.newContext({ viewport: { width: 412, height: 892 } });
    // 1. Standalone: paints the Nebula base itself, unhosted.
    const solo = await context.newPage();
    await solo.goto(`http://127.0.0.1:${A}/demo.html`);
    const s = await solo.evaluate(() => ({ pres: document.documentElement.dataset.presentation, hosted: document.documentElement.classList.contains('wz-hosted'), body: getComputedStyle(document.body).backgroundColor, connected: WizardTheme.connected }));
    mark('standalone presentation', s.pres === 'standalone' && !s.hosted && !s.connected);
    mark('standalone paints Nebula base', s.body === 'rgb(5, 3, 12)');
    await solo.screenshot({ path: path.join(shots, 'standalone-nebula.png') });

    // 2. Hosted fixture.
    const page = await context.newPage();
    await page.goto(`http://127.0.0.1:${A}/host.html`);
    await page.waitForFunction(() => readies.length >= 2);
    await page.waitForTimeout(200); // let a (wrongly) delivered foreign ready arrive, if it ever would
    const fr = await (await page.$('#same')).contentFrame();
    const pre = await fr.evaluate(() => ({ cls: document.documentElement.classList.contains('wz-hosted'), html: getComputedStyle(document.documentElement).backgroundColor, body: getComputedStyle(document.body).backgroundColor }));
    mark('boot.js marks hosted before any context; transparent first paint', pre.cls && pre.html === 'rgba(0, 0, 0, 0)' && pre.body === 'rgba(0, 0, 0, 0)');
    const readies = await page.evaluate(() => readies.map(r => r.origin));
    mark('foreign frame ready never reaches a different-origin parent', readies.filter(o => o === `http://127.0.0.1:${A}`).length === 2 && !readies.includes(`http://127.0.0.1:${B}`));
    // Preservation markers before any theme change.
    await fr.evaluate(() => { window.__identity = {}; document.querySelector('.wz-field, .wz-input').value = 'unsent idea'; const sc = document.querySelector('.wz-scroll'); sc.style.height = '120px'; sc.scrollTop = 40; document.getElementById('sheet').showModal(); window.__events = 0; addEventListener('wizard:theme', () => __events++); });
    const scroll0 = await fr.evaluate(() => document.querySelector('.wz-scroll').scrollTop);
    let rev = 0;
    for (const skin of Object.keys(tokens.skins)) {
      rev++;
      await page.evaluate(([a]) => send('same', a), [ctx(rev, skin)]);
      await page.waitForFunction(r => acks.some(a => a.src === 'same' && a.revision === r), rev);
      const o = await fr.evaluate(() => ({ cur: WizardTheme.current, html: getComputedStyle(document.documentElement).backgroundColor, body: getComputedStyle(document.body).backgroundColor,
        vars: Object.fromEntries(['text','accent','base','border'].map(k => [k, document.documentElement.style.getPropertyValue('--wz-' + k)])), radius: getComputedStyle(document.querySelector('.wz-card')).borderTopLeftRadius,
        ink: getComputedStyle(document.querySelector('.wz-card h2')).color, id: !!window.__identity, input: document.querySelector('.wz-field, .wz-input').value, sheet: document.getElementById('sheet').open, scroll: document.querySelector('.wz-scroll').scrollTop }));
      mark(`${skin}: applied revision ${rev}`, o.cur.skin === skin && o.cur.revision === rev);
      mark(`${skin}: exact colour roles`, ['text','accent','base','border'].every(k => o.vars[k] === tokens.skins[skin].tokens[k]));
      mark(`${skin}: transparent hosted canvas`, o.html === transparent && o.body === transparent);
      mark(`${skin}: shape (Signal square, others round)`, skin === 'signal' ? o.radius === '2px' : o.radius === '14px');
      mark(`${skin}: document, input, scroll and open sheet preserved`, o.id && o.input === 'unsent idea' && o.sheet && o.scroll === scroll0);
      await fr.evaluate(() => document.getElementById('sheet').close());
      await page.screenshot({ path: path.join(shots, `fixture-${skin}.png`) });
      await fr.evaluate(() => document.getElementById('sheet').showModal());
    }
    // 3. Generic light scheme (synthetic; no retired skin name).
    rev++;
    await page.evaluate(() => { document.body.style.background = '#f2efe8'; }); // a light host behind a light scheme
    await page.evaluate(([a]) => send('same', a), [{ version: 1, revision: rev, skin: 'fixture-light', colorScheme: 'light', presentation: 'immersive', tokens: LIGHT }]);
    await page.waitForFunction(r => acks.some(a => a.revision === r), rev);
    const lt = await fr.evaluate(() => ({ cs: getComputedStyle(document.documentElement).colorScheme, pres: document.documentElement.dataset.presentation, ink: document.documentElement.style.getPropertyValue('--wz-text') }));
    mark('generic light scheme + immersive presentation', lt.cs === 'light' && lt.pres === 'immersive' && lt.ink === '#1d1a16');
    await fr.evaluate(() => document.getElementById('sheet').close());
    await page.screenshot({ path: path.join(shots, 'fixture-generic-light.png') });
    await fr.evaluate(() => document.getElementById('sheet').showModal());
    const good = rev;
    // 4. Rejections: none may change state or produce an ack.
    const bad = {
      'stale revision': ctx(good - 1, 'grove'),
      'version 2': { ...ctx(good + 1, 'grove'), version: 2 },
      'opaque canvas': ctx(good + 1, 'grove', { tokens: { ...tokens.skins.grove.tokens, canvas: '#000' } }),
      'missing role': ctx(good + 1, 'grove', { tokens: Object.fromEntries(NAMES.filter(k => k !== 'accent').map(k => [k, k === 'canvas' ? 'transparent' : tokens.skins.grove.tokens[k]])) }),
      'var() substitution': ctx(good + 1, 'grove', { tokens: { ...tokens.skins.grove.tokens, canvas: 'transparent', text: 'var(--x)' } }),
      'inherit keyword': ctx(good + 1, 'grove', { tokens: { ...tokens.skins.grove.tokens, canvas: 'transparent', accent: 'inherit' } }),
      'url() injection': ctx(good + 1, 'grove', { tokens: { ...tokens.skins.grove.tokens, canvas: 'transparent', surface: 'url(https://x/y)' } }),
      'unknown presentation': ctx(good + 1, 'grove', { presentation: 'floating' }),
      'bad skin id': { ...ctx(good + 1, 'grove'), skin: 'Grove!' },
    };
    for (const [name, a] of Object.entries(bad)) {
      const n0 = await page.evaluate(() => acks.length);
      await page.evaluate(([x]) => send('same', x), [a]);
      await page.waitForTimeout(80);
      const st = await fr.evaluate(() => ({ rev: WizardTheme.current.revision, skin: WizardTheme.current.skin }));
      mark(`rejects ${name}`, st.rev === good && st.skin === 'fixture-light' && (await page.evaluate(() => acks.length)) === n0);
    }
    // Wrong source: a same-origin sibling posts to the app frame (not its parent).
    const n1 = await page.evaluate(() => acks.length);
    await page.evaluate(([x]) => document.getElementById('sib').contentWindow.eval(`parent.document.getElementById('same').contentWindow.postMessage({type:'wizard:appearance',appearance:${JSON.stringify(x)}},'*')`), [ctx(good + 5, 'tide')]);
    await page.waitForTimeout(80);
    mark('rejects sibling (non-parent) sender', (await fr.evaluate(() => WizardTheme.current.revision)) === good && (await page.evaluate(() => acks.length)) === n1);
    // Foreign-origin frame: the parent origin differs from its own, so it ignores the context.
    await page.evaluate(([x]) => send('foreign', x), [ctx(1, 'tide')]);
    await page.waitForTimeout(120);
    const ff = page.frames().find(f => f.url().startsWith(`http://127.0.0.1:${B}/`));
    mark('foreign-origin frame ignores host context', !(await ff.evaluate(() => WizardTheme.connected)) && !(await page.evaluate(() => acks.some(a => a.src === 'foreign'))));
    // Retransmission of the current revision: acked again, no second theme event.
    const ev0 = await fr.evaluate(() => __events), n2 = await page.evaluate(() => acks.length);
    await page.evaluate(([x]) => send('same', x), [{ version: 1, revision: good, skin: 'fixture-light', colorScheme: 'light', presentation: 'immersive', tokens: LIGHT }]);
    await page.waitForFunction(n => acks.length > n, n2);
    mark('retransmission re-acked without a second theme event', (await fr.evaluate(() => __events)) === ev0);
    // 5. Nested then root Back through the documented hook.
    const b1 = await fr.evaluate(() => [window.__wizardCloseOverlay(), document.getElementById('sheet').open]);
    const b2 = await fr.evaluate(() => window.__wizardCloseOverlay());
    mark('nested Back closes the sheet; root Back reports atRoot', b1[0] === true && b1[1] === false && b2 === false);
    await context.close();
  } finally { await browser.close(); sa.close(); sb.close(); }
  fs.writeFileSync(path.join(shots, 'receipt.json'), JSON.stringify({ host: require('node:os').hostname(), status: 'PASS', count: checks.length, checks, source: tokens.source.revision }, null, 2));
  console.log('PASS: ' + checks.length + ' browser fixture checks');
})().catch(e => { console.error(e); process.exitCode = 1; });
