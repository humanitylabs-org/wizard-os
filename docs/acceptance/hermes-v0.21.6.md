# Hermes stable test: v0.21.6, the next candidate (22 Oct 2026)

[`HERMES_STABLE.md`](../HERMES_STABLE.md) step 2 for the candidate that step 5 names: v0.21.6. The box started on the version pinned today (v2026.9.24), was updated to v0.21.6, ran the Wizard stable checks, and was rolled back to v2026.9.24. Run by Archimedes, Kanban task `t_737d1a52`. This record does not promote anything; promotion needs James's yes.

**Result: all seven checks pass, including the update from today's pin and the rollback to it.** v0.21.6 also fixes the history display problem the pinned version has: after compaction, the thread in Wizard still shows the older messages ([baseline record](hermes-v2026.9.24.md)).

**One thing to settle before step 5:** the published `v0.21.6` image was not built from the commit the `v0.21.6` tag points to. The image reports `upstream a28a5d03` (8 Oct 06:07 UTC, "fix(update): a whole-second marker creation time…"); the tag points to `818c13be`, which is 39 commits later on the same line. This run tested the image, so it vouches for `a28a5d03`. The release checker now requires a newly tested image pin to record `hermes.image.commit` separately from the source tag's `hermes.commit`, requires those commits to agree, and checks both Linux architectures' OCI revision labels by digest. Missing provenance fails closed. This image has no OCI revision label (registry metadata checked 23 Oct); the runtime evidence below reports a different commit. **It is not eligible for promotion.** Use a final image whose source matches its tag, then test that exact digest; do not relabel this passing record as a test of `818c13be`.

