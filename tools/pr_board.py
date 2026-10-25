#!/usr/bin/env python3
"""Sync the Wizard OS PR pipeline board (a GitHub Project in humanitylabs-org).

One card per pull request across the repos Wizard OS releases are built from.
The Status column says where the change is:

  Draft      -> draft PR
  In review  -> open PR, waiting for review or checks
  Merged     -> on main, not yet in a cut release (or final, for repos with no release)
  On Latest  -> inside the commit that releases/latest pins for that repo
  On Stable  -> inside the commit that releases/stable pins for that repo
  Dropped    -> closed without merging

Release membership comes from the release JSONs in this repo (components.*.repo/commit
and default_apps.*.repo/commit), so the board moves when tools/promote_stable.py moves
the pointers. Cards leave the board (archived, not deleted) two days after they reach
their last stage.

Usage:  python3 tools/pr_board.py [--dry-run]
Needs:  gh CLI logged in with the `project` scope (gh auth refresh -s project).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time

ORG = "humanitylabs-org"
TITLE = "Wizard OS · PR pipeline"
DESCRIPTION = ("Every Wizard OS pull request and where it is: Draft, In review, Merged, "
               "On Latest, On Stable, Dropped. Synced by wizard-os tools/pr_board.py.")
STAGES = [  # (name, colour, description)
    ("Draft", "GRAY", "Draft PR, still being worked on"),
    ("In review", "YELLOW", "Open PR waiting for review or checks"),
    ("Merged", "BLUE", "On main, not in a cut release yet"),
    ("On Latest", "PURPLE", "In the release on the latest channel"),
    ("On Stable", "GREEN", "In the release every install gets"),
    ("Dropped", "RED", "Closed without merging"),
]
TIERS = [  # (label, option name, colour)
    ("tier: recommended fix", "Bug fix", "RED"),
    ("tier: strong suggestion", "Improvement", "BLUE"),
    ("tier: opinionated", "Personal preference", "PINK"),
    ("tier: maintenance", "Maintenance", "GRAY"),
]
NO_TIER = ("No tier", "YELLOW")
# Repos without release pins still get cards; their last stage is Merged.
EXTRA_REPOS = [f"{ORG}/wizard-os", f"{ORG}/try-wizard"]
WINDOW_DAYS = 10       # closed PRs older than this are not added
ARCHIVE_AFTER_DAYS = 2  # cards in a final stage leave the board this many days after merge/close
HISTORY_DAYS = 45      # how far back to walk a pinned commit's history


def gql(query: str, **variables):
    body = json.dumps({"query": query, "variables": variables})
    err = ""
    for attempt in range(5):
        p = subprocess.run(["gh", "api", "graphql", "--input", "-"], input=body,
                           capture_output=True, text=True)
        if p.returncode == 0:
            out = json.loads(p.stdout)
            if not out.get("errors"):
                return out["data"]
            err = json.dumps(out["errors"])
        else:
            err = p.stderr or p.stdout
        low = err.lower()
        if any(k in low for k in ("rate limit", "502", "timeout", "try again", "temporary conflict")):
            time.sleep(10 * (attempt + 1))
            continue
        raise RuntimeError(err[:800])
    raise RuntimeError("GitHub GraphQL kept failing: " + err[:400])


def rest(path: str):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def release_pins() -> dict[str, dict[str, str]]:
    """{'latest': {repo: commit}, 'stable': {...}} read from wizard-os main."""
    import base64
    pins = {}
    for channel in ("latest", "stable"):
        ver = base64.b64decode(rest(f"repos/{ORG}/wizard-os/contents/releases/{channel}")["content"]).decode().strip()
        rel = json.loads(base64.b64decode(rest(f"repos/{ORG}/wizard-os/contents/releases/{ver}.json")["content"]))
        m = {}
        for section in ("components", "default_apps"):
            for v in (rel.get(section) or {}).values():
                if isinstance(v, dict) and v.get("repo") and v.get("commit"):
                    m[v["repo"]] = v["commit"]
        pins[channel] = {"version": ver, "repos": m}
    return pins


def ancestors(repo: str, sha: str) -> set[str]:
    owner, name = repo.split("/")
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = """query($o:String!,$n:String!,$sha:GitObjectID!,$since:GitTimestamp!,$after:String){
      repository(owner:$o,name:$n){object(oid:$sha){... on Commit{
        history(first:100,since:$since,after:$after){pageInfo{hasNextPage endCursor} nodes{oid}}}}}}"""
    seen, after = set(), None
    while True:
        d = gql(q, o=owner, n=name, sha=sha, since=since, after=after)
        obj = (d["repository"] or {}).get("object")
        if not obj:
            return seen
        h = obj["history"]
        seen.update(n["oid"] for n in h["nodes"])
        if not h["pageInfo"]["hasNextPage"]:
            return seen
        after = h["pageInfo"]["endCursor"]


def pull_requests(repo: str) -> list[dict]:
    since = (dt.date.today() - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    owner, name = repo.split("/")
    # Search is an eventually consistent index: a recently closed PR can disappear
    # from both searches, leaving its existing card stuck in review. Read the
    # repository connection instead, ordered by update time to bound history.
    q = """query($o:String!,$n:String!,$states:[PullRequestState!]!,$after:String){
      repository(owner:$o,name:$n){pullRequests(first:100,states:$states,
        orderBy:{field:UPDATED_AT,direction:DESC},after:$after){
        pageInfo{hasNextPage endCursor}
        nodes{id number title isDraft state updatedAt mergedAt closedAt
          mergeCommit{oid} author{login} labels(first:20){nodes{name}}}}}}"""
    out = {}
    for states in (["OPEN"], ["CLOSED", "MERGED"]):
        after = None
        while True:
            d = gql(q, o=owner, n=name, states=states, after=after)["repository"]["pullRequests"]
            for n in d["nodes"]:
                if states == ["OPEN"] or (n.get("closedAt") or "") >= since:
                    out[n["id"]] = n
            if (not d["pageInfo"]["hasNextPage"] or
                    (states != ["OPEN"] and d["nodes"] and d["nodes"][-1]["updatedAt"] < since)):
                break
            after = d["pageInfo"]["endCursor"]
    return list(out.values())


def stage_of(pr, repo, pins, anc) -> str:
    if pr["state"] == "OPEN":
        return "Draft" if pr["isDraft"] else "In review"
    if pr["state"] == "CLOSED":
        return "Dropped"
    sha = (pr.get("mergeCommit") or {}).get("oid")
    if sha and sha in anc.get(("stable", repo), set()):
        return "On Stable"
    if sha and sha in anc.get(("latest", repo), set()):
        return "On Latest"
    return "Merged"


def is_final(stage, repo, pins) -> bool:
    if stage in ("On Stable", "Dropped"):
        return True
    return stage == "Merged" and repo not in pins["latest"]["repos"] and repo not in pins["stable"]["repos"]


def tier_of(pr) -> str:
    names = {l["name"] for l in pr["labels"]["nodes"]}
    for label, option, _ in TIERS:
        if label in names:
            return option
    return NO_TIER[0]


# ---- project setup ---------------------------------------------------------------

def ensure_project():
    d = gql("""query($o:String!){organization(login:$o){id projectsV2(first:50){nodes{id number title url}}}}""", o=ORG)
    org = d["organization"]
    for p in org["projectsV2"]["nodes"]:
        if p["title"] == TITLE:
            if "--describe" in sys.argv:
                gql("""mutation($p:ID!,$d:String!,$r:String!){updateProjectV2(input:{projectId:$p,shortDescription:$d,readme:$r}){projectV2{id}}}""",
                    p=p["id"], d=DESCRIPTION, r=__doc__)
            return p
    p = gql("""mutation($o:ID!,$t:String!){createProjectV2(input:{ownerId:$o,title:$t}){projectV2{id number title url}}}""",
            o=org["id"], t=TITLE)["createProjectV2"]["projectV2"]
    gql("""mutation($p:ID!,$d:String!,$r:String!){updateProjectV2(input:{projectId:$p,shortDescription:$d,readme:$r}){projectV2{id}}}""",
        p=p["id"], d=DESCRIPTION, r=__doc__)
    return p


def fields(pid):
    d = gql("""query($p:ID!){node(id:$p){... on ProjectV2{fields(first:50){nodes{
      ... on ProjectV2FieldCommon{id name dataType}
      ... on ProjectV2SingleSelectField{options{id name}}}}}}}""", p=pid)
    return {f["name"]: f for f in d["node"]["fields"]["nodes"] if f}


def ensure_select(pid, fs, name, options):
    """options: [(name, colour, description)]. Creates or reshapes a single-select field."""
    want = [{"name": n, "color": c, "description": desc} for n, c, desc in options]
    f = fs.get(name)
    if f and [o["name"] for o in f.get("options", [])] == [o["name"] for o in want]:
        return f
    if f:
        gql("""mutation($f:ID!,$o:[ProjectV2SingleSelectFieldOptionInput!]){updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:$o}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}""",
            f=f["id"], o=want)
    else:
        gql("""mutation($p:ID!,$n:String!,$o:[ProjectV2SingleSelectFieldOptionInput!]){createProjectV2Field(input:{projectId:$p,dataType:SINGLE_SELECT,name:$n,singleSelectOptions:$o}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}""",
            p=pid, n=name, o=want)
    return fields(pid)[name]


def ensure_text(pid, fs, name):
    if name in fs:
        return fs[name]
    gql("""mutation($p:ID!,$n:String!){createProjectV2Field(input:{projectId:$p,dataType:TEXT,name:$n}){projectV2Field{... on ProjectV2Field{id}}}}""",
        p=pid, n=name)
    return fields(pid)[name]


def project_items(pid):
    q = """query($p:ID!,$after:String){node(id:$p){... on ProjectV2{items(first:100,after:$after){
      pageInfo{hasNextPage endCursor}
      nodes{id isArchived content{... on PullRequest{id}}
        fieldValues(first:20){nodes{
          ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}}
          ... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{name}}}}}}}}}}"""
    items, after = {}, None
    while True:
        d = gql(q, p=pid, after=after)["node"]["items"]
        for n in d["nodes"]:
            c = n.get("content") or {}
            if not c.get("id"):
                continue
            vals = {}
            for v in n["fieldValues"]["nodes"]:
                if v and v.get("field"):
                    vals[v["field"]["name"]] = v.get("name", v.get("text"))
            items[c["id"]] = {"id": n["id"], "archived": n["isArchived"], "values": vals}
        if not d["pageInfo"]["hasNextPage"]:
            return items
        after = d["pageInfo"]["endCursor"]


def set_select(pid, item, field, option_id):
    gql("""mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}""",
        p=pid, i=item, f=field, o=option_id)


def set_text(pid, item, field, text):
    gql("""mutation($p:ID!,$i:ID!,$f:ID!,$t:String!){updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,fieldId:$f,value:{text:$t}}){projectV2Item{id}}}""",
        p=pid, i=item, f=field, t=text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--describe", action="store_true", help="rewrite the project description and readme")
    a = ap.parse_args()

    pins = release_pins()
    repos = sorted(set(pins["latest"]["repos"]) | set(pins["stable"]["repos"]) | set(EXTRA_REPOS))
    anc = {}
    for ch in ("latest", "stable"):
        for repo, sha in pins[ch]["repos"].items():
            anc[(ch, repo)] = ancestors(repo, sha)

    now = dt.datetime.now(dt.timezone.utc)
    wanted = []  # (pr, repo, stage, tier, final_old)
    for repo in repos:
        try:
            prs = pull_requests(repo)
        except RuntimeError as e:
            print(f"skip {repo}: {e}", file=sys.stderr)
            continue
        for pr in prs:
            st = stage_of(pr, repo, pins, anc)
            ended = pr.get("mergedAt") or pr.get("closedAt")
            old = bool(ended) and (now - dt.datetime.fromisoformat(ended.replace("Z", "+00:00"))).days >= ARCHIVE_AFTER_DAYS
            wanted.append((pr, repo, st, tier_of(pr), is_final(st, repo, pins) and old))

    counts = {}
    for _, _, st, _, gone in wanted:
        if not gone:
            counts[st] = counts.get(st, 0) + 1
    print(f"latest {pins['latest']['version']} · stable {pins['stable']['version']} · {len(repos)} repos")
    print("on board:", json.dumps(counts))
    if a.dry_run:
        return

    proj = ensure_project()
    pid = proj["id"]
    fs = fields(pid)
    status = ensure_select(pid, fs, "Status", STAGES)
    tier = ensure_select(pid, fs, "Tier", [(o, c, l) for l, o, c in TIERS] + [(NO_TIER[0], NO_TIER[1], "No tier label yet")])
    author = ensure_text(pid, fs, "Opened by")
    sopt = {o["name"]: o["id"] for o in status["options"]}
    topt = {o["name"]: o["id"] for o in tier["options"]}
    items = project_items(pid)

    added = changed = archived = 0
    failed = 0
    for pr, repo, st, tr, gone in wanted:
        try:
            a_, c_, r_ = sync_one(pid, pr, st, tr, gone, items.get(pr["id"]), status, tier, author, sopt, topt)
        except RuntimeError as e:
            print(f"{repo}#{pr['number']}: {e}", file=sys.stderr)
            failed += 1
            continue
        added += a_; changed += c_; archived += r_
    print(f"{proj['url']}  added {added} · updated {changed} · archived {archived} · failed {failed}")
    if failed:
        sys.exit(1)


def sync_one(pid, pr, st, tr, gone, it, status, tier, author, sopt, topt):
    """Returns (added, changed, archived) as 0/1 each."""
    added = changed = archived = 0
    if gone:
        if it and not it["archived"]:
            gql("""mutation($p:ID!,$i:ID!){archiveProjectV2Item(input:{projectId:$p,itemId:$i}){item{id}}}""", p=pid, i=it["id"])
            archived += 1
        return added, changed, archived
    if not it:
        iid = gql("""mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}""",
                  p=pid, c=pr["id"])["addProjectV2ItemById"]["item"]["id"]
        it = {"id": iid, "archived": False, "values": {}}
        added += 1
    elif it["archived"]:
        gql("""mutation($p:ID!,$i:ID!){unarchiveProjectV2Item(input:{projectId:$p,itemId:$i}){item{id}}}""", p=pid, i=it["id"])
    v = it["values"]
    login = (pr.get("author") or {}).get("login") or "ghost"
    touched = False
    if v.get("Status") != st:
        set_select(pid, it["id"], status["id"], sopt[st]); touched = True
    if v.get("Tier") != tr:
        set_select(pid, it["id"], tier["id"], topt[tr]); touched = True
    if v.get("Opened by") != login:
        set_text(pid, it["id"], author["id"], login); touched = True
    changed += touched
    return added, changed, archived


if __name__ == "__main__":
    main()
