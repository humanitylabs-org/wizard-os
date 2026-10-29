#!/usr/bin/env python3
"""Generate the no-global-reset control subset for shell-embedded kit users.

ui.css remains self-contained for existing immutable/offline app builders.
controls.css is a generated distribution, never a second authored kit.
"""
from pathlib import Path
import argparse
import re
ROOT = Path(__file__).resolve().parent

def generate():
    source = (ROOT / 'ui.css').read_text()
    rules = [line for line in source.splitlines(True) if re.match(r'^\.wz-(?:button|card|row|actions|icon-button|pill|field|input|list|tile|main)(?:[ .:{#\[]|$)', line)]
    controls = ''.join(rules)
    aliases = {'var(--r-tile)':'var(--wz-radius-tile, 13px)', 'var(--r)':'var(--wz-radius, 16px)', 'var(--font)':'var(--wz-font-ui, system-ui, sans-serif)', 'var(--accent)':'var(--wz-accent)', 'var(--on-accent)':'var(--wz-on-accent)', 'var(--ink-2)':'var(--wz-text-secondary)', 'var(--ink-3)':'var(--wz-text-muted)', 'var(--ink)':'var(--wz-text)', 'var(--line-2)':'var(--wz-border)', 'var(--line)':'color-mix(in srgb, var(--wz-border) 55%, transparent)', 'var(--fill)':'var(--wz-surface)', 'var(--wz-space-4)':'var(--wz-space-4, 16px)', 'var(--wz-space-3)':'var(--wz-space-3, 12px)', 'var(--wz-space-2)':'var(--wz-space-2, 8px)'}
    for old, new in aliases.items():
        controls = controls.replace(old, new)
    return '/* Shared controls from ui.css: no root aliases or global reset, safe inside the shell. */\n' + controls

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'controls.css'
    expected = generate()
    if args.check:
        assert target.read_text() == expected, 'controls.css drifted; run python3 style/generate_controls.py'
        assert '@import' not in (ROOT / 'ui.css').read_text(), 'full kit must stay self-contained for offline app builders'
        print('PASS: generated shell control subset matches the self-contained canonical kit.')
    else:
        target.write_text(expected)

if __name__ == '__main__':
    main()
