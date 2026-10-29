"""The spec checker accepts the same offline needs vocabulary as WAM."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('needs_checker', ROOT / 'tools/check_wizard_md.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

class NeedsCapabilities(unittest.TestCase):
    def verdict(self, needs, provides=None):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'app'
            shutil.copytree(ROOT / 'examples/defleur-video', dest)
            manifest = dest / 'wizard.md'
            text = manifest.read_text()
            # YAML's last mapping key wins; avoid changing the original fixture.
            end = text.index('\n---', 4)
            extra = '\nneeds: ' + json.dumps(needs)
            if provides is not None:
                extra += '\nprovides: ' + json.dumps(provides)
            manifest.write_text(text[:end] + extra + text[end:])
            return next(ok for name, ok, detail in checker.check(dest) if name == 'needs known')

    def test_capabilities_app_ids_and_permissions(self):
        for need in ('speech-to-text-engine', 'connection-router', 'wizard-voice-service', 'home-network', 'credentials:test'):
            with self.subTest(need=need):
                self.assertTrue(self.verdict([need]))

    def test_aliases_null_slots_and_self_declarations_do_not_grant_vocabulary(self):
        for need in ('accounts', 'agent-history', 'wizard-agent-history', 'invented-engine'):
            with self.subTest(need=need):
                self.assertFalse(self.verdict([need], [need]))

    def test_optional_sibling_wam_parity(self):
        path = ROOT.parent / 'wizard-app-manager/wam/wizardmd.py'
        if not path.exists():
            self.skipTest('no sibling WAM checkout')
        spec = importlib.util.spec_from_file_location('wam_needs', path)
        wam = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wam)
        self.assertEqual(checker.known_dependencies(), wam.known_dependencies())
