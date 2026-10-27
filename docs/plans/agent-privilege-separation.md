# Agent privilege separation — Build Brief (final v3, Fable PASS WITH NITS after 3 rounds, 27 Oct 2026)

Status: agent proposal for James's approval. Reviews: Fable round 1 (SOUND WITH CHANGES, 10 changes adopted),
round 2 (FAIL on forgeable approvals, fixed in v3 via wam-verified owner approval; nits adopted),
round 3 (focused recheck). Load-bearing claims spot-checked in source by Archimedes.

**Outcome:** On every Wizard OS box (fresh and alongside, one configuration) the AI agent manages apps by asking
the App Manager for named actions, and holds no root-equivalent power: no docker group, no Docker socket, no sudo,
no Tailscale operator. Risky app requests complete only after the owner taps Approve in Wizard. Developers keep a
visible, expiring "full server access" grant, available only inside developer mode.

**Acceptance (forum VMs: fresh, alongside with an unprivileged Hermes user, alongside migrated from today's layout):**
1. `id <agent>` has no docker/sudo/wheel; `sudo -n true` fails; restricted-agent conformance D1–D3 (no
   docker/containerd socket, no Docker TCP) pass against the main agent; the agent cannot write any file the
   service account or root later executes or loads (state lives outside the agent's home); the files root is the
   one agent-writable path apps may mount.
2. From chat: install from the store, start/stop/restart, logs, restore a snapshot from the box's own backup
   repository (or undo one), publish an installed app's link, build a new app from source and open it, update Hermes
   (alongside: the agent's own `wam hermes update`; fresh: a service app-update of hermes-agent). No owner prompt.
3. Refused from the agent, approved only by the owner in Wizard: a recipe or build with privileged, host
   namespaces, devices, cap_add, security_opt, sysctls, runtime socket, `build.secrets/ssh`, `env_file`/`secrets`/
   `configs` from a host file, or any mount outside the app's own data and the files root; importing any backup
   file; `grants`, `network allow`, `updates apply`. `docker run -v /:/host` and `tailscale down` fail. A process at
   the agent's uid that forges the Agent Service owner-proof header against the Approve route is refused.
4. Existing boxes migrate via the normal update with apps, data, links and chats intact; `wam privilege rollback`
   restores the old layout; a rehearsal on a copy of James's box passes before any live box.
5. Developer mode → "Give the agent full server access": owner-approved, red row on Health, sudo log of every
   use; after expiry or developer mode off, new sudo calls fail and Health warns if `/etc/sudoers.d` or the root
   helpers changed during the grant.

**Constraints:** one configuration; stock Hermes untouched; no served feature dropped (parity gate); Troubleshooter
still repairs with the AI login dead; no passwords in chat; dev team never locked out.

## Facts that shaped this (verified in source)

- Fresh: `get.sh:975-977` gives `wizard` docker + `NOPASSWD:ALL`. The fresh agent's terminal is local inside its
  container (no SSH route on Linux), so fresh boxes are *nearly* there; the sudo line is the hole, used by humans
  over SSH and by `builder_bundle._sudo` / doctor's `sudo -n docker` fallback.
- Alongside: one uid (the Hermes user) owns Runtipi, `~/.wizard-os`, the wam checkout, user units, the Agent
  Service. That's the real refactor.
- `wam serve` API covers only install/bootstrap/registry/updates/uninstall; lifecycle, logs, backup, links,
  builder, views, doctor --fix are CLI-only. The Agent Service gateway never calls wam.
- Install gate = `network.host_access` (privileged, socket, network escapes); no bind-mount check. Stricter
  `wizardmd.compose_risks` exists but only for the builder/private agents and misses `/opt,/srv,/mnt,/tmp,/var/lib`.
- Backup restore writes `user-config/` overrides before Runtipi starts the app, unchecked (restore.py:616-623).
- Agent Service falls back to `BOX_OWNER` with no owner proof (principals.mjs:108), and its owner proof is a secret
  file readable at the agent's uid (service.mjs:4632): the Agent Service cannot be the approval authority.
- More sudo fallbacks to remove: links.py:25-29 (`sudo -n tailscale`), agent_link.py:98-103, backup/dockercli.py:79,
  test_catalog.py:51, builder_bundle.py:44-58,384-392.
- The root-helper pattern in MAINTENANCE.md (`os-patch`, `wam maintain`) is specified, **not built**.
- "Developer mode" is Decision #97 (follow a branch): decided, not built, Miguel still to confirm. The grant hangs off it.
- Spec already says it for everyone but the main agent: AGENTS.md:84, :134; PERMISSIONS.md:93; SECURITY_INVENTORY
  rule is containers-only; MAINTENANCE.md:72 relies on passwordless sudo.

## Design

Principals:
1. **root** — fixed, argument-checked helpers in `/usr/local/libexec/wizard-os/`, one sudoers line each, installed
   and updated only by the owner-approved host step (existing approval relay, get.sh:728-874), never by the nightly
   updater. Helpers: host-prep, os-patch, restart-agent-gateway (Troubleshooter), tailscale-operator, server-access.
2. **`wizard-system`** — owns Runtipi, wam state and checkout under `/var/lib/wizard-os` (never inside the agent's
   home), docker group, Tailscale operator; system units for `wam serve`, troubleshooter/guardian, backup and
   update timers. Never runs a model.
3. **Agent** — fresh: the hermes-agent container. Alongside: the owner's Hermes user as-is. Gets an agent-scoped
   wam token and a thin `wam` client; `wizard-files` group for the files root. Keeps doing what is its own:
   `wam hermes update` (hermes_update.py requires the owner uid), `wizard link`, host dashboard unit.
4. **Agent Service** — keeps the agent's uid (needs `state.db`), but its writable state moves to its own directory;
   it receives the Hermes API key through `wizard link`, wam never reads the agent's files.

Policy in the service:
- Agent verbs: store install, update, uninstall, start/stop/restart, logs, backup run, restore `--from-repo <snapshot>`
  and `undo` against the box's repository (service-written, box key unreadable to the agent), links publish
  (registry apps only, never a raw port), build/update from source, doctor. Owner-only (strict owner session):
  host-access approval, `grants`, `network allow/off`, `updates apply/mode`, backup import, developer mode.
- One **allowlist** compose check (keys + mount sources) shared by install, update, builder output and restore;
  replaces both `host_access` and `compose_risks`. Fail → 409 `needs_owner_approval` with an approval link.
- **wam is the approval authority, not the Agent Service.** The Approve page is served by `wam serve` (service
  account) on its own `tailscale serve` route, like store data (store_data.py:233), and wam checks the caller's
  tailnet identity itself: root-owned peer socket (tailscaled) plus `Tailscale-User-Login` equal to the node owner,
  the strict store rule (store_install.py:42-52, 149-164), which refuses tagged nodes. The owner login is pinned at
  host-prep; Health warns if it changes. The Wizard card only shows the link. No usable owner login (unpaired or
  tagged node) → the existing server-password approval relay; neither → the one terminal command. Nothing the
  agent's uid can read approves. Hardening: the UX-only shell override gets a non-root `user:` (alongside.py:500-512),
  and a test proves a root host-network container posting the owner header is refused.

**Full server access (developer mode only):** owner turns on developer mode (#97), then "Give the agent full server
access", approved on the wam-served Approve page. Root helper writes `/etc/sudoers.d/91-wizard-agent-access`
(`<agent> ALL=(root) NOPASSWD: ALL`, expiry in a comment) and a root timer deletes it at expiry (default 7 days,
or "until I turn it off"). Sudo re-reads per call, so new calls stop at expiry; every use is in the sudo log; the helper
checksums `/etc/sudoers.d` and the libexec helpers at grant start and Health warns on drift after. Health shows a red
row while on, and logs developer-mode source changes made during a grant. It's root and the UI says so. Turning
developer mode off deletes the grant. Migration grandfathers today's docker members into a 7-day grant shown on
Health; it can only be extended once developer mode is on. Humans keep SSH as root/`wizard` regardless.

## Slices (order: 0 → 1 → 2 → 3 → 4 → 5 → 6)

0. **Spike (1 day):** confirm Agent Service uid/state split; list every `wam`/`docker`/`sudo` call in shipped
   skills (wizard-builder build.md:11, SKILL.md:24,62; REPAIR_KIT; kernel plugin); find boxes running box-only;
   Mac VM `agent-ssh` route.
1. **Fresh-box sudo out (3–4 days, ships alone):** drop `NOPASSWD:ALL` from get.sh; replace every `sudo -n` fallback
   (builder bundle edits the agent's config inside the container as uid 1000 like agent_link.py; links, dockercli,
   test_catalog); build the root-helper installer + os-patch + tailscale-operator so maintenance and links keep
   working. Acceptance 1 on a fresh VM.
2. **Allowlist policy + wam approval (4–5 days, wam + Agent Service + wizard-ux card):** one compose allowlist used by
   install/update/builder/restore; owner-only verbs; wam-served Approve page with its own tailnet identity check;
   regression tests named for David's audit (`/:/host`, privileged, build secrets, restored override, forged owner
   header). This lands the rules early and guards owner-driven installs; it binds the agent only from slice 3, while
   the agent still owns `~/runtipi` and the docker group.
3. **Alongside skeleton (5–6 days, highest risk):** host-prep creates `wizard-system`, state under
   `/var/lib/wizard-os`, system units, agent token + thin client for lifecycle/logs; unprivileged-Hermes VM (the
   David case) passes acceptance 1 and the lifecycle part of 2.
4. **Rest of the agent verbs (4–5 days):** backup/restore-own, links publish, builder staging (agent source copied
   into service-owned staging, then allowlist, then build), doctor. Acceptance 2.
5. **Developer mode + full server access (3–4 days):** build #97's source setting, banner and return path (after
   Miguel confirms #97), then the grant helper, expiry timer, drift check and Health row. Acceptance 5.
6. **Migration (4–6 days, risky):** update path relocates state, swaps units, rotates the api-token, moves the
   Tailscale operator from the Hermes user to `wizard-system` through a new explicit root-run reassign path in
   prepare-named-user.sh (it refuses today, lines 45-49), grandfathers access; `wam privilege rollback`; rehearse on a copy of James's box, then Miguel/Jan
   testers, James's box last. Update skills and REPAIR_KIT wording. Acceptance 4.

**Spec (lands with slice 1):** DECISIONS row (text in round1-response §6, with "Server access" folded under
developer mode); new spec/PRIVILEGE.md (principals, agent vs owner verbs, compose allowlist, root helpers, the grant,
conformance checks); amend AGENTS.md:84, PERMISSIONS.md:93-94, MAINTENANCE.md:71-73, SECURITY_INVENTORY rule,
os.md:21, REPAIR_KIT.md:263.

**Deferred:** the main agent in the restricted-agent container on alongside boxes (AGENTS.md:134), egress limits for
the main agent, rootless Docker, per-app seccomp/AppArmor.

**Size:** ~25–32 agent-days total. Slices 1–2 are contained (about 8 days) and close the fresh-box hole; the rules
only bind alongside agents once slice 3 lands. Slices 3 and 6 are the breaking part: they change which account owns
what on every existing alongside box, so they go through a rehearsed migration with rollback.
