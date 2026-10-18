#!/usr/bin/env python3
"""Owner-only, time-boxed Claude sign-in window for one release 0.2.2 test guest.

Chain: tailnet HTTPS (Tailscale Serve, one dedicated test port) -> loopback
owner relay (this file) -> Lima SSH forward -> guest loopback AI Accounts page.

Runs entirely inside one heavy-queue job (launchd agents cannot reach the
media volume under macOS privacy rules, so nothing outlives the job):
  rehearse  open the window, prove allow/deny and phone rendering, close.
  hold      open the window, then keep it until Claude reports connected or
            the window expires; close. Status is read, never credentials.
Closing removes only this window's own Serve handler, ends the tunnel/relay
and stops the guest. A leftover handler from a killed run is removed first.

Identity comes from the Serve hop (Tailscale strips client-sent identity
headers) and the relay listens on loopback only. Owner login and node name are
discovered at runtime from tailscale status, never stored in source. The relay
never logs bodies, queries, cookies or credentials, and exposes only the
packaged page, its assets and the official sign-in/status API.
"""
import argparse, http.client, json, os, platform, signal, socket, subprocess, sys, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import e2e_022_alongside_claude as owner_claude

TS = '/opt/homebrew/bin/tailscale'
GUEST_PORT = 8795
VMS = ('fresh-022-candidate-amd64', 'alongside-022-amd64')
GET_ROUTES = {'/', '/app.js', '/app.css', '/api/accounts'}
POST_ROUTES = {'/api/claude/connect', '/api/claude/code', '/api/claude/cancel',
               '/api/claude/test', '/api/claude/logout'}
FORWARD_HEADERS = {'content-type', 'content-length', 'accept', 'accept-language', 'user-agent'}
MAX_BODY = 4096


def now():
    return time.time()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def ts_json(*args):
    return json.loads(subprocess.check_output([TS, *args, '--json'], text=True, timeout=30))


def owner_identity():
    st = ts_json('status')
    assert st['BackendState'] == 'Running', 'Tailscale is not running'
    user = st['User'][str(st['Self']['UserID'])]
    return user['LoginName'], st['Self']['DNSName'].rstrip('.')


def write_json(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    os.chmod(tmp, 0o600)
    tmp.replace(path)


class Relay(BaseHTTPRequestHandler):
    """Owner gate in front of the packaged page. Configured via class attrs."""
    owner = ''
    origin = ''
    upstream = 0
    log_path = None
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass  # default logging would include the query string

    def audit(self, status, ok):
        line = json.dumps({'t': stamp(), 'm': self.command, 'p': urlsplit(self.path).path,
                           's': status, 'owner': ok})
        with open(self.log_path, 'a') as f:
            f.write(line + '\n')

    def deny(self, code, text, ok=False):
        body = json.dumps({'ok': False, 'message': text}).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.audit(code, ok)

    def handle_one(self):
        path = urlsplit(self.path).path
        login = (self.headers.get('Tailscale-User-Login') or '').strip().casefold()
        if self.client_address[0] != '127.0.0.1':
            return self.deny(403, 'Local Serve hop required.')
        if not login or login != self.owner.casefold():
            return self.deny(403, 'The owner Tailnet identity is required.')
        if self.command in ('GET', 'HEAD'):
            if path not in GET_ROUTES:
                return self.deny(404, 'Not part of this sign-in page.', True)
            body = b''
        elif self.command == 'POST':
            if path not in POST_ROUTES:
                return self.deny(404, 'Not part of this sign-in page.', True)
            if self.headers.get('Origin') != self.origin:
                return self.deny(403, 'Same-origin request required.', True)
            if (self.headers.get('Sec-Fetch-Site') or 'same-origin') != 'same-origin':
                return self.deny(403, 'Same-origin request required.', True)
            n = int(self.headers.get('Content-Length') or 0)
            if n > MAX_BODY:
                return self.deny(413, 'Too large.', True)
            body = self.rfile.read(n)
        else:
            return self.deny(405, 'Method not allowed.', True)
        headers = {k: v for k, v in self.headers.items() if k.lower() in FORWARD_HEADERS}
        headers['Host'] = urlsplit(self.origin).netloc  # the package checks Origin against Host
        if self.command == 'POST':
            headers['Origin'] = self.origin
        try:
            conn = http.client.HTTPConnection('127.0.0.1', self.upstream, timeout=90)
            conn.request(self.command, path, body=body or None, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except OSError:
            return self.deny(502, 'The test installation is not reachable.', True)
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in ('content-type',):
                self.send_header(k, v)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.send_header('Connection', 'close')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)
        self.audit(resp.status, True)

    do_GET = do_HEAD = do_POST = do_PUT = do_DELETE = do_PATCH = handle_one



def lima_env(root):
    return {**os.environ, 'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',
            'LIMA_HOME': str(root / 'lima'), 'LIMA_CACHE_HOME': str(root / 'lima-cache')}


def serve_handler_ours(serve, state):
    port = str(state['https_port'])
    web = (serve.get('Web') or {}).get('%s:%s' % (state['node'], port), {})
    proxies = [h.get('Proxy') for h in (web.get('Handlers') or {}).values()]
    return port in (serve.get('TCP') or {}) and proxies == ['http://127.0.0.1:%d' % state['relay_port']]


def without_port(serve, state):
    port = str(state['https_port'])
    s = json.loads(json.dumps(serve))
    (s.get('TCP') or {}).pop(port, None)
    (s.get('Web') or {}).pop('%s:%s' % (state['node'], port), None)
    for k in ('TCP', 'Web'):
        if k in s and not s[k]:
            s.pop(k)
    return s


def remove_own_handler(state):
    serve = ts_json('serve', 'status')
    if serve_handler_ours(serve, state):
        subprocess.run([TS, 'serve', '--https=%d' % state['https_port'], 'off'], check=True, timeout=30,
                       stdout=subprocess.DEVNULL)
        return True
    return False


def port_free(port):
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def local(port, path, method='GET', headers=None, body=None):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=30)
    conn.request(method, path, body=body, headers=headers or {})
    r = conn.getresponse()
    return r.status, r.read()


