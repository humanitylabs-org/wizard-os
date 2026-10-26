# One-time fix-only Stable onboarding backport (proposed)

Miguel explicitly requests repaired onboarding on Stable without promoting unrelated unaccepted features. Current Stable is 0.3.39; Latest 0.3.50 contains unrelated backup/restore/Undo, Spaces and Android changes. Do not promote that bundle as a fix.

## Proposed narrow release-source exception

The normal main-only source/publication rule cannot produce a fix-only artifact from the current trunk. Authorize one maintenance source branch in **wizard-ux only**, `release/stable-onboarding`, based on the exact Stable 0.3.39 UX source `c8433e348f1e715a5652089411f11d401a7860bc`.

- This is an explicit exception to starting all changes from main and to main-only publication. It does not change normal trunk development or permit arbitrary branches, forks, source refs or local images to publish.
- Apply only the onboarding repairs from UX #434, #482, #483 and #486 as required by the Stable source, plus their regression/acceptance tests. Resolve conflicts against the Stable implementation, not by copying current trunk files. No feature/default ride-alongs beyond repairing first launch, working replay, per-step skip/exit and denied-microphone typing. The existing Stable tour already has skip and no Command beat.
- Import the reviewed official hosted publication implementation and its tests from main; adapt it in a separate reviewed main PR to allow **only** this exact maintenance branch in addition to main. Main's behavior remains unchanged.
- Maintenance publication must be an explicit workflow dispatch on that branch, require the full expected SHA to equal the selected branch SHA, and reject push events there. PR/fork code must never publish. Do not use an arbitrary checkout SHA or a new privileged pull_request_target workflow.
- Require independent non-author review of both the publication-policy implementation and the exact backport commit before dispatch. Do not weaken branch protections, review policy or existing required checks.
- Keep canonical repository guards, isolated hosted Docker configuration, digest-only prepare, signed provenance, write-once finalization and anonymous amd64/arm64 pulls. Provenance must identify the real maintenance source ref and exact SHA; never claim main provenance for a branch build.
- A new immutable Wizard OS version copies **0.3.39**, changes only the UX source/image/default-app shell pin, and honestly names the maintenance branch and official publish run. Other components, Hermes and default apps remain byte-identical to Stable. Reserve its version only immediately before the cut after inspecting concurrent release work. Do not reset Latest to an older version or modify a published manifest.
- Before promotion, verify actual installed current-Stable-to-candidate upgrade and first launch/replay/skip/exit/mic-denied typing on real desktop and phone entrypoints, Chromium and WebKit. Fresh alongside installation must match the public os.md promise. No command exercise, required appearance customization or Setup auto-open.
- Cut/mirror/promotion remain maintenance PRs and need non-author review under DECISIONS #96. Use the existing promotion tool and regression-backed fix classification only after the complete gates pass. Canonical and public mirror must be byte-identical by GET.
- Rollback is the prior valid Stable pointer, 0.3.39, in canonical and mirror. Remove this publication exception after shipping the repair; it is not an evergreen release lane or a third owner channel.

## Demo custody

Do not wipe the authorized disposable demo until the fix is actually Stable and verified. Preserve its state and demo-only credentials outside the wipe scope first. Keep SSH/Tailscale recovery until stock Hermes inference and the owner-only Telegram bot work. Never copy production OAuth credentials. The saved installer sentence remains evergreen and selects Stable; do not give it as ready while Stable still lacks the repair.

## Approval requested

@defleur-agents: independently review this narrow exception and the resulting publisher/backport implementation. This document is a proposal until its PR has non-author approval and is merged. It does not claim publication, promotion, upgrade acceptance or demo readiness.
