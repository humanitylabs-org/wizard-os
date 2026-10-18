#!/bin/bash
# Disposable-box test cleanup (labelled setup step, not an app interface): delete one removed qa63-* bundle row
# so the next admission can reuse chapter id qa-empty-hub. Removed bundles reserve ids by design.
set -euo pipefail
ID=$1
case "$ID" in qa63-*) ;; *) echo "refusing non-test id"; exit 1;; esac
C=$(docker ps -q --filter name=wisdom_wizardapps-wisdom)
docker exec -i -u 1000:1000 "$C" python3 - "$ID" <<'PY'
import sqlite3, sys, glob
key = sys.argv[1]
import os; paths = [os.path.join(os.environ.get('WISDOM_DATA', '/data'), 'wisdom.sqlite')]
c = sqlite3.connect(paths[0])
row = c.execute('SELECT status FROM wisdom_bundles WHERE id=?', (key,)).fetchone()
assert row and row[0] == 'removed', row
for t in [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cols = [r[1] for r in c.execute('PRAGMA table_info(%s)' % t)]
    col = 'id' if t == 'wisdom_bundles' else ('bundle_id' if 'bundle_id' in cols else None)
    if col: c.execute('DELETE FROM %s WHERE %s=?' % (t, col), (key,))
c.commit()
import shutil
lib = os.environ.get('WISDOM_LIBRARY', '/media/Wisdom')
for d in (os.path.join(lib, key), os.path.join(lib, '.editions', key)):
    shutil.rmtree(d, ignore_errors=True)
print('purged', key, 'db', paths[0], 'folders under', lib)
PY
