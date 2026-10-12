# Wizard OS · Stock integration

**Status: locally staged proposal, awaiting James’s approval to implement.** This lane changes no service, host, released image or approved spec. Daily remains intact.

## What audit item 4 means

A successful installer does not yet guarantee that the existing Hermes can use everything the phone sends it. A file can be stored under a name meaningful only inside a container; the phone can say voice is available while another status endpoint says unavailable; a background helper’s answer can sit in its conversation without triggering the final reply. These are small Wizard adapter/packaging seams, addressable while keeping Hermes stock.

**Recommendation: implement the three slices below on isolated branches, then verify the candidate containers on Thales before cohort rollout.** Approval would authorize candidate implementation/testing only. Coordinator/release authority retains integration and promotion.

## Verified now

- **Main versus published image:** Agent Service main is `f772b830ec4f3ba1faff885f8a66914b6010f062`. Anonymous GHCR readback resolves `wizard-shell:0.2.0` to index digest `sha256:e84d005431c2349cac708d7678d2c563ad9110437e36c23275b0a6d57ff5e03f`. The amd64 image’s downloaded **server source layer**, not an executed image, contains `service.mjs`, `hermes-http-readers.mjs` and `media-files.mjs` byte-identical to fresh main. Its screen-context and silent-recording fixes are absent. The other architecture was not source-extracted.
- **Daily only:** deployed Agent Service `4f9f85f8e47afbff9f740556b87f3f9ce7dfb247` preserves the bounded screen note and turns a transcriber’s “No speech detected” response into a graceful `200/no_speech`. The same isolated requests against main discard the screen note and return `502` for silence. Bring these fixes forward onto current main; daily predates newer HTTP readers/bridge work and is not a replacement base.
- **Files:** main already supports distinct `mediaRoot` and `agentRoot`. A synthetic bind-mount analogue reproduced an unreadable host path when those namespaces disagree, and byte-exact readback when `agentRoot` names the host folder. Alongside PR12’s approved head `46f63f23d3c6fcc203a29120fdf51b57a5464fb9` does not override the recipe’s `WIZARD_MEDIA_AGENT_ROOT: /media`.
- **Local voice:** in both main and daily fixtures, an OpenAI-compatible transcriber offering `/v1/models` and no `/health` yields bootstrap `voice:true` but `/wizard/voice/status` returns `503`. Daily’s actual configured voice endpoints answer successfully; this does not certify the cohort’s local transcriber.
- **Background results:** main finds a fresh completion from a long-running job. It misses a completion left unread through a service outage exceeding two hours, a completion beyond its first 100 sessions, and an assistant-prefix thread. The two-hour limit measures recent activity/completion, **not job duration**. Daily has broader prefix handling but retains a two-hour scan bound; its reader differs from main’s HTTP implementation.
- **History:** the Wizard HTTP reader drops a stock CLI thread and a 40-day-old pinned thread in fixtures. The CLI omission is a Wizard filter, not a stock Hermes inability. Stock `/api/sessions` backfills pins but does not expose a general archive-list option in the examined handler. Restricted mode’s archive/title/other-surface limits must remain visible; mounting the whole Hermes home to expand history is an existing owner opt-in that also exposes credentials.

## Three bounded implementation proposals

### 1. Make files handed to existing Hermes readable

**Lead: Archimedes future stock adapter owner. Packaging edits belong to Modular shell/release owner; Miguel’s WAM changes remain draft candidates.**

- Files/seams: WAM `wam/alongside.py:shell_override`; split Service compose/env; Agent Service `server/media-files.mjs` and `server/index.mjs`. Preserve service `WIZARD_MEDIA_ROOT=/media`; set `WIZARD_MEDIA_AGENT_ROOT` to the detected host Runtipi media absolute path. The index path stays inside Service-owned persistent state. Existing mapping code needs no new transfer protocol.
- APIs: `POST /wizard/files/upload`, `GET /wizard/files` and `GET /wizard/files/:id/content`; resolve `wf_…` IDs server-side into Hermes-readable paths for `POST /wizard/hermes/v1/runs`. Browser URLs remain same-origin and never reveal the host path. If Hermes executes file tools in a sandbox/container, preflight must establish that runtime’s actual media mount rather than assuming host-process access.
- Acceptance on an isolated Ubuntu VM on Thales: upload a real text file and PDF from the candidate UX; actual existing-Hermes tool read returns sentinel bytes/hash; app Files sees the same upload; attachments persist after Service restart. Repeat with separate service/host paths and restricted history mode. Dependency: packaging exposes media env/mount seam; app-installation owner retains file/open proxy authentication and same-origin routing.

### 2. Bring phone voice and screen context to released parity

**Lead: Archimedes future stock adapter owner; Modular shell packages the resulting Service commit. App store preview retains visual ownership.**

