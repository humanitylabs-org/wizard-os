#!/usr/bin/env python3
"""Check a repo against the wizard.md app format (v0.1/v0.2). Usage: check_wizard_md.py <repo-dir> [--github owner/repo]"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

TYPES = {"agent", "service", "view", "external"}
CATEGORIES = {"agent", "interface", "app", "system"}
BAD_CAPS = {"ALL", "SYS_ADMIN", "SYS_MODULE", "SYS_PTRACE", "SYS_RAWIO", "NET_ADMIN", "DAC_READ_SEARCH", "BPF", "PERFMON"}
HOST_PATH = re.compile(r"^/(etc|root|boot|proc|sys|dev|var/run|run|home|usr|lib|bin|sbin)(/|$)")
NEEDS = {"mic", "system-audio", "camera", "notifications", "files", "home-network"}
# Browser permissions an app frame may ask the owner for (spec/WIZARD_MD.md "Browser permissions").
PERMISSIONS = {"geolocation"}
# Connectors (owner rule, 27 Oct 2026): an app that signs in to or holds the key for an outside service is a
# Connector and must say `type: external`, or shells and the App Store shelve it under Apps/Agent apps.
CONNECTOR_SLOTS = {"ai-connection", "bank-connection", "cloudflare-connection", "web-data", "x-search"}
CONNECTOR_SLOT = re.compile(r"[a-z0-9-]+-(connection|connector)")
CONNECTOR_SUMMARY = re.compile(r"^\s*(connect|sign in to)\b", re.I)


def connector_signals(d: dict) -> list[str]:
    """Why this manifest looks like a connector (empty when it does not)."""
    why = []
    if str(d.get("id", "")).endswith("-connector"):
        why.append("id ends in -connector")
    pv = d.get("provides") if isinstance(d.get("provides"), list) else []
    slots = [str(p) for p in pv if str(p) in CONNECTOR_SLOTS or CONNECTOR_SLOT.fullmatch(str(p))]
    if slots:
        why.append("provides " + ", ".join(slots))
    if CONNECTOR_SUMMARY.match(str(d.get("summary", ""))):
        why.append("summary starts with Connect/Sign in to")
    return why


def known_dependencies() -> set[str]:
    """Match WAM: source app IDs and explicit provides, never slot aliases."""
    known = set(NEEDS)
    for app in json.loads(Path(__file__).with_name("known_dependencies.json").read_text())["apps"]:
        if app.get("app"):
            known.add(app["app"])
            known.update(app.get("provides") or [])
    return known

SPECS = {0.1, 0.2}
SLOT = re.compile(r"[a-z0-9][a-z0-9-]{1,40}")
NPUB = re.compile(r"npub1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{58}")
PACKAGES = {"source", "build", "image"}
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
VAR = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?::?-([^}]*))?\}")
COMPILE = re.compile(r"\b(npm|yarn|pnpm|bun) run build\b|\bcargo\b|\bgo build\b|\bmake\b|\bgcc\b|\bg\+\+|\brustc\b")


def front_matter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError("no YAML front matter")
    data = yaml.safe_load(m.group(1))
    if not isinstance(data, dict):
        raise ValueError("front matter is not a mapping")
    return data


def compose_risks(text: str) -> list[str]:
    """Host-level access a public, unreviewed app must never ask for (rule 12)."""
    try:
        doc = yaml.safe_load(text) or {}
    except Exception as e:  # noqa: BLE001
        return [f"compose does not parse: {e}"]
    risks = []
    for name, s in ((doc.get("services") or {}) if isinstance(doc, dict) else {}).items():
        if not isinstance(s, dict):
            continue
        if s.get("privileged"):
            risks.append(f"{name}: privileged")
        for k in ("network_mode", "pid", "ipc", "userns_mode", "uts"):
            if str(s.get(k, "")).lower() == "host":
                risks.append(f"{name}: {k}: host")
        for c in s.get("cap_add") or []:
            if str(c).upper().removeprefix("CAP_") in BAD_CAPS:
                risks.append(f"{name}: cap_add {c}")
        if s.get("devices"):
            risks.append(f"{name}: host devices")
        for o in s.get("security_opt") or []:
            if "unconfined" in str(o).lower():
                risks.append(f"{name}: security_opt {o}")
        for v in s.get("volumes") or []:
            src = v.split(":")[0] if isinstance(v, str) else str((v or {}).get("source", ""))
            if any(x in src for x in ("docker.sock", "containerd.sock", "podman.sock")):
                risks.append(f"{name}: mounts the container runtime socket")
            elif src == "/" or HOST_PATH.match(src):
                risks.append(f"{name}: mounts host path {src}")
    return risks


def _resolved(image: str) -> str:
    """`${VAR:-default}` resolves to its default, as on a box that sets nothing."""
    return VAR.sub(lambda m: m.group(1) or "", str(image or ""))


def _inside(repo: Path, rel: str) -> bool:
    try:
        return (repo / rel).resolve().is_relative_to(repo.resolve())
    except (OSError, ValueError):
        return False


def _hash_locked(path: Path) -> bool:
    if not path.is_file():
        return False
    reqs = [ln for ln in path.read_text(errors="replace").replace("\\\n", " ").splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return bool(reqs) and all("--hash=" in ln for ln in reqs)


def dockerfile_problems(repo: Path, dockerfile: Path, context: Path | None = None) -> list[str]:
    """Rule 14 for `package: build`: pinned bases, hash-locked pip, no compile or bundle steps."""
    if not dockerfile.is_file():
        return [f"no Dockerfile at {dockerfile.relative_to(repo) if _inside(repo, str(dockerfile)) else dockerfile}"]
    text = dockerfile.read_text(errors="replace").replace("\\\n", " ")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    args = {}
    for ln in lines:
        m = re.match(r"(?i)ARG\s+([A-Za-z_][A-Za-z0-9_]*)=(\S+)", ln)
        if m:
            args[m.group(1)] = m.group(2)
    context = context or dockerfile.parent
    copies: dict[str, str] = {}  # in-image path -> path in the build context
    for ln in lines:
        m = re.match(r"(?i)(?:COPY|ADD)\s+(?:--\S+\s+)*(\S+)\s+(\S+)$", ln)
        if m:
            src, dst = m.group(1), m.group(2)
            copies[dst.rstrip("/") + "/" + Path(src).name if dst.endswith("/") else dst] = src
    stages, bad = set(), []
    for ln in lines:
        m = re.match(r"(?i)FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", ln)
        if m:
            img = re.sub(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", lambda v: args.get(v.group(1), ""), m.group(1))
            if img.lower() not in stages and img != "scratch" and not DIGEST.search(img):
                bad.append(f"FROM {m.group(1)} is not pinned by digest")
            if m.group(2):
                stages.add(m.group(2).lower())
            continue
        if re.match(r"(?i)RUN\b", ln):
            if COMPILE.search(ln):
                bad.append(f"compiles or bundles on the box: {ln[:80]}")
            for part in re.split(r"&&|;", ln):
                if "pip install" in part and "--require-hashes" not in part:
                    reqs = re.findall(r"(?:-r|--requirement)\s+(\S+)", part)
                    if not reqs or not all(_hash_locked(context / copies.get(r, r).lstrip("/")) for r in reqs):
                        bad.append(f"pip install is not hash-locked: {part.strip()[:80]}")
    return bad


def packaging_problems(repo: Path, package: str, compose_text: str) -> list[str]:
    """Rule 14: how the app's containers come to exist (source, build or image)."""
    if package not in PACKAGES:
        return [f"runtime.package must be source, build or image, not {package!r}"]
    try:
        doc = yaml.safe_load(compose_text) or {}
    except Exception as e:  # noqa: BLE001
        return [f"compose does not parse: {e}"]
    services = {n: s for n, s in ((doc.get("services") or {}) if isinstance(doc, dict) else {}).items() if isinstance(s, dict)}
    bad, mounted, builds = [], False, {n: s["build"] for n, s in services.items() if s.get("build")}
    for n, s in services.items():
        if n not in builds and not DIGEST.search(_resolved(s.get("image", ""))):
            bad.append(f"{n}: image {s.get('image')!r} is not pinned by digest (name@sha256:...)")
        for v in s.get("volumes") or []:
            src, opts = (v.split(":")[0], v.split(":")[2:]) if isinstance(v, str) else (str((v or {}).get("source", "")), ["ro"] if (v or {}).get("read_only") else [])
            if src.startswith("${APP_SOURCE_DIR}"):
                mounted = True
                if "ro" not in ",".join(opts).split(","):
                    bad.append(f"{n}: ${{APP_SOURCE_DIR}} must be mounted read-only (:ro)")
    if package == "source":
        if builds:
            bad.append(f"source apps build nothing; remove build: from {', '.join(builds)}")
        if not mounted:
            bad.append("source apps mount their code: add ${APP_SOURCE_DIR}[/subdir]:/app:ro to a service")
    elif package == "image":
        if builds:
            bad.append(f"image apps use their published image; remove build: from {', '.join(builds)}")
    else:
        if not builds:
            bad.append("build apps need a build: section (context relative to the repo root)")
        for n, b in builds.items():
            b = {"context": b} if isinstance(b, str) else (b or {})
            ctx = str(b.get("context") or ".")
            if VAR.search(ctx) or ctx.startswith("/") or not _inside(repo, ctx):
                bad.append(f"{n}: build.context {ctx!r} must be a path inside the repo")
                continue
            df = str(b.get("dockerfile") or "Dockerfile")
            if not _inside(repo / ctx, df):
                bad.append(f"{n}: build.dockerfile {df!r} must stay inside the context")
                continue
            bad += [f"{n}: {p}" for p in dockerfile_problems(repo, repo / ctx / df, repo / ctx)]
    return bad


