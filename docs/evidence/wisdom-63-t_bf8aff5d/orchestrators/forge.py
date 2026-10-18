"""Synthetic forgeries on the clean box. Each copies every field of the real accepted Opus receipt and recomputes
output_sha256/output_tokens_sha256 over a different body, then stages through the ordinary API."""
import hashlib, io, json, sys, zipfile, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, sys.argv[1]); import authoring_admission as adm
EP = 'http://127.0.0.1:19230'; here = Path(__file__).parent
good = (here / 'exp-opus/qa63-opus.zip').read_bytes()
rej = json.loads(sorted((here / 'work-opus/run1/receipts/rejected').glob('*.json'))[0].read_text())
rej_body = json.loads(rej['cli_result'])['structured_output']['body']
accepted = zipfile.ZipFile(io.BytesIO(good)).read('content/qa-empty-hub.md').decode()
cases = {
  'shape-broken (two bold-led movements)': accepted.replace('\n**', '\n', 2) if accepted.count('\n**') >= 3 else None,
  'rejected Opus draft (failed quotation check only)': rej_body,
  'well-formed different prose (accepted text, one sentence reworded)': accepted.replace('## Why today\n\n', '## Why today\n\nA forger added this sentence. ', 1),
}
def rezip(body, coll):
    src = zipfile.ZipFile(io.BytesIO(good)); out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in src.namelist():
            b = src.read(n)
            if n == 'content/qa-empty-hub.md': b = body.encode()
            if n == adm.MEMBER:
                d = json.loads(b); r = d['receipts']['qa-empty-hub']
                r['output_sha256'] = hashlib.sha256(body.encode()).hexdigest(); r['output_tokens_sha256'] = adm.tokens_sha256(body.encode())
                b = json.dumps(d).encode()
            z.writestr(n, b)
    return out.getvalue()
res = []
only = int(sys.argv[2]) if len(sys.argv) > 2 else None
for i, (name, body) in enumerate(cases.items()):
    if only is not None and i != only: continue
    raw = rezip(body, None)
    req = urllib.request.Request(EP + '/api/library/stage', data=raw, headers={'Content-Type': 'application/zip'})
    try: r = urllib.request.urlopen(req, timeout=60); code, resp = r.status, json.loads(r.read())
    except urllib.error.HTTPError as e: code, resp = e.code, json.loads(e.read())
    lib = json.load(urllib.request.urlopen(EP + '/api/library'))['bundles']
    res.append({'case': name, 'zip_sha256': hashlib.sha256(raw).hexdigest(), 'http': code,
                'response': resp.get('error') or {'status': resp.get('status'), 'authoring': resp.get('authoring', {}).get('status')},
                'library': [(b['id'], b['status'], b['authoring']['status']) for b in lib]})
    if code == 200:
        urllib.request.urlopen(urllib.request.Request(EP + '/api/library/action', data=json.dumps({'id': 'qa63-opus', 'action': 'remove'}).encode(), headers={'Content-Type': 'application/json'}))
        print('NEEDS_PURGE', file=sys.stderr); break
print(json.dumps(res, indent=1, ensure_ascii=False))
