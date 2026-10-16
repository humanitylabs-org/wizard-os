# Wizard Supervisor — historical staging snapshot

**Canonical implementation moved to [humanitylabs-org/wizard-supervisor](https://github.com/humanitylabs-org/wizard-supervisor/tree/prototype/supervisor-package).** The installed isolated prototype and final acceptance are maintained there, starting with source `2ab9b22`. This subtree is retained as the original source/history checkpoint; the statements below describe its pre-extraction state. Production maintenance and default installs remain unchanged.

Supervisor is the Wizard OS system component responsible for maintenance judgment: detect impact, decide within permission, repair, verify the affected function, and retain a useful decision record. This prototype enrolls only its disposable service and internal job. Existing production maintenance and default installations remain unchanged.

## Place in Wizard

```text
System view / owner conversation
          |
Supervisor: incident ledger, policy, approval and verification
          |                         |
scoped execution adapter       tool-free judgment adapter
          |                         |
enrolled service or job        configured Hermes model/provider
```

Sibling components: `wizard-os` defines the platform contract; `wizard-agent-service` connects agents and owner conversations; `wizard-ux` supplies System, shared appearance and Back; `wizard-app-manager` admits and installs this package.

The `supervisor` slot and `wizard-supervisor` package are approved prototype identities. They are not yet default-install requirements. Source began in `wizard-os/prototypes/supervisor` on `prototype/supervisor-v01`.

## Structure

- `app/engine.py`: SQLite-backed generations, fenced approvals, bounded execution and scoped reversible preferences.
- `app/server.py`: HTTP/MCP, separate worker/owner credentials, controller and session/CSRF boundary.
- `app/agent.py`: durable, fail-closed client for enforced tool-free private judgment.
- `app/canary.py`: real disposable service operation and durable internal-job receipt.
- `web/`: the System-facing view using the shared WizardApp client, appearance kit and Back registration.
- `adapters/`: optional native Hermes SDK judgment gateway; no Hermes core changes or other-profile edits.
- `runtipi/`, `wizard.md`, `skill/`: normal Wizard package and its agent contract.
- `tests/`: focused engine, actual HTTP and planner-boundary tests.

## Run and verify

Run development/container/browser verification on Thales external media. The controller itself is a lightweight service. Packaging bundles exact stdlib Python source into a stock Python image, following the App Manager template; no local image build is required.

```sh
python3 scripts/package.py
wam check /absolute/path/to/wizard-supervisor --proposal
python3 -m unittest discover -s tests -v
```

The package is installable through the App Manager's private repository route after its source commit is published. It ships a synthetic companion target. `scripts/acceptance.py` exercises the exact Compose payload in disposable containers and writes evidence; it is distinct from managed-registration and in-shell browser proof.

## Configuration and authority

Required managed variables:
- `SUPERVISOR_TOKEN`: owner/lifecycle credential, never provided to reasoning workers.
- `SUPERVISOR_WORKER_TOKEN`: distinct scoped MCP credential; cannot approve actions, mint owner sessions, or change active rules.
- `SUPERVISOR_ORIGIN`: exact owner HTTPS origin for browser writes.
- `SUPERVISOR_COOKIE_PATH`: the hosted path prefix.

Optional private judgment: `WIZARD_AGENT_URL`, `WIZARD_AGENT_MODEL`, `WIZARD_AGENT_PROVIDER`, `WIZARD_AGENT_TOKEN`. All are passed explicitly into the main container. The URL must advertise enforced `tool_execution: none`; ordinary full-tool agent runs fail closed. No fallback model/provider is selected. Without an adapter configured, the visible mode is baseline policy.

The native adapter runs beside the installation's Agent Service using the existing Hermes interpreter and selected provider credentials. Set `JUDGMENT_DATA`, `JUDGMENT_TOKEN`, `JUDGMENT_MODEL`, `JUDGMENT_PROVIDER`, `JUDGMENT_PYTHON`, `JUDGMENT_PORT` and `PYTHONPATH` to the installed Hermes source, then run `adapters/judgment_gateway.py`. It starts with a native empty-toolset preflight, stores sessions separately, bounds admission, and launches only `sdk_worker.py`. It does not forward requests to the full-tool API. The worker asserts zero tools before and after inference and preserves the exact configured model/provider. Input cannot select executables, paths, credentials or toolsets.

Browser writes use a one-use setup ticket, an HttpOnly session, CSRF and exact Origin. Worker and owner methods remain distinct even when the worker knows the entire API. Treat this prototype's owner-network session as authority for its enrolled synthetic targets only; broader platform approval/signing remains a separate integration.

## Learning and results

Ordinary feedback is a candidate lesson. The owner can explicitly choose ask-first, wait, or handle-already-authorized for one target. These preferences are reversible, invalidate old approvals/advice, and do not enlarge underlying grants. The view shows effective versus overridden rules. A first-target diagnosis failure remains visible without starving later targets or manufacturing an owner gate.

Decision history and verified results are stored locally. Managed chat publication and production-alert cutover are separate delivery gates; no raw worker output is sent to human chats by this package.

## Evidence and release boundary

Initial engine/HTTP/planner regression suite: 39 checks passed on Thales after the first authority review. Native same-route enforcement probe returned zero available/dispatched tools and left the attempted tool-execution sentinel absent. Packaged live reasoning, managed installation and browser proof must be recorded for the final candidate; these source-level results alone do not establish them.

Every shared commit is pushed on a named branch. Production/default changes use normal PR and release authority. No full Mac guest image rebuild is needed for this prototype. Keep credentials, deployment origins, private receipts and generated state out of Git. Source provenance: in-repo implementation plus the App Manager's GPL-3.0-only UI kit; upstream shared client is loaded from Wizard at runtime, never copied or forked.