"""Rule 15, shared verbatim by the spec checker and WAM."""
def storage_problems(manifest: dict, compose: dict) -> list[str]:
    import re
    ident = re.compile(r'[a-z0-9][a-z0-9-]{1,40}')
    def relative(p):
        return (isinstance(p, str) and bool(p) and not p.startswith('/')
                and not any(x in ('', '.', '..') for x in p.split('/'))
                and not any(x in p for x in ('\\', '$', ':', ','))
                and not any(ord(c) < 32 or ord(c) == 127 for c in p))
    def absolute(p):
        return isinstance(p, str) and p.startswith('/') and p != '/' and relative(p[1:])
    bad = []
    volumes = compose.get('volumes', {})
    if not isinstance(volumes, dict):
        bad.append('volumes must be a mapping')
    else:
        for name, opts in volumes.items():
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name) or name in ('.', '..'):
                bad.append('invalid volume id')
            if opts is not None and not isinstance(opts, dict):
                bad.append(f'{name}: volume options must be a mapping')
            elif opts and ('name' in opts or opts.get('external') or opts.get('driver') or opts.get('driver_opts')):
                bad.append(f'{name}: fixed name, external and custom-driver volumes are not portable; use shares')
    for field, keys in (('shares', {'id', 'path'}), ('mounts', {'app', 'share', 'path'})):
        rows = manifest.get(field, [])
        if not isinstance(rows, list):
            bad.append(f'{field} must be a list'); continue
        seen = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != keys:
                bad.append(f'{field}: expected {sorted(keys)}'); continue
            ids = ['id'] if field == 'shares' else ['app', 'share']
            if not all(isinstance(row[k], str) and ident.fullmatch(row[k]) for k in ids):
                bad.append(f'{field}: invalid id')
            if not (relative(row['path']) if field == 'shares' else absolute(row['path'])):
                bad.append(f'{field}: unsafe path')
            key = row['id'] if field == 'shares' else row['path']
            if not isinstance(key, str) or key in seen:
                bad.append(f'{field}: duplicate or invalid id/path')
            else:
                seen.add(key)
    return bad


