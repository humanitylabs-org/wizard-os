"""Lightweight acceptance-harness tests. These are not VM or soak receipts."""
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from email.message import Message
import urllib.error
import zipfile
import io

ROOT = Path(__file__).resolve().parents[1] / 'acceptance' / 'launch'


def module(name):
    spec = importlib.util.spec_from_file_location('launch_' + name, ROOT / (name + '.py'))
    assert spec is not None and spec.loader is not None
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


runner, journey, publish = module('run'), module('journey'), module('publish')


class HarnessTests(unittest.TestCase):
    def rows(self):
        start = dt.datetime(2026, 1, 1, 9, 15, tzinfo=dt.timezone.utc)
        return [{'at': (start + dt.timedelta(days=d)).isoformat(), 'release': '0.3.33',
                 'passed': True, 'interventions': 0, 'overlays': []} for d in range(4)]

    def test_upgraded_case_checks_every_installed_default_version_not_prepared_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            home, rt = Path(td) / 'home', Path(td) / 'runtipi'
            home.mkdir()
            pins = {'default_apps': {app: {'app': app, 'index_version': '0.2.6', 'commit': 'b' * 40}
                                     for app in ('wizard-claude', 'files')}}
            (home / 'release-pins.json').write_text(json.dumps(pins))
            for app in ('wizard-claude', 'files'):
                for base in (rt / 'apps' / 'wizardapps', rt / 'repos' / 'wizardapps' / 'apps'):
                    d = base / app
                    d.mkdir(parents=True)
                    (d / 'wizard.md').write_text('---\nversion: 0.2.6\n---\n')
                    (d / '.wizard-commit').write_text('b' * 40)
            self.assertEqual(journey.assert_installed_default_pins(home, rt), ['wizard-claude', 'files'])
            live = rt / 'apps' / 'wizardapps' / 'wizard-claude'
            (live / 'wizard.md').write_text('---\nversion: 0.1.2\n---\n')
            with self.assertRaisesRegex(AssertionError, 'wizard-claude version 0.1.2'):
                journey.assert_installed_default_pins(home, rt)
            (live / 'wizard.md').write_text('---\nversion: 0.2.6\n---\n')
            (live / '.wizard-commit').write_text('a' * 40)
            with self.assertRaisesRegex(AssertionError, 'wizard-claude source'):
                journey.assert_installed_default_pins(home, rt)
            import shutil
            shutil.rmtree(live)
            with self.assertRaisesRegex(AssertionError, 'wizard-claude vanished'):
                journey.assert_installed_default_pins(home, rt, ['wizard-claude'])
        source = (ROOT / 'journey.py').read_text()
        self.assertLess(source.index('installed_defaults = assert_installed_default_pins'), source.index('report = json.loads'))

    def test_clean_candidate_is_independent_of_previous_release_upgrade(self):
        events = []
        ops = {name: Mock(side_effect=lambda *a, n=name: events.append((n, *a)))
               for name in ('create', 'install', 'journey', 'delete')}
        args = SimpleNamespace(release='0.3.33', previous_release='0.3.32')
        evidence, result = Path('evidence'), {}
        runner.disposable_cases(args, evidence, 'fixture', **ops, result=result)
        self.assertEqual(events, [
            ('create', 'fixture'),
            ('install', 'fixture', evidence / 'clean-install', '0.3.33'),
            ('journey', 'fixture', 'clean', evidence / 'clean-state.json', '0.3.33'),
            ('delete', 'fixture'), ('create', 'fixture'),
            ('install', 'fixture', evidence / 'upgrade-previous-install', '0.3.32'),
            ('journey', 'fixture', 'upgrade-baseline', evidence / 'upgrade-state.json', '0.3.32'),
            ('install', 'fixture', evidence / 'clean-upgrade', '0.3.33'),
            ('journey', 'fixture', 'upgraded', evidence / 'upgrade-state.json', '0.3.33')])
        self.assertEqual(result['step'], 'upgraded-candidate-journey')

    def test_candidate_setup_failure_never_falls_back_to_previous_baseline(self):
        create, install, delete = Mock(), Mock(), Mock()
        failed = Mock(side_effect=RuntimeError('candidate Setup 404'))
        result = {}
        with self.assertRaises(RuntimeError):
            runner.disposable_cases(SimpleNamespace(release='0.3.33', previous_release='0.3.32'),
                                    Path('evidence'), 'fixture', create, install, failed, delete, result)
        install.assert_called_once()
        failed.assert_called_once()
        delete.assert_not_called()  # caller's finally owns failure cleanup
        self.assertEqual(result['step'], 'clean-candidate-journey')

    def test_upgrade_baseline_cannot_claim_setup_or_contact_success(self):
        registry = {'apps': [{'provides': ['shell'], 'view': {'local': 'http://127.0.0.1:8796/wizard-os-home/'}}]}
        with patch.object(journey, 'request', return_value=b'<title>Wizard</title>') as request, \
                patch.object(journey, 'run', side_effect=AssertionError('must not claim baseline contact')):
            value = journey.first_contact(registry, Path('wizard'), 'upgrade-baseline')
        self.assertIsNone(value['contact'])
        self.assertIsNone(value['setup_route'])
        self.assertEqual(value['first_contact'], 'not-evaluated-upgrade-baseline')
        request.assert_called_once()

    def test_every_candidate_journey_requires_valid_setup(self):
        registry = {'apps': [{'provides': ['shell'], 'view': {'url': 'http://127.0.0.1:8796/wizard-os-home/'}}]}
        contact = json.dumps({'ok': True, 'command': 'ssh -L 127.0.0.1:18795:127.0.0.1:8796'})
        for case in ('clean', 'upgraded', 'retained'):
            for setup in (urllib.error.HTTPError('fixture', 404, 'missing', Message(), io.BytesIO()), {}, [], {'first_run': 'true'}):
                with self.subTest(case=case, setup=setup), \
                        patch.object(journey, 'request', side_effect=[b'Wizard', setup]), \
                        patch.object(journey, 'run', return_value=contact):
                    with self.assertRaises((AssertionError, urllib.error.HTTPError)):
                        journey.first_contact(registry, Path('wizard'), case)
                if isinstance(setup, urllib.error.HTTPError):
                    setup.close()
            with patch.object(journey, 'request', side_effect=[b'Wizard', {'first_run': False}]), \
                    patch.object(journey, 'run', return_value=contact):
                self.assertEqual(journey.first_contact(registry, Path('wizard'), case)['first_contact'], 'passed')

    def test_soak_needs_four_successes_and_actual_elapsed_72h(self):
        rows = self.rows()
        self.assertTrue(runner.gate(rows))
        self.assertFalse(runner.gate(rows[:3]))
        rows[-1]['at'] = rows[-1]['at'].replace('09:15', '09:14')
        self.assertFalse(runner.gate(rows))

    def test_failure_gap_candidate_overlay_or_intervention_resets(self):
        for key, value in [('passed', False), ('release', '0.3.34'), ('overlays', ['source']), ('interventions', 1)]:
            rows = self.rows()
            rows[2][key] = value
            self.assertFalse(runner.gate(rows))
        self.assertFalse(runner.gate(self.rows()[::2]))

    def test_receipt_hash_chain(self):
        with tempfile.TemporaryDirectory() as d:
            first = runner.receipt(Path(d), self.rows()[0])
            second = runner.receipt(Path(d), self.rows()[1])
            self.assertIsNone(first['previous_sha256'])
            self.assertEqual(second['previous_sha256'], first['sha256'])
            digest = second.pop('sha256')
            self.assertEqual(digest, hashlib.sha256(json.dumps(second, sort_keys=True, separators=(',', ':')).encode()).hexdigest())

    def test_fixture_bytes_are_public_attributed_and_deterministic(self):
        self.assertEqual(journey.bundle(), journey.bundle())
        with zipfile.ZipFile(io.BytesIO(journey.bundle())) as z:
            manifest = json.loads(z.read('collection.json'))
            self.assertEqual(manifest['rights'], 'redistributable')
            self.assertIn('1863', manifest['attribution'])
            self.assertEqual(z.read('content/launch-public-reading.md').decode(), journey.BODY)
            self.assertEqual(len(z.namelist()), 3)

    def test_real_sqlite_restore_reverts_changed_progress(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'reading.sqlite'
            backup = Path(d) / 'backup.sqlite'
            with sqlite3.connect(db) as c:
                c.execute('CREATE TABLE reading(progress INTEGER)')
                c.execute('INSERT INTO reading VALUES (7)')
            subprocess.run([sys.executable, str(ROOT / 'sqlite_copy.py'), str(db), str(backup)], check=True)
            with sqlite3.connect(db) as c:
                c.execute('UPDATE reading SET progress=8')
            subprocess.run([sys.executable, str(ROOT / 'sqlite_copy.py'), str(backup), str(db)], check=True)
            with sqlite3.connect(db) as c:
                self.assertEqual(c.execute('SELECT progress FROM reading').fetchone()[0], 7)

    def test_release_vm_reserves_full_backup_capacity(self):
        with patch.dict(sys.modules, {'run': module('run')}):
            gate = module('release_gate')
        self.assertEqual(gate.GUEST_DISK_GIB, 40)
        # macOS TMPDIR is long enough to trip Lima's UNIX socket limit. Use a
        # short, synthetic root: this is a check-only test and creates no VM.
        with tempfile.TemporaryDirectory() as td:
            work = Path('/capacity-test')
            cli = Path(td) / 'cli'; cli.write_text('fixture')
            argv = ['release_gate.py', '--root', str(work / 'check'), '--release', '0.3.48',
                    '--previous-release', '0.3.39', '--cli', str(cli), '--wam-commit', 'a' * 40, '--check-only']
            with patch.object(gate.sys, 'argv', argv), patch.dict(os.environ, WIZARD_WORK_ROOT=str(work)), \
                    patch.object(Path, 'is_mount', return_value=True), patch.object(gate.sys, 'stdout', io.StringIO()):
                with patch.object(gate.shutil, 'disk_usage', return_value=SimpleNamespace(free=290 * gate.GIB)):
                    with self.assertRaises(AssertionError):
                        gate.main()
                with patch.object(gate.shutil, 'disk_usage', return_value=SimpleNamespace(free=291 * gate.GIB)):
                    self.assertEqual(gate.main(), 0)
                self.assertFalse((work / 'check').exists())

    def test_install_failure_evidence_precedes_each_existing_baseline_retry(self):
        events = []
        error = RuntimeError('original install failure')
        def failed(*args, **kwargs):
            events.append('install')
            raise error
        def diagnostic(*args, **kwargs):
            events.append('diagnostic')
            self.assertIs(kwargs['stdout'], journey.sys.stderr)
            self.assertIs(kwargs['stderr'], journey.sys.stderr)
            self.assertLessEqual(kwargs['timeout'], 130)
        with patch.object(journey, 'run', side_effect=failed), \
                patch.object(journey.subprocess, 'run', side_effect=diagnostic), \
                patch.object(journey.sys, 'stderr', io.StringIO()):
            with self.assertRaises(RuntimeError) as caught:
                journey.install_wisdom('wam', 'upgrade-baseline')
        self.assertIs(caught.exception, error)
        self.assertEqual(events, ['install', 'diagnostic', 'install', 'diagnostic'])

    def test_candidate_failure_or_timeout_not_retried_and_diagnostic_cannot_mask_it(self):
        for case, error in [('clean', RuntimeError('install failed')),
                            ('upgrade-baseline', subprocess.TimeoutExpired('wam', 900))]:
            with self.subTest(case=case), patch.object(journey, 'run', side_effect=error) as run, \
                    patch.object(journey.subprocess, 'run', side_effect=OSError('diagnostic unavailable')), \
                    patch.object(journey.sys, 'stderr', io.StringIO()):
                with self.assertRaises(type(error)) as caught:
                    journey.install_wisdom('wam', case)
                self.assertIs(caught.exception, error)
                run.assert_called_once()

    def test_successful_wisdom_install_has_no_diagnostic_or_repair(self):
        with patch.object(journey, 'run', return_value='ok') as run, \
                patch.object(journey.subprocess, 'run') as diagnostic:
            journey.install_wisdom('wam', 'clean')
        run.assert_called_once_with('wam', 'install', 'wisdom', timeout=900)
        diagnostic.assert_not_called()

    def test_diagnostic_fixture_guard_and_read_only_commands(self):
        diagnostic = module('diagnostics')
        with patch.dict(os.environ, {'WIZARD_LAUNCH_FIXTURE': ''}), \
                patch.object(diagnostic.subprocess, 'run') as probe:
            with self.assertRaises(AssertionError):
                diagnostic.collect()
            probe.assert_not_called()
        with patch.dict(os.environ, WIZARD_LAUNCH_FIXTURE='launch-audits-8-9'), \
                patch.object(diagnostic.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=0, stdout='a' * 12 + '\n', stderr='')) as probe, \
                patch.object(diagnostic.sys, 'stdout', io.StringIO()):
            diagnostic.collect()
        commands = [call.args[0] for call in probe.call_args_list]
        self.assertEqual(len(commands), 5)
        self.assertTrue(all(c[:2] == ['sudo', '-n'] for c in commands))
        self.assertTrue(any(c[2:4] == ['docker', 'logs'] and c[-1] == 'runtipi' for c in commands))
        self.assertFalse(any('inspect' in c or 'pull' in c or 'up' in c for c in commands))
        self.assertTrue(all(call.kwargs['timeout'] == 15 for call in probe.call_args_list))
        self.assertTrue(commands[-1][-1].endswith('docker-compose.generated.yml'))

    def test_release_failure_capture_does_not_mask_failure_or_prevent_cleanup(self):
        with patch.dict(sys.modules, {'run': module('run')}):
            gate = module('release_gate')
        with tempfile.TemporaryDirectory() as td, \
                patch.object(gate.subprocess, 'run', side_effect=subprocess.TimeoutExpired('lima', 150)) as probe:
            gate.capture_failure_diagnostics('fixture', Path(td) / 'private-run.log')
        self.assertEqual(probe.call_args.args[0][-1], str(ROOT / 'diagnostics.py'))
        self.assertEqual(probe.call_args.kwargs['timeout'], 150)
        source = (ROOT / 'release_gate.py').read_text()
        self.assertLess(source.index('capture_failure_diagnostics(vm, log)', source.index('finally:')),
                        source.index("cleanup = subprocess.run"))

    def test_backup_failure_tails_go_only_to_private_stderr(self):
        backup = module('backup_journey')
        stdout, stderr = io.StringIO(), io.StringIO()
        failed = SimpleNamespace(returncode=1, stdout='x' * 5000 + 'diagnostic-json', stderr='y' * 5000 + 'diagnostic-stderr')
        with patch.object(backup.subprocess, 'run', return_value=failed), \
                patch.object(backup.sys, 'stdout', stdout), patch.object(backup.sys, 'stderr', stderr):
            with self.assertRaisesRegex(RuntimeError, '^real backup CLI failed: export$'):
                backup.run_backup('wam', 'export', '--key-file', Path('private.key'))
        self.assertEqual(stdout.getvalue(), '')
        self.assertIn('diagnostic-json', stderr.getvalue())
        self.assertIn('diagnostic-stderr', stderr.getvalue())
        self.assertNotIn('x' * 4001, stderr.getvalue())
        self.assertNotIn('y' * 4001, stderr.getvalue())

    def test_backup_key_must_be_written_not_printed_and_success_is_quiet(self):
        backup = module('backup_journey')
        with patch.object(backup.subprocess, 'run') as run:
            with self.assertRaises(AssertionError):
                backup.run_backup('wam', 'key', 'new')
            run.assert_not_called()
        with patch.object(backup.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout='{"ok": true}', stderr='private progress')), \
                patch.object(backup.sys, 'stderr', io.StringIO()) as stderr:
            self.assertEqual(backup.run_backup('wam', 'key', 'new', '--out', Path('private.key')), {'ok': True})
            self.assertEqual(stderr.getvalue(), '')

    def test_public_comment_cannot_leak_canaries(self):
        canary = 'private-token owner@example.invalid /private/home private.tail111.ts.net'
        value = {'release': canary, 'step': canary, 'sha256': 'a' * 64, 'private_log': canary,
                 'hostname': canary, 'passed': False, 'interventions': canary, 'cases': [canary]}
        body = publish.format_receipt(value)
        self.assertNotIn(canary, body)
        self.assertIn('**FAIL**', body)
        self.assertIn('unavailable', body)
        value['sha256'] = canary
        with self.assertRaises(ValueError):
            publish.format_receipt(value)


if __name__ == '__main__':
    unittest.main()
