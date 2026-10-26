#!/usr/bin/env python3
"""One-off release acceptance using the launch harness, no retained/daily VM.

Single bounded disposable VM at a time; fresh install and real update, then
optional installed-WAM backup/restore/Undo. Must run on the admitted work mount.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import run as launch

HERE = Path(__file__).resolve().parent
GIB = 1 << 30
# Public launch defaults plus a real ~1 GiB backup, staging, and Undo copies.
# 17 GiB leaves ~1 GiB free: WAM correctly refuses its ~2.5 GiB export budget.
GUEST_DISK_GIB = 24


def capture_failure_diagnostics(vm, log):
    """Read the guest before cleanup; best effort must never hide the real failure."""
    try:
        with log.open('a') as out:
            subprocess.run(['limactl', 'shell', '--workdir', '/', vm, '--', 'env',
                            'WIZARD_LAUNCH_FIXTURE=launch-audits-8-9', 'python3',
                            str(HERE / 'diagnostics.py')], stdout=out, stderr=subprocess.STDOUT,
                           timeout=150, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--release', required=True)
    p.add_argument('--previous-release', required=True)
    p.add_argument('--cli', required=True, type=Path)
    p.add_argument('--wam-commit', required=True)
    p.add_argument('--fixture', type=Path)
    p.add_argument('--fixture-sha256')
    p.add_argument('--check-only', action='store_true')
    a = p.parse_args()
    work = Path(os.environ['WIZARD_WORK_ROOT']).resolve()
    root = a.root.resolve()
    assert work.is_mount() and root.is_relative_to(work) and root != work
    assert not root.exists(), 'use a fresh isolated acceptance root'
    assert a.cli.is_file()
    assert not sys.flags.optimize, 'assertions may not be optimized away'
    if a.fixture:
        assert hashlib.sha256(a.fixture.read_bytes()).hexdigest() == a.fixture_sha256
    assert shutil.disk_usage(work).free >= (250 + GUEST_DISK_GIB + 1) * GIB, '250 GiB reserve plus guest and metadata required'
    os.environ.update(PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
                      LIMA_HOME=str(root / 'lima'), LIMA_CACHE_HOME=str(root / 'cache'))
    vm = 'release-check'
    assert len(str(root / 'lima' / vm / 'ssh.sock.1234567890123456')) < 104
    if a.check_only:
        print(json.dumps({'preflight': True, 'executed': False, 'release': a.release,
                          'previous_release': a.previous_release, 'backup': bool(a.fixture)}))
        return 0
    root.mkdir(parents=True)
    evidence = root / 'evidence'
    evidence.mkdir()
    log = evidence / 'private-run.log'
    result = {'passed': False, 'release': a.release, 'from': a.previous_release,
              'cases': [], 'step': 'start', 'overlays': [], 'architecture': 'aarch64',
              'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'disk_gib': GUEST_DISK_GIB, 'reserve_gib': 250}
    stop = threading.Event()
    low_space = threading.Event()
    def command(argv, timeout=1800):
        assert not low_space.is_set() and shutil.disk_usage(work).free >= 250 * GIB
        launch.command(list(map(str, argv)), log, timeout)
        assert not low_space.is_set()
    def shell(argv, timeout=1800):
        command(['limactl', 'shell', '--workdir', '/', vm, '--', *argv], timeout)
    def create(name):
        config = {'vmType': 'vz', 'arch': 'aarch64', 'cpus': 4, 'memory': '6GiB', 'disk': f'{GUEST_DISK_GIB}GiB',
                  'images': [{'location': 'https://cloud-images.ubuntu.com/releases/noble/release-20261017/ubuntu-24.04-server-cloudimg-arm64.img',
                              'arch': 'aarch64', 'digest': 'sha256:50e24e1fb79e89116e939d90aa7738f7af48c442fa1bc2510131e0b39c50348e'}],
                  'mounts': [{'location': str(root), 'writable': True},
                             {'location': str(HERE.parents[3]), 'writable': False}],
                  'containerd': {'system': False, 'user': False},
                  'portForwards': [{'guestPortRange': [1, 65535], 'ignore': True}],
                  'provision': [{'mode': 'system', 'script': '#!/bin/sh\nset -eu\napt-get update\napt-get install -y curl git python3\n'}]}
        config_path = evidence / 'vm.json'
        config_path.write_text(json.dumps(config))
        command(['limactl', 'create', '--name', vm, '--tty=false', config_path])
        command(['limactl', 'start', '--tty=false', vm])
    def install(name, state, release):
        shell(['env', 'WIZARD_LAUNCH_FIXTURE=launch-audits-8-9', 'AUDIT_STATE=' + str(state),
               'AUDIT_RELEASE=' + release, 'bash', str(HERE / 'bootstrap.sh')], 5400)
    def delete(name):
        command(['limactl', 'stop', '-f', vm])
        command(['limactl', 'delete', '-f', vm])
    def journey(name, case, state, expected_release):
        if case != 'upgrade-baseline':
            command(['python3', HERE / 'tunnel.py', vm, a.cli, evidence / ('contact-' + case)], 120)
        output = evidence / (case + '.json')
        shell(['env', 'WIZARD_LAUNCH_FIXTURE=launch-audits-8-9', 'python3', str(HERE / 'capture.py'),
               str(output), str(HERE / 'journey.py'), '--state', str(state), '--case', case, '--cli', str(a.cli)])
        value = json.loads(output.read_text())
        assert value['passed'] is True and value['release'] == expected_release
        result['cases'].append(value)
    def monitor():
        while not stop.wait(2):
            if shutil.disk_usage(work).free < 251 * GIB:
                low_space.set()
                subprocess.run(['limactl', 'stop', '-f', vm], capture_output=True, timeout=120)
                return
    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    try:
        launch.disposable_cases(a, evidence, vm, create, install, journey, delete, result)
        if a.fixture:
            result['step'] = 'backup-roundtrip'
            shell(['sudo', '-n', 'touch', '/var/lib/wizard-backup-disposable'])
            output = evidence / 'backup.json'
            shell(['env', 'WIZARD_LAUNCH_FIXTURE=launch-audits-8-9', 'python3', str(HERE / 'capture.py'),
                   str(output), str(HERE / 'backup_journey.py'), '--fixture', str(a.fixture),
                   '--fixture-sha256', a.fixture_sha256, '--release', a.release,
                   '--wam-commit', a.wam_commit], 7200)
            result['backup'] = json.loads(output.read_text())
            assert result['backup']['passed'] is True
        result.update(step='complete', passed=True)
    except BaseException as exc:
        result['error_kind'] = type(exc).__name__
        result['passed'] = False
    finally:
        stop.set()
        watcher.join(timeout=130)
        if (root / 'lima' / vm).exists():
            if not result['passed']:
                capture_failure_diagnostics(vm, log)
            cleanup = subprocess.run(['limactl', 'delete', '-f', vm], capture_output=True, timeout=180)
            result['cleanup'] = cleanup.returncode == 0 and not (root / 'lima' / vm).exists()
            if not result['cleanup']:
                result['passed'] = False
        result['low_space'] = low_space.is_set()
        if low_space.is_set():
            result['passed'] = False
        result['finished'] = dt.datetime.now(dt.timezone.utc).isoformat()
        (evidence / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
