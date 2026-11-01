# Proposal: dev flow after the stable release

**Status: tabled.** This is a proposal, not the current process. The team rules in `AGENTS.md` still apply. Revisit it once Wizard OS has a stable release, and adopt it by a PR that updates `AGENTS.md`.

Drafted by Miguel with Oscar, 1 Nov 2026.

## The standard open-source model

Roles:

- **Users** report bugs and ideas.
- **Contributors** send PRs.
- **Maintainers** review and merge in the area they own.
- **Project lead** sets direction and breaks ties.

Flow:

1. An issue describes the bug or idea.
2. A contributor opens a small PR against `main`.
3. Checks run, a maintainer approves, and the PR is squash-merged.
4. A release is a tag on `main`, and the build runs automatically.

## Our model: everyone moves up a level

Agents do the building, so every role moves up one step. The bottom role mostly goes away: instead of only reporting, people tell their agent and it opens the PR. The top role can't move up, because a project has one lead. That leaves three roles.

- **Contributors: everyone.** Your agent turns your bug or idea into a PR.
- **Maintainers: area owners.** Each has the final say on their area. A maintainer grows by owning more, not by becoming another lead.
- **Project lead: one person.** Sets direction and decides only when maintainers disagree.

## For our team

Each person decides a different question, so there is never more than one person deciding the same thing.

| Person | Role | Decides |
|---|---|---|
| James | Project lead, explorer | **What** we build. Breaks ties on direction. |
| Jan | Maintainer of `main` and the process | **Whether it's ready.** Nothing reaches `main` or a release without his approval. |
| Robert | Design maintainer | **How it looks.** Any visible change needs his approval. |
| Miguel | Explorer | Tries ideas as quick MVPs. |
| Nolan, Joe (later) | Contributors through their agents | Own the website and marketing content; give product feedback. |

Whoever builds an app maintains that app.

## The flow: from rough to stable

1. **Explore.** James or Miguel try an idea fast as an app, a tweak or a preview build. No approval is needed, and `main` isn't touched.
2. **Propose.** If it proves itself, it becomes one small PR to `main`.
3. **Approve.** Checks and an agent review run first. Jan approves for quality. Robert also approves if the change is visible.
4. **Release.** Jan tags `main`. Every box updates itself, and the download links never change.

## Rules for agents

- Every agent PR names the human responsible for it.
- Agents never merge their own PRs.
- Agents do the first review, so humans only decide merge or close.

## What we stop doing

- Long-lived release branches. Every release is a tag on `main`.
- Tier prefixes in PR titles. Labels carry the tier.
- The required Reuse block in PR bodies.
- Long PR bodies. What changed, why, and how it was tested is enough.

## Watch for

- **James is lead and explorer.** His own ideas clear Jan's bar like everyone else's.
- **Jan as bottleneck.** Keep PRs small and let agents check most PRs against his bar; he looks closely only at risky ones.
