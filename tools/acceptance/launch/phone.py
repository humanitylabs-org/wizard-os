#!/usr/bin/env python3
"""Published release APK + empty API35 emulator + a never-seen disposable box.

No debug APK, CDP, fake shell, TLS bypass, pre-seeded preferences or live owner
endpoint. Raw UI XML/transcript stay in memory; failure evidence is redacted.
"""
import contextlib
import fcntl
import hashlib
import ipaddress
import json
import platform
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

from tunnel import open_forward
from phone_diagnostics import capture_failure, private_write
from phone_transport import Relay, connect_proxy
from phone_runtime import (GPU_MODES, PersistentLogcat, checkpoint, configure_avd,
                           exception_note, runtime_note, stop_emulator)


@contextlib.contextmanager
def failure_boundary(capture):
    try:
        yield
    except Exception:
        # Diagnostics must not replace the original failure or skip teardown.
        with contextlib.suppress(Exception):
            capture()
        raise


class NetworkArgs(list):
    relay: Relay | None = None

    def configure(self, shell):
        if self.relay is not None:
            value = self.relay.android_proxy
            shell('settings', 'put', 'global', 'http_proxy', value)
            if shell('settings', 'get', 'global', 'http_proxy').strip() != value:
                raise RuntimeError('phone_android_proxy')


@contextlib.contextmanager
def emulator_network(status, port):
    args = NetworkArgs()
    if platform.system() != 'Linux':
        yield args
        return
    own = status['Self']
    with connect_proxy(own['DNSName'].rstrip('.'), own['TailscaleIPs'], port) as proxy:
        # Configure Android's HTTP stack, not emulator-level TCP interception.
        # Never combine the two proxy layers. The disposable AVD owns the setting.
        args.relay = proxy
        yield args


def emulator_argv(sdk, port, dns_server, network_args, config=None, logcat_args=()):
    config = config or {}
    mode = config.get('gpu_mode', 'swangle' if platform.system() == 'Linux' else 'swiftshader_indirect')
    if mode not in GPU_MODES:
        raise ValueError('phone_gpu_mode')
    return [str(sdk / 'emulator/emulator'), '-avd', 'launch_phone', '-port', str(port),
            '-no-window', '-no-snapshot', '-no-audio', '-gpu', mode,
            '-dns-server', dns_server, *network_args, *logcat_args]

PACKAGE = 'ai.wizards.os'
SIGNER = '3bf74d0b597bc170761079909d3692428702ba057f753ee1ffd62da3c76ed1fd'


def tailnet_resolver(dns_name, resolvers, system='Darwin'):
    """Return the host's scoped resolver for the box's tailnet DNS suffix.

    A real phone runs Tailscale and resolves the box's tailnet name itself. The
    emulator inherits only the host's primary resolver, while macOS keeps
    MagicDNS as a split resolver scoped to the tailnet suffix, so the published
    APK correctly reports "Couldn't reach". Read that scoped resolver from
    `scutil --dns` instead of hardcoding an address.
    """
    suffix = dns_name.rstrip('.').split('.', 1)[-1].lower()
    if system == 'Linux':
        entries = [line.split('#', 1)[0].split() for line in resolvers.splitlines()]
        domains = [v.rstrip('.').lower() for e in entries if e and e[0] in ('search', 'domain') for v in e[1:]]
        if suffix in domains:
            for e in entries:
                if len(e) == 2 and e[0] == 'nameserver':
                    try:
                        address = ipaddress.ip_address(e[1])
                    except ValueError:
                        continue
                    if address.version == 4 and not address.is_loopback and not address.is_unspecified:
                        return str(address)
        raise RuntimeError('phone_tailnet_dns')
    if system != 'Darwin':
        raise RuntimeError('phone_tailnet_dns')
    for block in re.split(r'\n(?=resolver #)', resolvers):
        domain = re.search(r'^\s*domain\s*:\s*(\S+)', block, re.M)
        server = re.search(r'^\s*nameserver\[0\]\s*:\s*([0-9.]+)\s*$', block, re.M)
        if domain and server and domain.group(1).rstrip('.').lower() == suffix:
            return server.group(1)
    raise RuntimeError('phone_tailnet_dns')


def native_system_image():
    # Share native host admission with the VM; never fall back to CPU emulation.
    from release_gate import native_vm_config
    arch = native_vm_config()['arch']
    abi = {'x86_64': 'x86_64', 'aarch64': 'arm64-v8a'}[arch]
    return 'system-images;android-35;google_apis;' + abi


