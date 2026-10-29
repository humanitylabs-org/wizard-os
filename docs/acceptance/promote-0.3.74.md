# Promote 0.3.74 (hand cut: App Manager main, quick interface updates)

## Why

0.3.74 moves the App Manager from its maintenance line (`08b54f65`) to main `79272034`, which carries wizard-app-manager #304: when the next release differs from the installed one only in Wizard UX pins, Update and Automatic swap that image in place in about 2 minutes instead of rerunning the 10–20 minute installer. Boxes get that path only after one full update onto a release whose App Manager contains it; this is that release. It also brings the App Manager fixes #311 (installer rerun no longer fails at `wizard link`), #312 (App Store data service starts again) and #320 (app-change rule keeps the approval gate).

## What changes (0.3.73 → 0.3.74)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): App Manager main carries feature merges as well as fixes. Only the App Manager pin and its image move; Wizard UX `db361987`, Agent Service `3773ca0c`, Hermes, Notifications, Troubleshooter and every other image and default app are byte-identical to 0.3.73. Cut in wizard-os #299; mirrored in wizard-app-manager #309. `releases/0.3.74.json` sha256 `dea8615dcf89453cc9c0b25fcfa144c2994dc0f464ab5f8397babce1651cbe21`.

- App Manager `08b54f65` → `7927203463e638266db6872e381ff2bc95f87570` (main); image `v4.10.2-wizard.571-80c76cf` → `v4.10.2-wizard.778-d9e1644` (`sha256:530076256e67…`, built from d9e16446; image inputs unchanged through 79272034).
- #274 adds a `web-search` default slot on main, but pinned installs take their default set from the release, and 0.3.74's `default_apps` are 0.3.73's: Search is not added.
- #214 makes the installer enable an hourly public phone-APK mirror timer (`wam phone-sync`); it never installs or restarts anything.

