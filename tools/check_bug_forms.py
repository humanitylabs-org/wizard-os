#!/usr/bin/env python3
"""Check that every humanitylabs-org repo has the bug form (goal wizard-os #418, item 5).

    python3 tools/check_bug_forms.py                  # every non-archived repo in the org
    python3 tools/check_bug_forms.py --repo wizard-ux --repo wizard-os
    python3 tools/check_bug_forms.py --json           # same, as one JSON object

Goal #418 asks for a bug form in every repo with these fields: what happens, what should happen, how to see
it, a screenshot, and the version and device. This tool answers "which repos still lack it?" so the forms can
be added repo by repo and the list ticked off with evidence.

A repo passes when one file in `.github/ISSUE_TEMPLATE/` is an issue form (`.yml`/`.yaml` with a `body:`)
that is the bug form (its `name:` is "Bug" or its `labels:` include `bug`) and that has a field for each of the
five required labels below. Labels match case-insensitively and ignore punctuation, so "What happens?" counts.
Extra fields (for example "Done when") are fine.

It only reads, through `gh api` (so private repos work with the caller's own login). It never writes, opens
PRs or changes settings, and nothing runs it automatically. Exit 0 = every repo has the form, 1 = some repos
lack it or miss fields (each printed), 2 = GitHub could not be read.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys

ORG = "humanitylabs-org"
FORM_DIR = ".github/ISSUE_TEMPLATE"
# The five fields goal #418 names, in form order.
REQUIRED = ("What happens", "What should happen", "How to see it", "Screenshot", "Version and device")


class FetchError(Exception):
    pass


class NotFound(FetchError):
    pass


def gh_api(path: str):
    """GET one GitHub API path with the caller's gh login; parsed JSON. 404 raises NotFound."""
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if p.returncode != 0:
        msg = (p.stderr or p.stdout).strip()
        if "404" in msg or "Not Found" in msg:
            raise NotFound(path)
        raise FetchError(f"{path}: {msg}")
    return json.loads(p.stdout)


def norm(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def _scalar(v: str) -> str:
    v = v.split(" #", 1)[0].strip()
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"" else v


def parse_form(text: str) -> dict:
    """The few things we need from an issue form, without PyYAML: name, top-level labels, field labels.

    Field labels are the `label:` keys nested under `attributes:` (markdown blocks have none)."""
    name, labels, fields = "", [], []
    in_labels = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = not raw[0].isspace()
        if top:
            in_labels = False
            m = re.match(r"name:\s*(.*)$", line)
            if m:
                name = _scalar(m.group(1))
            m = re.match(r"labels:\s*(.*)$", line)
            if m:
                rest = m.group(1).strip()
                if rest.startswith("["):
                    labels = [_scalar(x) for x in rest.strip("[]").split(",") if x.strip()]
                elif rest:
                    labels = [_scalar(rest)]
                else:
                    in_labels = True
            continue
        if in_labels and re.match(r"\s*-\s+", line):
            labels.append(_scalar(re.sub(r"^\s*-\s+", "", line)))
            continue
        m = re.match(r"\s+label:\s*(.+)$", line)
        if m:
            fields.append(_scalar(m.group(1)))
    return {"name": name, "labels": labels, "fields": fields, "is_form": bool(re.search(r"(?m)^body:", text))}


def is_bug_form(form: dict) -> bool:
    return form["is_form"] and (norm(form["name"]) == "bug" or "bug" in [norm(x) for x in form["labels"]])


def missing_fields(form: dict) -> list[str]:
    have = {norm(f) for f in form["fields"]}
    return [r for r in REQUIRED if norm(r) not in have]


def check_repo(repo: str, get=None, org: str = ORG) -> dict:
    """{"repo", "ok", "form" (path or None), "missing" (field labels), "problem" (plain words or None)}."""
    get = get or gh_api
    out = {"repo": repo, "ok": False, "form": None, "missing": list(REQUIRED), "problem": None}
    try:
        entries = get(f"repos/{org}/{repo}/contents/{FORM_DIR}")
    except NotFound:
        out["problem"] = f"no {FORM_DIR}/ folder"
        return out
    best = None
    for e in entries if isinstance(entries, list) else []:
        path = e.get("path", "")
        if e.get("type") != "file" or not path.endswith((".yml", ".yaml")) or path.endswith("/config.yml"):
            continue
        blob = get(f"repos/{org}/{repo}/contents/{path}")
        text = base64.b64decode(blob.get("content", "")).decode("utf-8", "replace")
        form = parse_form(text)
        if not is_bug_form(form):
            continue
        miss = missing_fields(form)
        if best is None or len(miss) < len(best[1]):
            best = (path, miss)
    if best is None:
        out["problem"] = "no bug issue form (a .yml form named Bug or labelled bug)"
        return out
    out["form"], out["missing"] = best
    out["ok"] = not best[1]
    if best[1]:
        out["problem"] = "bug form lacks: " + ", ".join(best[1])
    return out


def org_repos(get=None, org: str = ORG) -> list[str]:
    get = get or gh_api
    names, page = [], 1
    while True:
        batch = get(f"orgs/{org}/repos?per_page=100&type=all&page={page}")
        names += [r["name"] for r in batch if not r.get("archived")]
        if len(batch) < 100:
            return sorted(names)
        page += 1


def main(argv=None, get=None) -> int:
    ap = argparse.ArgumentParser(description="Which repos lack the #418 bug form (read-only).")
    ap.add_argument("--org", default=ORG)
    ap.add_argument("--repo", action="append", help="check only this repo (repeatable)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    get = get or gh_api  # looked up at call time so tests can patch the module's gh_api
    try:
        repos = a.repo or org_repos(get, a.org)
        results = [check_repo(r, get, a.org) for r in repos]
    except FetchError as e:
        print(f"could not read GitHub: {e}", file=sys.stderr)
        return 2
    bad = [r for r in results if not r["ok"]]
    if a.json:
        print(json.dumps({"org": a.org, "checked": len(results), "missing": len(bad), "repos": results}, indent=2))
    else:
        for r in results:
            print(f"{'ok  ' if r['ok'] else 'MISS'} {r['repo']}: {r['form'] if r['ok'] else r['problem']}")
        print(f"{len(results) - len(bad)}/{len(results)} repos have the bug form")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
