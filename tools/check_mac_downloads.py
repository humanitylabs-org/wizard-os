#!/usr/bin/env python3
"""Check what a Mac user actually gets from the public downloads (goal wizard-os #415).

    python3 tools/check_mac_downloads.py            # read-only probe of https://downloads.aiwizards.com
    python3 tools/check_mac_downloads.py --json     # same, as one JSON object
    python3 tools/check_mac_downloads.py --base URL # another mirror with the same layout

It answers one question a self-installer depends on: does the download page, the in-app update feed and the
first-install Wizard OS feed agree, and does every file they name answer? The layout is try-wizard
`next/mac/DOWNLOADS.md`: `mac/appcast.xml` (Sparkle feed), `index.html` (landing page with the DMG links),
`os/latest.json` (Wizard OS image in parts).

Problems it reports:
- the update feed and the download page offer different builds (a new install and an updated install end up
  on different apps; try-wizard #73 saw feed 308 while the page offered 309);
- a feed archive or the newest DMG does not answer 200, or its size differs from what the feed says;
- `os/latest.json` parts do not add up to its `bytes`, or its first part does not answer.

It only reads (GET for the three small index files, HEAD for the big ones). It never signs, uploads or changes
anything, and nothing runs it automatically. Exit 0 = consistent, 1 = problems found (each printed),
2 = a feed could not be fetched or parsed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_BASE = "https://downloads.aiwizards.com"
SPARKLE = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"
# DMG links on the landing page: .../mac/<build>/Wizard-<version>.dmg
DMG = re.compile(r'href="(?P<url>[^"]*/mac/(?P<build>\d+)/Wizard-(?P<version>[0-9][0-9A-Za-z.+-]*)\.dmg)"')
TIMEOUT = 30


class FetchError(Exception):
    pass


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "wizard-os-check-mac-downloads"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        raise FetchError(f"{url}: {e}") from e


def http_head(url: str) -> tuple[int, int | None]:
    """(status, content-length or None). Network errors come back as status 0."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "wizard-os-check-mac-downloads"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            n = r.headers.get("Content-Length")
            return r.status, int(n) if n and n.isdigit() else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, OSError):
        return 0, None


def parse_appcast(text: str) -> list[dict]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise FetchError(f"appcast.xml is not XML: {e}") from e
    items = []
    for item in root.iter("item"):
        build = (item.findtext(f"{SPARKLE}version") or "").strip()
        enc = item.find("enclosure")
        length = enc.get("length") if enc is not None else None
        items.append({
            "build": int(build) if build.isdigit() else None,
            "version": (item.findtext(f"{SPARKLE}shortVersionString") or "").strip(),
            "url": enc.get("url") if enc is not None else None,
            "length": int(length) if length and length.isdigit() else None,
        })
    return items


def parse_page(text: str, base: str) -> list[dict]:
    seen, out = set(), []
    for m in DMG.finditer(text):
        url = urllib.parse.urljoin(base + "/", m["url"])
        if url not in seen:
            seen.add(url)
            out.append({"build": int(m["build"]), "version": m["version"], "url": url})
    return out


def check(base: str = DEFAULT_BASE, get=http_get, head=http_head) -> dict:
    """Return {"feed", "page", "os", "problems"}; raise FetchError when an index file is unreadable."""
    base = base.rstrip("/")
    problems: list[str] = []

    feed = parse_appcast(get(f"{base}/mac/appcast.xml"))
    if not feed:
        problems.append("mac/appcast.xml lists no update")
    for it in feed:
        if it["build"] is None or not it["url"]:
            problems.append(f"feed item {it['version'] or '?'} has no numeric build or no archive URL")
            continue
        status, size = head(it["url"])
        if status != 200:
            problems.append(f"feed archive for build {it['build']} answers {status}: {it['url']}")
        elif it["length"] is not None and size is not None and size != it["length"]:
            problems.append(f"feed archive for build {it['build']} is {size} bytes, feed says {it['length']}")

    page = parse_page(get(f"{base}/index.html"), base)
    if not page:
        problems.append("index.html links no Mac DMG")
    else:
        newest = max(page, key=lambda d: d["build"])
        status, _ = head(newest["url"])
        if status != 200:
            problems.append(f"newest DMG on the download page answers {status}: {newest['url']}")

    feed_builds = [it["build"] for it in feed if it["build"] is not None]
    if feed_builds and page:
        fb, pb = max(feed_builds), max(d["build"] for d in page)
        fv = next(it["version"] for it in feed if it["build"] == fb)
        pv = next(d["version"] for d in page if d["build"] == pb)
        if pb > fb:
            problems.append(f"update feed lags the download page: new installs get {pv} (build {pb}), "
                            f"installed apps are offered only {fv} (build {fb})")
        elif fb > pb:
            problems.append(f"download page lags the update feed: new installs get {pv} (build {pb}), "
                            f"the feed already offers {fv} (build {fb})")

    os_feed = json.loads(get(f"{base}/os/latest.json") or "null")
    os_info = {}
    if not isinstance(os_feed, dict) or not isinstance(os_feed.get("parts"), list) or not os_feed["parts"]:
        problems.append("os/latest.json has no parts")
    else:
        parts = os_feed["parts"]
        total = sum(p.get("bytes", 0) for p in parts if isinstance(p, dict))
        os_info = {"version": os_feed.get("version"), "parts": len(parts), "bytes": os_feed.get("bytes")}
        if os_feed.get("bytes") != total:
            problems.append(f"os/latest.json parts add up to {total} bytes, it says {os_feed.get('bytes')}")
        first = parts[0].get("url") if isinstance(parts[0], dict) else None
        if first:
            url = urllib.parse.urljoin(f"{base}/os/latest.json", first)
            status, size = head(url)
            if status != 200:
                problems.append(f"first Wizard OS part answers {status}: {url}")
            elif size is not None and parts[0].get("bytes") not in (None, size):
                problems.append(f"first Wizard OS part is {size} bytes, latest.json says {parts[0]['bytes']}")

    return {"base": base, "feed": feed, "page": page, "os": os_info, "problems": problems}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("--base", default=DEFAULT_BASE, help="downloads root (default: %(default)s)")
    ap.add_argument("--json", action="store_true", help="print one JSON object")
    args = ap.parse_args(argv)
    try:
        result = check(args.base)
    except (FetchError, ValueError) as e:
        print(f"cannot read the downloads: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for it in result["feed"]:
            print(f"update feed : {it['version']} (build {it['build']})  {it['url']}")
        for d in result["page"]:
            print(f"download DMG: {d['version']} (build {d['build']})  {d['url']}")
        if result["os"]:
            o = result["os"]
            print(f"Wizard OS   : {o['version']} in {o['parts']} parts, {o['bytes']} bytes")
        for p in result["problems"]:
            print(f"PROBLEM: {p}")
        print("OK: download page, update feed and Wizard OS feed agree" if not result["problems"]
              else f"{len(result['problems'])} problem(s)")
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
