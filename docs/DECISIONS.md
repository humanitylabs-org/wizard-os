# Decisions

Newest first. **Locked** = the named owners agreed. **Approved by James, confirm** = James approved; Jan and/or Miguel still to confirm.

## 9 Oct 2026 — Wizard Dev Council and James's follow-up

| # | Decision | Status |
|---|---|---|
| 1 | Runtipi stays **stock**. Wizard adds a layer (`wizard-app-manager`) that compiles app repos into a Runtipi store and installs through Runtipi's API. No fork. | Approved by James, confirm Miguel |
| 2 | Repos: `wizard-ux` (James), `wizard-agent-service` (Jan), `wizard-app-manager` (Miguel), `wizard-os` (shared), one repo per app. | Locked on the call |
| 3 | An app is a repo with a root `wizard.md` (v0.2), stock Runtipi files, an MCP endpoint and a skill. A tag makes it found; only a passing check makes it listed. | Approved by James, confirm Miguel |
| 4 | Discovery tag: **`wizard-app`** (singular, like `obsidian-plugin` and `raycast-extension`: the tag says what one repo *is*). Nobody else uses it. `wizard-ai` stays searched during the transition. Chosen over `wizard-apps` (reads as a collection repo) and `wizardos-app` (longer, and "Wizard OS" is the developer name, not what users see). | Approved by James, 9 Oct |
| 5 | The Agent Service is a proxy that adds Wizard OS instructions; Hermes stays unmodified. It reads `apps.json` and connects each app's MCP and skill. | Locked on the call |
| 6 | Agent Service cutover to `wizard-agent-service`: done 9 Oct. | Done |
| 7 | One web UX codebase everywhere (`wizard-ux`). The desktop UX is its own paradigm in that codebase, plus a thin native desktop app for hotkeys; James + Archimedes own it. The Mac installer (the VM that runs the stack) is separate and comes later. No Electron. | Approved by James, 9 Oct |
| 8 | The Apps screen lives in `wizard-ux`. | Approved by James |
| 9 | System apps are normal apps with `system: true` that fill a slot and can be replaced. | Approved by James |
| 10 | One user-files root: Runtipi's `media/` folder (on a Mac, a Mac folder shared into the VM). Wizard attachments are saved into it. | Approved by James, confirm Jan + Miguel |
| 11 | One `transcription` slot with an OpenAI-compatible API. Wizard STT fills it and routes to providers; Speaches/Transcriber becomes its local backend. | Approved by James, confirm Jan + Miguel |
| 12 | Core packaging apps (files, transcriber, browser, hermes, secret-drop) stay together in one core-apps repo. Apps with their own code (DeFleur, Meeting Recorder, Reader) get their own repos. | Approved by James, confirm Miguel |
| 13 | No shared integration host. Test on an existing Hermes, a fresh Hermes and the Try Wizard VM. The Company Wizard is spare capacity. | James |
| 14 | `wizard-os` stays private to the org until James, Jan and Miguel agree on v0.2 of the contracts, then goes public. | Approved by James |
| 15 | Customers hear "your Wizard"; developers hear "Wizard OS". Laptop is the trial, always-on is the upgrade. | Agreed on the call |
| 16 | Nostr: app repos stay on GitHub. Nostr goes first to Wizard ID and seeing which apps friends use. | Approved by James |
| 17 | Monetization deferred until ~20 apps and a first outside developer. Settle 25% vs 20% then. | Approved by James |
| 18 | Mac files default to an outside Mac folder shared into the VM, so uninstalling Wizard never deletes them. | Approved by James (direction), details in MAC.md |
| 19 | The Mac mass-market path picks up existing Claude Code / Codex context live and chat-app history by export. | Approved by James (direction), feasibility in MAC.md |
| 20 | Vacation mode, Android VM, Omarchy, Rugix and the ~300-app catalog are parked with explicit unpark triggers (ROLLOUT.md). | Approved by James |
| 21 | Nostr discovery is added, not migrated to, in four stages with triggers: GitHub only → dual-publish when Wizard ID ships → Nostr primary at the first outside developer or ~20 apps → GRASP multi-host when GitHub actually hurts ([ROLLOUT.md](ROLLOUT.md#nostr-path-github-to-nostr-without-a-migration-day)). `wizard.md` gains optional `publisher: npub`. From stage 2, installs pin to the checked commit and updates need a re-check plus owner approval. | Approved by James |
| 22 | Wizard OS keeps one `settings.json` (owner name and place, agent name, clock, voice vocabulary) next to `apps.json`. The Agent Service owns the format and serves it with box capabilities at `GET /wizard/v1/bootstrap`; the UX hardcodes none of it. | Approved by James, 9 Oct |
| 23 | The Agent Service works with stock Hermes: it uses joined delegation when Hermes advertises it and otherwise takes the follow-up turn itself when delegated work finishes. Proven on a fresh VM with upstream Hermes. | Built 9 Oct, James to approve rollout |