- Files: `server/service.mjs` and focused tests; reconcile `spec/AGENT_SERVICE_API.md` only as a proposed contract update until approved. Forward-port daily `clientViewContext` from `feature/client-view-context@4f9f85f8e47afbff9f740556b87f3f9ce7dfb247`, and graceful no-speech handling from `fix/voice-no-speech@1a1dba74a6cd0563611d75c68082f20200afbb45`, onto current main. Use one readiness helper for bootstrap/status: a usable transcription endpoint/model is the relevant condition, not an unrelated `/health` requirement.
- APIs: `/wizard/v1/bootstrap`, `/wizard/voice/status`, `/wizard/voice/transcribe` and direct/queued `/wizard/hermes/v1/runs`. Server-owned instructions remain controlling; accept only the bounded `[Wizard OS context]` note as background context. Report missing models honestly and retain genuine audio-format/provider errors.
- Acceptance on Thales: installed local Transcriber model; status and bootstrap agree; real AAC and browser recording transcribe; silence ends cleanly; missing model is unavailable. Direct and queued requests preserve screen context, including voice outbox/reply/new-thread paths. Verify actual agent screen identification in an isolated conversation with daily model/provider/runtime parity. Dependencies: local-STT recipe/origin and current UX voice contract; no changes to daily or participant hosts.

### 3. Finish background work in the right thread after downtime

**Lead: Archimedes future stock adapter owner. Coordinator owns one active admission controller per target.**

- Files: `server/hermes-http-readers.mjs:createFollowThroughFinder`, `server/delegation-follow-through.mjs`, existing `server/run-queue.mjs` persistence/replay seam and focused tests. Page stock HTTP sessions, preserve root/live-tip lineage, cover the supported Wizard thread prefixes, and keep unfinished completion identities durably until answered or explicitly interrupted. Remove the two-hour discovery expiry for outstanding Wizard completions. Reuse admission’s stable `(session, completion-message)` idempotency key across restart.
- APIs: authenticated `/api/sessions?limit=…&offset=…`, latest-message reads and `/v1/runs` admission/status. Only the owning Wizard conversations receive continuation; CLI history inclusion is a separate display policy. Keep stock `joinedDelegation=prefer` and the existing detached follow-through mechanism.
- Acceptance on Thales: fresh result from a >2h job; a **persisted completion row** delivered while Service is offline >2h; result at session 101; assistant-prefix and compressed-root threads; Service restart before/after continuation admission; competing retry. Each discovered completion yields one final reply in its originating thread, or an explicit durable interrupted state for a **tracked, admitted continuation** whose Hermes owner dies. Include an intervening human turn so an old completion cannot overwrite the new conversation purpose. Dependencies: Service persistent queue volume and one controller; no core Hermes fork.
- Scope boundary: **Hermes death before a detached child creates its completion row is not covered by completion-message tracking.** Its parent run may already be terminal. Certifying interruption or recovering that child requires a separately established durable detached-work identity/observable; this slice makes no such guarantee. Service downtime with an existing completion, restart of an admitted continuation, and pre-completion Hermes death are distinct cases.

## Stock compatibility and release minimum

Examined exact official source refs: `v2026.9.24@e3dd27e`, latest release `v0.21.7@00f6931`, and upstream main `3f2abce` fetched 12 October. All examined sources provide run submission/status/events/steer/approval and session resources; joined delegation and Markdown-rendering extensions are absent. `audio_api` and `realtime_voice` are explicitly false: Wizard’s separate transcription adapter supplies dictation. The required plugin install flags and system-prompt registration API exist in the inspected sources; current upstream also supports `skills.external_dirs`.

This is **source compatibility, not a certified per-host support matrix**. Before cohort edits, the release owner should collect the exact version/home/profile/runtime and authenticated capability response, plus existing link/unlink checks. Missing capabilities explain unavailable controls; bootstrapping hardcoded `approvals:true/steer:true` is not verification. Telos’s live API advertises the required core features without join/Markdown extensions, but its custom installation is not evidence of another user’s stock host. No participant VPS was inspected here.

The useful minimum is file readback + voice/context parity + restart-safe continuation, with restricted history clearly explained. Preserve existing history opt-in. Retain old pins in the display reader when implementing that focused parity fix; defer broader CLI/archive browsing beyond clear disclosure. Public management routes and installed-app refresh remain the App installation lane’s existing responsibility. PR15 stays parked for the single Wizard gateway.

## Evidence, ownership and limits

Machine-readable receipts live one directory above this isolated clone: `refs.json`, `probe-main.json` (9 results), `probe-daily.json` (3 results), `published-source-evidence.json`, `published-image-config.json`, `stock-source-compatibility.json`, `stock-static-features.json`, `live-telos-capabilities.json` and `coordination.json`. `probes.mjs` reproduces the fixture behavior with explicit fake upstreams, follow-through disabled, no live model calls and no admission queue configured.

Modular shell and App installation received authenticated seam-only steers, read back as active machine-tagged input in their exact threads. Receipt/placement establishes coordination, not adoption or implementation. No competing service writer was introduced.

Limits: no new image build, VM run, real cohort audio/file/model test, reboot or participant-host mutation in this proposal lane. Those are the implementation acceptance gates above. No merge, publication, deployment or production architecture approval is implied.

**James’s one decision: approve these three isolated candidate implementation slices.** Yes starts candidate work coordinated with the existing owners and Thales gates; defer leaves this proposal staged and daily unchanged.
