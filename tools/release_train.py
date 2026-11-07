#!/usr/bin/env python3
"""Release train: get merged Recommended fixes onto Stable within a day, gated by a passed upgrade test.

    python3 tools/release_train.py plan                     # read-only: is Stable behind main with merged fixes?
    python3 tools/release_train.py run                      # cut -> mirror -> upgrade test -> promote (or stop)
    python3 tools/release_train.py run --dry-run            # everything local; stops before any push or merge
    python3 tools/release_train.py run --dry-run --force    # same, even when no fix is waiting (proves the path)
    python3 tools/release_train.py cut [--dry-run]          # For testers: cut + mirror main's newest published images
    python3 tools/release_train.py promote-soaked [--dry-run]   # For everyone: latest after 72h, no release-blocker

For testers / For everyone (Miguel + James, Nov 2026; proposed DECISIONS amendment of #75 in docs/RELEASE_AUTOMATION.md):
`cut` is what .github/workflows/release-cut.yml runs after any component merge to main publishes its image: every
newer published Wizard UX / Agent Service main commit is cut onto latest (not only Recommended fixes), mirrored, and
it stops there (no rig, no promotion). `promote-soaked` is what .github/workflows/release-promote.yml runs on a
schedule: when releases/latest has been latest for >= SOAK_HOURS (promote_stable.latest_since) and no issue labelled
`release-blocker` is open anywhere in the org, it runs the same installed upgrade test from the current Stable and
promotes WITHOUT --fast-track (the normal soaked gate), then mirrors. Anything missing: it waits and says why.

What `run` does, in order, and where it stops:

1. Find merged PRs titled "Recommended fix…" (or labelled `tier: recommended fix`) in Wizard UX, Agent Service and
   the App Manager that Stable's pinned commits lack. None: report "nothing to release" and stop.
2. Pick the candidate. If `releases/latest` already carries every waiting fix, the candidate is latest itself.
   Otherwise cut the next patch release onto latest: latest's JSON with Wizard UX / Agent Service moved to the newest
   main commit whose public image published (push run green on main, multi-arch digest from the registry). App
   Manager fixes are reported for a manual cut (its image/maintenance-branch provenance needs a person), never
   auto-cut. `tools/check_release.py` (online) and `promote_stable.py cut/check` must pass; then the wizard-os PR and
   the byte-identical wizard-app-manager mirror PR are opened and merged (the mirror waits for its own CI).
3. Run the documented installed upgrade test from the CURRENT Stable to the candidate on a disposable KVM guest
   (tools/acceptance/upgrade-rig/kvm_upgrade.py, public os.sh). Failed: report and stop; Stable does not move.
4. Classify honestly: `fix` only when every change between Stable and the candidate is a Recommended fix or
   maintenance; any feature, strong suggestion, opinionated or unlabelled PR, or any other moved pin (default apps,
   App Manager, Hermes) makes it `feature` (launch-phase fast-track, DECISIONS #93) and is listed in --notes.
   Owner rule (Miguel, 29 Oct 2026): only a `fix` candidate is fast-tracked. A `feature` candidate stops here, on
   Latest (early testers first), and goes to Stable by the normal 72h soak (`promote_stable.py promote` without
   --fast-track). `--feature-fast-track` restores the launch-phase path (DECISIONS #93) for one run.
5. Promote with `promote_stable.py promote --fast-track` plus the evidence doc, open and merge the promotion PR,
   then mirror `stable` + `promotions/<v>.json` into wizard-app-manager and merge after its CI.

Never promotes without a passed upgrade test; never touches a real box. `--dry-run` serves the candidate from a local
release directory to the guest (WIZARD_RELEASE_BASE, disclosed in the report), commits the cut and promotion only in
a scratch clone, runs `promote_stable.py check`, and stops before any push, PR or merge.

State and reports: ~/.wizard-os/release-train/ (reports/<stamp>.md|json, last.md). Needs gh (repo scope), git,
docker (buildx imagetools), and the KVM rig's tools for step 3.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ORG = "humanitylabs-org"
WOS, WAM = f"{ORG}/wizard-os", f"{ORG}/wizard-app-manager"
# Non-author reviewers asked when Codex cannot review, so the PR lands in their GitHub review queue.
FALLBACK_REVIEWERS = [r for r in os.environ.get("WIZARD_TRAIN_REVIEWERS", "defleur-agents").split(",") if r.strip()]
# image component -> (repo, default_apps slot that pins the same commit)
IMAGE_COMPONENTS = {"wizard-ux": (f"{ORG}/wizard-ux", "shell"),
                    "wizard-agent-service": (f"{ORG}/wizard-agent-service", "agent-service")}
FIX_REPOS = {**{c: r for c, (r, _) in IMAGE_COMPONENTS.items()}, "wizard-app-manager": WAM}
PUBLISH_WORKFLOW = "Publish public image"
STATE = Path(os.environ.get("WIZARD_TRAIN_HOME", Path.home() / ".wizard-os" / "release-train"))
RIG = Path(__file__).resolve().parent / "acceptance" / "upgrade-rig" / "kvm_upgrade.py"
PUBLIC_MIRROR = f"https://raw.githubusercontent.com/{WAM}/main/releases"
IDENTITY = ["-c", "user.name=Oscar", "-c", "user.email=262056908+oscarhenrycollins@users.noreply.github.com"]
VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,40}")


def _key(v: str) -> tuple:
    return tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"[.+-]", v))


def say(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def sh(cmd: list[str], cwd: Path | None = None, check: bool = True, timeout: float = 900, env=None) -> str:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, **(env or {})})
    if check and p.returncode:
        raise Stop(f"`{' '.join(cmd[:5])}` failed ({p.returncode}): {(p.stderr or p.stdout).strip()[-500:]}")
    return p.stdout


def gh_json(args: list[str], timeout: float = 120):
    return json.loads(sh(["gh", *args], timeout=timeout) or "null")


class Stop(Exception):
    """The train stops here; the message is the report's reason."""


