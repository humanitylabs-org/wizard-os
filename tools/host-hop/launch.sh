#!/bin/bash
# Start the host-hop runner in its own systemd user unit (independent cgroup; never inside the gateway).
#   launch.sh --probe FROM TO                  read-only preflight in a throwaway unit
#   launch.sh --parent-recovery-sent FROM TO   the hop; needs HOP_PARENT_LAUNCH=OWNER_RECOVERY_SENT
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
export XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
[ "$#" = 3 ] || { echo 'usage: launch.sh --probe FROM TO | --parent-recovery-sent FROM TO'; exit 64; }
FROM="$2"; TO="$3"
case "$1" in
 --probe)
  unit="host-hop-preflight-$(date +%s)"
  exec systemd-run --user --unit="$unit" --wait --pipe --collect -p Type=exec -p RuntimeMaxSec=120 /bin/bash -c 'cat /proc/self/cgroup; exec /usr/bin/python3 "$1/runner.py" preflight "$2" "$3"' _ "$D" "$FROM" "$TO";;
 --parent-recovery-sent)
  [ "${HOP_PARENT_LAUNCH:-}" = OWNER_RECOVERY_SENT ] || { echo 'Parent must first send verified recovery instructions, then explicitly set HOP_PARENT_LAUNCH=OWNER_RECOVERY_SENT'; exit 64; }
  # Fail-and-return; manager owns the process, never --wait on an embedded chat run.
  exec systemd-run --user --unit="host-hop-cutover-$(date -u +%Y%m%dT%H%M%SZ)" --collect -p Type=exec -p RuntimeMaxSec=21600 -p TimeoutStopSec=600 --setenv=HOP_PARENT_LAUNCH=OWNER_RECOVERY_SENT /usr/bin/python3 "$D/runner.py" execute "$FROM" "$TO";;
 *) echo 'usage: launch.sh --probe FROM TO | --parent-recovery-sent FROM TO';exit 64;;
esac
