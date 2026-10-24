#!/usr/bin/env python3
"""wizard-os#90 acceptance: updates that are cut short by a reboot must not strand the box.

Usage:
  update_reboot.py q2 EVIDENCE_ROOT LIMA_HOME VM [FROM=0.3.32] [TO=0.3.33]
      Fresh Ubuntu VM -> public install of FROM -> `wam updates --apply` to TO (latest channel) ->
      hard-stop the VM mid-update -> boot -> record what the box says (raw status, wam updates, installer
      status, stock doctor, candidate doctor) -> passive wait (does it retry by itself?) -> Update button
      (`wam updates --apply`) -> bounded wait for TO.
  update_reboot.py q3 EVIDENCE_ROOT LIMA_HOME VM [TO=0.3.32]
      The box already stuck on an older release: snapshot its stale state, show stock behaviour, rerun the
      public installer (`os.sh | WIZARD_RELEASE=TO bash -s start`) as the owner, bounded wait, read back.
  update_reboot.py dry-run ...   Print the plan for q2/q3 without touching any VM.

Env: WAM_CANDIDATE_TGZ (optional) = tarball containing a wizard-app-manager `wam/` package; its
install_state/status/retry are run against a COPY of the box's state (retry runner stubbed).
WAM_CANDIDATE_APPLY=1 additionally requires get.sh in that archive and executes the candidate CLI and
bootstrap during q2, from a separate cache directory in the newly-created disposable VM only.
Candidate acceptance requires interruption reporting, a retry that starts,
a verified successful final receipt, and a passing final doctor; it does not accept a failed install's version.
WAM_CANDIDATE_COMMIT selects a pushed WAM source SHA in a separately recorded TO manifest copy so
install.sh fixes are really executed. Only that source pin changes; images/default apps remain original.
This is candidate-bootstrap QA, never exact-release acceptance: the original-source comparison stays red.
The completed FROM receipt stays stock; only the TO mirror substitutes the candidate WAM pin.
Before starting the update, validate and sync the completed base and QA fixture, then sync the host.
After the cut, verify their hashes before executing WAM; never restore them or sync in-flight update writes.
Every updates call must emit JSON; combined stdout/stderr and its exit code are retained on failure.
Never touches a VM whose name does not start with `l4-`. No host credentials, no model calls.
"""
import datetime, json, os, re, shlex, subprocess, sys, time, traceback
from pathlib import Path

mode = sys.argv[1]
dry = mode == 'dry-run'
if dry:
    mode = sys.argv[2]
    sys.argv = sys.argv[:1] + sys.argv[2:]
root, lima, vm = Path(sys.argv[2]), sys.argv[3], sys.argv[4]
extra = sys.argv[5:]
assert mode in ('q2', 'q3'), mode
assert vm.startswith('l4-'), 'refuse non-lane VM'
FROM = extra[0] if mode == 'q2' and extra else '0.3.32'
TO = (extra[1] if len(extra) > 1 else '0.3.33') if mode == 'q2' else (extra[0] if extra else '0.3.32')
OS_SH = 'https://aiwizards.com/os.sh'
IMAGE_SHA = 'cafa1a965b591b7c4184b484ffd8e625981a79d48f9b4ae8a4adf7b4c5ade927'
IMAGE_URL = 'https://cloud-images.ubuntu.com/releases/noble/release-20260615/ubuntu-24.04-server-cloudimg-arm64.img'
CAND = os.environ.get('WAM_CANDIDATE_TGZ', '')
APPLY_CANDIDATE = os.environ.get('WAM_CANDIDATE_APPLY') == '1'
assert not APPLY_CANDIDATE or CAND, 'candidate application requires WAM_CANDIDATE_TGZ'
CANDIDATE_COMMIT = os.environ.get('WAM_CANDIDATE_COMMIT', '')
assert not CANDIDATE_COMMIT or re.fullmatch('[0-9a-f]{40}', CANDIDATE_COMMIT), 'candidate commit must be a full SHA'
assert not CANDIDATE_COMMIT or APPLY_CANDIDATE, 'candidate source requires candidate application'
os.environ.update(LIMA_HOME=lima, PATH='/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', ''))
receipt = {'mode': mode, 'vm': vm, 'LIMA_HOME': lima, 'from': FROM if mode == 'q2' else None, 'to': TO,
           'candidate': CAND or None, 'candidate_applied': APPLY_CANDIDATE,
           'candidate_source_commit': CANDIDATE_COMMIT or None, 'release_exact': not APPLY_CANDIDATE,
           'started': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'steps': [], 'observations': {}}
