"""check_mac_downloads.py: feed/page/OS-feed agreement, with fake HTTP (no network).

    python3 -m unittest tools/tests/test_check_mac_downloads.py -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_mac_downloads as cmd  # noqa: E402

BASE = "https://downloads.example.test"


def appcast(*items):
    body = "".join(
        f"<item><title>Wizard {v}</title><sparkle:version>{b}</sparkle:version>"
        f"<sparkle:shortVersionString>{v}</sparkle:shortVersionString>"
        f'<enclosure url="{BASE}/mac/{b}/Wizard-{b}.zip" type="application/octet-stream" length="{n}"/></item>'
        for v, b, n in items)
    return ('<?xml version="1.0" encoding="utf-8"?><!-- sparkle-sign-warning --><rss '
            'xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" version="2.0">'
            f"<channel><title>Wizard updates</title>{body}</channel></rss>")


def page(*dmgs):
    return "<html>" + "".join(f'<a href="{BASE}/mac/{b}/Wizard-{v}.dmg">Wizard {v}</a>' for v, b in dmgs) + "</html>"


OS = json.dumps({"version": "0.4.0", "bytes": 30, "parts": [
    {"url": "0.4.0/wizard-os-0.4.0.tar.xz.part00", "bytes": 20},
    {"url": "0.4.0/wizard-os-0.4.0.tar.xz.part01", "bytes": 10}]})


def fake(files, heads=None):
    heads = heads or {}

    def get(url):
        if url not in files:
            raise cmd.FetchError(f"{url}: 404")
        return files[url]

    def head(url):
        return heads.get(url, (200, None))
    return get, head


def site(feed, landing, os_feed=OS, heads=None):
    return fake({f"{BASE}/mac/appcast.xml": feed, f"{BASE}/index.html": landing, f"{BASE}/os/latest.json": os_feed},
                heads)


class Agreement(unittest.TestCase):
    def test_feed_and_page_on_the_same_build_is_clean(self):
        get, head = site(appcast(("0.7.2", 309, 100)), page(("0.7.1", 308), ("0.7.2", 309)))
        r = cmd.check(BASE, get, head)
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["os"], {"version": "0.4.0", "parts": 2, "bytes": 30})

    def test_feed_behind_page_is_reported(self):
        """try-wizard #73: the live feed served 308 while the page offered 309."""
        get, head = site(appcast(("0.7.1", 308, 100)), page(("0.7.1", 308), ("0.7.2", 309)))
        r = cmd.check(BASE, get, head)
        self.assertEqual(len(r["problems"]), 1, r["problems"])
        self.assertIn("update feed lags the download page", r["problems"][0])
        self.assertIn("build 309", r["problems"][0])

    def test_page_behind_feed_is_reported(self):
        get, head = site(appcast(("0.7.3", 310, 100)), page(("0.7.2", 309)))
        self.assertIn("download page lags", cmd.check(BASE, get, head)["problems"][0])


class Files(unittest.TestCase):
    def test_missing_archive_and_dmg_and_size_mismatch(self):
        heads = {f"{BASE}/mac/309/Wizard-309.zip": (200, 99),
                 f"{BASE}/mac/309/Wizard-0.7.2.dmg": (404, None),
                 f"{BASE}/os/0.4.0/wizard-os-0.4.0.tar.xz.part00": (403, None)}
        get, head = site(appcast(("0.7.2", 309, 100)), page(("0.7.2", 309)), heads=heads)
        problems = cmd.check(BASE, get, head)["problems"]
        self.assertTrue(any("99 bytes, feed says 100" in p for p in problems), problems)
        self.assertTrue(any("newest DMG" in p and "404" in p for p in problems), problems)
        self.assertTrue(any("first Wizard OS part answers 403" in p for p in problems), problems)

    def test_os_parts_must_add_up(self):
        bad = json.dumps({"version": "0.4.0", "bytes": 31, "parts": [{"url": "a", "bytes": 30}]})
        get, head = site(appcast(("0.7.2", 309, 100)), page(("0.7.2", 309)), os_feed=bad)
        self.assertIn("add up to 30 bytes, it says 31", cmd.check(BASE, get, head)["problems"][0])

    def test_empty_feed_and_page(self):
        get, head = site(appcast(), "<html></html>")
        problems = cmd.check(BASE, get, head)["problems"]
        self.assertIn("mac/appcast.xml lists no update", problems)
        self.assertIn("index.html links no Mac DMG", problems)

    def test_unreadable_feed_raises(self):
        get, head = site("not xml", page(("0.7.2", 309)))
        with self.assertRaises(cmd.FetchError):
            cmd.check(BASE, get, head)


if __name__ == "__main__":
    unittest.main()
