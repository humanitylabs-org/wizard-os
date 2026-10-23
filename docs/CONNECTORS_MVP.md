# Connector MVP: real YouTube Music and simulated private chat

**Status: proposed build, not implemented.** Companion to [CONNECTORS.md](../spec/CONNECTORS.md). The requested deliverable is the proposed architecture and a buildable MVP scope; this document does not claim an app, security boundary or live integration exists.

## The first useful slice

James's revised scope: **real YouTube Music**, plus a **simulated private-chat feed** whose first live successor is a chat-app integration. Fixture data stays useful for security tests; it is not the Music product demonstration.

1. The owner opens Account Manager / Connected accounts and connects a Google account using the vetted authorization mechanism. The YouTube Music connector offers **Use this Google account**, shows its actual access, and requests any missing service authorization. Selecting a Google identity does not itself grant Music access.
2. In the existing Wizard Music app, the owner searches the real catalog and plays a newly requested track. Prove audio progresses through the actual selected playback path; a login, metadata response, or already-cached file does not complete this milestone. Library/account-derived data uses the private route if requested; public catalog content can use the ordinary route only after whole-request classification. Audio playback itself requires no model.
3. A separate **Simulated Chat** source emits fictional messages through the future chat-adapter contract. **Contains private data** is on. The owner selects one conversation and receives a summary only in the protected human-facing view using the preferred privacy model.
4. Disable the privacy model and retry the chat summary: it visibly blocks, with zero ordinary-model calls. Unlink Music and prove its access stops while the Google identity remains available. Disconnect Google and prove every dependent binding is invalidated. Simulated additional bindings test the multi-service lifecycle without building Gmail or a general YouTube app.

The simulated chat stream models stable message/conversation IDs, timestamps, bounded snapshots, duplicates, reconnects and hostile text. The broker, not message contents, pins selection and limits. This data is treated as private in routing/storage even though safe synthetic fixtures can live in source. Do not publish real account identifiers, media-session URLs, tokens, personal library metadata or actual messages in shared test artifacts.

**Why this MVP:** Music is already wanted and exposes the useful shared-account seam; the simulated chat feed exercises private processing without exposing real conversations. Separate service connectors can evolve independently, while the user experiences one Google account to select. One integrated Google super-app would couple unrelated permissions, privacy defaults, releases and failures; a common typed Google broker keeps account plumbing reusable without requiring every Google service in this first release.

## Fit and owners

- **Archimedes:** proposed contract, reference capability/admission broker, route enforcement and protected-result API in `wizard-agent-service`; integration of the existing Wizard Music app with a scoped Google adapter, plus an isolated simulated-chat adapter. Keep stock Hermes unchanged.
- **Wizard UX (James + Archimedes):** Connected accounts aggregation, plain-language privacy/permission badges, route setup and human-only summary view. Reuse existing provider sign-in apps and Agents setup; show the actual effective processing destination.
- **App Manager (Miguel/Oscar, proposed seam for review):** descriptor/version admission, installed metadata and enforced container/network boundaries. Changes to its schema/checker/network policy require that owner's review; no implementation has been assigned by this document.
- **Account Manager / Google broker:** propose the account-handle, authorization-grant and connector-binding seam for coordination with Miguel's account-management concept. This recommendation is not evidence of an agreed or implemented manager API. Reuse its contract when available; keep a minimal replaceable provider adapter meanwhile.
- **Existing provider-connection owners:** keep `AI_CONNECTIONS.md` and current AI connection discovery work. The source connector consumes a selected processing route; it does not inherit or mount the AI provider's login files.

Keep Wizard Music as the user-facing music app. Add a small provider-local Google account/credential component, a YouTube Music service adapter and a separate simulated-chat test source. These are distinct trust roles; source adapters need no mandatory extra launcher tiles. The first account picker supports one real Google account while its records use explicit account/grant/binding IDs. A second synthetic identity must exercise cross-account refusal; multi-account management can follow. Gmail and general YouTube adapters remain future consumers. Use the normal App Manager installation path and current app checker; proposed descriptor fields stay opt-in until adopted. Agent permission grants and app→agent bindings remain separate.

