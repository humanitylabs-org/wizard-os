## Installed upgrade 0.3.81 → 0.3.82 on a disposable KVM guest

**Result: PASSED** (20261029T163256Z → 20261029T164734Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.81 (public command, agent-run, `WIZARD_STRICT=1`): done in 580 s; release.json 0.3.81 pinned.
- Upgrade to 0.3.82: done in 200 s; release.json 0.3.82 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `9a351b2b…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T16:41:15.308495403Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-29T16:41:15.193408467Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T16:39:03.872721799Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-29T16:39:03.751212795Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T16:41:52.033310443Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-29T16:41:52.183877295Z
runtipi sha256:7e6c8b4aff3b1631f05222b6a9fcd38c33dab7e5d6a76da2cb9868b255670a44 2026-10-29T16:44:54.551779251Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-29T16:34:31.859606227Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-29T16:34:31.744273241Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-29T16:34:47.132879799Z
runtipi-wizard-release-index-1 sha256:7e6c8b4aff3b1631f05222b6a9fcd38c33dab7e5d6a76da2cb9868b255670a44 2026-10-29T16:43:51.265082786Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T16:41:27.397244252Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-29T16:41:27.280091321Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T16:38:40.62634779Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-29T16:38:40.515140047Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:0795be214e76f07faf970a101c2c85be0dec067dcbf709496fdfa14caf852605 2026-10-29T16:39:15.326988521Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T16:45:55.3270715Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:aa8db34a31fe0fe8b83bb158d671681942ecc7b781daf4e3a61a6f9a1d82ad08 2026-10-29T16:45:55.190197306Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T16:46:33.446917664Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:86b258961a5a3c8fb59c5f2b658169992859c98c581d631634f7e101c122e532 2026-10-29T16:46:33.295347593Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-29T16:42:31.304137001Z
wizard-ux_wizardapps-wizard-ux-1 sha256:3fe171d53109c2978f2d9876c06779bd836d7ca8c1f0dbb6173a322183d48fb2 2026-10-29T16:45:33.208332706Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-29T16:42:21.736386241Z
```
</details>
