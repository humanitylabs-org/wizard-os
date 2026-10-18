#!/bin/bash
# 02 (as wizard): exact PR #10 head (t_bf8aff5d rerun) from the bundle; source tests, checkers, code image build with the canonical tag.
set -uo pipefail
W=/Volumes/ThalesMedia/wizard-os/wisdom-63
SHA=$1
exec > >(tee $W/receipts/rerun/02-build.log) 2>&1
date -u +%FT%TZ; echo "candidate $SHA"
rm -rf ~/wisdom && git clone -q --branch feature/authoring-model-contract $W/stage/wisdom-6ec9780.bundle ~/wisdom && cd ~/wisdom
test "$(git rev-parse HEAD)" = "$SHA" && echo "SOURCE_SHA_OK $(git rev-parse HEAD)" || { echo "SHA MISMATCH $(git rev-parse HEAD)"; exit 1; }
grep -A1 '^recommends:' wizard.md
python3 --version
mkdir -p ~/tmp; TMPDIR=~/tmp python3 -m unittest discover -s qa -p 'test_*.py' 2>&1 | tail -4; echo "UNIT-EXIT=${PIPESTATUS[0]}"
python3 ~/wizard-app-manager/wam/wizardmd.py . | tail -1; echo "WAM-CHECK-EXIT=${PIPESTATUS[0]} (wam $(git -C ~/wizard-app-manager rev-parse --short HEAD))"
rm -rf ~/wos && git clone -q --depth 1 https://github.com/humanitylabs-org/wizard-os ~/wos && python3 ~/wos/tools/check_wizard_md.py . | tail -1; echo "WOS-CHECK-EXIT=${PIPESTATUS[0]} (wizard-os $(git -C ~/wos rev-parse --short HEAD))"
python3 tools/check_view.py; echo "VIEW-CHECK-EXIT=$?"
docker build -q -t ghcr.io/humanitylabs-org/wisdom:0.3.0-private.6 --label org.opencontainers.image.revision=$SHA . ; echo "BUILD-EXIT=$?"
docker image inspect ghcr.io/humanitylabs-org/wisdom:0.3.0-private.6 --format 'image {{.Id}} {{.Architecture}} rev={{index .Config.Labels "org.opencontainers.image.revision"}} {{.Size}}'
date -u +%FT%TZ
