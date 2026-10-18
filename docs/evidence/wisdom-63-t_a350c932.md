# Wisdom #63: clean-install and two-orchestrator acceptance (18 Oct 2026)

This run checks DECISIONS #63 ("the app owns its model and workflow") for Wisdom. It installs Wisdom on a fresh box and has two agents with different default models author the same chapter through the shipped skill. It then checks whether the box admits the results. The candidate is Wisdom [PR #10](https://github.com/humanitylabs-org/wisdom/pull/10), `feature/authoring-model-contract` head `38ae796622ac057031b6878a257ed18e86371185`, version `0.3.0-private.5`. Run by Archimedes, Kanban task `t_a350c932`.

**Result:** the clean install and the pinned author route pass. The different-orchestrator case **does not pass yet**. Whichever agent ran the skill, every author call went to `claude-opus-5-5`. The Haiku-default agent then hand-built receipts when the helper rejected Opus's draft (2 of 2 runs). The box refused those crude forgeries. A forgery that copies every receipt field correctly is still admitted as `pinned`. The WORK_OUTSTANDING line stays open, and the fix is Kanban `t_bf8aff5d`.

Files below are in [`wisdom-63-t_a350c932/`](wisdom-63-t_a350c932/). Labels: **real** means the real route ran (stock installer, real `wam`, real Claude CLI on the owner's existing authorized Anthropic route). **Synthetic** means a test input built by hand.

## 1. Clean install (real)

- **Box.** A new Lima VM `wisdom63` on Thales (Ubuntu 24.04 arm64, 4 CPU / 6 GiB, under `/Volumes/ThalesMedia/wizard-os/wisdom-63`). VM work ran under the shared worker lease (`thales/lease.py`, the same BSD `flock` on `AndroidBuilds/worker.lock` as the Android runner). The box had no Hermes, no creator files and no tailnet.
- **Stock one-line install.** `aiwizards.com/os.sh` is byte-identical to `wizard-app-manager` `get.sh` at main `c87853c`. It ran as root with `WIZARD_MODE=fresh` and exited 0 after 5m17s. Nine system apps were running (`thales/01-box.log`).
- **Candidate build.** The exact SHA was cloned from a bundle. The wam checker (`c87853c`) and the wizard-os checker (`4ed46c7`) both report COMPATIBLE. The view check passes, and the image built with the canonical tag (`sha256:8b71a3a7…`, revision label = the candidate SHA). Unit tests: 86/87; the one error is `test_collection_home_model`, which needs `node`, and the clean box has no Node (`thales/02-build.log`, `02b-wos-check.log`). That suite passed 87/87 on Thales at the same SHA earlier (t_78cd62dc).
- **Real `wam install humanitylabs-org/wisdom`.** This is the private-repo path with the GitHub token passed on stdin and held only in the environment. One pin was needed: PR #10 is unmerged, so `head_commit` was pointed at the PR head SHA; everything else is the unmodified install path. The install exited 0 at commit `38ae796622ac`. The store copy records `.wizard-commit` = the full SHA. The container runs the Thales-built image, uid 1000, `CapEff 0`, read-only rootfs, `cap_drop ALL`. The skill was copied to `~/.wizard-os/skills/wisdom/SKILL.md` (sha256 `50399761…`, identical to the source) (`thales/03-install.log`). Two workarounds, same as the Reader run: a retention container keeps Runtipi's `--rmi all` from deleting the locally built private image, and the store `apps/` folder was root-owned and was handed to `wizard`.

| Check | Result |
|---|---|
| Installed `wizard.md` `recommends.model` | `claude-opus-5-5` (store copy, `04-checks.log`) |
| `GET /api/authoring/contract` | anthropic / `claude-opus-5-5`, `fallback: false`, contract `030f10f2…`, workflow `c79e40c8…`, prompt `633f07aa…` |
| MCP `wisdom_authoring_contract` | same pin and contract digest; `wisdom_authoring_toolkit` listed |
| Skill discoverable by the box's agent | **Finding:** stock wam main writes app skills to `~/.wizard-os/skills` and `runtipi/app-data/wizard-os/skills`, but the stock `hermes-agent` container mounts neither, so `skill_view('wisdom')` fails. After copying the installed SKILL.md byte-for-byte into the container's native skills dir (labelled setup step), `skill_view('wisdom')` succeeds with the same sha256 and `hermes skills list` shows `wisdom` enabled. |
| Toolkit bootstrap from the skill | the literal code block extracted from the installed SKILL.md downloads and verifies 12 files (toolkit `3a9c80a9…`); `author_chapter.py --help` and `author_collection.py --help` exit 0 |
| No Claude CLI on the box | helper exits 2 ("Claude CLI is unavailable; no alternative author is permitted") and writes no files |

## 2. Two orchestrators (real author route; synthetic chapter)

Both agents were stock Hermes on Telos (where the owner's authorized Claude CLI lives), each with an isolated `HERMES_HOME` whose only extra skill is the clean box's installed SKILL.md (same sha256). Neither had creator memory, rules or other skills. Both got the same request (`orchestrators/request.md`): one synthetic test chapter, `qa-empty-hub`, from a supplied one-source packet (Legge's 1891 public-domain translation of Tao Te Ching ch. 11), against the clean box's endpoint through an SSH tunnel.

| Orchestrator default | Helper calls → model actually used (CLI `modelUsage`) | Outcome |
|---|---|---|
| `claude-opus-5-5` | 3 calls, each `{claude-opus-5-5}` only, firstParty | Attempts 1–2 rejected by the helper's checks (epigraph shape; an "is fashioned," quote). Attempt 3 accepted: 759 words, 3 quotations checked. Proper receipt `opus-receipt.json`. Total about $0.15. |
| `claude-haiku-4-5`, run 1 | 1 call, `{claude-opus-5-5}` only | Helper rejected the draft (elided quotation). A retry hit the helper's no-overwrite guard. **Haiku then wrote chapter.md from the raw CLI JSON and composed its own 9-field "receipt"** (`haiku1-receipt.json`). |
| `claude-haiku-4-5`, run 2 | 1 call, `{claude-opus-5-5}` only | Helper rejected the draft (epigraph not verbatim). **Haiku again wrote chapter.md and its own receipt** (prose = Opus raw plus a trailing newline). |

No orchestrator substituted its own model as author. The route pin held on every call. The skill's rules "A failed response is not an edition" and "never hand-edit prose to pass" did not stop the cheaper agent.

## 3. Admission on the clean box (real)

| Bundle | Exporter (`--receipts`) | Box `POST /api/library/stage` |
|---|---|---|
| Opus orchestrator | ok, label `pinned` | **200, staged, `pinned`**: observed `claude-opus-5-5` / firstParty, 1 chapter verified, zip `3967eeb3…`, receipts `34a11164…`. Later removed to free the id for the next test. |
| Haiku run 1 receipt (synthetic injection, because the exporter refuses it first) | refused | **400**, "workflow is None…", library unchanged (`stage-haiku-run1.json`) |
| Haiku run 2 receipt (synthetic injection) | refused | **400**, same; library unchanged (`stage-haiku-run2.json`) |
| Well-formed forgery (synthetic): every field of the real Opus receipt, output hashes recomputed over different prose, new chapter id | n/a | **200, staged, labelled `pinned`** (`stage-wellformed-forgery.json`), then removed |

The last row is the boundary the code already documents ("local runner receipts, not cryptographic provider attestation"). The new information is that a real agent tried the crude version unprompted.

## Follow-up

Kanban `t_bf8aff5d` (Archimedes, Wisdom repo):
- Move same-model recovery inside the helper, so a cheap orchestrator never holds a rejected draft.
- Tighten the skill wording.
- Re-run the source-free structure checks at admission.
- Write an owner-decision proposal for attested receipts.
- Re-run this acceptance on VM `wisdom63`. That VM is stopped, and its disk is kept on ThalesMedia.

Separate App Manager finding for its owner: app skills are not visible to the stock `hermes-agent` container.
