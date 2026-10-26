#!/usr/bin/python3
"""No production mutation: isolated Python fixtures and real child cancellation."""
import contextlib,copy,importlib.util,json,os,pathlib,subprocess,tempfile,time,unittest
from unittest.mock import patch
# Placeholder settings (hosts.env.example) drive every fixture; no real host is contacted.
os.environ.setdefault('HOP_ENV',str(pathlib.Path(__file__).with_name('hosts.env.example')))
spec=importlib.util.spec_from_file_location('hop',pathlib.Path(__file__).with_name('runner.py'));hop=importlib.util.module_from_spec(spec);spec.loader.exec_module(hop)
hop.set_hosts('source-host','target-host')
TMP=os.environ.get('TMPDIR')
class Safety(unittest.TestCase):
 def test_parent_gate(self):
  with patch.dict(os.environ,{},clear=True),patch.object(hop,'preflight') as p:
   with self.assertRaisesRegex(RuntimeError,'parent launch gate'):hop.execute()
   p.assert_not_called()
 def test_cgroup_rejects_current_gateway(self):
  with self.assertRaisesRegex(RuntimeError,'independent'):hop.assert_independent()
 def test_barrier_recovery_never_calls_external(self):
  with patch.object(hop,'remote') as r,patch.object(hop,'run') as cmd:
   with self.assertRaisesRegex(RuntimeError,'REFUSED'):hop.recover_source({'promotion_barrier':True,'source_stopped':True})
   r.assert_not_called();cmd.assert_not_called()
 def test_target_not_cold_refuses_source_restart(self):
  for answer in ('99','0'):
   with self.subTest(answer=answer),patch.object(hop,'remote',side_effect=lambda s:'99' if answer=='99' else ('0' if 'MainPID' in s else 'target-writer')),patch.object(hop,'run') as cmd:
    with self.assertRaisesRegex(RuntimeError,'not cold'):hop.recover_source({'source_stopped':True,'promotion_barrier':False})
    cmd.assert_not_called()
 def test_target_guard_and_service_fences_required_for_recovery(self):
  for guard,unit in [('', 'MainPID=0\nActiveState=inactive'),('guarded','MainPID=17\nActiveState=active')]:
   def remote(s):
    if 'echo guarded' in s:return guard
    if '-p ActiveState' in s:return unit
    return '0' if 'MainPID' in s else ''
   with self.subTest(guard=guard,unit=unit),patch.object(hop,'remote',side_effect=remote),patch.object(hop,'run') as cmd:
    with self.assertRaisesRegex(RuntimeError,'target (not cold|service not fenced)'):hop.recover_source({'source_stopped':True,'promotion_barrier':False,'units':['hermesui.service']})
    cmd.assert_not_called()
 def test_pre_stop_abort_releases_owned_drain_and_schedules(self):
  st={'promotion_barrier':False,'source_stopped':False,'drain_owned':True,'schedulers_attempted':True,'timers':['sample.timer']}
  with patch.object(hop,'shell') as sh,patch.object(hop,'drain') as d,patch.object(hop,'publish'):
   hop.recover_source(st);d.assert_called_once_with(False);sh.assert_called_once_with('systemctl --user start sample.timer');self.assertEqual(st['phase'],'aborted-before-source-stop')
 def test_cold_source_recovery_restores_original_state(self):
  with tempfile.TemporaryDirectory(dir=TMP) as d:
   h=pathlib.Path(d);(h/'.wizard-os').mkdir();(h/'.wizard-os/standby.lock').touch();f=h/'frozen';f.mkdir();(f/'serve.json').write_text('{}');(f/'containers.json').write_text(json.dumps({'ctr':{'restart':{'Name':'on-failure','MaximumRetryCount':3}}}))
   st={'promotion_barrier':False,'source_stopped':True,'frozen':str(f),'source_role_before':'HOP_ROLE=active\n','old_source_name':'source-host','containers':['ctr'],'units':['hermes-gateway.service','hermesui.service'],'timers':['job.timer']}
   with patch.object(hop,'H',h),patch.object(hop,'remote',side_effect=lambda s:'guarded' if 'echo guarded' in s else ('MainPID=0\nActiveState=inactive' if '-p ActiveState' in s else ('0' if 'MainPID' in s else ''))),patch.object(hop,'shell') as sh,patch.object(hop,'run') as cmd,patch.object(hop,'restore_serve'),patch.object(hop,'drain') as drain,patch.object(hop,'pid',return_value=42),patch.object(hop,'jhttp',return_value={'status':'ok'}),patch.object(hop,'publish'):
    hop.recover_source(st)
   self.assertFalse((h/'.wizard-os/standby.lock').exists());self.assertEqual((h/'.wizard-os/host-role').read_text(),'HOP_ROLE=active\n');self.assertEqual(st['phase'],'source-recovered');self.assertFalse(st['source_stopped']);cmd.assert_any_call(['docker','update','--restart=on-failure:3','ctr']);cmd.assert_any_call(['docker','start','ctr'],timeout=180);drain.assert_called_once_with(False)
 def test_forced_command_fence_scoped_restore_and_foreign_refusal(self):
  cmd='/usr/bin/python3 -I /srv/local-service/gateway.py'
  with tempfile.TemporaryDirectory(dir=TMP) as d:
   h=pathlib.Path(d);(h/'.ssh').mkdir();p=h/'.ssh/authorized_keys';old='restrict,command="'+cmd+'",from="'+hop.tsip('target-host')+'" ssh-ed25519 PUBLIC fixture\n';p.write_text('unrelated-key\n'+old);st={}
   with patch.object(hop,'H',h),patch.object(hop,'publish'),patch.dict(hop.CFG,{'HOP_FENCE_FORCED_COMMAND':cmd}):
    hop.forced_command_fence(st,True);self.assertIn('forced-command-fence.sh',p.read_text());self.assertIn('unrelated-key',p.read_text());hop.forced_command_fence(st,False);self.assertEqual(p.read_text(),'unrelated-key\n'+old)
    p.write_text('foreign-provider\n')
    with self.assertRaisesRegex(RuntimeError,'preimage'):hop.forced_command_fence({},True)
 def test_forced_command_fence_unconfigured_is_noop(self):
  with tempfile.TemporaryDirectory(dir=TMP) as d,patch.object(hop,'H',pathlib.Path(d)),patch.dict(hop.CFG,{'HOP_FENCE_FORCED_COMMAND':''}):
   st={};hop.forced_command_fence(st,True);hop.forced_command_fence(st,False);self.assertEqual(st,{})
 def test_role_names_and_hosts_come_from_settings(self):
  self.assertEqual(hop.main_name(),'wizard-main');self.assertEqual(hop.standby_name('source-host'),'wizard-backup-1');self.assertEqual(hop.fqdn(hop.main_name()),'wizard-main.example-tailnet.ts.net')
  for bad in (('source-host','source-host'),('source-host','unknown-host')):
   with self.subTest(bad=bad),self.assertRaises(SystemExit):hop.set_hosts(*bad)
  hop.set_hosts('source-host','target-host')
 def test_abort_pins_exact_unit_pid(self):
  st={'unit':'host-hop-cutover-20261025T100000Z.service','runner_pid':123}
  with patch.object(hop,'load',return_value=st),patch.object(hop,'service',return_value='MainPID=124\nControlGroup=/app.slice/'+st['unit']),patch.object(hop,'shell') as sh:
   with self.assertRaisesRegex(RuntimeError,'identity changed'):hop.abort_runner()
   sh.assert_not_called()
  with patch.object(hop,'load',return_value=st),patch.object(hop,'service',return_value='MainPID=123\nControlGroup=/app.slice/'+st['unit']),patch.object(hop,'shell') as sh:
   hop.abort_runner();sh.assert_called_once_with('systemctl --user kill --kill-who=main --signal=TERM '+st['unit'])
 def test_failure_diagnostics_private_and_not_in_exception(self):
  with tempfile.TemporaryDirectory(dir=TMP) as d,patch.object(hop,'S',pathlib.Path(d)):
   with self.assertRaises(RuntimeError) as err:hop.run(['bash','-c','printf fixture-private-stderr >&2; exit 7'])
   self.assertNotIn('fixture-private-stderr',str(err.exception))
   p=next((pathlib.Path(d)/'private-failures').glob('*.json'));self.assertEqual(p.stat().st_mode&0o777,0o600);self.assertEqual(json.loads(p.read_text())['stderr'],'fixture-private-stderr')
 def test_optimized_python_refuses_before_any_action(self):
  p=subprocess.run(['/usr/bin/python3','-O',str(pathlib.Path(__file__).with_name('runner.py')),'status'],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('refusing optimized Python',p.stderr)
 def test_idle_deadline_is_bounded_without_stop(self):
  with patch.object(hop,'work') as w,patch.object(hop,'shell') as sh:
   with self.assertRaisesRegex(RuntimeError,'idle deadline'):hop.wait_idle({},deadline=0)
   sh.assert_not_called();w.assert_not_called()
 def test_exact_runner_and_infrastructure_excluded(self):
  for u in ('host-hop-cutover-123.service','host-hop-completion-123.service','docker.service','dbus.service','example-local-scan.service','example-local-relay.service','was-candidate.service','app-qa.service'):self.assertFalse(hop.allowed(u),u)
  self.assertTrue(hop.allowed('hermes-gateway.service'))
 def test_work_counters_all_gate(self):
  w={k:0 for k in ('ui_runs','ui_streams','gateway_agents','api_runs','leases','cron_locks')};self.assertTrue(hop.idle(w))
  for k in w:
   x=dict(w);x[k]=1;self.assertFalse(hop.idle(x),k)
 def test_subprocess_timeout_has_no_late_writer(self):
  with tempfile.TemporaryDirectory(dir=TMP) as d:
   p=pathlib.Path(d)/'late'
   with self.assertRaises(subprocess.TimeoutExpired):hop.run(['bash','-c',f'(sleep 1; printf late > {hop.q(p)}) & wait'],timeout=.1)
   time.sleep(1.2);self.assertFalse(p.exists())
 def test_subprocess_baseexception_has_no_late_writer(self):
  # A real SIGTERM during communicate must cancel the entire child session before propagating.
  import signal
  with tempfile.TemporaryDirectory(dir=TMP) as d:
   p=pathlib.Path(d)/'late'
   old=signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(KeyboardInterrupt()))
   try:
    signal.setitimer(signal.ITIMER_REAL,.1)
    with self.assertRaises(KeyboardInterrupt):hop.run(['bash','-c',f'(sleep 1; printf late > {hop.q(p)}) & wait'],timeout=5)
   finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
   time.sleep(1.2);self.assertFalse(p.exists())
 def scenario(self,fault,status_failure=False):
  with tempfile.TemporaryDirectory(dir=TMP) as d,contextlib.ExitStack() as stack:
   h=pathlib.Path(d);(h/'.wizard-os').mkdir();f=h/'frozen';f.mkdir();(f/'serve.json').write_text('{}');(f/'containers.json').write_text(json.dumps({'ctr':{'id':'immutable','restart':{'Name':'unless-stopped','MaximumRetryCount':0}}}))
   phases=[];recoveries=[];calls=[]
   def publish(st):
    phases.append(copy.deepcopy(st))
    if status_failure and st['phase']=='failed-needs-diagnosis':raise RuntimeError('status endpoint unreachable')
   stack.enter_context(patch.object(hop,'TX',h/'transaction.json'))
   def freeze(st):st.update(frozen=str(f),units=['hermes-gateway.service','hermesui.service'],timers=['job.timer'],containers=['ctr'],enabled=[],old_source_name='source-host');return f
   def cmd(s,**kw):
    calls.append(s)
    if fault and fault in s:raise RuntimeError('injected '+fault)
    if 'HOP_CONTAINER_SKIP_REGEX' in s:return '(^|[-_])(qa|test|apk|dev)([-_]|$)'
    if "docker ps --format" in s:return 'ctr'
    if '--type=timer,path' in s:return 'job.timer loaded active waiting'
    if 'list-units' in s:return 'hermes-gateway.service loaded active running'
    if 'MainPID' in s:return '0'
    if 'tables -S HOP-TEST' in s:return '1'
    if 'check-databases.py' in s:return json.dumps({'state.db':{'counts':{'sessions':1,'messages':1}}})
    if 'tailscale status' in s:return json.dumps({'Self':{'DNSName':'wizard-main.example-tailnet.ts.net.'}})
    return ''
   def run(a,**kw):
    if any('check-databases.py' in x for x in a):return json.dumps({'state.db':{'counts':{'sessions':1,'messages':1}}})
    calls.append(' '.join(a))
    if a[:3]==['docker','container','inspect']:return json.dumps([{'Name':'/ctr','Id':'immutable'}])
    if a[:2]==['docker','inspect']:raise AssertionError('untyped docker inspect (lesson 5)')
    return ''
   for name,val in [('H',h),('S',h/'state'),('preflight',lambda:None),('assert_independent',lambda:None),('load',lambda:{}),('publish',publish),('remote',cmd),('shell',cmd),('run',run),('freeze',freeze),('estimate_after_warm',lambda st:None),('forced_command_fence',lambda *a:None),('drain',lambda x:None),('wait_idle',lambda s:None),('idle',lambda w:True),('work',lambda:{}),('jhttp',lambda url:{'active_runs':0,'active_streams':0}),('stopped',lambda u:True),('pid',lambda u:0),('assert_source_cold',lambda s:None),('restore_serve',lambda *a:None),('recover_source',lambda s:recoveries.append(copy.deepcopy(s)))]:stack.enter_context(patch.object(hop,name,val))
   stack.enter_context(patch.dict(os.environ,{'HOP_PARENT_LAUNCH':'OWNER_RECOVERY_SENT'}))
   if fault:
    with self.assertRaisesRegex(RuntimeError,'injected'):hop.execute()
   else:hop.execute()
   return phases,recoveries,calls
 def test_pre_promotion_failure_recovery_branches(self):
  for fault in ('sync.sh source-host target-host','--final --only pg','promote.sh prepare'):
   with self.subTest(fault=fault):
    phases,recovery,calls=self.scenario(fault);self.assertEqual(len(recovery),1);self.assertFalse(recovery[0]['promotion_barrier'])
 def test_post_promotion_failure_never_recovers_source(self):
  for fault in ('promote.sh activate','promote.sh verify'):
   with self.subTest(fault=fault):
    phases,recovery,calls=self.scenario(fault);self.assertEqual(recovery,[]);self.assertTrue(phases[-1]['promotion_barrier']);self.assertEqual(phases[-1]['phase'],'failed-needs-diagnosis')
 def test_status_outage_does_not_skip_local_recovery(self):
  phases,recovery,calls=self.scenario('--final --only pg',status_failure=True)
  self.assertEqual(len(recovery),1);self.assertFalse(recovery[0]['promotion_barrier']);self.assertIn('status_publication_error',recovery[0])
 def test_success_has_barrier_before_activation_and_completion(self):
  phases,recovery,calls=self.scenario(None);self.assertEqual(recovery,[]);self.assertEqual(phases[-1]['phase'],'complete');self.assertTrue(phases[-1]['promotion_barrier']);self.assertIn('target-may-write',[p['phase'] for p in phases]);self.assertTrue(any('continue.sh' in c for c in calls))
  self.assertTrue(any('tailscale set --hostname=wizard-backup-1' in c for c in calls));self.assertTrue(any('tailscale set --hostname=wizard-main' in c for c in calls))
  self.assertTrue(any(c.startswith('docker container inspect') for c in calls))
