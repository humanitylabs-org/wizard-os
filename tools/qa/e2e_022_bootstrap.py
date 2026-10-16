#!/usr/bin/env python3
"""Capture the unmodified release installer on a dedicated disposable Lima VM.

Run on the assigned build host, under its shared heavy-job lock. --root holds
all VM disks and private raw evidence. No host home is mounted into the guest.
A successful harness exit means installation succeeded, not full E2E acceptance.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--installer-sha', required=True)
    parser.add_argument('--vm', default='fresh-022')
    args = parser.parse_args()
    if len(args.installer_sha) != 40 or any(c not in '0123456789abcdef' for c in args.installer_sha):
        parser.error('installer SHA must be 40 lowercase hex characters')
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    env = os.environ.copy()
    env['PATH'] = '/opt/homebrew/bin:' + env.get('PATH', '')
    env['LIMA_HOME'] = str(root / 'lima')
    env['LIMA_CACHE_HOME'] = str(root / 'lima-cache')
    evidence = root / 'evidence' / ('baseline-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    evidence.mkdir(parents=True)
    record = {'phase': 'unmodified fresh installer baseline', 'vm': args.vm,
              'release': '0.2.2', 'installer_sha': args.installer_sha,
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'limitations': ['No Tailscale enrollment: WIZARD_PRIVATE_ACCESS=none.',
                              'Bootstrap only; chat, video and navigation acceptance remain pending.',
                              'Raw logs are private; sanitize host paths before publication.'],
              'commands': []}
    def run(label, argv, *, data=None, timeout=1800):
        path = evidence / (label + '.log')
        with path.open('w') as log:
            log.write(json.dumps(argv) + '\n'); log.flush()
            try:
                result = subprocess.run(argv, input=data, text=True, env=env,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                rc = result.returncode
            except subprocess.TimeoutExpired:
                rc = 124
                log.write('\nCOMMAND TIMEOUT\n')
        record['commands'].append({'label': label, 'argv': argv, 'exit_code': rc,
                                   'log': path.name})
        (evidence / 'receipt.json').write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps({'step': label, 'exit_code': rc, 'evidence': str(path)}), flush=True)
        return rc
    created = False
    rc = 1
    try:
        if (root / 'lima' / args.vm).exists():
            raise RuntimeError('Refusing to reuse an existing guest: baseline requires a fresh disk')
        rc = run('create', ['limactl', 'create', '--tty=false', '--name=' + args.vm,
                           '--cpus=4', '--memory=4', '--disk=40', '--vm-type=vz', '--rosetta',
                           '--mount-none', '--containerd=none',
                           '--set=.portForwards = [{"guestIP":"0.0.0.0","guestPortRange":[1,65535],"ignore":true}]',
                           'template://ubuntu-24.04'], timeout=1200)
        if rc:
            return rc
        created = True
        rc = run('start', ['limactl', 'start', '--tty=false', args.vm], timeout=1200)
        if rc:
            return rc
        script = '''set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
printf 'OS baseline\n'
uname -a
cat /etc/os-release
printf 'Pre-existing application directories\n'
for p in "$HOME/.hermes" "$HOME/runtipi" /home/wizard/.hermes /home/wizard/runtipi; do
  test ! -e "$p" || { printf 'Unexpected existing state: %s\n' "$p"; exit 20; }
done
mkdir -p "$HOME/evidence"
curl -fsSL https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/INSTALLER/get.sh -o "$HOME/evidence/get.sh"
sha256sum "$HOME/evidence/get.sh"
set +e
sudo env WIZARD_RELEASE=0.2.2 WIZARD_STRICT=1 WIZARD_PRIVATE_ACCESS=none bash "$HOME/evidence/get.sh" </dev/null
rc=$?
set -e
printf '\nINSTALL_EXIT_CODE=%s\n' "$rc"
printf '\nSafe release and outcome readback\n'
for f in /home/wizard/.wizard-os/release.json /home/wizard/.wizard-os/install-outcome.json; do
  if sudo test -f "$f"; then sudo cat "$f"; fi
done
printf '\nContainer image readback\n'
sudo docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' || true
printf '\nInstalled checkout\n'
sudo git -C /home/wizard/wizard-app-manager rev-parse HEAD || true
exit "$rc"
'''.replace('INSTALLER', args.installer_sha)
        (evidence / 'guest-command.sh').write_text(script)
        rc = run('install', ['limactl', 'shell', '--workdir=/', args.vm, '--', 'bash', '-s'], data=script, timeout=5400)
        record['install_exit_code'] = rc
        # Capture only explicitly named non-secret records, never app.env/config.
        for name in ('release.json', 'install-outcome.json'):
            run('readback-' + name, ['limactl', 'shell', '--workdir=/', args.vm, '--',
                                  'sudo', 'cat', '/home/wizard/.wizard-os/' + name], timeout=30)
        return rc
    except Exception as exc:
        record['error'] = str(exc)
        raise
    finally:
        if created:
            run('stop', ['limactl', 'stop', args.vm], timeout=180)
        record['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record['baseline_exit_code'] = rc
        record['acceptance'] = 'pending'
        (evidence / 'receipt.json').write_text(json.dumps(record, indent=2) + '\n')
        print('RECEIPT=' + str(evidence / 'receipt.json'), flush=True)


if __name__ == '__main__':
    sys.exit(main())
