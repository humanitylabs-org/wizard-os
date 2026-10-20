import hashlib, json, sys
from pathlib import Path
w = Path(sys.argv[1]); md = w / 'chapter.md'; rc = w / 'chapter.receipt.json'; cli = w / 'chapter.receipt.json.cli.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
r = json.loads(rc.read_text()); c = json.loads(cli.read_text())
body = c.get('structured_output') or json.loads(c['result'])
out = {'dir': str(w), 'receipt_model': r['model'], 'receipt_provider': r['provider'], 'receipt_modelUsage_keys': sorted(r['modelUsage']),
       'cli_modelUsage_keys': sorted(c.get('modelUsage', {})), 'output_sha_matches_chapter': r['output_sha256'] == sha(md),
       'cli_sha_matches_raw': r['cli_result_sha256'] == sha(cli), 'raw_body_equals_chapter': body['body'].encode() == md.read_bytes(),
       'workflow_sha256': r['workflow_sha256'], 'prompt_sha256': r['prompt_sha256'], 'checks': r['checks'],
       'cli_total_cost_usd': c.get('total_cost_usd'), 'cli_is_error': c.get('is_error'), 'chapter_sha256': sha(md)}
print(json.dumps(out, indent=1))
