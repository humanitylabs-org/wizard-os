#!/bin/bash
# Pin the reviewed bundle: write RELEASE-SHA256SUMS over every *.sh, *.py and *.env here (hosts.env included).
# runner.py and promote.sh refuse to act if any file is added, removed or changed afterwards.
# Run after reviewing hosts.env and the scripts, then copy the whole directory to both hosts.
set -euo pipefail
cd "$(dirname "$0")"
[ -f hosts.env ] || { echo 'make-manifest: hosts.env missing (copy hosts.env.example and edit)' >&2; exit 2; }
find . -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' -o -name '*.env' \) -printf '%f\n' | LC_ALL=C sort | xargs sha256sum > RELEASE-SHA256SUMS.new
mv RELEASE-SHA256SUMS.new RELEASE-SHA256SUMS
sha256sum -c RELEASE-SHA256SUMS >/dev/null
echo "pinned $(wc -l < RELEASE-SHA256SUMS) files"
