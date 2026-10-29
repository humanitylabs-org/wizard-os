#!/bin/bash
# Install the independent status page and the restricted recovery client on the target.
# Usage (on FROM): install-status.sh FROM TO
# Prerequisite: FROM's authorized_keys holds the restricted key (recovery-access.sh as forced command)
# whose private half is $HOP_HOME/.ssh/host-hop_ed25519 on TO, and TO's
# $HOP_HOME/.ssh/host-hop_known_hosts pins FROM's host key.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
[ "$#" = 2 ] || die "usage: $0 FROM TO"
FROM="$1"; TO="$2"; known_host "$FROM"; known_host "$TO"; is_self "$FROM" || die "run on $FROM"
FROM_IP="$(host_ip "$FROM")"; TO_IP="$(host_ip "$TO")"
on_stdin "$TO" 'sudo -n install -d -m 755 /opt/host-hop-status; sudo -n tee /opt/host-hop-status/server.py >/dev/null; sudo -n chown root:root /opt/host-hop-status/server.py; sudo -n chmod 644 /opt/host-hop-status/server.py' < "$HOP_DIR/status-server.py"
on_stdin "$TO" 'sudo -n tee /usr/local/bin/host-hop-recovery >/dev/null; sudo -n chown root:root /usr/local/bin/host-hop-recovery; sudo -n chmod 755 /usr/local/bin/host-hop-recovery' <<EOF
#!/bin/bash
set -euo pipefail
case "\${1:-}" in status|probe|abort|recover-source) ;; *) echo 'usage: host-hop-recovery status|probe|abort|recover-source'; exit 64;; esac
exec /usr/bin/ssh -F /dev/null -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$HOP_HOME/.ssh/host-hop_known_hosts -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 -i $HOP_HOME/.ssh/host-hop_ed25519 $HOP_USER@$FROM_IP "\$1"
EOF
on_stdin "$TO" 'sudo -n tee /etc/systemd/system/host-hop-status.service >/dev/null; sudo -n install -d -m 755 /var/lib/host-hop-status; sudo -n systemctl daemon-reload; sudo -n systemctl enable --now host-hop-status.service' <<EOF
[Unit]
Description=Independent host-hop read-only recovery status
After=network-online.target tailscaled.service
Wants=network-online.target
[Service]
ExecStart=/usr/bin/python3 -I /opt/host-hop-status/server.py $TO_IP $HOP_STATUS_PORT $FROM_IP $HOP_USER
User=nobody
Group=nogroup
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
EOF
on "$TO" 'sudo -n systemctl show host-hop-status.service -p MainPID -p ControlGroup -p ActiveState; /usr/local/bin/host-hop-recovery probe; sha256sum /opt/host-hop-status/server.py'
curl --fail --max-time 10 "http://$TO_IP:$HOP_STATUS_PORT/status.json"
