# Promote 0.3.61: final three-step guide and a never-frozen orb on Stable

## Decision and scope

Miguel approved the final first-run wording verbatim in the owner thread on 26 Oct 2026. He asked for it to ship, with step numbers ("Step 1 of 3"), and then for the demo to be wiped for his final new-user test. He also reported a bug: in the iPhone Safari **browser** (not saved as an app), a tap on the orb started a voice note and then nothing responded. Tapping the orb again did not stop it, no button worked and he could not get out.

0.3.61 is Stable 0.3.59 plus two wizard-ux PRs on the Stable-only branch `release/stable-onboarding`:

| PR | Merge | Tier | Change |
|---|---|---|---|
| wizard-ux #567 | `08a50c57` | Recommended fix | **The orb never freezes in an iPhone Safari tab.** (1) A browser bar covering the page bottom lifts the dock, orb and Cancel above it. The visual viewport's covered strip feeds `--vv-b` and combines with the home-indicator inset as a union. A cover taller than 160 px is the on-screen keyboard and is ignored. (2) A second tap on a take whose microphone never opened ends it visibly. (3) An unanswered microphone request times out after 8 s with a message. (4) A borrowed meeting microphone is returned without an empty recording, and is kept and retried if the return fails. (5) During a take in the tour, the dock and its arcs sit above the tour layer, and the tour shows the message because it hides toasts. |
| wizard-ux #568 | `87b35bcb` | Strong suggestion (owner-approved feature) | **Three-step guide**, each beat labelled "Step N of 3", with "Skip this step" and "Skip tour" kept: Talk (moves on only on a real sent message; typed fallback when there is no mic), Reply ("Open Chats to see your Wizard's answer, then type a reply."; moves on only when a typed reply in a chat thread is delivered; no dim and no tap guard; the card steps aside while Chats is open), and Done (the owner's words). The Hide and Install beats are removed. Desktop guide: "Step 1 of 2" / "Step 2 of 2" with the same Done words. `pwa-install.js` is unchanged (the banner is held while the tour runs). |

