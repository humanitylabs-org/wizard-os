#!/usr/bin/env node
/* Actual installed pages only. No injected app state, fake APIs, credentials,
 * model calls, auth bootstrap, network traces, localStorage or cookie dumps. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const [modulePath, origin, shellPath, evidence, clipFolder] = process.argv.slice(2);
const {chromium} = require(modulePath);
const report = {scope: 'installed browser UI, non-AI', stages: [], blockedWrites: [],
  blockedExternalRequests: 0, websocketConnectionsDenied: 0, authStatuses: [],
  aiAcceptance: 'blocked: owner sign-in required', physicalAndroidAcceptance: 'not tested'};
const safePath = url => { try { return new URL(url).pathname; } catch { return '(invalid URL)'; } };
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const save = () => fs.writeFileSync(path.join(evidence, 'browser-receipt.json'), JSON.stringify(report, null, 2));
const check = (ok, reason) => { if (!ok) throw new Error(reason); };
const settings = p => p.locator('#dsettings:visible, #settingsBody:visible');
const visible = async l => (await l.count()) > 0 && await l.first().isVisible();
const delay = ms => new Promise(r => setTimeout(r, ms));

async function shot(page, name) {
  const file = `${name}.png`;
  // Screenshots are private. No auth form is ever filled, and password inputs masked.
  await page.screenshot({path: path.join(evidence, file), fullPage: true,
    mask: [page.locator('input[type=password]')]});
  return {file, sha256: hash(fs.readFileSync(path.join(evidence, file)))};
}
async function gate(page) {
  for (const frame of page.frames()) {
    try {
      if (await visible(frame.locator('input[type=password]')))
        return 'visible password/login form; no credentials supplied';
      if (await visible(frame.getByRole('button', {name: /^(unlock|sign in|log in)$/i})))
        return 'visible owner sign-in/unlock gate; not bypassed';
    } catch {}
  }
  return null;
}
async function back(page, method) {
  if (method === 'history') {
    await page.goBack({waitUntil: 'domcontentloaded', timeout: 15000}).catch(e => {
      if (!String(e.message).includes('ERR_ABORTED')) throw e;
    });
  } else {
    await page.keyboard.press('Escape');
  }
  await delay(900); // include settled async traversal, not only the first painted frame
}
async function atHome(page, device) {
  return page.evaluate(device => {
    const el = document.querySelector(device === 'desktop' ? '#desktopHome' : '.home-desk');
    if (!el || el.hidden || !el.getClientRects().length) return false;
    const box = el.getBoundingClientRect();
    return box.left < innerWidth / 2 && box.right > innerWidth / 2 && box.height > 0;
  }, device);
}
async function inShell(page, expectedPath) {
  if (page.isClosed()) return false;
  const u = new URL(page.url());
  return u.origin === origin && u.pathname === expectedPath &&
    await page.evaluate(() => !!window.WizCore && !!document.body?.children.length);
}

(async () => {
  const browser = await chromium.launch({headless: true});
  report.browserVersion = browser.version();
  report.playwrightVersion = require(path.join(modulePath, 'package.json')).version;
  async function journey(device, name, fn) {
    const context = await browser.newContext({viewport: device === 'mobile' ? {width: 412, height: 892} : {width: 1440, height: 1000},
      isMobile: device === 'mobile', hasTouch: device === 'mobile', serviceWorkers: 'block', acceptDownloads: false});
    await context.route('**/*', route => {
      const req = route.request();
      if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method())) {
        report.blockedWrites.push({method: req.method(), path: safePath(req.url())});
        return route.abort('blockedbyclient');
      }
      if (new URL(req.url()).origin !== origin) {
        report.blockedExternalRequests++;
        return route.abort('blockedbyclient');
      }
      return route.continue();
    });
    await context.routeWebSocket('**/*', ws => {
      report.websocketConnectionsDenied++;
      ws.close();
    });
    const page = await context.newPage();
    const authStart = report.authStatuses.length;
    page.on('response', r => {
      if ([401, 403].includes(r.status())) report.authStatuses.push({path: safePath(r.url()), status: r.status()});
    });
    // No HAR/tracing/console capture: those can contain auth/bootstrap secrets.
    const file = device === 'desktop' ? 'desktop.html' : 'index.html';
    const root = new URL(file, origin + shellPath.replace(/[^/]*\.html$/, '')).href;
    const expectedPath = new URL(root).pathname;
    const row = {device, journey: name, status: 'fail', screenshots: []};
    try {
      // Real preceding navigation exposes a root guard failure; no injected pushState guard.
      await page.goto('about:blank#before-wizard');
      const response = await page.goto(root, {waitUntil: 'domcontentloaded', timeout: 60000});
      row.httpStatus = response?.status();
      await page.waitForFunction(() => !!window.WizCore, null, {timeout: 15000}).catch(() => {});
      await delay(1800);
      row.screenshots.push(await shot(page, `${device}-${name}-entry`));
      const auth = await gate(page);
      if (auth) { row.status = 'blocked'; row.reason = auth; return; }
      check(await inShell(page, expectedPath), 'installed Wizard shell did not load');
      // Hash served installed HTML/JS, do not use local replacements.
      row.servedAssets = [];
      for (const asset of [root, new URL('core/apps.js', root).href]) {
        const r = await context.request.get(asset);
        row.servedAssets.push({path: safePath(asset), status: r.status(), sha256: hash(await r.body())});
      }
      await fn({page, row, root, expectedPath});
      row.status = 'pass';
    } catch (e) {
      // Restrict errors to our own assertion messages or a generic class. Playwright
      // call logs can contain URLs/query strings and should never go into receipts.
      row.reason = e.constructor === Error ? e.message : e.constructor.name;
      if (/https?:|Call log:|locator\./.test(row.reason)) row.reason = 'browser operation failed; inspect private screenshot';
      const auth = await gate(page);
      if (auth) { row.status = 'blocked'; row.reason = auth; }
      else if (report.authStatuses.length > authStart) {
        row.status = 'blocked'; row.reason = 'navigation incomplete with actual HTTP 401/403; no auth bootstrap attempted';
      }
      if (!page.isClosed()) row.screenshots.push(await shot(page, `${device}-${name}-failure`).catch(() => ({capture: 'failed'})));
    } finally {
      row.authStatuses = report.authStatuses.slice(authStart);
      report.stages.push(row);
      save();
      await context.close();
    }
  }
  try {
    for (const device of ['desktop', 'mobile']) {
      for (const method of ['history', 'escape']) {
        await journey(device, `settings-back-${method}`, async ({page, row, expectedPath}) => {
          // Three independent nested opens, real user clicks, one Back per open.
          for (let n = 1; n <= 3; n++) {
            const button = page.locator('#settingsBtn:visible, [data-act=settings]:visible').first();
            await button.click({timeout: 15000});
            await settings(page).first().waitFor({state: 'visible', timeout: 5000});
            row.screenshots.push(await shot(page, `${device}-settings-${method}-${n}-nested`));
            await back(page, method);
            check(await inShell(page, expectedPath), 'Back exited installed Wizard from Settings');
            check(!await visible(settings(page)), 'Back did not close precisely the Settings layer');
          }
          row.screenshots.push(await shot(page, `${device}-settings-${method}-returned`));
          row.repetitions = 3;
          row.coverage = 'shell-owned Settings overlay; not Files nested coverage';
        });
        await journey(device, `root-back-${method}`, async ({page, row, expectedPath}) => {
          check(!await visible(settings(page)) && await atHome(page, device), 'not at shell home/root');
          check(await page.evaluate(() => history.length >= 2), 'root history precondition missing');
          // Tap inert body space for genuine activation without installing test handlers.
          await page.locator('body').click({position: {x: 3, y: 3}});
          await back(page, method);
          check(await inShell(page, expectedPath) && await atHome(page, device), 'first root Back exited Wizard home');
          const warning = await page.getByText(/press back again to exit/i).count();
          row.firstBackWarning = warning > 0;
          row.rootBehavior = warning ? 'double-back floor shown; first Back stayed' : 'root consumed Back and stayed';
          row.screenshots.push(await shot(page, `${device}-root-${method}-after-first-back`));
          await delay(2300);
          await page.locator('body').click({position: {x: 3, y: 3}});
          await back(page, method);
          check(await inShell(page, expectedPath), 'root Back after exit-window timeout exited Wizard');
          row.screenshots.push(await shot(page, `${device}-root-${method}-after-timeout`));
        });
      }
      await journey(device, 'files-nested-history', async ({page, row, root, expectedPath}) => {
        // Canonical launcher entry, not direct file-server navigation or a fake app.
        await page.goto(root + '?open=files', {waitUntil: 'domcontentloaded', timeout: 60000});
        await delay(2500);
        row.screenshots.push(await shot(page, `${device}-files-open`));
        const auth = await gate(page);
        if (auth) throw new Error(auth);
        let frame;
        for (let n = 0; n < 30 && !frame; n++) {
          for (const f of page.frames().slice(1)) {
            const el = await f.frameElement().catch(() => null);
            if (el && await el.isVisible() && /\/files(?:\/|$)/.test(safePath(f.url()))) { frame = f; break; }
          }
          if (!frame) await delay(500);
        }
        check(frame, 'Files hosted view unavailable; nested Back is not proven');
        const videos = frame.getByText('Videos', {exact: true}).first();
        await videos.waitFor({state: 'visible', timeout: 15000});
        const filesRoot = await frame.evaluate(() => location.pathname);
        await videos.dblclick();
        const folder = frame.getByText(clipFolder, {exact: true}).first();
        await folder.waitFor({state: 'visible', timeout: 10000});
        const videosPath = await frame.evaluate(() => location.pathname);
        check(videosPath !== filesRoot, 'Videos did not open a real nested Files route');
        await folder.dblclick();
        await frame.getByText('release-acceptance-source.mp4', {exact: true}).first().waitFor({state: 'visible', timeout: 10000});
        row.screenshots.push(await shot(page, `${device}-files-synthetic-source-visible`));
        await back(page, 'history');
        check(await inShell(page, expectedPath), 'Files nested Back exited Wizard');
        check(!frame.isDetached() && await (await frame.frameElement()).isVisible(), 'Files closed on nested Back');
        check(await frame.evaluate(() => location.pathname) === videosPath, 'Back skipped Files Videos parent');
        check(await folder.isVisible(), 'Back did not restore exact parent listing');
        row.screenshots.push(await shot(page, `${device}-files-back-parent`));
        row.sourceFilenameVerified = 'release-acceptance-source.mp4';
        row.coverage = 'Files Videos/test-folder -> browser Back -> Videos; real generated source listing';
      });
    }
  } finally {
    await browser.close();
    report.status = report.stages.length === 10 && report.stages.every(r => r.status === 'pass') ? 'pass' : 'incomplete';
    report.journeyCount = report.stages.length;
    report.networkPolicy = 'only same-origin GET/HEAD/OPTIONS; all writes/websockets denied; no response fixtures';
    save();
  }
  process.exitCode = report.status === 'pass' ? 0 : 2;
})().catch(e => {
  report.status = 'fail'; report.fatal = e.constructor.name; save(); process.exitCode = 1;
});
