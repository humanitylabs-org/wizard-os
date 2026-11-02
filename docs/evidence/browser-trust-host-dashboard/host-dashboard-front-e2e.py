#!/usr/bin/env python3
"""Host Hermes dashboard on alongside boxes, base vs candidate (wizard-os issue 386). Synthetic, loopback only.

  run.py base|candidate <out.json> [--chromium]

- App Manager: the REAL `host_dashboard.ensure` of the checkout under test (base = WAM #421 head, candidate = this
  branch), with the box's Tailscale IPv4 stood in by 127.0.0.5 (Hermes treats it as a public bind, like 100.x) and
  systemctl stubbed: the units it writes are then started here exactly as written (ExecStart, EnvironmentFile,
  Environment). Runtipi state from the real ChatGPT and Claude recipes.
- Hermes: stock `hermes dashboard` v0.22.2 (the lock tag), temporary HERMES_HOME (+ the wizard-os plugin copied in).
- Consumer apps: the REAL engine code of wizard-app-store images/wizard-chatgpt (server.py `Hermes`/`connection`)
  and images/wizard-claude (pool_client.py), with the environment their compose would give them from app.env.
- Owner tab (candidate, --chromium): real chrome-headless-shell, box name mapped to 127.0.0.1, Tailscale-User-Login
  added as Serve would. Plain http here (Serve terminates TLS on a real box).
"""
import http.client
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MODE, OUT = sys.argv[1], sys.argv[2]
CHROMIUM = "--chromium" in sys.argv
S = Path(os.path.expanduser("~/.hermes/cache/scratch"))
WAM = {"base": S / "bt-card5/wizard-app-manager", "candidate": S / "bt-hd/wt/wam"}[MODE]
STORE = S / "bt-hd/wizard-app-store/images"
APPS = {"wizard-chatgpt": S / "bt-hd/chatgpt-connection", "wizard-claude": S / "bt-hd/claude-connection"}
TAILNET = "127.0.0.5"
OWNER_LOGIN = "owner@example.com"
BOX = "box.tail0.ts.net"
CHROME = os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/"
                            "chrome-headless-shell")
PW = os.path.expanduser("~/github_repos/aiwizards.com/node_modules/playwright-core")
sys.path.insert(0, str(WAM))
from wam import cli, host_dashboard as hd  # noqa: E402

work = Path(tempfile.mkdtemp(prefix=f"hdfront-{MODE}-"))
rows, procs = [], []


def row(caller, request, result, **kw):
    rows.append({"caller": caller, "request": request, "result": result, **kw})
    print(f"{caller:<44} {request:<58} {result}")


def req(host, port, method, path, headers=None, body=None, hosthdr=None, source=None):
    c = http.client.HTTPConnection(host, port, timeout=30, source_address=(source, 0) if source else None)
    h = {"Host": hosthdr or f"{host}:{port}", **(headers or {})}
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        h.setdefault("Content-Type", "application/json")
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    out = r.status, r.msg, r.read()
    c.close()
    return out


def wait_port(host, port, t=60):
    end = time.time() + t
    while time.time() < end:
        try:
            req(host, port, "GET", "/__probe__")
            return True
        except OSError:
            time.sleep(0.3)
    return False


def unit_cmd(text):
    env = dict(os.environ)
    for line in text.splitlines():
        if line.startswith("EnvironmentFile="):
            env.update(hd.read_env(Path(line.split("=", 1)[1])))
        elif line.startswith("Environment="):
            k, _, v = line.split("=", 1)[1].partition("=")
            env[k] = v
    cmd = next(l.split("=", 1)[1] for l in text.splitlines() if l.startswith("ExecStart="))
    return cmd.split(), env


def start(unit_text, log):
    argv, env = unit_cmd(unit_text)
    env["HOME"] = str(work / "home")   # nothing of this box's own sign-ins is visible to the test agent
    (work / "home").mkdir(exist_ok=True)
    p = subprocess.Popen(argv, env=env, stdout=open(log, "w"), stderr=subprocess.STDOUT, start_new_session=True)
    procs.append(p)
    return p


def client(app, env, code):
    """Run the app's real engine code with the environment its compose interpolates from app.env."""
    e = {k: v for k, v in os.environ.items() if not k.startswith("WIZARD_")}
    e.update(env)
    r = subprocess.run([sys.executable, "-c", code], env=e, capture_output=True, text=True, timeout=120,
                       cwd=str(STORE / ("wizard-chatgpt" if app == "wizard-chatgpt" else "wizard-claude")))
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stderr or r.stdout)[-300:]}


