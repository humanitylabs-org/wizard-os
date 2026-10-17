#!/usr/bin/env python3
"""Control-plane unit tests only: no VM, Docker, network, or browser execution."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load('e2e_022_ui_proof')
guest = load('e2e_022_ui_guest')


class RunnerTests(unittest.TestCase):
    def setUp(self):
        guest.REPORT['commands'] = []
        guest.REPORT['stages'] = []

    def test_lima_json_shapes(self):
        row = {'name': host.GUESTS[0], 'status': 'Stopped'}
        self.assertEqual(host.parse_lima(json.dumps([row])), [row])
        self.assertEqual(host.parse_lima(json.dumps(row)), [row])
        self.assertEqual(host.parse_lima(json.dumps(row) + '\n' + json.dumps(row)), [row, row])

    def test_control_plane_rejected_before_filesystem(self):
        with patch.object(host.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(RuntimeError, 'Thales/macOS-only'):
                host.validate_target(Path('/Volumes/ThalesMedia/wizard-os/e2e-022'), list(host.GUESTS))

    def test_no_other_guests_or_root(self):
        with patch.object(host.platform, 'system', return_value='Darwin'):
            for root, vms in [(Path('/Users/owner/e2e-022'), list(host.GUESTS)),
                              (Path('/Volumes/ThalesMedia/wizard-os/e2e-022'), ['production'])]:
                with self.assertRaises(RuntimeError):
                    host.validate_target(root, vms)

    def test_only_owned_stopped_guest_paths(self):
        with patch.object(host.platform, 'system', return_value='Darwin'), patch.object(Path, 'is_file', return_value=True):
            host.validate_target(Path('/Volumes/ThalesMedia/wizard-os/e2e-022'), list(host.GUESTS))
            with self.assertRaises(RuntimeError):
                host.validate_target(Path('/Volumes/ThalesMedia/wizard-os/e2e-022'), [host.GUESTS[0]] * 2)

    def test_endpoint_rewrites_only_authority(self):
        self.assertEqual(guest.loopback_url('http://192.168.1.5:8787/mcp'), 'http://127.0.0.1:8787/mcp')
        for value in ['http://user:secret@host:8787/mcp', 'https://host:8787/mcp', 'http://host:8787/mcp?token=secret']:
            with self.assertRaises(guest.CheckError):
                guest.loopback_url(value)

    def test_command_failure_does_not_leak_child_output(self):
        with patch.object(guest.subprocess, 'run', return_value=Mock(returncode=1, stdout='SECRET', stderr='SECRET')):
            with self.assertRaises(guest.CheckError) as e:
                guest.run(['wam', 'install', 'defleur-video'])
        self.assertNotIn('SECRET', str(e.exception) + json.dumps(guest.REPORT))
        self.assertEqual(guest.REPORT['commands'][0]['exit_code'], 1)

    def test_unexpected_error_receipt_does_not_leak_exception(self):
        def bad():
            raise ValueError('SECRET')
        self.assertIsNone(guest.stage('probe', bad))
        self.assertEqual(guest.REPORT['stages'][0]['reason'], 'ValueError')
        self.assertNotIn('SECRET', json.dumps(guest.REPORT))

    def test_startup_constructor_inside_try_and_retried(self):
        with patch.object(guest.time, 'sleep'), patch.object(guest.subprocess, 'run', side_effect=[
                subprocess.TimeoutExpired('probe', 20), Mock(returncode=0)]) as run:
            result = guest.wait_ready()
        self.assertEqual(result['attempts'], 2)
        probe = run.call_args.args[0][-1]
        self.assertLess(probe.index('try:'), probe.index('c.runtipi()'))
        self.assertLessEqual(run.call_args.kwargs['timeout'], 20)

    def test_startup_deadline_is_bounded(self):
        with patch.object(guest.time, 'monotonic', side_effect=[0, 181]), patch.object(guest.subprocess, 'run') as run:
            with self.assertRaisesRegex(guest.CheckError, '180 seconds'):
                guest.wait_ready()
        run.assert_not_called()

    def test_metadata_allowlist(self):
        projected = guest.safe_app({'id': 'defleur-video', 'commit': guest.APP_SHA, 'token': 'SECRET', 'env': 'SECRET'})
        self.assertNotIn('SECRET', json.dumps(projected))

    def test_real_mcp_protocol_discovery_without_tools_call(self):
        calls = []
        tools = ['workflow_guide', 'capabilities', 'list_files', 'import_file', 'start_edit']
        def urlopen(req, **kwargs):
            data = json.loads(req.data)
            calls.append(data['method'])
            if data['method'] == 'initialize':
                result = {'protocolVersion': '2024-11-05'}
            elif data['method'] == 'tools/list':
                result = {'tools': [{'name': n} for n in tools]}
            else:
                result = {}
            response = Mock(headers={'Mcp-Session-Id': 'SECRET'})
            response.read.return_value = json.dumps({'jsonrpc': '2.0', 'id': data.get('id'), 'result': result}).encode()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            return response
        with patch.object(guest.urllib.request, 'urlopen', side_effect=urlopen):
            result = guest.rpc_discovery('http://127.0.0.1:8787/mcp')
        self.assertEqual(calls, ['initialize', 'notifications/initialized', 'tools/list'])
        self.assertEqual(result['tool_count'], len(tools))
        self.assertEqual(result['tools_called'], [])
        self.assertNotIn('SECRET', json.dumps(result))

    def test_child_process_cleanup_on_timeout(self):
        process = Mock(pid=1234)
        process.communicate.side_effect = subprocess.TimeoutExpired('child', 1)
        process.poll.return_value = None
        with patch.object(host.subprocess, 'Popen', return_value=process), patch.object(host.os, 'killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):
                host.execute(['unused'], {}, timeout=1)
        kill.assert_called_once_with(1234, host.signal.SIGTERM)
        process.wait.assert_called_once_with(timeout=10)


if __name__ == '__main__':
    unittest.main()
