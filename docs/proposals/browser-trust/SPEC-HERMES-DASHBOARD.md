# Browser trust: Hermes dashboard (card 3, #386) — proposed second own-tab exception, draft

Draft record. Default-off under `WIZARD_BROWSER_BOUNDARY`. Nothing here enables the boundary, changes a release default, touches a box or patches Hermes.

## 1. Decision needed

| # | Proposal | Who decides | Status |
|---|---|---|---|
| H1 | The packaged Hermes dashboard (`hermes-agent` from `oscarhenrycollins/hermes-agent`, port 9119) is the **second reviewed separate-origin exception**, after File Browser (SPEC-FILES F1). It runs on its own https origin, keeps **its own login**, and opens **only as its own tab**. It is never framed. | Miguel | **Pending.** It is on the draft WAM list only for review. |

Why not the opaque frame: the census row (APP-CENSUS `hermes-agent`) needs dashboard storage, fetch auth and WebSocket boot to change. That is Hermes core, and Hermes core is not patched. The recommended "non-owner dashboard principal with its own auth" already exists: the dashboard's password login with a signed session cookie. It needs only an origin of its own and a front that refuses everything except its own page.

## 2. Shape (same machinery as F1, no new mechanism)

- **WAM** adds one pair to `OWN_TAB_EXCEPTIONS`: `('hermes-agent', 'oscarhenrycollins/hermes-agent')`. That gives the app no bindings, grants or listener credential. It stays on its own port; an agent-category dashboard never had a Wizard-origin path. `WIZARD_BROWSER_BOUNDARY=1` + `WIZARD_OWN_HOSTS` are written only if its installed compose declares `WIZARD_OWN_HOSTS`. No secret is written.
- **Agent Service and shell**: no change. They use the generic `own_tab` projection and tab open from F1.
- **App front** (`2026.9.24-wizard3`, `mcp/front.py`), before Hermes sees a request, refuses:
  - frame and embed requests;
  - an opaque or foreign `Origin`, WebSocket upgrades included;
  - cross-site and same-site requests other than a plain top-level GET navigation. The dashboard's `SameSite=Lax` session cookie rides along on same-site requests from other Wizard origins;
  - any Host other than its own.

  It adds `X-Frame-Options: DENY`, `frame-ancestors 'none'` and CORP/COOP same-origin. Box callers without browser or network headers are unchanged: the agent's `/mcp` and the ChatGPT/Claude apps' dashboard API calls.

## 3. Evidence (local, synthetic)

- Real Chromium against the real Wizard Hermes image (`ghcr.io/humanitylabs-org/hermes-agent@sha256:ac89f5f9…`): **23/23**.
- Baseline, for comparison:
  - with the boundary on, the current stack gives the dashboard **no address at all** (`url: ""`);
  - hostile frames can embed the signed-in dashboard;
  - same-site app tabs reach it carrying the owner's cookie.
- Evidence: `docs/evidence/browser-trust-hermes` on branch `docs/evidence/browser-trust-hermes`.
- Drafts: oscarhenrycollins/hermes-agent#1, wizard-app-manager#417, wizard-ux#865.

## 4. Still open

- H1 approval.
- Real Serve and Runtipi restart.
- The engine joins the Runtipi network (`add_to_main_network`), so peers reach the dashboard and API behind its login and key (card 5).
- The **alongside** host dashboard (`wizard-host-dashboard.service`, stock `hermes dashboard` on the box's Tailscale IPv4, http, its own login) is not a WAM app and is not covered by this front. It has no shell entry. A browser reaches it only by typing its address. It needs an audit, and if wanted, a Wizard-side front. Hermes is still not patched.
