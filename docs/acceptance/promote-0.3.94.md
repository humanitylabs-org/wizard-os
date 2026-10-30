# Promote 0.3.94 (release train)

## Why

Stable 0.3.90 lacked merged Recommended fixes:

- humanitylabs-org/wizard-ux#757 Recommended fix: Store can remove an installed app
- humanitylabs-org/wizard-ux#758 Recommended fix: model picker stays clear of draft text
- humanitylabs-org/wizard-ux#761 Recommended fix: the Welcome never switches skin on its own; picking sets only the skin
- humanitylabs-org/wizard-ux#762 Recommended fix: model switch recovers when ChatGPT models briefly drop out
- humanitylabs-org/wizard-ux#763 Recommended fix: a greyed model or stopped AI reading opens its app at Reconnect
- humanitylabs-org/wizard-ux#764 Recommended fix: title-bar tools get search, QR and settings icons and an attention dot
- humanitylabs-org/wizard-agent-service#281 Recommended fix: show and change which subscription the agent uses first
- humanitylabs-org/wizard-agent-service#282 Recommended fix: an idle subscription's expired sign-in renews instead of blanking its usage meter
- humanitylabs-org/wizard-agent-service#283 Recommended fix: Use first is not offered where stock Hermes cannot apply it
- humanitylabs-org/wizard-app-manager#368 Recommended fix: keep an app behind an owner gateway on its Wizard path
- humanitylabs-org/wizard-ux#765 [feature, owner-approved] desktop keys; Miguel 30 Oct 2026: "Please ship this feature straight to stable!"

## What changes (0.3.90 → 0.3.94)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): it carries changes that are not provably fixes.

- wizard-ux#678 [feature] Strong suggestion: the phone app shows a loader at launch and walks the owner through Tailscale when it can't reach Wizard
- wizard-ux#755 [feature] Skins and tweaks: all skins in one list; tweaks by author with quick buttons
- wizard-ux#757 [fix] Recommended fix: Store can remove an installed app
- wizard-ux#758 [fix] Recommended fix: model picker stays clear of draft text
- wizard-ux#760 [feature] Keep pooled Claude route during account limits
- wizard-ux#761 [fix] Recommended fix: the Welcome never switches skin on its own; picking sets only the skin
- wizard-ux#762 [fix] Recommended fix: model switch recovers when ChatGPT models briefly drop out
- wizard-ux#763 [fix] Recommended fix: a greyed model or stopped AI reading opens its app at Reconnect
- wizard-ux#764 [fix] Recommended fix: title-bar tools get search, QR and settings icons and an attention dot
- wizard-ux#765 [feature] Strong suggestion (feel free to drop): desktop keys — ⌥N chat beside the app, ⌥− ⌥= width, ⌥⇧W reopen, ⌥Z back, ⌥L light/dark
- wizard-agent-service#276 [maintenance] Maintenance: register multiline composer parity
- wizard-agent-service#279 [feature] Fail saved Claude turn promptly when both grants cool down
- wizard-agent-service#280 [feature] Keep ready status normalization in Claude cooldown release
- wizard-agent-service#281 [fix] Recommended fix: show and change which subscription the agent uses first
- wizard-agent-service#282 [fix] Recommended fix: an idle subscription's expired sign-in renews instead of blanking its usage meter
- wizard-agent-service#283 [fix] Recommended fix: Use first is not offered where stock Hermes cannot apply it
- wizard-app-manager#365 [maintenance] Maintenance: mirror 0.3.90 onto latest
- wizard-app-manager#367 [maintenance] Maintenance: mirror Stable 0.3.90 promotion
- wizard-app-manager#368 [fix] Recommended fix: keep an app behind an owner gateway on its Wizard path

## Evidence

## Installed upgrade 0.3.90 → 0.3.94 on a disposable KVM guest

**Result: PASSED** (20261030T151322Z → 20261030T152652Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.90 (public command, agent-run, `WIZARD_STRICT=1`): done in 551 s; release.json 0.3.90 pinned.
- Upgrade to 0.3.94: done in 154 s; release.json 0.3.94 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `b8077d98…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T15:21:14.504130634Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-30T15:21:14.390485301Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T15:19:04.489876435Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-30T15:19:04.376248272Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T15:21:51.94464028Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-30T15:21:52.094637699Z
runtipi sha256:ae8a65da8934dafb6a09ae5f1818c4266e402ca773daf70bcde382b5cfa03e9d 2026-10-30T15:25:00.728558639Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-30T15:14:50.184810179Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-30T15:14:50.046996263Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-30T15:15:05.553826647Z
runtipi-wizard-release-index-1 sha256:ae8a65da8934dafb6a09ae5f1818c4266e402ca773daf70bcde382b5cfa03e9d 2026-10-30T15:23:57.445695313Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T15:21:26.144262609Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-30T15:21:26.032444453Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T15:18:40.302420214Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-30T15:18:40.181500952Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:db28b87552c6874e3bf2713b22ff993aaeffe3eea53ea068449b5d3afe168274 2026-10-30T15:25:48.672624061Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T15:20:01.470635833Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:abe83ddb8fe1e54347f94b5057740ba5da2309691f20b5692db476967638b445 2026-10-30T15:20:01.307147555Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T15:20:41.481924672Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:e839af7cdc32c875fcefec9189ae4e29509ea78b3b52d922416285c9e2eb81bb 2026-10-30T15:20:41.34813302Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-30T15:22:30.456640725Z
wizard-ux_wizardapps-wizard-ux-1 sha256:d70516e49002e9ed0583982dfb3d2a241852b471cf2729909f39acd51127ad1d 2026-10-30T15:25:42.302666202Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-30T15:22:20.799963362Z
```
</details>
