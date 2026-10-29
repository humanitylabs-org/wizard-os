# App-to-app permissions, v0.2

Status: **principle approved by James, 21 Oct 2026** ([DECISIONS](../docs/DECISIONS.md) #76). Mechanism (networks, per-grant key, rollout) from Miguel's draft ([PR #6](https://github.com/humanitylabs-org/wizard-os/pull/6)); the App Manager implements it ([wizard-app-manager#8](https://github.com/humanitylabs-org/wizard-app-manager/pull/8), draft). Satisfies the #32 term "permissions get a spec before networking code lands".

**The rule:** one Wizard app may call another Wizard app only along a grant the owner approved. No grant, no call.

Today every Wizard app can reach every other app. Runtipi puts every app's main service on one shared Docker network (`runtipi_tipi_main_network`), so any container can call `http://<other-app>:<port>` and nobody records who called.

## What this spec covers, and what it leaves to other specs

| Caller → callee | Who decides | Where it's enforced | Spec |
|---|---|---|---|
| **App → app** (Wisdom → Connection Router, Router → Claude app, a recorder → Transcriber) | Owner-approved grants (this spec) | Per-app Docker networks + per-grant key at the provider | this file |
| Agent → app (Hermes or a container agent calling an app's tools) | The owner's tick boxes per agent, chosen at install (#58) | The Agent Service's `wizard` MCP gateway, one key per agent | [AGENTS.md](AGENTS.md) §5, [AGENT_BRIDGE.md](AGENT_BRIDGE.md) |
| Agent → another agent's data | Agent-data grants, default none (#46); private agents can never be a source (#59) | Agent History / Agent Service | [AGENT_STATE.md](AGENT_STATE.md) §4 |
| Where an app's work goes | App → agent binding (#60) | Agent Service delivery endpoint | [AGENTS.md](AGENTS.md) §7 |

This spec adds **no agent defaults**. Draft v0.1 gave every agent a grant to every app at install; #58 replaced that, and it does not come back here. Agents never call apps directly: they go through the gateway, and the gateway serves each agent only the apps ticked for it.

## Two graphs

| Graph | Question | Source | Stored? |
|---|---|---|---|
| **Compatibility** | Could A use B? | Computed from `wizard.md`: A's `uses:` names B's `id` or a slot in B's `provides:`; A's `requires.models` / `requires.services` make it compatible with the Connection Router. | No. Shown on the Apps screen and in the index. |
| **Permission** | May A call B on this box? | Grants the owner approved. | Yes, by the App Manager. Enforced. |

A grant is only offered along a compatibility edge. Compatibility never opens a connection by itself.

## Grants

A grant is one direction: **consumer app → provider**. The consumer may open connections to the provider, never the reverse.

- `to` is an app id (`transcriber`) or a slot (`slot:transcription`, `slot:connection-router`). A slot grant covers whichever installed app holds that slot, so swapping the app in a slot keeps the grant. The owner narrows it by replacing it with a direct app grant.
- **Proposed at install, shown ticked on the install sheet** ("Wisdom will be able to use: Connection Router"):
  1. one grant per `uses:` entry (the app id, or the slot when no installed app has that id);
  2. `slot:connection-router` when the app declares `requires.models` or `requires.services` ([CONNECTION_ROUTER.md](CONNECTION_ROUTER.md));
  3. system apps that relay for others get their relay grants from their own `uses:` (the Router → each `ai-connection` app it routes to).
  Nothing else is proposed. An app that wants more is granted by the owner by hand.
- The owner can untick a proposal at install or revoke any grant later. A refused or revoked proposal is remembered in `denied` and not proposed again.
- An app never needs a grant to itself. Uninstalling an app removes its grants as consumer and as provider; reinstalling proposes them again unless they are in `denied`.
- **Grants carry no agent authority.** A grant lets app A call app B's own API. It never lets A act as an agent, reach the gateway, read agent data, or read a private agent (#59). An app bound to a private agent (#60) delivers through the Agent Service endpoint, not through a grant to the agent.

## Share grants

A `share` grant lets a consumer mount a folder a provider exports ([WIZARD_MD.md](WIZARD_MD.md#shared-folders)): `{"kind": "share", "from": "hermes-agent", "to": "wizard-claude", "share": "claude-login", "reason": "mounts", "approved": "install", "created_at": …}`. It is proposed at install for each `mounts:` entry whose provider is installed (and again when the provider is installed later), shown on the install sheet as "Hermes Agent will be able to use: Claude sign-in", and revocable like any grant. The App Manager adds the bind mount when it compiles the consumer and restarts the consumer when a share grant is added or revoked. A share grant carries no network access and no key; it is only the mount.

## Where grants live (no database migration)

The App Manager writes one JSON file, `<runtipi data dir>/state/wizard-grants.json` (e.g. `~/runtipi/state/wizard-grants.json`). Apps never see it. Stock Runtipi ignores it. Atomic writes (temp + rename). No keys in this file.

```json
{
  "schema": 1,
  "updated_at": 1792560000,
  "seeded": ["wisdom", "wizard-connection-router", "wizard-claude"],
  "grants": [
    {"kind": "app", "from": "wisdom", "to": "slot:connection-router", "reason": "requires", "approved": "install", "created_at": 1792560000},
    {"kind": "app", "from": "wizard-connection-router", "to": "wizard-claude", "reason": "uses", "approved": "install", "created_at": 1792560000}
  ],
  "denied": [{"from": "wisdom", "to": "transcriber"}]
}
```

- `kind`: `app` or `share` here. `agent-data` grants (AGENT_STATE #46) share the file so one screen shows every permission on the box; their rules stay in AGENT_STATE.md.
- `reason`: `uses` | `requires` | `mounts` | `owner` (added by hand). `approved`: `install` (accepted on the install sheet) | `owner` (changed later).
- `seeded`: apps whose proposals were already made, so a restart doesn't re-add revoked grants.
- **Mirrored into `apps.json`** as top-level `grants` (same objects, no keys) so the Agent Service and the shell can show them ([APPS_JSON.md](APPS_JSON.md)).
- Agent → app ticks stay in each `agent.json` (`permissions.wizard_apps`, AGENTS.md). The Apps screen may show them beside app grants, labelled as agents; they are not written here.

## Enforcement layer 1: Docker networks

A Wizard app's main service (`is_main`) and any `add_to_main_network` service **leave** the shared main network. One
network per grant replaces it. This is the form Miguel approved on 27 Oct 2026, implemented in
[wizard-app-manager#271](https://github.com/humanitylabs-org/wizard-app-manager/pull/271). A network per provider
would let two consumers of the same provider reach each other.

| Network | Members | Internal |
|---|---|---|
| `wizard-app-<id>` | that app's services only (its internet access and published `127.0.0.1` port) | no |
| `wizard-link-<consumer>--<provider>` | the consumer's services + the provider's main service, aliased `<provider id>` so `http://wizard-claude:8080` resolves as before | yes |
| `wizard-gw-<id>`, `wizard-core` | fresh boxes only: the app + the shell, Agent Service and agent (the gateway runs in containers there) | yes |
| `<app>_<store>_network` | unchanged | as Runtipi makes it |

- **Persistence.** The App Manager writes the topology into each app's stock Runtipi user-config compose override
  (a block marked `x-wizard-networks`), so every Runtipi start, restart, update and reboot keeps it. No timer.
- **Reconcile.** `wam network reconcile` runs after every install (planned before the first start), uninstall,
  update and installer run. It creates the networks and writes the blocks. It moves running containers live:
  connect first, then leave the shared network. Then it removes orphaned networks. Undeclared pairs share no network.
- **The gateway.**
  - Alongside boxes run the gateway on the host network. It reaches apps on their published loopback port and joins
    no app network.
  - Fresh boxes: the gateway containers join each app's `wizard-gw-<id>`.
- **Host access.** `wam install` refuses a recipe with `network_mode: host`, `privileged` or the container runtime
  socket unless the owner passes `--allow-host-access`.
- **Runtipi's own reach.** If an owner exposes a Wizard app through Traefik, that main service stays on the main
  network too and also gets its declared links. The Connections view warns that every app can reach it.
- Apps from other Runtipi stores stay on the main network and can no longer reach isolated Wizard apps.
- **Limits.**
  - A link is two-way at the network level: the provider can also open connections to the consumer.
  - Host processes (the Agent Service, a host Hermes) reach every app on its loopback port. Layer 2 covers them.
- **The Connections view and `wam connections`** show each app's declared connections and the gateway path. They
  include a live check of Docker membership against the declarations.

## Enforcement layer 2: per-grant key

The network says "this container may connect"; the key says "this caller is that app". The key works on stock Runtipi too.

- On each grant the App Manager mints a random 32-byte key and writes one file per app, `<app-data>/<id>/wizard/grants.json`, mounted read-only into the app; `WIZARD_GRANTS_FILE` names the path inside the container:
  `{"outgoing": {"slot:connection-router": "<key>"}, "incoming": [{"from": "wisdom", "sha256": "<hex>"}], "provider_endpoints": {"wizard-claude": "http://wizard-claude:8080"}, "enforce": true}`
  - `outgoing`: keys keyed by the grant's `to` (app id or `slot:<name>`).
  - `incoming`: SHA-256 of each key a caller may present, and who it belongs to. The provider never holds callers' keys.
  - `provider_endpoints` (optional): where each granted provider answers, so a consumer never guesses addresses.
- The consumer sends `X-Wizard-Grant: <key>` on every call to the provider (MCP and plain HTTP). `Authorization` is left alone, because some apps already use it.
- The provider hashes the header, looks it up in `incoming`, and takes the caller's identity from the match, never from the request. It re-reads the file when it changes, so a revoke takes effect without a restart. With `enforce: false` it logs unknown callers and serves them; with `enforce: true` it answers 403. A configured file that is missing or malformed fails closed.
- The shared MCP front (`mcp/front.py`) does this check for every app built on it. Apps with their own server do the same check to be listed as enforce-ready. The Connection Router already does ([wizard-connection-router](https://github.com/humanitylabs-org/wizard-connection-router) `server.py`).
- **The gateway is a consumer too.** The Agent Service gateway holds one key per app with an `mcp`, in `~/.wizard-os/grants/agent-service.json` (mode 0600, written by the App Manager), and sends it when it proxies an agent's tool call. That key only proves "this call came through the gateway"; which agent may make the call is still the agent's tick list (#58). A host process without a key gets 403 once `enforce` is on.
- **Revocation** = delete the grant: disconnect the consumer from the provider's network, drop the key from both files, and add the pair to `denied` if it was a proposal.

## Install sheet and Apps screen

- Before install, the shell asks the Agent Service (`GET /wizard/v1/apps/<id>/proposed-grants`), which asks the App Manager. The sheet shows one ticked line per proposed grant, beside the per-agent tick boxes from #58.
- The Apps screen shows, per app: "Can use" (its outgoing grants) and "Used by" (incoming), each revocable, plus which agents may use it (#58).

## Rollout

1. **On by default** (Miguel, 27 Oct 2026). `wam network off` (or `WIZARD_APP_ISOLATION=0`) turns layer 1 off. Every
   override block is removed, apps go back to the shared network live, and the networks are deleted. `wam network on`
   redoes it.
2. **Layer 2 first, per app.** The App Manager writes grants files and keys for every installed Wizard app whether or not layer 1 is on. Providers start with `enforce: false` and move to `enforce: true` once their log shows zero unknown callers on dogfood boxes. The Router on the owner's daily box already runs with `enforce: true` from a hand-written file; the App Manager takes that file over without changing its shape.
3. **Turning layer 1 on (existing box):** the installer's `wam bootstrap` reconciles. Running apps move live (no
   restart unless a published port stops answering) from the declarations already on the box. Those are `uses:`,
   router needs and approved grants.
4. **Back to stock:** `wam network off` first. Changing the image tag alone leaves the user-config override blocks,
   which stock Runtipi still applies. No database changes either way.

Whether layer 1 must be on for the stable release stays deferred (AGENTS.md "Deferred"): due before any box installs another person's app.

## Acceptance (fresh Thales VM)

1. Install Wisdom with the Router and Claude: the sheet proposes Wisdom → `slot:connection-router`; Wisdom's Ask AI works.
2. Revoke it: Wisdom's next call gets 403 within one file re-read, with no restart; re-grant restores it.
3. A second test app with no grant: with layer 1 on, its container cannot resolve or connect to the Router; with only layer 2, it gets 403.
4. An agent unticked for an app (#58) still cannot call that app through the gateway, even though the gateway holds a key for it.
5. Flag off: generated compose files are byte-identical to stock.
