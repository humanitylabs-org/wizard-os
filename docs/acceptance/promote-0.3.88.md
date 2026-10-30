# Promote 0.3.88 (release train)

## Why

Stable 0.3.86 lacked merged Recommended fixes:

- humanitylabs-org/wizard-ux#712 Recommended fix: the Mac window buttons no longer cover the desktop bar
- humanitylabs-org/wizard-ux#745 Recommended fix: keep the mobile reload banner above Chats
- humanitylabs-org/wizard-ux#749 fix(landscapes): raise light Chats preview contrast
- humanitylabs-org/wizard-ux#750 Recommended fix: Welcome and Settings › Look say "color", not "colour"
- humanitylabs-org/wizard-ux#746 fix(chats): align accent controls with active palette
- humanitylabs-org/wizard-ux#747 fix(signal): improve Chats list text contrast
- humanitylabs-org/wizard-ux#748 fix(sepia): raise Chats status label contrast
- humanitylabs-org/wizard-ux#752 Recommended fix: keep multiline drafts editable
- humanitylabs-org/wizard-ux#753 Recommended fix: a closed desk no longer comes back from another device
- humanitylabs-org/wizard-ux#754 Recommended fix: Escape clears desktop Chats search before navigation
- humanitylabs-org/wizard-agent-service#272 Recommended fix: refuse history too new for the approved runtime
- humanitylabs-org/wizard-agent-service#274 Recommended fix: a finished queued run leaves Working at once
- humanitylabs-org/wizard-agent-service#275 Recommended fix: account changes can be on for one provider (WIZARD_ACCOUNT_CHANGES=chatgpt)

## What changes (0.3.86 → 0.3.88)

**Classification: fix** (every change is a Recommended fix or maintenance).

- wizard-ux#712 [fix] Recommended fix: the Mac window buttons no longer cover the desktop bar
- wizard-ux#745 [fix] Recommended fix: keep the mobile reload banner above Chats
- wizard-ux#746 [fix] fix(chats): align accent controls with active palette
- wizard-ux#747 [fix] fix(signal): improve Chats list text contrast
- wizard-ux#748 [fix] fix(sepia): raise Chats status label contrast
- wizard-ux#749 [fix] fix(landscapes): raise light Chats preview contrast
- wizard-ux#750 [fix] Recommended fix: Welcome and Settings › Look say "color", not "colour"
- wizard-ux#752 [fix] Recommended fix: keep multiline drafts editable
- wizard-ux#753 [fix] Recommended fix: a closed desk no longer comes back from another device
- wizard-ux#754 [fix] Recommended fix: Escape clears desktop Chats search before navigation
- wizard-agent-service#272 [fix] Recommended fix: refuse history too new for the approved runtime
- wizard-agent-service#274 [fix] Recommended fix: a finished queued run leaves Working at once
- wizard-agent-service#275 [fix] Recommended fix: account changes can be on for one provider (WIZARD_ACCOUNT_CHANGES=chatgpt)

## Evidence

## Installed upgrade 0.3.86 → 0.3.88 on a disposable KVM guest

**Result: PASSED** (20261030T011741Z → 20261030T013650Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.86 (public command, agent-run, `WIZARD_STRICT=1`): done in 917 s; release.json 0.3.86 pinned.
- Upgrade to 0.3.88: done in 154 s; release.json 0.3.88 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `bde40e1a…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T01:31:41.905876195Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-30T01:31:41.765662753Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T01:27:14.388293721Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-30T01:27:14.266222714Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T01:32:20.474603998Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-30T01:32:20.633225248Z
runtipi sha256:ae8a65da8934dafb6a09ae5f1818c4266e402ca773daf70bcde382b5cfa03e9d 2026-10-30T01:34:55.706561365Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-30T01:22:39.942973602Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-30T01:22:39.754479413Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-30T01:22:55.244772024Z
runtipi-wizard-release-index-1 sha256:ae8a65da8934dafb6a09ae5f1818c4266e402ca773daf70bcde382b5cfa03e9d 2026-10-30T01:33:52.470600751Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T01:31:54.796998425Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-30T01:31:54.676087682Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T01:26:47.765931357Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-30T01:26:47.631438103Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:e02d50a489240fd155f305c5768190f04cad232b852be127fc3693c04f1e3fe9 2026-10-30T01:35:46.185595716Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T01:28:17.401448399Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:bec542d1e4f11a9b8cd8a9efb733a563b93861b0549953e44bebcf6c986f8edc 2026-10-30T01:28:17.267857379Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T01:28:59.849626395Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:720058e1658c7870420dbb6414f6198eaaae1849058c4c8e18a518694f0be5a2 2026-10-30T01:28:59.705616587Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-30T01:32:57.437930064Z
wizard-ux_wizardapps-wizard-ux-1 sha256:2463c11b561b0b9fa3fe876f885e02f97a1e30c0273049f67682fc25683b1ca0 2026-10-30T01:35:40.226924596Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-30T01:32:49.192219749Z
```
</details>
