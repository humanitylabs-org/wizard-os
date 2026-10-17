#!/usr/bin/env python3
"""PREPARED runner: isolated stock-Hermes alongside experiment, not release acceptance.

Run only through the acceptance owner's Thales heavy queue. No chat/model probe.
The guest is retained (stopped) for later owner-authorized UX/DeFleur work.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time

HERMES_SHA = 'bebe448a2bdb57043ca8ebd820807bf7eed6320d'
HERMES_REPO = 'https://github.com/NousResearch/hermes-agent.git'
CANDIDATE_SHA = '2fb67c714c0c85be49d12e37e8a556d25cd23bba'
PLUGIN_SHA = 'eac2ea0fe8f81b2b1f8a1eb0217b7d3cfcd77764'
GUEST_DIR = '.alongside-022-qa'
# Owner documents/config only; runtime DBs/logs/caches are intentionally not immutable.
OWNER_ROOTS = ('config.yaml', '.env', 'SOUL.md', 'AGENTS.md', 'USER.md',
               'auth.json', 'auth-sentinel.json', 'memories', 'skills', 'plugins')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')
    path.chmod(0o600)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def checked(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, stdin=subprocess.DEVNULL,
                          text=True, timeout=kwargs.pop('timeout', 300), **kwargs)


def output(argv):
    return checked(argv, capture_output=True).stdout.strip()


def inventory(home):
    result = {}
    def visit(p):
        if not p.exists() and not p.is_symlink():
            return
        s = p.lstat()
        row = {'mode': stat.S_IMODE(s.st_mode), 'uid': s.st_uid, 'gid': s.st_gid}
        if p.is_symlink():
            row.update(kind='symlink', target=os.readlink(p))
        elif p.is_file():
            row.update(kind='file', sha256=hashlib.sha256(p.read_bytes()).hexdigest(), size=s.st_size)
        elif p.is_dir():
            row.update(kind='directory')
        else:
            raise RuntimeError('unexpected non-file owner entry')
        result[str(p.relative_to(home))] = row
        if row['kind'] == 'directory':
            for child in sorted(p.iterdir()):
                visit(child)
    for name in OWNER_ROOTS:
        visit(home / name)
    return result


def snapshot(home, dest):
    dest.mkdir(mode=0o700)
    rows = inventory(home)
    for name, row in rows.items():
        p = dest / 'bytes' / name
        if row['kind'] == 'file':
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(home / name, p)
    save(dest / 'inventory.json', rows)


def verify_original(home, evidence, stage):
    before = json.loads((evidence / 'before/inventory.json').read_text())
    after = inventory(home)
    mismatches = []
    for name, row in before.items():
        if after.get(name) != row:
            mismatches.append(name)
        elif row['kind'] == 'file' and (home / name).read_bytes() != (evidence / 'before/bytes' / name).read_bytes():
            mismatches.append(name)
    save(evidence / (stage + '-preservation.json'), {
        'comparison': 'actual saved bytes plus type/mode/uid/gid/symlink target',
        'baseline_entries': len(before), 'mismatches': mismatches,
        'added_owner_scope_entries': sorted(set(after) - set(before)),
        'scope': list(OWNER_ROOTS), 'runtime_state_excluded': True,
        'release_exact': False, 'acceptance': 'pending',
    })
    require(not mismatches, 'owner bytes or metadata changed; see preservation receipt')


def stock_proof(home, evidence, stage):
    source = home / 'hermes-agent'
    sha = output(['git', '-C', source, 'rev-parse', 'HEAD'])
    remote = output(['git', '-C', source, 'remote', 'get-url', 'origin'])
    dirty = output(['git', '-C', source, 'status', '--porcelain', '--untracked-files=no'])
    require(sha == HERMES_SHA and remote == HERMES_REPO and not dirty,
            'stock Hermes source identity or tracked bytes changed')
    launcher = Path.home() / '.local/bin/hermes'
    require(launcher.is_file() and os.access(launcher, os.X_OK), 'real Hermes launcher missing')
    save(evidence / (stage + '-stock.json'), {
        'commit': sha, 'origin': remote, 'tracked_clean': not dirty,
        'launcher_sha256': hashlib.sha256(launcher.read_bytes()).hexdigest(),
        'runtime_command': json.loads(output([launcher, '--print-runtime-command', '--module', 'json.tool'])),
    })
    checked([launcher, '--version'])


def fixture_config(home, evidence):
    # Preserve installer-produced files before adding genuine owner fixtures.
    snapshot(home, evidence / 'installer-originals')
    cmd = json.loads(output(['hermes', '--print-runtime-command', '--module', 'json.tool']))
    needle = "runpy.run_module('json.tool', run_name='__main__', alter_sys=True)"
    require(isinstance(cmd, list) and isinstance(cmd[-1], str) and cmd[-1].count(needle) == 1,
            'unsupported stock runtime command; no substitute interpreter')
    script = '''from pathlib import Path
from ruamel.yaml import YAML
p = Path.home() / '.hermes/config.yaml'
y = YAML(); y.preserve_quotes = True
d = y.load(p.read_text()) or {}
d.yaml_set_start_comment('Alongside QA owner fixture; preserve this comment and all owner bytes on unlink.')
skills = d.setdefault('skills', {})
skills.setdefault('external_dirs', [])
plugins = d.setdefault('plugins', {})
plugins.setdefault('enabled', [])
with p.open('w') as f: y.dump(d, f)
'''
    checked(cmd[:-1] + [cmd[-1].replace(needle, f'exec({script!r})')])
    # Random local API credential, not a provider/chat key. It is never printed.
    # Existing key/credential bytes are retained; this fixture owns the new append.
    from secrets import token_urlsafe
    env = home / '.env'
    require(not re.search(r'^API_SERVER_KEY\s*=', env.read_text(), re.M), 'unexpected preconfigured API key')
    with env.open('a') as f:
        f.write('\n# Alongside QA owner API configuration; not an LLM credential.\n')
        f.write('API_SERVER_HOST=127.0.0.1\nAPI_SERVER_PORT=8642\nAPI_SERVER_KEY=' + token_urlsafe(32) + '\n')
    env.chmod(0o600)
    soul = home / 'SOUL.md'
    # Do not replace stock content; retain it and append a named sentinel.
    with soul.open('a') as f:
        f.write('\n<!-- alongside-022 owner sentinel: preserve original contents -->\n')
    sentinel = home / 'skills/alongside-owner-sentinel/SKILL.md'
    sentinel.parent.mkdir(parents=True, exist_ok=False)
    sentinel.write_text('---\nname: alongside-owner-sentinel\ndescription: Owner preservation fixture; not a tool or chat substitute.\n---\nKeep this exact owner text.\n')
    sentinel.chmod(0o640)
    auth = home / 'auth-sentinel.json'
    require(not auth.exists(), 'owner sentinel collision')
    auth.write_text('{"fixture": "owner bytes, not real authentication"}\n')
    auth.chmod(0o600)
    (home / 'config.yaml').chmod(0o640)


def wait_api(evidence, label):
    # c.runtipi() reads persisted root/operator state and uses the normal CLI auth.
    # Each attempt runs in a bounded subprocess, including ensure_operator().
    probe = "from wam.cli import Config; c=Config(); r=c.runtipi().req('GET','/marketplace/all',timeout=10); assert isinstance(r,dict) and isinstance(r.get('appStores'),list)"
    attempts = []
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        try:
            p = subprocess.run([sys.executable, '-c', probe], cwd=Path.home() / 'wizard-app-manager',
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=min(20, max(1, deadline - time.monotonic())))
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = 124
        attempts.append({'at': now(), 'exit_code': rc})
        save(evidence / (label + '.json'), {'request': 'GET /marketplace/all via Config().runtipi()',
                                          'attempts': attempts, 'ready': rc == 0})
        if rc == 0:
            return
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise RuntimeError('Runtipi marketplace API not ready within 300s')


def wizard(evidence, label, *args):
    argv = ['wizard', *args, '--json']
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
    (evidence / (label + '.stdout.log')).write_text(p.stdout)
    (evidence / (label + '.stderr.log')).write_text(p.stderr)
    p.check_returncode()
    data = json.loads(p.stdout)
    save(evidence / (label + '.json'), data)
    require(data.get('ok') is True, label + ' did not report ok')
    return data


def doctor(evidence, label):
    # No --gate: doctor probes the actual bridge but does not make an LLM/chat call.
    deadline = time.monotonic() + 180
    attempt = 0
    while True:
        attempt += 1
        p = subprocess.run(['wizard', 'doctor', '--json'], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=90)
        (evidence / f'{label}-{attempt}.json').write_text(p.stdout)
        if p.returncode == 0:
            data = json.loads(p.stdout)
            require(data.get('ok') is True and data.get('checks') and all(r['ok'] for r in data['checks']),
                    'doctor returned incomplete checks')
            save(evidence / (label + '.json'), data)
            return
        if time.monotonic() >= deadline:
            raise subprocess.CalledProcessError(p.returncode or 1, ['wizard', 'doctor', '--json'])
        time.sleep(5)


def candidate_readback(evidence):
    home = Path.home()
    candidate = json.loads((home / 'candidate-022-evidence/candidate-release.json').read_text())
    original = json.loads((home / '.wizard-os/release.json').read_text())
    require(candidate.get('mode') == 'alongside' and candidate.get('status') == 'pinned'
            and candidate.get('checks') and all(c['ok'] for c in candidate['checks']), 'candidate checks not all green')
    source = next(c for c in original['checks'] if c['name'] == 'wizard-app-manager commit')
    original_manifest = json.loads((home / 'wam-candidate/releases/0.2.2.json').read_text())
    require(original.get('release_exact') is False and original['status'] == 'mismatch'
            and source['ok'] is False and source['observed'] == CANDIDATE_SHA
            and source['expected'] == original_manifest['components']['wizard-app-manager']['commit'],
            'original release source mismatch must remain explicit')
    outcome = json.loads((home / '.wizard-os/install-outcome.json').read_text())
    require(outcome.get('status') == 'ok' and outcome.get('mode') == 'alongside'
            and not outcome.get('failed') and not outcome.get('degraded'), 'install outcome not clean alongside')
    st = json.loads((home / '.wizard-os/alongside.json').read_text())
    require(st['mode'] == 'alongside' and not st.get('shell', {}).get('share_history'), 'wrong alongside/privacy mode')
    names = output(['sudo', '-n', 'docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()
    require(not any(n.startswith('hermes-agent_wizardapps-') for n in names), 'unexpected container Hermes')
    mounts = []
    for name in names:
        if name.startswith(('wizard-agent-service_wizardapps-', 'wizard-ux_wizardapps-')):
            raw = output(['sudo', '-n', 'docker', 'inspect', '--format', '{{json .Mounts}}', name])
            rows = json.loads(raw)
            require(not any(r.get('Source') == str(home / '.hermes') for r in rows), 'whole Hermes home exposed')
            mounts.append({'container': name, 'mounts': rows})
    require(len(mounts) == 2, 'expected split service and UX containers')
    image_rows = []
    for component in ('wizard-app-manager', 'wizard-agent-service', 'wizard-ux'):
        matching = ['runtipi'] if component == 'wizard-app-manager' else [n for n in names if n.startswith(component + '_wizardapps-')]
        require(len(matching) == 1, 'ambiguous core container identity')
        name = matching[0]
        image_id = output(['sudo', '-n', 'docker', 'inspect', '--format', '{{.Image}}', name])
        digests = json.loads(output(['sudo', '-n', 'docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', image_id]))
        want = original_manifest['images'][component]['digest']
        require(any(d.endswith('@' + want) for d in digests), 'actual core RepoDigests mismatch')
        image_rows.append({'component': component, 'container': name, 'image_id': image_id, 'repo_digests': digests})
    save(evidence / 'image-readback.json', image_rows)
    save(evidence / 'mount-readback.json', mounts)
    save(evidence / 'candidate-readback.json', {'candidate_checks': candidate['checks'],
         'source_exception': source, 'release_exact': False, 'acceptance': 'pending'})


def guest(phase):
    os.umask(0o077)
    home = Path.home()
    evidence = home / GUEST_DIR / 'evidence'
    evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(os.getuid() != 0 and Path('/etc/os-release').exists(), 'guest non-root user required')
    require((home / GUEST_DIR / 'owned-guest').is_file(), 'isolated guest marker missing')
    os.environ.update(PATH=str(home / '.local/bin') + ':' + os.environ.get('PATH', ''),
                      HERMES_HOME=str(home / '.hermes'), XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}',
                      DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{os.getuid()}/bus',
                      WIZARD_MODE='alongside', WIZARD_PRIVATE_ACCESS='none', WIZARD_STRICT='1',
                      WIZARD_PLUGIN_REF=PLUGIN_SHA, PYTHONDONTWRITEBYTECODE='1', NO_COLOR='1')
    h = home / '.hermes'
    if phase in ('provision', 'resume-provision'):
        for name in ('.wizard-os', 'runtipi', 'wizard-app-manager', 'wam-candidate'):
            require(not (home / name).exists(), 'guest has prior Wizard installation state')
        installer = evidence / 'stock-hermes-install.sh'
        if phase == 'resume-provision':
            require(installer.is_file() and not (evidence / 'before').exists()
                    and not (evidence / 'installer-originals').exists(), 'not a partial dependency-only provision')
            require(output(['git', '-C', h / 'hermes-agent', 'rev-parse', 'HEAD']) == HERMES_SHA,
                    'partial stock checkout revision changed')
        else:
            require(not h.exists(), 'guest has prior Hermes state')
            checked(['sudo', '-n', 'apt-get', 'update', '-qq'], timeout=600)
            checked(['sudo', '-n', 'apt-get', 'install', '-y', '-qq', 'git', 'curl', 'xz-utils', 'python3', 'python3-yaml'], timeout=600)
            url = f'https://raw.githubusercontent.com/NousResearch/hermes-agent/{HERMES_SHA}/scripts/install.sh'
            checked(['curl', '-fsSL', '--retry', '3', url, '-o', installer])
            save(evidence / 'installer-source.json', {'url': url, 'sha256': hashlib.sha256(installer.read_bytes()).hexdigest()})
        require(hashlib.sha256(installer.read_bytes()).hexdigest() == json.loads((evidence / 'installer-source.json').read_text())['sha256'], 'stock installer bytes changed')
        checked(['bash', installer, '--branch', 'main', '--commit', HERMES_SHA,
                 '--non-interactive', '--skip-browser', '--skip-computer-use'], timeout=3600)
        stock_proof(h, evidence, 'installed')
        fixture_config(h, evidence)
        checked(['sudo', '-n', 'loginctl', 'enable-linger', output(['id', '-un'])])
        checked(['hermes', 'gateway', 'install', '--start-now', '--start-on-login'], timeout=300)
        # A real stock API listener, not a stub, must be up before the owner baseline.
        from urllib.request import urlopen
        deadline = time.monotonic() + 180
        while True:
            try:
                with urlopen('http://127.0.0.1:8642/health', timeout=5) as response:
                    require(response.status == 200, 'stock API unhealthy')
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError('stock Hermes API failed before candidate install') from None
                time.sleep(3)
        checked(['hermes', 'gateway', 'status'])
        # Service setup can persist legitimate stock configuration: baseline is AFTER it.
        snapshot(h, evidence / 'before')
        checked(['git', 'clone', '-q', 'https://github.com/humanitylabs-org/wizard-app-manager.git', home / 'wam-candidate'], timeout=600)
        checked(['git', '-C', home / 'wam-candidate', 'checkout', '--detach', CANDIDATE_SHA])
        require(output(['git', '-C', home / 'wam-candidate', 'rev-parse', 'HEAD']) == CANDIDATE_SHA, 'wrong candidate source')
    elif phase == 'install':
        # Unchanged helper drives ordinary get.sh/install.sh; no override of core image pins.
        checked([sys.executable, home / 'wam-candidate/scripts/qa-release-candidate.py',
                 '--manifest', home / 'wam-candidate/releases/0.2.2.json',
                 '--evidence', home / 'candidate-022-evidence'], timeout=7200)
    elif phase == 'linked':
        wait_api(evidence, 'runtipi-ready-linked')
        candidate_readback(evidence)
        rec = json.loads((home / '.wizard-os/linked.json').read_text())
        require(rec.get('linked') is True and rec.get('plugin_ref') == PLUGIN_SHA, 'ordinary installer did not link pinned plugin')
        save(evidence / 'linked-owner-inventory.json', inventory(h))
        doctor(evidence, 'doctor-linked')
        stock_proof(h, evidence, 'linked')
    elif phase == 'unlink':
        data = wizard(evidence, 'unlink', 'unlink', '--restart')
        require(data.get('linked') is False and data.get('config_byte_identical') is True
                and data.get('env_restored') is True and data.get('gateway_restarted') is True,
                'actual unlink or gateway restart failed')
        verify_original(h, evidence, 'unlinked')
        require(not (h / 'plugins/wizard-os').exists(), 'Wizard-owned plugin was left behind')
        stock_proof(h, evidence, 'unlinked')
    elif phase == 'relink':
        wait_api(evidence, 'runtipi-ready-relink')
        data = wizard(evidence, 'relink', 'link', '--restart', '--plugin-ref', PLUGIN_SHA)
        require(data.get('gateway_restarted') is True, 'relink did not restart actual Hermes')
        doctor(evidence, 'doctor-relinked')
        candidate_readback(evidence)
        stock_proof(h, evidence, 'relinked')
        save(evidence / 'scope.json', {'sequence': ['stock-install', 'owner-baseline', 'candidate-install-link',
             'doctor', 'unlink', 'byte-and-metadata-comparison', 'relink', 'doctor'],
             'chat': 'not attempted; provider/model/credentials remain parent-owned',
             'release_exact': False, 'acceptance': 'pending', 'guest_final_state': 'linked'})
    elif phase == 'ready':
        wait_api(evidence, 'runtipi-ready-after-start')
    else:
        raise RuntimeError('unsupported guest phase')


def host(args):
    root = args.root.resolve()
    require(platform.system() == 'Darwin', 'host runner is Thales/macOS-only')
    require(str(root).startswith('/Volumes/ThalesMedia/'), 'external build volume required')
    require(root.exists() and root.stat().st_dev != Path('/').stat().st_dev, 'external volume must be mounted')
    require(shutil.disk_usage(root).free >= 60 * 1024**3, 'need 60 GiB free on external volume')
    require(shutil.disk_usage('/System/Volumes/Data').free >= 10 * 1024**3, 'internal host disk safety floor: 10 GiB')
    source = Path(__file__).resolve()
    repo = source.parents[2]
    revision = output(['git', '-C', repo, 'rev-parse', 'HEAD'])
    require(not output(['git', '-C', repo, 'status', '--porcelain']), 'stage an exact clean pushed checkout')
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'LANG', 'LC_ALL')}
    env.update(PATH='/opt/homebrew/bin:' + env.get('PATH', ''), LIMA_HOME=str(root / 'lima'),
               LIMA_CACHE_HOME=str(root / 'lima-cache'))
    vm = 'alongside-022' if args.arch == 'aarch64' else 'alongside-022-amd64'
    if args.arch == 'x86_64':
        require(shutil.which('qemu-system-x86_64', path=env['PATH']) is not None,
                'x86_64 needs QEMU preinstalled by the build-host owner')
    require((root / 'lima' / vm).exists() == args.resume_provision,
            'existing guest requires explicit dependency-only resume; new run requires absence')
    os.umask(0o077)
    evidence = root / 'evidence' / ('alongside-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    evidence.mkdir(parents=True, mode=0o700)
    receipt = {'host': socket.gethostname(), 'command': shlex.join([sys.executable, *sys.argv]),
               'source_revision': revision, 'runner_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
               'candidate_sha': CANDIDATE_SHA, 'hermes_sha': HERMES_SHA, 'plugin_sha': PLUGIN_SHA,
               'vm': vm, 'lima_home': env['LIMA_HOME'], 'lima_cache_home': env['LIMA_CACHE_HOME'],
               'release_exact': False, 'acceptance': 'pending', 'steps': [], 'started_at': now()}
    def run(label, argv, data=None, timeout=300, binary=False):
        path = evidence / (label + ('.tar' if binary else '.log'))
        with path.open('wb') as log:
            try:
                p = subprocess.run(argv, input=data, stdin=None if data is not None else subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.PIPE if binary else subprocess.STDOUT,
                                   env=env, timeout=timeout)
                rc = p.returncode
                if binary:
                    (evidence / (label + '.stderr.log')).write_bytes(p.stderr)
            except subprocess.TimeoutExpired:
                rc = 124
            except OSError as e:
                log.write((type(e).__name__ + '\n').encode()); rc = 127
        receipt['steps'].append({'label': label, 'argv': argv, 'exit_code': rc})
        save(evidence / 'receipt.json', receipt)
        print(json.dumps({'step': label, 'exit_code': rc}), flush=True)
        return rc
    shell = ['limactl', 'shell', '--workdir=/', vm, '--']
    def terminate(signum, _frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    claimed = False
    reservation = root / 'lima' / ('.' + vm + '-reservation')
    rc = 1
    try:
        # Claim only this absent VM; the queue serializes its work, mkdir prevents another runner collision.
        (root / 'lima').mkdir(exist_ok=True)
        reservation.mkdir()
        claimed = True
        forwards = [{ 'guestIP': ip, 'guestPortRange': [1, 65535], 'ignore': True }
                    for ip in ('127.0.0.1', '0.0.0.0', '::1', '::')]
        machine = ['--arch=aarch64', '--memory=6', '--vm-type=vz', '--rosetta'] if args.arch == 'aarch64' else [
            '--arch=x86_64', '--memory=8', '--vm-type=qemu']
        receipt['arch'] = args.arch
        rc = 0 if args.resume_provision else run('create', ['limactl', 'create', '--tty=false', '--name=' + vm,
                 '--cpus=4', '--disk=60', *machine,
                 '--mount-none', '--containerd=none', '--set=.portForwards = ' + json.dumps(forwards),
                 'template://ubuntu-24.04'], timeout=1200)
        if rc == 0:
            shutil.copy2(root / 'lima' / vm / 'lima.yaml', evidence / 'lima.yaml')
            rc = run('start', ['limactl', 'start', '--tty=false', vm], timeout=1800)
        if rc == 0:
            # No host mounts or inherited credentials. Payload is only this public-safe script.
            stage = "from pathlib import Path; import sys; p=Path.home()/'.alongside-022-qa'; p.mkdir(mode=0o700); (p/'owned-guest').write_text('alongside-022'); (p/'runner.py').write_bytes(sys.stdin.buffer.read())"
            if args.resume_provision:
                stage = "from pathlib import Path; import sys; p=Path.home()/'.alongside-022-qa'; assert (p/'owned-guest').read_text() == 'alongside-022'; assert not (p/'evidence/before').exists(); assert not (p/'evidence/installer-originals').exists(); (p/'runner.py').write_bytes(sys.stdin.buffer.read())"
            rc = run('stage', shell + ['python3', '-c', stage], source.read_bytes())
        if rc == 0:
            provision = 'resume-provision' if args.resume_provision else 'provision'
            for phase, timeout in [(provision, 4800), ('install', 7500), ('linked', 900), ('unlink', 900), ('relink', 900)]:
                guest_cmd = ['bash', '-c', 'exec python3 "$HOME/.alongside-022-qa/runner.py" --guest-phase "$1"', '--', phase]
                rc = run(phase, shell + guest_cmd, timeout=timeout)
                if rc:
                    break
    except KeyboardInterrupt:
        rc = 130
    except SystemExit as e:
        rc = int(e.code or 1)
    except Exception as e:
        receipt['runner_error'] = type(e).__name__ + ': ' + str(e)
        rc = rc or 1
    finally:
        if claimed and (root / 'lima' / vm).exists():
            # Collect even on failure. Private archive includes owner byte backups and generated keys.
            collect = 'cd "$HOME"; set -- .alongside-022-qa/evidence; for p in candidate-022-evidence .wizard-os/release.json .wizard-os/linked.json .wizard-os/install-outcome.json .wizard-os/apps.json; do if test -e "$p"; then set -- "$@" "$p"; fi; done; exec tar -cf - "$@"'
            erc = run('collect-private', shell + ['bash', '-c', collect], timeout=180, binary=True)
            # Do not print docker environment/auth, and do not copy unbounded runtime logs.
            readback = 'set -eu; sudo -n docker ps -a --format "{{.Names}} {{.Image}} {{.Status}}"; sudo -n docker image ls --digests; git -C "$HOME/.hermes/hermes-agent" rev-parse HEAD; git -C "$HOME/wizard-app-manager" rev-parse HEAD'
            rrc = run('readback', shell + ['bash', '-c', readback], timeout=120)
            stop = run('stop-owned-guest', ['limactl', 'stop', vm], timeout=180)
            if stop:
                force = run('force-stop-owned-guest', ['limactl', 'stop', '--force', vm], timeout=180)
                receipt['force_stop_exit_code'] = force
            state_rc = run('owned-guest-state', ['limactl', 'list', '--json', vm], timeout=60)
            try:
                states = [json.loads(line) for line in (evidence / 'owned-guest-state.log').read_text().splitlines() if line.strip()]
                stopped = len(states) == 1 and states[0].get('name') == vm and states[0].get('status') == 'Stopped'
            except (OSError, ValueError):
                stopped = False
            receipt['owned_guest_stopped'] = stopped
            rc = rc or erc or rrc or stop or state_rc or (0 if stopped else 1)
        if claimed:
            reservation.rmdir()
        receipt.update(exit_code=rc, finished_at=now())
        save(evidence / 'receipt.json', receipt)
        print('PRIVATE_RECEIPT=' + str(evidence / 'receipt.json'), flush=True)
        print(json.dumps({'exit_code': rc, 'release_exact': False, 'acceptance': 'pending'}), flush=True)
    return rc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path)
    p.add_argument('--arch', choices=('aarch64', 'x86_64'), default='aarch64',
                   help='x86_64 uses QEMU/8 GiB; no Rosetta; not DeFleur acceptance')
    p.add_argument('--resume-provision', action='store_true', help='retry failed stock dependencies in the owned guest before any owner baseline exists')
    p.add_argument('--guest-phase', choices=('provision', 'resume-provision', 'install', 'linked', 'unlink', 'relink', 'ready'), help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.guest_phase:
        try:
            guest(args.guest_phase)
            return 0
        except subprocess.CalledProcessError as e:
            return e.returncode if e.returncode > 0 else 128 - e.returncode
        except subprocess.TimeoutExpired:
            return 124
    if args.root is None:
        p.error('--root is required')
    return host(args)


if __name__ == '__main__':
    sys.exit(main())
