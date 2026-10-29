#!/usr/bin/env python3
"""Read-only diagnostics for disposable launch fixtures; private worker log only.

Never collect container environment, app.env, auth stores or owner content. These
logs/compose files are still private evidence, not machine/public receipts.
"""
import os
from pathlib import Path
import re
import subprocess
import sys


def collect():
    assert os.environ.get('WIZARD_LAUNCH_FIXTURE') == 'launch-audits-8-9', 'fixture guard'

    def probe(*argv):
        print('\n--- install diagnostic: ' + ' '.join(map(str, argv)) + ' ---', flush=True)
        try:
            result = subprocess.run(list(map(str, argv)), capture_output=True, text=True, timeout=15)
            print(result.stdout[-131072:], end='', flush=True)
            print(result.stderr[-131072:], end='', file=sys.stderr, flush=True)
            print('\nexit=' + str(result.returncode), flush=True)
            return result.stdout if result.returncode == 0 else ''
        except (OSError, subprocess.TimeoutExpired) as exc:
            print('diagnostic unavailable: ' + type(exc).__name__, flush=True)
            return ''

    probe('sudo', '-n', 'docker', 'logs', '--timestamps', '--tail', '1000', 'runtipi')
    probe('sudo', '-n', 'docker', 'image', 'ls', '--digests', '--no-trunc')
    ids = probe('sudo', '-n', 'docker', 'ps', '-aq', '--filter',
                'label=com.docker.compose.project=wisdom_wizardapps')
    for container in [s for s in ids.split() if re.fullmatch(r'[a-f0-9]{12,64}', s)][:4]:
        probe('sudo', '-n', 'docker', 'logs', '--timestamps', '--tail', '200', container)
    probe('sudo', '-n', 'cat', Path.home() / 'runtipi/apps/wizardapps/wisdom/docker-compose.generated.yml')


if __name__ == '__main__':
    collect()
