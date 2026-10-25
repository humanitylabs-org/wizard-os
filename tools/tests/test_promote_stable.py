"""promote_stable.py: the latest/stable channel rules (DECISIONS #75).

    python3 -m unittest tools/tests/test_promote_stable.py -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOL = HERE.parent / "promote_stable.py"
sys.path.insert(0, str(HERE.parent))
import promote_stable as ps  # noqa: E402


def run(rel, *args):
    return subprocess.run([sys.executable, str(TOOL), "--releases", str(rel), *args], capture_output=True, text=True,
                          timeout=60)


class Repo(unittest.TestCase):
    def test_this_repo_follows_the_channel_rules(self):
        p = run(ROOT / "releases", "check")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class Flow(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d)
        for v in ("0.3.25", "0.3.26"):
            (self.d / f"{v}.json").write_text(json.dumps({"version": v}))
        (self.d / "stable").write_text("0.3.25\n")
        (self.d / "latest").write_text("0.3.25\n")
        (self.d / "promotions").mkdir()
        (self.d / "promotions" / "0.3.25.json").write_text(json.dumps({"version": "0.3.25", "grandfathered": "seed"}))

    def test_cut_moves_only_latest(self):
        self.assertEqual(run(self.d, "cut", "0.3.26").returncode, 0)
        self.assertEqual((self.d / "latest").read_text().strip(), "0.3.26")
        self.assertEqual((self.d / "stable").read_text().strip(), "0.3.25")
        self.assertEqual(run(self.d, "check").returncode, 0)
        self.assertEqual(run(self.d, "cut", "0.3.25").returncode, 1)          # never backwards

    def test_promote_refuses_a_short_soak_and_keeps_stable(self):
        run(self.d, "cut", "0.3.26")
        p = run(self.d, "promote", "0.3.26", "--from", "0.3.25", "--evidence", "log",
                "--latest-since", "2026-10-21T00:00:00Z", "--now", "2026-10-22T00:00:00Z")
        self.assertEqual(p.returncode, 1)
        self.assertIn("soaked 24.0h", p.stdout)
        self.assertEqual((self.d / "stable").read_text().strip(), "0.3.25")
        self.assertFalse((self.d / "promotions" / "0.3.26.json").exists())

    def test_promote_after_soak_and_test_moves_stable_with_a_record(self):
        run(self.d, "cut", "0.3.26")
        p = run(self.d, "promote", "0.3.26", "--from", "0.3.25", "--evidence", "docs/acceptance/update-0.3.26.md",
                "--latest-since", "2026-10-21T00:00:00Z", "--now", "2026-10-24T01:00:00Z")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual((self.d / "stable").read_text().strip(), "0.3.26")
        rec = json.loads((self.d / "promotions" / "0.3.26.json").read_text())
        self.assertEqual(rec["upgrade_test"], {"from": "0.3.25", "to": "0.3.26", "passed": True,
                                               "evidence": "docs/acceptance/update-0.3.26.md"})
        self.assertEqual(run(self.d, "check").returncode, 0)

    def test_promote_reads_the_soak_start_from_git_history(self):
        g = lambda *a: subprocess.run(["git", *a], cwd=self.d, check=True, capture_output=True)
        g("init", "-q")
        g("add", ".")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed", "--date", "2026-10-01T00:00:00Z")
        run(self.d, "cut", "0.3.26")
        env = {"GIT_COMMITTER_DATE": "2026-10-21T00:00:00Z", "GIT_AUTHOR_DATE": "2026-10-21T00:00:00Z"}
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "cut"], cwd=self.d,
                       check=True, env={**__import__("os").environ, **env})
        self.assertEqual(ps.latest_since("0.3.26", self.d), "2026-10-21T00:00:00Z")
        p = run(self.d, "promote", "0.3.26", "--from", "0.3.25", "--evidence", "x", "--now", "2026-10-25T00:00:00Z")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_fast_track_promotes_a_verified_fix_the_same_day(self):
        """DECISIONS #82: a fix-only release with a passed upgrade test skips the soak; the record says why."""
        run(self.d, "cut", "0.3.26")
        p = run(self.d, "promote", "0.3.26", "--from", "0.3.25", "--evidence", "https://example.test/run/1",
                "--fast-track", "--classification", "fix", "--reason", "Store 404s on fresh boxes",
                "--notes", "rides along: channel picker (low risk)",
                "--latest-since", "2026-10-21T12:00:00Z", "--now", "2026-10-22T03:00:00Z")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("fast-tracked fix", p.stdout)
        self.assertEqual((self.d / "stable").read_text().strip(), "0.3.26")
        rec = json.loads((self.d / "promotions" / "0.3.26.json").read_text())
        self.assertEqual(rec["fast_track"], {"classification": "fix", "reason": "Store 404s on fresh boxes",
                                             "notes": "rides along: channel picker (low risk)"})
        self.assertEqual(run(self.d, "check").returncode, 0)

    def test_fast_track_accepts_a_tested_feature_release(self):
        """DECISIONS #93: during launch a feature release with a passed upgrade test goes to stable the same day."""
        run(self.d, "cut", "0.3.26")
        p = run(self.d, "promote", "0.3.26", "--from", "0.3.25", "--evidence", "log",
                "--latest-since", "2026-10-21T12:00:00Z", "--now", "2026-10-22T03:00:00Z", "--fast-track",
                "--classification", "feature", "--reason", "current main shell for launch")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual((self.d / "stable").read_text().strip(), "0.3.26")
        self.assertEqual(run(self.d, "check").returncode, 0)

    def test_fast_track_refuses_unknown_classes_missing_reasons_and_missing_tests(self):
        run(self.d, "cut", "0.3.26")
        base = ["promote", "0.3.26", "--from", "0.3.25", "--evidence", "log",
                "--latest-since", "2026-10-21T12:00:00Z", "--now", "2026-10-22T03:00:00Z", "--fast-track"]
        p = run(self.d, *base, "--classification", "other", "--reason", "new thing")
        self.assertNotEqual(p.returncode, 0)
        p = run(self.d, *base, "--classification", "fix")
        self.assertEqual(p.returncode, 1)
        self.assertIn("fast_track needs a reason", p.stdout)
        p = run(self.d, *base)
        self.assertEqual(p.returncode, 1)
        p = run(self.d, *[a if a != "log" else " " for a in base], "--classification", "fix", "--reason", "r")
        self.assertEqual(p.returncode, 1)
        self.assertIn("evidence", p.stdout)
        self.assertEqual((self.d / "stable").read_text().strip(), "0.3.25")
        self.assertFalse((self.d / "promotions" / "0.3.26.json").exists())

    def test_without_fast_track_the_72h_default_still_holds(self):
        run(self.d, "cut", "0.3.26")
        p = run(self.d, "promote", "0.3.26", "--from", "0.3.25", "--evidence", "log", "--classification", "fix",
                "--latest-since", "2026-10-21T12:00:00Z", "--now", "2026-10-22T03:00:00Z")
        self.assertEqual(p.returncode, 2)                      # classification alone never waives anything
        p = run(self.d, "promote", "0.3.26", "--from", "0.3.25", "--evidence", "log",
                "--latest-since", "2026-10-21T12:00:00Z", "--now", "2026-10-22T03:00:00Z")
        self.assertEqual(p.returncode, 1)
        self.assertIn("DECISIONS #82", p.stdout)
        self.assertEqual((self.d / "stable").read_text().strip(), "0.3.25")

    def test_check_catches_an_unpromoted_stable_and_a_trailing_latest(self):
        (self.d / "stable").write_text("0.3.26\n")
        p = run(self.d, "check")
        self.assertEqual(p.returncode, 1)
        self.assertIn("no promotion record", p.stdout)
        self.assertIn("trails", p.stdout)


