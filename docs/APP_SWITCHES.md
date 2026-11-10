# Feature switches: one catalog for core and apps (`wizard.app-switches/1`)

Miguel, 10 Nov 2026: the WizardOS Tracker's **Try it** toggle controls the feature switches of WizardOS core **and** of
every installed app, current or future. Every switch is off by default and is flipped with one click from the Human
review card. Internal tool for now; security hardening comes later.

## One catalog
The box's App Manager serves one catalog: `GET /wizard-os-home/store-install/_feature-switches` (owner's browser, same
origin, Tailscale owner login), `GET /api/feature-switches` (owner token) and `wam feature-switches`.

- **Core** rows: the shell's tweaks (`<author>/<id>`, `kind: "core"`, `issues` from the tweak manifest). Locked off on
  For everyone.
- **App** rows: every installed app that declares `switches:` in its `wizard.md` (`<app id>:<switch id>`,
  `kind: "app"`). Never locked by the channel; they follow the app's own state. `apps` lists each declaring app and
  whether it answered.

`POST` the same route with `{"id": "<id>", "on": true|false}` (browser: `X-Wizard-Store: 1`, the box Origin) flips one.
For an app row the App Manager calls the app **server-side, as the owner**, so it works the same in every browser and
device and never depends on an app cookie in the viewer's browser:
- with the app's platform owner-proof key (`owner_proof` in wizard.md, spec/OWNER_PROOF.md): the app's loopback port,
  signed `X-Wizard-App-Owner-Proof` (hmac-v1, bound to app id, method and target);
- otherwise: the box's own Tailscale Serve URL of the app (`<box origin>/<app path>/<switch path>`), where Serve names
  the owner for every request that starts on the box.
Both send the box `Origin` and `X-Wizard-Switch: 1`.

The Tracker gives every Human review item whose issue (`owner/repo#N`) a catalog switch names a real Try it toggle with
the switch's real state (core or app).

## The app contract
1. **Declare** it in `wizard.md`:
   ```yaml
   switches:
     contract: wizard.app-switches/1
     path: /api/switches          # or /api/view/switches when owner pages live under api/view (Messenger)
   ```
   (`switches: /api/switches` is the short form.) `wam check` validates it.
2. **Keep state on the box** (e.g. `DATA/switches.json`), not per device; off by default. The app's own Settings, the
   Tracker and the agent see one state.
3. **Serve** at that path:
   - `GET` → `{"contract": "wizard.app-switches/1", "switches": [{"id": "drafts-first", "name": "Drafts at top",
     "description": "…", "on": false, "default": false, "issues": ["humanitylabs-org/wizard-messenger#133"]}]}`
   - `POST` with `Content-Type: application/json`, `X-Wizard-Switch: 1`, the box's own `Origin`, body
     `{"id": "…", "on": true|false}` → the same listing (200). Unknown id 404, not the owner 403, bad body 400.
     Errors are JSON `{"error": "…"}`.
   - **Owner only**, accepting the App Manager's call: the platform owner proof (no app session needed for switches)
     and/or the Tailscale Serve owner login with `X-Wizard-Switch: 1` standing in for the page's own request header.
     Never a bearer, agent grant or box-local host.
4. **Link** each switch to the issue(s) it delivers (`issues`), so the card finds it.
5. Re-read switches when the page becomes visible: the owner may flip them from the Tracker.

Reference implementations: wizard-messenger `switches.py` + `web.py` `_switches`; wizard-calendar `app/server.py`
(`SWITCHES`, `post_switch`); wizard-app-manager `wam/app_switches.py`.
