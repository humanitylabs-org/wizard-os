#!/usr/bin/env python3
"""Run the exact staged WAM CLI in the host and disposable guest.

The sibling `wam/` tree is a git archive of the pinned, pushed WAM commit. This
is a bridge to the real CLI, not an imitation contact/report implementation.
"""
from pathlib import Path
import sys

source = Path(__file__).resolve().parents[4] / 'wam'
assert (source / 'wam/cli.py').is_file(), 'admitted sibling WAM source required'
sys.path.insert(0, str(source))
from wam.cli import main

raise SystemExit(main())
