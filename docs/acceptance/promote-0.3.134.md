# Promote 0.3.134: Troubleshooter 9088a25 (self-sufficient recovery) on Stable

## Decision and scope

Classification: **feature** (`--fast-track --classification feature`, DECISIONS #93): Troubleshooter #36/#38/#42 add owner-approved repair plans with backups and Undo, on by default. The rest of #24–#42 are fixes to the Troubleshooter's own recovery paths.

0.3.134 is Stable 0.3.102 plus exactly one pin change (cut in wizard-os #474, merge 8402c55; `releases/0.3.134.json` sha256 `1ae716ae8e360a199cf731fd7981aacd3c45d05bb7a3aa108a7e43add8e23b4c`):

| Component | 0.3.102 | 0.3.134 | Change |
|---|---|---|---|
| Troubleshooter (host tooling, no image) | `3e56f66d` | `9088a254` | #24 Agent Service repaired through App Manager; #25 James's one-tap repair screen restored; #26 the guardian only undoes an update when the link was healthy before it; #29 the guardian heals app addresses; #34 busy is not down, a restart that didn't hold is not repeated; #35 HEAD answers so the shell opens the real Troubleshooter; #36/#38 owner-approved repair plans with backups and Undo; #39 replies that never start are an incident, owner can restart Hermes while it looks green; #40 WizardOS spelling; #41 an approved Hermes restart actually runs; #42 bounded Hermes restart (drain stops waiting, gateway restarted), Restart now, crash-loop handoff, reply keeper check, repair plans on by default, the page watches itself. |

Every other pin is byte-for-byte 0.3.102. The guardian stays report-only: `wam troubleshooter` still writes `GUARDIAN_ACT=0`; nothing in this release changes that default. Latest testers already have the same pin (0.3.135, 0.3.136).

Why now: fresh installs and Stable boxes should get the Troubleshooter that can recover a locked-out box on its own (a hung Hermes drain, a crash loop, replies that never start) without someone on a console.

Risk: host tooling only (user systemd units); no image, route or permission changes in the Wizard shell. Repair plans run only after the owner approves each plan, take a backup first and offer Undo.

## Verification

- Troubleshooter wizard-troubleshooter#42 (head of main 9088a25): CI green (test, CodeQL).
- wizard-os #474 (the cut): review, contracts and Wizard style checks green; `check_release.py` ok at cut time.
- Mirrored to wizard-app-manager in #536 (`verify_mirror` byte-identical); the public mirror serves `releases/0.3.134.json` with the same sha256 `1ae716ae…`.

### Installed upgrade 0.3.102 → 0.3.134 on a disposable KVM guest

**Result: PASSED** (20261109T102613Z → 20261109T103918Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.23.0 (2026.9.24) · stable · local 2bd378ed1b8d) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: http://10.0.2.2:40523. os.sh sha256 `2ee8f5c8fc4386a9…`.

- Install 0.3.102 (public command, agent-run, `WIZARD_STRICT=1`): done in 550 s; release.json 0.3.102 pinned.
- Upgrade to 0.3.134: done in 123 s; release.json 0.3.134 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `f8eceb68…`, .env `a62ea1e5…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T10:34:08.336415193Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-11-09T10:34:08.192562502Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T10:32:00.967820823Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-11-09T10:32:00.854573493Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T10:34:45.137766505Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-11-09T10:34:45.297190442Z
runtipi sha256:f116feb1e4aa2fbd2a84eae9dbdc006e120092cfce80d7e05c9ae4714d0548e9 2026-11-09T10:38:06.015813029Z
runtipi-db sha256:834a046089d76edd1d2e81c4741f3ad5d1853646ededc86c2708936aad31c1ed 2026-11-09T10:27:32.992517869Z
runtipi-queue sha256:8425b8435b0203e87292cf1a4a7e5f8108c610bbd8217f8cc952f43628b24987 2026-11-09T10:27:32.852559309Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-11-09T10:27:48.283980903Z
runtipi-wizard-release-index-1 sha256:f116feb1e4aa2fbd2a84eae9dbdc006e120092cfce80d7e05c9ae4714d0548e9 2026-11-09T10:37:02.717676681Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T10:34:21.178165744Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-11-09T10:34:21.042774343Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T10:31:39.932188373Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-11-09T10:31:39.814699943Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:d1b9282dad321b20321582f6d7c0e32c88f07330c6e82ff029bd952129424ee4 2026-11-09T10:32:09.148688155Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T10:32:54.421647629Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:abe83ddb8fe1e54347f94b5057740ba5da2309691f20b5692db476967638b445 2026-11-09T10:32:54.271384267Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-09T10:33:37.259750836Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:e839af7cdc32c875fcefec9189ae4e29509ea78b3b52d922416285c9e2eb81bb 2026-11-09T10:33:37.105180696Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-11-09T10:35:24.651243703Z
wizard-ux_wizardapps-wizard-ux-1 sha256:b4785d8eef3d1aa9690fc0bafd7fa8de16da45aa67da99f291f26e4d81131efe 2026-11-09T10:32:19.626075352Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-11-09T10:35:16.661734014Z
```
</details>

Report files (private forum scratch, run `20261109T102613Z-0.3.102-to-0.3.134`): `report.md` sha256 `23ed4939f16430a04688a46cb26e85932dadb3143fe081e2d30b3dd407489e23`, `report.json` sha256 `32ef3941494f8b0896a5349efb2e5b01cb404f16319cfa4486a623aaedd6e525`.

**Disclosed:** the 0.3.102 install used the public mirror; the 0.3.134 candidate was served by the rig from wizard-os main at 8402c55 (`releases/0.3.134.json` sha256 `1ae716ae…`, identical to the file the public mirror now serves), not fetched from the public mirror. The run used a harness wrapper on forum that starts qemu through `sg kvm` instead of `systemd-run --user` (forum's user manager lacks the kvm group); the rig itself was unchanged (fixed in `kvm_upgrade.py` separately).

## Not checked / caveats

- The rig has no Tailscale Serve, so the installer reports the Troubleshooter as running but not mounted on every shell address (known rig limit, not a release failure). The installed Troubleshooter commit was not read back on the guest (the release checks cover App Manager, images and default apps, not host tooling).
- Not run: a fresh install of 0.3.134, real Tailscale/HTTPS/Serve, real chats and sign-ins, phones, a live repair plan on the rig.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted` (Update now still works).

Rollback: point `releases/stable` back at 0.3.102 in both repos (it has a valid promotion record).
