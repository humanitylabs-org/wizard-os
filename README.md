# wizard-os

The shared map of Wizard OS: how the pieces fit, the contracts between them, and what's next. James, Jan and Miguel's agents all build against this repo. Agreed at the Wizard Dev Council, 9 Oct 2026.

**Agents:** read [`AGENTS.md`](AGENTS.md) first.

## Repos and owners

| Repo | Owner | What |
|---|---|---|
| `wizard-ux` | James + Archimedes | The front end everywhere: phone app, desktop UX, and the native desktop app's hotkeys. Includes the Apps screen. |
| `wizard-agent-service` | Jan | The service between any front end and the agent. Adds the Wizard OS instructions and the installed apps; Hermes stays unmodified. |
| `wizard-app-manager` | Miguel | A **thin fork** of Runtipi (DECISIONS #32): a small backend patch that installs apps straight from the index, re-checks `wizard.md` and writes `apps.json`. The frontend is stock Runtipi (admin/break-glass); the image is a drop-in for `runtipi/runtipi`. |
| `wizard-app-index` | Miguel | The shared app catalog: [apps.aiwizards.com](https://apps.aiwizards.com) (API) and [aiwizards.com/wizard-apps](https://www.aiwizards.com/wizard-apps) (store page). Publish + topic crawl; a rebuildable cache. |
| `wizard-app-store` | Miguel | Legacy hand-maintained Runtipi store. Every app in it now has its own repo; kept until boxes move to the App Manager. |
| `wizard-os` (this repo) | shared | Architecture, rollout, decisions, contracts, style, checks. |
| one repo per app | app author | Root `wizard.md`, tagged `wizard-app`. Examples: `humanitylabs-org/defleur-video`, `oscarhenrycollins/transcriber`. |
| `try-wizard` | later | The Mac installer. Parked until the pieces above work together. |

## Read in this order

1. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): the pieces and how they connect.
2. [`docs/DECISIONS.md`](docs/DECISIONS.md): what's locked, what's proposed.
3. [`docs/ROLLOUT.md`](docs/ROLLOUT.md): what ships when, and what's parked.
4. [`docs/WORK_OUTSTANDING.md`](docs/WORK_OUTSTANDING.md): open items by owner.
5. [`docs/SYSTEM_APPS.md`](docs/SYSTEM_APPS.md): system apps, slots, and the files and transcription overlaps.
6. [`docs/PRIVATE_BETA.md`](docs/PRIVATE_BETA.md): sharing an app with a friend before it's public.
7. [`docs/MAC.md`](docs/MAC.md): the later Mac installer.

## Contracts (`spec/`)

- [`WIZARD_MD.md`](spec/WIZARD_MD.md): the app format (v0.2) and the checker's rules.
- [`APPS_JSON.md`](spec/APPS_JSON.md): the installed-apps list the App Manager writes and the Agent Service and UX read.
- [`AGENT_SERVICE_API.md`](spec/AGENT_SERVICE_API.md): the `/wizard/...` API.
- [`NATIVE_BRIDGE.md`](spec/NATIVE_BRIDGE.md): how native shells (Android, desktop) talk to the web UX.
- [`SHELL.md`](spec/SHELL.md): the shell slot (Wizard UX as the system front end) and how owners customize it without forking (proposed).
- [`PAGES.md`](spec/PAGES.md): pages, the agent-made reports, dashboards and shared docs that live in Files and need no container (proposed).

## Tools

- `tools/check_wizard_md.py <repo> [--github owner/repo]`: pass/fail check for an app. The App Manager and each app's CI run copies of it; the rules must stay identical.
- `tools/build_store.py`: compiles passing app repos into a stock Runtipi store (the App Manager does this live).
- `examples/defleur-video/`: DeFleur Video as a v0.2 app.
