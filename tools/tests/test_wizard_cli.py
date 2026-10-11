"""End-to-end tests for tools/wizard. Real subprocesses, real HTTP, no mocks.

    python3 -m unittest discover -s tools/tests -v      (or: python3 -m pytest -q tools/tests)

Each test starts mcp_fixture.py servers on free loopback ports and writes a throwaway
WIZARD_OS_HOME with an apps.json pointing at them. Nothing on the box is read or written.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = HERE.parent / "wizard"
FIXTURE = HERE / "mcp_fixture.py"
INSTALL = HERE.parent / "install_wizard_cli.sh"
TOKEN = "fixture-" + os.urandom(12).hex()  # random per run, asserted never to leak


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Box:
    """A throwaway Wizard OS home plus running fixture servers."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wizard-cli-test-"))
        self.home = self.dir / "wizard-os"
        self.home.mkdir()
        self.procs = []

    def serve(self, *flags, token=False):
        ready = self.dir / f"ready-{len(self.procs)}"
        cmd = [sys.executable, str(FIXTURE), "--port", "0", "--ready-file", str(ready), *flags]
        if token:
            tf = self.dir / "token"
            tf.write_text(TOKEN)
            cmd += ["--token-file", str(tf)]
        self.procs.append(subprocess.Popen(cmd))
        for _ in range(200):
            if ready.exists():
                return int(ready.read_text())
            time.sleep(0.02)
        raise RuntimeError("fixture did not start")

    def registry(self, apps, raw=None):
        (self.home / "apps.json").write_text(raw if raw is not None else json.dumps(
            {"schema": 2, "updated_at": 1, "store": "test", "apps": apps, "slots": {}}))

    def secret(self, app_id, data):
        d = self.home / "secrets"
        d.mkdir(exist_ok=True, mode=0o700)
        (d / f"{app_id}.json").write_text(json.dumps(data))

    def run(self, *args, stdin=None, env=None):
        e = {k: v for k, v in os.environ.items() if not k.startswith("WIZARD_")}
        e.update({"WIZARD_OS_HOME": str(self.home), "WIZARD_TIMEOUT": "5"})
        e.update(env or {})
        p = subprocess.run([sys.executable, str(CLI), *args], input=stdin, capture_output=True, text=True,
                           env=e, timeout=60)
        self.last = p
        assert TOKEN not in p.stdout and TOKEN not in p.stderr, "token leaked to output"
        return p

    def jrun(self, *args, **kw):
        p = self.run(*args, "--json", **kw)
        try:
            return p.returncode, json.loads(p.stdout)
        except ValueError:
            raise AssertionError(f"stdout is not one JSON document: {p.stdout!r} stderr={p.stderr!r}")

    def close(self):
        for p in self.procs:
            p.terminate()
            p.wait(5)
        shutil.rmtree(self.dir, ignore_errors=True)


def app(app_id, port, **extra):
    a = {"id": app_id, "name": app_id.title(), "type": "service", "version": "1.0.0", "status": "running",
         "summary": f"{app_id} fixture", "provides": [], "uses": [], "needs": [], "view": None,
         "mcp": {"url": f"http://127.0.0.1:{port}/mcp", "internal": f"http://{app_id}:9/mcp",
                 "transport": "streamable-http"}}
    for k, v in extra.items():
        if k == "mcp" and v is not None:
            a["mcp"].update(v)
        else:
            a[k] = v
    return a


