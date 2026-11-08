# Promote 0.3.81 (release train)

## Why

Stable 0.3.76 lacked merged Recommended fixes:

- humanitylabs-org/wizard-ux#416 Recommended fix: Media viewer: long screenshots scroll
- humanitylabs-org/wizard-ux#447 Recommended fix: Dictation inserts at the cursor instead of a copy card
- humanitylabs-org/wizard-ux#458 Recommended fix: Store's My apps link opens in place instead of reloading Wizard
- humanitylabs-org/wizard-ux#487 Recommended fix: Photos backup runs on Wi-Fi when the tailnet VPN is on
- humanitylabs-org/wizard-ux#586 Recommended fix: Retry saved first messages after subscription sign-in recovers
- humanitylabs-org/wizard-ux#587 Recommended fix: Show saved messages waiting for AI sign-in consistently
- humanitylabs-org/wizard-ux#589 Recommended fix: Keep first-launch app discovery from recursively rebuilding the shell
- humanitylabs-org/wizard-ux#605 Recommended fix: Share to Wizard picks New chat or one chat, quotes forwarded words, and sends in the background
- humanitylabs-org/wizard-ux#635 Recommended fix: show times in the phone's own timezone
- humanitylabs-org/wizard-ux#636 Recommended fix: every picked image rides an orb send made while it uploads
- humanitylabs-org/wizard-ux#641 Recommended fix: Share to Wizard sheet looks like the rest of the OS
- humanitylabs-org/wizard-ux#650 Recommended fix: Messenger recovers its own take after a reload and orphaned capture starts are stopped
- humanitylabs-org/wizard-ux#652 Recommended fix: tapping outside a sheet, menu or modal acts as Back across apps and shell
- humanitylabs-org/wizard-ux#655 Recommended fix: keep Ready asks visible while helpers continue
- humanitylabs-org/wizard-ux#658 Recommended fix: overlays with text are fully opaque in every skin
- humanitylabs-org/wizard-ux#679 Recommended fix: status pills get their own colours in every skin
- humanitylabs-org/wizard-ux#680 Recommended fix: the app kit follows its own text and touch-size rule
- humanitylabs-org/wizard-ux#682 Recommended fix: apps open at once; setup check no longer holds the window
- humanitylabs-org/wizard-ux#684 Recommended fix: show notifications when Ready has no chats
- humanitylabs-org/wizard-ux#689 Recommended fix: keep saved-message retries out of the connection warning
- humanitylabs-org/wizard-ux#690 Recommended fix: keep model picker above tall drafts and keyboard
- humanitylabs-org/wizard-ux#691 Recommended fix: Setup and Settings use the shared app style contract
- humanitylabs-org/wizard-ux#692 Recommended fix: keep agent replies on their own model and retain their threads
- humanitylabs-org/wizard-ux#693 Recommended fix: Keep repeated Back presses inside Wizard at Home
- humanitylabs-org/wizard-ux#694 Recommended fix: refresh the model picker on every open without repainting unchanged choices
- humanitylabs-org/wizard-ux#696 Recommended fix: a running reply never shows its interim line twice
- humanitylabs-org/wizard-ux#704 Recommended fix: Use current-route wording for voice health help
- humanitylabs-org/wizard-ux#709 Recommended fix: a chat is in one Space; filed chats read Move to Space…
- humanitylabs-org/wizard-ux#710 Recommended fix: Settings rows stay flat lines over the shared kit controls
- humanitylabs-org/wizard-ux#713 Recommended fix: owners see Apps, never Wizard apps, on the agent page, Apps sheet and share sheet
- humanitylabs-org/wizard-ux#715 Recommended fix: Screen chat QA fixture uses invented text, not a real team conversation
- humanitylabs-org/wizard-ux#718 Recommended fix: live replies resume after a dropped connection
- humanitylabs-org/wizard-ux#719 Recommended fix: Wizard opens offline and shows saved thread copies
- humanitylabs-org/wizard-ux#720 Recommended fix: show Claude extra enabled when its cap is unavailable
- humanitylabs-org/wizard-ux#721 Recommended fix: COMPONENTS.md back under its 14,000-byte budget (npm test red on main)
- humanitylabs-org/wizard-ux#723 Recommended fix: COMPONENTS.md back under its 14,000-byte budget (npm test red on main)
- humanitylabs-org/wizard-ux#725 Recommended fix: shared-app install links open in the Store again
- humanitylabs-org/wizard-ux#726 Recommended fix: launcher shows long one-word app names whole
- humanitylabs-org/wizard-ux#727 Recommended fix: one offline pop-up with three checks (Internet · Tailscale · Wizard)
- humanitylabs-org/wizard-ux#728 Recommended fix: Ready Priority ranks every status and shows its groups
- humanitylabs-org/wizard-ux#730 Recommended fix: launcher long-name size from the type token, with a regression test
- humanitylabs-org/wizard-ux#734 Recommended fix: working chats no longer flash into Ready while their history loads
- humanitylabs-org/wizard-ux#736 Recommended fix: protect every standalone app below Android status bar
- humanitylabs-org/wizard-agent-service#155 Recommended fix: owner CLI importer includes python-dotenv
- humanitylabs-org/wizard-agent-service#183 Recommended fix: threads know MEDIA sends PDFs and other files up to 256 MB
- humanitylabs-org/wizard-agent-service#197 Recommended fix: import older Hermes homes without shared-file or credential leaks
- humanitylabs-org/wizard-agent-service#228 Recommended fix: let open owner asks stay Ready during background work
- humanitylabs-org/wizard-agent-service#235 Recommended fix: chat pictures and files stay in the owner's browser, and edited files still update
- humanitylabs-org/wizard-agent-service#241 Recommended fix: a sent file is a snapshot, so a later rewrite never changes earlier chat messages
- humanitylabs-org/wizard-agent-service#245 Recommended fix: pointer skills send the agent through the app's own skill, with end-to-end proof
- humanitylabs-org/wizard-agent-service#250 Recommended fix: app workflow changes stay in released apps
- humanitylabs-org/wizard-agent-service#254 Recommended fix: a chat is in one Space at a time
- humanitylabs-org/wizard-agent-service#256 Recommended fix: Secret scan passes again (the round-10 synthetic placeholder is not a key)
- humanitylabs-org/wizard-agent-service#257 Recommended fix: the app-skill guard stops blocking reads and verification of installed skills
- humanitylabs-org/wizard-agent-service#260 Recommended fix: scheduled notifications use the job's own agent and survive late admission
- humanitylabs-org/wizard-agent-service#263 Recommended fix: Markdown support is a fact, not a formatting push
- humanitylabs-org/wizard-agent-service#264 Recommended fix: Secret scan passes again (shared-vault staging test's placeholder PEM is not a key)
- humanitylabs-org/wizard-agent-service#266 Recommended fix: a finished run leaves Working at once
- humanitylabs-org/wizard-app-manager#321 Recommended fix: app updates fill newly required settings first (or ask the owner)
- humanitylabs-org/wizard-app-manager#323 Recommended fix: Connections works on desktop: the phone's list on every screen, two columns when wide, Connect two apps from the list
- humanitylabs-org/wizard-app-manager#333 Recommended fix: wam picks up the docker group when the user manager predates it

