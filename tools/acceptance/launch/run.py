#!/usr/bin/env python3
"""Durable-worker entry. Isolated VMs, fail-closed receipts; never uses an owner's box."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent

# Outlives tunnel.py's own readiness deadline plus its guest snapshot.
TUNNEL_TIMEOUT_SECONDS = 600


def command(argv, log, timeout=1800):
    cleanup = argv[:3] in (['limactl', 'stop', '-f'], ['limactl', 'delete', '-f'])
    if not cleanup and shutil.disk_usage(Path(os.environ['WIZARD_WORK_ROOT'])).free < 250 * (1 << 30):
        raise RuntimeError('disk_reserve')
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
        if row.get('fixture') == 'launch-onboarding-87-88' or row.get('passed') is not True or row.get('interventions', 0) or row.get('overlays'):
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


def disposable_cases(args, evidence, vm, create, install, journey, delete, result):
    """Prove the candidate from empty disk independently of upgrade continuity."""
    result['step'] = 'clean-create'
    create(vm)
    result['step'] = 'clean-public-install'
    install(vm, evidence / 'clean-install', args.release)
    result['step'] = 'clean-candidate-journey'
    journey(vm, 'clean', evidence / 'clean-state.json', args.release)
    result['step'] = 'clean-delete'
    delete(vm)
    result['step'] = 'upgrade-create'
    create(vm)
    result['step'] = 'upgrade-previous-install'
    install(vm, evidence / 'upgrade-previous-install', args.previous_release)
    result['step'] = 'upgrade-baseline-journey'
    journey(vm, 'upgrade-baseline', evidence / 'upgrade-state.json', args.previous_release)
    result['step'] = 'clean-upgrade'
    install(vm, evidence / 'clean-upgrade', args.release)
    result['step'] = 'upgraded-candidate-journey'
    journey(vm, 'upgraded', evidence / 'upgrade-state.json', args.release)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--release', required=True)
    p.add_argument('--previous-release', default='0.3.32')
    p.add_argument('--cli', required=True, type=Path)
    p.add_argument('--first-chat-secret', type=Path)
    p.add_argument('--secrets-root', type=Path)
    p.add_argument('--oauth-source', type=Path, help='pushed ChatGPT connection source, for host-only OAuth renewal')
    p.add_argument('--phone-config', type=Path, help='private host paths to the published feed/APK and Android tools')
    p.add_argument('--check-only', action='store_true', help='validate host inputs without creating a VM')
    p.add_argument('--onboarding-only', action='store_true', help='fresh install + chat + phone; never touches the retained soak VM')
    args = p.parse_args()
    if args.first_chat_secret and not (args.secrets_root and args.oauth_source):
        p.error('first chat requires --secrets-root and --oauth-source')
    if args.phone_config and not args.first_chat_secret:
        p.error('phone proof requires a real first chat')
    if args.onboarding_only and not (args.first_chat_secret and args.phone_config):
        p.error('onboarding-only requires both chat and phone')
    root = args.root.resolve()
    work_value = os.environ.get('WIZARD_WORK_ROOT')
    if not work_value:
        p.error('WIZARD_WORK_ROOT must name the mounted work volume')
    work = Path(work_value).resolve()
    from release_gate import admitted_work_root, native_vm_config, GUEST_DISK_GIB
    native = native_vm_config()
    disk_gib = 50 if native['vmType'] == 'vz' else GUEST_DISK_GIB
    if not admitted_work_root(work) or not root.is_relative_to(work) or root == work or not args.cli.is_file():
        p.error('root must be below the admitted work root; staged CLI required')
    if sys.flags.optimize:
        p.error('assertions may not be optimized away')
    import re
    if not all(re.fullmatch(r'\d+\.\d+\.\d+', v) for v in (args.release, args.previous_release)):
        p.error('numeric released versions required')
    mounts = [root, HERE.parents[2], args.cli.resolve().parents[1]]
    if args.first_chat_secret:
        from first_chat import private_file, validate_oauth_source
        # Catch a wrapped/mis-staged helper before paying for a public VM install.
        try:
            validate_oauth_source(args.oauth_source)
        except RuntimeError:
            p.error('oauth_source_missing: --oauth-source must contain codex.py directly')
        private_file(args.first_chat_secret, args.secrets_root)
        # Secrets MUST NOT be in any Lima mount (the old daily root also contains
        # its secrets sibling). Source/CLI mounts are read-only; only run state is writable.
        secret = args.first_chat_secret.resolve()
        if any(secret.is_relative_to(m) for m in mounts):
            p.error('secret must be outside all guest mounts; use a separate onboarding --root')
        # Older retained fixtures mount the original acceptance root wholesale.
        # Audit their frozen JSON-form Lima YAML too; never expose a new plaintext
        # directory just because the *new* VM's mount table is narrow enough.
        for config in (args.secrets_root.parent / 'lima').glob('*/lima.yaml'):
            old = json.loads(config.read_text())
            if any(secret.is_relative_to(Path(m['location']).resolve()) for m in old.get('mounts', [])):
                p.error('credential is visible through an existing guest mount')
    # Linux reuses the release gate's guest budget; retain the Mac disk size.
    required_gib = 250 + disk_gib + 1 + (9 if args.phone_config else 0)
    if shutil.disk_usage(work).free < required_gib * (1 << 30):
        p.error(f'250 GiB reserve plus guest/phone/metadata required ({required_gib} GiB)')
    if args.check_only:
        print(json.dumps({'preflight': True, 'executed': False, 'release': args.release,
                          'architecture': native['arch'], 'vm_type': native['vmType']}))
        return 0
    os.umask(0o077)
    os.environ['LIMA_HOME'] = str(root / 'lima')
    os.environ['LIMA_CACHE_HOME'] = str(root / 'cache')
    if native['vmType'] == 'vz':
        os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
    root.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run = root / 'runs' / run_id
    run.mkdir(parents=True)
    retained = 'launch-real-use'
    # Lima's per-instance ssh.sock path must stay under macOS UNIX_PATH_MAX (104).
    clean = 'lc-' + run_id.lower()
    for name in (retained, clean):
        sock = Path(os.environ['LIMA_HOME']) / name / 'ssh.sock.1234567890123456'
        if len(str(sock)) >= 104:
            p.error(f'Lima socket path too long for instance {name!r} ({len(str(sock))} chars); use a shorter --root')
    result = {'fixture': 'launch-audits-8-9', 'at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'release': args.release, 'architecture': native['arch'], 'passed': False, 'interventions': 0,
              'overlays': [], 'cases': [], 'step': 'start'}
    log = run / 'private-run.log'
    def shell(name, argv, timeout=1800):
        command(['limactl', 'shell', '--workdir', '/', name, '--'] + argv, log, timeout)
    def create(name):
        config = {**native, 'cpus': 4, 'memory': '6GiB', 'disk': f'{disk_gib}GiB',
                  'mounts': [{'location': str(m), 'writable': m == root} for m in dict.fromkeys(mounts)],
                  'containerd': {'system': False, 'user': False},
                  'portForwards': [{'guestIP': ip, 'guestPortRange': [1, 65535], 'ignore': True}
                                   for ip in ('127.0.0.1', '0.0.0.0')],
                  'provision': [{'mode': 'system', 'script': '#!/bin/sh\nset -eu\napt-get update\napt-get install -y curl git python3\n'}]}
        config_path = run / (name + '.json')
        config_path.write_text(json.dumps(config))
        command(['limactl', 'create', '--name', name, '--tty=false', str(config_path)], log)
        command(['limactl', 'start', '--tty=false', name], log)
    def install(name, state, release):
        shell(name, ['env', 'WIZARD_LAUNCH_FIXTURE=launch-audits-8-9', 'AUDIT_STATE=' + str(state),
                     'AUDIT_RELEASE=' + release, 'bash', str(HERE / 'bootstrap.sh')], 5400)
    def delete(name):
        command(['limactl', 'stop', '-f', name], log)
        command(['limactl', 'delete', '-f', name], log)
    def journey(name, case, state, expected_release):
        if case != 'upgrade-baseline':
            contact_evidence = run / f'first-contact-{name}-{case}-{len(result["cases"])}'
            command(['python3', str(HERE / 'tunnel.py'), name, str(args.cli), str(contact_evidence)], log, TUNNEL_TIMEOUT_SECONDS)
        output = run / f'{case}-{len(result["cases"])}.json'
        # Wrapper creates a machine-only result file, while stderr stays in the private log.
        shell(name, ['env', 'WIZARD_LAUNCH_FIXTURE=launch-audits-8-9', 'python3', str(HERE / 'capture.py'),
                     str(output), str(HERE / 'journey.py'), '--state', str(state), '--case', case, '--cli', str(args.cli)])
        value = json.loads(output.read_text())
        assert value['passed'] and value['release'] == expected_release, 'wrong journey release'
        if case != 'upgrade-baseline':
            assert value['contact'] is True and value['setup_route'] is True, 'candidate Setup not proven'
        result['cases'].append(value)
        if case == 'clean' and args.first_chat_secret:
            from first_chat import credential_lease, run_chat, PROVIDER
            started = time.monotonic()
            result['step'] = 'first-chat'
            result['first_chat'] = {'passed': False, 'provider': PROVIDER, 'latency_ms': 0}
            try:
                with credential_lease(name, args.first_chat_secret, args.secrets_root, args.oauth_source, log=log) as chat_model:
                    result['first_chat'], internal = run_chat(name, model=chat_model, log=log)
                    if args.phone_config:
                        from phone import run_phone
                        result['step'] = 'second-owner-phone'
                        result['phone'] = {'passed': False}
                        result['phone'] = run_phone(name, args.cli, run / 'phone', args.phone_config, internal)
                        del internal
                        if not result['phone']['passed']:
                            raise RuntimeError('phone_failed')
            except Exception:
                if not result['first_chat']['passed']:
                    result['first_chat']['latency_ms'] = round((time.monotonic() - started) * 1000)
                raise RuntimeError('onboarding_failed') from None
    class OnboardingComplete(Exception):
        pass
    try:
        if args.onboarding_only:
            result['fixture'] = 'launch-onboarding-87-88'
            result['step'] = 'clean-create'
            create(clean)
            result['step'] = 'clean-public-install'
            install(clean, run / 'clean-install', args.release)
            result['step'] = 'clean-candidate-journey'
            journey(clean, 'clean', run / 'clean-state.json', args.release)
            result['step'] = 'complete'
            result['passed'] = True
        else:
            disposable_cases(args, run, clean, create, install, journey, delete, result)
        if args.onboarding_only:
            raise OnboardingComplete
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
        journey(retained, 'retained', state, args.release)
        assert result['cases'][-1]['release'] == args.release, 'retained candidate changed'
        result['step'] = 'retained-reboot'
        command(['limactl', 'stop', retained], log)
        command(['limactl', 'start', '--tty=false', retained], log)
        journey(retained, 'retained', state, args.release)
        result['step'] = 'complete'
        result['passed'] = True
    except OnboardingComplete:
        pass
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
