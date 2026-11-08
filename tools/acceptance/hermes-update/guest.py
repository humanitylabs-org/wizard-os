#!/usr/bin/env python3
"""In-VM half of the `wizard hermes update --stable` acceptance (run.sh starts it inside a fresh Lima VM).

Installs stock Hermes FROM_TAG with the official installer, points it at the deterministic fake model, links Wizard
OS alongside it (`wizard link` against the CLI's own MCP test fixture standing in for the shell's gateway), starts
the gateway as the installer's systemd user service, seeds chat sessions and a daily cron job, then runs:

  A  dry run                 `--dry-run` changes nothing: SHA-256 of every file in the Hermes home and its code
                             checkout is identical before and after (gateway stopped so nothing else writes)
  B  busy box                a cron job due every minute keeps Hermes busy; with --quiet-timeout 45 the command
                             gives up with exit 11 and nothing changes
  C  forced failure          WIZARD_HERMES_UPDATE_FAULT=break-config breaks config.yaml after the code moved; the
                             command rolls back to FROM_TAG by itself, restores the config and re-checks
  D  real update             FROM_TAG -> TO_TAG passes the stable checks; the harness then re-verifies on its own
                             (exact commit and tag, /health version, chat round trip, session counts, cron list)

The target release file is the current Wizard stable release with its `hermes` block pointed at TO_TAG, so the
command reads it exactly the way it reads releases/stable. Results: <out>/results.json, RECEIPT.md, evidence/.
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
for a in ("--out", "--from-tag", "--from-commit", "--to-tag", "--to-commit"):
    ap.add_argument(a, required=True)
A = ap.parse_args()
OUT = Path(A.out)
EV = OUT / "evidence"
EV.mkdir(parents=True, exist_ok=True)
H = Path(__file__).resolve().parent
HOME = Path.home()
HH = HOME / ".hermes"
REPO = HH / "hermes-agent"
WIZ = [sys.executable, str(H / "wizard")]
RESULTS = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "from": [A.from_tag, A.from_commit],
           "to": [A.to_tag, A.to_commit], "checks": [], "facts": {}}
ENV = {**os.environ, "PATH": f"{HOME}/.local/bin:{os.environ.get('PATH', '')}", "NO_COLOR": "1"}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd, check=True, timeout=1800, env=None, name=None, **kw):
    p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout,
                       env=env or ENV, stdin=subprocess.DEVNULL, **kw)
    if name:
        (EV / name).write_text(f"$ {cmd}\nexit {p.returncode}\n--- stdout\n{p.stdout}\n--- stderr\n{p.stderr}")
    if check and p.returncode:
        raise SystemExit(f"FAILED ({p.returncode}): {cmd}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
    return p


def check(name, ok, detail, evidence=()):
    RESULTS["checks"].append({"check": name, "pass": bool(ok), "detail": detail, "evidence": list(evidence)})
    log(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    save()


def save():
    (OUT / "results.json").write_text(json.dumps(RESULTS, indent=2, default=str))


def head():
    return sh(["git", "-C", str(REPO), "rev-parse", "HEAD"]).stdout.strip()


def version():
    return sh(["hermes", "--version"], check=False).stdout.strip().splitlines()[0]


def env_key():
    for ln in (HH / ".env").read_text().splitlines():
        if ln.startswith("API_SERVER_KEY="):
            return ln.split("=", 1)[1].strip().strip("'\"")
    return ""


def health(timeout=3):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8642/health", timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def wait_health(seconds=180):
    t0 = time.time()
    while time.time() - t0 < seconds:
        h = health()
        if h.get("status") == "ok":
            return h
        time.sleep(3)
    return health()


def chat(text):
    req = urllib.request.Request("http://127.0.0.1:8642/v1/chat/completions", method="POST",
                                 data=json.dumps({"model": "hermes-agent", "stream": False,
                                                  "messages": [{"role": "user", "content": text}]}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {env_key()}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


def history():
    c = sqlite3.connect(f"file:{HH / 'state.db'}?mode=ro", uri=True)
    try:
        return {"integrity": c.execute("PRAGMA quick_check").fetchone()[0],
                "sessions": c.execute("SELECT count(*) FROM sessions").fetchone()[0],
                "messages": c.execute("SELECT count(*) FROM messages").fetchone()[0],
                "ids": sorted(r[0] for r in c.execute("SELECT id FROM sessions"))}
    finally:
        c.close()


def cron_ids():
    data = json.loads((HH / "cron" / "jobs.json").read_text())
    jobs = data.get("jobs") if isinstance(data, dict) else data
    return sorted(str(j.get("id")) for j in jobs)


def tree_hash(roots, skip=()):
    files = {}
    for root in roots:
        for p in sorted(Path(root).rglob("*")):
            if p.is_symlink():
                files[str(p)] = "link:" + os.readlink(p)
            elif p.is_file() and not any(s in p.parts for s in skip):
                files[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), files


def wizard(*args, env_extra=None, name=None, timeout=5400):
    p = sh([*WIZ, *args, "--json"], check=False, env={**ENV, **(env_extra or {})}, name=name, timeout=timeout)
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        out = {"unparsed": p.stdout[-1500:], "stderr": p.stderr[-1500:]}
    return p.returncode, out


# ------------------------------------------------------------------ 1. stock Hermes FROM_TAG
log(f"installing stock Hermes {A.from_tag} with the official installer")
sh(f"curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/{A.from_tag}/scripts/install.sh "
   f"| bash -s -- --branch {A.from_tag} --skip-setup --non-interactive --skip-browser --skip-computer-use",
   name="install.txt", timeout=3600)
RESULTS["facts"]["installed"] = {"head": head(), "version": version(),
                                 "stamp": json.loads((REPO / "install-stamp.json").read_text())
                                 if (REPO / "install-stamp.json").is_file() else None,
                                 "shallow": sh(["git", "-C", str(REPO), "rev-parse", "--is-shallow-repository"]).stdout.strip()}
check("stock install is the exact FROM commit", head() == A.from_commit, RESULTS["facts"]["installed"])

# fake model + config
fake = subprocess.Popen([sys.executable, str(H / "fake_model.py")], env={**ENV, "FAKE_PORT": "18080",
                        "FAKE_LOG": str(EV / "fake-model.jsonl")}, stdout=open(EV / "fake-model.log", "w"),
                        stderr=subprocess.STDOUT, start_new_session=True)
for k, v in (("model.provider", "custom"), ("model.base_url", "http://127.0.0.1:18080/v1"),
             ("model.default", "hs-fake"), ("model.api_key", "acceptance-fake-model")):
    sh(["hermes", "config", "set", k, v], name=f"config-set-{k}.txt")

# WizardOS alongside: the CLI's MCP fixture stands in for the shell's gateway
fix = subprocess.Popen([sys.executable, str(H / "mcp_fixture.py"), "--port", "8796"], stdout=open(EV / "mcp.log", "w"),
                       stderr=subprocess.STDOUT, start_new_session=True)
time.sleep(2)
rc, linked = wizard("link", "--url", "http://127.0.0.1:8796/mcp", name="wizard-link.json")
check("WizardOS linked alongside (wizard link)", rc == 0 and linked.get("ok"), {"exit": rc, "plugin": linked.get(
    "plugin_installed"), "gateway": linked.get("gateway")}, ["evidence/wizard-link.json"])

# gateway as the installer's systemd user service
sh(["hermes", "gateway", "install"], name="gateway-install.txt", check=False, timeout=300)
sh(["hermes", "gateway", "start"], name="gateway-start.txt", check=False, timeout=300)
h = wait_health()
check("gateway up on FROM", h.get("status") == "ok", h)

# seed: chat sessions + a daily cron job
replies = [chat(f"HS-ECHO seed{i}") for i in range(3)]
cron = sh(["hermes", "cron", "create", "every 24h", "HS-CRON daily", "--name", "daily-check", "--deliver", "local"],
          name="cron-create.txt")
seed = {"history": history(), "cron": cron_ids()}
RESULTS["facts"]["seed"] = {**seed["history"], "ids": len(seed["history"]["ids"]), "cron": seed["cron"],
                            "replies": replies}
check("seeded sessions and cron job", seed["history"]["sessions"] >= 3 and seed["cron"], RESULTS["facts"]["seed"])

# target release file: today's Wizard stable release with its hermes block pointed at TO_TAG
base = "https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/main/releases"
stable = urllib.request.urlopen(f"{base}/stable", timeout=30).read().decode().strip()
rel = json.loads(urllib.request.urlopen(f"{base}/{stable}.json", timeout=30).read())
rel["version"] = f"{stable}+acceptance-{A.to_tag}"
rel["hermes"] = {**rel.get("hermes", {}), "tag": A.to_tag, "commit": A.to_commit,
                 "test_record": "acceptance candidate only (tools/acceptance/hermes-update); not a promotion"}
REL = OUT / "release-candidate.json"
REL.write_text(json.dumps(rel, indent=2))
RESULTS["facts"]["release_base"] = {"stable": stable, "candidate_file": str(REL)}

# ------------------------------------------------------------------ A. dry run changes nothing
sh(["hermes", "gateway", "stop"], name="gateway-stop-A.txt", check=False, timeout=300)
time.sleep(3)
h1, f1 = tree_hash([HH])
rc, dry = wizard("hermes", "update", "--stable", "--dry-run", "--release", str(REL), name="A-dry-run.json")
h2, f2 = tree_hash([HH])
changed = sorted(k for k in set(f1) | set(f2) if f1.get(k) != f2.get(k))
check("A dry run changes nothing", rc == 0 and dry.get("dry_run") and h1 == h2 and head() == A.from_commit,
      {"exit": rc, "home_sha256_before": h1, "home_sha256_after": h2, "files_changed": changed[:20],
       "files_hashed": len(f1), "plan_steps": len(dry.get("plan") or [])}, ["evidence/A-dry-run.json"])
sh(["hermes", "gateway", "start"], name="gateway-start-A.txt", check=False, timeout=300)
wait_health()

# ------------------------------------------------------------------ B. busy box: no quiet moment, nothing changed
busy = sh(["hermes", "cron", "create", "every 1m", "HS-CRON busy", "--name", "busy", "--deliver", "local"],
          name="cron-create-busy.txt")
busy_id = next((j for j in cron_ids() if j not in seed["cron"]), None)
before_b = head()
rc, out_b = wizard("hermes", "update", "--stable", "--release", str(REL), "--quiet-timeout", "45",
                   name="B-busy.json")
check("B busy box: waits, gives up, nothing changed", rc == 11 and head() == before_b and
      (out_b.get("error") or {}).get("code") == "not_quiet" and not (HH / ".drain_request.json").exists(),
      {"exit": rc, "error": out_b.get("error"), "head": head()}, ["evidence/B-busy.json"])
if busy_id:
    sh(["hermes", "cron", "remove", busy_id], name="cron-remove-busy.txt", check=False)
time.sleep(5)
before_c = {"history": history(), "cron": cron_ids()}

# ------------------------------------------------------------------ C. forced failure -> automatic rollback
rc, out_c = wizard("hermes", "update", "--stable", "--release", str(REL), "--quiet-timeout", "600",
                   env_extra={"WIZARD_HERMES_UPDATE_FAULT": "break-config"}, name="C-forced-failure.json")
rcpt_c = (out_c.get("error") or {}).get("receipt")
if rcpt_c:
    shutil.copy(rcpt_c, EV / "C-receipt.json")
hist_c = history()
h_c = wait_health(60)
reply_c = chat("HS-ECHO after-rollback")
cfg_ok = sh(["hermes", "config", "show"], check=False, name="C-config-show.txt").returncode == 0
check("C forced failure rolls back to FROM with history intact",
      rc == 12 and head() == A.from_commit and set(before_c["history"]["ids"]) <= set(hist_c["ids"]) and
      hist_c["integrity"] == "ok" and set(before_c["cron"]) <= set(cron_ids()) and h_c.get("status") == "ok"
      and bool(reply_c) and cfg_ok,
      {"exit": rc, "code": (out_c.get("error") or {}).get("code"), "head": head(), "version": version(),
       "health": h_c, "sessions_before": before_c["history"]["sessions"], "sessions_after": hist_c["sessions"],
       "cron_after": cron_ids(), "chat_after": reply_c, "config_readable": cfg_ok, "receipt": rcpt_c},
      ["evidence/C-forced-failure.json", "evidence/C-receipt.json"])

# ------------------------------------------------------------------ D. the real update
before_d = {"history": history(), "cron": cron_ids()}
rc, out_d = wizard("hermes", "update", "--stable", "--release", str(REL), "--quiet-timeout", "600",
                   name="D-update.json")
if out_d.get("receipt"):
    shutil.copy(out_d["receipt"], EV / "D-receipt.json")
tags = sh(["git", "-C", str(REPO), "tag", "--points-at", "HEAD"]).stdout.split()
h_d = wait_health(60)
reply_d = chat("HS-ECHO after-update")
hist_d = history()
cron_list = sh(["hermes", "cron", "list"], check=False, name="D-cron-list.txt")
ver = version()
want_ver = A.to_tag.lstrip("v")
check("D update to TO passes with the exact version",
      rc == 0 and out_d.get("updated") and head() == A.to_commit and A.to_tag in tags and h_d.get("status") == "ok"
      and want_ver in ver and str(h_d.get("version")) in ver,
      {"exit": rc, "head": head(), "tags": tags, "version": ver, "health": h_d, "receipt": out_d.get("receipt"),
       "cli_checks": [(c["check"], c["ok"]) for c in out_d.get("checks") or []]},
      ["evidence/D-update.json", "evidence/D-receipt.json"])
check("D sessions and cron intact after the update",
      set(before_d["history"]["ids"]) <= set(hist_d["ids"]) and hist_d["integrity"] == "ok" and
      hist_d["messages"] >= before_d["history"]["messages"] and set(before_d["cron"]) <= set(cron_ids())
      and cron_list.returncode == 0 and bool(reply_d),
      {"sessions_before": before_d["history"]["sessions"], "sessions_after": hist_d["sessions"],
       "messages_before": before_d["history"]["messages"], "messages_after": hist_d["messages"],
       "cron_before": before_d["cron"], "cron_after": cron_ids(), "chat_after": reply_d},
      ["evidence/D-cron-list.txt"])
rc, st = wizard("hermes", "status", "--release", str(REL), name="D-status.json")
check("wizard hermes status agrees", rc == 0 and st.get("matches_stable") is True, {"exit": rc, "matches": st.get(
    "matches_stable"), "current": (st.get("current") or {}).get("version")}, ["evidence/D-status.json"])

for p in (fake, fix):
    p.terminate()
RESULTS["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
save()
ok = all(c["pass"] for c in RESULTS["checks"])
lines = [f"# `wizard hermes update --stable` acceptance: {'PASS' if ok else 'FAIL'}", "",
         f"- {A.from_tag} ({A.from_commit}) -> {A.to_tag} ({A.to_commit})",
         f"- {RESULTS['started']} -> {RESULTS['finished']}", ""]
lines += [f"- {'PASS' if c['pass'] else 'FAIL'}: {c['check']}" for c in RESULTS["checks"]]
(OUT / "RECEIPT.md").write_text("\n".join(lines) + "\n")
sys.exit(0 if ok else 1)
