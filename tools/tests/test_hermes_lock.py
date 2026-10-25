import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hermes_lock as lock
import check_release


class HermesLockTests(unittest.TestCase):
    def setUp(self):
        self.doc = lock.load()
        self.now = datetime(2026, 10, 25, tzinfo=timezone.utc)

    def approved(self):
        doc = copy.deepcopy(self.doc)
        doc['state'] = 'approved'
        doc['promotion'] = {'id': 'fixture-1', 'published_at': '2026-10-01T00:00:00Z',
                            'approved_at': '2026-10-08T00:00:00Z'}
        for key in ('recommendation', 'approval', 'acceptance', 'canary', 'bug_review', 'rollback'):
            doc['promotion'][key] = 'https://example.invalid/' + key
        return doc

    def test_frozen_baseline_refuses_even_an_explicit_id(self):
        with patch.dict(os.environ, {'WIZARD_HERMES_PROMOTION': 'anything'}):
            with self.assertRaisesRegex(ValueError, 'paused'):
                lock.authorize(self.doc)

    def test_seven_complete_days_and_evidence_are_required(self):
        doc = self.approved()
        lock.validate(doc, self.now)
        doc['promotion']['approved_at'] = '2026-10-07T23:59:59Z'
        with self.assertRaisesRegex(ValueError, 'seven full days'):
            lock.validate(doc, self.now)
        doc = self.approved()
        doc['promotion']['approved_at'] = '2026-11-01T00:00:00Z'
        with self.assertRaises(ValueError):
            lock.validate(doc, self.now)
        for key in ('recommendation', 'approval', 'acceptance', 'canary', 'bug_review', 'rollback', 'published_at'):
            doc = self.approved(); del doc['promotion'][key]
            with self.assertRaises(ValueError):
                lock.validate(doc, self.now)

    def test_approval_is_not_execution_authorization(self):
        doc = self.approved()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                lock.authorize(doc)
        with patch.dict(os.environ, {'WIZARD_HERMES_PROMOTION': 'fixture-1'}):
            self.assertEqual(lock.authorize(doc), 'fixture-1')

    def test_pin_and_recipe_drift_are_rejected(self):
        for key in ('tag', 'commit', 'image'):
            pin = copy.deepcopy(self.doc['hermes']); pin[key] = 'latest'
            with self.assertRaises(ValueError):
                lock.check_pin(pin, self.doc)
        rel = {'hermes': self.doc['hermes'], 'default_apps': {'agent': copy.deepcopy(self.doc['agent_recipe'])}}
        lock.check_release(rel, self.doc)
        rel['default_apps']['agent']['commit'] = 'a' * 40
        with self.assertRaises(ValueError):
            lock.check_release(rel, self.doc)

    def test_new_release_cannot_float_hermes(self):
        root = Path(__file__).resolve().parents[2]
        rel = json.loads((root / 'releases/0.3.39.json').read_text())
        rel['version'] = '0.3.40'
        self.assertEqual(check_release.hermes_shape(rel), [])
        rel['hermes']['commit'] = 'a' * 40
        self.assertTrue(any('shared exact lock' in e for e in check_release.hermes_shape(rel)))

    def test_standalone_cli_refuses_before_inspecting_runtime(self):
        import importlib.machinery
        import importlib.util
        from types import SimpleNamespace
        loader = importlib.machinery.SourceFileLoader('wizard_lock_test', str(Path(__file__).resolve().parents[1] / 'wizard'))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        cli = importlib.util.module_from_spec(spec); loader.exec_module(cli)
        with patch.object(cli, '_read_source', return_value=json.dumps(self.doc)), patch.object(cli, 'hermes_home_path', return_value=Path('/fixture-not-a-runtime')) as home:
            with self.assertRaises(cli.Fail) as exc:
                cli.cmd_hermes_update(SimpleNamespace(stable=True, dry_run=False, timeout=1, hermes_home=None))
        home.assert_not_called()
        self.assertEqual(exc.exception.code, 'update_refused')
        self.assertIn('paused', str(exc.exception))

    def test_current_stable_matches_central_lock(self):
        root = Path(__file__).resolve().parents[2]
        version = (root / 'releases/stable').read_text().strip()
        lock.check_release(json.loads((root / 'releases' / (version + '.json')).read_text()), self.doc)


if __name__ == '__main__':
    unittest.main()
