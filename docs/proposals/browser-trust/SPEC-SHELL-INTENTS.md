# Shell intents: owner confirmation and narrow sign-in navigation (decided in draft)

**Draft for Miguel's review · 2 November 2026 · Oscar for Miguel.** Stacked on card 1 (#391). Card 2 (#385) needs it
for the ChatGPT and Claude connection pages. It records, as decided in this draft, the trusted-shell confirmation/
intent flow from [ADAPTER-SKETCH.md §4](ADAPTER-SKETCH.md#4-typed-app-data-operations) and the census label **N**
(narrow navigation/auth intent) from [APP-CENSUS.md](APP-CENSUS.md). Default-off behind `WIZARD_BROWSER_BOUNDARY`;
nothing is merged, released or enabled. James signs off the new operation ids (Q3).

## 1. Owner confirmation intent

- **Which operations.** A registry descriptor carries `consent: owner` (WAM `OPERATIONS`, Service `OPERATIONS`, shell
  `CONSENT_OPERATIONS`). Rule from §4: a new external send, an account connection or a global change. Such an
  operation is **never** a plain `data.call`: the shell refuses it (`not_allowed`) and the Service refuses it
  (`confirmation_required`), whatever the arguments. There is no `confirmed` argument; an app's `confirmed: true` is
  `bad_request`.
- **Queue, don't open.** The app calls `WizardApp.intent.confirm({operation, args, operationKey})`. The shell sends
  `POST /wizard/v1/browser-adapters/intents {kind: confirm, ...}` (shell token only). The Service admits the operation
  against WAM state, validates the exact arguments, renders the summary itself (title, detail, action label, danger)
  and stores an intent bound to: binding handle, document generation, installation, source, installed commit,
  permission revision, operation, normalized arguments and `operationKey`. Expiry 2 min. One open intent per binding.
- **The owner opens review in shell UI.** The shell shows a Review chip on that app's own window bar (shell DOM in the
  main document; the frame cannot draw there). Only a trusted click on the chip opens the dialog. No dialog opens by
  itself.
- **Activation.** The dialog is shell DOM (`<dialog>` in the main document). Its action button is inert for **500 ms**
  after it is shown (a progress bar paints at once: immediate visual feedback, delayed consent). Then it needs a fresh
  trusted activation inside the dialog: `pointerdown` **and** `pointerup` on the button after the delay, or a keyboard/
  assistive activation (`click` with `detail === 0`, focus inside the dialog). Synthetic events (`isTrusted` false),
  presses inside the delay, and anything the app does are ignored. Cancel and Esc cancel the intent.
- **Consume once.** The shell sends `POST .../intents/confirm {handle, generation, intent}` (no arguments: they are
  fixed at queue time). The Service deletes the intent before any effect, rechecks binding, generation and the
  installation identity (an update, source switch or grant change in between → `revoked`), runs the operation once
  with the stored arguments and `operationKey` (durable receipt before the effect), and adds `confirmed: true`
  upstream itself. A second confirm is `not_found`. A frame reload, detach or lost authority cancels the review.
- **Rate.** Review requests: at most **3 per minute per installation** (Service, `429 rate_limited` + `retryAfterMs`)
  and per app id in the shell, confirm and navigate together.

## 2. Narrow sign-in navigation intent (N)

- **Declared and reviewed.** `browser_contract.navigation`: up to four entries `{id, url, query}`. `url` is one exact
  `https://host/path` on the default port: no wildcard, IP literal, userinfo, fragment or query in it. `query` lists
  allowed parameter *names* only; credential-shaped names (`token`, `secret`, `password`, `session`, `api_key`,
  `cookie`, `assertion`, `credential`, `auth_code`) are refused. A navigation entry needs an operation with
  `signin: true`. Navigation is part of the contract digest, so a change is a permission delta.
- **The URL never reaches the frame.** A `signin` operation's provider URL is matched by the Service to an entry
  (exact origin and path, only listed names, no duplicates) and kept per binding; the frame gets the entry id only.
  Unmatched URLs are dropped.
- **Opened by the shell only.** The app calls `WizardApp.intent.open({target, ref})`, where `ref` names the operation
  (`ai:<job>`) or login (`cc:<login>`) that produced it, never a URL. The same queue, chip, dialog, 500 ms and trusted
  activation apply; the dialog shows the host and path. On confirm the Service re-checks the current contract and
  returns the URL to the shell, which opens it in a new tab inside that activation (`opener` cleared, no Referer). If
  the browser blocks the tab, the dialog shows the link for the owner's own tap. No arbitrary URLs, no tokens in URLs,
  no `allow-popups`, no top navigation.

## 3. Registry delta (James signs off)

| id | kind | consent | upstream (installation's own) |
|---|---|---|---|
| `ai_accounts.inventory` | read | — | `GET /api/accounts` |
| `ai_accounts.change` | write | owner | `POST /api/operations {action: add/reconnect/remove/prefer, target}` |
| `ai_accounts.progress` | read, signin | — | `GET /api/operations/<id>` |
| `ai_accounts.step` | write | — | `POST /api/operations {action: submit/cancel, operation[, code]}` |
| `claude_code.status` | read | — | `GET /claude-code/api/accounts` |
| `claude_code.connect` | write, signin | owner | `POST /claude-code/api/claude/connect` |
| `claude_code.code` / `.cancel` / `.test` | write | — | `POST /claude-code/api/claude/{code,cancel,test}` |
| `claude_code.logout` | write | owner | `POST /claude-code/api/claude/logout` |

All writes carry an `operationKey` with durable receipts; a pasted code is kept only as a digest. Results are fixed
DTOs (app text bounded, links replaced). Each call carries the installation's listener credential (card 3).

## 4. Listener gate for the two apps

Their MCP fronts take `WIZARD_BROWSER_BOUNDARY` / `WIZARD_APP_CREDENTIAL` (written by WAM) and guard `/api/accounts/`,
`/api/operations/` (+ `/claude-code/api/` for Claude): frames, pages, Tailscale Serve owner logins, simple posts and
preflights are refused before the engine. `/api/connection` (Agent Service usage reader) and `/api/infer` (connection
router) keep their own grants. A box page password is added only to admitted adapter calls. `Sec-Fetch-Mode` alone is
not a browser signal (Node's fetch sends it).

## 5. Morning Report's Overnight reader

Under the gate the generator's box-local `GET /notifications/api/daily` is refused (no credential). The same roll-up is
the typed read-only MCP tool `notifications_overnight` (hours 1..72): box-only, refuses web pages. Agent scripts call
it instead of holding an app credential.

## 6. Open

- Owning repos and what ships: release 0.3.102 pins `oscarhenrycollins/chatgpt-connection@37c3bc89` (0.2.12) and
  `claude-connection@2e58656b` (0.2.14); the page and engine are `humanitylabs-org/wizard-app-store`
  `images/wizard-{chatgpt,claude}`. These drafts are on main (0.2.16 / 0.2.20); the org copies of the two repos are not
  in a release.
- The shell model picker reads `/wizard-claude/api/accounts` from the shell document (`chat-models.js`); under the gate
  that 403s and the picker loses Claude limit notes until it reads through a shell-held binding.
- Morning Report's own Overnight picker (`/notifications/api/routes` from its view) needs a cross-app typed operation.
- Native (card 4), nginx/Forum/Runtipi lifecycle and rollback (card 6), phone-size dialog QA.
