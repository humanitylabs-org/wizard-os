// Run 3 (wizard-os 389 addendum): real Chromium checks for the release-blocker fixes, flag ON.
// usage: node run6.cjs <profile> <label> <step>    steps: views | store-get | store-remove
//  views:        Notifications renders with NO manual grant (O5); App Store data loads in its opaque window (O1),
//                and every store-data/store-install request comes from the SHELL document, never the frame.
//  store-get:    Store UI "Get" wizard-files -> shell Review chip -> dialog -> confirm (trusted) -> installed.
//  store-remove: Store UI "Remove app" wizard-files -> Store's own sheet -> shell Review -> confirm -> removed.
const { open, shot, ORIGIN } = require('./lib.cjs')
const fs = require('fs')
const [profile, label, step] = process.argv.slice(2)
const R = { label, step, checks: [] }
const rec = (name, pass, got) => { R.checks.push({ name, pass, got }); console.log(pass ? 'PASS' : 'FAIL', name, '|', JSON.stringify(got).slice(0, 300)) }
;(async () => {
  const ctx = await open(profile, { colorScheme: 'dark' })
  await ctx.addInitScript(() => {
    if (window.top !== window) return
    const c = window.close.bind(window)
    window.close = function () { console.log('DIAG window.close called\n' + new Error().stack); return c() }
    addEventListener('pagehide', (e) => console.log('DIAG pagehide persisted=' + e.persisted))
    addEventListener('beforeunload', () => console.log('DIAG beforeunload'))
  })
  const page = ctx.pages()[0] || await ctx.newPage()
  const cdp = await page.context().newCDPSession(page)
  cdp.on('Inspector.detached', (e) => console.log('EVENT inspector detached', JSON.stringify(e)))
  cdp.on('Inspector.targetCrashed', () => console.log('EVENT target crashed'))
  await cdp.send('Inspector.enable').catch((e) => console.log('inspector enable', String(e)))
  cdp.on('Runtime.exceptionThrown', (e) => console.log('EXC', JSON.stringify(e.exceptionDetails).slice(0, 600)))
  await cdp.send('Runtime.enable')
  const errors = [], storeReqs = []
  page.on('crash', () => console.log('EVENT page crash')); page.on('close', () => console.log('EVENT page close')); ctx.on('page', (p) => console.log('EVENT new page', p.url())); ctx.on('close', () => console.log('EVENT ctx close')); page.on('framenavigated', (f) => { if (f === page.mainFrame()) console.log('EVENT nav', f.url()) })
  page.on('console', (m) => { console.log('CONSOLE', m.type(), m.text().slice(0, 800)); if (m.type() === 'error') errors.push(m.text().slice(0, 200)) })
  page.on('response', async (r) => { if (/store-(data|install)\//.test(r.url()) && r.request().method() !== 'GET') { let b = ''; try { b = (await r.text()).slice(0, 400) } catch (e) { b = '[' + String(e).slice(0, 60) + ']' } console.log('RESP', r.status(), r.request().method(), r.url(), b) } })
  page.on('requestfailed', (r) => { if (!/ERR_ABORTED/.test(r.failure()?.errorText || '')) console.log('REQFAILED', r.method(), r.url(), r.failure()?.errorText) })
  page.on('request', (r) => { if (r.method() !== 'GET') console.log('REQ', r.method(), r.url(), r.frame() === page.mainFrame() ? 'shell' : 'frame') })
  page.on('request', (r) => {
    if (/\/wizard-os-home\/store-(data|install)\//.test(r.url())) storeReqs.push({ url: r.url().replace(ORIGIN, ''), method: r.method(), fromShell: r.frame() === page.mainFrame(), origin: r.headers().origin || null })
  })
  await page.goto(ORIGIN + '/', { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.waitForTimeout(7000)
  await page.evaluate(() => { document.getElementById('wosWelcome')?.remove(); localStorage.setItem('wos.wsync.off', 'true') })
  for (let i = 0; i < 12; i++) { const n = await page.evaluate(() => { const b = [...document.querySelectorAll('.wclose, [aria-label="Close"], [title="Close"]')].filter((x) => x.offsetWidth); b.forEach((x) => x.click()); return b.length }); if (!n) break; await page.waitForTimeout(400) }
  const frameOf = (re) => page.frames().find((f) => re.test(f.url()))
  const text = async (f) => { try { return (await f.evaluate(() => document.body?.innerText || '')).slice(0, 1200) } catch (e) { return '[unreadable ' + String(e).slice(0, 60) + ']' } }
  const openStore = async () => {
    await page.evaluate(() => window.WizOpenApp('app-store')); await page.waitForTimeout(12000)
    return frameOf(/\/wizard-os-home\/store\//)
  }
  const confirmInShell = async (what) => {
    const chip = page.locator('.wz-intent-chip')
    await chip.first().waitFor({ timeout: 60000 })
    rec(`${what}: shell Review chip appears (frame asked, shell decides)`, true, await chip.first().textContent())
    await chip.first().click()
    const go = page.locator('dialog.wz-intent .wzi-go')
    await go.waitFor({ timeout: 10000 })
    rec(`${what}: shell dialog text`, true, (await page.locator('dialog.wz-intent').innerText()).slice(0, 300))
    await shot(page, `${label}-${step}-review`)
    await page.waitForTimeout(800)   // the action button wakes after 500 ms
    await go.click()
  }

  if (step === 'views') {
    await page.evaluate(() => window.WizOpenApp('notifications')); await page.waitForTimeout(9000)
    const nf = frameOf(/\/notifications\//)
    const nt = nf ? await text(nf) : '[no frame]'
    rec('O5 Notifications renders without a manual grant', !!nf && !/need permission|needs permission/i.test(nt) && /Rehearsal|Synthetic|notification/i.test(nt), nt.slice(0, 300))
    await shot(page, `${label}-notifications`)
    await page.evaluate(() => document.querySelectorAll('.wclose, [aria-label="Close"]').forEach((b) => b.click())); await page.waitForTimeout(1500)
    storeReqs.length = 0
    const sf = await openStore()
    const st = sf ? await text(sf) : '[no frame]'
    const sandbox = await page.evaluate(() => [...document.querySelectorAll('iframe')].map((f) => ({ src: f.getAttribute('src'), sandbox: f.getAttribute('sandbox') })).find((f) => /store/.test(f.src || '')))
    rec('O1 Store window is still an opaque frame', !!sandbox && !/allow-same-origin/.test(sandbox.sandbox || ''), sandbox)
    rec('O1 Store shows index data (no "isn\'t reachable")', !!sf && !/isn.t reachable|couldn.t|unavailable right now/i.test(st) && /Apps|Agent apps/.test(st), st.slice(0, 400))
    rec('O1 every Store data request is made by the shell document, none by the frame', storeReqs.length > 0 && storeReqs.every((r) => r.fromShell), storeReqs.slice(0, 12))
    if (sf) {
      const direct = await sf.evaluate(async () => { try { const r = await (window.__nativeFetchProbe || fetch)('../store-data/wizard/v1/installed-apps'); return 'status ' + r.status } catch (e) { return 'threw ' + e } })
      rec('O1 the bridge answers only through the shell (same call from the frame -> typed op)', /status 200/.test(direct), direct)
      const raw = await sf.evaluate(async () => { try { const r = await fetch('../store-data/wizard/v1/anything-else'); return 'status ' + r.status + ' ' + (await r.text()).slice(0, 80) } catch (e) { return 'threw ' + e } })
      rec('O1 anything else under store-data from the frame is refused', /status 403/.test(raw), raw)
      const evil = await sf.evaluate(async () => { try { const r = await window.WizBoundaryClient.request('store.call', { op: 'fetch', args: { url: '/wizard/v1/apps' } }); return 'ok ' + JSON.stringify(r).slice(0, 80) } catch (e) { return 'refused ' + e.code } })
      rec('O1 not a relay: an unknown store op is refused', /^refused not_allowed/.test(evil), evil)
    }
    await shot(page, `${label}-app-store`)
  } else if (step === 'store-get' || step === 'store-remove' || step === 'look' || step === 'link') {
    const sf = await openStore()
    if (step !== 'link') await sf.fill('#q', 'Wizard Files').catch(() => {})
    await page.waitForTimeout(2500)
    const card = sf.locator('.row[data-app^="wizard-files"]')
    if (step !== 'link') rec('Store lists wizard-files', (await card.count()) > 0, await card.count())
    if (step === 'link') {
      // The Store's own install-link entry (same as opening /wizard-os-home/?view=install&repo=..&commit=..).
      const q = '?view=install&repo=humanitylabs-org/wizard-files&commit=' + process.env.LINK_COMMIT
      await sf.evaluate((x) => window.__store.openInstallLink(x), q)
      let t = ''
      for (let i = 0; i < 20; i++) { await page.waitForTimeout(1500); t = await text(sf); if (!/Checking the GitHub app/.test(t)) break }
      const btn = await sf.evaluate(() => document.querySelector('[data-link-install]')?.textContent || null)
      rec('Link sheet shows the expected action', btn === (process.env.EXPECT || 'Install'), { button: btn, text: t.slice(0, 500) })
      await shot(page, `${label}-link-sheet`)
      if (btn) {
        await sf.evaluate(() => document.querySelector('[data-link-install]').click())
        await page.waitForTimeout(2500)
        rec('nothing POSTed before the owner confirms in shell UI', storeReqs.filter((r) => r.method === 'POST').length === 0, storeReqs.filter((r) => r.method === 'POST').length)
        await confirmInShell('Store link ' + btn)
        let st = ''
        for (let i = 0; i < 100; i++) { await page.waitForTimeout(5000); st = await text(sf); if (!/Installing|Updating|Checking/.test(st) && /Open|installed|Installed|not confirmed|failed|couldn/i.test(st)) break }
        rec('Store link ' + btn + ' finished', /Open|is installed|✓ Installed/.test(st) && !/not confirmed/.test(st), st.slice(0, 500))
      }
    } else if (step === 'look') {
      rec('rows', true, await sf.evaluate(() => [...document.querySelectorAll('.row[data-app]')].map((r) => r.getAttribute('data-app') + ' :: ' + r.innerText.replace(/\s+/g, ' ') + ' :: ' + [...r.querySelectorAll('[data-get]')].map((b) => b.getAttribute('data-get') + '=' + b.textContent).join(','))))
      await shot(page, `${label}-look`)
    } else if (step === 'store-get') {
      // The Store's own button (its UI, not consent): the frame's click handler takes it.
      const clicked = await sf.evaluate((sel) => { const b = document.querySelector(sel); b?.click(); return b ? b.getAttribute('data-get') + '=' + b.textContent : false }, process.env.GET_SEL || '[data-get^="wizard-files|"]'); rec('Store Get/Update clicked', !!clicked, clicked)
      await page.waitForTimeout(2500)
      const before = storeReqs.filter((r) => r.method === 'POST').length
      rec('nothing POSTed before the owner confirms in shell UI', before === 0, before)
      await confirmInShell('Store Get wizard-files')
      let st = ''
      for (let i = 0; i < (process.env.QUICK ? 3 : 90); i++) { await page.waitForTimeout(5000); st = await text(sf); if (process.env.DONE_RE ? new RegExp(process.env.DONE_RE).test(st) : (/Open|✓ Installed|Installed/.test(st) && !/Installing|Updating/.test(st))) break }
      if (process.env.QUICK) rec('QUICK: Store window text 15 s after confirm', true, st.slice(0, 400) + ' | toast: ' + await sf.evaluate(() => [...document.querySelectorAll('.toast, [role=status], [role=alert]')].map((x) => x.innerText).join(' / ')).catch(() => '?'))
      rec('Store Get finished (installed)', /Open|Installed/.test(st), st.slice(0, 300))
    } else {
      // Open the detail (the result card), then the Store's own "Remove app" sheet and its button (Store UI, not consent).
      const opened = await sf.evaluate(() => { const c = document.querySelector('.row[data-app^="wizard-files"] .tx'); c?.click(); return c ? c.parentElement.outerHTML.slice(0, 120) : null })
      await page.waitForTimeout(2500)
      const rm = await sf.evaluate(() => { const b = document.querySelector('[data-remove^="wizard-files"]'); b?.click(); return !!b })
      rec('Store detail has Remove app', rm, opened)
      await page.waitForTimeout(5000)
      rec('Store Remove sheet confirm clicked', await sf.evaluate(() => { const b = document.querySelector('[data-remove-confirm]'); if (b && !b.disabled) b.click(); return !!b && !b.disabled }), await text(sf))
      await confirmInShell('Store Remove wizard-files')
      let st = ''
      for (let i = 0; i < (process.env.QUICK ? 3 : 60); i++) { await page.waitForTimeout(5000); st = await text(sf); if (/removed|Get/i.test(st) && !/Removing/.test(st)) break }
      if (process.env.QUICK) rec('QUICK: Store window text 15 s after confirm', true, st.slice(0, 400) + ' | toast: ' + await sf.evaluate(() => [...document.querySelectorAll('.toast, [role=status], [role=alert]')].map((x) => x.innerText).join(' / ')).catch(() => '?'))
      rec('Store Remove finished', /removed|Get/i.test(st), st.slice(0, 300))
    }
    await shot(page, `${label}-${step}`)
    rec('Store owner changes went out from the shell document only', storeReqs.filter((r) => r.method === 'POST').every((r) => r.fromShell), storeReqs.filter((r) => r.method === 'POST'))
  }
  R.errors = errors.slice(0, 30)
  fs.writeFileSync(`../out/run8-${label}-${step}.json`, JSON.stringify(R, null, 2))
  await ctx.close()
})().catch((e) => { console.error(e); fs.writeFileSync(`../out/run8-${label}-${step}.json`, JSON.stringify({ ...R, crash: String(e) }, null, 2)); process.exit(1) })
