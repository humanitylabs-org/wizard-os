# Promote 0.3.346 (release train)

## Why

- 0.3.346 soaked 72h+ on For testers (latest) with no open release-blocker issue (For everyone promotion, normal gate, no fast-track).

## What changes (0.3.332 → 0.3.346)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): it carries changes that are not provably fixes.

- wizard-ux#1648 [fix] Recommended fix: an app that gains its page opens from its tile, not its settings sheet
- wizard-ux#1656 [feature] Strong suggestion: the shell's Runtipi tools sign with Runtipi 4.12's CLI key (off by default)
- wizard-ux#1658 [fix] Recommended fix: a just-installed app says Starting… and opens once ready instead of a silent tap
- wizard-ux#1685 [maintenance] Maintenance: eleven phone-shell areas move out of app.js (twelfth split slice, no behaviour change)
- wizard-ux#1686 [maintenance] Maintenance: five skin-host areas move out of core/skin-host.js (thirteenth split slice, no behaviour change)
- wizard-ux#1687 [fix] Recommended fix: with the browser boundary on, the Android app's own owner calls carry the shell token
- wizard-ux#1688 [maintenance] Maintenance: nine desktop-shell areas move out of desktop/desktop.js (fourteenth split slice, no behaviour change)
- wizard-ux#1690 [maintenance] Maintenance: the rest of core/chats.js moves into 14 parts (238 KB to 111 KB, no behaviour change)
- wizard-ux#1691 [maintenance] Maintenance: the rest of app.js and desktop/desktop.js move into parts (291 KB to 94 KB, 254 KB to 60 KB, no behaviour change)
- wizard-ux#1695 [fix] Recommended fix: an app opened on its own gets the same shell services as inside the full shell
- wizard-ux#1697 [feature] Strong suggestion: a search box at the top of Settings narrows the pages to the ones mentioning your words and marks them (off by default)
- wizard-ux#1698 [fix] Recommended fix: a pinned app on the slim pin page sees Wizard's chat services from its first script
- wizard-ux#1699 [feature] Strong suggestion: Apps › Sign in to GitHub can be switched on (box switch wizard/github-signin, off)
- wizard-ux#1700 [fix] Recommended fix: saved background result Continue shows on main-agent threads
- wizard-ux#1702 [fix] Recommended fix: Chats stops re-reading every agent's list, title index and 404 agents on each poll (issue 1693)
- wizard-agent-service#585 [fix] Recommended fix: Chats list builds no longer re-read every schedule per chat row
- wizard-agent-service#587 [fix] Recommended fix: a .md file the agent sends opens on the phone (issue 586)
- wizard-agent-service#588 [maintenance] Maintenance: one-tap Continue for saved background results is covered on every agent kind
- wizard-agent-service#589 [feature] Strong suggestion: old Wizard Uploads files can be imported into the built-in file store (off by default)
- wizard-app-manager#872 [maintenance] Maintenance: mirror WizardOS 0.3.320 onto latest (release train)
- wizard-app-manager#874 [maintenance] Maintenance: mirror WizardOS 0.3.322 onto latest (release train)
- wizard-app-manager#876 [maintenance] Maintenance: mirror WizardOS 0.3.324 onto latest (release train)
- wizard-app-manager#877 [maintenance] Maintenance: mirror WizardOS 0.3.325 onto latest (release train)
- wizard-app-manager#878 [maintenance] Maintenance: mirror WizardOS 0.3.326 onto latest (release train)
- wizard-app-manager#879 [maintenance] Maintenance: mirror WizardOS 0.3.327 onto latest (release train)
- wizard-app-manager#881 [maintenance] Maintenance: mirror WizardOS 0.3.329 onto latest (release train)
- wizard-app-manager#882 [maintenance] Maintenance: mirror WizardOS 0.3.330 onto latest (release train)
- wizard-app-manager#883 [maintenance] Maintenance: mirror WizardOS 0.3.331 onto latest (release train)
- wizard-app-manager#884 [maintenance] Maintenance: mirror WizardOS 0.3.332 onto latest (release train)
- wizard-app-manager#886 [maintenance] Maintenance: mirror WizardOS 0.3.333 onto latest (release train)
- wizard-app-manager#887 [maintenance] Maintenance: mirror WizardOS 0.3.334 onto latest (release train)
- wizard-app-manager#888 [fix] Recommended fix: app rename copies the app's data from where Runtipi mounts it, and never removes an app whose data it did not copy
- wizard-app-manager#891 [maintenance] Maintenance: mirror WizardOS 0.3.335 onto latest (release train)
- wizard-app-manager#892 [maintenance] Maintenance: mirror WizardOS 0.3.336 onto latest (release train)
- wizard-app-manager#893 [fix] Recommended fix: app updates keep agent gateway folders private and remount stale Hermes session files
- wizard-app-manager#894 [maintenance] Maintenance: mirror WizardOS 0.3.337 onto latest (release train)
- wizard-app-manager#896 [maintenance] Maintenance: mirror WizardOS 0.3.338 onto latest (release train)
- wizard-app-manager#897 [fix] Recommended fix: an update whose new version is running is no longer reported rolled back when Runtipi's record lags

