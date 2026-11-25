# Promote 0.3.419 (release train)

## Why

- 0.3.419 carries hotfix wizard-ux#1763, wizard-ux#1767, wizard-app-manager#974, wizard-ux#1732, wizard-app-manager#939, wizard-app-manager#923, wizard-agent-service#592, wizard-agent-service#593, wizard-app-manager#934, wizard-agent-service#595, wizard-agent-service#596: hotfix lane (wizard-os#434), shortened soak with no open release-blocker issue, recorded as a fast-track.

## What changes (0.3.346 → 0.3.419)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): it carries changes that are not provably fixes.

- wizard-ux#1591 [fix] Recommended fix: Wizard for Mac's orb and Right ⌘ reply in the thread on screen while an app beside it has focus
- wizard-ux#1632 [maintenance] Maintenance: Apps in Settings > About & updates on for everyone (switch removed)
- wizard-ux#1660 [feature] Strong suggestion: with Skins are look only on, Look is just colours and background; feature switches get their own page
- wizard-ux#1703 [fix] Recommended fix: opening an app reads the Notifications items on its badge
- wizard-ux#1704 [feature] Strong suggestion: updates wait for running work on every box (switch wizard/os-update-waits removed)
- wizard-ux#1707 [feature] Strong suggestion: Channels are on for everyone (the wizard/chat-channels switch is removed)
- wizard-ux#1710 [fix] Recommended fix: Phone release runs again after Oscar became a second code owner
- wizard-ux#1711 [fix] Recommended fix: a channel feed's thread card says Draft while its thread holds a draft
- wizard-ux#1712 [fix] Recommended fix: a long-press on any word in a chat starts a selection, also "a" and "it"
- wizard-ux#1713 [feature] Strong suggestion: pinned apps open at once for everyone (the wizard/pin-fast-open switch is removed)
- wizard-ux#1714 [feature] Strong suggestion: Pinned apps load the slim page for everyone (the wizard/pin-slim-doc switch is removed)
- wizard-ux#1715 [fix] Recommended fix: the floating orb always keeps its coloured disc behind the icon (Android)
- wizard-ux#1716 [fix] Recommended fix: Wizard's mic on a phone no longer pauses music from other apps or drops earbuds to call quality
- wizard-ux#1717 [feature] Strong suggestion: draft marks are always on (switch wizard/draft-marks removed)
- wizard-ux#1718 [feature] Strong suggestion: Connecting leaves as soon as the Wizard answers, for everyone (switch wizard/pin-reach-answer removed, phone 0.10.58)
- wizard-ux#1719 [maintenance] Maintenance: the rest of ai-apps/desktop.js, skin-host.js and chats.js move into parts (196 KB to 58 KB, 117 to 35 KB, 110 to 68 KB, no behaviour change)
- wizard-ux#1720 [fix] Recommended fix: a tapped photo shows full screen at once, no fade-in or black frame
- wizard-ux#1721 [fix] Recommended fix: tests run the code they are about; no test only checks that source text exists
- wizard-ux#1727 [fix] Recommended fix: the Resources sheet closes on a phone tap on every tab (‹ or outside)
- wizard-ux#1732 [fix] Recommended fix: with private first, chats and the model menu go to the default private agent, not the hidden standard one
- wizard-ux#1733 [maintenance] Maintenance: the Android shell-token handover runs on a real emulator (wizard-os#133)
- wizard-ux#1736 [fix] Recommended fix: saved Wizards can be renamed, moved to a new address and removed
- wizard-ux#1737 [maintenance] Maintenance: the hostile-app check runs in CI on a real box with the browser boundary on
- wizard-ux#1739 [fix] Recommended fix: Download saves a file on older Wizard for Mac apps
- wizard-ux#1746 [fix] Recommended fix: Miguel's Home Tailscale tab no longer shows "null"
- wizard-ux#1747 [fix] Recommended fix: opening Wizard no longer takes over a shared Bluetooth speaker (phone 0.10.59)
- wizard-ux#1751 [fix] Recommended fix: a phone meeting recording carries on in the same meeting after the app process dies, and the phone records why (phone 0.10.60)
- wizard-ux#1753 [fix] Recommended fix: your own chat bubbles stand apart from the window on Landscapes Light
- wizard-ux#1754 [fix] Recommended fix: the desktop frame hotkeys QA run passes end to end (Refs #1726)
- wizard-ux#1756 [fix] Recommended fix: Welcome Say hello sends the shown default on an empty Send
- wizard-ux#1757 [fix] Recommended fix: Welcome Say hello has a mic, so the first message can be spoken
- wizard-ux#1758 [fix] Recommended fix: Activity on a fresh box shows one friendly empty state, not empty sections
- wizard-ux#1759 [fix] Recommended fix: a swipe down on the Apps panel's grip, or its grid at the top, closes it
- wizard-ux#1760 [fix] Recommended fix: the phone Apps panel has a visible Close Apps button next to Search
- wizard-ux#1761 [fix] Recommended fix: phone take discs show the skin red Cancel and amber paused Pause
- wizard-ux#1763 [fix] Recommended fix: the phone stops re-sending refused meeting markers every 5 s and saves the stack of any UI freeze (phone 0.10.61)
- wizard-ux#1764 [fix] Recommended fix: Archive on top also puts Archived first in the AI apps desktop sidebar
- wizard-ux#1765 [fix] Recommended fix: folding the AI apps sidebar leaves desks out of sight where they are
- wizard-ux#1767 [fix] Recommended fix: the phone app no longer freezes on open after a long meeting (phone 0.10.62)
- wizard-ux#1770 [fix] Recommended fix: Forward to Wizard works in an app opened from its home-screen icon
- wizard-ux#1771 [fix] Recommended fix: Mac Settings says For testers updates install as soon as Wizard is free
- wizard-ux#1773 [fix] Recommended fix: an existing Wizard with its AI signed out gets only Reconnect your AI
- wizard-ux#1774 [fix] Recommended fix: a failed send on a signed-out Tinfoil thread offers Reconnect Tinfoil
- wizard-ux#1776 [fix] Recommended fix: the phone app's start no longer waits on a long meeting's store or upload backlog (phone 0.10.63)
- wizard-ux#1780 [feature] Strong suggestion: list the switch wizard/local-app-routes (open apps without Tailscale)
- wizard-ux#1781 [feature] Strong suggestion: Telegram and Slack chats take replies in WizardOS (switch off by default)
- wizard-ux#1782 [feature] Strong suggestion: narrow desktop, tapping the app in front takes it to its first view (switch wizard/app-tap-home, off)
- wizard-ux#1783 [feature] Strong suggestion: phone, swipe the download banner and Downloads sheet away (switch wizard/download-swipe, off)
- wizard-ux#1784 [feature] Strong suggestion: list the switch wizard/capability-registry (agents use what the box already does)
- wizard-ux#1785 [maintenance] Maintenance: Notifications in Chats and AI apps are built into the shell, not tweak packages
- wizard-agent-service#583 [fix] Recommended fix: agent tool calls cannot change installed app skill files
- wizard-agent-service#590 [fix] Recommended fix: a draft request reaches the messaging app (Refs humanitylabs-org/wizard-os#800)
- wizard-agent-service#591 [feature] Strong suggestion: Channels are on for everyone (the Service stops reading the wizard/chat-channels switch)
- wizard-agent-service#592 [fix] Recommended fix: private first answers off when the box has no agent runtime, so Tinfoil keeps the owner chatting
- wizard-agent-service#593 [fix] Recommended fix: private first stays on without an agent runtime, and the runtime helper can listen on a Unix socket
- wizard-agent-service#595 [fix] Recommended fix: the agent runtime reads the Tinfoil key saved in the Tinfoil app, so the private agent can start
- wizard-agent-service#596 [fix] Recommended fix: a fresh box's first private agent installs before its Runtipi override, so it can start
- wizard-agent-service#599 [fix] Recommended fix: routed agents get one file-sending rule that matches what Wizard accepts
- wizard-agent-service#600 [fix] Recommended fix: a file a private agent names as a plain path shows as a file card or a 'not sent' line
- wizard-agent-service#601 [fix] Recommended fix: a Chats list snapshot rebuild no longer blocks the Service for about a second
- wizard-agent-service#602 [fix] Recommended fix: a private agent is never granted the Claude or ChatGPT connection apps
- wizard-agent-service#603 [fix] Recommended fix: a large Hermes history imports chat by chat instead of running the agent out of memory
- wizard-agent-service#604 [fix] Recommended fix: imported facts are used, fact memory goes on when an import brings facts
- wizard-agent-service#605 [fix] Recommended fix: an import that stops part way is marked failed with the reason, and Undo finds what came in
- wizard-agent-service#606 [fix] Recommended fix: a chat started on Telegram says it lives in Telegram instead of offering Retry
- wizard-agent-service#609 [fix] Recommended fix: with the browser boundary on, the box's own health probes answer again
- wizard-agent-service#610 [feature] Strong suggestion: app screens open on the box's own Wizard address without Tailscale (switch wizard/local-app-routes)
- wizard-agent-service#611 [feature] Strong suggestion: continue Telegram and Slack chats in WizardOS through their own connection (switch off by default)
- wizard-agent-service#614 [feature] Strong suggestion: agents find built-in WizardOS capabilities before installing their own (switch wizard/capability-registry, off)
- wizard-agent-service#616 [feature] Strong suggestion: the saved-result Needs you says why and can be dismissed on every device (switch wizard/needs-you-reason, off)
- wizard-app-manager#898 [fix] Recommended fix: the update retires the hand-written box overrides
- wizard-app-manager#900 [maintenance] Maintenance: mirror WizardOS 0.3.340 onto latest (release train)
- wizard-app-manager#901 [fix] Recommended fix: a restore reports an app Runtipi can't install and goes on with the rest
- wizard-app-manager#902 [maintenance] Maintenance: mirror WizardOS 0.3.341 onto latest (release train)
- wizard-app-manager#903 [fix] Recommended fix: Second Hand's ledger also moves when its app-data folder is root's
- wizard-app-manager#904 [maintenance] Maintenance: mirror WizardOS 0.3.342 onto latest (release train)
- wizard-app-manager#905 [feature] Strong suggestion: Store GitHub sign-in can be switched on (switch wizard/github-signin, off)
- wizard-app-manager#906 [maintenance] Maintenance: mirror WizardOS 0.3.343 onto latest (release train)
- wizard-app-manager#907 [feature] Strong suggestion: boxes check release signatures and the installer hash (warn-only, off by default)
- wizard-app-manager#908 [maintenance] Maintenance: mirror WizardOS 0.3.344 onto latest (release train)
- wizard-app-manager#909 [maintenance] Maintenance: mirror WizardOS 0.3.345 onto latest (release train)
- wizard-app-manager#910 [feature] Strong suggestion: updates wait for running work on every box (switch wizard/os-update-waits removed)
- wizard-app-manager#911 [maintenance] Maintenance: mirror WizardOS 0.3.346 onto latest (release train)
- wizard-app-manager#912 [maintenance] Maintenance: mirror WizardOS 0.3.347 onto latest (release train)
- wizard-app-manager#913 [maintenance] Maintenance: mirror WizardOS 0.3.348 onto latest (release train)
- wizard-app-manager#915 [maintenance] Maintenance: mirror WizardOS 0.3.349 onto latest (release train)
- wizard-app-manager#916 [fix] Recommended fix: app updates never install a lower version; moved apps record their new repo
- wizard-app-manager#917 [maintenance] Maintenance: mirror WizardOS 0.3.350 onto latest (release train)
- wizard-app-manager#919 [maintenance] Maintenance: mirror WizardOS 0.3.352 onto latest (release train)
- wizard-app-manager#920 [maintenance] Maintenance: mirror WizardOS 0.3.353 onto latest (release train)
- wizard-app-manager#921 [maintenance] Maintenance: mirror WizardOS 0.3.354 onto latest (release train)
- wizard-app-manager#922 [maintenance] Maintenance: mirror WizardOS 0.3.355 onto latest (release train)
- wizard-app-manager#923 [fix] Recommended fix: private app source copy and gateway-keys doctor use Runtipi's /app-data mount
- wizard-app-manager#924 [maintenance] Maintenance: mirror WizardOS 0.3.356 onto latest (release train)
- wizard-app-manager#925 [maintenance] Maintenance: mirror WizardOS 0.3.357 onto latest (release train)
- wizard-app-manager#926 [fix] Recommended fix: backups say when they leave out a host Hermes main agent
- wizard-app-manager#927 [maintenance] Maintenance: mirror WizardOS 0.3.358 onto latest (release train)
- wizard-app-manager#928 [maintenance] Maintenance: mirror WizardOS 0.3.359 onto latest (release train)
- wizard-app-manager#929 [maintenance] Maintenance: mirror WizardOS 0.3.360 onto latest (release train)
- wizard-app-manager#930 [maintenance] Maintenance: mirror WizardOS 0.3.361 onto latest (release train)
- wizard-app-manager#932 [fix] Recommended fix: app inbox tokens reach apps when the Agent Service runs on the host
- wizard-app-manager#933 [maintenance] Maintenance: mirror WizardOS 0.3.362 onto latest (release train)
- wizard-app-manager#934 [fix] Recommended fix: every fresh install and update sets up the agent runtime helper, so the Agent Service can create agents
- wizard-app-manager#935 [maintenance] Maintenance: mirror WizardOS 0.3.363 onto latest (release train)
- wizard-app-manager#936 [maintenance] Maintenance: mirror WizardOS 0.3.364 onto latest (release train)
- wizard-app-manager#938 [maintenance] Maintenance: mirror WizardOS 0.3.365 onto latest (release train)
- wizard-app-manager#939 [fix] Recommended fix: app updates no longer fail on live socket files in app data
- wizard-app-manager#940 [maintenance] Maintenance: mirror WizardOS 0.3.366 onto latest (release train)
- wizard-app-manager#941 [maintenance] Maintenance: mirror WizardOS 0.3.367 onto latest (release train)
- wizard-app-manager#942 [maintenance] Maintenance: mirror WizardOS 0.3.368 onto latest (release train)
- wizard-app-manager#943 [maintenance] Maintenance: mirror WizardOS 0.3.369 onto latest (release train)
- wizard-app-manager#944 [maintenance] Maintenance: mirror WizardOS 0.3.370 onto latest (release train)
- wizard-app-manager#945 [maintenance] Maintenance: mirror WizardOS 0.3.371 onto latest (release train)
- wizard-app-manager#946 [maintenance] Maintenance: mirror WizardOS 0.3.372 onto latest (release train)
- wizard-app-manager#947 [maintenance] Maintenance: mirror WizardOS 0.3.373 onto latest (release train)
- wizard-app-manager#948 [fix] Recommended fix: Connected accounts opens at its Wizard path again, not on a port of its own
- wizard-app-manager#949 [maintenance] Maintenance: mirror WizardOS 0.3.374 onto latest (release train)
- wizard-app-manager#950 [fix] Recommended fix: runtipi-cli on a fresh box matches the App Manager's Runtipi, so stop/start no longer answer 401
- wizard-app-manager#951 [maintenance] Maintenance: mirror WizardOS 0.3.375 onto latest (release train)
- wizard-app-manager#952 [fix] Recommended fix: a fresh install survives one dropped connection while downloading
- wizard-app-manager#953 [maintenance] Maintenance: mirror WizardOS 0.3.376 onto latest (release train)
- wizard-app-manager#954 [fix] Recommended fix: a scheduled backup clears the stale restic lock a crashed run left behind
- wizard-app-manager#956 [maintenance] Maintenance: mirror WizardOS 0.3.377 onto latest (release train)
- wizard-app-manager#957 [fix] Recommended fix: new boxes start with the browser boundary on
- wizard-app-manager#958 [maintenance] Maintenance: mirror WizardOS 0.3.378 onto latest (release train)
- wizard-app-manager#959 [maintenance] Maintenance: mirror WizardOS 0.3.379 onto latest (release train)
- wizard-app-manager#961 [maintenance] Maintenance: mirror WizardOS 0.3.380 onto latest (release train)
- wizard-app-manager#962 [fix] Recommended fix: inbox tokens reach apps when Runtipi's user-config is root-owned
- wizard-app-manager#963 [maintenance] Maintenance: mirror WizardOS 0.3.381 onto latest (release train)
- wizard-app-manager#964 [fix] Recommended fix: a fresh install on a slower machine waits for Runtipi instead of failing (wam recover)
- wizard-app-manager#965 [maintenance] Maintenance: mirror WizardOS 0.3.382 onto latest (release train)
- wizard-app-manager#966 [maintenance] Maintenance: mirror WizardOS 0.3.383 onto latest (release train)
- wizard-app-manager#967 [maintenance] Maintenance: mirror WizardOS 0.3.384 onto latest (release train)
- wizard-app-manager#968 [maintenance] Maintenance: mirror WizardOS 0.3.385 onto latest (release train)
- wizard-app-manager#969 [maintenance] Maintenance: mirror WizardOS 0.3.386 onto latest (release train)
- wizard-app-manager#970 [maintenance] Maintenance: mirror WizardOS 0.3.387 onto latest (release train)
- wizard-app-manager#972 [maintenance] Maintenance: mirror WizardOS 0.3.388 onto latest (release train)
- wizard-app-manager#973 [maintenance] Maintenance: mirror WizardOS 0.3.389 onto latest (release train)
- wizard-app-manager#974 [fix] Recommended fix: the Agent Service updates even while a private agent writes in its folder, and a failed update says why
- wizard-app-manager#975 [maintenance] Maintenance: mirror WizardOS 0.3.390 onto latest (release train)
- wizard-app-manager#976 [maintenance] Maintenance: mirror WizardOS 0.3.391 onto latest (release train)
- wizard-app-manager#977 [fix] Recommended fix: a big host Hermes no longer makes the nightly backup fail
- wizard-app-manager#978 [maintenance] Maintenance: mirror WizardOS 0.3.392 onto latest (release train)
- wizard-app-manager#979 [maintenance] Maintenance: mirror WizardOS 0.3.393 onto latest (release train)
- wizard-app-manager#980 [maintenance] Maintenance: mirror WizardOS 0.3.394 onto latest (release train)
- wizard-app-manager#981 [fix] Recommended fix: Bring your Wizard imports Hermes backups on a fresh install (agent sees Files Inbox/Imported)
- wizard-app-manager#982 [maintenance] Maintenance: mirror WizardOS 0.3.395 onto latest (release train)
- wizard-app-manager#983 [maintenance] Maintenance: mirror WizardOS 0.3.396 onto latest (release train)
- wizard-app-manager#984 [maintenance] Maintenance: mirror WizardOS 0.3.397 onto latest (release train)
- wizard-app-manager#985 [maintenance] Maintenance: mirror WizardOS 0.3.398 onto latest (release train)
- wizard-app-manager#986 [maintenance] Maintenance: mirror WizardOS 0.3.399 onto latest (release train)
- wizard-app-manager#987 [fix] Recommended fix: installing Mail no longer warns about a missing 'mail-calendar' app
- wizard-app-manager#988 [maintenance] Maintenance: mirror WizardOS 0.3.400 onto latest (release train)
- wizard-app-manager#989 [maintenance] Maintenance: mirror WizardOS 0.3.401 onto latest (release train)
- wizard-app-manager#990 [maintenance] Maintenance: mirror WizardOS stable 0.3.332 (release train, feature)
- wizard-app-manager#991 [maintenance] Maintenance: mirror WizardOS 0.3.402 onto latest (release train)
- wizard-app-manager#992 [maintenance] Maintenance: mirror WizardOS 0.3.403 onto latest (release train)
- wizard-app-manager#993 [maintenance] Maintenance: mirror WizardOS 0.3.404 onto latest (release train)
- wizard-app-manager#994 [fix] Recommended fix: a private owner phone feed moves with every phone release, and a stuck feed tells the owner
- wizard-app-manager#995 [maintenance] Maintenance: mirror WizardOS 0.3.405 onto latest (release train)
- wizard-app-manager#996 [maintenance] Maintenance: mirror WizardOS 0.3.406 onto latest (release train)
- wizard-app-manager#999 [fix] Recommended fix: boxes that already run Wizard turn the browser boundary on one release after new boxes
- wizard-app-manager#1000 [maintenance] Maintenance: mirror WizardOS 0.3.408 onto latest (release train)
- wizard-app-manager#1001 [maintenance] Maintenance: mirror WizardOS stable 0.3.346 (release train, feature)
- wizard-app-manager#1002 [maintenance] Maintenance: mirror WizardOS 0.3.409 onto latest (release train)
- wizard-app-manager#1003 [fix] Recommended fix: Mac guests turn the browser boundary on once their Mac app sends the token
- wizard-app-manager#1004 [maintenance] Maintenance: mirror WizardOS 0.3.410 onto latest (release train)
- wizard-app-manager#1007 [maintenance] Maintenance: mirror WizardOS 0.3.412 onto latest (release train)
- wizard-app-manager#1008 [maintenance] Maintenance: mirror WizardOS 0.3.413 onto latest (release train)
- wizard-app-manager#1009 [maintenance] Maintenance: mirror WizardOS 0.3.414 onto latest (release train)
- wizard-app-manager#1010 [maintenance] Maintenance: mirror WizardOS 0.3.415 onto latest (release train)
- wizard-app-manager#1011 [feature] Strong suggestion: a healthy host Wizard Voice Service fills Voice and Transcription in wam slots (switch wizard/capability-registry, off)
- wizard-app-manager#1012 [maintenance] Maintenance: mirror WizardOS 0.3.416 onto latest (release train)