RENDER_JS = r"""
const { chromium } = require(process.argv[2]);
const [origin, ip, shot] = process.argv.slice(3);
(async () => {
  const host = new URL(origin).hostname;
  const browser = await chromium.launch({ args: ['--host-resolver-rules=MAP ' + host + ' ' + ip] });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3,
    isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  const responses = {}; const errors = [];
  page.on('response', r => { const u = new URL(r.url()); if (u.origin === origin) responses[u.pathname] = r.status(); });
  page.on('pageerror', e => errors.push(String(e).slice(0, 200)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  await page.goto(origin + '/', { waitUntil: 'networkidle' });
  await page.waitForSelector('#accounts .name');
  const names = await page.$$eval('#accounts .name', xs => xs.map(x => x.textContent));
  const buttons = await page.$$eval('#accounts button', xs => xs.map(x => x.textContent));
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  await page.screenshot({ path: shot, fullPage: true });
  console.log(JSON.stringify({ responses, errors, names, buttons, scroll_width: width }));
  await browser.close();
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


def render_check(state, run_dir, node_bin, playwright):
    script = run_dir / 'render.cjs'
    script.write_text(RENDER_JS)
    ip = subprocess.check_output([TS, 'ip', '-4'], text=True, timeout=10).split()[0]
    out = subprocess.run([node_bin, str(script), playwright, state['origin'], ip, str(run_dir / 'phone.png')],
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, 'phone render failed: ' + out.stderr[-500:]
    r = json.loads(out.stdout.strip().splitlines()[-1])
    ok = (r['responses'].get('/') == 200 and r['responses'].get('/app.js') == 200 and
          r['responses'].get('/app.css') == 200 and r['responses'].get('/api/accounts') == 200 and
          not r['errors'] and 'Claude subscription' in r['names'] and r['scroll_width'] <= 390 and
          any(b in ('Connect', 'Test') for b in r['buttons']))
    return ok, r


def claude_status(state):
    code, raw = local(state['relay_port'], '/api/accounts', headers={'Tailscale-User-Login': state['owner']})
    assert code == 200
    return json.loads(raw)['accounts'][0]['status']


def run_window(a):
    assert platform.system() == 'Darwin', 'Thales/macOS only'
    assert a.https_port not in (443, 8447, 8847), 'production Serve ports are forbidden'
    assert all(1024 <= p <= 65535 for p in (a.https_port, a.relay_port, a.tunnel_port))
    assert len({a.https_port, a.relay_port, a.tunnel_port}) == 3
    host_page = a.vm == owner_claude.VM and a.guest_port == 8797
    assert a.vm != owner_claude.VM or host_page, 'alongside sign-in requires --guest-port 8797'
    assert not host_page or a.cmd == 'hold', 'owner setup is hold-only'
    assert a.guest_port == 8795 or host_page, 'port 8797 is alongside-owner only'
    root = a.root.resolve()
    assert str(root).startswith('/Volumes/ThalesMedia/'), 'window state belongs on the media volume'
    os.umask(0o077)
    owner, node = owner_identity()
    base = root / 'signin-window'
    base.mkdir(exist_ok=True)
    run_dir = base / ('%s-%s' % (a.cmd, datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')))
    run_dir.mkdir()
    state = {'vm': a.vm, 'owner': owner, 'node': node, 'origin': 'https://%s:%d' % (node, a.https_port),
             'https_port': a.https_port, 'relay_port': a.relay_port, 'tunnel_port': a.tunnel_port, 'guest_port': a.guest_port}
    receipt = {'mode': a.cmd, 'vm': a.vm, 'host': platform.node(), 'started_at': stamp(),
               'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'leftover_handler_removed': remove_own_handler(state)}
    serve_before = ts_json('serve', 'status')
    (run_dir / 'serve-before.json').write_text(json.dumps(serve_before, indent=2) + '\n')
    assert str(a.https_port) not in (serve_before.get('TCP') or {}), 'Serve port is owned by another handler'
    for p in (a.relay_port, a.tunnel_port):
        assert port_free(p), 'loopback port %d is in use' % p
    env = lima_env(root)
    vm = {json.loads(l)['name']: json.loads(l) for l in
          subprocess.check_output(['limactl', 'list', '--json'], env=env, text=True).splitlines()}[a.vm]
    assert vm['arch'] == 'x86_64' and not vm['config'].get('mounts')
    assert vm['status'] == 'Stopped', 'the guest must begin stopped; another lane may own it'
    Relay.owner, Relay.origin = owner, state['origin']
    Relay.upstream, Relay.log_path = a.tunnel_port, str(run_dir / 'relay.jsonl')
    srv = ThreadingHTTPServer(('127.0.0.1', a.relay_port), Relay)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    tunnel = None
    host_page_attempted = False
    checks = {}
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *x: stop.set())

    def ensure_tunnel():
        nonlocal tunnel
        if tunnel is None or tunnel.poll() is not None:
            tunnel = subprocess.Popen(['/usr/bin/ssh', '-F', str(root / 'lima' / a.vm / 'ssh.config'), '-N',
                                       '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=15', '-L',
                                       '127.0.0.1:%d:127.0.0.1:%d' % (a.tunnel_port, a.guest_port), 'lima-' + a.vm],
                                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with (run_dir / 'start.log').open('w') as f:
            subprocess.run(['limactl', 'start', '--tty=false', a.vm], env=env, check=True,
                           stdout=f, stderr=subprocess.STDOUT, timeout=420)
        if host_page:
            receipt['owner_setup'] = owner_claude.dispatch(root, 'setup')
            host_page_attempted = True
            receipt['owner_signin_page'] = owner_claude.dispatch(root, 'signin-page')
        deadline = now() + 600
        while True:
            ensure_tunnel()
            try:
                if local(a.relay_port, '/', headers={'Tailscale-User-Login': owner})[0] == 200:
                    break
            except OSError:
                pass
            assert now() < deadline, 'relay/tunnel never became ready'
            time.sleep(3)
        subprocess.run([TS, 'serve', '--bg', '--yes', '--https=%d' % a.https_port,
                        'http://127.0.0.1:%d' % a.relay_port], check=True, timeout=30, stdout=subprocess.DEVNULL)
        after = ts_json('serve', 'status')
        checks['only_test_handler_added'] = serve_handler_ours(after, state) and without_port(after, state) == without_port(serve_before, state)
        own = {'Tailscale-User-Login': owner}
        post = {**own, 'Origin': state['origin'], 'Content-Type': 'application/json'}
        checks['deny_no_identity'] = local(a.relay_port, '/')[0] == 403
        checks['deny_other_identity'] = local(a.relay_port, '/', headers={'Tailscale-User-Login': 'someone-else@example.com'})[0] == 403
        checks['deny_unlisted_route'] = local(a.relay_port, '/mcp', 'POST', post, b'{}')[0] == 404
        checks['deny_cross_origin_post'] = local(a.relay_port, '/api/claude/cancel', 'POST', {**post, 'Origin': 'https://evil.example'}, b'{}')[0] == 403
        checks['relay_loopback_only'] = not any(
            socket.socket().connect_ex((ip, a.relay_port)) == 0
            for ip in subprocess.check_output([TS, 'ip'], text=True).split() if ':' not in ip)
        ok, render = render_check(state, run_dir, a.node, a.playwright)
        checks['phone_render_via_serve'] = ok
        receipt['render'] = render
        receipt['claude_status_at_open'] = claude_status(state)
        checks['owner_status'] = receipt['claude_status_at_open'] in ('not_connected', 'connected')
        receipt['checks'] = checks
        assert all(checks.values()), checks
        if a.cmd == 'hold':
            expires = now() + a.minutes * 60
            receipt['window_open_at'] = stamp()
            receipt['window_expires_at'] = datetime.fromtimestamp(expires, timezone.utc).isoformat()
            write_json(run_dir / 'receipt.json', receipt)
            print(json.dumps({'window': 'open', 'origin_port': a.https_port,
                              'expires_at': receipt['window_expires_at']}), flush=True)
            status = receipt['claude_status_at_open']
            while not stop.is_set() and now() < expires and status != 'connected':
                stop.wait(10)
                ensure_tunnel()
                try:
                    status = claude_status(state)
                except (OSError, AssertionError, ValueError):
                    pass
            receipt['claude_status_at_close'] = status
            receipt['outcome'] = 'connected' if status == 'connected' else ('stopped' if stop.is_set() else 'expired')
        else:
            receipt['outcome'] = 'rehearsal-pass'
    finally:
        receipt['handler_removed'] = remove_own_handler(state)
        if tunnel and tunnel.poll() is None:
            tunnel.terminate()
        srv.shutdown()
        if host_page_attempted:
            try:
                receipt['owner_signin_page_stop'] = owner_claude.dispatch(root, 'signin-page', stop=True)
            except Exception as e:
                receipt['owner_signin_page_stop'] = {'error': type(e).__name__}
        with (run_dir / 'stop.log').open('w') as f:
            subprocess.run(['limactl', 'stop', a.vm], env=env, stdout=f, stderr=subprocess.STDOUT, timeout=240)
        final = ts_json('serve', 'status')
        (run_dir / 'serve-after.json').write_text(json.dumps(final, indent=2) + '\n')
        receipt['serve_restored'] = final == serve_before
        receipt['finished_at'] = stamp()
        receipt['run_dir'] = str(run_dir)
        write_json(run_dir / 'receipt.json', receipt)
        print(json.dumps(receipt), flush=True)
    assert receipt['serve_restored'], 'Serve config differs from the snapshot'
    if host_page_attempted:
        assert receipt.get('owner_signin_page_stop', {}).get('stopped'), 'one-shot cleanup failed'


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('rehearse', 'hold'):
        o = sub.add_parser(name)
        o.add_argument('--root', type=Path, required=True)
        o.add_argument('--vm', choices=VMS, required=True)
        o.add_argument('--guest-port', type=int, choices=(8795, 8797), default=GUEST_PORT)
        o.add_argument('--node', default='/opt/homebrew/bin/node')
        o.add_argument('--playwright', required=True, help='path to an installed playwright module')
        o.add_argument('--https-port', type=int, default=18449)
        o.add_argument('--relay-port', type=int, default=18450)
        o.add_argument('--tunnel-port', type=int, default=18451)
        if name == 'hold':
            o.add_argument('--minutes', type=int, default=60, choices=range(30, 91), metavar='30-90')
    return p


def main():
    run_window(parser().parse_args())


if __name__ == '__main__':
    main()
