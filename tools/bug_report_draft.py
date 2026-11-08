#!/usr/bin/env python3
"""Turn an owner's own words plus a `wizard report` into a GitHub issue draft (goal wizard-os #417).

    wizard report > report.json
    python3 tools/bug_report_draft.py --words "The chat froze after I sent a voice note" --report report.json
    python3 tools/bug_report_draft.py --words-file transcript.txt --report report.json --json

Goal #417 is: a broken thing becomes a voice note in the app, which turns into a GitHub issue with
diagnostics attached, without the reporter needing a GitHub account, after the owner approves what is
sent. This tool is only the middle step: from the voice note's transcript and the box's diagnostics to
the exact text an issue would carry, so the owner (or a maintainer) can read it before anything leaves.

It sends nothing. It opens no network connection, creates no relay or endpoint, and holds no credential.
Nothing runs it automatically. The account-free relay is a separate, not-yet-approved piece of #417.

Two privacy guards, both deliberate:
- Diagnostics: the report is re-projected onto the `wizard-report-v1` allowlist (wizard-app-manager
  `wizard-cli/wizard` `cmd_report`, spec/LAUNCH_AUDITS_8_9.md). Every key or value outside the allowlist
  is dropped and counted, never copied, so a stale, edited or newer report cannot widen what is posted.
  A report with another schema is refused (exit 2).
- Owner's words: emails, URLs, IP and tailnet addresses, home-directory paths and token-like strings are
  replaced with `[removed: <kind>]` and counted. The owner still reviews the result; this is not a
  promise that free text is clean.

Exit 0 = draft printed, 2 = unusable input (missing words, unreadable or unsupported report).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "wizard-report-v1"
MAX_WORDS = 4000
TITLE_MAX = 80
LABELS = ["bug", "from: in-app report"]

UNITS = ("wizard-app-manager-api.service", "wizard-troubleshooter.service", "wizard-guardian.timer")
COMPONENTS = ("wizard-app-manager", "wizard-agent-service", "wizard-ux", "wizard-troubleshooter")
SERVICE_STATES = ("active", "inactive", "failed", "activating", "deactivating", "unavailable")
ERROR_CLASSES = ("timeout", "connection_refused", "permission_denied", "out_of_memory", "error")
OS_IDS = ("ubuntu", "debian", "fedora", "arch", "alpine", "other")
RELEASE_STATUS = ("pinned", "drift", "mismatch", "install-failed", "unpinned", "unavailable")
PRIVACY_NOTE = "allowlisted-identities-and-enums-only; no raw logs or content; not uploaded"

VERSION_RE = r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]{1,40})?"
PATTERNS = {"version": VERSION_RE, "commit": r"[a-f0-9]{40}", "digest": r"sha256:[a-f0-9]{64}",
            "python": r"\d+\.\d+\.\d+[a-z0-9]{0,8}", "os_version": r"[0-9.]{1,12}"}

# Order matters: the specific shapes go first so a URL with credentials is removed as one URL.
REDACTIONS = (
    ("url", re.compile(r"\b(?:[a-z][a-z0-9+.-]*://|www\.)[^\s<>\"']+", re.I)),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("tailnet address", re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.ts\.net\b", re.I)),
    ("ip address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b|\b(?:[0-9a-f]{1,4}:){3,7}[0-9a-f]{1,4}\b", re.I)),
    ("home path", re.compile(r"(?:/home/|/Users/|/root\b|~/)[^\s]*")),
    ("token", re.compile(r"\b(?:sk-|ghp_|gho_|ghs_|github_pat_|xox[abpr]-|AKIA|glpat-|tskey-)[\w-]{6,}")),
    ("token", re.compile(r"\b(?=[A-Za-z0-9_\-+/=]*\d)(?=[A-Za-z0-9_\-+/=]*[A-Za-z])[A-Za-z0-9_\-+/=]{24,}")),
)


def _match(value, kind):
    return value if isinstance(value, str) and re.fullmatch(PATTERNS[kind], value) else None


def _enum(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100000 else None


class _Projector:
    """Copies only allowlisted fields; counts everything it refuses."""

    def __init__(self):
        self.dropped = 0

    def keep(self, value):
        if value is None:
            self.dropped += 1
        return value

    def extra(self, given: dict, allowed) -> None:
        self.dropped += sum(1 for k in given if k not in allowed)

    def dict_(self, value) -> dict:
        if isinstance(value, dict):
            return value
        self.dropped += value is not None
        return {}


def project_report(report: object) -> tuple[dict, int]:
    """Re-project a wizard-report-v1 document onto its allowlist. Returns (clean, dropped_count)."""
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} document")
    p = _Projector()
    top = ("schema", "cli_version", "python_version", "os", "release", "expected_pins", "services",
           "recent_errors", "updates", "privacy")
    p.extra(report, top)
    out = {"schema": SCHEMA,
           "cli_version": _match(report.get("cli_version"), "version"),
           "python_version": _match(report.get("python_version"), "python")}
    p.dropped += sum(1 for k in ("cli_version", "python_version") if report.get(k) is not None and out[k] is None)

    os_ = p.dict_(report.get("os"))
    p.extra(os_, ("id", "version"))
    out["os"] = {"id": _enum(os_.get("id"), OS_IDS), "version": _match(os_.get("version"), "os_version")}

    rel = p.dict_(report.get("release"))
    p.extra(rel, ("version", "status", "mismatches", "identities"))
    identities = []
    raw_ids = rel.get("identities") if isinstance(rel.get("identities"), list) else []
    for row in raw_ids[:128]:
        if not isinstance(row, dict) or row.get("kind") not in ("commit", "digest"):
            p.dropped += 1
            continue
        p.extra(row, ("kind", "expected", "observed", "ok"))
        kind = row["kind"]
        identities.append({"kind": kind, "expected": _match(row.get("expected"), kind),
                           "observed": _match(row.get("observed"), kind), "ok": row.get("ok") is True})
    p.dropped += max(0, len(raw_ids) - 128)
    out["release"] = {"version": _match(rel.get("version"), "version"),
                      "status": _enum(rel.get("status"), RELEASE_STATUS) or "unavailable",
                      "mismatches": _count(rel.get("mismatches")), "identities": identities}

    pins = p.dict_(report.get("expected_pins"))
    p.extra(pins, COMPONENTS)
    out["expected_pins"] = {}
    for key in COMPONENTS:
        row = p.dict_(pins.get(key))
        p.extra(row, ("commit", "digest"))
        out["expected_pins"][key] = {"commit": _match(row.get("commit"), "commit"),
                                     "digest": _match(row.get("digest"), "digest")}

    services = p.dict_(report.get("services"))
    p.extra(services, UNITS)
    out["services"] = {u: _enum(services.get(u), SERVICE_STATES) or "unavailable" for u in UNITS}

    errors = p.dict_(report.get("recent_errors"))
    p.extra(errors, UNITS)
    out["recent_errors"] = {}
    for unit in UNITS:
        row = p.dict_(errors.get(unit))
        p.extra(row, ("available", "classes"))
        classes = p.dict_(row.get("classes"))
        p.extra(classes, ERROR_CLASSES)
        out["recent_errors"][unit] = {"available": row.get("available") is True,
                                      "classes": {c: min(100, _count(classes.get(c)) or 0) for c in ERROR_CLASSES}}

    upd = p.dict_(report.get("updates"))
    p.extra(upd, ("mode", "channel"))
    out["updates"] = {"mode": _enum(upd.get("mode"), ("ask", "auto")) or "ask",
                      "channel": _enum(upd.get("channel"), ("stable", "latest")) or "stable"}
    out["privacy"] = PRIVACY_NOTE
    return out, p.dropped


def scrub_words(text: str) -> tuple[str, dict]:
    """Remove obvious private shapes from the owner's words. Returns (text, {kind: count})."""
    counts: dict[str, int] = {}
    text = text.replace("\r\n", "\n").strip()[:MAX_WORDS]
    for kind, rx in REDACTIONS:
        text, n = rx.subn(f"[removed: {kind}]", text)
        if n:
            counts[kind] = counts.get(kind, 0) + n
    return text, counts


