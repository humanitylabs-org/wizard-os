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


def setUpModule():
    """The hotfix lane is always on (wizard-os#434), so every soak gate asks GitHub for hotfix issues. Tests never
    read the real GitHub: no hotfixes unless a test patches hotfix_prs itself."""
    p = mock.patch.object(rt, "hotfix_prs", return_value=[])
    p.start()
    unittest.addModuleCleanup(p.stop)


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


class PrBody(unittest.TestCase):
    def test_a_long_ride_along_list_fits_githubs_limit(self):
        body = "Cut 0.3.180\n\n" + "\n".join(f"- wizard-ux#{n} [fix] Recommended fix: {'x' * 150}" for n in range(500))
        self.assertGreater(len(body), 65536)
        out = rt.fit_body(body)
        self.assertLessEqual(len(out), 65536)
        self.assertTrue(out.startswith("Cut 0.3.180\n\n- wizard-ux#0 "))
        self.assertRegex(out.splitlines()[-1], r"and \d+ more lines")

    def test_a_short_body_is_unchanged(self):
        self.assertEqual(rt.fit_body("short\nbody"), "short\nbody")

    def test_open_and_merge_sends_the_fitted_body(self):
        src = (HERE.parent / "release_train.py").read_text()
        body = src[src.index("def open_and_merge("):src.index("def mirror_problems(")]
        self.assertIn('"--body", fit_body(body)', body)


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

    def test_a_repo_that_only_moved_owner_is_no_ride_along(self):
        S = self.base(); S["default_apps"]["files"]["repo"] = "oscarhenrycollins/files"
        C = json.loads(json.dumps(S)); C["default_apps"]["files"]["repo"] = "humanitylabs-org/files"
        self.assertEqual(self._ride(S, C, [])[:2], ("fix", []))


