# An app page must not act as the Wizard owner

**For Jan and Miguel · 1 November 2026 · Proposal for review, not permission to enable or release**

## The problem: one bad preview can reach the control panel

An app displays an uploaded document or a model reply. Suppose a rendering mistake lets that content run JavaScript. Today, Wizard normally loads app pages in frames on the shell's own origin: the same scheme, host and port. The script can call the shell's server routes from the owner's browser. The server recognizes the owner through the trusted network/proxy identity; that identifies whose browser arrived, not which page inside it asked. Same-origin checks do not distinguish the app from the control panel. An app need not be deliberately malicious: one unsafe preview is enough.[1][11]

For example, the script requests the chat list, then submits an agent run. The browser supplies the same network-owner identity that legitimate shell requests use. On Android there is another route around browser isolation: the current source attaches `WizardOSNative` and `WizardOSDevice` using `addJavascriptInterface`, which exposes them to every WebView frame. Sandboxing frames cannot remove those native objects.[7]

This is an authority problem, not a Notes problem. Sanitizing previews remains necessary, but the platform must also contain a compromised app. We have not inspected the running owner box; exact live exposure, including the disputed notebook deployment, remains unverified.[11]

## What happens if we leave it

A hostile app script can attempt owner reads and writes: chats, agent runs, Settings, and Store operations, including installing or removing eligible apps. Private-agent notebook routes widen the data at risk when their owner view is enabled; refusing agent credentials does not stop a request arriving as the human owner. Native device hooks add recording, clipboard and other device actions, subject to each method's current checks.[1][7][11]

Third-party apps make this worse: every publisher and every content renderer becomes part of the owner's security boundary. App permissions cannot reliably mean “only these operations” while the page can bypass them through owner routes. Fixing one notebook endpoint leaves the general problem intact. The notebook containment draft is useful temporary protection, not the requested solution.[6]

## What exists, and what does not

The starting point is four **open, default-off draft PRs**, not a fresh implementation. Heads below were checked against GitHub and `heads.json`; links identify each draft.

