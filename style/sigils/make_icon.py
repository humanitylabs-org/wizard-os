#!/usr/bin/env python3
"""Export a Wizard OS app icon (a sigil) for an app.

    python3 -m venv .venv && .venv/bin/pip install skia-pathops fonttools resvg-py
    .venv/bin/python make_icon.py <app-id> --out <app repo>          # app already in palette.REGISTRY
    .venv/bin/python make_icon.py <app-id> --glyph bag --hue 55 --out <app repo>
    .venv/bin/python make_icon.py --list                              # glyphs with their meaning
    .venv/bin/python make_icon.py --free-hues                         # where a new app's colour should go

Writes into <out>:
    icon.svg            master: dark-glass tile + lit glyph, 512 grid
    icon.png            512x512, the `icon:` file for wizard.md and the launcher
    icon-192.png        PWA manifest icon
    icon-maskable.png   512x512 with the glyph inside the 80% safe zone (Android adaptive icons)
    favicon.svg         the bare glyph in the app colour, no tile
    favicon-32.png      the bare glyph, 32px
New glyphs are added to glyphs.py (one silhouette, one bite); see ../ICONS.md.
"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glyphs, palette  # noqa: E402


def mix(a, b, t):
    """Blend two #RRGGBB colours, t=0 → a, t=1 → b."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02X%02X%02X' % tuple(round(x + (y - x) * t) for x, y in zip(pa, pb))


def tile_svg(d, c, glyph_scale=0.70):
    """The launcher tile, same recipe as the shell's CSS: dark glass tinted by the hue, a bloom behind
    the glyph, a sheen across the top, and the glyph lit top-to-bottom in the app colour."""
    s = glyph_scale; off = 256 * (1 - s)
    hi, deep = mix(c, '#FFFFFF', .58), mix(c, '#1A0F2E', .20)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
<defs>
 <linearGradient id="base" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#17121F"/><stop offset="1" stop-color="#0C0A12"/></linearGradient>
 <radialGradient id="top" cx=".5" cy="-.08" r=".75"><stop offset="0" stop-color="{c}" stop-opacity=".40"/><stop offset=".8" stop-color="{c}" stop-opacity="0"/></radialGradient>
 <radialGradient id="bot" cx=".5" cy="1.2" r=".6"><stop offset="0" stop-color="{c}" stop-opacity=".26"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>
 <radialGradient id="bloom" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{c}" stop-opacity=".42"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>
 <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity=".07"/><stop offset=".38" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
 <linearGradient id="lit" x1=".4" y1="0" x2=".6" y2="1"><stop offset="0" stop-color="{hi}"/><stop offset=".46" stop-color="{c}"/><stop offset="1" stop-color="{deep}"/></linearGradient>
 <filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="22"/></filter>
 <filter id="lift" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#000" flood-opacity=".35"/></filter>
 <clipPath id="sq"><rect width="512" height="512" rx="164"/></clipPath>
</defs>
<g clip-path="url(#sq)">
 <rect width="512" height="512" fill="url(#base)"/>
 <rect width="512" height="512" fill="url(#top)"/>
 <rect width="512" height="512" fill="url(#bot)"/>
 <circle cx="256" cy="256" r="160" fill="url(#bloom)" filter="url(#soft)"/>
 <g transform="translate({off:.1f} {off:.1f}) scale({s})" filter="url(#lift)"><path d="{d}" fill="url(#lit)" fill-rule="nonzero"/></g>
 <rect width="512" height="512" fill="url(#sheen)"/>
</g>
<rect x="2" y="2" width="508" height="508" rx="162" fill="none" stroke="{c}" stroke-opacity=".38" stroke-width="4"/>
</svg>'''


def bare_svg(d, c):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="{d}" fill="{c}"/></svg>'


def png(svg, size, path):
    import resvg_py
    data = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size))
    open(path, 'wb').write(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('app', nargs='?')
    ap.add_argument('--glyph'); ap.add_argument('--hue', type=float)
    ap.add_argument('--quiet', action='store_true', help='system/tool app: low chroma')
    ap.add_argument('--out', default='.')
    ap.add_argument('--list', action='store_true'); ap.add_argument('--free-hues', action='store_true')
    a = ap.parse_args()
    lib = glyphs.build()
    if a.list:
        for k, v in lib.items(): print(f'{k:10s} {v["desc"]}')
        return
    if a.free_hues:
        for width, mid, lo, hi in palette.free_hues():
            print(f'hue {mid:3d}°  (gap {lo}°–{hi}°, {width}° wide)  {palette.tone(mid)}')
        return
    if not a.app: ap.error('app id required')
    if a.app in palette.REGISTRY and a.glyph is None and a.hue is None:
        g, h, c = palette.REGISTRY[a.app]
    else:
        if not (a.glyph and a.hue is not None):
            ap.error(f'{a.app} is not in palette.REGISTRY: pass --glyph and --hue, then add it to the registry')
        g, h, c = a.glyph, a.hue, (palette.C_QUIET if a.quiet else None)
    if g not in lib: ap.error(f'no glyph "{g}" (see --list); draw it in glyphs.py first')
    col = palette.tone(h, c); d = lib[g]['d']
    os.makedirs(a.out, exist_ok=True)
    tile = tile_svg(d, col)
    open(os.path.join(a.out, 'icon.svg'), 'w').write(tile)
    png(tile, 512, os.path.join(a.out, 'icon.png'))
    png(tile, 192, os.path.join(a.out, 'icon-192.png'))
    png(tile_svg(d, col, glyph_scale=0.56), 512, os.path.join(a.out, 'icon-maskable.png'))
    bare = bare_svg(d, col)
    open(os.path.join(a.out, 'favicon.svg'), 'w').write(bare)
    png(bare, 32, os.path.join(a.out, 'favicon-32.png'))
    print(json.dumps({'app': a.app, 'glyph': g, 'hue': h, 'colour': col, 'out': os.path.abspath(a.out),
                      'launcher_json': {'icon': g, 'colors': [col]}}))


if __name__ == '__main__':
    main()
