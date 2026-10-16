# Supervisor prototype — implementation checkpoint

Approved outcome: `spec/SUPERVISOR.md`. Prototype isolated from production maintenance; no default-install cutover. Source lives in this component subtree pending extraction.

## Current state
- Parent owns package, HTTP/MCP, UI and live integration on `prototype/supervisor-v01`.
- Engine integrated and pushed; parent independently matched remote hashes and ran 31 real engine/HTTP tests on Thales. Current runnable source `df8ddce`; shared-core UI and private Agent Service adapter included.
- Opus design verified: first-party `claude-opus-5-5`, valid JSON, nonempty artifact, no permission errors. Initial full-HTML call timed out; compact design contract succeeded. Parent implemented `web/index.html` from `docs/DESIGN.md`.
- WAM manifest/container/shared-function checks pass; Python and JS syntax pass. Container/live-inference acceptance is next via durable key `supervisor-package-df8ddce-01`, source `/Volumes/ThalesMedia/Supervisor/prototype`, output `/Volumes/ThalesMedia/Supervisor/evidence/df8ddce-01`. Read-only review `deleg_72517414` completed and its receipt is pending delivery; inspect it on resume. Browser and managed install remain undone; nothing installed.

## Next exact gates
1. Consume engine completion, verify SHA and remote tests, integrate its committed files only; reconcile snapshot shapes in UI and exceptions in server.
2. Package via `python3 scripts/package.py`; checker against current WAM. Compose bundles stdlib source in stock Python image (normal template mechanism), root-only app-data init then uid/gid 1000. Record pulled image digest/provenance.
3. Exercise on Thales external media, with container/test/browser jobs through durable heavy queue where sustained. No VPS builds. Test actual canary `/fault` → Supervisor tick → repaired `/function` and new `/job` receipt. Engine must send canary idempotency key correctly. Canary uses bearer from generated installation env, never source.
4. Complete actual Agent Service private-reasoning adapter and admitted-notification receipt transport. Relevant current Service routes: `/wizard/hermes/api/sessions` create then PATCH hidden=true then GET assert hidden BEFORE any input; `/wizard/hermes/v1/runs` with stable Idempotency-Key and configured model/provider unchanged. Operator preset routes are a different model; never use that as substitute. Freeze packet, bounded recommendation only, no authority from model text. Current package exposes MCP recommendation but is not yet automatic inference-connected.
5. Complete feedback-to-active scoped interpretation/reversal and replay; unknown prose stays candidate. Current browser records candidates and disables existing rules; it must not claim arbitrary text is understood.
6. Fresh read-only consequential review of approval replay, authority/CSRF/session surface, crash/retry ownership and truthful verification. Repair concrete blockers.
7. Actual managed install in isolated target using WAM's private source adapter (archive this exact component subtree), not manual registry-only installation. Source pinned/pushed first. No local Docker build; stock source bundle or Thales-built image only. Do not install into live maintenance slot/default.
8. Integrate reachable System entry and verify phone deep-link inside shell, nested/root Back, approval + feedback readback. Use owner-private origin in deployment config only. No public exposure. Existing System UI under `web/system/` in wizard-ux; preserve current live base and shared ownership, isolated branch/target-specific promotion.
9. Independent parent live readback; final first link is tested in-Wizard System/Prototype destination. Clearly distinguish installed prototype scope from production maintenance takeover. Record project transition and review evidence.

## Current interface / security notes
- Prototype shipped config enrolls only two synthetic targets, auto-granted service repair + internal-job rerun. Existing services, jobs and alerts are untouched.
- `server.py`: owner-network reverse proxy required. Read-only state is available to that network; mutations need operator bearer or one-use ticket → HttpOnly session + CSRF + exact Origin. Bootstrap expires in five minutes; browser session in one hour; restart invalidates sessions. Operator token length >=24.
- Validate same-origin sibling-app risks before any real-target enrollment. Never treat the prototype UI cookie as general platform authority. Model tool permissions do not grant owner approvals.
- Normal `/api/tick` and engine background loop use same lock; independent domain engine owns transaction correctness. Sanitize exceptions and probe evidence before displaying secrets.
- Set_rule must not convert arbitrary candidate prose to grants. Approvals bind exact immutable target/action/config/current generation and expire.

## Source commands
`python3 scripts/check_view.py` is a source-only check. `python3 scripts/package.py` waits for integrated engine. Actual install/run evidence remains required. Workload placement: `/Volumes/ThalesMedia/Supervisor/` on Thales. System source and this checkpoint are shared on the pushed prototype branch.
