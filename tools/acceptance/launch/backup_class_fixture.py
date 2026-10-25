#!/usr/bin/env python3
"""Seed/read explicit synthetic markers using real disposable guest storage.

No inference or account authentication. The login marker is a synthetic credential
file in the same named Docker volume used by the installed account app. Only
hashes/booleans leave the guest. Never run against an owner's box.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

FILES = {'Documents/backup-marker.txt': 'Mac origin marker\n',
         'Documents/Résumé — été.txt': 'accented filename marker\n',
         'Música/日本語 フォルダ/曲.txt': 'Japanese filename marker\n',
         'Documents/.hidden-note': 'hidden filename marker\n'}
PREFIX = 'BACKUP-MAC-ROUNDTRIP'
APP_MARKER = 'backup-acceptance-app-data'
LOGIN_MARKER = 'backup-acceptance-synthetic-login-not-valid'
LOGIN_CONTENT = json.dumps({'fixture':True, 'claudeAiOauth':{'accessToken':LOGIN_MARKER,'refreshToken':LOGIN_MARKER,'expiresAt':4070908800000}},sort_keys=True)
CLASSES = ('files', 'files_accented', 'files_japanese', 'files_hidden', 'chats',
           'memory', 'scheduled_jobs', 'settings', 'app_data', 'logins')

STOCK_SEED = r'''
import json, sys
sys.path.insert(0, '/opt/hermes')
from tools.memory_tool_store import MemoryStore
from hermes_state import SessionDB
from cron import jobs
p = 'BACKUP-MAC-ROUNDTRIP'
m = MemoryStore(); m.load_from_disk()
for kind in ('memory', 'user'):
    result = m.add(kind, p + '-' + kind)
    assert result.get('success', True), result
sid = p.lower() + '-session'
db = SessionDB()
assert not db.get_session(sid), 'Refuse reused fixture home'
db.create_session(sid, 'cli', model='acceptance-no-inference')
db.append_message(sid, 'user', p + '-question')
db.append_message(sid, 'assistant', p + '-answer')
db.end_session(sid, 'acceptance_seed'); db.close()
# Far-future one-shot: enabled at export, cannot fire during the acceptance run.
j = jobs.create_job(prompt=p, schedule='2099-01-01T00:00:00', name=p, deliver='local')
assert j.get('enabled', True) and j.get('state') != 'paused'
print(json.dumps({'id':'hermes', 'session':sid, 'cron':j['id']}))
'''
STOCK_READ = r'''
import json, sys
sys.path.insert(0, '/opt/hermes')
from tools.memory_tool_store import MemoryStore
from hermes_state import SessionDB
from cron import jobs
p = 'BACKUP-MAC-ROUNDTRIP'
m = MemoryStore(); m.load_from_disk()
db = SessionDB(); sid=p.lower()+'-session'
msgs=[{'role':r.get('role'),'content':r.get('content')} for r in db.get_messages(sid)]
db.close()
jj=[j for j in jobs.list_jobs(include_disabled=True) if j.get('name')==p]
print(json.dumps({'chats':msgs==[{'role':'user','content':p+'-question'},
 {'role':'assistant','content':p+'-answer'}],
 'memory':p+'-memory' in str(m.memory_entries) and p+'-user' in str(m.user_entries),
 'scheduled_jobs': len(jj)==1, 'cron':jj,
 'scheduled_jobs_paused':len(jj)==1 and (jj[0].get('enabled') is False or
 jj[0].get('state')=='paused' or bool(jj[0].get('paused_at')))}))
'''


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else None


def last_json(text):
    for line in reversed(text.splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            pass
    raise AssertionError('Missing stock Hermes JSON')


def root_python(script, *args):
    p = subprocess.run(['sudo', '-n', 'python3', '-c', script, *map(str, args)],
                       capture_output=True, text=True, check=True)
    return p.stdout.strip()


def boxes():
    assert Path('/var/lib/wizard-backup-disposable').is_file(), 'Disposable admission required'
    sys.path.insert(0, str(Path.cwd()))
    from wam.backup.box import Box
    b = Box()
    assert b.main_agent(), 'Main agent is required'
    rows = b.registry_rows()
    assert 'files' in rows and bool({'wizard-claude','wizard-ai-accounts'} & set(rows)), 'Install Files and account app before seeding'
    return b


def paths(b):
    return {'app': b.runtipi_root/'app-data/wizardapps/files/data/.backup-acceptance',
            'login': Path('/var/lib/docker/volumes/wizard-ai-accounts-claude/_data/backup-acceptance/.credentials.json')}


def seed(b, manifest):
    for rel, text in FILES.items():
        p = b.files_root()/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
    settings = b.home/'settings.json'
    cfg = json.loads(settings.read_text()) if settings.is_file() else {}
    cfg['backup_acceptance'] = PREFIX; settings.write_text(json.dumps(cfg))
    with getattr(b, 'operation', contextlib.nullcontext)():
        agent = last_json(b.runner.python(b.main_agent(), STOCK_SEED, ''))
    pp = paths(b)
    # Require the app-created named volume; do not fabricate a volume outside Docker.
    # Reach Docker the way WAM backup does (plain docker, else sudo -n docker): a fresh
    # box's owner is in the docker group only after the next login.
    from wam.backup.dockercli import docker
    subprocess.run([*docker(), 'volume', 'inspect', 'wizard-ai-accounts-claude'],
                   check=True, stdout=subprocess.DEVNULL)
    for key, text in (('app', APP_MARKER), ('login', LOGIN_CONTENT)):
        root_python('from pathlib import Path; import sys; p=Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(sys.argv[2]); p.chmod(0o600)', pp[key], text)
    obj = {'schema':2, 'origin':'mac', 'classes':list(CLASSES), 'agent':agent,
           'owner_files':{'files':[{'path':rel, 'sha256':hashlib.sha256(text.encode()).hexdigest()}
                                    for rel,text in FILES.items()]},
           'app_id':'files', 'login_volume':'wizard-ai-accounts-claude',
           'synthetic_login':True}
    # Publish only after every seed write has succeeded; no early copy dependency.
    temp = manifest.with_suffix('.tmp'); temp.write_text(json.dumps(obj, indent=2)); temp.replace(manifest)
    return obj


def snapshot(b, manifest):
    m = json.loads(manifest.read_text())
    assert m['schema']==2 and m['origin']=='mac' and set(m['classes'])==set(CLASSES)
    checks = {}
    names = ['files','files_accented','files_japanese','files_hidden']
    for key, entry in zip(names,m['owner_files']['files'],strict=True):
        checks[key] = digest(b.files_root()/entry['path']) == entry['sha256']
    with getattr(b, 'operation', contextlib.nullcontext)():
        state = last_json(b.runner.python(b.main_agent(), STOCK_READ, ''))
    for key in ('chats','memory','scheduled_jobs','scheduled_jobs_paused'):
        checks[key] = state[key]
    setting = b.home/'settings.json'
    cfg = json.loads(setting.read_text()) if setting.is_file() else {}
    checks['settings'] = cfg.get('backup_acceptance')==PREFIX
    pp = paths(b)
    for key, expected in (('app_data',APP_MARKER), ('logins',LOGIN_CONTENT)):
        path = pp['app' if key=='app_data' else 'login']
        checks[key] = root_python('import hashlib,sys; from pathlib import Path; p=Path(sys.argv[1]); print(hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "missing")',path)==hashlib.sha256(expected.encode()).hexdigest()
    # Hash refused app data + wiring + secret scopes independently from the rest.
    script = '''import hashlib,json,os,sys
from pathlib import Path
out={}
for raw in sys.argv[1:]:
 p=Path(raw)
 for f in sorted(p.rglob('*')) if p.is_dir() else ([p] if p.exists() else []):
  if f.is_file() and not f.is_symlink(): out[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
print(json.dumps(out,sort_keys=True))'''
    scopes = [b.runtipi_root/'app-data/wizardapps/files', b.runtipi_root/'user-config/wizardapps/files',
              b.home/'secrets/files.json', b.home/'app-tokens/files']
    # App config/data are stopped by the import; the marker stays stable across runtime caches.
    return {'checks':checks, 'cron_ids':[j['id'] for j in state['cron']],
            'refused_scope':json.loads(root_python(script,*scopes))}


def set_newer(b):
    """Actual exported app package/registry fixture, never edited archive/receipt/fake CLI.

    Version 9999 is deliberately reserved for this disposable refusal fixture.
    Both installed package and apps.json agree before the real exporter runs.
    """
    from wam.backup import versions
    regpath=b.home/'apps.json'; reg=json.loads(regpath.read_text())
    row=next(x for x in reg['apps'] if x['id']=='files')
    old={'row':dict(row),'files':{}}
    for package in (b.app_package('wizardapps','files'), b.store_package('wizardapps','files')):
        p=package/'wizard.md'
        if p.is_file():
            text=p.read_text(); old['files'][str(p)]=text
            changed,n=re.subn(r'(?m)^version: .*$', 'version: 9999.0.0',text)
            assert n==1
            root_python('from pathlib import Path; import sys; Path(sys.argv[1]).write_text(sys.argv[2])',p,changed)
    assert old['files'], 'Real installed Files package required'
    row['version']='9999.0.0'; regpath.write_text(json.dumps(reg))
    assert versions.package_release(b.app_package('wizardapps','files'))['version']=='9999.0.0'
    return old


def main():
    b=boxes(); mode=sys.argv[1]; manifest=Path(sys.argv[2])
    if mode=='seed': result=seed(b,manifest)
    elif mode=='snapshot': result=snapshot(b,manifest)
    elif mode=='newer': result=set_newer(b)
    elif mode=='receipt':
        from wam.backup.restore import last_restore
        folder,_=last_restore(b); raw=json.loads((folder/'receipt.json').read_text())
        result={k:raw[k] for k in ('ok','partial','refused','not_restored')}
    elif mode=='refusal-baseline':
        for p in (paths(b)['app'],b.home/'secrets/files.json',b.home/'app-tokens/files'):
            # Seed as root, but leave created files/parent dirs owned like the box home, as the Service would.
            root_python("import os,sys; from pathlib import Path; p=Path(sys.argv[1]); home=Path(sys.argv[2]); st=home.stat(); missing=[d for d in reversed(p.parents) if not d.exists()]; p.parent.mkdir(parents=True,exist_ok=True); [os.chown(d,st.st_uid,st.st_gid) for d in missing]; existed=p.exists(); p.write_text('REFUSAL-TARGET-KEEP'); p.chmod(0o600); None if existed else os.chown(p,st.st_uid,st.st_gid)",p,b.home)
        result={'seeded_refusal_baseline':True}
    else: raise ValueError(mode)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__': main()