# The scheduler wraps a run in `timeout 3600`; a run killed from outside writes no report. Every wait stops itself
# with a Stop (and so a report) before this budget runs out. Override with WIZARD_TRAIN_BUDGET_S.
RUN_BUDGET_S = float(os.environ.get("WIZARD_TRAIN_BUDGET_S", "3300"))
RUN_STARTED = time.time()
CODEX_OUT_OF_CREDITS = "usage limits have been reached"


def run_deadline() -> float:
    return RUN_STARTED + RUN_BUDGET_S


def codex_out_of_credits(repo: str, n: str, since: str) -> bool:
    """Did the Codex connector answer on this PR, after `since` (ISO time), that it has no review credits left?"""
    comments = gh_json(["api", f"repos/{repo}/issues/{n}/comments", "--paginate"]) or []
    return any("codex" in (c.get("user") or {}).get("login", "") and c.get("created_at", "") >= since
               and CODEX_OUT_OF_CREDITS in c.get("body", "") for c in comments)


# ---------------------------------------------------------------- repos


def clone(repo: str, work: Path) -> Path:
    """A private, fetched clone per repo (all branches: release pins may sit on maintenance branches)."""
    d = work / "repos" / repo.split("/")[1]
    if not (d / ".git").exists() and not (d / "HEAD").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        sh(["gh", "repo", "clone", repo, str(d), "--", "-q", "--no-checkout"], timeout=1800)
    sh(["git", "-C", str(d), "fetch", "-q", "--prune", "origin", "+refs/heads/*:refs/remotes/origin/*"], timeout=900)
    return d


def worktree(repo_dir: Path, path: Path, ref: str = "origin/main") -> Path:
    if path.exists():
        sh(["git", "-C", str(repo_dir), "worktree", "remove", "--force", str(path)], check=False)
        shutil.rmtree(path, ignore_errors=True)
    sh(["git", "-C", str(repo_dir), "worktree", "prune"])
    sh(["git", "-C", str(repo_dir), "worktree", "add", "-q", "--detach", str(path), ref])
    return path


def show(repo_dir: Path, ref: str, path: str) -> str:
    return sh(["git", "-C", str(repo_dir), "show", f"{ref}:{path}"])


def is_ancestor(repo_dir: Path, a: str, b: str) -> bool:
    return subprocess.run(["git", "-C", str(repo_dir), "merge-base", "--is-ancestor", a, b],
                          capture_output=True).returncode == 0


# ---------------------------------------------------------------- PRs and tiers


def merged_prs(repo: str, repo_dir: Path, old: str, new: str) -> list[dict]:
    """PRs merged on the first-parent line old..new, with title and labels (squash `(#n)` and merge commits)."""
    log = sh(["git", "-C", str(repo_dir), "log", "--first-parent", "--format=%H%x09%s", f"{old}..{new}"])
    nums: dict[int, str] = {}
    for line in log.splitlines():
        sha, _, subj = line.partition("\t")
        m = re.match(r"Merge pull request #(\d+)", subj) or re.search(r"\(#(\d+)\)\s*$", subj)
        if m:
            nums.setdefault(int(m.group(1)), sha)
    if not nums:
        return []
    known = {p["number"]: p for p in gh_json(["pr", "list", "-R", repo, "--state", "merged", "-L", "400",
                                              "--json", "number,title,labels"])}
    out = []
    for n, sha in nums.items():
        p = known.get(n) or gh_json(["pr", "view", str(n), "-R", repo, "--json", "number,title,labels"])
        out.append({"repo": repo, "number": n, "commit": sha, "title": p.get("title", ""),
                    "labels": sorted(lb["name"] for lb in p.get("labels", []))})
    return sorted(out, key=lambda p: p["number"])


def tier(pr: dict) -> str:
    """fix | maintenance | feature (anything not provably a fix or maintenance counts as a feature: honest)."""
    t, labels = pr["title"].strip().lower(), set(pr["labels"])
    if t.startswith("recommended fix") or "tier: recommended fix" in labels:
        return "fix"
    if "needs: james review" in labels or labels & {"tier: strong suggestion", "tier: opinionated"}:
        return "feature"
    if t.startswith(("maintenance", "docs", "ci:", "ci(", "test", "chore")) or "tier: maintenance" in labels:
        return "maintenance"
    return "feature"


# ---------------------------------------------------------------- images


def published(repo: str, repo_dir: Path, limit: int = 40) -> dict | None:
    """Newest main commit whose public image fully published (push run green, no skipped job) with a multi-arch digest."""
    runs = gh_json(["run", "list", "-R", repo, "--workflow", PUBLISH_WORKFLOW, "--branch", "main", "--event", "push",
                    "-L", str(limit), "--json", "databaseId,headSha,conclusion,status,url"])
    for r in runs:
        if r.get("conclusion") != "success":
            continue
        jobs = gh_json(["run", "view", str(r["databaseId"]), "-R", repo, "--json", "jobs"]).get("jobs", [])
        # Publication jobs must all have succeeded (the "PR build" matrix is skipped on push by design).
        need = [j for j in jobs if not str(j.get("name", "")).startswith("PR build")]
        names = {str(j.get("name")) for j in need}
        if any(j.get("conclusion") != "success" for j in need) or not {"publish", "finalize", "anonymous-pull"} <= names:
            continue
        sha = r["headSha"]
        if not is_ancestor(repo_dir, sha, "origin/main"):
            continue
        ref = f"ghcr.io/{repo}:sha-{sha}"
        raw = sh(["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest}}"], check=False)
        try:
            man = json.loads(raw)
        except ValueError:
            continue
        archs = {str((m.get("platform") or {}).get("architecture")) for m in man.get("manifests", [])}
        if not {"amd64", "arm64"} <= archs:
            continue
        return {"commit": sha, "ref": ref, "digest": man["digest"], "ci_run": r["url"], "architectures": ["amd64", "arm64"]}
    return None


