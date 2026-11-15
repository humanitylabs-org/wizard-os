# Promote 0.3.240: big app updates are waited for and never left stopped (wizard-app-manager#711) reach For everyone

## Decision and scope

Miguel (15 Nov 2026) approved shipping the App Manager update-timeout fix to every Wizard ("Ship"). Classification: **fix** (`--fast-track --classification fix`, DECISIONS #82: a fix release with regression tests and a passed upgrade test from the current Stable goes to Stable the same day).

0.3.240 is Stable 0.3.143 plus exactly one component move (cut in wizard-os #651, merged b8fd3bbc at 2026-11-15T14:10:25Z; `releases/0.3.240.json` sha256 `06968e2880c394db5cc7c477164501bba2f9d3181beedf7a37d8410da369cbf9`), the same way 0.3.143 was 0.3.134 plus one App Manager move:

| Component | 0.3.143 | 0.3.240 | Change |
|---|---|---|---|
| App Manager (host tooling) | `7d60346f` | `5fe14045` | wizard-app-manager#719 on `maintenance/stable-0.3.143-app-manager`: backport of #712 (host half) + #716 onto 7d60346f, nothing else. |
| App Manager image | `v4.10.2-wizard.1052-17c8d9c` | `v4.10.2-wizard.1326-db21345` | Published main image (run 43700409162), the one Latest runs since 0.3.238. `check_release`: built from db2134549fd9; no image input changed up to 5fe14045. |

Every other pin (Wizard UX, Agent Service, Troubleshooter 9088a25, default apps, Hermes) is byte-for-byte 0.3.143.

What it fixes (#711: a big Messenger update outlasted Runtipi's 5-minute queue timeout, ran up to 3 times and was left stopped on its old version):

- **#712 backend (in the image):** an install/update RPC is sent once (no re-publish on timeout), gets max(QUEUE_TIMEOUT_IN_MINUTES, 30) minutes, and the real late result is kept; the status sync leaves an app that is `updating` alone.
- **#712 host half (wam/cli.py):** wam waits 2 × max(QUEUE_TIMEOUT_IN_MINUTES, 30) min + 100 s and never starts an app Runtipi still reports `updating`.
- **#716:** Store/Tracker **Start** for an app an update left stopped; a Store update is refused (409) while Runtipi still runs one for that app; an update that leaves the app stopped reports failed.

Rides along in the image (its inputs differ from 0.3.143's image by exactly these merged PRs, all Recommended fixes or maintenance that Latest has run for days): #693 (an update keeps the code its running containers use until the new ones are up), #592 (app start/update no longer opens the Agent Service grant keys to everyone), #554 (Node 22.23.5 runtime).

## Verification

- **wizard-app-manager#719** (merged 5fe14045; CI green: test, backend, builder-verify, gitleaks, image build amd64+arm64, CodeQL, review):
  - Fail-first: `tests/test_update_queue_timeout.py` against 0.3.143's wam/cli.py: **3 failed, 1 passed**; with the backport 4 passed. `pytest tests/test_store_start.py tests/test_update_queue_timeout.py tests/test_store_install.py`: 36 passed.
  - Full host suite: 0.3.143's App Manager 7d60346f gives 4 failed, 3216 passed (environment-dependent tests on oscar-main); the candidate's result is in the promotion PR.
  - One Codex P1 (the backend still reports failure after a second full timeout, i.e. an update running > 60 min): same code as main #712, so not fixable here without leaving the published image; filed as wizard-app-manager#720.
- `tools/check_release.py releases/0.3.240.json` (online): ok. `promote_stable.py check`: channels ok.

### Installed upgrade 0.3.143 → 0.3.240 on a disposable KVM guest — PASSED

Rig: `tools/acceptance/upgrade-rig/kvm_upgrade.py run --from 0.3.143 --to 0.3.240` on oscar-main (the release train's KVM rig: Ubuntu 24.04 cloud-image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH; root stock Hermes v0.23.1 (2026.9.24) from the official installer + `hermes gateway install`; Tailscale on a local headscale with a pre-auth key; a test-only `tailscale` wrapper simulates HTTPS on). Nothing ran on a real box. Run `20261115T135344Z-0.3.143-to-0.3.240` (13:53:44Z → 14:08:40Z UTC).

- Install 0.3.143 (public command `curl -fsSL https://aiwizards.com/os.sh | … WIZARD_RELEASE=0.3.143 WIZARD_STRICT=1 bash -s start`, agent-run): done in 630 s; release.json 0.3.143 pinned.
- Upgrade to 0.3.240: done in 139 s; release.json 0.3.240 pinned (App Manager commit 5fe140450bf56e3f236a13e726e6660929a7017b), **27 checks, 0 failed**, `problems: []`.
- Hermes config.yaml / .env / SOUL.md identical before and after (config.yaml `d3bffbdb…`, .env `9090839e…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0. Maintenance helper root before and after.
- `runtipi` and `runtipi-wizard-release-index-1` run image `sha256:de348b282d29c78e14bd11e06a4dc508935b9356307c7777686b31ed5c3cb035` (the pinned db21345 image) after the upgrade; Wizard UX `b4785d8e…` and Agent Service `d1b9282d…` unchanged from 0.3.143.

Report files (private, oscar-main `~/.cache/wizard-release-train/rig/runs/20261115T135344Z-0.3.143-to-0.3.240/`): `report.md` sha256 `27b8c806a189670b66b2f63f1bcc03cc1511202f49aa95f2f37226427a40b683`, `report.json` sha256 `90bff1c9c39448ab00b7b119796eb987b6ae0d8ac623442ccf3d27fc58eba70b`.

**Disclosed:** the 0.3.143 install used the public mirror. The 0.3.240 candidate was served to the guest by a loopback server (`WIZARD_RELEASE_BASE=http://10.0.2.2:45331`) from wizard-app-manager main's `releases/` plus `0.3.240.json` from the head of wizard-os #651 (sha256 `06968e28…`, identical to the file merged to wizard-os main in b8fd3bbc and to the mirror in wizard-app-manager#724). The rig ran unchanged.

## Not checked / caveats

- The rig has no Tailscale Serve, so installs end box-only; known rig limit.
- No real > 30-minute app update was run on the guest; the #711 behaviour is proven by the unit tests above (both halves), and the guest proves the upgrade path and that the new App Manager image and host tooling come up healthy.
- Not run: a fresh install of 0.3.240, real Tailscale/HTTPS/Serve, real chats and sign-ins, phones.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted` (Update now still works).

Rollback: point `releases/stable` back at 0.3.143 in both repos (it has a valid promotion record).
