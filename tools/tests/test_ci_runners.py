"""Per-PR checks run on GitHub-hosted runners, not on one person's machine.

The Tests and Agent review workflows used to require the self-hosted Mac runner, so every
PR check sat queued whenever that Mac was offline. Release acceptance still needs the Mac
(it drives the local heavy VM worker) and is manual-dispatch only, so it stays self-hosted.
"""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / '.github/workflows'


def load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


class HostedRunnerTests(unittest.TestCase):
    def test_tests_workflow_runs_hosted(self):
        job = load('tests.yml')['jobs']['contracts']
        self.assertEqual(job['runs-on'], 'ubuntu-24.04')

    def test_agent_review_runs_hosted(self):
        job = load('pr-agent-review.yml')['jobs']['review']
        self.assertEqual(job['with']['runs-on'], '"ubuntu-24.04"')

    def test_per_pr_workflows_pin_actions_and_keep_least_privilege(self):
        for name in ('tests.yml', 'pr-agent-review.yml'):
            text = (WORKFLOWS / name).read_text()
            self.assertNotIn('self-hosted', text, name)
            for line in text.splitlines():
                line = line.strip().lstrip('- ')
                if line.startswith('uses: actions/'):
                    ref = line.split('@', 1)[1].split()[0]
                    self.assertRegex(ref, r'^[0-9a-f]{40}$', f'{name}: {line}')
        self.assertEqual(load('tests.yml')['permissions'], {'contents': 'read'})
        self.assertEqual(load('pr-agent-review.yml')['permissions'],
                         {'contents': 'read', 'pull-requests': 'write'})


if __name__ == '__main__':
    unittest.main()
