"""Contract-faithful fake AI connection apps for one acceptance state. Runs inside the acceptance VM.

usage: python3 fakes.py <state> <fake_provider.py dir> <models dir> <ports.json> <requests.jsonl>

Uses the Router's own test fixture (wizard-app-store images/wizard-connection-router/tests/fake_provider.py) so the
fakes speak exactly what the Router's unit suite proves: wizard.ai-connection/2 status plus /api/infer SSE with an
effective-model done event. Model lists are the real ones the shipped provider apps publish (wizard-claude
models.json, wizard-os Hermes plugin chatgpt.json). No credentials, no network beyond loopback.
"""
import json
import signal
import sys
from pathlib import Path

state, fixture_dir, models_dir, ports_file, log_file = sys.argv[1:6]
sys.path.insert(0, fixture_dir)
from fake_provider import FakeProvider  # noqa: E402

CONNECTED = {
    "claude-only": {"wizard-claude"},
    "chatgpt-only": {"wizard-chatgpt"},
    "both": {"wizard-claude", "wizard-chatgpt"},
    "neither": set(),
}[state]
SIGNED_OUT = {"wizard-claude": "Claude is not connected. Open the Claude app and press Connect.",
              "wizard-chatgpt": "ChatGPT is not connected. Open the ChatGPT app and press Connect."}


class Log(list):
    """Append each provider request to a JSONL file, without bodies' grant headers."""
    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def append(self, item):
        super().append(item)
        body = item["body"].decode("utf-8", "replace")
        try:
            model = json.loads(body).get("model") if body else None
        except ValueError:
            model = None
        with open(log_file, "a") as f:
            f.write(json.dumps({"provider": self.provider, "method": item["method"], "path": item["path"],
                                "model": model}) + "\n")


fakes = {}
for pid, models_file in (("wizard-claude", "claude-models.json"), ("wizard-chatgpt", "chatgpt-models.json")):
    models = json.loads((Path(models_dir) / models_file).read_text())["models"]
    f = FakeProvider(pid, models)
    f.requests = Log(pid)
    if pid not in CONNECTED:
        f.status = "not_connected"
        f.error = {"code": "signed_out", "message": SIGNED_OUT[pid]}
    fakes[pid] = f

Path(ports_file).write_text(json.dumps({pid: f.url for pid, f in fakes.items()}))
print("FAKES READY", state, {pid: (f.url, f.status) for pid, f in fakes.items()}, flush=True)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
signal.pause()
