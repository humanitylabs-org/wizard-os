"""The upgrade rig fails an upgrade that leaves the nightly maintenance helper stale (wizard-os#594)."""
import importlib.util
import unittest
from pathlib import Path

RIG = Path(__file__).resolve().parents[1] / "acceptance" / "upgrade-rig" / "kvm_upgrade.py"


def load():
    spec = importlib.util.spec_from_file_location("kvm_upgrade_helper", RIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def status(helper, removed=None):
    s = {"os_security": "check"}
    if removed is not None:
        s["helper_removed"] = removed
    return {"settings": s, "helper": helper, "health": []}


class UpgradeRigHelper(unittest.TestCase):
    def test_report_reads_wam_maintain_status(self):
        rig = load()
        assert rig.helper_report(status("ready"), True) == "ready"
        assert rig.helper_report(status("root"), False) == "root"
        assert rig.helper_report(status("stale"), True) == "stale"
        assert rig.helper_report(status("missing", True), False) == "removed_by_owner"
        assert rig.helper_report(status("root", True), False) == "removed_by_owner", "root box: no helper file is the proof"
        assert rig.helper_report(status("ready", True), True) == "needs_choice"
        assert rig.helper_report(None, False) == "unknown"
        assert rig.helper_report({"error": "x"}, False) == "unknown"

    def test_upgrade_passes_only_with_a_current_helper(self):
        rig = load()
        assert rig.helper_problems("ready", False) == []
        assert rig.helper_problems("root", False) == []
        for bad in ("stale", "unsafe", "missing", "unknown", "needs_choice", "removed_by_owner"):
            assert rig.helper_problems(bad, False), bad

    def test_owner_removal_must_survive_the_upgrade(self):
        rig = load()
        assert rig.helper_problems("removed_by_owner", True) == []
        for bad in ("ready", "root", "needs_choice", "stale", "unknown"):
            assert rig.helper_problems(bad, True), bad

    def test_snapshot_and_run_check_the_helper(self):
        src = RIG.read_text()
        assert 'snap["maintenance_helper"] = maintenance_helper()' in src
        assert "helper_problems((after.get(\"maintenance_helper\")" in src
        assert "--helper-removed" in src and "wam maintain remove" in src


if __name__ == "__main__":
    unittest.main()
