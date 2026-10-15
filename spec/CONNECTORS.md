# Account connectors and private-data routing

**Status: proposed technical contract, 15 October 2026.** The owner approved the architectural direction: protected account connectors, a **Contains private data** designation, and automatic routing of private material through the user's preferred privacy model. This document records that direction and proposes its enforcement and MVP. Publication is not proof of implementation or approval to connect real accounts. See [DECISIONS #63](../docs/DECISIONS.md) and [the MVP / release checklist](../docs/CONNECTORS_MVP.md).

## 1. Outcome

A user connects their own accounts to their own Wizard. Wizard can play supported media and summarize selected conversations while the user retains credential custody, visibility and revocation. Private content takes the user's selected private processing route automatically; public content may use their ordinary model. Account login, permission to process data, and permission to act are separate grants.

Start with **read-only summaries**. Real messaging access is gated on demonstrated privacy and prompt-injection containment. A new account can reduce exposure of an existing identity, but has the same connector and data-handling requirements.

### Two independent properties

- **Confidentiality:** who may receive this content? `public` or `private`; unknown is treated as private.
- **Trust:** may this content choose operations or grant authority? External content and model-generated summaries are untrusted, including public music metadata.

A private model is a confidentiality control. It does not make hostile instructions safe. A public song is not private merely because it is music; the owner's listening history, private playlists, account details, personalized query and authenticated playback URL can be private.

## 2. Fit with existing Wizard contracts

- Connectors remain independently installed/versioned apps, with existing `wizard.md`, HTTP API, MCP and skill contracts. They use the existing `wizard` gateway; this proposal introduces neither a parallel agent harness nor a new general agent tool transport.
- [AI_CONNECTIONS.md](AI_CONNECTIONS.md), decision #61, still owns one app per AI provider and `GET /api/connection`. Its provider authentication and usage work is reused, not replaced with a central credential-holding Accounts app. AI-provider connections and personal-source connectors have different jobs. A shared Connected accounts view is an aggregation surface, not a shared session store.
- [AGENTS.md](AGENTS.md) still governs per-agent app grants, sealed private agents and app→agent bindings. The new privacy requirement is an additional admission check, not permission for an app to choose its destination or for a standard agent to read a private agent.
- The platform resolves the owner's preferred privacy model to an eligible isolated private processing context. Model/provider preference and delivery-agent binding must agree. An absent binding, main-agent default, incompatible model or unavailable private context **blocks private admission**. The owner is shown the required private setup; no content goes to the standard agent while asking for it.
- Ordinary public apps retain their current binding defaults. This proposal does not change manifest checkers, `apps.json`, grant defaults or live routing until explicitly implemented and versioned with the App Manager owner.
- This contract is stricter than an alongside host agent that can read every file. `AGENTS.md` section 6 describes that limitation. Such a topology is not eligible for real private-connector release until host-level access is removed. Likewise, a private-agent model downgrade cannot carry retained private connector data into a standard model: deny it or create a separate empty context. This is a proposed connector-specific restriction on the downgrade option described in `AGENTS.md` section 3.

## 3. Account and capability boundary

Each connector owns a provider session per connected account. Prefer provider-supported, scoped OAuth with browser authorization and PKCE where appropriate; use explicit linked-device approval where that is the service's mechanism. A browser-session integration is declared as broader access, isolated per account, and reviewed independently for provider support and reliability.

The user completes login/2FA in a trusted authorization surface. Passwords, codes, refresh tokens, cookies and session keys never enter model prompts, chat history, MCP results, app manifests, screenshots used for inference, ordinary logs or shared files. Use an existing vault/OS credential service behind the connector; the agent sees opaque account handles, not credential retrieval tools.

The broker grants typed operations such as `catalog.lookup`, `playback.control` or `conversation.summarize`. A grant binds the authenticated caller, connector instance, account, operation, selected conversation/resource set, expiry and policy revision. Caller identity comes from the runtime, never from model-supplied `agent_id`. Authorize every call and every delivery, including queued jobs and retries. The gateway resolves the installed upstream; callers cannot nominate arbitrary URLs.

The credential-holding connector and policy broker run under identities/containers the model runtime cannot inspect, signal, reconfigure or replace. Exclude credential-volume mounts, host homes, Docker sockets, privileged helpers and unrestricted SSH paths into these components. A separate process under the same all-powerful agent account is insufficient. Network policy prevents bypassing the broker or reaching another connector directly. The installer, trusted policy broker, connector code, host administrator and selected processing provider remain in the trusted computing base; this does not claim resistance to a compromised host administrator.

