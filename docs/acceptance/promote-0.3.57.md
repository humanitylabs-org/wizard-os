# Promote 0.3.57: optional Add to Home Screen beat in Stable onboarding

## Decision and scope

Miguel (owner thread, 26 Oct 2026) asked that the chat handoff stop explaining PWA installation: os.md is trimmed in wizard-app-manager #246, and installing becomes part of onboarding. This is a stopgap until native iPhone, Android and desktop clients exist. He authorized shipping it to Stable. The change restores install guidance that used to live in the chat text, but it adds a new optional tour beat. It is therefore classified honestly as a **feature**, fast-tracked under DECISIONS #93 with the owner's approval. It is not called fix-only.

0.3.57 is Stable 0.3.55 plus **only** wizard-ux #548. Compared with `releases/0.3.55.json`, the runtime pins that change are:

- `components.wizard-ux.commit`: 26c3b20 → `ffa4c6366f9267e3ed5ca2fbc710ca9c8ad97686`, plus its note;
- `images.wizard-ux`: ref, digest and ci_run;
- `default_apps.shell.commit`.

Everything else is metadata (`version`, `name`, `about`). The App Manager, Agent Service, Troubleshooter, Hermes and every other default-app pin are byte-for-byte 0.3.55. No main/Latest feature code rides along, and there are no migrations and no owner-data changes.

| PR | Merge | Change |
|---|---|---|
| wizard-ux #548 (into `release/stable-onboarding`) | `ffa4c63` | The phone tour ends with one optional Install beat, offered only where installing can work and Wizard isn't installed yet. **Android Chrome:** one Install button calls the browser's real install prompt. `pwa-install.js` shares its single deferred `beforeinstallprompt` as `WizardPwaInstall`; its top banner is held while the tour runs; a dismissal or skip holds for both. **iPhone Safari:** "Tap Share, then Add to Home Screen". **In-app browsers** (Telegram/WhatsApp/Instagram… or an iOS web view): "Open this link in Safari/Chrome to install it". **No beat** in standalone mode, in the Wizard native apps, in Chrome/Firefox on iPhone, or on Android without a prompt. Skip this step, Skip tour, Back and Practice again all still work. Desktop is unchanged. |

The forward-port to main is wizard-ux #549, which is labelled `needs: james review`. Latest testers keep the exact 0.3.56 bundle via 0.3.58, which this PR cuts onto `latest` because latest may not trail stable. 0.3.58 does not contain the Install beat.

## Published pins

