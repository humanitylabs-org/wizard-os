# Browser-trust adapters: proposed contracts

**Proposal for Jan and Miguel to review · 1 November 2026**

This is an implementable design proposal, **not an approved manifest extension or an existing SDK**. It complements [REVIEW-BRIEF.md](REVIEW-BRIEF.md). All limits below are proposed defaults, subject to prototype measurements. No implementation or release is authorized here.

## 1. Extend the existing boundary, not a second bridge

REUSE UX #327 at `f85d6231`: `WizBrowserBoundary.attach/admits`, registered `contentWindow`, per-load channel, load revocation, Back/theme/field messages, existing sharing/transcription services. Its current opaque service allowlist is only `ready`, `share.wizard`, `voice.transcribe`.[2] EXTEND that dispatch and shared client with the methods below; do not claim they exist today. REUSE Service #100 and WAM #168 owner checks, source-qualified grant resolution, resumable uploader and actual app gateways.[3][4][7]

NEW: operation registry, per-installation asynchronous state facade, scoped resource tickets and bounded stream facade. The registry must not be an HTTP/MCP forwarding interface.

### Authority model

The shell resolves the following for routing and defense in depth, without trusting request fields; the server registry in §3 is the authoritative permission boundary:

```ts
type InstallPrincipal = {
  installationId: string;        // instance on this box, not catalogue app ID
  sourceId: string;              // canonical source provenance recorded by WAM
  installedCommit: string;
  permissionRevision: string;
};
type ViewBinding = {
  principal: InstallPrincipal;
  frame: HTMLIFrameElement;
  generation: string;            // replaced on every trusted load/registration
  channel: string;               // random, not an owner credential
};
```

`sourceId` is an opaque platform value tied to the recorded repository/source; an app cannot choose it. Duplicate `profiles` publishers demonstrate why catalogue IDs alone are insufficient.[7] Validate installed/running state, exact source, selected provider grants and current permission revision at every admission and before disclosing results. Names, URLs and manifest claims do not confer system-panel authority.

Proposed normal frame attributes: `sandbox="allow-scripts allow-forms allow-downloads" referrerpolicy="no-referrer"`. No `allow-same-origin`, popups, top navigation or modals. This retains the draft’s form/download tokens for parity, but direct form targets and downloads must still pass server/native resource authorization. Stage 1 must enumerate every legacy download path: approved safe public/blob exports may remain sandbox-native; private resources and native device saves use `download.request`. Remove `allow-downloads` per app if it has no approved direct path. No token creates an unreviewed second private-download path. Deny iframe device permission delegation explicitly: microphone, camera, display capture, clipboard read/write, geolocation and other powerful browser features default to none through frame `allow` plus compatible response Permissions-Policy. Main-document device access remains separately reviewed. Do not use a wildcard to grant an opaque frame device rights. Unsupported policy/receiver behavior must fail closed for that capability. Add service workers/offline, cookies, BroadcastChannel, Web Locks, dialogs and downloads to parity inspection; none is assumed preserved by sandboxing. Audit every frame creator, generated Pages/Chats modules and owner-origin content endpoint. Untrusted content must not execute in the main shell document. Install identity is not a private-agent grant; a private source stays sealed from other agents and ordinary app requests.

**No direct-backend bypass:** when enforcement is enabled, every app route reachable with network-owner identity must require a scoped non-ambient adapter credential or equivalent independently reviewed app authentication. Cover reads, writes, forms/simple requests, media and preflights, not just owner API prefixes. A compromised frame must not reach another app by skipping `data.call`. Do not forward the shell token to app upstreams. Keep enforcement off until every installed app and separate listener passes, or obtain James's explicit approval to quarantine incompatible apps with a visible explanation. No legacy same-origin exemption.

The shell token is header-only (`X-Wizard-Shell-Token`), never cookie/query/storage/app API. Reuse navigation-only no-store bootstrap; exclude bootstrap and credentialed routes from service-worker caches. Proposed lifetime is the active server generation: owner-only secret file, atomic coordinated rotation across UX/Service/WAM, old generation invalidated, existing tabs forced to rebootstrap before further owner work. Do not log it. Inventory CLI/agent/native/service callers by route and preserve their independently authenticated scopes; they do not acquire browser-owner authority by supplying a token.

