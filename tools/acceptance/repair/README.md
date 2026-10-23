# Repair-kit drill (broken box)

Proves that [`docs/REPAIR_KIT.md`](../../../docs/REPAIR_KIT.md) gets a broken Wizard box working again. Answers the
done-when of [#93](https://github.com/humanitylabs-org/wizard-os/issues/93): a fresh box ships the Troubleshooter,
and the runbook repairs a deliberately broken test box.

`drill.py` builds a disposable Ubuntu 24.04 VM with Lima (pinned cloud image, checked by sha256, no host mounts, no
credentials, no forwarded ports), installs Wizard OS with the public command
(`curl -fsSL https://aiwizards.com/os.sh | bash -s start`, `WIZARD_RELEASE` pinned, default 0.3.32) and waits on
its own `bash -s status`. Then, for each failure, it runs four steps as the box owner:

1. **inject** the failure,
2. **confirm** the box is really broken,
3. run **only the kit's recipe** for it, verbatim,
4. **confirm** recovery (container running and the app's own health URL answering, or install `done`).

| Drill | Failure injected | Kit recipe |
|---|---|---|
| `C-shell-down` | stop the shell and Agent Service containers | C: `wam recover` |
| `F-hermes-down` | stop the Hermes engine container | F: `wam app restart hermes-agent` |
| `E-app-screen` | stop the Files app containers | E: `wam app start files`, `wam apps` |
| `A-stuck-installing` | `install-status.json` left `running` by a dead runner, plus a stale `install.lock` (#90) | A: `wam updates`, `os.sh … status`, `os.sh … start` |

Not drilled (need a real account or a failing registry): B (AI provider signed out) and D (app install fails). Both
are checked against the App Manager source only.

## Run

It is heavy work (a VM and a full install, about 45 to 75 minutes): run it on the shared heavy worker through the
wizard-heavy queue, never on the control-plane VPS or an owner's box.

```sh
# on the worker; LANE_ROOT is on the work disk, e.g. "$WIZARD_WORK_ROOT/launch-lanes/L8-repair"
python3 tools/acceptance/repair/drill.py "$LANE_ROOT" <run-id> --dry-run      # writes evidence/<run-id>/plan.json
python3 tools/acceptance/repair/drill.py "$LANE_ROOT" <run-id> [--seed-image <verified ubuntu img>] [--keep]
```

Evidence: `$LANE_ROOT/evidence/<run-id>/` with one log per step, `receipt.json` (exits, timestamps, per-drill
verdict) and `RECEIPT.md`. The VM (`l8-repair-<run-id>`) is deleted at the end unless `--keep`. The run refuses to
reuse an existing VM name.

`tools/tests/test_repair_drill.py` keeps the drill honest: every recipe command it runs must appear verbatim in
`docs/REPAIR_KIT.md`, and the dry-run plan must contain all four drills.
