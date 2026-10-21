"""VM-side driver for one Connection Router acceptance state. Runs as root inside the disposable Lima VM.

  vm_state.py up <state>                 fresh state dir, fake providers, Router container, Wisdom container
  vm_state.py collect <state> <phase>    owner needs, app needs (with each app's grant), routes, provider status
  vm_state.py runs <state> <phase>       one /v1/models/<feature>/run per feature (Wisdom's from inside Wisdom)
  vm_state.py order <state> <a,b>        POST /v1/owner/provider-order
  vm_state.py down <state>               stop containers and fakes; evidence stays

Everything an app sees comes from the real artefacts: the published Router image (pinned digest), Wisdom built from
its pinned commit, and Wisdom's own wizard.md resolved through WIZARD_RECIPES_DIR exactly as on a stock box.
"""
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("ACCEPT_ROOT", "/Volumes/ThalesMedia/wizard-os/router-acceptance"))
RUN = Path(os.environ["ACCEPT_RUN"])                       # this run's folder under ROOT/runs/<id>
STAGE = ROOT / "stage"
HERE = Path(__file__).resolve().parent
WORK = Path("/var/lib/router-accept")                      # VM-local state (bind-mount permissions stay simple)
ROUTER_IMAGE = os.environ["ROUTER_IMAGE"]
WISDOM_IMAGE = os.environ.get("WISDOM_IMAGE", "wisdom-accept:9202da8")
RPORT, WPORT = 28802, 29200
R = f"http://127.0.0.1:{RPORT}"
OPEN = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def sh(*args, check=True, **kw):
    return subprocess.run(args, check=check, text=True, capture_output=True, **kw)


def http(method, url, body=None, headers=None, timeout=20):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={**({"Content-Type": "application/json"} if data else {}), **(headers or {})})
    try:
        with OPEN.open(req, timeout=timeout) as r:
            raw, status, ctype = r.read(), r.status, r.headers.get_content_type()
    except urllib.error.HTTPError as e:
        raw, status, ctype = e.read(), e.code, e.headers.get_content_type()
    text = raw.decode("utf-8", "replace")
    if ctype == "text/event-stream":
        return status, [json.loads(l[5:].strip()) for l in text.splitlines() if l.startswith("data:")]
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text[:400]


def manifest_version(path):
    import yaml
    return str(yaml.safe_load(path.read_text().split("---", 2)[1])["version"])


def evidence(state):
    d = RUN / "evidence" / state
    d.mkdir(parents=True, exist_ok=True)
    return d


def secrets_file(state):
    return WORK / state / "test-grants.json"   # throwaway per-run app grants; never leave the VM


