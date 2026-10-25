# Launch audits 8/9 — preflight evidence, not release acceptance

Spec PR: #161. Scope: #139, #140, umbrella #25.

## Verified

- One bounded Fable spec review: actual model `claude-fable-5-1`, `is_error=false`,
  no permission denials. Raw response SHA256
  `add075ad754f98200e3f70b13c53243875074e131c6e2268efa2d3bb15a60855`.
  Incorporated NAT/sudo corrections, explicit source-probe versus released-profile
  scope, candidate/overlay window resets, public fixture provenance, changed-state
  SQLite restore, closed diagnostics schema and privacy-canary tests.
- WAM focused CLI + existing WAM regression suite: **67 passed, 2 skipped** in 6.95s.
  The new CLI audit cases all pass (10 cases). Existing skips are not counted as
  acceptance. `bash -n install.sh` and `git diff --check` pass.
- The real offline `wizard report` output validates against `report.schema.json`
  with the JSON Schema validator. Secret canaries are excluded from the projection,
  including malformed input/probe failures; report code opens no network socket.
- Appliance harness: **6 passed** stdlib unit tests. This includes a real SQLite
  snapshot → change → restore → readback test (not a fake no-op restore), public
  fixture ZIP determinism, receipt hash linkage, canary-safe comment formatting,
  and 72-hour gate failure/gap/candidate/intervention/overlay reset cases.
- Fixture ZIP staged and enabled using the actual public Wisdom library modules
  at commit `c80f54cdfde9ffa273dc5140dbcc704e4038574f`; its real state returned
  `launch-public-reading`, exact expected text, progress 0. This was a lightweight
  library smoke check, **not a shipped-profile app/VM receipt**.
- Ubuntu 24.04 ARM image dated `20261017`: upstream SHA256SUMS pins
  `50e24e1fb79e89116e939d90aa7738f7af48c442fa1bc2510131e0b39c50348e`.
  Build machine has Lima 2.2.1; source and VM state are staged only on its work volume.

## Still required

No fresh Ubuntu public-install run, browser/two-skin evidence, persistent appliance,
daily schedule, full installed-app workflow, in-place candidate upgrade or elapsed
72-hour soak is claimed by this preflight. The frozen source runner is ready for
durable heavy admission; its first real VM result may identify harness or product
failures that must be corrected without weakening the public install/pin gate.
Do not merge the implementation or close #139/#140 before fresh-box proof and CI.

The planned daily slot is 09:15 UTC. The schedule is **not installed** by the runner;
activate it only after the initial full run succeeds, through the durable queue.
`publish.py` mirrors bounded receipts to #140 and reads back the exact comment.
No private logs, owner data or host paths belong in public issue comments.
