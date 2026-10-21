// Install-sheet capture for one Connection Router acceptance state. Runs on the Thales host against the VM's Router
// (Lima forwards the VM's loopback port). Real pieces: the Store page from wizard-ux main, the Store feed bridge
// (tools/store-data-origin.mjs → store-router-owner.mjs) and the Router in the VM. Catalog/installed/install calls are
// fixtures; nothing reaches a real Wizard.
//   node sheet.cjs <uxTree> <evidenceDir> <state> <phase> <routerPort> <appsJson> [apps=wisdom,router-fixture] [approve=app/feature]
const pw = require(process.env.PW || 'playwright');
const fs = require('fs'), path = require('path'), http = require('http'), net = require('net'), { spawn } = require('child_process');
const [ux, out, state, phase, rport, appsJson, appList = 'wisdom,router-fixture', approve = ''] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const web = path.join(ux, 'web'), NODE = process.execPath, BASE = 'http://store.qa/wizard-os-home/store/index.html';
const C = 'a'.repeat(40);
const app = (id, name, extra = {}) => ({ id, name, summary: name + ' summary', publisher: 'QA', version: '1.0.0', type: 'view', category: 'Reading',
  repo: 'https://github.com/qa/' + id, source: 'standard', channel: 'standard', commit: C, releases: [], ...extra });
const catalog = { apps: [app('wisdom', 'Wisdom'), app('router-fixture', 'Router Fixture', { category: 'Tools' }),
  app('wizard-claude', 'Claude', { provides: ['ai-connection'], category: 'Connections', type: 'service' }),
  app('wizard-chatgpt', 'ChatGPT', { provides: ['ai-connection'], category: 'Connections', type: 'service' })], sources: [], next_offset: null };
const freePort = () => new Promise(res => { const s = net.createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => res(p)); }); });
const get = (p) => new Promise((res, rej) => http.get({ host: '127.0.0.1', port: rport, path: p }, r => { let b = ''; r.on('data', c => b += c); r.on('end', () => res(JSON.parse(b))); }).on('error', rej));
function start(cmd, args, env, ready) {
  const p = spawn(cmd, args, { env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'] });
  return new Promise((res, rej) => { let log = ''; const on = d => { log += d; if (log.includes(ready)) res(p); };
    p.stdout.on('data', on); p.stderr.on('data', on); p.on('exit', c => rej(new Error(cmd + ' exited ' + c + ': ' + log))); setTimeout(() => rej(new Error('timeout ' + log)), 15000); });
}
(async () => {
  const fp = await freePort();
  const feed = await start(NODE, [path.join(ux, 'tools/store-data-origin.mjs'), String(fp)],
    { WIZARD_STORE_ROUTER_ORIGIN: 'http://127.0.0.1:' + rport, WIZARD_STORE_APPS_JSON: appsJson, WIZARD_STORE_RUNTIPI_ENV: path.join(out, 'none.env') }, 'Store browse data');
  const browser = await pw.chromium.launch({ headless: true });
  const result = { state, phase, sheets: {} };
  try {
    for (const id of appList.split(',')) {
      const st = { installed: new Set(), writes: [], approves: [] };
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, serviceWorkers: 'block' });
      await ctx.addInitScript(() => { try { localStorage.setItem('wos.coached', 'true'); } catch (_) {} });
      const json = (r, s, b) => r.fulfill({ status: s, contentType: 'application/json', body: JSON.stringify(b) });
      await ctx.route('**/*', async r => {
        const u = new URL(r.request().url()), m = r.request().method(), p = u.pathname;
        if (u.host !== 'store.qa') return r.abort();
        if (p.startsWith('/wizard-os-home/store-data/router/')) {
          if (m === 'POST') st.approves.push(r.request().postData());
          const res = await r.fetch({ url: 'http://127.0.0.1:' + fp + p + u.search }); return r.fulfill({ response: res });
        }
        if (p.startsWith('/wizard-os-home/store-data/')) {
          const sub = p.slice('/wizard-os-home/store-data/'.length);
          if (sub === 'wizard/v1/index/search') return json(r, 200, catalog);
          if (sub === 'api/apps/installed') return json(r, 200, { installed: [] });
          if (sub === 'wizard/v1/installed-apps') return json(r, 200, { complete: true, architecture: 'arm64',
            wam: [...st.installed].map(i => ({ id: i, repo: 'https://github.com/qa/' + i, commit: C, source: 'standard', status: 'running' })), shell: [] });
          st.writes.push(m + ' ' + p); return json(r, 404, {});
        }
        const inst = p.match(/^\/wizard-os-home\/store-install\/([a-z0-9-]+)$/);
        if (inst) { if (m === 'POST') { st.installed.add(inst[1]); return json(r, 200, { state: 'installed', selection: JSON.parse(r.request().postData()) }); } return json(r, 200, { state: 'installed' }); }
        if (m !== 'GET') { st.writes.push(m + ' ' + p); return r.abort(); }
        const f = path.join(web, p.replace(/^\/wizard-os-home\//, ''));
        if (!f.startsWith(web) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return r.fulfill({ status: 404, body: '' });
        return r.fulfill({ status: 200, contentType: { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' }[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) });
      });
      const pg = await ctx.newPage(); const errors = []; pg.on('pageerror', e => errors.push(e.message));
      const shot = async n => { await pg.waitForTimeout(700); const f = path.join(out, `390-${state}-${phase}-${id}-${n}.png`); await pg.screenshot({ path: f, fullPage: true }); return path.basename(f); };
      const rows = () => pg.$$eval('#sheet .mc-row', rs => rs.map(r => ({ feature: r.dataset.mcFeature, state: r.querySelector('.mc-state')?.innerText.trim(),
        text: r.innerText.replace(/\s+/g, ' ').trim(), buttons: [...r.querySelectorAll('button')].map(b => b.innerText.trim()) })));
      await pg.goto(BASE + '?app=' + id);
      await pg.locator('#detail [data-get]').first().waitFor({ timeout: 10000 });
      await pg.locator('#detail [data-get]').first().click();
      await pg.locator('#sheet:not([hidden]) .mc-row').first().waitFor({ timeout: 15000 });
      const sheet = { heading: await pg.locator('#sheet .list-head').innerText(), rows: await rows(), shots: [await shot('sheet')] };
      if (approve.startsWith(id + '/')) {
        const feature = approve.split('/')[1];
        const btn = pg.locator(`#sheet .mc-row[data-mc-feature="${feature}"] [data-mc-approve]`);
        sheet.approve_button = (await btn.count()) ? await btn.first().innerText() : null;
        if (sheet.approve_button) {
          await btn.first().click();
          await pg.waitForFunction(f => /approved swap/i.test(document.querySelector(`#sheet .mc-row[data-mc-feature="${f}"] .mc-state`)?.innerText || ''),
            feature, { timeout: 10000 }).catch(() => {});
          sheet.after_approve = { heading: await pg.locator('#sheet .list-head').innerText(), rows: await rows(), shot: await shot('approved') };
          sheet.approve_posts = st.approves;
        }
      }
      sheet.unexpected_writes = st.writes; sheet.page_errors = errors;
      result.sheets[id] = sheet;
      await ctx.close();
    }
    result.owner_routes = await get('/v1/owner/routes');
  } finally { await browser.close(); feed.kill(); }
  fs.writeFileSync(path.join(out, `sheet-${phase}.json`), JSON.stringify(result, null, 1));
  console.log('SHEET', state, phase, Object.entries(result.sheets).map(([k, v]) => `${k}:${v.rows.length} rows`).join(' '));
})().catch(e => { console.error(e); process.exit(2); });