CHATGPT = """
import json, server
try:
    info = server.Hermes.call('GET', '/api/model/info')
    oauth = server.Hermes.call('GET', '/api/providers/oauth')
    print(json.dumps({'ok': True, 'model_info': isinstance(info, dict), 'oauth_list': isinstance(oauth.get('providers'), list)}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': type(e).__name__ + ': ' + str(e)[:160]}))
"""
CLAUDE = """
import json, pool_client
try:
    r = pool_client.Hermes.accounts('claude')
    print(json.dumps({'ok': True, 'owner': r.get('owner'), 'inventory': isinstance(r.get('accounts'), list)}))
except pool_client.BridgeError as e:
    print(json.dumps({'ok': False, 'error': 'BridgeError %s %s' % (e.status, e.code)}))
except Exception as e:
    print(json.dumps({'ok': False, 'error': type(e).__name__ + ': ' + str(e)[:160]}))
"""


def main():
    rt = work / "runtipi"
    for app, repo in APPS.items():
        d = rt / "apps" / "wizardapps" / app
        d.mkdir(parents=True)
        shutil.copy(repo / "runtipi" / "docker-compose.yml", d / "docker-compose.yml")
        shutil.copy(repo / "runtipi" / "config.json", d / "config.json")
    home, units, hh = work / "wos", work / "units", work / "hermes-home"
    hh.mkdir()
    plug = Path.home() / ".hermes" / "plugins" / "wizard-os"
    if plug.is_dir():
        # Plugin code only (no state files from this box), enabled like a Wizard box enables it.
        shutil.copytree(plug, hh / "plugins" / "wizard-os",
                        ignore=shutil.ignore_patterns("__pycache__", "*.log", "chatgpt.json", "*.db", "*.sqlite"))
        (hh / "config.yaml").write_text("plugins:\n  enabled:\n    - wizard-os\n")
    hd.tailnet_ip = lambda: TAILNET
    hd._systemctl = lambda *a: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    kw = {"boundary": MODE == "candidate", "owner": {"hosts": [f"{BOX}:{hd.OWNER_PORT if MODE == 'candidate' else 0}"],
                                                       "logins": [OWNER_LOGIN]}} if MODE == "candidate" else {}
    hermes = shutil.which("hermes") or str(Path.home() / ".local/bin/hermes")
    if MODE == "candidate":   # what a box had before: the stock setup, then the boundary turned on
        hd.ensure(home, rt, "wizardapps", set(APPS), hermes, str(hh), cli.write_user_env, unit_dir=units, boundary=False)
        before_pw = hd.read_env(hd.env_path(home))[hd.PASSWORD_VAR]
    out = hd.ensure(home, rt, "wizardapps", set(APPS), hermes, str(hh), cli.write_user_env, unit_dir=units, **kw)
    creds = hd.read_env(hd.env_path(home))
    row("App Manager", "ensure", out.get("state"), front=out.get("front", "n/a (base)"))
    unit = (units / hd.UNIT).read_text()
    bind = re.search(r"--host (\S+) --port (\d+)", unit).groups()
    row("App Manager", "Hermes unit binds", f"{bind[0]}:{bind[1]}")
    start(unit, work / "hermes.log")
    assert wait_port(bind[0], int(bind[1]), 90), (work / "hermes.log").read_text()[-2000:]
    if MODE == "candidate":
        start((units / hd.FRONT_UNIT).read_text(), work / "front.log")
        assert wait_port(TAILNET, hd.PORT, 20), (work / "front.log").read_text()[-2000:]
    envs = {a: hd.read_env(rt / "user-config" / "wizardapps" / a / "app.env") for a in APPS}
    holds = {a: envs[a].get(hd.PASSWORD_VAR) == creds[hd.PASSWORD_VAR] for a in APPS}
    row("App Manager", "consumer app.env holds the dashboard password", holds)
    row("App Manager", "consumer dashboard address", {a: envs[a].get(f"WIZARD_{a.split('-')[1].upper()}_HERMES_URL") for a in APPS})
    if MODE == "candidate":
        cfg = json.loads(hd.front_config_path(home).read_text())
        row("App Manager", "front config mode / consumers", oct(hd.front_config_path(home).stat().st_mode & 0o777),
            consumers=sorted(r["app"] for r in cfg["consumers"].values()))
        row("App Manager", "password rotated when the front took over", before_pw != creds[hd.PASSWORD_VAR])

    # Consumer apps with the environment their compose gives them.
    def app_env(a):
        p = "WIZARD_" + a.split("-")[1].upper()
        return {f"{p}_HERMES_URL": envs[a][f"{p}_HERMES_URL"], f"{p}_HERMES_USER": envs[a]["HERMES_DASHBOARD_BASIC_AUTH_USERNAME"],
                f"{p}_HERMES_PASSWORD": envs[a][hd.PASSWORD_VAR]}
    row("ChatGPT app (real engine code)", "connection reads: GET /api/model/info, /api/providers/oauth",
        client("wizard-chatgpt", app_env("wizard-chatgpt"), CHATGPT))
    row("Claude app (real engine code)", "account inventory (provider-accounts/claude)",
        client("wizard-claude", app_env("wizard-claude"), CLAUDE))

    # Raw probes on the address the apps use (the tailnet IPv4 in production).
    T, P = TAILNET, hd.PORT
    for path in ("/api/status", "/api/model/info", "/api/config", "/api/env"):
        row("box peer, no session", f"GET {path}", req(T, P, "GET", path)[0])
    app_login = envs["wizard-chatgpt"][hd.PASSWORD_VAR]
    st, msg, _ = req(T, P, "POST", "/auth/password-login",
                     body={"provider": "basic", "username": "hermes", "password": app_login})
    cookie = "; ".join(c.split(";")[0] for c in msg.get_all("Set-Cookie") or [])
    row("ChatGPT app's credential", "POST /auth/password-login", st)
    for path in ("/api/model/info", "/api/env", "/api/config", "/api/sessions"):
        row("ChatGPT app's credential (session)", f"GET {path}", req(T, P, "GET", path, {"Cookie": cookie})[0])
    row("ChatGPT app's credential + Origin", "GET /api/model/info",
        req(T, P, "GET", "/api/model/info", {"Cookie": cookie, "Origin": "https://evil.example"})[0])
    row("ChatGPT app's credential + Tailscale-User-Login", "GET /api/model/info",
        req(T, P, "GET", "/api/model/info", {"Cookie": cookie, "Tailscale-User-Login": OWNER_LOGIN})[0])
    row("DNS rebinding", "GET /api/status Host: attacker.example",
        req(T, P, "GET", "/api/status", hosthdr="attacker.example")[0])
    # Login lockout: a burst of wrong passwords from the same source address the apps use.
    codes = [req(T, P, "POST", "/auth/password-login", body={"provider": "basic", "username": "hermes",
                                                              "password": "wrong"})[0] for _ in range(25)]
    row("box peer", "25 wrong dashboard logins", sorted(set(codes)))
    row("ChatGPT app (real engine code)", "connection reads right after that burst",
        client("wizard-chatgpt", app_env("wizard-chatgpt"), CHATGPT))
    row("Claude app (real engine code)", "account inventory right after that burst",
        client("wizard-claude", app_env("wizard-claude"), CLAUDE))
    if MODE == "candidate":
        st = req(hd.UPSTREAM_HOST, hd.UPSTREAM_PORT, "POST", "/auth/password-login",
                 body={"provider": "basic", "username": "hermes", "password": before_pw}, source="127.0.0.9")[0]
        row("pre-rotation password", "POST /auth/password-login on Hermes itself", st)
        logins = sum(1 for l in (work / "front.log").read_text().splitlines() if '"upstream-login"' in l)
        row("front", "its own Hermes sign-ins during the whole run", logins)
    if CHROMIUM and MODE == "candidate":
        row("owner", "real Chromium own tab", chromium(creds[hd.PASSWORD_VAR]))
    if CHROMIUM and MODE == "base":
        row("owner", "real Chromium: a hostile page frames the dashboard address", chromium_base())


