"""side_branches.py: integration/* and live* side branches and their recorded decisions (#491).

    python3 -m unittest tools/tests/test_side_branches.py -v
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import side_branches as sb  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": os.devnull}


def run(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=ENV)


def commit(cwd, name, text):
    (Path(cwd) / name).write_text(text)
    run(cwd, "add", name)
    run(cwd, "commit", "-q", "-m", f"edit {name}")


def ledger(tmp, rows):
    path = Path(tmp) / "ledger.md"
    body = "| Branch | Decision | Notes |\n|---|---|---|\n" + "".join(f"| `{b}` | {d} | n |\n" for b, d in rows)
    path.write_text(body)
    return path


class SideBranchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        origin, self.clone = Path(self.tmp) / "origin", Path(self.tmp) / "clone"
        origin.mkdir()
        run(origin, "init", "-q", "-b", "main")
        commit(origin, "a.txt", "a\n")
        # integration/landed: its only commit was cherry-picked onto main -> 0 unique (patch-id compare).
        run(origin, "switch", "-q", "-c", "integration/landed")
        commit(origin, "b.txt", "b\n")
        run(origin, "switch", "-q", "main")
        commit(origin, "m.txt", "main moved on\n")
        run(origin, "cherry-pick", "integration/landed")
        # integration/open and live-old carry work not on main; owner-snapshot/x and fix/y are out of scope.
        for name, files in [("integration/open", ["c.txt", "d.txt"]), ("live-old", ["e.txt"]),
                            ("owner-snapshot/x", ["f.txt"]), ("fix/y", ["g.txt"])]:
            run(origin, "switch", "-q", "-c", name, "main")
            for f in files:
                commit(origin, f, f)
        run(origin, "switch", "-q", "main")
        run(self.tmp, "clone", "-q", str(origin), str(self.clone))

    def test_lists_only_side_branches_with_patch_id_unique_counts(self):
        got = {b["branch"]: (b["unique_commits"], b["files"]) for b in sb.side_branches(self.clone)}
        self.assertEqual(got, {"integration/landed": (0, 1), "integration/open": (2, 2), "live-old": (1, 1)})

    def test_problems_cover_missing_undecided_abandoned_and_gone(self):
        branches = sb.side_branches(self.clone)
        rows = sb.read_ledger(ledger(self.tmp, [
            ("integration/landed", "abandon, signed off by James"),
            ("integration/open", "undecided"),
            ("integration/gone", "land via #1"),
            ("integration/old", "deleted"),
        ]))
        found = "\n".join(sb.problems(branches, rows))
        self.assertIn("live-old: on origin but not in the ledger", found)
        self.assertIn("integration/open: undecided (2 commits", found)
        self.assertIn("integration/landed: abandoned with sign-off, still on origin", found)
        self.assertIn("integration/gone: gone from origin", found)
        self.assertNotIn("integration/old", found)
        self.assertNotIn("owner-snapshot", found)

    def test_exit_zero_when_every_branch_is_decided(self):
        path = ledger(self.tmp, [("integration/landed", "keep: proof of the 0.2.2 run"),
                                 ("integration/open", "land via #9"), ("live-old", "keep: reason")])
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(sb.main(["--repo", str(self.clone), "--ledger", str(path), "--json"]), 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["problems"], [])
        self.assertEqual({b["decision"] for b in data["branches"]}, {"keep", "land"})

    def test_exit_one_with_problems_and_two_without_repo_or_ledger(self):
        path = ledger(self.tmp, [("integration/open", "undecided")])
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(sb.main(["--repo", str(self.clone), "--ledger", str(path)]), 1)
        self.assertIn("problem  live-old", out.getvalue())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(sb.main(["--repo", self.tmp, "--ledger", str(path)]), 2)
            self.assertEqual(sb.main(["--repo", str(self.clone), "--ledger", str(Path(self.tmp) / "nope.md")]), 2)

    def test_unknown_decision_word_is_rejected(self):
        with self.assertRaises(ValueError):
            sb.read_ledger(ledger(self.tmp, [("integration/open", "maybe later")]))


class LedgerFileTest(unittest.TestCase):
    def test_repo_ledger_parses_and_records_the_seven_branches(self):
        rows = sb.read_ledger(ROOT / "docs" / "SIDE_BRANCHES.md")
        self.assertEqual(len(rows), 7)
        self.assertTrue(all(sb.SIDE.match(b) for b in rows))
        self.assertIn("integration/l4-fresh-install-0317", rows)


if __name__ == "__main__":
    unittest.main()
