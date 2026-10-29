# Work outstanding

Components still to build. Pick one up: put your name on it in a PR, and close it with evidence. Ordered roughly by when it's needed.

**Release labels** (every Wizard repo): `release: v1` = needed for the first release; `release: later` = future feature, parked until after it. Tag every new issue with one. Ideas for later go in as an issue labelled `release: later` + `enhancement`, never as a build. Cross-repo views: [v1](https://github.com/search?q=org%3Ahumanitylabs-org+label%3A%22release%3A+v1%22+is%3Aopen&type=issues) · [later](https://github.com/search?q=org%3Ahumanitylabs-org+label%3A%22release%3A+later%22+is%3Aopen&type=issues).

## Launch v1 core path (audit #132)

**Owner: Archimedes.** The core path is launch items [#87–#93](https://github.com/humanitylabs-org/wizard-os/issues/87) **plus audits #133–#140**, on both profiles: fresh Linux box and Mac app. The [reading map and weekly receipt template](CORE_AGENT_PATH.md) separate this launch checklist from the lower-level agent request path. Historical component receipts below do not close current launch acceptance.

- Launch items: [first chat #87](https://github.com/humanitylabs-org/wizard-os/issues/87), [phone pairing #88](https://github.com/humanitylabs-org/wizard-os/issues/88), [model connection #89](https://github.com/humanitylabs-org/wizard-os/issues/89), [updates #90](https://github.com/humanitylabs-org/wizard-os/issues/90), [backup/restore #91](https://github.com/humanitylabs-org/wizard-os/issues/91), [app set #92](https://github.com/humanitylabs-org/wizard-os/issues/92), [repair #93](https://github.com/humanitylabs-org/wizard-os/issues/93).
- Audit guardrails: [browser boundary #133](https://github.com/humanitylabs-org/wizard-os/issues/133), [box state #134](https://github.com/humanitylabs-org/wizard-os/issues/134), [release evidence #135](https://github.com/humanitylabs-org/wizard-os/issues/135), [defaults/custody #136](https://github.com/humanitylabs-org/wizard-os/issues/136), [route contract #137](https://github.com/humanitylabs-org/wizard-os/issues/137), [security inventory #138](https://github.com/humanitylabs-org/wizard-os/issues/138), [first contact/report #139](https://github.com/humanitylabs-org/wizard-os/issues/139), [daily real-use signal #140](https://github.com/humanitylabs-org/wizard-os/issues/140).
- **No scope freeze.** New work proceeds behind a profile flag or as a non-default app until promoted with tests. Each PR declares effects on frozen client fields (#137), box state (#134), updates (#135) and trust (#133).
- **Still required:** the daily architecture check-in reports merge risk, and its weekly report names core items that moved or stalled. Before launch, verify every new feature is either promoted with evidence or off by default on tester boxes. This index/template does not claim those operational checks have run.

## Account connectors and privacy routing (direction approved 15 Oct, mechanism proposed; #85)

Archimedes owns the [contract](../spec/CONNECTORS.md) and [YouTube Music + simulated-chat MVP / release checklist](CONNECTORS_MVP.md). Next: slice B (pure admission function + fixtures) and slice A (real Music account seam and uncached playback). The Account Manager / Google broker seam is for Jan to confirm; App Manager descriptor/network enforcement for Miguel/Oscar. Real credential use and private-chat activation keep their release gates. Not on the v1 critical path.

## Receives voice input (15 Oct, approved; #62)

Archimedes owns the [shell-independent contract](../spec/VOICE_INPUT.md), Wizard UX receiver/capture UX and Manager, Video Editor and Search adapters. App-owned results do not create automatic success Chats. Implementation/live acceptance is in progress; the App Manager checker/metadata/builder mirror goes through Miguel/Oscar review.

## Wizard stable Hermes (Archimedes; DECISIONS #74, [HERMES_STABLE.md](HERMES_STABLE.md))

- [x] **Pin in the snapshot** (21 Oct): `hermes` block required from 0.3.23, validated by `tools/check_release.py` offline and online (upstream tag commit, Docker Hub digest, `hermes-agent` app's `FROM`).
- [ ] **Candidate test on Thales**: fresh VM per tag, record in `docs/acceptance/hermes-<tag>.md`.
- [ ] **Weekly candidate post**: the Sunday release gate names the candidate and its blocker.
- [ ] **`wizard hermes update --stable`** for alongside boxes: backup, quiet moment, exact tag, check, automatic rollback. Built on `feature/hermes-update-stable` (`wizard hermes status|update`, [WIZARD_CLI](../spec/WIZARD_CLI.md#updating-this-boxs-hermes-alongside-mode)); fresh-VM record [acceptance/hermes-update-stable.md](acceptance/hermes-update-stable.md); ticks when the PR merges.
- [ ] **Fresh installs off `v2026.9.24`**: `hermes-agent` app moves to the first passing candidate with an image (review: app repo owner).

## Private model providers (Archimedes; DECISIONS #66, [PRIVATE_PROVIDERS.md](../spec/PRIVATE_PROVIDERS.md))

- [x] **Spec** (Archimedes, 20 Oct).
- [ ] **In-seal client, `tinfoil` profile** (Archimedes): Tinfoil SDK sidecar that encrypts inside the private agent's seal; relay capture shows no plaintext.
- [ ] **Agent Service** (Archimedes): provider = installed app id, internal networks, per-agent client tokens, provider list on the Agents page.
- [ ] **Relay mode in wizard-tinfoil** (Miguel): forward ciphertext, sole key holder, client tokens, declared egress only.
- [ ] **Local model provider app** (Archimedes).
- [ ] **Move the owner's box** (Archimedes): retire the per-agent proxy sidecar, its key copy and the `tinfoil-operator` chat route.

## Connection Router (Archimedes; DECISIONS #65, [CONNECTION_ROUTER.md](../spec/CONNECTION_ROUTER.md))

- [x] **Router app**: needs from `apps.json`, routing table, `/v1/needs`, `/v1/models/<feature>/run`, grants in report-only mode. Tested with a fake provider. Done: `wizard-app-store` `images/wizard-connection-router` (server.py serves `/v1/needs`, `/v1/models/<feature>/run`, report-only grants; `tests/fake_provider.py`), published as Router 0.1.3 (wizard-app-store #12, #13).
- [x] **Provider apps** (PRs to Miguel's repos): `wizard.ai-connection/2` model lists and `/api/infer` for Claude, then ChatGPT through a raw-inference route in the `wizard-os` Hermes plugin (no second login). Done: `wizard-app-store` `images/wizard-claude/server.py` (`wizard.ai-connection/2` status with `models.json`, `/api/infer`) and `images/wizard-chatgpt/server.py` + `inference.py` (`/api/infer` over the plugin's `/api/plugins/wizard-os/infer/chatgpt`, models from `/api/plugins/wizard-os/models/chatgpt`), released through wizard-app-store #11 and `c188760`.
- [ ] **Shell**: install sheet (connect the recommended provider or approve a swap) and per-app "Models and connections".
- [ ] **Wisdom first adopter**: ask = standard, lookup = fast, author = frontier `swap: never`; its helper service retires.
- [x] **Acceptance on Thales**: Claude only, ChatGPT only, both, neither. Done 21 Oct: 48/48 checks on a fresh Thales VM, plus a read-only check of the daily box; see [acceptance/router-2026-10-21.md](acceptance/router-2026-10-21.md). One wording fix: wisdom #34.

## Agent Service (Archimedes; DECISIONS #30, #42)

- [x] **Runs on stock Hermes** (Archimedes, 9 Oct): capability-aware runs, helper follow-through without a Hermes patch, settings/bootstrap/apps endpoints, orb router, serves Wizard UX. James's daily driver since 9 Oct; `main` = `2634564`, CI green.
- [ ] **Container port** (Archimedes, 🔨): one Runtipi app = Agent Service + Wizard UX, `wizard.md` with `provides: [shell]`; Hermes at `hermes-agent-engine:8642`; sessions read from a read-only Hermes data volume; voice via the `transcription` slot; uploads into `media/`; every host path becomes a setting. Done when it passes the end-to-end test on a fresh stock-Runtipi VM.
- [ ] **Wizard OS instruction injection.** Prepend "you are an agent inside Wizard OS" plus the installed-app summary to every agent run. Hermes stays unmodified. Built: [wizard-agent-service#2](https://github.com/humanitylabs-org/wizard-agent-service/pull/2), rebased on main, 183/183 tests; Jan to review.
- [ ] **Agent bridge** ([AGENT_BRIDGE.md](../spec/AGENT_BRIDGE.md), #40; Archimedes): `wizard` MCP gateway at `/wizard/mcp` over `apps.json`, `list_changed` on change, `wizard_apps` meta tool; kernel at `/wizard/v1/agent-context`; `wizard-os` Hermes plugin; weak-model gate. Replaces "`apps.json` reader: register each app's MCP".
- [x] **Pointer skills** (Archimedes, part of #40). One short skill per job type ("short-form video → DeFleur Video"), rebuilt from `apps.json` `provides` on every change. Done in wizard-agent-service#245: pointers send the agent to the app's shipped skill first, non-main agents get their own job list inline, and a fresh-VM run with stock Hermes and a real model routed 3/3 unnamed "make a short video" requests to the app and none after uninstall (`ops/acceptance/pointer-skills/`).
- [x] **`spec/AGENT_SERVICE_API.md`** (Archimedes, 12 Oct; [#22](https://github.com/humanitylabs-org/wizard-os/pull/22)). v1 written from shipped behaviour (wizard-agent-service `main` `f772b83`, wizard-ux `daily` `8866124`): 46 served routes plus the 4 proposed PR #7 routes and 1 gap, with discrepancies D1–D5. Evidence: `tools/check_api_contract.py --ux` maps all 63 UX requests (web + Android) onto documented routes, 0 problems; `tools/tests/test_api_contract.py` 12/12 with negative controls; `tools/api_contract_probe.mjs` 75/75 cases against an isolated service, 46/46 served routes exercised, 11 negative controls (undocumented, proposed and gap paths answer 404).
- [ ] **Current core-path launch acceptance (#132).** [CORE_AGENT_PATH.md](CORE_AGENT_PATH.md) labels the existing core versus its extensions and supplies a weekly receipt template. The historical #22 receipt above remains historical: reconcile current UX calls, isolated served-route results and the selected release's service pin before closing #132. Keep documented gaps, skips and proposed routes explicit; a checker or template existing is not a passing current run.
- [ ] **Install alongside an existing Hermes** (#41; Archimedes): `os.sh` detect + alongside mode, `wizard link / unlink / doctor`, tested on a fresh VM with stock Hermes preinstalled.
- [x] **Release file** (Archimedes). `releases/<version>.json`: the commit of each repo that goes together. Done: `releases/0.3.7.json` … `0.3.12.json` plus `releases/stable` on `main` (stable = 0.3.12, PR #76).
- [ ] **Attachments into the files root** ([SYSTEM_APPS.md](SYSTEM_APPS.md#files)).
- [ ] **Pages** ([PAGES.md](../spec/PAGES.md), #35): serve `/pages/` from `media/Pages/` with the sandbox header; list / save-with-version / history / restore API; git commit on every write; refuse `Origin: null` on `/wizard/...`; redirect James's old `/reports/<slug>/`.
- [ ] **Agent switch for the Opus-vs-Hermes test.** One thread, routed either to Hermes or straight to Opus.

- [ ] **Agent state** ([AGENT_STATE.md](../spec/AGENT_STATE.md), #43–#49), after the agent bridge lands:
  - `~/.wizard-os/agents/<id>/` layout and `agent.json`; the Hermes agent app mounts its home there.
  - Agent History system app (#102, PR #70): daily copy from each agent, sealed monthly files, conversation export, `release` then harness prune of machine sessions past `live_days`, disk forecast, `sessions_search` with `deep`; then Chats reading old threads from History, the Pi reader, grant checks and read log. v0 runs on James's box (Archimedes): copy live since 21 Oct, first scheduled-job prune 25 Oct (864 sessions, verified).
  - Agents app: owner-controlled `shared_with_agents` silo toggle, independently editable `other_agents`.
  - Agents app: split/merge diff approval and lifecycle UI ([AGENT_SPLIT.md](../spec/AGENT_SPLIT.md)); spec and procedure only for now.
  - Agent-data grants in `wizard-grants.json` and on the Apps screen.
  - Wizard scheduler (Archimedes, 🔨; #47 approved 21 Oct): jobs API, UX list, Hermes cron import for alongside mode, blueprint templates. First slice: Agent Service jobs + results posted into their thread by run id (replaces host `cron_to_chats.py`), high-frequency watchdogs move to Supervisor health checks + Notifications.
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
- [x] **Lock the App Manager API**: loopback bind, token for install/uninstall/refresh (#28). Done in code (`WAM_BIND` default 127.0.0.1, bearer in `~/.wizard-os/api-token`); see [SECURITY_INVENTORY.md](SECURITY_INVENTORY.md).
- [ ] Move DeFleur's image build and e2e scripts into `defleur-video`.
- [ ] **Thin-fork terms (#32, Miguel):** ~~frontend back to stock Runtipi~~ done 10 Oct (only the four Wizard categories remain; Wizard views in `wizard-app-manager/wizard-views/` for Wizard UX); image stays a drop-in for `runtipi/runtipi`; "Open port" fix sent upstream; index store offered upstream as a pluggable store source. Review 20 Nov 2026.
- [x] **App-to-app permissions spec**: [spec/PERMISSIONS.md](../spec/PERMISSIONS.md) v0.2, approved by James 21 Oct (#76). App → app grants only; agents stay on #58 ticks and #59 seals.
- [ ] **App-to-app grants in the App Manager** ([wizard-app-manager#8](https://github.com/humanitylabs-org/wizard-app-manager/pull/8)): grants file + per-app keys first (layer 2), then networks behind `WIZARD_APP_ISOLATION` (layer 1); install-sheet proposals; acceptance in PERMISSIONS.md. Isolation-for-stable stays deferred (spec/AGENTS.md).
- [ ] Dependency install UX: "you already have a transcriber" vs "install the recommended one". Today `uses:` installs missing dependencies silently.
- [ ] Install-time model checks and architecture mismatch messages: preserve the app's binding model/workflow contract, show missing-route requirements, and require an explicit owner override before substituting a model ([APP_WORKFLOWS.md](../spec/APP_WORKFLOWS.md), decision #63). A warning alone does not authorize execution.
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
- [ ] **Skins, palettes and swappable views** ([spec/SKINS_AND_VIEWS.md](../spec/SKINS_AND_VIEWS.md), #70–#73): palettes grouped under skins (slice 1, in build); My skin folder with `skin.js` (replaces the overlay folder); Chats as a swappable `chats` view; skins recommend views; shell opens `wam views` own versions.
- [ ] **Customize skill** so the owner's agent edits settings, layout, theme and overlay safely.
- [ ] **Move the review screens out** (Day/Week/Month) into their own view apps; the shell keeps only what every screen relies on.
- [ ] **App graph in the Apps screen** (from Miguel's Runtipi branch): interface → agent → system apps each one uses, with live status.

## Mac installer (later, once the components work together)

The Try Wizard VM that runs the whole stack on a Mac. Not started until the App Manager, Agent Service and UX work together on Linux. Owner decided then.

- [ ] Build the VM's UX payload from `wizard-ux` (the `mizel-mac` prototype ships the old `wizard-mobile` build).
- [ ] **Shared `~/Wizard` folder** mounted into the VM as the files root (virtio-fs) ([MAC.md](MAC.md#where-files-live)).
- [ ] Folder picker for read-only sharing of `~/.claude`, `~/.codex` and project folders into the VM.

## Apps (anyone)

- [x] **App-owned model consistency (#63):** Wisdom is the first repair lane: package its established Opus authoring contract, enforce the effective model and preserve prior editions on rewrite. Verify the clean-install and different-orchestrator cases; record per-app implementation evidence rather than treating the new specification as universal enforcement. Archimedes owns Wisdom and the shared contract; the builder mirror is subject to App Manager owner review. Done for Wisdom, 18 Oct, [PR #10](https://github.com/humanitylabs-org/wisdom/pull/10) at `6ec9780` on a clean Thales VM. The helper now re-asks Opus itself when a draft fails, and the skill forbids hand-built receipts. One Opus-default and two Haiku-default agents each ran the helper once, wrote no prose or receipts themselves, and all three results were admitted as `pinned`. Receipts whose prose the runner would reject on shape are now refused. One limit stays open: a receipt copied from a real one over correctly shaped prose is still admitted as `pinned`. Signed receipts are an owner decision (A/B/C in the evidence), and PR #10 is awaiting merge. ([evidence](evidence/wisdom-63-t_bf8aff5d.md), [first run](evidence/wisdom-63-t_a350c932.md))
- [ ] **Context bridge** app: read Claude Code / Codex sessions and project folders; import ChatGPT and Claude exports; MCP tools `search_past_work`, `load_project_context` ([MAC.md](MAC.md#picking-up-where-claude-or-chatgpt-left-off)).
- [ ] **Meeting Recorder** as a wizard.md app (Archimedes).
- [x] **Reader** as a wizard.md app (Archimedes). Private repo `humanitylabs-org/reader`, package in [reader PR #1](https://github.com/humanitylabs-org/reader/pull/1) (merging it publishes the image). Fresh-VM acceptance at `7146f45` with the stock one-line install: both checkers COMPATIBLE, `wam install` of the private repo, save and read a markdown item inside Wizard UX, Back stays in the app, stock Hermes adds and finds items through the wizard gateway, uninstall keeps the library (it lives in `media/Reader`), reinstall brings it back ([QA.md](https://github.com/humanitylabs-org/reader/blob/feature/wizard-app-package/QA.md)). Still open elsewhere: index listing (index repo is read-only for this account; patch on the Reader task), the launcher tile on `wam` main (loopback view URLs are dropped until the `/apps/<id>/` route lands), and two fresh-box App Manager issues the run worked around (store folder owned by root; Runtipi deletes a locally built image on install).

## Shared (Archimedes unless noted)

- [x] **Style tokens** pulled from `wizard-ux` into `style/` (colours, type, spacing, radius, motion) plus core components. Appearance v1, five skins, `tokens.json` → `tokens.css` with a drift check; demo sits on the same glass as Chats; Wisdom and a fresh generated app re-dress live in all five skins, window and full screen, on Thales (308 real-shell + 43 browser checks). [evidence](evidence/style-tokens-t_24e03d53.md). Staged in #36, awaiting James's style review.
- [x] **`wizard-app-builder` skill.** It knows the style, the system apps, the template and the checker, and ends every build by asking "is there a component here other apps could share?" Pointer in `system-skills/wizard-app-builder/`; WAM's builder takes `style/` as a hash-locked copy (wizard-app-manager#32, `wam new` app imports it byte-identically and passes the checker). [evidence](evidence/style-tokens-t_24e03d53.md). Awaiting Oscar's review.
- [x] **Generic `wizard` CLI**: `wizard apps list --json`, `wizard tools <app>`, `wizard call <app>.<tool> --json`. Archimedes. Contract [`spec/WIZARD_CLI.md`](../spec/WIZARD_CLI.md), code `tools/wizard`, end-to-end tests `tools/tests/`.
- [ ] **`docs/CREDENTIALS.md` + break-glass kit**, after the token-sharing test (Miguel + Oscar). The kit is one "repair with any working subscription" path (Claude Code or Codex against the box) plus scripts for known failures. Kit written: [`REPAIR_KIT.md`](REPAIR_KIT.md) (where every sign-in lives and how to reconnect it, the helper repair path with [`tools/repair/REPAIR_PROMPT.md`](../tools/repair/REPAIR_PROMPT.md), one recipe per known failure; #93). Open: the broken-box drill run on a fresh VM, and a review of the sign-in table after the token-sharing test.
- [ ] **One-button host move**: snapshot → verify → cut over → roll back.
- [x] GitHub tag: `wizard-app` (approved by James, 9 Oct).
