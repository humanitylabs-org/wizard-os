# Wizard Supervisor: UI Contract (prototype)

**Scope banner** (always visible, top): "Prototype · enrolled test services only". 12px, teal `#5EEAD4` at 70% opacity.

**Surface:** transparent background (it inherits Wizard). Cards use `rgba(255,255,255,0.04)` with a 1px `rgba(196,181,253,0.14)` border and 12px radius. Font is `system-ui`. Text: primary `#ECEAF6`, secondary `#A09CB8`. Lavender `#C4B5FD` is for actions and focus. Teal `#5EEAD4` marks verified/healthy. Amber `#FBBF24` means needs approval. Rose `#FB7185` means failed or error.

**Spacing:** 4px base. Page padding 16px, gaps between cards 12px, card padding 14px. Tap targets are at least 44px. Single column, max width 560px.

## Screen (one scroll, three sections, each with a 13px uppercase header)

**1. Now**: one row per enrolled service/job showing name, state chip and "checked 2m ago".
State chips: `Healthy · verified` (teal), `Degraded` (amber), `Failing` (rose), `Not checked yet` (grey), `Check stale` (grey, shown when older than 2× the interval).
Empty state: "No enrolled services. Nothing is being supervised." Grey, never teal. Empty means not watched, so it must never read as healthy.

**2. Recent decisions**: newest first, up to 20 entries, then "Show older". Each row shows the action verb, the target and an outcome chip: `Done · verified`, `Done · unverified`, `Awaiting approval`, `Declined`, `Failed`.
Empty state: "No decisions recorded yet."

**3. Maintenance rules**: each rule shows its rule text and a chip, `Active` (lavender, filled) or `Candidate` (lavender outline, dashed). A candidate rule shows "Not enforced. Learned from feedback, waiting for review."
Empty state: "No rules defined."

## Detail drawer (tap any row)

A bottom sheet covering 85% of the height, with a drag handle and a × button at top right.
- **Evidence**: each item shows its source, timestamp and raw excerpt (monospace, 12px), with a `Verified` or `Unverified` label. Unverified evidence never shows teal.
- **Approval**: shown only when the state is `Awaiting approval`. It names the exact scope: "Approve: restart `svc-x` once. Nothing else." Two buttons: `Approve this action` (lavender fill) and `Decline`. Once tapped, the button shows "Sending…" and stays disabled until the server confirms. There is no bulk approve.
- **Feedback**: a text field plus `Record feedback`. The confirmation reads "Saved as candidate rule, not active yet." Only an explicit `Promote to active` (with a confirmation prompt) changes enforcement.

## Errors

- **Fetch failure**: the affected section shows "Couldn't load — last data from 14:02" with a `Retry` button and keeps the last data dimmed. It never blanks the section and never presents stale data as current.
- **Action failure**: an inline rose line inside the drawer: "Approval not sent: <reason>. Nothing changed." The drawer stays open.
- **Data loading**: grey skeleton placeholders only. No mock data, ever.

## Back (standing rule)

- Back closes the drawer first, and returns any expanded "older" list to the root.
- At the root, Back stays on the screen. Inside Wizard it returns control to the Wizard shell. In a standalone tab it shows "Press back again to exit" for 2s.
- **Required test:** open the drawer, press Back, assert the drawer is closed and the app is still open. Press Back again and assert the screen is still mounted.

**Accessibility:** contrast of at least 4.5:1, `aria-live="polite"` on state changes, and the drawer is focus-trapped and returns focus to its row when it closes.

Design source: first-party Claude Opus, verified modelUsage claude-opus-5-5. Parent implementation retains single Back at root and reports candidate feedback accurately.