## 2. Wire format and lifecycle

Preserve the existing version-1 envelope; extend the handshake to document-bound ports as specified below before enabling sensitive operations. Proposed added requests:

```ts
type Request = {
  type: 'wizard:boundary'; version: 1; channel: string;
  op: 'service.request'; id: string; method: Method; args: object;
};
type Reply = {
  type: 'wizard:boundary'; version: 1; channel: string;
  op: 'service.reply'; id: string;
} & ({value: unknown; error?: never} | {error: Failure; value?: never});
type Failure = {
  code: ErrorCode; message: string; retryable: boolean;
  outcome?: 'not_started' | 'unknown'; operationKey?: string;
  retryAfterMs?: number;
};
```

`Method` is the closed union of the method names in sections 4–7, plus existing admitted methods. No app identity, URL, HTTP verb, headers, token or arbitrary tool name is accepted in this envelope. Validate exact keys, JSON types, UTF-8 sizes, array bounds and schemas; reject unknown fields. Use ordinary JSON values; no executable callbacks or prototype merging. Proposed limit: 64 KiB request/reply, 32 pending requests per binding. Larger content uses transfers, not giant messages.

For the initial window-message handshake the receiver checks `event.origin === 'null'` **and** `event.source === registeredFrame.contentWindow`, current channel and binding. `null` is a sandbox property, never an identity. Parent-to-opaque delivery needs `'*'` but addresses only the registered window and sends no owner secret. The app client accepts only its parent, exact expected shell origin, version/channel. Reuse source validation, but EXTEND the draft handshake before adding sensitive adapters: client creates a fresh `MessageChannel`, offers one port in its ready response, and proves receipt with a handshake challenge over that port. The shell binds the accepted port to the already registered frame/installation and server binding. Reject duplicate/stale handshakes and do not derive the principal from the frame's current URL. After handshake, requests, replies and capability events use only that document's port, never `postMessage(...,'*')` to its WindowProxy. A self-navigation between commit and load must not deliver a pending reply to the replacement document; port ownership stays with the old document. Close on pagehide/load/detach and recheck the generation before delivery. The channel is not a credential and the handshake alone returns no private data. A replacement document may at most request that app's own reviewed permissions; it cannot inherit a sensitive in-flight operation or trusted confirmation.

New ports are transferred only in validated replies with declared `portRole`; they inherit that binding and operation scope. Close pending ports, revoke tickets and deny result delivery on load/detach, update/uninstall, permission change or owner-session loss. Revalidate on each stream/upload message, not just initial creation. Background tasks already durably admitted may continue only under their explicit backend contract, without sending data to a replacement view.

Proposed common errors:

| Code | Meaning / client action |
|---|---|
| `bad_request`, `too_large` | Invalid shape or bound; fix request, do not retry unchanged |
| `unsupported_version`, `unsupported_capability` | No supported adapter; show unavailable, never use owner fetch fallback |
| `not_allowed` | Operation absent from effective permissions; no silent grant request |
| `not_found` | Resource unavailable in this scope; do not reveal other-app existence |
| `stale_binding`, `revoked` | Stop old-view work; reconnect only as a new binding |
| `conflict` | Revision mismatch; preserve draft and reconcile explicitly |
| `quota_exceeded`, `storage_unavailable` | Do not claim durable save; retain unsaved/update hold |
| `busy`, `timeout`, `cancelled` | Bound reached or transport ended; writes may have unknown outcome |
| `confirmation_required` | Needs trusted shell interaction; never infer consent from app click |
| `expired`, `range_invalid` | Resource ticket expired or invalid byte range |
| `backend_unavailable`, `backend_failed` | Sanitized failure; no upstream HTML/credentials reflected |
| `outcome_unknown` | Reconcile by durable operation key before another mutation |

No error includes secrets, raw private payloads or arbitrary backend bodies. Audit admission/result metadata and redacted identifiers, not content or ticket values.

## 3. Proposed manifest fields and admission

