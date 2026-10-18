#!/usr/bin/env python3
"""Read-only agent-bridge diagnosis for one owned release-0.2.2 test guest.

Run through the Thales heavy queue. Starts/stops only the selected stopped guest
and sends no chat. It reads:
  - Hermes config.yaml: mcp_servers names/urls and skills.external_dirs (no headers, no env),
  - the Agent Service container's non-secret WIZARD_* settings and its mounts,
  - the apps.json the Agent Service reads: app ids, provides and MCP urls,
  - reachability of each app MCP url from inside the Agent Service container,
  - which DeFleur/Files paths the Hermes engine container can see,
  - the tool calls made in one Hermes session (names plus clipped arguments),
  - the Agent Service's agent-bridge log lines.
Values of secret-named keys are never printed.
"""
import argparse, json, os, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

GUEST = r'''
import json, re, subprocess, sys, sqlite3, getpass
session_id = sys.argv[1]
SECRET = re.compile(r'(?i)token|secret|password|key|authorization|cookie|credential|bearer')
def sh(argv, timeout=120):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr
def docker(*a, timeout=120): return sh(['sudo', '-n', 'docker', *a], timeout)
out = {}
names = docker('ps', '--format', '{{.Names}}')[1].split()
def one(part):
    m = [n for n in names if part in n]
    return m[0] if m else None
engine, service = one('hermes-agent-engine'), one('agent-service')
home = None
if engine:
    _info = json.loads(docker('inspect', engine)[1])[0]
    home = next((m['Source'] for m in _info['Mounts'] if m['Destination'] == '/opt/data'), None)
home = home or '/home/%s/runtipi/app-data/wizardapps/hermes-agent/data' % getpass.getuser()
out['hermes_home'] = home
# Hermes config: only mcp_servers name/url/command and skills.external_dirs.
code, cfg_py, err = sh(['sudo', '-n', 'python3', '-c', """
import json, sys, yaml
c = yaml.safe_load(open(sys.argv[1])) or {}
m = c.get('mcp_servers') or {}
print(json.dumps({'mcp_servers': {k: {'url': (v or {}).get('url'), 'command': (v or {}).get('command'),
     'enabled': (v or {}).get('enabled', True), 'has_headers': bool((v or {}).get('headers'))} for k, v in m.items()},
     'skills_external_dirs': (c.get('skills') or {}).get('external_dirs'),
     'plugins': {k: v for k, v in (c.get('plugins') or {}).items() if k in ('enabled', 'disabled')},
     'model': {k: (c.get('model') or {}).get(k) for k in ('provider', 'default')} if isinstance(c.get('model'), dict) else c.get('model')}))
""", home + '/config.yaml'])
out['hermes_config'] = json.loads(cfg_py) if code == 0 else {'error': err[-400:]}
# Agent Service settings and mounts.
if service:
    info = json.loads(docker('inspect', service)[1])[0]
    env = dict(e.split('=', 1) for e in info['Config'].get('Env', []) if '=' in e)
    out['service_env'] = {k: ('[set]' if SECRET.search(k) else v[:200]) for k, v in env.items() if k.startswith(('WIZARD_', 'HERMES_'))}
    out['service_mounts'] = [{'src': m['Source'], 'dst': m['Destination'], 'rw': m['RW']} for m in info['Mounts']]
    apps_path = env.get('WIZARD_APPS_JSON_PATH') or ''
    host_apps = next((m['Source'] for m in info['Mounts'] if m['Destination'] == '/wizard-os'), None)
    out['service_user'] = docker('exec', service, 'id')[1].strip()
    out['apps_json_stat'] = sh(['sudo', '-n', 'stat', '-c', '%a %U:%G %u:%g %y %n', host_apps + '/apps.json', host_apps])[1].strip() if host_apps else None
    out['apps_dir_listing'] = sh(['sudo', '-n', 'ls', '-la', host_apps])[1][-1500:] if host_apps else None
    code, txt, err = sh(['sudo', '-n', 'cat', host_apps + '/apps.json']) if host_apps else (1, '', 'no mount')
    try:
        reg = json.loads(txt)
        out['service_apps'] = [{'id': a.get('id'), 'status': a.get('status'), 'provides': a.get('provides'),
                                'mcp': {k: (a.get('mcp') or {}).get(k) for k in ('url', 'internal')}} for a in reg.get('apps', [])]
    except Exception:
        out['service_apps'] = {'path': apps_path, 'raw_head': txt[:300], 'err': err[-200:]}
    reach = {}
    for a in out['service_apps'] if isinstance(out['service_apps'], list) else []:
        for k in ('internal', 'url'):
            u = a['mcp'].get(k)
            if u:
                code, so, se = docker('exec', service, 'node', '-e',
                    "fetch(process.argv[1],{method:'POST',headers:{'content-type':'application/json',accept:'application/json, text/event-stream'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'diag',version:'0'}}}),signal:AbortSignal.timeout(15000)}).then(r=>console.log(r.status)).catch(e=>console.log('ERR '+(e.cause?.code||e.message)))", u, timeout=60)
                reach['%s:%s' % (a['id'], k)] = (so or se).strip()[:120]
    out['service_mcp_reach'] = reach
    code, logs, lerr = docker('logs', '--tail', '2000', service)
    out['service_bridge_log'] = [l[:300] for l in (logs + lerr).splitlines() if 'agent-bridge' in l or 'apps.json' in l][-40:]
# What the Hermes engine container itself can see.
if engine:
    info = json.loads(docker('inspect', engine)[1])[0]
    out['engine_mounts'] = [{'src': m['Source'], 'dst': m['Destination'], 'rw': m['RW']} for m in info['Mounts']]
    out['engine_networks'] = sorted(info['NetworkSettings']['Networks'])
    code, so, se = docker('exec', '-u', '1000:1000', engine, 'sh', '-c',
        'ls -d /opt/data/skills/wizard-job-* /opt/wizard-os/skills 2>&1 | head -20; echo ---; ls /media /opt/data/media 2>&1 | head')
    out['engine_view'] = (so + se)[-1500:]
if service:
    info = json.loads(docker('inspect', service)[1])[0]
    out['service_networks'] = sorted(info['NetworkSettings']['Networks'])
# Tool calls in the session (names + clipped args).
code, so, se = sh(['sudo', '-n', 'python3', '-c', """
import json, sqlite3, sys
db = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)
cols = [r[1] for r in db.execute('pragma table_info(messages)')]
rows = db.execute('select * from messages where session_id=? order by rowid', (sys.argv[2],)).fetchall()
res = []
for r in rows:
    d = dict(zip(cols, r))
    tc = d.get('tool_calls')
    item = {'role': d.get('role'), 'tool_name': d.get('tool_name')}
    if tc:
        try:
            item['calls'] = [{'name': (c.get('function') or {}).get('name'), 'args': str((c.get('function') or {}).get('arguments'))[:300]} for c in json.loads(tc)]
        except Exception:
            item['calls_raw'] = str(tc)[:300]
    if d.get('role') == 'tool':
        item['result'] = str(d.get('content'))[:400]
    res.append(item)
print(json.dumps(res))
""", home + '/state.db', session_id])
out['session_tool_calls'] = json.loads(so) if code == 0 else {'error': se[-400:]}
print(json.dumps(out))
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--vm', choices=['fresh-022-candidate-amd64', 'alongside-022-amd64'], required=True)
    ap.add_argument('--session-id', required=True)
    a = ap.parse_args()
    root = a.root.resolve()
    assert platform.system() == 'Darwin' and str(root).startswith('/Volumes/ThalesMedia/')
    os.umask(0o077)
    ev = root / 'evidence' / ('bridge-diag-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
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
        # Give the app containers time to come up before reading them.
        subprocess.run(['limactl', 'shell', a.vm, '--', 'sleep', '90'], env=env, timeout=200)
        p = subprocess.run(['limactl', 'shell', '--workdir=/', a.vm, '--', 'python3', '-', a.session_id],
                           env=env, input=GUEST, text=True, capture_output=True, timeout=900)
        (ev / 'bridge-private.json').write_text(p.stdout)
        receipt['guest_exit'] = p.returncode
        if p.returncode == 0:
            receipt['diag'] = json.loads(p.stdout)
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
