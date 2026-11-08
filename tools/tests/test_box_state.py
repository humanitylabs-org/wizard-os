"""Every state place MAINTENANCE.md names has a row in BOX_STATE.md (wizard-os#425)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / 'spec'

# Paths a contract reads but the box never writes: not box state.
READ_ONLY_INPUTS = {'/etc/os-release'}

HELPER_ARGV = ['check', 'check --refresh', 'apply', 'native-off', 'native-on', 'restart-check', 'remove']
LANE_ARGV = ['restart-service *', 'apply-held', 'reboot']


def named_paths(text: str) -> set[str]:
    """Backticked absolute or home paths, e.g. `/etc/sudoers.d/x` or `~/.wizard-os/x`."""
    return set(re.findall(r'`([/~][^`\s]*)`', text)) - READ_ONLY_INPUTS


def listed(path: str, inventory: str) -> bool:
    if path in inventory:
        return True
    parent, _, name = path.rpartition('/')
    return f'{parent}/' in inventory and name in inventory


class BoxStateTest(unittest.TestCase):
    def setUp(self):
        self.inventory = (SPEC / 'BOX_STATE.md').read_text()
        self.maintenance = (SPEC / 'MAINTENANCE.md').read_text()

    def test_every_maintenance_state_path_has_a_row(self):
        paths = named_paths(self.maintenance)
        self.assertIn('/usr/local/libexec/wizard-os/os-patch', paths)
        for path in sorted(paths):
            with self.subTest(path=path):
                self.assertTrue(listed(path, self.inventory), f'{path} is named in MAINTENANCE.md, not in BOX_STATE.md')

    def test_helper_removed_restore_rule_is_marked(self):
        self.assertIn('helper_removed', self.inventory)
        self.assertRegex(self.inventory, r'(?m)^### (Open|Decided): `helper_removed` on restore$')

    def test_maintenance_lists_the_sudoers_argument_lists(self):
        privilege = self.maintenance.split('## Privilege', 1)[1].split('\n## ', 1)[0]
        self.assertEqual(len(HELPER_ARGV), 7)
        self.assertIn('exactly seven argument lists', privilege)
        for argv in HELPER_ARGV + LANE_ARGV:
            with self.subTest(argv=argv):
                self.assertIn(f'`{argv}`', privilege)


if __name__ == '__main__':
    unittest.main()