A provider session may itself permit sending even when the agent grant is read-only. The UI must distinguish **provider access** from **Wizard permissions**. A compromised connector is therefore a higher-impact failure than a compromised summarizing model. Review its small API surface and restrict its network destinations and accessible secrets accordingly.

## 4. Contains private data: defaults and payloads

**Contains private data** is the clear user-facing connector badge. It is a conservative default, not a way to declare an entire account harmless. Authentication material is always secret and never model input, even for a connector with public content.

The following is a **proposed descriptor**, not an accepted `wizard.md` extension or a currently served endpoint:

```json
{
  "contract": "wizard.connector/1",
  "id": "sample-conversations",
  "contains_private_data": true,
  "operations": {
    "conversation.summarize": {
      "effect": "read",
      "output_classification": "private",
      "processing": "summary-only"
    }
  }
}
```

A future versioned implementation validates strict boolean/enum types, rejects unknown operation definitions and binds descriptors to the installed reviewed revision. Missing/invalid privacy metadata never means public. App-provided metadata is a claim, not an independent proof: public-data operations require reviewed schemas and trusted admission policy; unreviewed adapters default to private or are refused.

### Effective classification

1. Start with the connector default: private if `contains_private_data` is true or absent, public only for an explicitly admitted public descriptor.
2. A private-default connector may expose an explicitly reviewed public-only operation (for example, catalog lookup) with a closed schema and independent provenance. This is a separate output boundary, not runtime declassification of arbitrary private data. Account/history/query fields are excluded. The owner can force this operation back to private.
3. Join the operation's output class with **every** contributing input, including user instructions, selection context, account-derived metadata and prior summaries. Any private or unknown contributor makes the whole job private. If public and private material cannot be independently separated before processing, process the whole batch privately.
4. Summaries, embeddings, extracted entities, inferred preferences, caches and retries inherit that classification. Summarization or a model's claim that text is anonymized never lowers it.
5. Persist an integrity-protected envelope with opaque source references, authenticated connector/account identity, classification, trust=`untrusted`, operation, grant/policy revisions, pinned model route and retention policy. The trusted broker creates/verifies it; the model cannot relabel it. Source references and account mappings are private metadata and are not appended to ordinary model requests or content-free notifications.

Public audio/catalog material may use the user's ordinary model when that provider use is authorized and the **entire request** is public. Raw account cookies, bearer media URLs and personal listening context never accompany it. Stream playback ordinarily needs no model at all. Data classification does not grant redistribution, downloading, model-processing or playback rights; provider terms and technical support remain separate release gates.

## 5. Deterministic processing route

Before any payload enters a model, job log, agent history or shared queue, the trusted boundary decides:

```
owner-authorized request / fixed schedule
  -> connector's scoped reader
  -> private-capable admission boundary (classification + grant checks)
  -> public job: approved ordinary model, minimal public payload
     private job: owner's pinned eligible privacy model, minimal private payload
  -> bounded untrusted result, classification retained
  -> owner-only result surface
```

The preference identifies provider, model and privacy requirements. For the existing Private-agent contract, eligible processing means local execution or a verified confidential-compute route; provider branding or a "no training" toggle alone does not establish that property. Validate attestation where applicable, endpoint identity, retention configuration, tool restrictions and the actual request path. A provider/model change requires owner authorization and renewed compatibility checks. Incognito/retention is independent from model privacy: choosing private inference does not automatically disable history.

**Fail closed:** missing preference, model unavailable, attestation failure, unsupported operation, expired grant, stale policy or uncertain classification yields a typed blocked state with no ordinary-model fallback. The owner sees a content-free explanation. Resolve the privacy destination before fetching private payloads where possible; otherwise retain them only inside the protected boundary under the stated retention policy.

A standard agent may request a fixed workflow only with an existing owner-issued grant. Its response is a content-free job status. Message text, sender names, snippets and even generated report titles must not return to that agent. Results open directly for the human in the protected surface. Private jobs never inherit the initiating standard chat's transcript or write results into it.

## 6. Summarization and prompt injection

The first lane is fixed: **read one owner-selected conversation snapshot → summarize → show the human**. The trusted broker pins source IDs, time range, byte/token limits, model route, output destination and bounded retry policy before inference. A later scheduled version uses the same owner-configured scope; message content never expands it.

