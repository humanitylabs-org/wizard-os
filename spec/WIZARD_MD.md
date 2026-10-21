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
2. `recommends:` — the agent/model the app is tuned for. For an AI process, its declared model is binding: load the app's shipped workflow, select that model explicitly, and stop on a mismatch unless the owner explicitly approves the named override. The chat or host default never silently substitutes. Every installation receives the same versioned prompt/model contract. See [APP_WORKFLOWS.md](APP_WORKFLOWS.md) (James, 16 Oct). Proposed: `requires:` declares each AI feature's tier, tested model and whether it may swap, plus outside services, so the Connection Router can match them to the owner's providers ([CONNECTION_ROUTER.md](CONNECTION_ROUTER.md), #65).
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
  package: source           # source | build | image (see "Packaging"); recommended

mcp:                        # required for agent, service, external; optional for view
  path: /mcp
  port: 8787
  transport: streamable-http

skill: skill/SKILL.md       # required for every type except view; ships with the app

view:                       # required for view; optional for others
  path: /                   # opened by Wizard UX at /apps/<id>/
  port: 8080

receives_voice_input: true  # optional boolean: app owns voice requests and feedback

provides: [video-editing, short-form-video]   # capability slots (optional, recommended)
recommends:                 # optional for non-AI apps; declared AI model is binding
  agent: hermes
  model: claude-opus-5-5

system: false               # true = installed with Wizard OS, hidden from the
                            # launcher, known to the agent, replaceable by any
                            # app that provides the same slot

agent_binding:              # optional; the app sends work (recaps, reports) to an
  required: true            # agent the owner picks; default = the main agent
  purpose: Where your recaps go   # (spec/AGENTS.md section 7)
uses: [transcriber, browser, files]   # other app ids or slots it calls
shares:                     # optional: folders in this app's app-data that other
  - id: claude-login        # apps may mount once the owner grants it
    path: claude            # relative to ${APP_DATA_DIR}/data
mounts:                     # optional: another app's share this app needs
  - app: wizard-claude
    share: claude-login
    path: /claude           # where it appears inside this app's main service
needs: []                   # device capabilities: mic, system-audio, camera,
                            # notifications, files, credentials:<provider>
