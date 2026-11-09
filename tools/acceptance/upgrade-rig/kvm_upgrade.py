#!/usr/bin/env python3
"""Disposable-KVM upgrade test: install the current Stable on a fresh guest with the public command, then upgrade it
to a candidate release with the same command, and check what promote_stable.py's upgrade evidence needs.

    python3 tools/acceptance/upgrade-rig/kvm_upgrade.py golden            # build/refresh the Hermes base image
    python3 tools/acceptance/upgrade-rig/kvm_upgrade.py run --from 0.3.72 --to 0.3.73 [--release-base URL] [--keep]

The rig is the one documented in docs/acceptance/promote-0.3.65.md and promote-0.3.72.md, automated:

- an Ubuntu 24.04 cloud image (KVM, 4 vCPU, 8 GB, user-mode NAT, loopback-only SSH forward), never the host's
  Docker, Tailscale or services; every run boots a throwaway qcow2 overlay and deletes it afterwards;
- a "golden" overlay with root stock Hermes from the official installer (`--skip-setup`) and `hermes gateway install`,
  plus Tailscale, rebuilt when missing or older than --max-golden-age days (Hermes moves; customers install today's);
- a local headscale (docker, 127.0.0.1 only) stands in for the owner's tailnet; a pre-auth key stands in for the
  owner approving the sign-in link. Headscale has no HTTPS certificates or Serve: a test-only `tailscale` wrapper on
  the guest reports CertDomains and accepts `tailscale cert` (simulates an owner who turned HTTPS on), so installs end
  box-only, and the Troubleshooter's Serve check is an infrastructure limit, not a release failure;
- both installs run the PUBLIC command (`curl -fsSL https://aiwizards.com/os.sh | ... bash -s start`) as an agent
  would (agent-safe env), polled through ~/.wizard-os/install-status.json.

Passing means: the upgrade ended `done`; release.json names the candidate, status `pinned`, every check ok; Hermes
config.yaml/.env/SOUL.md are byte-identical; the Hermes API answers; the shell answers; `wizard doctor` and
`wam doctor` report no FAIL. The report (JSON + Markdown) is the evidence a promotion links to.

Needs: qemu-system-x86_64 with /dev/kvm, qemu-img, cloud-localds, docker (rootless is fine), ssh, ~12 GB disk.
Nothing here touches a real box.
"""
from __future__ import annotations

import argparse
import grp
import hashlib
import json
import os
import pwd
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ASSETS = Path(os.environ.get("WIZARD_RIG_DIR", Path.home() / ".cache" / "wizard-release-train" / "rig"))
BASE_URL = "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
OS_SH = "https://aiwizards.com/os.sh"
HERMES_INSTALL = "https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh"
SSH_PORT = int(os.environ.get("WIZARD_RIG_SSH_PORT", "2273"))
SHELL_PORT = int(os.environ.get("WIZARD_RIG_SHELL_PORT", "18897"))
HS_PORT = int(os.environ.get("WIZARD_RIG_HS_PORT", "8090"))
# Guest size: 4 vCPU / 8 GB on a box; a GitHub-hosted runner (2 vCPU, 7 GB) sets smaller values in the workflow.
GUEST_SMP = os.environ.get("WIZARD_RIG_SMP", "4")
GUEST_MEM_MB = os.environ.get("WIZARD_RIG_MEM_MB", "8192")
HS_NAME = "wizard-train-headscale"
HS_IMAGE = "headscale/headscale:latest"
GUEST_UNIT = "wizard-train-guest"
ROOT_ENV = "export PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin XDG_RUNTIME_DIR=/run/user/0; "
# An agent-run install (what owners do: they paste one sentence to their agent): detached, restart deferred.
AGENT_ENV = "_HERMES_GATEWAY=1 HERMES_SESSION_PLATFORM=telegram "

