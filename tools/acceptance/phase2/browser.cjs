// Phase 2 browser proof for the fresh L4 box: real Chromium on Thales against the VM's forwarded shell port.
// Usage: node browser.cjs OUT_DIR LABEL [URL]
const { chromium, devices } = require('/Volumes/ThalesMedia/launch-lanes/L7/tools/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const [out, label, url = 'http://127.0.0.1:18796/'] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
(async () => {
  const browser = await chromium.launch();
  const result = { label, url, views: [] };
  for (const [name, opts] of [['desktop', { viewport: { width: 1440, height: 1000 } }], ['pixel7', devices['Pixel 7']]]) {
    const ctx = await browser.newContext(opts);
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e).slice(0, 300)));
    let status = null;
    try {
      const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      status = resp && resp.status();
      await page.waitForTimeout(6000);
    } catch (e) { errors.push('goto: ' + String(e).slice(0, 300)); }
    const info = await page.evaluate(() => {
      const bg = getComputedStyle(document.body || document.documentElement).backgroundColor;
      const text = (document.body ? document.body.innerText : '').replace(/\s+/g, ' ').slice(0, 600);
      return { title: document.title, bg, text, inputs: document.querySelectorAll('textarea,input,[contenteditable=true]').length };
    }).catch(e => ({ error: String(e) }));
    const shot = path.join(out, `${label}-${name}.png`);
    await page.screenshot({ path: shot, fullPage: false }).catch(() => {});
    const white = /rgb\(25[0-5], 25[0-5], 25[0-5]\)/.test(info.bg || '');
    result.views.push({ name, status, ...info, white_canvas: white, errors, screenshot: shot });
    await ctx.close();
  }
  await browser.close();
  result.ok = result.views.every(v => v.status === 200 && !v.white_canvas && (v.text || '').length > 0);
  fs.writeFileSync(path.join(out, `${label}-browser.json`), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ label, ok: result.ok, views: result.views.map(v => [v.name, v.status, v.title, v.white_canvas, (v.text || '').slice(0, 120)]) }));
  process.exit(result.ok ? 0 : 1);
})();
