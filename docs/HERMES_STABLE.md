# Wizard stable: which Hermes version every Wizard box runs

**Status:** direction approved by James on 21 Oct 2026 (DECISIONS #74). The details below are a proposal by Archimedes.
**Owner:** Archimedes. The `hermes-agent` app repo owner reviews the image change in step 5.

## The idea in one paragraph

Hermes ships a new release roughly every few days, and some of them break things. In October, 0.22.x had open reports of lost and duplicated conversations, and one update restored a three-week-old copy of someone's chat history. We are not going to maintain our own trimmed copy of Hermes. Instead, Wizard picks **one upstream release that it has tested**, and every Wizard box runs that release. A new upstream release reaches Wizard boxes only after it has been public for a week, has passed our own test run on Thales, and has run on Archimedes for a few days. Rolling back is one step. Wizard ships no changes to Hermes code by default.

## Done when

1. Every install snapshot (`releases/<version>.json`) names one Hermes release: the upstream tag and commit, the container image digest, the date it passed our tests, and the release to roll back to. `tools/check_release.py` rejects a snapshot that is missing any of these.
2. A fresh install gets exactly that Hermes. An alongside install (a box that already ran Hermes) is told when its Hermes differs from Wizard stable, and the owner can move to Wizard stable with one command. That command takes a backup first and rolls back automatically if the update fails.
3. Every candidate release has a test record in `docs/acceptance/` from a fresh Thales VM. The record covers the checks listed below, including an update and a rollback.
4. The weekly release check posts one message saying whether there is a candidate and what is blocking it. Promoting a candidate to Wizard stable needs one "yes" from James.

## Where things stand (checked 21 Oct 2026)

- **Fresh installs already pin Hermes, but the pin is old and was set by hand.** Snapshot 0.3.21 installs the `hermes-agent` app (`oscarhenrycollins/hermes-agent` at `e8ae558`). That app wraps the official image `nousresearch/hermes-agent:v2026.9.24`, pinned by digest. That image is four weeks old and several releases behind.
- **Upstream's own "stable" label does not fit our purpose.** On Docker Hub, `stable` and `latest` both point to v0.22.2 (15 Oct). That is the release with the open reports about lost and duplicated conversations.
- **Releases do not always come in both forms.** v0.21.7 exists as a source tag only: Docker Hub has its test builds but no final image. So a release can be a candidate for source installs and still not be one for container installs.
- **Wizard does not control the Hermes version on alongside installs.** On a source install, `hermes update` follows upstream `main`, which includes code that has not been released yet.
- **Archimedes is now pinned to an exact tag by hand.** The overnight move from v0.21.6 to v0.21.7 (script `hermes_0217_update.py` on James's box) is the first working version of the promotion step. It takes a backup, waits until the box is quiet, swaps the version, checks it, and rolls back if anything fails.

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
- **The order a release reaches boxes:** first the Thales test run, then Archimedes for two to three days, then a new install snapshot, then everyone else.
- **Patches:** none by default. When one is unavoidable, it is a small patch with an open upstream pull request and a note saying when to remove it. It is deleted as soon as upstream fixes the problem. A Hermes feature we don't want on Wizard boxes is switched off in settings, so the code stays upstream's.
- **When we would fork after all:** only if upstream takes a direction we can't live with. For example, if Hermes's own installer insists on managing how Hermes runs on our boxes, or if the licence changes. None of these has happened.

## Steps

1. **Record the pin.** Done 21 Oct: every snapshot from 0.3.23 on needs a `hermes` block (0.3.22 was cut the same minute without one) (see `releases/README.md`), and `check_release.py` validates it. Older snapshots are history and stay as they are. The first 0.3.23 carries the September pin as `"test_record": "none: carried over…"`. *Check:* `python3 -m unittest tools/tests/test_check_release.py -v`; the online check proves the tag's commit upstream, the image digest on Docker Hub, and that the `hermes-agent` app really builds from that digest.
2. **Test a candidate on Thales.** One script starts a fresh VM on a given tag or image, runs the checks above and writes the record to `docs/acceptance/hermes-<tag>.md`. Reuse the VM setup from the Connection Router test. *Check:* one full run against the version pinned today, and one against the next candidate. Done 22 Oct: `tools/acceptance/hermes/`; [v2026.9.24](acceptance/hermes-v2026.9.24.md) (today's pin) and [v0.21.6](acceptance/hermes-v0.21.6.md) both pass all seven checks, with update from the pin and rollback to it. The v0.21.6 image is built from `a28a5d03`, 39 commits before its tag's commit; it is not promotable as that tag. Newly tested snapshots separately record `hermes.image.commit`, and the online checker requires both Linux image revisions to equal the tag commit.
3. **Weekly candidate report.** Extend the existing Sunday cron job "Weekly Hermes release stability gate" so that it also reads the snapshot pin, checks Docker Hub for a final image and names the candidate. It posts one message in the Hermes release-check thread. *Check:* that Sunday's post names the candidate and what is blocking it. **Staged 23 Oct:** `tools/hermes_candidate_report.py` performs read-only snapshot/tag/image/issue discovery; [the existing-job prompt addition](HERMES_WEEKLY_GATE.md) is ready. The live job was not changed under the overnight no-live-Hermes rule, and no post has been sent.
4. **One-command update for alongside boxes.** Turn James's overnight update script into `wizard hermes update --stable`: backup, wait until quiet, exact tag, check, automatic rollback. It never runs plain `hermes update`. *Check:* a test box goes through an update and a forced rollback with its history intact.
5. **Move fresh installs off the September image.** Point the `hermes-agent` app at the first candidate that passes and has an image. The v0.21.6 image is blocked by source/tag mismatch; v0.22.2 has a final image but lacks revision provenance and fresh acceptance and has open risk reports requiring review. No promotion approval is ready ([23 Oct evidence](HERMES_WEEKLY_GATE.md)). Then cut a new snapshot. *Check:* a fresh install on Thales reports the new version, and its test record is linked from the snapshot.

**Later:** an update prompt in the Wizard UX for alongside owners; Wizard stable for other agent runtimes (Pi).