Place the candidate extension in `wizard.md`; exact field location and supported contract version require Miguel's approval. The following YAML is illustrative, not valid under current checkers by assumption:

```yaml
browser_contract:
  version: 1
  isolation: opaque
  operations:
    - notifications.list
    - notifications.mark_read
  state:
    schema_version: 1
    persistent_bytes: 5242880
    session_bytes: 1048576
  resources:
    - notification.thumbnail
  uploads: []
  downloads: []
  streams: []
```

An app requests named operations/resource classes, **not endpoint templates or handler code inside the manifest**. Each class's authoritative schemas, limits, consent policy and implementation live in a reviewed versioned registry. A proposed app-owned registry file may declare its *own* backend handlers, but WAM must validate and compile it with fixed upstream resolution; it cannot appoint an owner/system handler. Freeze normalized descriptors to the installed source/commit. Reject wildcards, unknown IDs, schema references outside the package and privilege increases hidden in updates. Treat changes to the implementation/schema/target/limits as permission deltas, not only changes to the operation name.

Effective permission is the intersection of requested operations, platform admission, installed-source policy, owner-approved grants and current resource/provider access.

**Enforcement is server-side as well as in the client.** A shell-only binding-creation endpoint registers the selected installation against the current owner session, source/commit and permission revision. Keep the returned binding handle in shell custody. Each adapter invocation carries that handle under the shell token; the Service/WAM registry reloads authoritative identity/grants, checks the operation descriptor and validates input/output. Never accept a principal supplied by the frame or expose binding creation to apps. Recheck before effect/result. Fixed handlers execute with app-scoped backend credentials, not a catch-all owner session; missing authentication support is an integration blocker. Browser checks are defense in depth, not the sole permission boundary. Ordinary app data operations never target `/wizard/*`, Store, global settings, grant administration, credentials or arbitrary run creation. Built-in management panels use a separate source-pinned shell-intent registry; an app may request opening a panel, never claim its authority by calling itself Store or Agents.

Teach the candidate contract in the builder/template and mirror opt-in checks in OS/WAM validators. Keep existing defaults unchanged until approval. Update offers must show increased authority and retain existing explicit denials. Browser app operations, agent-to-app grants, app-to-agent delivery and provider-slot selection remain separate authorities.

## 4. Typed app-data operations

Proposed shared facade: `WizardApp.data.call(request): Promise<Result>`.

```ts
// Example requests and exact response shapes:
data.call({operation:'notifications.list', args:{limit:20, cursor:null}})
// -> {items:[{id:string,title:string,read:boolean,revision:string}],nextCursor:string|null}

data.call({operation:'notifications.mark_read',
  args:{id:'n-17', expectedRevision:'r3'}, operationKey:'<random-uuid>'})
// -> {id:'n-17',read:true,revision:'r4',operationKey:'<same-uuid>'}

data.status({operation:'notifications.mark_read',operationKey:'<random-uuid>'})
// -> {status:'pending'|'succeeded'|'failed'|'unknown',
//     operationKey:string, result?:OperationSpecificResult,error?:Failure}
```

`data.status` is also a proposed admitted method. The registry validates operation-specific responses, including IDs, maximum items, string sizes and absence of secrets. Example reviewed mapping: `notifications.list` is a fixed GET on the resolved Notifications API, not a path selected by the frame; `mark_read` is a fixed mutation handler. Each descriptor fixes input/output schema, upstream app, timeout (default 15 s), maximum request/result bytes, read/write class, resource checks and consent requirement.

Preserve actual backend authentication through a dedicated authenticated adapter route and that app’s scoped session/CSRF custody where required. Server registry admission is mandatory; a shell-side transport is not permission to bypass it. Do not forge an Origin to bypass policy, reuse an agent bearer as an owner session, or forward owner/proxy credentials or the shell token upstream. Strip redirect authority and secret-bearing response headers; no redirect-following to a new destination. Cookie-dependent account apps need dedicated session handling, not a universal cookie relay. Keep secrets server-side; account enrollment input needs a separately reviewed trusted-shell flow.

