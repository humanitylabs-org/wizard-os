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
publisher: npub1…            # optional; the Wizard ID (Nostr key) credited with this app (#38)

runtime:                    # how the App Manager installs it (Runtipi today)
  kind: runtipi
  config: runtipi/config.json
  compose: runtipi/docker-compose.yml

api:                        # required for every app with a back end (#51)
  port: 8787                # where the app's HTTP API listens (inside the app network)
  path: /api
  spec: openapi.json        # OpenAPI file in the repo or a URL the app serves (recommended),
                            # or a Markdown file describing every route

mcp:                        # required for every app with a back end (#51)
  path: /mcp
  port: 8787
  transport: streamable-http

skill: skill/SKILL.md       # required for every type except view; ships with the app

view:                       # required for view; optional for others
  path: /                   # opened by Wizard UX at /apps/<id>/
  port: 8080
  source:                   # optional: where the screen's source lives, so an owner's agent can make
    path: web/              #   its own version of it (spec/VIEWS.md). May point at another repo:
    build: npm ci && npm run build   #   repo: filebrowser/filebrowser, ref: v2.63.23, path: frontend/
    dist: web/dist
backend: none               # only for a view with no server of its own (it uses other apps' APIs);
                            # such a view needs neither api nor mcp
replaces_view: mizel        # optional, views only: installing this view swaps it in for that app's
                            # screen in the launcher; uninstalling it brings the original back (VIEWS.md)

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
5. `mcp` present for agent, service and external, and for every view that doesn't say `backend: none`; `skill` present for every non-view; the skill file exists and has `name` + `description` front matter.
6. `view` present for type view.
7. Every `needs` entry is from the known capability list.
8. `provides` entries, if present, are slot ids (`^[a-z0-9][a-z0-9-]{1,40}$`).
9. Optional online check (`--github owner/repo`): the repo has the `wizard-app` or `wizard-ai` topic.
10. `publisher`, if present, is a valid `npub1…`.
11. `category`, if present, is one of `agent`, `interface`, `app`, `system`.
12. The Runtipi compose file asks for no host-level access: no `privileged`, no `network_mode`/`pid`/`ipc`/`uts`/`userns_mode: host`, no host devices, no container-runtime socket, no host system paths (`/`, `/etc`, `/root`, `/home`, `/proc`, `/sys`, `/dev`, `/run`, `/var/run`, `/usr`, `/boot` …), no `unconfined` security options, and none of `SYS_ADMIN`, `SYS_MODULE`, `SYS_PTRACE`, `SYS_RAWIO`, `NET_ADMIN`, `DAC_READ_SEARCH`, `BPF`, `PERFMON`, `ALL` in `cap_add`. Runtipi's own `${APP_DATA_DIR}` and `${ROOT_FOLDER_HOST}/media` mounts are fine.
13. Publisher credit (index and App Manager): an app is credited to an npub only when `publisher` names it **and** that npub signed a NIP-34 announcement whose `clone` is this repo and whose `euc` is the repo's first commit (or lists the signer in `maintainers`). Every Nostr event's id and signature are verified. With either side missing, the app is listed as unclaimed under its GitHub owner ([WIZARD_ID.md](WIZARD_ID.md#app-publishing-decisions-33)).
14. `api` present (with `port`, `path` and `spec`) for every app that has `mcp`. **Warning in 0.2, error from `wizard: 0.3`**, so apps listed today stay listed while they add it.
15. `view.source`, if present, names `path`, `build` and `dist`; with `repo` it also names `ref` (a tag or commit, never a branch).
16. `backend: none` only on `type: view`, and never together with `api` or `mcp`.

## Every app with a back end has an API and an MCP (#51)

An app with a back end is anything that keeps state or does work beyond serving static files. Every such app, whatever its `type`, exposes two things:

- **A documented HTTP API** (`api:`): the same API its own screen uses. This is what lets an owner's agent build a different screen for the app, and what other apps call.
- **An MCP** (`mcp:`): how agents use the app. The MCP can be a thin layer over the API (the front-container pattern below does exactly that).

The only apps that skip both are pure front ends (`type: view`, `backend: none`): a screen that runs entirely in the browser and talks to other apps' APIs through `uses:`.

**The app's own screen is optional, and it is never the only way in.** Anything a person can do on the screen, an agent can do through the MCP and another screen can do through the API.

**How customizable a screen is follows from what the app declares** (shown in the store; the full mechanics are in [VIEWS.md](VIEWS.md)):

| The app declares | The owner's agent can |
|---|---|
| any screen (`view:`) | add an **overlay**: move, hide and restyle things on the existing screen |
| `view.source` + a screen that talks only to `api` | make the owner's **own version** of the screen, kept in step with app updates |
| `api` | build a **new screen** for the app's data from scratch |

Single-page front ends over a JSON API (most modern self-hosted apps, File Browser included) can declare `view.source`, pointing at the upstream repo if the wrapper doesn't hold the source. Screens rendered on the server (Nextcloud, Gitea) get overlays and new screens, but not an own version. Both are fine; the store says which.

## Making an existing app compatible (no fork)

An existing open-source app becomes a Wizard app without moving a single folder in its repo. Two ways, same result:

- **In the app's own repo:** add `wizard.md`, `runtipi/` (config + compose) and `skill/` at the root.
- **In a small wrapper repo** (what Files, Transcriber, Browser and Hermes Agent do): the same three things, with the compose pointing at the upstream image. Nothing upstream changes, and updating means bumping the image tag.

What it has to provide:
1. **`wizard.md`** pointing at things where they already are: the API, its docs, the screen's source. Paths, not a required layout.
2. **Runtipi files.** Most popular self-hosted apps already have them in the Runtipi or Umbrel app stores; adapt those.
3. **An MCP.** If upstream has none, add the stdlib MCP front container (next section): a few narrow tools that call the upstream API.
4. **A skill** that tells an agent how to do the app's jobs with those tools.
5. **API docs.** Point `api.spec` at upstream's OpenAPI file or docs page. If upstream's API is undocumented, the wrapper documents the routes its MCP and screen use.

Two guides follow with the `wizard-builder` skill (to write): `docs/BUILD_AN_APP.md` for a new app and `docs/PORT_AN_APP.md` for an existing one. The skill teaches agents the same steps.

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
