#!/usr/bin/env python3
"""Card-5 callers, base vs candidate (wizard-os issue 386). Synthetic, loopback only.

  card5-callers-e2e.py base|candidate <out.json>

Providers are the same in both runs and are the real card-5 fronts with the boundary ON and their grants file
`enforce: true` (the state the boundary is meant to reach):
- Transcriber front (oscarhenrycollins/transcriber#1 head), engine = a stub OpenAI-compatible /v1 API;
- Browser front (oscarhenrycollins/browser#2 head, WIZARD_PEER_GATE=require as its compose sets) over a real
  chrome-headless-shell.
Callers are the real code of the checkout under test:
- Agent Service speech-to-text (`createWizardServer`, /wizard/voice/status + /wizard/voice/transcribe): base = Service
  #316 head, candidate = the STT gateway-key branch. Its key comes from grants/agent-service.json as WAM #421 writes it.
- Voice `providers._request_text` (packaged local-engine profile; only the socket target is moved from
  transcriber:8000 to the local front port): base = wizard-voice-service#9 head, candidate = the grant-key branch.
- DeFleur Video `transcriber.status()`, `workflow.browser_status()` and the real `capture-remote.cjs` smoke capture
  through puppeteer-core: base = defleur-video main, candidate = the grant-key branch. Its keys come from its own
  grants file (`outgoing`), as the App Manager backend writes it for `uses: [transcriber, browser, files]`.
"""
import hashlib
import http.client
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MODE, OUT = sys.argv[1], sys.argv[2]
S = Path(os.path.expanduser("~/.hermes/cache/scratch"))
CK = {
    "transcriber": S / "bt-card5/transcriber", "browser": S / "bt-card5/browser",
    "svc": {"base": S / "bt-card5/wizard-agent-service", "candidate": S / "bt-hd/wt/svc"}[MODE],
    "voice": {"base": S / "bt-card5/wizard-voice-service", "candidate": S / "bt-hd/wt/voice"}[MODE],
    "video": {"base": None, "candidate": S / "bt-hd/defleur-video"}[MODE],
}
PY_VOICE = str(S / "vvenv/bin/python")
CHROME = os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/"
                            "chrome-headless-shell")
D = Path(tempfile.mkdtemp(prefix=f"c5callers-{MODE}-"))
procs, rows = [], []


def free():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait(port, n=300):
    for _ in range(n):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return
        except OSError:
            time.sleep(0.1)
    raise SystemExit(f"port {port} never opened")


def start(args, env=None, cwd=None, log=None):
    p = subprocess.Popen(args, env={**os.environ, **(env or {})}, cwd=cwd, start_new_session=True,
                         stdout=open(log, "w") if log else subprocess.DEVNULL, stderr=subprocess.STDOUT)
    procs.append(p)
    return p


def row(caller, request, result):
    rows.append({"caller": caller, "request": request, "result": result})
    print(f"{caller:<40} {request:<52} {result}")


def front(k, app, port, upstream, extra):
    src = (CK[k] / "mcp/front.py").read_text() + "\n\n" + (CK[k] / "mcp/tools.py").read_text() + \
        '\n\nif __name__ == "__main__":\n    asyncio.run(main())\n'
    f = D / f"{app}-front.py"
    f.write_text(src)
    start([sys.executable, str(f)], {"WIZARD_APP": app, "FRONT_PORT": str(port), "UPSTREAM_HOST": "127.0.0.1",
                                     "UPSTREAM_PORT": str(upstream), "TRANSCRIBER_MODEL": "stub-whisper",
                                     "WIZARD_BROWSER_BOUNDARY": "1", **extra}, log=D / f"{app}.log")


