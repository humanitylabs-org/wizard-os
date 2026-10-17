#!/usr/bin/env python3
"""Run a pushed bootstrap candidate on a NEW isolated guest; never certify 0.2.2."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--candidate-sha', required=True)
    p.add_argument('--vm', default='fresh-022-candidate')
    a = p.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', a.candidate_sha):
        p.error('candidate SHA must be full lowercase hex')
    if not re.fullmatch(r'fresh-022-candidate[a-z0-9-]*', a.vm):
        p.error('dedicated fresh candidate VM name required')
    root = a.root.resolve()
    if not str(root).startswith('/Volumes/ThalesMedia/'):
        p.error('all data must reside on the external build volume')
    env = {**os.environ, 'PATH': '/opt/homebrew/bin:' + os.environ.get('PATH', ''),
           'LIMA_HOME': str(root / 'lima'), 'LIMA_CACHE_HOME': str(root / 'lima-cache')}
    if (root / 'lima' / a.vm).exists():
        p.error('refusing existing guest; preserve previous experiment')
    evidence = root / 'evidence' / ('candidate-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    evidence.mkdir(parents=True, mode=0o700)
    record = {'host': os.uname().nodename, 'candidate_sha': a.candidate_sha,
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'vm': a.vm, 'release_exact': False, 'acceptance': 'pending', 'commands': []}

    def run(label, argv, data=None, timeout=1800):
        with (evidence / (label + '.log')).open('w') as log:
            log.write(json.dumps(argv) + '\n'); log.flush()
            try:
                rc = subprocess.run(argv, input=data, text=True, stdout=log,
                                    stderr=subprocess.STDOUT, env=env, timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                log.write('\nTIMEOUT\n'); rc = 124
        record['commands'].append({'label': label, 'argv': argv, 'exit_code': rc})
        (evidence / 'receipt.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({'step': label, 'exit_code': rc}), flush=True)
        return rc

    created = False
    rc = 1
    try:
        rc = run('create', ['limactl', 'create', '--tty=false', '--name=' + a.vm,
                  '--cpus=4', '--memory=4', '--disk=40', '--vm-type=vz', '--rosetta',
                  '--mount-none', '--containerd=none',
                  '--set=.portForwards = [{"guestIP":"0.0.0.0","guestPortRange":[1,65535],"ignore":true}]',
                  'template://ubuntu-24.04'], timeout=1200)
        if rc: return rc
        created = True
        rc = run('start', ['limactl', 'start', '--tty=false', a.vm], timeout=1200)
        if rc: return rc
        script = '''set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
printf 'OS baseline\\n'
uname -a
cat /etc/os-release
for d in "$HOME/.hermes" "$HOME/runtipi" "$HOME/wizard-app-manager"; do
 test ! -e "$d" || { printf 'Unexpected prior state: %s\\n' "$d"; exit 20; }
done
sudo apt-get update -qq
sudo apt-get install -y -qq git curl python3 python3-yaml
# This is the unchanged candidate helper at the exact published source commit.
git clone -q https://github.com/humanitylabs-org/wizard-app-manager.git "$HOME/wam-candidate"
git -C "$HOME/wam-candidate" checkout --detach CANDIDATE_SHA
export WIZARD_MODE=fresh
python3 "$HOME/wam-candidate/scripts/qa-release-candidate.py" --manifest "$HOME/wam-candidate/releases/0.2.2.json" --evidence "$HOME/candidate-022-evidence"
'''.replace('CANDIDATE_SHA', a.candidate_sha)
        (evidence / 'guest-command.sh').write_text(script)
        rc = run('candidate-install', ['limactl', 'shell', '--workdir=/', a.vm, '--', 'bash', '-s'], script, 6600)
        readback = '''set -u
for f in candidate-022-evidence/candidate-exception.json candidate-022-evidence/candidate-release.json candidate-022-evidence/original-release-readback.json .wizard-os/release.json .wizard-os/install-outcome.json; do
 printf '\\nRECORD %s\\n' "$f"
 test ! -f "$HOME/$f" || cat "$HOME/$f"
done
printf '\\nCONTAINERS\\n'
sudo docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}'
printf '\\nIMAGE DIGESTS\\n'
sudo docker image inspect $(sudo docker image ls -q | sort -u) --format '{{json .RepoDigests}}'
printf '\\nINSTALLED SOURCE\\n'
git -C "$HOME/wizard-app-manager" rev-parse HEAD
printf '\\nPRIVATE MANAGER ERROR LOG\\n'
sudo test ! -f "$HOME/runtipi/logs/error.log" || sudo cat "$HOME/runtipi/logs/error.log"
'''
        run('readback', ['limactl', 'shell', '--workdir=/', a.vm, '--', 'bash', '-s'], readback, 60)
        return rc
    finally:
        if created:
            run('stop', ['limactl', 'stop', a.vm], timeout=180)
        record.update(exit_code=rc, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        (evidence / 'receipt.json').write_text(json.dumps(record, indent=2) + '\n')
        print('RECEIPT=' + str(evidence / 'receipt.json'), flush=True)


if __name__ == '__main__':
    sys.exit(main())
