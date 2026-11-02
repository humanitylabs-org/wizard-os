#!/usr/bin/env python3
"""Probe a stock `hermes dashboard` bound like the alongside host dashboard (a non-loopback IP, stock basic auth).

Isolated instance: temp HERMES_HOME, bound to 127.0.0.2 (Hermes treats any address other than 127.0.0.1/localhost/::1
as a public bind, exactly like the box's Tailscale IPv4), synthetic password. Never pointed at a real box.
  probe.py <host> <port> <password-file> <out.json>
"""
import http.client
import json
import re
import sys

HOST, PORT, PWF, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
PW = open(PWF).read().strip()
AUTH = f'{HOST}:{PORT}'
rows = []


def req(method, path, headers=None, body=None, host=AUTH):
    c = http.client.HTTPConnection(HOST, PORT, timeout=20)
    h = {'Host': host, **(headers or {})}
    c.request(method, path, body=body, headers=h)
    r = c.getresponse()
    data = r.read()
    hd = {k.lower(): v for k, v in r.getheaders()}
    hd['set-cookie'] = [v for k, v in r.getheaders() if k.lower() == 'set-cookie']
    out = (r.status, hd, data)
    c.close()
    return out


def note(name, status, detail=''):
    rows.append({'probe': name, 'status': status, 'detail': detail})
    print(f'{name:<72} {status!s:<6} {detail}')


# 1. What answers without a session
for path in ('/', '/login', '/api/status', '/api/auth/me', '/api/config', '/api/sessions', '/api/env', '/api/plugins/wizard-os/usage',
             '/api/cron/jobs', '/api/model/info'):
    s, h, d = req('GET', path)
    note(f'no session: GET {path}', s, (h.get('content-type') or '')[:30])

# 2. DNS rebinding: Host must be the bound address
s, *_ = req('GET', '/api/status', host='attacker.example')
note('Host: attacker.example (rebinding)', s)
s, *_ = req('GET', '/api/status', host=f'{HOST}')
note('Host: bound IP without port', s)

# 3. Login: discover the form endpoint and cookie attributes
login_paths = []
s, h, d = req('GET', '/login')
login_paths += re.findall(rb'(/api/auth/[a-z/_-]*login[a-z/_-]*)', d)
PROV = json.loads(req('GET', '/api/auth/providers')[2]).get('providers', [{}])
PROV = next((p.get('name') or p.get('id') for p in PROV if p.get('supports_password') or p.get('kind') == 'password'), 'basic')
LOGIN = lambda pw: json.dumps({'provider': PROV, 'username': 'hermes', 'password': pw, 'next': '/'})
s, h, d = req('POST', '/auth/password-login', {'Content-Type': 'application/json'}, LOGIN('wrong'))
note(f'POST /auth/password-login (wrong password, provider {PROV})', s, d[:60].decode('utf8', 'replace'))
s, h, d = req('POST', '/auth/password-login', {'Content-Type': 'application/json'}, LOGIN(PW))
sc = h['set-cookie']
note('POST /auth/password-login (right password)', s, ','.join(c.split('=')[0] for c in sc))
for c in sc:
    attrs = sorted({a.strip().split('=')[0].lower() for a in c.split(';')[1:] if a.strip()})
    note(f"cookie {c.split('=')[0]}", '-', f"{attrs} SameSite={re.findall(r'samesite=([a-z]+)', c, re.I)}")
jar = '; '.join(c.split(';')[0] for c in sc)

codes = []
for _ in range(25):
    s, *_ = req('POST', '/auth/password-login', {'Content-Type': 'application/json'}, LOGIN('wrong'))
    codes.append(s)
note('25 more wrong passwords in a row', sorted(set(codes)), 'any 429 = rate limited')
s, *_ = req('POST', '/auth/password-login', {'Content-Type': 'application/json'}, LOGIN(PW))
note('right password right after that burst (same client IP)', s, '429 = a caller can lock the consumer apps out')
# 4. With the session: what a holder of the password (any consumer app) can reach
for path in ('/api/status', '/api/config', '/api/env', '/api/sessions', '/api/auth/me'):
    s, *_ = req('GET', path, {'Cookie': jar})
    note(f'session: GET {path}', s)

# 5. Browser-side: framing and cross-site requests carrying the session
s, h, d = req('GET', '/', {'Cookie': jar})
note('GET / framing headers', s, f"XFO={h.get('x-frame-options')} CSP-fa={'frame-ancestors' in (h.get('content-security-policy') or '')}")
s, *_ = req('GET', '/api/config', {'Cookie': jar, 'Origin': 'https://evil.example', 'Sec-Fetch-Site': 'cross-site'})
note('session + Origin evil + cross-site: GET /api/config', s, 'cookie only rides if SameSite allows')
s, h, _ = req('OPTIONS', '/api/config', {'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'PUT'})
note('CORS preflight from https://evil.example', s, f"ACAO={h.get('access-control-allow-origin')}")
s, h, _ = req('OPTIONS', '/api/config', {'Origin': f'https://wizard-box.example.ts.net', 'Access-Control-Request-Method': 'PUT'})
note('CORS preflight from the Wizard shell origin', s, f"ACAO={h.get('access-control-allow-origin')}")
s, *_ = req('POST', '/auth/logout', {'Cookie': jar, 'Origin': f'http://{AUTH}', 'Sec-Fetch-Site': 'same-origin'})
note('same-origin logout POST with the session (control)', s)
json.dump(rows, open(OUT, 'w'), indent=2)
