#!/usr/bin/env python3
"""Regression: preflight guest code against the real AI Accounts 0.1.1 server.py.

Usage: AI_ACCOUNTS_PKG=<checkout of oscarhenrycollins/ai-accounts@ddc9dc5> python3 tools/qa/test_e2e_022_signin_preflight.py
The package Claude CLI path points at a missing file, so no real sign-in state is read.
"""
import ast, json, os, pathlib, subprocess, sys, time, urllib.request
here = pathlib.Path(__file__).parent
import tempfile
fixture = here / 'signin_preflight_fixture'
pkg = pathlib.Path(os.environ['AI_ACCOUNTS_PKG'])
work = pathlib.Path(tempfile.mkdtemp())
(work / 'claude').mkdir()
src = here / 'e2e_022_signin_preflight.py'
tree = ast.parse(src.read_text())
guest = next(ast.literal_eval(x.value) for x in tree.body if isinstance(x, ast.Assign)
             and any(getattr(t, 'id', '') == 'GUEST' for t in x.targets))
for gate in ('', 'test-gate'):
    env = {**os.environ, 'HOME': str(work / 'home'), 'AI_ACCOUNTS_PORT': '18795',
           'AI_ACCOUNTS_PASSWORD': gate, 'CLAUDE_CONFIG_DIR': str(work / 'claude'), 'AI_ACCOUNTS_CLAUDE': str(work / 'no-claude'), 'AI_ACCOUNTS_CLAUDE_DIR': str(work / 'claude'), 'AI_ACCOUNTS_WORK_DIR': str(work / 'work'), 'AI_ACCOUNTS_BIND': '127.0.0.1'}
    server = subprocess.Popen([sys.executable, str(pkg / 'server.py')], env=env,
                              stdout=open(work / 'server.log', 'a'), stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen('http://127.0.0.1:18795/health', timeout=1); break
            except OSError:
                time.sleep(0.1)
        out = subprocess.run([sys.executable, '-'], input=guest, text=True, capture_output=True, timeout=60,
                             env={**os.environ, 'FAKE_GATE': gate, 'PATH': str(fixture) + ':' + os.environ['PATH']})
        assert out.returncode == 0, out.stderr[-2000:]
        d = json.loads(out.stdout)
        assert d['password_gate'] is bool(gate)
        if gate:
            assert 'assets' not in d and 'accounts' not in d
        else:
            assert d['origin_rejection'] == 403 and d['json_requirement'] == 415
            assert set(d['assets']) == {'/', '/app.js', '/app.css'}
            assert [a['status'] for a in d['accounts']][0] in ('not_connected', 'connected', 'error')
            assert not any(a['signing_in'] for a in d['accounts']), 'preflight must not start sign-in'
            assert d['account_image']['architecture'] == 'amd64'
        print('PASS gate=%s' % ('set' if gate else 'none'), json.dumps({k: d.get(k) for k in ('password_gate', 'accounts', 'networks')}))
    finally:
        server.terminate(); server.wait()
