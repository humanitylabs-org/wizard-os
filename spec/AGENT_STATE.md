# Agent state: what each agent learns, and who can read it

**Status: proposed (James, 11 Oct 2026; DECISIONS #43–#49; section 3 amended by #102, 18, 21 and 25 Oct). #43 (one folder per agent) and #48 (agent adapter) approved 14 Oct; the MVP contract is [AGENTS.md](AGENTS.md).** Builds on the agent bridge (#40, [AGENT_BRIDGE.md](AGENT_BRIDGE.md) in PR #12) and the permissions draft ([PERMISSIONS.md](PERMISSIONS.md) in PR #6).

Hermes is the agent today. A box will often run more than one agent: a frontier Hermes for building, a lean private agent on a Tinfoil model, a Pi or Claude Code agent someone is trying out. Each agent learns as it works. It writes skills, keeps memories, and builds up session history.

Wizard OS owns **where** that state lives and **who** may read it. The agent owns **how** it uses its own state. That keeps three promises:

- **No lock-in.** Switching agents, or running two side by side, doesn't throw away what the first one learned. The new agent can look it up.
- **Owner-controlled sharing.** Standard agents read each other on demand by default. The owner can silo any one; private agents stay sealed.
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
- **Other agents' skills are looked up, never injected.** No agent's skills list ever includes another agent's skills by default. Under section 4 permissions, an agent can use the Agent Service gateway for skills and memory. Session retrieval belongs to Agent History (#45/#102):
  - `skills_search(query, agents?)` returns names, descriptions and which agent and harness wrote each.
  - `skill_read(agent, name)` returns the skill. It starts with: "Written by *agent* for the *harness* harness. Tools and paths it names may not exist for you. Adapt it into your own skill before relying on it."
- **Adapting is the agent's job.** If the skill is useful, the reading agent writes its own version with its own skill tooling and records `adapted_from: <agent>/<skill>` in the frontmatter. The original is never edited.

When and how often agents should look up another agent's skills is left to usage. This spec only provides the ability.

## 3. Agent History: every agent's permanent record and its session search

**Agent History** (`wizard-agent-history`, slot `agent-history`, `system: true`) is a headless system app with two jobs. Renamed from Agent Search (James, 18 Oct, #102: "clear rather than clever"); "archive" already means a closed thread in Chats, so it is not used for this app.

1. **Keep.** It holds a permanent copy of every agent's full history, so each agent's own store stays bounded.
2. **Look up.** It owns session search and reading, for an agent's own history and, under section 4, other standard agents'. Memory, skills and notes are read through the Agent Service gateway (section 4); there is no second session reader and no raw `state.db` access.

**The promise to the owner: your history is never lost, and your Wizard never fills itself up.** Without a rule, an agent's store grows without limit (on James's box, about 11 GB a month). Backups and restores slow down, search gets slower and cluttered with machine output, big-store maintenance gets riskier, and eventually the disk fills. The harness's own fix, a timed prune, deletes history. History is how a Wizard box avoids both outcomes.

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
- **MCP tools** (through the `wizard` gateway, #40): `sessions_search` (with `deep`, `after`, `before`) and `session_read`. Every result names the source agent and month. Memory, skills and notes use the gateway's `wizard_agents__*` tools (section 4).
- **How an agent uses it.** An agent searches its own live store first, as it does today. A Wizard system skill tells it to call History for anything older than `live_days` or from another agent. **Own data is always allowed** without a grant (useful for harnesses with no session search of their own, such as Pi).
- **The Wizard thread list reads from here too.** The Agent Service's thread list, archive and status checks move from reading Hermes' `state.db` directly to the agent adapter (#47) and Agent History, so a second agent's threads, and threads older than the live window, can appear in the same list.

Why not give agents each other's database files: SQLite with a write-ahead log across containers risks corruption. The formats are each harness's private schema and change with updates. And a file grant is all-or-nothing and invisible. Why not each harness's own MCP: Hermes has one (`hermes mcp serve`), Pi has none, the shapes differ, and the private agent's own endpoint would be a second door to guard. Why not let each harness prune on its own clock: a harness prune deletes, and History would lose whatever it had not yet copied.

## 4. Sharing: the owner decides who reads what

- **Standard defaults: read and shared.** New standard agents and the main agent default to `permissions.other_agents: "read"` and `permissions.shared_with_agents: true`. This amends #46 for standard agents only. Existing stored `other_agents` values are not migrated. Missing `shared_with_agents` means true for standard, false for private.
- **Opt-out silo.** The owner may set `shared_with_agents: false` at any time. This agent disappears from every reader's readable sources, including explicit grants (`409 check: "agent.not_shared"`). Its own `other_agents` stays independently editable. Normally a silo also uses `none`, but that is not forced.
- **Read covers bounded, read-only files.** Hermes `memories/MEMORY.md`, `memories/USER.md`, `SOUL.md` labelled "persona (read-only)", skills list and each `SKILL.md`, and an optional owner-visible notes folder declared by `notes_dir` relative to home (for example `wiki`). Never `.env`, credentials, auth/key/config files or raw databases. Realpath must stay inside the source home; no dotfiles or escaping symlinks.
- **Look up, never inject.** Another agent's memory, persona and skills are read only when relevant, never injected into the reader's default prompt. Each agent is the sole writer of its memory, skills and notes. A reader keeps an adapted note in its own store with `adapted_from: <agent>/<item>`, never copy-edits the source.
- **Gateway levels.** `none` gives no sources; `titles` lists agents only; `search` also lists skills and notes; `read` permits content reads. Tools on `/wizard/mcp`: `wizard_agents__list`, `wizard_agents__memory_read(agent)`, `wizard_agents__skills_list(agent)`, `wizard_agents__skill_read(agent,name)`, `wizard_agents__notes_list(agent)` and `wizard_agents__notes_read(agent,path)`. Hermes prefixes these with `mcp__wizard__`. Every call rechecks permissions.
- **Explicit grants** are reader → source, with `titles`, `search` or `read` scope. Grants may extend access to shared standard sources, never bypass a silo. Every cross-agent read logs reader, source, kind and scope, never content.
- **Private agents remain sealed (#59).** No grant can name a private source, for any reader. `shared_with_agents` is always false for private agents, even in forged stored records. Setting true returns 409 `agent.private_sealed`. A private agent shares only by publishing exact copies the owner approves item by item, including when moving harnesses.
- **Sessions stay with Agent History.** Full transcripts and history search arrive through Agent History under the same `other_agents` level, silo and private seals; not through these file tools.

## 5. Memory: opinionated by default

- **Each agent keeps its own memory engine.** Memory is wired into the harness's turn loop (what gets recalled into the prompt, when facts are written), so we don't replace it. The gateway reads only the always-loaded files listed in section 4. Other memory engines are not exposed by these tools.
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

**Packages:** an **agent package** is one agent's folder (for Hermes, its own backup zip). A **Wizard package** is every agent package plus app data, settings, schedules and Files. App data is not silently bundled/mounted through an agent package. Import, backup/restore and moving a box to another machine use these two boundaries. An **agent template** (idea, [AGENT_TEMPLATES.md](AGENT_TEMPLATES.md)) is the shareable subset of an agent package: soul, skills and recommendations, with no memory, history or sign-ins.

## App notebook reads (proposal, not an approved exception)

[App reads of declared agent notebooks](APP_AGENT_NOTEBOOKS.md) proposes a generic, explicitly owner-granted read-only resource layered over normal per-app identity. It keeps private/hidden/recovery agents excluded and keeps presentation in apps. It does not make an ordinary app connection into agent-state authority or amend sealed private agents (#59); contract review and an authenticated consuming-app handoff are required before implementation merges or activation.

## Not in this spec

- **Keys and the Key Vault:** a separate proposal (Wizard Topics thread, 11 Oct): an egress proxy that holds the real keys so agents only hold stand-ins.
- **AI Accounts:** the existing system app; Claude subscription sign-in is live, with ChatGPT and API keys next.
- **Approval policy** (which actions need the owner's yes, across agents): Wizard-level too, still unowned. Listed in WORK_OUTSTANDING.

## Done when (first version)

1. A box runs two agents (stock Hermes and a second Hermes or Pi), each in its own `~/.wizard-os/agents/<id>/`, and nothing in either harness was changed.
2. Standard B reads standard A on demand by default, with labelled results and content-free logs. Siloing A removes it immediately, including stored grants. Private sources stay sealed. Session retrieval is verified separately through Agent History.
3. B adapts one of A's skills into its own skills folder with `adapted_from`, and A's skill is unchanged.
4. A schedule created in the Wizard UX runs on the agent it names and posts to its thread; `hermes cron list` on that box is empty.
5. The Wizard thread list shows both agents' threads, with no direct `state.db` read left in the Agent Service.
6. Agent History holds every Hermes session; machine sessions older than `live_days` are gone from the Hermes store with History's next copy reporting no deletions; every owner conversation still opens in Chats; a search for something said three months ago returns it through `sessions_search`; and restoring the box backup brings back both.