## What changes (0.3.76 → 0.3.81)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): it carries changes that are not provably fixes.

- wizard-ux#340 [feature] Strong suggestion: Apps can wear the agent orb (Mizel: New recording)
- wizard-ux#407 [feature] Opinionated — feel free to drop: Chats: Priority orders Yesterday and Past week too
- wizard-ux#409 [feature] Strong suggestion: Apps can lower Wizard Music while they play a short sound
- wizard-ux#416 [fix] Recommended fix: Media viewer: long screenshots scroll
- wizard-ux#447 [fix] Recommended fix: Dictation inserts at the cursor instead of a copy card
- wizard-ux#458 [fix] Recommended fix: Store's My apps link opens in place instead of reloading Wizard
- wizard-ux#478 [feature] Strong suggestion: Share files and images through Wizard, hold Share for the system tray
- wizard-ux#487 [fix] Recommended fix: Photos backup runs on Wi-Fi when the tailnet VPN is on
- wizard-ux#496 [feature] Strong suggestion: Pages in the shell — list, open, edit, history
- wizard-ux#536 [feature] Strong suggestion: Shared offline kit: scoped reading replica and durable ordered edits
- wizard-ux#574 [feature] Strong suggestion: Customize skill: owner's agent changes look and layout safely (+ broken skin.js starts off, file named)
- wizard-ux#586 [fix] Recommended fix: Retry saved first messages after subscription sign-in recovers
- wizard-ux#587 [fix] Recommended fix: Show saved messages waiting for AI sign-in consistently
- wizard-ux#589 [fix] Recommended fix: Keep first-launch app discovery from recursively rebuilding the shell
- wizard-ux#605 [fix] Recommended fix: Share to Wizard picks New chat or one chat, quotes forwarded words, and sends in the background
- wizard-ux#610 [feature] Strong suggestion: Window opacity setting in Settings › Appearance (no default change)
- wizard-ux#625 [feature] Opinionated: one inbox — notifications arrive in Chats as yellow threads, for everyone (feel free to drop)
- wizard-ux#635 [fix] Recommended fix: show times in the phone's own timezone
- wizard-ux#636 [fix] Recommended fix: every picked image rides an orb send made while it uploads
- wizard-ux#641 [fix] Recommended fix: Share to Wizard sheet looks like the rest of the OS
- wizard-ux#650 [fix] Recommended fix: Messenger recovers its own take after a reload and orphaned capture starts are stopped
- wizard-ux#652 [fix] Recommended fix: tapping outside a sheet, menu or modal acts as Back across apps and shell
- wizard-ux#655 [fix] Recommended fix: keep Ready asks visible while helpers continue
- wizard-ux#658 [fix] Recommended fix: overlays with text are fully opaque in every skin
- wizard-ux#663 [feature] Opinionated: reply style lives with each agent (retire Summary/Concise picker)
- wizard-ux#679 [fix] Recommended fix: status pills get their own colours in every skin
- wizard-ux#680 [fix] Recommended fix: the app kit follows its own text and touch-size rule
- wizard-ux#682 [fix] Recommended fix: apps open at once; setup check no longer holds the window
- wizard-ux#683 [feature] Strong suggestion: close desks with hover ✕ or right-click, land on the left desk
- wizard-ux#684 [fix] Recommended fix: show notifications when Ready has no chats
- wizard-ux#685 [feature] Orb: voice bars that follow the mic, and no white shine behind the app icon
- wizard-ux#687 [feature] Revert the voice bars inside the orb (keep the shine fix)
- wizard-ux#688 [feature] Strong suggestion: one device page and connect flow (James approved)
- wizard-ux#689 [fix] Recommended fix: keep saved-message retries out of the connection warning
- wizard-ux#690 [fix] Recommended fix: keep model picker above tall drafts and keyboard
- wizard-ux#691 [fix] Recommended fix: Setup and Settings use the shared app style contract
- wizard-ux#692 [fix] Recommended fix: keep agent replies on their own model and retain their threads
- wizard-ux#693 [fix] Recommended fix: Keep repeated Back presses inside Wizard at Home
- wizard-ux#694 [fix] Recommended fix: refresh the model picker on every open without repainting unchanged choices
- wizard-ux#695 [feature] Preserve approved Setup connect entry and green completed step
- wizard-ux#696 [fix] Recommended fix: a running reply never shows its interim line twice
- wizard-ux#704 [fix] Recommended fix: Use current-route wording for voice health help
- wizard-ux#707 [feature] fix: show full original contents in opened alert thread
- wizard-ux#709 [fix] Recommended fix: a chat is in one Space; filed chats read Move to Space…
- wizard-ux#710 [fix] Recommended fix: Settings rows stay flat lines over the shared kit controls
- wizard-ux#713 [fix] Recommended fix: owners see Apps, never Wizard apps, on the agent page, Apps sheet and share sheet
- wizard-ux#715 [fix] Recommended fix: Screen chat QA fixture uses invented text, not a real team conversation
- wizard-ux#717 [feature] Add Dismiss to failed chat sends
- wizard-ux#718 [fix] Recommended fix: live replies resume after a dropped connection
- wizard-ux#719 [fix] Recommended fix: Wizard opens offline and shows saved thread copies
- wizard-ux#720 [fix] Recommended fix: show Claude extra enabled when its cap is unavailable
- wizard-ux#721 [fix] Recommended fix: COMPONENTS.md back under its 14,000-byte budget (npm test red on main)
- wizard-ux#722 [feature] fix: make saved provider waits actionable without duplicate retries
- wizard-ux#723 [fix] Recommended fix: COMPONENTS.md back under its 14,000-byte budget (npm test red on main)
- wizard-ux#725 [fix] Recommended fix: shared-app install links open in the Store again
- wizard-ux#726 [fix] Recommended fix: launcher shows long one-word app names whole
- wizard-ux#727 [fix] Recommended fix: one offline pop-up with three checks (Internet · Tailscale · Wizard)
- wizard-ux#728 [fix] Recommended fix: Ready Priority ranks every status and shows its groups
- wizard-ux#730 [fix] Recommended fix: launcher long-name size from the type token, with a regression test
- wizard-ux#733 [feature] Opinionated UX: first run is one Welcome modal (connect AI, pick a colour, say hello)
- wizard-ux#734 [fix] Recommended fix: working chats no longer flash into Ready while their history loads
- wizard-ux#736 [fix] Recommended fix: protect every standalone app below Android status bar
- wizard-agent-service#122 [feature] Strong suggestion: Machines v1: agent-owned computers (Archimedes → Thales)
- wizard-agent-service#134 [feature] Strong suggestion: Pages: serve /pages/ sandboxed, versioned Pages API, refuse Origin: null
- wizard-agent-service#155 [fix] Recommended fix: owner CLI importer includes python-dotenv
- wizard-agent-service#174 [feature] Strong suggestion: Serve the shared phone update feed on every box
- wizard-agent-service#183 [fix] Recommended fix: threads know MEDIA sends PDFs and other files up to 256 MB
- wizard-agent-service#197 [fix] Recommended fix: import older Hermes homes without shared-file or credential leaks
- wizard-agent-service#198 [feature] Strong suggestion: enable stock holographic fact memory for Wizard agent containers
- wizard-agent-service#215 [feature] Strong suggestion: share the daily reminders, agent-reading and Working plugins
- wizard-agent-service#224 [feature] Strong suggestion: service-owned host system jobs and disabled Hermes cron migration
- wizard-agent-service#228 [fix] Recommended fix: let open owner asks stay Ready during background work
- wizard-agent-service#235 [fix] Recommended fix: chat pictures and files stay in the owner's browser, and edited files still update
- wizard-agent-service#241 [fix] Recommended fix: a sent file is a snapshot, so a later rewrite never changes earlier chat messages
- wizard-agent-service#245 [fix] Recommended fix: pointer skills send the agent through the app's own skill, with end-to-end proof
- wizard-agent-service#246 [feature] Opinionated: each agent keeps its own reply style, with no Wizard override
- wizard-agent-service#248 [feature] Strong suggestion: agents can look up the owner’s phone and app versions
- wizard-agent-service#249 [maintenance] Record the reviewed source commit when building restricted sidecars
- wizard-agent-service#250 [fix] Recommended fix: app workflow changes stay in released apps
- wizard-agent-service#254 [fix] Recommended fix: a chat is in one Space at a time
- wizard-agent-service#256 [fix] Recommended fix: Secret scan passes again (the round-10 synthetic placeholder is not a key)
- wizard-agent-service#257 [fix] Recommended fix: the app-skill guard stops blocking reads and verification of installed skills
- wizard-agent-service#258 [maintenance] Maintenance: parity inventory names the agent held-take route test
- wizard-agent-service#260 [fix] Recommended fix: scheduled notifications use the job's own agent and survive late admission
- wizard-agent-service#262 [feature] fix: reject stale saved retries on a different model route
- wizard-agent-service#263 [fix] Recommended fix: Markdown support is a fact, not a formatting push
- wizard-agent-service#264 [fix] Recommended fix: Secret scan passes again (shared-vault staging test's placeholder PEM is not a key)
- wizard-agent-service#265 [feature] Agents: a turned-off app is refused in plain words; new standard agents start with every app on (Miguel-approved)
- wizard-agent-service#266 [fix] Recommended fix: a finished run leaves Working at once
- wizard-app-manager#309 [maintenance] Maintenance: mirror WizardOS 0.3.74 onto latest (0.3.73 + App Manager main 79272034, quick interface updates)
- wizard-app-manager#321 [fix] Recommended fix: app updates fill newly required settings first (or ask the owner)
- wizard-app-manager#323 [fix] Recommended fix: Connections works on desktop: the phone's list on every screen, two columns when wide, Connect two apps from the list
- wizard-app-manager#326 [maintenance] Maintenance: mirror stable 0.3.74 (feature fast-track, App Manager main, quick interface updates)
- wizard-app-manager#328 [feature] Connections: Agents with per-agent on/off switches, one Linked apps list, Restore defaults (Miguel-approved)
- wizard-app-manager#329 [maintenance] Maintenance: mirror WizardOS 0.3.75 onto latest (release train)
- wizard-app-manager#330 [maintenance] Maintenance: mirror WizardOS stable 0.3.76 (fix) and latest 0.3.77
- wizard-app-manager#331 [feature] Connections: spacing in the Restore defaults dialog
- wizard-app-manager#332 [maintenance] Maintenance: mirror WizardOS 0.3.78 onto latest (release train)
- wizard-app-manager#333 [fix] Recommended fix: wam picks up the docker group when the user manager predates it
- wizard-app-manager#334 [maintenance] Maintenance: mirror WizardOS 0.3.79 onto latest (release train)
- default app ai-connection: wizard-chatgpt f73b8487 0.2.6 -> wizard-chatgpt 5e5f1b2c 0.2.8
- default app claude-subscription: wizard-claude 43f6a412 0.2.8 -> wizard-claude ee874699 0.2.10