- Manifest `releases/0.3.57.json` SHA256 `69d54ea0cf9e2a5361eabedcfe6510071594868803b743cdf268e89dd05544db` (canonical wizard-os #250, merge `d592d73e03c3680dad27b9a8cdec1ecb3f3d0afd`).
- UX image `ghcr.io/humanitylabs-org/wizard-ux:sha-ffa4c6366f9267e3ed5ca2fbc710ca9c8ad97686`, digest `sha256:a667cd87f0446dce9e6117ff05adf741df47979d380a31c946cd400e11ed721c` (amd64 + arm64).
- The image comes from the official GitHub-hosted maintenance dispatch https://github.com/humanitylabs-org/wizard-ux/actions/runs/40292759016 with `expected_sha` equal to the branch SHA. Validate, publish, attest (signed provenance verified for the exact source commit), finalize and anonymous-pull all succeeded.

## Verification

- **Unit tests.** wizard-ux `npm test` on the maintenance source: 760/760.
  - The new `tests/tour-install-step.test.mjs` runs the real `tour.js` and `pwa-install.js` together; 8 of its first 9 tests fail on 26c3b20.
  - The Codex P2 fix (a dismissal holds for the tour) has its own test, which fails on the previous head.
- **Codex review.** It completed on the exact head `a151e9b` with no unresolved findings. All checks were green, and the PR was merged with the owner's approval comment.
- **Real-browser matrix**, run in the Playwright v1.64.1 docker image (Chromium, WebKit, Firefox) with `/wizard/*` mocked locally. The probe and evidence are in the private scratch.

  | Cell | Engine | Expected |
  |---|---|---|
  | iPhone Safari | WebKit | Share hint; Done → end card; reload stays quiet; deep-link replay; Skip this step; Help → Practice again; Skip tour; the orb takes taps afterwards |
  | iPhone Telegram-like web view | WebKit | Open-in-Safari hint |
  | iPhone standalone | WebKit | No beat, "of 2" |
  | Android Chrome, emulated `beforeinstallprompt` | Chromium | No banner during the tour; Install calls `prompt()` exactly once inside a real user activation; then the end card; no banner afterwards |
  | Android Chrome, skip the beat | Chromium | Prompt never opened; banner snoozed |
  | Android Chrome, Skip tour | Chromium | The existing banner returns |
  | Android standalone | Chromium | No beat |
  | Android Telegram web view | Chromium | Open-in-Chrome hint |
  | Desktop | Chromium, WebKit, Firefox | Real desktop shell; one-step guide unchanged; desktop Chrome keeps its banner |

  - **Source build:** 11/11 PASS.
  - **Exact published image** (`@sha256:a667cd87…`, served by its own nginx as a container): 11/11 PASS.
  - **Old 26c3b20:** 5/11. The banner shows during the tour and there is no beat; the desktop and standalone cells are unchanged.
  - Screenshots of the install beat (iPhone Safari, Telegram-like, Android Chrome) were inspected visually.
- **Known artefact.** WebKit intermittently reports `TypeError: Load failed` when the probe reloads mid-boot, because the shell's own fetches are cancelled by the navigation. A navigation-only control reproduces it on unmodified 26c3b20: 7/15 and 3/10 runs, against 4/15 and 2/10 on the candidate. It is listed separately in the matrix receipts, never hidden. No other page errors occurred.
- **Image content diff, 0.3.55 vs 0.3.57 UX image.**
  - Only `core/tour.js`, `core/tour.css` and `pwa-install.js` differ in content, and their sha256 equals the reviewed source.
  - Twelve HTML/JS files differ only by the build release stamp (`?v=…`).
  - nginx configuration, entrypoint and every other file are identical.
- **Installer acceptance of the manifest.** The 0.3.57 file fetched from the wizard-app-manager mirror PR head (byte-identical, SHA256 above) was run through the installer's own `get.sh` pin validator together with the shared Hermes lock. It resolves `PIN_UX_IMAGE=…@sha256:a667cd87…`, and the App Manager and Agent Service pins are unchanged from 0.3.55.
- `tools/check_release.py releases/0.3.57.json`: ok. `promote_stable.py check`: channels ok.

### Upgrade test 0.3.55 → 0.3.57 (component level), 26 Oct 2026 UTC

This follows the same standard as 0.3.55: the real component step, run in an isolated sandbox. It used the App Manager code pinned by both releases (`wizard-app-manager` `d926eec199c6440249c799677ff87585ece76a96`) and called `wam.alongside.write_shell_override(..., 'wizard-ux', role='shell')`, the step `wam alongside` runs for the shell app. `WIZARD_RELEASE_PINS` was set to the canonical 0.3.55 file and then the 0.3.57 file. The sandbox had a temporary Wizard home and Runtipi `user-config` tree. Docker Compose recreated the container from the override that step wrote, in its own project on loopback, with a local mock as the Agent Service origin. Nothing on any live box was read or changed.

- **0.3.55.** The override pins `wizard-ux@sha256:03a93684…`. The running container's image is that digest, `/wizard/v1/setup` proxies through, and the served `tour.js` is the old one.
- **Upgrade to 0.3.57.**
  - The override pins `wizard-ux@sha256:a667cd87…`, and `previous_images` records `03a93684…`.
  - Compose recreated the container, and the running image is `a667cd87…`.
  - The served `core/tour.js`, `core/tour.css` and `pwa-install.js` have the same sha256 as the reviewed source.
- **Browser matrix against the upgraded container:** 11/11 PASS. The cells are the same as above.
- **Rollback to 0.3.55**, then re-upgrade to 0.3.57: the image and the served files switch back and forth as expected.

| Receipt (private scratch) | SHA256 |
|---|---|
| before-0.3.55.json | `f67a68826019f5773804ac3db8afa8eb6c05f3493bbf2d1dca965f44f0f55394` |
| after-0.3.57.json | `14439a8578def1f4f7be9d18735aa18fa4f44d469a8e6b1acd7d679f54abc446` |
| rollback-0.3.55.json | `467bc94c229c366d2b7ad4984917cd1e8cde9c94e84ffb9e51aa0051254f64b1` |
| reupgrade-0.3.57.json | `6e8367c1a40c1ae53edd67155da60744fd75da0489d1cced1704051ead3ba6a7` |

## Not checked / caveats

- **No full installer upgrade or fresh install was run on a real box.**
  - `demo` was wiped and taken offline for the owner's own first-install test and was deliberately not touched.
  - `demo-2` and `demo-3` are offline.
  - No other disposable VM was available: this host has no KVM, and the Lima acceptance runner needs the ARM build machine.
- The upgrade test above was component level: the real pinned App Manager pin step plus a Compose recreate. It was not a full `os.sh` installer run. The upgrade 0.3.55 → 0.3.57 replaces one immutable UX image digest through the same installer/WAM path as 0.3.53 → 0.3.55. **Run the installer upgrade and a fresh install on `demo` when it is back.** Miguel's next fresh install will exercise this exact path.
- Emulation cannot prove three things: a real iPhone Add to Home Screen, the real Telegram in-app browser, or the real Android install sheet.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted`; Update now still works.

Rollback: point `releases/stable` back at 0.3.55 in both repos (it already has a valid promotion record). If a full return is needed, 0.3.53 also has one.
