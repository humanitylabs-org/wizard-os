# Promote 0.3.72: pinned chats stay the same on every device (and the current Wizard UX)

## Why

The owner reported that a chat pinned or unpinned on one device did not show the same way on another. When two devices synced at about the same time, the later write replaced the shared list and dropped the other device's pin. A phone that had not pulled yet could also bring back a pin removed elsewhere.

The fix is wizard-ux #670 (merge `970378b2`). Each device now queues pin/unpin operations, reads the shared list fresh, replays its operations and reads the result back. On a conflict it replays again. Miguel asked for it on Stable ("promote that to stable because it's a fix").

## What changes

**Release contents.** 0.3.72 is 0.3.71 with **Wizard UX `d53b2b24` → `970378b2`**:
- image `sha256:d1b00210cf5f2ccd7de55da1649702a1fc81fce1d9a988080b784ff2c8baff34`, amd64 + arm64;
- built by push run [40628699290](https://github.com/humanitylabs-org/wizard-ux/actions/runs/40628699290) on `main`, where validate, publish, attest, finalize and anonymous-pull all succeeded;
- an anonymous ghcr token GET of `sha-970378b2…` returns the same index digest.

Everything else is exactly 0.3.71. Cut in wizard-os #292, mirrored byte-identical in wizard-app-manager #295.

**What Stable gains vs 0.3.68.** Stable moves 0.3.68 → 0.3.72, so it also takes everything in between:

- **0.3.69 — App Manager `da2f01d1` → `08b54f65`** (wizard-app-manager #267, a fix). Upgrades bring installed default apps to their release pins and reconcile new required connection inputs without resetting owner settings. No image-input change.
- **0.3.70** — no further component change for Stable (0.3.69 + Stable 0.3.68's pins).
- **0.3.71 — Notifications 2.29.0-wizard2 → 2.29.0-wizard10** (`cdce9f18`, wizard-app-manager #277). This is a **feature** update to the inbox: a skin-scoped inbox, a phone list/detail view, Reply opens an unsent chat, and an optional Hermes cron relay. Its compose images are unchanged; the ntfy message cache is kept, and the new marks state lives in a new volume.
- **0.3.72 — Wizard UX: 59 first-parent merges after `d53b2b24`**, listed below.
  - Several are **features**: the desktop heads-up chat (#656, #661, #665, #667), Response style (#631, #659), inline agent screenshots (#628), live tool steps (#600), Settings and previews as desktop windows (#588), edge peek (#560), the inbox tweak capability (#609, #619) and Machines on Home (#642).
  - Four were labelled `needs: james review` and are already merged on main: #604, #600, #588 and #560.
  - The rest are fixes: Stop on send (#649, #651), no doubled replies (#607), held late messages (#660, #662), reconnecting pill (#638), workspace sync between phones (#654) and others.

Agent Service stays `b1f8d2c1`. The shell features that pair with newer Agent Service PRs degrade gracefully on it:
- Response style needs AS #214/#230. On this guest `/wizard/v1/settings` has no `response_style`, so the shell says "Update your Wizard to choose a response style".
- Inline screenshots (#628) need AS #211, the diagnosed sign-in path (#603) needs AS #200, and live tool steps (#600) need AS #205+. Without those, they stay off.

**Classification: feature** (DECISIONS #93 launch-phase fast-track), not fix. The release is cut for a fix, but it carries feature ride-alongs.

### Wizard UX first-parent merges d53b2b24..970378b2

```
970378b2 Merge pull request #670 from humanitylabs-org/fix/pins-sync-merge
fb55c3b1 Merge pull request #667 from humanitylabs-org/feature/hud-desk1-own
09b93949 Miguel tweak: Resolve this does what the notification calls for (#666)
a577c51d Merge pull request #665 from humanitylabs-org/feature/hud-simplify
0607797d Merge pull request #659 from humanitylabs-org/settings/own-reply-style
6c38a250 Keep late held replies visible in scoped Chats lists (#662)
c833fe85 Merge pull request #661 from humanitylabs-org/feature/desktop-hud-keys
c9a3c25b Hold chat messages older than six hours for owner Send or Discard (#660)
5d0a215c Merge pull request #657 from humanitylabs-org/fix/hud-opaque-orb-sleep
23bd14c6 Merge pull request #654 from humanitylabs-org/fix/two-phone-workspace-sync
c8fb4d4f Merge pull request #656 from humanitylabs-org/feature/desktop-chat-hud
ff6d175e Owner app updates never forget their Wizard when an offline phone skips migration (#653)
ab7cb382 Merge pull request #651 from humanitylabs-org/fix/stop-no-recovery-card
4ce0ff29 Merge pull request #649 from humanitylabs-org/fix/stop-on-send
29f2d577 Merge pull request #647 from humanitylabs-org/feat/bracket-window-walk
cea5fcdd Model switch folds into one chip when squeezed (#646)
39b27467 Merge pull request #645 from humanitylabs-org/miguel/notif-in-order
3781ae1c Merge pull request #642 from humanitylabs-org/feature/machines-people-left
0dfe9900 Merge approved white orb icon and centre-dot fix (James, 27 Oct 2026)
91df7859 App kinds: Connectors follow the app's declared type (#640)
350647cc Fingerprint vault: replacing a secret never erases the saved one (#570)
06997cbb Merge pull request #545 from humanitylabs-org/chore/phone-train-to-main
f1dce946 Merge pull request #638 from humanitylabs-org/fix/reconnecting-pill
2f535005 Merge pull request #637 from humanitylabs-org/fix/mizel-violet-orb
88629be0 Merge pull request #634 from humanitylabs-org/fix/live-red-tests-20261027
e5cf115d Merge pull request #631 from humanitylabs-org/feature/owner-response-style
4f50011b Merge pull request #628 from humanitylabs-org/feature/inline-agent-screenshots
14a6b1d7 Merge pull request #629 from humanitylabs-org/fix/one-running-activity
7cc8fa3f Merge pull request #626 from humanitylabs-org/fix/mizel-phone-polish
afda2da1 Merge pull request #620 from humanitylabs-org/tweak/miguel-machines-home
a19f5308 Merge pull request #623 from humanitylabs-org/fix/no-hidden-done-keys
b42da7a8 Merge pull request #624 from humanitylabs-org/fix/bracket-chips-own-row
c9ae9013 Merge pull request #622 from humanitylabs-org/miguel/notif-keys
59b7d829 Merge pull request #621 from humanitylabs-org/feat/desk-steps-no-wrap
9bcb78fd Merge pull request #619 from humanitylabs-org/miguel/notif-threads
cc8f8baa Merge pull request #618 from humanitylabs-org/feat/keys-guide-more
f5f2e737 Merge pull request #607 from humanitylabs-org/fix/stream-double-reply
b338b90e One diagnosed sign-in path, no Retry, and automatic reply return (#603)
769fa4b9 Merge pull request #617 from humanitylabs-org/miguel/unified-inbox-fab
80e14007 Merge pull request #616 from humanitylabs-org/fix/keys-guide-tweaks
6a728fe5 Merge pull request #614 from humanitylabs-org/miguel/unified-inbox-dock
aae496c2 Merge pull request #612 from humanitylabs-org/skin/landscapes-85-glass
a341a383 Merge pull request #613 from humanitylabs-org/feat/keys-guide-in-place
699a500a Merge pull request #609 from humanitylabs-org/miguel/unified-inbox
ee2f9182 Merge pull request #560 from humanitylabs-org/feat/edge-peek-default
6ecdc11c Merge pull request #611 from humanitylabs-org/fix/keys-guide-overlap
464ee2d5 Merge pull request #600 from humanitylabs-org/fix/live-tool-steps
6b9b8774 Merge pull request #604 from humanitylabs-org/ux/update-wording
a5f1dec9 Merge pull request #608 from humanitylabs-org/feat/desktop-arrows-done-snooze
6aa1040e Merge pull request #606 from humanitylabs-org/fix/mizel-desktop-polish
9ff148fa Merge pull request #602 from humanitylabs-org/feat/desktop-pick-anything
8373f83c Merge pull request #599 from humanitylabs-org/fix/sheet-close-44px
b453d36d Merge pull request #601 from humanitylabs-org/feat/desktop-home-backquote
4aef40d2 Merge pull request #598 from humanitylabs-org/fix/desktop-ready-simplify
3dad62e9 Merge pull request #597 from humanitylabs-org/fix/archive-select-sync
717b2ed5 Merge pull request #588 from humanitylabs-org/pr/settings-preview-windows
da3920e9 Merge pull request #584 from humanitylabs-org/pr/kit-design-rules-v0
a67bd279 Merge pull request #595 from humanitylabs-org/fix/desktop-builtin-mic-and-send-focus
c0289e02 Merge pull request #592 from humanitylabs-org/fix/offline-banner-stale-probe
```

## Evidence: installed upgrade 0.3.68 → 0.3.72 on a disposable KVM guest

**Rig.** A disposable KVM guest on oscar-main:
- Ubuntu 24.04 noble cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH forward.
- Root stock **Hermes v0.22.5** from the official `install.sh --skip-setup`, then `hermes gateway install`.
- Tailscale 1.104.4 joined to a local **headscale v0.29.6** (`tailscale up --login-server=http://10.0.2.2:8089`, approved with `headscale auth register`), tailnet IP 100.72.0.1.
- Headscale cannot issue HTTPS certificates, so a test-only `/usr/local/bin/tailscale` wrapper reported `CertDomains` and accepted `tailscale cert`. This simulates an owner who has already turned HTTPS on.
- Serve stays unavailable (headscale 501), so the installs end box-only.

Nothing ran on the owner's box or on any customer box.

**Install 0.3.68.** Public command: `curl -fsSL https://aiwizards.com/os.sh | WIZARD_RELEASE=0.3.68 WIZARD_STRICT=1 bash -s start`. os.sh sha256 `fa9271d0…` = wizard-app-manager main `get.sh`.
- 04:16:41 → 04:23:59 UTC, `done`.
- `release.json`: 0.3.68 pinned, 27 checks, 0 failed.
- `wizard doctor` and `wam doctor`: 0 FAIL.

**Negative control on 0.3.68 (UX `5b661b07`).** Two Playwright browser contexts on the guest's shell: a desktop context and a 390×844 mobile one. The script is `race.mjs` with three synthetic thread ids, because the guest has no chats; pin ids are opaque strings to the pin store.

```
ids [ 'qa-pin-1', 'qa-pin-2', 'qa-pin-3' ]
FAIL both pins survive on server ["qa-pin-2"]
FAIL B sees both ["qa-pin-2"]
PASS unpin elsewhere not undone ["qa-pin-2","qa-pin-3"]
FAIL phone resume pulls pins ["qa-pin-2","qa-pin-3"]
cleanup [] fails 3
```

**Upgrade.** `curl -fsSL https://aiwizards.com/os.sh | WIZARD_RELEASE=0.3.72 WIZARD_STRICT=1 bash -s start`, after both repos' main had 0.3.72 and the public raw mirror served sha256 `0bf3563e…`.
- 04:30:41 → 04:33:29 UTC (about 3 min), `done`.
- `release.json`: **0.3.72 pinned, 27 checks, 0 failed**, App Manager `08b54f65`.
- `wizard doctor` 0 FAIL, `wam doctor` 0 FAIL.
- The install log reports `Hermes API answers`, `Wizard shell answers`, `shell reaches this Hermes` and a live bridge request (37 tools).
- Troubleshooter `degraded` only because Serve returns 501 on headscale (infra limit, same as promote-0.3.68.md).

**Preserved.**
- Hermes `config.yaml` (`13a542c3…`), `.env` (`71aee953…`) and `SOUL.md` (`36c1f5a2…`) are identical before and after the upgrade.
- Hermes is still v0.22.5; the gateway is active and API `/health` is 200.

**Running images after the upgrade.**
- UX `sha256:d1b00210…` (was `5b661b07…`), recreated 04:32:40.
- Notifications front + engine recreated for wizard10.
- runtipi and the release index were recreated.
- Agent Service `59cc1672…`, ChatGPT `72be4ede…`, Claude `7e795608…`, Files, Browser, Secret Drop, Transcriber, Voice and Connection Router kept their containers (same StartedAt).

**Notifications data.** The 3 messages posted on 0.3.68 are all listed after the upgrade. `POST /notifications/api/mark {read:true}` returned 200 `{"changed": 1}`, and unread went 3 → 2. The 0.3.71 cut's 🟡 (marks 500 after an update until restart, wizard-app-manager #285) did **not** reproduce on this root alongside upgrade. Its fix (#286) is on WAM main, not in this release's App Manager.

**The pins symptom after the upgrade** (same script, run twice):

```
ids [ 'qa-pin-1', 'qa-pin-2', 'qa-pin-3' ]
PASS both pins survive on server ["qa-pin-1","qa-pin-2"]
PASS B sees both ["qa-pin-1","qa-pin-2"]
PASS unpin elsewhere not undone ["qa-pin-2","qa-pin-3"]
PASS phone resume pulls pins ["qa-pin-3"]
cleanup [] fails 0
```

The second run gave the same 4/4 PASS.

**Shell render.** The upgraded shell was rendered in phone (402×874) and desktop (1440×900) Chromium with 0 page errors. Phone Home shows the AI widget; Chats opens on desktop. Server meters read "Unavailable" through the forwarded test view, as in promote-0.3.68.md.

### Tests

- wizard-ux #670: CI green before merge; the main publish run is listed above.
- `tools/check_release.py releases/0.3.72.json` (online): ok. `tools/tests`: 229 OK (18 skipped), run locally. The self-hosted wizard-os runner is offline today.
- WAM release tests: 83 passed. wizard-app-manager #295 CI green; Codex review: no findings.

## Not covered

- A real Tailscale control plane, real HTTPS certificates and Serve links (headscale plus the test wrapper).
- Real chats: the pin checks used synthetic thread ids. Real provider sign-ins, a physical phone, and two real devices on a real tailnet were also not covered.
- Fresh install of 0.3.72; only the upgrade from current Stable was run.
- Backup/restore/Undo. App Manager `08b54f65` has been on Latest since 0.3.69.
- The alongside host plugin installs from Agent Service main HEAD (`pinned: false`), which is pre-existing behaviour.

Rollback: point `releases/stable` back at 0.3.68 in both repos. It has a valid promotion record.