def whats_new_ok(value: object) -> bool:
    """`whats_new`: one line (1-140 characters, no line breaks or control characters) saying what changed in this
    version, shown to the owner next to the update in Settings > About & updates."""
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 140 and not re.search(r"[\x00-\x1f\x7f]", value)


def voice_names(manifest: dict) -> list[str]:
    """Spoken names that open this app; absence is backward compatible."""
    names = manifest.get("voice_names", [])
    if (not isinstance(names, list) or len(names) > 8 or
            any(not isinstance(n, str) or not n.strip() or len(n) > 40 or
                any(ord(c) < 32 or ord(c) == 127 for c in n) for n in names)):
        raise ValueError("voice_names must be a list of at most 8 nonblank strings, each at most 40 characters, without controls")
    return list(names)


def permissions_ok(value: object) -> bool:
    """`permissions`: a list of distinct browser permissions from PERMISSIONS; absent or [] means none."""
    return (isinstance(value, list) and all(isinstance(v, str) and v in PERMISSIONS for v in value)
            and len(set(value)) == len(value))


HOME_SCREEN_KEYS = {"offline", "position_keys", "route_state"}
HOME_SCREEN_ROUTE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,39}")


def home_screen(manifest: dict) -> dict:
    """Home-screen pin capabilities the app declares for itself; absence is backward compatible.

    Returns only what was declared: offline (true), position_keys (patterns) and route_state (a name).
    """
    if "home_screen" not in manifest:
        return {}
    hs = manifest["home_screen"]  # a present null is malformed, not absent
    if not isinstance(hs, dict) or set(hs) - HOME_SCREEN_KEYS:
        raise ValueError("home_screen must be a mapping with only offline, position_keys and route_state")
    out: dict = {}
    if "offline" in hs:
        if type(hs["offline"]) is not bool:
            raise ValueError("home_screen.offline must be a boolean")
        if hs["offline"]:
            out["offline"] = True
    if "position_keys" in hs:
        keys = hs["position_keys"]
        if (not isinstance(keys, list) or len(keys) > 8 or
                any(not isinstance(k, str) or len(k) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in k)
                    or len(k.split("*", 1)[0]) < 3 for k in keys)):
            raise ValueError("home_screen.position_keys must be at most 8 strings of at most 120 characters, "
                             "without controls, each with at least 3 literal characters before the first '*'")
        if keys:
            out["position_keys"] = list(keys)
    if "route_state" in hs:
        rs = hs["route_state"]
        if not isinstance(rs, str) or not HOME_SCREEN_ROUTE.fullmatch(rs):
            raise ValueError("home_screen.route_state must be a name matching [A-Za-z_][A-Za-z0-9_]{0,39}")
        out["route_state"] = rs
    return out