PLAN = []


def save():
    if not dry:
        (root / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


def run(name, argv, timeout=300, required=True):
    if dry:
        PLAN.append({'step': name, 'timeout': timeout, 'argv': argv}); return 0
    with (root / (name + '.log')).open('w') as log:
        log.write(json.dumps(argv) + '\n'); log.flush()
        try:
            rc = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            rc = 124
    receipt['steps'].append({'step': name, 'exit': rc, 'log': name + '.log'})
    save(); print(name, rc, flush=True)
    if required and rc:
        raise RuntimeError(f'{name} failed: {rc}')
    return rc


def guest(name, cmd, timeout=300, required=True):
    return run(name, ['limactl', 'shell', '--workdir', '/', vm, '--', 'bash', '-lc', cmd], timeout, required)


def owner(name, cmd, timeout=300, required=True):
    # sudo -i re-quotes its command through the login shell, expanding $p before the
    # inner bash assigns it. Use a single command shell as the owner instead.
    inner = 'export PATH=$HOME/.local/bin:$PATH; '
    inner += 'export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus; '
    if APPLY_CANDIDATE:
        inner += ('export PATH=$HOME/.cache/wam-update-candidate/bin:$PATH; '
                  'export WIZARD_GET_SH_URL=file://$HOME/.cache/wam-update-candidate/src/get.sh; '
                  'export WIZARD_TAILSCALE_WAIT=1; ')
        if CANDIDATE_COMMIT:
            # Baseline install precedes activation; only subsequent updates use the mirror.
            inner += ('if [ -d "$HOME/.cache/wam-update-candidate/releases" ]; then '
                      'export WIZARD_RELEASE_BASE=file://$HOME/.cache/wam-update-candidate/releases; fi; ')
    return guest(name, 'sudo -u wizard -H bash -c ' + shlex.quote(inner + cmd), timeout, required)


def activate_candidate():
    """Opt-in execution of the candidate in this disposable VM only; installed release files stay stock."""
    if not APPLY_CANDIDATE:
        return
    run('candidate-activation-copy', ['limactl', 'copy', CAND, f'{vm}:/tmp/wam-update-candidate.tgz'], 120)
    guest('candidate-activation-owner',
          'sudo install -o wizard -m 600 /tmp/wam-update-candidate.tgz /home/wizard/wam-update-candidate.tgz', 60)
    runner = ('import sys\nfrom pathlib import Path\nfrom wam import updates, cli\n'
              'updates.INSTALLER = (Path(__file__).parent / "get.sh").as_uri()\n'
              'sys.exit(cli.main())\n')
    wrapper = ('#!/bin/bash\nexport WIZARD_RELEASE_PINS="${WIZARD_RELEASE_PINS-$HOME/.wizard-os/release-pins.json}"\n'
               'cd "$HOME/.cache/wam-update-candidate/src" || exit 1\n'
               'exec /usr/bin/python3 runner.py "$@"\n')
    owner('candidate-activate',
          'set -e; d=$HOME/.cache/wam-update-candidate; mkdir -p "$d/src" "$d/bin"; '
          'tar -xzf "$HOME/wam-update-candidate.tgz" -C "$d/src"; '
          'printf %s ' + shlex.quote(runner) + ' > "$d/src/runner.py"; '
          'printf %s ' + shlex.quote(wrapper) + ' > "$d/bin/wam"; chmod 700 "$d/bin/wam"; '
          'test -f "$d/src/get.sh"; sha256sum "$HOME/wam-update-candidate.tgz"; '
          'command -v wam; wam updates', 180)
    if CANDIDATE_COMMIT:
        # get.sh checks out the manifest's WAM commit before running install.sh.
        # A CLI-only archive does NOT exercise installer fixes in that checkout.
        # Use an explicitly non-release mirror, changing only the WAM source pin.
        stage = ('import copy,hashlib,json\nfrom pathlib import Path\n'
                 'd=Path.home()/".cache/wam-update-candidate"\n'
                 'raw=(d/"original-release.json").read_bytes()\n'
                 'original=json.loads(raw); candidate=copy.deepcopy(original)\n'
                 'old=candidate["components"]["wizard-app-manager"]["commit"]\n'
                 'candidate["components"]["wizard-app-manager"]["commit"]=' + repr(CANDIDATE_COMMIT) + '\n'
                 'base_raw=(d/"base-release.json").read_bytes()\n'
                 'assert json.loads(base_raw)["version"]=='+repr(FROM)+'\n'
                 'p=d/"releases"; p.mkdir()\n'
                 '(p/'+repr(FROM+'.json')+').write_bytes(base_raw)\n'
                 '(p/(candidate["version"]+".json")).write_text(json.dumps(candidate))\n'
                 '(p/"latest").write_text(candidate["version"]+"\\n")\n'
                 'record={"kind":"candidate-bootstrap-not-release-acceptance","release_exact":False,\n'
                 ' "original_manifest_sha256":hashlib.sha256(raw).hexdigest(),\n'
                 ' "source_exception":{"expected":old,"candidate":' + repr(CANDIDATE_COMMIT) + ',"ok":False}}\n'
                 '(d/"candidate-exception.json").write_text(json.dumps(record,indent=2)+"\\n")\n'
                 'print(json.dumps(record))\n')
        owner('candidate-source-stage',
              'set -e; d=$HOME/.cache/wam-update-candidate; curl -fsSL '
              'https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/main/releases/'
              + shlex.quote(TO + '.json') + ' -o "$d/original-release.json"; curl -fsSL '
              'https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/main/releases/'
              + shlex.quote(FROM + '.json') + ' -o "$d/base-release.json"; python3 -c ' + shlex.quote(stage)
              + '; curl -fsSL https://raw.githubusercontent.com/humanitylabs-org/wizard-app-manager/main/releases/stable'
              ' -o "$d/releases/stable"', 180)
        observe('candidate_source_exception', as_json('candidate-source-stage'))


def out(name):
    try:
        return (root / (name + '.log')).read_text().split('\n', 1)[1]
    except (OSError, IndexError):
        return ''


def as_json(name):
    t = out(name)
    try:
        return json.loads(t[t.index('{'):t.rindex('}') + 1])
    except ValueError:
        return None


def observe(key, value):
    receipt['observations'][key] = value; save()


RAW = ('for f in install-status.json release.json release-pins.json updates.json install-outcome.json; do '
       'p=$HOME/.wizard-os/$f; [ -f "$p" ] && { echo "FILE $f"; cat "$p"; echo; }; done; '
       'ls -la $HOME/.wizard-os/install.lock $HOME/.wizard-os/install.start.lock 2>&1; '
       'echo BOOT_ID $(cat /proc/sys/kernel/random/boot_id); grep ^btime /proc/stat; '
       'tail -n 30 $HOME/.wizard-os/install.log 2>/dev/null')


def raw(name):
    """Read-only: the files as they are, before any wam call can heal them."""
    owner(name, RAW, 120, required=False)
    t = out(name)
    try:
        i = t.index('FILE install-status.json') + len('FILE install-status.json')
        return json.loads(t[i:t.index('\n}', i) + 2])
    except ValueError:
        return None


def candidate(name):
    """The fix under review, on a COPY of the box's state (the live files are untouched)."""
    if not CAND:
        return None
    if not dry:
        run(name + '-copy', ['limactl', 'copy', CAND, f'{vm}:/tmp/wam-candidate.tgz'], 120, required=False)
    py = ('import json, sys, subprocess; from pathlib import Path; d = Path.home() / ".cache/wam-candidate"; '
          'sys.path.insert(0, str(d / "src")); from wam import updates; h = d / "home"; '
          'retry = updates.apply(h, runner=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, "", "")); '
          'print(json.dumps({"install_state": updates.install_state(h), "updates": updates.status(h), "retry": retry, '
          '"status_after": json.loads((h / "install-status.json").read_text()) '
          'if (h / "install-status.json").exists() else None, "lock_left": (h / "install.lock").exists()}))')
    cmd = ('d=$HOME/.cache/wam-candidate; rm -rf "$d" && mkdir -p "$d/src" "$d/home" && '
           'tar -xzf ~/wam-candidate.tgz -C "$d/src" && '
           'for f in install-status.json install.lock install.start.lock release.json release-pins.json updates.json; do '
           '[ ! -e $HOME/.wizard-os/$f ] || cp -p $HOME/.wizard-os/$f "$d/home/"; done; '
           '/usr/bin/python3 -c ' + shlex.quote(py))
    guest(name, 'sudo install -o wizard -m 600 /tmp/wam-candidate.tgz /home/wizard/wam-candidate.tgz && '
          'sudo -u wizard -H bash -c ' + shlex.quote(cmd), 180, False)
    return as_json(name)


def wam_json(name, args='updates', timeout=180):
    # An empty executable is a successful shell no-op, not a successful WAM call.
    # Keep the command's stderr and exit status even when no JSON was emitted.
    rc = owner(name, 'wam ' + args + '; rc=$?; printf "\\nWAM_COMMAND_RC=%s\\n" "$rc" >&2; exit "$rc"',
               timeout, required=False)
    value = as_json(name)
    if not dry and (rc or not isinstance(value, dict)):
        raise RuntimeError(f'{name}: wam {args} exit={rc}, no valid JSON object; inspect {name}.log (stdout + stderr)')
    return value


def updates_state(name):
    return wam_json(name)


def durable_fixture():
    """Flush the completed base + QA fixture BEFORE launching the update under test.

    A fresh install and candidate activation can finish seconds before the cut. Without
    this boundary ext4 may retain names but lose their dirty data: even an empty shell
    wrapper then exits 0. Never sync once the update has begun; its crash writes remain
    part of the test. The inventory detects fixture corruption without repairing it.
    """
    check = ('import hashlib,json\nfrom pathlib import Path\n'
             'h=Path.home(); state=h/".wizard-os"; d=h/".cache/wam-update-candidate"\n'
             'r=json.loads((state/"release.json").read_text())\n'
             'assert r.get("release")=='+repr(FROM)+' and r.get("status") in ("pinned","drift"), r\n'
             'assert json.loads((state/"updates.json").read_text()).get("channel")=="latest"\n'
             'files=[state/"release.json",state/"updates.json"]\n')
    if APPLY_CANDIDATE:
        check += ('files += [d/"bin/wam", d/"src/runner.py", d/"src/get.sh", d/"src/wam/cli.py", '
                  'd/"src/wam/updates.py", d/"src/wam/__init__.py"]\n')
        # __init__.py may deliberately be empty. Executables and entrypoints may not.
        check += ('assert all(p.stat().st_size for p in files if p.name!="__init__.py")\n')
        if CANDIDATE_COMMIT:
            check += ('files += [d/"original-release.json",d/"base-release.json",d/"candidate-exception.json",'
                      'd/"releases"/'+repr(FROM+'.json')+',d/"releases"/'+repr(TO+'.json')+',d/"releases/latest",d/"releases/stable"]\n'
                      'assert (d/"releases"/'+repr(FROM+'.json')+').read_bytes()==(d/"base-release.json").read_bytes()\n'
                      'assert json.loads((d/"base-release.json").read_text())["version"]=='+repr(FROM)+'\n'
                      'pins=json.loads((d/"releases"/'+repr(TO+'.json')+').read_text())\n'
                      'assert pins["components"]["wizard-app-manager"]["commit"]=='+repr(CANDIDATE_COMMIT)+'\n')
    check += ('inventory={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}\n'
              '(state/"qa-fixture-sha256.json").write_text(json.dumps(inventory))\n'
              'print(json.dumps({"base_receipt":r,"fixture_sha256":inventory}))\n')
    owner('fixture-before-update', 'set -e; python3 -c ' + shlex.quote(check) + '; sync', 180)
    run('fixture-host-sync', ['sync'], 120)
    observe('fixture_before_update', as_json('fixture-before-update'))
    st = updates_state('updates-before-cut') or {}
    if not dry and (st.get('installed') != FROM or st.get('channel') != 'latest' or st.get('failed')):
        raise RuntimeError(f'candidate activation invalidated the completed base: {st}')


def verify_fixture_after_reboot():
    check = ('import hashlib,json\nfrom pathlib import Path\n'
             'p=Path.home()/".wizard-os/qa-fixture-sha256.json"\n'
             'inventory=json.loads(p.read_text())\n'
             'bad=[name for name,digest in inventory.items() if not Path(name).is_file() '
             'or hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest]\n'
             'print(json.dumps({"fixture_files":len(inventory),"changed_or_missing":bad}))\n'
             'assert not bad, "completed base or QA fixture corrupted by power cut"\n')
    owner('fixture-after-reboot', 'python3 -c ' + shlex.quote(check), 120)
    observe('fixture_after_reboot', as_json('fixture-after-reboot'))


def wait_for(name, release, limit, apply_note=None):
    """Bounded poll; records the last `wam updates` answer. Never edits install state."""
    t0, last, n = time.time(), None, 0
    if dry:
        PLAN.append({'step': name, 'poll': f'wam updates every 30 s up to {limit} s until installed == {release}'})
        return False
    while time.time() - t0 < limit:
        n += 1
        st = updates_state(f'{name}-{n:03d}')
        if st:
            last = st
            if st.get('installed') == release and not st.get('installing'):
                break
        time.sleep(30)
    observe(name, {'last': last, 'polls': n, 'seconds': round(time.time() - t0)})
    return bool(last) and last.get('installed') == release and not last.get('installing')


def create_vm():
    run('host-preflight', ['bash', '-lc', 'df -h / /Volumes/ThalesMedia; sysctl hw.memsize; limactl list'], 60)
    if not dry and Path(lima, vm).exists():
        raise RuntimeError('refuse to overwrite an existing VM; inspect the receipt first')
    cache = root / 'cache'
    image = cache / 'ubuntu-24.04-arm64.img'
    seed = os.environ.get('L4_UBUNTU_IMAGE_SEED', '')
    if not dry:
        cache.mkdir(parents=True, exist_ok=True)
    if dry or (not image.exists() and seed and Path(seed).is_file()):
        run('ubuntu-seed-copy', ['cp', seed or '<seed>', str(image)], 300, required=False)
    if dry or not image.exists():
        run('ubuntu-download', ['curl', '-fL', '--retry', '3', '-o', str(image), IMAGE_URL], 2700)
    run('ubuntu-sha256', ['bash', '-lc', f'shasum -a 256 {shlex.quote(str(image))} | grep -q {IMAGE_SHA}'], 300)
    cfg = root / 'vm.yaml'
    text = (f'vmType: vz\narch: aarch64\ncpus: 4\nmemory: 6GiB\ndisk: 40GiB\nimages:\n- location: {image}\n'
            f'  arch: aarch64\n  digest: sha256:{IMAGE_SHA}\nmounts: []\ncontainerd:\n  system: false\n  user: false\n'
            'portForwards:\n- guestPort: 8796\n  hostPort: 18806\n- guestPortRange: [1, 65535]\n  ignore: true\n')
    if not dry:
        cfg.write_text(text)
    run('vm-create', ['limactl', 'start', '--tty=false', '--name=' + vm, str(cfg)], 900)
    guest('fresh-baseline', 'cat /etc/os-release | head -2; command -v hermes && exit 9; echo FRESH_NO_HERMES', 120)


def install(release):
    guest('public-install', 'set -o pipefail; mkdir -p ~/evidence; curl -fsSL ' + OS_SH + ' -o ~/evidence/os.sh; '
          'sha256sum ~/evidence/os.sh; curl -fsSL ' + OS_SH + f' | sudo env WIZARD_RELEASE={release} '
          'WIZARD_TAILSCALE_WAIT=1 bash', 2400, False)
    st = updates_state('updates-after-install')
    observe('installed_after_install', (st or {}).get('installed'))
    if not dry and (st or {}).get('installed') != release:
        raise RuntimeError(f'box is not on {release} after the public install: {st}')


def hard_reboot(tag):
    run(f'{tag}-hard-stop', ['limactl', 'stop', '-f', vm], 300)      # power cut: no clean shutdown
    run(f'{tag}-start', ['limactl', 'start', '--tty=false', vm], 900)


def q2():
    create_vm()
    install(FROM)
    owner('channel-latest', 'wam updates --channel latest', 120)       # TO is a latest-channel release
    owner('doctor-before', 'wam doctor', 300, required=False)
    activate_candidate()
    durable_fixture()
    a = wam_json('update-apply', 'updates --apply', 900)
    observe('apply_started', (a or {}).get('started'))
    if not dry and not (a or {}).get('started'):
        raise RuntimeError(f'the update did not start: {a}')
    # Cut only a proved active target, never a timed-out wait or an already-completed update.
    mid = ('import json,time\nfrom pathlib import Path\nh=Path.home()/".wizard-os"\n'
           'for i in range(120):\n'
           ' try:\n'
           '  s=json.loads((h/"install-status.json").read_text())\n'
           '  p=json.loads((h/"release-pins.json").read_text())\n'
           ' except (OSError,ValueError):\n'
           '  time.sleep(0.5); continue\n'
           ' print(i,s.get("state"),s.get("step"),flush=True)\n'
           ' if s.get("state") in ("running","needs_owner") and s.get("step") != "starting" '
           'and p.get("version") == ' + repr(TO) + ':\n'
           '  time.sleep(5); raise SystemExit(0)\n'
           ' time.sleep(0.5)\nraise SystemExit(3)\n')
    owner('mid-update-wait', 'python3 -c ' + shlex.quote(mid), 90)
    before_cut = raw('status-before-cut')
    if not dry and (not before_cut or before_cut.get('state') not in ('running', 'needs_owner')):
        raise RuntimeError('no active installer at the cut point')
    hard_reboot('cut')
    observe('raw_after_reboot', raw('raw-after-reboot'))             # before any wam call can heal it
    verify_fixture_after_reboot()
    observe('candidate_after_reboot', candidate('candidate-after-reboot'))
    owner('installer-status-after-reboot', f'curl -fsSL {OS_SH} | bash -s status', 120, required=False)
    owner('doctor-after-reboot', 'wam doctor', 300, required=False)
    doctor_caught = 'FAIL  Wizard OS update completed' in out('doctor-after-reboot')
    observe('doctor_after_reboot', {'exit': receipt['steps'][-1]['exit'] if not dry else None,
                                    'mentions_update': doctor_caught})
    s = updates_state('updates-after-reboot')
    observe('updates_after_reboot', s)
    observe('raw_after_wam_updates', raw('raw-after-wam-updates'))
    # Does it carry on by itself? (Ask me is the default mode; the nightly timer only exists in Automatic.)
    observe('self_recovered', wait_for('passive-wait', TO, 600))
    owner('timers', 'systemctl --user list-timers --all | grep -i wizard || true; cat ~/.wizard-os/updates.json', 60, False)
    observe('reapply', wam_json('update-reapply', 'updates --apply', 900))
    ok = wait_for('recovery-wait', TO, 2700)
    observe('recovered_to', ok)
    owner('installer-status-final', f'curl -fsSL {OS_SH} | bash -s status', 120, required=False)
    final_doctor = owner('doctor-final', 'wam doctor', 300, required=False)
    final_status = raw('raw-final')
    verify = ('import json\nfrom pathlib import Path\nh=Path.home()/".wizard-os"\n'
              'r=json.loads((h/"release.json").read_text())\n'
              's=json.loads((h/"install-status.json").read_text())\n'
              'print(json.dumps({"receipt":r,"installer":s}))\n'
              'assert r.get("release") == ' + repr(TO) + ' and r.get("status") in ("pinned","drift")\n'
              'assert s.get("state") == "done"\n'
              'assert all(c["ok"] for c in r["checks"] if c.get("core"))\n'
              'assert any(c["name"] == "image wizard-agent-service" and c["ok"] for c in r["checks"])\n')
    final_readback = owner('verified-final-receipt', 'python3 -c ' + shlex.quote(verify), 120, False)
    if CANDIDATE_COMMIT:
        # Keep the public release comparison red, separately from candidate success.
        comparison = ('import json\nfrom pathlib import Path\n'
                      'd=Path.home()/".cache/wam-update-candidate"\n'
                      'r=json.loads((Path.home()/".wizard-os/release.json").read_text())\n'
                      'exception=json.loads((d/"candidate-exception.json").read_text())\n'
                      'c=next(c for c in r["checks"] if c["name"]=="wizard-app-manager commit")\n'
                      'assert c["observed"]==' + repr(CANDIDATE_COMMIT) + '\n'
                      'c.update(expected=exception["source_exception"]["expected"],ok=False)\n'
                      'r.update(status="mismatch",release_exact=False,candidate_exception=exception)\n'
                      'print(json.dumps(r))\n')
        owner('original-release-readback', 'python3 -c ' + shlex.quote(comparison), 120)
        observe('original_release_readback', as_json('original-release-readback'))
    if APPLY_CANDIDATE:
        recovered = as_json('update-reapply') or {}
        ok = (ok and doctor_caught and bool(s) and s.get('interrupted') is True
              and s.get('installed') == FROM and s.get('latest') == TO
              and s.get('update_available') is True and s.get('unpinned') is False
              and recovered.get('started') is True and final_readback == 0 and final_doctor == 0)
    observe('candidate_acceptance_passed', ok if APPLY_CANDIDATE else None)
    return ok


def q3():
    run('vm-status', ['limactl', 'list', vm], 60)
    if not dry and ' Running ' not in out('vm-status'):
        run('vm-start', ['limactl', 'start', '--tty=false', vm], 900)
    observe('raw_stuck', raw('raw-stuck'))                           # the stuck evidence, byte for byte
    guest('snapshot-stuck', 'sudo tar -C /home/wizard -czf /tmp/stuck-wizard-os.tgz .wizard-os/install-status.json '
          '.wizard-os/install.log .wizard-os/release.json 2>/dev/null; sudo chmod 644 /tmp/stuck-wizard-os.tgz', 60, False)
    run('snapshot-copy', ['limactl', 'copy', f'{vm}:/tmp/stuck-wizard-os.tgz', str(root / 'stuck-wizard-os.tgz')], 60, False)
    observe('candidate_on_stuck', candidate('candidate-on-stuck'))
    owner('doctor-stuck', 'wam doctor', 300, required=False)
    observe('updates_stuck', updates_state('updates-stuck'))
    owner('apply-stuck', 'wam updates --apply', 300, required=False)
    observe('apply_stuck', as_json('apply-stuck'))
    owner('installer-status-stuck', f'curl -fsSL {OS_SH} | bash -s status', 120, required=False)
    # The way out under test: the public installer rerun, as the owner (what `wam updates --apply` runs).
    owner('installer-start', f'curl -fsSL {OS_SH} | WIZARD_RELEASE={TO} bash -s start', 600, required=False)
    observe('installer_start_said', out('installer-start')[-1500:])
    observe('raw_after_start', raw('raw-after-start'))
    ok = wait_for('installer-wait', TO, 2700)
    observe('landed_on', ok)
    owner('installer-status-final', f'curl -fsSL {OS_SH} | bash -s status', 120, required=False)
    owner('doctor-final', 'wam doctor', 300, required=False)
    owner('version-final', 'cat ~/.wizard-os/release.json', 120, required=False)
    raw('raw-final')
    # A clean reboot afterwards must not resurrect "installing".
    run('vm-stop', ['limactl', 'stop', vm], 300, required=False)
    run('vm-start-final', ['limactl', 'start', '--tty=false', vm], 900, required=False)
    observe('updates_after_clean_reboot', updates_state('updates-after-clean-reboot'))
    return ok


try:
    if not dry:
        root.mkdir(parents=True, exist_ok=True)
    ok = q2() if mode == 'q2' else q3()
    receipt['state'] = 'pass' if ok else 'checks-failed'
except Exception:
    receipt['state'] = 'failed'
    receipt['error'] = traceback.format_exc()
finally:
    receipt['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if dry:
        print(json.dumps({'mode': mode, 'vm': vm, 'from': FROM, 'to': TO, 'state': receipt.get('state'),
                          'candidate_source_commit': CANDIDATE_COMMIT or None,
                          'release_exact': not APPLY_CANDIDATE,
                          'error': receipt.get('error'), 'plan': PLAN}, indent=1))
    else:
        save(); print(json.dumps(receipt, indent=2))
sys.exit(0 if receipt['state'] == 'pass' or dry else 1)
