# Browser-trust app census and enablement plan

**Decision:** isolate every installed app document; keep owner authority in the shell. This is not a Notes/notebook fix. **Current verdict: do not enable globally yet.** The inherited r5 hostile-page browser receipt proves the synthetic boundary, not compatibility of the packages below. This census performs static public-source/package inspection only; no APK, Mac app, real app backend, live checkout, installed box or owner data was used.

## Scope and provenance

- Snapshot: GitHub `main` SHAs and public published app/package pins fetched for this task. Exact provenance is in `census-source/source-manifest-final.json`; no moving-branch URL is used as an immutable evidence pin.
- There is no `humanitylabs-org/wizard-apps` repository (GitHub returned 404). The actual discovery catalogue is **wizard-app-index**, backed by public app repositories, plus **wizard-app-store** recipe sources, **wizard-app-manager/wam/defaults.json**, and the **wizard-os** release manifests. The wizard-os catalogue/release metadata was explicitly in scope; private app sources were not fetched.
- The live public index returned **48 listings / 47 distinct app IDs**. Both `oscarhenrycollins/profiles` and `humanitylabs-org/profiles` publish `profiles`; these are NOT interchangeable principals. Every listing is mapped below, including Oscar's public provider packages rather than just the org's forks.
- The three additions to that ID set are **Photos** (public first-party source outside index), **Voice service** (default service), and **Troubleshooter** (installed host component / shell launcher alias `troubleshooter`). Result: **50 unique active app/component rows**. Shell-owned system views and retired/reserved recipes are inventoried separately; they are not silently counted as additional installed app packages.
- `releases/latest` = **0.3.101**; `releases/stable` = **0.3.94**. Latest declares **12 non-null default apps**, plus the independently installed Troubleshooter component. All appear below. Stable changes shell and Agent Service pins only within this set; those source snapshots were also scanned. WAM host-component and actual image-source commits were fetched separately because they differ. Latest/stable are repository channel declarations, not an assertion about James's running box.
- Public repos without `main`: **wizard-connectors, wizard-google, wizard-messenger, wizard-music, wizard-search**. Their immutable published catalogue commits were inspected instead. This limitation is explicit, not a guessed `origin/main` result.
- Source corpus: public GitHub archives only, selected text files, no app source executed. Root manifests, shipped YAML/JSON inline frontend code, runtime JS/TS/HTML/Python, and Android Java were scanned for owner routes, network calls, parent/frame access, storage, content/download/form URLs, backend Origin policy and native bridges. Tests/docs/vendor/build output were excluded from *runtime hit classification*, not treated as app behavior. `Path(...).parent`, mounted `/wizard/grants.json` files and backend-to-Service calls are not browser parent/owner-API findings.
- **Hard coverage limits:** wrapper-only recipes do not themselves expose all served frontend bytes. I followed their public source links: **File Browser v2.63.23** at `e8a388f840173580116f2743813d03b22286e44e`, **Hermes Frontend 3** renderer `przbadu/hermes-ui@1af684e2d6ce05e6d1da82d67bc671e15d2d2d96` recovered from app-store `scripts/prepare-frontend.sh`, and the **Hermes dashboard** upstream release v2026.9.24 at `f97608f178d1ffeca59860195ab7da295f7c8e5f`. Those sources were inspected and concrete failures are in the table; the org's separate Tinfoil engine source was also included. This still does **not** attest actual served image bytes/local patches/proxy configuration or prove runtime compatibility. Sign-in/recipient engines have the same image-vs-source acceptance requirement. The scanner excludes binary assets, files over 2.5 MB, vendored/build/content trees; no regex result is equivalent to a runtime PASS.

## Reading the table

`D` = proposed typed **app-data operation** adapter; `S` = proposed **per-installation async state** adapter; `M` = proposed **scoped content/upload/download** adapter; `T` = proposed bounded **stream/socket** adapter; `V` = extension of existing **capture/background/native** owner components; `U` = extension of shared **view/update/titlebar/badge** services; `N` = narrow **navigation/auth intent** adapter. These are design labels, not existing API names.

Already in #327: **B** Back, **A** Appearance v1, field pin/insertion, confirmed `share.wizard`, bounded `voice.transcribe`. Their opaque-frame handshake is opt-in: apps need `browser-boundary-client.js` before `app-client.js`. Ordinary `WizardApp.*` or old `wizard:appearance:*` messaging does **not** establish opaque compatibility. #327's opaque app-service request allowlist is only ready/share/transcribe; capture, vault, titlebar, view, update and navigation cannot be assumed to work.

Sizing means **active engineering work, not queue/calendar time**: **S 0.5–2 h**, **M 2–5 h**, **L 6–14 h** of app-specific integration/validation after shared adapters exist. L also flags unresolved security/image integration, so its upper bound is a planning allowance, not a guarantee. `wizard-ux` and `wizard-agent-service` are platform rows; their work is budgeted in shared work packages, not added again as app migrations. Service-only S means no iframe migration, not that all listener security is already proven.

### Every active public app/package

**Counts: 50 app/component IDs — S 5, M 25, L 20.** All 48 catalogue listings map to the 47 catalogue IDs; the 3 explicitly described additions complete this scope.

