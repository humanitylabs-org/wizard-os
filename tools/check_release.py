#!/usr/bin/env python3
"""Check a Wizard OS release file: every pinned commit exists in its repo, every image digest resolves.

    python3 tools/check_release.py releases/0.2.0.json          # commits (gh api) + image digests (registry)
    python3 tools/check_release.py releases/0.2.0.json --offline # shape only (CI without network)

A release file names exactly what one Wizard OS version is: the commit of each component repo, the image digests
those commits produced, and the default app in every parking spot (with the index version it resolves to).
Exit 0 = everything checked out; 1 = something is missing (each problem printed); 2 = usage / unreadable file.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def shape(rel: dict) -> list[str]:
    errs: list[str] = []
    if not VERSION.match(str(rel.get("version", ""))):
        errs.append(f"version {rel.get('version')!r} is not semver")
    comps = rel.get("components")
    if not isinstance(comps, dict) or not comps:
        return errs + ["components: missing"]
    for name, c in comps.items():
        if not REPO.match(str(c.get("repo", ""))):
            errs.append(f"{name}: repo {c.get('repo')!r} is not owner/name")
        if not SHA.match(str(c.get("commit", ""))):
            errs.append(f"{name}: commit {c.get('commit')!r} is not a 40-char sha")
    for name, im in (rel.get("images") or {}).items():
        if not DIGEST.match(str(im.get("digest", ""))):
            errs.append(f"image {name}: digest {im.get('digest')!r} is not sha256:<64 hex>")
        if im.get("built_from") and im["built_from"] not in comps:
            errs.append(f"image {name}: built_from {im['built_from']!r} is not a component")
    for slot, d in (rel.get("default_apps") or {}).items():
        if d is not None and not d.get("app"):
            errs.append(f"default_apps.{slot}: needs app (or null)")
    return errs


def commit_exists(repo: str, sha: str) -> tuple[bool, str]:
    r = subprocess.run(["gh", "api", f"repos/{repo}/commits/{sha}", "-q", ".sha"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip() == sha:
        return True, ""
    return False, ((r.stderr or "").strip().splitlines() or ["not found"])[-1][:160]


def digest_exists(ref: str, digest: str) -> tuple[bool, str]:
    """ghcr.io/<owner>/<name>: anonymous pull token, then HEAD the manifest by digest."""
    m = re.match(r"^ghcr\.io/([^:@]+)", ref)
    if not m:
        return False, f"{ref}: only ghcr.io is checked"
    name = m.group(1)
    try:
        tok = json.load(urllib.request.urlopen(f"https://ghcr.io/token?scope=repository:{name}:pull", timeout=20))["token"]
        req = urllib.request.Request(f"https://ghcr.io/v2/{name}/manifests/{digest}", method="HEAD", headers={
            "Authorization": f"Bearer {tok}",
            "Accept": ", ".join(["application/vnd.oci.image.index.v1+json", "application/vnd.oci.image.manifest.v1+json",
                                 "application/vnd.docker.distribution.manifest.list.v2+json",
                                 "application/vnd.docker.distribution.manifest.v2+json"])})
        urllib.request.urlopen(req, timeout=20)
        return True, ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except (OSError, ValueError, KeyError) as e:
        return False, str(e)[:160]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file")
    ap.add_argument("--offline", action="store_true", help="check the shape only")
    a = ap.parse_args(argv)
    try:
        rel = json.loads(Path(a.file).read_text())
    except (OSError, ValueError) as e:
        print(f"can't read {a.file}: {e}", file=sys.stderr)
        return 2
    errs = shape(rel)
    ok_lines: list[str] = []
    if not errs and not a.offline:
        for name, c in rel["components"].items():
            ok, why = commit_exists(c["repo"], c["commit"])
            (ok_lines if ok else errs).append(f"{name}: {c['repo']}@{c['commit'][:12]}" + ("" if ok else f" missing ({why})"))
        for name, im in (rel.get("images") or {}).items():
            ok, why = digest_exists(im["ref"], im["digest"])
            (ok_lines if ok else errs).append(f"image {name}: {im['digest'][:19]}" + ("" if ok else f" missing ({why})"))
    for line in ok_lines:
        print(f"PASS  {line}")
    for e in errs:
        print(f"FAIL  {e}")
    print(f"release {rel.get('version')}: {'ok' if not errs else f'{len(errs)} problem(s)'}")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
