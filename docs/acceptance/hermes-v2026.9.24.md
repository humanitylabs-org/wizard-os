# Hermes stable test: v2026.9.24, the version pinned today (22 Oct 2026)

This is the baseline record for [`HERMES_STABLE.md`](../HERMES_STABLE.md) step 2. It runs the Wizard stable checks against the Hermes that fresh installs get today, so the next candidate has something to be compared with. Release snapshot 0.3.25 pins it with `"test_record": "none: carried over…"`; this is the record it never had. Run by Archimedes, Kanban task `t_737d1a52`.

**Result: all seven checks pass.** One thing an owner would notice: after Hermes compacts a long thread, the thread in Wizard shows only the turns after the compaction. The older messages are still in the database, but the shell can no longer scroll back to them. v0.21.6 does not have this problem ([record](hermes-v0.21.6.md)).

| | |
|---|---|
| Tag | `v2026.9.24` (upstream release "Hermes Agent v0.21.5 (v2026.9.24)", 24 Sep 2026) |
| Commit | `f97608f178d1ffeca59860195ab7da295f7c8e5f`; the image reports `upstream f97608f1`, the same commit |
| Image | `docker.io/nousresearch/hermes-agent@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7` (matches `releases/0.3.25.json`) |
| Reports itself as | `Hermes Agent v0.21.5 (2026.9.24) · upstream f97608f1` |
| Date | 22 Oct 2026, 01:02–01:05 UTC |
| Update / rollback | from and back to this same image (there is no older pin), so that check covers recreating the container over the same data |
| Thales evidence | `$WIZARD_WORK_ROOT/wizard-os/hermes-stable/runs/20261022T010058Z/` |

## Checks

| Check | Result | What happened | Evidence |
|---|---|---|---|
| A thread sends and receives | PASS | One turn through the Agent Service completed (`ECHO t1`); the thread reads back both messages. | `thread-run.json`, `thread-messages.json` |
| A helper's result comes back to the thread that started it | PASS | The model called `delegate_task`. Stock Hermes ran the helper in the background (its own session, parent = this thread, `subagent`, `agent_close`). The helper's result was stored in the parent thread, the Agent Service's follow-through started the next turn, and the parent replied `PARENT-SAW CHILD-RESULT h1`. | `helper-run.json`, `helper-messages-raw.json`, `helper-messages.json`, `helper-child-sessions.json` |
| Markdown replies render | PASS | The reply was stored verbatim and the shell's renderer produced the heading, bold text, list, code block, table and link. | `md-input.txt`, `md-rendered.html` |
| A long conversation keeps its reasoning after compaction | PASS | Hermes compacted once. On the next turn the three early facts reached the model only through the compaction summary, and it recalled all three. | `compaction-summary-requests.json`, `compaction-recall-request.json`, `compaction-recall-run.json` |
| The database is intact before and after a restart | PASS | `PRAGMA integrity_check` ok on online-backup copies before and after `docker restart`; 6 sessions / 61 messages before and after; the first thread reads back identically and takes a new turn. | `restart-db.json`, `restart-thread-*.json` |
| A scheduled job fires | PASS | `hermes cron create "every 1m"`; the job's model call arrived 119 s later and wrote `cron/output/<job>/….md`. | `cron-create.txt`, `cron-list.txt`, `cron-outputs.json` |
| An update followed by a rollback both work, with history intact | PASS | The seed thread written before the update reads back identically after it. After the rollback, the seed thread and a thread written in between both read back identically (7 sessions / 65 messages before and after) and take a new turn. | `update.json`, `rollback.json` |

## Observation: thread history after compaction

The compaction test thread has 46 rows in `state.db`, including all three early fact turns. The Agent Service returns 8 of them to the shell (`include_compacted=true&view=wizard`, the read `web/live.js` makes), so the owner sees only the turns after the compaction. Nothing is lost from the database, and the model's reasoning is unaffected. On v0.21.6 the same read returns 41 messages including the early turns.

## How it ran

- **Box.** A fresh Lima VM on Thales (Ubuntu 24.04 arm64, 4 CPU / 6 GiB, Docker 29.1.3), created for this run and deleted after it. The run took Thales' shared heavy-work lock (`AndroidBuilds/worker.lock`, granted after 0 s) through `tools/acceptance/hermes/locked.py`; a Kanban worker has no Wizard chat run for the wizard-heavy queue to resume, the same situation as the [Connection Router run](router-2026-10-21.md).
- **Real parts, all pinned by digest.** Every image was fetched on the Thales host with each blob checked against its digest, then loaded into the VM (GHCR downloads fail inside the vz guest with TLS "bad record MAC").
  - Hermes: the official `nousresearch/hermes-agent` images, stock and unmodified, in gateway mode with the API server on and a per-run random key.
  - Agent Service: `ghcr.io/humanitylabs-org/wizard-agent-service@sha256:cb92d01c5656e89f8280e54f6972bc486de3d04f1e50203e00c8acf0d8bb0389` (source `e7bfd6d`). Every check talks to Hermes through it, on the routes the shell uses.
  - Markdown renderer: `web/core/chat-kit.js` copied out of `ghcr.io/humanitylabs-org/wizard-ux@sha256:c60920e7da9fadbc7d9c322c26df6068c9fa505eb30cf1cf6e9829268acfebec` (source `a79e28a`) and run in Node.
- **Fake.** The model is `fake_model.py`, a deterministic OpenAI-compatible server registered as a Hermes `custom` provider (`python@sha256:1b668429…`). No account, key or paid inference was used.
- **Harness.** wizard-os `tools/acceptance/hermes/` at `705f289`; the copy on Thales was byte-identical (sha256 of all seven files compared). A later commit on this branch only makes `run.sh` take its work disk from `WIZARD_WORK_ROOT`.
- **What the update and rollback cover.** They swap the container image over the same data directory and `config.yaml`, which is what the `hermes-agent` app does on a box. They do not exercise the alongside updater (`HERMES_STABLE.md` step 4).

The copy in this PR is in [`hermes-v2026.9.24/`](hermes-v2026.9.24/): `RECEIPT.md`, `results.json`, `run.log` and the evidence files under 150 KB. Database copies and container logs stay on Thales. Machine paths in the copies are written as `$WIZARD_WORK_ROOT` (the Thales work disk) and `~`.
