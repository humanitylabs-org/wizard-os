# App actions in chat (`wizard.app-actions/1`)

**Status: proposed, built behind the owner switch `wizard/action-cards` (off by default; wizard-ux#1463).** The shell
card is wizard-ux `web/core/action-cards.js`. Apps adopt it on their own (Messenger drafts, Mail replies, Calendar
events and Money reconciliation steps first); until an app does, nothing changes for it.

Chat is the main way of working; apps hold the real state and are where the owner takes over. When an agent prepares
something in an app (a draft, a reply, an event, a step), the app keeps it **pending** and the chat shows a small card
with the app's own preview and three buttons: **Approve**, **Edit** and **Open in app** (plus a quiet **Reject**).
Approve carries the action out without leaving the chat; Open in app opens that exact item inside the app.

One contract, no per-app chat UI: every app's card looks the same.

## 1. Proposing: the app keeps it, the agent names it

An app's agent tool (MCP), e.g. `messenger_propose_reply`, creates the item in the app, **never acts on it**, and
returns its id plus one marker line the agent puts in its reply, on its own line:

```
[WIZARD_ACTION_V1]{"app":"<installed app id>","id":"<item id>"}[/WIZARD_ACTION_V1]
```

- `app`: the installed app id (`[a-z0-9][a-z0-9-]{0,62}`). `id`: the app's item id (`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`,
  no `/`). At most 4 markers count per reply; anything else in the marker is ignored.
- The marker carries **no preview text and no route**. Everything the card shows and everything Approve does comes
  from the app itself, read by the owner's browser at a fixed path under the installed app's own url, so words the
  agent writes (or an injected message makes it write) can never change what is approved or where it is sent.
- Wizard always hides the marker from the message text, copy, the Chats list preview and a streaming answer, like
  every chat marker (wizard-ux docs/CHAT-MARKERS.md). With the switch off no card is drawn and nothing is read.
- The skill that teaches the tool says: put the marker line in your reply as is; don't also describe the item at
  length (the card shows it); never claim it was sent before the card says Approved.

## 2. Reading: `GET <app url>api/actions/<id>`

`<app url>` is the app's page url from the box's app list (`/wizard/v1/apps`, same origin as the shell). The shell
reads with the owner's browser credentials, exactly as the app's own page would, `Accept: application/json`, when a
card is shown (at most every 15 s while it stays on screen, and again when the page shows): a message is history,
so the card always shows the item's **current** state.

`200`:

```json
{
  "schema": "wizard.app-actions/1",
  "id": "draft-42",
  "kind": "Draft reply",
  "title": "Reply to Sam",
  "body": "In your chat with Sam",
  "fields": [
    { "id": "to", "label": "To", "value": "Sam" },
    { "id": "text", "label": "Message", "value": "Sounds good, see you at 7!", "editable": true, "multiline": true }
  ],
  "state": "pending",
  "open": "?thread=sam#m-981",
  "approve_label": "Send",
  "message": ""
}
```

- `id` must equal the requested id; `schema`, when present, must be `wizard.app-actions/1` (otherwise no card).
- `title` (≤140 chars) and optional `kind` (≤40, shown after the app's name), `body` (≤600, plain text).
- `fields`: up to 8 `{id, label, value}` (plain text, value ≤4000). `editable: true` fields become text boxes under
  **Edit**; `multiline` asks for a multi-line box. Only editable fields are ever sent back.
- `state`: `pending` (buttons shown), `approved`, `rejected`, `failed`, `expired` (shown as a status line; only
  Open in app stays). `message` (≤240) is shown next to a done state, e.g. "Sent to Sam".
- `open`: where Open in app goes, relative to the app's url (`?thread=sam`, `threads/9#m2`). The shell opens it only
  when it stays inside that app's own path on the same origin; otherwise it opens the app at its start.
- `approve_label`: the Approve button's word (≤30), e.g. "Send", "Add to calendar". Default "Approve".
- `404`: the app no longer has the item; the card says so. `401`/`403`: the card asks the owner to open the app once.
  Anything else: "Can't reach <app> right now", with Open in app.

## 3. Deciding: `POST <app url>api/actions/<id>`

Headers `Content-Type: application/json`, `X-Wizard-Action: 1`, the box's own `Origin`; body

```json
{ "decision": "approve", "fields": { "text": "Sounds good, see you at 8!" } }
```

or `{ "decision": "reject" }`. `fields` appears only after Edit and only holds editable fields.

- **Owner only.** The app accepts a decision only from the owner, with the same owner check as its own pages
  (spec/OWNER_PROOF.md where the app has the key, otherwise its Tailscale owner login), **plus** `X-Wizard-Action: 1`
  and a same-origin `Origin` (a cross-site form can't send either). Never a bearer token or an agent grant: an agent
  can propose, only the owner approves.
- Approve does the action (sends the draft, books the event) with the edited fields, once. The answer is the item's
  new document (`200`, state `approved`, or `failed` with `message`). A second decision on an item that is no longer
  pending answers `409` with the current document; the card shows it.
- A refusal answers `4xx` with `{ "error": "<code>", "message": "<plain words>" }`; the item stays pending and the
  card shows the message.
- The app should also show the pending item on its own screens (with its own Approve), so taking over in the app
  and approving in chat are the same item; whichever happens first wins.

## 4. What the shell guarantees

- Calls go only to `<installed app url>api/actions/<id>` on the shell's own origin, for an app in the box's list;
  an unknown app or one on another origin gets no call ("<app> isn't installed on this Wizard").
- Nothing is approved without the owner's tap; nothing is sent while the switch is off.
- The app's strings are shown as plain text (escaped), never as markup.
