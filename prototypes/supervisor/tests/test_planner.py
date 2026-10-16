"""Regression fixtures for reviewed planner/control-plane boundaries."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from agent import AgentPlanner

class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.planner=AgentPlanner(self.root,'http://127.0.0.1:1','model','provider','x'*32)
        self.inc={'id':'abc123','generation':1,'kind':'service','state':'detected','verification':{'status':'failed','checked_at':1}}
        self.target={'name':'Test','action':'repair','description':'Test only','grant':True,'effective_preference':'authorized','policy_digest':'first'}
        self.cap={'tool_execution':'none','enforced':True,'model':'model','provider':'provider'}
        self.proof={'tools':[],'tool_count':0,'tool_execution':'none','enforced':True}
    def tearDown(self):self.tmp.cleanup()
    def test_full_tool_route_fails_closed_without_submission(self):
        with patch.object(self.planner,'request',return_value={'features':{'run_submission':True}}) as request:
            with self.assertRaises(ValueError):self.planner.recommendation(self.inc,self.target)
            self.assertEqual(request.call_count,1)
    def test_invalid_completed_output_is_terminal(self):
        replies=[self.cap,{'run_id':'run'}, {'status':'completed','model':'model','provider':'provider','execution_policy':self.proof,'output':'invalid'}]
        with patch.object(self.planner,'request',side_effect=replies) as request:
            self.assertIsNone(self.planner.recommendation(self.inc,self.target))
            with self.assertRaises(ValueError):self.planner.recommendation(self.inc,self.target)
            with self.assertRaises(ValueError):self.planner.recommendation(self.inc,self.target)
            self.assertEqual(request.call_count,3)
        self.assertEqual(self.planner.receipts()[0]['state'],'failed')
    def test_policy_changes_admission_but_probe_time_does_not(self):
        calls=[]
        def reply(method,path,body=None,key=None):
            calls.append((method,path,key))
            return self.cap if path.endswith('capabilities') else {'run_id':'run','status':'running'}
        with patch.object(self.planner,'request',side_effect=reply):
            self.planner.recommendation(self.inc,self.target)
            self.inc['verification']['checked_at']=20;self.planner.recommendation(self.inc,self.target)
            self.assertEqual(len([c for c in calls if c[0]=='POST']),1)
            self.target['policy_digest']='second';self.planner.recommendation(self.inc,self.target)
        keys=[c[2] for c in calls if c[0]=='POST'];self.assertEqual(len(set(keys)),2)
    def test_receipt_fsyncs_file_and_directory(self):
        with patch('os.fsync',wraps=os.fsync) as synced:
            self.planner.save(self.root/'proof.json',{'state':'new'})
            self.assertEqual(synced.call_count,2)
    def test_completed_receipt_requires_exact_route_and_zero_tools(self):
        output=json.dumps({'action':'repair','generation':1,'why':'Within grant','needs_approval':False})
        replies=[self.cap,{'run_id':'run'},{'status':'completed','model':'other','provider':'provider','execution_policy':self.proof,'output':output}]
        with patch.object(self.planner,'request',side_effect=replies):
            self.planner.recommendation(self.inc,self.target)
            with self.assertRaises(ValueError):self.planner.recommendation(self.inc,self.target)
    def test_one_planner_failure_does_not_starve_other_targets(self):
        config=self.root/'config.json';config.write_text(json.dumps({'targets':{}}))
        env={'DATA_DIR':str(self.root/'server'),'SUPERVISOR_TOKEN':'o'*32,'SUPERVISOR_CONFIG':str(config),'WIZARD_AGENT_URL':''}
        with patch.dict(os.environ,env):
            spec=importlib.util.spec_from_file_location('isolated_server',Path(__file__).resolve().parents[1]/'app/server.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        class Engine:
            observed=[];executed=[]
            def snapshot(self):return {'targets':[{'id':'a'},{'id':'b'}]}
            def observe(self,key):
                self.observed.append(key);return {'id':key,'state':'detected','verification':{'status':'failed'}}
            def decide(self,*args):pass
            def execute(self,key):self.executed.append(key);return {'id':key}
        class Planner:
            def recommendation(self,inc,target):
                if target['id']=='a':raise ValueError('diagnosis failed')
                return {'action':'repair'}
        engine=Engine();module.ENGINE=engine;module.PLANNER=Planner();module.cycle()
        self.assertEqual(engine.observed,['a','b']);self.assertEqual(engine.executed,['b'])
        self.assertIn('a',module.LAST_TICK['targets']);self.assertIsNotNone(module.LAST_TICK['error'])

if __name__=='__main__':unittest.main()
