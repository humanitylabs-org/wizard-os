# Wizard OS architecture

**Version 1.0 · 9 Oct 2026.** Written from the Wizard Dev Council (James, Jan, Miguel, 9 Oct 2026) and the earlier architecture plan. Decisions are logged in [DECISIONS.md](DECISIONS.md).

## What it is

A personal AI server you run by talking to it. You install it on your Mac to try it. You move it to something always-on (a Mac mini, a VPS, a Wizard Box) when you want it working while you sleep. It has a front end you can reshape, one agent you talk to, and apps that give that agent new abilities.

## The pieces

```
  You (phone, Mac, browser)
     │
  Wizard UX ─────────────── one web front end; thin native shells add hotkeys, mic, files
     │  /wizard/... API
  Wizard Agent Service ──── adds "you are an agent inside Wizard OS", connects installed apps,
     │                      handles threads, runs, files, voice. The agent is unmodified.
  Agent (Hermes today) ──── reasons and acts
     │  MCP over HTTP
  Apps ──────────────────── each one: wizard.md + container + MCP endpoint + skill

  Wizard App Index ──────── shared catalog (apps.aiwizards.com): publish + crawl, checked, pinned
     │
  Wizard App Manager ────── installs what the owner picks into a local Runtipi store,
     │                      re-checks it, writes apps.json
  Runtipi (stock) ───────── runs the containers
```

**Wizard UX** (`wizard-ux`). One web app for every screen size. Phone and desktop are layouts of the same code. Native shells stay thin:
- Android: `ai.wizards.os`, a WebView.
- Wizard for Mac: a WKWebView, plus the Caps Lock Wizard key, Right ⌘ orb and Right ⌥ dictation.

The shells add what a browser can't (hotkeys, background mic, file sharing) through the [native bridge](../spec/NATIVE_BRIDGE.md). The Apps screen lives here.

Wizard UX is the **shell**: a system app filling the `shell` slot, always exactly one per box. Other screens are views (normal apps). Owners reshape it through settings, layout, theme and overlay files rather than forks ([spec/SHELL.md](../spec/SHELL.md)).

**Wizard Agent Service** (`wizard-agent-service`). The only thing the UX talks to.
- It proxies the agent, and adds the Wizard OS instructions on the way in, so Hermes itself stays stock.
- On every change to `apps.json` it connects each app's MCP and skill and tells the agent what's installed. That's the "knowledge transfer on install".
- It also keeps one short **pointer skill** per job type, for example "short-form video → DeFleur Video". The app's full skill stays with the app.
- It owns the versioned `/wizard/...` API.

**Agent.** Hermes today. Any harness that speaks MCP can sit here later. It gets its abilities from apps and its standing instructions from the Agent Service. Its skills, sessions and memory live in its own folder under `~/.wizard-os/agents/<id>/`; other agents reach them only through Agent Search under owner grants ([AGENT_STATE.md](../spec/AGENT_STATE.md)).

**Apps.** One repo each. Every app has:
- a root `wizard.md` ([spec](../spec/WIZARD_MD.md))
- stock Runtipi `config.json` and `docker-compose.yml`
- an MCP endpoint
- a skill telling the agent when and how to use it

Apps come in four types: view, service, agent and external. An app can declare:
- what it **provides**, as capability slots like `transcription` or `video-editing`
- what it **uses**, meaning other apps it depends on
- what it **needs**, meaning device permissions
- the agent and model it **recommends**; for AI processes the declared model and shipped workflow are binding unless the owner explicitly approves an override ([app-owned workflows](../spec/APP_WORKFLOWS.md))

