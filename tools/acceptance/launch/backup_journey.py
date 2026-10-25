#!/usr/bin/env python3
"""Real installed WAM backup/restore/Undo on an admitted disposable guest.

Reuses the class-marker fixture from the retained L1 backup rig, by exact hash.
No auth/inference; synthetic login content only. Emits booleans, never key data.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--fixture', required=True, type=Path)
    p.add_argument('--fixture-sha256', required=True)
    p.add_argument('--release', required=True)
    p.add_argument('--wam-commit', required=True)
    args = p.parse_args()
    assert os.environ.get('WIZARD_LAUNCH_FIXTURE') == 'launch-audits-8-9'
    assert Path('/var/lib/wizard-backup-disposable').is_file()
    assert hashlib.sha256(args.fixture.read_bytes()).hexdigest() == args.fixture_sha256
    source = Path.home() / 'wizard-app-manager'
    assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == args.wam_commit
    release = json.loads((Path.home() / '.wizard-os/release.json').read_text())
    assert release['release'] == args.release and release['status'] in ('pinned', 'drift')
    os.chdir(source)
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location('backup_fixture', args.fixture)
    assert spec is not None and spec.loader is not None
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    b = fixture.boxes()
    state = Path.home() / 'backup-release-acceptance'
    assert not state.exists(), 'refuse reused backup fixture'
    state.mkdir(mode=0o700)
    manifest = state / 'markers.json'
    fixture.seed(b, manifest)
    before = fixture.snapshot(b, manifest)
    assert all(before['checks'][k] is True for k in fixture.CLASSES)
    wam = str(Path.home() / '.local/bin/wam')
    def backup(*argv):
        r = subprocess.run([wam, 'backup', *map(str, argv), '--json'], capture_output=True, text=True, timeout=1800)
        assert r.returncode == 0, 'real backup CLI failed: ' + argv[0]
        result = json.loads(r.stdout)
        assert result.get('ok', True) is True and not result.get('partial')
        return result
    key = state / 'recovery.key'
    backup('key', 'new', '--out', key)
    bundle = state / 'release.wizardbackup'
    backup('export', '--key-file', key, '-o', bundle)
    backup('verify', bundle, '--key-file', key)
    # Distinct return baseline: import must actually restore, Undo must reverse it.
    files = json.loads(manifest.read_text())['owner_files']['files']
    for row in files:
        (b.files_root() / row['path']).write_text('distinct release Undo baseline\n')
    settings = b.home / 'settings.json'
    cfg = json.loads(settings.read_text())
    cfg['backup_acceptance'] = 'distinct-release-undo-baseline'
    settings.write_text(json.dumps(cfg))
    disturbed = fixture.snapshot(b, manifest)
    assert not disturbed['checks']['files'] and not disturbed['checks']['settings']
    imported = backup('import', bundle, '--key-file', key, '--yes')
    assert not imported.get('refused')
    restored = fixture.snapshot(b, manifest)
    required = set(fixture.CLASSES) | {'scheduled_jobs_paused'}
    assert all(restored['checks'][k] is True for k in required)
    assert restored['cron_ids'], 'no vacuous cron assertion'
    undo = backup('undo')
    assert undo.get('digest_match') is True
    undone = fixture.snapshot(b, manifest)
    assert undone['checks'] == disturbed['checks'] and undone['cron_ids'] == disturbed['cron_ids']
    print(json.dumps({'passed': True, 'release': args.release, 'wam_commit': args.wam_commit,
                      'classes': sorted(required), 'real_export_verify_import': True,
                      'cron_paused': True, 'distinct_baseline': True, 'undo_digest_match': True,
                      'scope': 'same-release Linux round trip; synthetic login; no scheduler/refresh fencing or Mac GUI claim'}))


if __name__ == '__main__':
    main()
