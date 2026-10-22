#!/usr/bin/env python3
"""Fast harness contracts only. NO VMs, network, real accounts or backup acceptance.

The dry-run executes the actual orchestration with test doubles, and attacks
marker omissions, paused jobs, leftover Mac markers and partial-exit handling.
"""
import contextlib
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from fixture import CLASSES, FILES
spec=importlib.util.spec_from_file_location('backup_proof',HERE/'backup-proof.py')
assert spec is not None and spec.loader is not None
driver=importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)


def marked(*, present=True, paused=True):
    return {'checks':{**{k:present for k in CLASSES},'scheduled_jobs_paused':paused},
            'cron_ids':['fixture-job'] if present else [], 'refused_scope':{'files-data':'baseline-sha'}}


class HarnessContracts(unittest.TestCase):
    def test_every_named_class_is_required(self):
        for key in CLASSES:
            for missing in (False,True):
                with self.subTest(key=key,missing=missing):
                    value=marked()
                    if missing: del value['checks'][key]
                    else: value['checks'][key]=False
                    with self.assertRaises(AssertionError): driver.require_markers(value,paused=True)

    def test_cron_must_exist_and_arrive_paused(self):
        for value in (marked(paused=False),dict(marked(),cron_ids=[])):
            with self.assertRaises(AssertionError): driver.require_markers(value,paused=True)
        driver.require_markers(marked(),paused=True)

    def test_refusal_only_exempts_refused_app_data(self):
        value=marked(); value['checks']['app_data']=False
        driver.require_markers(value,paused=True,refused_app=True)
        value['checks']['logins']=False
        with self.assertRaises(AssertionError): driver.require_markers(value,paused=True,refused_app=True)

    def exercise(self, *, refusal_exit=3, refusal_message=None, leftover=False, lost_class=None, undo_digest=True):
        events=[]
        def event(name): events.append(name)
        with tempfile.TemporaryDirectory(prefix='backup-harness-',dir=__import__('os').environ.get('TMPDIR')) as temp:
            root=Path(temp); shared=root/'shared'; shared.mkdir()
            def fixture(label, where, action='snapshot'):
                event(label)
                if action=='seed':
                    self.assertFalse((shared/'markers.json').exists())
                    (shared/'markers.json').write_text(json.dumps({'origin':'mac'}))
                    return {'seeded':True}
                self.assertTrue((shared/'markers.json').is_file(),'markers read before seed')
                if action=='newer': return {'row':{'id':'files'}}
                if action=='receipt': return {'ok':False,'partial':True,'refused':[{'id':'files','backup':{'version':'9999.0.0'},'here':{'version':'1.0.0'}}]}
                if label=='linux-before-markers': return marked(present=False)
                if label in ('mac-return-disturbed','mac-return-undo-disturbed'):
                    return marked(present=leftover)
                if label=='refusal-before': return marked(present=False)
                value=marked()
                if label=='refusal-after': value['checks']['app_data']=False
                if label=='mac-return-markers' and lost_class: value['checks'][lost_class]=False
                return value
            def linux(label,*args,**kw):
                event(label)
                if label=='newer-app-refusal':
                    message=refusal_message if refusal_message is not None else "partly restored: Files not restored: your backup is from Files 9999.0.0, newer than this box's 1.0.0. Update this box, then restore again. scheduled jobs are paused"
                    return SimpleNamespace(returncode=refusal_exit,stdout=message,stderr='')
                if 'undo' in label: return SimpleNamespace(returncode=0,stdout=json.dumps({'ok':True,'digest_match':undo_digest}),stderr='')
                return SimpleNamespace(returncode=0,stdout=json.dumps({'ok':True,'partial':False,'refused':[]}),stderr='')
            def job(label,*args,**kw):
                event(label); return {'result':{'ok':True,'digest_match':undo_digest}}
            with contextlib.ExitStack() as stack:
                for key,value in {'R':root,'Q':shared,'REPORT':{'steps':[]},'fixture':fixture,
                    'snapshot':lambda label,*a,**k: (event(label) or {'snapshot':label}),
                    'expect_comparison':lambda label,*a,**k:event(label),
                    'save_report':lambda:None,'write_json':lambda *a:None,
                    'clone':lambda *a:event('clone-linux'),
                    'install_wam':lambda *a:driver.WAM_LINUX_SHA,
                    'run':lambda label,*a,**k:event(label),
                    'linux':linux,'mac':lambda label,*a,**k:event(label),
                    'job':job,'export_mac':lambda *a:(event('mac-native-export') or shared/'mac-native.wizardbackup'),
                    'mac_import':lambda *a:event('linux-to-mac-import')}.items():
                    stack.enter_context(patch.object(driver,key,value))
                driver.acceptance('test-secret-not-a-real-key')
                self.assertTrue((root/'markers.json').is_file())
                self.assertEqual(driver.REPORT['P1'],'PASS'); self.assertEqual(driver.REPORT['P2'],'PASS')
                self.assertEqual(driver.REPORT['refusal'],'PASS')
        return events

    def test_dry_run_mac_linux_mac_order_seed_undo_refusal(self):
        events=self.exercise()
        sequence=['mac-seed','mac-source-markers','mac-native-export','mac-to-linux-import',
                  'linux-restored-markers','linux-roundtrip-export','mac-return-baseline',
                  'mac-return-disturbed','linux-to-mac-import','mac-return-markers','mac-return-undo',
                  'linux-newer-package','linux-newer-export','linux-success-undo','newer-app-refusal',
                  'refusal-after','linux-refusal-undo']
        self.assertEqual([x for x in events if x in sequence],sequence)

    def test_exit_zero_does_not_pass_refusal(self):
        with self.assertRaisesRegex(AssertionError,'exit 3'): self.exercise(refusal_exit=0)

    def test_exit_three_without_clear_message_fails(self):
        with self.assertRaisesRegex(AssertionError,'Unclear'): self.exercise(refusal_message='error')

    def test_preexisting_mac_markers_cannot_pass_return_leg(self):
        with self.assertRaisesRegex(AssertionError,'retained'): self.exercise(leftover=True)

    def test_each_return_class_is_asserted(self):
        for key in CLASSES:
            with self.subTest(key=key), self.assertRaises(AssertionError): self.exercise(lost_class=key)

    def test_undo_digest_is_mandatory(self):
        with self.assertRaises(AssertionError): self.exercise(undo_digest=False)

    def test_file_name_coverage(self):
        self.assertTrue(any('é' in p for p in FILES))
        self.assertTrue(any('日本語' in p for p in FILES))
        self.assertTrue(any(Path(p).name.startswith('.') for p in FILES))

    def test_no_false_success_after_late_error_or_cleanup_failure(self):
        value={k:'PASS' for k in ('build','swift_tests','P1','P2','refusal')}
        value.update(key_never_in_frontdoor_journal=True,cleanup={'mac_disk_removed':True,'keys_removed':True,'staging_removed':True,'guests_destroyed':{'linux':True}})
        self.assertTrue(driver.accepted(value))
        value['error']='late secret audit failed'
        self.assertFalse(driver.accepted(value))
        del value['error']; value['cleanup']['guests_destroyed']['linux']=False
        self.assertFalse(driver.accepted(value))

    def test_seed_publishes_manifest_last_and_failure_leaves_none(self):
        import fixture
        with tempfile.TemporaryDirectory(prefix='backup-seed-',dir=__import__('os').environ.get('TMPDIR')) as temp:
            root=Path(temp); home=root/'home'; home.mkdir(); files=root/'files'; files.mkdir()
            marker=root/'markers.json'
            b=SimpleNamespace(home=home,files_root=lambda:files,runtipi_root=root/'runtipi',main_agent=lambda:None,runner=SimpleNamespace(python=lambda *a:json.dumps({'id':'hermes','cron':'job'})))
            writes=[]
            def write(*a):
                self.assertFalse(marker.exists(),'manifest was published before seed completed')
                writes.append(a)
            with patch.object(fixture,'root_python',side_effect=write),patch.object(fixture.subprocess,'run'):
                got=fixture.seed(b,marker)
            self.assertEqual(len(writes),2)
            self.assertEqual(json.loads(marker.read_text()),got)
            self.assertEqual(set(got['classes']),set(CLASSES))
            self.assertEqual(len(got['owner_files']['files']),4)
            marker.unlink()
            with patch.object(fixture,'root_python',side_effect=RuntimeError('seed failed')),patch.object(fixture.subprocess,'run'):
                with self.assertRaises(RuntimeError): fixture.seed(b,marker)
            self.assertFalse(marker.exists())

    def test_embedded_stock_scripts_compile(self):
        import fixture, disturb
        for script in (fixture.STOCK_READ,fixture.STOCK_SEED,disturb.STOCK):
            compile(script,'guest-stock-script','exec')


if __name__=='__main__':
    print('DRY-RUN ONLY: orchestration/unit contracts; no real VM acceptance',flush=True)
    unittest.main(verbosity=2)
