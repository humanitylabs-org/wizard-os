"""Strict opt-in home_screen manifest contract; run directly or with unittest."""
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

GOOD = {'offline': True, 'position_keys': ['reader:*:pos:*', 'abc'], 'route_state': 'reader'}


class HomeScreen(unittest.TestCase):
    def rules(self, value: object = 'missing', view=True):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            d = {'wizard': 0.2, 'id': 'home-screen-test', 'type': 'service'}
            if value != 'missing':
                d['home_screen'] = value
            if view:
                d['view'] = {'path': '/', 'port': 8080}
            (p / 'wizard.md').write_text('---\n' + yaml.safe_dump(d) + '---\n')
            return {name: ok for name, ok, _ in checker.check(p) if 'home' in name}

    def test_absent_adds_nothing(self):
        self.assertEqual(self.rules(), {})
        self.assertEqual(checker.home_screen({}), {})

    def test_valid(self):
        self.assertEqual(checker.home_screen({'home_screen': GOOD}), GOOD)
        self.assertTrue(all(self.rules(GOOD).values()))

    def test_only_declared_values_survive(self):
        self.assertEqual(checker.home_screen({'home_screen': {'offline': False, 'position_keys': []}}), {})
        self.assertEqual(checker.home_screen({'home_screen': {'offline': True}}), {'offline': True})

    def test_invalid(self):
        bad = ['offline', [], {'offline': 'true'}, {'offline': 1}, {'unknown': True},
               {'position_keys': 'a'}, {'position_keys': ['*']}, {'position_keys': ['ab*']},
               {'position_keys': ['x' * 121]}, {'position_keys': ['abc'] * 9}, {'position_keys': [5]},
               {'position_keys': ['abc\n']}, {'route_state': '1abc'}, {'route_state': 'a b'},
               {'route_state': 'x' * 41}, {'route_state': 3}]
        for v in bad:
            with self.subTest(v=v):
                self.assertFalse(self.rules(v)['home_screen valid'])

    def test_declaration_needs_a_view(self):
        self.assertFalse(self.rules(GOOD, view=False)['home screen has a declared view'])
        self.assertNotIn('home screen has a declared view', self.rules({'offline': False}, view=False))


if __name__ == '__main__':
    unittest.main()
