#!/usr/bin/env bash
# Stage the Connection Router acceptance inputs on Thales (run on Telos). Copies source only: no credentials, no
# owner state. Pins every input and writes stage/PROVENANCE.json.
#   stage.sh <wizard-os checkout> <wizard-app-store checkout> <wizard-ux checkout> <wisdom checkout> <wizard-agent-service checkout>
set -euo pipefail
WOS=$1 STORE=$2 UX=$3 WISDOM=$4 WAS=$5
: "${WIZARD_BUILD_HOST:?set WIZARD_BUILD_HOST to the SSH worker}"
: "${WIZARD_WORK_ROOT:?set WIZARD_WORK_ROOT to the remote work disk}"
ROOT="$WIZARD_WORK_ROOT/wizard-os/router-acceptance"
ROUTER_IMAGE=${ROUTER_IMAGE:-ghcr.io/humanitylabs-org/wizard-connection-router@sha256:71e9721efc3904c76862b83613d6e88a1c5edff26432152f3727073fde417ecf}
HSHA=$(git -C "$WOS" rev-parse HEAD)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/stage/router-src/tests" "$T/stage/provider-models" "$T/stage/wisdom-src" "$T/stage/ux" "$T/harness/$HSHA"
git -C "$STORE" show HEAD:images/wizard-connection-router/tests/fake_provider.py > "$T/stage/router-src/tests/fake_provider.py"
git -C "$STORE" show HEAD:images/wizard-claude/models.json > "$T/stage/provider-models/claude-models.json"
git -C "$WAS" show HEAD:hermes-plugin/wizard-os/chatgpt.json > "$T/stage/provider-models/chatgpt-models.json"
git -C "$WISDOM" archive HEAD | tar -x -C "$T/stage/wisdom-src"
git -C "$UX" archive HEAD web tools | tar -x -C "$T/stage/ux"
git -C "$WOS" archive HEAD tools/acceptance/router | tar -x -C "$T/harness/$HSHA" --strip-components=3
echo "$HSHA" > "$T/harness/$HSHA/HARNESS_SHA"
python3 - "$T/stage/PROVENANCE.json" <<EOF
import json, sys
json.dump({"router_image": "$ROUTER_IMAGE",
           "router_source": "wizard-app-store@$(git -C "$STORE" rev-parse HEAD)",
           "claude_models": "wizard-app-store@$(git -C "$STORE" rev-parse HEAD):images/wizard-claude/models.json",
           "chatgpt_models": "wizard-agent-service@$(git -C "$WAS" rev-parse HEAD):hermes-plugin/wizard-os/chatgpt.json",
           "wisdom_commit": "$(git -C "$WISDOM" rev-parse HEAD)",
           "ux_commit": "$(git -C "$UX" rev-parse HEAD)",
           "harness_commit": "$HSHA"}, open(sys.argv[1], "w"), indent=1)
EOF
printf -v REMOTE_ROOT '%q' "$ROOT"
ssh "$WIZARD_BUILD_HOST" "mkdir -p $REMOTE_ROOT/stage $REMOTE_ROOT/harness && rm -rf $REMOTE_ROOT/stage/wisdom-src $REMOTE_ROOT/stage/ux $REMOTE_ROOT/stage/router-src"
rsync -a -s "$T/stage/" "$WIZARD_BUILD_HOST:$ROOT/stage/"
rsync -a -s "$T/harness/" "$WIZARD_BUILD_HOST:$ROOT/harness/"
rm -rf "$T"
echo "staged harness $HSHA → $WIZARD_BUILD_HOST:$ROOT/harness/$HSHA"
