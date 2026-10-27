# Incognito private-agent chat

**Status: implementation candidate; not a live rollout.** Ordinary private chats keep their existing durable behavior. Incognito is an explicit owner-only new conversation, not a setting on an existing chat and not a query/header flag on the usual chat API.

## Owner experience

- Only a new private-agent chat before its first send exposes an **Incognito** toggle. Existing threads, the Chats list and standard-agent chats never expose it. The temporary thread has a persistent label, dashed frame, and warning that it is never saved.
- Conversation and composer text live only in the current browser process. No durable outbox, automatic retry, draft recovery, session listing, title generation, search indexing, read state, pins, reminders, app actions, attachments or voice capture participate.
- Back/Close or leaving the conversation asks whether to discard it. Reload/pagehide/BFCache and removed windows wipe it and request teardown. A dropped browser or service expires its lease; reopening cannot restore it.
- v1 is text-only and tools are disabled, not merely hidden. A failed connection stays failed; no automatic ordinary-chat or public-provider fallback exists.

## Boundary

The Agent Service authenticates the owner before accepting `POST /wizard/v1/agents/:agent/incognito {}`. It requires a private agent on its configured confidential Tinfoil model. The runtime helper creates a fresh stock-Hermes sibling with a fresh API credential, returning the target only to the service. The returned browser identifier is a random `incog_<32 hex>` reference; only that owner's ephemeral route can use it.

The sibling uses the locked stock image without Hermes patches. Its root is read-only. Hermes HOME/workdir/cache/output/SQLite histories and API run state are in `noswap` tmpfs; logs are disabled at Docker and conversation-related paths are never host-mounted. No normal-agent home, Docker socket, App Manager socket, owner files, gateway credential, shared prompt mirror or persistent volume is mounted. Core dumps and container swap are disabled. A separate internal network permits only the attesting Tinfoil proxy, whose separate network supplies egress; the session itself has no public network. Provider credentials enter through stdin into tmpfs, not Docker argv/environment metadata.

The read-only seed allowlist is `AGENTS.md`, `SOUL.md`, `memories/MEMORY.md`, `memories/USER.md`, bounded and no-symlink at every path component. No directory enumeration occurs. Existing normal sessions, SQLite state, configuration, cron, credentials, plugins and skill implementations are excluded. Configuration is constructed for the configured private model, empty toolsets/MCP/plugins and no provider fallback. No write reaches the normal home. This is read-only context availability, not permission to persist new memories.

The Service reuses its existing secret-safe agent JSON/SSE proxy with an explicit ephemeral target context. The context is an allowlist, not a spread of normal hooks. Pin, catalog, input receipt, provenance, media mirrors, presentation status/title, queue and follow-up hooks do not run. The reserved `incog_` namespace is refused by ordinary discovery and side-state routes. Incognito only permits its own text-run admission, owned-run read/event/stop, own-session messages and lease/destroy endpoints. No session list or search is exposed.

## Lifetime and failure

- At most one active Incognito session per private agent. No normal runtime start/stop/restart is part of the operation.
- Browser heartbeats every 20 seconds; service and helper leases expire after 90 seconds, with a two-hour owner-message idle limit and periodic reaping. Heartbeats do not count as owner activity; sending another message renews the idle deadline.
- Closing forgets the service map before aborting streams and removing resources. Late start responses are destroyed, not reattached.
- Every helper-created container/network is labeled `wizard.incognito=1`; recovery removes only those resources, never the ordinary agent. Startup orphan recovery completes before creating sessions; the normal helper is supervised with restart. No durable reconnect registry is written.
- v1 rejects imported/restricted runtimes instead of falling back to a normal or less confined target. Supporting those runtimes requires separate acceptance, not weakening the boundary.

## Honest privacy limits

This is no conversation persistence on the owner's machine, not anonymity or a way to hide intent from the active browser/OS. Text necessarily exists temporarily in browser, service, stock Hermes and confidential-provider memory. A compromised host/browser, extension, remote debugger, copied text or screenshots can capture it. The provider's attestation/privacy guarantees remain a separate dependency. Normal read-only prompt/memory seeds were already durable before this conversation. Operating-system memory protection and crash-dump/swap settings for the service/helper/browser must also be considered; container tmpfs and disabled loggers alone do not prove all host persistence absent.

## Required acceptance before promotion

Use only fresh synthetic agents on the approved remote Linux rig. Prove the pinned image actually honors the constructed tool policy and prompts. Verify multi-turn reasoning through the real confidential provider; seed-memory recall without writes; stdout/stderr and Docker logging; exact mounts/network/cgroup limits; unique canary absence on all durable stores; close, reload, offline, dropped browser, service restart, helper interruption and late-callback cleanup. Confirm normal private persistence unchanged, full agent chat parity, two-skin phone/desktop screenshots and source-matched staging. Fixture/unit results never stand in for real stock/provider/browser evidence.
