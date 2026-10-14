# Style extraction checkpoint · t_24e03d53

Status: **staged; runtime acceptance blocked, no merge or daily deployment**.

## Source and decisions

- Approved Appearance v1 rows #50–53 at Wizard OS base `be8cdf1d489161321c472ef88e600fdca2a122b8`.
- Extracted live skin source: Wizard UX daily `201b4e66d1c3d8a7c9772787721ba028bdce2d58`. All recorded source-file hashes were compared to that exact Git revision.
- Five accepted skins, fourteen transport colour roles. Type/layout/motion defaults remain CSS-only. Miguel's manifest-field confirmation remains separate.
- WAM base `6ad71d8dd73974a822e821182936f4288d097b5f`. Four runtime assets are byte-identical, hash-locked distribution copies of this repo's `style/`; the sync helper also refreshes inline container packaging.

## Verified evidence

- Both unchanged manifest checkers printed `COMPATIBLE` (DeFleur example and hello-wizard reference).
- `python3 style/generate_tokens.py --check`: JSON/CSS match.
- `python3 tools/sync_wizard_style.py --check --source <candidate wizard-os>`: distribution files match canonical source.
- Every text file embedded in the reference template's inline compose package was compared byte-for-byte to its source, including the new token stylesheet.
- `python3 templates/hello-wizard/app/build_view.py`: source view validated.
- **Thales lightweight protocol fixtures**: `/opt/homebrew/bin/node /Users/thales/.hermes/cache/scratch/style-tokens-t_24e03d53/test_client.cjs` printed PASS. Covers parent/origin/schema, fourteen colours, transparent canvas, stale revisions, reordered retransmission acknowledgements, generic light fixtures and rejected unresolved CSS substitutions. This is a VM-based source fixture, not browser or packaged-runtime acceptance.
- Independent source review found three issues (stale inline payload, order-dependent acknowledgements, unresolved substitutions); each was corrected and covered in source/fixture checks.

## Blocking evidence

On Thales, `hostname`, mount metadata and files on the internal disk respond. Opening or reading `/Volumes/ThalesMedia/AndroidBuilds/worker.lock` and an existing builder receipt stalls for Python and Node, including a scoped read-only sudo probe. APFS volume is mounted, writable, unlocked and has free space. Timed-out task-owned probe processes were stopped. No reboot, remount, service interruption or lock replacement was performed.

## Remaining acceptance on Thales

After external-volume I/O is restored, reserve the existing shared lock (same inode; no bypass), sync the final exact heads, then run these in one locked script:

1. WAM full `python3 -m pytest -q` and reference protocol fixtures; capture actual file selections/counts and exact source hashes.
2. Generate a fresh hello app with `wam new`, run its real container, verify API/MCP/view/readback and automatic style imports.
3. Browser fixtures: standalone, hosted window/fullscreen, all five skins and synthetic generic light. Cover scroll/input/document preservation, nested/root Back, rejected origins/schema/stale contexts and screenshots.
4. Read-only real-shell cold entry for Topics, Music, Signal and Wisdom using `style/qa-live.cjs`; inject only the candidate appearance client through isolated browser routing, block production writes, compare same window material/ink/accent to Chats. Extend its checks for window/fullscreen and explicit frame-to-window transparency before claiming acceptance. Inspect screenshots yourself.
5. Append exact-host/source/command receipts and real screenshots to these PRs, request James's style review and Miguel/Oscar's WAM review. Both PRs stay unmerged under this task's authority.

Daily Wizard, existing app code, manifest admission and deployed builder remain unchanged.
