# App-to-app permissions, v0.1 (draft)

Status: proposed by Miguel. Jan (Agent Service, the main caller) and James to review. Code waits for this spec ([DECISIONS](../docs/DECISIONS.md) #32, #33).

Today every Wizard app can reach every other app. Runtipi puts every app's main service on one shared Docker network (`runtipi_tipi_main_network`), so `hermes-frontend-3` reaches `http://hermes-agent:9119` without anyone saying it may. This spec says who may talk to whom, where that is written down, and how the App Manager enforces it.

## Two graphs

| Graph | Question | Source | Who sees it |
|---|---|---|---|
| **Compatibility** | Could A use B? | Computed from `wizard.md`: A's `uses:` names B's `id`, or a slot in B's `provides:`. Every `category: agent` app is compatible with every app that has an `mcp`. | Apps screen (wires between apps), the index, anyone. Nothing to store. |
| **Permission** | May A call B on this box? | **Grants** the owner approved. Stored by the App Manager. | Apps screen, install sheet, Agent Service. Enforced. |

A grant is only offered along a compatibility edge. Compatibility never opens a connection by itself.

## Grants

A grant is one direction: **consumer → provider**. The consumer may open connections to the provider; not the other way round.

- `to` is an app id (`hermes-agent`) or a slot (`slot:transcription`). A slot grant covers every installed app that provides the slot, so swapping the app in a parking spot (including the shell) keeps the grant. The owner narrows it by replacing it with a direct app grant.
- **Default grants, proposed at install** and shown on the install sheet ("Hermes Desktop will be able to use: Hermes Agent"):
  1. **agent → app first:** every `category: agent` app gets a grant to every installed app with an `mcp`, and every new app with an `mcp` is granted to every installed agent.
  2. **`uses:` second:** the new app gets a grant for each `uses:` entry (app id, or slot if no app has that id).
- The owner can untick a default at install or revoke later. A refused or revoked default is remembered (`denied`) and not proposed again.
- An app never needs a grant to itself. Uninstalling an app keeps its grants until it's reinstalled or the owner clears them.

## Where grants live (no database migration)

The App Manager writes one JSON file in Runtipi's state directory: `<runtipi data dir>/state/wizard-grants.json` (e.g. `~/runtipi/state/wizard-grants.json`). Stock Runtipi ignores it. Atomic writes (temp + rename). No tokens in this file.

```json
{
  "schema": 1,
  "updated_at": 1791543706,
  "seeded": ["hermes-agent", "hermes-frontend-3", "transcriber"],
  "grants": [
    {"from": "hermes-frontend-3", "to": "hermes-agent", "reason": "uses", "approved": "default", "created_at": 1791543706},
    {"from": "hermes-agent", "to": "transcriber", "reason": "agent", "approved": "owner", "created_at": 1791543710}
  ],
  "denied": [{"from": "hermes-agent", "to": "secret-drop"}]
}
```

- `reason`: `uses` | `agent` | `owner` (added by hand). `approved`: `default` (accepted at install) | `owner` (changed later).
- `seeded`: apps whose defaults were already proposed, so a restart doesn't re-add revoked grants.
- **Mirrored into `apps.json`** (top-level `grants`, same objects, no tokens) so the Agent Service and Wizard UX can show them without reading Runtipi's state. Readers ignore unknown fields, so this is not a version bump ([APPS_JSON.md](APPS_JSON.md)).

## Enforcement layer 1: Docker networks

With isolation on, a Wizard app's main service (`is_main`) and any `add_to_main_network` service **leave** the shared main network and join the app's own network, `wizard-app-<id>` (created by the App Manager, not internal, label `wizard.app=<id>`).

| Before | After |
|---|---|
| Main services of all apps on `runtipi_tipi_main_network` | Main services on `wizard-app-<id>` only |
| Any app reaches any app by service name | A consumer's containers are **connected to the provider's network** for each grant, so `http://hermes-agent:9119` resolves as before, but only for granted apps |
| Multi-service private network `<app>_<store>_network` | Unchanged |

- The App Manager **reconciles** after every start/install/update/restart of a Wizard app, on boot and every few minutes: create missing `wizard-app-<id>` networks, connect each granted consumer, disconnect anything without a grant. Containers recreated by `docker compose up` lose manual connections, which is why reconcile runs after every start.
- **Runtipi's own reach.** Wizard apps publish their port on `127.0.0.1` only and aren't exposed through Traefik, so leaving the main network loses nothing. `RUNTIPI_FORWARD_AUTH_URL` (`http://runtipi:3000/...`) is called by Traefik, not by apps; no current Wizard app calls `runtipi:3000`. If an owner exposes a Wizard app through Traefik, that main service stays on the main network (Traefik must reach it) and the Apps screen warns that the app is reachable by every app. Later: connect the reverse proxy to `wizard-app-<id>` instead.
- Apps from other Runtipi stores are untouched: they stay on the main network and can no longer reach isolated Wizard apps.
- Limit: networks stop other **containers**. They do nothing for host processes, which reach every app on its loopback port.

## Enforcement layer 2: per-grant credential

The network says "this container may connect"; the credential says "this caller is that app". The key alone works on stock Runtipi, but it's only half the protection (any app could still try to reach any other).

- On each grant the App Manager mints a random 32-byte token. It writes one file per app, `<app-data>/<id>/wizard/grants.json`, mounted read-only into the app at `/run/wizard/grants.json` (`WIZARD_GRANTS_FILE` points at it):
  `{"outgoing": {"hermes-agent": "<token>"}, "incoming": [{"from": "hermes-frontend-3", "sha256": "<hex>"}], "enforce": false}`
- The consumer sends `X-Wizard-Grant: <token>` on every call to the provider (MCP and plain HTTP). `Authorization` is left alone, because some apps already use it (Hermes' `HERMES_API_KEY`).
- **MCP-front contract change** (`mcp/front.py`, shared by Transcriber, Secret Drop, Hermes Agent, AI Accounts): re-read the file when it changes, hash the header, and look it up in `incoming`. With `enforce: false` it only logs unknown callers; with `enforce: true` it answers 403. Apps that don't use the shared front must do the same check to be listed as `enforce`-ready.
- **Revocation** = delete the grant: disconnect the consumer from the provider's network at once, drop the token from both files (the front stops accepting it on its next read), and add the pair to `denied` if it was a default.

## Rollout

1. **Flag off by default:** `WIZARD_APP_ISOLATION=1` on the App Manager turns layer 1 on. Off means byte-for-byte today's compose files and no network changes.
2. **Turning it on (existing box):** on first reconcile with no grants file, the App Manager seeds defaults for every installed Wizard app as if each had just been installed, then restarts Wizard apps one by one. The owner sees the seeded grants in the Apps screen.
3. **Layer 2 in report-only mode** (`enforce: false`) until every MCP front logs zero unknown callers on dogfood boxes, then `enforce: true`.
4. **Back to stock:** turn the flag off or change the image tag. Runtipi regenerates every compose file on start, so apps return to the main network; the grants file and `wizard-app-*` networks are ignored (remove with `docker network rm`). No database changes either way.

## Open questions for Jan

1. **The Agent Service is a host process**, not a container. It reaches apps through loopback ports, so layer 1 doesn't cover it. Should it be a named consumer (`agent-service`) holding a grant to every app with an MCP, and use layer 2 tokens like any app?
2. **How does it get its tokens?** Options: read them from the App Manager API (`GET /api/wizard/grants?from=agent-service`, behind the App Manager token from #28), or a file under `~/.wizard-os/` written by the App Manager with mode 0600.
3. **Which identity calls the app**: the Agent Service registers MCPs with Hermes using `mcp.url` (host) or `mcp.internal` (container). If Hermes calls from its container, the caller is `hermes-agent` (layer 1 + its token); if from the host, it's `agent-service`. One answer per path.
4. When the Agent Service moves into a container (#30), it becomes an ordinary `category: agent` consumer and question 1 goes away. Is that the target?
5. The install sheet needs the proposed grants before install. Should the Agent Service's `/wizard/v1/apps` return them, or should the Wizard UX ask the App Manager directly?
