#!/usr/bin/env python3
"""Release train: get merged Recommended fixes onto Stable within a day, gated by a passed upgrade test.

    python3 tools/release_train.py plan                     # read-only: is Stable behind main with merged fixes?
    python3 tools/release_train.py run                      # cut -> mirror -> upgrade test -> promote (or stop)
    python3 tools/release_train.py run --dry-run            # everything local; stops before any push or merge
    python3 tools/release_train.py run --dry-run --force    # same, even when no fix is waiting (proves the path)
    python3 tools/release_train.py cut [--dry-run]          # For testers: cut + mirror main's newest published images
    python3 tools/release_train.py promote-soaked [--dry-run]   # For everyone: newest release cut 72h+ ago, no release-blocker

For testers / For everyone (Miguel + James, Nov 2026; proposed DECISIONS amendment of #75 in docs/RELEASE_AUTOMATION.md):
`cut` is what .github/workflows/release-cut.yml runs after any component merge to main publishes: every newer
published Wizard UX / Agent Service main commit, and the newest green App Manager main commit (with its newest
published image), is cut onto latest (not only Recommended fixes), mirrored, and it stops there (no rig, no
promotion). At most one cut per MIN_CUT_INTERVAL (30 min): the workflow runs `cut --wait-deferred`, so a cut asked
for sooner waits in its run until the window ends and then cuts (wizard-os#669); without the flag it ends DEFERRED. `promote-soaked` is what .github/workflows/release-promote.yml runs on a
schedule: it takes the NEWEST release above Stable that was cut onto releases/latest >= SOAK_HOURS ago
(promote_stable.latest_since, from the git history of releases/latest; latest itself keeps moving every ~30 min), and
when no issue labelled `release-blocker` is open anywhere in the org, it runs the same installed upgrade test from the
current Stable on it and promotes WITHOUT --fast-track (the normal soaked gate), then mirrors. Anything missing: it waits and says why.
`promote-soaked --check` only answers whether that is due (no clones of the components, no rig).

Mirror PRs into wizard-app-manager merge on an automated check, not a person (DECISIONS #96 as amended, Nov 2026):
`verify_mirror` proves every file the mirror PR changes is byte-identical (sha256) to the same file on wizard-os
main, and that releases/README.md only gained lines at the end; it posts the commit status
`release-mirror/byte-identical` on the PR head, and the train merges only that exact head after every other check
passed.

What `run` does, in order, and where it stops:

1. Find merged PRs titled "Recommended fix…" (or labelled `tier: recommended fix`) in Wizard UX, Agent Service and
   the App Manager that Stable's pinned commits lack. None: report "nothing to release" and stop.
2. Pick the candidate. If `releases/latest` already carries every waiting fix, the candidate is latest itself.
   Otherwise cut the next patch release onto latest: latest's JSON with Wizard UX / Agent Service moved to the newest
   main commit whose public image published (push run green on main, multi-arch digest from the registry), and the App
   Manager to its newest main commit with a green `test` run (its image: the newest published `image` run at or before
   it, pinned with source_commit + image_inputs, so check_release proves no image input changed since). App Manager
   commits that only touch releases/ (the mirror itself) never count as a move. `tools/check_release.py` (online) and `promote_stable.py cut/check` must pass; then the wizard-os PR and
   the byte-identical wizard-app-manager mirror PR are opened and merged (after its CI and `verify_mirror`).
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

State and reports: ~/.wizard-os/release-train/ (reports/<stamp>.md|json, last.md). Needs gh (RELEASE_TRAIN_TOKEN, see
docs/RELEASE_AUTOMATION.md), git,
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
# image component -> (repo, default_apps slot that pins the same commit)
IMAGE_COMPONENTS = {"wizard-ux": (f"{ORG}/wizard-ux", "shell"),
                    "wizard-agent-service": (f"{ORG}/wizard-agent-service", "agent-service")}
FIX_REPOS = {**{c: r for c, (r, _) in IMAGE_COMPONENTS.items()}, "wizard-app-manager": WAM}
PUBLISH_WORKFLOW = "Publish public image"
WAM_IMAGE_WORKFLOW, WAM_TEST_WORKFLOW = "image", "test"     # wizard-app-manager .github/workflows/image.yml, test.yml
MIRROR_STATUS = "release-mirror/byte-identical"
MIN_CUT_INTERVAL = int(os.environ.get("WIZARD_TRAIN_MIN_CUT_INTERVAL", "1800"))   # at most one For testers cut per 30 min
CUT_WAIT_MARGIN = 30     # seconds past the window before a waiting cut goes ahead
CUT_WAIT_POLL = 120      # a waiting cut looks for a hotfix this often
STATE = Path(os.environ.get("WIZARD_TRAIN_HOME", Path.home() / ".wizard-os" / "release-train"))
RIG = Path(__file__).resolve().parent / "acceptance" / "upgrade-rig" / "kvm_upgrade.py"
PUBLIC_MIRROR = f"https://raw.githubusercontent.com/{WAM}/main/releases"
# Who the train's commits are by. The workflows set the token owner's identity (wizardosbuilder); a host run keeps Oscar's.
IDENTITY = ["-c", f"user.name={os.environ.get('WIZARD_TRAIN_GIT_NAME', 'Oscar')}",
            "-c", f"user.email={os.environ.get('WIZARD_TRAIN_GIT_EMAIL', '262056908+oscarhenrycollins@users.noreply.github.com')}"]
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


def run_deadline() -> float:
    return RUN_STARTED + RUN_BUDGET_S


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
    subjects = dict(line.split("\t", 1) for line in log.splitlines() if "\t" in line)   # sha -> subject
    out = []
    for n, sha in nums.items():
        try:
            p = known.get(n) or gh_json(["pr", "view", str(n), "-R", repo, "--json", "number,title,labels"])
        except Stop as e:
            # 12 Nov 2026: GitHub hides every PR of the suspended wizardosbuilder user ("Could not resolve to a
            # PullRequest"). The merge is still in git: take its title from the commit subject, with no labels.
            if "Could not resolve to a PullRequest" not in str(e):
                raise
            subj = subjects.get(sha, "")
            p = {"title": re.sub(r"\s*\(#\d+\)\s*$", "", subj), "labels": []}
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


def wam_image_tag(repo_dir: Path, sha: str) -> str | None:
    """The versioned tag wizard-app-manager's image.yml gives the image of `sha` (v<runtipi>-wizard.<count>-<short>)."""
    wf = sh(["git", "-C", str(repo_dir), "show", f"{sha}:.github/workflows/image.yml"], check=False)
    m = re.search(r'tag=(v[0-9A-Za-z.+-]*-wizard\.)\$\(git rev-list --count HEAD\)-\$\(git rev-parse --short HEAD\)', wf)
    if not m:
        return None
    count = sh(["git", "-C", str(repo_dir), "rev-list", "--count", sha]).strip()
    short = sh(["git", "-C", str(repo_dir), "rev-parse", "--short", sha]).strip()
    return f"{m.group(1)}{count}-{short}"


