# Promote 0.3.51: isolated Stable onboarding repair

## Scope and immutable target

Requested outcome: fix broken first-launch onboarding on Stable without promoting the unrelated Latest feature bundle. Base is Stable **0.3.39**, not 0.3.50. Programmatic manifest comparison proves that only `components.wizard-ux`, `images.wizard-ux` and `default_apps.shell.commit` differ; all other components, images, Hermes and default apps are identical to 0.3.39.

- Canonical cut: wizard-os #237, merge `777e84ed6d9c17e5ba99ffd759f22a95067901e7`.
- Public mirror: wizard-app-manager #235, merge `49a6518c36bcad8932b534faac4ad1d7f3ce9d9d`.
- Manifest SHA-256: `9f28c6104767a5812cd429a2f086bda657d3aa782850f72a4873632b180ce2cd`.
- UX source: `c0bd9adc82f6d61cd156b9f2568249cff7d668ba`, real branch `release/stable-onboarding`, backport UX #531. The narrow source exception and hosted publisher were independently reviewed by defleur-agents in wizard-os #236 / UX #530. Exact-head Codex review completed with no unresolved findings after its rotation finding was fixed, replied to and resolved; no admin/protection bypass was used.
- Official hosted publication: https://github.com/humanitylabs-org/wizard-ux/actions/runs/40259576904 — `workflow_dispatch` on the actual maintenance ref/SHA. Validate, publish, attest, finalize and anonymous-pull all succeeded.
- Official image: `ghcr.io/humanitylabs-org/wizard-ux:sha-c0bd9adc82f6d61cd156b9f2568249cff7d668ba@sha256:a36276aa5f63676c3217a24664831cac80e32c434adf3312b0fc66cb34ea9bd0`.
- Anonymous OCI config-digest/source/revision checks independently passed for amd64 (`sha256:00ec2ecbde656311bd8db09cab0cabe19b9470cf66e0684953d1971b54558854`) and arm64 (`sha256:8f7fa5c0f12779ad555c1e6c50863033f8e97f384346950d1ef8f57277454777`). `gh attestation verify` also passed with exact signer workflow, maintenance source-ref and source-digest; verified JSON retained privately. CI emitted an optional artifact-metadata storage warning, but actual signed OCI provenance verification and anonymous pulls passed.

No backup/restore/Undo, Spaces, Android update, shared composer, Store or other Latest feature is included. 0.3.52 is a separate Latest-only continuity snapshot with exactly the 0.3.50 pins; it must not be promoted as this repair. The competing full-feature 0.3.50 promotion is separately flagged for owner-instruction reconciliation and lacks the new Done-card regression repair.

## Regression and source verification

- `npm test` on the maintenance backport: **749 passed, 0 failed**.
- New onboarding tests against untouched Stable source: **16 failed / 3 passed**, proving the regressions catch the old behavior. Old installed 0.3.39 desktop also showed `alongside:quiet`, no loaded desktop guide, and no guide card.
- Done-card resize test fails on the pre-repair source and passes corrected source. Real Chromium and WebKit portrait → 844×390 landscape → portrait probes assert copy/glyph/mic-note/tap-row bounds and click the real Skip control. The old landscape placed the mic note and Tap row below the screen; corrected geometry keeps all rows visible.
- Publication contract suite: **31 passed**; these are mock registry/Docker tests, not substituted for the real publication run.
- `node --check` on changed JS and `git diff --check`: pass.
- Online `python3 tools/check_release.py releases/0.3.51.json`: `release 0.3.51: ok` (catalog drift is informational).
- Public mirror release-pins/split/metadata/channel/update tests: **83 passed**; actual hosted checks passed before independent merge.

## Actual demo installation matrix

The explicitly authorized disposable demo was snapshotted while Hermes and app containers were quiesced. Owner state and demo-only credentials were archived outside the wipe scope with 0700/0600 permissions, archive SHA-256/CRC/member checks and a successful extracted SQLite integrity check. SSH/Tailscale recovery stayed intact. No production OAuth credentials or personal devices were used. Existing stock host Hermes stayed on its original official source and `gpt-6.1-sol` throughout these installation tests.

