# App-provided agent runtimes (candidate)

Reply-only app runtimes are exempt from legacy MCP/skill declarations: they
implement the agent HTTP protocol, not app tools. Agent ids follow Service's
31-character namespace and reserve main/hermes/default/new/options.

REUSE: WAM layer-2 grants, generated provider endpoints, network isolation,
local `runtime.package: build`, installed apps.json and Service's external run
protocol. EXTEND: a generic `agent_runtime` manifest field and Service projection.
NEW: Pi's adapter from Router SSE into the existing Pi SDK provider interface.

## Admission

A type `agent`, standard-privacy app may declare:

```yaml
agent_runtime:
  id: pi
  label: Pi
  harness: pi
  port: 18659
  model: {provider: wizard-router, model: reply}
```

`id` and `harness` are slugs; label is nonblank, max 80 characters; port is a
nonprivileged container TCP port. The model identifies the runtime's stable
logical model, not a forced underlying subscription. Arbitrary URLs, secret
references and filesystem paths are not accepted. No tools are implied.

WAM validates/project this declaration and allocated host_port into apps.json.
Agent Service obtains a normal scoped connection TO the runtime, minted by WAM's
existing layer-2 grants reconciler. Only Service's own `/wizard/grants.json`
contains the clear outgoing key. The runtime's own grants file has its hash.
Registry/browser responses contain no keys. Uninstall removes the installed
projection and revokes the connection; Service no longer lists or routes the
runtime. Chat/thread catalog and app-data are not deleted by admission.

Service projects agents dynamically on every read: install, key rotation,
disconnection and uninstall take effect without a Service restart. Duplicate
agent ids fail closed; any existing Service-owned/file-provisioned id wins and
requires explicit migration, never automatic overwrite. Main is reserved.
App-managed runtime settings/lifecycle are not sent to the Hermes driver.

## Model access

Pi declares a `reply` model need and uses its normal outgoing Router grant.
Router chooses the tested model or an owner-approved replacement, through the
installed ChatGPT/Claude connection apps. Pi has no subscription credentials,
forum endpoint or inference proxy. The adapter forwards text only and requires
Router's effective-model done receipt; errors/truncation are failures, not a
successful empty answer. Phase two can add MCP with explicit permissions later.

## Release gate

This is candidate platform behavior, not an assertion that released managers
already support it. Ship compatible checker, WAM and Agent Service before
advertising a runtime app. Private owner testing precedes any public listing.