## Four build slices

Slice A establishes provider feasibility first. Its credentialed steps depend on slice B's admission and credential-boundary checks; public research and those checks can run together. Slice C combines the verified Music route with the simulated chat lane.

### A. Real Music feasibility and minimal account seam

Before generalizing login UX, prove the exact supported authorization and playback path on a separately authorized account. Record mechanism (OAuth/API, device session, or browser session), actual scope/session reach, upstream adapter, refresh behavior and provider constraints. An unofficial client such as `ytmusicapi` documents OAuth for account/catalog operations; that is not proof that a YouTube Data API token enables authenticated audio delivery or makes the existing downloader sustainable. Keep catalog, account access and actual playback as separate checks.

Acceptance: establish one Google account identity; explicitly bind the Music connector; search a real track; play uncached audio through the app's selected route; restart and refresh/re-authenticate without losing the binding; unlink; verify calls are refused. Inspect network and secret custody before any real credential use. Use an authorized test account while proving custody; owner personal-account activation requires the applicable isolation gates, including protection from the general host agent. Protect credentials even if the selected music content is public.

If the chosen playback route remains challenged or lacks a viable provider-supported path, report that exact Music milestone as blocked. Retain real Music as the selected integration and preserve the account-seam work. A fictional music catalog, metadata-only result, or cached audio is not completion, and another music provider requires owner approval.

### B. Executable policy and account-binding contract

Implement a pure deterministic admission function and schema fixtures before UI or credentials. Suggested input: trusted installed descriptor, authenticated principal/grant, input classifications, pinned owner preferences, destination eligibility, current policy revision. Output: a closed `allow_public | allow_private | block` decision and a typed reason. It never accepts model-selected endpoints or lower classifications.

Acceptance cases:

- Explicitly public catalog + public prompt -> ordinary route.
- Same catalog + private personal prompt -> private route.
- Private conversation, private summary and mixed batch -> private route.
- Missing/invalid labels -> private or block; never implicit public.
- Private-default connector's reviewed public-only operation -> public only with public inputs and no private provenance.
- App/model attempt to relabel private content -> refused.
- Missing private preference, ineligible model, failed attestation, unreachable private worker -> blocked, zero public-provider calls.
- Main-agent/default binding on a private job -> blocked before content admission.
- Wrong account, conversation, caller or expired/revoked grant -> refused.
- Music caller requests Gmail operation using the same Google identity -> refused even when the broker holds a broader provider token.
- Scope escalation requires consent; token refresh is serialized per grant; a Music operation cannot obtain the token.
- Unlink Music preserves unrelated local bindings; account disconnect invalidates all; external combined-grant revocation marks every dependent connector for re-authentication.
- Re-authentication as the wrong Google account is refused; explicit rebind invalidates prior queued work and cannot reuse old-account caches/results.
- Policy/account/model change while queued or before delivery -> cancelled/quarantined, no stale delivery.

Mocks prove decision logic only. They are not evidence of OS isolation, confidential inference or injection safety.

### C. Integrated Music plus simulated-chat preview

Package the Music account adapter and simulated-chat source through the current Wizard app contract. Run on the authorized development worker with separate agent/broker identities; real Music credentials remain only in the protected Google component, while chat uses fixtures. Use the owner's selected ordinary and private models after route verification. A model outage leaves its demonstration blocked or explicitly mocked; it does not substitute providers or count as model-route proof. Music playback and private-summary milestones can progress independently.

Observe actual HTTP/model requests, process permissions, network attempts, delivery and storage. Each model receives only its pinned, classified data packet. Verify the owner can use real Music and open the private chat summary; the ordinary agent receives no private text, private titles or sender metadata. Request retry, provider outage and disconnect must settle visibly without dropping data silently or changing providers. Back remains in the app.

The security test substitutes a hostile model result as well as hostile source messages: request a tool, fetch a URL, change destination, read a second thread, modify policy, write memory, and exfiltrate a canary. Assert that the allowed operation trace and destinations remain fixed. Misleading text may be shown to the human as untrusted output; it never becomes an executable action.

