#!/usr/bin/env python3
"""Guest half of the 0.2.2 AI-workflow acceptance. Invoked only by e2e_022_ai_flow.py.

Sent over `limactl shell ... python3 - <command> <run_id> [json]` on stdin. Subcommands:
  preflight  account status (read once), DeFleur via real WAM, digests, clip, skills/config "before"
  snapshot   media "before" listing, right before the DeFleur request is sent
  poll       cheap new-video check against that snapshot (no hashing)
  final      media diff + ffprobe, skills diff + pointer verdicts, config/session model readback

stdout is one allowlisted JSON receipt. Never prints raw command output, Docker env,
HTTP bodies, .env values, auth stores, or full config.yaml. Never writes media itself
except the synthetic SOURCE clip when none can be reused.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit
import wave

APP_ID = 'defleur-video'
APP_SHA = '76c544a75515f41d49317a625fdf40e63d0b8176'
IMAGE_DIGEST = 'sha256:d837622c977e1d868bfbb331f5f61fc3040d2ee89b0218e4f1f73a84aa6b4b57'
VERSION = '0.7.0-testing'
HERMES_IMAGE_DIGEST = 'sha256:ac89f5f9fa16eda6c7aba3de3ba7235da3d867914e3ae2dcf13135ee078fd3b0'
MODEL = 'claude-opus-5-5'
PROVIDER = 'claude-subscription-directsdk-experimental'
# WAM PR #56 commit carrying `wam agent-link` (fresh-mode gateway link, the 0.2.2 fresh-box gap).
AGENT_LINK_WAM = '07a901c155cdf4356bb80d8dfa237613800d614f'
ACCOUNTS_PORT = 8795  # AI Accounts guest-loopback port; status API only, page never opened
CLIP_NAME = 'release-acceptance-source.mp4'
SPEECH = 'This is a release acceptance test. Please trim the pauses and add captions.'
VIDEO_EXT = ('.mp4', '.mov', '.m4v', '.mkv', '.webm', '.avi')
POINTER_MAX_LINES = 60
CONTAINER_KEYS = ('hermes-agent', 'wizard-ux', 'wizard-agent-service', 'defleur-video')
REPORT: dict = {'stages': [], 'commands': []}

# Parsed in a privileged child as well (config.yaml is container-owned); one source of truth.
MODEL_KEYS_SRC = r'''
def model_keys(text):
    """Return ONLY model.provider/model.default from Hermes config.yaml text (no YAML lib)."""
    import re as _re
    def scalar(v):
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
            v = v[1:-1]
        return None if v in ('', 'null', '~', 'Null', 'NULL') else v
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = _re.match(r'^model:(?:\s+(.*?))?\s*$', line)
        if not m:
            continue
        val = _re.sub(r'\s+#.*$', '', m.group(1) or '')
        if val and val not in ('|', '>'):
            return {'shape': 'scalar', 'provider': None, 'default': scalar(val)}
        out, indent = {}, None
        for nxt in lines[i + 1:]:
            if not nxt.strip() or nxt.lstrip().startswith('#'):
                continue
            lead = len(nxt) - len(nxt.lstrip())
            if lead == 0:
                break
            if indent is None:
                indent = lead
            if lead != indent:
                continue
            mm = _re.match(r'^\s+(default|provider):(?:\s+(.*?))?\s*$', nxt)
            if mm:
                out[mm.group(1)] = scalar(_re.sub(r'\s+#.*$', '', mm.group(2) or ''))
        return {'shape': 'mapping', 'provider': out.get('provider'), 'default': out.get('default')}
    return {'shape': 'absent', 'provider': None, 'default': None}
'''
exec(MODEL_KEYS_SRC)

SKILLS_SRC = r'''
import hashlib, json, os, sys
root = sys.argv[1]
out = {}
if os.path.isdir(root):
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.git'))
        for f in sorted(files):
            p = os.path.join(d, f)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            rel = os.path.relpath(p, root)
            data = open(p, 'rb').read()
            row = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
            if f == 'SKILL.md' and b'defleur' in data.lower() and len(data) < 262144:
                row['text'] = data.decode('utf-8', 'replace')
            out[rel] = row
print(json.dumps(out))
'''

MEDIA_SRC = r'''
import json, os, sys
root, exts = sys.argv[1], tuple(sys.argv[2].split(','))
out = {}
for d, dirs, files in os.walk(root):
    dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
    for f in files:
        if not f.lower().endswith(exts):
            continue
        p = os.path.join(d, f)
        try:
            st = os.stat(p)
        except OSError:
            continue
        out[os.path.relpath(p, root)] = [st.st_size, st.st_mtime_ns]
print(json.dumps(out))
'''

SESSIONS_SRC = r'''
import json, sqlite3, sys
db, ids = sys.argv[1], json.loads(sys.argv[2])
con = sqlite3.connect('file:' + db + '?mode=ro', uri=True, timeout=10)
cols = [r[1] for r in con.execute('PRAGMA table_info(sessions)')]
want = [c for c in ('id', 'model', 'billing_provider', 'provider', 'source') if c in cols]
out = {}
if 'id' in want:
    for sid in ids:
        row = con.execute('SELECT %s FROM sessions WHERE id = ?' % ','.join(want), (sid,)).fetchone()
        out[sid] = dict(zip(want, row)) if row else None
print(json.dumps({'columns': want, 'sessions': out}))
'''


class CheckError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CheckError(message)


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return digest_bytes(Path(path).read_bytes())


DIAGNOSTIC_TOOLS = {'apt-get', 'install', 'ffmpeg', 'ffprobe', 'espeak-ng'}


def run(argv, timeout=90, data=None):
    argv = [str(a) for a in argv]
    try:
        p = subprocess.run(argv, input=data, stdin=None if data is not None else subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=timeout)
        REPORT['commands'].append({'argv': argv[:3] + (['…'] if len(argv) > 3 and argv[0] == 'sudo' and argv[3] == '-c' else argv[3:]),
                                   'exit_code': p.returncode})
    except subprocess.TimeoutExpired:
        REPORT['commands'].append({'argv': argv[:3], 'exit_code': 124})
        raise CheckError('command timeout; output suppressed') from None
    if p.returncode != 0:
        # Package/media tools only: their stderr is diagnostic, never credential-bearing.
        tool = next((a for a in argv if not a.startswith('-') and a not in ('sudo', 'env') and '=' not in a), '')
        if Path(tool).name in DIAGNOSTIC_TOOLS:
            REPORT['commands'][-1]['stderr_tail'] = (p.stderr or '')[-600:]
            raise CheckError('%s failed (exit %d); see stderr_tail' % (Path(tool).name, p.returncode))
    require(p.returncode == 0, 'command failed; output suppressed')
    return p.stdout.strip()


def sudo_py(src, *args, timeout=300):
    return json.loads(run(['sudo', '-n', 'python3', '-c', src, *args], timeout=timeout))


def sudo_exists(path):
    # Container-owned paths: existence only (never read).
    return subprocess.run(['sudo', '-n', 'test', '-e', str(path)], stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30).returncode == 0


def stage(name, fn):
    try:
        value = fn()
        REPORT['stages'].append({'stage': name, 'status': 'pass', 'result': value})
        return value
    except Exception as e:
        REPORT['stages'].append({'stage': name, 'status': 'fail',
                                'reason': str(e) if isinstance(e, CheckError) else type(e).__name__})
        return None


# ---------------------------------------------------------------- pure helpers (unit tested)

def new_videos(before, after):
    """Paths that are new or changed (size/mtime) between two {rel: [size, mtime_ns]} listings."""
    out = []
    for rel, meta in sorted(after.items()):
        if not rel.lower().endswith(VIDEO_EXT):
            continue
        if rel not in before or list(before[rel]) != list(meta):
            out.append(rel)
    return out


def norm_line(line):
    return re.sub(r'\s+', ' ', line.strip().lstrip('#>-*0123456789. ')).lower()


def classify_skill(text, app_skill_text, max_lines=POINTER_MAX_LINES):
    """Is a Hermes SKILL.md mentioning DeFleur a short POINTER rather than a copy of the app's skill?"""
    lower = text.lower()
    if 'defleur' not in lower:
        return {'relevant': False}
    lines = [l for l in text.splitlines()]
    app_lines = {norm_line(l) for l in (app_skill_text or '').splitlines() if len(norm_line(l)) >= 40}
    copied = sorted({norm_line(l) for l in lines if norm_line(l) in app_lines})
    identical = bool(app_skill_text) and text.strip() == app_skill_text.strip()
    refs = [k for k in ('defleur-video', 'mcp', 'installed', 'app-owned', 'wizard app', 'skill', 'app')
            if k in lower]
    reasons = []
    if identical:
        reasons.append('identical to installed DeFleur SKILL.md')
    if len(lines) > max_lines:
        reasons.append('longer than %d lines' % max_lines)
    ratio = (len(copied) / len(app_lines)) if app_lines else 0.0
    if len(copied) >= 5 or ratio >= 0.2:
        reasons.append('inlines %d substantive lines of the installed DeFleur SKILL.md' % len(copied))
    if not refs:
        reasons.append('does not reference the installed DeFleur app, its MCP, or its skill')
    return {'relevant': True, 'pointer': not reasons, 'line_count': len(lines),
            'copied_app_lines': len(copied), 'copied_ratio': round(ratio, 3),
            'references': refs, 'reasons': reasons}


