#!/usr/bin/env python3
"""Source-bound backup premerge checks; native-only, no guest rebuild or live deployment."""
from pathlib import Path
import hashlib
import json
import os
import plistlib
import signal
import subprocess
import sys
import traceback

R = Path(os.environ.get('RIG_ROOT', Path(__file__).resolve().parent.parent)).resolve()
assert str(R).startswith('/Volumes/ThalesMedia/'), 'Acceptance state must be on the external volume'
CONFIG = json.loads((R / 'rig-config.json').read_text())
E = R / 'evidence/premerge'
E.mkdir(parents=True, exist_ok=True)
ENV = dict(os.environ, PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
           RIG_ROOT=str(R), LIMA_HOME=str(R / 'lima'), TMPDIR=str(R / 'tmp'), PYTHONDONTWRITEBYTECODE='1',
           CLANG_MODULE_CACHE_PATH=str(R / 'cache/clang'), SWIFT_MODULECACHE_PATH=str(R / 'cache/swift'),
           PIP_CACHE_DIR=str(R / 'cache/pip'))
for d in ('tmp', 'cache', 'mac/tmp', 'mac/module-cache'):
    (R / d).mkdir(parents=True, exist_ok=True)
report = {'scope': 'native candidate, disposable Mac→Linux→Mac, named data markers, Undo and actual newer-app CLI refusal; GUI separate',
          'success': False, 'steps': []}
child = None


def save():
    (E / 'result.json').write_text(json.dumps(report, indent=2) + '\n')


def interrupted(signum, frame):
    if child is not None and child.poll() is None:
        child.terminate()
        child.wait(timeout=120)
    raise InterruptedError('Worker interrupted; no background work retained')


signal.signal(signal.SIGTERM, interrupted)


def run(name, argv, cwd=R, timeout=1200):
    global child
    log = E / (name + '.log')
    with log.open('w') as output:
        child = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=ENV, stdout=output, stderr=subprocess.STDOUT)
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            child.terminate()
            child.wait(timeout=120)
            raise RuntimeError(name + ' timed out')
    code = child.returncode
    child = None
    report['steps'].append({'name': name, 'exit': code, 'log': str(log)})
    save()
    print(name, code, flush=True)
    return code == 0


