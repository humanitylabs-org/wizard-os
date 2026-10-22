#!/usr/bin/env python3
"""Private build-worker acceptance driver. No secret output. All guests are disposable."""
import contextlib
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback

R = Path(os.environ.get('RIG_ROOT', Path(__file__).resolve().parent.parent)).resolve()
M = R / 'mac'
S = R / 'try-wizard'
E = R / 'evidence/backup'
Q = R / 'shared/mac-backup-qa'
KEYS = R / 'keys'
RIG = R / 'bin/rig'
WAM_BRANCH = 'feature/wizard-backup-20261018'
WAM_LINUX_SHA = '2ba5599c2d1b38ee2190f179225b12bc01a2868b'
# Shipped 0.4.0 Macs run the release wam line (0696805f); the backup engine is ported onto it with managed admission.
MAC_WAM_BRANCH = 'integration/backup-launch-mac-v1'
MAC_WAM_SHA = '75248544a64c17fc2894815b9cf8d793a98e6c6c'
WAM_REPO = 'https://github.com/humanitylabs-org/wizard-app-manager.git'
SRC = 'l1-backup-src'
DST = 'l1-backup-dst'
MACNAME = 'mac-backup-proof'
REPORT = {'build': 'NOT_RUN', 'swift_tests': 'NOT_RUN', 'P1': 'NOT_RUN', 'P2': 'NOT_RUN', 'gui': 'NOT_RUN', 'refusal': 'NOT_RUN', 'steps': []}
START = time.monotonic()
CREATED = []
VM = None
SECRET_VALUES = []
ENV = dict(os.environ, PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
           RIG_ROOT=str(R), LIMA_HOME=str(R/'lima'), TMPDIR=str(M/'tmp'), CLANG_MODULE_CACHE_PATH=str(M/'module-cache/clang'),
           SWIFT_MODULECACHE_PATH=str(M/'module-cache/swift'), PYTHONDONTWRITEBYTECODE='1')


def safe(text):
    for secret in SECRET_VALUES:
        text = text.replace(secret, '[redacted]')
    return text


def save_report():
    REPORT['seconds'] = round(time.monotonic() - START, 1)
    (E/'result.json').write_text(safe(json.dumps(REPORT, indent=2)))


def free_check():
    free = shutil.disk_usage(R).free
    if free < 250 * (1 << 30):
        raise RuntimeError('External volume below 250 GiB free; stopped rather than consuming reserve')
    return free


def write_json(name, obj):
    (E/(name + '.json')).write_text(safe(json.dumps(obj, indent=2, sort_keys=True)))


def run(label, argv, *, timeout=600, cwd=None, check=True, log=True, input=None, env=None):
    free_check()
    t = time.monotonic()
    print('START', label, flush=True)
    p = subprocess.run(list(map(str, argv)), input=input, capture_output=True, text=True, timeout=timeout,
                       env=env or ENV, cwd=cwd)
    if log:
        (E/(label + '.log')).write_text(safe(p.stdout + '\nSTDERR\n' + p.stderr))
    REPORT['steps'].append({'step': label, 'exit': p.returncode, 'seconds': round(time.monotonic()-t, 1)})
    save_report()
    print('END', label, p.returncode, flush=True)
    if check and p.returncode:
        raise RuntimeError(label + ' failed; see its log')
    return p


