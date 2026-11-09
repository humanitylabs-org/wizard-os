#!/usr/bin/env python3
"""Check that what boxes read for updates matches the canonical release channels (goal wizard-os #416).

    python3 tools/check_channel_drift.py              # wizard-os releases/ vs the public installer mirror
    python3 tools/check_channel_drift.py --json       # same, as one JSON object
    python3 tools/check_channel_drift.py --mirror URL # another mirror with the same layout

Boxes never read wizard-os: `get.sh` and the App Manager's updater read the public mirror
(`wizard-app-manager/main/releases`, see releases/README.md "Channels" and "Publication is a separate gate").
If the mirror lags or differs, every box on that channel silently stays behind. This answers one question:
would a box on Latest or on Stable get exactly the release wizard-os says it should?

Problems it reports (exit 1):
- the mirror's `latest` or `stable` pointer names a different release than wizard-os (boxes drift behind);
- the release JSON a pointer names is missing on the mirror, or not byte-identical (sha256) to wizard-os;
- the mirror's `promotions/<stable>.json` is missing, differs from wizard-os, or fails the promotion gate
  (`promote_stable.promotion_problems`). Automatic skips a Stable pointer without a valid record, so those
  boxes never move even though Stable did.

It also says, as information only, how far Stable trails Latest (number of release files between them and,
when git history is available, how long Latest has been latest). Trailing during the soak is normal.

It only reads (anonymous GETs of small text files). It never writes, mirrors or promotes anything, and
nothing runs it automatically. Exit 0 = consistent, 1 = problems found (each printed), 2 = the mirror
could not be reached or wizard-os releases/ is unreadable.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIRROR = "https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/main/releases"
TIMEOUT = 30
CHANNELS = ("latest", "stable")


def _promote_stable():
    spec = importlib.util.spec_from_file_location("promote_stable", Path(__file__).resolve().parent / "promote_stable.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ps = _promote_stable()


class FetchError(Exception):
    pass


class NotFound(FetchError):
    pass


def http_get(url: str) -> bytes:
    """Bytes at url. 404 raises NotFound; any other failure raises FetchError."""
    req = urllib.request.Request(url, headers={"User-Agent": "wizard-os-check-channel-drift",
                                               "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFound(f"{url}: 404") from e
        raise FetchError(f"{url}: HTTP {e.code}") from e
    except (urllib.error.URLError, OSError) as e:
        raise FetchError(f"{url}: {e}") from e


def _sha(b: bytes | None) -> str | None:
    return hashlib.sha256(b).hexdigest() if b is not None else None


def _local(rel: Path, name: str) -> bytes | None:
    try:
        return (rel / name).read_bytes()
    except OSError:
        return None


def check(rel: Path, mirror: str, get=None, now: float | None = None, history: bool = True) -> dict:
    """The drift report. `get(url) -> bytes` (raises NotFound / FetchError) so tests need no network."""
    get = get or http_get
    mirror = mirror.rstrip("/")
    problems: list[str] = []
    info: list[str] = []
    canon: dict[str, str] = {}
    seen: dict[str, str | None] = {}

    def remote(name: str) -> bytes | None:
        try:
            return get(f"{mirror}/{name}")
        except NotFound:
            return None

    for ch in CHANNELS:
        raw = _local(rel, ch)
        v = raw.decode().strip() if raw is not None else ""
        if not ps.VERSION.fullmatch(v):
            raise FetchError(f"wizard-os releases/{ch}: {v!r} is not a version")
        canon[ch] = v
        m = remote(ch)
        seen[ch] = m.decode("utf-8", "replace").strip() if m is not None else None

    for ch in CHANNELS:
        want, got = canon[ch], seen[ch]
        if got is None:
            problems.append(f"{ch}: the mirror has no releases/{ch}; boxes on {ch} cannot see any release")
        elif got != want:
            problems.append(f"{ch}: the mirror names {got}, wizard-os names {want}; "
                            f"boxes on {ch} {'stay behind' if _behind(got, want) else 'get a release wizard-os does not name'}")
        name = f"{want}.json"
        here, there = _local(rel, name), remote(name)
        if here is None:
            problems.append(f"{ch}: wizard-os has no releases/{name}")
        elif there is None:
            problems.append(f"{ch}: the mirror has no releases/{name}; boxes on {ch} cannot install {want}")
        elif _sha(here) != _sha(there):
            problems.append(f"{ch}: releases/{name} on the mirror is not byte-identical to wizard-os "
                            f"({hashlib.sha256(there).hexdigest()[:12]} vs {hashlib.sha256(here).hexdigest()[:12]})")

    stable = canon["stable"]
    pname = f"promotions/{stable}.json"
    here, there = _local(rel, pname), remote(pname)
    if there is None:
        problems.append(f"stable: the mirror has no releases/{pname}; Automatic updates skip Stable {stable}")
    else:
        if here is not None and _sha(here) != _sha(there):
            problems.append(f"stable: releases/{pname} on the mirror is not byte-identical to wizard-os")
        try:
            rec = json.loads(there)
        except ValueError:
            rec = None
        for p in ps.promotion_problems(rec, stable):
            problems.append(f"stable: mirror promotion record for {stable} fails the gate ({p}); "
                            "Automatic updates skip it")

    latest = canon["latest"]
    if ps._key(latest) > ps._key(stable):
        between = sorted((p.stem for p in rel.glob("*.json")
                          if ps.VERSION.fullmatch(p.stem) and ps._key(stable) < ps._key(p.stem) <= ps._key(latest)),
                         key=ps._key)
        line = f"Stable {stable} trails Latest {latest} by {len(between)} release(s)"
        since = ps.latest_since(latest, rel) if history else None
        if since:
            t = datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp()
            hours = ((now if now is not None else time.time()) - t) / 3600
            line += f"; {latest} has been latest for {hours:.0f}h (soak {ps.SOAK_HOURS}h unless fast-tracked)"
        info.append(line)
    else:
        info.append(f"Stable and Latest both name {stable}")

    return {"mirror": mirror, "canonical": canon, "mirror_pointers": seen,
            "ok": not problems, "problems": problems, "info": info}


def _behind(got: str, want: str) -> bool:
    try:
        return ps._key(got) < ps._key(want)
    except ValueError:
        return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--mirror", default=DEFAULT_MIRROR, help="base URL of the releases/ directory boxes read")
    ap.add_argument("--releases", type=Path, default=ROOT / "releases", help="canonical wizard-os releases/ directory")
    ap.add_argument("--json", action="store_true", help="print one JSON object")
    a = ap.parse_args(argv)
    try:
        rep = check(a.releases, a.mirror)
    except FetchError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, indent=2))
    else:
        for ch in CHANNELS:
            print(f"{ch}: wizard-os {rep['canonical'][ch]}, mirror {rep['mirror_pointers'][ch]}")
        for line in rep["info"]:
            print(f"INFO {line}")
        for p in rep["problems"]:
            print(f"DRIFT {p}")
        print("OK: boxes on both channels see what wizard-os names" if rep["ok"]
              else f"{len(rep['problems'])} problem(s)")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
