"""The weekly evidence helper is read-only and fails closed; it is not a promotion command."""
from datetime import datetime, timedelta, timezone
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hermes_candidate_report as h

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
SHA = "a" * 40


def release(tag, age, **extra):
    return {"tag_name": tag, "published_at": (NOW - timedelta(days=age)).isoformat(),
            "html_url": "https://example.invalid/release", "draft": False, "prerelease": False, **extra}


class CandidateReport(unittest.TestCase):
    def test_seven_full_days_not_calendar_date(self):
        old = release("v0.21.6", 8)
        candidate, young = h.choose([release("v0.22.5", 6.99), old], NOW)
        self.assertEqual(candidate, old)
        self.assertEqual(young, ["v0.22.5"])
        candidate, young = h.choose([release("v0.22.5", 7)], NOW)
        assert candidate is not None
        self.assertEqual(candidate["tag_name"], "v0.22.5")

    def test_draft_prerelease_and_mutable_labels_cannot_be_candidates(self):
        candidate, young = h.choose([release("v0.22.5", 8, prerelease=True),
                                    release("v0.22.4", 9, draft=True), release("stable", 10),
                                    release("v0.22.3-rc1", 11)], NOW)
        self.assertIsNone(candidate)

    def test_no_false_ready_from_a_record_filename(self):
        blocked = h.gates({"commit": SHA}, {"commit": SHA}, "docs/acceptance/hermes-v0.22.2.md", [])
        self.assertTrue(any("exact image digest" in b for b in blocked))
        self.assertTrue(any("James" in b for b in blocked))
        self.assertTrue(any("soak" in b for b in blocked))

    def test_missing_or_mismatched_image_provenance_blocks(self):
        for img in ({"commit": None}, {"commit": "b" * 40}, {"error": "404"}):
            blocked = h.gates({"commit": SHA}, img, None, [])
            self.assertTrue(any("image" in b for b in blocked), blocked)

    def test_search_pages_deduplicate_and_filter_without_hiding_risk(self):
        issue = {"number": 1, "title": "session loss", "body": "", "html_url": "https://example.invalid/1"}
        irrelevant = {"number": 2, "title": "logo", "body": "", "html_url": "https://example.invalid/2"}
        with patch.object(h, "gh", side_effect=[{"total_count": 2, "items": [issue]},
                                               {"total_count": 2, "items": [irrelevant]}]):
            self.assertEqual(h.issues("v0.22.2"), [{"number": 1, "title": "session loss", "url": issue["html_url"]}])

    def test_incomplete_search_is_not_a_clean_bill_of_health(self):
        with patch.object(h, "gh", return_value={"incomplete_results": True, "total_count": 0, "items": []}):
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                h.issues("v0.22.2")

    def test_network_failure_returns_explicit_hold(self):
        snapshot = h.ROOT / "releases" / ((h.ROOT / "releases" / "stable").read_text().strip() + ".json")
        with patch.object(h, "gh", side_effect=RuntimeError("fixture unavailable")):
            out = h.report(snapshot, NOW)
        self.assertEqual(out["decision"], "HOLD")
        self.assertIsNone(out["approval"])
        self.assertIn("assessment incomplete", out["blocked"][0])
        self.assertTrue(h.markdown(out).startswith("HOLD\n"))


if __name__ == "__main__":
    unittest.main()
