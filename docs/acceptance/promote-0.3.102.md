## Installed upgrade 0.3.94 → 0.3.102 on a disposable KVM guest

**Result: PASSED** (20261102T042003Z → 20261102T043449Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `775d941ea54b1584…`.

- Install 0.3.94 (public command, agent-run, `WIZARD_STRICT=1`): done in 567 s; release.json 0.3.94 pinned.
- Upgrade to 0.3.102: done in 201 s; release.json 0.3.102 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `43bef6b8…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-02T04:28:12.28084724Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-11-02T04:28:12.099845495Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-02T04:33:24.268966922Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-11-02T04:33:24.005515795Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-02T04:33:45.732464263Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-11-02T04:33:45.601110383Z
runtipi sha256:f116feb1e4aa2fbd2a84eae9dbdc006e120092cfce80d7e05c9ae4714d0548e9 2026-11-02T04:32:13.172730483Z
runtipi-db sha256:a26d06e6878f114ab53aace021fd9c599b498cca4c5ba2c18b34aee472f20148 2026-11-02T04:21:34.801902809Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-11-02T04:21:34.563028685Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-11-02T04:21:50.18379425Z
runtipi-wizard-release-index-1 sha256:f116feb1e4aa2fbd2a84eae9dbdc006e120092cfce80d7e05c9ae4714d0548e9 2026-11-02T04:31:09.159519381Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-02T04:28:23.59125465Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-11-02T04:28:23.460731069Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-02T04:25:32.228762608Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-11-02T04:25:32.093631109Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:d1b9282dad321b20321582f6d7c0e32c88f07330c6e82ff029bd952129424ee4 2026-11-02T04:33:03.15557306Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-02T04:26:51.254813275Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:abe83ddb8fe1e54347f94b5057740ba5da2309691f20b5692db476967638b445 2026-11-02T04:26:51.07448471Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-02T04:27:35.017781192Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:e839af7cdc32c875fcefec9189ae4e29509ea78b3b52d922416285c9e2eb81bb 2026-11-02T04:27:34.859881916Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-11-02T04:29:28.420639688Z
wizard-ux_wizardapps-wizard-ux-1 sha256:b4785d8eef3d1aa9690fc0bafd7fa8de16da45aa67da99f291f26e4d81131efe 2026-11-02T04:32:56.908962114Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-11-02T04:29:18.947486057Z
```
</details>
