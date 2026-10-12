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
- **Most v1 routes have no `/v1` in the path.** Only `bootstrap`, `apps`, `route` and `agent-context` do. The rest (`/wizard/files`, `/wizard/thread-seen`, `/wizard/attention`, ...) are v1 at their current paths and are not being moved.
- **Passthrough (`/wizard/hermes/...`):** the Hermes API (`/api/sessions...`, `/v1/runs...`) behind a fixed allowlist. The allowlist (paths, methods, query keys, limits) and the Wizard projections listed below are v1. The rest of each body is whatever Hermes returns and moves with Hermes, so front ends read it defensively (`run.run_id || run.id`, `p.data || p.messages || p.items`), as the UX already does. The agent adapter call set (spec/AGENT_BRIDGE.md, DECISIONS #48) is what a second harness must serve underneath.
- **Discovery:** `GET /wizard/v1/bootstrap` returns `bootstrap: 1`, `api: "wizard-agent-service/1"`, `capabilities` and `endpoints`. Front ends take the apps, sessions, runs, transcribe, route and upload addresses from `endpoints` and switch features off from `capabilities`. A shell that cannot reach bootstrap falls back to the pre-bootstrap aliases (class `compat`).

## Route table

Machine-readable: both checking tools parse this block. Columns: methods, path (`{x}` = one path segment), class, whether Wizard UX (web or Android) calls it (`ux`) or not (`-`), allowed query keys (`-` = none).

Classes: `stable` = Agent Service route, v1. `passthrough` = Hermes route behind the allowlist. `compat` = alias kept for older shells and native builds. `box` = agent and operations surface, not for front ends. `page` = HTML entry point. `proposed` = in an open PR, **not served on main**, not part of v1. `gap` = the UX calls it and main does not serve it (see Discrepancies).

```routes
# methods       path                                              class        ux  query
GET             /wizard/v1/bootstrap                              stable       ux  -
GET             /wizard/v1/apps                                   stable       ux  -
POST            /wizard/v1/route                                  stable       ux  -
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
 "capabilities":{"voice":true,"router":true,"files":true,"approvals":true,"steer":true,"joined_delegation":false,"markdown":false},
 "endpoints":{"apps":"/wizard/v1/apps","sessions":"/wizard/hermes/api/sessions","runs":"/wizard/hermes/v1/runs",
   "transcribe":"/wizard/voice/transcribe","route":"/wizard/v1/route","upload":"/wizard/files/upload"}}
```
`fast_router` shows only `account` and `model`, never the endpoint or key. `network.base_url` is for links that leave Wizard; in-app links stay relative. An endpoint is `""` when its capability is off.

### `GET /wizard/v1/apps`
The launcher list: installed apps from the App Manager's `apps.json` (the shell itself left out) plus the owner's links from `launcher.json`. Only what a tile needs leaves the box: no MCP address, health URL, repo or skill path.
```json
{"schema":1,"apps":[
  {"id":"hello-wizard","name":"Hello Wizard","url":"/hello-wizard/","status":"running","system":false,"source":"apps.json"},
  {"id":"notes","name":"Notes","url":"https://notes.example.com/","source":"launcher.json"}]}
```

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
Raw bytes with `Content-Type: application/octet-stream`, `X-Wizard-Filename` and `X-Wizard-Mime`; ≤ 64 MB. `201 {"file":{"id":"wf_…","name":"notes.txt","mime":"text/plain","bytes":11,"kind":"file","created_at":"…",…}}`. `415 bytes_required` for any other content type. On a Wizard OS box (`WIZARD_MEDIA_ROOT`) the file lands in the owner's Files root under `Inbox/<date>/` and never overwrites; on James's box it goes through Wizard Inbox. The response never carries the on-disk path.

To attach files to a message, pass `"wizard_file_ids":["wf_…"]` (≤ 8, unique) in a run or steer body. The service resolves them to trusted paths for the agent and strips the field.

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

## Read state, attention and filing

### `GET|PUT /wizard/thread-seen`
Per-account "last seen" state behind unread markers. A query string gives `400`. `GET` → `{"state":<state>|null}`. `PUT <state>` (JSON ≤ 256 KB) merges per thread, newest `updatedAt` winning, and returns the merged `{"state":<state>}`; a malformed state is `400 invalid_request`.
```json
{"initializedAt":1791763200000,
 "threads":{"direct:chat-recent":{"updatedAt":"2026-10-12T00:00:00.000Z","previewFingerprint":"abc123","messageCount":2,"status":"completed","assistantActivityAt":"…","seenAt":1791763300000}}}
```
Thread keys match `[A-Za-z0-9._:-]{1,320}` (≤ 500 kept); `status` is one of `idle`, `submitting`, the run statuses.

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
