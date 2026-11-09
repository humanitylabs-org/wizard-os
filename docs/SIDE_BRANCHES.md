# Side branches ledger

Live == main: nothing runs from a side branch, and no new `integration/*`, `live/*` or `live-*` branches
should be created (wizard-os #491). Every such branch still on `origin` gets one row here with a decision.
`tools/side_branches.py` compares this table with the branches on origin and lists what is still open
(run `git fetch --prune origin` first).

Decision words (the cell must start with one):

- `undecided`: nobody has decided yet. This is the starting state; the builder never decides for people.
- `land`: the wanted part lands on `main` by PR; name the PR.
- `abandon`: dropped; name the person who signed off. A person may then delete the branch.
- `keep`: stays on origin; give the reason.
- `deleted`: the branch is gone from origin; the row stays as history.

Do not touch `owner-snapshot/*` branches (some live work is saved only there), and touch a branch tied to
an open PR only after that PR is merged or closed.

Facts as of 9 Nov 2026 (`git cherry origin/main <branch>`, files changed since the merge base). All 7 were
written by Archimedes (`defleur-agents`) for release 0.2.2 / 0.3.17 acceptance runs.

| Branch | Decision | Facts and notes |
|---|---|---|
| `integration/l4-fresh-install-0317` | undecided | last 2026-10-23, 9 commits not on main, 6 files. Head of open draft PR #94: wait until #94 is merged or closed. |
| `integration/e2e-022-ai-flow` | undecided | last 2026-10-18, 31 commits not on main, 20 files. No PR. |
| `integration/e2e-022-acceptance` | undecided | last 2026-10-17, 14 commits not on main, 11 files. PR #51 closed unmerged. Same top commits as `e2e-022-runner`. |
| `integration/e2e-022-runner` | undecided | last 2026-10-17, 14 commits not on main, 11 files. No PR. Same top commits as `e2e-022-acceptance`. |
| `integration/e2e-022-ui-proof` | undecided | last 2026-10-17, 12 commits not on main, 11 files. No PR. |
| `integration/e2e-022-alongside` | undecided | last 2026-10-17, 4 commits not on main, 4 files. No PR. |
| `integration/style-review-20261015` | undecided | last 2026-10-15, 2 commits not on main, 2 files. No PR. |
