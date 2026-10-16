"""Disposable prototype target. No production services or owner data are touched.

/function is an actual small service operation; /job reads a durable execution
receipt. Authenticated fault injection is confined to these synthetic targets.
Action idempotency keys are persisted so retries cannot execute a job twice.
"""
import hmac
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(os.environ.get('DATA_DIR', '/data'))
ROOT.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ.get('SUPERVISOR_TOKEN', '')
if len(TOKEN) < 24:
    raise SystemExit('A prototype operator token is required')
LOCK = threading.Lock()
DB = sqlite3.connect(ROOT / 'canary.sqlite3', check_same_thread=False)
DB.execute('create table if not exists state (key text primary key, value text not null)')
DB.execute('create table if not exists actions (key text primary key, path text not null, result text not null)')
DB.execute("insert or ignore into state values ('service','healthy')")
DB.execute("insert or ignore into state values ('job','pending')")
DB.commit()

def state(key):
    return DB.execute('select value from state where key=?', (key,)).fetchone()[0]

def put(key, value):
    DB.execute('insert or replace into state values (?,?)', (key, value))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send(self, status, obj):
        b=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)

    def do_GET(self):
        with LOCK:
            if self.path=='/function':
                good=state('service')=='healthy'
                return self.send(200 if good else 503, {'ok':good,'answer':sum(range(7))*2 if good else None,'kind':'service'})
            if self.path=='/job':
                value=state('job')
                if value in ('pending','failed'):
                    return self.send(503, {'ok':False,'status':value,'kind':'job'})
                return self.send(200,json.loads(value))
            if self.path=='/healthz':
                return self.send(200,{'ok':True,'component':'disposable-canary'})
            return self.send(404,{'error':'not found'})

    def do_POST(self):
        if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+TOKEN):
            return self.send(403,{'error':'prototype operator required'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n<0 or n>8192: raise ValueError('body size')
            doc=json.loads(self.rfile.read(n)); key=str(doc.get('idempotency_key') or self.headers.get('Idempotency-Key') or '')
            with LOCK:
                if self.path=='/fault':
                    target=doc.get('target')
                    if target not in ('service','job'):raise ValueError('unknown target')
                    put(target,'failed');DB.commit();return self.send(200,{'injected':target})
                if self.path not in ('/repair','/rerun'):return self.send(404,{'error':'not found'})
                if not key or len(key)>200:raise ValueError('idempotency key required')
                prev=DB.execute('select path,result from actions where key=?',(key,)).fetchone()
                if prev:
                    if prev[0]!=self.path:return self.send(409,{'error':'idempotency key conflict'})
                    return self.send(200,json.loads(prev[1]))
                if self.path=='/repair':
                    put('service','healthy');result={'ok':True,'action':'repair','at':time.time()}
                else:
                    # A real internal job: compute and persist a new durable result.
                    result={'ok':True,'status':'complete','kind':'job','answer':sum(range(7))*2,'completed_at':time.time(),'execution_key':key}
                    put('job',json.dumps(result))
                DB.execute('insert into actions values (?,?,?)',(key,self.path,json.dumps(result)));DB.commit()
                return self.send(200,result)
        except (ValueError,TypeError,KeyError):
            return self.send(400,{'error':'invalid prototype action'})

if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',8800),Handler).serve_forever()
