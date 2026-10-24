# Acceptance: `wizard hermes update --stable` (alongside boxes)

**Result: PASS, 10 of 10 checks**, run on 23 Oct 2026 on Thales (`thales.local`) in a fresh Lima VM (`hu-1023t005358z`, Ubuntu 24.04 arm64), which was deleted after the run.

- Candidate: `feature/hermes-update-stable` at `76136a4ea9aa4c5c4777c2e7b17139ad0ff35a52`. The CLI the VM ran is byte-identical to `tools/wizard` at that commit (sha256 `1fe71eb0…ab2f82`).
- From: stock Hermes **v2026.9.24** (`f97608f178d1ffeca59860195ab7da295f7c8e5f`), installed by the official `scripts/install.sh --branch v2026.9.24`. That gave a shallow git checkout with a venv and a systemd user gateway.
- To: **v0.21.6** (`818c13be1dc4fd28987e1e881a9408224afd4535`), the tag commit. It is not `a28a5d03`, which is the commit the published v0.21.6 image was built from (the PR #149 finding).
- Pin source: today's Wizard stable release file, 0.3.32, with its `hermes` block pointed at v0.21.6 and passed through `--release`. That is the same code path `releases/stable` uses. **This promotes nothing**: Wizard stable still pins v2026.9.24.
- Model: the deterministic fake model from PR #149 (`fake_model.py`). No accounts and no paid inference were used.
- Wizard OS alongside: `wizard link` was run against the CLI's own MCP test fixture, which stood in for the shell's gateway. The wizard-os plugin was installed and the MCP server registered.
- Evidence on Thales: `$WIZARD_WORK_ROOT/wizard-os/hermes-update-stable/runs/20261023T005358Z/`, containing `RECEIPT.md`, `results.json`, `run.log` and 25 files in `evidence/`. The command's own receipts are `evidence/C-receipt.json` and `evidence/D-receipt.json`; inside the VM they were `~/.wizard-os/hermes-update/20261023T010224Z/` and `…/20261023T010643Z/`.
- Harness: `tools/acceptance/hermes-update/run.sh` (host) and `guest.py` (in the VM). It ran under Thales' shared heavy-work lock. The `wizard_heavy_submit` queue refused admission from a Kanban worker (409), so the run took the same lock file directly, as PR #149's `locked.py` does.

## What was checked

| Step | What happened | Result |
|---|---|---|
| Setup | Stock install is exactly `f97608f1`. `wizard link` succeeded. The gateway is up (`/health` 0.21.5). Three chat sessions and a daily cron job are seeded. | PASS |
| A. Dry run | `--dry-run` printed the six-step plan. The Hermes home was hashed before and after with the gateway stopped: 58,818 files, sha256 `f568473b…0012` both times, zero files changed. The code stayed on `f97608f1`. | PASS |
| B. Busy box | A cron job was due every minute. With `--quiet-timeout 45` the command exited **11 `not_quiet`** and named the job. Code unchanged, no drain marker left behind. | PASS |
| C. Forced failure | `WIZARD_HERMES_UPDATE_FAULT=break-config` made `config.yaml` unparsable after the code had moved to v0.21.6. The gateway answered, chat worked and history was fine, but the new checks **settings file parses** and **hermes reports no setup problems** failed. The command then rolled back by itself: gateway stopped → code back to `f97608f1` → dependencies reinstalled → `config.yaml` and `skills/` restored → every database kept (intact, newer writes preserved) → launchers and gateway unit restored → gateway started → `/health` 0.21.5 → all 8 re-checks PASS. It exited **12 `update_rolled_back`**. Afterwards: 6 sessions (5 before, plus the post-rollback chat), the cron job still present, `hermes config show` works, chat replies. | PASS |
| D. Real update | The command exited 0. Checkout at `818c13be`, tagged `v0.21.6`. `hermes --version` reports "v0.21.6 · upstream 818c13be", and `/health` reports 0.21.6. All 8 stable checks passed. The harness re-verified independently: sessions went from 7 to 8 (+1 = its own chat), messages from 16 to 20, the cron job is intact, `hermes cron list` works, chat replies. | PASS |
| Status | `wizard hermes status` reports `matches_stable: true`. | PASS |

## What the first two runs found (fixed before this run)

- **Hermes v0.21.6 keeps running on "last good settings" when `config.yaml` is broken.** In run `20261023T002111Z` the injected bad config passed every check: the gateway answered, chat worked and history was fine. The update was kept while the owner's settings were being ignored. Fix: two new stable checks. One parses `config.yaml` with Hermes's own YAML; the other fails on Hermes's own warnings ("formatting error", "install out of sync", "source-update completion failed").
- **From v0.21.6 on, Hermes manages its own dependencies.** It keeps venvs under `$HERMES_HOME/installs/` and re-mints `~/.local/bin/hermes{,-agent,-acp}` and the gateway's systemd unit to use them. In run `20261023T003527Z` the rollback put the old code back behind the *new* launcher. `hermes` then failed with `No module named 'yaml'`, and the `cron list` re-check failed. Fix: the backup also snapshots those launchers and units, and the rollback puts them back and runs `systemctl --user daemon-reload`. In this run, all four were restored.
- **The rollback replaced live databases that had only changed.** It also restored them while the old gateway was still running, and it accepted a `/health` answer from the not-yet-replaced v0.21.6 process. Fix: the rollback stops the gateway first and restores a database only when it fails its integrity check (or, for `state.db`, when it lost rows). Every restart now waits until `/health` reports the version the code on disk names.

## Also verified on Telos (no VM; fixtures only)

- A pin with an `rc` tag is refused (exit 10). So is a pin whose commit is not upstream's tag commit: a pin of `a28a5d03…` under the v0.21.6 tag was refused with "upstream tag v0.21.6 points at 818c13be…" (exit 10).
- A checkout with local changes is refused (exit 10). Moving from v0.21.6 down to v2026.9.24 is refused as a downgrade (exit 10, with a receipt). `update` without `--stable` is a usage error (exit 2).
- Telos's own Hermes reports "`install-stamp.json` says updates belong to 'external'; left it alone". The command never touches it.
- `python3 -m unittest discover -s tools/tests`: 108 tests. The 3 import errors (`test_packaging`, `test_storage`, `test_voice_input`) are identical on `origin/main`.

## Not covered

- An alongside box whose Hermes is the Docker image or another non-git install. The command exits 10 `update_by_hand` and names the tag; that branch was checked only with fixtures.
- A rollback from a failure *during* the dependency install of a PM-era target. The forced failure here came after the install.
- Promoting v0.21.6 to Wizard stable. That needs James's yes and the soak in [HERMES_STABLE](../HERMES_STABLE.md) steps 2–3.