class DnsLag(unittest.TestCase):
 def test_wait_dns_tolerates_propagation_lag(self):
  answers=iter(['target-host.example-tailnet.ts.net.','target-host.example-tailnet.ts.net.','wizard-main.example-tailnet.ts.net.'])
  with patch.object(hop,'remote',side_effect=lambda s:json.dumps({'Self':{'DNSName':next(answers)}})),patch.object(hop.time,'sleep'):
   hop.wait_dns('wizard-main.example-tailnet.ts.net')
 def test_wait_dns_fails_with_observed_name(self):
  with patch.object(hop,'remote',return_value=json.dumps({'Self':{'DNSName':'wizard-main-1.example-tailnet.ts.net.'}})),patch.object(hop.time,'sleep'):
   with self.assertRaisesRegex(RuntimeError,'wizard-main-1'):hop.wait_dns('wizard-main.example-tailnet.ts.net',limit=0)
 def test_wait_health_retries_refused_then_ok(self):
  seq=iter([OSError('refused'),{'status':'ok'}])
  def j(u):
   v=next(seq)
   if isinstance(v,Exception):raise v
   return v
  with patch.object(hop,'jhttp',side_effect=j),patch.object(hop,'pid',return_value=5),patch.object(hop.time,'sleep'):
   self.assertTrue(hop.wait_health())
if __name__=='__main__':unittest.main(verbosity=2)
