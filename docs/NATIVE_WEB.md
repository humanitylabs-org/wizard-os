# Native web capabilities: search, page reading, provider upgrades

**Status: Proposed.** This is an architecture proposal and build brief. It is not a decision in [DECISIONS.md](DECISIONS.md), it records no release, and it does not claim that any capability is installed, tested on a box or on by default. Increment 1 is open for review as [wizard-search#17](https://github.com/humanitylabs-org/wizard-search/pull/17).

## Outcome

Every new Wizard gets keyless public-web search and page reading out of the box. Paid or specialised providers are separate upgrades that the owner installs and approves, and apps and agents reach them through the existing platform paths. Nothing here needs a Hermes fork, a personal server or another router.

## Where things stand (source audit, 29 Oct 2026)

| Capability | Packaged today | In the latest/stable release (0.3.73) default apps |
|---|---|---|
| Keyless web and image search ([wizard-search](https://github.com/humanitylabs-org/wizard-search), bundled SearXNG) | Yes | **No.** App Manager `main` lists `web-search`, but release-pinned boxes only take slots from the release's `default_apps` |
| Rendered visible-text reading and screenshots ([browser](https://github.com/oscarhenrycollins/browser) MCP `read_page`, `screenshot`) | Yes | Yes |
| Paid search lanes (Firecrawl, Bright Data) | Env keys injected straight into Search; before increment 1, a key alone turned on automatic paid racing | n/a |
| Safe arbitrary public-URL reading | **No.** `read_page` checks the URL scheme only, with no egress, redirect, subresource or rebinding protection and no per-request isolation | n/a |
| Semantic article/PDF extraction, human browser takeover | Not offered by the tools inspected | n/a |

The real gaps are getting into a release as a default, an explicit spend/provider policy, public-read safety, and structured read errors and provenance. Search and rendered reading already exist.

## Architecture

```
owner agent ── stock Hermes MCP ── Agent Service /wizard/mcp (existing bridge)
                                    ├─ Search tools ── bundled SearXNG (default, free)
                                    │                └─ approved provider apps (upgrades)
                                    └─ Browser tools ─ isolated public-read Chromium
other apps ── Connection Router service routes ── the same installed capability/provider apps
App Manager: install, grants, advertised endpoints.  Provider app: its own vendor credential, billing, readiness, request.
Router: provider choice and approved substitutions.  Search: search semantics.  Browser: rendering.
```

- **REUSE** Search for web and image queries, Browser for rendered reads and screenshots, the Agent Service bridge for agents ([spec/AGENT_BRIDGE.md](../spec/AGENT_BRIDGE.md)), and the Connection Router plus App Manager grants for apps ([spec/CONNECTION_ROUTER.md](../spec/CONNECTION_ROUTER.md), [spec/PERMISSIONS.md](../spec/PERMISSIONS.md)).
- **EXTEND** the Router with approved provider selection and fallback policy, rather than adding a second router. Search keeps a local policy gate until provider apps and the Router own it.
- **NEW**, only later: separately installable provider apps (candidates are Firecrawl for richer extraction and Bright Data for blocked sites; neither is verified or packaged yet). One provider can advertise several capabilities, and a capability does not belong to any one vendor.
- Private agents keep their current grants and seals. They never fall back to public tools. Attested private search (Tinfoil) is a separate approved route, never an automatic public fallback.
- "Self-hosted" is not "confidential". SearXNG sends queries to public engines.

## Policy principles

1. The default spends nothing. A configured key is never consent to spend or to send data to a new provider.
2. Upgrades are explicit, per capability, and revocable: an allowlist and order, public/private classification, bounded attempts, time and cost, and provenance in every result.
3. Invalid policy fails closed to the no-spend default and says why.
4. Existing owner choices move to the new model by an explicit, compatible migration. They are never silently reinterpreted, and where a choice is the owner's, the migration surfaces it instead of making it.
5. AI-inference consent (for example Search overviews through Tinfoil) is separate from search spend. Neither one grants the other.
6. Unavailable, blocked, empty and setup-required are different outcomes, and each is reported as itself.

## Increments

1. **Keyless search baseline** ([wizard-search#17](https://github.com/humanitylabs-org/wizard-search/pull/17), draft). Search 0.3.2 adds `WIZARD_SEARCH_PROVIDER_POLICY` with three modes: `free-only` (the default), `approved-upgrades` (named lanes only) and `legacy-race` (the explicit 0.3.1 behaviour). Upgrade-lane calls refuse before any network request, and status reports blocked configured lanes by name. Open owner decision: whether 0.3.1 installs with paid keys stay free-only after upgrade (the current proposal) or have a policy pre-set by an owner-confirmed step. Container and real-SearXNG checks are staged, not run.
2. **Public Browser reader.** Isolated per-request context, egress enforced where Chromium connects (navigation, redirects, subresources, DNS rebinding, metadata and private ranges), bounded size and lifetime, and structured provenance and errors. Existing tools and deliberate local-app browsing stay as a separate mode. Needs a security review and real-browser negative tests.
3. **Integrated fresh-box search then read.** Pin Search in a *new* candidate release's `default_apps`, never by rewriting a published release. Prove discovery and tool execution through stock Hermes MCP on fresh and alongside installs, on amd64 and arm64.
4. **Provider upgrades.** Move Firecrawl, then Bright Data, into connector-owned packages, and extend Router policy. Prove install, connect, select and revoke, with no secret transfer and no automatic activation.
5. **Interactive handoff and specialised sources.** Reuse the shared vault and companion controls, with the owner approving account use. Transcript and PDF sources follow the same capability interface.

## Acceptance (whole programme)

1. A fresh candidate install discovers Search and Browser through real stock-Hermes MCP, searches a real public query, reads a result and gives a cited answer, with no vendor keys or personal hosts.
2. Free-only makes zero paid requests even with stale keys and failures, proven by request counters or egress evidence. Upgrade routing is explicit and revocable.
3. Public reads cannot reach private or metadata networks by any path, and requests share no cookies.
4. Missing or stopped providers and denied permissions give accurate errors. Existing image, voice, overview and screenshot behaviour and owner configuration stay recoverable.
5. Installed immutable versions, effective grants and runtime behaviour are proven separately from source tests. A platform release comes only after fresh, alongside, amd64 and arm64 admission.

## Coordination

Overlapping open work: [wizard-search#16](https://github.com/humanitylabs-org/wizard-search/pull/16) (voice/translation; reconcile, don't overwrite), [wizard-connection-router#8](https://github.com/humanitylabs-org/wizard-connection-router/pull/8) (private-data service contract, not merged), [wizard-app-manager#215](https://github.com/humanitylabs-org/wizard-app-manager/pull/215) (grant/provider-choice preservation), and Tinfoil private-search work in [wizard-agent-service#239](https://github.com/humanitylabs-org/wizard-agent-service/pull/239), [#240](https://github.com/humanitylabs-org/wizard-agent-service/pull/240), [#244](https://github.com/humanitylabs-org/wizard-agent-service/pull/244) and [#247](https://github.com/humanitylabs-org/wizard-agent-service/pull/247).
