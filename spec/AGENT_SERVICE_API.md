# Agent Service API (`/wizard/...`), v1

**Owner: Archimedes** (DECISIONS #42; Jan reviews after the fact). **Status: v1, documented from shipped behaviour.**

This is the contract between Wizard front ends (Wizard UX on the web and in the Android app) and `wizard-agent-service`. It describes what the service does today. Where today's behaviour looks wrong it is flagged under [Discrepancies](#discrepancies), not redesigned here. A change to anything below is a PR that edits this file first; a breaking change bumps `api` in the bootstrap.

Evidence for every statement here:

| Repo | Ref | Commit |
|---|---|---|
| `humanitylabs-org/wizard-agent-service` | `main` (release 0.2.0, PR #9) | `f772b830ec4f3ba1faff885f8a66914b6010f062` |
| `humanitylabs-org/wizard-ux` | `daily` | `88661246ebf29bd862264490199536a2cfbc8ba7` |
| `humanitylabs-org/wizard-os` | `main` | `031cff5e886c54f1121d426246e611bb907fd141` |
| `humanitylabs-org/wizard-agent-service` | PR #7 `feature/apps-views-routes` (draft) | `2d22e8770a5fb5e0879a2cecf02dffa1524a547a` (proposed only) |

Handlers live in `server/service.mjs` (`createWizardServer`), the Hermes allowlist in `isAllowedProxyRequest`, settings and bootstrap in `server/wizard-os-settings.mjs`, the MCP gateway in `server/agent-bridge.mjs`. Two tools keep this file honest (see [Verifying the contract](#verifying-the-contract)): `tools/check_api_contract.py` maps every request in the Wizard UX source onto the route table below, and `tools/api_contract_probe.mjs` exercises every served route against an isolated service.

## What "v1" covers

- **Versioned by this document (`stable`):** the routes the Agent Service implements itself. Paths, methods, request bodies, response fields and error codes are v1. Adding a field is allowed; removing or renaming one is breaking.
- **Most v1 routes have no `/v1` in the path.** Only `bootstrap`, `apps`, `route`, `uploads`, `shares` and `agent-context` do. The rest (`/wizard/files`, `/wizard/thread-seen`, `/wizard/attention`, ...) are v1 at their current paths and are not being moved.
- **Passthrough (`/wizard/hermes/...`):** the Hermes API (`/api/sessions...`, `/v1/runs...`) behind a fixed allowlist. The allowlist (paths, methods, query keys, limits) and the Wizard projections listed below are v1. The rest of each body is whatever Hermes returns and moves with Hermes, so front ends read it defensively (`run.run_id || run.id`, `p.data || p.messages || p.items`), as the UX already does. The agent adapter call set (spec/AGENT_BRIDGE.md, DECISIONS #48) is what a second harness must serve underneath.
- **Discovery:** `GET /wizard/v1/bootstrap` returns `bootstrap: 1`, `api: "wizard-agent-service/1"`, `capabilities` and `endpoints`. Front ends take the apps, sessions, runs, transcribe, route, upload, uploads and shares addresses from `endpoints` and switch features off from `capabilities`. A shell that cannot reach bootstrap falls back to the pre-bootstrap aliases (class `compat`).

## Phone Setup (companion implementation: wizard-agent-service #24)

The five `/wizard/v1/setup*` routes below are the [Phone Setup](PHONE_SETUP.md) contract.
`GET /wizard/v1/setup` returns `first_run`; `POST /wizard/v1/setup/seen` consumes that first-run flag.
An explicitly configured existing-Hermes installation (`WIZARD_SETUP_MODE=alongside`) also returns
`launch_mode: "alongside"`. Clients keep first launch quiet (no automatic Setup or gesture tour),
without marking Setup seen or the tour completed. Setup and its tour remain available explicitly.
Absent or unknown launch modes retain the VM onboarding flow. This field grants no access.
For already configured host-managed private access, the phone item may return `state: "done"`
and `phone_ready: true` before the first recorded phone visit: the same validated host address the phone page offers is ready to open,
not proof that a phone has connected. Clients say "Ready to open on your phone", not "connected".
A present-but-unreachable helper never turns a stale host address into readiness. This read does
not persist `phone_seen_at` or alter enrollment, authorization, or the host's Tailscale configuration.
`phone_ready` is only a checklist-copy hint for ready-before-first-visit, not an availability capability:
after an observed phone visit it is omitted, preserving the existing connected checklist copy.
`GET /wizard/v1/setup/phone` returns the current Tailscale/checklist state; `POST .../start` begins
interactive sign-in and `POST .../reset` disconnects the box. Only the owner may use these routes;
agent credentials never authorize Setup. Writes require a same-origin browser request. The box-local
owner-proof ingress and the dedicated enrolled-owner Serve ingress are separate trust boundaries.
Treat the routes as unavailable on an older service (404); deploy the companion implementation before
enabling them. Detailed schemas and state transitions live in the service `docs/phone-setup.md`.
The non-summary calls use a shared dynamic request helper in wizard-ux; the literal-source scanner
currently sees only the summary URL, so those rows are not marked `ux` by that scanner.

## Route table

Machine-readable: both checking tools parse this block. Columns: methods, path (`{x}` = one path segment), class, whether Wizard UX (web or Android) calls it (`ux`) or not (`-`), allowed query keys (`-` = none).

Classes: `stable` = Agent Service route, v1. `passthrough` = Hermes route behind the allowlist. `compat` = alias kept for older shells and native builds. `box` = agent and operations surface, not for front ends. `page` = HTML entry point. `proposed` = in an open PR, **not served on main**, not part of v1. `gap` = the UX calls it and main does not serve it (see Discrepancies).

```routes
# methods       path                                              class        ux  query
GET             /wizard/v1/bootstrap                              stable       ux  -
GET             /wizard/v1/setup                                  stable       ux  -
POST            /wizard/v1/setup/seen                             stable       -   -
GET             /wizard/v1/setup/phone                            stable       -   -
POST            /wizard/v1/setup/phone/start                       stable       -   -
POST            /wizard/v1/setup/phone/reset                       stable       -   -
GET             /wizard/v1/apps                                   stable       ux  -
GET,HEAD        /wizard/v1/chats-views/{id}/{hash}.js               stable       -   -
POST            /wizard/v1/route                                  stable       ux  -
GET,POST        /wizard/v1/schedules                              proposed     -   -
PATCH,DELETE    /wizard/v1/schedules/{id}                         proposed     -   -
POST            /wizard/v1/schedules/{id}/run                     proposed     -   -
POST            /wizard/v1/schedules/import-hermes                proposed     -   -
GET             /wizard/voice/status                              stable       ux  -
POST            /wizard/voice/transcribe                          stable       ux  -
POST            /wizard/voice/recovery-receipt                    stable       -   -
GET             /wizard/ai-usage                                  stable       ux  -
GET,HEAD        /wizard/attachments/{id}                          stable       ux  -
GET             /wizard/files                                     stable       ux  -
GET             /wizard/files/{id}/content                        stable       ux  -
HEAD            /wizard/files/{id}/content                        stable       -   -
POST            /wizard/files/upload                              stable       ux  -
POST            /wizard/files/invite                              stable       -   -
POST            /wizard/v1/uploads                                stable       -   -
GET,PATCH       /wizard/v1/uploads/{id}                           stable       -   -
POST            /wizard/v1/uploads/{id}/complete                  stable       -   -
POST            /wizard/v1/shares                                 stable       -   -
GET             /wizard/v1/shares/{id}                            stable       -   -
GET             /wizard/v1/user-files                             stable       -   folder
GET,HEAD        /wizard/v1/user-files/content                     stable       -   path,download
GET             /wizard/attention                                 stable       ux  -
POST            /wizard/attention/{id}/retry                      stable       ux  -
POST            /wizard/attention/{id}/dismiss                    stable       ux  -
POST            /wizard/session-failure/{id}/dismiss              stable       ux  -
GET,PUT         /wizard/thread-seen                               stable       ux  -
GET,PUT         /wizard/thread-dispositions                       stable       ux  -
POST            /wizard/filings                                   stable       ux  -
POST            /wizard/filings/{id}/status                       stable       ux  -
GET             /wizard/hermes/api/model/options                  passthrough  ux  -
GET             /wizard/hermes/api/sessions                       passthrough  ux  limit,offset,include_children,snapshot
POST            /wizard/hermes/api/sessions                       passthrough  ux  -
GET             /wizard/hermes/api/sessions/{id}                  passthrough  ux  -
PATCH           /wizard/hermes/api/sessions/{id}                  passthrough  ux  -
GET             /wizard/hermes/api/sessions/{id}/messages         passthrough  ux  order,limit,offset,include_compacted,view
POST            /wizard/hermes/api/sessions/{id}/model            passthrough  ux  -
POST            /wizard/hermes/v1/runs                            passthrough  ux  -
GET             /wizard/hermes/v1/runs/{id}                       passthrough  ux  -
GET             /wizard/hermes/v1/runs/{id}/events                passthrough  -   -
POST            /wizard/hermes/v1/runs/{id}/approval              passthrough  ux  -
POST            /wizard/hermes/v1/runs/{id}/steer                 passthrough  ux  -
POST            /wizard/hermes/v1/runs/{id}/stop                  passthrough  ux  -
POST            /wizard-os-home/api/transcribe                    compat       ux  -
POST            /wizard-os-home/api/route                         compat       ux  -
GET,POST,DELETE /wizard/mcp                                       box          -   -
GET             /wizard/v1/agent-context                          box          -   harness,format
GET             /wizard/health                                    box          -   -
GET             /wizard/                                          page         ux  session,view
GET             /wizard-os-home/                                  page         ux  -
GET             /wizard/v1/wizard-apps                            proposed     -   -
GET             /wizard/v1/index/search                           proposed     -   q,tag,sort,limit,offset,type,category
GET             /wizard/v1/index/tags                             proposed     -   -
GET             /wizard/v1/index/apps/{owner}/{repo}              proposed     -   -
GET             /wizard-os-home/api/status                        gap          ux  -
```

Out of scope: paths the Android app calls on other apps (`/wizard-search/...`, `/meetings/...`) and app views opened from the launcher. They are not Agent Service routes.

## Common rules

**Access.** With `WIZARD_REQUIRE_CF_ACCESS` on (the code default), every route except `/wizard/health`, `/wizard/mcp` and `/wizard/v1/agent-context` needs a valid Cloudflare Access assertion, else `403 {"error":"access_required"}`. A Wizard OS box (`WIZARD_REQUIRE_CF_ACCESS=0`: the container default and James's daily service) has no per-request auth; reach is the boundary (loopback, the tailnet route, the shell). Per-account state (`thread-seen`, `thread-dispositions`) is keyed by the Access identity when Access is on, else by the single scope `wizard-account-local`.

**Box-only routes.** `/wizard/mcp` needs `Authorization: Bearer <WIZARD_MCP_TOKEN>` (`401 {"error":"unauthorized"}`) and refuses anything that came through a proxy (`X-Forwarded-For`, `Forwarded`, `Tailscale-User-Login`, `Cf-Connecting-Ip`, `Cf-Access-Jwt-Assertion`) with `403 {"error":"box_only"}`. `/wizard/v1/agent-context` takes the same bearer, or Access when that is on.

**Errors.** JSON `{"error":"<code>"}`. Unless a route lists its own: `400 invalid_request`, `403 access_required`, `404 not_found` (also every undocumented path), `409 conflict`, `413 body_too_large`, `415 unsupported_media_type`/`json_required`, `502 upstream_unavailable` (a dependency failed), `503 service_unavailable` (no Hermes key). Responses carry `Cache-Control: no-store`.

**IDs.** Session ids match `[A-Za-z0-9._:-]{1,200}`; Wizard creates its own as `wizard_<ms>_<12 hex>`; ids in the operator namespace are refused (`400`). Wizard file ids are `wf_<32 hex>` on a Wizard OS box and Wizard Inbox drop ids on James's box. Attachment ids are 32 hex. Public run ids are `wizardq_<32 hex>`.

## Settings and discovery

### `GET /wizard/v1/bootstrap`
Settings, capabilities and endpoint addresses. It still answers when Hermes is down (`joined_delegation` and `markdown` are then false).
```json
{"bootstrap":1,"api":"wizard-agent-service/1",
 "settings":{"schema":1,"owner":{"name":"Sam","place":""},"agent":{"name":"Wizard","adapter":""},
   "clock":{"timezone":"Asia/Bangkok","day_starts_at":"04:00"},"voice":{"language":"en","vocabulary":["Runtipi"]},
   "fast_router":{"account":"","model":""},"network":{"base_url":"https://box.example.ts.net","aliases":[]}},
 "settings_source":"file",
 "capabilities":{"voice":true,"router":true,"files":true,"resumable_uploads":true,"upload_destinations":true,"approvals":true,"steer":true,"joined_delegation":false,"markdown":false},
 "endpoints":{"apps":"/wizard/v1/apps","sessions":"/wizard/hermes/api/sessions","runs":"/wizard/hermes/v1/runs",
   "transcribe":"/wizard/voice/transcribe","route":"/wizard/v1/route","upload":"/wizard/files/upload",
   "uploads":"/wizard/v1/uploads","shares":"/wizard/v1/shares","user_files":"/wizard/v1/user-files"}}
```
`fast_router` shows only `account` and `model`, never the endpoint or key. `resumable_uploads` (with `endpoints.uploads` and `endpoints.shares`) is present when the service can store files and its upload state is writable; a client that does not see it uses `POST /wizard/files/upload`. `upload_destinations` (with `endpoints.user_files`) is present when, in addition, the box has a user-files root (`WIZARD_USER_FILES_ROOT`): uploads may then carry a `destination` and the Files app can list that root ([Upload destination](#upload-destination-files-app)). `network.base_url` is for links that leave Wizard; in-app links stay relative. An endpoint is `""` when its capability is off.

### `GET /wizard/v1/apps`
The launcher list: installed apps from the App Manager's `apps.json` (the shell itself left out) plus the owner's links from `launcher.json`. Only what a tile needs leaves the box: no MCP address, health URL, repo or skill path.
```json
{"schema":1,"apps":[
  {"id":"hello-wizard","name":"Hello Wizard","url":"/hello-wizard/","status":"running","system":false,"source":"apps.json"},
  {"id":"notes","name":"Notes","url":"https://notes.example.com/","source":"launcher.json"}]}
```

Installed apps additionally expose their safe `provides` list, and their declared `type`
(`view`, `service`, `agent` or `external`, from `wizard.md`) and `category` (`agent`,
`interface`, `app` or `system`) when `apps.json` carries one of those exact values; any
other value is omitted, and shells then fall back to their own sorting. Valid owner-installed
Chats providers expose the versioned `chats_view` descriptor (module URL, SHA-256,
bytes, pinned commit), and the response includes `slots.chats` and the Chats parking
row. The built-in fallback is `wizard-chats`. See [SKINS_AND_VIEWS.md §3](SKINS_AND_VIEWS.md#3-swappable-views-chats-first)
for exact manifest/registry shapes, owner default selection and trust boundaries.
Launcher links never supply in-document code.

### `GET|HEAD /wizard/v1/chats-views/:id/:hash.js`
Owner-gated, read-only JavaScript from the installed package's sealed share. The URL
must exactly match that app's admitted descriptor, including its SHA-256. Every read
checks confinement, byte limit, recorded size/hash and banned-API lint. `200` serves
JavaScript with `nosniff`, `no-store` and `X-Wizard-Sha256`; `403` is the existing
owner access gate, `404` means uninstalled/unadmitted/unknown URL, `409` means package
integrity failed, and other methods return `405`. No API proxy or redirect.

### `POST /wizard/v1/route`
Sorts one orb utterance into a phone command, an agent request or a view action, using the configured fast model (not the agent). Body ≤ 8 KB: `{"text":"…","force":"command"|"","view":{"name":"…","kind":"…"},"apps":["Notes"]}`. `200 {"cmd":{"route":"agent","summary":"water the plants"},"ms":12,"model":"<router model>"}`; `cmd.route` is always `command`, `agent` or `view`. Errors: `404 router_not_configured`, `400 invalid_request` (bad JSON or empty text), `502 router_unavailable`.

## Voice

### `POST /wizard/voice/transcribe`
Raw audio body with `Content-Type: audio/(webm|ogg|mp4|wav|x-m4a|aac|x-aac|mpeg)` and optional `X-Wizard-Filename`. Language and spelling hints come from settings. `200 {"text":"remind me to water the plants","provider":"local","model":"…"}`. Errors: `415 audio_required`, `400 empty_audio`, `400` blank transcription, `502` transcriber failure. Up to 180 s.

### `GET /wizard/voice/status`
`200 {"ready":true,"provider":"local","name":"Local model","model":"…","attested":false}`; `503` with `ready:false` and `name:"Voice unavailable"` when the transcriber is down. The UX derives this address from the transcribe endpoint (`…/transcribe` becomes `…/status`).

### `POST /wizard/voice/recovery-receipt`
Proof that a retained Android voice note was admitted (body ≤ 2 KB). `200 {"receipt":{…}}`; `400`/`409`/`413 voice_recovery_unverified`. Reads the run queue and Wizard Inbox. No caller on UX `daily`.

## Files and attachments

### `POST /wizard/files/upload`
Compat route for clients without `resumable_uploads`; new clients use [`/wizard/v1/uploads`](#resumable-uploads-wizardv1uploads). Raw bytes with `Content-Type: application/octet-stream`, `X-Wizard-Filename` and `X-Wizard-Mime`; ≤ 64 MB, read whole into memory. `201 {"file":{"id":"wf_…","name":"notes.txt","mime":"text/plain","bytes":11,"kind":"file","created_at":"…",…}}`. `415 bytes_required` for any other content type. On a Wizard OS box (`WIZARD_MEDIA_ROOT`) the file lands in the owner's Files root under `Inbox/<date>/` and never overwrites; on James's box it goes through Wizard Inbox. The response never carries the on-disk path.

To attach files to a message, pass `"wizard_file_ids":["wf_…"]` (≤ 8, unique) in a run or steer body. The service resolves them to trusted paths for the agent and strips the field.

### Resumable uploads (`/wizard/v1/uploads`)
One upload path for every file a client sends: chat attachments and shares. Bytes are streamed to disk (never held whole in memory), fsynced per chunk, and resumable from the last durable byte after a dropped connection, an app kill or a reboot. There is no per-file cap except real disk space: a file is refused only when it would not fit in free space minus a reserve (`WIZARD_UPLOAD_RESERVE_BYTES`, default 5 GiB; bytes still owed to open uploads count as used). A box may set `WIZARD_UPLOAD_MAX_BYTES` (default `0` = disk-bound only). File names and contents are never logged.

- `POST /wizard/v1/uploads` JSON `{"client_upload_id":"…","filename":"clip.mp4","mime":"video/mp4","bytes":123456789,"sha256":"…"?}` → `201 {"upload_id":"up_<32 hex>","offset":0,"bytes":123456789,"chunk_bytes":8388608,"status":"uploading"}`. `client_upload_id` is the client's own id (`[A-Za-z0-9._:-]{1,128}`): the same id returns the existing upload with its current `offset` (and `"status":"complete","file":{…}` once finished; header `Idempotency-Replayed: true`); the same id with a different `bytes`/`sha256` is `409 client_upload_id_conflict`. Errors: `507 {"error":"insufficient_storage"}` when the file would not fit or exceeds the box cap; `413 {"error":"file_too_large"}` when James's Wizard Inbox refuses the size (its own boundary, 2 GiB today); `400 invalid_request` with `field`.
- `GET /wizard/v1/uploads/{id}` → `200 {"upload_id","offset","bytes","chunk_bytes","status":"uploading"|"complete"|"failed","file"?,"error"?}`; also header `Upload-Offset`. `failed` carries `error` (`sha256_mismatch`, `expired`).
- `PATCH /wizard/v1/uploads/{id}` raw bytes, `Content-Type: application/offset+octet-stream`, `Upload-Offset: <n>`. Appends at `n`, fsyncs, `204` with `Upload-Offset: <new>`. A chunk is ≤ 64 MiB (`413 body_too_large`) and may not run past `bytes` (`413 chunk_too_large`); suggested size is `chunk_bytes` (8 MiB). `n` ≠ the server offset → `409 {"error":"offset_mismatch","offset":<server offset>}` (also in `Upload-Offset`): continue from that offset. If a connection drops mid-chunk, the bytes that reached disk are kept; `GET` (or the 409) says where to resume. A newer PATCH for the same upload ends an older one still in flight. `410` once the upload has failed or expired; `415 bytes_required` for another content type; `400` for a missing or malformed `Upload-Offset`.
- `POST /wizard/v1/uploads/{id}/complete` (empty JSON body) verifies the size and, when given, the sha256, then stores the file → `200 {"file":{…}}`, the same shape `/wizard/files/upload` returns, so `file.id` is a `wizard_file_id` for runs and steers. Idempotent: a repeat returns the same file. `409 {"error":"upload_incomplete","offset":n}` before the last byte; `422 {"error":"sha256_mismatch"}` fails the upload (and its share) and keeps nothing.
- Storage: Wizard Files, as for `/wizard/files/upload`. On a Wizard OS box chunks stage in `<media root>/.wizard-uploads/` (same filesystem) and the finished file is moved into `Inbox/<date>/<name>` without being read into memory. On James's box the Wizard Inbox drop service owns the bytes: with `sha256` declared, chunks stream straight through to a drop upload; without it they stage locally and are pushed to the drop service at completion.
- Incomplete uploads expire 7 days after their last chunk; their bytes are removed.

### Upload destination (Files app)
The Files app uploads into the owner's user-files root (Runtipi's `media/` folder on a Wizard OS box, docs/SYSTEM_APPS.md) through the same resumable path. Needs `capabilities.upload_destinations`.

- `POST /wizard/v1/uploads` takes an optional `"destination":{"folder":"Projects/Clips"}`. `folder` is relative to the user-files root, `/`-separated; `""` or omitted means `Inbox/<YYYY-MM-DD>` with the date in the owner's time zone (`settings.clock.timezone`), fixed when the upload is created. A named folder must exist and be writable when the upload is created (`404 folder_not_found`, `403 folder_not_writable`, `409 not_a_folder`); the dated Inbox folder is created as needed. Refused with `400 invalid_request`, `field:"destination.folder"`: absolute paths, `..`, hidden segments (leading `.`), backslashes or control characters, and any folder that resolves (through symlinks) outside the root. `destination` with any other key is `400`, `field:"destination"`. No user-files root → `409 destination_unavailable`.
- Everything else is unchanged (PATCH, GET, offsets, 507, expiry, idempotent `client_upload_id`). On `complete` the finished file is placed in the folder under its own (cleaned) file name without being read into memory (hard link from the staging folder `<root>/.wizard-uploads/`, a checked rename where links are unsupported). It never overwrites: a taken name becomes `name (2).ext`, `name (3).ext`, …. A repeated `complete` returns the same placement. The response is `200 {"file":{"filename":"clip.mp4","path":"Projects/Clips/clip.mp4","folder":"Projects/Clips","mime":"video/mp4","bytes":123,"sha256":"…","created_at":"…","location":"files_root"}}`: a user file addressed by `path`, not a Wizard file id (it is not attached to a chat). Uploads without `destination` (chat attachments, shares) keep going to Wizard Files exactly as before.
- `GET /wizard/v1/user-files?folder=<path>` → `200 {"folder":"Projects","entries":[{"name":"Clips","is_dir":true,"size":0,"mtime":"<ISO>"},{"name":"b.txt","is_dir":false,"size":11,"mtime":"<ISO>"}],"truncated"?:true}`. Folders first, then names (case-insensitive, numeric). Hidden names (leading `.`) are left out, and so are symlinks that resolve outside the root; at most 5000 entries. `folder` omitted = the root. Same folder rules as above (`400`, `404 folder_not_found`, `409 not_a_folder`); `503 service_unavailable` without a user-files root.
- `GET|HEAD /wizard/v1/user-files/content?path=<path>[&download=1]` → the file's bytes, `inline` for images, audio, video, PDF and plain text, else (or with `download=1`) `attachment`; single `Range` requests (`206`, `416`). `Content-Security-Policy: sandbox`, `X-Content-Type-Options: nosniff`. `404 not_found` for a missing file, a folder, or a symlink out of the root.
- Configuration: `WIZARD_USER_FILES_ROOT` (the root as this service sees it). It is separate from `WIZARD_MEDIA_ROOT`, which moves chat attachments into the files root, and from `WIZARD_FILES_ROOT`, the agent-facing path named in the kernel text. The placement index lives next to the upload state (`WIZARD_USER_FILES_INDEX_PATH` to override).

### Shares (`/wizard/v1/shares`)
Files shared into Wizard from another app (Android share sheet; later Mac and iOS), delivered server-side as one message.

- `POST /wizard/v1/shares` JSON `{"client_share_id":"…","agent":"hermes"?,"thread":"<session id>"?,"note":"…"?,"files":[{"filename","mime","bytes","sha256"?},…]}` (1 to 8 files, note ≤ 8000 chars) → `201 {"share_id":"sh_<32 hex>","agent":"hermes","thread_id":"wizard_<ms>_<12 hex>","status":"uploading","uploads":[{"upload_id","offset","bytes","chunk_bytes","status"},…]}`, uploads in `files` order. Idempotent on `client_share_id` (same files → the same share, its current offsets and status, `Idempotency-Replayed: true`; different files → `409 client_share_id_conflict`). `agent` omitted → the default agent (`hermes`, the main agent, on a box without an agents registry). An unknown or stopped agent → `409 {"error":"agent_unavailable","agent":"…"}`, never another agent. `thread` omitted → a new thread whose id is returned now and which is created at delivery, titled with the first file name until the agent retitles it (the title is not a user lock). A `thread` the agent does not have → `404 {"error":"thread_not_found"}`. `507 insufficient_storage` when the files together would not fit.
- Each upload is sent with `PATCH /wizard/v1/uploads/{id}` and finished with `…/complete`, exactly as above.
- When the last upload completes, the service delivers once: it creates the new thread if needed and admits one run in `thread_id`, with every file attached (`wizard_file_ids`) and the note as the user's text (empty note → `Shared 1 file` / `Shared N files`), on the target agent, through the same path as a client send (`Idempotency-Key: share-<share_id>`). Concurrent or replayed completes, a replayed create and a restart mid-delivery never post twice; a transient Hermes failure is retried with backoff.
- `GET /wizard/v1/shares/{id}` → `200 {"share_id","agent","thread_id","status":"uploading"|"delivering"|"delivered"|"failed","run_id"?,"error"?,"uploads":[…]}`. `failed` carries `error` (`sha256_mismatch`, `expired`, `delivery_rejected_<status>`); a failed share delivers nothing.
- Privacy: a share to a `private`-class agent (agents registry present, spec/AGENTS.md) is stored in that agent's own `home/inbox/<date>/` and never in `media/` or the main Wizard Files index, and is delivered only to that agent. Notifications are the client's: "N files → <agent label>", never file names.

### `GET /wizard/files`
`200 {"files":[<file>,…]}`, newest first, ≤ 100.

### `GET|HEAD /wizard/files/{id}/content`
The bytes, with `Range` (`206`, `416`). `404 not_found` for an unknown id.

### `GET|HEAD /wizard/attachments/{id}`
A file the agent produced (agent artifact) or, on James's box, a Helm attachment, by 32-hex id. Images, audio and video are `inline`; everything else downloads as `attachment` with its real type. `Range` supported. Errors: `404 attachment_not_found`, `502 attachment_unavailable`, `503 attachment_unavailable` when no Helm is configured and the id is not an artifact. Message history marks attachments with a `<helm_attachments>` block whose items carry `id`, `name`, `mime`, `kind` and optional `transcript`; the UX builds `/wizard/attachments/<id>` from them.

### `POST /wizard/files/invite`
Phone pairing invite from Wizard Inbox: `201 {"origin":"https://…","enroll_url":"https://…","deep_link":"wizard://pair…"}`. Needs Wizard Inbox (James's box): without an Inbox token `503 service_unavailable`, with a bad Inbox answer `502`. No caller on UX `daily`.

## Threads (Hermes passthrough)

`/wizard/hermes<path>` forwards `<path>` to Hermes with the box's Hermes key, only when method, path and query match the allowlist (`404 not_found` otherwise, including any `%`, `\` or `//` in the path). Request bodies must be `application/json` (`415 json_required`). Responses are scanned: if a Hermes key, Inbox token or private path would leak, the answer becomes `502 unsafe_upstream_response`; private file paths in session JSON are rewritten.

| Route | Query rules | Wizard projection on top of Hermes |
|---|---|---|
| `GET /api/model/options` | none | none |
| `GET /api/sessions` | `limit`, `offset` ≤ 6 digits; `include_children` only `false`; `snapshot` (a paging cursor, not forwarded) | canonical paged listing; rows gain live run status from the run queue and admitted runs, defer state and Wizard titles; archived rows only with the state.db fallback |
| `POST /api/sessions` | none | `{"source":"wizard-mobile","id":"wizard_…"}`; operator ids refused |
| `GET /api/sessions/{id}` | none | private paths rewritten |
| `PATCH /api/sessions/{id}` | none | `{"title":…}` renames; `{"archived":true\|false}` closes or restores and clears any defer |
| `GET /api/sessions/{id}/messages` | `order` `latest`/`oldest`; `limit` ≤ 500; `offset`; `include_compacted` `true`/`false`; `view` only `wizard` (not forwarded) | always: status markers and agent media projected to `/wizard/attachments/…`. `view=wizard` also drops delegation-batch and task-restore rows, slims each row to `id`, `role`, timestamps, `display_kind`, `display_content`, `content` (tool rows: no content, plus `plan`/`question`), adds `shareable` (a finished assistant answer), slims `tool_calls` to name + `display_label`, and turns process wake-ups into `role:"system"`, `display_kind:"process_wakeup"`. Rows with `display_kind:"hidden"` stay; the client hides them |
| `POST /api/sessions/{id}/model` | none | `{"model":…,"provider":…}`; the operator preset is refused |

Example, `GET /wizard/hermes/api/sessions/chat-recent/messages?order=oldest&limit=500&include_compacted=true&view=wizard`:
```json
{"messages":[{"id":"m-1","role":"user","created_at":"…","content":"Help me plan a quiet weekend.","shareable":false},
             {"id":"m-2","role":"assistant","created_at":"…","content":"I found three gentle options close to home.","shareable":false}]}
```

## Runs (Hermes passthrough, through the Wizard run queue)

### `POST /wizard/hermes/v1/runs`
Body `{"session_id":"wizard_…","input":"…"|[parts],"wizard_file_ids":[…]?,"instructions":"…"?}` with an `Idempotency-Key` header (the UX uses a UUID per send, the outbox its item id, Android voice notes `voice-…`).

With the run queue on (every deployed service: James's daily and the container), admission is **durable and asynchronous**: `202` with the run's current public shape and `Idempotency-Replayed: true|false`. While it waits that is `{"object":"run","run_id":"wizardq_<32 hex>","session_id":"…","status":"queued","queue_position":0,"queue_reason":"capacity","created_at":…,"updated_at":…}`; if Hermes already took it, the same `202` carries `status:"running"` and Hermes's fields under the public ids. Front ends treat any `2xx` with a `run_id` as admitted. The same key and body replays the same `run_id`; an Android voice retry of the same recording into the same thread replays the first admission. The `wizardq_…` id is the run id for every later call; the service maps it to the Hermes run once Hermes accepts it. Without a queue (tests only) Hermes's own `201 {"run_id":…,"status":…}` passes through.

The service rewrites the body before Hermes sees it: it sets its own run instructions plus the Wizard OS kernel (or, with the `wizard-os` Hermes plugin, only the app changes since the thread started), adds `delegation_delivery:"join"` and `response_rendering:"markdown"` when Hermes advertises them, and turns `wizard_file_ids` into trusted file references. See D1 for the client's `instructions`.

### `GET /wizard/hermes/v1/runs/{id}`
Status. A queued id still waiting gives the queued shape above. Once admitted: Hermes's run object with `run_id` and `session_id` set to the public ids, e.g. `{"run_id":"wizardq_…","session_id":"…","status":"running","output":"…","approval":{…}?}`. Statuses: `queued`, `running`, `waiting_for_approval`, `stopping`, then `completed`, `failed`, `cancelled` or `interrupted`. The UX and Android follow a run by **polling** this.

### `GET /wizard/hermes/v1/runs/{id}/events`
Server-sent events. While queued: `event: run.queued`, then a comment every 15 s until Hermes starts the run, then Hermes's stream (`message.delta`, `tool.started`/`tool.completed`, `reasoning.available`, `approval.request`, `run.completed`/`run.failed`/`run.cancelled`), filtered so no secret or private path passes. Closing the connection ends only the stream, never the run. Served and part of v1; UX `daily` does not use it (it polls).

### `POST /wizard/hermes/v1/runs/{id}/steer`
`{"input":"…","wizard_file_ids":[…]?}` adds guidance to a live turn: `200 {"accepted":true}` from Hermes. While the run is still queued the guidance is appended to the queued request: `202 {"accepted":true,"run_id":…,"status":"queued","queue_position":…}`. Unknown `wizardq_` id: `404`. Hermes answers `409` or `404` when no agent is attached; the UX then treats `404`/`409`/`410` as "start a new run in this thread".

### `POST /wizard/hermes/v1/runs/{id}/approval`
`{"choice":"allow_once"|"deny"|…,"request_id":"…"}` from the run's `approval` object. `200 {"accepted":true}`; `409` if the run is not waiting or the choice or request id does not match; `409 run_queued` for a run not yet admitted.

### `POST /wizard/hermes/v1/runs/{id}/stop`
No body. A queued run is cancelled locally: `202` with the queued shape and `status:"cancelled"`. An admitted run: Hermes's `202 {"accepted":true}`.

## Schedules (decision #47; companion wizard-agent-service #81)

These additive endpoints are `proposed` until the companion service PR lands;
promote the four route-table rows to `stable` with that merge. Approval of the
single-scheduler architecture does not itself enable a timer or migrate a live
installation. Settings → Schedules is the proposed caller (wizard-ux #293).

All endpoints use the existing owner/service principal and configured Access
checks; secondary-agent credentials cannot manage schedules. Bodies are JSON,
limited to 128 KiB. Cross-site browser requests are rejected.

| Endpoint | Contract |
| --- | --- |
| `GET /wizard/v1/schedules` | `200 {"schedules":[job,...]}` |
| `POST /wizard/v1/schedules` | Create, `201 job` |
| `PATCH /wizard/v1/schedules/{id}` | Edit, `200 job`; `enabled:false/true` pauses/resumes |
| `DELETE /wizard/v1/schedules/{id}` | `200 {"deleted":true}` |
| `POST /wizard/v1/schedules/{id}/run` | `202 occurrence`, durable request receipt, not completion proof |
| `POST /wizard/v1/schedules/import-hermes` | `{ "dryRun": true/false }` → `200 {"dryRun":...,"results":[...]}` |

Create/edit fields: `name`, `when`, `timezone`, `agent`, optional `model`,
`prompt` and/or `skill`, optional `thread`, `enabled`. `when` has exactly one of
`{"cron":"0 9 * * *"}` (five fields), `{"every":30}` (minutes, at least 1),
or `{"once":"2026-10-22T09:00:00+07:00"}` (explicit offset/Z). Unknown fields
are rejected. The service generates `id`, cursor/anchor and created/updated
metadata. Defaults: enabled, `agent:main`, and the current owner
`settings.clock.timezone` (Asia/Bangkok when unset). An explicit per-job timezone
or `WIZARD_SCHEDULER_TIMEZONE` overrides that default. Existing jobs retain their
stored timezone when the owner setting changes.

### Last and next run

Every job in GET and the job returned by POST/PATCH includes:

```json
{
  "lastRun": {
    "scheduledFor": "2026-10-21T00:00:00.000Z",
    "startedAt": "2026-10-21T00:00:01.000Z",
    "finishedAt": "2026-10-21T00:00:09.000Z",
    "outcome": "posted",
    "error": null
  },
  "nextRun": "2026-10-22T00:00:00.000Z"
}
```

`lastRun` is null before any occurrence. Otherwise it is the latest durable
occurrence by scheduled instant (including run-now), never the job's edit time or
unrelated activity in its destination. `outcome` is `running` after admission or
while queued/running, `posted` for completed nonempty visible output, `silent` for
completed empty/[SILENT] output, and `failed` for failed/cancelled/interrupted runs
or an admission failure awaiting exact-key retry. Admission is not completion.
`error` is null or short service-owned copy; raw upstream errors/output are never
copied into this projection. Admission retry clears its error on success.

Run status is refreshed on the scheduler tick and before GET/PATCH via the ordinary
exact run-ID/agent route. Last observations persist in the existing occurrence
SQLite ledger (additive schema migration); completed observations survive restart
and upstream retention. A lookup outage preserves the durable observation, not a
fabricated failure. `startedAt` is nullable until known (or first observed running);
`finishedAt` is nullable until terminal and uses runtime time when provided, else
first terminal observation time. Old receipts can be enriched by exact-ID lookup;
unavailable upstream history cannot retrospectively recover exact timestamps.

`nextRun` is a UTC ISO rendering of the durable `nextAt` cursor for enabled
cron/interval/once jobs, null while paused or after a claimed one-shot (including
pause/resume). It describes the schedule cursor, not a promise of worker capacity
or proof the opt-in timer is active. Existing numeric `nextAt` remains for
compatibility. Both new fields are read-only and rejected in write bodies.
Clients format these ISO instants in the owner's clock timezone and retain an
unavailable fallback when connecting to older services without these fields.

`thread` names an existing session. If absent/null, first occurrence reserves a
stable session ID and creates a thread titled with `name` (`Schedules · <name>`
when a Project · Feature title was not supplied). Every later occurrence reuses
that thread. Changing a bound job's agent requires an explicit thread choice.
`main` maps to the main Hermes agent; other IDs use the ordinary agent router.

An occurrence receipt contains `key`, `jobId`, `scheduledAt`, `agent`, `thread`,
`createThread`, `title`, and the frozen ordinary-run `body`. The key is
`schedule:<jobId>:<scheduledInstantISO>`. Claim and next-cursor advance are one
durable transaction; ambiguous admission retries the same body/key through the
ordinary chat admission path. The main-agent queue retains schedule receipts
past its normal terminal-retention window. Other agents retain their ordinary
runtime's idempotency contract. Downtime/forward jumps produce at most one
catch-up per job; an unresolved pending admission is retried instead of claiming
another catch-up. Backward jumps cannot rewind the cursor. One-shots disable
at claim and cannot replay on pause/resume/restart. A paused job's explicit
run-now still works. Editing does not rewrite already frozen outbox payloads;
deleting cancels only unadmitted entries. There is no bounded seen-list.

A final answer equal to, starting with, or ending with `[SILENT]` (ignoring a
Wizard status trailer) produces no visible answer and advances no visible
reply/unread clock. The synthetic schedule input is internal. History/preview
and canonical session-truth projections suppress these without rewriting the
Hermes transcript or marking the whole thread seen. Scheduled text streaming
waits for terminal completion so a trailing sentinel cannot flash on screen;
interactive chat streaming is unchanged.

Import reads `<HERMES_HOME>/cron/jobs.json` **read-only** and always creates
**paused** copies of supported cron/interval/once, name, prompt/skills and model
fields. `dryRun` defaults true and changes neither store. Source job IDs are
remembered durably, so repeat import returns `already imported` even after
restart/deleting a copy. Script/no-agent rows return
`not imported: script job`; unsupported rows are reported individually.
Import never disables Hermes cron or silently activates migrated copies.

`WIZARD_SCHEDULER=1` is required to start the loop; off by default. State is
configurable with `WIZARD_SCHEDULER_STATE_PATH`, normally alongside the service
run queue under the resolved Hermes home. Store and queue must be backed up
together. Loop-off does not disable CRUD/import or explicit run-now. Installer
cut-over, MCP tools, schedule templates and a schedules UI are separate slices.
No live deployment is implied by this contract.

## Read state, attention and filing

### `GET|PUT /wizard/thread-seen`
Per-account "last seen" state behind unread markers. A query string gives `400`. `GET` → `{"state":<state>|null}`. `PUT <state>` (JSON ≤ 256 KB) merges per thread, newest `updatedAt` winning, and returns the merged `{"state":<state>}`; a malformed state is `400 invalid_request`.
```json
{"initializedAt":1791763200000,
 "threads":{"direct:chat-recent":{"updatedAt":"2026-10-12T00:00:00.000Z","previewFingerprint":"abc123","messageCount":2,"status":"completed","assistantActivityAt":"…","seenAt":1791763300000,"unreadAt":1791763400000}}}
```
Thread keys match `[A-Za-z0-9._:-]{1,320}` (≤ 500 kept); `status` is one of `idle`, `submitting`, the run statuses. `seenAt` and optional `unreadAt` are safe-integer epoch milliseconds no more than 24 hours ahead of the service clock. A thread is explicitly unread while `unreadAt > seenAt`; reading it writes a newer `seenAt`. Merges retain the greatest `seenAt` and `unreadAt` independently, so an older client cannot erase either marker and clients that do not understand `unreadAt` remain compatible. The service also keeps `unreadAt` in a sidecar beside its schema-1 state so rolling back to a version that drops unknown fields cannot erase manual unread markers.

### `GET|PUT /wizard/thread-dispositions`
Per-account "later" (deferred) flags. A query string gives `400`. `GET` → `{"state":{…}}`. `PUT {"runtime":"direct","sessionId":"…","deferred":true}` (≤ 1 KB, same origin only) → `{"record":{…}}`. A new run in the thread clears its disposition.

### `GET /wizard/attention`
Failed Wizard work to show: `{"attention":[{"id":"<uuid>","thread_id":"…","session_id":"…","title":"…","detail":"…","failed_at":"…","can_retry":true}]}`. Empty on a box without Helm.

### `POST /wizard/attention/{id}/retry`, `POST /wizard/attention/{id}/dismiss`
`{id}` is a UUID; empty body. `{"ok":true,"action":"retry"|"dismiss"}`; `400` for a bad id or any body. Helm-backed (James's box).

### `POST /wizard/session-failure/{id}/dismiss`
Hides a failed thread's banner; empty body. `200 {"ok":true,"dismissed":true,"session_id":"…"}`.

### `POST /wizard/filings`, `POST /wizard/filings/{id}/status`
"File this thread" on James's box. `{"session_id":"…","client_command_id":"…","runtime":"direct"}` starts a Helm filing (`202 {"ok":true,"source_thread_id":…,"activity_id":…}`) or returns its receipt (`200`, after which the Hermes session is archived). `status` with `{"runtime":"direct"}` reads progress. Needs Helm; elsewhere it fails with an error, and the UX then archives the thread with `PATCH {"archived":true}`.

## Compatibility aliases

Served only when the service also serves the UX (`WIZARD_UX_DIR`), under its prefix (`WIZARD_UX_PREFIX`, default `wizard-os-home`).
- `POST /wizard-os-home/api/transcribe`: multipart (`file`, optional `model`), same origin only. `200 {"text":…,"ms":…,"model":…}`. The Android lock-screen assistant still calls it, and the UX does before bootstrap.
- `POST /wizard-os-home/api/route`: same as `/wizard/v1/route`. The UX calls it before bootstrap.

## Box surfaces (not for front ends)

- `/wizard/mcp`: the `wizard` MCP gateway (streamable HTTP; spec/AGENT_BRIDGE.md). `POST` JSON-RPC (`initialize` returns `Mcp-Session-Id`; `tools/list`, `tools/call`, `ping`), `GET` the notification stream (`tools/list_changed` when `apps.json` changes), `DELETE` ends the session. `404` when the bridge is off.
- `GET /wizard/v1/agent-context?harness=hermes|generic&format=json`: the Wizard OS kernel for a harness, as text, or as JSON (`text`, `chars`, `harness`, `mcp_server`, `job_map`, `job_skills`, `apps`).
- `GET /wizard/health`: `{"status":"ok","upstream_reachable":true,"queue":{…}}`. No auth.

## Pages

`GET /wizard/` serves the legacy Wizard (Mobile) page; `?session=<id>` and `?view=work` are how notifications and links open a thread. `GET /wizard-os-home/` serves Wizard UX when `WIZARD_UX_DIR` is set. `/` redirects to whichever exists. Static files under both prefixes are not API.

## Alongside mode and the state.db fallback

Install alongside (DECISIONS #41; spec/WIZARD_CLI.md, spec/AGENT_BRIDGE.md) changes no route. It changes what some routes can know:
- `wizard link` makes exactly three Hermes config edits (`mcp_servers.wizard`, `skills.external_dirs += ~/.wizard-os/skills`, `plugins.enabled += wizard-os`), recorded for `wizard unlink`. None touches this API.
- By default the shell gets **no Hermes home**: only `cache/images`, read-only, and `WIZARD_HERMES_STATE_PATH` is empty. Over HTTP alone these answers are reduced, not errors: the thread list has no **archived** threads (Hermes `/api/sessions` never lists them); there are no **agent-made thread titles** (title authority needs `state.db`); turns running on **other surfaces** (Telegram, TUI, cron) do not hold queued Wizard runs; session route truth (model, lineage) is not annotated; the Helm closure overlay is absent.
- `wam alongside --share-history` mounts the Hermes home read-only and sets the fallback path, and all five come back. `wizard doctor` says which mode a box is in.

## Discrepancies

Found while documenting. Each is today's behaviour, recorded rather than changed here.

- **D1. The client's `instructions` are dropped.** The UX sends `instructions` on `POST …/v1/runs` (which view the owner was looking at, for review and voice: `web/live.js` `send`/`reply`, `web/app.js`, `web/device.js`, `web/outbox.js`). The service's `directBody` overwrites `instructions` with its own run instructions and kernel, so Hermes never receives the client's text. Keeping clients out of the per-run system prompt may be intended; the UX code assumes the opposite. The probe asserts today's behaviour, so either fix shows up as a contract change: the service appends the client text (with a size cap), or the UX moves that context into `input`.
- **D2. Voice status before bootstrap.** Without bootstrap the UX derives the status address from the alias `api/transcribe` and asks for `/wizard-os-home/api/status`, which nothing serves (`404`), so the voice indicator reads "unavailable" on a pre-bootstrap service. Route table class `gap`.
- **D3. App Manager views are not shipped.** wizard-agent-service PR #7 (draft, staged only) adds `GET /wizard/v1/wizard-apps` and a read-only App Index proxy `GET /wizard/v1/index/{search,tags,apps/<owner>/<repo>}` for the My Apps, App Store and Resources views. They are class `proposed`: not on `main`, not deployed, not part of v1. They move to `stable` in the PR that merges them, together with this file.
- **D4. Helm and Wizard Inbox routes.** `filings`, `attention/{id}/retry|dismiss`, `files/invite` and `voice/recovery-receipt` only work on James's box (Helm, Wizard Inbox). On a Wizard OS box they return errors or empty lists. They stay in v1 so the daily shell keeps working; a Wizard OS front end must treat them as optional.
- **D5. `/wizard/` is still the legacy page.** The Wizard UX entry point is `/wizard-os-home/`, while thread links (`chatUrl`, notifications) point at `/wizard/?session=…`.
- **D6. Share delivery uses the model the thread already has.** A share has no model picker, so its run carries no `model`/`provider`: a new thread runs on the agent's default model and an existing thread keeps its own. A client send carries the picker's route with `require_model_lock`.

## Verifying the contract

```sh
# UX coverage: every /wizard/... request in Wizard UX source maps onto a documented route (exit 1 if not)
python3 tools/check_api_contract.py --ux <wizard-ux checkout>
# the checker's own tests, including the negative-control fixture
python3 -m pytest -q tools/tests/test_api_contract.py
# behaviour: every served route exercised against an isolated service and fixtures; undocumented paths must 404
(cd <wizard-agent-service checkout> && npm ci) && node tools/api_contract_probe.mjs --service <wizard-agent-service checkout>
```
Neither tool calls a live endpoint or writes outside a temp directory. Proposed routes never count toward acceptance; the probe requires them to answer `404` on the commit under test.
