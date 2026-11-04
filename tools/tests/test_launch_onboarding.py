#!/usr/bin/env python3
"""Lightweight safety/protocol tests; NOT evidence of a model or emulator pass."""
import contextlib
import importlib.util
import io
import itertools
import json
import os
import platform
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

    def test_wrapped_oauth_archive_is_rejected_before_any_vm_or_secret_read(self):
        import run as launch_run
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            cli = work / 'wam/wizard-cli/wizard'
            cli.parent.mkdir(parents=True)
            cli.touch()
            source = work / 'oauth'
            (source / 'chatgpt-connection').mkdir(parents=True)
            (source / 'chatgpt-connection/codex.py').write_text('raise RuntimeError("must not import")')
            argv = ['run.py', '--root', str(work / 'run'), '--release', '0.3.70',
                    '--cli', str(cli), '--first-chat-secret', str(work / 'secret/connection.json'),
                    '--secrets-root', str(work / 'secret'), '--oauth-source', str(source)]
            error = io.StringIO()
            with patch.object(sys, 'argv', argv), patch.dict(os.environ, WIZARD_WORK_ROOT=d), \
                 patch.object(Path, 'is_mount', return_value=True), \
                 patch.object(first_chat, 'private_file') as secret, \
                 patch.object(launch_run.subprocess, 'run') as subprocess_run, \
                 contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as caught:
                launch_run.main()
            self.assertEqual(caught.exception.code, 2)
            self.assertIn('oauth_source_missing', error.getvalue())
            secret.assert_not_called()
            subprocess_run.assert_not_called()
            self.assertFalse((work / 'run').exists())

    def test_oauth_source_preflight_accepts_only_explicit_helper_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            helper = root / 'chatgpt-connection'
            helper.mkdir()
            source = helper / 'codex.py'
            source.write_text('raise RuntimeError("must not import")')
            self.assertEqual(first_chat.validate_oauth_source(helper), source)
            with self.assertRaisesRegex(RuntimeError, '^oauth_source_missing$'):
                first_chat.validate_oauth_source(root)

    def test_host_catalog_and_access_failures_log_only_fixed_stage_and_class(self):
        for stage, target in [('catalog', 'select_model'), ('access', 'access_lease')]:
            with tempfile.TemporaryDirectory() as d:
                log = Path(d) / 'private.log'
                with patch.object(first_chat, 'select_model', return_value='gpt-test'), \
                     patch.object(first_chat, 'access_lease', return_value={}), \
                     patch.object(first_chat, target, side_effect=FileNotFoundError('secret-canary')), \
                     patch.object(first_chat, 'guest') as guest:
                    with self.assertRaises(FileNotFoundError):
                        with first_chat.credential_lease('lc-fresh', 'x', 'x', 'x', log=log):
                            self.fail('host failure must not install')
                guest.assert_not_called()
                self.assertEqual(json.loads(log.read_text()), {'first_chat_failure': {
                    'snippet': stage, 'rc': None, 'stderr_class': 'FileNotFoundError'}})
                self.assertNotIn('canary', log.read_text())

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

    # Documentation-range addresses and example names only: never a real tailnet.
    SCUTIL = ('DNS configuration\n\nresolver #1\n  nameserver[0] : 192.0.2.1\n\n'
              'resolver #2\n  domain   : other.example\n  nameserver[0] : 192.0.2.9\n\n'
              'resolver #3\n  domain   : example.ts.net\n  nameserver[0] : 192.0.2.53\n')

    def fake_device(self, unknown_host=False):
        from unittest.mock import Mock
        def command(argv, **kwargs):
            text = ' '.join(map(str, argv))
            output = ''
            if text.startswith('tailscale status'):
                output = json.dumps({'Self': {'DNSName': 'box.example.ts.net.'}})
            elif text.startswith('scutil --dns'):
                output = self.SCUTIL
            elif 'sys.boot_completed' in text:
                output = '1'
            elif 'ro.build.version.sdk' in text:
                output = '35'
            elif ' install ' in text:
                output = 'Success'
            elif 'shell cat /sdcard/launch-ui.xml' in text:
                output = '<hierarchy><node text="Change Wizard"/></hierarchy>'
            elif ' ping ' in text and unknown_host:
                return Mock(returncode=2, stdout='', stderr='ping: unknown host box.example.ts.net')
            return Mock(returncode=0, stdout=output, stderr='')
        return command

    def test_tailnet_resolver_is_read_from_the_hosts_scoped_magicdns_entry(self):
        self.assertEqual(phone.tailnet_resolver('box.example.ts.net.', self.SCUTIL), '192.0.2.53')
        with self.assertRaisesRegex(RuntimeError, 'phone_tailnet_dns'):
            phone.tailnet_resolver('box.missing.ts.net', self.SCUTIL)

    def test_phone_failure_keeps_stage_and_completed_checks_without_private_text(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / 'phone.json'
            config.write_text(json.dumps({'sdk': str(root), 'work_root': str(root),
                'java_home': str(root)}))
            em = Mock()
            em.poll.return_value = None
            with patch.object(platform, 'system', return_value='Darwin'), \
                 patch.object(platform, 'machine', return_value='arm64'), \
                 patch.object(phone, 'validate_apk', return_value=(root / 'published.apk', {}, True)), \
                 patch.object(phone, 'worker_lock', return_value=contextlib.nullcontext()), \
                 patch.object(phone, 'configure_avd'), \
                 patch.object(phone.subprocess, 'run', side_effect=self.fake_device()), \
                 patch.object(phone.subprocess, 'Popen', return_value=em), \
                 patch.object(phone, 'https_forward', side_effect=RuntimeError('private-url transcript-canary')):
                result = phone.run_phone('lc-fresh', 'unused', root, config, {'output': 'private-reply'})
            self.assertEqual(result['failure']['exception_class'], 'RuntimeError')
            self.assertEqual(result['failure']['message_code'], 'unclassified')
            self.assertIn('adb_devices', result.pop('failure'))
            self.assertEqual(result, {'passed': False, 'checks': {'empty_install_connect': True},
                                     'failure_stage': 'https-forward'})
            self.assertNotIn('private', json.dumps(result))
            em.wait.assert_called_once()
            self.assertFalse((root / 'avd').exists())
            self.assertFalse((root / 'device').exists())

    def test_emulator_resolves_tailnet_names_like_a_phone_running_tailscale(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            config = root / 'phone.json'
            config.write_text(json.dumps({'sdk': str(root), 'work_root': str(root), 'java_home': str(root)}))
            em = Mock()
            em.poll.return_value = None
            with patch.object(platform, 'system', return_value='Darwin'), \
                 patch.object(platform, 'machine', return_value='arm64'), \
                 patch.object(phone, 'validate_apk', return_value=(root / 'published.apk', {}, True)), \
                 patch.object(phone, 'worker_lock', return_value=contextlib.nullcontext()), \
                 patch.object(phone, 'configure_avd'), \
                 patch.object(phone.subprocess, 'run', side_effect=self.fake_device(unknown_host=True)), \
                 patch.object(phone.subprocess, 'Popen', return_value=em) as start, \
                 patch.object(phone, 'https_forward', return_value=contextlib.nullcontext('https://box.example.ts.net:9450')), \
                 patch.object(phone.time, 'sleep'), \
                 patch.object(phone.time, 'monotonic', side_effect=itertools.count(0, 5)):
                result = phone.run_phone('lc-fresh', 'unused', root, config, {})
            argv = start.call_args.args[0]
            self.assertEqual(argv[argv.index('-dns-server') + 1], '192.0.2.53')
            self.assertEqual(result.pop('failure')['message_code'], 'phone_tailnet_dns')
            self.assertEqual(result, {'passed': False, 'checks': {'empty_install_connect': True},
                                     'failure_stage': 'tailnet-dns'})
            self.assertNotIn('example', json.dumps(result))

    def test_phone_receipt_allowlists_stages_and_preflight_errors(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result = phone.run_phone('owner-box', 'unused', root, 'not-read', {})
            self.assertEqual(result.pop('failure')['message_code'], 'phone_disposable_required')
            self.assertEqual(result, {'passed': False, 'checks': {}, 'failure_stage': 'preflight'})
        def fail(*args):
            progress = args[-1]
            progress['stage'] = 'transcript-canary'
            raise RuntimeError('private-url')
        with patch.object(phone, '_run_phone', side_effect=fail):
            result = phone.run_phone('lc-fresh', 'unused', None, None, {})
        self.assertEqual(result['failure_stage'], 'preflight')
        self.assertNotIn('canary', json.dumps(result))

    def test_phone_failure_receipt_fails_the_whole_onboarding_run(self):
        import run as launch_run
        # macOS runner temp paths exceed Lima's socket limit; /tmp is short on both hosts.
        with tempfile.TemporaryDirectory(dir='/tmp', prefix='lo') as d:
            work = Path(d)
            cli = work / 'wam/wizard-cli/wizard'
            cli.parent.mkdir(parents=True)
            cli.touch()
            def command(argv, log, timeout=1800):
                if 'capture.py' in ' '.join(map(str, argv)):
                    target = Path(argv[argv.index(str(ROOT / 'capture.py')) + 1])
                    target.write_text(json.dumps({'passed': True, 'release': '0.3.70',
                                                 'contact': True, 'setup_route': True}))
            failed = {'passed': False, 'failure_stage': 'https-forward',
                      'checks': {'empty_install_connect': True}}
            argv = ['run.py', '--root', str(work / 'run'), '--release', '0.3.70', '--cli', str(cli),
                    '--first-chat-secret', str(work / 'secret/connection.json'),
                    '--secrets-root', str(work / 'secret'), '--oauth-source', str(work / 'oauth'),
                    '--phone-config', 'private-config', '--onboarding-only']
            with patch.object(sys, 'argv', argv), patch.dict(os.environ, WIZARD_WORK_ROOT=d), \
                 patch.object(Path, 'is_mount', return_value=True), \
                 patch.object(first_chat, 'private_file'), patch.object(first_chat, 'validate_oauth_source'), \
                 patch.object(first_chat, 'credential_lease', return_value=contextlib.nullcontext('gpt-test')), \
                 patch.object(first_chat, 'run_chat', return_value=({'passed': True}, {})), \
                 patch.object(phone, 'run_phone', return_value=failed), \
                 patch.object(launch_run.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 400 << 30})()), \
                 patch.object(launch_run, 'command', side_effect=command), \
                 contextlib.redirect_stdout(io.StringIO()):
                status = launch_run.main()
            self.assertEqual(status, 1)
            receipts = list((work / 'run/runs').glob('*/receipt.json'))
            self.assertEqual(len(receipts), 1)
            receipt = json.loads(receipts[0].read_text())
            self.assertFalse(receipt['passed'])
            self.assertEqual(receipt['phone'], failed)
            self.assertEqual(receipt['step'], 'second-owner-phone')
            import release_gate
            native = release_gate.native_vm_config()
            config = json.loads(next((work / 'run/runs').glob('*/lc-*.json')).read_text())
            self.assertEqual(receipt['architecture'], native['arch'])
            self.assertEqual(receipt['reserve_gib'], 250 if native['vmType'] == 'vz' else 60)
            self.assertEqual(receipt['disk_gib'], 50 if native['vmType'] == 'vz' else 40)
            self.assertEqual(receipt['required_free_gib'], 310 if native['vmType'] == 'vz' else 110)
            self.assertEqual(config['disk'], '50GiB' if native['vmType'] == 'vz' else '40GiB')
            self.assertTrue(all(config[key] == value for key, value in native.items()))
            self.assertEqual([m for m in config['mounts'] if m['writable']],
                             [{'location': str(work / 'run'), 'writable': True}])

    def test_ui_xml_parses_escaped_text_and_bounds(self):
        xml = '<hierarchy><node text="Wizard &amp; ready" content-desc="Chat" bounds="[10,20][30,40]"/></hierarchy>'
        self.assertIn('Wizard & ready', phone.labels(xml))
        self.assertEqual(phone.center(next(phone.ET.fromstring(xml).iter('node'))), (20, 30))


    def test_phone_reuses_heavy_worker_lock_instead_of_blocking_on_it(self):
        import fcntl
        with tempfile.TemporaryDirectory() as d:
            lock = Path(d) / 'worker.lock'
            with lock.open('a') as parent:
                fcntl.flock(parent, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.dict(os.environ, {'WIZARD_HEAVY_LOCK_FD': str(parent.fileno())}):
                    with phone.worker_lock(d):
                        pass
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop('WIZARD_HEAVY_LOCK_FD', None)
                    with self.assertRaises(BlockingIOError), phone.worker_lock(d):
                        pass
            other = Path(d) / 'other.lock'
            other.touch()
            with other.open('a') as wrong, patch.dict(os.environ, {'WIZARD_HEAVY_LOCK_FD': str(wrong.fileno())}):
                with self.assertRaises(RuntimeError), phone.worker_lock(d):
                    pass

class NativeLinuxTests(unittest.TestCase):
    RESOLV = ('# Generated resolver\nnameserver 192.0.2.53\n'
              'nameserver 2001:db8::53\nsearch example.ts.net\n')

    def test_vm_and_android_image_share_native_admission(self):
        import release_gate
        for system, machine, vm, arch, abi in (
                ('Linux', 'x86_64', 'qemu', 'x86_64', 'x86_64'),
                ('Darwin', 'arm64', 'vz', 'aarch64', 'arm64-v8a')):
            with patch.object(platform, 'system', return_value=system), \
                 patch.object(platform, 'machine', return_value=machine):
                config = release_gate.native_vm_config()
                self.assertEqual((config['vmType'], config['arch']), (vm, arch))
                self.assertEqual(config['images'][0]['arch'], arch)
                self.assertRegex(config['images'][0]['digest'], r'^sha256:[0-9a-f]{64}$')
                self.assertEqual(phone.native_system_image(), 'system-images;android-35;google_apis;' + abi)
                if system == 'Linux':
                    self.assertEqual(config['mountType'], '9p')
        for system, machine in (('Linux', 'aarch64'), ('Darwin', 'x86_64')):
            with patch.object(platform, 'system', return_value=system), \
                 patch.object(platform, 'machine', return_value=machine):
                with self.assertRaises(RuntimeError):
                    phone.native_system_image()

    def test_linux_resolver_uses_host_file_not_scutil(self):
        from unittest.mock import Mock
        call = Mock()
        with patch.object(platform, 'system', return_value='Linux'), \
             patch.object(Path, 'read_text', return_value=self.RESOLV) as read:
            self.assertEqual(phone.host_resolver('box.example.ts.net.', call), '192.0.2.53')
        read.assert_called_once_with()
        call.assert_not_called()
        for text in ('search other.example\nnameserver 192.0.2.53',
                     'search example.ts.net\nnameserver 127.0.0.53',
                     'search example.ts.net\nnameserver invalid'):
            with self.assertRaisesRegex(RuntimeError, '^phone_tailnet_dns$'):
                phone.tailnet_resolver('box.example.ts.net', text, 'Linux')

    def test_linux_directory_admission_keeps_mac_mount_requirement(self):
        import release_gate
        with tempfile.TemporaryDirectory() as d, patch.object(Path, 'is_mount', return_value=False):
            with patch.object(platform, 'system', return_value='Linux'):
                self.assertTrue(release_gate.admitted_work_root(Path(d)))
                self.assertFalse(release_gate.admitted_work_root(Path(d) / 'absent'))
            with patch.object(platform, 'system', return_value='Darwin'):
                self.assertFalse(release_gate.admitted_work_root(Path(d)))

    def test_linux_check_only_preserves_containment_reserve_and_no_vm(self):
        import run as launch_run
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            cli = work / 'wam/wizard-cli/wizard'
            cli.parent.mkdir(parents=True)
            cli.touch()
            argv = ['run.py', '--root', str(work / 'run'), '--release', '0.3.94',
                    '--cli', str(cli), '--check-only']
            with patch.object(sys, 'argv', argv), patch.dict(os.environ, WIZARD_WORK_ROOT=d), \
                 patch.object(Path, 'is_mount', return_value=False), \
                 patch.object(platform, 'system', return_value='Linux'), \
                 patch.object(platform, 'machine', return_value='x86_64'), \
                 patch.object(launch_run.shutil, 'disk_usage') as disk, \
                 patch.object(launch_run, 'command') as command, \
                 contextlib.redirect_stdout(io.StringIO()) as out, \
                 contextlib.redirect_stderr(io.StringIO()):
                disk.return_value.free = 400 << 30
                self.assertEqual(launch_run.main(), 0)
                self.assertEqual(json.loads(out.getvalue())['architecture'], 'x86_64')
                disk.return_value.free = (101 << 30) - 1
                with self.assertRaises(SystemExit):
                    launch_run.main()
                disk.return_value.free = 400 << 30
                for root in (work, work.parent / 'outside'):
                    argv[2] = str(root)
                    with self.assertRaises(SystemExit):
                        launch_run.main()
                command.assert_not_called()
            self.assertFalse((work / 'run').exists())

    def test_linux_worker_lock_uses_production_inode_not_android_build_root(self):
        import fcntl
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            production = work / 'heavy/production'
            android = work / 'AndroidBuilds'
            production.mkdir(parents=True)
            android.mkdir()
            (android / 'worker.lock').touch()
            with (production / 'worker.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch.dict(os.environ, WIZARD_HEAVY_LOCK_FD=str(lock.fileno())):
                    with phone.worker_lock(production):
                        pass
                    with self.assertRaisesRegex(RuntimeError, 'inherited_lock_mismatch'), phone.worker_lock(android):
                        pass
                # The context must never unlock or close the heavy worker's FD.
                with (production / 'worker.lock').open('a') as competitor:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(competitor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_optional_sudo_serve_changes_only_dedicated_port(self):
        before = {'TCP': {'443': {'HTTPS': True}}, 'Web': {'box.example.ts.net:443': {'Handlers': {'/': {'Text': 'keep'}}}}}
        after = json.loads(json.dumps(before))
        after['TCP']['9450'] = {'HTTPS': True}
        after['Web']['box.example.ts.net:9450'] = {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:18795'}}}
        responses = [before, {'Self': {'DNSName': 'box.example.ts.net.'}}, {}, after, {}, before]
        for sudo in (False, True):
            with patch.object(phone.subprocess, 'check_output', side_effect=[json.dumps(r) for r in responses]) as call, \
                 patch.object(phone, 'open_forward', return_value=contextlib.nullcontext()):
                with phone.https_forward('lc-fresh', 'unused', Path('unused'), 9450, sudo=sudo):
                    pass
            prefix = ['sudo', '-n'] if sudo else []
            self.assertTrue(all(c.args[0][:len(prefix) + 1] == prefix + ['tailscale'] for c in call.call_args_list))
            self.assertEqual(call.call_args_list[-2].args[0], prefix + ['tailscale', 'serve', '--https=9450', 'off'])


class PhoneTransportDiagnosticsTests(unittest.TestCase):
    def test_linux_proxy_is_explicit_and_darwin_is_unchanged(self):
        status = {'Self': {'DNSName': 'box.example.ts.net.', 'TailscaleIPs': ['192.0.2.2']}}
        from phone_transport import Relay
        import threading
        relay = Relay('http://127.0.0.1:1234')
        relay.lock, relay.counts = threading.Lock(), {}
        with patch.object(platform, 'system', return_value='Linux'), \
             patch.object(phone, 'connect_proxy', return_value=contextlib.nullcontext(relay)) as proxy:
            with phone.emulator_network(status, 9450) as args:
                self.assertEqual(args, [])  # No emulator-level proxy/double proxy.
                calls = []
                def shell(*argv):
                    calls.append(argv)
                    return '10.0.2.2:1234\n'
                args.configure(shell)
                self.assertEqual(calls[0], ('settings', 'put', 'global', 'http_proxy', '10.0.2.2:1234'))
                self.assertIs(args.relay, relay)
            proxy.assert_called_once_with('box.example.ts.net', ['192.0.2.2'], 9450)
        with patch.object(platform, 'system', return_value='Darwin'), patch.object(phone, 'connect_proxy') as proxy:
            with phone.emulator_network({}, 9450) as args:
                self.assertEqual(args, [])
            proxy.assert_not_called()

    def test_proxy_only_connects_to_fixed_authority_and_is_removed_on_failure(self):
        import socket
        import socketserver
        import threading
        from urllib.parse import urlsplit
        from phone_transport import connect_proxy
        class Echo(socketserver.BaseRequestHandler):
            def handle(self):
                while data := self.request.recv(4096):
                    self.request.sendall(data)
        with socketserver.ThreadingTCPServer(('127.0.0.1', 0), Echo) as upstream:
            upstream.daemon_threads = True
            thread = threading.Thread(target=upstream.serve_forever, daemon=True)
            thread.start()
            port = upstream.server_address[1]
            try:
                with self.assertRaisesRegex(RuntimeError, '^test$'):
                    with connect_proxy('127.0.0.1', ['192.0.2.2', '2001:db8::1'], port) as address:
                        endpoint = urlsplit(address)
                        for authority in (f'127.0.0.1:{port}', f'192.0.2.2:{port}', f'[2001:db8::1]:{port}'):
                            with socket.create_connection((endpoint.hostname, endpoint.port), timeout=3) as client:
                                client.sendall(f'CONNECT {authority} HTTP/1.1\r\n\r\n'.encode())
                                self.assertIn(b'200 Connection Established', client.recv(4096))
                                client.sendall(b'opaque-tls-test-bytes')
                                self.assertEqual(client.recv(4096), b'opaque-tls-test-bytes')
                        for request in ('CONNECT other.example:443 HTTP/1.1',
                                        f'CONNECT 127.0.0.1:{port + 1} HTTP/1.1',
                                        f'GET https://127.0.0.1:{port}/ HTTP/1.1', 'X' * 4096):
                            with socket.create_connection((endpoint.hostname, endpoint.port), timeout=3) as client:
                                client.sendall((request + '\r\n\r\n').encode())
                                self.assertIn(b'403 Forbidden', client.recv(4096))
                        counts = address.snapshot()
                        self.assertEqual(counts['connect_allowed'], 3)
                        self.assertGreater(counts['bytes_to_box'], 0)
                        self.assertGreater(counts['bytes_to_android'], 0)
                        self.assertEqual(counts['connect_denied'], 4)
                        self.assertEqual(counts['upstream_failed'], 0)
                        raise RuntimeError('test')
                with self.assertRaises(OSError):
                    socket.create_connection((endpoint.hostname, endpoint.port), timeout=1)
            finally:
                upstream.shutdown()
                thread.join(timeout=2)

    @staticmethod
    def png(raw=b'\x00\xff\x00\x00\xff\xff\x00\x00\xff'):
        import struct, zlib
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
        return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 1, 8, 6, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'tEXt', b'secret-metadata') + chunk(b'IEND', b''))

    @staticmethod
    def pixels(png):
        import struct, zlib
        offset, content = 8, b''
        while offset + 12 <= len(png):
            size = struct.unpack('>I', png[offset:offset + 4])[0]
            if png[offset + 4:offset + 8] == b'IDAT':
                content += png[offset + 8:offset + 8 + size]
            offset += size + 12
        return zlib.decompress(content)

    def test_png_masks_private_text_and_strips_metadata_for_every_filter(self):
        from phone_diagnostics import masked_png
        # First pixel stays red; second private pixel is black and opaque.
        for mode, pixel in ((0, b'\xff\x00\x00\xff\xff\x00\x00\xff'),
                            (1, b'\xff\x00\x00\xff\x00\x00\x00\x00'),
                            (2, b'\xff\x00\x00\xff\xff\x00\x00\xff'),
                            (3, b'\xff\x00\x00\xff\x80\x00\x00\x80'),
                            (4, b'\xff\x00\x00\xff\x00\x00\x00\x00')):
            png = self.png(bytes([mode]) + pixel)
            masked = masked_png(png, [(1, 0, 2, 1)])
            self.assertNotIn(b'secret', masked)
            self.assertEqual(self.pixels(masked), b'\x00\xff\x00\x00\xff\x00\x00\x00\xff')
        self.assertEqual(self.pixels(masked_png(self.png(), None)), b'\x00' + b'\x00\x00\x00\xff' * 2)
        for invalid in (b'not-a-png', self.png(b'invalid')):
            with self.assertRaises(ValueError):
                masked_png(invalid, [])

    def test_failure_diagnostics_are_bounded_private_and_exclude_tokens(self):
        from types import SimpleNamespace
        import phone_diagnostics as diagnostics
        canary = 'access-secret-canary'
        xml = ('<hierarchy><node text="Connect to your Wizard" bounds="[0,0][1,1]"/>'
               f'<node text="{canary}" bounds="[1,0][2,1]"/></hierarchy>')
        calls = []
        def run(argv, **kw):
            calls.append(argv)
            self.assertEqual(kw['timeout'], 20 if 'uiautomator' in argv else 8)
            if 'uiautomator' in argv:
                output = b'UI dumped'
            elif 'cat' in argv:
                output = xml.encode()
            elif 'screencap' in argv:
                output = self.png()
            elif 'dumpsys' in argv:
                output = f'ACTIVITY ai.wizards.os/.ConnectActivity aab123 pid=123\n Intent extras: {canary}\n'.encode()
            else:
                output = json.dumps({'TCP': {'9450': {'HTTPS': True}}, 'Web': {
                    'box.example:9450': {'Handlers': {'/': {'Proxy': canary}}}}}).encode()
            return SimpleNamespace(returncode=0, stdout=output)
        with tempfile.TemporaryDirectory() as d, patch.object(diagnostics.subprocess, 'run', side_effect=run):
            root = Path(d)
            diagnostics.capture_failure(root, 'address-pairing', adb='adb', serial='emulator-5682', sudo=True)
            files = list((root / 'failure').iterdir())
            self.assertEqual({p.name for p in files}, {'labels.json', 'screen.png', 'activity-top.txt', 'serve.json', 'diagnostics.json', 'network-errors.json'})
            for p in files:
                self.assertEqual(p.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(canary.encode(), p.read_bytes())
                self.assertLess(p.stat().st_size, diagnostics.MAX_PNG)
            self.assertEqual(json.loads((root / 'failure/labels.json').read_text()), [['Connect to your Wizard'], ['[redacted]']])
            self.assertIn('ConnectActivity', (root / 'failure/activity-top.txt').read_text())
            self.assertTrue(json.loads((root / 'failure/serve.json').read_text())['https'])
            self.assertEqual(calls[-1][:3], ['sudo', '-n', 'tailscale'])
            self.assertEqual(self.pixels((root / 'failure/screen.png').read_bytes()), b'\x00\xff\x00\x00\xff\x00\x00\x00\xff')

    def test_dead_adb_does_not_skip_serve_note_or_replace_stage(self):
        from types import SimpleNamespace
        import phone_diagnostics as diagnostics
        def run(argv, **kw):
            if 'tailscale' in argv:
                return SimpleNamespace(returncode=0, stdout=b'{}')
            raise diagnostics.subprocess.TimeoutExpired('private-command', 8, output=b'secret-canary')
        with tempfile.TemporaryDirectory() as d, patch.object(diagnostics.subprocess, 'run', side_effect=run):
            diagnostics.capture_failure(d, 'emulator-boot', adb='adb', serial='emulator-5682')
            status = json.loads((Path(d) / 'failure/diagnostics.json').read_text())
            for key in ('labels', 'screenshot', 'activity', 'device', 'logcat'):
                self.assertEqual(status[key], 'TimeoutExpired')
            self.assertEqual(status['stage'], 'emulator-boot')
            self.assertEqual(status['serve'], 'saved')
            self.assertNotIn('canary', json.dumps(status))

    def test_boundary_captures_before_transport_cleanup_and_survives_capture_failure(self):
        events = []
        @contextlib.contextmanager
        def transport():
            try:
                yield
            finally:
                events.append('transport-cleanup')
        with self.assertRaisesRegex(RuntimeError, '^original$'):
            with transport(), phone.failure_boundary(lambda: events.append('capture')):
                raise RuntimeError('original')
        self.assertEqual(events, ['capture', 'transport-cleanup'])
        def broken_capture():
            raise ValueError('capture')
        with self.assertRaisesRegex(RuntimeError, '^original$'):
            with phone.failure_boundary(broken_capture):
                raise RuntimeError('original')


if __name__ == '__main__':
    unittest.main()


class ShellForwardReadinessTest(unittest.TestCase):
    def test_forward_waits_by_deadline_not_try_count(self):
        # A refused connection returns instantly, so a try count gave a busy
        # Linux worker only ~10 s for the shell to come up after install.
        source = (ROOT / 'tunnel.py').read_text()
        self.assertNotIn('for _ in range(40)', source)
        self.assertIn('ready_deadline = time.monotonic() + FORWARD_READY_SECONDS', source)
        spec = importlib.util.spec_from_file_location('launch_tunnel', ROOT / 'tunnel.py')
        tunnel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tunnel)
        self.assertGreaterEqual(tunnel.FORWARD_READY_SECONDS, 120)


class ShellForwardTimeoutTest(unittest.TestCase):
    def test_callers_outlive_the_forward_deadline_and_failure_keeps_guest_state(self):
        # The callers killed tunnel.py at 120 s, before its 180 s deadline,
        # so a slow guest left no evidence at all.
        spec = importlib.util.spec_from_file_location('launch_tunnel2', ROOT / 'tunnel.py')
        tunnel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tunnel)
        snapshot = 30 * len(tunnel.GUEST_STATE_COMMANDS)
        for name in ('run.py', 'release_gate.py'):
            source = (ROOT / name).read_text()
            self.assertNotIn("], log, 120)", source)
            self.assertNotIn("('contact-' + case)], 120)", source)
            value = int(source.split('TUNNEL_TIMEOUT_SECONDS = ')[1].split()[0])
            self.assertGreater(value, tunnel.FORWARD_READY_SECONDS + snapshot)
        self.assertIn('save_guest_state(vm, evidence)', (ROOT / 'tunnel.py').read_text())

    def test_guest_state_is_bounded_and_survives_command_failures(self):
        spec = importlib.util.spec_from_file_location('launch_tunnel3', ROOT / 'tunnel.py')
        tunnel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tunnel)
        calls = []
        def fake_run(argv, **kwargs):
            calls.append(argv)
            if len(calls) == 2:
                raise tunnel.subprocess.TimeoutExpired(argv, 30)
            class Done:
                returncode = 0
                stdout = b'x' * (tunnel.GUEST_STATE_BYTES * 3)
                stderr = b''
            return Done()
        with tempfile.TemporaryDirectory() as d, patch.object(tunnel.subprocess, 'run', fake_run):
            tunnel.save_guest_state('vm', Path(d))
            text = (Path(d) / 'private-guest-state.txt').read_text()
        self.assertEqual(len(calls), len(tunnel.GUEST_STATE_COMMANDS))
        self.assertIn('[TimeoutExpired]', text)
        self.assertLess(len(text), len(tunnel.GUEST_STATE_COMMANDS) * (tunnel.GUEST_STATE_BYTES + 400))
