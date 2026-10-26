# 0.3.50 Stable promotion — 26 October 2026

## Authority and scope

James explicitly waived the 72-hour Latest soak on 25 October 2026 for the first small tester group on Tuesday 27 October. See `docs/DECISIONS.md`, “Tuesday small-group backup/restore release; explicit soak override”. The current launch instruction explicitly selects the published 0.3.50 bundle after both mandatory gates passed. This uses **feature** fast-track classification, not a fix-only classification. Release metadata, image pins, installer bytes and acceptance checks are unchanged.

Separate fix-only onboarding maintenance work (#236/#237) is not part of this promotion. That work copies 0.3.39; this promotion intentionally selects the already-published 0.3.50 bundle under James's launch-specific authority. It must not be described as a fix-only backport or a mass rollout.

## Immutable input

- Canonical release cut: #233; `releases/0.3.50.json`.
- Frozen acceptance stage: `0.3.50-79dc64a-44fded38`.
- Harness: wizard-os main `79dc64a` (diagnostics preserve private failure evidence).
- App Manager: main `44fded385c0555b6ee5adf7593c67f33cb701ac7`.
- Release source/image/default app pins remain exactly those of published 0.3.50.

## Real execution evidence

Both original receipts were read and hashed on the acceptance worker before creating the promotion record. Relative locations below are beneath the worker's Acceptance directory, not public owner paths. The full original receipts remain there.

| Gate | Durable job | Receipt | SHA-256 | Result |
| --- | --- | --- | --- | --- |
| A | `heavy_fa4ed5aecf3d4f6ab6182c9b8a410def` | `b350-39/evidence/receipt.json` | `7485c3e9a919983313c4de079aaa2d04df551ae95e6ecf47160c64b49193a881` | `passed=true`, release 0.3.50, from 0.3.39 |
| B | `heavy_733abccb64a44aad86ac324a35101b27` | `b350-40/evidence/receipt.json` | `6c9329578ce189e9d9f8144f85ac1877d9b5f11fae9a1dd8c9cea63a9daa8de9` | `passed=true`, release 0.3.50, from 0.3.40 |

Gate A finished at `2026-10-26T02:41:07.242754+00:00`; Gate B at `2026-10-26T02:08:29.970756+00:00`. Both receipts report aarch64, no overlays, successful cleanup and no low-space failure.

Each proves a fresh public install of 0.3.50, the historical baseline install, and the upgraded candidate. Candidate journeys prove Setup/first contact, Wisdom readiness, preserved reading progress and restore. Upgrade readback is retained. Gate A also proves real new-version backup export, verify, import and Undo, distinct baseline, paused cron, and matching Undo digest for all 11 classes: app_data, chats, files, files_accented, files_hidden, files_japanese, logins, memory, scheduled_jobs, scheduled_jobs_paused, settings.

## Boundaries and rollback

This is same-release Linux backup acceptance with synthetic login data. It does **not** establish scheduler/refresh fencing, real rotating provider-token portability, Mac GUI migration, physical phone/QR pairing or first real-model onboarding. The first-chat/phone job remains separate and must run before claiming that onboarding proof. The skipped 72-hour soak remains an explicit owner waiver, not a passed soak.

Rollback is the prior valid Stable pointer, 0.3.39, in both canonical and mirror, retaining its valid promotion record. Never mutate published release manifests.

## Promotion checks

Generate the record with `tools/promote_stable.py promote 0.3.50 --from 0.3.39 --fast-track --classification feature` and the authority/evidence above; do not hand-edit the record. Validate canonical channels and sibling App Manager gate parity; require exact-head hosted CI, squash merge the canonical PR, then mirror `stable` and `promotions/0.3.50.json` through a separate PR. Read canonical git/API, public mirror API and anonymous raw bytes after merging. This report records execution evidence, not an advance claim that those publication steps have completed.
