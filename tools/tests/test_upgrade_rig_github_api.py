"""Installing the OLD Stable on the rig must not depend on api.github.com's anonymous rate limit (wizard-os#856).

0.3.240's App Manager runs Runtipi's setup without --version, so the setup asks api.github.com for the latest Runtipi
without a token; on a shared GitHub-hosted runner the 60-an-hour limit is often used up and the install stopped after
"Installing runtipi...". The rig lends the guest's root curl a read-only token for api.github.com only, during the
old install, and takes it back before the upgrade."""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
RIG = ROOT / "tools" / "acceptance" / "upgrade-rig" / "kvm_upgrade.py"


def load():
    spec = importlib.util.spec_from_file_location("kvm_upgrade_ghapi", RIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class GuestScripts(unittest.TestCase):
    def setUp(self):
        self.m = load()
        self.home = tempfile.mkdtemp()

    def bash(self, script, stdin=""):
        return subprocess.run(["bash", "-c", script.replace("/root", self.home)], input=stdin, text=True,
                              capture_output=True)

    def test_on_scopes_token_to_api_github_and_off_restores(self):
        Path(self.home, ".curlrc").write_text("# owner's own\n")
        self.assertEqual(self.bash(self.m.GITHUB_API_AUTH_ON, "tok123\n").returncode, 0)
        netrc = Path(self.home, ".netrc").read_text()
        self.assertEqual(netrc, "machine api.github.com login x-access-token password tok123\n")
        self.assertEqual(os.stat(Path(self.home, ".netrc")).st_mode & 0o777, 0o600)
        self.assertIn("netrc-optional", Path(self.home, ".curlrc").read_text())
        self.assertEqual(self.bash(self.m.GITHUB_API_AUTH_OFF).returncode, 0)
        self.assertFalse(Path(self.home, ".netrc").exists())
        self.assertEqual(Path(self.home, ".curlrc").read_text(), "# owner's own\n")
        self.assertEqual(sorted(os.listdir(self.home)), [".curlrc"])


class Lending(unittest.TestCase):
    def test_no_token_changes_nothing(self):
        m = load()
        with mock.patch.dict(os.environ, {m.GITHUB_API_TOKEN_ENV: ""}), mock.patch.object(m, "sh") as sh, \
                mock.patch.object(m, "guest") as guest:
            self.assertFalse(m.github_api_auth(True))
            self.assertFalse(m.github_api_auth(False))
        sh.assert_not_called()
        guest.assert_not_called()

    def test_token_goes_over_stdin_never_argv(self):
        m = load()
        done = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.dict(os.environ, {m.GITHUB_API_TOKEN_ENV: "secret-tok"}), \
                mock.patch.object(m, "sh", return_value=done) as sh, mock.patch.object(m, "say"):
            self.assertTrue(m.github_api_auth(True))
        argv, kw = sh.call_args[0][0], sh.call_args[1]
        self.assertNotIn("secret-tok", " ".join(argv))
        self.assertEqual(kw["input"], "secret-tok\n")

    def test_workflow_lends_its_read_only_token(self):
        wf = (ROOT / ".github" / "workflows" / "release-promote.yml").read_text()
        self.assertIn("WIZARD_RIG_GITHUB_API_TOKEN: ${{ github.token }}", wf)
        self.assertIn("permissions:\n  contents: read", wf)

    def test_run_takes_the_token_back_before_the_upgrade(self):
        src = RIG.read_text()
        start = src.index("authed = github_api_auth(True)")
        self.assertLess(start, src.index("github_api_auth(False)"))
        self.assertLess(src.index("github_api_auth(False)"), src.index("before = snapshot()"))


if __name__ == "__main__":
    unittest.main()
