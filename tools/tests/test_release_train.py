"""release_train.py: fixes reach Stable within a day, only through a passed upgrade test, classified honestly.

    python3 -m unittest tools/tests/test_release_train.py -v
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
import release_train as rt  # noqa: E402


def pr(title, labels=(), n=1, repo="humanitylabs-org/wizard-ux"):
    return {"repo": repo, "number": n, "commit": "c" * 40, "title": title, "labels": list(labels)}


class Tiers(unittest.TestCase):
    def test_only_recommended_fixes_count_as_fixes(self):
        self.assertEqual(rt.tier(pr("Recommended fix: pins stay put")), "fix")
        self.assertEqual(rt.tier(pr("Pins stay put", ["tier: recommended fix"])), "fix")
        self.assertEqual(rt.tier(pr("Maintenance: bump", ["tier: maintenance"])), "maintenance")

    def test_anything_not_provably_a_fix_is_a_feature(self):
        for p in (pr("Strong suggestion (feel free to drop): x"), pr("Opinionated UX: y", ["tier: opinionated"]),
                  pr("Settings sheet", ["needs: james review"]), pr("Mizel: Landscapes Light"),   # unlabelled
                  pr("feat: new thing")):
            self.assertEqual(rt.tier(p), "feature", p)


class Candidate(unittest.TestCase):
    def setUp(self):
        latest = (ROOT / "releases" / "latest").read_text().strip()
        self.L = json.loads((ROOT / "releases" / f"{latest}.json").read_text())

    def test_candidate_moves_only_the_component_its_slot_and_image(self):
        pub = {"commit": "f" * 40, "ref": "ghcr.io/humanitylabs-org/wizard-agent-service:sha-" + "f" * 40,
               "digest": "sha256:" + "1" * 64, "ci_run": "https://github.com/x/y/actions/runs/1",
               "architectures": ["amd64", "arm64"]}
        C = rt.candidate_json(self.L, "9.9.9", {"wizard-agent-service": pub}, "0.0.1", ["wizard-agent-service#1 a fix"])
        self.assertEqual(C["version"], "9.9.9")
        self.assertEqual(C["components"]["wizard-agent-service"]["commit"], "f" * 40)
        self.assertEqual(C["images"]["wizard-agent-service"]["digest"], "sha256:" + "1" * 64)
        self.assertEqual(C["default_apps"]["agent-service"]["commit"], "f" * 40)
        for key in ("components", "images", "default_apps"):
            for name in self.L[key]:
                if name not in ("wizard-agent-service", "agent-service"):
                    self.assertEqual(C[key][name], self.L[key][name], f"{key}.{name} must not move")
        for key in set(self.L) - {"version", "name", "date", "about", "notes", "components", "images", "default_apps"}:
            self.assertEqual(C[key], self.L[key], key)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "9.9.9.json"
            p.write_text(json.dumps(C, indent=2) + "\n")
            r = subprocess.run([sys.executable, str(HERE.parent / "check_release.py"), "--offline", str(p)],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Classification(unittest.TestCase):
    def _ride(self, S, C, prs):
        with mock.patch.object(rt, "clone", return_value=Path("/nonexistent")), \
                mock.patch.object(rt, "is_ancestor", return_value=True), \
                mock.patch.object(rt, "merged_prs", side_effect=lambda repo, *a: [p for p in prs if p["repo"] == repo]):
            return rt.ride_alongs(Path("/tmp"), S, C)

    def base(self):
        comps = {c: {"commit": "a" * 40} for c in rt.FIX_REPOS}
        return {"version": "1.0.0", "components": comps, "images": {},
                "default_apps": {"shell": {"app": "wizard-ux", "commit": "a" * 40},
                                 "files": {"app": "files", "commit": "d" * 40}}}

    def test_fix_only_when_every_change_is_a_fix_or_maintenance(self):
        S = self.base(); C = json.loads(json.dumps(S)); C["version"] = "1.0.1"
        C["components"]["wizard-ux"]["commit"] = "b" * 40; C["default_apps"]["shell"]["commit"] = "b" * 40
        cls, items, prs = self._ride(S, C, [pr("Recommended fix: a", n=1), pr("Maintenance: b", ["tier: maintenance"], n=2)])
        self.assertEqual((cls, items), ("fix", []))
        cls, _, _ = self._ride(S, C, [pr("Recommended fix: a", n=1), pr("Strong suggestion: c", n=3)])
        self.assertEqual(cls, "feature")

    def test_other_moved_pins_are_listed_and_make_it_a_feature(self):
        S = self.base(); C = json.loads(json.dumps(S))
        C["default_apps"]["files"]["commit"] = "e" * 40
        cls, items, _ = self._ride(S, C, [])
        self.assertEqual(cls, "feature")
        self.assertTrue(any(i.startswith("default app files") for i in items), items)
        C = json.loads(json.dumps(S)); C["hermes"] = {"tag": "v2"}
        self.assertEqual(self._ride(S, C, [])[0], "feature")


class CodexGate(unittest.TestCase):
    def test_reads_the_latest_codex_state(self):
        body = lambda sha, st: ('<!-- codex-pull-request-review-summary -->\n<!-- codex-review-state:v1 {"code_review":'
                                f'{{"commit_sha":"{sha}","has_any_findings":false,"has_unresolved_findings":false,'
                                f'"status":"{st}"}},"security_review":{{"commit_sha":null}}}} -->')
        comments = [{"user": {"login": "chatgpt-codex-connector[bot]"}, "body": body("a" * 40, "completed")},
                    {"user": {"login": "someone"}, "body": body("c" * 40, "completed")},          # not Codex
                    {"user": {"login": "chatgpt-codex-connector[bot]"}, "body": body("b" * 40, "running")}]
        with mock.patch.object(rt, "gh_json", return_value=comments):
            self.assertEqual(rt.codex_state("o/r", "1"), {"commit_sha": "b" * 40, "has_any_findings": False,
                                                          "has_unresolved_findings": False, "status": "running"})
        with mock.patch.object(rt, "gh_json", return_value=[]):
            self.assertIsNone(rt.codex_state("o/r", "1"))


class Gate(unittest.TestCase):
    def test_force_is_only_for_dry_runs(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rt, "STATE", Path(d)):
            self.assertEqual(rt.main(["--work", d, "run", "--force"]), 2)

    def test_a_failed_upgrade_test_stops_before_any_promotion(self):
        """run() returns STOPPED and never calls promote_stable.py promote when the rig fails."""
        src = (HERE.parent / "release_train.py").read_text()
        i_rig, i_promote = src.index('rig.get("passed")'), src.index('"promote", V, "--from", stable')
        self.assertLess(i_rig, i_promote)
        block = src[i_rig:i_promote]
        self.assertIn("return rep", block)
        self.assertIn("STOPPED: the upgrade test", block)

    def test_promotion_record_uses_the_computed_classification_and_the_evidence(self):
        src = (HERE.parent / "release_train.py").read_text()
        self.assertIn('"--fast-track",\n        "--classification", cls', src)
        self.assertIn("promotion record's classification does not match", src)

    def test_a_feature_candidate_stays_on_latest_unless_asked(self):
        """Owner rule: fixes fast-track to Stable; features stop on Latest (no upgrade rig, no promotion)."""
        src = (HERE.parent / "release_train.py").read_text()
        i_gate = src.index('if cls != "fix" and not feature_fast_track and mode != "soaked":')
        self.assertLess(i_gate, src.index("cmd = [sys.executable, str(RIG)"))
        self.assertLess(i_gate, src.index('"promote", V, "--from", stable'))
        self.assertIn("return rep", src[i_gate:src.index("cmd = [sys.executable, str(RIG)")])
        self.assertIn("a.feature_fast_track", src)

    def test_an_unmirrored_latest_is_blocked_before_the_rig(self):
        """A latest cut by an earlier run whose mirror PR is unmerged: no 404 upgrade test, a BLOCKED outcome."""
        src = (HERE.parent / "release_train.py").read_text()
        i_gate = src.index('if not served(f"{V}.json", sha(rel_json)):')
        i_rig = src.index("cmd = [sys.executable, str(RIG)")
        self.assertLess(i_gate, i_rig)
        self.assertIn("return rep", src[i_gate:i_rig])
        self.assertIn('rep["outcome"] = (f"BLOCKED:', src[i_gate:i_rig])

    def test_served_compares_the_exact_bytes(self):
        body = b'{"version": "0.0.1"}\n'
        resp = mock.MagicMock()
        resp.__enter__.return_value.read.return_value = body
        with mock.patch.object(rt.urllib.request, "urlopen", return_value=resp):
            self.assertTrue(rt.served("0.0.1.json", rt.hashlib.sha256(body).hexdigest()))
            self.assertFalse(rt.served("0.0.1.json", "0" * 64))
        with mock.patch.object(rt.urllib.request, "urlopen", side_effect=OSError("404")):
            self.assertFalse(rt.served("0.0.1.json", rt.hashlib.sha256(body).hexdigest()))


class CodexWait(unittest.TestCase):
    def test_out_of_credits_is_detected_only_from_codex_after_the_pr_opened(self):
        comments = [
            {"user": {"login": "chatgpt-codex-connector[bot]"}, "created_at": "2026-10-31T03:02:48Z",
             "body": "Codex usage limits have been reached for code reviews."},
            {"user": {"login": "someone"}, "created_at": "2026-10-31T04:00:00Z",
             "body": "Codex usage limits have been reached for code reviews."},
        ]
        with mock.patch.object(rt, "gh_json", return_value=comments):
            self.assertTrue(rt.codex_out_of_credits("o/r", "1", "2026-10-31T03:00:00Z"))
            self.assertFalse(rt.codex_out_of_credits("o/r", "1", "2026-10-31T03:30:00Z"))
        with mock.patch.object(rt, "gh_json", return_value=None):
            self.assertFalse(rt.codex_out_of_credits("o/r", "1", "2026-10-31T03:00:00Z"))

    def test_every_merge_wait_ends_inside_the_run_budget(self):
        """A wrapper `timeout 3600` kills the run with no report; waits must raise Stop before that."""
        self.assertLess(rt.RUN_BUDGET_S, 3600)
        src = (HERE.parent / "release_train.py").read_text()
        body = src[src.index("def open_and_merge("):src.index("def codex_state(")]
        self.assertIn("min(time.time() + timeout, run_deadline())", body)
        self.assertIn("codex_out_of_credits(repo, n, opened_iso)", body)

    def test_out_of_credits_requests_a_non_author_reviewer(self):
        """No Codex credits must not leave the PR invisible: it goes into a teammate's review queue."""
        src = (HERE.parent / "release_train.py").read_text()
        body = src[src.index("def open_and_merge("):src.index("def codex_state(")]
        self.assertIn("request_reviewers(repo, n)", body)
        self.assertTrue(rt.FALLBACK_REVIEWERS)