Mutations require a random `operationKey`, persisted by the owning backend before effect. Scope it to installation + operation, bind it to a normalized argument digest, reject reuse with different arguments, and return the original outcome on identical replay. The transport request ID is not idempotency. If a backend cannot reconcile a write, expose `outcome_unknown` and block automatic retry. Cancellation is not proof of rollback. Proposed status retention: at least seven days; durable business receipts may live longer. Enforce the same authorization on status reads, without allowing another app to probe keys.

A new external send, account connection or global change requires the trusted-shell confirmation/intent flow. Bind approval to exact arguments, current source and permission revision; consume once. App requests queue an intent, not an automatically opened modal. The owner opens review through shell UI. On presentation disable confirmation activation for at least 500 ms, then require a fresh trusted activation: pointer-down and pointer-up both inside the dialog after that delay, or a fresh keyboard/accessibility activation within it. Rate-limit review requests (proposed three per minute per installation). Preserve accessibility and same-frame visual feedback: paint the interaction immediately while delaying only dangerous confirmation. Never accept an app's `confirmed:true` or synthetic event as proof.

## 5. Per-installation async storage

Proposed methods and results:

```ts
state.read({area:'persistent',key:'draft'})
// -> {exists:boolean,value?:Json,revision:string|null,schemaVersion:1}
state.write({area:'persistent',key:'draft',value:{text:'hello'},
             ifRevision:null,operationKey:'<uuid>'})
// -> {revision:string,committed:true}
state.remove({area:'persistent',key:'draft',ifRevision:'r4',operationKey:'<uuid>'})
// -> {revision:string,committed:true}
state.transaction({area:'persistent',operationKey:'<uuid>',changes:[
  {kind:'put',key:'draft',value:{text:'hello'},ifRevision:'r4'},
  {kind:'remove',key:'old-draft',ifRevision:'r2'}]})
// -> {committed:true,revisions:{draft:string,'old-draft':string}}
```

**Storage decision for this prototype:** persistent preferences, caches and local draft recovery use one shell-origin IndexedDB store on this browser profile; session state uses shell memory. This is not server-backed, cross-device, immune to eviction, or retained after browser/APK data clearing. The shell and its reviewed scripts are trusted with that store; arbitrary owner-origin scripts would compromise it, so untrusted in-document modules remain forbidden. Canonical documents and irreplaceable drafts/recordings must be acknowledged in the app backend before the UI claims portable or backed-up custody. Browser-only recovery is labelled local; preservation/upgrade tests must not imply cross-device recovery.

Shell assigns namespace from owner profile + installation + source, never a frame argument. Persistent state survives frame/app restarts; session state ends with the shell session (not a frame navigation). Neither contains credentials. Keys: 1–128 UTF-8 bytes, no filesystem or global database semantics. JSON only, 32 KiB per value, at most 16 changes and 64 KiB per transaction; larger recovery blobs use the scoped resource store. Manifest quotas are requests capped by host policy, not reserved memory.

`ifRevision:null` means create only; a present revision means exact compare-and-swap. Never-created keys have null revision; deleted keys return `exists:false` with a tombstone revision to detect stale recreation. Recreating one requires that tombstone revision, not null. All transaction preconditions validate before one atomic commit. Store the operation-key/digest/result with the commit so retries do not create false conflicts. A committed reply follows durable transaction completion and readback; define and test platform persistence limits honestly. On failure retain unsaved UI state and update holds. Browser eviction is still possible: canonical documents/original recordings stay in their existing backend archive, not solely here.

REUSE one shell-owned persistence store; no database per iframe and no synchronous localStorage polyfill. Migrate app startup to await hydration. Legacy migration is a shell-owned reviewed mapping from known keys/stores to one source/instance (Stage 1 must resolve unattributable/shared legacy keys with Miguel, and James if content ownership would change); copy, verify value/revision/hash, mark migration, keep old data for rollback. Frames cannot name arbitrary old keys. Unknown/shared keys, source switches, uninstall deletion and retention require explicit policy; do not silently adopt another publisher's state.

## 6. Scoped media, upload and download tickets

Proposed requests/results:

