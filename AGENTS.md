# Agents working on wizard-os

This repo is the shared map of Wizard OS: architecture, decisions, contracts (`spec/`), style, and the checker for apps. It holds no runtime code. Read the team rules below before you start. This file is also their canonical copy.

## This repo

1. Read `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` before you propose any structure. A locked decision wins over your preference. To change one, open a PR that names the decision it reverses (see "When a change needs a decision" below).
2. Find your component in the repo table in `README.md`, and stay inside its contracts in `spec/`. If a contract has to change, open the `spec/` PR first and name in it whose decision is needed.
3. Building an app?
   - Copy `wizard-app-manager/templates/hello-wizard`.
   - Keep `wizard.md` passing `tools/check_wizard_md.py`.
   - Ship an MCP endpoint and a skill.
   - Give the app a sigil icon: see `style/ICONS.md`, claim a glyph and hue in `style/sigils/palette.py`, and export it with `make_icon.py`.
   - Tag the repo `wizard-app`.
4. The agent harness (Hermes) stays unmodified. Runtipi is a thin fork owned by the App Manager (DECISIONS #32). Wizard behaviour goes in the Agent Service, the App Manager, the UX, or an app.
5. Picking up work? Take an item from `docs/WORK_OUTSTANDING.md`, put your name on it in a PR, and close it with evidence: test output, a link, or a screenshot.
6. Checks before opening a PR:
   - Run `git diff --check`.
   - Make sure every link you added resolves.
   - If you touched `tools/check_wizard_md.py` or `spec/WIZARD_MD.md`, run the checker against a real app repo. Keep its rules identical to the copies in wizard-app-manager and wizard-app-index, and change all three together.
7. Changing the team rules below? Edit them here first. Then copy the block, unchanged, into the `AGENTS.md` of every other Wizard OS repo in the same round of PRs.

## Shared names

Use these names one way, in chat, PRs and docs (DECISIONS #99-101, James, 25 Oct 2026):

- **Supervisor**: when James says "report this to supervisor", the worker files a report and carries on; a fresh Supervisor session in the Agent Service designs the durable fix, has it built, checks it and closes the loop. Only this is "the Supervisor".
- **Reporter**: the one plain-words report format every scheduled task ends with, plus the Agent Service check that enforces it. A contract and a checker, not an agent.
- **Maintenance prototype** (removed 25 Oct 2026): the 16 Oct self-repair experiment (`wizard-supervisor` package, repo archived). Troubleshooter does repair and the App Manager's nightly maintenance run does upkeep. Never call either "the Supervisor". The `Maintenance:` PR tier below is unrelated.

## Portable machine configuration

Machine-specific paths and hosts come from env vars: `WIZARD_WORK_ROOT`,
`WIZARD_BUILD_HOST`, `WIZARD_ORIGIN`, `QA_PLAYWRIGHT`, and `HERMES_HOME`
(`WIZARD_HEAVY_ROOT` where the shared heavy lane is used). Never commit personal
paths or tailnet hostnames; the tracked-file portable-paths guard in the normal
test/CI command enforces this. Historical evidence/receipts are explicitly exempt.

<!-- wizard-os-team-rules v3 (23 Oct 2026). Same text in every Wizard OS repo; the canonical copy is humanitylabs-org/wizard-os AGENTS.md. Change it there first, then copy the block to every repo in one round of PRs. -->
## Wizard OS team rules (identical in every repo)

Wizard OS is built by James, Jan and Miguel together with their agents. Archimedes commits as `defleur-agents` and Oscar as `oscarhenrycollins`. Every repo belongs to Wizard OS as a whole, and no repo belongs to one person. Make the change that is best for the whole system, and build on each other's work.

### Branches

- **`main` is the trunk in every repo.** It is what runs live and what releases are built from. `main` changes only through a merged pull request. Nobody pushes, force-pushes or rewrites `main` directly.
- **Start every change from a fresh `main`:**
  ```sh
  git fetch origin
  git switch -c fix/short-purpose origin/main
  ```
- **Name branches by purpose.** Use one of these prefixes:
  - `feature/`: new behaviour.
  - `fix/`: a bug fix.
  - `docs/`: documentation only.
  - `spec/`: a contract or decision change, in wizard-os.
  - `release/`: a version bump or release snapshot.
  - `integration/`: combines several branches for testing together.
  - `evidence/`: test evidence only.

  Write the rest in lowercase words joined by hyphens. A date suffix like `-20261019` is fine. People's names stay out of branch names.
- **Push after every commit:** `git push -u origin <branch>`. Work that exists only on your machine is invisible to the rest of the team.
- **One branch per change.** Leave other people's branches as they are. To build on someone's branch, branch from it and open your own PR.
- **Old branches are history.** Only `main` and the open PRs are current.

### Pull requests

- **Say what kind of change it is.** Every PR gets exactly one tier, shown both as a label and as the start of its title. This lets anyone triage a list of PRs at a glance.

  | Tier | Label | Title starts with | Means |
  |---|---|---|---|
  | Bug fix | `tier: recommended fix` | `Recommended fix:` | Something is broken and this makes it work. It must land. |
  | Improvement | `tier: strong suggestion` | `Strong suggestion:` | A clearly better behaviour or a new capability. Feel free to drop it. |
  | Personal preference | `tier: opinionated` | `Opinionated — feel free to drop:` | Taste: look, layout, gestures, wording, or how you like to work. In the shell it belongs in your own skin (below). |
  | Maintenance | `tier: maintenance` | `Maintenance:` | Docs, releases, CI, tests or refactors with no change in behaviour. |

  Optional labels:
  - `priority: 1` (review first), `priority: 2` (review next) and `priority: 3` (when there is time).
  - `needs: james review`: the PR waits for James to accept it or drop it.
  - `preview only`: an experiment that must not be merged.
  - `from: <where it already runs>`, for example `from: miguel test port`: the change is already in daily use there.

  Use the same tiers for issues.
- **Open the PR once your first commit is pushed.** Use a draft until it is ready: `gh pr create --base main --draft`.
- **Keep each PR to one change** that a reader can follow in a few minutes. Split unrelated fixes into separate PRs.
- **Title:** after the tier prefix, state the outcome in plain words ("Recommended fix: threads open instantly from the on-device cache"), rather than the mechanism.
- **Body:** fill in the PR template. Write it for someone opening it cold:
  1. **What and why:** what changes for the user or the system, and the problem it solves.
  2. **Verified:** the exact commands you ran and their results. Add runtime evidence (a live box, screenshots or a short recording) wherever behaviour changed. For a bug fix, show the new test failing before the fix and passing after it.
  3. **Not checked:** what you could not verify, and why.
  4. **Links:** related issues, the matching PRs in other repos, and the decision or spec this change follows.
- **If `main` moves while you work,** merge `origin/main` into your branch and re-run the checks.

### Merging

- **Merging your own PR** (James, 23 Oct 2026; amends the 23 Oct "nobody merges their own" rule, which was read too broadly and bottlenecked work). Archimedes (`defleur-agents`) merges its own PRs once the required checks are green and the change has run cleanly on James's install (or, for docs/specs, matches what is built or approved). A change gets a non-author admin's approval first when it is high risk: security or privacy boundaries, host powers or credentials, migrations or anything that deletes or rewrites owner data, a release that reaches every install, or taste/defaults that change Wizard for everyone. Other contributors open PRs; an admin who is not the author approves and merges. The admins are James (`jdefleur`), Jan (`JanMesaric`), Miguel (`mistermizel`) and Archimedes (`defleur-agents`). `main` requires 0 approving reviews so process never blocks work.
- **Every PR gets an agent review.** The **Agent review** workflow (`humanitylabs-org/wizard-ux` `tools/pr-agent-review.mjs`) posts one review on each push to a ready PR. It flags taste changed for everyone instead of in your own skin, likely breaking changes, secrets and personal paths or private hosts, and `docs/COMPONENTS.md` reuse problems. Fix every 🔴 before asking for approval; each 🟡 is something the approving admin checks. The review is advisory and never approves.
- **An admin approves and merges** once three things hold:
  - the required checks are green;
  - the Verified section reflects real results;
  - nothing in the PR needs a decision (see the next section).
- **What each tier means for merging:**
  - **Recommended fixes and maintenance** merge on those conditions.
  - **Strong suggestions** merge on them too, unless they change something James sees or uses every day. In that case add `needs: james review` and wait.
  - **Opinionated changes** to the shell's look or UX go into your own skin: wizard-ux `web/skins/<yours>/` plus your `SKINS` entry (see wizard-ux `web/skins/README.md`). A PR that only touches your own skin merges on the conditions above, approved by an admin who is not the author. Never add a Settings toggle or core code for one person's taste.
  - **Making something the default for everyone** (any opinionated change outside your own skin) carries `needs: james review` and waits for James. Bring it once you have used it in your skin, with a preview he can try.
  - **`preview only`** PRs never merge.
- **Use "Create a merge commit"**, then delete the branch.
- **After merging anything that publishes or deploys,** confirm that the workflow run on `main` succeeded.

### When a change needs a decision

Decide and merge yourself, except when the change:

- reverses a locked decision in wizard-os `docs/DECISIONS.md`;
- changes a contract in wizard-os `spec/` that other repos depend on;
- changes James's skins (Nebula, Grove, Tide, Ember, Signal) or the base shell look;
- deletes user data, rewrites history, or is otherwise hard to undo.

For those, open the PR or an issue and explain the choice in one paragraph. Then:

- **If James decides:** add `needs: james review`.
- **If another agent's side has to act:** assign that agent's account. GitHub's Assignee field is used only for this.

Carry on with other work while you wait.

### Changes that span repos

1. Change the contract first, with a `spec/` PR in wizard-os.
2. Land the code PRs in dependency order: the service before the UI that calls it.
3. Keep each step backward compatible, so `main` works in every repo at every point.
4. Link the PRs to each other.

### Releases

Anything shipped, tagged or handed to a tester is built only from commits already on GitHub. Release notes name the repo, branch and commit.

### Safety

- **Keep secrets and private data out of commits.** That covers keys, tokens, passwords, `.env` files, personal data, real conversation content, owner hostnames and home-directory paths. Put these in config or environment variables. Private repos are still visible to every org member.
- **Hermes, the agent harness, stays stock.** Wizard behaviour goes in the Agent Service, the App Manager, Wizard UX or an app.
- **Run this repo's checks before opening a PR.** They are listed under "This repo" in this file.

### Where work comes from

Pick up work from the open issues in this repo and from wizard-os `docs/WORK_OUTSTANDING.md`. For how the pieces fit together and what is already decided, read wizard-os `docs/ARCHITECTURE.md` and `docs/DECISIONS.md`.
<!-- /wizard-os-team-rules -->