| | |
|---|---|
| Tag | `v0.21.6` (upstream release 8 Oct 2026, public 14 days) |
| Commit | tag → `818c13be1dc4fd28987e1e881a9408224afd4535`; the image reports `upstream a28a5d03a9fa60418db5f44f3436fa2aa029c8f2` (39 commits earlier) |
| Image | `docker.io/nousresearch/hermes-agent@sha256:55e192fba0cd4fde61142abbff5adeacff40efdb482ccd0ff877924bd274f909` (the `v0.21.6` tag on Docker Hub) |
| Reports itself as | `Hermes Agent v0.21.6 (2026.9.24) · upstream a28a5d03` |
| Date | 22 Oct 2026, 01:07–01:10 UTC |
| Updated from, rolled back to | `v2026.9.24`, `sha256:fca358f1…` (today's pin) |
| Thales evidence | `$WIZARD_WORK_ROOT/wizard-os/hermes-stable/runs/20261022T010545Z/` |

## Candidate rules (HERMES_STABLE.md)

- Final upstream tag, not a test build: yes.
- Public for at least seven days: yes, 14 days.
- Published final image: yes, `v0.21.6` on Docker Hub.
- No open upstream reports against it about session storage, compaction, the database or the gateway: none found (GitHub issue search for `0.21.6` with each of those words, 22 Oct).
- Later releases: v0.21.7 has no final image; v0.22.2 is the release with the open lost-conversation reports; v0.22.3 and v0.22.4 are under seven days old.

## Checks

| Check | Result | What happened | Evidence |
|---|---|---|---|
| A thread sends and receives | PASS | One turn through the Agent Service completed (`ECHO t1`); the thread reads back both messages. | `thread-run.json`, `thread-messages.json` |
| A helper's result comes back to the thread that started it | PASS | The model called `delegate_task`. Hermes ran the helper in the background (its own session, parent = this thread, `subagent`, `agent_close`). The helper's result was stored in the parent thread, the Agent Service's follow-through started the next turn, and the parent replied `PARENT-SAW CHILD-RESULT h1`. | `helper-run.json`, `helper-messages-raw.json`, `helper-messages.json`, `helper-child-sessions.json` |
| Markdown replies render | PASS | The reply was stored verbatim and the shell's renderer produced the heading, bold text, list, code block, table and link. | `md-input.txt`, `md-rendered.html` |
| A long conversation keeps its reasoning after compaction | PASS | Hermes compacted once. On the next turn the three early facts reached the model only through the compaction summary, and it recalled all three. The thread in Wizard still shows the compacted turns: 46 rows in `state.db`, 41 messages returned to the shell, the 3 early fact turns among them. | `compaction-summary-requests.json`, `compaction-recall-request.json`, `compaction-recall-run.json` |
| The database is intact before and after a restart | PASS | `PRAGMA integrity_check` ok on online-backup copies before and after `docker restart`; 6 sessions / 61 messages before and after; the first thread reads back identically and takes a new turn. | `restart-db.json`, `restart-thread-*.json` |
| A scheduled job fires | PASS | `hermes cron create "every 1m"`; the job's model call arrived 117 s later and wrote `cron/output/<job>/….md`. | `cron-create.txt`, `cron-list.txt`, `cron-outputs.json` |
| An update followed by a rollback both work, with history intact | PASS | Update v2026.9.24 → v0.21.6: the seed thread written on v2026.9.24 reads back identically and the database passes its integrity check. Rollback v0.21.6 → v2026.9.24: the seed thread and a thread written on v0.21.6 both read back identically (7 sessions / 65 messages before and after) and take a new turn (`ECHO rb1`). | `update.json`, `rollback.json` |

## Rollback

If v0.21.6 is promoted and has to come back out, the rollback is the one this run tested: put the `hermes-agent` app back on `nousresearch/hermes-agent:v2026.9.24@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7` over the same data. A database written by v0.21.6 opened on v2026.9.24 kept every thread readable and writable here. The snapshot that promotes v0.21.6 should name v2026.9.24 in its `rollback` field.

## What this run does not cover

- Real models: the fake model drives every Hermes code path, but not provider quirks.
- The alongside updater (step 4) and Archimedes' two-to-three-day soak (the next stage in "The order a release reaches boxes").
- The extras the `hermes-agent` app adds on top of the official image (Claude CLI, the DirectSDK plugin); this run used the official image itself.

## How it ran

- **Box.** A fresh Lima VM on Thales (Ubuntu 24.04 arm64, 4 CPU / 6 GiB, Docker 29.1.3), created for this run and deleted after it. The run took Thales' shared heavy-work lock (`AndroidBuilds/worker.lock`, granted after 0 s) through `tools/acceptance/hermes/locked.py`; a Kanban worker has no Wizard chat run for the wizard-heavy queue to resume, the same situation as the [Connection Router run](router-2026-10-21.md).
- **Real parts, all pinned by digest.** Every image was fetched on the Thales host with each blob checked against its digest, then loaded into the VM (GHCR downloads fail inside the vz guest with TLS "bad record MAC").
  - Hermes: the official `nousresearch/hermes-agent` images, stock and unmodified, in gateway mode with the API server on and a per-run random key.
  - Agent Service: `ghcr.io/humanitylabs-org/wizard-agent-service@sha256:cb92d01c5656e89f8280e54f6972bc486de3d04f1e50203e00c8acf0d8bb0389` (source `e7bfd6d`). Every check talks to Hermes through it, on the routes the shell uses.
  - Markdown renderer: `web/core/chat-kit.js` copied out of `ghcr.io/humanitylabs-org/wizard-ux@sha256:c60920e7da9fadbc7d9c322c26df6068c9fa505eb30cf1cf6e9829268acfebec` (source `a79e28a`) and run in Node.
- **Fake.** The model is `fake_model.py`, a deterministic OpenAI-compatible server registered as a Hermes `custom` provider (`python@sha256:1b668429…`). No account, key or paid inference was used.
- **Harness.** wizard-os `tools/acceptance/hermes/` at `705f289`; the copy on Thales was byte-identical (sha256 of all seven files compared). A later commit on this branch only makes `run.sh` take its work disk from `WIZARD_WORK_ROOT`.
- **What the update and rollback cover.** They swap the container image over the same data directory and `config.yaml`, which is what the `hermes-agent` app does on a box. They do not exercise the alongside updater (`HERMES_STABLE.md` step 4).

The copy in this PR is in [`hermes-v0.21.6/`](hermes-v0.21.6/): `RECEIPT.md`, `results.json`, `run.log` and the evidence files under 150 KB (`compaction-messages.json`, which holds the long filler reply, stays on Thales with the database copies and container logs). Machine paths in the copies are written as `$WIZARD_WORK_ROOT` (the Thales work disk) and `~`.
