# Promote 0.3.102 (hand cut, wizard-os #395)

## Why

Miguel approved shipping the wizard-os #386 security fixes ("ship"), and his standing rule is: "If you're shipping a fix, ship it straight to stable" (30 Oct 2026). Stable 0.3.94 lacks:

- oscarhenrycollins/notifications#18 Recommended fix: other websites can't read or publish notifications through ntfy (ntfy's built-in `Access-Control-Allow-Origin: *`, no login); `/mcp` handshake box-only
- oscarhenrycollins/files#2 Recommended fix: through Tailscale Serve, Files (File Browser noauth) answers only the box owner
- humanitylabs-org/wizard-app-manager#408 Recommended fix: app update writes the owner's tailnet login for recipes that started declaring it (so existing Files/Tinfoil installs get protected)
- oscarhenrycollins/notifications#19 Recommended fix: Landscapes Light gets the minimal inbox and swipe strip

Not pinned by a release (they reach boxes through the nightly app updates from the index): oscarhenrycollins/wizard-microsoft#1 (0.2.6) and wizard-app-store#56 + oscarhenrycollins/wizard-tinfoil#12 (0.3.8). Not shipped: wizard-ux#840 (waiting on required review).

## What changes (0.3.94 → 0.3.102)

**Classification: feature** (launch-phase fast-track, DECISIONS #93): Latest 0.3.95–0.3.101 already carried changes that are not provably fixes, and the App Manager and Notifications pins bring more along.

- wizard-ux#513 [maintenance] Maintenance: canonical origin-less phone release tooling and signed origin-custody proof
- wizard-ux#714 [fix] Recommended fix: Wizard ID approval shows the raw request when an event only partly matches a known action
- wizard-ux#732 [fix] Recommended fix: replies with pictures no longer show twice or as raw MEDIA text
- wizard-ux#759 [fix] Recommended fix: keep the Resources Back control tappable
- wizard-ux#766 [fix] Recommended fix: launcher tiles for agent Pages open in the Pages window (#766)
- wizard-ux#769 [fix] Recommended fix: Replace Installed with Open after install
- wizard-ux#770 [fix] Recommended fix: ignore gitleaks false positive on app-logo storage key
- wizard-ux#772 [fix] Recommended fix: chat files download from the card; PDFs open in the viewer
- wizard-ux#773 [fix] Recommended fix: chat file Download/viewer styles use tokens (style check)
- wizard-ux#774 [feature] James: keep classic Home, Settings and skins by default; Miguel's Home as his tweak
- wizard-ux#777 [fix] Recommended fix: desktop Settings from Home stays on Home
- wizard-ux#778 [feature] Miguel's tweaks: drop Home resource bars; Defer and Done join the model switch
- wizard-ux#779 [feature] Settings › Look: tweaks grouped by person, each with an All switch
- wizard-agent-service#284 [fix] Recommended fix: Import keeps host-shared paths on the host (main, conflict resolved)
- wizard-agent-service#285 [feature] Show routed agents' notes paths as their notebook, not [private attachment]
- wizard-agent-service#286 [feature] Agent notebooks for Notes: owner-only, read-only route
- wizard-app-manager#369 [maintenance] Maintenance: mirror Wizard OS 0.3.91 and 0.3.92 onto latest
- wizard-app-manager#370 [maintenance] Mirror 0.3.93 onto latest (byte-identical to wizard-os #349)
- wizard-app-manager#371 [fix] Recommended fix: the wizard-os plugin follows the release's Agent Service commit
- wizard-app-manager#372 [maintenance] Maintenance: mirror Wizard OS 0.3.94 onto latest (release train)
- wizard-app-manager#373 [fix] Recommended fix: an update survives Ubuntu's automatic restarts and keeps its release
- wizard-app-manager#374 [maintenance] Maintenance: mirror Wizard OS stable 0.3.94 (release train, feature)
- wizard-app-manager#375 [feature] links: keep an app's Wizard address when Serve can't be read; serialize link refreshes
- wizard-app-manager#379 [maintenance] Maintenance: mirror Wizard OS 0.3.95–0.3.97 onto latest (release train)
- wizard-app-manager#380 [maintenance] Mirror 0.3.98 onto latest (release train) (#380)
- wizard-app-manager#381 [maintenance] Maintenance: mirror Wizard OS 0.3.99 onto latest (release train)
- wizard-app-manager#383 [feature] App update notice: use display names, not internal ids
- wizard-app-manager#384 [maintenance] Maintenance: mirror Wizard OS 0.3.100 onto latest (release train)
- wizard-app-manager#385 [feature] App renames: an app's id follows its name (renamed_from), migrated with rollback; naming lint
- wizard-app-manager#388 [fix] Recommended fix: app checks distinguish acceptance harnesses from hosted code
- wizard-app-manager#389 [fix] Fix: phone sync reads the public release mirror (wizard-os is private)
- wizard-app-manager#391 [maintenance] Maintenance: mirror Wizard OS 0.3.101 onto latest (release train)
- wizard-app-manager#392 [feature] Retire migrated app ids and update the Connected accounts default
- wizard-app-manager#393 [fix] Recommended fix: reach every provider without breaking install checks
- wizard-app-manager#398 [feature] Store installs recover after a failed release; apps open in every shell alias
- wizard-app-manager#401 [feature] wam standard: show where a box drifts from the Store
- wizard-app-manager#402 [fix] Recommended fix: preserve private sources and detect never-pull overrides
- wizard-app-manager#408 [fix] Recommended fix: app update writes the owner's tailnet login for recipes that started declaring it
- notifications#13 [feature] Reply only on Wizards that support Chats drafts (wizard11)
- notifications#14 [fix] Recommended fix: Notifications shows under Agent apps on the Connections map
- notifications#15 [feature] 2.29.0-wizard15: ship the box build (inbox marks + sources); run-as, thumbnail folders and ntfy exempt hosts as owner settings
- notifications#18 [fix] Recommended fix: other websites can't read or publish notifications through ntfy; /mcp handshake box-only (wizard16)
- notifications#19 [fix] Recommended fix: Landscapes Light gets the minimal inbox and swipe strip like the other Mizel palettes
- files#2 [fix] Recommended fix: through Tailscale Serve, Files (File Browser noauth) answers only the box owner (wizard3)

Not checked: real Tailscale Serve/HTTPS on the rig (headscale has no Serve), real chats and sign-ins, phones, a fresh install. The security gates themselves were verified on Miguel's box (oscar-main) after `wam app-updates --apply`: cross-origin ntfy reads/preflights 403 with no CORS header, tailnet `/mcp` handshakes 403, forged stranger / no-login proxied requests to Files and Tinfoil 403, owner views and the shell bell count 200, agent MCP tools answer.

## Upgrade test

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
