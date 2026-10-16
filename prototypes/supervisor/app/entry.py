"""Minimal root-only app-data initialization, then drop all process privileges."""
import json
import os
from pathlib import Path
import runpy

root=Path(os.environ.get('DATA_DIR','/data'))
root.mkdir(parents=True,exist_ok=True)
if os.getuid()==0:
    for p in [root,*root.rglob('*')]:
        if p.is_symlink():
            raise SystemExit('Symlinks are not accepted in prototype state')
        os.chown(p,1000,1000)
    os.setgroups([]);os.setgid(1000);os.setuid(1000)
role=os.environ.get('ROLE','supervisor')
if role=='supervisor':
    token=os.environ.get('SUPERVISOR_TOKEN','')
    base=os.environ.get('CANARY_BASE','http://wizard-supervisor-canary:8800')
    config={'targets':{
        'prototype-service':{'name':'Recovery test service','kind':'service','probe_url':base+'/function','action_url':base+'/repair','action_token':token,'expected':{'ok':True,'answer':42},'grant':True,'action':'repair','description':'Repair only the disposable prototype service'},
        'prototype-job':{'name':'Recovery test job','kind':'job','probe_url':base+'/job','action_url':base+'/rerun','action_token':token,'expected':{'ok':True,'status':'complete','answer':42},'grant':True,'action':'rerun','description':'Rerun only the disposable internal prototype job'}},'max_attempts':2}
    config_path=root/'config.json'
    if not config_path.exists():
        config_path.write_text(json.dumps(config));config_path.chmod(0o600)
    os.environ['SUPERVISOR_CONFIG']=str(config_path)
runpy.run_path(str(Path(__file__).parent/('canary.py' if role=='canary' else 'server.py')),run_name='__main__')
