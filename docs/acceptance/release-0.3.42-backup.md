# 0.3.42 backup/restore — small-group admission

**Status: prepared; not a passed acceptance receipt. Stable must not move yet.**

## Scope and authority

Carry published 0.3.40 forward, changing only the WAM source/image pins. This
includes backup/restore (#61), strict contact/report (#166), install retry (#209)
and the independently reviewed credential/recovery fixes (#213). It does not
replace the separately reserved 0.3.41 defaults/UI lane (#206/#211).

**James's explicit release-specific policy override, 25 October 2026:** cut now
for the first small tester group by Tuesday 27 October; do not wait 72 hours on
latest. This waives the soak only, not review, published image provenance,
validation, fresh install or upgrade/restore evidence. Use the existing audited
`--fast-track --classification feature` path, recording this authority verbatim
in the promotion reason. Stable promotion is a separate PR after passing gates.

## Evidence still required

| Gate | Status / evidence slot |
| --- | --- |
| Non-author backup review | WAM #61, comment 6395098867 found recovery/stop blockers; final fix review must close them before pinning. |
| Canonical state contract and recovery fixes | WAM #213; final-head CI and merge required. |
| Published WAM image | Official `image.yml` run 40171067383, source `80c76cf9e61df78abe4c09ffa419ad899bbc61a6`; digest must verify via `gh attestation verify`, and image-input diff to pinned WAM must be empty. No hand-built image. |
| Release validation | `python3 tools/check_release.py releases/0.3.42.json` must pass online. |
| Fresh 0.3.42 + 0.3.39 -> 0.3.42 | Thales `release_gate.py`, no overlays; attach real `receipt.json` including pin/contact/diagnostics, marker preservation and cleanup. Pending. |
| Fresh 0.3.42 + 0.3.40 -> 0.3.42 | Same admission, distinct sequential disposable VM and receipt. Pending. |
| Real new-version backup/restore/Undo | `backup_journey.py` on the upgraded guest, exact-hash class fixture from the L1 backup rig. Export, full verify, distinct baseline, import, all nine marker classes + paused cron, Undo digest and return baseline. Pending. |
| Public mirror | WAM releases/ bytes must match canonical release and latest pointer after PR merge; stable stays 0.3.39. |

The dedicated `release_gate.py` reuses launch `disposable_cases`, bootstrap,
contact tunnel and journey checks. It never enters the retained/daily lane.
Admission requires a mounted work root, an unused per-run root, 250 GiB reserve
plus a 17 GiB disposable disk and metadata, pinned Ubuntu image, disabled guest
port forwarding and a reserve watcher. Only the isolated run root is writable
inside the guest; the separate staged source is read-only. It deletes the
fresh VM before the upgrade VM is created and always writes a terminal receipt.
Run the two admissions **sequentially**, not concurrently. A preflight PASS is
not an acceptance PASS. Never modify the scheduled daily stage.

## Known limitations / tester handover

`wizard-app-manager/docs/BACKUP.md` is the canonical what-travels/re-enrols
contract. Wizard scheduler SQLite files travel at default in-home paths, but
there is no scheduler-aware checkpoint/pause/occurrence reconciliation. Stop
source Service before export; inspect/recreate schedules with destination
Service stopped/offline. Custom external scheduler paths do not travel.

AI logins can refresh before activation; `--old-is-off` is not a refresh lock.
The old box must be off/disconnected before import, or the destination must
remain offline until exclusive handover. Re-authenticate when required.
Tailscale identity does not travel; re-enrol through Setup. Alongside/linked
machine pointers and external folder grants must be re-established locally.
Kept destination-only trees are copied into staging for safety; budget for that
extra space (an out-of-space failure must retain the original and Undo data).

This Linux acceptance does not prove a fresh Mac GUI migration or real provider
refresh-token portability. Historical Mac->Linux->Mac evidence remains scoped
to its earlier revision, not represented as a new-release pass.

## Promotion template — do not run before evidence passes

```sh
python3 tools/promote_stable.py promote 0.3.42 --from 0.3.39 \
  --evidence '<PUBLIC_LINK_TO_PASSED_0.3.39_AND_0.3.40_UPGRADE_AND_BACKUP_RECEIPTS>' \
  --fast-track --classification feature \
  --reason 'James explicit policy override, 25 Oct 2026: backup/restore for the first small tester group by Tue 27 Oct; waive 72h latest soak for this release only. Real fresh-install, both upgrade and backup/restore gates passed; see evidence.' \
  --notes '0.3.40 bundle with WAM backup/report/retry/recovery fixes; offline scheduler and AI-login handover required; Tailscale re-enrols. Not a mass rollout.'
python3 tools/promote_stable.py check
```

Put the resulting promotion record and stable pointer through a named PR; mirror
both to WAM in another PR. Verify **both** gate implementations
(`tools/promote_stable.py` and `wam/updates.py`) accept the same actual record,
and reject a record without passed upgrade evidence. Do not replace evidence
with this preparation document or manufacture a passed slot.
