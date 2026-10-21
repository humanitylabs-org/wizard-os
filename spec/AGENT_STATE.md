# Agent state: what each agent learns, and who can read it

**Status: proposed (James, 11 Oct 2026; DECISIONS #43–#49; section 3 amended by #77, 18 and 21 Oct). #43 (one folder per agent) and #48 (agent adapter) approved 14 Oct; the MVP contract is [AGENTS.md](AGENTS.md).** Builds on the agent bridge (#40, [AGENT_BRIDGE.md](AGENT_BRIDGE.md) in PR #12) and the permissions draft ([PERMISSIONS.md](PERMISSIONS.md) in PR #6).

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
- **Outside the user files root.** `media/` is mounted into every app (SYSTEM_APPS "one file root"), so agent state there would be readable by DeFleur, the browser or any other app. `~/.wizard-os/agents/` is mounted only into its own agent and, read-only, into Agent History (section 3). The trimmer that shortens an agent's store runs with that agent's own access, not History's.
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

`privacy` is `private` (the model runs locally or in a confidential provider such as Tinfoil) or `standard`. A private agent is sealed: no other agent can read it, and it shares only by publishing a copy the owner approves (section 4, DECISIONS #59).

## 2. Skills: each agent keeps its own, and can look up the others'

- **Each agent writes only its own skills.** Skills are written for one harness's tools (`skill_view`, `delegate_task`, `~/.hermes/...`). A skill shared by every agent would be wrong for most of them.
- **Wizard system skills** stay in `~/.wizard-os/skills/` (#40): app skills from the App Manager plus pointer skills from the Agent Service. Every agent reads them, read-only (Hermes through `skills.external_dirs`). We call them **system skills**, not "shared", because Wizard writes them and no agent edits them.
- **Other agents' skills are looked up, never injected.** No agent's skills list ever includes another agent's skills by default. With a grant (section 4), an agent can call Agent History:
  - `skills_search(query, agents?)` returns names, descriptions and which agent and harness wrote each.
  - `skill_read(agent, name)` returns the skill. It starts with: "Written by *agent* for the *harness* harness. Tools and paths it names may not exist for you. Adapt it into your own skill before relying on it."
- **Adapting is the agent's job.** If the skill is useful, the reading agent writes its own version with its own skill tooling and records `adapted_from: <agent>/<skill>` in the frontmatter. The original is never edited.

When and how often agents should look up another agent's skills is left to usage. This spec only provides the ability.

## 3. Agent History: every agent's permanent record, and the only reader across agents

**Agent History** (`wizard-agent-history`, slot `agent-history`, `system: true`) is a headless system app with two jobs. Renamed from Agent Search (James, 18 Oct, #77: "clear rather than clever"); "archive" already means a closed thread in Chats, so it is not used for this app.

1. **Keep.** It holds a permanent copy of every agent's full history, so each agent's own store stays bounded.

**The promise to the owner: your history is never lost, and your Wizard never fills itself up.** Without a rule, an agent's store grows without limit (on James's box, about 11 GB a month). Backups and restores slow down, search gets slower and cluttered with machine output, big-store maintenance gets riskier, and eventually the disk fills. The harness's own fix, a timed prune, deletes history. History is how a Wizard box avoids both outcomes.
2. **Look up.** It is the only thing that reads one agent's state on behalf of another, and only under grants.

### 3.1 Keeping

- **Copies each agent's sessions into its own store, daily, after the box backup.** Hourly is not needed until something reads History often; the backup already bounds the loss window. A small reader per harness reads the agent's store read-only and adds only what changed since the last pass. First readers: `hermes-state-db` (sessions), Hermes skills folder, `hermes-holographic` (facts), `pi-jsonl` (sessions), Pi skills folder.
- **Keeps everything readable:** the owner's messages, replies, reasoning, tool calls and tool output. A year of an agent's work, including how it reasoned and which tools it used, is the record an owner would use to tune or train an agent on their own workflows. Provider-encrypted reasoning (opaque blobs only the provider can decrypt) is left out; it stays in the box backup.
- **Monthly files per agent:** `~/.wizard-os/agent-history/<agent>/<YYYY-MM>.db`, each with its own search index. A month is **sealed** once it is past and fully copied; sealed months never change, so the box backup uploads each one once. A row the agent writes later with an old date, or a newer version of a sealed row, goes into the current month; the sealed copy stays as the earlier version. `storage_path` (owner setting) can put them on a second disk.
- **Conversation export:** `~/.wizard-os/agent-history/<agent>/conversation.jsonl`, the owner's messages and the agent's final replies only, all time. It is small, and it is what moves to a new box, seeds an imported agent, or feeds training.
- **What leaves the agent's store, and when.** One owner setting for every agent, `live_days`, default 30.
  - **Machine sessions** (scheduled jobs, helper agents, recovery and maintenance runs) leave the agent's store once they are older than `live_days`. History first **releases** each session: it checks every row against its own copy and records that it keeps the session. The harness's own prune command then removes exactly those sessions, at a quiet moment in the maintenance window, and History's next copy must report no deletions. A helper session is released only when no owner thread still links to it.
  - **The owner's conversations stay in the agent's store at every age** until Chats reads old threads from History (section 3.2). Then they follow the same rule, so the store stops growing for good.
  - **Nothing leaves without a verified History copy.** The harness's built-in timed auto-prune stays off on a Wizard box, because it deletes.
  - **No store rewrites.** History does not rebuild an agent's store to strip old tool output or reasoning from threads that are still visible. Measured on James's box, that saved about a quarter of the file once, needed the agent stopped every time, and changed how old replies display. The bulk is the harness's own compaction leftovers, which belong upstream.
- **Disk forecast.** History reports the agent store's growth and the days of disk left, and alerts the owner when that forecast drops below four months.
- **Private agents:** History keeps a private agent's record for that agent and its owner. It never serves it to another agent (#59), and never sends it off the box except inside the encrypted box backup.

### 3.2 Looking up

- **Search covers the conversation by default** (owner messages and agent replies). `deep: true` also searches reasoning, tool calls and tool output, for questions like "how did we fix this last month?".
- **Search method:** the same ones Hermes uses today. Its session search is SQLite full-text search, and its fact memory is the holographic provider (both MIT). We vendor them so every agent gets Hermes-quality recall without running Hermes.
- **MCP tools** (through the `wizard` gateway, #40): `sessions_search` (with `deep`, `after`, `before`), `session_read`, `facts_search`, `skills_search`, `skill_read`, `agents_list`. Every result names the source agent and month.
- **How an agent uses it.** An agent searches its own live store first, as it does today. A Wizard system skill tells it to call History for anything older than `live_days` or from another agent. **Own data is always allowed** without a grant (useful for harnesses with no session search of their own, such as Pi).
- **The Wizard thread list reads from here too.** The Agent Service's thread list, archive and status checks move from reading Hermes' `state.db` directly to the agent adapter (#47) and Agent History, so a second agent's threads, and threads older than the live window, can appear in the same list.

Why not give agents each other's database files: SQLite with a write-ahead log across containers risks corruption. The formats are each harness's private schema and change with updates. And a file grant is all-or-nothing and invisible. Why not each harness's own MCP: Hermes has one (`hermes mcp serve`), Pi has none, the shapes differ, and the private agent's own endpoint would be a second door to guard. Why not let each harness prune on its own clock: a harness prune deletes, and History would lose whatever it had not yet copied.

## 4. Grants: the owner decides who reads what

A grant is one direction, **reader agent → source agent**, with a scope per kind:

```json
{"from": "pi-trial", "to": "hermes", "sessions": "search", "skills": "read", "memory": "none",
 "subjects": ["Wizard OS"], "approved": "owner", "created_at": 1791700000}
```

- Scopes: `none`, `titles` (thread titles and dates), `search` (search results with snippets), `read` (whole sessions or skills).
- `subjects` optionally limits it to threads in those subjects.
- **Default: no grants.** Installing a second agent gives it nothing from the first. The owner turns it on per pair, in the Apps screen or by asking an agent that holds the "manage grants" right (owner-approved).
- **Private agents are sealed (#59, James 14 Oct; replaces the earlier "no hard wall" rule).** No grant can name a private agent as its source, for any reader, standard or private. A private agent shares by publishing a copy, item by item, after the owner approves it in that agent's chat; moving harness works the same way. Grants between standard agents keep the rules above.
- Stored alongside app grants in `wizard-grants.json` (PERMISSIONS.md) as `kind: "agent-data"`, so one file and one screen show every permission on the box. Agent History enforces them on every call and logs each cross-agent read (reader, source, kind, scope, no content).

## 5. Memory: opinionated by default

- **Each agent keeps its own memory engine.** Memory is wired into the harness's turn loop (what gets recalled into the prompt, when facts are written), so we don't replace it. Agent History reads it across agents, under grants.
- **One opinionated default.** The Wizard OS Hermes app ships with the holographic fact store turned on (`memory.provider: holographic`), the setup we run ourselves and install for clients. Owners can change it, but nobody has to choose among Hermes' eight memory backends to get started.
- **Same engine at Wizard level.** Agent History uses that same holographic method for facts, so a lean agent with no memory of its own still gets good recall through Agent History.
- **Later, optional:** a `wizard` memory provider plugin (stock Hermes plugin API) could point Hermes' memory at Agent History instead of its own store. Only if usage shows one shared memory beats per-agent memory.

## 6. Schedules: one Wizard scheduler

- **The Agent Service owns every schedule on the box.** A job is: when (cron or interval, owner's timezone), which agent, which model, a prompt or skill, which thread gets the result, and on/off.
- **One list in the Wizard UX** (Settings → Schedules, and the agent can manage it through the `wizard` gateway: `schedules_list/create/update/pause`).
- **Agents don't keep their own cron on a Wizard box.** The installer turns Hermes' cron scheduler off when the Wizard scheduler is active. Install-alongside mode imports existing Hermes cron jobs once, read from `jobs.json`, and offers to switch them over.
- **Blueprints become schedule templates.** The useful ideas from Hermes automation blueprints (morning brief, topic digest, weekly review) ship as Wizard schedule templates, and an app's skill can carry its own template offered at install.

## 7. The agent adapter

The Agent Service talks to each agent through one small call set: **run, events, steer, approve, stop, list threads, read thread, run status**.

- **Hermes** implements it over its HTTP API (`/v1/runs`, `/api/sessions`). Today the Agent Service still reads Hermes' `state.db` directly for six things: the thread list, the archive, the "is a turn running" check, abandoned-run outcomes, active sessions and helper follow-through. Moving those onto the adapter is owned by the agent-bridge work (#40). Anything Hermes' API doesn't expose falls back to Agent History.
- **Pi** would implement it over its RPC mode (JSON over stdin/stdout).
- **Agent-specific runs** carry `agent: <id>`, so a thread and a schedule can each name the agent they use.

## 8. Lean agents

Weak, cheap or private models do well on short jobs and poorly on long multi-step builds. From 692 Wizard threads over 30 days: 30% needed 20 or fewer tool calls, and 45% needed more than 60.

- **A lean agent** runs a small profile: few tools, the Wizard kernel, system skills, a skill search tool instead of a full skills list. It handles quick questions, drafts, summaries, single app actions, voice quick-asks and fetch-and-summarise schedules.
- **The frontier agent** keeps builds, releases, browser work with credentials, research that needs checking, fan-out to helper agents, and anything with outside effects.
- **Every workflow moved into an app tool moves work into the lean tier.** One `defleur_video__start_edit` call suits a flash model; sixty terminal steps doing the same job don't.
- **Which harness for the lean tier** (a slim Hermes profile, Pi, or another) is decided by a bake-off once a containerised box exists (WORK_OUTSTANDING).

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
6. Agent History holds every Hermes session; machine sessions older than `live_days` are gone from the Hermes store with History's next copy reporting no deletions; every owner conversation still opens in Chats; a search for something said three months ago returns it through `sessions_search`; and restoring the box backup brings back both.
