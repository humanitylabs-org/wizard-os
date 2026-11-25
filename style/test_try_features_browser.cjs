/* Real-browser check for the "Try new features" section (style/try-features.js, wizard-os#916).
 * 1. At phone size (412 px) every control has at least a 44 x 44 px hit area, while the drawn thumbs (34 px circle) and
 *    the On/Off track (46 x 28 px) look the same and the row keeps its height.
 * 2. A re-read that started before a save never paints the old listing over the saved one.
 * Requires: PLAYWRIGHT_PATH / QA_PLAYWRIGHT (or a resolvable `playwright`). Optional: STYLE_ROOT, QA_SHOTS, QA_EXPECT=broken. */
'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), assert = require('node:assert/strict');
const pw = require('../tools/acceptance/router/qa-playwright.cjs');
const root = process.env.STYLE_ROOT || __dirname;
const shots = process.env.QA_SHOTS ? path.resolve(process.env.QA_SHOTS) : '';
if (shots) fs.mkdirSync(shots, { recursive: true });
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css' };
const page = `<!doctype html><html data-skin="nebula"><meta charset=utf-8><meta name=viewport content="width=device-width">
<link rel=stylesheet href="/tokens.css"><link rel=stylesheet href="/ui.css"><body style="margin:0">
<main class="wz-scroll"><section id="try-features"></section></main><script src="/try-features.js"></script>`;

function serve() {
  return new Promise(res => {
    const s = http.createServer((req, rsp) => {
      const u = new URL(req.url, 'http://x');
      if (u.pathname === '/') { rsp.writeHead(200, { 'content-type': 'text/html' }); return rsp.end(page); }
      const f = path.join(root, path.basename(u.pathname));
      if (!fs.existsSync(f)) { rsp.writeHead(404); return rsp.end(); }
      rsp.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'text/plain', 'cache-control': 'no-store' }); rsp.end(fs.readFileSync(f));
    }).listen(0, '127.0.0.1', () => res(s));
  });
}

