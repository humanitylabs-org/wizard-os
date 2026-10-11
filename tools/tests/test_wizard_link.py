"""End-to-end tests for `wizard link / unlink / doctor` (alongside mode, spec/AGENT_BRIDGE.md).

    python3 -m unittest tools/tests/test_wizard_link.py -v

A throwaway HERMES_HOME and WIZARD_OS_HOME; a stand-in `hermes` command (a Python script, so the config editor runs
in this interpreter, which needs ruamel.yaml + PyYAML, as Hermes' own venv has) that implements only `plugins install`,
`config get` and `gateway restart`. Nothing on the box is read or written.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = HERE.parent / "wizard"

try:
    import ruamel.yaml  # noqa: F401
    import yaml  # noqa: F401
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

OWNER_CONFIG = textwrap.dedent("""\
    # The owner's config: comments, blank lines with trailing spaces and odd quoting must survive.
    model:
      default: "some/model"   # keep this comment
      provider: custom
      base_url: 'http://127.0.0.1:3301/v1'
      \n\
    mcp_servers:
      sentinel:
        url: http://127.0.0.1:9/mcp
        enabled: false
    skills:
      external_dirs:
        - ~/shared-skills
    max_concurrent_sessions: null
    agent:
      reasoning_overrides: {}
    """).replace("\\n\\\n", "\n")

FAKE_HERMES = textwrap.dedent("""\
    #!{python}
    import json, os, sys
    from pathlib import Path
    home = Path(os.environ["HERMES_HOME"])
    a = sys.argv[1:]
    log = home / "fake-hermes.log"
    with open(log, "a") as f:
        f.write(" ".join(a[:3]) + "\\n")
    if a[:2] == ["plugins", "install"]:
        d = home / "plugins" / "wizard-os"
        d.mkdir(parents=True, exist_ok=True)
        (d / "plugin.yaml").write_text("name: wizard-os\\n")
        (home / "plugins" / ".install-metadata.json").write_text(json.dumps({{"wizard-os": {{"source": a[2]}}}}))
        sys.exit(0)
    if a[:2] == ["config", "get"]:
        import yaml
        cur = yaml.safe_load((home / "config.yaml").read_text()) or {{}}
        for k in a[2].split("."):
            if not isinstance(cur, dict) or k not in cur:
                print("Config key not set: " + a[2]); sys.exit(1)
            cur = cur[k]
        print(json.dumps(cur)); sys.exit(0)
    if a[:2] == ["gateway", "restart"]:
        sys.exit(0)
    sys.exit(2)
    """)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@unittest.skipUnless(HAVE_YAML, "needs ruamel.yaml and PyYAML (both ship with Hermes)")
class LinkTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wizard-link-test-"))
        self.hh = self.dir / "hermes"
        self.wos = self.dir / "wizard-os"
        self.bin = self.dir / "bin"
        for d in (self.hh, self.wos, self.bin):
            d.mkdir()
        (self.hh / "config.yaml").write_text(OWNER_CONFIG)
        (self.hh / ".env").write_text("# owner\nOPENROUTER_API_KEY=sk-sentinel-not-real\n")
        os.chmod(self.hh / ".env", 0o600)
        (self.hh / "SOUL.md").write_text("sentinel soul\n")
        h = self.bin / "hermes"
        h.write_text(FAKE_HERMES.format(python=sys.executable))
        h.chmod(0o755)
        (self.wos / "alongside.json").write_text(json.dumps({"mode": "alongside", "shell": {"port": 18796},
                                                             "agent": {"origin": "http://127.0.0.1:1", "uid": os.getuid()}}))
        self.env = {**os.environ, "HERMES_HOME": str(self.hh), "WIZARD_OS_HOME": str(self.wos),
                    "PATH": f"{self.bin}:{os.environ.get('PATH', '')}", "HOME": str(self.dir)}
        self.before = {p: sha(self.hh / p) for p in ("config.yaml", ".env", "SOUL.md")}

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def wizard(self, *args):
        p = subprocess.run([sys.executable, str(CLI), *args, "--json"], capture_output=True, text=True,
                           env=self.env, timeout=120)
        return p.returncode, json.loads(p.stdout)

    def test_link_makes_the_three_edits_then_unlink_restores_bytes(self):
        rc, out = self.wizard("link")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out["edits"], ["mcp_servers.wizard", "skills.external_dirs", "plugins.enabled"])
        cfg_text = (self.hh / "config.yaml").read_text()
        import yaml
        cfg = yaml.safe_load(cfg_text)
        self.assertEqual(cfg["mcp_servers"]["wizard"]["url"], "http://127.0.0.1:18796/wizard/mcp")
        self.assertEqual(cfg["mcp_servers"]["wizard"]["headers"]["Authorization"], "Bearer ${WIZARD_MCP_TOKEN}")
        self.assertEqual(cfg["mcp_servers"]["sentinel"], {"url": "http://127.0.0.1:9/mcp", "enabled": False})
        self.assertEqual(cfg["skills"]["external_dirs"], ["~/shared-skills", str(self.wos / "skills")])
        self.assertEqual(cfg["plugins"]["enabled"], ["wizard-os"])
        self.assertNotIn("eager_tools", cfg_text)   # stock Hermes has no such setting; link never writes it
        # only additions: every original line is still there, in order
        orig = OWNER_CONFIG.splitlines()
        it = iter(cfg_text.splitlines())
        self.assertTrue(all(any(line == x for x in it) for line in orig), "an owner line was rewritten")
        # secrets: in the .env (0600), never in the output or the config
        token = (self.wos / "mcp-token").read_text().strip()
        self.assertNotIn(token, json.dumps(out))
        self.assertNotIn(token, cfg_text)
        env = (self.hh / ".env").read_text()
        self.assertIn(f"WIZARD_MCP_TOKEN={token}", env)
        self.assertIn("API_SERVER_KEY=", env)
        self.assertEqual(os.stat(self.hh / ".env").st_mode & 0o777, 0o600)
        rec = json.loads((self.wos / "linked.json").read_text())
        self.assertTrue(rec["linked"])
        self.assertTrue((self.hh / "plugins" / "wizard-os").is_dir())

        rc, out = self.wizard("unlink")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["config_byte_identical"])
        for p, h in self.before.items():
            self.assertEqual(sha(self.hh / p), h, f"{p} not restored byte for byte")
        self.assertFalse((self.hh / "plugins").exists())

    def test_unlink_keeps_owner_changes_made_after_link(self):
        self.assertEqual(self.wizard("link")[0], 0)
        p = self.hh / "config.yaml"
        p.write_text(p.read_text().replace('default: "some/model"', 'default: "other/model"'))
        rc, out = self.wizard("unlink")
        self.assertEqual(rc, 0, out)
        self.assertFalse(out["config_byte_identical"])
        import yaml
        cfg = yaml.safe_load(p.read_text())
        self.assertEqual(cfg["model"]["default"], "other/model")
        self.assertNotIn("wizard", cfg["mcp_servers"])
        self.assertNotIn("plugins", cfg)
        self.assertEqual(cfg["skills"]["external_dirs"], ["~/shared-skills"])

    def test_link_refuses_a_foreign_wizard_entry(self):
        p = self.hh / "config.yaml"
        p.write_text(p.read_text().replace("  sentinel:", "  wizard:\n    command: something-else\n  sentinel:"))
        before = sha(p)
        rc, out = self.wizard("link")
        self.assertNotEqual(rc, 0)
        self.assertIn("isn't Wizard OS", out["error"]["message"])
        self.assertEqual(sha(p), before)

    def test_link_leaves_the_owner_tool_search_settings_alone(self):
        p = self.hh / "config.yaml"
        owner_ts = 'tools:\n  tool_search:\n    enabled: "off"\n    defer:\n      - todo_list\n'
        p.write_text(p.read_text() + owner_ts)
        before = sha(p)
        rc, out = self.wizard("link")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out["edits"], ["mcp_servers.wizard", "skills.external_dirs", "plugins.enabled"])
        import yaml
        cfg = yaml.safe_load(p.read_text())
        self.assertEqual(cfg["tools"]["tool_search"], {"enabled": "off", "defer": ["todo_list"]})
        rc, doc = self.wizard("doctor")
        self.assertFalse(any("eager" in r["check"] for r in doc["checks"]), doc["checks"])
        rc, out = self.wizard("unlink")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["config_byte_identical"])
        self.assertEqual(sha(p), before)

    def test_link_twice_is_a_no_op(self):
        self.assertEqual(self.wizard("link")[0], 0)
        after = sha(self.hh / "config.yaml")
        rc, out = self.wizard("link")
        self.assertEqual(rc, 0)
        self.assertTrue(out["already_linked"])
        self.assertEqual(sha(self.hh / "config.yaml"), after)

    def test_doctor_reports_fail_lines_without_a_shell(self):
        self.assertEqual(self.wizard("link")[0], 0)
        rc, out = self.wizard("doctor")
        self.assertEqual(rc, 1)
        by = {r["check"]: r["ok"] for r in out["checks"]}
        self.assertTrue(by["linked (wizard link)"])
        self.assertTrue(by["Hermes has the wizard MCP server"])
        self.assertTrue(by["wizard-os plugin installed and enabled"])
        self.assertNotIn("wizard_apps eager behind Tool Search", by)   # the dropped 4th edit has no check
        self.assertFalse(by["session history readable"])   # no state.db in the throwaway home
        self.assertFalse(by["Wizard shell answers"])
        token = (self.wos / "mcp-token").read_text().strip()
        self.assertNotIn(token, json.dumps(out))


if __name__ == "__main__":
    unittest.main()
