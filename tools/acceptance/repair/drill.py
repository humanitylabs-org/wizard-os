#!/usr/bin/env python3
"""Broken-box drill for docs/REPAIR_KIT.md (wizard-os#93).

Builds a disposable Ubuntu VM with Lima, installs Wizard OS from the public installer, then breaks it in known ways
and repairs each break with ONLY the commands the repair kit prints for that failure. Every phase is
inject -> confirm broken -> kit recipe -> confirm recovered, with logs and a receipt.

Usage:
  drill.py LANE_ROOT RUN_ID [--release 0.3.32] [--seed-image PATH] [--keep] [--dry-run]

LANE_ROOT holds lima/ (LIMA_HOME), cache/ and evidence/<RUN_ID>/. --dry-run writes plan.json and runs nothing.
No host mounts, no credentials, no Tailscale login: the box is a plain fresh install. The VM is deleted at the end
unless --keep. Runs on the shared heavy worker (macOS + Lima); never against an owner's box.
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

UBUNTU_URL = ("https://cloud-images.ubuntu.com/releases/noble/release-20260615/"
              "ubuntu-24.04-server-cloudimg-arm64.img")
UBUNTU_SHA256 = "cafa1a965b591b7c4184b484ffd8e625981a79d48f9b4ae8a4adf7b4c5ade927"
if (platform.system(), platform.machine()) == ('Linux', 'x86_64'):
    VM_TYPE, VM_ARCH, IMAGE_ARCH = 'qemu', 'x86_64', 'amd64'
    UBUNTU_URL = UBUNTU_URL.replace('arm64.img', 'amd64.img')
    UBUNTU_SHA256 = '5fa5b05e5ec239858c4531485d6023b0896448c2df7c63b34f8dae6ea6051a44'
elif (platform.system(), platform.machine()) == ('Darwin', 'arm64'):
    VM_TYPE, VM_ARCH, IMAGE_ARCH = 'vz', 'aarch64', 'arm64'
else:
    raise RuntimeError('unsupported native acceptance host')
OS_SH = "https://aiwizards.com/os.sh"
OWNER = "wizard"

# Kit recipes, verbatim from docs/REPAIR_KIT.md (tools/tests/test_repair_drill.py keeps them in sync).
RECIPE_A_HEAL = "wam updates"
RECIPE_A_STATUS = "curl -fsSL https://aiwizards.com/os.sh | bash -s status"
RECIPE_A_START = "curl -fsSL https://aiwizards.com/os.sh | bash -s start"
RECIPE_C = "wam recover"
RECIPE_E_START = "wam app start files"
RECIPE_E_APPS = "wam apps"
RECIPE_F = "wam app restart hermes-agent"
DOCTOR = "wam doctor"

SHELL_C = "wizard-ux_wizardapps-wizard-ux-1"
AGENT_C = "wizard-agent-service_wizardapps-wizard-agent-service-1"
HERMES_C = "hermes-agent_wizardapps-hermes-agent-engine-1"

# Owner-side helpers prepended to every owner script: health URL of an app from ~/.wizard-os/apps.json, and
# "is this container running".
OWNER_PRELUDE = r'''
set -u
export PATH="$HOME/.local/bin:$PATH"
health_url() { python3 - "$1" <<'PY'
import json, sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
d = json.loads((Path.home() / ".wizard-os/apps.json").read_text())
rows = d.get("apps", d) if isinstance(d, dict) else d
rows = rows.values() if isinstance(rows, dict) else rows
for a in rows:
    if not isinstance(a, dict) or a.get("id") != sys.argv[1]:
        continue
    url = a.get("health")
    if not url and a["id"] == "files":
        # 0.3.32 Files has no manifest health field. Its MCP front proxies
        # /files/health to File Browser (not /health, and GET /mcp is 405).
        # Use the box-only published port, not view.url (may be relative/tailnet).
        u = urlsplit((a.get("mcp") or {}).get("url") or "")
        if u.scheme in ("http", "https") and u.netloc:
            url = urlunsplit((u.scheme, u.netloc, "/files/health", "", ""))
    if isinstance(url, str) and urlsplit(url).scheme in ("http", "https"):
        print(url)
        sys.exit(0)
raise SystemExit("no health URL for " + sys.argv[1])
PY
}
running() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ]; }
healthy() { u="$(health_url "$1")"; [ -n "$u" ] && curl -fsS -m 5 -o /dev/null "$u"; }
wait_healthy() {
  u="$(health_url "$1")" || return 1
  printf 'health probe %s: %s\n' "$1" "$u"
  for _ in $(seq 1 "${2:-60}"); do healthy "$1" && return 0; sleep 3; done
  printf 'health probe failed: %s\n' "$u" >&2
  return 1
}
install_state() { bash -c "$1" 2>/dev/null | sed -n 's/^Wizard OS install: //p' | head -1; }
'''


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def b64(script):
    return base64.b64encode(script.encode()).decode()


class Drill:
    def __init__(self, a):
        self.lane = Path(a.lane_root).resolve()
        self.run_id = a.run_id
        self.vm = "l8-repair-" + "".join(c for c in a.run_id.lower() if c.isalnum() or c == "-")[:24]
        assert self.vm.startswith("l8-repair-"), "refuse non-lane VM"
        self.release = a.release
        self.seed = Path(a.seed_image) if a.seed_image else None
        self.keep = a.keep
        self.dry = a.dry_run
        self.lima = self.lane / "lima"
        self.cache = self.lane / "cache"
        self.ev = self.lane / "evidence" / a.run_id
        self.receipt = {"run_id": a.run_id, "vm": self.vm, "LIMA_HOME": str(self.lima), "release": self.release,
                        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        "started": now(), "steps": [], "drills": {}}
        self.plan = []

    # ---- execution primitives -------------------------------------------------------------------------------
    def save(self):
        if not self.dry:
            (self.ev / "receipt.json").write_text(json.dumps(self.receipt, indent=2) + "\n")

    def run(self, name, argv, timeout=180, required=True):
        self.plan.append({"step": name, "timeout": timeout, "required": required, "argv": argv})
        if self.dry:
            return 0
        with (self.ev / (name + ".log")).open("w") as log:
            log.write(json.dumps(argv[:-1] + ["<guest script: see plan.json>"] if self.is_guest(argv) else argv)
                      + "\n")
            log.flush()
            try:
                rc = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                rc = 124
        self.receipt["steps"].append({"step": name, "exit": rc, "log": name + ".log", "at": now()})
        self.save()
        print(f"{name} {rc}", flush=True)
        if required and rc:
            raise RuntimeError(f"{name} failed: {rc}")
        return rc

    @staticmethod
    def is_guest(argv):
        return argv[:2] == ["limactl", "shell"]

    def _guest(self, name, script, runner, timeout, required):
        # The script goes to a file first: a command that reads stdin must never eat the rest of the script.
        f = f"/tmp/repair-drill-{name}.sh"
        argv = ["limactl", "shell", "--workdir", "/", self.vm, "--", "bash", "-lc",
                f"echo {b64(script)} | base64 -d > {f} && chmod 644 {f} && {runner} {f}"]
        rc = self.run(name, argv, timeout, required)
        self.plan[-1]["script"] = script
        return rc

    def guest_root(self, name, script, timeout=180, required=True):
        return self._guest(name, script, "sudo bash -l", timeout, required)

    def guest_owner(self, name, script, timeout=180, required=True):
        return self._guest(name, OWNER_PRELUDE + script, f"sudo -iu {OWNER} bash -l", timeout, required)

    # ---- one drill ------------------------------------------------------------------------------------------
    def drill(self, key, recipe, inject, broken, repair, recovered, repair_timeout=600, recover_timeout=600):
        """inject -> confirm broken -> kit recipe -> confirm recovered. Never aborts the run."""
        res = {"recipe": recipe, "started": now()}
        try:
            res["inject"] = self.guest_owner(f"{key}-1-inject", inject, 180, False)
            res["broken_confirmed"] = self.guest_owner(f"{key}-2-broken", broken, 240, False) == 0
            res["repair_exit"] = self.guest_owner(f"{key}-3-repair", repair, repair_timeout, False)
            res["recovered"] = self.guest_owner(f"{key}-4-recovered", recovered, recover_timeout, False) == 0
        except Exception as e:  # noqa: BLE001 - one drill failing must not hide the others
            res["error"] = str(e)[:300]
        res["pass"] = bool(res.get("inject") == 0 and res.get("broken_confirmed") and res.get("recovered"))
        res["finished"] = now()
        self.receipt["drills"][key] = res
        self.save()

    # ---- the run --------------------------------------------------------------------------------------------
    def image(self):
        img = self.cache / f"ubuntu-24.04-{IMAGE_ARCH}.img"
        if self.dry:
            self.plan.append({"step": "ubuntu-image", "seed": str(self.seed) if self.seed else None,
                              "url": UBUNTU_URL, "sha256": UBUNTU_SHA256, "dest": str(img)})
            return img

        def ok():
            if not img.is_file():
                return False
            with img.open("rb") as f:
                return hashlib.file_digest(f, "sha256").hexdigest() == UBUNTU_SHA256
        if not ok() and self.seed and self.seed.is_file():
            self.run("ubuntu-seed-copy", ["cp", str(self.seed), str(img)], 600)
        if not ok():
            self.run("ubuntu-download", ["curl", "-fL", "--retry", "2", "-o", str(img), UBUNTU_URL], 1800)
        if not ok():
            raise RuntimeError("Ubuntu image checksum mismatch")
        self.receipt["base_image_sha256"] = UBUNTU_SHA256
        return img

    def vm_yaml(self, img):
        return (f"vmType: {VM_TYPE}\narch: {VM_ARCH}\ncpus: 4\nmemory: 6GiB\ndisk: 40GiB\nimages:\n"
                f"- location: {json.dumps(str(img))}\n  arch: {VM_ARCH}\n  digest: sha256:{UBUNTU_SHA256}\n"
                "mounts: []\ncontainerd:\n  system: false\n  user: false\n"
                "portForwards:\n- guestIP: 127.0.0.1\n  guestPortRange: [1, 65535]\n  ignore: true\n"
                "- guestIP: 0.0.0.0\n  guestPortRange: [1, 65535]\n  ignore: true\n")

    def main(self):
        for d in (self.lima, self.cache, self.ev):
            if not self.dry:
                d.mkdir(parents=True, exist_ok=True)
        os.environ.update(LIMA_HOME=str(self.lima), TMPDIR=str(self.cache),
                          PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
        created = False
        try:
            self.run("host-preflight", ["bash", "-lc", "df -h /; df -h \"$LIMA_HOME\"; "
                                        + ("free -m; " if VM_TYPE == "qemu" else "sysctl hw.memsize; ") +
                                        "limactl --version; limactl list"], 60)
            if (self.lima / self.vm).exists():
                raise RuntimeError(f"{self.vm} already exists; inspect it, then delete it or pick a new RUN_ID")
            img = self.image()
            cfg = self.ev / "vm.yaml"
            if not self.dry:
                cfg.write_text(self.vm_yaml(img))
            self.run("vm-start", ["limactl", "start", "--tty=false", "--name=" + self.vm, str(cfg)], 900)
            created = True
            self.guest_root("fresh-baseline", "cat /etc/os-release; df -h /; free -m; "
                            "if command -v hermes || test -d /root/.hermes; then echo NOT_FRESH; exit 9; fi; "
                            "echo FRESH_NO_HERMES")
            # The public command, detached, with only a release selector; then wait on its own status command.
            self.guest_root("install-start", f"set -o pipefail; curl -fsSL {OS_SH} | sha256sum; "
                            f"curl -fsSL {OS_SH} | env WIZARD_RELEASE={self.release} WIZARD_TAILSCALE_WAIT=1 "
                            "bash -s start", 300)
            self.guest_root("install-wait", f'''
for i in $(seq 1 270); do
  out="$(curl -fsSL {OS_SH} | bash -s status 2>&1)"; st="$(printf '%s\\n' "$out" | sed -n 's/^Wizard OS install: //p' | head -1)"
  case "$st" in running|needs_owner) sleep 10 ;; *) break ;; esac
done
printf '%s\\n' "$out"; tail -n 40 /root/.wizard-os/install.log 2>/dev/null
[ "$st" = done ]''', 2900)
            self.guest_owner("baseline-readback", "cat ~/.wizard-os/release.json; "
                             "docker ps -a --format '{{.Names}} {{.Status}}'; " + DOCTOR + " || true", 300)
            self.guest_owner("baseline-healthy", f"running {SHELL_C} && running {AGENT_C} && running {HERMES_C} "
                             "&& wait_healthy wizard-ux 20 && wait_healthy wizard-agent-service 20 "
                             "&& wait_healthy files 20", 300)

            # C. Shell won't load / "Wizard needs attention"
            self.drill("C-shell-down", "docs/REPAIR_KIT.md#c-shell-wont-load--wizard-needs-attention",
                       inject=f"docker stop {SHELL_C} {AGENT_C}",
                       broken=f"! running {SHELL_C} && ! running {AGENT_C} && ! healthy wizard-ux",
                       repair=f"{RECIPE_C}",
                       recovered=f"running {SHELL_C} && running {AGENT_C} && wait_healthy wizard-ux 60 "
                                 "&& wait_healthy wizard-agent-service 60")
            # F. Hermes not answering (fresh box)
            self.drill("F-hermes-down", "docs/REPAIR_KIT.md#f-hermes-not-answering",
                       inject=f"docker stop {HERMES_C}",
                       broken=f"! running {HERMES_C}",
                       repair=f"{RECIPE_F}",
                       recovered=f"for _ in $(seq 1 40); do running {HERMES_C} && "
                                 f"docker ps --filter name={HERMES_C} --format '{{{{.Status}}}}' && exit 0; sleep 3; "
                                 "done; exit 1")
            # E. An app screen won't open inside Wizard
            self.drill("E-app-screen", "docs/REPAIR_KIT.md#e-an-app-screen-wont-open-inside-wizard",
                       inject="docker stop $(docker ps --format '{{.Names}}' | grep '^files_wizardapps-files-')",
                       broken="! healthy files",
                       repair=f"{RECIPE_E_START} && {RECIPE_E_APPS}",
                       recovered="wait_healthy files 60")
            # A. Update stuck on "installing" (#90): a status left `running` by a runner that died, plus its lock.
            self.drill("A-stuck-installing", "docs/REPAIR_KIT.md#a-update-stuck-on-installing",
                       inject=r'''
cd ~/.wizard-os && cp -p install-status.json install-status.before-drill.json 2>/dev/null || true
sh -c 'exit 0' & dead=$!; wait $dead
python3 - "$dead" <<'PY'
import json, sys, time
from pathlib import Path
p = Path.home() / ".wizard-os/install-status.json"
t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
st = {"state": "running", "step": "apps", "pid": int(sys.argv[1]), "started_at": t, "updated_at": t,
      "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "message": "drill: runner killed"}
p.write_text(json.dumps(st, indent=2) + "\n"); p.chmod(0o600)
PY
: > install.lock; chmod 600 install.lock''',
                       broken="python3 -c \"import json,pathlib;"
                              "s=json.loads((pathlib.Path.home()/'.wizard-os/install-status.json').read_text());"
                              "assert s['state']=='running', s\" && test -e ~/.wizard-os/install.lock",
                       repair=f'''set -e
{RECIPE_A_HEAL} || echo "(wam updates exited $?; its heal still ran)"
python3 -c "import json,pathlib;s=json.loads((pathlib.Path.home()/'.wizard-os/install-status.json').read_text());print('after heal:',s['state']);assert s['state']=='interrupted'"
test ! -e ~/.wizard-os/install.lock && echo "stale lock removed"
{RECIPE_A_STATUS}
{RECIPE_A_START.replace("bash -s start", f"WIZARD_RELEASE={self.release} bash -s start")}''',
                       recovered=f'''
for i in $(seq 1 270); do
  st="$(install_state "{RECIPE_A_STATUS}")"
  case "$st" in running|needs_owner) sleep 10 ;; *) break ;; esac
done
echo "final: $st"; {RECIPE_A_STATUS}; grep -o '"version": *"[^"]*"' ~/.wizard-os/release.json | head -1
[ "$st" = done ] && wait_healthy wizard-ux 60''', repair_timeout=600, recover_timeout=2900)

            self.guest_owner("final-doctor", DOCTOR, 300, False)
            self.guest_owner("final-readback", "docker ps -a --format '{{.Names}} {{.Status}}'; "
                             "cat ~/.wizard-os/install-status.json", 120, False)
            passed = [k for k, v in self.receipt["drills"].items() if v.get("pass")]
            self.receipt["state"] = "pass" if len(passed) == len(self.receipt["drills"]) else "drills-failed"
        except Exception:
            self.receipt["state"] = "failed"
            self.receipt["error"] = traceback.format_exc()[-2000:]
        finally:
            if created:
                self.run("vm-stop", ["limactl", "stop", "--force", self.vm], 300, False)
                if not self.keep:
                    self.run("vm-delete", ["limactl", "delete", "--force", self.vm], 300, False)
            self.receipt["finished"] = now()
            if self.dry:
                self.receipt["state"] = "dry-run"
                out = Path(os.environ.get("DRILL_PLAN_OUT") or (self.ev / "plan.json"))
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({"vm": self.vm, "release": self.release, "plan": self.plan}, indent=1)
                               + "\n")
                print(f"dry run: {len(self.plan)} steps -> {out}")
            else:
                self.save()
                self.write_md()
                print(json.dumps({k: self.receipt[k] for k in ("state", "drills")}, indent=2))
        return 0 if self.receipt["state"] in ("pass", "dry-run") else 1

    def write_md(self):
        rows = "\n".join(f"| {k} | `{v.get('recipe')}` | {v.get('broken_confirmed')} | {v.get('repair_exit')} | "
                         f"{v.get('recovered')} | **{'PASS' if v.get('pass') else 'FAIL'}** |"
                         for k, v in self.receipt["drills"].items())
        (self.ev / "RECEIPT.md").write_text(
            f"# Repair-kit drill {self.run_id}\n\nVM `{self.vm}`, Wizard OS {self.release} from the public installer, "
            f"state **{self.receipt.get('state')}**.\n\n| Drill | Recipe | Broken confirmed | Repair exit | "
            f"Recovered | Result |\n|---|---|---|---|---|---|\n{rows}\n\nLogs: one `<step>.log` per step; "
            "`receipt.json` has exits and timestamps.\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lane_root"); ap.add_argument("run_id")
    ap.add_argument("--release", default="0.3.32")
    ap.add_argument("--seed-image", default=None, help="an already-downloaded copy of the pinned Ubuntu image")
    ap.add_argument("--keep", action="store_true", help="keep the VM for inspection")
    ap.add_argument("--dry-run", action="store_true", help="write plan.json, run nothing")
    if shutil.which("limactl") is None and not any(a == "--dry-run" for a in sys.argv):
        os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ.get("PATH", "")
    sys.exit(Drill(ap.parse_args()).main())
