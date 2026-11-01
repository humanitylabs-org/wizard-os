"""Acceptance-only emulator settings and bounded crash evidence, no raw public text."""
import contextlib
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import threading
import time

from phone_diagnostics import MAX_PNG, masked_png, private_write, ui_evidence

GPU_MODES = frozenset(('auto', 'host', 'software', 'lavapipe', 'swiftshader', 'swangle',
                       'guest', 'swiftshader_indirect', 'swangle_indirect'))
MESSAGE_CODES = frozenset(('phone_emulator_exited', 'phone_ui_timeout', 'phone_tailnet_dns',
    'phone_command_failed', 'phone_disposable_required', 'phone_android_proxy', 'phone_bounds',
    'phone_serve_port_busy', 'phone_inherited_lock_mismatch', 'phone_gpu_mode', 'phone_memory',
    'phone_logcat_writer', 'phone_diagnostic_interrupted', 'phone_diagnostic_deadline',
    'phone_diagnostic_page_timeout', 'phone_diagnostic_liveness', 'phone_diagnostic_crash'))
CLASS_NAMES = frozenset(('RuntimeError', 'ValueError', 'AssertionError', 'TimeoutExpired',
    'CalledProcessError', 'FileNotFoundError', 'PermissionError', 'OSError', 'BlockingIOError',
    'ParseError', 'StopIteration', 'KeyError', 'TypeError', 'JSONDecodeError'))
ARG_WORDS = frozenset(('-s', 'shell', 'devices', 'install', 'create', 'avd', 'dex', 'code',
    'verify', '--print-certs', 'dump', 'badging', 'status', '--json', 'serve', 'get-state'))


def exception_note(exc):
    name = type(exc).__name__
    note: dict = {'exception_class': name if name in CLASS_NAMES else 'unavailable',
            'message_code': str(exc) if type(exc) in (RuntimeError, ValueError) and str(exc) in MESSAGE_CODES
                            else name if name in ('TimeoutExpired', 'CalledProcessError') else 'unclassified'}
    if isinstance(exc, (subprocess.TimeoutExpired, subprocess.CalledProcessError)):
        argv = exc.cmd if isinstance(exc.cmd, (list, tuple)) else []
        # Only argv[1:3], projected onto command words / disposable emulator ID.
        note['command_args'] = [str(a) if str(a) in ARG_WORDS or re.fullmatch(r'emulator-\d{4,5}', str(a))
                                else '[redacted]' for a in argv[1:3]]
        if isinstance(exc, subprocess.CalledProcessError):
            note['command_returncode'] = exc.returncode
    return note


def runtime_note(em, adb, serial, env, clocks):
    now = time.monotonic()
    rc = em.poll() if em is not None else None
    if type(rc) is not int:
        rc = None
    note = {'emulator_returncode': rc, 'emulator_signal': None,
            **{'seconds_since_' + k: round(max(0, now - clocks[k]), 3) if k in clocks else None
               for k in ('boot', 'connect', 'start')}}
    if rc is not None and rc < 0:
        with contextlib.suppress(ValueError):
            note['emulator_signal'] = signal.Signals(-rc).name
    state = {'owned_state': 'not_started' if em is None else 'unavailable', 'rc': None}
    if em is not None:
        try:
            result = subprocess.run([str(adb), 'devices'], env=env, capture_output=True, text=True, timeout=5)
            state['rc'] = result.returncode
            if result.returncode == 0:
                state['owned_state'] = 'missing'
                for line in result.stdout[:65536].splitlines():
                    row = line.split()
                    if len(row) >= 2 and row[0] == serial:
                        state['owned_state'] = row[1] if row[1] in ('device', 'offline', 'unauthorized', 'recovery', 'bootloader') else 'other'
        except (OSError, subprocess.TimeoutExpired) as exc:
            state['error_class'] = type(exc).__name__
    note['adb_devices'] = state
    # Numeric-only Linux pressure evidence, not process names or command lines.
    pressure = {}
    for path, keys in ((Path('/proc/meminfo'), {'MemAvailable', 'SwapFree', 'SwapTotal'}),
                       (Path('/proc') / str(getattr(em, 'pid', 'none')) / 'status', {'VmRSS', 'VmPeak'})):
        with contextlib.suppress(OSError):
            for line in path.read_text().splitlines():
                row = line.split()
                if len(row) >= 2 and row[0].rstrip(':') in keys and row[1].isdigit():
                    pressure[row[0].rstrip(':') + '_kb'] = int(row[1])
    note['memory'] = pressure
    return note


def configure_avd(path, config):
    """Pin the disposable AVD, not the SDK or any shared profile."""
    ram, heap = config.get('ram_mb', 3072), config.get('heap_mb', 512)
    if type(ram) is not int or type(heap) is not int or not 2048 <= ram <= 8192 or not 128 <= heap <= 1024 or heap > ram // 2:
        raise ValueError('phone_memory')
    path = Path(path)
    rows = [r for r in path.read_text().splitlines() if r.split('=', 1)[0].strip() not in ('hw.ramSize', 'vm.heapSize')]
    path.write_text('\n'.join(rows + [f'hw.ramSize={ram}', f'vm.heapSize={heap}']) + '\n')