def hostile_server(target):
    """A hostile page on another local origin (evil.test -> 127.0.0.1): a real HTTP server, so Chromium's local-network
    rules treat both sides alike and only the dashboard's own answer decides whether it can be framed."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    body = f'<!doctype html><iframe id=f src="{target}" width=800 height=600></iframe>'.encode()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def chromium(password):
    script = work / "owner.cjs"
    script.write_text(r"""
const { chromium } = require(process.env.PW);
(async () => {
  const out = {};
  const b = await chromium.launch({ executablePath: process.env.CHROME,
    args: ['--host-resolver-rules=MAP %BOX% 127.0.0.1, MAP evil.test 127.0.0.1'] });
  const ctx = await b.newContext({ extraHTTPHeaders: { 'Tailscale-User-Login': '%LOGIN%' } });
  const page = await ctx.newPage();
  const url = 'http://%BOX%:9120/';
  let r = await page.goto(url);
  out.first = { status: r.status(), url: page.url(), xfo: r.headers()['x-frame-options'] || null };
  await page.fill('input[name=password]', process.env.DASH_PW);
  const user = await page.$('input[name=username]'); if (user) await user.fill('hermes');
  await Promise.all([page.waitForLoadState('networkidle').catch(() => {}), page.click('button[type=submit]')]);
  await page.waitForTimeout(2500);
  out.signedIn = { url: page.url(), title: await page.title() };
  const st = await page.evaluate(async () => { const r = await fetch('/api/config'); return r.status; });
  out.sameOriginApi = st;
  await page.screenshot({ path: process.env.SHOT });
  // A hostile page on another origin tries to frame it and to read it.
  const evil = await ctx.newPage();
  const seen = [];
  evil.on('response', (r) => { if (r.url().startsWith(url)) seen.push({ status: r.status(), xfo: r.headers()['x-frame-options'] || null }); });
  await evil.goto('http://evil.test:' + process.env.EVIL_PORT + '/');
  await evil.waitForTimeout(2500);
  const frame = evil.frames().find((f) => f !== evil.mainFrame());
  const html = frame ? await frame.content().catch(() => '') : '';
  out.hostileFrame = { frameUrl: frame ? frame.url() : null, rendered: /name="password"|Hermes/.test(html), answers: seen };
  const guest = await b.newContext({ extraHTTPHeaders: { 'Tailscale-User-Login': 'guest@example.com' } });
  r = await (await guest.newPage()).goto(url);
  out.otherTailnetUser = r.status();
  await b.close();
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({ error: String(e).slice(0, 300) })); process.exit(0); });
""".replace("%BOX%", BOX).replace("%LOGIN%", OWNER_LOGIN))
    evil = hostile_server(f"http://{BOX}:9120/login")
    env = {**os.environ, "PW": PW, "CHROME": CHROME, "DASH_PW": password, "SHOT": str(Path(OUT).with_suffix(".owner.png")),
           "EVIL_PORT": str(evil.server_address[1])}
    r = subprocess.run(["node", str(script)], env=env, capture_output=True, text=True, timeout=180)
    evil.shutdown()
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stderr or r.stdout)[-400:]}


def chromium_base():
    script = work / "base.cjs"
    script.write_text(r"""
