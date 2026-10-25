#!/usr/bin/env python3
"""Deterministic OpenAI-compatible model for the Hermes stable candidate test.

Stock Hermes talks to it as a `custom` provider, so every Hermes mechanism under test (sessions, runs, delegation,
compaction, cron, the database) is the candidate's own code while no account, key or paid inference is involved.
Replies are chosen by markers in the newest user message:

  HS-ECHO <n>        -> "ECHO <n>"
  HS-MARKDOWN <n>    -> a Markdown reply (heading, bold, list, code block, table, link) carrying <n>
  HS-DELEGATE <n>    -> a delegate_task tool call whose goal is "HS-CHILD <n>". A joined result is answered
                        "PARENT-SAW <child result>"; a background dispatch receipt "HELPER-DISPATCHED", and the
                        later follow-up turn (Wizard's follow-through) "PARENT-SAW <child result>"
  HS-CHILD <n>       -> (the helper's own request) "CHILD-RESULT <n>"
  HS-FACT <word>     -> "NOTED <word>"
  HS-FILL <n>        -> a filler reply of $FAKE_FILL_CHARS characters, so the next turn crosses Hermes' compaction
                        threshold
  HS-RECALL          -> "RECALL <every HS-FACT word visible in this request>", plus whether a compaction summary
                        was present and whether the original fact turns were still verbatim
  HS-CRON <n>        -> "CRON-FIRED <n>"

A summarisation request (Hermes' context compressor) is answered in the template it asks for, carrying every
HS-FACT word it was given into "Key Decisions" and "Critical Context". Every request is appended to
$FAKE_LOG (JSON lines) so the checks can prove what Hermes actually sent.
"""
import hashlib
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("FAKE_PORT", "18080"))
LOG = os.environ.get("FAKE_LOG", "/tmp/fake-model.jsonl")
MODEL = os.environ.get("FAKE_MODEL", "hs-fake")
CONTEXT = int(os.environ.get("FAKE_CONTEXT", "64000"))
FILL_CHARS = int(os.environ.get("FAKE_FILL_CHARS", "200000"))
LOCK = threading.Lock()
FACT = re.compile(r"HS-FACT ([A-Za-z0-9_-]+)")


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def all_text(messages):
    return "\n".join(text_of(m.get("content")) for m in messages)


def is_summary_request(messages):
    t = all_text(messages)
    return "TURNS TO SUMMARIZE" in t or "You are a summarization agent" in t


def summary_reply(messages):
    t = all_text(messages)
    facts = sorted(set(FACT.findall(t)))
    m = re.search(r"Use this exact structure:\s*(.*)", t, re.S)
    heads = re.findall(r"^## [^\n]+", m.group(1), re.M) if m else []
    heads = heads or ["## Goal", "## Key Decisions", "## Critical Context"]
    body = []
    for h in heads:
        body.append(h)
        if "Decision" in h or "Critical" in h:
            body.append("- The owner asked to remember: " + ", ".join("HS-SUMMARY-FACT " + f for f in facts))
        elif "Goal" in h:
            body.append("Acceptance conversation about remembered facts (synthetic).")
        else:
            body.append("None.")
        body.append("")
    return "\n".join(body).strip()


def last_user(messages):
    for m in reversed(messages):
        if m.get("role") == "user":
            return text_of(m.get("content"))
    return ""


