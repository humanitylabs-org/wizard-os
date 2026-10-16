"""Optional private reasoning through the installation's existing Agent Service.

No provider fallback, arbitrary tools, credentials or owner data are placed in a
packet. The configured route is preserved. Durable keys fence submission retries;
finished recommendations cannot grant authority. A failed planner leaves work
system-owned and visible. The deterministic prototype can run without this adapter.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AgentPlanner:
    def __init__(self, root, base, model, provider, token=''):
        if not model or not provider:
            raise ValueError('Private reasoning requires the exact configured model and provider')
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.base=base.rstrip('/');self.model=model;self.provider=provider;self.token=token
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())

    def request(self, method, path, body=None, key=None):
        headers={'Accept':'application/json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        if body is not None:headers['Content-Type']='application/json'
        if key:headers['Idempotency-Key']=key
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
        with self.http.open(req,timeout=12) as r:
            return json.load(r)

    def save(self, path, row):
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(row));tmp.chmod(0o600)
        with tmp.open('rb') as f:os.fsync(f.fileno())
        os.replace(tmp,path)

    @staticmethod
    def unbox(value):
        return value['data'] if isinstance(value,dict) and isinstance(value.get('data'),dict) else value

    def recommendation(self, incident, target):
        packet={'incident_id':incident['id'],'generation':incident['generation'],'kind':incident['kind'],
                'state':incident['state'],'verification':incident['verification'],
                'target':{k:target[k] for k in ('name','action','description','grant','effective_preference')}}
        key='supervisor-'+hashlib.sha256(json.dumps(packet,sort_keys=True).encode()).hexdigest()[:32]
        # A single reasoning run per incident generation; later owner rules are
        # always revalidated by the engine, not overridden by a prior model output.
        path=self.root/(incident['id']+'.json')
        row=json.loads(path.read_text()) if path.exists() else None
        if row is None:
            sid='supervisor_private_'+incident['id']
            prompt=('You are the private decision adviser for an isolated Wizard Supervisor prototype. '
                'Reason only from this sanitized packet. No tools, repairs, messages or external actions. '
                'Return ONLY one JSON object with action (the configured action or wait), why (under 500 characters), '
                'generation, and needs_approval (boolean). Existing grants mean technical work is system-owned; '
                'an unnecessary worker request must not create a human gate. Respect a scoped wait or ask-first preference. '
                'Propose the best bounded next step. You cannot enlarge permissions. Packet: '+json.dumps(packet))
            row={'session_id':sid,'key':key,'created_at':time.time(),'state':'new','packet':packet,
                 'payload':{'session_id':sid,'input':prompt,'model':self.model,'provider':self.provider,'require_model_lock':True,
                            'model_options':{'reasoning_effort':'low'},'response_rendering':'markdown'}}
            self.save(path,row)
        if row.get('state')=='complete':return row['recommendation']
        if row.get('state')=='failed':raise ValueError('Private reasoning unavailable; incident remains system-owned')
        try:
            if row['state']=='new':
                sid=row['session_id']
                try: session=self.unbox(self.request('GET','/api/sessions/'+sid))
                except urllib.error.HTTPError as e:
                    if e.code!=404:raise
                    self.request('POST','/api/sessions',{'id':sid,'title':'Supervisor private diagnosis','source':'api_server','model':self.model,'provider':self.provider,'require_model_lock':True})
                self.request('PATCH','/api/sessions/'+sid,{'hidden':True})
                session=self.unbox(self.request('GET','/api/sessions/'+sid))
                if session.get('hidden') is not True and session.get('hidden')!=1:
                    raise ValueError('Private session could not be confirmed hidden')
                row['state']='admitting';self.save(path,row)
            if row['state']=='admitting':
                # Replay with the original payload/key only; never mint a second key.
                admitted=self.request('POST','/v1/runs',row['payload'],row['key'])
                row.update(state='running',run_id=admitted.get('run_id') or admitted.get('id'))
                if not row['run_id']:raise ValueError('No private-run receipt')
                self.save(path,row);return None
            result=self.request('GET','/v1/runs/'+row['run_id'])
            status=result.get('status')
            if status in ('failed','cancelled','interrupted'):
                row.update(state='failed',failure='Private reasoning did not complete');self.save(path,row)
                raise ValueError('Private reasoning did not complete')
            if status!='completed':
                if time.time()-row['created_at']>600:
                    row.update(state='failed',failure='Private reasoning deadline exceeded');self.save(path,row)
                    # Reason-only operation is not replayed or provider-swapped.
                    raise ValueError('Private reasoning deadline exceeded')
                return None
            output=result.get('output')
            if not isinstance(output,str):
                output=json.dumps(output)
            start=output.find('{')
            if start<0:raise ValueError('No structured recommendation')
            value,_=json.JSONDecoder().raw_decode(output[start:])
            if not isinstance(value,dict) or set(value)-{'action','why','generation','needs_approval'}:
                raise ValueError('Invalid bounded recommendation')
            if value.get('generation')!=incident['generation'] or value.get('action') not in (target['action'],'wait'):
                raise ValueError('Recommendation outside current incident')
            if not isinstance(value.get('why'),str) or len(value['why'])>1000 or type(value.get('needs_approval')) is not bool:
                raise ValueError('Invalid recommendation fields')
            row.update(state='complete',recommendation=value,completed_at=time.time(),reported_model=result.get('model'),reported_provider=result.get('provider'))
            self.save(path,row);return value
        except (ValueError,urllib.error.URLError,OSError):
            # Retain the stable admission receipt for recovery. No message is
            # escalated to the owner merely because inference is unavailable.
            raise

    def receipts(self):
        rows=[]
        for p in self.root.glob('*.json'):
            r=json.loads(p.read_text())
            rows.append({k:r.get(k) for k in ('session_id','run_id','state','created_at','completed_at','failure')})
        return rows
