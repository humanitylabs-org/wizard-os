#!/bin/bash
# TEST-ONLY: install the Serve stand-in on the rehearsal guest.
set -e
cd /root/standin
[ -f cert.pem ] || openssl req -x509 -newkey rsa:2048 -nodes -days 30 -keyout key.pem -out cert.pem -subj /CN=wtrain.train.test \
  -addext "subjectAltName=DNS:wtrain.train.test,IP:100.73.0.1" 2>/dev/null
chmod 644 key.pem cert.pem
W=/usr/local/bin/tailscale
grep -q serve_cli.py $W || python3 -c 'import sys;p=sys.argv[1];s=open(p).read();l="[ \"$1\" = serve ] && exec python3 /root/standin/serve_cli.py \"$@\"\n";open(p,"w").write(s.replace("REAL=/usr/bin/tailscale\n","REAL=/usr/bin/tailscale\n"+l,1))' $W
docker rm -f serve-standin >/dev/null 2>&1 || true
docker run -d --name serve-standin --restart unless-stopped --network host -v /root/standin:/s \
  -e TS_IP=$(/usr/bin/tailscale ip -4) -e TS_LOGIN=train node:22-alpine node /s/serve.mjs
tail -3 $W
