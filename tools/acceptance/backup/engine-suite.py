#!/usr/bin/env python3
"""Heavy-worker entry: full managed Mac engine suite in a disposable Linux VM.

Host macOS cannot run the Linux-only installer tests (Apple bash lacks declare -A).
Use only a cloned lane template, never a retained image or owner install. On success
optionally run the existing native/round-trip premerge gate. No worker submission.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time
import uuid

def verify_inputs(root):
    """Check the same immutable harness/source inventories as premerge, without importing its executable."""
    for name in ('harness-manifest.json', 'source-manifest.json'):
        manifest = json.loads((root / name).read_text())
        for row in manifest['files']:
            path = root / row['path']
            content = os.readlink(path).encode() if row.get('symlink') else path.read_bytes()
            if hashlib.sha256(content).hexdigest() != row['sha256']:
                raise RuntimeError('staged source differs: ' + row['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--then-premerge', action='store_true')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not str(root).startswith('/Volumes/ThalesMedia/'):
        raise SystemExit('suite requires isolated external-volume lane')
    verify_inputs(root)
    manifest = json.loads((root / 'source-manifest.json').read_text())
    pin = manifest['pins']['mac-engine']
    run_id = uuid.uuid4().hex[:10]
    name = 'l1-engine-suite-' + run_id
    evidence = root / 'evidence' / ('engine-suite-' + run_id)
    evidence.mkdir(parents=True)
    env = dict(os.environ, RIG_ROOT=str(root), LIMA_HOME=str(root / 'lima'),
               TMPDIR=str(root / 'tmp'), PYTHONDONTWRITEBYTECODE='1',
               PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin')
    receipt = {'mac_engine_sha': pin, 'scope': 'full pytest suite in a disposable Linux clone',
               'guest': name, 'success': False, 'steps': [], 'cleanup': False}
    result = evidence / 'result.json'

    def save():
        result.write_text(json.dumps(receipt, indent=2) + '\n')

    def step(label, argv, *, timeout=3600):
        start = time.monotonic()
        with (evidence / (label + '.log')).open('w') as log:
            process = subprocess.run([str(x) for x in argv], env=env, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=timeout)
        receipt['steps'].append({'name': label, 'exit': process.returncode,
                                 'seconds': round(time.monotonic() - start, 1)})
        save()
        if process.returncode:
            raise RuntimeError(label + ' failed; see ' + str(evidence / (label + '.log')))

    rig = root / 'bin/rig'
    # Only source-manifest-listed bytes; no .git, bytecode, owner state or host venv.
    archive = evidence / 'mac-engine.tar.gz'
    entries = [row for row in manifest['files'] if row['path'].startswith('mac-engine/')]
    if not entries:
        raise RuntimeError('missing managed engine source inventory')
    with tarfile.open(archive, 'w:gz') as out:
        for row in entries:
            out.add(root / row['path'], arcname=Path(row['path']).relative_to('mac-engine'), recursive=False)
    receipt['source_archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
    save()
    guest = '/home/wizard/wam-engine-suite'
    created = False
    try:
        step('clone', [rig, 'clone', 'source-full', name], timeout=600)
        created = True
        step('boot', [rig, 'start', name, '--timeout', '420'], timeout=600)
        step('copy-source', [rig, 'copy-in', name, archive, guest + '/source.tar.gz', '--owner', 'wizard'])
        setup = ('set -eu; cd ' + shlex.quote(guest) + '; mkdir src home tmp; '
                 'tar -xzf source.tar.gz -C src; python3 -m venv venv; '
                 'venv/bin/python -m pip install -e "src[test]" aiohttp')
        step('dependencies', [rig, 'exec', name, '--wizard', '--', setup], timeout=900)
        tests = ('set -eu; cd ' + shlex.quote(guest) + '; '
                 'export HOME="$PWD/home" TMPDIR="$PWD/tmp" HERMES_HOME="$PWD/home/hermes" '
                 'WIZARD_OS_HOME="$PWD/home/wizard-os" RUNTIPI_ROOT="$PWD/home/runtipi" '
                 'PYTHONDONTWRITEBYTECODE=1; cd src; ')
        step('backup-restore-frontdoor', [rig, 'exec', name, '--wizard', '--', tests +
             '../venv/bin/python -m pytest -q tests -k "backup or restore or frontdoor"'], timeout=1800)
        step('full-pytest', [rig, 'exec', name, '--wizard', '--', tests +
             '../venv/bin/python -m pytest -q tests'], timeout=1800)
        # Source identity must still match after running tests.
        verify_inputs(root)
        receipt['success'] = True
    except Exception as error:
        receipt['error'] = str(error)
    finally:
        if created:
            try:
                step('destroy', [rig, 'destroy', name], timeout=300)
                receipt['cleanup'] = True
            except Exception as error:
                receipt['cleanup_error'] = str(error)
                receipt['success'] = False
        save()
    print(json.dumps(receipt, indent=2), flush=True)
    if not receipt['success'] or not receipt['cleanup']:
        return 1
    if args.then_premerge:
        return subprocess.call([sys.executable, str(root / 'rig/premerge.py'), '--root', str(root)], env=env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
