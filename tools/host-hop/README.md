# host-hop: move a Wizard to another machine

Reference scripts for the host hop in [spec/HOST_HOP.md](../../spec/HOST_HOP.md) (roles in
[spec/MACHINES.md](../../spec/MACHINES.md)). They make another machine on the owner's tailnet the **main**
and keep the old main as a fenced **standby**.

Tested once: Oscar, VPS (Ubuntu) → mini PC (Debian 13), 26 Oct 2026. Treat every other pair of machines as
untested; run each phase by hand and read its output.

## Setup

1. Same user, uid and `/etc/subuid`/`/etc/subgid` range on both machines; passwordless sudo; rootless Docker
   on the source; both machines on the tailnet with SSH aliases that reach each other.
2. `cp hosts.env.example hosts.env` and edit it. It is the only place for box values (agent name, host keys,
   tailnet names and IPs, machine-local units, OS-only units, paths). Role names derive from `HOP_AGENT`:
   `<agent>-main` and `<agent>-backup-<n>`.
3. Put pinned `sqlite3` and `sqlite3_rsync` binaries in `bin/` (not committed).
4. Review, then pin the bundle: `bash make-manifest.sh`. This writes `RELEASE-SHA256SUMS` over every
   `*.sh`, `*.py` and `*.env` here. The runner and `promote.sh` refuse to act if anything changed since.
5. Copy the whole directory to the same path on both machines.

`FROM` and `TO` below are host keys from `HOP_HOSTS`. Run everything on `FROM` (the current main) unless
noted.

## Phases

| Step | Command | What it does |
|---|---|---|
| 1 | `prepare-target.sh TO` | Checks user/uid/subuid/sudo, installs packages, writes the role file (`standby`) and standby lock. Starts nothing. |
| 2 | `sync.sh FROM TO` | Warm copy: home tree, live SQLite (`sqlite3_rsync`), Postgres base backup, images, volumes, staged units, venv recipes, inventories. Read-only on FROM. Rerun any time. |
| 3 | `standby-install.sh TO` | Installs staged units with the standby guard, disabled. Rebuilds venvs and node_modules. Ships images, volumes and Postgres. Nothing starts. |
| 4 | `install-status.sh FROM TO` | Status page on TO's raw tailnet IP (`HOP_STATUS_PORT`) and the restricted `host-hop-recovery` client. |
| 5 | `test-mode.sh TO start [--serve]` / `verify` / `stop` | Boots TO in an isolated preview. A firewall blocks all non-loopback egress, deny-listed apps and the gateway stay off, and `verify` writes evidence. Always `stop` before going on. |
| 6 | `launch.sh --probe FROM TO` | Read-only preflight in its own systemd unit. |
| 7 | `HOP_PARENT_LAUNCH=OWNER_RECOVERY_SENT launch.sh --parent-recovery-sent FROM TO` | The hop. Send the owner the recovery instructions (below) **before** setting the variable. |

The runner (step 7) does: preview teardown → warm sync → frozen inventory → standby install → drain and wait
for idle → stop schedulers → stop the source's exact units and containers → fence the source → final sync →
database count check → rename (`FROM`→`<agent>-backup-n`, `TO`→`<agent>-main`) → `promote.sh prepare` →
**promotion barrier** → `promote.sh activate` → Serve → `promote.sh verify` → completion notice
(`continue.sh`).

Afterwards, update `hosts.env` (TSNAMEs are now the role names) and re-pin before a hop back.

## Recovery

- **Status page:** `http://<TO tailnet IP>:<HOP_STATUS_PORT>/status.json`. It is served on TO, read-only,
  without the Wizard, and shows the phase, `promotion_barrier`, `source_stopped` and a failure id. Error
  details stay in a 0600 file under `~/.local/share/host-hop/private-failures/` on FROM.
- **On TO:** `/usr/local/bin/host-hop-recovery status | probe | abort | recover-source`. This is a restricted
  key on FROM (`recovery-access.sh` as its forced command) and can do nothing else.
- **`promotion_barrier: false`:** the new main never started. Any failure already restored the old main
  automatically (about 5 minutes). If it did not, run `host-hop-recovery recover-source`.
- **`promotion_barrier: true`:** the new main may have accepted writes. Nothing fails back, and
  `recover-source` refuses. Diagnose forward on TO. A move back needs a new, deliberate hop.
- `abort` signals only the pinned runner unit and PID.

## The eight lessons, as checks

1. **Asynchronous renames:** `wait_dns` polls up to 90 s, and recovery renames both machines back.
2. **Health checked too early:** `wait_health` and `promote.sh verify` wait with a bound before judging.
3. **Unknown containers:** `HOP_CONTAINER_SKIP_REGEX` and `HOP_UNIT_SKIP_REGEX` skip disposable
   `*-candidate`, `*-qa` and `*-test` names. Recovery skips transient units that no longer exist.
4. **Leftovers:** Postgres backups are named per run (`.warm-before-<run>`, `.before-final-<run>`).
   `test-final-pg.sh` runs the final copy twice.
5. **Ambiguous Docker lookups:** every lookup is `docker container inspect`. The runner tests fail on an
   untyped `docker inspect`.
6. **OS differences:** the unit gate in `promote.sh prepare` refuses before the barrier if a captured unit is
   missing on TO. Waive source-OS-only units in `HOP_OS_ONLY_UNITS`, and check host tools by hand.
7. **Self-references:** jobs that reach "the other machine" over SSH break after a hop. List them as
   machine-local (`HOP_HOST_LOCAL_UNITS`, `HOP_TARGET_OWNED`) and fix them in `HOP_POST_ACTIVATE_HOOK`.
   The Machines registry in the spec replaces this step.
8. **Secrets and logs:** failed commands go to a private 0600 file. Status and exceptions show only an id.

## Tests

```
python3 test-runner.py      # runner transaction, mocked (no host touched)
python3 test-teardown.py    # teardown.sh body against fixture shims
HOP_TEST_TARGET=<standby key> bash test-final-pg.sh   # real remote, disposable Postgres; skips without the variable
```

Never run `test-final-pg.sh`, `test-mode.sh` or `launch.sh` against a machine that is a live main unless you
mean it.

## Not here

Cloudflare tunnels, messaging webhooks, Mac/Windows mains (see the spec's "Not covered yet").
`rewrite-targets.txt` (configs rewritten in test mode) is per box. Generate it on the standby with
`python3 rewrite.py scan $HOME <FROM fqdn> <FROM ip> > rewrite-targets.txt`.
