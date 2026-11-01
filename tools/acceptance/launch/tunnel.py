#!/usr/bin/env python3
"""Exercise the printed owner SSH forward on an isolated Lima guest."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import time
import urllib.parse
import urllib.request


FORWARD_READY_SECONDS = 180


@contextlib.contextmanager
def open_forward(vm, cli, evidence):
    lima = Path(os.environ['LIMA_HOME'])
    def guest(*argv):
        return subprocess.check_output(['limactl', 'shell', '--workdir', '/', vm, '--'] + list(argv), text=True)
    options = subprocess.check_output(['limactl', 'show-ssh', '--format=options', vm], text=True)
    settings = dict(line.split('=', 1) for line in options.splitlines() if '=' in line)
    port = int(settings['Port'])
    contact = json.loads(guest('python3', str(cli), 'contact', '--json', '--ssh-host', '127.0.0.1', '--ssh-port', str(port)))
    public_key = guest('cat', '/etc/ssh/ssh_host_ed25519_key.pub').strip().split()
    evidence.mkdir(parents=True, exist_ok=True)
    known = evidence / 'fixture-known-hosts'
    known.write_text(f'[127.0.0.1]:{port} {public_key[0]} {public_key[1]}\n')
    argv = shlex.split(contact['command'])
    argv = argv[:-1] + ['-i', str(lima / '_config/user'), '-o', 'IdentitiesOnly=yes',
                       '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                       '-o', 'UserKnownHostsFile=' + str(known), '-o', 'GlobalKnownHostsFile=/dev/null'] + argv[-1:]
    def forward_port_free():
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', 18795))
                return True
            except OSError:
                return False
    deadline = time.monotonic() + 60
    while not forward_port_free():
        if time.monotonic() > deadline:
            raise RuntimeError('loopback_forward_busy')
        time.sleep(1)
    with (evidence / 'private-ssh.log').open('w') as log:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            ready = False
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            # A deadline, not a try count: a refused connection returns at once,
            # so 40 tries was ~10 s on a busy host while the shell was still starting.
            ready_deadline = time.monotonic() + FORWARD_READY_SECONDS
            while time.monotonic() < ready_deadline:
                if proc.poll() is not None:
                    raise RuntimeError('fixture_forward_exited')
                try:
                    with opener.open(contact['url'], timeout=2) as response:
                        ready = response.status == 200 and b'wizard' in response.read(262144).lower()
                    if ready:
                        break
                except OSError:
                    pass
                time.sleep(.5)
            assert ready, 'printed shell forward never became ready'
            setup_url = urllib.parse.urljoin(contact['url'], '/wizard/v1/setup')
            with opener.open(setup_url, timeout=5) as response:
                setup = json.loads(response.read())
                assert response.status == 200 and isinstance(setup, dict) and type(setup.get('first_run')) is bool
            yield contact['url']
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('vm')
    p.add_argument('cli', type=Path)
    p.add_argument('evidence', type=Path)
    a = p.parse_args()
    with open_forward(a.vm, a.cli, a.evidence):
        (a.evidence / 'first-contact.json').write_text(json.dumps({'passed': True,
             'transport': 'SSH-host-key-verified-loopback-forward', 'host_port_override': True,
             'shell_http': 200, 'setup_api': 200, 'tailnet_enrolled': False}) + '\n')


if __name__ == '__main__':
    main()