class RepoMoves(unittest.TestCase):
    """wizard-os#945: a cut pins every moved repo under GitHub's new name, same commit."""
    MOVED = {"oscarhenrycollins/files": "humanitylabs-org/files",
             "oscarhenrycollins/hermes-agent": "humanitylabs-org/hermes-agent"}

    def rel(self):
        return {"components": {"wizard-ux": {"repo": "humanitylabs-org/wizard-ux", "commit": "a" * 40}},
                "default_apps": {"files": {"app": "files", "repo": "oscarhenrycollins/files", "commit": "d" * 40},
                                 "browser": {"app": "browser", "repo": "oscarhenrycollins/browser", "commit": "e" * 40},
                                 "agent": {"app": "hermes-agent", "repo": "oscarhenrycollins/hermes-agent",
                                           "commit": "f" * 40},
                                 "agent-history": None}}

    def test_moved_repos_get_the_new_name_and_keep_their_commit(self):
        d = self.rel()
        calls = []
        moved = rt.follow_repo_moves(d, lookup=lambda r: calls.append(r) or self.MOVED.get(r, r))
        self.assertEqual(moved, ["default_apps.files: oscarhenrycollins/files -> humanitylabs-org/files"])
        self.assertEqual(d["default_apps"]["files"], {"app": "files", "repo": "humanitylabs-org/files", "commit": "d" * 40})
        self.assertEqual(d["default_apps"]["browser"]["repo"], "oscarhenrycollins/browser")
        self.assertNotIn("oscarhenrycollins/hermes-agent", calls)   # the lock-pinned Hermes recipe is left to James
        self.assertEqual(d["default_apps"]["agent"]["repo"], "oscarhenrycollins/hermes-agent")

    def test_a_failed_lookup_changes_nothing(self):
        d = self.rel()
        self.assertEqual(rt.follow_repo_moves(d, lookup=lambda r: None), [])
        self.assertEqual(d, self.rel())

    def test_the_cut_follows_moves_before_check_release(self):
        src = Path(rt.__file__).read_text()
        self.assertLess(src.index("moved = follow_repo_moves(C)"), src.index('"tools/check_release.py", f"releases/{V}.json"'))


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

    def test_mirror_gap_lists_canonical_releases_the_mirror_skipped(self):
        """wizard-app-manager#656: stalled mirror PRs left Latest jumping 0.3.182 -> 0.3.198 with no rollback target."""
        with tempfile.TemporaryDirectory() as d:
            wos, wam = Path(d, "wos"), Path(d, "wam")
            wos.mkdir(); wam.mkdir()
            for v in ("0.3.9", "0.3.10", "0.3.11", "0.3.12", "0.3.13", "0.3.14"):
                (wos / f"{v}.json").write_text("{}")
            (wos / "hermes-lock.json").write_text("{}")
            (wam / "0.3.9.json").write_text("{}"); (wam / "0.3.10.json").write_text("{}")
            (wam / "0.3.12.json").write_text("{}")
            (wam / "latest").write_text("0.3.10\n")
            # 0.3.12 is already there; 0.3.14 is the release being cut now; 0.3.9 is older than the mirror's latest.
            self.assertEqual(rt.mirror_gap(wos, wam, "0.3.14"), ["0.3.11", "0.3.13"])
            (wam / "latest").write_text("0.3.13\n")
            self.assertEqual(rt.mirror_gap(wos, wam, "0.3.14"), [])
            (wam / "latest").unlink()
            self.assertEqual(rt.mirror_gap(wos, wam, "0.3.14"), [])

    def test_the_cut_mirror_fills_the_gap_before_moving_latest(self):
        src = (HERE.parent / "release_train.py").read_text()
        i_gap = src.index('gap = mirror_gap(wt / "releases", mwt / "releases", V)')
        i_latest = src.index('shutil.copyfile(wt / "releases" / "latest", mwt / "releases" / "latest")')
        self.assertLess(i_gap, i_latest)

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

    def test_wam_image_found_whatever_short_sha_length_the_runner_used(self):
        # wizard-os#844: the runner tagged 7 chars, the train's clone abbreviates to 8 -> image never found.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                   "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"}
            git = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True,  # noqa: E731
                                            env=env).stdout.strip()
            git("init", "-q", "-b", "main")
            git("config", "core.abbrev", "8")
            (d / ".github" / "workflows").mkdir(parents=True)
            (d / ".github" / "workflows" / "image.yml").write_text(
                '      - id: v\n        run: echo "tag=v4.12.0-wizard.$(git rev-list --count HEAD)-$(git rev-parse --short HEAD)" '
                '>> "$GITHUB_OUTPUT"\n')
            git("add", "."); git("commit", "-qm", "one")
            (d / "wam.py").write_text("x\n"); git("add", "."); git("commit", "-qm", "two")
            img = git("rev-parse", "HEAD")
            (d / "wam.py").write_text("y\n"); git("commit", "-qam", "code")
            head = git("rev-parse", "HEAD")
            self.assertEqual(len(rt.wam_image_tag(d, img).rsplit("-", 1)[1]), 8)
            tags = rt.wam_image_tags(d, img)
            self.assertEqual(tags[0], rt.wam_image_tag(d, img))
            self.assertEqual({len(t.rsplit("-", 1)[1]) for t in tags}, set(range(7, 13)))
            published = f"ghcr.io/{rt.WAM}:v4.12.0-wizard.2-{img[:7]}"
            man = {"digest": "sha256:abc", "manifests": [{"platform": {"architecture": "amd64"}},
                                                         {"platform": {"architecture": "arm64"}}]}
            real_sh = rt.sh

            def fake_sh(cmd, *a, **kw):
                if cmd[:3] == ["docker", "buildx", "imagetools"]:
                    return json.dumps(man) if cmd[4] == published else "ERROR: not found"
                return real_sh(cmd, *a, **kw)

            def fake_gh(args):
                if args[0] == "run" and args[1] == "list" and rt.WAM_TEST_WORKFLOW in args:
                    return [{"headSha": head, "conclusion": "success", "status": "completed"}]
                if args[0] == "run" and args[1] == "list":
                    return [{"databaseId": 1, "headSha": img, "conclusion": "success", "url": "u",
                             "createdAt": "2026-11-21T00:00:00Z"}] if "push" in args else []
                return {"jobs": [{"name": "publish", "conclusion": "success"}, {"name": "attest", "conclusion": "success"}]}

            first = git("rev-list", "--max-parents=0", "HEAD")
            L = {"components": {"wizard-app-manager": {"commit": first}},
                 "images": {"wizard-app-manager": {"image_inputs": ["Dockerfile"]}}}
            with mock.patch.object(rt, "sh", fake_sh), mock.patch.object(rt, "gh_json", fake_gh), \
                    mock.patch.object(rt, "is_ancestor", lambda _d, a, b: b != first):
                got = rt.published_wam(d, L)
            self.assertIsNotNone(got)
            self.assertEqual(got["ref"], published)
            self.assertEqual(got["commit"], head)
            self.assertEqual(got["source_commit"], img)
            self.assertEqual(got["digest"], "sha256:abc")

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

    def test_a_deferred_cut_waits_out_the_window_then_cuts(self):
        # wizard-os#669: a deferred cut must run once the 30-minute window ends, without a repo variable.
        naps = []
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rt, "clone", return_value=Path(d)), \
                mock.patch.object(rt, "last_cut_age", return_value=600.0), \
                mock.patch.object(rt, "pending_hotfixes", return_value=[]), \
                mock.patch.object(rt.time, "sleep", side_effect=naps.append), \
                mock.patch.object(rt, "plan", side_effect=rt.Stop("planned")):
            with self.assertRaises(rt.Stop):
                rt.run(Path(d), False, False, [], False, "cut", wait_deferred=True)
        self.assertAlmostEqual(sum(naps), rt.MIN_CUT_INTERVAL - 600.0 + rt.CUT_WAIT_MARGIN)
        self.assertTrue(all(n <= rt.CUT_WAIT_POLL for n in naps))
        # a hotfix that turns up while waiting ends the wait at once
        naps.clear()
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rt, "clone", return_value=Path(d)), \
                mock.patch.object(rt, "last_cut_age", return_value=600.0), \
                mock.patch.object(rt, "pending_hotfixes", side_effect=[[], [], [{"repo": "o/r", "number": 7}]]), \
                mock.patch.object(rt.time, "sleep", side_effect=naps.append), \
                mock.patch.object(rt, "plan", side_effect=rt.Stop("planned")):
            with self.assertRaises(rt.Stop):
                rt.run(Path(d), False, False, [], False, "cut", wait_deferred=True)
        self.assertEqual(len(naps), 2)

    def test_release_cut_workflow_waits_instead_of_a_variable_sweep(self):
        wf = (HERE.parent.parent / ".github" / "workflows" / "release-cut.yml").read_text()
        self.assertIn("--wait-deferred", wf)
        self.assertNotIn("vars.RELEASE_CUT_PENDING", wf)
        self.assertNotIn("gh variable set", wf)

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
                mock.patch.object(rt, "SOAK_BY_CUT", False), \
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
                mock.patch.object(rt, "SOAK_BY_CUT", False), \
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
        # an unmeasurable soak stops loudly (wizard-os#416), never "an unknown time"
        with mock.patch.object(rt, "soaked_for", return_value=None), \
                mock.patch.object(rt, "release_blockers", side_effect=AssertionError("stops before")):
            with self.assertRaises(rt.Stop) as e:
                rt.soak_gate("0.3.102", "0.3.106", Path("/nonexistent"))
        self.assertIn("can't tell how long 0.3.106 has been For testers", str(e.exception))
        self.assertNotIn("'an unknown time' if hours is None", (HERE.parent / "release_train.py").read_text())

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

    def test_promote_soaked_passes_only_what_promote_stable_accepts_without_fast_track(self):
        """wizard-os#856: the first soaked promotion to pass the upgrade test stopped on `--classification/--reason/
        --notes only go with --fast-track` (exit 2), so Stable stayed put even with a green upgrade test."""
        src = (HERE.parent / "release_train.py").read_text()
        i = src.index('if mode == "soaked":     # the normal gate')
        block = src[i:src.index("else:", i)]
        for flag in ("--notes", "--classification", "--reason"):
            self.assertNotIn(f'"{flag}"', block)
        self.assertIn("only go with --fast-track", (HERE.parent / "promote_stable.py").read_text())

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
            src = history(Path(d) / "src", [("0.3.106", "2026-11-01T00:00:00Z")])
            from datetime import datetime
            now = datetime.fromisoformat("2026-11-04T01:00:00+00:00").timestamp()
            self.assertAlmostEqual(rt.soaked_for("0.3.106", src, now), 73.0, places=3)
            self.assertIsNone(rt.soaked_for("0.3.999", src, now))

    def test_cli_has_cut_and_promote_soaked(self):
        out = subprocess.run([sys.executable, str(HERE.parent / "release_train.py"), "--help"], capture_output=True,
                             text=True).stdout
        self.assertIn("cut", out)
        self.assertIn("promote-soaked", out)


GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin"}


def history(d: Path, cuts) -> Path:
    """A wizard-os-like repo whose releases/latest named each (version, ISO time) in turn, with origin/main set."""
    d.mkdir(parents=True)
    run = lambda *a, env=None: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True,  # noqa: E731
                                              env={**GIT_ENV, **(env or {})})
    run("init", "-q", "-b", "main")
    (d / "releases").mkdir()
    for v, when in cuts:
        (d / "releases" / f"{v}.json").write_text(json.dumps({"version": v}) + "\n")
        (d / "releases" / "latest").write_text(v + "\n")
        run("add", ".")
        run("commit", "-qm", f"cut {v}", env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    run("update-ref", "refs/remotes/origin/main", "HEAD")
    return d


class SoakByCutAge(unittest.TestCase):
    """wizard-os#416: the scheduled promote measured "an unknown time" (its clone has no checkout), and with cuts
    landing every few hours the current latest never reaches 72h. Measure from git objects, and promote the newest
    release cut 72h or more ago (on by default; WIZARD_TRAIN_SOAK_BY_CUT=0 restores the old rule)."""
    CUTS = [("0.3.102", "2026-11-01T00:00:00Z"), ("0.3.103", "2026-11-02T00:00:00Z"),
            ("0.3.104", "2026-11-03T00:00:00Z"), ("0.3.105", "2026-11-05T00:00:00Z"),
            ("0.3.106", "2026-11-06T23:00:00Z")]
    NOW = "2026-11-07T00:00:00+00:00"

    def no_checkout_clone(self, d: Path) -> Path:
        src = history(d / "src", self.CUTS)
        dst = d / "repos" / "wizard-os"
        subprocess.run(["git", "clone", "-q", "--no-checkout", str(src), str(dst)], check=True, capture_output=True)
        self.assertFalse((dst / "releases").exists())     # what clone() gives the train: no releases/ on disk
        return dst

    def now(self):
        from datetime import datetime
        return datetime.fromisoformat(self.NOW).timestamp()

    def test_on_by_default_and_0_turns_it_off(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "WIZARD_TRAIN_SOAK_BY_CUT"}
        probe = lambda e: subprocess.run([sys.executable, "-c", "import release_train as rt; print(rt.SOAK_BY_CUT)"],  # noqa: E731
                                         cwd=HERE.parent, env=e, capture_output=True, text=True).stdout.strip()
        self.assertEqual(probe(env), "True")
        self.assertEqual(probe({**env, "WIZARD_TRAIN_SOAK_BY_CUT": "0"}), "False")

    def test_latest_moving_every_30_min_still_promotes_a_72h_old_release(self):
        """The stall of 9-15 Nov 2026: a cut every 30 minutes, so latest is never 72h old. By default the gate must
        still promote the newest release cut 72h+ ago, keep the blocker gate, and promote_stable must accept it."""
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 11, 10, tzinfo=timezone.utc)
        cuts = [(f"0.3.{143 + i}", (start + timedelta(minutes=30 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"))
                for i in range(161)]                       # 0.3.143 .. 0.3.303 over 80h
        now = (start + timedelta(hours=80)).timestamp()    # latest 0.3.303 was cut 0h ago
        with tempfile.TemporaryDirectory() as d:
            src = history(Path(d) / "src", cuts)
            wos = Path(d) / "repos" / "wizard-os"
            subprocess.run(["git", "clone", "-q", "--no-checkout", str(src), str(wos)], check=True, capture_output=True)
            env = {k: v for k, v in __import__("os").environ.items() if k != "WIZARD_TRAIN_SOAK_BY_CUT"}
            default = subprocess.run([sys.executable, "-c", "import release_train as rt; print(rt.SOAK_BY_CUT)"],
                                     cwd=HERE.parent, env=env, capture_output=True, text=True).stdout.strip()
            with mock.patch.object(rt.time, "time", return_value=now), \
                    mock.patch.object(rt, "SOAK_BY_CUT", default == "True"), \
                    mock.patch.object(rt, "release_blockers", return_value=[]):
                due, why, hours, hf, v = rt.soak_gate("0.3.143", "0.3.303", wos)
            # cut i lands at 30*i min; 72h before "now" (80h) is 8h in, cut 16: 0.3.159 is the newest cut 72h+ ago
            self.assertEqual((due, v, hf), (True, "0.3.159", []), why)
            self.assertAlmostEqual(hours, 72.0)
            with mock.patch.object(rt.time, "time", return_value=now), \
                    mock.patch.object(rt, "SOAK_BY_CUT", default == "True"), \
                    mock.patch.object(rt, "release_blockers", return_value=["u blocker"]):
                due, why, _, _, _ = rt.soak_gate("0.3.143", "0.3.303", wos)
            self.assertFalse(due)
            self.assertTrue(why.startswith("HELD: 1 open release-blocker"), why)
            # promote_stable (normal gate, no fast-track) accepts it: latest_since from the same history
            import promote_stable as ps
            since = ps.latest_since("0.3.159", src / "releases")
            self.assertEqual(since, "2026-11-10T08:00:00Z")
            rec = {"version": "0.3.159", "latest_since": since,
                   "promoted_at": datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "upgrade_test": {"from": "0.3.143", "to": "0.3.159", "passed": True, "evidence": "x"}}
            self.assertEqual(ps.promotion_problems(rec, "0.3.159"), [])
            # the old rule (switch off) is the stall itself
            with mock.patch.object(rt.time, "time", return_value=now), mock.patch.object(rt, "SOAK_BY_CUT", False), \
                    mock.patch.object(rt, "release_blockers", return_value=[]):
                due, why, _, _, _ = rt.soak_gate("0.3.143", "0.3.303", wos)
            self.assertFalse(due)
            self.assertTrue(why.startswith("WAITING: 0.3.303 has been For testers for 0h"), why)

    def test_waiting_says_when_the_oldest_release_above_stable_is_due(self):
        with tempfile.TemporaryDirectory() as d:
            wos = self.no_checkout_clone(Path(d))
            with mock.patch.object(rt.time, "time", return_value=self.now()), \
                    mock.patch.object(rt, "SOAK_BY_CUT", True), \
                    mock.patch.object(rt, "release_blockers", return_value=[]):
                due, why, _, _, v = rt.soak_gate("0.3.104", "0.3.106", wos)
            self.assertFalse(due)
            self.assertIn("the oldest release above Stable, 0.3.105, was cut 48h ago and is promoted at 72h", why)

    def test_the_gate_measures_a_no_checkout_clone(self):
        with tempfile.TemporaryDirectory() as d:
            wos = self.no_checkout_clone(Path(d))
            self.assertAlmostEqual(rt.soaked_for("0.3.106", wos, self.now()), 1.0, places=3)
            with mock.patch.object(rt.time, "time", return_value=self.now()), \
                    mock.patch.object(rt, "SOAK_BY_CUT", False), \
                    mock.patch.object(rt, "release_blockers", return_value=[]):
                due, why, hours, hf, v = rt.soak_gate("0.3.102", "0.3.106", wos)
            self.assertFalse(due)
            self.assertTrue(why.startswith("WAITING: 0.3.106 has been For testers for 1h"), why)
            self.assertEqual(v, "0.3.106")

    def test_unreadable_history_stops_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rt.Stop):
                rt.soak_gate("0.3.102", "0.3.106", Path(d))     # not a git repo

    def test_switch_on_promotes_the_newest_release_cut_72h_ago(self):
        with tempfile.TemporaryDirectory() as d:
            wos = self.no_checkout_clone(Path(d))
            self.assertEqual(rt.due_by_cut("0.3.102", "0.3.106", wos, self.now()), ("0.3.104", 96.0))
            self.assertIsNone(rt.due_by_cut("0.3.104", "0.3.106", wos, self.now()))
            with mock.patch.object(rt.time, "time", return_value=self.now()), \
                    mock.patch.object(rt, "SOAK_BY_CUT", True), \
                    mock.patch.object(rt, "release_blockers", return_value=[]):
                due, why, hours, hf, v = rt.soak_gate("0.3.102", "0.3.106", wos)
                self.assertEqual((due, v, hf), (True, "0.3.104", []))
                self.assertAlmostEqual(hours, 96.0)
                # nothing old enough above stable: it waits on latest as before
                due, why, _, _, v = rt.soak_gate("0.3.104", "0.3.106", wos)
                self.assertFalse(due)
                self.assertEqual(v, "0.3.106")
            with mock.patch.object(rt.time, "time", return_value=self.now()), \
                    mock.patch.object(rt, "SOAK_BY_CUT", True), \
                    mock.patch.object(rt, "release_blockers", return_value=["u blocker"]):
                due, why, _, _, _ = rt.soak_gate("0.3.102", "0.3.106", wos)
                self.assertTrue(why.startswith("HELD: 1 open release-blocker"))

    def test_check_reads_the_clone_not_a_missing_folder(self):
        with tempfile.TemporaryDirectory() as d:
            wos = self.no_checkout_clone(Path(d))
            from io import StringIO
            with mock.patch.object(rt, "STATE", Path(d)), mock.patch.object(rt, "clone", return_value=wos), \
                    mock.patch.object(rt.time, "time", return_value=self.now()), \
                    mock.patch.object(rt, "SOAK_BY_CUT", True), \
                    mock.patch.object(rt, "release_blockers", return_value=[]), \
                    mock.patch("sys.stdout", new=StringIO()) as out:
                with mock.patch.object(rt, "show", side_effect=lambda r, ref, f: "0.3.106\n" if f.endswith("latest")
                                       else "0.3.102\n"):
                    self.assertEqual(rt.main(["--work", d, "promote-soaked", "--check"]), 0)
            self.assertIn("due=true", out.getvalue())
            self.assertIn("0.3.104 has soaked", out.getvalue())

    def test_run_takes_the_due_release_not_latest(self):
        src = (HERE.parent / "release_train.py").read_text()
        self.assertIn('p["candidate"], p["cut"], p["moves"] = version, False, {}', src)
        self.assertIn('C = L if V == latest else json.loads((wt / "releases" / f"{V}.json").read_text())', src)


class HotfixLane(unittest.TestCase):
    """wizard-os#434, always on (its switch was removed after show-and-tell): a merged PR that closes or references a
    `hotfix` issue skips the 30-min cut limit and reaches For everyone after 24h (0h with `breaking` or a closed
    release-blocker), still held by any open release-blocker."""
    UX = "humanitylabs-org/wizard-ux"

    def rel(self, ux):
        return {"components": {c: {"commit": ux if c == "wizard-ux" else "s" * 40} for c in rt.FIX_REPOS}}

    def issue(self, labels=(), merged=True, repo=UX, closes=()):
        pr = {"number": 7, "merged": merged, "mergeCommit": {"oid": "h" * 40}, "repository": {"nameWithOwner": repo},
              "closingIssuesReferences": {"nodes": [{"labels": {"nodes": [{"name": n} for n in c]}} for c in closes]}}
        return {"labels": {"nodes": [{"name": n} for n in ("hotfix", *labels)]},
                "timelineItems": {"nodes": [{"__typename": "CrossReferencedEvent", "source": pr},
                                            {"__typename": "ClosedEvent", "closer": pr}, {"__typename": "X"}]}}

    def test_always_on_no_switch_left(self):
        src = (HERE.parent / "release_train.py").read_text()
        self.assertNotIn("WIZARD_TRAIN_HOTFIX_LANE", src)
        self.assertFalse(hasattr(rt, "HOTFIX_LANE"))
        env = {**__import__("os").environ, "WIZARD_TRAIN_HOTFIX_LANE": "0"}   # a stale env value changes nothing
        out = subprocess.run([sys.executable, "-c", "import release_train as rt; print(hasattr(rt, 'HOTFIX_LANE'))"],
                             cwd=HERE.parent, env=env, capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, "False")

    def test_no_gh_on_path_keeps_normal_timing(self):
        rels = {"releases/0.3.102.json": self.rel("a" * 40), "releases/0.3.106.json": self.rel("b" * 40)}
        with mock.patch.object(rt, "show", side_effect=lambda d, ref, f: json.dumps(rels[f])), \
                mock.patch.object(rt, "hotfix_prs", side_effect=FileNotFoundError("gh")):
            self.assertEqual(rt.hotfix_soak(Path("."), "0.3.102", "0.3.106"), (72, []))

    def test_finds_merged_component_prs_and_what_makes_them_immediate(self):
        got = rt.hotfix_prs_of("u", self.issue())
        self.assertEqual(got, [{"repo": self.UX, "number": 7, "commit": "h" * 40, "issue": "u", "immediate": False}])
        self.assertTrue(rt.hotfix_prs_of("u", self.issue(labels=["breaking"]))[0]["immediate"])
        self.assertTrue(rt.hotfix_prs_of("u", self.issue(closes=[["bug", "release-blocker"]]))[0]["immediate"])
        self.assertFalse(rt.hotfix_prs_of("u", self.issue(closes=[["bug"]]))[0]["immediate"])
        self.assertEqual(rt.hotfix_prs_of("u", self.issue(merged=False)), [])
        self.assertEqual(rt.hotfix_prs_of("u", self.issue(repo="humanitylabs-org/wizard-os")), [])

    def gate(self, hours, immediate=False, blockers=(), in_latest=True, lookup_fails=False):
        hf = [{"repo": self.UX, "number": 7, "commit": "h" * 40, "issue": "u", "immediate": immediate}]
        rels = {"releases/0.3.102.json": self.rel("a" * 40), "releases/0.3.106.json": self.rel("b" * 40)}
        with mock.patch.object(rt, "show", side_effect=lambda d, ref, f: json.dumps(rels[f])), \
                mock.patch.object(rt, "hotfix_prs", side_effect=rt.Stop("down") if lookup_fails else None, return_value=hf), \
                mock.patch.object(rt, "contains", side_effect=lambda repo, ref, c: ref == "b" * 40 and in_latest), \
                mock.patch.object(rt, "soaked_for", return_value=hours), \
                mock.patch.object(rt, "SOAK_BY_CUT", False), \
                mock.patch.object(rt, "release_blockers", return_value=list(blockers)):
            return rt.soak_gate("0.3.102", "0.3.106", Path("/nonexistent"))[:4]

    def test_a_hotfix_reaches_for_everyone_after_24h(self):
        due, why, _, hf = self.gate(20.0)
        self.assertFalse(due)
        self.assertIn("after 24h (hotfix lane: wizard-ux#7)", why)
        due, why, _, hf = self.gate(24.5)
        self.assertTrue(due, why)
        self.assertEqual(len(hf), 1)

    def test_breaking_or_a_closed_release_blocker_promotes_right_away_but_open_blockers_still_hold(self):
        self.assertTrue(self.gate(0.2, immediate=True)[0])
        self.assertTrue(self.gate(None, immediate=True)[0])
        due, why, _, _ = self.gate(0.2, immediate=True, blockers=["x other"])
        self.assertFalse(due)
        self.assertTrue(why.startswith("HELD: 1 open release-blocker"))

    def test_no_hotfix_or_a_failed_lookup_keeps_72h(self):
        due, why, _, hf = self.gate(30.0, in_latest=False)
        self.assertFalse(due)
        self.assertIn("after 72h.", why)
        self.assertEqual(hf, [])
        due, why, _, _ = self.gate(30.0, lookup_fails=True)
        self.assertFalse(due)
        self.assertIn("after 72h.", why)

    def test_with_latest_moving_every_30_min_a_hotfix_still_reaches_for_everyone_after_24h(self):
        """Soak by cut age is on by default (#416) and latest is cut every ~30 min, so latest itself is never 24h old.
        The newest release cut 24h+ ago that carries the hotfix must take the shortened soak (wizard-os#434)."""
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 11, 10, tzinfo=timezone.utc)
        cuts = [(f"0.3.{143 + i}", (start + timedelta(minutes=30 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"))
                for i in range(61)]                        # 0.3.143 .. 0.3.203 over 30h
        now = (start + timedelta(hours=30)).timestamp()    # 24h before now is cut 12: 0.3.155
        pin = lambda v: f"{int(v.split('.')[2]):040d}"     # noqa: E731  (a fake wizard-ux commit per release)
        hf = [{"repo": self.UX, "number": 7, "commit": "h" * 40, "issue": "u", "immediate": False}]

        def gate(first_with_fix, blockers=()):
            carries = lambda ref: ref != "main" and int(ref) >= int(pin(first_with_fix))  # noqa: E731
            with tempfile.TemporaryDirectory() as d:
                src = history(Path(d) / "src", cuts)
                wos = Path(d) / "repos" / "wizard-os"
                subprocess.run(["git", "clone", "-q", "--no-checkout", str(src), str(wos)], check=True,
                               capture_output=True)
                with mock.patch.object(rt.time, "time", return_value=now), \
                        mock.patch.object(rt, "SOAK_BY_CUT", True), \
                        mock.patch.object(rt, "show", side_effect=lambda r, ref, f: json.dumps(
                            self.rel(pin(f.split("/")[1][:-5])))), \
                        mock.patch.object(rt, "hotfix_prs", return_value=hf), \
                        mock.patch.object(rt, "contains", side_effect=lambda repo, ref, c: carries(ref)), \
                        mock.patch.object(rt, "release_blockers", return_value=list(blockers)):
                    return rt.soak_gate("0.3.143", "0.3.203", wos)

        # the hotfix landed in 0.3.150 (cut 27h ago): 0.3.155 (cut 24h ago) carries it and is promoted now
        due, why, hours, got, v = gate("0.3.150")
        self.assertEqual((due, v), (True, "0.3.155"), why)
        self.assertAlmostEqual(hours, 24.0)
        self.assertEqual([h["number"] for h in got], [7])
        # an open release-blocker still holds it
        due, why, _, _, _ = gate("0.3.150", blockers=["x other"])
        self.assertFalse(due)
        self.assertTrue(why.startswith("HELD: 1 open release-blocker"), why)
        # the hotfix landed only in 0.3.190 (cut 6.5h ago): nothing carrying it has soaked 24h, so it waits
        due, why, _, _, v = gate("0.3.190")
        self.assertFalse(due)
        self.assertIn("after 24h (hotfix lane: wizard-ux#7)", why)
        self.assertEqual(v, "0.3.203")

    def test_a_pending_hotfix_skips_the_30_minute_limit(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(rt, "clone", return_value=Path(d)), \
                mock.patch.object(rt, "last_cut_age", return_value=600.0), \
                mock.patch.object(rt, "pending_hotfixes", return_value=[{"repo": self.UX, "number": 7}]), \
                mock.patch.object(rt, "plan", side_effect=rt.Stop("planned")):
            with self.assertRaises(rt.Stop):
                rt.run(Path(d), False, False, [], False, "cut")
        with mock.patch.object(rt, "show", side_effect=lambda d, ref, f: "0.3.106\n" if f == "releases/latest"
                                  else json.dumps(self.rel("b" * 40))), \
                mock.patch.object(rt, "hotfix_prs", return_value=[{"repo": self.UX, "number": 7, "commit": "h" * 40,
                                                                  "issue": "u", "immediate": False}]), \
                mock.patch.object(rt, "contains", side_effect=lambda repo, ref, c: ref == "main"):
            self.assertEqual([h["number"] for h in rt.pending_hotfixes(Path("."))], [7])

    def test_hotfix_promotion_is_recorded_as_a_fast_track_after_the_upgrade_test(self):
        src = (HERE.parent / "release_train.py").read_text()
        i = src.index('if mode == "soaked" and rep.get("hotfixes"):')
        block = src[i:src.index('elif mode == "soaked":', i)]
        self.assertIn("--fast-track", block)
        self.assertIn("Hotfix lane (wizard-os#434)", block)
        self.assertLess(src.index('rig.get("passed")'), i)


if __name__ == "__main__":
    unittest.main()
