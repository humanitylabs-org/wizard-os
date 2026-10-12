# Where things live on a Wizard box

**Status: proposed (James, 12 Oct 2026; DECISIONS #53).** Collects the paths already decided in [SHELL.md](SHELL.md), [PAGES.md](PAGES.md), [AGENT_STATE.md](AGENT_STATE.md), [AGENT_BRIDGE.md](AGENT_BRIDGE.md) and [MAC.md](../docs/MAC.md), and adds homes for customized app screens and for apps the owner's Wizard builds.

## Three areas, split by who may read them

```
~/runtipi/media/            YOUR FILES. Mounted into every app that asks for `files`. Agents see it as /files.
                            On a Mac this is the ~/Wizard folder shared into the VM.
  Inbox/                    drops, uploads, chat attachments
  Documents/  Videos/  Audio/  Meetings/  Exports/
  Pages/                    things to look at: reports, dashboards, shared docs (one git repo; PAGES.md)

~/.wizard-os/               THE SYSTEM. Never mounted into an app as a whole; each part goes only where it's needed.
  settings.json             shell layer 1: names, timezone, voice vocabulary (SHELL.md)
  launcher.json             shell layer 2: dock and home screen
  theme.json                shell layer 3: colours, type, motion
  shell/overlay/            shell layer 4: the owner's CSS/JS for the shell itself
  views/<app-id>/           the owner's version of an installed app's screen (VIEWS.md; git)
  dev/<app-id>/             source of apps the owner's Wizard builds (git; pushed to GitHub to share)
  agents/<agent-id>/        one folder per agent: agent.json + home/ (AGENT_STATE.md)
  skills/<app-id>/          app skills, written by the App Manager        ┐ generated; every agent
  skills/wizard-job-<job>/  pointer skills, written by the Agent Service  ┘ reads them, none edits them
  apps.json                 installed apps (App Manager)
  wizard-grants.json        what each agent and app may use (permissions)
  mcp-token                 the gateway token (0600)
  alongside.json            alongside boxes only: the agent spot is the host Hermes
  linked.json               alongside boxes only: the exact config edits `wizard unlink` reverses

~/runtipi/                  THE MACHINERY. Runtipi and the App Manager only; nobody edits it by hand.
  app-data/<store>/<app-id>/     each app's own database, cache and state
  user-config/<store>/<app-id>/  App Manager overrides (alongside wiring, ports)
  apps/  repos/  state/  traefik/  Runtipi internals
```

## Rules

1. **Content the owner looks at goes in `media/`. Anything that acts with authority goes in `~/.wizard-os/`.** Every app with `files` access can write to `media/`. Pages live there because they're sandboxed and can't act as the owner. A customized app screen calls that app's API as the owner, and source in `dev/` gets built and installed, so a confused or hostile app must not be able to plant code in either. They live in the system area.
2. **App databases stay in `app-data/`.** Apps never put their own state into `media/`, so the owner's folder stays readable and apps can't trip over each other's files.
3. **Everything the owner or their agent makes is in git**: `media/Pages/`, `views/<app-id>/`, `dev/<app-id>/`. Agents' homes keep whatever history their harness keeps.
4. **Generated files are never edited**: `skills/`, `apps.json`. They're rebuilt from installed apps on every change.
5. **What survives uninstalling an app:** `media/`, its `views/<app-id>/` (switched off), and `app-data/` unless the owner chooses "delete its data".
6. **What a backup or a move to always-on copies:** `media/`, `~/.wizard-os/` minus generated files, and `app-data/`. Everything else is rebuilt from the release file and `apps.json`.

## Not decided here

- Per-app sub-folders inside `media/` (for example `media/Videos/DeFleur/`) are each app's choice, written into its skill.
- Encrypting `~/.wizard-os/agents/` at rest waits for the private-agent work.