**Wizard App Index** (`wizard-app-index`). One shared catalog for every Wizard: [apps.aiwizards.com](https://apps.aiwizards.com), with the store page at [aiwizards.com/wizard-apps](https://www.aiwizards.com/wizard-apps). Publishers push (API, webhook or the app's own GitHub Action); a crawler searches the `wizard-app` topic in date slices as a fallback. It runs the same checker and records the passing commit. It's a cache: the repos are the source of truth and it can be rebuilt from them. Nostr announcements become a third way in.

**Wizard App Manager** (`wizard-app-manager`). The Wizard layer on top of Runtipi, on each box. It does four things:
1. When the owner installs an app found in the index, fetches that one repo at the listed commit.
2. Re-runs the checker on it.
3. Adds it to a small local Runtipi store that holds only this box's apps, and installs through Runtipi's own API.
4. Writes [`apps.json`](../spec/APPS_JSON.md) and the app skills.

Its API listens on the box only and needs a token to install or remove apps.

A tag gets a repo **found**; only a passing `wizard.md` gets it **listed**.

**Runtipi.** A thin fork (DECISIONS #32): upstream Runtipi plus a small backend patch (index-backed store, Wizard categories, and later permission-aware networking). Its own screens stay stock and serve as admin/break-glass. The image is a drop-in for `runtipi/runtipi`, so any box can go back to stock by changing one image tag. Fixes go upstream wherever possible.

## Contracts

| Contract | Where | Owner |
|---|---|---|
| `wizard.md` v0.2, the app format | [spec/WIZARD_MD.md](../spec/WIZARD_MD.md) + `tools/check_wizard_md.py` | shared (Miguel drives) |
| `apps.json` v1, the installed apps | [spec/APPS_JSON.md](../spec/APPS_JSON.md) | Miguel writes it, Jan reads it |
| `/wizard/...` API, versioned | [spec/AGENT_SERVICE_API.md](../spec/AGENT_SERVICE_API.md) | Archimedes (DECISIONS #42; Jan reviews) |
| Native bridge (hotkeys, mic, files) | [spec/NATIVE_BRIDGE.md](../spec/NATIVE_BRIDGE.md) | James + Archimedes (desktop UX and native app) |
| Style tokens and shared components | [style/](../style/) | James |
| Release file (which versions go together) | `releases/` (to create) | Jan |

## Rules everyone builds to

- **Hermes stays unmodified; Runtipi carries only the thin, reversible App Manager patch (#32).** Wizard behaviour lives in the Agent Service, the App Manager, the UX or an app.
- **MCP over HTTP is the one way agents use apps.** One generic `wizard` CLI can call any app's MCP for humans and scripts.
- **One file root.** Every app sees the same user files folder ([SYSTEM_APPS.md](SYSTEM_APPS.md#files)).
- **One provider per slot by default.** Two apps can both provide `transcription`; `apps.json` names the default, and apps call the slot, not a specific app.
- **User data outlives apps.** Uninstalling an app keeps its data. On a Mac, user files live in a Mac folder and survive uninstalling Wizard ([MAC.md](MAC.md)).
- **Agents learn pointers, not copies.** When an agent picks up a workflow from an app, it writes a pointer to that app's skill, never a rewrite of it.
- **Slots are parking spots; system apps are only their defaults.** Every system capability, the shell included, is a slot. A system app is a normal app with `system: true` that we publish as a slot's default; any app that `provides:` the slot can replace it ([SYSTEM_APPS.md](SYSTEM_APPS.md)).

## Where it runs

All hosts run the same Linux stack: Runtipi, the App Manager, the Agent Service, the agent, the UX server and the apps.
- **Mac (trial, mass market, later):** a Mac installer runs that same stack in one Linux VM (`try-wizard`). Built after the components work together on Linux.
- **Always-on:** Mac mini, VPS or Wizard Box. One button moves the whole thing: snapshot, verify, cut over, roll back. Only one host writes at a time.
- **Phone:** always a client, never the server.

## Not in this document

- The deeper agent-service contract: see `WIZARD_AGENT_SERVICE_ARCHITECTURE.md` in James's context repo; the parts that matter here will move into `spec/AGENT_SERVICE_API.md`.
- Networking: Tailscale-compatible private network, with Headscale/DERP run by AI Wizards as the default.
- The appliance OS (Debian + Rugix).
