#!/usr/bin/env python3
"""Guest half of the NON-AI 0.2.2 proof. Invoked only by e2e_022_ui_proof.py.

No credentials, model requests, transcription, imports, or editing. stdout is an
allowlisted receipt, never raw command output, Docker environment, or HTTP bodies.
"""
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
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import wave

APP_SHA = '76c544a75515f41d49317a625fdf40e63d0b8176'
IMAGE_DIGEST = 'sha256:d837622c977e1d868bfbb331f5f61fc3040d2ee89b0218e4f1f73a84aa6b4b57'
VERSION = '0.7.0-testing'
SPEECH = 'This is a release acceptance test. Please trim the pauses and add captions.'
REPORT = {'scope': 'non-AI only', 'ai_acceptance': 'blocked: owner sign-in required',
          'edit_acceptance': 'not attempted', 'stages': [], 'commands': []}


class CheckError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise CheckError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, timeout=90):
    argv = [str(a) for a in argv]
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=timeout)
        REPORT['commands'].append({'argv': argv, 'exit_code': p.returncode})
    except subprocess.TimeoutExpired:
        REPORT['commands'].append({'argv': argv, 'exit_code': 124})
        raise CheckError('command timeout; output suppressed') from None
    require(p.returncode == 0, 'command failed; output suppressed')
    return p.stdout.strip()


def stage(name, fn):
    try:
        value = fn()
        REPORT['stages'].append({'stage': name, 'status': 'pass', 'result': value})
        return value
    except Exception as e:
        REPORT['stages'].append({'stage': name, 'status': 'fail',
                                'reason': str(e) if isinstance(e, CheckError) else type(e).__name__})
        return None


def containers():
    # Inspect selected public fields only; never collect Config.Env or full inspect.
    ids = run(['sudo', '-n', 'docker', 'ps', '-aq']).split()
    rows = []
    for cid in ids:
        raw = run(['sudo', '-n', 'docker', 'inspect', '--format',
                   '{{json .Name}}\t{{json .Config.Image}}\t{{json .Image}}\t{{json .State.Status}}', cid])
        name, ref, image, status = [json.loads(v) for v in raw.split('\t')]
        rows.append({'name': name.lstrip('/'), 'ref': ref, 'image_id': image, 'status': status})
    return rows


def safe_app(row):
    return {k: row.get(k) for k in ('id', 'version', 'status', 'repo', 'commit', 'skill', 'provides')}


def wait_ready():
    # Client construction probes the marketplace too: it MUST be inside try.
    # Each whole attempt is isolated/bounded, so constructor hangs cannot defeat 180s.
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
            p = subprocess.run([sys.executable, '-c', probe], cwd=Path.home() / 'wizard-app-manager',
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=min(20, max(0.1, deadline - time.monotonic())))
            if p.returncode == 0:
                return {'attempts': attempts, 'deadline_seconds': 180}
        except subprocess.TimeoutExpired:
            pass
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise CheckError('marketplace unavailable after 180 seconds')


def loopback_url(value):
    u = urlsplit(value)
    require(u.scheme == 'http' and u.port and not u.username and not u.password and not u.query,
            'unexpected endpoint shape')
    return f'http://127.0.0.1:{u.port}{u.path}'


