# Promote 0.3.436 (release train)

## Why

- 0.3.436 carries hotfix wizard-ux#1806, wizard-ux#1806, wizard-agent-service#632: hotfix lane (wizard-os#434), shortened soak with no open release-blocker issue, recorded as a fast-track.

## What changes (0.3.435 → 0.3.436)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): it carries changes that are not provably fixes.

- wizard-ux#1806 [feature] Strong suggestion: new owners connect Claude or ChatGPT first, private AI offered once after (switch wizard/standard-first-setup, off)
- wizard-agent-service#632 [feature] Strong suggestion: the Welcome's Set up private AI opts a box into private first (POST /wizard/v1/private-first {offer})
- wizard-agent-service#633 [fix] Recommended fix: removing a custom skin removes it on the box (Undo works, Files can delete skin folders)

## Evidence

## Installed upgrade 0.3.435 → 0.3.436 on a disposable KVM guest

**Result: PASSED** (20261126T214828Z → 20261126T220030Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.23.4 (2026.9.24) · stable · local 8fc037444731) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `e4e6a3c08ebe6bc4…`.

- Install 0.3.435 (public command, agent-run, `WIZARD_STRICT=1`): done in 447 s; release.json 0.3.435 pinned.
- Upgrade to 0.3.436: done in 153 s; release.json 0.3.436 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `e43236d8…`, .env `4439935d…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.
- Maintenance helper: root before, root after.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T21:54:10.802236397Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-11-26T21:54:10.639780349Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T21:52:52.183070641Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-11-26T21:52:52.030660607Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T21:54:33.327947515Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-11-26T21:54:33.516351849Z
runtipi sha256:debaee945b939f0e2aac97ac81b3bf02732b1bb1705fb2a5796b3a49fb0d1fb0 2026-11-26T21:57:24.206532406Z
runtipi-db sha256:c0e9c0e9bac7e4c1834b698217a03ee5c708de30d313c84a506972de0e24b059 2026-11-26T21:49:40.517519918Z
runtipi-queue sha256:bba4266e0129b9e5c4b5eb985d8e488c77689eaf73399b34b5d176eb8a5d29e7 2026-11-26T21:49:40.686927242Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-11-26T21:49:55.873305946Z
runtipi-wizard-release-index-1 sha256:debaee945b939f0e2aac97ac81b3bf02732b1bb1705fb2a5796b3a49fb0d1fb0 2026-11-26T21:57:20.605812979Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T21:54:20.028102631Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-11-26T21:54:19.860191322Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T21:52:37.949257248Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-11-26T21:52:37.791858692Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:fb3f94d73cbc38c0cb77bea24235edb5022d60536d0f99a7630b965d9cb9ed78 2026-11-26T21:58:54.197487585Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T21:53:32.64674027Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:629c29911e68b2088e43ccdd21c0c8d57841eb021bc7951bbf9e2e2087e40924 2026-11-26T21:53:32.394065443Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T21:53:56.570751052Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:bb4812461d21852967e3d89187c66c89e8c45a82878dbf81ad6972d7eef83ee1 2026-11-26T21:53:56.373165832Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-11-26T21:55:18.857676602Z
wizard-ux_wizardapps-wizard-ux-1 sha256:82568995c922e4ae7d62d8ec4c35b0fe32e54e21ed27672f3e29d6426bc7f2e4 2026-11-26T21:58:48.703517272Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-11-26T21:55:04.712741363Z
```
</details>
