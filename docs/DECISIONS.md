# Decisions

Newest first. **Locked** = the named owners agreed. **Approved by James, confirm** = James approved; Jan and/or Miguel still to confirm.

## 11 Oct 2026 — James: Archimedes owns the Agent Service; agent bridge; install alongside Hermes

| # | Decision | Status |
|---|---|---|
| 40 | **Agent bridge** ([spec/AGENT_BRIDGE.md](../spec/AGENT_BRIDGE.md)). Leaves the app spec unchanged: apps still ship MCP plus a skill, with no per-app CLIs. The Agent Service's half has three pieces. (1) **Discovery by skills:** one generated pointer skill per job plus each app's shipped skill, read through `skills.external_dirs`, so apps appear in the agent's normal skills list and load on demand. (2) **Calling through one `wizard` MCP gateway:** `<app>__<tool>`, one config entry, `tools/list_changed` on install. App tools stay deferred behind Hermes' Tool Search, so no app's schema goes into every session. (3) **A fixed, short Wizard OS kernel with no app list**, delivered by a stock Hermes plugin (system-prompt section) or per-run instructions for other harnesses. Release gate: a flash-tier model makes the right first app call in 7 of 8 plain requests, and session tokens stay flat as apps are added. | Proposed by Archimedes, revised after James's review 11 Oct (no per-session app list); James to confirm |
| 41 | **Install alongside an existing Hermes first** (option A). `os.sh` detects a running Hermes and installs Wizard OS next to it: the Agent Service points at the host Hermes, the `agent` slot is "external", and linking is three reversible stock-config edits recorded in `~/.wizard-os/linked.json` (`wizard unlink` undoes them). Migrating Hermes into Wizard OS (option B) comes later as its own command. | James |
| 42 | **Agent Service items move from Jan to Archimedes** (apps.json reader, pointer skills, API spec, release file). Archimedes builds; no review gate on Jan. Applies to wizard-os#6 (permissions) too: Archimedes reviews it against the agent bridge. | James |

## 10 Oct 2026 (night) — James: publisher identity and Wizard ID

| # | Decision | Status |
|---|---|---|
| 38 | **Amends #16 and #21.** **Who made an app = a Nostr identity, from v0.2.** Code stays on GitHub. Several agents and people commit to one repo (Telos, defleur-agents, oscarhenrycollins), so the GitHub owner says little about whose app it is. Publishing an app means signing a NIP-34 announcement with the publisher's `npub`. The store shows that person's name and photo, and tapping the name lists their apps. Credit needs both sides: `wizard.md` names `publisher:` (proves control of the repo) **and** that key signs an announcement whose `clone` and `euc` match the repo (proves control of the key). Co-authors and the publisher's Wizard are `maintainers`. Apps with no claim show "GitHub: *owner*". Downloads still come from GitHub at the checked commit. Stages 3–4 of #21 (Nostr as the main catalog, GRASP hosting) keep their triggers. | Approved by James; Miguel to confirm (index + `wam`) |
| 39 | **Wizard ID is built into the Wizard app.** Nobody installs a separate signer app such as Amber. The key is created on the phone in `ai.wizards.os` and wrapped by a biometric/PIN-gated Android Keystore key. It is backed up through Android's own "save password" sheet to the phone's password manager, and the app reads it back once to confirm. A lost key can't be reset. Every owner signature goes through a native sheet whose wording is generated from the event itself. The web UX can ask for a signature through the bridge but never touches the key. Desktop devices route requests to the phone. Contract: [spec/WIZARD_ID.md](../spec/WIZARD_ID.md). | Approved by James; Jan to review the key handling and bridge |

## 10 Oct 2026 (night) — Miguel: agent service is its own app; public by default

