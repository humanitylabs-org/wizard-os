# Repair-kit drill (broken box)

Proves that [`docs/REPAIR_KIT.md`](../../../docs/REPAIR_KIT.md) gets a broken Wizard box working again. Answers the
done-when of [#93](https://github.com/humanitylabs-org/wizard-os/issues/93): a fresh box ships the Troubleshooter,
and the runbook repairs a deliberately broken test box.

`drill.py` builds a disposable Ubuntu 24.04 VM with Lima (pinned cloud image, checked by sha256, no host mounts, no
credentials, no forwarded ports), installs WizardOS with the public command
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
`docs/REPAIR_KIT.md`, and the dry-run plan must contain all four drills. A healthy baseline is required before
injecting any failure. The Files probe uses `/files/health` on the local published port when the release's app
manifest does not declare `health`; missing probes for other apps fail explicitly. It does not GET `/mcp`.

## Why the first 0.3.32 run failed E

The first run (`l8-drill-0332-r1`) had already failed `baseline-healthy`, before any injection. Its Files repair
exited 0 and listed Files running, but `health_url files` returned an empty string, so the recovery check never
made an HTTP request. This is a drill defect, not evidence that the recipe failed:

- [0.3.32's release pin](../../../releases/0.3.32.json) selects **oscarhenrycollins/files** at
  `8a4dd8ac5189d7d9d8af2bb8a2416936668e90df` (not the separate `humanitylabs-org/wizard-files` app).
  Its [wizard.md](https://github.com/oscarhenrycollins/files/blob/8a4dd8ac5189d7d9d8af2bb8a2416936668e90df/wizard.md)
  declares `/files/` and `/mcp`, but no `health` field.
- The pinned App Manager's
  [registry builder](https://github.com/humanitylabs-org/wizard-app-manager/blob/66d06b4504b22d56a9f1f7087e97d6143fade25a/wam/registry.py#L111)
  consequently writes `health: null`; its `mcp.url` carries the actual local published port (8794 on this release).
- The Files [compose recipe](https://github.com/oscarhenrycollins/files/blob/8a4dd8ac5189d7d9d8af2bb8a2416936668e90df/runtipi/docker-compose.yml)
  checks the engine at `/files/health` and sets `FB_BASEURL=/files`. Its
  [front](https://github.com/oscarhenrycollins/files/blob/8a4dd8ac5189d7d9d8af2bb8a2416936668e90df/mcp/front.py)
  proxies every non-MCP request unchanged to that engine. Thus the local probe traverses **both** containers.
- `wam app start files` calls the authenticated lifecycle API; the pinned
  [start handler](https://github.com/humanitylabs-org/wizard-app-manager/blob/66d06b4504b22d56a9f1f7087e97d6143fade25a/packages/backend/src/modules/app-lifecycle/handlers/start-app.handler.ts)
  queues a start even if the record previously said running. The
  [start command](https://github.com/humanitylabs-org/wizard-app-manager/blob/66d06b4504b22d56a9f1f7087e97d6143fade25a/packages/backend/src/modules/app-lifecycle/commands/start-app-command.ts)
  runs compose `up --detach --force-recreate --remove-orphans` for the whole app, including its engine.
  This is not a no-op based on stale status.

Keep recipe E unchanged. A full fresh-VM rerun is still required to prove recovery with the corrected probe.
This credential-free lane checks the local app path; it does **not** establish authenticated Tailscale Serve
publication or an actual phone screen opening, and there is no source evidence here requiring re-sharing a route.
