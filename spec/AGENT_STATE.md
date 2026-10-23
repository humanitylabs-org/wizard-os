# Agent state: what each agent learns, and who can read it

**Status: proposed (James, 11 Oct 2026; DECISIONS #43–#49). #43 (one folder per agent) and #48 (agent adapter) approved 14 Oct; the MVP contract is [AGENTS.md](AGENTS.md).** Builds on the agent bridge (#40, [AGENT_BRIDGE.md](AGENT_BRIDGE.md) in PR #12) and the permissions draft ([PERMISSIONS.md](PERMISSIONS.md) in PR #6).

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

`privacy` is `private` (the model runs locally or in a confidential provider such as Tinfoil) or `standard`. A private agent is sealed: no other agent can read it, and it shares only by publishing a copy the owner approves (section 4, DECISIONS #59).

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
- **Private agents are sealed (#59, James 14 Oct; replaces the earlier "no hard wall" rule).** No grant can name a private agent as its source, for any reader, standard or private. A private agent shares by publishing a copy, item by item, after the owner approves it in that agent's chat; moving harness works the same way. Grants between standard agents keep the rules above.
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

- Check every archive member before extraction: no absolute/parent/Windows paths, aliases, symlinks or special files; bound members and uncompressed size. Machine-local `bin/`, code/venvs, logs, runtime state, caches, locks and old Wizard plugins stay out. Profiles, hooks and executable extensions do not silently boot as additional copies.
- Wizard's wiring wins: local terminal in the container, new per-agent API/gateway keys, the `wizard` app gateway, reviewed Wizard plugins/system skills and the API used by Agent Service. Preserve the imported memory engine, its settings/fact store, identity, skills, provider login and history; do not regenerate a fresh agent's config over them on start/apply.
- **One active copy.** Cross-machine imports default to paused messaging and cron; plaintext originals/credentials are preserved outside the running home for undo. Until #47's Wizard scheduler is live, an explicitly approved same-host **take-over** stops source writers first and keeps Hermes's own cron/messaging inside the container. Never copy the jobs into both schedulers. The importer does not implement or change #47.
- Save the box's previous/default agent first; undo stops only the labelled imported runtime, restores original config/cron bytes, reverses the rename, restores routing if it changed and resumes only source services recorded active. A conflicting pointer or concurrent settings edit fails closed. The original on another machine is never touched.
- Sign-ins travel over the trusted host–box channel (vsock on Mac), never Files. Delete filtered transport archives and temporary credential copies on completion/undo. A caller-owned original backup remains the owner's deletion responsibility; never delete an arbitrary input file silently.

### Outside the home: scan → approve → apply → undo

Stock Hermes backup covers its home, not its whole working environment. Begin with an **owner-operated CLI** in Agent Service's ops/runtime tree (that component already owns container records and lifecycle authority); keep planning/validation in a library for a future owner API/Add-agent UI. Do not give import/Docker/shell authority to an agent-facing tool or the HTTP Service process.

1. **Read-only scan.** Report logical bytes, sessions, memory backend, skills, plugins/MCP commands, cron enabled/count, platforms and credential **names only**. Find outside absolute/tilde references in config, cron, skills, memory, identity/context and plugin configs. Classify each as `folder`, `credential`, `tool`, `host-service` or `unknown`, with source file/line and an explicit proposal (`mount rw`, `mount ro`, `carry secret`, `available in image`, `missing`, `leave behind`). Unknowns are not approved mounts.
2. **Approve exact selections.** Bind source identity/critical configuration, image, network/route, port, mode, dependency actions and approved executable/plugin/credential names to a plan digest. No secret values in the plan, logs, evidence or subprocess arguments. Source plugins do not get to bootstrap host commands just because they were present in a backup. Retain known memory-provider configuration separately from executable-plugin activation.
3. **Same-host means rename, never a full database copy.** Require an explicitly approved move, a same-filesystem destination and a stopped-writer census. Leave a plain pointer directory, not a symlink into the new home. Default path-preserving mode presents `HOME`, `HERMES_HOME` and approved folders at their original absolute container paths; skills and prompts need no rewriting. A reduced rehearsal can explicitly bind its physical copied home to that original **logical** home. Block extra mounts over either logical/physical agent home. Path rewriting is not part of this version.
4. **Outside dependencies are individual grants.** Copy narrowly scoped credentials read-only or mount reviewed project folders at the same logical path. Never mount an owner home wholesale, a service socket, the Wizard root (or an ancestor/alias/nested tree containing it), or another agent. No Docker socket, host PID/network namespace, host shell backend or App Manager install power. A borrowed SSH identity that can SSH back into the box would undo the seal; provision a scoped build-host identity instead. Host maintenance belongs to a separate recovery agent.
5. **Stock runtime, explicit deltas.** Cross-host data runs through stock `hermes import` as the agent user in an isolated helper; no runtime source patch. Pin the actual source/image revisions and inventory missing tools. If a workbench image is needed, package it on a remote build worker, not the control plane. Record Python/SQLite and plugin/tool differences rather than declaring parity from a version string. New Wizard assets are reviewed digest-pinned packages, not inherited old wiring.
6. **Contain untrusted homes on lifecycle/undo too.** Reject agent-planted symlinks/FIFOs/shared hardlinks in managed files or their parents before any host helper reads/writes them. Stop the agent before merging Wizard-owned fields; preserve identity/memory/provider state. Imported non-compose runtimes must fail closed when they cannot provide a stopped/offline census, never issue a false compose seal.
7. **Rehearse, then select default separately.** Hidden test sessions must follow create → PATCH hidden:true → GET literal true before input. Check history/facts/skills, actual tools/SSH/project writes, private-home/socket exclusion and undo/agent-list readback. A full live home may be much larger than the disk or a 2 GB fixture; report exactly which roots and recent sessions were omitted. A bounded partial rehearsal, unavailable `gh`, failed SSH or failed model turn does not satisfy full acceptance. Do not copy/hardlink a large live database or touch live launchers to make a rehearsal pass.
8. **Cutover is a separate owner-authorized window.** `agents.default_agent_id` changes only after health/tool checks; the previous main is `role:recovery`. That label alone does not provision a recovery runtime when its original home was moved. Verify a separately runnable recovery home first. Journal routing snapshots for undo. No automatic cutover from apply, rehearsal or a successful image build.

**Packages:** an **agent package** is one agent's folder (for Hermes, its own backup zip). A **Wizard package** is every agent package plus app data, settings, schedules and Files. App data is not silently bundled/mounted through an agent package. Import, backup/restore and moving a box to another machine use these two boundaries.

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