1. **Fresh current-Stable alongside installation**: supported `wizard unlink` restored the recorded original config byte-for-byte; the old Wizard runtime was archived, not discarded. Public `os.sh start`, without a version override, installed **0.3.39**, exit 0, `status: pinned`, every source/image/default-app readback passed. After the actual deferred gateway restart, `wizard doctor --gate` passed all checks including a real model-selected `wizard_apps` call.
2. **Actual 0.3.39 → 0.3.51 upgrade**: public `os.sh start` with `WIZARD_RELEASE=0.3.51`, strict mode, and the explicit immutable public mirror PR-head release base `https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/5b4f99bc859e1d977f804961940c9fb295402cb9/releases`. That manifest was fetched and proved byte-identical to canonical before installation. This override is disclosed; it is not a claim that Stable had already moved. Exit 0, `status: pinned`, exact official running image and source/default-app receipts passed. After deferred restart, all doctors and the real app-tool routing gate passed. **config.yaml, .env and auth.json hashes were unchanged across this upgrade.**
3. **Fresh candidate alongside installation**: after another supported byte-identical unlink, the upgraded Wizard runtime was archived and a clean Wizard/Runtipi state was installed through the same official strict candidate route. Docker packages/images and Tailscale were already present; this is a clean Wizard alongside install, not a brand-new OS or human Tailscale-enrollment claim. Exit 0 and pinned 0.3.51. Post-restart `wizard doctor --gate` passed; gateway was active with its third intentional deferred restart.

Private exact installer/status/release/doctor logs are retained for each run. No local image or box-only repair substituted for the official installer.

## Installed user-visible acceptance

Both the upgraded candidate and the fresh candidate were exercised through their actual HTTPS-served files, not local source substitutes:

- Chromium and WebKit, real device-selected **desktop.html at 1440×900** and phone entrypoint at **402×874**; not the phone shell stretched wide.
- Fresh-browser first launch displays the appropriate readable guide, with no Setup window auto-opened beside it.
- Per-step skip, whole-tour exit, quiet second launch, actual `?view=tour` replay, real desktop Alt+/ → Show me again, and visible phone Settings Help → Practice again pass.
- Simulated browser microphone permission denial exposes a real editable phone fallback. Desktop actual microphone-denied click leaves the editable composer usable. This is not a physical microphone test.
- WebKit instruction text and ancestor visibility checks pass; screenshots were visually inspected. No Command exercise or mandatory appearance customization.
- Real desktop and denied-mic phone typed messages were admitted by the installed service (HTTP **202**, distinct real session/run IDs). Actual `gpt-6.1-sol` assistant history returned **`onboarding-desktop-ok`** and **`onboarding-phone-ok`**; this is not merely an outbox Sent receipt or a fabricated response. Both reached `completed` in the actual session list. Actual reply screenshots were inspected.

One first WebKit matrix attempt hit `Load failed` while the deferred gateway restart was still settling. It is retained as a failed attempt, not counted green; a full rerun after the active restarted gateway was verified passed both shells. The first chat probe initially parsed the wrong list-envelope field; the real response was already present. The harness was corrected against the captured actual `data` payload and both real-chat cases passed. No product change was needed for either harness/restart issue.

## Promotion, rollback and remaining human coverage

Classify **fix** only because the actual Stable-to-candidate difference is isolated, each repair has regression coverage, and actual installed upgrade/fresh/browser/chat acceptance above passed. Fast-track under DECISIONS #82; no invented soak or timestamp. Generate the record with the supported promotion tool, using the real 0.3.51 Latest cut history and `--from 0.3.39`.

Cut/mirror/promotion require their normal non-author review. Mirror the exact canonical Stable pointer and promotion record only after canonical merge; fetch both repositories and public raw URLs and compare byte hashes. Keep the 0.3.52 continuity bundle Latest-only.

Rollback: restore `releases/stable` to **0.3.39** in canonical and public mirror, retaining its existing valid promotion record. On the disposable demo the original 0.3.50 and tested upgraded 0.3.51 runtime states remain archived; restore through the supported pinned installer/recovery path, not an unreviewed image swap. No migrations or deletion are part of this release.

Not claimed: physical phone/Telegram webview, real microphone, Add to Home Screen, native APK pairing, Mac GUI, a new human Tailscale sign-in, or a brand-new OS. The owner-only final test is Miguel sending the evergreen installer sentence to the prepared stock-Hermes Telegram bot after Stable and the clean baseline are verified; do not hand out that prompt early.