# ---------------------------------------------------------------- plan


def plan(work: Path, any_merge: bool = False) -> dict:
    """What the train would do. any_merge (For testers `cut`): also move every image component whose newest published
    main commit is newer than latest's pin, fix or not."""
    wos = clone(WOS, work)
    rel = lambda name: show(wos, "origin/main", f"releases/{name}")   # noqa: E731
    stable, latest = rel("stable").strip(), rel("latest").strip()
    S, L = json.loads(rel(f"{stable}.json")), json.loads(rel(f"{latest}.json"))
    out: dict = {"stable": stable, "latest": latest, "components": {}, "waiting_fixes": [], "manual": [],
                 "unpublished": [], "moves": {}}
    for comp, repo in FIX_REPOS.items():
        d = clone(repo, work)
        s_c, l_c = S["components"][comp]["commit"], L["components"][comp]["commit"]
        base = s_c if is_ancestor(d, s_c, "origin/main") else \
            sh(["git", "-C", str(d), "merge-base", s_c, "origin/main"]).strip()   # stable pinned a maintenance branch
        fixes = [x for x in merged_prs(repo, d, base, "origin/main") if tier(x) == "fix" and not is_ancestor(d, x["commit"], s_c)]
        on_latest = [x for x in fixes if is_ancestor(d, x["commit"], l_c)]
        missing = [x for x in fixes if x not in on_latest]
        ready: list[dict] = []
        info: dict = {"stable": s_c, "latest": l_c, "fixes": fixes}
        if missing and comp in IMAGE_COMPONENTS:
            pub = published(repo, d)
            info["published"] = pub
            ready = [x for x in missing if pub and is_ancestor(d, x["commit"], pub["commit"])]
            if ready:
                out["moves"][comp] = pub
            out["unpublished"] += [f"{repo}#{x['number']} {x['title']} (image not published yet)"
                                   for x in missing if x not in ready]
        elif missing:
            out["manual"] += [f"{repo}#{x['number']} {x['title']} (App Manager: cut by hand)" for x in missing]
        out["waiting_fixes"] += [f"{repo}#{x['number']} {x['title']}" for x in on_latest + ready]
        out["components"][comp] = info
        if any_merge and comp in IMAGE_COMPONENTS and comp not in out["moves"]:
            pub = info.get("published") or published(repo, d)
            if pub and pub["commit"] != l_c and not is_ancestor(d, pub["commit"], l_c):
                out["moves"][comp] = pub
    if out["moves"]:
        out["candidate"], out["cut"] = next_version(wos), True
    elif out["waiting_fixes"] and _key(latest) > _key(stable):
        out["candidate"], out["cut"] = latest, False
    else:
        out["candidate"], out["cut"] = None, False
    return out


def next_version(wos: Path) -> str:
    names = sh(["git", "-C", str(wos), "ls-tree", "--name-only", "origin/main", "releases/"]).split()
    top = max((m.group(1) for n in names if (m := re.fullmatch(r"releases/(\d+\.\d+\.\d+)\.json", n))), key=_key)
    a, b, c = top.split(".")
    return f"{a}.{b}.{int(c) + 1}"


