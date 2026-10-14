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
        self.assertTrue(by["Hermes home not shared with the shell"])   # default: the shell reads chats over HTTP
        self.assertNotIn("session history readable", by)
        self.assertFalse(by["Wizard shell answers"])
        token = (self.wos / "mcp-token").read_text().strip()
        self.assertNotIn(token, json.dumps(out))

    # ---- failures part-way through link (wizard-os#28): every fault point, raised and killed

    FAULT_POINTS = [f"{w}:{k}" for k in ("mcp_servers.wizard", "skills.external_dirs", "plugin", "plugins.enabled",
                                         "env", "apikey") for w in ("before", "after")] + \
        [f"mid:{k}" for k in ("mcp_servers.wizard", "skills.external_dirs", "plugins.enabled", "env", "apikey")]

    def assert_restored(self):
        for p, h in self.before.items():
            self.assertEqual(sha(self.hh / p), h, f"{p} not restored byte for byte")
        self.assertFalse((self.hh / "plugins").exists(), "plugin left behind")
        left = sorted(x.name for x in self.hh.iterdir() if x.name != "fake-hermes.log")   # the stand-in's own log
        self.assertEqual(left, [".env", "SOUL.md", "config.yaml"])

    def test_a_failure_at_any_step_rolls_link_back(self):
        for point in self.FAULT_POINTS:
            with self.subTest(point=point):
                self.env["WIZARD_LINK_FAULT"] = point
                rc, out = self.wizard("link")
                self.assertNotEqual(rc, 0, out)
                self.assertEqual(out["error"]["stage"], "rolled_back")
                self.assertIn("injected fault", out["error"]["message"])
                self.assert_restored()
                rec = json.loads((self.wos / "linked.json").read_text())
                self.assertEqual((rec["state"], rec["linked"]), ("rolled_back", False))
                # the next, healthy link works and unlinks back to the owner's bytes
                del self.env["WIZARD_LINK_FAULT"]
                self.assertEqual(self.wizard("link")[0], 0)
                self.assertEqual(self.wizard("unlink")[0], 0)
                self.assert_restored()

    def test_a_kill_at_any_step_is_rolled_back_by_unlink(self):
        for point in self.FAULT_POINTS:
            with self.subTest(point=point):
                self.env["WIZARD_LINK_FAULT"] = point + "=kill"
                p = subprocess.run([sys.executable, str(CLI), "link", "--json"], capture_output=True, text=True,
                                   env=self.env, timeout=120)
                self.assertEqual(p.returncode, 137)
                del self.env["WIZARD_LINK_FAULT"]
                rec = json.loads((self.wos / "linked.json").read_text())
                self.assertEqual((rec["state"], rec["linked"]), ("linking", False))
                rc, doc = self.wizard("doctor")
                self.assertNotEqual(rc, 0)
                self.assertIn({"check": "no unfinished link", "ok": False,
                               "detail": "a link stopped half-way; `wizard unlink` rolls it back"}, doc["checks"])
                rc, out = self.wizard("unlink")
                self.assertEqual(rc, 0, out)
                self.assertTrue(out["recovered_unfinished_link"])
                self.assertTrue(out["config_byte_identical"] and out["env_byte_identical"], out)
                self.assert_restored()

    def test_a_kill_is_recovered_by_the_next_link(self):
        self.env["WIZARD_LINK_FAULT"] = "after:plugin=kill"
        subprocess.run([sys.executable, str(CLI), "link", "--json"], capture_output=True, env=self.env, timeout=120)
        del self.env["WIZARD_LINK_FAULT"]
        rc, out = self.wizard("link")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["recovered_unfinished_link"]["config_byte_identical"])
        self.assertEqual(out["edits"], ["mcp_servers.wizard", "skills.external_dirs", "plugins.enabled"])
        self.assertEqual(self.wizard("unlink")[0], 0)
        self.assert_restored()

    def test_a_failing_plugin_install_rolls_back(self):
        (self.bin / "hermes").write_text(FAKE_HERMES.format(python=sys.executable).replace(
            'if a[:2] == ["plugins", "install"]:', 'if a[:2] == ["plugins", "install"]:\n'
            '    (home / "plugins" / "wizard-os").mkdir(parents=True); sys.exit(1)\nif False:'))
        rc, out = self.wizard("link")
        self.assertNotEqual(rc, 0)
        self.assertEqual(out["error"]["stage"], "rolled_back")
        self.assert_restored()

    def test_kill_without_an_owner_env_file_leaves_none(self):
        (self.hh / ".env").unlink()
        del self.before[".env"]
        self.env["WIZARD_LINK_FAULT"] = "after:apikey=kill"
        subprocess.run([sys.executable, str(CLI), "link", "--json"], capture_output=True, env=self.env, timeout=120)
        del self.env["WIZARD_LINK_FAULT"]
        self.assertTrue((self.hh / ".env").exists())
        rc, out = self.wizard("unlink")
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.hh / ".env").exists())
        for p, h in self.before.items():
            self.assertEqual(sha(self.hh / p), h)

    def test_kill_mid_edit_without_an_owner_env_file_leaves_none(self):
        # killed after the .env was written but before link journalled it: the sha is unknown, so rollback removes
        # Wizard's names and must then delete the (now empty) file it created
        (self.hh / ".env").unlink()
        del self.before[".env"]
        for point in ("mid:env", "mid:apikey"):
            with self.subTest(point=point):
                self.env["WIZARD_LINK_FAULT"] = point + "=kill"
                subprocess.run([sys.executable, str(CLI), "link", "--json"], capture_output=True, env=self.env,
                               timeout=120)
                del self.env["WIZARD_LINK_FAULT"]
                rc, out = self.wizard("unlink")
                self.assertEqual(rc, 0, out)
                self.assertTrue(out["env_byte_identical"], out)
                self.assertFalse((self.hh / ".env").exists())
                for p, h in self.before.items():
                    self.assertEqual(sha(self.hh / p), h)

    def test_a_second_link_or_unlink_while_one_runs_fails_fast(self):
        import fcntl
        (self.wos / "linked.json.lock").touch()
        fd = os.open(self.wos / "linked.json.lock", os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)   # stands in for a link that is still running
        try:
            for cmd in ("link", "unlink"):
                with self.subTest(cmd=cmd):
                    rc, out = self.wizard(cmd)
                    self.assertNotEqual(rc, 0, out)
                    self.assertEqual(out["error"]["stage"], "locked")
            self.assertFalse((self.wos / "linked.json").exists())
            for p, h in self.before.items():
                self.assertEqual(sha(self.hh / p), h)
        finally:
            os.close(fd)
        self.assertEqual(self.wizard("link")[0], 0)   # once the other run ends, link works

    def test_a_failing_unlink_rollback_keeps_the_json_contract(self):
        self.env["WIZARD_LINK_FAULT"] = "after:mcp_servers.wizard=kill"
        subprocess.run([sys.executable, str(CLI), "link", "--json"], capture_output=True, env=self.env, timeout=120)
        del self.env["WIZARD_LINK_FAULT"]
        rec = json.loads((self.wos / "linked.json").read_text())
        rec["hermes_home"] = str(self.dir / "gone")   # rollback cannot work: no such Hermes home
        (self.wos / "linked.json").write_text(json.dumps(rec))
        rc, out = self.wizard("unlink")
        self.assertNotEqual(rc, 0)
        self.assertEqual(out["error"]["stage"], "rollback_incomplete")
        self.assertEqual(json.loads((self.wos / "linked.json").read_text())["state"], "linking")   # journal kept

    def test_relink_gives_hermes_the_same_api_key(self):
        # the shell captured the key at install; unlink -> link must not mint a new one it doesn't know
        self.assertEqual(self.wizard("link")[0], 0)
        key1 = [l for l in (self.hh / ".env").read_text().splitlines() if l.startswith("API_SERVER_KEY=")]
        self.assertEqual(self.wizard("unlink")[0], 0)
        self.assertNotIn("API_SERVER_KEY", (self.hh / ".env").read_text())
        self.assertEqual(self.wizard("link")[0], 0)
        key2 = [l for l in (self.hh / ".env").read_text().splitlines() if l.startswith("API_SERVER_KEY=")]
        self.assertEqual(len(key1), 1)
        self.assertEqual(key1, key2)
        self.assertEqual(os.stat(self.wos / "hermes-api-key").st_mode & 0o777, 0o600)

    def test_relink_after_an_older_link_keeps_its_api_key(self):
        # a box linked before the key file existed: unlink saves the key it removes, relink reuses it
        self.assertEqual(self.wizard("link")[0], 0)
        (self.wos / "hermes-api-key").unlink()
        key1 = [l for l in (self.hh / ".env").read_text().splitlines() if l.startswith("API_SERVER_KEY=")]
        self.assertEqual(self.wizard("unlink")[0], 0)
        self.assertEqual(self.wizard("link")[0], 0)
        key2 = [l for l in (self.hh / ".env").read_text().splitlines() if l.startswith("API_SERVER_KEY=")]
        self.assertEqual(key1, key2)

    def test_owner_edits_during_an_unfinished_link_are_kept(self):
        self.env["WIZARD_LINK_FAULT"] = "after:plugins.enabled=kill"
        subprocess.run([sys.executable, str(CLI), "link", "--json"], capture_output=True, env=self.env, timeout=120)
        del self.env["WIZARD_LINK_FAULT"]
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
        self.assertFalse((self.hh / "plugins").exists())


if __name__ == "__main__":
    unittest.main()
