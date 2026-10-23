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
            for key in ("C-shell-down", "F-hermes-down", "E-app-screen", "A-stuck-installing"):
                for phase in ("1-inject", "2-broken", "3-repair", "4-recovered"):
                    self.assertIn(f"{key}-{phase}", steps)
            self.assertTrue(plan["vm"].startswith("l8-repair-"))
            text = json.dumps(plan)
            for bad in ("api-token", "mcp-token", "auth.json", "/secrets/", "credentials"):
                self.assertNotIn(bad, text, "the drill must never touch sign-in material")

    def test_kit_links_resolve(self):
        import re
        for doc in (KIT, ROOT / "tools/repair/REPAIR_PROMPT.md", DRILL.parent / "README.md"):
            for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", doc.read_text()):
                with self.subTest(doc=doc.name, target=target):
                    self.assertTrue((doc.parent / target).resolve().exists(), target)


if __name__ == "__main__":
    unittest.main()
