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
For an app row with the app's platform owner-proof key (`owner_proof` in wizard.md, spec/OWNER_PROOF.md) the App
Manager calls the app **server-side, as the owner**, so it works the same in every browser and device and never depends
on an app cookie in the viewer's browser: the app's loopback port, signed `X-Wizard-App-Owner-Proof` (hmac-v1, bound
to app id, method and target), with the box `Origin` and `X-Wizard-Switch: 1`. It never calls an app through the box's
own Tailscale Serve URL: Serve names the owner for every request that starts on the box, whoever sent it
(spec/OWNER_PROOF.md section 3, wizard-os#133). A keyless app is listed with `ok: false`, and the Tracker flips it from
the owner's browser at the app's same-origin path.

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
   - **Owner only**, always with `X-Wizard-Switch: 1` and never a bearer or agent grant. An app that has the platform
     owner-proof key (`WIZARD_OWNER_PROOF_KEY_FILE`) accepts **only** a valid owner proof (+-30 s, each nonce once,
     constant-time compare; no app session needed for switches). `Host`, `Origin` and `Tailscale-User-Login` are
     client-set, so any process on the box could send them; such an app never falls back to them, also when its key
     can't be read. An app without a key accepts the Tailscale Serve owner login, never a box-local host; it must
     declare `owner_proof` before it ships a switch that gates anything trust-related.
4. **Link** each switch to the issue(s) it delivers (`issues`), so the card finds it.
5. Re-read switches when the page becomes visible: the owner may flip them from the Tracker.

## Try new features: the one place in an app's Settings
Miguel, 14 Nov 2026 (wizard-os#627): a feature under test is shown **only** in one standard section at the very bottom
of the app's Settings, with the same look and wording in every app, and **never** as ordinary Settings rows.

- **Title** `Try new features`, then one short note: "Features still being tested. Approved ones become part of the
  app; the rest go away. Thumbs up the ones you like."
- **One row per switch** from the app's own listing: name, one-line description, On/Off and, when the app keeps votes,
  thumbs up / thumbs down. The section hides when the app has no switches.
- **Shared component**, so apps don't each build it: `style/try-features.js` (kit name `wizard-try-features.js`,
  hash-locked in `style/style-policy.json`). Put an empty `<section id="try-features"></section>` last in Settings and
  call `WzTryFeatures.mount(el, { path: 'api/switches' })` (the path declared in `wizard.md`). It needs `tokens.css` +
  `ui.css`, posts flips and votes with `X-Wizard-Switch: 1`, and re-reads when the page becomes visible.
- **Lifecycle unchanged:** approved removes the switch (the feature is just part of the app); dropped removes it with
  its code. Either way it leaves the listing, so it leaves the section.

### Optional feedback fields (additive to `wizard.app-switches/1`)
An app that records feedback adds two fields to each switch in its `GET` listing; clients that don't know them ignore
them, and an app without them simply shows no thumbs:

- `tried`: `true` once the owner has turned the switch on at least once on this box (never reset by turning it off).
- `vote`: `"up"`, `"down"` or `null` (no vote). Present (even `null`) means the app keeps votes.

`POST` with `{"id": "…", "vote": "up"|"down"|null}` sets the vote, with the same owner-only checks as a flip; any
other vote value is 400. Tapping the active thumb again sends `null`. Votes and `tried` are box state like `on`
(`DATA/switches.json`).

**Counts leave the box only after the owner opts in, and anonymously** (James, show-and-tell yes on wizard-os#627):
sharing is off by default on every box, and nothing is sent until the owner says yes to a clear prompt that says what is
sent. Tapping a thumb or a switch is not that yes; the section and thumbs work fully on the box without it. Once the
owner says yes: only `{switch id, issues, tried, vote}` plus a per-box random id for de-duplication, never content or
identity, through the existing Feedback route. The App Manager collects them
from the catalog above and the Tracker shows `Tried by N · 👍 N · 👎 N` on the item. Those two parts are tracked in
their own repos (linked from wizard-os#627).

Shared code (empty list, copy as is): Python stdlib `wizard-app-manager templates/hello-wizard/app/server.py` (the `wizard.app-switches/1` block + `wizard_switches_install(Handler)`); FastAPI `wizard-recorder app/wizard_switches.py` (`install_switches(app, data_dir)`); Node `wizard-music server/switches.mjs` (`handleSwitches(req, res)`). Every org app shipped one on 11 Nov 2026.

Reference implementations: wizard-messenger `switches.py` + `web.py` `_switches`; wizard-calendar `app/server.py`
(`SWITCHES`, `post_switch`); wizard-app-manager `wam/app_switches.py`.
