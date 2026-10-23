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
bootstrap during q2, from a separate cache directory in the newly-created disposable VM only. Installed
release files remain stock. Candidate acceptance requires interruption reporting, a retry that starts,
a verified successful final receipt, and a passing final doctor; it does not accept a failed install's version.
Never touches a VM whose name does not start with `l4-`. No host credentials, no model calls.
"""
import datetime, json, os, shlex, subprocess, sys, time, traceback
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
os.environ.update(LIMA_HOME=lima, PATH='/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', ''))
receipt = {'mode': mode, 'vm': vm, 'LIMA_HOME': lima, 'from': FROM if mode == 'q2' else None, 'to': TO,
           'candidate': CAND or None, 'candidate_applied': APPLY_CANDIDATE,
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


def updates_state(name):
    owner(name, 'wam updates', 180, required=False)
    return as_json(name)


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
    owner('update-apply', 'wam updates --apply', 900, required=False)
    a = as_json('update-apply')
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
    owner('update-reapply', 'wam updates --apply', 900, required=False)
    observe('reapply', as_json('update-reapply'))
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
              'assert s.get("state") == "done"\n')
    final_readback = owner('verified-final-receipt', 'python3 -c ' + shlex.quote(verify), 120, False)
    if APPLY_CANDIDATE:
        recovered = as_json('update-reapply') or {}
        ok = (ok and doctor_caught and bool(s) and s.get('interrupted') is True
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
                          'error': receipt.get('error'), 'plan': PLAN}, indent=1))
    else:
        save(); print(json.dumps(receipt, indent=2))
sys.exit(0 if receipt['state'] == 'pass' or dry else 1)
