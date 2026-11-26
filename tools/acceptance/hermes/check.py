#!/usr/bin/env python3
"""Wizard stable checks for one Hermes candidate, run as root inside a fresh acceptance VM.

The box is the stock Wizard shape reduced to what the checks need: the candidate's official Hermes image (stock,
unmodified, gateway mode), the pinned Wizard Agent Service in front of it, and a deterministic fake model
(fake_model.py) so no account or paid inference is involved. Every request goes through the Agent Service's
public routes, the same ones the Wizard shell uses.

The box starts on --from-image (today's pin), gets a seed thread, is updated to --image, runs the checks, and is
rolled back to --from-image at the end. Results go to <out>/results.json; evidence files sit next to it.

    check.py --image <ref> --from-image <ref> --was-image <ref> --ux-image <ref> --fake-image <ref> --out <dir>
"""
import argparse
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

NET = "hs"
HERMES, WAS, FAKE = "hs-hermes", "hs-was", "hs-fake"
WAS_URL = "http://127.0.0.1:8787"
HERMES_URL = "http://127.0.0.1:8642"
SETTLE_TURNS = 3  # ordinary turns the compaction check allows before the compacted history must reach the model
CONFIG = """model:
  provider: custom
  base_url: http://hs-fake:18080/v1
  api_key: acceptance-fake-model
  default: hs-fake
  context_length: 64000
compression:
  enabled: true
"""


