#!/usr/bin/env python3
"""Card-5 box-peer gate, end to end on real processes (wizard-os #386). Synthetic data; loopback only.

  run.py <mode: base|candidate> <out.json>

Per mode:
  WAM (real cli.write_registry via tools/browser_admission_fixture.py) installs Transcriber, Browser and Voice from
  their own wizard.md + runtipi compose, so WAM decides from the real recipes whether to mint gateway keys.
  Real listeners: the Transcriber and Browser MCP fronts (mcp/front.py + tools.py, as inline.py assembles them) and
  the real Voice FastAPI server; Browser's upstream is a real chrome-headless-shell; Transcriber's engine is a stub
  OpenAI-compatible /v1/models (speaches is not pulled). The real Agent Service gateway (server/agent-bridge.mjs)
  serves /wizard/mcp and proxies to them from apps.json + grants/agent-service.json.
  Probes: the agent's path through the gateway, and box peers hitting the listeners directly.
"""
import hashlib
import http.client
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
S = HERE.parent
MODE, OUT = sys.argv[1], Path(sys.argv[2])
CK = {  # app checkouts per mode (worktrees prepared by the caller)
    'wam': S / ('wam-base' if MODE == 'base' else 'wizard-app-manager'),
    'transcriber': S / ('transcriber-base' if MODE == 'base' else 'transcriber'),
    'browser': S / ('browser-base' if MODE == 'base' else 'browser'),
    'voice': S / ('voice-base' if MODE == 'base' else 'wizard-voice-service'),
}
SVC = S / 'wizard-agent-service'   # Service #316 head; unchanged in this work
PY_WAM = os.path.expanduser('~/.hermes/cache/scratch/bt-files/venv/bin/python')
PY_VOICE = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'vvenv/bin/python')
CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell')
PW = os.path.expanduser('~/github_repos/aiwizards.com/node_modules/playwright-core')
procs, results = [], []


def free():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait(port, n=200):
    for _ in range(n):
        try:
            socket.create_connection(('127.0.0.1', port), timeout=0.2).close()
            return
        except OSError:
            time.sleep(0.1)
    raise SystemExit(f'port {port} never opened')


def start(args, env=None, cwd=None, log=None):
    p = subprocess.Popen(args, env={**os.environ, **(env or {})}, cwd=cwd,
                         stdout=open(log, 'w') if log else subprocess.DEVNULL, stderr=subprocess.STDOUT)
    procs.append(p)
    return p


def req(port, path, method='GET', headers=None, body=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=60)
    try:
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        return r.status, r.read()
    except (ConnectionError, OSError) as e:
        return 0, str(e).encode()
    finally:
        c.close()


def mcp_list(port, headers=None):
    b = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}).encode()
    return req(port, '/mcp', 'POST', {'Content-Type': 'application/json', **(headers or {})}, b)[0]


def ws_upgrade(port, path, extra=None):
    s = socket.create_connection(('127.0.0.1', port), timeout=10)
    h = {'Upgrade': 'websocket', 'Connection': 'Upgrade', 'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
         'Sec-WebSocket-Version': '13', **(extra or {})}
    s.sendall((f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n' + ''.join(f'{k}: {v}\r\n' for k, v in h.items())
               + '\r\n').encode())
    line = s.recv(4096).split(b'\r\n', 1)[0].decode()
    s.close()
    return int(line.split(' ')[1]) if line.startswith('HTTP/') else 0


def record(who, what, got, want_candidate):
    results.append({'caller': who, 'request': what, 'status': got, 'expect_candidate': want_candidate})


def env_file(app):
    f = D / 'runtipi' / 'user-config' / 'wizardapps' / app / 'app.env'
    return dict(l.split('=', 1) for l in f.read_text().splitlines() if '=' in l) if f.is_file() else {}


