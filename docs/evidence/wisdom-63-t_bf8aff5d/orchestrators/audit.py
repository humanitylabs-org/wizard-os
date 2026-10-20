"""Audit one orchestrator run: every helper invocation, every file-writing tool call, and the run's final files."""
import hashlib, json, sqlite3, sys
from pathlib import Path
name, home = sys.argv[1], sys.argv[2]
db = sqlite3.connect(f'{home}/state.db')
calls, writes = [], []
for (tc,) in db.execute("select tool_calls from messages where tool_calls is not null order by id"):
    for t in json.loads(tc):
        f = t.get('function', t); n = f.get('name'); a = f.get('arguments', '')
        try: a = json.loads(a)
        except Exception: pass
        s = json.dumps(a)
        if 'author_chapter' in s: calls.append({'tool': n, 'cmd': str((a.get('command') or a.get('code') or s) if isinstance(a, dict) else s)[:400]})
        if n in ('write_file', 'patch') or (n == 'terminal' and any(k in s for k in ('receipt.json >', '.md >', "open(", 'write_text', 'cat >', 'tee '))):
            writes.append({'tool': n, 'arg': s[:300]})
print(json.dumps({'run': name, 'helper_invocations': calls, 'file_writing_calls': writes}, indent=1))
