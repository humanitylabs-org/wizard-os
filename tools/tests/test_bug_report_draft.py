"""bug_report_draft.py: owner's words + wizard report -> issue draft, with privacy canaries (goal #417).

    python3 -m unittest tools/tests/test_bug_report_draft.py -v
"""
import io
import json
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bug_report_draft as brd  # noqa: E402

UNITS = brd.UNITS
COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64


def good_report():
    """Same shape as wizard-app-manager wizard-cli `cmd_report`."""
    return {"schema": "wizard-report-v1", "cli_version": "0.3.41", "python_version": "3.12.3",
            "os": {"id": "ubuntu", "version": "24.04"},
            "release": {"version": "0.3.41", "status": "drift", "mismatches": 1,
                        "identities": [{"kind": "commit", "expected": COMMIT, "observed": "c" * 40, "ok": False}]},
            "expected_pins": {k: {"commit": COMMIT, "digest": DIGEST} for k in brd.COMPONENTS},
            "services": {UNITS[0]: "active", UNITS[1]: "failed", UNITS[2]: "active"},
            "recent_errors": {u: {"available": True, "classes": {c: 2 for c in brd.ERROR_CLASSES}} for u in UNITS},
            "updates": {"mode": "auto", "channel": "latest"},
            "privacy": brd.PRIVACY_NOTE}


CANARIES = ["owner@example.com", "ghp_CANARYtoken1234567890abcdef", "sk-CANARY0123456789abcdef",
            "my-box.tail1234.ts.net", "100.101.102.103", "https://user:pw@host.example/x?token=CANARYQ",
            "/home/canaryuser/secret.txt", "PrivateCanaryText", "Zm9vYmFyCANARY0123456789base64=="]


class ProjectReport(unittest.TestCase):
    def test_good_report_survives_unchanged(self):
        clean, dropped = brd.project_report(good_report())
        self.assertEqual(dropped, 0)
        self.assertEqual(clean, good_report())

    def test_other_schema_refused(self):
        with self.assertRaises(ValueError):
            brd.project_report({"schema": "wizard-report-v2"})
        with self.assertRaises(ValueError):
            brd.project_report(["not", "a", "dict"])

    def test_canaries_in_every_field_never_survive(self):
        bad = good_report()
        for i, canary in enumerate(CANARIES):
            bad[f"extra_{i}"] = canary
        bad["cli_version"] = CANARIES[0]
        bad["python_version"] = CANARIES[7]
        bad["os"] = {"id": CANARIES[3], "version": CANARIES[4], "hostname": CANARIES[3]}
        bad["release"]["version"] = CANARIES[5]
        bad["release"]["status"] = CANARIES[7]
        bad["release"]["notes"] = CANARIES[6]
        bad["release"]["identities"].append({"kind": "commit", "expected": CANARIES[1], "observed": COMMIT,
                                             "name": CANARIES[7]})
        bad["release"]["identities"].append({"kind": CANARIES[7]})
        bad["expected_pins"]["wizard-ux"]["url"] = CANARIES[5]
        bad["expected_pins"][CANARIES[6]] = {"commit": COMMIT}
        bad["services"][UNITS[0]] = CANARIES[2]
        bad["services"][CANARIES[3]] = "active"
        bad["recent_errors"][UNITS[0]]["lines"] = [CANARIES[8]]
        bad["recent_errors"][UNITS[0]]["classes"]["timeout"] = CANARIES[0]
        bad["recent_errors"][UNITS[0]]["classes"][CANARIES[7]] = 1
        bad["updates"] = {"mode": CANARIES[1], "channel": CANARIES[2], "token": CANARIES[2]}
        bad["privacy"] = CANARIES[7]
        clean, dropped = brd.project_report(bad)
        text = json.dumps(clean)
        for canary in CANARIES:
            self.assertNotIn(canary, text)
        self.assertNotIn("Canary", text.replace("canary", ""))
        self.assertGreater(dropped, 15)
        self.assertEqual(clean["services"][UNITS[0]], "unavailable")
        self.assertEqual(clean["updates"], {"mode": "ask", "channel": "stable"})
        self.assertEqual(set(clean), set(good_report()))

    def test_wrong_types_do_not_crash(self):
        bad = good_report()
        bad.update(os="ubuntu", release=None, expected_pins=[1], services=7, recent_errors="x", updates=True)
        clean, dropped = brd.project_report(bad)
        self.assertGreater(dropped, 0)
        self.assertEqual(clean["release"]["status"], "unavailable")
        self.assertEqual(clean["release"]["identities"], [])