### D. First real private-content connector: scoped chat reading

After the release gates below, replace the simulated adapter with a real chat-app adapter behind the same snapshot contract. Telegram is the recommended first candidate, still subject to owner choice; the selected first private integration is a chat app. Start with a separately authorized test account, then an explicitly selected owner conversation. If Telegram is selected, use its official client authorization mechanism where feasible. The first real flow is a user-triggered, one-conversation, bounded-time snapshot summary. Sending, arbitrary retrieval, attachments, URL fetching, broad inbox monitoring and automatic replies are later capabilities with separate review.

This is a recommendation and dependency order, not authorization to link an account or begin live monitoring. A Telegram login can provide broader provider access than Wizard grants; communicate and test that difference. WhatsApp device linking has a separate adapter review; real YouTube Music is already slice A and is not deferred behind chat.

## Required before real private chat release

Every item below is **outstanding**; specification review or green fixture tests do not complete it. Credential custody, host isolation, lifecycle and provider-access checks also apply before real Google credential use; the chat gates additionally prove private-content processing and output containment.

- [ ] **Credential custody:** actual OAuth/device login, scoped session storage, refresh concurrency, account identity, local disconnect and provider revocation tested with disposable credentials. No credential appears in model traffic, logs, images, package or backup defaults.
- [ ] **Host isolation:** from the ordinary agent's actual runtime, attempts to read connector/private-worker volumes, alter policy/config, signal privileged services, reach broker internals, obtain provider tokens or invoke a host escape path fail. An unrestricted host agent keeps this gate open.
- [ ] **Processing-route proof:** real selected private model path verified, including confidential execution/attestation where applicable, all derived data, retries, errors and no-fallback behavior. Audit every ancillary service such as transcription, embeddings and telemetry before enabling it.
- [ ] **Containment proof:** hostile-source and hostile-output corpus cannot alter operation, read set, destination, identifiers, retries or external effects. Worker network probes and observed effect traces agree with the fixed template; no provider-side tools are active.
- [ ] **Output seal:** canaries absent from the standard agent's prompts/history/memory, shared files/indexes, notifications, telemetry and error reports. Human renderer loads no remote resources and follow-ups remain equally restricted. Test reconnect, multiple tabs and stale results.
- [ ] **Lifecycle:** restart, duplicate request, policy/model change, pause, disconnect, revoke and concurrent work yield at most one authorized result and no stale delivery. Crash dumps and retained queues follow private retention rules.
- [ ] **Recovery and consent:** protected retention/deletion/backup/restore documented and tested; exact owner-approved export is separate; UI accurately names plaintext custody, provider access, Wizard permissions and actual route.
- [ ] **Provider/product readiness:** provider-supported access and terms assessed, login renewals recoverable, summary quality/source references checked, limits survive flooding, and a fresh install→connect→summarize→disconnect path passes on the stock Wizard topology.
- [ ] **Independent review:** broker, runtime bypass paths, renderer and evidence reviewed by someone other than the implementer at the exact release revision. Material findings repaired and rechecked before real-data activation.

Keep the first working Music + simulated-chat slice small, run focused checks, and widen QA against demonstrated risks. All mobile builds, browser QA and sustained development run on Thales under its external work volume; orchestration/source/lightweight checks may run on the control plane. No guest-image rebuild is required for this proposal or a small web preview. Build and release artifacts must name GitHub-pushed source revisions.

## Release labels

- **Proposed:** this specification and MVP scope are published.
- **Music integration preview:** actual account binding/search/uncached playback verified; state any remaining provider or account-isolation limitations explicitly.
- **Simulated private-chat preview:** install/open/summarize works on fixture data; list unproven boundaries explicitly. Real chat is not connected.
- **Private-data eligible:** all applicable gates have exact-revision evidence.
- **Account connected:** the owner authorized a real source after eligibility; monitoring remains off until separately enabled.

These labels prevent a convincing demo or a successful login from being mistaken for a secure production connector.
