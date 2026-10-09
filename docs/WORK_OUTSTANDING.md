# Work outstanding

Components still to build. Pick one up: put your name on it in a PR, and close it with evidence. Ordered roughly by when it's needed.

## Agent Service (Jan)

- [ ] **Wizard OS instruction injection.** Prepend "you are an agent inside Wizard OS" plus the installed-app summary to every agent run. Hermes stays unmodified.
- [ ] **`apps.json` reader.** Watch `~/.wizard-os/apps.json` (or `GET :8790/api/apps`). On change, register each app's MCP with the agent and load its skill.
- [ ] **Pointer skills.** One short skill per job type ("short-form video → DeFleur Video"), rebuilt from `apps.json` `provides` on every change.
- [ ] **`spec/AGENT_SERVICE_API.md`.** The versioned `/wizard/...` contract the UX relies on.
- [ ] **Release file.** `releases/<version>.json`: the commit of each repo that goes together.
- [ ] **Attachments into the files root** ([SYSTEM_APPS.md](SYSTEM_APPS.md#files)).
- [ ] **Agent switch for the Opus-vs-Hermes test.** One thread, routed either to Hermes or straight to Opus.

## App Manager (Miguel)

- [ ] Take over `wizard-app-manager`, and review the reference implementation's choices (CLI token auth, git smart-HTTP store, `apps.json` v1).
- [ ] `wizard.md` for every app in `wizard-app-store`. Rename it `wizard-core-apps` when convenient.
- [ ] Move DeFleur's image build and e2e scripts into `defleur-video`.
- [ ] Dependency install UX: "you already have a transcriber" vs "install the recommended one". Today `uses:` installs missing dependencies silently.
- [ ] Install-time checks: `recommends.model` warning and architecture mismatch messages for the UX.
- [ ] Uninstall keeps data. Verify Runtipi's behaviour and add an explicit `--delete-data`.
- [x] **Nostr catalog source behind a flag** (Archimedes, 9 Oct): `wam/nostr.py`, signature-verified NIP-34 discovery, publisher rule, GitHub/Nostr de-dupe, `commit` recorded per catalog row. Off unless `WAM_NOSTR=1`. Tested against four live relays.
- [ ] **Pinned updates** (needed by stage 2): `wam update <id>` shows the commit diff, re-runs the checker, installs only after owner approval. Today a refresh moves to the latest commit.
- [ ] **Stage 2 publish tooling**: one command that posts the NIP-34 announcement for an app (GitHub clone URL, `t=wizard-app`), signed through Wizard Authority, plus the Humanity Labs curated list.

## Wizard UX, including the desktop UX (James + Archimedes)

- [ ] **Apps screen sources**: label each app Public / Beta / Local / Link; GitHub sign-in for beta apps; `wizard://install` share links ([PRIVATE_BETA.md](PRIVATE_BETA.md)).

- [x] **Desktop UX** of `wizard-ux`: one codebase, two shells. `web/core/` is shared; `desktop.html` is the Omarchy-style shell (workspaces, auto-tiling, ⌘K, ⌥ keys, ⌥V voice), picked by device so neither shell downloads the other's code. Live at `/wizard-os-home/` (`daily` 60e1489), qa-desktop 45/45. UX side of the native bridge done (v0.1).
- [ ] **Native desktop app with hotkeys** (Caps Lock Wizard key, Right ⌘ voice) driving `wizard-ux` through the [native bridge](../spec/NATIVE_BRIDGE.md). This is desktop UX work, separate from the Mac installer.
- [ ] **Apps screen**: catalog, install, open, status from the App Manager API. A separate section for plain Runtipi apps.
- [ ] Back button contract: Back never exits (see James's standing rule in `wizard-ux`).
  - Hosted app views need a spec'd Back hook in `spec/NATIVE_BRIDGE.md` and the `hello-wizard` template: the shell asks the focused app for one back step and the app answers `handled` or `not handled`, so the shell knows when to take its own step. Today `wizard-ux` bridges Legacy Wizard's `__wizardCloseOverlay` with a layout-signature guess (`LEGACY-BRIDGE` in `web/app.js`); delete that once the contract lands or Legacy Wizard retires.

## Mac installer (later, once the components work together)

The Try Wizard VM that runs the whole stack on a Mac. Not started until the App Manager, Agent Service and UX work together on Linux. Owner decided then.

- [ ] Build the VM's UX payload from `wizard-ux` (the `mizel-mac` prototype ships the old `wizard-mobile` build).
- [ ] **Shared `~/Wizard` folder** mounted into the VM as the files root (virtio-fs) ([MAC.md](MAC.md#where-files-live)).
- [ ] Folder picker for read-only sharing of `~/.claude`, `~/.codex` and project folders into the VM.

## Apps (anyone)

- [ ] **Context bridge** app: read Claude Code / Codex sessions and project folders; import ChatGPT and Claude exports; MCP tools `search_past_work`, `load_project_context` ([MAC.md](MAC.md#picking-up-where-claude-or-chatgpt-left-off)).
- [ ] **Meeting Recorder** as a wizard.md app (Archimedes).
- [ ] **Reader** as a wizard.md app (Archimedes).

## Shared (Archimedes unless noted)

- [ ] **Style tokens** pulled from `wizard-ux` into `style/` (colours, type, spacing, radius, motion) plus core components.
- [ ] **`wizard-app-builder` skill.** It knows the style, the system apps, the template and the checker, and ends every build by asking "is there a component here other apps could share?"
- [ ] **Generic `wizard` CLI**: `wizard apps list --json`, `wizard tools <app>`, `wizard call <app>.<tool> --json`.
- [ ] **`docs/CREDENTIALS.md` + break-glass kit**, after the token-sharing test (Miguel + Oscar). The kit is one "repair with any working subscription" path (Claude Code or Codex against the box) plus scripts for known failures.
- [ ] **One-button host move**: snapshot → verify → cut over → roll back.
- [x] GitHub tag: `wizard-app` (approved by James, 9 Oct).
