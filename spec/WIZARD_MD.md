# wizard.md — Wizard app format, v0.1 (draft)

Status: draft for James, Jan and Miguel. Source: Wizard Dev Council, 9 Oct 2026 ("if it has a wizard.md, it's compatible"; "the app has to ship with an MCP and with a skill"; "any wizard can verify a wizard.md … pass, pass, pass").

A repository is a Wizard app when its root contains `wizard.md` and the repo carries the GitHub topic `wizard-ai`. No human review. Any Wizard (or CI) runs the checker and gets pass/fail.

## Shape

`wizard.md` = YAML front matter (machine contract) + Markdown body (what the app does, written for people and agents).

```yaml
---
wizard: 0.1                 # spec version
id: defleur-video           # lowercase, a-z0-9-, unique in the store
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

skill: skill/SKILL.md       # required for every type except view

view:                       # required for view; optional for others
  path: /                   # served under /apps/<id>/ by Wizard UX
  port: 8080

system: false               # true = core app (Files, Transcription, Notifications,
                            # Microphone, Credentials): installed with Wizard OS,
                            # hidden from the user's app list, known to the agent

uses: [transcriber, browser, files]   # other app ids it calls
needs: []                   # device capabilities: mic, system-audio, camera,
                            # notifications, files, credentials:<provider>
health: /healthz
---
```

## Rules the checker enforces

1. Front matter parses and `wizard` is a known spec version.
2. `id` matches `^[a-z0-9][a-z0-9-]{1,40}$`; `type` is one of the four types.
3. `version` is semver-ish; `summary` ≤ 140 characters; `license` and `source` present.
4. `runtime.config` and `runtime.compose` exist in the repo.
5. `mcp` present for agent, service and external; `skill` present for every non-view; the skill file exists and has `name` + `description` front matter.
6. `view` present for type view.
7. Every `needs` entry is from the known capability list.
8. Optional online check (`--github owner/repo`): the repo has the `wizard-ai` topic.

## Discovery (agreed gap; proposed owner split)

- **App Manager (Miguel)** owns the registry: on install/update/remove it reads each app's `wizard.md` and writes `/wizard-os/apps.json` (id, type, MCP URL, skill path, view route, health).
- **Wizard Agent Service (Jan)** consumes `apps.json`: registers each MCP with the agent and links each shipped skill, then injects the installed-app list into the Wizard OS meta-instructions. Hermes stays unmodified.
- **Wizard UX (James)** reads the same `apps.json` for the launcher and for opening views at `/apps/<id>/`.

## GitHub now, Nostr later

Catalog = GitHub topic search `topic:wizard-ai` + `wizard.md` at repo root. The Nostr path (NIP-34 repo announcements, ngit, GRASP hosting) replaces the topic search and GitHub handles with a single switch later; `wizard.md` does not change.
