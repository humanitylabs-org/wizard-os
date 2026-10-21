# Agent bridge: how every agent on a box knows Wizard OS and uses its apps

**Status:** proposed by Archimedes, 11 Oct 2026 (DECISIONS #40). Owner: Archimedes (Agent Service items moved from Jan to Archimedes by James, 11 Oct).

## The problem

The first release end-to-end test (Telos, 10 Oct) passed only because the agent spent about 4 minutes digging through the box: it grepped skills, read `apps.json` by hand, found the skill file with `find /`, and wrote its own MCP client. On a fresh Hermes, or on a weak model, step 3 fails. The per-run "you are inside Wizard OS" block (wizard-agent-service#2) tells the agent the apps exist, but it hands over URLs and file paths, and a weak model has to turn those into working calls itself.

**Rule:** an installed app must reach the agent as **real callable tools plus a short, fixed orientation**. The agent should never need to read files, write clients or guess. If DeepSeek Flash can't do it on the first try, the bridge is wrong.

## How this fits the app spec (nothing in `wizard.md` changes)

- **Apps keep shipping MCP plus a skill, exactly as [WIZARD_MD.md](WIZARD_MD.md) says.** MCP stays the one way agents use apps (ARCHITECTURE). There are no per-app CLIs.
- **The `wizard` CLI ([WIZARD_CLI.md](WIZARD_CLI.md)) is unchanged.** It's a generic CLI for people, scripts and cron that reads the same MCP. It is not the agent's path to apps.
- **This spec is the Agent Service's half of the existing contract.** WIZARD_MD already says the Agent Service "registers each MCP with the agent, links each shipped skill, regenerates pointer skills". This doc says how, built so a flash-tier model succeeds.

## The design: three pieces, one source (`apps.json`), and a gate

Progressive disclosure from start to finish. Nothing about an individual app goes into every session, apart from the one-line skill entries the harness already lists for its own skills.

### 1. Discovery: pointer skills (the app index lives in the agent's skills list)

- **One pointer skill per job** (`provides`), generated into `~/.wizard-os/skills/wizard-job-<job>/` on every `apps.json` change (by the Agent Service, and by the Hermes plugin so they stay current when the service is down). For example: "short-form video → DeFleur Video. Load the `defleur-video` skill, then call its tools." The pointer holds routing only, never the app's workflow (WIZARD_MD "shipped skill + pointer skill").
- **Each app's shipped skill** is written by the App Manager into `~/.wizard-os/skills/<id>/` (wizard-app-manager#10, merged 11 Oct).
- **Hermes reads that folder as an extra skills dir** (`skills.external_dirs`, stock config). Its normal skills index then lists each pointer by name and description, the same way it lists the owner's own skills. A request for "a short from this clip" matches `wizard-job-short-form-video` the way any skill matches. The agent loads the full app skill only when it uses the app.
- **The owner's own learned skills.** Hermes may still save skills about how the owner likes a job done ("James wants 3 motion beats"). The rule stays pointer-not-copy: those skills point to the app skill, and Wizard's generated pointers are never edited by the agent. For AI generation, load the app's model/workflow contract before calling or delegating; a pointer must not describe that skill as optional for routine generation. The current chat model never overrides the app's pin ([APP_WORKFLOWS.md](APP_WORKFLOWS.md)).

### 2. Calling: one `wizard` MCP gateway, with app tools loaded on demand

- **One MCP endpoint in the Agent Service**, `/wizard/mcp` (streamable HTTP, box-only, token), proxies every running app's tools as `<app>__<tool>`. Each description starts with the app and its job. It adds one meta tool, `wizard_apps` (installed apps, jobs, status).
- **The agent's config gets one entry** (`mcp_servers.wizard`), written once at install. It never changes per app. Installs and uninstalls send `tools/list_changed`; Hermes re-fetches between turns, so there's no restart.
- **No tool bloat.** Hermes defers MCP tools behind its stock Tool Search bridge (`tools.tool_search`, on by default). The model sees `tool_search` / `tool_describe` / `tool_call` plus a short catalog line per server, never every app's full schema. Stock Hermes has no per-tool eager list (only `defer`), so `wizard_apps` is reached like any app tool: the kernel names it and the model calls it through `tool_call`. The gate passed that way (below). A box with 30 apps adds roughly the same per-session cost as a box with 3.
- **One door to guard.** Each agent's app ticks (#58) are enforced here, and every app call is logged here. The gateway also holds a per-app key so providers know the call came through it ([PERMISSIONS.md](PERMISSIONS.md)).
- Harnesses without deferral get the gateway's `wizard_apps` + `wizard_call` pair (two tools, constant size) instead of the full list.

### 3. Orientation: a fixed Wizard OS kernel, with no per-app list

- **Short and fixed** (under 900 characters, the same on every box): you are the owner's agent inside Wizard OS; the files root is `media/`; installed apps do jobs; when a request matches a `wizard-job-*` skill, load it first, then the app's skill, then call its tools through the `wizard` server; never search the disk or write your own client for an app; save only pointer skills.
- **Hermes, every surface** (Wizard, Telegram, CLI, cron): the `wizard-os` Hermes plugin registers the kernel as a system-prompt section through Hermes' stock plugin API (`register_system_prompt_section`). It's frozen per session, so it's cache-safe. It doesn't touch `SOUL.md`, memory or Hermes core, and removing the plugin removes it.
- **Other harnesses:** the Agent Service sends the same kernel in per-run `instructions` when the harness has no plugin.
- **Mid-thread installs:** the Agent Service adds a one-line delta to that run only ("new app: X for job Y, load `wizard-job-Y`"). The rest of the session stays byte-stable.
- **Fallback, only if the gate needs it:** a job → app map inside the kernel (one line per app, capped at 12 lines). It ships only if the weak-model gate fails without it, so the measured result decides.

### Published facts (built 11 Oct; the install thread links against these)

| | |
|---|---|
| Gateway | `http://127.0.0.1:8797/wizard/mcp`, streamable HTTP, box-only. Header `Authorization: Bearer <token>`; the token is `$WIZARD_MCP_TOKEN`, else `~/.wizard-os/mcp-token` (0600, created on first start). Meta tool `wizard_apps`; app tools `<app_id with - as _>__<tool>`, so Hermes names them `mcp__wizard__<app>__<tool>`. |
| Kernel | `GET /wizard/v1/agent-context?harness=hermes` (same bearer token): JSON `{ kernel, ... }`, under 900 characters. |
| Plugin | `hermes plugins install "https://github.com/humanitylabs-org/wizard-agent-service.git#hermes-plugin/wizard-os"`, then `plugins.enabled += wizard-os`. It reads `~/.wizard-os/apps.json` itself (`$WIZARD_OS_HOME` overrides). |
| Skills folder | `skills.external_dirs += ~/.wizard-os/skills` (app skills in `<id>/`, pointers in `wizard-job-<job>/`). |
| Agent Service setting | `agent.adapter: hermes-plugin` makes per-run instructions send only the one-line delta for apps installed mid-thread. Without it, the full kernel goes in every run. |

The link is therefore **three** stock-config edits, `mcp_servers.wizard`, `skills.external_dirs` and `plugins.enabled`, plus the token in `~/.hermes/.env` as `WIZARD_MCP_TOKEN` (referenced from the MCP header as `${WIZARD_MCP_TOKEN}`). The fourth edit in the original plan, `tools.tool_search.eager_tools`, does not exist in stock Hermes and is dropped.

### 4. Proof: the weak-model gate

A release can't ship unless this passes on a fresh box:

- Eight plain requests that name the job, not the app or MCP ("make a short from the clip in my Files", "transcribe this recording", "what apps do I have?" …). Run each on a **flash-tier model** (GLM 5.3 Flash; DeepSeek Flash where a route exists) and on the default model.
- Pass = the agent loads the matching pointer or app skill and its first app call is the right `<app>__<tool>` in at least 7 of 8, with zero file-system searches for app details, on both models.
- Also report tokens per session: the box with every default app installed must stay within 10% of the box with none.
- For AI-generating apps, verify the shipped skill and its prompt references are actually discoverable and that different default orchestrator models dispatch the same pinned process model. Unavailable or mismatched models fail without substitution; owner overrides are explicit and scoped. A successful tool call alone does not satisfy the model-contract gate.
- Lives in `wizard-os/tools/tests/agent_bridge_gate.py`, against a real Hermes, a real Agent Service and a real installed app.

**Measured 11 Oct** on a fresh Lima VM on Thales (stock `os.sh`, stock Hermes install, Hello Wizard, Transcriber, Browser, Secret Drop, AI Accounts), with no job map in the kernel:

- DeepSeek V4.1 Flash: 8/8 first calls right, 0 file searches for app details.
- Claude Opus 5.5 (default model, stock Hermes main): 7/8 first calls right. The miss was Secret Drop: the first call was right, then two shell reads to fetch the app's client. That is the Secret Drop skill's own workflow, not discovery.
- GLM 5.3 Flash: not run; Tinfoil returned `model_unavailable` all day.
- Tokens: a one-word reply costs 14,945 prompt tokens with no apps and 15,625 with every default app, +4.6% (the limit is 10%).
- The job→app map fallback did not help: DeepSeek scored 7/8 with it against 8/8 without, so it stays off.

## Agent adapter: the calls a second agent must serve

The Agent Service talks to its agent over HTTP only. A second agent (Pi, or any harness) serves this call set, and the Agent Service runs unchanged on top of it:

| Call | Hermes route | Agent Service use |
|---|---|---|
| run | `POST /v1/runs` | start a turn on a session |
| events | `GET /v1/runs/<id>/events` (SSE) | stream the turn to Wizard |
| steer | `POST /v1/runs/<id>/steer` | add guidance to a live turn. Also the liveness probe: an empty steer gets 400 while an agent is attached, 409 or 404 when none is |
| approve | `POST /v1/runs/<id>/approval` | answer a tool approval |
| stop | `POST /v1/runs/<id>/stop` | stop a turn |
| list | `GET /api/sessions` | thread list; compression chains under their root id with live-tip fields |
| read | `GET /api/sessions/<id>/messages?order=latest` | latest rows with `role`, `timestamp`, `display_kind` |
| status | `GET /v1/runs/<id>` | `queued`, `running`, `waiting_for_approval`, `stopping` or a terminal status |

Hermes `state.db` reads, as of wizard-agent-service `feature/agent-bridge`:

- **Gone (now HTTP):**
  - stale-run guard turn check (`status` + `steer` probe)
  - abandoned-run outcome (`read`)
  - delegation follow-through finder (`list` + `read`; completion rows have `display_kind: async_delegation_complete`)
  - canonical thread listing (`list`, paged)
- **Remain, read-only, only when `WIZARD_HERMES_STATE_PATH` is set** (stock Hermes serves none of them over HTTP):
  1. Archived threads: `/api/sessions` never lists archived sessions.
  2. Turns running on other surfaces (Telegram, TUI, cron), used to hold queued Wizard runs. Without the path, the queue counts only its own runs, and Hermes still serialises turns per session.
  3. The Helm closure overlay in the canonical listing (`read-human-sessions.py`), used only when a Helm DB is present. It is James's box only and is not part of Wizard OS.
  4. Thread-title authority (`title_source`, whether you or the agent named the thread). `/api/sessions/<id>` serves the title but not its source, so agent titling is off without the path.
  5. Session route truth (model and lineage, `session-truth.mjs`), used to annotate the thread list.

Without `WIZARD_HERMES_STATE_PATH` the Agent Service opens no Hermes file at all.

A session-search or grants service is out of scope here; the agent-state proposal covers it.

## Installing over an existing Hermes ("alongside" mode, James 11 Oct)

`os.sh` detects an existing Hermes (`~/.hermes/config.yaml` plus a running API server) and offers **alongside** mode. Wizard OS runs next to the owner's Hermes and never moves or migrates it:

1. Install Runtipi with the Wizard App Manager (unchanged), on ports that don't fight an existing web server.
2. Run the Agent Service + Wizard UX against the owner's Hermes API (`HERMES_ORIGIN=http://127.0.0.1:8642`) instead of the `hermes-agent` app. The `agent` slot is marked "external: host Hermes".
3. Link, with three stock-config edits, each recorded in `~/.wizard-os/linked.json` so `wizard unlink` reverses exactly them (exact values under "Published facts" above):
   1. `mcp_servers.wizard`, with its token in `~/.hermes/.env` as `WIZARD_MCP_TOKEN`
   2. `skills.external_dirs += ~/.wizard-os/skills`
   3. `plugins.enabled += wizard-os`, after `hermes plugins install` of the plugin
   `wizard link` never touches `tools.tool_search`: an owner who set Tool Search `off` keeps that, and every app tool is then loaded eagerly.
4. Give the shell **no access to the Hermes home** by default, apart from the agent's images folder (`cache/images`, read-only, so pictures in chats show). It reads chats over the Hermes API; the five `state.db` reads above stay off (no agent thread titles, other-surface activity or archived list). `wam alongside --share-history` opts in: the shell then mounts the Hermes home read-only and runs as the owner's uid, which lets it read every file there, `.env` and `auth.json` included. `wizard doctor` states which of the two a box uses.
5. Leave alone: `SOUL.md`, memory, sessions, other skills, providers and every existing `mcp_servers` entry.
6. Prove it with `wizard doctor`, which runs one gate request.

Migrating the owner's Hermes into Wizard OS (option B) comes later, as its own command.

## What this replaces

- WORK_OUTSTANDING "apps.json reader: register each app's MCP with the agent". Each app is no longer registered per app: one gateway entry covers all of them.
- The URL- and path-heavy per-run app block in wizard-agent-service#2. It becomes the fixed kernel plus pointer skills; no installed-app list goes into every run.
