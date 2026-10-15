# Style extraction acceptance · t_24e03d53

Status: **runtime acceptance passed on Thales; staged for review, no merge or daily deployment**.

## Source and decisions

- Approved Appearance v1 rows #50–53 at Wizard OS base `be8cdf1d489161321c472ef88e600fdca2a122b8`.
- Extracted live skin source: Wizard UX daily `201b4e66d1c3d8a7c9772787721ba028bdce2d58`. Re-checked on 15 Oct against daily `dfb115082f230b2b8fcf4a081c606567be7e412b`: `skins.js`, `skins.css`, `appearance-host.js`, `base.css` unchanged; `chats.css` only gained an upload progress bar (no colour role).
- Five accepted skins, fourteen transport colour roles. Type/layout/motion defaults remain CSS-only. Miguel's manifest-field confirmation remains separate.
- WAM base `6ad71d8dd73974a822e821182936f4288d097b5f`. Four runtime assets are byte-identical, hash-locked distribution copies of this repo's `style/`.

## Locked Thales run (15 Oct 2026, 01:27–01:29 UTC)

- Host `thales.local` (macOS 26.7.1). Shared worker lock `/Volumes/ThalesMedia/AndroidBuilds/worker.lock`, inode 7016370, flock queued and acquired (0 s wait), released after the run. External-volume I/O that blocked the 14 Oct attempt had recovered; nothing was remounted or replaced.
- Exact sources (git archive of each head): wizard-os `f951fdcb531961dc429a1a325c3db5933df257bd` (tree `b13cefef2d12ec68b3efbaf6b97c847e7ffe34bd`); wizard-app-manager `48ea186e87b9054ad1243da49c5abcf58cde8a69` (tree `8e780478a351829dcea750363c1e3f1f9aac2b33`). Later wizard-os commits add only this evidence folder.
- One script ran every step; all exited 0.

| Step | Command | Result |
|---|---|---|
| Manifest checkers | `check_wizard_md.py examples/defleur-video`; `wam/wizardmd.py templates/hello-wizard` | both `COMPATIBLE` |
| Tokens | `style/generate_tokens.py --check` | JSON/CSS match |
| Distribution pin | `tools/sync_wizard_style.py --check --source ../wos` | template assets match `style/` |
| Protocol fixtures | `node style/test_client.cjs` | PASS |
| WAM suite | `pytest -q -rs` (uv, pytest + pyyaml) | 106 collected; **104 passed, 2 skipped** (no `jwt` module; remote wizard-os pin unreadable without auth, local pin checked) |
| Browser fixtures | `node style/test_browser.cjs` (Chromium, Playwright 1.63) | **43 checks PASS** |
| Generated app | `wam new` → `check --proposal` → `install-local --stage-only --run` (real Docker container) | health OK; API add + readback; MCP `tools/list` and `habits_list` call; served `wizard-tokens.css`, `wizard-ui.css`, `boot.js`, `theme-client.js` byte-identical to `style/`; page imports all four |
| Real shell | `node style/qa-live.cjs` against the daily phone shell (read-only) | **308 checks PASS** |
| Cleanup | compose down -v | 0 containers left |

### Browser fixtures (`style/test_browser.cjs`)

Standalone paints the Nebula base itself. Hosted: `boot.js` marks the document hosted with a transparent first paint before any context; for each of the five skins the exact colour roles apply, the canvas stays transparent, Signal turns square, and the document, unsent input, scroll position and an open sheet survive the change. A synthetic light scheme applies in immersive presentation. Rejected without state change or acknowledgement: stale revision, version 2, opaque canvas, missing role, `var()`, `inherit`, `url()`, unknown presentation, bad skin id, a same-origin sibling sender, and a foreign-origin frame. A retransmitted revision is re-acknowledged without a second theme event. Back closes the open sheet, then reports root.

### Real shell (`style/qa-live.cjs`)

Phone profile (Pixel 7) cold entry through `?open=<id>`. Every request other than GET/HEAD was refused inside the isolated browser context, so no box settings, app data or selections were written. Six apps × five skins × window and full screen. Each view asserts: app canvas transparent; every element from the frame up to the shell window transparent; the window paints the skin's own window material (the same `--sk-win` glass Chats sits on); text, secondary text, accent, base and border resolve to the exact token colours; the document was not reloaded.

| App | Client that answered |
|---|---|
| Topics, Music, Signal | the shell's own `app-client.js` (unchanged daily client) |
| Wisdom | **candidate** `appearance-client.js` (injected for its `wizard-appearance.js`) |
| Style QA Habits (fresh `wam new` app, real container) | **candidate** client from the template |
| Style QA Components (`style/demo.html`) | **candidate** client |

Back: the component demo's open sheet closed first (`hosted`), then Back went home; the other apps' first Back went home.

Screenshots were inspected by eye: every cell sits on its skin's glass with legible ink, no opaque slab in either presentation; the generated app shows its own title only in full screen, where the window bar is hidden.

- [Window, all apps × skins](style-tokens-t_24e03d53/shell-window.jpg)
- [Full screen, all apps × skins](style-tokens-t_24e03d53/shell-immersive.jpg)
- [Browser fixtures: standalone, Grove, Signal, synthetic light](style-tokens-t_24e03d53/fixtures.jpg)

### Side by side with Chats (desktop shell, Nebula)

The component demo opened next to the shell's own Chats window (read-only, same lock). Both windows paint the same glass (`rgba(14, 9, 30, 0.9)`); Chats' ink and the demo's ink both resolve to `rgb(243, 239, 255)`; the demo accent is the Nebula accent `rgb(185, 155, 255)`; the demo card is 14 px round with the faint ink-tinted surface and hairline Chats uses, and the input is the same pill shape. [Screenshot](style-tokens-t_24e03d53/side-by-side-chats.jpg).

## Not covered

- The desktop shell was driven only for the side-by-side (it has no skin switcher; Nebula).
- Topics, Music and Signal were verified with the live client, not the candidate one, because they do not load `wizard-appearance.js`.

## Next

James reviews the style (screenshots above). Miguel/Oscar review the WAM template PR. Both PRs stay unmerged under this task's authority. Daily Wizard, existing app code, manifest admission and the deployed builder are unchanged.