```ts
media.open({resourceId:'res-17',purpose:'thumbnail'|'play'|'read'})
// -> {kind:'blob',blob:Blob,mime:string,bytes:number} // small; structured clone
// or {kind:'ticket',url:string,expiresAt:string,mime:string,
//     bytes:number,methods:['GET','HEAD'],range:true}

upload.create({class:'attachment',bytes:123456,mime:'image/png',
               filename:'photo.png',operationKey:'<uuid>'})
// -> {uploadId:string,ticket:string,expiresAt:string,chunkBytes:number,
//     offset:number,portRole:'upload'} + transferred MessagePort
upload.status({uploadId:string})
// -> {offset:number,status:'open'|'committed'|'aborted'|'unknown',resourceId?:string}
upload.commit({uploadId:string,operationKey:'<uuid>',sha256:string})
// -> {resourceId:string,bytes:number,sha256:string}
upload.abort({uploadId:string})
// -> {status:'aborted'|'committed'|'unknown'}

download.request({resourceId:string,suggestedName:string})
// -> {status:'saved'|'cancelled'|'unknown',receiptId?:string}
```

The supplied resource ID is resolved against this installation's existing grants or a trusted owner selection; it is not a filesystem path, URL or other-agent selector. Validate filenames/MIME and resource purpose; never evaluate downloaded/uploaded HTML or SVG on the owner origin. Use nosniff, safe content dispositions and isolated/inert preview policy.

Content tickets are unguessable, resource/method/install-bound bearer capabilities with an absolute 60 s expiry, no sliding extension on use. Check current grant, installation/session generation and revocation on every GET/HEAD/Range and upload chunk; deny stale tickets even before expiry. A read ticket may allow repeated Range/HEAD requests for seeking within that window, so it is **not described as one-use**. A transfer admitted before expiry has a proposed five-minute maximum connection lifetime and closes sooner on revocation; large transfers resume with a fresh authorization. Renewal issues a new 60 s ticket only through the current scoped binding, at most ten renewals per minute, with an eight-hour playback session cap before fresh owner authorization. Revocation checks must interrupt long responses, not only the next Range request. It cannot enumerate resources, call owner APIs, change path scope or redirect. Serve on a dedicated non-owner content origin/listener with no owner authentication semantics; protect direct owner-origin content routes separately. Keep capability URLs out of logs/Referer/history, send no-store/no-referrer and use credentialless loads. If opaque fetch needs CORS, allow anonymous access only to ticket endpoints whose capability validation is sufficient; never credentialed global `Origin:null` access. Native download managers must obey the same scope/redirect rules, without owner cookies.

The upload ticket above is an opaque handle bound to its upload port, **not a reusable HTTP owner credential**. Proposed upload port messages: `chunk {ticket,seq,offset,bytes:ArrayBuffer,sha256}`; replies `ack {seq,offset}` or `error {seq,error}`. One outstanding chunk; maximum 1 MiB per chunk; check expiry/grants/generation every chunk. Reuse `WizUploads` offset/hash/retry machinery; query authoritative status after uncertain acknowledgement. No whole-file default cap below the existing intake system: admission depends on available storage/reserve and owner quota. On navigation close the port and pause resumable work; issue a fresh scoped ticket after reauthorization, never trust the frame's claimed offset.

`upload.commit` validates declared size/hash and final custody before announcing success; abort reports the actual outcome and cleans uncommitted temporary data. Downloads through this adapter remain trusted shell save/open actions: do not give a general navigation URL back to the app. Direct sandbox exports are only the reviewed exceptions listed in §1. Revocation denies future reads, but cannot recall already delivered bytes or undo an external save. Long playback uses the bounded renewal above; background renewal belongs to an explicit shell-owned playback lease, never a stale frame.

## 7. Bounded stream adapter

```ts
stream.open({operation:'search.overview',args:{query:'synthetic query'},cursor:null})
// -> {streamId:string,portRole:'stream',limits:{maxEventBytes:65536,
//     maxTotalBytes:8388608,maxDurationMs:300000,maxEventsPerSecond:20}}
// + transferred MessagePort
stream.cancel({streamId:string})
// -> {status:'closed'|'already_closed'}
```

