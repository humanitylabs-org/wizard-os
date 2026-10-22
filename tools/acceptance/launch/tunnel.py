#!/usr/bin/env python3
"""Exercise the printed owner SSH forward on an isolated Lima guest."""
import argparse
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import time
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('vm')
p.add_argument('cli', type=Path)
p.add_argument('evidence', type=Path)
a = p.parse_args()
lima = Path(os.environ['LIMA_HOME'])
def guest(*argv):
    return subprocess.check_output(['limactl', 'shell', '--workdir', '/', a.vm, '--'] + list(argv), text=True)
options = subprocess.check_output(['limactl', 'show-ssh', '--format=options', a.vm], text=True)
settings = dict(line.split('=', 1) for line in options.splitlines() if '=' in line)
port = int(settings['Port'])
# The owner route is tested using the actual Lima host-side mapped SSH port.
contact = json.loads(guest('python3', str(a.cli), 'contact', '--json', '--ssh-host', '127.0.0.1', '--ssh-port', str(port)))
public_key = guest('cat', '/etc/ssh/ssh_host_ed25519_key.pub').strip().split()
a.evidence.mkdir(parents=True, exist_ok=True)
known = a.evidence / 'fixture-known-hosts'
known.write_text(f'[127.0.0.1]:{port} {public_key[0]} {public_key[1]}\n')
argv = shlex.split(contact['command'])
argv = argv[:-1] + ['-i', str(lima / '_config/user'), '-o', 'IdentitiesOnly=yes',
                   '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'UserKnownHostsFile=' + str(known), '-o', 'GlobalKnownHostsFile=/dev/null'] + argv[-1:]
# Refuse an occupied forward rather than accidentally reading another service.
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 18795))
with (a.evidence / 'private-ssh.log').open('w') as log:
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
    try:
        ready = False
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(40):
            if proc.poll() is not None:
                raise RuntimeError('fixture SSH forward exited')
            try:
                with opener.open(contact['url'], timeout=2) as response:
                    ready = response.status == 200 and b'wizard' in response.read(262144).lower()
                if ready:
                    break
            except OSError:
                time.sleep(.25)
        assert ready, 'printed shell forward never became ready'
        with opener.open('http://127.0.0.1:18795/wizard/v1/setup', timeout=5) as response:
            assert isinstance(json.loads(response.read()), dict), 'forwarded Setup route failed'
        (a.evidence / 'first-contact.json').write_text(json.dumps({'passed': True,
             'transport': 'SSH-host-key-verified-loopback-forward', 'host_port_override': True,
             'shell_http': 200, 'setup_api': 200, 'tailnet_enrolled': False}) + '\n')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
