# Launch v1 and the tracks after it

**James, 20 Oct 2026 (logged 23 Oct).** This is the answer to "what should we be focusing on now?". Launch v1 comes first. The tracks below are the broad areas we work on once it ships. Pick work from a track only when it doesn't slow launch v1.

## Now: launch v1

Four people outside the core build loop (Robert, Miguel, Jan, Novaire; [#29](https://github.com/humanitylabs-org/wizard-os/issues/29)) install Wizard on their own Mac or box. They chat, use it from their phone, install an app, survive an update and restore a backup. A public release comes after that.

| # | Must-have | Issue |
|---|---|---|
| 1 | Install to a first chat (Linux one-line install and the Mac app) | [#87](https://github.com/humanitylabs-org/wizard-os/issues/87) |
| 2 | Phone access for any owner (QR or address, no owner host in source) | [#88](https://github.com/humanitylabs-org/wizard-os/issues/88) |
| 3 | Model connection on first run (Claude by default, clear reconnect) | [#89](https://github.com/humanitylabs-org/wizard-os/issues/89) |
| 4 | Updates that don't strand people (exact pins, retry, truthful rollback) | [#90](https://github.com/humanitylabs-org/wizard-os/issues/90) |
| 5 | Backup and restore (one encrypted file, logins included) | [#91](https://github.com/humanitylabs-org/wizard-os/issues/91) |
| 6 | Launch app set (Chats, voice, Files, Store and 3–4 strong apps) | [#92](https://github.com/humanitylabs-org/wizard-os/issues/92) |
| 7 | A way back when it breaks (Troubleshooter on every box and a repair kit) | [#93](https://github.com/humanitylabs-org/wizard-os/issues/93) |

The architecture audits that protect this path are #132–#140. The map of who owns what is [#25](https://github.com/humanitylabs-org/wizard-os/issues/25).

## After launch: tracks

Each track is a broad area that holds many projects. New ideas go under one of these tracks, tagged `release: later`.

1. **Privacy.** A private agent anyone can set up. Transcripts are redacted by the private agent before the main agent sees them. Next, the main model teaches the private model until it processes transcripts well enough. Then private by default: most conversations pass through the private pipeline before handoff. Each stage has a quality bar it must pass before the next stage starts. Next project: **Wizard Notes sharing.** Notes is private by default: the whole vault joins the private agent only. The owner can share single notes or whole folders with a standard agent on an ongoing basis, for example an `Archimedes` folder where anything moved in is readable and editable by Archimedes, so they write notes together. Moving a note into a shared folder triggers a redaction pass first: the private agent marks what you may want to remove (Airlock-style), you approve or edit, then it is shared. Access is per agent and per path, revocable, and everything outside shared paths stays private. `release: later`.
2. **Apps and builders.** Grow the catalogue. Owners customise an app's screens against the same data ([#30](https://github.com/humanitylabs-org/wizard-os/issues/30)). Publisher profiles. The goal is the first outside developer.
3. **Voice and presence.** The side button on the shared recorder, the voice engine comparison, and native desktop hotkeys.
4. **Always-on.** A one-button move from a Mac to a home box or the VPS, vacation mode, and Wizard hardware.
5. **Bringing your history in.** A context-bridge app that imports Claude Code, Codex and ChatGPT history. This is the biggest "wow" in the first ten minutes, so it may move ahead of the others.
6. **Models and cost.** More routes in the Connection Router (ChatGPT, private providers). Prove that cheaper models are good enough (the lean-agent bake-off).
7. **Identity and network.** Wizard ID, Messenger between Wizards, social.
8. **Business.** Hosting, the Store revenue share and business setup. This waits for about 20 apps and a first outside developer (DECISIONS #17).
