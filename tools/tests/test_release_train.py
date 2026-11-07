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


class MirrorCheck(unittest.TestCase):
    """DECISIONS #96 as amended (Nov 2026): the mirror PR merges on an automated byte-identity check, not a click."""
    REL = b'{"version": "0.3.106"}\n'

    def _check(self, changes, mirror, canonical, base=None):
        return rt.mirror_problems(changes, lambda f: mirror[f], lambda f: canonical.get(f), lambda f: (base or {}).get(f))

    def test_identical_files_and_an_append_only_readme_pass(self):
        probs, proofs = self._check(
            [("A", "releases/0.3.106.json"), ("M", "releases/latest"), ("M", "releases/README.md")],
            {"releases/0.3.106.json": self.REL, "releases/latest": b"0.3.106\n", "releases/README.md": b"# R\n\n## 0.3.106\n"},
            {"releases/0.3.106.json": self.REL, "releases/latest": b"0.3.106\n"},
            {"releases/README.md": b"# R\n"})
        self.assertEqual(probs, [])
        self.assertEqual(len(proofs), 3)
        self.assertIn(rt.hashlib.sha256(self.REL).hexdigest()[:16], proofs[0])

    def test_one_changed_byte_fails(self):
        probs, _ = self._check([("A", "releases/0.3.106.json")], {"releases/0.3.106.json": self.REL.replace(b"6", b"7")},
                               {"releases/0.3.106.json": self.REL})
        self.assertEqual(len(probs), 1)
        self.assertIn("!= wizard-os", probs[0])

    def test_anything_else_fails(self):
        cases = [
            ([("M", "wam/cli.py")], {"wam/cli.py": b"x"}, {}),                                   # outside releases/
            ([("D", "releases/0.3.90.json")], {"releases/0.3.90.json": b""}, {}),                # a deletion
            ([("A", "releases/9.9.9.json")], {"releases/9.9.9.json": self.REL}, {}),             # not in wizard-os
            ([("A", "releases/../x")], {"releases/../x": b""}, {}),
            ([], {}, {}),                                                                       # empty PR
        ]
        for changes, mirror, canonical in cases:
            self.assertTrue(self._check(changes, mirror, canonical)[0], changes)
        probs, _ = self._check([("M", "releases/README.md")], {"releases/README.md": b"# rewritten\n"}, {},
                               {"releases/README.md": b"# R\n"})
        self.assertIn("not append-only", probs[0])

    def test_verify_mirror_runs_on_real_git_and_posts_the_status(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                   "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}
            git = lambda repo, *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True,  # noqa: E731
                                                  text=True, env=env).stdout.strip()
            wos, wam = d / "wos", d / "wam"
            for r in (wos, wam):
                (r / "releases").mkdir(parents=True)
                git(r, "init", "-q", "-b", "main")
            (wos / "releases" / "0.3.106.json").write_bytes(self.REL)
            (wos / "releases" / "latest").write_text("0.3.106\n")
            git(wos, "add", "."); git(wos, "commit", "-qm", "cut")
            git(wos, "update-ref", "refs/remotes/origin/main", "HEAD")
            (wam / "releases" / "README.md").write_text("# R\n")
            git(wam, "add", "."); git(wam, "commit", "-qm", "base")
            base = git(wam, "rev-parse", "HEAD")
            (wam / "releases" / "0.3.106.json").write_bytes(self.REL)
            (wam / "releases" / "latest").write_text("0.3.106\n")
            (wam / "releases" / "README.md").write_text("# R\n\n## 0.3.106\n")
            git(wam, "add", "."); git(wam, "commit", "-qm", "mirror")
            head = git(wam, "rev-parse", "HEAD")
            real_sh, posted = rt.sh, []

            def fake_sh(cmd, *a, **k):
                if cmd[:2] == ["git", "-C"] and "fetch" in cmd:
                    return ""
                if cmd[:3] == ["gh", "api", "-X"]:
                    posted.append(cmd)
                    return ""
                return real_sh(cmd, *a, **k)
            with mock.patch.object(rt, "sh", side_effect=fake_sh), \
                    mock.patch.object(rt, "gh_json", return_value={"headRefOid": head}):
                proofs = rt.verify_mirror(wam, wos, base, "7", head)
                self.assertEqual(len(proofs), 3)
                self.assertIn(f"repos/{rt.WAM}/statuses/{head}", posted[-1])
                self.assertIn("state=success", posted[-1])
                self.assertIn(f"context={rt.MIRROR_STATUS}", posted[-1])
                (wam / "releases" / "latest").write_text("0.3.107\n")
                git(wam, "commit", "-qam", "drift")
                bad = git(wam, "rev-parse", "HEAD")
            with mock.patch.object(rt, "sh", side_effect=fake_sh), \
                    mock.patch.object(rt, "gh_json", return_value={"headRefOid": bad}):
                with self.assertRaises(rt.Stop):
                    rt.verify_mirror(wam, wos, base, "7", bad)
                self.assertIn("state=failure", posted[-1])

    def test_mirror_merges_need_the_check_and_no_person(self):
        src = (HERE.parent / "release_train.py").read_text()
        body = src[src.index("def open_and_merge("):src.index("def mirror_problems(")]
        self.assertIn("min(time.time() + timeout, run_deadline())", body)   # every wait ends inside the run budget
        self.assertLess(rt.RUN_BUDGET_S, 3600)
        self.assertIn("verify(n, head)", body)
        self.assertIn("MIRROR_STATUS", body)
        self.assertIn('"--match-head-commit", head', body)
        self.assertNotIn("codex", body.lower())
        self.assertEqual(src.count("verify=lambda n, h: verify_mirror("), 2)   # cut mirror and promote mirror


