# Card 3: listener and direct-route inventory, and the listener credential contract

Card 3 ([#386](https://github.com/humanitylabs-org/wizard-os/issues/386)), first slice. Draft for Miguel's review, stacked on the card-1 spec ([#391](https://github.com/humanitylabs-org/wizard-os/pull/391)). The flag (`WIZARD_BROWSER_BOUNDARY`) stays default-off. Nothing here is enabled, released or applied to a box.

**Evidence level.** Section 1 and the Notifications row are proven by local runtime tests (see §5). All other rows come from reading source at the pinned commits. They are not runtime proof and not an inventory of any real box's installed or private apps.

## 1. Where the direct routes actually go

The adapter sketch (§1 "No direct-backend bypass") requires that every app route reachable with network-owner identity needs a scoped, non-ambient credential once enforcement is on. That raises the question of where such a rule can live. The answer comes from how WAM publishes apps today:

- **Path routes on the shell origin bypass the shell.** For an app page with no explicit gateway, `wam/links.py` `implicit_gateway()` and `_publish()` run `tailscale serve --set-path=/<path>/` straight to `http://127.0.0.1:<app port>`. Notifications declares `view.path: /notifications/`, so `https://<box>:<shell port>/notifications/*` reaches the app listener directly. Shell nginx (`packaging/nginx.conf.template`) and the Agent Service are not on that path. A gateway rule in shell nginx or in the Service would protect nothing here.
- **Every page app also keeps its own port.** `_publish()` publishes `https://<box>:<app port>/` as a whole. For Notifications, that is the entire MCP front, so it includes the unmodified ntfy server behind it.
- **Serve adds the owner's identity.** Serve adds `Tailscale-User-Login` for the owner's own devices, and for every process on the box (`wam/store_install.py` `from_box()`). So the network login identifies a network peer. It is not app authority.
- **Main ports are bound to loopback, but peers remain.** Runtipi binds main ports to `127.0.0.1:${APP_PORT}` (`wizard-index-store.ts`). That leaves box processes and containers on shared Docker networks as the other direct callers.

So the one hop every caller goes through is the app's own listener. For Notifications and the other packages built on the Wizard MCP front pattern, that is `mcp/front.py`. This slice puts the gate there, and has WAM and the Service supply the credential.

## 2. Listener credential contract (v1, draft)

| Part | Rule |
|---|---|
| Who mints | WAM, for each **installation** (card-1 `installation_id`). It is minted only when the boundary is on **and** the installed compose declares `WIZARD_APP_CREDENTIAL`. Apps without that variable are untouched. |
| Value | 32 random bytes, lowercase hex. |
| Server copy | `<WIZARD_OS_HOME>/browser-app-credentials/<installation_id>.key`. The file is 0600 and the directory 0700. Only the Agent Service reads it. |
| App copy | The app's own Runtipi user env (`user-config/<store>/<app>/app.env`, 0600): `WIZARD_BROWSER_BOUNDARY=1`, `WIZARD_APP_CREDENTIAL=<value>`. The container picks it up on its next start. Until then its gate fails closed (see below). |
| Registry | `apps.json` `browser.listener_credential = {header, ref, env, state}`. This is a reference only. The value is never in apps.json, a browser response, a URL or a log. |
| Lifecycle | A reinstall is a new installation and gets a new credential. Uninstall removes the key file. The Service reads the file on every upstream call, so rotation and removal apply at once. A recorded but missing or malformed key means `backend_unavailable` before any upstream request. |
| Header | `X-Wizard-App-Credential: <value>`. Only the Service adapter sends it, on its fixed-operation upstream call. Upstream headers are built fresh, never copied from the browser request. **Never the shell token**, owner proof, cookie, `Authorization`, `Origin` or Tailscale identity. |
| Listener gate (flag on) | For `WIZARD_GUARDED_PATHS` (Notifications: `/notifications/api/`, `/notifications/media/`), any method:<br>(1) a browser marker (`Origin`, `Cookie`, `Referer`, `Sec-Fetch-Site/Dest/User`) gets 403 `browser_request_refused`, even with a valid credential;<br>(2) a network or proxy marker (`Tailscale-User-*`, `X-Forwarded-*`, `Forwarded`, `X-Real-IP`, `Via`, `cf-*`) gets 403 `network_identity_refused`;<br>(3) anything other than exactly one matching credential gets 401 `adapter_credential_required`.<br>`OPTIONS` anywhere under the app's routes gets 403 `preflight_refused`. No `Access-Control-*` header is ever sent. The view's static files (document, js, css, `healthz`) still load. The front refuses to start with the flag on but no valid credential or guarded paths. Flag off: unchanged. |
| Not allowed | A generic relay, `Origin: null` allowances, forwarding the shell token, or network identity as authority. The credential is not owner enrollment. It authorizes only this installation's listener paths for the Service's fixed operations. |

Peer apps that hold `X-Wizard-Grant` or MCP tokens keep their own, separate authority. This credential does not replace provider and consumer grants.

## 3. Inventory: listeners and direct routes reachable by network-owner identity

Columns: route(s) as WAM publishes them; auth today (from source at the pin); what accepts network-owner identity; proposed protection; card owner. "Shell path" means a Serve path on the shell origin. "Own port" means `https://<box>:<app port>/`.

| App (source @ pin) | Route(s) | Auth today | Accepts network-owner identity? | Proposed protection | Card |
|---|---|---|---|---|---|
| **Notifications** (oscarhenrycollins/notifications @ `e6df99a8`) | Shell path `/notifications/` (api, media, view). Own port: the whole front, including ntfy. `/mcp`. | None on `/notifications/api/*` and `media/*`. `api/mark` and `api/sources` require JSON. MCP tools refuse forwarded headers (`_box_only`), but `initialize` and `tools/list` don't. | **Yes.** Any tailnet caller reads and writes owner notifications (runtime-proven, §5 control). | **This slice:** the listener gate + WAM credential + Service header (§2). **Next:** ntfy on the own port sends `Access-Control-Allow-Origin: *` by default (ntfy v2.29.0 `server/config.go` default `*`) and the recipe has `NTFY_ENABLE_LOGIN=false`. So any web page in the owner's browser that knows the host can read or publish topics. It needs ntfy access tokens (deny-all default plus a token for the front relay and the phone app) and a non-`*` CORS origin, without breaking the ntfy phone subscription. | 3 (this slice; ntfy next) |
| **wizard-ux shell documents** (wizard-ux #831 `032b7e09`) | `/wizard-os-home/{,index.html,desktop.html}` | Card-1 boundary document template: navigation only, shell token injected by `sub_filter`. | n/a (the shell) | **Fixed here.** With real nginx 1.28, every refusal was nginx's HTML error page, and `sub_filter` injected the shell token into it. Refusals are now text/plain. A remaining edge: a missing document file would hit `try_files =404`. The files are in the image. | 3 (found here; fold into #831) |
| **wizard-chatgpt** (org chatgpt-connection @ `1d296951`; Oscar's @ `bc6a1df9`) | Shell path `/wizard-chatgpt/` (implicit) + own port. `/v1/*` gateway. `/mcp`. | Optional page Basic password (`WIZARD_CHATGPT_PASSWORD`). POST requires `Origin` equal to `Host` (or absent) and `X-Wizard-Request: 1`. `/v1` and `/api/connection` are box-only with a gateway bearer. `GET /api/accounts` is open. | **Yes, for non-browser callers.** They can send `X-Wizard-Request` and omit `Origin`. Basic auth is an ambient browser credential. | Same listener gate on `/api/*` (sign-in, connect, accounts). Shell-owned sign-in confirmation. Keep `/v1` box-only and bearer. Audit both publishers. | 3 |
| **wizard-claude** (org claude-connection @ `0da65a4a`; Oscar's @ `ddf75246`) | Same shape as ChatGPT. | Same pattern: Basic option, Origin and custom header on writes, box-only inference. | **Yes, for non-browser callers.** | Same as ChatGPT. Preserve device-code renewal and the connection test. | 3 |
| **wizard-cloudflare** (oscarhenrycollins/wizard-cloudflare @ `67b3b339`) | Gateway `/wizard-cloudflare/` (defaults.json, strip) + own port. | `owner_guard`: `Tailscale-User-Login` in `WIZARD_OWNER_LOGINS`, or `X-Wizard-Owner-Token`. Reads need `Sec-Fetch-Site: same-origin`. Session cookie + CSRF bootstrap need trusted `Origin` and `X-Wizard-Request: bootstrap`. | **Yes.** The owner login is the authority, and browser-metadata headers can be forged by a non-browser network caller. | Listener gate, plus app-specific session/CSRF custody brokered by the Service (dedicated adapter, no cookie relay). Exact OAuth callback binding is kept. | 3 |
| **wizard-google** (humanitylabs-org/wizard-google @ `209a6ff3` catalogue pin) | Shell path + own port. OAuth callback. `/mcp`. | `Tailscale-User-Login` (exactly one, in owner logins) or owner token. Same-origin writes. `wg_session` cookie + CSRF. MCP is box-only. | **Yes** (same as Cloudflare). | Same as Cloudflare. Consumer routes keep refusing browser credentials. | 3 |
| **wizard-microsoft** (oscarhenrycollins/wizard-microsoft @ `343c8dd8`) | Shell path + own port. Return pages. `/v1` mirror. `/mcp`. | Owner token, or `Tailscale-User-Login`. **With `WIZARD_OWNER_LOGINS` empty, any login containing `@` is accepted** (`app/server.py` `owner()`). Same-origin writes. `wm_session` + CSRF. | **Yes. Any tailnet member** when owner logins are unset. | Same as Google. In addition, WAM must always set owner logins (or the listener credential replaces this path). | 3 |
| **wizard-tinfoil** (humanitylabs-org/wizard-tinfoil @ `d1bc51ed`) | Shell path + own port. `/v1`. `/mcp`. | Host allowlist. Origin allowlist when present. Writes need trusted Origin + `X-Wizard-Request`. **GET `/api/*` has no owner check.** `/v1` and `/mcp` are box-only with a gateway token. | **Yes**, for reads (status, billing, models). | Listener gate on `/api/*`. Key setup through a shell-owned confirmation. Never key export. | 3 |
| **connected-accounts** (humanitylabs-org/wizard-connectors @ `e873a61c` catalogue pin) | Gateway `/connected-accounts/` (strip) + own port. Google callback. | Owner token (`Authorization`), or a `connectors_session` cookie (HttpOnly, SameSite=Strict, **Path=/**) minted from that token. Origin and cross-site checks. Separate MCP token. | **No.** It has its own app authentication. The cookie is host-wide on the shared origin. | Keep its auth. Scope the cookie Path to `/connected-accounts/`. Add the gate when the boundary is on, for consistency. | 3 |
| **wizard-connection-router** (humanitylabs-org/wizard-connection-router @ `ec8ca140`) | Own port (static view, owner API). | The owner API refuses any forwarded or browser header (box-only). Static view only. | **No** (box-only). Its source notes that a direct box process can omit the headers. | Keep box-only. Add a Service-held credential if box peers become a concern (card 5 network isolation). | 3 (audit only) |
| **files** (File Browser 2.63.23, oscarhenrycollins/files @ `8a4dd8ac`) | Gateway `/files/` (defaults.json, `strip_prefix:false`) + own port. | `--auth.method noauth` behind private exposure. | **Yes. Full read, write and delete for any tailnet caller.** | Card-1 reviewed exception (separate origin) or listener gate on `/files/api/*`, plus `M` content tickets for raw, preview and Range (ADAPTER-SKETCH §6). It cannot just switch to JWT auth: the JWT would become global owner authority. | 3 (tickets) + 2 (UI) |
| **hermes-agent dashboard** (oscarhenrycollins/hermes-agent @ `e8ae558f`) | Own port 9119 (category `agent`, no shell path). | `HERMES_DASHBOARD_BASIC_AUTH_*` (Basic auth, an ambient browser credential). The MCP front has a bearer. | Network reach plus the Basic credential the browser caches. | Reviewed separate-origin exception (card 1) with its own non-ambient session. The dashboard must not be framed by the shell under the boundary. | 3 |
| **troubleshooter** (humanitylabs-org/wizard-troubleshooter @ `8d3a39f4`) | Shell path `/troubleshoot/` to its host listener (path reserved in WAM). | Tailscale whois of the loopback `X-Forwarded-For` peer must match `Tailscale-User-Login` (optional `TROUBLESHOOT_OWNERS`). Writes need an allowed Origin + `X-Wizard-Troubleshoot: 1`. | **Yes, by design**: recovery must work while the Service is down. | Distinct recovery gate: a recovery credential held by the trusted shell document (not the shell token) or a reviewed separate origin. Keep it usable without the Service. Never a blanket owner-token exemption. | 3 |
| **WAM store listener** (wizard-app-manager #405 `0b92cbf3`) | `/wizard-os-home/store-install/` → `127.0.0.1:7791`. | Owner `Tailscale-User-Login` + not from the box + trusted Origin + `X-Wizard-Store: 1` + JSON. With the flag on: the shell token (WAM #168). | Not alone: with the flag on, possession of the shell token is required. | Done in #168. Keep. | 1 (done) |
| **Agent Service** (#306 `74f6e017`) | Everything else on the shell origin. | Owner verifier + shell token with the flag on (#100/#303). Adapter admission against WAM facts (card 1). | Not alone with the flag on. | Done for adapter routes. Headerless media/streams are card 3 tickets and card 5. | 1 / 3 / 5 |
| **messenger** | Owner ingress via a Unix-socket gateway (`links.owner_fronted`). | Own cookie + CSRF owner sessions. | Its own session. | Card-1 optional probe. Session custody adapter. | 2 / 5 |
| **secret-drop** (oscarhenrycollins/secret-drop @ `690b2776`) | Own port (recipient page). | One-use drop capability. Exactly one same-origin `Origin` on submit. Optional API bearer. COOP/CORP. | Recipient capability, not owner identity. | Keep the recipient page on an isolated non-owner origin. Test its framing. | 3 (recipient separation) |
| **browser**, **transcriber**, **wizard-voice-service** | `/mcp` (own port), no app view. | MCP bearer when set (`MCP_TOKEN` / `WIZARD_VOICE_MCP_TOKEN`). Voice front checks allowed origins. | Only where no token is set. | Require the MCP token on every box. Keep DevTools box-only. | 3 (audit) |

Every other page app with a view gets the same two Serve routes (shell path and own port) from `_publish()`. Its listener needs the same gate before the boundary can be enabled. The APP-CENSUS rows list them; their owner listeners are assigned to card 3 and their UIs to card 2.

## 4. Dependencies this slice creates or exposes

- **Shell bell and count.** `web/core/notif-bell.js` fetches `/notifications/api/{count,items,mark}` from the shell document. With the flag on, these get 403 (browser marker). The shell-owned count refresh in card 2 (#385 claim) must replace them before enablement.
- **The real Notifications UI** (card 2) must use `data.call` only. Its own `fetch('api/…')` is refused with the flag on, by design.
- **Thumbnails** (`/notifications/media/*`) are refused with the flag on until card-3 content tickets exist (an open card-2 dependency, as #385 states).
- **Running containers** only pick up the WAM-written env after a restart. Until then the front either has no credential (flag off: legacy behaviour) or refuses to start (flag on without a credential). There is no silent unguarded mode.
- **Preflight evidence.** In the Chromium run, a cross-origin `application/json` POST from the opaque frame reached the listener with **no** OPTIONS in the nginx log. The QA harness enables Playwright request interception (onboarding fixture routes), so a browser run under interception cannot show preflight blocking. The SPEC-CARD1 §3 remark ("blocked by preflight") should be read as unproven. Only server-side refusal counts. That is how this slice proves it (the raw OPTIONS is refused, and the actual POST gets 403).

## 5. Evidence (local runs; Forum `/srv/work` not reachable from this runtime)

All runs used synthetic data, the exact heads in the PRs, and Linux:

- **Notifications front (unit + real process):** `tests/test_listener_gate.py` passes 6/6 on the candidate. On base `e6df99a8`, 4 of 6 fail: network identity, frames, credentials and fail-closed startup. The 2 that pass are the adapter-call and static-file positives. All 7 existing suites pass.
- **WAM:** `tests/test_browser_listener_credentials.py` passes 6/6. The full suite reports 1741 passed / 9 skipped (card-1 head: 1735 / 9).
- **Service:** `tests/browser-listener-credential.test.ts` passes 5/5 against a WAM-generated golden (`listener-auth.json`). On the card-1 head, 3 fail; the 2 that pass are the reference-shape and ungated-compatibility tests. Full `npm test`: exit 0.
- **Browser (real Chromium, real nginx 1.28.3):** nginx ran in a scratch container on the host network and was removed afterwards. The rest of the stack was the real Agent Service, real WAM state and the real front. `tools/qa-browser-listener-gate.cjs` passes 21/21:
  - data.call list and mark-read work, with inbox.json readback;
  - network-identity reads and writes get 403;
  - all 7 direct frame requests (CORS GET, no-cors GET, text/plain POST, JSON POST, sources POST, form POST into a child frame, `<img>` media) reached the listener and got 403 in the nginx access log;
  - inbox.json was unchanged after the hostile requests;
  - the shell document's direct `api/count` gets 403;
  - a raw OPTIONS gets 403 with no `Access-Control-*`;
  - reinstall rotates the credential and the old binding is refused;
  - none of the 4 shell-document refusal variants carries the token.
- **Controls:**
  - With the same harness and the base front (flag off), the network caller reads (200, data) and writes (200, landed), the frame GETs are answered 200 by the server, and the shell's `api/count` gets 200.
  - With the card-1 template (#831 head), all 4 document refusal variants returned the shell token in the 403 body.
- **Tailscale Serve itself was not run.** nginx stood in for Serve's path handler by adding `Tailscale-User-Login` and `X-Forwarded-For`.

## 6. Not proven or open

- A real Tailscale Serve route, a real Runtipi install/restart with the WAM-written env, Store update/uninstall on a box, Forum/heavy runs, native clients and phone (card 4), and packaged rollback (card 6).
- The ntfy own-port exposure (ACAO `*`, no login), and the `/mcp` `initialize`/`tools/list` exposure without `MCP_TOKEN`.
- Every row other than Notifications is source-read only. Their gates, tickets for Files/media/streams, and the Hermes dashboard and Troubleshooter exceptions are follow-up slices of card 3.
- Peer containers on shared Docker networks can still reach listeners directly. The gate stops them without the credential, but network isolation itself is card-5/netiso work.
- Installed private apps and James's box were not inventoried. This was intentionally not collected (no private content).