Register the operation in the manifest `streams` list and reviewed registry with exact upstream, input/event schemas, direction, resume semantics and limits. App cannot choose an EventSource/WebSocket URL, headers, arbitrary run ID, peer or protocol. First prototype is server-to-app only. Bidirectional Outline audio/document operations need their own typed registry contracts and retained-original custody tests, not a wildcard socket.

Proposed port protocol: server `event {streamId,seq,cursor,event:{kind,data}}`, `end {streamId,lastSeq}`, or `error {streamId,error}`; client `ack {streamId,seq}` or `cancel {streamId}`. Sequence begins at 1; acknowledge highest contiguous sequence. Keep at most eight unacknowledged events and 512 KiB buffered; after 10 s without progress close with `timeout`. Apply aggregate per-installation limits as well as per-stream limits. Stop backend subscription on closure/revocation. Grant checks apply before each delivery; renewal/reconnect never upgrades scope. Cursor is opaque and bound to source, operation, parameters and permissions. Duplicates are possible after reconnect: consumers deduplicate by sequence/cursor; do not promise exactly-once delivery.

Reuse existing streaming backend, never expose the shell token in stream URLs. Mutating event kinds are rejected until separately specified with backend idempotency and consent. Original recording storage and background playback remain their existing owners; a bounded transcription call is not their replacement.

## 8. Native, proof and stop rules

Jan's proposed native contract: dispatch only when the receiver proves main frame, exact trusted shell origin/path, active top-document generation and reviewed command. Remove both all-frame Android Java interfaces; migrate shell synchronous reads to an async facade. Inventory Mizel, audio, Photos, Apps, shortcuts and local assist WebViews too. On Mac inspect actual script handlers/content worlds and enforce `frameInfo.isMainFrame`; a JavaScript wrapper or Android source inspection is not Mac proof.[7]

Require fail-closed older clients, no generic native method dispatcher, source-bound owner prompts, cancellation and stale-reply checks. Before creating any app frame in native mode, the shell requires a successful main-document-only protocol/version handshake; a legacy all-frame build, absent handshake or unknown capability disables app-frame creation and shows “Update Wizard to open apps safely.” No JS wrapper upgrades an old APK. Jan must define/enforce the minimum native build and prevent stale cached shells from loading apps under enforcement; server token checks alone cannot remove old Java interfaces. Standalone browsers without native bridges follow the browser-only path, not an Android compatibility fallback.

Include Android `onPermissionRequest`, file chooser, download listener, navigation interception, intents and localhost/recovery bridges; Mac equivalents and every content world need the same audit. Verify frame identity or reject the operation and offer only a deliberate trusted-shell action. Removing one JS interface is insufficient.

Prototype acceptance: valid app works; unknown method/schema, forged source, duplicate publisher ID, stale load, revoked permission, resource substitution, ticket replay beyond scope, hostile MIME, oversized stream, lost write response, storage quota and upstream redirect all fail safely. Read back server admission logs: a CORS exception is not proof that a write was refused. Repeat r5's shell-positive and hostile-negative tests at exact heads; its 45 checks do not establish native or packaged-app acceptance.[9]

Before enablement require actual packaged auth/session, fresh/alongside install and rollback, app feature parity, real APK/Mac hostile-child and positive-device workflows, and inspected two-skin screenshots with live Appearance v1 changes/dark standalone fallback. Keep default-off/draft; synthetic fixtures only; Forum for heavy Linux/Android runs, Thales for Mac. No owner-box changes, private-content tests, publication or third-party messages under this proposal.

## Sources

[2] https://github.com/humanitylabs-org/wizard-ux/pull/327 — UX boundary draft
[3] https://github.com/humanitylabs-org/wizard-agent-service/pull/100 — Service boundary draft
[4] https://github.com/humanitylabs-org/wizard-app-manager/pull/168 — WAM boundary draft
[7] ./APP-CENSUS.md — Static app census and effort bounds
[9] ./brief-sources/r5-receipt.json — Forum r5 synthetic receipt, local read-only copy
