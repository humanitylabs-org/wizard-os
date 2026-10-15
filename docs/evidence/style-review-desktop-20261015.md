# Appearance v1: current desktop and phone review

Candidate runtime assets: PR #36, `89ff5f69658481cdf0fec6715771f5ff0ab7910e`. No style redesign or runtime asset changes in this follow-up. Existing demo and five palettes reused.

## Reproduction

`style/qa-review.cjs` extends the earlier `qa-live.cjs` acceptance with:
- the actual `?view=skin` entry and visible Skin controls;
- desktop Chromium and Pixel 7 mobile-UA/touch emulation;
- five skins in window and fullscreen, with unsent form, open dialog, document identity and Back assertions;
- comparison to an actual Chats window on desktop (Nebula desktop glass intentionally differs from phone glass);
- delivered skin/appearance asset hashes, explicit browser-only injection flag, structured known issues and nonzero exit for issues.

Set `QA_URL` to the private authorized shell, `PLAYWRIGHT_PATH` to installed Playwright, and `QA_SHOTS` to an external-volume evidence directory. Use `QA_DEVICE='Desktop Chrome'` or `QA_DEVICE='Pixel 7'`. For a staged candidate, set `QA_APPS=''` and `QA_INJECT` to a JSON array containing `{id, name, prefix, url, dir, index:'demo.html'}`. `dir` must point to this repository's `style/`. The entry is injected only into this throwaway browser's registry response; it is **not** a deployment. After real promotion, omit `QA_INJECT` and set `QA_APPS` to the admitted review entry ID.

## Observed results

On Thales, using the delivered current shell and original PR36 runtime assets:
- token generation and protocol fixtures pass;
- original Chromium fixture suite: 43 checks pass;
- phone: 91 checks pass, zero issues;
- desktop: 86 checks pass, five recorded presentation mismatches (one per skin), exit 2.

The new Skin UI applies all five choices on both profiles. Transparent app/iframe layers, exact transport colors, retained unsent text/open dialog/document, nested Back and browser Back pass. Inspected screenshots show readable card/list/empty-state/input controls on the shell glass. Signal keeps its square component shapes. No native-device claim.

## Shared-host defect, outside style ownership

`wizard-ux/web/core/appearance-host.js` currently computes immersive presentation only from `.device.immersive .win.full`. Desktop fullscreen uses its own window-manager state and never matches this selector. Therefore every desktop fullscreen candidate frame still receives `presentation:'window'`, even though the app visually fills the screen. Color propagation is correct. Do not claim complete desktop Appearance v1 acceptance until the shell owner repairs this and reruns the test.

Do not patch skin palettes to compensate. Existing desktop Nebula window glass is `rgba(14, 9, 30, 0.9)`, while the phone uses `--sk-win`; compare against Chats rather than imposing the phone material on desktop.

## Promotion boundary

No App Manager, release manifest, Files surface, shared shell or launcher mutation was made. The installed builder's `install-local` path requires `--stage-only` and explicitly delegates production lifecycle elsewhere. The original generated app remains recovered for reuse, not represented as installed.

The parent receives an exact five-file static review payload plus proposed launcher link and hashes. This is a **shared-shell static review artifact**, not a WAM-installed app. Parent must promote that owned target or arrange canonical WAM installation, read back the registry, and test the exact uninjected review URL before describing it as live. Existing Skin entry is live; the candidate demo is not yet live.

Private screenshots include real Chats labels and remain in private evidence storage; do not attach them to a public PR without redaction.
