"""The upgrade rig's QMP socket fits in a UNIX socket path from any workdir (forum run failed from a deep one)."""
import importlib.util
import os
from pathlib import Path

RIG = Path(__file__).resolve().parents[1] / "acceptance" / "upgrade-rig" / "kvm_upgrade.py"


def load():
    spec = importlib.util.spec_from_file_location("kvm_upgrade_paths", RIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_short_workdir_keeps_the_socket_beside_the_disk(tmp_path):
    rig = load()
    disk = tmp_path / "guest.qcow2"
    assert rig.qmp_path(disk, rig.GUEST_UNIT) == tmp_path / "guest.qmp"


def test_deep_workdir_gets_a_short_stable_socket_path():
    rig = load()
    disk = Path("/srv/work/guardian-act-upgrade-0.3.140-20261109/rig-assets/runs/20261109T124326Z-0.3.134-to-0.3.140/guest.qcow2")
    q = rig.qmp_path(disk, rig.GUEST_UNIT)
    assert len(os.fsencode(str(q))) <= rig.UNIX_PATH_MAX and q.parent == Path("/tmp")
    assert q == rig.qmp_path(disk, rig.GUEST_UNIT), "the same disk always gets the same socket"
    other = disk.with_name("other.qcow2")
    assert rig.qmp_path(other, rig.GUEST_UNIT) != q
