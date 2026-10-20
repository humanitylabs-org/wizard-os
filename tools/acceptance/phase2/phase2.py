#!/usr/bin/env python3
"""Fresh-box phase 2 (run under the heavy worker lock): shell in a real browser, install an app,
update check, VM restart survival, app uninstall. Wizard itself stays installed (the VM is kept for
first chat after model sign-in, and for backup/restore).

Usage: phase2.py EVIDENCE_ROOT LIMA_HOME VM_NAME
No model calls, no host credentials, no provider substitution.
"""
import datetime, json, os, subprocess, sys, time, traceback
from pathlib import Path

root, lima, vm = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
assert vm.startswith('l4-'), 'refuse non-lane VM'
here = Path(__file__).resolve().parent
root.mkdir(parents=True, exist_ok=True)
os.environ.update(LIMA_HOME=lima, PATH='/opt/homebrew/bin:/usr/local/bin:' + os.environ['PATH'])
APP = 'wizard-tinfoil'  # public, installable without a key; removed again at the end
receipt = {'vm': vm, 'app_under_test': APP, 'started': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'steps': []}

def save():
    (root / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

def run(name, argv, timeout=300, required=True):
    with (root / (name + '.log')).open('w') as log:
        log.write(json.dumps(argv) + '\n'); log.flush()
        try:
            rc = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            rc = 124
    receipt['steps'].append({'step': name, 'exit': rc, 'required': required, 'log': name + '.log'})
    save(); print(name, rc, flush=True)
    if required and rc:
        raise RuntimeError(f'{name} failed: {rc}')
    return rc

def wam(name, args, timeout=600, required=True):
    cmd = 'sudo -iu wizard bash -lc "export PATH=\\$HOME/.local/bin:\\$PATH; wam ' + args + '"'
    return run(name, ['limactl', 'shell', '--workdir', '/', vm, '--', 'bash', '-lc', cmd], timeout, required)

def browser(label, required=True):
    return run('browser-' + label, ['node', str(here / 'browser.cjs'), str(root / 'browser'), label], 180, required)

def wait_ux(name, limit=600):
    script = f'for i in $(seq 1 {limit // 5}); do c=$(curl -sL -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18796/); echo "$i $c"; [ "$c" = 200 ] && exit 0; sleep 5; done; exit 1'
    return run(name, ['bash', '-lc', script], limit + 30)

def wait_wam(name, limit=300):
    for i in range(limit // 10):
        if wam(name, 'apps', 120, required=False) == 0:
            receipt['steps'][-1]['required'] = True
            return 0
        receipt['steps'].pop(); time.sleep(10)
    return wam(name, 'apps', 120)

def update_state(name):
    wam(name, 'updates', 120, required=False)
    try:
        txt = (root / (name + '.log')).read_text()
        return json.loads(txt[txt.index('{'):txt.rindex('}') + 1])
    except Exception:
        return None

def wait_update(name, limit):
    """Bounded wait for the box to reach the latest release (or stop installing). Never touches install state."""
    t0 = time.time(); last = None
    while time.time() - t0 < limit:
        st = update_state(name)
        receipt['steps'].pop()
        if st:
            last = st
            if not st.get('installing') and not st.get('update_available'):
                break
        time.sleep(30)
    receipt.setdefault('update_states', {})[name] = last
    save()
    return bool(last) and not last.get('installing') and not last.get('update_available')

try:
    run('vm-status', ['limactl', 'list', vm])
    wait_ux('ux-up-before')
    browser('before')
    wam('app-install', f'install {APP}', 900)
    wam('apps-after-install', 'apps')
    out = (root / 'apps-after-install.log').read_text()
    receipt['app_running_after_install'] = any(l.split()[:2] == [APP, 'running'] for l in out.splitlines())
    wam('update-apply', 'updates --apply', 1200, required=False)
    wam('version-after-update', 'version', 120, required=False)
    run('vm-stop', ['limactl', 'stop', vm], 300)
    run('vm-start', ['limactl', 'start', '--tty=false', vm], 900)
    wait_ux('ux-up-after-restart')
    wait_wam('apps-after-restart')
    out = (root / 'apps-after-restart.log').read_text()
    receipt['app_running_after_restart'] = any(l.split()[:2] == [APP, 'running'] for l in out.splitlines())
    wam('doctor-after-restart', 'doctor', 300, required=False)
    receipt['update_after_restart'] = update_state('updates-after-restart')
    wam('update-reapply', 'updates --apply', 1200, required=False)
    receipt['update_recovered'] = wait_update('update-recovery', 1800)
    wait_ux('ux-up-after-update')
    wait_wam('apps-after-update')
    browser('after-restart')
    wam('app-uninstall', f'uninstall {APP}', 600)
    wam('apps-after-uninstall', 'apps')
    out = (root / 'apps-after-uninstall.log').read_text()
    receipt['app_gone_after_uninstall'] = not any(l.split()[:1] == [APP] for l in out.splitlines())
    browser('after-uninstall', required=False)
    ok = receipt.get('update_recovered') and receipt['app_running_after_install'] and receipt['app_running_after_restart'] and receipt['app_gone_after_uninstall']
    receipt['state'] = 'phase2-pass' if ok else 'phase2-checks-failed'
except Exception:
    receipt['state'] = 'failed'
    receipt['error'] = traceback.format_exc()
finally:
    receipt['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(); print(json.dumps(receipt, indent=2))
sys.exit(0 if receipt['state'] == 'phase2-pass' else 1)
