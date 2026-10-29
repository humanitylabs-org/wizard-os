## Installed upgrade 0.3.84 → 0.3.86 on a disposable KVM guest

**Result: PASSED** (20261029T225826Z → 20261029T231250Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.84 (public command, agent-run, `WIZARD_STRICT=1`): done in 581 s; release.json 0.3.84 pinned.
- Upgrade to 0.3.86: done in 186 s; release.json 0.3.86 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `1284b478…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T23:06:41.881629407Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-29T23:06:41.691481949Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T23:04:20.417644328Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-29T23:04:20.293555637Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T23:07:18.840620485Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-29T23:07:19.006455797Z
runtipi sha256:ae8a65da8934dafb6a09ae5f1818c4266e402ca773daf70bcde382b5cfa03e9d 2026-10-29T23:10:32.016540476Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-29T22:59:48.396093429Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-29T22:59:48.257521458Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-29T23:00:03.665827752Z
runtipi-wizard-release-index-1 sha256:ae8a65da8934dafb6a09ae5f1818c4266e402ca773daf70bcde382b5cfa03e9d 2026-10-29T23:09:28.74841886Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T23:06:53.910947715Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-29T23:06:53.763766443Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T23:03:57.508119132Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-29T23:03:57.380754131Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:0795be214e76f07faf970a101c2c85be0dec067dcbf709496fdfa14caf852605 2026-10-29T23:04:33.528110727Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T23:11:11.421235524Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:bec542d1e4f11a9b8cd8a9efb733a563b93861b0549953e44bebcf6c986f8edc 2026-10-29T23:11:11.265375562Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T23:11:48.846700777Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:720058e1658c7870420dbb6414f6198eaaae1849058c4c8e18a518694f0be5a2 2026-10-29T23:11:48.686925692Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-29T23:07:58.012969131Z
wizard-ux_wizardapps-wizard-ux-1 sha256:daf65b4236ae9a3e269b7fedd25473aa7b3a1dc7121bde48db65bbc53ca8c58e 2026-10-29T23:04:46.950908883Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-29T23:07:50.734909671Z
```
</details>
