#!/usr/bin/env node
/* Release 0.2.2 AI-workflow acceptance, browser half. Invoked only by e2e_022_ai_flow.py.
 *
 * Drives the REAL installed Wizard UX like an owner: New chat, model chip -> picker, typed
 * message, Send; thread rows; browser Back. No injected app state, no response fixtures,
 * no localStorage/cookie dumps, no HAR/console capture. Same-origin requests only. The AI
 * Accounts page is never navigated to or captured (navigation to it is aborted and logged).
 *
 * Phases:
 *   ai     model pick + READY chat (mobile, desktop readback) + DeFleur request and bounded wait
 *   files  open the output video's folder in Files (?open=files), Back once, still on Wizard
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');

const MODEL = 'claude-opus-5-5';
const MODEL_ALIASES = new Set([MODEL, MODEL + '[1m]']);
// Claude Opus 5.5 as the installed catalogue names it: the DirectSDK plugin collapses opus/opus[1m]
// onto the 1M route id, so the exact catalogue id is chosen at runtime (plain id preferred if offered).
let routeModel = MODEL;
const pickRouteId = values => values.includes(MODEL) ? MODEL : values.includes(MODEL + '[1m]') ? MODEL + '[1m]' : '';
const PROVIDER = 'claude-subscription-directsdk-experimental';
const READY_PROMPT = 'Reply with exactly the word READY.';
const ANSWER = 'Trim the pauses and add captions, then save it to my Files.';
const WORKING = new Set(['submitting', 'queued', 'accepted', 'running', 'stopping']);
const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'interrupted', 'expired']);

const [modulePath, origin, shellPath, evidence, runId, phase, rawCfg] = process.argv.slice(2);
const cfg = JSON.parse(rawCfg || '{}');
const {chromium} = require(modulePath);
const report = {phase, runId, stages: [], requests: [], postPaths: [], blockedExternalRequests: 0, blockedAccountsNavigations: [],
  authStatuses: [], screenshotsSkipped: [], status: 'fail'};
const receiptFile = path.join(evidence, `browser-${phase}.json`);
const save = () => fs.writeFileSync(receiptFile, JSON.stringify(report, null, 2), {mode: 0o600});
const delay = ms => new Promise(r => setTimeout(r, ms));
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const check = (ok, reason) => { if (!ok) throw new Error(reason); };
const safePath = u => { try { return new URL(u).pathname; } catch { return '(invalid URL)'; } };
const isAccounts = u => /ai[-_]?accounts|\/accounts(\/|$)/i.test(safePath(u));
const visible = async l => (await l.count()) > 0 && await l.first().isVisible().catch(() => false);
const now = () => new Date().toISOString();
const text = c => typeof c === 'string' ? c : Array.isArray(c) ? c.map(p => typeof p === 'string' ? p : p?.text || '').join('') : '';
const clip = (s, n = 600) => String(s || '').slice(0, n);
const pick = (o, keys) => Object.fromEntries(keys.filter(k => o && o[k] !== undefined).map(k => [k, o[k]]));

async function shot(page, name) {
  // Never capture the AI Accounts page (or a frame of it).
  if (page.frames().some(f => isAccounts(f.url()))) { report.screenshotsSkipped.push(name); return {file: null, skipped: 'accounts'}; }
  const file = `${name}.png`;
  await page.screenshot({path: path.join(evidence, file), fullPage: false, mask: [page.locator('input[type=password]')]});
  return {file, sha256: hash(fs.readFileSync(path.join(evidence, file)))};
}
async function gate(page) {
  for (const frame of page.frames()) {
    try {
      if (await visible(frame.locator('input[type=password]'))) return 'visible password/login form; no credentials supplied';
      if (await visible(frame.getByRole('button', {name: /^(unlock|sign in|log in)$/i}))) return 'visible owner sign-in/unlock gate; not bypassed';
    } catch {}
  }
  return null;
}
async function historyBack(page) {
  await page.goBack({waitUntil: 'domcontentloaded', timeout: 15000}).catch(e => { if (!String(e.message).includes('ERR_ABORTED')) throw e; });
  await delay(1200);
}
async function inShell(page, expectedPath) {
  if (page.isClosed()) return false;
  const u = new URL(page.url());
  return u.origin === origin && u.pathname === expectedPath && await page.evaluate(() => !!window.WizCore && !!document.body?.children.length);
}

function guestProbe(cmd) {
  // The host passes the exact limactl argv; output is the guest's allowlisted JSON only.
  const p = cfg.probe;
  const out = execFileSync(p.argv[0], [...p.argv.slice(1), cmd, runId],
    {input: fs.readFileSync(p.script), timeout: 180000, stdio: ['pipe', 'pipe', 'ignore'], env: process.env});
  return JSON.parse(String(out));
}

(async () => {
  const browser = await chromium.launch({headless: true});
  report.browserVersion = browser.version();
  report.playwrightVersion = require(path.join(modulePath, 'package.json')).version;
  const contexts = [];

  async function boot(device, query = '') {
    const context = await browser.newContext({viewport: device === 'mobile' ? {width: 412, height: 892} : {width: 1440, height: 1000},
      isMobile: device === 'mobile', hasTouch: device === 'mobile', serviceWorkers: 'block', acceptDownloads: false});
    contexts.push(context);
    await context.route('**/*', route => {
      const req = route.request();
      if (new URL(req.url()).origin !== origin) { report.blockedExternalRequests++; return route.abort('blockedbyclient'); }
      if (req.isNavigationRequest() && isAccounts(req.url())) {
        report.blockedAccountsNavigations.push(safePath(req.url()));
        return route.abort('blockedbyclient');
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('response', r => { if ([401, 403].includes(r.status())) report.authStatuses.push({path: safePath(r.url()), status: r.status()}); });
    page.on('request', req => {
      const p = safePath(req.url());
      if (req.method() === 'POST' && /^\/wizard\//.test(p)) report.postPaths.push({at: now(), device, path: p});
      if (req.method() !== 'POST' || !/^\/wizard\/hermes\/(api\/sessions(\/[^/]+\/model)?|v1\/runs(\/[^/]+\/steer)?)$/.test(p)) return;
      let body = {}; try { body = JSON.parse(req.postData() || '{}'); } catch {}
      const row = {at: now(), device, path: p, body: pick(body, ['id', 'session_id', 'model', 'provider', 'require_model_lock', 'source'])};
      const inp = text(body.input); if (inp) row.body.input = clip(inp, 300);
      report.requests.push(row);
      req.response().then(async res => {
        row.status = res?.status();
        try { const j = await res.json(); row.response = pick(j, ['run_id', 'id', 'status']); if (j.runtime) row.response.runtime = pick(j.runtime, ['model', 'provider', 'model_lock']); } catch {}
      }).catch(() => {});
    });
    const file = device === 'desktop' ? 'desktop.html' : 'index.html';
    const root = new URL(file, origin + shellPath.replace(/[^/]*\.html$/, '')).href;
    const expectedPath = new URL(root).pathname;
    await page.goto('about:blank#before-wizard');
    const res = await page.goto(root + query, {waitUntil: 'domcontentloaded', timeout: 90000});
    await page.waitForFunction(() => !!window.WizCore, null, {timeout: 30000}).catch(() => {});
    await delay(2500);
    const tour = page.locator('[data-tskip]:visible');
    if (await visible(tour)) { await tour.first().click(); await delay(600); }
    const auth = await gate(page);
    check(!auth, auth);
    check(await inShell(page, expectedPath), 'installed Wizard shell did not load');
    return {context, page, root, expectedPath, httpStatus: res?.status(), device};
  }

  async function stage(name, fn) {
    const row = {stage: name, status: 'fail', started: now(), screenshots: []};
    report.stages.push(row);
    try { await fn(row); row.status = 'pass'; }
    catch (e) {
      row.reason = e.constructor === Error ? e.message : e.constructor.name;
      if (/https?:|Call log:|locator\./.test(row.reason)) row.reason = 'browser operation failed; inspect private screenshot';
    } finally { row.finished = now(); save(); }
    return row;
  }

  const api = async (page, p) => {
    const r = await page.request.get(origin + p, {timeout: 30000});
    check(r.ok(), `read ${p.split('?')[0]} -> ${r.status()}`);
    return r.json();
  };
  const sessionInfo = async (page, sid) => {
    const j = await api(page, `/wizard/hermes/api/sessions/${encodeURIComponent(sid)}`);
    const s = j.session || j;
    return {...pick(s, ['id', 'status', 'model', 'provider', 'message_count', 'wizard_model_lock_updated_at', 'source']),
      attention: s.wizard_attention || null};
  };
  const runInfo = async (page, rid) => pick(await api(page, `/wizard/hermes/v1/runs/${encodeURIComponent(rid)}`), ['id', 'run_id', 'status', 'model', 'provider', 'session_id']);
  const messages = async (page, sid) => {
    const j = await api(page, `/wizard/hermes/api/sessions/${encodeURIComponent(sid)}/messages?order=oldest&limit=500&offset=0&include_compacted=true&view=wizard`);
    return (j.data || j.messages || j.items || []).map(m => ({role: m.role, text: text(m.content)}));
  };
  const modelOk = o => !!o && MODEL_ALIASES.has(o.model) && o.provider === PROVIDER;

  async function newChat(b) {
    const fab = b.page.locator('[data-chfab]:visible');
    await fab.first().waitFor({state: 'visible', timeout: 20000});
    await (b.device === 'mobile' ? fab.first().tap() : fab.first().click());
    await b.page.locator('.ch-compose textarea:visible').first().waitFor({state: 'visible', timeout: 10000});
  }

  // A real pointer click when the target receives pointer events; otherwise record what covers it and
  // activate it the way a keyboard user would (focus + Enter). Never a synthetic DOM click.
  async function activate(page, loc, row, what) {
    const el = loc.first();
    await el.scrollIntoViewIfNeeded({timeout: 5000}).catch(() => {});
    try { await el.click({trial: true, timeout: 3000}); await el.click({timeout: 5000}); return 'pointer'; }
    catch {
      const cover = await el.evaluate(n => {
        const r = n.getBoundingClientRect(), e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return e && !n.contains(e) ? `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}.${String(e.className).split(' ')[0]} "${(e.innerText || '').trim().slice(0, 40)}"` : 'unknown';
      }).catch(() => 'unknown');
      row.findings = (row.findings || []).concat(`${what}: pointer target obscured by ${cover}; used keyboard focus+Enter`);
      await el.focus(); await page.keyboard.press('Enter');
      return 'keyboard';
    }
  }

  // Owner path: the header model chip opens the picker; pick Claude Opus on the Claude subscription.
  async function pickModelUi(b, row) {
    const {page} = b;
    const chip = page.locator('.ch-model[data-chmodel]:visible').first();
    const openSheet = async () => {
      await chip.click({timeout: 10000});
      await page.locator('.ch-msheet:visible').first().waitFor({state: 'visible', timeout: 10000});
      // The catalogue comes from the account's own Claude CLI handshake; slow under emulation.
      await page.waitForFunction(() => window.WosModels?.ready, null, {timeout: 240000});
      await delay(400);
    };
    await openSheet();
    row.screenshots.push(await shot(page, `${b.device}-${row.stage}-model-sheet`));
    const catalogue = await page.evaluate(p => ({
      ready: !!window.WosModels?.ready,
      subscriptionIds: (window.WosModels?.options || []).filter(o => o.provider === p).map(o => o.value),
      providers: [...new Set((window.WosModels?.options || []).map(o => o.provider))],
    }), PROVIDER);
    routeModel = pickRouteId(catalogue.subscriptionIds);
    catalogue.chosen = routeModel;
    row.catalogue = catalogue;
    check(routeModel, 'Claude Opus 5.5 on the Claude subscription is not in the installed model catalogue');
    // 1) the short list: a single "Claude Opus · Claude subscription" row
    const rows = page.locator('.ch-msheet [data-mpick]');
    const labels = await rows.evaluateAll(xs => xs.map(x => x.innerText.replace(/\s+/g, ' ').trim()));
    let idx = labels.findIndex(l => /Claude Opus/.test(l) && /Claude subscription/.test(l));
    const steps = [];
    let via = 'short-list';
    // The short list shows one row per family (e.g. the newest Opus), so a matching label is not proof of the id.
    if (idx >= 0) steps.push('short-list:' + await activate(page, rows.nth(idx), row, 'short-list row'));
    const chipModel = async () => (await chip.getAttribute('title')) || '';
    await delay(800);
    if (idx < 0 || await chipModel() !== routeModel) {
      // 2) "More models": the full catalogue, in WosModels.options order (sheetHtml: all -> M.options).
      if (idx >= 0) { row.shortListPicked = await chipModel(); await openSheet(); }
      const more = page.locator('.ch-msheet [data-mall]');
      check(await visible(more), 'picker has no matching row and no More models');
      steps.push('more-models:' + await activate(page, more, row, 'More models'));
      await delay(600);
      idx = await page.evaluate(([m, p]) => window.WosModels.options.findIndex(o => o.value === m && o.provider === p), [routeModel, PROVIDER]);
      check(idx >= 0, 'full catalogue lacks the required route');
      const exact = page.locator(`.ch-msheet [data-mpick="${idx}"]`);
      check(await visible(exact), 'full catalogue row not rendered');
      steps.push('catalogue-row:' + await activate(page, exact, row, 'catalogue row'));
      via = 'more-models';
      await delay(800);
    }
    row.pickerSteps = steps;
    row.modelChip = {title: await chipModel(), label: clip(await chip.innerText(), 60), aria: clip(await chip.getAttribute('aria-label'), 120)};
    check(row.modelChip.title === routeModel, 'model chip does not show Claude Opus 5.5 after picking');
    return {method: 'ui-picker', via, labels};
  }

  // Same backend route the UI calls (chat-models.js setThreadModel), only if the picker cannot select.
  async function pickModelRoute(b, row) {
    const sid = `wizard_${Date.now()}_${crypto.randomUUID().replaceAll('-', '').slice(0, 12)}`;
    const H = {'Content-Type': 'application/json', Origin: origin};
    const c = await b.page.request.post(origin + '/wizard/hermes/api/sessions', {headers: H, data: {source: 'wizard-mobile', id: sid, model: routeModel, provider: PROVIDER}});
    check(c.ok() || c.status() === 409, `session create -> ${c.status()}`);
    const r = await b.page.request.post(origin + `/wizard/hermes/api/sessions/${sid}/model`, {headers: H, data: {model: routeModel, provider: PROVIDER, require_model_lock: true}});
    check(r.ok(), `model route -> ${r.status()}`);
    const ack = await r.json();
    row.routeAck = pick(ack.runtime || {}, ['model', 'provider', 'model_lock', 'selection_version']);
    check(ack.runtime?.model_lock === 'accepted' && MODEL_ALIASES.has(ack.runtime?.model) && ack.runtime?.provider === PROVIDER, 'service did not confirm model lock');
    await b.page.goto(b.root + '?session=' + encodeURIComponent(sid), {waitUntil: 'domcontentloaded'});
    await delay(2500);
    await b.page.locator('.ch-compose textarea:visible').first().waitFor({state: 'visible', timeout: 15000});
    return {method: 'route-fallback', sessionId: sid};
  }

  async function chooseModel(b, row) {
    try { return await pickModelUi(b, row); }
    catch (e) {
      row.uiPickerFailure = e.constructor === Error ? e.message : e.constructor.name;
      row.screenshots.push(await shot(b.page, `${b.device}-${row.stage}-picker-failure`));
      await b.page.keyboard.press('Escape').catch(() => {});
      return pickModelRoute(b, row);
    }
  }

  async function send(b, message) {
    const ta = b.page.locator('.ch-compose textarea:visible').first();
    await ta.click(); await ta.fill(message); await delay(200);
    const row = report.stages[report.stages.length - 1] || {};
    row.sendActivation = await activate(b.page, b.page.locator('button.ch-send:visible'), row, 'Send');
    await delay(2500);
    // What the owner sees right after Send (toast, list, thread): diagnostic only.
    row.screenshots.push(await shot(b.page, `${b.device}-${row.stage}-after-send`));
    row.afterSend = await b.page.evaluate(() => ({
      toast: (document.querySelector('.toast, [role=status]')?.innerText || '').slice(0, 160),
      composerEmpty: !(document.querySelector('.ch-compose textarea')?.value || ''),
    })).catch(() => null);
  }

  // Wait for the outbox's real POSTs: the new session id and its run receipt.
  async function sent(message, knownSid) {
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      const run = report.requests.find(r => r.path === '/wizard/hermes/v1/runs' && typeof r.body.input === 'string'
        && r.body.input.includes(clip(message, 120)) && r.response?.run_id
        && (!knownSid || r.body.session_id === knownSid));
      if (run) return {sessionId: run.body.session_id, runId: run.response.run_id, body: run.body};
      await delay(1000);
    }
    throw new Error('the UI did not admit the message (no run receipt within 120 s)');
  }

  async function openThread(b, sid) {
    // Real row tap when the Chats list shows it; otherwise the documented ?session deep link.
    const rowEl = b.page.locator(`.ch-list [data-chopen="${sid}"]:visible`);
    if (await visible(rowEl)) { await (b.device === 'mobile' ? rowEl.first().tap() : rowEl.first().click()); await delay(1500); return 'row-tap'; }
    await b.page.goto(b.root + '?session=' + encodeURIComponent(sid), {waitUntil: 'domcontentloaded'});
    await delay(3000);
    return 'session-deeplink';
  }

  async function backFromThread(b, row, name) {
    const before = await b.page.locator('.ch-compose textarea:visible').count();
    await historyBack(b.page);
    const out = {view: name, threadOpenBefore: before > 0, inWizard: await inShell(b.page, b.expectedPath),
      composerVisibleAfter: await b.page.locator('.ch-compose textarea:visible').count() > 0,
      chatsListVisibleAfter: await visible(b.page.locator('.ch-list:visible'))};
    row.back = (row.back || []).concat(out);
    row.screenshots.push(await shot(b.page, `${b.device}-${name}-after-back`));
    check(out.inWizard, `Back exited Wizard from ${name}`);
    return out;
  }

  try {
    if (phase === 'ai') {
      let m = null;
      await stage('boot-mobile', async () => { m = await boot('mobile', '?view=chats'); });
      check(m, 'installed Wizard shell did not load');
      report.shell = {httpStatus: m.httpStatus, path: m.expectedPath};
      let chatSid = '';

      // ---------------- 1. READY chat
      await stage('chat-ready', async row => {
        await newChat(m);
        row.modelSelection = await chooseModel(m, row);
        row.screenshots.push(await shot(m.page, 'mobile-chat-model-picked'));
        await send(m, READY_PROMPT);
        const s = await sent(READY_PROMPT, row.modelSelection.sessionId);
        chatSid = s.sessionId; row.sessionId = s.sessionId; row.runId = s.runId; row.runBody = s.body;
        check(modelOk(s.body), 'UI sent the run on a different model/provider');
        check(s.body.require_model_lock === true, 'run was not model-locked');
        const deadline = Date.now() + 20 * 60000;
        let reply = null;
        while (Date.now() < deadline) {
          await delay(5000);
          const info = await sessionInfo(m.page, chatSid).catch(() => null);
          const msgs = await messages(m.page, chatSid).catch(() => []);
          const a = msgs.filter(x => x.role === 'assistant' && x.text.trim());
          row.lastStatus = info?.status;
          if (a.length && info && !WORKING.has(info.status)) { reply = a[a.length - 1].text; row.session = info; break; }
          if (info && ['failed', 'interrupted', 'cancelled'].includes(info.status)) { row.session = info; break; }
        }
        row.run = await runInfo(m.page, s.runId).catch(e => ({unavailable: true}));
        check(reply, `no assistant reply (status ${row.lastStatus || 'unknown'})`);
        row.reply = clip(reply, 200);
        row.replyIsExactlyReady = reply.trim().replace(/[.!]$/, '') === 'READY';
        check(modelOk(row.session), `service recorded ${row.session?.model}/${row.session?.provider}`);
        row.openedVia = await openThread(m, chatSid);
        await m.page.locator('.msg.a .bub:visible').filter({hasText: 'READY'}).first().waitFor({state: 'visible', timeout: 30000});
        row.screenshots.push(await shot(m.page, 'mobile-chat-ready-reply'));
        await backFromThread(m, row, 'chat-ready-thread');
      });

      // Desktop readback of the same thread (cheap): deep link, reply visible, Back stays in Wizard.
      await stage('chat-ready-desktop', async row => {
        check(chatSid, 'no chat thread to read back');
        const d = await boot('desktop', '?session=' + encodeURIComponent(chatSid));
        await d.page.locator('.msg.a .bub:visible').filter({hasText: 'READY'}).first().waitFor({state: 'visible', timeout: 30000});
        row.chip = await d.page.locator('.ch-model[data-chmodel]:visible').first().getAttribute('title').catch(() => null);
        row.screenshots.push(await shot(d.page, 'desktop-chat-ready-reply'));
        await backFromThread(d, row, 'chat-ready-thread-desktop');
        await d.context.close();
      });

      // ---------------- 2. DeFleur request, typed like an owner, in a NEW chat
      await stage('defleur-edit', async row => {
        row.mediaBefore = guestProbe('snapshot');
        check(row.mediaBefore.status === 'pass', 'media snapshot failed');
        await m.page.goto(m.root + '?view=chats', {waitUntil: 'domcontentloaded'}); await delay(2500);
        await newChat(m);
        row.modelSelection = await chooseModel(m, row);
        row.message = cfg.message;
        await send(m, cfg.message);
        const s = await sent(cfg.message, row.modelSelection.sessionId);
        const sid = s.sessionId; row.sessionId = sid; row.runIds = [s.runId]; row.runBody = s.body;
        check(modelOk(s.body), 'UI sent the DeFleur run on a different model/provider');
        row.screenshots.push(await shot(m.page, 'mobile-defleur-sent'));
        const started = Date.now(), limit = cfg.waitSeconds * 1000, every = cfg.pollSeconds * 1000;
        row.timeline = [];
        let answered = false, stableFor = 0, lastSizes = '', outcome = 'timeout', idleSince = 0;
        while (Date.now() - started < limit) {
          await delay(every);
          const info = await sessionInfo(m.page, sid).catch(() => null);
          const run = await runInfo(m.page, row.runIds[row.runIds.length - 1]).catch(() => null);
          let vids = {};
          try { vids = guestProbe('poll').new_videos || {}; } catch { vids = null; }
          const t = {t: Math.round((Date.now() - started) / 1000), session: info?.status, run: run?.status,
            messages: info?.message_count, newVideos: vids ? Object.keys(vids).length : 'probe-failed'};
          row.timeline.push(t); save();
          if (info) row.session = info;
          if (info?.status === 'waiting_for_approval' || run?.status === 'waiting_for_approval') {
            outcome = 'approval-requested'; break;  // the runner never approves on the owner's behalf
          }
          const idle = info && !WORKING.has(info.status) && (!run || TERMINAL.has(run.status) || !run.status);
          const sizes = JSON.stringify(vids || {});
          stableFor = sizes === lastSizes ? stableFor + 1 : 0; lastSizes = sizes;
          if (idle && vids && Object.keys(vids).length && stableFor >= 1) { outcome = 'output-appeared'; break; }
          const dead = ['failed', 'interrupted', 'cancelled'];
          if (idle && (dead.includes(info.status) || dead.includes(run?.status))) {
            // A failed run with no reply is final: no answer to give, nothing for DeFleur to render.
            const msgs = await messages(m.page, sid).catch(() => []);
            if (!msgs.some(x => x.role === 'assistant' && x.text.trim()) || dead.includes(info.status)) {
              outcome = 'run-' + (dead.includes(run?.status) ? run.status : info.status); break;
            }
          }
          if (idle && vids && !Object.keys(vids).length) {
            const msgs = await messages(m.page, sid).catch(() => []);
            const a = msgs.filter(x => x.role === 'assistant' && x.text.trim());
            const last = a.length ? a[a.length - 1].text : '';
            if (!answered && /\?/.test(last.trim().slice(-300))) {
              // The agent asked something: answer once, briefly, like a person would.
              row.question = clip(last.slice(-400), 400);
              await openThread(m, sid);
              await send(m, ANSWER);
              const s2 = await sent(ANSWER, sid);
              row.runIds.push(s2.runId); row.answeredAt = Math.round((Date.now() - started) / 1000);
              answered = true; idleSince = 0; continue;
            }
            // DeFleur renders asynchronously after the agent's turn ends: keep watching Files for the output,
            // but stop once the agent has been idle with no new video for the idle grace period.
            idleSince = idleSince || Date.now();
            if (a.length && Date.now() - idleSince > cfg.idleGraceSeconds * 1000) { outcome = 'agent-idle-without-output'; row.lastReply = clip(last, 800); break; }
          } else if (!idle) idleSince = 0;
        }
        if (outcome === 'timeout' && lastSizes && lastSizes !== '{}') outcome = 'timeout-agent-still-working-output-present';
        row.outcome = outcome;
        row.idleGraceSeconds = cfg.idleGraceSeconds;
        row.waitedSeconds = Math.round((Date.now() - started) / 1000);
        const msgs = await messages(m.page, sid).catch(() => []);
        row.lastReply = row.lastReply || clip((msgs.filter(x => x.role === 'assistant').pop() || {}).text, 800);
        row.runs = [];
        for (const rid of row.runIds) row.runs.push(await runInfo(m.page, rid).catch(() => ({id: rid, unavailable: true})));
        row.openedVia = await openThread(m, sid);
        row.screenshots.push(await shot(m.page, 'mobile-defleur-thread'));
        await backFromThread(m, row, 'defleur-thread');
        check(modelOk(row.session), `service recorded ${row.session?.model}/${row.session?.provider}`);
        check(outcome === 'output-appeared', `DeFleur run ended: ${outcome}`);
      });
      report.sessions = report.stages.map(s => s.sessionId).filter(Boolean);
      report.status = report.stages.every(s => s.status === 'pass') ? 'pass' : 'fail';
    } else if (phase === 'files') {
      await stage('files-output-back', async row => {
        const rel = cfg.relPath; check(rel && !rel.includes('..'), 'no output path');
        const parts = rel.split('/');
        const b = await boot('mobile', '?open=files');
        let frame;
        for (let n = 0; n < 40 && !frame; n++) {
          for (const f of b.page.frames().slice(1)) {
            const el = await f.frameElement().catch(() => null);
            if (el && await el.isVisible() && /\/files(?:\/|$)/.test(safePath(f.url()))) { frame = f; break; }
          }
          if (!frame) await delay(500);
        }
        check(frame, 'Files hosted view unavailable');
        let parentPath = await frame.evaluate(() => location.pathname);
        for (const dir of parts.slice(0, -1)) {
          const item = frame.getByText(dir, {exact: true}).first();
          await item.waitFor({state: 'visible', timeout: 20000});
          parentPath = await frame.evaluate(() => location.pathname);
          await item.dblclick(); await delay(1200);
        }
        const leafPath = await frame.evaluate(() => location.pathname);
        const name = parts[parts.length - 1];
        await frame.getByText(name, {exact: true}).first().waitFor({state: 'visible', timeout: 20000});
        row.screenshots.push(await shot(b.page, 'mobile-files-output-visible'));
        row.outputVisible = name;
        await historyBack(b.page);
        row.back = [{view: 'files-output-folder', inWizard: await inShell(b.page, b.expectedPath),
          filesStillOpen: !frame.isDetached() && await (await frame.frameElement()).isVisible().catch(() => false),
          leftLeafFolder: parts.length > 1 ? (await frame.evaluate(() => location.pathname).catch(() => '')) !== leafPath : null}];
        row.screenshots.push(await shot(b.page, 'mobile-files-after-back'));
        check(row.back[0].inWizard, 'Files Back exited Wizard');
        row.nested = parts.length > 1;
        if (row.nested) check(row.back[0].filesStillOpen, 'Files closed on nested Back');
      });
      report.status = report.stages.every(s => s.status === 'pass') ? 'pass' : 'fail';
    }
  } finally {
    for (const c of contexts) await c.close().catch(() => {});
    await browser.close();
    report.networkPolicy = 'same-origin only; AI Accounts navigations aborted; no response fixtures; no HAR/console/cookie capture';
    save();
  }
  process.exitCode = report.status === 'pass' ? 0 : 2;
})().catch(e => { report.status = 'fail'; report.fatal = e.constructor.name; save(); process.exitCode = 1; });
