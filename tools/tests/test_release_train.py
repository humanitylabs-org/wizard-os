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


if __name__ == "__main__":
    unittest.main()
