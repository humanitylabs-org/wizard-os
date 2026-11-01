"""Test-scoped Linux emulator transport; no TLS termination or host reconfiguration."""
import contextlib
from _thread import LockType
import select
import socket
import socketserver
import threading
import time


class Relay(str):
    """String-compatible endpoint with address/payload-free evidence."""
    lock: LockType
    counts: dict
    def snapshot(self):
        with self.lock:
            return dict(self.counts)

    @property
    def android_proxy(self):
        # Android Emulator's documented alias for host loopback (also virtio WiFi).
        return '10.0.2.2:' + self.rsplit(':', 1)[1]


@contextlib.contextmanager
def connect_proxy(host, addresses, port):
    """Permit CONNECT only to this test's Serve authority (name or resolved IP).

    Linux Serve sockets are device-bound: traffic entering on a guest bridge
    cannot reach them, even when host-local HTTPS works. The emulator's explicit
    HTTP proxy makes the final connection in the host network stack. The APK
    still checks the real tailnet certificate and speaks to the real guest UX.
    Nothing is decrypted, logged, persisted, or forwarded to another authority.
    """
    authorities = {f'{host}:{port}', *(f'{a}:{port}' if ':' not in a else f'[{a}]:{port}' for a in addresses)}
    slots = threading.BoundedSemaphore(64)
    active = set()
    lock = threading.Lock()
    stopping = threading.Event()
    counts = dict.fromkeys(('accepted', 'connect_allowed', 'connect_denied',
                            'upstream_ok', 'upstream_failed', 'bytes_to_box', 'bytes_to_android'), 0)

    def count(name, amount=1):
        with lock:
            counts[name] += amount

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            count('accepted')
            if not slots.acquire(blocking=False):
                count('connect_denied')
                return
            upstream = None
            try:
                self.request.settimeout(10)
                with lock:
                    active.add(self.request)
                header = bytearray()
                while b'\r\n\r\n' not in header and len(header) < 4096:
                    chunk = self.request.recv(1)
                    if not chunk:
                        return
                    header.extend(chunk)
                line = bytes(header).split(b'\r\n', 1)[0].decode('ascii')
                parts = line.split(' ')
                if (not header.endswith(b'\r\n\r\n') or len(parts) != 3 or parts[0] != 'CONNECT'
                        or parts[1] not in authorities or parts[2] not in ('HTTP/1.0', 'HTTP/1.1')):
                    count('connect_denied')
                    self.request.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
                    return
                count('connect_allowed')
                # Never use the request's destination for dialing. Even numeric
                # CONNECT targets are pinned to the host's real HTTPS name.
                try:
                    upstream = socket.create_connection((host, port), timeout=10)
                except OSError:
                    count('upstream_failed')
                    return
                count('upstream_ok')
                with lock:
                    active.add(upstream)
                self.request.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                upstream.settimeout(10)
                deadline = time.monotonic() + 1800
                while not stopping.is_set() and time.monotonic() < deadline:
                    ready, _, _ = select.select([self.request, upstream], [], [], 1)
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.request else self.request).sendall(data)
                        count('bytes_to_box' if source is self.request else 'bytes_to_android', len(data))
            except (OSError, UnicodeError, ValueError):
                # Exception strings can contain addresses or HTTP data.
                pass
            finally:
                with lock:
                    active.discard(self.request)
                    active.discard(upstream)
                if upstream is not None:
                    upstream.close()
                slots.release()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        request_queue_size = 64

        def handle_error(self, request, client_address):
            pass  # Never emit a traceback containing request data.

    with Server(('127.0.0.1', 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
        thread.start()
        try:
            relay = Relay(f'http://127.0.0.1:{server.server_address[1]}')
            relay.lock, relay.counts = lock, counts
            yield relay
        finally:
            stopping.set()
            server.shutdown()
            with lock:
                for connection in active:
                    with contextlib.suppress(OSError):
                        connection.shutdown(socket.SHUT_RDWR)
            thread.join(timeout=5)
