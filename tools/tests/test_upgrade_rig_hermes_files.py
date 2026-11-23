"""The upgrade test fails only when the OWNER's Hermes files change. WizardOS's own entries in config.yaml (its MCP
server, skills folder and plugin) may change with a release: wizard-app-manager#591 added `lazy: true` to the MCP
entry, and every For everyone promotion from 0.3.240 failed on that from 19 Nov 2026."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RIG = Path(__file__).resolve().parents[1] / "acceptance" / "upgrade-rig" / "kvm_upgrade.py"


def load():
    spec = importlib.util.spec_from_file_location("kvm_upgrade_hermes", RIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BEFORE = """model:
  default: some-model
mcp_servers:
  wizard:
    url: http://127.0.0.1:8796/wizard/mcp
    headers:
      Authorization: Bearer ${WIZARD_MCP_TOKEN}
  mine:
    url: http://example.test/mcp
skills:
  external_dirs:
  - /root/.wizard-os/system-skills
  - /root/my-skills
plugins:
  enabled:
  - wizard-os
  - my-plugin
"""


def check(before, after):
    """Run the rig's own config check script on two config files, the way the guest runs it."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        raise unittest.SkipTest("PyYAML not installed")
    rig = load()
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a.yaml", Path(d) / "b.yaml"
        a.write_text(before); b.write_text(after)
        out = subprocess.run([sys.executable, "-", str(a), str(b)], input=rig.OWNER_CONFIG_CHECK, text=True,
                             capture_output=True, check=True).stdout
    return json.loads(out)["owner_equal"]


class OwnerConfig(unittest.TestCase):
    def test_wizardos_making_its_mcp_entry_lazy_is_not_an_owner_change(self):
        after = BEFORE.replace("      Authorization: Bearer ${WIZARD_MCP_TOKEN}\n",
                               "      Authorization: Bearer ${WIZARD_MCP_TOKEN}\n    lazy: true\n")
        self.assertTrue(check(BEFORE, after))

    def test_wizardos_skills_folder_and_plugin_are_its_own(self):
        after = BEFORE.replace("  - /root/.wizard-os/system-skills\n", "").replace("  - wizard-os\n", "")
        self.assertTrue(check(BEFORE, after))

    def test_any_owner_setting_that_changes_fails(self):
        for old, new in (("default: some-model", "default: other-model"),
                         ("url: http://example.test/mcp", "url: http://example.test/other"),
                         ("  - /root/my-skills\n", ""), ("  - my-plugin\n", "")):
            self.assertFalse(check(BEFORE, BEFORE.replace(old, new)), old)

    def test_owner_changed_counts_env_and_soul_always_and_config_only_beyond_wizardos(self):
        rig = load()
        b = {"config.yaml": "1", ".env": "e", "SOUL.md": "s"}
        with mock.patch.object(rig, "config_owner_equal", return_value=True):
            self.assertEqual(rig.owner_changed(b, {**b, "config.yaml": "2"}), [])
            self.assertEqual(rig.owner_changed(b, {**b, "config.yaml": "2", ".env": "f"}), [".env"])
        with mock.patch.object(rig, "config_owner_equal", return_value=False):
            self.assertEqual(rig.owner_changed(b, {**b, "config.yaml": "2"}), ["config.yaml"])

    def test_an_unreadable_check_fails_closed(self):
        rig = load()
        with mock.patch.object(rig, "guest", return_value="Traceback: no module named yaml\n"):
            self.assertFalse(rig.config_owner_equal())

    def test_the_diff_never_reads_env(self):
        rig = load()
        calls = []
        with mock.patch.object(rig, "guest", lambda cmd, check=True, timeout=600: calls.append(cmd) or "+    lazy: true\n"):
            d = rig.hermes_diff({"config.yaml": "1", ".env": "e"}, {"config.yaml": "2", ".env": "f"})
        self.assertEqual(d[".env"], "(changed; content not shown)")
        self.assertTrue(all(".env" not in c for c in calls))

    def test_report_says_only_wizardos_entries_changed(self):
        rig = load()
        r = {"from": "1", "to": "2", "passed": True, "started_at": "a", "finished_at": "b", "golden": {},
             "before": {"files": {"config.yaml": "1"}}, "after": {"files": {"config.yaml": "2"}},
             "hermes_owner_changed": [], "hermes_diff": {"config.yaml": "+    lazy: true"}}
        md = rig.markdown(r)
        self.assertIn("only WizardOS's own entries in config.yaml changed", md)
        self.assertIn("+    lazy: true", md)


if __name__ == "__main__":
    unittest.main()
