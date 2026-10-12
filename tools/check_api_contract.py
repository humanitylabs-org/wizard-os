#!/usr/bin/env python3
"""Check that every Agent Service request in the Wizard UX source is a documented route in spec/AGENT_SERVICE_API.md.

    python3 tools/check_api_contract.py --ux <wizard-ux checkout>            # text report
    python3 tools/check_api_contract.py --ux <wizard-ux checkout> --json     # one JSON document
    python3 tools/check_api_contract.py --ux DIR --strict                    # documented gaps fail too

Scans web/**/*.js|html and android/app/src/main/**/*.java|js|html for string literals that start with /wizard/ or
/wizard-os-home/api/, plus the addresses the UX derives at run time (bootstrap endpoints, the pre-bootstrap aliases,
the voice status address). Each request (method + path) must match a route in the spec's ```routes block whose class
is stable, passthrough, compat or page, with only the query keys that route allows. Also fails when a route marked
`ux` in the spec is not found in the source (the table would be stale).

Exit 0 = every request maps (documented gaps are listed); 1 = an undocumented, proposed-only or mismatched request,
or a stale `ux` mark (each printed); 2 = usage / unreadable input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent / "spec" / "AGENT_SERVICE_API.md"
SERVED = {"stable", "passthrough", "compat", "page"}
UX_PREFIX = "/wizard-os-home/"
# Requests to these prefixes are other apps' routes, not the Agent Service (see the spec's "Out of scope").
OTHER_APPS = ("/wizard-search/", "/meetings/")

LITERAL = re.compile(r"""(['"`])((?:/wizard/|/wizard-os-home/)(?:(?!\1)[^\\\n]|\\.)*)\1""")
STATIC_FILE = re.compile(r"^/wizard-os-home/(?!api/)[^?]*\.[A-Za-z0-9]+(?:\?.*)?$")  # UX static files, not API
# Literals that are not requests themselves: (file, literal, regex the line must match, why). A rule only applies on a
# line that still matches, so a source change brings the literal back into the check.
ADDRESS_ONLY = [
    ("web/core/voice-status.js", "/wizard/voice/transcribe", r"endpoint\('transcribe'\)\)\s*\|\|", "fallback base; derived() adds the status request"),
    ("android/app/src/main/java/ai/wizards/os/assist/Transcriber.java", "/wizard-os-home/api/transcribe",
     r"static final String ENDPOINT =", "unused constant; the request itself is the POST a few lines down"),
]
# Literals with a segment the code fills from a fixed set: (file, normalised path, {placeholder index: values}, anchor
# regex per value that must exist in the file).
VARIANTS = [
    ("web/core/chat-errors.js", "/wizard/attention/{x}/{x}", {1: ["retry", "dismiss"]},
     {"retry": r"_attention\(id, 'retry'\)", "dismiss": r"_attention\(id, 'dismiss'\)"}),
]


def address_only(rel: str, lit: str, line: str) -> bool:
    return any(rel == f and lit == l and re.search(rx, line) for f, l, rx, _ in ADDRESS_ONLY)


def expand(rel: str, path: str, text: str) -> list[str]:
    for f, p, slots, anchors in VARIANTS:
        if f == rel and p == path:
            out = []
            for idx, values in slots.items():
                for v in values:
                    if re.search(anchors[v], text):
                        parts = path.split("{x}")
                        out.append("{x}".join(parts[: idx + 1]) + v + "{x}".join(parts[idx + 1:]))
            return out or [path]
    return [path]
METHOD_JS = re.compile(r"""method\s*:\s*['"]([A-Z]+)['"]""")
METHOD_JAVA = re.compile(r"""\b(?:request|json|post)\(\s*"([A-Z]+)"\s*,\s*(?:origin\s*\+\s*)?$""")


def parse_routes(text: str) -> list[dict]:
    m = re.search(r"```routes\n(.*?)```", text, re.S)
    if not m:
        raise ValueError("no ```routes block in the spec")
    routes = []
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"bad routes line: {line}")
        methods, path, cls, ux = parts[:4]
        query = [] if len(parts) < 5 or parts[4] == "-" else parts[4].split(",")
        for method in methods.split(","):
            routes.append({"method": method, "path": path, "cls": cls, "ux": ux == "ux", "query": query,
                           "re": re.compile("^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(path)) + "$")})
    return routes


def bootstrap_endpoints(text: str) -> dict:
    """The endpoint addresses from the spec's bootstrap example (front ends must take them from bootstrap)."""
    m = re.search(r'"endpoints":(\{[^}]*\})', text)
    return json.loads(m.group(1)) if m else {}


def normalise(literal: str) -> tuple[str, list[str]]:
    """'/wizard/files/${encodeURIComponent(id)}/content?x=${y}' -> ('/wizard/files/{x}/content', ['x'])."""
    s = re.sub(r"\$\{[^}]*\}", "{x}", literal)
    path, _, query = s.partition("?")
    keys = [kv.split("=", 1)[0] for kv in query.split("&") if kv and not kv.startswith("{x}")]
    if path.endswith("/") and path not in ("/wizard/", UX_PREFIX):
        path += "{x}"  # Java: "/wizard/hermes/v1/runs/" + URLEncoder.encode(id)
    return path, keys


def methods_near(lines: list[str], i: int, start: int, end: int, is_java: bool) -> list[str]:
    """The HTTP method(s) a literal is requested with, from the call around it. Defaults to GET (fetch, links, media src)."""
    line = lines[i]
    if is_java:
        m = re.search(r'\(\s*"([A-Z]+)"\s*,\s*[^,]*$', line[:start])     # request("POST", "/wizard/…")
        if m:
            return [m.group(1)]
        for nxt in lines[i:i + 8]:                                         # new URL(origin + "/…") … setRequestMethod("POST")
            m = re.search(r'setRequestMethod\("([A-Z]+)"\)', nxt)
            if m:
                return [m.group(1)]
        return ["GET"]
    m = re.search(r"\b(post|put|patch|del)\(\s*$", line[:start])           # helper named after its method: post(`/wizard/…`)
    if m:
        return [{"post": "POST", "put": "PUT", "patch": "PATCH", "del": "DELETE"}[m.group(1)]]
    m = METHOD_JS.search(line, end)
    if m:
        return [m.group(1)]
    v = re.search(r"\b(?:const|let|var)\s+(\w+)\s*=\s*$", line[:start])  # const url = `/wizard/…`; fetch(url, { method: 'HEAD' })
    out = ["GET"]
    if v:
        for nxt in lines[i + 1:i + 6]:
            m = re.search(r"fetch\(\s*" + re.escape(v.group(1)) + r"\s*,[^)]*method\s*:\s*['\"]([A-Z]+)['\"]", nxt)
            if m and m.group(1) not in out:
                out.append(m.group(1))
    return out


def scan(ux: Path) -> list[dict]:
    files = sorted(list((ux / "web").rglob("*.js")) + list((ux / "web").rglob("*.html"))
                   + [p for p in (ux / "android/app/src/main").rglob("*") if p.suffix in (".java", ".js", ".html")])
    found = []
    for f in sorted(set(files)):
        if "/motion/" in str(f):
            continue
        is_java = f.suffix == ".java"
        rel = str(f.relative_to(ux))
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            for m in LITERAL.finditer(line):
                lit = m.group(2)
                if lit.startswith(OTHER_APPS) or STATIC_FILE.match(lit) or address_only(rel, lit, line):
                    continue
                path, keys = normalise(lit)
                for concrete in expand(rel, path, text):
                    for method in methods_near(lines, i, m.start(), m.end(), is_java):
                        found.append({"method": method, "path": concrete, "query": keys, "where": f"{rel}:{i + 1}", "how": "literal"})
    return found


def derived(ux: Path, endpoints: dict) -> tuple[list[dict], list[str]]:
    """Requests the UX builds at run time. Each rule is anchored on the source that builds it, so a rule whose
    anchor disappeared is reported (the derivation changed) instead of silently passing."""
    rules = [
        # (file, anchor regex, method, path, query keys, why)
        ("web/core/apps.js", r"endpoint\('apps'\)", "GET", endpoints.get("apps", ""), [], "bootstrap endpoints.apps"),
        ("web/core/chat-search.js", r"endpoint\('sessions'\)", "GET", endpoints.get("sessions", ""), [], "bootstrap endpoints.sessions"),
        ("web/core/chat-search.js", r"\$\{base\(\)\}/\$\{encodeURIComponent\(s\.id\)\}/messages\?order=latest&limit=\$\{LIMIT\}&view=wizard",
         "GET", endpoints.get("sessions", "") + "/{x}/messages", ["order", "limit", "view"], "search reads each thread"),
        ("web/core/config.js", r"endpoint\('transcribe'\)", "POST", endpoints.get("transcribe", ""), [], "bootstrap endpoints.transcribe"),
        ("web/app.js", r"endpoint\('route'\)", "POST", endpoints.get("route", ""), [], "bootstrap endpoints.route"),
        ("web/core/config.js", r"transcribe: 'api/transcribe'", "POST", UX_PREFIX + "api/transcribe", [], "pre-bootstrap alias, relative to the page"),
        ("web/core/config.js", r"route: 'api/route'", "POST", UX_PREFIX + "api/route", [], "pre-bootstrap alias, relative to the page"),
        ("web/core/voice-status.js", r"replace\(/\[\^/\]\*\$/, 'status'\)", "GET",
         re.sub(r"[^/]*$", "status", endpoints.get("transcribe", ""), count=1), [], "voice status from the bootstrap transcribe address"),
        ("web/core/voice-status.js", r"replace\(/\[\^/\]\*\$/, 'status'\)", "GET", UX_PREFIX + "api/status", [],
         "voice status from the pre-bootstrap alias"),
    ]
    out, stale = [], []
    for rel, anchor, method, path, keys, why in rules:
        f = ux / rel
        text = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
        m = re.search(anchor, text)
        if not m or not path:
            stale.append(f"{rel}: derivation anchor not found ({why}); update tools/check_api_contract.py")
            continue
        no = text[: m.start()].count("\n") + 1
        out.append({"method": method, "path": path, "query": keys, "where": f"{rel}:{no}", "how": f"derived: {why}"})
    return out, stale


def check(ux: Path, spec_text: str, strict: bool = False, derive: bool = True) -> dict:
    routes = parse_routes(spec_text)
    requests = scan(ux)
    extra, stale = derived(ux, bootstrap_endpoints(spec_text)) if derive else ([], [])
    requests += extra
    problems, gaps, mapped = [], [], []
    used = set()
    for r in requests:
        hits = [x for x in routes if x["re"].match(r["path"]) and x["method"] == r["method"]]
        any_method = [x for x in routes if x["re"].match(r["path"])]
        label = f"{r['method']} {r['path']}  ({r['where']}, {r['how']})"
        if not hits:
            problems.append(f"undocumented: {label}" + (f"; documented methods: {sorted({x['method'] for x in any_method})}" if any_method else ""))
            continue
        route = hits[0]
        used.add((route["method"], route["path"]))
        if route["cls"] == "proposed":
            problems.append(f"proposed-only route used by the UX (not served on main): {label}")
            continue
        if route["cls"] == "gap":
            gaps.append(f"documented gap: {label}")
            continue
        if route["cls"] not in SERVED:
            problems.append(f"route class {route['cls']} is not for front ends: {label}")
            continue
        bad = [k for k in r["query"] if k not in route["query"]]
        if bad:
            problems.append(f"query keys {bad} not allowed on {route['method']} {route['path']}: {label}")
            continue
        mapped.append({**{k: r[k] for k in ("method", "path", "where", "how")}, "route": f"{route['method']} {route['path']}", "class": route["cls"]})
    for x in routes:
        if x["ux"] and (x["method"], x["path"]) not in used:
            problems.append(f"stale ux mark: {x['method']} {x['path']} is marked ux but no UX request maps to it")
    problems += stale
    if strict:
        problems += gaps
    return {"ok": not problems, "requests": len(requests), "mapped": len(mapped), "routes_used": len(used),
            "problems": problems, "gaps": gaps, "detail": mapped}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check Wizard UX requests against spec/AGENT_SERVICE_API.md.")
    ap.add_argument("--ux", required=True, help="wizard-ux checkout")
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="documented gaps fail too")
    a = ap.parse_args(argv)
    ux = Path(a.ux)
    if not (ux / "web").is_dir():
        print(f"check_api_contract: {ux} is not a wizard-ux checkout (no web/)", file=sys.stderr)
        return 2
    try:
        spec_text = Path(a.spec).read_text(encoding="utf-8")
        result = check(ux, spec_text, a.strict)
    except (OSError, ValueError) as e:
        print(f"check_api_contract: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        for d in result["detail"]:
            print(f"ok    {d['method']:6} {d['path']:58} -> {d['route']} [{d['class']}]  {d['where']}")
        for g in result["gaps"]:
            print(f"gap   {g}")
        for p in result["problems"]:
            print(f"FAIL  {p}")
        print(f"\n{result['requests']} UX requests, {result['mapped']} mapped onto {result['routes_used']} documented routes, "
              f"{len(result['gaps'])} documented gaps, {len(result['problems'])} problems -> {'COMPATIBLE' if result['ok'] else 'INCOMPATIBLE'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