| # | Decision | Status |
|---|---|---|
| 36 | **Agent Service and shell are two apps, not one.** `wizard-agent-service` is a headless system app filling its own `agent-service` slot (its `/wizard/...` API on a box-only port). `wizard-ux` is a view app filling the `shell` slot, `uses: [agent-service]`, serving its static files and passing `/wizard/...` through. Any other shell (Oscar's Wizard App, `hermes-frontend-3`, community shells) can use the same Agent Service, and the Agent Service can be swapped without touching the shell. Updates #30's packaging ("one Runtipi app"); the container work in wizard-agent-service#3 carries over, split in two. | Miguel |
| 37 | **Public by default.** Every Wizard app repo is public from its first commit, tagged `wizard-app`, and published to the index, so anyone can install it from the App Store straight away. Private only with a stated reason (customer data, secrets). | Miguel |

## 10 Oct 2026 (night) — James: pages, not apps, for things to look at

| # | Decision | Status |
|---|---|---|
| 35 | **Pages.** What the agent makes for its owner to look at (reports, write-ups, dashboards, previews, storyboards, docs to edit together) is a **page**, not an app: a folder at `media/Pages/<slug>/` with a `page.json`, served by the Agent Service at `/pages/<slug>/` behind a sandbox header, and versioned in one git repo over `media/Pages/`. A page with changing data is still a page; a job rewrites its `data.json`. It becomes an app only when it needs its own process, database, MCP or other people's installs. Amends [SHELL.md](../spec/SHELL.md) ("new screens are views (new apps)"). Spec: [PAGES.md](../spec/PAGES.md). | Proposed by James; Jan (Agent Service API) and Miguel (files root) to confirm |

## 10 Oct 2026 (night) — James: app icons are sigils

| # | Decision | Status |
|---|---|---|
| 33 | **Every Wizard app's icon is a sigil**: one solid silhouette, one bite of negative space, one colour per app, on a dark glass tile. The guide, glyph library, colour registry and icon exporter live in [`style/ICONS.md`](../style/ICONS.md) and [`style/sigils/`](../style/sigils/). A new app claims a glyph and a free hue in the registry and ships the exported icon files; no emoji, letters or stock icons. `wizard-ux` draws the same sigils live in the launcher. | Locked (James owns `style/`) |

## 10 Oct 2026 (evening) — Miguel: thin Runtipi fork

| # | Decision | Status |
|---|---|---|
| 32 | **Answers #31; replaces #1 and #23 on the Runtipi question.** The App Manager is a **thin fork** of Runtipi (`wizard-app-manager`), not stock. Stock can't do two things Wizard needs: **permissions between apps** (Runtipi puts every app on one shared network, `runtipi_tipi_main_network`, so any app can reach any other; enforcing "A may use B" means choosing each app's networks inside Runtipi's compose builder) and **installing straight from the index** without a sync job that mirrors apps into a local store. Upstream is active but mostly one maintainer (about 148 of 170 human commits in the past year; a release every one to three months), so rebasing is cheap and we shouldn't wait on upstream for permissions. **Thin** means: the fork carries only a small backend patch (index store, Wizard categories, permission-aware networking); its frontend returns to stock Runtipi as the admin/break-glass screen; the Wizard views live in `packages/frontend/src/wizard-views` for the shell's Apps screen (#8 stands, one Apps screen); the "Open port" fix goes upstream and leaves the fork once merged; each Runtipi release is rebased, built by CI and smoke-tested; source stays public (GPL-3.0). #3 stands with one change: an app installs from its `wizard.md` plus Runtipi files, and the App Manager writes the Runtipi config. Discussion: [wizard-app-manager#6](https://github.com/humanitylabs-org/wizard-app-manager/issues/6). **Approved with these terms:** `install.sh` keeps stock Runtipi as the default until the frontend is back to stock; the image stays a drop-in for `runtipi/runtipi` (same data dir and database, no fork-only migrations), so any box returns to stock by changing the image tag; the index store is offered upstream as a pluggable store source; permissions get a spec, with Jan, before networking code lands. **One review on 20 Nov 2026** (or before the first client box, if that comes first): frontend back to stock, cost of the last rebase, upstream's answer. If those look fine, the fork stays. | Miguel; **approved by James 10 Oct** ([PR #4](https://github.com/humanitylabs-org/wizard-os/pull/4)) |

## 10 Oct 2026 — James: shell, Agent Service owner, stock Runtipi

| # | Decision | Status |
|---|---|---|
| 29 | **The shell.** `wizard-ux` is the system front end and fills a `shell` slot (`system: true`, `provides: [shell]`). Every box has exactly one active shell; the App Manager never removes the last one. Other screens are views (normal apps). Owners customize through settings, layout, theme and overlay files that survive updates, never by forking the shell ([spec/SHELL.md](../spec/SHELL.md)). Theme and overlay are later work. | Proposed by James |
| 30 | **Agent Service container port: Archimedes**, with Jan reviewing. Package `wizard-agent-service` + `wizard-ux` as one Runtipi app that talks to the `hermes-agent` app; Jan keeps the `/wizard/...` API contract. `main` is now the stock-Hermes build James runs daily (`2634564`). | James |
| 31 | **Re #1 and wizard-app-manager#5 (Runtipi fork).** Proposal to keep Runtipi stock: the index-backed store moves into `wam`, the Wizard UX Apps screen becomes the place to browse and install, Runtipi's dashboard stays admin/break-glass, and the "Open port" fix goes upstream. Discussion: [wizard-app-manager#6](https://github.com/humanitylabs-org/wizard-app-manager/issues/6). | Proposed by James; Miguel + Oscar to answer |

## 9 Oct 2026 (evening) — Miguel: index, one repo per app, categories

| # | Decision | Status |
|---|---|---|
| 23 | Confirms #1 (stock Runtipi, no fork) and #3 (an app = `wizard.md` + stock Runtipi files + MCP + skill). | Miguel; **#1 part replaced by #32** |
| 24 | **One shared index instead of per-box GitHub search.** Per-box search tops out at 100 apps today and 1,000 at best (GitHub's search cap), and every box re-clones every app. The index ([apps.aiwizards.com](https://apps.aiwizards.com), Cloudflare Worker + D1) takes publishes (API, webhook, or the app's own GitHub Action) and crawls the `wizard-app` topic in date slices as a fallback. It's a rebuildable cache; the repos stay the source of truth. Nostr becomes a third way into the same publish path. Boxes fetch only the apps they install. | Miguel |
| 25 | **Replaces #12:** no core-apps repo. Every app is its own repo, Humanity Labs apps included; "core" is a slot plus a defaults list, not a property of an app. Files, Transcriber, Browser, Secret Drop, Hermes Agent, Hermes Frontend 3 and AI Accounts were split out with history on 9 Oct and are listed. | Miguel |
| 26 | `wizard.md` gains optional `category` (agent / interface / app / system, the store shelf) and `icon`. The checker also refuses host-level container access (spec rule 12). | Miguel |
| 27 | Apps whose upstream image has no MCP get a small stdlib MCP front container in front of the unchanged image ([spec](../spec/WIZARD_MD.md#mcp-for-apps-that-dont-ship-one)). | Miguel |
| 28 | The App Manager API binds to the box only (loopback); install/uninstall need a token. Tailscale and Cloudflare Tunnel both reach the UX, never the App Manager. | Miguel |

## 9 Oct 2026 — Wizard Dev Council and James's follow-up

| # | Decision | Status |
|---|---|---|
| 1 | Runtipi stays **stock**. Wizard adds a layer (`wizard-app-manager`) that compiles app repos into a Runtipi store and installs through Runtipi's API. No fork. | **Replaced by #32** (thin fork) |
| 2 | Repos: `wizard-ux` (James), `wizard-agent-service` (Jan), `wizard-app-manager` (Miguel), `wizard-os` (shared), one repo per app. | Locked on the call |
| 3 | An app is a repo with a root `wizard.md` (v0.2), stock Runtipi files, an MCP endpoint and a skill. A tag makes it found; only a passing check makes it listed. | Approved by James; confirmed by Miguel (#23) |
| 4 | Discovery tag: **`wizard-app`** (singular, like `obsidian-plugin` and `raycast-extension`: the tag says what one repo *is*). Nobody else uses it. `wizard-ai` stays searched during the transition. Chosen over `wizard-apps` (reads as a collection repo) and `wizardos-app` (longer, and "Wizard OS" is the developer name, not what users see). | Approved by James, 9 Oct |
| 5 | The Agent Service is a proxy that adds Wizard OS instructions; Hermes stays unmodified. It reads `apps.json` and connects each app's MCP and skill. | Locked on the call |
| 6 | Agent Service cutover to `wizard-agent-service`: done 9 Oct. | Done |
| 7 | One web UX codebase everywhere (`wizard-ux`). The desktop UX is its own paradigm in that codebase, plus a thin native desktop app for hotkeys; James + Archimedes own it. The Mac installer (the VM that runs the stack) is separate and comes later. No Electron. | Approved by James, 9 Oct |
| 8 | The Apps screen lives in `wizard-ux`. | Approved by James |
| 9 | System apps are normal apps with `system: true` that fill a slot and can be replaced. | Approved by James |
| 10 | One user-files root: Runtipi's `media/` folder (on a Mac, a Mac folder shared into the VM). Wizard attachments are saved into it. | Approved by James, confirm Jan + Miguel |
| 11 | One `transcription` slot with an OpenAI-compatible API. Wizard STT fills it and routes to providers; Speaches/Transcriber becomes its local backend. | Approved by James, confirm Jan + Miguel |
| 12 | Core packaging apps (files, transcriber, browser, hermes, secret-drop) stay together in one core-apps repo. Apps with their own code (DeFleur, Meeting Recorder, Reader) get their own repos. | **Replaced by #25** |
| 13 | No shared integration host. Test on an existing Hermes, a fresh Hermes and the Try Wizard VM. The Company Wizard is spare capacity. | James |
| 14 | `wizard-os` stays private to the org until James, Jan and Miguel agree on v0.2 of the contracts, then goes public. | Approved by James |
| 15 | Customers hear "your Wizard"; developers hear "Wizard OS". Laptop is the trial, always-on is the upgrade. | Agreed on the call |
| 16 | Nostr: app repos stay on GitHub. Nostr goes first to Wizard ID and seeing which apps friends use. | Approved by James |
| 17 | Monetization deferred until ~20 apps and a first outside developer. Settle 25% vs 20% then. | Approved by James |
| 18 | Mac files default to an outside Mac folder shared into the VM, so uninstalling Wizard never deletes them. | Approved by James (direction), details in MAC.md |
| 19 | The Mac mass-market path picks up existing Claude Code / Codex context live and chat-app history by export. | Approved by James (direction), feasibility in MAC.md |
| 20 | Vacation mode, Android VM, Omarchy, Rugix and the ~300-app catalog are parked with explicit unpark triggers (ROLLOUT.md). | Approved by James |
| 21 | Nostr discovery is added, not migrated to, in four stages with triggers: GitHub only → dual-publish when Wizard ID ships → Nostr primary at the first outside developer or ~20 apps → GRASP multi-host when GitHub actually hurts ([ROLLOUT.md](ROLLOUT.md#nostr-path-github-to-nostr-without-a-migration-day)). `wizard.md` gains optional `publisher: npub`. From stage 2, installs pin to the checked commit and updates need a re-check plus owner approval. | Approved by James |
| 22 | Private beta sharing uses GitHub visibility: private repo = just me, private repo + invited collaborators = beta, public = everyone. Same `wizard.md` check at every level; the Apps screen labels each app's source ([PRIVATE_BETA.md](PRIVATE_BETA.md)). | Proposed by Archimedes, James to confirm |