## Evidence

## Installed upgrade 0.3.346 → 0.3.419 on a disposable KVM guest

**Result: PASSED** (20261125T215501Z → 20261125T220822Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.23.4 (2026.9.24) · stable · local 8fc037444731) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `e4e6a3c08ebe6bc4…`.

- Install 0.3.346 (public command, agent-run, `WIZARD_STRICT=1`): done in 475 s; release.json 0.3.346 pinned.
- Upgrade to 0.3.419: done in 199 s; release.json 0.3.419 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `e43236d8…`, .env `3aacd470…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.
- Maintenance helper: root before, root after.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-25T22:00:34.196334181Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-11-25T22:00:33.90535194Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-25T21:59:06.150319559Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-11-25T21:59:05.929086592Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-25T22:00:59.922331551Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-11-25T22:01:00.233067044Z
runtipi sha256:004f5a7820e2820a2d649aba8cf34cc732173a5240e6414fd6a78e364102b6f9 2026-11-25T22:04:21.951642543Z
runtipi-db sha256:c0e9c0e9bac7e4c1834b698217a03ee5c708de30d313c84a506972de0e24b059 2026-11-25T21:56:14.664690232Z
runtipi-queue sha256:bba4266e0129b9e5c4b5eb985d8e488c77689eaf73399b34b5d176eb8a5d29e7 2026-11-25T21:56:14.86571218Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-11-25T21:56:30.109768966Z
runtipi-wizard-release-index-1 sha256:004f5a7820e2820a2d649aba8cf34cc732173a5240e6414fd6a78e364102b6f9 2026-11-25T22:04:17.959960216Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-25T22:00:45.678912583Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-11-25T22:00:45.471510777Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-25T21:58:53.818447582Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-11-25T21:58:53.582423583Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:152c15c5196375c026a81874e7d993b7b544e4fce916c08e4aa9da2d9f2f35c5 2026-11-25T22:06:15.843481345Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-25T21:59:53.050020999Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:629c29911e68b2088e43ccdd21c0c8d57841eb021bc7951bbf9e2e2087e40924 2026-11-25T21:59:52.732429906Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-11-25T22:00:19.355360665Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:bb4812461d21852967e3d89187c66c89e8c45a82878dbf81ad6972d7eef83ee1 2026-11-25T22:00:19.0997541Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-11-25T22:01:55.43555856Z
wizard-ux_wizardapps-wizard-ux-1 sha256:7e940d2eca60262af91b61b62c600b51a9d3d090dbb512de12a8106b2507a254 2026-11-25T22:06:27.86917006Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-11-25T22:01:35.579639262Z
```
</details>
