"""Stage rules for tools/pr_board.py (the GitHub PR pipeline board). No network."""
import datetime as dt
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


class PullRequests(unittest.TestCase):
    def test_direct_connection_paginates_without_search_index(self):
        from unittest.mock import patch
        recent = dt.datetime.now(dt.timezone.utc).isoformat()
        def node(id, state, ended=recent, updated=recent):
            return dict(id=id, state=state, isDraft=False, closedAt=ended,
                        updatedAt=updated, mergeCommit=None)
        old = "2000-01-01T00:00:00Z"
        pages = [
            ([node("old-open", "OPEN", None, old)], True, "open-next"),
            ([node("other-open", "OPEN", None)], False, None),
            ([node("444", "CLOSED"), node("445", "CLOSED"),
              node("old-closed-recent-edit", "CLOSED", old)], True, "closed-next"),
            ([node("merged", "MERGED"), node("old", "CLOSED", old, old)], True, "stop"),
        ]
        calls = []
        def gql(query, **variables):
            self.assertNotIn("search(", query)
            self.assertIn("orderBy:{field:UPDATED_AT,direction:DESC}", query)
            self.assertEqual((variables["o"], variables["n"]), tuple(REPO.split("/")))
            calls.append(variables)
            nodes, more, cursor = pages[len(calls) - 1]
            return {"repository": {"pullRequests": {
                "nodes": nodes, "pageInfo": {"hasNextPage": more, "endCursor": cursor}}}}
        with patch.object(b, "gql", side_effect=gql):
            prs = b.pull_requests(REPO)
        self.assertEqual([p["id"] for p in prs], ["old-open", "other-open", "444", "445", "merged"])
        self.assertEqual([c["after"] for c in calls], [None, "open-next", None, "closed-next"])
        self.assertEqual([c["states"] for c in calls], [["OPEN"], ["OPEN"],
                                                       ["CLOSED", "MERGED"], ["CLOSED", "MERGED"]])
        self.assertEqual([b.stage_of(p, REPO, PINS, ANC) for p in prs[2:4]], ["Dropped", "Dropped"])

    def test_empty_repository(self):
        from unittest.mock import patch
        response = {"repository": {"pullRequests": {
            "nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}}
        with patch.object(b, "gql", return_value=response) as gql:
            self.assertEqual(b.pull_requests(REPO), [])
        self.assertEqual(gql.call_count, 2)


if __name__ == "__main__":
    unittest.main()
