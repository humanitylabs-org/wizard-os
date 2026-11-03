# App reads of declared agent notebooks

**Status: proposed; security/privacy contract review required before implementation merges or activation.** Companion drafts: [Agent Service #321](https://github.com/humanitylabs-org/wizard-agent-service/pull/321), [Notes transition #7](https://github.com/humanitylabs-org/notes-local/pull/7). The latter is containment, not completed feature parity.

This extends the read-only resource part of [agent state](AGENT_STATE.md) and reuses [app permissions](PERMISSIONS.md) layer 2. It does not turn an ordinary app connection into authority over agent state, reverse sealed private agents (DECISIONS #59), or change agent-to-agent grants. Source selection, presentation, Markdown navigation and explicit copying belong in each consuming app, never in the Agent Service core.

## Two checks on every read

1. **Who calls:** an installed app's ordinary owner-approved connection to Agent Service presents `X-Wizard-Grant`. The provider hashes it against current App Manager-managed `incoming` grant rows. Missing, malformed, revoked or ambiguous identity fails closed even during non-enforcing legacy app-network mode. No owner cookie, Origin, client-supplied app name or gateway agent label substitutes for the key. There is no new notebook token store.
2. **Which resource:** the owner has explicitly approved an `app-notebook` grant for that app and that agent, with read-only scope. No default source discovery, wildcard source grant, implicit main-agent access or app connection grants all notebooks.

The proposed Service administrative API reuses its existing owner-authenticated grant ledger (`.agent-grants.json`):

```json
{"kind":"app-notebook","reader":"app:<installed-app-id>","source":"<agent-id>","scope":"read"}
```

- Create: `POST /wizard/v1/agent-grants` with the typed body above.
- List: `GET /wizard/v1/agent-grants?reader=app:<app-id>`.
- Revoke: `DELETE /wizard/v1/agent-grants/<grant-id>`.

Only an authenticated owner creates/deletes these records. App identity cannot manage grants. The `app:` reader namespace and `app-notebook` kind prevent an app resource grant from being interpreted as an agent-to-agent grant. The App Manager remains authoritative for connection/key lifecycle; the Service's existing resource ledger is authoritative for the selected agent resources. A future Connections UI calls the same APIs rather than persisting another copy. This UI does not yet exist.

## Source boundary

Safe eligible sources are standard, visible, non-recovery agents with an explicit `notes_dir`. The eligibility check runs on every request **before** resolving any state-home or opening a file. No fallback folder or implicit host-profile notebook. A guessed excluded ID behaves exactly like a missing ID. Private, siloed, hidden and recovery agents stay excluded, including forged or stale stored grants. An ordinary owner session may inspect its private Chats; it does not confer that authority on an app.

No private-source exception is proposed. Any future owner-authorized exception needs a separate explicit private-data/privacy decision, must not be implied by an app connection, and must preserve [connector private-data routing](CONNECTORS.md). Notebook data and its derivatives must never silently be forwarded to a public model.

## Generic read-only API

The box-local resource routes are:

- `GET /wizard/v1/agent-notebooks` → `{sources:[{id,label,privacy,appearance?}]}`.
- `GET /wizard/v1/agent-notebooks/<agent-id>` → `{source,entries,truncated}`.
- `GET /wizard/v1/agent-notebooks/<agent-id>/read?path=...` → `{source,path,text}`.
- `GET /wizard/v1/agent-notebooks/<agent-id>/search?q=...` → `{source,notes,truncated}`.

Every response is no-store. Non-read methods refuse. Reuse the Service's existing bounded text/path/link/secret-name gates, never raw database/home mounts. Neither owner endpoints nor unrelated app/agent resources become reachable with an app key. Public phone ingress does not accept the backend app credential.

## Browser/app transition gate

App keys stay exclusively in the app backend. Before forwarding a notebook request, an app must prove an owner-authenticated browser handoff from the installed shell. Host/Origin allowlists, network locality and an app's unrelated MCP connection are not owner authentication. Do not build an unauthenticated credential-forwarding proxy. Agent/app calls to a consuming app must not inherit the app's notebook grants automatically.

The retired unscoped `/wizard/v1/agent-notes...` route returns 410 with no notebook data. No compatibility switch preserves the former every-agent leak. Release the consuming-app update and Service change together only after synthetic caller-isolation/revocation/path tests and phone/two-skin notebook parity pass. Containment alone may hide notebooks and therefore is **not** authorization to cut a running box over or drop a live capability.

## Acceptance / decision needed

The proposal needs security/privacy contract approval before merge, including whether to keep the existing Service resource ledger as proposed or migrate resource grants to App Manager in a separately reviewed migration. It does not claim the current App Manager UI understands `app-notebook`.

Required proofs: normal key grant vs explicit source authority; forged identity; per-app source isolation; immediate independent connection/source revocation; excluded sources never reach filesystem readers; bounded safe reads and no writes; source privacy changes invalidate stale grants; owner vs agent browser handoff; no browser key disclosure; no private-to-public model fallback; old/new app compatibility. Fixtures must be synthetic, never real private agent homes or notebooks.
