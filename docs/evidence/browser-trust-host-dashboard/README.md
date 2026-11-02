# Browser trust: host Hermes dashboard front + card-5 key wiring (wizard-os #386)

Synthetic data, loopback only, local runs on 2 Nov 2026. Nothing here touched a real box. Approved disposition:
https://github.com/humanitylabs-org/wizard-os/issues/386#issuecomment-6574712392.

## 1. Host Hermes dashboard on alongside boxes (WAM front, default-off)

`host-dashboard-front-e2e.py base|candidate <out.json> --chromium` drives:

- **App Manager**: the real `host_dashboard.ensure` of the checkout under test (base = WAM #421 head `261f3d1`,
  candidate = the front branch). The box's Tailscale IPv4 is stood in by `127.0.0.5` (Hermes treats it as a public
  bind, like `100.x`). `systemctl` is stubbed; the units it writes are started here exactly as written
  (`ExecStart`, `EnvironmentFile`, `Environment`). Runtipi state uses the real ChatGPT and Claude recipes.
- **Hermes**: stock `hermes dashboard` v0.22.2 (`2026.9.24`, the lock tag), temporary `HERMES_HOME` and `HOME`,
  the wizard-os plugin code copied in and enabled.
- **Consumer apps**: the real engine code of wizard-app-store `images/wizard-chatgpt` (`server.py` `Hermes.call`)
  and `images/wizard-claude` (`pool_client.py`), with the environment their compose builds from `app.env`.
- **Owner tab**: real chrome-headless-shell; the box name is mapped to 127.0.0.1 and `Tailscale-User-Login` is added
  as Serve would. Plain http here (Serve terminates TLS on a real box), so Chromium sends no `Sec-Fetch-*` headers:
  the frame refusal below is `X-Frame-Options: DENY`; the `Sec-Fetch-*` and Origin rules are covered by the WAM tests.
- **Hostile page**: a real local HTTP server on `evil.test` (another origin) with an `<iframe>` of the dashboard.

| Caller | Request | Base | Candidate |
|---|---|---|---|
| App Manager | Hermes listens on | `127.0.0.5:9119` (the tailnet stand-in) | **`127.0.0.2:19119`** (host-only); the front takes `127.0.0.5:9119` |
| App Manager | ChatGPT / Claude `app.env` holds the dashboard password | yes / yes | **no / no** (each holds its own key) |
| App Manager | password rotated when the front took over | n/a | **yes**; the old password then gets 401 on Hermes itself |
| ChatGPT app (real code) | connection reads (`/api/model/info`, `/api/providers/oauth`) | ok | **ok** |
| Claude app (real code) | account inventory (`provider-accounts/claude`) | ok | **ok** |
| box peer, no session | `GET /api/status`, `/api/model/info` | 200, 200 | **401, 401** |
| box peer, no session | `GET /api/config`, `/api/env` | 401, 401 | 401, 401 |
| ChatGPT app's credential | `GET /api/env`, `/api/config`, `/api/sessions` | **200, 200, 200** (full admin) | **403, 403, 403** (not on its allowlist) |
| ChatGPT app's credential | `GET /api/model/info` | 200 | 200 |
| … + `Origin: https://evil.example` | `GET /api/model/info` | 200 | **403** |
| … + `Tailscale-User-Login` | `GET /api/model/info` | 200 | **403** |
| DNS rebinding | `Host: attacker.example` | 400 | 400 |
| box peer | 25 wrong logins from the apps' source address | 401 then **429** | 401 only (the front answers; Hermes never sees them) |
| ChatGPT app (real code) | right after that burst | **`Hermes Agent answered 429`** | **ok** |
| Claude app (real code) | right after that burst | **`BridgeError 503 unreachable`** | **ok** |
| front | its own Hermes sign-ins during the whole run | n/a | **1** |
| hostile page on another origin | `<iframe>` of the dashboard | **renders the sign-in form** (200, no XFO) | **blocked** (200 with `X-Frame-Options: DENY`) |
| owner (real Chromium) | own tab `http://box.tail0.ts.net:9120/` | no owner tab exists | login page (XFO DENY) → signs in with the dashboard password → `Hermes Agent - Dashboard`; same-origin `/api/config` 200 |
| another tailnet user | own tab | n/a | **403** |

Screenshots: `base.hostile-frame.png` (base: a hostile page frames the sign-in form), `cand.owner.png` (candidate:
the owner's own tab, signed in, empty synthetic agent). Raw rows: `base.json`, `cand.json` (+ `.txt`).

**Login lockout risk (checked).** Stock Hermes limits `/auth/password-login` per client IP to 10 attempts a minute,
successful logins included (`hermes_cli/dashboard_auth/routes.py`). In base, a burst from the apps' source address
gives the real apps 429 (above). With the front: consumer logins are answered by the front from the app's key and
never reach Hermes; the front signs in once from its own source address (`127.0.0.3`) and again only after a 401; the
owner tab reaches Hermes from `127.0.0.4`. WAM test `test_owner_typos_and_the_apps_use_different_login_buckets`:
12 owner typos lock only the owner for a minute; the apps keep working. Rootless-Docker source addresses on a real
box were not verified.

Not covered: real Tailscale Serve / TLS, a real remote tailnet device (box-peer refusal is unit-tested with injected
interface tables: another tailnet IP and a LAN neighbour are refused), real Runtipi restarts, systemd itself.
