# Privilege: no AI agent is root-equivalent (Decision #105)

Status: proposed on branch `feature/agent-privilege-separation`. Build plan:
[docs/plans/agent-privilege-separation.md](../docs/plans/agent-privilege-separation.md).

An agent reads untrusted input all day: email, web pages, messages. One prompt injection must never be able to
rewrite the server. So on every Wizard box, fresh or alongside, in one configuration, the account or container an
AI agent runs in holds **no docker group, no Docker or containerd socket, no sudo and no Tailscale operator right**.
The system still has that power; the agent asks for it by name.

## Principals

| Principal | Holds | Never |
|---|---|---|
| **root** | Fixed, argument-checked helpers in `/usr/local/libexec/wizard-os/` (host-prep, os-patch, restart-agent-gateway, tailscale-operator, server-access), one sudoers line each | Installed or changed by the nightly updater; only the owner-approved host step installs or updates them |
| **`wizard-system`** | Runtipi, App Manager state and checkout under `/var/lib/wizard-os`, the docker group, Tailscale operator, the system units (`wam serve`, Troubleshooter, backup and update timers) | Runs a model; writes into a tree an agent owns |
| **Agent** (fresh: the `hermes-agent` container; alongside: the owner's Hermes user, unchanged) | An agent-scoped App Manager token, a thin `wam` client, read/write on the files root, its own Hermes (`wam hermes update`, `wizard link`) | Docker, sudo, Tailscale operator, write access to anything root or `wizard-system` executes, loads or mounts (except the files root) |
| **Agent Service** | Runs at the agent's uid (it reads `state.db`); its own writable directory; receives the Hermes API key through `wizard link` | Acts as the approval authority |

## Agent actions and owner actions

**Agent token** (no prompt): store install, update, uninstall, start, stop, restart, logs, backup run, restore a
snapshot from the box's own backup repository (`--from-repo`) and undo it, publish the link of an installed app,
build and update an app from source, doctor.

**Owner only:** approving a recipe that needs host access, `grants`, `network allow` / `network off`,
`updates apply` and update mode, importing any backup file, developer mode, server access.

## The app check (one allowlist)

Install, update, builder output and restore all pass the same allowlist of compose keys and mount sources. Anything
outside it needs the owner: privileged, host network/PID/IPC/user namespaces, devices, `cap_add`, `security_opt`,
`sysctls`, a container runtime socket, `build.secrets` / `build.ssh`, `env_file`, `secrets` or `configs` read from a
host file, and any mount outside the app's own `app-data` and the files root. A refused request returns
`409 needs_owner_approval` with an approval link.

## Owner approval

The App Manager, not the Agent Service, decides who the owner is. Its Approve page is served by `wam serve` on its
own `tailscale serve` route and accepts a request only from a root-owned peer socket (tailscaled) carrying the
node owner's `Tailscale-User-Login` (the strict store rule: a tagged node approves nothing). The owner login is
pinned at host-prep; Health warns if it changes. Without a usable owner login the existing server-password approval
page is used, and without that, one terminal command. Wizard shows the link; nothing an agent's uid can read
approves.

## Server access (developer mode only)

Developers sometimes need their agent to work on the system itself. Inside developer mode (#97) the owner can
**Give the agent full server access**, approved on the Approve page. The `server-access` helper writes
`/etc/sudoers.d/91-wizard-agent-access` with an expiry (7 days by default, or until turned off), and a root timer
removes it. It is root and Wizard says so: a red Health row while on, every use in the sudo log, a checksum of
`/etc/sudoers.d` and the helpers at grant start and a Health warning if they changed afterwards. Turning developer
mode off removes the grant. It never changes the layout. Boxes whose agent is in the docker group today get a
7-day grant when they migrate; it can be extended only once developer mode is on.

People are never locked out: owners keep their own server login (SSH as root or their admin account).

## Conformance (every release, fresh and alongside)

From the agent's runtime: `id` shows no docker/sudo/wheel; `sudo -n true` fails; restricted-agent checks D1–D3
(no docker or containerd socket, no Docker API over TCP) pass; `docker run -v /:/host` and `tailscale down` fail;
a recipe with a host mount is refused until owner approval; a forged owner-proof header on the Approve route is
refused.
