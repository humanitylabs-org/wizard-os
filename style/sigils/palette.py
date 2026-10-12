"""Sigil colour: one hue per app, every hue at the same perceived lightness (OKLCH).

The registry below is the source of truth for which app owns which glyph and hue. A new app claims a
free hue here (see `python3 make_icon.py --free-hues`) so no two apps in a launcher share a colour.
"""
import math

L_MAIN, C_MAIN = 0.79, 0.18     # vivid apps
C_QUIET = 0.06                  # system / tool / legacy apps keep their hue at low chroma
MIN_GAP = 12                    # degrees between two vivid apps' hues


def oklch_to_lin(L, C, h):
    a = C * math.cos(math.radians(h)); b = C * math.sin(math.radians(h))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def hexof(L, C, h):
    """sRGB hex for an OKLCH colour, lowering chroma until it fits the gamut."""
    while C > 0 and not all(-1e-4 <= c <= 1 + 1e-4 for c in oklch_to_lin(L, C, h)):
        C -= 0.002
    enc = lambda c: round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))
    return '#%02X%02X%02X' % tuple(enc(min(max(c, 0), 1)) for c in oklch_to_lin(L, C, h))


def tone(h, c=None):
    """The app colour for hue `h`. Yellows/greens read darker at equal L and blues brighter, so nudge them."""
    c = C_MAIN if c is None else c
    L = L_MAIN + (0.06 if 70 <= h <= 135 else 0) - (0.02 if 235 <= h <= 285 else 0)
    return hexof(L, c, h)


# app id: (glyph, hue°, chroma or None for vivid)
REGISTRY = {
    'calendar':      ('calendar', 8,   None),
    'mizel':         ('mic',      30,  None),
    'usuals':        ('usuals',   42,  None),
    'v-day':         ('day',      48,  None),
    'shopping':      ('bag',      55,  None),
    'wisdom':        ('wisdom',   78,  None),
    'cinequeue':     ('cine',     100, None),
    'trackhunt':     ('track',    128, None),
    'android-apps':  ('android',  150, None),
    'maps':          ('pin',      114, None),
    'v-inbox':       ('inbox',    166, None),
    'topics':        ('eye',      178, None),
    'wizard-signal': ('signal',   205, None),
    'meditation':    ('meditate', 218, None),
    'files':         ('files',    232, None),
    'wizard-search': ('search',   256, None),
    'projects':      ('projects', 276, None),
    'wizard':        ('chats',    296, None),
    'v-week':        ('week',     310, None),
    'social':        ('social',   322, None),
    'wizard-music':  ('music',    344, None),
    # quiet: system, tools, legacy
    'iching':        ('iching',   75,  0.06),
    'console':       ('console',  250, 0.025),
    'legacy-wizard': ('wizard',   296, 0.05),
    'v-month':       ('month',    262, 0.08),
    'side-button':   ('side',     300, 0.07),
}


def colour_of(app_id):
    g, h, c = REGISTRY[app_id]
    return tone(h, c)


def free_hues(step=2):
    """Hue bands at least MIN_GAP° from every vivid app, widest first: where a new app should go."""
    taken = sorted(h for _, h, c in REGISTRY.values() if c is None)
    gaps = []
    for i, h in enumerate(taken):
        nxt = taken[(i + 1) % len(taken)] + (360 if i == len(taken) - 1 else 0)
        if nxt - h >= 2 * MIN_GAP:
            gaps.append((nxt - h, (h + (nxt - h) // 2) % 360, h, nxt % 360))
    return sorted(gaps, reverse=True)
