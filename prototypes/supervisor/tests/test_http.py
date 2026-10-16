"""Real HTTP integration checks. All processes/state are disposable."""
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.token=secrets.token_urlsafe(32);self.worker_token=secrets.token_urlsafe(32);self.sp=port();self.cp=port()
        self.base='http://127.0.0.1:'+str(self.sp);self.canary='http://127.0.0.1:'+str(self.cp)
        self.processes=[];self.logs=[]
        self.config={'targets':{}}
        for ident,kind,path,action in [('service','service','function','repair'),('job','job','job','rerun')]:
            self.config['targets'][ident]={'name':'Test '+ident,'kind':kind,'probe_url':self.canary+'/'+path,'action_url':self.canary+'/'+action,'action_token':self.token,'expected':{'ok':True,'answer':42},'grant':ident=='service','action':action,'description':'Only the disposable '+ident}
        self.config_file=self.root/'config.json';self.config_file.write_text(json.dumps(self.config))
        self.start('canary.py',self.cp,self.root/'canary');self.server=self.start('server.py',self.sp,self.root/'server')
        self.cookies=http.cookiejar.CookieJar();self.browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def start(self,name,p,data):
        env=dict(os.environ,DATA_DIR=str(data),HOST='127.0.0.1',PORT=str(p),SUPERVISOR_TOKEN=self.token,SUPERVISOR_WORKER_TOKEN=self.worker_token,SUPERVISOR_CONFIG=str(self.config_file),SUPERVISOR_AUTOTICK='0',SUPERVISOR_ORIGIN=self.base,SUPERVISOR_COOKIE_PATH='/')
        env.pop('WIZARD_AGENT_URL',None)
        log=(self.root/(name+str(len(self.logs))+'.log')).open('w');self.logs.append(log)
        proc=subprocess.Popen([sys.executable,str(ROOT/'app'/name)],env=env,stdout=log,stderr=log);self.processes.append(proc)
        for _ in range(100):
            try:
                urllib.request.urlopen('http://127.0.0.1:'+str(p)+'/healthz',timeout=.2).close();return proc
            except OSError:
                if proc.poll() is not None:raise AssertionError('Process exited: '+(self.root/log.name).read_text())
                time.sleep(.03)
        raise AssertionError('HTTP readiness deadline exceeded')

    def tearDown(self):
        for p in self.processes:
            if p.poll() is None:p.terminate()
        for p in self.processes:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for f in self.logs:f.close()
        self.tmp.cleanup()

    def req(self,path,body=None,operator=True,browser=False,csrf=None,origin=None,base=None,worker=False):
        headers={}
        if operator:headers['Authorization']='Bearer '+self.token
        if worker:headers['Authorization']='Bearer '+self.worker_token
        if body is not None:headers['Content-Type']='application/json'
        if csrf:headers['X-Supervisor-CSRF']=csrf
        if origin:headers['Origin']=origin
        req=urllib.request.Request((base or self.base)+path,json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with (self.browser.open(req,timeout=10) if browser else urllib.request.urlopen(req,timeout=10)) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)

    def snapshot(self):return self.req('/api/status')[1]
    def bootstrap(self):
        ticket=self.req('/api/ticket',{})[1]['ticket']
        status,result=self.req('/api/bootstrap',{'ticket':ticket},False,True,origin=self.base)
        self.assertEqual(status,200);return result['csrf'],ticket

    def test_real_service_repair_and_job_approval_with_restart(self):
        self.req('/fault',{'target':'service'},base=self.canary)
        self.assertEqual(self.req('/api/tick',{})[0],200)
        s=self.snapshot();service=next(i for i in s['incidents'] if i['target_id']=='service');job=next(i for i in s['incidents'] if i['target_id']=='job')
        self.assertEqual(service['status'],'resolved');self.assertFalse(service['owner_required'])
        self.assertEqual(job['status'],'awaiting_approval')
        self.assertEqual(self.req('/api/approve',{'incident_id':job['id'],'digest':job['approval_digest']})[0],200)
        self.assertEqual(self.req('/api/approve',{'incident_id':job['id'],'digest':job['approval_digest']})[0],400)
        self.assertEqual(self.req('/job',base=self.canary)[1]['status'],'complete')
        self.server.terminate();self.server.wait();self.server=self.start('server.py',self.sp,self.root/'server')
        self.assertEqual({i['status'] for i in self.snapshot()['incidents']},{'resolved'})
        self.assertNotIn(self.token,json.dumps(self.snapshot()))

    def test_browser_ticket_csrf_and_scoped_learning(self):
        self.req('/fault',{'target':'service'},base=self.canary);self.req('/api/tick',{})
        inc=next(i for i in self.snapshot()['incidents'] if i['target_id']=='service')
        payload={'incident_id':inc['id'],'text':'Please make this gentler next time'}
        self.assertEqual(self.req('/api/feedback',payload,False)[0],403)
        csrf,ticket=self.bootstrap()
        self.assertEqual(self.req('/api/bootstrap',{'ticket':ticket},False,True,origin=self.base)[0],403)
        self.assertEqual(self.req('/api/feedback',payload,False,True,csrf,origin='https://attacker.invalid')[0],403)
        result=self.req('/api/feedback',payload,False,True,csrf,origin=self.base)
        self.assertEqual(result[0],200);self.assertFalse(result[1]['result']['enabled'])
        r=self.req('/api/preference',{'incident_id':inc['id'],'text':'ask first for this target'},False,True,csrf,origin=self.base)
        self.assertEqual(r[0],200);self.assertTrue(r[1]['result']['enabled'])
        self.req('/fault',{'target':'service'},base=self.canary);self.req('/api/tick',{})
        latest=[i for i in self.snapshot()['incidents'] if i['target_id']=='service'][-1]
        self.assertEqual(latest['status'],'awaiting_approval')
        self.assertEqual(self.req('/api/rule',{'rule_id':r[1]['result']['id'],'enabled':False},False,True,csrf,origin=self.base)[0],200)
        self.req('/api/tick',{});self.assertEqual([i for i in self.snapshot()['incidents'] if i['target_id']=='service'][-1]['status'],'resolved')
        self.assertEqual([t for t in self.snapshot()['targets'] if t['id']=='job'][0]['effective_preference'],'authorized')

    def test_worker_is_denied_every_owner_route(self):
        for path,body in [('/api/ticket',{}),('/api/approve',{'incident_id':'x','digest':'x'}),('/api/preference',{'incident_id':'x','text':'handle authorized repairs'}),('/api/rule',{'rule_id':'x','enabled':True}),('/api/tick',{}),('/api/feedback',{'incident_id':'x','text':'x'})]:
            with self.subTest(path=path):
                self.assertEqual(self.req(path,body,operator=False,worker=True)[0],403)
        self.assertEqual(self.req('/mcp',{'jsonrpc':'2.0','id':1,'method':'tools/list'},operator=False,worker=True)[0],200)

    def test_mcp_only_exposes_bounded_worker_tools(self):
        body={'jsonrpc':'2.0','id':1,'method':'tools/list'}
        self.assertEqual(self.req('/mcp',body,False)[0],403)
        code,result=self.req('/mcp',body);self.assertEqual(code,200)
        self.assertEqual({t['name'] for t in result['result']['tools']},{'supervisor_status','supervisor_decide','supervisor_feedback'})

if __name__=='__main__':unittest.main()