class Box:
    def __init__(self, a):
        self.a = a
        self.out = Path(a.out)
        self.ev = self.out / "evidence"
        self.ev.mkdir(parents=True, exist_ok=True)
        self.root = Path("/var/lib/hermes-stable")
        self.data = self.root / "data"
        self.fake_dir = self.root / "fake"
        self.key = secrets.token_hex(24)
        self.results = []
        self.observations = []
        self.log = open(self.ev / "harness.log", "a")

    # ---------- plumbing ----------
    def say(self, *msg):
        line = time.strftime("%H:%M:%S ") + " ".join(str(m) for m in msg)
        print(line, flush=True)
        self.log.write(line + "\n")
        self.log.flush()

    def sh(self, *cmd, check=True, timeout=600):
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if check and p.returncode:
            raise RuntimeError(f"{' '.join(cmd[:4])}... exited {p.returncode}: {p.stderr[-800:]}")
        return p.stdout

    def http(self, method, path, body=None, base=WAS_URL, headers=None, timeout=120):
        h = {"content-type": "application/json", **(headers or {})}
        if base == HERMES_URL:
            h["Authorization"] = "Bearer " + self.key
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, method=method, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw.strip().startswith(("{", "[")) else raw)
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, raw
        except Exception as e:  # connection refused while restarting
            return 0, str(e)

    def wait(self, what, fn, timeout=180, every=2):
        end = time.time() + timeout
        last = None
        while time.time() < end:
            try:
                last = fn()
                if last:
                    return last
            except Exception as e:
                last = e
            time.sleep(every)
        raise RuntimeError(f"timed out waiting for {what}: {last}")

    def record(self, check, ok, detail, evidence=()):
        self.results.append({"check": check, "pass": bool(ok), "detail": detail,
                             "evidence": [str(Path(e).relative_to(self.out)) for e in evidence]})
        self.say("PASS" if ok else "FAIL", check, "-", detail)
        (self.out / "results.json").write_text(json.dumps(self.meta | {"checks": self.results, "observations": self.observations}, indent=2))

    def dump(self, name, obj):
        p = self.ev / name
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str))
        return p

    # ---------- containers ----------
    def setup(self):
        for c in (HERMES, WAS, FAKE):
            self.sh("docker", "rm", "-f", c, check=False)
        self.sh("docker", "network", "rm", NET, check=False)
        shutil.rmtree(self.root, ignore_errors=True)
        self.data.mkdir(parents=True)
        self.fake_dir.mkdir(parents=True)
        (self.root / "was").mkdir()
        shutil.copy(Path(__file__).with_name("fake_model.py"), self.fake_dir / "fake_model.py")
        (self.data / "config.yaml").write_text(CONFIG)
        for p in (self.data, self.root / "was"):
            self.sh("chown", "-R", "1000:1000", str(p))
        self.sh("docker", "network", "create", NET)
        self.sh("docker", "run", "-d", "--name", FAKE, "--network", NET, "-v", f"{self.fake_dir}:/fake",
                "-e", "FAKE_LOG=/fake/requests.jsonl", self.a.fake_image, "python", "/fake/fake_model.py")

    def start_hermes(self, image):
        self.sh("docker", "rm", "-f", HERMES, check=False)
        self.sh("docker", "run", "-d", "--name", HERMES, "--network", NET, "-p", "127.0.0.1:8642:8642",
                "-v", f"{self.data}:/opt/data", "-e", "HERMES_UID=1000", "-e", "HERMES_GID=1000",
                "-e", "API_SERVER_KEY=" + self.key, "-e", "API_SERVER_HOST=0.0.0.0", "-e", "API_SERVER_PORT=8642",
                image, "gateway", "run")
        self.wait("Hermes health", lambda: self.http("GET", "/health", base=HERMES_URL)[0] == 200, timeout=240)
        self.wait("Agent Service sees Hermes", lambda: (self.http("GET", "/wizard/health")[1] or {}).get("upstream_reachable")
                  if self.was_running() else True, timeout=120)
        return self.hermes_version()

    def was_running(self):
        return self.sh("docker", "ps", "-q", "-f", "name=^" + WAS + "$", check=False).strip() != ""

    def start_was(self):
        self.sh("docker", "rm", "-f", WAS, check=False)
        self.sh("docker", "run", "-d", "--name", WAS, "--network", NET, "-p", "127.0.0.1:8787:8787",
                "-v", f"{self.root / 'was'}:/state", "-e", "WIZARD_HERMES_API_KEY=" + self.key,
                "-e", "HERMES_ORIGIN=http://hs-hermes:8642", "-e", "WIZARD_AUTH_MODE=none", self.a.was_image)
        self.wait("Agent Service health", lambda: (self.http("GET", "/wizard/health")[1] or {}).get("upstream_reachable"))

    def hermes_version(self):
        return self.sh("docker", "exec", "-u", "hermes", HERMES, "hermes", "--version").strip().splitlines()[0]

    def hermes_cli(self, *args):
        return self.sh("docker", "exec", "-u", "hermes", "-e", "HERMES_HOME=/opt/data", HERMES, "hermes", *args)

    # ---------- Wizard thread helpers (Agent Service routes, as the shell uses them) ----------
    def new_thread(self, title):
        """Create a thread exactly as the shell's outbox does (wizard_<ms>_<12 hex> id, source wizard-mobile), so
        the Agent Service treats it as a Wizard thread (follow-through, titles) rather than a bare API session."""
        sid = f"wizard_{int(time.time() * 1000)}_{uuid.uuid4().hex[:12]}"
        st, j = self.http("POST", "/wizard/hermes/api/sessions",
                          {"source": "wizard-mobile", "id": sid, "model": "hs-fake", "provider": "custom"})
        if st not in (200, 201):
            raise RuntimeError(f"session create {st}: {j}")
        self.say("thread", title, sid)
        return sid

    def send(self, sid, text, timeout=240):
        st, j = self.http("POST", "/wizard/hermes/v1/runs",
                          {"session_id": sid, "input": text, "model": "hs-fake", "provider": "custom",
                           "require_model_lock": True}, headers={"Idempotency-Key": str(uuid.uuid4())})
        if st not in (200, 202):
            raise RuntimeError(f"run create {st}: {j}")
        rid = j["run_id"]

        def done():
            s, r = self.http("GET", f"/wizard/hermes/v1/runs/{rid}")
            return r if s == 200 and r.get("status") in ("completed", "failed", "cancelled", "stopped", "error") else None
        return self.wait(f"run {rid}", done, timeout=timeout)

    def messages(self, sid, raw=False):
        """The thread as the shell reads it (web/live.js): oldest first, compacted rows included, Wizard view.
        raw=True drops the Wizard view, which hides internal rows such as helper completion receipts."""
        st, j = self.http("GET", f"/wizard/hermes/api/sessions/{sid}/messages?order=oldest&limit=500"
                                 "&include_compacted=true" + ("" if raw else "&view=wizard"))
        if st != 200:
            raise RuntimeError(f"messages {st}: {j}")
        return j["data"]

    def fake_requests(self):
        p = self.fake_dir / "requests.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

    # ---------- database ----------
    def db_snapshot(self, name):
        """Online-backup copy of state.db (the API the updater uses), then integrity and counts on the copy."""
        src = sqlite3.connect(f"file:{self.data / 'state.db'}?mode=ro", uri=True, timeout=30)
        copy = self.ev / name
        dst = sqlite3.connect(copy)
        src.backup(dst)
        src.close()
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {t: dst.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("sessions", "messages")}
        dst.close()
        return {"integrity": integrity, **counts, "copy": str(copy)}

    # ---------- checks ----------
    def check_thread(self):
        sid = self.new_thread("HS thread")
        run = self.send(sid, "HS-ECHO t1")
        msgs = self.messages(sid)
        pairs = [(m["role"], m.get("content")) for m in msgs]
        ok = run.get("status") == "completed" and run.get("output") == "ECHO t1" and \
            ("user", "HS-ECHO t1") in pairs and ("assistant", "ECHO t1") in pairs
        ev = [self.dump("thread-run.json", run), self.dump("thread-messages.json", msgs)]
        self.record("A thread sends and receives", ok, f"run {run.get('status')}, output {run.get('output')!r}; "
                    f"thread has {len(msgs)} messages read back through the Agent Service", ev)
        self.thread = sid
        self.thread_msgs = msgs

    def check_helper(self):
        sid = self.new_thread("HS helper")
        run = self.send(sid, "HS-DELEGATE h1", timeout=300)
        joined = "PARENT-SAW CHILD-RESULT h1" in str(run.get("output"))

        def arrived():
            msgs = self.messages(sid)
            return msgs if any(m["role"] == "assistant" and "PARENT-SAW CHILD-RESULT h1" in str(m.get("content"))
                               for m in msgs) else None
        try:
            msgs = self.wait("the helper's result in the parent thread", arrived, timeout=300, every=5)
        except RuntimeError:
            msgs = self.messages(sid)
        raw = self.messages(sid, raw=True)
        result_rows = [m for m in raw if m["role"] in ("tool", "user") and "CHILD-RESULT h1" in str(m.get("content"))]
        final = [m for m in msgs if m["role"] == "assistant" and "PARENT-SAW CHILD-RESULT h1" in str(m.get("content"))]
        child_req = [r for r in self.fake_requests() if r["reply"] == "CHILD-RESULT h1"]
        db = sqlite3.connect(f"file:{self.data / 'state.db'}?mode=ro", uri=True, timeout=30)
        children = db.execute("SELECT id, parent_session_id, source, end_reason FROM sessions WHERE parent_session_id = ?",
                              (sid,)).fetchall()
        db.close()
        mode = "joined inside the run" if joined else \
            "background helper; the Agent Service's follow-through started the next turn" if final else "background helper"
        ok = run.get("status") == "completed" and bool(result_rows) and bool(final) and bool(child_req)
        ev = [self.dump("helper-run.json", run), self.dump("helper-messages.json", msgs),
              self.dump("helper-messages-raw.json", raw),
              self.dump("helper-child-sessions.json", children)]
        self.record("A helper's result comes back to the thread that started it", ok,
                    f"{mode}; helper's model call seen: {bool(child_req)}; helper result stored in the parent thread: "
                    f"{bool(result_rows)}; parent's reply using it: {final[-1]['content'] if final else 'none within 300s'!r}; "
                    f"helper sessions recorded with this thread as parent: {len(children)}", ev)

    def check_markdown(self):
        sid = self.new_thread("HS markdown")
        run = self.send(sid, "HS-MARKDOWN m1")
        msgs = self.messages(sid)
        text = next((m["content"] for m in msgs if m["role"] == "assistant" and "m1" in str(m.get("content"))), "")
        # Render with the shell's own Markdown renderer (wizard-ux web/core/chat-kit.js from the pinned UX image),
        # evaluated in the Agent Service container's Node.
        kit = self.ev / "chat-kit.js"
        cid = self.sh("docker", "create", self.a.ux_image).strip()
        try:
            self.sh("docker", "cp", f"{cid}:/usr/share/nginx/wizard-ux/core/chat-kit.js", str(kit), check=False)
        finally:
            self.sh("docker", "rm", cid, check=False)
        (self.ev / "md-input.txt").write_text(text)
        render = ("const vm=require('vm'),fs=require('fs');const w={};w.window=w;w.document={addEventListener(){},"
                  "createElement(){return {style:{}}},documentElement:{style:{}}};w.navigator={};w.localStorage={getItem(){return null},setItem(){}};"
                  "w.addEventListener=()=>{};w.matchMedia=()=>({matches:false,addEventListener(){}});"
                  "vm.createContext(w);vm.runInContext(fs.readFileSync('/x/chat-kit.js','utf8'),w);"
                  "process.stdout.write(w.WosChat.md(fs.readFileSync('/x/md-input.txt','utf8')))")
        html = ""
        if kit.exists():
            html = self.sh("docker", "run", "--rm", "-v", f"{self.ev}:/x:ro", "--entrypoint", "node", self.a.was_image,
                           "-e", render, check=False)
        self.dump("md-rendered.html", html)
        want = {"heading": r"<h[1-6][^>]*>[^<]*Result m1", "bold": r"<strong>bold m1</strong>", "list": r"<li[^>]*>first item",
                "code block": r"<pre[^>]*>.*print\(", "table": r"<table", "link": r'href="https://example.com/m1"'}
        got = {k: bool(re.search(v, html, re.S)) for k, v in want.items()}
        ok = run.get("status") == "completed" and text.startswith("## Result m1") and all(got.values())
        self.record("Markdown replies render", ok,
                    "reply stored verbatim: %s; rendered by the shell's chat-kit.js: %s" % (
                        text.startswith("## Result m1"), ", ".join(f"{k} {'yes' if v else 'NO'}" for k, v in got.items())),
                    [self.ev / "md-input.txt", self.ev / "md-rendered.html"])

    @staticmethod
    def compacted(sent):
        """True when a request to the model carries the compaction summary and none of the early fact turns."""
        return "HS-SUMMARY-FACT" in json.dumps(sent) and not any(
            m.get("role") == "user" and "HS-FACT " in str(m.get("content")) for m in sent)

    def check_compaction(self):
        """Facts are stated early in a thread, buried under ordinary turns and a long reply, so Hermes' default
        compaction (head and tail protected, middle summarised) has to carry them through its summary."""
        sid = self.new_thread("HS compaction")
        before = len(self.fake_requests())
        for i in range(2):
            self.send(sid, f"HS-ECHO head{i}")
        for word in ("alpha", "bravo", "charlie"):
            self.send(sid, f"HS-FACT {word}")
        for i in range(12):
            self.send(sid, f"HS-ECHO pad{i}")
        self.send(sid, "HS-FILL f1", timeout=300)
        self.send(sid, "HS-ECHO after-fill", timeout=300)
        # When the compacted history reaches the model varies by release: v0.21.5 used it on the very next turn.
        # From v0.22 the gateway's session hygiene still compacts after the long turn, but the next turn goes out
        # with the full history ("Skipping preflight compression: ... not anchored on real usage ... deferring to
        # the next response"), and the turn after that is compacted (wizard-os#726,
        # docs/acceptance/hermes-fork-v0.22.7-compaction.md). Owners lose nothing either way. So the recall waits for
        # ordinary turns until one reaches the model compacted, up to SETTLE_TURNS of them, and the delay is reported.
        settled = None
        for i in range(SETTLE_TURNS):
            self.send(sid, f"HS-ECHO settle{i}", timeout=300)
            req = next((r for r in reversed(self.fake_requests()[before:]) if r["reply"] == f"ECHO settle{i}"), None)
            if req and self.compacted(req["request"]["messages"]):
                settled = i + 1
                break
        run = self.send(sid, "HS-RECALL", timeout=300)
        reqs = self.fake_requests()[before:]
        summaries = [r for r in reqs if "TURNS TO SUMMARIZE" in json.dumps(r["request"]) or
                     "summarization agent" in json.dumps(r["request"])]
        out = str(run.get("output"))
        recall_req = next((r for r in reversed(reqs) if r["reply"].startswith("RECALL")), None)
        recall_sent = recall_req["request"]["messages"] if recall_req else []
        sent = json.dumps(recall_sent)
        via_summary = [w for w in ("alpha", "bravo", "charlie") if "HS-SUMMARY-FACT " + w in sent]
        verbatim = [w for w in ("alpha", "bravo", "charlie")
                    if any(m.get("role") == "user" and "HS-FACT " + w in str(m.get("content")) for m in recall_sent)]
        recalled = [w for w in ("alpha", "bravo", "charlie") if w in out.split("|")[0]]
        msgs = self.messages(sid)
        shown = [w for w in ("alpha", "bravo", "charlie")
                 if any(m["role"] == "user" and m.get("content") == "HS-FACT " + w for m in msgs)]
        db = sqlite3.connect(f"file:{self.data / 'state.db'}?mode=ro", uri=True, timeout=30)
        stored = db.execute("SELECT count(*) FROM messages WHERE session_id = ?", (sid,)).fetchone()[0]
        stored_facts = db.execute("SELECT count(*) FROM messages WHERE session_id = ? AND content LIKE 'HS-FACT %'",
                                  (sid,)).fetchone()[0]
        db.close()
        # Pass/fail is the reasoning check. Whether the shell can still scroll back to the compacted turns is
        # reported beside it (history display, not reasoning).
        ok = run.get("status") == "completed" and bool(summaries) and via_summary == ["alpha", "bravo", "charlie"] \
            and not verbatim and recalled == via_summary
        self.observations.append({
            "topic": "When compaction reaches the model",
            "detail": (f"Hermes compacted after the long turn; the compacted history first reached the model on ordinary "
                       f"turn {settled} after it (v0.21.5: turn 1; v0.22 and later: turn 2, one extra full-size call)"
                       if settled else f"no ordinary turn reached the model compacted within {SETTLE_TURNS} turns")})
        self.observations.append({
            "topic": "Thread history after compaction",
            "detail": f"the compaction test thread has {stored} rows in state.db ({stored_facts} of the 3 early fact turns); "
                      f"the Agent Service returns {len(msgs)} messages to the shell (include_compacted=true, view=wizard), "
                      f"{'including' if shown == ['alpha', 'bravo', 'charlie'] else 'WITHOUT'} the compacted early turns"})
        ev = [self.dump("compaction-recall-run.json", run), self.dump("compaction-messages.json", msgs),
              self.dump("compaction-summary-requests.json", [{"reply": s["reply"], "messages": s["request"]["messages"][-2:]}
                                                             for s in summaries]),
              self.dump("compaction-recall-request.json", recall_sent)]
        self.record("A long conversation keeps its reasoning after compaction", ok,
                    f"Hermes compacted {len(summaries)} time(s), used by the model "
                    f"{f'from ordinary turn {settled} on' if settled else f'not within {SETTLE_TURNS} ordinary turns'}; "
                    "on the recall turn the early facts reached the model only "
                    f"through the summary: {via_summary or 'none'} (still verbatim: {verbatim or 'none'}); the model "
                    f"recalled {recalled or 'none'}", ev)

    def check_restart(self):
        before = self.db_snapshot("state-before-restart.db")
        t_before = self.messages(self.thread)
        self.sh("docker", "restart", HERMES)
        self.wait("Hermes health after restart", lambda: self.http("GET", "/health", base=HERMES_URL)[0] == 200, timeout=240)
        self.wait("Agent Service sees Hermes", lambda: (self.http("GET", "/wizard/health")[1] or {}).get("upstream_reachable"))
        after = self.db_snapshot("state-after-restart.db")
        t_after = self.messages(self.thread)
        run = self.send(self.thread, "HS-ECHO r1")
        ok = before["integrity"] == "ok" and after["integrity"] == "ok" and \
            after["sessions"] >= before["sessions"] and after["messages"] >= before["messages"] and \
            [m["content"] for m in t_after] == [m["content"] for m in t_before] and run.get("output") == "ECHO r1"
        ev = [self.dump("restart-db.json", {"before": before, "after": after}),
              self.dump("restart-thread-before.json", t_before), self.dump("restart-thread-after.json", t_after)]
        self.record("The database is intact before and after a restart", ok,
                    f"integrity before {before['integrity']}, after {after['integrity']}; sessions {before['sessions']}"
                    f"→{after['sessions']}, messages {before['messages']}→{after['messages']}; the first thread reads back "
                    f"identically and takes a new turn ({run.get('output')!r})", ev)

    def check_cron(self):
        created = self.hermes_cli("cron", "create", "every 1m", "HS-CRON c1", "--name", "hs-cron", "--deliver", "local")
        job = re.search(r"Created job: (\S+)", created)
        t0 = time.time()
        try:
            fired = self.wait("the scheduled job to fire",
                              lambda: [r for r in self.fake_requests() if r["reply"] == "CRON-FIRED c1"], timeout=240, every=5)
        except RuntimeError:
            fired = []
        listing = self.hermes_cli("cron", "list")
        out_dir = self.data / "cron" / "output"
        outputs = sorted(str(p.relative_to(self.data)) for p in out_dir.rglob("*") if p.is_file()) if out_dir.exists() else []
        if job:
            self.hermes_cli("cron", "remove", job.group(1))
        ok = bool(job) and bool(fired)
        ev = [self.dump("cron-create.txt", created), self.dump("cron-list.txt", listing),
              self.dump("cron-outputs.json", outputs)]
        self.record("A scheduled job fires", ok,
                    f"job {job.group(1) if job else 'not created'} scheduled 'every 1m'; its model call arrived "
                    f"{(fired[0]['t'] - t0):.0f}s after creation" if fired else
                    f"job {job.group(1) if job else 'not created'}; no model call within 240s", ev)

    def check_update_rollback(self):
        a = self.a
        # Update leg was done at the start (from → candidate); its evidence is in self.update.
        snap = self.db_snapshot("state-before-rollback.db")
        seed_before = self.messages(self.seed)
        thread_before = self.messages(self.thread)
        self.say("rolling back to", a.from_image)
        version = self.start_hermes(a.from_image)
        after = self.db_snapshot("state-after-rollback.db")
        seed_after = self.messages(self.seed)
        thread_after = self.messages(self.thread)
        run = self.send(self.thread, "HS-ECHO rb1")
        rb_ok = after["integrity"] == "ok" and [m["content"] for m in seed_after] == [m["content"] for m in seed_before] \
            and [m["content"] for m in thread_after] == [m["content"] for m in thread_before] and run.get("output") == "ECHO rb1"
        up = self.update
        ok = up["ok"] and rb_ok
        ev = [self.dump("update.json", up), self.dump("rollback.json", {
            "version": version, "db_before": snap, "db_after": after, "new_turn": run.get("output")})]
        same = a.from_image == a.image
        self.record("An update followed by a rollback both work, with history intact", ok,
                    ("update %s → %s: %s (seed thread from before the update read back identically: %s); "
                     "rollback → %s: %s (integrity %s; seed thread and post-update thread read back identically; "
                     "new turn %r)%s") % (
                        up["from_version"], up["to_version"], "ok" if up["ok"] else "FAILED", up["seed_intact"],
                        version, "ok" if rb_ok else "FAILED", after["integrity"], run.get("output"),
                        " — from and to are the same image, so this exercises the recreate/backup path only" if same else ""),
                    ev)

    # ---------- run ----------
    def run(self):
        a = self.a
        self.meta = {"image": a.image, "from_image": a.from_image, "was_image": a.was_image, "ux_image": a.ux_image,
                     "fake_image": a.fake_image, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self.setup()
        self.say("starting on the pinned release", a.from_image)
        from_version = self.start_hermes(a.from_image)
        self.start_was()
        self.seed = self.new_thread("HS seed")
        seed_run = self.send(self.seed, "HS-ECHO seed1")
        seed_msgs = self.messages(self.seed)
        pre = self.db_snapshot("state-before-update.db")
        # Update: back up config + state (online backup above), swap the image, keep the data.
        shutil.copy(self.data / "config.yaml", self.ev / "config-before-update.yaml")
        self.say("updating to the candidate", a.image)
        to_version = self.start_hermes(a.image)
        post = self.db_snapshot("state-after-update.db")
        seed_after = self.messages(self.seed)
        intact = [m["content"] for m in seed_after] == [m["content"] for m in seed_msgs]
        self.update = {"from_version": from_version, "to_version": to_version, "seed_run": seed_run.get("output"),
                       "db_before": pre, "db_after": post, "seed_intact": intact,
                       "ok": seed_run.get("output") == "ECHO seed1" and intact and post["integrity"] == "ok"}
        self.meta |= {"from_version": from_version, "version": to_version,
                      "image_labels": json.loads(self.sh("docker", "image", "inspect", a.image, "--format",
                                                         "{{json .Config.Labels}}") or "{}")}
        steps = [(self.check_thread, "A thread sends and receives"),
                 (self.check_helper, "A helper's result comes back to the thread that started it"),
                 (self.check_markdown, "Markdown replies render"),
                 (self.check_compaction, "A long conversation keeps its reasoning after compaction"),
                 (self.check_restart, "The database is intact before and after a restart"),
                 (self.check_cron, "A scheduled job fires"),
                 (self.check_update_rollback, "An update followed by a rollback both work, with history intact")]
        for step, name in steps:
            try:
                step()
            except Exception as e:  # one broken check must not hide the others
                self.record(name, False, f"harness error: {e}")
                if self.http("GET", "/health", base=HERMES_URL)[0] != 200:
                    self.start_hermes(a.image)
        for c in (HERMES, WAS, FAKE):
            self.dump(f"logs-{c}.txt", self.sh("docker", "logs", c, check=False) +
                      subprocess.run(["docker", "logs", c], capture_output=True, text=True).stderr[-200000:])
        self.meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (self.out / "results.json").write_text(json.dumps(self.meta | {"checks": self.results, "observations": self.observations}, indent=2))
        return all(r["pass"] for r in self.results) and len(self.results) == 7


def main():
    ap = argparse.ArgumentParser()
    for k in ("image", "from-image", "was-image", "ux-image", "fake-image", "out"):
        ap.add_argument("--" + k, required=True)
    box = Box(ap.parse_args())
    ok = box.run()
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
