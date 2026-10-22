#!/usr/bin/env python3
"""Control-plane receipt mirror. Not a runner; never publishes private worker logs."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import subprocess

REPO = 'humanitylabs-org/wizard-os'
STEPS = {'start', 'clean-create', 'clean-public-install', 'clean-previous-journey', 'clean-upgrade',
         'retained-create', 'retained-start', 'retained-intervention-check', 'retained-journey',
         'retained-reboot', 'complete'}


def format_receipt(value):
    release = value.get('release')
    release = release if isinstance(release, str) and re.fullmatch(r'\d+\.\d+\.\d+', release) else 'unavailable'
    digest = value.get('sha256')
    if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise ValueError('receipt digest required')
    step = value.get('step') if value.get('step') in STEPS else 'unavailable'
    passed = value.get('passed') is True
    interventions = value.get('interventions')
    interventions = interventions if type(interventions) is int and 0 <= interventions <= 10000 else 'unavailable'
    return (f'### Launch audits 8/9 — daily appliance receipt\n\n'
            f'- Fixture: `launch-audits-8-9` (isolated Ubuntu 24.04 arm64, no owner data).\n'
            f'- Candidate: `{release}`. Journey: **{"PASS" if passed else "FAIL"}**, last step `{step}`.\n'
            f'- Interactive login interventions: `{interventions}`.\n'
            '- Shipped-profile VM remains distinct from the frozen CLI source probe; no source overlay counts as a released feature.\n'
            '- This receipt alone does not prove the 72-hour gate. Worker logs/paths are not published.\n'
            f'- Receipt SHA256: `{digest}`.\n\n<!-- launch-audits:{digest} -->')


def gh(*argv):
    return json.loads(subprocess.check_output(['gh', 'api'] + list(argv), text=True))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('receipt', type=Path)
    p.add_argument('--issue', type=int, choices=[139, 140], default=140)
    a = p.parse_args()
    value = json.loads(a.receipt.read_text())
    body = format_receipt(value)
    marker = '<!-- launch-audits:' + value['sha256'] + ' -->'
    # Paginate rather than assuming the first 100 comments are all comments.
    page = 1
    existing = None
    while True:
        rows = gh(f'repos/{REPO}/issues/{a.issue}/comments?per_page=100&page={page}')
        existing = next((row for row in rows if marker in row.get('body', '')), None)
        if existing or len(rows) < 100:
            break
        page += 1
    posted = existing or gh(f'repos/{REPO}/issues/{a.issue}/comments', '--method', 'POST', '-f', 'body=' + body)
    readback = gh(f'repos/{REPO}/issues/comments/{posted["id"]}')
    if readback.get('body') != body:
        raise SystemExit('comment readback mismatch')
    print(readback['html_url'])


if __name__ == '__main__':
    main()
