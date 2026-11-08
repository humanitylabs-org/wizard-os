# For testers / For everyone: release automation (proposal)

Status: **proposed** (Miguel + James agreed the model, Nov 2026). Amends DECISIONS #75 (72h soak, manual
promotion) and #96 clause 4 for release mirrors once approved. Nothing here runs before the PR is merged and the
owner step below is done.

## Model

| Shown to users | Channel id (unchanged) | Gets |
| --- | --- | --- |
| For testers | `latest` | every merge to main of a component, as soon as it publishes (at most one cut per 30 min) |
| For everyone | `stable` | the newest For testers release once it has been latest for 72h with no open `release-blocker` |

- Updates are always automatic on both channels (wizard-app-manager#465; the nightly
  `wam updates --apply-if-auto` follows the box's channel since #464, Refs #458).
- New work ships behind off-by-default feature switches. Testers turn them on in Settings › Appearance › Try new
  features or with the WizardOS Tracker app's Try it (same state; wizard-app-manager#466 owner-only same-origin
  route); on For everyone they stay off and can't be flipped (wizard-ux#1144 + #466).
- To stop a release reaching everyone: open (or label) any org issue `release-blocker`. The promoter holds until
  every such issue is closed, and says so in its report.

## Automation

1. **Cut** — `.github/workflows/release-cut.yml` → `tools/release_train.py cut`.
   Triggers: `repository_dispatch: component-published` sent by each component's `release-train-notify.yml`
   (`workflow_run` after a green `Publish public image` on main for wizard-ux and wizard-agent-service, after a
   green `test` or `image` on main for wizard-app-manager); a daily sweep; manual (dry run by default).
   `plan(any_merge=True)` moves every component whose newest publishable main commit is newer than latest's pin:
   Wizard UX / Agent Service to their newest published multi-arch image; the **App Manager** to its newest main
   commit with a green `test` run, pinned with its newest published `image` (as `source_commit` + `image_inputs`,
   so `check_release.py` proves no image input changed since). App Manager commits that only touch `releases/`
   (the mirror merges themselves) never count. Then: `candidate_json`, `check_release.py`,
   `promote_stable.py cut/check`, release tests, wizard-os PR, byte-identical wizard-app-manager mirror PR merged on
   the automated mirror check (below), wait until the public mirror serves it. Stops there: no rig, no promotion.
2. **Bursts** — at most one For testers cut per 30 minutes. One concurrency group (`release-train`) runs one train
   at a time and keeps only the newest queued request. A cut asked for within 30 minutes of the last change to
   `releases/latest` ends `DEFERRED` and sets the wizard-os variable `RELEASE_CUT_PENDING=1`; the `*/30` sweep runs
   only while that is set (a skipped job uses no runner minutes) and cuts everything newer in one release, then
   clears it.
3. **Promote** — `.github/workflows/release-promote.yml` (every 6h). `release_train.py promote-soaked --check`
   (wizard-os only, seconds) decides: latest newer than stable → `promote_stable.latest_since` ≥ 72h → no open
   `release-blocker` (`gh search issues --owner humanitylabs-org --label release-blocker`, fails closed). Only when
   due: KVM + qemu on the runner, the installed upgrade test from the current stable on a disposable guest,
   `promote_stable.py promote` **without** `--fast-track`, promotion PR, checked mirror. Otherwise `WAITING` /
   `HELD` / `nothing to promote` with the reason.
4. **Mirror check (replaces the per-cut human click)** — before merging any wizard-app-manager mirror PR,
   `verify_mirror` proves every file the PR changes is under `releases/`, is added or updated (never deleted), and
   has the same sha256 as the file at the same path on wizard-os main; `releases/README.md` (the App Manager's own
   provenance log) may only grow at its end. It posts the commit status `release-mirror/byte-identical` on the PR
   head (description: "N file(s) identical to wizard-os main@<sha>"), and the train merges only that exact head
   (`--match-head-commit`) after every other check is green and no review thread is open. Any mismatch posts a
   failure status and stops the train with the file and both hashes.

