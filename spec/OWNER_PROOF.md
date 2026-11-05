# Owner proof: passphrase-free owner access for app pages

Status: **proposed by Miguel, approved by James 5 Nov 2026** ([DECISIONS](../docs/DECISIONS.md) #106), amended by James the same day ([#107](../docs/DECISIONS.md): "the owner's device" is an enrolled Wizard device; host access is accepted only on one). Nothing here is deployed.
Draft implementation: wizard-app-manager (owner edge, key minting, routing), wizard-messenger (manifest + verifier).

## The problem

Messenger is the one app whose owner must never type a second password ("trusted Wizard means no passphrase box,
ever"). Today that works on exactly one box, through a private path built by hand:

```
phone ─▶ Tailscale Serve /messenger/ ─▶ unix:~/.wizard-os/messenger-owner/ingress.sock   (hand-built user unit)
            ─▶ owner_ingress.py: tailscaled peer check, owner login, strip headers, HMAC-sign
            ─▶ unix backend socket mounted into the Messenger container (hand-written user-config override)
```

Every other app page is a plain Serve route that `wam links` publishes to the app's loopback port. Because the
Messenger route is foreign to the App Manager, it has broken the same few ways again and again:

- `wam links` (or an older copy of it in the Builder bundle) saw the route as a conflict and moved the launcher to
  the raw `:9245` port, where every owner request is refused (`trusted_gateway_required`): 2 Nov and earlier.
- Serve routes drift per shell port (8444 vs 8796) because nobody publishes them together.
- Ingress releases (`waiting-*`, `backlog-*`, `activity-*`) are copied and repointed by hand.
- A generic header strip dropped `X-Messenger-CSRF` (every send failed); a Unix backlog of 5 turned the opening
  burst into 502s.
- Only Miguel's box has it, so no other owner can get passphrase-free Messenger.

## What the gateway actually is today (checked against main, 2 Nov 2026)

- **App pages:** `wizard-app-manager/wam/links.py` `_publish()` puts `/<app>/` on every shell port as a Serve
  handler straight to `http://127.0.0.1:<app port>` (`implicit_gateway`, `ensure`). No Wizard process sits between
  Serve and the app. `owner_fronted()` exists only to *leave alone* Messenger's hand-built Unix route.
- **Shell (`:8796`):** wizard-ux nginx serves the shell's files and passes `/wizard/*` to the Agent Service. It does
  not proxy app pages.
- **Agent Service:** resolves one principal per request (`server/principals.mjs`): `X-Wizard-Owner-Proof` (a static
  shared secret from a trusted front proxy), the Tailscale/Cloudflare access verifier (`server/tailnet-access.mjs`,
  trusted proxy peer = loopback or container gateway), agent bearer keys, else `box_only`. On alongside boxes
  (Miguel's) it runs with no proof and no access check, so "owner" means "any caller that reached it".
- **A precedent already in the App Manager:** `wam/store_install.py` serves the Store "Get" route behind Serve and
  accepts a request only when the local peer socket is root's (tailscaled), `Tailscale-User-Login` is the node
  owner, and `X-Forwarded-For` is not this box's own tailnet address (`from_box`).

So "move trusted owner into the gateway" means: **give the App Manager, which already owns app routing, a generic
owner edge** built from the proven Messenger ingress and the Store-install checks. Putting it in the Agent Service
was considered and rejected (see Alternatives).

## Design

### 1. The app declares it (wizard.md)

```yaml
owner_proof: hmac-v1            # shorthand, or:
owner_proof:
  scheme: hmac-v1
  wrap_key: true                # also mint an independent key the app may use to wrap data at rest
  activity: [/api/drafts]       # extra paths that mean "the owner has this app on screen"
  strip: [X-Messenger-Owner-Proof]   # app-specific legacy headers a browser must never send through
```

Optional and generic. An App Manager that does not know the key ignores it (the checker has no unknown-key rule),
and the app keeps its own sign-in. `wam check` validates it when present ("owner_proof valid").

### 2. The App Manager mints per-app keys

- Edge copy: `~/.wizard-os/owner-proof/<app>/edge.key`: 32 random bytes, host user, 0600, folder 0700.
- App copy: `~/.wizard-os/owner-proof/<app>/app/{proof.key,wrap.key}`, owned by the app's container user (written
  by a throwaway `--network none` container of the app's own image, the same way `alongside.adopt_media` works on
  rootless Docker). The wrap key exists only in the app copy, is created once and **never replaced**.
- Both live outside the app's data volume, so an app-data backup alone never carries them.
- Injected into the app's main service by a block in the stock Runtipi user-config override marked
  `x-wizard-owner-proof` (same pattern as `x-wizard-networks`): a read-only mount at `/run/wizard-owner` and
  `WIZARD_OWNER_PROOF_KEY_FILE`, `WIZARD_OWNER_WRAP_KEY_FILE`, `WIZARD_OWNER_PROOF_APP`. Only that block is ever
  rewritten or removed. Hand-written trusted-owner lines must be migrated first (the writer refuses to merge them).
- Keys are per app: a leaked Messenger key cannot sign for another app (unlike one shared box-wide proof).

### 3. The owner edge signs, only for the authenticated owner

One App Manager process (`wam owner-edge serve`, user unit `wizard-owner-edge.service`) binds
`~/.wizard-os/owner-edge/<app>.sock` (0600, folder 0700) for each owner-proof app, and `wam links` publishes the app's
Wizard path on every shell port as `unix:<that socket>` instead of the raw port. This rollout is off by default:
`app-manager.json` must explicitly set `owner_proof_enabled: true`. **Follow-up 2 is a hard precondition for enabling
the edge**, including any migration or lifecycle hook. While off, provisioning and `owner-edge serve` refuse,
registry output omits the declaration, and routing is unchanged even if a recipe declares `owner_proof` or an old
edge socket remains. When enabled, per request, in order:

1. **Kernel peer credentials:** the connecting process is tailscaled (uid/gid 0 and the PID systemd reports for
   `tailscaled.service`). Anything else gets 403 before a byte is read.
2. **Serve identity:** `Tailscale-User-Login` (exactly one) is the box owner: the login pinned in
   `~/.wizard-os/owner-edge.json`, else the node's own user; a tagged node has no owner unless pinned.
3. **Owner's device, not the box, not the owner's other servers** (amended, #107). `X-Forwarded-For` must not be this
   node's own tailnet address or loopback: Serve labels the node's own address with the node owner's login, so every
   program on the box would otherwise pass as the owner (same rule as `store_install.from_box`). Serve *sets* these
   headers, never appends (tailscale 1.104.2 `ipn/ipnlocal/serve.go` `addProxyForwardedHeaders`,
   `addTailscaleIdentityHeaders`). And the caller must be a device **enrolled in Wizard**, because `Tailscale-User-Login`
   is the same on every untagged node the owner signed in to, including their other servers, where agents run:
   - The edge resolves the caller itself, not from a header: `tailscale whois --json <X-Forwarded-For>` (LocalAPI
     whois) returns the node's stable ID, tags, hostname, OS and owner login. One literal address is required; a list,
     a port or a name is refused.
   - The node must be untagged, owned by the asserted login, and **one of the owner's devices in the existing Devices
     record** (`~/.wizard-os/devices.json`, [DEVICES.md](DEVICES.md); written by "Connect another device" / Machines
     and `wizard-devices`). No second list: the rule is wizard-ux `peerGroup` over that record. A node is the owner's
     when the record's `groups` says `human` under the name the control plane gave it (whois `Node.Name`, never
     `Hostinfo.Hostname`; a node's self-reported hostname can only take a mark away, never grant one; a name freed by
     a deleted node can be inherited by a new node until follow-up 2), or by default when it is an iOS, iPadOS or Android device
     (what "Connect another device" adds). A Mac, laptop or server must be marked `human` first: a Mac that runs
     agents is common, so macOS is not assumed to be the owner (wizard-ux's display default is not used for this gate).
     Anything the Wizard works on (`this`, `devices[]`, any group `agent`) and anything marked `client` or `other` is
     never the owner, whatever else is written.
   - **Fail closed.** If tailscaled cannot answer, the address is unknown, the node has no stable ID, or the record is
     unreadable, the request is refused with `owner_device_unverified`; a resolved caller that is not enrolled gets
     `owner_device_required`. Neither forwards a byte. Lookups are cached for 10 s, keyed on the address and the record's modification time, so a revoked mark can lag by
     at most 10 s.
   - Known limit, deliberately recorded: an iOS/iPadOS/Android node counts by its reported `Hostinfo.OS` (that is
     what "Connect another device" itself keys on; no per-phone record exists), and the OS is self-reported by the
     node, so anyone who can register a node as the owner could make it claim `android`. Stable-ID enrollment at the
     owner-authenticated connect step (follow-up 2) closes this; until then the enrollment check is not a boundary
     against such a caller, whether or not they have root on an existing server.
   - Known limit, deliberately recorded: the record names nodes (tailnet names), not stable IDs, and the agent can
     edit it (`wizard-devices group`). Closing that needs the stable ID stored at the owner-authenticated connect step
     and the record made owner-writable only; see Follow-ups.
4. **Host and origin:** `Host: localhost` with `X-Forwarded-Host` = this node's tailnet name; writes need
   `Origin` = that exact origin; `Sec-Fetch-Site` only `same-origin`/`none`.
5. **Never for a bearer:** any `Authorization` header is refused. Agents reach apps through the Agent Service's MCP
   gateway with their own per-app key; they never come through here and are never signed for.
6. **Strip, then sign:** hop-by-hop, `tailscale-*`, `x-forwarded-*`, `x-wizard-*`, `cf-access-*`, `forwarded`,
   `x-real-ip` and the app's `strip` list are dropped. App headers (cookies, `X-Messenger-CSRF`) pass. Then
   `X-Wizard-App-Owner-Proof` is added and the request goes to `127.0.0.1:<app port>`.

Signature (pinned test vector in both repos):

```
value   = <unix seconds> "." <48 hex nonce> "." hex(HMAC-SHA256(key, message))
message = "wizard-app-owner-v1\n" <app id> "\n" <seconds> "\n" <nonce> "\n" <METHOD> "\n" <target as the app receives it>
```

The app accepts exactly one proof within ±30 s, refuses a nonce it has seen in the last 61 s, compares in constant
time, and never treats a proof as authority for a bearer request. Messenger's legacy
`X-Messenger-Owner-Proof` / `wizard-messenger-owner-v1` stays accepted for boxes still on the old ingress; a request
carrying both kinds is refused.

### 4. Generic restart tolerance and owner activity

- Connection refused while the app restarts is retried for 5 s. A page load that still fails gets a 503
  "<App> is restarting" page (`X-Wizard-Waiting: 1`) that reopens by itself; API calls get JSON 502 so the app's
  own retry logic runs. Responses stream (long polls, ranges, event streams); nothing is buffered whole.
- Socket backlog 256 (the opening burst of an app must queue, not EAGAIN).
- `~/.wizard-os/owner-activity/<app>` is touched (at most every 15 s) on page loads, writes and the app's
  `activity` paths. Deploy gates and, later, nightly App Manager updates read it to wait until the owner is idle.

### 5. Routing never downgrades

For an owner-proof app, `wam links` publishes `unix:<edge socket>` or nothing. If the edge is not running it
reports `owner edge not running` and keeps the last known Wizard path; it never falls back to the raw port (where
the app would refuse every owner request). An existing different handler (the hand-built ingress) is still left
alone, so migration is an explicit step, not a side effect of a refresh.

## Host access is an owner-device action (amended, #107)

The intended boundary is that an app asking to escape isolation is accepted by the owner on an enrolled device,
not by an agent. **The implementation is staged, not that completed boundary.** Host-access grants are off by default:
the host file `app-manager.json` must explicitly set `owner_host_access_grants: true`. **Follow-ups 2, 5, 6, 7, 8, 9
and 10 are all hard preconditions for enabling grants.** Follow-up 7 cannot wait: the checked recipe must be the
deployed artifact, or an agent can replace it after consent.

**Switch off means existing main behaviour, not deny-all.** The listener answers `403 grants_off` and creates no key.
Install, update, `wam network allow`, network planning and start-time policy retain the existing host-access detector,
owner `--allow-host-access` CLI path and stored allowances. No existing recipe becomes newly blocked; in particular
`wizard-connection-router` keeps its `${ROOT_FOLDER_HOST}/repos` and `/app-data/wizard-os` mounts. This deliberately
does not secure acceptance while off. Nothing is provisioned, migrated or restarted by merging this change.

The remaining gate and audit descriptions in this section apply **only with grants enabled**, subject to the honest
limits below. Symlinks in `${APP_DATA_DIR}` or `media/`, unchecked stored update values (including a value pointing
at `~/.ssh`), the `media/` and read-only `.wizard-source/` exemptions, unauthenticated legacy/forged start-time
allowances and the check-to-deploy race work **regardless of the switch**; turning it on does not close those paths.

- **What counts as host access when enabled** (`wam/network.py owner_host_access()`, used by install, update and
  the grant listener; `host_access()` remains the unchanged main detector for network planning/start policy):
  `privileged`; the Docker, containerd or Podman socket; a bind mount outside the app (absolute, `~`, `..`, or a
  variable that is not one Runtipi sets: `${APP_DATA_DIR}`, under `${ROOT_FOLDER_HOST}` only `media/`, and, read-only
  only, `${APP_SOURCE_DIR}` and `app-data/.wizard-source/` (a writable source folder lets an app rewrite its own recipe
  or the source Wizard builds from); an app's own release folder read-only; `/etc/localtime` and
  `/etc/timezone` read-only). Every other path under `${ROOT_FOLDER_HOST}` (the root, `user-config`, `apps`, `state`,
  `traefik`, another app's `app-data`) is host access, because from there an app can rewrite the network policy file or
  a compose override. Also: named volumes bound to a host path; volumes the app does not own (`external`, fixed `name`;
  the Claude login volume shared by design is the one named exception); `volumes_from`; top-level secrets/configs and
  `env_file` read from outside the app; `build` contexts outside the app (Wizard's pinned source folder excepted);
  `network_mode: host`; `pid`/`ipc`/`userns_mode`/`uts`/`cgroup` set to `host` or to another container; host
  `devices`, `device_cgroup_rules`, GPU reservations; any `security_opt` but `no-new-privileges`; `cap_add` beyond
  Docker's default set; networks the app does not own; and anything that cannot be checked: a variable in
  `privileged`, a namespace mode, `cap_add` or a bind source, `include`, `extends`.
- **Values the installer is given count.** The check runs on the recipe with the values given to the install
  (`--set NAME=...`, form fields) filled in, and the grant is bound to the hash of that filled-in recipe and to concrete
  risk items (each names its path, socket, capability or network), compared exactly, so an optional media folder pointed
  at `~/.ssh` is host access. The variables Runtipi sets cannot be overridden by a given value. *Not covered:* values
  stored by an earlier install and used by an update (follow-up 8).
- **Gate.** `--allow-host-access` (install and `wam app update`) and `wam network allow` do not accept anything by
  themselves. They proceed only with a **grant**: a record MACed with a host-only key (`owner-proof/host-access.key`,
  0600, not mounted into any container the Wizard starts). A grant is bound to one app, one purpose (install, update
  or allow), the risk list and the hash of the recipe as the **listener computed them itself** from the current store
  copy (the client never supplies a risk list), valid 10 minutes, never blank. It is claimed by an atomic rename to a
  name unique to the caller, checked, and deleted whatever the result, so exactly one caller can use it; a check that
  fails on the wrong purpose or recipe is done before the claim and does not use it up. Without a grant the command
  exits with a refusal that names the owner action. The in-process callers (`install_with_retry`, bootstrap,
  `app_updates`, the Agent Service's runtime driver, `app_rename`) share the same functions, so they are gated too.
  An allowance already on file never opens an install and never covers what an update adds: new access always needs
  a new grant.
- **Who writes a grant.** Only the App Manager's owner listener, `POST /_host-access/<app>` on the existing Store
  listener (a loopback TCP port; the peer's uid is read from the kernel's socket table and must be root, i.e.
  tailscaled; this is weaker than the edge's Unix-socket peer-PID check and is the existing Store model); owner login; not this box; the shell's origin;
  **and** the enrollment check of step 3 on a single `X-Forwarded-For`; **and** no `Authorization` header. The listener
  is HTTP/1.0, one request per connection, so a refused body cannot be read as a second request.
- **Paths audited.** Agent container `wam` CLI (install, `app update`, `network allow`): gated in `wam`. Agent Service
  runtime driver and Builder (`cli.install` / `cli.app_update` in-process): gated, they never pass the flag. App
  Manager HTTP: `wam serve` (`:7790`, bearer) has no host-access endpoint; the Store listener's install/update
  endpoints take no host-access flag. Nightly `app-updates --apply`, `quick_update` and `store_selection` update
  without the flag, so an update that adds host access is refused and reported.

### Honest limits (this change does not close these)

- **The gate lives in `wam`.** It stops an agent that goes through `wam` or the Agent Service. It does not stop code
  that can reach what `wam` itself drives: the Docker socket, the Runtipi API token, a write to the Runtipi folders or
  `user-config`, or running as the host user. The agent container must not have any of those, and that is a **required
  invariant to verify** (the agent apps' recipes mount only their own agent folder today; no test enforces it for
  the container the Builder or an agent can start). Host access also means a root-capable app can do all of the above.
- **A grant can be obtained by an agent that controls an owner-login node.** The Devices record is agent-writable
  (`wizard-devices group`) and the edge matches names; an agent that marks its other server `human` can send the
  grant request itself with a forged `Origin` (curl is not a browser). Follow-up 2 is therefore a **precondition for
  turning grants on**, not a nice-to-have. Phones count by self-reported `Hostinfo.OS` with no record entry
  (what "Connect another device" does), so anything that can register a node as the owner and claim `android` passes
  until stable IDs are recorded.
- **Symlinks in bind sources.** Sources are judged by their text. Docker follows a symlink inside an allowed source
  (for example `${APP_DATA_DIR}/data/x -> /` made by an earlier container of the same app, or inside the shared
  `media/` folder) when it creates the container, so a text-clean recipe can still mount the host. Not stopped.
  Closing it needs a host-side check before every start that resolves each bind source without following symlinks
  and beneath the app's folder (follow-up 10).
- **Agent content on the shell origin** could make the owner's own browser send the request (follow-up 6).
- **A recipe changed between the check and Runtipi's deploy** is not detected (follow-up 7).
- **Allowance lists.** `app-manager.json` `host_access_allowed` (mirrored to `user-config/wizard-app-networks.json`
  for start-time enforcement) is a plain file with no MAC. The audited enabled-gate paths require a grant to write
  it, but switch-off commands retain the main writer. Allowances written
  before this change are indistinguishable from forged ones and stay honoured at start-time enforcement with either
  switch setting so running apps do not stop (follow-up 5).
- **Folder sharing.** `media/` and `.wizard-source/` mounts, which Wizard's own apps use, are not counted (counting
  them would force an owner grant on every update of those apps). Follow-up 8.
- **Host user.** A process running as the host user can read the key and write a grant, exactly as it can read the
  edge key (Threat model: same-uid host process). This is not a boundary against it.

## Follow-ups (recorded, not part of this change)

1. **Agent Service tailnet verifier has the same weakness.** `wizard-agent-service/server/tailnet-access.mjs` authorizes
   any request whose `Tailscale-User-Login` is the owner, from any untagged node of the owner, including their other
   servers. It should resolve the caller (whois) and require an enrolled device like step 3. Not changed here.
2. **Make the enrollment record trustworthy (hard precondition for edge and grants).** Store the node's stable ID when "Connect
   another device" completes (owner-authenticated), match on stable ID rather than name or reported OS, make
   `groups: human` writable only from an owner request (not by `wizard-devices` run by an agent), and remove a mark
   when its node is deleted so a later node with the same name does not inherit it.
3. **UI:** the "Allow host access" action in Store / Connections on the owner's device (calls `/_host-access/<app>`).
4. **Key lifecycle** (provision on install/update) stays off until the rollout order below reaches it.
5. **Authenticate allowances (hard precondition for grants).** MAC each allowance with the host-access key over (app, risk digest, recipe hash);
   verify on every read including start-time enforcement; legacy entries become "unverified" until the owner
   re-accepts them on a device; clear on uninstall and on failed install. Needs a change to the Runtipi fork's
   `wizard-networks.ts`, so it is not part of this inert change.
6. **Grant UI hardening (hard precondition for grants):** serve "Allow host access" from an origin that renders no agent
   content, with a WebAuthn user-verification step bound to (app, risks, recipe hash); today a grant proves the owner's
   enrolled device, not the tap.
7. **Deployed-artifact check (hard precondition for grants):** verify at apply time that what Runtipi deploys hashes to the grant's recipe hash
   (today the check is on the store copy read just before the apply), and render `include`/`extends`/interpolation
   rather than refusing them.
8. **Folder sharing and stored values under the same gate (hard precondition for grants):** treat a form-chosen or `${ROOT_FOLDER_HOST}` media/source
   mount as an owner action, and apply the given-values check to values an earlier install stored.
9. **Agent container invariant test (hard precondition for grants):** assert that no container the Builder or an agent can start has the Docker
   socket, the Runtipi token or write access to the Runtipi folders.
10. **Symlink-safe bind sources (hard precondition for grants):** resolve with `openat2(RESOLVE_NO_SYMLINKS | RESOLVE_BENEATH)` (or refuse symlinks)
    in the start-time enforcement in the Runtipi fork, for `APP_DATA_DIR`, `media/` and the source folders.

## Threat model

| Caller | What stops it |
|---|---|
| Browser sends its own `X-Wizard-App-Owner-Proof` / `X-Messenger-Owner-Proof` / `Tailscale-User-Login` | Serve overwrites identity headers; the edge drops every proof/identity header before signing; the app requires a valid HMAC with a fresh nonce |
| Replay of a captured proof | 30 s window + per-app nonce cache; proof bound to method, target and app id |
| Proof for app A replayed at app B | Separate keys per app and the app id inside the signed message |
| Agent or any bearer caller (MCP gateway, agent keys) | Edge refuses `Authorization`; agents never reach the edge; the app keeps every bearer on its agent policy |
| Another tailnet user (shared device, invited user) | `Tailscale-User-Login` is not the owner → 403, nothing forwarded |
| Tagged tailnet node / Funnel | Serve sets no user identity for them → 403 |
| Owner's own phone/laptop (enrolled in Wizard) | Allowed: that is the trust decision (enrolled owner device = owner) |
| The owner's other untagged server, where agents run, signed in as the owner | Conditional on trusted stable-ID enrollment (follow-up 2, required before edge enablement): whois resolves a node not enrolled as an owner device → `owner_device_required`. Today's name/OS check can be defeated as below |
| Tailscale cannot answer, address unknown, record unreadable | Fail closed → `owner_device_unverified` |
| Agent edits the Devices record to mark its own server `human` | **Not stopped yet** (follow-up 2). The record is agent-writable today; the edge matches names, not stable IDs. It also lets that server request a host-access grant, so follow-up 2 is a hard precondition for enabling either edge or grants |
| An owner-login node that reports a mobile OS (anyone who can register a node as the owner, not only root on a server) | **Not stopped yet** (follow-up 2): phones count by reported OS with no record entry |
| Agent accepts host access through `wam` with grants off | **Not stopped**: unchanged main detector, CLI flag and existing allowances. Off is compatibility, not a security boundary |
| Agent accepts detected host access through `wam` with grants on (`--allow-host-access`, `wam network allow`, Builder or Agent Service install/update) | The audited gate paths require a single-use grant. **Not a complete boundary**: direct Docker/Runtipi access, agent-controlled owner-login nodes, shell-origin content, symlinks, stored values, exempt folders, legacy/forged allowances and check-to-deploy races remain; follow-ups 2, 5, 6, 7, 8, 9, 10 must be completed before enablement |
| Host access through symlinks in app data/media, stored update values pointing at `~/.ssh`, or exempt media/source mounts | **Not stopped with either switch setting** (follow-ups 8, 10); the enabled detector checks recipe text and given install values, not these runtime paths |
| Legacy or forged unauthenticated host-access allowance at start time | **Not stopped with either switch setting**; indistinguishable and still honoured (follow-up 5) |
| Recipe replaced between check and deployment | **Not stopped with either switch setting** (follow-up 7) |
| A program on the box calling the tailnet URL | `X-Forwarded-For` is the node's own address → 403 (closes the gap Miguel's ingress has today) |
| A program on the box connecting to the edge socket | Socket 0600 in a 0700 folder, and the peer must be tailscaled's PID |
| A program on the box calling the app port directly | No valid proof without the key; app port alone never grants owner |
| Same-uid host process (host Hermes on alongside boxes) | **Not stopped**, same as today: it can read keys in the owner's home. Only a separate Unix user for the agent closes this (PHONE_SETUP rule 4). Mode 0600 is not a boundary against the same user |
| Leaked app-data backup | Keys and wrap key live outside the data volume |

## Backward compatibility

| Box | Result |
|---|---|
| Old App Manager, new Messenger | `owner_proof` ignored, no keys injected → passphrase sign-in, as today on every box but Miguel's |
| New App Manager, old Messenger (no `owner_proof`) | Nothing changes |
| New App Manager, new Messenger, edge not running | Link keeps its previous path, never the raw port; the lifecycle hook (step 5) injects keys only once the edge is live, so the app stays on passphrase sign-in |
| Miguel's box before migration | Hand-written `MESSENGER_OWNER_*` lines keep working (legacy env + header accepted); the override writer refuses to mix |
| Explicit `MESSENGER_TRUST_WIZARD_OWNER=0` | Owner opt-out wins over provisioned keys |
| Non-Linux / no systemd (Mac VM host, containers without tailscaled) | Peer check fails closed → no edge → passphrase sign-in |

## Tests

Added in the draft PRs:
- wizard-app-manager `tests/test_owner_edge.py` (real edge on a Unix socket in front of a real loopback backend,
  requests shaped like Serve): signed for exactly the forwarded target; refused for the owner's other (unenrolled)
  server, an unresolvable caller, an unreadable record; client proofs and identity headers dropped,
  app headers kept; refused for other users, tagged/no identity, this box's own address, loopback, missing source,
  wrong host, non-Serve Host, bearer, duplicated identity, non-tailscaled peer, cross-origin writes; body forwarding;
  waiting page vs JSON 502; streaming; activity only for page loads/writes/declared paths; socket modes; node-owner
  vs tagged vs pinned identity.
- wizard-app-manager `tests/test_owner_proof.py`: manifest parsing and checker rule, sign/verify binding and window,
  pinned vector, edge key create/adopt/refuse, the throwaway-container key copy (networkless, wrap key kept),
  override block add/remove exactly beside `x-wizard-networks`, refusal to merge hand-written lines, links publishes
  `unix:<edge>` and never the raw port without the edge.
- wizard-messenger `tests/test_trusted_owner.py`: the whole existing trusted-owner suite re-run with platform keys
  and platform proofs, plus app-id binding, replay, legacy-domain-under-new-header refusal, both-kinds refusal,
  explicit opt-out, unchanged legacy environment, the same pinned vector.

Added with the amendments (#107): wizard-app-manager `tests/test_owner_devices.py` (the enrollment rule over a
synthetic tailnet and record, fail-closed lookups, the edge refusing the owner's other server),
`tests/test_owner_proof_keys.py` (concurrent first provisions publish exactly one key; the key cache re-checks
permissions) and `tests/test_host_access_gate.py` (with grants enabled, synthetic examples of the detected risks are
refused through the listed command/in-process entry points without a grant; grants are single-use, expiring, app-,
purpose-, risk- and recipe-bound; synthetic listener tests exercise the current enrollment rule, not trustworthy
enrollment). These do not prove an agent cannot obtain host access by the honest-limit paths. `test_owner_proof_off.py`
compares off-mode install/update results, output and written bytes with frozen main functions, including the router's
wide mounts and the existing flag/allowance path; the original network tests remain unchanged and run with switches off.

Still to add before rollout: lifecycle hook test (install/update calls `owner-proof provision` and `links`), a
two-box Serve rehearsal (a second tailnet device as owner, a second user, and a box-local `curl` to the tailnet URL),
restart-under-load browser test through the edge (`trusted_restart_browser.cjs` pointed at the edge), and
`live_smoke.cjs` after migration.

## Rollout order

1. James approves this decision (#106) and the header/domain names.
2. Merge Messenger verifier + manifest (inert everywhere: no box injects keys yet). Ship a Store release.
3. Merge the App Manager part behind `owner_proof_enabled: false` and `owner_host_access_grants: false` (both default
   to off when absent). **Before enabling the edge or migrating/provisioning, complete follow-up 2. Before enabling
   grants, complete follow-ups 2, 5, 6, 7, 8, 9 and 10; none may be waived by a green inert-code test run.** Nothing provisions
   keys automatically yet; the installer may install the user unit, which serves nothing until an app has keys.
4. Migrate Miguel's box (below), watch for a week with the deploy idle gate reading the new activity file.
5. Add the lifecycle hook (install/update of an `owner_proof` app runs provision, then links, and injects keys only
   once the edge socket is live); release; other owners get passphrase-free Messenger on the next App Manager update
   (their first open after the update unlocks once with the passphrase, then remembers).

### Migrating Miguel's box (no logout)

Done while he is idle (deploy gate), with backups of the Serve JSON, `links.json`, `apps.json` and the user-config
override:

1. `wam owner-proof provision messenger --adopt-proof ~/.wizard-os/messenger-owner/proof --adopt-wrap
   ~/.wizard-os/messenger-owner/app-secrets/messenger-owner-wrap` (same key bytes, so the remembered unlock still
   opens).
2. Replace the hand-written `MESSENGER_TRUST_WIZARD_OWNER` / `MESSENGER_OWNER_*` / `MESSENGER_OWNER_SOCKET` lines and
   the two mounts in the override with the managed block (the writer refuses until they are gone); keep
   `MESSENGER_GATEWAY_KEY_FILE`, attachments and the networks block.
3. Start `wizard-owner-edge.service`; restart Messenger through `scripts/runtipi_app.py`.
4. Point `/messenger/` on 8444 and 8796 at `unix:~/.wizard-os/owner-edge/messenger.sock`; `wam links --json`
   shows `owner_proof: edge` and no Messenger error.
5. Verify: `api/view/trusted-owner` through each port returns `enabled:true`; the read-only live smoke on phone and
   desktop; a box-local `curl` to the tailnet URL now gets 403 `owner_device_required`.
6. Stop and disable `messenger-owner-ingress.service`; keep its release folder for rollback; update the deploy idle
   gate to read `~/.wizard-os/owner-activity/messenger`.

Rollback (minutes): restore the saved override and Serve JSON (the old ingress socket and keys are untouched), start
`messenger-owner-ingress.service`, restart Messenger through the gated script, run `wam links --json`.

## Alternatives considered

- **Sign in the Agent Service.** Would reuse its principal resolver, but the Agent Service is not in the app path on
  any box today, Node has no `SO_PEERCRED` (its loopback Serve listener cannot tell tailscaled from a box-local
  process), it restarts often and would take every owner-proof app with it, and on alongside boxes it runs in
  `box_only` mode, where "owner" is not authenticated at all. Its shared `X-Wizard-Owner-Proof` is one static secret
  for the whole box; owner proof here is per app, per request.
- **Keep the per-box ingress and teach wam about it.** That is what `owner_fronted()` does today; it keeps the hand
  maintenance, the per-port drift and the single-box limitation.
- **Loopback TCP edge with a root-peer check** (Store-install style) instead of Unix sockets: avoids Serve's
  operator privilege for `unix:` handlers, but only proves "some root process", not tailscaled's PID. Kept as a
  fallback option if Unix handlers prove unavailable on fresh boxes.

## Open questions for James

1. Header and domain names: `X-Wizard-App-Owner-Proof` / `wizard-app-owner-v1` (kept distinct from the Agent
   Service's static `X-Wizard-Owner-Proof`).
2. Should the edge also front the Agent Service's tailnet listener later (one owner front door), or stay app-only?
3. Owner login source of truth: the pinned file, Agent Service settings `access.tailscale.owner_logins`, or the node
   owner (current draft: pinned file, else node owner).
4. Should nightly App Manager updates wait on `owner-activity/<app>` for every app, not only Messenger deploys?

## Effort and risk

About 2–3 days to finish: the lifecycle hook and installer unit (half a day), the two-box Serve rehearsal and
browser restart test (a day), Miguel's migration with a watched week. Main risk is the routing switch on a live box;
it is reversible in minutes because the old ingress, its keys and its socket stay in place until the new path has
run for a week. Security risk is lower than today's: same checks plus the box-local caller fix, and per-app keys.
