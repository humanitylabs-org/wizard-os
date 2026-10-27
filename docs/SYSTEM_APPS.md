# System apps, slots, and the two collisions

## The rule: slots are parking spots

A **slot** is a job every Wizard needs done (a shell, an agent, files, transcription …). Think of it as a **parking spot**: the spot is part of Wizard OS, the app parked in it is not. Any app whose `wizard.md` says `provides: [<slot>]` can park there, and the owner can swap it at any time. A **system app** is just a normal app (`system: true`) that we publish as the **default** for a spot.

This holds for every spot, **including the shell**: Wizard UX is the default shell, not the only one. `hermes-frontend-3` or a community shell can fill the same spot.

| Slot | Default app | Required | Notes |
|---|---|---|---|
| `shell` | `wizard-ux` | yes | Exactly one active per box ([SHELL.md](../spec/SHELL.md)). Oscar's Wizard App and `hermes-frontend-3` are alternatives |
| `agent-service` | `wizard-agent-service` | yes | Headless; the `/wizard/...` API every shell talks to. Separate from the shell (#36) |
| `agent` | `hermes-agent` | yes | Any MCP-speaking agent later |
| `files` | `wizard-files` (Wizard Files on Runtipi `media/`) | yes | Approved replacement; active on the owner's box. New-box default rollout remains pending; see [adoption decision](WIZARD_FILES_DECISION.md). |
| `ai-connection` | one app per provider: `claude`, `chatgpt` (#61) | no | Many may be filled at once; each owns one provider sign-in ([AI_CONNECTIONS.md](../spec/AI_CONNECTIONS.md)). Replaces `ai-accounts` / `wizard-ai-accounts` |
| `connection-router` | `wizard-connection-router` (proposed, #65) | no | Connects apps to the models, services and agents their `wizard.md` requires; holds no provider credentials ([CONNECTION_ROUTER.md](../spec/CONNECTION_ROUTER.md)) |
| `transcription` | `transcriber` today; Wizard STT as its front later (below) | no | OpenAI-compatible `/v1/audio/transcriptions` |
| `browser` | `browser` (headless Chromium) | no | |
| `secrets` | `secret-drop` | no | One-time credential handoff |
| `private-access` | Tailscale (native host integration) | no | Preinstalled by the installer; the owner joins their own tailnet. Cloudflare Tunnel + Access is the alternative ([PRIVATE_ACCESS.md](../spec/PRIVATE_ACCESS.md)). Not yet an ordinary store app |
| `notifications` | `notifications` (ntfy, `oscarhenrycollins/notifications`) | no | Bell beside Chats search + phone push. Agents send one-way alerts with its `notify` tool; scheduled-job delivery to Notifications (`deliver: notification`, falling back to the thread when the slot is empty) is a candidate in [wizard-agent-service#130](https://github.com/humanitylabs-org/wizard-agent-service/pull/130), not shipped yet. Chats stay for conversations |
| `cloudflare-connection` | `wizard-cloudflare` (on demand) | no | Recommended in Setup; never installed by bootstrap |
| `connected-accounts` | `wizard-connectors` (on demand) | no | Recommended in Setup; unavailable until a reviewed pullable release is indexed |
| `microphone` | native shell (Android, Mac) | no | Through the native bridge, not a container |

**How it works on a box** (built in `wizard-app-manager`, `wam/defaults.json`):
- **System apps are exactly the spot defaults.** WAM writes `system: true` on each such app in `apps.json` (on a pinned box the release's `default_apps` decide), the Agent Service passes it on, and every shell draws the system ring from that flag rather than its own id list. The same set is what a Wizard OS update brings to the release's pinned commits (installed defaults are upgraded with the release).
- `wam slots` lists every spot: which app fills it, or that it's empty / has no default yet. `apps.json` carries the same list as `parking`, so the UX can show empty spots as placeholders.
- `wam bootstrap` installs the default app for every empty spot that has one, except `install: on-demand` slots. A spot already filled by another provider is left alone. ChatGPT and Claude connection apps stay preinstalled because they hold the agent's own sign-in.
- Setup has one **Recommended next** list. One tap selects the indexed immutable release through the existing owner-only Store/WAM route, waits for installation, then opens the connector's sign-in. Unpublished recommendations are visibly unavailable, never installed from an unchecked branch.
- After Setup first records `/wizard/v1/setup/seen`, it requests WAM's pull-only background prefetch. `recommended: true`, `prefetch: true` on an on-demand slot opt it in. WAM pulls the indexed recipe's images sequentially with idle I/O / nice priority; this lowers client priority, not Docker daemon bandwidth. It creates no containers, app records or credentials, and adds no Apps tiles. An interrupted request resumes when WAM restarts; `wam prefetch` retries downloads explicitly. Normal installation still works if caching fails.
- `wam uninstall` refuses to empty a **required** spot; install another provider first.
- `apps.json` `slots` records the owner's chosen default per spot when several apps provide it. Apps call the **slot**, never a named app (`TRANSCRIPTION_URL`, not `http://transcriber:8000`).
- Swapping a spot's default changes `defaults.json` (for new boxes) or the owner's choice (on one box). It never needs a new OS release.

## Collision 1: two file roots → one root {#files}

**Today:**
- Wizard keeps attachments in its own store, Wizard Files (`wizard_file_ids`, `~/.hermes/data/apps/wizard-inbox/blobs/`, content-addressed).
- The Runtipi apps share `runtipi/media/`, which the Files app browses and DeFleur reads from and writes to.
- A video you send Wizard in chat is therefore invisible to DeFleur, and a DeFleur render is invisible in Wizard Files.

**Decision:**
- The user-files root is **Runtipi's `media/` folder**. On a Mac, that folder is a Mac folder shared into the VM ([MAC.md](MAC.md#where-files-live)).
- The Files app stays its default view.
- Wizard Files keeps its content-addressed blob store as the **inbox and dedupe layer**. Every attachment that's a user file (media, documents) is also written to `media/Inbox/<date>/<name>`, and its `wizard_file_id` records that path.
- The agent gets one convention: "user files are under `/files`" (mounted read-write for the agent, read-only for apps that only read).

**Why not the other way round:**
- Every Runtipi app already mounts `media/`, and the Files app already makes it browsable from a phone.
- Wizard's blob store is an implementation detail: hashed names, no folders.
- One copy written at upload time is cheap. Rewriting every app's mounts is not.

**Who:**
- Jan: the Agent Service writes attachments into `media/Inbox` and exposes the path.
- Miguel: App Manager mounts are unchanged.

**Done when:** a video sent in a Wizard chat can be edited with DeFleur by name, and the render appears in both the Files app and the chat.

## Collision 2: two transcription services → one slot

**Today:**
- **Wizard STT** (`wizard-stt`, port 8864) is Wizard's voice core. It's OpenAI-compatible (`/v1/audio/transcriptions`), routes between providers (local whisper.cpp, cloud) chosen in Hermes config, and adds chunking and jobs. It runs on the host, not in Runtipi.
- **Transcriber** (Speaches, in Miguel's store) is a Runtipi container on port 8791. It's also OpenAI-compatible, local faster-whisper, and DeFleur uses it.

**Decision:**
- One `transcription` slot. Its contract is the OpenAI `/v1/audio/transcriptions` API, plus `verbose_json` word timestamps for apps like DeFleur that need alignment.
- **Wizard STT is the slot's front**: provider choice, chunking, jobs, and one place to set "local only" or "cloud allowed".
- **Speaches becomes Wizard STT's local backend**, replacing Wizard STT's own whisper.cpp process so there's one local model server.
- Both get `wizard.md`. Wizard STT `provides: [transcription]` with `system: true`. Speaches `provides: [speech-to-text-engine]` and is a dependency of Wizard STT.
- DeFleur's `TRANSCRIBER_URL` points at the slot.

**Why this way round:**
- Wizard STT already holds the provider and privacy choice the owner makes, and the voice UX depends on its jobs API.
- Speaches is a better-maintained local engine than a bare whisper.cpp process, and it's already packaged for Runtipi.
- Keeping both as peers would mean two model downloads, two privacy settings, and apps silently getting different transcripts.

**Check first:** DeFleur needs word timestamps. Confirm Wizard STT passes `timestamp_granularities[]=word` through to Speaches before switching DeFleur. Until then DeFleur keeps calling Speaches directly, which the slot design allows.

**Who:**
- Miguel: package Wizard STT as an app; DeFleur reads the slot.
- Jan: the Agent Service voice path reads the slot URL from `apps.json`.
- Archimedes: the backend switch in Wizard STT and the word-timestamp check.

**Done when:** one `transcription` default in `apps.json`, voice notes and DeFleur both transcribed through it, and one local model on disk.