def skills_diff(before, after, app_skill_text):
    """Diff {rel: {sha256, bytes, text?}} maps; classify new/changed DeFleur SKILL.md files."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(after) & set(before) if after[k]['sha256'] != before[k]['sha256'])
    verdicts = []
    for rel in added + changed:
        row = after[rel]
        if Path(rel).name != 'SKILL.md' or 'text' not in row:
            continue
        v = classify_skill(row['text'], app_skill_text)
        if v.get('relevant'):
            verdicts.append({'path': rel, 'sha256': row['sha256'], 'change': 'added' if rel in added else 'changed', **v})
    strip = lambda m, keys: {k: {'sha256': m[k]['sha256'], 'bytes': m[k]['bytes']} for k in keys}
    if not verdicts:
        verdict = 'pass: no DeFleur skill copy written'
    elif all(v['pointer'] for v in verdicts):
        verdict = 'pass: DeFleur skill(s) written are pointers'
    else:
        verdict = 'fail: DeFleur workflow copied into a Hermes skill'
    return {'added': strip(after, added), 'changed': strip(after, changed), 'removed': removed,
            'defleur_skill_verdicts': verdicts, 'verdict': verdict, 'pass': verdict.startswith('pass'),
            'before_count': len(before), 'after_count': len(after)}


def clip_phrase(rel, listing):
    """What a person would type: the file name, plus its folder only when the name is ambiguous."""
    name = Path(rel).name
    same = [p for p in listing if Path(p).name == name]
    if len(same) <= 1:
        return name
    return '%s/%s' % (Path(rel).parent.name, name)


def account_status(payload):
    accounts = payload.get('accounts') if isinstance(payload, dict) else None
    require(isinstance(accounts, list) and accounts, 'AI Accounts status has no accounts')
    claude = [a for a in accounts if isinstance(a, dict) and 'claude' in json.dumps(
        {k: a.get(k) for k in ('id', 'name', 'provider', 'kind')}).lower()]
    row = claude[0] if claude else accounts[0]
    return {'status': row.get('status'), 'matched': 'claude' if claude else 'accounts[0]', 'count': len(accounts)}


# ---------------------------------------------------------------- guest facts

def owner_wam(x, *args, timeout=600):
    """Run WAM the way an owner's shell does (umask 022), not under this runner's private umask."""
    return run(['sh', '-c', 'umask 022; exec "$0" "$@"', str(x.home / '.wizard-os/bin/wam'), *args], timeout=timeout)


def containers():
    ids = run(['sudo', '-n', 'docker', 'ps', '-aq']).split()
    rows = []
    for cid in ids:
        raw = run(['sudo', '-n', 'docker', 'inspect', '--format',
                   '{{json .Name}}\t{{json .Config.Image}}\t{{json .Image}}\t{{json .State.Status}}', cid])
        name, ref, image, status = [json.loads(v) for v in raw.split('\t')]
        rows.append({'name': name.lstrip('/'), 'ref': ref, 'image_id': image, 'status': status})
    return rows


def image_digests():
    out = {}
    for row in containers():
        key = next((k for k in CONTAINER_KEYS if k in row['name'] or k in row['ref']), None)
        if not key:
            continue
        ds = json.loads(run(['sudo', '-n', 'docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', row['image_id']]))
        arch = run(['sudo', '-n', 'docker', 'image', 'inspect', '--format', '{{.Architecture}}', row['image_id']])
        out.setdefault(key, []).append({**row, 'repo_digests': ds, 'arch': arch})
    return out


def safe_app(row):
    return {k: row.get(k) for k in ('id', 'version', 'status', 'repo', 'commit', 'skill', 'provides')}


def wait_ready(home):
    probe = '''from wam.cli import Config
try:
    c = Config()
    rt = c.runtipi()
    data = rt.req('GET', '/marketplace/all', timeout=10)
    assert isinstance(data.get('appStores'), list)
except Exception:
    raise SystemExit(1)
'''
    deadline = time.monotonic() + 180
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        try:
            p = subprocess.run([sys.executable, '-c', probe], cwd=home / 'wizard-app-manager',
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=min(20, max(0.1, deadline - time.monotonic())))
            if p.returncode == 0:
                return {'attempts': attempts}
        except subprocess.TimeoutExpired:
            pass
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise CheckError('marketplace unavailable after 180 seconds')


def loopback_url(value):
    u = urlsplit(value)
    require(u.scheme == 'http' and u.port and not u.username and not u.password and not u.query,
            'unexpected endpoint shape')
    return f'http://127.0.0.1:{u.port}{u.path}'


def get_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        require(r.status == 200, 'unexpected HTTP status')
        return json.loads(r.read(1024 * 1024).decode())


class Ctx:
    def __init__(self, run_id):
        require(bool(re.fullmatch(r'ai-flow-[0-9TZ]+', run_id)), 'invalid evidence id')
        self.run_id = run_id
        self.home = Path.home()
        self.state = self.home / '.wizard-os'
        self.work = self.home / '.e2e-022-ai-flow' / run_id
        sys.path.insert(0, str(self.home / 'wizard-app-manager'))
        from wam.cli import Config
        self.c = Config()
        self.media = self.c.runtipi_root / 'media'
        self.hermes = self.c.runtipi_root / 'app-data' / 'wizardapps' / 'hermes-agent' / 'data'

    def registry(self):
        return {a['id']: a for a in json.loads((self.state / 'apps.json').read_text())['apps']}

    def save(self, name, value):
        p = self.work / name
        p.write_text(json.dumps(value))
        p.chmod(0o600)

    def load(self, name):
        return json.loads((self.work / name).read_text())

    def media_listing(self):
        return sudo_py(MEDIA_SRC, str(self.media), ','.join(VIDEO_EXT))

    def skills(self):
        return sudo_py(SKILLS_SRC, str(self.hermes / 'skills'))

    def config_model(self):
        cfg = self.hermes / 'config.yaml'
        src = MODEL_KEYS_SRC + '\nimport json, sys\nprint(json.dumps(model_keys(open(sys.argv[1]).read())))\n'
        return sudo_py(src, str(cfg))

    def app_skill_text(self):
        row = self.registry()[APP_ID]
        skill = self.state / row['skill']
        require(skill.resolve().is_relative_to(self.state.resolve()) and skill.is_file(), 'installed DeFleur skill missing')
        return skill.read_text()


def probe(path):
    info = json.loads(run(['sudo', '-n', 'ffprobe', '-v', 'error', '-show_entries',
                           'format=duration,format_name:stream=codec_type,codec_name,width,height,duration',
                           '-of', 'json', path], timeout=120))
    return info


def valid_video(info):
    try:
        duration = float(info['format']['duration'])
    except (KeyError, TypeError, ValueError):
        return False
    return duration > 0 and any(s.get('codec_type') == 'video' for s in info.get('streams', []))


# ---------------------------------------------------------------- subcommands

def preflight(x):
    x.work.mkdir(parents=True, exist_ok=False)
    REPORT.update(host=platform.node(), arch=platform.machine())
    require(platform.machine() == 'x86_64', 'AMD64 guest required')
    if stage('marketplace-ready', lambda: wait_ready(x.home)) is None:
        return

    def accounts():
        # Status API only (GET, guest loopback), read ONCE after it answers. The AI Accounts page is never opened.
        deadline, payload = time.monotonic() + 180, None
        while payload is None and time.monotonic() < deadline:
            try:
                payload = get_json(f'http://127.0.0.1:{ACCOUNTS_PORT}/api/accounts')
            except (OSError, ValueError, CheckError):
                time.sleep(3)
        require(payload is not None, 'AI Accounts status unavailable after 180 seconds')
        status = account_status(payload)
        require(status['status'] == 'connected', 'Claude subscription is not connected')
        return status
    stage('ai-accounts-status-connected', accounts)

    def defleur():
        apps = x.registry()
        row = apps.get(APP_ID)
        pinned = bool(row) and row.get('version') == VERSION and row.get('commit') == APP_SHA
        running = [r for r in containers() if APP_ID in r['ref'] and r['status'] == 'running']
        digest_ok = False
        if running:
            ds = json.loads(run(['sudo', '-n', 'docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', running[0]['image_id']]))
            digest_ok = any(d.endswith('@' + IMAGE_DIGEST) for d in ds)
        action = 'already-installed-at-pinned-digest'
        if not (pinned and len(running) == 1 and digest_ok):
            action = 'wam-install'
            owner_wam(x, 'install', APP_ID, timeout=2400)
        row = x.registry()[APP_ID]
        require(row['version'] == VERSION and row['commit'] == APP_SHA, 'DeFleur source/version drift')
        require(row['repo'] == 'humanitylabs-org/defleur-video', 'unexpected DeFleur publisher')
        running = [r for r in containers() if APP_ID in r['ref']]
        require(len(running) == 1 and running[0]['status'] == 'running', 'DeFleur not uniquely running')
        ds = json.loads(run(['sudo', '-n', 'docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', running[0]['image_id']]))
        require(any(d.endswith('@' + IMAGE_DIGEST) for d in ds), 'DeFleur public digest mismatch')
        mounts = json.loads(run(['sudo', '-n', 'docker', 'inspect', '--format', '{{json .Mounts}}', running[0]['name']]))
        require(any(m['Destination'] == '/media' and Path(m['Source']).resolve() == x.media.resolve() for m in mounts),
                'DeFleur does not share the real Runtipi media root')
        health = loopback_url(row['health'])
        deadline = time.monotonic() + 180
        while True:
            try:
                with urllib.request.urlopen(health, timeout=10) as r:
                    if r.status == 200:
                        break
            except OSError:
                pass
            require(time.monotonic() < deadline, 'DeFleur health unavailable after 180 seconds')
            time.sleep(3)
        skill_text = x.app_skill_text()
        (x.work / 'defleur-app-skill.md').write_text(skill_text)
        return {'action': action, 'app': safe_app(row), 'repo_digests': ds,
                'installed_skill': {'path': row['skill'], 'sha256': digest_bytes(skill_text.encode()),
                                    'lines': len(skill_text.splitlines())}}
    stage('defleur-installed-pinned', defleur)

    def digests():
        found = image_digests()
        hermes = [d for r in found.get('hermes-agent', []) for d in r['repo_digests']]
        return {'containers': found, 'hermes_expected_digest': HERMES_IMAGE_DIGEST,
                'hermes_digest_match': any(d.endswith('@' + HERMES_IMAGE_DIGEST) for d in hermes),
                'missing': [k for k in CONTAINER_KEYS if k not in found]}
    REPORT['images'] = stage('image-digests-readback', digests)

    def clip():
        videos = x.media / 'Videos'
        reused = None
        if videos.is_dir():
            for folder in sorted(videos.glob('ui-proof-*'), reverse=True) + sorted(videos.glob('ai-flow-*'), reverse=True):
                cand = folder / CLIP_NAME
                if cand.is_file():
                    try:
                        info = probe(cand)
                    except CheckError:
                        continue
                    if valid_video(info) and 8 <= float(info['format']['duration']) <= 12:
                        reused = cand
                        break
        if reused is None:
            needed = [p for p in ('ffmpeg', 'espeak-ng') if not shutil.which(p)]
            if needed:
                run(['sudo', '-n', 'apt-get', 'update', '-qq'], timeout=300)
                run(['sudo', '-n', 'env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '-y', '-qq', *needed], timeout=600)
            if not videos.exists():
                run(['sudo', '-n', 'install', '-d', '-m', '755', '-o', str(os.getuid()), '-g', str(os.getgid()), videos])
            target = videos / x.run_id
            require(not target.exists(), 'synthetic target already exists')
            run(['sudo', '-n', 'install', '-d', '-m', '755', '-o', str(os.getuid()), '-g', str(os.getgid()), target])
            wav = x.work / 'synthetic-speech.wav'
            run(['espeak-ng', '-s', '165', '-w', wav, SPEECH])
            with wave.open(str(wav)) as w:
                require(1 < w.getnframes() / w.getframerate() < 9, 'speech duration would truncate')
            reused = target / CLIP_NAME
            run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
                 '-f', 'lavfi', '-i', 'color=c=0x263449:s=360x640:r=24', '-i', wav,
                 '-af', 'adelay=500|500,apad', '-t', '10', '-c:v', 'libx264', '-preset', 'ultrafast',
                 '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', reused], timeout=300)
            reused.chmod(0o644)
            created = True
        else:
            created = False
        info = probe(reused)
        require(valid_video(info), 'source clip invalid')
        rel = str(reused.relative_to(x.media))
        listing = x.media_listing()
        out = {'relative_path': rel, 'sha256': digest(reused), 'bytes': reused.stat().st_size,
               'ffprobe': info, 'created_now': created, 'synthetic_source_only': True,
               'phrase': clip_phrase(rel, listing)}
        x.save('source.json', out)
        return out
    REPORT['clip'] = stage('synthetic-source-clip', clip)

    def before():
        skills = x.skills()
        x.save('skills-before.json', skills)
        cfg = x.config_model()
        x.save('config-before.json', cfg)
        return {'skills_count': len(skills), 'config_model_keys': cfg,
                # Existence only; never read .env or auth stores.
                'hermes_home_present': {'config_yaml': sudo_exists(x.hermes / 'config.yaml'),
                                        'dotenv_file': sudo_exists(x.hermes / '.env'),
                                        'auth_json_file': sudo_exists(x.hermes / 'auth.json')}}
    stage('hermes-before', before)

    def owner_default_model():
        # Stock Hermes v2026.9.24 resolves its global default provider before honouring a
        # per-request model lock, so a fresh box with no default fails every chat ("not connected
        # to any AI provider"). Set exactly the owner's required route through the Hermes app's own
        # CLI, as the owner would with `hermes model`; no credentials are touched or copied.
        want = {'provider': PROVIDER, 'default': MODEL}
        cur = x.config_model()
        if cur.get('provider') == want['provider'] and cur.get('default') in (MODEL, MODEL + '[1m]'):
            return {'changed': False, 'before': cur, 'after': cur}
        engine = [r['name'] for r in containers() if 'hermes-agent-engine' in r['name'] and r['status'] == 'running']
        require(len(engine) == 1, 'running Hermes engine container not found')
        for key, value in (('model.provider', want['provider']), ('model.default', want['default'])):
            p = subprocess.run(['sudo', '-n', 'docker', 'exec', '-u', '1000:1000', engine[0], 'hermes', 'config', 'set', key, value],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180)
            REPORT['commands'].append({'argv': ['docker', 'exec', 'hermes', 'config', 'set', key, value], 'exit_code': p.returncode})
            require(p.returncode == 0, 'hermes config set %s failed: %s' % (key, (p.stderr or p.stdout)[-300:]))
        after = x.config_model()
        require(after.get('provider') == want['provider'] and after.get('default') == want['default'],
                'Hermes default model did not read back as the owner route')
        return {'changed': True, 'before': cur, 'after': after, 'method': 'hermes config set (app CLI, owner step)'}
    REPORT['owner_default_model'] = stage('owner-default-model', owner_default_model)

    def agent_sees_apps():
        # The Agent Service (another uid in its container) must be able to read the shared apps.json,
        # or the agent sees no installed apps at all. An earlier runner installed DeFleur under umask
        # 077, which left that share 0600; regenerate it with the owner's own `wam apps`.
        shared = x.c.runtipi_root / 'app-data/wizard-os/apps.json'
        mode_before = run(['sudo', '-n', 'stat', '-c', '%a', shared]).strip()
        action = 'none'
        if not (int(mode_before, 8) & 0o004):
            owner_wam(x, 'apps', '--json', timeout=600)
            action = 'regenerated-with-owner-umask'
        mode_after = run(['sudo', '-n', 'stat', '-c', '%a', shared]).strip()
        service = [r['name'] for r in containers() if 'wizard-agent-service' in r['name'] and r['status'] == 'running']
        require(len(service) == 1, 'Agent Service container not running')
        p = subprocess.run(['sudo', '-n', 'docker', 'exec', service[0], 'cat', '/wizard-os/apps.json'],
                           capture_output=True, text=True, timeout=60)
        require(p.returncode == 0, 'Agent Service cannot read the shared apps.json: ' + p.stderr[-200:])
        ids = [a.get('id') for a in json.loads(p.stdout).get('apps', [])]
        require(APP_ID in ids, 'DeFleur missing from the apps.json the Agent Service reads')
        defleur = next(a for a in json.loads(p.stdout)['apps'] if a.get('id') == APP_ID)
        internal = (defleur.get('mcp') or {}).get('internal') or (defleur.get('mcp') or {}).get('url')
        # Recorded, not asserted: can the Agent Service open DeFleur's MCP endpoint?
        reach_js = ("fetch(process.argv[1],{method:'POST',headers:{'content-type':'application/json',"
                    "accept:'application/json, text/event-stream'},body:JSON.stringify({jsonrpc:'2.0',id:1,"
                    "method:'initialize',params:{protocolVersion:'2025-06-18',capabilities:{},clientInfo:"
                    "{name:'e2e',version:'0'}}}),signal:AbortSignal.timeout(20000)}).then(r=>console.log(r.status))"
                    ".catch(e=>console.log('ERR '+(e.cause?.code||e.message)))")
        reach = None
        if internal:
            q = subprocess.run(['sudo', '-n', 'docker', 'exec', service[0], 'node', '-e', reach_js, internal],
                               capture_output=True, text=True, timeout=60)
            reach = (q.stdout or q.stderr).strip()[:120]
        # Hermes' MCP servers (names and urls only, never headers).
        src = """