The summarizer has no terminal, browser, MCP, connector calls, retrieval, sending, delegation, memory writes or model-provider built-in tools. It receives only the pinned snapshot and a fixed task; it returns bounded text. Its network route reaches only the selected model gateway, not arbitrary domains or provider-account APIs. Tools/function-call outputs fail validation rather than being executed. The model never chooses identifiers, read sets, URLs, recipients, scheduler parameters or actions through an ostensibly structured response.

Output is untrusted plain text in a deterministic owner-only renderer with source references added by the broker. Render no active HTML, remote images, automatic URL fetches, link previews or executable Markdown. Follow-up questions remain in an equally restricted, private context. Do not feed summaries to a general tool-enabled agent, shared memory, compression, search index, diagnostic collector or notification generator. A safe summarizer followed by an unrestricted agent is an open boundary.

**Containment claim:** even if the model follows every hostile instruction, it can produce misleading words and consume its bounded allowance; it cannot choose another read, destination, tool action or external effect. Semantic correctness remains a separate quality test. Injection detectors and prompt warnings may supplement this boundary; passing them is not release evidence.

Future reply drafting and sending are separate capability lanes. Owner approval must bind the exact destination and content outside model control. Owner-approved export is a separate declassification flow showing the exact item and recipient; it preserves the untrusted label. Export does not automatically authorize executing instructions in that content. Broad private-agent action workflows require their own containment design.

## 7. Lifecycle, storage and visibility

- **Connect:** show provider access, Wizard-granted operations, selected accounts/conversations, effective privacy route and retention before activation. Preserve provider passkey/2FA; verify the resulting account without exposing secrets.
- **Test:** report authentication, source access, routing and playback/summary checks separately. A signed-in account is not proof that playback or automation works.
- **Pause/restrict:** stop admission, invalidate applicable pending capabilities and prevent late outputs from crossing the old policy boundary. In-flight processing may already have reached the authorized provider; state that honestly.
- **Disconnect:** revoke provider credentials where supported, invalidate local grants/jobs and clear local session material. Report local disconnection separately from confirmed provider revocation. Failed remote revocation remains a visible recovery action. Disconnect does not silently erase user-owned summaries; deletion and retention are separate controls.
- **Policy change:** reauthorize jobs before dispatch and before delivery. Revoke or quarantine outstanding jobs if the account, resource scope, classification, model eligibility or destination changed; idempotency never bypasses these checks.
- **Storage:** secrets, private raw data and private derived data stay in connector/private-worker volumes inaccessible to standard agents and ordinary apps. Never place them in the globally shared `media/` root. Encrypt retained data/backups with user-controlled custody, bound retention, and document restore/revocation behavior. Encryption at rest does not isolate a running process that holds the keys.
- **Audit:** owner-visible operation/time/outcome/policy receipts, with sensitive identifiers in the protected store. Ordinary service logs and notifications contain only opaque status codes and job handles. Redact provider errors before forwarding; they may contain content or authenticated URLs.
- **Custody:** a home box, rented VPS and confidential compute have different trusted parties. UI/docs state where plaintext, keys and inference exist. "Runs on your Wizard" alone is not a privacy guarantee.

## 8. Compatibility and adoption

This publication is documentation only. Existing AI-provider apps, Music packaging and agent-binding work continue under their existing contracts. No session is copied, real account linked, app permission widened, privacy model substituted, host service restarted or data reclassified by adopting this proposal into the repository.

Implement metadata parsing, enforcement, network isolation, protected rendering and migration as explicit versioned slices. Legacy connectors without the new contract remain legacy; the UI must not award them the new privacy/containment assurance badge. The opted-in connector path defaults unknown data to private and blocks when enforcement is unavailable.

The [MVP](../docs/CONNECTORS_MVP.md) proposes a synthetic music catalog plus synthetic private conversations to validate the whole user journey without credentials. Real Telegram is the first suggested integration after release gates; WhatsApp and real music playback each need provider-specific feasibility and account-risk review. No provider switch is implied.

## References

- [Google native OAuth authorization and PKCE](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Telegram user authorization](https://core.telegram.org/api/auth)
- [WhatsApp linked-device security design](https://engineering.fb.com/2021/07/14/security/whatsapp-multi-device/)
- [YouTube API developer policies](https://developers.google.com/youtube/terms/developer-policies)

These explain authentication and provider constraints; they do not certify this proposed implementation.