| App (D = release default; H = installed host component) | What it needs / observed break | Replacement | Missing / release gate | Effort |
|---|---|---|---|---|---|
| [browser](#evidence-browser) **D** | Headless Chrome/MCP service; no declared app view. No app-frame owner call found. | No new frame adapter; REUSE service grants. | Keep DevTools and MCP box-only; do not turn the Chrome listener into an owner-browser bypass. | **S** |
| [connected-accounts](#evidence-connected-accounts) | Own same-origin credentialed fetch and Origin guard; account-link UI; shared Back. | D connector-status/link operations + B/A + N auth flow. | No main branch: reviewed catalogue pin only. Preserve deliberate Google sign-in-disabled policy; add cookie/session broker if selected backend requires it. | **M** |
| [contacts](#evidence-contacts) | Own contact reads/saves, avatar URLs/import/export; Origin gate on writes; shared Back. | D contacts ops + M avatars/export + B/A. | Scope cross-app access (Messenger currently fetches Contacts directly); upload/download and confirmation tests. | **M** |
| [defleur-video](#evidence-defleur-video) | No declared launcher view. Service embeds optional /v1/projects file-upload helper; output files flow through Files. | REUSE backend grants; M only for helper if framed later. | No automatic migration of a nonexistent app frame. Keep upload helper authenticated/scoped; playback/download parity belongs to Files path. | **S** |
| [files](#evidence-files) **D** | Default File Browser v2.63.23 upstream uses document.cookie + localStorage JWT, fetch API, XHR uploads, raw/media/download URLs and WebSocket commands. Packaged server uses noauth behind private exposure. | Dedicated non-owner app origin OR D file ops + M upload/download + S non-secret UI state + T reviewed live functions. | Cookie/storage boot breaks in opaque frame; JWT must not become global owner authority. Exact upstream source audited; served-image/proxy noauth boundary and full UI parity still need runtime proof. | **L** |
| [hermes-agent](#evidence-hermes-agent) **D** | Declared dashboard on 9119; pinned v2026.9.24 source has unguarded localStorage chat-panel state, sessionStorage PTY/plugin state, dashboard fetch/auth and WebSocket chat/console. Alongside uses host Hermes. | Non-owner dashboard principal with its own auth, or reviewed D/T/S adapters; never owner/run proxy for arbitrary frames. | Pinned upstream inspected; exact Wizard image and local patches/served bundle still require parity. Preserve dashboard-owner vs app/agent/MCP distinction; opaque boot/storage and websocket auth need changes. | **L** |
| [hermes-frontend-3](#evidence-hermes-frontend-3) | Recipe resolves exact upstream przbadu/hermes-ui 1af684e2: localStorage drafts/cache/gateway token, document.cookie gateway selection, fetch dashboard auth and JSON-RPC WebSocket. | Non-owner app origin and narrow agent-specific D/T/S/M, not shell owner authority. | Upstream source pin recovered from wizard-app-store prepare-frontend.sh; rendered image/bundle still needs proof. Remove token-in-storage assumption for opaque mode; don't promote alternative agent UI to trusted shell. | **L** |
| [messenger](#evidence-messenger) | Own cookie+CSRF owner sessions; many local/sessionStorage drafts/cache; authenticated media fetch/upload; direct Contacts calls; capture/share/vault/titlebar/update SDK surface. | D reviewed Messenger ops + S drafts + M media/upload + B/A + EXTEND U/V/N. | Owner-only policy writes reject machine bearers: generic MCP forwarding is invalid. Biometric vault, upload resume, send confirmation/idempotency and nested media parity required. | **L** |
| [money](#evidence-money) | Own finance API/Origin guard; localStorage cache, filters and recent categories; appearance messaging. | D Money ops + S cache/preferences + B/A. | Private financial cache lifecycle; preserve source-qualified provider grants and user-visible edits/readback. | **M** |
| [morning-report](#evidence-morning-report) | Own edition/status API; localStorage last-seen marker; badge/titlebar shared APIs not admitted by opaque service allowlist. | D report reads + S seen marker + B/A + EXTEND U badge/titlebar. | Preserve unread counts and held reading state; no full-owner notebook/history export. | **M** |
| [movies](#evidence-movies) | Own queue API/Origin guard; unguarded startup localStorage cinequeue.view; posters/media URLs; backend creates Chats runs. | D Movies ops + S preference + M scoped assets + B/A/N. | Thread opening uses narrow nav; keep backend app-to-agent permission separate. Startup storage exception can stop whole view. | **M** |
| [notifications](#evidence-notifications) **D** | Own inline/minimal api/ fetches, read/archive/reply; parent.document shell detection; frameElement and origin-bound count postMessage; media thumbs. | D Notifications ops + B/A + M thumbs + EXTEND U count/badge + N unsent reply draft. | Read both live inline compose and web/minimal sources; /notifications path and default pin differ from current main. Click once returns to list. | **M** |
| [outline](#evidence-outline) | Own HTTP document/audio APIs + WebSocket api/live; indexedDB document/speech recovery plus separate retained-original capture; trusted Host/Origin. | D document ops + T bounded realtime port + S recovery ledger + M original takes + B/A/V/U. | Realtime socket cannot set shell header. Preserve immutable chunk hashes, crash recovery and separate original-audio custody; not just voice.transcribe. | **L** |
| [photos](#evidence-photos) | Pure frontend for shell Photos relay; postMessage location.origin, shell source/origin checks; native backup settings, albums, connect/disconnect. | EXTEND existing photos-relay to current opaque channel; B/A; retain narrow native method set. | No generic native passthrough. Status/album privacy and biometric/key custody; desktop unsupported remains explicit. | **M** |
| [profiles](#evidence-profiles) | Both published repos read release/install snapshot and /wizard/v1/my-skin; PUT/DELETE CSS there; writes shared wos.skin storage; own profile API. | D profile-local ops + S local prefs; shell-owned appearance export/apply/reset intent with explicit confirmation. | No general data.call permission to owner skin endpoints. Two different published sources share id=profiles: source-qualified identity mandatory. | **L** |
| [secret-drop](#evidence-secret-drop) **D** | No declared launcher view, but engine serves secret-recipient page with window.fetch; same-Origin-only submission and COOP/CORP guards. | Keep recipient page on isolated non-owner origin with one-use drop capability; dedicated D if shell embeds it. | Do not route secret contents via a generic owner broker or break one-time links. Framing, secure-context crypto and actual image assets not runtime-proven. | **M** |
| [smart-home](#evidence-smart-home) | Packaged inline Python/YAML frontend calls api/ controls; Home Assistant backend access through wrapper. | D declared smart-home actions + B/A. | Review device-control scope and acknowledgements; don't bypass existing Home Assistant authority or confuse inline package code with absent UI. | **M** |
| [transcriber](#evidence-transcriber) **D** | Service/MCP package only, no view. No app-frame owner calls found. | REUSE bounded voice.transcribe from #327; existing service grants. | Keep upstream provider secrets private; audit service listener independently if exposed, not a new frame API. | **S** |
| [troubleshooter](#evidence-troubleshooter) **H** | Installed host recovery view (not index app); /troubleshoot/api calls and direct /wizard/v1/provider-recovery; localStorage engine cache; parent.WizOpenApp. | Dedicated recovery-scoped D + S cache + N source-bound navigation + B/A. | Independent listener must remain usable if Agent Service fails; give it a distinct shell/recovery gate, not blanket owner-token exemption. | **L** |
| [wisdom](#evidence-wisdom) | Own library/discussion APIs and streamed lookup; local/sessionStorage reading/drafts; zip upload/export; parent.WizardOSNative.haptic call. | D Wisdom ops + S place/drafts + M bundles/images + T lookup + B/A + V bounded haptic. | Remove direct parent native access; preserve discussions, import/export, stream cancellation, update holds and private/shared library separation. | **L** |
| [wizard-agent-service](#evidence-wizard-agent-service) **D** | Trusted platform backend, not a normal frame: owner HTTP reads/writes + headerless streams/media routes. Backend /wizard hits are intentional. | REUSE #100 gate; EXTEND narrow brokers/stream-ticket handling and separate principals. | Must not forward shell header to app upstreams, put it in URLs or use owner token for agent/peer requests; package alongside and fresh gates. | **L** |
| [wizard-apple-health](#evidence-wizard-apple-health) | Own API reads/import setup; backend rejects unknown Origin; local Back and themed settings. | D app-data operations + existing B/A. | Review import/status operation allowlist; preserve inbound iPhone ingestion independently of owner UI. | **M** |
| [wizard-calendar](#evidence-wizard-calendar) | Own event API; localStorage wc.mode is read at startup; trusted Host/Origin backend; update hold. | D calendar ops + S preference + B/A; U update hold. | Replace synchronous storage init; writes/refresh and held-update lifecycle must survive reload. | **M** |
| [wizard-chatgpt](#evidence-wizard-chatgpt) **D** | Sign-in UI fetches own API; exact Origin/Fetch metadata checks; Basic/session gateway variants and old appearance parent DOM in org variant. | D auth/status/usage operations + A; shell-owned sign-in confirmation/navigation. | Audit BOTH Oscar release package and org main; owner enrollment/login listener is outside Service token gate; image/source binding and refresh parity. | **L** |
| [wizard-claude](#evidence-wizard-claude) **D** | Own sign-in/usage API with Origin guard; Basic/session variants; org appearance parent.document. | D auth/status/usage + A; shell-managed sign-in actions. | Audit separate listener and source-qualified credentials; preserve account renewal, device-code and connection test; do not expose MCP/credential export. | **L** |
| [wizard-cloudflare](#evidence-wizard-cloudflare) | Own API session cookie + CSRF; bootstrap demands trusted Origin and Sec-Fetch-Site:same-origin; OAuth links and secret-bearing settings. | D reviewed Cloudflare owner operations; app-session custody + N external auth + A. | App-specific owner consent, not a general credential proxy; do not relax Origin:null or hand wz/cf_session, CSRF or owner gateway token to frame. | **L** |
| [wizard-connection-router](#evidence-wizard-connection-router) **D** | Manifest exposes descriptive static view; no view fetch found; appearance.js reads parent.document/getComputedStyle; hidden launcher plumbing. | A existing appearance snapshot; no data API needed for current static page. | Do not invent owner connection writes for this static slice. WAM provider/source-qualified grants remain separate infrastructure work. | **S** |
| [wizard-coros](#evidence-wizard-coros) | Own connector API and account/sync actions; Host/Origin guard; shared Back/theme. | D Coros operations + B/A + N auth navigation if used. | Never surface account credential material; verify connect/disconnect and server-side ingestion independently. | **M** |
| [wizard-files](#evidence-wizard-files) | Frontend reads owner file APIs; direct /wizard/v1/uploads fetch/XHR with progress; localStorage upload resume; indexedDB video frames; content/download/thumb URLs. | D authorized Files operations + REUSE WizUploads behind M upload port + S resume/cache + B/A/U. | Scope folders/agents and content grants; resumable chunks, HEAD/readback, large-media seeking and cancellation. Not the same app as default id=files. | **L** |
| [wizard-fitbit](#evidence-wizard-fitbit) | Own connector API, OAuth links, account form/media; Origin guard; Back/theme. | D Fitbit ops + B/A + N reviewed OAuth. | Return only connector status/data; preserve callback/session binding; do not allow arbitrary popup origins. | **M** |
| [wizard-garmin](#evidence-wizard-garmin) | Own connector API/account fields; Host/Origin guard; Back/theme. | D Garmin ops + B/A. | Review credential ingress and disconnect consent; retain server-only secrets and consumer-grant separation. | **M** |
| [wizard-google](#evidence-wizard-google) | api/session cookie/CSRF bootstrap and sign-in fetches; strict Origin/same-origin metadata; consumer routes reject browser credentials. | D Google owner ops + session custody + N auth + B/A. | No main branch: catalogue pin. Separate owner listener/relay audit; preserve grant consumer identity, exact callback state and disabled/unconfigured behavior. | **L** |
| [wizard-health](#evidence-wizard-health) | Own health aggregation API; localStorage metric and cached private health data; Host/Origin gate. | D scoped health reads + S private app cache + B/A. | Explicit storage quota/retention and privacy; /wizard/grants.json in backend is a mounted file, NOT an owner-browser route. | **M** |
| [wizard-mail](#evidence-wizard-mail) | Own API requires X-Wizard-Request:mail and same-origin metadata; write Origin check; localStorage preview choice; connect.js directly bootstraps other provider apps; contentDocument used for a CHILD message preview frame. | D Mail ops + provider-specific connection ceremony + S prefs + M attachments; B/A/U. | Keep inert email-preview sandbox; contentDocument here is not owner parent access. Remove cross-provider direct browser API calls; sanitization and OAuth/session custody remain gates. | **L** |
| [wizard-manager](#evidence-wizard-manager) | Own api/state/request calls; localStorage conversation draft/read/scroll with write-readback; shared nav/thread/view/update services. | D Manager ops + durable S draft transaction + B/A/U/N. | Fail-closed draft durability and reading-place migration; server /wizard/hermes calls are backend authority, not frontend owner fetch. | **M** |
| [wizard-microsoft](#evidence-wizard-microsoft) | Own api/session cookie/CSRF and Origin checks; quick sign-in polling page; form/login links. | D Microsoft owner ops + session custody + N auth + B/A. | Separate listener/callback audit; owner relay vs consumer/MCP separation; no blanket null-origin allowlist. | **L** |
| [wizard-monarch](#evidence-wizard-monarch) | Own financial-connector API and connection form; trusted Origin; app theme client uses old appearance protocol. | D Monarch ops + A/B. | Keep finance tokens server-side; explicit owner consent for connection changes and scoped consumer reads. | **M** |
| [wizard-music](#evidence-wizard-music) | Own APIs incl legacy /wizard/music backend; localStorage playback state; parent.location + parent.WizBackgroundAudio gate; origin-bound postMessage; stream URLs/audio engine. | D Music ops + S queue/state + M ranged stream + EXTEND V background-audio + B/A. | No main branch: catalogue pin. Preserve background play/lockscreen/queue revision, tokenized media isolation and reconnect; no direct native authority. | **L** |
| [wizard-notes](#evidence-wizard-notes) | Own Notes API/Host/Origin guard; localStorage draft/recovery; theme/Back SDK aliases. | D Notes-local ops + S drafts + B/A/U. | Ordinary compatibility only; no private notebook adapter, no special Notes workstream and no reason to grant broader reads. | **M** |
| [wizard-oura](#evidence-wizard-oura) | Own OAuth/sync connector API, links/forms; Origin guard; Back/theme. | D Oura ops + B/A + N auth. | Connection consent/callback state and secrets stay server-side; do not turn OAuth into arbitrary navigation. | **M** |
| [wizard-podcasts](#evidence-wizard-podcasts) | Own podcast APIs, localStorage filters/mini-player resume; direct audio src and Range fetch; pagehide keepalive progress; shared ducking/update holds. | D podcast ops + S resume + M ranged audio + V background/audio.duck + B/A/U/N. | Progress flush must survive view teardown without leaking authority; download/seek/native continuity and update-hold release. | **L** |
| [wizard-polar](#evidence-wizard-polar) | Own OAuth/sync API and forms; Host/Origin guard; Back/theme. | D Polar ops + B/A + N auth. | Retain exact OAuth callback binding; app/backend no-null refusal stays intact. | **M** |
| [wizard-search](#evidence-wizard-search) | Own API fetches + EventSource overview stream; indexedDB voice query custody; shared voiceInput; Origin checks and image URLs. | D Search ops + T bounded overview stream + S query receipts + M safe images + B/A/V. | No main branch: catalogue pin. SSE lacks token header; retain one-shot/acknowledged voice insertion and provider choice confirmation. | **L** |
| [wizard-simplefin](#evidence-wizard-simplefin) | Own financial connector API/Origin gate; sessionStorage sf-step read during startup; connect token form. | D SimpleFIN ops + S wizard-step preference + B/A. | Startup storage denial currently throws; preserve one-use setup-token handling and secret-free responses. | **M** |
| [wizard-tinfoil](#evidence-wizard-tinfoil) | Own API key/billing/model operations; strict trusted Origin + X-Wizard-Request; box-only /v1 and /mcp listeners. | D exact owner setup/status ops + A/B. | Separate account/proxy listener audit mandatory. Never expose key-export, arbitrary inference or consumer bearer via shell broker. | **M** |
| [wizard-ux](#evidence-wizard-ux) **D** | Trusted shell owns token bootstrap/fetch patch, all SDK state and native bridges; headers not automatically attached to XHR/EventSource/media/native downloads. | REUSE #327 channel/B/A/field/share/transcribe; EXTEND shared adapter owners only. | Default-off remains until platform/native plus actual package compatibility pass. Trusted child system screens cannot just inherit owner token. | **L** |
| [wizard-voice-service](#evidence-wizard-voice-service) **D** | Manifest explicitly no owner UI. MCP speech job service; Origin-restricted front; no app frame to migrate. | REUSE existing service grants and #327 bounded transcription where appropriate. | Preserve durable jobs/corrections and engine identity; no origin-null exception and no speculative iframe port. | **S** |
| [wizard-whoop](#evidence-wizard-whoop) | Own OAuth/sync API, connection links/forms; Origin guard; Back/theme. | D WHOOP ops + B/A + N auth. | Callbacks/session identity and private health-data consumer scopes need regression evidence. | **M** |
| [wizard-withings](#evidence-wizard-withings) | Own OAuth/sync API and links/forms; Host/Origin guard; Back/theme. | D Withings ops + B/A + N auth. | Preserve explicit account consent and callback state; no browser-visible consumer credentials. | **M** |
| [wizard-youtube-music](#evidence-wizard-youtube-music) | Own credentialed API/control actions; old appearance protocol; origin-bound wizard:open-app agents message; player/account connection links. | D YouTube Music ops + B/A + N navigation/auth; M only for actual media paths. | Keep account sign-in and separate audio/native provider scopes; verify actual playback not only UI API responses. | **M** |


## Shell-owned system views: do not grant arbitrary installed apps these powers

These are additional first-party **surfaces within wizard-ux / WAM**, not extra index app IDs. The sandbox decision covers their child documents too. Calling them first-party is not a reason to leak the shell token into an iframe.

| Surface / actual source | What breaks / authority needed | Minimal handling | Size / review |
|---|---|---|---|
| **Agents** `web/agents/agents.js:49`, `web/core/agents.js` | Direct `/wizard/v1/agents` reads/permission writes, options, agent creation; shared parent/SDK hooks. | Shell-owned agent-management operation set and shell confirmation for permission changes; do NOT give any app `agents.*` owner access. Prefer trusted built-in shell code or a dedicated source-pinned system-panel instance requesting named intents. | L; Miguel security/API; Jan handset/Back. |
| **Store** `web/store/store.js:48–67,259,390–420`; `core/store-install.js` | Parent config/skin/appsLoaded/CanOpen, catalogue + installed snapshots, installs/uninstalls/access/lifecycle, top navigation. | Keep existing Store installer/idempotency/selection owner. Shell owns trusted install review and execution; panel requests source+commit-qualified intent. No generic install relay to apps; do not revive link installs. | L; Miguel install/identity; Jan confirmation and Back. |
| **My Apps / Resources / Connections** `web/wizard-apps/`, WAM `wizard-views/`, `core/resources.js`, `core/connection-policy.js` | Owner lifecycle, grants/network/storage/provider changes, shared parent state; two shipped frontends exist. | Reuse existing owner services and page registry; explicitly inventory both UX-hosted and WAM-hosted documents. Shell-owned, typed management panels only; never all-app grant endpoints. | L; Miguel topology/owner policy. |
| **Setup / Phone Setup** `web/setup/setup.js:16,25,48,206`, `recommended.js:12`; `core/phone-connect.js` | Direct bootstrap/setup/phone endpoints; parent.document layout, config/phone native; recommended install/prefetch. | Existing phone-connect and Store owners behind dedicated shell intent; minimal greeting/layout snapshot, not bootstrap/settings export. Preserve separate prefetch vs installation consent. | L; Miguel recovery/owner; Jan pairing/reset/handset. |
| **Pages** `web/core/pages.js`, `web/core/chats-view.js` | Agent Pages/custom in-document modules can execute on shell principal if admitted as script, bypassing frame isolation completely. | App/agent-generated content stays an opaque frame. Only reviewed built-in shell modules may run in-document. Disable untrusted Chats-module import under boundary until a non-owner rendering contract exists; review existing module loader, not just iframe attributes. | L security gate; Miguel. |
| **Built-in Chats / Settings / Appearance / Home** `web/app.js`, `web/desktop/desktop.js`, `core/settings.js` | In-shell owner state is intentional; direct media, EventSource/XHR/native requests are not covered by a `fetch` patch. Settings also nests connection frames. | Keep in trusted main document; route headerless protected content through M/T. Audit every nested frame and page load, not only app-window creation. `allow-same-origin`/srcdoc exceptions must not reintroduce owner script. | L platform; Miguel + Jan. |

**Legacy/reserved inventory:** `wizard-app-store/apps/wizard-ai-accounts/config.json` has `available:false` and explicitly deprecates the app in favor of Claude and ChatGPT; retain existing rotating-login migration safeguards, do not enable its old page on the owner origin. `wizard-agent-history` has only placeholder source and a null default slot: no shipped app view to migrate. WAM's `chats` slot is null with built-in wizard-chats, not a missing package. `connected-accounts` and Cloudflare in WAM defaults are **recommended/on-demand**, not claimed installed-by-default. Existing private/local apps (Shopping, Recorder, Meditate, private editor variants etc.) are **outside this public-source census** and require their own compatibility evidence before enabling on a box that has them. No live installation inventory was read.

## Minimal design: extend the existing boundary, do not create a second privileged bridge

### 1. Admission, principal and transport — REUSE / EXTEND

**REUSE** #327 `WizBrowserBoundary.attach/admits`, registered iframe `contentWindow`, per-load channel, generation revocation, structured replies/timeouts, frame visibility checks and `WizAppServices` registration. `Origin:null` alone is never admission. Bind authority to the **installed source-qualified identity** (repo + installed instance/source selection, not caller-supplied `appId`, not a catalogue ID alone), then to this exact frame/load. Revalidate installed/running/granted state on invocation; revoke pending operations/ports when frame navigates, detaches, app updates/uninstalls or authority is removed. No secret is sent in handshake, errors or telemetry. App operation completions may persist to their own backend but cannot paint/send into replacement frames.

**REUSE** #168 `wam/browser_boundary.py` gate (`X-Wizard-Shell-Token`, exact token, reject null Origin/cross-site), source-bound WAM grant machinery and existing view/upstream resolution. **Important:** #168 does not already implement a generic app-data, browser-state or media adapter; backend file-storage/grant changes are not a browser localStorage replacement. Keep the Service agent/peer/MCP principal separate from browser possession; a machine bearer is not an owner session.

**EXTEND** the existing opaque request dispatch with individually admitted methods below. Maintain one shared client facade and one service owner per capability; do not make a separate iframe RPC SDK or rely on DOM inspection. Header-injected fetch is shell-only. Never add `allow-same-origin`, globally allow `Origin:null`, give the app the token, or support `fetch(url,init)` / arbitrary native invocation.

### 2. Typed app-data operations D — NEW capability, EXTEND transport and existing app gateway

- Shape, **proposed not implemented**: `data.call({operation, args, operationKey?})`. Operation is a static ID registered for that installed source/version, not a URL, method, headers, arbitrary provider, path or arbitrary MCP tool supplied by a frame.
- Each reviewed operation maps to fixed method/path templates on **that app's existing view API**, input/output schema, permitted response kind/size, timeout and write/consent class. Reuse WAM's validated view registry/upstream resolution, and the existing same-origin app gateway. Where a provider is involved, use the existing source-bound consumer grant on the backend; the browser cannot pick another consumer identity.
- Shell dispatch may call the known same-origin app API with `credentials:same-origin`, keeping app session/CSRF in shell custody; a Service-side operation implementation must preserve the backend's actual owner/session policy rather than pretend that a forged trusted Origin or an agent bearer is owner consent. App-specific sign-in/session bootstraps need adapters; there is no safe universal cookie-login fix.
- No arbitrary host/path, redirects, owner cookies/Authorization/shell token forwarded to app upstreams, `Set-Cookie`/CSRF/key material in frame responses, or raw HTML error reflection. Reject unknown operations and bound IDs/arguments/body/result/concurrency. Existing owner API paths (`/wizard`, installs, grants, runs, credentials, global settings) are **not** ordinary app-data targets.
- Preserve real idempotency keys and unknown-result reconciliation across transport loss. Trusted shell confirmation is needed for owner/global changes, new account grants, app install or a new send—not a claim that every UI click is owner consent. Reuse #327's trusted share sheet where applicable.
- System panels use a separate, built-in-source-qualified intent registry; never allow an installed app to claim it is Store/Agents by name or path. Apps can ask to open those shell panels, not invoke their owner operations unattended.

### 3. Per-installation storage S — NEW facade, REUSE one shell-owned persistence store

- Async `state.read / write / remove / transaction` via the same opaque channel; namespace assigned by the shell from installed source+instance, schema version, revision/CAS, byte quota and lifetime. Separate persistent from session-only state. App cannot name a shell database/key, another app, global `wos.skin`, a vault or a filesystem path.
- One shell-owned IndexedDB store can persist browser preferences/drafts/blobs; do not make a new database/daemon per app. Reuse existing app server storage/archive for canonical documents and original recordings. Browser persistence is not a substitute for server backup or readback-verified audio custody. Give health/finance caches explicit retention/delete behavior; no credential/token material in browser state.
- **No synchronous localStorage/IndexedDB polyfill.** Opaque-origin storage throws; update app startup to await hydration, render loading honestly, handle quota/unavailable failures, and only release unsaved/update holds after transaction completion/readback. Manager's draft write-readback and Outline's recovery ledger are acceptance obligations, not optional UI polish.
- Migration is a shell-owned, explicit allowlisted mapping of **known old keys/database stores to the specific installed source**; never let the frame request arbitrary legacy keys. Copy, verify revision/content/hash as applicable, then mark migration; leave old data untouched for rollback until separately approved. Unknown/shared keys require owner review. Avoid importing one published Profiles source's state into the other automatically.

### 4. Scoped media/upload/download M — EXTEND existing Uploads/content/share owners

- Reuse `WizUploads` resumable/chunk ownership, existing app content endpoints, shell download/open and share components. Do not add a second uploader or accept arbitrary file paths/URLs from a frame.
- `media.open({resourceId, purpose})` resolves a resource already allowed to this app/owner choice; return a typed transferred Blob for small data or an **app/resource/method-bound short-lived content ticket** for large ranged playback. Tickets must not be shell/owner tokens and must not authorize any other API. Enforce Range/HEAD rules, expiry, origin/credential policy and bounded resource types on the ticket-only content listener. Revocation cannot recall bytes already delivered; scope admission accordingly.
- `<img>`, `<video>`, `<audio>`, anchors/forms, XHR and native download managers cannot attach the shell's fetch header. Browser/native headerless loads use those content tickets, never shell-token query strings or Referer-bearing owner URLs. `credentials:omit` on ticket fetches; if CORS is required, allow it **only on the resource-ticket endpoint**, not owner or general app APIs. Executable/HTML content is not served as an owner-origin document; enforce content-type, nosniff and attachment/inert-viewer policy.
- Shell-mediated, owner-selected download/save/open and upload progress/cancel ports keep filenames, folder grants, byte limits and idempotency. Preserve Files chunk offset/HEAD readback, retry after uncertain outcomes, media seeking, PDF viewer behavior and navigation-away cancellation.

### 5. Streams, shared SDK and native/audio — EXTEND, not another engine

- `T`: a bounded operation-bound stream port (SSE/realtime or read-only run subscription), cancellation/backpressure and generation checks. Relay through existing backend streaming components or narrowly scoped short-lived stream tickets; EventSource/WebSocket cannot send the header. Never a general socket/tunnel or runs API. Limit event kinds, total bytes/rate/duration and close on revocation.
- `U`: source-bound view visibility, update-hold acquire/release leases, titlebar/badge state and pinning. Shared shell state only for that app. `N`: open a known installed app or trusted shell panel / external auth URL from a reviewed allowlist, with unsent thread handoffs kept unsent. Never `parent.WizOpenApp` or arbitrary top navigation as authority.
- `V`: route existing `WizCapture` / retained-original ledger, `WizBackgroundAudio`, Photos relay and bounded haptic through the new main-document native receiver and opaque channel. Keep original audio ack/recover semantics; `voice.transcribe` alone does not replace PCM capture, 5-second original chunks or background playback. Vault unlock/key access remains owner-presence/biometric and source-bound, not generic `native.call`.
- Existing B/A/field/share/transcribe remain **REUSE**, with app opt-in and old appearance protocol conversion. Keep Back in Wizard, same-frame tap feedback, field seals, visible-source checks and real trusted shell confirmation. Verify Appearance v1 `--wz-*`, live skin changes, dark standalone fallback and opaque text panels on **two in-shell skins**; static source scans do not close that gate.

## Native: exact Android main-source finding and Jan's proof list

Source pin for the following paths: `humanitylabs-org/wizard-ux@ac0d73e752d3d0bedd68926936d128ec5a9b14d3` (GitHub main when fetched).

1. **Unsafe attachment is concrete:** `android/app/src/main/java/ai/wizards/os/MainActivity.java:180` calls `web.addJavascriptInterface(new Bridge(), "WizardOSNative")`. This injects the Java object into **all WebView frames**, including opaque sandboxed frames; a JavaScript `parent===window` wrapper does not remove the object's native authority. `Bridge` begins at **951**, with download/open browser at **953–962**, plus device settings, usuals and other annotated methods. These are not uniformly protected by caller-frame identity.
2. **Second all-frame object:** `MainActivity.java:191–193` constructs `device/DeviceBridge.java` and registers it as `WizardOSDevice` on the same WebView. `DeviceBridge.java:171–360` contains annotated recording, clipboard, microphone/settings and custody methods; it does not have a frame-aware message receiver. For example `recRead`/`recDone` at **269/277** address retained recording data. A WebView top-URL check elsewhere cannot identify the calling subframe. A usable existing frame-aware model is `apps/AppsBridge.java:125–127,149–151` (Origin, `isMainFrame`, `shellOnTop`), and `MainActivity.java:97–99` already gates `wizardScreenPort` to the main frame.
3. **Minimal safe implementation:** remove **both** `addJavascriptInterface` registrations (all annotated entry points lose injection), reuse AndroidX `WebViewCompat.addWebMessageListener` with an exact persisted owner-origin allowlist, and enforce `isMainFrame`, expected trusted top-document path/identity and current navigation generation **in native receiver code before dispatch**. Migrate shell synchronous reads to an async cached/readiness facade; a method-name-preserving JS wrapper may be installed only in the trusted main document, without exposing a synchronous Java object to frames. No legacy fallback to `addJavascriptInterface` when WebMessage/document-start support is missing: fail closed with visible unsupported capability. Bind pending responses to generation. Remove the unused annotations/object too, so a future convenience registration cannot reopen it.
4. **Other native surfaces need the same inventory, not just those two lines:** `mizel/MizelBridge.java:48,63–73` (`wizardMizelPort`) checks Origin but does not reject a child `isMainFrame:false`; `audio/BackgroundAudioBridge.java:28,33` (`wizardAudioPort`) already rejects non-main/source-origin/non-shell-top calls and should retain that contract. `photos/PhotosBridge.java:61,118–119`, `apps/AppsBridge.java:72–73,125–127,149–151`, `HomeScreenShortcuts.java:74–76` and `MainActivity.java:97–99` already have main-frame admission checks—reuse and test them, including trusted-path/navigation identity. There are additional all-frame objects in **separate local-only WebViews**: `assist/AssistLockActivity.java:96` and `assist/WizardSession.java:100` (`WizardNative`), `everywhere/ScreenMode.java:128` (`ScreenNative`) and `everywhere/EverywhereService.java:503` (`EverywhereNative`). These explicitly block network loads and serve bundled assets; that is a different exposure from the remote shell WebView, not evidence of a remotely exploitable path. Jan must verify their loaded-content/child-frame boundary rather than blindly count them as closed. Same-origin legacy meeting/player frames must use a scoped shell relay instead of preserving direct native authority.
5. **Downloads:** `MainActivity.java:203` WebView download listener routes to `downloadOutside`, in addition to the annotated `Bridge.download`. Native download authorization and navigation interception need the scoped M contract; blocking the JS object alone does not close other owner-cookie/native navigation paths.

**Jan must return real APK + Mac receipts, not a JS fixture:**

- Candidate binary/package source identity; on Android, instrument/assert no all-frame Java interfaces, and absence/denial in same-origin, cross-origin, `Origin:null`, nested, srcdoc/about:blank and redirected child frames. Hostile child tries direct `WizardOSNative`/`WizardOSDevice`, every existing message port, forged source, stale reply/channel and navigation race; native logs show **no action**, not merely a missing JS property.
- Trusted main shell still supports Back (never exits), external links and scoped downloads, haptics, device/identity/biometric prompts, phone pairing/reset, locked/assist/teach activities, voice dictation, retained recording recovery, Photos and background Music/Podcasts. Prove the old direct meeting/player flows were migrated rather than silently dropped. Authenticated downloads/Range streaming and return from background must work without leaking the shell token.
- On Mac/WKWebView, inspect **actual** script-message handler installation (`WKUserContentController`, document-start scripts, user scripts/content worlds); receiver enforces `WKScriptMessage.frameInfo.isMainFrame`, trusted security origin + top navigation generation and reviewed command set. Reject child handlers in every configured content world and any remote-control/localhost bridge bypass; no assumption that Android Java findings describe Mac implementation. Native Mac sources/binary were not inspected in this census.
- Two skins, phone and desktop; real trusted click/share confirmation and cancel/navigation races; mic/device prompts remain usable only from authorized shell UI. No synthetic `isTrusted:true` test is a user-gesture acceptance receipt.

## Top five blockers to turning the real fix on

1. **Native remains an all-frame owner-power escape** through two Android Java objects; other native ports/activities and Mac still need proof. Sandbox alone does not close it.
2. **Most real app data paths have no scoped opaque adapter.** Their own backends intentionally reject null Origin or require owner cookies/CSRF; first-party system panels still call owner APIs and parent hooks directly. A generic fetch/owner-API relay would erase the security fix.
3. **Durable state would be lost or views would fail at startup.** localStorage/sessionStorage/IndexedDB are unavailable to opaque frames; Manager/Messenger/Outline/Files/voice/search need verified preservation, not an exception-catching cosmetic fix.
4. **Protected media and long-lived protocols bypass the fetch-header mechanism.** File URLs, image/audio/video/Range, XHR uploads, SSE/WebSocket and native downloads need scoped content/stream ownership; original-audio and background playback parity are not covered by transcription.
5. **Actual package enablement is unproven:** wrapper-only default Files/Hermes/alternative frontend and separate sign-in/recovery/account listeners lack exact served-asset/runtime evidence; in-document Pages/Chats modules can bypass isolation. Public-source coverage is not the installed private-app inventory or a full phone/Mac product test.

## Order of work and active-work sizing

Work in this order; keep the flag default-off throughout preparation. Do not merge or rewrite the existing drafts as part of this census.

| Stage | Deliverable / acceptance | Active-work estimate | Review owner |
|---|---|---:|---|
| 1 | Miguel reviews principal/admission, D operation registry vs system-panel intents, exact backend auth/session model, source-qualified identity collision, app grants and separate listener inventory. Jan reviews main-document native contract concurrently. | 4–6 h | Miguel; Jan |
| 2 | Extend existing opaque channel/client and owner dispatch with typed D, scoped S and U/N baseline; migrate one plain app plus one durable-draft app with synthetic backends; denied/unknown/stale/cross-app operations fail closed. | 14–22 h | Miguel security + API |
| 3 | M content/upload and T streams; reuse resumable uploader/capture/background owners; proof of Range/HEAD, cancellation, bounded tickets and no owner credentials upstream. | 14–24 h | Miguel protocols/grants; Jan native consumers |
| 4 | Native all-frame removal, main-frame-only receivers on every Android activity/port; Mac frame-info equivalent; trusted shell facade migration. Can overlap stage 2 but must precede enablement. | 16–28 h | Jan implementation/binary QA; Miguel authority review |
| 5 | App migrations from table; do plain API/appearance/preference family once, then default account/session/Files/Hermes images, then shared drafts/recordings/realtime/media. Migrate Agents/Store/Setup/Resources as shell-owned surfaces, not installed-app powers. | See computed app subtotal below; system panels another 12–20 h | Miguel auth/system panels; Jan interaction/native |
| 6 | Package/pins/rollback fixtures, isolated fresh + alongside actual public default install and upgrade; negative tests + real browser/phone/Mac product workflows, no live James box. Two-skin screenshots and exact-head r5 rerun. | 8–12 h packaging + 16–28 h QA | Miguel source/grants/config; Jan APK/Mac |

**Computed planning bounds (not elapsed-time promises):**

- Shared platform/system/native/package/QA stages above: **84–140 active hours**; this includes both platform rows and the six system-surface groups, so they are not added twice.
- Default-app + host-recovery integrations excluding the two platform rows: **11 packages**, **36–88 h**. Together the smallest default-system pilot is **120–228 active hours**.
- All public app integrations excluding the two platform rows: **48 packages**, **160.5–387 h**. Whole public catalogue + additions + shared/system/native/acceptance work: **about 245–527 active hours**.
- These are deliberately broad source-based estimates. Common provider-app code should reduce repeated work after the first template migration; do not count on that saving before parity receipts. Replacing an opaque upstream frontend, resolving new auth/listener flaws, or migrating private apps can exceed the bounds. Review/queue waiting is excluded.


Do not average away unknown image/listener failures. The **smallest global-box pilot** is not Notes: it is all installed defaults + every reachable system panel + native enforcement + actual package/runtime verification. Catalogue-only optional apps can migrate in waves and be unavailable under the boundary until proven, but do not preserve compatibility by falling back to an unsandboxed frame. An enablement decision for James's box additionally requires a read-only installed-app inventory and private-app owners' migration evidence; that inventory was intentionally not collected here.

### Miguel's explicit review gates

- D schemas/response bounds and owner-session custody; no arbitrary routing, header copying or owner/run/lifecycle proxy; deny revoked/uninstalled/source-collision calls. App backend own-data scope is not permission to global owner APIs.
- Exact source-qualified grant/upstream/storage mapping, including both published Profiles sources and owner-vs-agent-vs-peer principals. Keep WAM network grants and browser grants related but not conflated.
- Every separate app owner listener (Cloudflare, Google/Microsoft, Tinfoil, connection apps, File Browser/Hermes/legacy auth, Troubleshooter) and every legacy/import/content route: Origin/Host/Fetch metadata is defense in depth, not owner authentication by itself.
- Storage migration/rollback and original-data custody; system panels/custom module isolation; source pins and packaged entrypoints. Review draft-to-main drift without dropping existing daily features. Existing WAM alias-import/storage test gap stays open until actual suite receipt.

### Verified now / not verified

**Verified:** public catalogue pagination completed; all listing entries and all release-default IDs have rows; source archives pinned and regex/category hit files persisted; both main and relevant shipped source pins available; Android attachment and receiver code inspected. Evidence and count assertions are generated programmatically by `census_report.py` and `census_scan.py`.

**Not verified:** app runtime compatibility, actual image-byte execution, data migration, browser/handset user gestures, private installed apps, separate listeners' configured exposure, Mac implementation or binary enforcement. No builds, deploys, PRs, merges, draft edits or live-box reads were performed. This is a migration census/design, not a release acceptance report.

## Per-app evidence pointers

Each pointer below uses the exact source pin. The raw hit list also includes false positives; the app table above is the reviewed classification. Absence of a pointer for a category means no relevant hit in the inspected source, not proof of absence in an opaque image.

<a id="evidence-browser"></a>
### browser

- **humanitylabs-org/browser**: [`4c313284bc73e0af20b7faba7a2554bff1b63513`](https://github.com/humanitylabs-org/browser/tree/4c313284bc73e0af20b7faba7a2554bff1b63513) (main); packaged variants: `main@4c313284bc73`.
  - Package/source: [wizard.md](https://github.com/humanitylabs-org/browser/blob/4c313284bc73e0af20b7faba7a2554bff1b63513/wizard.md). No relevant runtime hit in available wrapper source; see confidence limit in table.
  - Package/source: [runtipi/docker-compose.yml](https://github.com/humanitylabs-org/browser/blob/4c313284bc73e0af20b7faba7a2554bff1b63513/runtipi/docker-compose.yml). No relevant runtime hit in available wrapper source; see confidence limit in table.
- **oscarhenrycollins/browser**: [`4c313284bc73e0af20b7faba7a2554bff1b63513`](https://github.com/oscarhenrycollins/browser/tree/4c313284bc73e0af20b7faba7a2554bff1b63513) (main); packaged variants: `main@4c313284bc73`.
  - Package/source: [wizard.md](https://github.com/oscarhenrycollins/browser/blob/4c313284bc73e0af20b7faba7a2554bff1b63513/wizard.md). No relevant runtime hit in available wrapper source; see confidence limit in table.
  - Package/source: [runtipi/docker-compose.yml](https://github.com/oscarhenrycollins/browser/blob/4c313284bc73e0af20b7faba7a2554bff1b63513/runtipi/docker-compose.yml). No relevant runtime hit in available wrapper source; see confidence limit in table.

<a id="evidence-connected-accounts"></a>
### connected-accounts

- **humanitylabs-org/wizard-connectors**: [`e873a61cb9793c222c806194314c0143622c8d00`](https://github.com/humanitylabs-org/wizard-connectors/tree/e873a61cb9793c222c806194314c0143622c8d00) (catalogue_pin); packaged variants: `catalogue_pin@e873a61cb979`.
  - network: [web/app.js:9](https://github.com/humanitylabs-org/wizard-connectors/blob/e873a61cb9793c222c806194314c0143622c8d00/web/app.js#L9) — `async function api(path, data){const r=await fetch('api/'+path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data),credentials:'same-origin',cache:'no-store'`
  - origin: [app/server.py:59](https://github.com/humanitylabs-org/wizard-connectors/blob/e873a61cb9793c222c806194314c0143622c8d00/app/server.py#L59) — `origin = self.headers.get("Origin")`
  - assets: [web/index.html:1](https://github.com/humanitylabs-org/wizard-connectors/blob/e873a61cb9793c222c806194314c0143622c8d00/web/index.html#L1) — `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Connected accounts</title><script src="boot.js"></script><link rel="stylesheet" href="wizard-ui.css"><link rel="stylesheet" hre`
  - shared: [web/app.js:11](https://github.com/humanitylabs-org/wizard-connectors/blob/e873a61cb9793c222c806194314c0143622c8d00/web/app.js#L11) — `function dialog(title,text){$('dialog-title').textContent=title;$('dialog-text').textContent=text;$('dialog').showModal();overlay=WizardApp.back.push(()=>{closeDialog();return true;});}`

<a id="evidence-contacts"></a>
### contacts

- **oscarhenrycollins/contacts**: [`7eee025b0e680fbd37f0941cf5fc3587479c0fda`](https://github.com/oscarhenrycollins/contacts/tree/7eee025b0e680fbd37f0941cf5fc3587479c0fda) (main); packaged variants: `main@7eee025b0e68`.
  - network: [web/app.js:58](https://github.com/oscarhenrycollins/contacts/blob/7eee025b0e680fbd37f0941cf5fc3587479c0fda/web/app.js#L58) — `const r = await fetch(path, init);`
  - origin: [app/server.py:984](https://github.com/oscarhenrycollins/contacts/blob/7eee025b0e680fbd37f0941cf5fc3587479c0fda/app/server.py#L984) — `# browser Origin on writes must be configured too. ′contacts:<port>′ is the name linked apps use on their`
  - assets: [web/app.js:38](https://github.com/oscarhenrycollins/contacts/blob/7eee025b0e680fbd37f0941cf5fc3587479c0fda/web/app.js#L38) — `const img = el('img', 'ct-qr'); img.alt = label || 'QR code'; img.src = q.createDataURL(8, 2); return img; }`
  - shared: [web/app.js:55](https://github.com/oscarhenrycollins/contacts/blob/7eee025b0e680fbd37f0941cf5fc3587479c0fda/web/app.js#L55) — `function toast(text) { if (window.WizardApp?.toast) WizardApp.toast(text); else say(text, 'note'); }`

<a id="evidence-defleur-video"></a>
### defleur-video

- **humanitylabs-org/defleur-video**: [`ba5b14c8fcd67bb46944682543a036ccc9253e9a`](https://github.com/humanitylabs-org/defleur-video/tree/ba5b14c8fcd67bb46944682543a036ccc9253e9a) (main); packaged variants: `main@ba5b14c8fcd6`.
  - network: [service.py:79](https://github.com/humanitylabs-org/defleur-video/blob/ba5b14c8fcd67bb46944682543a036ccc9253e9a/service.py#L79) — `const r = await fetch('/v1/projects', {method: 'POST', headers, body: file});`
  - assets: [mcp_server.py:250](https://github.com/humanitylabs-org/defleur-video/blob/ba5b14c8fcd67bb46944682543a036ccc9253e9a/mcp_server.py#L250) — `"<source name>-edited-<id>.mp4 (never overwriting). Paths you pass are relative to Files, e.g. 'Videos/IMG_5644.mov'."),`

<a id="evidence-files"></a>
### files

- **filebrowser/filebrowser**: [`e8a388f840173580116f2743813d03b22286e44e`](https://github.com/filebrowser/filebrowser/tree/e8a388f840173580116f2743813d03b22286e44e) (shipped_upstream); packaged variants: `shipped_upstream@e8a388f84017`.
  - storage: [frontend/src/utils/auth.ts:13](https://github.com/filebrowser/filebrowser/blob/e8a388f840173580116f2743813d03b22286e44e/frontend/src/utils/auth.ts#L13) — `document.cookie = ′auth=${token}; Path=/; SameSite=Strict;′;`
  - network: [frontend/src/utils/upload.ts:39](https://github.com/filebrowser/filebrowser/blob/e8a388f840173580116f2743813d03b22286e44e/frontend/src/utils/upload.ts#L39) — `const destination = await api.fetch(basePath);`
  - origin: [frontend/vite.config.ts:17](https://github.com/filebrowser/filebrowser/blob/e8a388f840173580116f2743813d03b22286e44e/frontend/vite.config.ts#L17) — `compression({ include: /\.js$/, deleteOriginalAssets: false }),`
  - assets: [frontend/src/api/pub.ts:65](https://github.com/filebrowser/filebrowser/blob/e8a388f840173580116f2743813d03b22286e44e/frontend/src/api/pub.ts#L65) — `window.open(url);`
- **oscarhenrycollins/files**: [`8a4dd8ac5189d7d9d8af2bb8a2416936668e90df`](https://github.com/oscarhenrycollins/files/tree/8a4dd8ac5189d7d9d8af2bb8a2416936668e90df) (main); packaged variants: `main@8a4dd8ac5189`.
  - assets: [runtipi/docker-compose.yml:422](https://github.com/oscarhenrycollins/files/blob/8a4dd8ac5189d7d9d8af2bb8a2416936668e90df/runtipi/docker-compose.yml#L422) — `--perm.admin=false --perm.execute=false --perm.create --perm.delete --perm.download --perm.modify --perm.rename --perm.share`

<a id="evidence-hermes-agent"></a>
### hermes-agent

- **NousResearch/hermes-agent**: [`f97608f178d1ffeca59860195ab7da295f7c8e5f`](https://github.com/NousResearch/hermes-agent/tree/f97608f178d1ffeca59860195ab7da295f7c8e5f) (shipped_upstream); packaged variants: `shipped_upstream@f97608f178d1`.
  - storage: [web/src/App.tsx:384](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/web/src/App.tsx#L384) — `return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";`
  - network: [web/vite.config.ts:41](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/web/vite.config.ts#L41) — `const res = await fetch(BACKEND, { headers: { accept: "text/html" } });`
  - origin: [web/src/pages/SessionsPage.tsx:277](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/web/src/pages/SessionsPage.tsx#L277) — `/** Original message content that came after the end marker. */`
  - assets: [web/src/pages/ModelsPage.tsx:1310](https://github.com/NousResearch/hermes-agent/blob/f97608f178d1ffeca59860195ab7da295f7c8e5f/web/src/pages/ModelsPage.tsx#L1310) — `in <a href="/config" className="underline">Config</a> to`
- **oscarhenrycollins/hermes-agent**: [`e8ae558f26bf4b981e0cad60e387386a1ad7b869`](https://github.com/oscarhenrycollins/hermes-agent/tree/e8ae558f26bf4b981e0cad60e387386a1ad7b869) (main); packaged variants: `main@e8ae558f26bf`.
  - Package/source: [wizard.md](https://github.com/oscarhenrycollins/hermes-agent/blob/e8ae558f26bf4b981e0cad60e387386a1ad7b869/wizard.md). No relevant runtime hit in available wrapper source; see confidence limit in table.
  - Package/source: [runtipi/docker-compose.yml](https://github.com/oscarhenrycollins/hermes-agent/blob/e8ae558f26bf4b981e0cad60e387386a1ad7b869/runtipi/docker-compose.yml). No relevant runtime hit in available wrapper source; see confidence limit in table.

<a id="evidence-hermes-frontend-3"></a>
### hermes-frontend-3

- **humanitylabs-org/hermes-frontend-3**: [`ff1c579cbfc7ad96634434f6e2bbd545069540c2`](https://github.com/humanitylabs-org/hermes-frontend-3/tree/ff1c579cbfc7ad96634434f6e2bbd545069540c2) (main); packaged variants: `main@ff1c579cbfc7`.
  - Package/source: [wizard.md](https://github.com/humanitylabs-org/hermes-frontend-3/blob/ff1c579cbfc7ad96634434f6e2bbd545069540c2/wizard.md). No relevant runtime hit in available wrapper source; see confidence limit in table.
  - Package/source: [runtipi/docker-compose.yml](https://github.com/humanitylabs-org/hermes-frontend-3/blob/ff1c579cbfc7ad96634434f6e2bbd545069540c2/runtipi/docker-compose.yml). No relevant runtime hit in available wrapper source; see confidence limit in table.
- **oscarhenrycollins/hermes-frontend-3**: [`ff1c579cbfc7ad96634434f6e2bbd545069540c2`](https://github.com/oscarhenrycollins/hermes-frontend-3/tree/ff1c579cbfc7ad96634434f6e2bbd545069540c2) (main); packaged variants: `main@ff1c579cbfc7`.
  - Package/source: [wizard.md](https://github.com/oscarhenrycollins/hermes-frontend-3/blob/ff1c579cbfc7ad96634434f6e2bbd545069540c2/wizard.md). No relevant runtime hit in available wrapper source; see confidence limit in table.
  - Package/source: [runtipi/docker-compose.yml](https://github.com/oscarhenrycollins/hermes-frontend-3/blob/ff1c579cbfc7ad96634434f6e2bbd545069540c2/runtipi/docker-compose.yml). No relevant runtime hit in available wrapper source; see confidence limit in table.
- **przbadu/hermes-ui**: [`1af684e2d6ce05e6d1da82d67bc671e15d2d2d96`](https://github.com/przbadu/hermes-ui/tree/1af684e2d6ce05e6d1da82d67bc671e15d2d2d96) (shipped_upstream); packaged variants: `shipped_upstream@1af684e2d6ce`.
  - storage: [app/index.html:22](https://github.com/przbadu/hermes-ui/blob/1af684e2d6ce05e6d1da82d67bc671e15d2d2d96/app/index.html#L22) — `let bg = localStorage.getItem('hermes-boot-background')`
  - network: [app/src/lib/media.ts:137](https://github.com/przbadu/hermes-ui/blob/1af684e2d6ce05e6d1da82d67bc671e15d2d2d96/app/src/lib/media.ts#L137) — `const response = await fetch(dataUrl)`
  - origin: [app/vite.config.ts:19](https://github.com/przbadu/hermes-ui/blob/1af684e2d6ce05e6d1da82d67bc671e15d2d2d96/app/vite.config.ts#L19) — `// (the gateway's CORS and WS Origin checks are localhost-only).`
  - assets: [app/src/lib/svg-image.ts:44](https://github.com/przbadu/hermes-ui/blob/1af684e2d6ce05e6d1da82d67bc671e15d2d2d96/app/src/lib/svg-image.ts#L44) — `image.src = ′data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}′`

<a id="evidence-messenger"></a>
### messenger

- **humanitylabs-org/wizard-messenger**: [`77a21f949b743b8c7edfc7f35c0586ca8f723556`](https://github.com/humanitylabs-org/wizard-messenger/tree/77a21f949b743b8c7edfc7f35c0586ca8f723556) (catalogue_pin); packaged variants: `catalogue_pin@77a21f949b74`.
  - owner_routes: [static/unified.js:2657](https://github.com/humanitylabs-org/wizard-messenger/blob/77a21f949b743b8c7edfc7f35c0586ca8f723556/static/unified.js#L2657) — `await api('api/view/agents/wizard/' + encodeURIComponent(agent.id), {method: 'POST', body: {level}});`
  - storage: [static/app.js:135](https://github.com/humanitylabs-org/wizard-messenger/blob/77a21f949b743b8c7edfc7f35c0586ca8f723556/static/app.js#L135) — `let trustedWizard = (() => { try { return localStorage.getItem(TRUSTED_KEY) === '1'; } catch { return false; } })();`
  - network: [static/app.js:214](https://github.com/humanitylabs-org/wizard-messenger/blob/77a21f949b743b8c7edfc7f35c0586ca8f723556/static/app.js#L214) — `const response = await fetch(path, {method, headers, credentials: 'same-origin', cache: 'no-store', signal, ...(body !== undefined ? {body: JSON.stringify(body)} : {})});`
  - origin: [API-contract.json:11](https://github.com/humanitylabs-org/wizard-messenger/blob/77a21f949b743b8c7edfc7f35c0586ca8f723556/API-contract.json#L11) — `"browser_origins": "Exact comma-separated MESSENGER_ALLOWED_ORIGINS; no permissive CORS. Non-browser clients may omit Origin. Cross-site browser requests are rejected.",`
  - assets: [static/connectors.js:474](https://github.com/humanitylabs-org/wizard-messenger/blob/77a21f949b743b8c7edfc7f35c0586ca8f723556/static/connectors.js#L474) — `if (f.frame) { img.src = 'data:image/jpeg;base64,' + f.frame; seq = f.seq; }`
  - shared: [static/app.js:112](https://github.com/humanitylabs-org/wizard-messenger/blob/77a21f949b743b8c7edfc7f35c0586ca8f723556/static/app.js#L112) — `window.WizardApp.ready({name: 'messenger', version: '0.2.0-unified.15.13'});`

<a id="evidence-money"></a>
### money

- **oscarhenrycollins/money**: [`d695fd02c4b93389405ea8d1428b5adac98779fc`](https://github.com/oscarhenrycollins/money/tree/d695fd02c4b93389405ea8d1428b5adac98779fc) (main); packaged variants: `main@d695fd02c4b9`.
  - storage: [web/app.js:20](https://github.com/oscarhenrycollins/money/blob/d695fd02c4b93389405ea8d1428b5adac98779fc/web/app.js#L20) — `try { cache = JSON.parse(localStorage.getItem(CK) || '{}'); } catch (e) { cache = {}; }`
  - network: [web/app.js:12](https://github.com/oscarhenrycollins/money/blob/d695fd02c4b93389405ea8d1428b5adac98779fc/web/app.js#L12) — `const r = await fetch(path, init);`
  - origin: [app/server.py:1467](https://github.com/oscarhenrycollins/money/blob/d695fd02c4b93389405ea8d1428b5adac98779fc/app/server.py#L1467) — `origin = (self.headers.get('Origin') or '').lower()`
  - parent, shared: [web/app.js:786](https://github.com/oscarhenrycollins/money/blob/d695fd02c4b93389405ea8d1428b5adac98779fc/web/app.js#L786) — `/* Inside the shell, Back (and Esc on the desktop) reach this app through WizardApp.back, not __wizardCloseOverlay,`

<a id="evidence-morning-report"></a>
### morning-report

- **oscarhenrycollins/morning-report**: [`b2572a17741b2bab7ee67aec044efc14749ff641`](https://github.com/oscarhenrycollins/morning-report/tree/b2572a17741b2bab7ee67aec044efc14749ff641) (main); packaged variants: `main@b2572a17741b`.
  - storage: [web/app.js:123](https://github.com/oscarhenrycollins/morning-report/blob/b2572a17741b2bab7ee67aec044efc14749ff641/web/app.js#L123) — `const seen = () => { try { return localStorage.getItem(SEEN) || ''; } catch (e) { return ''; } };`
  - network: [web/app.js:13](https://github.com/oscarhenrycollins/morning-report/blob/b2572a17741b2bab7ee67aec044efc14749ff641/web/app.js#L13) — `const r = await fetch(path, { cache: 'no-store' });`
  - origin: [app/server.py:153](https://github.com/oscarhenrycollins/morning-report/blob/b2572a17741b2bab7ee67aec044efc14749ff641/app/server.py#L153) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:46](https://github.com/oscarhenrycollins/morning-report/blob/b2572a17741b2bab7ee67aec044efc14749ff641/web/index.html#L46) — `<a id="pdf" class="mr-btn mr-text" href="#" target="_blank" rel="noopener" hidden>PDF</a>`
  - shared: [web/app.js:120](https://github.com/oscarhenrycollins/morning-report/blob/b2572a17741b2bab7ee67aec044efc14749ff641/web/app.js#L120) — `* count on this app's dock/bar mark (WizardApp.badge); a report counts as read once it is on screen`

<a id="evidence-movies"></a>
### movies

- **humanitylabs-org/movies**: [`def907556756774b313aa4c25f5d3ecd4f816a53`](https://github.com/humanitylabs-org/movies/tree/def907556756774b313aa4c25f5d3ecd4f816a53) (main); packaged variants: `main@def907556756`.
  - owner_routes: [cinequeue/server.py:241](https://github.com/humanitylabs-org/movies/blob/def907556756774b313aa4c25f5d3ecd4f816a53/cinequeue/server.py#L241) — `_wizard("POST", "/wizard/hermes/api/sessions", {"source": "wizard-mobile", "id": session_id})`
  - storage: [web/app.js:390](https://github.com/humanitylabs-org/movies/blob/def907556756774b313aa4c25f5d3ecd4f816a53/web/app.js#L390) — `let view = localStorage.getItem('cinequeue.view') === 'grid' ? 'grid' : 'list';`
  - network: [web/app.js:50](https://github.com/humanitylabs-org/movies/blob/def907556756774b313aa4c25f5d3ecd4f816a53/web/app.js#L50) — `const res = await fetch(base(path), { headers: { 'Content-Type': 'application/json' }, ...options });`
  - origin: [cinequeue/server.py:517](https://github.com/humanitylabs-org/movies/blob/def907556756774b313aa4c25f5d3ecd4f816a53/cinequeue/server.py#L517) — `"""Known Host, and a browser Origin that is absent, configured, or this box-local host itself."""`
  - assets: [web/index.html:27](https://github.com/humanitylabs-org/movies/blob/def907556756774b313aa4c25f5d3ecd4f816a53/web/index.html#L27) — `<a class="brand" href="./" aria-label="Movies home">`

<a id="evidence-notifications"></a>
### notifications

- **oscarhenrycollins/notifications**: [`804b486afbbf50acb7564d34453b47659ef147fc`](https://github.com/oscarhenrycollins/notifications/tree/804b486afbbf50acb7564d34453b47659ef147fc) (main); packaged variants: `main@804b486afbbf`, `release_pin@cdce9f18d10f`.
  - parent: [web/minimal/inbox.js:56](https://github.com/oscarhenrycollins/notifications/blob/804b486afbbf50acb7564d34453b47659ef147fc/web/minimal/inbox.js#L56) — `try { const s = parent !== window && parent.document.documentElement.dataset.shell; if (s) return s === 'phone'; } catch (_) {}`
  - network: [web/minimal/inbox.js:20](https://github.com/oscarhenrycollins/notifications/blob/804b486afbbf50acb7564d34453b47659ef147fc/web/minimal/inbox.js#L20) — `const response = await fetch('api/' + path, data ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)} : {cache: 'no-store'});`
  - origin: [runtipi/docker-compose.yml:548](https://github.com/oscarhenrycollins/notifications/blob/804b486afbbf50acb7564d34453b47659ef147fc/runtipi/docker-compose.yml#L548) — `# JSON only: a form on another site cannot send this without a CORS preflight, which is never granted.`
  - assets: [web/minimal/inbox.js:151](https://github.com/oscarhenrycollins/notifications/blob/804b486afbbf50acb7564d34453b47659ef147fc/web/minimal/inbox.js#L151) — `const img = node('img'); img.alt = name; img.loading = 'lazy'; img.decoding = 'async'; img.src = url;`
  - shared: [web/minimal/inbox.js:188](https://github.com/oscarhenrycollins/notifications/blob/804b486afbbf50acb7564d34453b47659ef147fc/web/minimal/inbox.js#L188) — `const receipt = window.WizardApp.nav.openContextDraft({id: String(it.id), title: titleOf(it), message: String(it.message || '')});`

<a id="evidence-outline"></a>
### outline

- **humanitylabs-org/outline**: [`d7fe4e8f2c2e2b55da14874ef4f543952e469db8`](https://github.com/humanitylabs-org/outline/tree/d7fe4e8f2c2e2b55da14874ef4f543952e469db8) (main); packaged variants: `main@d7fe4e8f2c2e`.
  - storage: [runtime/web/app.js:190](https://github.com/humanitylabs-org/outline/blob/d7fe4e8f2c2e2b55da14874ef4f543952e469db8/runtime/web/app.js#L190) — `try{db=await new Promise((resolve,reject)=>{const req=indexedDB.open(config.recovery,1);req.onupgradeneeded=()=>req.result.createObjectStore('recovery');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});`
  - network: [runtime/web/app.js:8](https://github.com/humanitylabs-org/outline/blob/d7fe4e8f2c2e2b55da14874ef4f543952e469db8/runtime/web/app.js#L8) — `const request=async(path,options={})=>{const r=await fetch(path,{cache:'no-store',...options});const value=await r.json();if(!r.ok)throw Object.assign(new Error(value.error||'Request failed'),{status:r.status,value});return value;};`
  - origin: [runtime/web/index.html:15](https://github.com/humanitylabs-org/outline/blob/d7fe4e8f2c2e2b55da14874ef4f543952e469db8/runtime/web/index.html#L15) — `<dialog id="sheet"><div class="sheet-head"><h2>Outline</h2><button id="close-sheet" aria-label="Close menu">✕</button></div><button id="redo">↷ Redo</button><button id="share">↗ Share as text</button><button id="pause">Ⅱ Pause / resume dictation</button><butto`
  - assets, origin: [runtime/web/app.js:173](https://github.com/humanitylabs-org/outline/blob/d7fe4e8f2c2e2b55da14874ef4f543952e469db8/runtime/web/app.js#L173) — `async function recordings(){const list=$('recordings');list.replaceChildren();list.textContent='Loading original recordings…';try{const {takes}=await request('./api/audio');list.replaceChildren();if(!takes.length)list.textContent='No saved recordings yet. Reta`

<a id="evidence-photos"></a>
### photos

- **humanitylabs-org/wizard-photos-app**: [`0bd9e360ae59ded0589bab03d3c0a4b35a61541e`](https://github.com/humanitylabs-org/wizard-photos-app/tree/0bd9e360ae59ded0589bab03d3c0a4b35a61541e) (main); packaged variants: `main@0bd9e360ae59`.
  - origin: [app/static/photos.js:88](https://github.com/humanitylabs-org/wizard-photos-app/blob/0bd9e360ae59ded0589bab03d3c0a4b35a61541e/app/static/photos.js#L88) — `if (st.mode === 'legacy') return ′<div class="ph"><p class="ph-intro">This Wizard OS app predates the Photos app. Its backup screen still works.</p><button type="button" class="ph-row" data-ph="native"><span class="ph-tx"><b>Photos backup</b><small>Originals b`
  - shared: [app/static/app.js:38](https://github.com/humanitylabs-org/wizard-photos-app/blob/0bd9e360ae59ded0589bab03d3c0a4b35a61541e/app/static/app.js#L38) — `WizardApp.ready({ name: 'Photos', version: '1' });`

<a id="evidence-profiles"></a>
### profiles

- **humanitylabs-org/profiles**: [`5cbb6fb0fcc737ecc240fe47b88885364959f005`](https://github.com/humanitylabs-org/profiles/tree/5cbb6fb0fcc737ecc240fe47b88885364959f005) (main); packaged variants: `main@5cbb6fb0fcc7`.
  - owner_routes: [web/app.js:94](https://github.com/humanitylabs-org/profiles/blob/5cbb6fb0fcc737ecc240fe47b88885364959f005/web/app.js#L94) — `const [rel, inst, css] = await Promise.all([getJSON('/wizard-os-home/my-release.json'), getJSON('/wizard-os-home/store-data/wizard/v1/installed-apps'), getText('/wizard/v1/my-skin')]);`
  - storage: [web/app.js:57](https://github.com/humanitylabs-org/profiles/blob/5cbb6fb0fcc737ecc240fe47b88885364959f005/web/app.js#L57) — `const hideSystem = () => { try { return localStorage.getItem(SYS_KEY) === '1'; } catch (_) { return false; } };`
  - network: [web/app.js:29](https://github.com/humanitylabs-org/profiles/blob/5cbb6fb0fcc737ecc240fe47b88885364959f005/web/app.js#L29) — `const r = await fetch(path, { method, cache: 'no-store', credentials: 'same-origin', ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });`
  - origin: [app/server.py:1360](https://github.com/humanitylabs-org/profiles/blob/5cbb6fb0fcc737ecc240fe47b88885364959f005/app/server.py#L1360) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/app.js:144](https://github.com/humanitylabs-org/profiles/blob/5cbb6fb0fcc737ecc240fe47b88885364959f005/web/app.js#L144) — `img.src = url;`
  - shared: [web/theme-client.js:31](https://github.com/humanitylabs-org/profiles/blob/5cbb6fb0fcc737ecc240fe47b88885364959f005/web/theme-client.js#L31) — `if (parent===window || e.source!==parent || e.origin!==trustedHost || e.data?.type!=='wizard:appearance') return;`
- **oscarhenrycollins/profiles**: [`9d3d2061ef1a92089a487dd6053e48599f0f8d4e`](https://github.com/oscarhenrycollins/profiles/tree/9d3d2061ef1a92089a487dd6053e48599f0f8d4e) (main); packaged variants: `main@9d3d2061ef1a`.
  - owner_routes: [web/app.js:94](https://github.com/oscarhenrycollins/profiles/blob/9d3d2061ef1a92089a487dd6053e48599f0f8d4e/web/app.js#L94) — `const [rel, inst, css] = await Promise.all([getJSON('/wizard-os-home/my-release.json'), getJSON('/wizard-os-home/store-data/wizard/v1/installed-apps'), getText('/wizard/v1/my-skin')]);`
  - storage: [web/app.js:57](https://github.com/oscarhenrycollins/profiles/blob/9d3d2061ef1a92089a487dd6053e48599f0f8d4e/web/app.js#L57) — `const hideSystem = () => { try { return localStorage.getItem(SYS_KEY) === '1'; } catch (_) { return false; } };`
  - network: [web/app.js:29](https://github.com/oscarhenrycollins/profiles/blob/9d3d2061ef1a92089a487dd6053e48599f0f8d4e/web/app.js#L29) — `const r = await fetch(path, { method, cache: 'no-store', credentials: 'same-origin', ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });`
  - origin: [app/server.py:1360](https://github.com/oscarhenrycollins/profiles/blob/9d3d2061ef1a92089a487dd6053e48599f0f8d4e/app/server.py#L1360) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/app.js:144](https://github.com/oscarhenrycollins/profiles/blob/9d3d2061ef1a92089a487dd6053e48599f0f8d4e/web/app.js#L144) — `img.src = url;`
  - shared: [web/theme-client.js:31](https://github.com/oscarhenrycollins/profiles/blob/9d3d2061ef1a92089a487dd6053e48599f0f8d4e/web/theme-client.js#L31) — `if (parent===window || e.source!==parent || e.origin!==trustedHost || e.data?.type!=='wizard:appearance') return;`

<a id="evidence-secret-drop"></a>
### secret-drop

- **oscarhenrycollins/secret-drop**: [`690b277619847405cffc711917abafd85223f10b`](https://github.com/oscarhenrycollins/secret-drop/tree/690b277619847405cffc711917abafd85223f10b) (main); packaged variants: `main@690b27761984`.
  - network: [static/app.js:73](https://github.com/oscarhenrycollins/secret-drop/blob/690b277619847405cffc711917abafd85223f10b/static/app.js#L73) — `return window.fetch(path, settings).then((r) => r.json().catch(() => ({})).then((data) => ({ok: r.ok, data: data || {}})));`
  - origin: [server.py:462](https://github.com/oscarhenrycollins/secret-drop/blob/690b277619847405cffc711917abafd85223f10b/server.py#L462) — `"Cross-Origin-Opener-Policy": "same-origin",`
  - assets: [static/index.html:22](https://github.com/oscarhenrycollins/secret-drop/blob/690b277619847405cffc711917abafd85223f10b/static/index.html#L22) — `<form id="secret-form" autocomplete="off" hidden>`

<a id="evidence-smart-home"></a>
### smart-home

- **humanitylabs-org/smart-home**: [`81c44fd4c9cbc41a6a3c7c121b56fb2c1f2dff7d`](https://github.com/humanitylabs-org/smart-home/tree/81c44fd4c9cbc41a6a3c7c121b56fb2c1f2dff7d) (main); packaged variants: `main@81c44fd4c9cb`.
  - network: [runtipi/docker-compose.yml:1018](https://github.com/humanitylabs-org/smart-home/blob/81c44fd4c9cbc41a6a3c7c121b56fb2c1f2dff7d/runtipi/docker-compose.yml#L1018) — `const r = await fetch('api/' + path, data ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)} : {cache: 'no-store'});`
  - assets: [runtipi/docker-compose.yml:940](https://github.com/humanitylabs-org/smart-home/blob/81c44fd4c9cbc41a6a3c7c121b56fb2c1f2dff7d/runtipi/docker-compose.yml#L940) — `<footer class="sh-foot"><a id="advanced" target="_blank" rel="noopener">Other brands ↗</a><button id="showlogin" class="sh-quiet" type="button">Home Assistant sign-in</button><button id="ownoff" class="sh-quiet" type="button" hidden>Stop using my own</button><`
- **oscarhenrycollins/smart-home**: [`81c44fd4c9cbc41a6a3c7c121b56fb2c1f2dff7d`](https://github.com/oscarhenrycollins/smart-home/tree/81c44fd4c9cbc41a6a3c7c121b56fb2c1f2dff7d) (main); packaged variants: `main@81c44fd4c9cb`.
  - network: [runtipi/docker-compose.yml:1018](https://github.com/oscarhenrycollins/smart-home/blob/81c44fd4c9cbc41a6a3c7c121b56fb2c1f2dff7d/runtipi/docker-compose.yml#L1018) — `const r = await fetch('api/' + path, data ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)} : {cache: 'no-store'});`
  - assets: [runtipi/docker-compose.yml:940](https://github.com/oscarhenrycollins/smart-home/blob/81c44fd4c9cbc41a6a3c7c121b56fb2c1f2dff7d/runtipi/docker-compose.yml#L940) — `<footer class="sh-foot"><a id="advanced" target="_blank" rel="noopener">Other brands ↗</a><button id="showlogin" class="sh-quiet" type="button">Home Assistant sign-in</button><button id="ownoff" class="sh-quiet" type="button" hidden>Stop using my own</button><`

<a id="evidence-transcriber"></a>
### transcriber

- **oscarhenrycollins/transcriber**: [`b8d1170a3f97e1d6eed8abc874bdebdf7e9f21dc`](https://github.com/oscarhenrycollins/transcriber/tree/b8d1170a3f97e1d6eed8abc874bdebdf7e9f21dc) (main); packaged variants: `main@b8d1170a3f97`.
  - Package/source: [wizard.md](https://github.com/oscarhenrycollins/transcriber/blob/b8d1170a3f97e1d6eed8abc874bdebdf7e9f21dc/wizard.md). No relevant runtime hit in available wrapper source; see confidence limit in table.
  - Package/source: [runtipi/docker-compose.yml](https://github.com/oscarhenrycollins/transcriber/blob/b8d1170a3f97e1d6eed8abc874bdebdf7e9f21dc/runtipi/docker-compose.yml). No relevant runtime hit in available wrapper source; see confidence limit in table.

<a id="evidence-troubleshooter"></a>
### troubleshooter

- **humanitylabs-org/wizard-troubleshooter**: [`8d3a39f44b6afc03c6d5b10417cd146c9f14638d`](https://github.com/humanitylabs-org/wizard-troubleshooter/tree/8d3a39f44b6afc03c6d5b10417cd146c9f14638d) (main); packaged variants: `main@8d3a39f44b6a`, `release_component@3e56f66da33a`.
  - owner_routes, network: [web/index.html:267](https://github.com/humanitylabs-org/wizard-troubleshooter/blob/8d3a39f44b6afc03c6d5b10417cd146c9f14638d/web/index.html#L267) — `const r = await fetch('/wizard/v1/provider-recovery?run_id=' + encodeURIComponent(runId), { cache: 'no-store', credentials: 'same-origin' });`
  - parent: [web/index.html:417](https://github.com/humanitylabs-org/wizard-troubleshooter/blob/8d3a39f44b6afc03c6d5b10417cd146c9f14638d/web/index.html#L417) — `if (o) { try { if (o.dataset.openapp && window.parent !== window && window.parent.WizOpenApp?.(o.dataset.openapp)) { e.preventDefault(); return; } } catch (_) {} return; }`
  - storage: [web/index.html:187](https://github.com/humanitylabs-org/wizard-troubleshooter/blob/8d3a39f44b6afc03c6d5b10417cd146c9f14638d/web/index.html#L187) — `try { localStorage.setItem(CACHE, JSON.stringify({ engines, selected })); } catch {}`
  - network: [web/index.html:229](https://github.com/humanitylabs-org/wizard-troubleshooter/blob/8d3a39f44b6afc03c6d5b10417cd146c9f14638d/web/index.html#L229) — `const r = await fetch('/troubleshoot/api/' + path, { cache: 'no-store', credentials: 'same-origin', ...opts });`
  - assets: [web/index.html:118](https://github.com/humanitylabs-org/wizard-troubleshooter/blob/8d3a39f44b6afc03c6d5b10417cd146c9f14638d/web/index.html#L118) — `<a class="ts-back" id="back" href="/wizard-os-home/" aria-label="Back to Wizard">‹</a>`

<a id="evidence-wisdom"></a>
### wisdom

- **humanitylabs-org/wisdom**: [`e35a6efc0961acc2763b3a252e906b1bf217a48d`](https://github.com/humanitylabs-org/wisdom/tree/e35a6efc0961acc2763b3a252e906b1bf217a48d) (main); packaged variants: `main@e35a6efc0961`.
  - owner_routes: [server.py:92](https://github.com/humanitylabs-org/wisdom/blob/e35a6efc0961acc2763b3a252e906b1bf217a48d/server.py#L92) — `_wizard('POST', '/wizard/hermes/api/sessions', {'source': 'wizard-mobile', 'id': sid,`
  - parent, native: [static/wisdom.js:661](https://github.com/humanitylabs-org/wisdom/blob/e35a6efc0961acc2763b3a252e906b1bf217a48d/static/wisdom.js#L661) — `function buzz(){try{(window.parent!==window&&window.parent.WizardOSNative?.haptic)?window.parent.WizardOSNative.haptic(12):navigator.vibrate?.(12)}catch{}}`
  - storage: [static/discussions.js:90](https://github.com/humanitylabs-org/wisdom/blob/e35a6efc0961acc2763b3a252e906b1bf217a48d/static/discussions.js#L90) — `try { persisted = JSON.parse(localStorage.getItem(storageKey()) || '{}'); if (!persisted || typeof persisted !== 'object' || Array.isArray(persisted)) persisted = {}; }`
  - network: [static/discussions.js:111](https://github.com/humanitylabs-org/wisdom/blob/e35a6efc0961acc2763b3a252e906b1bf217a48d/static/discussions.js#L111) — `const response = await fetch(new URL('api/discussions' + path, base), {`
  - assets, origin: [static/wisdom.js:291](https://github.com/humanitylabs-org/wisdom/blob/e35a6efc0961acc2763b3a252e906b1bf217a48d/static/wisdom.js#L291) — `return ′<section class="wisdom-thinker wb-book wb-collection">${bookHero({artHtml:colArt(c,'wb-book-portrait'),kicker:′<span class="wb-form-tag">${esc(formOf(c))}</span> ${esc(c.kind||'Collection')} · by ${esc(c.by||'Wizard')}′,title:′${k?′<span>${esc(k)}</spa`
  - assets: [static/app.js:14](https://github.com/humanitylabs-org/wisdom/blob/e35a6efc0961acc2763b3a252e906b1bf217a48d/static/app.js#L14) — `$('#app').innerHTML=′<div class="w-layout"><main class="w-main" id="content">${Wisdom.render()}${!location.hash||location.hash==='#'?'<footer class="wm-library-entry"><button class="wisdom-action wz-button secondary" data-wisdom-discussions="">Discussions</but`
  - shared: [static/discussions.js:100](https://github.com/humanitylabs-org/wisdom/blob/e35a6efc0961acc2763b3a252e906b1bf217a48d/static/discussions.js#L100) — `if (unsaved && !updateHold && window.WizardApp?.update) updateHold = WizardApp.update.hold('Wisdom discussion draft or reply');`

<a id="evidence-wizard-agent-service"></a>
### wizard-agent-service

- **humanitylabs-org/wizard-agent-service**: [`aba3efa925a7ba1f11560b1732976e9ba57c0179`](https://github.com/humanitylabs-org/wizard-agent-service/tree/aba3efa925a7ba1f11560b1732976e9ba57c0179) (main); packaged variants: `main@aba3efa925a7`, `release_pin@1eaaa4f25d83`, `stable_component@9233c1997e8a`.
  - owner_routes: [server/system-jobs.mjs:273](https://github.com/humanitylabs-org/wizard-agent-service/blob/aba3efa925a7ba1f11560b1732976e9ba57c0179/server/system-jobs.mjs#L273) — `const suffix = url.pathname.slice('/wizard/v1/system-jobs'.length)`
  - network, parent, storage: [server/chats-views.mjs:11](https://github.com/humanitylabs-org/wizard-agent-service/blob/aba3efa925a7ba1f11560b1732976e9ba57c0179/server/chats-views.mjs#L11) — `const BANNED = /\b(?:addEventListener|setTimeout|setInterval|requestAnimationFrame|fetch|XMLHttpRequest|__wos|__wux|localStorage|sessionStorage|innerHTML|outerHTML|history|eval|Function|WebSocket|import)\b|document\s*\.\s*cookie/;`
  - network: [server/locked-run-bridge.mjs:83](https://github.com/humanitylabs-org/wizard-agent-service/blob/aba3efa925a7ba1f11560b1732976e9ba57c0179/server/locked-run-bridge.mjs#L83) — `async fetch(url, init = {}) {`
  - origin: [server/agents.mjs:461](https://github.com/humanitylabs-org/wizard-agent-service/blob/aba3efa925a7ba1f11560b1732976e9ba57c0179/server/agents.mjs#L461) — `const mainUpstreamOrigin = options.mainUpstreamOrigin || ''`

<a id="evidence-wizard-apple-health"></a>
### wizard-apple-health

- **oscarhenrycollins/wizard-apple-health**: [`5748e564ed72e46e8a71ea470a885a15828793ea`](https://github.com/oscarhenrycollins/wizard-apple-health/tree/5748e564ed72e46e8a71ea470a885a15828793ea) (main); packaged variants: `main@5748e564ed72`.
  - network: [web/app.js:17](https://github.com/oscarhenrycollins/wizard-apple-health/blob/5748e564ed72e46e8a71ea470a885a15828793ea/web/app.js#L17) — `const r = await fetch(path, init);`
  - origin: [app/server.py:882](https://github.com/oscarhenrycollins/wizard-apple-health/blob/5748e564ed72e46e8a71ea470a885a15828793ea/app/server.py#L882) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:42](https://github.com/oscarhenrycollins/wizard-apple-health/blob/5748e564ed72e46e8a71ea470a885a15828793ea/web/index.html#L42) — `<a class="wz-button" id="open-health" href="/wizard-health/">Open Health</a>`
  - shared: [web/app.js:225](https://github.com/oscarhenrycollins/wizard-apple-health/blob/5748e564ed72e46e8a71ea470a885a15828793ea/web/app.js#L225) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-calendar"></a>
### wizard-calendar

- **humanitylabs-org/wizard-calendar**: [`650bdd74ebe261c97c908b82e8bb3997d15d210f`](https://github.com/humanitylabs-org/wizard-calendar/tree/650bdd74ebe261c97c908b82e8bb3997d15d210f) (main); packaged variants: `main@650bdd74ebe2`.
  - storage: [web/app.js:8](https://github.com/humanitylabs-org/wizard-calendar/blob/650bdd74ebe261c97c908b82e8bb3997d15d210f/web/app.js#L8) — `let mode = MODES.includes(localStorage.getItem('wc.mode')) ? localStorage.getItem('wc.mode') : 'week';`
  - network: [web/app.js:291](https://github.com/humanitylabs-org/wizard-calendar/blob/650bdd74ebe261c97c908b82e8bb3997d15d210f/web/app.js#L291) — `const r = await fetch(new URL(path, location.href).pathname, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });`
  - origin: [app/server.py:387](https://github.com/humanitylabs-org/wizard-calendar/blob/650bdd74ebe261c97c908b82e8bb3997d15d210f/app/server.py#L387) — `if self.headers.get('Origin') and self.headers['Origin'] not in ORIGINS:`
  - assets: [web/app.js:267](https://github.com/humanitylabs-org/wizard-calendar/blob/650bdd74ebe261c97c908b82e8bb3997d15d210f/web/app.js#L267) — `<div class="acts">${e.meet ? ′<a href="${esc(e.meet)}" target="_blank" rel="noopener">Join Meet</a>′ : ''}${maps ? ′<a href="${esc(maps)}" target="_blank" rel="noopener">Map</a>′ : ''}${e.link ? ′<a href="${esc(e.link)}" target="_blank" rel="noopener">Open in `
  - shared: [web/app.js:269](https://github.com/humanitylabs-org/wizard-calendar/blob/650bdd74ebe261c97c908b82e8bb3997d15d210f/web/app.js#L269) — `if (!sheetOpen) { sheetOpen = true; sheetBack = WizardApp.back.push(() => { closeSheet(); return true; }); }`

<a id="evidence-wizard-chatgpt"></a>
### wizard-chatgpt

- **humanitylabs-org/chatgpt-connection**: [`1d2969516fa25b6b800356bd25044bea47b4a128`](https://github.com/humanitylabs-org/chatgpt-connection/tree/1d2969516fa25b6b800356bd25044bea47b4a128) (main); packaged variants: `main@1d2969516fa2`.
  - parent: [static/appearance.js:30](https://github.com/humanitylabs-org/chatgpt-connection/blob/1d2969516fa25b6b800356bd25044bea47b4a128/static/appearance.js#L30) — `if (parent.location.origin === origin) {`
  - network: [static/app.js:15](https://github.com/humanitylabs-org/chatgpt-connection/blob/1d2969516fa25b6b800356bd25044bea47b4a128/static/app.js#L15) — `try { res = await fetch(path, {`
  - origin: [server.py:552](https://github.com/humanitylabs-org/chatgpt-connection/blob/1d2969516fa25b6b800356bd25044bea47b4a128/server.py#L552) — `origin = self.headers.get("Origin")`
  - assets: [static/index.html:31](https://github.com/humanitylabs-org/chatgpt-connection/blob/1d2969516fa25b6b800356bd25044bea47b4a128/static/index.html#L31) — `<a id="login-url" class="primary login-link" href="#" target="_blank" rel="noopener noreferrer">Open ChatGPT sign-in <span aria-hidden="true">↗</span></a>`
  - shared: [static/appearance.js:19](https://github.com/humanitylabs-org/chatgpt-connection/blob/1d2969516fa25b6b800356bd25044bea47b4a128/static/appearance.js#L19) — `if (e.source !== parent || e.origin !== origin || e.data?.type !== 'wizard:appearance' ||`
- **oscarhenrycollins/chatgpt-connection**: [`bc6a1df93300e75f751c8507d344b7709950dce2`](https://github.com/oscarhenrycollins/chatgpt-connection/tree/bc6a1df93300e75f751c8507d344b7709950dce2) (main); packaged variants: `main@bc6a1df93300`, `release_pin@37c3bc8924fe`.
  - network: [static/app.js:14](https://github.com/oscarhenrycollins/chatgpt-connection/blob/bc6a1df93300e75f751c8507d344b7709950dce2/static/app.js#L14) — `const res = await fetch(path, {`
  - origin: [server.py:431](https://github.com/oscarhenrycollins/chatgpt-connection/blob/bc6a1df93300e75f751c8507d344b7709950dce2/server.py#L431) — `origin = self.headers.get("Origin")`
  - assets: [static/index.html:19](https://github.com/oscarhenrycollins/chatgpt-connection/blob/bc6a1df93300e75f751c8507d344b7709950dce2/static/index.html#L19) — `<li><a id="login-url" href="#" target="_blank" rel="noopener noreferrer">Open the ChatGPT sign-in page</a> on your phone or computer and sign in.</li>`

<a id="evidence-wizard-claude"></a>
### wizard-claude

- **humanitylabs-org/claude-connection**: [`0da65a4ae26b21a8fe95ff149be998759aa89501`](https://github.com/humanitylabs-org/claude-connection/tree/0da65a4ae26b21a8fe95ff149be998759aa89501) (main); packaged variants: `main@0da65a4ae26b`.
  - owner_routes: [usage.py:10](https://github.com/humanitylabs-org/claude-connection/blob/0da65a4ae26b21a8fe95ff149be998759aa89501/usage.py#L10) — `are exactly what ′GET /wizard/ai-usage′ already returns and the shell needs no change.`
  - parent: [static/appearance.js:30](https://github.com/humanitylabs-org/claude-connection/blob/0da65a4ae26b21a8fe95ff149be998759aa89501/static/appearance.js#L30) — `if (parent.location.origin === origin) {`
  - network: [static/app.js:13](https://github.com/humanitylabs-org/claude-connection/blob/0da65a4ae26b21a8fe95ff149be998759aa89501/static/app.js#L13) — `const res = await fetch(path, {`
  - origin: [server.py:436](https://github.com/humanitylabs-org/claude-connection/blob/0da65a4ae26b21a8fe95ff149be998759aa89501/server.py#L436) — `origin = self.headers.get("Origin")`
  - assets: [static/index.html:21](https://github.com/humanitylabs-org/claude-connection/blob/0da65a4ae26b21a8fe95ff149be998759aa89501/static/index.html#L21) — `<li><a id="login-url" href="#" target="_blank" rel="noopener noreferrer">Open the Claude sign-in page</a> on your phone or computer and sign in.</li>`
  - shared: [static/appearance.js:19](https://github.com/humanitylabs-org/claude-connection/blob/0da65a4ae26b21a8fe95ff149be998759aa89501/static/appearance.js#L19) — `if (e.source !== parent || e.origin !== origin || e.data?.type !== 'wizard:appearance' ||`
- **oscarhenrycollins/claude-connection**: [`ddf7524601fd121f2e425b6845e78d75aefe05ef`](https://github.com/oscarhenrycollins/claude-connection/tree/ddf7524601fd121f2e425b6845e78d75aefe05ef) (main); packaged variants: `main@ddf7524601fd`, `release_pin@2e58656b9776`.
  - owner_routes: [usage.py:10](https://github.com/oscarhenrycollins/claude-connection/blob/ddf7524601fd121f2e425b6845e78d75aefe05ef/usage.py#L10) — `are exactly what ′GET /wizard/ai-usage′ already returns and the shell needs no change.`
  - network: [static/app.js:13](https://github.com/oscarhenrycollins/claude-connection/blob/ddf7524601fd121f2e425b6845e78d75aefe05ef/static/app.js#L13) — `const res = await fetch(path, {`
  - origin: [server.py:413](https://github.com/oscarhenrycollins/claude-connection/blob/ddf7524601fd121f2e425b6845e78d75aefe05ef/server.py#L413) — `origin = self.headers.get("Origin")`
  - assets: [static/index.html:19](https://github.com/oscarhenrycollins/claude-connection/blob/ddf7524601fd121f2e425b6845e78d75aefe05ef/static/index.html#L19) — `<li><a id="login-url" href="#" target="_blank" rel="noopener noreferrer">Open the Claude sign-in page</a> on your phone or computer and sign in.</li>`

<a id="evidence-wizard-cloudflare"></a>
### wizard-cloudflare

- **oscarhenrycollins/wizard-cloudflare**: [`67b3b33951fa488148c0eb91a9154ee1ce93fe39`](https://github.com/oscarhenrycollins/wizard-cloudflare/tree/67b3b33951fa488148c0eb91a9154ee1ce93fe39) (main); packaged variants: `main@67b3b33951fa`.
  - network: [web/app.js:21](https://github.com/oscarhenrycollins/wizard-cloudflare/blob/67b3b33951fa488148c0eb91a9154ee1ce93fe39/web/app.js#L21) — `const r = await fetch(path, init); let v = {}; try { v = await r.json(); } catch (_) {}`
  - origin: [app/server.py:975](https://github.com/oscarhenrycollins/wizard-cloudflare/blob/67b3b33951fa488148c0eb91a9154ee1ce93fe39/app/server.py#L975) — `origin=(self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:11](https://github.com/oscarhenrycollins/wizard-cloudflare/blob/67b3b33951fa488148c0eb91a9154ee1ce93fe39/web/index.html#L11) — `<p class="cf-hint" id="new-hint">No account? <a href="https://dash.cloudflare.com/sign-up" target="_blank" rel="noopener noreferrer">Sign up free</a></p>`
  - shared: [web/app.js:159](https://github.com/oscarhenrycollins/wizard-cloudflare/blob/67b3b33951fa488148c0eb91a9154ee1ce93fe39/web/app.js#L159) — `try { if (window.WizardApp?.chat?.prompt) shared = await window.WizardApp.chat.prompt(text) === true; } catch (_) {}`

<a id="evidence-wizard-connection-router"></a>
### wizard-connection-router

- **humanitylabs-org/wizard-connection-router**: [`ec8ca140494b302a9d4e651417162b89f1d9e282`](https://github.com/humanitylabs-org/wizard-connection-router/tree/ec8ca140494b302a9d4e651417162b89f1d9e282) (main); packaged variants: `main@ec8ca140494b`, `release_pin@f46a867207de`.
  - parent: [static/appearance.js:30](https://github.com/humanitylabs-org/wizard-connection-router/blob/ec8ca140494b302a9d4e651417162b89f1d9e282/static/appearance.js#L30) — `if (parent.location.origin === origin) {`
  - shared: [static/appearance.js:19](https://github.com/humanitylabs-org/wizard-connection-router/blob/ec8ca140494b302a9d4e651417162b89f1d9e282/static/appearance.js#L19) — `if (e.source !== parent || e.origin !== origin || e.data?.type !== 'wizard:appearance' ||`

<a id="evidence-wizard-coros"></a>
### wizard-coros

- **oscarhenrycollins/wizard-coros**: [`5aeb75e044fc0fff13f23c3df2dbcc6f800d3782`](https://github.com/oscarhenrycollins/wizard-coros/tree/5aeb75e044fc0fff13f23c3df2dbcc6f800d3782) (main); packaged variants: `main@5aeb75e044fc`.
  - network: [web/app.js:17](https://github.com/oscarhenrycollins/wizard-coros/blob/5aeb75e044fc0fff13f23c3df2dbcc6f800d3782/web/app.js#L17) — `const r = await fetch(path, init);`
  - origin: [app/server.py:1241](https://github.com/oscarhenrycollins/wizard-coros/blob/5aeb75e044fc0fff13f23c3df2dbcc6f800d3782/app/server.py#L1241) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:42](https://github.com/oscarhenrycollins/wizard-coros/blob/5aeb75e044fc0fff13f23c3df2dbcc6f800d3782/web/index.html#L42) — `<a class="wz-button secondary" id="open-health" href="/wizard-health/">Open Health</a>`
  - shared: [web/app.js:175](https://github.com/oscarhenrycollins/wizard-coros/blob/5aeb75e044fc0fff13f23c3df2dbcc6f800d3782/web/app.js#L175) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-files"></a>
### wizard-files

- **humanitylabs-org/wizard-files**: [`a635669a02bfb577663bcb80066867db3b1ceeed`](https://github.com/humanitylabs-org/wizard-files/tree/a635669a02bfb577663bcb80066867db3b1ceeed) (main); packaged variants: `main@a635669a02bf`.
  - owner_routes: [my-files.js:4](https://github.com/humanitylabs-org/wizard-files/blob/a635669a02bfb577663bcb80066867db3b1ceeed/my-files.js#L4) — `* Upload: the same resumable path as chat attachments and the share sheet (/wizard/v1/uploads), with`
  - storage: [media-gallery.js:8](https://github.com/humanitylabs-org/wizard-files/blob/a635669a02bfb577663bcb80066867db3b1ceeed/media-gallery.js#L8) — `function database(){return dbPromise ||= new Promise(resolve=>{let request,done=false;const finish=db=>{if(done){db?.close();return;}done=true;clearTimeout(timer);resolve(db);};const timer=setTimeout(()=>finish(null),1500);try{request=indexedDB.open('wizard-fi`
  - network: [media-gallery.js:15](https://github.com/humanitylabs-org/wizard-files/blob/a635669a02bfb577663bcb80066867db3b1ceeed/media-gallery.js#L15) — `const response=await fetch(urlFor(item),{signal:controller.signal,credentials:'same-origin',priority:'low'});`
  - origin: [server.py:185](https://github.com/humanitylabs-org/wizard-files/blob/a635669a02bfb577663bcb80066867db3b1ceeed/server.py#L185) — `origin = self.headers.get('Origin')`
  - assets: [media-gallery.js:19](https://github.com/humanitylabs-org/wizard-files/blob/a635669a02bfb577663bcb80066867db3b1ceeed/media-gallery.js#L19) — `const img=new Image();img.src=url;await img.decode();return {url,width:img.naturalWidth,height:img.naturalHeight};`
  - shared: [app.js:15](https://github.com/humanitylabs-org/wizard-files/blob/a635669a02bfb577663bcb80066867db3b1ceeed/app.js#L15) — `WizardApp.ready({name:'wizard-files',version:'0.1.4'});`

<a id="evidence-wizard-fitbit"></a>
### wizard-fitbit

- **oscarhenrycollins/wizard-fitbit**: [`1d774cae80e337ee09d29c470387d892ba0289bf`](https://github.com/oscarhenrycollins/wizard-fitbit/tree/1d774cae80e337ee09d29c470387d892ba0289bf) (main); packaged variants: `main@1d774cae80e3`.
  - network: [web/app.js:15](https://github.com/oscarhenrycollins/wizard-fitbit/blob/1d774cae80e337ee09d29c470387d892ba0289bf/web/app.js#L15) — `const r = await fetch(path, init);`
  - origin: [app/server.py:1136](https://github.com/oscarhenrycollins/wizard-fitbit/blob/1d774cae80e337ee09d29c470387d892ba0289bf/app/server.py#L1136) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:45](https://github.com/oscarhenrycollins/wizard-fitbit/blob/1d774cae80e337ee09d29c470387d892ba0289bf/web/index.html#L45) — `<a class="wz-button secondary" id="open-health" href="/wizard-health/">Open Health</a>`
  - shared: [web/app.js:297](https://github.com/oscarhenrycollins/wizard-fitbit/blob/1d774cae80e337ee09d29c470387d892ba0289bf/web/app.js#L297) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-garmin"></a>
### wizard-garmin

- **oscarhenrycollins/wizard-garmin**: [`c2d80c1afecc18a96ed1e854e1fa5127367348a6`](https://github.com/oscarhenrycollins/wizard-garmin/tree/c2d80c1afecc18a96ed1e854e1fa5127367348a6) (main); packaged variants: `main@c2d80c1afecc`.
  - network: [web/app.js:17](https://github.com/oscarhenrycollins/wizard-garmin/blob/c2d80c1afecc18a96ed1e854e1fa5127367348a6/web/app.js#L17) — `const r = await fetch(path, init);`
  - origin: [app/server.py:1021](https://github.com/oscarhenrycollins/wizard-garmin/blob/c2d80c1afecc18a96ed1e854e1fa5127367348a6/app/server.py#L1021) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:44](https://github.com/oscarhenrycollins/wizard-garmin/blob/c2d80c1afecc18a96ed1e854e1fa5127367348a6/web/index.html#L44) — `<a class="wz-button secondary" id="open-health" href="/wizard-health/">Open Health</a>`
  - shared: [web/app.js:211](https://github.com/oscarhenrycollins/wizard-garmin/blob/c2d80c1afecc18a96ed1e854e1fa5127367348a6/web/app.js#L211) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-google"></a>
### wizard-google

- **humanitylabs-org/wizard-google**: [`209a6ff38b29bd2d213841b99c47141264b2fb8f`](https://github.com/humanitylabs-org/wizard-google/tree/209a6ff38b29bd2d213841b99c47141264b2fb8f) (catalogue_pin); packaged variants: `catalogue_pin@209a6ff38b29`.
  - network: [web/app.js:56](https://github.com/humanitylabs-org/wizard-google/blob/209a6ff38b29bd2d213841b99c47141264b2fb8f/web/app.js#L56) — `const r = await fetch(path, init);`
  - origin: [app/server.py:278](https://github.com/humanitylabs-org/wizard-google/blob/209a6ff38b29bd2d213841b99c47141264b2fb8f/app/server.py#L278) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/app.js:359](https://github.com/humanitylabs-org/wizard-google/blob/209a6ff38b29bd2d213841b99c47141264b2fb8f/web/app.js#L359) — `const tab = window.open('', '_blank');`
  - shared: [web/sheet.js:4](https://github.com/humanitylabs-org/wizard-google/blob/209a6ff38b29bd2d213841b99c47141264b2fb8f/web/sheet.js#L4) — `* and a downward swipe on the grip. Back: in an app that uses WizardApp, each open sheet is pushed on WizardApp.back`

<a id="evidence-wizard-health"></a>
### wizard-health

- **oscarhenrycollins/wizard-health**: [`3598c1c81aef03ad0f9e90ea619df441eeacb44b`](https://github.com/oscarhenrycollins/wizard-health/tree/3598c1c81aef03ad0f9e90ea619df441eeacb44b) (main); packaged variants: `main@3598c1c81aef`.
  - storage: [web/app.js:496](https://github.com/oscarhenrycollins/wizard-health/blob/3598c1c81aef03ad0f9e90ea619df441eeacb44b/web/app.js#L496) — `try { localStorage.setItem(PREF, m); } catch (e) {}`
  - network: [web/app.js:24](https://github.com/oscarhenrycollins/wizard-health/blob/3598c1c81aef03ad0f9e90ea619df441eeacb44b/web/app.js#L24) — `const r = await fetch(path, init);`
  - origin: [app/server.py:1111](https://github.com/oscarhenrycollins/wizard-health/blob/3598c1c81aef03ad0f9e90ea619df441eeacb44b/app/server.py#L1111) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:25](https://github.com/oscarhenrycollins/wizard-health/blob/3598c1c81aef03ad0f9e90ea619df441eeacb44b/web/index.html#L25) — `<a class="hl-connect" id="connect" href="#">`
  - shared: [web/app.js:645](https://github.com/oscarhenrycollins/wizard-health/blob/3598c1c81aef03ad0f9e90ea619df441eeacb44b/web/app.js#L645) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-mail"></a>
### wizard-mail

- **oscarhenrycollins/wizard-mail**: [`c818d4c85cb75096742bd5375a46d4d0018302a0`](https://github.com/oscarhenrycollins/wizard-mail/tree/c818d4c85cb75096742bd5375a46d4d0018302a0) (main); packaged variants: `main@c818d4c85cb7`.
  - parent: [web/app.js:325](https://github.com/oscarhenrycollins/wizard-mail/blob/c818d4c85cb75096742bd5375a46d4d0018302a0/web/app.js#L325) — `const doc = frame.contentDocument;`
  - storage: [web/app.js:54](https://github.com/oscarhenrycollins/wizard-mail/blob/c818d4c85cb75096742bd5375a46d4d0018302a0/web/app.js#L54) — `function previewsOn() { try { return localStorage.getItem(PREVIEWS) === '1'; } catch (_) { return false; } }`
  - network: [web/app.js:32](https://github.com/oscarhenrycollins/wizard-mail/blob/c818d4c85cb75096742bd5375a46d4d0018302a0/web/app.js#L32) — `const r = await fetch(path, { credentials: 'same-origin', ...init });`
  - origin: [app/server.py:198](https://github.com/oscarhenrycollins/wizard-mail/blob/c818d4c85cb75096742bd5375a46d4d0018302a0/app/server.py#L198) — `# A custom header and JSON make every API call a CORS-preflighted request that this app never allows.`
  - assets: [web/index.html:37](https://github.com/oscarhenrycollins/wizard-mail/blob/c818d4c85cb75096742bd5375a46d4d0018302a0/web/index.html#L37) — `<form class="wm-search" role="search" autocomplete="off">`
  - shared: [web/app.js:63](https://github.com/oscarhenrycollins/wizard-mail/blob/c818d4c85cb75096742bd5375a46d4d0018302a0/web/app.js#L63) — `if (window.WizardApp && window.WizardApp.version === 1) {`

<a id="evidence-wizard-manager"></a>
### wizard-manager

- **humanitylabs-org/wizard-manager**: [`716d3af6d86e6194005cf21cbd4bb3984991f57d`](https://github.com/humanitylabs-org/wizard-manager/tree/716d3af6d86e6194005cf21cbd4bb3984991f57d) (main); packaged variants: `main@716d3af6d86e`.
  - owner_routes: [app/manager.py:55](https://github.com/humanitylabs-org/wizard-manager/blob/716d3af6d86e6194005cf21cbd4bb3984991f57d/app/manager.py#L55) — `self.was = (was or os.environ.get('MANAGER_WAS_URL', 'http://127.0.0.1:8923/wizard/hermes')).rstrip('/')`
  - storage: [web/app.js:72](https://github.com/humanitylabs-org/wizard-manager/blob/716d3af6d86e6194005cf21cbd4bb3984991f57d/web/app.js#L72) — `const raw = localStorage.getItem(KEY);`
  - network: [web/app.js:326](https://github.com/humanitylabs-org/wizard-manager/blob/716d3af6d86e6194005cf21cbd4bb3984991f57d/web/app.js#L326) — `const r = await fetch(path, { signal: controller.signal, cache: 'no-store', ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });`
  - origin: [app/server.py:58](https://github.com/humanitylabs-org/wizard-manager/blob/716d3af6d86e6194005cf21cbd4bb3984991f57d/app/server.py#L58) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:28](https://github.com/humanitylabs-org/wizard-manager/blob/716d3af6d86e6194005cf21cbd4bb3984991f57d/web/index.html#L28) — `<form id="compose" class="wz-compose mgr-dock" autocomplete="off">`

<a id="evidence-wizard-microsoft"></a>
### wizard-microsoft

- **oscarhenrycollins/wizard-microsoft**: [`343c8dd84cf48500c83e1509513ee04cec0a06be`](https://github.com/oscarhenrycollins/wizard-microsoft/tree/343c8dd84cf48500c83e1509513ee04cec0a06be) (main); packaged variants: `main@343c8dd84cf4`.
  - network: [web/signin.js:20](https://github.com/oscarhenrycollins/wizard-microsoft/blob/343c8dd84cf48500c83e1509513ee04cec0a06be/web/signin.js#L20) — `const r = await fetch('../../api/quick/flow?flow=' + encodeURIComponent(flow), { credentials: 'same-origin', cache: 'no-store' });`
  - origin: [app/server.py:277](https://github.com/oscarhenrycollins/wizard-microsoft/blob/343c8dd84cf48500c83e1509513ee04cec0a06be/app/server.py#L277) — `origin = (self.headers.get('Origin') or '').lower().rstrip('/')`
  - assets: [web/signin.js:11](https://github.com/oscarhenrycollins/wizard-microsoft/blob/343c8dd84cf48500c83e1509513ee04cec0a06be/web/signin.js#L11) — `win = window.open(target, 'composio-signin', 'popup,width=520,height=760');`
  - shared: [web/app.js:68](https://github.com/oscarhenrycollins/wizard-microsoft/blob/343c8dd84cf48500c83e1509513ee04cec0a06be/web/app.js#L68) — `WizardApp.ready({ name: 'wizard-microsoft', version: '0.2.5' });`

<a id="evidence-wizard-monarch"></a>
### wizard-monarch

- **oscarhenrycollins/wizard-monarch**: [`3db12032a186de123cf6e38544e3a2d66d67f13f`](https://github.com/oscarhenrycollins/wizard-monarch/tree/3db12032a186de123cf6e38544e3a2d66d67f13f) (main); packaged variants: `main@3db12032a186`.
  - network: [web/app.js:10](https://github.com/oscarhenrycollins/wizard-monarch/blob/3db12032a186de123cf6e38544e3a2d66d67f13f/web/app.js#L10) — `const r = await fetch(path, init);`
  - origin: [app/server.py:926](https://github.com/oscarhenrycollins/wizard-monarch/blob/3db12032a186de123cf6e38544e3a2d66d67f13f/app/server.py#L926) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:39](https://github.com/oscarhenrycollins/wizard-monarch/blob/3db12032a186de123cf6e38544e3a2d66d67f13f/web/index.html#L39) — `<p>Monarch opens in a new tab. Sign in, approve the data notice, choose <b>Read</b> access and tap <b>Allow</b>. New to Monarch? <a href="https://www.monarch.com/" target="_blank" rel="noopener noreferrer">Create a Monarch account</a> first; a Monarch subscrip`
  - shared: [web/theme-client.js:31](https://github.com/oscarhenrycollins/wizard-monarch/blob/3db12032a186de123cf6e38544e3a2d66d67f13f/web/theme-client.js#L31) — `if (parent===window || e.source!==parent || e.origin!==trustedHost || e.data?.type!=='wizard:appearance') return;`

<a id="evidence-wizard-music"></a>
### wizard-music

- **humanitylabs-org/wizard-music**: [`073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38`](https://github.com/humanitylabs-org/wizard-music/tree/073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38) (catalogue_pin); packaged variants: `catalogue_pin@073100ae6cd6`.
  - owner_routes: [server/music.mjs:6](https://github.com/humanitylabs-org/wizard-music/blob/073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38/server/music.mjs#L6) — `// The hub speaks in /wizard/music/... paths; API responses are rewritten to this`
  - parent: [src/music/backgroundAudio.ts:7](https://github.com/humanitylabs-org/wizard-music/blob/073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38/src/music/backgroundAudio.ts#L7) — `if (window.parent === window || window.parent.location.origin !== location.origin) return undefined`
  - storage: [src/music/MusicApp.tsx:529](https://github.com/humanitylabs-org/wizard-music/blob/073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38/src/music/MusicApp.tsx#L529) — `const [showPlayed, setShowPlayedState] = useState(() => { try { return localStorage.getItem(SHOW_PLAYED_KEY) === '1' } catch { return false } })`
  - network: [src/main.tsx:30](https://github.com/humanitylabs-org/wizard-music/blob/073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38/src/main.tsx#L30) — `const page = await fetch(new URL('../', BUILD_SCRIPT), { cache: 'no-store', credentials: 'include' })`
  - origin: [server/request-policy.mjs:16](https://github.com/humanitylabs-org/wizard-music/blob/073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38/server/request-policy.mjs#L16) — `// Read/navigation and box-only MCP do not send Origin. JSON is still required for writes.`
  - assets: [src/music/MusicApp.tsx:287](https://github.com/humanitylabs-org/wizard-music/blob/073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38/src/music/MusicApp.tsx#L287) — `<form className="music-search" role="search" onSubmit={(event) => { event.preventDefault(); void runSearch(query) }}>`
  - shared: [src/main.tsx:144](https://github.com/humanitylabs-org/wizard-music/blob/073100ae6cd6f72a4f04b6f1cbbe8b5570a8aa38/src/main.tsx#L144) — `window.WizardApp.ready({ name: 'Music', version: '1' })`

<a id="evidence-wizard-notes"></a>
### wizard-notes

- **humanitylabs-org/wizard-notes**: [`0dddee6f4d086ce45656dd965a53fcc833415609`](https://github.com/humanitylabs-org/wizard-notes/tree/0dddee6f4d086ce45656dd965a53fcc833415609) (main); packaged variants: `main@0dddee6f4d08`.
  - storage: [web/app.js:8](https://github.com/humanitylabs-org/wizard-notes/blob/0dddee6f4d086ce45656dd965a53fcc833415609/web/app.js#L8) — `const stored=(key,fallback)=>{try{return JSON.parse(localStorage.getItem(key)||'null')??fallback;}catch{return fallback;}};`
  - network: [web/app.js:30](https://github.com/humanitylabs-org/wizard-notes/blob/0dddee6f4d086ce45656dd965a53fcc833415609/web/app.js#L30) — `async function api(route,body,method='POST',keepalive=false){let r;try{r=await fetch('api/'+route,{method:body===undefined?'GET':method,headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),keepali`
  - origin: [web/app.js:84](https://github.com/humanitylabs-org/wizard-notes/blob/0dddee6f4d086ce45656dd965a53fcc833415609/web/app.js#L84) — `async function resolveConflict(n){const body=sheet('Note changed elsewhere');body.append(el('p','Your local text is safe. Keep both versions by saving your draft as a new note, or cancel and reconcile before retrying.'));try{const latest=await api('note?path='`

<a id="evidence-wizard-oura"></a>
### wizard-oura

- **oscarhenrycollins/wizard-oura**: [`5b6366646c4d0f2fb4041310b0a6cfc9e18d63ce`](https://github.com/oscarhenrycollins/wizard-oura/tree/5b6366646c4d0f2fb4041310b0a6cfc9e18d63ce) (main); packaged variants: `main@5b6366646c4d`.
  - network: [web/app.js:15](https://github.com/oscarhenrycollins/wizard-oura/blob/5b6366646c4d0f2fb4041310b0a6cfc9e18d63ce/web/app.js#L15) — `const r = await fetch(path, init);`
  - origin: [app/server.py:1007](https://github.com/oscarhenrycollins/wizard-oura/blob/5b6366646c4d0f2fb4041310b0a6cfc9e18d63ce/app/server.py#L1007) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:45](https://github.com/oscarhenrycollins/wizard-oura/blob/5b6366646c4d0f2fb4041310b0a6cfc9e18d63ce/web/index.html#L45) — `<a class="wz-button secondary" id="open-health" href="/wizard-health/">Open Health</a>`
  - shared: [web/app.js:294](https://github.com/oscarhenrycollins/wizard-oura/blob/5b6366646c4d0f2fb4041310b0a6cfc9e18d63ce/web/app.js#L294) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-podcasts"></a>
### wizard-podcasts

- **humanitylabs-org/wizard-podcasts**: [`55ebac0941cb8dac3f4e0f6b399f07f07e59637f`](https://github.com/humanitylabs-org/wizard-podcasts/tree/55ebac0941cb8dac3f4e0f6b399f07f07e59637f) (main); packaged variants: `main@55ebac0941cb`.
  - storage: [web/app.js:384](https://github.com/humanitylabs-org/wizard-podcasts/blob/55ebac0941cb8dac3f4e0f6b399f07f07e59637f/web/app.js#L384) — `const f = JSON.parse(localStorage.getItem(FILTER_KEY) || '{}');`
  - network: [web/app.js:32](https://github.com/humanitylabs-org/wizard-podcasts/blob/55ebac0941cb8dac3f4e0f6b399f07f07e59637f/web/app.js#L32) — `const res = await fetch(path, init);`
  - origin: [app/server.py:181](https://github.com/humanitylabs-org/wizard-podcasts/blob/55ebac0941cb8dac3f4e0f6b399f07f07e59637f/app/server.py#L181) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:43](https://github.com/humanitylabs-org/wizard-podcasts/blob/55ebac0941cb8dac3f4e0f6b399f07f07e59637f/web/index.html#L43) — `<form id="search-form" class="pc-search" autocomplete="off" role="search">`
  - shared: [web/app.js:10](https://github.com/humanitylabs-org/wizard-podcasts/blob/55ebac0941cb8dac3f4e0f6b399f07f07e59637f/web/app.js#L10) — `const W = window.WizardApp && window.WizardApp.version === 1 ? window.WizardApp : null;`

<a id="evidence-wizard-polar"></a>
### wizard-polar

- **oscarhenrycollins/wizard-polar**: [`8e0d04dbef0ea485dc8be33b6a160100b1af6d6e`](https://github.com/oscarhenrycollins/wizard-polar/tree/8e0d04dbef0ea485dc8be33b6a160100b1af6d6e) (main); packaged variants: `main@8e0d04dbef0e`.
  - network: [web/app.js:17](https://github.com/oscarhenrycollins/wizard-polar/blob/8e0d04dbef0ea485dc8be33b6a160100b1af6d6e/web/app.js#L17) — `const r = await fetch(path, init);`
  - origin: [app/server.py:1016](https://github.com/oscarhenrycollins/wizard-polar/blob/8e0d04dbef0ea485dc8be33b6a160100b1af6d6e/app/server.py#L1016) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:43](https://github.com/oscarhenrycollins/wizard-polar/blob/8e0d04dbef0ea485dc8be33b6a160100b1af6d6e/web/index.html#L43) — `<a class="wz-button secondary" id="open-health" href="/wizard-health/">Open Health</a>`
  - shared: [web/app.js:300](https://github.com/oscarhenrycollins/wizard-polar/blob/8e0d04dbef0ea485dc8be33b6a160100b1af6d6e/web/app.js#L300) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-search"></a>
### wizard-search

- **humanitylabs-org/wizard-search**: [`b137b5ee2452443c7d1bc98777a6f259f30f2be5`](https://github.com/humanitylabs-org/wizard-search/tree/b137b5ee2452443c7d1bc98777a6f259f30f2be5) (catalogue_pin); packaged variants: `catalogue_pin@b137b5ee2452`.
  - storage: [web/voice-input.js:11](https://github.com/humanitylabs-org/wizard-search/blob/b137b5ee2452443c7d1bc98777a6f259f30f2be5/web/voice-input.js#L11) — `const request = indexedDB.open('wizard-search-voice:' + scope, 1);`
  - network: [web/app.js:7](https://github.com/humanitylabs-org/wizard-search/blob/b137b5ee2452443c7d1bc98777a6f259f30f2be5/web/app.js#L7) — `const api = (p, q) => fetch(′${BASE}api/${p}?q=${encodeURIComponent(q)}′, { credentials: 'same-origin' }).then(r => r.ok ? r.json() : r.json().then(j => Promise.reject(new Error(j.error || r.status))));`
  - origin: [web/voice-input.js:14](https://github.com/humanitylabs-org/wizard-search/blob/b137b5ee2452443c7d1bc98777a6f259f30f2be5/web/voice-input.js#L14) — `request.onerror = () => reject(new Error('Voice query could not be saved. Original input kept.'));`
  - assets: [web/index.html:19](https://github.com/humanitylabs-org/wizard-search/blob/b137b5ee2452443c7d1bc98777a6f259f30f2be5/web/index.html#L19) — `<form id="f" class="bar" autocomplete="off" role="search">`
  - shared: [web/voice-input.js:108](https://github.com/humanitylabs-org/wizard-search/blob/b137b5ee2452443c7d1bc98777a6f259f30f2be5/web/voice-input.js#L108) — `WizardApp.voiceInput.register({ snapshot, receive: async (message, authorize) => {`

<a id="evidence-wizard-simplefin"></a>
### wizard-simplefin

- **oscarhenrycollins/wizard-simplefin**: [`79c20fdb753e099b071a87975bc799588b6cf42b`](https://github.com/oscarhenrycollins/wizard-simplefin/tree/79c20fdb753e099b071a87975bc799588b6cf42b) (main); packaged variants: `main@79c20fdb753e`.
  - storage: [web/app.js:6](https://github.com/oscarhenrycollins/wizard-simplefin/blob/79c20fdb753e099b071a87975bc799588b6cf42b/web/app.js#L6) — `let st = null, step = Number(sessionStorage.getItem('sf-step') || 1), poll = null, confirming = false;`
  - network: [web/app.js:11](https://github.com/oscarhenrycollins/wizard-simplefin/blob/79c20fdb753e099b071a87975bc799588b6cf42b/web/app.js#L11) — `const r = await fetch(path, init);`
  - origin: [app/server.py:475](https://github.com/oscarhenrycollins/wizard-simplefin/blob/79c20fdb753e099b071a87975bc799588b6cf42b/app/server.py#L475) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:34](https://github.com/oscarhenrycollins/wizard-simplefin/blob/79c20fdb753e099b071a87975bc799588b6cf42b/web/index.html#L34) — `<div class="sf-row-btns"><a class="wz-button secondary" href="https://beta-bridge.simplefin.org/" target="_blank" rel="noopener noreferrer">Open SimpleFIN ↗</a>`
  - shared: [web/theme-client.js:31](https://github.com/oscarhenrycollins/wizard-simplefin/blob/79c20fdb753e099b071a87975bc799588b6cf42b/web/theme-client.js#L31) — `if (parent===window || e.source!==parent || e.origin!==trustedHost || e.data?.type!=='wizard:appearance') return;`

<a id="evidence-wizard-tinfoil"></a>
### wizard-tinfoil

- **humanitylabs-org/wizard-tinfoil**: [`d1bc51ede2a3c6a9eca61554b4ed15364a3f7dda`](https://github.com/humanitylabs-org/wizard-tinfoil/tree/d1bc51ede2a3c6a9eca61554b4ed15364a3f7dda) (main); packaged variants: `main@d1bc51ede2a3`.
  - network: [web/app.js:16](https://github.com/humanitylabs-org/wizard-tinfoil/blob/d1bc51ede2a3c6a9eca61554b4ed15364a3f7dda/web/app.js#L16) — `async function request(path,body){const r=await fetch(path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json','X-Wizard-Request':'1'},body:JSON.stringify(body)});const s=await r.json();if(!r.ok)throw Error(s.error||'C`
  - origin: [app/server.py:205](https://github.com/humanitylabs-org/wizard-tinfoil/blob/d1bc51ede2a3c6a9eca61554b4ed15364a3f7dda/app/server.py#L205) — `origin=self.headers.get('Origin','').lower()`
  - assets: [web/index.html:6](https://github.com/humanitylabs-org/wizard-tinfoil/blob/d1bc51ede2a3c6a9eca61554b4ed15364a3f7dda/web/index.html#L6) — `<form data-form autocomplete="off" hidden><input class="wz-input" type="password" autocomplete="new-password" spellcheck="false" autocapitalize="none" minlength="16" maxlength="512" required placeholder="Paste API key (tk_…)" aria-label="API key"><div class="a`
  - shared: [web/theme-client.js:31](https://github.com/humanitylabs-org/wizard-tinfoil/blob/d1bc51ede2a3c6a9eca61554b4ed15364a3f7dda/web/theme-client.js#L31) — `if (parent===window || e.source!==parent || e.origin!==trustedHost || e.data?.type!=='wizard:appearance') return;`
- **oscarhenrycollins/wizard-tinfoil**: [`f1fdb7f9dea070109bca18cab56ee4d140bf28ac`](https://github.com/oscarhenrycollins/wizard-tinfoil/tree/f1fdb7f9dea070109bca18cab56ee4d140bf28ac) (main); packaged variants: `main@f1fdb7f9dea0`.
  - network: [web/app.js:61](https://github.com/oscarhenrycollins/wizard-tinfoil/blob/f1fdb7f9dea070109bca18cab56ee4d140bf28ac/web/app.js#L61) — `async function request(path,body){const r=await fetch(path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json','X-Wizard-Request':'1'},body:JSON.stringify(body)});const s=await r.json();if(!r.ok)throw Error(s.error||'C`
  - origin: [app/server.py:234](https://github.com/oscarhenrycollins/wizard-tinfoil/blob/f1fdb7f9dea070109bca18cab56ee4d140bf28ac/app/server.py#L234) — `origin=self.headers.get('Origin','').lower()`
  - assets: [web/index.html:11](https://github.com/oscarhenrycollins/wizard-tinfoil/blob/f1fdb7f9dea070109bca18cab56ee4d140bf28ac/web/index.html#L11) — `<a class="get-key topup" id="topup" href="https://dash.tinfoil.sh/?tab=billing" target="_blank" rel="noopener noreferrer" hidden>Add credit on Tinfoil ↗</a></li>`
  - shared: [web/theme-client.js:31](https://github.com/oscarhenrycollins/wizard-tinfoil/blob/f1fdb7f9dea070109bca18cab56ee4d140bf28ac/web/theme-client.js#L31) — `if (parent===window || e.source!==parent || e.origin!==trustedHost || e.data?.type!=='wizard:appearance') return;`

<a id="evidence-wizard-ux"></a>
### wizard-ux

- **humanitylabs-org/wizard-ux**: [`ac0d73e752d3d0bedd68926936d128ec5a9b14d3`](https://github.com/humanitylabs-org/wizard-ux/tree/ac0d73e752d3d0bedd68926936d128ec5a9b14d3) (main); packaged variants: `main@ac0d73e752d3`, `release_pin@61c116404c58`, `stable_component@7991db030ccb`.
  - owner_routes: [web/sw.js:6](https://github.com/humanitylabs-org/wizard-ux/blob/ac0d73e752d3d0bedd68926936d128ec5a9b14d3/web/sw.js#L6) — `// every /wizard/* API stay network-only.`
  - parent: [web/device.js:372](https://github.com/humanitylabs-org/wizard-ux/blob/ac0d73e752d3d0bedd68926936d128ec5a9b14d3/web/device.js#L372) — `const w = f.contentWindow, d = f.contentDocument; if (!w || !d) return false;`
  - storage: [web/outbox.js:2](https://github.com/humanitylabs-org/wizard-ux/blob/ac0d73e752d3d0bedd68926936d128ec5a9b14d3/web/outbox.js#L2) — `* IndexedDB first; complete per-item localStorage backup second; RAM plus a persistent warning last.`
  - native: [android/app/src/main/java/ai/wizards/os/SelectionWebView.java:14](https://github.com/humanitylabs-org/wizard-ux/blob/ac0d73e752d3d0bedd68926936d128ec5a9b14d3/android/app/src/main/java/ai/wizards/os/SelectionWebView.java#L14) — `* Settings). The page tells this view, through WizardOSNative.selection(state), when a selection is its own; then`
  - network: [web/sw.js:13](https://github.com/humanitylabs-org/wizard-ux/blob/ac0d73e752d3d0bedd68926936d128ec5a9b14d3/web/sw.js#L13) — `// respondWith(fetch()) made Share/Save wait ~30 s on Android (18 Oct 2026).`
  - origin: [web/pwa-install.js:7](https://github.com/humanitylabs-org/wizard-ux/blob/ac0d73e752d3d0bedd68926936d128ec5a9b14d3/web/pwa-install.js#L7) — `if (!script || (script.dataset.pwaOrigin && location.origin !== script.dataset.pwaOrigin)) return;`
  - assets: [web/orb.js:213](https://github.com/humanitylabs-org/wizard-ux/blob/ac0d73e752d3d0bedd68926936d128ec5a9b14d3/web/orb.js#L213) — `fallback.src = (m === 'idle' || m === 'type') ? 'robert-thread-orb.png' : 'robert-listening-galaxy.png';`
  - shared: [web/outbox.js:663](https://github.com/humanitylabs-org/wizard-ux/blob/ac0d73e752d3d0bedd68926936d128ec5a9b14d3/web/outbox.js#L663) — `if (!window.WizAppServices?.conversation) throw new Error('App voice input conversation unavailable');`

<a id="evidence-wizard-voice-service"></a>
### wizard-voice-service

- **humanitylabs-org/wizard-voice-service**: [`e1c3c8660c477494ccc302a1359463da26818b64`](https://github.com/humanitylabs-org/wizard-voice-service/tree/e1c3c8660c477494ccc302a1359463da26818b64) (main); packaged variants: `main@e1c3c8660c47`, `release_pin@d28c5f7cd290`.
  - origin: [voice_mcp/front.py:59](https://github.com/humanitylabs-org/wizard-voice-service/blob/e1c3c8660c477494ccc302a1359463da26818b64/voice_mcp/front.py#L59) — `allowed_origins = {x.strip() for x in os.environ.get("WIZARD_VOICE_MCP_ORIGINS", "").split(",") if x.strip()}`

<a id="evidence-wizard-whoop"></a>
### wizard-whoop

- **oscarhenrycollins/wizard-whoop**: [`0daaaed30bf0efc322e3d80aad51117017934add`](https://github.com/oscarhenrycollins/wizard-whoop/tree/0daaaed30bf0efc322e3d80aad51117017934add) (main); packaged variants: `main@0daaaed30bf0`.
  - network: [web/app.js:15](https://github.com/oscarhenrycollins/wizard-whoop/blob/0daaaed30bf0efc322e3d80aad51117017934add/web/app.js#L15) — `const r = await fetch(path, init);`
  - origin: [app/server.py:984](https://github.com/oscarhenrycollins/wizard-whoop/blob/0daaaed30bf0efc322e3d80aad51117017934add/app/server.py#L984) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:43](https://github.com/oscarhenrycollins/wizard-whoop/blob/0daaaed30bf0efc322e3d80aad51117017934add/web/index.html#L43) — `<a class="wz-button secondary" id="open-health" href="/wizard-health/">Open Health</a>`
  - shared: [web/app.js:285](https://github.com/oscarhenrycollins/wizard-whoop/blob/0daaaed30bf0efc322e3d80aad51117017934add/web/app.js#L285) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-withings"></a>
### wizard-withings

- **oscarhenrycollins/wizard-withings**: [`aaa2ea359d50431151b815207d82b187fde896c5`](https://github.com/oscarhenrycollins/wizard-withings/tree/aaa2ea359d50431151b815207d82b187fde896c5) (main); packaged variants: `main@aaa2ea359d50`.
  - network: [web/app.js:17](https://github.com/oscarhenrycollins/wizard-withings/blob/aaa2ea359d50431151b815207d82b187fde896c5/web/app.js#L17) — `const r = await fetch(path, init);`
  - origin: [app/server.py:981](https://github.com/oscarhenrycollins/wizard-withings/blob/aaa2ea359d50431151b815207d82b187fde896c5/app/server.py#L981) — `origin = (self.headers.get('Origin') or '').lower()`
  - assets: [web/index.html:43](https://github.com/oscarhenrycollins/wizard-withings/blob/aaa2ea359d50431151b815207d82b187fde896c5/web/index.html#L43) — `<a class="wz-button secondary" id="open-health" href="/wizard-health/">Open Health</a>`
  - shared: [web/app.js:300](https://github.com/oscarhenrycollins/wizard-withings/blob/aaa2ea359d50431151b815207d82b187fde896c5/web/app.js#L300) — `if (!window.WizardApp || WizardApp.version !== 1) {`

<a id="evidence-wizard-youtube-music"></a>
### wizard-youtube-music

- **humanitylabs-org/wizard-youtube-music**: [`9ab575e56f5ba1c56356cd3a4ca31256e21dd204`](https://github.com/humanitylabs-org/wizard-youtube-music/tree/9ab575e56f5ba1c56356cd3a4ca31256e21dd204) (main); packaged variants: `main@9ab575e56f5b`.
  - network: [web/app.js:9](https://github.com/humanitylabs-org/wizard-youtube-music/blob/9ab575e56f5ba1c56356cd3a4ca31256e21dd204/web/app.js#L9) — `const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers, body: JSON.stringify(body) });`
  - origin: [app/server.py:627](https://github.com/humanitylabs-org/wizard-youtube-music/blob/9ab575e56f5ba1c56356cd3a4ca31256e21dd204/app/server.py#L627) — `origin = (self.headers.get("Origin") or "").lower()`
  - assets: [web/index.html:81](https://github.com/humanitylabs-org/wizard-youtube-music/blob/9ab575e56f5ba1c56356cd3a4ca31256e21dd204/web/index.html#L81) — `<p>Open <a id="google-link" target="_blank" rel="noopener noreferrer">Google authorization</a> and enter <strong id="user-code" class="ytm-code"></strong> Do not share this code. Then return here.</p>`
  - shared: [web/theme-client.js:31](https://github.com/humanitylabs-org/wizard-youtube-music/blob/9ab575e56f5ba1c56356cd3a4ca31256e21dd204/web/theme-client.js#L31) — `if (parent===window || e.source!==parent || e.origin!==trustedHost || e.data?.type!=='wizard:appearance') return;`

