#!/bin/bash
# 04 (as wizard): installed manifest pin, contract API, agent skill discovery, toolkit bootstrap from the installed skill.
set -uo pipefail
W=/Volumes/ThalesMedia/wizard-os/wisdom-63
exec > >(tee $W/receipts/04-checks.log) 2>&1
date -u +%FT%TZ
EP=http://127.0.0.1:9230
echo "== 1. installed package manifest (Runtipi store copy written by wam install)"
grep -A1 '^recommends:' ~/runtipi/repos/wizardapps/apps/wisdom/wizard.md
grep '^version:' ~/runtipi/repos/wizardapps/apps/wisdom/wizard.md; cat ~/runtipi/repos/wizardapps/apps/wisdom/.wizard-commit; echo
echo "== 2. GET /api/authoring/contract on the installed app"
for i in $(seq 30); do curl -fsS $EP/healthz >/dev/null 2>&1 && break; sleep 1; done
curl -fsS $EP/api/authoring/contract > /tmp/contract.json; echo "HTTP-EXIT=$?"
python3 - <<'PY'
import json; c=json.load(open('/tmp/contract.json'))
print(json.dumps({k:c.get(k) for k in ('id','version','provider','model','cli_provider','fallback','workflow_sha256','prompt_sha256','contract_sha256')}))
print('toolkit', c['toolkit']['format'], c['toolkit']['sha256'], c['toolkit']['bytes'], len(c['toolkit']['files']), 'files')
assert (c['provider'], c['model'], c['fallback']) == ('anthropic','claude-opus-5-5',False); print('CONTRACT_PIN_OK')
PY
echo "== MCP wisdom_authoring_contract (same pin over the app's /mcp)"
python3 - <<'PY'
import json, urllib.request
EP='http://127.0.0.1:9230/mcp'
def rpc(m, p, i, sid=None):
    h={'content-type':'application/json','accept':'application/json, text/event-stream'}
    if sid: h['mcp-session-id']=sid
    r=urllib.request.urlopen(urllib.request.Request(EP, json.dumps({'jsonrpc':'2.0','id':i,'method':m,'params':p}).encode(), h), timeout=30)
    b=r.read().decode()
    if 'data:' in b: b=[l[5:] for l in b.splitlines() if l.startswith('data:')][-1]
    return r.headers.get('mcp-session-id'), (json.loads(b) if b.strip() else {})
sid,_=rpc('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'w63','version':'1'}},1)
_,tl=rpc('tools/list',{},2,sid); names=[t['name'] for t in tl['result']['tools']]
print('mcp tools:', len(names), [n for n in names if 'authoring' in n])
_,r=rpc('tools/call',{'name':'wisdom_authoring_contract','arguments':{}},3,sid)
txt=r['result']['content'][0]['text']; c=json.loads(txt)
print('mcp contract:', c['provider'], c['model'], c['fallback'], c['contract_sha256'])
PY
echo "== 3. agent skill discovery (the box's stock container Hermes)"
E=$(docker ps -q --filter name=hermes-agent_wizardapps-hermes-agent-engine)
echo "hermes image $(docker inspect -f '{{.Config.Image}}' $E)"
X="docker exec -i -u 1000:1000 -e HERMES_HOME=/opt/data -e HOME=/opt/data $E"
cat > /tmp/sv.py <<'PY'
import json, sys
sys.path.insert(0, '/opt/hermes')
from tools.skills_tool import skill_view, skills_list
r = json.loads(skill_view('wisdom'))
print('skill_view(wisdom): success=%s name=%s path=%s chars=%d' % (r.get('success'), r.get('name'), r.get('path'), len(r.get('content') or '')))
import hashlib; print('skill_view content sha256', hashlib.sha256((r.get('content') or '').encode()).hexdigest())
print('pinned text present:', 'anthropic / claude-opus-5-5' in (r.get('content') or ''))
PY
echo "-- before: stock wam main install"
$X /opt/hermes/.venv/bin/python - < /tmp/sv.py 2>&1 | tail -3
echo "-- SETUP (labelled): stock wam main copies app skills to ~/.wizard-os/skills and runtipi/app-data/wizard-os/skills, but the"
echo "   stock hermes-agent container mounts neither. Sync the installed SKILL.md byte-for-byte into Hermes' native skills dir."
D=~/runtipi/app-data/wizardapps/hermes-agent/data/skills/wizard-apps/wisdom
sudo install -d -o 1000 -g 1000 $(dirname $D) $D && sudo install -o 1000 -g 1000 -m 0644 ~/.wizard-os/skills/wisdom/SKILL.md $D/SKILL.md
sha256sum ~/.wizard-os/skills/wisdom/SKILL.md $D/SKILL.md
echo "-- after"
$X /opt/hermes/.venv/bin/python - < /tmp/sv.py 2>&1 | tail -3
$X hermes skills list 2>&1 | grep -i wisdom
echo "== 4. toolkit bootstrap: the literal code block from the installed skill"
rm -rf ~/w63 && mkdir -m 700 ~/w63 && cd ~/w63
python3 - <<'PY'
import re; s=open('/home/wizard/.wizard-os/skills/wisdom/SKILL.md').read()
blocks=re.findall(r'```python\n(.*?)```', s, re.S); assert len(blocks)==1 and blocks[0].startswith('# wisdom-toolkit-bootstrap-v1')
open('fetch_toolkit.py','w').write(blocks[0]); print('extracted fetch_toolkit.py', len(blocks[0]), 'bytes')
PY
WISDOM_ENDPOINT=$EP WISDOM_TOOLKIT_DIR=$HOME/w63/toolkit python3 fetch_toolkit.py; echo "BOOTSTRAP-EXIT=$?"
cd ~/w63/toolkit && ls -R . | head -30
python3 tools/author_chapter.py --help; echo "AUTHOR-CHAPTER-HELP-EXIT=$?"
python3 tools/author_collection.py --help; echo "AUTHOR-COLLECTION-HELP-EXIT=$?"
echo "== 5. no Claude CLI on the clean box: the helper must refuse, with no output"
printf 'brief' > ~/w63/brief.txt; cp /dev/null ~/w63/x; echo '[{"url":"https://example.org/s","text":"t"}]' > ~/w63/src.json
python3 tools/author_chapter.py --chapter qa-x --brief ~/w63/brief.txt --sources ~/w63/src.json --output ~/w63/out.md --receipt ~/w63/out.receipt.json; echo "NO-CLI-EXIT=$?"; ls ~/w63/out* 2>&1
date -u +%FT%TZ
