#!/usr/bin/python3
"""Host-hop transaction. No cutover without the separate parent launch capability.
Commands preflight/status are read-only; launch is always a separate systemd unit.

  runner.py status | abort
  runner.py preflight FROM TO
  runner.py execute FROM TO            (only from launch.sh --parent-recovery-sent)
  runner.py recover-source [FROM TO]   (FROM/TO default to the recorded transaction)
"""
import argparse,datetime,fcntl,fnmatch,hashlib,json,os,pathlib,re,shlex,signal,sqlite3,subprocess,sys,time,urllib.request
if sys.flags.optimize:raise SystemExit('refusing optimized Python: admission assertions must execute')
D=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(D))
import hopenv
CFG=hopenv.load()
H=pathlib.Path(CFG['HOP_HOME']); S=H/'.local/share/host-hop'; TX=S/'transaction.json'
UID=os.getuid()
ENV=dict(os.environ,XDG_RUNTIME_DIR=f'/run/user/{UID}',DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{UID}/bus',DOCKER_HOST=f'unix:///run/user/{UID}/docker.sock',PATH=f'{H}/bin:{H}/.local/bin:/usr/local/bin:/usr/bin:/bin')
INFRA={'dbus.service','docker.service','gpg-agent.service','at-spi-dbus-bus.service'}
HOST_LOCAL=hopenv.words(CFG,'HOP_HOST_LOCAL_UNITS')
UNIT_SKIP=CFG.get('HOP_UNIT_SKIP_REGEX') or r'(^|[-_])(qa|test|candidate)([-_.]|$)'
SRC=None;DST=None   # host keys from hosts.env HOP_HOSTS; set by main()
def set_hosts(src,dst):
 global SRC,DST
 known=hopenv.words(CFG,'HOP_HOSTS')
 if src not in known or dst not in known or src==dst:raise SystemExit('FROM and TO must be two different host keys from HOP_HOSTS: '+' '.join(known))
 SRC,DST=src,dst
def hv(kind,host):return hopenv.hv(CFG,kind,host)
def machine(h):return hv('MACHINE',h)
def tsip(h):return hv('TSIP',h)
def main_name():return CFG['HOP_AGENT']+'-main'
def standby_name(h):return CFG['HOP_AGENT']+'-backup-'+(hv('BACKUP_INDEX',h) or '1')
def fqdn(name):return name+'.'+CFG['HOP_TAILNET_SUFFIX']
def status_base():return 'http://'+tsip(DST)+':'+CFG.get('HOP_STATUS_PORT','8979')
def container_skip():return CFG.get('HOP_CONTAINER_SKIP_REGEX') or r'(^|[-_])(qa|test|candidate)([-_]|$)'
def q(x):return shlex.quote(str(x))
def run(args,timeout=120,check=True,input=None):
 p=subprocess.Popen(args,env=ENV,stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 try:out,err=p.communicate(input,timeout=timeout)
 except BaseException:
  try:os.killpg(p.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:p.communicate(timeout=5)
  except subprocess.TimeoutExpired:
   try:os.killpg(p.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   p.communicate()
  raise
 if check and p.returncode:
  # Keep failure details private for diagnosis, never in public status/journal (lesson 8).
  private=S/'private-failures';private.mkdir(mode=0o700,parents=True,exist_ok=True);os.chmod(private,0o700)
  failure_id=str(time.time_ns())
  atomic(private/(failure_id+'.json'),{'argv':[str(a) for a in args],'returncode':p.returncode,'stderr':err,'stdout':out})
  raise RuntimeError(f'command failed rc={p.returncode}: {pathlib.Path(str(args[0])).name}; private failure {failure_id} (arguments/stderr omitted to protect secrets)')
 return out.strip()
def shell(cmd,**kw):return run(['bash','-c',cmd],**kw)
def lib():return '. '+q(D/'lib.sh')+'; '
def remote(cmd,**kw):return shell(lib()+'on '+q(DST)+' '+q(cmd),**kw)
def push_staged(f):shell(lib()+'rsync -a -e "ssh $HOP_SSH_BASE" '+q(str(f)+'/')+' "$(host_ssh '+q(DST)+')":'+q(str(S/'staged')+'/'))
def atomic(p,d):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.new');t.write_text(json.dumps(d,indent=2)+'\n');os.chmod(t,0o600);os.replace(t,p)
def load():return json.loads(TX.read_text()) if TX.exists() else {'phase':'prepared-not-launched','promotion_barrier':False,'source_stopped':False}
def publish(st):
 st['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();atomic(TX,st)
 safe={k:st[k] for k in ('phase','updated_at','promotion_barrier','source_stopped','error','run_id') if k in st}
 for k in ('estimated_service_stop_seconds','actual_service_stop_seconds','warm_sync_seconds'):
  if k in st:safe[k]=st[k]
 # A lost remote publication must not undo a local durable promotion barrier.
 remote('printf %s '+q(json.dumps(safe))+' | sudo -n tee /var/lib/host-hop-status/status.json >/dev/null; sudo -n chmod 644 /var/lib/host-hop-status/status.json',timeout=20)
 observed=json.loads(remote('cat /var/lib/host-hop-status/status.json',timeout=20))
 if observed!=safe:raise RuntimeError('independent status readback mismatch')
 print(json.dumps(safe),flush=True)
def service(u):return shell('systemctl --user show '+q(u)+' -p MainPID -p ActiveState -p ControlGroup -p FragmentPath')
def pid(u):return int(shell('systemctl --user show '+q(u)+' -p MainPID --value') or 0)
def stopped(u):
 props=dict(l.split('=',1) for l in service(u).splitlines() if '=' in l)
 if props.get('MainPID')!='0' or props.get('ActiveState') not in ('inactive','failed'):return False
 cg=props.get('ControlGroup','')
 if cg:
  base=pathlib.Path('/sys/fs/cgroup')/cg.lstrip('/')
  if base.exists() and any(p.read_text().strip() for p in base.rglob('cgroup.procs')):return False
 return True
def allowed(u):
 # Infrastructure, machine-local units (HOP_HOST_LOCAL_UNITS) and disposable units (lesson 3) never move.
 if u in INFRA or u.startswith(('host-hop-','hop-exempt-','ssh','tailscale')):return False
 if any(fnmatch.fnmatchcase(u,g) for g in HOST_LOCAL):return False
 return not re.search(UNIT_SKIP,u)
def jhttp(url):
 with urllib.request.urlopen(url,timeout=8) as r:return json.load(r)
def wait_dns(want,limit=90):
 # Lesson 1: Tailscale applies a hostname change asynchronously; poll instead of asserting once.
 until=time.monotonic()+limit;seen=None
 while True:
  seen=json.loads(remote('tailscale status --self --json'))['Self']['DNSName'].rstrip('.')
  if seen==want:return
  if time.monotonic()>until:raise RuntimeError('target DNS name is '+repr(seen)+', expected '+want)
  time.sleep(3)
def wait_health(limit=120):
 # Lesson 2: services listen seconds after systemd reports them started; wait with a bound.
 until=time.monotonic()+limit
 while True:
  try:
   if pid('hermes-gateway.service') and jhttp('http://127.0.0.1:8797/health')['status']=='ok':return True
  except Exception:pass
  if time.monotonic()>until:return False
  time.sleep(3)
def work():
 ui=jhttp('http://127.0.0.1:8797/health'); gw=json.loads((H/'.hermes/gateway_state.json').read_text())
 age=time.time()-datetime.datetime.fromisoformat(gw['updated_at'].replace('Z','+00:00')).timestamp()
 if age>45:raise RuntimeError('stale gateway status')
 leases=0;homes=[H/'.hermes',*(H/'.hermes/profiles').glob('*')]
 # Every profile: do not discard current conversation/child leases as control-plane work.
 for home in homes:
  p=home/'state.db'
  if not p.exists():continue
  with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True,timeout=5) as c:
   if c.execute("select 1 from sqlite_master where name='session_turn_leases'").fetchone():leases+=c.execute('select count(*) from session_turn_leases where expires_at>?',(time.time(),)).fetchone()[0]
 locks=0
 for p in (p for home in homes for p in (home/'cron').glob('.fire-*.lock')):
  with p.open('rb') as f:
   try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:locks+=1
 return {'ui_runs':int(ui['active_runs']),'ui_streams':int(ui['active_streams']),'gateway_agents':int(gw['active_agents']),'api_runs':int(gw['platforms']['api_server']['metrics']['active_runs']),'leases':leases,'cron_locks':locks,'gateway_state':gw['gateway_state']}
def idle(w):return all(w[k]==0 for k in ('ui_runs','ui_streams','gateway_agents','api_runs','leases','cron_locks'))
def drain(on):
 code="from gateway.drain_control import "+('write_drain_request; write_drain_request(principal=\"host-hop\",suppress_notification=False)' if on else 'clear_drain_request; clear_drain_request()')
 # Use the installed Hermes runtime, not a guessed system Python dependency set.
 py=H/'.hermes/hermes-agent/venv/bin/python'
 if not py.exists():py=H/'.hermes/hermes-agent/.venv/bin/python'
 run([str(py),'-c','import sys;sys.path.insert(0,'+repr(str(H/'.hermes/hermes-agent'))+');'+code],timeout=30)
def wait_idle(st,seconds=60,deadline=7200):
 # Idle gate: 60 s of zero work while draining, bounded at 2 h; expiry stops nothing.
 end=time.monotonic()+deadline;since=None;refreshed=time.monotonic()
 while time.monotonic()<end:
  if time.monotonic()-refreshed>900:drain(True);refreshed=time.monotonic()
  w=work();st['work']=w;publish(st)
  if idle(w) and w['gateway_state']=='draining':
   since=since or time.monotonic()
   if time.monotonic()-since>=seconds:return
  else:since=None
  time.sleep(5)
 raise RuntimeError('stable idle deadline expired; no source services stopped')
def verify_bundle():
 manifest=D/'RELEASE-SHA256SUMS'
 if not manifest.is_file():raise RuntimeError('no verified artifact manifest; refuse execution (run make-manifest.sh after review)')
 listed={}
 for line in manifest.read_text().splitlines():
  digest,name=line.split('  ',1)
  if not re.fullmatch(r'[a-f0-9]{64}',digest) or pathlib.Path(name).name!=name:raise RuntimeError('invalid artifact manifest')
  listed[name]=digest
 actual={p.name for p in D.iterdir() if p.is_file() and p.suffix in ('.sh','.py','.env')}
 if actual!=set(listed):raise RuntimeError('artifact set differs from reviewed manifest')
 for name,digest in listed.items():
  if hashlib.sha256((D/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('artifact changed after review: '+name)
def preflight():
 verify_bundle()
 assert os.uname().nodename.split('.')[0]==machine(SRC),'run on the source host '+SRC
 assert pid('hermes-gateway.service')>0,'source gateway absent'
 assert remote('systemctl --user show hermes-gateway.service -p MainPID --value')=='0','target gateway running'
 assert remote('test -e ~/.wizard-os/standby.lock && echo guarded')=='guarded'
 assert remote('/usr/local/bin/host-hop-recovery probe')=='host-hop-reverse-ok '+machine(SRC),'reverse SSH'
 assert jhttp(status_base()+'/health')['phase'],'independent HTTP'
 assert remote('sudo -n test -r /opt/host-hop-status/server.py && echo ok')=='ok'
 assert remote('(test -x ~/.hermes/hermes-agent/venv/bin/python -o -x ~/.hermes/hermes-agent/.venv/bin/python) && echo ok')=='ok'
 manifest=(D/'RELEASE-SHA256SUMS').read_text()
 assert remote('cat '+q(D/'RELEASE-SHA256SUMS'))==manifest.strip(),'target artifact manifest differs'
 remote('cd '+q(D)+' && sha256sum -c RELEASE-SHA256SUMS >/dev/null')
 assert remote('test -x '+q(H/'.local/bin/hermes')+' && test -r '+q(D/'continue.sh')+' && echo ok')=='ok','target continuation absent'
 assert not (H/'.hermes/.drain_request.json').exists(),'pre-existing drain belongs to another operator'
 # Prove raw-IP direct connection independent of control masters.
 key=hv('DIRECT_KEY',DST) or str(H/'.ssh'/(DST+'_ed25519'))
 assert shell('ssh -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile='+q(S/'target_known_hosts')+' -o IdentitiesOnly=yes -o ConnectTimeout=8 -i '+q(key)+' '+q(CFG['HOP_USER']+'@'+tsip(DST))+' hostname -s')==machine(DST)
 w=work()
 return {'preflight':'pass','source':SRC,'target':DST,'source_gateway_pid':pid('hermes-gateway.service'),'source_wizard_pid':pid('hermesui.service'),'work':w,'target_gateway_pid':0,'status_url':status_base()+'/status.json','preview_containers':int(remote('docker ps -q | wc -l'))}
def estimate_after_warm(st):
 samples=[]
 for p in (S/'sync').glob('timings-*'):
  try:d={k:float(v) for k,v in (l.split() for l in p.read_text().splitlines())}
  except (ValueError,OSError):continue
  if all(k in d for k in ('home','db','pg','volumes','sqlite-inventory','total')):samples.append((p.stat().st_mtime,d))
 if not samples:raise RuntimeError('no complete measured warm sync for downtime estimate')
 measured=max(samples,key=lambda x:x[0])[1];delta=sum(measured[k] for k in ('home','db','pg','volumes','sqlite-inventory'))
 overhead=float(CFG.get('HOP_STOP_START_OVERHEAD_SECONDS') or 120)
 st['warm_sync_seconds']=measured['total'];st['estimated_service_stop_seconds']=[round(delta+overhead+60),round(delta+overhead+180)];publish(st)
def freeze(st):
 # Frozen inventory: the new main starts exactly this set, never re-read from the stopped source.
 f=S/('frozen-'+st['run_id']);f.mkdir(mode=0o700)
 for name in ('enabled-units.txt','running-units.txt','running-containers.txt','compose-projects.tsv','serve.json'):
  p=S/'sync'/name
  if not p.exists():raise RuntimeError('missing warm inventory '+name)
  (f/name).write_bytes(p.read_bytes())
 units=[u for u in (f/'running-units.txt').read_text().split() if allowed(u)]
 # Timers/paths active, not merely enabled; preserve paused schedules.
 timers=[x.split()[0] for x in shell('systemctl --user list-units --state=active --type=timer,path --no-legend').splitlines() if x.strip()]
 skip=container_skip()
 ctrs=[x for x in (f/'running-containers.txt').read_text().split() if not re.search(skip,x)]
 # Lesson 5: container-typed lookup; a same-named volume must not answer.
 raw=json.loads(run(['docker','container','inspect',*ctrs]));inventory={x['Name'].lstrip('/'): {'id':x['Id'],'image':x['Image'],'project':(x['Config'].get('Labels') or {}).get('com.docker.compose.project'),'service':(x['Config'].get('Labels') or {}).get('com.docker.compose.service'),'restart':x['HostConfig']['RestartPolicy'],'mounts':x['Mounts']} for x in raw}
 (f/'running-units.txt').write_text('\n'.join(units)+'\n');(f/'running-containers.txt').write_text('\n'.join(ctrs)+'\n');atomic(f/'containers.json',inventory);atomic(f/'active-schedules.json',timers)
 sums=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(f.iterdir()) if p.is_file())
 (f/'SHA256SUMS').write_text(sums)
 st.update(source_role_before=(H/'.wizard-os/host-role').read_text() if (H/'.wizard-os/host-role').exists() else None, frozen=str(f),units=units,timers=timers,containers=ctrs,enabled=(f/'enabled-units.txt').read_text().split(),old_source_name=json.loads(shell('tailscale status --self --json'))['Self']['HostName'])
 for p in f.iterdir():os.chmod(p,0o400)
 publish(st);return f

def assert_source_cold(st):
 for u in st['units']:
  if not stopped(u):raise RuntimeError('source unit still running: '+u)
 skip=container_skip()
 running={n for n in shell("docker ps --format '{{.Names}}'").split() if not re.search(skip,n)}
 if running:raise RuntimeError('source production containers still running')
 services=[x.split()[0] for x in shell('systemctl --user list-units --state=running --type=service --no-legend').splitlines() if x.strip() and allowed(x.split()[0])]
 if services:raise RuntimeError('unfenced source services remain: '+','.join(services))
def forced_command_fence(st,on):
 # Optional (HOP_FENCE_FORCED_COMMAND): swap one exact authorized_keys forced command used by the target
 # for forced-command-fence.sh while draining; restore it byte-for-byte on recovery.
 if not on and not st.get('fence_old_line'):return
 old_command=CFG.get('HOP_FENCE_FORCED_COMMAND','')
 if on and not old_command:return
 p=H/'.ssh/authorized_keys';s=p.read_text();new_command=str(D/'forced-command-fence.sh')
 if on:
  lines=[l for l in s.splitlines() if 'command="'+old_command+'"' in l and 'from="'+tsip(DST)+'"' in l]
  if len(lines)!=1:raise RuntimeError('fenced SSH provider differs from expected preimage')
  st['fence_old_line']=lines[0];st['fence_new_line']=lines[0].replace('command="'+old_command+'"','command="'+new_command+'"');publish(st)
  s=s.replace(st['fence_old_line'],st['fence_new_line'])
 else:
  if not st.get('fence_old_line'):return
  if st['fence_new_line'] not in s:
   if st['fence_old_line'] in s:return
   raise RuntimeError('fenced SSH authorization changed; refusing overwrite')
  s=s.replace(st['fence_new_line'],st['fence_old_line'])
 temp=p.with_name('authorized_keys.host-hop-new');temp.write_text(s);os.chmod(temp,0o600);os.replace(temp,p)
 if (st['fence_new_line'] if on else st['fence_old_line']) not in p.read_text():raise RuntimeError('fenced SSH authorization readback failed')
def recover_source(st):
 # Ambiguous target start is a permanent barrier. Never infer safety from failed health.
 if st.get('promotion_barrier'):raise RuntimeError('REFUSED: target may have accepted writes. Forward diagnosis or separately authorized reverse data migration required.')
 if not st.get('source_stopped'):
  if st.get('schedulers_attempted'):
   for u in st.get('timers',[]):shell('systemctl --user start '+q(u))
  if st.get('drain_owned'):drain(False)
  forced_command_fence(st,False)
  st['phase']='aborted-before-source-stop';publish(st);return
 # Fail closed unless target is known cold, even on errors before intended activation.
 if remote('test -e ~/.wizard-os/standby.lock && echo guarded')!='guarded' or remote('systemctl --user show hermes-gateway.service -p MainPID --value')!='0' or remote('docker ps -q'):raise RuntimeError('target not cold; no source restart')
 for u in st['units']:
  props=dict(l.split('=',1) for l in remote('systemctl --user show '+q(u)+' -p MainPID -p ActiveState').splitlines() if '=' in l)
  if props.get('MainPID')!='0' or props.get('ActiveState') not in ('inactive','failed'):raise RuntimeError('target service not fenced; no source restart: '+u)
 (H/'.wizard-os/standby.lock').unlink(missing_ok=True)
 role=H/'.wizard-os/host-role'
 if st.get('source_role_before') is not None:role.write_text(st['source_role_before'])
 else:role.unlink(missing_ok=True)
 if st.get('source_stopped'):
  inventory=json.loads((pathlib.Path(st['frozen'])/'containers.json').read_text())
  for name,c in inventory.items():
   rp=c['restart'];value=rp['Name'] or 'no'
   if value=='on-failure' and rp.get('MaximumRetryCount'):value+=':'+str(rp['MaximumRetryCount'])
   run(['docker','update','--restart='+value,name])
 # Retain all source original files; no reverse copy is needed before promotion.
 if st.get('old_source_name'):shell('timeout 25 tailscale set --hostname='+q(st['old_source_name']))
 if st.get('target_renamed'):
  try:remote('timeout 25 tailscale set --hostname='+q(hv('TSNAME',DST))+' </dev/null')
  except Exception as e:st['target_rename_back_error']=str(e)
 run(['docker','start',*st['containers']],timeout=180)
 for u in st['units']:
  if u=='hermesui.service':continue
  # Lesson 3: a transient unit another thread created and removed has nothing to restore.
  if shell('systemctl --user show '+q(u)+' -p LoadState --value')=='not-found':continue
  shell('systemctl --user start '+q(u),timeout=100)
 if 'hermesui.service' in st['units']:shell('systemctl --user start hermesui-launcher.service',timeout=100)
 for u in st['timers']:shell('systemctl --user start '+q(u))
 restore_serve(json.loads((pathlib.Path(st['frozen'])/'serve.json').read_text()),False)
 drain(False);forced_command_fence(st,False)
 if not wait_health():raise RuntimeError('source recovery health failed')
 st['phase']='source-recovered';st['source_stopped']=False;publish(st)
def restore_serve(data,target):
 call=remote if target else shell
 skip_ports=set(hopenv.words(CFG,'HOP_SERVE_SKIP_PORTS_ON_TARGET'))
 call('timeout 25 tailscale serve reset </dev/null');expected=set()
 for hp,cfg in data.get('Web',{}).items():
  port=hp.rsplit(':',1)[1]
  if target and port in skip_ports:continue
  for path,h in cfg.get('Handlers',{}).items():
   if 'Proxy' in h:
    expected.add((port,path,h['Proxy']))
    call('timeout 25 tailscale serve --bg --https='+q(port)+' --set-path='+q(path)+' '+q(h['Proxy'])+' </dev/null')
 actual=json.loads(call('tailscale serve status --json'))
 observed={(hp.rsplit(':',1)[1],p,h['Proxy']) for hp,c in actual.get('Web',{}).items() for p,h in c.get('Handlers',{}).items() if 'Proxy' in h}
 if observed!=expected:raise RuntimeError('Serve handler readback differs from frozen plan')
def assert_independent():
 cg=pathlib.Path('/proc/self/cgroup').read_text()
 if 'host-hop-cutover-' not in cg or 'hermes-gateway.service' in cg or 'hermesui.service' in cg:raise RuntimeError('not independent cutover cgroup')
def execute():
 if os.environ.get('HOP_PARENT_LAUNCH')!='OWNER_RECOVERY_SENT':raise RuntimeError('parent launch gate absent; no mutation')
 assert_independent()
 if load().get('promotion_barrier'):raise RuntimeError('previous promotion barrier; no automatic retry')
 hosts=' '+q(SRC)+' '+q(DST)
 preflight();st={'run_id':datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'),'source':SRC,'target':DST,'unit':pathlib.Path('/proc/self/cgroup').read_text().strip().rsplit('/',1)[-1],'runner_pid':os.getpid(),'phase':'preview-teardown','promotion_barrier':False,'source_stopped':False};publish(st)
 try:
  # Preview disappears here; source remains live. Restore full native API only after activation.
  shell('bash '+q(D/'test-mode.sh')+' '+q(DST)+' stop',timeout=300)
  assert remote('docker ps -q')==''
  until=time.monotonic()+90
  while remote('systemctl --user show hermesui.service -p MainPID --value')!='0':
   if time.monotonic()>until:raise RuntimeError('target preview UI did not quiesce')
   time.sleep(1)
  assert remote('ss -ltnH sport = :8797')==''
  assert remote('ss -ltnH sport = :8642')==''
  assert remote('sudo -n iptables -S HOP-TEST >/dev/null 2>&1; echo $?')=='1'
  assert remote('sudo -n ip6tables -S HOP-TEST >/dev/null 2>&1; echo $?')=='1'
  st['phase']='warm-sync';publish(st);shell('bash '+q(D/'sync.sh')+hosts,timeout=3600)
  estimate_after_warm(st);f=freeze(st)
  # Install freshly staged target files under existing standby guards; no target workloads start.
  shell('bash '+q(D/'standby-install.sh')+' '+q(DST),timeout=1800)
  push_staged(f)
  remote('python3 '+q(D/'check-startup.py')+' '+q(S/'staged'),timeout=300)
  st['phase']='waiting-stable-idle';st['drain_owned']=True;publish(st);forced_command_fence(st,True);drain(True);wait_idle(st)
  # Revalidate the frozen startup/scheduler preimage after an arbitrarily long idle wait.
  schedules={x.split()[0] for x in shell('systemctl --user list-units --state=active --type=timer,path --no-legend').splitlines() if x.strip()}
  enabled=set(shell("systemctl --user list-unit-files --state=enabled --no-legend | awk '{print $1}'").split())
  if schedules!=set(st['timers']) or enabled!=set(st['enabled']):raise RuntimeError('schedule/enablement drift since frozen inventory')
  st['schedulers_attempted']=True;publish(st)
  # Stop only schedulers, then recheck to close the schedule/work race.
  for u in st['timers']:shell('systemctl --user stop '+q(u))
  if not idle(work()):raise RuntimeError('work returned at scheduler fence')
  current={x.split()[0] for x in shell('systemctl --user list-units --state=running --type=service --no-legend').splitlines() if x.strip() and allowed(x.split()[0])}
  if current-set(st['units']):raise RuntimeError('new service appeared since frozen inventory; abort before downtime')
  skip=container_skip()
  now_containers={n for n in shell("docker ps --format '{{.Names}}'").split() if not re.search(skip,n)}
  if now_containers!=set(st['containers']):raise RuntimeError('production container set changed since inventory')
  expected=json.loads((f/'containers.json').read_text())
  actual=json.loads(run(['docker','container','inspect',*st['containers']]))
  if any(expected[c['Name'].lstrip('/')]['id']!=c['Id'] for c in actual):raise RuntimeError('source container identity drift')
  st['phase']='source-stopping';st['source_stopped']=True;st['service_stop_started_at']=time.time();publish(st)
  # Fence ingress after zero-work; stop exact captured units, gateway first.
  shell('timeout 25 tailscale serve reset </dev/null')
  if not idle(work()):raise RuntimeError('work appeared during ingress fence; source must recover without interruption')
  shell('systemctl --user stop hermes-gateway.service',timeout=100)
  if not stopped('hermes-gateway.service'):raise RuntimeError('gateway not stopped')
  ui=jhttp('http://127.0.0.1:8797/health')
  if ui['active_runs'] or ui['active_streams']:raise RuntimeError('Wizard App work appeared; preserve worker and recover source')
  for u in st['units']:
   if u=='hermes-gateway.service':continue
   if u=='hermesui.service':shell('systemctl --user kill --kill-who=all --signal=TERM hermesui.service')
   else:shell('systemctl --user stop '+q(u),timeout=120)
  until=time.monotonic()+90
  while pid('hermesui.service') and time.monotonic()<until:time.sleep(1)
  run(['docker','stop','-t','60',*st['containers']],timeout=240);assert_source_cold(st)
  # Make source reboot inert, preserving captured originals for recovery.
  for u in set(st['units']+st['timers']+st['enabled']):
   if not allowed(u):continue
   dd=H/'.config/systemd/user'/(u+'.d');dd.mkdir(parents=True,exist_ok=True);(dd/'zz-host-hop-fence.conf').write_text('[Unit]\nConditionPathExists=!'+str(H/'.wizard-os/standby.lock')+'\n')
  (H/'.wizard-os/standby.lock').touch();(H/'.wizard-os/host-role').write_text('HOP_ROLE=standby\nHOP_AGENT='+CFG['HOP_AGENT']+'\nHOP_TSNAME='+standby_name(SRC)+'\nHOP_TSIP='+tsip(SRC)+'\n');shell('systemctl --user daemon-reload')
  run(['docker','update','--restart=no',*st['containers']]);st['phase']='final-sync';publish(st)
  for step in ('home','db','pg','volumes'):
   shell('HOP_FROZEN_DIR='+q(f)+' bash '+q(D/'sync.sh')+hosts+' --final --only '+step,timeout=3600)
  # Verify all copied session databases before allowing any target writer.
  expected_db=json.loads(run(['/usr/bin/python3',str(D/'check-databases.py')],timeout=180))
  target_db=json.loads(remote('python3 '+q(D/'check-databases.py')+' --quick-check',timeout=600))
  if {k:v['counts'] for k,v in expected_db.items()}!={k:v['counts'] for k,v in target_db.items()}:raise RuntimeError('source/target database row counts differ')
  st['database_counts']={k:v['counts'] for k,v in target_db.items()};publish(st)
  # Copy immutable pre-stop inventories, never enumerate stopped source for target startup.
  push_staged(f)
  st['phase']='identity';publish(st)
  shell('timeout 25 tailscale set --hostname='+q(standby_name(SRC))+' </dev/null');remote('timeout 25 tailscale set --hostname='+q(main_name())+' </dev/null')
  st['target_renamed']=True;publish(st)
  wait_dns(fqdn(main_name()))
  remote('bash '+q(D/'promote.sh')+' prepare'+hosts,timeout=180)
  assert_source_cold(st)
  # Promotion barrier: persist BEFORE any target starts. Failures after this point never auto-failback.
  st['promotion_barrier']=True;st['phase']='target-may-write';publish(st)
  remote('bash '+q(D/'promote.sh')+' activate'+hosts,timeout=600)
  restore_serve(json.loads((f/'serve.json').read_text()),True)
  remote('bash '+q(D/'promote.sh')+' verify'+hosts,timeout=180)
  assert_source_cold(st)
  st['phase']='complete';st['actual_service_stop_seconds']=round(time.time()-st['service_stop_started_at'],1);publish(st)
  try:remote('bash '+q(D/'continue.sh')+hosts,timeout=30)
  except Exception as e:
   st['continuation_error']=str(e);publish(st)
 except BaseException as e:
  st['error']=type(e).__name__+': '+str(e);st['phase']='failed-needs-diagnosis'
  # An unreachable status endpoint must never prevent local compensation.
  try:publish(st)
  except BaseException as report:
   st['status_publication_error']=type(report).__name__;atomic(TX,st)
  if not st.get('promotion_barrier'):
   try:recover_source(st)
   except BaseException as r:
    st['recovery_error']=str(r);st['phase']='recovery-refused'
    try:publish(st)
    except BaseException:atomic(TX,st)
  raise

def abort_runner():
 st=load();unit=st.get('unit','');expected=st.get('runner_pid')
 if not re.fullmatch(r'host-hop-cutover-[0-9TZ]+\.service',unit):raise RuntimeError('no pinned host-hop runner to abort')
 props=dict(l.split('=',1) for l in service(unit).splitlines() if '=' in l)
 if int(props.get('MainPID','0'))!=expected or not props.get('ControlGroup','').endswith('/'+unit):raise RuntimeError('runner identity changed; refusing signal')
 shell('systemctl --user kill --kill-who=main --signal=TERM '+q(unit));print('abort signal sent to verified runner; poll independent status; source recovery is prohibited after promotion barrier')
def main():
 cmd=sys.argv[1] if len(sys.argv)>1 else 'status';args=sys.argv[2:]
 if cmd=='abort':abort_runner();return
 if cmd=='status':print(json.dumps(load(),indent=2));return
 if cmd not in ('preflight','execute','recover-source'):raise SystemExit('unknown command')
 S.mkdir(parents=True,exist_ok=True)
 if cmd=='recover-source' and not args:
  st=load()
  if not (st.get('source') and st.get('target')):raise SystemExit('no recorded transaction hosts; pass FROM TO')
  args=[st['source'],st['target']]
 if len(args)!=2:raise SystemExit('usage: runner.py '+cmd+' FROM TO')
 set_hosts(*args)
 if cmd=='preflight':print(json.dumps(preflight(),indent=2));return
 with (S/'transaction.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if cmd=='execute':execute()
  else:recover_source(load())
if __name__=='__main__':
 def interrupted(sig,frame):raise RuntimeError('runner signal '+str(sig))
 signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
 main()
