#!/bin/bash
# Forced-command admission fence (see HOP_FENCE_FORCED_COMMAND); installed only by the launched runner.
# While this host drains or is a standby, refuse; otherwise run the original forced command.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
if [ -e "$HOP_HOME/$HOP_STANDBY_LOCK_REL" ] || [ -e "$HOP_HOME/.hermes/.drain_request.json" ]; then
 echo 'service temporarily unavailable: this host is draining or standby' >&2
 exit 75
fi
[ -n "${HOP_FENCE_FORCED_COMMAND:-}" ] || exit 64
# shellcheck disable=SC2086
exec $HOP_FENCE_FORCED_COMMAND
