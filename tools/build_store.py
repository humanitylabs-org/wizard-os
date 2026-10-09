"""NOTE: superseded by wizard-app-manager (wam refresh), which adds install, apps.json and serving the store to Runtipi.
Kept as a dependency-free one-shot compiler.
"""
#!/usr/bin/env python3
"""Compile Wizard app repos into a stock Runtipi app store plus a catalog.

Usage:
  build_store.py --out <dir> <repo-dir> [<repo-dir> ...]      # local checkouts
  build_store.py --out <dir> --github-topic wizard-app [--limit 50]

Each repo must pass check_wizard_md.py. Passing apps are written as
  <out>/apps/<id>/config.json, docker-compose.yml, metadata/description.md[, logo.jpg]
which is the layout stock Runtipi (>= 4.8) reads from an app-store git repo,
and every candidate (pass or fail) is recorded in <out>/catalog.json.
Runtipi itself is not modified; nobody hand-merges app repos into one store.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_wizard_md import check, front_matter  # noqa: E402


def body(text: str) -> str:
    return re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S).strip()


def compile_app(repo: Path, out: Path, origin: str) -> dict:
    results = check(repo)
    ok = bool(results) and all(r[1] for r in results)
    row = {"origin": origin, "compatible": ok, "failed": [n for n, good, _ in results if not good]}
    if not ok:
        return row
    text = (repo / "wizard.md").read_text()
    d = front_matter(text)
    app_id = d["id"]
    dest = out / "apps" / app_id
    if dest.exists():
        row.update(compatible=False, failed=[f"duplicate id {app_id}"])
        return row
    (dest / "metadata").mkdir(parents=True)
    cfg = json.loads((repo / d["runtime"]["config"]).read_text())
    cfg["id"] = app_id  # Runtipi folder name and config id must agree
    cfg.setdefault("name", d["name"])
    cfg["version"] = str(d["version"])
    cfg["wizard_type"] = d["type"]
    if d.get("system"):
        cfg["wizard_system"] = True
    shutil.copyfile(repo / d["runtime"]["compose"], dest / "docker-compose.yml")
    (dest / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    (dest / "metadata" / "description.md").write_text(body(text) + "\n")
    for logo in ("logo.jpg", "metadata/logo.jpg", "runtipi/logo.jpg"):
        if (repo / logo).is_file():
            shutil.copyfile(repo / logo, dest / "metadata" / "logo.jpg")
            break
    row.update(
        id=app_id,
        name=d["name"],
        type=d["type"],
        version=str(d["version"]),
        summary=d["summary"],
        source=d["source"],
        system=bool(d.get("system")),
        provides=d.get("provides") or [],
        uses=d.get("uses") or [],
        mcp=d.get("mcp"),
        skill=d.get("skill"),
        view=d.get("view"),
        recommends=d.get("recommends"),
    )
    return row


def topic_repos(topic: str, limit: int) -> list[str]:
    r = subprocess.run(
        ["gh", "search", "repos", "--topic", topic, "--json", "fullName", "--limit", str(limit)],
        capture_output=True, text=True, check=True,
    )
    return [x["fullName"] for x in json.loads(r.stdout)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--github-topic")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("repos", nargs="*")
    a = ap.parse_args()
    out = Path(a.out)
    if (out / "apps").exists():
        shutil.rmtree(out / "apps")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in a.repos:
        rows.append(compile_app(Path(r), out, r))
    if a.github_topic:
        with tempfile.TemporaryDirectory() as tmp:
            for name in topic_repos(a.github_topic, a.limit):
                dst = Path(tmp) / name.replace("/", "__")
                c = subprocess.run(["git", "clone", "--depth", "1", "-q", f"https://github.com/{name}", str(dst)],
                                   capture_output=True, text=True)
                if c.returncode:
                    rows.append({"origin": name, "compatible": False, "failed": ["clone failed"]})
                    continue
                rev = subprocess.run(["git", "-C", str(dst), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
                row = compile_app(dst, out, name)
                row["commit"] = rev
                rows.append(row)
    (out / "catalog.json").write_text(json.dumps({"apps": rows}, indent=2) + "\n")
    good = [r for r in rows if r["compatible"]]
    for r in rows:
        print(("OK    " if r["compatible"] else "SKIP  ") + str(r.get("id") or r["origin"]) +
              ("" if r["compatible"] else f"  ({', '.join(r['failed'])})"))
    print(f"{len(good)}/{len(rows)} apps compiled into {out / 'apps'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
