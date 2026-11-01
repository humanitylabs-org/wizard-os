# Browser trust, card 1: decisions, admission contract and storage ownership

**Spec for review · draft · nothing adopted until reviewed.** This is the contract record for [card 1 (#384)](https://github.com/humanitylabs-org/wizard-os/issues/384). It sits on the review brief ([#379](https://github.com/humanitylabs-org/wizard-os/pull/379)). Oscar wrote it for Miguel. Oscar cannot approve his own proposal: Miguel reviews the contract and the storage parts, Jan reviews anything that touches native, and James signs off the platform permission decisions listed in §1. `WIZARD_BROWSER_BOUNDARY` stays default-off. Nothing here enables, merges or releases anything.

Implementation drafts that follow this spec (all draft, all default-off, stacked on the existing prototype rather than a rebuild):

| Repo | Draft | Stacked on |
|---|---|---|
| App Manager | `feature/browser-trust-production-admission` | WAM #168 `247cc12a` |
| Agent Service | `feature/browser-trust-production-admission` | Service #303 `51008d11` (on #100) |
| Wizard UX | `feature/browser-trust-production-admission` | UX #822 `6c8903fa` (on #327) |

The exact heads, commands and results are in the PR bodies and in the #384 evidence comment.

## 1. Decision register for the #379 questions

No answer here counts as approval just because nobody objected. Each row says who decides and where the answer is.

| # | Question (brief) | Recorded answer | Decider | Status |
|---|---|---|---|---|
| 1 | Source-qualified install identity and operation admission, including the duplicate `profiles` publishers | **Identity = source + app id.** The duplicate publisher `oscarhenrycollins/profiles` is retired, so `humanitylabs-org/profiles` is the only one. Retiring it keeps that source's identity and its legacy data until a reviewed migration is done: no data loss, and no automatic adoption by the other source. Operations are admitted per installation and source, never by catalogue id alone. | Miguel | **Miguel's answer** ([comment](https://github.com/humanitylabs-org/wizard-os/pull/379#issuecomment-6555792526); [reaffirmed after correction](https://github.com/humanitylabs-org/wizard-os/pull/379#issuecomment-6559446930)), **pending Miguel's review of this spec PR** |
| 2 | Which listeners need auth adapters or isolated origins; how unattributable old storage is handled | **ChatGPT, Claude, Cloudflare, Troubleshooter, Files and the Hermes dashboard** each get **distinct-listener handling**: an authenticated listener adapter or a reviewed separate-origin exception with equivalent isolation proof. Per-app origins are no longer the default (see §2). Legacy **drafts are migrated, never dropped**. Only true caches may be dropped. Unattributable keys stay where they are until reviewed (§5). | Miguel | **Miguel's answer** (same links), **pending Miguel's review of this spec PR**. The wording changed from "own origin" to "distinct-listener handling" because of [the correction](https://github.com/humanitylabs-org/wizard-os/pull/379#issuecomment-6559446930). Miguel should confirm that. |
| 3 | Who signs off permission increases, provider-selection changes and rollback state preservation | **James** signs off platform permission increases: new operation ids in the registry and new capability classes. The **box owner** approves each box through the Store update prompt. **Oscar** owns proving that rollback preserves state. | Miguel | **Miguel's answer**, **pending Miguel's review**. *Still open:* Miguel did not answer provider-selection changes separately. This spec treats a provider change as a permission delta: refused until the owner re-grants (§3). Miguel needs to confirm or change that. |
| 4 | Can every Android/Mac receiver enforce trusted-main-document identity without an all-frame fallback; minimum client versions | — | Jan | **OPEN** until Jan answers ([card 4, #387](https://github.com/humanitylabs-org/wizard-os/issues/387)) |
| 5 | Which native capture, recovery, download and background workflows the prototype must cover first | — | Jan | **OPEN** until Jan answers (#387) |

**Platform decisions that need James, recorded separately.** None of these is requested or implied by this card: (a) turning `WIZARD_BROWSER_BOUNDARY` on anywhere; (b) quarantining incompatible apps; (c) every addition to the reviewed operation registry (§4), which counts as a platform permission increase under Q3; (d) any change of default app or provider slot. James already authorized queuing the migration work, so that does not need asking again.

## 2. Architecture: comparison and disposition

| Option | Position | Disposition |
|---|---|---|
| Opaque sandboxed app frames + typed shell adapters (brief) | Target. Miguel's position after [the correction](https://github.com/humanitylabs-org/wizard-os/pull/379#issuecomment-6559446930); [Archimedes treats per-app origins as withdrawn](https://github.com/humanitylabs-org/wizard-os/pull/379#issuecomment-6560039763) | **Miguel's position, pending his review of this spec PR.** Separate origins are only a reviewed exception: File Browser, the Hermes dashboard, and any package that genuinely can't be sealed, each with equivalent isolation proof. |
| Per-app origins by default (Oscar's [earlier comment](https://github.com/humanitylabs-org/wizard-os/pull/379#issuecomment-6555792526)) | **Withdrawn** | Not adopted. No routing spike was run under this card. Reasons below. |

**Why per-app origins were withdrawn, so no routing spike was spent on them:**

1. **Cookies are not port-isolated.** A compromised app on `host:portA` can read and overwrite the cookies of the shell and of other apps on the same host, for example Messenger and the Cloudflare session/CSRF cookies.
2. **Different ports on one host are same-site.** SameSite therefore does not separate apps, and Chrome Site Isolation is per site, so process isolation between apps stays weak.
3. **Backend hardening is still required.** Every listener still has to stop treating network-owner identity as authority. That is the same work the brief already budgets.
4. **Distinct registrable domains would fix 1–2, but there are none to use.** Tailscale/MagicDNS boxes and the Mac VM guest don't have them. Sibling subdomains under one `ts.net` name stay same-site.

The bounded spike in card item 2 (Notifications, Files uploads/Range, Messenger cookie/CSRF under per-app origins) was therefore **not run**. That is a documented choice that follows the withdrawal, not a result. The opaque-adapter path is measured on the real Notifications slice instead (§6).

## 3. Principals and admission (implemented in the drafts)

**Principals stay separate.**

- **Browser owner (shell):** the shell document. It holds `X-Wizard-Shell-Token` (#327, #100, #168) and is the only principal that can create a binding or call an adapter.
- **App frame:** an opaque sandboxed document. It never holds the token or an owner credential. It reaches data only through the shell's document port, and the shell binds it to an installation.
- **Agent:** Hermes or app agents on their own credentials. They are refused on the adapter routes.
- **Peer app or network caller:** a request carrying only network identity. It is refused because it has no shell possession.

**WAM is the single source of install facts.** When the boundary is on, WAM projects these facts into `apps.json` as `browser`. It never trusts a frame, URL or request body for them.

| Fact | Definition |
|---|---|
| `installation_id` | `inst-` + digest of (store, app id, Runtipi row serial, row creation time). A reinstall is a new installation. |
| `source_id` | `<store source>:<owner>/<repo>` recorded at install. `null` (unattributed) admits nothing. |
| `commit` | The installed commit. |
| `contract` | The `browser_contract` from the **installed** `wizard.md`, normalized. Unknown fields, unknown ids and wildcards are rejected. |
| `granted` | The owner's browser grants for **this installation and this source** that the installed contract also declares. |
| `permission_revision` | Digest of the contract and the effective grants. Any change revokes open bindings. |
| `upstream` | `http://<box internal ip>:<installed port>`, recorded by WAM. Frames cannot name it. |

Browser grants live in `<WIZARD_OS_HOME>/browser-grants.json` (mode 0600). They are separate from WAM's network/agent grants. The owner manages them with `wam browser-grants list|grant|revoke <app> --operation <id>`. A grant can only cover operations the installed contract declares, and it is bound to the current installation and source.

**Checks happen four times.** The Service re-reads the WAM facts when a binding is created, at every admission, immediately before an upstream effect, and before a result is delivered. A result whose grant was revoked mid-call is withheld; the durable outcome receipt keeps the truth.

| Lifecycle event | Server outcome |
|---|---|
| Manifest declares the operation, no owner grant | `not_allowed` (the binding names an installation; it grants nothing) |
| Grant revoked | Open binding → `revoked`; new binding → `not_allowed` for that operation |
| Update (new commit) | Open binding → `revoked`; same-source grants carry over, but only for operations the new contract still declares. A newly declared operation needs a new grant (later via the Store update prompt). |
| Uninstall | `not_allowed`. The grant record stays inert. |
| Reinstall | New installation id. No grants and no outcome receipts from the old one carry over. |
| Source change, same app id | Open binding → `revoked`. The new source inherits no grant and no state namespace. The old source's records are kept, inert. |
| Provider change (no longer the slot's provider) | Provider-bound operations → `not_allowed` |
| Two installed entries with one id (both `profiles`) | WAM refuses to write the registry. If a hostile or corrupt registry has duplicates anyway, the Service refuses the binding. |
| Staged side-by-side install, unattributed legacy install, unreadable registry or grants | Nothing admitted |
| Forged principal fields in a request (`appId`, `installationId`, `sourceId`, `url`) | `bad_request`; exact-key schemas |

**Leases.** A binding lasts at most one hour or 4096 requests (prototype values kept). It is revoked on frame load or detach. There is no background lease or revocation bus; the next admission re-reads WAM state.

**Not changed by this card, and left as open items:** shell-token bootstrap and rotation, and service-worker cache exclusion (#327 behaviour kept as is); per-app direct listener protection. The Notifications listener `/notifications/api/*` is still reachable on the gateway by network identity, and that belongs to [card 3, #386](https://github.com/humanitylabs-org/wizard-os/issues/386). The browser run shows only that a CORS-less cross-origin JSON write from an opaque frame is blocked by preflight. That is not server-side proof.

## 4. Reviewed operation registry v1

The operation ids live in two places that must match: WAM `wam/browser_admission.py` `OPERATIONS` and Service `server/browser-operations.mjs` `OPERATIONS`. Adding an id is a platform permission increase (Q3, James).

| Id | Class | Scope | Upstream (fixed) | Arguments (exact keys) | Result (exact keys) |
|---|---|---|---|---|---|
| `notifications.list` | read | self, current `notifications` slot provider | `GET /notifications/api/items?view=inbox&limit=N` | `{limit: 1..50, cursor: null}`. A non-null cursor returns `unsupported_capability`. | `{items:[{id,title≤200,message≤2000,time,read,revision}], nextCursor:null}` |
| `notifications.mark_read` | write | same | `POST /notifications/api/mark {ids:[id],read:true}` | `{id, expectedRevision}` plus top-level `operationKey` (UUID) | `{id, read:true, revision, operationKey}` |
| `data.status` | status | same as the target operation | none (receipt store, then readback) | `{operation:"notifications.mark_read", operationKey}` | `{status: succeeded\|failed\|pending\|unknown, operationKey, result?, error?}` |
| `state.local` | state | self | none (shell IndexedDB, prototype) | `{}` | namespace + quota |

`revision` = `r-` + digest of (id, read, flag, archived). The Notifications backend has no compare-and-swap. The adapter checks `expectedRevision` against a fresh read. The remaining race with a direct agent write is harmless for a monotonic `read=true`. Any future non-monotonic write needs upstream CAS.

**Write outcome semantics.** The receipt is persisted before the effect: fsynced, renamed, then read back. It is scoped to installation + operation + key and bound to an argument digest and the source. The flow:

1. Pre-read, then `conflict` on a stale revision.
2. Durable `pending` receipt.
3. Recheck admission.
4. Upstream effect.
5. Readback.
6. `succeeded` receipt, then recheck, then result.

Failure handling:

- A lost reply or a failed readback returns `outcome_unknown` and claims nothing.
- A retry with the same key reconciles by readback without a second effect.
- Key reuse with different arguments returns `conflict`.
- Receipt store full (256 per installation, 4096 total, 1 MiB) returns `quota_exceeded` before any effect.
- Unwritable receipt storage returns `storage_unavailable` before any effect.
- Completed receipts are kept 7 days. A retry after eviction conflicts and does not reapply.

**HTTP.** The routes are `POST /wizard/v1/browser-adapters/{bindings,call,revoke}`. They exist only when the boundary is on and the Service is started with `WIZARD_BROWSER_ADAPTERS=wam`. They require shell possession plus the owner principal. Status codes: 400 bad request; 403 authority (`not_allowed`, `revoked`, `stale_binding`, `replay`); 404; 409 (`conflict`, `outcome_unknown`); 429 busy; 501 unsupported; 502/503/504 backend; 507 quota. Error bodies carry only `error`, `retryable`, `outcome`, `operationKey`. This is an additive Agent Service route; once this is reviewed, `spec/AGENT_SERVICE_API.md` gets the same rows in the round that lands the Service PR.

## 5. Storage scope and legacy ownership

Each item is marked **decided-in-draft** (implemented as shown, pending Miguel's review) or **OPEN**.

| Topic | Position | Status |
|---|---|---|
| Custody of `state.local` | One shell-owned IndexedDB store on this browser profile. Not cross-device, not a backup, can be evicted. Canonical documents and irreplaceable drafts must be acknowledged by the app backend before the UI claims durable custody. | decided-in-draft (prototype) |
| Notifications custody | Read/flag/archive marks are canonical in the Notifications backend (`/data/inbox.json`). The view keeps no browser state, and the shipped Notifications web view has no localStorage/IndexedDB use, so there is **no legacy key to migrate**. | decided-in-draft |
| Namespace | `[local-owner-profile, installation_id, source_id]`. A frame can never name it. | decided-in-draft |
| Source switch | New namespace. The old namespace and grants are kept, inert; switching back to the same source on the same installation restores them. No automatic copying across sources. | decided-in-draft; Miguel to confirm "switch back restores" |
| Duplicate `profiles` legacy data (`wos.skin`, local `SYS_KEY`, its server data) | Retiring `oscarhenrycollins/profiles` keeps its source identity and data until a reviewed migration. Neither source adopts the other's state automatically. Who owns the shared `wos.skin` is not settled. | **OPEN** (owner: Miguel; James if content ownership changes) |
| Unknown/shared old keys | Not adopted and not deleted; bytes kept. A shell-owned allowlisted mapping per source is required before any copy. | decided-in-draft (no adoption); mapping per app **OPEN** |
| Session/cache areas, delete/remove, enumeration, blobs | Not provided; they return `unsupported_capability`. Each is added only when a census row needs it, with its own review. | decided-in-draft |
| Transaction limits | Browser state: 32 KiB/value, 16 changes and 64 KiB per transaction, ≤5 MiB quota, newest 256 receipts within 512 KiB. Service write receipts: 256/installation, 4096 total, 1 MiB, 7 days. | decided-in-draft; numbers open to measurement |
| Receipt eviction | An evicted retry conflicts; there is no blind re-apply. | decided-in-draft |
| Uninstall deletion and retention | Nothing is deleted on uninstall: browser namespaces, grants and receipts stay inert. | **OPEN** (owner: Miguel) |
| Rollback | Legacy bytes are preserved and rollback restores them. Full IndexedDB rollback is not provided. Oscar must prove rollback preserves state at package level (Q3). | **OPEN**: package-level proof belongs to card 6 |
| Inputs from other inventories | Listener/download (card 3), client version (card 4) and generated-module (card 5) storage rows | **OPEN**: those cards own them |

## 6. What this card proves and what it does not

**Proven on exact draft heads (local runs, details in the PR bodies):**

- The real WAM registry writer and grant CLI produce the install/grant state.
- The Service admits Notifications list and mark-read only from that state.
- Durable write and readback work against the real Notifications front, with a stub ntfy upstream.
- The server refuses every lifecycle and forgery case in §3.
- Lost reply, retry, conflict, quota, storage and eviction cases fail safe.
- Real Chromium covers the shell, an opaque frame, revocation through WAM, and screenshots on two skins plus a dark standalone page.

**Not proven:**

- Forum `/srv/work` was not reachable from this runtime, so all runs are local.
- nginx was replaced by a Node stand-in that applies the same document template.
- The real Notifications UI migration (card 2) was not done; a synthetic test view was used.
- Real Runtipi install, update and uninstall on a box.
- Store update prompts.
- Cross-app operations and cursors.
- Direct listener protection (card 3).
- Native Android/Mac and phone (card 4).
- Packaged fresh/alongside install and rollback (card 6).
