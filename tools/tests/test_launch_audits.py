"""Lightweight acceptance-harness tests. These are not VM or soak receipts."""
import datetime as dt
import hashlib
import importlib.util
import json
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