D = Path(tempfile.mkdtemp(prefix='bt5-'))
try:
    ports = {k: free() for k in ('engine', 'chrome', 'transcriber', 'browser', 'voice', 'gateway')}
    # -- stub Transcriber engine (OpenAI-compatible model list) + a page for the browser to render
    stub = D / 'stub.py'
    stub.write_text('''import json,sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/page"):
            b=b"<html><head><title>Card five synthetic page</title></head><body>Rendered by the box browser</body></html>";t="text/html"
        else:
            b=json.dumps({"data":[{"id":"stub-whisper"}]}).encode();t="application/json"
        self.send_response(200);self.send_header("Content-Type",t);self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def log_message(self,*a): pass
ThreadingHTTPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()
''')
    start([sys.executable, str(stub), str(ports['engine'])])
    start([CHROME, '--headless', f'--remote-debugging-port={ports["chrome"]}', '--remote-debugging-address=127.0.0.1',
           f'--user-data-dir={D / "chrome"}', '--no-first-run', '--no-sandbox'])
    wait(ports['engine']); wait(ports['chrome'])

    # -- WAM installs the three recipes (real registry write with the boundary on)
    fixture = CK['wam'] / 'tools' / 'browser_admission_fixture.py'
    ids = {'transcriber': 'transcriber', 'browser': 'browser', 'voice': 'wizard-voice-service'}
    for k, app in ids.items():
        args = [PY_WAM, str(fixture), str(D), 'install', app, '--repo', f'x/{app}', '--port', str(ports[k]),
                '--wizard-md', str(CK[k] / 'wizard.md')]
        if '--compose' in fixture.read_text():
            args += ['--compose', str(CK[k] / 'runtipi' / 'docker-compose.yml')]
        else:   # base WAM has no --compose: copy the recipe in, then rewrite the registry
            pass
        subprocess.run(args, check=True, capture_output=True)
        if '--compose' not in fixture.read_text():
            shutil.copy(CK[k] / 'runtipi' / 'docker-compose.yml', D / 'runtipi/apps/wizardapps' / app / 'docker-compose.yml')
            subprocess.run([PY_WAM, str(fixture), str(D), 'write', app], check=True, capture_output=True)
    home = D / 'home'
    gw_file = home / 'grants' / 'agent-service.json'
    wam_state = {
        'gateway_file_mode': oct(gw_file.stat().st_mode & 0o777) if gw_file.exists() else None,
        'gateway_outgoing_apps': sorted(json.loads(gw_file.read_text())['outgoing']) if gw_file.exists() else [],
        'app_env_keys': {app: sorted(env_file(app)) for app in ids.values()},
        'apps_json_carries_a_key': any(v and v in (home / 'apps.json').read_text()
                                       for v in (json.loads(gw_file.read_text())['outgoing'].values() if gw_file.exists() else [])),
    }

    # -- a granted app's key for Browser DevTools (as App Manager writes it: incoming sha256 row in /wizard/grants.json)
    app_key = secrets.token_hex(32)
    bgrants = D / 'browser-grants.json'
    bgrants.write_text(json.dumps({'outgoing': {}, 'incoming': [{'from': 'defleur-video', 'sha256': hashlib.sha256(app_key.encode()).hexdigest()}],
                                   'enforce': True}))

    # -- listeners, with the env WAM wrote (app.env) and the compose's own fixed env
    def front(k, app, upstream, extra):
        src = (CK[k] / 'mcp/front.py').read_text() + '\n\n' + (CK[k] / 'mcp/tools.py').read_text() + \
            '\n\nif __name__ == "__main__":\n    asyncio.run(main())\n'
        f = D / f'{app}-front.py'
        f.write_text(src)
        env = {'WIZARD_APP': app, 'FRONT_PORT': str(ports[k]), 'UPSTREAM_HOST': '127.0.0.1', 'UPSTREAM_PORT': str(upstream),
               'TRANSCRIBER_MODEL': 'stub-whisper', **extra, **env_file(app)}
        start([sys.executable, str(f)], env, log=D / f'{app}.log')
    front('transcriber', 'transcriber', ports['engine'], {})
    compose_b = (CK['browser'] / 'runtipi/docker-compose.yml').read_text()
    front('browser', 'browser', ports['chrome'], {'WIZARD_GRANTS_FILE': str(bgrants),
                                                   **({'WIZARD_PEER_GATE': 'require'} if 'WIZARD_PEER_GATE: require' in compose_b else {})})
    vcfg = D / 'voice-config.yaml'
    shutil.copy(CK['voice'] / 'packaging/default-config.yaml', vcfg)
    (D / 'jobs').mkdir()
    start([PY_VOICE, '-m', 'uvicorn', 'server:app', '--host', '127.0.0.1', '--port', str(ports['voice']), '--no-access-log'],
          {'WIZARD_VOICE_CONFIG': str(vcfg), 'WIZARD_VOICE_DATA_DIR': str(D / 'jobs'), 'WIZARD_VOICE_ENV': '/dev/null',
           'WIZARD_VOICE_ALLOWED_HOSTS': '127.0.0.1,localhost', **env_file('wizard-voice-service')},
          cwd=CK['voice'], log=D / 'voice.log')
    token = secrets.token_urlsafe(24)
    start(['node', str(HERE / 'gateway.mjs'), str(SVC), str(home), str(ports['gateway']), token], log=D / 'gateway.log')
    for k in ('transcriber', 'browser', 'voice', 'gateway'):
        wait(ports[k])

    # -- 1. the agent's legitimate path: Hermes -> gateway /wizard/mcp -> app /mcp
    def gw(method, params, sid=None, i=1):
        h = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
        if sid:
            h['Mcp-Session-Id'] = sid
        c = http.client.HTTPConnection('127.0.0.1', ports['gateway'], timeout=120)
        c.request('POST', '/wizard/mcp', json.dumps({'jsonrpc': '2.0', 'id': i, 'method': method, 'params': params}), h)
        r = c.getresponse()
        body = json.loads(r.read() or b'{}')
        return r.getheader('Mcp-Session-Id'), body
    sid, _ = gw('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'harness'}})
    _, listed = gw('tools/list', {}, sid, 2)
    names = sorted(t['name'] for t in listed['result']['tools'])
    agent = {}
    for label, tool, args in (('transcriber', 'transcriber__transcriber_status', {}),
                              ('browser', 'browser__read_page', {'url': f'http://127.0.0.1:{ports["engine"]}/page'}),
                              ('voice', 'wizard_voice_service__voice_status', {})):
        _, r = gw('tools/call', {'name': tool, 'arguments': args}, sid, 3)
        res = r.get('result') or {}
        text = ''.join(c.get('text', '') for c in res.get('content', []))
        ok = not res.get('isError') and bool(text) and ('Card five synthetic page' in text if label == 'browser' else True)
        agent[label] = {'tool': tool, 'ok': ok, 'excerpt': text[:160]}
        record('agent via gateway', f'tools/call {tool}', 'ok' if ok else 'FAILED', 'ok')
    gw_tools = {k: any(n.startswith(p) for n in names) for k, p in
                (('transcriber', 'transcriber__'), ('browser', 'browser__'), ('voice', 'wizard_voice_service__'))}

    # -- 2. box peers straight at the listeners (another process / container on the box)
    for k in ('transcriber', 'browser', 'voice'):
        p = ports[k]
        record('box peer, no key', f'{k} POST /mcp tools/list', mcp_list(p), 403)
        record('box peer, guessed key', f'{k} POST /mcp', mcp_list(p, {'X-Wizard-Grant': secrets.token_hex(32)}), 403)
        record('browser page (Origin)', f'{k} POST /mcp', mcp_list(p, {'Origin': 'http://127.0.0.1'}), 403)
        record('tailnet-proxied (Tailscale-User-Login)', f'{k} POST /mcp', mcp_list(p, {'Tailscale-User-Login': 'owner@example.com'}), 403)
    gwkey = json.loads(gw_file.read_text())['outgoing'].get('browser') if gw_file.exists() else None
    record('gateway key + Origin', 'browser POST /mcp', mcp_list(ports['browser'], {'X-Wizard-Grant': gwkey or 'none', 'Origin': 'null'}), 403)
    b = ports['browser']
    record('box peer, no key', 'browser GET /json/version (DevTools)', req(b, '/json/version')[0], 403)
    record('box peer, no key', 'browser GET /json/list (DevTools)', req(b, '/json/list')[0], 403)
    record('box peer, no key', 'browser WS /devtools/browser (CDP upgrade)', ws_upgrade(b, '/devtools/browser/x'), 403)
    record('granted app (defleur-video key)', 'browser GET /json/version (DevTools)', req(b, '/json/version', headers={'X-Wizard-Grant': app_key})[0], 200)
    t = ports['transcriber']
    record('box peer, no key (grants not enforced: log+serve)', 'transcriber GET /v1/models (engine API)', req(t, '/v1/models')[0], 200)
    record('browser page (Origin)', 'transcriber GET /v1/models (engine API)', req(t, '/v1/models', headers={'Origin': 'http://127.0.0.1'})[0], 403)
    record('box probe', 'transcriber GET /health', req(t, '/health')[0], 200)

    # -- 3. a real CDP client (Playwright connectOverCDP) as a granted app vs a keyless peer
    pw = subprocess.run(['node', '-e', '''
const { chromium } = require(process.argv[1]); const base = process.argv[2], key = process.argv[3], page = process.argv[4];
(async () => {
  const out = {};
  for (const [label, headers] of [['granted', { 'X-Wizard-Grant': key }], ['keyless', {}]]) {
    try { const b = await chromium.connectOverCDP(base, { headers, timeout: 8000 }); const p = await b.newPage();
          await p.goto(page); out[label] = 'connected; title=' + await p.title(); await p.close(); await b.close() }
    catch (e) { out[label] = 'refused: ' + String(e.message).split('\\n')[0].slice(0, 120) }
  }
  console.log(JSON.stringify(out))
})()''', PW, f'http://127.0.0.1:{b}', app_key, f'http://127.0.0.1:{ports["engine"]}/page'],
        capture_output=True, text=True, timeout=90)
    cdp = json.loads(pw.stdout.strip().splitlines()[-1]) if pw.stdout.strip() else {'error': pw.stderr[-300:]}
    record('granted app via Playwright connectOverCDP', 'browser CDP session', 'connected' if str(cdp.get('granted', '')).startswith('connected') else 'refused', 'connected')
    record('keyless peer via Playwright connectOverCDP', 'browser CDP session', 'connected' if str(cdp.get('keyless', '')).startswith('connected') else 'refused', 'refused')

    upstream_saw_key = 'x-wizard-grant' in (D / 'browser.log').read_text().lower()
    OUT.write_text(json.dumps({'mode': MODE, 'wam': wam_state, 'gateway_tools_visible': gw_tools, 'agent_calls': agent,
                               'cdp': cdp, 'results': results}, indent=2) + '\n')
    print(json.dumps({'mode': MODE, 'wam': wam_state, 'gateway_tools_visible': gw_tools}, indent=1))
    for r in results:
        print(f"{r['caller'][:44]:<46}{r['request'][:46]:<48}{r['status']!s:<10} (candidate expects {r['expect_candidate']})")
finally:
    for p in procs:
        p.kill()
    for p in procs:
        p.wait()
    shutil.rmtree(D, ignore_errors=True)
