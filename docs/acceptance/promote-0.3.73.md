# Promote 0.3.73 (release train)

## Why

Stable 0.3.72 lacked merged Recommended fixes:

- humanitylabs-org/wizard-ux#674 Recommended fix: Spaces and subject order keep every device's edit
- humanitylabs-org/wizard-ux#675 Recommended fix (performance): Settings says 'Takes about 2 minutes' when only the interface image changes
- humanitylabs-org/wizard-ux#676 Recommended fix: an unreachable Wizard on Tailscale says what to check instead of 'No internet', and Troubleshoot opens the phone app's guide
- humanitylabs-org/wizard-agent-service#205 Recommended fix: serve live run events for model-locked turns (events were 404 for every Wizard turn)
- humanitylabs-org/wizard-agent-service#206 Recommended fix: archive window honours the Auto-archive choice
- humanitylabs-org/wizard-agent-service#214 Recommended fix: owners choose Summary or Concise replies
- humanitylabs-org/wizard-agent-service#219 Recommended fix: bring live fixes onto main: dismissed errors stay dismissed, faster Chats list, live step updates
- humanitylabs-org/wizard-agent-service#221 Recommended fix: apps list carries declared type and category
- humanitylabs-org/wizard-agent-service#237 Recommended fix: every picture or file an agent sends shows in chats
- humanitylabs-org/wizard-agent-service#238 Recommended fix: shared lists keep every device's edit (item operations on ui-preferences)
- humanitylabs-org/wizard-agent-service#243 Recommended fix: Setup stops saying a phone is connected once the last phone leaves the tailnet

## What changes (0.3.72 → 0.3.73)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): it carries changes that are not provably fixes.

- wizard-ux#671 [feature] Mizel: Landscapes Light and Landscapes Dark
- wizard-ux#674 [fix] Recommended fix: Spaces and subject order keep every device's edit
- wizard-ux#675 [fix] Recommended fix (performance): Settings says 'Takes about 2 minutes' when only the interface image changes
- wizard-ux#676 [fix] Recommended fix: an unreachable Wizard on Tailscale says what to check instead of 'No internet', and Troubleshoot opens the phone app's guide
- wizard-agent-service#200 [feature] Diagnosed provider sign-in: one fix path and bounded same-model resend
- wizard-agent-service#205 [fix] Recommended fix: serve live run events for model-locked turns (events were 404 for every Wizard turn)
- wizard-agent-service#206 [fix] Recommended fix: archive window honours the Auto-archive choice
- wizard-agent-service#210 [feature] Replies: replace rigid finish-report template with a concise-prose rule
- wizard-agent-service#211 [feature] Strong suggestion: show agent screenshots where the reply discusses them
- wizard-agent-service#214 [fix] Recommended fix: owners choose Summary or Concise replies
- wizard-agent-service#219 [fix] Recommended fix: bring live fixes onto main: dismissed errors stay dismissed, faster Chats list, live step updates
- wizard-agent-service#220 [feature] Fix owned follow-up questions, schedule credit and done alerts
- wizard-agent-service#221 [fix] Recommended fix: apps list carries declared type and category
- wizard-agent-service#222 [feature] Land live release (owned open work check + recovery fixes) onto main
- wizard-agent-service#223 [feature] fix: acknowledge legacy heavy results once on upgrade
- wizard-agent-service#227 [maintenance] Maintenance: agent parity entry for Stop on send (wizard-ux#649)
- wizard-agent-service#230 [feature] Strong suggestion: Own response style sends Wizard OS facts only
- wizard-agent-service#233 [maintenance] Maintenance: parity entry for pinned chats sync
- wizard-agent-service#237 [fix] Recommended fix: every picture or file an agent sends shows in chats
- wizard-agent-service#238 [fix] Recommended fix: shared lists keep every device's edit (item operations on ui-preferences)
- wizard-agent-service#243 [fix] Recommended fix: Setup stops saying a phone is connected once the last phone leaves the tailnet

## Evidence

## Installed upgrade 0.3.72 → 0.3.73 on a disposable KVM guest

**Result: PASSED** (20261028T221127Z → 20261028T222438Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.72 (public command, agent-run, `WIZARD_STRICT=1`): done in 551 s; release.json 0.3.72 pinned.
- Upgrade to 0.3.73: done in 154 s; release.json 0.3.73 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `60a4182d…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-28T22:19:21.95053439Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-28T22:19:21.832820806Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-28T22:17:13.244376956Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-28T22:17:13.125134673Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-28T22:19:58.183435072Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-28T22:19:58.346789049Z
runtipi sha256:ff30d81d103c7ca408692fb25b98827d0fb382a8034e2bcbd0daf46b99547e39 2026-10-28T22:22:54.369594726Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-28T22:12:46.417578746Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-28T22:12:46.551545811Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-28T22:13:01.872531783Z
runtipi-wizard-release-index-1 sha256:ff30d81d103c7ca408692fb25b98827d0fb382a8034e2bcbd0daf46b99547e39 2026-10-28T22:21:51.086525147Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-28T22:19:33.948838759Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-28T22:19:33.82292899Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-28T22:16:50.565253856Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-28T22:16:50.455854908Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:dd204c42dbf37403e6b98ad1b3f3b2d9209609b639395188aded90b724803c3a 2026-10-28T22:23:41.534548758Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-28T22:18:08.003877311Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:72be4ede5a2e0151eea3a9050611352b0b14c044e56c1202a25442f4003552e3 2026-10-28T22:18:07.86174336Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-28T22:18:47.560568747Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:7e7956086a2f8810b46666e5948c71ffc2637e1e54566eaffb100fb8acdc406c 2026-10-28T22:18:47.422203496Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-28T22:20:34.302405634Z
wizard-ux_wizardapps-wizard-ux-1 sha256:314697acd8220a51bba598b8f51f24d1d7df8a31780b22ec9e16a5ad84fbe508 2026-10-28T22:23:37.75036571Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-28T22:20:28.123066585Z
```
</details>
