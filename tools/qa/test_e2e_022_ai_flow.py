#!/usr/bin/env python3
"""Control-plane unit tests for the AI-flow runner: pure helpers only.
No VM, Docker, network, model, or browser execution."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load('e2e_022_ai_flow')
guest = load('e2e_022_ai_guest')

APP_SKILL = '\n'.join(['---', 'name: defleur-video', 'description: Edit videos with DeFleur.', '---', '# DeFleur video editing'] + [
    f'{n}. Call the DeFleur MCP tool start_edit with the imported file id and wait for job {n} to finish completely.'
    for n in range(1, 30)])
POINTER = '\n'.join(['---', 'name: wizard-job-video-editing', 'description: Use when the owner asks for video editing.', '---',
                     'The installed DeFleur app (defleur-video) owns this workflow.',
                     'Load its app-owned skill and use its MCP server; do not copy its steps here.'])


class MediaDiffTests(unittest.TestCase):
    def test_new_and_changed_videos_only(self):
        before = {'Videos/a/src.mp4': [10, 1], 'Videos/b/old.mov': [5, 1]}
        after = {'Videos/a/src.mp4': [10, 1], 'Videos/b/old.mov': [6, 2], 'Videos/a/src-edited.mp4': [20, 3],
                 'Videos/a/notes.txt': [1, 3]}
        self.assertEqual(guest.new_videos(before, after), ['Videos/a/src-edited.mp4', 'Videos/b/old.mov'])

    def test_no_change_is_empty(self):
        listing = {'Videos/a/src.mp4': [10, 1]}
        self.assertEqual(guest.new_videos(listing, dict(listing)), [])

    def test_json_roundtrip_lists_compare_equal(self):
        before = json.loads(json.dumps({'x.mp4': (1, 2)}))
        self.assertEqual(guest.new_videos(before, {'x.mp4': [1, 2]}), [])

    def test_valid_video(self):
        self.assertTrue(guest.valid_video({'format': {'duration': '9.5'}, 'streams': [{'codec_type': 'video'}]}))
        self.assertFalse(guest.valid_video({'format': {'duration': '0'}, 'streams': [{'codec_type': 'video'}]}))
        self.assertFalse(guest.valid_video({'format': {'duration': '3'}, 'streams': [{'codec_type': 'audio'}]}))
        self.assertFalse(guest.valid_video({}))

    def test_clip_phrase_adds_folder_only_when_ambiguous(self):
        one = {'Videos/ui-proof-1/release-acceptance-source.mp4': [1, 1]}
        self.assertEqual(guest.clip_phrase('Videos/ui-proof-1/release-acceptance-source.mp4', one),
                         'release-acceptance-source.mp4')
        two = {**one, 'Videos/ui-proof-2/release-acceptance-source.mp4': [1, 1]}
        self.assertEqual(guest.clip_phrase('Videos/ui-proof-2/release-acceptance-source.mp4', two),
                         'ui-proof-2/release-acceptance-source.mp4')


class SkillClassifierTests(unittest.TestCase):
    def test_short_pointer_passes(self):
        v = guest.classify_skill(POINTER, APP_SKILL)
        self.assertTrue(v['relevant'] and v['pointer'], v)

    def test_identical_copy_fails(self):
        v = guest.classify_skill(APP_SKILL, APP_SKILL)
        self.assertFalse(v['pointer'])
        self.assertTrue(any('identical' in r for r in v['reasons']))

    def test_inlined_body_fails_even_when_short(self):
        body = POINTER + '\n' + '\n'.join(APP_SKILL.splitlines()[5:12])
        v = guest.classify_skill(body, APP_SKILL)
        self.assertFalse(v['pointer'])
        self.assertGreaterEqual(v['copied_app_lines'], 5)

    def test_long_skill_fails(self):
        long = POINTER + '\n' + '\n'.join(f'local note {n}' for n in range(80))
        self.assertFalse(guest.classify_skill(long, APP_SKILL)['pointer'])

    def test_unrelated_skill_ignored(self):
        self.assertEqual(guest.classify_skill('# Cooking\nBoil water.', APP_SKILL), {'relevant': False})

    def test_skills_diff_verdicts(self):
        before = {'a/SKILL.md': {'sha256': '1', 'bytes': 1}}
        self.assertEqual(guest.skills_diff(before, dict(before), APP_SKILL)['verdict'], 'pass: no DeFleur skill copy written')
        pointer = {**before, 'video/SKILL.md': {'sha256': '2', 'bytes': 2, 'text': POINTER}}
        d = guest.skills_diff(before, pointer, APP_SKILL)
        self.assertTrue(d['pass'])
        self.assertEqual(list(d['added']), ['video/SKILL.md'])
        self.assertNotIn('text', json.dumps(d['added']))
        copied = {**before, 'video/SKILL.md': {'sha256': '3', 'bytes': 3, 'text': APP_SKILL}}
        self.assertFalse(guest.skills_diff(before, copied, APP_SKILL)['pass'])
        changed = {'a/SKILL.md': {'sha256': '9', 'bytes': 9, 'text': APP_SKILL}}
        d = guest.skills_diff(before, changed, APP_SKILL)
        self.assertEqual(d['defleur_skill_verdicts'][0]['change'], 'changed')
        self.assertFalse(d['pass'])


class ConfigAndAccountsTests(unittest.TestCase):
    def test_model_keys_mapping_only_two_keys(self):
        text = 'model:\n  default: claude-opus-5-5\n  provider: "claude-subscription-directsdk-experimental"\n  api_key: SECRET\nother: 1\n'
        self.assertEqual(guest.model_keys(text), {'shape': 'mapping', 'provider': 'claude-subscription-directsdk-experimental',
                                                  'default': 'claude-opus-5-5'})
        self.assertNotIn('SECRET', json.dumps(guest.model_keys(text)))

    def test_model_keys_null_and_absent(self):
        self.assertEqual(guest.model_keys('model: null\n')['default'], None)
        self.assertEqual(guest.model_keys('x: 1\n')['shape'], 'absent')
        self.assertEqual(guest.model_keys('model:\n  default: ~\n')['default'], None)

    def test_account_status(self):
        payload = {'accounts': [{'id': 'claude-subscription', 'name': 'Claude subscription', 'status': 'connected', 'email': 'x'}]}
        self.assertEqual(guest.account_status(payload), {'status': 'connected', 'matched': 'claude', 'count': 1})
        with self.assertRaises(guest.CheckError):
            guest.account_status({'accounts': []})


class SanitizerTests(unittest.TestCase):
    def test_keys_and_values_redacted(self):
        raw = {'Authorization': 'Bearer abcdefghijklmnop', 'nested': [{'api_key': 'x', 'note': 'key sk-ant-abcdefghijkl123'}],
               'cookie': 'c=1', 'model': 'claude-opus-5-5', 'status': 'connected', 'dotenv_file': True,
               'jwt': 'eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0NTY3ODkw.SflKxwRJSMeKKF2QT4'}
        out = host.sanitize(raw)
        text = json.dumps(out)
        for secret in ('abcdefghijklmnop', 'sk-ant-', 'c=1', 'eyJhbGci'):
            self.assertNotIn(secret, text)
        self.assertEqual(out['model'], 'claude-opus-5-5')
        self.assertIs(out['dotenv_file'], True)
        self.assertEqual(out['nested'][0]['api_key'], '[redacted]')

    def test_verdict_and_status_keys_survive(self):
        out = host.sanitize({'pass': True, 'status': 'pass', 'stages': [{'stage': 'x', 'pass': False}], 'passed': 1})
        self.assertEqual(out, {'pass': True, 'status': 'pass', 'stages': [{'stage': 'x', 'pass': False}], 'passed': 1})

    def test_save_is_private_and_sanitized(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'r.json'
            host.save(p, {'token': 'SECRET'})
            self.assertNotIn('SECRET', p.read_text())
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)


class HostTests(unittest.TestCase):
    def test_only_named_guest_on_thales(self):
        with patch.object(host.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(RuntimeError, 'Thales/macOS-only'):
                host.validate_target(Path('/Volumes/ThalesMedia/wizard-os/e2e-022'), host.GUESTS[0])
        with patch.object(host.platform, 'system', return_value='Darwin'):
            with self.assertRaises(RuntimeError):
                host.validate_target(Path('/Volumes/ThalesMedia/wizard-os/e2e-022'), 'production')
            with self.assertRaises(RuntimeError):
                host.validate_target(Path('/Users/owner/e2e-022'), host.GUESTS[0])

    def test_verdicts_all_pass_shape(self):
        ok = {'status': 'pass'}
        pre = {'stages': [{'stage': k, **ok} for k in host.PREFLIGHT_REQUIRED] + [
            {'stage': 'image-digests-readback', 'status': 'pass', 'result': {'hermes_digest_match': True, 'missing': []}},
            {'stage': 'ai-accounts-status-connected', 'status': 'pass', 'result': {'status': 'connected'}}]}
        route = {'model': host.MODEL, 'provider': host.PROVIDER, 'require_model_lock': True}
        browser = {'stages': [
            {'stage': 'chat-ready', 'status': 'pass', 'session': route, 'runBody': route, 'modelSelection': {'method': 'ui-picker'},
             'back': [{'view': 'chat-ready-thread', 'inWizard': True}]},
            {'stage': 'defleur-edit', 'status': 'pass', 'session': {**route, 'model': host.MODEL + '[1m]'}, 'outcome': 'output-appeared',
             'back': [{'view': 'defleur-thread', 'inWizard': True}]}], 'blockedAccountsNavigations': [], 'screenshotsSkipped': []}
        final = {'stages': [{'stage': 'defleur-output-video', 'status': 'pass', 'result': {'chosen': {'relative_path': 'x.mp4'}}},
                            {'stage': 'skills-pointer-not-copy', 'status': 'pass', 'result': {'verdict': 'pass: no DeFleur skill copy written'}}]}
        files = {'stages': [{'stage': 'files-output-back', 'status': 'pass', 'back': [{'view': 'files-output-folder', 'inWizard': True}]}]}
        v = host.verdicts(pre, browser, final, files)
        self.assertTrue(all(x['pass'] for x in v.values()), v)
        browser['stages'][0]['session'] = {'model': 'claude-sonnet-5', 'provider': host.PROVIDER}
        self.assertFalse(host.verdicts(pre, browser, final, files)['1-chat']['pass'])

    def test_verdicts_missing_inputs_fail_closed(self):
        v = host.verdicts(None, None, None, None)
        self.assertFalse(any(x['pass'] for x in v.values()), v)


class AlongsideClaudeTests(unittest.TestCase):
    def test_one_shot_argv_has_only_owner_mount_and_local_pinned_image(self):
        c = load('e2e_022_alongside_claude')
        image = 'sha256:' + 'a' * 64
        expected = ['sudo', '-n', 'docker', 'run', '-d', '--rm', '--pull=never', '--user', '501:20',
                    '--read-only', '--tmpfs', '/tmp', '--label', c.LABEL,
                    '-e', 'AI_ACCOUNTS_CLAUDE_DIR=/claude', '-e', 'AI_ACCOUNTS_BIND=0.0.0.0',
                    '-e', 'AI_ACCOUNTS_PORT=8795', '-v', '/home/owner/.claude:/claude',
                    '-p', '127.0.0.1:8797:8795', '--name', c.NAME, image]
        self.assertEqual(c.container_argv(['sudo', '-n', 'docker'], Path('/home/owner'), 501, 20, image), expected)
        with self.assertRaises(c.CheckError):
            c.container_argv(['docker'], Path('/home/owner'), 501, 20, 'latest')
        for forbidden in ('auth.json', '.credentials', 'WIZARD_MCP_TOKEN', 'API_KEY', '--privileged', '--env-file'):
            self.assertNotIn(forbidden, ' '.join(expected))

    def test_status_is_allowlisted_and_masks_domain(self):
        c = load('e2e_022_alongside_claude')
        result = c.status_payload({'loggedIn': True, 'authMethod': 'claude.ai', 'subscriptionType': 'max',
                                   'email': 'private@company.example', 'accessToken': 'DO-NOT-EMIT'})
        self.assertEqual(result, {'logged_in': True, 'plan': 'Claude Max', 'email_domain': 'c***.example'})
        self.assertNotIn('private', json.dumps(result))
        self.assertFalse(c.status_payload({'loggedIn': True, 'authMethod': 'api_key'})['logged_in'])

    def test_guest_port_option_and_security_logic_unchanged(self):
        import ast
        import hashlib
        w = load('e2e_022_signin_window')
        base = ['hold', '--root', '/Volumes/ThalesMedia/wizard-os/e2e-022',
                '--vm', 'alongside-022-amd64', '--playwright', '/installed/playwright']
        self.assertEqual(w.parser().parse_args(base).guest_port, 8795)
        self.assertEqual(w.parser().parse_args(base + ['--guest-port', '8797']).guest_port, 8797)
        # Audited os-runner original: AST fingerprints exclude whitespace only.
        expected = {
            'Relay': '4eb300c11ece3f1858af352309862d8f40ef397c33638aa4733ddf060692b540',
            'serve_handler_ours': '09f7837434edebf7f8ac9a543fe55b671ebe272b9bb1cca5771dac56aa78fb06',
            'without_port': 'ec845c351d3e2a2941d1af860b31e3e1ca6f2d75c8056ecde7f57d3a6896e9f7',
            'remove_own_handler': 'f7b09beb562e078cddcf204bf91fbfaa80af434b2c15e095adb02c15e83356a6',
            'claude_status': 'c5ff7be2611638bfb0e810b52b0a329e7c418c67fb373c9d0b6c79b525f6b48c',
        }
        tree = ast.parse((HERE / 'e2e_022_signin_window.py').read_text())
        found = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
                 for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in expected}
        self.assertEqual(found, expected)

    def test_alongside_stages_and_unlink_are_required(self):
        required = host.preflight_required('alongside-022-amd64')
        self.assertNotIn('agent-link', required)
        self.assertIn('agent-link', host.preflight_required('fresh-022-candidate-amd64'))
        self.assertEqual(set(required), set(host.PREFLIGHT_REQUIRED) - {'agent-link'})
        pre = {'stages': [{'stage': k, 'status': 'pass'} for k in required] + [
            {'stage': 'image-digests-readback', 'status': 'pass',
             'result': {'hermes_source_match': True, 'missing': []}}]}
        out = host.verdicts(pre, None, None, None, 'alongside-022-amd64')
        self.assertTrue(out['0-preflight']['pass'])
        self.assertTrue(out['0-image-digests']['pass'])
        self.assertFalse(out['6-alongside-unlink']['pass'])
        final = {'stages': [{'stage': 'alongside-unlink', 'status': 'pass', 'result': {'left_linked': True}}]}
        self.assertTrue(host.verdicts(pre, None, final, None, 'alongside-022-amd64')['6-alongside-unlink']['pass'])
        self.assertFalse(host.verdicts(pre, None, None, None)['0-preflight']['pass'])
        self.assertFalse(host.verdicts(pre, None, None, None)['0-image-digests']['pass'])

    def test_unlink_compares_setup_bytes_and_relinks_even_on_mismatch(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import Mock
        for match, mapping in ((True, True), (False, True), (True, False), (False, False)):
            with self.subTest(match=match, mapping=mapping), tempfile.TemporaryDirectory() as td:
                home = Path(td)
                work = home / 'work'
                work.mkdir()
                state = home / '.e2e-022-alongside-claude'
                state.mkdir()
                baseline = {'config.yaml': 'setup-cfg-hash', '.env': 'setup-dotenv-hash'}
                setup = {'original_prelink': {'config.yaml': 'original-cfg', '.env': 'original-dotenv'},
                         'setup_unlinked': baseline, 'wizard_plugin_ref': 'a' * 40}
                (state / 'setup.json').write_text(json.dumps(setup))
                (work / 'owner-model-restore.json').write_text(json.dumps(
                    {'present': True, 'mapping': mapping, 'scalar': None if mapping else 'owner-old-model',
                     'keys': {'default': None} if mapping else {}}))
                c = Mock()
                c.link_info.side_effect = [dict(linked=True, baseline=baseline), dict(linked=False), dict(linked=True)]
                c.hashes.side_effect = [{'config.yaml': 'model-step', '.env': 'linked'},
                                       baseline if match else {'config.yaml': 'drift', '.env': baseline['.env']},
                                       {'config.yaml': 'linked-again', '.env': 'linked'}]
                c.wizard.return_value = {'ok': True}
                x = SimpleNamespace(home=home, work=work, owner_claude=c, save=Mock())
                with patch.object(guest, 'alongside_apps', return_value={'linked': True}):
                    if match:
                        result = guest.alongside_unlink(x)
                        self.assertTrue(result['owner_setup_preserved'])
                        self.assertFalse(result['equals_original_prelink'])
                        self.assertTrue(result['left_linked'])
                    else:
                        with self.assertRaisesRegex(guest.CheckError, 'setup-only byte hashes'):
                            guest.alongside_unlink(x)
                self.assertEqual([a.args[1] for a in c.wizard.call_args_list], ['unlink', 'link'])
                if mapping:
                    c.hermes.assert_any_call(home, 'config', 'unset', 'model.provider')
                    c.hermes.assert_any_call(home, 'config', 'set', 'model.default', 'null')
                else:
                    c.hermes.assert_called_once_with(home, 'config', 'set', 'model', 'owner-old-model', '--force')
                x.save.assert_called_once()

    def test_binary_install_is_idempotent_and_rejects_bad_integrity(self):
        import tempfile
        from unittest.mock import Mock
        c = load('e2e_022_alongside_claude')
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            dest = home / '.local/bin/claude'
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b'unit-test-only-not-a-real-binary')
            previous = {'version': c.VERSION, 'npm_integrity': c.NPM_INTEGRITY,
                        'binary_sha256': c.sha(dest)}
            with patch.object(c.urllib.request, 'urlopen') as fetch:
                self.assertFalse(c.install_claude(home, previous)['changed'])
                fetch.assert_not_called()
            bad = Mock()
            bad.read.return_value = b'invalid-untrusted-archive'
            with patch.object(c.urllib.request, 'urlopen', return_value=bad), patch.object(c, 'run') as child:
                with self.assertRaisesRegex(c.CheckError, 'integrity mismatch'):
                    c.install_claude(home, {})
                child.assert_not_called()
            self.assertEqual(dest.read_bytes(), b'unit-test-only-not-a-real-binary')

    def test_gateway_path_detection_never_overrides_a_different_binary(self):
        import tempfile
        from types import SimpleNamespace
        c = load('e2e_022_alongside_claude')
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            output = SimpleNamespace(stdout='PATH=/usr/bin:/bin')
            with patch.object(c, 'run', return_value=output), patch.object(c.shutil, 'which', return_value=None):
                self.assertFalse(c.gateway_claude_on_path(home))
            with patch.object(c, 'run', return_value=output), patch.object(c.shutil, 'which', return_value='/other/claude'):
                with self.assertRaisesRegex(c.CheckError, 'different Claude'):
                    c.gateway_claude_on_path(home)
            with patch.object(c, 'run', return_value=output), patch.object(c.shutil, 'which', return_value=str(home / '.local/bin/claude')):
                self.assertTrue(c.gateway_claude_on_path(home))

    def test_older_link_journal_uses_native_metadata_pin(self):
        import tempfile
        c = load('e2e_022_alongside_claude')
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / '.wizard-os').mkdir()
            (home / '.hermes/plugins').mkdir(parents=True)
            (home / '.wizard-os/linked.json').write_text(json.dumps({'hermes_home': str(home / '.hermes'), 'linked': True}))
            metadata = home / '.hermes/plugins/.install-metadata.json'
            metadata.write_text(json.dumps({'wizard-os': {'pinned': True, 'revision': 'b' * 40}}))
            self.assertEqual(c.link_info(home)['plugin_ref'], 'b' * 40)
            metadata.write_text('{}')
            self.assertIsNone(c.link_info(home)['plugin_ref'])

    def test_immutable_pin_values_match_acceptance_route(self):
        c = load('e2e_022_alongside_claude')
        self.assertEqual(c.VERSION, '2.1.296')
        self.assertEqual(c.PLUGIN_REF, 'ef73726cfaf2fa0ee041e55572f406e2c24fed83')
        self.assertEqual(c.PLUGIN_NAME, guest.PROVIDER)
        self.assertEqual(guest.PROVIDER, host.PROVIDER)
        self.assertEqual(guest.MODEL, host.MODEL)
        self.assertEqual(len(c.PLUGIN_FILES), 9)

    def test_no_command_prints_credentials(self):
        import ast
        for name in ('e2e_022_alongside_claude.py', 'e2e_022_signin_window.py', 'e2e_022_ai_guest.py'):
            text = (HERE / name).read_text()
            for n in ast.walk(ast.parse(text)):
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    self.assertNotRegex(n.value, r'(?:cat|print|read_text|read_bytes).*?(?:\.credentials|auth\.json|mcp-token|WIZARD_MCP_TOKEN)')
            self.assertNotIn("'serve', 'reset'", text)


if __name__ == '__main__':
    unittest.main()
