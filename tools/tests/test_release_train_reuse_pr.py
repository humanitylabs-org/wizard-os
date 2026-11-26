"""wizard-os#959: the release train must not wedge on its own leftover PR or on a GitHub 5xx while merging.

open_and_merge runs with a fake `gh`; nothing touches GitHub and no release is made.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_train as rt

HEAD = "b" * 40
OLD = "c" * 40
URL = "https://github.com/humanitylabs-org/wizard-os/pull/939"
GREEN = [{"name": "unit", "status": "COMPLETED", "conclusion": "SUCCESS"}]


class FakeGitHub:
    def __init__(self, open_prs=(), merge_errors=(), merged_after_error=False, heads=()):
        self.open_prs = list(open_prs)
        self.merge_errors = list(merge_errors)
        self.merged_after_error = merged_after_error
        self.heads = list(heads)            # headRefOid per poll, then HEAD
        self.calls = []
        self.merged = False

    def sh(self, args, **kwargs):
        self.calls.append(args)
        if args[:3] == ["gh", "pr", "create"]:
            if self.open_prs:
                raise rt.Stop('`gh pr create` failed (1): a pull request for branch "release/0.3.437-train" '
                              'into branch "main" already exists:\n' + URL)
            return "https://github.com/humanitylabs-org/wizard-os/pull/960\n"
        if args[:3] == ["gh", "pr", "merge"]:
            if self.merge_errors:
                err = self.merge_errors.pop(0)
                if self.merged_after_error:
                    self.merged = True
                raise err
            self.merged = True
            return ""
        if args[0] == "git" and "rev-parse" in args:
            return HEAD + "\n"
        return ""

    def gh_json(self, args, **kwargs):
        self.calls.append(["gh", *args])
        if args[:2] == ["pr", "list"]:
            assert "--head" in args and "open" in args, args
            return [{"url": u, "number": int(u.rsplit("/", 1)[1])} for u in self.open_prs]
        if args[:2] == ["pr", "view"] and "statusCheckRollup,headRefOid" in args:
            return {"statusCheckRollup": GREEN, "headRefOid": self.heads.pop(0) if self.heads else HEAD}
        if args[:2] == ["pr", "view"]:
            return {"state": "MERGED" if self.merged else "OPEN", "headRefOid": HEAD}
        if args[:2] == ["api", "graphql"]:
            return {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": []}}}}}
        raise AssertionError(args)

    def run(self):
        with mock.patch.object(rt, "sh", side_effect=self.sh), \
                mock.patch.object(rt, "gh_json", side_effect=self.gh_json), \
                mock.patch.object(rt.time, "sleep"), \
                mock.patch.object(rt, "run_deadline", return_value=float("inf")):
            return rt.open_and_merge(rt.WOS, Path("/synthetic"), "release/0.3.437-train", "Maintenance: cut 0.3.437",
                                     "body", "tier: maintenance", need_checks=True)

    def merges(self):
        return [c for c in self.calls if c[:3] == ["gh", "pr", "merge"]]


def bad_gateway():
    return rt.Stop("`gh pr merge 939 -R humanitylabs-org/wizard-os` failed (1): HTTP 502: 502 Bad Gateway "
                   "(https://api.github.com/graphql)")


class ExistingPullRequest(unittest.TestCase):
    def test_a_pr_for_this_branch_already_exists_is_reused_and_merged(self):
        gh = FakeGitHub(open_prs=[URL])
        self.assertEqual(gh.run(), URL)
        self.assertFalse([c for c in gh.calls if c[:3] == ["gh", "pr", "create"]])
        edit = [c for c in gh.calls if c[:3] == ["gh", "pr", "edit"]]
        self.assertEqual(len(edit), 1)
        self.assertIn("Maintenance: cut 0.3.437", edit[0])
        merge = gh.merges()
        self.assertEqual(len(merge), 1)
        self.assertEqual(merge[0][3], "939")
        self.assertEqual(merge[0][-2:], ["--match-head-commit", HEAD])

    def test_no_open_pr_creates_one(self):
        gh = FakeGitHub()
        self.assertTrue(gh.run().endswith("/pull/960"))
        self.assertEqual(len([c for c in gh.calls if c[:3] == ["gh", "pr", "create"]]), 1)
        self.assertEqual(gh.merges()[0][3], "960")

    def test_waits_until_github_shows_the_new_head_before_trusting_checks(self):
        gh = FakeGitHub(open_prs=[URL], heads=[OLD, OLD])
        gh.run()
        polls = [c for c in gh.calls if c[:3] == ["gh", "pr", "view"] and "statusCheckRollup,headRefOid" in c]
        self.assertEqual(len(polls), 3)
        self.assertEqual(len(gh.merges()), 1)


class TransientMergeFailure(unittest.TestCase):
    def test_a_502_is_retried_and_then_merges(self):
        gh = FakeGitHub(merge_errors=[bad_gateway(), bad_gateway()])
        gh.run()
        self.assertEqual(len(gh.merges()), 3)
        self.assertTrue(gh.merged)

    def test_a_timeout_is_retried(self):
        gh = FakeGitHub(merge_errors=[subprocess.TimeoutExpired(["gh"], 900)])
        gh.run()
        self.assertEqual(len(gh.merges()), 2)

    def test_a_502_that_merged_anyway_counts_as_merged(self):
        gh = FakeGitHub(merge_errors=[bad_gateway()], merged_after_error=True)
        gh.run()
        self.assertEqual(len(gh.merges()), 1)

    def test_a_502_every_time_stops_after_a_few_tries(self):
        gh = FakeGitHub(merge_errors=[bad_gateway() for _ in range(10)])
        with self.assertRaises(rt.Stop):
            gh.run()
        self.assertEqual(len(gh.merges()), 4)

    def test_a_real_refusal_is_not_retried(self):
        gh = FakeGitHub(merge_errors=[rt.Stop("`gh pr merge` failed (1): Head branch was modified. "
                                              "Review and try the merge again.")])
        with self.assertRaises(rt.Stop):
            gh.run()
        self.assertEqual(len(gh.merges()), 1)


if __name__ == "__main__":
    unittest.main()
