# Promote 0.3.34 to stable: upgrade-test evidence (24 Oct 2026)

Fast-tracked feature promotion under DECISIONS #93 (launch phase). Stable moves from 0.3.32 to 0.3.34.

## Box

Wipeable demo VPS (Ubuntu 24.04, tailnet host `demo-1`). Stock Hermes v0.22.5 installed as root with Telegram, then Wizard OS installed alongside by the owner pasting the private install prompt into Telegram (stable 0.3.32). The box started with no Tailscale: the installer installed it and the owner signed in from the link it sent.

## Upgrade 0.3.32 → 0.3.34 (same box, no wipe)

- `curl -fsSL https://aiwizards.com/os.sh | WIZARD_RELEASE=0.3.34 bash -s start`, the documented agent-safe rerun: 06:18 → `done` at 06:21 UTC.
- install.log read-back: 0 FAIL lines. Running images: wizard-ux `d1e2c390f807` (788affe), wizard-agent-service `e30b48f50a8f` (65d33e1), exactly the 0.3.34 pins.
- Every container Up. Hermes `config.yaml` and `.env` unchanged (sha256 before/after). The deferred Hermes restart ran; Telegram reconnected and the home-channel startup notice was sent.
- Shell `/wizard-os-home/` 200; `/store-install/_updates` 200 with `installed: 0.3.34`, mode `ask`, channel `stable`.

## Classification

Feature release (current main shell, Agent Service and App Manager for the private launch), including Chats reconciliation fixes for the stale "Sent / Dismiss" bubble seen on 0.3.32. A fresh install of 0.3.34 follows on the same box after this promotion.
