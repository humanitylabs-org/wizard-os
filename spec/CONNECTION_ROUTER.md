# Connection Router: apps get the models, services and agents they need

Status: **Direction approved by James, 18 Oct 2026** (decision #65): one component, separate from the Agent Service, that connects every app to the AI models, outside services and agents it needs. Field names and APIs below are **proposed**; Miguel to confirm the provider-app changes (his [AI_CONNECTIONS.md](AI_CONNECTIONS.md) apps), Jan reviews after the fact.

## Why

Today every app wires its own connections. Wisdom hardcodes three Claude models and its helper service reads the owner's Claude sign-in file directly, so a box with only ChatGPT gets "not connected" and no way forward. The pieces to fix this already exist, each answering one question:

| Question | Answered by |
|---|---|
| Which providers is this box signed in to? | One connection app per provider ([AI_CONNECTIONS.md](AI_CONNECTIONS.md), #61) |
| Which model must an AI process use, and when may it change? | The app's shipped workflow; swaps need the owner's explicit approval ([APP_WORKFLOWS.md](APP_WORKFLOWS.md), #63) |
| May app A call app B? | Owner-approved grants with a per-grant key ([PERMISSIONS.md](PERMISSIONS.md), #76) |
| Where does an app's work go? | App → agent binding ([AGENTS.md](AGENTS.md) section 7) |
| Which data is private, and which models may see it? | "Contains private data" and preferred private model ([CONNECTORS.md](CONNECTORS.md), #85) |

Missing is the one piece that reads what an app needs, matches it to what the owner has, asks the owner once when they don't match, and then makes the calls. That is the Connection Router.

## The pieces

- **Provider apps** own one sign-in each and make the actual call: Claude, ChatGPT, later Tinfoil, OpenRouter, Google, Bright Data. They stay small.
- **The Connection Router** (system app, slot `connection-router`, replaceable like any slot) reads every app's needs, keeps the owner's choices, gives each app one address and its own token, and forwards each request to the right provider app. It holds no provider credentials.
- **Apps** declare needs in `wizard.md` and talk only to the router. An app never holds a password or API key and never names a provider in code.
- **The shell** shows the install sheet and the per-app "Models and connections" settings.

It is not part of the Agent Service. The Agent Service is the front door to Hermes (threads, runs, files). App inference must not touch Hermes memory, persona or tools: Wisdom's Ask AI deliberately sees only the passage and chapter. Agents appear here only as one more thing an app can need.

## Model tiers

| Tier | Meant for | Examples (each provider publishes its own) |
|---|---|---|
| `fast` | instant lookups, classification, short rewrites | Claude Haiku, GPT mini, DeepSeek Flash |
| `standard` | everyday reasoning, Q&A over a document, drafting | Claude Sonnet, GPT standard, GLM |
| `frontier` | the hardest work: long synthesis, authoring, architecture | Claude Opus, GPT top model |

A provider app lists which of its models fill each tier. Only models the provider marks `frontier` count as frontier, so GLM can be standard and never frontier. When no connected provider has a model in the requested tier, the router can offer the best model it has, labelled as standing in for that tier, and only as a swap the owner approves.

## What an app declares (`wizard.md`)

```yaml
requires:
  models:                       # one entry per AI feature; ids are stable
    ask:
      label: Ask AI about a passage
      tier: standard
      tested_on: claude-sonnet-5   # what the developer tested and recommends
      abilities: [web_search]      # the feature is offered only where these exist
    lookup:
      label: Look up a word
      tier: fast
      tested_on: claude-haiku-4-5
    author:
      label: Write a chapter
      tier: frontier
      tested_on: claude-opus-5-5
      swap: never                  # strict: waits for this model, never swaps
      private_data: false          # true = only the owner's private models ([CONNECTORS.md](CONNECTORS.md))
  services:                     # outside connections other than AI models
    - slot: web-scraping
      recommend: brightdata
      purpose: Fetch pages that block ordinary requests
      optional: true
```

- Models and services are required unless `optional: true`. Each may declare an optional `purpose`: one owner-facing line of at most 80 characters. An omitted purpose is returned as `null`.
- Service `private_data` defaults to `false`. When `true`, only a provider whose installed registry entry has `private: true` can satisfy the service; neither owner approval nor an optional declaration bypasses this check. The registry marker, not a provider's self-report, is authoritative.
- `swap` is `ask` (default: the owner may approve a replacement) or `never`.
- `recommends.model` stays for discovery and must equal one of the `tested_on` values.
- A `services` slot counts as a `uses:` entry; it need not be listed twice. `recommend` names the provider app to install when none is present.
- Agents: an app that hands work to an agent keeps declaring `agent_binding` exactly as today. The router shows it on the same install sheet. Apps with only `requires.models` run without any agent.

## The owner's choices

The router keeps one **routing table** per box: for each installed app and feature, the provider and model, and who chose it.

```json
{"app": "wisdom", "feature": "ask", "provider": "chatgpt", "model": "gpt-5.5",
 "tested_on": "claude-sonnet-5", "chosen": "owner-swap", "at": 1792360000}
```

`chosen` is `match` (the tested model was available), `owner-swap` (the owner approved a replacement; this is the APP_WORKFLOWS override with installation scope), or `owner-pick` (the owner changed a match by hand). The table lives in the router's app data, is mirrored without tokens into `apps.json` as top-level `routes`, and travels with whole-box backups.

**At install** the router works through each feature:

1. The tested model is reachable through a connected provider: route it, nothing to ask.
2. It isn't, and `swap: ask`: the install sheet shows the feature, what it was tested on, and two choices. **Connect Claude** installs and opens that provider's connection app. **Use ChatGPT instead** names the replacement model and says "results may differ from what the developer tested". The owner's provider order in router settings pre-selects the replacement; it still takes one tap.
3. `swap: never`: only the connect choice. The feature stays off until the provider is connected; the rest of the app works.
4. `private_data: true`: only the owner's private providers are offered ([CONNECTORS.md](CONNECTORS.md)). There is never a fallback to an ordinary model.

Later, the app's settings sheet lists each feature with the model answering it, where the owner can change it.

**At run time nothing switches by itself.** If the routed provider is signed out, out of quota or down, the call fails with a reason and a link to fix it. The router may then offer a one-off swap ("Claude is signed out. Reconnect, or answer this one with ChatGPT?"); the owner's tap is a single-run override. An app update that changes `tested_on` re-runs matching for that feature only and asks again if the match is lost.

## Router API (for apps)

The app gets a grant to `slot:connection-router` at install ([PERMISSIONS.md](PERMISSIONS.md)) and sends `X-Wizard-Grant` on every call.

```
GET  /v1/needs                       this app's features and services, each ready | needs_owner | blocked, with a fix link
POST /v1/models/<feature>/run        run one feature
ANY  /v1/services/<slot>/<path>      forwarded to the provider app holding that slot
```

`run` body: `{system, messages, max_tokens, stream, abilities}`. It streams server-sent events; the final event carries provenance:

```json
{"type": "done", "provider": "claude", "model": "claude-sonnet-5", "tier": "standard",
 "tested_on": "claude-sonnet-5", "chosen": "match", "usage": {"input": 4120, "output": 380}}
```

The app shows the model that answered ("Answered by Sonnet 5"). Errors use the AI_CONNECTIONS codes (`signed_out`, `expired`, `limit`, `unreachable`, `provider_error`) plus `needs_owner` and `blocked`, always with `fix_url`.

### Setup readiness (additive needs fields)

`GET /v1/needs` and the trusted-shell-only `GET /v1/owner/needs/<app>` return the same needs for the installed app; the owner endpoint additionally lists model providers. Both include:

- Each model and service: `required: bool` (the inverse of `optional: true`) and `purpose: str|null`.
- Each service: `private_data: bool`, `recommend: str|null`, and `fix_url: str|null`. A non-private selected provider for a private-data service yields `status: blocked` with a clear `error` message, even while running. The same check applies at call admission, not only in the checklist.
- Top-level `ready_to_open: bool`: true exactly when every **required** model and service has `status: ready`. An empty needs list is ready. Optional blocked needs remain visible but do not prevent opening. `agent_binding` is passed through unchanged and does not enter this calculation.

The shell uses these fields for the shared install/open checklist. Batch transcription through the box's existing shared `TRANSCRIPTION_URL` is not a live-transcription need.

### WebSocket service transport

`GET /v1/services/<slot>/<path>` with `Upgrade: websocket` uses the same caller grant, declared-service check, pinned slot selection, privacy check and outgoing provider grant as HTTP. The router connects directly to the provider's API origin (TLS verified for HTTPS); it never follows redirects or environment proxies.

Only these caller headers may be forwarded: `Sec-WebSocket-Key`, `Sec-WebSocket-Version`, `Sec-WebSocket-Protocol`, `Sec-WebSocket-Extensions`, `Upgrade`, `Connection`. The router supplies `Host` and its own `X-Wizard-Grant`; it drops caller `Origin`, `Cookie`, `Authorization`, identity and forwarding headers. A successful provider `101` relays the upgrade and negotiation headers, not provider cookies, then tunnels opaque bytes bidirectionally until either side closes. The router does not log audio or transcript bytes and does not interpret frames. The service must enforce its frame/protocol limits. A session closes after 120 seconds without bytes in either direction or four hours overall. Other HTTP requests continue concurrently. Rejected/non-101 upgrades return the normal JSON error shape (`type`, `code`, `message`, `fix_url`), never provider HTML or credentials.

Inference APIs remain unavailable through service routes. A provider that also offers `ai-connection` may expose the live-transcription contract below through **only** slot `live-transcription`, path `/v1/live` (with optional query); this is not general access to that provider's `/api/infer` or other paths.

### Live transcription (`wizard.live-transcription/1`)

A provider declares `provides: [live-transcription]` (possibly alongside `ai-connection`) and serves `GET /v1/live` as a WebSocket on its API port. Only the Router may call it, using its outgoing grant. A consuming app declares:

```yaml
requires:
  services:
    - slot: live-transcription
      recommend: wizard-tinfoil
      private_data: true
      purpose: Words appear as you speak
```

Apps connect only through `ws(s)://<router>/v1/services/live-transcription/v1/live`, with their normal `X-Wizard-Grant` header. Providers are replaceable; `recommend` is not a hardcoded runtime route.

Client → provider:

- First frame, text: `{"type":"start","format":"pcm_s16le","sample_rate":16000,"channels":1,"language":null}`.
- Binary frames: raw PCM in that format, each at most 64 KiB.
- Text `{"type":"commit"}`: finalise the current utterance (a pause).
- Text `{"type":"stop"}`: finalise pending audio, send `closed`, then close.

Provider → client (JSON text frames):

- `{"type":"ready","provider":"<app id>","model":"<model id>"}` once audio can be accepted. Audio arriving before `ready` must be buffered, never dropped.
- `{"type":"delta","text":"..."}`: provisional words for the current utterance.
- `{"type":"final","text":"..."}`: finished words, one per commit with audio.
- `{"type":"error","code":"signed_out|limit|unreachable|unsupported_format|provider_error","message":"..."}`: failure.
- `{"type":"closed"}` followed by a normal WebSocket close.

Providers never log audio or text. An unsupported format produces `error` with `code: unsupported_format`, then closes. The tunnel is transport only: these semantics are enforced by provider and consumer, not by the router.

## Provider app additions (`wizard.ai-connection/2`, additive)

1. `GET /api/connection` gains `models: [{id, label, tier, abilities, context}]`. Readers of `/1` ignore it.
2. `POST /api/infer`: one isolated call. No memory, no persona, no tools except the requested abilities the model supports; returns the same event stream and the effective model the provider reported. Only the router may call it (grant from `connection-router`).

For Claude this is the pattern Wisdom's helper service already runs: `claude -p` with its own config directory and the app's own sign-in. For ChatGPT it forwards to a raw-inference route in the `wizard-os` Hermes plugin, so Hermes stays the only holder of the ChatGPT login (open question 1).

## Exporting an app

An app that talks only to the router can run outside WizardOS. A small stand-in router with the same API, filled from a config file of API keys and a fixed routing table, lets a Wizard app run as an ordinary web service on a client's server. Later; the API above is designed so the stand-in needs no shell, App Manager or agent.

## Rollout

1. This spec (decision #65).
2. Router app: discovery from `apps.json`, routing table, `/v1/needs`, `run` forwarding, grants; tested with a fake provider.
3. Provider apps: `/2` model lists and `/api/infer` for Claude, then ChatGPT (PRs to Miguel's repos).
4. Shell: install sheet and per-app "Models and connections".
5. Wisdom adopts it (ask = standard, lookup = fast, author = frontier with `swap: never`); its own helper service retires.
6. Acceptance on Thales with four boxes: Claude only, ChatGPT only, both, neither. A strict feature waits, a swap is asked once and recorded, and every answer names its model.
7. Later: the orb's fast router moves onto the router; services beyond AI (Google via the [CONNECTORS.md](CONNECTORS.md) broker, Bright Data); the export stand-in.

## Open questions

1. **ChatGPT sign-in: settled (spike, 18 Oct).** ChatGPT stays one login, owned by Hermes, so the owner never signs in twice and no refresh token is copied. The ChatGPT app's `/api/infer` forwards to a new raw-inference route in the `wizard-os` Hermes plugin, next to the existing `/ai-usage/chatgpt` route that already lets the app show usage without holding a token. The route calls the provider directly with the app's messages only: no agent, persona, memory, skills, session record or tools; a pinned model allowlist; fail closed. Hermes' agent API (`/v1/chat/completions`, `/v1/responses`) is not usable for this, because it always runs the full agent with tools and memory. A second independent Codex CLI login stays a fallback only: it needs a phone approval and `codex exec` is a coding agent with tools, not a plain model call.
2. **Until the App Manager writes grants** ([PERMISSIONS.md](PERMISSIONS.md) rollout), the Router reads a hand-written grants file; with no file configured it runs report-only. The owner's daily box runs it with `enforce: true`.
3. **Cost and quota.** Subscription quotas are shared with the owner's own agent use. The router should show per-app usage and let the owner cap an app; shape to follow the first real usage data.
