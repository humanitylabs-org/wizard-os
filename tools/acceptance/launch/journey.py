#!/usr/bin/env python3
"""Guest-side journey. Only run in the explicitly isolated launch audit appliance."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request
import zipfile

ENTRY = 'launch-public-reading'
BODY = ('# The Gettysburg Address\n\n'
        'Four score and seven years ago our fathers brought forth on this continent, '
        'a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.\n')


def run(*argv, timeout=120):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        # These are isolated fixture commands, not auth-store readers. Keep failure
        # output in the worker's private log; public receipts contain only step enums.
        sys.stderr.write(p.stderr[-4000:])
        raise RuntimeError('command_failed:' + Path(argv[0]).name)
    return p.stdout.strip()


def request(url, value=None, raw=None):
    headers = {}
    if value is not None:
        raw = json.dumps(value).encode()
        headers['Content-Type'] = 'application/json'
    elif raw is not None:
        headers['Content-Type'] = 'application/zip'
    req = urllib.request.Request(url, data=raw, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read(4 * 1024 * 1024)
        return json.loads(body) if 'json' in r.headers.get('Content-Type', '') else body


def bundle():
    catalog = {'thinkers': [{'id': 'lincoln', 'name': 'Abraham Lincoln'}],
               'entries': [{'id': ENTRY, 'title': 'The Gettysburg Address (opening)', 'thinker': 'lincoln', 'part': 1}],
               'collections': [{'id': 'launch-public', 'title': 'Public-domain daily reading', 'entries': [ENTRY], 'thinker': 'lincoln'}]}
    manifest = {'version': 1, 'id': 'launch-public', 'title': 'Public-domain daily reading',
                'attribution': 'Abraham Lincoln, Gettysburg Address, 19 November 1863. Opening paragraph.',
                'license': 'Public domain (United States government speech, 1863)', 'rights': 'redistributable'}
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, text in [('collection.json', json.dumps(manifest)), ('content/catalog.json', json.dumps(catalog)),
                           (f'content/{ENTRY}.md', BODY)]:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            z.writestr(info, text.encode())
    return out.getvalue()


def first_contact(registry, cli, case):
    shell = next(a for a in registry['apps'] if 'shell' in (a.get('provides') or []))
    local = shell['view'].get('local') or shell['view']['url']
    assert b'wizard' in request(local).lower(), 'shell not readable'
    # The older release only seeds upgrade continuity. It is not candidate
    # first-contact evidence: 0.3.32's Agent Service predates Setup entirely.
    if case == 'upgrade-baseline':
        return {'contact': None, 'setup_route': None, 'first_contact': 'not-evaluated-upgrade-baseline'}
    contact = json.loads(run('python3', str(cli), 'contact', '--json', '--ssh-host', '127.0.0.1'))
    assert contact['ok'] and '127.0.0.1:18795:' in contact['command']
    assert 'StrictHostKeyChecking=no' not in contact['command']
    from urllib.parse import urlsplit
    origin = 'http://127.0.0.1:' + str(urlsplit(local).port)
    setup = request(origin + '/wizard/v1/setup')
    assert isinstance(setup, dict) and type(setup.get('first_run')) is bool, 'Setup API unavailable'
    return {'contact': True, 'setup_route': True, 'first_contact': 'passed'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--state', required=True, type=Path)
    p.add_argument('--case', required=True, choices=['clean', 'retained', 'upgrade-baseline', 'upgraded'])
    p.add_argument('--cli', required=True, type=Path)
    args = p.parse_args()
    assert os.environ.get('WIZARD_LAUNCH_FIXTURE') == 'launch-audits-8-9', 'fixture guard'
    home = Path.home() / '.wizard-os'
    registry = json.loads((home / 'apps.json').read_text())
    release = json.loads((home / 'release.json').read_text())
    assert release.get('status') in ('pinned', 'drift'), 'public install pin failure'
    assert not any(c.get('core') and not c.get('ok') for c in release.get('checks', [])), 'core pin mismatch'
    # Probe frozen code without modifying the shipped profile or installers.
    report = json.loads(run('python3', str(args.cli), 'report', '--json'))
    assert report['schema'] == 'wizard-report-v1'
    contact_result = first_contact(registry, args.cli, args.case)
    # No automatic repairs: missing catalog app/install or private content is a failing journey.
    if not any(a['id'] == 'wisdom' for a in registry['apps']):
        assert args.case == 'clean' or not args.state.exists(), 'installed app vanished'
        run(str(Path.home() / '.local/bin/wam'), 'install', 'wisdom', timeout=900)
        registry = json.loads((home / 'apps.json').read_text())
    wisdom = next(a for a in registry['apps'] if a['id'] == 'wisdom')
    endpoint = wisdom['mcp']['url'].removesuffix('/mcp')
    state = request(endpoint + '/api/wisdom')
    assert isinstance(state, dict)
    entries = state.get('entries', [])
    assert not any(e['id'] != ENTRY for e in entries), 'non-fixture content refused'
    if not entries:
        assert not args.state.exists(), 'retained library vanished'
        staged = request(endpoint + '/api/library/stage', raw=bundle())
        item = staged.get('bundle', staged)
        request(endpoint + '/api/library/action', {'id': item['id'], 'action': 'enable'})
    def entry():
        return next(e for e in request(endpoint + '/api/wisdom')['entries'] if e['id'] == ENTRY)
    current = entry()
    assert current['body'] == BODY, 'public reading content changed'
    old = json.loads(args.state.read_text()) if args.state.exists() else None
    if old:
        assert current['progress'] == old['progress'], 'retained progress lost'
    progress = ((current['progress'] or 0) + 7) % 101
    def set_progress(value):
        request(endpoint + '/api/wisdom/reaction', {'kind': 'entry', 'id': ENTRY, 'field': 'progress', 'value': value})
        assert entry()['progress'] == value, 'reading state write/readback failed'
    set_progress(progress)
    containers = run('sudo', '-n', 'docker', 'ps', '--filter', 'label=com.docker.compose.project=wisdom_wizardapps', '--format', '{{.ID}}').split()
    assert len(containers) == 1, 'unexpected Wisdom topology'
    container = containers[0]
    mounts = json.loads(run('sudo', '-n', 'docker', 'inspect', '--format', '{{json .Mounts}}', container))
    data = Path(next(m['Source'] for m in mounts if m['Destination'] == '/data'))
    db = data / 'wisdom.sqlite'
    # Backup via SQLite API while stopped; never copy a live WAL database.
    def restart():
        run('sudo', '-n', 'docker', 'start', container)
        for _ in range(30):
            try:
                if entry()['body'] == BODY:
                    return
            except (OSError, StopIteration, ValueError):
                pass
            time.sleep(1)
        raise RuntimeError('reader_restart_timeout')
    run('sudo', '-n', 'docker', 'stop', container)
    backup = args.state.with_suffix('.sqlite')
    helper = str(Path(__file__).with_name('sqlite_copy.py'))
    run('sudo', '-n', 'python3', helper, str(db), str(backup))
    restart()
    set_progress((progress + 1) % 101)
    run('sudo', '-n', 'docker', 'stop', container)
    run('sudo', '-n', 'python3', helper, str(backup), str(db))
    restart()
    assert entry()['progress'] == progress, 'restore did not restore the older reading position'
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps({'progress': progress}))
    receipt = {'fixture': 'launch-audits-8-9', 'case': args.case, 'release': release['release'],
               'architecture': run('uname', '-m'), 'public_install': True, 'overlays': [],
               'diagnostics': 'frozen-source-probe-not-installed-release', **contact_result,
               'public_reading_sha256': hashlib.sha256(BODY.encode()).hexdigest(),
               'retained_readback': old is not None, 'progress': progress, 'restore': True, 'passed': True}
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
