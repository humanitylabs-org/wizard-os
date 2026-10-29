#!/usr/bin/python3
"""Independent, read-only tailnet status. No secrets, shell, or mutation routes.
Runs as nobody from /opt (cannot read $HOME), so its settings come from argv:
  server.py BIND_IP PORT SOURCE_IP USER
"""
import http.server,json,pathlib,sys,time
ROOT=pathlib.Path('/var/lib/host-hop-status')
BIND,PORT,SOURCE,USER=sys.argv[1],int(sys.argv[2]),sys.argv[3],sys.argv[4]
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path not in ('/','/status.json','/health'):
   self.send_error(404);return
  try: state=json.loads((ROOT/'status.json').read_text())
  except (OSError,ValueError):state={'phase':'prepared-not-launched','source':SOURCE,'target':BIND}
  state['observed_at']=time.time()
  state['recovery']='SSH '+USER+'@'+BIND+'; /usr/local/bin/host-hop-recovery status; /usr/local/bin/host-hop-recovery recover-source (refuses after promotion barrier; no automatic failback).'
  body=json.dumps(state,indent=2).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def do_POST(self):self.send_error(405,'read-only; recovery requires SSH')
 def log_message(self,*args):pass
if __name__=='__main__':http.server.ThreadingHTTPServer((BIND,PORT),Handler).serve_forever()