class Gate(unittest.TestCase):
    GOOD = {"version": "1.2.3", "latest_since": "2026-10-21T11:00:00Z", "promoted_at": "2026-10-24T11:00:00Z",
            "upgrade_test": {"from": "1.2.2", "to": "1.2.3", "passed": True, "evidence": "e"}}

    def test_gate(self):
        self.assertEqual(ps.promotion_problems(self.GOOD, "1.2.3"), [])
        bad = {**self.GOOD, "upgrade_test": {**self.GOOD["upgrade_test"], "passed": False}}
        self.assertEqual(ps.promotion_problems(bad, "1.2.3"), ["no passed upgrade test"])
        self.assertTrue(ps.promotion_problems({"version": "0.3.26", "grandfathered": "x"}, "0.3.26"))
        quick = {**self.GOOD, "promoted_at": "2026-10-21T15:00:00Z"}
        self.assertTrue(any("soaked 4.0h" in x for x in ps.promotion_problems(quick, "1.2.3")))
        fix = {**quick, "fast_track": {"classification": "fix", "reason": "r"}}
        self.assertEqual(ps.promotion_problems(fix, "1.2.3"), [])
        self.assertTrue(ps.promotion_problems({**fix, "upgrade_test": None}, "1.2.3"))      # still needs the test
        self.assertTrue(ps.promotion_problems({**fix, "promoted_at": "2026-10-20T00:00:00Z"}, "1.2.3"))

    def test_identical_to_the_app_manager_gate(self):
        """The mirror's updater (wam/updates.py) must judge records exactly like this tool."""
        import importlib.util
        wam = ROOT.parent / "wizard-app-manager" / "wam" / "updates.py"
        if not wam.is_file():
            self.skipTest("no wizard-app-manager checkout beside this repo")
        spec = importlib.util.spec_from_file_location("wam_updates", wam)
        up = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(up)
        self.assertEqual((up.SOAK_HOURS, up.GRANDFATHERED_THROUGH, up.FAST_TRACK_CLASSES),
                         (ps.SOAK_HOURS, ps.GRANDFATHERED_THROUGH, ps.FAST_TRACK_CLASSES))
        t = self.GOOD["upgrade_test"]
        q = {**self.GOOD, "promoted_at": "2026-10-21T15:00:00Z"}
        cases = [self.GOOD, None, {}, {"version": "1.2.4"}, {"version": "1.2.3", "grandfathered": "x"},
                 {"version": "0.3.20", "grandfathered": "x"}, {**self.GOOD, "promoted_at": "2026-10-22T00:00:00Z"},
                 {**self.GOOD, "latest_since": "nope"}, {**self.GOOD, "upgrade_test": None},
                 {**self.GOOD, "upgrade_test": {**t, "from": "1.2.3"}}, {**self.GOOD, "upgrade_test": {**t, "from": "x"}},
                 {**self.GOOD, "upgrade_test": {**t, "to": "9"}}, {**self.GOOD, "upgrade_test": {**t, "evidence": ""}},
                 {**q, "fast_track": {"classification": "fix", "reason": "r"}},
                 {**q, "fast_track": {"classification": "feature", "reason": "r"}},
                 {**q, "fast_track": {"classification": "fix", "reason": " "}}, {**q, "fast_track": "fix"},
                 {**q, "fast_track": {"classification": "fix", "reason": "r"}, "upgrade_test": None},
                 {**q, "promoted_at": "2026-10-20T00:00:00Z", "fast_track": {"classification": "fix", "reason": "r"}}]
        for rec in cases:
            for v in ("1.2.3", "0.3.20", "0.3.26"):
                with self.subTest(rec=rec, v=v):
                    self.assertEqual(ps.promotion_problems(rec, v), up.promotion_problems(rec, v))
        for a, b in (("0.3.9", "0.3.10"), ("1.0.0", "1.0.0-rc.1"), ("0.3.25", "0.3.26")):
            self.assertEqual(ps._key(a) < ps._key(b), up._key(a) < up._key(b))

if __name__ == "__main__":
    unittest.main()