TS_WRAPPER = r"""#!/bin/bash
# TEST-ONLY wrapper (disposable upgrade-rig guest): headscale cannot issue HTTPS certs; simulate "owner turned HTTPS on".
REAL=/usr/bin/tailscale
if [ -f /root/.https-on ]; then
  case " $* " in
    *" cert "*)
      for ((i=1;i<=$#;i++)); do a="${!i}"; n=$((i+1));
        [ "$a" = --cert-file ] && touch "${!n}"; [ "$a" = --key-file ] && touch "${!n}"; done; exit 0 ;;
    *" status "*"--json"*|*" status --json "*)
      "$REAL" "$@" | python3 -c 'import json,sys
d=json.load(sys.stdin); s=(d.get("Self") or {}).get("DNSName","wtrain.train.test.").rstrip(".")
d["CertDomains"]=[s]; print(json.dumps(d))'; exit ${PIPESTATUS[0]} ;;
  esac
fi
exec "$REAL" "$@"
"""

HS_CONFIG = f"""server_url: http://10.0.2.2:{HS_PORT}
listen_addr: 0.0.0.0:8080
metrics_listen_addr: 127.0.0.1:9090
grpc_listen_addr: 127.0.0.1:50443
grpc_allow_insecure: false
noise:
  private_key_path: /var/lib/headscale/noise_private.key
prefixes:
  v4: 100.73.0.0/16
  v6: fd7a:115c:a1e0:73::/64
  allocation: sequential
derp:
  server:
    enabled: false
  urls:
    - https://controlplane.tailscale.com/derpmap/default
  auto_update_enabled: false
  update_frequency: 24h
disable_check_updates: true
ephemeral_node_inactivity_timeout: 30m
database:
  type: sqlite
  sqlite:
    path: /var/lib/headscale/db.sqlite
log:
  level: info
policy:
  mode: file
  path: ""
dns:
  magic_dns: true
  base_domain: train.test
  override_local_dns: false
  nameservers:
    global: []
unix_socket: /var/run/headscale/headscale.sock
unix_socket_permission: "0770"
"""


def say(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def sh(cmd: list[str], check: bool = True, timeout: float = 600, **kw) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    if check and p.returncode:
        raise SystemExit(f"{' '.join(cmd[:4])}…: exit {p.returncode}: {(p.stderr or p.stdout).strip()[-400:]}")
    return p


def key() -> Path:
    k = ASSETS / "guest_key"
    if not k.exists():
        sh(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "wizard-upgrade-rig", "-f", str(k)])
    return k


def ssh_cmd(cmd: str) -> list[str]:
    return ["ssh", "-i", str(key()), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30", "-p", str(SSH_PORT),
            "root@127.0.0.1", cmd]


def guest(cmd: str, check: bool = True, timeout: float = 600) -> str:
    p = sh(ssh_cmd(ROOT_ENV + cmd), check=False, timeout=timeout)
    if check and p.returncode:
        raise SystemExit(f"guest `{cmd[:80]}`: exit {p.returncode}: {(p.stderr or p.stdout).strip()[-400:]}")
    return p.stdout


def wait_ssh(timeout: float = 420) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if sh(ssh_cmd("true"), check=False, timeout=20).returncode == 0:
            return
        time.sleep(5)
    raise SystemExit("guest SSH did not come up")


def port_free(port: int) -> bool:
    s = socket.socket()
    try:
        return s.connect_ex(("127.0.0.1", port)) != 0
    finally:
        s.close()


def base_image() -> Path:
    img = ASSETS / "noble-base.img"
    if not img.exists():
        ASSETS.mkdir(parents=True, exist_ok=True)
        say(f"downloading {BASE_URL}")
        tmp = img.with_suffix(".part")
        with urllib.request.urlopen(BASE_URL, timeout=600) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.replace(img)
    return img


def seed(path: Path, instance: str) -> None:
    ud, md = path.with_suffix(".user-data"), path.with_suffix(".meta-data")
    ud.write_text("#cloud-config\nhostname: wtrain\ndisable_root: false\nssh_pwauth: false\nusers:\n  - name: root\n"
                  f"    ssh_authorized_keys:\n      - {(ASSETS / 'guest_key.pub').read_text().strip()}\n"
                  "package_update: false\n")
    md.write_text(f"instance-id: {instance}\nlocal-hostname: wtrain\n")
    sh(["cloud-localds", str(path), str(ud), str(md)])


