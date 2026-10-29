#!/usr/bin/env bash
# Acceptance for `wizard hermes update --stable` (docs/HERMES_STABLE.md step 4): one fresh Lima VM on Thales with
# stock Hermes FROM_TAG from the official installer, linked to Wizard OS (alongside mode), seeded with chat sessions
# and a cron job, then: dry run (Hermes home hash unchanged), busy box (no quiet moment, nothing changed), forced
# failure (automatic rollback to FROM_TAG with history intact), real update to TO_TAG (exact commit, history and cron
# intact).
#
#   tools/acceptance/hermes-update/run.sh [FROM_TAG FROM_COMMIT TO_TAG TO_COMMIT]
#
# Env: WIZARD_WORK_ROOT (the work disk) or WORK; KEEP_VM=1 leaves the VM running. Writes
# $WORK/runs/<UTC stamp>/{results.json,RECEIPT.md,run.log,evidence/}. Run it under the shared heavy-work lock
# (wizard_heavy_submit, lane heavy).
set -euo pipefail
export PATH=/opt/homebrew/bin:$PATH
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/../../.." && pwd)
FROM_TAG=${1:-v2026.9.24}
FROM_COMMIT=${2:-f97608f178d1ffeca59860195ab7da295f7c8e5f}
TO_TAG=${3:-v0.21.6}
TO_COMMIT=${4:-818c13be1dc4fd28987e1e881a9408224afd4535}
WORK=${WORK:-${WIZARD_WORK_ROOT:?set WIZARD_WORK_ROOT to the work disk}/wizard-os/hermes-update-stable}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
RUN=$WORK/runs/$STAMP
VM=hu-$(echo "$STAMP" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9' | tail -c 12)
export LIMA_HOME=$WORK/lima
mkdir -p "$RUN/harness" "$LIMA_HOME"
cp "$HERE"/{guest.py,fake_model.py,lima.yaml} "$SRC/tools/wizard" "$SRC/tools/tests/mcp_fixture.py" "$RUN/harness/"
exec > >(tee -a "$RUN/run.log") 2>&1
echo "run $STAMP vm $VM on $(hostname): $FROM_TAG ($FROM_COMMIT) -> $TO_TAG ($TO_COMMIT)"
echo "wizard-os source $SRC at $(git -C "$SRC" rev-parse HEAD 2>/dev/null || cat "$SRC/.candidate-sha" 2>/dev/null || echo unknown)"
shasum -a 256 "$RUN/harness/wizard"
python3 - "$RUN/harness/lima.yaml" "$WORK" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
p.write_text(p.read_text().replace("__ACCEPT_ROOT_JSON__", json.dumps(str(pathlib.Path(sys.argv[2]).resolve()))))
PY
limactl create --tty=false --name "$VM" "$RUN/harness/lima.yaml"
cleanup() { [ "${KEEP_VM:-0}" = 1 ] || { limactl stop -f "$VM" >/dev/null 2>&1; limactl delete -f "$VM" >/dev/null 2>&1; }; }
trap cleanup EXIT
limactl start --tty=false "$VM"
limactl shell --workdir / "$VM" sudo loginctl enable-linger "$(limactl shell --workdir / "$VM" id -un)"
set +e
limactl shell --workdir / "$VM" python3 "$RUN/harness/guest.py" --out "$RUN" --from-tag "$FROM_TAG" \
  --from-commit "$FROM_COMMIT" --to-tag "$TO_TAG" --to-commit "$TO_COMMIT"
rc=$?
set -e
echo "guest exit $rc; VM $VM on $(hostname)"
[ -f "$RUN/RECEIPT.md" ] && cat "$RUN/RECEIPT.md"
exit $rc
