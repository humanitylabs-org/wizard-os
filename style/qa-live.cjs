/* Real-shell Appearance v1 acceptance. Read-only against a running Wizard shell: every non-GET request is refused
 * inside this isolated browser context, except to disposable QA apps injected below. No box settings, apps or data
 * are written. The release reviewer must inspect the captured screenshots, not only these assertions.
 *
 * Env:
 *   QA_URL          (required) the shell entry, e.g. https://<box>.<tailnet>.ts.net/wizard-os-home/
 *   PLAYWRIGHT_PATH resolvable playwright module          STYLE_ROOT  this folder (default)
 *   QA_SHOTS        screenshot + receipt folder           QA_APPS     installed app ids (default topics,wizard-music,wizard-signal,wisdom)
 *   QA_DEVICE       Playwright device profile (default Pixel 7)
 *   QA_INJECT       JSON [{id,name,prefix,upstream|dir}]  disposable apps added to the registry for this context only:
 *                   `upstream` proxies to a local container (writes allowed: it is disposable); `dir` serves files (`index` names its entry page).
 * Candidate client: requests for a wizard-appearance.js path are answered with this folder's appearance-client.js.
 * Apps that take the theme from the shell's own app-client.js are checked too; the receipt records which client ran. */
'use strict';
const fs = require('node:fs'), path = require('node:path');
const pw = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root = process.env.STYLE_ROOT || __dirname;
const url = process.env.QA_URL; if (!url) throw new Error('Set QA_URL to the shell entry URL.');
const shots = path.resolve(process.env.QA_SHOTS || 'style-qa-shots'); fs.mkdirSync(shots, { recursive: true });
const tokens = JSON.parse(fs.readFileSync(path.join(root, 'tokens.json')));
const client = fs.readFileSync(path.join(root, 'appearance-client.js'), 'utf8');
const inject = JSON.parse(process.env.QA_INJECT || '[]');
const apps = (process.env.QA_APPS ?? 'topics,wizard-music,wizard-signal,wisdom').split(',').filter(Boolean).concat(inject.map(a => a.id));
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml' };
const transparent = 'rgba(0, 0, 0, 0)';
const checks = [], report = {};
const mark = (name, ok, detail) => { if (!ok) throw new Error('FAILED: ' + name + (detail ? ' ' + JSON.stringify(detail) : '')); checks.push(name); };

