# Connector MVP: public catalog and private conversation summaries

**Status: proposed build, not implemented.** Companion to [CONNECTORS.md](../spec/CONNECTORS.md). The requested deliverable is the proposed architecture and a buildable MVP scope; this document does not claim an app, security boundary or live integration exists.

## The first useful slice

An owner opens Connected accounts, enables two conspicuously labelled demo sources, selects their normal model and eligible preferred privacy model, and asks for summaries:

1. **Demo Music Catalog:** small fictional public catalog with public descriptions. The ordinary model answers a public catalog question. No copyrighted audio download or external music account is needed.
2. **Demo Conversations:** fictional messages from one selected conversation, including an adversarial message. **Contains private data** is on. Its summary opens only in the protected human-facing view using the selected privacy model.
3. The owner disables the privacy route and retries. The job visibly blocks, with no ordinary-model request. Revoking the demo connection stops queued work and late deliveries. Re-enabling requires explicit authorization.

The second source contains synthetic data but is treated exactly as private for routing and storage. Demo data may be shared in source; secrets and real conversations may not. Public-source prompts in the demonstration are also synthetic so account identity or personal query context cannot quietly contaminate the public route.

**Why this MVP:** one journey proves the user's defining idea—privacy-labelled connectors select the right processing route—while keeping account-login complexity and real-chat exposure out of the first experiment.

## Fit and owners

- **Archimedes:** proposed contract, reference capability/admission broker, route enforcement and protected-result API in `wizard-agent-service`; synthetic adapters in an isolated connector demo package. Keep stock Hermes unchanged.
- **Wizard UX (James + Archimedes):** Connected accounts aggregation, plain-language privacy/permission badges, route setup and human-only summary view. Reuse existing provider sign-in apps and Agents setup; show the actual effective processing destination.
- **App Manager (Miguel/Oscar, proposed seam for review):** descriptor/version admission, installed metadata and enforced container/network boundaries. Changes to its schema/checker/network policy require that owner's review; no implementation has been assigned by this document.
- **Existing provider-connection owners:** keep `AI_CONNECTIONS.md` and current AI connection discovery work. The source connector consumes a selected processing route; it does not inherit or mount the AI provider's login files.

Use one isolated demo package with two separately authenticated fixture adapters and separate data stores. Final provider connectors remain independently installed apps. The demo is a test vehicle, not a central production session warehouse. Its install and release must use the normal App Manager path and unchanged current app checker; proposed descriptor fields stay in an explicit opt-in schema until adopted. Agent permission grants and app→agent delivery bindings remain separate.

## Three build slices

### A. Executable policy contract

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
- Policy/account/model change while queued or before delivery -> cancelled/quarantined, no stale delivery.

Mocks prove decision logic only. They are not evidence of OS isolation, confidential inference or injection safety.

### B. Isolated end-to-end synthetic preview

Package the demo using the current Wizard app contract. Run it on the authorized development worker, with separate agent/broker identities and no real account material. Use the owner's selected ordinary and private providers only after route verification; if unavailable, keep model-output demonstration explicitly mocked and the provider proof outstanding.

Observe actual HTTP/model requests, process permissions, network attempts, delivery and storage. The model receives only the pinned fixture. Verify the owner can open both results; the ordinary agent receives no private text, private titles or sender metadata. Request retry, provider outage and disconnect must settle visibly without dropping data silently or changing providers. Back remains in the app.

The security test substitutes a hostile model result as well as hostile source messages: request a tool, fetch a URL, change destination, read a second thread, modify policy, write memory, and exfiltrate a canary. Assert that the allowed operation trace and destinations remain fixed. Misleading text may be shown to the human as untrusted output; it never becomes an executable action.

### C. First real connector: scoped Telegram reading

After the release gates below, propose a separately authorized Telegram test account, then an explicitly selected owner conversation. Use Telegram's official client authorization mechanism where feasible. The first real flow is a user-triggered, one-conversation, bounded-time snapshot summary. Sending, arbitrary retrieval, attachments, URL fetching, broad inbox monitoring and automatic replies are later capabilities with separate review.

This is a recommendation and dependency order, not authorization to link an account or begin live monitoring. A Telegram login can provide broader provider access than Wizard grants; communicate and test that difference. WhatsApp device linking and supported Music playback follow separate adapter reviews.

## Required before real private chat release

Every item below is **outstanding**; specification review or green fixture tests do not complete it.

- [ ] **Credential custody:** actual OAuth/device login, scoped session storage, refresh concurrency, account identity, local disconnect and provider revocation tested with disposable credentials. No credential appears in model traffic, logs, images, package or backup defaults.
- [ ] **Host isolation:** from the ordinary agent's actual runtime, attempts to read connector/private-worker volumes, alter policy/config, signal privileged services, reach broker internals, obtain provider tokens or invoke a host escape path fail. An unrestricted host agent keeps this gate open.
- [ ] **Processing-route proof:** real selected private model path verified, including confidential execution/attestation where applicable, all derived data, retries, errors and no-fallback behavior. Audit every ancillary service such as transcription, embeddings and telemetry before enabling it.
- [ ] **Containment proof:** hostile-source and hostile-output corpus cannot alter operation, read set, destination, identifiers, retries or external effects. Worker network probes and observed effect traces agree with the fixed template; no provider-side tools are active.
- [ ] **Output seal:** canaries absent from the standard agent's prompts/history/memory, shared files/indexes, notifications, telemetry and error reports. Human renderer loads no remote resources and follow-ups remain equally restricted. Test reconnect, multiple tabs and stale results.
- [ ] **Lifecycle:** restart, duplicate request, policy/model change, pause, disconnect, revoke and concurrent work yield at most one authorized result and no stale delivery. Crash dumps and retained queues follow private retention rules.
- [ ] **Recovery and consent:** protected retention/deletion/backup/restore documented and tested; exact owner-approved export is separate; UI accurately names plaintext custody, provider access, Wizard permissions and actual route.
- [ ] **Provider/product readiness:** provider-supported access and terms assessed, login renewals recoverable, summary quality/source references checked, limits survive flooding, and a fresh install→connect→summarize→disconnect path passes on the stock Wizard topology.
- [ ] **Independent review:** broker, runtime bypass paths, renderer and evidence reviewed by someone other than the implementer at the exact release revision. Material findings repaired and rechecked before real-data activation.

Keep the first working synthetic slice small, run focused checks, and widen QA against demonstrated risks. All mobile builds, browser QA and sustained development run on Thales under its external work volume; orchestration/source/lightweight checks may run on the control plane. No guest-image rebuild is required for this proposal or a small web preview. Build and release artifacts must name GitHub-pushed source revisions.

## Release labels

- **Proposed:** this specification and MVP scope are published.
- **Synthetic preview:** install/open/use works on fixture data; list unproven boundaries explicitly.
- **Private-data eligible:** all applicable gates have exact-revision evidence.
- **Account connected:** the owner authorized a real source after eligibility; monitoring remains off until separately enabled.

These labels prevent a convincing demo or a successful login from being mistaken for a secure production connector.
