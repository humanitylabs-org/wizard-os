# 0.3.43 backup/restore — fresh-install recovery

**Status: cut to latest; full-release acceptance pending. Stable stays 0.3.39.**

## Scope

Carry the 0.3.42 bundle forward, changing only WAM source to
`42999861f941baad33aa5731fd041f4abdd0c673`
([WAM #217](https://github.com/humanitylabs-org/wizard-app-manager/pull/217)).
No other component or image pin changes. This is the backup/restore tester lane,
not the separately reserved 0.3.41 defaults/UI work.

0.3.42's real disposable fresh-install gate failed before default apps installed:
the host registry writer tried to read backend-owned `state/wizard-grants.json`
(root, 0600). #211 creates that file on backend startup, so upgrading from
0.3.40 to the broken bundle can hit the same failure; it is not fresh-only.

#217 resolves public grant metadata from a readable file, otherwise the existing
App Manager API, otherwise the existing registry mirror. The host-reader audit
found and fixed a second eager read in `registry.write`, including an explicit
`WIZARD_GRANTS_FILE` / sibling-state path. File permissions stay 0600. Backup
helpers read app data inside their root helper container; the #211 per-grant
keys remain backend-owned, not direct host state reads. No further host readers
of those root-only state files were found in CLI/doctor/install/backup paths.

REUSE: published image, release tooling, existing launch acceptance harness and grants API.
EXTEND: existing host registry reader/writer.
NEW: none.

## Evidence

- Final fix head `491a12fcc6fdd3bb21b309238f99800dbdef9ef8`: required `test` and
  `gitleaks`, plus backend and CodeQL, passed before squash merge.
- Targeted host/registry/storage tests: **43 passed**. Six added permission and
  missing/malformed-source cases failed before the fix and passed afterward.
  Existing Node Open tests: **4 passed**.
- Cheap isolated Thales filesystem reproduction: non-root process calling real
  `write_registry` against a root-owned 0600 file. Old 0.3.42 source exits 13 /
  `PermissionError`; pushed candidate exits 0 and persists matching owner/shared
  registry grants. Permissions unchanged. Installed rows/API are synthetic;
  this proves the filesystem regression, not full install acceptance.
- WAM image inputs did not change. Official
  [image.yml run 40171067383](https://github.com/humanitylabs-org/wizard-app-manager/actions/runs/40171067383),
  source `80c76cf9e61df78abe4c09ffa419ad899bbc61a6`, published
  `sha256:ff30d81d103c7ca408692fb25b98827d0fb382a8034e2bcbd0daf46b99547e39`.
  `gh attestation verify` passed (matching main-ref signer, source and subject).
  The online release checker must also prove no image-input diff to the new pin.
  The CLI-only fix does not trigger image.yml; no image was hand-built.

## Required Thales gates — not yet passed

Stage exact merged source archives with SHA256 and file-by-file verification in
one new external-disk directory, never modify the prior or daily stage. Reuse
`tools/acceptance/launch/release_gate.py` with no install overlays:

1. Fresh 0.3.43, then 0.3.39 -> 0.3.43, then real backup/restore/Undo using the
   existing class fixture SHA256
   `984d0437264b82b54b43fe78c08aacb246926fee700f837cd82868eec2087859`.
2. Fresh 0.3.43, then 0.3.40 -> 0.3.43, in a separate sequential disposable run.

Admission requires an unused root and at least **268 GiB free** (250 GiB reserve,
17 GiB guest plus metadata); do not delete unrelated data to obtain admission.
Run sequentially. `--check-only` reports preflight, not acceptance. Require real
`receipt.json` with expected pins/contact/diagnostics, preservation, cleanup and
backup marker/Undo results. A prepared spec is not a passed test.

## Stable promotion and handover

James's explicit **25 October 2026** override in `docs/DECISIONS.md` waives only
the 72-hour latest soak for the first backup/restore tester group by Tuesday
27 October, not review, provenance, fresh install, upgrade or backup gates.
Stable must remain **0.3.39** until those gates pass; promotion is another PR and
public mirror PR. Keep the scheduler/offline-login/Tailscale handover limitations
in [0.3.42's admission](release-0.3.42-backup.md) and WAM `docs/BACKUP.md`.
No live owner box or core Hermes is touched by this release preparation.