def up(state):
    down(state, quiet=True)
    w = WORK / state
    shutil.rmtree(w, ignore_errors=True)
    for d in ("registry", "grants", "recipes", "state", "wisdom-data", "wisdom-media", "fakes"):
        (w / d).mkdir(parents=True)
    ev = evidence(state)
    # 1. Fake providers (both provider apps installed; connection status is what differs between states).
    ports = w / "fakes" / "ports.json"
    log = ev / "provider-requests.jsonl"
    log.unlink(missing_ok=True)
    out = open(w / "fakes" / "fakes.log", "w")
    p = subprocess.Popen([sys.executable, str(HERE / "fakes.py"), state, str(STAGE / "router-src" / "tests"),
                          str(STAGE / "provider-models"), str(ports), str(log)], stdout=out, stderr=out,
                         start_new_session=True)
    (w / "fakes" / "pid").write_text(str(p.pid))
    for _ in range(100):
        if ports.exists():
            break
        time.sleep(.1)
    endpoints = json.loads(ports.read_text())
    # 2. Recipes exactly as WAM leaves them: <store>/apps/<id>/{wizard.md,.wizard-commit}.
    apps = []
    for app_id, src, commit, store in (("wisdom", STAGE / "wisdom-src", os.environ["WISDOM_COMMIT"], "wizardapps"),
                                       ("router-fixture", HERE / "fixture" / "router-fixture", "f" * 40, "wizardapps")):
        dst = w / "recipes" / store / "apps" / app_id
        dst.mkdir(parents=True)
        shutil.copy(src / "wizard.md", dst / "wizard.md")
        (dst / ".wizard-commit").write_text(commit + "\n")
        apps.append({"id": app_id, "name": "Wisdom" if app_id == "wisdom" else "Router Fixture", "status": "running",
                     "urn": f"{app_id}:{store}", "commit": commit, "version": manifest_version(dst / "wizard.md"),
                     "provides": [], "view": {"url": f"/{app_id}/"}})
    apps += [
        {"id": "wizard-claude", "name": "Claude", "status": "running", "urn": "wizard-claude:core", "version": "0.2.2",
         "provides": ["ai-connection", "claude-subscription"], "view": {"url": "/wizard-claude/"}},
        {"id": "wizard-chatgpt", "name": "ChatGPT", "status": "running", "urn": "wizard-chatgpt:core", "version": "0.2.1",
         "provides": ["ai-connection", "chatgpt-subscription"], "view": {"url": "/wizard-chatgpt/"}},
        {"id": "wizard-connection-router", "name": "Connection Router", "status": "running",
         "urn": "wizard-connection-router:wizardapps", "version": "0.1.4", "provides": ["connection-router"]},
    ]
    (w / "registry" / "apps.json").write_text(json.dumps({"schema": 1, "apps": apps, "slots": {}}, indent=1))
    # 3. Grants: enforcement on, one incoming grant per adopter, owner-side provider addresses (as on Telos).
    tokens = {a: secrets.token_urlsafe(24) for a in ("wisdom", "router-fixture")}
    secrets_file(state).write_text(json.dumps(tokens))
    (w / "grants" / "grants.json").write_text(json.dumps({
        "enforce": True,
        "incoming": [{"from": a, "sha256": hashlib.sha256(t.encode()).hexdigest()} for a, t in tokens.items()],
        "outgoing": {}, "provider_endpoints": endpoints}, indent=1))
    shutil.copy(w / "registry" / "apps.json", ev / "apps.json")   # credential-free; the Store feed reads it too
    sh("chown", "-R", "1000:1000", str(w / "state"))
    # 4. Router: the published image, read-only registry/grants/recipes, host network so it reaches loopback fakes.
    sh("docker", "run", "-d", "--name", "router", "--network", "host", "--user", "1000:1000", "--read-only",
       "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
       "-e", "WIZARD_ROUTER_BIND=127.0.0.1", "-e", f"WIZARD_ROUTER_PORT={RPORT}",
       "-e", "WIZARD_APPS_JSON=/run/wizard/apps.json", "-e", "WIZARD_GRANTS_FILE=/run/grants/grants.json",
       "-e", "WIZARD_RECIPES_DIR=/run/recipes", "-e", "WIZARD_ROUTER_DATA_DIR=/data",
       "-v", f"{w}/registry:/run/wizard:ro", "-v", f"{w}/grants:/run/grants:ro", "-v", f"{w}/recipes:/run/recipes:ro",
       "-v", f"{w}/state:/data", ROUTER_IMAGE)
    # 5. Wisdom: built from its pinned commit, same hardening flags as its Runtipi compose, wired to the Router.
    sh("docker", "run", "-d", "--name", "wisdom", "--network", "host", "--read-only", "--tmpfs", "/tmp",
       "--cap-drop", "ALL", "--cap-add", "CHOWN", "--cap-add", "SETUID", "--cap-add", "SETGID",
       "--security-opt", "no-new-privileges:true",
       "-e", "WISDOM_BASE=", "-e", "WISDOM_CONTAINER=1", "-e", f"WISDOM_PORT={WPORT}", "-e", "WISDOM_DATA=/data",
       "-e", "WISDOM_LIBRARY=/media/Wisdom", "-e", "WISDOM_ADMIT=disabled", "-e", "WISDOM_WIZARD_ORIGIN=",
       "-e", f"WISDOM_ROUTER_URL={R}", "-e", f"WISDOM_ROUTER_GRANT={tokens['wisdom']}",
       "-v", f"{w}/wisdom-data:/data", "-v", f"{w}/wisdom-media:/media/Wisdom", WISDOM_IMAGE)
    ok = {}
    for name, url in (("router", R + "/health"), ("wisdom", f"http://127.0.0.1:{WPORT}/healthz")):
        for _ in range(120):
            try:
                if http("GET", url, timeout=2)[0] == 200:
                    ok[name] = True
                    break
            except OSError:
                pass
            time.sleep(.5)
    images = {n: sh("docker", "inspect", "-f", "{{.Image}}", n).stdout.strip() for n in ("router", "wisdom")}
    (ev / "up.json").write_text(json.dumps({"state": state, "healthy": ok, "image_ids": images,
                                            "router_image": ROUTER_IMAGE, "provider_endpoints": endpoints}, indent=1))
    print("UP", state, ok, flush=True)
    if set(ok) != {"router", "wisdom"}:
        print(sh("docker", "logs", "router", check=False).stderr[-2000:], sh("docker", "logs", "wisdom", check=False).stderr[-2000:])
        sys.exit(1)


