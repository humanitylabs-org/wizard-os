# Agent state: what each agent learns, and who can read it

**Status: proposed (James, 11 Oct 2026; DECISIONS #43–#49).** Builds on the agent bridge (#40, [AGENT_BRIDGE.md](AGENT_BRIDGE.md) in PR #12) and the permissions draft ([PERMISSIONS.md](PERMISSIONS.md) in PR #6).

Hermes is the agent today. A box will often run more than one agent: a frontier Hermes for building, a lean private agent on a Tinfoil model, a Pi or Claude Code agent someone is trying out. Each agent learns as it works. It writes skills, keeps memories, and builds up session history.

Wizard OS owns **where** that state lives and **who** may read it. The agent owns **how** it uses its own state. That keeps three promises:

- **No lock-in.** Switching agents, or running two side by side, doesn't throw away what the first one learned. The new agent can look it up.
- **Privacy by grant.** One agent can't read another's sessions, skills or memory unless the owner says so.
- **One place for the box's moving parts.** Schedules, keys and approvals are Wizard's, not buried inside one agent's container.

## 1. One folder per agent

Every installed agent gets one folder. Its id is the **instance**, not the harness, because a box can run two Hermes agents.

```
~/.wizard-os/
  skills/                    # Wizard system skills: app skills + pointer skills (#40). Every agent reads these.
  agents/
    hermes/                  # one folder per installed agent instance
      agent.json             # harness, model route, privacy label, where its state is inside home/
      home/                  # bind-mounted into the agent's container as its home (HERMES_HOME here)
    hermes-private/
      agent.json
      home/
    pi-trial/
      agent.json
      home/                  # Pi's agent dir (skills/, sessions/ as JSONL)
```

- **Bind mount, not symlink.** The agent's container mounts `agents/<id>/home` read-write as its own home. A symlink pointing out of a container doesn't resolve inside it.
- **Outside the user files root.** `media/` is mounted into every app (SYSTEM_APPS "one file root"), so agent state there would be readable by DeFleur, the browser or any other app. `~/.wizard-os/agents/` is mounted only into its own agent and into Agent Search (section 3).
- **Survives uninstall and moves with the box.** Uninstalling an agent keeps its folder ("user data outlives apps"). Backups and the one-button host move include `~/.wizard-os/agents/`.
- **Harness layout stays native.** Hermes keeps `skills/`, `state.db` and its memory store where Hermes expects them, inside `home/`. `agent.json` tells Wizard where they are, so nothing in Hermes changes:

```json
{
  "schema": 1,
  "id": "hermes-private",
  "harness": "hermes",
  "label": "Private Hermes",
  "privacy": "private",
  "model_route": "tinfoil",
  "state": {
    "skills": "home/skills",
    "sessions": {"format": "hermes-state-db", "path": "home/state.db"},
    "memory": {"format": "hermes-holographic", "path": "home/memory_store.db"}
  }
}
```

`privacy` is `private` (the model runs locally or in a confidential provider such as Tinfoil) or `standard`. It's a label used for warnings and defaults, never a hard wall (section 4).

## 2. Skills: each agent keeps its own, and can look up the others'

- **Each agent writes only its own skills.** Skills are written for one harness's tools (`skill_view`, `delegate_task`, `~/.hermes/...`). A skill shared by every agent would be wrong for most of them.
- **Wizard system skills** stay in `~/.wizard-os/skills/` (#40): app skills from the App Manager plus pointer skills from the Agent Service. Every agent reads them, read-only (Hermes through `skills.external_dirs`). We call them **system skills**, not "shared", because Wizard writes them and no agent edits them.
- **Other agents' skills are looked up, never injected.** No agent's skills list ever includes another agent's skills by default. With a grant (section 4), an agent can call Agent Search:
  - `skills_search(query, agents?)` returns names, descriptions and which agent and harness wrote each.
  - `skill_read(agent, name)` returns the skill. It starts with: "Written by *agent* for the *harness* harness. Tools and paths it names may not exist for you. Adapt it into your own skill before relying on it."
- **Adapting is the agent's job.** If the skill is useful, the reading agent writes its own version with its own skill tooling and records `adapted_from: <agent>/<skill>` in the frontmatter. The original is never edited.

When and how often agents should look up another agent's skills is left to usage. This spec only provides the ability.

## 3. Agent Search: one system app that reads across agents

**Agent Search** (`wizard-agent-search`, slot `agent-search`, `system: true`) is a headless system app. It's the only thing that reads another agent's state, and it does that only under grants.

- **Reads each agent's own store through a small reader per harness.** First readers: `hermes-state-db` (sessions), Hermes skills folder, `hermes-holographic` (facts), `pi-jsonl` (sessions), Pi skills folder. It mounts `~/.wizard-os/agents/*` **read-only** and never writes to an agent's store.
- **Builds its own index per agent**, in `~/.wizard-os/agent-search/<agent>/`. Revoking a grant never needs a re-index: the reader agent simply can't query that index any more. Uninstalling an agent and choosing "forget" deletes its index.
- **Search method:** the same ones Hermes uses today. Its session search is SQLite full-text search, and its fact memory is the holographic provider (both MIT). We vendor them so every agent gets Hermes-quality recall without running Hermes.
- **MCP tools** (through the `wizard` gateway, #40): `sessions_search`, `session_read`, `facts_search`, `skills_search`, `skill_read`, `agents_list`. Every result names the source agent.
- **Own data is always allowed.** An agent can search its own history through Agent Search with no grant (useful for harnesses with no session search of their own, such as Pi).
- **The Wizard thread list reads from here too.** The Agent Service's thread list, archive and status checks move from reading Hermes' `state.db` directly to the agent adapter (#47) and Agent Search, so a second agent's threads can appear in the same list.

Why not give agents each other's database files: SQLite with a write-ahead log across containers risks corruption. The formats are each harness's private schema and change with updates. And a file grant is all-or-nothing and invisible. Why not each harness's own MCP: Hermes has one (`hermes mcp serve`), Pi has none, the shapes differ, and the private agent's own endpoint would be a second door to guard.

## 4. Grants: the owner decides who reads what

A grant is one direction, **reader agent → source agent**, with a scope per kind:

```json
{"from": "pi-trial", "to": "hermes", "sessions": "search", "skills": "read", "memory": "none",
 "subjects": ["Wizard OS"], "approved": "owner", "created_at": 1791700000}
```

- Scopes: `none`, `titles` (thread titles and dates), `search` (search results with snippets), `read` (whole sessions or skills).
- `subjects` optionally limits it to threads in those subjects.
- **Default: no grants.** Installing a second agent gives it nothing from the first. The owner turns it on per pair, in the Apps screen or by asking an agent that holds the "manage grants" right (owner-approved).
- **No hard privacy wall.** Two private agents can read each other, which is useful when moving from one harness to another or split-testing. A grant that lets a `standard` agent read a `private` agent shows a plain warning ("Text from Private Hermes may be sent to *provider*"). The owner can still allow it.
- Stored alongside app grants in `wizard-grants.json` (PERMISSIONS.md) as `kind: "agent-data"`, so one file and one screen show every permission on the box. Agent Search enforces them on every call and logs each cross-agent read (reader, source, kind, scope, no content).

## 5. Memory: opinionated by default

- **Each agent keeps its own memory engine.** Memory is wired into the harness's turn loop (what gets recalled into the prompt, when facts are written), so we don't replace it. Agent Search reads it across agents, under grants.
- **One opinionated default.** The Wizard OS Hermes app ships with the holographic fact store turned on (`memory.provider: holographic`), the setup we run ourselves and install for clients. Owners can change it, but nobody has to choose among Hermes' eight memory backends to get started.
- **Same engine at Wizard level.** Agent Search uses that same holographic method for facts, so a lean agent with no memory of its own still gets good recall through Agent Search.
- **Later, optional:** a `wizard` memory provider plugin (stock Hermes plugin API) could point Hermes' memory at Agent Search instead of its own store. Only if usage shows one shared memory beats per-agent memory.

## 6. Schedules: one Wizard scheduler

- **The Agent Service owns every schedule on the box.** A job is: when (cron or interval, owner's timezone), which agent, which model, a prompt or skill, which thread gets the result, and on/off.
- **One list in the Wizard UX** (Settings → Schedules, and the agent can manage it through the `wizard` gateway: `schedules_list/create/update/pause`).
- **Agents don't keep their own cron on a Wizard box.** The installer turns Hermes' cron scheduler off when the Wizard scheduler is active. Install-alongside mode imports existing Hermes cron jobs once, read from `jobs.json`, and offers to switch them over.
- **Blueprints become schedule templates.** The useful ideas from Hermes automation blueprints (morning brief, topic digest, weekly review) ship as Wizard schedule templates, and an app's skill can carry its own template offered at install.

## 7. The agent adapter

The Agent Service talks to each agent through one small call set: **run, events, steer, approve, stop, list threads, read thread, run status**.

- **Hermes** implements it over its HTTP API (`/v1/runs`, `/api/sessions`). Today the Agent Service still reads Hermes' `state.db` directly for six things: the thread list, the archive, the "is a turn running" check, abandoned-run outcomes, active sessions and helper follow-through. Moving those onto the adapter is owned by the agent-bridge work (#40). Anything Hermes' API doesn't expose falls back to Agent Search.
- **Pi** would implement it over its RPC mode (JSON over stdin/stdout).
- **Agent-specific runs** carry `agent: <id>`, so a thread and a schedule can each name the agent they use.

## 8. Lean agents

Weak, cheap or private models do well on short jobs and poorly on long multi-step builds. From 692 Wizard threads over 30 days: 30% needed 20 or fewer tool calls, and 45% needed more than 60.

- **A lean agent** runs a small profile: few tools, the Wizard kernel, system skills, a skill search tool instead of a full skills list. It handles quick questions, drafts, summaries, single app actions, voice quick-asks and fetch-and-summarise schedules.
- **The frontier agent** keeps builds, releases, browser work with credentials, research that needs checking, fan-out to helper agents, and anything with outside effects.
- **Every workflow moved into an app tool moves work into the lean tier.** One `defleur_video__start_edit` call suits a flash model; sixty terminal steps doing the same job don't.
- **Which harness for the lean tier** (a slim Hermes profile, Pi, or another) is decided by a bake-off once a containerised box exists (WORK_OUTSTANDING).

## 9. Adding an agent: new or imported (James, 14 Oct 2026)

Every agent arrives through one **Add agent** flow with two sources:

- **New:** sign in with ChatGPT, Claude, or Wizard Private AI. First setup asks only this, with a small "Already have an agent? Bring it in" link. On a Mac with Hermes installed the link is offered more prominently.
- **Import:** an existing agent comes in with its memory, skills, history, settings and sign-ins. **Hermes first**, built on stock `hermes backup` / `hermes import`. ChatGPT and Claude data exports come later as conversation history for a new or existing agent, searchable through Agent Search.

Any agent can be **main** (the default for new chats, voice and schedules); the others are secondary and are picked per thread. Connecting an agent that keeps running on another machine is **not** being built: an external agent breaks the box's isolation, and alongside mode already covers agents on a VPS.

**Import rules (Hermes):**

- The archive is checked (no absolute or parent paths) and per-machine files stay out: `bin/` (a Mac's binaries), logs, runtime state, caches, locks, and Wizard's own plugins.
- Wizard's wiring wins over the imported settings: the terminal in the box, the `wizard` app gateway, Wizard's plugins and system skills, and the API server the Agent Service uses.
- **One active copy.** Messaging platforms come in with `enabled: false` (credentials kept for later) and every scheduled job comes in paused, so the imported copy never answers a chat or runs a job the original still owns.
- The box's previous agent is saved first; **undo** puts it back exactly. The original agent on the other machine is never touched.
- The archive holds sign-ins: it travels over the host–box channel (vsock on Mac), never through the shared Files folder, and is deleted when the import ends.

**Packages:** an **agent package** is one agent's folder (for Hermes, its own backup zip). A **Wizard package** is every agent package plus app data, settings, schedules and Files. Import, backup/restore and moving a box to another machine use the same two formats.

## Not in this spec

- **Keys and the Key Vault:** a separate proposal (Wizard Topics thread, 11 Oct): an egress proxy that holds the real keys so agents only hold stand-ins.
- **AI Accounts:** the existing system app; Claude subscription sign-in is live, with ChatGPT and API keys next.
- **Approval policy** (which actions need the owner's yes, across agents): Wizard-level too, still unowned. Listed in WORK_OUTSTANDING.

## Done when (first version)

1. A box runs two agents (stock Hermes and a second Hermes or Pi), each in its own `~/.wizard-os/agents/<id>/`, and nothing in either harness was changed.
2. With no grant, agent B's `sessions_search` and `skills_search` return nothing from agent A. After the owner grants `search`, they return A's results labelled with A's name, and the read is logged.
3. B adapts one of A's skills into its own skills folder with `adapted_from`, and A's skill is unchanged.
4. A schedule created in the Wizard UX runs on the agent it names and posts to its thread; `hermes cron list` on that box is empty.
5. The Wizard thread list shows both agents' threads, with no direct `state.db` read left in the Agent Service.
