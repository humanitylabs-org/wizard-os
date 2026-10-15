# Agents: more than one agent on a box

**Status: MVP contract, approved by James 14 Oct 2026** (DECISIONS #43, #48, #58, #59 approved; #54, #60 proposed). Builds on [AGENT_STATE.md](AGENT_STATE.md) (one folder per agent, the agent adapter) and the permissions draft ([PERMISSIONS.md](PERMISSIONS.md), PR #6). The Agent Service implements this contract; the **Agents** app is its front end.

A box runs more than one agent. The first extra one is a **Private** agent: stock Hermes in its own container, talking only to a confidential model (Tinfoil GLM 5.3), with no outside tools. Its chats, memory and session history stay in its own folder. The main agent (the host Hermes, `hermes`) cannot see them.

## Words

| Word | Meaning |
|---|---|
| **Agent** | One running agent instance with its own folder, chats, memory and skills. Its id is the instance (`private`), not the harness. |
| **Harness** | The agent program: `hermes` today; Pi, Claude Code later. (Not "engine".) |
| **Model provider** | Where the model runs: `tinfoil`, `local`, or an AI Accounts provider (`anthropic`, `openai-codex`, ...). A provider is **confidential** when the model runs locally or inside an attested enclave (Tinfoil). |
| **Permissions** | What the agent may use. Set by a **preset**, then adjusted: outside tools, files, Wizard apps, agent apps, other agents. |
| **Wizard app** | An installed Wizard app (has a window; may also have MCP tools). Listed in `apps.json`. |
| **Agent app** | A tool or connector only an agent uses (MCP server, connector, skill pack). No window. |
| **Outside tools** | Harness toolsets that send content off the box: web, search, browser, x_search, image_gen, video_gen, tts, vision, video, delegation, connections, homeassistant, spotify. |

Apps are apps and agents are agents: agents live in their own **Agents** system app (Home tile / "Your system"), never in the Apps list or the Store. Each agent has its own chats; a persistent indicator (sigil, colour, label, lock when private) shows which agent is open. "Workspace" as a grouping and naming layer is a later UX decision: the data model has no workspace object yet, and nothing here prevents adding one.

## 1. Agent folder (#43)

`<wizard-os home>/agents/<id>/` (`~/.wizard-os/agents/<id>/` alongside; `${ROOT_FOLDER_HOST}/app-data/wizard-os/agents/<id>/` on a stock box).

```
agents/<id>/
  agent.json      # this contract, schema 1. No secrets.
  home/           # the harness home, bind-mounted read-write as the container's HERMES_HOME (/opt/data)
  runtime.key     # 0600: the bearer for this agent's own API server. Agent Service only; never served.
```

```json
{
  "schema": 1,
  "id": "private",
  "label": "Private",
  "harness": "hermes",
  "privacy": "private",
  "appearance": {"glyph": "lock", "hue": 160},
  "model": {"provider": "tinfoil", "model": "glm-5-3", "allowed_models": ["glm-5-3"], "fallback": false},
  "permissions": {
    "preset": "private",
    "outside_tools": [],
    "files": "own",
    "wizard_apps": [],
    "agent_apps": [],
    "other_agents": "none"
  },
  "runtime": {"kind": "container", "app_id": "agent-private", "api": "http://agent-private:8642", "port": 18650},
  "created_at": 1792000000
}
```

- `id`: `[a-z][a-z0-9-]{0,30}`; `hermes` is reserved for the main agent. Readers ignore folders without a valid schema-1 `agent.json` (e.g. experiments already in `agents/`).
- `privacy`: `private` | `standard`.
- `model.allowed_models`: the only models a run in this agent's threads may use. `fallback: false` means the harness has no fallback provider.
- `permissions.files`: `none` | `own` (only `home/`) | `shared-read` | `shared-write` (the box's user files root).
- `permissions.outside_tools`: the outside toolsets this agent may use; every other outside toolset is disabled in the harness config.
- `permissions.wizard_apps` / `agent_apps`: app ids from `apps.json` (Wizard apps) and agent-app ids. Stored here in the MVP; when app-to-app grants land they are mirrored as `wizard-grants.json` grants `{from: "agent:<id>", to: <app>}` so `wam connect` narrows to them.
- `permissions.other_agents`: `none` | `titles` | `search` | `read` (AGENT_STATE #46; MVP stores it, Agent Search enforces it later). This is what *this* agent may read of standard agents. No agent may ever read a private agent (#59): a grant naming a private agent as its source is rejected.
- `runtime.kind`: `container` (own container) | `external` (the host Hermes, alongside mode). `api` is the address from inside the box network; `port` is the loopback port on the host (`127.0.0.1:<port>`) for an Agent Service that runs on the host.
- The **main agent** is always listed as `id: "hermes"`, `runtime.kind: "external"`, `is_default: true`, served from the Agent Service's configured Hermes. Its state is never moved.

### Presets

| Preset | Outside tools | Files | Apps | Model |
|---|---|---|---|---|
| `private` | none | `own` | none | confidential provider only (`tinfoil`, `local`), `fallback: false` |
| `standard` | harness defaults | `shared-write` | owner's choice | any provider; fallback allowed |

Apps column at install (#58): a standard agent's box starts ticked, a private agent's starts unticked.

A preset sets the starting values; the owner adjusts any field afterwards. `preset` keeps the name it was created with.

## 2. Runtime: one container per agent

- Image: stock Hermes, the Runtipi package shape of `wizard-app-store/apps/hermes-agent` (`ghcr.io/humanitylabs-org/hermes-agent`), installed as Runtipi app `agent-<id>` through the App Manager's install path (local candidate package, same container-safety check, `apps.json` write).
- `home/` bind-mounted at `/opt/data`. The Agent Service seeds `home/config.yaml` and `home/.env` before first start (the image never overwrites them) and rewrites the managed keys on permission changes.
- API server on, with its own key (`API_SERVER_KEY` = `runtime.key`), listening on the app network and on `127.0.0.1:<port>`.
- Confidential model: a **Tinfoil attestation proxy sidecar** (`ghcr.io/tinfoilsh/tinfoil-proxy`) in the same compose; Hermes uses `http://tinfoil-proxy:3301/v1` as a custom provider. The provider key sits only in the agent's own `home/.env`.
- The Agent Service never gets the Docker socket. It asks the runtime driver (App Manager endpoint or a host helper) to install/start/stop `agent-<id>`.

## 3. Agent Service API

All under `/wizard/v1`, same access rules as the rest of the Service (owner access; writes need `Content-Type: application/json`). Errors are `{error, check, detail?}` where `check` names the failed guard.

| Method | Path | Result |
|---|---|---|
| GET | `/agents` | `{agents:[Agent]}` |
| POST | `/agents` | body `{label, harness:"hermes", model:{provider,model}, permissions:{preset,...overrides}, appearance?}` → 201 `{agent}`. Creates the folder, writes config, starts the container. `Idempotency-Key` honoured (same key + same body → same agent, 200). |
| GET | `/agents/<id>` | `{agent}` |
| PATCH | `/agents/<id>` | edit `label`, `appearance`, `permissions`, `model`. → `{agent}` |
| POST | `/agents/<id>/start`, `/agents/<id>/stop` | → 202 `{agent}` |
| GET | `/agent-options` | `{harnesses, providers, presets, wizard_apps, agent_apps, outside_tools, binding_apps}` (`binding_apps` = every Binding, section 7) |
| GET | `/app-bindings` | `{bindings:[Binding]}` (section 7) |
| GET, PUT | `/apps/<app_id>/binding` | `{binding}`; PUT body `{agent}` (section 7) |
| POST | `/apps/<app_id>/deliveries` | app-scoped token; section 7 |

`Agent` = `{id, label, harness, privacy, appearance, model:{provider, model, allowed_models, fallback}, permissions, status: "running"|"stopped"|"starting"|"error", status_detail, is_default, bound_apps:[{id,label,purpose}]}` (`bound_apps` = the apps that send work here, section 7). Never secrets, keys, host paths or upstream URLs.

`agent-options.providers` = `[{id, label, confidential, models:[{id,label}]}]`: Tinfoil (confidential, `glm-5-3`) plus the providers signed in through AI Accounts.

**Model rules (server-side, never by hiding UI):**
- `model.model` must be in the provider's model list; `allowed_models` defaults to `[model]` and must contain `model`.
- A `private` agent never gets a non-confidential provider: PATCH → 409 `check: "agent.confidential_provider"` unless the body carries `confirm_downgrade: true` (the MVP UI never sends it; a downgrade also flips `privacy` to `standard`).
- A run in an agent's thread with a `model` outside `allowed_models` → 409 `check: "agent.allowed_models"`.

**Threads and runs.** The existing thread and run endpoints (`/wizard/hermes/api/sessions...`, `/wizard/hermes/v1/runs...`) take `agent=<id>` (query; or `agent` in a JSON body, stripped before forwarding). No `agent` means `hermes`.

- Each thread object gains `agent: {id, label, privacy, appearance}` from server metadata.
- The agent is pinned when the thread is created (session create or first run). A request for that thread under another agent → 409 `check: "thread.agent_pinned"`.
- A private agent's threads are read from that agent's own API (`/api/sessions`, `/v1/runs`) and never written to the main Hermes `state.db`, its session search or its memory.

## 4. Recordings

A recording app (the Meeting Recorder, or any app that turns recordings into recaps) is an app with an agent binding (section 7). Its recaps go to the bound agent as assistant-only messages in that agent's own session store (no inference). Existing recaps are not migrated; moving or exporting them out of an agent happens only when the owner asks that agent to.

## 5. Which agents can use an app (#58)

Installing an app shows one tick box per agent: **"Which agents can use *App*?"** Standard agents start ticked, private agents start unticked. The owner's choice is written to each agent's `permissions.wizard_apps` / `agent_apps`, and the gateway serves an agent only the apps on its list. Either side can change it later: the app's settings sheet lists agents, the agent's page lists apps. An app never joins an agent without the owner's tick, so installing more apps never widens a private agent.

Apps that produce work for an agent also show **"Sends its work to: [agent]"** (the app → agent binding). That decides where the app's output lands; it gives the app no right to run the agent or read its history.

## 6. Private agents are sealed (#59)

- No other agent, standard or private, can read a private agent's chats, memory, skills or files. The Agent Service rejects any `agent-data` grant whose source is a private agent (`409 check: "agent.private_sealed"`), and Agent Search does not index private agents for other readers.
- Sharing goes outward only, as a copy: the owner asks the private agent to share something; it shows the exact item and its destination (another agent's thread, or Files); it publishes only after the owner approves that item. The destination receives a copy; it never gets a way back in. Each publish is logged (item, destination, time, no content in the log).
- Moving to a new harness works the same way: the private agent publishes what the owner approves into the new agent.
- On an alongside box the main Hermes runs on the host and can reach the files under `~/.wizard-os/agents/`. The wall is complete once the main agent also runs in its own container; until then the Agent Service, the gateway and Agent Search enforce it.

## 7. App → agent binding (#60, proposed)

Some apps produce work for an agent: recording recaps, reports, automation results. Each such app routes through exactly one agent, chosen by the owner, like an automation's destination.

**Declaration.** The app says so in `wizard.md`; the App Manager copies it into `apps.json` unchanged:

```yaml
agent_binding:
  required: true                       # the app has nothing useful to do without an agent
  purpose: Where your recording recaps go   # one line shown next to the picker
```

`agent_binding: true` is short for `{required: false, purpose: ""}`. Apps without it have no binding and cannot deliver.

**Storage.** The Agent Service owns the bindings, one per installed app, in `<wizard-os home>/app-bindings.json`:

```json
{"schema": 1, "apps": {"meeting-recorder": {"agent": "private", "set_at": 1791960000}}}
```

No entry = the main agent (`hermes`). A fresh box therefore routes every app to its one agent with nothing to set. The owner picks the agent at install time and can change it later; setting the main agent removes the entry.

`Binding` = `{app_id, label, required, purpose, agent, is_default, agent_info:{id,label,privacy,appearance}|null, problem?}`. `problem: "agent_missing"` when the bound agent no longer exists.

| Method | Path | Result |
|---|---|---|
| GET | `/wizard/v1/apps/<app_id>/binding` | `{binding}`. 404 `check: "app.id"` (not installed), 409 `check: "app.agent_binding"` (installed, declares no binding). |
| PUT | `/wizard/v1/apps/<app_id>/binding` | body `{agent}` → `{binding}`. Unknown agent → 404 `check: "agent.id"`. Owner access, JSON only. |
| GET | `/wizard/v1/app-bindings` | `{bindings:[Binding]}` for every installed app that declares one. |
| POST | `/wizard/v1/apps/<app_id>/deliveries` | app delivery, below. |

**Delivery.** `POST /wizard/v1/apps/<app_id>/deliveries` with `Authorization: Bearer <app token>` and

```json
{"delivery_key": "meeting-42", "title": "Recording · Team sync", "body": "<markdown>", "thread": "recordings", "metadata": {"meeting_id": "42"}}
```

- The app token is per app: the Service creates `<wizard-os home>/app-tokens/<app_id>` (0600) when the binding is first read or set; the installer hands it to the app (`WIZARD_DELIVERY_TOKEN`, with `WIZARD_DELIVERY_URL` = this endpoint). Another app's token, the owner's session or the Service's internal tokens are refused: 403 `check: "app.delivery_token"`.
- An app never names an agent or a session. The Service resolves the binding, derives the thread id from `(app_id, thread)` (`thread` defaults to `delivery_key`), pins the thread to the bound agent (section 3), and writes the assistant-only message through that agent's delivery path. `delivery_key` makes a retry idempotent (`already_delivered: true`); the same key with different content → 502 `check: "agent.delivery"`.
- Answer: `{verified: true, already_delivered, session_id, agent:{id,label,privacy,appearance}}`.
- **No fallback.** A bound agent that is stopped, starting or unreachable → 503 `check: "app.binding.agent_running"`; a bound agent that no longer exists → 409 `check: "app.binding.agent"`. The delivery never goes to another agent; the app keeps the item and retries.
- Delivering to the main agent needs a runtime that can write to the main agent's session store (the agent-runtime helper names the main container); without it → 502 `check: "agent.delivery"`.

**Where it shows.** An agent's page lists "Apps that send work here" (`Agent.bound_apps`). An app's info/settings sheet, and the System and Agents views, show **"Sends its work to: [agent ▾]"** (`Binding`), editable with PUT. Which agents can use an app (section 7) is separate: a binding only says where an app's deliveries go; it grants the app nothing else and gives the agent no new app.

## Deferred (James, 14 Oct; brought back when due)

- Whether apps that can run an agent get their own unticked warning line at install. Due before apps from other publishers are installable.
- Whether network isolation between apps (PR #6 layer 1, `WIZARD_APP_ISOLATION`) is required for the stable release. Due before any box installs another person's app.

## Not in this spec

Agent Search and cross-agent grants (#45, #46), the Wizard scheduler (#47), workspace objects, container hardening of the main Hermes, export/move UI.
