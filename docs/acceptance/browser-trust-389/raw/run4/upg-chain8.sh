#!/bin/bash
# wizard-os 389 run 4: upgraded guest 0.3.102 -> candidate 0.3.103-bt389.7 -> boundary on, for the Store-window repro. Logs in runs8/.
cd "$(dirname "$0")"
K="-i $HOME/.cache/wizard-release-train/rig/guest_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
cp_g() { scp -q $K -P 2273 -r "$@" root@127.0.0.1:/root/; }
set -x
systemctl --user stop bt389-socks bt389-device-tunnel 2>/dev/null
python3 rig.py down fresh8 > runs8/20-down-fresh8.log 2>&1
rm -f runs/fresh8/guest.qcow2
python3 rig.py up upg8 > runs8/21-up-upg8.log 2>&1 || { echo UPFAIL; exit 1; }
cp_g standin enable-boundary-v2.sh checks6.sh store_lifecycle6.sh lc7.sh wamp.py owner-extra.sh socks5.py testpin.sh
./g 'bash /root/standin/install.sh' > runs8/22-standin-pre.log 2>&1
python3 rig.py install upg8 0.3.102 > runs8/23-install-0.3.102.log 2>&1
./g 'bash /root/standin/install.sh' > runs8/24-standin-post.log 2>&1
python3 rig.py install upg8 0.3.103-bt389.7 --candidate > runs8/25-upgrade-cand7.log 2>&1
./g 'bash /root/standin/install.sh' > runs8/26-standin-post2.log 2>&1
./g 'bash /root/enable-boundary-v2.sh on' > runs8/27-on.log 2>&1
./g 'docker rm -f bt389-socks5 >/dev/null 2>&1; docker run -d --name bt389-socks5 -v /root/socks5.py:/s.py python:3.12-alpine python /s.py; sleep 3; docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" bt389-socks5' > runs8/28-socks5.log 2>&1
IP=$(tail -1 runs8/28-socks5.log)
systemd-run --user --quiet --collect --unit bt389-socks ssh -N $K -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p 2273 -D 127.0.0.1:1081 root@127.0.0.1
systemd-run --user --quiet --collect --unit bt389-device-tunnel ssh -N $K -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p 2273 -L 127.0.0.1:1082:$IP:1080 root@127.0.0.1
touch runs8/upg8.done
