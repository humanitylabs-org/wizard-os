#!/usr/bin/env python3
"""Read-only input to the existing Sunday Hermes stability assessment. Never promotes or posts.

Run from a current wizard-os checkout: python3 tools/hermes_candidate_report.py [--json]
Requires authenticated gh for public GitHub reads. Registry reads are anonymous and digest-verified.
This is evidence for the assessor, not an automatic substitute for reading upstream issues or the soak diary.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request

from check_release import dockerhub_image_revision

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "NousResearch/hermes-agent"
FINAL = re.compile(r"v\d+\.\d+\.\d+\Z")
RISK = re.compile(r"session|state\.db|sqlite|database|compact|compress|gateway|history", re.I)


def gh(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True, timeout=90))


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def choose(releases, now):
    final = sorted((r for r in releases if not r.get("draft") and not r.get("prerelease")
                    and FINAL.fullmatch(r["tag_name"]) and r.get("published_at")),
                   key=lambda r: utc(r["published_at"]), reverse=True)
    eligible = [r for r in final if now - utc(r["published_at"]) >= timedelta(days=7)]
    return (eligible[0] if eligible else None), [r["tag_name"] for r in final if r not in eligible]


def image(tag):
    token = json.load(urllib.request.urlopen(
        "https://auth.docker.io/token?service=registry.docker.io&scope=repository:nousresearch/hermes-agent:pull",
        timeout=20))["token"]
    req = urllib.request.Request(f"https://registry-1.docker.io/v2/nousresearch/hermes-agent/manifests/{tag}",
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        digest = "sha256:" + hashlib.sha256(response.read()).hexdigest()
    revision, error = dockerhub_image_revision(digest)
    return {"ref": f"docker.io/nousresearch/hermes-agent:{tag}", "digest": digest,
            "commit": revision, "provenance_error": error or None}


def issues(tag):
    # Include v-prefixed and unprefixed version references. Return actual risk matches, not a total claiming
    # all relevant bugs are known. A version-scoped search cannot establish absence of unversioned reports.
    query = f'repo:{UPSTREAM} is:issue is:open "{tag.lstrip("v")}" in:title,body'
    rows, page = [], 1
    while True:
        result = gh("search/issues?" + urllib.parse.urlencode({"q": query, "per_page": 100, "page": page}))
        if result.get("incomplete_results"):
            raise RuntimeError("GitHub issue search is incomplete")
        rows.extend(result["items"])
        if len(rows) >= result["total_count"]:
            if len({r["number"] for r in rows}) != result["total_count"]:
                raise RuntimeError("GitHub issue search changed during pagination; rerun assessment")
            break
        if not result["items"] or page >= 10:
            raise RuntimeError("GitHub issue search was truncated")
        page += 1
    dedup = {r["number"]: r for r in rows}
    return [{"number": r["number"], "title": r["title"], "url": r["html_url"]}
            for r in dedup.values() if RISK.search(r["title"] + "\n" + (r.get("body") or ""))]


def gates(candidate, img, record, risk):
    blocked = []
    if img.get("error"):
        blocked.append("final container image unverified: " + img["error"])
    elif not img.get("commit"):
        blocked.append("image/tag source identity unproven: " + str(img.get("provenance_error")))
    elif img["commit"] != candidate["commit"]:
        blocked.append(f"image/tag source mismatch: {img['commit']} != {candidate['commit']}")
    if not record:
        blocked.append("no fresh Thales acceptance record for this tag")
    else:
        blocked.append("assessor must verify that the record passed and covers this exact image digest and commit")
    if risk:
        blocked.append(f"{len(risk)} open version-mentioned risk-search hit(s) need adjudication; these are not confirmed regressions")
    blocked += ["unversioned upstream issue/fix-churn review not yet signed off",
                "two-to-three-day Archimedes soak not yet signed off (no install authorized)",
                "James has not approved promotion"]
    return blocked


def report(snapshot, now):
    pin = json.loads(snapshot.read_text())["hermes"]
    out = {"decision": "HOLD", "checked_at": now.isoformat(), "snapshot": snapshot.name, "pin": pin,
           "candidate": None, "blocked": [], "approval": None}
    try:
        # One page is deliberately enough for recency, but never silently call an empty list complete.
        releases = gh(f"repos/{UPSTREAM}/releases?per_page=100")
        candidate, young = choose(releases, now)
        out["too_young"] = young
        if not candidate:
            out["blocked"] = ["no final release with seven full days of public soak in the latest 100 releases"]
            return out
        tag = candidate["tag_name"]
        sha = gh(f"repos/{UPSTREAM}/commits/{tag}")["sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise RuntimeError("GitHub returned no full source commit")
        out["candidate"] = {"tag": tag, "commit": sha, "published_at": candidate["published_at"],
                            "url": candidate["html_url"]}
        try:
            img = image(tag)
        except Exception as e:
            img = {"error": str(e)[:200]}
        out["image"] = img
        record = ROOT / "docs" / "acceptance" / f"hermes-{tag}.md"
        out["test_record"] = str(record.relative_to(ROOT)) if record.is_file() else None
        risk = issues(tag)
        out["open_risk_reports"] = risk
        out["blocked"] = gates(out["candidate"], img, out["test_record"], risk)
    except Exception as e:
        out["blocked"].append("assessment incomplete: " + str(e)[:300])
    # Intentionally no UPDATE or promotion write: this helper cannot know the installed box's soak or James's yes.
    return out


def markdown(out):
    candidate = out.get("candidate")
    text = ["HOLD", "", f"Wizard snapshot {out['snapshot']}: {out['pin']['tag']} at {out['pin']['commit']}."]
    text.append("Candidate: " + (f"[{candidate['tag']}]({candidate['url']}) at `{candidate['commit']}`; seven-day public soak met."
                                if candidate else "none verified."))
    if out.get("image"):
        text.append("Image: " + json.dumps(out["image"], sort_keys=True))
    text += ["", "Blocked by:", *("- " + b for b in out["blocked"])]
    risk_rows = out.get("open_risk_reports", [])
    priority = re.compile(r"lost|loss|sqlite|database|compact|compress|resume|rollback|history", re.I)
    shown = sorted(risk_rows, key=lambda r: (not bool(priority.search(r["title"])), r["number"]))[:5]
    for risk in shown:
        text.append(f"- Upstream #{risk['number']}: [{risk['title']}]({risk['url']})")
    if len(shown) < len(risk_rows):
        text.append(f"Showing {len(shown)} of {len(risk_rows)} risk-search hits; --json retains the complete list.")
    if out.get("too_young"):
        text.append("Too young: " + ", ".join(out["too_young"]) + ".")
    text.append("No promotion or live update performed; no approval requested while these gates are open.")
    return "\n".join(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args()
    snapshot = ns.snapshot or ROOT / "releases" / ((ROOT / "releases" / "stable").read_text().strip() + ".json")
    out = report(snapshot, datetime.now(timezone.utc))
    print(json.dumps(out, indent=2) if ns.json else markdown(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