def wam_image_tags(repo_dir: Path, sha: str) -> list[str]:
    """Every tag image.yml may have given `sha`: `git rev-parse --short` picks its length from the size of the clone it
    runs in, so the runner's tag (e.g. 7 chars) and this clone's (e.g. 8) can differ (wizard-os#844). This clone's own
    abbreviation first, then 7 to 12 characters."""
    tag = wam_image_tag(repo_dir, sha)
    if not tag:
        return []
    prefix = tag.rsplit("-", 1)[0]
    full = sh(["git", "-C", str(repo_dir), "rev-parse", sha]).strip()
    out = [tag]
    for n in range(7, 13):
        t = f"{prefix}-{full[:n]}"
        if t not in out:
            out.append(t)
    return out


def multiarch_manifest(ref: str) -> dict | None:
    """The registry's manifest list for `ref` when it carries amd64 and arm64, else None (missing or single-arch)."""
    raw = sh(["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest}}"], check=False)
    try:
        man = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(man, dict) or not {"amd64", "arm64"} <= {
            str((m.get("platform") or {}).get("architecture")) for m in man.get("manifests", [])}:
        return None
    return man


def only_releases_changed(repo_dir: Path, base: str, head: str) -> bool:
    """True when base..head touches nothing outside releases/ (the App Manager's mirror merges)."""
    names = sh(["git", "-C", str(repo_dir), "diff", "--name-only", base, head]).split()
    return all(n.startswith("releases/") for n in names)


def published_wam(repo_dir: Path, latest: dict, limit: int = 40) -> dict | None:
    """App Manager: the newest main commit whose `test` push run is green and that changes more than releases/ since
    latest's pin, plus the newest published multi-arch image at or before it (image.yml only runs when image inputs
    change, so the image is usually from an earlier commit: pinned as source_commit with latest's image_inputs, and
    check_release proves no input changed in between). None: nothing newer to cut, or no publishable image yet."""
    l_c = latest["components"]["wizard-app-manager"]["commit"]
    tests = gh_json(["run", "list", "-R", WAM, "--workflow", WAM_TEST_WORKFLOW, "--branch", "main", "--event", "push",
                     "-L", str(limit), "--json", "headSha,conclusion,status"])
    head = next((r["headSha"] for r in tests if r.get("conclusion") == "success"
                 and is_ancestor(repo_dir, r["headSha"], "origin/main")), None)
    if not head or head == l_c or is_ancestor(repo_dir, head, l_c) or only_releases_changed(repo_dir, l_c, head):
        return None
    # 12 Nov 2026: a main push by the suspended wizardosbuilder user left no visible image run, so a rebuild can be
    # started by hand (workflow_dispatch on main): count those too. Both publish from main and are attested.
    images = [r for ev in ("push", "workflow_dispatch")
              for r in gh_json(["run", "list", "-R", WAM, "--workflow", WAM_IMAGE_WORKFLOW, "--branch", "main",
                                "--event", ev, "-L", str(limit), "--json", "databaseId,headSha,conclusion,url,createdAt"])]
    images.sort(key=lambda r: r.get("createdAt") or "", reverse=True)
    for r in images:
        if r.get("conclusion") != "success" or not is_ancestor(repo_dir, r["headSha"], head):
            continue
        jobs = gh_json(["run", "view", str(r["databaseId"]), "-R", WAM, "--json", "jobs"]).get("jobs", [])
        if not {"publish", "attest"} <= {str(j.get("name")) for j in jobs if j.get("conclusion") == "success"}:
            continue
        found = next(((f"ghcr.io/{WAM}:{t}", man) for t in wam_image_tags(repo_dir, r["headSha"])
                      if (man := multiarch_manifest(f"ghcr.io/{WAM}:{t}"))), None)
        if not found:
            continue
        ref, man = found
        return {"commit": head, "ref": ref, "digest": man["digest"], "ci_run": r["url"], "architectures": ["amd64", "arm64"],
                "source_commit": r["headSha"],
                "image_inputs": list(latest["images"]["wizard-app-manager"].get("image_inputs") or [])}
    return None


def last_cut_age(wos: Path, now: float | None = None) -> float | None:
    """Seconds since releases/latest last changed on wizard-os main (the last For testers cut)."""
    t = sh(["git", "-C", str(wos), "log", "-1", "--format=%ct", "origin/main", "--", "releases/latest"]).strip()
    return ((now if now is not None else time.time()) - int(t)) if t else None


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
        elif missing:   # the App Manager: its newest green main commit + newest published image
            pub = published_wam(d, L)
            info["published"] = pub
            ready = [x for x in missing if pub and is_ancestor(d, x["commit"], pub["commit"])]
            if ready:
                out["moves"][comp] = pub
            out["unpublished"] += [f"{repo}#{x['number']} {x['title']} (not on a green main with a published image yet)"
                                   for x in missing if x not in ready]
        out["waiting_fixes"] += [f"{repo}#{x['number']} {x['title']}" for x in on_latest + ready]
        out["components"][comp] = info
        if any_merge and comp not in out["moves"]:
            pub = info.get("published") or (published(repo, d) if comp in IMAGE_COMPONENTS else published_wam(d, L))
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