## Evidence

## Installed upgrade 0.3.332 → 0.3.346 on a disposable KVM guest

**Result: PASSED** (20261124T095959Z → 20261124T100955Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.23.4 (2026.9.24) · stable · local 8fc037444731) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `e4e6a3c08ebe6bc4…`.

- Install 0.3.332 (public command, agent-run, `WIZARD_STRICT=1`): done in 383 s; release.json 0.3.332 pinned.
- Upgrade to 0.3.346: done in 123 s; release.json 0.3.346 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `e43236d8…`, .env `04f651c6…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.
- Maintenance helper: root before, root after.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-24T10:04:47.972359878Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-11-24T10:04:47.847410916Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-24T10:03:57.173924635Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-11-24T10:03:57.049360397Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-24T10:05:03.373596622Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-11-24T10:05:03.539236884Z
runtipi sha256:7b2b97360115cc7fb88f079a1faf2e78d955abb5c591172e765fadf7c69aad48 2026-11-24T10:07:31.218927249Z
runtipi-db sha256:c0e9c0e9bac7e4c1834b698217a03ee5c708de30d313c84a506972de0e24b059 2026-11-24T10:01:14.692323553Z
runtipi-queue sha256:3dbd31cb9e4d45dac44de7b73cc45b848028494e98bcab71477386cbd4dc7f56 2026-11-24T10:01:14.806772707Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-11-24T10:01:29.929142561Z
runtipi-wizard-release-index-1 sha256:7b2b97360115cc7fb88f079a1faf2e78d955abb5c591172e765fadf7c69aad48 2026-11-24T10:07:27.983127907Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-24T10:04:53.085353864Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-11-24T10:04:52.922118543Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-24T10:03:45.484035329Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-11-24T10:03:45.35375538Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:97f7f50b814e9a936a466004a2fabeddabdb224a747d0b766c8240299af9f132 2026-11-24T10:08:42.019335193Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-24T10:04:30.806284294Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:629c29911e68b2088e43ccdd21c0c8d57841eb021bc7951bbf9e2e2087e40924 2026-11-24T10:04:30.633352127Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-24T10:06:06.020717692Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:bb4812461d21852967e3d89187c66c89e8c45a82878dbf81ad6972d7eef83ee1 2026-11-24T10:06:05.886060386Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-11-24T10:05:33.287842831Z
wizard-ux_wizardapps-wizard-ux-1 sha256:7784a6e416474600bd39406aa3f45e9dde78966c03e4eba6cdda5744e43065f8 2026-11-24T10:08:37.767299352Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-11-24T10:05:22.849134875Z
```
</details>
