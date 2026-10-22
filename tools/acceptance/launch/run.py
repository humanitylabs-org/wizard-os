#!/usr/bin/env python3
"""Durable-worker entry. Isolated VMs, fail-closed receipts; never uses an owner's box."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def command(argv, log, timeout=1800):
    with log.open('a') as out:
        p = subprocess.run(argv, stdout=out, stderr=subprocess.STDOUT, timeout=timeout)
    if p.returncode:
        raise RuntimeError('step_failed')


def receipt(root, value):
    ledger = root / 'receipts.jsonl'
    lines = ledger.read_text().splitlines() if ledger.exists() else []
    prior = json.loads(lines[-1]) if lines else None
    value['previous_sha256'] = prior['sha256'] if prior else None
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'))
    value['sha256'] = hashlib.sha256(payload.encode()).hexdigest()
    with ledger.open('a') as out:
        out.write(json.dumps(value, sort_keys=True) + '\n')
    return value


def gate(rows):
    """Four consecutive UTC daily receipts across >=72h, unchanged shipped candidate."""
    window = []
    previous = None
    for row in rows:
        if row.get('passed') is not True or row.get('interventions', 0) or row.get('overlays'):
            window = []
            previous = None
            continue
        when = dt.datetime.fromisoformat(row['at'].replace('Z', '+00:00'))
        if previous:
            before = dt.datetime.fromisoformat(previous['at'].replace('Z', '+00:00'))
            if row['release'] != previous['release'] or (when.date() - before.date()).days != 1:
                window = []
        window.append(row)
        previous = row
    return len(window) >= 4 and (dt.datetime.fromisoformat(window[-1]['at'].replace('Z', '+00:00')) -
                                dt.datetime.fromisoformat(window[0]['at'].replace('Z', '+00:00'))).total_seconds() >= 72 * 3600


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--release', required=True)
    p.add_argument('--previous-release', default='0.3.32')
    p.add_argument('--cli', required=True, type=Path)
    args = p.parse_args()
    root = args.root.resolve()
    work_value = os.environ.get('WIZARD_WORK_ROOT')
    if not work_value:
        p.error('WIZARD_WORK_ROOT must name the mounted work volume')
    work = Path(work_value).resolve()
    if not work.is_mount() or not root.is_relative_to(work) or root == work or not args.cli.is_file():
        p.error('root must be below the mounted work volume; staged CLI required')
    import re
    if not all(re.fullmatch(r'\d+\.\d+\.\d+', v) for v in (args.release, args.previous_release)):
        p.error('numeric released versions required')
    os.environ['LIMA_HOME'] = str(root / 'lima')
    os.environ['LIMA_CACHE_HOME'] = str(root / 'cache')
    os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
    root.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run = root / 'runs' / run_id
    run.mkdir(parents=True)
    retained = 'launch-real-use'
    clean = 'launch-clean-' + run_id.lower()
    result = {'fixture': 'launch-audits-8-9', 'at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'release': args.release, 'architecture': 'aarch64', 'passed': False, 'interventions': 0,
              'overlays': [], 'cases': [], 'step': 'start'}
    log = run / 'private-run.log'
    def shell(name, argv, timeout=1800):
        command(['limactl', 'shell', '--workdir', '/', name, '--'] + argv, log, timeout)
    def create(name):
        config = {'vmType': 'vz', 'arch': 'aarch64', 'cpus': 4, 'memory': '6GiB', 'disk': '50GiB',
                  'images': [{'location': 'https://cloud-images.ubuntu.com/releases/noble/release-20261017/ubuntu-24.04-server-cloudimg-arm64.img',
                              'arch': 'aarch64', 'digest': 'sha256:50e24e1fb79e89116e939d90aa7738f7af48c442fa1bc2510131e0b39c50348e'}],
                  'mounts': [{'location': str(root), 'writable': True}],
                  'containerd': {'system': False, 'user': False},
                  'portForwards': [{'guestPortRange': [1, 65535], 'ignore': True}],
                  'provision': [{'mode': 'system', 'script': '#!/bin/sh\nset -eu\napt-get update\napt-get install -y curl git python3\n'}]}
        config_path = run / (name + '.json')
        config_path.write_text(json.dumps(config))
        command(['limactl', 'create', '--name', name, '--tty=false', str(config_path)], log)
        command(['limactl', 'start', '--tty=false', name], log)
    def install(name, state, release):
        shell(name, ['env', 'WIZARD_LAUNCH_FIXTURE=launch-audits-8-9', 'AUDIT_STATE=' + str(state),
                     'AUDIT_RELEASE=' + release, 'bash', str(HERE / 'bootstrap.sh')], 5400)
    def journey(name, case, state):
        contact_evidence = run / ('first-contact-' + name)
        command(['python3', str(HERE / 'tunnel.py'), name, str(args.cli), str(contact_evidence)], log, 120)
        output = run / (case + '.json')
        # Wrapper creates a machine-only result file, while stderr stays in the private log.
        shell(name, ['env', 'WIZARD_LAUNCH_FIXTURE=launch-audits-8-9', 'python3', str(HERE / 'capture.py'),
                     str(output), str(HERE / 'journey.py'), '--state', str(state), '--case', case, '--cli', str(args.cli)])
        result['cases'].append(json.loads(output.read_text()))
    try:
        result['step'] = 'clean-create'
        create(clean)
        result['step'] = 'clean-public-install'
        install(clean, run / 'clean-install', args.previous_release)
        result['step'] = 'clean-previous-journey'
        journey(clean, 'clean', run / 'clean-state.json')
        result['step'] = 'clean-upgrade'
        install(clean, run / 'clean-upgrade', args.release)
        journey(clean, 'clean', run / 'clean-state.json')
        instance = root / 'lima' / retained
        state = root / 'persistent-state.json'
        if not instance.exists():
            result['step'] = 'retained-create'
            create(retained)
            install(retained, run / 'retained-install', args.release)
        else:
            result['step'] = 'retained-start'
            command(['limactl', 'start', '--tty=false', retained], log)
            # No silent repair or daily candidate change. Upgrade must be an explicit reset.
        result['step'] = 'retained-intervention-check'
        cursor = root / 'intervention-cursor.txt'
        since = cursor.read_text().strip() if cursor.exists() else result['at']
        check = run / 'interventions.json'
        shell(retained, ['python3', str(HERE / 'capture.py'), str(check), str(HERE / 'interventions.py'), '--since', since])
        result['interventions'] = json.loads(check.read_text())['interactive_logins']
        cursor.write_text(result['at'])
        if result['interventions']:
            raise RuntimeError('operator_intervention')
        result['step'] = 'retained-journey'
        journey(retained, 'retained', state)
        assert result['cases'][-1]['release'] == args.release, 'retained candidate changed'
        result['step'] = 'retained-reboot'
        command(['limactl', 'stop', retained], log)
        command(['limactl', 'start', '--tty=false', retained], log)
        journey(retained, 'retained', state)
        result['step'] = 'complete'
        result['passed'] = True
    except (Exception, KeyboardInterrupt):
        # Step names are enums owned by this file. No exception text crosses the publication boundary.
        result['passed'] = False
    finally:
        if (root / 'lima' / clean).exists():
            try:
                command(['limactl', 'stop', '-f', clean], log)
                command(['limactl', 'delete', '-f', clean], log)
            except Exception:
                result['passed'] = False
                result['cleanup_failed'] = True
        result = receipt(root, result)
        (run / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
        rows = [json.loads(line) for line in (root / 'receipts.jsonl').read_text().splitlines()]
        result['soak_72h_passed'] = gate(rows)
        print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
