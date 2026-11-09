"""Published release records are immutable (wizard-os#416).

Boxes install releases/<v>.json from the wizard-app-manager mirror, release notes cite their sha256, and
tools/check_channel_drift.py requires the mirror to stay byte-identical to wizard-os. So once a release or promotion
record is published, nobody edits it: not a spelling sweep, not a reformat. releases/SHA256SUMS lists every published
record; the release train appends each new cut and promotion.

    python3 -m unittest tools/tests/test_published_releases.py -v
"""
import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REL = ROOT / "releases"
sys.path.insert(0, str(HERE.parent))
import release_train as rt  # noqa: E402

LINE = re.compile(r"([0-9a-f]{64})  ((?:promotions/)?[0-9][0-9A-Za-z.+-]*\.json)")


def sums() -> dict[str, str]:
    out = {}
    for n, line in enumerate((REL / "SHA256SUMS").read_text().splitlines(), 1):
        m = LINE.fullmatch(line)
        if not m:
            raise AssertionError(f"releases/SHA256SUMS line {n} is not '<sha256>  <v>.json': {line!r}")
        out[m.group(2)] = m.group(1)
    return out


class PublishedReleasesAreImmutable(unittest.TestCase):
    def test_every_listed_record_is_unchanged(self):
        changed = [name for name, want in sums().items()
                   if not (REL / name).is_file() or hashlib.sha256((REL / name).read_bytes()).hexdigest() != want]
        self.assertEqual(changed, [], "published release records changed or vanished; restore their original bytes "
                         "(boxes and the mirror read them byte-for-byte). A new release gets a new version instead.")

    def test_the_channel_pointers_and_hermes_lock_are_not_listed(self):
        # latest/stable move on purpose; hermes-lock.json and phone/ are not release records.
        self.assertFalse({"latest", "stable", "hermes-lock.json", "phone/latest.json"} & set(sums()))

    def test_stable_and_its_promotion_are_listed(self):
        stable = (REL / "stable").read_text().strip()
        self.assertIn(f"{stable}.json", sums())
        self.assertIn(f"promotions/{stable}.json", sums())

    def test_the_train_appends_each_new_record_once(self):
        with tempfile.TemporaryDirectory() as d:
            rel = Path(d)
            (rel / "promotions").mkdir()
            (rel / "0.3.200.json").write_text('{"version": "0.3.200"}\n')
            (rel / "promotions" / "0.3.200.json").write_text('{"version": "0.3.200"}\n')
            (rel / rt.SUMS).write_text("a" * 64 + "  0.3.199.json\n")
            rt.record_published(rel, "0.3.200.json")
            rt.record_published(rel, "0.3.200.json")
            rt.record_published(rel, "promotions/0.3.200.json")
            lines = (rel / rt.SUMS).read_text().splitlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[1], f"{rt.sha(rel / '0.3.200.json')}  0.3.200.json")
            self.assertTrue(all(LINE.fullmatch(x) for x in lines))

    def test_the_train_records_cuts_and_promotions(self):
        src = (HERE.parent / "release_train.py").read_text()
        self.assertIn('record_published(wt / "releases", f"{V}.json")', src)
        self.assertIn('f"releases/{SUMS}"', src)
        self.assertIn('record_published(wt / "releases", f"promotions/{V}.json")', src)

    def test_the_spelling_guard_leaves_releases_alone(self):
        src = (HERE / "test_wizardos_spelling.py").read_text()
        self.assertIn("^releases/", src)


if __name__ == "__main__":
    unittest.main()