class WizardCLITest(unittest.TestCase):
    def setUp(self):
        self.box = Box()
        self.addCleanup(self.box.close)

    # ---- apps list
    def test_empty_registry(self):
        self.box.registry([])
        code, out = self.box.jrun("apps", "list")
        self.assertEqual((code, out["ok"], out["apps"]), (0, True, []))
        self.assertIn("No apps installed", self.box.run("apps", "list").stdout)

    def test_missing_registry(self):
        code, out = self.box.jrun("apps", "list")
        self.assertEqual((code, out["ok"], out["error"]["code"]), (3, False, "registry_not_found"))

    def test_corrupt_registry(self):
        self.box.registry(None, raw="{not json")
        code, out = self.box.jrun("apps", "list")
        self.assertEqual((code, out["error"]["code"]), (3, "registry_invalid"))

    def test_apps_list_redacts_and_flags(self):
        port = self.box.serve()
        self.box.registry([
            app("alpha", port, mcp={"url": f"http://user:{TOKEN}@127.0.0.1:{port}/mcp?key={TOKEN}",
                                    "auth": {"type": "bearer", "secret": "MCP_TOKEN"}}, _skill_src="/private"),
            app("beta", port, status="stopped"),
            app("viewer", port, type="view", mcp=None),
        ])
        code, out = self.box.jrun("apps", "list")
        self.assertEqual(code, 0)
        by = {a["id"]: a for a in out["apps"]}
        self.assertEqual(sorted(by), ["alpha", "beta", "viewer"])
        self.assertEqual(by["alpha"]["mcp"]["url"], f"http://127.0.0.1:{port}/mcp")
        self.assertEqual(by["alpha"]["mcp"]["auth"], "bearer")
        self.assertNotIn("_skill_src", by["alpha"])
        self.assertEqual([by[i]["callable"] for i in ("alpha", "beta", "viewer")], [True, False, False])

    def test_registry_flag_and_env_override(self):
        port = self.box.serve()
        other = self.box.dir / "elsewhere.json"
        other.write_text(json.dumps({"schema": 2, "apps": [app("gamma", port)]}))
        _, out = self.box.jrun("apps", "list", "--registry", str(other))
        self.assertEqual([a["id"] for a in out["apps"]], ["gamma"])
        _, out = self.box.jrun("--registry", str(other), "apps", "list")  # option before the subcommand
        self.assertEqual([a["id"] for a in out["apps"]], ["gamma"])
        _, out = self.box.jrun("apps", "list", env={"WIZARD_APPS_JSON": str(other)})
        self.assertEqual([a["id"] for a in out["apps"]], ["gamma"])

    # ---- tools
    def test_tools_lists_across_pages_over_sse(self):
        port = self.box.serve("--sse", "--page-size", "2")
        self.box.registry([app("alpha", port)])
        code, out = self.box.jrun("tools", "alpha")
        self.assertEqual(code, 0)
        self.assertEqual([t["name"] for t in out["tools"]], ["echo", "add", "fail", "explode", "whoami"])
        self.assertEqual(out["tools"][0]["inputSchema"]["required"], ["text"])
        code, out = self.box.jrun("tools", "alpha.add")
        self.assertEqual((code, out["tool"]["name"], out["tool"]["annotations"]), (0, "add", {"readOnlyHint": True}))
        human = self.box.run("tools", "alpha")
        self.assertEqual(human.returncode, 0)
        self.assertIn("add(a, b)  Add two numbers.", human.stdout)

    def test_missing_app(self):
        port = self.box.serve()
        self.box.registry([app("alpha", port)])
        for argv in (("tools", "ghost"), ("call", "ghost.echo", "{}")):
            code, out = self.box.jrun(*argv)
            self.assertEqual((code, out["error"]["code"], out["error"]["installed"]), (4, "app_not_found", ["alpha"]))
        p = self.box.run("tools", "ghost")
        self.assertEqual((p.returncode, p.stdout), (4, ""))
        self.assertIn("no installed app 'ghost'", p.stderr)

    def test_disabled_and_view_only_apps(self):
        port = self.box.serve()
        self.box.registry([app("off", port, status="stopped"), app("viewer", port, mcp=None)])
        code, out = self.box.jrun("tools", "off")
        self.assertEqual((code, out["error"]["code"], out["error"]["status"]), (5, "app_not_running", "stopped"))
        code, out = self.box.jrun("call", "viewer.echo", "{}")
        self.assertEqual((code, out["error"]["code"]), (5, "app_has_no_mcp"))

    def test_unsupported_transport(self):
        self.box.registry([app("legacy", 1, mcp={"transport": "sse"})])
        code, out = self.box.jrun("tools", "legacy")
        self.assertEqual((code, out["error"]["code"], out["error"]["transport"]), (5, "unsupported_transport", "sse"))

    def test_unavailable_endpoint(self):
        self.box.registry([app("gone", free_port())])
        code, out = self.box.jrun("tools", "gone")
        self.assertEqual((code, out["ok"], out["error"]["code"]), (7, False, "unreachable"))
        code, out = self.box.jrun("call", "gone.echo", '{"text": "x"}')
        self.assertEqual((code, out["error"]["code"]), (7, "unreachable"))

    def test_endpoint_internal(self):
        port = self.box.serve()
        self.box.registry([app("alpha", 1, mcp={"internal": f"http://127.0.0.1:{port}/mcp"})])
        code, _ = self.box.jrun("tools", "alpha")
        self.assertEqual(code, 7)  # host url points nowhere
        code, out = self.box.jrun("tools", "alpha", "--endpoint", "internal")
        self.assertEqual((code, len(out["tools"])), (0, 5))

    # ---- call
    def test_call_round_trips_arguments(self):
        port = self.box.serve()
        self.box.registry([app("alpha", port)])
        args = {"text": "héllo \"wizard\" ✨", "n": 3, "nested": {"list": [1, 2.5, None, True], "s": "x"}}
        code, out = self.box.jrun("call", "alpha.echo", json.dumps(args))
        self.assertEqual(code, 0)
        self.assertEqual((out["ok"], out["app"], out["tool"]), (True, "alpha", "echo"))
        self.assertEqual(out["arguments"], args)
        self.assertEqual(out["data"], args)                      # structuredContent
        self.assertEqual(json.loads(out["text"]), args)          # text block
        # stdin and @file carry the same arguments
        _, via_stdin = self.box.jrun("call", "alpha.echo", "-", stdin=json.dumps(args))
        self.assertEqual(via_stdin["data"], args)
        f = self.box.dir / "args.json"
        f.write_text(json.dumps(args))
        _, via_file = self.box.jrun("call", "alpha.echo", f"@{f}")
        self.assertEqual(via_file["data"], args)
        _, add = self.box.jrun("call", "alpha.add", '{"a": 2, "b": 40.5}')
        self.assertEqual(add["data"], {"sum": 42.5})             # single JSON text block is decoded
        self.assertEqual(self.box.run("call", "alpha.add", '{"a": 1, "b": 1}').stdout.strip(), '{"sum": 2}')

    def test_call_over_sse(self):
        port = self.box.serve("--sse")
        self.box.registry([app("alpha", port)])
        code, out = self.box.jrun("call", "alpha.echo", '{"text": "sse"}')
        self.assertEqual((code, out["data"]), (0, {"text": "sse"}))

    def test_unknown_tool(self):
        port = self.box.serve()
        self.box.registry([app("alpha", port)])
        code, out = self.box.jrun("call", "alpha.ech", "{}")
        self.assertEqual((code, out["error"]["code"]), (6, "tool_not_found"))
        self.assertIn("did you mean echo", out["error"]["message"])
        code, out = self.box.jrun("tools", "alpha.nope")
        self.assertEqual((code, out["error"]["code"]), (6, "tool_not_found"))

    def test_bad_json_and_bad_arguments(self):
        port = self.box.serve()
        self.box.registry([app("alpha", port)])
        for raw in ("{bad", "[1, 2]", "42"):
            code, out = self.box.jrun("call", "alpha.echo", raw)
            self.assertEqual((code, out["error"]["code"]), (2, "bad_arguments"), raw)
        code, out = self.box.jrun("call", "alpha.echo", f"@{self.box.dir}/missing.json")
        self.assertEqual((code, out["error"]["code"]), (2, "bad_arguments"))
        code, out = self.box.jrun("call", "alpha.echo", "{}")
        self.assertEqual((code, out["error"]["missing"]), (2, ["text"]))
        code, out = self.box.jrun("call", "alpha.add", '{"a": 1, "b": 2, "c": 3}')
        self.assertEqual((code, out["error"]["unexpected"]), (2, ["c"]))
        code, out = self.box.jrun("call", "alpha.add", '{"a": "1", "b": 2}')
        self.assertEqual((code, out["error"]["argument"]), (2, "a"))
        code, out = self.box.jrun("call", "alpha", "{}")
        self.assertEqual((code, out["error"]["code"]), (2, "usage"))
        code, out = self.box.jrun("frobnicate")
        self.assertEqual((code, out["error"]["code"]), (2, "usage"))

    def test_bad_json_needs_no_network(self):
        self.box.registry([app("gone", free_port())])
        code, out = self.box.jrun("call", "gone.echo", "{bad")
        self.assertEqual((code, out["error"]["code"]), (2, "bad_arguments"))

    def test_tool_errors(self):
        port = self.box.serve()
        self.box.registry([app("alpha", port)])
        code, out = self.box.jrun("call", "alpha.fail")
        self.assertEqual((code, out["error"]["code"]), (9, "tool_error"))
        self.assertIn("failed on purpose", out["error"]["message"])
        code, out = self.box.jrun("call", "alpha.explode")
        self.assertEqual((code, out["error"]["code"], out["error"]["rpc_code"]), (9, "tool_error", -32000))

    # ---- auth
    def test_auth_from_app_manager_secrets_file(self):
        port = self.box.serve(token=True)
        self.box.registry([app("locked", port, mcp={"auth": {"type": "bearer", "secret": "MCP_TOKEN"}})])
        code, out = self.box.jrun("call", "locked.whoami")
        self.assertEqual((code, out["error"]["code"]), (8, "auth_missing"))
        self.box.secret("locked", {"MCP_TOKEN": "wrong"})
        code, out = self.box.jrun("tools", "locked")
        self.assertEqual((code, out["error"]["code"], out["error"]["status"]), (8, "auth_failed", 401))
        self.box.secret("locked", {"MCP_TOKEN": TOKEN})
        code, out = self.box.jrun("call", "locked.whoami")
        self.assertEqual((code, out["text"]), (0, "authenticated"))

    def test_auth_from_env(self):
        port = self.box.serve(token=True)
        self.box.registry([app("locked-app", port)])
        code, out = self.box.jrun("tools", "locked-app")
        self.assertEqual((code, out["error"]["code"]), (8, "auth_failed"))
        self.assertIn("WIZARD_MCP_TOKEN_LOCKED_APP", out["error"]["message"])
        code, out = self.box.jrun("call", "locked-app.whoami", env={"WIZARD_MCP_TOKEN_LOCKED_APP": TOKEN})
        self.assertEqual((code, out["text"]), (0, "authenticated"))
        self.box.registry([app("locked-app", port, mcp={"auth": {"type": "bearer", "env": "MY_APP_TOKEN"}})])
        code, out = self.box.jrun("call", "locked-app.whoami")
        self.assertEqual((code, out["error"]["code"]), (8, "auth_missing"))
        code, out = self.box.jrun("call", "locked-app.whoami", env={"MY_APP_TOKEN": TOKEN})
        self.assertEqual((code, out["text"]), (0, "authenticated"))


