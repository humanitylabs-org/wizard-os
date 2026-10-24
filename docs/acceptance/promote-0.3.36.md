# Promote 0.3.36 to stable: upgrade-test evidence (24 Oct 2026)

Fast-tracked fix promotion (DECISIONS #82). Stable moves from 0.3.34 to 0.3.36.

## Box

Demo VPS (Ubuntu 24.04, tailnet host `demo`), stock Hermes v0.22.5 as root with Telegram. Wizard OS 0.3.34 was installed alongside by the owner through the Telegram install prompt, with Tailscale installed and signed in by the installer.

## Upgrades on the same box (no wipe)

- 0.3.34 -> 0.3.35 (`WIZARD_RELEASE=0.3.35 bash -s start`): done in about 2.5 min. Setup phone answered `step: serving` with the box's tailnet link (#141). The owner's message row still read `internal_notification`: Hermes history omits `platform_message_id`, so #142 never matched.
- 0.3.35 -> 0.3.36 (`WIZARD_RELEASE=0.3.36 bash -s start`): done in about 2 min. Agent Service image `8b5f9f9ce8f6` (35b2463). The owner's `hi` now projects as a plain user row (#143), so the Sent/Dismiss bubble clears.
- Both runs: Hermes `config.yaml` and `.env` unchanged (sha256 before/after), every container Up, `wizard doctor` 0 FAIL, install.log 0 FAIL, gateway active.

## Classification

Fixes only (Agent Service #141, #142, #143), each with a regression test that fails on the previous main.
