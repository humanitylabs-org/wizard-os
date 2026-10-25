#!/usr/bin/env python3
"""SQLite online backup API; only isolated fixture data, source and destination explicit."""
import sqlite3
import sys
from pathlib import Path

source, target = map(Path, sys.argv[1:])
if not source.is_file() or source.is_symlink() or target.is_symlink():
    raise SystemExit('fixture SQLite source/target refused')
with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