CRASH_PATTERNS = {
    'fatal_exception': r'FATAL EXCEPTION',
    'fatal_signal': r'Fatal signal\s+\d+',
    'anr': r'\bANR in\b|\bApplication Not Responding\b',
    'chromium_crash': r'(?:chromium|cr_\w+|webview|render(?:er)? process).*(?:crash|fatal|has died)|(?:crash|fatal).*(?:chromium|webview)',
    'gpu_errors': r'(?:GPU|EGL|swiftshader|vulkan|gfxstream).*(?:error|fail|fatal|crash)|(?:error|fail|fatal|crash).*(?:GPU|EGL|swiftshader|vulkan|gfxstream)',
    'lowmemorykiller_kills': r'(?:lowmemorykiller|lmkd).*(?:kill|killing)',
}


class PersistentLogcat:
    """Guest-console logcat survives adb loss. FIFO drains after retention fills.

    The emulator supports -logcat-output on 37.2.12. A FIFO prevents an emulator
    from writing unbounded raw logs: two files retain the latest 16 MiB;
    fixed counters continue across the entire stream. No log lines are public.
    """
    def __init__(self, evidence, limit=8 * 1024 * 1024):
        self.root = Path(evidence)
        self.fifo = self.root / 'private-logcat.pipe'
        self.argv = ['-logcat-output', str(self.fifo), '-logcat', '*:V']
        self.limit = limit
        self.bytes_seen = 0
        self.counts = dict.fromkeys(CRASH_PATTERNS, 0)
        self.stop = threading.Event()
        self.error = False

    def __enter__(self):
        os.mkfifo(self.fifo, 0o600)
        self.fd = os.open(self.fifo, os.O_RDWR | os.O_NONBLOCK | os.O_NOFOLLOW)
        self.output = os.fdopen(os.open(self.root / 'private-logcat.txt',
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb', buffering=0)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
        return self

    def _read(self):
        pending = b''
        retained = 0
        try:
            while True:
                ready = select.select([self.fd], [], [], .1)[0]
                if not ready:
                    if self.stop.is_set():
                        break
                    continue
                chunk = raw = os.read(self.fd, 65536)
                self.bytes_seen += len(raw)
                while raw:
                    if retained == self.limit:
                        self.output.close()
                        os.replace(self.root / 'private-logcat.txt', self.root / 'private-logcat.previous.txt')
                        self.output = os.fdopen(os.open(self.root / 'private-logcat.txt',
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb', buffering=0)
                        retained = 0
                    keep, raw = raw[:self.limit - retained], raw[self.limit - retained:]
                    self.output.write(keep)
                    retained += len(keep)
                lines = (pending + chunk).split(b'\n')
                pending = lines.pop()[-8192:]
                for line in lines:
                    text = line[:8192].decode(errors='replace')
                    for key, pattern in CRASH_PATTERNS.items():
                        self.counts[key] += bool(re.search(pattern, text, re.I))
            if pending:
                for key, pattern in CRASH_PATTERNS.items():
                    self.counts[key] += bool(re.search(pattern, pending.decode(errors='replace'), re.I))
        except Exception:
            self.error = True

    def summary(self):
        return {'counts': dict(self.counts), 'bytes_seen': self.bytes_seen,
                'retention_truncated': self.bytes_seen > 2 * self.limit, 'writer_failed': self.error}

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            self.error = True
        self.output.close()
        os.close(self.fd)
        self.fifo.unlink(missing_ok=True)
        private_write(self.root / 'logcat-summary.json', json.dumps(self.summary()).encode())


def checkpoint(evidence, name, adb, serial, env, *, full_mask=False):
    """No raw PNG/XML on disk. Snapshot failure never replaces the actual failure."""
    if name not in ('before-connect', 'after-connect-5s', 'hold-end'):
        raise ValueError('checkpoint_name')
    note: dict = {'saved': False}
    prefix = [str(adb), '-s', serial]
    try:
        masks = None
        if not full_mask:
            subprocess.run(prefix + ['shell', 'uiautomator', 'dump', '--compressed', '/sdcard/checkpoint.xml'],
                           env=env, capture_output=True, check=True, timeout=5)
            xml = subprocess.run(prefix + ['exec-out', 'cat', '/sdcard/checkpoint.xml'], env=env,
                                 capture_output=True, check=True, timeout=5).stdout
            if len(xml) <= 1024 * 1024:
                _, masks = ui_evidence(xml.decode())
        image = subprocess.run(prefix + ['exec-out', 'screencap', '-p'], env=env,
                               capture_output=True, check=True, timeout=8).stdout
        if len(image) <= MAX_PNG:
            private_write(Path(evidence) / (name + '.png'), masked_png(image, masks))
            note['saved'] = True
    except Exception as exc:
        note.update(exception_note(exc))
    return note


def stop_emulator(em, adb, serial, env):
    if em is None:
        return
    if em.poll() is not None:
        em.wait(timeout=5)
        return
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run([str(adb), '-s', serial, 'emu', 'kill'], env=env, capture_output=True, timeout=15)
    try:
        em.wait(timeout=20)
    except subprocess.TimeoutExpired:
        em.terminate()
        try:
            em.wait(timeout=10)
        except subprocess.TimeoutExpired:
            em.kill()
            em.wait(timeout=10)
