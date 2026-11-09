#!/usr/bin/env python3
"""Weak-model gate for the WizardOS agent bridge (spec/AGENT_BRIDGE.md, "Proof").

Sends eight plain, job-worded requests to a real Hermes (fresh session each) and checks the FIRST
app-relevant tool call. Pass = the expected `<app>__<tool>` first in at least 7 of 8, with zero
file-system searches for app details. Also reports tokens per session (input + output, summed over
the turn) so a box with every default app can be compared with an empty one (spec: within 10%).
Run it on the box, as the user whose Hermes is linked:

    python3 agent_bridge_gate.py --model deepseek-v4-1-flash --provider custom --out gate.json
    python3 agent_bridge_gate.py --tokens-only --out empty.json     # on a box with no apps

App-relevant = any tool call except the neutral ones below (loading the wizard-job / app skill first
is what the kernel asks for; tool_search/tool_describe are Hermes' own bridge). `tool_call` is unwrapped to the
tool it invokes. A file-system search for app details = a terminal/file/code tool whose arguments
mention apps.json, .wizard-os, wam, an MCP URL or an app skill path. Arguments are not stored in the
report, only tool names, so the evidence never carries conversation content.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time

REQUESTS = [
    ("time", "what time is it on my server?", ["hello_wizard__wizard_time"]),
    ("apps", "what apps do I have?", ["wizard_apps"]),
    ("transcribe", "transcribe the recording Inbox/2026-10-11/standup.wav from my files", # Checking the engine first is legitimate app use (its skill says to); both count.
     ["transcriber__transcribe", "transcriber__transcriber_status"]),
    ("stt-check", "is speech to text working on this box?", ["transcriber__transcriber_status"]),
    ("read-page", "open https://example.com in the browser and tell me what the page says", ["browser__read_page"]),
    ("screenshot", "take a screenshot of https://example.com", ["browser__screenshot"]),
    ("secret", "I need to give you my GitHub token without pasting it in chat. Set that up.",
     # Secret Drop's own skill fetches its client first (secret_drop_info says where), so both count.
     ["secret_drop__request_secret", "secret_drop__secret_drop_info"]),
    ("claude", "is my Claude subscription connected on this box?", ["wizard_ai_accounts__ai_accounts_status"]),
]
PROBE = "Reply with just the word ok. Use no tools."
NEUTRAL = {"skill_view", "skills_list", "tool_search", "tool_describe", "todo", "todo_list", "clarify", "memory"}
FS_TOOLS = {"terminal", "search_files", "read_file", "execute_code", "process", "shell_exec", "browser_exec"}
# The owner's Files root (~/runtipi/media) is the owner's data, not app internals: looking at the file
# they named is allowed. Everything else under runtipi is an app detail.
APP_DETAIL = re.compile(r"apps\.json|\.wizard-os|\bwam\b|/mcp\b|skills/[a-z0-9-]+/SKILL\.md|wizard-app-manager|runtipi(?!/media)", re.I)


def short(name: str) -> str:
    """mcp__wizard__hello_wizard__wizard_time -> hello_wizard__wizard_time."""
    return name.split("mcp__wizard__", 1)[1] if name.startswith("mcp__wizard__") else name


def run_one(hermes: str, prompt: str, model: str, provider: str, timeout: int, max_turns: int) -> dict:
    cmd = [hermes, "chat", "-q", prompt, "--format", "stream-json", "--yolo", "--max-turns", str(max_turns)]
    if model:
        cmd += ["-m", model]
    if provider:
        cmd += ["--provider", provider]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = proc.stdout
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    calls, result, tokens = [], {}, {}
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "tool_use":
            name, args = ev.get("name") or "", ev.get("input") if isinstance(ev.get("input"), dict) else {}
            if name == "tool_call":  # Hermes' deferred-tool bridge: score the tool it actually invokes
                inner = (args.get("calls") or [{}]) if isinstance(args.get("calls"), list) else [args]
                for c in inner:
                    calls.append({"name": short(str(c.get("name") or "")), "via": "tool_call",
                                  "app_detail_search": False})
                continue
            calls.append({"name": short(name), "via": "direct",
                          "app_detail_search": name in FS_TOOLS and bool(APP_DETAIL.search(json.dumps(args))),
                          **({"skill": str(args.get("name") or "")[:80]} if name == "skill_view" else {})})
        elif ev.get("type") == "tool_result" and calls:
            calls[-1].setdefault("error", bool(ev.get("is_error")))
        elif ev.get("type") == "result":
            result = {"exit_code": ev.get("exit_code"), "error": str(ev.get("error") or "")[:200]}
            tokens = ev.get("tokens") if isinstance(ev.get("tokens"), dict) else {}
    return {"calls": calls, "result": result, "tokens": tokens, "seconds": round(time.time() - started, 1)}


def prompt_tokens(tokens: dict) -> int:
    """Whole prompt size: fresh input plus cached reads/writes (providers split them differently)."""
    return sum(int(tokens.get(k) or 0) for k in ("input", "cache_read", "cache_write"))


def score(run: dict, expected: list[str]) -> dict:
    relevant = [c for c in run["calls"] if c["name"] not in NEUTRAL]
    first = relevant[0]["name"] if relevant else ""
    searches = sum(1 for c in run["calls"] if c["app_detail_search"])
    skills = [c.get("skill", "") for c in run["calls"] if c["name"] == "skill_view" and c.get("skill")]
    return {"first_app_call": first, "pass": first in expected and searches == 0, "app_detail_searches": searches,
            "skills_loaded": skills, "pointer_loaded": any(s.startswith("wizard-job-") for s in skills),
            "tools": [c["name"] + ("" if c["via"] == "direct" else " (via tool_call)") for c in run["calls"]]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hermes", default="hermes")
    ap.add_argument("--model", default="")
    ap.add_argument("--provider", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--max-turns", type=int, default=6)  # pointer + app skill + describe + call
    ap.add_argument("--only", default="", help="comma-separated request ids")
    ap.add_argument("--out", default="")
    ap.add_argument("--tokens-only", action="store_true",
                    help="measure session tokens only (for the empty-box baseline); no pass/fail")
    ns = ap.parse_args()
    # Per-session fixed cost: a neutral one-word reply, so the input tokens are system prompt + tool
    # schemas only. Compare a box with every default app against an empty one (spec: within 10%).
    probes = [prompt_tokens(run_one(ns.hermes, PROBE, ns.model, ns.provider, ns.timeout, 1)["tokens"]) for _ in range(2)]
    session_tokens = min(t for t in probes if t) if any(probes) else 0
    print(f"session cost: {session_tokens} prompt tokens (input + cached) for a one-word reply", flush=True)
    rows = []
    for rid, prompt, expected in REQUESTS:
        if ns.tokens_only:
            break
        if ns.only and rid not in ns.only.split(","):
            continue
        run = run_one(ns.hermes, prompt, ns.model, ns.provider, ns.timeout, ns.max_turns)
        row = {"id": rid, "request": prompt, "expected": expected, **score(run, expected),
               "tokens": run["tokens"], "seconds": run["seconds"], "run": run["result"]}
        rows.append(row)
        mark = "PASS" if row["pass"] else "FAIL"
        print(f"{mark}  {rid:<11} first={row['first_app_call'] or '-':<45} searches={row['app_detail_searches']}  "
              f"pointer={'y' if row['pointer_loaded'] else 'n'}  prompt={prompt_tokens(row['tokens'])}  {row['seconds']}s",
              flush=True)
    passed = sum(r["pass"] for r in rows)
    searches = sum(r["app_detail_searches"] for r in rows)
    pointers = sum(r["pointer_loaded"] for r in rows)
    first_turn = [prompt_tokens(r["tokens"]) for r in rows if r["tokens"]]
    ok = passed >= max(1, len(rows) - 1) and searches == 0
    report = {"gate": "agent-bridge", "model": ns.model or "(config default)", "label": ns.label,
              "provider": ns.provider or "(config default)", "passed": passed, "total": len(rows),
              "app_detail_searches": searches, "pointer_skill_loaded": pointers,
              "session_input_tokens": session_tokens,
              "input_tokens_per_request_mean": round(sum(first_turn) / len(first_turn)) if first_turn else 0,
              "result": "TOKENS" if ns.tokens_only else ("PASS" if ok else "FAIL"), "rows": rows,
              "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    print(f"{report['result']}: {passed}/{len(rows)} first calls right, {searches} app-detail file searches, "
          f"{pointers} loaded a wizard-job skill, session cost {session_tokens} prompt tokens "
          f"({report['model']})")
    if ns.out:
        with open(ns.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return 0 if ok or ns.tokens_only else 1


if __name__ == "__main__":
    sys.exit(main())
