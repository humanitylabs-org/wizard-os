#!/usr/bin/env python3
"""Operator-dispatched CI transport to the unchanged durable heavy worker.

No owner-session impersonation, arbitrary command input, SSH, or direct VM start.
The existing configured shared lock is mandatory; missing configuration fails closed.
Raw worker/guest logs stay private on the mounted work volume.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request

SOURCE = Path(__file__).resolve().parents[3]
WORKER_COMMIT = '88c0c478d74f80e8abf7d09ec01ee5e9a5963a2a'
WORKER_HASH = 'e92959ed94f7e40071f4ca237aa23425a307033d4f3d71d647c0261b55637cee'
GIB = 1 << 30


def check(condition, code):
    if not condition:
        raise RuntimeError(code)


def mounted_volume(path):
    path = path.resolve(strict=True)
    while not path.is_mount():
        path = path.parent
    check(path != Path('/'), 'external_work_volume_required')
    return path


def placement(env):
    check(env.get('WIZARD_CI_ROOT'), 'missing_WIZARD_CI_ROOT')
    ci = Path(env['WIZARD_CI_ROOT']).resolve(strict=True)
    check(ci.is_dir(), 'ci_root_not_directory')
    work = Path(env['WIZARD_WORK_ROOT']).resolve(strict=True) if env.get('WIZARD_WORK_ROOT') else mounted_volume(ci)
    check(work.is_mount() and work != Path('/') and ci.is_relative_to(work) and ci != work,
          'external_work_volume_required')
    check(env.get('WIZARD_CI_WORKER_LOCK'), 'missing_WIZARD_CI_WORKER_LOCK')
    raw = Path(env['WIZARD_CI_WORKER_LOCK'])
    check(raw.is_absolute() and raw.exists() and not raw.is_symlink(), 'existing_shared_lock_required')
    lock = raw.resolve(strict=True)
    check(lock.is_file() and lock.is_relative_to(work), 'shared_lock_outside_work_volume')
    if env.get('WIZARD_HEAVY_REMOTE_LOCK'):
        check(lock.samefile(env['WIZARD_HEAVY_REMOTE_LOCK']), 'shared_lock_identity_mismatch')
    if env.get('WIZARD_HEAVY_ROOT'):
        check(Path(env['WIZARD_HEAVY_ROOT']).resolve(strict=True) == work, 'heavy_root_mismatch')
    # release-acceptance.yml dispatches this controller only on macOS ARM64.
    # Keep its legacy 250 reserve + 40 guest + 1 metadata = 291 GiB; Linux
    # directory admission belongs to run.py/release_gate.py, not this transport.
    check(shutil.disk_usage(work).free >= 291 * GIB, '291_GiB_free_required')
    for tool in ('limactl', 'git', 'python3'):
        check(shutil.which(tool), 'missing_' + tool)
    return ci, work, lock


def published_manifest(release, expected):
    check(re.fullmatch(r'\d+\.\d+\.\d+', release), 'invalid_release')
    check(re.fullmatch(r'[0-9a-f]{64}', expected), 'invalid_manifest_sha256')
    canonical = (SOURCE / 'releases' / (release + '.json')).read_bytes()
    check(hashlib.sha256(canonical).hexdigest() == expected, 'canonical_manifest_mismatch')
    url = 'https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/main/releases/' + release + '.json'
    with urllib.request.urlopen(url, timeout=30) as response:
        public = response.read(1024 * 1024)
    check(public == canonical, 'public_manifest_mismatch')
    manifest = json.loads(public)
    check(manifest['version'] == release, 'manifest_version_mismatch')
    wam = manifest['components']['wizard-app-manager']
    check(wam['repo'] == 'humanitylabs-org/wizard-app-manager' and wam['branch'] == 'main', 'untrusted_wam_repository')
    check(re.fullmatch(r'[0-9a-f]{40}', wam['commit']), 'invalid_wam_commit')
    return wam['commit']


def rpc(worker, spool, lock, value):
    result = subprocess.run([sys.executable, str(worker), '--root', str(spool), '--lock', str(lock)],
                            input=json.dumps(value), text=True, capture_output=True, timeout=30)
    check(result.returncode == 0, 'worker_rpc_failed')
    data = json.loads(result.stdout)
    check(not data.get('error'), 'worker_rpc_failed')
    return data


def execute(stage):
    """The only VM-calling path, invoked by the real worker with its lease."""
    metadata = json.loads((stage / 'job.json').read_text())
    lock = Path(metadata['lock'])
    fd = int(os.environ['WIZARD_HEAVY_LOCK_FD'])
    held, current = os.fstat(fd), lock.stat()
    check((held.st_dev, held.st_ino) == (current.st_dev, current.st_ino), 'inherited_lock_identity_mismatch')
    src = stage / 'source'
    check(hashlib.sha256((src / 'releases' / (metadata['release'] + '.json')).read_bytes()).hexdigest() == metadata['manifest_sha256'],
          'staged_manifest_mismatch')
    fixture = src / 'tools/acceptance/launch/backup_class_fixture.py'
    fixture_hash = hashlib.sha256(fixture.read_bytes()).hexdigest()
    results = []
    # Separate empty candidate/baseline disks and backup fixtures for BOTH baselines.
    for previous in ('0.3.39', '0.3.40'):
        root = stage / ('v' + previous.replace('.', ''))
        argv = [sys.executable, str(src / 'tools/acceptance/launch/release_gate.py'),
                '--root', str(root), '--release', metadata['release'], '--previous-release', previous,
                '--cli', str(src / 'wam/wizard-cli/wizard'), '--wam-commit', metadata['wam_commit'],
                '--fixture', str(fixture), '--fixture-sha256', fixture_hash]
        # Real check-only before each run; neither capacity nor assertions is weakened.
        subprocess.run([*argv, '--check-only'], check=True)
        code = subprocess.run(argv).returncode
        path = root / 'evidence/receipt.json'
        receipt = json.loads(path.read_text()) if path.exists() else {'passed': False, 'step': 'no_receipt'}
        results.append(receipt)
        (stage / 'receipts.json').write_text(json.dumps({**metadata, 'fixture_sha256': fixture_hash,
                                                       'results': results}, indent=2) + '\n')
        check(code == 0 and receipt.get('passed') is True, 'release_acceptance_failed')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--execute':
        execute(Path(sys.argv[2]))
        return
    env = os.environ
    def interrupted(signum, frame):
        raise RuntimeError('controller_cancelled')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    check(env.get('GITHUB_REPOSITORY') == 'humanitylabs-org/wizard-os' and env.get('GITHUB_REF') == 'refs/heads/main'
          and env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'canonical_manual_dispatch_required')
    release, expected = env['ACCEPT_RELEASE'], env['ACCEPT_MANIFEST_SHA256']
    wam_commit = published_manifest(release, expected)
    ci, work, lock = placement(env)
    print(json.dumps({'preflight': True, 'executed': False, 'shared_lock_exists': True,
                      'external_volume': True, 'reserve_gib': 250, 'required_free_gib': 291,
                      'release': release, 'manifest_sha256': expected}), flush=True)
    check(env.get('ACCEPT_PREFLIGHT_ONLY') in ('true', 'false'), 'explicit_preflight_choice_required')
    if env['ACCEPT_PREFLIGHT_ONLY'] == 'true':
        return
    run = env['GITHUB_RUN_ID']
    attempt = env['GITHUB_RUN_ATTEMPT']
    check(re.fullmatch(r'\d+', run) and re.fullmatch(r'\d+', attempt), 'invalid_run_identity')
    # Keep the Lima UNIX socket path short. Existing paths are never erased/reused.
    base = work / 'ra'
    base.mkdir(mode=0o700, exist_ok=True)
    check(base.resolve() == base, 'aliased_staging_root')
    stage = base / (run + '-' + attempt)
    check(len(str(stage / 'v0340/lima/release-check/ssh.sock.1234567890123456')) < 104, 'lima_socket_path_too_long')
    stage.mkdir(mode=0o700)
    src = stage / 'source'
    src.mkdir()
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
    check(sha == env['GITHUB_SHA'], 'workflow_source_mismatch')
    archive = subprocess.check_output(['git', 'archive', sha], cwd=SOURCE)
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(src, filter='data')
    # Public, fixed-repository exact commit; checkout never writes to an owner's tree.
    subprocess.run(['git', 'clone', '--quiet', '--no-checkout', 'https://github.com/humanitylabs-org/wizard-app-manager', str(src / 'wam')], check=True)
    subprocess.run(['git', '-C', str(src / 'wam'), 'checkout', '--quiet', '--detach', wam_commit], check=True)
    check(subprocess.check_output(['git', '-C', str(src / 'wam'), 'rev-parse', 'HEAD'], text=True).strip() == wam_commit,
          'wam_source_mismatch')
    worker = stage / 'heavy-worker.py'
    with urllib.request.urlopen('https://raw.githubusercontent.com/humanitylabs-org/wizard-agent-service/' + WORKER_COMMIT + '/scripts/heavy-worker.py', timeout=30) as response:
        code = response.read(1024 * 1024)
    check(hashlib.sha256(code).hexdigest() == WORKER_HASH, 'worker_source_mismatch')
    worker.write_bytes(code)
    metadata = {'release': release, 'manifest_sha256': expected, 'source_commit': sha,
                'wam_commit': wam_commit, 'worker_commit': WORKER_COMMIT, 'lock': str(lock),
                'github_run_id': run, 'github_run_attempt': attempt}
    (stage / 'job.json').write_text(json.dumps(metadata))
    # An independent CI control-plane spool, never the Service's authority database.
    # Both dispatchers use exactly the EXISTING Android/VM lock and worker health guards.
    spool = base / 'spool'
    os.environ.update(WIZARD_HEAVY_ROOT=str(work), WIZARD_WORK_ROOT=str(work))
    job_id = 'heavy_' + hashlib.sha256(('release-acceptance:' + run + ':' + attempt).encode()).hexdigest()[:32]
    spec = {'cwd': str(src), 'argv': [sys.executable, str(src / 'tools/acceptance/launch/ci.py'), '--execute', str(stage)],
            'timeout_seconds': 18000, 'lane': 'heavy'}
    submitted = False
    finished = False
    try:
        submitted = True  # ambiguous submit must also be cancelled on transport failure
        state = rpc(worker, spool, lock, {'action': 'submit', 'job_id': job_id, 'spec': spec})
        print(json.dumps({'job_id': job_id, 'state': state['state']}), flush=True)
        deadline = time.monotonic() + 19000
        while state['state'] not in ('completed', 'failed', 'cancelled', 'interrupted'):
            check(time.monotonic() < deadline, 'controller_deadline')
            time.sleep(10)
            state = rpc(worker, spool, lock, {'action': 'status', 'job_id': job_id})
        finished = True
        receipt = dict(state.get('receipt') or {})
        receipt.pop('log_path', None)
        print(json.dumps({'job_id': job_id, 'state': state['state'], 'receipt': receipt}), flush=True)
        receipts = stage / 'receipts.json'
        value = {'results': []}
        if receipts.exists():
            value = json.loads(receipts.read_text())
            value.pop('lock', None)  # private machine configuration never enters Actions output
            print(json.dumps(value), flush=True)
        check(state['state'] == 'completed' and receipts.exists(), 'worker_did_not_complete_acceptance')
        check(len(value['results']) == 2 and all(r.get('passed') is True for r in value['results']), 'incomplete_acceptance')
    finally:
        if submitted and not finished:
            rpc(worker, spool, lock, {'action': 'cancel', 'job_id': job_id})


if __name__ == '__main__':
    os.umask(0o077)
    try:
        main()
    except Exception as error:
        # Exception text can contain private paths/URLs; only named refusal codes are public.
        reason = str(error) if isinstance(error, RuntimeError) and re.fullmatch(r'[A-Za-z0-9_]+', str(error)) else type(error).__name__
        print(json.dumps({'passed': False, 'reason': reason}), flush=True)
        sys.exit(1)
