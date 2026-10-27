# Incognito private-agent chat

**Status: implementation candidate; not a live rollout.** Ordinary private chats remain durable. Incognito is an owner-only new conversation, not a setting on an existing thread.

## Owner experience

- Only a new private-agent composer before its first send exposes the Incognito toggle. The temporary conversation stays visibly labelled.
- Draft and transcript remain in browser memory, never the ordinary outbox, history, title/index/read-state or recovery stores. Close/Back asks “End incognito chat? It will be erased.” Reload, leaving, expired leases and service/helper recovery discard it.
- v1 accepts text only. The hint explicitly says that the microphone is unavailable. No normal-chat fallback exists. **Retry** explicitly resends the in-memory input to the same temporary session; no automatic resend occurs.
- Normal shared Markdown, live answer deltas, tool progress and Stop are reused through the shared run-stream component with a scoped ephemeral target. The shared stream's ordinary status-read safety net remains; Incognito has no separate polling adapter.

## Runtime and capability boundary

The owner-only Service creates a fresh stock-Hermes sibling and keeps its fresh API credential and target only in memory. The sibling uses the **exact source container image ID**, its numeric user, network memberships (including existing egress/Tinfoil sidecar routes) and scoped `/run/` socket mounts. No source home is mounted into the sibling; unsupported non-socket mounts/imported or host-network runtimes fail closed. Existing source networks/sidecars are neither labelled nor removed. The normal private runtime is never restarted.

The root is read-only, capabilities dropped, privilege escalation disabled, core dumps disabled, container swap disabled and Docker logging disabled. Home, caches, output, histories and logs live in tmpfs. Docker 26 rejects the mount-level `noswap` option, so the supported no-swap boundary is container-wide: equal `--memory` / `--memory-swap` limits and a kernel cgroup-v2 `memory.swap.max` readback of exactly `0`. Before transferring any seed, the helper verifies that kernel limit and the three RAM mounts; missing/unverifiable enforcement fails admission and removes the empty sibling. This also prevents tmpfs/shmem pages charged to that container from entering swap. No durable reconnect registry or content-bearing Docker argv/environment is created.

### Full working-home seed

A bounded anonymous pipe connects `docker exec <source> … tar -c` to `docker exec -i <temporary> tar -x`. It never creates a host archive or logs content. It includes config, provider/fallback settings, `.env`/auth, skills, plugins, memories and fact-store files rather than a four-file allowlist. Logs, session transcripts, response-store DB/WAL files, caches, compiled caches and cron state are excluded. Symlinks/special files are not copied. No content inspection on the real owner runtime is part of development or acceptance.

The **192 MiB total transfer cap** fits within the 512 MiB RAM home. Non-history seed overflow fails admission rather than silently dropping capabilities. `state.db` is copied separately using SQLite's backup API into source-process RAM (including WAL), then streamed directly to the temporary home. If that snapshot exceeds the remaining budget, only it is omitted; `history_search: unavailable` is returned in session metadata and shown in the UI. A larger home still fails admission; no real home has been measured or read.

Configuration retains toolsets, MCP servers, providers, fallback chain, memory/fact backend, skills and plugins. Only durable orchestration is disabled: cron, schedules, kanban, delegate/heavy operations that write service records, cross-platform `send_message`, and service-history writes. A temporary **stock plugin pre-tool-call hook**, verified before admission, blocks these named operations. Platform listeners are disabled except the API listener so copied bot credentials cannot start a second messaging gateway. Cron state is not seeded. Hermes core and image remain unchanged.

Memory, fact and skill writes are allowed inside the RAM home and disappear with it. Existing home symlinks and external non-socket mounts are not a supported capability source in this candidate; refusal is preferable to mounting normal writable state.

### External actions

Read-only Wizard app access keeps the private agent's grants. Every run receives an Incognito system note: before **each** external write (Notes, Calendar, Files, Messenger sends, etc.), explain what will change, ask James and wait for an explicit yes in the current chat. The original action request does not count as that confirmation. This is the approved conversational route, not a separate approval UI or a cryptographic side-effect sandbox. Approved app changes persist in those apps. The agent must never export this chat's transcript/history into service stores.

The Service reuses `proxyToAgent` with an allowlisted ephemeral context, never a spread of normal hooks. Pins, catalog/input/provenance/media/title/queue/follow-up projections do not run. Only that temporary session's admitted runs, stream, Stop, own messages, lease and destroy are routed. Normal endpoints reject the reserved `incog_` namespace.

## Lifetime and failure

- One active session per private agent; 20-second heartbeats, 90-second leases and a two-hour **owner-message** idle deadline. Heartbeats do not renew owner activity.
- Closing forgets the Service map before aborting streams and removing the disposable container. Late callbacks cannot revive it.
- Only created disposable containers are labelled `wizard.incognito=1`; startup recovery removes labelled orphans. Existing source networks, sidecars, mounts and the normal runtime are never removed.
- Any unavailable route, seed, stock policy hook or provider fails closed. No silent standard-agent or ordinary-chat fallback is allowed.

## Acceptance and honest limits

Run only on fresh synthetic agents on the approved remote Linux worker. The staged stock test uses a **labelled deterministic OpenAI protocol fixture**, not confidential inference: actual stock Hermes must read its synthetic memory context, call a synthetic MCP tool, execute a RAM-only memory save, and retain two input canaries only in RAM. After end, abandoned lease and helper restart, require no disposable leftovers, unchanged synthetic normal home, and no canaries in synthetic service/home stores. Metadata proves no durable target volumes/log paths. Service-restart and browser-store/lifecycle checks exercise the isolated Service fixture separately. Local unit/fixture passes do not prove any remote stock result.

Real confidential-provider reasoning/attestation, actual restart interruption, source-only live parity reconciliation and owner preview/feedback remain separate promotion requirements. This is no local conversation persistence, not anonymity: the active browser/OS, debugger, copied text, screenshots, host/service swap or crash dumps remain outside the container-only boundary. External app writes explicitly approved by James remain durable.
