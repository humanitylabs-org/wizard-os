#!/usr/bin/env python3
"""Invalidate EVERY named marker in a disposable Mac before the return import.
The distinct resulting box is the real engine Undo baseline, not a fake snapshot.
"""
import contextlib
import json
from pathlib import Path
from fixture import boxes, paths, root_python, PREFIX

STOCK = r'''
import json,sqlite3,sys
from pathlib import Path
sys.path.insert(0,'/opt/hermes')
from hermes_constants import get_hermes_home
home=Path(get_hermes_home()); p='BACKUP-MAC-ROUNDTRIP'; sid=p.lower()+'-session'
with sqlite3.connect(home/'state.db') as db:
    db.execute('DELETE FROM messages WHERE session_id=?',(sid,))
    db.execute('DELETE FROM sessions WHERE id=?',(sid,))
for name in ('MEMORY.md','USER.md'):
    f=home/'memories'/name
    assert f.is_file(), str(f)
    f.write_text(f.read_text().replace(p,'RETURN-BASELINE'))
f=home/'cron/jobs.json'; cfg=json.loads(f.read_text())
if isinstance(cfg,dict): cfg['jobs']=[j for j in cfg['jobs'] if j.get('name')!=p]
else: cfg=[j for j in cfg if j.get('name')!=p]
f.write_text(json.dumps(cfg))
print(json.dumps({'disturbed':True}))
'''


def main():
    b=boxes()
    manifest=json.loads(Path('/mnt/rig-shared/mac-backup-qa/markers.json').read_text())
    for row in manifest['owner_files']['files']:
        (b.files_root()/row['path']).write_text('distinct Mac return baseline\n')
    cfg=b.home/'settings.json'; data=json.loads(cfg.read_text()); data['backup_acceptance']='return-baseline'; cfg.write_text(json.dumps(data))
    with getattr(b,'operation',contextlib.nullcontext)():
        b.runner.python(b.main_agent(),STOCK,'')
    for p in paths(b).values():
        root_python('from pathlib import Path; import sys; Path(sys.argv[1]).write_text("distinct-return-baseline")',p)
    print(json.dumps({'disturbed':True}))


if __name__=='__main__': main()