The release is classified as a **feature** (it carries #568), fast-tracked under DECISIONS #93 with the owner's approval. It is not called fix-only.

Compared with `releases/0.3.59.json`, the runtime pins that change are `components.wizard-ux.commit` (325be039 → `87b35bcb1314961887c06da5f96ad10b50786fe6`, plus its note), `images.wizard-ux` (ref, digest and ci_run) and `default_apps.shell.commit`. App Manager, Agent Service, Troubleshooter, Hermes and every other default app are byte-for-byte 0.3.59. There are no migrations and no owner-data changes.

Latest moves to **0.3.62**: the 0.3.60 runtime pins unchanged (Latest may not trail Stable). The guide and the fix reach main through wizard-ux #569 (`needs: james review`). The chat handoff text (os.md) shipped separately as wizard-app-manager #253 (merge `6b33c2e7`) and is live at https://aiwizards.com/os.md.

## Published pins

- Manifest `releases/0.3.61.json` SHA256 `b049d493c0eea548ce5a987a4cb05985912020b13c80765f4f0071233ebb6665` (wizard-os #257, merge `d179358941b0209e958973a5a034aa043b5d4e99`). `releases/0.3.62.json` SHA256 `c6b9fde9bcd21fbd159ded564f59453b9f0bd8be925488238afef03df10ad057`.
- UX image `ghcr.io/humanitylabs-org/wizard-ux:sha-87b35bcb1314961887c06da5f96ad10b50786fe6`, digest `sha256:ecaba88e568ff2b6d90c6ca19a5b9bba153fcbb2eb7a4ee1aca3073c9e9acdb6` (amd64 + arm64).
- Official GitHub-hosted maintenance dispatch https://github.com/humanitylabs-org/wizard-ux/actions/runs/40339463332, with `expected_sha` equal to the branch head. Validate, publish, attest, finalize and anonymous-pull all succeeded.

## Verification

### Unit tests

- wizard-ux `npm test` on the published source: 769/769.
- #567's new tests fail first on 325be039:
  - `tests/orb-mic-never-opened.test.mjs` (8): silent latch, watchdog, visual-viewport lift, union with the safe area, keyboard by size, meeting loan returned / kept and retried / capture invalidated, z-order;
  - plus the tour `voicefail` test.
- #568's rewritten `tests/tour-skip-step.test.mjs` (12) and the updated desktop, end-layout and my-skin tests: 10 fail on the #567 base.

### Codex review

- #567: six P2 findings over five rounds. Each was fixed with a test that fails on the previous head and the thread was resolved. The final review on `27f12e4` had no findings.
- #568: one P1 (the browser QA still measured the removed glyph row), fixed in `001bc23`. The final review on `e41bb62` had no findings.
- All required checks were green. Both PRs were merged with the owner's approval comment, without `--admin`.

### Stuck-orb reproduction (WebKit, iPhone Safari UA, not standalone)

The old Stable source (325be039) shows the bug two ways:

- **Bottom bar after the mic prompt.** The probe simulates Safari's bottom bar expanding after the microphone prompt: the visual viewport shrinks by 80 px and a tap-catching bar covers the bottom. `elementFromPoint` at the orb and at Cancel both return the bar, and the take stays `listen`.
- **Microphone request never answered.** The second tap is ignored and the take stays `listen`.

The old source fails **12 checks** across these cells; the new source passes 34/34. Demo logs agree: of Miguel's attempts, only one reached the box. Emulation cannot prove which of the two his phone hit, so both are fixed.

### Real-browser matrix

Real shells (phone `index.html`, desktop `desktop.html` via `core/shell.js`), Playwright 1.64.1 docker, writes stubbed. **176/176 PASS** on each of: the source, the **exact published image** (files extracted from `@sha256:ecaba88e…`) and the main forward-port candidate. Cells:

- iPhone Safari with a bottom bar;
- iPhone standalone;
- iPhone Telegram-like with no mic (typed);
- Android Chrome, mic granted and denied;
- desktop Chrome 1440 and 1280, Safari, Firefox;
- 6 stuck-orb cells.

Each phone cell checks:

- Step labels, a real send, Open Chats, opening a thread, a delivered typed reply leading to Done with the approved words, and tap to finish;
- reload stays quiet, Practice again replays it, and Skip this step works twice, then Skip tour;
- no Hide or Install text anywhere, the orb and Cancel work afterwards, and there are no page errors.

Screenshots were inspected.

### Image content diff, 0.3.59 vs 0.3.61 UX image

- Only `app.js`, `core/tour.js`, `core/tour.css` and `styles.css` differ in content. Each is byte-identical to the reviewed source at 87b35bcb.
- 10 HTML/JS files differ only by the build stamp.
- Nothing was added or removed.

### Installed upgrade on the demo box (`demo-4`, alongside, Hermes as root), 26 Oct 2026 UTC

The box ran 0.3.57 (Miguel's test). It was first moved to current Stable with the supported installer: `WIZARD_RELEASE=0.3.59 WIZARD_STRICT=1 bash os.sh start`. That gave `release.json` 0.3.59 pinned, 0 failed checks, UX `cd80f6f8`, and `wizard doctor` with 0 FAIL and "Hermes API answers".

Then **0.3.59 → 0.3.61** used the same installer with `WIZARD_RELEASE=0.3.61 WIZARD_STRICT=1`. **Disclosed override:** `WIZARD_RELEASE_BASE=https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/812e10bad90c1b6ae89d63ce198d246e62d9cd25/releases` (the WAM mirror PR head, before the mirror merged). The file there is byte-identical to canonical (SHA256 above, checked on the box).

| | before (0.3.59) | after (0.3.61) |
|---|---|---|
| `release.json` | 0.3.59 pinned, 0 failed checks | **0.3.61 pinned, 0 failed checks** |
| UX container image | `sha256:cd80f6f8…` | **`sha256:ecaba88e…`** |
| Agent Service image | `sha256:840a371c…` | `sha256:840a371c…` (unchanged) |
| Hermes `config.yaml` / `.env` / `auth.json` sha256 (prefix) | cc42ff06 / 1bfbdcd0 / bb28025e | cc42ff06 / 1bfbdcd0 / bb28025e (unchanged) |
| Hermes gateway | active | active |
| `wizard doctor` | 0 FAIL, Hermes API answers | 0 FAIL, Hermes API answers |

- The served `core/tour.js`, `core/tour.css`, `app.js` and `styles.css` from `https://demo-4…:8796/wizard-os-home/` have the same sha256 as the reviewed source.
- **Live WebKit/Chromium check against the upgraded box** (real GETs, writes stubbed so no messages were sent): **61/61 PASS**. Cells: iPhone Safari tour with the bottom bar (24), the stuck-orb cells (bar in the tour, bar + Cancel, mic never answered + second tap, 8 s timeout), desktop Safari and desktop Chrome.

## Not checked / caveats

- **Physical devices.** Emulation cannot prove what Miguel's iPhone 26.x Safari does with its bottom bar or its microphone prompt, real Add to Home Screen, the real Telegram webview, or a physical microphone. His final first-install test on the wiped demo is that check.
- **No fresh install of 0.3.61 on a clean box was run here.** The demo is wiped to stock Hermes for Miguel's own first install. That install runs exactly the evergreen path, which selects Stable 0.3.61.
- wizard-os Actions runners were queued (since 13:09 UTC) during these PRs. The same tests were run locally: `tools/tests` 213 OK.
- os.md wording: a Codex P1 on wizard-app-manager #253 asked to tell owners to install the Tailscale app. The owner chose this exact wording, so it was kept and answered.
- Boxes on 0.3.26–0.3.31 set to Automatic skip a fast-tracked stable as `unpromoted`; Update now still works.

Rollback: point `releases/stable` back at 0.3.59 in both repos (it has a valid promotion record), or further back to 0.3.57.