try:
    ports = {k: free() for k in ("engine", "chrome", "transcriber", "browser", "svc")}
    keys = {k: secrets.token_hex(32) for k in ("gateway", "voice", "video-t", "video-b", "browser-gw")}
    sha = lambda k: hashlib.sha256(keys[k].encode()).hexdigest()
    stub = D / "engine.py"
    stub.write_text('''import json,sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def _send(self, b):
        self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        self._send(json.dumps({"data":[{"id":"stub-whisper","task":"automatic-speech-recognition"}]}).encode())
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._send(json.dumps({"text":"synthetic words","segments":[{"text":"synthetic words","no_speech_prob":0.01}]}).encode())
    def log_message(self,*a): pass
ThreadingHTTPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()
''')
    start([sys.executable, str(stub), str(ports["engine"])])
    start([CHROME, "--headless", f"--remote-debugging-port={ports['chrome']}", "--remote-debugging-address=127.0.0.1",
           f"--user-data-dir={D / 'chrome'}", "--no-first-run", "--no-sandbox"])
    wait(ports["engine"]); wait(ports["chrome"])
    # Provider grants files (App Manager layer 2, enforce on): who may call the Transcriber engine / Browser DevTools.
    tg = D / "transcriber-grants.json"
    tg.write_text(json.dumps({"outgoing": {}, "enforce": True, "incoming": [
        {"from": "host:agent-service", "sha256": sha("gateway")}, {"from": "wizard-voice-service", "sha256": sha("voice")},
        {"from": "defleur-video", "sha256": sha("video-t")}]}))
    bg = D / "browser-grants.json"
    bg.write_text(json.dumps({"outgoing": {}, "enforce": True, "incoming": [{"from": "defleur-video", "sha256": sha("video-b")}]}))
    front("transcriber", "transcriber", ports["transcriber"], ports["engine"],
          {"WIZARD_GATEWAY_KEY": keys["gateway"], "WIZARD_GRANTS_FILE": str(tg)})
    front("browser", "browser", ports["browser"], ports["chrome"],
          {"WIZARD_GATEWAY_KEY": keys["browser-gw"], "WIZARD_GRANTS_FILE": str(bg), "WIZARD_PEER_GATE": "require"})
    wait(ports["transcriber"]); wait(ports["browser"])
    T = f"http://127.0.0.1:{ports['transcriber']}"
    B = f"http://127.0.0.1:{ports['browser']}"

    # 0. The fronts themselves: a keyless box peer.
    def get(port, path, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        c.request("GET", path, headers=headers or {})
        r = c.getresponse()
        r.read()
        c.close()
        return r.status
    row("keyless box peer", "Transcriber GET /v1/models (enforce on)", get(ports["transcriber"], "/v1/models"))
    row("keyless box peer", "Browser GET /json/version", get(ports["browser"], "/json/version"))

    # 1. Agent Service speech-to-text.
    home = D / "wos"
    (home / "grants").mkdir(parents=True)
    (home / "apps.json").write_text(json.dumps({"apps": [{"id": "transcriber", "name": "Transcriber", "status": "running",
                                                          "provides": ["transcription"], "mcp": {"url": f"{T}/mcp"}}]}))
    gf = home / "grants" / "agent-service.json"
    gf.write_text(json.dumps({"outgoing": {"transcriber": keys["gateway"]}}))
    gf.chmod(0o600)
    nm = CK["svc"] / "node_modules"
    if not nm.exists():
        nm.symlink_to(S / "bt-files/wt/svc/node_modules")
    svc = D / "svc.mjs"
    svc.write_text(f"""
import {{ createWizardServer, listen }} from '{CK["svc"]}/server/service.mjs'
const s = createWizardServer({{ joinedDelegation: 'prefer', requireAccess: false, followThrough: false, hermesKey: 'fixture',
  upstreamOrigin: 'http://127.0.0.1:9', sttOrigin: '{T}', appsJsonPath: '{home}/apps.json', wizardOsHome: '{home}' }})
await listen(s, '127.0.0.1', {ports['svc']})
""")
    start(["node", str(svc)], log=D / "svc.log")
    wait(ports["svc"])
    c = http.client.HTTPConnection("127.0.0.1", ports["svc"], timeout=60)
    c.request("GET", "/wizard/voice/status")
    st = json.loads(c.getresponse().read())
    c.close()
    row("Agent Service STT", "GET /wizard/voice/status", {"ready": st.get("ready"), "name": st.get("name")})
    c = http.client.HTTPConnection("127.0.0.1", ports["svc"], timeout=60)
    c.request("POST", "/wizard/voice/transcribe", body=b"synthetic audio", headers={"Content-Type": "audio/webm"})
    r = c.getresponse()
    row("Agent Service STT", "POST /wizard/voice/transcribe", {"status": r.status, "body": json.loads(r.read() or b"{}")})
    c.close()

    # 2. Voice -> Transcriber (packaged local engine route).
    vg = D / "voice-grants.json"
    vg.write_text(json.dumps({"outgoing": {"transcriber": keys["voice"]}, "incoming": [], "enforce": False}))
    vcfg = D / "voice-config.yaml"
    shutil.copy(CK["voice"] / "packaging/default-config.yaml", vcfg)
    audio = D / "synthetic.mp3"
    audio.write_bytes(b"unit-fixture")
    code = f"""
import json, providers
from config import load_provider_config, is_local_transcriber
c = load_provider_config()
real = providers._open_transcription
def to_front(request, *, timeout):
    assert request.full_url == c.endpoint
    request.full_url = '{T}/v1/audio/transcriptions'
    return real(request, timeout=timeout)
providers._open_transcription = to_front
try:
    print(json.dumps({{'local_engine': is_local_transcriber(c), 'text': providers._request_text(__import__('pathlib').Path('{audio}'), c, '')}}))
except Exception as e:
    print(json.dumps({{'local_engine': is_local_transcriber(c), 'error': str(e)[:160]}}))
"""
    r = subprocess.run([PY_VOICE, "-c", code], cwd=CK["voice"], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "WIZARD_VOICE_CONFIG": str(vcfg), "WIZARD_GRANTS_FILE": str(vg)})
    row("Voice (real provider code)", "POST /v1/audio/transcriptions", json.loads((r.stdout or "{}").strip().splitlines()[-1]))

    # 3. DeFleur Video -> Transcriber and Browser.
    video = CK["video"]
    if video is None:   # base: defleur-video main
        video = D / "video-main"
        video.mkdir()
        subprocess.run(f"git -C {S / 'bt-hd/defleur-video'} archive origin/main | tar -x -C {video}", shell=True, check=True)
        (video / "capture" / "node_modules").symlink_to(S / "bt-hd/defleur-video/capture/node_modules")
    dg = D / "video-grants.json"
    dg.write_text(json.dumps({"outgoing": {"transcriber": keys["video-t"], "browser": keys["video-b"], "files": secrets.token_hex(32)},
                              "incoming": [], "enforce": False,
                              "provider_endpoints": {"transcriber": T, "browser": B}}))
    venv = {**os.environ, "WIZARD_GRANTS_FILE": str(dg), "TRANSCRIBER_URL": T, "BROWSER_URL": B,
            "VIDEO_CAPTURE_DIR": str(video / "capture")}
    code = """
import json, transcriber, workflow
t = transcriber.status()
b = workflow.browser_status()
print(json.dumps({'transcriber_reachable': t.get('reachable'), 'browser_reachable': b.get('reachable'), 'browser_error': b.get('error', '')[:80]}))
"""
    r = subprocess.run([sys.executable, "-c", code], cwd=video, capture_output=True, text=True, timeout=60, env=venv)
    row("DeFleur Video (real code)", "transcriber.status / workflow.browser_status",
        json.loads((r.stdout or "{}").strip().splitlines()[-1]) if r.stdout.strip() else r.stderr[-300:])
    # The real capture-remote.cjs (smoke) against Browser through its front, a 2-frame synthetic project.
    proj = D / "proj"
    (proj / "base_frames").mkdir(parents=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64", "-frames:v", "1",
                    str(proj / "base_frames" / "000000.jpg")], check=True)
    (proj / "package.json").write_text('{"private": true}')
    (proj / "locked-timeline.json").write_text(json.dumps({"fps": "10", "frames": 2, "duration": 0.2, "canvas": [64, 64]}))
    (proj / "index.html").write_text("<!doctype html><body style=margin:0><img id=live width=64 height=64><script>"
                                     "window.sourceFrameForOutputFrame=f=>0;window.renderFrame=t=>{};</script></body>")
    grant = ""
    if (video / "workflow.py").read_text().count("browser_grant"):
        grant = subprocess.run([sys.executable, "-c", f"import workflow; print(workflow.browser_grant('{B}'))"], cwd=video,
                               capture_output=True, text=True, env=venv).stdout.strip()
    r = subprocess.run(["node", str(video / "capture" / "capture-remote.cjs"), str(proj), "smoke"], cwd=proj,
                       capture_output=True, text=True, timeout=120,
                       env={**venv, "BROWSER_GRANT": grant, "NODE_PATH": str(video / "capture" / "node_modules")})
    cap = proj / "capture-smoke.json"
    row("DeFleur Video capture-remote.cjs", "smoke capture via Browser (CDP)",
        {"exit": r.returncode, "frames": json.loads(cap.read_text())["frame_count"] if cap.is_file() else 0,
         "error": (r.stderr.strip().splitlines() or [""])[0][:140]})
finally:
    for p in procs:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    Path(OUT).write_text(json.dumps({"mode": MODE, "rows": rows}, indent=2) + "\n")
    shutil.rmtree(D, ignore_errors=True)
