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

## How WizardOS is built now (the 7 and 9 Nov 2026 calls)

James and Miguel's 7 and 9 Nov 2026 calls are the source of truth for this section; where it conflicts with the team rules below, this section wins from the **cutover** onward (DECISIONS #108-#112). Until the cutover, the team rules below still apply and `main` keeps moving through PRs. The cutover is one permission change: only the builder (`wizardosbuilder`) can merge, for humans and for every other agent. James and Miguel set its date once the Tracker and the builder are running.

- **Three kinds of issue; the kind sets the rules.** A **goal** is a big outcome that James sets; each has one owner who steers it, and it runs a week or longer. A **bug** is anything wrong or worse than it should be; anyone on the team and their agents can file one. A **feature** is something new (label `feature`). Small pieces of a goal are checklist items on the goal, never separate issues. Whether a feature is core or app is decided by its repo, not by a new type: **core** is wizard-ux, agent-service, app-manager and the other platform repos; **app** is Messenger, Calendar and every other app repo. Every issue lives in exactly one repo, chosen when it is filed.
- **Every issue says when it is done.** A goal states "done when"; a bug states what happens, what should happen, how to see it, a screenshot, and the version or device. The reviewing agent judges against that text, because the builder reads only the repo and the issue and never your memory.
- **Reporters update first.** Before filing a bug, update to the latest build and check it is still there.
- **One line:** Queued → Building → AI review → Human review → Done. The builder merges the work switched off. The agent of whoever opened the issue checks it matches what was asked and sends it back to Building if not (kept for now so the kick-back numbers can show whether it is redundant). After that the lane depends on the kind:
  - **Bug:** the opener tries it and approves; it merges. Until the product is stable we accept that some fixes add a new bug (about one in five) in exchange for speed; whoever hits it files it. Add a second reviewer once it is stable. The builder first checks the bug is general, not one person's setup, and does its own QA on a real install, because every "still not working" round-trip costs human time.
  - **App feature:** the builder picks it up at once. The opener's agent and the opener review it; no one else has to.
  - **Core feature:** the builder does **not** pick it up until James or Miguel accepts it (anyone may file one, and rejecting is normal). After the AI review the opener confirms it does what they meant, then presents it with the problem it solves, and James decides whether we want it at all. A feature lands switched off; the final yes removes the switch, and it goes out in the next For everyone build.
  - **Goal:** a goal's owner reviews it. It is a human thread of dated progress updates, not builder work.
  Works makes it permanently on and closes the issue. Doesn't work sends it back to Building.
- **Releases follow Chrome's two channels.** Every merge reaches **For testers** within minutes, switched off. A known-good tester build is promoted to **For everyone** about every three days, with anything not Done still off. These replace Latest and Stable, and the "automatic or ask me" setting goes. Testers are James, Jan, Miguel and Robert at first; later any user who opts in.
- **Experiments land switched off.** A feature James is still dialling in ships off by default; he turns it on for himself, then offers it to others. The switch for each change appears on that issue and in the chat that announces it, never only inside Settings.
- **Hotfix lane.** A bug labelled `hotfix` (only James, Miguel or the Troubleshooter may add it) goes to the front of the builder's queue, merges and reaches For testers first, and gets its AI and human review afterwards. It exists because the cutover removes everyone else's merge rights, and a broken pipeline cannot be fixed through itself. The Troubleshooter and the recovery path stay repairable without the pipeline.
- **Goals and tags.** The builder tags each feature and bug with the goal it serves, or none. Features outside any goal are fine because some are fast, but we watch their share per sprint. At each goal review a person samples ten tags, so a flattering tag rate shows up as its own number.
- **Rhythm.** The Tracker (`/board/`) shows goals, bugs and features, counts per step, time in each step, and how often work is kicked back to the builder, including the number of AI-review rounds. It also counts how often a person says "still not working" after review; the aim of the whole system is more leverage per human minute, so that is the number that matters most. Review daily at first, then weekly. Goals are read one by one; bugs are read as metrics. Once "Standardized development pipeline" is done, replace it with an "Optimized development pipeline" goal that sets targets for those metrics.
- **The builder's instructions are this file.** The builder starts every run from the repo as it stands and keeps no memory, so `AGENTS.md` is its only standing instruction and its quality sets the quality of the work. Changing `AGENTS.md` is a pull request like any other, reviewed by James or Miguel. When the builder, a reviewer or the metrics show repeated kick-backs from the same missing instruction, the owner of that goal or bug files the `AGENTS.md` change. Agents never write their own memory into this file.

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

