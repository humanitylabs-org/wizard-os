"""Runtime regressions; no emulator/VM or owner endpoints."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'acceptance/launch'))
import phone
import phone_runtime as runtime


class PhoneRuntimeTests(unittest.TestCase):
    def test_linux_uses_supported_software_mode_without_changing_mac(self):
        with patch.object(phone.platform, 'system', return_value='Linux'):
            argv = phone.emulator_argv(Path('/sdk'), 5582, '192.0.2.1', [])
            self.assertEqual(argv[argv.index('-gpu') + 1], 'swangle')
        with patch.object(phone.platform, 'system', return_value='Darwin'):
            argv = phone.emulator_argv(Path('/sdk'), 5582, '192.0.2.1', [])
            self.assertEqual(argv[argv.index('-gpu') + 1], 'swiftshader_indirect')
        argv = phone.emulator_argv(Path('/sdk'), 5582, '192.0.2.1', [], {'gpu_mode': 'lavapipe'})
        self.assertEqual(argv[argv.index('-gpu') + 1], 'lavapipe')
        with self.assertRaisesRegex(ValueError, 'phone_gpu_mode'):
            phone.emulator_argv(Path('/sdk'), 5582, '192.0.2.1', [], {'gpu_mode': 'bad --option'})

    def test_memory_is_explicit_and_overrides_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'config.ini'
            path.write_text('hw.ramSize=1536\nvm.heapSize=48\nhw.ramSize=8192\nother=yes\n')
            runtime.configure_avd(path, {'ram_mb': 3072, 'heap_mb': 512})
            text = path.read_text()
            self.assertEqual(text.count('hw.ramSize='), 1)
            self.assertIn('hw.ramSize=3072', text)
            self.assertIn('vm.heapSize=512', text)
            self.assertIn('other=yes', text)
            with self.assertRaises(ValueError):
                runtime.configure_avd(path, {'ram_mb': 1000000})

    def test_failure_projection_never_retains_exception_output_or_private_args(self):
        errors = [RuntimeError('phone_emulator_exited'), RuntimeError('https://private/?token=canary'),
                  subprocess.TimeoutExpired(['/sdk/adb', '-s', 'emulator-5582', 'shell', 'canary'], 3),
                  subprocess.CalledProcessError(1, ['/sdk/adb', 'shell', 'https://private/canary'], output='canary')]
        notes = [runtime.exception_note(e) for e in errors]
        self.assertEqual(notes[0]['message_code'], 'phone_emulator_exited')
        self.assertEqual(notes[1]['message_code'], 'unclassified')
        self.assertEqual(notes[2]['command_args'], ['-s', 'emulator-5582'])
        self.assertEqual(notes[3]['command_args'], ['shell', '[redacted]'])
        self.assertNotIn('canary', json.dumps(notes))
        self.assertNotIn('private', json.dumps(notes))

    def test_death_snapshot_is_taken_before_cleanup_and_keeps_signal_and_device_state(self):
        em = SimpleNamespace(poll=lambda: -9)
        p = SimpleNamespace(returncode=0, stdout='List of devices attached\nemulator-5582\toffline\nowner-canary\tdevice\n')
        with patch.object(runtime.subprocess, 'run', return_value=p), patch.object(runtime.time, 'monotonic', return_value=100):
            note = runtime.runtime_note(em, Path('/sdk/adb'), 'emulator-5582', {}, {'boot': 65, 'connect': 70})
        self.assertEqual(note['emulator_returncode'], -9)
        self.assertEqual(note['emulator_signal'], 'SIGKILL')
        self.assertEqual(note['seconds_since_boot'], 35)
        self.assertEqual(note['seconds_since_connect'], 30)
        self.assertEqual(note['adb_devices']['owned_state'], 'offline')
        self.assertNotIn('owner-canary', json.dumps(note))

    def test_fifo_logcat_survives_writer_death_is_bounded_and_only_projects_counts(self):
        with tempfile.TemporaryDirectory() as d:
            with runtime.PersistentLogcat(Path(d), limit=1024) as log:
                self.assertEqual(log.argv[0], '-logcat-output')
                with open(log.argv[1], 'wb', buffering=0) as writer:
                    writer.write(b'FATAL EXCEPTION secret-token https://private/\nFatal signal 11\nANR in app\nchromium renderer crash\nEGL error\nlowmemorykiller: Killing process\n')
                    writer.write(b'x' * 8192 + b'\n')
                deadline = time.monotonic() + 3
                while log.bytes_seen < 8192 and time.monotonic() < deadline:
                    time.sleep(.01)
            self.assertLessEqual((Path(d) / 'private-logcat.txt').stat().st_size, 1024)
            summary = json.loads((Path(d) / 'logcat-summary.json').read_text())
            for key in ('fatal_exception', 'fatal_signal', 'anr', 'chromium_crash', 'gpu_errors', 'lowmemorykiller_kills'):
                self.assertEqual(summary['counts'][key], 1)
            self.assertTrue(summary['retention_truncated'])
            self.assertNotIn('secret-token', json.dumps(summary))
            self.assertFalse(Path(log.argv[1]).exists())
            self.assertEqual((Path(d) / 'private-logcat.txt').stat().st_mode & 0o777, 0o600)


class PairingFailureTests(unittest.TestCase):
    def exercise_failure(self, failure):
        import contextlib
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / 'phone.json'
            config.write_text(json.dumps({'sdk': str(root), 'work_root': str(root), 'java_home': str(root)}))
            connected = False
            origin = 'https://box.example.ts.net:9450'
            def command(argv, **kw):
                nonlocal connected
                text = ' '.join(map(str, argv))
                output = ''
                if 'tailscale status' in text:
                    output = json.dumps({'Self': {'DNSName': 'box.example.ts.net.'}})
                elif 'sys.boot_completed' in text:
                    output = '1'
                elif 'ro.build.version.sdk' in text:
                    output = '35'
                elif ' install ' in text:
                    output = 'Success'
                elif ' ping ' in text:
                    output = 'PING box.example.ts.net (192.0.2.1)'
                elif 'input tap 30 30' in text:
                    connected = True
                elif 'shell cat /sdcard/launch-ui.xml' in text:
                    if connected and failure == 'timeout':
                        raise subprocess.TimeoutExpired(argv, 60, output='private-canary')
                    output = ('<hierarchy><node text="Change Wizard"/>'
                              '<node class="android.widget.EditText" text="' + origin + '" bounds="[0,0][10,10]"/>'
                              '<node text="Connect" bounds="[20,20][40,40]"/></hierarchy>')
                if 'devices' in argv:
                    output = 'List of devices attached\n'
                return SimpleNamespace(returncode=0, stdout=output, stderr='')
            em = Mock()
            em.poll.side_effect = lambda: -11 if connected and failure == 'exit' else None
            with patch.object(phone.platform, 'system', return_value='Darwin'), \
                 patch.object(phone, 'native_system_image', return_value='api35'), \
                 patch.object(phone, 'host_resolver', return_value='192.0.2.1'), \
                 patch.object(phone, 'validate_apk', return_value=(root / 'apk', {}, True)), \
                 patch.object(phone, 'worker_lock', return_value=contextlib.nullcontext()), \
                 patch.object(phone, 'configure_avd'), \
                 patch.object(phone, 'https_forward', return_value=contextlib.nullcontext(origin)), \
                 patch.object(phone, 'checkpoint', return_value={'saved': True}), \
                 patch.object(phone, 'capture_failure'), \
                 patch.object(phone.subprocess, 'run', side_effect=command), \
                 patch.object(phone.subprocess, 'Popen', return_value=em), \
                 patch.object(phone.time, 'sleep'):
                result = phone.run_phone('lc-fresh', 'unused', root, config, {})
            self.assertEqual(result['failure_stage'], 'address-pairing', result)
            self.assertFalse(result['passed'])
            self.assertTrue(result['checks']['tailnet_dns'])
            self.assertIn('seconds_since_connect', result['failure'])
            self.assertNotIn('private-canary', json.dumps(result))
            self.assertTrue((root / 'logcat-summary.json').exists())
            em.wait.assert_called_once()
            return result

    def test_emulator_death_keeps_exit_and_signal_before_cleanup(self):
        result = self.exercise_failure('exit')
        self.assertEqual(result['failure']['message_code'], 'phone_emulator_exited')
        self.assertEqual(result['failure']['emulator_returncode'], -11)
        self.assertEqual(result['failure']['emulator_signal'], 'SIGSEGV')
        self.assertEqual(result['failure']['adb_devices']['owned_state'], 'missing')

    def test_uiautomator_timeout_is_not_misreported_as_emulator_death(self):
        result = self.exercise_failure('timeout')
        self.assertEqual(result['failure']['exception_class'], 'TimeoutExpired')
        self.assertIsNone(result['failure']['emulator_returncode'])
        self.assertEqual(result['failure']['command_args'], ['-s', 'emulator-5682'])


class CrashDiagnosticTests(unittest.TestCase):
    def test_modes_share_lock_and_clean_serve_before_releasing_it(self):
        import contextlib
        import phone_crash_diag as crash
        events = []
        @contextlib.contextmanager
        def lock(work):
            events.append('lock')
            yield
            events.append('unlock')
        @contextlib.contextmanager
        def serve(port, sudo, checks, body):
            self.assertEqual(port, 9453)
            self.assertIn(b'Synthetic WebView diagnostic', body)
            events.append('serve')
            yield 'https://box.example.ts.net:9453', {}, None
            checks.update(serve_removed=True, other_handlers_unchanged=True)
            events.append('serve-off')
        def mode(config, root, origin, status):
            events.append(config['gpu_mode'])
            return {'passed': True, 'checks': {'emulator_stopped': True}}
        with tempfile.TemporaryDirectory() as d, patch.object(crash, 'worker_lock', lock), \
             patch.object(crash, 'served_page', serve), patch.object(crash, 'run_mode', mode):
            result = crash.run({'work_root': d}, Path(d) / 'new', ['swiftshader_indirect', 'swangle'])
        self.assertTrue(result['passed'])
        self.assertFalse(result['pairing_tested'])
        self.assertEqual(events, ['lock', 'serve', 'swiftshader_indirect', 'swangle', 'serve-off', 'unlock'])

    def test_failed_cleanup_or_deadline_never_starts_second_emulator(self):
        import contextlib
        import phone_crash_diag as crash
        for entry in ({'passed': False, 'checks': {'emulator_stopped': False}},
                      {'passed': False, 'checks': {'emulator_stopped': True},
                       'failure': {'message_code': 'phone_diagnostic_deadline'}}):
            with tempfile.TemporaryDirectory() as d, \
                 patch.object(crash, 'worker_lock', return_value=contextlib.nullcontext()), \
                 patch.object(crash, 'served_page', return_value=contextlib.nullcontext(('https://box.example.ts.net:9453', {}, None))), \
                 patch.object(crash, 'run_mode', return_value=entry) as mode:
                result = crash.run({'work_root': d}, Path(d) / 'new', ['swiftshader_indirect', 'swangle'])
            mode.assert_called_once()
            self.assertFalse(result['passed'])

    def test_diagnostic_boot_death_writes_verdict_stops_process_and_removes_avd(self):
        import contextlib
        import phone_crash_diag as crash
        from unittest.mock import Mock
        em = Mock()
        em.poll.return_value = -11
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'swangle'
            config = {'sdk': '/sdk', 'java_home': '/java', 'gpu_mode': 'swangle'}
            with patch.object(crash, 'emulator_network', return_value=contextlib.nullcontext(phone.NetworkArgs())), \
                 patch.object(crash, 'validate_apk', return_value=(Path('/apk'), {'versionName': 'test', 'sha256': '0' * 64}, True)), \
                 patch.object(crash, 'configure_avd'), \
                 patch.object(crash, 'native_system_image', return_value='api35'), \
                 patch.object(crash, 'host_resolver', return_value='192.0.2.1'), \
                 patch.object(crash.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')), \
                 patch.object(crash.subprocess, 'Popen', return_value=em) as start, \
                 patch.object(crash, 'capture_failure'):
                result = crash.run_mode(config, root, 'https://box.example.ts.net:9453', {'Self': {'DNSName': 'box.example.ts.net.'}})
            self.assertEqual(result['failure']['message_code'], 'phone_emulator_exited')
            self.assertEqual(result['failure']['emulator_signal'], 'SIGSEGV')
            self.assertTrue(result['checks']['emulator_stopped'])
            self.assertFalse(result['passed'])
            self.assertEqual(json.loads((root / 'verdict.json').read_text()), result)
            self.assertFalse((root / 'avd').exists())
            self.assertFalse((root / 'device').exists())
            self.assertIn('-logcat-output', start.call_args.args[0])
            em.wait.assert_called_once()


if __name__ == '__main__':
    unittest.main()
