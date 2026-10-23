# Skins on Nostr v1 (skin store MVP)

**Status:** approved by James, 23 Oct 2026 ([DECISIONS](../docs/DECISIONS.md) #86–#90). Archimedes builds.

Owners make skins with their agent, keep several of them, publish one with their Wizard ID, and get other people's skins from the Store in Settings > Look. No skin ever goes through a GitHub repo. A published skin is one signed Nostr event; its files live on Blossom servers, addressed by SHA-256.

## Words

- **Default:** the built-in look. Nebula, plus the built-ins still in the shell until they move to the Store (#88). Not editable.
- **My skins:** the owner's own skins, one folder each in Files. One of them (or none) is active and is layered on top of the Default.
- **Store:** skins other people published, read from relays through the Agent Service.

## On the box (Files)

```
Skins/
  active                 # one line: the folder name of the active skin; empty or missing = none
  My skin/               # the existing folder, unchanged; active by default
    skin.css
    skin.js              # optional, local only, device-approved by exact SHA-256 (unchanged)
    skin.json            # optional metadata, written by the service
  Nebula Remix/
    skin.css
    skin.json
```

- A skin's **id** is its folder name (1–64 chars, no `/`, `\`, leading `.`, control characters).
- `skin.json`: `{ "name", "summary", "base": "nebula", "forked_from": { "a", "event_id", "author" } | null, "published": { "a", "event_id", "created_at", "slug" } | null }`. Every field is optional; a missing file reads as `{ name: <folder name> }`.
- `GET /wizard/v1/my-skin` and `/wizard/v1/my-skin/script` keep their contract and serve the **active** skin. With no active skin they serve an empty sheet. The shell's My skin layer needs no change.
- The 64 KB cap and the existing sanitiser apply to every skin, local or from the Store.

## Agent Service API (additive, `/wizard/v1/skins…`)

Owner-only, same-origin, like `/my-skin`. Errors are `{ error: "<code>", detail? }`.

| Method & path | Body | Returns |
|---|---|---|
| `GET /skins` | | `{ active: id\|null, skins: [{ id, name, summary, base, bytes, empty, has_script, forked_from, published }] }` |
| `PUT /skins/active` | `{ id: string\|null }` | the `GET /skins` shape |
| `POST /skins` | `{ name, css? }` | `{ id }` new folder (name de-duplicated with " 2", " 3"…). Used for "New skin". |
| `GET /skins/store` | `?refresh=1` optional, `?authors=<hex,…>` optional | `{ items: [StoreItem], featured: [a], fetched_at, relays: [{ url, ok }] }` |
| `GET /skins/store/blob/<sha256>` | | the verified bytes (from the box cache), correct `Content-Type`, `Cache-Control: immutable` |
| `POST /skins/store/add` | `{ a }` | `{ id }`: copies the verified bundle into a new folder, writes `forked_from`, makes it active |
| `POST /skins/store/report` | `{ a, reason }` | `{ ok: true }` (NIP-56 kind 1984, signed by the box's upload key, sent to the AI Wizards relay) |
| `POST /skins/<id>/pack` | `{ preview_webp_b64?, slug?, summary? }` | `{ unsigned: <event template without pubkey/id/sig>, slug }` after uploading every file to Blossom |
| `POST /skins/<id>/publish` | `{ event }` (signed by the owner) | `{ event_id, a, relays: [{ url, ok, message }] }` after verifying signature, kind, tags and that every file hash is on a Blossom server; writes `published` to `skin.json` |

`StoreItem`: `{ a, event_id, pubkey, npub, author: { name, picture } | null, name, summary, slug, version, published_at, updated_at, base, ux, files: [{ name, sha256, mime, size }], preview: "/wizard/v1/skins/store/blob/<sha>" | null, forked_from: a | null, forks: n, featured: bool }`.

The WebView never talks to relays or Blossom. The Agent Service fetches, verifies and caches; the page reads only `/wizard/v1/skins/…`.

## The skin event (kind 30117)

Addressable (`d` = slug), so republishing replaces the previous version on relays. Kind 30117 is unassigned in the NIPs kinds table (checked Aug 2026 snapshot).

| Tag | Required | Meaning |
|---|---|---|
| `d` | yes | slug, `[a-z0-9-]{1,48}` |
| `t` | yes | `wizard-skin` |
| `name` | yes | display name, ≤ 48 chars |
| `summary` | no | one line, ≤ 140 chars |
| `published_at` | yes | unix seconds of the first publish; never changes on update |
| `version` | yes | integer, +1 per publish |
| `base` | yes | `nebula` (schema 1 allows only this) |
| `ux` | yes | minimum skin API version the CSS needs; `1` today |
| `file` | yes, ≥ 1 | `["file", <name>, <sha256 hex>, <mime>, <bytes>]`. Names in schema 1: `skin.css` (required, `text/css`, ≤ 64 KB), `preview.webp` (optional, `image/webp`, ≤ 512 KB), `composition.json` (optional, `application/json`, ≤ 8 KB) |
| `server` | yes, ≥ 1 | Blossom base URL(s) holding the files |
| `a` + marker `fork` | no | `["a", "30117:<parent pubkey>:<parent d>", <relay hint>, "fork"]` |
| `p` | with `a` | parent author |
| `alt` | yes | `Wizard OS skin: <name>` (NIP-31) |

`content` is `{"schema":1}`. Clients ignore events with any other schema, unknown `base`, `ux` above what they support, missing `skin.css`, or a file over its cap.

```json
{
  "kind": 30117,
  "pubkey": "<owner hex>",
  "created_at": 1761220000,
  "tags": [
    ["d", "nebula-remix"], ["t", "wizard-skin"], ["name", "Nebula Remix"],
    ["summary", "Warmer surfaces and a tighter composer."],
    ["published_at", "1760000000"], ["version", "3"], ["base", "nebula"], ["ux", "1"],
    ["file", "skin.css", "<sha256>", "text/css", "41203"],
    ["file", "preview.webp", "<sha256>", "image/webp", "38811"],
    ["server", "https://store.wizard001.com/blossom"],
    ["a", "30117:<parent hex>:nebula-warm", "wss://store.wizard001.com/relay", "fork"], ["p", "<parent hex>"],
    ["alt", "Wizard OS skin: Nebula Remix"]
  ],
  "content": "{\"schema\":1}",
  "id": "<sha256 of the NIP-01 serialisation>",
  "sig": "<BIP-340>"
}
```

**Store skins are CSS only** (#88). `skin.js` never leaves the box: pack refuses nothing but simply doesn't include it, and "Add to my skins" never writes one.

## Curation (NIP-51)

The **AI Wizards curator key** (pubkey `9f6deaf1a019f9393e3a044f873e508b1ac6cfa093db77ba21e70c811ee1f127`; same identity #83's signed lists should use) publishes two kind `30004` sets:

- `d = wizard-skins-featured`: `a` tags of featured skins, in order.
- `d = wizard-skins-blocked`: `a` tags (or `p` tags for a whole author) hidden in every client.

The curator pubkey is pinned in the Agent Service config (`WIZARD_SKINS_CURATOR`, with a built-in default). Reports are kind `1984` events addressed to the listing (`a`, `p`, `["report", "other"]`); only the curator reads them.

Store order: featured (in set order), then by `updated_at` descending. Each card shows name, author name and photo, npub head…tail, first published, last updated, and fork count (listings whose `fork` tag points at it).

## Relays and Blossom

- **REUSE/EXTEND, not NEW:** our relay and Blossom are the existing Wizard Store service (`zapstore-pilot`), extended for skins. It keeps the app catalog publisher-only and opens kinds 0, 5 (own events), 1984, 30004 (`d = wizard-skins-*`) and 30117 (`t = wizard-skin`) to any signer, with per-key caps.
- Default relays: `wss://store.wizard001.com/relay` (ours, the archive), `wss://nos.lol`, `wss://relay.damus.io`. Config: `WIZARD_SKINS_RELAYS`. `relay.aiwizards.com` / `blossom.aiwizards.com` may later point at the same service.
- Blossom: `https://store.wizard001.com/blossom` (ours). Accepts `text/css`, `image/webp`, `application/json` up to 1 MB per blob from any signer, 60 uploads per key per hour. BUD-01 GET/HEAD, BUD-02 PUT `/upload` with a kind 24242 auth event.
- The box uploads with its own **upload key** (generated on first use, stored in Agent Service state, never shown). Integrity comes from the hashes in the owner-signed listing, not from the uploader.
- Every blob fetched is hashed before it is cached or served. A mismatch drops the listing.

## Signing (Wizard ID)

Only the owner's Wizard ID signs a listing ([WIZARD_ID.md](WIZARD_ID.md)). The phone's bridge method `identity.sign` uses one approval sheet for every kind; its sentence comes only from the event: kind 30117 **"Publish *<name>* as your skin"**, kind 30617 (NIP-34 app announcement from `wizard publish`) **"Publish *<name>* as your app"**, from the `name` tag (else `d`). Desktop and Wizard for Mac show "Publish from your phone" until request routing lands.

Bridge (Android, per [NATIVE_BRIDGE.md](NATIVE_BRIDGE.md)): `identity.info` → `{npub, pubkey, name, picture, backed_up}` or `{none: true}`; `identity.setup` → `{npub}` or `{cancelled: true}`; `identity.sign {event}` → signed event or `{denied: true}`.

## Preview

The Look screen renders a fixed demo scene (home plus a short canned thread, no owner data) with the skin applied. The Android bridge method `view.capture {rect}` returns a WebP (base64) of that region. Where capture is missing, publish goes without a preview and cards show a swatch built from the skin's colours.

## Not in v1

skin.js in Store skins; follows, groups or "who uses this"; creator-uploaded images or video; publishing from desktop/Mac; NIP-46/55/05; comments, reactions, zaps; release-history events. Reserved for later: an attestation event linking a Messenger key to a Wizard ID (#90).

## Tests

- Golden vectors: two fixed events (one fork) whose ids and signatures verify.
- A listing with a bad signature, a missing file, a hash mismatch or an oversized file never reaches `GET /skins/store`.
- A blocked `a` or `p` disappears within one refresh.
- Add to my skins creates a new folder with `forked_from`; nothing existing is overwritten.
- Existing owners keep their look after upgrade: `Skins/My skin/` becomes the active skin.
- A publish with a tampered blob or a bad signature is refused and nothing is broadcast.
