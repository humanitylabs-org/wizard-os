#!/usr/bin/env python3
"""Lightweight safety/protocol tests; NOT evidence of a model or emulator pass."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'acceptance/launch'
sys.path.insert(0, str(ROOT))
import first_chat
import phone


class OnboardingTests(unittest.TestCase):
    def test_secret_must_be_owned_0600_and_not_a_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / 'connection.json'
            p.write_text('{}')
            p.chmod(0o600)
            self.assertEqual(first_chat.private_file(p, root), p)
            p.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, 'permissions'):
                first_chat.private_file(p, root)
            p.chmod(0o600)
            link = root / 'link'
            link.symlink_to(p)
            with self.assertRaisesRegex(RuntimeError, 'boundary'):
                first_chat.private_file(link, root)
            with self.assertRaisesRegex(RuntimeError, 'boundary'):
                first_chat.private_file(p, root / 'other')

    def test_guest_snippets_compile(self):
        for s in (first_chat.INSTALL, first_chat.REMOVE, first_chat.CHAT):
            compile(s, '<guest>', 'exec')
        self.assertIn("/v1/bootstrap", first_chat.CHAT)
        self.assertIn("/hermes/v1/runs", first_chat.CHAT)
        self.assertIn("r.get('status')=='completed'", first_chat.CHAT)
        self.assertIn("m.get('role')=='assistant'", first_chat.CHAT)

    def test_renewable_secret_never_in_access_lease(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'connection.json'
            p.write_text('{}')
            p.chmod(0o600)
            # Deliberately fake ONLY for testing the credential projection.
            module = type('M', (), {'Connection': lambda p: type('C', (), {'access': lambda self: 'access-canary'})(),
                                   'claims': lambda s: {'exp': 9999999999}})
            spec = type('S', (), {'loader': type('L', (), {'exec_module': lambda *args: None})()})()
            with patch.object(first_chat.importlib.util, 'spec_from_file_location', return_value=spec), \
                 patch.object(first_chat.importlib.util, 'module_from_spec', return_value=module):
                lease = first_chat.access_lease(p, Path(d), Path(d))
            tokens = lease['providers']['openai-codex']['tokens']
            self.assertEqual(tokens, {'access_token': 'access-canary'})
            self.assertNotIn('refresh_token', json.dumps(lease))

    def test_cleanup_even_on_partial_install_and_model_failure(self):
        for failure in ('install', 'chat'):
            calls = []
            def fake_guest(vm, code, value=None):
                calls.append(code)
                if failure == 'install' and code == first_chat.INSTALL:
                    raise RuntimeError('private-canary')
                return {}
            with patch.object(first_chat, 'access_lease', return_value={}), patch.object(first_chat, 'guest', side_effect=fake_guest):
                with self.assertRaises(RuntimeError):
                    with first_chat.credential_lease('lc-fresh', 'not-read', 'not-read', 'not-read'):
                        raise RuntimeError('chat-failed')
            self.assertEqual(calls[-1], first_chat.REMOVE)

    def test_never_touch_retained_or_owner_vm(self):
        with patch.object(first_chat, 'guest') as guest:
            for name in ('launch-real-use', 'owner-box'):
                with self.assertRaisesRegex(RuntimeError, 'disposable'):
                    with first_chat.credential_lease(name, 'x', 'x', 'x'):
                        pass
            guest.assert_not_called()

    def test_receipt_has_no_transcript_or_session(self):
        with patch.object(first_chat, 'guest', return_value={'session': 'private-session', 'output': 'private-response'}):
            receipt, transient = first_chat.run_chat('lc-fresh')
        self.assertEqual(set(receipt), {'passed', 'latency_ms', 'provider'})
        self.assertNotIn('private', json.dumps(receipt))
        self.assertEqual(transient['session'], 'private-session')

    def test_release_apk_hash_checked_before_tools_or_install(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            apk, feed = d / 'published.apk', d / 'feed.json'
            apk.write_bytes(b'bad')
            feed.write_text(json.dumps({'app': phone.PACKAGE, 'signer': phone.SIGNER, 'bytes': 3, 'sha256': '0' * 64}))
            with self.assertRaises(AssertionError), patch.object(phone.subprocess, 'run') as run:
                phone.validate_apk({'apk': str(apk), 'feed': str(feed)}, d, run)
            run.assert_not_called()

    def test_ui_xml_parses_escaped_text_and_bounds(self):
        xml = '<hierarchy><node text="Wizard &amp; ready" content-desc="Chat" bounds="[10,20][30,40]"/></hierarchy>'
        self.assertIn('Wizard & ready', phone.labels(xml))
        self.assertEqual(phone.center(next(phone.ET.fromstring(xml).iter('node'))), (20, 30))


if __name__ == '__main__':
    unittest.main()
