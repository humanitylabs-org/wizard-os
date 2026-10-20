"""Stage a ZIP on the clean box through the app's ordinary API; print HTTP result and library readback (no enable)."""
import hashlib, json, sys, urllib.request, urllib.error
EP = 'http://127.0.0.1:19230'
raw = open(sys.argv[1], 'rb').read()
def get(p): return json.load(urllib.request.urlopen(EP + p, timeout=30))
before = {b['id']: (b['sha256'], b['status']) for b in get('/api/library')['bundles']}
req = urllib.request.Request(EP + '/api/library/stage', data=raw, headers={'Content-Type': 'application/zip'})
try:
    r = urllib.request.urlopen(req, timeout=60); code, body = r.status, r.read().decode()
except urllib.error.HTTPError as e:
    code, body = e.code, e.read().decode()
after = get('/api/library')['bundles']
print(json.dumps({'zip': sys.argv[1].rsplit('/', 1)[-1], 'zip_sha256': hashlib.sha256(raw).hexdigest(), 'http': code, 'response': json.loads(body) if body.startswith('{') else body[:400],
                  'library_changed': before != {b['id']: (b['sha256'], b['status']) for b in after},
                  'readback': [{k: b.get(k) for k in ('id', 'status', 'sha256', 'authoring')} for b in after if b['id'].startswith('qa63')]}, indent=1, ensure_ascii=False))
