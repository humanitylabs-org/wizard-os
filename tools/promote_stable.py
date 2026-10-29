#!/usr/bin/env python3
"""Release channels: cut onto latest, promote to stable only after a soak and a passed upgrade test.

    python3 tools/promote_stable.py cut 0.3.26                       # releases/latest -> 0.3.26 (testers get it)
    python3 tools/promote_stable.py promote 0.3.26 --from 0.3.25 \\
        --evidence https://github.com/humanitylabs-org/wizard-os/blob/main/docs/acceptance/update-0.3.26.md
    python3 tools/promote_stable.py promote 0.3.33 --from 0.3.25 --evidence <upgrade-test link> \\
        --fast-track --classification fix --reason "fixes only: Store 404s on fresh boxes"   # DECISIONS #82
    python3 tools/promote_stable.py check                            # the channel rules hold (tests run this)

James, 21 Oct 2026: every release goes to `releases/latest` as soon as it is cut. `releases/stable` (what fresh
installs and Automatic updates take) moves only when the release has been on latest for SOAK_HOURS and an upgrade
from an older release onto it passed on a test box (Thales). `promote` writes releases/promotions/<version>.json
with that evidence and then moves stable; it refuses when the soak or the test is missing.

DECISIONS #82 (Miguel, 22 Oct 2026, amends #75): a release that only fixes things skips the soak with
`--fast-track --classification fix --reason ...` once the same upgrade test passed (plus a fresh install where a
box allows it). DECISIONS #93 (Miguel, 24 Oct 2026, launch phase): additive feature releases may fast-track too, with
`--classification feature`; the passed upgrade test and the recorded reason are still required. The record keeps the classification and reason, so the waiver is visible and auditable.

The App Manager mirror (wizard-app-manager/releases) carries the same three things (latest, stable, promotions/)
and its updater applies the same gate (wam/updates.py promotion_problems): Automatic never installs a stable
release without a valid record. Keep the two gate functions identical.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,40}")
SOAK_HOURS = 72
FAST_TRACK_CLASSES = ("fix", "feature")   # DECISIONS #82 + #93: any release with a passed upgrade test may skip the soak
GRANDFATHERED_THROUGH = "0.3.25"   # stable when the channels split; every later promotion passes the full gate


def _key(v: str) -> tuple:
    return tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"[.+-]", v))


def _stamp(s) -> float | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def promotion_problems(rec, version: str) -> list[str]:
    """Why a promotion record does not let <version> be stable ([] = it does). Same as wam/updates.py."""
    if not isinstance(rec, dict):
        return ["no promotion record"]
    if rec.get("version") != version:
        return [f"record is for {rec.get('version')!r}, not {version}"]
    if rec.get("grandfathered"):
        ok = VERSION.fullmatch(version) and _key(version) <= _key(GRANDFATHERED_THROUGH)
        return [] if ok else [f"only releases up to {GRANDFATHERED_THROUGH} can be grandfathered"]
    out = []
    since, at = _stamp(rec.get("latest_since")), _stamp(rec.get("promoted_at"))
    if since is None or at is None:
        out.append("latest_since and promoted_at must be ISO timestamps")
    elif at < since:
        out.append("promoted_at is before latest_since")
    elif at - since < SOAK_HOURS * 3600:
        ft = rec.get("fast_track")
        if ft is None:
            out.append(f"soaked {(at - since) / 3600:.1f}h on latest; stable needs {SOAK_HOURS}h "
                       "(a release with a passed upgrade test may fast-track: DECISIONS #82, #93)")
        else:
            out += fast_track_problems(ft)
    t = rec.get("upgrade_test")
    if not isinstance(t, dict) or t.get("passed") is not True:
        out.append("no passed upgrade test")
    else:
        frm = str(t.get("from", ""))
        if t.get("to") != version or not VERSION.fullmatch(frm) or _key(frm) >= _key(version):
            out.append("upgrade test must go from an older release to this one")
        if not str(t.get("evidence", "")).strip():
            out.append("upgrade test needs evidence (a run log or report link)")
    return out


def fast_track_problems(ft) -> list[str]:
    """Why a `fast_track` block does not waive the soak ([] = it does). DECISIONS #82 and #93: a release classified as
    fix or feature, with the reason recorded, skips the soak; it still needs the passed upgrade test. Same as the other repo."""
    if not isinstance(ft, dict):
        return ["fast_track must be an object"]
    out = []
    if ft.get("classification") not in FAST_TRACK_CLASSES:
        out.append(f"fast_track is only for {'/'.join(FAST_TRACK_CLASSES)} releases; features, data-format changes and "
                   f"big UX changes soak {SOAK_HOURS}h")
    if not str(ft.get("reason", "")).strip():
        out.append("fast_track needs a reason")
    return out


def _read(p: Path) -> str | None:
    try:
        return p.read_text().strip()
    except OSError:
        return None


def check(rel: Path) -> list[str]:
    """The channel rules for a releases/ directory (canonical or mirror)."""
    errs = []
    stable, latest = _read(rel / "stable"), _read(rel / "latest")
    for name, v in (("stable", stable), ("latest", latest)):
        if not v or not VERSION.fullmatch(v):
            errs.append(f"releases/{name}: {v!r} is not a version")
        elif not (rel / f"{v}.json").is_file():
            errs.append(f"releases/{name}: {v}.json does not exist")
    if errs:
        return errs
    if _key(latest) < _key(stable):
        errs.append(f"releases/latest ({latest}) trails releases/stable ({stable})")
    try:
        rec = json.loads((rel / "promotions" / f"{stable}.json").read_text())
    except (OSError, ValueError):
        rec = None
    errs += [f"releases/stable {stable}: {p}" for p in promotion_problems(rec, stable)]
    for p in sorted((rel / "promotions").glob("*.json")):
        if not (rel / f"{p.stem}.json").is_file():
            errs.append(f"promotions/{p.name}: no release file {p.stem}.json")
            continue
        try:
            r = json.loads(p.read_text())
        except ValueError as e:
            errs.append(f"promotions/{p.name}: not JSON ({e})")
            continue
        errs += [f"promotions/{p.name}: {x}" for x in promotion_problems(r, p.stem)]
    return errs


def latest_since(version: str, rel: Path) -> str | None:
    """When releases/latest first named <version>, from git history (UTC ISO), or None."""
    try:
        out = subprocess.run(["git", "log", "--reverse", "--format=%H %cI", "--", "latest"], cwd=rel,
                             capture_output=True, text=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        sha, when = line.split(" ", 1)
        named = subprocess.run(["git", "show", f"{sha}:./latest"], cwd=rel, capture_output=True, text=True).stdout
        if named.strip() == version:
            return datetime.fromisoformat(when).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--releases", default=str(ROOT / "releases"), help="releases/ directory (default: this repo's)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cut", help="point releases/latest at a new release")
    c.add_argument("version")
    p = sub.add_parser("promote", help="record the soak + upgrade test and point releases/stable at the release")
    p.add_argument("version")
    p.add_argument("--from", dest="frm", required=True, help="the older release the upgrade test started from")
    p.add_argument("--evidence", required=True, help="link or repo path to the passed upgrade-test run")
    p.add_argument("--latest-since", help="ISO time the release went to latest (default: from git history)")
    p.add_argument("--fast-track", action="store_true",
                   help="skip the soak once the upgrade test passed (DECISIONS #82, #93); needs --classification and --reason")
    p.add_argument("--classification", choices=("fix", "feature"),
                   help="what the release changes: fix or feature (both may fast-track during launch, DECISIONS #93)")
    p.add_argument("--reason", help="why this fix cannot wait for the soak, and what was verified")
    p.add_argument("--notes", help="optional: ride-along changes and their risk, kept in the record")
    p.add_argument("--now", help=argparse.SUPPRESS)
    sub.add_parser("check", help="the channel rules hold")
    a = ap.parse_args(argv)
    rel = Path(a.releases)

    if a.cmd == "check":
        errs = check(rel)
        for e in errs:
            print(f"FAIL  {e}")
        print("channels: " + ("ok" if not errs else f"{len(errs)} problem(s)"))
        return 0 if not errs else 1

    v = a.version
    if not VERSION.fullmatch(v) or not (rel / f"{v}.json").is_file():
        print(f"no release file releases/{v}.json", file=sys.stderr)
        return 2

    if a.cmd == "cut":
        cur = _read(rel / "latest")
        if cur and VERSION.fullmatch(cur) and _key(v) < _key(cur):
            print(f"releases/latest is already {cur}; a cut never moves it back", file=sys.stderr)
            return 1
        _write(rel / "latest", v + "\n")
        print(f"latest -> {v}. Stable stays {_read(rel / 'stable')} until `promote {v}` after {SOAK_HOURS}h and a "
              "passed upgrade test.")
        return 0

    now = a.now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    since = a.latest_since or latest_since(v, rel)
    if not since:
        print(f"can't tell when {v} went to latest (no commit of releases/latest names it); cut it first, or pass "
              "--latest-since", file=sys.stderr)
        return 1
    rec = {"version": v, "latest_since": since, "promoted_at": now,
           "upgrade_test": {"from": a.frm, "to": v, "passed": True, "evidence": a.evidence}}
    if a.fast_track:
        rec["fast_track"] = {"classification": a.classification or "", "reason": (a.reason or "").strip()}
        if a.notes:
            rec["fast_track"]["notes"] = a.notes.strip()
    elif a.classification or a.reason or a.notes:
        print("--classification/--reason/--notes only go with --fast-track", file=sys.stderr)
        return 2
    problems = promotion_problems(rec, v)
    if problems:
        for x in problems:
            print(f"FAIL  {x}")
        print(f"{v} stays on latest only.")
        return 1
    _write(rel / "promotions" / f"{v}.json", json.dumps(rec, indent=2) + "\n")
    _write(rel / "stable", v + "\n")
    if _key(_read(rel / "latest") or "0.0.0") < _key(v):
        _write(rel / "latest", v + "\n")
    how = "fast-tracked fix (DECISIONS #82)" if a.fast_track else f"soaked since {since}"
    print(f"stable -> {v} ({how}; upgrade {a.frm} -> {v} passed: {a.evidence}). Mirror releases/stable "
          f"and promotions/{v}.json to wizard-app-manager/releases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
