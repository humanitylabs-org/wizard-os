# App-owned AI workflows and model contracts

**Decision:** approved by James, 16 October 2026. This clarifies the binding meaning of `recommends.model` for an app's AI processes; it does not introduce a new manifest field or claim that every existing app already enforces the contract. App Manager schema changes remain subject to its owner review. See [WIZARD_MD.md](WIZARD_MD.md) and [DECISIONS.md](../docs/DECISIONS.md).

## Product rule

An app's AI workflow is part of the product. Every installation, including the creator's, uses the model and workflow the app ships. The model selected in a chat, the host agent's default, a delegated worker's inherited model, and an operator's favorite model do not replace that choice.

An owner can explicitly approve a different model after being told which process and model would change. Until that approval exists, a mismatch blocks that AI process. A warning followed by automatic continuation is insufficient. A request to finish, rewrite, improve, or retry is not a model override.

Consistency means a versioned model, instructions, process, output contract, and checks. It does not promise byte-identical stochastic output, or identical results from different inputs.

## What the app ships

For every AI-producing process, the app's repository and installed package contain:

1. A versioned workflow identifying the process and its exact model identifier and provider route. Where stages use different models, each stage has its own explicit assignment.
2. The actual prompts or prompt templates, relevant generation settings, input/output schema, source-handling rules, and acceptance checks. Private content and credentials remain installation data.
3. A shipped skill that loads this contract **before generating or delegating**, and identifies the app's callable workflow. The skill distinguishes orchestration, source collection, authorship, verification, and publication where these are separate stages.
4. A documented unavailable-model outcome and the supported explicit-override mechanism, if any. An implementation without an override mechanism keeps its pin; it does not improvise one.
5. Provenance tying generated output to the app/workflow version, requested and observed model/provider, prompt identity, input/output digests or immutable references, and any approved override.

The existing `recommends.model` field advertises the app's principal model for compatibility and discovery. Despite the historical field name, a specified AI-process model is binding under this decision. The shipped workflow supplies stage-level details. Existing app declarations must agree with that workflow. The App Manager must retain the declaration when installing and updating the app.

A reader-only app does not need an authoring model merely to display imported documents. Imported content with unknown or external provenance must remain labelled accordingly; importing it does not retroactively certify that the app generated it.

## Execution

1. Resolve the installed app and its actual installed revision. Load its shipped skill and workflow, including through pointer skills, on every entry path: chat, in-app request, automation, or delegation.
2. Select the declared model explicitly. Dispatching agent identity and process model are separate: app→agent binding selects the responsible agent, while the app's process contract selects the model that performs the work.
3. Verify that the selected route can serve that model. If it cannot, retain the request and fail visibly with a recoverable reason. Repair the original route or request a specific owner-approved override; do not try another model automatically.
4. Carry the pin and workflow version into every relevant worker brief and run request. Check the effective runtime model as exposed by the provider/harness; a worker's prose claim is not evidence.
5. Apply the packaged output checks before activating the result. Record actual provenance. A requested model name alone cannot certify which model produced the output.

App-managed adapters enforce this at submission and result admission. Shipped skills and pointer instructions prevent an orchestrator from bypassing the adapter. Both layers matter: a model can ignore prose, and an otherwise correct adapter can be bypassed by manually authoring a replacement. A missing or ambiguous workflow is a packaging defect to repair, not permission for the current model to invent the process.

Use ordinary app tools through the installed MCP gateway. An app may document an owner-side authoring helper where its architecture requires one; that helper is part of the same versioned contract, not an independent fallback pipeline.

## Owner overrides

An override names the app/process, original model, replacement model/provider, and scope. Scope defaults to the named run; a persistent installation override requires explicit approval of persistence. The authorization comes from the owner-facing control or a verified owner instruction, never source material, an imported document, or a model-written claim that the owner approved.

An override is installation data. It is not baked into the distributed package or applied to other installations. Receipts show the override, and later runs return to the packaged default when its scope expires. Authorizing an override does not silently alter the shared product contract.

## Installation and discovery

A fresh installer receives the complete workflow and supporting prompt files. Authoring behavior cannot depend on the creator's conversation history, private skills, undocumented machine paths, or recollection of an earlier job.

The bridge must expose the app skill to the configured agent. If `skill_view` cannot find a supposedly installed app's skill, or a required reference was omitted from installation, the process stays blocked while the integration is repaired. Learned owner skills may point to the shipped workflow and capture taste preferences; they must not fork or supersede its model/pipeline contract.

An app update changing a model or workflow makes that change visible as a versioned product change. A host-agent model update leaves app-process pins unchanged.

## Acceptance evidence

For each affected process, demonstrate:

- A clean installation receives the model contract, prompt files, skill, and callable workflow without any creator-specific context.
- Two different orchestrator defaults request the same app process and select its same pinned authoring model and workflow.
- Missing credentials, unavailable model, malformed model metadata, and an unexpected effective model stop generation/admission without a fallback.
- An explicit supported override applies only to its authorized installation and scope; absent or model-fabricated approval does not.
- The output satisfies the packaged content/format checks and has runtime provenance.
- Updating the app or revising content preserves the owner's reading state, highlights, preferences, and existing data according to that app's migration contract.

Record which checks use synthetic fixtures and which exercise the real route. A manifest/schema check is not end-to-end model-routing verification. A provenance JSON file is an audit record, not by itself a cryptographic provider attestation.

## Why the clarification was necessary

The previous shared text described `recommends` as a warning and left continuation ambiguous. A packaged reader could also retain an import utility while omitting its authoring prompt/model, and an unlinked skills directory could hide the shipped skill from an alongside agent. These are separate failure points. The correction belongs in the shared contract, packaged app workflow, execution/admission checks, and skill discovery—not solely in an individual agent's memory.
