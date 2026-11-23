"""Rule 12: one exec argument or environment entry over 120,000 bytes fails (Linux MAX_ARG_STRLEN is 128 KiB).

Same rule as wizard-app-manager wam/wizardmd.py (wizard-app-manager#858). Run directly or with unittest.
"""
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

MSG = "Linux refuses one argument over 128 KiB. Pack it (zlib+base64 in mcp/inline.py) or ship a file."


def compose(**service):
    return yaml.safe_dump({'services': {'front': {'image': 'python:3.12-alpine', **service}}}, width=10**7)


class ExecArgLimit(unittest.TestCase):
    def test_photos_040_size_fails(self):
        self.assertEqual(checker.compose_risks(compose(command=['python', '-c', 'x' * 154_132])),
                         ['front command argument is 154 KB; ' + MSG])

    def test_every_exec_string_counts(self):
        for kw in ({'command': 'python -c ' + 'y' * 125_000}, {'entrypoint': ['sh', '-c', 'z' * 125_000]},
                   {'environment': {'BIG': 'v' * 125_000}}, {'environment': ['BIG=' + 'v' * 125_000]}):
            with self.subTest(kw=list(kw)):
                risks = checker.compose_risks(compose(**kw))
                self.assertEqual(len(risks), 1)
                self.assertIn(MSG, risks[0])

    def test_under_the_limit_passes(self):
        for n in (110_000, 120_000):
            self.assertEqual(checker.compose_risks(compose(command=['python', '-c', 'x' * n])), [])
        self.assertEqual(checker.compose_risks(compose(command="python -c 'unbalanced", environment=['A'])), [])

    def test_check_rule_fails_the_app(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            (p / 'runtipi').mkdir()
            (p / 'runtipi/docker-compose.yml').write_text(compose(command=['python', '-c', 'x' * 130_000]))
            d = {'wizard': 0.2, 'id': 'big-test', 'type': 'service',
                 'runtime': {'compose': 'runtipi/docker-compose.yml'}}
            (p / 'wizard.md').write_text('---\n' + yaml.safe_dump(d) + '---\n')
            rules = {name: (ok, detail) for name, ok, detail in checker.check(p)}
            ok, detail = rules['container asks for no host-level access']
            self.assertFalse(ok)
            self.assertIn('front command argument is 130 KB', detail)


if __name__ == '__main__':
    unittest.main()
