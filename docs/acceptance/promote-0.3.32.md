# Promote 0.3.32 to stable: upgrade-test evidence (22 Oct 2026)

First promotion under DECISIONS #82 (fast track for verified fixes). Stable moves from 0.3.25 to 0.3.32.

## Box

The demo box is a wipeable Debian 13 VPS on the team tailnet (host `demo`). Its owner is the fresh `wizard` user, uid 1001, because a uid-1000 user already exists. Leftover root-owned `/tmp/runtipi-setup.sh` is kept on purpose (the regression fixture for WAM #135). Checks ran in headless Chrome over real Tailscale HTTPS against the shell origin `:8796`.

## Upgrade 0.3.25 → 0.3.32 (21 Oct, one box, no wipe in between)

| Step | How | Result |
|---|---|---|
| Fresh 0.3.25 | wiped box, `curl -fsSL https://www.aiwizards.com/os.sh \| bash -s start` as root | ok. Every release.json check ok. Troubleshooter ready. ([#87 comment](https://github.com/humanitylabs-org/wizard-os/issues/87#issuecomment-6314893812)) Store routes 404, "Installed status is incomplete" (the stable bug). |
| 0.3.25 → 0.3.28 | `WIZARD_RELEASE=0.3.28 bash -s start` | status ok, every check ok. Store data/install routes mounted. A real Get of Morning Report installed and rendered. ([#87](https://github.com/humanitylabs-org/wizard-os/issues/87#issuecomment-6316635515)) |
| 0.3.28 → 0.3.29 | installer rerun | ok. Store apps show Open and open in a Wizard window. ([#87](https://github.com/humanitylabs-org/wizard-os/issues/87#issuecomment-6318327472)) |
| 0.3.29 → 0.3.30 | Settings → Updates (channel latest, apply) | `installed: 0.3.30`. A Tinfoil Get flipped to Open with no reload. ([#87](https://github.com/humanitylabs-org/wizard-os/issues/87#issuecomment-6319396773)) |
| 0.3.30 → 0.3.31 → 0.3.32 | Settings → Updates | `installed: 0.3.32`. A real Store Get of Wisdom installed (job `installed`/`running`, about 8s) and Open rendered `/wisdom/` with no 421. ([#92](https://github.com/humanitylabs-org/wizard-os/issues/92#issuecomment-6321462615)) |

## Re-check on 0.3.32 (22 Oct, 02:35–02:40 UTC, before promotion)

- `GET /wizard-os-home/store-install/_updates` returned `installed: 0.3.32`, `latest: 0.3.32`, `stable: 0.3.25`, `installing: false`, `interrupted: false`.
- The shell answered 200.
- Troubleshooter: `/troubleshoot/` returned 200 and the pill read "All working". The details sheet lists every check. The shell window (`WizOpenApp('troubleshooter')`) opens `/troubleshoot/` hosted. Chat answered the quick check. The engines read Not signed in, which is expected on a box with no sign-ins.
- Store, every category: installed status is complete (no "incomplete"). Installed apps show Open or ✓ Installed, the rest show Get. The `store-data`/`store-install` calls are all 200.
- New Store Get, Cloudflare (Connections): `POST /store-install/wizard-cloudflare` returned 202, then "Cloudflare is ready", and the row flipped to Open with no reload. Open loaded `/wizard-cloudflare/` as the app's own page, which says "Owner gateway authentication is not configured." That is the Cloudflare connector waiting for its owner setup, not a routing error: no 403/421.
- Wisdom: Open renders `/wisdom/` ("Nothing on the shelves yet", Shared/My library).
- Screenshots (judged with vision): `demo-promote-store-0332-{cloudflare-before,cloudflare-after,cloudflare-open,wisdom-before,wisdom-open}.png` and `demo-promote-ts-0332-{page,checks,chat,shell}.png` in the operator's screenshot cache.

## Not re-done

- **Fresh 0.3.25 → 0.3.32 in one step, and a fresh install of 0.3.32.** On 22 Oct, Tailscale SSH to the box asked for an interactive login check, and the public address has no port 22, so there was no shell to wipe or reinstall. The 21 Oct chain above is the upgrade evidence. Every hop used the shipped installer rerun or the Settings → Updates path that owners use.

## Classification (fix vs feature, 0.3.25 → 0.3.32)

**Fixes, each with a regression test (the reason for this promotion):**

- WAM #143: Store routes on fresh boxes.
- WAM #146: trusted hosts for Store apps.
- WAM #150: same-origin Open.
- WAM #152: report installed only after routes exist.
- WAM #155: required origin list.
- WAM #148: portable paths.
- WAM #149: tests no longer delete the live dashboard.
- wizard-ux #273: Open right after Get.
- wizard-ux #282: no data.js/summaries.js 404.
- wizard-ux #279: image publishing.
- wizard-ux #269/#270: portable build settings.
- wizard-ux #260: recording repaint.
- wizard-ux #262, #263: Chats copy, pull to refresh.
- wizard-ux #248: composer caret.
- wizard-ux #253: Update burst.
- wizard-ux #266: connection pill.
- wizard-ux #265: picker labels.
- wizard-ux #267: Chats QA.
- wizard-ux #281: recording delete.

**Feature-like ride-alongs (already merged and live on latest):**

| Change | Risk | Why acceptable |
|---|---|---|
| WAM #138: updates default Ask me | medium | Changes behaviour for owners who never chose. 0.3.25 defaults to Automatic, so its nightly timer installs 0.3.32 once this record exists. After that the box is Ask me and gets no further automatic updates until the owner picks Automatic. This is the intended direction (James on WAM #83, Miguel 21 Oct). |
| WAM #141 + wizard-ux #268: stable/latest channels, Settings picker | low | Additive. Default channel is stable. |
| WAM #140: sealed Chats slot (no default app), new App Manager image | low | Nothing installs unless an owner picks a Chats app. The image is the official build. |
| WAM #153: `runtime.package: source` | low–medium | Only apps that declare it (Wisdom) take the new path. Proven by the Wisdom Get. |
| wizard-ux #272: Settings redesign (index with pages) | medium (big UX change) | Strong suggestion, labelled `needs: james review`, but already merged on main. Owners see a different Settings layout. Verified only through Updates, not page by page. |
| wizard-ux #15: first-run Setup + phone QR | medium | Fresh-box first run. Not re-proven on a fresh 0.3.32 (no shell). |
| wizard-ux #256 (Chats views), #258 (own app screens), #254 (My skin scripts, owner-approved) | low | Opt-in surfaces. |
| New skins and skin tweaks (#203, #257, #259, #244, #246, #249, #252, #261, #264, #271, #274–#277, #280) | low | Scoped to skins. The default skin is unchanged. |

Strictly read, #82 would give this release a 72h soak (until 24 Oct 16:39 UTC) because of these ride-alongs. It is promoted now on Miguel's explicit call: the demo tests pass, and stable's fresh-box Store is broken until it moves. The ride-alongs are listed in the record's `fast_track.notes`.
