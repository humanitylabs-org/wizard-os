#!/bin/bash
# REHEARSAL-ONLY (wizard-os 389 run 4): owner-private test pin for wizard-files so the Store window can Get, then Update.
# Pin $1 = commit. The WAM listener runs the stock CLI via wamp.py (public-repo fetch without a GitHub login).
set -e
export XDG_RUNTIME_DIR=/run/user/0
echo "{\"schema\": 1, \"scope\": \"private-test\", \"apps\": [{\"id\": \"wizard-files\", \"repo\": \"humanitylabs-org/wizard-files\", \"commit\": \"$1\"}]}" > /root/wf-catalog.json
D=/root/.config/systemd/user
printf '[Service]\nEnvironment=WAM_PRIVATE_CATALOG=/root/wf-catalog.json\nExecStart=\nExecStart=/usr/bin/python3 /root/wamp.py serve\n' > $D/wizard-app-manager-api.service.d/bt389-testpin.conf
printf '[Service]\nEnvironment=WAM_PRIVATE_CATALOG=/root/wf-catalog.json\n' > $D/wizard-store-data.service.d/bt389-testpin.conf
systemctl --user daemon-reload
systemctl --user try-restart wizard-app-manager-api.service wizard-store-data.service
sleep 4; systemctl --user is-active wizard-app-manager-api.service wizard-store-data.service
cat /proc/$(systemctl --user show -p MainPID --value wizard-app-manager-api.service)/environ | tr '\0' '\n' | grep PRIVATE