class AppManagerAndBursts(unittest.TestCase):
    def test_app_manager_moves_with_source_commit_and_inputs(self):
        latest = (ROOT / "releases" / "latest").read_text().strip()
        L = json.loads((ROOT / "releases" / f"{latest}.json").read_text())
        pub = {"commit": "e" * 40, "ref": "ghcr.io/humanitylabs-org/wizard-app-manager:v4.10.2-wizard.1100-ddddddd",
               "digest": "sha256:" + "2" * 64, "ci_run": "https://github.com/x/y/actions/runs/2",
               "architectures": ["amd64", "arm64"], "source_commit": "d" * 40,
               "image_inputs": L["images"]["wizard-app-manager"]["image_inputs"]}
        C = rt.candidate_json(L, "9.9.9", {"wizard-app-manager": pub}, "0.0.1", [])
        self.assertEqual(C["components"]["wizard-app-manager"]["commit"], "e" * 40)
        im = C["images"]["wizard-app-manager"]
        self.assertEqual((im["source_commit"], im["digest"]), ("d" * 40, "sha256:" + "2" * 64))
        self.assertEqual(im["image_inputs"], L["images"]["wizard-app-manager"]["image_inputs"])
        self.assertIn("App Manager", C["name"])
        for k in ("wizard-ux", "wizard-agent-service"):
            self.assertEqual(C["components"][k], L["components"][k])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "9.9.9.json"
            p.write_text(json.dumps(C, indent=2) + "\n")
            r = subprocess.run([sys.executable, str(HERE.parent / "check_release.py"), "--offline", str(p)],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_wam_tag_follows_image_yml_and_mirror_only_commits_never_move(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                   "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}
            git = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True,  # noqa: E731
                                            env=env).stdout.strip()
            git("init", "-q", "-b", "main")
            (d / ".github" / "workflows").mkdir(parents=True)
            (d / ".github" / "workflows" / "image.yml").write_text(
                '      - id: v\n        run: echo "tag=v4.10.2-wizard.$(git rev-list --count HEAD)-$(git rev-parse --short HEAD)" '
                '>> "$GITHUB_OUTPUT"\n')
            git("add", "."); git("commit", "-qm", "one")
            (d / "wam.py").write_text("x\n"); git("add", "."); git("commit", "-qm", "two")
            a = git("rev-parse", "HEAD")
            self.assertEqual(rt.wam_image_tag(d, a), f"v4.10.2-wizard.2-{git('rev-parse', '--short', a)}")
            (d / "releases").mkdir(); (d / "releases" / "latest").write_text("0.3.106\n")
            git("add", "."); git("commit", "-qm", "mirror")
            b = git("rev-parse", "HEAD")
            self.assertTrue(rt.only_releases_changed(d, a, b))
            (d / "wam.py").write_text("y\n"); git("commit", "-qam", "code")
            self.assertFalse(rt.only_releases_changed(d, a, git("rev-parse", "HEAD")))

    def test_plan_cuts_the_app_manager_automatically(self):
        src = (HERE.parent / "release_train.py").read_text()
        i = src.index("def plan(")
        block = src[i:src.index("def next_version(")]
        self.assertIn("published_wam(d, L)", block)
        self.assertNotIn("cut by hand", block)

    def test_at_most_one_cut_per_30_minutes(self):
        self.assertEqual(rt.MIN_CUT_INTERVAL, 1800)
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rt, "clone", return_value=Path(d)), \
                mock.patch.object(rt, "last_cut_age", return_value=600.0), \
                mock.patch.object(rt, "plan", side_effect=AssertionError("a deferred cut plans nothing")):
            rep = rt.run(Path(d), False, False, [], False, "cut")
        self.assertTrue(rep["deferred"])
        self.assertTrue(rep["outcome"].startswith("DEFERRED: the last For testers cut was 10 min ago"))
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rt, "clone", return_value=Path(d)), \
                mock.patch.object(rt, "last_cut_age", return_value=1801.0), \
                mock.patch.object(rt, "plan", side_effect=rt.Stop("planned")):
            with self.assertRaises(rt.Stop):
                rt.run(Path(d), False, False, [], False, "cut")

    def test_last_cut_age_reads_releases_latest_history(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            env = {"GIT_AUTHOR_DATE": "2026-11-07T10:00:00Z", "GIT_COMMITTER_DATE": "2026-11-07T10:00:00Z",
                   "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                   "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}
            run = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, env=env)  # noqa: E731
            run("init", "-q", "-b", "main")
            (d / "releases").mkdir(); (d / "releases" / "latest").write_text("0.3.106\n")
            run("add", "."); run("commit", "-qm", "cut"); run("update-ref", "refs/remotes/origin/main", "HEAD")
            from datetime import datetime
            now = datetime.fromisoformat("2026-11-07T10:20:00+00:00").timestamp()
            self.assertAlmostEqual(rt.last_cut_age(d, now), 1200.0)

    def test_promote_check_is_cheap_and_prints_due(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(rt, "STATE", Path(d)), \
                mock.patch.object(rt, "clone", return_value=Path(d)), \
                mock.patch.object(rt, "show", side_effect=lambda repo, ref, f: "0.3.106\n" if f.endswith("latest") else "0.3.102\n"), \
                mock.patch.object(rt, "soaked_for", return_value=10.0), \
                mock.patch.object(rt, "plan", side_effect=AssertionError("no component clones")):
            from io import StringIO
            with mock.patch("sys.stdout", new=StringIO()) as out:
                self.assertEqual(rt.main(["--work", d, "promote-soaked", "--check"]), 0)
            self.assertIn("due=false", out.getvalue())
            self.assertIn("WAITING", out.getvalue())


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


if __name__ == "__main__":
    unittest.main()
