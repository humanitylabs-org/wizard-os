# Install snapshots

A release JSON records compatible **component revisions**, image digests, and expected
catalog defaults. Its version names an install snapshot, not a shared UX, Service,
Android, or Mac version. Existing release files are historical identities; create a
new file rather than rewriting one.

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

## Provenance check

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

Advance `stable` only when the complete new JSON has passed provenance and
installer-contract checks. Never insert a placeholder digest to unblock a merge.
