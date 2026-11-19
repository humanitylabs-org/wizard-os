"""Optional wizard.md `permissions` (browser permissions an app frame may ask the owner for)."""
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


class Permissions(unittest.TestCase):
    def rules(self, value: object = 'missing'):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            d = {'wizard': 0.2, 'id': 'maps-test', 'type': 'view', 'view': {'path': '/', 'port': 8080}}
            if value != 'missing':
                d['permissions'] = value
            (p / 'wizard.md').write_text('---\n' + yaml.safe_dump(d) + '---\n')
            return {name: ok for name, ok, _ in checker.check(p) if 'permission' in name}

    def test_absent_adds_no_rule(self):
        self.assertEqual(self.rules(), {})

    def test_geolocation_and_empty_pass(self):
        for v in (['geolocation'], []):
            with self.subTest(v=v):
                self.assertEqual(self.rules(v), {'permissions are known (geolocation)': True})

    def test_other_values_fail(self):
        for v in (['camera'], ['geolocation', 'microphone'], ['Geolocation'], 'geolocation',
                  ['geolocation', 'geolocation'], None, {}, [1]):
            with self.subTest(v=v):
                self.assertFalse(self.rules(v)['permissions are known (geolocation)'])


if __name__ == '__main__':
    unittest.main()