const { chromium } = require(process.env.PW);
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME, args: ['--host-resolver-rules=MAP evil.test 127.0.0.1'] });
  const page = await b.newPage();
  const url = 'http://%T%:9119/login';
  const seen = [];
  page.on('response', (r) => { if (r.url().startsWith(url)) seen.push({ status: r.status(), xfo: r.headers()['x-frame-options'] || null }); });
  await page.goto('http://evil.test:' + process.env.EVIL_PORT + '/');
  await page.waitForTimeout(2500);
  const frame = page.frames().find((f) => f !== page.mainFrame());
  const html = frame ? await frame.content().catch(() => '') : '';
  await page.screenshot({ path: process.env.SHOT });
  console.log(JSON.stringify({ hostileFrame: { frameUrl: frame ? frame.url() : null, rendered: /name="password"|Hermes/.test(html), answers: seen } }));
  await b.close();
})().catch((e) => { console.log(JSON.stringify({ error: String(e).slice(0, 300) })); });
""".replace("%T%", TAILNET))
    evil = hostile_server(f"http://{TAILNET}:9119/login")
    r = subprocess.run(["node", str(script)], env={**os.environ, "PW": PW, "CHROME": CHROME, "EVIL_PORT": str(evil.server_address[1]),
                       "SHOT": str(Path(OUT).with_suffix(".hostile-frame.png"))}, capture_output=True, text=True, timeout=120)
    evil.shutdown()
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stderr or r.stdout)[-400:]}


try:
    main()
finally:
    for p in procs:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for p in procs:
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
    Path(OUT).write_text(json.dumps({"mode": MODE, "wam": str(WAM), "rows": rows}, indent=2) + "\n")
    for log in ("front.log", "hermes.log"):
        if (work / log).is_file():
            shutil.copy(work / log, Path(OUT).with_suffix(f".{log}"))
    shutil.rmtree(work, ignore_errors=True)
