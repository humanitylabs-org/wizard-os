#!/usr/bin/env python3
"""Which `integration/*` and `live*` side branches are still on origin, and is each one decided (wizard-os #491).

    python3 tools/side_branches.py                 # this checkout, ledger docs/SIDE_BRANCHES.md
    python3 tools/side_branches.py --repo ../wizard-os --json

Live == main: nothing should run from a side branch. Every leftover `integration/*`, `live/*` or `live-*`
branch needs a recorded decision in the ledger (docs/SIDE_BRANCHES.md): land it by PR, abandon it with
a person's sign-off, or keep it with a stated reason. This tool compares the branches on origin with that
ledger and prints, one line each:

    branch   last commit date, commits not on main (patch-id compare, `git cherry`), files changed since
             the merge base (approx. "not landed"), and the ledger decision
    problem  a side branch on origin with no ledger row (a new one, or one nobody recorded), a row still
             `undecided`, an `abandon` row whose branch is still on origin (a person may delete it now),
             or a row whose branch is gone from origin but not marked `deleted`

It reads the local remote-tracking refs, so run `git fetch --prune origin` first. It only reads: it never
deletes, pushes or edits a branch, and nothing runs it automatically, so it changes no behaviour (no switch).
`owner-snapshot/*` and every other prefix are out of scope and never listed.
Exit 0 = every side branch is decided and nothing is left to do, 1 = at least one problem (each printed),
2 = not a git checkout with `origin/main`, or the ledger is missing or unreadable.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SIDE = re.compile(r"^(integration/.+|live/.+|live-.+|live)$")
DECISIONS = ("undecided", "land", "abandon", "keep", "deleted")
ROW = re.compile(r"^\|\s*`(?P<branch>[^`]+)`\s*\|\s*(?P<decision>[^|]*?)\s*\|(?P<rest>.*)\|\s*$")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def side_branches(repo: Path, base: str = "origin/main") -> list[dict]:
    """Every origin side branch with its last date, unique commits and changed files."""
    refs = git(repo, "for-each-ref", "--format=%(refname:strip=3)\t%(committerdate:short)", "refs/remotes/origin/")
    out = []
    for line in refs.splitlines():
        name, _, date = line.partition("\t")
        if not SIDE.match(name):
            continue
        ref = f"origin/{name}"
        unique = sum(1 for c in git(repo, "cherry", base, ref).splitlines() if c.startswith("+"))
        merge_base = git(repo, "merge-base", base, ref).strip()
        files = [f for f in git(repo, "diff", "--name-only", merge_base, ref).splitlines() if f]
        out.append({"branch": name, "last": date, "unique_commits": unique, "files": len(files)})
    return sorted(out, key=lambda b: b["branch"])


def read_ledger(path: Path) -> dict[str, dict]:
    """Rows `| `branch` | decision | note |` from the ledger table. Unknown decision words raise ValueError."""
    rows: dict[str, dict] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = ROW.match(line.strip())
        if not m:
            continue
        w = re.match(r"\W*([A-Za-z]+)", m["decision"])
        word = w[1].lower() if w else ""
        if word not in DECISIONS:
            raise ValueError(f"{path.name}:{n}: decision must start with one of {', '.join(DECISIONS)}: {m['decision']!r}")
        rows[m["branch"]] = {"decision": word, "text": m["decision"], "note": m["rest"].strip(" |")}
    return rows


def problems(branches: list[dict], ledger: dict[str, dict]) -> list[str]:
    found = []
    on_origin = {b["branch"] for b in branches}
    for b in branches:
        row = ledger.get(b["branch"])
        if row is None:
            found.append(f"{b['branch']}: on origin but not in the ledger (no new side branches; record a decision)")
        elif row["decision"] == "undecided":
            found.append(f"{b['branch']}: undecided ({b['unique_commits']} commits not on main)")
        elif row["decision"] == "abandon":
            found.append(f"{b['branch']}: abandoned with sign-off, still on origin (a person may delete it)")
        elif row["decision"] == "deleted":
            found.append(f"{b['branch']}: marked deleted but still on origin")
    for name, row in sorted(ledger.items()):
        if name not in on_origin and row["decision"] != "deleted":
            found.append(f"{name}: gone from origin; mark its row `deleted`")
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--repo", default=".", help="wizard-os checkout (default: .)")
    ap.add_argument("--ledger", default=None, help="ledger file (default: <repo>/docs/SIDE_BRANCHES.md)")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    ledger_path = Path(args.ledger) if args.ledger else repo / "docs" / "SIDE_BRANCHES.md"
    try:
        git(repo, "rev-parse", "--verify", "--quiet", args.base)
        branches = side_branches(repo, args.base)
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        print(f"not a git checkout with {args.base}: {repo}", file=sys.stderr)
        return 2
    try:
        ledger = read_ledger(ledger_path)
    except (OSError, ValueError) as err:
        print(f"ledger unreadable: {err}", file=sys.stderr)
        return 2
    found = problems(branches, ledger)
    if args.json:
        for b in branches:
            b["decision"] = ledger.get(b["branch"], {}).get("decision", "missing")
        print(json.dumps({"branches": branches, "problems": found}, indent=2))
    else:
        for b in branches:
            d = ledger.get(b["branch"], {}).get("decision", "missing")
            print(f"branch   {b['branch']}  last {b['last']}  {b['unique_commits']} commits not on main  "
                  f"{b['files']} files  decision: {d}")
        for p in found:
            print(f"problem  {p}")
        print(f"{len(branches)} side branches on origin, {len(found)} problems")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
