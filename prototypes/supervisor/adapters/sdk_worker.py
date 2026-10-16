"""Tool-free Hermes SDK worker used by the prototype Agent Service adapter.

Run with the existing Hermes interpreter/provider configuration. No core edits,
profile changes, model/provider substitution, or production-session persistence.
"""
import json
import os
from pathlib import Path
import sys


def run(packet_path, result_path):
    from hermes_state import SessionDB
    from run_agent import AIAgent
    packet=json.loads(Path(packet_path).read_text())
    result=Path(result_path)
    db=SessionDB(result.parent/'private-sessions.sqlite3')
    events=[]
    def denied(*args,**kwargs):
        events.append('unexpected tool dispatch')
        raise RuntimeError('Tool-free judgment cannot dispatch a tool')
    agent=AIAgent(model=packet['model'],provider=packet['provider'],enabled_toolsets=[],
        max_iterations=1,quiet_mode=True,skip_context_files=True,load_soul_identity=False,
        skip_memory=True,skip_background_review=True,side_agent=True,fallback_model=None,
        session_id=packet['session_id'],session_db=db,tool_start_callback=denied,
        run_budget_seconds=150,reasoning_config={'enabled':True,'effort':'low'})
    try:
        if agent.tools or agent.valid_tool_names:
            raise RuntimeError('Native runtime did not enforce empty toolsets')
        if agent.model!=packet['model'] or agent.provider!=packet['provider']:
            raise RuntimeError('Native runtime route differs from configured route')
        outcome = {'final_response': 'Native empty-toolset preflight'} if packet.get('preflight') else agent.run_conversation(user_message=packet['input'],
            system_message='You are a tool-free maintenance adviser. Return the requested bounded JSON. You cannot take actions or grant permission.')
        if agent.tools or agent.valid_tool_names or events:
            raise RuntimeError('Tool-free execution invariant failed')
        output=outcome.get('final_response')
        if not isinstance(output,str) or not output.strip():raise RuntimeError('No final decision text')
        doc={'status':'completed','output':output,'model':agent.model,'provider':agent.provider,
             'execution_policy':{'tools':[],'tool_count':0,'tool_execution':'none','enforced':True},
             'private_session_store':True}
        tmp=result.with_suffix('.tmp');tmp.write_text(json.dumps(doc));tmp.chmod(0o600)
        with tmp.open('rb') as f:os.fsync(f.fileno())
        os.replace(tmp,result)
    finally:
        agent.close();db.close()

if __name__=='__main__':run(sys.argv[1],sys.argv[2])
