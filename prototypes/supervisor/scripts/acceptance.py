"""Bounded Thales-only packaged acceptance; always removes disposable containers.

This exercises the exact Runtipi Compose payload. It is container-package proof,
not a claim that App Manager registered the component or the shell was verified.
The optional live agent uses the exact route supplied in a private settings file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--settings',required=True);p.add_argument('--out',required=True);args=p.parse_args()
settings=json.loads(Path(args.settings).read_text());out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
if not str(out.resolve()).startswith('/Volumes/ThalesMedia/'):
    raise SystemExit('Acceptance must run on Thales external media')
token=secrets.token_urlsafe(32)
base='http://127.0.0.1:19898';canary='http://127.0.0.1:19899'
compose=json.loads((ROOT/'runtipi/docker-compose.yml').read_text())
a=compose['services']['wizard-supervisor'];b=compose['services']['wizard-supervisor-canary']
a['ports']=['127.0.0.1:19898:8798'];b['ports']=['127.0.0.1:19899:8800']
a['environment'].update(SUPERVISOR_AUTOTICK='0',SUPERVISOR_ORIGIN=base,SUPERVISOR_COOKIE_PATH='/')
for k in ('WIZARD_AGENT_URL','WIZARD_AGENT_MODEL','WIZARD_AGENT_PROVIDER','WIZARD_AGENT_TOKEN'):
    a['environment'][k]=settings.get(k,'')
for s in compose['services'].values():s.pop('x-runtipi',None)
compose.pop('x-runtipi',None)
file=out/'compose.json';file.write_text(json.dumps(compose));file.chmod(0o600)
env=dict(os.environ,PATH='/opt/homebrew/bin:'+os.environ.get('PATH',''),SUPERVISOR_TOKEN=token,APP_DATA_DIR=str(out/'app-data'))
cmd=['docker','--context',settings.get('docker_context','colima-wb'),'compose','-p','supervisor-acceptance','-f',str(file)]
report={'host':platform.node(),'source_files':{},'steps':[]}
for f in ROOT.rglob('*'):
    if f.is_file() and f.suffix in ('.py','.html','.css','.js','.yml') and '__pycache__' not in str(f):report['source_files'][str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
def req(path,body=None,url=base):
    headers={'Authorization':'Bearer '+token}
    if body is not None:headers['Content-Type']='application/json'
    request=urllib.request.Request(url+path,json.dumps(body).encode() if body is not None else None,headers=headers)
    with urllib.request.urlopen(request,timeout=40) as response:return json.load(response)
def command(argv,log):
    with (out/log).open('w') as f:
        r=subprocess.run(argv,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
    if r.returncode:raise RuntimeError(log+' failed; inspect saved log')
try:
    command([sys.executable,'-m','unittest','discover','-s','tests','-v'],'focused-tests.log')
    report['steps'].append('Focused engine and HTTP tests passed')
    command(cmd+['up','-d'],'compose-up.log')
    for _ in range(60):
        try:req('/healthz');req('/healthz',url=canary);break
        except OSError:time.sleep(1)
    else:raise RuntimeError('Packaged readiness deadline exceeded')
    report['steps'].append('Exact packaged Supervisor and canary are serving')
    # Initialize the separate job, then independently fault the service.
    req('/rerun',{'idempotency_key':'acceptance-seed-job'},canary)
    req('/fault',{'target':'service'},canary)
    start=time.time()
    while time.time()-start<240:
        req('/api/tick',{})
        status=req('/api/status')
        rows=[i for i in status['incidents'] if i['target_id']=='prototype-service']
        if rows and rows[-1]['state']=='resolved':break
        time.sleep(2)
    else:raise RuntimeError('Service did not reach verified resolution')
    probe=req('/function',url=canary)
    assert probe['ok'] is True and probe['answer']==42
    assert rows[-1]['owner_required'] is False
    report['service']=rows[-1];report['probe']=probe
    if settings.get('WIZARD_AGENT_URL'):
        assert status['reasoning']['mode']=='private-agent'
        receipts=status['reasoning']['receipts'];assert receipts and any(r['state']=='complete' for r in receipts)
        report['private_runs']=receipts
        for r in receipts:
            if r['state'] != 'complete':
                continue
            request=urllib.request.Request(settings['WIZARD_AGENT_URL'].rstrip('/')+'/v1/runs/'+r['run_id'],headers={'Authorization':'Bearer '+settings['WIZARD_AGENT_TOKEN']})
            with urllib.request.urlopen(request,timeout=15) as response:judgment=json.load(response)
            assert judgment['execution_policy']=={'tools':[],'tool_count':0,'tool_execution':'none','enforced':True}
            assert judgment['private_session_store'] is True
            assert judgment['model']==settings['WIZARD_AGENT_MODEL'] and judgment['provider']==settings['WIZARD_AGENT_PROVIDER']
        report['steps'].append('Configured real private judgment completed with enforced zero tools and isolated session storage')
    report['steps'].append('Real failed service repaired and function independently verified without owner approval')
    # Persisted data survives a real container restart.
    command(cmd+['restart','wizard-supervisor'],'restart.log')
    for _ in range(30):
        try:
            restarted=req('/api/status')
            assert any(i['id']==rows[-1]['id'] and i['state']=='resolved' for i in restarted['incidents']);break
        except OSError:time.sleep(1)
    else:raise RuntimeError('Restart/readback deadline exceeded')
    report['steps'].append('Container restart preserved verified incident')
    image=subprocess.check_output(['docker','--context',settings.get('docker_context','colima-wb'),'image','inspect','python:3.12-alpine','--format','{{json .RepoDigests}}'],text=True,env=env)
    report['image_digests']=json.loads(image)
    report['ok']=True
except Exception as error:
    report['ok']=False;report['error']=str(error)
finally:
    subprocess.run(cmd+['logs','--no-color'],env=env,stdout=(out/'container.log').open('w'),stderr=subprocess.STDOUT,timeout=30)
    subprocess.run(cmd+['down'],env=env,stdout=(out/'compose-down.log').open('w'),stderr=subprocess.STDOUT,timeout=60)
    (out/'receipt.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'ok':report.get('ok'),'steps':report['steps'],'error':report.get('error'),'receipt':str(out/'receipt.json')}))
raise SystemExit(0 if report.get('ok') else 1)
