#!/usr/bin/env python3
"""Release 0.2.2 AI-workflow acceptance on ONE retained AMD64 guest (default: fresh).

Runs after e2e_022_ui_proof.py. Owner-level journeys through the real installed
Wizard UX (Playwright): pick Claude Opus 5.5 on the Claude subscription, READY chat,
"edit <clip> from my Files with DeFleur" in a new chat, Files view of the output,
browser Back on each nested view. Guest-side readbacks: AI Accounts status (API only),
DeFleur via real WAM at the pinned digest, image digests, media before/after diff +
ffprobe, Hermes skills/ diff with pointer-vs-copy verdicts, config.yaml model keys.

SOURCE-ONLY preparation is separate from execution: the acceptance owner admits
this command through the Thales heavy queue. It refuses to start a guest that is
already Running, and stops the guest in finally (reading back Stopped).
"""
import argparse
import base64
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import socket
import subprocess
import sys
import time

GUESTS = ('fresh-022-candidate-amd64', 'alongside-022-amd64')
HERE = Path(__file__).resolve().parent
SOURCES = ('e2e_022_ai_flow.py', 'e2e_022_ai_guest.py', 'e2e_022_ai_browser.cjs')
MODEL = 'claude-opus-5-5'
PROVIDER = 'claude-subscription-directsdk-experimental'
PREFLIGHT_REQUIRED = ('marketplace-ready', 'ai-accounts-status-connected', 'defleur-installed-pinned',
                      'synthetic-source-clip', 'hermes-before', 'owner-default-model', 'agent-sees-apps', 'agent-link')
SECRET_KEY = re.compile(r'(password|passwd|secret|token|cookie|authori[sz]ation|api[-_]?key|credential|bearer|'
                        r'private[-_]?key|oauth|^env$|^headers?$|^dotenv$)', re.I)
SECRET_VALUE = re.compile(r'(sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{20,}|Bearer\s+\S{8,}|gh[pousr]_[A-Za-z0-9]{20,}|'
                          r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}|'
                          r'-----BEGIN [A-Z ]*PRIVATE KEY-----)')
