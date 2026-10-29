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

**Final gate.** The Python App Manager is not the only caller of the backend API, so its check is not the boundary.
Immediately before any Compose command that can create or change a container (`up`, `create`, `run`, `build`,
`watch`), the privileged backend reads Compose's own merged and interpolated model of that exact invocation
(generated recipe, user override, every env file) and refuses any host-reaching setting not recorded for that app in
`user-config/wizard-host-approvals.json`. Only the App Manager service account writes that file, and only for a
recipe its policy accepts (no risk, manager-managed mounts, or an owner approval); revoking an approval clears it.
A missing or unreadable file accepts nothing and an unknown Compose key is refused. Python and TypeScript share
test vectors for the token rules.

**App environment.** An app's `app.env` receives only an allowlist of public base keys (time zone, domains, ports,
paths, store ids), never a manager credential, including ones added later. It is written 0600 by temp file and
rename, owned by the manager. The app data widening for non-root app users excludes `app.env`, the app directory
itself and symlinks. `docker-compose` runs with a minimal environment, so a recipe cannot interpolate manager
credentials. On upgrade the backend removes lines whose value is exactly a manager credential from existing
`app.env` files and leaves every other byte alone. Credentials an app already read cannot be un-read; the owner
rotates them (database, queue, session signing).

## Owner approval

The App Manager, not the Agent Service, decides who the owner is. It accepts an owner request only from a root-owned
peer socket (tailscaled) carrying the node owner's `Tailscale-User-Login` (the strict store rule: a tagged node
approves nothing). The owner login is pinned at host-prep; Health warns if it changes.

Identity is not intent. The shell origin also serves apps and proxied agent responses, so script running there
sends the owner's real identity and an accepted `Origin`; a same-origin token would not help, because that script
can read it. So:

- **Risk-raising owner actions** (approving host access, `grants` grant, `network allow` / `network off`, developer
  mode on or a source change, installing a developer source, server access, importing a backup file) never run
  from the shell origin. They become an intent: stored by the App Manager, bound to the exact action, body and owner
  login, five minutes, single use. It executes only from a POST on the **approval origin**, a dedicated
  `tailscale serve` HTTPS port whose whole site is the App Manager's approval listener and nothing else. That POST
  must carry the approval origin exactly, `Sec-Fetch-Site: same-origin` and the intent digest shown on the
  confirmation page. Approval pages forbid framing, opener access and cross-origin reads.
- **Risk-reducing actions** (revoke server access, developer mode off, deny host access, revoke a grant, isolation on,
  release updates) stay one click on the shell origin, so the owner can always back out.
- **Fail closed.** Without a verified approval origin (`wam approval-origin enable`), risk-raising owner actions are
  refused with that setup command. The agent token never reaches any owner action.

Separately, the Agent Service proxy publishes only JSON (and SSE on the events route) from the agent gateway on the
owner origin, on every status, with a sandbox CSP; anything else becomes a 502 JSON error. This removes one
injection path; the approval origin is what makes approval safe against the rest.

## Server access (developer mode only)

Developers sometimes need their agent to work on the system itself. Inside developer mode (#97) the owner can
**Give the agent full server access**, confirmed on the approval origin. The `server-access` helper writes
`/etc/sudoers.d/91-wizard-agent-access` with an expiry (7 days by default, or until turned off), and a root timer
removes it. It is root and Wizard says so: a red Health row while on, every use in the sudo log, a checksum of
`/etc/sudoers.d` and the helpers at grant start and a Health warning if they changed afterwards. Turning developer
mode off removes the grant. It never changes the layout. The helper grants only while developer mode is on; there
is no automatic or migration grant. Migrating a box whose agent is in the docker group removes that membership and
leaves the agent with no sudo and no Docker immediately, including on resume; a grant left by an earlier candidate
is revoked on resume. A developer who needs access afterwards turns developer mode on and grants it explicitly.

People are never locked out: owners keep their own server login (SSH as root or their admin account).

## Conformance (every release, fresh and alongside)

From the agent's runtime: `id` shows no docker/sudo/wheel; `sudo -n true` fails; restricted-agent checks D1–D3
(no docker or containerd socket, no Docker API over TCP) pass; `docker run -v /:/host` and `tailscale down` fail;
a recipe with a host mount is refused until owner approval, including through the backend API directly; a forged
owner-proof header on the Approve route is refused; owner-origin HTML cannot spend an approval; app env files hold
no manager credential.
