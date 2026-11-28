"""Capacity-policy regressions only; no VM, Android, or remote work is run."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

LAUNCH = Path(__file__).resolve().parents[1] / 'acceptance/launch'
GIB = 1 << 30


def load(name):
    spec = importlib.util.spec_from_file_location('capacity_test_' + name, LAUNCH / (name + '.py'))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, 'path', [str(LAUNCH), *sys.path]):
        spec.loader.exec_module(module)
    return module


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(sys, 'path', [str(LAUNCH), *sys.path]))
        self.runner = load('run')
        self.enterContext(patch.dict(sys.modules, {'run': self.runner}))
        self.gate = load('release_gate')
        self.enterContext(patch.dict(sys.modules, {'release_gate': self.gate}))

    def host(self, system):
        self.enterContext(patch.object(platform, 'system', return_value=system))
        self.enterContext(patch.object(platform, 'machine', return_value='x86_64' if system == 'Linux' else 'arm64'))

    def test_shared_budget_components_and_totals(self):
        capacity = load('capacity')
        self.assertEqual(capacity.LINUX_ANDROID_COEXISTENCE_GIB, 32)
        self.assertEqual(capacity.LINUX_DAILY_FIX_SCRATCH_GIB, 16)
        self.assertEqual(capacity.LINUX_EMERGENCY_FREE_FLOOR_GIB, 12)
        self.assertEqual(capacity.METADATA_GIB, 1)
        self.assertEqual(capacity.PHONE_GIB, 9)
        for system, reserve, disk, without_phone, with_phone in (
                ('Linux', 60, 40, 101, 110), ('Darwin', 250, 50, 301, 310)):
            with self.subTest(system=system), patch.object(platform, 'system', return_value=system):
                self.assertEqual(capacity.reserve_gib(), reserve)
                self.assertEqual(capacity.required_free_gib(disk), without_phone)
                self.assertEqual(capacity.required_free_gib(disk, phone=True), with_phone)

    def check_launch_boundary(self, system, phone, required):
        self.host(system)
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            cli = work / 'wam/wizard-cli/wizard'
            cli.parent.mkdir(parents=True)
            cli.touch()
            argv = ['run.py', '--root', str(work / 'run'), '--release', '0.3.94',
                    '--cli', str(cli), '--check-only']
            if phone:
                argv += ['--phone-config', 'unused', '--first-chat-secret', str(work / 'secret/key'),
                         '--secrets-root', str(work / 'secret'), '--oauth-source', str(work / 'oauth')]
            # The credential and command mocks are guards: check-only never opens
            # a real connection, creates a VM, or reads private credential bytes.
            import first_chat
            with patch.object(sys, 'argv', argv), patch.dict(os.environ, WIZARD_WORK_ROOT=td), \
                    patch.object(Path, 'is_mount', return_value=system == 'Darwin'), \
                    patch.object(first_chat, 'private_file'), patch.object(first_chat, 'validate_oauth_source'), \
                    patch.object(self.runner.shutil, 'disk_usage') as usage, \
                    patch.object(self.runner, 'command') as command, \
                    contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                usage.return_value.free = required * GIB - 1
                with self.assertRaises(SystemExit) as caught:
                    self.runner.main()
                self.assertEqual(caught.exception.code, 2)
                usage.return_value.free += 1
                self.assertEqual(self.runner.main(), 0)
                value = json.loads(out.getvalue())
                self.assertTrue(value['preflight'])
                self.assertFalse(value['executed'])
                self.assertEqual(value['required_free_gib'], required)
                self.assertEqual(value['reserve_gib'], 60 if system == 'Linux' else 250)
                self.assertEqual(value['disk_gib'], 40 if system == 'Linux' else 50)
                command.assert_not_called()
            self.assertFalse((work / 'run').exists())

    def test_linux_admission_exact_101_gib_boundary(self):
        self.check_launch_boundary('Linux', False, 101)

    def test_linux_phone_admission_exact_110_gib_boundary(self):
        self.check_launch_boundary('Linux', True, 110)

    def test_mac_admission_unchanged_with_and_without_phone(self):
        for phone, required in ((False, 301), (True, 310)):
            with self.subTest(phone=phone):
                self.check_launch_boundary('Darwin', phone, required)

    def test_command_floor_exact_bytes_and_depleted_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            for system, reserve in (('Linux', 60), ('Darwin', 250)):
                with self.subTest(system=system), patch.object(platform, 'system', return_value=system), \
                        patch.dict(os.environ, WIZARD_WORK_ROOT=td), \
                        patch.object(self.runner.shutil, 'disk_usage') as usage, \
                        patch.object(self.runner.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
                    log = Path(td) / 'log'
                    usage.return_value.free = reserve * GIB - 1
                    with self.assertRaisesRegex(RuntimeError, '^disk_reserve$'):
                        self.runner.command(['limactl', 'start', 'fixture'], log)
                    run.assert_not_called()
                    usage.return_value.free += 1
                    self.runner.command(['limactl', 'start', 'fixture'], log)
                    run.assert_called_once()
                    usage.return_value.free = 0
                    for argv in (['limactl', 'start', 'fixture'], ['limactl', 'stop', 'fixture'],
                                 ['limactl', 'delete', 'fixture'], ['python3', 'fixture.py']):
                        with self.assertRaisesRegex(RuntimeError, '^disk_reserve$'):
                            self.runner.command(argv, log)
                    for action in ('stop', 'delete'):
                        self.runner.command(['limactl', action, '-f', 'fixture'], log)
                    self.assertEqual(run.call_count, 3)

    def test_release_gate_exact_boundary_and_check_only_receipt(self):
        for system, required, reserve in (('Linux', 101, 60), ('Darwin', 291, 250)):
            with self.subTest(system=system), patch.object(platform, 'system', return_value=system), \
                    patch.object(platform, 'machine', return_value='x86_64' if system == 'Linux' else 'arm64'), \
                    tempfile.TemporaryDirectory() as td:
                cli = Path(td) / 'cli'; cli.touch()
                work = Path('/capacity-test')  # check-only: short synthetic mount; nothing created
                argv = ['release_gate.py', '--root', str(work / 'v'), '--release', '0.3.94',
                        '--previous-release', '0.3.39', '--cli', str(cli), '--wam-commit', 'a' * 40, '--check-only']
                with patch.object(sys, 'argv', argv), patch.dict(os.environ, WIZARD_WORK_ROOT=str(work)), \
                        patch.object(Path, 'is_mount', return_value=True), \
                        patch.object(self.gate.shutil, 'disk_usage') as usage, \
                        patch.object(self.gate.launch, 'command') as command, \
                        patch.object(self.gate.threading, 'Thread') as thread, \
                        contextlib.redirect_stdout(io.StringIO()) as out:
                    usage.return_value.free = required * GIB - 1
                    with self.assertRaises(AssertionError):
                        self.gate.main()
                    usage.return_value.free += 1
                    self.assertEqual(self.gate.main(), 0)
                    value = json.loads(out.getvalue())
                    self.assertEqual((value['reserve_gib'], value['required_free_gib'], value['disk_gib']),
                                     (reserve, required, 40))
                    command.assert_not_called()
                    thread.assert_not_called()
                self.assertFalse((work / 'v').exists())

    def release_fixture(self, work, free, disposable, thread=None):
        cli = work / 'cli'; cli.touch()
        argv = ['release_gate.py', '--root', str(work / 'v'), '--release', '0.3.94',
                '--previous-release', '0.3.39', '--cli', str(cli), '--wam-commit', 'a' * 40]
        with patch.object(sys, 'argv', argv), patch.dict(os.environ, WIZARD_WORK_ROOT=str(work)), \
                patch.object(Path, 'is_mount', return_value=True), \
                patch.object(self.gate.shutil, 'disk_usage', side_effect=lambda _: SimpleNamespace(free=free[0])), \
                patch.object(self.gate.threading, 'Thread', side_effect=thread), \
                patch.object(self.gate.launch, 'disposable_cases', side_effect=disposable), \
                patch.object(self.gate.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            code = self.gate.main()
        value = json.loads((work / 'v/evidence/receipt.json').read_text())
        return code, value, run

    def test_release_gate_command_floor_and_cleanup_use_shared_policy(self):
        self.host('Linux')
        free = [101 * GIB]
        def disposable(args, evidence, vm, create, install, journey, delete, result):
            self.assertEqual((result['reserve_gib'], result['disk_gib'], result['required_free_gib']), (60, 40, 101))
            free[0] = 60 * GIB
            install(vm, evidence / 'install', args.release)
            free[0] -= 1
            with self.assertRaises(AssertionError):
                install(vm, evidence / 'install', args.release)
            free[0] = 0
            delete(vm)  # both forced cleanup commands must bypass the floor
        with tempfile.TemporaryDirectory() as td:
            code, value, run = self.release_fixture(Path(td), free, disposable)
        self.assertEqual(code, 0)
        self.assertTrue(value['passed'])
        self.assertEqual(run.call_count, 3)
        self.assertEqual([c.args[0][:3] for c in run.call_args_list[1:]],
                         [['limactl', 'stop', '-f'], ['limactl', 'delete', '-f']])

    def test_daily_disposable_deleted_before_retained_create_or_start(self):
        self.host('Linux')
        # No VM commands run. A short deterministic run ID keeps the synthetic
        # socket path within Lima's limit even under the managed scratch root.
        clock = Mock(wraps=self.runner.dt.datetime)
        clock.now.return_value = SimpleNamespace(
            strftime=lambda _: 'r1', isoformat=lambda: '2026-11-04T00:00:00+00:00')
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as td:
                work = Path(td)
                root = work / 'r'
                retained = root / 'lima/launch-real-use'
                if existing:
                    retained.mkdir(parents=True)
                cli = work / 'cli'; cli.touch()
                events = []
                def disposable(args, evidence, vm, create, install, journey, delete, result):
                    events.append(('disposable', vm))
                    (root / 'lima' / vm).mkdir(parents=True)
                def command(argv, log, timeout=1800):
                    if argv[:2] == ['limactl', 'delete']:
                        events.append(('delete', argv[-1]))
                        (root / 'lima' / argv[-1]).rmdir()
                    elif argv[:2] in (['limactl', 'create'], ['limactl', 'start']):
                        # The sizing contract: disposable disk is gone BEFORE
                        # any retained VM allocation/start can consume space.
                        self.assertFalse((root / 'lima/lc-r1').exists())
                        events.append(('retained', 'launch-real-use'))
                    elif str(LAUNCH / 'capture.py') in argv:
                        target = Path(argv[argv.index(str(LAUNCH / 'capture.py')) + 1])
                        if str(LAUNCH / 'interventions.py') in argv:
                            value = {'interactive_logins': 0}
                        else:
                            value = {'passed': True, 'release': '0.3.94',
                                     'contact': True, 'setup_route': True}
                        target.write_text(json.dumps(value))
                argv = ['run.py', '--root', str(root), '--release', '0.3.94', '--cli', str(cli)]
                with patch.object(sys, 'argv', argv), patch.dict(os.environ, WIZARD_WORK_ROOT=td), \
                        patch.object(self.runner.dt, 'datetime', clock), \
                        patch.object(self.runner.shutil, 'disk_usage', return_value=SimpleNamespace(free=101 * GIB)), \
                        patch.object(self.runner, 'disposable_cases', side_effect=disposable), \
                        patch.object(self.runner, 'command', side_effect=command), \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(self.runner.main(), 0)
                self.assertLess(events.index(('delete', 'lc-r1')),
                                events.index(('retained', 'launch-real-use')))
                self.assertEqual(events.count(('delete', 'lc-r1')), 1)

    def test_release_monitor_exact_metadata_trigger_and_cleanup_after_latch(self):
        for system, reserve in (('Linux', 60), ('Darwin', 250)):
            for below in (False, True):
                with self.subTest(system=system, below=below), \
                        patch.object(platform, 'system', return_value=system), \
                        patch.object(platform, 'machine', return_value='x86_64' if system == 'Linux' else 'arm64'), \
                        tempfile.TemporaryDirectory() as td:
                    free = [(reserve + 41) * GIB]
                    # A deterministic synchronous watcher: no background thread or sleeps.
                    stop = Mock(); stop.wait.side_effect = [False, True]
                    low_space = Mock(); low_space.is_set.return_value = False
                    low_space.set.side_effect = lambda: setattr(low_space.is_set, 'return_value', True)
                    def thread(*, target, daemon):
                        def start():
                            free[0] = (reserve + 1) * GIB - int(below)
                            target()
                        return SimpleNamespace(start=start, join=lambda **kw: None)
                    def disposable(args, evidence, vm, create, install, journey, delete, result):
                        if below:
                            with self.assertRaises(AssertionError):
                                install(vm, evidence / 'install', args.release)
                        else:
                            install(vm, evidence / 'install', args.release)
                        free[0] = 0
                        delete(vm)
                    with patch.object(self.gate.threading, 'Event', side_effect=[stop, low_space]):
                        code, value, run = self.release_fixture(Path(td), free, disposable, thread)
                    self.assertEqual(code, int(below))
                    self.assertEqual(value['low_space'], below)
                    self.assertEqual(value['passed'], not below)
                    self.assertEqual(value['reserve_gib'], reserve)
                    self.assertEqual(value['required_free_gib'], reserve + 41)
                    self.assertEqual(run.call_count, 3)
                    if below:
                        self.assertEqual(run.call_args_list[0].args[0], ['limactl', 'stop', '-f', 'release-check'])
                    self.assertEqual(run.call_args_list[-1].args[0][:3], ['limactl', 'delete', '-f'])


if __name__ == '__main__':
    unittest.main()
