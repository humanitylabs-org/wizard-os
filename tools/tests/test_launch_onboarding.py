#!/usr/bin/env python3
"""Lightweight safety/protocol tests; NOT evidence of a model or emulator pass."""
import contextlib
import importlib.util
import io
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

    def test_retired_chat_model_is_replaced_by_the_live_subscription_catalog(self):
        rows = [{'id': 'codex-auto-review', 'abilities': ['text']},
                {'id': "gpt-bad'; private-canary", 'abilities': ['text']},
                {'id': 'gpt-image', 'abilities': ['image']},
                {'id': 'gpt-current', 'abilities': ['text', 'streaming']}]
        module = type('M', (), {'Connection': lambda p: type('C', (), {'models': lambda self: rows})()})
        with patch.object(first_chat, 'oauth_module', return_value=module):
            model = first_chat.select_model('unused', 'unused', 'unused')
        self.assertEqual(model, 'gpt-current')
        code = first_chat.chat_code(model)
        compile(code, '<guest>', 'exec')
        self.assertNotIn('gpt-5.4', code)
        self.assertNotIn('__CHAT_MODEL__', code)
        self.assertEqual(code.count("'gpt-current'"), 3)
        with patch.object(first_chat, 'guest', return_value={}) as guest:
            first_chat.run_chat('lc-fresh', model)
        self.assertEqual(guest.call_args.args[1], code)
        self.assertEqual(guest.call_args.kwargs['snippet'], 'chat')
        for invalid in (None, '', "gpt-bad'", 'gpt-bad\n'):
            with self.assertRaisesRegex(RuntimeError, 'chat_model_invalid'):
                first_chat.chat_code(invalid)

    def test_empty_or_failed_catalog_never_falls_back_to_a_retired_slug(self):
        for rows in ([], [{'id': 'codex-auto-review', 'abilities': ['text']}]):
            module = type('M', (), {'Connection': lambda p: type('C', (), {'models': lambda self: rows})()})
            with patch.object(first_chat, 'oauth_module', return_value=module):
                with self.assertRaisesRegex(RuntimeError, 'chat_model_catalog_empty'):
                    first_chat.select_model('unused', 'unused', 'unused')
        module = type('M', (), {'Connection': lambda p: type('C', (), {'models': lambda self: (_ for _ in ()).throw(RuntimeError('secret-canary'))})()})
        with patch.object(first_chat, 'oauth_module', return_value=module):
            with self.assertRaisesRegex(RuntimeError, '^chat_model_catalog_unavailable$'):
                first_chat.select_model('unused', 'unused', 'unused')

    def test_cleanup_even_on_partial_install_and_model_failure(self):
        for failure in ('install', 'chat'):
            calls = []
            def fake_guest(vm, code, value=None, **kwargs):
                calls.append(code)
                if failure == 'install' and code == first_chat.INSTALL:
                    raise RuntimeError('private-canary')
                return {}
            with patch.object(first_chat, 'select_model', return_value='gpt-test'), patch.object(first_chat, 'access_lease', return_value={}), patch.object(first_chat, 'guest', side_effect=fake_guest):
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

    def test_nested_docker_stderr_is_class_only_with_original_return_code(self):
        namespace = {}
        with patch.object(first_chat.subprocess, 'check_output', return_value='fixture-hermes-agent-engine-1\n'):
            exec(first_chat.ENGINE, namespace)
        for stderr in ('PermissionError: secret-canary /private/auth.json', b'PermissionError: secret-canary'):
            result = type('Result', (), {'returncode': 33, 'stderr': stderr})()
            out = io.StringIO()
            with contextlib.redirect_stderr(out), self.assertRaises(SystemExit) as caught:
                namespace['checked'](result)
            self.assertEqual(caught.exception.code, 33)
            self.assertEqual(out.getvalue(), 'PermissionError\n')

    def test_guest_failures_log_only_snippet_rc_and_allowlisted_class(self):
        for code, stage in ((first_chat.INSTALL, 'install'), (first_chat.CHAT, 'chat'), (first_chat.REMOVE, 'remove')):
            with tempfile.TemporaryDirectory() as d:
                log = Path(d) / 'private.log'
                result = type('Result', (), {'returncode': 17, 'stdout': 'model-transcript-canary',
                    'stderr': 'Traceback (most recent call last):\nPermissionError: token-canary /private/home/auth.json'})()
                with patch.object(first_chat.subprocess, 'run', return_value=result):
                    with self.assertRaises(first_chat.GuestFailure) as caught:
                        first_chat.guest('lc-fresh', code, {'access_token': 'input-canary'}, log=log)
                self.assertEqual(json.loads(log.read_text()), {'first_chat_failure': {
                    'snippet': stage, 'rc': 17, 'stderr_class': 'PermissionError'}})
                self.assertNotIn('canary', str(caught.exception))
                self.assertNotIn('canary', log.read_text())

    def test_guest_timeout_and_malformed_reply_do_not_leak_captured_output(self):
        failures = [first_chat.subprocess.TimeoutExpired(['private-argv-canary'], 1,
                      output='transcript-canary', stderr='secret-canary'),
                    type('Result', (), {'returncode': 0, 'stdout': 'transcript-canary', 'stderr': ''})()]
        for failure, category in zip(failures, ('timeout', 'JSONDecodeError')):
            with tempfile.TemporaryDirectory() as d:
                log = Path(d) / 'private.log'
                kwargs = {'side_effect': failure} if isinstance(failure, Exception) else {'return_value': failure}
                with patch.object(first_chat.subprocess, 'run', **kwargs):
                    with self.assertRaises(first_chat.GuestFailure):
                        first_chat.guest('lc-fresh', first_chat.CHAT, log=log)
                row = json.loads(log.read_text())['first_chat_failure']
                self.assertEqual(row['stderr_class'], category)
                self.assertNotIn('canary', log.read_text())
        self.assertEqual(first_chat.stderr_class('CustomSecretError: canary'), 'unknown')

    def test_install_and_cleanup_failures_are_both_diagnosed(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'private.log'
            result = type('Result', (), {'returncode': 1, 'stdout': '', 'stderr': 'PermissionError: secret-canary'})()
            with patch.object(first_chat, 'select_model', return_value='gpt-test'), patch.object(first_chat, 'access_lease', return_value={}), \
                 patch.object(first_chat.subprocess, 'run', return_value=result):
                with self.assertRaises(first_chat.GuestFailure):
                    with first_chat.credential_lease('lc-fresh', 'x', 'x', 'x', log=log):
                        self.fail('install must fail closed')
            rows = [json.loads(line)['first_chat_failure'] for line in log.read_text().splitlines()]
            self.assertEqual([row['snippet'] for row in rows], ['install', 'remove'])
            self.assertNotIn('canary', log.read_text())

    def test_receipt_has_no_transcript_or_session(self):
        with patch.object(first_chat, 'guest', return_value={'session': 'private-session', 'output': 'private-response'}):
            receipt, transient = first_chat.run_chat('lc-fresh', 'gpt-test')
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
