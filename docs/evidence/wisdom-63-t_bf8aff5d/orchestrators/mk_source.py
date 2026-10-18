"""Build a one-chapter export source tree around an orchestrator's chapter Markdown."""
import json, shutil, sys
from pathlib import Path
md, receipt, dest, coll = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
shutil.rmtree(dest, ignore_errors=True)
(dest / 'src/content').mkdir(parents=True); (dest / 'receipts').mkdir()
cid = 'qa-empty-hub'
cat = {'thinkers': [{'id': 'qa-laozi', 'name': 'Laozi (QA)', 'bio': 'Synthetic QA thinker row for the #63 acceptance.', 'url': 'https://www.gutenberg.org/ebooks/216'}],
       'entries': [{'id': cid, 'thinker': 'qa-laozi', 'part': 1, 'title': 'Laozi — The Empty Hub', 'source_url': 'https://www.gutenberg.org/cache/epub/216/pg216.txt',
                    'published_at': '2026-10-18T00:00:00.000Z', 'origin': 'Wisdom', 'initial_read': False, 'initial_archived': False}],
       'collections': [{'id': coll, 'title': 'QA #63 ' + coll, 'form': 'book', 'by': 'Wizard', 'thinker': 'qa-laozi', 'entries': [cid]}]}
(dest / 'src/content/catalog.json').write_text(json.dumps(cat, ensure_ascii=False, indent=1) + '\n')
shutil.copyfile(md, dest / 'src/content' / (cid + '.md'))
shutil.copyfile(receipt, dest / 'receipts' / (cid + '.receipt.json'))
print('built', dest)
