# Browser-isolation release rehearsal: wizard-os #389 (card 6), run 2

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