### Ride-alongs (App Manager PRs since Stable's maintenance line)
Classification for Stable: **feature** (DECISIONS #93), not fix-only.

Merged on App Manager main after the first cut of this PR (55655c9c..79272034), also in this release:
- wizard-app-manager#320 [fix] Recommended fix: app-change rule keeps the release approval gate and checks every changed file
- wizard-app-manager#316 [fix] Recommended fix: teach safe Wizard changes and owner-approved problem reports
- wizard-app-manager#184 [feature] Send one-way alerts to Notifications instead of creating extra chats
- wizard-app-manager#214 [feature] Mirror phone releases hourly, independent of box updates (install.sh now runs `wam phone-sync --ensure-timer`: an hourly public-APK mirror timer; never installs or restarts anything)
- wizard-app-manager#274 [feature] web-search spot with Search as its default (fresh unpinned boxes only; see Pins)
- wizard-app-manager#317 [maintenance] wizard-builder: app changes ship in the app, not agent skills
- wizard-app-manager#318 [maintenance] enforce the canonical app style contract in the builder
- Maintenance: #313, #314 (0.3.73 mirrors), #315 (portable CI)

Features through 55655c9c:
- wizard-app-manager#231 [feature] release: mirror Wizard OS 0.3.49 latest (backup permission repair)
- wizard-app-manager#232 [feature] Store: install from share links (source: link) and record install source
- wizard-app-manager#242 [feature] fix(installer): wait for Ubuntu automatic update locks
- wizard-app-manager#249 [feature] Strong suggestion: alongside boxes turn on the Claude account broker and reload the dashboard after the plugin refresh
- wizard-app-manager#253 [feature] Strong suggestion: os.md uses the owner's final Tailscale and save-as-app wording
- wizard-app-manager#267 [feature] Fix upgrades leaving installed default apps behind their release pins
- wizard-app-manager#268 [feature] Mirror Latest 0.3.69: installed default-app upgrade repair
- wizard-app-manager#270 [feature] Strong suggestion: new apps start on the shared app design rules, and wam check warns on breaks
- wizard-app-manager#271 [feature] Strong suggestion: apps reach only the apps they declare (one Docker network per connection), with a Connections view
- wizard-app-manager#283 [feature] Seamless, owner-controllable app connections: auto-approve, runtime requests, sticky Disconnect, Sensitive approvals
- wizard-app-manager#288 [feature] Strong suggestion: app connections open by default (everything connected unless you disconnect it)
- wizard-app-manager#294 [feature] Strong suggestion: Connections controls open from Wizard on your phone
- wizard-app-manager#297 [feature] Strong suggestion: Connections as one picture — all your apps connected, only the exceptions drawn, tap an app to change it
- wizard-app-manager#298 [feature] Strong suggestion: Connections map in plain groups — Agents, Apps, Connectors and System, decided by each app's wizard.md
- wizard-app-manager#300 [feature] Strong suggestion: Connections map v3 — four groups with a 'Comes with Wizard' badge; apps kept apart by default with only real connections drawn
- wizard-app-manager#310 [feature] Connections on a phone: a plain list, the map one tap away

Fixes:
- wizard-app-manager#212 [fix] Recommended fix: pause Hermes updates behind the shared exact lock
- wizard-app-manager#243 [fix] Recommended fix: Hermes restart after an agent-run install waits for the live chat turn
- wizard-app-manager#252 [fix] Recommended fix: host dashboard applies owner edits of its environment and reports a failed reload
- wizard-app-manager#258 [fix] Recommended fix: installer reruns recreate connection apps, HTTPS-off owner step, approved Tailscale login waited for, official Hermes routes to hermes update
- wizard-app-manager#273 [fix] Recommended fix: backups finish on a busy agent and never publish an app without its data
- wizard-app-manager#275 [fix] Recommended fix: apps.json marks system apps so the launcher ring matches the spot defaults
- wizard-app-manager#278 [fix] Recommended fix: trusted exposure and truthful network identity
- wizard-app-manager#280 [fix] Recommended fix: default-app custody runs again
- wizard-app-manager#284 [fix] Recommended fix: default-app custody keeps the Troubleshooter's source without an app manifest
- wizard-app-manager#286 [fix] Recommended fix: app updates open new data folders after start
- wizard-app-manager#290 [fix] Recommended fix: installed apps with a fixed-name volume keep working after an App Manager upgrade
- wizard-app-manager#292 [fix] Recommended fix: backups no longer skip apps pinned by image digest
- wizard-app-manager#293 [fix] Recommended fix: apps can no longer act as the owner through the owner listener
- wizard-app-manager#301 [fix] Recommended fix: wam check warns when an app would break on older Wizards
- wizard-app-manager#302 [fix] Recommended fix: the agent sheet shows everything the agent can use, not the first 12
- wizard-app-manager#303 [fix] Recommended fix: update backups no longer pile up — keep the newest, expire this app's older copies after 12 hours (Hermes snapshots after 30 days)
- wizard-app-manager#304 [fix] Recommended fix (performance): interface-only releases install in about 2 minutes instead of the 10–20 minute installer rerun
- wizard-app-manager#305 [fix] Recommended fix: every box gets new app versions automatically (verified, rolled back on failure)
- wizard-app-manager#307 [fix] Recommended fix: app updates no longer roll back apps whose health endpoint refuses loopback
- wizard-app-manager#311 [fix] Recommended fix: updates no longer fail at wizard link while the App Manager rewrites app skills
- wizard-app-manager#312 [fix] Recommended fix: the App Store data service starts again (adapter imports a shell module)

Maintenance (release mirrors, docs, deps): #233, #235, #239, #240, #241, #244, #245, #246, #247, #248, #254, #255, #256, #257, #261, #262, #263, #264, #266, #269, #281, #295, #296

## Evidence

## Installed upgrade 0.3.73 → 0.3.74 on a disposable KVM guest

**Result: PASSED** (20261029T043802Z → 20261029T045158Z UTC)

**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH). Root stock Hermes (Hermes Agent v0.22.5 (2026.9.24) · stable · local bf0203a794a0) from the official installer (`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key (stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. Headscale has no Serve, so installs end box-only. Nothing ran on a real box. Upgrade release base: https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/release/0.3.74-mirror/releases. os.sh sha256 `fa9271d0713d613b…`.

- Install 0.3.73 (public command, agent-run, `WIZARD_STRICT=1`): done in 587 s; release.json 0.3.73 pinned.
- Upgrade to 0.3.74: done in 140 s; release.json 0.3.74 pinned, 27 checks, 0 failed.
- Hermes config.yaml/.env/SOUL.md: identical (config.yaml `13a542c3…`, .env `3a3b8636…`, SOUL.md `36c1f5a2…`).
- After: Hermes API /health 200, gateway active, shell 302, `wizard doctor` FAIL 0, `wam doctor` FAIL 0.

<details><summary>Containers after the upgrade</summary>

```
browser_wizardapps-browser-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T04:46:24.881411906Z
browser_wizardapps-browser-engine-1 sha256:0dc9356ce1428962cddcf938dab712a8c56de79adc326f9138298f13df440071 2026-10-29T04:46:24.392960964Z
files_wizardapps-files-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T04:44:00.420026758Z
files_wizardapps-files-engine-1 sha256:a469ea076d4a1b4b1d86a41d130f2f536cd9da996a2b1fb39c0d7635f9d89b9a 2026-10-29T04:44:00.286994045Z
notifications_wizardapps-notifications-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T04:47:03.208692056Z
notifications_wizardapps-notifications-engine-1 sha256:4c599cf0818965782f93f652bd843e92714992e84d6b88ad17713dc0951cda1f 2026-10-29T04:47:03.401716513Z
runtipi sha256:530076256e67469f2261c516b44e3bd64fea869c81adee2d65dc1658a7f22f3a 2026-10-29T04:50:42.360705606Z
runtipi-db sha256:0472f5295d05c211cc42b3daa5e84a128e390c5267b60ced9fe044bcf4edfdb8 2026-10-29T04:39:32.629113494Z
runtipi-queue sha256:21577d148f4f7563a87d761862fa353f59348a094833ca8b1b1a46a8102dffce 2026-10-29T04:39:32.480274021Z
runtipi-reverse-proxy sha256:4cda3393930dceff030e144b46260e96e1337c9cfaa4fed81c90cb8f4d498f57 2026-10-29T04:39:53.46941255Z
runtipi-wizard-release-index-1 sha256:530076256e67469f2261c516b44e3bd64fea869c81adee2d65dc1658a7f22f3a 2026-10-29T04:49:35.203471885Z
secret-drop_wizardapps-secret-drop-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T04:46:39.104433242Z
secret-drop_wizardapps-secret-drop-engine-1 sha256:29ebc6a7846e6036afc471dc6ddcee31a9cac3a0ce8f00d59cd1186c80c03302 2026-10-29T04:46:38.96226493Z
transcriber_wizardapps-transcriber-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T04:43:38.47391894Z
transcriber_wizardapps-transcriber-engine-1 sha256:2163775b6df5e451a71200e8f675fed68dbd8ab184fc604453d549e486f22fd2 2026-10-29T04:43:38.329194325Z
wizard-agent-service_wizardapps-wizard-agent-service-1 sha256:dd204c42dbf37403e6b98ad1b3f3b2d9209609b639395188aded90b724803c3a 2026-10-29T04:44:19.831069705Z
wizard-chatgpt_wizardapps-wizard-chatgpt-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T04:45:04.705469471Z
wizard-chatgpt_wizardapps-wizard-chatgpt-engine-1 sha256:72be4ede5a2e0151eea3a9050611352b0b14c044e56c1202a25442f4003552e3 2026-10-29T04:45:04.544365833Z
wizard-claude_wizardapps-wizard-claude-1 sha256:1b668429b3511ab407d8e00648891631b0b1a4d7e15e3ca70f38ab5b91ad4ab4 2026-10-29T04:45:43.533428191Z
wizard-claude_wizardapps-wizard-claude-engine-1 sha256:7e7956086a2f8810b46666e5948c71ffc2637e1e54566eaffb100fb8acdc406c 2026-10-29T04:45:43.3651063Z
wizard-connection-router_wizardapps-wizard-connection-router-1 sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf 2026-10-29T04:47:39.101653195Z
wizard-ux_wizardapps-wizard-ux-1 sha256:314697acd8220a51bba598b8f51f24d1d7df8a31780b22ec9e16a5ad84fbe508 2026-10-29T04:44:31.576356887Z
wizard-voice-service_wizardapps-wizard-voice-service-1 sha256:a279274949c03bd8fe244f083f727e41f51d7040e58a48288089621f5ab27e89 2026-10-29T04:47:32.919664649Z
```
</details>

Note on the release base: the upgrade read `releases/` from the mirror PR branch (`release/0.3.74-mirror` on the public wizard-app-manager repo) because the mirror's hosted CI was queued; that file is byte-identical to wizard-os main and to the merged mirror (sha256 `dea8615d…`). The 0.3.73 install used the public mirror (main).

## Quick interface update after 0.3.74 (rig, test-only release)

On the same guest (`--keep`) after the upgrade, a never-published test release 0.3.940 = 0.3.74 with only the Wizard UX pin moved (`db361987` → published main `aad4b24d`, `sha256:d260f4af…`, run 40814189427) was served locally (`WIZARD_RELEASE_BASE`).

- `wam updates`: installed 0.3.74, latest 0.3.940, `quick: true`. (0.3.73 → 0.3.74 itself is not quick: the App Manager moved, so the installer ran, as designed.)
- `wam updates --apply`: quick path, done in **109 s** (110 s wall); release.json 0.3.940 pinned, 27 checks, 0 failed; Wizard UX running `sha256:d260f4af…`; shell 302.
- Every other container kept its image and start time except `runtipi` and `runtipi-wizard-release-index` (recreated by the index refresh, as designed); Agent Service and Hermes were not restarted.
- After: `wizard doctor` FAIL 0, `wam doctor` FAIL 0, Hermes API /health 200.

So the first interface-only release after 0.3.74 should reach boxes on 0.3.74 in about 2 minutes.

## Not checked

Real Tailscale/HTTPS/Serve, real chats and sign-ins, phones, a fresh install of 0.3.74, named-user (non-root) owners, and the quick path's rollback on this exact pair (covered by the #304 QA with test releases 0.3.900–0.3.903).
