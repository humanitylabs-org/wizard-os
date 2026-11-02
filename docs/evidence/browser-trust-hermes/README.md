# Browser trust: Hermes dashboard as an own-tab app (evidence, draft)

Card 3 / issue #386. Synthetic data, local runs (Forum `/srv/work` is not reachable from this runtime). Nothing here
touched a box, a release or Hermes itself.

Runner: wizard-ux `tools/qa-browser-hermes-own-tab.cjs` (draft branch `feature/browser-trust-hermes-own-tab`).
Real Chromium (headless shell 1248), the real Agent Service (#316 head), real WAM state from the app's own `wizard.md`
(candidate WAM head `feature/browser-trust-hermes-own-tab`; baseline WAM #416 head), the real hermes-agent front
(`mcp/*.py`, candidate `277548c`, baseline `e8ae558`) over the **real Wizard Hermes image**
`ghcr.io/humanitylabs-org/hermes-agent@sha256:ac89f5f9…` (the recipe's engine: dashboard on, its own password login).
Node stand-ins replace nginx (shell document) and Tailscale Serve (the dashboard's own https port, WebSocket included).

| Run | Result | Shows |
|---|---|---|
| `candidate/` | **23/23** | The picker lists Hermes Agent; Enter opens a new tab at its own origin (no opener, no referrer), never an iframe. The dashboard asks for its own login, sets its own `hermes_session_*` cookies (Lax, HttpOnly) and works: `/api/auth/me` 200, own-page WebSocket upgrade 101. Server-side 403 for every request from an opaque Wizard frame (fetch, no-cors login POST, `Origin: null` WebSocket, nested iframe) and every same-site request from an app tab on the Wizard origin, including those carrying the owner's session cookie; the owner's session survives. Box callers (no browser headers) pass. |
| `baseline/` | 5 checks (recorded) | Under the boundary on the current stack heads the Service row has **no address** (`url: ""`): the shell has no Hermes Agent entry at all. A hostile frame can embed the signed-in dashboard (no `X-Frame-Options`; `GET /` iframe 200), and same-site app tabs reach it with the owner's cookie (`GET /api/auth/me` 200, unreadable to the caller). Hermes' own WebSocket Origin check already refuses foreign origins (403) in both runs. |

Screenshots: `candidate/hermes-own-tab-dark.png` (dark standalone), `hermes-own-tab-light.png`,
`picker-{nebula,grove,landscapes-light}.png`; baseline `baseline-picker-*.png`, `baseline-hermes-direct-light.png`.
Pre-existing, not from this change: in Landscapes Light an opaque-frame window title (the synthetic hostile app) is
dark on dark; it is the same in the baseline.

Not proven: real Tailscale Serve, a real Runtipi install/restart picking up the WAM-written env, the alongside host
dashboard (`wizard-host-dashboard.service`, not a WAM app), phones.
