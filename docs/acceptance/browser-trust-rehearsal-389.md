# Browser-isolation release rehearsal: wizard-os #389 (card 6), run 2

> **Run 3 (final) is appended at the end:** [Run 3](#run-3-final-candidates-03103-bt3896--7-flag-on), with the final pass/fail table and remaining blockers. **Run 4** closes R16 (Store window on a fresh box): [Run 4](#run-4-r16-store-window-on-a-fresh-box-diagnosed-not-a-product-bug).

Raw receipts: [browser-trust-389/raw](browser-trust-389/raw), screenshots: [browser-trust-389/screenshots](browser-trust-389/screenshots) (inspected).

**Verdict: not release-ready.** The browser boundary stays default-off. Every PR below is a draft, and nothing was merged, released or published to a real registry. This dossier covers synthetic data on a disposable KVM alongside box (`wizard-train-guest`, ssh 2273, its own headscale). It does not cover oscar-main, James's box or any phone. Device lanes are not covered at all: Jan's APK/Mac and real phone gestures were not run.

## Candidate under test: `0.3.103-bt389.5` (rehearsal-only release, never published)

This is 0.3.102 plus the draft stacks at these heads. Images are local builds of exact GitHub commits, served from a loopback-only registry (127.0.0.1:5000) that the guest reaches through an ssh reverse tunnel.

| Component | Head | Notes |
|---|---|---|
| App Manager | WAM #422 `1c862d9` (contains `5376b25`), integration `018d28e5` (+0.3.102 pin) | image `bt389-41eac4bd368b` reused: image inputs unchanged |
| Shell | UX #865 `8b63b5d3` + #866 `c1309f24` + **#873 `f18aff2d`**, integration `c1932e10` | image `localhost:5000/wizard-ux:bt389-c1932e100342` `sha256:f10c0be9…` |
| Agent Service | **#318 `78063a4`** on #317 `2beacaa0` | image `bt389-78063a4` `sha256:ea090821…` |
| Troubleshooter | **#30 `37c5367`** on #28 | |
| Notifications | **#23 `610f11d`** on #21 | |
| ChatGPT / Claude | chatgpt-connection #19 + rehearsal engine commit `15009cf0`; claude-connection #23 + `ecde674d` | engines = local builds of wizard-app-store #58 `b32a510a` |
| Files (own tab) / Transcriber / Browser / Secret Drop / Voice | files #3 `5e2fc4d`, transcriber #1 `c3f6600`, browser #2 `556017f`, secret-drop #2 `e1bed1d`, voice #10 + rehearsal image commit `6e748ef9` | |
| Wizard Files (Store candidate) | wizard-files #11 **`5765f57`** | see #10 below |

The boundary switch is still rehearsal-only (`enable-boundary-v2.sh`). Its "on" mode writes the shell/Service compose env, the recovery/shell tokens, the WAM API/Troubleshooter drop-ins and `app-manager.json browser_boundary: true` (read by WAM `5376b25`). The product has no supported switch yet.

## Results (run 2)

| # | Check | Result | Evidence |
|---|---|---|---|
| A | WAM #422 head contains `5376b25` | **PASS**: head is now `1c862d9` (child of `5376b25`) | `gh pr view 422` |
| C1 | **Upgrade** 0.3.102 → candidate (public `os.sh`, `WIZARD_RELEASE_BASE=file://`), flag off | **PASS**: `pinned`; `wizard doctor` and `wam doctor` show 0 FAIL; API 200, gateway active | runs5/04, 05 |
| C2 | Every default app, flag off | **PASS**: Notifications, ChatGPT, Claude, Files, App Store windows open; 0 page errors, except one 403 in the App Store (store-data) | tour r5-cand5-off |
| C3 | Flag on (rehearsal switch) | **PASS**: projection, app env, front and keys written; doctors clean | runs5/06 |
| C4 | Every default app, flag on, Nebula + Landscapes Light | **PASS with an open item**: Notifications (opaque, inbox), ChatGPT/Claude (Not connected, no accounts), Files own-tab card plus its own tab, and the Troubleshooter window. The agent-only apps were checked over MCP on the fresh box (C12). The App Store renders its UI, but its data is refused (open item O1). | screenshots r5-on-nebula-*, r5-on-landscapes-light-* |
| C5 | Model picker | **PARTIAL**: the picker opens and the shell made the `models.claude_accounts` typed read. The list is empty because the rig has no AI provider signed in, so model listing is unverified. | r5-on-model-picker.png, extra-r5-on.json |
| C6 | Chats bell (#8) | **PASS**: only `browser-shell/call` `notifications.count`/`.items`; unread 7 / 8 items; mark-read through `notifications.mark` gives unread 6, item read | extra-r5-on.json |
| C7 | Hermes dashboard owner sign-in on its own tab (synthetic rig password, never printed) | **PASS**: `:9120/login` 200, XFO DENY; after sign-in the dashboard loads ("hermes via basic"); `/api/status` 200 | r5-on-hermes-dashboard-signed-in.png |
| C8 | Troubleshooter with the Agent Service stopped | **PASS for diagnosis**: its own tab answers 200 and shows "2 problems". **One-tap fix skipped**: it needs an AI provider (Claude "Not available", ChatGPT "Not signed in", Tinfoil "Not available"), and the rig has none. The Service was restarted by hand. | svc-down-r5.json |
| C9 | Hostile suite (real Chromium, cross-site page, opaque frame, replay/revoke) | **45/45 refused or as expected** (harness scored 43/45, see note) after restarting Files | hostile-browser-r5-after-files-restart.json |
| C10 | Store install/update/uninstall **with grants** (#10) | **NOT EXERCISED for a contract app** (see #10 and O2). Index wizard-files 0.1.4: install PASS, grant refused `no_contract` (correct) | store-lifecycle-r5*.txt |
| C11 | **Rollback** candidate → 0.3.102 with the flag on | **PASS**: `pinned`, doctors clean. Owner-state manifest (21 hashed files: Hermes config/.env/SOUL, memories, skills, notifications inbox, media/Pages/Skins) is **identical** before and after. The front is skipped by exec-condition and stock Hermes owns the tailnet :9119. | runs5/07, 09, 10 |
| C12 | **Fresh install** of the candidate (new guest from the golden image, public `os.sh`) | **PASS**: `pinned` in ~8 min; doctors 0 FAIL. Flag on: doctor `Wizard shell answers` PASS; gateway `tools/list` 39 tools (browser, transcriber, voice, notifications, secret-drop, files, chatgpt, claude; router missing, see #13); front active on :9119 with Hermes on 127.0.0.2:19119; bell via shell ops; dashboard sign-in PASS; Grove windows render | runs5/12–16, extra-r5-fresh-on.json, r5-fresh-on-granted-troubleshooter.png |

Hostile note: two rows the harness marked FAIL are actually refusals. (1) A cross-site frame of `/troubleshoot/` got `403 {"error":"frame_refused"}`, refused by the server before any page byte (#30). (2) An exact replay of an inbox call on an open binding got `403 replay`. That is stricter than the harness expectation ("served"), not a leak. The harness frame check was also fixed: an empty `frame.url()` was being scored as a failure.

## Findings from run 1 and their state

| # | Finding | Fix (draft, with a test that fails on base) | Live on the rig |
|---|---|---|---|
| 5 | Rollback to 0.3.102 left the WAM front unit holding :9119 | WAM #422 `1c862d9`: front unit `PartOf=` the dashboard plus `ExecCondition=` "dashboard is the fronted one" (`tests/test_host_dashboard_front_rollback.py`, 3/3 fail on `5376b25`). Full WAM suite: 1843 passed. | **Fixed**: after rollback `Skipped due to 'exec-condition'`, `hermes` on 100.73.0.1:9119 |
| 6 | `wizard doctor` reported 401 under the boundary. It probes `/wizard/health`, not `/`: the shell's `proxy.conf` added `X-Forwarded-For`, which the Service's box-local health exemption refuses | UX #873: `location = /wizard/health` passes XFF only when the caller sent one (real nginx + echo upstream proof; `tests/nginx-box-local-health.test.mjs`) | **Fixed**: doctor PASS. Bare probe 200; with XFF, a foreign Origin, or via Tailscale Serve 401 |
| 7 | App Store window: ES modules refused by CORS from the Origin:null frame | UX #873: static `.js` only, only for `Origin: null`, gets anonymous `ACAO: *` + `Vary: Origin`. Never credentials, APIs, `.html` or token-bearing documents (real nginx proof; `tests/nginx-opaque-module-scripts.test.mjs`) | **Modules fixed**: the Store UI renders. Data reads are still refused (O1) |
| 8 | `notif-bell.js` fetched `/notifications/api/*` directly | Service #318 adds the shell-owned `notifications.count/.items/.mark` (reusing the typed notifications ops and receipts; 4 tests; full suite 1861 passed). UX #873 makes the bell use them when the boundary is on | **Fixed** (C6) |
| 9 | `/notifications/` and `/troubleshoot/` frameable cross-site | notifications #23: `frame-ancestors 'self'` + XFO SAMEORIGIN on pages. Troubleshooter #30: refuses non-same-origin iframe navigations with 403 before any byte, plus XFO SAMEORIGIN | **Fixed**: both refused cross-site, and both still render in the shell's opaque windows |
| 10 | Store grants need a contract-bearing wizard-files candidate | wizard-files #11 `5765f57`: the image did not build at all (`.dockerignore` missed 4 COPY sources; `tests/test_docker_context.py`). The compose **builds from source**, so there is no registry image to publish. Offered through WAM's own private test pin (`WAM_PRIVATE_CATALOG`) with a rehearsal wrapper that skips the GitHub login for a public repo | **Blocked by O2**: Runtipi cannot build it on this box |
| 12 | Landscapes Light: "opens in its own tab" was dark on dark | UX #873: desktop card uses `--wz-panel/--wz-text/--wz-accent` (`tests/desktop-frame-fallback-skin.test.mjs`) | **Fixed**: inspected r5-on-landscapes-light-files.png |
| 13 | Connection Router `tools/list` 400 | **Root cause, pre-existing on stock 0.3.102** (reproduced after rollback: `tools/list` → 400). In report-only mode the router (`server.py` `caller()`) needs `X-Wizard-App` or a matching `incoming` grant row. The gateway sends neither: `grants/agent-service.json` `outgoing` has no router key (WAM #421 mints keys only for apps whose compose takes `WIZARD_GATEWAY_KEY`), and the router's `/wizard/grants.json` has `incoming: []`. Not fixed: it needs a permission-model decision (WAM grant row for `host:agent-service` → router, or a router that accepts the gateway key) | open (O3) |

Findings #1–#4 and #11 were handled in run 1 (WAM `5c74615`, `5376b25`).

## New findings in run 2

- **O1 App Store data under the boundary.** In the opaque window the Store's `/wizard-os-home/store-data/*` reads (installed apps, index) are refused from Origin:null, so it shows "The App Index isn't reachable right now". This is correct: owner APIs must not get CORS. The Store needs typed shell operations or intents for read, install, update and remove. **Release blocker.** The Store window also stays dark on Landscapes Light because it cannot adopt the parent appearance from an opaque frame.
- **O2 Build-packaged apps from a private or test pin cannot install on an alongside box.** WAM's CLI-prepared recipe sets the build context to the host path `/root/runtipi/app-data/.wizard-source/…`, but the Runtipi container sees app-data at `/app-data`. `docker compose up` exits 1 in about 1 s ("Docker-compose exited with code 1"). The same compose builds fine from the host. This is pre-existing App Manager behavior, not browser-trust code. It blocks the Store-grant lifecycle on a contract app (C10).
- **O4 Own-tab env applied late.** After the boundary was switched on, Files ran **ungated** (cross-site frame rendered My files) until it was restarted. Its `WIZARD_BROWSER_BOUNDARY`/`WIZARD_OWN_HOSTS` are written into `app.env` by the `wam links` step *after* the app restarts, and nothing restarts it again. Fix needed in WAM (restart an app whose boundary env changed) or in the switch order. **Release blocker for the switch.**
- **O5 Fresh box: default Notifications has no browser grants.** With the boundary on, the opaque Notifications window says "Notifications need permission from the owner for this" until `wam browser-grants grant notifications --operation notifications.inbox --operation notifications.mark`. After that grant it renders. The upgrade box only worked because run 1 had granted these by hand. Enablement needs a decision on default grants for system apps.
- O3: see #13.

Rig notes: headscale cannot issue HTTPS certs, so both guests use run 1's test-only Serve stand-in (`standin/`, self-signed, a `tailscale serve` wrapper). On the fresh guest it was installed after the install, so the `/troubleshoot` and Store Serve routes registered at install time were missing. `/troubleshoot` was re-added by hand. This is a rig artifact, not a product finding.

## Suites (local, not CI)

- WAM `1c862d9`: 1843 passed, 9 skipped.
- Service `78063a4`: 153 files / 1861 tests passed.
- UX #873: 1940/1942. The two failures are pre-existing on #865: the `browser-adapter-state` module was not found in this checkout, and COMPONENTS.md is over 14000 B.
- Troubleshooter #30: 68/68.
- notifications #23: frame, cross-site and routes tests 12 passed.
- wizard-files #11: docker-context + shared-style 5 passed; real `docker build` passes.

## Not covered / unverified

Jan's APK/Mac and phone gestures. Model listing with real provider accounts. The Troubleshooter one-tap fix (needs an AI provider). Store grant lifecycle on a contract app (O2). Optional/private apps. Global enablement is out of scope.

## Draft PRs from this run

WAM #422 (pushed `1c862d9`) · Service #318 · UX #873 · notifications #23 · troubleshooter #30 · wizard-files #11 (pushed `5765f57`).
Integration branches kept for this report: `integration/browser-trust-release-rehearsal` in wizard-app-manager (`018d28e5`) and wizard-ux (`c1932e10`). The chatgpt-connection, claude-connection and wizard-voice-service rehearsal branches (localhost:5000 images) were deleted.

## Run 3 (final): candidates `0.3.103-bt389.6` / `.7`, flag on

Raw receipts: [browser-trust-389/raw/run3](browser-trust-389/raw/run3). Screenshots: [screenshots/run3](browser-trust-389/screenshots/run3) (inspected). Same rig as run 2: disposable KVM guests, loopback registry, Serve stand-in. Nothing was merged, released or published.

**Verdict: still not release-ready.** O1/O3/O4/O5 now pass on the rig. Two issues remain open: Store UI install/remove on a *fresh* box (R3-2) and the device lanes. Both are listed below.

| # | Check | Result | Evidence |
|---|---|---|---|
| R1 | Upgrade 0.3.102 → `.6`, flag on: O5 release-default grants (Notifications, ChatGPT, Claude) | **PASS**: all three `by: release-default`, admissible; doctors 0 FAIL | run3/06-on.txt |
| R2 | O4 on `.6`: Files gated right after `on` | **FAIL on `.6`**: Files env empty after `on`. Fixed in `.7` (WAM #425) | run3/06-on.txt |
| R3 | O4 on `.6` second `on` / `.7` upgrade | **PASS**: Files `WIZARD_BROWSER_BOUNDARY=1`, `WIZARD_OWN_HOSTS=wtrain.train.test:8794`; doctors 0 FAIL | run3/08-on-again.txt, on3-checks-cand7.txt |
| R4 | O3 Connection Router through the gateway (router #10) | **PASS**: 40 tools incl. `wizard_connection_router__connection_needs`; direct `tools/list` 200 | same |
| R5 | O1 Store under the boundary (UX #874, real Chromium, upgraded box) | **PASS 7/7**: opaque frame; index data shown; every store-data request made by the shell document; frame-direct store-data 403; unknown op refused | out/run6-r6-upg7-views.json |
| R6 | Store lifecycle with grants on wizard-files, upgraded box (Store UI Get/Remove + CLI grants) | **PASS** for UI Remove, grant/deny/revoke/re-grant, reinstall gets a new installation id and no inherited grant (`no_grant`). UI Get of the *index* commit failed: `needs FILES_ALLOWED_HOSTS` (R3-1) | run3/11-grants.txt, 13, 14 |
| R7 | Rollback `.7` → 0.3.102, flag on, Wizard Files installed | **FAIL**: strict `wam doctor` `slot 'files' has 2 apps (files, wizard-files)` (R3-3) | run3/15, 16 |
| R8 | Rollback rerun after removing Wizard Files | **PASS**: `pinned` in 124 s, doctors 0 FAIL. Owner state **identical** (config.yaml/.env/SOUL.md, memories, skills, media, browser-grants.json hashes; Hermes version). Files back to the ungated 0.3.102 recipe | run3/18–21, snap-*-rollback2.json |
| R9 | **Fresh** install of `.7` (new guest, public `os.sh`), then flag on | **PASS**: `pinned` in 520 s, doctors 0 FAIL; O5 grants present without any manual grant | run3/25, 29, 31 |
| R10 | O5 fresh: Notifications renders with no manual grant (real Chromium) | **PASS**: "Inbox 2 … Rehearsal 1/2" after seeding 2 synthetic notifications. The unseeded run showed an empty inbox, no permission prompt | run3/36, r7-fresh-notifications.png |
| R11 | O4 fresh: Files gated immediately | **PASS once Serve works**: `wam links` wrote the own-tab env and restarted Files *before returning* (StartedAt 00:04:18, return 00:04:21). The first `on` left Files ungated (`/api/files` 200 with a foreign Origin) because the rig's tailscale wrapper answered `serve status --json` with the cert stub. That is a rig artifact (wrapper order), fixed by hand | run3/30, 33, 34 |
| R12 | O1 fresh Store window | **PASS** (same 6 O1 checks) | run6-r7-fresh-views.json |
| R13 | Wizard Files install with **no owner setting** (#12, via the integration commit `7df0ec5` = #11 + #12, stock WAM test pin, no `--set`) | **PASS**: installed; WAM wrote `WIZARD_TRUSTED_HOSTS=wtrain.train.test:8796,wtrain.train.test`; `FILES_ALLOWED_HOSTS` empty; boundary on at first start (`/api/files` 401 without credential, `/health` 200) | run3/38 |
| R14 | Grants on the fresh box (contract app) | **PASS**: grant `files.list` admissible; undeclared op refused; revoke → `no_grant`; re-grant `files.index`+`files.list` | run3/40 |
| R15 | Doctor with Files + Wizard Files on the candidate | **FAIL as expected** (`slot collision`). With WAM #427 patched in: **0 FAIL**, row `PASS slot 'files': active app is chosen files (also installed: wizard-files)`. Reverted after | run3/38, 39 |
| R16 | Store **UI** Get / Remove on the fresh box | **Closed in run 4 (rig artifact, not a product bug)**. Run 3 text: after the owner clicks the shell's Install/Remove, the shell document closes its own tab (Playwright `page close`, no crash, no popup). No request reached the WAM store listener. Get also logged one `POST /wizard-files 403` earlier in the run. The same runner passed Remove on the upgraded box. Not diagnosed | run3/37, 41, 42 |

### Findings and fixes in run 3

- **R3-1 Store can't install Wizard Files** (`needs FILES_ALLOWED_HOSTS`: a required form field the Store can't fill). Fix: **wizard-files #12** (ordinary PR off main). The listener also trusts `WIZARD_TRUSTED_HOSTS`, which WAM already writes for recipes that declare it, so `FILES_ALLOWED_HOSTS` becomes optional. 2 new tests fail on main. Suite 36/37 (the known provenance ctime flake). Verified live in R13. #11 must take 0.1.6 when it rebases.
- **R3-3 Alternative slot provider failed strict doctor.** WAM's slot model supports several providers with a saved active choice: install the alternative before removing the default, as `blocks_uninstall`/Store Remove expect, and `slots.<s>.default` is kept across rewrites. Only doctor called it a FAIL. Fix: **WAM #427** (off main). Doctor reports the active choice and FAILs only if the saved choice names no installed app. 4 new tests fail on main; full suite 1833 passed. A rollback *to* 0.3.102 still runs 0.3.102's doctor, so on such a box Wizard Files must be removed before rolling back.
- **R3-2 Store UI confirm closes the shell tab on a fresh box** (R16). Open, needs a UX look (wizard-ux #874 / intents).

### Release blockers remaining

1. ~~R16 Store UI install/remove on a fresh box~~: closed in run 4, rig artifact (see Run 4).
2. Jan's native review: **wizard-ux #871** (native main-document receivers, draft, REVIEW_REQUIRED) and **try-wizard #61** (Mac), both still open drafts. Device lanes (APK/Mac, phone gestures) are not covered by this rig.
3. Merge-order dependencies for a real release: WAM #424 (non-draft), #425 (O4/O5), #422; router #10; UX #874 on #873; wizard-files #11 rebased on main (0.1.6); spec wizard-os #403. Already on main (merged by defleur-agents during this run, not by Oscar): WAM #427 (slot doctor) and wizard-files #13, which supersedes #12 (box-host admission, optional setting).
4. Still unverified: the Store UI *update* of a contract app. Update ran through the CLI test pin in run 2/3, because the Store has no UI path to a test pin. Also unverified: model listing with real provider accounts and the Troubleshooter one-tap fix.

Integration branches cited by this report and kept: `integration/browser-trust-release-rehearsal` in wizard-app-manager, wizard-ux and **wizard-files (`7df0ec5`)**. Rig torn down after this run (VMs, disks, registry, tunnels).

## Run 4: R16 Store window on a fresh box (diagnosed, not a product bug)

Raw receipts: [browser-trust-389/raw/run4](browser-trust-389/raw/run4). Screenshots: [screenshots/run4](browser-trust-389/screenshots/run4) (inspected). Same candidate `0.3.103-bt389.7`, flag on. Two new disposable guests: a **fresh** public `os.sh` install of `.7`, then an **upgraded** box (0.3.102 → `.7`). Real Chromium (Playwright) through the rig's two browser paths. Nothing was merged, released or published.

**Root cause of R16: two rig artifacts. Neither is a product bug.**

1. **"Nothing reaches WAM" / the 403.** On the fresh box, run 3 drove the browser only through `bt389-socks`. That is `ssh -D` *into the guest*, so every request reaches Tailscale Serve from the box's own tailnet address. WAM's Store listener refuses owner changes from the box itself (`store_install.check_request` → `from_box`, on main; it exists because every app container also reaches Serve as the owner). The refusal is `403 {"error": "changes are refused from this Wizard itself: its apps reach Tailscale Serve with your identity too. Use your phone or computer, or `wam` on the server"}`. The WAM journal logs only `"POST /wizard-files HTTP/1.1" 403 -` without the reason, so run 3 read it as "nothing reached WAM". Run 3's passing upgraded-box Remove used the second path, `bt389-device-tunnel` (a SOCKS proxy in a container on the guest's Docker bridge, i.e. "another device"). Run 3's upgraded-box Get through `ssh -D` failed in the same way.
2. **"The tab closes itself."** After a refusal the runner kept polling for "Installed" until the shell `timeout` (280/420 s) killed node. Playwright then closes the browser gracefully, which logs `page close`. Proof in run 4: `pw:browser <gracefully close start>` at exactly the timeout, after the 403 ([10-get-1081.log](browser-trust-389/raw/run4/10-get-1081.log)). There is no `window.close()` anywhere in the shell; an init-script hook on `window.close`, `pagehide` and `beforeunload` never fired. The shell stays open and shows the refusal in the Store's own sheet ([screenshot](browser-trust-389/screenshots/run4/r8-fresh-1081-store-remove.png)), or a toast "Wizard Files wasn't installed" for Get.

| # | Check (Store window, owner confirms in the shell dialog) | Fresh box | Upgraded box (0.3.102 → `.7`) | Evidence |
|---|---|---|---|---|
| R4-1 | Get from the box itself (`ssh -D` path) | **refused 403 `from_box`** (correct); shell intact, reason shown | same | 10, 12, 30, 18/36 journal |
| R4-2 | Store Get, index release `wizard-files` 0.1.5 @ `1b30909` (main, incl. #13), "other device" path | **PASS**: 202, container healthy, row shows Open | **PASS** | 11, 31 |
| R4-3 | Store Remove (Store sheet → shell Review → Remove) | **PASS** (one earlier attempt saw the Store list still loading at 12 s; retry passed) | **PASS** | 13b, 32 |
| R4-4 | Install by **link** at `1b30909` (Store's install-link sheet, `source: link`) | **PASS** | **PASS** (stock WAM, no rig stub) | 15, 33 |
| R4-5 | Release change by link to **wizard-files #11 rebased head `5aceb5d` (0.1.6, browser contract)** | **PASS** as **"Switch to this release"** → 0.1.6, `WIZARD_BROWSER_BOUNDARY=1`, credential set, `WIZARD_TRUSTED_HOSTS` written; `/api/files` 403 with a browser Origin, 401 without credential, `/health` 200; contract ops listed, `no_grant` until granted | **PASS** (same switch) | 16, 34, snap in 16 |
| R4-6 | Store Remove of the 0.1.6 contract app | **PASS** (container gone, recipe dir gone) | **PASS** | 17, 35 |
| R4-7 | Every Store owner change sent by the shell document, none by the frame; nothing POSTed before the owner confirms | **PASS** in every run | **PASS** | all |

Notes:
- The Store's **Update** button is not reachable on the rig. It appears only when the *same* source and channel offer a newer version. The public index has one wizard-files release, and link installs carry no channel, so a newer link is offered as "Switch to this release" (operation `switch`). The release change itself (0.1.5 → 0.1.6 through the Store window, owner-confirmed) is proven. The literal "Update" label needs a newer public index release. WAM's test pin (`WAM_PRIVATE_CATALOG`) is not shown in the Store UI.
- `wam doctor` on the fresh box with Files + Wizard Files: 1 FAIL `slot collision`. That is expected on `.7`, which predates WAM #427 (merged on main).
- The Store-listener journal has no refusal reason. Logging `why` next to the 403 would have made R16 a one-line diagnosis. This is a suggestion only; no PR was opened.
- Rig fixes: the Serve stand-in installer now puts the `serve` passthrough right after `REAL=` (run 3's wrapper-order artifact). The fresh-box SOCKS IP is read from `.NetworkSettings.Networks`.

**wizard-files #11** was rebased on main (after merged #13) and became **0.1.6** (`5aceb5d`: recipe/server/manifest/assets/test version). Conflicts in `runtipi/config.json` and `server.py` were resolved by keeping main's optional `FILES_ALLOWED_HOSTS` and box-host admission, plus #11's boundary gate and kit assets. Local suite: 48 tests, 1 failure, `test_provenance…invalidate_cache`, the known ctime-tick flake that also fails on main (39 tests, same single failure). Live: the image builds and installs through the Store link path on both boxes (R4-5).

**Verdict after run 4:** the Store-window blocker (R16) is closed. No server-side release blocker remains on this rig. Still open, as before: Jan's native review (wizard-ux #871, try-wizard #61) and the device lanes. Merge order: WAM #425/#422 (#424 landed as #426), router #10, UX #874 on #873, wizard-files #11 (now on main, 0.1.6), spec #403. Rig torn down (both guests, disks, registry container, tunnels).
