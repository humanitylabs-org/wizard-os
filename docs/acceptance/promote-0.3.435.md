# Promote 0.3.435 (release train)

## Why

- 0.3.435 carries hotfix wizard-agent-service#623, wizard-ux#1803, wizard-ux#1803, wizard-agent-service#628, wizard-agent-service#627, wizard-ux#1803, wizard-agent-service#628, wizard-ux#1790: hotfix lane (wizard-os#434), shortened soak with no open release-blocker issue, recorded as a fast-track.

## What changes (0.3.419 → 0.3.435)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): it carries changes that are not provably fixes.

- wizard-ux#1786 [feature] Strong suggestion: a chat Wizard itself marked Needs you says why, with Continue and Dismiss (switch wizard/needs-you-reason, off)
- wizard-ux#1787 [feature] Strong suggestion: the agent gets a manual of the Wizard interface, generated from the code and kept current by a test (switch wizard/interface-manual, off)
- wizard-ux#1788 [maintenance] Maintenance: help line for the wizard/needs-you-reason switch (fixes red agent-manual test on main)
- wizard-ux#1789 [feature] Strong suggestion: list the switch wizard/follow-main (merged fixes go live by themselves)
- wizard-ux#1790 [feature] Strong suggestion: one shell write guard drops identical resends, pauses bursts and honours Retry-After (switch wizard/write-guard, off)
- wizard-ux#1791 [feature] Strong suggestion: serve the shared Try new features section in the app kit
- wizard-ux#1792 [feature] Strong suggestion: list the switch wizard/plain-chat-titles (undated chat titles)
- wizard-ux#1793 [fix] Recommended fix: Try new features kit copy gets 44 px thumbs and switch, and no reverted flip after a late re-read
- wizard-ux#1794 [feature] Strong suggestion: list the switch wizard/try-feature-counts (anonymous Try new features counts)
- wizard-ux#1795 [feature] Strong suggestion: list the switch wizard/app-wake (apps wake your agent through the box)
- wizard-ux#1796 [feature] Strong suggestion: inline action cards in chat (approve, edit or open an app's proposed action)
- wizard-ux#1797 [feature] Strong suggestion: swap the AI apps desktop's sides (chats right, Apps left), behind a switch
- wizard-ux#1798 [feature] Strong suggestion: an app you Get shows in the Apps column with a spinner while it installs (switch wizard/install-in-sidebar)
- wizard-ux#1803 [feature] Strong suggestion: Chats Sent tab shows everything sent and how it was routed (switch wizard/chats-inbox, off)
- wizard-agent-service#617 [feature] Strong suggestion: the agent gets the shell's interface manual while switch wizard/interface-manual is on (off by default)
- wizard-agent-service#618 [fix] Recommended fix: Archive clears the saved-result Needs you for good, also after a restore (switch wizard/needs-you-reason, off)
- wizard-agent-service#619 [feature] Strong suggestion: merged changes go live by themselves on a hand-deployed box, and Wizard says when it is behind (switch wizard/follow-main, off)
- wizard-agent-service#620 [feature] Strong suggestion: chats that share a topic keep their plain title instead of a date (switch wizard/plain-chat-titles, off)
- wizard-agent-service#621 [fix] Recommended fix: the Telegram conversation after a /new shows in Chats
- wizard-agent-service#622 [feature] Strong suggestion: apps wake the owner's agent with a small typed event through the box (switch wizard/app-wake)
- wizard-agent-service#623 [fix] Recommended fix: an expired AI sign-in shows the sign-in card, not Not sent / Needs retry
- wizard-agent-service#624 [fix] Recommended fix: every app wake after the first starts (no fixed thread title Hermes refuses twice)
- wizard-agent-service#625 [feature] Strong suggestion: Chats list preview hides the action-card marker (inline action cards in chat)
- wizard-agent-service#627 [feature] Strong suggestion: Sent log records every capture and how it was routed (switch wizard/agent-inbox)
- wizard-agent-service#628 [maintenance] Maintenance: agent parity entry for the Chats Sent tab (wizard-ux issue 1778)
- wizard-app-manager#1013 [maintenance] Maintenance: mirror WizardOS 0.3.417 onto latest (release train)
- wizard-app-manager#1014 [maintenance] Maintenance: mirror WizardOS 0.3.418 onto latest (release train)
- wizard-app-manager#1015 [maintenance] Maintenance: mirror WizardOS 0.3.419 onto latest (release train)
- wizard-app-manager#1016 [fix] Recommended fix: the Wizard guide names today's update options (Automatic / Ask me, For everyone / For testers)
- wizard-app-manager#1018 [maintenance] Maintenance: mirror WizardOS 0.3.420 onto latest (release train)
- wizard-app-manager#1019 [maintenance] Maintenance: mirror WizardOS 0.3.421 onto latest (release train)
- wizard-app-manager#1020 [maintenance] Maintenance: mirror WizardOS 0.3.422 onto latest (release train)
- wizard-app-manager#1022 [fix] Recommended fix: app updates that add a second service no longer fail on an undefined <app>_wizardapps_network
- wizard-app-manager#1023 [maintenance] Maintenance: mirror WizardOS 0.3.423 onto latest (release train)
- wizard-app-manager#1024 [maintenance] Maintenance: mirror WizardOS 0.3.424 onto latest (release train)
- wizard-app-manager#1025 [feature] Strong suggestion: Try new features in the app template (Settings section, kept thumbs) and anonymous tried/thumbs counts (switch wizard/try-feature-counts, off)
- wizard-app-manager#1026 [maintenance] Maintenance: mirror WizardOS 0.3.425 onto latest (release train)
- wizard-app-manager#1027 [maintenance] Maintenance: mirror WizardOS 0.3.426 onto latest (release train)
- wizard-app-manager#1028 [maintenance] Maintenance: mirror WizardOS 0.3.427 onto latest (release train)
- wizard-app-manager#1029 [maintenance] Maintenance: mirror WizardOS 0.3.428 onto latest (release train)
- wizard-app-manager#1030 [maintenance] Maintenance: mirror WizardOS 0.3.429 onto latest (release train)
- wizard-app-manager#1031 [maintenance] Maintenance: mirror WizardOS 0.3.430 onto latest (release train)
- wizard-app-manager#1033 [maintenance] Maintenance: mirror WizardOS 0.3.431 onto latest (release train)
- wizard-app-manager#1034 [maintenance] Maintenance: mirror WizardOS 0.3.432 onto latest (release train)
- wizard-app-manager#1035 [maintenance] Maintenance: mirror WizardOS 0.3.433 onto latest (release train)
- wizard-app-manager#1036 [maintenance] Maintenance: mirror WizardOS 0.3.434 onto latest (release train)
- wizard-app-manager#1037 [fix] Recommended fix: WizardOS updates no longer fail on hard-linked files in the Agent Service data

