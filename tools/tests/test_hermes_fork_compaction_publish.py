"""wizard-os#726: the Hermes compaction check and the fork image publish step.

- The compaction check waits for the compacted history to reach the model (v0.22 and later use it one turn later
  than v0.21.5) and judges it by `Box.compacted`.
- The fork image workflow's publish step survives GHCR answering "not found" right after a push (the 19 Nov run
  crashed on a JSON parse of the empty read-back) and still refuses a wrong revision label.
"""
import importlib.util
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tools/acceptance/hermes/check.py"
IMAGE_YML = ROOT / "tools/hermes-fork/image.yml"
COMMIT = "b200f5bc60e31588ba2cb60e288029c4a54ba5fa"
DIGEST = "sha256:" + "1f" * 32


def load_check():
    spec = importlib.util.spec_from_file_location("hermes_acceptance_check", CHECK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def publish_step():
    """The `run:` block of the publish step, read from the workflow text (no YAML dependency)."""
    text = IMAGE_YML.read_text()
    start = text.index("- name: One multi-arch tag, digest in the summary")
    body = text[text.index("run: |\n", start) + len("run: |\n"):]
    lines = []
    for line in body.splitlines():
        if line.strip() and not line.startswith(" " * 10):
            break
        lines.append(line[10:])
    return "\n".join(lines) + "\n"


SHIM = r"""#!/bin/bash
# Fake docker for the publish step: `imagetools inspect` says "not found" for the first $FAIL calls (GHCR right
# after a push), then answers the Go templates the step uses.
n=$(cat "$STATE"); echo $((n+1)) > "$STATE"
[ "$1 $2" = "buildx imagetools" ] || exit 2
[ "$3" = create ] && exit 0
[ "$3" = inspect ] || exit 2
if [ "$n" -lt "$FAIL" ]; then echo "ERROR: $4: not found" >&2; exit 1; fi
fmt="${@: -1}"
case "$fmt" in
  *Manifest.Digest*) echo "$DIGEST" ;;
  *linux/amd64*) echo "$REV_AMD64" ;;
  *linux/arm64*) echo "$REV_ARM64" ;;
  *) exit 2 ;;
esac
"""


class CompactedTest(unittest.TestCase):
    def setUp(self):
        self.compacted = load_check().Box.compacted

    def test_summary_without_the_fact_turns_is_compacted(self):
        sent = [{"role": "system", "content": "x"},
                {"role": "user", "content": "[CONTEXT COMPACTION] - The owner asked to remember: HS-SUMMARY-FACT alpha"},
                {"role": "user", "content": "HS-ECHO settle1"}]
        self.assertTrue(self.compacted(sent))

    def test_full_history_is_not_compacted(self):
        sent = [{"role": "user", "content": "HS-FACT alpha"}, {"role": "assistant", "content": "NOTED alpha"},
                {"role": "user", "content": "HS-ECHO settle0"}]
        self.assertFalse(self.compacted(sent))

    def test_summary_next_to_a_verbatim_fact_turn_is_not_compacted(self):
        sent = [{"role": "user", "content": "HS-SUMMARY-FACT alpha"},
                {"role": "user", "content": [{"type": "text", "text": "HS-FACT bravo"}]}]
        self.assertFalse(self.compacted(sent))

    def test_recall_waits_for_settle_turns(self):
        src = CHECK.read_text()
        body = src[src.index("    def check_compaction(self):"):src.index("    def check_restart(self):")]
        self.assertLess(body.index("HS-ECHO settle"), body.index('"HS-RECALL"'))
        self.assertGreaterEqual(load_check().SETTLE_TURNS, 2)


class PublishStepTest(unittest.TestCase):
    def run_step(self, fail, rev_amd64=COMMIT, rev_arm64=COMMIT):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "bin").mkdir()
            shim = d / "bin/docker"
            shim.write_text(SHIM)
            shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
            (d / "state").write_text("0")
            work = d / "digests"
            work.mkdir()
            for name in ("aa" * 32, "bb" * 32):
                (work / name).touch()
            step = re.sub(r"sleep \$\(\(i \* 5\)\)", "sleep 0", publish_step())
            env = dict(os.environ, PATH=f"{d / 'bin'}:{os.environ['PATH']}", STATE=str(d / "state"), FAIL=str(fail),
                       DIGEST=DIGEST, REV_AMD64=rev_amd64, REV_ARM64=rev_arm64, IMAGE="ghcr.io/example/hermes-agent",
                       COMMIT=COMMIT, GITHUB_STEP_SUMMARY=str(d / "summary.md"), GITHUB_SERVER_URL="https://github.com",
                       GITHUB_REPOSITORY="example/hermes-agent", GITHUB_RUN_ID="1")
            p = subprocess.run(["bash", "-e", "-c", step], cwd=work, env=env, capture_output=True, text=True)
            summary = (d / "summary.md").read_text() if (d / "summary.md").exists() else ""
            return p, summary

    def test_not_found_right_after_the_push_is_retried(self):
        p, summary = self.run_step(fail=2)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("not found", p.stderr)
        self.assertIn(f"- digest: `{DIGEST}`", summary)
        self.assertIn(f"--digest {DIGEST}", summary)
        self.assertNotIn("Traceback", p.stderr)

    def test_registry_that_never_answers_fails_with_a_plain_error(self):
        p, summary = self.run_step(fail=99)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("could not read", p.stderr)
        self.assertNotIn("Traceback", p.stderr)
        self.assertEqual(summary, "")

    def test_wrong_revision_label_still_fails(self):
        p, summary = self.run_step(fail=0, rev_arm64="0" * 40)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("linux/arm64 revision", p.stdout + p.stderr)
        self.assertEqual(summary, "")


if __name__ == "__main__":
    unittest.main()