try:
    harness = json.loads((R / 'harness-manifest.json').read_text())
    for row in harness['files']:
        assert hashlib.sha256((R / row['path']).read_bytes()).hexdigest() == row['sha256'], row['path']
    report['harness'] = {k:v for k,v in harness.items() if k != 'files'}
    assert run('harness-dry-run', [sys.executable,R / 'rig/backup-proof.py','--dry-run'],timeout=120)
    manifest = json.loads((R / 'source-manifest.json').read_text())
    report['source_pins'] = manifest['pins']
    for row in manifest['files']:
        path = R / row['path']
        content = os.readlink(path).encode() if row['symlink'] else path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == row['sha256'], row['path']
    report['staged_files_verified'] = len(manifest['files'])
    save()
    assert run('venv', ['/opt/homebrew/bin/python3', '-m', 'venv', R / 'venv'])
    py = R / 'venv/bin/python'
    assert run('test-dependencies', [py, '-m', 'pip', 'install', 'pytest', 'PyYAML', 'PyJWT',
                                  '-r', R / 'try-wizard/next/guest/tests/requirements.txt'], timeout=600)
    ENV['PATH'] = str(py.parent) + ':' + ENV['PATH']
    # Run both so the managed Mac companion cannot silently lose its operation reservation.
    for name in ('wam', 'mac-engine'):
        tests = sorted((R / name / 'tests').glob('test_backup_*.py'))
        report[name + '_backup_tests'] = run(name + '-backup-tests', [py, '-m', 'pytest', '-q', *tests], cwd=R / name)
    report['http_dependency_contract'] = run('http-dependency-contract', [py, 'tests/test-backup-test-dependencies.py'], cwd=R / 'try-wizard')
    report['native_contract_tests'] = run('native-backup-contracts', ['make', 'test-backup'], cwd=R / 'try-wizard')
    sparkle = Path(CONFIG['sparkle'])
    archive = sparkle / 'Sparkle-2.10.0.tar.xz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'c2bf58aa8387266ac179357b1415d6f2635f044da8be41042af32425dae6da0c'
    # Public updater verification key only; never read signing/private keys.
    info = plistlib.loads(Path(CONFIG['updater_public_info']).read_bytes())
    ENV.update(SPARKLE_DIR=str(sparkle), SPARKLE_PUBLIC_KEY=info['SUPublicEDKey'],
               SPARKLE_FEED='https://downloads.aiwizards.com/mac/appcast.xml', SIGN_IDENTITY='-', DMG='0',
               VER='0.7.0', BUILD='309', RELEASE_ID=manifest['pins']['try-wizard'])
    report['native_build'] = run('native-build', ['bash', 'next/mac/build.sh'], cwd=R / 'try-wizard')
    candidate = R / 'try-wizard/next/mac/dist/Wizard.app/Contents/MacOS/Wizard'
    if report['native_build']:
        report['candidate'] = {'path': str(candidate), 'sha256': hashlib.sha256(candidate.read_bytes()).hexdigest()}
    report['success'] = all(s['exit'] == 0 for s in report['steps'])
    report['remaining_release_gate'] = 'Read actual round-trip receipt below; native GUI is separate. No merge/deploy/publication from this job.'
    if report['success']:
        # Read-only templates are copied, never booted or updated in place. The
        # proof owns only l1-backup-src/dst and its APFS clone of the saved Mac disk.
        ENV.update(RIG_ROOT=str(R), PYTHON_L5=str(py), PYTHONPATH=str(R / 'wam'))
        (R / 'shared').mkdir(exist_ok=True)
        (R / 'lima').mkdir(exist_ok=True)
        template_root = Path(CONFIG['template_root'])
        inventory = subprocess.check_output(['/opt/homebrew/bin/limactl', '--tty=false', 'list', '--json'],
                    env=dict(ENV, LIMA_HOME=str(template_root)), text=True)
        states = {x['name']: x['status'] for x in map(json.loads, inventory.splitlines()) if x}
        local_inventory = subprocess.check_output(['/opt/homebrew/bin/limactl', '--tty=false', 'list', '--json'], env=ENV,text=True)
        local_states = {x['name']:x['status'] for x in map(json.loads,local_inventory.splitlines()) if x}
        assert not set(local_states) - {'img-source-full','img-base-fresh'}, 'Refuse leftover runtime guests'
        # Only the fresh Linux template is needed for Mac-origin acceptance.
        for name in ('img-base-fresh',):
            assert states.get(name) == 'Stopped', 'Refuse uncertain template: ' + name
            target = R / 'lima' / name
            donor = template_root / name
            if target.exists():
                assert local_states.get(name)=='Stopped', 'Refuse active lane template'
                for entry in ('disk','diffdisk','basedisk'):
                    src,dst=donor/entry,target/entry
                    if src.exists():
                        assert not dst.is_symlink() and src.stat().st_ino!=dst.stat().st_ino
                        assert (src.stat().st_size,src.stat().st_mtime_ns)==(dst.stat().st_size,dst.stat().st_mtime_ns), 'Lane template drift: '+entry
                report['template_reused'] = 'Stopped APFS copy; disk sizes and mtimes equal donor; never booted'
            else:
                assert run('template-' + name, ['cp', '-cR', donor, target], timeout=300)
        baseline = R / 'mac/base/existing-mac-040.img'
        st = baseline.stat()
        report['baseline_before'] = [st.st_ino, st.st_size, st.st_mtime_ns]
        handles = subprocess.run(['lsof', '-Fpfatn', str(baseline.resolve())], capture_output=True, text=True)
        assert not handles.stdout.strip(), 'Saved baseline has open handles'
        report['fresh_acceptance_attempt'] = run('fresh-acceptance', [py, R / 'rig/backup-proof.py'], timeout=10800)
        st = baseline.stat()
        report['baseline_after'] = [st.st_ino, st.st_size, st.st_mtime_ns]
        assert report['baseline_before'] == report['baseline_after'], 'Saved baseline changed'
        report['success'] = report['success'] and report['fresh_acceptance_attempt']
        report['acceptance_scope'] = 'Mac→Linux→Mac; named class assertions on both legs, distinct return baseline, digest-checked Undo on both platforms, real CLI exit-3 newer Files refusal fixture.'
        if (R / 'evidence/backup/result.json').exists():
            report['acceptance_result'] = json.loads((R / 'evidence/backup/result.json').read_text())
except BaseException as exc:
    report['success'] = False
    report['error'] = type(exc).__name__ + ': ' + str(exc)
    (E / 'failure.log').write_text(traceback.format_exc())
finally:
    save()
print(json.dumps(report, indent=2))
sys.exit(0 if report['success'] else 1)
