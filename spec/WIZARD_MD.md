# wizard.md — Wizard app format, v0.2 (draft)

Status: draft for James, Jan and Miguel. Source: Wizard Dev Council, 9 Oct 2026, full transcript.

- "We make any open source GitHub repo compatible if … it has a WizardMD" (James)
- "the app has to ship with an MCP and with a skill" (Miguel)
- "any wizard can verify a WizardMD. Does it qualify? … Pass, pass, pass" (James)
- "it's just checks rather … what I would not want is any sort of human review" (Miguel)
- "each app its own repository tagged with wizard AI" + "monitor all GitHub repositories with this tag and include them in a wizard apps interface that is installable using RunTP" (James/Jan)

A repository is a Wizard app when its root contains a `wizard.md` that passes the checker. The GitHub topic `wizard-os-app` (proposed 9 Oct 2026; `wizard-ai` still searched during the transition) makes it discoverable; it is not proof of compatibility (the topic is public and already used by unrelated repos). No human review.

## Changes from v0.1

1. `provides:` — capability slots the app fills (`video-editing`, `files`, `transcription` …). This is how the agent picks between several apps for the same job (James: "for shorts I want the DeFleur pipeline, for long-form podcasts this pipeline") and how system core apps become swappable ("these are alternatives to fit into those slots").
2. `recommends:` — the agent/model the app is tuned for. The shipped skill runs the check first and warns, then proceeds ("intended to be used with Opus 5.5 and Hermes … results may vary, do you want to proceed?").
3. `system: true` is a role, not a separate format: system core apps are ordinary Wizard apps that the OS installs by default, hides from the launcher and tells the agent about. Any of them can be replaced by another app that `provides` the same slot.
4. Pointer-skill rule (below): the Agent Service, not the app, owns the generic "when asked to do X, use app Y" skill.
5. The topic alone never makes an app compatible.

## Shape

`wizard.md` = YAML front matter (machine contract) + Markdown body (what the app does, for people and agents).

```yaml
---
wizard: 0.2                 # spec version (0.1 still accepted)
id: defleur-video           # lowercase a-z0-9-, unique in a catalog
name: DeFleur Video
type: service               # agent | service | view | external
version: 0.6.5
summary: Edit a talking-head video into a finished vertical short.
license: MIT
source: https://github.com/humanitylabs-org/defleur-video

runtime:                    # how the App Manager installs it (Runtipi today)
  kind: runtipi
  config: runtipi/config.json
  compose: runtipi/docker-compose.yml

mcp:                        # required for agent, service, external; optional for view
  path: /mcp
  port: 8787
  transport: streamable-http

skill: skill/SKILL.md       # required for every type except view; ships with the app

view:                       # required for view; optional for others
  path: /                   # opened by Wizard UX at /apps/<id>/
  port: 8080

provides: [video-editing, short-form-video]   # capability slots (optional, recommended)
recommends:                 # optional; the skill checks this first and warns
  agent: hermes
  model: claude-opus-5-5

system: false               # true = installed with Wizard OS, hidden from the
                            # launcher, known to the agent, replaceable by any
                            # app that provides the same slot

uses: [transcriber, browser, files]   # other app ids or slots it calls
needs: []                   # device capabilities: mic, system-audio, camera,
                            # notifications, files, credentials:<provider>
health: /healthz
---
```

## Rules the checker enforces

1. Front matter parses and `wizard` is a known spec version (0.1, 0.2).
2. `id` matches `^[a-z0-9][a-z0-9-]{1,40}$`; `type` is one of the four types.
3. `version` is semver-ish; `summary` ≤ 140 characters; `license` and `source` present.
4. `runtime.config` and `runtime.compose` exist in the repo.
5. `mcp` present for agent, service and external; `skill` present for every non-view; the skill file exists and has `name` + `description` front matter.
6. `view` present for type view.
7. Every `needs` entry is from the known capability list.
8. `provides` entries, if present, are slot ids (`^[a-z0-9][a-z0-9-]{1,40}$`).
9. Optional online check (`--github owner/repo`): the repo has the `wizard-os-app` or `wizard-ai` topic.

## Skills: shipped skill + pointer skill

- The app ships its own full skill (`skill:`). The agent never writes that skill from scratch. Miguel's demo showed the failure mode: without a shipped skill, Hermes wrote its own "video editing" skill from the MCP.
- The Agent Service keeps one small **pointer skill per slot** (e.g. `video-editing`): "for shorts use `defleur-video`; for long-form use `<other>`; ask if unsure". It holds routing and the owner's preferences, never the app's instructions. It is regenerated from `apps.json` on every install/update/remove, and the owner's stated preferences are kept.

## Discovery: catalog → store → apps.json

- **Catalog (App Manager):** GitHub topic search `topic:wizard-os-app` (and `topic:wizard-ai` during the transition), filtered to repos whose `wizard.md` passes the checker, cached. Each catalog row records the repo, commit and checker result.
- **Store (App Manager):** the catalog is compiled into a Runtipi-compatible store (`apps/<id>/config.json`, `docker-compose.yml`, `metadata/`). Runtipi stays stock and unmodified; it just points at the compiled store. Nobody merges app repos into a monorepo by hand. Reference implementation: `tools/build_store.py`.
- **Installed registry (App Manager):** on install/update/remove, write `/wizard-os/apps.json` (id, type, version, MCP URL, skill path, view route, provides, system, health).
- **Agent Service (Jan):** reads `apps.json`, registers each MCP with the agent, links each shipped skill, regenerates pointer skills, and injects the installed-app list into the Wizard OS meta-instructions. Hermes stays unmodified.
- **Wizard UX (James):** reads the same `apps.json` for the launcher (non-system apps) and opens views at `/apps/<id>/`.
- **`wizard` CLI:** `wizard apps list --json` reads the same file; one generic CLI, no per-app CLIs.

## GitHub now, Nostr later

Catalog = GitHub topic search + `wizard.md` at repo root. The Nostr path (NIP-34 repo announcements, ngit, GRASP hosting, Wizard ID = npub) replaces the catalog source later. `wizard.md`, the compiled store and `apps.json` do not change; only the catalog fetcher does.
