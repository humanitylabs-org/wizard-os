# Hermes v0.22.7 fork build: why the compaction check failed (wizard-os#726)

On 19 Nov the forum acceptance run of the WizardOS fork build of Hermes passed 6 of 7 checks, and so did the
control build of plain upstream v0.22.7 from the same workflow. Both failed only "A long conversation keeps its
reasoning after compaction". This file records why, and what changed in the check. It moves no pin and files no
candidate.

| | |
|---|---|
| Image that failed on forum | `ghcr.io/defleur-agents/hermes-agent@sha256:1fc3a522a95dfd6b85a43b12fa3ea602b453a352a30bf01afc813c7c535b31ec` (upstream v0.22.7 `b200f5bc`, source-revision label `b200f5bc…` on amd64 and arm64, fork run [44515962008](https://github.com/defleur-agents/hermes-agent/actions/runs/44515962008)) |
| Baseline | `nousresearch/hermes-agent@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7` (v2026.9.24 = Hermes v0.21.5, pinned today) |
| Also run | `nousresearch/hermes-agent@sha256:3e9fe4c6ef36490f43aa0d0d80f9df64e9c92a576eee3042f1a97c8813c05355` (v0.23.3) |
| Where | builder machine, x86_64 Docker, no VM; `check.py` with the data folder from `HS_ROOT` and no `chown` (as in [hermes-v0.23.3.md](hermes-v0.23.3.md)); same Agent Service `cb92d01c…`, shell `c60920e7…` and `fake_model.py` as `run.sh` |

## Finding: the check's expectation was stale, Hermes did not lose anything

The old check sends the recall turn right after the turn that crosses the compaction threshold and expects the
three early facts to reach the model only through the summary on that turn.

| Check | v0.21.5 | v0.22.7 fork control | v0.23.3 |
|---|---|---|---|
| Old check (recall on the next turn) | PASS | **FAIL**, same as forum: facts still verbatim, none via the summary | FAIL ([hermes-v0.23.3.md](hermes-v0.23.3.md)) |
| New check (recall once a turn reaches the model compacted) | PASS, compacted on turn 1 | PASS, compacted on turn 2 | PASS, compacted on turn 2 |

What happens on v0.22.7 ([`hermes-fork-v0.22.7/compaction-timing.json`](hermes-fork-v0.22.7/compaction-timing.json)
has every request and the Hermes log lines):

1. After the long turn the gateway's session hygiene compacts the session (`compressed 39 → 6 msgs, ~65,143 →
   ~1,095 tokens`).
2. The next turn still goes to the model with the full history (40 messages, ~224 K characters). Hermes logs
   `Skipping preflight compression: rough estimate ~62,877 >= 54,400 is not anchored on real usage (last real
   provider prompt 0); deferring to the next response`. That deferral is new since v0.22
   (`agent/turn_context_compaction.py`): Hermes no longer compacts on its own estimate until the provider has
   reported the real size.
3. Hygiene compacts again after that turn, and from the next turn on the model gets the compacted history (8 to
   10 messages); the facts arrive only through the summary and the model recalls all three.

So the five fork edits were not the cause (plain upstream does the same), and no reasoning is lost. What an owner
pays is one extra full-size model call and one extra summary call after a compaction; hygiene starts at 85 % of the
context, so that call still fits. v0.21.5 used the compacted history on the very next turn.

## What changed in the check

`check_compaction` now sends up to three ordinary turns (`HS-ECHO settle<n>`) after the long turn and stops at the
first one whose request to the model is compacted (it carries the summary and none of the early fact turns), then
asks for the recall. The pass rule is unchanged: Hermes compacted, on the recall turn the facts reached the model
only through the summary, and the model recalled all three. The number of turns it took is reported as the
observation "When compaction reaches the model". A release that never uses its compacted history within three turns
still fails.

## The fork image publish step

The same 19 Nov control run (fork run 44515962008) built both architectures and pushed the multi-arch tag, then the
publish step failed: `imagetools inspect` of the tag it had just pushed answered `not found` from GHCR, printed
nothing, and `json.load` crashed on the empty input. The tag reads back fine since. `tools/hermes-fork/image.yml` now
reads the tag back with retries (8 tries, growing waits), never parses empty output, reads the digest and both
`linux/amd64` and `linux/arm64` revision labels with Go templates on the digest itself, and stops with a plain error
when the registry never answers or a label is wrong. Tried against a local registry with a `docker` wrapper that
answers `not found` first: the old step crashes with the same traceback, the new one retries and writes the summary.

## Still to do in the fork (Archimedes)

Copy the updated `image.yml` into the fork, re-run the forum acceptance with the updated `check.py`, and write the
candidate with `tools/hermes_fork_candidate.py` (#726 steps 1 to 4).
