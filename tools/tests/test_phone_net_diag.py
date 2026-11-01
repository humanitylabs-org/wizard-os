"""No VM/emulator boots: diagnostics/relay/Serve cleanup regression coverage."""
import contextlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'acceptance/launch'))
import phone
import phone_diagnostics as diag
import phone_net_diag as net
from phone_transport import connect_proxy
from tools.tests import test_launch_onboarding as fixtures


class NetworkDiagnosticTests(unittest.TestCase):
    def test_real_subprocess_capture_preserves_serial_env_and_redaction(self):
        """Exercise the real subprocess boundary (old mocks hid rc/type problems)."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            png = root / 'fixture.png'
            png.write_bytes(fixtures.PhoneTransportDiagnosticsTests.png())
            adb = root / 'adb'
            adb.write_text('#!' + sys.executable + '\n' + '''import os,sys
from pathlib import Path
assert sys.argv[1:3] == ['-s', 'emulator-5582']
assert os.environ['DIAG_ENV'] == 'retained'
a = sys.argv[3:]
if 'get-state' in a: print('device')
elif 'uiautomator' in a: print('UI hierarchy dumped to: /sdcard/launch-failure.xml')
elif 'cat' in a: print('<hierarchy><node text="Connect" bounds="[0,0][1,1]"/><node text="secret-canary" bounds="[1,0][2,1]"/></hierarchy>')
elif 'screencap' in a: sys.stdout.buffer.write(Path(os.environ['DIAG_PNG']).read_bytes())
elif 'dumpsys' in a: print('topResumedActivity=ActivityRecord{1 u0 ai.wizards.os/.ConnectActivity t2} secret-canary')
elif 'pidof' in a: print('123')
elif 'logcat' in a: print('11-01 05:00:00.000 123 1 E chromium: net::ERR_CONNECTION_REFUSED https://box.example.ts.net/?token=secret-canary')
''')
            adb.chmod(0o700)
            env = dict(os.environ, DIAG_ENV='retained', DIAG_PNG=str(png))
            original = subprocess.run
            def dispatch(argv, **kwargs):
                if 'tailscale' in argv:
                    return SimpleNamespace(returncode=0, stdout=b'{}')
                return original(argv, **kwargs)
            with patch.object(diag.subprocess, 'run', side_effect=dispatch):
                # Same failure boundary and exact adb/serial/env passed by diagnose.
                with self.assertRaisesRegex(RuntimeError, 'original'):
                    with phone.failure_boundary(lambda: diag.capture_failure(root, 'address-pairing', adb=adb,
                            serial='emulator-5582', env=env, box_host='box.example.ts.net')):
                        raise RuntimeError('original')
            status = json.loads((root / 'failure/diagnostics.json').read_text())
            self.assertTrue(all(status[k] == 'saved' for k in ('device', 'labels', 'screenshot', 'activity', 'logcat', 'serve')), status)
            for path in (root / 'failure').iterdir():
                self.assertNotIn(b'secret-canary', path.read_bytes())
            self.assertEqual(json.loads((root / 'failure/network-errors.json').read_text()),
                             [{'error': 'net::ERR_CONNECTION_REFUSED', 'host': 'box'}])

    def test_nonzero_adb_is_distinct_from_limits_and_ui_masking(self):
        for rc, output, expected in ((1, b'', 'nonzero'), (0, b'x' * (diag.MAX_PNG + 1), 'output_limit')):
            def run(argv, **kw):
                if 'tailscale' in argv:
                    return SimpleNamespace(returncode=0, stdout=b'{}')
                return SimpleNamespace(returncode=rc, stdout=output, stderr=b"error: device 'private-canary' not found")
            with tempfile.TemporaryDirectory() as d, patch.object(diag.subprocess, 'run', side_effect=run):
                diag.capture_failure(d, 'address-pairing', adb=Path('adb'), serial='emulator-5582', env={'SENTINEL': '1'})
                status = json.loads((Path(d) / 'failure/diagnostics.json').read_text())
                for name in ('labels', 'screenshot', 'activity'):
                    self.assertEqual(status[name], expected)
                self.assertEqual(status['commands']['screenshot']['rc'], rc)
                self.assertNotIn('private-canary', json.dumps(status))
        rows, masks = diag.ui_evidence('<hierarchy><node text="private-canary"/></hierarchy>')
        self.assertEqual(rows, [['[redacted]']])
        self.assertIsNone(masks)
        self.assertEqual(fixtures.PhoneTransportDiagnosticsTests.pixels(diag.masked_png(fixtures.PhoneTransportDiagnosticsTests.png(), masks)),
                         b'\x00' + b'\x00\x00\x00\xff' * 2)

    def test_logcat_projection_filters_processes_urls_queries_and_bounds(self):
        lines = ['11-01 05:00:00.000 123 1 E App: SSLHandshakeException https://box.example.ts.net/path?secret=canary',
                 '11-01 05:00:00.000 456 1 E unrelated: net::ERR_FAILED https://box.example.ts.net/canary',
                 '11-01 05:00:00.000 456 1 E chromium: net::ERR_PROXY_CONNECTION_FAILED https://other.example/canary',
                 '11-01 05:00:00.000 123 1 E App: CLEARTEXT canary']
        rows = diag.network_errors('\n'.join(lines), 'box.example.ts.net', ['123'])
        self.assertEqual(rows, [{'error': 'SSLHandshakeException', 'host': 'box'},
                                {'error': 'net::ERR_PROXY_CONNECTION_FAILED', 'host': 'other'},
                                {'error': 'CLEARTEXT', 'host': 'other'}])
        self.assertNotIn('canary', json.dumps(rows))
        self.assertEqual(len(diag.network_errors('\n'.join(lines * 100), 'box.example.ts.net', ['123'])), 80)

    def test_proxy_counters_count_upstream_failure_and_denial_without_addresses(self):
        with socket.socket() as closed:
            closed.bind(('127.0.0.1', 0))
            port = closed.getsockname()[1]
        with connect_proxy('127.0.0.1', [], port) as relay:
            endpoint = ('127.0.0.1', int(relay.rsplit(':', 1)[1]))
            for authority in (f'127.0.0.1:{port}', 'other.example:443'):
                with socket.create_connection(endpoint, timeout=3) as client:
                    client.sendall(f'CONNECT {authority} HTTP/1.1\r\n\r\n'.encode())
                    client.recv(4096)
            counts = relay.snapshot()
            self.assertEqual(counts['accepted'], 2)
            self.assertEqual(counts['connect_allowed'], 1)
            self.assertEqual(counts['connect_denied'], 1)
            self.assertEqual(counts['upstream_failed'], 1)
            self.assertTrue(all(type(v) is int for v in counts.values()))

    def test_serve_failure_removes_only_own_port_and_preserves_photos(self):
        before = {'TCP': {'2283': {'HTTPS': True}},
                  'Web': {'box.example.ts.net:2283': {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:2283'}}}}}
        after = json.loads(json.dumps(before))
        after['TCP']['9453'] = {'HTTPS': True}
        # Port of the HTTP fixture is ephemeral; fill the readback dynamically.
        calls = []
        def run(argv, **kw):
            calls.append(argv)
            if '--bg' in argv:
                after.setdefault('Web', {})['box.example.ts.net:9453'] = {'Handlers': {'/': {'Proxy': argv[-1]}}}
            return SimpleNamespace(returncode=0)
        responses = [before, {'Self': {'DNSName': 'box.example.ts.net.'}}, after, before]
        with patch.object(net.subprocess, 'check_output', side_effect=lambda *a, **k: json.dumps(responses.pop(0)).encode()), \
             patch.object(net.subprocess, 'run', side_effect=run):
            checks = {}
            with self.assertRaisesRegex(RuntimeError, 'fixture'):
                with net.served_page(9453, True, checks):
                    raise RuntimeError('fixture')
        self.assertEqual(calls[-1], ['sudo', '-n', 'tailscale', 'serve', '--https=9453', 'off'])
        self.assertEqual(checks, {'serve_removed': True, 'other_handlers_unchanged': True})
        self.assertTrue(net.preserved(before, before))

    def test_failed_preflight_writes_verdict_and_no_emulator_is_started(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'new'
            config = {'sdk': '/sdk', 'java_home': '/java', 'work_root': d}
            with patch.object(net, 'worker_lock', side_effect=RuntimeError('lock')), patch.object(net.subprocess, 'Popen') as popen:
                result = net.run(config, root, 9453)
            popen.assert_not_called()
            self.assertFalse(result['passed'])
            self.assertEqual(result['stage'], 'worker-lock')
            self.assertEqual(json.loads((root / 'verdict.json').read_text()), result)

    def test_emulator_cleanup_kills_if_adb_and_terminate_do_not_work(self):
        from unittest.mock import Mock
        em = Mock()
        em.wait.side_effect = [subprocess.TimeoutExpired('private', 20), subprocess.TimeoutExpired('private', 10), 0]
        with patch.object(net.subprocess, 'run', side_effect=OSError('private')):
            net.stop_emulator(em, Path('adb'), 'emulator-5582', {})
        em.terminate.assert_called_once()
        em.kill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
