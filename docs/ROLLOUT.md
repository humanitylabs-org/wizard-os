# Wizard OS rollout

**9 Oct 2026.** What ships when, from the Dev Council and James's follow-up decisions. Each line has an owner and a "done when". Status: ✅ done · 🔨 in progress · ⏳ next · 💤 parked.

## Now: days 0–3 (week of 9 Oct)

- ✅ **Agent Service cutover** (Jan's repo is live). Telos runs `wizard-agent-service` @ `fc0d022` since 9 Oct 09:45 UTC; `/wizard/health` answers 200.
- ✅ **wizard-os repo**: architecture, rollout, contracts, decisions, work outstanding.
- ✅ **wizard-app-manager reference implementation** (Archimedes → Miguel). It was dogfooded on a fresh Ubuntu VM with stock Runtipi v4.9:
  - find → check → compile → Runtipi pull → install → `apps.json` → agent calls the app's MCP
  - also tested: `install.sh`, uninstall/reinstall, and the HTTP API
- ✅ **DeFleur Video in its own repo** (`defleur-video`): full history, root `wizard.md`, and a CI check that passes.
- ⏳ **Jan:** instruction injection; read `apps.json` and connect each app's MCP and skill; pointer skills; write `spec/AGENT_SERVICE_API.md`. Done when a fresh Hermes behind the service lists installed apps without being told.
- ⏳ **Miguel:** take over `wizard-app-manager`; add `wizard.md` to each app in `wizard-app-store` (it becomes the core-apps repo); move DeFleur's image build to `defleur-video`. Done when `wam catalog` lists files, transcriber, browser, secret-drop and defleur-video.
- 🔨 **James:** desktop layout in `wizard-ux`; native bridge listener (`spec/NATIVE_BRIDGE.md`). Done when Wizard for Mac's Right ⌘ orb works on `wizard-ux`.

## Days 3–7: the end-to-end test

Run the same test on three setups:
- an existing Hermes install
- a fresh Hermes install
- the Try Wizard Mac VM

The Company Wizard is spare capacity if a shared box is ever needed.

The test:
1. Wizard UX → Agent Service → Hermes.
2. Install DeFleur from the Apps screen (or `wam install defleur-video`).
3. Say "edit X from my Files with DeFleur", with no MCP hint.
4. The finished video lands in Files.
5. Any skill the agent writes is a pointer to DeFleur, not a copy.

Owner: whoever finishes their piece first runs it. Evidence goes in the PR.

## Week 2

- ⏳ **One files root, one transcription slot.** Resolve both collisions ([SYSTEM_APPS.md](SYSTEM_APPS.md)). Owners: Jan (Agent Service attachments), Miguel (Transcriber → slot).
- ⏳ **Mac payload from `wizard-ux`.** Try Wizard builds its UX payload from `wizard-ux` instead of the old `wizard-mobile`. Merge `mizel-mac` into `try-wizard` `main`. Owner: Miguel.
- ⏳ **Meeting Recorder and Reader become wizard.md apps.** Owner: Archimedes.
- ⏳ **Style tokens + `wizard-app-builder` skill** land in this repo. Owner: Archimedes, with James approving the style.
- ⏳ **Credentials test**: two harnesses sharing one ChatGPT OAuth token on one box. Result → `docs/CREDENTIALS.md` + the break-glass kit. Owners: Miguel + Oscar, write-up Archimedes.
- ⏳ **First release file**: which version of each repo goes together. Owner: Jan.

## Weeks 3–6: Mac alpha

- **Mac files in a Mac folder** (`~/Wizard`, shared into the VM). See [MAC.md](MAC.md#where-files-live).
- **Context bridge app.** Wizard reads your existing Claude Code / Codex sessions and project folders, and imports chat-app exports. See [MAC.md](MAC.md#picking-up-where-claude-or-chatgpt-left-off).
- **Apps screen in `wizard-ux`.** It replaces `tailnet-app-manager` at `/apps`.
- **One-button move to always-on** (snapshot → verify → cut over → roll back), proven Mac → VPS once.
- **Opus alone vs Opus + Hermes**: same thread, switched at the Agent Service. Archimedes runs it and James judges.

## Parked, with what unparks it

| Item | Unparks when |
|---|---|
| Vacation mode (VPS takes over, home box gets a copy) | One Mac → VPS move verified |
| Monetization (25% on the call vs 20% in the old roadmap) | ~20 apps and a first outside developer |
| Nostr app catalog / Wizard ID / friends' apps | App catalog works on GitHub; only the catalog fetcher changes |
| ~300 preloaded Runtipi apps as a separate section | Apps screen ships |
| Omarchy desktop | After the Mac |
| Android VM | Someone has a spare Pixel afternoon; the phone stays a client |
| Rugix atomic updates | Wizard Box appliance work starts |
| Spynel coordination experiment | Direct route works in daily use |
| Migration from an existing server directory | After the mass-market Mac path |

## Retire

- `tailnet-app-manager` at `/apps`: once the Apps screen ships
- `feature/apps-manager` in `wizard-mobile`
- the `server/` folder in `wizard-mobile`: the live service already runs from `wizard-agent-service`
- the Helm reads in the Agent Service
- the `wizardos` installer repo: once the end-to-end test passes on Try Wizard
- Electron as a desktop wrapper: dropped; Wizard for Mac is the shell

## How this maps to the older phase plan

The days-0–7 work above completes the old **Phase 0** (connect the pieces) and starts **Phase 1** (a usable Wizard alongside Hermes). The App Manager and Apps screen are the first half of **Phase 2** (app management). Files root and transcription slot are early slices of **Phases 4–5** (shared model services, shared files), pulled forward because apps already depend on them.
