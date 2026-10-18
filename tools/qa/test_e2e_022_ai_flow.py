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


if __name__ == '__main__':
    unittest.main()
