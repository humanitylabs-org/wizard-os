# For testers / For everyone: release automation (proposal)

Status: **proposed** (Miguel + James agreed the model, Nov 2026). Amends DECISIONS #75 (72h soak, manual
promotion) once approved. Nothing here runs before the PR is merged and the open decisions below are settled.

## Model

| Shown to users | Channel id (unchanged) | Gets |
| --- | --- | --- |
| For testers | `latest` | every merge to main of a component, as soon as its image publishes |
| For everyone | `stable` | the newest For testers release once it has been latest for 72h with no open `release-blocker` |

- Updates are always automatic on both channels (wizard-app-manager#465; the nightly
  `wam updates --apply-if-auto` follows the box's channel since #464, Refs #458).
- New work ships behind off-by-default feature switches. Testers turn them on in the Wizard OS Tracker app
  (wizard-app-manager#466 API); on For everyone they stay off and can't be flipped (wizard-ux#1144 + #466).
- To stop a release reaching everyone: open (or label) any org issue `release-blocker`. The promoter holds until
  every such issue is closed, and says so in its report.

## Automation (existing tools, two new subcommands)

1. **Cut** — `.github/workflows/release-cut.yml` → `tools/release_train.py cut`.
   Trigger: `repository_dispatch: component-published` from each component's `Publish public image` workflow
   (and manual, dry-run by default). `plan(any_merge=True)` moves every image component whose newest *published*
   main commit is newer than latest's pin (not only Recommended fixes); then the existing path: `candidate_json`,
   `check_release.py`, `promote_stable.py cut/check`, release tests, wizard-os PR, byte-identical
   wizard-app-manager mirror PR (Codex/non-author review, DECISIONS #96), wait until the public mirror serves it.
   Stops there: no rig, no promotion.
2. **Promote** — `.github/workflows/release-promote.yml` (every 6h) → `tools/release_train.py promote-soaked`.
   latest newer than stable → `promote_stable.latest_since` ≥ 72h → no open `release-blocker`
   (`gh search issues --owner humanitylabs-org --label release-blocker`, fails closed) → installed upgrade test from
   current stable on the KVM rig → `promote_stable.py promote` **without** `--fast-track` → promotion PR + mirror.
   Otherwise `WAITING` / `HELD` / `nothing to promote` with the reason.

Component side (one step per component repo, after its publish job; plan only, not in this PR):

```yaml
  notify-release-train:
    needs: [finalize]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - env: { GH_TOKEN: "${{ secrets.RELEASE_TRAIN_DISPATCH_TOKEN }}" }
        run: >
          gh api -X POST repos/humanitylabs-org/wizard-os/dispatches -f event_type=component-published
          -f "client_payload[repo]=${{ github.repository }}" -f "client_payload[sha]=${{ github.sha }}"
```

Repos: wizard-ux, wizard-agent-service. wizard-app-manager stays a manual cut (its image/maintenance-branch
provenance needs a person, as today).

## Proposed DECISIONS entry (amends #75)

> **Nov 2026 — Miguel + James: For testers / For everyone.** Channels are shown as For testers (`latest`) and For
> everyone (`stable`). Every component merge to main whose image publishes is cut onto For testers automatically.
> A For testers release is promoted to For everyone automatically after 72h on latest if no `release-blocker`
> issue is open and the installed upgrade test from the current stable passes. Updates are always automatic.
> Feature switches live only in the Wizard OS Tracker app and only work on For testers. The fix fast-track
> (`release_train.py run`, DECISIONS #93 owner rule) stays for Recommended fixes.

## Open decisions

1. Runner: the train needs gh, docker buildx and KVM; today it runs from a host, wizard-os runners are self-hosted
   and often offline. Which machine gets the `release-train` label?
2. Token: `RELEASE_TRAIN_TOKEN` / `RELEASE_TRAIN_DISPATCH_TOKEN` (repo scope) — org secret owner.
3. Mirror merge: each cut still waits for a non-author review of the mirror PR (DECISIONS #96). Fully hands-off
   needs James to accept an automated reviewer or keep a human click per cut.
4. Batching: a burst of merges produces one cut per published image (concurrency group serializes them); OK, or
   debounce (e.g. at most one cut per hour)?
5. Create the `release-blocker` label in each repo (org settings: not done here).