def host_resolver(dns_name, call):
    system = platform.system()
    resolvers = Path('/etc/resolv.conf').read_text() if system == 'Linux' else call(['scutil', '--dns'])
    return tailnet_resolver(dns_name, resolvers, system)


def validate_apk(config, sdk, call):
    apk = Path(config['apk'])
    feed = json.loads(Path(config['feed']).read_text())
    assert feed['app'] == PACKAGE and feed['signer'] == SIGNER
    assert apk.stat().st_size == feed['bytes']
    assert hashlib.sha256(apk.read_bytes()).hexdigest() == feed['sha256']
    tools = sorted((sdk / 'build-tools').glob('*'))[-1]
    signature = call([tools / 'apksigner', 'verify', '--print-certs', apk])
    assert SIGNER in signature.lower().replace(':', '')
    badging = call([tools / 'aapt2', 'dump', 'badging', apk])
    assert f"name='{PACKAGE}'" in badging
    assert f"versionCode='{feed['versionCode']}'" in badging
    assert f"versionName='{feed['versionName']}'" in badging
    # Identify migration defaults without ever exposing their hostname. The
    # published owner-upgrade APK can still pair through its exported Connect
    # entry; launch that screen BEFORE MainActivity can load the old default.
    dex = call([sdk / 'cmdline-tools/latest/bin/apkanalyzer', 'dex', 'code',
                '--class', 'ai.wizards.os.BuildConfig', apk])
    assert ' ORIGIN:Ljava/lang/String;' in dex
    owner_default = not bool(re.search(r'ORIGIN:Ljava/lang/String;\s*=\s*""', dex))
    return apk, feed, owner_default


def labels(xml):
    return ' '.join((n.get('text', '') + ' ' + n.get('content-desc', '')) for n in ET.fromstring(xml).iter('node'))


