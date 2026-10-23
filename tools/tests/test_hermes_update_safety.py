"""Focused updater safety regressions; VM acceptance remains the runtime/rollback gate."""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

LOADER = importlib.machinery.SourceFileLoader("wizard_update_safety", str(Path(__file__).resolve().parents[1] / "wizard"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
w = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(w)


class Safety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hermes-updater-safety-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def test_backup_symlink_never_chmods_live_target(self):
        target = self.home / "live-secret"
        target.write_text("private fixture")
        target.chmod(0o640)
        (self.home / "skills").mkdir()
        (self.home / "skills" / "linked").symlink_to(target)
        w.backup_home(self.home, self.home / "backup")
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertTrue((self.home / "backup" / "skills" / "linked").is_symlink())

    def test_foreign_drain_is_not_overwritten_or_removed(self):
        marker = self.home / ".drain_request.json"
        marker.write_text('{"principal":"owner-maintenance"}')
        before = marker.read_bytes()
        with self.assertRaises(w.Fail):
            w._drain(self.home, True)
        w._drain(self.home, False)
        self.assertEqual(marker.read_bytes(), before)

    def test_interrupted_idle_recheck_releases_own_drain(self):
        with patch.object(w, "busy_reasons", return_value=[]), patch("time.sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                w.wait_quiet(self.home, True, 60, lambda _: None)
        self.assertFalse((self.home / ".drain_request.json").exists())

    def test_work_arriving_during_drain_is_not_quiet(self):
        with patch.object(w, "busy_reasons", side_effect=[[], ["late helper"]]), patch("time.sleep"):
            with self.assertRaises(w.Fail) as exc:
                w.wait_quiet(self.home, True, 0, lambda _: None)
        self.assertEqual(exc.exception.code, "not_quiet")
        self.assertFalse((self.home / ".drain_request.json").exists())

    def test_stop_failure_is_not_writer_absence(self):
        with patch.object(w, "run_hermes", return_value=SimpleNamespace(returncode=1)), \
                patch.object(w, "_health", return_value={"ok": True}):
            with self.assertRaisesRegex(RuntimeError, "stop failed"):
                w.stop_gateway(self.home, "http://fixture", 0)

    def test_successful_stop_command_with_live_pid_is_still_refused(self):
        (self.home / "gateway_state.json").write_text(json.dumps({"pid": os.getpid()}))
        with patch.object(w, "run_hermes", return_value=SimpleNamespace(returncode=0)), \
                patch.object(w, "_health", return_value={"ok": False}):
            with self.assertRaisesRegex(RuntimeError, "still running"):
                w.stop_gateway(self.home, "http://fixture", 0)

    def test_absent_gateway_allows_restoration(self):
        with patch.object(w, "run_hermes", side_effect=RuntimeError("broken dependency environment")) as run, \
                patch.object(w, "_health", return_value={"ok": False}):
            w.stop_gateway(self.home, "http://fixture", 0)
        run.assert_not_called()

    def test_unreadable_gateway_state_is_not_proof_of_absence(self):
        (self.home / "gateway_state.json").write_text("{broken")
        self.assertTrue(w._gateway_pid_alive(self.home))

    def git(self, repo, *args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def make_origin(self):
        origin = self.home / "origin"
        origin.mkdir()
        self.git(origin, "init", "-b", "main")
        self.git(origin, "config", "user.name", "Fixture")
        self.git(origin, "config", "user.email", "fixture@example.invalid")
        (origin / "file").write_text("old")
        self.git(origin, "add", "file")
        self.git(origin, "commit", "-m", "old")
        old = self.git(origin, "rev-parse", "HEAD")
        self.git(origin, "tag", "v0.1.0")
        (origin / "file").write_text("new")
        self.git(origin, "commit", "-am", "new")
        new = self.git(origin, "rev-parse", "HEAD")
        self.git(origin, "tag", "v0.2.0")
        return origin, old, new

    def test_real_shallow_clone_gets_ancestry_not_timestamp_fallback(self):
        origin, old, new = self.make_origin()
        repo = self.home / "clone"
        self.git(self.home, "clone", "--depth", "1", "--branch", "v0.1.0", origin.as_uri(), str(repo))
        self.assertEqual(self.git(repo, "rev-parse", "--is-shallow-repository"), "true")
        w.prove_forward(repo, old, {"tag": "v0.2.0", "commit": new})
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), old)
        self.assertEqual(self.git(repo, "rev-parse", "--is-shallow-repository"), "false")
        with self.assertRaises(w.Fail):
            w.prove_forward(repo, new, {"tag": "v0.1.0", "commit": old})

    def test_divergent_newer_commit_is_refused(self):
        origin, old, new = self.make_origin()
        self.git(origin, "checkout", "--orphan", "divergent")
        self.git(origin, "commit", "--allow-empty", "-m", "newer unrelated history")
        other = self.git(origin, "rev-parse", "HEAD")
        self.git(origin, "tag", "v0.3.0")
        with self.assertRaises(w.Fail) as exc:
            w.prove_forward(origin, new, {"tag": "v0.3.0", "commit": other})
        self.assertEqual(exc.exception.code, "update_refused")


if __name__ == "__main__":
    unittest.main()
