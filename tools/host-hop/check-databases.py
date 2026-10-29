#!/usr/bin/python3
"""Read-only counts/integrity; never prints prompts or message contents."""
import json,pathlib,sqlite3,time,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import hopenv
root=pathlib.Path(hopenv.load()['HOP_HOME'])/'.hermes';out={}
for home in [root,*(root/'profiles').glob('*')]:
 p=home/'state.db'
 if not p.exists():continue
 t=time.monotonic()
 with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True,timeout=10) as c:
  if '--quick-check' in sys.argv:
   if c.execute('pragma quick_check').fetchall()!=[('ok',)]:raise SystemExit('SQLite quick_check failed: '+str(p))
  counts={table:c.execute('select count(*) from '+table).fetchone()[0] for table in ('sessions','messages')}
 out[str(p.relative_to(root))]={'counts':counts,'seconds':round(time.monotonic()-t,3)}
print(json.dumps(out))
