#!/usr/bin/env python3
"""Real subscription chat, with an access-only lease in a disposable Lima guest.

The renewable login NEVER leaves the host secrets directory. Subprocess output is
captured in memory, not streamed to the acceptance log. No transcripts in receipts.
"""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import uuid

PROVIDER = 'openai-codex'
MODEL_PATTERN = r'[A-Za-z0-9][A-Za-z0-9._:-]{0,99}'


def private_file(path, secrets_root):
    path, secrets_root = Path(path), Path(secrets_root).resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(secrets_root):
        raise RuntimeError('credential_boundary')
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o600 or st.st_uid != os.getuid():
        raise RuntimeError('credential_permissions')
    return path


def oauth_module(path, secrets_root, oauth_source):
    private_file(path, secrets_root)
    # Reuse the pushed ChatGPT app's single-writer OAuth implementation. Refreshes
    # persist ONLY on the host, never in a guest or an archive/source checkout.
    spec = importlib.util.spec_from_file_location('launch_codex', Path(oauth_source) / 'codex.py')
    if spec is None or spec.loader is None:
        raise RuntimeError('oauth_source_missing')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def access_lease(path, secrets_root, oauth_source):
    module = oauth_module(path, secrets_root, oauth_source)
    connection = module.Connection(Path(path).parent)
    access = connection.access()
    if module.claims(access).get('exp', 0) < time.time() + 300:
        raise RuntimeError('credential_too_short')
    return {'active_provider': PROVIDER, 'providers': {PROVIDER: {
        'tokens': {'access_token': access}, 'auth_mode': 'chatgpt',
        'base_url': 'https://chatgpt.com/backend-api/codex', 'source': 'launch-access-only'}}}


def select_model(path, secrets_root, oauth_source):
    module = oauth_module(path, secrets_root, oauth_source)
    # The dedicated connection advertises models available to this subscription.
    # Do not pin a retired slug or retry a failed model on an unobserved fallback.
    try:
        rows = module.Connection(Path(path).parent).models()
    except Exception:
        raise RuntimeError('chat_model_catalog_unavailable') from None
    for row in rows:
        model = row.get('id')
        if (isinstance(model, str) and re.fullmatch(MODEL_PATTERN, model)
                and model.startswith('gpt-') and 'text' in row.get('abilities', [])):
            return model
    raise RuntimeError('chat_model_catalog_empty')


def chat_code(model):
    if not isinstance(model, str) or re.fullmatch(MODEL_PATTERN, model) is None:
        raise RuntimeError('chat_model_invalid')
    return CHAT.replace('__CHAT_MODEL__', model)


STDERR_CLASSES = frozenset({'PermissionError', 'StopIteration', 'AssertionError',
    'ConnectionRefusedError', 'HTTPError', 'RuntimeError', 'FileNotFoundError',
    'KeyError', 'IndexError', 'URLError', 'JSONDecodeError', 'TimeoutError'})


def stderr_class(text):
    # Do not redact arbitrary text: project onto fixed enums only. Neither a
    # provider body nor a traceback line/path/value can cross this boundary.
    matches = re.findall(r'^([A-Za-z]+Error|StopIteration)(?::|$)', text, re.MULTILINE)
    return next((x for x in reversed(matches) if x in STDERR_CLASSES), 'unknown')


class GuestFailure(RuntimeError):
    def __init__(self, snippet, rc, category):
        self.diagnostic = {'snippet': snippet, 'rc': rc, 'stderr_class': category}
        super().__init__('chat_guest_failed')


def guest(vm, code, value=None, timeout=90, log=None, snippet=None):
    snippet = snippet or {INSTALL: 'install', CHAT: 'chat', REMOVE: 'remove'}.get(code, 'unknown')
    if snippet not in ('install', 'chat', 'remove'):
        snippet = 'unknown'
    try:
        p = subprocess.run(['limactl', 'shell', '--workdir', '/', vm, '--', 'python3', '-c', code],
                           input=json.dumps(value) if value is not None else '',
                           text=True, capture_output=True, timeout=timeout)
        if p.returncode:
            raise GuestFailure(snippet, p.returncode, stderr_class(p.stderr))
        try:
            return json.loads(p.stdout)
        except (ValueError, TypeError):
            raise GuestFailure(snippet, 0, 'JSONDecodeError') from None
    except subprocess.TimeoutExpired:
        failure = GuestFailure(snippet, None, 'timeout')
    except GuestFailure as exc:
        failure = exc
    if log is not None:
        with Path(log).open('a') as out:
            out.write(json.dumps({'first_chat_failure': failure.diagnostic}, sort_keys=True) + '\n')
    raise failure from None


