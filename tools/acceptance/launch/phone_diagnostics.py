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
    'Connect to your Wizard', 'Change Wizard', 'Connect', 'Chats', 'Wizard OS',
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
                raise ValueError('unbounded_sensitive_label')
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


def capture_failure(evidence, stage, *, adb=None, serial=None, env=None, sudo=False, port=9450):
    """Best effort, independent probes; unavailable devices never hide the failure.

    Commands are deadline-bounded, retained files are size-bounded, and failure
    reasons are class-only. Capture before emulator teardown; Serve is separately
    noted inside its context, before the dedicated handler is removed.
    """
    target = Path(evidence) / 'failure'
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.chmod(0o700)
    statuses = {'stage': stage, 'labels': 'no_owned_device',
                'screenshot': 'no_owned_device', 'activity': 'no_owned_device'}
    def command(argv, limit):
        result = subprocess.run(list(map(str, argv)), env=env, capture_output=True, timeout=8)
        if result.returncode or not isinstance(result.stdout, bytes) or len(result.stdout) > limit:
            raise ValueError('diagnostic_unavailable')
        return result.stdout
    def attempt(name, fn):
        try:
            fn()
            statuses[name] = 'saved'
        except Exception as exc:
            statuses[name] = type(exc).__name__ if type(exc) in (ValueError, OSError, subprocess.TimeoutExpired) else 'unavailable'
    masks = None
    if adb is not None and serial is not None:
        prefix = [adb, '-s', serial]
        def ui():
            nonlocal masks
            command(prefix + ['shell', 'uiautomator', 'dump', '/sdcard/launch-ui.xml'], 4096)
            xml = command(prefix + ['shell', 'cat', '/sdcard/launch-ui.xml'], 262144).decode()
            rows, masks = ui_evidence(xml)
            while len(json.dumps(rows).encode()) > MAX_TEXT:
                rows.pop()
            private_write(target / 'labels.json', json.dumps(rows).encode())
        attempt('labels', ui)
        attempt('screenshot', lambda: private_write(target / 'screen.png', masked_png(
            command(prefix + ['exec-out', 'screencap', '-p'], MAX_PNG), masks)))
        def activity():
            raw = command(prefix + ['shell', 'dumpsys', 'activity', 'top'], 2 * 1024 * 1024).decode(errors='replace')
            # Retain component/lifecycle evidence, never Intent extras, view text,
            # saved instance state, URLs, thread IDs, or binder/application data.
            lines = [line for line in raw.splitlines() if re.fullmatch(
                r'\s*(?:ACTIVITY [a-zA-Z0-9_.$/]+ [a-f0-9]+ pid=\d+|m(?:Resumed|Stopped|Finished|Destroyed)=(?:true|false))\s*', line)]
            private_write(target / 'activity-top.txt', ('\n'.join(lines[:80]) + '\n').encode()[:MAX_TEXT])
        attempt('activity', activity)
    prefix = ['sudo', '-n'] if sudo else []
    def serve():
        value = json.loads(command(prefix + ['tailscale', 'serve', 'status', '--json'], 262144))
        note = {'port': port, 'configured': str(port) in value.get('TCP', {}),
                'https': value.get('TCP', {}).get(str(port), {}).get('HTTPS') is True,
                'handler_count': sum(len(v.get('Handlers', {})) for v in value.get('Web', {}).values())}
        private_write(target / 'serve.json', json.dumps(note).encode())
    attempt('serve', serve)
    private_write(target / 'diagnostics.json', json.dumps(statuses).encode())
