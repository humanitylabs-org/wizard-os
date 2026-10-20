#!/bin/bash
set -euo pipefail
export PATH=/opt/homebrew/bin:$PATH
W=/Volumes/ThalesMedia/wizard-os/wisdom-63
export LIMA_HOME=$W/lima
limactl start --name wisdom63 --tty=false $W/scripts/vm.yaml
limactl shell wisdom63 -- uname -a
echo VM_READY
