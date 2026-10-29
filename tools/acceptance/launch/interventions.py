#!/usr/bin/env python3
"""Count interactive guest logins only; never publish account/address/log text."""
import argparse
import datetime as dt
import json
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--since', required=True)
a = p.parse_args()
when = dt.datetime.fromisoformat(a.since.replace('Z', '+00:00')).astimezone(dt.timezone.utc)
r = subprocess.run(['last', '-F', '-w', '-s', when.strftime('%Y%m%d%H%M%S')], capture_output=True, text=True, timeout=10,
                   env={'PATH': '/usr/bin:/bin', 'TZ': 'UTC', 'LC_ALL': 'C'})
if r.returncode:
    raise SystemExit('login-history-unavailable')
count = sum(bool(re.search(r'\b(?:pts/[0-9]+|tty[0-9]+)\b', line)) for line in r.stdout.splitlines())
print(json.dumps({'interactive_logins': count, 'scope': 'wtmp-interactive-tty-logins-only'}))
