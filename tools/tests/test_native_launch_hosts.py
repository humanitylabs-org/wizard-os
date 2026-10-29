"""Native host selection must not weaken guest acceptance assertions."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

class NativeHosts(unittest.TestCase):
    def gate(self):
        launch = load('run', 'tools/acceptance/launch/run.py')
        with patch.dict(sys.modules, {'run': launch}):
            return load('gate', 'tools/acceptance/launch/release_gate.py')

    def test_linux_uses_native_amd64_with_pinned_image_and_9p(self):
        gate = self.gate()
        with patch.object(gate.platform, 'system', return_value='Linux'), patch.object(gate.platform, 'machine', return_value='x86_64'):
            cfg = gate.native_vm_config()
        self.assertEqual((cfg['vmType'], cfg['arch'], cfg['mountType']), ('qemu', 'x86_64', '9p'))
        self.assertEqual(cfg['images'][0]['digest'], 'sha256:04e8f2461a16a44e78a370284471f29616cdd9baf1893df25807b71f985b6c94')
        self.assertTrue(cfg['images'][0]['location'].endswith('amd64.img'))

    def test_mac_arm_keeps_native_vz(self):
        gate = self.gate()
        with patch.object(gate.platform, 'system', return_value='Darwin'), patch.object(gate.platform, 'machine', return_value='arm64'):
            cfg = gate.native_vm_config()
        self.assertEqual((cfg['vmType'], cfg['arch']), ('vz', 'aarch64'))
        self.assertNotIn('mountType', cfg)
        self.assertEqual(cfg['images'][0]['digest'], 'sha256:50e24e1fb79e89116e939d90aa7738f7af48c442fa1bc2510131e0b39c50348e')

    def test_unsupported_host_refuses_emulation(self):
        gate = self.gate()
        with patch.object(gate.platform, 'system', return_value='Darwin'), patch.object(gate.platform, 'machine', return_value='x86_64'):
            with self.assertRaisesRegex(RuntimeError, 'unsupported native'):
                gate.native_vm_config()

    def test_repair_linux_pins_match_generated_guest(self):
        with patch('platform.system', return_value='Linux'), patch('platform.machine', return_value='x86_64'):
            drill = load('drill', 'tools/acceptance/repair/drill.py')
        obj = object.__new__(drill.Drill)
        config = obj.vm_yaml(Path('/work/image.img'))
        self.assertIn('vmType: qemu\narch: x86_64', config)
        self.assertIn('digest: sha256:5fa5b05e5ec239858c4531485d6023b0896448c2df7c63b34f8dae6ea6051a44', config)
        for ip in ('127.0.0.1', '0.0.0.0'):
            self.assertIn('guestIP: ' + ip, config)

if __name__ == '__main__':
    unittest.main()
