# Browser trust: Files (cards 2/3, #385/#386) — decided in draft

Draft record. Default-off under `WIZARD_BROWSER_BOUNDARY`; nothing here enables the boundary, changes a release default or touches a box.

## 1. Decisions

| # | Decision | Who | Where |
|---|---|---|---|
| F1 | Upstream File Browser is the first **reviewed separate-origin exception** (README brief §1): it runs on its own https origin and opens **only as its own tab**, never in a Wizard window. Equivalent isolation proof is still required before enablement. | Miguel, 2 Nov 2026 | [#385 comment](https://github.com/humanitylabs-org/wizard-os/issues/385#issuecomment-6571935945) |
| F2 | Making the first-party `wizard-files` view the **default** Files app is a proposal awaiting James. Oscar migrates `wizard-files` to the opaque boundary in draft either way; release defaults do not change without James's yes. | pending @jdefleur / @defleur-agents | same comment |

## 2. File Browser: own-tab exception (F1)

- **WAM** owns the fact. `browser_contract: {version: 1, isolation: own-tab}` (nothing else may be declared) is admitted only for the reviewed (app id, source) pair `('files', 'oscarhenrycollins/files')`; any other app declaring it is `invalid_contract`, so no app can opt itself out of the opaque frame. An own-tab app gets no bindings, grants or credential. With the boundary on its view is its own https origin (own port), never a gateway path, and WAM writes `WIZARD_BROWSER_BOUNDARY=1` + `WIZARD_OWN_HOSTS=<its authority>` only if its installed compose declares `WIZARD_OWN_HOSTS`.
- **Agent Service** flags the app `own_tab: true` in the apps snapshot only when WAM state says `isolation: own-tab` and its view is an https URL.
- **Shell** never frames an `own_tab` app: it checks the address is a different https origin (no userinfo/fragment) and opens it with `noopener,noreferrer`; nothing crosses into the tab (no token, frame or message channel). Flag off = today's frame.
- **App front** (files `2.63.23-wizard4`, `mcp/front.py`), before File Browser sees a request: refuses frame/embed requests, opaque or foreign `Origin`, cross-site and same-site requests other than a plain top-level GET navigation, and any Host that is not Files' own address (an old `/files/` route on the Wizard origin). Every reply carries `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'`, CORP/COOP same-origin. The card-3 owner-login gate is unchanged.
- No shell token, Agent Service route or relay is reachable from that origin.

## 3. `wizard-files` in the opaque frame (F2 draft)

Manifest (`wizard.md`, 0.1.5):

```yaml
browser_contract:
  version: 1
  isolation: opaque
  operations: [files.list, files.index, files.thumbnail, files.content, files.upload]
  state: {schema_version: 1, persistent_bytes: 65536}
```

Each id is its own owner grant (WAM `browser-grants`); listing never implies bytes and bytes never imply uploads. The Agent Service calls one constant path on the installation's WAM-recorded upstream with its WAM listener credential — not a relay: exact argument and result schemas, `redirect: manual`, no owner credentials, cookies, shell token or upstream bodies passed through.

| Operation | Frame call | Upstream | Result |
|---|---|---|---|
| `files.list` | `data.call {folder, scope: personal\|app}` | `GET /api/files` | rows `{name,path,is_dir,size,mtime,type,resource}`, `upload_allowed`, `app_data_prefixes` |
| `files.index` | `data.call {q,type,scope,sender,offset,limit<=300,snapshot}` | `GET /api/index` | same paging contract as the app's own index |
| `files.thumbnail` | `data.call {resourceId}` | `GET /api/files/thumbnail` | `{mime:'image/jpeg', bytes<=512 KiB, data}`; 240/min per binding |
| `files.content` | `media.open {resourceId, purpose: read\|play}` | `HEAD`/Range `GET /api/files/content` | 60 s ticket on the content origin (§6); 10/min, 8 h cap |
| `files.upload` | `WizardApp.upload.create\|chunk\|status\|commit\|abort` | Service's own resumable store into the owner-files root | see §4 |

- `resource` ids (`fr_…`) are minted per binding for files the app's own listing returned; never a path or URL; they die with the binding. Folder arguments are re-validated (no `..`, dot-names, `:`, `\`, control characters).
- Content tickets stream (never hold the file): every request re-resolves the installation's current upstream + credential and asks for exactly the requested range; a changed file (ETag or size) ends the ticket with 410. Inline only for a closed MIME list (images, mp4/webm/mov, common audio, text/plain, pdf); anything else is an attachment with `CSP: sandbox`, `nosniff`, `no-store`.

## 4. Upload port and downloads (deviations from ADAPTER-SKETCH §6)

- **Ticket stays in the shell.** `upload.create` returns `{uploadId, offset, bytes, status, chunkBytes}` to the frame; the upload ticket is kept by the shell, which forwards each chunk (`ArrayBuffer`, ≤ 1 MiB, one outstanding per upload) with `Upload-Offset` and its sha256 to `POST /wizard/v1/browser-adapters/upload-chunk` (owner + shell token). Stronger than the sketch's ticket-in-frame port; no MessagePort is transferred.
- **Per chunk** the Service checks: ticket, the same live binding and document generation, the installation unchanged, `files.upload` still granted — before the bytes are written — then exact offset (409 `offset_mismatch` with the authoritative offset) and chunk hash (422 `integrity`).
- **Destination policy, server-side:** the app's own listing must say the folder takes uploads and is not app data; the owner-files root confines the path. `commit {uploadId, sha256, operationKey}` checks the whole-file hash before placing, then reads the new file back through the app (listed, committed size). `abort` reports the real outcome (`aborted` / `committed`). Uploads of one installation are invisible to others.
- **Downloads:** `download.request {resourceId, action: save|open}` (sketch had `suggestedName`); the shell itself saves/opens a `files.content` ticket, only during the owner's own user activation, with no referrer. The frame never receives a navigable URL.

## 5. Listener gate (card 3)

With `WIZARD_BROWSER_BOUNDARY=1` the `wizard-files` listener refuses to start without a 64-hex `WIZARD_APP_CREDENTIAL` (from WAM). Its `/api/*` answers only a box-local request with no browser headers (`Origin`, `Cookie`, `Referer`, `Sec-Fetch-Site/Dest/User`) and no network identity (`Tailscale-User-*`, `X-Forwarded-*`, `Forwarded`, `cf-*`) that carries exactly that credential. Static page files and `/health` (version only) stay public; browser requests to `/mcp` are refused; the agent's `/mcp` path is unchanged. Flag off: unchanged.

## 6. Evidence and still open

- Real Chromium, local (no Forum `/srv/work` from here): `wizard-ux tools/qa-browser-files-own-tab.cjs` and `tools/qa-browser-wizard-files.cjs` with `QA_BASELINE=1` before shots; results on #385/#386.
- Open: James's default decision (F2); File Browser isolation proof on a real box before enablement; the opaque Files view has no skin-layer mirroring (tokens only) by design.