import json, sys, yaml
c = yaml.safe_load(open(sys.argv[1])) or {}
print(json.dumps({k: (v or {}).get('url') for k, v in (c.get('mcp_servers') or {}).items()}))
"""
        try:
            hermes_mcp = sudo_py(src, str(x.hermes / 'config.yaml'))
        except (CheckError, ValueError):
            hermes_mcp = 'unreadable'
        # Wait for the bridge to publish DeFleur's job pointer skill.
        deadline, jobs = time.monotonic() + 240, []
        while time.monotonic() < deadline:
            q = subprocess.run(['sudo', '-n', 'docker', 'exec', service[0], 'sh', '-c',
                                'ls -1 "${WIZARD_OS_HOME:-/state/wizard-os}/skills" 2>/dev/null'],
                               capture_output=True, text=True, timeout=60)
            jobs = [l for l in q.stdout.split() if l.startswith('wizard-job-')]
            if any(j in jobs for j in ('wizard-job-video-editing', 'wizard-job-short-form-video')):
                break
            time.sleep(10)
        require(any(j in jobs for j in ('wizard-job-video-editing', 'wizard-job-short-form-video')),
                'bridge never published a DeFleur job pointer skill')
        return {'shared_mode_before': mode_before, 'shared_mode_after': mode_after, 'action': action,
                'service_app_ids': ids, 'defleur_mcp': internal, 'service_to_defleur_mcp': reach,
                'hermes_mcp_servers': hermes_mcp, 'bridge_jobs': jobs}
    REPORT['agent_sees_apps'] = stage('agent-sees-apps', agent_sees_apps)

    def agent_link():
        # Fresh mode shipped without connecting the hermes-agent app to the gateway (no mcp_servers.wizard,
        # no pointer skills). Apply the PR #56 fix from its exact public commit, as the owner (umask 022).
        src = x.work / ('wam-' + AGENT_LINK_WAM[:12])
        if not (src / 'wam/agent_link.py').is_file():
            src.mkdir(parents=True, exist_ok=True)
            tar = x.work / 'wam.tar.gz'
            run(['curl', '-fsSL', '-o', tar, 'https://codeload.github.com/humanitylabs-org/wizard-app-manager/tar.gz/' + AGENT_LINK_WAM], timeout=300)
            run(['tar', '-xzf', tar, '-C', src, '--strip-components=1'], timeout=120)
        p = subprocess.run(['sh', '-c', 'umask 022; cd "$0" && exec python3 -m wam agent-link', str(src)],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2400)
        REPORT['commands'].append({'argv': ['python3', '-m', 'wam', 'agent-link'], 'exit_code': p.returncode})
        # agent-link never prints the token; its stderr is a plain reason.
        require('{' in p.stdout, 'agent-link failed (exit %s): %s' % (p.returncode, (p.stderr or p.stdout)[-500:]))
        rec = json.loads(p.stdout[p.stdout.index('{'):])
        require(rec.get('linked') is True, 'agent-link did not verify the gateway: %s' % json.dumps(rec)[:400])
        require('wizard-job-video-editing' in (rec.get('skills_visible') or []), 'Hermes cannot see the DeFleur pointer skill')
        return {'wam_commit': AGENT_LINK_WAM, **rec}
    REPORT['agent_link'] = stage('agent-link', agent_link)

    shell = x.registry().get('wizard-ux', {})
    shell_url = (shell.get('view') or {}).get('url') or ''
    if shell_url.startswith('http://'):
        u = urlsplit(shell_url)
        REPORT['browser_target'] = {'guest_port': u.port or 80, 'path': u.path or '/'}
    else:
        cfg = x.c.runtipi_root / 'apps/wizardapps/wizard-ux/config.json'
        REPORT['browser_target'] = {'guest_port': int(json.loads(cfg.read_text())['port']), 'path': '/wizard-os-home/'}


def snapshot(x):
    def media():
        listing = x.media_listing()
        x.save('media-before.json', listing)
        return {'video_count': len(listing)}
    stage('media-before', media)


def poll(x):
    before = x.load('media-before.json')
    after = x.media_listing()
    REPORT['new_videos'] = {rel: after[rel][0] for rel in new_videos(before, after)}
    REPORT['stages'].append({'stage': 'poll', 'status': 'pass'})


def final(x, args):
    source = x.load('source.json')

    def media():
        before = x.load('media-before.json')
        after = x.media_listing()
        rows = []
        for rel in new_videos(before, after):
            path = x.media / rel
            sha = run(['sudo', '-n', 'sha256sum', path], timeout=300).split()[0]
            try:
                info = probe(path)
            except CheckError:
                info = {}
            decode_ok = True
            try:
                run(['sudo', '-n', 'ffmpeg', '-v', 'error', '-nostdin', '-i', path, '-f', 'null', '-'], timeout=600)
            except CheckError:
                decode_ok = False
            video = [s for s in info.get('streams', []) if s.get('codec_type') == 'video']
            rows.append({'relative_path': rel, 'bytes': after[rel][0], 'sha256': sha,
                         'duration': (info.get('format') or {}).get('duration'), 'streams': info.get('streams', []),
                         'format': (info.get('format') or {}).get('format_name'), 'decode_ok': decode_ok,
                         'valid': valid_video(info) and sha != source['sha256'],
                         'differs_from_source': sha != source['sha256'], 'video_streams': len(video)})
        good = [r for r in rows if r['valid']]
        require(rows, 'no new video file appeared under the shared Files media root')
        require(good, 'new file(s) appeared but none is a valid video differing from the source')
        return {'outputs': rows, 'chosen': max(good, key=lambda r: r['bytes']), 'source': source}
    REPORT['media'] = stage('defleur-output-video', media)

    def skills():
        before = x.load('skills-before.json')
        after = x.skills()
        app_text = (x.work / 'defleur-app-skill.md').read_text() if (x.work / 'defleur-app-skill.md').exists() else x.app_skill_text()
        diff = skills_diff(before, after, app_text)
        diff['installed_app_skill_sha256'] = digest_bytes(app_text.encode())
        require(diff['pass'], diff['verdict'])
        return diff
    REPORT['skills'] = stage('skills-pointer-not-copy', skills)

    def model():
        out = {'config_before': x.load('config-before.json'), 'config_after': x.config_model()}
        try:
            out['state_db'] = sudo_py(SESSIONS_SRC, str(x.hermes / 'state.db'), json.dumps(args.get('sessions', [])))
        except (CheckError, ValueError):
            out['state_db'] = 'unavailable'
        return out
    REPORT['model'] = stage('model-readback', model)


def finish():
    REPORT['status'] = 'pass' if REPORT['stages'] and all(r['status'] == 'pass' for r in REPORT['stages']) else 'fail'
    print(json.dumps(REPORT), flush=True)


def main():
    os.umask(0o077)
    command, run_id = sys.argv[1], sys.argv[2]
    args = json.loads(base64.urlsafe_b64decode(sys.argv[3].encode())) if len(sys.argv) > 3 else {}
    REPORT['command'] = command
    x = Ctx(run_id)
    if command == 'preflight':
        preflight(x)
    elif command == 'snapshot':
        snapshot(x)
    elif command == 'poll':
        poll(x)
    elif command == 'final':
        final(x, args)
    else:
        raise CheckError('unknown subcommand')
    finish()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        REPORT['status'] = 'fail'
        REPORT['stages'].append({'stage': 'guest-unhandled', 'status': 'fail',
                                'reason': str(error) if isinstance(error, CheckError) else type(error).__name__})
        print(json.dumps(REPORT), flush=True)
        sys.exit(1)
