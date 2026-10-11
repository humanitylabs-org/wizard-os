#!/usr/bin/env python3
"""A real MCP streamable-HTTP server for testing `tools/wizard`. Stdlib only.

    python3 mcp_fixture.py --port 0 [--token-file F] [--sse] [--page-size N] [--ready-file F]

Behaves like a strict MCP server: requires initialize before other methods and hands out an
Mcp-Session-Id, enforces a bearer token when --token-file is given, can answer in SSE, and paginates
tools/list. Writes its bound port to --ready-file once listening.
"""
import argparse
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOLS = [
    {"name": "echo", "description": "Return the arguments exactly as received.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "n": {"type": "integer"},
                                                      "nested": {"type": "object"}}, "required": ["text"]}},
    {"name": "add", "description": "Add two numbers.",
     "inputSchema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                     "required": ["a", "b"], "additionalProperties": False},
     "annotations": {"readOnlyHint": True}},
    {"name": "fail", "description": "Always reports a tool error (isError).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "explode", "description": "Always answers with a JSON-RPC error.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "whoami", "description": "Report whether a bearer token arrived (never the token).",
     "inputSchema": {"type": "object", "properties": {}}},
]


def make_handler(cfg):
    sessions = set()
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, obj=None, headers=None, sse=False):
            if obj is None:
                body, ctype = b"", "application/json"
            elif sse:
                body = (": keepalive\n\nevent: message\ndata: " + json.dumps(obj) + "\n\n").encode()
                ctype = "text/event-stream"
            else:
                body, ctype = json.dumps(obj).encode(), "application/json"
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _authed(self):
            if not cfg["token"]:
                return True
            return self.headers.get("Authorization", "") == f"Bearer {cfg['token']}"

        def do_GET(self):
            if self.path == "/healthz":
                return self._send(200, {"ok": True})
            self._send(405, {"error": "POST /mcp"})

        def do_DELETE(self):
            with lock:
                sessions.discard(self.headers.get("Mcp-Session-Id"))
            self._send(200 if self._authed() else 401)

        def do_POST(self):
            if self.path != "/mcp":
                return self._send(404, {"error": "not found"})
            if not self._authed():
                return self._send(401, {"error": "unauthorized"}, {"WWW-Authenticate": "Bearer"})
            if "text/event-stream" not in self.headers.get("Accept", "") or \
                    "application/json" not in self.headers.get("Accept", ""):
                return self._send(406, {"error": "Accept must list application/json and text/event-stream"})
            msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            m, i, p = msg.get("method"), msg.get("id"), msg.get("params") or {}
            if m == "initialize":
                sid = secrets.token_hex(8)
                with lock:
                    sessions.add(sid)
                return self._send(200, {"jsonrpc": "2.0", "id": i, "result": {
                    "protocolVersion": p.get("protocolVersion"), "capabilities": {"tools": {}},
                    "serverInfo": {"name": "wizard-cli-fixture", "version": "1"}}},
                    {"Mcp-Session-Id": sid}, sse=cfg["sse"])
            sid = self.headers.get("Mcp-Session-Id")
            with lock:
                known = sid in sessions
            if not known:
                return self._send(400 if not sid else 404, {"error": "missing or unknown Mcp-Session-Id"})
            if not self.headers.get("MCP-Protocol-Version"):
                return self._send(400, {"error": "missing MCP-Protocol-Version"})
            if i is None:
                return self._send(202)
            if m == "tools/list":
                start = int(p.get("cursor") or 0)
                size = cfg["page_size"] or len(TOOLS)
                page = TOOLS[start:start + size]
                res = {"tools": page}
                if start + size < len(TOOLS):
                    res["nextCursor"] = str(start + size)
                return self._send(200, {"jsonrpc": "2.0", "id": i, "result": res}, sse=cfg["sse"])
            if m == "tools/call":
                n, a = p.get("name"), p.get("arguments")
                if n == "echo":
                    r = {"content": [{"type": "text", "text": json.dumps(a)}], "structuredContent": a}
                elif n == "add":
                    r = {"content": [{"type": "text", "text": json.dumps({"sum": a["a"] + a["b"]})}]}
                elif n == "fail":
                    r = {"content": [{"type": "text", "text": "the fixture failed on purpose"}], "isError": True}
                elif n == "whoami":
                    r = {"content": [{"type": "text", "text": "authenticated" if cfg["token"] else "open"}]}
                elif n == "explode":
                    return self._send(200, {"jsonrpc": "2.0", "id": i,
                                            "error": {"code": -32000, "message": "kaboom"}}, sse=cfg["sse"])
                else:
                    return self._send(200, {"jsonrpc": "2.0", "id": i,
                                            "error": {"code": -32602, "message": f"unknown tool {n}"}})
                return self._send(200, {"jsonrpc": "2.0", "id": i, "result": r}, sse=cfg["sse"])
            self._send(200, {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": f"no method {m}"}})

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--token-file")
    ap.add_argument("--sse", action="store_true")
    ap.add_argument("--page-size", type=int, default=0)
    ap.add_argument("--ready-file")
    a = ap.parse_args()
    token = open(a.token_file).read().strip() if a.token_file else None
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler({"token": token, "sse": a.sse,
                                                                   "page_size": a.page_size}))
    if a.ready_file:
        with open(a.ready_file + ".tmp", "w") as f:
            f.write(str(srv.server_address[1]))
        import os
        os.replace(a.ready_file + ".tmp", a.ready_file)
    srv.serve_forever()


if __name__ == "__main__":
    main()
