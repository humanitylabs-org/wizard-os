#!/bin/bash
# wizard-os 389 run 4: fresh guest -> candidate 0.3.103-bt389.7 -> boundary on, for the Store-window repro. Logs in runs8/.
cd "$(dirname "$0")"
K="-i $HOME/.cache/wizard-release-train/rig/guest_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
cp_g() { scp -q $K -P 2273 -r "$@" root@127.0.0.1:/root/; }
set -x
docker rm -f bt389-registry >/dev/null 2>&1
docker run -d --name bt389-registry --network host -v $PWD/registry:/var/lib/registry registry:2 > runs8/00-registry.log 2>&1
sleep 3; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/v2/ >> runs8/00-registry.log
python3 rig.py up fresh8 > runs8/01-up.log 2>&1 || { echo UPFAIL; exit 1; }
cp_g standin enable-boundary-v2.sh checks6.sh store_lifecycle6.sh lc7.sh wamp.py owner-extra.sh socks5.py
./g 'bash /root/standin/install.sh' > runs8/02-standin-pre.log 2>&1
python3 rig.py install fresh8 0.3.103-bt389.7 --candidate > runs8/03-install.log 2>&1
./g 'bash /root/standin/install.sh' > runs8/04-standin-post.log 2>&1
./g 'bash /root/enable-boundary-v2.sh on' > runs8/05-on.log 2>&1
./g 'docker rm -f bt389-socks5 >/dev/null 2>&1; docker run -d --name bt389-socks5 -v /root/socks5.py:/s.py python:3.12-alpine python /s.py; sleep 3; docker inspect -f "{{.NetworkSettings.IPAddress}}" bt389-socks5' > runs8/06-socks5.log 2>&1
IP=$(tail -1 runs8/06-socks5.log)
systemctl --user stop bt389-socks bt389-device-tunnel 2>/dev/null
systemd-run --user --quiet --collect --unit bt389-socks ssh -N $K -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p 2273 -D 127.0.0.1:1081 root@127.0.0.1
systemd-run --user --quiet --collect --unit bt389-device-tunnel ssh -N $K -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -p 2273 -L 127.0.0.1:1082:$IP:1080 root@127.0.0.1
touch runs8/fresh8.done