@unittest.skipUnless(shutil.which("sh"), "needs sh")
class InstallTest(unittest.TestCase):
    """Installs into a fresh temporary HOME and PATH; never touches the real one."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wizard-cli-install-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.bin = self.dir / "home" / ".local" / "bin"
        self.env = {"HOME": str(self.dir / "home"), "PATH": f"{self.bin}:/usr/bin:/bin",
                    "PYTHON": sys.executable}

    def install(self, *args):
        return subprocess.run(["sh", str(INSTALL), *args], capture_output=True, text=True, env=self.env, timeout=60)

    def test_fresh_install_then_run(self):
        p = self.install()
        self.assertEqual(p.returncode, 0, p.stderr)
        w = self.bin / "wizard"
        self.assertTrue(os.access(w, os.X_OK))
        e = dict(self.env, WIZARD_OS_HOME=str(self.dir / "empty"))
        (self.dir / "empty").mkdir()
        (self.dir / "empty" / "apps.json").write_text('{"schema": 2, "apps": []}')
        r = subprocess.run(["wizard", "apps", "list", "--json"], capture_output=True, text=True, env=e)
        self.assertEqual((r.returncode, json.loads(r.stdout)["apps"]), (0, []))
        self.assertEqual(self.install().returncode, 0)  # re-install over our own copy is an upgrade

    def test_refuses_to_replace_foreign_wizard(self):
        self.bin.mkdir(parents=True)
        foreign = self.bin / "wizard"
        foreign.write_text("#!/bin/sh\necho someone else's wizard\n")
        before = foreign.read_text()
        p = self.install()
        self.assertEqual(p.returncode, 1)
        self.assertIn("not the Wizard OS CLI", p.stderr)
        self.assertEqual(foreign.read_text(), before)
        p = self.install("--name", "wizard-os")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue((self.bin / "wizard-os").is_file())
        self.assertEqual(foreign.read_text(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
