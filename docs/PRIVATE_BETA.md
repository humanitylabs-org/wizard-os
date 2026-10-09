# Sharing an app before it's public (private beta)

**Question (James, 9 Oct 2026):** someone builds an app in private and wants a friend to beta-test it, without publishing it to every Wizard. How?

## Answer: visibility is the repo's GitHub visibility, plus who can read it

The catalog is whatever the App Manager can *see*. So the same three levels GitHub already has become the three levels of sharing, with no new server and no new permissions system.

| Level | How the developer sets it | Who sees the app in their Apps screen |
|---|---|---|
| **Private (just me)** | Private repo, or a local folder. Add it as a source: `{"local": "~/dev/my-app"}` or `{"git": "https://github.com/me/my-app"}`. | Only the developer's Wizard |
| **Beta (named friends)** | Private repo, tagged `wizard-app`. Invite the friend as a collaborator (read access is enough). | The developer + every invited friend whose Wizard is signed in to GitHub |
| **Public (everyone)** | Make the repo public, keep the `wizard-app` tag. | Every Wizard |

Promoting an app from beta to public is one click on GitHub ("Change visibility → Public"). Nothing in the app changes.

## What the friend does

1. Accept the GitHub invite.
2. In Wizard: **Apps → Sources → Sign in to GitHub** (once). Their Wizard stores a read-only token in `~/.wizard-os/github-token` (mode 600).
3. The beta app appears in their Apps screen under **Beta**, with the developer's name. Install it like any other app.

Without step 2, a Wizard only sees public apps. That is the safe default.

## Direct share link (no tag needed)

For a one-off "try this": the developer sends `wizard://install?repo=github.com/me/my-app` (or the https fallback page). The friend's Wizard adds that repo as a single source, runs the same `wizard.md` check, and shows an install screen that says **"Not in the catalog: shared with you by <developer>"**. Same access rule: a private repo still needs the friend to have been invited.

## Rules

- **Same check for every level.** A beta app runs the same `wizard.md` checker as a public one. Beta never means unchecked.
- **Label the source.** The Apps screen shows where each app came from: Public catalog, Beta (shared with you by X), Local (yours), Link.
- **The token is the friend's own and read-only.** Wizard asks for read access to repos only. It never needs write access, and it's never written into git config or logs (the App Manager sends it per command as a header).
- **Revoking access works the GitHub way.** Removing the collaborator stops future updates. An already-installed copy keeps running until the friend uninstalls it; the Apps screen marks it "no longer shared".
- **Updates follow the pinned-install rule** from the Nostr path in [ROLLOUT.md](ROLLOUT.md): a beta app updates only after the friend approves the new commit.

## Later: Nostr

At stage 2 of the Nostr path, a beta can also be an announcement shared only with chosen npubs (an encrypted or gift-wrapped NIP-34 announcement). Same three levels, different transport. Not needed for the GitHub phase.

## Status (9 Oct 2026)

- **Built:** the App Manager reads private repos when a token is present (`~/.wizard-os/github-token` or `GITHUB_TOKEN`), for both topic search and cloning. Tested on Telos: the private `humanitylabs-org/defleur-video` repo is found, checked and compiled.
- **To build:** the source label in the catalog (`found_via: public|beta|local|link`), the GitHub sign-in in the Apps screen, the `wizard://install` link, and the "no longer shared" state.
