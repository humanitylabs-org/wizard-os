#!/usr/bin/env python3
"""Bounded, receipt-writing fresh Ubuntu acceptance phase (run under worker lock).

Usage: fresh_launch.py EVIDENCE_ROOT LIMA_HOME VM_NAME [RELEASE]
No home mounts, no host credentials, no model substitution. The VM is retained.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

root, lima, vm = sys.argv[1:4]
release = sys.argv[4] if len(sys.argv) > 4 else '0.3.17'
assert vm.startswith('l4-'), 'refuse non-lane VM'
root = Path(root)
root.mkdir(parents=True, exist_ok=True)
os.environ.update(LIMA_HOME=lima, PATH='/opt/homebrew/bin:/usr/local/bin:' + os.environ['PATH'], TMPDIR='/Volumes/ThalesMedia/tmp')
receipt = {'vm': vm, 'LIMA_HOME': lima, 'release_requested': release, 'started': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'steps': []}

def save():
    (root / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

def run(name, argv, timeout=180, required=True):
    with (root / (name + '.log')).open('w') as log:
        log.write(json.dumps(argv) + '\n'); log.flush()
        try:
            p = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    receipt['steps'].append({'step': name, 'exit': rc, 'log': name + '.log'})
    save()
    print(name, rc, flush=True)
    if required and rc:
        raise RuntimeError(f'{name} failed: {rc}')
    return rc

def guest(name, command, timeout=180, required=True):
    return run(name, ['limactl', 'shell', '--workdir', '/', vm, '--', 'bash', '-lc', command], timeout, required)

try:
    run('host-preflight', ['bash', '-lc', 'df -h / /Volumes/ThalesMedia; vm_stat; sysctl hw.memsize'])
    if Path(lima, vm).exists():
        raise RuntimeError('refuse to overwrite existing VM; inspect receipt before retry')
    config = root / 'vm.yaml'
    config.write_text('''vmType: vz
arch: aarch64
cpus: 4
memory: 6GiB
disk: 40GiB
images:
- location: https://cloud-images.ubuntu.com/releases/noble/release-20260615/ubuntu-24.04-server-cloudimg-arm64.img
  arch: aarch64
  digest: sha256:cafa1a965b591b7c4184b484ffd8e625981a79d48f9b4ae8a4adf7b4c5ade927
mounts: []
containerd:
  system: false
  user: false
portForwards:
- guestPort: 8796
  hostPort: 18796
- guestPortRange: [1, 65535]
  ignore: true
''')
    run('vm-start', ['limactl', 'start', '--tty=false', '--name=' + vm, str(config)], 900)
    guest('fresh-baseline', 'cat /etc/os-release; id; df -h /; free -m; '
          'if command -v hermes; then exit 9; fi; '
          'if sudo test -d /root/.hermes || test -d ~/.hermes || sudo test -d /home/wizard/.hermes; then exit 10; fi; '
          'echo FRESH_NO_HERMES')
    # Preserve the actual public entry bytes, run the public command with only a release selector.
    guest('public-install', 'set -o pipefail; mkdir -p ~/evidence; '
          'curl -fsSL https://aiwizards.com/os.sh -o ~/evidence/public-os.sh; '
          'sha256sum ~/evidence/public-os.sh; '
          f'curl -fsSL https://aiwizards.com/os.sh | sudo env WIZARD_RELEASE={release} WIZARD_TAILSCALE_WAIT=1 bash', 2100, False)
    guest('installed-readback', 'sudo bash -lc '\
          "'for h in /home/* /root; do for f in .wizard-os/release.json .wizard-os/install-outcome.json .wizard-os/install-status.json .wizard-os/apps.json; do "\
          'if test -f "$h/$f"; then printf "\\nFILE %s\\n" "$h/$f"; cat "$h/$f"; fi; done; done; '\
          'docker ps -a --format "{{.Names}} {{.Image}} {{.Status}}"; '\
          'docker ps -q | xargs -r docker inspect --format "{{.Name}} image={{.Config.Image}} imageID={{.Image}}"; '\
          "ss -ltnp'", 180, False)
    guest('doctor', 'sudo -iu wizard bash -lc "export PATH=\\$HOME/.local/bin:\\$PATH; wam doctor"', 240, False)
    run('vm-final', ['limactl', 'list', '--json'], 60, False)
    receipt['state'] = 'initial-phase-complete; browser, update, restart, uninstall acceptance pending'
except Exception:
    receipt['state'] = 'failed'
    receipt['error'] = traceback.format_exc()
finally:
    receipt['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
    print(json.dumps(receipt, indent=2))
if receipt['state'] == 'failed':
    sys.exit(1)
