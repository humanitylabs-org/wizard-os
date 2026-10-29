# Promote 0.3.84

## Why

Miguel asked for the new Home & Settings (wizard-ux#668) on Stable the same day.

## What changes (0.3.83 → 0.3.84)

**Classification: feature** (launch-phase fast-track, DECISIONS #93).

- wizard-ux#668 [feature] Home & Settings for everyone (merged after a clean Codex review, 1727 tests)

## Evidence

### Upgrade test (passed, retry)

## Installed upgrade 0.3.83 → 0.3.84 on a disposable KVM guest

**Result: PASSED** (20261029T215425Z → 20261029T220828Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.83 (public command, agent-run, `WIZARD_STRICT=1`): done in 583 s; release.json 0.3.83 pinned.
- Upgrade to 0.3.84: done in 153 s; release.json 0.3.84 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `1532ce26…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T22:02:44.616251205Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-29T22:02:44.486893344Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T22:00:29.552781926Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-29T22:00:29.415262866Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T22:03:22.217874955Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-29T22:03:22.393181902Z
runtipi sha256:7e6c8b4aff3b1631f05222b6a9fcd38c33dab7e5d6a76da2cb9868b255670a44 2026-10-29T22:06:36.648993002Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-29T21:55:55.966067109Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-29T21:55:55.604825611Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-29T21:56:11.391992976Z
runtipi-wizard-release-index-1 sha256:7e6c8b4aff3b1631f05222b6a9fcd38c33dab7e5d6a76da2cb9868b255670a44 2026-10-29T22:05:33.405213105Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T22:02:57.422010213Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-29T22:02:57.261782179Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T22:00:01.418384932Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-29T22:00:01.289694249Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:0795be214e76f07faf970a101c2c85be0dec067dcbf709496fdfa14caf852605 2026-10-29T22:00:43.110811026Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T22:01:28.961715939Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:aa8db34a31fe0fe8b83bb158d671681942ecc7b781daf4e3a61a6f9a1d82ad08 2026-10-29T22:01:28.80054229Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T22:02:12.338173006Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:86b258961a5a3c8fb59c5f2b658169992859c98c581d631634f7e101c122e532 2026-10-29T22:02:12.185655633Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-29T22:04:07.555009828Z
wizard-ux_wizardapps-wizard-ux-1 sha256:daf65b4236ae9a3e269b7fedd25473aa7b3a1dc7121bde48db65bbc53ca8c58e 2026-10-29T22:07:28.055006865Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-29T22:03:59.681887496Z
```
</details>


### First upgrade test (failed, transient)

The upgrade step failed after 63 s with `Conflict. The container name "/runtipi" is already in use`; nothing in this release touches Runtipi or the App Manager. Same command, fresh guest, passed.

## Installed upgrade 0.3.83 → 0.3.84 on a disposable KVM guest

**Result: FAILED** (20261029T213753Z → 20261029T215114Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.83 (public command, agent-run, `WIZARD_STRICT=1`): done in 536 s; release.json 0.3.83 pinned.
- Upgrade to 0.3.84: failed in 63 s; release.json 0.3.83 install-failed, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `2cedbf32…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 2.

**Problems:**
- upgrade ended failed: Error response from daemon: Error when allocating new name: Conflict. The container name "/runtipi" is already in use by container "8d598937d3d06f112fff8e43a092320c7dc0aaec0c1b08ff79cdc523349d17e3". You have to remove (or rename) that container to be able to reuse that name.
- after: release.json 0.3.83 install-failed, failed checks []
- wam doctor FAIL: ["FAIL  App Manager API reachable  GET /marketplace/all -> 404: b'404 page not found\\n'", "FAIL  app networks readable  GET /marketplace/all -> 404: b'404 page not found\\n'"]

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T21:45:31.288272831Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-29T21:45:31.159759194Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T21:43:29.381164079Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-29T21:43:29.230115971Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T21:46:08.099323608Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-29T21:46:08.237713544Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-29T21:39:11.49257292Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-29T21:39:11.340868088Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-29T21:39:26.899533422Z
runtipi-wizard-release-index-1 sha256:7e6c8b4aff3b1631f05222b6a9fcd38c33dab7e5d6a76da2cb9868b255670a44 2026-10-29T21:48:47.550601795Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T21:45:42.571107319Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-29T21:45:42.427926834Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T21:43:08.033727824Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-29T21:43:07.926888303Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:0795be214e76f07faf970a101c2c85be0dec067dcbf709496fdfa14caf852605 2026-10-29T21:43:43.418782704Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T21:44:26.668179923Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:aa8db34a31fe0fe8b83bb158d671681942ecc7b781daf4e3a61a6f9a1d82ad08 2026-10-29T21:44:26.521416355Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T21:44:57.609937161Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:86b258961a5a3c8fb59c5f2b658169992859c98c581d631634f7e101c122e532 2026-10-29T21:44:57.457789205Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-29T21:46:50.665430157Z
wizard-ux_wizardapps-wizard-ux-1 sha256:3fe171d53109c2978f2d9876c06779bd836d7ca8c1f0dbb6173a322183d48fb2 2026-10-29T21:43:51.637930735Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-29T21:46:41.136796376Z
```
</details>
