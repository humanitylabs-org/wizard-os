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


# The pin fresh installs ran in 0.3.21: hermes-agent app e8ae558 builds FROM this image (checked 21 Oct 2026).
SEPTEMBER_PIN = {
    "tag": "v2026.9.24",
    "commit": "f97608f178d1ffeca59860195ab7da295f7c8e5f",
    "image": {"ref": "docker.io/nousresearch/hermes-agent:v2026.9.24",
              "digest": "sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7"},
    "test_record": "none: carried over from 0.3.21, pinned before Wizard stable existed",
    "rollback": None,
}


class HermesPin(unittest.TestCase):
    """DECISIONS #74 / docs/HERMES_STABLE.md: every snapshot from 0.3.23 names one upstream Hermes release."""

    def check(self, hermes="unset", version="0.3.23"):
        rel = json.loads((ROOT / "releases" / "0.3.21.json").read_text())
        rel["version"] = version
        if hermes != "unset":
            rel["hermes"] = hermes
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(rel, f)
        return run(f.name, "--offline")

    def pin(self, **changes):
        return json.loads(json.dumps({**SEPTEMBER_PIN, **changes}))

    def assertFails(self, p, words):
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn(words, p.stdout)

    def test_new_snapshot_without_a_pin_fails(self):
        self.assertFails(self.check(), "hermes: required from 0.3.23")

    def test_older_snapshots_stay_history(self):
        self.assertEqual(self.check(version="0.3.22").returncode, 0)

    def test_carried_over_september_pin_passes(self):
        p = self.check(self.pin())
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_release_candidate_tags_are_refused(self):
        self.assertFails(self.check(self.pin(tag="rc.15-v0.21.7")), "not a final upstream tag")

    def test_image_must_match_the_tag(self):
        im = {**SEPTEMBER_PIN["image"], "ref": "docker.io/nousresearch/hermes-agent:v0.22.2"}
        self.assertFails(self.check(self.pin(image=im)), "differs from hermes.tag")

    def test_upstream_stable_label_is_not_a_pin(self):
        im = {**SEPTEMBER_PIN["image"], "ref": "docker.io/nousresearch/hermes-agent:stable"}
        self.assertFails(self.check(self.pin(image=im)), "hermes.image: ref must be")

    def test_container_installs_need_an_image(self):
        self.assertFails(self.check(self.pin(image=None)), "needs an image")

    def test_rollback_is_required_and_different(self):
        pin = self.pin()
        del pin["rollback"]
        self.assertFails(self.check(pin), "hermes.rollback: required")
        same = {"tag": SEPTEMBER_PIN["tag"], "commit": SEPTEMBER_PIN["commit"]}
        self.assertFails(self.check(self.pin(rollback=same)), "different release")

    def test_test_record_must_exist(self):
        self.assertFails(self.check(self.pin(test_record="docs/acceptance/hermes-v9.9.9.md")), "does not exist")
        self.assertFails(self.check(self.pin(test_record="trust me")), "hermes.test_record")


if __name__ == "__main__":
    unittest.main()


class ServiceRoutes(unittest.TestCase):
    """A release must not pair the shell with an Agent Service that lacks a stable route (0.3.32: /wizard/v1/setup 404)."""
    SPEC = """```routes
# methods  path                                  class     ux  query
GET        /wizard/v1/bootstrap                  stable    ux  -
GET        /wizard/v1/setup                      stable    ux  -
POST       /wizard/session-failure/{id}/dismiss  stable    ux  -
GET        /wizard/v1/wizard-apps                proposed  -   -
GET        /wizard-os-home/api/route             compat    ux  -
```"""

    def setUp(self):
        sys.path.insert(0, str(HERE.parent))
        import check_release
        self.cr = check_release

    def test_old_service_without_setup_fails(self):
        old = {"server/service.mjs": "if (url.pathname === '/wizard/v1/bootstrap') {}\n"
                                     "const m = url.pathname.match(/^\\/wizard\\/session-failure\\/([^/]+)\\/dismiss$/)"}
        self.assertEqual(self.cr.missing_service_routes(self.SPEC, old), ["GET /wizard/v1/setup"])

    def test_service_with_every_stable_route_passes(self):
        new = {"server/service.mjs": "'/wizard/v1/bootstrap' '/wizard/session-failure/'",
               "server/phone-setup.mjs": "/** GET /wizard/v1/setup */"}
        self.assertEqual(self.cr.missing_service_routes(self.SPEC, new), [])

    def test_proposed_and_non_service_routes_are_not_required(self):
        src = {"server/service.mjs": "/wizard/v1/bootstrap /wizard/v1/setup /wizard/session-failure/"}
        self.assertEqual(self.cr.missing_service_routes(self.SPEC, src), [])

    def test_real_spec_parses(self):
        spec = (ROOT / "spec" / "AGENT_SERVICE_API.md").read_text(encoding="utf-8")
        self.assertIn("GET /wizard/v1/setup", self.cr.missing_service_routes(spec, {"server/x.mjs": ""}))

    def test_gate_starts_at_0_3_33(self):
        rel = {"version": "0.3.32", "components": {"wizard-agent-service": {"repo": "x/y", "commit": "0" * 40}}}
        self.assertEqual(self.cr.service_routes_online(rel, self.SPEC), ([], []))
