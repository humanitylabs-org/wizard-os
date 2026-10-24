# Install snapshots

A release JSON records compatible **component revisions**, image digests, and expected
catalog defaults. Its version names an install snapshot, not a shared UX, Service,
Android, or Mac version. Existing release files are historical identities; create a
new file rather than rewriting one.

## Curator custody (DECISIONS #83)

Builders retain their repositories and publisher identities. AI Wizards keeps
**matching pinned bytes**, not a build service:

* Source: the public
  [WAM `curator-source-mirrors` release](https://github.com/humanitylabs-org/wizard-app-manager/releases/tag/curator-source-mirrors),
  with append-only `<owner>--<repo>--<40-hex-commit>.bundle` assets. A standalone
  Git bundle contains the exact commit and its reachable objects, not an archive
  merely claiming that SHA. Never delete or replace an asset when a default
  changes. This prerelease is **not a WAM binary/latest release**. Private source
  repositories are refused, rather than accidentally made public. Bundles avoid
  pushing unrelated builders' workflow trees into the manager's Git history.
* Images already at `ghcr.io/humanitylabs-org/*` are in org custody. Other
  digest-pinned Compose images are copied, without rebuilding or changing their
  multi-platform manifest, to
  `ghcr.io/humanitylabs-org/wizard-app-manager:curator-sha256-<64-hex>`.
  These are custody tags, **not App Manager binaries/releases**: production WAM
  `latest`/version tags are untouched. Reusing the existing public package avoids
  a new private-by-default package or registry account/permission setup.
  Install fallback uses that ref **with the original `@sha256:…` appended**.
  Anonymous manifest retrieval is part of commissioning.
* `default-mirrors.yml` runs every six hours and on dispatch, **main only**, on
  the WAM repo-scoped Thales runner. It executes WAM's reviewed
  `tools/mirror_defaults.py` against WAM's public release mirror and defaults.
  The inventory is the union of `stable`/`latest` default commits and the current
  indexed pinned publications for every default slot (including on-demand apps).
  An unpublished on-demand recommendation has no commit to copy and is reported
  explicitly; an unresolved ordinary default fails the job. Older copies remain.
  All Compose services/sidecars are included. Source-sidecar code stays in Git.
* Authentication: WAM's own job-scoped workflow token has contents/package-write
  permission. No personal/org-wide token, deploy key, or new Actions secret is
  needed. The dedicated WAM runner hook admits only this main-branch
  scheduled/manual workflow, never pull requests or forks. Temporary registry
  credentials are removed even after failure. This avoids the org's deliberate
  deploy-key restriction rather than relaxing it.
* Each job uploads `default-app-custody/mirrors.json` (30-day operational receipt).
  Every published bundle and copied image digest is read back; a conflicting
  existing ref/digest fails closed. Registry denial is not treated as absence.
  Mirror failures fail the scheduled job rather than claiming full custody.

WAM's Python installer and index-backed backend try the builder's exact commit
first. Only a failed fetch permits the deterministic public bundle URL, fetched
into a clean Git repository. Downloads are streamed with a 256 MiB limit. `rev-parse HEAD` must equal the approved full SHA **before** manifest
use or source/build packaging; a mismatching copy is deleted and rejected. No
mirror HEAD, mutable tag, latest-version substitution, or changed approval is used.
For digest-pinned non-org images, a present local copy or available origin wins;
only an unavailable origin permits the matching org mirror. The generated
Compose preserves the digest so Docker verifies the original bytes on pull.
Unpinned legacy images are never silently substituted. This mechanism does not
claim protection against GitHub/GHCR themselves being unavailable, nor mirror
unpublished defaults or arbitrary dependency download services used by a build.

Before promoting a newly changed default, dispatch this workflow and require its
receipt to cover the new commit and image digests. The timer refreshes custody;
it cannot recover a builder commit deleted before its first successful mirror.
Source/image policy enforcement and the Cloudflare image's ownership move remain
the separate image-policy work from #136.

## Split images

New split snapshots need all three image keys:

| Image / `built_from` component | `get.sh` exports | Default slot |
| --- | --- | --- |
| `wizard-app-manager` | `WAM_IMAGE` | manager container |
| `wizard-agent-service` | `WIZARD_AGENT_SERVICE_IMAGE` | `agent-service` → `wizard-agent-service` |
| `wizard-ux` | `WIZARD_UX_IMAGE` | `shell` → `wizard-ux` |

The WAM component commit selects the exact installer checkout. `ref` supplies the
repository name; `digest` is authoritative. Use published immutable version or
full-SHA tags for readable references, and always retain the digest. Never combine
`wizard-shell` with the split pair. Historical bundled releases remain readable.

The current split consumer is WAM main
`e39576a0e28e95b5eef996454a269288ba37e8c2` (PR48). Its `get.sh` validates both split
pins and passes them to `install.sh`; alongside state records them for compose
materialization. Readback checks the manager and both app containers; updates are
ordered Service before UX. A failed installer does not queue updates. This is not
fresh-box acceptance: fresh bootstrap still takes catalog defaults and reports
image drift; strict mode rejects drift. Catalog commits and manifests are not
changed by an OS release JSON.

## Hermes pin (from 0.3.23)

Every snapshot from 0.3.23 on names the one upstream Hermes release it runs
([docs/HERMES_STABLE.md](../docs/HERMES_STABLE.md), DECISIONS #74):

```json
"hermes": {
  "tag": "v2026.9.24",
  "commit": "f97608f178d1ffeca59860195ab7da295f7c8e5f",
  "image": {"ref": "docker.io/nousresearch/hermes-agent:v2026.9.24",
            "digest": "sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7"},
  "test_record": "none: carried over from 0.3.21, pinned before Wizard stable existed",
  "rollback": null
}
```

`tag` is a final upstream tag (never an `rc.*` build or the floating `stable`/`latest`
labels). `image` is `null` only for a source-only release, which the container
`hermes-agent` default cannot use. `test_record` is `docs/acceptance/hermes-<tag>.md`
from the Thales test run. `rollback` names the previous pin (`tag` + `commit`). Online,
the checker resolves the tag's commit upstream, finds the digest on Docker Hub, and
reads the `hermes-agent` app's `image/Dockerfile` at its pinned commit to prove it builds
`FROM nousresearch/hermes-agent:<tag>@<digest>`.

## Provenance check

For a newly tested Hermes pin, `hermes.commit` is the **source tag's commit** and
`hermes.image.commit` is the **image's vouched-for source commit**. They must agree.
The online checker verifies the image digest and both Linux architectures' full
`org.opencontainers.image.revision` labels, with digest-verified manifest/config
reads. Missing labels, a missing architecture, differing revisions, or an image
built before its tag block promotion. Historical `none: carried over…` pins may
omit `image.commit`; their online revision still has to equal the tag commit.
The v0.21.6 container acceptance record covers `a28a5d03`, not source tag
`818c13be`, so that digest must not be promoted as the tag's tested image.

```sh
python3 tools/check_release.py releases/<version>.json --offline
python3 tools/check_release.py releases/<version>.json
python3 -m unittest tools/tests/test_check_release.py tools/tests/test_release_provenance.py -v
```

Offline checks require a complete bundled or split shape, matching core slots,
40-hex commits, source mappings, valid image references and both architectures.
Online checks additionally verify branch ancestry, anonymous digest availability,
and every platform's OCI revision label or BuildKit provenance. An older
`source_commit` is allowed only when the workflow's path filter is covered by
`image_inputs`, the workflow itself is included, and no covered path changed
(including a rename out of the input tree). Unknown ancestry, absent path filters,
and GitHub's 300-file compare cap fail closed. Workflows rebuilding every push
require an exact source/image match.

A green checker establishes source/image identity, **not** a working fresh install,
production activation, a native build, or catalog availability. `DRIFT` lines are
not suppressed when the live catalog differs or cannot be reached.

## Channels: latest and stable

DECISIONS #75 (James, 21 Oct 2026). Two pointers, both mirrored to
`wizard-app-manager/releases` beside the release JSONs:

- `releases/latest` names every release as soon as it is cut. Boxes whose owner ran
  `wam updates --channel latest` (or installs with `WIZARD_CHANNEL=latest`) follow it.
- `releases/stable` names the newest **promoted** release. Fresh installs, every box on
  the default channel, and every Automatic update take only this.

A release is promoted when it has been on latest for 72 hours and an upgrade from an
older release onto it passed on a test box (Thales, or the demo box). A fix release
skips the 72 hours (DECISIONS #82, see "Fast track" below). The promotion record
`releases/promotions/<version>.json` carries that evidence:

```json
{"version": "0.3.26", "latest_since": "2026-10-21T12:00:00Z", "promoted_at": "2026-10-24T12:30:00Z",
 "upgrade_test": {"from": "0.3.25", "to": "0.3.26", "passed": true,
                  "evidence": "docs/acceptance/update-0.3.26.md"}}
```

The flow:

```sh
python3 tools/promote_stable.py cut 0.3.26          # after the release JSON passes check_release.py
# ... 72h on latest; upgrade 0.3.25 -> 0.3.26 on a Thales test box ...
python3 tools/promote_stable.py promote 0.3.26 --from 0.3.25 --evidence <run log or report>
python3 tools/promote_stable.py check               # also run by the tests, here and in the mirror
```

`promote` refuses a short soak, a missing or failed upgrade test, and evidence-free
records. The App Manager's updater applies the same gate: Automatic skips a stable
pointer that has no valid record (Update by hand still works). Never edit a record by
hand or fake `--latest-since`. 0.3.25, stable when the channels split, carries a
`grandfathered` record; no later release can.

### Fast track for verified fixes

DECISIONS #82 (Miguel, 22 Oct 2026; amends #75). The soak exists to catch surprises in
new behaviour. A fix is the opposite case: every extra day on latest leaves stable boxes
broken. So:

| Release contains | Soak | Needs |
|---|---|---|
| Fixes only (each with a regression test) | none | upgrade test from the current stable passed (+ fresh install when a box allows it), `--fast-track` |
| Any feature, data-format change or big UX change | 72h on latest | upgrade test passed |

```sh
python3 tools/promote_stable.py promote 0.3.32 --from 0.3.25 \
    --evidence docs/acceptance/promote-0.3.32.md \
    --fast-track --classification fix --reason "stable 0.3.25 Store is broken on fresh boxes" \
    --notes "ride-alongs: ... (risk: ...)"
```

The record gains `"fast_track": {"classification": "fix", "reason": ..., "notes": ...}`.
`--classification feature` is refused, a missing reason is refused, and the upgrade
test and its evidence are still required. When a fix release carries already-merged
feature ride-alongs, list each one and its risk in `--notes` and say so on the
rollout issue; promote only if the demo tests pass. Both gates
(`tools/promote_stable.py`, `wam/updates.py`) accept exactly the same records
(`test_identical_to_the_app_manager_gate`).

**Rolling back a promotion:** point `releases/stable` back at the previous stable in
both repos (it already has a valid record), mirror, done. Boxes that already took the
new release stay on it; the next promoted release moves them on. To drop the policy
itself, remove the `fast_track` branch from both gates (fast-tracked records then fail
`check`, so move `stable` back first).

## PR pipeline board

[Wizard OS · PR pipeline](https://github.com/orgs/humanitylabs-org/projects/1) (org members
only) shows every pull request in the repos a release pins, plus wizard-os and try-wizard,
in one of six columns: **Draft → In review → Merged → On Latest → On Stable**, or
**Dropped**. Each card carries its **Tier** (from the `tier:` label) and **Opened by**, so
the board can be filtered to open fixes or one person's PRs.

`tools/pr_board.py` keeps it in sync every 15 minutes (a timer on the Archimedes VPS). A
merged PR moves to On Latest or On Stable once the commit that `releases/latest` or
`releases/stable` pins for its repo contains it, so the board follows
`tools/promote_stable.py` with no extra step. Repos no release pins stop at Merged.
Finished cards are archived two days after merge or close. Run it by hand with
`python3 tools/pr_board.py` (`--dry-run` prints the counts only); it needs `gh` with the
`project` scope.

## Publication is a separate gate

`get.sh` defaults to the anonymous raw GitHub URL for `releases/stable`, followed
by `<version>.json`. A private repository returns 404 without credentials even
when an authenticated GitHub read succeeds. Verify both URLs anonymously before
claiming the one-command public installer uses a release. Do not make the whole
repository public as a workaround; publish only approved release files through
the owner's release-hosting route and configure its base URL if needed.

For an authenticated team member with the exact release files already downloaded,
`WIZARD_RELEASE_BASE=file:///absolute/path/to/releases WIZARD_RELEASE=<version>`
selects that local artifact. It does not bypass image validation or fix absent
images. Run the installer only on the intended fresh/alongside target, not on a
live machine just to check the manifest.

Advance `latest` only when the complete new JSON has passed provenance and
installer-contract checks, and `stable` only through `tools/promote_stable.py promote`. Never insert a placeholder digest to unblock a merge.
