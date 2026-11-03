"""Shared repository maps describe components, not personal ownership."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RepoTablesTest(unittest.TestCase):
    def test_readme_repo_map_has_no_owner_column(self):
        text = (ROOT / 'README.md').read_text()
        self.assertIn('## Repos\n', text)
        self.assertNotIn('## Repos and owners', text)
        self.assertRegex(text, r'(?m)^\| Repo \| What \|$')

    def test_repo_and_contract_tables_do_not_assign_owners(self):
        for file in [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('**/*.md'))]:
            for line in file.read_text().splitlines():
                if not line.startswith('|'):
                    continue
                cells = [c.strip().lower() for c in line.strip('|').split('|')]
                # Task assignees and rollout responsibilities are not repository ownership.
                if any(re.fullmatch(r'repos?(?:itory|itories)?|contract', c) for c in cells):
                    with self.subTest(file=file.relative_to(ROOT), header=line):
                        self.assertNotIn('owner', cells)
                        self.assertNotIn('owners', cells)


if __name__ == '__main__':
    unittest.main()
