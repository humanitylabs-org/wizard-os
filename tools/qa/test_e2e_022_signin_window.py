#!/usr/bin/env python3
"""Regression: owner relay in front of the real AI Accounts 0.1.1 server.py.

Usage: AI_ACCOUNTS_PKG=<checkout of oscarhenrycollins/ai-accounts@ddc9dc5> \
       python3 tools/qa/test_e2e_022_signin_window.py
The package Claude CLI path points at a missing file: no sign-in can start.
"""
import http.client, importlib.util, json, os, pathlib, subprocess, sys, tempfile, threading, time
from http.server import ThreadingHTTPServer

here = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location('window', here / 'e2e_022_signin_window.py')
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
pkg = pathlib.Path(os.environ['AI_ACCOUNTS_PKG'])
work = pathlib.Path(tempfile.mkdtemp()); (work / 'claude').mkdir()
UP, RELAY = 18796, 18797
ORIGIN, OWNER = 'https://node.example.ts.net:18449', 'Owner@Example'
server = subprocess.Popen([sys.executable, str(pkg / 'server.py')], env={**os.environ,
    'AI_ACCOUNTS_PORT': str(UP), 'AI_ACCOUNTS_BIND': '127.0.0.1', 'AI_ACCOUNTS_CLAUDE': str(work / 'none'),
    'AI_ACCOUNTS_CLAUDE_DIR': str(work / 'claude'), 'AI_ACCOUNTS_WORK_DIR': str(work / 'w')},
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w.Relay.owner, w.Relay.origin, w.Relay.upstream, w.Relay.log_path = 'owner@example', ORIGIN, UP, str(work / 'relay.jsonl')
relay = ThreadingHTTPServer(('127.0.0.1', RELAY), w.Relay)
threading.Thread(target=relay.serve_forever, daemon=True).start()

def req(path, method='GET', headers=None, body=None):
    c = http.client.HTTPConnection('127.0.0.1', RELAY, timeout=20)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse(); return r.status, r.read(), dict(r.getheaders())

try:
    for _ in range(50):
        try:
            if req('/', headers={'Tailscale-User-Login': OWNER})[0] == 200: break
        except OSError: pass
        time.sleep(0.1)
    own = {'Tailscale-User-Login': OWNER}
    post = {**own, 'Origin': ORIGIN, 'Content-Type': 'application/json'}
    cases = {
        'owner_page': (req('/', headers=own)[0], 200),
        'owner_assets': (req('/app.js', headers=own)[0], 200),
        'owner_status': (req('/api/accounts', headers=own)[0], 200),
        'no_identity': (req('/')[0], 403),
        'other_identity': (req('/', headers={'Tailscale-User-Login': 'other@example'})[0], 403),
        'mcp_hidden': (req('/mcp', 'POST', post, b'{}')[0], 404),
        'skill_hidden': (req('/SKILL.md', headers=own)[0], 404),
        'health_hidden': (req('/health', headers=own)[0], 404),
        'cross_origin_post': (req('/api/claude/cancel', 'POST', {**post, 'Origin': 'https://evil.example'}, b'{}')[0], 403),
        'no_origin_post': (req('/api/claude/cancel', 'POST', {**own, 'Content-Type': 'application/json'}, b'{}')[0], 403),
        'cross_site_fetch': (req('/api/claude/cancel', 'POST', {**post, 'Sec-Fetch-Site': 'cross-site'}, b'{}')[0], 403),
        # Same-origin POST reaches the package, whose Origin==Host check must pass via the relay.
        'same_origin_post': (req('/api/claude/cancel', 'POST', post, b'{}')[0], 200),
        'too_large': (req('/api/claude/code', 'POST', post, b'x' * 5000)[0], 413),
        'put_refused': (req('/', 'PUT', own, b'')[0], 405),
    }
    bad = {k: v for k, v in cases.items() if v[0] != v[1]}
    assert not bad, bad
    status, _, headers = req('/?code=secret-query', headers=own)
    log = (work / 'relay.jsonl').read_text()
    assert 'secret-query' not in log and 'Owner@Example' not in log, 'relay log leaked query or identity'
    assert headers.get('Cache-Control') == 'no-store'
    # Serve-handler ownership helpers.
    state = {'https_port': 18449, 'relay_port': 18450, 'node': 'node.example.ts.net'}
    other = {'TCP': {'443': {'HTTPS': True}}, 'Web': {'node.example.ts.net:443': {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:1'}}}}}
    ours = json.loads(json.dumps(other)); ours['TCP']['18449'] = {'HTTPS': True}
    ours['Web']['node.example.ts.net:18449'] = {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:18450'}}}
    assert w.serve_handler_ours(ours, state) and not w.serve_handler_ours(other, state)
    assert w.without_port(ours, state) == other
    foreign = json.loads(json.dumps(ours)); foreign['Web']['node.example.ts.net:18449']['Handlers']['/']['Proxy'] = 'http://127.0.0.1:9'
    assert not w.serve_handler_ours(foreign, state), 'must never remove a handler it does not own'
    print('PASS', len(cases) + 6, 'relay checks')
finally:
    relay.shutdown(); server.terminate(); server.wait()
