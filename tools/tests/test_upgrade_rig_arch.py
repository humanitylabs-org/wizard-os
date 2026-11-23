"""The upgrade rig runs an arm64 guest (what Wizard for Mac's WizardOS VM runs) as well as amd64, without changing
the amd64 KVM command the release train already uses."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RIG = Path(__file__).resolve().parents[1] / "acceptance" / "upgrade-rig" / "kvm_upgrade.py"


def load():
    spec = importlib.util.spec_from_file_location("kvm_upgrade_arch", RIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class UpgradeRigArch(unittest.TestCase):
    def setUp(self):
        self.rig = load()
        self.tmp = Path(tempfile.mkdtemp())
        self.disk = self.tmp / "guest.qcow2"
        self.qmp = self.tmp / "guest.qmp"

    def test_amd64_kvm_command_is_unchanged(self):
        rig = self.rig
        with mock.patch.object(rig.shutil, "which", lambda b: f"/usr/bin/{b}"):
            cmd = rig.qemu_argv(self.disk, self.qmp, None, "amd64", "kvm")
        self.assertEqual(cmd, [
            "/usr/bin/qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-smp", rig.GUEST_SMP, "-m", rig.GUEST_MEM_MB,
            "-drive", f"file={self.disk},if=virtio",
            "-netdev", f"user,id=n0,hostfwd=tcp:127.0.0.1:{rig.SSH_PORT}-:22,hostfwd=tcp:127.0.0.1:{rig.SHELL_PORT}-:8796",
            "-device", "virtio-net-pci,netdev=n0", "-display", "none", "-serial", f"file:{self.disk.with_suffix('.console')}",
            "-qmp", f"unix:{self.qmp},server,nowait"])

    def test_arm64_guest_is_a_virt_machine_with_uefi_and_the_seed_before_the_network(self):
        rig = self.rig
        fw = self.tmp / "edk2-aarch64-code.fd"
        fw.write_bytes(b"x")
        seed = self.tmp / "seed.iso"
        with mock.patch.dict(os.environ, {"WIZARD_RIG_FIRMWARE": str(fw)}), \
                mock.patch.object(rig.shutil, "which", lambda b: f"/opt/bin/{b}"):
            cmd = rig.qemu_argv(self.disk, self.qmp, seed, "arm64", "hvf")
        self.assertEqual(cmd[:10], ["/opt/bin/qemu-system-aarch64", "-machine", "virt", "-accel", "hvf", "-cpu", "host",
                                    "-bios", str(fw), "-smp"])
        self.assertLess(cmd.index(f"file={seed},if=virtio,format=raw"), cmd.index("-netdev"))
        self.assertIn("virtio-net-pci,netdev=n0", cmd)

    def test_arm64_without_firmware_says_what_to_install(self):
        rig = self.rig
        with mock.patch.object(rig, "AARCH64_FIRMWARE", ()), mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WIZARD_RIG_FIRMWARE", None)
            with self.assertRaises(SystemExit) as e:
                rig.firmware()
        self.assertIn("qemu-efi-aarch64", str(e.exception))

    def test_a_guest_of_another_architecture_is_refused_not_emulated(self):
        rig = self.rig
        with mock.patch.object(rig, "host_arch", lambda: "amd64"):
            with self.assertRaises(SystemExit) as e:
                rig.accel("arm64")
        self.assertIn("arm64 host", str(e.exception))

    def test_amd64_assets_keep_their_names_and_arm64_gets_its_own(self):
        rig = self.rig
        self.assertEqual(rig.asset("golden.qcow2", "amd64"), rig.ASSETS / "golden.qcow2")
        self.assertEqual(rig.asset("noble-base.img", "arm64"), rig.ASSETS / "noble-base-arm64.img")
        self.assertEqual(rig.asset("golden.json", "arm64"), rig.ASSETS / "golden-arm64.json")
        self.assertTrue(rig.BASE_URLS["arm64"].endswith("noble-server-cloudimg-arm64.img"))

    def test_seed_iso_without_cloud_localds_uses_hdiutil_with_the_nocloud_label(self):
        rig = self.rig
        ud, md = self.tmp / "s.user-data", self.tmp / "s.meta-data"
        ud.write_text("#cloud-config\n"); md.write_text("instance-id: x\n")
        with mock.patch.object(rig.shutil, "which", lambda b: "/usr/bin/hdiutil" if b == "hdiutil" else None):
            cmd = rig.seed_cmd(self.tmp / "s.iso", ud, md)
        self.assertEqual(cmd[:2], ["hdiutil", "makehybrid"])
        self.assertIn("cidata", cmd)
        src = Path(cmd[-1])
        self.assertEqual(sorted(p.name for p in src.iterdir()), ["meta-data", "user-data"])

    def test_report_names_the_architecture_and_no_host_name(self):
        rig = self.rig
        r = {"from": "0.3.1", "to": "0.3.2", "arch": "arm64", "accel": "hvf", "host": "a Mac (Apple silicon)",
             "passed": True, "started_at": "a", "finished_at": "b", "golden": {"hermes": "Hermes v1"}}
        md = rig.markdown(r)
        self.assertIn("disposable HVF guest (arm64)", md)
        self.assertIn("a Mac (Apple silicon)", md)
        self.assertNotIn("oscar-main", md)

    def test_a_rerun_of_the_starting_install_is_disclosed_and_the_upgrade_is_never_retried(self):
        rig = self.rig
        r = {"from": "0.3.1", "to": "0.3.2", "arch": "arm64", "accel": "hvf", "passed": True, "started_at": "a",
             "finished_at": "b", "golden": {}, "install_from_first": {"failure_reason": "wam recover failed"},
             "install_from": {"state": "done", "rerun": True}}
        self.assertIn("first ended **failed** (wam recover failed)", rig.markdown(r))
        src = RIG.read_text()
        i = src.index("if st.get(\"state\") == \"failed\" and retry_from")
        self.assertLess(i, src.index("st, secs = install(to,"), "only the starting install is re-run")

    def test_a_changed_hermes_file_is_shown_as_a_diff_but_env_never(self):
        rig = self.rig
        calls = []
        with mock.patch.object(rig, "guest", lambda cmd, check=True, timeout=600: calls.append(cmd) or "-a: 1\n+a: 2\n"):
            d = rig.hermes_diff({"config.yaml": "x", ".env": "e", "SOUL.md": "s"},
                                {"config.yaml": "y", ".env": "f", "SOUL.md": "s"})
        self.assertEqual(d[".env"], "(changed; content not shown)")
        self.assertIn("+a: 2", d["config.yaml"])
        self.assertNotIn("SOUL.md", d)
        self.assertTrue(all(".env" not in c for c in calls))
        md = rig.markdown({"from": "1", "to": "2", "passed": False, "hermes_diff": d, "started_at": "a", "finished_at": "b"})
        self.assertIn("Hermes config.yaml: what the upgrade changed", md)


if __name__ == "__main__":
    unittest.main()
