#!/usr/bin/env python3
"""Check a WizardOS release file: every pinned commit exists in its repo, every image digest resolves.

    python3 tools/check_release.py releases/0.2.0.json          # commits (gh api) + image digests (registry)
    python3 tools/check_release.py releases/0.2.0.json --offline # shape only (CI without network)
    python3 tools/check_release.py --stable                      # the release releases/stable points at

Online it also checks that each commit is on the branch the release names (a commit only reachable from a PR is
not a release), and that each image was built from its component's pinned commit (OCI label
org.opencontainers.image.revision). The installer (wizard-app-manager get.sh) installs exactly these pins and reads
back what runs; every pinned repo must answer under the name the release uses (a moved repo fails until the release
pins its new name). releases/stable names the release a plain `curl -fsSL aiwizards.com/os.sh | bash` installs.

A release file names exactly what one WizardOS version is: the commit of each component repo, the image digests
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
import hermes_lock

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
VERSION = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
HERMES_TAG = re.compile(r"^v\d+\.\d+\.\d+$")          # a final upstream tag, never an rc build
HERMES_IMAGE = re.compile(r"^docker\.io/nousresearch/hermes-agent:(v\d+\.\d+\.\d+)$")
HERMES_UPSTREAM = "NousResearch/hermes-agent"
# The WizardOS Hermes fork (DECISIONS #116): upstream base tag + Wizard's local edits, built into its own image.
HERMES_FORK_IMAGE = re.compile(r"^ghcr\.io/([a-z0-9._-]+)/hermes-agent:([A-Za-z0-9._-]{1,128})$")
HERMES_FORK_TAG = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
CANDIDATE = "candidate"   # `"channel": "candidate"`: a snapshot to test, never what latest/stable installs
HERMES_PIN_FROM = (0, 3, 23)   # DECISIONS #74: snapshots from 0.3.23 on name their Hermes; older files are history
SERVICE_ROUTES_FROM = (0, 3, 33)   # snapshots from 0.3.33 on: the pinned Agent Service serves every stable spec route
SPEC = Path(__file__).resolve().parents[1] / "spec" / "AGENT_SERVICE_API.md"


def _vtuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.match(r"^(\d+)\.(\d+)\.(\d+)", v).groups())


def _fork_commit(pin: dict) -> str | None:
    fork = pin.get("fork")
    return fork.get("commit") if isinstance(fork, dict) else None


def hermes_shape(rel: dict) -> list[str]:
    """The `hermes` block (docs/HERMES_STABLE.md): the one upstream Hermes release this snapshot runs."""
    h = rel.get("hermes")
    version = str(rel.get("version", ""))
    if h is None:
        if VERSION.fullmatch(version) and _vtuple(version) >= HERMES_PIN_FROM:
            return ["hermes: required from 0.3.23 on (tag, commit, image, test_record, rollback)"]
        return []
    if not isinstance(h, dict):
        return ["hermes: expected an object"]
    errs: list[str] = []
    if not HERMES_TAG.fullmatch(str(h.get("tag", ""))):
        errs.append(f"hermes: tag {h.get('tag')!r} is not a final upstream tag like v0.21.6")
    if not SHA.fullmatch(str(h.get("commit", ""))):
        errs.append(f"hermes: commit {h.get('commit')!r} is not a 40-char sha")
    im = h.get("image")
    fork = h.get("fork")
    if fork is not None:
        errs += hermes_fork_shape(h)
    elif im is not None:
        m = HERMES_IMAGE.fullmatch(str((im or {}).get("ref", ""))) if isinstance(im, dict) else None
        if not m:
            errs.append("hermes.image: ref must be docker.io/nousresearch/hermes-agent:<tag> (null = source-only)")
        elif m.group(1) != h.get("tag"):
            errs.append(f"hermes.image: ref tag {m.group(1)} differs from hermes.tag {h.get('tag')}")
        if not isinstance(im, dict) or not DIGEST.fullmatch(str(im.get("digest", ""))):
            errs.append("hermes.image: digest is not sha256:<64 hex>")
        # Historical carried-over pins stay readable; a newly tested pin must name the image's source too.
        image_commit = im.get("commit") if isinstance(im, dict) else None
        if image_commit is not None or not str(h.get("test_record", "")).startswith("none: "):
            if not SHA.fullmatch(str(image_commit or "")):
                errs.append("hermes.image: commit must record the 40-char image source commit for a tested pin")
            elif image_commit != h.get("commit"):
                errs.append("hermes.image: commit differs from the upstream tag commit; do not promote this image")
    agent = (rel.get("default_apps") or {}).get("agent")
    if im is None and isinstance(agent, dict) and agent.get("app") == "hermes-agent":
        errs.append("hermes.image: fresh installs run the hermes-agent container, so the pin needs an image")
    rec = h.get("test_record")
    if fork is not None and isinstance(rec, str) and re.fullmatch(r"https://\S+", rec):
        pass   # a fork pin may link its test run (e.g. the forum run of the fork's tests)
    elif fork is not None and isinstance(rec, str) and rec.startswith("none: "):
        errs.append("hermes.test_record: a fork pin needs a real test record (docs/acceptance/... or an https link)")
    elif not isinstance(rec, str) or not (rec.startswith("none: ") and len(rec) > 12 or
                                       re.fullmatch(r"docs/acceptance/hermes-v[\w.-]+\.md", rec)):
        errs.append("hermes.test_record: docs/acceptance/hermes-<tag>.md, or 'none: <why>' for a carried-over pin")
    elif not rec.startswith("none: ") and not (Path(__file__).resolve().parents[1] / rec).is_file():
        errs.append(f"hermes.test_record: {rec} does not exist")
    rb = h.get("rollback", "missing")
    if rb == "missing":
        errs.append("hermes.rollback: required (the release to go back to, or null for the first pin)")
    elif rb is not None and (not isinstance(rb, dict) or not HERMES_TAG.fullmatch(str(rb.get("tag", ""))) or
                             not SHA.fullmatch(str(rb.get("commit", "")))):
        errs.append("hermes.rollback: needs a final tag and a 40-char commit")
    elif isinstance(rb, dict) and rb.get("tag") == h.get("tag") and _fork_commit(rb) == _fork_commit(h):
        errs.append("hermes.rollback: must be a different release from hermes.tag")
    if rel.get("channel", CANDIDATE) != CANDIDATE:
        errs.append(f"channel: {rel.get('channel')!r}; only \"candidate\" is a channel (latest/stable are pointers)")
    # The shared frozen lock guards what installs get. A candidate is only tested, never installed by
    # releases/latest or releases/stable (main() checks that), so it may pin a Hermes the lock does not.
    if VERSION.fullmatch(version) and _vtuple(version) >= (0, 3, 40) and rel.get("channel") != CANDIDATE:
        try:
            hermes_lock.check_release(rel)
        except (ValueError, OSError) as exc:
            errs.append(str(exc))
    return errs


def hermes_fork_shape(h: dict) -> list[str]:
    """A fork pin: `tag`/`commit` name the upstream base release, `fork` the fork commit the image was built from."""
    errs: list[str] = []
    fork, im = h.get("fork"), h.get("image")
    if not isinstance(fork, dict):
        return ["hermes.fork: expected an object (repo, branch, tag, commit)"]
    if not REPO.fullmatch(str(fork.get("repo", ""))):
        errs.append(f"hermes.fork: repo {fork.get('repo')!r} is not owner/name")
    if not isinstance(fork.get("branch"), str) or not fork["branch"].strip():
        errs.append("hermes.fork: branch is required (the fork branch the commit is on, normally main)")
    if not HERMES_FORK_TAG.fullmatch(str(fork.get("tag", ""))):
        errs.append(f"hermes.fork: tag {fork.get('tag')!r} is not an image tag")
    if not SHA.fullmatch(str(fork.get("commit", ""))):
        errs.append(f"hermes.fork: commit {fork.get('commit')!r} is not a 40-char sha")
    if not isinstance(im, dict):
        return errs + ["hermes.image: a fork pin needs the fork's image (ref, digest, commit, architectures)"]
    m = HERMES_FORK_IMAGE.fullmatch(str(im.get("ref", "")))
    if not m:
        errs.append("hermes.image: a fork pin's ref must be ghcr.io/<fork owner>/hermes-agent:<fork tag>")
    else:
        if m.group(1) != str(fork.get("repo", "")).split("/")[0].lower():
            errs.append(f"hermes.image: ref owner {m.group(1)} is not the fork's owner")
        if m.group(2) != fork.get("tag"):
            errs.append(f"hermes.image: ref tag {m.group(2)} differs from hermes.fork.tag {fork.get('tag')}")
    if not DIGEST.fullmatch(str(im.get("digest", ""))):
        errs.append("hermes.image: digest is not sha256:<64 hex>")
    if im.get("commit") != fork.get("commit"):
        errs.append("hermes.image: commit must equal hermes.fork.commit (the image's source-revision label)")
    if not isinstance(im.get("architectures"), list) or set(im["architectures"]) != {"amd64", "arm64"}:
        errs.append("hermes.image: architectures must name amd64 and arm64")
    if "ci_run" in im and not re.fullmatch(r"https://github\.com/\S+/actions/runs/\d+", str(im["ci_run"])):
        errs.append("hermes.image: ci_run must link the GitHub Actions run that built it")
    return errs


def shape(rel: dict) -> list[str]:
    """Both historical bundled-shell and complete split releases, matching get.sh's keys."""
    errs: list[str] = []
    if not isinstance(rel, dict):
        return ["release: expected an object"]
    if not VERSION.fullmatch(str(rel.get("version", ""))):
        errs.append(f"version {rel.get('version')!r} is not semver")
    comps = rel.get("components")
    if not isinstance(comps, dict) or not comps:
        return errs + ["components: missing"]
    for name, c in comps.items():
        if not isinstance(c, dict):
            errs.append(f"{name}: expected a component object")
            continue
        if not REPO.fullmatch(str(c.get("repo", ""))):
            errs.append(f"{name}: repo {c.get('repo')!r} is not owner/name")
        if not SHA.fullmatch(str(c.get("commit", ""))):
            errs.append(f"{name}: commit {c.get('commit')!r} is not a 40-char sha")
        if not isinstance(c.get("branch"), str) or not c["branch"].strip():
            errs.append(f"{name}: branch is required")
    images = rel.get("images")
    if not isinstance(images, dict) or not images:
        return errs + ["images: missing"]
    split = "wizard-ux" in images or "wizard-agent-service" in images
    required = ("wizard-app-manager", "wizard-ux", "wizard-agent-service") if split else (
        "wizard-app-manager", "wizard-shell")
    for name in required:
        if name not in images:
            errs.append(f"image {name}: required for a {'split' if split else 'bundled'} release")
    if split and "wizard-shell" in images:
        errs.append("images: cannot mix wizard-shell with split UX/Service images")
    for name, im in images.items():
        if not isinstance(im, dict):
            errs.append(f"image {name}: expected an object")
            continue
        if not DIGEST.fullmatch(str(im.get("digest", ""))):
            errs.append(f"image {name}: digest {im.get('digest')!r} is not sha256:<64 hex>")
        ref = str(im.get("ref", ""))
        if not re.fullmatch(r"ghcr\.io/[a-z0-9._-]+/[a-z0-9._/-]+(?::[A-Za-z0-9._-]+|@sha256:[0-9a-f]{64})?", ref):
            errs.append(f"image {name}: ref {ref!r} is not a supported GHCR image name")
        if "@" in ref and ref.rsplit("@", 1)[1] != im.get("digest"):
            errs.append(f"image {name}: ref digest differs from digest")
        if not isinstance(im.get("built_from"), str) or im["built_from"] not in comps:
            errs.append(f"image {name}: built_from {im.get('built_from')!r} is not a component")
        elif name in ("wizard-app-manager", "wizard-ux", "wizard-agent-service") and im["built_from"] != name:
            errs.append(f"image {name}: built_from must name {name}")
        if "source_commit" in im and not SHA.fullmatch(str(im["source_commit"])):
            errs.append(f"image {name}: source_commit is not a 40-char sha")
        if "image_inputs" in im and (not isinstance(im["image_inputs"], list) or not im["image_inputs"] or
                not all(isinstance(p, str) and p and not p.startswith("!") for p in im["image_inputs"])):
            errs.append(f"image {name}: image_inputs must be nonempty positive path patterns")
        if "image_workflow" in im and not re.fullmatch(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", str(im["image_workflow"])):
            errs.append(f"image {name}: image_workflow must name a workflow file")
        if (not isinstance(im.get("architectures"), list) or
                not all(isinstance(a, str) for a in im["architectures"]) or
                set(im["architectures"]) != {"amd64", "arm64"}):
            errs.append(f"image {name}: architectures must name amd64 and arm64")
    defaults = rel.get("default_apps")
    if not isinstance(defaults, dict):
        return errs + ["default_apps: expected an object"]
    for slot, d in defaults.items():
        if d is not None and (not isinstance(d, dict) or not d.get("app") or not d.get("index_version")):
            errs.append(f"default_apps.{slot}: needs app and index_version (or null)")
    for slot, app in (("shell", "wizard-ux" if split else "wizard-shell"),
                      ("agent-service", "wizard-agent-service" if split else "wizard-shell")):
        d = defaults.get(slot)
        if not isinstance(d, dict) or d.get("app") != app:
            errs.append(f"default_apps.{slot}: must name {app}")
    return errs + hermes_shape(rel)


def on_branch(repo: str, sha: str, branch: str) -> tuple[bool, str]:
    """The commit is the branch head or one of its ancestors (GitHub compare: identical / behind)."""
    r = subprocess.run(["gh", "api", f"repos/{repo}/compare/{branch}...{sha}", "-q", ".status"],
                       capture_output=True, text=True)
    st = r.stdout.strip()
    if r.returncode == 0 and st in ("identical", "behind"):
        return True, ""
    return False, (f"not on {branch} (compare: {st})" if r.returncode == 0 else
                   ((r.stderr or "").strip().splitlines() or ["compare failed"])[-1][:160])


def image_revision(ref: str, digest: str, architectures: list[str] | None = None) -> tuple[str | None, str]:
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
        if architectures and not {("linux", a) for a in architectures} <= {
                (d["platform"]["os"], d["platform"].get("architecture")) for d in plats}:
            return None, "manifest does not contain all declared Linux architectures"
        if subs and not plats:
            return None, "manifest index has no runnable platforms"
        mans = [get(f"manifests/{d['digest']}") for d in plats] if subs else [top]
        labels = {((get(f"blobs/{m['config']['digest']}").get("config") or {}).get("Labels") or {})
                  .get("org.opencontainers.image.revision") for m in mans}
        if len(labels) > 1:
            return None, "platforms carry different revision labels: " + ", ".join(sorted(str(x) for x in labels))
        rev = labels.pop() if labels else None
        if rev:
            return rev, ""
        proven = {}
        for att in subs:
            if (att.get("annotations") or {}).get("vnd.docker.reference.type") != "attestation-manifest":
                continue
            for layer in get(f"manifests/{att['digest']}").get("layers", []):
                if "provenance" not in (layer.get("annotations") or {}).get("in-toto.io/predicate-type", ""):
                    continue
                target = (att.get("annotations") or {}).get("vnd.docker.reference.digest")
                proven.setdefault(target, set()).update(re.findall(
                    r'"(?:vcs:revision|revision)":\s*"([0-9a-f]{40})"',
                    json.dumps(get(f"blobs/{layer['digest']}"))))
        if not plats or any(len(proven.get(p["digest"], set())) != 1 for p in plats):
            return None, "no unambiguous provenance for every platform"
        found = set().union(*(proven[p["digest"]] for p in plats))
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
                        "--jq", "{status: .status, files: [.files[] | {filename, previous_filename}]}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, ((r.stderr or "").strip().splitlines() or ["compare failed"])[-1][:160]
    d = json.loads(r.stdout)
    if d["status"] not in ("ahead", "identical"):
        return None, f"{base[:12]} is not an ancestor of {head[:12]} ({d['status']})"
    if len(d["files"]) >= 300:   # GitHub's compare lists at most 300 files: can't prove nothing changed
        return None, f"{len(d['files'])} files changed, at GitHub's compare cap; check with a local git diff"
    # A rename OUT of an input directory is still a change to an image input.
    paths = {p for f in d["files"] for p in (f["filename"], f.get("previous_filename")) if p}
    return sorted(f for f in paths if any(fnmatch.fnmatch(f, g) for g in inputs)), ""


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


def missing_service_routes(spec_text: str, sources: dict[str, str]) -> list[str]:
    """Stable /wizard/ routes in the spec's ```routes block that no Agent Service server file mentions.

    A release pairs one shell image with one Agent Service image. 0.3.32 shipped a shell that calls GET /wizard/v1/setup
    with an Agent Service from before that route existed, so first-run Setup never opened on a fresh box. A route counts
    as served when its literal prefix (up to the first {param}) appears in server/*.mjs, plain or regex-escaped."""
    m = re.search(r"```routes\n(.*?)```", spec_text, re.S)
    if not m:
        return ["spec: no ```routes block"]
    text = "\n".join(sources.values())
    out = []
    for raw in m.group(1).splitlines():
        parts = raw.split()
        if len(parts) < 4 or raw.lstrip().startswith("#") or parts[2] != "stable" or not parts[1].startswith("/wizard/"):
            continue
        pre = parts[1].split("{", 1)[0]
        forms = {pre, pre.rstrip("/")}
        forms |= {f.replace("/", "\\/") for f in forms}
        if not any(f in text for f in forms if f):
            out.append(f"{parts[0]} {parts[1]}")
    return out


def service_sources(repo: str, sha: str) -> tuple[dict[str, str] | None, str]:
    """server/*.mjs of the pinned Agent Service commit (GitHub tarball through gh)."""
    import io
    import tarfile
    r = subprocess.run(["gh", "api", f"repos/{repo}/tarball/{sha}"], capture_output=True)
    if r.returncode != 0:
        return None, ((r.stderr or b"").decode("utf-8", "replace").strip().splitlines() or ["tarball failed"])[-1][:160]
    out = {}
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as t:
        for mem in t.getmembers():
            rel = mem.name.split("/", 1)[-1]
            if mem.isfile() and rel.startswith("server/") and rel.endswith(".mjs"):
                out[rel] = t.extractfile(mem).read().decode("utf-8", "replace")
    return (out, "") if out else (None, "no server/*.mjs in the tarball")


def service_routes_online(rel: dict, spec_text: str) -> tuple[list[str], list[str]]:
    version = str(rel.get("version", ""))
    c = (rel.get("components") or {}).get("wizard-agent-service")
    if not c or not VERSION.fullmatch(version) or _vtuple(version) < SERVICE_ROUTES_FROM:
        return [], []
    src, why = service_sources(c["repo"], c["commit"])
    if src is None:
        return [], [f"wizard-agent-service: can't read server sources at {c['commit'][:12]} ({why})"]
    miss = missing_service_routes(spec_text, src)
    if miss:
        return [], [f"wizard-agent-service@{c['commit'][:12]} does not serve stable spec route(s) the shell may call: "
                    + ", ".join(miss)]
    return [f"wizard-agent-service@{c['commit'][:12]}: serves every stable /wizard/ route in spec/AGENT_SERVICE_API.md"], []


def current_name(repo: str) -> tuple[str | None, str]:
    """GitHub's name for a repo today. A transferred or renamed repo answers under its new owner/name (the API follows
    the redirect), so a pin still naming the old one shows up as a difference (wizard-os#945)."""
    r = subprocess.run(["gh", "api", f"repos/{repo}", "-q", ".full_name"], capture_output=True, text=True)
    name = r.stdout.strip()
    if r.returncode == 0 and REPO.fullmatch(name):
        return name, ""
    return None, ((r.stderr or "").strip().splitlines() or ["not found"])[-1][:160]


def pinned_repos(rel: dict) -> list[tuple[str, str]]:
    """(where, repo) for every components.*.repo and default_apps.*.repo the release names."""
    out = [(f"components.{n}", c["repo"]) for n, c in (rel.get("components") or {}).items()
           if isinstance(c, dict) and c.get("repo")]
    out += [(f"default_apps.{s}", d["repo"]) for s, d in (rel.get("default_apps") or {}).items()
            if isinstance(d, dict) and d.get("repo")]
    return out


# The Hermes recipe's repo is pinned again by releases/hermes-lock.json, which only James moves (DECISIONS #74): a move
# there is reported, not failed, so it can't stop every For testers cut.
LOCKED_SLOTS = ("default_apps.agent",)


def moved_repos(rel: dict, lookup=current_name) -> tuple[list[str], list[str], list[str]]:
    """A pin must name the repo as GitHub names it now: a moved repo pinned under its old name is skipped by boxes
    that already follow the move (wizard-os#945). Returns (ok lines, errors, warnings)."""
    ok, errs, warns, seen = [], [], [], {}
    for where, repo in pinned_repos(rel):
        if repo not in seen:
            seen[repo] = lookup(repo)
        now, why = seen[repo]
        if now is None:
            errs.append(f"{where}.repo: can't look up {repo} on GitHub ({why})")
        elif now.lower() != repo.lower():
            if where in LOCKED_SLOTS:
                warns.append(f"{where}.repo: {repo} moved to {now}; releases/hermes-lock.json pins the old name, "
                             "so the lock has to move first")
            else:
                errs.append(f"{where}.repo: {repo} moved to {now}: pin the new name (same commit)")
    if not errs:
        ok.append(f"repos: all {len(seen)} pinned repos answer under the name the release uses"
                  + (" (except the lock-pinned Hermes recipe)" if warns else ""))
    return ok, errs, warns


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


def upstream_tag_commit(tag: str) -> tuple[str | None, str]:
    """Resolve an upstream tag to its commit, following annotated tags."""
    r = subprocess.run(["gh", "api", f"repos/{HERMES_UPSTREAM}/git/ref/tags/{tag}", "-q", ".object.type+\" \"+.object.sha"],
                       capture_output=True, text=True)
    if r.returncode:
        return None, ((r.stderr or "").strip().splitlines() or ["not found"])[-1][:160]
    kind, sha = r.stdout.split()
    if kind == "tag":
        r = subprocess.run(["gh", "api", f"repos/{HERMES_UPSTREAM}/git/tags/{sha}", "-q", ".object.sha"],
                           capture_output=True, text=True)
        sha = r.stdout.strip() if r.returncode == 0 else ""
    return (sha or None), ""


def dockerhub_digest_exists(digest: str) -> tuple[bool, str]:
    try:
        tok = json.load(urllib.request.urlopen(
            "https://auth.docker.io/token?service=registry.docker.io&scope=repository:nousresearch/hermes-agent:pull",
            timeout=20))["token"]
        req = urllib.request.Request(f"https://registry-1.docker.io/v2/nousresearch/hermes-agent/manifests/{digest}",
                                     method="HEAD", headers={"Authorization": f"Bearer {tok}", "Accept": ", ".join([
                                         "application/vnd.oci.image.index.v1+json",
                                         "application/vnd.docker.distribution.manifest.list.v2+json"])})
        urllib.request.urlopen(req, timeout=20)
        return True, ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except (OSError, ValueError, KeyError) as e:
        return False, str(e)[:160]


STAMP = "opt/hermes/install-stamp.json"
STAMP_LAYER_MAX = 8 * 1024 * 1024     # the stamp sits in a tiny top layer; never download the big ones


def install_stamp_revision(manifest: dict, blob) -> tuple[str | None, str]:
    """The commit in the image's /opt/hermes/install-stamp.json, read from its top-most layer that has it.

    `blob(digest)` returns the digest-verified layer bytes. Only small layers are read, top-down; the first layer
    that writes or deletes the stamp decides (as in the running image). The stamp must name a clean CI build.
    """
    import io
    import tarfile
    for layer in reversed(manifest.get("layers") or []):
        name = Path(STAMP).name
        if int(layer.get("size") or 0) > STAMP_LAYER_MAX:
            return None, "the install stamp is not in a small top layer"
        try:
            with tarfile.open(fileobj=io.BytesIO(blob(layer["digest"])), mode="r:*") as tar:
                for m in tar.getmembers():
                    path = m.name.lstrip("./")
                    if path in (str(Path(STAMP).parent / (".wh." + name)), str(Path(STAMP).parent / ".wh..wh..opq")):
                        return None, "a layer removes the install stamp"
                    if path == STAMP:
                        if not m.isfile() or m.size > 64 * 1024:
                            return None, "the install stamp is not a small file"
                        stamp = json.loads(tar.extractfile(m).read())
                        rev = stamp.get("commit") if isinstance(stamp, dict) else None
                        if not SHA.fullmatch(str(rev or "")) or stamp.get("dirty") is not False:
                            return None, "the install stamp names no clean 40-char commit"
                        return rev, ""
        except (tarfile.TarError, OSError, ValueError, KeyError) as e:
            return None, f"its layers can't be read ({str(e)[:80]})"
    return None, "it has no install stamp"


def dockerhub_image_revision(digest: str) -> tuple[str | None, str]:
    """Prove the digest's revision on BOTH install architectures, without downloading image layers.

    No inferred revision from a tag, build date, or another architecture. Missing metadata blocks promotion.
    """
    import hashlib
    accept = ", ".join(["application/vnd.oci.image.index.v1+json",
                        "application/vnd.docker.distribution.manifest.list.v2+json",
                        "application/vnd.oci.image.manifest.v1+json",
                        "application/vnd.docker.distribution.manifest.v2+json"])
    try:
        tok = json.load(urllib.request.urlopen(
            "https://auth.docker.io/token?service=registry.docker.io&scope=repository:nousresearch/hermes-agent:pull",
            timeout=20))["token"]

        def get_raw(path: str, expected: str, limit: int = 16 * 1024 * 1024) -> bytes:
            req = urllib.request.Request(f"https://registry-1.docker.io/v2/nousresearch/hermes-agent/{path}",
                                         headers={"Authorization": f"Bearer {tok}", "Accept": accept})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read(limit + 1)
            if len(raw) > limit:
                raise ValueError("registry blob is larger than expected")
            if "sha256:" + hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("registry content differs from its digest")
            return raw

        def get(path: str, expected: str) -> dict:
            return json.loads(get_raw(path, expected))

        top = get(f"manifests/{digest}", digest)
        revisions = set()
        for arch in ("amd64", "arm64"):
            matches = [m for m in top.get("manifests", []) if m.get("platform", {}).get("os") == "linux"
                       and m.get("platform", {}).get("architecture") == arch]
            if len(matches) != 1:
                return None, f"expected one linux/{arch} manifest"
            md = matches[0]["digest"]
            man = get(f"manifests/{md}", md)
            cd = man["config"]["digest"]
            cfg = get(f"blobs/{cd}", cd)
            rev = ((cfg.get("config") or {}).get("Labels") or {}).get("org.opencontainers.image.revision")
            if not SHA.fullmatch(str(rev or "")):
                # Official images from v0.23 on carry no labels; their CI build writes the source commit into
                # /opt/hermes/install-stamp.json instead (wizard-app-manager#856). Read it from the image's own layers.
                rev, why = install_stamp_revision(man, lambda d: get_raw(f"blobs/{d}", d))
                if rev is None:
                    return None, f"linux/{arch} has no full OCI revision label and {why}; image/tag agreement is unproven"
            revisions.add(rev)
        if len(revisions) != 1:
            return None, "Linux architectures carry different source revisions"
        return revisions.pop(), ""
    except (OSError, ValueError, KeyError, TypeError) as e:
        return None, str(e)[:160]


def app_dockerfile(repo: str, commit: str) -> str | None:
    r = subprocess.run(["gh", "api", f"repos/{repo}/contents/image/Dockerfile?ref={commit}", "-q", ".content"],
                       capture_output=True, text=True)
    if r.returncode:
        return None
    import base64
    return base64.b64decode(r.stdout).decode(errors="replace")


def hermes_fork_online(rel: dict, ok: list[str], errs: list[str]) -> tuple[list[str], list[str]]:
    """Fork pin: the fork commit is on its branch, the GHCR image exists and was built from that commit on both
    architectures, and the hermes-agent app builds FROM exactly that image."""
    h = rel["hermes"]
    fork, im = h["fork"], h["image"]
    found, why = commit_exists(fork["repo"], fork["commit"])
    (ok if found else errs).append(f"hermes.fork: {fork['repo']}@{fork['commit'][:12]}" + ("" if found else f" missing ({why})"))
    if found:
        on, why = on_branch(fork["repo"], fork["commit"], fork["branch"])
        (ok if on else errs).append(f"hermes.fork: {fork['commit'][:12]} on {fork['branch']}" + ("" if on else f" ({why})"))
    found, why = digest_exists(im["ref"], im["digest"])
    (ok if found else errs).append(f"hermes.image: {im['ref']} {im['digest'][:19]}" + ("" if found else
                                   f" missing ({why}; a private image fails here until it is made public)"))
    if found:
        rev, why = image_revision(im["ref"], im["digest"], im["architectures"])
        if rev == fork["commit"]:
            ok.append(f"hermes.image: linux/amd64 + linux/arm64 built from fork commit {rev[:12]}")
        else:
            errs.append(f"hermes.image: built from {(rev or '?')[:12]}, fork pins {fork['commit'][:12]}"
                        + (f" ({why})" if why else ""))
    agent = (rel.get("default_apps") or {}).get("agent") or {}
    if agent.get("app") == "hermes-agent" and agent.get("repo") and agent.get("commit"):
        df = app_dockerfile(agent["repo"], agent["commit"])
        want = f"{im['ref']}@{im['digest']}"
        if df is None:
            errs.append(f"hermes.image: can't read image/Dockerfile in {agent['repo']}@{agent['commit'][:12]}")
        elif want in df:
            ok.append(f"hermes.image: {agent['repo']}@{agent['commit'][:12]} builds FROM the fork image")
        else:
            errs.append(f"hermes.image: {agent['repo']}@{agent['commit'][:12]} does not build FROM {want[:60]}…, "
                        "so fresh installs would run another Hermes")
    return ok, errs


def hermes_online(rel: dict) -> tuple[list[str], list[str]]:
    """Tag -> commit upstream, image digest on Docker Hub, and the hermes-agent app really builds FROM that digest."""
    h, ok, errs = rel.get("hermes"), [], []
    if not h:
        return ok, errs
    for label, pin in (("hermes", h), ("hermes.rollback", h.get("rollback"))):
        if not pin:
            continue
        sha, why = upstream_tag_commit(pin["tag"])
        if sha == pin["commit"]:
            ok.append(f"{label}: {HERMES_UPSTREAM} {pin['tag']} = {sha[:12]}")
        else:
            errs.append(f"{label}: {pin['tag']} is {(sha or '?')[:12]} upstream, release says {pin['commit'][:12]}"
                        + (f" ({why})" if why else ""))
    im = h.get("image")
    if im and isinstance(h.get("fork"), dict):
        return hermes_fork_online(rel, ok, errs)
    if im:
        found, why = dockerhub_digest_exists(im["digest"])
        (ok if found else errs).append(f"hermes.image: {im['digest'][:19]}" + ("" if found else f" missing ({why})"))
        if found:
            rev, why = dockerhub_image_revision(im["digest"])
            expected = im.get("commit", h["commit"])
            if rev is not None and rev == expected == h["commit"]:
                ok.append(f"hermes.image: linux/amd64 + linux/arm64 built from tag commit {rev[:12]}")
            else:
                errs.append(f"hermes.image: built from {(rev or '?')[:12]}, tag pins {h['commit'][:12]}, "
                            f"image pin says {expected[:12]}" + (f" ({why})" if why else ""))
        agent = (rel.get("default_apps") or {}).get("agent") or {}
        if agent.get("app") == "hermes-agent" and agent.get("repo") and agent.get("commit"):
            df = app_dockerfile(agent["repo"], agent["commit"])
            if df is None:
                errs.append(f"hermes.image: can't read image/Dockerfile in {agent['repo']}@{agent['commit'][:12]}")
            elif f"nousresearch/hermes-agent:{h['tag']}@{im['digest']}" in df:
                ok.append(f"hermes.image: {agent['repo']}@{agent['commit'][:12]} builds FROM {h['tag']}@{im['digest'][:19]}")
            else:
                errs.append(f"hermes.image: {agent['repo']}@{agent['commit'][:12]} does not build FROM "
                            f"nousresearch/hermes-agent:{h['tag']}@{im['digest'][:19]}…, so fresh installs run another Hermes")
    return ok, errs


def candidate_place(rel: dict, path: Path) -> list[str]:
    """A candidate lives in releases/candidates/, has a pre-release version, and no channel pointer names it."""
    if not isinstance(rel, dict) or rel.get("channel") != CANDIDATE:
        return []
    errs: list[str] = []
    releases = Path(__file__).resolve().parents[1] / "releases"
    if path.resolve().parent == releases:
        errs.append("channel: a candidate snapshot lives in releases/candidates/, not beside the releases")
    version = str(rel.get("version", ""))
    if "-" not in version:
        errs.append(f"version {version!r}: a candidate needs a pre-release suffix, e.g. 0.3.289-hermes-fork.1")
    for pointer in ("latest", "stable"):
        try:
            if (releases / pointer).read_text().strip() == version:
                errs.append(f"releases/{pointer} names candidate {version}; candidates are never installed")
        except OSError:
            pass
    return errs


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
        if not VERSION.fullmatch(ver):
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
    errs = shape(rel) + candidate_place(rel, Path(a.file))
    ok_lines: list[str] = []
    m_warns: list[str] = []
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
                rev, why = image_revision(im["ref"], im["digest"], im["architectures"])
                if rev != im["source_commit"]:
                    errs.append(f"image {name}: built from {(rev or '?')[:12]}, release says source_commit "
                                f"{im['source_commit'][:12]}" + (f" ({why})" if why else ""))
                else:
                    wf = im.get("image_workflow", ".github/workflows/image.yml")
                    need, why_wf = workflow_paths(src["repo"], rev, wf)
                    # The recipe itself must not drift, even if its paths filter omits itself.
                    short = sorted((set(need or []) | {wf}) - set(im.get("image_inputs") or []))
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
                rev, why = image_revision(im["ref"], im["digest"], im["architectures"])
                if rev is None:
                    errs.append(f"image {name}: can't prove it was built from {im['built_from']}@{src['commit'][:12]}"
                                + (f" ({why})" if why else ""))
                elif rev == src["commit"]:
                    ok_lines.append(f"image {name}: built from {im['built_from']}@{rev[:12]}")
                else:
                    errs.append(f"image {name}: built from {im['built_from']}@{rev[:12]}, release pins "
                                f"{src['commit'][:12]}")
    if not errs and not a.offline:
        m_ok, m_errs, m_warns = moved_repos(rel)
        ok_lines += m_ok
        errs += m_errs
    if not errs and not a.offline:
        h_ok, h_errs = hermes_online(rel)
        ok_lines += h_ok
        errs += h_errs
        try:
            s_ok, s_errs = service_routes_online(rel, SPEC.read_text(encoding="utf-8"))
        except OSError as e:
            s_ok, s_errs = [], [f"spec: can't read {SPEC.name} ({e})"]
        ok_lines += s_ok
        errs += s_errs
    warns = index_drift(rel.get("default_apps") or {}) if not errs and not a.offline else []
    for line in ok_lines:
        print(f"PASS  {line}")
    for w in m_warns:
        print(f"MOVED {w}")
    for w in warns:   # the installer takes the index's current version; get.sh reads it back as DRIFT
        print(f"DRIFT {w}")
    for e in errs:
        print(f"FAIL  {e}")
    version = rel.get('version') if isinstance(rel, dict) else '?'
    print(f"release {version}: {'ok' if not errs else f'{len(errs)} problem(s)'}")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
