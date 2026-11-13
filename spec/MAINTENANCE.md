# System maintenance

Every WizardOS box keeps itself patched and backed up. Neither the owner nor the agent has to do anything. The box
runs one platform-owned job each night, `wam maintain run`, from the App Manager. It is not a Hermes cron job or a
skill, and it keeps working while the agent is down. Implementation: `wam/maintain.py` and `wam/os_patch.py` in
wizard-app-manager.

## What one nightly run does

All steps share one maintenance lease, one owner-visible history and one Health row per step.

| Step | Owner | State |
|---|---|---|
| OS security patches | `wam maintain` → `os_patch` | slice 1 (this spec) |
| Backups: catch up a missed one, report whether the last one succeeded and was read back | `wam backup` (wizard-app-manager #61) keeps its own schedule and lock | slice 2 |
| The owner's Automatic WizardOS update (stable, promoted releases), only when quiet | `wam updates` (`apply_if_auto`) | slice 3: replaces the separate 03:30 timer |
| Hermes and app updates | `wam hermes update`, `wam app update` | stay explicit for now |
| Repair | Troubleshooter guardian (report-only until the owner turns repairs on) | unchanged |
| Quiet restarts and reboots | not offered | gated, see [Restarts](#restarts) |

The timer fires at 02:00 box-local time, with up to 45 minutes of random delay. That is after the 00:00 backup and
before the 03:30 WizardOS update window. A missed night runs at the next boot (`Persistent=true`).
The maintenance timer is always on, even with OS patching `off`: it owns the nightly backup check and the Automatic
update. Installing it retires `wizard-os-update.timer`, and `wam updates` never reinstalls that timer while it exists.
A daily backup older than 26 hours (weekly: 7 days) is caught up with `wam backup run --scheduled`. Health shows
**Backups**: `verified, Nh ago`, `backed up Nh ago` (not read back this week), `last run failed`, `last N days ago`
(error after 50 hours), or `not set up`.

## OS security patches: any Linux, using its own updater

`os_patch` reads `/etc/os-release` (`ID`, then `ID_LIKE`, then whichever package manager is present). It then uses
that system's own package manager and its security channel. Each family is one small backend class, so adding a
distribution means adding one class.

| Family | Systems | Security updates | Installs | Restarts during install |
|---|---|---|---|---|
| apt | Debian, Ubuntu and derivatives | origins with `-security` (`apt-get -s dist-upgrade`) | yes | blocked: a temporary `policy-rc.d` refuses every service action and needrestart is suspended |
| dnf | Fedora, RHEL, Rocky, Alma, Amazon | `dnf updateinfo --security` | yes | package scripts may try-restart their own service; skipped whenever a held package is in the set |
| apk | Alpine | stable branches carry only fixes | yes | none (OpenRC packages do not restart) |
| zypper | openSUSE, SLES | `list-updates --type patch --category security` | report only (slice 1) | none |
| pacman | Arch | no security-only channel (rolling) | report only | none |
| unknown | | | report "not supported" | none |

**Held packages.** Upgrading these would restart what the box's work runs on: the container runtime (docker,
containerd, runc, podman), the private network (tailscale), and init/dbus (systemd, udev, dbus). They are never
installed by a nightly run. They are reported as waiting for the quiet-restart lane.

**After an install,** the running services keep their old code until they next restart. The run records which
processes still use replaced libraries and whether a newer kernel needs a reboot. Health shows both.

**The distribution's own updater.** Ubuntu turns unattended-upgrades on by default, and its needrestart integration
can restart services automatically. Choosing `patch` pauses that updater with one file,
`/etc/apt/apt.conf.d/52wizard-os-maintenance`, and the box does the same security patching itself without restarts.
Going back to `check` or `off` deletes the file and hands patching back to the distribution. Other families keep
whatever the owner set.

## Owner setting

`~/.wizard-os/maintenance.json` → `os_security`. The installer never writes it, and it survives reinstalls.

| Value | Meaning |
|---|---|
| `check` (default) | Look every night and show pending fixes in Health. Changes nothing. |
| `patch` | Also install pending security fixes, only once the box has been quiet for two checks in a row. Never restarts a service or reboots. |
| `off` | No OS check. The nightly timer stays for backups and updates. |

`patch` becomes the default only after the gates in [Restarts](#restarts) pass (James, 23 Oct 2026).

## Privilege

The App Manager runs as the box's owner account. Root work goes through one fixed helper,
`/usr/local/libexec/wizard-os/os-patch`, installed root-owned by `wam maintain setup`. The installer runs setup, using
the passwordless sudo that `get.sh` already sets up. The matching `/etc/sudoers.d/wizard-os-maintenance` allows
exactly seven argument lists: `check`, `check --refresh`, `apply`, `native-off`, `native-on`, `restart-check`,
`remove`. The restart lane has its own rule, `/etc/sudoers.d/wizard-os-maintenance-restart-lane`, written only by an
attended `wam maintain setup --restart-lane`; it allows `restart-service *`, `apply-held` and `reboot`. The helper
takes no other input, so it cannot run a package name, a path or a shell command it was given. A box without sudo
stays `check`, with an unprivileged check; Health shows the one command that turns patching on.

Besides the read-only checks, the owner account can do three things through the main rule: force a patch run, pause
the distribution's own updater (`native-off`), or remove the helper. Nothing else, and no shell.

`wam maintain remove` deletes the helper and both rules, sets `os_security` back to `check`, turns off `quiet_restarts`, `held_platform` and
`quiet_reboot`, and records
`helper_removed: true` in `maintenance.json`. Installer runs then skip setup until the owner runs `wam maintain setup`
again. After a restore the flag is kept, and Health asks the owner to choose when a helper is installed on the new box: see [BOX_STATE.md](BOX_STATE.md#decided-helper_removed-on-restore).

## Safety rules

- **One lease.** `~/.wizard-os/maintenance.lock`. A run also refuses while a Hermes update holds
  `hermes-update.lock`. A busy run records `busy` and changes nothing.
- **Quiet only.** The quiet check is the same one `wam hermes update` uses: no queued or active Agent Service run and
  no active Hermes gateway work. It waits up to 30 minutes. If the box is still busy, it records `deferred` and tries
  again the next night.
- **No restarts, no reboots.** See the table above.
- **Crash safety.** A `policy-rc.d` left behind by a killed run is detected by its marker and removed at the start of
  the next run. An owner's own `policy-rc.d` is never touched.
- **History.** Every run appends one line to `~/.wizard-os/maintenance/history.jsonl` (bounded to 400). It also writes
  `last.json`, plus `health.json` in the Health shape (`WIZARD_SYSTEM_HEALTH_FILE`, wizard-ux
  `tools/system-health.mjs`). The row is **Security updates** and shows `up to date`, `N pending`, `N installed`,
  `waiting for quiet`, `not supported`, or `not running` after 3 days without a run.

## Restarts

Restarting services or the server is a separate lane. Automatic restarts are off on every box until every gate below
passes on Thales test machines. James and Archimedes run these gates together.

1. **No lost work.** A restart during a live chat run, voice upload, scheduled job, app job or Hermes update never
   happens. Each of these work types is run as a real job while the lane is asked to restart, and the job must finish
   intact.
2. **Always comes back.** 50 or more forced restart and reboot cycles per supported family, each followed by Health
   green: Agent Service, shell, apps, private network and timers. Each cycle also recovers on its own from a held
   container-runtime upgrade.
3. **Rollback.** A failed post-restart health check restores the previous package version where the distribution can
   (apt pinned versions, `dnf history undo`). Otherwise it stops and posts one owner note.
4. **Distribution matrix.** The apply path is green on Debian 12, Ubuntu 22.04 and 24.04, Fedora, Rocky/Alma 9 and
   Alpine. Mac VM guests and the Wizard 1 Debian image are included.

Until then, the restart lane reports what needs a restart. Owners restart from Home → Resources.

## Rollout

Ships in a normal WizardOS release. The installer runs `wam maintain setup` and `wam maintain --ensure-timer`.
Existing boxes get it on update. Alongside boxes, where Hermes runs on the host, follow the same path. Containerized
Hermes boxes are unaffected: the step patches the host OS, not the containers.
