# wizard.md — Wizard app format, v0.2 (draft)

Status: draft for James, Jan and Miguel. Source: Wizard Dev Council, 9 Oct 2026, full transcript.

- "We make any open source GitHub repo compatible if … it has a WizardMD" (James)
- "the app has to ship with an MCP and with a skill" (Miguel)
- "any wizard can verify a WizardMD. Does it qualify? … Pass, pass, pass" (James)
- "it's just checks rather … what I would not want is any sort of human review" (Miguel)
- "each app its own repository tagged with wizard AI" (the call's working name; the approved tag is `wizard-app`) + "monitor all GitHub repositories with this tag and include them in a wizard apps interface that is installable using RunTP" (James/Jan)

A repository is a Wizard app when its root contains a `wizard.md` that passes the checker. The GitHub topic `wizard-app` (approved by James 9 Oct 2026, [DECISIONS](../docs/DECISIONS.md) #4; `wizard-ai` still searched during the transition) makes it discoverable; it is not proof of compatibility (the topic is public and already used by unrelated repos). No human review.

Every app is its own repo, including the ones Humanity Labs makes: there are no "core apps" by definition, only apps that fill slots. Which app fills a slot by default is a separate defaults list, not a property of the app.

## Changes from v0.1

1. `provides:` — capability slots the app fills (`video-editing`, `files`, `transcription` …). This is how the agent picks between several apps for the same job (James: "for shorts I want the DeFleur pipeline, for long-form podcasts this pipeline") and how system core apps become swappable ("these are alternatives to fit into those slots").
2. `recommends:` — the agent/model the app is tuned for. The shipped skill runs the check first and warns, then proceeds ("intended to be used with Opus 5.5 and Hermes … results may vary, do you want to proceed?").
3. `system: true` is a role, not a separate format: system core apps are ordinary Wizard apps that the OS installs by default, hides from the launcher and tells the agent about. Any of them can be replaced by another app that `provides` the same slot.
4. Pointer-skill rule (below): the Agent Service, not the app, owns the generic "when asked to do X, use app Y" skill.
5. The topic alone never makes an app compatible.
6. `category:` (optional) — the store shelf: `agent`, `interface`, `app` or `system`. Missing means `agent` for `type: agent`, `app` otherwise. `type` says how the app runs; `category` says where people find it.
7. `icon:` (optional) — a square PNG or JPEG in the repo for the store and launcher. Missing falls back to Runtipi's `metadata/logo.jpg` next to `runtime.config`. The icon is a sigil made to [`style/ICONS.md`](../style/ICONS.md); `style/sigils/make_icon.py` writes `icon.png` (DECISIONS #33).
8. Container safety: the checker refuses host-level access in the compose file (rule 12).

## Shape

`wizard.md` = YAML front matter (machine contract) + Markdown body (what the app does, for people and agents).

```yaml
---
wizard: 0.2                 # spec version (0.1 still accepted)
id: defleur-video           # lowercase a-z0-9-, unique in a catalog
name: DeFleur Video
type: service               # agent | service | view | external (how it runs)
category: app               # agent | interface | app | system (store shelf; optional)
version: 0.6.5
summary: Edit a talking-head video into a finished vertical short.
icon: icon.png              # optional; square PNG/JPEG, 512x512 recommended
license: MIT
source: https://github.com/humanitylabs-org/defleur-video
publisher: npub1…            # optional; the Nostr key that publishes this app (stage 2+)

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
9. Optional online check (`--github owner/repo`): the repo has the `wizard-app` or `wizard-ai` topic.
10. `publisher`, if present, is a valid `npub1…`.
11. `category`, if present, is one of `agent`, `interface`, `app`, `system`.
12. The Runtipi compose file asks for no host-level access: no `privileged`, no `network_mode`/`pid`/`ipc`/`uts`/`userns_mode: host`, no host devices, no container-runtime socket, no host system paths (`/`, `/etc`, `/root`, `/home`, `/proc`, `/sys`, `/dev`, `/run`, `/var/run`, `/usr`, `/boot` …), no `unconfined` security options, and none of `SYS_ADMIN`, `SYS_MODULE`, `SYS_PTRACE`, `SYS_RAWIO`, `NET_ADMIN`, `DAC_READ_SEARCH`, `BPF`, `PERFMON`, `ALL` in `cap_add`. Runtipi's own `${APP_DATA_DIR}` and `${ROOT_FOLDER_HOST}/media` mounts are fine.
13. App Manager only, for apps found on Nostr: the announcement's signature verifies, and if `publisher` is declared, the signer is that key or a listed maintainer.

## Skills: shipped skill + pointer skill

- The app ships its own full skill (`skill:`). The agent never writes that skill from scratch. Miguel's demo showed the failure mode: without a shipped skill, Hermes wrote its own "video editing" skill from the MCP.
- The Agent Service keeps one small **pointer skill per slot** (e.g. `video-editing`): "for shorts use `defleur-video`; for long-form use `<other>`; ask if unsure". It holds routing and the owner's preferences, never the app's instructions. It is regenerated from `apps.json` on every install/update/remove, and the owner's stated preferences are kept.

## Discovery: index → local store → apps.json

- **Index (shared, `wizard-app-index`):** one public catalog at [apps.aiwizards.com](https://apps.aiwizards.com), with the store page at [aiwizards.com/wizard-apps](https://www.aiwizards.com/wizard-apps). It's a Cloudflare Worker + D1 database. It's a cache, not the source of truth: every listing is re-read from the app's own repo at a pinned commit, so the database can be dropped and rebuilt. Apps get in two ways:
  - **Publish (push):** `POST https://apps.aiwizards.com/v1/publish {"repo":"owner/name"}`, a GitHub webhook to the same URL, or the one-line GitHub Action every app repo carries. The index re-reads the repo and runs the checker; nothing in the request is trusted.
  - **Crawl (fallback):** every 10 minutes it searches the `wizard-app` topic (and `wizard-ai` during the transition) in created-date slices, so no single query hits GitHub search's 1,000-result cap. Listings are re-verified weekly; a failing or vanished repo is delisted.
  - Search: `GET /v1/search?q=&category=&slot=&type=&publisher=&arch=`. Why a repo isn't listed: `GET /v1/apps/{owner}/{repo}`.
- **Why an index, not per-box search:** a box that searches GitHub itself stops at 100 apps (one result page) and 1,000 at best (GitHub's cap), and every box re-clones every app. The index does the search once; a box only fetches the apps its owner installs. Work grows with publishes, not with apps × boxes.
- **Local store (App Manager):** on install, the App Manager fetches that one app at the commit the index lists, re-runs the checker, and writes it into Runtipi's normal per-app layout, fetching on demand inside the App Manager's thin Runtipi fork (DECISIONS #32), so there is no separate sync job.
- **Installed registry (App Manager):** on install/update/remove, write `~/.wizard-os/apps.json` (id, type, version, MCP URL, skill path, view route, provides, system, health).
- **Agent Service (Jan):** reads `apps.json`, registers each MCP with the agent, links each shipped skill, regenerates pointer skills, and injects the installed-app list into the Wizard OS meta-instructions. Hermes stays unmodified.
- **Wizard UX (James):** the Apps screen searches the index and installs through the App Manager; the launcher reads `apps.json` (non-system apps) and opens views at `/apps/<id>/`.
- **`wizard` CLI:** `wizard apps list --json` reads the same file; one generic CLI, no per-app CLIs.

## MCP for apps that don't ship one

Upstream images (Speaches, Chromium, File Browser, Hermes) don't speak MCP. The pattern used by Transcriber, Browser, Secret Drop, Hermes Agent and AI Accounts:
- The main Runtipi service is a small stdlib MCP front (`mcp/front.py` + `mcp/tools.py`) on a digest-pinned `python:3.12-alpine`, inlined into the compose `command` by `mcp/inline.py` so there's no image to build.
- It serves `/mcp` and passes every other request, byte for byte, to the unchanged upstream container (`<id>-engine`), WebSockets included. Other apps keep calling the same address (`http://transcriber:8000`).
- Tools stay narrow and never handle secrets (Secret Drop's MCP creates requests with the agent's public key; AI Accounts' MCP only reports status).

## GitHub now, Nostr later

Index sources today = publish + GitHub topic crawl, with `wizard.md` at the repo root. Nostr is **added** as a third source in stages ([ROLLOUT.md](../docs/ROLLOUT.md#nostr-path-github-to-nostr-without-a-migration-day)); `wizard.md`, the local store and `apps.json` do not change, only the index gains a source. A signed NIP-34 announcement becomes another way to call publish.

How an app is found on Nostr: a NIP-34 repository announcement (kind 30617) with hashtag `["t", "wizard-app"]`. Its `clone` tag can point at GitHub, so dual-publishing needs no new hosting. The index (and the App Manager, re-checking at install) verifies every event's id and signature, keeps the newest announcement per publisher + repo id, lists a repo found on both GitHub and Nostr once, and applies rule 11. The announcement's `euc` (earliest unique commit) links copies of the same project across hosts.

Every catalog row records `commit`, `found_via` (`github` | `nostr`), `publisher` and, for Nostr, the announcement event id. Installs pin to that commit.
