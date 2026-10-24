"""Stage rules for tools/pr_board.py (the GitHub PR pipeline board). No network."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pr_board as b  # noqa: E402

REPO = "humanitylabs-org/wizard-ux"
PINS = {"latest": {"version": "0.3.39", "repos": {REPO: "L"}},
        "stable": {"version": "0.3.38", "repos": {REPO: "S"}}}
ANC = {("stable", REPO): {"s1"}, ("latest", REPO): {"s1", "l1"}}


def pr(state="MERGED", draft=False, sha=None, labels=()):
    return {"state": state, "isDraft": draft, "mergeCommit": {"oid": sha} if sha else None,
            "labels": {"nodes": [{"name": n} for n in labels]}}


class Stage(unittest.TestCase):
    def test_open(self):
        self.assertEqual(b.stage_of(pr("OPEN", draft=True), REPO, PINS, ANC), "Draft")
        self.assertEqual(b.stage_of(pr("OPEN"), REPO, PINS, ANC), "In review")

    def test_closed_unmerged_is_dropped(self):
        self.assertEqual(b.stage_of(pr("CLOSED"), REPO, PINS, ANC), "Dropped")

    def test_release_membership(self):
        self.assertEqual(b.stage_of(pr(sha="s1"), REPO, PINS, ANC), "On Stable")
        self.assertEqual(b.stage_of(pr(sha="l1"), REPO, PINS, ANC), "On Latest")
        self.assertEqual(b.stage_of(pr(sha="new"), REPO, PINS, ANC), "Merged")

    def test_final_stages(self):
        self.assertTrue(b.is_final("On Stable", REPO, PINS))
        self.assertTrue(b.is_final("Dropped", REPO, PINS))
        self.assertFalse(b.is_final("Merged", REPO, PINS))
        # a repo no release pins (docs, installer) ends at Merged
        self.assertTrue(b.is_final("Merged", "humanitylabs-org/wizard-os", PINS))

    def test_tier(self):
        self.assertEqual(b.tier_of(pr(labels=["tier: recommended fix"])), "Bug fix")
        self.assertEqual(b.tier_of(pr(labels=["needs: james review"])), "No tier")


if __name__ == "__main__":
    unittest.main()
