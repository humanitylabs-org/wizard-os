import hashlib, json, sys
from pathlib import Path
md, rc = Path(sys.argv[1]), Path(sys.argv[2]); cli = rc.with_name(rc.name + '.cli.json')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
r = json.loads(rc.read_text()); c = json.loads(cli.read_text())
body = c.get('structured_output') or json.loads(c['result'])
rej = sorted((rc.parent / 'rejected').glob('*.rejected.json'))
print(json.dumps({'receipt_model': r['model'], 'receipt_modelUsage': sorted(r['modelUsage']), 'cli_modelUsage': {k: v.get('provider') for k, v in c.get('modelUsage', {}).items()},
  'attempt': r.get('attempt'), 'rejected_attempts': r.get('rejected_attempts'), 'rejected_files': len(rej),
  'rejected_errors': [json.loads(p.read_text())['error'][:90] for p in rej],
  'rejected_models': [sorted(json.loads(json.loads(p.read_text())['cli_result']).get('modelUsage', {})) for p in rej],
  'output_sha_matches_chapter': r['output_sha256'] == sha(md), 'cli_sha_matches_raw': r['cli_result_sha256'] == sha(cli),
  'raw_body_equals_chapter': body['body'].encode() == md.read_bytes(), 'checks': r['checks'],
  'accepted_cost_usd': c.get('total_cost_usd'), 'rejected_cost_usd': [json.loads(json.loads(p.read_text())['cli_result']).get('total_cost_usd') for p in rej]}, indent=1))
