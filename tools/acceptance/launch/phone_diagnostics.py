"""Bounded, private failure evidence. Never retain raw UI XML or activity extras."""
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
import zlib

# Fail closed: new/dynamic labels are redacted, not guessed to be non-secret.
SAFE_LABELS = frozenset({
    'Connect to your Wizard', 'Change Wizard', 'Connect', 'Chats', 'WizardOS',
    'Wizard address', 'Scan QR code', 'Back to your Wizard', 'Keep current Wizard',
    'Checking your Wizard…', 'Attach photos or files', 'Settings', 'Home',
    "Couldn't reach that Wizard. Check the address and that Tailscale is on, then try again.",
    "Enter your Wizard's https:// address, like https://wizard.your-tailnet.ts.net",
    "Couldn't switch yet. Let any recording or upload finish, then try again.",
})
MAX_TEXT = 32768
MAX_PNG = 8 * 1024 * 1024


def private_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(data)


def ui_evidence(xml):
    nodes = list(ET.fromstring(xml).iter('node'))
    if len(nodes) > 1024:
        raise ValueError('ui_node_limit')
    rows, masks = [], []
    for node in nodes:
        values = [node.get(k, '') for k in ('text', 'content-desc')]
        rows.append([v if v in SAFE_LABELS else '[redacted]' for v in values if v])
        if any(v and v not in SAFE_LABELS for v in values):
            match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
            if not match:
                masks = None  # Keep redacted labels, black out the entire image.
            elif masks is not None:
                masks.append(tuple(map(int, match.groups())))
    return rows, masks


def masked_png(png, masks):
    """Decode Android's 8-bit RGB(A) screencap, mask text, strip metadata.

    Unknown PNG layouts fail closed; the caller keeps no unredacted image.
    None means no usable XML: black out the whole screen.
    """
    if len(png) > MAX_PNG or png[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('invalid_png')
    offset, compressed, ihdr = 8, bytearray(), None
    while offset + 12 <= len(png):
        size = struct.unpack('>I', png[offset:offset + 4])[0]
        kind, data = png[offset + 4:offset + 8], png[offset + 8:offset + 8 + size]
        if len(data) != size:
            raise ValueError('short_png')
        if kind == b'IHDR':
            ihdr = data
        elif kind == b'IDAT':
            compressed.extend(data)
        offset += size + 12
    if ihdr is None or len(ihdr) != 13:
        raise ValueError('missing_png_header')
    width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', ihdr)
    if not (0 < width * height <= 4_000_000 and depth == 8 and color in (2, 6)
            and (compression, filtering, interlace) == (0, 0, 0)):
        raise ValueError('unsupported_png')
    channels = 3 if color == 2 else 4
    stride = width * channels
    expected = (stride + 1) * height
    raw = zlib.decompressobj().decompress(compressed, expected + 1)
    if len(raw) != expected:
        raise ValueError('png_size')
    if masks is None:
        masks = [(0, 0, width, height)]
    rows, previous = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        mode, row = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        if mode not in range(5):
            raise ValueError('png_filter')
        if mode:
            for x in range(stride):
                left = row[x - channels] if x >= channels else 0
                above, corner = previous[x], previous[x - channels] if x >= channels else 0
                if mode == 1:
                    predictor = left
                elif mode == 2:
                    predictor = above
                elif mode == 3:
                    predictor = (left + above) // 2
                else:
                    p = left + above - corner
                    distances = [abs(p - v) for v in (left, above, corner)]
                    predictor = (left, above, corner)[distances.index(min(distances))]
                row[x] = (row[x] + predictor) & 255
        previous = row[:]
        for x1, y1, x2, y2 in masks:
            if y1 <= y < y2:
                x1, x2 = max(0, min(width, x1)), max(0, min(width, x2))
                if x2 > x1:
                    row[x1 * channels:x2 * channels] = (b'\x00\x00\x00' + (b'\xff' if channels == 4 else b'')) * (x2 - x1)
        rows.append(b'\x00' + row)
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    result = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b'')
    if len(result) > MAX_PNG:
        raise ValueError('png_retention_limit')
    return result


class DiagnosticError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def network_errors(raw, box_host='', app_pids=()):
    """Project logcat onto error enums only; never redact-and-forward lines."""
    rows = []
    for line in raw.splitlines():
        # threadtime format: date time pid tid priority tag: message.
        fields = line.split(None, 5)
        if len(fields) != 6:
            continue
        pid = fields[2]
        if pid not in app_pids and not re.search(r'\b(?:chromium|cr_\w+|NetworkSecurityConfig)\s*:', fields[5], re.I):
            continue
        errors = re.findall(r'net::ERR_[A-Z_0-9]{1,64}\b|\bSSL(?:HandshakeException|PeerUnverifiedException|Exception)?\b|\bCLEARTEXT\b', fields[5])
        for error in errors[:8]:
            urls = re.findall(r'https?://([^/\s:?#]+)', fields[5])
            host_class = 'box' if box_host and any(h.lower() == box_host.lower() for h in urls) else 'other'
            rows.append({'error': error, 'host': host_class})
            if len(rows) >= 80:
                return rows
    return rows


