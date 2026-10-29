#!/usr/bin/env python3
"""The broken-box drill only uses commands the repair kit actually tells people to run."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DRILL = ROOT / "tools/acceptance/repair/drill.py"
KIT = ROOT / "docs/REPAIR_KIT.md"


def load():
    spec = importlib.util.spec_from_file_location("repair_drill", DRILL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RepairDrillTests(unittest.TestCase):
    def test_recipes_are_verbatim_in_the_kit(self):
        kit = KIT.read_text()
        mod = load()
        for name in [n for n in dir(mod) if n.startswith("RECIPE_")] + ["DOCTOR"]:
            with self.subTest(name=name):
                self.assertIn(getattr(mod, name), kit)

    def test_dry_run_plans_every_drill_and_touches_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            lane, out = pathlib.Path(d) / "lane", pathlib.Path(d) / "plan.json"
            env = dict(os.environ, DRILL_PLAN_OUT=str(out))
            subprocess.run([sys.executable, str(DRILL), str(lane), "t1", "--dry-run"], check=True, env=env,
                           capture_output=True)
            self.assertFalse(lane.exists(), "a dry run must not create the lane")
            plan = json.loads(out.read_text())
            steps = [s["step"] for s in plan["plan"]]
            baseline = next(s for s in plan["plan"] if s["step"] == "baseline-healthy")
            self.assertTrue(baseline["required"], "never inject failures on an already-broken baseline")
            for key in ("C-shell-down", "F-hermes-down", "E-app-screen", "A-stuck-installing"):
                for phase in ("1-inject", "2-broken", "3-repair", "4-recovered"):
                    self.assertIn(f"{key}-{phase}", steps)
            self.assertTrue(plan["vm"].startswith("l8-repair-"))
            text = json.dumps(plan)
            for bad in ("api-token", "mcp-token", "auth.json", "/secrets/", "credentials"):
                self.assertNotIn(bad, text, "the drill must never touch sign-in material")

    def owner_probe(self, apps, command):
        with tempfile.TemporaryDirectory() as d:
            home = pathlib.Path(d)
            (home / ".wizard-os").mkdir()
            (home / ".wizard-os/apps.json").write_text(json.dumps({"schema": 2, "apps": apps}))
            return subprocess.run(["bash", "-c", load().OWNER_PRELUDE + command],
                                  env=dict(os.environ, HOME=d), capture_output=True, text=True)

    def test_files_without_declared_health_uses_prefixed_engine_probe(self):
        # 0.3.32 pins oscarhenrycollins/files@8a4dd8a: no wizard.md health;
        # registry.build supplies mcp.url, and the engine checks /files/health.
        row = {"id": "files", "health": None, "view": {"url": "/files/"},
               "mcp": {"url": "http://127.0.0.1:8794/mcp"}}
        for field in (None, "absent"):
            with self.subTest(health=field):
                if field == "absent":
                    row.pop("health")
                p = self.owner_probe([row], "health_url files")
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout.strip(), "http://127.0.0.1:8794/files/health")

    def test_declared_health_is_preserved_and_missing_probe_is_an_error(self):
        p = self.owner_probe([{"id": "files", "health": "http://127.0.0.1:9876/custom-health",
                               "mcp": {"url": "http://127.0.0.1:8794/mcp"}}], "health_url files")
        self.assertEqual(p.stdout.strip(), "http://127.0.0.1:9876/custom-health")
        for row in ({"id": "files", "health": None},
                    {"id": "unknown", "mcp": {"url": "http://127.0.0.1:9876/mcp"}}):
            with self.subTest(row=row):
                p = self.owner_probe([row], "health_url " + row["id"])
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("no health URL", p.stderr)

    def test_files_probe_checks_backend_not_just_mcp_front(self):
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            backend_up = True
            paths = []

            def do_GET(self):
                self.paths.append(self.path)
                self.send_response(200 if self.path == "/files/health" and self.backend_up else 502)
                self.end_headers()

            def log_message(self, format, *args):
                pass

        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                row = {"id": "files", "health": None,
                       "mcp": {"url": f"http://127.0.0.1:{server.server_port}/mcp"}}
                p = self.owner_probe([row], "healthy files")
                self.assertEqual(p.returncode, 0, p.stderr)
                Handler.backend_up = False
                p = self.owner_probe([row], "healthy files")
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(Handler.paths, ["/files/health", "/files/health"])
            finally:
                server.shutdown()
                thread.join()

    def test_kit_links_resolve(self):
        import re
        for doc in (KIT, ROOT / "tools/repair/REPAIR_PROMPT.md", DRILL.parent / "README.md"):
            for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", doc.read_text()):
                with self.subTest(doc=doc.name, target=target):
                    self.assertTrue((doc.parent / target).resolve().exists(), target)


if __name__ == "__main__":
    unittest.main()