def center(node):
    coordinates = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
    if not coordinates:
        raise RuntimeError('phone_bounds')
    x1, y1, x2, y2 = map(int, coordinates.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


@contextlib.contextmanager
def https_forward(vm, cli, evidence, port, sudo=False):
    # Only a new dedicated Serve port; never reset, replace or re-route existing
    # Serve handlers. This is a transport to the real box, not a substitute shell.
    def ts(*argv):
        prefix = ['sudo', '-n'] if sudo else []
        return subprocess.check_output(prefix + ['tailscale', *map(str, argv)], text=True, stderr=subprocess.DEVNULL, timeout=20)
    before = json.loads(ts('serve', 'status', '--json'))
    assert str(port) not in before.get('TCP', {}), 'phone_serve_port_busy'
    status = json.loads(ts('status', '--json'))
    dns = status['Self']['DNSName'].rstrip('.')
    origin = f'https://{dns}:{port}'
    key = f'{dns}:{port}'
    with open_forward(vm, cli, evidence):
        try:
            ts('serve', '--bg', '--yes', f'--https={port}', 'http://127.0.0.1:18795')
            after = json.loads(ts('serve', 'status', '--json'))
            assert after['Web'][key]['Handlers']['/']['Proxy'] == 'http://127.0.0.1:18795'
            # All previous handlers must still be byte-for-byte equivalent.
            assert all(after.get(k, {}).get(n) == v for k in ('TCP', 'Web') for n, v in before.get(k, {}).items())
            yield origin
        finally:
            ts('serve', f'--https={port}', 'off')
            after = json.loads(ts('serve', 'status', '--json'))
            assert key not in after.get('Web', {}) and str(port) not in after.get('TCP', {})
            assert all(after.get(k, {}).get(n) == v for k in ('TCP', 'Web') for n, v in before.get(k, {}).items())


@contextlib.contextmanager
def worker_lock(work):
    """Hold the shared Android/VM lock, reusing the heavy worker's lease.

    Both workers already hold worker.lock and pass that open file
    description as WIZARD_HEAVY_LOCK_FD; opening the file again would conflict
    with our own parent and fail with BlockingIOError.
    """
    # work_root must be the worker's lock directory, not its Android SDK/build
    # directory. The inherited descriptor must identify this exact file.
    path = Path(work) / 'worker.lock'
    inherited = os.environ.get('WIZARD_HEAVY_LOCK_FD')
    if inherited:
        fd = int(inherited)
        expected, actual = path.stat(), os.fstat(fd)
        if (expected.st_dev, expected.st_ino) != (actual.st_dev, actual.st_ino):
            raise RuntimeError('phone_inherited_lock_mismatch')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
        return
    with path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


PHONE_STAGES = frozenset({
    'preflight', 'apk-validation', 'worker-lock', 'avd-create', 'emulator-start',
    'emulator-boot', 'empty-install', 'apk-install', 'connect-ui', 'https-forward', 'tailnet-dns',
    'address-entry', 'address-pairing', 'model-reply', 'nested-back', 'root-back',
    'pairing-restart', 'crash-check', 'https-cleanup', 'emulator-cleanup',
})


def run_phone(vm, cli, evidence, config_path, chat):
    """Return bounded progress and fixed crash enums; never raw exception text."""
    progress = {'stage': 'preflight', 'checks': {}}
    try:
        if evidence is not None:
            Path(evidence).mkdir(mode=0o700, parents=True, exist_ok=True)
            Path(evidence).chmod(0o700)
        return _run_phone(vm, cli, evidence, config_path, chat, progress)
    except Exception as exc:
        stage = progress.get('failure_stage', progress['stage'])
        if evidence is not None and not (Path(evidence) / 'failure/diagnostics.json').exists():
            with contextlib.suppress(Exception):
                capture_failure(evidence, stage if stage in PHONE_STAGES else 'preflight')
        result = {'passed': False, 'checks': progress['checks'],
                  'failure_stage': stage if stage in PHONE_STAGES else 'preflight',
                  'failure': progress.get('failure', exception_note(exc))}
        if evidence is not None:
            with contextlib.suppress(OSError, ValueError):
                result['failure']['logcat'] = json.loads((Path(evidence) / 'logcat-summary.json').read_text())
        if progress.get('cleanup_failure'):
            result['cleanup_failure'] = progress['cleanup_failure']
        if progress.get('cleanup_failed'):
            result['cleanup_failed'] = True
        return result


def _run_phone(vm, cli, evidence, config_path, chat, progress):
    if not vm.startswith('lc-'):
        raise RuntimeError('phone_disposable_required')
    config = json.loads(Path(config_path).read_text())
    sdk = Path(config['sdk'])
    work = Path(config['work_root'])
    work.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['JAVA_HOME'] = config['java_home']
    brew = '/opt/homebrew/bin:' if platform.system() == 'Darwin' else ''
    env['PATH'] = config['java_home'] + '/bin:' + brew + env['PATH']
    if platform.system() == 'Linux':
        env.pop('http_proxy', None)  # Don't silently re-enable emulator TCP proxy.
    env['ANDROID_HOME'] = env['ANDROID_SDK_ROOT'] = str(sdk)
    env['ANDROID_AVD_HOME'] = str(evidence / 'avd')
    Path(env['ANDROID_AVD_HOME']).mkdir(parents=True)
    def call(argv, **kw):
        p = subprocess.run(list(map(str, argv)), env=env, capture_output=True, text=True, timeout=kw.pop('timeout', 60), **kw)
        if p.returncode:
            raise subprocess.CalledProcessError(p.returncode, list(map(str, argv)))
        return p.stdout
    progress['stage'] = 'apk-validation'
    apk, feed, owner_default = validate_apk(config, sdk, call)
    port = config.get('emulator_port', 5682)
    serial = f'emulator-{port}'
    adb = sdk / 'platform-tools/adb'
    def shell(*argv):
        return call([adb, '-s', serial, 'shell', *argv])
    def ui():
        shell('uiautomator', 'dump', '/sdcard/launch-ui.xml')
        return shell('cat', '/sdcard/launch-ui.xml')
    def wait_for(predicate, timeout=60):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if em is None or em.poll() is not None:
                raise RuntimeError('phone_emulator_exited')
            try:
                value = predicate()
                if value:
                    return value
            except (RuntimeError, subprocess.CalledProcessError, ET.ParseError):
                pass
            time.sleep(1)
        raise RuntimeError('phone_ui_timeout')
    def tap(node):
        shell('input', 'tap', *center(node))
    def foreground():
        dump = shell('dumpsys', 'activity', 'activities')
        return any(PACKAGE + '/' in line for line in dump.splitlines() if 'topResumedActivity' in line or 'mResumedActivity' in line)
    em = None
    clocks = {}
    persistent = None
    checks = progress['checks']
    progress['stage'] = 'tailnet-dns'
    image = native_system_image()
    tailnet = json.loads(call(['tailscale', 'status', '--json']))
    dns_server = config.get('dns_server') or host_resolver(tailnet['Self']['DNSName'], call)
    def diagnose():
        # Freeze liveness before any slow diagnostic or cleanup changes the facts.
        if 'failure' not in progress:
            progress['failure'] = runtime_note(em, adb, serial, env, clocks)
        capture_failure(evidence, progress['stage'], adb=adb if em is not None else None,
                        serial=serial, env=env, sudo=config.get('tailscale_sudo', False),
                        port=config.get('https_port', 9450),
                        relay=network_args.relay, box_host=tailnet['Self']['DNSName'].rstrip('.'))
    progress['stage'] = 'worker-lock'
    # Match the selected worker's shared Android/VM exclusion lock.
    with worker_lock(work), emulator_network(tailnet, config.get('https_port', 9450)) as network_args, \
            PersistentLogcat(evidence) as persistent:
        assert serial not in call([adb, 'devices'])
        try:
            progress['stage'] = 'avd-create'
            call([sdk / 'cmdline-tools/latest/bin/avdmanager', 'create', 'avd', '-n', 'launch_phone',
                  '-k', image, '-d', 'pixel_7', '-p', evidence / 'device'], input='no\n')
            configure_avd(evidence / 'device/config.ini', config)
            # Emulator stdout may contain URLs. Keep it private, never publish it.
            progress['stage'] = 'emulator-start'
            fd = os.open(evidence / 'private-emulator.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as log:
                clocks['start'] = time.monotonic()
                em = subprocess.Popen(emulator_argv(sdk, port, dns_server, network_args, config, persistent.argv),
                                      env=env, stdout=log, stderr=log)
            progress['stage'] = 'emulator-boot'
            wait_for(lambda: shell('getprop', 'sys.boot_completed').strip() == '1', 240)
            clocks['boot'] = time.monotonic()
            assert shell('getprop', 'ro.build.version.sdk').strip() == '35'
            network_args.configure(shell)
            progress['stage'] = 'empty-install'
            assert PACKAGE not in shell('pm', 'list', 'packages', PACKAGE)
            progress['stage'] = 'apk-install'
            assert 'Success' in call([adb, '-s', serial, 'install', apk], timeout=120)
            progress['stage'] = 'connect-ui'
            shell('logcat', '-c')
            shell('input', 'keyevent', 'KEYCODE_WAKEUP')
            shell('wm', 'dismiss-keyguard')
            # Use the real exported Connect entry on owner-upgrade artifacts;
            # never launch Main at its migration default. Generic artifacts also
            # prove normal first-run Main -> Connect plus unpaired Back.
            shell('am', 'start', '-W', '-n', PACKAGE + ('/.ConnectActivity' if owner_default else '/.MainActivity'))
            title = 'Change Wizard' if owner_default else 'Connect to your Wizard'
            wait_for(lambda: title in labels(ui()))
            checks['empty_install_connect'] = True
            if not owner_default:
                shell('input', 'keyevent', 'KEYCODE_BACK')
                assert foreground() and title in labels(ui())
                checks['unpaired_back_stays'] = True
            progress['stage'] = 'https-forward'
            with https_forward(vm, cli, evidence / 'forward', config.get('https_port', 9450),
                               sudo=config.get('tailscale_sudo', False)) as origin, failure_boundary(diagnose):
                progress['stage'] = 'tailnet-dns'
                # Name resolution only: ICMP may be filtered, so rc/reply are ignored.
                # The emulator's resolver can need a few seconds to settle after boot.
                host = origin.split('//', 1)[1].rsplit(':', 1)[0]
                def resolves():
                    lookup = subprocess.run([str(adb), '-s', serial, 'shell', 'ping', '-c', '1', '-W', '3', host],
                                            env=env, capture_output=True, text=True, timeout=30)
                    # ADB rc=1/device missing is NOT a successful DNS lookup.
                    return bool(re.search(r'^PING .*\([0-9a-fA-F:.]+\)', lookup.stdout, re.M))
                try:
                    wait_for(resolves, 60)
                except RuntimeError:
                    raise RuntimeError('phone_tailnet_dns') from None
                checks['tailnet_dns'] = True
                progress['stage'] = 'address-entry'
                xml = ui()
                edit = next(n for n in ET.fromstring(xml).iter('node') if n.get('class') == 'android.widget.EditText')
                tap(edit)
                # Replace the migration default only through native keyboard input.
                old_text = edit.get('text', '')
                shell('input', 'keyevent', 'KEYCODE_MOVE_END')
                if old_text:
                    shell('input', 'keyevent', *(['KEYCODE_DEL'] * len(old_text)))
                shell('input', 'text', origin)
                shell('input', 'keyevent', 'KEYCODE_BACK')
                paired_input = next(n for n in ET.fromstring(ui()).iter('node') if n.get('class') == 'android.widget.EditText')
                assert paired_input.get('text') == origin
                connect = next(n for n in ET.fromstring(ui()).iter('node')
                               if n.get('text') == 'Connect' or n.get('content-desc') == 'Connect')
                progress['stage'] = 'address-pairing'
                progress['before_connect_screenshot'] = checkpoint(evidence, 'before-connect', adb, serial, env)
                clocks['connect'] = time.monotonic()
                tap(connect)
                time.sleep(max(0, 5 - (time.monotonic() - clocks['connect'])))
                # Dynamic WebView/canvas content is entirely masked, not guessed safe.
                progress['after_connect_screenshot'] = checkpoint(evidence, 'after-connect-5s', adb, serial, env, full_mask=True)
                wait_for(lambda: 'Connect to your Wizard' not in labels(ui()) and 'Chats' in labels(ui()), 90)
                checks['address_pairing_shell'] = True
                progress['stage'] = 'model-reply'
                # Use the release's exported thread handoff, not WebView injection.
                shell('am', 'start', '-W', '-n', PACKAGE + '/.MainActivity', '-a',
                      'ai.wizards.os.action.THREAD', '--es', 'ai.wizards.os.extra.THREAD', chat['session'])
                expected = ' '.join(chat['output'].split())
                wait_for(lambda: expected in ' '.join(labels(ui()).split()), 90)
                checks['model_reply_visible'] = True
                # The first Back must actually leave the nested chat, not merely
                # be swallowed. Subsequent root Back must never finish the app.
                progress['stage'] = 'nested-back'
                assert 'Attach photos or files' in labels(ui())
                shell('input', 'keyevent', 'KEYCODE_BACK')
                wait_for(lambda: foreground() and 'Attach photos or files' not in labels(ui()), 20)
                checks['nested_back_navigates'] = True
                progress['stage'] = 'root-back'
                for _ in range(3):
                    shell('input', 'keyevent', 'KEYCODE_BACK')
                    time.sleep(1)
                    assert foreground()
                checks['nested_and_root_back_stay'] = True
                # Saved choice survives process death; no new Connect prompt.
                progress['stage'] = 'pairing-restart'
                shell('am', 'force-stop', PACKAGE)
                shell('am', 'start', '-W', '-n', PACKAGE + '/.MainActivity')
                wait_for(lambda: 'Connect to your Wizard' not in labels(ui()) and 'Chats' in labels(ui()), 60)
                checks['pairing_survives_restart'] = True
                progress['stage'] = 'crash-check'
                assert 'FATAL EXCEPTION' not in shell('logcat', '-d', '-b', 'crash')
                progress['stage'] = 'https-cleanup'
            return {'passed': all(checks.values()), 'checks': checks, 'apk_version': feed['versionName'],
                    'apk_version_code': feed['versionCode'], 'apk_sha256': feed['sha256'],
                    'transport': 'address-https-to-disposable-box', 'api': 35,
                    'published_owner_default': owner_default,
                    'entry': 'exported-connect' if owner_default else 'generic-first-run',
                    'unpaired_back': 'not-tested-migration-default' if owner_default else 'passed',
                    'physical_device': 'not-tested', 'qr': 'not-tested'}
        except Exception as exc:
            progress['failure_stage'] = progress['stage']
            if 'failure' not in progress:
                progress['failure'] = runtime_note(em, adb, serial, env, clocks)
            progress['failure'].update(exception_note(exc))
            progress['failure']['logcat'] = persistent.summary()
            progress['failure']['screenshots'] = {k: progress[k] for k in
                ('before_connect_screenshot', 'after_connect_screenshot') if k in progress}
            if not (evidence / 'failure/diagnostics.json').exists():
                with contextlib.suppress(Exception):
                    diagnose()
            raise
        finally:
            if network_args.relay is not None:
                with contextlib.suppress(Exception):
                    private_write(evidence / 'relay.json', json.dumps(network_args.relay.snapshot()).encode())
            progress['stage'] = 'emulator-cleanup'
            try:
                stop_emulator(em, adb, serial, env)
            except Exception as exc:
                progress['cleanup_failed'] = True
                progress['cleanup_failure'] = exception_note(exc)
                if not (evidence / 'failure/diagnostics.json').exists():
                    with contextlib.suppress(Exception):
                        diagnose()
                raise
            finally:
                # Remove temporary XML/transcript/cache copies even if stop fails.
                shutil.rmtree(evidence / 'device', ignore_errors=True)
                shutil.rmtree(evidence / 'avd', ignore_errors=True)
