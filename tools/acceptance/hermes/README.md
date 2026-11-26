# Hermes stable-candidate test

Step 2 of [`docs/HERMES_STABLE.md`](../../../docs/HERMES_STABLE.md): before an upstream Hermes release reaches Wizard boxes, it runs on a fresh VM on Thales behind the Agent Service and has to pass the Wizard stable checks. The records live in [`docs/acceptance/hermes-<tag>.md`](../../../docs/acceptance/).

```sh
# on Thales, from a checkout of this folder
WIZARD_WORK_ROOT=<Thales work disk> python3 locked.py \
  nousresearch/hermes-agent@sha256:<candidate digest> \
  nousresearch/hermes-agent@sha256:<digest pinned in releases/<stable>.json>
```

The first argument is the image under test. The second is the image the box starts on before it updates to the candidate, and the one it rolls back to at the end; pass the same digest twice to record the version pinned today. `locked.py` waits for Thales' shared heavy-work lock (`AndroidBuilds/worker.lock`), which the Android and VM lanes also take; `run.sh` runs without it.

## What one run does

1. Fetches every image on the Thales host and checks each blob against its digest (`fetch_image.py`), then loads them into the VM. GHCR downloads fail inside the vz guest with TLS "bad record MAC", and side-loading keeps the run pinned to exact digests either way.
2. Creates a fresh Lima VM (`lima.yaml`: Ubuntu 24.04 arm64, 4 CPU, 6 GiB, Docker) and deletes it afterwards (`KEEP_VM=1` keeps it).
3. Inside the VM, `check.py` starts:
   - stock Hermes from the official image, unmodified, in gateway mode with its API server on, a per-run random API key, and `/opt/data` on the VM disk;
   - the pinned Wizard Agent Service in front of it, the way a box runs it;
   - `fake_model.py`, a deterministic OpenAI-compatible model registered as a Hermes `custom` provider. Its replies are driven by markers in the prompt (`HS-ECHO`, `HS-DELEGATE`, `HS-FACT`, `HS-FILL`, `HS-RECALL`, `HS-MARKDOWN`, `HS-CRON`), so every Hermes code path runs for real with no account or paid inference.
4. Creates a seed thread on the starting image, updates to the candidate, and runs the seven checks through the Agent Service routes the shell uses (`/wizard/hermes/api/sessions`, `/wizard/hermes/v1/runs`, the shell's message read with `include_compacted=true&view=wizard`).
5. Writes `results.json`, `RECEIPT.md`, `run.log` and `evidence/` under `$WORK/runs/<UTC stamp>/` (default `WORK=$WIZARD_WORK_ROOT/wizard-os/hermes-stable`).

## The checks

| Check | How it is judged |
|---|---|
| A thread sends and receives | One turn through the Agent Service completes and the thread reads back both messages. |
| A helper's result comes back to the thread that started it | The model calls `delegate_task`; the helper's own model call happens; its result lands in the parent thread and the parent's next reply uses it. On stock Hermes the helper runs in the background and the Agent Service's follow-through starts that next turn. |
| Markdown replies render | A reply with a heading, bold text, a list, a code block, a table and a link is stored verbatim and rendered by the shell's own `web/core/chat-kit.js`, copied out of the pinned wizard-ux image. |
| A long conversation keeps its reasoning after compaction | Three facts are stated early, buried under ordinary turns and one very long reply. Hermes must compact, and once the compacted history reaches the model (up to three ordinary turns later: v0.21.5 uses it on the next turn, v0.22 and later one turn after that, see [`hermes-fork-v0.22.7-compaction.md`](../../../docs/acceptance/hermes-fork-v0.22.7-compaction.md)) the facts must reach the model only through the summary and the model must recall all three. How many turns it took is reported as an observation. Whether the shell can still scroll back to the compacted turns is reported beside it as an observation. |
| The database is intact before and after a restart | `state.db` is copied with SQLite's online-backup API before and after `docker restart`; both copies pass `PRAGMA integrity_check`, no rows are lost, and the first thread reads back identically and takes a new turn. |
| A scheduled job fires | `hermes cron create "every 1m"` inside the container; the job's model call has to arrive within four minutes. |
| An update followed by a rollback both work, with history intact | The seed thread from before the update reads back identically on the candidate; after recreating the container on the starting image, the seed thread and a thread written on the candidate both read back identically and take a new turn. |

The update and rollback swap the container image over the same data directory and keep `config.yaml`, which is what the `hermes-agent` app does on a box. They do not exercise the alongside updater (`HERMES_STABLE.md` step 4).

## Files

- `run.sh`: host side (fetch images, fresh VM, checks, receipt).
- `locked.py`: runs `run.sh` under Thales' shared heavy-work lock.
- `check.py`: the in-VM checks and the judge.
- `fake_model.py`: the deterministic model.
- `fetch_image.py`: digest-verified registry fetch into a `docker load` archive.
- `lima.yaml`, `render_lima.py`: the VM, as in `tools/acceptance/router/`.
- `pull.sh`: retrying `docker pull` for registries the guest can reach.