def make_title(words: str) -> str:
    first = re.split(r"(?<=[.!?])\s|\n", words.strip(), maxsplit=1)[0].strip()
    if len(first) > TITLE_MAX:
        first = first[:TITLE_MAX - 1].rstrip() + "…"
    return f"In-app report: {first or 'something is broken'}"


def build_draft(words: str, report: dict | None) -> dict:
    clean_words, redactions = scrub_words(words)
    if not clean_words:
        raise ValueError("the owner's words are empty")
    quoted = "\n".join(f"> {line}" if line else ">" for line in clean_words.splitlines())
    parts = ["## What happened (the owner's words)", "", quoted, ""]
    dropped = 0
    if report is not None:
        clean, dropped = project_report(report)
        rel = clean["release"]
        down = [u for u, s in clean["services"].items() if s != "active"]
        parts += ["## Box at the time", "",
                  f"- Release: {rel['version'] or 'unknown'} ({rel['status']}, {rel['mismatches'] or 0} pin mismatches)",
                  f"- Updates: {clean['updates']['channel']}, {clean['updates']['mode']}",
                  f"- Services not active: {', '.join(down) if down else 'none'}", "",
                  "<details><summary>Diagnostics (wizard report, wizard-report-v1)</summary>", "",
                  "```json", json.dumps(clean, indent=2, sort_keys=True), "```", "", "</details>", ""]
    else:
        parts += ["## Box at the time", "", "No diagnostics attached.", ""]
    parts += ["---", "Drafted inside Wizard from a voice note. Nothing is sent until the owner approves this text."]
    return {"title": make_title(clean_words), "body": "\n".join(parts), "labels": list(LABELS),
            "redacted_from_words": redactions, "dropped_from_report": dropped, "sent": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Draft a GitHub issue from an owner's words and a wizard report. Sends nothing.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--words", help="the owner's words (the voice note transcript)")
    src.add_argument("--words-file", type=Path, help="file holding the owner's words")
    ap.add_argument("--report", type=Path, help="a `wizard report` JSON file (optional)")
    ap.add_argument("--json", action="store_true", help="print the whole draft as one JSON object")
    ns = ap.parse_args(argv)
    try:
        words = ns.words if ns.words is not None else ns.words_file.read_text(encoding="utf-8")
        report = json.loads(ns.report.read_text(encoding="utf-8")) if ns.report else None
        draft = build_draft(words, report)
    except (OSError, UnicodeError, ValueError) as e:
        print(f"bug_report_draft: {e}", file=sys.stderr)
        return 2
    if ns.json:
        print(json.dumps(draft, indent=2, ensure_ascii=False))
    else:
        print(f"Title: {draft['title']}\nLabels: {', '.join(draft['labels'])}\n\n{draft['body']}")
        notes = [f"{n} {k}" for k, n in draft["redacted_from_words"].items()]
        if notes:
            print(f"\nRemoved from the owner's words: {', '.join(notes)}", file=sys.stderr)
        if draft["dropped_from_report"]:
            print(f"Dropped {draft['dropped_from_report']} field(s) outside {SCHEMA}", file=sys.stderr)
        print("Not sent.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
