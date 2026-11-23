# Wizard stable: which Hermes version every Wizard box runs

**Status:** direction approved by James on 21 Oct 2026 (DECISIONS #74); on 15 Nov 2026 James decided that WizardOS maintains its own Hermes fork and Hermes never updates automatically (DECISIONS #116, which replaces #74's "never a fork"). The details below are a proposal by Archimedes.
**Owner:** Archimedes. The `hermes-agent` app repo owner reviews the image change in step 5.

**Shared lock implementation:** [contract](../spec/HERMES_LOCK.md) and
[baseline/discovery evidence](HERMES_LOCK_EVIDENCE.md). This freezes the existing
exact September pin; it does not declare the latest release safe or authorize a
downgrade of alongside installations. Hermes automatic changes stay paused,
independently of unrelated Wizard app updates. A recommendation precedes admin
approval and an explicit coordinated promotion; elapsed release age alone is
never approval.

## The idea in one paragraph

Hermes ships a new release roughly every few days, and some of them break things. In October, 0.22.x had open reports of lost and duplicated conversations, and one update restored a three-week-old copy of someone's chat history. So Hermes never updates itself on a Wizard box. **The WizardOS Hermes fork ([`defleur-agents/hermes-agent`](https://github.com/defleur-agents/hermes-agent)) is the Wizard Hermes track** (James, 15 Nov 2026, DECISIONS #116). Its `main` is one tested upstream release plus Wizard's own local edits, and every Wizard box runs that. The local Wizard edits ride on the fork as ordinary commits, kept small, and are re-applied and re-verified on every new candidate. Rolling back is one step.

## The path of a new Hermes version

1. **Weekly gate.** The Sunday job (`07dec4c126fb`, [HERMES_WEEKLY_GATE](HERMES_WEEKLY_GATE.md)) names the newest upstream final release that qualifies and what blocks it.
2. **Our test.** The candidate plus the fork's local edits passes a fresh-VM acceptance run (the checks below) and an isolated rehearsal of the session API against a copy of a real `state.db`. The local edits' own tests pass on the candidate.
3. **James says go.** Nothing moves past our test without his yes.
4. **Telos first, then Miguel and the other testers.**
5. **A few days of soak** on those boxes.
6. **Official WizardOS update**, on James's yes: the fork's `main` moves to the candidate plus the edits, and a new install snapshot pins it. Before that yes, the fork image runs only from a **candidate snapshot** (`releases/candidates/`, never named by latest or stable; format and tools in [`releases/README.md`](../releases/README.md#hermes-fork-candidates-wizard-os723)).

## Done when

1. Every install snapshot (`releases/<version>.json`) names one Hermes release: the upstream tag and commit, the container image digest, the date it passed our tests, and the release to roll back to. `tools/check_release.py` rejects a snapshot that is missing any of these.
2. A fresh install gets exactly that Hermes. An alongside install (a box that already ran Hermes) is told when its Hermes differs from Wizard stable, and the owner can move to Wizard stable with one command. That command takes a backup first and rolls back automatically if the update fails.
3. Every candidate release has a test record in `docs/acceptance/` from a fresh Thales VM. The record covers the checks listed below, including an update and a rollback.
4. The weekly release check posts one message saying whether there is a candidate and what is blocking it. Promoting a candidate to Wizard stable needs one "yes" from James.

## Where things stand (checked 3 Nov 2026, UTC)

**HOLD: no newer final image qualifies for the acceptance run.** Stable and latest snapshot **0.3.102** still pin `v2026.9.24` at source `f97608f178d1ffeca59860195ab7da295f7c8e5f`, image digest `sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7`. The [dated discovery record](acceptance/hermes-candidates-2026-11-03.md) preserves source SHAs, image digests, both architecture configs, issue qualifications and check receipts. This is the no-eligible-candidate result, not a runtime PASS.

Every final release newer than the September pin was checked. **P** below means the published image lacks a full OCI source-revision label on **both linux/amd64 and linux/arm64**; image/tag identity is unproven, not an observed unequal revision. The current checker fails closed on this. Open session, compaction, database and gateway reports also require adjudication; keyword hits alone are not confirmed regressions.

| Final tag | Seven full days public (UTC) | Exact reason not eligible now |
|---|---|---|
| v0.22.7 | 10 Nov 2026 21:53:16 | Too young; P. No version-search hits yet does not clear unversioned reports. |
| v0.22.6 | 9 Nov 2026 17:18:36 | Too young; P; exact-tag session-resume failure report #148581 remains open. |
| v0.22.5 | 30 Oct 2026 05:28:45 | P; gateway report #143478 and compaction-input report #144449 need adjudication. |
| v0.22.4 | 28 Oct 2026 18:49:24 | P; migration/resume report #143150 and mixed native/third-party session-write report #143818 need adjudication. |
| v0.22.3 | 28 Oct 2026 12:21:11 | P; exact-release gateway-startup report #142579 needs adjudication. |
| v0.22.2 | 22 Oct 2026 08:21:32 | P; Docker/s6 gateway-status report #139799 and pending-reply report #141438 need adjudication. |
| v0.22.1 | 21 Oct 2026 23:59:24 | P; exact-release ACP session start/resume report #138949 needs adjudication. |
| v0.22.0 | 21 Oct 2026 03:21:46 | P; compaction report #139538 has unresolved incident-version/causality questions. |
| v0.21.7 | 19 Oct 2026 05:53:41 | Final Docker manifest returns HTTP 404; desktop transcript-tail report #138454 also needs adjudication. |
| v0.21.6 | 15 Oct 2026 11:51:57 | P; the unchanged image digest also has a previously proven runtime/tag mismatch ([22 Oct record](acceptance/hermes-v0.21.6.md)). |

**Next age gate:** v0.22.6 reaches seven days on **9 Nov 2026 at 17:18:36 UTC**; v0.22.7 follows on **10 Nov at 21:53:16 UTC**. These are earliest age-only reconsideration dates, not bookings or promised eligibility. Already-aged finals could be reconsidered sooner only after upstream publishes verifiable matching image provenance and relevant reports are resolved or shown inapplicable; neither has a known date. No scheduled run was created or changed.

No VM, Docker pull, acceptance run, app-image PR, release-snapshot PR, promotion, live Hermes update or live cron edit was performed. There is no promotion decision for James yet. Once discovery clears, this task's Linux acceptance route is a fresh VM on forum under `/srv/work`, admitted through `wizard_heavy_submit host="forum"`; earlier Thales receipts below remain historical evidence, not a substitute.

## Rules for Wizard stable

- **Which releases can be candidates:** a final upstream tag (never a test build), public for at least seven days, with no open upstream reports against it about session storage, compaction, the database or the gateway. A candidate for container installs also needs a published final image.
- **The test run on Thales:** start a fresh VM on the candidate, behind the Agent Service, and check that:
  - a thread sends and receives;
  - a helper's result comes back to the thread that started it;
  - Markdown replies render;
  - a long conversation keeps its reasoning after compaction;
  - the database is intact before and after a restart;
  - a scheduled job fires;
  - an update followed by a rollback both work, and history is still there afterwards.
- **The order a release reaches boxes:** the path above: weekly gate, our test, James's go, Telos, then Miguel and the other testers, a few days of soak, then the official WizardOS update.
- **Local Wizard edits:** they live on the fork as commits on top of the upstream release, each with its own tests, never as uncommitted changes on a box. Each candidate is checked with those edits applied, and their tests run again. An edit upstream has taken over is dropped from the fork. Where one is useful upstream too, offer it there as a pull request. A Hermes feature we don't want on Wizard boxes is still switched off in settings rather than cut out of the code.
- **Box working trees match the fork.** A box's `~/.hermes/hermes-agent` is a checkout of the fork's `main` with an empty `git status`. Restarting a gateway is the box owner's agent's job, on a quiet gateway.

## Steps

1. **Record the pin.** Done 21 Oct: every snapshot from 0.3.23 on needs a `hermes` block (0.3.22 was cut the same minute without one) (see `releases/README.md`), and `check_release.py` validates it. Older snapshots are history and stay as they are. The first 0.3.23 carries the September pin as `"test_record": "none: carried over…"`. *Check:* `python3 -m unittest tools/tests/test_check_release.py -v`; the online check proves the tag's commit upstream, the image digest on Docker Hub, and that the `hermes-agent` app really builds from that digest.
2. **Test a candidate on Thales.** One script starts a fresh VM on a given tag or image, runs the checks above and writes the record to `docs/acceptance/hermes-<tag>.md`. Reuse the VM setup from the Connection Router test. *Check:* one full run against the version pinned today, and one against the next candidate. Done 22 Oct: `tools/acceptance/hermes/`; [v2026.9.24](acceptance/hermes-v2026.9.24.md) (today's pin) and [v0.21.6](acceptance/hermes-v0.21.6.md) both pass all seven checks, with update from the pin and rollback to it. The v0.21.6 image is built from `a28a5d03`, 39 commits before its tag's commit; it is not promotable as that tag. Newly tested snapshots separately record `hermes.image.commit`, and the online checker requires both Linux image revisions to equal the tag commit.
3. **Weekly candidate report.** Extend the existing Sunday cron job "Weekly Hermes release stability gate" so that it also reads the snapshot pin, checks Docker Hub for a final image and names the candidate. It posts one message in the Hermes release-check thread. *Check:* that Sunday's post names the candidate and what is blocking it. **Staged 23 Oct:** `tools/hermes_candidate_report.py` performs read-only snapshot/tag/image/issue discovery; [the existing-job prompt addition](HERMES_WEEKLY_GATE.md) is ready. The live job was not changed under the overnight no-live-Hermes rule, and no post has been sent.
4. **One-command update for alongside boxes.** Turn James's overnight update script into `wizard hermes update --stable`: backup, wait until quiet, exact tag, check, automatic rollback. It never runs plain `hermes update`. *Check:* a test box goes through an update and a forced rollback with its history intact. Built 23 Oct as `wizard hermes status` / `wizard hermes update --stable` in `tools/wizard` (behaviour, exit codes and receipt: [WIZARD_CLI](../spec/WIZARD_CLI.md#updating-this-boxs-hermes-alongside-mode)); record: [acceptance/hermes-update-stable.md](acceptance/hermes-update-stable.md). Moving to a version is still the owner's command; promoting a version to Wizard stable still needs James.
5. **Move fresh installs off the September image.** Point the `hermes-agent` app at the first candidate that passes and has an image. The v0.21.6 image is blocked by source/tag mismatch; v0.22.2 has a final image but lacks revision provenance and fresh acceptance and has open risk reports requiring review. No promotion approval is ready ([23 Oct evidence](HERMES_WEEKLY_GATE.md)). Then cut a new snapshot. *Check:* a fresh install on Thales reports the new version, and its test record is linked from the snapshot.

**Later:** an update prompt in the Wizard UX for alongside owners; Wizard stable for other agent runtimes (Pi).