health: /healthz
---
```

## State storage

Everything an app must keep lives under `${APP_DATA_DIR}`, so the App Manager's backup and a box move carry it. Docker named volumes are not backed up. The App Manager therefore rewrites each top-level named volume in an app's compose to a bind mount at `${APP_DATA_DIR}/volumes/<name>`; on the first start after the rewrite it copies the old volume's contents there once (ownership and modes kept) and leaves the old volume in place for the owner to delete. A volume with a fixed `name:` is refused by the checker (rule 15); apps that need to give another app a folder use `shares`.

## Shared folders

A share is the one way two apps see the same files. The provider lists it under `shares` (a folder relative to its `${APP_DATA_DIR}/data`); the consumer lists it under `mounts`. Installing the consumer proposes a `share` grant on the install sheet ([PERMISSIONS.md](PERMISSIONS.md#share-grants)). While the grant exists the App Manager bind-mounts the folder into the consumer's main service at `path`; revoking it removes the mount on the next restart. The files stay in the provider's app-data, so the provider's backup holds them and uninstalling the consumer never deletes them. Use a share only when an official client must run on both sides (Claude's login); everything else goes through the provider's API.

## Receives voice input

Optional `receives_voice_input: true` opts a declared app view into shell-delivered speech. Missing/false keeps normal shell routing; the value is a strict boolean. The app owns interpretation and feedback, including whether its existing agent workflow needs a Chat. Shells own capture and interaction design; this declares no orb or app-local recorder. See [VOICE_INPUT.md](VOICE_INPUT.md) for the shared receiver, durable acknowledgement and recovery contract.

## Packaging: source, build or image

An app says how its containers come to exist with `runtime.package`. Nobody should have to build images for two kinds of CPU to publish a small app, and an owner should be able to read what their box runs. Source is the canonical artifact; a prebuilt image is a cache.

1. **`source` (the default for new apps).** No custom image. Every service uses an official, digest-pinned, multi-arch image (`python:3.12-alpine@sha256:…`) and runs the app's own code, which the App Manager mounts read-only from the pinned commit at `${APP_SOURCE_DIR}` (the whole repo, without `.git`). Mount a subfolder with `${APP_SOURCE_DIR}/app:/app:ro`. Dependencies are vendored in the repo or there are none. Works on Intel and Apple Silicon with nothing to build.
2. **`build`.** The repo has a Dockerfile and the box builds it from the pinned commit. `build.context` is a path relative to the repo root and `dockerfile` is relative to the context, as in Compose; the App Manager points them at its pinned copy and names the result `wizard-local/<app>-<service>:<commit12>`. Every `FROM` is digest-pinned, every `pip install` uses `--require-hashes` (or `-r` a file whose lines carry `--hash=`), and nothing compiles or bundles: no `npm run build`, `cargo`, `go build`, `make` or `gcc`. Distro packages (`apk add`, `apt-get install`) from the pinned base are allowed.
3. **`image`.** A prebuilt multi-arch image (linux/amd64 + linux/arm64), required for anything heavy or compiled (ffmpeg builds, speech models, Rust, JS bundles). Publish it with the shared workflow (`humanitylabs-org/wizard-app-index/.github/workflows/app-image.yml`), which builds both architectures from the commit and tags `sha-<commit>`. The compose names it by digest.

For every package type, every `image:` in the compose (after `${VAR:-default}` resolves to its default) is pinned by digest, and no image uses `latest` or a bare version tag. On install the App Manager uses the published image when the type is `image`, builds locally when it is `build`, and mounts the source when it is `source` or `build`.

Apps without `runtime.package` still install as before. New apps declare it; the checker applies the packaging rules whenever it is present.

## Rules the checker enforces

1. Front matter parses and `wizard` is a known spec version (0.1, 0.2).
2. `id` matches `^[a-z0-9][a-z0-9-]{1,40}$`; `type` is one of the four types.
3. `version` is semver-ish; `summary` ≤ 140 characters; `license` and `source` present.
4. `runtime.config` and `runtime.compose` exist in the repo.
5. `mcp` present for agent, service and external; `skill` present for every non-view; the skill file exists and has `name` + `description` front matter.
6. `view` present for type view.
7. Every `needs` entry is from the known capability list.
8a. `receives_voice_input`, if present, is a boolean; true requires a declared view with path and port.
8. `provides` entries, if present, are slot ids (`^[a-z0-9][a-z0-9-]{1,40}$`).
9. Optional online check (`--github owner/repo`): the repo has the `wizard-app` or `wizard-ai` topic.
10. `publisher`, if present, is a valid `npub1…`.
11. `category`, if present, is one of `agent`, `interface`, `app`, `system`.
12. The Runtipi compose file asks for no host-level access: no `privileged`, no `network_mode`/`pid`/`ipc`/`uts`/`userns_mode: host`, no host devices, no container-runtime socket, no host system paths (`/`, `/etc`, `/root`, `/home`, `/proc`, `/sys`, `/dev`, `/run`, `/var/run`, `/usr`, `/boot` …), no `unconfined` security options, and none of `SYS_ADMIN`, `SYS_MODULE`, `SYS_PTRACE`, `SYS_RAWIO`, `NET_ADMIN`, `DAC_READ_SEARCH`, `BPF`, `PERFMON`, `ALL` in `cap_add`. Runtipi's own `${APP_DATA_DIR}` and `${ROOT_FOLDER_HOST}/media` mounts are fine.
13. Publisher credit (index and App Manager): an app is credited to an npub only when `publisher` names it **and** that npub signed a NIP-34 announcement whose `clone` is this repo and whose `euc` is the repo's first commit (or lists the signer in `maintainers`). Every Nostr event's id and signature are verified. With either side missing, the app is listed as unclaimed under its GitHub owner ([WIZARD_ID.md](WIZARD_ID.md#app-publishing-decisions-33)).
14. Packaging (when `runtime.package` is present): it is `source`, `build` or `image`; every compose image is digest-pinned; `source` has no `build:` and mounts `${APP_SOURCE_DIR}` read-only; `build` has a `build:` whose context stays inside the repo and a Dockerfile with digest-pinned `FROM`s, hash-locked `pip install`s and no compile or bundle steps; `image` has no `build:`.
15. Storage: no top-level volume sets `name:`; every `shares[].path` is relative and stays inside the app-data folder; every `mounts[]` names an app id, a share id and an absolute container path.

## Skills: shipped skill + pointer skill

- AI-generating apps ship the versioned model/prompt/process and verification contract described in [APP_WORKFLOWS.md](APP_WORKFLOWS.md). The skill loads it before generation or delegation; a mismatch requires explicit owner approval before execution. Owner-local skills and earlier conversations cannot be the only copy.
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