# Count-like fields whose names match SECRET_KEY by accident are kept.
SAFE_KEYS = {'tokens_redacted', 'max_tokens'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sanitize(value, key=''):
    """Drop credential-shaped keys and redact token-shaped strings anywhere in a receipt."""
    if key and key not in SAFE_KEYS and SECRET_KEY.search(key):
        return '[redacted]'
    if isinstance(value, dict):
        return {k: sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        return SECRET_VALUE.sub('[redacted]', value)
    return value


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(sanitize(value), indent=2) + '\n')
    tmp.chmod(0o600)
    tmp.replace(path)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def terminate(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


def execute(argv, env, timeout=180, data=None):
    p = subprocess.Popen([str(a) for a in argv], env=env, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = p.communicate(data, timeout=timeout)
        return p.returncode, out, err
    finally:
        terminate(p)


def parse_lima(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        return [json.loads(line) for line in raw.splitlines() if line.strip()]


def validate_target(root, vm):
    require(platform.system() == 'Darwin', 'execution is Thales/macOS-only; do not execute on control plane')
    require(root.is_relative_to(Path('/Volumes/ThalesMedia')) and root.name == 'e2e-022',
            'only the dedicated e2e-022 root on ThalesMedia is allowed')
    require(vm in GUESTS, 'only the two named retained guests are allowed')
    require((root / 'lima' / vm / 'lima.yaml').is_file(), 'existing dedicated Lima guest missing')


def stage_map(guest):
    return {s['stage']: s for s in (guest or {}).get('stages', [])}


def model_ok(row):
    return bool(row) and row.get('model') in (MODEL, MODEL + '[1m]') and row.get('provider') == PROVIDER


def session_ok(row, final_stages):
    """Session API model plus Hermes' own state.db billing provider for that session id."""
    if not row or row.get('model') not in (MODEL, MODEL + '[1m]'):
        return False
    if row.get('provider'):
        return row.get('provider') == PROVIDER
    db = (((final_stages.get('model-readback') or {}).get('result') or {}).get('state_db') or {})
    rec = (db.get('sessions') or {}).get(row.get('id')) if isinstance(db, dict) else None
    return bool(rec) and rec.get('billing_provider') == PROVIDER and rec.get('model') in (MODEL, MODEL + '[1m]')


def verdicts(pre, browser, final, files):
    """Pure: step verdicts from the three guest/browser receipts (unit tested)."""
    pre_s, fin_s = stage_map(pre), stage_map(final)
    stages = {s['stage']: s for s in (browser or {}).get('stages', [])}
    chat, df = stages.get('chat-ready', {}), stages.get('defleur-edit', {})
    out = {}
    out['0-preflight'] = {'pass': all(pre_s.get(k, {}).get('status') == 'pass' for k in PREFLIGHT_REQUIRED),
                          'stages': {k: pre_s.get(k, {}).get('status', 'missing') for k in PREFLIGHT_REQUIRED}}
    images = (pre_s.get('image-digests-readback') or {}).get('result') or {}
    out['0-image-digests'] = {'pass': bool(images.get('hermes_digest_match')) and not images.get('missing'),
                              'hermes_digest_match': images.get('hermes_digest_match'), 'missing': images.get('missing')}
    out['1-chat'] = {'pass': chat.get('status') == 'pass' and session_ok(chat.get('session'), fin_s) and model_ok(chat.get('runBody')),
                     'model_selection': (chat.get('modelSelection') or {}).get('method'),
                     'session_model': pick(chat.get('session'), ('model', 'provider')),
                     'run_body_model': pick(chat.get('runBody'), ('model', 'provider', 'require_model_lock')),
                     'reply_is_exactly_ready': chat.get('replyIsExactlyReady'), 'reason': chat.get('reason')}
    media = (fin_s.get('defleur-output-video') or {})
    out['2-defleur'] = {'pass': df.get('status') == 'pass' and media.get('status') == 'pass' and session_ok(df.get('session'), fin_s),
                        'outcome': df.get('outcome'), 'waited_seconds': df.get('waitedSeconds'),
                        'asked_question': bool(df.get('question')), 'model_selection': (df.get('modelSelection') or {}).get('method'),
                        'session_model': pick(df.get('session'), ('model', 'provider')),
                        'output': (media.get('result') or {}).get('chosen'), 'reason': df.get('reason') or media.get('reason')}
    sk = fin_s.get('skills-pointer-not-copy') or {}
    out['3-skills'] = {'pass': sk.get('status') == 'pass', 'verdict': (sk.get('result') or {}).get('verdict') or sk.get('reason')}
    backs = []
    for s in list(stages.values()) + [x for x in (files or {}).get('stages', [])]:
        backs.extend(s.get('back') or [])
    expected = {'chat-ready-thread', 'defleur-thread'} | ({'files-output-folder'} if files else set())
    seen = {b['view'] for b in backs if b.get('inWizard')}
    out['4-back'] = {'pass': bool(backs) and all(b.get('inWizard') for b in backs) and expected <= seen,
                     'views': backs, 'files_checked': bool(files)}
    out['5-accounts-page-never-opened'] = {'pass': browser is not None and not (browser or {}).get('blockedAccountsNavigations') and
                                           not (browser or {}).get('screenshotsSkipped'),
                                           'status_api': ((pre_s.get('ai-accounts-status-connected') or {}).get('result'))}
    return out


def pick(row, keys):
    return {k: row.get(k) for k in keys} if isinstance(row, dict) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--playwright-module', type=Path, required=True, help='existing Playwright package dir; no npm install')
    parser.add_argument('--node', type=Path, default=Path('/opt/homebrew/bin/node'))
    parser.add_argument('--vm', choices=GUESTS, default=GUESTS[0])
    parser.add_argument('--wait-minutes', type=int, default=75, help='DeFleur run bound (default 75)')
    parser.add_argument('--poll-seconds', type=int, default=20)
    parser.add_argument('--idle-grace-minutes', type=int, default=30,
                        help='stop waiting once the agent is idle this long with no new video (default 30)')
    args = parser.parse_args()
    require(5 <= args.wait_minutes <= 120 and 5 <= args.poll_seconds <= 120 and 5 <= args.idle_grace_minutes <= 120,
            'wait/poll/grace out of range')
    root, vm = args.root.resolve(), args.vm
    validate_target(root, vm)
    require(args.node.is_file() and (args.playwright_module / 'package.json').is_file(), 'existing Node/Playwright required')
    env = {**os.environ, 'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',
           'LIMA_HOME': str(root / 'lima'), 'LIMA_CACHE_HOME': str(root / 'lima-cache'), 'TMPDIR': str(root / 'scratch')}
    os.umask(0o077)
    (root / 'scratch').mkdir(exist_ok=True)
    # Never overlap the UI-proof runner or another AI-flow run on the same guests.
    locks = []
    for name in ('ui-proof.lock', 'ai-flow.lock'):
        f = (root / name).open('a')
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('%s is held: another e2e-022 runner is active' % name) from None
        locks.append(f)
    run_id = 'ai-flow-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    evidence = root / 'evidence' / run_id
    evidence.mkdir(parents=True, exist_ok=False)
    evidence.chmod(0o700)
    rc, revision, _ = execute(['git', '-C', HERE, 'rev-parse', 'HEAD'], env)
    require(rc == 0, 'source revision unavailable; run from pushed checkout')
    rc, dirty, _ = execute(['git', '-C', HERE, 'status', '--porcelain', '--untracked-files=no'], env)
    require(rc == 0 and not dirty.strip(), 'tracked source must be clean')
    receipt = {'host': platform.node(), 'source_revision': revision.strip(),
               'source_hashes': {n: sha(HERE / n) for n in SOURCES}, 'argv': sys.argv, 'guest': vm, 'run_id': run_id,
               'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'required_route': {'model': MODEL, 'provider': PROVIDER},
               'scope': 'AI workflow acceptance through the installed Wizard UX on one retained guest',
               'provider_credentials': 'never read/copied/provisioned; AI Accounts status API read once, page never opened',
               'commands': [], 'status': 'fail', 'cleanup': {}}
    receipt_file = evidence / 'receipt.json'
    save(receipt_file, receipt)

    def interrupted(signum, frame):
        raise KeyboardInterrupt('termination requested')
    old = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGINT)}

    def command(label, argv, timeout=180, data=None):
        t0 = time.monotonic()
        try:
            rc, out, _ = execute(argv, env, timeout=timeout, data=data)
        except subprocess.TimeoutExpired:
            rc, out = 124, ''
        except OSError:
            rc, out = 125, ''
        # Raw child output/stderr is never stored; only the guest/browser allowlisted JSON is parsed.
        receipt['commands'].append({'stage': label, 'argv': [str(a) for a in argv], 'exit_code': rc,
                                    'seconds': round(time.monotonic() - t0, 1)})
        save(receipt_file, receipt)
        return rc, out

    guest_argv = ['limactl', 'shell', '--workdir=/', vm, '--', 'python3', '-']
    guest_src = (HERE / 'e2e_022_ai_guest.py').read_text()

    def guest(cmd, timeout, extra=None):
        # Extra args travel base64url-encoded: limactl shell re-joins argv through a remote shell.
        blob = [base64.urlsafe_b64encode(json.dumps(extra).encode()).decode()] if extra else []
        rc, raw = command('guest-' + cmd, guest_argv + [cmd, run_id] + blob, timeout, guest_src)
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = {'status': 'fail', 'stages': [], 'reason': 'no guest JSON (exit %d)' % rc}
        save(evidence / ('guest-%s.json' % cmd), value)
        return value

    tunnel, started = None, False
    pre = browser = final = files = None
    try:
        rc, raw, _ = execute(['limactl', 'list', '--json'], env, timeout=60)
        require(rc == 0, 'Lima inventory failed')
        state = {r['name']: r for r in parse_lima(raw)}.get(vm, {}).get('status')
        receipt['guest_state_before'] = state
        require(state == 'Stopped', 'guest is %s; refusing to start a guest another lane may own' % state)
        rules = '.portForwards = [{"guestIP":"127.0.0.1","guestPortRange":[1,65535],"ignore":true},{"guestIP":"0.0.0.0","guestPortRange":[1,65535],"ignore":true}]'
        rc, _ = command('disable-host-port-forwarding', ['limactl', 'edit', '--tty=false', '--set=' + rules, vm], 60)
        require(rc == 0, 'could not enforce loopback and wildcard forwarding ignores')
        receipt['lima_config_sha256'] = sha(root / 'lima' / vm / 'lima.yaml')
        started = True
        rc, _ = command('start', ['limactl', 'start', '--tty=false', vm], 600)
        require(rc == 0, 'guest failed to start')

        pre = guest('preflight', 3600)
        receipt['images'] = (stage_map(pre).get('image-digests-readback') or {}).get('result')
        receipt['clip'] = (stage_map(pre).get('synthetic-source-clip') or {}).get('result')
        failed = [k for k in PREFLIGHT_REQUIRED if stage_map(pre).get(k, {}).get('status') != 'pass']
        require(not failed, 'preflight failed: ' + ', '.join(failed))
        target = pre.get('browser_target') or {}
        port = target.get('guest_port')
        require(isinstance(port, int) and 1 <= port <= 65535, 'invalid guest shell port')
        require(re.fullmatch(r'/[A-Za-z0-9_./-]*', target.get('path', '')) is not None, 'invalid shell path')

        rc, config = command('guest-ssh-config', ['limactl', 'show-ssh', '--format=config', vm], 60)
        require(rc == 0, 'guest ssh config unavailable')
        cfg = evidence / 'ssh.config'
        cfg.write_text(config)
        cfg.chmod(0o600)
        host = next((l.split()[1] for l in config.splitlines() if re.match(r'^\s*Host\s+', l)), None)
        require(host and re.fullmatch(r'[A-Za-z0-9_.-]+', host), 'ambiguous guest SSH alias')
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            local_port = s.getsockname()[1]
        # Only the Wizard shell port is forwarded; AI Accounts (8795) is never reachable from the browser.
        # Independent connection (no ControlMaster mux), stderr kept privately,
        # retried while the guest's sshd settles. The local listener is the readiness signal.
        argv = ['/usr/bin/ssh', '-F', str(cfg), '-N', '-T', '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
                '-o', 'ControlMaster=no', '-o', 'ControlPath=none',
                '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=6',
                '-L', f'127.0.0.1:{local_port}:127.0.0.1:{port}', host]
        tunnel_log = evidence / 'tunnel-private.log'
        deadline = time.monotonic() + 180
        connected, attempts = False, 0
        while not connected and time.monotonic() < deadline:
            attempts += 1
            with tunnel_log.open('ab') as tl:
                tunnel = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                          stderr=tl, start_new_session=True)
            attempt_end = min(deadline, time.monotonic() + 30)
            while time.monotonic() < attempt_end and tunnel.poll() is None:
                try:
                    with socket.create_connection(('127.0.0.1', local_port), timeout=1):
                        connected = True
                        break
                except OSError:
                    time.sleep(0.2)
            if not connected:
                terminate(tunnel)
                time.sleep(3)
        receipt['tunnel_attempts'] = attempts
        if not connected:
            receipt['tunnel_exit_code'] = tunnel.poll()
            receipt['tunnel_stderr_tail'] = tunnel_log.read_text(errors='replace')[-600:] if tunnel_log.exists() else ''
        require(connected, 'process-owned SSH tunnel failed')
        receipt['tunnel'] = {'argv': argv, 'bind': '127.0.0.1', 'guest_port': port}
        origin = f'http://127.0.0.1:{local_port}'
        phrase = (receipt['clip'] or {}).get('phrase') or 'release-acceptance-source.mp4'
        message = f'edit {phrase} from my Files with DeFleur'
        receipt['defleur_message'] = message
        wait_s = args.wait_minutes * 60
        browser_cfg = {'message': message, 'waitSeconds': wait_s, 'pollSeconds': args.poll_seconds,
                       'idleGraceSeconds': args.idle_grace_minutes * 60,
                       'probe': {'argv': guest_argv, 'script': str(HERE / 'e2e_022_ai_guest.py')}}
        rc, _ = command('browser-ai', [args.node, HERE / 'e2e_022_ai_browser.cjs', args.playwright_module.resolve(), origin,
                                       target['path'], evidence, run_id, 'ai', json.dumps(browser_cfg)], wait_s + 2400)
        bp = evidence / 'browser-ai.json'
        browser = json.loads(bp.read_text()) if bp.exists() else {'status': 'fail', 'stages': []}
        save(bp, browser)  # re-written through the receipt sanitizer
        receipt['browser_ai_status'] = browser.get('status')

        final = guest('final', 1800, {'sessions': browser.get('sessions') or []})
        chosen = ((stage_map(final).get('defleur-output-video') or {}).get('result') or {}).get('chosen')
        receipt['output_video'] = chosen
        receipt['skills_diff'] = (stage_map(final).get('skills-pointer-not-copy') or {}).get('result') or \
            {'reason': (stage_map(final).get('skills-pointer-not-copy') or {}).get('reason')}
        receipt['model_readback'] = (stage_map(final).get('model-readback') or {}).get('result')
        if chosen:
            rc, _ = command('browser-files', [args.node, HERE / 'e2e_022_ai_browser.cjs', args.playwright_module.resolve(), origin,
                                              target['path'], evidence, run_id, 'files',
                                              json.dumps({'relPath': chosen['relative_path']})], 600)
            fp = evidence / 'browser-files.json'
            files = json.loads(fp.read_text()) if fp.exists() else {'status': 'fail', 'stages': []}
            save(fp, files)
    except BaseException as error:
        receipt['error_class'] = type(error).__name__
        if type(error) is RuntimeError:
            receipt['reason'] = str(error)
    finally:
        terminate(tunnel)
        receipt['cleanup']['tunnel_stopped'] = tunnel is None or tunnel.poll() is not None
        if started:
            stop_rc, _ = command('stop', ['limactl', 'stop', vm], 300)
            receipt['cleanup']['stop_exit_code'] = stop_rc
            if stop_rc:
                forced, _ = command('force-stop-owned-guest', ['limactl', 'stop', '--force', vm], 120)
                receipt['cleanup']['force_stop_exit_code'] = forced
        rc, raw, _ = execute(['limactl', 'list', '--json'], env, timeout=60)
        states = {r['name']: r.get('status') for r in parse_lima(raw)} if rc == 0 else {}
        receipt['cleanup']['guest_state_after'] = states.get(vm)
        receipt['cleanup']['guest_stopped'] = states.get(vm) == 'Stopped'
        receipt['steps'] = verdicts(pre, browser, final, files)
        receipt['screenshots'] = {p.name: sha(p) for p in sorted(evidence.glob('*.png'))}
        receipt['status'] = 'pass' if all(v['pass'] for v in receipt['steps'].values()) and \
            receipt['cleanup']['guest_stopped'] and 'error_class' not in receipt else 'fail'
        receipt['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        receipt['evidence_hashes'] = {str(p.relative_to(evidence)): sha(p) for p in evidence.rglob('*')
                                      if p.is_file() and p != receipt_file and p.name != 'ssh.config'}
        save(receipt_file, receipt)
        for s, h in old.items():
            signal.signal(s, h)
        for f in locks:
            f.close()
        print('RECEIPT=' + str(receipt_file), flush=True)
    return 0 if receipt['status'] == 'pass' else 2


if __name__ == '__main__':
    sys.exit(main())
