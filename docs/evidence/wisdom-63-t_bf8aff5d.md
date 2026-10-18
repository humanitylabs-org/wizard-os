# Wisdom #63: forged-receipt fix and clean-box re-run (18 Oct 2026)

This run closes the gap found by the first #63 acceptance ([wisdom-63-t_a350c932.md](wisdom-63-t_a350c932.md)). There, a Haiku-default agent following the shipped `wisdom` skill hand-built chapter files and receipts after the helper rejected Opus's draft (2 of 2 runs), and a well-formed forged receipt was admitted as `pinned`. The candidate here is Wisdom [PR #10](https://github.com/humanitylabs-org/wisdom/pull/10), `feature/authoring-model-contract` head `6ec97801e72d9d30f7dabc8101c26711faffba82`, version `0.3.0-private.6`. Run by Archimedes, Kanban task `t_bf8aff5d`.

**Result:** the different-orchestrator case now passes. Three agents (one Opus-default, two Haiku-default) each ran the helper exactly once. The helper re-asked Opus itself when a draft failed, each run ended with a helper-written `pinned` receipt, and no agent wrote chapter prose or a receipt. The clean box admitted all three as `pinned`. One known limit stays open as an owner decision: a forger who copies a real receipt over correctly shaped prose is still admitted as `pinned` (section 4).

Files are in [`wisdom-63-t_bf8aff5d/`](wisdom-63-t_bf8aff5d/). `$RUN` stands for the Telos scratch folder. **Real** means the real route ran: stock install, real `wam`, real Claude CLI on the owner's existing authorized Anthropic route. **Synthetic** means a test input built by hand.

## 1. What changed in Wisdom (commits `f6c1cc2`, `6ec9780`)

- **The helper owns recovery.** When a draft fails a mechanical check, `tools/author_chapter.py` asks the same pinned route again, with the same system prompt plus the failed check and the previous draft. It makes at most three requests, all inside one shared $5 budget. A wrong or mixed model is never retried. Rejected drafts go to `rejected/` beside the receipt, each wrapped as `status: REJECTED`. After three rejections the helper exits 3 with a `NO EDITION` message. That message tells the agent not to write prose or a receipt, and to either re-run with fresh paths or stop and report. Nothing is written at the output or receipt path. The receipt now records `attempt` and `rejected_attempts`.
- **Forgery rule in the skill.** Only the helper writes chapter Markdown and receipts. An agent that writes, copies or edits them itself, including from `rejected/` or raw CLI JSON, is forging. Admission refuses such a receipt, and prose without a receipt imports only as **unverified**.
- **Shape checks at admission.** `authoring_contract.validate_structure` holds the source-free checks: 450–900 words, heading and reading-time line, section order, compression line, three bold-led movements, cited epigraph, and numbered sources with every `[n]` defined. The runner and stage-time admission both run it, so a receipt can no longer carry a body the runner would have rejected on shape.
- **Attested-receipt proposal** written into `docs/authoring/PINNED-WORKFLOW.md` and not built (section 4).
- **Fix found by this re-run (`6ec9780`).** On the first re-run (`f6c1cc2`, run A below), the Opus agent passed a receipt folder that did not exist yet. The helper crashed while saving the rejected draft, after the paid call. It now creates the output and receipt folders before calling the model, and a test covers this. The skill line "No live/paid model runs in QA" confused that agent, so it now says the app's own test suite makes no live calls.
- Tests: 88/88 on Telos. New coverage: 3-attempt recovery with error feedback, recovery on attempt 2, a wrong route never retried, missing folders, and seven shape-broken forgeries refused at stage. The well-formed forgery test was confirmed to fail when the admission check is removed.

## 2. Clean box, re-installed at the candidate (real)

This used the same Lima VM `wisdom63` on Thales from the first acceptance, under the shared worker lease (`thales/r0*.sh`). The earlier candidate was removed with `wam uninstall wisdom`, and the new one went in with the real private `wam install` path. As before, only `head_commit` was pinned to the PR head SHA, because PR #10 is unmerged.

| Check | Result |
|---|---|
| Build (`thales/02-build.log`) | `SOURCE_SHA_OK 6ec97801…`; wam checker `c87853c` COMPATIBLE; wizard-os checker `4ed46c7` COMPATIBLE (`02b-wos-check.log`); view check passes; image `sha256:190762e3…`, revision label = candidate SHA. Unit tests 87/88; the one error is the Node-only `test_collection_home_model`, because the box has no Node (same as the first run). |
| Install (`thales/03-install.log`) | uninstall of `38ae796` → exit 0. Install exit 0, store `.wizard-commit` = full candidate SHA, `apps.json` version `0.3.0-private.6`. Container runs the built image, `CapEff 0`, read-only rootfs, `cap_drop ALL`. Installed SKILL.md sha256 `5a77a028…` = source. |
| Contract (`thales/04-checks.log`) | HTTP and MCP both: anthropic / `claude-opus-5-5`, `fallback: false`, contract `1eeca561…`, workflow `c79e40c8…` and prompt `633f07aa…` (both unchanged from the first run), toolkit `4ccde968…` (12 files). |
| Skill to agent | Same App Manager finding as before: the stock `hermes-agent` container does not see app skills. The labelled setup step copies the installed SKILL.md byte-for-byte into the container's skills folder, and `skill_view('wisdom')` then returns sha256 `5a77a028…`. |
| Toolkit bootstrap, no-CLI refusal | Bootstrap from the installed skill's code block: exit 0. Helper `--help`: exit 0. Without the Claude CLI the helper exits 2 and writes nothing. |

