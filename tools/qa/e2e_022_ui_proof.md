# 0.2.2 retained AMD64 guests: NON-AI UI proof

**Prepared source, not an execution/acceptance receipt.** The release acceptance
owner reviews and admits this runner through the native Thales heavy queue. Do
not run it on the control plane, start a parallel VM job, or submit a queue job
from this script. The separate owner sign-in preflight/HTTPS relay remains owned
by the release supervisor; this runner neither edits nor invokes it.

## Exact execution command (after staging this pushed checkout)

Working directory: `/Volumes/ThalesMedia/wizard-os/e2e-022/ui-proof-source`

```sh
/usr/bin/python3 tools/qa/e2e_022_ui_proof.py \
  --root /Volumes/ThalesMedia/wizard-os/e2e-022 \
  --node /opt/homebrew/bin/node \
  --playwright-module /Volumes/ThalesMedia/wizard-manager/qa/node_modules/playwright
```

Stage the pushed `integration/e2e-022-ui-proof` branch into that directory, then
check out the exact handed-off commit detached. The command requires a clean
tracked checkout and records its HEAD and all runner hashes. It defaults to
**both** `fresh-022-candidate-amd64` and `alongside-022-amd64`, sequentially. An
explicit `--vm <exact-name>` selects one guest for a later focused retry.
Both selected guests must already be stopped; the script refuses other names.

Read-only Thales discovery confirmed `/usr/bin/python3`, Node
`/opt/homebrew/bin/node` v22.23.2, Lima 2.2.1, and the existing Playwright package
above (1.64.1), whose Chromium executable exists. This is dependency discovery,
not browser execution. No packages are installed on the Thales host by the runner.
Browser profiles/temporary work use the external-volume scratch directory.

## What the admitted run does

1. Records source/host/argv; rejects a non-macOS host, non-external root, missing
   guest, already-running guest, dirty tracked source, or concurrent invocation.
2. Enforces Lima wildcard **and loopback** forwarding ignores, starts one guest,
   and waits at most 180 seconds for the actual WAM marketplace. Client
   construction (`c.runtipi()`) is inside the retry attempt's `try`; each attempt
   is bounded by its own subprocess timeout.
3. Calls **`$HOME/.wizard-os/bin/wam install defleur-video`**. It does not replace
   this with `docker run`, change catalogs, or install a hand-authored app.
4. Reads the installed registry back. Requires public DeFleur `0.7.0-testing`,
   source `76c544a75515f41d49317a625fdf40e63d0b8176`, AMD64, and public image digest
   `sha256:d837622c977e1d868bfbb331f5f61fc3040d2ee89b0218e4f1f73a84aa6b4b57`.
   Records installed app metadata, app-owned SKILL/wizard/config hashes, and
   generated workflow-pointer skill existence/hashes. Nothing rewrites skills.
5. Probes real health and MCP **initialize → initialized → tools/list** (all pages).
   It records names/count, never calls `tools/call`, and never imports/transcribes
   or edits a video. A mismatch or missing pointer is a failed stage, not success.
6. Verifies Files and DeFleur share the actual Runtipi `media` mount. Creates a new
   `media/Videos/ui-proof-<UTC>/release-acceptance-source.mp4`: ten seconds,
   360×640 H.264/AAC, flat-color video, offline `espeak-ng` speech with pauses:
   “This is a release acceptance test. Please trim the pauses and add captions.”
   Missing `ffmpeg`/`espeak-ng` packages are installed **inside that test guest**.
   Existing media is not overwritten. Checks streams, duration, decode and hash.
   This is clearly labelled synthetic **source**, never fake edited output.
7. Opens one process-owned loopback SSH tunnel using
   `limactl show-ssh --format=config`. Runs actual installed Wizard HTML/JS in
   separate desktop and mobile-sized Playwright contexts; no fake APIs or app
   state, no credential bootstrap, no sign-in, no copied host authentication.
8. Exercises ten journeys per guest:
   - Desktop/mobile Settings overlay → browser history Back; three opens each.
   - The same separately with Escape/CloseWatcher path; three opens each.
   - Desktop/mobile first root Back and another after the exit window, separately
     for history and Escape. A real prior document exposes exit failures; the
     test never installs its own history guard. Root must remain Wizard Home.
   - Desktop/mobile canonical `?open=files` → Videos → new source folder → Back
     to the exact Videos parent, with the real synthetic filename visible.
   Settings overlay proof is explicitly **not** counted as nested Files proof.
9. Captures private screenshots of entry/nested/returned states and actual auth
   gates; blocked or missing nested views stay blocked/incomplete. Checks both
   the shell and the retained Files frame after settled history traversal.
10. Kills its SSH tunnel, stops its guest in `finally` (force-stop fallback for
    this owned start only), and reads Lima state back before starting the next.
    No daemon/tunnel/guest is intentionally left running. Checks pre-existing
    container image identities and release-manifest bytes were preserved.

## Evidence and boundaries

Private evidence is under `<root>/evidence/ui-proof-<UTC>/`:

- `receipt.json`: source revision/hash, host, exact commands/stage exits,
  per-guest status, verified cleanup, evidence hashes.
- `<vm>/guest-receipt.json`: allowlisted install/discovery/metadata/media proof.
- `<vm>/browser-receipt.json` and PNGs: per-journey results and screenshot hashes.
- `<vm>/ssh.config`: private tunnel configuration, not printed or published.

No raw Docker inspect/environment, raw command logs, HTTP bodies, cookies,
localStorage, bootstrap token, HAR, Playwright trace, or provider-auth files are
saved. Browser network policy allows same-origin GET/HEAD/OPTIONS only; all
writes and WebSockets are denied, with safe path-only diagnostics. This is
non-AI navigation coverage under an explicit read-only policy, not full app
functionality. Files login gates are captured, never bypassed.

Exit 0 means these **non-AI** stages/journeys passed for every selected guest.
Exit 2 means incomplete/blocked/failing stage(s); prerequisites may exit 1.
Neither exit 0 nor a screenshot certifies provider/model readiness, AI-account
Connect/Test, Hermes chat, DeFleur editing, physical Android Back, or exact
release acceptance. AI/provider/edit acceptance stays pending owner sign-in.

## App-owned workflow source (do not copy it into this runner)

The current public index resolves to `humanitylabs-org/defleur-video` at
`76c544a75515f41d49317a625fdf40e63d0b8176`; the older aggregate app-store copy is
not the current 0.7.0 source. Fetch/read that repository's `SKILL.md` and
`wizard.md` at the pinned commit when preparing a future actual edit.

- [Pinned app skill](https://github.com/humanitylabs-org/defleur-video/blob/76c544a75515f41d49317a625fdf40e63d0b8176/SKILL.md)
- Skill SHA-256: `5380d9983cbe8221416f2f5f532f7e8d13045c753a9cb20475110e9b0a30c4ad`
- The workflow recommends Hermes with `claude-opus-5-5` and requires its real
  agent check plus owner confirmation on mismatch before importing. This runner
  does not pretend to satisfy that gate.

## Source-only verification

```sh
python3 tools/qa/test_e2e_022_ui_proof.py -v
python3 -m py_compile tools/qa/e2e_022_ui_proof.py tools/qa/e2e_022_ui_guest.py tools/qa/test_e2e_022_ui_proof.py
node --check tools/qa/e2e_022_ui_browser.cjs
python3 tools/qa/e2e_022_ui_proof.py --help
git diff --check
```

Unit tests mock subprocess/HTTP responses solely to check code contracts. They
are not live guest/browser evidence. No guest or browser was run while preparing
this source. Inspect screenshots only after the supervisor admits the real run.
