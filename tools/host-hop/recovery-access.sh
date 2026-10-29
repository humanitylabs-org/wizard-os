#!/bin/bash
# Restricted reverse key: no arbitrary shell, forwarding, or interactive sessions.
# Install on the source as the forced command of the target's recovery key, e.g. in authorized_keys:
#   from="<target tailnet IP>",restrict,command="<HOP_DIR>/recovery-access.sh" ssh-ed25519 AAAA... host-hop-recovery
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
export XDG_RUNTIME_DIR="/run/user/$(id -u)" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus" DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
case "${SSH_ORIGINAL_COMMAND:-}" in
 probe) printf 'host-hop-reverse-ok %s\n' "$(hostname -s)";;
 status) exec /usr/bin/python3 "$D/runner.py" status;;
 abort) exec /usr/bin/python3 "$D/runner.py" abort;;
 recover-source) exec /usr/bin/python3 "$D/runner.py" recover-source;;
 *) echo 'restricted host-hop key: allowed probe, status, abort, recover-source' >&2; exit 64;;
esac
