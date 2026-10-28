# Promote 0.3.73: automatic app updates

## Why

Apps installed from the Wizard App Index stayed on the version they were installed at. A publisher's fix reached new
installs only; existing boxes kept the old version until someone ran `wam app update <id>` by hand. Miguel asked for
this to work for every owner (28 Oct 2026: "make sure the appropriate thing is built out for everyone").

## What changes

**Release contents.** 0.3.73 is 0.3.72 with **App Manager source `08b54f65` → `68ed4a26`** (branch
`maintenance/app-updates-0.3.73`). Everything else is exactly 0.3.72: the App Manager image
(`v4.10.2-wizard.571-80c76cf`, `sha256:ff30d81d…`), Wizard UX `970378b2`, Agent Service `b1f8d2c1`, Notifications
`cdce9f18`, Troubleshooter, Hermes, and every other image and default app.

The maintenance branch is 08b54f65 plus two commits, nothing else from main:

- `1d2efb45`: the Python/host part of wizard-app-manager **#305** (cherry-pick of 2985b046). It adds
  `wam/app_updates.py`, `wam app-updates`, `GET/POST /api/app-updates`, and makes `wam updates --ensure-timer` (run by
  `install.sh` on every installer run, line 139) also install and enable `wizard-app-updates.timer`. One adaptation:
  rollback calls `network_step` only when the App Manager has it, because this line has no app network isolation.
- `68ed4a26`: wizard-app-manager **#307** (merged on main as `b750a4b2`). The upgrade test below found that
  morning-report's `/healthz` answers `403 "Unknown host."` from loopback, so every working update of it was rolled
  back. The health/MCP check after an update is now required only when it answered just before the update.

`git diff --quiet 08b54f65 68ed4a26 -- packages Dockerfile package.json bun.lock turbo.json .github/workflows/image.yml`
shows no changes, so no image input changed. #305's backend fix (re-prepare an app's missing source copy,
`packages/backend/.../wizard-index-store.ts`) needs a new App Manager image and is **not** in 0.3.73. Until a later
release carries it, an app hit by that bug fails its update. The update is then undone the usual way (the old version
is kept, or restored from its backup), the owner is told, and it is retried after 7 days.

**What owners get.**
- Every night (04:30 + up to 1 h) the App Manager updates each Wizard App Index app that has a newer version, one at a
  time.
- It takes a Runtipi backup first, then checks the result: same running/stopped state, version moved, no restarting
  containers and no fewer running ones after 20 s, and the health URL or MCP endpoint answers (if it answered before).
- If the check fails, it restores the backup and sends one Notifications line.
- **Automatic by default**, separate from the Wizard OS update mode. `wam app-updates --ask` turns it off;
  `--hold <id>` keeps one app where it is.
- It never moves the shell, the Agent Service, Hermes, the release's default apps or `.wizard-selection` pins.

