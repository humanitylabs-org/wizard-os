# Shared Hermes lock: implementation evidence

## Baseline, not a newly certified latest release

The frozen pin is the existing stable snapshot 0.3.39's upstream
`v2026.9.24` / `f97608f178d1ffeca59860195ab7da295f7c8e5f` and official
image `sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7`.
The [committed baseline acceptance](acceptance/hermes-v2026.9.24.md) passed
seven checks but records a compacted-history visibility limitation. This is not
an assertion of universal safety, nor approval to downgrade an existing host.
No 0.21.7 or 0.22.x promotion is made.

Read-only discovery on 25 October 2026:

- GitHub's annotated `v2026.9.24` tag dereferenced to the commit above.
- GHCR `humanitylabs-org/hermes-agent:v2026.9.24-wizard2` resolved to manifest
  `sha256:e8ad921a23c7a2144b9c89902cb16908b68020fcd4f301bf8a2dbe2da75f3f5f`.
  Its amd64 and arm64 configuration labels both name upstream commit
  `f97608f178d1ffeca59860195ab7da295f7c8e5f` and the official September base.
  The lock freezes this wrapper by digest, not its mutable tag. This is registry
  provenance evidence, not a new wrapper behavioral canary.
- `python3 tools/hermes_candidate_report.py --json` returned **HOLD**.
  The newest age-eligible release was v0.22.2, with no proven image/tag revision
  identity, no exact fresh acceptance, upstream risk-search hits requiring human
  adjudication, no completed soak or approval. The report excluded v0.22.3,
  v0.22.4 and v0.22.5 as younger than seven days. Risk-search matches are not
  automatically confirmed regressions.
- PR [wizard-agent-service#142](https://github.com/humanitylabs-org/wizard-agent-service/pull/142)
  documents the 0.22.5 owner-history regression. Its review also flags retention,
  retry-input and routed-agent coverage risks. These reinforce HOLD; they are
  not a safety certification of a different release.

## Owning paths and boundaries

- App Manager `get.sh`: validates snapshot Hermes identity and agent recipe
  against the public shared lock before checking out or installing components.
- `wam/release_pins.py`: even unpinned ordinary Hermes installs select the exact
  frozen recipe instead of the live index. `release_updates` skips installed
  Hermes independently of unrelated app defaults. `app_update`, flag-first/bulk
  CLI passthrough and the host transactional updater require a reviewed promotion
  plus explicit matching operator id. Automatic OS updates clear that id.
- `tools/wizard`: standalone alongside updater reads the public lock; an arbitrary
  `--release` cannot bypass it. The gate precedes runtime access.
- Agent Service `ops/agent-runtime`: normal/import defaults consume the same
  vendored lock. Restricted helper execution always sets `AGENT_IMAGE`, preventing
  ambient `latest` inheritance. Normal helper image overrides are refused.
  Existing non-import agent apply/start compares immutable image IDs and refuses
  a version change without coordinated authorization; stop/delivery stay usable.

Administrator escape hatches remain explicit, **not covered by a claim that all
installed Hermes runtimes are centrally controlled**: stock `hermes update`,
owner cron, raw Docker/Runtipi administration, direct use of vendored restricted
Compose, and separately journalled imported/recovery runtimes. The recovery
`import-image/build.sh` pins a different explicit upstream source commit; its
Dockerfile's pre-existing base digest returned GHCR 404 during discovery. That
specialist recovery build was not changed or exercised here. Inventory these
paths before a coordinated fleet rollout; do not disable unrelated app updates.

## Verification and remaining gates

All changes were developed in isolated worktrees from fresh origin/main:

- wizard-os `e34e7a2d7946d74c7bb5a26601cf560aaae555c6`.
- wizard-app-manager `73f06acfc1c41e46eb156155b4e8848b7d04f44e`.
- wizard-agent-service `34eaaa35f7d98e8f0a4a377cde9bffd7b4281acf`.

Regression tests exercise installer refusal before checkout, absent/mismatched
locks, normal and flag-first update refusal, preservation of unrelated app
updates, exact normal/import/restricted image defaults, and refusal to silently
converge existing agent images. Gate tests cover seven complete days (including
one second short), future approval, missing evidence and approval without an
explicit execution id. Transaction/rollback tests retain their isolated synthetic
revision fixtures; policy tests separately use the real frozen lock.

No production deployment, live runtime mutation, new release snapshot, clean-VM
install or real cross-version update/rollback was performed. Fresh and alongside
clean-VM acceptance of the final merged installer remains a **release gate**, as
do non-author admin review and James's approval for this all-install default.
The current live host must not be downgraded to the frozen baseline. Promotion
requires the recommendation, exact-source canary and rollback evidence described
in [the contract](../spec/HERMES_LOCK.md).
