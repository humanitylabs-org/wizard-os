#!/usr/bin/env python3
"""Pinned owner Claude setup. Guest commands or Thales dispatch via --root.

No credential files are opened. Config/.env are hashed, never emitted; all
Hermes writes use its CLI. stdout is allowlisted JSON, raw child output is lost.
No VM lifecycle or Serve operations occur here. The caller owns that lifecycle.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

VM = 'alongside-022-amd64'
STATE_DIR = '.e2e-022-alongside-claude'
NAME = 'e2e-alongside-host-claude'
LABEL = 'org.wizard.e2e.alongside-host-claude=1'
VERSION = '2.1.296'
# Identical to store/images/hermes-agent/fetch-claude-code.py and AI Accounts.
NPM_INTEGRITY = '+m01urgelnI+VJxPaKPEK0wixgq42uZ8PeCaUk5tX/8YoDBvSmC/REVQG2jQfJAr8dxunpjJ600FvLrcj1WWTw=='
CLAUDE_URL = f'https://registry.npmjs.org/@anthropic-ai/claude-code-linux-x64/-/claude-code-linux-x64-{VERSION}.tgz'
PLUGIN_SOURCE = 'NousResearch/hermes-plugin-claude-subscription-directsdk'
PLUGIN_REF = 'ef73726cfaf2fa0ee041e55572f406e2c24fed83'
PLUGIN_NAME = 'claude-subscription-directsdk-experimental'
PLUGIN_FILES = {
    'LICENSE': 'f26e906c042707a257816cf8a0396556b596be540b8add290132b8d72c080d60',
    'README.md': '7884703fc97c07273a3870141eb2480d5bd663fca865bb2df1cf7e90b5e9e77e',
    'plugin.yaml': '13c3e3995d4dbc9b5831758e14bb481d792b7d14b82043c79478f84444d02a20',
    '__init__.py': '0ea1f0a45fd3f8db16bc14fbdaeb6c68c84ed9fd34f97b5c0ea1046dd908f4d2',
    'admission.py': '20500dd7c8f8951a71a8e92206a6d52f0f03d8790c6602b1f80c2f7b5483d0aa',
    'directsdk.py': '36f8bb6bc6e2bd83cd01b26c8e3163592f9a81678928bfcd5eec20f992395f7a',
    'directsdk_setup.py': '0e78787d7771ca83e81c4e2d6f9b224bcf7bae175441c08d7aef2f50864084ab',
    'inert_mcp.py': 'bf20a09b2358600981b115c32845ec24722cb66adfc18d247d1c35ed999a0e0a',
    'model_catalog.py': '3cbb588caa3838aa2e5aa9039fc8c52e6f58a84ea80702aa2a413fcd10a34ff7',
}


class CheckError(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise CheckError(reason)


def run(argv, timeout=180, check=True, env=None, data=None):
    p = subprocess.run([str(x) for x in argv], input=data,
                       stdin=None if data is not None else subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout, env=env)
    require(not check or p.returncode == 0, 'command failed; output suppressed')
    return p


def sha(path):
    # Hash-only read: no parsing or printing of .env values.
    if not path.is_file():
        return None
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def hashes(home):
    return {n: sha(home / '.hermes' / n) for n in ('config.yaml', '.env')}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.chmod(0o600)
    tmp.replace(path)


def owner_env(home):
    # Do not inherit provider credentials, profiles or Claude directory overrides.
    env = {k: v for k, v in os.environ.items() if k in ('LANG', 'LC_ALL', 'TERM')}
    env.update(HOME=str(home), USER=home.name, LOGNAME=home.name,
               PATH=f'{home}/.local/bin:{home}/.wizard-os/bin:/usr/local/bin:/usr/bin:/bin',
               HERMES_HOME=str(home / '.hermes'), HERMES_PROFILE='default',
               XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}',
               DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{os.getuid()}/bus',
               DISABLE_AUTOUPDATER='1', NO_COLOR='1', PYTHONDONTWRITEBYTECODE='1')
    return env


def owner_guard(home):
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64' and os.getuid() != 0,
            'AMD64 guest login owner required (not sudo/root)')
    require(home.parent == Path('/home') and home.stat().st_uid == os.getuid(), 'owner home mismatch')
    require((home / '.alongside-022-qa/owned-guest').read_text().strip() == 'alongside-022',
            'isolated alongside guest marker missing')
    require((home / '.local/bin/hermes').is_file(), 'stock owner Hermes launcher missing')


def hermes(home, *args):
    return run([home / '.local/bin/hermes', *args], env=owner_env(home), timeout=900).stdout.strip()


def link_info(home):
    # Journal contains public config edits and hashes, not the gateway credential.
    rec = json.loads((home / '.wizard-os/linked.json').read_text())
    require(Path(rec['hermes_home']) == home / '.hermes', 'link belongs to another Hermes home')
    ref = rec.get('plugin_ref')
    if not ref and rec.get('linked'):
        # Older wizard journals omit plugin_ref; native plugin install metadata
        # still records the exact pin. Do not fall back to main/a new revision.
        meta_path = home / '.hermes/plugins/.install-metadata.json'
        meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        entry = meta.get('wizard-os') or {}
        if entry.get('pinned') is True:
            ref = entry.get('revision')
    return {'linked': rec.get('linked') is True,
            'baseline': {'config.yaml': rec.get('config_sha_before'), '.env': rec.get('env_sha_before')},
            'plugin_ref': ref}


def wizard(home, command, plugin_ref=None):
    argv = [home / '.local/bin/wizard', command, '--restart', '--json']
    if command == 'link':
        require(bool(re.fullmatch('[0-9a-f]{40}', plugin_ref or '')), 'missing pinned Wizard plugin ref')
        argv += ['--plugin-ref', plugin_ref]
    out = json.loads(run(argv, env=owner_env(home), timeout=900).stdout)
    require(out.get('ok') is True and out.get('gateway_restarted') is True, 'Wizard link lifecycle failed')
    require(link_info(home)['linked'] == (command == 'link'), 'Wizard link state did not read back')
    return {k: out.get(k) for k in ('ok', 'linked', 'config_byte_identical', 'env_restored', 'gateway_restarted')}


def gateway_claude_on_path(home):
    # Only inspect the service's declared PATH; never dump Environment or /proc/environ.
    p = run(['systemctl', '--user', 'show', 'hermes-gateway.service', '--property=Environment', '--value'],
            env=owner_env(home))
    paths = [x[5:] for x in shlex.split(p.stdout) if x.startswith('PATH=')]
    require(len(paths) == 1, 'gateway PATH unavailable; refusing to guess command override')
    found = shutil.which('claude', path=paths[0])
    require(not found or Path(found).resolve() == (home / '.local/bin/claude').resolve(),
            'gateway resolves a different Claude executable')
    return bool(found)


def install_claude(home, previous):
    dest = home / '.local/bin/claude'
    if (previous.get('version') == VERSION and previous.get('npm_integrity') == NPM_INTEGRITY
            and previous.get('binary_sha256') and sha(dest) == previous['binary_sha256']):
        return {**previous, 'changed': False}
    # SHA512 authenticates the pinned npm archive; SHA256 verifies the extracted
    # binary against bytes on disk. The upstream recipe publishes no SHA256 pin.
    data = urllib.request.urlopen(CLAUDE_URL, timeout=300).read()
    require(base64.b64encode(hashlib.sha512(data).digest()).decode() == NPM_INTEGRITY, 'Claude npm integrity mismatch')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        member = tar.getmember('package/claude')
        require(member.isfile(), 'Claude archive member is not a regular file')
        handle = tar.extractfile(member)
        require(handle is not None, 'Claude binary missing')
        binary = handle.read()
    expected = hashlib.sha256(binary).hexdigest()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name('claude.e2e-tmp')
    tmp.write_bytes(binary)
    tmp.chmod(0o755)
    require(sha(tmp) == expected, 'Claude staging SHA256 mismatch')
    tmp.replace(dest)
    require(sha(dest) == expected, 'Claude installed SHA256 mismatch')
    require(run([dest, '--version'], env=owner_env(home)).stdout.strip().startswith(VERSION + ' '),
            'Claude installed version mismatch')
    return {'version': VERSION, 'npm_integrity': NPM_INTEGRITY,
            'archive_sha256': hashlib.sha256(data).hexdigest(), 'binary_sha256': expected, 'changed': True}


def setup(home):
    report_path = home / STATE_DIR / 'setup.json'
    previous = json.loads(report_path.read_text()) if report_path.is_file() else {}
    info = link_info(home)
    require(info['linked'], 'setup requires the existing Wizard link')
    # Wizard unlink replays the entire plugins.enabled list. Install owner plugins
    # while unlinked, then link afresh, otherwise unlink would remove owner enablement.
    report = {'before': hashes(home), 'original_prelink': previous.get('original_prelink', info['baseline']),
              'prelink_before_setup': info['baseline'], 'wizard_plugin_ref': info['plugin_ref']}
    require(info['plugin_ref'], 'existing link did not record its pinned Wizard plugin')
    report['claude'] = install_claude(home, previous.get('claude', {}))
    try:
        wizard(home, 'unlink')
        require(hashes(home) == info['baseline'], 'pre-setup unlink did not restore pre-link bytes')
        report['unlinked_before'] = hashes(home)
        dest = home / '.hermes/plugins' / PLUGIN_NAME
        if not dest.exists():
            hermes(home, 'plugins', 'install', PLUGIN_SOURCE, '--ref', PLUGIN_REF, '--no-enable', '--no-deps')
        require(all(sha(dest / n) == d for n, d in PLUGIN_FILES.items()), 'installed DirectSDK bytes do not match image pin')
        # Same native config route as cmd_link; no full config/env output.
        # An unset list is normal on a stock installation. Read only this public key.
        p = run([home / '.local/bin/hermes', 'config', 'get', 'plugins.enabled', '--json'],
                env=owner_env(home), check=False)
        require(p.returncode == 0 or 'Config key not set: plugins.enabled' in p.stdout + p.stderr,
                'could not read plugins.enabled through Hermes CLI')
        enabled = json.loads(p.stdout) if p.returncode == 0 else []
        require(isinstance(enabled, list), 'plugins.enabled is not a list')
        if PLUGIN_NAME not in enabled:
            hermes(home, 'config', 'set', 'plugins.enabled', json.dumps(enabled + [PLUGIN_NAME]))
        hermes(home, 'config', 'set', 'DISABLE_AUTOUPDATER', '1')
        report['gateway_claude_on_path'] = gateway_claude_on_path(home)
        if not report['gateway_claude_on_path']:
            hermes(home, 'config', 'set', 'CLAUDE_SUBSCRIPTION_DIRECTSDK_COMMAND', str(home / '.local/bin/claude'))
        report['plugin_ref'] = PLUGIN_REF
        report['setup_unlinked'] = hashes(home)
    finally:
        if not link_info(home)['linked']:
            wizard(home, 'link', info['plugin_ref'])
        report['after'] = hashes(home)
        report['left_linked'] = link_info(home)['linked']
        save(report_path, report)
    require(link_info(home)['baseline'] == report['setup_unlinked'], 'relink did not capture owner setup baseline')
    return report


def container_argv(docker, home, uid, gid, image):
    require(bool(re.fullmatch(r'sha256:[0-9a-f]{64}', image)), 'immutable local image ID required')
    return [*docker, 'run', '-d', '--rm', '--pull=never', '--user', f'{uid}:{gid}',
            '--read-only', '--tmpfs', '/tmp', '--label', LABEL,
            '-e', 'AI_ACCOUNTS_CLAUDE_DIR=/claude', '-e', 'AI_ACCOUNTS_BIND=0.0.0.0',
            '-e', 'AI_ACCOUNTS_PORT=8795', '-v', f'{home}/.claude:/claude',
            '-p', '127.0.0.1:8797:8795', '--name', NAME, image]


def docker_prefix():
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], check=False).returncode == 0:
        return ['docker']
    run(['sudo', '-n', 'docker', 'info', '--format', '{{.ServerVersion}}'])
    return ['sudo', '-n', 'docker']


def signin_page(home, stop=False):
    docker = docker_prefix()
    names = run([*docker, 'ps', '-a', '--format', '{{.Names}}']).stdout.splitlines()
    if NAME in names:
        own = run([*docker, 'inspect', '--format', '{{index .Config.Labels "org.wizard.e2e.alongside-host-claude"}}', NAME]).stdout.strip()
        require(own == '1', 'named container is not owned by this runner')
        if stop:
            run([*docker, 'rm', '-f', NAME])
            require(NAME not in run([*docker, 'ps', '-a', '--format', '{{.Names}}']).stdout.splitlines(), 'one-shot container still exists')
            return {'stopped': True, 'name': NAME}
        raise CheckError('one-shot container already exists; stop it explicitly first')
    if stop:
        return {'stopped': True, 'name': NAME, 'already_absent': True}
    claude_dir = home / '.claude'
    require(not claude_dir.is_symlink(), 'refusing symlink Claude directory')
    claude_dir.mkdir(mode=0o700, exist_ok=True)
    require(claude_dir.is_dir() and claude_dir.stat().st_uid == os.getuid(), 'Claude directory is not owner-owned')
    claude_dir.chmod(0o700)
    engines = []
    for _ in range(60):   # Runtipi restarts apps after the guest boots; give it up to 10 minutes
        engines = [n for n in run([*docker, 'ps', '--format', '{{.Names}}']).stdout.splitlines()
                   if 'wizard-ai-accounts' in n and 'engine' in n]
        if len(engines) == 1:
            break
        time.sleep(10)
    require(len(engines) == 1, 'AI Accounts engine is not uniquely running (%d found)' % len(engines))
    image = run([*docker, 'inspect', '--format', '{{.Image}}', engines[0]]).stdout.strip()
    ds = json.loads(run([*docker, 'image', 'inspect', '--format', '{{json .RepoDigests}}', image]).stdout)
    require(ds and all('@sha256:' in d for d in ds), 'AI Accounts local image has no RepoDigest')
    require(run([*docker, 'image', 'inspect', '--format', '{{.Architecture}}', image]).stdout.strip() == 'amd64', 'AI Accounts architecture drift')
    argv = container_argv(docker, home, os.getuid(), os.getgid(), image)
    started = run(argv, check=False)
    # docker's own error text carries no secrets (only fixed AI_ACCOUNTS_* settings are passed).
    require(started.returncode == 0, 'one-shot docker run failed: ' + re.sub(r'\s+', ' ', started.stderr)[-300:])
    # Only selected non-secret inspect fields; never Config.Env.
    raw = run([*docker, 'inspect', '--format', '{{json .State.Running}}\t{{json .Image}}\t{{json .Config.User}}\t{{json .HostConfig.PortBindings}}\t{{json .Mounts}}\t{{json .HostConfig.ReadonlyRootfs}}', NAME]).stdout
    running, observed, user, ports, mounts, readonly = [json.loads(v) for v in raw.strip().split('\t')]
    require(running and observed == image and user == f'{os.getuid()}:{os.getgid()}' and readonly,
            'one-shot container identity mismatch')
    require(ports == {'8795/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8797'}]}, 'one-shot port exposure mismatch')
    require(any(m['Source'] == str(claude_dir) and m['Destination'] == '/claude' and m['RW'] for m in mounts), 'owner Claude mount mismatch')
    return {'name': NAME, 'source_engine': engines[0], 'image_id': image, 'repo_digests': ds,
            'uid': os.getuid(), 'gid': os.getgid(), 'guest_port': 8797, 'running': True}


def status_payload(data):
    email = str(data.get('email') or '')
    domain = email.rsplit('@', 1)[-1] if '@' in email else ''
    # Neither local part nor full private domain is retained.
    masked = (domain[:1] + '***.' + domain.rsplit('.', 1)[-1]) if re.fullmatch(r'[A-Za-z0-9.-]+\.[A-Za-z]{2,24}', domain) else None
    plans = {'pro': 'Claude Pro', 'max': 'Claude Max', 'team': 'Claude Team', 'enterprise': 'Claude Enterprise'}
    return {'logged_in': data.get('loggedIn') is True and data.get('authMethod') == 'claude.ai',
            'plan': plans.get(str(data.get('subscriptionType') or '').lower(), 'unknown'), 'email_domain': masked}


def status(home):
    out = run([home / '.local/bin/claude', 'auth', 'status', '--json'], env=owner_env(home), check=False, timeout=60)
    require(out.returncode in (0, 1), 'Claude status failed')
    data = json.loads(out.stdout)
    require(isinstance(data, dict) and isinstance(data.get('loggedIn'), bool), 'Claude status schema mismatch')
    return status_payload(data)


def dispatch(root, command, stop=False):
    require(platform.system() == 'Darwin' and root.resolve().is_relative_to(Path('/Volumes/ThalesMedia'))
            and root.name == 'e2e-022', 'Thales dedicated root required')
    env = {**os.environ, 'LIMA_HOME': str(root / 'lima'), 'LIMA_CACHE_HOME': str(root / 'lima-cache')}
    argv = ['/opt/homebrew/bin/limactl', 'shell', '--workdir=/', VM, '--', 'python3', '-', command]
    if stop:
        argv.append('--stop')
    out = run(argv, env=env, data=Path(__file__).read_text(), timeout=2400, check=False)
    # The guest prints one allowlisted JSON line, also on failure: surface its reason instead of hiding it.
    try:
        result = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        result = {'error': 'guest %s produced no JSON (exit %d)' % (command, out.returncode)}
    require(out.returncode == 0 and 'error' not in result, 'guest %s: %s' % (command, result.get('error')))
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('setup', 'signin-page', 'status'))
    p.add_argument('--stop', action='store_true')
    p.add_argument('--root', type=Path, help='Thales dispatch; omitted inside the guest')
    p.add_argument('--vm', choices=(VM,), default=VM)
    a = p.parse_args(argv)
    require(not a.stop or a.command == 'signin-page', '--stop is only for signin-page')
    if a.root:
        result = dispatch(a.root, a.command, a.stop)
    else:
        os.umask(0o077)
        home = Path.home()
        owner_guard(home)
        result = setup(home) if a.command == 'setup' else status(home) if a.command == 'status' else signin_page(home, a.stop)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(json.dumps({'error': str(e) if isinstance(e, CheckError) else type(e).__name__}), flush=True)
        sys.exit(1)
