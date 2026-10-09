# System apps, slots, and the two collisions

## The rule

A **system app** is a normal Wizard app with `system: true` in its `wizard.md`. It fills a **slot**, which is a capability other apps rely on. Any app that `provides:` the same slot can replace it. `wam bootstrap` installs every system app; the Apps screen hides them by default.

| Slot | Today's default | Notes |
|---|---|---|
| `files` | Files (File Browser on Runtipi `media/`) | The one user-files root |
| `transcription` | Wizard STT (front) → Speaches/Transcriber (local backend) | OpenAI-compatible `/v1/audio/transcriptions` |
| `browser` | Browser (Chromium) | Headless + viewable |
| `notifications` | to build | |
| `microphone` | native shell (Android, Mac) | Through the native bridge, not a container |
| `secrets` | Secret Drop | One-time credential handoff |

`apps.json` lists each slot's default and candidates. Apps call the **slot**, never a named app (`TRANSCRIPTION_URL`, not `http://transcriber:8000`).

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