WISDOM_NEEDS = """
import json, os, urllib.request
r = urllib.request.Request(os.environ['WISDOM_ROUTER_URL'] + '/v1/needs', headers={'X-Wizard-Grant': os.environ['WISDOM_ROUTER_GRANT']})
try:
    print(urllib.request.urlopen(r, timeout=20).read().decode())
except urllib.error.HTTPError as e:
    print(json.dumps({'http_status': e.code, 'body': json.loads(e.read() or b'{}')}))
"""


def collect(state, phase):
    ev, tokens = evidence(state), json.loads(secrets_file(state).read_text())
    endpoints = json.loads((WORK / state / "fakes" / "ports.json").read_text())
    out = {"state": state, "phase": phase, "at": int(time.time())}
    out["provider_status"] = {pid: http("GET", url + "/api/connection")[1] for pid, url in endpoints.items()}
    out["owner_needs"] = {a: http("GET", f"{R}/v1/owner/needs/{a}")[1] for a in ("wisdom", "router-fixture")}
    # The app's own view, asked with the app's own grant: Wisdom from inside its container.
    w = sh("docker", "exec", "wisdom", "python3", "-c", WISDOM_NEEDS)
    out["needs"] = {"wisdom": json.loads(w.stdout),
                    "router-fixture": http("GET", R + "/v1/needs", headers={"X-Wizard-Grant": tokens["router-fixture"]})[1]}
    out["needs_unknown_grant"] = http("GET", R + "/v1/needs", headers={"X-Wizard-Grant": "not-a-grant"})
    out["owner_routes"] = http("GET", R + "/v1/owner/routes")[1]
    (ev / f"{phase}.json").write_text(json.dumps(out, indent=1))
    print("COLLECTED", state, phase, flush=True)


