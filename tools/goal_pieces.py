#!/usr/bin/env python3
"""Where each piece of a goal stands (goal wizard-os #419, and any goal with a Pieces list).

    python3 tools/goal_pieces.py 419                  # goal humanitylabs-org/wizard-os#419
    python3 tools/goal_pieces.py 419 --json           # same, as one JSON object
    python3 tools/goal_pieces.py 418 --repo wizard-os

Since the 7 Nov 2026 reorganization, a goal's small pieces live on the goal as a checklist:

    - [ ] humanitylabs-org/wizard-ux#166 — Tell the owner why a reply failed

This tool reads that checklist and, for each piece, the linked issue and the pull requests that mention it.
It prints one line per piece with a plain status:

    done        the issue is closed
    merged      the issue is open but a PR that mentions it is merged (someone should check it and close it)
    in review   an open PR mentions it
    no PR yet   nothing is moving on it

It also flags checklist drift: a ticked box whose issue is still open, or an unticked box whose issue is
closed. That is the cue to update the goal by hand; the tool never edits it.

It only reads, through `gh api` (so private repos work with the caller's own login). It never writes,
comments, ticks boxes or changes settings, and nothing runs it automatically. Exit 0 = read fine and no
drift, 1 = some checkbox disagrees with its issue (each printed), 2 = GitHub could not be read or the goal
has no Pieces list.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

ORG = "humanitylabs-org"
REPO = "wizard-os"
# "- [ ] owner/repo#123 — title" (also "*" bullets, "[x]" ticks and a plain hyphen or colon before the title).
PIECE = re.compile(
    r"^\s*[-*]\s+\[(?P<tick>[ xX])\]\s+(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)\s*(?:[—–:-]\s*)?(?P<title>.*)$"
)


class FetchError(Exception):
    pass


def gh_api(path: str):
    """GET one GitHub API path (all pages) with the caller's gh login; parsed JSON."""
    p = subprocess.run(["gh", "api", "--paginate", "--slurp", path], capture_output=True, text=True)
    if p.returncode != 0:
        raise FetchError(f"{path}: {(p.stderr or p.stdout).strip()}")
    pages = json.loads(p.stdout)
    # --slurp wraps every page in a list; a single object comes back as [obj].
    if len(pages) == 1 and isinstance(pages[0], dict):
        return pages[0]
    return [item for page in pages for item in (page if isinstance(page, list) else [page])]


def parse_pieces(body: "str | None") -> list[dict]:
    """The checklist lines that link an issue: [{"repo", "number", "ticked", "title"}], in order, no repeats."""
    out, seen = [], set()
    for line in (body or "").splitlines():
        m = PIECE.match(line)
        if not m:
            continue
        key = (m.group("repo").lower(), int(m.group("num")))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "repo": m.group("repo"),
            "number": int(m.group("num")),
            "ticked": m.group("tick").lower() == "x",
            "title": m.group("title").strip(),
        })
    return out


def linked_prs(timeline: list) -> list[dict]:
    """PRs that cross-reference the issue: [{"repo", "number", "state": open|merged|closed, "title"}]."""
    prs, seen = [], set()
    for ev in timeline or []:
        if ev.get("event") != "cross-referenced":
            continue
        src = (ev.get("source") or {}).get("issue") or {}
        pr = src.get("pull_request")
        if not pr:
            continue
        repo = (src.get("repository") or {}).get("full_name", "")
        key = (repo, src.get("number"))
        if key in seen:
            continue
        seen.add(key)
        state = "merged" if pr.get("merged_at") else ("open" if src.get("state") == "open" else "closed")
        prs.append({"repo": repo, "number": src.get("number"), "state": state, "title": src.get("title", "")})
    return prs


def status(issue_state: str, prs: list[dict]) -> str:
    if issue_state == "closed":
        return "done"
    states = {p["state"] for p in prs}
    if "merged" in states:
        return "merged"
    if "open" in states:
        return "in review"
    return "no PR yet"


def check_piece(piece: dict, get=None) -> dict:
    get = get or gh_api
    path = f"repos/{piece['repo']}/issues/{piece['number']}"
    issue = get(path)
    prs = linked_prs(get(f"{path}/timeline?per_page=100"))
    state = issue.get("state", "open")
    out = dict(piece)
    out.update({
        "title": issue.get("title") or piece["title"],
        "issue_state": state,
        "status": status(state, prs),
        "prs": prs,
        "drift": None,
    })
    if piece["ticked"] and state != "closed":
        out["drift"] = "ticked on the goal but the issue is still open"
    elif not piece["ticked"] and state == "closed":
        out["drift"] = "issue is closed but its box on the goal is not ticked"
    return out


def check_goal(number: int, repo: str = f"{ORG}/{REPO}", get=None) -> dict:
    get = get or gh_api
    goal = get(f"repos/{repo}/issues/{number}")
    pieces = parse_pieces(goal.get("body", ""))
    return {
        "goal": f"{repo}#{number}",
        "title": goal.get("title", ""),
        "pieces": [check_piece(p, get) for p in pieces],
    }


def _pr_ref(goal_repo: str, pr: dict) -> str:
    return f"#{pr['number']}" if pr["repo"] == goal_repo else f"{pr['repo']}#{pr['number']}"


def main(argv=None, get=None) -> int:
    ap = argparse.ArgumentParser(description="Where each piece of a goal stands (read-only).")
    ap.add_argument("number", type=int, help="goal issue number")
    ap.add_argument("--org", default=ORG)
    ap.add_argument("--repo", default=REPO, help="repo the goal lives in (default wizard-os)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    get = get or gh_api  # looked up at call time so tests can patch the module's gh_api
    goal_repo = f"{a.org}/{a.repo}"
    try:
        result = check_goal(a.number, goal_repo, get)
    except FetchError as e:
        print(f"could not read GitHub: {e}", file=sys.stderr)
        return 2
    if not result["pieces"]:
        print(f"{result['goal']} has no Pieces checklist (lines like '- [ ] owner/repo#N — title')", file=sys.stderr)
        return 2
    drift = [p for p in result["pieces"] if p["drift"]]
    if a.json:
        result["drift"] = len(drift)
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['goal']} {result['title']}")
        for p in result["pieces"]:
            prs = ", ".join(f"{_pr_ref(p['repo'], pr)} {pr['state']}" for pr in p["prs"]) or "-"
            print(f"  {p['status']:<10} {p['repo']}#{p['number']} {p['title']}  [PRs: {prs}]")
            if p["drift"]:
                print(f"  {'DRIFT':<10} {p['repo']}#{p['number']}: {p['drift']}")
        counts = {}
        for p in result["pieces"]:
            counts[p["status"]] = counts.get(p["status"], 0) + 1
        summary = ", ".join(f"{counts[s]} {s}" for s in ("done", "merged", "in review", "no PR yet") if s in counts)
        print(f"{len(result['pieces'])} pieces: {summary}; {len(drift)} checkbox drift")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
