"""Optional wizard.md whats_new (wizard-ux#1191): one line on what changed in this version; run with unittest."""
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


class WhatsNew(unittest.TestCase):
    def rules(self, value: object = 'missing'):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            d = {'wizard': 0.2, 'id': 'whats-new-test', 'type': 'service'}
            if value != 'missing':
                d['whats_new'] = value
            (p / 'wizard.md').write_text('---\n' + yaml.safe_dump(d) + '---\n')
            return {name: ok for name, ok, _ in checker.check(p) if 'whats_new' in name}

    def test_absent_adds_nothing(self):
        self.assertEqual(self.rules(), {})

    def test_one_short_line_passes(self):
        self.assertEqual(self.rules('Replies stay in their thread.'), {'whats_new is one line of 1-140 chars': True})
        self.assertTrue(checker.whats_new_ok('x' * 140))

    def test_everything_else_fails(self):
        for bad in ['', '   ', 'x' * 141, 'two\nlines', 'tab\there', None, 3, ['a'], {'a': 1}]:
            with self.subTest(bad=bad):
                self.assertFalse(checker.whats_new_ok(bad))
                self.assertEqual(self.rules(bad), {'whats_new is one line of 1-140 chars': False})


if __name__ == '__main__':
    unittest.main()
