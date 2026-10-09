# wizard-os

Shared architecture repo for Wizard OS (agreed at the Wizard Dev Council, 9 Oct 2026). One place for the specs, the style guide and the checks, so James's, Jan's and Miguel's agents build against the same contract.

## Repos and owners (as agreed 9 Oct)

| Repo | Owner | What |
|---|---|---|
| `wizard-ux` | James | Mobile-first front end (Chromium-based; Electron on desktop, native container on phone) |
| `wizard-agent-service` | Jan | Deterministic proxy between any front end and any agent; injects Wizard OS meta-instructions; Hermes unmodified |
| `wizard-app-manager` | Miguel | Fork of Runtipi + Wizard app store; ships system core apps (Files, Transcription, Notifications, Microphone) |
| `wizard-os` (this repo) | shared | Architecture, app format, style guide, checks |
| one repo per app | app author | Tagged `wizard-ai`, contains `wizard.md` |

## Contents

- `spec/WIZARD_MD.md` — the app format (v0.2): what `wizard.md` contains, capability slots (`provides`), shipped skill + pointer skill, the checker's rules, and the discovery chain (topic catalog → compiled Runtipi store → `apps.json` → Agent Service + Wizard UX).
- `tools/check_wizard_md.py` — automated pass/fail check. `python3 tools/check_wizard_md.py <repo> [--github owner/repo]`
- `tools/build_store.py` — compiles passing app repos (local paths or `--github-topic wizard-ai`) into a stock Runtipi store layout plus `catalog.json`. Runtipi stays unmodified; nobody hand-merges apps into one store repo.
- `examples/defleur-video/` — Miguel's DeFleur Video expressed as a v0.2 Wizard app. Passes the checker; its compiled store entry passes the wizard-app-store test suite (47/47, official Runtipi schemas).

## Next additions

- `spec/ARCHITECTURE.md` — the one-page system map (UX → Agent Service → agent; App Manager → apps.json).
- `style/` — design tokens and components extracted from `wizard-ux`.
- `spec/CREDENTIALS.md` — one credential per AI provider shared across agents on a host, plus the break-glass kit.
