"""Bundle exact stdlib source into the normal Runtipi Compose package.
Run after source changes, before commit. No Docker build or local service startup.
"""
from pathlib import Path
import base64,json
root=Path(__file__).resolve().parent.parent
paths=sorted([*root.glob('app/*.py'),*root.glob('web/*.html')])
files={str(p.relative_to(root)):p.read_text() for p in paths}
if 'app/engine.py' not in files:
    raise SystemExit('Engine has not been integrated yet')
blob=base64.b64encode(json.dumps(files,sort_keys=True).encode()).decode()
code="import base64,json,pathlib,runpy,sys;root=pathlib.Path('/tmp/supervisor');root.mkdir(exist_ok=True);files=json.loads(base64.b64decode('"+blob+"'));[(root/p).parent.mkdir(parents=True,exist_ok=True) for p in files];[(root/p).write_text(s) for p,s in files.items()];sys.path.insert(0,str(root/'app'));runpy.run_path(str(root/'app/entry.py'),run_name='__main__')"
def svc(role):
    return {'image':'python:3.12-alpine','restart':'unless-stopped','read_only':True,'cap_drop':['ALL'],'cap_add':['CHOWN','SETUID','SETGID'],'security_opt':['no-new-privileges:true'],'mem_limit':'128m','tmpfs':['/tmp:size=16m,mode=1777'],'environment':{'ROLE':role,'DATA_DIR':'/data','SUPERVISOR_TOKEN':'${SUPERVISOR_TOKEN}','SUPERVISOR_ORIGIN':'${SUPERVISOR_ORIGIN:-}','SUPERVISOR_COOKIE_PATH':'${SUPERVISOR_COOKIE_PATH:-/supervisor-prototype/}'},'volumes':['${APP_DATA_DIR}/data/'+role+':/data'],'command':['python','-c',code]}
a,b=svc('supervisor'),svc('canary');a['x-runtipi']={'is_main':True,'internal_port':8798};a['depends_on']=['wizard-supervisor-canary']
compose={'services':{'wizard-supervisor':a,'wizard-supervisor-canary':b},'x-runtipi':{'schema_version':2,'overrides':[]}}
(root/'runtipi').mkdir(exist_ok=True)
(root/'runtipi/docker-compose.yml').write_text(json.dumps(compose,indent=2)+'\n')
print('Packaged',len(files),'files into Runtipi Compose')
