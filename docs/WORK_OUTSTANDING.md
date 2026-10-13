# Work outstanding

Components still to build. Pick one up: put your name on it in a PR, and close it with evidence. Ordered roughly by when it's needed.

## Agent Service (Archimedes; DECISIONS #30, #42)

- [x] **Runs on stock Hermes** (Archimedes, 9 Oct): capability-aware runs, helper follow-through without a Hermes patch, settings/bootstrap/apps endpoints, orb router, serves Wizard UX. James's daily driver since 9 Oct; `main` = `2634564`, CI green.
- [ ] **Container port** (Archimedes, 🔨): one Runtipi app = Agent Service + Wizard UX, `wizard.md` with `provides: [shell]`; Hermes at `hermes-agent-engine:8642`; sessions read from a read-only Hermes data volume; voice via the `transcription` slot; uploads into `media/`; every host path becomes a setting. Done when it passes the end-to-end test on a fresh stock-Runtipi VM.
- [ ] **Wizard OS instruction injection.** Prepend "you are an agent inside Wizard OS" plus the installed-app summary to every agent run. Hermes stays unmodified. Built: [wizard-agent-service#2](https://github.com/humanitylabs-org/wizard-agent-service/pull/2), rebased on main, 183/183 tests; Jan to review.
- [ ] **Agent bridge** ([AGENT_BRIDGE.md](../spec/AGENT_BRIDGE.md), #40; Archimedes): `wizard` MCP gateway at `/wizard/mcp` over `apps.json`, `list_changed` on change, `wizard_apps` meta tool; kernel at `/wizard/v1/agent-context`; `wizard-os` Hermes plugin; weak-model gate. Replaces "`apps.json` reader: register each app's MCP".
- [ ] **Pointer skills** (Archimedes, part of #40). One short skill per job type ("short-form video → DeFleur Video"), rebuilt from `apps.json` `provides` on every change.
- [x] **`spec/AGENT_SERVICE_API.md`** (Archimedes, 12 Oct; [#22](https://github.com/humanitylabs-org/wizard-os/pull/22)). v1 written from shipped behaviour (wizard-agent-service `main` `f772b83`, wizard-ux `daily` `8866124`): 46 served routes plus the 4 proposed PR #7 routes and 1 gap, with discrepancies D1–D5. Evidence: `tools/check_api_contract.py --ux` maps all 63 UX requests (web + Android) onto documented routes, 0 problems; `tools/tests/test_api_contract.py` 12/12 with negative controls; `tools/api_contract_probe.mjs` 75/75 cases against an isolated service, 46/46 served routes exercised, 11 negative controls (undocumented, proposed and gap paths answer 404).
- [ ] **Install alongside an existing Hermes** (#41; Archimedes): `os.sh` detect + alongside mode, `wizard link / unlink / doctor`, tested on a fresh VM with stock Hermes preinstalled.
- [ ] **Release file** (Archimedes). `releases/<version>.json`: the commit of each repo that goes together.
- [ ] **Attachments into the files root** ([SYSTEM_APPS.md](SYSTEM_APPS.md#files)).
- [ ] **Pages** ([PAGES.md](../spec/PAGES.md), #35): serve `/pages/` from `media/Pages/` with the sandbox header; list / save-with-version / history / restore API; git commit on every write; refuse `Origin: null` on `/wizard/...`; redirect James's old `/reports/<slug>/`.
- [ ] **Agent switch for the Opus-vs-Hermes test.** One thread, routed either to Hermes or straight to Opus.

- [ ] **Agent state** ([AGENT_STATE.md](../spec/AGENT_STATE.md), #43–#49), after the agent bridge lands:
  - `~/.wizard-os/agents/<id>/` layout and `agent.json`; the Hermes agent app mounts its home there.
  - Agent Search system app: Hermes + Pi readers, per-agent index, MCP tools, grant checks, read log.
  - Agent-data grants in `wizard-grants.json` and on the Apps screen.
  - Wizard scheduler: jobs API, UX list, Hermes cron import for alongside mode, blueprint templates.
- [ ] **Approval policy across agents**: which actions need the owner's yes, enforced in Wizard rather than per agent. Unowned.
- [ ] **Lean-agent bake-off** (once a containerised box exists): 20 real tasks, four setups (Hermes + frontier model, Hermes + flash model, slim Hermes profile + flash model, Pi + flash model), scored on pass rate, cost, time and tool calls. Runs in fresh containers on Thales with stub app MCPs.

## Wizard ID (Archimedes builds, Jan reviews; DECISIONS #38, #39)

- [ ] **Wizard ID in `ai.wizards.os`**: create or import a key, wrap it with a biometric/PIN Keystore key, save it to the password manager and read it back, publish the profile, Settings → Wizard ID, and the `identity.info/setup/sign` bridge methods ([spec/WIZARD_ID.md](../spec/WIZARD_ID.md)). Built and emulator-tested on Thales.
- [ ] **`wizard publish`**: the Agent Service drafts the NIP-34 announcement for an app (GitHub `clone`, `euc`, `t=wizard-app`, maintainers), the owner approves on the phone, then it is posted to relays and the index.
- [ ] **Two-sided publisher rule** in the index and `wam` (Miguel): fill `publisher_npub` only when both sides match.
- [ ] **Store publisher profiles** (James + Archimedes): name and photo from the npub's kind 0 profile, tap through to all of that npub's apps, and a "GitHub: *owner*" label for unclaimed apps.

## App Manager (Miguel)

- [ ] Take over `wizard-app-manager`, and review the reference implementation's choices (CLI token auth, git smart-HTTP store, `apps.json` v1).
- [x] `wizard.md` for every app: each split into its own public repo with history, an MCP and a skill, and listed in the index (9 Oct).
- [x] **Index** `wizard-app-index` live at apps.aiwizards.com, store page at aiwizards.com/wizard-apps (9 Oct).
- [ ] **App Manager reads the index**: install = fetch one app at the index's commit, re-check, add to the local store. Retire per-box topic search.
- [ ] **Lock the App Manager API**: loopback bind, token for install/uninstall/refresh (#28).
- [ ] Move DeFleur's image build and e2e scripts into `defleur-video`.
- [ ] **Thin-fork terms (#32, Miguel):** ~~frontend back to stock Runtipi~~ done 10 Oct (only the four Wizard categories remain; Wizard views in `wizard-app-manager/wizard-views/` for Wizard UX); image stays a drop-in for `runtipi/runtipi`; "Open port" fix sent upstream; index store offered upstream as a pluggable store source. Review 20 Nov 2026.
- [ ] **App-to-app permissions spec** (Miguel + Jan): agent→app grants first, then `uses:` grants; per-grant credential; shown at install. Spec before networking code.
- [ ] Dependency install UX: "you already have a transcriber" vs "install the recommended one". Today `uses:` installs missing dependencies silently.
- [ ] Install-time checks: `recommends.model` warning and architecture mismatch messages for the UX.
- [ ] Uninstall keeps data. Verify Runtipi's behaviour and add an explicit `--delete-data`.
- [x] **Nostr catalog source behind a flag** (Archimedes, 9 Oct): `wam/nostr.py`, signature-verified NIP-34 discovery, publisher rule, GitHub/Nostr de-dupe, `commit` recorded per catalog row. Off unless `WAM_NOSTR=1`. Tested against four live relays.
- [ ] **Pinned updates** (needed by stage 2): `wam update <id>` shows the commit diff, re-runs the checker, installs only after owner approval. Today a refresh moves to the latest commit.
- [ ] **Stage 2 publish tooling**: see Wizard ID above (`wizard publish`), plus the Humanity Labs curated list.

## Wizard UX, including the desktop UX (James + Archimedes)

- [ ] **Pages in the shell** ([PAGES.md](../spec/PAGES.md), #35): pass `/pages/` through, Pages list, open on a review desk, `doc.md` editor, page bridge (`feedback`, `save`).
- [ ] **Apps screen sources**: label each app Public / Beta / Local / Link; GitHub sign-in for beta apps; `wizard://install` share links ([PRIVATE_BETA.md](PRIVATE_BETA.md)).

- [x] **Desktop UX** of `wizard-ux`: one codebase, two shells. `web/core/` is shared; `desktop.html` is the Omarchy-style shell (workspaces, auto-tiling, ⌘K, ⌥ keys, ⌥V voice), picked by device so neither shell downloads the other's code. Live at `/wizard-os-home/` (`daily` 60e1489), qa-desktop 45/45. UX side of the native bridge done (v0.1).
- [ ] **Native desktop app with hotkeys** (Caps Lock Wizard key, Right ⌘ voice) driving `wizard-ux` through the [native bridge](../spec/NATIVE_BRIDGE.md). This is desktop UX work, separate from the Mac installer.
- [ ] **Apps screen**: catalog, install, open, status from the App Manager API. A separate section for plain Runtipi apps.
- [ ] Back button contract: Back never exits (see James's standing rule in `wizard-ux`).
  - Hosted app views need a spec'd Back hook in `spec/NATIVE_BRIDGE.md` and the `hello-wizard` template: the shell asks the focused app for one back step and the app answers `handled` or `not handled`, so the shell knows when to take its own step. Today `wizard-ux` bridges Legacy Wizard's `__wizardCloseOverlay` with a layout-signature guess (`LEGACY-BRIDGE` in `web/app.js`); delete that once the contract lands or Legacy Wizard retires.

## Shell customization (James + Archimedes, later; [spec/SHELL.md](../spec/SHELL.md))

- [x] **Parking spots** (Miguel, 10 Oct): `wam slots`, `wam bootstrap` and the required-spot uninstall guard cover every slot, the shell included (`wam/defaults.json`). The shell spot's default fills in once the Wizard UX app is published.
- [ ] **Theme / skin file** (`theme.json` over the style tokens): look changes on phone and desktop without a rebuild, survives updates. Apps follow through [Appearance v1](../spec/APPEARANCE.md) (#50–#53); preview proven on Wisdom, Music, Signal, Topics.
- [ ] **Overlay folder**: user CSS/JS and per-view overrides loaded last; a broken overlay starts with it off and names the file.
- [ ] **Customize skill** so the owner's agent edits settings, layout, theme and overlay safely.
- [ ] **Move the review screens out** (Day/Week/Month) into their own view apps; the shell keeps only what every screen relies on.
- [ ] **App graph in the Apps screen** (from Miguel's Runtipi branch): interface → agent → system apps each one uses, with live status.

## Mac installer (later, once the components work together)

The Try Wizard VM that runs the whole stack on a Mac. Not started until the App Manager, Agent Service and UX work together on Linux. Owner decided then.

- [ ] Build the VM's UX payload from `wizard-ux` (the `mizel-mac` prototype ships the old `wizard-mobile` build).
- [ ] **Shared `~/Wizard` folder** mounted into the VM as the files root (virtio-fs) ([MAC.md](MAC.md#where-files-live)).
- [ ] Folder picker for read-only sharing of `~/.claude`, `~/.codex` and project folders into the VM.

## Apps (anyone)

- [ ] **Context bridge** app: read Claude Code / Codex sessions and project folders; import ChatGPT and Claude exports; MCP tools `search_past_work`, `load_project_context` ([MAC.md](MAC.md#picking-up-where-claude-or-chatgpt-left-off)).
- [ ] **Meeting Recorder** as a wizard.md app (Archimedes). Package staged in [meeting-recorder PR #1](https://github.com/humanitylabs-org/meeting-recorder/pull/1): v0.2 checker passes; four Thales fixture regressions pass; fresh Runtipi/App Manager system apps installed. Full recording/upload, hosted Back, Hermes gateway and uninstall-retention acceptance remains open. Private short-name install mapping is a separately dispatched WAM proposal; index PR publication awaits repository write access (READ account, forks disabled). [Acceptance checkpoint](https://github.com/humanitylabs-org/meeting-recorder/blob/feature/wizard-app-package/QA.md).
- [ ] **Reader** as a wizard.md app (Archimedes).

## Shared (Archimedes unless noted)

- [ ] **Style tokens** pulled from `wizard-ux` into `style/` (colours, type, spacing, radius, motion) plus core components.
- [ ] **`wizard-app-builder` skill.** It knows the style, the system apps, the template and the checker, and ends every build by asking "is there a component here other apps could share?"
- [x] **Generic `wizard` CLI**: `wizard apps list --json`, `wizard tools <app>`, `wizard call <app>.<tool> --json`. Archimedes. Contract [`spec/WIZARD_CLI.md`](../spec/WIZARD_CLI.md), code `tools/wizard`, end-to-end tests `tools/tests/`.
- [ ] **`docs/CREDENTIALS.md` + break-glass kit**, after the token-sharing test (Miguel + Oscar). The kit is one "repair with any working subscription" path (Claude Code or Codex against the box) plus scripts for known failures.
- [ ] **One-button host move**: snapshot → verify → cut over → roll back.
- [x] GitHub tag: `wizard-app` (approved by James, 9 Oct).
