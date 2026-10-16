from pathlib import Path
p=Path(__file__).resolve().parent.parent/'web/index.html'
s=p.read_text()
assert all(x in s for x in ['__wizardCloseOverlay','api/status' if False else "api('status')",'Prototype','Maintenance rules'])
print('View source verified; no compilation needed')
