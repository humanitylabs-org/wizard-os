# Browser trust, card 2 (first slice): the real Notifications app behind the opaque frame

**Spec for review · draft · nothing adopted until reviewed.** Card: [#385](https://github.com/humanitylabs-org/wizard-os/issues/385). Stacked on the card-1 spec ([#391](https://github.com/humanitylabs-org/wizard-os/pull/391), `SPEC-CARD1.md`) and its disposition (Q1–Q3 confirmed; provider changes = box owner approves; Profiles data owned by `humanitylabs-org/profiles`; uninstall never auto-deletes). Oscar wrote it for Miguel. `WIZARD_BROWSER_BOUNDARY` stays default-off. This slice covers **Notifications only**; the Router view and the other census rows are later slices of #385.

Implementation drafts (all draft, all default-off, each stacked on its card-1 draft at the exact head):

| Repo | Branch | Stacked on |
|---|---|---|
| `oscarhenrycollins/notifications` | `feature/browser-trust-default-notifications` | main `e6df99a` |
| App Manager | `feature/browser-trust-default-notifications` | WAM #405 `0b92cbf3` |
| Agent Service | `feature/browser-trust-default-notifications` | Service #306 `74f6e017` |
| Wizard UX | `feature/browser-trust-default-notifications` | UX #831 `032b7e09` |

## 1. What the real app needed (census row, read from both screens)

Notifications ships two screens from one front: the original inbox (inline in `mcp/tools.py`, all skins) and the minimal screen (`web/minimal/*`, Miguel's skins via `layout.js`). Read from main `e6df99a`; the default release pin is still `cdce9f18` (see §6).

| Need (census) | Before (same-origin frame) | Under the opaque frame (this slice) |
|---|---|---|
| D: list with views and counts | `fetch('api/items?view=…')` | `notifications.inbox` typed read |
| D: read / unread, flag, archive / restore, mark all read | `fetch('api/mark', POST)` | `notifications.mark` typed compare-and-set write |
| U: count / badge | `parent.postMessage(count, location.origin)` | the shell re-reads its own count after each proven write; the frame posts nothing |
| N: Reply (unsent draft) | `WizardApp.nav.openContextDraft` (same-document service) | same API, carried as `nav.contextDraft` over the boundary port |
| B/A: Back, appearance | `__wizardCloseOverlay`, `WizardApp.back`, Appearance v1 | `WizardApp.back.register` on both screens + boundary Back; Appearance v1 over the port (card 1) |
| shell detection | `parent.document…dataset.shell` (SecurityError in an opaque frame) | skipped when opaque; pointer/width fallback (already the code's fallback) |
| M: thumbnails | `<img src="media/…">` | **unchanged, OPEN** on card 3 (#386): a plain image GET from the opaque frame to `/notifications/media/*` |

## 2. Registry delta (platform permission increase: James signs off, per Q3)

Two new ids. `notifications.list` / `notifications.mark_read` (card 1) are unchanged, so the card-1 fixture keeps working.

| Id | Class | Scope | Upstream (fixed) | Arguments (exact keys) | Result (exact keys) |
|---|---|---|---|---|---|
| `notifications.inbox` | read | self, current `notifications` slot provider | `GET /notifications/api/items?view=V&limit=N` | `{view: inbox\|flagged\|archive\|all, limit: 1..500}` | `{view, counts:{unread,needs,flagged}, items:[{id,title≤300,message≤8000,time,priority 1..5,link (https only, else ""),source: agent\|cron,read,flag,archived,revision}]}` |
| `notifications.mark` | write | same | `POST /notifications/api/mark {ids, read?, flag?, archived?, expect:{id: revision}}` | `{items:[{id, expectedRevision}] 1..500 unique, marks:{read?,flag?,archived?} ≥1 boolean}` + top-level `operationKey` | `{items:[{id, revision}], marks, operationKey}` |
| `data.status` | status | same as target | none | `{operation: notifications.mark_read\|notifications.mark, operationKey}` | as card 1 |

**Compare-and-set is upstream, not just a pre-read.** Card 1 noted that any non-monotonic write needs upstream CAS. Unread, unflag and restore are non-monotonic, so the Notifications backend now:

- returns `revision` on every item: `'r-' + sha256(JSON ["notification-mark-v1", id, read, flag, archived])[:16]`, byte-identical to the Service's digest (a test computes both);
- accepts optional `expect` on `/api/mark`: under the store lock, every id must still have its expected revision or the call returns **409 and writes nothing**. Without `expect` the API is unchanged (the agent's MCP tools and the shell's own bell keep working).

The Service sends `expect` on every `notifications.mark`. If the installed backend does not report the same revision (an older build), the write is refused with `unsupported_capability` before any receipt or effect. The rest of the write semantics are card 1's: durable `pending` receipt before the effect, recheck before the effect and before delivery, `outcome_unknown` on a lost reply, reconcile by key and readback, `conflict` on key reuse. A retry whose expected revisions are gone succeeds only if the readback shows the receipt's recorded target marks; otherwise `conflict`.

**Receipt size (measured, open to review).** One 500-item mark-all-read receipt is ~23 KB, so the 1 MiB store holds ~44 such receipts within 7 days before `quota_exceeded`. Results are kept compact (`{id, revision}` only) for that reason.

## 3. Shell services (UX, default-off)

- **Reply draft (`nav.contextDraft`).** Same validation and Chats owner as the same-origin `openContextDraft` (one `contextDraft` function). An opaque frame cannot prove a user gesture, so the shell adds: the registered frame must hold focus (`document.activeElement === frame`) in a visible document; exact keys `{id,title,message}`; at most one per 1.5 s and 20 per 10 minutes per app; only `{kind, sent}` crosses back. It opens an unsent draft and never sends. The frame watchers pass an opaque frame only `openContextDraft` and `isVisible` from the same-origin options (never `openThread`, Back callbacks or a document connection).
- **Badge in one place.** A frame's `wizard:notifications:count` message has origin `null` and is ignored. After a write the shell proved through `data.call`, it dispatches `wizard:browser-data-written` (registered app id only) and `notif-bell.js` re-reads `/notifications/api/count` itself. The bell's existing one-or-the-other rule (desk mark while the window is open, Chats bell otherwise) is unchanged.
- No generic owner relay, no shell token in a frame, no `Origin: null` allowance.

## 4. App Manager

`OPERATIONS` gains the two ids. The app's own `wizard.md` declares `browser_contract: {version: 1, isolation: opaque, operations: [notifications.inbox, notifications.mark]}`. Nothing is granted until the owner grants it (`wam browser-grants grant notifications --operation …`); lookalike ids stay `invalid_contract`.

**Deploy order.** A WAM without these ids marks the new manifest `invalid_contract` and admits nothing for Notifications. That only matters with the boundary on (default off): WAM first, then the app build that declares the contract.

## 5. Storage

No change to card 1's storage table. Notifications still keeps no browser state; read/flag/archive marks stay canonical in its backend (`inbox.json`), so there is no legacy key to migrate.

## 6. Findings outside this slice (reported, not changed)

- **Default pin drift.** Releases pin Notifications `cdce9f18` (index `2.29.0-wizard10`); main is `e6df99a` (`wizard15`, adds inbox sources/app marks and the mark-prune fix). This slice is built on main. A boundary-capable release needs a new pin anyway.
- **Landscapes Light shows the original screen, not the minimal one.** `layout.js` and the minimal screen's skin set list `obsidian`, `obsidian-light` and `landscapes`, but not `landscapes-light`. This was true before this slice.
- **The same notifications counted twice on the desk mark.** With the "Notifications in Chats" tweak on, the desktop desk mark showed `5` (Chats Ready: 2 chats + the 3 notifications, `desktop.js` adds `WosBell.readyCount()`) and `2` (Notifications unread: `notif-bell.js` `paint()` always calls `setCount('notifications', …)`). Miguel's rule is one place per app. Both code paths predate this slice and do not depend on the boundary; this slice changes only what triggers the bell's re-read. Needs its own fix against the rule.
- **Browser QA artifact.** Playwright request interception (`page.route`) makes Chromium skip CORS preflights. The card-1 harness and this one use `page.route` for onboarding, so a direct JSON write from the frame appears to succeed there. This slice proves the preflight refusal in a separate context without interception.

## 7. What this slice proves and what it does not

**Proven (local runs, exact commands and heads in the PR bodies and the #385 evidence comment):** the real Notifications UI (both screens) runs in the opaque frame on typed operations only: list and views, open-marks-read, read/unread, flag, archive/restore, mark all read, conflict on a stale view, unsent reply draft, the shell badge re-read, thumbnails, Back inside the app and Back at the list staying in Wizard, live skin change into the minimal screen. Admission comes from real WAM state built from the app's own `wizard.md`; revoke and uninstall are refused at the server. The unmigrated app in the same frame shows no rows and "Failed to fetch".

**Not proven / OPEN:**

- Thumbnails depend on the ambient `/notifications/media/*` route: no typed media adapter yet (**card 3, #386**).
- `/notifications/api/*` still answers by network identity; a plain GET from the frame still reaches the app (the body stays hidden) and only the browser's preflight stops JSON writes (**card 3, #386**).
- Phone shell run (minimal swipe strip in an opaque frame), native Android/Mac (**card 4, #387**).
- nginx itself (Node stand-in), Forum `/srv/work` (not reachable from this runtime), real Runtipi install/update/uninstall, Store update prompts, packaged rollback (**card 6**).
- James's sign-off on the two new registry ids.
