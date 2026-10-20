#!/bin/bash
# 01: fresh box, stock one-line Wizard OS install (aiwizards.com/os.sh == wizard-app-manager get.sh@main), fresh mode,
# as root, no tailnet. No creator context: new VM, no Hermes, no James files.
set -uo pipefail
W=/Volumes/ThalesMedia/wizard-os/wisdom-63
exec > >(tee $W/receipts/01-box.log) 2>&1
date -u +%FT%TZ; uname -m; hostname
command -v hermes || echo "no hermes on this box (fresh)"; ls /home
WAM_MAIN=$(git ls-remote https://github.com/humanitylabs-org/wizard-app-manager refs/heads/main | cut -f1); echo "wam main $WAM_MAIN"
curl -fsSL https://aiwizards.com/os.sh -o /tmp/os.sh; sha256sum /tmp/os.sh
curl -fsSL "https://github.com/humanitylabs-org/wizard-app-manager/raw/$WAM_MAIN/get.sh" | cmp - /tmp/os.sh && echo "os.sh == get.sh@main"
time sudo env WIZARD_MODE=fresh WAM_REF=main WIZARD_PRIVATE_ACCESS=none bash /tmp/os.sh </dev/null 2>&1 \
  | grep -v -E 'Pulling fs layer|Download complete|Pull complete|Already exists|Waiting|Verifying|Extracting|Downloading' | tail -60
echo "INSTALL-EXIT=${PIPESTATUS[0]}"
sudo -iu wizard bash -lc 'git -C ~/wizard-app-manager rev-parse HEAD; ~/.local/bin/wam apps' 2>&1 | tail -30
sudo docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
date -u +%FT%TZ
