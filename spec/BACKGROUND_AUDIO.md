# Background audio v1 — Android Music pilot

**Staged capability, not live platform availability.** The implementation adds a generic Android Media3 transport; the initial authorized app is the registered same-origin `wizard-music` document at `/wizard-music/`. Other apps and macOS keep their existing playback. This is runtime capability discovery, not a new installed permission system or an extension to wizard.md frontmatter.

## Ownership and API

The shell exposes the origin-bound **main-frame-only** `wizardAudioPort`. Hosted apps use the host relay `wizard:background-audio:v1` with `{id, method, params}`; replies have `{id, ok, result, error}`. The relay validates the host-owned registered window/frame grant, live app registry, attached iframe Window and document, current URL and iframe src before forwarding and again before returning. These are trusted first-party same-origin apps; this does not sandbox hostile same-origin code that can access its parent. Untrusted consumers require origin/sandbox isolation before admission. Native requests are bounded, carry `v:1` and appId, and accept an explicit method allowlist.

- `capabilities` discovers the supported version/methods.
- `attach` returns the live session; it never loads a saved browser queue over that session.
- `state` accepts `knownQueueRevision`; the queue is included when revisions differ.
- `load`, `play`, `pause`, `seek`, `next`, `previous`, `jump`, `enqueueNext`, `removeCurrent`, `removeUpcoming`, `volume`, `detach`, `stop` adapt the existing MusicEngine interface.
- Mutations carry the attached `sessionId`; stale identities are refused. `detach` releases the view, not playback. `stop` explicitly clears playback. Full Android package upgrades, reboot and force-stop are separate lifecycle boundaries.

Canonical snapshots contain sessionId, appId, queueRevision, generation, index, playing, wantPlaying, buffering, positionMs, durationMs, volume, station and error; changed queues retain stable hub track IDs. The Android service owns the clock, queue and transport while it plays. The app keeps its skin, screen structure, catalog/search/voice behavior and editable web assets.

## Native-owned continuation, server-owned policy

The service consumes the hub's station continuation with a generation fence. Queue policy and preference learning stay in the hub. Bounded duplicate filtering, queue history and edits are native transport behavior. Native play/skip events carry stable per-transition idempotency IDs and a small persistent retry outbox; the Music view suppresses its playback reporter when native playback is active. The hub atomically commits station advancement and its requestId batch receipt, validates conflicting playback events, and leaves empty batches retryable. Native policy mutations fence stale continuation replies. Artwork, reports and continuation have independent bounded IO so image latency cannot block transport; failed player timelines are rebuilt from the canonical queue before skipping. Likes/dislikes still use the web/backend feedback path.

Streams, artwork, continuation and feedback are confined to the bound origin and explicitly allowed Music paths. Native requests receive that origin's WebView cookies; hub credentials stay in the server proxy. Redirects are refused before following them or forwarding credentials. Foreign media URLs are rejected before a fetch. An app's claimed appId does not grant authority.

Media3 supplies notification/lock-screen metadata and controls, audio focus and becoming-noisy handling. The existing MicOwner, native recorder and app-voice paths notify a pure-Java recording gate synchronously. The service suspends playback before recording starts without taking or rerouting the mic. Explicit user play intention remains separate from suspension; a user pause stays paused after recording finishes. Existing recorder input and Bluetooth-output routing remain owned by the recorder lane. Handset/call/Bluetooth behavior requires physical-device evidence.

## Wizard app compatibility

The current wizard.md v0.2 app format remains unchanged. The pilot does not require speculative permissions fields. Music remains an ordinary embedded customizable web app with a runtime optional transport adapter: new Android shell → native engine; browser/desktop/older shell → existing HTML-audio engine. It never starts both. Only this pilot's explicitly authorized app uses the native capability until separately approved consumers and admission rules exist.

## Release

Source changes are isolated from daily. A signed `ai.wizards.os` candidate preserves the production signer and update lineage; a separately installable signed Wizard shell preview (`ai.wizards.os.musicpreview`) points at an isolated corresponding shell/Music/hub and does not replace James's daily app. This is a Wizard shell preview, not a standalone Music app. Phone installation, live feed promotion and publication retain their existing authority gates.
