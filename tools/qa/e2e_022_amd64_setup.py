#!/usr/bin/env python3
"""Prepare QEMU and prove one x86_64 guest boot; no release acceptance claim."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request


def verify_amd64(manifest):
    for name, image in manifest['images'].items():
        repo = image['ref'].split('ghcr.io/', 1)[1].split(':', 1)[0]
        with urllib.request.urlopen('https://ghcr.io/token?scope=repository:' + repo + ':pull', timeout=30) as r:
            token = json.load(r)['token']
        def get(path):
            req = urllib.request.Request('https://ghcr.io/v2/' + repo + '/' + path,
                headers={'Authorization': 'Bearer ' + token,
                         'Accept': 'application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.docker.distribution.manifest.v2+json'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        record = get('manifests/' + image['digest'])
        platforms = [m.get('platform', {}) for m in record.get('manifests', [])]
        if not platforms:
            config = get('blobs/' + record['config']['digest'])
            platforms = [{'os': config.get('os'), 'architecture': config.get('architecture')}]
        assert any(p.get('os') == 'linux' and p.get('architecture') == 'amd64' for p in platforms), name
        print(json.dumps({'component': name, 'digest': image['digest'], 'linux_amd64': True}), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    a = ap.parse_args()
    root = a.root.resolve()
    if not str(root).startswith('/Volumes/ThalesMedia/'):
        ap.error('external work volume required')
    if shutil.disk_usage('/').free < 12 * 1024**3 or shutil.disk_usage(root).free < 80 * 1024**3:
        raise RuntimeError('insufficient internal/tool or external/guest reserve')
    manifest = json.loads((Path(__file__).resolve().parents[2] / 'releases/0.2.2.json').read_text())
    verify_amd64(manifest)
    env = {**os.environ, 'PATH': '/opt/homebrew/bin:' + os.environ.get('PATH', ''),
           'LIMA_HOME': str(root / 'lima'), 'LIMA_CACHE_HOME': str(root / 'lima-cache'),
           'HOMEBREW_CACHE': str(root / 'brew-cache'), 'HOMEBREW_TEMP': str(root / 'brew-tmp'),
           'TMPDIR': str(root / 'tmp'), 'HOMEBREW_LOGS': str(root / 'brew-logs'),
           'HOMEBREW_NO_AUTO_UPDATE': '1', 'HOMEBREW_NO_INSTALL_CLEANUP': '1',
           'HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK': '1', 'HOMEBREW_NO_INSTALL_UPGRADE': '1'}
    for key in ('HOMEBREW_CACHE', 'HOMEBREW_TEMP', 'TMPDIR', 'HOMEBREW_LOGS'):
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    def run(args, timeout=1200):
        print('COMMAND ' + json.dumps(args), flush=True)
        subprocess.run(args, env=env, check=True, timeout=timeout)
    for formula in ('qemu', 'lima-additional-guestagents'):
        check = subprocess.run(['brew', 'list', '--versions', formula], env=env, capture_output=True)
        if check.returncode:
            run(['brew', 'install', formula], 1800)
    run(['qemu-system-x86_64', '--version'], 30)
    vm = 'e2e-022-amd64-smoke'
    if (root / 'lima' / vm).exists():
        raise RuntimeError('refusing to reuse existing smoke guest')
    rules='.portForwards = [{"guestIP":"127.0.0.1","guestPortRange":[1,65535],"ignore":true},{"guestIP":"0.0.0.0","guestPortRange":[1,65535],"ignore":true}]'
    run(['limactl', 'create', '--tty=false', '--name=' + vm, '--arch=x86_64', '--vm-type=qemu',
         '--cpus=2', '--memory=2', '--disk=10', '--mount-none', '--containerd=none',
         '--set=' + rules, 'template://ubuntu-24.04'])
    try:
        run(['limactl', 'start', '--tty=false', vm], 1200)
        run(['limactl', 'shell', '--workdir=/', vm, '--', 'bash', '-lc',
             'set -e; test "$(uname -m)" = x86_64; uname -a; cat /etc/os-release; printf "AMD64_SMOKE_PASS\\n"'], 120)
    finally:
        run(['limactl', 'stop', vm], 180)
    print('AMD64_SETUP_COMPLETE; acceptance remains pending', flush=True)


if __name__ == '__main__':
    main()
