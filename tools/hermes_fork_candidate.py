#!/usr/bin/env python3
"""Write a Hermes fork candidate snapshot (wizard-os#723): releases/candidates/<base>-hermes-fork.<n>.json.

    python3 tools/hermes_fork_candidate.py --fork-commit <40-hex> --digest sha256:<64-hex> \\
        --ci-run https://github.com/<fork>/actions/runs/<id> --test-record <forum run link or docs/acceptance/...> \\
        [--base releases/<version>.json] [--base-tag v0.22.7] [--fork-repo defleur-agents/hermes-agent] \\
        [--agent-repo owner/name --agent-commit <40-hex> --agent-index-version <v>]

The candidate copies the base snapshot (default: what releases/latest names), swaps its `hermes` block for the
fork pin, keeps the base pin as `rollback`, and is marked `"channel": "candidate"`. It moves no pointer:
releases/latest and releases/stable stay as they are, and the shared Hermes lock is not touched. Without
--agent-commit the hermes-agent recipe stays the base one, which `check_release.py` (online) reports as not
building FROM the fork image until a recipe that does is pinned. Offline shape check runs before writing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import check_release

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"
FORK_REPO = "defleur-agents/hermes-agent"


def upstream_commit(tag: str) -> str:
    sha, why = check_release.upstream_tag_commit(tag)
    if not sha:
        raise SystemExit(f"can't resolve upstream {tag}: {why}")
    return sha


def build(base: dict, a: argparse.Namespace) -> dict:
    rel = json.loads(json.dumps(base))
    prev = base["hermes"]
    owner = a.fork_repo.split("/")[0].lower()
    tag = f"sha-{a.fork_commit}"
    rel["channel"] = check_release.CANDIDATE
    rel["version"] = f"{base['version']}-hermes-fork.{a.n}"
    rel["name"] = f"WizardOS {rel['version']}: {base['version']} with the Hermes fork {a.fork_commit[:10]} (candidate)"
    rel["about"] = (f"Candidate only (wizard-os#723): {base['version']} with Hermes from the WizardOS fork "
                    f"{a.fork_repo}@{a.fork_commit[:10]} (upstream {a.base_tag} plus Wizard's local edits). "
                    "Not latest, not stable: Telos first, then Miguel and the testers, soak, then James's yes.")
    rel["hermes"] = {
        "tag": a.base_tag,
        "commit": a.base_commit or upstream_commit(a.base_tag),
        "fork": {"repo": a.fork_repo, "branch": a.fork_branch, "tag": tag, "commit": a.fork_commit},
        "image": {"ref": f"ghcr.io/{owner}/hermes-agent:{tag}", "digest": a.digest, "commit": a.fork_commit,
                  "architectures": ["amd64", "arm64"], "ci_run": a.ci_run},
        "test_record": a.test_record,
        "rollback": {k: prev[k] for k in ("tag", "commit", "image", "fork") if prev.get(k) is not None},
    }
    if a.agent_commit:
        agent = dict((rel.get("default_apps") or {}).get("agent") or {"app": "hermes-agent"})
        agent.update(repo=a.agent_repo or agent.get("repo"), commit=a.agent_commit)
        if a.agent_index_version:
            agent["index_version"] = a.agent_index_version
        rel.setdefault("default_apps", {})["agent"] = agent
    return rel


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", help="base snapshot (default: the release releases/latest names)")
    ap.add_argument("--base-tag", default="v0.22.7", help="upstream tag the fork's main is built on")
    ap.add_argument("--base-commit", help="its commit (default: resolved upstream with gh)")
    ap.add_argument("--fork-repo", default=FORK_REPO)
    ap.add_argument("--fork-branch", default="main")
    ap.add_argument("--fork-commit", required=True)
    ap.add_argument("--digest", required=True, help="multi-arch digest from the fork image run's summary")
    ap.add_argument("--ci-run", required=True)
    ap.add_argument("--test-record", required=True)
    ap.add_argument("--agent-repo")
    ap.add_argument("--agent-commit")
    ap.add_argument("--agent-index-version")
    ap.add_argument("--n", type=int, default=1, help="candidate number on this base")
    ap.add_argument("--out-dir", default=str(RELEASES / "candidates"))
    ap.add_argument("--print", action="store_true", help="print instead of writing")
    a = ap.parse_args(argv)
    base_path = Path(a.base) if a.base else RELEASES / f"{(RELEASES / 'latest').read_text().strip()}.json"
    rel = build(json.loads(base_path.read_text()), a)
    out = Path(a.out_dir) / f"{rel['version']}.json"
    errs = check_release.shape(rel) + check_release.candidate_place(rel, out)
    if errs:
        for e in errs:
            print(f"FAIL  {e}", file=sys.stderr)
        return 1
    text = json.dumps(rel, indent=2, ensure_ascii=False) + "\n"
    if a.print:
        sys.stdout.write(text)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
