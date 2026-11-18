# Weekly Hermes candidate gate — staged integration

This is HERMES_STABLE step 3's read-only evidence helper, not an updater.

**Track (James, 15 Nov 2026, DECISIONS #116):** the WizardOS Hermes fork
([`defleur-agents/hermes-agent`](https://github.com/defleur-agents/hermes-agent))
is the Wizard Hermes track, and Hermes never updates automatically. Local Wizard
edits ride on the fork and are re-verified on each candidate. The gate is the
first step of the path: weekly gate, our test (fresh-VM acceptance plus an
isolated `state.db` rehearsal of the session API, with the fork's local edits
applied), James says go, Telos first, then Miguel and the other testers, a few
days of soak, then the official WizardOS update on James's yes. The live job is
`07dec4c126fb`.
`tools/hermes_candidate_report.py` reads the local **stable snapshot**, selects the
newest final upstream release with seven full days of public soak, resolves its
source commit, checks its final Docker Hub image/digest and both Linux revisions,
and lists version-mentioned open risk-search hits. It does not equate search hits
with confirmed regressions, or an acceptance filename with a passed exact-image run.

```sh
python3 tools/hermes_candidate_report.py --json
python3 tools/hermes_candidate_report.py
python3 -m unittest tools.tests.test_hermes_candidate_report -v
```

Requires `gh` authenticated for GitHub reads and network access to Docker Hub.
No changes to Hermes, cron, stable pointers, app recipes, or release files are made.
The helper always returns HOLD: the existing assessor must still review unversioned
issues, fix churn, exact acceptance evidence and the Archimedes soak diary.

## Existing Sunday job: append-only prompt change, not applied here

Keep the existing **Weekly Hermes release stability gate** job (`07dec4c126fb`),
its schedule, destination and assessment-only restriction. Do not create a second
job or a second message. Append this instruction to its current prompt when live
job changes are authorized:

> Also assess Wizard's Hermes stable track using a current wizard-os checkout.
> Read docs/HERMES_STABLE.md and run python3 tools/hermes_candidate_report.py --json.
> Read the stable snapshot's hermes pin, not releases/latest. Include its tag and
> commit, the newest seven-day-soaked final source tag/commit, whether its final
> Docker Hub image exists, its digest, and whether both Linux image revisions
> match that source tag. Missing provenance is a blocker, not permission to infer
> the commit from the image name. Read the complete risk-search results, then
> review unversioned upstream storage/session/compaction/database/gateway reports
> and recent fix churn. List the fork's local Wizard edits (commits on
> defleur-agents/hermes-agent main after the pinned upstream tag) and say whether
> each still applies cleanly to the candidate or has been taken upstream. Link a passed fresh-Thales acceptance record only if it
> covers the exact proposed source/image digest. Confirm the two-to-three-day
> Archimedes soak without installing or restarting anything. Produce only ONE
> concise assessment in this job's existing Hermes release-check thread, beginning
> HOLD or UPDATE TO <exact tag and SHA>. Name the snapshot pin, candidate and
> concrete blockers. Do not promote a snapshot, edit an app, or change a live box.
> If and only if every technical gate is satisfied, stage one approval question:
> "Promote <exact tag> (<source SHA>, image <digest>) to Wizard Hermes stable?
> Reply **yes**." Approval does not waive missing technical evidence.

The overnight instruction prohibits live-Hermes changes and messages to humans,
so this patch is **staged, not installed**, and no Sunday post is claimed. Step 3
is not complete until the existing job is extended and its single Sunday output
is checked against the pin and live evidence.

## 23 Oct dry run (not a promotion recommendation)

The actual helper run selected **v0.22.2**, source
`d923a5eb487a17c0a68801bba9ef0f56c81040a8`, published 15 Oct.
Its final image resolves to
`sha256:36099926da316742423544e055d4734777105ffe6341873af5459b957d0c2919`,
but lacks an OCI source-revision label, so image/tag identity is unproven.
There is no fresh Thales acceptance record for this tag in this repository.
v0.22.3, v0.22.4 and v0.22.5 have not had seven full days of public soak.
Open version-mentioned reports include [rollback/resume history damage](https://github.com/NousResearch/hermes-agent/issues/140060)
and [gateway regression between adjacent releases](https://github.com/NousResearch/hermes-agent/issues/141509).
These are upstream reports requiring assessment, not independently reproduced bugs.

The already-tested v0.21.6 container is also **not eligible**: it runs `a28a5d03`,
not source tag `818c13be`, and has no OCI revision label. Its seven-check pass
cannot be reused as a test of the tag's source commit.

**Current decision: HOLD. No approval request is ready.** Once technical gates
pass, the exact question above needs only **yes**; do not ask James to approve an
unproven image or move his live Hermes merely to remove this blocker.