(async () => {
  const browser = await pw.chromium.launch();
  try {
    // A real phone profile (touch + mobile UA): a bare narrow viewport is redirected to the desktop shell.
    const context = await browser.newContext({ ...pw.devices[process.env.QA_DEVICE || 'Pixel 7'], ignoreHTTPSErrors: true });
    await context.addInitScript(() => localStorage.setItem('wos.coached', 'true'));
    await context.route('**/*', async route => {
      const req = route.request(), u = new URL(req.url());
      const qa = inject.find(a => u.pathname.startsWith(a.prefix));
      if (qa && qa.upstream) {
        const target = qa.upstream.replace(/\/$/, '') + '/' + u.pathname.slice(qa.prefix.length) + u.search;
        const headers = { ...req.headers() }; delete headers.host;
        return route.fulfill({ response: await route.fetch({ url: target, headers }) });
      }
      if (qa && qa.dir) {
        const f = path.join(qa.dir, path.normalize(u.pathname.slice(qa.prefix.length) || qa.index || 'index.html'));
        if (!f.startsWith(qa.dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return route.fulfill({ status: 404, body: '' });
        return route.fulfill({ contentType: TYPES[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) });
      }
      if (!['GET', 'HEAD'].includes(req.method())) return route.fulfill({ status: 403, body: 'Read-only QA' });
      if (/\/wizard-appearance\.js$/.test(u.pathname)) return route.fulfill({ contentType: 'text/javascript', body: client });
      if (/\/wizard\/v1\/apps\/?$/.test(u.pathname) && inject.length) {
        const r = await route.fetch(); const body = await r.json();
        for (const a of inject) body.apps.push({ id: a.id, name: a.name, desc: 'Disposable style QA app', url: a.prefix, icon: '✓', colors: ['#b99bff', '#7fd8ff'], source: 'qa' });
        return route.fulfill({ response: r, json: body });
      }
      return route.continue();
    });

    for (const app of apps) {
      const page = await context.newPage();
      const rec = report[app] = { client: null, views: {}, back: [] };
      await page.goto(url + '?open=' + encodeURIComponent(app), { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(id => Object.values(window.__wos?.wins || {}).some(w => w.appId === id), app, { timeout: 30000 });
      const winId = await page.evaluate(id => Object.entries(window.__wos.wins).filter(([, w]) => w.appId === id).pop()[0], app);
      const winSel = `.win[data-win="${winId}"]`;
      const frame = await (await page.waitForSelector(winSel + ' iframe', { timeout: 30000 })).contentFrame();
      mark(app + ' cold canonical entry opens its frame', !!frame);
      await frame.waitForLoadState('load');
      // The shell marks the window themed only after the document acknowledged a context.
      await page.waitForFunction(sel => document.querySelector(sel)?.classList.contains('wz-themed'), winSel, { timeout: 20000 })
        .catch(() => { throw new Error(`FAILED: ${app} never acknowledged an appearance context (window not .wz-themed)`); });
      rec.client = await frame.evaluate(() => [...document.scripts].some(s => /wizard-appearance\.js|theme-client\.js|appearance-client\.js/.test(s.src)) ? 'candidate appearance client' : 'shell app-client.js');
      rec.path = await frame.evaluate(() => location.pathname);
      // Let the app finish its first content load so screenshots show real content, not a spinner.
      await frame.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(1500);
      await frame.evaluate(() => { window.__styleQAIdentity = {}; });
      const before = await frame.evaluate(() => ({ url: location.href, type: getComputedStyle(document.querySelector('h1,h2,main') || document.body).fontFamily }));
      for (const skin of Object.keys(tokens.skins)) {
        // Device-local preference in this throwaway context; the box settings write is refused above.
        await page.evaluate(id => WosSkin.set(id), skin);
        for (const pres of ['window', 'immersive']) {
          const isFull = await page.evaluate(sel => document.querySelector(sel).classList.contains('full'), winSel);
          // Enter through the visible window-bar button; leave through the shell's own API (full screen hides the bar).
          if (pres === 'immersive' && !isFull) await page.click(winSel + ' [data-wact="full"]');
          if (pres === 'window' && isFull) await page.evaluate(id => window.__wos.setFull(id, false), winId);
          await page.waitForFunction(([sel, s, p]) => {
            const f = document.querySelector(sel + ' iframe'); const st = window.WizAppearance?.inspect().find(x => x.src === f.getAttribute('src'));
            const el = f.contentDocument?.documentElement; return st && st.acked && st.presentation === p && el?.dataset.skin === s && el?.dataset.presentation === p;
          }, [winSel, skin, pres], { timeout: 10000 }).catch(() => { throw new Error(`FAILED: ${app} ${skin} ${pres} context not applied`); });
          await page.waitForTimeout(250);
          const o = await frame.evaluate(names => {
            const cs = getComputedStyle(document.documentElement);
            return { html: cs.backgroundColor, body: getComputedStyle(document.body).backgroundColor, scheme: cs.colorScheme, url: location.href,
              type: getComputedStyle(document.querySelector('h1,h2,main') || document.body).fontFamily, identity: !!window.__styleQAIdentity,
              vars: Object.fromEntries(names.map(k => [k, cs.getPropertyValue('--wz-' + k).trim()])) };
          }, Object.keys(tokens.skins[skin].tokens));
          const c = await page.evaluate(sel => {
            const win = document.querySelector(sel), f = win.querySelector('iframe'), chain = [];
            for (let el = f; el && el !== win; el = el.parentElement) chain.push({ el: el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).join('.') : ''), bg: getComputedStyle(el).backgroundColor });
            const probe = document.createElement('div'); probe.style.background = 'var(--sk-win)'; win.appendChild(probe);
            const material = getComputedStyle(probe).backgroundColor; probe.remove();
            return { chain, win: getComputedStyle(win).backgroundColor, material, themed: win.classList.contains('wz-themed') };
          }, winSel);
          const tag = `${app} ${skin} ${pres}`;
          mark(tag + ': app canvas transparent', o.html === transparent && o.body === transparent, o);
          mark(tag + ': frame-to-window chain transparent', c.themed && c.chain.every(x => x.bg === transparent), c.chain);
          mark(tag + ': window paints the skin window material', c.win === c.material, { win: c.win, material: c.material });
          // Same colour, any notation: the shell sends computed rgba(), tokens.json records hex.
          const roles = ['text', 'text-secondary', 'accent', 'base', 'border'];
          const cmp = await frame.evaluate(([pairs]) => pairs.map(([a, b]) => { const r = v => { const e = document.createElement('i'); e.style.color = v; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; }; return [r(a), r(b)]; }),
            [roles.map(k => [o.vars[k], tokens.skins[skin].tokens[k]])]);
          mark(tag + ': exact ink, accent, base, border roles', cmp.every(([a, b]) => a === b), { got: o.vars, cmp });
          mark(tag + ': document retained (no reload, same URL and type)', o.identity && o.url === before.url && o.type === before.type);
          rec.views[skin + ':' + pres] = { window: c.win, material: c.material, ink: o.vars.text, accent: o.vars.accent, scheme: o.scheme };
          await page.screenshot({ path: path.join(shots, `${app}-${skin}-${pres}.png`) });
        }
      }
      await page.evaluate(id => window.__wos.setFull(id, false), winId);
      // Back: an open in-app sheet closes first (nested); the next Back is the shell's own step (root).
      const hasSheet = await frame.evaluate(() => { const d = document.querySelector('dialog'); if (d && !d.open && typeof window.__wizardCloseOverlay === 'function') { d.showModal(); return true; } return false; });
      if (hasSheet) {
        const r1 = await page.evaluate(() => window.__wosNativeBack());
        const open = await frame.evaluate(() => document.querySelector('dialog').open);
        mark(app + ' nested Back closes the in-app sheet inside its window', r1 === 'hosted' && !open && (await page.$(winSel)) !== null, { r1, open });
        rec.back.push('nested:' + r1);
        const r2 = await page.evaluate(() => window.__wosNativeBack());
        mark(app + ' root Back passes to the shell', r2 !== 'hosted', { r2 });
        rec.back.push('root:' + r2);
      } else rec.back.push('first:' + await page.evaluate(() => window.__wosNativeBack()));
      await page.close();
    }
    await context.close();
  } finally { await browser.close(); }
  fs.writeFileSync(path.join(shots, 'receipt.json'), JSON.stringify({ host: require('node:os').hostname(), status: 'PASS', count: checks.length, apps: report, checks, source: tokens.source.revision,
    scope: 'read-only real-shell cold entry; candidate client injected where an app loads wizard-appearance.js; injected QA apps are disposable' }, null, 2));
  console.log('PASS: ' + checks.length + ' real-shell appearance checks');
})().catch(e => { console.error(e); process.exitCode = 1; });