def rpc_discovery(url):
    session = None
    protocol = '2024-11-05'
    def request(method, params=None, ident=None):
        nonlocal session
        # This allowlist is the proof boundary. Never extend to tools/call here.
        require(method in ('initialize', 'notifications/initialized', 'tools/list'), 'forbidden MCP method')
        payload = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            payload['params'] = params
        if ident is not None:
            payload['id'] = ident
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                   'MCP-Protocol-Version': protocol}
        if session:
            headers['Mcp-Session-Id'] = session
        req = urllib.request.Request(url, json.dumps(payload).encode(), headers, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            session = response.headers.get('Mcp-Session-Id') or session
            raw = response.read(4 * 1024 * 1024).decode()
        if ident is None:
            return {}
        if raw.lstrip().startswith('{'):
            data = json.loads(raw)
        else:
            messages = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:')]
            data = next(m for m in messages if m.get('id') == ident)
        require('error' not in data and 'result' in data, 'MCP error response')
        return data['result']
    init = request('initialize', {'protocolVersion': protocol, 'capabilities': {},
                                 'clientInfo': {'name': 'wizard-release-non-ai-probe', 'version': '1'}}, 1)
    protocol = init.get('protocolVersion', protocol)
    request('notifications/initialized')
    names, cursor = [], None
    for n in range(20):
        data = request('tools/list', {'cursor': cursor} if cursor else {}, n + 2)
        names.extend(t['name'] for t in data.get('tools', []))
        cursor = data.get('nextCursor')
        if not cursor:
            break
    require(not cursor, 'MCP discovery pagination incomplete')
    unique = sorted(set(names))
    require(len(unique) == len(names), 'duplicate tool names')
    require({'workflow_guide', 'capabilities', 'list_files', 'import_file', 'start_edit'} <= set(unique),
            'expected DeFleur tools missing')
    return {'protocol': protocol, 'tool_names': unique, 'tool_count': len(unique), 'tools_called': []}


def main():
    os.umask(0o077)
    run_id = sys.argv[1]
    require(bool(re.fullmatch(r'ui-proof-[0-9TZ-]+', run_id)), 'invalid evidence id')
    home = Path.home()
    state = home / '.wizard-os'
    work = home / '.e2e-022-ui-proof' / run_id
    work.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(home / 'wizard-app-manager'))
    from wam.cli import Config
    c = Config()
    REPORT.update(host=platform.node(), arch=platform.machine(), work=str(work))
    require(platform.machine() == 'x86_64', 'AMD64 guest required')
    before = containers()
    REPORT['before_containers'] = before
    REPORT['wam_source_sha'] = run(['git', '-C', home / 'wizard-app-manager', 'rev-parse', 'HEAD'])
    release = state / 'release.json'
    REPORT['release_sha256'] = digest(release) if release.is_file() else None
    if stage('marketplace-ready', wait_ready) is None:
        finish(work)
        return

    def install():
        # Real WAM path: no direct docker-run substitute and no copied workflow.
        run([home / '.wizard-os/bin/wam', 'install', 'defleur-video'], timeout=1800)
        # WAM writes the canonical registry; read it back rather than assuming success.
        reg = json.loads((state / 'apps.json').read_text())
        row = next(a for a in reg['apps'] if a['id'] == 'defleur-video')
        REPORT['app'] = safe_app(row)
        require(row['version'] == VERSION and row['commit'] == APP_SHA, 'DeFleur source/version drift')
        require(row['repo'] == 'humanitylabs-org/defleur-video', 'unexpected DeFleur publisher')
        return safe_app(row)
    stage('wam-install', install)
    reg = json.loads((state / 'apps.json').read_text())
    REPORT['registry'] = [safe_app(a) for a in reg['apps']]
    apps = {a['id']: a for a in reg['apps']}
    # This URL is used only to discover the installed shell port/path, not to read auth.
    shell = apps.get('wizard-ux', {})
    shell_url = (shell.get('view') or {}).get('url') or ''
    if shell_url.startswith('http://'):
        u = urlsplit(shell_url)
        REPORT['browser_target'] = {'guest_port': u.port or 80, 'path': u.path or '/'}
    else:
        cfg = c.runtipi_root / 'apps/wizardapps/wizard-ux/config.json'
        port = json.loads(cfg.read_text())['port']
        REPORT['browser_target'] = {'guest_port': int(port), 'path': '/wizard-os-home/'}

    def metadata():
        row = apps['defleur-video']
        meta = c.runtipi_root / 'repos/wizardapps/apps/defleur-video'
        require(meta.is_dir(), 'installed store metadata missing')
        config = json.loads((meta / 'config.json').read_text())
        require(config['version'] == VERSION and config['supported_architectures'] == ['amd64'],
                'installed architecture/version mismatch')
        skill = state / row['skill']
        require(skill.resolve().is_relative_to(state.resolve()), 'skill escaped app-owned root')
        require(skill.is_file(), 'installed app-owned skill missing')
        require(digest(skill) == digest(meta / 'SKILL.md'), 'installed skill differs from source')
        pointers = []
        for p in (state / 'skills').glob('wizard-job-*/SKILL.md'):
            if 'defleur' in p.read_text().lower():
                pointers.append({'path': str(p.relative_to(state)), 'sha256': digest(p)})
        require(pointers, 'generated DeFleur workflow pointer skill missing')
        wm = (meta / 'wizard.md').read_text()
        require('claude-opus-5-5' in wm and 'hermes' in wm, 'model recommendation missing')
        return {'source_commit': APP_SHA, 'files': {p.name: digest(p) for p in
                (meta / 'wizard.md', meta / 'config.json', meta / 'SKILL.md')},
                'installed_skill': {'path': row['skill'], 'sha256': digest(skill)},
                'pointer_skills': pointers, 'recommended_model': 'claude-opus-5-5',
                'recommended_harness': 'Hermes', 'no_workflow_rewrite': True}
    stage('metadata-and-pointer-skills', metadata)

    def image_proof():
        matches = [r for r in containers() if 'defleur-video' in r['ref']]
        require(len(matches) == 1 and matches[0]['status'] == 'running', 'DeFleur not uniquely running')
        ds = json.loads(run(['sudo', '-n', 'docker', 'image', 'inspect', '--format',
                             '{{json .RepoDigests}}', matches[0]['image_id']]))
        arch = run(['sudo', '-n', 'docker', 'image', 'inspect', '--format', '{{.Architecture}}', matches[0]['image_id']])
        require(any(d.endswith('@' + IMAGE_DIGEST) for d in ds), 'DeFleur public digest mismatch')
        require(arch == 'amd64', 'DeFleur image is not AMD64')
        mounts = json.loads(run(['sudo', '-n', 'docker', 'inspect', '--format', '{{json .Mounts}}', matches[0]['name']]))
        media = c.runtipi_root / 'media'
        require(any(m['Destination'] == '/media' and Path(m['Source']).resolve() == media.resolve() for m in mounts),
                'DeFleur does not share the real Runtipi media root')
        file_containers = [r for r in containers() if 'filebrowser' in r['ref'] or re.search(r'(^|[-_])files([-_]|$)', r['name'])]
        require(file_containers, 'Files container missing')
        shared = False
        for row in file_containers:
            ms = json.loads(run(['sudo', '-n', 'docker', 'inspect', '--format', '{{json .Mounts}}', row['name']]))
            shared |= any(Path(m['Source']).resolve() == media.resolve() for m in ms)
        require(shared, 'Files does not share the same media root')
        return {'container': matches[0], 'repo_digests': ds, 'arch': arch, 'shared_media_verified': True}
    stage('image-and-shared-files', image_proof)

    def discovery():
        row = apps['defleur-video']
        health = loopback_url(row['health'])
        deadline = time.monotonic() + 120
        while True:
            try:
                with urllib.request.urlopen(health, timeout=min(10, max(0.1, deadline - time.monotonic()))) as r:
                    require(r.status == 200, 'health endpoint unavailable')
                break
            except (OSError, CheckError):
                require(time.monotonic() < deadline, 'DeFleur health unavailable after 120 seconds')
                time.sleep(min(2, max(0, deadline - time.monotonic())))
        return rpc_discovery(loopback_url(row['mcp']['url']))
    stage('health-and-mcp-discovery', discovery)

    def clip():
        needed = [p for p in ('ffmpeg', 'espeak-ng') if not shutil.which(p)]
        if needed:
            run(['sudo', '-n', 'apt-get', 'update', '-qq'], timeout=300)
            run(['sudo', '-n', 'env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get', 'install', '-y', '-qq', *needed], timeout=600)
        target = c.runtipi_root / 'media/Videos' / run_id
        run(['sudo', '-n', 'mkdir', '-p', target])
        run(['sudo', '-n', 'chown', f'{os.getuid()}:{os.getgid()}', target])
        run(['chmod', '755', target])
        wav = work / 'synthetic-speech.wav'
        run(['espeak-ng', '-s', '165', '-w', wav, SPEECH])
        with wave.open(str(wav)) as w:
            speech_seconds = w.getnframes() / w.getframerate()
        require(1 < speech_seconds < 9, 'speech duration would truncate the synthetic utterance')
        out = target / 'release-acceptance-source.mp4'
        run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
             '-f', 'lavfi', '-i', 'color=c=0x263449:s=360x640:r=24', '-i', wav,
             '-af', 'adelay=500|500,apad', '-t', '10', '-c:v', 'libx264', '-preset', 'ultrafast',
             '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', out], timeout=180)
        out.chmod(0o644)
        info = json.loads(run(['ffprobe', '-v', 'error', '-show_entries',
                              'format=duration:stream=codec_type,codec_name,width,height', '-of', 'json', out]))
        require(8 <= float(info['format']['duration']) <= 12, 'clip outside requested duration')
        require({s['codec_type'] for s in info['streams']} == {'video', 'audio'}, 'clip streams missing')
        run(['ffmpeg', '-v', 'error', '-nostdin', '-i', out, '-f', 'null', '-'], timeout=120)
        return {'relative_path': str(out.relative_to(c.runtipi_root / 'media')), 'sha256': digest(out),
                'bytes': out.stat().st_size, 'ffprobe': info, 'spoken_text': SPEECH,
                'speech_seconds': speech_seconds, 'synthetic_source_only': True, 'edited': False}
    stage('synthetic-files-source', clip)

    def preservation():
        after = containers()
        current = {r['name']: r for r in after}
        changed = [r['name'] for r in before if r['name'] not in current or
                   current[r['name']]['image_id'] != r['image_id']]
        require(not changed, 'pre-existing container images changed during install')
        require(not release.is_file() or digest(release) == REPORT['release_sha256'], 'release manifest changed')
        return {'existing_image_count': len(before), 'changed': changed, 'after': after}
    stage('existing-images-and-release-preserved', preservation)
    finish(work)


def finish(work):
    REPORT['status'] = 'pass' if REPORT['stages'] and all(r['status'] == 'pass' for r in REPORT['stages']) else 'fail'
    (work / 'receipt.json').write_text(json.dumps(REPORT, indent=2) + '\n')
    print(json.dumps(REPORT), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        REPORT['status'] = 'fail'
        REPORT['stages'].append({'stage': 'guest-unhandled', 'status': 'fail', 'reason': type(error).__name__})
        print(json.dumps(REPORT), flush=True)
        sys.exit(1)
