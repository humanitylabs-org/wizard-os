#!/usr/bin/env python3
"""Capture a guest journey JSON document without mixing subprocess stdout."""
from pathlib import Path
import subprocess
import sys

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
p = subprocess.run([sys.executable] + sys.argv[2:], capture_output=True, text=True)
if p.returncode:
    sys.stderr.write(p.stderr)
    raise SystemExit(p.returncode)
out.write_text(p.stdout)
