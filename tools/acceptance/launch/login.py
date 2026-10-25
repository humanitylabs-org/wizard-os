#!/usr/bin/env python3
"""Host-only sign-in station: reuse the pushed ChatGPT app, never a live login.

Run under launchd on the build machine, behind a dedicated private HTTPS Serve
port. A capability URL establishes a Secure/HttpOnly cookie; neither the URL nor
provider credentials go to logs. This station never registers against any Hermes.
"""
import argparse
import hmac
from http.cookies import SimpleCookie
import importlib
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--oauth-source', required=True, type=Path)
    p.add_argument('--state', required=True, type=Path)
    p.add_argument('--origin', required=True)
    p.add_argument('--port', type=int, default=18808)
    a = p.parse_args()
    if urlsplit(a.origin).scheme != 'https' or urlsplit(a.origin).path not in ('', '/'):
        p.error('private HTTPS origin required')
    os.umask(0o077)
    a.state.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(a.state, 0o700)
    keyfile = a.state / 'login-capability'
    if not keyfile.exists():
        keyfile.write_text(secrets.token_urlsafe(48))
    os.chmod(keyfile, 0o600)
    key = keyfile.read_text().strip()
    # The app owns and refreshes only the new dedicated login in this directory.
    # No local Hermes dashboard, credential pool or owner config is consulted.
    os.environ.update(APP_DATA_DIR=str(a.state), WIZARD_CHATGPT_BIND='127.0.0.1',
                      WIZARD_CHATGPT_PORT=str(a.port), WIZARD_CHATGPT_HERMES_URL='http://127.0.0.1:1',
                      WIZARD_CHATGPT_HERMES_PASSWORD='', WIZARD_CHATGPT_PASSWORD='')
    sys.path.insert(0, str(a.oauth_source))
    app = importlib.import_module('server')
    class Handler(app.Handler):
        def gate(self):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie', ''))
                given = cookie['launch-signin'].value
            except (KeyError, ValueError):
                given = ''
            if not hmac.compare_digest(given, key):
                self.json(403, {'error': 'Open your private sign-in link.'})
                return False
            return True

        def do_GET(self):
            if hmac.compare_digest(self.path, '/' + key):
                self.send_response(303)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie', f'launch-signin={key}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=21600')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if self.gate():
                if self.path.startswith('/v1/') or self.path.startswith('/.well-known/'):
                    self.json(404, {'error': 'Sign-in station only.'})
                    return
                super().do_GET()

        def do_POST(self):
            if self.gate():
                if not self.path.startswith('/api/chatgpt/'):
                    self.json(404, {'error': 'Sign-in station only.'})
                    return
                super().do_POST()
    # Link is private configuration, not a receipt or a stdout message.
    (a.state / 'owner-link').write_text(a.origin.rstrip('/') + '/' + key + '\n')
    os.chmod(a.state / 'owner-link', 0o600)
    app.ThreadingHTTPServer(('127.0.0.1', a.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