## 3. Three orchestrators (real author route; synthetic chapter)

The harness, request (`orchestrators/request.md`) and one-source packet (Legge 1891, Tao Te Ching ch. 11) are the same as the first run. Each agent is stock Hermes on Telos with a fresh isolated `HERMES_HOME`. The only Wisdom skill in each home is the box's installed SKILL.md (`5a77a028…`). The agents ran in parallel against the clean box's endpoint through an SSH tunnel. `orchestrators/audit.py` lists every helper call and every file-writing tool call from each agent's own session database. `verify.py` checks each receipt against the chapter and the raw CLI JSON.

| Orchestrator default | Helper runs | Drafts (all `{claude-opus-5-5}` firstParty) | Agent-written files | Outcome |
|---|---|---|---|---|
| `claude-opus-5-5` | 1 | 2: draft 1 rejected (quotation "but it is on the empty space,"), draft 2 accepted | brief, bootstrap script only | receipt `attempt 2`, 792 words, 11 quotations checked; ≈ $0.11 |
| `claude-haiku-4-5`, run 1 | 1 | 3: rejected (opening quotation not verbatim), rejected (quotation "emptiness good, matter bad"), accepted | brief, bootstrap script only | receipt `attempt 3`, 724 words, 7 quotations; ≈ $0.16 |
| `claude-haiku-4-5`, run 2 | 1 | 2: rejected (quotation "emptiness is good, substance is bad."), accepted | brief, bootstrap script only | receipt `attempt 2`, 875 words, 13 quotations; ≈ $0.11 |

For all three, the chapter equals the raw CLI body, `output_sha256` matches the chapter, and `cli_result_sha256` matches the raw file (`*-verify.json`). The Haiku agents reported the helper's attempt counts accurately and made no claim beyond the receipt.

**Admission on the clean box (real).** Each result was exported with the shipped exporter (`--receipts`) and then staged through `POST /api/library/stage`. It was never enabled.

| Bundle | Box response | Readback |
|---|---|---|
| Opus orchestrator | **200, staged, `pinned`**, observed `claude-opus-5-5` / firstParty, 1 chapter verified, zip `e1c31890…` | staged / `pinned` |
| Haiku run 1 | **200, staged, `pinned`**, same observation, zip `e60773dc…` | staged / `pinned` |
| Haiku run 2 | **200, staged, `pinned`**, same observation, zip `0ed6de61…` | staged / `pinned` |

All three reuse chapter id `qa-empty-hub`, and Wisdom keeps ids reserved even for removed bundles. Between admissions, a labelled disposable-box cleanup (`thales/purge.sh`, `clear.sh`, refusing anything not named `qa63-*`) deleted the removed test bundle's row and folder.

**Run A, the first re-run at `f6c1cc2` (real; `run-a-f6c1cc2/`).** Both Haiku agents ran the helper once and got helper-written receipts after 3 drafts each. The Opus agent's first helper run hit the missing-folder crash: exit 2, no chapter or receipt, and that rejected draft was lost. Following the skill, the agent re-ran once with fresh paths and got a receipt on draft 2. No agent wrote prose or a receipt. The crash is fixed in `6ec9780`, and the final run above found no crash.

## 4. Forgeries on the clean box (synthetic)

`admission/forge.py` copies every field of the real accepted Opus receipt, swaps in a different body and recomputes `output_sha256`/`output_tokens_sha256`.

| Forged body | Box response |
|---|---|
| Accepted chapter with its first two bold-led lines un-bolded (fails shape) | **400**: "fails the compression v1 checks the pinned runner applies"; library unchanged |
| First run's crude Haiku receipts (`t_a350c932`) | **400**: "workflow is None…"; library unchanged |
| Opus's own rejected draft from this run (failed only a quotation check) | **200, `pinned`** |
| Accepted chapter plus one added sentence (well-formed) | **200, `pinned`** |

The last two rows are the documented limit: receipts are local runner evidence, not provider attestation. One new fact matters for the decision. Every rejected draft recorded across both re-runs (9 of 9) failed a **quotation** check. Those checks need the private source packet, which is not in the ZIP. So the new shape check blocks shape failures, but it would not block the most common real rejection if an agent forged around it. In this run the helper change removed the cause: no agent held a rejected draft it was asked to repair, and none forged.

**Owner decision (proposal in Wisdom `docs/authoring/PINNED-WORKFLOW.md`, nothing built):**
- **A:** the app authors server-side with an app-held Anthropic key and signs receipts.
- **B:** bind the Anthropic response id. This cannot be verified today.
- **C:** carry the raw CLI JSON and source packet in the ZIP, so admission re-runs the full checks, including quotations.

The recommendation is A at the first shared or published `pinned` collection. C is cheap hardening that would also catch the quotation-failure forgery above.

## Follow-up

- James: pick A, A-later or C for attested receipts (see above).
- Merge Wisdom PR #10 at `6ec9780` so stock `wam install` delivers it without the `head_commit` pin.
- App Manager owner: app skills are still not visible to the stock `hermes-agent` container (unchanged from the first run).
- VM `wisdom63` is stopped, and its disk is kept on ThalesMedia.
