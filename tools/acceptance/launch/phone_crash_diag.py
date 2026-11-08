#!/usr/bin/env python3
"""Queued WebView crash contrast, no Wizard VM or pairing acceptance claim.

Uses the published APK's native Connect -> WebView and exact Linux HTTPS relay.
The served document is an explicitly synthetic bounded GPU/DOM stress fixture,
not a replacement Wizard shell. Run only via the shared heavy worker.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

from phone import (PACKAGE, center, emulator_argv, emulator_network, host_resolver,
                   labels, native_system_image, validate_apk, worker_lock)
from phone_diagnostics import capture_failure, private_write
from phone_net_diag import served_page
from phone_runtime import (GPU_MODES, PersistentLogcat, checkpoint, configure_avd,
                           exception_note, runtime_note, stop_emulator)

MARKER = 'Synthetic WebView diagnostic ready'
# The native release requires WizardProbe's title/core marker before entering a
# WebView. This fixture deliberately meets that read-only check; never report it
# as a real shell or second-owner pairing result. No APIs, tokens or owner data.
STRESS_PAGE = b'''<!doctype html><meta name="viewport" content="width=device-width">
<title>WizardOS - synthetic crash diagnostic</title><!-- core/ fixture only -->
<style>body{background:#101019;color:white}#tiles{display:grid;grid-template-columns:repeat(12,1fr)}
.tile{height:16px;background:linear-gradient(40deg,#362c70,#72549b);filter:blur(.2px);will-change:transform}
canvas{width:95%;height:180px}#tiles{animation:move 1s infinite alternate}@keyframes move{to{transform:translateY(10px)}}</style>
<h1>Synthetic WebView diagnostic loading</h1><p id="gpu-state">WebGL loading</p><canvas id="paint" width="960" height="480"></canvas>
<canvas id="gpu" width="960" height="480"></canvas><div id="tiles"></div>
<script>
const ctx=document.querySelector('#paint').getContext('2d');
const gl=document.querySelector('#gpu').getContext('webgl');
const root=document.querySelector('#tiles');
let program=null;
if(gl){const shader=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);return s};
program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}'));
gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'precision mediump float;uniform float t;void main(){gl_FragColor=vec4(sin(gl_FragCoord.x*.02+t)*.5+.5,.2,.7,1.);}'));
gl.linkProgram(program);gl.useProgram(program);const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);
gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
const a=gl.getAttribLocation(program,'p');if(a>=0){gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0)}}
for(let i=0;i<1200;i++){const e=document.createElement('div');e.className='tile';root.append(e)}
let frames=0;
function frame(t){for(let i=0;i<150;i++){ctx.fillStyle=`hsl(${(t/10+i)%360} 65% 50%)`;
ctx.fillRect((i*61+t/9)%960,(i*29)%480,40,40)}
if(gl&&gl.getProgramParameter(program,gl.LINK_STATUS)&&!gl.isContextLost()){gl.uniform1f(gl.getUniformLocation(program,'t'),t/1000);gl.drawArrays(gl.TRIANGLES,0,3);
document.querySelector('#gpu-state').textContent='WebGL active'}else{document.querySelector('#gpu-state').textContent='WebGL unavailable'}
frames++;if(frames===30){document.querySelector('h1').textContent='Synthetic WebView diagnostic ready';
fetch('/fixture-rendered',{cache:'no-store'}).catch(()=>{})}requestAnimationFrame(frame)}requestAnimationFrame(frame);
</script>'''


def run_mode(config, root, origin, status):
    root.mkdir(mode=0o700)
    sdk = Path(config['sdk'])
    adb = sdk / 'platform-tools/adb'
    port = config.get('emulator_port', 5582)
    serial = f'emulator-{port}'
    env = os.environ.copy()
    env.pop('http_proxy', None)
    env.update(JAVA_HOME=config['java_home'], ANDROID_HOME=str(sdk), ANDROID_SDK_ROOT=str(sdk),
               ANDROID_AVD_HOME=str(root / 'avd'))
    env['PATH'] = config['java_home'] + '/bin:' + env['PATH']
    Path(env['ANDROID_AVD_HOME']).mkdir()
    checks, clocks, samples = {}, {}, []
    result = {'passed': False, 'stage': 'apk-validation', 'gpu_mode': config['gpu_mode'],
              'ram_mb': config.get('ram_mb', 3072), 'heap_mb': config.get('heap_mb', 512),
              'checks': checks, 'fixture': 'synthetic-webview-gpu-dom', 'pairing_tested': False,
              'liveness': samples}
    em = None

    def call(argv, timeout=20, **kw):
        p = subprocess.run(list(map(str, argv)), env=env, capture_output=True, text=True, timeout=timeout, **kw)
        if p.returncode:
            raise subprocess.CalledProcessError(p.returncode, list(map(str, argv)))
        return p.stdout

    def shell(*args):
        return call([adb, '-s', serial, 'shell', *args])

    def ui():
        shell('uiautomator', 'dump', '--compressed', '/sdcard/crash-diag.xml')
        return shell('cat', '/sdcard/crash-diag.xml')

    def wait(predicate, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if em is None or em.poll() is not None:
                raise RuntimeError('phone_emulator_exited')
            try:
                value = predicate()
                if value:
                    return value
            except (subprocess.CalledProcessError, ET.ParseError):
                pass
            time.sleep(1)
        raise RuntimeError('phone_ui_timeout')

    def edit_origin():
        node = next(n for n in ET.fromstring(ui()).iter('node') if n.get('class') == 'android.widget.EditText')
        shell('input', 'tap', *center(node))
        shell('input', 'keyevent', 'KEYCODE_MOVE_END')
        old = node.get('text', '')
        if old:
            shell('input', 'keyevent', *(['KEYCODE_DEL'] * len(old)))
        shell('input', 'text', origin)
        shell('input', 'keyevent', 'KEYCODE_BACK')
        nodes = list(ET.fromstring(ui()).iter('node'))
        assert next(n for n in nodes if n.get('class') == 'android.widget.EditText').get('text') == origin
        return next(n for n in nodes if n.get('text') == 'Connect' or n.get('content-desc') == 'Connect')

    with emulator_network(status, 9453) as network, PersistentLogcat(root) as logcat:
        try:
            apk, feed, _ = validate_apk(config, sdk, call)
            result['apk_version'] = feed['versionName']
            result['apk_sha256'] = feed['sha256']
            if serial in call([adb, 'devices']):
                raise RuntimeError('phone_diagnostic_liveness')
            result['stage'] = 'avd-create'
            call([sdk / 'cmdline-tools/latest/bin/avdmanager', 'create', 'avd', '-n', 'launch_phone',
                  '-k', native_system_image(), '-d', 'pixel_7', '-p', root / 'device'], input='no\n', timeout=60)
            configure_avd(root / 'device/config.ini', config)
            dns = config.get('dns_server') or host_resolver(status['Self']['DNSName'], call)
            result['stage'] = 'emulator-boot'
            with os.fdopen(os.open(root / 'private-emulator.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
                clocks['start'] = time.monotonic()
                em = subprocess.Popen(emulator_argv(sdk, port, dns, network, config, logcat.argv), env=env,
                                      stdout=output, stderr=output)
            wait(lambda: shell('getprop', 'sys.boot_completed').strip() == '1', 240)
            clocks['boot'] = time.monotonic()
            checks['api35'] = shell('getprop', 'ro.build.version.sdk').strip() == '35'
            network.configure(shell)
            result['stage'] = 'apk-install'
            assert 'Success' in call([adb, '-s', serial, 'install', apk], timeout=90)
            shell('input', 'keyevent', 'KEYCODE_WAKEUP')
            shell('wm', 'dismiss-keyguard')
            # Never open Main at the release's built-in migration/owner origin.
            shell('am', 'start', '-W', '-n', PACKAGE + '/.ConnectActivity')
            result['stage'] = 'connect'
            wait(lambda: 'Connect' in labels(ui()), 60)
            connect = edit_origin()
            result['before_connect_screenshot'] = checkpoint(root, 'before-connect', adb, serial, env)
            clocks['connect'] = time.monotonic()
            shell('input', 'tap', *center(connect))
            time.sleep(max(0, 5 - (time.monotonic() - clocks['connect'])))
            result['after_connect_screenshot'] = checkpoint(root, 'after-connect-5s', adb, serial, env, full_mask=True)
            result['stage'] = 'fixture-render'
            wait(lambda: MARKER in labels(ui()), 90)
            checks['fixture_rendered_in_apk'] = True
            checks['webgl_active'] = 'WebGL active' in labels(ui())
            result['stage'] = 'hold-120s'
            hold = time.monotonic()
            while time.monotonic() - hold < 120:
                sample = runtime_note(em, adb, serial, env, clocks)
                samples.append(sample)
                if sample['emulator_returncode'] is not None or sample['adb_devices']['owned_state'] != 'device':
                    raise RuntimeError('phone_diagnostic_liveness')
                if PACKAGE not in shell('dumpsys', 'activity', 'activities'):
                    raise RuntimeError('phone_diagnostic_liveness')
                time.sleep(min(5, max(0, 120 - (time.monotonic() - hold))))
            checks['held_120s'] = time.monotonic() - hold >= 120
            # Verify a live WebView after the hold, not merely an extant emulator.
            end_labels = labels(ui())
            checks['fixture_still_visible'] = MARKER in end_labels
            checks['webgl_still_active'] = 'WebGL active' in end_labels
            result['hold_end_screenshot'] = checkpoint(root, 'hold-end', adb, serial, env, full_mask=True)
            checks['persistent_logcat_received'] = logcat.bytes_seen > 0
        except Exception as exc:
            result['failure'] = {**runtime_note(em, adb, serial, env, clocks), **exception_note(exc)}
            if str(exc) not in ('phone_diagnostic_deadline', 'phone_diagnostic_interrupted'):
                with contextlib.suppress(Exception):
                    capture_failure(root, result['stage'], adb=adb if em is not None else None, serial=serial,
                                    env=env, port=9453, sudo=config.get('tailscale_sudo', False),
                                    relay=network.relay, box_host=status['Self']['DNSName'].rstrip('.'))
        finally:
            result['before_cleanup'] = runtime_note(em, adb, serial, env, clocks)
            result['relay'] = network.relay.snapshot() if network.relay else {}
            checks['relay_carried_tls'] = all(result['relay'].get(k, 0) > 0 for k in
                ('connect_allowed', 'upstream_ok', 'bytes_to_box', 'bytes_to_android'))
            try:
                stop_emulator(em, adb, serial, env)
                checks['emulator_stopped'] = em is None or em.poll() is not None
            except Exception as exc:
                checks['emulator_stopped'] = False
                result['cleanup_failure'] = exception_note(exc)
            finally:
                shutil.rmtree(root / 'device', ignore_errors=True)
                shutil.rmtree(root / 'avd', ignore_errors=True)
    result['logcat'] = logcat.summary()
    checks['logcat_writer_healthy'] = not result['logcat']['writer_failed']
    checks['no_fatal_crash'] = not any(result['logcat']['counts'][k] for k in
        ('fatal_exception', 'fatal_signal', 'anr', 'chromium_crash'))
    if not checks['no_fatal_crash'] and 'failure' not in result:
        result['failure'] = {**result['before_cleanup'], **exception_note(RuntimeError('phone_diagnostic_crash'))}
    result['passed'] = 'failure' not in result and all(checks.values())
    if result['passed']:
        result['stage'] = 'complete'
    private_write(root / 'verdict.json', json.dumps(result, sort_keys=True).encode())
    return result


def run(config, root, modes):
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    root.chmod(0o700)
    result = {'passed': False, 'stage': 'worker-lock', 'checks': {}, 'modes': [],
              'pairing_tested': False, 'fixture': 'synthetic-webview-gpu-dom'}
    try:
        # Exactly the same inherited lock inode/FD validation as phone.py. Both
        # Serve teardown and all emulator cleanup occur before releasing this lease.
        with worker_lock(config['work_root']):
            result['stage'] = 'serve'
            with served_page(9453, config.get('tailscale_sudo', False), result['checks'], STRESS_PAGE) as (origin, status, _):
                for mode in modes:
                    result['stage'] = 'gpu-mode'
                    entry = run_mode(dict(config, gpu_mode=mode), root / mode, origin, status)
                    result['modes'].append(entry)
                    # A cleanup failure must not boot another emulator.
                    if not entry['checks'].get('emulator_stopped', False) or entry.get('failure', {}).get('message_code') in (
                            'phone_diagnostic_deadline', 'phone_diagnostic_interrupted'):
                        break
            result['passed'] = len(result['modes']) == len(modes) and all(e['passed'] for e in result['modes']) and all(result['checks'].values())
            if result['passed']:
                result['stage'] = 'complete'
    except Exception as exc:
        result['failure'] = exception_note(exc)
    finally:
        private_write(root / 'verdict.json', json.dumps(result, sort_keys=True).encode())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phone-config', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--gpu-modes', nargs='+', default=['swiftshader_indirect', 'swangle'], choices=sorted(GPU_MODES))
    args = parser.parse_args()
    work = Path(os.environ['WIZARD_WORK_ROOT']).resolve()
    if work not in args.root.resolve().parents or not 1 <= len(args.gpu_modes) <= 2 or len(set(args.gpu_modes)) != len(args.gpu_modes):
        parser.error('require a fresh work-root child and one or two distinct GPU modes')
    config = json.loads(args.phone_config.read_text())
    def interrupt(signum, frame):
        raise RuntimeError('phone_diagnostic_deadline' if signum == signal.SIGALRM else 'phone_diagnostic_interrupted')
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGALRM, interrupt)
    # 17.5 min execution budget + bounded cleanup; worker has a 30 min hard stop.
    signal.alarm(1050)
    try:
        verdict = run(config, args.root, args.gpu_modes)
    finally:
        signal.alarm(0)
    print(json.dumps(verdict, sort_keys=True))
    return 0 if verdict['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