def capture_failure(evidence, stage, *, adb=None, serial=None, env=None, sudo=False, port=9450,
                    relay=None, box_host=''):
    """Independent bounded probes; fixed reasons, rc and byte counts, never stderr.

    The old implementation collapsed adb nonzero, oversize output and XML masking
    failures into ValueError. That discarded the evidence needed to tell a lost
    device from an unsupported UI/PNG. Preserve these distinctions and retry the
    UI dump independently; don't rely on a stale XML file from the UI wait loop.
    """
    target = Path(evidence) / 'failure'
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.chmod(0o700)
    statuses = {'stage': stage, 'labels': 'no_owned_device',
                'screenshot': 'no_owned_device', 'activity': 'no_owned_device',
                'logcat': 'no_owned_device', 'commands': {}}

    def command(name, argv, limit, timeout=8):
        try:
            result = subprocess.run(list(map(str, argv)), env=env, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            statuses['commands'][name] = {'rc': None, 'stdout_bytes': None, 'timeout': True}
            raise
        stdout = result.stdout
        note = {'rc': result.returncode, 'stdout_bytes': len(stdout) if isinstance(stdout, bytes) else None}
        statuses['commands'][name] = note
        if result.returncode:
            # Recognize only fixed ADB error classes; never retain its message.
            stderr = getattr(result, 'stderr', b'') or b''
            note['adb'] = next((v for k, v in ((b'device offline', 'offline'),
                               (b'not found', 'missing'), (b'no devices', 'missing'),
                               (b'unauthorized', 'unauthorized')) if k in stderr), 'command_failed')
            raise DiagnosticError('nonzero')
        if not isinstance(stdout, bytes):
            raise DiagnosticError('output_type')
        if len(stdout) > limit:
            raise DiagnosticError('output_limit')
        return stdout

    def attempt(name, fn):
        try:
            fn()
            statuses[name] = 'saved'
        except DiagnosticError as exc:
            statuses[name] = exc.reason
        except Exception as exc:
            statuses[name] = type(exc).__name__ if type(exc) in (ValueError, OSError, subprocess.TimeoutExpired, ET.ParseError) else 'unavailable'

    masks = None
    if adb is not None and serial is not None:
        adb_prefix = [str(adb), '-s', str(serial)]
        attempt('device', lambda: command('device', adb_prefix + ['get-state'], 4096))

        def ui():
            nonlocal masks
            for retry in range(2):
                try:
                    # API35 may fail to become idle; compressed output also avoids
                    # enormous WebView trees. Use the same owned serial/env.
                    command('ui_dump', adb_prefix + ['shell', 'uiautomator', 'dump', '--compressed',
                                                    '/sdcard/launch-failure.xml'], 4096, timeout=20)
                    xml = command('ui_xml', adb_prefix + ['exec-out', 'cat', '/sdcard/launch-failure.xml'], 1024 * 1024).decode()
                    rows, masks = ui_evidence(xml)
                    while len(json.dumps(rows).encode()) > MAX_TEXT:
                        rows.pop()
                    private_write(target / 'labels.json', json.dumps(rows).encode())
                    return
                except (DiagnosticError, subprocess.TimeoutExpired):
                    if retry:
                        raise
        attempt('labels', ui)
        attempt('screenshot', lambda: private_write(target / 'screen.png', masked_png(
            command('screenshot', adb_prefix + ['exec-out', 'screencap', '-p'], MAX_PNG), masks)))

        def activity():
            # 'activities' avoids top's unbounded app view dump; retain components
            # and lifecycle booleans only, never Intent extras or task descriptions.
            raw = command('activity', adb_prefix + ['shell', 'dumpsys', 'activity', 'activities'], 2 * 1024 * 1024).decode(errors='replace')
            lines = []
            for line in raw.splitlines():
                if re.fullmatch(r'\s*(?:ACTIVITY [a-zA-Z0-9_.$/]+ [a-f0-9]+ pid=\d+|m(?:Resumed|Stopped|Finished|Destroyed)=(?:true|false))\s*', line):
                    lines.append(line.strip())
                elif 'topResumedActivity' in line or 'mResumedActivity' in line:
                    match = re.search(r'\bai\.wizards\.os/[a-zA-Z0-9_.$]+\b', line)
                    if match:
                        lines.append('resumed ' + match[0])
            private_write(target / 'activity-top.txt', ('\n'.join(lines[:80]) + '\n').encode()[:MAX_TEXT])
        attempt('activity', activity)

        def logcat():
            # A stopped/crashed app (and the browser-only network fixture) has no
            # pid. Still retain Chromium's filtered network errors in that case.
            pids = []
            try:
                pid = command('pid', adb_prefix + ['shell', 'pidof', 'ai.wizards.os'], 1024).decode().split()
                pids = [p for p in pid if p.isdecimal()][:8]
            except DiagnosticError:
                pass
            raw = command('logcat', adb_prefix + ['logcat', '-d', '-t', '800', '-v', 'threadtime'], 2 * 1024 * 1024).decode(errors='replace')
            private_write(target / 'network-errors.json', json.dumps(network_errors(raw, box_host, pids)).encode())
        attempt('logcat', logcat)
    if relay is not None:
        attempt('relay', lambda: private_write(target / 'relay.json', json.dumps(relay.snapshot()).encode()))
    ts_prefix = ['sudo', '-n'] if sudo else []

    def serve():
        value = json.loads(command('serve', ts_prefix + ['tailscale', 'serve', 'status', '--json'], 262144))
        note = {'port': port, 'configured': str(port) in value.get('TCP', {}),
                'https': value.get('TCP', {}).get(str(port), {}).get('HTTPS') is True,
                'handler_count': sum(len(v.get('Handlers', {})) for v in value.get('Web', {}).values())}
        private_write(target / 'serve.json', json.dumps(note).encode())
    attempt('serve', serve)
    private_write(target / 'diagnostics.json', json.dumps(statuses).encode())
