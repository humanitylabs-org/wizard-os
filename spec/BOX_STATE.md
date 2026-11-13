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
- **Not captured**: lives where a backup looks, but the engine or stock `hermes backup` leaves it out on purpose.
- **Not box state**: kept by each device (browser storage), not by the box.

A Wizard home entry travels unless the backup engine names it as per-machine, regenerated or engine state, or it is a
`*.lock`, `*.pid`, `*.tmp` or `*.bak*` file.

## Nightly maintenance

Contract: [MAINTENANCE.md](MAINTENANCE.md). Implementation: wizard-app-manager `wam/maintain.py` and `wam/os_patch.py`.

| State | Where | Backup and restore today |
|---|---|---|
| Owner choices: `os_security`, `quiet_restarts`, `held_platform`, `quiet_reboot`, `helper_removed` | `~/.wizard-os/maintenance.json` | Travels. For `helper_removed` see [the restore rule](#decided-helper_removed-on-restore). |
| Run history, last run, Health row | `~/.wizard-os/maintenance/` (`history.jsonl`, `last.json`, `health.json`) | Travels. The next nightly run on the destination overwrites `last.json` and `health.json`. |
| Run lease | `~/.wizard-os/maintenance.lock` | Not captured (lock file). |
| Nightly timer | `~/.config/systemd/user/wizard-os-maintain.{service,timer}` | Outside the backup. The destination's installer runs `wam maintain --ensure-timer`. |
| Root helper | `/usr/local/libexec/wizard-os/os-patch` (root-owned, 0755) | Outside the backup. The destination's installer runs `wam maintain setup --installer`. |
| Sudoers rule for the helper | `/etc/sudoers.d/wizard-os-maintenance` (root, 0440) | Outside the backup. Written by setup with the helper. |
| Restart lane sudoers rule (attended opt-in) | `/etc/sudoers.d/wizard-os-maintenance-restart-lane` (root, 0440) | Outside the backup. Only `wam maintain setup --restart-lane` writes it, so it is never on the destination after a restore. |
| Distribution updater pause (apt, `patch` mode only) | `/etc/apt/apt.conf.d/52wizard-os-maintenance` | Outside the backup. Written by the helper's `native-off` when the owner picks `patch`. A restored `os_security: patch` does not write it: the distribution's own updater keeps running on the destination until the owner sets the mode again. |

### Decided: `helper_removed` on restore

`wam maintain remove` deletes the helper and both sudoers rules and records `helper_removed: true`. Later installer
runs (`wam maintain setup --installer`; a WizardOS update re-runs the installer) then skip the helper, so the owner's
removal sticks.

Because `maintenance.json` travels, a restore copies the source box's `helper_removed: true` onto a host whose own
installer has already put the helper in place. Left alone, the helper stays installed but every later installer run
skips refreshing it, so after the next update that changes the helper every root step is refused and OS patching
stops on the new host.

Rule (wizard-os#425, the builder's pick of the three options listed there, because it is the only one that does no
root work and keeps the owner's choice): **the flag travels and is kept, and the mismatch is shown.** Nothing removes
or reinstalls the helper during or after a restore. Whenever `helper_removed` is set but a helper exists on the box,
Home > Resources > Health shows a **Maintenance helper: needs a choice** row naming `wam maintain setup` (keep it
here; clears the flag) and `wam maintain remove` (remove it here too). Either command clears the row.
A restore recomputes `maintenance/health.json` on the destination right away, so the row shows without waiting for
the next nightly run.
Implementation: wizard-app-manager `wam/maintain.py` `_helper_removed_item` and `refresh_health` (called from
`wam/backup/restore.py`), test
`tests/test_maintain_restore.py` (which also checks that the sudoers rules `setup()` writes list exactly the commands
in [MAINTENANCE.md](MAINTENANCE.md)).

To change it later (for example to treat the flag as per machine), change this section first.

## Agent and owner state

Places in release 0.3.103/0.3.104 `latest` that are not about maintenance (wizard-os#425). Each row says what a backup and a restore do **today**,
checked against the code named in its section. A row marked **Gap** is today's behaviour, written down so it can be
decided. Nothing on this page changes it.

### Personality-replacement undo data

Implementation: wizard-agent-service `hermes-plugin/wizard-os/bring_data.py` (`_state_dir()`), contract
`docs/bring-my-data.md`, Agent Service #336. Each agent's home is captured by stock `hermes backup`, which leaves out
everything under `cache/` except its media and citations folders (`_KEPT_CACHE_SUBDIRS` in Hermes
`hermes_cli/backup.py`).

| State | Where | Backup and restore today |
|---|---|---|
| Import record per agent: import id, kind, files written, skills, memory entries added | `$HERMES_HOME/cache/bring-data/imports.json` | Not captured (stock `hermes backup` leaves `cache/bring-data/` out). **Gap:** after a restore the Importer lists no earlier imports, so their Undo is gone on the new host. The files, skills and memory they wrote do travel with the agent home. |
| The personality and About me before an import replaced them | `$HERMES_HOME/cache/bring-data/` (`SOUL.before-<import>.md`, `About me.before-<import>.md`) | Not captured, same reason. **Gap:** on the new host the replaced `SOUL.md` cannot be put back through Undo. The current `SOUL.md` and `About me.md` travel. |

### Wizard scheduler and Incognito

Implementation: wizard-agent-service `server/index.mjs` (`schedulerStatePath`) and `server/incognito.mjs` with
`ops/agent-runtime/incognito_runtime.py`, Agent Service #290. Backup behaviour: wizard-app-manager `docs/BACKUP.md`,
"Wizard scheduler / run queue" row, which wins over this table.

| State | Where | Backup and restore today |
|---|---|---|
| Wizard schedules and pending runs | `$HERMES_HOME/state/wizard-mobile/` (`schedules.sqlite3`, `run-queue.sqlite3`) | Travels inside the agent's stock `hermes backup`, copied as plain files (no SQLite snapshot). Not paused on arrival: `wam backup activate --old-is-off` does not fence them. Stop the source Service before export. A custom `WIZARD_SCHEDULER_STATE_PATH` outside the agent home does not travel. |
| Incognito conversation home | A RAM-only container, `/opt/data` on `tmpfs` | Not captured, by design: it is never written to disk and ends with the conversation. A restore never brings back an Incognito session. |
| Incognito runtime helper | `~/.wizard-os/agent-runtime/` | Per-machine (`agent-runtime` in `PER_MACHINE`). The destination keeps its own. |

### Owner Look file

Implementation: wizard-ux `web/core/look-sync.js` (wizard-ux #829), stored through the Agent Service Pages file API
([PAGES.md](PAGES.md)).

| State | Where | Backup and restore today |
|---|---|---|
| Skin, feature switches (`tweaks`, `defaults`) and shell views for every device | `media/Pages/wizard-look/look.json` (the owner's Files) | Travels in the Files tree, unless the export used `--no-files`. Without it each device keeps its own last copy, and the first device that has switches on seeds the new box. |
| Its save history | `<Agent Service state>/pages-history.git` | Travels in the Agent Service's app data (`app-data/data/`). |
| Each device's own copy | Browser storage on the device (`wos.skin`, `wos.skin-tweaks.v1`, `wos.look-sync.v1`) | Not box state. The device keeps it; the box copy wins at the next sync. |

### Saved notification levels

Implementation: wizard-ux `web/core/notif-bell.js` ("Routing: notification levels", wizard-ux #899).

| State | Where | Backup and restore today |
|---|---|---|
| Level per source (Chats, Badge, Morning report, Off) and per System kind (`system:<kind>`) | The Notifications app's own data, saved through `/notifications/api/routes` | Travels in the Notifications app's data archive. The app is refused when the backup holds a newer Notifications release than the destination offers, and then the levels stay as the destination has them. |
| This device's fallback copy | Browser storage (`wos.notify.route.v1`) | Not box state. On a box with nothing saved, the first device to sync uploads its copy once, then the box wins. |

### App data folder modes

Implementation: wizard-app-manager `packages/backend/src/modules/apps/app-files-manager.ts`
(`setAppDataDirPermissions()`), policy in `docs/private-app-data-permissions.md`, wizard-app-manager #457.

| State | Where | Backup and restore today |
|---|---|---|
| Owner, group and mode of every file in an app's data | `<runtipi>/app-data/<store>/<app>/` | Travels: the app data archive keeps owners and modes. **Gap:** on the destination, install and start run `chmod -Rf a+rwx` over the app's data again unless its recipe sets `private_data: true`. So a folder that was private on the source is open to every user on the new host. In the 6 Nov survey none of the 34 recipe folders set it (Messenger's opt-in is its own PR). |
