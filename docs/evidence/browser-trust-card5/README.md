# Browser trust, card 5: box-only listeners (wizard-os #386)

Synthetic data, loopback only, local runs on 2 Nov 2026. Nothing here touched a real box.

## 1. Transcriber, Browser and Voice: per-installation gateway key

`run.py base|candidate` drives real processes:

- **App Manager.** The real `cli.write_registry` (via `tools/browser_admission_fixture.py`, boundary on) installs the three apps from their own `wizard.md` and runtipi compose.
- **Listeners.**
  - The Transcriber and Browser MCP fronts, assembled exactly as `mcp/inline.py` does.
  - The real Voice FastAPI server (uvicorn).
  - Browser's upstream is a real `chrome-headless-shell` (DevTools on loopback).
  - Transcriber's engine is a stub `/v1/models`. Speaches was not pulled.
- **Gateway.** The real Agent Service gateway (`server/agent-bridge.mjs` at Service #316 head, unchanged) serves `/wizard/mcp`. It reads `apps.json` and `grants/agent-service.json` as written by App Manager.
- **Agent.** The harness speaks MCP to the gateway with the gateway token, as Hermes does.

Base = WAM #417 head + transcriber/browser/voice `main`. Candidate = this work's branches.

App Manager state in the candidate:
- `grants/agent-service.json` is mode `0o600` with keys for `browser, transcriber, wizard-voice-service`.
- Each app's `app.env` carries `WIZARD_BROWSER_BOUNDARY` and `WIZARD_GATEWAY_KEY`.
- `apps.json` carries a key: False.

In base App Manager wrote no keys: `[]`.

Agent through the gateway, candidate:
- Transcriber: True.
- Browser `read_page` rendered the synthetic page in real Chromium: True.
- Voice: True.

The same calls work in base.

| Caller | Request | Base | Candidate | As designed |
|---|---|---|---|---|
| agent via gateway | `tools/call transcriber__transcriber_status` | ok | **ok** | yes |
| agent via gateway | `tools/call browser__read_page` | ok | **ok** | yes |
| agent via gateway | `tools/call wizard_voice_service__voice_status` | ok | **ok** | yes |
| box peer, no key | `transcriber POST /mcp tools/list` | 200 | **403** | yes |
| box peer, guessed key | `transcriber POST /mcp` | 200 | **403** | yes |
| browser page (Origin) | `transcriber POST /mcp` | 200 | **403** | yes |
| tailnet-proxied (Tailscale-User-Login) | `transcriber POST /mcp` | 200 | **403** | yes |
| box peer, no key | `browser POST /mcp tools/list` | 200 | **403** | yes |
| box peer, guessed key | `browser POST /mcp` | 200 | **403** | yes |
| browser page (Origin) | `browser POST /mcp` | 200 | **403** | yes |
| tailnet-proxied (Tailscale-User-Login) | `browser POST /mcp` | 200 | **403** | yes |
| box peer, no key | `voice POST /mcp tools/list` | 200 | **403** | yes |
| box peer, guessed key | `voice POST /mcp` | 200 | **403** | yes |
| browser page (Origin) | `voice POST /mcp` | 403 | **403** | yes |
| tailnet-proxied (Tailscale-User-Login) | `voice POST /mcp` | 200 | **403** | yes |
| gateway key + Origin | `browser POST /mcp` | 200 | **403** | yes |
| box peer, no key | `browser GET /json/version (DevTools)` | 200 | **403** | yes |
| box peer, no key | `browser GET /json/list (DevTools)` | 200 | **403** | yes |
| box peer, no key | `browser WS /devtools/browser (CDP upgrade)` | 404 | **403** | yes |
| granted app (defleur-video key) | `browser GET /json/version (DevTools)` | 200 | **200** | yes |
| box peer, no key (grants not enforced: log+serve) | `transcriber GET /v1/models (engine API)` | 200 | **200** | yes |
| browser page (Origin) | `transcriber GET /v1/models (engine API)` | 200 | **403** | yes |
| box probe | `transcriber GET /health` | 200 | **200** | yes |
| granted app via Playwright connectOverCDP | `browser CDP session` | connected | **connected** | yes |
| keyless peer via Playwright connectOverCDP | `browser CDP session` | connected | **refused** | yes |

Playwright `connectOverCDP` (real CDP session, then `newPage` + `goto`):
- Base: {'granted': 'connected; title=Card five synthetic page', 'keyless': 'connected; title=Card five synthetic page'}
- Candidate: {'granted': 'connected; title=Card five synthetic page', 'keyless': 'refused: browserType.connectOverCDP: Unexpected status 403 when connecting to http://127.0.0.1:50433/json/version/.'}

The Transcriber engine API without a key is still served in the candidate (`WIZARD_PEER_GATE` default `grants`). It follows the grants file's `enforce` flag (spec PERMISSIONS.md rollout), because its box consumers do not send keys yet: the Agent Service STT path and Voice. Browser DevTools is strict (`require`).

## 2. Host Hermes dashboard on alongside boxes (audit)

`host-dashboard-probe.py` probes stock `hermes dashboard` v0.22.2 (`v2026.9.24`, the lock tag) started the way `wam/host_dashboard.py` starts it:
- the same stock basic-auth environment;
- a temporary `HERMES_HOME`;
- bound to `127.0.0.2`, which Hermes treats as a public bind like the box's Tailscale IPv4.

| Probe | Status | Detail |
|---|---|---|
| no session: GET / | 302 |  |
| no session: GET /login | 200 | text/html; charset=utf-8 |
| no session: GET /api/status | 200 | application/json |
| no session: GET /api/auth/me | 401 | application/json |
| no session: GET /api/config | 401 | application/json |
| no session: GET /api/sessions | 401 | application/json |
| no session: GET /api/env | 401 | application/json |
| no session: GET /api/plugins/wizard-os/usage | 401 | application/json |
| no session: GET /api/cron/jobs | 401 | application/json |
| no session: GET /api/model/info | 200 | application/json |
| Host: attacker.example (rebinding) | 400 |  |
| Host: bound IP without port | 200 |  |
| POST /auth/password-login (wrong password, provider basic) | 401 | {"detail":"Invalid credentials"} |
| POST /auth/password-login (right password) | 200 | hermes_session_at,hermes_session_rt,hermes_session_provider |
| cookie hermes_session_at | - | ['httponly', 'max-age', 'path', 'samesite'] SameSite=['lax'] |
| cookie hermes_session_rt | - | ['httponly', 'max-age', 'path', 'samesite'] SameSite=['lax'] |
| cookie hermes_session_provider | - | ['httponly', 'max-age', 'path', 'samesite'] SameSite=['lax'] |
| 25 more wrong passwords in a row | 401/429 | any 429 = rate limited |
| right password right after that burst (same client IP) | 429 | 429 = a caller can lock the consumer apps out |
| session: GET /api/status | 200 |  |
| session: GET /api/config | 200 |  |
| session: GET /api/env | 200 |  |
| session: GET /api/sessions | 200 |  |
| session: GET /api/auth/me | 200 |  |
| GET / framing headers | 200 | XFO=None CSP-fa=False |
| session + Origin evil + cross-site: GET /api/config | 200 | cookie only rides if SameSite allows |
| CORS preflight from https://evil.example | 400 | ACAO=None |
| CORS preflight from the Wizard shell origin | 400 | ACAO=None |
| same-origin logout POST with the session (control) | 302 |  |