5. **Hotfix lane (wizard-os#434), off by default** — `WIZARD_TRAIN_HOTFIX_LANE=1` in the job env turns it on;
   unset, every release keeps the 30-min limit and the 72h soak. When a merged Wizard UX / Agent Service / App
   Manager PR closes or references an org issue labelled `hotfix` (updated in the last 30 days; read with
   `gh search issues` + the issue timeline, compare API for "is this commit in that pin", no clones):
   - **Cut:** a hotfix PR on a component main but not yet in latest skips the 30-min limit (the step says
     `hotfix lane: <repo>#<n> waiting; cutting now`).
   - **Promote:** a latest that carries a hotfix PR not yet in stable moves after **24h** instead of 72h; after
     **0h** when the hotfix issue is also labelled `breaking` or the PR closes a `release-blocker` issue. Any open
     `release-blocker` still holds it, and the installed upgrade test still runs first. The promotion record uses
     `promote_stable.py promote --fast-track` with a `Hotfix lane (wizard-os#434): ...` reason, so
     `promote_stable.py check` (and its mirrored copy) is unchanged.
   - Any GitHub read error keeps the normal timing (fails toward waiting).
   - **To turn it on** (needs a workflow edit, which the builder token can't push): add
     `WIZARD_TRAIN_HOTFIX_LANE: "1"` to the `cut` job env in `release-cut.yml` and to both `gate` and `promote` job
     envs in `release-promote.yml`. The promote schedule (every 6h) means "right away" is within 6h unless someone
     runs the workflow by hand.

## Runners

- Every release job runs on **GitHub-hosted `ubuntu-latest`** by default: it has gh, git, python3, docker buildx
  and `/dev/kvm` (enabled with GitHub's documented udev rule in `.github/actions/upgrade-rig-setup`, which also
  installs qemu + cloud-localds and starts a user systemd manager for the rig). Proven on wizard-os (private repo,
  2 vCPU / 7 GB runner, 7 Nov 2026): `/dev/kvm` opens, the guest boots, the golden Hermes guest builds in ~3 min and
  the public installer runs; the guest is sized to 2 vCPU / 6 GB there (`WIZARD_RIG_SMP`, `WIZARD_RIG_MEM_MB`) and
  keeps 4 vCPU / 8 GB on a box. **Not yet proven there:** both hosted trial runs (0.3.102 → 0.3.105) ended the
  stable *install* `degraded: wam recover failed` before the upgrade step, while the same install passed on
  oscar-main's 4 vCPU rig (5 Nov). A failed test fails closed (Stable does not move). Until a hosted run passes, set
  `RELEASE_UPGRADE_RUNNER` to a self-hosted x86_64 Linux/KVM runner label: that moves only the promote job (the
  upgrade test); the gate and every cut stay hosted.
- Runner choice is one variable per job: `runs-on: ${{ vars.RELEASE_RUNNER || 'ubuntu-latest' }}` (cut and the
  promote gate) and `${{ vars.RELEASE_UPGRADE_RUNNER || 'ubuntu-latest' }}` (the upgrade test + promotion job). Set them as **wizard-os
  repository variables** (Settings › Secrets and variables › Actions › Variables): on GitHub Free, organization
  variables and secrets are not visible to private repositories such as wizard-os.
- The existing self-hosted macOS `release-acceptance.yml` is unchanged.

### Moving to the Mac later

1. On the Mac, register a self-hosted runner for humanitylabs-org/wizard-os (Settings › Actions › Runners › New
   self-hosted runner) with the label `release-mac`.
2. Set the wizard-os repository variable `RELEASE_RUNNER` to `release-mac`; the next cut runs there, nothing else changes.
3. Keep `RELEASE_UPGRADE_RUNNER` unset (GitHub-hosted): the upgrade test boots an x86_64 Linux guest under KVM, which
   macOS cannot do; point it only at a Linux/KVM runner label.

## Owner setup (one token)

The train has one writer, `wizardosbuilder`, and one secret, `RELEASE_TRAIN_TOKEN`.

1. **Access for the account** (org admin, once): `wizardosbuilder` needs **Write** on wizard-os and
   wizard-app-manager (today: none and read) as well as wizard-ux and wizard-agent-service (already Write).
   It must be an **organization member**, not an outside collaborator, for a fine-grained token to reach these
   repos (GitHub does not yet let outside collaborators use fine-grained tokens).
2. **The token** (signed in as wizardosbuilder): Settings › Developer settings › Fine-grained tokens › Generate.
   Resource owner `humanitylabs-org`; repositories wizard-os, wizard-app-manager, wizard-ux, wizard-agent-service;
   permissions **Contents, Pull requests, Issues, Commit statuses, Variables: Read and write**; **Actions: Read**
   (Metadata: read is automatic). An org owner approves the token request (Settings › Personal access tokens ›
   Pending requests) unless the org skips approval.
3. **Paste the same token under the same name** (one token, one name; two boxes because GitHub Free does not
   show organization secrets to private repos such as wizard-os):
   - **wizard-os** (required: the train): humanitylabs-org/wizard-os › Settings › Secrets and variables › Actions ›
     New repository secret › `RELEASE_TRAIN_TOKEN`
     (`gh secret set RELEASE_TRAIN_TOKEN -R humanitylabs-org/wizard-os`).
   - **organization** (the merge → For testers trigger): humanitylabs-org › Settings › Secrets and variables ›
     Actions › New organization secret › `RELEASE_TRAIN_TOKEN`, repository access: wizard-ux,
     wizard-agent-service, wizard-app-manager (public repos, so Free allows it)
     (`gh secret set RELEASE_TRAIN_TOKEN --org humanitylabs-org --repos wizard-ux,wizard-agent-service,wizard-app-manager`).

There is no second token. Without the organization copy the components' `release-train-notify.yml` skips the
dispatch (it never fails a component's CI), and merges reach For testers by the daily sweep instead of within
minutes.

## Proposed DECISIONS entry (amends #75 and #96)

> **Nov 2026 — Miguel + James: For testers / For everyone.** Channels are shown as For testers (`latest`) and For
> everyone (`stable`). Every component merge to main (Wizard UX, Agent Service, App Manager) that publishes is cut
> onto For testers automatically, at most once per 30 minutes. A For testers release is promoted to For everyone
> automatically after 72h on latest if no `release-blocker` issue is open and the installed upgrade test from the
> current stable passes. Updates are always automatic. Feature switches live in Settings (For testers only) and the
> WizardOS Tracker app, and only work on For testers. The Recommended-fix fast-track (`release_train.py run`,
> DECISIONS #93 owner rule) stays. Release mirror PRs into wizard-app-manager merge on the automated
> `release-mirror/byte-identical` check instead of a per-cut non-author review (#96 clause 4 amended for mirrors
> only: their content is already reviewed in wizard-os, and the check proves the bytes are the same).

## Not decided here

- Making `release-mirror/byte-identical` a branch-protection required context on wizard-app-manager main is an
  optional settings change for an admin; the train already refuses to merge without it.
