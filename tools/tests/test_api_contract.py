"""Tests for tools/check_api_contract.py: a synthetic Wizard UX tree, no network.

    python3 -m pytest -q tools/tests/test_api_contract.py     (or: python3 -m unittest tools/tests/test_api_contract.py)

The negative controls prove the checker fails on an undocumented route, a wrong method, a query key outside the
allowlist, a proposed-only route and a stale `ux` mark, so its pass on the real UX is meaningful.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))
import check_api_contract as cac  # noqa: E402

SPEC = (TOOLS.parent / "spec" / "AGENT_SERVICE_API.md").read_text(encoding="utf-8")

MINI_SPEC = """# test
```routes
GET        /wizard/v1/bootstrap                       stable       ux  -
GET,PUT    /wizard/thread-seen                        stable       ux  -
GET        /wizard/hermes/api/sessions                passthrough  ux  limit,offset
POST       /wizard/hermes/v1/runs/{id}/steer          passthrough  ux  -
GET        /wizard/v1/wizard-apps                     proposed     -   -
```
"""

GOOD_JS = """
const a = await fetch('/wizard/v1/bootstrap', { cache: 'no-store' });
const b = await req('/wizard/thread-seen');
const c = await req('/wizard/thread-seen', { method: 'PUT', headers: J, body });
const d = await req(`/wizard/hermes/api/sessions?limit=100&offset=${o}`);
await req(`/wizard/hermes/v1/runs/${encodeURIComponent(id)}/steer`, { method: 'POST', headers: J, body });
"""


def ux_tree(js: str, java: str = "") -> Path:
    root = Path(tempfile.mkdtemp(prefix="wux-"))
    (root / "web/core").mkdir(parents=True)
    (root / "web/core/live.js").write_text(js, encoding="utf-8")
    if java:
        d = root / "android/app/src/main/java/x"
        d.mkdir(parents=True)
        (d / "Outbox.java").write_text(java, encoding="utf-8")
    return root


class ParseTests(unittest.TestCase):
    def test_spec_route_block_parses_and_is_unique(self):
        routes = cac.parse_routes(SPEC)
        keys = [(r["method"], r["path"]) for r in routes]
        self.assertEqual(len(keys), len(set(keys)), "duplicate route in spec")
        self.assertTrue({r["cls"] for r in routes} <= {"stable", "passthrough", "compat", "box", "page", "proposed", "gap"})
        self.assertIn(("GET", "/wizard/v1/bootstrap"), keys)
        self.assertEqual(cac.bootstrap_endpoints(SPEC)["runs"], "/wizard/hermes/v1/runs")

    def test_proposed_routes_are_pr7_only(self):
        proposed = {r["path"] for r in cac.parse_routes(SPEC) if r["cls"] == "proposed"}
        self.assertEqual(proposed, {"/wizard/v1/wizard-apps", "/wizard/v1/index/search", "/wizard/v1/index/tags", "/wizard/v1/index/apps/{owner}/{repo}"})

    def test_normalise(self):
        self.assertEqual(cac.normalise("/wizard/files/${encodeURIComponent(id)}/content"), ("/wizard/files/{x}/content", []))
        self.assertEqual(cac.normalise("/wizard/hermes/api/sessions?limit=100&offset=${o}"), ("/wizard/hermes/api/sessions", ["limit", "offset"]))
        self.assertEqual(cac.normalise("/wizard/hermes/v1/runs/"), ("/wizard/hermes/v1/runs/{x}", []))


class CheckTests(unittest.TestCase):
    def test_good_tree_passes(self):
        r = cac.check(derive=False, ux=ux_tree(GOOD_JS), spec_text=MINI_SPEC)
        self.assertTrue(r["ok"], r["problems"])
        self.assertEqual(r["mapped"], 5)

    def test_negative_undocumented_route_fails(self):
        r = cac.check(derive=False, ux=ux_tree(GOOD_JS + "await fetch('/wizard/v1/does-not-exist');\n"), spec_text=MINI_SPEC)
        self.assertFalse(r["ok"])
        self.assertTrue(any(p.startswith("undocumented: GET /wizard/v1/does-not-exist") for p in r["problems"]), r["problems"])

    def test_negative_wrong_method_fails(self):
        r = cac.check(derive=False, ux=ux_tree(GOOD_JS + "await req('/wizard/thread-seen', { method: 'DELETE' });\n"), spec_text=MINI_SPEC)
        self.assertTrue(any("undocumented: DELETE /wizard/thread-seen" in p for p in r["problems"]), r["problems"])

    def test_negative_query_key_outside_allowlist_fails(self):
        r = cac.check(derive=False, ux=ux_tree(GOOD_JS + "await req('/wizard/hermes/api/sessions?evil=1');\n"), spec_text=MINI_SPEC)
        self.assertTrue(any("query keys ['evil']" in p for p in r["problems"]), r["problems"])

    def test_negative_proposed_route_does_not_count(self):
        r = cac.check(derive=False, ux=ux_tree(GOOD_JS + "await fetch('/wizard/v1/wizard-apps');\n"), spec_text=MINI_SPEC)
        self.assertTrue(any(p.startswith("proposed-only route") for p in r["problems"]), r["problems"])

    def test_negative_stale_ux_mark_fails(self):
        r = cac.check(derive=False, ux=ux_tree("const a = await fetch('/wizard/v1/bootstrap');\n"), spec_text=MINI_SPEC)
        self.assertTrue(any("stale ux mark: PUT /wizard/thread-seen" in p for p in r["problems"]), r["problems"])

    def test_java_method_and_concatenated_id(self):
        java = 'r = request("POST", "/wizard/hermes/v1/runs/" + URLEncoder.encode(id, "UTF-8") + "/steer", body);\n'
        found = cac.scan(ux_tree("", java))
        self.assertIn(("POST", "/wizard/hermes/v1/runs/{x}"), [(f["method"], f["path"]) for f in found])


class DerivationTests(unittest.TestCase):
    def test_negative_missing_derivation_anchor_is_reported(self):
        r = cac.check(ux_tree(GOOD_JS), MINI_SPEC)
        self.assertFalse(r["ok"])
        self.assertTrue(any("derivation anchor not found" in p for p in r["problems"]), r["problems"])


class RealUxTest(unittest.TestCase):
    """Runs the CLI against a real wizard-ux checkout when one sits next to this repo (as in CI with both cloned)."""

    def test_cli_on_sibling_checkout(self):
        ux = TOOLS.parent.parent / "wizard-ux"
        if not (ux / "web").is_dir():
            self.skipTest("no ../wizard-ux checkout")
        p = subprocess.run([sys.executable, str(TOOLS / "check_api_contract.py"), "--ux", str(ux)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("COMPATIBLE", p.stdout)


if __name__ == "__main__":
    unittest.main()