if __name__ == "__main__":
    unittest.main()


class ForTestersForEveryone(unittest.TestCase):
    """For testers = every merge cut onto latest (`cut`); For everyone = latest after 72h with no release-blocker
    (`promote-soaked`), the normal promotion gate, never a fast-track."""

    def _plan(self, mode, latest="0.3.106", stable="0.3.102", hours=80.0, blockers=()):
        p = {"stable": stable, "latest": latest, "components": {}, "waiting_fixes": [], "manual": [],
             "unpublished": [], "moves": {}, "candidate": None, "cut": False}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rt, "plan", return_value=p) as plan, \
                mock.patch.object(rt, "clone", return_value=Path(d)), \
                mock.patch.object(rt, "soaked_for", return_value=hours), \
                mock.patch.object(rt, "release_blockers", return_value=list(blockers)), \
                mock.patch.object(rt, "worktree", side_effect=rt.Stop("reached the rig path")):
            try:
                rep = rt.run(Path(d), True, False, [], False, mode)
            except rt.Stop as e:
                rep = {"outcome": f"PROCEEDS: {e}"}
            return rep, plan

    def test_soak_constant_matches_promote_stable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ps", HERE.parent / "promote_stable.py")
        ps = importlib.util.module_from_spec(spec); spec.loader.exec_module(ps)
        self.assertEqual(rt.SOAK_HOURS, ps.SOAK_HOURS)

    def test_promote_soaked_waits_until_72_hours(self):
        rep, _ = self._plan("soaked", hours=71.5)
        self.assertTrue(rep["outcome"].startswith("WAITING: 0.3.106 has been For testers for 72h"[:30]))
        self.assertIn("after 72h", rep["outcome"])
        rep, _ = self._plan("soaked", hours=None)
        self.assertIn("an unknown time", rep["outcome"])

    def test_promote_soaked_is_held_by_an_open_release_blocker(self):
        rep, _ = self._plan("soaked", blockers=["https://github.com/humanitylabs-org/wizard-ux/issues/1 Chats blank"])
        self.assertTrue(rep["outcome"].startswith("HELD: 1 open release-blocker"))
        self.assertIn("Stable stays 0.3.102", rep["outcome"])

    def test_promote_soaked_with_nothing_newer_does_nothing(self):
        rep, _ = self._plan("soaked", latest="0.3.102")
        self.assertTrue(rep["outcome"].startswith("nothing to promote"))

    def test_promote_soaked_goes_on_to_the_upgrade_test_when_soaked_and_clear(self):
        rep, _ = self._plan("soaked", hours=72.0)
        self.assertEqual(rep["outcome"], "PROCEEDS: reached the rig path")

    def test_promote_soaked_uses_the_normal_gate_never_fast_track(self):
        src = (HERE.parent / "release_train.py").read_text()
        i = src.index('if mode == "soaked":     # the normal gate')
        block = src[i:src.index("else:", i)]
        self.assertNotIn("--fast-track", block)
        self.assertIn('"promote", V, "--from", stable, "--evidence", evidence', block)
        # it still needs a passed upgrade test first
        self.assertLess(src.index('rig.get("passed")'), i)

    def test_cut_plans_with_any_merge_and_stops_after_the_mirror(self):
        rep, plan = self._plan("cut")
        plan.assert_called_once()
        self.assertEqual(plan.call_args.kwargs, {"any_merge": True})
        self.assertTrue(rep["outcome"].startswith("nothing to cut"))
        src = (HERE.parent / "release_train.py").read_text()
        i_stop = src.index('if mode == "cut":\n        rep["outcome"] = (f"CUT {V} onto For testers')
        self.assertLess(src.index('rep["mirror_pr"] = open_and_merge'), i_stop)
        self.assertLess(i_stop, src.index("cmd = [sys.executable, str(RIG)"))

    def test_release_blockers_fail_closed(self):
        with mock.patch.object(rt, "gh_json", return_value=None):
            with self.assertRaises(rt.Stop):
                rt.release_blockers()
        with mock.patch.object(rt, "gh_json", return_value=[{"url": "u", "title": "t"}]) as g:
            self.assertEqual(rt.release_blockers(), ["u t"])
            self.assertIn("release-blocker", g.call_args.args[0])

    def test_soaked_for_reads_latest_history(self):
        with tempfile.TemporaryDirectory() as d:
            rel = Path(d)
            subprocess.run(["git", "init", "-q"], cwd=rel, check=True)
            (rel / "latest").write_text("0.3.106\n")
            env = {"GIT_AUTHOR_DATE": "2026-11-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-11-01T00:00:00Z",
                   "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                   "PATH": "/usr/bin:/bin"}
            subprocess.run(["git", "add", "latest"], cwd=rel, check=True)
            subprocess.run(["git", "commit", "-qm", "cut"], cwd=rel, check=True, env=env)
            from datetime import datetime
            now = datetime.fromisoformat("2026-11-04T01:00:00+00:00").timestamp()
            self.assertAlmostEqual(rt.soaked_for("0.3.106", rel, now), 73.0, places=3)
            self.assertIsNone(rt.soaked_for("0.3.999", rel, now))

    def test_cli_has_cut_and_promote_soaked(self):
        out = subprocess.run([sys.executable, str(HERE.parent / "release_train.py"), "--help"], capture_output=True,
                             text=True).stdout
        self.assertIn("cut", out)
        self.assertIn("promote-soaked", out)
