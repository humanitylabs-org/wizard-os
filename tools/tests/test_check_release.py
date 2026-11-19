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
        files = sorted(p for p in (ROOT / "releases").glob("*.json") if p.name != 'hermes-lock.json')
        files += sorted((ROOT / "releases" / "candidates").glob("*.json"))
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


FORK_COMMIT = "c1d1d6fefdf2f43f83960ea4280455e5f626f3d8"   # defleur-agents/hermes-agent main, 18 Nov 2026
FORK_PIN = {
    "tag": "v0.22.7",
    "commit": "b200f5bc60e31588ba2cb60e288029c4a54ba5fa",
    "fork": {"repo": "defleur-agents/hermes-agent", "branch": "main", "tag": f"sha-{FORK_COMMIT}",
             "commit": FORK_COMMIT},
    "image": {"ref": f"ghcr.io/defleur-agents/hermes-agent:sha-{FORK_COMMIT}", "digest": "sha256:" + "ab" * 32,
              "commit": FORK_COMMIT, "architectures": ["amd64", "arm64"],
              "ci_run": "https://github.com/defleur-agents/hermes-agent/actions/runs/1"},
    "test_record": "https://github.com/humanitylabs-org/wizard-os/issues/692",
    "rollback": {k: SEPTEMBER_PIN[k] for k in ("tag", "commit", "image")},
}


class HermesForkCandidate(unittest.TestCase):
    """wizard-os#723: a candidate snapshot may pin the fork image; latest/stable and the frozen lock stay as they are."""

    def check(self, hermes=None, channel="candidate", version="0.3.289-hermes-fork.1", where=None):
        rel = json.loads((ROOT / "releases" / "0.3.289.json").read_text())
        rel["version"] = version
        rel["hermes"] = json.loads(json.dumps(FORK_PIN if hermes is None else hermes))
        if channel is not None:
            rel["channel"] = channel
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, dir=where) as f:
            json.dump(rel, f)
        try:
            return run(f.name, "--offline")
        finally:
            Path(f.name).unlink()

    def pin(self, **changes):
        pin = json.loads(json.dumps(FORK_PIN))
        for key, value in changes.items():
            part, _, field = key.partition("__")
            if field:
                pin[part][field] = value
            else:
                pin[part] = value
        return pin

    def assertFails(self, p, words):
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn(words, p.stdout)

    def test_fork_candidate_passes(self):
        p = self.check()
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_fork_pin_outside_a_candidate_hits_the_frozen_lock(self):
        self.assertFails(self.check(channel=None, version="0.3.290"), "Hermes is frozen")

    def test_unknown_channel_is_refused(self):
        self.assertFails(self.check(channel="beta"), "only \"candidate\" is a channel")

    def test_candidate_needs_a_prerelease_version(self):
        self.assertFails(self.check(version="0.3.290"), "pre-release suffix")

    def test_candidate_never_sits_beside_the_releases(self):
        self.assertFails(self.check(where=ROOT / "releases"), "releases/candidates/")

    def test_latest_or_stable_never_names_a_candidate(self):
        latest = (ROOT / "releases" / "latest").read_text().strip()
        self.assertFails(self.check(version=latest), "releases/latest names candidate")

    def test_image_must_be_the_forks_own_ghcr_image(self):
        self.assertFails(self.check(self.pin(image__ref="docker.io/nousresearch/hermes-agent:v0.22.7")),
                         "ghcr.io/<fork owner>/hermes-agent")
        self.assertFails(self.check(self.pin(image__ref=f"ghcr.io/someone/hermes-agent:sha-{FORK_COMMIT}")),
                         "not the fork's owner")
        self.assertFails(self.check(self.pin(image__ref="ghcr.io/defleur-agents/hermes-agent:latest")),
                         "differs from hermes.fork.tag")

    def test_image_commit_is_the_fork_commit(self):
        self.assertFails(self.check(self.pin(image__commit=FORK_PIN["commit"])), "must equal hermes.fork.commit")

    def test_both_architectures_and_a_digest(self):
        self.assertFails(self.check(self.pin(image__architectures=["amd64"])), "amd64 and arm64")
        self.assertFails(self.check(self.pin(image__digest="sha256:short")), "digest is not")

    def test_fork_pin_needs_a_real_test_record(self):
        self.assertFails(self.check(self.pin(test_record="none: not tested yet")), "needs a real test record")

    def test_fork_fields_are_required(self):
        self.assertFails(self.check(self.pin(fork__commit="main")), "hermes.fork: commit")
        self.assertFails(self.check(self.pin(fork__repo="hermes")), "hermes.fork: repo")

    def test_rollback_to_the_same_fork_commit_is_refused(self):
        same = {"tag": FORK_PIN["tag"], "commit": FORK_PIN["commit"], "fork": FORK_PIN["fork"]}
        self.assertFails(self.check(self.pin(rollback=same)), "different release")
        older = {**same, "fork": {**FORK_PIN["fork"], "commit": "1" * 40}}
        self.assertEqual(self.check(self.pin(rollback=older)).returncode, 0)

    def test_candidate_writer_makes_a_passing_snapshot_and_moves_no_pointer(self):
        before = {n: (ROOT / "releases" / n).read_text() for n in ("latest", "stable")}
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, str(HERE.parent / "hermes_fork_candidate.py"),
                                "--base-commit", FORK_PIN["commit"], "--fork-commit", FORK_COMMIT,
                                "--digest", FORK_PIN["image"]["digest"], "--ci-run", FORK_PIN["image"]["ci_run"],
                                "--test-record", FORK_PIN["test_record"], "--out-dir", d],
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            out = Path(p.stdout.strip())
            rel = json.loads(out.read_text())
            self.assertEqual(rel["channel"], "candidate")
            self.assertEqual(rel["hermes"]["fork"]["commit"], FORK_COMMIT)
            self.assertEqual(rel["hermes"]["rollback"]["image"], SEPTEMBER_PIN["image"])
            self.assertEqual(run(str(out), "--offline").returncode, 0)
        self.assertEqual(before, {n: (ROOT / "releases" / n).read_text() for n in ("latest", "stable")})


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
