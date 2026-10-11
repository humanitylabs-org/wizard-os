# Agent bridge: how every agent on a box knows Wizard OS and uses its apps

**Status:** proposed by Archimedes, 11 Oct 2026 (DECISIONS #40). Owner: Archimedes (Agent Service items moved from Jan to Archimedes by James, 11 Oct).

## The problem

The first release end-to-end test (Telos, 10 Oct) passed only because the agent spent about 4 minutes digging through the box: it grepped skills, read `apps.json` by hand, found the skill file with `find /`, and wrote its own MCP client. On a fresh Hermes, or on a weak model, step 3 fails. The per-run "you are inside Wizard OS" block (wizard-agent-service#2) tells the agent the apps exist, but it hands over URLs and file paths, and a weak model has to turn those into working calls itself.

**Rule:** an installed app must reach the agent as **real callable tools plus a short, fixed orientation**. The agent should never need to read files, write clients or guess. If DeepSeek Flash can't do it on the first try, the bridge is wrong.

## The design: four layers, one source (`apps.json`)

### 1. Tools: one `wizard` MCP gateway in the Agent Service (all harnesses)

- The Agent Service serves one MCP endpoint, `/wizard/mcp` (streamable HTTP, box-only, token). It reads `apps.json` and proxies every running app's MCP tools as its own.
- Tool names are `<app>__<tool>` (for example `defleur_video__start_edit`). Each description starts with the app and the job it does: `[DeFleur Video · short-form video, video editing] Start an edit…`.
- It adds one meta tool, `wizard_apps`: the installed apps, what each is for, and its status, so "what can you do?" has a real answer.
- On an install, uninstall or restart it sends `notifications/tools/list_changed`. Hermes already re-fetches tools on that notification and refreshes them between turns, so new apps show up on the next message without a restart or a config edit.
- The agent's config gets **one** MCP entry, written once at install (`mcp_servers.wizard`). It never changes per app. Claude Code, Codex and any MCP-speaking agent use the same entry.
- It's the one place the agent reaches apps. That makes it where the app-permission grants (PERMISSIONS.md, agent → app) are enforced later, and where every app call is logged.

### 2. Orientation: one Wizard OS kernel text, rendered by the Agent Service

- `GET /wizard/v1/agent-context` returns the kernel: you are this owner's agent inside Wizard OS; how the box works (files root at `media/`, apps do jobs, `wizard__*` tools); the installed apps grouped **by job** ("short-form video → DeFleur Video: `defleur_video__*`"); and the rules (prefer an installed app for its job, follow its skill, save only pointer skills).
- It's plain, short (under 2,500 characters for 20 apps) and imperative. It's written for the weakest supported model, not the strongest.
- One renderer, many deliveries:
  - **Hermes, every surface** (Wizard, Telegram, CLI, cron): a small Hermes plugin, `wizard-os`, registers the kernel as a system-prompt section through Hermes' stock plugin API (`register_system_prompt_section`). It renders from `apps.json` locally, so it works when the Agent Service is down. This is the "lives in Hermes' own files" option done without touching the owner's `SOUL.md`, memory or Hermes core. Removing the plugin removes it cleanly.
  - **Through the Agent Service** (any harness): the per-run `instructions` carry the kernel when the harness has no adapter. When the Hermes plugin is installed (`agent.adapter: hermes-plugin` in Wizard settings, set by the installer), the per-run block carries only what changed since the thread started (apps installed mid-thread), so the kernel isn't sent twice.
- The kernel goes above the owner's own context in effect, though not above Hermes' safety core: Wizard OS says what the box is, and the owner's SOUL says who the agent is.

### 3. Skills: app skills appear as Hermes skills

- The App Manager already writes each app's `SKILL.md` under `~/.wizard-os/skills/<id>/` (keeping them intact is wizard-app-manager#10).
- The installer adds that folder to `skills.external_dirs` (stock Hermes config). Every app skill then shows in the skills list and loads with `skill_view`, the same way the owner's skills do.
- Pointer skills: the Agent Service generates one tiny skill per job in `provides` ("short-form video → use DeFleur Video, `defleur_video__*`, read its skill") into the same folder, rebuilt on every `apps.json` change. That way the job word the owner actually says matches a skill description.

### 4. Proof: the weak-model gate

A release can't ship unless this passes on a fresh box:

- Eight plain requests that name the job, not the app or MCP ("make a short from the clip in my Files", "transcribe this recording", "what apps do I have?" …), on a **flash-tier model** (GLM 5.3 Flash, already routed; DeepSeek Flash where a route exists) and on the default model.
- Pass = the first app-relevant tool call is the right `<app>__<tool>` in at least 7 of 8, with zero file-system searches for app details, on both models.
- It runs in `wizard-os/tools/tests/agent_bridge_gate.py` against a real Hermes, a real Agent Service and a real installed app.

## Installing over an existing Hermes ("alongside" mode, James 11 Oct)

`os.sh` detects an existing Hermes (`~/.hermes/config.yaml` plus a running API server) and offers **alongside** mode. Wizard OS runs next to the owner's Hermes and never moves or migrates it:

1. Install Runtipi with the Wizard App Manager (unchanged), on ports that don't fight an existing web server.
2. Run the Agent Service + Wizard UX against the owner's Hermes API (`HERMES_ORIGIN=http://127.0.0.1:8642`) instead of the `hermes-agent` app. The `agent` slot is marked "external: host Hermes".
3. Link, with three stock-config edits, each recorded in `~/.wizard-os/linked.json` so `wizard unlink` reverses exactly them:
   1. `mcp_servers.wizard`
   2. `skills.external_dirs += ~/.wizard-os/skills`
   3. `plugins.enabled += wizard-os`
4. Leave alone: `SOUL.md`, memory, sessions, other skills, providers and every existing `mcp_servers` entry.
5. Prove it with `wizard doctor`, which runs one gate request.

Migrating the owner's Hermes into Wizard OS (option B) comes later, as its own command.

## What this replaces

- WORK_OUTSTANDING "apps.json reader: register each app's MCP with the agent". Each app is no longer registered per app: one gateway entry covers all of them.
- The URL- and path-heavy app block in wizard-agent-service#2. It becomes the kernel above.