def kvm_wrap() -> list[str]:
    """[] when this process can open /dev/kvm; else `sg kvm -c` (the user is in the kvm group, but a long-lived
    process such as a job worker or the systemd --user manager started before they joined it has stale groups)."""
    try:
        os.close(os.open("/dev/kvm", os.O_RDWR))
        return []
    except OSError:
        pass
    try:
        g = grp.getgrnam("kvm")
        member = pwd.getpwuid(os.getuid()).pw_name in g.gr_mem or pwd.getpwuid(os.getuid()).pw_gid == g.gr_gid
    except KeyError:
        member = False
    return ["sg", "kvm", "-c"] if member and shutil.which("sg") and os.path.exists("/dev/kvm") else []


def _pidfile(unit: str) -> Path:
    return ASSETS / f"{unit}.pid"


def vm_active(unit: str) -> bool:
    try:
        pid = int(_pidfile(unit).read_text().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    try:   # a zombie child of this process counts as gone
        return os.waitpid(pid, os.WNOHANG) == (0, 0)
    except ChildProcessError:
        return True


def vm_stop(unit: str, timeout: float = 60) -> None:
    """Stop a guest started by vm_start (this run or an earlier --keep run): SIGTERM, then SIGKILL."""
    if vm_active(unit):
        pid = int(_pidfile(unit).read_text().strip())
        for sig, wait in ((signal.SIGTERM, timeout), (signal.SIGKILL, 10)):
            try:
                os.killpg(pid, sig)
            except OSError:
                break
            deadline = time.time() + wait
            while time.time() < deadline and vm_active(unit):
                time.sleep(1)
            if not vm_active(unit):
                break
    _pidfile(unit).unlink(missing_ok=True)


def vm_start(unit: str, argv: list[str], log: Path) -> None:
    """Start qemu as this process's own child, in its own session so --keep guests outlive it; tracked by a pidfile.
    Not `systemd-run --user`: the user manager may predate the user joining the kvm group, and then qemu cannot open
    /dev/kvm (forum, 9 Nov 2026)."""
    wrap = kvm_wrap()
    cmd = wrap + ["exec " + shlex.join(argv)] if wrap else argv
    with open(log, "ab") as out:
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    _pidfile(unit).write_text(f"{p.pid}\n")
    time.sleep(3)
    if p.poll() is not None:
        _pidfile(unit).unlink(missing_ok=True)
        raise SystemExit(f"qemu exited {p.returncode}: {log.read_text(errors='replace')[-400:]}")


def boot(disk: Path, unit: str, seed_iso: Path | None = None) -> Path:
    if not port_free(SSH_PORT):
        raise SystemExit(f"127.0.0.1:{SSH_PORT} is taken: another rig guest is running ({unit})")
    qmp = disk.with_suffix(".qmp")
    qmp.unlink(missing_ok=True)
    cmd = [shutil.which("qemu-system-x86_64") or "qemu-system-x86_64", "-enable-kvm", "-cpu", "host", "-smp", GUEST_SMP,
           "-m", GUEST_MEM_MB, "-drive", f"file={disk},if=virtio",
           "-netdev", f"user,id=n0,hostfwd=tcp:127.0.0.1:{SSH_PORT}-:22,hostfwd=tcp:127.0.0.1:{SHELL_PORT}-:8796",
           "-device", "virtio-net-pci,netdev=n0", "-display", "none", "-serial", f"file:{disk.with_suffix('.console')}",
           "-qmp", f"unix:{qmp},server,nowait"]
    if seed_iso:
        cmd[cmd.index("-netdev"):cmd.index("-netdev")] = ["-drive", f"file={seed_iso},if=virtio,format=raw"]
    vm_start(unit, cmd, disk.with_suffix(".qemu.log"))
    return qmp


def power_off(qmp: Path, unit: str, timeout: float = 120) -> None:
    """ACPI power button through QMP (a clean guest shutdown), then stop the guest."""
    try:
        s = socket.socket(socket.AF_UNIX)
        s.settimeout(10)
        s.connect(str(qmp))
        s.recv(4096)
        for msg in ({"execute": "qmp_capabilities"}, {"execute": "system_" + "powerdown"}):
            s.sendall(json.dumps(msg).encode() + b"\n")
            time.sleep(0.5)
            s.recv(4096)
        s.close()
    except OSError:
        pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not vm_active(unit):
            vm_stop(unit)
            return
        time.sleep(3)
    vm_stop(unit)


def golden(max_age_days: float = 7, force: bool = False) -> Path:
    """The Hermes base image: noble + root stock Hermes (official installer, --skip-setup) + gateway + Tailscale."""
    g, meta = ASSETS / "golden.qcow2", ASSETS / "golden.json"
    if g.exists() and meta.exists() and not force:
        m = json.loads(meta.read_text())
        if time.time() - m.get("built", 0) < max_age_days * 86400:
            return g
    base = base_image()
    key()
    say("building the golden Hermes guest (official Hermes installer; ~10-15 min)")
    tmp = ASSETS / "golden-build.qcow2"
    tmp.unlink(missing_ok=True)
    sh(["qemu-img", "create", "-q", "-f", "qcow2", "-b", str(base), "-F", "qcow2", str(tmp), "40G"])
    iso = ASSETS / "golden-seed.iso"
    seed(iso, f"wtrain-golden-{int(time.time())}")
    unit = GUEST_UNIT + "-golden"
    vm_stop(unit)
    qmp = boot(tmp, unit, iso)
    try:
        wait_ssh()
        guest("cloud-init status --wait >/dev/null 2>&1 || true", timeout=600)
        guest("loginctl enable-linger root; systemctl start user@0.service")
        guest(f"curl -fsSL {HERMES_INSTALL} -o /root/hermes-install.sh && "
              "(nohup bash /root/hermes-install.sh --skip-setup > /root/hermes-install.log 2>&1; echo $? > /root/hermes-install.rc) "
              "</dev/null >/dev/null 2>&1 &")
        deadline = time.time() + 2400
        while time.time() < deadline and not guest("cat /root/hermes-install.rc 2>/dev/null", check=False).strip():
            time.sleep(15)
        rc = guest("cat /root/hermes-install.rc 2>/dev/null", check=False).strip()
        if rc != "0":
            raise SystemExit(f"Hermes installer exit {rc or 'timeout'}: "
                             + guest("tail -5 /root/hermes-install.log", check=False))
        guest("hermes gateway install </dev/null", timeout=300)
        guest("curl -fsSL https://tailscale.com/install.sh | sh >/root/tailscale-install.log 2>&1", timeout=900)
        guest("cat > /usr/local/bin/tailscale <<'EOF'\n" + TS_WRAPPER + "EOF\nchmod 755 /usr/local/bin/tailscale")
        version = guest("hermes --version 2>/dev/null | head -1", check=False).strip()
        guest("sync")
    finally:
        power_off(qmp, unit)
    tmp.replace(g)
    meta.write_text(json.dumps({"built": time.time(), "hermes": version, "base": BASE_URL,
                                "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n")
    say(f"golden ready: {version}")
    return g


def headscale_up(rundir: Path) -> str:
    """A fresh local headscale and a one-hour pre-auth key (stands in for the owner approving the link)."""
    sh(["docker", "rm", "-f", HS_NAME], check=False)
    cfg, lib = rundir / "hs" / "config", rundir / "hs" / "lib"
    cfg.mkdir(parents=True); lib.mkdir(parents=True)
    (cfg / "config.yaml").write_text(HS_CONFIG)
    sh(["docker", "run", "-d", "--name", HS_NAME, "-p", f"127.0.0.1:{HS_PORT}:8080", "-v", f"{cfg}:/etc/headscale",
        "-v", f"{lib}:/var/lib/headscale", HS_IMAGE, "serve"])
    for _ in range(30):
        if sh(["docker", "exec", HS_NAME, "headscale", "users", "list"], check=False).returncode == 0:
            break
        time.sleep(1)
    sh(["docker", "exec", HS_NAME, "headscale", "users", "create", "train"], check=False)
    users = json.loads(sh(["docker", "exec", HS_NAME, "headscale", "users", "list", "-o", "json"]).stdout or "[]")
    uid = next(str(u.get("id")) for u in users if u.get("name") == "train")
    out = sh(["docker", "exec", HS_NAME, "headscale", "preauthkeys", "create", "--user", uid, "--reusable",
              "--expiration", "2h", "-o", "json"]).stdout
    return json.loads(out)["key"]


def wait_install(label: str, timeout: float = 2700) -> dict:
    deadline, last = time.time() + timeout, ""
    while time.time() < deadline:
        st = guest("cat /root/.wizard-os/install-status.json 2>/dev/null", check=False)
        try:
            d = json.loads(st)
        except ValueError:
            d = {}
        step = f"{d.get('state')} · {d.get('step')}"
        if step != last:
            say(f"{label}: {step}")
            last = step
        if d.get("state") in ("done", "failed", "needs_owner", "needs_admin", "interrupted"):
            return d
        time.sleep(15)
    return {"state": "timeout"}


def snapshot() -> dict:
    out = guest(
        "cd /root/.hermes; for f in config.yaml .env SOUL.md; do [ -f $f ] && echo \"$f $(sha256sum < $f | cut -c1-64)\"; done; "
        "echo \"hermes $(hermes --version 2>/dev/null | head -1)\"; "
        "echo \"api $(curl -s -o /dev/null -m 5 -w %{http_code} http://127.0.0.1:8642/health)\"; "
        "echo \"gateway $(systemctl --user is-active hermes-gateway 2>/dev/null)\"; "
        "echo \"shell $(curl -s -o /dev/null -m 5 -w %{http_code} http://127.0.0.1:8796/)\"", check=False)
    snap: dict = {"files": {}}
    for line in out.splitlines():
        k, _, v = line.partition(" ")
        if k in ("config.yaml", ".env", "SOUL.md"):
            snap["files"][k] = v
        else:
            snap[k] = v
    try:
        snap["release"] = json.loads(guest("cat /root/.wizard-os/release.json", check=False))
    except ValueError:
        snap["release"] = {}
    snap["containers"] = guest("docker ps --format '{{.Names}}' | sort | while read n; do "
                               "echo \"$n $(docker inspect -f '{{.Image}} {{.State.StartedAt}}' $n)\"; done",
                               check=False).splitlines()
    for tool in ("wizard", "wam"):
        lines = guest(f"{tool} doctor 2>&1", check=False, timeout=300).splitlines()
        snap[f"{tool}_doctor_fail"] = [ln.strip() for ln in lines if ln.strip().startswith("FAIL")]
    return snap


def install(release: str, label: str, release_base: str | None) -> tuple[dict, float]:
    env = AGENT_ENV + f"WIZARD_RELEASE={shlex.quote(release)} WIZARD_STRICT=1 "
    if release_base:
        env += f"WIZARD_RELEASE_BASE={shlex.quote(release_base)} "
    gw = lambda: guest("systemctl --user show -p MainPID --value hermes-gateway; "   # noqa: E731
                       "systemctl --user is-active hermes-gateway; "
                       "curl -s -o /dev/null -m 5 -w %{http_code} http://127.0.0.1:8642/health", check=False).split()
    pid0 = (gw() or [""])[0]
    t0 = time.time()
    say(f"{label}: curl -fsSL {OS_SH} | {env}bash -s start")
    guest(f"curl -fsSL {OS_SH} | {env}bash -s start", timeout=300)
    st = wait_install(label)
    secs = time.time() - t0
    # The installer defers the Hermes restart until its runner exits (~20 s, then a graceful drain). Checking right
    # away sees the OLD gateway answer and then catches the restart mid-way (a false "API down"): wait for the new
    # gateway process to answer, or 2 minutes without a restart (none was needed).
    t1 = time.time()
    while time.time() - t1 < 420:
        cur = gw() + ["", "", ""]
        settled = cur[1] == "active" and cur[2] == "200"
        if settled and (cur[0] != pid0 or time.time() - t1 > 120):
            say(f"{label}: Hermes gateway {'restarted' if cur[0] != pid0 else 'kept running'} and answers")
            break
        time.sleep(10)
    time.sleep(10)
    return st, secs


def run(frm: str, to: str, release_base: str | None, keep: bool, max_golden_age: float, out: Path | None) -> dict:
    for tool in ("qemu-system-x86_64", "qemu-img", "cloud-localds", "docker", "ssh"):
        if not shutil.which(tool):
            raise SystemExit(f"missing {tool}")
    if not os.access("/dev/kvm", os.R_OK | os.W_OK) and not kvm_wrap():
        raise SystemExit("no /dev/kvm access")
    ASSETS.mkdir(parents=True, exist_ok=True)
    g = golden(max_golden_age)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    rundir = ASSETS / "runs" / f"{stamp}-{frm}-to-{to}"
    rundir.mkdir(parents=True)
    disk = rundir / "guest.qcow2"
    sh(["qemu-img", "create", "-q", "-f", "qcow2", "-b", str(g), "-F", "qcow2", str(disk)])
    os_sh = subprocess.run(["curl", "-fsSL", OS_SH], capture_output=True, timeout=60).stdout   # the bytes owners get
    report: dict = {"from": frm, "to": to, "started_at": stamp, "release_base": release_base or "public mirror",
                    "golden": json.loads((ASSETS / "golden.json").read_text()),
                    "os_sh_sha256": hashlib.sha256(os_sh).hexdigest(), "rundir": str(rundir), "problems": []}
    vm_stop(GUEST_UNIT)
    qmp = None
    try:
        authkey = headscale_up(rundir)
        qmp = boot(disk, GUEST_UNIT)
        wait_ssh()
        guest(f"tailscale up --login-server=http://10.0.2.2:{HS_PORT} --authkey={authkey} --timeout=90s "
              ">/root/ts-up.log 2>&1; touch /root/.https-on; tailscale ip -4", timeout=200)
        st, secs = install(frm, f"install {frm}", None)
        report["install_from"] = {"state": st.get("state"), "seconds": round(secs)}
        if st.get("state") != "done":
            report["problems"].append(f"installing {frm} ended {st.get('state')}: {st.get('failure_reason') or st.get('message')}")
            return report
        before = snapshot()
        report["before"] = before
        rel = before.get("release") or {}
        if rel.get("release") != frm or rel.get("status") != "pinned":
            report["problems"].append(f"before: release.json is {rel.get('release')} {rel.get('status')}, not {frm} pinned")
        st, secs = install(to, f"upgrade {frm} -> {to}", release_base)
        report["upgrade"] = {"state": st.get("state"), "seconds": round(secs), "quick": st.get("quick") is True,
                             "failure_reason": st.get("failure_reason")}
        after = snapshot()
        report["after"] = after
        if st.get("state") != "done":
            report["problems"].append(f"upgrade ended {st.get('state')}: {st.get('failure_reason') or st.get('message')}")
        rel = after.get("release") or {}
        bad = [c.get("name") for c in rel.get("checks", []) if not c.get("ok")]
        if rel.get("release") != to or rel.get("status") != "pinned" or bad:
            report["problems"].append(f"after: release.json {rel.get('release')} {rel.get('status')}, failed checks {bad}")
        if before["files"] != after["files"]:
            report["problems"].append(f"Hermes files changed: {before['files']} -> {after['files']}")
        for k, want in (("api", "200"), ("gateway", "active")):
            if after.get(k) != want:
                report["problems"].append(f"{k}: {after.get(k)} (want {want})")
        if not str(after.get("shell", "")).startswith(("2", "3")):   # the shell answers / with a redirect into the UI
            report["problems"].append(f"shell: HTTP {after.get('shell')}")
        for tool in ("wizard", "wam"):
            if after.get(f"{tool}_doctor_fail"):
                report["problems"].append(f"{tool} doctor FAIL: {after[f'{tool}_doctor_fail']}")
        return report
    finally:
        report["passed"] = not report["problems"] and "after" in report
        report["finished_at"] = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        try:
            report["install_log_tail"] = guest("tail -40 /root/.wizard-os/install.log", check=False)[-6000:]
        except BaseException:   # noqa: BLE001
            pass
        (rundir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        (rundir / "report.md").write_text(markdown(report))
        if out:
            out.write_text(json.dumps(report, indent=2) + "\n")
        if not keep:
            if qmp:
                vm_stop(GUEST_UNIT)
            sh(["docker", "rm", "-f", HS_NAME], check=False)
            disk.unlink(missing_ok=True)
        say(f"upgrade test {frm} -> {to}: {'PASSED' if report['passed'] else 'FAILED'} ({rundir})")


def markdown(r: dict) -> str:
    b, a = r.get("before") or {}, r.get("after") or {}
    rel = a.get("release") or {}
    lines = [f"## Installed upgrade {r['from']} → {r['to']} on a disposable KVM guest", "",
             f"**Result: {'PASSED' if r.get('passed') else 'FAILED'}** ({r.get('started_at')} → {r.get('finished_at')} UTC)", "",
             "**Rig.** Disposable KVM guest on oscar-main (Ubuntu 24.04 cloud image overlay, 4 vCPU, 8 GB, user-mode NAT, "
             f"loopback-only SSH). Root stock Hermes ({(r.get('golden') or {}).get('hermes')}) from the official installer "
             "(`--skip-setup`) + `hermes gateway install`; Tailscale joined to a local headscale with a pre-auth key "
             "(stands in for the owner's approval); a test-only `tailscale` wrapper simulates HTTPS turned on. "
             "Headscale has no Serve, so installs end box-only. Nothing ran on a real box. "
             f"Upgrade release base: {r.get('release_base')}. os.sh sha256 `{r.get('os_sh_sha256', '')[:16]}…`.", "",
             f"- Install {r['from']} (public command, agent-run, `WIZARD_STRICT=1`): "
             f"{(r.get('install_from') or {}).get('state')} in {(r.get('install_from') or {}).get('seconds')} s; "
             f"release.json {(b.get('release') or {}).get('release')} {(b.get('release') or {}).get('status')}.",
             f"- Upgrade to {r['to']}: {(r.get('upgrade') or {}).get('state')} in {(r.get('upgrade') or {}).get('seconds')} s"
             + (" (quick shell swap)" if (r.get('upgrade') or {}).get('quick') else "") + "; "
             f"release.json {rel.get('release')} {rel.get('status')}, {len(rel.get('checks', []))} checks, "
             f"{sum(1 for c in rel.get('checks', []) if not c.get('ok'))} failed.",
             f"- Hermes config.yaml/.env/SOUL.md: {'identical' if b.get('files') == a.get('files') else 'CHANGED'} "
             f"({', '.join(f'{k} `{v[:8]}…`' for k, v in (a.get('files') or {}).items())}).",
             f"- After: Hermes API /health {a.get('api')}, gateway {a.get('gateway')}, shell {a.get('shell')}, "
             f"`wizard doctor` FAIL {len(a.get('wizard_doctor_fail') or [])}, `wam doctor` FAIL {len(a.get('wam_doctor_fail') or [])}.",
             ""]
    if r.get("problems"):
        lines += ["**Problems:**", *[f"- {p}" for p in r["problems"]], ""]
    lines += ["<details><summary>Containers after the upgrade</summary>", "", "```", *a.get("containers", []), "```",
              "</details>", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("golden"); g.add_argument("--force", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("--from", dest="frm", required=True); r.add_argument("--to", required=True)
    r.add_argument("--release-base", help="WIZARD_RELEASE_BASE for the upgrade only (disclosed in the report)")
    r.add_argument("--keep", action="store_true", help="leave the guest running (debugging)")
    r.add_argument("--max-golden-age", type=float, default=7.0, help="days before the Hermes base is rebuilt")
    r.add_argument("--out", type=Path, help="also write the JSON report here")
    a = ap.parse_args()
    if a.cmd == "golden":
        golden(force=a.force)
        return 0
    rep = run(a.frm, a.to, a.release_base, a.keep, a.max_golden_age, a.out)
    print(json.dumps({k: rep.get(k) for k in ("passed", "problems", "rundir")}, indent=2))
    return 0 if rep.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
