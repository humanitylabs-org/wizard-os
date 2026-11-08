# Box state

**Status:** draft inventory, started for wizard-os#425 (from #134). Lists where a WizardOS box keeps state, and what a
backup and a restore do with each place today. The backup engine's own contract is wizard-app-manager
[`docs/BACKUP.md`](https://github.com/humanitylabs-org/wizard-app-manager/blob/main/docs/BACKUP.md). Its "What
travels" table and its per-machine list (`PER_MACHINE` in `wam/backup/box.py`) win where this page is less precise.

Rules used below:

- **Travels**: in the encrypted backup, and put back on restore, replacing the destination's copy.
- **Per-machine**: never captured and never replaced. The destination keeps its own.
- **Outside the backup**: lives outside the Wizard home, app data, agent homes and Files, so no backup sees it. The
  destination's installer or setup step makes its own.

A Wizard home entry travels unless the backup engine names it as per-machine, regenerated or engine state, or it is a
`*.lock`, `*.pid`, `*.tmp` or `*.bak*` file.

## Nightly maintenance

Contract: [MAINTENANCE.md](MAINTENANCE.md). Implementation: wizard-app-manager `wam/maintain.py` and `wam/os_patch.py`.

| State | Where | Backup and restore today |
|---|---|---|
| Owner choices: `os_security`, `quiet_restarts`, `held_platform`, `quiet_reboot`, `helper_removed` | `~/.wizard-os/maintenance.json` | Travels. See [the open question](#open-helper_removed-on-restore) for `helper_removed`. |
| Run history, last run, Health row | `~/.wizard-os/maintenance/` (`history.jsonl`, `last.json`, `health.json`) | Travels. The next nightly run on the destination overwrites `last.json` and `health.json`. |
| Run lease | `~/.wizard-os/maintenance.lock` | Not captured (lock file). |
| Nightly timer | `~/.config/systemd/user/wizard-os-maintain.{service,timer}` | Outside the backup. The destination's installer runs `wam maintain --ensure-timer`. |
| Root helper | `/usr/local/libexec/wizard-os/os-patch` (root-owned, 0755) | Outside the backup. The destination's installer runs `wam maintain setup --installer`. |
| Sudoers rule for the helper | `/etc/sudoers.d/wizard-os-maintenance` (root, 0440) | Outside the backup. Written by setup with the helper. |
| Restart lane sudoers rule (attended opt-in) | `/etc/sudoers.d/wizard-os-maintenance-restart-lane` (root, 0440) | Outside the backup. Only `wam maintain setup --restart-lane` writes it, so it is never on the destination after a restore. |
| Distribution updater pause (apt, `patch` mode only) | `/etc/apt/apt.conf.d/52wizard-os-maintenance` | Outside the backup. Written by the helper's `native-off` when the owner picks `patch`. A restored `os_security: patch` does not write it: the distribution's own updater keeps running on the destination until the owner sets the mode again. |

### Open: `helper_removed` on restore

`wam maintain remove` deletes the helper and both sudoers rules and records `helper_removed: true`. Later installer
runs (`wam maintain setup --installer`; a WizardOS update re-runs the installer) then skip the helper, so the owner's
removal sticks.

Because `maintenance.json` travels, a restore copies the source box's `helper_removed: true` onto a host whose own
installer has already put the helper in place. The helper stays installed on the new host, but every later installer
run skips refreshing it. After the next update that changes the helper, the installed copy is `stale`, every root
step is refused ("The OS patch helper is not installed"), and OS patching stops on the new host. Nothing tells the
owner that a flag copied from the old box is the cause.

The restore rule is not decided yet. Options:

1. Treat `helper_removed` as per-machine: a restore keeps the destination's value. The destination keeps the helper
   its installer put in place, and the owner removes it again there if they still want it gone.
2. Keep the source's value, and have restore (or the first nightly run after it) remove the destination's helper so
   the box matches what the owner chose. Root work during a restore.
3. Keep the source's value and show a Health line on the destination: "Root maintenance helper was removed on your
   old box. Run `wam maintain setup` to turn it on here."

Until this is decided, the installed upgrade test (#135) and the blank-host restore proof should record what they
see for this flag rather than assert one rule.

## Not yet listed

These state places exist in release 0.3.103/0.3.104 `latest` and still need rows here (wizard-os#425):

- Personality-replacement undo data: `$HERMES_HOME/cache/bring-data/` (`imports.json`, `SOUL.before-*.md`), Agent
  Service #336.
- The Wizard scheduler database `schedules.sqlite3` and the Incognito runtime, Agent Service #290. BACKUP.md already
  describes the scheduler and run-queue files and their limits.
- The owner's Look file, Pages `wizard-look/look.json`, wizard-ux #829.
- Saved notification levels, wizard-ux #899.
- App data folders left open to every user on the box (`a+rwx`) for the recipes that do not set `private_data`,
  wizard-app-manager #457.
