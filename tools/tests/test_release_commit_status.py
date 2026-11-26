"""Exercise legacy commit statuses through the production release merge wait loop.

Network, Git mutations and sleep are stubbed. No release is made.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_train as rt


class CommitStatusAdmission(unittest.TestCase):
    def exercise(self, rows):
        head = 'a' * 40
        calls, polls = [], []

        def shell(args, **kwargs):
            calls.append(args)
            if args[:3] == ['gh', 'pr', 'create']:
                return 'https://github.com/example/repo/pull/7'
            if args[0] == 'git' and 'rev-parse' in args:
                return head
            return ''

        def github(args, **kwargs):
            if args[:2] == ['pr', 'view']:
                index = len(polls)
                if index >= len(rows):
                    raise AssertionError('did not settle within the supplied status sequence')
                polls.append(index)
                return {'statusCheckRollup': rows[index]}
            if args[:2] == ['pr', 'list']:
                return []
            if args[:2] == ['api', 'graphql']:
                return {'data': {'repository': {'pullRequest': {'reviewThreads': {'nodes': []}}}}}
            raise AssertionError(args)

        with mock.patch.object(rt, 'sh', side_effect=shell), \
                mock.patch.object(rt, 'gh_json', side_effect=github), \
                mock.patch.object(rt.time, 'sleep'), \
                mock.patch.object(rt, 'run_deadline', return_value=float('inf')):
            try:
                rt.open_and_merge(rt.WAM, Path('/synthetic'), 'synthetic', 'title', 'body',
                                  'tier: maintenance', need_checks=True)
            except rt.Stop:
                self.assertFalse(any(c[:3] == ['gh', 'pr', 'merge'] for c in calls))
                raise
        return calls, polls

    def test_pending_commit_status_waits_then_success_merges(self):
        calls, polls = self.exercise([
            [{'context': 'external', 'state': 'PENDING'}],
            [{'context': 'external', 'state': 'SUCCESS'}],
        ])
        self.assertEqual(len(polls), 2)
        merge = [c for c in calls if c[:3] == ['gh', 'pr', 'merge']]
        self.assertEqual(len(merge), 1)
        self.assertEqual(merge[0][-2:], ['--match-head-commit', 'a' * 40])

    def test_failed_commit_status_stops_without_merge(self):
        for state in ('ERROR', 'FAILURE'):
            with self.subTest(state=state), self.assertRaises(rt.Stop):
                self.exercise([[{'context': 'external', 'state': state}]])

    def test_mixed_check_run_and_commit_status_wait_for_both(self):
        calls, polls = self.exercise([
            [{'name': 'unit', 'status': 'COMPLETED', 'conclusion': 'SUCCESS'},
             {'context': 'external', 'state': 'PENDING'}],
            [{'name': 'unit', 'status': 'COMPLETED', 'conclusion': 'SUCCESS'},
             {'context': 'external', 'state': 'SUCCESS'}],
        ])
        self.assertEqual(len(polls), 2)
        self.assertTrue(any(c[:3] == ['gh', 'pr', 'merge'] for c in calls))

    def test_failed_check_run_remains_blocking(self):
        with self.assertRaises(rt.Stop):
            self.exercise([[{'name': 'unit', 'status': 'COMPLETED', 'conclusion': 'FAILURE'},
                            {'context': 'external', 'state': 'SUCCESS'}]])


if __name__ == '__main__':
    unittest.main()
