"""check_channel_drift.py: wizard-os channels vs the public mirror, with fake HTTP (no network).

    python3 -m unittest tools/tests/test_check_channel_drift.py -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_channel_drift as ccd  # noqa: E402

MIRROR = "https://mirror.example.test/releases"
GOOD_RECORD = json.dumps({"version": "0.3.25", "grandfathered": True}).encode()


def releases(tmp: Path, latest="0.3.27", stable="0.3.25", versions=("0.3.25", "0.3.26", "0.3.27")) -> Path:
    rel = tmp / "releases"
    (rel / "promotions").mkdir(parents=True)
    (rel / "latest").write_text(latest + "\n")
    (rel / "stable").write_text(stable + "\n")
    for v in versions:
        (rel / f"{v}.json").write_text(json.dumps({"version": v}))
    (rel / "promotions" / "0.3.25.json").write_bytes(GOOD_RECORD)
    return rel


def mirror_of(rel: Path, **override):
    """Files the fake mirror serves: an exact copy of rel, then overrides (None = 404)."""
    files = {p.relative_to(rel).as_posix(): p.read_bytes() for p in rel.rglob("*") if p.is_file()}
    files.update(override)

    def get(url):
        assert url.startswith(MIRROR + "/"), url
        b = files.get(url[len(MIRROR) + 1:])
        if b is None:
            raise ccd.NotFound(url)
        return b
    return get


class ChannelDrift(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.rel = releases(Path(self._t.name))

    def tearDown(self):
        self._t.cleanup()

    def run_check(self, **override):
        return ccd.check(self.rel, MIRROR, get=mirror_of(self.rel, **override), history=False)

    def test_identical_mirror_is_ok(self):
        rep = self.run_check()
        self.assertTrue(rep["ok"], rep["problems"])
        self.assertEqual(rep["mirror_pointers"], {"latest": "0.3.27", "stable": "0.3.25"})
        self.assertIn("Stable 0.3.25 trails Latest 0.3.27 by 2 release(s)", rep["info"][0])

    def test_mirror_latest_behind(self):
        rep = self.run_check(latest=b"0.3.26\n")
        self.assertFalse(rep["ok"])
        self.assertTrue(any("latest: the mirror names 0.3.26, wizard-os names 0.3.27" in p and "stay behind" in p
                            for p in rep["problems"]), rep["problems"])

    def test_missing_release_json_on_mirror(self):
        rep = self.run_check(**{"0.3.27.json": None})
        self.assertTrue(any("mirror has no releases/0.3.27.json" in p for p in rep["problems"]), rep["problems"])

    def test_release_json_not_byte_identical(self):
        rep = self.run_check(**{"0.3.25.json": b'{"version": "0.3.25", "x": 1}'})
        self.assertTrue(any("0.3.25.json on the mirror is not byte-identical" in p for p in rep["problems"]))

    def test_missing_promotion_record_means_automatic_skips(self):
        rep = self.run_check(**{"promotions/0.3.25.json": None})
        self.assertTrue(any("Automatic updates skip Stable 0.3.25" in p for p in rep["problems"]), rep["problems"])

    def test_invalid_promotion_record_on_mirror(self):
        bad = json.dumps({"version": "0.3.25", "upgrade_test": {"passed": False}}).encode()
        rep = self.run_check(**{"promotions/0.3.25.json": bad})
        self.assertTrue(any("fails the gate" in p for p in rep["problems"]), rep["problems"])

    def test_missing_pointer_on_mirror(self):
        rep = self.run_check(stable=None)
        self.assertTrue(any("mirror has no releases/stable" in p for p in rep["problems"]), rep["problems"])

    def test_unreachable_mirror_raises(self):
        def down(url):
            raise ccd.FetchError("down")
        with self.assertRaises(ccd.FetchError):
            ccd.check(self.rel, MIRROR, get=down, history=False)

    def test_same_release_on_both_channels(self):
        (self.rel / "latest").write_text("0.3.25\n")
        rep = self.run_check()
        self.assertTrue(rep["ok"], rep["problems"])
        self.assertEqual(rep["info"], ["Stable and Latest both name 0.3.25"])

    def test_main_exit_codes(self):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        from unittest import mock
        args = ["--releases", str(self.rel), "--mirror", MIRROR]

        def down(url):
            raise ccd.FetchError("down")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with mock.patch.object(ccd, "http_get", mirror_of(self.rel)):
                self.assertEqual(ccd.main(args), 0)
                self.assertEqual(ccd.main(args + ["--json"]), 0)
            with mock.patch.object(ccd, "http_get", mirror_of(self.rel, latest=b"0.3.20")):
                self.assertEqual(ccd.main(args), 1)
            with mock.patch.object(ccd, "http_get", down):
                self.assertEqual(ccd.main(args), 2)

if __name__ == "__main__":
    unittest.main()