const fails = [];
const check = (name, ok, detail) => { if (ok) console.log('ok  ', name); else { console.log('FAIL', name, detail || ''); fails.push(name); } };

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}/`;
  const browser = await pw.chromium.launch();
  try {
    const ctx = await browser.newContext({ viewport: { width: 412, height: 892 }, hasTouch: true, isMobile: true, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    await p.goto(base);
    // The box: a listing in page memory; POST answers are held until the test releases them.
    await p.evaluate(() => {
      window.state = { contract: 'wizard.app-switches/1', switches: [
        { id: 'drag-events', name: 'Drag events', description: 'Move events by dragging them', on: false, vote: null, tried: false },
        { id: 'old-app', name: 'No votes here', description: 'An app that keeps no votes', on: true } ] };
      window.held = []; window.hold = false; window.gets = [];
      const reply = () => { const snap = JSON.stringify(state); return { ok: true, status: 200, json: async () => JSON.parse(snap) }; };
      window.fakeFetch = (url, init = {}) => {
        if (init.method === 'POST') {
          // The box applies the change when it answers, so a read it served earlier still has the old state.
          const apply = () => { const b = JSON.parse(init.body), s = state.switches.find(x => x.id === b.id);
            if ('on' in b) s.on = b.on; if ('vote' in b) s.vote = b.vote; return reply(); };
          return hold ? new Promise(res => held.push(() => res(apply()))) : Promise.resolve(apply());
        }
        const snap = reply(); // what the box says right now
        return new Promise(res => gets.push(() => res(snap)));
      };
      window.release = () => { const h = gets.splice(0); h.forEach(f => f()); return h.length; };
      window.m = WzTryFeatures.mount(document.getElementById('try-features'), { path: 'api/switches', fetch: fakeFetch });
    });
    await p.evaluate(() => release());
    await p.waitForSelector('[data-try-toggle]');

    // 1. Hit areas at 412 px.
    const sizes = await p.evaluate(() => {
      const box = el => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10, x: r.x, y: r.y }; };
      const pseudo = (el, which) => { const cs = getComputedStyle(el, which); return { w: parseFloat(cs.width), h: parseFloat(cs.height) }; };
      const hit = el => { const r = el.getBoundingClientRect(); let n = 0, all = 0;
        for (let x = r.left + 1; x < r.right - 1; x += 2) for (let y = r.top + 1; y < r.bottom - 1; y += 2) { all++; const t = document.elementFromPoint(x, y); if (t === el || el.contains(t)) n++; }
        return all ? n / all : 0; };
      const ctrls = [...document.querySelectorAll('[data-try-id] button')];
      const row = document.querySelector('[data-try-id]').getBoundingClientRect().height;
      const vote = document.querySelector('[data-try-vote]'), tog = document.querySelector('[data-try-toggle]');
      return { ctrls: ctrls.map(el => ({ kind: el.hasAttribute('data-try-toggle') ? 'toggle' : 'vote-' + el.dataset.tryVote, ...box(el), hit: hit(el) })), row,
        voteLook: getComputedStyle(vote).width === '34px' ? { w: 34, h: 34 } : pseudo(vote, '::before'),
        toggleLook: getComputedStyle(tog).height === '28px' ? { w: 46, h: 28 } : pseudo(tog, '::before') };
    });
    for (const c of sizes.ctrls) check(`${c.kind} hit area ${c.w}x${c.h} px is at least 44x44`, c.w >= 44 && c.h >= 44);
    for (const c of sizes.ctrls) check(`${c.kind}: the whole 44 px area answers its own taps (${Math.round(c.hit * 100)}%)`, c.hit > 0.99);
    check(`thumb still drawn as a 34 px circle (${sizes.voteLook.w}x${sizes.voteLook.h})`, sizes.voteLook.w === 34 && sizes.voteLook.h === 34);
    check(`switch still drawn 46x28 (${sizes.toggleLook.w}x${sizes.toggleLook.h})`, sizes.toggleLook.w === 46 && sizes.toggleLook.h === 28);
    check(`row keeps its height (${sizes.row} px, 57.2 before)`, sizes.row < 58);
    if (shots) await p.locator('#try-features').screenshot({ path: path.join(shots, 'try-features-412.png') });

    // A real tap on the switch's top edge (inside 44 px, outside the drawn 28 px track) flips it.
    const t = sizes.ctrls.find(c => c.kind === 'toggle');
    await p.evaluate(() => { hold = false; });
    await p.touchscreen.tap(t.x + t.w / 2, t.y + 2);
    await p.waitForTimeout(100);
    check('a tap on the edge of the switch hit area flips it', await p.evaluate(() => state.switches[0].on === true));
    await p.evaluate(async () => { state.switches[0].on = false; const r = m.reload(); release(); await r; });

    // 2. Re-read racing a flip: GET starts, then the POST, POST answers first, GET answers last with the old state.
    const race = await p.evaluate(async () => {
      gets.length = 0; hold = true;
      Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
      const r = m.reload();                     // a read in flight (e.g. visibilitychange)
      const staleSnap = gets.length;            // it answers with what the box had before the flip
      const s = m.send('drag-events', 'toggle'); // the flip
      document.dispatchEvent(new Event('visibilitychange')); // another re-read while the save is in flight
      await new Promise(res => setTimeout(res, 20));
      held.splice(0).forEach(f => f()); await s; // the save lands first
      const afterSave = document.querySelector('[data-try-id="drag-events"] [data-try-toggle]').getAttribute('aria-checked');
      release(); await r; await new Promise(res => setTimeout(res, 50)); release(); await new Promise(res => setTimeout(res, 50));
      const end = document.querySelector('[data-try-id="drag-events"] [data-try-toggle]').getAttribute('aria-checked');
      hold = false;
      return { staleSnap, afterSave, end, box: state.switches[0].on, listing: m.listing.switches[0].on };
    });
    check('save shows the switch on', race.afterSave === 'true', JSON.stringify(race));
    check('an older re-read resolving last does not paint the switch reverted', race.end === 'true' && race.listing === true && race.box === true, JSON.stringify(race));

    // Same for a vote.
    const vrace = await p.evaluate(async () => {
      gets.length = 0; hold = true;
      const r = m.reload(); const s = m.send('drag-events', 'up');
      await new Promise(res => setTimeout(res, 20)); held.splice(0).forEach(f => f()); await s;
      release(); await r; await new Promise(res => setTimeout(res, 50));
      hold = false;
      return document.querySelector('[data-try-id="drag-events"] [data-try-vote="up"]').getAttribute('aria-pressed');
    });
    check('an older re-read resolving last does not clear a saved thumbs up', vrace === 'true', vrace);

    // A re-read after the save still picks up a flip made elsewhere (the Tracker).
    const later = await p.evaluate(async () => {
      state.switches[1].on = false; const r = m.reload(); release(); await r;
      return document.querySelector('[data-try-id="old-app"] [data-try-toggle]').getAttribute('aria-checked');
    });
    check('a re-read with no save in flight still shows a flip made from the Tracker', later === 'false', later);
  } finally { await browser.close(); server.close(); }
  const expectBroken = process.env.QA_EXPECT === 'broken';
  if (expectBroken) { console.log(fails.length ? `BROKEN as expected (${fails.length} failing)` : 'NOT BROKEN'); process.exit(fails.length ? 0 : 1); }
  if (fails.length) { console.error(`FAIL: ${fails.length} check(s)`); process.exit(1); }
  console.log('PASS: try-features hit areas and save/re-read order');
})().catch(e => { console.error(e); process.exit(1); });
