"""Connector apps must declare type external; run directly or with unittest."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('checker', ROOT / 'tools/check_wizard_md.py')
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
RULE = 'connector apps are type external'


class ConnectorType(unittest.TestCase):
    def rules(self, **d):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            (p / 'wizard.md').write_text('---\n' + yaml.safe_dump({'wizard': 0.2, 'summary': 'x', **d}) + '---\n')
            return {name: ok for name, ok, _ in checker.check(p) if name == RULE}

    def test_plain_app_has_no_rule(self):
        self.assertEqual(self.rules(id='movies', type='service', provides=['watch-queue']), {})

    def test_music_source_service_fails(self):
        self.assertFalse(self.rules(id='wizard-youtube-music', type='service', provides=['music-source'])[RULE])

    def test_connector_id_fails(self):
        self.assertFalse(self.rules(id='zoom-connector', type='service')[RULE])

    def test_connect_summary_fails(self):
        self.assertFalse(self.rules(id='acme', type='view', summary='Connect your Acme account.')[RULE])

    def test_external_passes(self):
        for d in ({'id': 'wizard-brightdata', 'provides': ['web-data']}, {'id': 'wizard-twitterapi', 'provides': ['x-search']},
                  {'id': 'wizard-claude', 'provides': ['ai-connection']}):
            with self.subTest(d=d):
                self.assertTrue(self.rules(type='external', **d)[RULE])


if __name__ == '__main__':
    unittest.main()
