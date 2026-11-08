"""check_bug_forms.py: which repos lack the #418 bug form, with a fake GitHub API (no network).

    python3 -m unittest tools/tests/test_check_bug_forms.py -v
"""
import base64
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_bug_forms as cbf  # noqa: E402

FULL = """name: Bug
description: Something is wrong or worse than it should be
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: Update to the latest build first.
  - type: textarea
    id: happens
    attributes:
      label: What happens
  - type: textarea
    attributes:
      label: What should happen
  - type: textarea
    attributes:
      label: How to see it
  - type: textarea
    attributes:
      label: Done when
  - type: textarea
    attributes:
      label: Screenshot
  - type: input
    attributes:
      label: Version and device
"""

GOAL = """name: Goal
labels:
  - goal
body:
  - type: textarea
    attributes:
      label: What happens
"""


def enc(text):
    return {"content": base64.b64encode(text.encode()).decode()}


def fake(repos):
    """repos: {name: {filename: text} or None (no template folder)}."""
    def get(path):
        if path.startswith("orgs/"):
            return [{"name": n, "archived": False} for n in repos] + [{"name": "old", "archived": True}]
        _, org, repo, _, *rest = path.split("/")
        files = repos.get(repo)
        sub = "/".join(rest)
        if files is None:
            raise cbf.NotFound(path)
        if sub == cbf.FORM_DIR:
            return [{"type": "file", "path": f"{cbf.FORM_DIR}/{n}"} for n in files]
        name = sub[len(cbf.FORM_DIR) + 1:]
        if name in files:
            return enc(files[name])
        raise cbf.NotFound(path)
    return get


class ParseForm(unittest.TestCase):
    def test_full_form_passes(self):
        f = cbf.parse_form(FULL)
        self.assertTrue(cbf.is_bug_form(f))
        self.assertEqual(cbf.missing_fields(f), [])

    def test_block_list_labels_and_goal_is_not_bug(self):
        f = cbf.parse_form(GOAL)
        self.assertEqual(f["labels"], ["goal"])
        self.assertFalse(cbf.is_bug_form(f))

    def test_labels_match_loosely(self):
        text = FULL.replace("label: What happens", "label: 'What happens?'").replace(
            "label: Version and device", 'label: "Version & device"')
        self.assertEqual(cbf.missing_fields(cbf.parse_form(text)), ["Version and device"])

    def test_markdown_template_is_not_a_form(self):
        self.assertFalse(cbf.is_bug_form(cbf.parse_form("---\nname: Bug\nlabels: bug\n---\nWhat happens\n")))


class CheckRepo(unittest.TestCase):
    def test_states(self):
        get = fake({
            "good": {"bug.yml": FULL, "config.yml": "blank_issues_enabled: false\n"},
            "none": None,
            "goal-only": {"goal.yml": GOAL},
            "partial": {"bug.yaml": FULL.replace("      label: Screenshot\n", "      label: Picture\n")},
        })
        r = {n: cbf.check_repo(n, get) for n in ("good", "none", "goal-only", "partial")}
        self.assertTrue(r["good"]["ok"])
        self.assertEqual(r["good"]["form"], ".github/ISSUE_TEMPLATE/bug.yml")
        self.assertIn("no .github/ISSUE_TEMPLATE", r["none"]["problem"])
        self.assertIn("no bug issue form", r["goal-only"]["problem"])
        self.assertEqual(r["partial"]["missing"], ["Screenshot"])
        self.assertFalse(r["partial"]["ok"])


class Main(unittest.TestCase):
    def run_main(self, argv, get):
        buf = io.StringIO()
        with mock.patch.object(cbf, "gh_api", get), redirect_stdout(buf):
            code = cbf.main(argv)
        return code, buf.getvalue()

    def test_all_ok_exit_0_and_archived_skipped(self):
        code, out = self.run_main(["--json"], fake({"a": {"bug.yml": FULL}, "b": {"bug.yml": FULL}}))
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual([r["repo"] for r in data["repos"]], ["a", "b"])
        self.assertEqual(data["missing"], 0)

    def test_missing_exit_1(self):
        code, out = self.run_main(["--repo", "a", "--repo", "b"], fake({"a": {"bug.yml": FULL}, "b": None}))
        self.assertEqual(code, 1)
        self.assertIn("MISS b:", out)
        self.assertIn("1/2 repos have the bug form", out)

    def test_fetch_error_exit_2(self):
        def boom(path):
            raise cbf.FetchError("down")
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            code, _ = self.run_main([], boom)
        self.assertEqual(code, 2)


class OwnFormsTest(unittest.TestCase):
    """wizard-os's own issue forms (#418) must pass the checker other repos are measured by."""

    FORMS = Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE"

    def test_bug_form_has_the_five_fields(self):
        form = cbf.parse_form((self.FORMS / "bug.yml").read_text(encoding="utf-8"))
        self.assertTrue(cbf.is_bug_form(form))
        self.assertEqual(cbf.missing_fields(form), [])

    def test_goal_form_is_a_form_but_not_the_bug_form(self):
        form = cbf.parse_form((self.FORMS / "goal.yml").read_text(encoding="utf-8"))
        self.assertTrue(form["is_form"])
        self.assertEqual(form["labels"], ["goal"])
        self.assertIn("Done when", form["fields"])
        self.assertFalse(cbf.is_bug_form(form))

    def test_check_repo_passes_on_these_files(self):
        files = {p.name: p.read_text(encoding="utf-8") for p in self.FORMS.glob("*.yml")}

        def get(path):
            if path.endswith("/contents/" + cbf.FORM_DIR):
                return [{"type": "file", "path": f"{cbf.FORM_DIR}/{n}"} for n in sorted(files)]
            name = path.rsplit("/", 1)[1]
            return {"content": base64.b64encode(files[name].encode()).decode()}

        r = cbf.check_repo("wizard-os", get)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["form"], f"{cbf.FORM_DIR}/bug.yml")


if __name__ == "__main__":
    unittest.main()
