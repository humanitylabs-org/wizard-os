#!/usr/bin/env python3
"""Queued API35 HTTPS transport proof, no Wizard VM, credentials or fake pairing.

Run only through the heavy worker. A tiny page is explicitly a network fixture,
not a Wizard shell. Success requires its text in Android plus opaque relay bytes.
"""
import argparse
import contextlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

from phone import (center, emulator_argv, emulator_network, host_resolver, labels,
                   native_system_image, worker_lock)
from phone_diagnostics import capture_failure, private_write

MARKER = 'Wizard network diagnostic ready'


def preserved(before, after):
    return all(after.get(k, {}).get(n) == v for k in ('TCP', 'Web')
               for n, v in before.get(k, {}).items())


@contextlib.contextmanager
def served_page(port, sudo, checks, body=None):
    def ts(*args):
        return json.loads(subprocess.check_output(
            (['sudo', '-n'] if sudo else []) + ['tailscale', *map(str, args)],
            stderr=subprocess.DEVNULL, timeout=20))

    # Reused by the crash fixture: never accept a live/shared Serve port.
    if port != 9453:
        raise ValueError('diagnostic_port')
    page_body = body if body is not None else ('<!doctype html><title>Network diagnostic</title><h1>' + MARKER + '</h1>').encode()
    before = ts('serve', 'status', '--json')
    if str(port) in before.get('TCP', {}) or any(k.endswith(':' + str(port)) for k in before.get('Web', {})):
        raise RuntimeError('serve_port_busy')
    status = ts('status', '--json')
    host = status['Self']['DNSName'].rstrip('.')
    key = f'{host}:{port}'
    received = threading.Event()

    class Page(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = page_body
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            received.set()

        def log_message(self, format, *args):
            pass

    with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Page) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        target = f'http://127.0.0.1:{server.server_port}'
        prefix = (['sudo', '-n'] if sudo else []) + ['tailscale', 'serve']
        try:
            subprocess.run(prefix + ['--bg', '--yes', f'--https={port}', target],
                           check=True, capture_output=True, timeout=20)
            after = ts('serve', 'status', '--json')
            if not preserved(before, after) or after['Web'][key]['Handlers']['/']['Proxy'] != target:
                raise RuntimeError('serve_preservation')
            yield f'https://{host}:{port}', status, received
        finally:
            try:
                subprocess.run(prefix + [f'--https={port}', 'off'], check=True, capture_output=True, timeout=20)
                after = ts('serve', 'status', '--json')
                checks['serve_removed'] = key not in after.get('Web', {}) and str(port) not in after.get('TCP', {})
                checks['other_handlers_unchanged'] = preserved(before, after)
                if not checks['serve_removed'] or not checks['other_handlers_unchanged']:
                    raise RuntimeError('serve_cleanup')
            finally:
                server.shutdown()
                thread.join(timeout=5)


def stop_emulator(em, adb, serial, env):
    if em is None:
        return
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run([str(adb), '-s', serial, 'emu', 'kill'], env=env, capture_output=True, timeout=15)
    try:
        em.wait(timeout=20)
    except subprocess.TimeoutExpired:
        em.terminate()
        try:
            em.wait(timeout=10)
        except subprocess.TimeoutExpired:
            em.kill()
            em.wait(timeout=10)