| Component | Draft and pinned head | Existing work |
|---|---|---|
| Shell | [UX #327](https://github.com/humanitylabs-org/wizard-ux/pull/327), `f85d6231` | Navigation-only token bootstrap; opaque frames; narrow Back, appearance, field insertion, confirmed sharing and bounded transcription[2] |
| Agent Service | [#100](https://github.com/humanitylabs-org/wizard-agent-service/pull/100), `eab0b021` | Owner-route token checks in addition to existing identity and permission checks[3] |
| App Manager | [WAM #168](https://github.com/humanitylabs-org/wizard-app-manager/pull/168), `247cc12a` | Store-listener token checks; link-source grant restrictions[4] |
| Platform contract | [OS #163](https://github.com/humanitylabs-org/wizard-os/pull/163), `51db0d5b` | Proposed browser boundary contract[5] |

Separate [Service #302](https://github.com/humanitylabs-org/wizard-agent-service/pull/302), `f2c5182b`, hides private/hidden notebooks by default; it does not isolate apps.[6]

The later **r5** synthetic browser test on Forum passed **45 checks**, including server-observed denials for hostile requests, positive shell-only notebook reads, Back, sealed field insertion and two skins. It supersedes earlier “not run” notes for that fixture. Its receipt says `release_ready:false`; native and real Store installs were not proven. Three sandbox service-worker errors were recorded and remain to be triaged. Prior focused Opus source review allowed continuation only with release requirements outstanding.[9][10]

**Still missing:** real app-data, durable-state, media and stream adapters; native isolation; separate account/recovery-listener protection; actual package compatibility. The app inventory (“census”) is static public-source evidence, not proof that installed apps work.[7][8]

## Proposed solution: contain apps, then replace legitimate access

1. **Seal app documents.** Keep opaque-origin sandboxed frames without `allow-same-origin`, top navigation or popups. Generated Pages and Chats modules must not run untrusted code inside the shell document. Separate non-owner origins may be needed for upstream applications, but require an explicit reviewed exception and equivalent isolation proof.
2. **Keep owner authority in the shell.** A shell-only secret, carried in a header, proves browser possession alongside existing owner checks. Audit all listeners and direct app routes; server-side adapters recheck grants without forwarding owner credentials. Protect bootstrap, rotation, caches and other callers.
3. **Use typed messages.** Extend the registered-frame channel with document-bound message ports for sensitive replies. Resolve publisher/repository and installation identity, never trust an app-supplied name; revoke on navigation, update, uninstall or grant removal.
4. **Build the missing adapters**, detailed in [ADAPTER-SKETCH.md](ADAPTER-SKETCH.md):
   - **App data:** `data.call({operation:"notifications.list",args:{limit:20}})`. Each operation has fixed input/output schemas and a fixed backend handler. A per-app manifest allowlist requests these operations; declaration alone grants nothing.
   - **Storage:** `state.read({area:"persistent",key:"draft"})` and `state.transaction(...)`, asynchronous and scoped to one installed app. Preserve drafts with revisions and verified migration; do not imitate synchronous browser storage.
   - **Media/transfers:** `media.open({resourceId,purpose:"play"})`, scoped upload handles and owner-selected downloads. Short-lived tickets authorize one resource and permitted methods, never owner APIs. Reuse resumable uploads; preserve seeking, progress and cancellation.
   - **Streams:** `stream.open({operation:"search.overview",args:{query}})`, with fixed event schemas, flow control, limits and cancellation; not a general socket proxy.
5. **Make native receivers main-document-only.** Jan validates frame, trusted document and navigation generation in Android/Mac receivers, including browser device hooks. Older unsafe clients cannot open app frames; no all-frame fallback.

Never build a generic owner-fetch relay, hand the shell token to an app, globally allow `Origin:null`, or disguise owner access as an unrestricted MCP call. A compromised app can still read data deliberately granted to that app: scope grants and keep private content out of ordinary renderers by default. These are proposed requirements, not shipped adapters.

## Prototype first, then migrate without dropping features

**Yes: prototype the adapters, not another notebook viewer.** Start with one plain and one draft-heavy fixture, plus media/streams; this is smaller than the default-system pilot. Miguel/Oscar own app migration; Jan owns native implementation and binary proof.[7]

The census estimates **120–228 active hours for the default-system pilot**, or **about 245–527 for the full public catalogue and additions**. The full total includes the pilot. These are active-work bounds, not calendar promises; private apps and new authentication problems add work.[7][8]

| Stage | Deliverable and proposed owner | Active hours |
|---|---|---:|
| 1 | Authority, identity and API review: Miguel; native design: Jan | 4–6 |
| 2 | Typed data/state and shared-client prototype: Oscar, Miguel review | 14–22 |
| 3 | Scoped media/uploads/streams: Oscar; Jan reviews native consumers | 14–24 |
| 4 | Android/Mac receivers and trusted-shell facade: Jan | 16–28 |
| 5 | App migrations: Oscar/Miguel; shell management panels separately | Pilot apps 36–88; all apps 160.5–387; panels 12–20 |
| 6 | Package/rollback: Oscar/Miguel; browser/device acceptance: Oscar + Jan | Packaging 8–12; QA 16–28 |

Shared work totals 84–140 hours, including panels and platform components; do not count those twice. Pilot app integration covers 11 non-platform packages including recovery, not 11 iframe rewrites. Service-only packages need listener/grant checks, not invented views.[7]

**Review requirements:** approve contracts, prove the prototype, then test packaged fresh installs and installation beside an existing Hermes (“alongside”). Keep enforcement off until every installed app passes; quarantining incompatible apps needs James’s approval. Rerun r5-style attacks at exact candidate heads with server-side denial evidence, plus stale channels, cross-app identity, replay, permission revocation and separate listeners. Exercise real Store install/removal/update and provider grants. Require real APK and Mac evidence, app-parity checks against approved behavior, and inspected in-shell screenshots on two skins: Appearance v1 `--wz-*`, live changes, dark standalone fallback and opaque text panels. Back never exits; drafts, recordings, uploads, background playback and actual trusted confirmations must survive.

## Questions for review

**Miguel:** (1) Approve source-qualified install identity and operation admission, including the duplicate `profiles` publishers? (2) Which listeners need authentication adapters or isolated origins, and how should unattributable old storage be handled? (3) Who signs off permission increases, provider selection changes and rollback state preservation?

**Jan:** (4) Can every Android/Mac receiver enforce trusted-main-document identity without an all-frame fallback, and what minimum client versions follow? (5) Which native capture, recovery, download and background workflows must the prototype cover before migration starts?

## How Oscar executes this

These are ordered proposed task cards, **not dispatched work**. Each produces a draft candidate, acceptance results and evidence tied to exact heads.

1. **Contract — OS/WAM `spec/browser-trust-adapters`:** resolve Miguel/Jan questions; read `COMPONENTS.md`; record REUSE/EXTEND/NEW and handlers. Evidence: approved schemas, listener inventory, denial matrix, checker fixtures.
2. **Prototype — UX/Service/WAM `feat/browser-trust-data-state`:** extend existing channel/client; migrate a plain and draft-heavy fixture. Accept unknown/cross-app/stale denial, durable readback and old-state rollback. Evidence: tests and two-skin screenshots.
3. **Transfers — UX/Service `feat/browser-trust-media-streams`:** reuse uploader/content/stream owners. Accept Range/HEAD, reconnect, cancel, expiry and no credentials upstream. Evidence: resource/stream traces and cleanup checks.
4. **Native — UX/Mac wrapper `fix/browser-trust-native-main-document`:** Jan implements/reviews; Oscar coordinates dependencies. Accept hostile-child denial and working trusted device flows. Evidence: APK/Mac identities, native logs and device recordings.
5. **Migration — each app repo `migrate/browser-trust-<source>-<app>`:** migrate census families, defaults first; keep Store/Agents/Setup as shell-controlled panels. Accept package authentication, `app-parity-gate` and grant separation. Evidence: per-source checklist, pinned packages and screenshots.
6. **Release rehearsal — OS `test/browser-trust-release-rehearsal`:** isolated fresh/alongside upgrade and rollback, full attack and app-parity suites. Evidence: exact-head results, package digests, two skins, APK/Mac receipts and remaining failures.

Keep the flag default-off, PRs draft and James's live box untouched. Use synthetic fixtures, `android-build-forum` and the durable worker for heavy Linux/Android tests; Thales for Mac. Stage before any separately approved live release. Decide implementation details and repairs independently; ask Miguel/Jan about contract/native tradeoffs. Ask James only about changed product scope, private-content exposure, security exceptions, extra spend or release authority. This document authorizes none of those actions.

## Sources

[1] https://github.com/humanitylabs-org/wizard-os/issues/133 — Browser trust issue
[2] https://github.com/humanitylabs-org/wizard-ux/pull/327 — UX boundary draft
[3] https://github.com/humanitylabs-org/wizard-agent-service/pull/100 — Service boundary draft
[4] https://github.com/humanitylabs-org/wizard-app-manager/pull/168 — WAM boundary draft
[5] https://github.com/humanitylabs-org/wizard-os/pull/163 — Boundary contract draft
[6] https://github.com/humanitylabs-org/wizard-agent-service/pull/302 — Notebook containment only
[7] ./APP-CENSUS.md — Static app census and effort bounds
[8] ./CENSUS-VERIFICATION.json — Census coverage verification
[9] ./brief-sources/r5-receipt.json — Forum r5 synthetic receipt, local read-only copy
[10] ./review/VERDICT.md — Prior focused source review
[11] ./PLAN.md — Earlier engineering plan