<!-- wizard-os-team-rules v4 (24 Oct 2026). Same text in every Wizard OS repo; the canonical copy is humanitylabs-org/wizard-os AGENTS.md. Change it there first, then copy the block to every repo in one round of PRs. -->
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
  - `from: <where it already runs>`, for example `from: miguel test port`: the change is already in daily use there. A box in developer mode (below) uses `from: <owner> dev build`.

  Use the same tiers for issues. **Add the label when you open the PR** (`gh pr create --label "tier: ..."`); a PR without one shows as "No tier" on the board below. Agents label every PR they open, and add the missing label when they find one of their own without it.
- **Open the PR once your first commit is pushed.** Use a draft until it is ready: `gh pr create --base main --draft`.
- **Keep each PR to one change** that a reader can follow in a few minutes. Split unrelated fixes into separate PRs.
- **Title:** after the tier prefix, state the outcome in plain words ("Recommended fix: threads open instantly from the on-device cache"), rather than the mechanism.
- **Body:** fill in the PR template. Write it for someone opening it cold:
  1. **What and why:** what changes for the user or the system, and the problem it solves.
  2. **Verified:** the exact commands you ran and their results. Add runtime evidence (a live box, screenshots or a short recording) wherever behaviour changed. For a bug fix, show the new test failing before the fix and passing after it.
  3. **Not checked:** what you could not verify, and why.
  4. **Links:** related issues, the matching PRs in other repos, and the decision or spec this change follows.
- **If `main` moves while you work,** merge `origin/main` into your branch and re-run the checks.

### Two routes for every change

Every change reaches `main` one of two ways: **propose a fix** (`tier: recommended fix`) or **propose a feature** (any other tier). There is no third "my build" lane. Owners who only want Wizard to look or behave differently use their skin, settings or apps. People who change Wizard itself can run their branch first on a box in **developer mode**, which follows a named branch or fork instead of `latest`/`stable` (DECISIONS #97, wizard-os `releases/README.md`). That box is a test bench; the change still lands as a fix or feature PR.

### Tracking

**The [Wizard OS · PR pipeline](https://github.com/orgs/humanitylabs-org/projects/1) board is the source of truth for where every PR is**, across all repos: Draft → In review → Merged → On Latest → On Stable, or Dropped. wizard-os `tools/pr_board.py` syncs it every 15 minutes from the PRs and the release pointers, so nobody moves cards by hand; keep the tier label right and the board stays right. Check it before asking someone where a change is, and link it in status updates instead of listing PRs.

### Merging

DECISIONS #96 (24 Oct 2026). `main` keeps **0 required approvals** and non-strict status checks, so process never blocks work.

- **Humans are the only admins:** James (`jdefleur`), Jan (`JanMesaric`) and Miguel (`mistermizel`). Agent accounts (`defleur-agents`, `oscarhenrycollins`) hold Write and sit on `main`'s review-bypass list; they never change branch rules, collaborators or repository settings.
- **Fixes ship immediately.** A `tier: recommended fix` PR that is not on the high-risk list below merges by its author, human or agent, without waiting for another review, once all of these hold:
  - a regression test that fails on `main` before the fix and passes after it;
  - the required checks are green;
  - every review thread is resolved (Codex or Agent review findings fixed or answered).

  The release carrying it can go to stable the same day (DECISIONS #82).
- **Everything else needs a review by someone other than its author**, and that reviewer may be an agent (the Agent review workflow or another collaborator's agent). This covers features, maintenance, taste and defaults, and the **high-risk list, fixes included**: security or privacy boundaries, host powers or credentials, migrations or anything that deletes or rewrites owner data, and a release that reaches every install. A high-risk fix still ships the same day; it just gets that review first. Once the review, the required checks and resolved conversations hold, the author's agent merges; no human has to visit GitHub to click merge.
- **Every PR gets an agent review.** The **Agent review** workflow (`humanitylabs-org/wizard-ux` `tools/pr-agent-review.mjs`) posts one review on each push to a ready PR. It flags taste changed for everyone instead of in your own skin, likely breaking changes, secrets and personal paths or private hosts, and `docs/COMPONENTS.md` reuse problems. Fix every 🔴 before merging; each 🟡 is something the reviewer checks.
- **The Verified section must reflect real results** before anything merges.
- **What each tier means for merging:**
  - **Recommended fixes** merge on the fix conditions above.
  - **Strong suggestions and maintenance** merge after a non-author review, unless they change something James sees or uses every day. In that case add `needs: james review` and wait.
  - **Opinionated changes** to the shell's look or UX go into your own skin: wizard-ux `web/skins/<yours>/` plus your `SKINS` entry (see wizard-ux `web/skins/README.md`). Never add a Settings toggle or core code for one person's taste.
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
