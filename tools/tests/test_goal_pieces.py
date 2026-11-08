"""goal_pieces.py: where each piece of a goal stands, with a fake GitHub API (no network).

    python3 -m unittest tools/tests/test_goal_pieces.py -v
"""
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import goal_pieces as gp  # noqa: E402

GOAL_BODY = """Lock in one UX for desktop and mobile.

<!-- pieces-7nov -->
**Pieces**
- [ ] humanitylabs-org/wizard-ux#1 — Closed but not ticked
- [x] humanitylabs-org/wizard-ux#2 — Ticked but still open
- [ ] humanitylabs-org/wizard-agent-service#3 — Has an open PR
- [ ] humanitylabs-org/wizard-ux#4 — Nothing moving
* [X] humanitylabs-org/wizard-ux#5: Done and ticked
- [ ] humanitylabs-org/wizard-ux#1 — repeated line is ignored
- [ ] not a piece, no issue link
- humanitylabs-org/wizard-ux#9 — no checkbox, not a piece
"""


def xref(repo, number, state="open", merged_at=None, pr=True):
    issue = {"number": number, "state": state, "title": f"PR {number}", "repository": {"full_name": repo}}
    if pr:
        issue["pull_request"] = {"merged_at": merged_at}
    return {"event": "cross-referenced", "source": {"issue": issue}}


ISSUES = {
    "repos/humanitylabs-org/wizard-os/issues/419": {"title": "UX refactor", "state": "open", "body": GOAL_BODY},
    "repos/humanitylabs-org/wizard-ux/issues/1": {"title": "One", "state": "closed"},
    "repos/humanitylabs-org/wizard-ux/issues/2": {"title": "Two", "state": "open"},
    "repos/humanitylabs-org/wizard-agent-service/issues/3": {"title": "Three", "state": "open"},
    "repos/humanitylabs-org/wizard-ux/issues/4": {"title": "Four", "state": "open"},
    "repos/humanitylabs-org/wizard-ux/issues/5": {"title": "Five", "state": "closed"},
}
TIMELINES = {
    "repos/humanitylabs-org/wizard-ux/issues/2": [
        {"event": "labeled"},
        xref("humanitylabs-org/wizard-ux", 20, state="closed", merged_at="2026-11-01T00:00:00Z"),
        xref("humanitylabs-org/wizard-ux", 20, state="closed", merged_at="2026-11-01T00:00:00Z"),
        xref("humanitylabs-org/wizard-ux", 21, state="open"),
    ],
    "repos/humanitylabs-org/wizard-agent-service/issues/3": [
        xref("humanitylabs-org/wizard-agent-service", 30, state="open"),
        xref("humanitylabs-org/wizard-agent-service", 31, state="closed"),
        xref("humanitylabs-org/wizard-os", 419, pr=False),
    ],
}


def fake_get(path):
    if path.endswith("/timeline?per_page=100"):
        return TIMELINES.get(path[: -len("/timeline?per_page=100")], [])
    if path in ISSUES:
        return ISSUES[path]
    raise gp.FetchError(f"{path}: HTTP 404")


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(gp, "gh_api", fake_get), redirect_stdout(out), redirect_stderr(err):
        code = gp.main(argv)
    return code, out.getvalue(), err.getvalue()


class ParseTest(unittest.TestCase):
    def test_reads_checklist_lines_only_once_each(self):
        pieces = gp.parse_pieces(GOAL_BODY)
        self.assertEqual([(p["repo"], p["number"]) for p in pieces], [
            ("humanitylabs-org/wizard-ux", 1),
            ("humanitylabs-org/wizard-ux", 2),
            ("humanitylabs-org/wizard-agent-service", 3),
            ("humanitylabs-org/wizard-ux", 4),
            ("humanitylabs-org/wizard-ux", 5),
        ])
        self.assertEqual([p["ticked"] for p in pieces], [False, True, False, False, True])
        self.assertEqual(pieces[0]["title"], "Closed but not ticked")
        self.assertEqual(pieces[4]["title"], "Done and ticked")

    def test_empty_body(self):
        self.assertEqual(gp.parse_pieces(None), [])
        self.assertEqual(gp.parse_pieces("no list here"), [])

    def test_linked_prs_skips_issues_and_repeats(self):
        prs = gp.linked_prs(TIMELINES["repos/humanitylabs-org/wizard-ux/issues/2"])
        self.assertEqual([(p["number"], p["state"]) for p in prs], [(20, "merged"), (21, "open")])
        prs = gp.linked_prs(TIMELINES["repos/humanitylabs-org/wizard-agent-service/issues/3"])
        self.assertEqual([(p["number"], p["state"]) for p in prs], [(30, "open"), (31, "closed")])

    def test_status_order(self):
        self.assertEqual(gp.status("closed", []), "done")
        self.assertEqual(gp.status("open", [{"state": "open"}, {"state": "merged"}]), "merged")
        self.assertEqual(gp.status("open", [{"state": "open"}, {"state": "closed"}]), "in review")
        self.assertEqual(gp.status("open", [{"state": "closed"}]), "no PR yet")


