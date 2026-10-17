#!/usr/bin/env python3
"""Replay NON-AI UI/discovery QA on the two retained AMD64 0.2.2 guests.

SOURCE-ONLY preparation is separate from execution. The acceptance owner must
admit this command through the Thales heavy queue. No queue submission here.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import socket
import subprocess
import sys
import time

GUESTS = ('fresh-022-candidate-amd64', 'alongside-022-amd64')
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')
    path.chmod(0o600)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def terminate(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def execute(argv, env, timeout=180, data=None):
    p = subprocess.Popen([str(a) for a in argv], env=env, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = p.communicate(data, timeout=timeout)
        return p.returncode, out, err
    finally:
        terminate(p)


def parse_lima(raw):
    # Lima versions emit either a JSON array or newline-delimited JSON objects.
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        return [json.loads(line) for line in raw.splitlines() if line.strip()]


def validate_target(root, vms):
    require(platform.system() == 'Darwin', 'execution is Thales/macOS-only; do not execute on control plane')
    require(root.is_relative_to(Path('/Volumes/ThalesMedia')) and root.name == 'e2e-022',
            'only the dedicated e2e-022 root on ThalesMedia is allowed')
    require(set(vms) <= set(GUESTS) and len(vms) == len(set(vms)), 'only the two named retained guests are allowed')
    for vm in vms:
        require((root / 'lima' / vm / 'lima.yaml').is_file(), 'existing dedicated Lima guest missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--playwright-module', type=Path, required=True, help='existing absolute Playwright package directory; no npm install')
    parser.add_argument('--node', type=Path, default=Path('/opt/homebrew/bin/node'))
    parser.add_argument('--vm', action='append', choices=GUESTS, help='default: BOTH retained guests, sequentially')
    args = parser.parse_args()
    root = args.root.resolve()
    vms = args.vm or list(GUESTS)
    validate_target(root, vms)
    require(args.node.is_file() and (args.playwright_module / 'package.json').is_file(), 'existing Node/Playwright required')
    env = {**os.environ, 'PATH': '/opt/homebrew/bin:' + os.environ.get('PATH', ''),
           'LIMA_HOME': str(root / 'lima'), 'LIMA_CACHE_HOME': str(root / 'lima-cache'),
           'TMPDIR': str(root / 'scratch')}
    os.umask(0o077)
    (root / 'scratch').mkdir(exist_ok=True)
    lock = (root / 'ui-proof.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    run_id = 'ui-proof-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence = root / 'evidence' / run_id
    evidence.mkdir(parents=True, exist_ok=False)
    rc, revision, _ = execute(['git', '-C', HERE, 'rev-parse', 'HEAD'], env)
    require(rc == 0, 'source revision unavailable; run from pushed checkout')
    rc, dirty, _ = execute(['git', '-C', HERE, 'status', '--porcelain', '--untracked-files=no'], env)
    require(rc == 0 and not dirty.strip(), 'tracked source must be clean')
    sources = [HERE / n for n in ('e2e_022_ui_proof.py', 'e2e_022_ui_guest.py', 'e2e_022_ui_browser.cjs')]
    receipt = {'host': platform.node(), 'source_revision': revision.strip(),
               'source_hashes': {p.name: sha(p) for p in sources}, 'command': sys.argv,
               'scope': 'NON-AI only; existing candidate guests; not exact release certification',
               'ai_acceptance': 'blocked: packaged owner sign-in/Connect/Test not completed',
               'provider_credentials': 'never read/copied/provisioned', 'guests': []}
    receipt_file = evidence / 'receipt.json'
    save(receipt_file, receipt)
    old_handlers = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt('termination requested')
    for sig in (signal.SIGTERM, signal.SIGINT):
        old_handlers[sig] = signal.signal(sig, interrupted)
    try:
        # Validate BOTH before altering either. Never stop a guest somebody else owns.
        rc, raw, _ = execute(['limactl', 'list', '--json'], env, timeout=60)
        require(rc == 0, 'Lima inventory failed')
        inventory = {r['name']: r for r in parse_lima(raw)}
        require(all(inventory.get(vm, {}).get('status') == 'Stopped' for vm in vms),
                'both selected guests must already be stopped')
        for vm in vms:
            dest = evidence / vm
            dest.mkdir()
            item = {'vm': vm, 'commands': [], 'status': 'fail', 'cleanup': {}}
            receipt['guests'].append(item)
            tunnel = None
            started = False
            def command(label, argv, timeout=180, data=None):
                try:
                    rc, out, err = execute(argv, env, timeout=timeout, data=data)
                except subprocess.TimeoutExpired:
                    rc, out = 124, ''
                except OSError:
                    rc, out = 125, ''
                # Intentionally discard stderr and raw child output, except the guest's
                # allowlisted JSON result and show-ssh's private config (not auth material).
                item['commands'].append({'stage': label, 'argv': [str(a) for a in argv],
                                         'exit_code': rc, 'status': 'pass' if rc == 0 else 'fail'})
                save(receipt_file, receipt)
                return rc, out
            try:
                rules = '.portForwards = [{"guestIP":"127.0.0.1","guestPortRange":[1,65535],"ignore":true},{"guestIP":"0.0.0.0","guestPortRange":[1,65535],"ignore":true}]'
                rc, _ = command('disable-host-port-forwarding', ['limactl', 'edit', '--tty=false', '--set=' + rules, vm], 60)
                require(rc == 0, 'could not enforce loopback and wildcard forwarding ignores')
                item['lima_config_sha256'] = sha(root / 'lima' / vm / 'lima.yaml')
                started = True  # even a partially failed start must be stopped in finally
                rc, _ = command('start', ['limactl', 'start', '--tty=false', vm], 300)
                require(rc == 0, 'guest failed to start')
                rc, raw = command('guest-non-ai-workflow', ['limactl', 'shell', '--workdir=/', vm, '--',
                                  'python3', '-', run_id], 3000, (HERE / 'e2e_022_ui_guest.py').read_text())
                guest = json.loads(raw)
                save(dest / 'guest-receipt.json', guest)
                item['guest_status'] = guest.get('status', 'fail')
                target = guest.get('browser_target')
                require(target, 'guest did not discover the installed shell endpoint')
                port = target['guest_port']
                require(isinstance(port, int) and 1 <= port <= 65535, 'invalid guest shell port')
                require(re.fullmatch(r'/[A-Za-z0-9_./-]*', target['path']) is not None, 'invalid shell path')
                # Current Lima supports this directly; no parsing of human show-ssh output.
                rc, config = command('guest-ssh-config', ['limactl', 'show-ssh', '--format=config', vm], 60)
                require(rc == 0, 'guest ssh config unavailable')
                cfg = dest / 'ssh.config'
                cfg.write_text(config)
                cfg.chmod(0o600)
                host = next((l.split()[1] for l in config.splitlines() if re.match(r'^\s*Host\s+', l)), None)
                require(host and re.fullmatch(r'[A-Za-z0-9_.-]+', host), 'ambiguous guest SSH alias')
                with socket.socket() as s:
                    s.bind(('127.0.0.1', 0))
                    local_port = s.getsockname()[1]
                argv = ['ssh', '-F', str(cfg), '-N', '-T', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
                        '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
                        '-L', f'127.0.0.1:{local_port}:127.0.0.1:{port}', host]
                tunnel = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL, start_new_session=True)
                deadline = time.monotonic() + 30
                connected = False
                while time.monotonic() < deadline and tunnel.poll() is None:
                    try:
                        with socket.create_connection(('127.0.0.1', local_port), timeout=1):
                            connected = True
                            break
                    except OSError:
                        time.sleep(0.2)
                require(connected, 'process-owned SSH tunnel failed')
                item['tunnel'] = {'argv': argv, 'pid': tunnel.pid, 'bind': '127.0.0.1'}
                rc, _ = command('installed-browser-qa', [args.node, HERE / 'e2e_022_ui_browser.cjs',
                                 args.playwright_module.resolve(), f'http://127.0.0.1:{local_port}',
                                 target['path'], dest, run_id], 900)
                bp = dest / 'browser-receipt.json'
                browser = json.loads(bp.read_text()) if bp.exists() else {'status': 'fail'}
                item['browser_status'] = browser['status']
                item['status'] = 'pass' if item['guest_status'] == 'pass' and rc == 0 and browser['status'] == 'pass' else 'incomplete'
            except Exception as error:
                # Do not serialize subprocess outputs/exceptions: they can contain secrets.
                item['error_class'] = type(error).__name__
                if type(error) is RuntimeError:
                    item['reason'] = str(error)
            finally:
                # Cleanup even after timeout/failure/SIGTERM; never detached tunnels/guests.
                terminate(tunnel)
                item['cleanup']['tunnel_stopped'] = tunnel is None or tunnel.poll() is not None
                if started:
                    stop_rc, _ = command('stop', ['limactl', 'stop', vm], 180)
                    item['cleanup']['stop_exit_code'] = stop_rc
                    if stop_rc:
                        forced_rc, _ = command('force-stop-owned-guest', ['limactl', 'stop', '--force', vm], 120)
                        item['cleanup']['force_stop_exit_code'] = forced_rc
                rc, raw = command('verify-stopped', ['limactl', 'list', '--json'], 60)
                states = {r['name']: r.get('status') for r in parse_lima(raw)} if rc == 0 else {}
                item['cleanup']['guest_stopped'] = states.get(vm) == 'Stopped'
                if not item['cleanup']['guest_stopped']:
                    item['status'] = 'fail'
                save(receipt_file, receipt)
            # Refuse to start a second guest if cleanup of the first failed.
            require(item['cleanup']['guest_stopped'], 'guest stop failed; operator intervention needed')
    finally:
        receipt['status'] = 'pass' if len(receipt['guests']) == len(vms) and all(r['status'] == 'pass' for r in receipt['guests']) else 'incomplete'
        receipt['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        receipt['evidence_hashes'] = {str(p.relative_to(evidence)): sha(p) for p in evidence.rglob('*')
                                      if p.is_file() and p != receipt_file and p.name != 'ssh.config'}
        save(receipt_file, receipt)
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        lock.close()
        print('RECEIPT=' + str(receipt_file), flush=True)
    return 0 if receipt['status'] == 'pass' else 2


if __name__ == '__main__':
    sys.exit(main())