def check(repo: Path, github: str | None = None) -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []

    def rule(name: str, ok: bool, detail: str = "") -> None:
        out.append((name, bool(ok), detail))

    f = repo / "wizard.md"
    if not f.is_file():
        rule("wizard.md present", False, str(f))
        return out
    rule("wizard.md present", True)
    try:
        d = front_matter(f.read_text())
    except Exception as e:  # noqa: BLE001 - report as a failed rule
        rule("front matter parses", False, str(e))
        return out
    rule("front matter parses", True)
    if "voice_names" in d:
        try:
            voice_names(d)
            rule("voice_names valid", True)
        except ValueError as e:
            rule("voice_names valid", False, str(e))
    if "home_screen" in d:
        try:
            declared = home_screen(d)
            rule("home_screen valid", True)
            if declared:
                hv = d.get("view")
                rule("home screen has a declared view", isinstance(hv, dict) and bool(hv.get("path")) and bool(hv.get("port")), str(hv))
        except ValueError as e:
            rule("home_screen valid", False, str(e))
    rule("spec version known", d.get("wizard") in SPECS, str(d.get("wizard")))
    rule("id valid", bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", str(d.get("id", "")))), str(d.get("id")))
    t = d.get("type")
    rule("type valid", t in TYPES, str(t))
    why = connector_signals(d)
    if why:
        rule("connector apps are type external", t == "external", f"type {t}; " + "; ".join(why))
    rule("version valid", bool(re.fullmatch(r"\d+\.\d+\.\d+([-+.][\w.]+)?", str(d.get("version", "")))), str(d.get("version")))
    s = str(d.get("summary", ""))
    rule("summary 1-140 chars", 0 < len(s) <= 140, f"{len(s)} chars")
    rule("license and source", bool(d.get("license")) and bool(d.get("source")))
    rt = d.get("runtime") or {}
    for key in ("config", "compose"):
        p = rt.get(key)
        rule(f"runtime.{key} exists", bool(p) and (repo / p).is_file(), str(p))
    cfg_path = repo / str(rt.get("config") or "")
    if rt.get("config") and cfg_path.is_file():
        import time as _t
        try:
            cfg = json.loads(cfg_path.read_text())
            now_ms = int(_t.time() * 1000)
            bad_ts = [k for k in ("created_at", "updated_at") if isinstance(cfg.get(k), (int, float)) and cfg[k] > now_ms]
            rule("runtipi config id matches", cfg.get("id") == d.get("id"), f"{cfg.get('id')} vs {d.get('id')}")
            rule("runtipi timestamps not in future", not bad_ts, ", ".join(bad_ts))
        except Exception as e:  # noqa: BLE001
            rule("runtipi config parses", False, str(e))
    if t in {"agent", "service", "external"}:
        m = d.get("mcp") or {}
        rule("mcp declared", bool(m.get("path")) and bool(m.get("port")), json.dumps(m))
    if t != "view":
        sk = d.get("skill")
        ok, detail = False, str(sk)
        if sk and (repo / sk).is_file():
            try:
                sfm = front_matter((repo / sk).read_text())
                ok = bool(sfm.get("name")) and bool(sfm.get("description"))
                detail = sfm.get("name", "")
            except Exception as e:  # noqa: BLE001
                detail = str(e)
        rule("skill ships with name+description", ok, detail)
    if t == "view":
        v = d.get("view") or {}
        rule("view declared", bool(v.get("path")) and bool(v.get("port")), json.dumps(v))
    bad = [n for n in d.get("needs") or [] if n not in known_dependencies() and not str(n).startswith("credentials:")]
    rule("needs known", not bad, ", ".join(map(str, bad)))
    if "whats_new" in d:
        wn = d["whats_new"]
        rule("whats_new is one line of 1-140 chars", whats_new_ok(wn), repr(wn)[:60])
    if "permissions" in d:
        pm = d["permissions"]
        rule("permissions are known (geolocation)", permissions_ok(pm), repr(pm)[:60])
    if "receives_voice_input" in d:
        rv = d["receives_voice_input"]
        rule("receives_voice_input is boolean", type(rv) is bool, repr(rv))
        if rv is True:
            voice_view = d.get("view")
            rule("voice input has a declared view", isinstance(voice_view, dict) and bool(voice_view.get("path")) and bool(voice_view.get("port")), str(voice_view))
    if d.get("provides") is not None:
        pv = d.get("provides")
        badp = [p for p in (pv if isinstance(pv, list) else [pv]) if not SLOT.fullmatch(str(p))]
        rule("provides are slot ids", isinstance(pv, list) and not badp, ", ".join(map(str, badp)))
    if d.get("category") is not None:
        rule("category is agent, interface, app or system", d.get("category") in CATEGORIES, str(d.get("category")))
    if d.get("icon") is not None:
        ic = repo / str(d.get("icon"))
        rule("icon exists (png/jpg)", ic.is_file() and ic.suffix.lower() in {".png", ".jpg", ".jpeg"}, str(d.get("icon")))
    comp = repo / str(rt.get("compose") or "")
    if rt.get("compose") and comp.is_file():
        risks = compose_risks(comp.read_text())
        rule("container asks for no host-level access", not risks, "; ".join(risks))
        if "package" in rt:
            probs = packaging_problems(repo, str(rt.get("package")), comp.read_text())
            rule(f"packaging ({rt.get('package')}) follows the rules", not probs, "; ".join(probs))
    if d.get("agent_binding") is not None:
        ab = d.get("agent_binding")
        ok = ab is True or (isinstance(ab, dict) and set(ab) <= {"required", "purpose"}
                            and isinstance(ab.get("required", False), bool) and len(str(ab.get("purpose", ""))) <= 120)
        rule("agent_binding is true or {required, purpose}", ok, json.dumps(ab))
    try:
        probs = storage_problems(d, yaml.safe_load(comp.read_text()) if comp.is_file() else {})
    except Exception as e:
        probs = [str(e)]
    rule("storage (rule 15)", not probs, "; ".join(probs))
    if d.get("publisher") is not None:
        rule("publisher is an npub", bool(NPUB.fullmatch(str(d.get("publisher")))), str(d.get("publisher")))
    if github:
        r = subprocess.run(["gh", "api", f"repos/{github}/topics", "--jq", ".names"], capture_output=True, text=True)
        topics = set(re.findall(r'"([^"]+)"', r.stdout))
        rule("GitHub topic wizard-app (or wizard-ai during the transition)", bool(topics & {"wizard-app", "wizard-ai"}), r.stdout.strip() or r.stderr.strip())
    return out


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    gh = args[args.index("--github") + 1] if "--github" in args else None
    results = check(Path(args[0]), gh)
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    passed = all(ok for _, ok, _ in results)
    print("COMPATIBLE" if passed else "NOT COMPATIBLE")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
