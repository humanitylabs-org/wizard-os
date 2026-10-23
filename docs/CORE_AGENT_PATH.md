# The core agent path and its launch receipt

This is a reading map for [Launch v1 audit 1 (#132)](https://github.com/humanitylabs-org/wizard-os/issues/132), not another API contract or a claim that an install passed. It labels the existing [architecture](ARCHITECTURE.md) and links the checks an acceptance receipt must contain. Paths, methods, query keys and compatibility classes remain authoritative in [Agent Service API v1](../spec/AGENT_SERVICE_API.md).

## The launch core is a checklist, not just a request/reply loop

[Issue #132](https://github.com/humanitylabs-org/wizard-os/issues/132) defines the launch core as **items #87–#93 plus audits #133–#140**, on **fresh Linux and Mac app** profiles. [WORK_OUTSTANDING](WORK_OUTSTANDING.md#launch-v1-core-path-audit-132) lists each item. That full set is the weekly report's subject; the lower-level agent path below explains only one part of it.

No scope freeze: new work continues behind a profile flag or as a non-default app until promoted with tests. Each PR declares any effect on frozen client fields (#137), box state (#134), updates (#135) and trust (#133). The daily architecture check-in reports merge risk; its weekly report names which core items moved and which stalled. Launch verification must prove each new feature is promoted with tests or off by default on tester boxes. This document supplies a template, not proof that a flag, check-in or weekly report is active.

## Core: from a person to an agent and back

```text
Browser / thin Android or Mac shell
  -> Wizard UX: discover endpoints and enabled capabilities
  -> Agent Service: owner boundary, session/run allowlist and Wizard projection
  -> unmodified agent harness (Hermes today)
  -> model connection, then the response/event stream back along the same path
```

| Core responsibility | Existing interface / contract | Acceptance evidence to retain |
|---|---|---|
| Discover the service | `GET /wizard/v1/bootstrap`; use its `endpoints` and `capabilities` | Selected release identity; bootstrap API version; unavailable capabilities disabled rather than assumed |
| List, open and create conversations | Allowlisted `/wizard/hermes/api/sessions` routes | List/create/read requests; correct owner and agent; retained thread readback after restart |
| Start and control a run | Allowlisted `/wizard/hermes/v1/runs` routes, including events, stop, steer and approval | A real reply; incremental events where supported; stop/steer/approval results; no cross-agent access |
| Connect the harness | [Agent bridge](../spec/AGENT_BRIDGE.md), [agent state](../spec/AGENT_STATE.md), [agents](../spec/AGENTS.md) | Exact stock harness pin and agent identity; no Wizard patch to Hermes; explicit alongside versus fresh topology |
| Reach a model | [AI connections](../spec/AI_CONNECTIONS.md) | Existing authorized model connection works; signed-out state is actionable; no credentials in the receipt |
| Keep the owner boundary intact | API access rules and [security inventory](SECURITY_INVENTORY.md) | Allowed owner and denied non-owner results on the selected composition; the browser-boundary work in #133 remains a separate open gate |

The Agent Service is the only Wizard shell API. App Manager and individual app APIs have their own contracts; they are not an invitation for a shell to bypass this boundary. The full Hermes response body is not a Wizard-owned stable schema: the API contract explicitly distinguishes the allowlist/projection from upstream passthrough data.

## Extensions around that path

“Extension” describes where a capability attaches, **not** permission to drop it from a launch requirement. The selected launch scope and each issue's done-when still apply.

| Extension | Attachment point | Canonical contract / gate |
|---|---|---|
| Launcher and app discovery | Agent Service's safe installed-app projection | API v1 `apps`; [apps.json](../spec/APPS_JSON.md) |
| App tools and skills | One box-local MCP gateway, with agent grants | [Agent bridge](../spec/AGENT_BRIDGE.md); [permissions](../spec/PERMISSIONS.md) |
| Voice and command routing | Capability-discovered transcribe/route endpoints | API v1 Voice and route sections; [native bridge](../spec/NATIVE_BRIDGE.md) |
| Files, attachments, uploads and shares | Owner-scoped storage and delivery projection | API v1 Files and attachments; [one files root](SYSTEM_APPS.md#files) |
| Read state, attention and conversation organization | Service-owned per-owner projections | API v1 thread-seen, thread-dispositions, attention and filings |
| Setup and private phone access | Owner-only setup endpoints and host integration | [Phone Setup](../spec/PHONE_SETUP.md); #87 and #139 |
| Swappable shell/views | Installed, checked view descriptor or selected shell slot | [Shell](../spec/SHELL.md); [skins and views](../spec/SKINS_AND_VIEWS.md) |
| Install, update, backup and repair | App Manager lifecycle, outside the request/reply loop | #88, #90 and #93; [repair kit](REPAIR_KIT.md); [maintenance](../spec/MAINTENANCE.md) |

A slot is a job, not a hardwired app name. Core responsibilities above do not reverse the [system-app replacement rule](SYSTEM_APPS.md): the shell and the agent remain replaceable providers of their respective slots.

## Stable, compatible, proposed and absent are different

- A route classified `stable` in API v1 is a documented service contract. A `passthrough` route has a stable allowlist/projection, not a frozen upstream body.
- `compat` is an explicit older-client alias, not a second independently designed API. `box` is an agent/operations surface, not a frontend endpoint. `page` is an HTML entry point.
- A `proposed` row is not served on main and must not be advertised as available. A `gap` row is a known call without a served implementation, not a passing check.
- Documentation on main does not prove the service selected by a release implements it. [OS PR #153](https://github.com/humanitylabs-org/wizard-os/pull/153) adds the complementary release-source check. Neither this map nor that checker substitutes for running the selected release.

## Weekly launch receipt: fill from evidence, never from memory

Use the following short record in the owning issue or acceptance report. Keep `NOT RUN` until the corresponding evidence exists. Record immutable source/artifact identities rather than a moving branch name. Do not paste owner content, raw logs, provider tokens or personal hostnames.

```text
Window (UTC): NOT RUN
Owner / next checkpoint: NOT SET
Scope: alongside | fresh | both; architecture/client and selected release: NOT SET
Pins: release manifest SHA-256; UX/service/harness/App Manager commits and digests: NOT RECORDED
Source-to-contract check: command + UX commit + spec commit + exit + unmapped/gap counts: NOT RUN
Release-to-service check: command + release + selected service commit + result: NOT RUN
Isolated route probe: command + composition + receipt SHA-256 + pass/fail/skip counts: NOT RUN
Real journey: conversation -> reply -> stop/control -> restart/readback: NOT RUN
Owner boundary: positive and negative cases + receipt: NOT RUN
Extensions required for this scope: names + individual result/receipt: NOT RUN
New failures since previous receipt: UNKNOWN
Remaining gates: exact criterion / next actor / next action: NOT REVIEWED
Weekly core progress (#87–#93, #133–#140): moved / stalled / next actor per issue: NOT REVIEWED
New-feature default audit: promoted + evidence | flag/non-default and tester state: NOT REVIEWED
Merge risk this week (client fields/state/update/trust): NOT REVIEWED
Disposition: keep open | propose close with linked evidence
```

The two API verification tools are documented in [Verifying the contract](../spec/AGENT_SERVICE_API.md#verifying-the-contract). Run sustained suites, builds and appliance journeys on the designated external QA worker. A source scanner pass, a unit-test pass and a real appliance pass are different rows, not interchangeable proofs. Keep known discrepancies and skipped cases explicit.

This document completes only the core-versus-extension map and reusable receipt-template slice. #132 stays open until the current frontend/source mapping, isolated served-route checks, selected release and weekly receipt are reconciled with linked evidence.
