"""check_release.py: shape checks (offline) and the --stable pointer.

    python3 -m unittest tools/tests/test_check_release.py -v
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECK = HERE.parent / "check_release.py"


def run(*args):
    return subprocess.run([sys.executable, str(CHECK), *args], capture_output=True, text=True, timeout=60)


class Shape(unittest.TestCase):
    def test_every_release_file_has_a_valid_shape(self):
        files = sorted((ROOT / "releases").glob("*.json"))
        self.assertTrue(files)
        for f in files:
            with self.subTest(f.name):
                p = run(str(f), "--offline")
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_stable_names_an_existing_release(self):
        ver = (ROOT / "releases" / "stable").read_text().strip()
        self.assertTrue((ROOT / "releases" / f"{ver}.json").is_file(), ver)
        rel = json.loads((ROOT / "releases" / f"{ver}.json").read_text())
        self.assertEqual(rel["version"], ver)

    def test_stable_release_pins_what_the_installer_needs(self):
        """get.sh refuses a release without a 40-hex App Manager commit and sha256 image digests."""
        ver = (ROOT / "releases" / "stable").read_text().strip()
        rel = json.loads((ROOT / "releases" / f"{ver}.json").read_text())
        self.assertRegex(rel["components"]["wizard-app-manager"]["commit"], r"^[0-9a-f]{40}$")
        names = ("wizard-app-manager", "wizard-ux", "wizard-agent-service") if "wizard-ux" in rel["images"] else (
            "wizard-app-manager", "wizard-shell")
        for name in names:
            self.assertRegex(rel["images"][name]["digest"], r"^sha256:[0-9a-f]{64}$")
        for slot, d in rel["default_apps"].items():
            if d:
                self.assertIn("index_version", d, slot)

    def test_a_bad_commit_fails_the_shape(self):
        rel = json.loads((ROOT / "releases" / "0.2.1.json").read_text())
        rel["components"]["wizard-app-manager"]["commit"] = "main"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(rel, f)
        p = run(f.name, "--offline")
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("FAIL", p.stdout)


if __name__ == "__main__":
    unittest.main()
