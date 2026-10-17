#!/usr/bin/env python3
"""Owner-only, time-boxed Claude sign-in window for one release 0.2.2 test guest.

Chain: tailnet HTTPS (Tailscale Serve, one dedicated test port) -> loopback
owner relay (this file) -> Lima SSH forward -> guest loopback AI Accounts page.

Subcommands
  open      run inside the heavy queue: start the guest, install the launchd
            supervisor, add one Serve handler, verify allow/deny, exit.
  supervise launchd entry: run tunnel + relay until expiry, then close.
  close     remove only this window's handler/agent/tunnel and stop the guest.

Identity comes from the Serve hop (Tailscale strips client-sent identity
headers) and the relay listens on loopback only. Owner login and node name are
discovered at runtime from tailscale status, never stored in source. The relay
never logs bodies, queries, cookies or credentials, and exposes only the
packaged page, its assets and the official sign-in/status API.
"""
import argparse, http.client, json, os, signal, socket, subprocess, sys, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

TS = '/opt/homebrew/bin/tailscale'
LABEL = 'ai.wizard.e2e022.signin-window'
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


def supervise(state_path):
    state = json.loads(state_path.read_text())
    root = Path(state['root'])
    if now() >= state['expires_at']:
        return close(state_path, stop_guest=state.get('stop_guest_on_expiry', True), reason='expired-on-start')
    Relay.owner, Relay.origin = state['owner'], state['origin']
    Relay.upstream, Relay.log_path = state['tunnel_port'], state['relay_log']
    srv = ThreadingHTTPServer(('127.0.0.1', state['relay_port']), Relay)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    # The guest lives under this launchd job, not the heavy job's process group,
    # so it survives the setup job and always stops when the window closes.
    vms = [json.loads(l) for l in subprocess.check_output(['limactl', 'list', '--json'],
           env=lima_env(root), text=True).splitlines()]
    if [v['status'] for v in vms if v['name'] == state['vm']] != ['Running']:
        with open(Path(state['run_dir']) / 'start.log', 'a') as f:
            subprocess.run(['limactl', 'start', '--tty=false', state['vm']], env=lima_env(root),
                           check=True, stdout=f, stderr=subprocess.STDOUT, timeout=420)
    cfg = root / 'lima' / state['vm'] / 'ssh.config'
    tunnel = None
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *a: stop.set())
    while not stop.is_set() and now() < state['expires_at']:
        if tunnel is None or tunnel.poll() is not None:
            tunnel = subprocess.Popen(['/usr/bin/ssh', '-F', str(cfg), '-N', '-o', 'ExitOnForwardFailure=yes',
                                       '-o', 'ServerAliveInterval=15', '-L',
                                       '127.0.0.1:%d:127.0.0.1:%d' % (state['tunnel_port'], GUEST_PORT),
                                       'lima-' + state['vm']], stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        stop.wait(5)
    if tunnel and tunnel.poll() is None:
        tunnel.terminate()
    srv.shutdown()
    if now() >= state['expires_at']:
        close(state_path, stop_guest=state.get('stop_guest_on_expiry', True), reason='expired')


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
    return s


def close(state_path, stop_guest=False, reason='requested'):
    state = json.loads(state_path.read_text())
    root = Path(state['root'])
    result = {'closed_at': stamp(), 'reason': reason}
    serve = ts_json('serve', 'status')
    if serve_handler_ours(serve, state):
        subprocess.run([TS, 'serve', '--https=%d' % state['https_port'], 'off'], check=True, timeout=30)
        result['handler_removed'] = True
    elif str(state['https_port']) in (serve.get('TCP') or {}):
        result['handler_removed'] = False
        result['warning'] = 'port occupied by a handler this window does not own; left untouched'
    after = ts_json('serve', 'status')
    before = json.loads(Path(state['serve_before']).read_text())
    result['other_handlers_unchanged'] = without_port(after, state) == without_port(before, state)
    plist = Path(state['plist'])
    # Stop the guest whenever the window closes: it ran outside the heavy lock.
    # Its sign-in state persists in the guest's Docker volume.
    subprocess.run(['limactl', 'stop', state['vm']], env=lima_env(root), timeout=240,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result['guest_stopped'] = True
    state.setdefault('closures', []).append(result)
    state['closed'] = True
    write_json(state_path, state)
    print(json.dumps(result), flush=True)
    if plist.exists():
        plist.unlink()
    # Last: this may terminate the calling supervisor itself.
    subprocess.run(['launchctl', 'bootout', 'gui/%d/%s' % (os.getuid(), LABEL)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result


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


def open_window(a):
    root = a.root.resolve()
    assert str(root).startswith('/Volumes/ThalesMedia/'), 'window state belongs on the media volume'
    os.umask(0o077)
    base = root / 'signin-window'
    base.mkdir(exist_ok=True)
    state_path = base / 'state.json'
    if state_path.exists():
        old = json.loads(state_path.read_text())
        assert old.get('closed'), 'an earlier window is still open; close it first'
        state_path.rename(base / ('state-%s.json' % int(now())))
    owner, node = owner_identity()
    serve = ts_json('serve', 'status')
    for p in (a.relay_port, a.tunnel_port):
        assert port_free(p), 'loopback port %d is in use' % p
    assert str(a.https_port) not in (serve.get('TCP') or {}), 'Serve port is already in use'
    run_dir = base / ('window-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    run_dir.mkdir()
    (run_dir / 'serve-before.json').write_text(json.dumps(serve, indent=2) + '\n')
    env = lima_env(root)
    vms = {json.loads(l)['name']: json.loads(l) for l in
           subprocess.check_output(['limactl', 'list', '--json'], env=env, text=True).splitlines()}
    vm = vms[a.vm]
    assert vm['arch'] == 'x86_64' and not vm['config'].get('mounts')
    assert vm['status'] == 'Stopped', 'the guest must begin stopped; another lane may own it'
    origin = 'https://%s:%d' % (node, a.https_port)
    state = {'root': str(root), 'vm': a.vm, 'owner': owner, 'node': node, 'origin': origin,
             'https_port': a.https_port, 'relay_port': a.relay_port, 'tunnel_port': a.tunnel_port,
             'opened_at': now(), 'expires_at': now() + a.minutes * 60, 'stop_guest_on_expiry': True,
             'serve_before': str(run_dir / 'serve-before.json'), 'relay_log': str(run_dir / 'relay.jsonl'),
             'run_dir': str(run_dir), 'plist': str(Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')),
             'closed': False}
    write_json(state_path, state)
    plist = Path(state['plist'])
    plist.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>%s</string>
<key>ProgramArguments</key><array><string>%s</string><string>%s</string><string>supervise</string><string>--state</string><string>%s</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
<key>StandardOutPath</key><string>%s</string><key>StandardErrorPath</key><string>%s</string>
</dict></plist>
''' % (LABEL, sys.executable, Path(__file__).resolve(), state_path, run_dir / 'supervisor.log', run_dir / 'supervisor.log'))
    checks = {}
    try:
        subprocess.run(['launchctl', 'bootstrap', 'gui/%d' % os.getuid(), str(plist)], check=True, timeout=30)
        deadline = now() + 600
        while True:
            try:
                code, _ = local(a.relay_port, '/', headers={'Tailscale-User-Login': owner})
                if code == 200:
                    break
            except OSError:
                pass
            assert now() < deadline, 'relay/tunnel never became ready'
            time.sleep(2)
        subprocess.run([TS, 'serve', '--bg', '--yes', '--https=%d' % a.https_port,
                        'http://127.0.0.1:%d' % a.relay_port], check=True, timeout=30,
                       stdout=subprocess.DEVNULL)
        after = ts_json('serve', 'status')
        (run_dir / 'serve-after-open.json').write_text(json.dumps(after, indent=2) + '\n')
        checks['only_test_handler_added'] = serve_handler_ours(after, state) and without_port(after, state) == serve
        owner_h = {'Tailscale-User-Login': owner}
        checks['deny_no_identity'] = local(a.relay_port, '/')[0] == 403
        checks['deny_other_identity'] = local(a.relay_port, '/', headers={'Tailscale-User-Login': 'someone-else@example.com'})[0] == 403
        checks['deny_unlisted_route'] = local(a.relay_port, '/mcp', 'POST', {**owner_h, 'Origin': origin, 'Content-Type': 'application/json'}, b'{}')[0] == 404
        checks['deny_cross_origin_post'] = local(a.relay_port, '/api/claude/cancel', 'POST', {**owner_h, 'Origin': 'https://evil.example', 'Content-Type': 'application/json'}, b'{}')[0] == 403
        code, raw = local(a.relay_port, '/api/accounts', headers=owner_h)
        claude = json.loads(raw)['accounts'][0]
        checks['owner_status'] = code == 200 and claude['status'] in ('not_connected', 'connected')
        state['claude_status_at_open'] = claude['status']
        state['checks'] = checks
        write_json(state_path, state)
        assert all(checks.values()), checks
    except BaseException:
        close(state_path, stop_guest=True, reason='open-failed')
        raise
    print(json.dumps({'window': 'open', 'vm': a.vm, 'expires_at': datetime.fromtimestamp(state['expires_at'], timezone.utc).isoformat(),
                      'https_port': a.https_port, 'checks': checks, 'claude_status': state['claude_status_at_open'],
                      'run_dir': str(run_dir)}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    o = sub.add_parser('open')
    o.add_argument('--root', type=Path, required=True)
    o.add_argument('--vm', choices=VMS, required=True)
    o.add_argument('--minutes', type=int, default=60, choices=range(30, 91), metavar='30-90')
    o.add_argument('--https-port', type=int, default=18449)
    o.add_argument('--relay-port', type=int, default=18450)
    o.add_argument('--tunnel-port', type=int, default=18451)
    s = sub.add_parser('supervise')
    s.add_argument('--state', type=Path, required=True)
    c = sub.add_parser('close')
    c.add_argument('--state', type=Path, required=True)
    a = p.parse_args()
    if a.cmd == 'open':
        open_window(a)
    elif a.cmd == 'supervise':
        supervise(a.state)
    else:
        close(a.state)


if __name__ == '__main__':
    main()
