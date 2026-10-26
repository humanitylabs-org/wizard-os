#!/usr/bin/python3
"""Validate staged startup without starting anything; --activate is target helper-only.
Never print compose config/environment, which may contain credentials.
  check-startup.py STAGED_DIR [--activate]   (--activate needs HOP_EXPECT_MACHINE, set by promote.sh)
"""
import json,os,pathlib,subprocess,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import hopenv
CFG=hopenv.load()
CORE=CFG.get('HOP_CORE_PROJECT') or 'runtipi'
STANDALONE=dict(x.split('=',1) for x in hopenv.words(CFG,'HOP_STANDALONE_ALLOWED') if '=' in x)
st=pathlib.Path(sys.argv[1]);inventory=json.loads((st/'containers.json').read_text());rows=[l.rstrip('\n').split('\t') for l in (st/'compose-projects.tsv').open()];active='--activate' in sys.argv
if active:
 want=os.environ.get('HOP_EXPECT_MACHINE','')
 if not want or os.uname().nodename.split('.')[0]!=want:raise SystemExit('activation is target-only')
 barrier=json.loads(subprocess.check_output(['/usr/local/bin/host-hop-recovery','status'],text=True))
 if not (barrier.get('promotion_barrier') and barrier.get('source_stopped') and barrier.get('phase')=='target-may-write'):raise SystemExit('source promotion barrier absent')

def run(a):
 p=subprocess.run(a,capture_output=True,text=True,timeout=240)
 if p.returncode:raise SystemExit('startup validation failed: '+a[0]+' '+a[1]+' (details omitted; configuration may contain secrets)')
 return p.stdout
for name,c in inventory.items():run(['docker','image','inspect',c['image']])
rows.sort(key=lambda x:0 if len(x)>1 and x[1]==CORE else 1)
projects=0
for r in rows:
 if r[0]=='project':
  _,p,wd,files,envs,svcs=r;a=['docker','compose','-p',p,'--project-directory',wd]
  for f in filter(None,files.split(',')):
   if not pathlib.Path(f).is_file():raise SystemExit('missing compose file: '+f)
   a+=['-f',f]
  for e in filter(None,envs.split(',')):
   if not pathlib.Path(e).is_file():raise SystemExit('missing compose environment file: '+e)
   a+=['--env-file',e]
  imgs={c['service']:{'image':c['image']} for c in inventory.values() if c.get('project')==p}
  if set(imgs)!=set(svcs.split()):raise SystemExit('frozen service-set mismatch for '+p)
  out=st/'exact-images';out.mkdir(exist_ok=True);override=out/(p+'.json');override.write_text(json.dumps({'services':imgs}));a+=['-f',str(override)]
  config=json.loads(run(a+['config','--format','json']))
  if any(config['services'][s]['image']!=v['image'] for s,v in imgs.items()):raise SystemExit('image override mismatch for '+p)
  if active:run(a+['up','-d','--no-deps','--pull','never','--no-build',*svcs.split()])
  projects+=1
 elif r[0]=='standalone':
  if STANDALONE.get(r[1])!=r[2]:raise SystemExit('unreviewed standalone container: '+r[1])
  if active:run(['docker','start',r[1]])
if active:
 end=time.monotonic()+180
 while True:
  runtime=json.loads(run(['docker','container','inspect',*inventory]))
  if all(c['State']['Running'] and c['State'].get('Health',{}).get('Status','healthy')=='healthy' for c in runtime):break
  if time.monotonic()>end:raise SystemExit('captured containers did not reach running/healthy')
  time.sleep(3)
 if any(c['Image']!=inventory[c['Name'].lstrip('/')]['image'] for c in runtime):raise SystemExit('running image differs from frozen digest')
print(json.dumps({'startup':'activated-and-image-verified' if active else 'validated-no-start','projects':projects,'containers':len(inventory)}))
