#!/bin/bash
# Fire-and-return continuation, run on the new main only, outside the gateway lifecycle:
# one agent turn that tells the owner the hop finished. Usage: continue.sh FROM TO
set -euo pipefail
. "$(dirname "$0")/lib.sh"
export XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
[ "$#" = 2 ] || exit 64
FROM="$1"; TO="$2"; known_host "$FROM"; known_host "$TO"
is_self "$TO" || exit 64
/usr/local/bin/host-hop-recovery status | python3 -c 'import json,sys;assert json.load(sys.stdin)["phase"]=="complete"'
STATUS="http://$(host_ip "$TO"):$HOP_STATUS_PORT/status.json"
URL="https://$(main_name).$HOP_TAILNET_SUFFIX:$HOP_SHELL_PORT/"
exec systemd-run --user --unit="host-hop-completion-$(date +%s)" --collect -p Type=exec -p RuntimeMaxSec=900 -p TimeoutStopSec=30 "$HOP_HOME/.local/bin/hermes" chat --oneshot --source tool --max-turns 12 --run-budget 600 -q "Host-hop finished. Do not change services, schedules, roles or files. Read $STATUS and verify phase complete. Load the notifications skill and send the owner ONE installed Notifications app notification that $HOP_AGENT moved from $FROM to $TO; address $URL. Include independent status $STATUS and say the old machine $FROM is stopped and kept as standby $(standby_name "$FROM"), not erased. Verify notification readback. If delivery fails, do not repeat indefinitely; the independent status is the authoritative result."