# Wisdom's two live router features go through its own adopter code (model_router.request + admit); chapter
# authoring has no runtime caller at this commit, so it is called with Wisdom's grant on the same route.
WISDOM_RUNS = r"""
import json, os, sys, urllib.request, urllib.error
sys.path.insert(0, '/app')
import model_router
out = {}
payload = {'system': 'Acceptance probe.', 'quote': 'probe', 'sources': [], 'source_links_not_read': [],
           'messages': [{'role': 'user', 'content': 'Say hello.'}], 'web_enabled': False}
for feature in ('ask-ai', 'look-up'):
    try:
        with model_router.request(feature, payload, 30) as resp:
            events = [json.loads(line) for line in resp]
        out[feature] = {'ok': True, 'via': 'wisdom model_router', 'events': events}
    except model_router.Fault as e:
        out[feature] = {'ok': False, 'via': 'wisdom model_router', 'fault': e.public()}
req = urllib.request.Request(os.environ['WISDOM_ROUTER_URL'] + '/v1/models/chapter-authoring/run',
    data=json.dumps({'system': 'Acceptance probe.', 'messages': [{'role': 'user', 'content': 'Say hello.'}],
                     'max_tokens': 64}).encode(),   # chapter-authoring declares no abilities; send none
    headers={'Content-Type': 'application/json', 'X-Wizard-Grant': os.environ['WISDOM_ROUTER_GRANT']})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode()
        out['chapter-authoring'] = {'ok': True, 'via': 'router run (wisdom grant)', 'http_status': r.status,
            'events': [json.loads(l[5:]) for l in body.splitlines() if l.startswith('data:')]}
except urllib.error.HTTPError as e:
    out['chapter-authoring'] = {'ok': False, 'via': 'router run (wisdom grant)', 'http_status': e.code, 'body': json.loads(e.read() or b'{}')}
print(json.dumps(out))
"""


def runs(state, phase):
    ev, tokens = evidence(state), json.loads(secrets_file(state).read_text())
    out = {"state": state, "phase": phase, "at": int(time.time())}
    w = sh("docker", "exec", "wisdom", "python3", "-c", WISDOM_RUNS)
    out["wisdom"] = json.loads(w.stdout)
    out["router-fixture"] = {}
    for feature, abilities in (("summarize", ["text", "streaming"]), ("draft", ["text", "streaming"]), ("classify", ["text"])):
        out["router-fixture"][feature] = dict(zip(("http_status", "events"), http(
            "POST", f"{R}/v1/models/{feature}/run", {"system": "Acceptance probe.", "max_tokens": 64,
                                                      "messages": [{"role": "user", "content": "Say hello."}], "abilities": abilities},
            headers={"X-Wizard-Grant": tokens["router-fixture"]})))
    out["owner_routes_after"] = http("GET", R + "/v1/owner/routes")[1]
    # Wisdom still installs and opens: its health and first screen answer whatever the providers say.
    s, page = http("GET", f"http://127.0.0.1:{WPORT}/")
    out["wisdom_opens"] = {"status": s, "is_html": isinstance(page, str) and "<html" in page.lower(),
                           "health": http("GET", f"http://127.0.0.1:{WPORT}/healthz")[0]}
    (ev / f"runs-{phase}.json").write_text(json.dumps(out, indent=1))
    print("RUNS", state, phase, flush=True)


def order(state, providers):
    s, body = http("POST", R + "/v1/owner/provider-order", {"providers": [p for p in providers.split(",") if p]})
    (evidence(state) / f"order-{providers.replace(',', '_') or 'empty'}.json").write_text(json.dumps({"status": s, "body": body}))
    print("ORDER", s, body, flush=True)


def down(state, quiet=False):
    if not quiet:
        for n in ("router", "wisdom"):
            r = sh("docker", "logs", n, check=False)
            (evidence(state) / f"{n}.log").write_text(r.stdout + r.stderr)
    sh("docker", "rm", "-f", "router", "wisdom", check=False)
    pid = WORK / state / "fakes" / "pid"
    if pid.exists():
        try:
            os.killpg(int(pid.read_text()), 15)
        except (ProcessLookupError, ValueError):
            pass
    if not quiet:
        print("DOWN", state, flush=True)


if __name__ == "__main__":
    cmd, state, *rest = sys.argv[1:]
    {"up": lambda: up(state), "collect": lambda: collect(state, rest[0]), "runs": lambda: runs(state, rest[0]),
     "order": lambda: order(state, rest[0] if rest else ""), "down": lambda: down(state)}[cmd]()
