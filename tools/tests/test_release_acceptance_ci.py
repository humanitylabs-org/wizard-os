import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('accept_ci', ROOT / 'tools/acceptance/launch/ci.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class ReleaseAcceptanceCITests(unittest.TestCase):
    def test_manual_main_only_no_arbitrary_command(self):
        workflow = (ROOT / '.github/workflows/release-acceptance.yml').read_text()
        self.assertIn('workflow_dispatch:', workflow)
        self.assertNotIn('pull_request:', workflow)
        self.assertNotIn('push:', workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('default: true', workflow)
        self.assertIn('cancel-in-progress: false', workflow)
        self.assertNotIn('secrets.', workflow)
        self.assertNotIn('argv:', workflow)
        self.assertIn('self-hosted, macOS, ARM64, wizard-os', workflow)

    def test_native_owner_admission_not_impersonated(self):
        source = (ROOT / 'tools/acceptance/launch/ci.py').read_text()
        self.assertNotIn('session_id', source)
        self.assertNotIn('/wizard/internal', source)
        self.assertNotIn('ssh ', source)
        self.assertIn("'timeout_seconds': 18000, 'lane': 'heavy'", source)
        self.assertIn("'action': 'cancel'", source)
        self.assertIn("'0.3.39', '0.3.40'", source)
        self.assertIn("'--check-only'", source)
        self.assertIn('fixture-sha256', source)
        self.assertNotIn('WAM_REF', source)

    def test_config_absence_refused_without_creating_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'missing_WIZARD_CI_ROOT'):
                ci.placement({})
            self.assertEqual([], list(Path(directory).iterdir()))

    def test_shared_lock_is_required_no_new_fake_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(Path, 'is_mount', return_value=True):
                with self.assertRaisesRegex(RuntimeError, 'missing_WIZARD_CI_WORKER_LOCK'):
                    ci.placement({'WIZARD_CI_ROOT': directory, 'WIZARD_WORK_ROOT': str(root.parent)})
                missing = root / 'missing.lock'
                with self.assertRaisesRegex(RuntimeError, 'existing_shared_lock_required'):
                    ci.placement({'WIZARD_CI_ROOT': directory, 'WIZARD_WORK_ROOT': str(root.parent),
                                  'WIZARD_CI_WORKER_LOCK': str(missing)})
                self.assertFalse(missing.exists())

    def test_external_volume_system_disk_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'external_work_volume_required'):
            ci.mounted_volume(Path('/'))

    def test_reserve_and_existing_lock_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = work / 'ci'
            root.mkdir()
            lock = work / 'worker.lock'
            lock.touch()
            other = work / 'other.lock'
            other.touch()
            env = {'WIZARD_CI_ROOT': str(root), 'WIZARD_WORK_ROOT': str(work),
                   'WIZARD_CI_WORKER_LOCK': str(lock)}
            with patch.object(Path, 'is_mount', return_value=True), patch.object(ci.shutil, 'which', return_value='/bin/tool'), \
                    patch.object(ci.shutil, 'disk_usage') as usage:
                usage.return_value.free = 291 * ci.GIB - 1
                with self.assertRaisesRegex(RuntimeError, '291_GiB_free_required'):
                    ci.placement(env)
                usage.return_value.free += 1
                self.assertEqual((root, work, lock), ci.placement(env))
                with self.assertRaisesRegex(RuntimeError, 'shared_lock_identity_mismatch'):
                    ci.placement({**env, 'WIZARD_HEAVY_REMOTE_LOCK': str(other)})
                with self.assertRaisesRegex(RuntimeError, 'heavy_root_mismatch'):
                    ci.placement({**env, 'WIZARD_HEAVY_ROOT': str(root)})

    def test_symlink_lock_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = work / 'ci'
            root.mkdir()
            lock = work / 'lock'
            lock.touch()
            alias = work / 'alias'
            alias.symlink_to(lock)
            with patch.object(Path, 'is_mount', return_value=True):
                with self.assertRaisesRegex(RuntimeError, 'existing_shared_lock_required'):
                    ci.placement({'WIZARD_CI_ROOT': str(root), 'WIZARD_WORK_ROOT': str(work),
                                  'WIZARD_CI_WORKER_LOCK': str(alias)})

    def test_real_lease_required_before_vm_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / 'lock'
            other = root / 'other'
            lock.touch()
            other.touch()
            (root / 'job.json').write_text(json.dumps({'lock': str(lock)}))
            with other.open() as fd, patch.dict(os.environ, {'WIZARD_HEAVY_LOCK_FD': str(fd.fileno())}):
                with self.assertRaisesRegex(RuntimeError, 'inherited_lock_identity_mismatch'):
                    ci.execute(root)
            self.assertFalse((root / 'source').exists())

    def test_manifest_and_version_tokens_validated_before_fetch(self):
        for release, digest in [('0.3.50;id', 'a' * 64), ('0.3.50', 'A' * 64), ('0.3.50', 'abc')]:
            with self.assertRaisesRegex(RuntimeError, 'invalid_'):
                ci.published_manifest(release, digest)

    def test_exact_public_bytes_not_just_same_version(self):
        release = '0.3.50'
        raw = (ROOT / 'releases' / (release + '.json')).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        with patch.object(ci.urllib.request, 'urlopen') as fetch:
            fetch.return_value.__enter__.return_value.read.return_value = raw
            self.assertEqual(json.loads(raw)['components']['wizard-app-manager']['commit'], ci.published_manifest(release, digest))
            fetch.return_value.__enter__.return_value.read.return_value = raw + b'\n'
            with self.assertRaisesRegex(RuntimeError, 'public_manifest_mismatch'):
                ci.published_manifest(release, digest)


if __name__ == '__main__':
    unittest.main()