class MainTest(unittest.TestCase):
    def test_text_report_and_drift_exit(self):
        code, out, _ = run(["419"])
        self.assertEqual(code, 1)
        self.assertIn("humanitylabs-org/wizard-os#419 UX refactor", out)
        self.assertIn("done       humanitylabs-org/wizard-ux#1 One", out)
        self.assertIn("merged     humanitylabs-org/wizard-ux#2 Two  [PRs: #20 merged, #21 open]", out)
        self.assertIn("in review  humanitylabs-org/wizard-agent-service#3 Three", out)
        self.assertIn("no PR yet  humanitylabs-org/wizard-ux#4 Four  [PRs: -]", out)
        self.assertIn("DRIFT      humanitylabs-org/wizard-ux#1: issue is closed but its box", out)
        self.assertIn("DRIFT      humanitylabs-org/wizard-ux#2: ticked on the goal but the issue is still open", out)
        self.assertNotIn("DRIFT      humanitylabs-org/wizard-ux#5", out)
        self.assertIn("5 pieces: 2 done, 1 merged, 1 in review, 1 no PR yet; 2 checkbox drift", out)

    def test_json(self):
        code, out, _ = run(["419", "--json"])
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["goal"], "humanitylabs-org/wizard-os#419")
        self.assertEqual(data["drift"], 2)
        self.assertEqual([p["status"] for p in data["pieces"]], ["done", "merged", "in review", "no PR yet", "done"])

    def test_no_drift_exits_zero(self):
        body = "- [x] humanitylabs-org/wizard-ux#5 — Done\n- [ ] humanitylabs-org/wizard-ux#4 — Open\n"
        issues = dict(ISSUES)
        issues["repos/humanitylabs-org/wizard-os/issues/419"] = {"title": "G", "body": body}
        with mock.patch.dict(ISSUES, issues):
            code, out, _ = run(["419"])
        self.assertEqual(code, 0)
        self.assertIn("2 pieces: 1 done, 1 no PR yet; 0 checkbox drift", out)

    def test_goal_without_pieces(self):
        with mock.patch.dict(ISSUES, {"repos/humanitylabs-org/wizard-os/issues/419": {"title": "G", "body": "x"}}):
            code, _, err = run(["419"])
        self.assertEqual(code, 2)
        self.assertIn("no Pieces checklist", err)

    def test_github_unreadable(self):
        code, _, err = run(["999"])
        self.assertEqual(code, 2)
        self.assertIn("could not read GitHub", err)

    def test_one_unreadable_piece_does_not_hide_the_others(self):
        # Goal #420 links humanitylabs-org/wizard-shopping-history#2, which GitHub answers with 404;
        # the report used to stop there and print nothing about the other pieces.
        body = GOAL_BODY + "- [ ] humanitylabs-org/gone-repo#7 — Repo moved or private\n"
        with mock.patch.dict(ISSUES, {"repos/humanitylabs-org/wizard-os/issues/419": {"title": "UX refactor", "body": body}}):
            code, out, err = run(["419"])
            jcode, jout, _ = run(["419", "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(err, "")
        self.assertIn("done       humanitylabs-org/wizard-ux#1 One", out)
        self.assertIn("unreadable humanitylabs-org/gone-repo#7 Repo moved or private  [PRs: -]", out)
        self.assertIn("ERROR      humanitylabs-org/gone-repo#7: could not read GitHub: repos/humanitylabs-org/gone-repo/issues/7: HTTP 404", out)
        self.assertIn("6 pieces: 2 done, 1 merged, 1 in review, 1 no PR yet, 1 unreadable; 2 checkbox drift", out)
        self.assertEqual(jcode, 2)
        data = json.loads(jout)
        self.assertEqual(data["unreadable"], 1)
        self.assertEqual(data["pieces"][-1]["status"], "unreadable")
        self.assertIn("HTTP 404", data["pieces"][-1]["error"])

    def test_never_writes(self):
        src = (Path(__file__).resolve().parents[1] / "goal_pieces.py").read_text()
        for verb in ("--method", "-X", "POST", "PATCH", "PUT", "DELETE", "issue edit", "issue comment"):
            self.assertNotIn(verb, src)


if __name__ == "__main__":
    unittest.main()