def decide(req):
    """Return (content, tool_calls)."""
    messages = req.get("messages") or []
    if is_summary_request(messages):
        return summary_reply(messages), None
    user = last_user(messages)
    tail = messages[-1] if messages else {}
    if tail.get("role") == "tool":
        result = text_of(tail.get("content"))
        child = re.search(r"CHILD-RESULT [A-Za-z0-9_-]+", result)
        # Stock Hermes runs the helper in the background for API sessions and returns a dispatch receipt.
        return ("PARENT-SAW " + child.group(0)) if child else "HELPER-DISPATCHED", None
    if user.startswith("[Wizard follow-through]") or "ASYNC DELEGATION BATCH COMPLETE" in user:
        found = re.findall(r"CHILD-RESULT [A-Za-z0-9_-]+", all_text(messages))
        return ("PARENT-SAW " + found[-1]) if found else "PARENT-SAW nothing", None
    if m := re.search(r"HS-CHILD ([A-Za-z0-9_-]+)", user):
        return "CHILD-RESULT " + m.group(1), None
    if m := re.search(r"HS-DELEGATE ([A-Za-z0-9_-]+)", user):
        call = {"id": "call_" + m.group(1)[:20], "type": "function",
                "function": {"name": "delegate_task", "arguments": json.dumps({
                    "goal": "HS-CHILD " + m.group(1) + ": reply with the child marker only.",
                    "context": "Synthetic acceptance helper. Answer in one line."})}}
        return "", [call]
    if m := re.search(r"HS-ECHO ([A-Za-z0-9_-]+)", user):
        return "ECHO " + m.group(1), None
    if m := re.search(r"HS-MARKDOWN ([A-Za-z0-9_-]+)", user):
        n = m.group(1)
        return ("## Result " + n + "\n\nThis is **bold " + n + "** and *italic* text.\n\n- first item\n- second item\n\n"
                "```python\nprint('code " + n + "')\n```\n\n| Column | Value |\n|---|---|\n| marker | " + n + " |\n\n"
                "[a link](https://example.com/" + n + ")"), None
    if m := re.search(r"HS-FACT ([A-Za-z0-9_-]+)", user):
        return "NOTED " + m.group(1), None
    if m := re.search(r"HS-FILL ([A-Za-z0-9_-]+)", user):
        # Distinct lines: Hermes cuts a stream that turns into a repetition loop, so the filler must not repeat.
        lines, i = ["FILLED " + m.group(1)], 0
        while sum(len(x) + 1 for x in lines) < FILL_CHARS:
            lines.append("Note %d: %s" % (i, hashlib.sha256(str(i).encode()).hexdigest()))
            i += 1
        return "\n".join(lines), None
    if "HS-RECALL" in user:
        everything = all_text(messages)
        facts = sorted(set(re.findall(r"HS-SUMMARY-FACT ([A-Za-z0-9_-]+)", everything)) |
                       set(FACT.findall(everything.replace(user, ""))))
        summary = "CONTEXT COMPACTION" in everything or "HS-SUMMARY-FACT" in everything
        verbatim = any(m.get("role") == "user" and FACT.search(text_of(m.get("content"))) for m in messages)
        return ("RECALL " + " ".join(facts) + " | summary=" + str(summary).lower() +
                " | verbatim_fact_turns=" + str(verbatim).lower()), None
    if m := re.search(r"HS-CRON ([A-Za-z0-9_-]+)", user):
        return "CRON-FIRED " + m.group(1), None
    if re.search(r"\btitle\b", all_text(messages[:2]), re.I) and len(messages) <= 3:
        return "Acceptance thread", None
    return "OK", None


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": MODEL, "object": "model", "owned_by": "acceptance", "context_length": CONTEXT}]})
        if self.path.startswith("/health"):
            return self._json(200, {"ok": True})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        req = json.loads(self.rfile.read(n) or b"{}")
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._json(404, {"error": {"message": "only chat/completions"}})
        content, calls = decide(req)
        # Report usage the way a real provider would (about four characters per token), so Hermes' own
        # context accounting and compaction decisions see a coherent conversation size.
        ptok = max(200, len(json.dumps(req.get("messages") or [])) // 4 + len(json.dumps(req.get("tools") or [])) // 4)
        with LOCK, open(LOG, "a") as f:
            f.write(json.dumps({"t": time.time(), "request": req, "reply": content, "tool_calls": calls,
                                "prompt_tokens": ptok}) + "\n")
        usage = {"prompt_tokens": ptok, "completion_tokens": 20, "total_tokens": ptok + 20}
        cid = "chatcmpl-%d" % int(time.time() * 1000)
        finish = "tool_calls" if calls else "stop"
        if not req.get("stream"):
            msg = {"role": "assistant", "content": content or None}
            if calls:
                msg["tool_calls"] = calls
            return self._json(200, {"id": cid, "object": "chat.completion", "created": int(time.time()),
                                    "model": MODEL, "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                                    "usage": usage})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def ev(delta, fin=None, use=None):
            chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL,
                     "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
            if use:
                chunk["usage"] = use
            self.wfile.write(b"data: " + json.dumps(chunk).encode() + b"\n\n")
            self.wfile.flush()

        ev({"role": "assistant", "content": ""})
        if content:
            for i in range(0, len(content), 400):
                ev({"content": content[i:i + 400]})
        if calls:
            for k, c in enumerate(calls):
                ev({"tool_calls": [{"index": k, "id": c["id"], "type": "function",
                                    "function": {"name": c["function"]["name"], "arguments": c["function"]["arguments"]}}]})
        ev({}, finish)
        if (req.get("stream_options") or {}).get("include_usage"):
            self.wfile.write(b"data: " + json.dumps({"id": cid, "object": "chat.completion.chunk", "model": MODEL,
                                                    "choices": [], "usage": usage}).encode() + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    print("fake model on :%d, log %s" % (PORT, LOG), file=sys.stderr, flush=True)
    srv.serve_forever()