def lock_recipe() -> dict:
    """The agent recipe of the shared Hermes lock beside this script (tools/hermes_lock.py, releases/hermes-lock.json)."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import hermes_lock
    return hermes_lock.load()["agent_recipe"]


def candidate_json(L: dict, version: str, moves: dict, stable: str, notes: list[str]) -> dict:
    d = json.loads(json.dumps(L))
    d["version"] = version
    d["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    names = []
    for comp, pub in moves.items():
        repo, slot = IMAGE_COMPONENTS.get(comp) or (FIX_REPOS[comp], None)
        old = d["components"][comp]["commit"]
        mine = [n for n in notes if n.startswith(repo + "#")]
        d["components"][comp].update(commit=pub["commit"], branch="main",
                                     note=f"Official main at {pub['commit'][:8]} (release train)"
                                          + (": carries " + "; ".join(mine) if mine else ""))
        im = d["images"][comp]
        im.update(ref=pub["ref"], digest=pub["digest"], ci_run=pub["ci_run"], architectures=pub["architectures"])
        for k in ("source_commit", "image_inputs", "note"):
            im.pop(k, None)
        if pub.get("source_commit"):     # App Manager: image built from an earlier commit, inputs proven unchanged
            im.update(source_commit=pub["source_commit"], image_inputs=pub["image_inputs"])
        if slot and slot in d.get("default_apps", {}) and d["default_apps"][slot]:
            d["default_apps"][slot]["commit"] = pub["commit"]
        label = {"wizard-ux": "Wizard UX", "wizard-agent-service": "Agent Service"}.get(comp, "App Manager")
        names.append(f"{label} {old[:8]} -> {pub['commit'][:8]}")
    # The Hermes recipe follows the shared lock, which only James moves (DECISIONS #74): without this every cut copied
    # latest's recipe forward and a lock move never reached a release (wizard-app-store#92).
    recipe, agent = lock_recipe(), (d.get("default_apps") or {}).get("agent")
    if isinstance(agent, dict) and agent.get("app") == recipe["app"] and agent.get("commit") != recipe["commit"]:
        names.append(f"Hermes recipe {agent.get('index_version')} -> {recipe['index_version']}")
        agent.update(repo=recipe["repo"], commit=recipe["commit"], index_version=recipe["index_version"])
    d["name"] = f"WizardOS {version} — {L['version']} with " + ", ".join(names) + " (fixes)"
    d["about"] = (f"Latest {L['version']} with " + ", ".join(names) + ". Cut by the release train for merged "
                  "Recommended fixes: " + "; ".join(notes) + f". Stable stays {stable} until the installed upgrade test passes.")
    d["notes"] = f"Latest. Exactly {L['version']} except " + ", ".join(names) + "."
    return d


# Hermes recipe: its repo name is pinned again by releases/hermes-lock.json, which only James moves.
REPO_MOVE_SKIP = {("default_apps", "agent")}


def current_repo(repo: str) -> str | None:
    """GitHub's owner/name for a repo today (the API follows a transfer or rename). None when it can't tell."""
    r = subprocess.run(["gh", "api", f"repos/{repo}", "-q", ".full_name"], capture_output=True, text=True, timeout=60)
    name = r.stdout.strip()
    return name if r.returncode == 0 and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name) else None


def follow_repo_moves(d: dict, lookup=current_repo) -> list[str]:
    """Rewrite every components.*.repo / default_apps.*.repo that moved on GitHub to its new name, same commit
    (wizard-os#945: a box that already follows a move skips a pin naming the old repo). Returns "old -> new" lines."""
    moved, seen = [], {}
    for key in ("components", "default_apps"):
        for slot, pin in (d.get(key) or {}).items():
            if not isinstance(pin, dict) or not pin.get("repo") or (key, slot) in REPO_MOVE_SKIP:
                continue
            old = pin["repo"]
            if old not in seen:
                seen[old] = lookup(old)
            new = seen[old]
            if new and new.lower() != old.lower():
                pin["repo"] = new
                moved.append(f"{key}.{slot}: {old} -> {new}")
    return moved


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
                same = lambda x: {k: v for k, v in x.items() if k != "repo"}   # noqa: E731  a moved repo, same pin
                if same(a) != same(b):
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


PR_BODY_MAX = 60000   # GitHub rejects a PR body over 65536 characters (wizard-ux issue 1289: every cut STOPPED)


def fit_body(body: str, limit: int = PR_BODY_MAX) -> str:
    """Keep a PR body under GitHub's size limit: cut whole lines from the end and say how many were left out. A long
    ride-along list (hundreds of PRs since Stable) must never stop a cut; the full list stays in the release report."""
    if len(body) <= limit:
        return body
    lines, kept, size = body.split("\n"), [], 0
    for line in lines:
        if size + len(line) + 1 > limit - 200:
            break
        kept.append(line)
        size += len(line) + 1
    return "\n".join(kept) + f"\n- ... and {len(lines) - len(kept)} more lines (full list in the release train report)"


def open_and_merge(repo: str, wt: Path, branch: str, title: str, body: str, label: str, need_checks: bool,
                   timeout: float = 3600, verify=None) -> str:
    """Push, open, wait for every check on this exact head (need_checks), then merge that head. `verify(n, head)`
    (the App Manager mirror: verify_mirror) is the automated non-author check of DECISIONS #96 as amended: it must
    pass, and post its status, before the merge."""
    sh(["git", "-C", str(wt), "push", "-q", "-f", "origin", f"HEAD:refs/heads/{branch}"])
    url = existing_pr(repo, branch)
    if url:
        # An earlier run opened this PR and stopped before merging it (wizard-os#959: a 502 on `gh pr merge` left
        # #939 open, and every later `gh pr create` failed). The force-push above moved it to this run's head;
        # refresh its title and body and carry on with it.
        say(f"reusing the open PR for {branch}: {url}")
        sh(["gh", "pr", "edit", url, "-R", repo, "--title", title, "--body", fit_body(body)], check=False)
    else:
        url = sh(["gh", "pr", "create", "-R", repo, "--base", "main", "--head", branch, "--title", title,
                  "--body", fit_body(body)]).strip()
    n = url.rstrip("/").rsplit("/", 1)[1]
    sh(["gh", "api", "-X", "POST", f"repos/{repo}/issues/{n}/labels", "-f", f"labels[]={label}"], check=False)
    head = sh(["git", "-C", str(wt), "rev-parse", "HEAD"]).strip()
    deadline = min(time.time() + timeout, run_deadline())
    if verify:
        verify(n, head)          # raises Stop (and posts a failure status) unless byte-identical
    while need_checks:
        time.sleep(30)
        pr = gh_json(["pr", "view", n, "-R", repo, "--json", "statusCheckRollup,headRefOid"])
        if pr.get("headRefOid", head) != head:    # a reused PR: GitHub has not caught up with the force-push yet
            if time.time() > deadline:
                raise Stop(f"{url}: GitHub still shows head {pr['headRefOid'][:8]}, not {head[:8]}")
            continue
        checks = pr["statusCheckRollup"]
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
            if verify and not any(name == MIRROR_STATUS and c == "SUCCESS" for name, _, c in states):
                raise Stop(f"{url}: {MIRROR_STATUS} is not green on {head[:8]}")
            break
        if time.time() > deadline:
            raise Stop(f"{url}: checks still running after {timeout // 60:.0f} min")
    merge_pr(repo, n, head)
    return url


def existing_pr(repo: str, branch: str) -> str | None:
    """URL of the open PR from `branch` into main, if a run before this one left it open."""
    prs = gh_json(["pr", "list", "-R", repo, "--head", branch, "--base", "main", "--state", "open",
                   "--json", "url,number"]) or []
    return prs[0]["url"] if prs else None


TRANSIENT = re.compile(r"\b(5\d\d|bad gateway|service unavailable|gateway time-?out|timed? ?out|"
                       r"connection (reset|refused)|eof|tls handshake)\b", re.I)


def merge_pr(repo: str, n: str, head: str, tries: int = 4, pause: float = 20) -> None:
    """Merge exactly `head`. A GitHub 5xx or network blip is retried (wizard-os#959); when the failed call had in
    fact merged the PR, that counts as merged. Any other failure stops the train as before."""
    for attempt in range(1, tries + 1):
        try:
            sh(["gh", "pr", "merge", n, "-R", repo, "--merge", "--match-head-commit", head])
            return
        except (Stop, subprocess.TimeoutExpired) as e:
            err = e
        try:
            st = gh_json(["pr", "view", n, "-R", repo, "--json", "state,headRefOid"]) or {}
        except (Stop, subprocess.TimeoutExpired, ValueError):
            st = {}
        if st.get("state") == "MERGED" and st.get("headRefOid", head) == head:
            say(f"{repo}#{n}: merge call failed but the PR is merged; carrying on")
            return
        if attempt == tries or not TRANSIENT.search(str(err)):
            raise err if isinstance(err, Stop) else Stop(f"`gh pr merge {n} -R {repo}` timed out")
        say(f"{repo}#{n}: merge failed ({str(err)[-120:]}); retry {attempt}/{tries - 1} in {pause:.0f}s")
        time.sleep(pause)


def mirror_problems(changes: list[tuple[str, str]], mirror_file, canonical_file, base_file) -> tuple[list[str], list[str]]:
    """The byte-identity proof for a release mirror PR (pure, so tests drive it without GitHub).
    changes: (git status letter, path) of base..head in wizard-app-manager. mirror_file(path) -> bytes at the PR head,
    canonical_file(path) -> bytes on wizard-os main (None: absent), base_file(path) -> bytes at the PR base.
    Returns (problems, proofs). Every changed path must be under releases/, added or modified, and sha256-equal to
    wizard-os main's file at the same path; releases/README.md (wizard-app-manager's own provenance log) may only
    gain lines at its end."""
    problems, proofs = [], []
    if not changes:
        problems.append("the mirror PR changes nothing")
    for status, path in changes:
        if not path.startswith("releases/") or ".." in path.split("/"):
            problems.append(f"{path}: outside releases/")
            continue
        if status not in ("A", "M"):
            problems.append(f"{path}: {status} (a mirror only adds or updates files)")
            continue
        got = mirror_file(path)
        if path == "releases/README.md":
            old = base_file(path) or b""
            if got.startswith(old) and len(got) > len(old):
                proofs.append(f"{path}: append-only (+{len(got) - len(old)} bytes)")
            else:
                problems.append(f"{path}: not append-only")
            continue
        want = canonical_file(path)
        if want is None:
            problems.append(f"{path}: not in wizard-os main")
            continue
        a, b = hashlib.sha256(got).hexdigest(), hashlib.sha256(want).hexdigest()
        (proofs if a == b else problems).append(f"{path}: sha256 {a[:16]}" + ("" if a == b else f" != wizard-os {b[:16]}"))
    return problems, proofs


def _vkey(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in v.split("."))


def mirror_gap(canonical: Path, mirror: Path, upto: str) -> list[str]:
    """Canonical releases the App Manager mirror skipped (wizard-app-manager#656): every wizard-os releases/<v>.json
    newer than the mirror's `latest` and older than `upto` that the mirror lacks, oldest first. A mirror PR that
    stalled (a flaky check stops the train) leaves the next cut jumping past it; copying these with the new release
    keeps every rollback target installable instead of a 404."""
    try:
        floor = _vkey((mirror / "latest").read_text().strip())
    except (OSError, ValueError):
        return []
    names = []
    for f in canonical.glob("*.json"):
        v = f.name[:-5]
        if not v[:1].isdigit() or (mirror / f.name).exists():
            continue
        if floor < _vkey(v) < _vkey(upto):
            names.append(v)
    return sorted(names, key=_vkey)


def verify_mirror(wam_dir: Path, wos_dir: Path, base: str, n: str, head: str) -> list[str]:
    """Prove mirror PR #n (head) byte-identical to wizard-os main and post MIRROR_STATUS on its head."""
    sh(["git", "-C", str(wos_dir), "fetch", "-q", "origin", "+refs/heads/main:refs/remotes/origin/main"])
    gh_head = gh_json(["pr", "view", n, "-R", WAM, "--json", "headRefOid"]).get("headRefOid")
    raw = sh(["git", "-C", str(wam_dir), "diff", "--name-status", "--no-renames", base, head])
    changes = [tuple(line.split("\t", 1)) for line in raw.splitlines() if "\t" in line]
    blob = lambda d, ref, path: subprocess.run(["git", "-C", str(d), "show", f"{ref}:{path}"],   # noqa: E731
                                               capture_output=True).stdout if subprocess.run(
        ["git", "-C", str(d), "cat-file", "-e", f"{ref}:{path}"], capture_output=True).returncode == 0 else None
    problems, proofs = mirror_problems(changes, lambda f: blob(wam_dir, head, f) or b"",
                                       lambda f: blob(wos_dir, "origin/main", f), lambda f: blob(wam_dir, base, f))
    if gh_head != head:
        problems.insert(0, f"PR head is {str(gh_head)[:8]}, the train pushed {head[:8]}")
    wos_main = sh(["git", "-C", str(wos_dir), "rev-parse", "origin/main"]).strip()
    ok = not problems
    desc = (f"{len(proofs)} file(s) identical to wizard-os main@{wos_main[:8]}" if ok else problems[0])[:140]
    sh(["gh", "api", "-X", "POST", f"repos/{WAM}/statuses/{head}", "-f", f"state={'success' if ok else 'failure'}",
        "-f", f"context={MIRROR_STATUS}", "-f", f"description={desc}"], check=False)
    if not ok:
        raise Stop(f"mirror PR {WAM}#{n} is not byte-identical to wizard-os main: {'; '.join(problems)}")
    return proofs


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


# Published release records never change (boxes and release notes cite their sha256; wizard-os#416).
# releases/SHA256SUMS lists every one; tools/tests/test_published_releases.py fails when a listed file changes.
SUMS = "SHA256SUMS"


def record_published(releases: Path, name: str) -> None:
    """Append <name> (relative to releases/) to releases/SHA256SUMS once."""
    f = releases / SUMS
    lines = f.read_text().splitlines() if f.is_file() else []
    if not any(x.endswith(f"  {name}") for x in lines):
        with open(f, "a") as fh:
            fh.write(f"{sha(releases / name)}  {name}\n")


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


# Hotfix lane (wizard-os#434), always on (approved at show-and-tell, 25 Nov 2026). When a merged component PR
# closes or references an org issue labelled `hotfix`: its For testers cut skips the MIN_CUT_INTERVAL throttle, and
# the For everyone soak is HOTFIX_SOAK_HOURS instead of SOAK_HOURS (still no open release-blocker), or 0h when the
# hotfix issue is also labelled `breaking` or the PR closes a `release-blocker` issue. Any lookup error: normal timing.
HOTFIX_LABEL, BREAKING_LABEL = "hotfix", "breaking"
HOTFIX_SOAK_HOURS = 24
HOTFIX_LOOKBACK_DAYS = 30
_PR_FIELDS = ("number merged mergeCommit{oid} repository{nameWithOwner} "
              "closingIssuesReferences(first:20){nodes{labels(first:30){nodes{name}}}}")
HOTFIX_QUERY = ("query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){issue(number:$n){"
                "labels(first:30){nodes{name}} timelineItems(first:100,itemTypes:[CROSS_REFERENCED_EVENT,"
                "CONNECTED_EVENT,CLOSED_EVENT]){nodes{__typename "
                f"... on CrossReferencedEvent{{source{{... on PullRequest{{{_PR_FIELDS}}}}}}} "
                f"... on ConnectedEvent{{subject{{... on PullRequest{{{_PR_FIELDS}}}}}}} "
                f"... on ClosedEvent{{closer{{... on PullRequest{{{_PR_FIELDS}}}}}}}}}}}}}}}}}")


def _names(node) -> set[str]:
    return {str(x.get("name")) for x in ((node or {}).get("labels") or {}).get("nodes") or [] if isinstance(x, dict)}


def hotfix_prs_of(issue_url: str, issue: dict) -> list[dict]:
    """Merged component PRs that close or reference one hotfix issue (its GraphQL `issue` node)."""
    breaking = BREAKING_LABEL in _names(issue)
    out: dict[tuple, dict] = {}
    for ev in ((issue.get("timelineItems") or {}).get("nodes") or []):
        p = (ev or {}).get("source") or (ev or {}).get("subject") or (ev or {}).get("closer") or {}
        repo = (p.get("repository") or {}).get("nameWithOwner")
        oid = (p.get("mergeCommit") or {}).get("oid")
        if not p.get("merged") or not oid or repo not in FIX_REPOS.values():
            continue
        closes_blocker = any(BLOCKER_LABEL in _names(i) for i in ((p.get("closingIssuesReferences") or {}).get("nodes") or []))
        prev = out.get((repo, p["number"]), {})
        out[(repo, p["number"])] = {"repo": repo, "number": p["number"], "commit": oid, "issue": issue_url,
                                    "immediate": bool(prev.get("immediate") or breaking or closes_blocker)}
    return list(out.values())


def hotfix_prs(now: float | None = None) -> list[dict]:
    """Every merged component PR tied to an org `hotfix` issue updated in the last HOTFIX_LOOKBACK_DAYS. Raises Stop
    when GitHub can't be read (callers then keep the normal timing)."""
    since = datetime.fromtimestamp((now if now is not None else time.time()) - HOTFIX_LOOKBACK_DAYS * 86400,
                                   timezone.utc).strftime("%Y-%m-%d")
    issues = gh_json(["search", "issues", "--owner", ORG, "--label", HOTFIX_LABEL, "--updated", f">={since}",
                      "--json", "url,number,repository", "--limit", "50"])
    if not isinstance(issues, list):
        raise Stop(f"could not read {HOTFIX_LABEL} issues")
    out = []
    for i in issues:
        repo = (i.get("repository") or {}).get("nameWithOwner") or ""
        owner, _, name = repo.partition("/")
        got = gh_json(["api", "graphql", "-f", f"query={HOTFIX_QUERY}", "-F", f"o={owner}", "-F", f"r={name}",
                       "-F", f"n={i['number']}"])
        issue = (((got or {}).get("data") or {}).get("repository") or {}).get("issue")
        if not isinstance(issue, dict):
            raise Stop(f"could not read {i.get('url')}")
        out += hotfix_prs_of(i.get("url", ""), issue)
    return out


def contains(repo: str, ref: str, commit: str) -> bool:
    """Is <commit> in <ref>'s history (GitHub compare, no clone)?"""
    st = sh(["gh", "api", f"repos/{repo}/compare/{commit}...{ref}", "--jq", ".status"]).strip()
    return st in ("ahead", "identical")


def hotfixes_between(old: dict, new: dict | None) -> list[dict]:
    """Hotfix PRs in <new> release's component pins (None: each component's main) and not in <old>'s pins."""
    out = []
    for h in hotfix_prs():
        comp = next(c for c, r in FIX_REPOS.items() if r == h["repo"])
        old_pin = old["components"][comp]["commit"]
        new_pin = new["components"][comp]["commit"] if new else "main"
        if contains(h["repo"], new_pin, h["commit"]) and not contains(h["repo"], old_pin, h["commit"]):
            out.append(h)
    return out


def hotfix_soak(wos: Path, stable: str, latest: str) -> tuple[float, list[dict]]:
    """(hours latest must soak, hotfixes it carries since stable). Any lookup error: (SOAK_HOURS, [])."""
    try:
        rel = lambda v: json.loads(show(wos, "origin/main", f"releases/{v}.json"))   # noqa: E731
        hf = hotfixes_between(rel(stable), rel(latest))
    except (Stop, OSError, KeyError, StopIteration, TypeError, ValueError) as e:   # OSError: no gh on PATH
        say(f"hotfix lane: lookup failed ({e}); normal {SOAK_HOURS}h soak")
        return SOAK_HOURS, []
    if not hf:
        return SOAK_HOURS, []
    return (0 if any(h["immediate"] for h in hf) else HOTFIX_SOAK_HOURS), hf


def pending_hotfixes(wos: Path) -> list[dict]:
    """Hotfix PRs merged on a component main but not yet in releases/latest. Lookup error: []."""
    try:
        latest = show(wos, "origin/main", "releases/latest").strip()
        return hotfixes_between(json.loads(show(wos, "origin/main", f"releases/{latest}.json")), None)
    except (Stop, OSError, KeyError, StopIteration, TypeError, ValueError) as e:   # OSError: no gh on PATH
        say(f"hotfix lane: lookup failed ({e}); normal throttle")
        return []


def _hf_names(hf: list[dict]) -> str:
    return ", ".join(f"{h['repo'].split('/')[1]}#{h['number']}" for h in hf)


# Soak by cut age (wizard-os#416), ON by default (Miguel, 15 Nov 2026: Stable had not moved since 9 Nov). While cuts
# keep landing about every 30 minutes, the current latest is always minutes old, so "latest soaked 72h" never fires.
# So For everyone takes the NEWEST release above stable that was first named on releases/latest SOAK_HOURS or more
# ago, the same latest_since promote_stable.py records and checks ("72h" means "cut onto For testers 72h ago"). The
# no-release-blocker gate, the installed upgrade test and promote_stable's own soak gate still apply to it.
# WIZARD_TRAIN_SOAK_BY_CUT=0 restores the old rule (only the current latest, once it is 72h old).
SOAK_BY_CUT = os.environ.get("WIZARD_TRAIN_SOAK_BY_CUT", "1") != "0"


def latest_history(wos: Path, ref: str = "origin/main") -> dict[str, float]:
    """version -> unix time releases/latest first named it on <ref>. Reads git objects only, so it works in the
    train's --no-checkout clone (where there is no releases/ folder on disk). Unreadable history raises Stop."""
    out = sh(["git", "-C", str(wos), "log", "--reverse", "--format=%H %ct", ref, "--", "releases/latest"])
    first: dict[str, float] = {}
    for line in out.splitlines():
        commit, ct = line.split(" ", 1)
        v = sh(["git", "-C", str(wos), "show", f"{commit}:releases/latest"], check=False).strip()
        if v and v not in first:
            first[v] = float(ct)
    return first


def soaked_for(version: str, wos: Path, now: float | None = None) -> float | None:
    """Hours since releases/latest first named <version> on wizard-os main (git history, as promote_stable reads it).
    None: no commit of releases/latest names it."""
    t = latest_history(wos).get(version)
    return None if t is None else ((now if now is not None else time.time()) - t) / 3600


def due_by_cut(stable: str, latest: str, wos: Path, now: float | None = None,
               need: float = SOAK_HOURS) -> tuple[str, float] | None:
    """(newest version above stable cut onto latest >= <need> hours ago (default SOAK_HOURS), its hours), or None.
    Only real releases count."""
    now = now if now is not None else time.time()
    best = None
    for v, t in latest_history(wos).items():
        hours = (now - t) / 3600
        if _key(stable) < _key(v) <= _key(latest) and hours >= need and (best is None or _key(v) > _key(best[0])):
            if subprocess.run(["git", "-C", str(wos), "cat-file", "-e", f"origin/main:releases/{v}.json"],
                              capture_output=True).returncode == 0:
                best = (v, hours)
    return best


def oldest_above(stable: str, latest: str, wos: Path, now: float | None = None) -> tuple[str, float] | None:
    """(the oldest release above stable that releases/latest named, its hours since that cut), or None. Only for
    the WAITING message: it says when the next promotion is due."""
    now = now if now is not None else time.time()
    cand = [(v, (now - t) / 3600) for v, t in latest_history(wos).items() if _key(stable) < _key(v) <= _key(latest)]
    return max(cand, key=lambda x: x[1]) if cand else None


def soak_gate(stable: str, latest: str, wos: Path) -> tuple[bool, str, float | None, list[dict], str]:
    """Is a release due for For everyone? (due, outcome when not due, hours on latest, hotfixes that shortened the
    soak, the version to promote). <wos> is the wizard-os clone (git objects; no checkout needed).
    Cheap: wizard-os only (plus GitHub API reads for the hotfix lane)."""
    if _key(latest) <= _key(stable):
        return False, f"nothing to promote: For everyone ({stable}) already has latest ({latest})", None, [], latest
    need, hf = hotfix_soak(wos, stable, latest)
    hours = soaked_for(latest, wos)
    version = latest
    if need > 0 and hours is None:
        # Never "an unknown time": a gate that cannot measure the soak must say so and stop (wizard-os#416).
        raise Stop(f"can't tell how long {latest} has been For testers: no commit of releases/latest on "
                   f"origin/main names it (in {wos}). Stable stays {stable}.")
    if need > 0 and hours < need:
        hot = hotfix_due_by_cut(stable, latest, wos, need) if hf and SOAK_BY_CUT else None
        if hot is not None:
            # hotfix lane under soak by cut age (wizard-os#434): latest moves every ~30 min, so it is never 24h old;
            # the newest release cut 24h+ ago that already carries the hotfix takes the shortened soak instead.
            version, hours, hf = hot
        else:
            older = due_by_cut(stable, latest, wos) if SOAK_BY_CUT else None
            if older is None:
                oldest = oldest_above(stable, latest, wos) if SOAK_BY_CUT else None
                return False, (f"WAITING: {latest} has been For testers for {hours:.0f}h; it moves to For everyone "
                               f"after {need:.0f}h{f' (hotfix lane: {_hf_names(hf)})' if hf else ''}"
                               + (f"; the oldest release above Stable, {oldest[0]}, was cut {oldest[1]:.0f}h ago and "
                                  f"is promoted at {SOAK_HOURS}h" if oldest and oldest[0] != latest else "")
                               + f". Stable stays {stable}."), hours, hf, latest
            # soak by cut age: the older release takes the normal soaked gate (no hotfix waiver applies to it)
            version, hours, hf = older[0], older[1], []
    blockers = release_blockers()
    if blockers:
        return False, (f"HELD: {len(blockers)} open {BLOCKER_LABEL} issue(s): " + "; ".join(blockers)
                       + f". Stable stays {stable}."), hours, hf, version
    return True, "", hours, hf, version


def hotfix_due_by_cut(stable: str, latest: str, wos: Path, need: float) -> tuple[str, float, list[dict]] | None:
    """Hotfix lane with soak by cut age: (the newest release above stable cut onto latest >= <need> hours ago that
    carries a hotfix PR not in stable, its hours, those hotfixes), or None. A release older than that cannot carry a
    hotfix the newer one lacks (pins only move forward), so only that one release is looked up."""
    cand = due_by_cut(stable, latest, wos, need=need)
    if cand is None or cand[0] == latest:
        return None
    n2, hf2 = hotfix_soak(wos, stable, cand[0])
    return (cand[0], cand[1], hf2) if hf2 and cand[1] >= n2 else None


def wait_out_cut_window(work: Path, age: float, step) -> list:
    """Sleep until MIN_CUT_INTERVAL has passed since the last cut, then return (wizard-os#669: a deferred cut used to
    wait for a sweep gated on a repo variable the builder app can't write, so it waited for the daily cut). Checks for
    a waiting hotfix every CUT_WAIT_POLL seconds and returns it at once, so the hotfix lane still skips the wait."""
    left = MIN_CUT_INTERVAL - age + CUT_WAIT_MARGIN
    step(f"the last For testers cut was {age / 60:.0f} min ago (at most one per {MIN_CUT_INTERVAL // 60} min); "
         f"waiting {max(left, 0) / 60:.0f} min, then cutting whatever is newer")
    while left > 0:
        nap = min(CUT_WAIT_POLL, left)
        time.sleep(nap)
        left -= nap
        if left > 0:
            hf = pending_hotfixes(clone(WOS, work))
            if hf:
                return hf
    return []


def run(work: Path, dry: bool, force: bool, rig_args: list[str], feature_fast_track: bool = False,
        mode: str = "train", wait_deferred: bool = False) -> dict:
    """mode "train": today's fix train. "cut": For testers (cut + mirror any newer published main, then stop).
    "soaked": For everyone (promote latest after SOAK_HOURS with no release-blocker; normal gate, no fast-track)."""
    rep: dict = {"started": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "dry_run": dry, "force": force,
                 "steps": []}
    step = lambda s: (rep["steps"].append(s), say(s))   # noqa: E731
    if mode == "cut" and not dry:
        age = last_cut_age(clone(WOS, work))
        hf = pending_hotfixes(clone(WOS, work)) if age is not None and age < MIN_CUT_INTERVAL else []
        if hf:
            rep["hotfixes"] = hf
            step(f"hotfix lane: {_hf_names(hf)} waiting; cutting now (skips the {MIN_CUT_INTERVAL // 60}-min limit)")
        elif age is not None and age < MIN_CUT_INTERVAL and wait_deferred:
            hf = wait_out_cut_window(work, age, step)
            if hf:
                rep["hotfixes"] = hf
                step(f"hotfix lane: {_hf_names(hf)} waiting; cutting now")
        elif age is not None and age < MIN_CUT_INTERVAL:
            rep["mode"], rep["deferred"] = mode, True
            rep["outcome"] = (f"DEFERRED: the last For testers cut was {age / 60:.0f} min ago (at most one per "
                              f"{MIN_CUT_INTERVAL // 60} min); the next sweep cuts whatever is newer then.")
            return rep
    p = plan(work, any_merge=(mode == "cut")) if mode != "soaked" else plan(work)
    rep["mode"] = mode
    rep["plan"] = {k: v for k, v in p.items() if k != "components"}
    stable, latest = p["stable"], p["latest"]
    if mode == "soaked":
        # For everyone takes latest as it is: never a new cut here.
        due, why, hours, hotfixes, version = soak_gate(stable, latest, clone(WOS, work))
        if not due:
            rep["outcome"] = why
            return rep
        p["candidate"], p["cut"], p["moves"] = version, False, {}
        if hotfixes:
            rep["hotfixes"] = hotfixes
        step(f"{version} soaked {'0h (immediate hotfix)' if hours is None else f'{hours:.0f}h'} on For testers; no open "
             f"{BLOCKER_LABEL}{f'; hotfix lane: {_hf_names(hotfixes)}' if hotfixes else ''}"
             f"{f' (soak by cut age, wizard-os#416: latest {latest} is newer)' if version != latest else ''}")
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
        moved = follow_repo_moves(C)
        if moved:
            C["notes"] += " Repos renamed to where GitHub moved them (same commits): " + "; ".join(moved) + "."
            step(f"repo moves followed: {'; '.join(moved)}")
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
        record_published(wt / "releases", f"{V}.json")
        sh(["git", *IDENTITY, "-C", str(wt), "add", f"releases/{V}.json", "releases/latest", f"releases/{SUMS}"])
        sh(["git", *IDENTITY, "-C", str(wt), "commit", "-qm", f"Cut {V} onto latest (release train): {C['name']}"])
        step(f"cut {V}: check_release ok, channels ok ({'local only' if dry else 'pushing'})")
    else:
        C = L if V == latest else json.loads((wt / "releases" / f"{V}.json").read_text())   # soak by cut age
    cls, items, prs = ride_alongs(work, S, C)
    rep["classification"], rep["ride_alongs"] = cls, items
    rep["prs"] = [{**x, "tier": tier(x)} for x in prs]
    step(f"classification {cls}: {sum(tier(x) == 'fix' for x in prs)} fix, "
         f"{sum(tier(x) == 'feature' for x in prs)} feature, {sum(tier(x) == 'maintenance' for x in prs)} maintenance PRs; "
         f"{len(items)} other changes")
    rel_json = wt / "releases" / f"{V}.json"
    if p["cut"]:
        # Mirror the cut into the App Manager (the copy installers read), byte-identical. Releases an earlier,
        # stalled mirror PR never landed come along (oldest first), so the rollback target always exists.
        gap = mirror_gap(wt / "releases", mwt / "releases", V)
        for g in gap:
            shutil.copyfile(wt / "releases" / f"{g}.json", mwt / "releases" / f"{g}.json")
            with open(mwt / "releases" / "README.md", "a") as f:
                f.write(f"\n## {g} provenance\n\nCanonical: wizard-os releases/{g}.json (release train, gap fill). "
                        f"SHA256: `{sha(wt / 'releases' / f'{g}.json')}`.\n"
                        f"{json.loads((wt / 'releases' / f'{g}.json').read_text()).get('about', '')}\n"
                        "Channel: on latest only.\n")
        if gap:
            step(f"mirror gap fill: {', '.join(gap)} (never landed in {WAM})")
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
                     + (f"Also mirrors {', '.join(gap)}, which earlier mirror PRs never landed. " if gap else "")
                     + f"`releases/{V}.json` sha256 `{sha(rel_json)}`. Stable unchanged ({stable}). Merged on the automated "
                     f"`{MIRROR_STATUS}` check (DECISIONS #96 as amended).\n\nRollback: "
                     f"`releases/latest` back to {latest}.")
            mbase = sh(["git", "-C", str(wam), "rev-parse", "origin/main"]).strip()
            rep["mirror_pr"] = open_and_merge(WAM, mwt, f"release/{V}-mirror-train",
                                              f"Maintenance: mirror WizardOS {V} onto latest (release train)", mbody,
                                              "tier: maintenance", need_checks=True,
                                              verify=lambda n, h: verify_mirror(wam, wos, mbase, n, h))
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
              "0 failed checks, doctors 0 FAIL, the owner's Hermes config/.env/SOUL unchanged.")
    notes = ("Ride-alongs onto Stable: " + "; ".join(f"{x['repo'].split('/')[1]}#{x['number']} [{tier(x)}] {x['title'][:80]}"
                                                     for x in prs) + ("; " + "; ".join(items) if items else "")
             + ". Not checked: real Tailscale/HTTPS/Serve, real chats and sign-ins, phones, a fresh install.")
    why = ([f"{V} carries hotfix {_hf_names(rep['hotfixes'])}: hotfix lane (wizard-os#434), shortened soak with no "
            f"open {BLOCKER_LABEL} issue, recorded as a fast-track."] if mode == "soaked" and rep.get("hotfixes") else
           [f"{V} soaked {SOAK_HOURS}h+ on For testers (latest) with no open {BLOCKER_LABEL} issue (For everyone "
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
    if mode == "soaked" and rep.get("hotfixes"):   # hotfix lane: the soak is waived on the record (DECISIONS #82)
        sh([sys.executable, "tools/promote_stable.py", "promote", V, "--from", stable, "--evidence", evidence, "--fast-track",
            "--classification", cls, "--reason", f"Hotfix lane (wizard-os#434): {_hf_names(rep['hotfixes'])} "
            f"(issues {', '.join(sorted({h['issue'] for h in rep['hotfixes']}))}); no open {BLOCKER_LABEL}. " + reason,
            "--notes", notes], cwd=wt)
    elif mode == "soaked":     # the normal gate: promote_stable itself refuses a release that has not soaked
        # No notes here: promote_stable takes notes only on a fast-track and exits 2 otherwise (wizard-os#856, the
        # first soaked promotion to pass the upgrade test stopped on it). The ride-alongs are in the evidence doc.
        sh([sys.executable, "tools/promote_stable.py", "promote", V, "--from", stable, "--evidence", evidence], cwd=wt)
    else:
        sh([sys.executable, "tools/promote_stable.py", "promote", V, "--from", stable, "--evidence", evidence, "--fast-track",
        "--classification", cls, "--reason", reason, "--notes", notes], cwd=wt)
    sh([sys.executable, "tools/promote_stable.py", "check"], cwd=wt)
    rec = json.loads((wt / "releases" / "promotions" / f"{V}.json").read_text())
    record_published(wt / "releases", f"promotions/{V}.json")
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
    how = (f"hotfix lane for {_hf_names(rep['hotfixes'])} with no open {BLOCKER_LABEL}" if mode == "soaked" and rep.get("hotfixes")
           else f"after {SOAK_HOURS}h on For testers with no open {BLOCKER_LABEL}" if mode == "soaked" else f"fast-track **{cls}**")
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
    pbase = sh(["git", "-C", str(wam), "rev-parse", "origin/main"]).strip()
    rep["promote_mirror_pr"] = open_and_merge(WAM, mwt, f"promote/{V}-mirror-train",
                                              f"Maintenance: mirror WizardOS stable {V} (release train, {cls})",
                                              body.replace("promote **", "mirror stable **"), "tier: maintenance",
                                              need_checks=True, verify=lambda n, h: verify_mirror(wam, wos, pbase, n, h))
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
                       ("promote-soaked", "For everyone: promote the newest release cut onto latest 72h+ ago, no open release-blocker")):
        x = sub.add_parser(name, help=what)
        x.add_argument("--dry-run", action="store_true", help="local only; stop before any push, PR or merge")
        x.add_argument("--keep-guest", action="store_true")
        if name == "cut":
            x.add_argument("--wait-deferred", action="store_true",
                           help="inside the 30-min window, wait for it to end and then cut (instead of DEFERRED)")
        if name == "promote-soaked":
            x.add_argument("--check", action="store_true",
                           help="only say whether a promotion is due (prints due=true|false; no component clones, no rig)")
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
    if a.cmd == "promote-soaked" and a.check:
        try:
            wos = clone(WOS, a.work)
            rel = lambda name: show(wos, "origin/main", f"releases/{name}")   # noqa: E731
            due, why, _hours, _hf, version = soak_gate(rel("stable").strip(), rel("latest").strip(), wos)
            if due:
                why = f"due: {version} has soaked with no release-blocker; run promote-soaked"
        except Stop as e:
            due, why = False, f"STOPPED: {e}"
        print(f"due={'true' if due else 'false'}")
        print(why or "due: latest has soaked with no release-blocker; run promote-soaked")
        return 0
    if a.cmd == "plan":
        p = plan(a.work)
        print(json.dumps({k: v for k, v in p.items() if k != "components"}, indent=2, default=str))
        return 0
    try:
        mode = {"cut": "cut", "promote-soaked": "soaked"}.get(a.cmd, "train")
        rep = run(a.work, a.dry_run, getattr(a, "force", False), ["--keep"] if a.keep_guest else [],
                  a.feature_fast_track if a.cmd == "run" else False, mode, getattr(a, "wait_deferred", False))
        code = 0 if not str(rep.get("outcome", "")).startswith("STOPPED") else 1
    except Stop as e:
        rep, code = {"outcome": f"STOPPED: {e}", "dry_run": a.dry_run}, 1
    path = write_report(rep)
    print((STATE / "last.md").read_text())
    print(f"report: {path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
