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
- ✅ **Miguel: every app in its own repo, listed in the index** (9 Oct). Files, Transcriber, Browser, Secret Drop, Hermes Agent, Hermes Frontend 3, AI Accounts and DeFleur are at [aiwizards.com/wizard-apps](https://www.aiwizards.com/wizard-apps).
- ⏳ **Miguel:** App Manager installs from the index and its API is locked down; move DeFleur's image build to `defleur-video`.
- 🔨 **James + Archimedes:** the desktop UX in `wizard-ux`, including the native desktop app and its hotkeys (`spec/NATIVE_BRIDGE.md`). Done when James uses it as his daily desktop Wizard.

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

### Run 1: existing Hermes (Telos), 10 Oct: job works, Wizard OS wiring missing

Synthetic 25 s talking-head clip in `media/Videos/`, hidden test thread, prompt `edit e2e-synthetic-talking-head.mp4 from my Files with DeFleur`. Stack: `wizard-ux` daily 7b766e0, `wizard-agent-service` 3709e39, `wam` + stock Runtipi, DeFleur 0.6.5-testing.

1. ✅ UX → Agent Service → Hermes: bootstrap, `/wizard/hermes` sessions and runs, health `upstream_reachable`.
2. ✅ `wam doctor` 4 PASS; `/wizard/v1/apps` lists `defleur-video`. Installed with `wam` (no Apps screen); MCP-only, so no tile or capability row in the UX.
3. ✅ by workaround: the agent found DeFleur by grepping the box and `apps.json`, then hand-wrote an MCP client. No Wizard OS instructions, no MCP registered with Hermes. A fresh Hermes would fail here.
4. ✅ / ❌ Render (1080x1920, 19.7 s, delivery gate pass) landed in `media/Videos/Edited/`, but the UX Files tile on Telos opens the legacy file browser, which doesn't show `media/`.
5. ✅ (vacuous): no skill written; no pointer-skill mechanism exists yet.

Gaps, owner, smallest fix:
- **Instruction injection** (Jan): apps.json block appended to every run. Fix proposed in [wizard-agent-service#2](https://github.com/humanitylabs-org/wizard-agent-service/pull/2) (not merged).
- **apps.json reader / MCP registration** (Jan): register each app's `mcp.url` with Hermes on change.
- **Pointer skills** (Jan): one ~10-line skill per `provides` job, rebuilt on change.
- **Files tile shows the files root** (James + Archimedes for the tile; Miguel for the `files` app): install Runtipi Files, point the tile at it.
- **Capabilities row, then the Apps screen** (James + Archimedes).
- **App Manager API lock** (Miguel, #28): `:7790` binds 0.0.0.0 and `apps.json` advertises public-IP MCP urls.
- **Dependencies in `apps.json`** (Miguel): transcriber and browser are installed by `uses:` but not listed.

Run 2 (fresh Hermes) is the real gate for the first three items.

## Week 2

- ⏳ **One files root, one transcription slot.** Resolve both collisions ([SYSTEM_APPS.md](SYSTEM_APPS.md)). Owners: Jan (Agent Service attachments), Miguel (Transcriber → slot).
- ⏳ **Meeting Recorder and Reader become wizard.md apps.** Owner: Archimedes.
- ⏳ **Style tokens + `wizard-app-builder` skill** land in this repo. Owner: Archimedes, with James approving the style.
- ⏳ **Credentials test**: two harnesses sharing one ChatGPT OAuth token on one box. Result → `docs/CREDENTIALS.md` + the break-glass kit. Owners: Miguel + Oscar, write-up Archimedes.
- ⏳ **First release file**: which version of each repo goes together. Owner: Jan.

## Later: Mac installer (after the components work together)

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
| Nostr app discovery, stages 2–4 ([below](#nostr-path-github-to-nostr-without-a-migration-day)) | Stage 2: Wizard ID ships. Stage 3: first outside developer or ~20 apps. Stage 4: GitHub actually hurts |
| ~300 preloaded Runtipi apps as a separate section | Apps screen ships |
| Omarchy desktop | After the Mac |
| Android VM | Someone has a spare Pixel afternoon; the phone stays a client |
| Rugix atomic updates | Wizard Box appliance work starts |
| Spynel coordination experiment | Direct route works in daily use |
| Migration from an existing server directory | After the mass-market Mac path |

## Nostr path: GitHub to Nostr without a migration day

Approved by James, 9 Oct 2026 ([DECISIONS](DECISIONS.md) #16, #21). Nostr is **added** as a discovery source and GitHub shrinks to one place the code is hosted. Nothing moves on a set date. Only the App Manager's catalog fetcher changes; `wizard.md`, the compiled store and `apps.json` stay the same.

Why bother: a GitHub topic is public and unsigned, so anyone can tag a repo (`wizard-ai` already has an unrelated one). A Nostr announcement (NIP-34, kind 30617, hashtag `t=wizard-app`) is **signed by its publisher**, and signed lists give us curated stores and friends' apps. That's the trust layer.

| Stage | Unparks when | What changes | Owner |
|---|---|---|---|
| 1. GitHub only | now, until the v0.2 contracts go public | Apps use the approved `wizard-app` topic (on Nostr, the same `wizard-app` hashtag). Keep the catalog fetcher pluggable. The Nostr source exists in `wam` behind a flag (off). | Miguel |
| 2. Dual-publish | **Wizard ID ships** (the phone-signing slice) | `wizard.md` gains optional `publisher: npub1…`. Publishing an app also posts a NIP-34 announcement whose `clone` URL is still GitHub. `wam` reads both sources, lists the same repo once, and skips any Nostr-found app whose signer isn't the declared publisher. Humanity Labs signs the official list. | Miguel (App Manager), Archimedes (publish tooling) |
| 3. Nostr primary | **first outside developer or ~20 apps** (same trigger as monetization) | Nostr announcements and signed lists become the main catalog. The Apps screen shows verified publishers and the apps friends use. GitHub topic search stays as a fallback. | Miguel + James (Apps screen) |
| 4. Multi-host | **GitHub actually hurts**: a takedown, rate limits, private-repo cost, or developers who won't use it | Apps add a GRASP clone URL beside GitHub's (`relay.ngit.dev`, `gitnostr.com`, or our own). GitHub becomes one copy of several. | App authors; we run one GRASP host |

**Rule from stage 2 on: pin installs, gate updates.** On Nostr, a publisher's key is write authority over every copy of their repo; one signed state event can rewind a branch on every host within seconds. So installs pin to the exact commit the checker passed (the catalog already records `commit`), and an update only lands after it re-passes the checker and the owner approves it. Never auto-follow the latest signed state.

## Retire

- `tailnet-app-manager` at `/apps`: once the Apps screen ships
- `feature/apps-manager` in `wizard-mobile`
- the `server/` folder in `wizard-mobile`: the live service already runs from `wizard-agent-service`
- the Helm reads in the Agent Service
- the `wizardos` installer repo: once the end-to-end test passes on Try Wizard
- Electron as a desktop wrapper: dropped; Wizard for Mac is the shell

## How this maps to the older phase plan

The days-0–7 work above completes the old **Phase 0** (connect the pieces) and starts **Phase 1** (a usable Wizard alongside Hermes). The App Manager and Apps screen are the first half of **Phase 2** (app management). Files root and transcription slot are early slices of **Phases 4–5** (shared model services, shared files), pulled forward because apps already depend on them.
