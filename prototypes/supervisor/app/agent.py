"""Durable client for the tool-free Agent Service prototype adapter.
Ordinary full-tool /v1/runs is rejected; exact model/provider and an enforced
empty-toolset capability are required. No provider fallback is permitted.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

class AgentPlanner:
    def __init__(self,root,base,model,provider,token=''):
        if not model or not provider or len(token)<24:raise ValueError('Tool-free judgment requires the configured route and scoped credential')
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.base=base.rstrip('/');self.model=model;self.provider=provider;self.token=token
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def request(self,method,path,body=None,key=None):
        headers={'Accept':'application/json','Authorization':'Bearer '+self.token}
        if body is not None:headers['Content-Type']='application/json'
        if key:headers['Idempotency-Key']=key
        req=urllib.request.Request(self.base+path,json.dumps(body).encode() if body is not None else None,headers,method=method)
        with self.http.open(req,timeout=12) as r:return json.load(r)

    def save(self,path,row):
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(row));tmp.chmod(0o600)
        with tmp.open('rb') as f:os.fsync(f.fileno())
        os.replace(tmp,path)
        fd=os.open(str(path.parent),os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def recommendation(self,incident,target):
        identity={'incident_id':incident['id'],'generation':incident['generation'],'policy_digest':target['policy_digest'],'model':self.model,'provider':self.provider}
        # Exclude mutable probe timestamps. A lost receipt conflicts rather than
        # silently creating another admission. Policy changes get a new identity.
        key='supervisor-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:32]
        path=self.root/(key+'.json')
        row=json.loads(path.read_text()) if path.exists() else None
        if row is None:
            packet={**identity,'kind':incident['kind'],'state':incident['state'],'verification':incident['verification'],
                'target':{k:target[k] for k in ('name','action','description','grant','effective_preference')}}
            prompt=('Choose the next step for this isolated maintenance incident. Return ONLY JSON with action '
                '(the configured action or wait), why (under 500 characters), generation, needs_approval (boolean). '
                'Existing grants mean technical work is system-owned. Respect explicit ask-first/wait preferences. '
                'You can recommend but cannot grant permission. Packet: '+json.dumps(packet))
            row={'session_id':key.replace('-','_'),'key':key,'created_at':time.time(),'state':'new','packet':packet,
                'payload':{'session_id':key.replace('-','_'),'input':prompt,'model':self.model,'provider':self.provider,'require_model_lock':True}}
            self.save(path,row)
        if row['state']=='complete':return row['recommendation']
        if row['state']=='failed':raise ValueError(row.get('failure','Private judgment failed'))
        if time.time()-row['created_at']>600:
            row.update(state='failed',failure='Private judgment deadline exceeded; incident remains system-owned');self.save(path,row);raise ValueError(row['failure'])
        if row['state']=='new':
            cap=self.request('GET','/v1/capabilities')
            if cap.get('tool_execution')!='none' or cap.get('enforced') is not True or cap.get('model')!=self.model or cap.get('provider')!=self.provider:
                raise ValueError('Configured route does not prove tool-free execution')
            row['capability']={k:cap[k] for k in ('tool_execution','enforced','model','provider')}
            row['state']='admitting';self.save(path,row)
        if row['state']=='admitting':
            admitted=self.request('POST','/v1/runs',row['payload'],row['key'])
            if not admitted.get('run_id'):raise ValueError('No durable judgment receipt')
            row.update(state='running',run_id=admitted['run_id']);self.save(path,row);return None
        result=self.request('GET','/v1/runs/'+row['run_id'])
        if result.get('status') in ('failed','cancelled','interrupted'):
            row.update(state='failed',failure='Private judgment did not complete; incident remains system-owned');self.save(path,row);raise ValueError(row['failure'])
        if result.get('status')!='completed':return None
        try:
            if result.get('execution_policy')!={'tools':[],'tool_count':0,'tool_execution':'none','enforced':True}:raise ValueError('No enforced tool-free proof')
            if result.get('model')!=self.model or result.get('provider')!=self.provider:raise ValueError('Configured route changed')
            output=result.get('output')
            if not isinstance(output,str):raise ValueError('No structured recommendation')
            start=output.find('{')
            if start<0:raise ValueError('No structured recommendation')
            value,_=json.JSONDecoder().raw_decode(output[start:])
            if not isinstance(value,dict) or set(value)-{'action','why','generation','needs_approval'}:raise ValueError('Invalid recommendation fields')
            if value.get('generation')!=incident['generation'] or value.get('action') not in (target['action'],'wait'):raise ValueError('Outside current incident')
            if not isinstance(value.get('why'),str) or len(value['why'])>1000 or type(value.get('needs_approval')) is not bool:raise ValueError('Invalid values')
        except (ValueError,TypeError,KeyError):
            row.update(state='failed',failure='Private judgment returned invalid output; incident remains system-owned');self.save(path,row);raise ValueError(row['failure'])
        row.update(state='complete',recommendation=value,completed_at=time.time(),execution_policy=result['execution_policy'],private_session_store=True)
        self.save(path,row);return value

    def receipts(self):
        rows=[]
        for p in self.root.glob('*.json'):
            r=json.loads(p.read_text());rows.append({k:r.get(k) for k in ('session_id','run_id','state','created_at','completed_at','failure','execution_policy','private_session_store')})
        return rows
