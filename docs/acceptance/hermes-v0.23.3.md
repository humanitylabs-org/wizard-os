# Hermes v0.23.3-wizard1: acceptance, bug review and rollback (23 Nov 2026)

Evidence for the Hermes lock promotion asked for in
[wizard-app-manager#856](https://github.com/humanitylabs-org/wizard-app-manager/issues/856) (spec/HERMES_LOCK.md
steps 1 to 3). It moves no pin: the lock change and the release cut that ship this engine land separately, on or
after the approval date below. This file is the `acceptance`, `bug_review` and `rollback` evidence of that
promotion record.

| | |
|---|---|
| Upstream | `v0.23.3`, commit `caafe5389ae585ef77387a962aee05b1bcf17029`, published 2026-11-20T00:34:38Z |
| Official image | `docker.io/nousresearch/hermes-agent:v0.23.3` at `sha256:3e9fe4c6ef36490f43aa0d0d80f9df64e9c92a576eee3042f1a97c8813c05355` (amd64 + arm64) |
| Wizard image (what boxes run) | `ghcr.io/humanitylabs-org/hermes-agent:v0.23.3-wizard1@sha256:1353ee1e39d4fe5536050ade372cf70951fb6947eb1f192c8158a1a038f0fb8f`, built from wizard-app-store `images/hermes-agent` at `2d038e06` (official image + Claude Code 2.1.296 + the DirectSDK plugin) |
| Agent recipe | `oscarhenrycollins/hermes-agent` commit `8db4cc2aa51b9b91cd9369631b2aa47b4dc48c1d` (index version `0.23.3-wizard1`, `tipi_version` 7) |
| Replaces | `v2026.9.24` (Hermes v0.21.5), Wizard image `sha256:e8ad921a…`, recipe `e8ae558f` |
| Why | 9 high-severity advisories in the shipped engine's packages; v0.23.3 carries tornado 6.6.1, oauthlib 4.0.1, pyasn1 0.6.5, msgpack 1.2.3 |
| Owner approval | James, [23 Nov](https://github.com/humanitylabs-org/wizard-app-manager/issues/856#issuecomment-7096312096): ship on the normal path, For testers first, approval date 27 Nov 2026 00:35Z (the earliest the 7-day gate allows) |

## Acceptance: the seven stable checks

Run on the builder machine (x86_64, Docker 29.9.2) with `tools/acceptance/hermes/check.py` at wizard-os `944a39a`,
two local changes only: the data folder comes from `HS_ROOT` instead of `/var/lib/hermes-stable`, and the `chown`
is skipped because the runner already is uid 1000. No VM: the containers ran directly on that Docker. The box
starts on today's Wizard image (`e8ad921a…`), updates to the candidate Wizard image, runs the checks, and rolls back.
Agent Service and shell are the ones in release 0.3.380 (`be85059c…`, `89c297d8…`); the model is the deterministic
`fake_model.py`.

**Result: six pass; compaction works but one turn later than the check expects** (details below).

| Check | Result | What happened |
|---|---|---|
| A thread sends and receives | PASS | `ECHO t1`; the thread reads back through the Agent Service. |
| A helper's result comes back to the thread that started it | PASS | Background helper; its result landed in the parent thread and the parent replied `PARENT-SAW CHILD-RESULT h1`. |
| Markdown replies render | PASS | Stored verbatim; the shell's `chat-kit.js` rendered heading, bold, list, code, table, link. |
| A long conversation keeps its reasoning after compaction | see below | Hermes compacted (39 → 6 messages, facts kept in the summary) and the model recalled all three facts. |
| The database is intact before and after a restart | PASS | `integrity_check` ok before and after; 6 sessions / 66 messages before and after. |
| A scheduled job fires | PASS | `every 1m` job's model call arrived 106 s after creation. |
| An update followed by a rollback both work, with history intact | PASS | v0.21.5 → v0.23.3 → v0.21.5 over the same data: integrity ok, seed thread and the thread written on v0.23.3 read back identically, new turn `ECHO rb1` after the rollback. |

Files: [`hermes-v0.23.3/results.json`](hermes-v0.23.3/results.json), [`run.log`](hermes-v0.23.3/run.log).

### Compaction, in detail

The check sends the recall turn right after the turn that crosses the threshold, and expects the facts to reach the
model only through the summary. On v0.23.3 the gateway's session hygiene compacts after that turn (`compressed 39 →
6 msgs, ~65,031 → ~1,106 tokens`, `commit_status: committed`), but the very next turn still goes to the model with
the full history (40 messages, ~228 K characters; Hermes logs `Skipping preflight compression … not anchored on real
usage … deferring to the next response`). From the turn after that on, the compacted history is used. A second run
with three more turns ([`compaction-timing.json`](hermes-v0.23.3/compaction-timing.json)) shows it: request 23 is the
full 40 messages, requests 26 to 28 are 8 to 10 messages, and the final recall turn reaches all three facts only
through the summary (`RECALL alpha bravo charlie | summary=true | verbatim_fact_turns=false`).

For an owner: nothing is lost and reasoning carries through compaction. The cost is one extra full-size model call
after a compaction, still under the context limit (hygiene starts at 85 %). v2026.9.24 applied it on the next turn.

Observation (history display): the shell now still shows the compacted early turns (42 of 48 rows returned,
including the three fact turns). On v2026.9.24 it showed only the turns after the compaction, so this is better.

## Canary

Since 22 Nov ~16:40Z James's fresh private-first forum install runs this exact published image
([Archimedes, 22 Nov](https://github.com/humanitylabs-org/wizard-app-manager/issues/856#issuecomment-7082235579)):
0 restarts, gateway `/health` ok at 0.23.3, the fixed package versions, install stamp 0644, no tracebacks. Before
that it ran the equivalent v0.23.2 fork build for two days. Archimedes re-checks it on 27 Nov and adds the result to
the issue.

## Bug review

Read on 23 Nov 2026: all 420 upstream `NousResearch/hermes-agent` issues opened since v0.23.3's publication (20 Nov),
filtered to session, database, gateway, compaction, history, API server, cron and delegation, leaving out
desktop/mobile/Windows/Termux/chat-platform reports Wizard does not run. Nothing found is a data-loss or history
regression on the paths a Wizard uses (the API server's `/v1/runs` and `/api/sessions`, `state.db`, compaction,
cron). Reports worth knowing:

- [#158976](https://github.com/NousResearch/hermes-agent/issues/158976): settled gateway admission results are never
  deleted from `state_meta`, so `state.db` grows (942 MB on one heavy desktop install). Reported on `main`; it is
  disk growth, not loss. Watch `state.db` size on the canary.
- [#159039](https://github.com/NousResearch/hermes-agent/issues/159039): the boot `integrity_check` can delay
  gateway start for minutes on a very large `state.db` (reported from v0.22.5/v0.23.0). Startup only.
- [#158684](https://github.com/NousResearch/hermes-agent/issues/158684): v0.23.3 sends the compaction summary with
  real message roles; a separate summarizer that rejects tool messages falls back to the main model. Wizard uses the
  main model for compaction, so no change for owners.
- [#158798](https://github.com/NousResearch/hermes-agent/issues/158798): `GET /v1/runs/{id}` reports an empty
  `runtime.provider/model`. The Agent Service does not read those fields.
- [#158507](https://github.com/NousResearch/hermes-agent/issues/158507): `GET /v1/skills` returns 500. The Agent
  Service does not call it.
- [#158242](https://github.com/NousResearch/hermes-agent/issues/158242), [#158332](https://github.com/NousResearch/hermes-agent/issues/158332):
  fleet-restart bookkeeping and the host dashboard service after `hermes update`: host installs only, not the
  container Wizards run.
- [#156311](https://github.com/NousResearch/hermes-agent/issues/156311): the "install out of sync (pnpm)" warning on
  sealed Docker images is cosmetic (the tester saw it on plain upstream too).

## Rollback

- **One box:** the update check above rolled v0.23.3 back to the v2026.9.24 Wizard image over the same data with
  history intact. On a box that is: put the `hermes-agent` app back on recipe `e8ae558f` (image
  `ghcr.io/humanitylabs-org/hermes-agent@sha256:e8ad921a23c7a2144b9c89902cb16908b68020fcd4f301bf8a2dbe2da75f3f5f`)
  with the same app data, after a private backup of `state.db`. Keep the old image on the box until the update is
  verified.
- **The fleet:** revert the lock to the frozen v2026.9.24 block as its own reviewed promotion and cut a release with
  it (spec/HERMES_LOCK.md, Rollback). That stops new installs and updates taking v0.23.3; it does not downgrade boxes
  already on it.
- Never restore an old `state.db` over newer writes.

## Promotion record (landed 27 Nov 2026, after 00:35Z)

`hermes_lock.validate` refuses an `approved_at` in the future, and every box runs it whenever it loads the lock, so
this record can only merge once its date has passed:

```json
"state": "approved",
"hermes": {"tag": "v0.23.3", "commit": "caafe5389ae585ef77387a962aee05b1bcf17029",
           "image": {"ref": "docker.io/nousresearch/hermes-agent:v0.23.3",
                     "digest": "sha256:3e9fe4c6ef36490f43aa0d0d80f9df64e9c92a576eee3042f1a97c8813c05355"}, ...},
"agent_recipe": {"commit": "8db4cc2aa51b9b91cd9369631b2aa47b4dc48c1d", "index_version": "0.23.3-wizard1", ...},
"runtime_image": "ghcr.io/humanitylabs-org/hermes-agent@sha256:1353ee1e39d4fe5536050ade372cf70951fb6947eb1f192c8158a1a038f0fb8f",
"promotion": {"id": "hermes-v0.23.3-wizard1", "published_at": "2026-11-20T00:34:38Z", "approved_at": "2026-11-27T00:35:00Z",
              "recommendation": "https://github.com/humanitylabs-org/wizard-app-manager/issues/856",
              "approval": "https://github.com/humanitylabs-org/wizard-app-manager/issues/856#issuecomment-7096312096",
              "acceptance": "<this file>", "canary": "https://github.com/humanitylabs-org/wizard-app-manager/issues/856#issuecomment-7082235579",
              "bug_review": "<this file>#bug-review", "rollback": "<this file>#rollback"}
```

Then byte-identical copies in App Manager (`wam/hermes-lock.json`, `releases/hermes-lock.json`) and Agent Service
(`ops/agent-runtime/hermes-lock.json`), their new images, and one For testers release that moves App Manager, Agent
Service, the `hermes` block and the agent slot together.

Landed with a `previous` block (the replaced v2026.9.24 pin) so the stable snapshot stays installable while the
promoted snapshot soaks on For testers (spec/HERMES_LOCK.md step 4, wizard-app-manager#856).