## Evidence

## Installed upgrade 0.3.76 → 0.3.81 on a disposable KVM guest

**Result: PASSED** (20261029T140926Z → 20261029T142433Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: public mirror. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.76 (public command, agent-run, `WIZARD_STRICT=1`): done in 597 s; release.json 0.3.76 pinned.
- Upgrade to 0.3.81: done in 232 s; release.json 0.3.81 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `71218e4b…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T14:17:49.453339866Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-29T14:17:49.31341859Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T14:15:20.51044197Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-29T14:15:20.385880388Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T14:18:39.637108609Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-29T14:18:39.970635296Z
runtipi sha256:7e6c8b4aff3b1631f05222b6a9fcd38c33dab7e5d6a76da2cb9868b255670a44 2026-10-29T14:21:29.337779001Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-29T14:11:33.499168537Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-29T14:11:33.650984565Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-29T14:11:59.555149147Z
runtipi-wizard-release-index-1 sha256:7e6c8b4aff3b1631f05222b6a9fcd38c33dab7e5d6a76da2cb9868b255670a44 2026-10-29T14:20:26.061745509Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T14:18:01.840053263Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-29T14:18:01.699035735Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T14:14:47.241440107Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-29T14:14:47.10681958Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:0795be214e76f07faf970a101c2c85be0dec067dcbf709496fdfa14caf852605 2026-10-29T14:22:21.414622655Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T14:22:45.645265967Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:e3fda924e99eeb8c40520b8e60fefa757e0832773c099588a9d00e441a25d142 2026-10-29T14:22:45.467453164Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T14:23:24.205673516Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:1f706a5b58cc06d81e44ff247fbf3949e21051ea5e0e5b59e90f7fe0e6468825 2026-10-29T14:23:24.024490553Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-29T14:19:18.861498838Z
wizard-ux_wizardapps-wizard-ux-1 sha256:cc24c9884aa707438f9034a1871ded9574588075931b49d542cf286fb6780f67 2026-10-29T14:22:14.784779559Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-29T14:19:10.298184981Z
```
</details>
