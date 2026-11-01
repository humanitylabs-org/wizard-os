# App design rules (v0, foundation)

**Canonical app style guide.** Foundation: Miguel, written by Oscar, 27 Oct 2026; enforcement and component detail requested by James, 29 Oct 2026. Existing Robert-owned design values remain authoritative; this is not a new look.

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
- Status has its own colours: `--wz-success` (Connected, done) and `--wz-warning` (Needs attention), set per skin in `tokens.json`, with `-light` versions for light schemes, plus `--wz-danger` for errors. Status never borrows the accent: the accent means "act here".
- Section headings: `.wz-sec-h`. Status: `.wz-pill`. Numbers that change: `.wz-meter`. Nothing new is invented when a kit class exists.
- Touch targets are at least 44 px. Text, including section labels and counters, is at least 13 px.

### 7. Shell surfaces follow the same idea
These are the shell's job (wizard-ux) and proposed there, not in apps:
- **Settings** opens as a normal window on desktop and as the same full-height sheet on phone. It closes like everything else: the ×, Esc, Back and ⌥W.
- **Previews** (files, links, images) open as a window on desktop and as a full-screen sheet on phone, with the same close gestures.

### 8. Thumb-first in narrow windows
Miguel, 31 Oct 2026. In narrow windows (below 600 px) the things you act on most sit nearest the thumb, like Chats.
- **Arriving-over-time lists flip:** feeds, inboxes, notifications and message threads put the newest item at the **bottom**, open scrolled to it, and stay pinned there when new items arrive or items are dismissed. Date headers run oldest at the top to Today at the bottom.
- **Primary controls go to the bottom:** the screen's filter chips, its main actions and its one input (search box, composer) sit in one bottom bar above the safe-area inset. A mini player or progress bar stacks directly above it. Toasts appear above the bar, never over it. Sheets already open from the bottom.
- **Do not flip** content that is read from the top or ranked: settings, documents, reports, articles, forms, grids such as the launcher, and search results ranked best-first. Ranked results next to a bottom input put the best match nearest the input.
- **Wide windows stay top-down:** newest first, controls at the top. Use the same container query as rule 2, never device detection.
- **Messaging apps (James, 31 Oct 2026):** a message thread stays bottom-anchored, newest message at the bottom next to the composer, as in every messenger; Messenger and Chats already work this way. A messaging app's **conversation list** (Messenger's chat list, the Chats list) is **not** flipped: newest conversation stays at the top, because people expect that from every messenger. Its primary controls may still sit in the bottom bar.
- **Applies to (apps today, 31 Oct 2026):** Notifications (inbox), Manager (Ready updates), Mail (inbox), Podcasts (My feed; the first to adopt it, in 0.3.2), Topics and Wizard Signal (chronological feeds; a ranked view such as Signal's For you keeps best-first). Bottom controls only: Morning Report (a report is read from the top) and MindFeed (one card at a time). Messenger and Chats: threads already comply; their conversation lists stay newest-first. Each app adopts the rule in its next update.

### Personal features are tweaks

James, 1 Nov 2026: features only one person wants live in `wizard-ux/web/tweaks/<author>/<id>/` and stay **off for everyone else**. A personal feature is not a new default or a permanent Settings item. Changes to core UX (Home, Settings or the shell) need James’s decision first. Skins and colours remain separate choices; do not turn colour variants into separate skins.

The existing tweak host, introduced in [wizard-ux #437](https://github.com/humanitylabs-org/wizard-ux/pull/437) and extended by [#755](https://github.com/humanitylabs-org/wizard-ux/pull/755) and [#779](https://github.com/humanitylabs-org/wizard-ux/pull/779), already supports:

- **Home:** a `layout` package can mount content at named slots, including `home-top` and `home-main`; Miguel’s `machines-home` is an existing example. This is an opt-in Home treatment, not a general installed Home-view provider.
- **Settings:** a trusted author with the `settings` capability can add sections to the existing System pages (`overview`, `ai`, `network`, `storage`). This does not grant replacement of Settings, arbitrary new pages, or changes to Look’s skin/colour controls.
- **Controls and menus:** a `layout` package can mount its own controls in declared slots (for example `thread-header-actions` or `dock-end`) and register a Back handler for its overlay. There is no generic tweak API for adding an item to every core menu. A missing slot or hook needs a small reviewed core extension, not a parallel menu implementation.

Implementation limits: packages are shipped with the shell and declared in its catalog; author folders are namespaces, not per-user access controls. Contributed tweaks start off on a fresh device, but existing explicit choices and migrated choices are preserved, and owners can opt in with any skin. Release-wide `catalog.defaults` are a separate mechanism for approved core features, not a shortcut for personal features. Choices currently use per-device storage, not account-wide profile sync. Capability filtering and cleanup are guardrails for trusted same-origin code, not a security sandbox or remote package installation system.

Source: `wizard-ux/web/core/{skin-host.js,experience.js,slots.json}`, `web/tweaks/catalog.json`. Credit Oscar (`oscarhenrycollins`, Miguel’s agent) for his contributions to the tweak and Look work; this rule does not approve the flattened Look picker introduced by #755.

## App checklist (for app PRs)
- [ ] Loads `wizard-ui.css`, and the app frame has no `max-width`.
- [ ] Looks right at 360, 700 and 1200 px window widths, in at least two skins, one of them light.
- [ ] Every pop-up is a `.wz-sheet` that closes with ×, Esc, outside tap, Back and swipe-down.
- [ ] Connector apps follow pattern 5: status card, accounts, one primary action, details collapsed.
- [ ] No own title header in a window. No hex colours in app CSS.
- [ ] Narrow windows follow rule 8: feeds and inboxes have newest at the bottom, and primary controls sit in a bottom bar; read-from-top and ranked screens, and messaging apps' conversation lists, are not flipped.

## Component contract (normative)

This file is the **one app style guide**, including shell-owned app screens. Robert's kit values are the design baseline; Jan owns rollout. `style/README.md` documents distribution, `spec/APPEARANCE.md` documents transport, `style/ICONS.md` documents sigils, and `wizard-ux/docs/COMPONENTS.md` inventories implementations. None is a competing visual guide. Propose a missing primitive here and in the kit, not in an app-only design system. Existing features and intentional reading/media treatments must survive migrations.

### Type, space and shape

| Role | Value / use |
|---|---|
| UI body, field, row title | `--wz-font-size` (15px), `--wz-line-height` (1.4), `--wz-font-ui` |
| Labels, metadata, pills, helper/error text | `--wz-text-sm` (13px minimum), including section labels and counters |
| Empty-state copy | `--wz-text-md` (14px); `.wz-empty strong` uses `--wz-text-lg` (16px) |
| Sheet/connector heading | `--wz-text-heading` (17px) |
| Standalone app title | `--wz-text-title` (26px); hidden in hosted windows, not a second page header |
| Reading / display / code | `--wz-font-reading`, `--wz-font-display`, `--wz-font-mono`; do not load app-specific UI webfonts |
| Space | `--wz-space-1/2/3/4/5`: 4/8/12/16/24px; use gap/padding in this scale |
| Gutters | Kit `--wz-gutter`: 12px narrow, 20px medium, 28px wide; do not add a centred app-width cap |
| Radius | `--wz-radius` 14px; `--wz-radius-tile` 12px; `--wz-radius-pill` 20px. Signal overrides these to 2px: never override it locally |
| Target / icons | `--wz-target` 44px minimum interactive area; `--wz-icon-size` 18px icon inside it; row minimum 52px |

Use kit classes first. App CSS may arrange domain-specific content with `--wz-*` roles, percentages, `ch`, flex/grid and container queries; it must not restyle common controls, invent colours, fonts or a private type scale. Physical media/canvas dimensions and intrinsically sized art are not UI type. The 13px label minimum supersedes the old 11px counter/11.5px uppercase exception. Reading text may be larger, through an approved type role; never shrink labels to fit.

### Components to use, not redraw

- **Frame:** `.wz-app`, `.wz-scroll`, `.wz-sec`, `.wz-sec-h`, `.wz-actions`. Keep content and scroll state; no replacement app shell or nested Chats composer.
- **Buttons:** `<button class="wz-button">` for the one primary action. Add `.secondary` for other actions and `.destructive` for destructive confirmation; name the consequence ("Disconnect account", not "OK"). `.wz-icon-button` for labelled icon-only actions. Use native `disabled`; retain focus-visible, keyboard activation and busy text. A navigational/list row uses `.wz-row`, not an accent button. Don't decorate every card with an accent CTA.
- **Rows:** `.wz-list` containing `.wz-row`, `.wz-tile`, `.wz-main` with a title and optional secondary line. Whole row is the target; separate nested actions remain keyboard reachable. No hover-only actions on phone.
- **Cards:** `.wz-card` for grouped information; `.wz-grid` for item sets. Tinted cards may expose the underlying window material; do not put a second page background inside the window. `.wz-prose` caps only reading text, never the app frame.
- **Sheets:** native `<dialog class="wz-sheet">`, labelled with `aria-labelledby`, `.wz-sheet-x`, `.wz-sheet-grip`, and shared `wizard-sheet.js` / `WzSheet.open`. Narrow = bottom sheet; wide = centred card up to 520px. Preserve focus return. ×, Esc, outside tap, Back and grip swipe close it; Back never exits the app. Text-bearing floating panels, menus and toasts are **opaque**, derived from base + ink (`--wz-panel`), not translucent `--wz-overlay` glass. A backdrop may remain translucent. `overlay` is a transport material, not permission to make text panels see-through.
- **Inputs:** labelled `.wz-field` / `.wz-input`; `.wz-field-row` and `.wz-field-go` for one-line non-chat forms. Placeholder is not the accessible label. Keep entered text on recoverable failures; add `aria-invalid` and `aria-describedby` to inline errors. Use inputmode/type appropriate to the data, no tiny controls.
- **Status:** `.wz-pill.ok`, `.warn`, `.off`, `.error`; accompanying text, not colour alone. Success and warning come from each skin's `--wz-success`/`--wz-warning` (light variants in light schemes); danger from `--wz-danger`. Accent means action, **not connected/success**. Loading uses text plus `aria-busy`; meter uses `.wz-meter`.
- **Empty/error:** `.wz-empty` with a short heading, one sentence and at most one useful action. `.wz-status` with `role="alert"` for actionable failures; `.note` / `role="status"` for nonurgent progress. Do not show raw IDs, stack traces, an empty spinner forever, or green success toasts after every action. Diagnostics belong in `.wz-more`.
- **Icons:** inline monochrome SVG using `currentColor`, hidden from assistive tech when decorative. Icon-only buttons need a name. App launch icons use the sigil registry in `ICONS.md`; no emoji/stock-icon replacement of app identities. Product imagery, thumbnails, charts and reader illustrations are content, not a second palette for app chrome.

### Phone, desktop and skins

Layout follows the **app container**, not user agent: <600px one column, 600–959px two columns where appropriate, ≥960px up to three columns or list/detail. Test 390×844 phone and 700/1200px windows; keep safe-area insets, wrapping, 44px targets, keyboard reachability and reduced motion. A narrow desktop window gets the same layout as a phone. Do not remove actions at a breakpoint. No horizontal page overflow. Verify Nebula **and a light skin**; a screenshot alone is not functional proof. Shell Setup/Settings/Home/Chats use the same token roles and component decisions; special shell runtime primitives stay in the component inventory rather than being copied into apps.

### Source, copies and enforcement

Author `style/tokens.json` → run `python3 style/generate_tokens.py`; author common controls in `style/ui.css` and behaviour in `style/sheet.js`. Mirror byte-identical files to `wizard-ux/web/kit/` and WAM's pinned hello template, with provenance. Appearance v1 transports colours only: new size/type roles are CSS defaults, **not a wire-schema change**. Do not edit generated copies independently or substitute a CDN's latest kit.

`python3 style/check_style.py APP --policy style/style-policy.json --base BASE_SHA` is the change-line ratchet: existing raw colours/type declarations and stale kit copies **warn**; added/changed violations and modified stale copies **fail**. `--strict` checks all source in a new app; `--warn --json` produces an audit. Only exact, SHA256-locked source exceptions with an owner/reason in the canonical policy are accepted (skin definitions, brand/media content where justified). A changed exception needs a reviewed policy refresh. No global ignore glob for app CSS. Skin packages and owner tweaks (`skin_layers` in the policy: `web/skins/`, `web/tweaks/`) are skin definitions, so their literal colours, fonts and px type warn and never fail; cyclic tokens, kit drift and symlinks still fail there. Do not execute app code during lint. An unavailable diff base is an error, never silently a pass.

Visual/behaviour review remains required: the lexical gate cannot certify accessible contrast, 44px targets, correct layout, component semantics or feature parity. The app builder applies the same check, ratcheting tracked existing apps against their base and checking newly generated templates strictly. Existing non-Git imports remain warnings until they carry a reviewed baseline; do not call those a strict admission pass.

### Reconciled guidance

| Former overlap or conflict | Resolution |
|---|---|
| OS rules vs shell kit README vs COMPONENTS inventory | This file owns appearance decisions; others link here and document APIs/distribution only |
| Early 640px app frame / per-app width caps vs rule 1 | Window fills; only `.wz-prose` limits text measure |
| 11/11.5px label exceptions vs approved 13px labels | 13px minimum; kit labels/counters updated together |
| Overlay token described as sheet background vs opaque floating text | Overlay transport remains; text panels use opaque `--wz-panel` |
| App-specific UI fonts/accent palettes vs shared Appearance v1 | UI uses type roles/host accent; intentional reader typography/content art is separate and reviewable |
| Status reusing accent in old app copies | Per-skin status roles, including light variants; accent reserved for actions |
| Hosted live kit replacement hiding stale local copies | Check source copies against canonical hashes as well as browser appearance |

See [STYLE-AUDIT.md](STYLE-AUDIT.md) for the source inventory, measured debt and rollout evidence.
