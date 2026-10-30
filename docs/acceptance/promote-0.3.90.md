## Installed upgrade 0.3.89 → 0.3.90 on a disposable KVM guest

**Result: PASSED** (20261030T100002Z → 20261030T101315Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.89 (public command, agent-run, `WIZARD_STRICT=1`): done in 582 s; release.json 0.3.89 pinned.
- Upgrade to 0.3.90: done in 124 s; release.json 0.3.90 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `bea4f2d9…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T10:08:19.641343748Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-30T10:08:19.509386688Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T10:06:03.970363855Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-30T10:06:03.840584989Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T10:08:57.721670607Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-30T10:08:57.883359466Z
runtipi sha256:ae8a65da8934dafb6a09ae5f1818c4266e402ca773daf70bcde382b5cfa03e9d 2026-10-30T10:12:04.08604805Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-30T10:01:29.021306716Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-30T10:01:28.878163262Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-30T10:01:44.394881246Z
runtipi-wizard-release-index-1 sha256:ae8a65da8934dafb6a09ae5f1818c4266e402ca773daf70bcde382b5cfa03e9d 2026-10-30T10:11:00.748301811Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T10:08:32.638279646Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-30T10:08:32.514204342Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T10:05:38.034540519Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-30T10:05:37.907169275Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:e02d50a489240fd155f305c5768190f04cad232b852be127fc3693c04f1e3fe9 2026-10-30T10:06:18.508788123Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T10:07:04.365417182Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:abe83ddb8fe1e54347f94b5057740ba5da2309691f20b5692db476967638b445 2026-10-30T10:07:04.138187715Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-30T10:07:46.93545627Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:e839af7cdc32c875fcefec9189ae4e29509ea78b3b52d922416285c9e2eb81bb 2026-10-30T10:07:46.769201059Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-30T10:09:37.44407191Z
wizard-ux_wizardapps-wizard-ux-1 sha256:2463c11b561b0b9fa3fe876f885e02f97a1e30c0273049f67682fc25683b1ca0 2026-10-30T10:06:29.535836554Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-30T10:09:29.244044317Z
```
</details>
