"""Regression coverage for strict, legacy and changed-line style admission."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('check_style', Path(__file__).with_name('check_style.py'))
style = importlib.util.module_from_spec(spec)
spec.loader.exec_module(style)


class StyleCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, content):
        (self.root / 'app.css').write_text(content)

    def test_strict_and_warn(self):
        self.write('a{color:#fff;font-size:12px;font-family:Arial}\n')
        self.assertEqual(len(style.scan(self.root, {}, strict=True)), 3)
        self.assertTrue(all(r['error'] for r in style.scan(self.root, {}, strict=True)))
        self.assertFalse(any(r['error'] for r in style.scan(self.root, {})))

    def test_tokens_comments_and_literal_fallback(self):
        self.write('/* #fff */ a{color:var(--wz-text);font-size:var(--wz-text-sm);font-family: var(--wz-font-ui)}')
        self.assertEqual(style.scan(self.root, {}, strict=True), [])
        self.write('a{color:var(--wz-text,#fff)}')
        self.assertEqual(len(style.scan(self.root, {}, strict=True)), 1)

    def test_kit_hash_and_reviewed_exception(self):
        p = self.root / 'wizard-ui.css'; p.write_text('approved')
        policy = {'assets': {'wizard-ui.css': {'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}}}
        self.assertEqual(style.scan(self.root, policy, strict=True), [])
        p.write_text('drift')
        self.assertEqual(style.scan(self.root, policy, strict=True)[0]['rule'], 'kit-drift')
        self.write('a{color:#fff}')
        policy['exceptions'] = [{'path': 'app.css', 'sha256': hashlib.sha256((self.root/'app.css').read_bytes()).hexdigest(), 'reason': 'Reviewed product artwork, Robert owns this exception'}]
        self.assertEqual(len(style.scan(self.root, policy, strict=True)), 1)  # kit still drifts
        self.write('a{color:#000}')
        self.assertEqual(len(style.scan(self.root, policy, strict=True)), 2)
        policy['exceptions'][0]['reason'] = ''
        with self.assertRaises(ValueError): style.scan(self.root, policy)

    def test_change_line_ratchet_and_untracked(self):
        def git(*a): return subprocess.check_output(['git','-C',str(self.root),*a], stderr=subprocess.DEVNULL)
        git('init'); git('config','user.name','Fixture'); git('config','user.email','fixture@example.invalid')
        self.write('a{color:#fff}\nb{color:var(--wz-text)}\n')
        git('add','.'); git('commit','-m','Legacy fixture')
        self.write('a{color:#fff}\nb{font-size:12px}\n')
        rows = style.scan(self.root, {}, base='HEAD')
        self.assertEqual([(r['rule'],r['error']) for r in rows], [('literal-colour',False),('px-type',True)])
        (self.root/'new.css').write_text('c{color:rgb(1,2,3)}')
        self.assertEqual(sum(r['error'] for r in style.scan(self.root, {}, base='HEAD')),2)
        with self.assertRaises(subprocess.CalledProcessError): style.scan(self.root, {}, base='missing-base')


    def test_no_self_referential_skin_alias(self):
        self.write('.st-root { --wz-text: var(--wz-text); }')
        self.assertEqual(style.scan(self.root, {}, strict=True)[0]['rule'], 'cyclic-token')
        self.write('.st-root { color: var(--wz-text); }')
        self.assertEqual(style.scan(self.root, {}, strict=True), [])

    def test_hex_like_dom_ids_are_not_colours(self):
        self.write('#feed { color:var(--wz-text) }')
        (self.root / 'app.js').write_text("$('#feed'); document.querySelector('#bad');")
        (self.root / 'index.html').write_text('<a href="#abc">Go</a>')
        self.assertEqual(style.scan(self.root, {}, strict=True), [])
        self.write('a{color:#feed}')
        self.assertEqual(len(style.scan(self.root, {}, strict=True)), 1)

    def test_shell_export_has_no_global_resets_or_alias_cycles(self):
        import runpy
        source = Path(__file__).parent
        generated = runpy.run_path(str(source / 'generate_shell.py'))['outputs']()
        controls = generated['controls.css']
        self.assertNotIn(':root', controls)
        self.assertNotRegex(controls, r'(?m)^button\s*\{')
        self.assertIn('.wz-button[hidden]', controls)
        self.assertIn('--wz-text: var(--ink)', generated['shell-tokens.css'])
        self.assertNotIn('--ink:', generated['shell-tokens.css'])


if __name__ == '__main__': unittest.main()
