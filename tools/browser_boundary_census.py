#!/usr/bin/env python3
"""Which browser frames and native bridges can still act as the owner (wizard-os #133).

    python3 tools/browser_boundary_census.py ../wizard-ux          # a wizard-ux checkout
    python3 tools/browser_boundary_census.py ../wizard-ux --json   # same, as one JSON object

Issue #133: app screens load as same-origin frames with no sandbox, so a script on an app page can
reach the shell and call owner endpoints. The planned fix (draft wizard-os#163, by Archimedes) sandboxes
every app frame without `allow-same-origin` and keeps the native bridge on the shell document only. This
tool is the static half of that check. It reads a wizard-ux checkout and lists, one line each:

    frames   every `<iframe ...>` literal and `createElement('iframe')` in web/ (vendor and tests skipped),
             with its sandbox state:
               open         no sandbox attribute: the frame runs same-origin with the shell
               same-origin  sandboxed, but the token list includes allow-same-origin (no boundary)
               sandboxed    sandboxed without allow-same-origin
               unknown      the sandbox value is built at runtime and could not be read from the file
    bridges  every Android `addJavascriptInterface(..., "Name")` outside src/test. Such an interface is
             reachable from every frame in that WebView, whatever the frame's sandbox (#163 enable gate 1).

A static census is not runtime proof: it does not show what a frame loads, and it cannot see a sandbox
set somewhere else in the file. The hostile-app browser run stays the acceptance test.

It only reads files. It never edits, commits or runs anything, and nothing runs it automatically, so it
changes no behaviour and `WIZARD_BROWSER_BOUNDARY` stays off. Exit 0 = every frame is sandboxed without
same-origin and no bridge is found, 1 = at least one open, same-origin or unknown frame or bridge
(each printed), 2 = the path is not a readable wizard-ux checkout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WEB_SUFFIXES = (".js", ".mjs", ".html")
SKIP_DIRS = {"vendor", "node_modules", "tests", "test", "dist"}
ANDROID_SUFFIXES = (".java", ".kt")

IFRAME_TAG = re.compile(r"<iframe\b(?P<attrs>[^>]*)>", re.I)
CREATE_IFRAME = re.compile(r"createElement\(\s*['\"]iframe['\"]\s*\)")
# Attribute forms inside a tag literal: sandbox, sandbox="a b", sandbox='a', sandbox="${NAME}".
SANDBOX_ATTR = re.compile(r"(?<![\w-])sandbox(?:\s*=\s*(?:\"(?P<dq>[^\"]*)\"|'(?P<sq>[^']*)'|(?P<bare>[^\s>]+)))?", re.I)
# Script forms after createElement: x.sandbox = '...', x.setAttribute('sandbox', '...'), x.sandbox.add(...).
SANDBOX_SET = re.compile(
    r"\.sandbox\s*=\s*(?P<v1>[^;\n]+)|setAttribute\(\s*['\"]sandbox['\"]\s*,\s*(?P<v2>[^)\n]+)\)|\.sandbox\.(?:add|value)\b"
)
TEMPLATE_REF = re.compile(r"^\$\{\s*(?P<name>[A-Za-z_$][\w$]*)\s*\}$")
NAME_ONLY = re.compile(r"^[A-Za-z_$][\w$]*$")
JS_INTERFACE = re.compile(r"addJavascriptInterface\(\s*(?P<obj>[^,]+?)\s*,\s*\"(?P<name>[^\"]+)\"\s*\)")
# How far after createElement('iframe') a sandbox assignment still counts as the same frame.
CREATE_WINDOW = 600


def const_value(text: str, name: str) -> str | None:
    """The literal string `NAME = '...'` holds in the same file (first plain assignment), if any.

    Matches `const NAME = '...'` and a later name in one declaration, `const A = 1, NAME = '...'`.
    """
    m = re.search(r"(?<![\w$.])" + re.escape(name) + r"\s*=(?!=)\s*(['\"`])(?P<v>[^'\"`]*)\1", text)
    return m.group("v") if m else None


def resolve(text: str, raw: str | None) -> str | None:
    """Turn an attribute or assignment value into the sandbox token string, or None if unknowable."""
    if raw is None:
        return None
    raw = raw.strip().rstrip(";").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"`" and "${" not in raw[1:-1]:
        return raw[1:-1]
    ref = TEMPLATE_REF.match(raw)
    if ref:
        return const_value(text, ref.group("name"))
    if NAME_ONLY.match(raw):
        return const_value(text, raw)
    if "${" not in raw and not any(c in raw for c in "'\"`()+"):
        return raw
    return None


def classify(tokens: str | None, present: bool) -> str:
    if not present:
        return "open"
    if tokens is None:
        return "unknown"
    return "same-origin" if "allow-same-origin" in tokens.lower().split() else "sandboxed"


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def frames_in(rel: str, text: str) -> list[dict]:
    found = []
    for m in IFRAME_TAG.finditer(text):
        attrs = m.group("attrs")
        s = SANDBOX_ATTR.search(attrs)
        if s:
            raw = s.group("dq") if s.group("dq") is not None else s.group("sq")
            if raw is None:
                raw = s.group("bare")
            tokens = "" if raw is None else (resolve(text, f'"{raw}"') if "${" not in raw else resolve(text, raw))
        else:
            tokens = None
        cls = re.search(r"class=[\"']([^\"']*)", attrs)
        found.append({
            "file": rel, "line": line_of(text, m.start()), "form": "tag",
            "class": cls.group(1) if cls else "",
            "sandbox": tokens, "state": classify(tokens, bool(s)),
        })
    for m in CREATE_IFRAME.finditer(text):
        window = text[m.end(): m.end() + CREATE_WINDOW]
        nxt = CREATE_IFRAME.search(window)
        if nxt:
            window = window[: nxt.start()]
        s = SANDBOX_SET.search(window)
        tokens = resolve(text, s.group("v1") or s.group("v2")) if s and (s.group("v1") or s.group("v2")) else None
        cls = re.search(r"className\s*=\s*['\"]([^'\"]*)", window)
        found.append({
            "file": rel, "line": line_of(text, m.start()), "form": "createElement",
            "class": cls.group(1) if cls else "",
            "sandbox": tokens, "state": classify(tokens, bool(s)),
        })
    return found


def walk(root: Path, sub: str, suffixes: tuple[str, ...], skip_test_dirs: bool):
    base = root / sub
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.is_symlink() or not path.name.endswith(suffixes):
            continue
        parts = set(path.relative_to(root).parts[:-1])
        if skip_test_dirs and parts & SKIP_DIRS:
            continue
        if path.name.endswith((".test.js", ".test.mjs", ".spec.js")):
            continue
        yield path


def census(root: Path) -> dict:
    frames, bridges = [], []
    for path in walk(root, "web", WEB_SUFFIXES, True):
        rel = path.relative_to(root).as_posix()
        frames.extend(frames_in(rel, path.read_text(errors="replace")))
    for path in walk(root, "android", ANDROID_SUFFIXES, False):
        rel = path.relative_to(root).as_posix()
        if "/src/test/" in f"/{rel}" or "/src/androidTest/" in f"/{rel}":
            continue
        text = path.read_text(errors="replace")
        for m in JS_INTERFACE.finditer(text):
            bridges.append({"file": rel, "line": line_of(text, m.start()), "name": m.group("name")})
    counts = {k: sum(f["state"] == k for f in frames) for k in ("open", "same-origin", "unknown", "sandboxed")}
    return {"frames": frames, "bridges": bridges, "counts": counts,
            "problems": counts["open"] + counts["same-origin"] + counts["unknown"] + len(bridges)}


def render(result: dict) -> str:
    out = []
    c = result["counts"]
    out.append(f"frames: {len(result['frames'])} ({c['open']} open, {c['same-origin']} same-origin, "
               f"{c['unknown']} unknown, {c['sandboxed']} sandboxed)")
    for f in result["frames"]:
        cls = f" .{f['class']}" if f["class"] else ""
        sb = "" if f["sandbox"] is None else f" sandbox=\"{f['sandbox']}\""
        out.append(f"  {f['state']:<11} {f['file']}:{f['line']} {f['form']}{cls}{sb}")
    out.append(f"bridges: {len(result['bridges'])} (reachable from every frame in their WebView)")
    for b in result["bridges"]:
        out.append(f"  bridge      {b['file']}:{b['line']} {b['name']}")
    out.append("not runtime proof: the hostile-app browser run is the acceptance test (#133).")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("checkout", help="path to a wizard-ux checkout")
    ap.add_argument("--json", action="store_true", help="print one JSON object")
    args = ap.parse_args(argv)
    root = Path(args.checkout)
    if not (root / "web").is_dir():
        print(f"{root}: no web/ folder, not a wizard-ux checkout", file=sys.stderr)
        return 2
    result = census(root)
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 1 if result["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
