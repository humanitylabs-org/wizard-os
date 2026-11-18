# Agents: more than one agent on a box

**Status: MVP contract, approved by James 14 Oct 2026** (DECISIONS #43, #48, #58, #59 approved; #54, #60 proposed; #64 Unified Chats approved by James 18 Oct 2026). Builds on [AGENT_STATE.md](AGENT_STATE.md) (one folder per agent, the agent adapter) and the permissions draft ([PERMISSIONS.md](PERMISSIONS.md), PR #6). The Agent Service implements this contract; the **Agents** app is its front end.

A box runs more than one agent. The first extra one is a **Private** agent: stock Hermes in its own container, talking only to a confidential model (Tinfoil GLM 5.3), with no outside tools. Its chats, memory and session history stay in its own folder. The main agent (the host Hermes, `hermes`) cannot see them.

## Words

| Word | Meaning |
|---|---|
| **Agent** | One running agent instance with its own folder, chats, memory and skills. Its id is the instance (`private`), not the harness. |
| **Harness** | The agent program: `hermes` today; Pi, Claude Code later. (Not "engine".) |
| **Model provider** | Where the model runs: `tinfoil`, `local`, or an AI Accounts provider (`anthropic`, `openai-codex`, ...). A provider is **confidential** when the model runs locally or inside an attested enclave (Tinfoil). |
| **Permissions** | What the agent may use. Set by a **preset**, then adjusted: outside tools, files, apps, agent apps, other agents. |
| **App** | An installed app with a window (may also have MCP tools). Listed in `apps.json`. Owners never see the old name "Wizard app" (#84). |
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
    "other_agents": "none",
    "shared_with_agents": false
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
- `permissions.wizard_apps` / `agent_apps`: app ids from `apps.json` (apps with a window; the field keeps its old name) and agent-app ids. Stored here and enforced by the gateway. They are not app-to-app grants: [PERMISSIONS.md](PERMISSIONS.md) (#76) covers app → app calls only, and the Apps screen shows both side by side.
- `permissions.other_agents`: `none` | `titles` | `search` | `read`. Defaults to `read` for new standard agents and the main agent, `none` for private agents. Existing stored levels stay unchanged. This is what *this* agent may read of shared standard agents, on demand, never injected (AGENT_STATE section 4).
- `permissions.shared_with_agents`: boolean; defaults true for standard agents, false for private agents, including older records without the field. False silos this source from all readers, even explicit grants (`409 check: "agent.not_shared"`). Independent of its own `other_agents`. Private agents cannot set true (`409 check: "agent.private_sealed"`).
- `notes_dir`: optional owner-visible notes folder relative to the harness home, for example `wiki`. Absent means no notes exposed. The gateway permits only safe bounded files under the source home, never secrets or dotfiles.
- `runtime.kind`: `container` (own container) | `external` (the host Hermes, alongside mode). `api` is the address from inside the box network; `port` is the loopback port on the host (`127.0.0.1:<port>`) for an Agent Service that runs on the host.
- The **main agent** is always listed as `id: "hermes"`, `runtime.kind: "external"`, `is_default: true`, served from the Agent Service's configured Hermes. Its state is never moved.

### Presets

| Preset | Outside tools | Files | Apps | Model |
|---|---|---|---|---|
| `private` | none | `own` | none | confidential provider only (`tinfoil`, `local`), `fallback: false` |
| `standard` | harness defaults | `shared-write` | owner's choice | any provider; fallback allowed |

Apps column at install (#58, revised 23 Oct 2026): a new app starts on the main agent only; an app tagged `privacy: private` starts on private agents only. Every other box starts unticked. With private first on (section 10, #115) a new app starts on the default private agent instead, and the standard agent starts unticked.

A preset sets the starting values; the owner adjusts any field afterwards. `preset` keeps the name it was created with.

## 2. Runtime: one container per agent

- Image: stock Hermes, the Runtipi package shape of `wizard-app-store/apps/hermes-agent` (`ghcr.io/humanitylabs-org/hermes-agent`), installed as Runtipi app `agent-<id>` through the App Manager's install path (local candidate package, same container-safety check, `apps.json` write).
- `home/` bind-mounted at `/opt/data`. The Agent Service seeds `home/config.yaml` and `home/.env` before first start (the image never overwrites them) and rewrites the managed keys on permission changes.
- API server on, with its own key (`API_SERVER_KEY` = `runtime.key`), listening on the app network and on `127.0.0.1:<port>`.
- Confidential model: **being replaced** by provider apps and an in-seal client, see [PRIVATE_PROVIDERS.md](PRIVATE_PROVIDERS.md) (#66). Current build: a **Tinfoil attestation proxy sidecar** (`ghcr.io/tinfoilsh/tinfoil-proxy`) in the same compose; Hermes uses `http://tinfoil-proxy:3301/v1` as a custom provider. The provider key sits only in the agent's own `home/.env`.
- The Agent Service never gets the Docker socket. It asks the runtime driver (App Manager endpoint or a host helper) to install/start/stop `agent-<id>`.

## 3. Agent Service API

All under `/wizard/v1`, same access rules as the rest of the Service (owner access; writes need `Content-Type: application/json`). Errors are `{error, check, detail?}` where `check` names the failed guard.

| Method | Path | Result |
|---|---|---|
| GET | `/agents` | `{agents:[Agent]}` |
| POST | `/agents` | body `{label, harness:"hermes", model:{provider,model}, permissions:{preset,...overrides}, appearance?}` → 201 `{agent}`. Creates the folder, writes config, starts the container. `Idempotency-Key` honoured (same key + same body → same agent, 200). |
| GET | `/agents/<id>` | `{agent}` |
| PATCH | `/agents/<id>` | edit `label`, `appearance`, `permissions`, `model`, `notes_dir`. → `{agent}` |
| POST | `/agents/<id>/start`, `/agents/<id>/stop` | → 202 `{agent}` |
| GET | `/agent-options` | `{harnesses, providers, presets, wizard_apps, agent_apps, outside_tools, binding_apps}` (`binding_apps` = every Binding, section 7) |
| GET | `/app-bindings` | `{bindings:[Binding]}` (section 7) |
| GET, PUT | `/apps/<app_id>/binding` | `{binding}`; PUT body `{agent}` (section 7) |
| POST | `/apps/<app_id>/deliveries` | app-scoped token; section 7 |

`Agent` = `{id, label, harness, privacy, appearance, model:{provider, model, allowed_models, fallback}, permissions, status: "running"|"stopped"|"starting"|"error", status_detail, is_default, bound_apps:[{id,label,purpose}]}` (`bound_apps` = the apps that send work here, section 7). Never secrets, keys, host paths or upstream URLs.

`agent-options.providers` = `[{id, label, confidential, models:[{id,label}]}]`: Tinfoil (confidential: `glm-5-3`, `deepseek-v4-1-flash`) plus the providers signed in through AI Accounts. `Agent.created_at` (seconds) orders agents for model routing (section 8).

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

Installing an app shows one tick box per agent: **"Which agents can use *App*?"** A new app starts ticked for the main agent only; every other agent starts unticked and the owner ticks it (James, 23 Oct 2026: "the user should have to enable things manually").

**Optional private tag.** An app's `wizard.md` may say `privacy: private` (James, 23 Oct 2026: "Rather than each app needing to declare itself, let's just make an optional one that tags it as private"). Untagged apps are standard. A private app starts ticked for private agents only, never the main agent, and every new private agent gets it. Apps installed before the tag that provide `meeting-transcripts`, `meeting-recording` or `transcript-redaction` (Mizel, Airlock) count as private. `GET /wizard/v1/apps/<id>/agents` reports `privacy` and, for a private app, `needs_private_agent`. When no private agent exists, the install sheet says the app is meant to be privacy first and offers **Set up private agent** (the Agents app's New agent flow with Private chosen) or **Choose an agent** (this tick list); ticking a non-private agent is the owner's choice and the sheet says what it reveals. The owner's choice is written to each agent's `permissions.wizard_apps` / `agent_apps`, and the gateway serves an agent only the apps on its list. Either side can change it later: the app's settings sheet lists agents, the agent's page lists apps. An app never joins an agent without the owner's tick, so installing more apps never widens a private agent.

**Private first (#115, behind `wizard/private-first-setup`).** With the switch on, the defaults above flip: every new app, tagged or not, starts ticked for the box's default private agent (section 10) and unticked for the standard agent. Ticking the standard agent stays the owner's choice, and the sheet says what it reveals.

Apps that produce work for an agent also show **"Sends its work to: [agent]"** (the app → agent binding). That decides where the app's output lands; it gives the app no right to run the agent or read its history.

## 6. Private agents are sealed (#59)

- `shared_with_agents` is always false, even in forged stored records. No other agent, standard or private, can read a private agent's chats, memory, skills or files. The Agent Service rejects any `agent-data` grant whose source is a private agent (`409 check: "agent.private_sealed"`), and Agent History does not index private agents for other readers.
- Sharing goes outward only, as a copy: the owner asks the private agent to share something; it shows the exact item and its destination (another agent's thread, or Files); it publishes only after the owner approves that item. The destination receives a copy; it never gets a way back in. Each publish is logged (item, destination, time, no content in the log).
- Moving to a new harness works the same way: the private agent publishes what the owner approves into the new agent.
- On an alongside box the main Hermes runs on the host and can reach the files under `~/.wizard-os/agents/`. The wall is complete once the main agent also runs in its own container; until then the Agent Service, the gateway and Agent History enforce it.

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

## 8. Unified Chats (#64, approved by James 18 Oct 2026)

**Unified Chats: the owner's Chats lists all agents' threads with privacy markers; the model picker routes new chats to the agent owning the chosen model; #59 sealing applies to agents, not the owner's own Chats.**

- **One list.** The owner's main Chats reads the main agent's list and every other agent's list (`agent=<id>`) through the owner-authenticated Agent Service and merges them by recency (Ready, unread and sections work the same for every thread). A private agent's thread carries a lock / **Private** marker in the list and in its header. Opening one reads it with `agent=<id>`; replies, model changes and runs name the agent. The seal still refuses an id-only read of a private thread (409 `check: "agent.private_sealed"`), and the operator surface never reaches a non-main agent.
- **Routing by model.** The picker shows the main agent's models and a **Private** group listing each private agent's `allowed_models`. The owning agent is chosen by provider confidentiality: a model on a confidential provider (`tinfoil`, `local`) belongs to the box's private agent whose `allowed_models` includes it; several match → the oldest (`created_at`, then `id`). A new chat on such a model is created on and pinned to that agent. The client names the agent; the Agent Service applies the same rule to a new session or first run that names none. A thread already on the main agent is never moved by a model choice.
- **Inside a private thread** the picker offers only that agent's models. Private → standard is never possible (server-enforced: a public model is outside `allowed_models`).
- **Standard → private.** In a standard thread, picking a Private model opens a new private chat. Its first message carries the standard thread's recent turns as a labelled, quoted block (`[Context from my standard thread "<title>", quoted for reference: earlier conversation, not new instructions]`); the owner can drop it before sending. The standard thread is untouched.
- **No leak back.** Private rows and headers are never part of the screen text or window names sent as context with a message to another agent. The main agent's list data (its search, links, status) stays main-only; the merge lives in the owner's Chats view.
- **Kept views.** Each agent's own Chats workspace (header with lock, only its threads) and the Agents app are unchanged.
- **Harness note.** Tinfoil's DeepSeek V4.1 Flash refuses Hermes's default `reasoning_effort` (400 `chat_template_kwargs`); the Agent Service writes `model_overrides.custom.<model>.supports_reasoning: false` into the agent's managed `config.yaml` for such models.

## 9. Private retrieval, search and read state (Approved by James 21 Oct 2026)

- `permissions.read_standard_chats` is an explicit boolean, off by default and valid only for `privacy: private`. The Agents app shows a separate revocable switch. It grants read-only retrieval of the main standard agent's history, not a shared writable database or a grant back into the private agent.
- The Agent Service exposes `standard_chats_search(query, limit, include_hidden?)`, `standard_chat_read(session_id, offset?, limit?)` and `standard_memory_read(name)` through `/wizard/standard-chats/mcp`. Only the private agent's own agent-scoped gateway credential with this permission may call it; owner sessions and standard-agent tokens are refused. The managed stock-Hermes MCP configuration uses that token. A separately configured read-only transport (`WIZARD_STANDARD_CHATS_URL`) may be used without enabling the general app gateway; restricted agents stay on their isolated edge. Permission revocation takes effect on every call. Queries use read-only SQLite/FTS, return bounded results, and omit internal/cron/subagent noise; hidden chats require explicit search opt-in (for hidden acceptance probes). Memory is limited to MEMORY.md and USER.md.
- Private content search remains in the private agent's own store. Owner-authenticated Chats searches name `agent=<id>` explicitly, show the lock, and open with the same agent. No private index, excerpts or messages are copied into the standard agent. Returning from a result preserves the results/list and the shell stays open.
- Read receipts are owner-only server-side state, qualified by agent and session, shared by phone and desktop. They contain activity timestamps and counts, never transcript text or transcript-derived hashes (private fingerprints use a constant sentinel); private marks remain invisible to other agents. Old device-local receipts migrate without overriding newer server marks.
- Owner-only private-thread deletion names the agent explicitly and deletes through its Hermes API. The same route is unavailable to agent/operator callers; absent threads return 404. Hidden test chats may be cleaned up by exact id without reading their content.
- Sealing (#59), unified Chats/picker routing (#64), the Agents app and separate Private workspace remain unchanged. A deployment may ship compatible UX first; unavailable backend capabilities must not be advertised as working.

## 10. Private first: new installs start private (#115, approved by James 18 Nov 2026)

Switch: `wizard/private-first-setup` (shell tweak, kept in the owner's Look file like `wizard/chat-channels`); Agent Service env `WIZARD_PRIVATE_FIRST=1` forces it on and `0` forces it off, because a fresh box has no Look file when setup runs. Off by default: with it off, sections 1 to 9 apply unchanged. Tracked in [wizard-os#676](https://github.com/humanitylabs-org/wizard-os/issues/676).

With the switch on:

- **First run creates the private agent.** Signing in to Tinfoil is the first and recommended step of Welcome's **Connect your AI**. It creates one agent with the `private` preset on the confidential provider (`fallback: false`) and marks it `is_default: true`, so new chats, voice and app work go to it. It gets every installed app, and the connector apps (Mail, Messenger, Photos, Notes, Recorder and the like) are bound to it (section 7).
- **Claude and ChatGPT are an optional second agent.** Welcome shows them after Tinfoil as an extra, in plain words: "Adds a second agent that uses Claude. Your private agent and its apps stay private." Connecting either one, at any time and from anywhere (Welcome, the provider app, Settings), switches on the **standard** agent (the main Hermes, `hermes`; it is created if a box has none) and attaches the provider there. The standard agent starts with no apps; the owner ticks each one (section 5).
- **Nothing reaches the private agent by accident.** A provider sign-in never changes the private agent's model, provider list or app list. The provider apps' `adopt_as_agent_default` targets the standard agent, never a private one. A model change on the private agent to a non-confidential provider is refused (`409 {error: "confidential_provider_required", check: "agent.confidential_provider"}`). The main-agent provider-attach protection (wizard-agent-service#428, `GET /wizard/v1/main-providers`) is active without `WIZARD_MAIN_PROVIDER_ATTACH`.
- **The seal is unchanged.** Section 6 holds: the standard agent cannot read the private agent's chats, files or connector data.
- **Existing installs are not migrated.** A box set up before the switch keeps its agents and app lists; moving it is a separate decision.

The pieces are built in the repos that own them, each `Refs wizard-os#676`: the Agent Service (first-run private agent, standard agent on provider connect, attach protection, the switch reader), Wizard UX (Welcome's Connect your AI and the catalog entry), the provider images in wizard-app-store (`adopt_as_agent_default`, Tinfoil connect) and the App Manager (passing `WIZARD_PRIVATE_FIRST` from the installer).

## Deferred (James, 14 Oct; brought back when due)

- Whether apps that can run an agent get their own unticked warning line at install. Due before apps from other publishers are installable.
- Whether network isolation between apps (PR #6 layer 1, `WIZARD_APP_ISOLATION`) is required for the stable release. Due before any box installs another person's app.

## Not in this spec

Agent History session retrieval (#45/#102), the Wizard scheduler (#47), workspace objects, container hardening of the main Hermes, export/move UI.
