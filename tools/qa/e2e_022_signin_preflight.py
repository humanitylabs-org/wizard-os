#!/usr/bin/env python3
"""Read-only packaged AI Accounts preflight in one owned acceptance guest.

Run through the Thales heavy queue. Starts/stops only the selected guest;
never starts provider sign-in, reads credentials, or changes Serve handlers.
Evidence is private; public reports must sanitize host/runtime paths.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

GUEST = r'''
import hashlib,json,subprocess,time,urllib.request,urllib.error
from pathlib import Path

def cmd(args):
    return subprocess.check_output(args,text=True,timeout=60)
def docker(*args):
    return cmd(['sudo','-n','docker',*args])
rows=[]
for ident in docker('ps','-aq').split():
    d=json.loads(docker('inspect',ident))[0]
    name=d['Name'].lstrip('/')
    if 'ai-accounts' in name or 'hermes-agent' in name:
        rows.append(d)
accounts=[d for d in rows if 'ai-accounts' in d['Name']]
assert len(accounts)==1,'expected exactly one packaged AI Accounts container'
a=accounts[0]
assert a['State']['Running'],'AI Accounts container is not running'
password_present=any(x.startswith('AI_ACCOUNTS_PASSWORD=') and x.split('=',1)[1] for x in a['Config'].get('Env',[]))
assert not password_present,'package has an additional password gate; preserve it and resolve supported access'
ports=a['NetworkSettings']['Ports'].get('8795/tcp') or []
loopbacks=[p for p in ports if p['HostIp']=='127.0.0.1']
assert len(loopbacks)==1,'expected one loopback-only AI Accounts published port'
assert all(p['HostIp'] in ('127.0.0.1','::1') for p in ports),'unexpected non-loopback account listener'
port=int(loopbacks[0]['HostPort']); base='http://127.0.0.1:'+str(port)
def fetch(route,method='GET',headers=None,data=None):
    req=urllib.request.Request(base+route,method=method,headers=headers or {},data=data)
    try:
        with urllib.request.urlopen(req,timeout=60) as r:return r.status,r.read(),dict(r.headers)
    except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
end=time.monotonic()+180
while True:
    try:
        code,raw,_=fetch('/health')
        if code==200:break
    except (OSError,TimeoutError):pass
    assert time.monotonic()<end,'AI Accounts did not become ready'
    time.sleep(2)
assets={}
for route in ('/','/app.js','/app.css'):
    code,raw,headers=fetch(route)
    assert code==200,(route,code)
    assets[route]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'content_type':headers.get('Content-Type')}
    if route=='/app.js':
        js=raw.decode()
        assert all(s in js for s in ['/api/claude/connect','/api/claude/code','/api/accounts']), 'packaged sign-in contract missing'
code,raw,_=fetch('/api/accounts');assert code==200
state=json.loads(raw)
status=[{'id':x.get('id'),'status':x.get('status'),'signing_in':x.get('signing_in',False)} for x in state['accounts']]
# Invalid requests exercise the official handler without starting login or inference.
code,_,_=fetch('/api/claude/connect',method='POST',headers={'Content-Type':'application/json','Origin':'https://invalid.example'},data=b'{}')
assert code==403,'official origin rejection failed'
origin_rejection=code
code,_,_=fetch('/api/claude/code',method='POST',headers={'Content-Type':'text/plain'},data=b'')
assert code==415,'official JSON requirement failed'
image=json.loads(docker('image','inspect',a['Image']))[0]
containers=[]
for d in rows:
    containers.append({'name':d['Name'],'image_ref':d['Config']['Image'],'image_id':d['Image'],
        'mounts':[{'type':m['Type'],'name':m.get('Name'),'source':m['Source'],'destination':m['Destination'],'rw':m['RW']} for m in d['Mounts']],
        'provider_config':[x for x in d['Config'].get('Env',[]) if x.split('=',1)[0] in ('CLAUDE_SUBSCRIPTION_DIRECTSDK_CONFIG_DIR','CLAUDE_CONFIG_DIR','HERMES_MODEL','HERMES_PROVIDER')]})
result={'scope':'read-only packaged auth preflight; no login or inference','port':port,'assets':assets,'accounts':status,
    'origin_rejection':origin_rejection,'json_requirement':code,'containers':containers,
    'account_image':{'digests':image.get('RepoDigests',[]),'architecture':image.get('Architecture'),'revision':image.get('Config',{}).get('Labels',{}).get('org.opencontainers.image.revision')},
    'auth_modes_separate':True}
print(json.dumps(result))
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--vm',choices=['fresh-022-candidate-amd64','alongside-022-amd64'],required=True)
    args=p.parse_args()
    root=args.root.resolve()
    if platform.system()!='Darwin' or not str(root).startswith('/Volumes/ThalesMedia/'):
        p.error('execution belongs on the assigned Thales media volume')
    os.umask(0o077)
    evidence=root/'evidence'/('signin-preflight-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    evidence.mkdir(parents=True)
    env={**os.environ,'PATH':'/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin','LIMA_HOME':str(root/'lima'),'LIMA_CACHE_HOME':str(root/'lima-cache'),'TMPDIR':str(root/'tmp')}
    (root/'tmp').mkdir(exist_ok=True)
    def run(argv,**kw):return subprocess.run(argv,env=env,check=True,**kw)
    ts='/opt/homebrew/bin/tailscale'
    before=run([ts,'serve','status','--json'],capture_output=True,text=True,timeout=30).stdout
    (evidence/'serve-before.json').write_text(before)
    states=[json.loads(x) for x in run(['limactl','list','--json'],capture_output=True,text=True,timeout=30).stdout.splitlines()]
    selected=[x for x in states if x['name']==args.vm]
    assert len(selected)==1 and selected[0]['status']=='Stopped','owned guest must begin stopped'
    assert selected[0]['arch']=='x86_64'
    assert not selected[0]['config'].get('mounts'),'guest must not mount host folders'
    assert selected[0]['config'].get('portForwards') and all(x.get('ignore') for x in selected[0]['config']['portForwards'])
    source=run(['git','rev-parse','HEAD'],capture_output=True,text=True,timeout=10).stdout.strip()
    receipt={'host':platform.node(),'source_revision':source,'argv':sys.argv,'vm':args.vm,'started_at':datetime.now(timezone.utc).isoformat(),'login_started':False,'serve_changed':False}
    try:
        with (evidence/'start.log').open('w') as f:
            run(['limactl','start','--tty=false',args.vm],stdout=f,stderr=subprocess.STDOUT,timeout=240)
        out=run(['limactl','shell','--workdir=/',args.vm,'--','python3','-'],input=GUEST,text=True,capture_output=True,timeout=600)
        result=json.loads(out.stdout)
        (evidence/'package-private.json').write_text(json.dumps(result,indent=2)+'\n')
        receipt.update({'preflight':'pass','accounts':result['accounts'],'asset_hashes':result['assets']})
    except Exception as e:
        receipt.update({'preflight':'failed','error_type':type(e).__name__})
        # Raw command output is kept private and never streamed to the job log.
        if isinstance(e,subprocess.CalledProcessError):
            (evidence/'failure-private.log').write_text((e.stdout or '')+'\n'+(e.stderr or ''))
        raise
    finally:
        with (evidence/'stop.log').open('w') as f:
            run(['limactl','stop',args.vm],stdout=f,stderr=subprocess.STDOUT,timeout=180)
        after=run([ts,'serve','status','--json'],capture_output=True,text=True,timeout=30).stdout
        (evidence/'serve-after.json').write_text(after)
        receipt['serve_unchanged']=json.loads(before)==json.loads(after)
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        (evidence/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps({'evidence':str(evidence),**receipt}),flush=True)
        assert receipt['serve_unchanged'],'Serve changed concurrently; inspect before any exposure'

if __name__=='__main__':main()