**Classification: feature** (DECISIONS #93 launch-phase fast-track). It is a new default-on behaviour on every box, not a
fix. There are no other ride-alongs: Stable is 0.3.72 and 0.3.73 changes only the App Manager source above.

**Risk.**
- Third-party app updates now reach boxes without an owner tap. The mitigations are the backup, the verify/rollback
  step, per-app holds, Ask me, and the 7-day back-off after a failure.
- An app whose update changes the published port or health path is judged on the new registry entry.
- Release default apps are skipped only when `WIZARD_RELEASE_PINS` is set. The installer's `~/.local/bin/wam` wrapper
  exports it, and the guest proves it: `files`, `transcriber` and `wizard-agent-service` have newer index versions and
  are skipped as `system`.

## Evidence: installed upgrade 0.3.72 → 0.3.73 on a disposable KVM guest

**Rig.** wizard-os `tools/acceptance/upgrade-rig/kvm_upgrade.py` from the `tools/release-train` branch (wizard-os
#296), unchanged except:
- its own systemd unit, headscale container name and ports (another thread's guest held the defaults);
- **6 GiB guest RAM** (the generated report text says 8 GB; host headroom).

Setup:
- Ubuntu 24.04 cloud overlay, 4 vCPU, user-mode NAT.
- Root stock Hermes v0.22.5 from the official installer (`--skip-setup`) + `hermes gateway install`.
- Tailscale on a local headscale with a pre-auth key. A test-only wrapper simulates HTTPS turned on; there is no Serve,
  so installs end box-only.

Nothing ran on the owner's box or any customer box.

**Install 0.3.72.** Public `curl -fsSL https://aiwizards.com/os.sh | WIZARD_RELEASE=0.3.72 WIZARD_STRICT=1 bash -s start`
(os.sh sha256 `fa9271d0…`), run as an agent:
- `done` in 535 s;
- `release.json` 0.3.72 pinned, 27 checks, 0 failed;
- `wizard doctor` / `wam doctor` 0 FAIL.

**Negative control on 0.3.72.** `wam app-updates` → `invalid choice: 'app-updates'` (exit 2).
`wizard-app-updates.timer` → `not-found`. No unit files.

**Upgrade.** Same public command with `WIZARD_RELEASE=0.3.73`.
- Disclosed override: `WIZARD_RELEASE_BASE=https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/7f927922…/releases`
  (the WAM mirror PR head; its `0.3.73.json` sha256 `f97ab231…` equals wizard-os #297 head `fd2304e4`), because the
  mirror was not merged yet.
- `done` in 109 s.
- `release.json` **0.3.73 pinned, 27 checks, 0 failed**; App Manager checkout `68ed4a26`.
- `wizard doctor` 0 FAIL, `wam doctor` 0 FAIL. Hermes API `/health` 200, gateway active, shell 302.
- Hermes `config.yaml` (`13a542c3…`), `.env` (`7571a19c…`) and `SOUL.md` (`36c1f5a2…`) are byte-identical before and
  after. Hermes is still v0.22.5.
- Containers: only `runtipi` and the release index were recreated, on the same image `sha256:ff30d81d…`. Every app
  container kept its StartedAt (same image, same start).

**App updates after the upgrade.**
- `wam app-updates` → `app_mode: auto`, nothing due. `files` 3→4, `transcriber` 3→4 and `wizard-agent-service` 2→3 are
  newer in the index but skipped as `system`, because the release pins them.
- `systemctl --user is-enabled/is-active wizard-app-updates.timer` → `enabled` / `active`; next run
  `Thu 2026-10-29 04:42 UTC`.
- The unit runs `ExecStart=/root/.local/bin/wam app-updates --apply-if-auto`, `OnCalendar=*-*-* 04:30`,
  `RandomizedDelaySec=1h`, `Persistent=true`.
- `wam app-updates --apply --dry-run` → `due: []` with the same three `system` skips.
- `wam updates` still reports Wizard OS mode `ask`, `chosen: false` (the OS mode is untouched).

**The nightly path, exercised for real** on the upgraded guest. The "older version" was simulated in the database:
1. `wam install morning-report` (index app, tipi 1, `0.5.6`).
2. Its Runtipi DB version was set to 0, so it is due. Dry run: `due: [morning-report 0 → 1]`.
3. `systemctl --user start wizard-app-updates.service`, the timer's own unit, ran `--apply-if-auto` → exit 0,
   `"message": "Updated morning-report (0.5.6)."`.
   - A Runtipi backup `morning-report-wizardapps-1793186000776.tar.gz` was made first.
   - Afterwards: DB version 1, running, container up.
   - `app-updates.json` `last.updated: ["morning-report"]`, nothing failed or rolled back.
4. The same step on the first guest, with App Manager `1d2efb45` (before #307), rolled the working update back:
   `its health check fails (http://127.0.0.1:8804/healthz)`. The endpoint answered `403 {"error": "Unknown host."}`
   before the update too. That is the #307 fix; 0.3.73 was re-pinned to `68ed4a26` before merge. That first run's
   installer upgrade had otherwise passed the same checks.

**Rollback** is covered by:
- the live forced-failure run on Oscar's (unpinned dev) box in #305: wizard-chatgpt 4 → 9 → restored to 4, running,
  MCP answering;
- `tests/test_app_updates.py` (`test_rollback_restores_the_backup_this_update_made`).

It was not forced on the guest.

**Tests on `68ed4a26`.**
- WAM full suite: 1167 passed, 8 skipped on `1d2efb45`.
- `tests/test_app_updates.py`: 11 passed on `68ed4a26`. Its 2 new tests fail without the #307 change.
- wizard-os `tools/tests`: 229 OK. `check_release.py releases/0.3.73.json` → ok. `promote_stable.py check` →
  `channels: ok`.

## Not checked

- Real Tailscale/HTTPS/Serve.
- Notification delivery to a phone. The guest's Notifications inbox was not read back, so the owner line is proven
  only by unit tests and by #305's live run on Oscar's box.
- A forced rollback on the guest.
- A fresh 0.3.73 install.
- Alongside on a non-root owner.
- Physical phones.
- Boxes on App Managers older than 0.3.69.
