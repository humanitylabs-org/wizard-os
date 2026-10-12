#!/usr/bin/env python3
"""Check a Wizard OS release file: every pinned commit exists in its repo, every image digest resolves.

    python3 tools/check_release.py releases/0.2.0.json          # commits (gh api) + image digests (registry)
    python3 tools/check_release.py releases/0.2.0.json --offline # shape only (CI without network)
    python3 tools/check_release.py --stable                      # the release releases/stable points at

Online it also checks that each commit is on the branch the release names (a commit only reachable from a PR is
not a release), and that each image was built from its component's pinned commit (OCI label
org.opencontainers.image.revision). The installer (wizard-app-manager get.sh) installs exactly these pins and reads
back what runs; releases/stable names the release a plain `curl -fsSL aiwizards.com/os.sh | bash` installs.

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


def on_branch(repo: str, sha: str, branch: str) -> tuple[bool, str]:
    """The commit is the branch head or one of its ancestors (GitHub compare: identical / behind)."""
    r = subprocess.run(["gh", "api", f"repos/{repo}/compare/{branch}...{sha}", "-q", ".status"],
                       capture_output=True, text=True)
    st = r.stdout.strip()
    if r.returncode == 0 and st in ("identical", "behind"):
        return True, ""
    return False, (f"not on {branch} (compare: {st})" if r.returncode == 0 else
                   ((r.stderr or "").strip().splitlines() or ["compare failed"])[-1][:160])


def image_revision(ref: str, digest: str) -> tuple[str | None, str]:
    """The git commit the image was built from: the OCI label org.opencontainers.image.revision, else the commit in
    the BuildKit SLSA provenance attestation (docker/build-push-action records it by default). None = unknown."""
    m = re.match(r"^ghcr\.io/([^:@]+)", ref)
    if not m:
        return None, "only ghcr.io is checked"
    name = m.group(1)
    accept = ", ".join(["application/vnd.oci.image.index.v1+json", "application/vnd.oci.image.manifest.v1+json",
                        "application/vnd.docker.distribution.manifest.list.v2+json",
                        "application/vnd.docker.distribution.manifest.v2+json"])
    try:
        tok = json.load(urllib.request.urlopen(f"https://ghcr.io/token?scope=repository:{name}:pull", timeout=20))["token"]
        hdr = {"Authorization": f"Bearer {tok}", "Accept": accept}
        get = lambda path: json.load(urllib.request.urlopen(urllib.request.Request(  # noqa: E731
            f"https://ghcr.io/v2/{name}/{path}", headers=hdr), timeout=30))
        top = get(f"manifests/{digest}")
        subs = top.get("manifests") or []
        plats = [d for d in subs if (d.get("platform") or {}).get("os") not in (None, "unknown")]
        mans = [get(f"manifests/{d['digest']}") for d in plats] if subs else [top]
        labels = {((get(f"blobs/{m['config']['digest']}").get("config") or {}).get("Labels") or {})
                  .get("org.opencontainers.image.revision") for m in mans}
        if len(labels) > 1:
            return None, "platforms carry different revision labels: " + ", ".join(sorted(str(x) for x in labels))
        rev = labels.pop() if labels else None
        if rev:
            return rev, ""
        found = set()
        for att in subs:
            if (att.get("annotations") or {}).get("vnd.docker.reference.type") != "attestation-manifest":
                continue
            for layer in get(f"manifests/{att['digest']}").get("layers", []):
                if "provenance" not in (layer.get("annotations") or {}).get("in-toto.io/predicate-type", ""):
                    continue
                found |= set(re.findall(r'"(?:vcs:revision|revision)":\s*"([0-9a-f]{40})"',
                                        json.dumps(get(f"blobs/{layer['digest']}"))))
        if len(found) == 1:
            return found.pop(), ""
        return None, ("provenance names several commits: " + ", ".join(sorted(found))) if found else "no provenance"
    except (OSError, ValueError, KeyError) as e:
        return None, str(e)[:160]


def changed_inputs(repo: str, base: str, head: str, inputs: list[str]) -> tuple[list[str] | None, str]:
    """Files under `inputs` (paths or dir/** globs) changed between base and head; base must be an ancestor."""
    import fnmatch
    if not inputs:
        return None, "image_inputs not given"
    r = subprocess.run(["gh", "api", f"repos/{repo}/compare/{base}...{head}",
                        "--jq", "{status: .status, files: [.files[].filename]}"], capture_output=True, text=True)
    if r.returncode != 0:
        return None, ((r.stderr or "").strip().splitlines() or ["compare failed"])[-1][:160]
    d = json.loads(r.stdout)
    if d["status"] not in ("ahead", "identical"):
        return None, f"{base[:12]} is not an ancestor of {head[:12]} ({d['status']})"
    if len(d["files"]) >= 300:   # GitHub's compare lists at most 300 files: can't prove nothing changed
        return None, f"{len(d['files'])} files changed, at GitHub's compare cap; check with a local git diff"
    return [f for f in d["files"] if any(fnmatch.fnmatch(f, g) or f == g for g in inputs)], ""


def workflow_paths(repo: str, ref: str, workflow: str) -> tuple[list[str] | None, str]:
    """The `paths:` filter of the image workflow at `ref`: the files whose change rebuilds the image."""
    import base64
    r = subprocess.run(["gh", "api", f"repos/{repo}/contents/{workflow}?ref={ref}", "-q", ".content"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"can't read {workflow} at {ref[:12]}"
    text = base64.b64decode(r.stdout).decode("utf-8", "replace")
    found: list[str] = []
    for m in re.finditer(r"^\s*paths:\s*\[([^\]]*)\]", text, re.M):
        found += [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
    if not found:
        return None, f"no paths: filter in {workflow} (every push rebuilds; pin the exact build commit instead)"
    return sorted(set(found)), ""


def index_drift(defaults: dict) -> list[str]:
    """Default apps whose version in the live index differs from the release (the installer takes the index's)."""
    out = []
    for slot, d in defaults.items():
        if not d:
            continue
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(
                f"https://apps.aiwizards.com/v1/search?q={d['app']}", headers={"User-Agent": "check_release"}), timeout=20))
        except (OSError, ValueError) as e:
            out.append(f"{slot}: index unreachable ({str(e)[:80]})")
            continue
        hit = next((a for a in r.get("apps", []) if a.get("id") == d["app"]), None)
        if not hit:
            out.append(f"{slot}: {d['app']} not in the index")
        elif str(hit.get("version")) != str(d.get("index_version")) or (
                d.get("commit") and (hit.get("install") or {}).get("commit") != d["commit"]):
            out.append(f"{slot}: index serves {d['app']} {hit.get('version')} "
                       f"@{((hit.get('install') or {}).get('commit') or '')[:12]}, release pins {d.get('index_version')}"
                       + (f" @{d['commit'][:12]}" if d.get("commit") else ""))
    return out


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
    ap.add_argument("file", nargs="?")
    ap.add_argument("--offline", action="store_true", help="check the shape only")
    ap.add_argument("--stable", action="store_true", help="check the release releases/stable points at")
    a = ap.parse_args(argv)
    if a.stable:
        stable = Path(__file__).resolve().parents[1] / "releases" / "stable"
        try:
            ver = stable.read_text().strip()
        except OSError as e:
            print(f"no stable release: {e}", file=sys.stderr)
            return 2
        if not VERSION.match(ver):
            print(f"FAIL  releases/stable: {ver!r} is not a version")
            return 1
        a.file = str(stable.parent / f"{ver}.json")
    if not a.file:
        ap.error("give a release file or --stable")
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
            if not c.get("branch"):
                errs.append(f"{name}: no branch named, so it can't be shown to be released (only on a PR?)")
            elif ok:
                ok, why = on_branch(c["repo"], c["commit"], c["branch"])
                (ok_lines if ok else errs).append(f"{name}: {c['commit'][:12]} on {c['branch']}" + ("" if ok else f" ({why})"))
        for name, im in (rel.get("images") or {}).items():
            ok, why = digest_exists(im["ref"], im["digest"])
            (ok_lines if ok else errs).append(f"image {name}: {im['digest'][:19]}" + ("" if ok else f" missing ({why})"))
            src = rel["components"].get(im.get("built_from") or "")
            if not src:
                errs.append(f"image {name}: built_from {im.get('built_from')!r} doesn't name a component, so its "
                            "source can't be proven")
            if ok and src and im.get("source_commit"):
                # The image was built from an earlier commit of the component; fine only if no image input changed.
                rev, why = image_revision(im["ref"], im["digest"])
                if rev != im["source_commit"]:
                    errs.append(f"image {name}: built from {(rev or '?')[:12]}, release says source_commit "
                                f"{im['source_commit'][:12]}" + (f" ({why})" if why else ""))
                else:
                    wf = im.get("image_workflow", ".github/workflows/image.yml")
                    need, why_wf = workflow_paths(src["repo"], rev, wf)
                    short = sorted(set(need or []) - set(im.get("image_inputs") or []))
                    if need is None or short:
                        errs.append(f"image {name}: image_inputs must cover {wf}'s paths at {rev[:12]}"
                                    + (f"; missing {', '.join(short)}" if short else f" ({why_wf})"))
                        continue
                    changed, why = changed_inputs(src["repo"], rev, src["commit"], im.get("image_inputs") or [])
                    if changed is None:
                        errs.append(f"image {name}: can't compare {rev[:12]}..{src['commit'][:12]} ({why})")
                    elif changed:
                        errs.append(f"image {name}: built from {rev[:12]}, but image inputs changed before "
                                    f"{src['commit'][:12]}: {', '.join(changed[:5])}")
                    else:
                        ok_lines.append(f"image {name}: built from {rev[:12]}; no image input changed up to "
                                        f"{im['built_from']}@{src['commit'][:12]}")
            elif ok and src:
                rev, why = image_revision(im["ref"], im["digest"])
                if rev is None:
                    errs.append(f"image {name}: can't prove it was built from {im['built_from']}@{src['commit'][:12]}"
                                + (f" ({why})" if why else ""))
                elif rev == src["commit"]:
                    ok_lines.append(f"image {name}: built from {im['built_from']}@{rev[:12]}")
                else:
                    errs.append(f"image {name}: built from {im['built_from']}@{rev[:12]}, release pins "
                                f"{src['commit'][:12]}")
    warns = index_drift(rel.get("default_apps") or {}) if not errs and not a.offline else []
    for line in ok_lines:
        print(f"PASS  {line}")
    for w in warns:   # the installer takes the index's current version; get.sh reads it back as DRIFT
        print(f"DRIFT {w}")
    for e in errs:
        print(f"FAIL  {e}")
    print(f"release {rel.get('version')}: {'ok' if not errs else f'{len(errs)} problem(s)'}")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
