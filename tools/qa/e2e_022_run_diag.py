#!/usr/bin/env python3
"""Diagnose a failed Hermes run in one owned release-0.2.2 test guest.

Run through the Thales heavy queue. Starts/stops only the selected stopped
guest. Reads the run/session through the installed shell API and the error
lines of the Hermes and Agent Service container logs. No sign-in, no new run,
no credential files. Lines are redacted for token-like strings; the full
filtered output stays in a private evidence directory.
"""
import argparse, json, os, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

GUEST = r'''
import json, re, subprocess, sys, urllib.request
run_id, session_id = sys.argv[1], sys.argv[2]
SECRET = re.compile(r'(sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S+|(?i:token|key|secret|password|authorization)["\']?\s*[:=]\s*["\']?[^\s"\',]{6,})')
KEEP = re.compile(r'(?i)error|exception|traceback|failed|refused|denied|not found|unauthori|forbidden|timeout|directsdk|claude|provider|model')
def red(s): return SECRET.sub('[redacted]', s)[:600]
def get(path):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8796' + path, timeout=30) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, {'body': red(e.read().decode(errors='replace'))}
    except Exception as e:
        return None, {'error': type(e).__name__}
def docker(*a):
    return subprocess.run(['sudo', '-n', 'docker', *a], capture_output=True, text=True, timeout=120)
out = {}
code, run = get('/wizard/hermes/v1/runs/' + run_id)
out['run'] = {'http': code, 'data': json.loads(red(json.dumps(run)))}
code, sess = get('/wizard/hermes/api/sessions/' + session_id)
out['session'] = {'http': code, 'data': json.loads(red(json.dumps(sess)))}
code, msgs = get('/wizard/hermes/api/sessions/%s/messages?order=oldest&limit=50&offset=0&include_compacted=true&view=wizard' % session_id)
rows = msgs.get('data') or msgs.get('messages') or []
out['messages'] = [{'role': m.get('role'), 'text': red(m['content'] if isinstance(m.get('content'), str) else json.dumps(m.get('content')))[:400]} for m in rows]
names = docker('ps', '-a', '--format', '{{.Names}}').stdout.split()
logs = {}
for n in names:
    if any(k in n for k in ('hermes-agent', 'agent-service', 'wizard-ux', 'ai-accounts')):
        p = docker('logs', '--tail', '600', n)
        lines = (p.stdout + '\n' + p.stderr).splitlines()
        logs[n] = [red(l) for l in lines if KEEP.search(l)][-60:]
out['container_logs'] = logs
home = '/home/' + __import__('getpass').getuser() + '/runtipi/app-data/wizardapps/hermes-agent/data/logs'
p = subprocess.run(['sudo', '-n', 'sh', '-c', 'for f in %s/*.log; do echo "== $f"; tail -n 400 "$f"; done' % home], capture_output=True, text=True, timeout=60)
out['hermes_logs'] = [red(l) for l in p.stdout.splitlines() if l.startswith('==') or KEEP.search(l)][-120:]
print(json.dumps(out))
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--vm', choices=['fresh-022-candidate-amd64', 'alongside-022-amd64'], required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--session-id', required=True)
    a = ap.parse_args()
    root = a.root.resolve()
    assert platform.system() == 'Darwin' and str(root).startswith('/Volumes/ThalesMedia/')
    os.umask(0o077)
    ev = root / 'evidence' / ('run-diag-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    ev.mkdir(parents=True)
    env = {**os.environ, 'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',
           'LIMA_HOME': str(root / 'lima'), 'LIMA_CACHE_HOME': str(root / 'lima-cache')}
    vms = {json.loads(l)['name']: json.loads(l) for l in
           subprocess.check_output(['limactl', 'list', '--json'], env=env, text=True).splitlines()}
    assert vms[a.vm]['status'] == 'Stopped', 'guest must begin stopped'
    receipt = {'host': platform.node(), 'vm': a.vm, 'argv': sys.argv,
               'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}
    try:
        with (ev / 'start.log').open('w') as f:
            subprocess.run(['limactl', 'start', '--tty=false', a.vm], env=env, check=True, stdout=f,
                           stderr=subprocess.STDOUT, timeout=420)
        p = subprocess.run(['limactl', 'shell', '--workdir=/', a.vm, '--', 'python3', '-', a.run_id, a.session_id],
                           env=env, input=GUEST, text=True, capture_output=True, timeout=600)
        (ev / 'diag-private.json').write_text(p.stdout)
        receipt['guest_exit'] = p.returncode
        if p.returncode == 0:
            d = json.loads(p.stdout)
            receipt['run'] = d['run']
            receipt['messages'] = d['messages']
            receipt['log_tails'] = {k: v[-15:] for k, v in d['container_logs'].items()}
            receipt['hermes_log_tail'] = d['hermes_logs'][-40:]
        else:
            receipt['guest_stderr_tail'] = p.stderr[-800:]
    finally:
        with (ev / 'stop.log').open('w') as f:
            subprocess.run(['limactl', 'stop', a.vm], env=env, stdout=f, stderr=subprocess.STDOUT, timeout=240)
        (ev / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=1), flush=True)
    sys.exit(0 if receipt.get('guest_exit') == 0 else 1)


if __name__ == '__main__':
    main()
