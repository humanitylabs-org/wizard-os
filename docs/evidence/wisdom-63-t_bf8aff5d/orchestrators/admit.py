"""Export one orchestrator's helper-written chapter+receipt with the shipped exporter, stage it on the clean box
through the ordinary API, record the result, then remove it (no enable) so the next run can reuse the chapter id."""
import hashlib, json, subprocess, sys, urllib.request, urllib.error
from pathlib import Path
EP = 'http://127.0.0.1:19230'
name, md, receipt, toolkit = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
here = Path(__file__).parent; dest = here / ('exp-' + name); coll = 'qa63-' + name
subprocess.run([sys.executable, str(here / 'mk_source.py'), str(md), str(receipt), str(dest), coll], check=True)
zp = dest / (coll + '.zip')
ex = subprocess.run([sys.executable, 'tools/author_collection.py', 'export', '--source', str(dest / 'src'), '--collection', coll,
                     '--output', str(zp), '--license', 'Public domain source (Legge 1891); synthetic QA chapter',
                     '--attribution', 'James Legge, 1891 translation (Project Gutenberg #216)', '--rights', 'private',
                     '--receipts', str(dest / 'receipts')], cwd=toolkit, capture_output=True, text=True)
out = {'run': name, 'exporter_exit': ex.returncode, 'exporter_stderr': ex.stderr.strip()[-300:]}
def get(p): return json.load(urllib.request.urlopen(EP + p, timeout=30))
def post(p, data, ctype='application/json'):
    req = urllib.request.Request(EP + p, data=data, headers={'Content-Type': ctype})
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        b = e.read().decode(); return e.code, (json.loads(b) if b.startswith('{') else b[:300])
if ex.returncode == 0:
    raw = zp.read_bytes(); out['zip_sha256'] = hashlib.sha256(raw).hexdigest()
    code, resp = post('/api/library/stage', raw, 'application/zip')
    out['stage_http'] = code
    a = resp.get('authoring', {}) if isinstance(resp, dict) else {}
    out['stage'] = {k: (resp.get(k) if isinstance(resp, dict) else resp) for k in ('id', 'status', 'sha256')}
    out['authoring'] = {k: a.get(k) for k in ('status', 'observed_model', 'observed_provider', 'chapters_verified', 'chapters_unverified', 'receipts_sha256', 'override')}
    rb = [b for b in get('/api/library')['bundles'] if b['id'] == coll]
    out['readback'] = {k: rb[0].get(k) for k in ('id', 'status', 'sha256')} | {'authoring_status': rb[0]['authoring']['status']} if rb else None
    if rb:
        out['remove_http'] = post('/api/library/action', json.dumps({'id': coll, 'action': 'remove'}).encode())[0]
        out['after_remove_present'] = any(b['id'] == coll for b in get('/api/library')['bundles'])
print(json.dumps(out, indent=1))