def run(config, root, https_port):
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    root.chmod(0o700)
    sdk = Path(config['sdk'])
    adb = sdk / 'platform-tools/adb'
    port = config.get('emulator_port', 5582)
    serial = f'emulator-{port}'
    env = os.environ.copy()
    env.pop('http_proxy', None)
    env.update(JAVA_HOME=config['java_home'], ANDROID_HOME=str(sdk), ANDROID_SDK_ROOT=str(sdk),
               ANDROID_AVD_HOME=str(root / 'avd'))
    env['PATH'] = config['java_home'] + '/bin:' + env['PATH']
    Path(env['ANDROID_AVD_HOME']).mkdir()
    checks = {}
    verdict = {'passed': False, 'stage': 'worker-lock', 'checks': checks,
               'transport': 'android-system-proxy', 'pairing_tested': False}
    em = None
    network = None

    def call(argv, timeout=30, **kwargs):
        p = subprocess.run(list(map(str, argv)), env=env, capture_output=True, text=True, timeout=timeout, **kwargs)
        if p.returncode:
            raise RuntimeError('command_failed')
        return p.stdout

    def shell(*args):
        return call([adb, '-s', serial, 'shell', *args])

    def ui():
        shell('uiautomator', 'dump', '--compressed', '/sdcard/network-ui.xml')
        return shell('cat', '/sdcard/network-ui.xml')

    def wait(predicate, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if em is None or em.poll() is not None:
                raise RuntimeError('emulator_exited')
            try:
                if predicate():
                    return
            except (RuntimeError, ET.ParseError):
                pass
            time.sleep(1)
        raise RuntimeError('timeout')

    try:
        # Reuse the exact inherited lease validation; never open a second lock
        # against our parent. Cleanup runs while this lease is still held.
        with worker_lock(config['work_root']):
            if serial in call([adb, 'devices']):
                raise RuntimeError('device_busy')
            verdict['stage'] = 'serve'
            with served_page(https_port, config.get('tailscale_sudo', False), checks) as (origin, status, received):
                with emulator_network(status, https_port) as network:
                    try:
                        verdict['stage'] = 'avd-create'
                        call([sdk / 'cmdline-tools/latest/bin/avdmanager', 'create', 'avd', '-n', 'launch_phone',
                              '-k', native_system_image(), '-d', 'pixel_7', '-p', root / 'device'], input='no\n', timeout=90)
                        dns = config.get('dns_server') or host_resolver(status['Self']['DNSName'], call)
                        verdict['stage'] = 'emulator-boot'
                        fd = os.open(root / 'private-emulator.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                        with os.fdopen(fd, 'w') as log:
                            em = subprocess.Popen(emulator_argv(sdk, port, dns, network), env=env, stdout=log, stderr=log)
                        wait(lambda: shell('getprop', 'sys.boot_completed').strip() == '1', 240)
                        checks['api35'] = shell('getprop', 'ro.build.version.sdk').strip() == '35'
                        network.configure(shell)
                        checks['proxy_readback'] = network.relay is not None
                        host = status['Self']['DNSName'].rstrip('.')
                        ips = [v for v in status['Self']['TailscaleIPs'] if ':' not in v]
                        verdict['stage'] = 'tcp-probe'
                        # Direct TCP is a contrast probe, not HTTPS or proxy proof.
                        tcp = subprocess.run([str(adb), '-s', serial, 'shell', 'toybox', 'nc', '-w', '5',
                                              ips[0], str(https_port)], env=env, input=b'', capture_output=True, timeout=10)
                        verdict['direct_tcp_rc'] = tcp.returncode
                        shell('input', 'keyevent', 'KEYCODE_WAKEUP')
                        shell('wm', 'dismiss-keyguard')
                        shell('logcat', '-c')
                        verdict['stage'] = 'https-page'
                        shell('am', 'start', '-W', '-a', 'android.intent.action.VIEW', '-d', origin)

                        def page_visible():
                            xml = ui()
                            if MARKER in labels(xml) and received.is_set():
                                return True
                            # Chrome first-run controls only; no account sign-in,
                            # TLS override, debug flags or application prefs.
                            dismiss = {'Accept & continue', 'Use without an account', 'No thanks', 'Got it'}
                            for node in ET.fromstring(xml).iter('node'):
                                if node.get('text') in dismiss or node.get('content-desc') in dismiss:
                                    shell('input', 'tap', *center(node))
                                    break
                            return False

                        wait(page_visible, 150)
                        checks['https_page_visible'] = True
                        verdict['relay'] = network.relay.snapshot() if network.relay else {}
                        checks['relay_carried_tls'] = all(verdict['relay'].get(k, 0) > 0
                                                         for k in ('connect_allowed', 'upstream_ok', 'bytes_to_box', 'bytes_to_android'))
                        # Exercise real capture call path even on a successful probe.
                        capture_failure(root, 'network-diagnostic', adb=adb, serial=serial, env=env,
                                        sudo=config.get('tailscale_sudo', False), port=https_port,
                                        relay=network.relay, box_host=host)
                        diag = json.loads((root / 'failure/diagnostics.json').read_text())
                        checks['diagnostics_saved'] = all(diag.get(k) == 'saved' for k in ('labels', 'screenshot', 'activity', 'logcat', 'relay', 'serve'))
                    except Exception:
                        if em is not None:
                            with contextlib.suppress(Exception):
                                capture_failure(root, verdict['stage'], adb=adb, serial=serial, env=env,
                                                sudo=config.get('tailscale_sudo', False), port=https_port,
                                                relay=network.relay, box_host=status['Self']['DNSName'].rstrip('.'))
                        raise
                    finally:
                        try:
                            stop_emulator(em, adb, serial, env)
                            checks['emulator_stopped'] = em is None or em.poll() is not None
                        finally:
                            shutil.rmtree(root / 'device', ignore_errors=True)
                            shutil.rmtree(root / 'avd', ignore_errors=True)
            verdict['passed'] = bool(checks) and all(checks.values())
            if verdict['passed']:
                verdict['stage'] = 'complete'
    except Exception as exc:
        verdict['error_class'] = type(exc).__name__ if type(exc) in (RuntimeError, OSError, subprocess.TimeoutExpired) else 'unavailable'
    finally:
        if network is not None and network.relay is not None:
            verdict['relay'] = network.relay.snapshot()
        private_write(root / 'verdict.json', json.dumps(verdict, sort_keys=True).encode())
    return verdict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phone-config', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path, help='New private directory beneath WIZARD_WORK_ROOT')
    parser.add_argument('--https-port', type=int, default=9453)
    args = parser.parse_args()
    work = Path(os.environ['WIZARD_WORK_ROOT']).resolve()
    if work not in args.root.resolve().parents or args.https_port != 9453:
        parser.error('require a new work-root child and dedicated port 9453')
    config = json.loads(args.phone_config.read_text())
    # SIGTERM from the worker deadline must unwind Serve/emulator scopes too.
    def interrupted(signum, frame):
        raise RuntimeError('interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    verdict = run(config, args.root, args.https_port)
    print(json.dumps(verdict, sort_keys=True))
    return 0 if verdict['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
