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
