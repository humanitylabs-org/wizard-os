# Host hop: move a Wizard to another machine

**Status:** proposed by Miguel, 26 Oct 2026. Proven once in production: Miguel's Wizard (Oscar) moved from a VPS (Ubuntu) to a mini PC (Debian 13, installed from `wizard-os-iso`) on 26 Oct 2026. Reference scripts: `tools/host-hop/` (to land in a follow-up PR). James's box is the next test.

A Wizard's **main** is the machine that runs its agent, apps and data. A **host hop** makes another machine on the owner's tailnet the main, with the same history, apps, schedules and address, and keeps the old main as a **standby**. It is how an owner moves off a full or rented server, upgrades hardware, or recovers from a failing box.

This builds on [MACHINES.md](MACHINES.md) and [DEVICES.md](DEVICES.md): every machine in the owner's Machines list has one role.

## Roles

| Role | Runs | Machines access |
|---|---|---|
| **Main** | The Wizard: agent, Agent Service, shell, apps, schedules. Exactly one per Wizard. | Grants helpers to its agents |
| **Standby** | A full copy of the main, kept in sync, every Wizard service fenced off (cannot start, even after a reboot) | May also work as a helper with its spare CPU/disk, never touching the copied Wizard data |
| **Helper** | Jobs for the main (agent-owned level in MACHINES.md) | Granted per agent |

`wizard-os-iso` makes a **helper-ready** machine (Debian, Tailscale, SSH). "Add a standby" turns a helper into a standby. A hop swaps main and standby. The old main becomes a standby that can also take helper jobs.

## Owner flow (Settings → Machines)

1. **Add a standby.** Pick a machine from the list. Wizard checks it (OS, disk, CPU architecture, free space ≥ 1.5× the main's data), installs the Wizard runtime at identical paths, and fences it.
2. **Keep in sync.** Incremental copy on a timer. Shows last sync time and size. The first copy takes hours. Later ones take minutes.
3. **Test.** Starts the standby in an isolated preview (no outbound network except loopback, messaging/device apps off) and shows machine-checked evidence plus a temporary URL.
4. **Switch.** A dry run shows the expected offline time, measured from the last sync. Then it waits for the Wizard to be idle, stops the main, copies the last changes, swaps names and starts the standby as main.
5. **Switch back.** The same action in reverse. The old main has all data up to the switch.

## Client: workspaces and the hop screen

The native clients (Android `ai.wizards.os`, Wizard for Mac) gain a **workspace switcher**: a list of Wizards the owner can open, such as "Oscar", "Carlos" and "AI Wizards". Each entry is a Wizard identity plus its current main address. The same switcher serves a hop:

- Clients address a Wizard by its role name `<agent>-main.<tailnet>`, never a machine name, so a hop needs no new bookmark.
- During a switch the main publishes `hop: {phase, eta_seconds}` on a small status endpoint that stays up on the standby (independent of the Wizard). The client shows a hop screen ("Moving Oscar to Mini PC · about 6 minutes") instead of a connection error, then reconnects to the same name and reopens the thread the owner was on.
- Pending sends stay queued in the client outbox and deliver after the switch.
- Adding another workspace uses the same pairing as [PHONE_SETUP.md](PHONE_SETUP.md). Switching workspaces never mixes chats, notifications or credentials between Wizards.

## What the switch must guarantee

- **One writer.** The old main is fully stopped and fenced before the new main may write. A durable **promotion barrier** is recorded before any new-main service starts. Before the barrier, any failure restores the old main automatically. After it, nothing fails back automatically.
- **No lost turns.** The switch starts only after 60 s with no agent runs, streams, turn leases, background helpers or cron locks. New turns are refused (gateway drain) while it waits, and waiting is bounded (2 h, then it gives up and leaves the main running). Threads resume with "continue". A reply in progress cannot move mid-stream.
- **Exact data.** SQLite with `sqlite3_rsync`, Postgres as a cleanly shut-down physical copy (checksummed, control state verified), files and Docker volumes with rsync inside the rootless-Docker uid map. Session and message counts must match before the barrier.
- **Exact set.** The new main starts exactly the units, schedules and containers that were running before the stop, from an inventory frozen before the stop, never re-read from the stopped machine.
- **Recovery reachable without the Wizard.** A read-only status page on the standby's raw tailnet IP, and a restricted recovery key that can only `status`, `probe` or `recover-source`.

## Lessons from the first hop (each became a check)

Each of the four attempts failed safely and restored the old main in about 5 minutes. Every cause was a difference between machines or a timing assumption:

1. **Asynchronous renames.** Tailscale applies a hostname change seconds later. Poll for it (≤ 90 s), never assert once. Undo the rename on failure.
2. **Health checked too early.** Services listen seconds after systemd reports them started. Every health and verify step waits with a bound.
3. **Unknown containers.** A disposable test container started by another thread blocked the inventory. Disposable containers and units follow a naming rule (`*-candidate`, `*-qa`, `*-test`) that the hop skips, and recovery ignores transient units that no longer exist.
4. **Leftovers from earlier attempts.** A previous attempt's backup folder blocked the database swap. Every attempt names its own backups by run id.
5. **Ambiguous Docker lookups.** `docker inspect NAME` matched a volume with the container's name. Use `docker container inspect`.
6. **OS differences.** Ubuntu-only user units (`session-migration`, `launchpadlib-cache-clean`) do not exist on Debian, and host tools (`ripgrep`, `chromium`, `psql`, `tmux`, `rclone`) were missing. "Add a standby" inventories the main's units, packages and binaries and installs or explicitly waives each one. Promotion refuses before the barrier if a captured unit is missing.
7. **Self-references.** A job that reached the mini PC over SSH broke once it ran on the mini PC. Helper addresses resolve through the Machines registry, which knows "this machine".
8. **Secrets and logs.** Failure details go to a private 0600 file, and the status page shows only a failure id.

## Not covered yet

- Cloudflare tunnels and public routes still point at the old machine. Repoint them as a step of Switch.
- Messaging bots (Telegram etc.) move with the agent, but their webhooks must be checked after the switch.
- A Mac or Windows main.
- Switching between Wizards owned by different people. Admin on someone else's Wizard needs its own spec.

## Build order

1. Land the reference scripts with every box value moved to one settings file, plus their tests (23 runner tests, Postgres fixture, teardown fixture).
2. James hops Archimedes from Thales to a second machine with the scripts and reports gaps.
3. The Machines page gains Role, Add standby, Sync, Test, Switch and Switch back, calling a small root-capable helper on each machine.
4. Native clients gain the workspace switcher, hop screen and outbox hold.
