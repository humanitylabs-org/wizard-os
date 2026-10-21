#!/usr/bin/env bash
# Connection Router acceptance on Thales: Claude only, ChatGPT only, both, neither (wizard-os WORK_OUTSTANDING).
# Run from the staged harness under /Volumes/ThalesMedia/wizard-os/router-acceptance/harness/<sha>/ (stage.sh puts it
# there), through the wizard-heavy queue. Creates a fresh Lima VM, runs the four states, judges them, deletes the VM.
# Evidence: $ROOT/runs/<run id>/ (RECEIPT.md, checks.json, evidence/<state>/*.json|png|log).
set -uo pipefail
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
ROOT=/Volumes/ThalesMedia/wizard-os/router-acceptance
HERE=$(cd "$(dirname "$0")" && pwd)
STAGE=$ROOT/stage
RUN_ID=${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}
RUN=$ROOT/runs/$RUN_ID
mkdir -p "$RUN/evidence"
exec > >(tee -a "$RUN/run.log") 2>&1
export LIMA_HOME=$ROOT/lima
VM=router-accept
RPORT=28802
PROV=$STAGE/PROVENANCE.json
ROUTER_IMAGE=$(python3 -c "import json;print(json.load(open('$PROV'))['router_image'])")
WISDOM_COMMIT=$(python3 -c "import json;print(json.load(open('$PROV'))['wisdom_commit'])")
UX=$STAGE/ux
export PW=${PW:-/Volumes/ThalesMedia/wizard-manager/qa/node_modules/playwright}
echo "== run $RUN_ID on $(hostname) $(date -u +%FT%TZ); harness $(cat "$HERE/HARNESS_SHA" 2>/dev/null)"

vm() { limactl shell --workdir / "$VM" sudo env ACCEPT_ROOT="$ROOT" ACCEPT_RUN="$RUN" ROUTER_IMAGE="$ROUTER_IMAGE" \
  WISDOM_COMMIT="$WISDOM_COMMIT" python3 "$HERE/vm_state.py" "$@"; }
sheet() { node "$HERE/sheet.cjs" "$UX" "$RUN/evidence/$1" "$1" "$2" "$RPORT" "$RUN/evidence/$1/apps.json" "${3:-wisdom,router-fixture}" "${4:-}"; }
forwarded() { for _ in $(seq 90); do curl -sf "127.0.0.1:$RPORT/health" >/dev/null && return 0; sleep 1; done; echo "Router port not forwarded"; return 1; }
cleanup() { limactl stop -f "$VM" >/dev/null 2>&1; limactl delete -f "$VM" >/dev/null 2>&1; echo "== VM $VM deleted"; }
trap cleanup EXIT

if lsof -nP -iTCP:$RPORT -sTCP:LISTEN >/dev/null 2>&1; then echo "port $RPORT already in use on the host"; exit 3; fi
limactl delete -f "$VM" >/dev/null 2>&1 || true
echo "== creating VM"; limactl create --name "$VM" --tty=false "$HERE/lima.yaml" && limactl start --tty=false "$VM" || exit 4
limactl shell "$VM" -- bash -lc 'cat /etc/os-release | head -2; uname -m; docker --version' | tee "$RUN/vm.txt"
echo "== images"
limactl shell --workdir / "$VM" sudo docker pull "$ROUTER_IMAGE" || exit 5
limactl shell --workdir / "$VM" sudo docker build -q -t "wisdom-accept:${WISDOM_COMMIT:0:7}" "$STAGE/wisdom-src" || exit 6
limactl shell --workdir / "$VM" sudo docker images --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}} {{.ID}}' | tee "$RUN/images.txt"

for state in claude-only chatgpt-only both neither; do
  echo "== state $state"
  if ! { vm up "$state" && forwarded; }; then echo "STATE $state did not start"; vm down "$state"; continue; fi
  vm collect "$state" pre
  case $state in
    chatgpt-only)
      vm runs "$state" pre
      sheet "$state" pre wisdom,router-fixture wisdom/look-up
      vm collect "$state" post
      vm runs "$state" post ;;
    both)
      sheet "$state" pre
      vm order "$state" wizard-claude,wizard-chatgpt; vm collect "$state" order-claude-first; sheet "$state" claude-first router-fixture
      vm order "$state" wizard-chatgpt,wizard-claude; vm collect "$state" order-chatgpt-first; sheet "$state" chatgpt-first router-fixture
      vm runs "$state" pre ;;
    *)
      sheet "$state" pre
      vm runs "$state" pre ;;
  esac
  vm down "$state"
done

echo "== judging"
python3 "$HERE/check.py" "$RUN"; verdict=$?
{
  echo "# Connection Router acceptance receipt"
  echo; echo "- Run: $RUN_ID on $(hostname) ($(sw_vers -productVersion 2>/dev/null)), finished $(date -u +%FT%TZ)"
  echo "- Harness: wizard-os $(cat "$HERE/HARNESS_SHA" 2>/dev/null) (tools/acceptance/router)"
  echo "- VM: Lima $(limactl --version | awk '{print $3}'), $(head -1 "$RUN/vm.txt"), fresh per run, deleted after"
  echo "- Inputs: $(python3 -c "import json;d=json.load(open('$PROV'));print('; '.join(f'{k}={v}' for k,v in d.items()))")"
  echo "- Checks: $(python3 -c "import json;d=json.load(open('$RUN/checks.json'));print(d['passed'],'passed,',d['failed'],'failed')")"
  echo "- Evidence: $RUN/evidence/<state>/"
} > "$RUN/RECEIPT.md"
cat "$RUN/RECEIPT.md"
exit $verdict
