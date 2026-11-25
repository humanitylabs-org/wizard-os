# Capture inboxes

**Status: proposed, built behind the owner switch `wizard/capture-inbox` (off by default; wizard-os#696).** Inboxes
built: the Files drop folder and the Photos camera roll. Implemented by the Agent Service (`server/capture-inbox.mjs`,
`docs/capture-inbox.md`) and the Photos app (`mcp/tools.py`, capture inbox section).

The owner drops things wherever is easiest (Files uploads, the phone's share menu, a laptop folder that syncs, the
camera roll) and his own agent files each new item by rules he wrote in plain words. One contract covers every inbox:
something arrives, the box hands a batch to the owner's main agent, the agent files each item with logged tools, and
one line in the agent inbox says what happened. Every step can be undone. Because the main agent is private by default
(wizard-os#676), nothing leaves the box except to the owner's private provider.

## Inboxes

| Inbox | Source | How the box learns of new items |
|---|---|---|
| Files drop folder | `files` | The Agent Service watches `Inbox/` of the owner's Files root (box side, no app event). |
| Photos camera roll | `photos` | The Photos app sends `items_arrived` to the Service's capture route (below). |
| Chat dumps | `chat` | Already handled on receipt (agent inbox #551); attachments of a dump with no words land in `Inbox/<date>/`. |
| Messenger, Mail | `messenger`, `mail` | Later, through the same capture route; urgent items go through the alert rules (#552). |

The Files drop folder is watched by the Agent Service, not the Files app: Files mounts the owner's files read-only by
design, and the Service already owns the writes into `Inbox/<date>/`. No app gets new write powers.

## The event (app inboxes)

An inbox app hands a batch to the box with its own app token (`<wizard-os home>/app-tokens/<app id>`, handed to the
app by the App Manager as `<NAME>_AGENT_INBOX_TOKEN`, as for the agent inbox's app doors). It is a capture route of its
own, not the general app wake ([APP_WAKE.md](APP_WAKE.md)), because a capture batch needs the inbox's record, rules and
undo, and the capture switch alone decides it.

- **Probe:** `GET /wizard/v1/capture/events`. `404` = the box offers no capture inbox (switch off, older Service): the
  app does nothing new. `200 {"on": true, "contract": "wizard.capture-inbox/1", "app", "batches"}` lists the app's own
  batches newest first (`batch`, `app_batch`, `state`, `undone_at`). Apps read it every half minute or so.
- **Event:**

  ```json
  {"event": "items_arrived", "data": {"source": "photos", "batch": "<app's own batch id>", "count": 3, "at": "2026-11-25T08:00:00Z"}}
  ```

  `202 {"accepted": true, "created": true, "batch", "app_batch", "record_id"}` made the batch, its record and the
  worker turn; the same app batch again answers `200` with the same batch (never a second worker). `400` for another
  app's `source` or a bad batch id or count (1 to 500), `403 app_token_required` without an app's own token.

The event carries no content: the agent reads the items through the app's own tools, which list them by the app's
batch id (Photos: `photos_capture_batch`, `photos_capture_file`). Each app does its own baseline and quiet period and
sends one event per batch.

## A batch

- **Quiet period:** items are batched once nothing new arrived and nothing grew for a few minutes (Files: 2 minutes,
  `WIZARD_CAPTURE_QUIET_MS`), so a set of photos or a synced folder is one batch. At most 50 items per batch.
- **Only new items:** turning the switch on takes a baseline; what is already there is never touched. Chat
  attachments belong to their chat and are never batched.
- **One record:** each batch is one agent-inbox record (#549): `source` `capture:<source>`, `privacy_class`
  `private`, `capture: {batch, source, count}`, a hidden worker thread (`worker: true`). It is `running` while the
  agent works, `new` with kind `result` and the one-line outcome as its title when done (the sweep's Done line), or
  `needs_you` with one question.
- **The worker turn** lists every item where the agent sees it, plus the owner's rules, and tells the agent to file
  each item only with the logged tool.

## Rules

One plain Markdown file in the owner's Files, `Capture rules.md`, written with a default set the first time a batch
needs it. The owner reads and changes it like any note (or asks the agent to). The default set:

- a voice note in a batch says what the batch is: follow it first, then file the voice note in `Voice notes`;
- receipts and invoices: `Documents/Receipts/<year>`, plus the expense in Money if installed, keeping the original;
- articles and other things to read: `Reading/Articles`;
- photos of book pages: the highlighted passages into `Reading/<book title>.md`, the photos in `Reading/<book title>`;
- screenshots: `Pictures/Screenshots/<year>`; personal photos and videos: `Pictures/<year>/<month>`;
- other documents: `Documents/<what it is>`;
- not sure: leave it in Inbox and ask one question; never delete anything.

With no rule for an item the agent makes its best guess only for a low-risk move and asks about the rest.

## Filing: move, copy or tag

- Files inbox: **move** within the owner's Files (out of `Inbox/`), never over another file (`name (2).ext`), never
  into Inbox or outside the root. Text taken out of an item (highlights) is **appended** to a note in Files.
- Another app (Money, a later Reference app): the agent **adds a copy** with that app's tools; the original stays
  where it was filed.
- Photos inbox: personal photos **stay in Photos** and get tags and albums; document photos get a filed copy where they
  belong (`wizard_capture` action `copy`, from the original's place under `Photos/Library`) and the original is marked
  processed in Photos (tag `Wizard/Processed`). Photos counts only photos taken at most 3 days before they arrived, so
  a Takeout import or a phone's first backup of years of photos is never swept up.

## Log and undo

Every item gets one log line in its batch: what it was judged to be, the rule used, where it went (or why it stayed).
"Undo that" puts a whole batch back, newest step first: every moved item to where it arrived, every note without the
text the batch added. An item is moved back only when its first place is free and it is still where it was filed;
anything else is reported, never overwritten. Put-back items are never batched again. In the Agent Service: the main
agent's `wizard_capture` tool (actions `list`, `listen`, `file`, `copy`, `keep`, `note`, `done`, `undo`, `rules`) and
the owner's `GET /wizard/v1/capture`, `POST /wizard/v1/capture/<batch>/undo`. A copy is taken away while it is
unchanged. For an app batch the app keeps its own log (Photos: tags, albums, processed marks) and takes exactly that
away when its probe shows the batch undone.

## Questions

An item the agent is unsure about stays where it is, and the batch's record waits as `needs_you` with one question,
a recommendation and one-tap answers in the sweep (#550), never as a new thread.

## Switch

`wizard/capture-inbox` in the shell's tweak catalog, read by the Agent Service from the Look file;
`WIZARD_CAPTURE_INBOX=1|0` forces it. Apps follow it through the probe. Off: nothing is watched, moved or written, the
agent has no `wizard_capture` tool and no app capture tools, and the routes answer 404.
