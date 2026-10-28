# App design rules (v0, foundation)

**Status: proposed foundation, 27 Oct 2026 (Miguel, written by Oscar).** It replaces "every app picks its own width and its own pop-up" with one shared baseline that is better than what we have now. It does not settle taste. Treat it as a starting point that the owners below are expected to change.

## Who owns what

| Area | Owner | What that means |
|---|---|---|
| Design: the rules and values in this file, `tokens.json` and `ui.css` | **Robert** (`@hacalastudio`) | Changes widths, spacing, type, components and patterns. Whatever he changes here reaches every kit app at once. |
| Process: how the rules are checked, reviewed and rolled out to apps | **Jan** (`@JanMesaric`) | Decides how the rules are enforced (for example in the app checker or the Agent review) and how the apps move to new versions of the kit. |
| `style/` code and the shell | **James** (`@jdefleur`) and **Archimedes** (`@defleur-agents`) | Keep the kit, the tokens and the shell's copy (`wizard-ux/web/kit/`) in step. The shell owns Settings, previews and window chrome. |
| Everyone | All builders and agents | Proposes a change to a rule as a PR to this file. Keeps their own apps on the rules. |

A change to a rule is a PR to this file, plus `ui.css` or `tokens.json` where needed, followed by `wizard-ux/web/kit/` (the live copy). The app checklist at the end is what reviewers look for in app PRs.

## Why

An audit on 27 Oct 2026 covered 22 installed apps. Kit apps capped their content at six different widths: 640, 680, 760, 820 and 1040 px, plus none. Most of them inherited the cap from `.wz-app { max-width: 640px }` in this kit. Windows are already sized by the shell, so a cap inside a window only adds empty side margins. As a result, ChatGPT is a narrow centred list while Cloudflare is a wide card grid, even though both connect an account. There were also five different home-made pop-ups, each closing a different way.

## Rules

### 1. The window is the page
- The app fills its window. **No `max-width` on the app frame.** Side padding is `--wz-gutter` (12 px narrow, up to 28 px wide).
- Wider windows get **more columns** (`.wz-grid`), not wider rows or bigger margins.
- One exception: **long reading text** (reports, articles, help) caps its line length with `.wz-prose` (about 72 characters). Only the text is capped; the page still fills the window.

### 2. Layout follows the window's width, not the device
- Use container queries on `.wz-app` (`container-type: inline-size`), never the device type or user agent.
- **Narrow** below 600 px: one column, the phone layout. **Medium** 600–959 px: two columns where the content is a set of items. **Wide** 960 px and up: up to three columns, or a list plus detail.
- A narrow desktop window must look like the phone, and a phone in landscape like a narrow window. Nothing reads "made for mobile" or "made for desktop".

### 3. No duplicate title
- In a window or full screen, the shell's title bar names the app, so `.wz-head` stays hidden. This already exists. An app never draws its own big title or logo header above its content.

### 4. One pop-up: the sheet
- Every pop-up inside an app is a `<dialog class="wz-sheet">`. In narrow windows it is a **bottom sheet**: full width, rounded top and a grip. In wide windows it is a **centred card**, 520 px at most.
- It always closes **five ways**: the × button (`.wz-sheet-x`), Esc, tapping outside, Back (through `WizardApp.back` in apps that use it, otherwise `window.__wizardCloseOverlay()`) and swiping down on the grip. `style/sheet.js` wires all five.
- No side drawers, no extra windows and no full-page takeovers for options, details or confirmations. A sheet holds one task. A flow longer than one screen is a page in the app, with Back.

### 5. One pattern per job
- **Connector apps**, which connect an account (ChatGPT, Claude, Tinfoil, Cloudflare, SimpleFIN, YouTube Music, Monarch…), share one layout:
  1. A **status card** (`.wz-conn`): the service sigil, the service name, one status pill (`.wz-pill.ok` Connected · `.warn` Needs attention · `.off` Not connected) and one line saying what the agent can do with it.
  2. **Accounts** (`.wz-sec` + `.wz-list`): one `.wz-row` per account with its own pill. Usage or limits show as `.wz-meter` under the row. Rarer actions (rename, make default, disconnect) go in a sheet opened from the row.
  3. **One primary action** at the bottom: `Connect` when there are no accounts, `Add account` otherwise (`.wz-button`).
  4. **Details** (IDs, scopes, versions, diagnostics) go in a collapsed `<details class="wz-more">` at the end, never on the first screen.
- **Lists of things** (cards, reports, transactions) use `.wz-list` rows in narrow windows and `.wz-grid` cards in wider ones.

### 6. Shared basics
- Colours and type come from the kit variables only, never hex values or fonts in app CSS. Intentional app typography, such as a reader's serif, is allowed through the type roles.
- Buttons: `.wz-button` (44 px tall), with `.secondary` for the second choice. At most one accent button is visible per screen.
- Section headings: `.wz-sec-h`. Status: `.wz-pill`. Numbers that change: `.wz-meter`. Nothing new is invented when a kit class exists.
- Touch targets are at least 44 px. Text is at least 13 px. The one exception is short uppercase labels and counters (`.wz-sec-h`, `.wz-count`), which may go down to 11 px.

### 7. Shell surfaces follow the same idea
These are the shell's job (wizard-ux) and proposed there, not in apps:
- **Settings** opens as a normal window on desktop and as the same full-height sheet on phone. It closes like everything else: the ×, Esc, Back and ⌥W.
- **Previews** (files, links, images) open as a window on desktop and as a full-screen sheet on phone, with the same close gestures.

## App checklist (for app PRs)
- [ ] Loads `wizard-ui.css`, and the app frame has no `max-width`.
- [ ] Looks right at 360, 700 and 1200 px window widths, in at least two skins, one of them light.
- [ ] Every pop-up is a `.wz-sheet` that closes with ×, Esc, outside tap, Back and swipe-down.
- [ ] Connector apps follow pattern 5: status card, accounts, one primary action, details collapsed.
- [ ] No own title header in a window. No hex colours in app CSS.
