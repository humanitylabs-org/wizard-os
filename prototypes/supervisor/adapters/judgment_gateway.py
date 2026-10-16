"""Prototype Agent Service adapter for native tool-free Hermes judgment.

A narrow standalone extension, not a Hermes patch or provider proxy. Configure the
existing Hermes interpreter/source and exact authorized model/provider. It never
accepts tool configuration, credentials, callbacks or file paths from requests.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

ROOT=Path(os.environ['JUDGMENT_DATA']);ROOT.mkdir(parents=True,exist_ok=True)
TOKEN=os.environ['JUDGMENT_TOKEN']
MODEL=os.environ['JUDGMENT_MODEL'];PROVIDER=os.environ['JUDGMENT_PROVIDER']
PYTHON=os.environ.get('JUDGMENT_PYTHON',sys.executable)
WORKER=Path(__file__).with_name('sdk_worker.py')
if len(TOKEN)<24:raise SystemExit('Scoped judgment credential required')
LOCK=threading.RLock();POOL=ThreadPoolExecutor(max_workers=1)
DB=sqlite3.connect(ROOT/'admissions.sqlite3',check_same_thread=False)
DB.execute('create table if not exists jobs (id text primary key, digest text not null, state text not null, body text not null, result text, created real not null)')
# A crash after durable reservation is uncertain. Never recreate its model run.
DB.execute("update jobs set state='failed',result=? where state='running'",(json.dumps({'error':'Judgment was interrupted; no automatic replay'}),));DB.commit()


def execute(ident,preflight=False):
    with LOCK:
        row=DB.execute('select body,state from jobs where id=?',(ident,)).fetchone()
        if not row or row[1]!='queued':return
        DB.execute("update jobs set state='running' where id=?",(ident,));DB.commit()
        payload=json.loads(row[0])
    work=ROOT/ident;work.mkdir(exist_ok=True);packet=work/'packet.json';result=work/'result.json'
    payload['preflight']=preflight;packet.write_text(json.dumps(payload));packet.chmod(0o600)
    try:
        with (work/'runtime.log').open('w') as log:
            proc=subprocess.run([PYTHON,str(WORKER),str(packet),str(result)],stdout=log,stderr=subprocess.STDOUT,timeout=180)
        if proc.returncode!=0 or not result.exists():raise RuntimeError('Tool-free runtime failed; inspect private adapter log')
        value=json.loads(result.read_text())
        if value.get('execution_policy')!={'tools':[],'tool_count':0,'tool_execution':'none','enforced':True}:raise RuntimeError('Tool-free proof missing')
        if value.get('model')!=MODEL or value.get('provider')!=PROVIDER:raise RuntimeError('Configured route not preserved')
        state='completed'
    except Exception:
        value={'error':'Private judgment failed; the incident remains system-owned'};state='failed'
    with LOCK:
        DB.execute('update jobs set state=?,result=? where id=?',(state,json.dumps(value),ident));DB.commit()


def preflight():
    ident='preflight-'+secrets.token_hex(6)
    body={'model':MODEL,'provider':PROVIDER,'session_id':ident,'input':'No inference in preflight'}
    with LOCK:
        DB.execute('insert into jobs values (?,?,?,?,?,?)',(ident,'preflight','queued',json.dumps(body),None,time.time()));DB.commit()
    execute(ident,True)
    with LOCK:return DB.execute('select state from jobs where id=?',(ident,)).fetchone()[0]=='completed'

READY=preflight()
if not READY:raise SystemExit('Native tool-free execution preflight failed')
with LOCK:
    for (ident,) in DB.execute("select id from jobs where state='queued'").fetchall():POOL.submit(execute,ident)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):pass
    def reply(self,status,value):
        b=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def auth(self):return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN)
    def do_GET(self):
        if not self.auth():return self.reply(403,{'error':'Scoped judgment credential required'})
        if self.path=='/v1/capabilities':return self.reply(200,{'tool_execution':'none','enforced':True,'model':MODEL,'provider':PROVIDER,'durable_idempotency':True,'private_session_store':True})
        ident=self.path.removeprefix('/v1/runs/')
        if self.path.startswith('/v1/runs/') and re.fullmatch(r'[a-z0-9-]{8,90}',ident):
            with LOCK:row=DB.execute('select state,result from jobs where id=?',(ident,)).fetchone()
            if row:return self.reply(200,{'run_id':ident,'status':row[0],**(json.loads(row[1]) if row[1] else {})})
        return self.reply(404,{'error':'Not found'})
    def do_POST(self):
        if not self.auth():return self.reply(403,{'error':'Scoped judgment credential required'})
        if self.path!='/v1/runs':return self.reply(404,{'error':'Not found'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=24000:raise ValueError('Bounded JSON required')
            body=json.loads(self.rfile.read(size));key=self.headers.get('Idempotency-Key','')
            if not re.fullmatch(r'supervisor-[a-f0-9]{32}',key):raise ValueError('Stable admission key required')
            if set(body)-{'session_id','input','model','provider','require_model_lock','model_options','response_rendering'}:raise ValueError('Unsupported execution option')
            if body.get('model')!=MODEL or body.get('provider')!=PROVIDER or body.get('require_model_lock') is not True:raise ValueError('Exact configured route required')
            if not isinstance(body.get('input'),str) or len(body['input'])>16000:raise ValueError('Bounded input required')
            if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}',body.get('session_id','')):raise ValueError('Invalid private receipt identity')
            frozen={k:body[k] for k in ('session_id','input','model','provider')}
            digest=hashlib.sha256(json.dumps(frozen,sort_keys=True).encode()).hexdigest()
            with LOCK:
                old=DB.execute('select digest,state from jobs where id=?',(key,)).fetchone()
                if old:
                    if old[0]!=digest:return self.reply(409,{'error':'Admission identity conflicts with frozen packet'})
                    return self.reply(200,{'run_id':key,'status':old[1]})
                count=DB.execute("select count(*) from jobs where state in ('running','queued')").fetchone()[0]
                if count>=8:return self.reply(429,{'error':'Private judgment capacity is busy'})
                DB.execute('insert into jobs values (?,?,?,?,?,?)',(key,digest,'queued',json.dumps(frozen),None,time.time()));DB.commit()
                POOL.submit(execute,key)
            return self.reply(201,{'run_id':key,'status':'queued'})
        except (ValueError,TypeError,KeyError):return self.reply(400,{'error':'Invalid bounded judgment request'})

if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('JUDGMENT_PORT','8947'))),Handler).serve_forever()