def parse_json(text):
    for line in reversed(text.splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            pass
    raise RuntimeError('Command returned no JSON object')


def linux(label, name, script, *, timeout=3600, wizard=True, **kw):
    if wizard:
        script = 'export PATH="$HOME/.local/bin:$PATH"; ' + script
    return run(label, [RIG, 'exec', name, *(['--wizard'] if wizard else []), '--', script], timeout=timeout, **kw)


def mac(label, script, *, wizard=False, timeout=3600, check=True, log=True):
    free_check()
    if wizard:
        script = 'sudo -iu wizard env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus bash -lc ' + shlex.quote(script)
    marker = 'EXIT_' + secrets.token_hex(8)
    payload = '{\n' + script + '\n}; _rc=$?; printf "\\n' + marker + '%s\\n" "$_rc"; exit\n'
    t = time.monotonic()
    print('START', label, flush=True)
    with socket.create_connection(('127.0.0.1', 48400), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(payload.encode())
        output = bytearray()
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            output.extend(chunk)
    text = output.decode(errors='replace')
    before, sep, after = text.rpartition(marker)
    rc = int(after.strip().splitlines()[0]) if sep else 255
    if log:
        (E/(label+'.log')).write_text(safe(before))
    REPORT['steps'].append({'step': label, 'exit': rc, 'seconds': round(time.monotonic()-t, 1)})
    save_report()
    print('END', label, rc, flush=True)
    if check and rc:
        raise RuntimeError(label + ' failed; see its log')
    return before


def request(path, *, method='GET', body=None, file=None, headers=None, download=None, timeout=120):
    conn = http.client.HTTPConnection('127.0.0.1', 48430, timeout=timeout)
    h = {'X-Wizard-Backup': 'wizardbackup-v1'} if headers is None else headers
    stream = None
    if body is not None:
        payload = json.dumps(body).encode(); h = dict(h, **{'Content-Type': 'application/json'})
    elif file:
        stream = Path(file).open('rb'); payload = stream
        h = dict(h, **{'Content-Type': 'application/octet-stream', 'Content-Length': str(Path(file).stat().st_size)})
    else:
        payload = None
    try:
        conn.request(method, '/api/backup/' + path, body=payload, headers=h)
        response = conn.getresponse()
        code = response.status
        if download and code == 200:
            with Path(download).open('wb') as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            return code, {'bytes': Path(download).stat().st_size, 'sha256': sha_file(Path(download))}
        return code, json.loads(response.read())
    finally:
        if stream:
            stream.close()
        conn.close()


def sha_file(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def job(label, path, body, *, timeout=7200):
    t = time.monotonic()
    status, j = request(path, method='POST', body=body)
    if status != 202:
        write_json(label+'-rejected', {'http_status': status, 'response': j})
        raise RuntimeError(label + ' was not accepted')
    while j['state'] == 'running':
        if time.monotonic()-t > timeout:
            raise RuntimeError(label + ' timed out')
        free_check()
        time.sleep(2)
        status, j = request('jobs/' + j['id'])
        if status != 200:
            raise RuntimeError(label + ' lost its job receipt')
    j['wall_seconds'] = round(time.monotonic()-t, 1)
    write_json(label, j)
    if j['state'] not in ('complete', 'verified'):
        raise RuntimeError(label + ' failed; see its receipt')
    return j


def store_key(path, secret):
    KEYS.mkdir(exist_ok=True, mode=0o700)
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(secret + '\n')
    SECRET_VALUES.append(secret)


def compare(source, target, *, paused, fixture=False):
    checks = {}
    for ident, agent in source['agents'].items():
        found = target['agents'].get(ident, {})
        for key in ('memory_sha256', 'user_sha256'):
            checks['agent/' + ident + '/' + key] = agent.get(key) == found.get(key)
        for sid, value in agent['sessions'].items():
            checks['session/' + sid] = found.get('sessions', {}).get(sid) == value
        if paused:
            # off = switched off by the import, or never set up on either side (None: no Telegram configured)
            checks['agent/' + ident + '/telegram_off'] = found.get('telegram_enabled') is False or (
                agent.get('telegram_enabled') is None and found.get('telegram_enabled') is None)
            dest_jobs = {j['id']: j for j in found.get('cron', [])}
            for j in agent.get('cron', []):
                if j.get('enabled', True) and j.get('state') not in ('paused', 'completed', 'error'):
                    dst = dest_jobs.get(j['id'], {})
                    checks['cron/' + str(j['id'])] = bool(dst) and (dst.get('enabled') is False or dst.get('state') == 'paused' or bool(dst.get('paused_at')))
    for rel, meta in source['files'].items():
        checks['file/' + rel] = target['files'].get(rel) == meta
    for name, value in source['settings'].items():
        checks['settings/' + name] = target['settings'].get(name) == value
    # A split Wizard (wizard-ux + wizard-agent-service) and a bundled one (wizard-shell = both) keep their own shell:
    # the restore keeps the destination's providers. Then check the slots instead of those app versions.
    slot_apps = {'wizard-ux', 'wizard-agent-service', 'wizard-shell'}
    src_slots, dst_slots = slot_apps & set(source['app_versions']), slot_apps & set(target['app_versions'])
    crossed = src_slots != dst_slots
    for ident, row in source['app_versions'].items():
        if crossed and ident in slot_apps:
            continue
        from wam.backup.versions import compare as version_compare
        target_version = target.get('app_versions', {}).get(ident, {}).get('version')
        relation = version_compare(row.get('version'), target_version)
        checks['version/' + ident] = ident in target['app_versions'] and (relation in (-1, 0) or row.get('version') == target_version)
    if crossed:
        checks['slot/one-agent-service'] = len(dst_slots & {'wizard-agent-service', 'wizard-shell'}) == 1
        checks['slot/one-shell'] = len(dst_slots & {'wizard-ux', 'wizard-shell'}) == 1
    if fixture:
        checks.update(target['fixture_checks'])
    return {'ok': all(checks.values()), 'passed': sum(checks.values()), 'total': len(checks), 'checks': checks,
            'agents': len(source['agents']), 'sessions': sum(len(a['sessions']) for a in source['agents'].values()),
            'files': len(source['files']), 'file_bytes': sum(x['bytes'] for x in source['files'].values())}


def snapshot(label, where, *, markers=False):
    cmd = 'cd /home/wizard/wizard-app-manager && python3 /mnt/rig-shared/mac-backup-qa/guest-snapshot.py'
    if markers:
        cmd += ' /mnt/rig-shared/mac-backup-qa/markers.json'
    text = mac(label, cmd, wizard=True) if where == 'mac' else linux(label, where, cmd).stdout
    result = parse_json(text)
    write_json(label, result)
    return result


MAC_WAM_UPDATE = 'set -e\nH=$(sed -n \'s/^cd "\\(.*\\)" && exec.*/\\1/p\' /home/wizard/.local/bin/wam)\ntest -n "$H"\necho "WAM_HERE=$H"\nls -la "$H" | head -20\nif git -C "$H" rev-parse --git-dir >/dev/null 2>&1; then\n  cd "$H"; git fetch -q __REPO__ __BRANCH__; git checkout -q --detach __REF__; S=$(git rev-parse HEAD)\nelse\n  # Shipped guest: plain copy, no .git. In-place update replaces the wam package, keeping the old one beside it.\n  T=$(mktemp -d); git -C "$T" init -q; git -C "$T" fetch -q __REPO__ __BRANCH__\n  S=$(git -C "$T" rev-parse __REF__)\n  if [ -d "$H/wam" ]; then rm -rf "$H/wam.pre-backup"; mv "$H/wam" "$H/wam.pre-backup"; fi\n  git -C "$T" archive "$S" wam pyproject.toml THIRD_PARTY_NOTICES.md | tar -x -C "$H"\n  echo "$S" > "$H/.wam-commit"; rm -rf "$T"\nfi\n/home/wizard/.local/bin/wam backup --help >/dev/null\n/home/wizard/.local/bin/wam backup restic-install >/dev/null || echo "restic-install failed (non-fatal)"\necho "$S"\n'


def install_wam(label, where, sha=None, branch=None):
    ref = sha or 'FETCH_HEAD'
    branch = branch or WAM_BRANCH
    if where == 'mac':
        # The guest shell path flattens newlines and expands $ once, so run the update as a file from the shared folder.
        script = Q / 'wam-update.sh'
        script.write_text(MAC_WAM_UPDATE.replace('__REPO__', shlex.quote(WAM_REPO)).replace('__BRANCH__', branch)
                          .replace('__REF__', ref))
        cmd = 'bash /mnt/rig-shared/mac-backup-qa/wam-update.sh'
    else:
        cmd = 'set -e; cd /home/wizard/wizard-app-manager; git fetch ' + shlex.quote(WAM_REPO) + ' ' + WAM_BRANCH + '; git checkout --detach ' + ref + '; /home/wizard/.local/bin/wam backup --help; git rev-parse HEAD'
    text = mac(label, cmd, wizard=True) if where == 'mac' else linux(label, where, cmd).stdout
    for line in reversed(text.splitlines()):
        if len(line) == 40 and all(c in '0123456789abcdef' for c in line):
            return line
    raise RuntimeError('No pinned WAM SHA')


def clone(name, image):
    run(name+'-clone', [RIG, 'clone', image, name])
    CREATED.append(name)
    run(name+'-start', [RIG, 'start', name, '--wizard-wait', '900'], timeout=1200)
    linux(name+'-admit', name, 'touch /var/lib/wizard-backup-disposable', wizard=False)


def export_mac(label, secret):
    done = job(label+'-export', 'export', {'secret': secret})
    path = Q / (label+'.wizardbackup')
    status, got = request('jobs/'+done['id']+'/download', download=path, timeout=3600)
    if status != 200 or got['sha256'] != done['sha256'] or got['bytes'] != done['total_bytes']:
        raise RuntimeError('Mac download integrity check failed')
    status, consumed = request('jobs/'+done['id'])
    assert consumed['state'] == 'downloaded'
    mac(label+'-staging-clean', 'test ! -e /var/lib/wizard/backup-transfer/'+done['id']+'/bundle.wizardbackup && test -z "$(find /var/lib/wizard/backup-transfer -name \'key-*\' -print -quit)"')
    write_json(label+'-download', got)
    return path


def fixture(label, where, action='snapshot'):
    cmd = 'cd /home/wizard/wizard-app-manager && python3 /mnt/rig-shared/mac-backup-qa/fixture.py ' + action + ' /mnt/rig-shared/mac-backup-qa/markers.json'
    text = mac(label, cmd, wizard=True) if where == 'mac' else linux(label, where, cmd).stdout
    result = parse_json(text)
    write_json(label, result)
    return result


def require_markers(result, *, paused, refused_app=False):
    from fixture import CLASSES
    checks = result['checks']
    required = (set(CLASSES) - ({'app_data'} if refused_app else set())) | ({'scheduled_jobs_paused'} if paused else set())
    assert required <= checks.keys(), 'Missing named coverage: ' + str(required - checks.keys())
    assert all(checks[k] is True for k in required), 'Failed markers: ' + str([k for k in required if checks[k] is not True])
    assert result.get('cron_ids'), 'Vacuous scheduled-job coverage'


def expect_comparison(label, source, target, *, paused):
    result = compare(source, target, paused=paused)
    write_json(label, result)
    assert result['total'] > 0 and result['ok'], label + ': marker differences'


def linux_undo(label, before):
    receipt = parse_json(linux(label, DST, 'wam backup undo --json').stdout)
    assert receipt.get('ok', True) and receipt.get('digest_match') is True, receipt
    expect_comparison(label+'-markers', before, snapshot(label+'-after', DST), paused=False)


def mac_import(label, bundle, secret):
    code, uploaded = request('upload', method='POST', file=bundle, timeout=3600)
    assert code == 201 and uploaded['sha256'] == sha_file(bundle)
    job(label+'-verify', 'jobs/'+uploaded['id']+'/verify', {'secret':secret})
    result = job(label+'-import', 'jobs/'+uploaded['id']+'/import', {'secret':secret,'confirm':True})
    assert result['result'].get('ok') is True and not result['result'].get('partial'), result


def acceptance(native_key):
    # Mac is the origin. Publish markers only AFTER real guest seeding, and
    # assert them before either exporter runs. Never copy a missing root file.
    fixture('mac-seed', 'mac', 'seed')
    assert (Q/'markers.json').is_file(), 'Seed did not publish markers.json'
    shutil.copyfile(Q/'markers.json', R/'markers.json')
    require_markers(fixture('mac-source-markers', 'mac'), paused=False)
    source = snapshot('mac-source', 'mac')
    native_bundle = export_mac('mac-native', native_key)
    REPORT['P1'] = 'RUNNING'; save_report()
    clone(DST, 'img-base-fresh')
    assert install_wam('destination-wam-update', DST, WAM_LINUX_SHA) == WAM_LINUX_SHA
    # Real account app/volume, not an arbitrary untracked directory.
    linux('destination-refresh-files',DST,'wam app update files --no-backup')
    linux('destination-account-app', DST, 'wam install wizard-claude')
    linux('destination-registry-refresh',DST,'wam apps --json')
    before = snapshot('linux-before', DST)
    clean_linux = fixture('linux-before-markers',DST)
    assert all(clean_linux['checks'][key] is False for key in __import__('fixture').CLASSES), 'Fresh Linux retained a source marker'
    run('native-key-copy', [RIG,'copy-in',DST,KEYS/'mac-native.key','/home/wizard/mac-import.key','--owner','wizard'])
    linux('native-key-mode',DST,'chmod 600 /home/wizard/mac-import.key')
    imported = parse_json(linux('mac-to-linux-import',DST,'wam backup import /mnt/rig-shared/mac-backup-qa/mac-native.wizardbackup --key-file /home/wizard/mac-import.key --yes --json').stdout)
    assert imported.get('ok') is True and not imported.get('partial') and not imported.get('refused'), imported
    target = snapshot('linux-restored', DST)
    expect_comparison('mac-to-linux-markers',source,target,paused=True)
    require_markers(fixture('linux-restored-markers',DST),paused=True)
    # This is the actual Linux export of the imported Mac data.
    linux('linux-roundtrip-export',DST,'wam backup export --key-file /home/wizard/mac-import.key -o /mnt/rig-shared/mac-backup-qa/linux-return.wizardbackup --json')
    REPORT['P1'] = 'PASS'; REPORT['P2'] = 'RUNNING'; save_report()
    # Disturb the destination so return-leg checks cannot pass on leftover Mac
    # markers. The engine's Undo must restore this distinct pre-import baseline.
    mac('mac-return-baseline', 'python3 /mnt/rig-shared/mac-backup-qa/disturb.py',wizard=True)
    mac_before = snapshot('mac-return-before', 'mac')
    disturbed = fixture('mac-return-disturbed','mac')
    assert all(disturbed['checks'][key] is False for key in __import__('fixture').CLASSES), 'Return baseline retained a source marker'
    mac_import('linux-to-mac', Q/'linux-return.wizardbackup',native_key)
    require_markers(fixture('mac-return-markers','mac'),paused=True)
    expect_comparison('linux-to-mac-markers',target,snapshot('mac-return-after','mac'),paused=True)
    undo = job('mac-return-undo','undo',{'confirm':True})
    assert undo['result'].get('digest_match') is True
    expect_comparison('mac-return-undo-markers',mac_before,snapshot('mac-return-after-undo','mac'),paused=False)
    assert fixture('mac-return-undo-disturbed','mac')['checks']['files'] is False
    REPORT['P2'] = 'PASS'; save_report()
    # Refusal uses a genuinely exported newer-version Files fixture on this
    # disposable Linux source, not a fake CLI, patched archive or invented receipt.
    newer = fixture('linux-newer-package',DST,'newer')
    assert newer['row']['id']=='files'
    linux('linux-newer-export',DST,'wam backup export --key-file /home/wizard/mac-import.key -o /mnt/rig-shared/mac-backup-qa/newer-files.wizardbackup --json')
    # Undo Linux first: proves first-leg recovery and removes its restored markers.
    linux_undo('linux-success-undo',before)
    # The real CLI is needed here to require exit 3 AND the owner-visible message.
    # Target is now the Linux baseline (offered Files release older than 9999).
    linux('refusal-stop-files',DST,'wam app stop files')
    fixture('refusal-target-seed',DST,'refusal-baseline')
    refusal_before = fixture('refusal-before',DST)
    assert refusal_before['refused_scope'], 'Vacuous refused-app preservation'
    refusal_baseline = snapshot('refusal-baseline',DST)
    got = linux('newer-app-refusal',DST,'wam backup import /mnt/rig-shared/mac-backup-qa/newer-files.wizardbackup --key-file /home/wizard/mac-import.key --yes',check=False)
    message = got.stdout + got.stderr
    assert got.returncode == 3, 'Expected partial restore exit 3, got '+str(got.returncode)
    assert all(word in message for word in ('partly restored','not restored:','9999.0.0','newer than this box', 'Update this box, then restore again.','paused')), 'Unclear refusal message'
    receipt = fixture('refusal-receipt',DST,'receipt')
    assert receipt['ok'] is False and receipt['partial'] is True
    assert [r['id'] for r in receipt['refused']]==['files'], 'Wrong or additional app refused'
    assert receipt['refused'][0]['backup']['version']=='9999.0.0'
    assert receipt['refused'][0]['here']['version'] != '9999.0.0'
    refused = fixture('refusal-after',DST)
    assert refused['refused_scope']==refusal_before['refused_scope'], 'Refused Files data/wiring/logins changed'
    # Files app data is refused, but owner files and every OTHER named class must restore.
    require_markers(refused,paused=True,refused_app=True)
    # Explicitly prove the refused marker did not arrive; never count it as restored.
    assert refused['checks']['app_data'] is False
    write_json('newer-app-refusal-assertions', {'exit':got.returncode,'message_clear':True,
       'refused_scope_unchanged':True,'refused_app_marker_absent':True,
       'other_named_markers':{k:v for k,v in refused['checks'].items() if k!='app_data'}})
    linux_undo('linux-refusal-undo',refusal_baseline)
    REPORT['refusal']='PASS'; save_report()


def proof():
    global VM
    E.mkdir(parents=True, exist_ok=True); Q.mkdir(parents=True, exist_ok=True); Q.chmod(0o777)
    KEYS.mkdir(parents=True, exist_ok=True, mode=0o700)
    (M/'tmp').mkdir(exist_ok=True)
    REPORT['source_commit'] = (S/'SOURCE_SHA').read_text().strip()
    REPORT['free_bytes_before'] = free_check()
    # premerge builds and tests once; this driver consumes the exact candidate.
    candidate = S/'next/mac/dist/Wizard.app/Contents/MacOS/Wizard'
    assert candidate.is_file(), 'Native candidate must be built by premerge first'
    pre = json.loads((R/'evidence/premerge/result.json').read_text())
    assert pre.get('native_build') is True and pre.get('native_contract_tests') is True
    assert pre['source_pins']['try-wizard'] == REPORT['source_commit']
    assert pre['candidate']['sha256'] == sha_file(candidate), 'Stale native candidate'
    REPORT['build']='PASS'; REPORT['swift_tests']='PASS'
    for port in (48400,48430,48423):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port)) == 0:
                raise RuntimeError('Mac proof port is occupied; no other lane was touched')
    shutil.copyfile(S/'next/mac/backup/qa/guest-snapshot.py',Q/'guest-snapshot.py')
    for name in ('fixture.py','disturb.py'):
        shutil.copyfile(Path(__file__).parent/name,Q/name)
    guest_setup = Q/'setup'; guest_setup.mkdir(exist_ok=True)
    for f in ('server.py','backup_frontdoor.py'):
        shutil.copyfile(S/'next/guest/overlay/opt/wizard/setup'/f,guest_setup/f)
    # Start the same signed vmrun/kernel/initrd as macvm.sh, as a supervised child rather than nohup.
    # Only this CoW-clone and this private host files share are mutable.
    runtime = M/'runtime'; runtime.mkdir(exist_ok=True)
    disk = runtime/'disk.img'
    if disk.exists():
        raise RuntimeError('Refusing to reuse a previous mutable Mac disk')
    # Existing Mac Wizard: the accepted 0.4.0 release's used-install disk (same kernel/initrd sha as boot-0.3.0).
    # APFS clone only; the source disk is never opened for writing. (The 0.3.0 import-test.img was purged 19 Oct.)
    # Lane-owned read-only APFS clone (base/.keep): the release folder's used disk was removed by the 19 Oct test-image rule.
    base = (M / 'base/existing-mac-040.img').resolve()
    if not base.is_file():
        raise RuntimeError('Existing Mac Wizard base disk is missing')
    REPORT['mac_base_disk'] = str(base)
    run('mac-cow-clone', ['cp','-c', base, disk])
    disk.chmod(0o600)   # the base is read-only; its per-run clone is the writable Mac disk
    media = Q/'owner-files'; media.mkdir(exist_ok=True)
    (media/'MAC-NATIVE-OWNER-FILE.txt').write_text('Disposable native Mac owner file marker\n')
    console = (E/'mac-console.log').open('w')
    VM = subprocess.Popen([str(R/'mac-guest/vmrun'), '--kernel', str(R/'mac-guest/boot-0.3.0/vmlinux'),
        '--initrd', str(R/'mac-guest/boot-0.3.0/initrd'), '--disk', str(disk), '--cmdline','console=hvc0 root=/dev/vda rw wizard.dev=1',
        '--cpus','3','--mem','4096','--bridge','48400:9200','--bridge','48423:8923','--bridge','48430:8930',
        '--share','rig='+str(R/'shared'),'--share','wizard-files='+str(media), '--timeout','10800',
        '--console',str(E/'mac-console-guest.log')], env=ENV, stdout=console, stderr=subprocess.STDOUT)
    t = time.monotonic()
    while True:
        if VM.poll() is not None:
            raise RuntimeError('Mac guest runner exited')
        if time.monotonic()-t > 900:
            # the owner shell (8924) is an authenticated ingress on a set-up Wizard; record what answered
            with contextlib.suppress(Exception):
                mac('mac-readiness-diag', 'for u in http://127.0.0.1:8924/wizard/health http://127.0.0.1:8930/healthz; do echo "$u $(curl -s -o /dev/null -w %{http_code} $u)"; done; docker inspect runtipi --format "{{.State.Health.Status}}"; systemctl is-active wizard-setup wizard-ux-bridge local-proxy 2>&1', timeout=30, check=False)
            raise RuntimeError('Mac guest readiness timeout')
        try:
            text = mac('mac-readiness', 'test "$(docker inspect runtipi --format \'{{.State.Health.Status}}\')" = healthy && curl -fsS http://127.0.0.1:8930/healthz >/dev/null && echo \'"ok"\'', timeout=20, log=False)
            if '"ok"' in text:
                break
        except (OSError,RuntimeError):
            pass
        time.sleep(5)
    REPORT['mac_boot_seconds'] = round(time.monotonic()-t,1)
    mac('mac-admit-mounts', 'set -e; touch /var/lib/wizard-backup-disposable; mkdir -p /mnt/rig-shared; mountpoint -q /mnt/rig-shared || mount -t virtiofs rig /mnt/rig-shared; findmnt /home/wizard/runtipi/media; findmnt /var/lib/wizard/mac-files')
    REPORT['mac_wam_commit'] = install_wam('mac-wam-update', 'mac', MAC_WAM_SHA, MAC_WAM_BRANCH)
    assert REPORT['mac_wam_commit'] == MAC_WAM_SHA
    # Save the old setup files only inside this disposable disk, apply both new modules atomically before restart.
    mac('mac-frontdoor-update', 'set -e; install -m 644 /mnt/rig-shared/mac-backup-qa/setup/backup_frontdoor.py /opt/wizard/setup/backup_frontdoor.py; install -m 644 /mnt/rig-shared/mac-backup-qa/setup/server.py /opt/wizard/setup/server.py; systemctl restart wizard-setup.service')
    for _ in range(30):
        try:
            status, cap = request('capabilities')
            if status == 200 and cap.get('version') == 1:
                break
        except OSError:
            pass
        time.sleep(1)
    else:
        raise RuntimeError('New front-door capability did not become ready')
    write_json('mac-capabilities', cap)
    # Exercise actual native-only refusal before upload; no import side effect.
    refused = []
    for headers in ({}, {'X-Wizard-Backup':'wizardbackup-v1','Origin':'null'},
                    {'X-Wizard-Backup':'wizardbackup-v1','Origin':'http://127.0.0.1:48430'}):
        code, _ = request('export', method='POST', body={}, headers=headers)
        refused.append(code)
    assert refused == [403,403,403]
    assert request('activate', method='POST', body={'old_is_off':False})[0] == 400
    write_json('anti-web', {'codes':refused, 'activation_without_confirmation':400})
    if not cap['stored_key']:
        code, key_result = request('key/new', method='POST', body={})
        assert code == 200
        native_key = key_result.pop('recovery_key')
        store_key(KEYS/'mac-native.key', native_key)
        write_json('mac-key-created', key_result)
    else:
        native_key = secrets.token_urlsafe(32)
        store_key(KEYS/'mac-native.key', native_key)
        write_json('mac-key-created', {'used_passphrase':True, 'existing_key_not_rotated':True})
    mac('mac-refresh-files','/home/wizard/.local/bin/wam app update files',wizard=True)
    mac('mac-account-app','/home/wizard/.local/bin/wam install wizard-claude',wizard=True)
    mac('mac-registry-refresh','/home/wizard/.local/bin/wam apps --json',wizard=True)
    acceptance(native_key)
    journal = mac('mac-secret-audit','journalctl -u wizard-setup --no-pager -o cat',log=False)
    REPORT['key_never_in_frontdoor_journal'] = not any(s in journal for s in SECRET_VALUES)
    assert REPORT['key_never_in_frontdoor_journal'], 'Secret detected; journal suppressed'
    REPORT['gui'] = 'NOT_RUN: HTTP/CLI acceptance; native GUI is a separate gate'
    REPORT['direction'] = 'Mac→Linux→Mac'


def cleanup():
    global VM
    print('CLEANUP',flush=True)
    if VM is not None:
        with contextlib.suppress(Exception):
            mac('mac-poweroff','systemctl poweroff',timeout=20,check=False,log=False)
        try:
            VM.wait(timeout=60)
        except subprocess.TimeoutExpired:
            VM.terminate()
            try: VM.wait(timeout=10)
            except subprocess.TimeoutExpired: VM.kill(); VM.wait(timeout=10)
    destroyed = {}
    for name in reversed(CREATED):
        p = subprocess.run([str(RIG),'destroy',name],env=ENV,capture_output=True,text=True,timeout=240)
        (E/(name+'-cleanup.log')).write_text(safe(p.stdout+p.stderr))
        destroyed[name] = p.returncode == 0
    (M/'runtime/disk.img').unlink(missing_ok=True)
    for file in ('mac-source.key','mac-native.key'):
        (KEYS/file).unlink(missing_ok=True)
    if Q.exists():
        shutil.rmtree(Q)
    REPORT['free_bytes_after'] = shutil.disk_usage(R).free
    REPORT['cleanup'] = {'guests_destroyed': destroyed, 'mac_disk_removed': not (M/'runtime/disk.img').exists(),
                         'keys_removed': not any((KEYS/f).exists() for f in ('mac-source.key','mac-native.key')),
                         'staging_removed': not Q.exists()}
    save_report()


def accepted(report):
    cleanup = report.get('cleanup', {})
    return (not report.get('error')
            and all(report.get(k)=='PASS' for k in ('build','swift_tests','P1','P2','refusal'))
            and report.get('key_never_in_frontdoor_journal') is True
            and all(cleanup.get(k) is True for k in ('mac_disk_removed','keys_removed','staging_removed'))
            and all(cleanup.get('guests_destroyed',{}).values()))


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise InterruptedError('Acceptance worker interrupted; cleaning owned guests')
    signal.signal(signal.SIGTERM, interrupted)
    if '--dry-run' in sys.argv:
        os.execv(sys.executable,[sys.executable,str(Path(__file__).with_name('test_harness.py'))])
    E.mkdir(parents=True,exist_ok=True)
    try:
        proof()
    except BaseException as e:
        for phase in ('P1', 'P2'):
            if REPORT.get(phase) == 'RUNNING':
                REPORT[phase] = 'FAIL'
        REPORT['error'] = safe(str(e))
        (E/'failure.log').write_text(safe(traceback.format_exc()))
        print('FAILED:',safe(str(e)),flush=True)
    finally:
        cleanup()
    REPORT['success'] = accepted(REPORT)
    save_report()
    print(json.dumps(REPORT,indent=2),flush=True)
    sys.exit(0 if REPORT['success'] else 1)
