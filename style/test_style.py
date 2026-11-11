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

    def test_skin_layers_warn_but_structural_rules_fail(self):
        skin = self.root / 'web/skins/obsidian'; skin.mkdir(parents=True)
        (skin / 'skin.css').write_text('html[data-skin="obsidian"] .x{color:#e8e4ff;font-family:Inter;font-size:13px}\n')
        tweak = self.root / 'web/tweaks/owner'; tweak.mkdir(parents=True)
        (tweak / 'tweak.css').write_text('.y{background:rgba(0,0,0,.4)}\n')
        policy = {'skin_layers': ['web/skins/', 'web/tweaks/']}
        rows = style.scan(self.root, policy, strict=True)
        self.assertEqual(len(rows), 4)
        self.assertFalse(any(r['error'] for r in rows))
        # Without the reviewed scope the same files fail like app chrome.
        self.assertTrue(all(r['error'] for r in style.scan(self.root, {}, strict=True)))
        # Cyclic tokens are still bugs inside a skin layer.
        (skin / 'skin.css').write_text('html{--wz-accent: var(--wz-accent, #fff)}\n')
        rows = style.scan(self.root, policy, strict=True)
        self.assertTrue(any(r['rule'] == 'cyclic-token' and r['error'] for r in rows))
        # App chrome outside the layers is unaffected.
        self.write('a{color:#fff}')
        self.assertTrue(any(r['path'] == 'app.css' and r['error'] for r in style.scan(self.root, policy, strict=True)))
        for bad in (['web/skins'], ['/abs/'], ['**/skins/'], ['./web/']):
            with self.assertRaises(ValueError): style.scan(self.root, {'skin_layers': bad})

    def test_generated_vendor_bundle_warns_only_while_ci_drift_checks_it(self):
        def git(*a): return subprocess.check_output(['git','-C',str(self.root),*a], stderr=subprocess.DEVNULL)
        git('init'); git('config','user.name','Fixture'); git('config','user.email','fixture@example.invalid')
        vendor = self.root / 'web/vendor'; vendor.mkdir(parents=True)
        bundle = vendor / 'live-preview.js'
        bundle.write_text('var a=1;\nvar t={".cm-button":{color:"#fff"}};\n')
        wf = self.root / '.github/workflows'; wf.mkdir(parents=True)
        (wf / 'quality.yml').write_text('jobs:\n  t:\n    steps:\n      - run: npm run build:editor\n      - run: git diff --exit-code -- web/vendor\n')
        self.write('a{color:var(--wz-text)}\n')
        git('add','.'); git('commit','-m','Base with drift check')
        policy = {'generated_vendor': ['web/vendor/']}
        # A rebuild renames identifiers file-wide, so the library theme line changes.
        bundle.write_text('var b=1;\nvar u={".cm-button":{color:"#fff",background:"rgba(0,0,0,.1)"}};\n')
        rows = style.scan(self.root, policy, base='HEAD')
        self.assertTrue(rows and not any(r['error'] for r in rows))
        self.assertTrue(all(r.get('generated') for r in rows))
        # Without the policy scope, or without a drift check in CI, the same lines fail.
        self.assertTrue(any(r['error'] for r in style.scan(self.root, {}, base='HEAD')))
        (wf / 'quality.yml').write_text('jobs:\n  t:\n    steps:\n      - run: npm run build:editor\n')
        self.assertTrue(any(r['error'] for r in style.scan(self.root, policy, base='HEAD')))
        # App CSS and app JS outside the vendor folder are still checked as before.
        (wf / 'quality.yml').write_text('      - run: git diff --exit-code -- web/vendor\n')
        self.write('a{color:#fff}\n')
        (self.root / 'web/app.js').write_text('el.style.color="#fff"\n')
        rows = style.scan(self.root, policy, base='HEAD')
        self.assertEqual(sorted(r['path'] for r in rows if r['error']), ['app.css', 'web/app.js'])
        # A drift check under a different folder does not cover web/vendor.
        self.write('a{color:var(--wz-text)}\n'); (self.root / 'web/app.js').unlink()
        (wf / 'quality.yml').write_text('      - run: git diff --exit-code -- web/vendor-other\n')
        self.assertTrue(any(r['error'] for r in style.scan(self.root, policy, base='HEAD')))
        # Kit copies inside the vendor folder still drift-fail.
        (wf / 'quality.yml').write_text('      - run: git diff --exit-code -- web/vendor\n')
        (vendor / 'wizard-ui.css').write_text('drift')
        self.assertTrue(any(r['rule'] == 'kit-drift' and r['error'] for r in style.scan(self.root, policy, base='HEAD')))
        for bad in (['web/vendor'], ['/abs/'], ['**/vendor/'], ['./web/']):
            with self.assertRaises(ValueError): style.scan(self.root, {'generated_vendor': bad})

    def test_generated_vendor_skip_cannot_be_granted_by_the_pr_itself(self):
        def git(*a): return subprocess.check_output(['git','-C',str(self.root),*a], stderr=subprocess.DEVNULL)
        git('init'); git('config','user.name','Fixture'); git('config','user.email','fixture@example.invalid')
        self.write('a{color:var(--wz-text)}\n')
        git('add','.'); git('commit','-m','Base without drift check')
        vendor = self.root / 'web/vendor'; vendor.mkdir(parents=True)
        (vendor / 'x.js').write_text('var t={color:"#fff"};\n')
        wf = self.root / '.github/workflows'; wf.mkdir(parents=True)
        (wf / 'ci.yml').write_text('      - run: git diff --exit-code -- web/vendor\n')
        rows = style.scan(self.root, {'generated_vendor': ['web/vendor/']}, base='HEAD')
        self.assertTrue(any(r['path'] == 'web/vendor/x.js' and r['error'] for r in rows))
        # Without a base (local inventory) the working-tree workflows decide.
        rows = style.scan(self.root, {'generated_vendor': ['web/vendor/']}, strict=True)
        self.assertFalse(any(r['path'] == 'web/vendor/x.js' and r['error'] for r in rows))

    def test_drift_checked_paths(self):
        f = style.drift_checked_paths
        self.assertEqual(f(['run: git diff --exit-code -- web/vendor/ ./dist/a.js "x/y"\n']), {'web/vendor', 'dist/a.js', 'x/y'})
        self.assertEqual(f(['run: git diff --stat web/vendor\n', 'git diff --exit-code $DIR\n']), set())
        self.assertEqual(f(['      - run: npm ci && git diff --quiet web/vendor && echo ok # web/other\n']), {'web/vendor'})
        # Comments, quoted output and step names are not drift checks.
        self.assertEqual(f(['# git diff --exit-code -- web/vendor\n',
                            '      - run: echo "git diff --exit-code -- web/vendor"\n',
                            '      - run: echo "x && git diff --exit-code -- web/vendor"\n',
                            '      - name: git diff --exit-code web/vendor\n']), set())
        # Shell line continuations are joined.
        self.assertEqual(f(['        run: |\n          git diff --exit-code -- \\\n            web/vendor\n']), {'web/vendor'})

    def test_generated_vendor_coverage_compared_per_side(self):
        def git(*a): return subprocess.check_output(['git','-C',str(self.root),*a], stderr=subprocess.DEVNULL)
        git('init'); git('config','user.name','Fixture'); git('config','user.email','fixture@example.invalid')
        vendor = self.root / 'web/vendor'; vendor.mkdir(parents=True)
        (vendor / 'live-preview.js').write_text('var a=1;\n')
        wf = self.root / '.github/workflows'; wf.mkdir(parents=True)
        (wf / 'q.yml').write_text('      - run: git diff --exit-code -- web/vendor\n')
        git('add','.'); git('commit','-m','Base')
        # The PR tightens the check to the exact file and rebuilds the bundle.
        (wf / 'q.yml').write_text('      - run: git diff --exit-code -- ./web/vendor/live-preview.js\n')
        (vendor / 'live-preview.js').write_text('var t={color:"#fff"};\n')
        rows = style.scan(self.root, {'generated_vendor': ['web/vendor/']}, base='HEAD')
        self.assertTrue(rows and not any(r['error'] for r in rows))

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

    def test_sticky_sheet_close_is_opaque(self):
        # Sheet text scrolls under the sticky close control; a translucent fill lets it show through.
        import re
        css = Path(__file__).with_name('ui.css').read_text()
        rule = re.search(r'\.wz-sheet-x \{([^}]*)\}', css)[1]
        self.assertRegex(rule, r'background:[^;]*var\(--wz-panel\)')


if __name__ == '__main__': unittest.main()
