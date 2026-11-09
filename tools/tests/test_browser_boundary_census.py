"""browser_boundary_census.py: frames and native bridges that can still act as the owner (#133).

    python3 -m unittest tools/tests/test_browser_boundary_census.py -v
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import browser_boundary_census as bbc  # noqa: E402

APP_JS = """
const SANDBOX = 'allow-scripts allow-forms';
function frame(a) {
  return `<div><iframe class="appframe" ${a.probe ? `data-probe="${esc(a.url)}"` : ''} src="${esc(a.url)}" title="App"></iframe></div>`;
}
const pane = `<iframe class="ls-frame" sandbox="${SANDBOX}" title="Link"></iframe>`;
const same = `<iframe class="bad" sandbox="allow-scripts allow-same-origin"></iframe>`;
const bare = '<iframe sandbox src="x"></iframe>';
const dyn = `<iframe class="dyn" sandbox="${pick()}"></iframe>`;
"""

SERVICES_JS = """
const API = '/x', TOKENS = 'allow-scripts';
function make() {
  const frame = document.createElement('iframe'); frame.className = 'appframe'; frame.hidden = true;
  return frame;
}
function makeSafe() {
  const f = document.createElement("iframe");
  f.className = 'voice';
  f.setAttribute('sandbox', TOKENS);
  return f;
}
"""

MAIN_ACTIVITY = """
class MainActivity {
  void setup() {
    web.addJavascriptInterface(new Bridge(), "WizardOSNative");
    web.addJavascriptInterface(device, "WizardOSDevice");
  }
}
"""


def checkout(tmp: Path) -> Path:
    files = {
        "web/app.js": APP_JS,
        "web/core/app-services.js": SERVICES_JS,
        "web/vendor/lib.js": '<iframe src="vendored"></iframe>',
        "web/core/app.test.js": '<iframe src="test"></iframe>',
        "tests/qa.cjs": '<iframe src="qa"></iframe>',
        "android/app/src/main/java/ai/wizards/os/MainActivity.java": MAIN_ACTIVITY,
        "android/app/src/test/java/ai/wizards/os/BridgeTest.java": MAIN_ACTIVITY,
    }
    for rel, text in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp


class CensusTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = checkout(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def states(self):
        return {(f["file"], f["class"] or f["form"]): f["state"] for f in bbc.census(self.root)["frames"]}

    def test_classifies_each_frame(self):
        self.assertEqual(self.states(), {
            ("web/app.js", "appframe"): "open",
            ("web/app.js", "ls-frame"): "sandboxed",
            ("web/app.js", "bad"): "same-origin",
            ("web/app.js", "tag"): "sandboxed",
            ("web/app.js", "dyn"): "unknown",
            ("web/core/app-services.js", "appframe"): "open",
            ("web/core/app-services.js", "voice"): "sandboxed",
        })

    def test_resolves_constant_sandbox_values(self):
        frames = {f["class"]: f for f in bbc.census(self.root)["frames"]}
        self.assertEqual(frames["ls-frame"]["sandbox"], "allow-scripts allow-forms")
        self.assertEqual(frames["voice"]["sandbox"], "allow-scripts")

    def test_skips_vendor_and_tests(self):
        files = {f["file"] for f in bbc.census(self.root)["frames"]}
        self.assertEqual(files, {"web/app.js", "web/core/app-services.js"})

    def test_lists_android_bridges_outside_tests(self):
        bridges = bbc.census(self.root)["bridges"]
        self.assertEqual([b["name"] for b in bridges], ["WizardOSNative", "WizardOSDevice"])
        self.assertTrue(all("/src/main/" in b["file"] for b in bridges))

    def test_exit_1_and_lines_when_anything_is_open(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = bbc.main([str(self.root)])
        self.assertEqual(code, 1)
        text = out.getvalue()
        self.assertIn("frames: 7 (2 open, 1 same-origin, 1 unknown, 3 sandboxed)", text)
        self.assertIn("open        web/app.js:4 tag .appframe", text)
        self.assertIn("bridge      android/app/src/main/java/ai/wizards/os/MainActivity.java:4 WizardOSNative", text)

    def test_exit_0_when_everything_is_sandboxed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "web" / "app.js"
            p.parent.mkdir(parents=True)
            p.write_text('const f = `<iframe class="appframe" sandbox="allow-scripts"></iframe>`;\n')
            out = io.StringIO()
            with redirect_stdout(out):
                code = bbc.main([tmp, "--json"])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["problems"], 0)
            self.assertEqual(result["counts"]["sandboxed"], 1)

    def test_exit_2_without_web_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = bbc.main([tmp])
            self.assertEqual(code, 2)
            self.assertIn("not a wizard-ux checkout", err.getvalue())

    def test_only_reads(self):
        before = sorted((p.relative_to(self.root).as_posix(), p.read_text()) for p in self.root.rglob("*") if p.is_file())
        with redirect_stdout(io.StringIO()):
            bbc.main([str(self.root), "--json"])
        after = sorted((p.relative_to(self.root).as_posix(), p.read_text()) for p in self.root.rglob("*") if p.is_file())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