# These snippets run in the VM, and docker's stdin carries the only secret bytes.
ENGINE = """
import subprocess,json,sys,re
names=subprocess.check_output(['sudo','-n','docker','ps','--format','{{.Names}}'],text=True).splitlines()
c=next(n for n in names if n.endswith('hermes-agent-engine-1'))
def checked(r):
 if not r.returncode: return
 text=r.stderr.decode(errors='replace') if isinstance(r.stderr,bytes) else (r.stderr or '')
 allowed={'PermissionError','AssertionError','FileNotFoundError','RuntimeError','JSONDecodeError'}
 classes=re.findall(r'^([A-Za-z]+Error)(?::|$)',text,re.MULTILINE)
 print(next((v for v in reversed(classes) if v in allowed),'RuntimeError'),file=sys.stderr)
 sys.exit(r.returncode)
"""
INSTALL = ENGINE + """
code='''import json,os,pathlib,sys
p=pathlib.Path('/opt/data/auth.json'); marker=pathlib.Path('/opt/data/.launch-chat-lease')
if marker.exists(): raise RuntimeError('stale lease')
if p.exists():
 old=json.loads(p.read_text())
 if old.get('providers') or old.get('credential_pool'): raise RuntimeError('not an empty owner')
marker.touch(mode=0o600)
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f: json.dump(json.load(sys.stdin),f)
os.chmod(p,0o600);os.chown(p,1000,1000)
'''
r=subprocess.run(['sudo','-n','docker','exec','-i',c,'python3','-c',code],input=sys.stdin.read(),text=True,capture_output=True)
checked(r)
print('{}')
"""
REMOVE = ENGINE + """
code='''import pathlib
p=pathlib.Path('/opt/data/auth.json'); marker=pathlib.Path('/opt/data/.launch-chat-lease')
if marker.exists(): p.unlink(missing_ok=True); marker.unlink()
assert not p.exists(), 'credential remains'
'''
r=subprocess.run(['sudo','-n','docker','exec',c,'python3','-c',code],capture_output=True)
checked(r)
# Drop any in-process provider/client cache, then read back the exact target.
r=subprocess.run(['sudo','-n','docker','restart',c],capture_output=True)
checked(r)
r=subprocess.run(['sudo','-n','docker','exec',c,'python3','-c',"from pathlib import Path; assert not Path('/opt/data/auth.json').exists()"],capture_output=True)
checked(r)
print('{}')
"""
CHAT = """
import json,time,uuid,urllib.request
from pathlib import Path
apps=json.loads((Path.home()/'.wizard-os/apps.json').read_text())['apps']
service=next(a for a in apps if a['id']=='wizard-agent-service')['mcp']['url'].removesuffix('/mcp')
def http(method,path,body=None):
 data=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request(service+path,data=data,method=method,headers={'Content-Type':'application/json','Idempotency-Key':str(uuid.uuid4())})
 with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
# /wizard/v1 is the bootstrap/control API, not a send API. Use the shipped
# Agent Service /wizard/hermes/v1/runs route used by the shell, never raw Hermes.
http('GET','/v1/bootstrap')
# service ends in /wizard: compatibility routes below are relative to it.
sid='wizard_'+str(int(time.time()*1000))+'_'+uuid.uuid4().hex[:12]
http('POST','/hermes/api/sessions',{'id':sid,'source':'wizard-mobile','provider':'openai-codex','model':'__CHAT_MODEL__'})
r=http('POST','/hermes/v1/runs',{'session_id':sid,'input':'Reply with exactly: Wizard is ready.','provider':'openai-codex','model':'__CHAT_MODEL__','require_model_lock':True})
deadline=time.monotonic()+240
while time.monotonic()<deadline:
 r=http('GET','/hermes/v1/runs/'+r['run_id'])
 if r.get('status') in ('completed','failed','cancelled','stopped','error'): break
 time.sleep(1)
assert r.get('status')=='completed' and isinstance(r.get('output'),str) and r['output'].strip()
runtime=r.get('runtime') or r.get('usage',{}).get('runtime',{})
assert runtime.get('provider')=='openai-codex' and runtime.get('model')=='__CHAT_MODEL__'
rows=http('GET','/hermes/api/sessions/'+sid+'/messages?order=oldest&limit=100&view=wizard')['data']
assert any(m.get('role')=='assistant' and m.get('content')==r['output'] for m in rows)
# Internal pipe only: never write these fields to evidence or stdout of run.py.
print(json.dumps({'session':sid,'output':r['output']}))
"""


def run_chat(vm, model, log=None):
    started = time.monotonic()
    internal = guest(vm, chat_code(model), timeout=300, log=log, snippet='chat')
    return {'passed': True, 'latency_ms': round((time.monotonic() - started) * 1000),
            'provider': PROVIDER}, internal


@contextlib.contextmanager
def credential_lease(vm, path, secrets_root, oauth_source, log=None):
    # Only disposable VM names emitted by run.py are admissible. Never inject the
    # retained soak VM, or any arbitrary owner box provided on a command line.
    if not vm.startswith('lc-'):
        raise RuntimeError('disposable_guest_required')
    model = select_model(path, secrets_root, oauth_source)
    auth = access_lease(path, secrets_root, oauth_source)
    try:
        guest(vm, INSTALL, auth, log=log)
        del auth
        yield model
    finally:
        # A failed/partial install still needs read-back cleanup.
        guest(vm, REMOVE, log=log)
