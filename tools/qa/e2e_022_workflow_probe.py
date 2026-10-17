#!/usr/bin/env python3
"""Inspect the installed fresh candidate after boot readiness, through real WAM."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

GUEST = r'''
import json, time, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / 'wizard-app-manager'))
from wam.cli import Config
c = Config()
deadline = time.monotonic() + 180
while True:
    try:
        rt = c.runtipi()  # Creating the client also probes the operator endpoint.
        rt.req('GET', '/marketplace/all')
        print('APP_MANAGER_READY', flush=True)
        break
    except Exception as error:
        if time.monotonic() >= deadline:
            raise RuntimeError('App Manager never became ready') from error
        time.sleep(2)
# This is the requested actual install entry, not a container-only substitute.
p = subprocess.run([str(Path.home()/'.wizard-os/bin/wam'), 'install', 'defleur-video'])
print('DEFLEUR_INSTALL_EXIT',p.returncode,flush=True)
registry=json.loads((Path.home()/'.wizard-os/apps.json').read_text())
print('APP_METADATA',json.dumps(registry),flush=True)
subprocess.run(['sudo','-n','docker','ps','--format','{{.Names}} {{.Ports}} {{.Status}}'],check=True)
# Read nonsecret model readiness only; never emit authentication files.
import yaml
home=Path.home()/'runtipi/app-data/wizardapps/hermes-agent/data'
cfg=yaml.safe_load((home/'config.yaml').read_text()) or {}
print('MODEL_READINESS',json.dumps({'model':cfg.get('model'),'auth_file_exists':(home/'auth.json').exists(),'env_file_exists':(home/'.env').exists()}))
for skill in (home/'skills').rglob('*SKILL.md'):
    if 'defleur' in str(skill).lower():
        print('POINTER_SKILL',str(skill.relative_to(home)),skill.read_text())
sys.exit(p.returncode)
'''

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--vm',default='fresh-022-candidate2')
    a=p.parse_args()
    if not a.vm.startswith('fresh-022-candidate'):
        p.error('only an owned candidate guest is allowed')
    env={**os.environ,'PATH':'/opt/homebrew/bin:'+os.environ.get('PATH',''),
         'LIMA_HOME':str(a.root/'lima'),'LIMA_CACHE_HOME':str(a.root/'lima-cache')}
    def run(args,**kwargs):
        return subprocess.run(args,env=env,check=True,**kwargs)
    # A wildcard-address ignore alone misses loopback listeners.
    rules='.portForwards = [{"guestIP":"127.0.0.1","guestPortRange":[1,65535],"ignore":true},{"guestIP":"0.0.0.0","guestPortRange":[1,65535],"ignore":true}]'
    run(['limactl','edit','--tty=false','--set='+rules,a.vm],timeout=60)
    try:
        run(['limactl','start','--tty=false',a.vm],timeout=180)
        run(['limactl','shell','--workdir=/',a.vm,'--','python3','-'],input=GUEST,text=True,timeout=1800)
    finally:
        run(['limactl','stop',a.vm],timeout=180)

if __name__=='__main__':
    main()
