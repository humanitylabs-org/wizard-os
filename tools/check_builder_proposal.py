#!/usr/bin/env python3
"""Run approved checker plus proposed PR24 additions; no approved-rule replacement."""
import argparse
import json
from pathlib import Path
from check_wizard_md import check as approved, front_matter
from app_standard_proposal import check as proposed

p=argparse.ArgumentParser(description=__doc__);p.add_argument('repo',type=Path);args=p.parse_args()
rows=[{'rule':n,'ok':ok,'severity':'error','detail':detail} for n,ok,detail in approved(args.repo)]
if all(r['ok'] for r in rows):
    rows += proposed(args.repo,front_matter((args.repo/'wizard.md').read_text()))
ok=all(r['ok'] or r['severity']=='warning' for r in rows)
print(json.dumps({'ok':ok,'policy':'PR24 proposed (opt-in)','rules':rows,'warnings':[r for r in rows if not r['ok'] and r['severity']=='warning']},indent=2))
raise SystemExit(0 if ok else 1)