class ScrubWords(unittest.TestCase):
    def test_each_canary_shape_removed(self):
        words = "It broke. " + " and ".join(c for c in CANARIES if c != "PrivateCanaryText")
        text, counts = brd.scrub_words(words)
        for canary in CANARIES:
            if canary != "PrivateCanaryText":
                self.assertNotIn(canary, text)
        self.assertNotIn("CANARY", text)
        for kind in ("url", "email", "tailnet address", "ip address", "home path", "token"):
            self.assertIn(kind, counts)

    def test_plain_words_untouched(self):
        words = "The chat froze after I sent a voice note on version 0.3.41, twice today."
        self.assertEqual(brd.scrub_words(words), (words, {}))

    def test_long_words_are_capped(self):
        text, _ = brd.scrub_words("word " * 5000)
        self.assertLessEqual(len(text), brd.MAX_WORDS)


class BuildDraft(unittest.TestCase):
    def test_draft_shape(self):
        d = brd.build_draft("The chat froze. It happened twice.", good_report())
        self.assertEqual(d["title"], "In-app report: The chat froze.")
        self.assertEqual(d["labels"], ["bug", "from: in-app report"])
        self.assertIs(d["sent"], False)
        self.assertIn("> The chat froze. It happened twice.", d["body"])
        self.assertIn("Services not active: wizard-troubleshooter.service", d["body"])
        self.assertIn("Release: 0.3.41 (drift, 1 pin mismatches)", d["body"])
        self.assertIn('"schema": "wizard-report-v1"', d["body"])

    def test_title_is_scrubbed_and_short(self):
        d = brd.build_draft("Mail to owner@example.com fails " + "x" * 200, None)
        self.assertNotIn("owner@example.com", d["title"])
        self.assertLessEqual(len(d["title"]), len("In-app report: ") + brd.TITLE_MAX)
        self.assertIn("No diagnostics attached.", d["body"])

    def test_empty_words_refused(self):
        with self.assertRaises(ValueError):
            brd.build_draft("   ", good_report())

    def test_no_canary_reaches_the_draft(self):
        bad = good_report()
        bad["leak"] = CANARIES
        d = brd.build_draft(" ".join(c for c in CANARIES if c != "PrivateCanaryText"), bad)
        out = json.dumps(d)
        for canary in CANARIES:
            self.assertNotIn(canary, out)


class Main(unittest.TestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = brd.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_json_and_never_touches_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text(json.dumps(good_report()))
            with mock.patch.object(socket, "socket", side_effect=AssertionError("network used")):
                code, out, _ = self.run_main("--words", "It froze", "--report", str(path), "--json")
        self.assertEqual(code, 0)
        self.assertIs(json.loads(out)["sent"], False)

    def test_text_mode_says_not_sent(self):
        code, out, err = self.run_main("--words", "Mail owner@example.com broke")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("Title: In-app report:"))
        self.assertIn("Not sent.", err)
        self.assertIn("1 email", err)

    def test_bad_report_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text("{not json")
            self.assertEqual(self.run_main("--words", "x", "--report", str(path))[0], 2)
            path.write_text(json.dumps({"schema": "other"}))
            self.assertEqual(self.run_main("--words", "x", "--report", str(path))[0], 2)


if __name__ == "__main__":
    unittest.main()