def candidate_json(L: dict, version: str, moves: dict, stable: str, notes: list[str]) -> dict:
    d = json.loads(json.dumps(L))
    d["version"] = version
    d["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    names = []
    for comp, pub in moves.items():
        repo, slot = IMAGE_COMPONENTS[comp]
        old = d["components"][comp]["commit"]
        mine = [n for n in notes if n.startswith(repo + "#")]
        d["components"][comp].update(commit=pub["commit"], branch="main",
                                     note=f"Official main at {pub['commit'][:8]} (release train)"
                                          + (": carries " + "; ".join(mine) if mine else ""))
        im = d["images"][comp]
        im.update(ref=pub["ref"], digest=pub["digest"], ci_run=pub["ci_run"], architectures=pub["architectures"])
        for k in ("source_commit", "image_inputs", "note"):
            im.pop(k, None)
        if slot in d.get("default_apps", {}) and d["default_apps"][slot]:
            d["default_apps"][slot]["commit"] = pub["commit"]
        names.append(f"{'Wizard UX' if comp == 'wizard-ux' else 'Agent Service'} {old[:8]} -> {pub['commit'][:8]}")
    d["name"] = f"Wizard OS {version} — {L['version']} with " + ", ".join(names) + " (fixes)"
    d["about"] = (f"Latest {L['version']} with " + ", ".join(names) + ". Cut by the release train for merged "
                  "Recommended fixes: " + "; ".join(notes) + f". Stable stays {stable} until the installed upgrade test passes.")
    d["notes"] = f"Latest. Exactly {L['version']} except " + ", ".join(names) + "."
    return d


def ride_alongs(work: Path, S: dict, C: dict) -> tuple[str, list[str], list[dict]]:
    """Every change Stable -> candidate, and the honest classification."""
    items, prs = [], []
    for comp, repo in FIX_REPOS.items():
        s_c, c_c = S["components"][comp]["commit"], C["components"][comp]["commit"]
        if s_c == c_c:
            continue
        d = clone(repo, work)
        base = s_c if is_ancestor(d, s_c, c_c) else sh(["git", "-C", str(d), "merge-base", s_c, c_c]).strip()
        got = merged_prs(repo, d, base, c_c)
        prs += got
        if not got:
            items.append(f"{comp} {s_c[:8]} -> {c_c[:8]} (no PR merges on the first-parent line: maintenance branch)")
    feature = any(tier(p) == "feature" for p in prs) or any(i.startswith("wizard-app-manager") for i in items)
    for key in sorted(set(S) | set(C)):
        if key in ("version", "name", "date", "about", "notes", "components", "images"):
            continue
        if key == "default_apps":
            for slot in sorted(set(S[key]) | set(C[key])):
                a, b = (S[key].get(slot) or {}), (C[key].get(slot) or {})
                if slot in ("shell", "agent-service"):
                    continue          # moves with its component
                if a != b:
                    items.append(f"default app {slot}: {a.get('app')} {str(a.get('commit'))[:8]} {a.get('index_version')}"
                                 f" -> {b.get('app')} {str(b.get('commit'))[:8]} {b.get('index_version')}")
                    feature = True
        elif S.get(key) != C.get(key):
            items.append(f"{key} changed")
            feature = True
    for comp in set(S.get("components", {})) | set(C.get("components", {})):
        if comp not in FIX_REPOS and S["components"].get(comp) != C["components"].get(comp):
            items.append(f"{comp} {str((S['components'].get(comp) or {}).get('commit'))[:8]} -> "
                         f"{str((C['components'].get(comp) or {}).get('commit'))[:8]}")
            feature = True
    return ("feature" if feature else "fix"), items, prs


# ---------------------------------------------------------------- PR mechanics


def open_and_merge(repo: str, wt: Path, branch: str, title: str, body: str, label: str, need_checks: bool,
                   timeout: float = 3600) -> str:
    sh(["git", "-C", str(wt), "push", "-q", "-f", "origin", f"HEAD:refs/heads/{branch}"])
    url = sh(["gh", "pr", "create", "-R", repo, "--base", "main", "--head", branch, "--title", title, "--body", body]).strip()
    n = url.rstrip("/").rsplit("/", 1)[1]
    sh(["gh", "api", "-X", "POST", f"repos/{repo}/issues/{n}/labels", "-f", f"labels[]={label}"], check=False)
    head = sh(["git", "-C", str(wt), "rev-parse", "HEAD"]).strip()
    deadline, opened, nudged = min(time.time() + timeout, run_deadline()), time.time(), False
    opened_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    while need_checks:
        time.sleep(30)
        checks = gh_json(["pr", "view", n, "-R", repo, "--json", "statusCheckRollup"])["statusCheckRollup"]
        states = [(c.get("name") or c.get("context"),
                   c.get("status") or ("PENDING" if c.get("state") == "PENDING" else "COMPLETED"),
                   c.get("conclusion") or c.get("state")) for c in checks]
        if any(s == "COMPLETED" and c not in ("SUCCESS", "SKIPPED", "NEUTRAL") for _, s, c in states):
            raise Stop(f"{url}: a check failed: {[x for x in states if x[2] not in ('SUCCESS', 'SKIPPED', 'NEUTRAL', None, '')]}")
        if states and all(s == "COMPLETED" for _, s, _ in states):
            threads = gh_json(["api", "graphql", "-f", "query=query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r)"
                               "{pullRequest(number:$n){reviewThreads(first:50){nodes{isResolved}}}}}",
                               "-F", f"o={repo.split('/')[0]}", "-F", f"r={repo.split('/')[1]}", "-F", f"n={n}"])
            open_threads = [t for t in threads["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
                            if not t["isResolved"]]
            if open_threads:
                raise Stop(f"{url}: {len(open_threads)} unresolved review finding(s); a person must look")
            # DECISIONS #96: a release that reaches every install needs a non-author review, and an agent counts.
            # On the App Manager mirror that is Codex: wait for its review of this exact head, clean.
            state = codex_state(repo, n)
            if state is None or state.get("commit_sha") != head or state.get("status") != "completed":
                if codex_out_of_credits(repo, n, opened_iso):
                    request_reviewers(repo, n)
                    raise Stop(f"{url}: Codex is out of review credits, so no non-author review of {head[:8]} "
                               f"(DECISIONS #96); review requested from {', '.join(FALLBACK_REVIEWERS)}; they review and merge")
                if time.time() - opened > 600 and not nudged:
                    sh(["gh", "pr", "comment", n, "-R", repo, "-b", "@codex review"], check=False)
                    nudged = True
                if time.time() > deadline:
                    raise Stop(f"{url}: no completed Codex review of {head[:8]} yet; merge it after the review")
                continue
            if state.get("has_unresolved_findings") or state.get("has_any_findings"):
                raise Stop(f"{url}: Codex found something in the release mirror; a person must look")
            break
        if time.time() > deadline:
            raise Stop(f"{url}: checks still running after {timeout // 60:.0f} min")
    sh(["gh", "pr", "merge", n, "-R", repo, "--merge", "--match-head-commit", head])
    return url


def request_reviewers(repo: str, n: str) -> None:
    """Put the PR in a teammate's review queue instead of leaving it for someone to notice."""
    for r in FALLBACK_REVIEWERS:
        sh(["gh", "pr", "edit", n, "-R", repo, "--add-reviewer", r.strip()], check=False)


def codex_state(repo: str, n: str) -> dict | None:
    """The latest `codex-review-state` the Codex connector left on the PR (None: no review yet)."""
    comments = gh_json(["api", f"repos/{repo}/issues/{n}/comments", "--paginate"]) or []
    for c in reversed(comments):
        m = re.search(r"codex-review-state:v1 (\{.*?\}) -->", c.get("body", ""), re.S)
        if m and "codex" in (c.get("user") or {}).get("login", ""):
            try:
                return json.loads(m.group(1)).get("code_review")
            except ValueError:
                return None
    return None


def served(name: str, sha256: str) -> bool:
    """Does the public installer mirror serve releases/<name> with exactly this content?"""
    try:
        req = urllib.request.Request(f"{PUBLIC_MIRROR}/{name}", headers={"User-Agent": "curl/8 wizard-release-train"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return hashlib.sha256(r.read()).hexdigest() == sha256
    except OSError:
        return False


def wait_public(name: str, sha256: str, timeout: float = 900) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if served(name, sha256):
            return
        time.sleep(30)
    raise Stop(f"the public mirror does not serve releases/{name} ({sha256[:12]}) after {timeout // 60:.0f} min")


@contextlib.contextmanager
def serve(directory: Path):
    """A loopback HTTP server for a dry run's local release directory (the guest reaches it as 10.0.2.2)."""
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv.server_address[1]
    finally:
        srv.shutdown()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- run


BLOCKER_LABEL = "release-blocker"
SOAK_HOURS = 72          # same as promote_stable.SOAK_HOURS (DECISIONS #75); test_release_train checks they match


def release_blockers() -> list[str]:
    """Open issues labelled release-blocker anywhere in the org. Fails closed: an unreadable answer stops promotion."""
    got = gh_json(["search", "issues", "--owner", ORG, "--label", BLOCKER_LABEL, "--state", "open",
                   "--json", "url,title", "--limit", "50"])
    if not isinstance(got, list):
        raise Stop(f"could not read open {BLOCKER_LABEL} issues")
    return [f"{x.get('url')} {x.get('title', '')[:80]}" for x in got]


def soaked_for(version: str, releases: Path, now: float | None = None) -> float | None:
    """Hours <version> has been releases/latest (from git history, the same source promote_stable uses)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("promote_stable", Path(__file__).resolve().parent / "promote_stable.py")
    ps = importlib.util.module_from_spec(spec); spec.loader.exec_module(ps)   # type: ignore[union-attr]
    since = ps.latest_since(version, releases)
    if not since:
        return None
    t = datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp()
    return ((now if now is not None else time.time()) - t) / 3600


def run(work: Path, dry: bool, force: bool, rig_args: list[str], feature_fast_track: bool = False,
        mode: str = "train") -> dict:
    """mode "train": today's fix train. "cut": For testers (cut + mirror any newer published main, then stop).
    "soaked": For everyone (promote latest after SOAK_HOURS with no release-blocker; normal gate, no fast-track)."""
    rep: dict = {"started": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "dry_run": dry, "force": force,
                 "steps": []}
    step = lambda s: (rep["steps"].append(s), say(s))   # noqa: E731
    p = plan(work, any_merge=(mode == "cut")) if mode != "soaked" else plan(work)
    rep["mode"] = mode
    rep["plan"] = {k: v for k, v in p.items() if k != "components"}
    stable, latest = p["stable"], p["latest"]
    if mode == "soaked":
        # For everyone takes latest as it is: never a new cut here.
        if _key(latest) <= _key(stable):
            rep["outcome"] = f"nothing to promote: For everyone ({stable}) already has latest ({latest})"
            return rep
        hours = soaked_for(latest, clone(WOS, work) / "releases")
        if hours is None or hours < SOAK_HOURS:
            rep["outcome"] = (f"WAITING: {latest} has been For testers for "
                              f"{'an unknown time' if hours is None else f'{hours:.0f}h'}; it moves to For everyone "
                              f"after {SOAK_HOURS}h. Stable stays {stable}.")
            return rep
        blockers = release_blockers()
        if blockers:
            rep["outcome"] = (f"HELD: {len(blockers)} open {BLOCKER_LABEL} issue(s): " + "; ".join(blockers)
                              + f". Stable stays {stable}.")
            return rep
        p["candidate"], p["cut"], p["moves"] = latest, False, {}
        step(f"{latest} soaked {hours:.0f}h on For testers; no open {BLOCKER_LABEL}")
    step(f"stable {stable}, latest {latest}; waiting fixes: {len(p['waiting_fixes'])}; to move: {sorted(p['moves'])}")
    for m in p["manual"] + p["unpublished"]:
        step(f"not in this train: {m}")
    if not p["candidate"]:
        if mode == "cut":
            rep["outcome"] = f"nothing to cut: latest {latest} already pins main's newest published images"
            return rep
        if not force:
            rep["outcome"] = "nothing to release: no merged Recommended fix is missing from Stable (or none is publishable yet)"
            return rep
        # forced proof run: a candidate made from the newest published main images even without a fix
        for comp, (repo, _) in IMAGE_COMPONENTS.items():
            pub = published(repo, clone(repo, work))
            if pub and pub["commit"] != p["components"][comp]["latest"]:
                p["moves"][comp] = pub
        p["candidate"], p["cut"] = (next_version(clone(WOS, work)), True) if p["moves"] else (latest, False)
        if p["candidate"] == stable:
            rep["outcome"] = "forced, but latest is stable and main has no newer published image: nothing to test"
            return rep
        step(f"--force: no fix waiting; proving the path with candidate {p['candidate']} (moves {sorted(p['moves'])})")
    wos = clone(WOS, work)
    wam = clone(WAM, work)
    wt = worktree(wos, work / "wt-wizard-os")
    mwt = worktree(wam, work / "wt-wizard-app-manager")
    S = json.loads((wt / "releases" / f"{stable}.json").read_text())
    L = json.loads((wt / "releases" / f"{latest}.json").read_text())
    V = p["candidate"]
    fix_notes = [f"{f.split(' ', 1)[0]} {f.split(' ', 1)[1][:90]}" for f in p["waiting_fixes"]]
    branch_cut, branch_promo = f"release/{V}-train", f"promote/{V}-train"
    if p["cut"]:
        C = candidate_json(L, V, p["moves"], stable, fix_notes or ["no fix (forced proof run)"])
        (wt / "releases" / f"{V}.json").write_text(json.dumps(C, indent=2) + "\n")
        sh([sys.executable, "tools/check_release.py", f"releases/{V}.json"], cwd=wt, timeout=600)
        sh([sys.executable, "tools/promote_stable.py", "cut", V], cwd=wt)
        sh([sys.executable, "tools/promote_stable.py", "check"], cwd=wt)
        # wizard-os CI runs on a self-hosted runner that is often offline: run the release tests here.
        for pattern in ("test_promote_stable.py", "test_check_release.py", "test_release_train.py"):
            if not (wt / "tools" / "tests" / pattern).is_file():
                continue
            sh([sys.executable, "-m", "unittest", "discover", "-s", "tools/tests", "-p", pattern], cwd=wt, timeout=900)
        sh(["git", "-C", str(wt), "checkout", "-q", "-B", branch_cut])
        sh(["git", *IDENTITY, "-C", str(wt), "add", f"releases/{V}.json", "releases/latest"])
        sh(["git", *IDENTITY, "-C", str(wt), "commit", "-qm", f"Cut {V} onto latest (release train): {C['name']}"])
        step(f"cut {V}: check_release ok, channels ok ({'local only' if dry else 'pushing'})")
    else:
        C = L
    cls, items, prs = ride_alongs(work, S, C)
    rep["classification"], rep["ride_alongs"] = cls, items
    rep["prs"] = [{**x, "tier": tier(x)} for x in prs]
    step(f"classification {cls}: {sum(tier(x) == 'fix' for x in prs)} fix, "
         f"{sum(tier(x) == 'feature' for x in prs)} feature, {sum(tier(x) == 'maintenance' for x in prs)} maintenance PRs; "
         f"{len(items)} other changes")
    rel_json = wt / "releases" / f"{V}.json"
    if p["cut"]:
        # Mirror the cut into the App Manager (the copy installers read), byte-identical.
        shutil.copyfile(rel_json, mwt / "releases" / f"{V}.json")
        shutil.copyfile(wt / "releases" / "latest", mwt / "releases" / "latest")
        with open(mwt / "releases" / "README.md", "a") as f:
            f.write(f"\n## {V} provenance\n\nCanonical: wizard-os releases/{V}.json (release train). "
                    f"SHA256: `{sha(rel_json)}`.\n{C['about']}\nChannel: on latest only.\n")
        sh(["git", "-C", str(mwt), "checkout", "-q", "-B", f"release/{V}-mirror-train"])
        sh(["git", *IDENTITY, "-C", str(mwt), "add", "releases"])
        sh(["git", *IDENTITY, "-C", str(mwt), "commit", "-qm", f"Mirror {V} onto latest (release train)"],
           env={"LEFTHOOK": "0"})
        if not dry:
            body = (f"Maintenance (release train): cut **{V}** onto latest. Stable stays {stable} until the installed "
                    f"upgrade test from {stable} passes.\n\n" + "\n".join(f"- {x}" for x in fix_notes)
                    + "\n\nGate: `tools/check_release.py` online ok, `promote_stable.py check` ok, release tests "
                    "(test_promote_stable, test_check_release, test_release_train) passed locally because the "
                    "self-hosted wizard-os runner may be offline. Ride-alongs since "
                    f"Stable ({cls}):\n" + "\n".join(f"- {x['repo'].split('/')[1]}#{x['number']} [{tier(x)}] {x['title']}"
                                                     for x in prs) + "".join(f"\n- {i}" for i in items))
            rep["cut_pr"] = open_and_merge(WOS, wt, branch_cut, f"Maintenance: cut {V} onto latest (release train)",
                                           body, "tier: maintenance", need_checks=False)
            mbody = (f"Maintenance: mirror **{V}** onto latest, byte-identical to canonical ({rep['cut_pr']}). "
                     f"`releases/{V}.json` sha256 `{sha(rel_json)}`. Stable unchanged ({stable}).\n\nRollback: "
                     f"`releases/latest` back to {latest}.")
            rep["mirror_pr"] = open_and_merge(WAM, mwt, f"release/{V}-mirror-train",
                                              f"Maintenance: mirror Wizard OS {V} onto latest (release train)", mbody,
                                              "tier: maintenance", need_checks=True)
            step(f"cut merged {rep['cut_pr']}, mirror merged {rep['mirror_pr']}")
            wait_public(f"{V}.json", sha(rel_json))
    if mode == "cut":
        rep["outcome"] = (f"CUT {V} onto For testers (latest){' (dry run, local only)' if dry else ''}; For everyone "
                          f"stays {stable} until {V} has soaked {SOAK_HOURS}h with no {BLOCKER_LABEL}.")
        return rep
    # Features go to early testers first: a feature candidate stays on Latest for the normal soak (owner rule).
    if cls != "fix" and not feature_fast_track and mode != "soaked":
        rep["outcome"] = (f"ON LATEST ONLY: {V} carries features, so it soaks 72h on Latest before Stable "
                          f"(promote_stable.py promote {V} --from {stable} after the soak and an upgrade test). "
                          f"Stable stays {stable}.")
        return rep
    # A candidate that was cut by an earlier run (latest itself) may still be unmirrored, e.g. its mirror PR waits
    # for a review. The installer would 404 on it, so don't spend the rig on it: report the blocker instead.
    if not dry and not p["cut"]:
        if not served(f"{V}.json", sha(rel_json)):
            rep["outcome"] = (f"BLOCKED: {V} is latest but the public installer mirror ({PUBLIC_MIRROR}/{V}.json) does not "
                              f"serve it yet; merge its {WAM} mirror PR after review. No upgrade test run. "
                              f"Stable stays {stable}.")
            return rep
    # The upgrade test from the CURRENT stable, on a disposable guest, with the public command.
    out = work / f"rig-{V}.json"
    cmd = [sys.executable, str(RIG), "run", "--from", stable, "--to", V, "--out", str(out), *rig_args]
    if dry:
        local = work / "local-releases"
        shutil.rmtree(local, ignore_errors=True)
        shutil.copytree(mwt / "releases", local)     # the mirror as it would be after merge (+ hermes-lock.json)
        with serve(local) as port:
            step(f"upgrade test {stable} -> {V} on the KVM rig (dry run: candidate served locally, WIZARD_RELEASE_BASE)")
            r = subprocess.run(cmd + ["--release-base", f"http://10.0.2.2:{port}"], text=True, timeout=7200)
    else:
        step(f"upgrade test {stable} -> {V} on the KVM rig (public mirror)")
        r = subprocess.run(cmd, text=True, timeout=7200)
    rig = json.loads(out.read_text()) if out.exists() else {"passed": False, "problems": ["rig wrote no report"]}
    rep["upgrade_test"] = {k: rig.get(k) for k in ("passed", "problems", "rundir", "upgrade", "install_from")}
    if r.returncode or not rig.get("passed"):
        rep["outcome"] = f"STOPPED: the upgrade test {stable} -> {V} failed: {rig.get('problems')}. Stable stays {stable}."
        return rep
    # Evidence + promotion.
    evidence_rel = f"docs/acceptance/promote-{V}.md"
    rig_md = Path(rig["rundir"], "report.md").read_text()
    reason = (f"Release train: merged Recommended fixes ({'; '.join(fix_notes) or 'none: forced proof run'}). Installed "
              f"upgrade {stable} -> {V} passed on a disposable KVM guest (public os.sh"
              f"{', candidate served locally' if dry else ''}): {(rig.get('upgrade') or {}).get('seconds')} s, pinned, "
              "0 failed checks, doctors 0 FAIL, Hermes config/.env/SOUL unchanged.")
    notes = ("Ride-alongs onto Stable: " + "; ".join(f"{x['repo'].split('/')[1]}#{x['number']} [{tier(x)}] {x['title'][:80]}"
                                                     for x in prs) + ("; " + "; ".join(items) if items else "")
             + ". Not checked: real Tailscale/HTTPS/Serve, real chats and sign-ins, phones, a fresh install.")
    why = ([f"{V} soaked {SOAK_HOURS}h+ on For testers (latest) with no open {BLOCKER_LABEL} issue (For everyone "
            "promotion, normal gate, no fast-track)."] if mode == "soaked" else (p["waiting_fixes"] or ["(none: forced proof run)"]))
    doc = (f"# Promote {V} (release train)\n\n## Why\n\n"
           + ("" if mode == "soaked" else f"Stable {stable} lacked merged Recommended fixes:\n\n")
           + "\n".join(f"- {x}" for x in why)
           + f"\n\n## What changes ({stable} → {V})\n\n**Classification: {cls}**"
           + (" (every change is a Recommended fix or maintenance)." if cls == "fix" else
              " (launch-phase fast-track, DECISIONS #93): it carries changes that are not provably fixes.")
           + "\n\n" + "\n".join(f"- {x['repo'].split('/')[1]}#{x['number']} [{tier(x)}] {x['title']}" for x in prs)
           + "".join(f"\n- {i}" for i in items) + "\n\n## Evidence\n\n" + rig_md)
    (wt / evidence_rel).write_text(doc)
    if p["cut"] and not dry:
        sh(["git", "-C", str(wt), "fetch", "-q", "origin"])
        sh(["git", "-C", str(wt), "checkout", "-q", "-B", branch_promo, "origin/main"])
        (wt / evidence_rel).write_text(doc)
    elif not p["cut"]:
        sh(["git", "-C", str(wt), "checkout", "-q", "-B", branch_promo])
    else:
        sh(["git", "-C", str(wt), "checkout", "-q", "-B", branch_promo])   # dry: stacked on the local cut commit
    evidence = f"https://github.com/{WOS}/blob/main/{evidence_rel}"
    if mode == "soaked":     # the normal gate: promote_stable itself refuses a release that has not soaked
        sh([sys.executable, "tools/promote_stable.py", "promote", V, "--from", stable, "--evidence", evidence,
            "--notes", notes], cwd=wt)
    else:
        sh([sys.executable, "tools/promote_stable.py", "promote", V, "--from", stable, "--evidence", evidence, "--fast-track",
        "--classification", cls, "--reason", reason, "--notes", notes], cwd=wt)
    sh([sys.executable, "tools/promote_stable.py", "check"], cwd=wt)
    rec = json.loads((wt / "releases" / "promotions" / f"{V}.json").read_text())
    if mode != "soaked" and rec.get("fast_track", {}).get("classification") != cls:
        raise Stop("the promotion record's classification does not match the computed one")
    sh(["git", *IDENTITY, "-C", str(wt), "add", "releases", evidence_rel])
    sh(["git", *IDENTITY, "-C", str(wt), "commit", "-qm", f"Promote {V} to stable ({'soaked ' + str(SOAK_HOURS) + 'h, no release-blocker' if mode == 'soaked' else cls + ' fast-track'}, release train)"])
    step(f"promotion record ok ({cls}); channels ok")
    if dry:
        rep["outcome"] = (f"DRY RUN complete: {V} would be promoted ({cls}); stopped before any push, PR or merge. "
                          f"Local commits: {sh(['git', '-C', str(wt), 'log', '--oneline', '-3']).strip()}")
        rep["promotion_record"] = rec
        return rep
    how = f"after {SOAK_HOURS}h on For testers with no open {BLOCKER_LABEL}" if mode == "soaked" else f"fast-track **{cls}**"
    body = (f"Maintenance (release train): promote **{V}** to stable, {how}. Installed upgrade "
            f"{stable} → {V} passed: {evidence_rel}.\n\nRollback: `releases/stable` back to {stable}.")
    rep["promote_pr"] = open_and_merge(WOS, wt, branch_promo, f"Maintenance: promote {V} to stable (release train, {cls})",
                                       body, "tier: maintenance", need_checks=False)
    clone(WOS, work)
    clone(WAM, work)               # fetch both again: the cut and its mirror merged since the start of this run
    mwt = worktree(wam, work / "wt-wizard-app-manager")
    for f in ("stable", "latest", f"promotions/{V}.json"):
        (mwt / "releases" / f).parent.mkdir(parents=True, exist_ok=True)
        (mwt / "releases" / f).write_text(show(wos, "origin/main", f"releases/{f}"))
    with open(mwt / "releases" / "README.md", "a") as fh:
        fh.write(f"\n## stable {V}\n\nCanonical: {rep['promote_pr']} (release train). `releases/stable` → {V}; "
                 f"`promotions/{V}.json` sha256 `{sha(mwt / 'releases' / 'promotions' / f'{V}.json')}`.\n"
                 f"{'Soaked ' + str(SOAK_HOURS) + 'h on For testers' if mode == 'soaked' else 'Fast-tracked as **' + cls + '**'}. Installed upgrade {stable} → {V} passed: wizard-os {evidence_rel}.\n")
    sh(["git", "-C", str(mwt), "checkout", "-q", "-B", f"promote/{V}-mirror-train"])
    sh(["git", *IDENTITY, "-C", str(mwt), "add", "releases"])
    sh(["git", *IDENTITY, "-C", str(mwt), "commit", "-qm", f"Mirror stable {V} (release train)"], env={"LEFTHOOK": "0"})
    rep["promote_mirror_pr"] = open_and_merge(WAM, mwt, f"promote/{V}-mirror-train",
                                              f"Maintenance: mirror Wizard OS stable {V} (release train, {cls})",
                                              body.replace("promote **", "mirror stable **"), "tier: maintenance",
                                              need_checks=True)
    wait_public("stable", hashlib.sha256((V + "\n").encode()).hexdigest())
    rep["outcome"] = f"PROMOTED {V} to stable ({cls}); was {stable}."
    return rep


def write_report(rep: dict) -> Path:
    (STATE / "reports").mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    lines = [f"# Release train {stamp}{' (dry run)' if rep.get('dry_run') else ''}", "", f"**{rep.get('outcome')}**", ""]
    lines += [f"- {s}" for s in rep.get("steps", [])]
    for k in ("cut_pr", "mirror_pr", "promote_pr", "promote_mirror_pr"):
        if rep.get(k):
            lines.append(f"- {k.replace('_', ' ')}: {rep[k]}")
    if rep.get("upgrade_test"):
        lines.append(f"- upgrade test: {'passed' if rep['upgrade_test'].get('passed') else 'FAILED'} "
                     f"({rep['upgrade_test'].get('rundir')})")
    md = "\n".join(lines) + "\n"
    (STATE / "reports" / f"{stamp}.md").write_text(md)
    (STATE / "reports" / f"{stamp}.json").write_text(json.dumps(rep, indent=2, default=str) + "\n")
    (STATE / "last.md").write_text(md)
    return STATE / "reports" / f"{stamp}.md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    for name, what in (("cut", "For testers: cut + mirror main's newest published images onto latest, then stop"),
                       ("promote-soaked", "For everyone: promote latest after 72h with no open release-blocker")):
        x = sub.add_parser(name, help=what)
        x.add_argument("--dry-run", action="store_true", help="local only; stop before any push, PR or merge")
        x.add_argument("--keep-guest", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true", help="local only; stop before any push, PR or merge")
    r.add_argument("--force", action="store_true", help="go on even when no fix is waiting (proof runs)")
    r.add_argument("--keep-guest", action="store_true")
    r.add_argument("--feature-fast-track", action="store_true",
                   help="also fast-track a feature candidate to Stable (launch-phase DECISIONS #93); default: Latest only")
    ap.add_argument("--work", type=Path, default=STATE / "work")
    a = ap.parse_args(argv)
    if a.cmd == "run" and a.force and not a.dry_run:
        print("--force is for proof runs only: use it with --dry-run", file=sys.stderr)
        return 2
    a.work.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    lock = open(STATE / "train.lock", "w")
    import fcntl
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("another release train is running")
        return 0
    if a.cmd == "plan":
        p = plan(a.work)
        print(json.dumps({k: v for k, v in p.items() if k != "components"}, indent=2, default=str))
        return 0
    try:
        mode = {"cut": "cut", "promote-soaked": "soaked"}.get(a.cmd, "train")
        rep = run(a.work, a.dry_run, getattr(a, "force", False), ["--keep"] if a.keep_guest else [],
                  a.feature_fast_track if a.cmd == "run" else False, mode)
        code = 0 if not str(rep.get("outcome", "")).startswith("STOPPED") else 1
    except Stop as e:
        rep, code = {"outcome": f"STOPPED: {e}", "dry_run": a.dry_run}, 1
    path = write_report(rep)
    print((STATE / "last.md").read_text())
    print(f"report: {path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
