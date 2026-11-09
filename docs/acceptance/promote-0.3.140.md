# Promote 0.3.140: the Troubleshooter guardian repairs by default on Stable

## Decision and scope

James (9 Nov 2026) approved making the guardian act by default on every box (he replied "defaults" after the explanation of what it fixes on its own: restart a broken link, undo a fresh Agent Service update that broke it, start a repair).

Classification: **feature** (`--fast-track --classification feature`, DECISIONS #93).

0.3.140 is Stable 0.3.134 plus exactly one component move (cut in wizard-os #482, merge 171e9d9; `releases/0.3.140.json` sha256 `07cda908d8a92df9340accabfc2f6ff15b43891ad11a7e5d3dc4232023bfa9c8`):

| Component | 0.3.134 | 0.3.140 | Change |
|---|---|---|---|
| App Manager (host tooling) | `525e9d3d` | `9f793620` | wizard-app-manager#542: `wam troubleshooter` writes `GUARDIAN_ACT=1` on fresh installs and on boxes whose host.env holds the old App Manager default; `wam troubleshooter --report-only` keeps it report-only (saved in `~/.wizard-os/guardian.json`, kept across updates), `--act` turns repairs back on; a hand edit of host.env after this version is kept as the owner's choice; hand-installed Troubleshooters untouched. |
| App Manager image | `v4.10.2-wizard.993-4ef2963` | `v4.10.2-wizard.1052-17c8d9c` | Newest published main image (source_commit 17c8d9cd, `check_release` proves no image input changed up to 9f793620). Latest has run this image since 0.3.104 (6 Nov). |

The App Manager move also carries every App Manager main PR between the two commits, which Latest has been running (merged PRs other than release mirrors):

- Strong suggestion: the Troubleshooter guardian repairs new boxes by itself; an owner's report-only choice survives updates
- Recommended fix: make owner feature switches reachable through the private gateway
- Recommended fix: alongside installs keep the existing Docker access route
- Store Get and Settings routes (Updates, About compare, Connections) work behind the private gateway (proof-gated :7792 listener)
- Recommended fix: bound source-link expansion during backups
- Recommended fix: preserve source backups and recover safely from restore failures
- Recommended fix: About shows how far behind main even when the diff is huge
- Recommended fix: back up source contexts so restored apps can start
- Strong suggestion: Settings › About can say how far the shell is from main (store-install/_main-compare, wizard-ux#887 rule 5)
- Strong suggestion: carry wizard.md home_screen into apps.json
- Recommended fix: builder restore accepts its emitted revision
- Recommended fix: preserve local builder rules when activating instant feedback
- Recommended fix: builder actions respond before waiting for I/O
- wam doctor: an alternative slot provider is the owner's choice, not a FAIL
- Recommended fix: build private apps from the correct source folder
- Recommended fix: delegated box commands load current code
- Recommended fix: Builder bundle runs box commands through the box's own wam; doctor flags bundle drift
- Recommended fix: wam links never silently downgrades a same-origin app to its raw port

Every other pin (Wizard UX, Agent Service, Troubleshooter 9088a25, default apps, Hermes) is byte-for-byte 0.3.134.

Why now: fresh installs and Stable boxes should fix a broken link to the agent by themselves instead of only reporting it.

Risk: the guardian acts on the box (bounded restarts, an undo of a fresh Agent Service update that broke the link, a repair through the box's AI connection). Owners who want it off run `wam troubleshooter --report-only`. Rollback below.

Correction: the `components.wizard-troubleshooter.note` inherited unchanged from 0.3.134 into 0.3.140 still says the guardian timer is installed "report-only". That is out of date from App Manager 9f793620 on; release files are immutable, so it is corrected here and in wizard-app-manager `releases/README.md`.

## Verification

- wizard-app-manager#542 (merged 9f79362): CI green (test, backend, builder-verify, gitleaks, CodeQL, agent review); `tests/test_troubleshooter_native.py` + `test_troubleshooter_default.py` 24 passed locally, 8 new tests for the default, the upgrade from the old default, the saved report-only choice across reruns, hand edits (replaced and appended), dry run, the waiting install, hand-installed boxes. Codex's two findings fixed in e5d19b4.
- wizard-os #482 (the cut): `check_release.py` (online) ok for 0.3.140 and 0.3.141, `promote_stable.py check` ok, published-release tests 44 passed.
- Mirrored to wizard-app-manager in #545 (`verify_mirror` byte-identical).


**Result: PASSED** (20261109T124415Z → 20261109T125729Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.23.0 (2026.9.24) · stable · local 2bd378ed1b8d) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: http://10.0.2.2:41699. os.sh sha256 `2ee8f5c8fc4386a9…`.

- Install 0.3.134 (public command, agent-run, `WIZARD_STRICT=1`): done in 566 s; release.json 0.3.134 pinned.
- Upgrade to 0.3.140: done in 124 s; release.json 0.3.140 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `f8eceb68…`, .env `b6f8c22e…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T12:52:18.577431414Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-11-09T12:52:18.438746907Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T12:50:09.608465122Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-11-09T12:50:09.484329887Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T12:52:55.762848764Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-11-09T12:52:55.945597071Z
runtipi sha256:e92d0564b04e08949a1ce84576da584b53ce00f6f3b27e3b7e79d1662063e7f8 2026-11-09T12:56:08.952235803Z
runtipi-db sha256:834a046089d76edd1d2e81c4741f3ad5d1853646ededc86c2708936aad31c1ed 2026-11-09T12:45:31.235905396Z
runtipi-queue sha256:8425b8435b0203e87292cf1a4a7e5f8108c610bbd8217f8cc952f43628b24987 2026-11-09T12:45:31.369212413Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-11-09T12:45:46.563114219Z
runtipi-wizard-release-index-1 sha256:e92d0564b04e08949a1ce84576da584b53ce00f6f3b27e3b7e79d1662063e7f8 2026-11-09T12:55:05.592228204Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T12:52:31.669792196Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-11-09T12:52:31.546553082Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T12:49:45.361958982Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-11-09T12:49:45.239451182Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:d1b9282dad321b20321582f6d7c0e32c88f07330c6e82ff029bd952129424ee4 2026-11-09T12:50:17.627779177Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T12:51:03.378216574Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:abe83ddb8fe1e54347f94b5057740ba5da2309691f20b5692db476967638b445 2026-11-09T12:51:03.23504382Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T12:51:46.159080527Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:e839af7cdc32c875fcefec9189ae4e29509ea78b3b52d922416285c9e2eb81bb 2026-11-09T12:51:46.002149087Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-11-09T12:53:35.565159498Z
wizard-ux_wizardapps-wizard-ux-1 sha256:b4785d8eef3d1aa9690fc0bafd7fa8de16da45aa67da99f291f26e4d81131efe 2026-11-09T12:50:28.999378464Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-11-09T12:53:26.493206828Z
```
</details>


### Guardian readback on the guest (extra, outside the rig's gate)

| | GUARDIAN_ACT | marker line | wizard-guardian.timer | Troubleshooter status `guardian` |
|---|---|---|---|---|
| Before (0.3.134) | `0` | 0 | active | none (older App Manager) |
| After (0.3.140) | `1` | 1 | active | `{"act": true, "set_by": "default"}` |

The upgrade turned the old default into repairs on, with no owner choice invented (`~/.wizard-os/guardian.json` absent).

Report files (private forum scratch, run `20261109T124415Z-0.3.134-to-0.3.140`, job heavy_ed335aad): `report.md` sha256 `e214e7e9a2f564c40699e6775360a96bd54f06fa568c832dbb77883d812fb7c4`, `report.json` sha256 `5a2a76c6c2bf33b4665d517151775c2520effb10e31e57d5747adb2bacd48991`, `guardian.json` sha256 `2e40b3e9324be124525e1f52f4190c6897be9a190198f70d8d7a90e3c0e56989`.

**Disclosed:** the 0.3.134 install used the public mirror; the 0.3.140 candidate was served by the rig from wizard-os main at 171e9d9 (`releases/0.3.140.json` sha256 `07cda908…`, identical to the mirrored file), not fetched from the public mirror. A wrapper added only the guardian readback above; the rig ran unchanged. The first attempt (heavy_8c5be0b9) failed before any product step because its deep workdir made the QMP socket path too long for qemu; fixed in wizard-os #483, the rerun used a short workdir.

## Not checked / caveats

- The rig has no Tailscale Serve, so the Troubleshooter reports `degraded` (not mounted on every shell address: Serve 501) before and after; known rig limit, not a release failure.
- The guardian was not made to repair anything on the rig (no injected fault); its acting code is unchanged Troubleshooter 9088a25, already on Stable in report-only mode.
- Not run: a fresh install of 0.3.140, real Tailscale/HTTPS/Serve, real chats and sign-ins, phones.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted` (Update now still works).

Rollback: point `releases/stable` back at 0.3.134 in both repos (it has a valid promotion record). A single box: `wam troubleshooter --report-only`.
