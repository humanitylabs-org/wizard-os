# Backup launch acceptance (disposable Mac → Linux → Mac)

This is a heavy-worker harness, **not** a release image builder or a live-box migration.
Stage the files alongside an isolated lane's existing `bin/rig`, source snapshots,
Mac kernel/initrd/vmrun, read-only Mac base disk and stopped Lima test template.
All mutable paths and `LIMA_HOME` must be on the external ThalesMedia volume.
The lane's `rig-config.json` supplies `sparkle`, `updater_public_info` and
`template_root`; no owner identity or private paths belong in this source.

Quick check (no guests, network or secrets):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/acceptance/backup/backup-proof.py --dry-run
```

This runs orchestration tests with explicit test doubles. It is **not evidence of
a real restore**. The heavy worker runs staged `rig/premerge.py`, whose own dry-run,
source pins, native contracts/build and actual VM gate must all succeed.
`harness-manifest.json` binds staged bytes to the pushed branch/commit. Historical
receipts from previous attempts must be preserved outside the active result paths.

## Assertions exercised by the real VM gate

1. Boot a private CoW Mac guest; install the pinned managed Mac engine/front door.
   Refresh Files and install the account app inside this disposable guest only.
2. Seed Mac owner files with ordinary, accented, Japanese and hidden names; use
   **stock Hermes APIs** for a chat, memory/user entries and an enabled far-future
   scheduled job. Seed settings, Files app data and a synthetic login document
   inside the account app's real Docker volume. Publish `markers.json` atomically
   **only after all writes succeed**. No dependency on a preexisting lane-root file.
3. Export through the real native-only HTTP front door. Import into fresh Linux
   through the real CLI. Assert every named marker, exact chat/memory equality,
   nonempty scheduled jobs and their paused state. Refusal here fails acceptance.
4. Export that restored Linux box. Disturb **all** named Mac markers (including
   stock Hermes state), prove they are absent, then import the Linux export into
   Mac. Reassert every class and paused jobs. This prevents leftover original Mac
   data from giving a false return-leg pass.
5. Run actual Mac Undo and assert engine `digest_match` plus the distinct baseline.
   Run Linux Undo and require its digest/baseline equality too.
6. Export a newer-version Files fixture using the **real engine and archive**.
   Only this disposable fixture's installed package/registry version is raised to
   `9999.0.0`; no production release is claimed, no archive/receipt/CLI is patched.
   Import into the older Linux target. Require actual **exit 3**, a clear human
   message, a real partial receipt refusing exactly Files with the newer version,
   unchanged refused app data/wiring/secret/token hashes, restored other named
   classes and paused jobs. The refused app marker must stay absent. Undo this
   partial import and require another digest/baseline match.
7. Remove only owned runtime guests, keys, staging files and the Mac CoW disk.
   Late errors, secret-audit failures and failed cleanup cannot produce success.

`logins` proves byte preservation of a synthetic credential-shaped file in the
real private account-login volume, **not** a live provider sign-in. It cannot
contact a provider or authenticate. No owner credentials are used.

## Gates not replaced by this harness

Native-window interaction/screenshot QA (`gui`) remains a separate, explicitly
NOT_RUN gate. The HTTP/CLI proof does not claim GUI approval. This harness neither
merges PRs nor deploys, publishes, or rebuilds a release Mac guest image.

On failure inspect `evidence/premerge/result.json`, `fresh-acceptance.log`, and
`evidence/backup/result.json`. Never infer VM success from the quick dry-run.
