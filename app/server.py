"""Private prototype HTTP/MCP adapter. Domain policy lives in engine.py.

Only configured synthetic targets are enrolled by the shipped prototype. Operator
writes use a dedicated bearer token; browser writes require an explicitly minted
one-use bootstrap ticket, HttpOnly session and per-session CSRF token. No operator
credential is sent to the browser. A deployment reverse proxy must fence access to
the owner network and set SUPERVISOR_ORIGIN to its exact HTTPS origin.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from engine import Supervisor
from agent import AgentPlanner

VERSION = '0.1.0-prototype'
ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('DATA_DIR', '/data'))
DATA.mkdir(parents=True, exist_ok=True)
CONFIG = json.loads(Path(os.environ.get('SUPERVISOR_CONFIG', '/data/config.json')).read_text())
TOKEN = os.environ.get('SUPERVISOR_TOKEN', '')
if len(TOKEN) < 24:
    raise SystemExit('SUPERVISOR_TOKEN must contain at least 24 characters')
ORIGIN = os.environ.get('SUPERVISOR_ORIGIN', '').rstrip('/')
COOKIE_PATH = os.environ.get('SUPERVISOR_COOKIE_PATH', '/supervisor-prototype/')
ENGINE = Supervisor(DATA / 'supervisor.sqlite3', CONFIG)
LOCK = threading.RLock()
SESSIONS, TICKETS = {}, {}
LAST_TICK: dict = {'at': None, 'error': None}
PLANNER = AgentPlanner(DATA / 'private-runs', os.environ['WIZARD_AGENT_URL'],
    os.environ.get('WIZARD_AGENT_MODEL', ''), os.environ.get('WIZARD_AGENT_PROVIDER', ''),
    os.environ.get('WIZARD_AGENT_TOKEN', '')) if os.environ.get('WIZARD_AGENT_URL') else None


def cycle():
    if PLANNER is None:
        result = ENGINE.tick()
    else:
        result = []
        for target in ENGINE.snapshot()['targets']:
            incident = ENGINE.observe(target['id'])
            if not incident.get('id') or incident['state'] == 'resolved':
                continue
            if incident['verification']['status'] == 'failed' and incident['state'] != 'awaiting_approval':
                recommendation = PLANNER.recommendation(incident, target)
                if recommendation is None:
                    continue
                ENGINE.decide(incident['id'], recommendation)
            result.append(ENGINE.execute(incident['id']))
    LAST_TICK.update(at=time.time(), error=None)
    return result


def snapshot():
    with LOCK:
        result = ENGINE.snapshot()
    result.update(version=VERSION, scope='Enrolled prototype targets only', controller=dict(LAST_TICK))
    result['reasoning'] = {'mode': 'private-agent' if PLANNER else 'baseline-policy',
                           'receipts': PLANNER.receipts() if PLANNER else []}
    for target in result['targets']:
        check = target.get('verification') or {}
        target.update(status=check.get('status', 'unknown'), last_checked=check.get('checked_at'))
    for incident in result['incidents']:
        incident['summary'] = incident.get('reason', '')
        target = next((t for t in result['targets'] if t['id'] == incident['target_id']), {})
        incident['action_description'] = target.get('description', '') + ' — once, for this incident only.'
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = 'WizardSupervisor/0.1'

    def log_message(self, format, *args):
        # Access paths and bootstrap tickets are deliberately omitted.
        return

    def reply(self, status, body, content_type='application/json', headers=None):
        data = json.dumps(body).encode() if content_type == 'application/json' else body.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get('Content-Length', '0'))
        if n < 0 or n > 32768:
            raise ValueError('Request too large')
        if self.headers.get_content_type() != 'application/json':
            raise ValueError('JSON required')
        val = json.loads(self.rfile.read(n))
        if not isinstance(val, dict):
            raise ValueError('JSON object required')
        return val

    def operator(self):
        return hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + TOKEN)

    def session(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
            key = cookies['supervisor_session'].value
        except (KeyError, ValueError):
            return None
        with LOCK:
            row = SESSIONS.get(hashlib.sha256(key.encode()).hexdigest())
            return row if row and row['expires'] > time.time() else None

    def origin_ok(self):
        # Same-origin browser mutations only; a bearer operator never uses cookies.
        return bool(ORIGIN) and self.headers.get('Origin', '') == ORIGIN

    def browser_write(self):
        row = self.session()
        return bool(row and self.origin_ok() and hmac.compare_digest(self.headers.get('X-Supervisor-CSRF', ''), row['csrf']))

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/healthz':
            return self.reply(200, {'ok': True, 'service': 'wizard-supervisor', 'version': VERSION})
        if path in ('/', '/index.html'):
            return self.reply(200, (ROOT / 'web/index.html').read_text(), 'text/html; charset=utf-8')
        if path in ('/boot.js', '/wizard-ui.css'):
            mime = 'text/javascript' if path.endswith('.js') else 'text/css'
            return self.reply(200, (ROOT / 'web' / path[1:]).read_text(), mime)
        if path == '/api/session':
            row = self.session()
            return self.reply(200, {'authorized': bool(row), 'csrf': row['csrf'] if row else None})
        if path == '/api/status':
            return self.reply(200, snapshot())
        return self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        try:
            path = urlsplit(self.path).path
            body = self.body()
            op = self.operator()
            if path == '/api/bootstrap':
                if not self.origin_ok():
                    return self.reply(403, {'error': 'Owner origin required'})
                digest = hashlib.sha256(str(body.get('ticket', '')).encode()).hexdigest()
                with LOCK:
                    expiry = TICKETS.pop(digest, 0)
                    if expiry < time.time():
                        return self.reply(403, {'error': 'Setup link expired or already used'})
                    key, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
                    SESSIONS[hashlib.sha256(key.encode()).hexdigest()] = {'csrf': csrf, 'expires': time.time() + 3600}
                secure = '; Secure' if ORIGIN.startswith('https://') else ''
                return self.reply(200, {'authorized': True, 'csrf': csrf}, headers={'Set-Cookie': f'supervisor_session={key}; Path={COOKIE_PATH}; HttpOnly; SameSite=Strict; Max-Age=3600{secure}'})
            if path == '/api/ticket':
                if not op:
                    return self.reply(403, {'error': 'Operator permission required'})
                ticket = secrets.token_urlsafe(32)
                with LOCK:
                    TICKETS[hashlib.sha256(ticket.encode()).hexdigest()] = time.time() + 300
                return self.reply(200, {'ticket': ticket, 'expires_in': 300})
            if path == '/mcp':
                if not op:
                    return self.reply(403, {'error': 'Operator permission required'})
                return self.mcp(body)
            if not (op or self.browser_write()):
                return self.reply(403, {'error': 'Open an owner setup link to make changes, or ask your Wizard here.'})
            with LOCK:
                if path == '/api/approve':
                    result = ENGINE.approve(str(body['incident_id']), str(body['digest']))
                elif path == '/api/feedback':
                    result = ENGINE.feedback(str(body['incident_id']), str(body['text']), mode='candidate')
                elif path == '/api/preference':
                    text = str(body['text']).strip().lower()
                    if text not in ENGINE.PREFERENCES:
                        raise ValueError('Choose one of the displayed scoped preferences')
                    result = ENGINE.feedback(str(body['incident_id']), text, mode='owner')
                elif path == '/api/rule':
                    if not isinstance(body.get('enabled'), bool):
                        raise ValueError('enabled must be a boolean')
                    result = ENGINE.set_rule(str(body['rule_id']), body['enabled'])
                elif path == '/api/tick' and op:
                    result = cycle()
                elif path == '/api/decide' and op:
                    result = ENGINE.decide(str(body['incident_id']), body['recommendation'])
                else:
                    return self.reply(404, {'error': 'Not found'})
            return self.reply(200, {'ok': True, 'result': result})
        except (ValueError, KeyError, TypeError) as exc:
            return self.reply(400, {'error': str(exc)[:300]})
        except Exception:
            # Do not leak configuration, tokens, SQL, filesystem paths or target URLs.
            return self.reply(409, {'error': 'The action could not be settled. Refresh the incident before retrying.'})

    def mcp(self, req):
        method, rid = req.get('method'), req.get('id')
        tools = [
            {'name': 'supervisor_status', 'description': 'Read enrolled prototype targets, incidents and decisions.', 'inputSchema': {'type': 'object', 'properties': {}}},
            {'name': 'supervisor_decide', 'description': 'Submit a bounded diagnosis/recommendation; configuration enforces authority.', 'inputSchema': {'type': 'object', 'properties': {'incident_id': {'type': 'string'}, 'recommendation': {'type': 'object'}}, 'required': ['incident_id', 'recommendation']}},
            {'name': 'supervisor_feedback', 'description': 'Record owner feedback as a candidate lesson, without granting new authority.', 'inputSchema': {'type': 'object', 'properties': {'incident_id': {'type': 'string'}, 'text': {'type': 'string'}}, 'required': ['incident_id', 'text']}},
        ]
        if method == 'initialize':
            result = {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'wizard-supervisor', 'version': VERSION}}
        elif method == 'notifications/initialized':
            return self.reply(202, {})
        elif method == 'tools/list':
            result = {'tools': tools}
        elif method == 'tools/call':
            args = req.get('params', {}).get('arguments', {})
            name = req.get('params', {}).get('name')
            with LOCK:
                if name == 'supervisor_status':
                    value = snapshot()
                elif name == 'supervisor_decide':
                    value = ENGINE.decide(args['incident_id'], args['recommendation'])
                elif name == 'supervisor_feedback':
                    value = ENGINE.feedback(args['incident_id'], args['text'], mode='candidate')
                else:
                    raise ValueError('Unknown tool')
            result = {'content': [{'type': 'text', 'text': json.dumps(value)}], 'isError': False}
        else:
            return self.reply(200, {'jsonrpc': '2.0', 'id': rid, 'error': {'code': -32601, 'message': 'Method not found'}})
        return self.reply(200, {'jsonrpc': '2.0', 'id': rid, 'result': result})


def ticker():
    while True:
        try:
            with LOCK:
                cycle()
            LAST_TICK.update(at=time.time(), error=None)
        except Exception:
            LAST_TICK.update(at=time.time(), error='Check could not complete; health is unknown.')
        time.sleep(max(5, int(os.environ.get('SUPERVISOR_INTERVAL', '15'))))


if __name__ == '__main__':
    if os.environ.get('SUPERVISOR_AUTOTICK', '1') == '1':
        threading.Thread(target=ticker, daemon=True).start()
    ThreadingHTTPServer((os.environ.get('HOST', '0.0.0.0'), int(os.environ.get('PORT', '8798'))), Handler).serve_forever()