## Evidence

## Installed upgrade 0.3.419 → 0.3.435 on a disposable KVM guest

**Result: PASSED** (20261126T083605Z → 20261126T084644Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.23.4 (2026.9.24) · stable · local 8fc037444731) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `e4e6a3c08ebe6bc4…`.

- Install 0.3.419 (public command, agent-run, `WIZARD_STRICT=1`): done in 412 s; release.json 0.3.419 pinned.
- Upgrade to 0.3.435: done in 138 s; release.json 0.3.435 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `e43236d8…`, .env `b3ddeaca…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.
- Maintenance helper: root before, root after.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T08:41:02.489717134Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-11-26T08:41:02.359950089Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T08:40:00.94651924Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-11-26T08:40:00.820710114Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T08:41:23.728724055Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-11-26T08:41:23.933766398Z
runtipi sha256:debaee945b939f0e2aac97ac81b3bf02732b1bb1705fb2a5796b3a49fb0d1fb0 2026-11-26T08:44:04.298382265Z
runtipi-db sha256:c0e9c0e9bac7e4c1834b698217a03ee5c708de30d313c84a506972de0e24b059 2026-11-26T08:37:07.248829564Z
runtipi-queue sha256:bba4266e0129b9e5c4b5eb985d8e488c77689eaf73399b34b5d176eb8a5d29e7 2026-11-26T08:37:07.375036239Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-11-26T08:37:22.503326975Z
runtipi-wizard-release-index-1 sha256:debaee945b939f0e2aac97ac81b3bf02732b1bb1705fb2a5796b3a49fb0d1fb0 2026-11-26T08:44:00.865869046Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T08:41:11.454294386Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-11-26T08:41:11.334468591Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T08:39:50.694429595Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-11-26T08:39:50.577415158Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:41def474de3433d80a1705147456fe02dea4555d0c05d5a04c895de4114d5127 2026-11-26T08:45:23.897498265Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T08:40:37.506650176Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:629c29911e68b2088e43ccdd21c0c8d57841eb021bc7951bbf9e2e2087e40924 2026-11-26T08:40:37.201708608Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-26T08:42:28.904123458Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:bb4812461d21852967e3d89187c66c89e8c45a82878dbf81ad6972d7eef83ee1 2026-11-26T08:42:28.738272279Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-11-26T08:41:57.953922798Z
wizard-ux_wizardapps-wizard-ux-1 sha256:7c7f84e4a51d44e9eb4412134a7432797346735e39fd142294c4d6f24e439f89 2026-11-26T08:45:17.687448296Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-11-26T08:41:44.950729761Z
```
</details>
