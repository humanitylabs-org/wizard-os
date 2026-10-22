# Browser owner boundary — Audit 2 candidate

Tracking: [wizard-os#133](https://github.com/humanitylabs-org/wizard-os/issues/133).

**Status: default-OFF draft. NOT ready to enable on an owner box.** Backend enforcement and a real browser candidate exist; this document does not close the launch blocker. No owner deployment or merge is authorized by this evidence.

## Threat and adopted boundary

Network ownership (Tailscale identity, front-proxy owner proof or box-local access) does not distinguish shell JavaScript from an app XSS. Require **both** the existing access/principal proof and a browser possession proof on owner API reads and writes. Keep machine credentials and restricted-agent scope separate.

Feature flag: `WIZARD_BROWSER_BOUNDARY=1`. Off/unset keeps the legacy authorization path and emits no bootstrap. With it on, UX, Agent Service and WAM receive the same `WIZARD_SHELL_TOKEN_FILE`: 32 random bytes as 64 lowercase hex characters, optional final LF. Missing/invalid secret fails startup. Do not put the token in compose environment values, query strings, localStorage, app containers, logs or generated JS assets.

- **Bootstrap:** only exact shell entry documents (`/wizard-os-home/`, `/wizard-os-home/index.html`, `/wizard-os-home/desktop.html`, and the equivalent `/wizard-ux/` paths) contain the token. A request must be a main-document navigation (`Sec-Fetch-Dest: document`, `Sec-Fetch-Mode: navigate`). Fetch, scripts, workers and iframes cannot set those forbidden headers from browser JavaScript. Non-browser clients can forge them; the network owner proof is still required. The shell consumes and removes the meta element before loading other scripts. This protects against app XSS, not shell XSS or a malicious browser extension.
- **Document isolation:** `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `Cache-Control: private, no-store`. `Cross-Origin-Opener-Policy: noopener-allow-popups` additionally breaks an app's same-origin popup handle to a newly opened shell. That header needs real support on every admitted browser/WebView; a Chromium pass is not Safari/native proof. All other app origins/routes must be assessed, including standalone/top-level paths. There is no blanket top-level-app storage isolation on a shared origin.
- **Owner calls:** shell `fetch` attaches `X-Wizard-Shell-Token` only to explicitly enumerated same-origin owner paths and sets `redirect: error`, including same-origin redirects into an app. It is not a general app fetch proxy. Agent Service checks before route dispatch on both listeners. WAM checks before Store peer/owner checks, body parsing and installer entry, including `_recommended` POST, `_updates`, slots and view routes. The machine WAM bearer API remains bearer-protected, not network-owner protected.
- **Machine calls:** service and agent principals retain their existing credentials/scopes, but flag-on boundary rejects them if browser Origin/Fetch Metadata is present. Credentials are not minted by the browser bridge. The Service internal token is random, in-process and not a browser/bootstrap value. Restricted-agent socket admission remains unchanged.
- **Frames:** mobile app windows, desktop app windows and link panes use sandbox `allow-scripts allow-forms allow-downloads`; **no** same-origin, popup or top-navigation exception. An incompatible app is not a reason to weaken this boundary.
- **Bridge:** narrow postMessage Back, Appearance v1 and sealed field insertion. Exact opaque source WindowProxy plus per-load channel; pending calls revoked on load/detach, bounded waiters and explicit acknowledgements. Timeout stays put rather than making a late app Back become two steps. No fetch, install, native call, arbitrary URL or owner credential RPC. Current field seals support ordinary text inputs/textareas; contenteditable, recorder wiring and cross-document navigation-start hardening remain enable gates.

## Implementation and evidence

Named branch in each implementation repository: `fix/browser-owner-boundary`. See sibling draft PRs linked from #133 for exact revisions. Tests run directly on the dedicated QA host, not on the owner box.

- Agent Service: `npx vitest run tests/browser-boundary.test.ts tests/agent-principals.test.ts` covers configuration, legacy off path, owner reads/mutations across both ingress paths, wrong/missing tokens, null Origin and existing private-agent isolation.
- WAM: `python -m pytest -q tests/test_browser_boundary.py tests/test_recommended.py tests/test_store_install.py` exercises the real StoreHandler, `_recommended` installer entry (synthetic stub, not a real installation), all new gates, owner/peer checks and flag-off behavior.
- UX: `npm test` includes boundary unit tests for credential scope, Request body preservation, redirect refusal, wrong source/channel, timeout, pin revocation and theme acknowledgement.
- `tests/qa-browser-boundary.cjs` runs real nginx + current UX shell + Agent Service + its synthetic Hermes fixture in Chromium, without owner API route mocks. It checks hostile app DOM/storage/chat/bootstrap access, mutation refusal, shell owner fetch, nested Back, acknowledged field insertion, stale field rejection and two live skins. Screenshot review caught and fixed the light-skin black-frame defect: only acknowledge `wz-themed` after the opaque client applied the current revision.
- The browser test records `nativeProven: false` and `realStoreInstallProven: false`. Its `nativeAbsent` assertion means no native API is present in Chromium; **it proves nothing about Android/Mac bridge isolation**. STT/recorder hardware was not exercised by the text insertion test.
- An optional `QA_COOP_NEGATIVE_CONTROL=1` removes only the opener header in the test configuration and must reproduce the same-origin app popup access. Keep that evidence separate from the protected run.

Evidence paths and final counts are posted on #133 rather than asserted before execution here.

## Launch app origin inventory

See [BROWSER_BOUNDARY_ORIGINS.json](BROWSER_BOUNDARY_ORIGINS.json). Scope is the current **13 WAM default slots**, plus built-in Store/Setup/Settings and the explicitly discussed Wisdom/Calendar apps. Source commits are pinned. This is source inspection, **not a live installed-app census or opaque-origin compatibility certification**. Unknown installed apps must stay unadmitted until inventoried and runtime-tested. No app is approved for `allow-same-origin` on the shared shell origin.

## Independent review disposition

Claude was invoked with the Fable route for one design round and one code-review round. The first bounded code-review invocation timed out; its successful retry has a nonempty result, `is_error: false` and no permission denials. Its receipt reports Fable thinking and Opus output usage, so it is not evidence of sole-model Fable authorship. Raw receipts are retained with the QA evidence.

The reviewer approved only a default-off draft and rejected enable. The concrete same-origin opener concern was reproduced with a negative control and addressed in supported Chromium by `noopener-allow-popups`; broader client support remains gated. Machine-principal exemptions now reject browser metadata. A static-proxy test verifies navigation metadata and COOP/CSP preservation while owner tokens, proof, cookies and tailnet identity are not forwarded. The review's suggestion that WAM has service/agent principal exemptions is not applicable: WAM has its own token gate, peer and owner checks. Nor can a top-level app simply inherit the shell's closure; the actual same-origin popup-reference attack is the one tested. Do not treat reviewer assertions as substitute source evidence.

## Enable gates — all still binding

1. **Native interfaces:** Android `MainActivity` exposes `WizardOSNative` and `WizardOSDevice` with `addJavascriptInterface`, which reaches every frame regardless of the sandbox. Replace with main-frame-scoped message ports and prove an actual APK. Audit `MizelBridge` and Mac frame handling too. A sandbox or browser `nativeAbsent` result does not fix this.
2. **Owner-login app listeners:** Cloudflare derives owner authority from `WIZARD_OWNER_LOGINS` and tailnet headers on a separate listener. The current Agent Service/WAM gate does not automatically protect it. Add a server-side shell-possession/scoped-session boundary there and test null-origin and same-origin hostile callers before admission. Do not broaden `null` origins globally or simply remove its origin checks.
3. **App-local APIs and storage:** ChatGPT/Claude, Cloudflare, Connectors, Wisdom, Calendar and Secret Drop reject opaque-origin writes. Other embedded server/upstream apps have no compatibility proof. Implement per-app, narrowly scoped adapters or separate origins. App internal connection POST work remains in its existing default-off lane; this branch does not modify those repositories or their parallel PRs.
4. **Store and Setup flows:** real UI install/release/slot actions and `_recommended` must move to shell-owned, explicitly approved operations (or an equivalently scoped bridge), not a generic authenticated fetch relay. Current opaque Store/Setup frames cannot perform their old direct calls. A mocked installer unit test is not acceptance.
5. **Voice:** wire asynchronous pin/insert acknowledgements through the real microphone/STT/retained-audio path; preserve contenteditable support and reject navigation/changed targets without losing the take. The bridge primitive alone is insufficient.
6. **Ingress/clients:** exercise packaged nginx entrypoint, Tailscale-to-Service static proxy, bundled local shell path, browser Back key from inside a focused app, mobile geometry and all admitted client engines, including opener isolation support. The current desktop shell Back event proof is not a physical Android Back proof. Headerless EventSource, media/download URLs and native transports need scoped alternatives; never put the owner token in a URL.
7. **Shell extensions:** in-document installed Chats modules run in the shell JS realm and are privileged shell code, not sandboxed app pages. Review their admission separately; do not describe an iframe sandbox as isolating in-document modules. Do not disturb the parallel WAM/connection admission lane.
8. **Flag-off and owner gate:** all companion CI green, full source/behavior equivalence checks and a current installed-app census. Only then stage an owner enable; this lane may not deploy it. Merge only under the standing owner-live-clean rule or a separately confirmed safe default-off merge decision.

## Staged deployment and rollback (not authorization)

**Now:** keep `WIZARD_BROWSER_BOUNDARY` unset/`0`. Build immutable companion images from the pushed draft revisions on the build host; pin those exact digests in an isolated preview. Do not use floating `main`/`latest` for this candidate. The current drafts are not an enable-ready bundle.

**After every gate above is satisfied:**

1. Capture the running image digests, WAM revision, effective compose files, Serve mappings and current installed registry into an encrypted rollback receipt. Do not collect secrets into evidence.
2. Generate a dedicated secret file with `umask 077; openssl rand -hex 32 > "$WIZARD_SHELL_TOKEN_FILE"`. Bind it read-only to UX/Agent Service and configure the WAM service with the same file; never mount it into app containers. Ensure the backend and UX flags cannot be enabled independently through an owner-facing toggle.
3. Stage immutable UX/Service/WAM candidates with flag `0`. Verify both shell entrypoints and health/read/mutation behavior before any enable. Use an isolated synthetic account/fixture for mutation probes.
4. In a maintenance window, enable matching services together; use the UX navigation bootstrap, not API token injection by a network proxy. Preserve the original access verifier. Re-run hostile fixture, real Store/Setup, nested Back, chats, voice and native denial on the actual owner install before declaring live clean.
5. If any check fails: stop flagged listeners, restore the recorded image digests/WAM revision and Serve mappings, set flag `0` everywhere, restart, reload both shell clients and verify normal chats/Back/Store/voice. Remove the preview token mount only after rollback is read back. **This rollback reopens the known pre-existing app trust hole; it is compatibility recovery, not a security fix.** Do not claim a partial UX/server flag rollback is safe.

No owner-only design decision is needed to excuse these gaps. They are engineering and evidence work, not a request for James to accept an insecure `allow-same-origin` shortcut.
