#!/usr/bin/env python3
"""Enclosure reference drawings for esp-read — regenerates the PNGs in this dir.

Emits SVG (no third-party deps) and rasterises with `rsvg-convert`
(librsvg). Everything is driven by the dimension tables below, so a hardware
change means editing a number and re-running:

    python3 layout_generator.py

Figures (all to scale; sections exaggerate Z only, and say so):
  component-layout.png   front view (portrait, looking at the screen, spine on
                         the LEFT): outline, glass, visible window, every
                         internal footprint, keys, light pipes, pinholes, USB-C
  back-view.png          back view (spine on the RIGHT, X mirrored): spine
                         plateau, stowing recess, cove, HAT bump, grip pad,
                         stowed cover
  section.png            cross-sections across the width at the button band
                         (Y 92) and through the battery (Y 22)

Design: the Oasis-style grip spine ("Form" in MEASUREMENTS.md) — NOT the old
option-B wedge. Source of truth: `enclosure/MEASUREMENTS.md` (later
"SUPERSEDES" notes win; the battery is NOT rotated) and the CAD model
`enclosure/ereader-case.sc`, whose coordinate frame is used here:
  X across the width, 0 = spine's outer edge (left in the front view)
  Y along the length, 0 = bottom edge
  Z depth, 0 = spine's back, T = front face
"""
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
BG = '#f5f5f5'

# ---------------------------------------------------------------- case (mm)
W, L, T = 107.7, 138.4, 9.0      # outline width (X), length (Y), spine depth (Z)
R_CORNER = 6.0                   # plan corner radius
WALL = 1.2                       # shell
FRONT_T = 1.2                    # front plate, Z 7.8-9.0
Z_TUB = T - FRONT_T              # 7.8, tub rim / front-plate seam
FRONT_CHAMFER = 0.8
SPINE_CAV = (1.2, 32.1)          # spine cavity X range
X_STEP = 33.3                    # back step: stowing recess for X > X_STEP
Z_RECESS = 2.2                   # recess floor (back of the screen section)
SCREEN_BACK = 1.0                # screen-section back wall
Z_FLOOR = Z_RECESS + SCREEN_BACK  # 3.2, screen-section interior floor
R_SPINE_BACK = 4.0               # spine's outer back edge round
R_STEP = 1.3                     # step convex round
COVE = 0.6                       # concave cove at the step foot (CAD value)
WALL_THIN = 0.9                  # spine back wall thinned under the HAT

# glass + lip
GLASS = (35.1, 106.3, 9.0, 135.4)          # x0, x1, y0, y1
GLASS_Z = (7.14, 8.2)
LIP = 0.8
WINDOW = (38.85, 102.35, 20.25, 131.9)     # lip opening at its inner face
WIN_CHAMFER = 0.8                          # 45 deg, opening outward

# --------------------------------------------------------------- parts (mm)
# name: x0, x1, y0, y1, thickness, stroke, fill, label
PARTS = {
    'battery': (1.85, 31.45, 1.5, 37.5, 4.9, '#1a7a3c', '#d9f0e1',
                'Battery 29.6 x 36 x 4.9 (5.3 at wire end)'),
    'hat':     (1.4, 31.9, 38.0, 103.5, 5.2, '#d98a00', '#fdeacc',
                'Driver HAT 30.5 x 65.5 x 5.2'),
    'xiao':    (7.9, 25.4, 115.9, 136.9, 4.5, '#cc2222', '#fbdcdc',
                'XIAO ESP32-S3+ 17.5 x 21 x 4.5'),
    'adapter': (40.0, 72.0, 10.0, 28.0, 3.6, '#7a4a1a', '#efe0cf',
                'FFC adapter 32 x 18 x 3.6'),
    'storage': (37.0, 58.5, 112.0, 129.7, 2.6, '#2255cc', '#dde7fb',
                'Storage 21.5 x 17.7 x 2.6'),
    'antenna': (64.0, 104.0, 113.0, 133.0, 0.1, '#7d3cc4', '#efe2fb',
                'WiFi antenna sticker 40 x 20'),
}
HAT_BARE_BOTTOM = 11.0           # switch end (down)
HAT_BARE_TOP = 13.5
HAT_MID = (54.0, 90.0)           # middle components (underside), Y
HAT_HOLES = [(16.65 + dx, 70.75 + dy) for dx in (-11.5, 11.5) for dy in (-29, 29)]
HAT_HOLE_D = 3.0
HAT_PCB = 1.7
HAT_TOP_PARTS = 2.0
HAT_INDUCTOR = 1.5
ZIF = (29.9, 31.9, 62.0, 79.5)   # FPC ZIF on the glass-side long edge (24 from each end)
ANT_KEEPOUT = 10.0               # magnets >= 10 from the antenna
FPC_X = 70.7                     # panel FPC leaves the glass bottom, centred
FREE_GAP = (103.5, 115.9)

# keys on the spine's front face
KEY_X = 16.65
SWITCH = (6.0, 3.5)              # switch body; 6.0 drawn across X (assumed)
KEYS = [('BACK', 91.75, 'pill'), ('FWD', 103.75, 'pill'), ('MENU', 44.0, 'round')]
PILL_CAP = (5.0, 2.6)            # indicative cap stem
ROUND_CAP_D = 3.6
SWITCH_H, KNOB_H = 3.6, 4.3      # body / to top of knob

# light pipes + pinholes on the spine's front face
LEDS = [('charge LED', 11.4, 131.9), ('user LED', 21.9, 131.9)]
PIPE_D = 1.5
PINHOLES = [('RESET', 11.4, 133.9), ('BOOT', 21.9, 133.9)]
PINHOLE_D = 1.0
USBC = (KEY_X - 4.45, KEY_X + 4.45)          # 8.9 wide receptacle, top edge

# back
HAT_BUMP = (9.0, 27.0, 52.0, 92.0, 1.4)      # x0, x1, y0, y1, proud of Z=0
GRIP_PAD = (R_SPINE_BACK, X_STEP - R_STEP, 30.0, 110.0)   # X range assumed
COVER = (34.0, W, 0.0, L, 2.0)               # x0, x1, y0, y1, thickness
MAGNET = (6.0, 1.0)                          # dia x thick, 4 pairs

# section cut planes
SEC_BUTTON_Y = 92.0
SEC_BATTERY_Y = 22.0     # "Y~20": 22 so the cut passes through the window (starts 20.25)


# ------------------------------------------------------------------ svg bits
class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []
        self.add('<defs>'
                 '<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" '
                 'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" '
                 'stroke="#d98a00" stroke-width="1.2"/></pattern>'
                 '<pattern id="hatchg" width="7" height="7" patternUnits="userSpaceOnUse" '
                 'patternTransform="rotate(-45)"><line x1="0" y1="0" x2="0" y2="7" '
                 'stroke="#888" stroke-width="1"/></pattern>'
                 '<marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" '
                 'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
                 'fill="#333"/></marker></defs>')

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, stroke='#333', fill='none', sw=1.4, dash=None, rx=0, op=1.0):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                 f'rx="{rx:.1f}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{d}/>')

    def circle(self, cx, cy, r, stroke='#333', fill='none', sw=1.2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def path(self, d, stroke='#333', fill='none', sw=1.4, dash=None, op=1.0):
        da = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<path d="{d}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{da}/>')

    def line(self, x1, y1, x2, y2, stroke='#333', sw=1.0, dash=None, arrows=False):
        da = f' stroke-dasharray="{dash}"' if dash else ''
        m = ' marker-start="url(#arr)" marker-end="url(#arr)"' if arrows else ''
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{da}{m}/>')

    def text(self, x, y, s, size=11, fill='#222', anchor='start', weight='normal',
             style='normal'):
        s = (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="Helvetica,Arial,sans-serif" '
                 f'font-size="{size}" font-weight="{weight}" font-style="{style}" '
                 f'fill="{fill}" text-anchor="{anchor}">{s}</text>')

    def lines(self, x, y, rows, size=9.5, fill='#555', step=None, **kw):
        step = step or size * 1.45
        for i, r in enumerate(rows):
            self.text(x, y + i * step, r, size=size, fill=fill, **kw)
        return y + len(rows) * step

    def save(self, name):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
                f'height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
                f'<rect width="100%" height="100%" fill="{BG}"/>')
        svg = head + ''.join(self.parts) + '</svg>'
        out_svg = HERE / f'{name}.svg'
        out_png = HERE / f'{name}.png'
        out_svg.write_text(svg)
        try:
            subprocess.run(['rsvg-convert', '-o', str(out_png), str(out_svg)], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            sys.exit(f'rsvg-convert failed ({e}) — install librsvg')
        out_svg.unlink()
        print(f'wrote {out_png.name}  ({self.w}x{self.h})')


class Plan:
    """Maps plan mm (X, Y) to px. mirror=True gives the back view (X flipped)."""

    def __init__(self, s, ox, oy, k, mirror=False):
        self.s, self.ox, self.oy, self.k, self.mirror = s, ox, oy, k, mirror

    def px(self, x):
        return self.ox + ((W - x) if self.mirror else x) * self.k

    def py(self, y):
        return self.oy + (L - y) * self.k

    def box(self, x0, x1, y0, y1, **kw):
        a, b = sorted((self.px(x0), self.px(x1)))
        self.s.rect(a, self.py(y1), b - a, (y1 - y0) * self.k, **kw)

    def dot(self, x, y, d, **kw):
        self.s.circle(self.px(x), self.py(y), d / 2 * self.k, **kw)

    def label(self, x, y, txt, **kw):
        self.s.text(self.px(x), self.py(y), txt, **kw)

    def outline(self, inset=0.0, **kw):
        r = max(R_CORNER - inset, 0)
        self.s.rect(self.ox + inset * self.k, self.oy + inset * self.k,
                    (W - 2 * inset) * self.k, (L - 2 * inset) * self.k, rx=r * self.k, **kw)

    def callout(self, x, y, tx, ty, rows, color='#333', anchor='start', size=9.5):
        """Leader from feature (x, y mm) to text at absolute px (tx, ty)."""
        fx, fy = self.px(x), self.py(y)
        ex = tx + (4 if anchor == 'end' else -4)
        self.s.line(ex, ty - 4, fx, fy, stroke=color, sw=0.8)
        self.s.circle(fx, fy, 1.6, stroke=color, fill=color, sw=0.5)
        for i, r in enumerate(rows):
            self.s.text(tx, ty + i * size * 1.3, r, size=size, fill=color, anchor=anchor,
                        weight='bold' if i == 0 else 'normal')


def dim_h(s, x0, x1, y, txt, size=10, above=True):
    s.line(x0, y, x1, y, sw=0.9, arrows=True)
    s.text((x0 + x1) / 2, y - 4 if above else y + 13, txt, size=size, anchor='middle')


def dim_v(s, x, y0, y1, txt, size=10, left=False):
    s.line(x, y0, x, y1, sw=0.9, arrows=True)
    s.text(x - 5 if left else x + 5, (y0 + y1) / 2 + 4, txt, size=size,
           anchor='end' if left else 'start')


def part(key):
    return PARTS[key]


def draw_internal(p, op=0.55, labels=True):
    """All internal footprints, hidden behind the front plate / glass."""
    s = p.s
    for key in ('battery', 'hat', 'xiao', 'adapter', 'storage', 'antenna'):
        x0, x1, y0, y1, t, st, fi, _ = part(key)
        p.box(x0, x1, y0, y1, stroke=st, fill=fi, sw=1.5, op=op)
    # HAT zones: bare ends, middle components, holes, ZIF
    x0, x1, y0, y1, *_ = part('hat')
    p.box(x0, x1, HAT_MID[0], HAT_MID[1], stroke='#d98a00', fill='url(#hatch)', sw=0.8, op=0.5)
    for yy in (y0 + HAT_BARE_BOTTOM, y1 - HAT_BARE_TOP):
        s.line(p.px(x0), p.py(yy), p.px(x1), p.py(yy), stroke='#d98a00', sw=1.0, dash='4,3')
    for hx, hy in HAT_HOLES:
        p.dot(hx, hy, HAT_HOLE_D, stroke='#d98a00', fill='#fff', sw=1.3)
    p.box(*ZIF, stroke='#d98a00', fill='#d98a00', sw=0.8, op=0.8)
    # antenna keep-out for magnets
    ax0, ax1, ay0, ay1, *_ = part('antenna')
    k = ANT_KEEPOUT
    p.box(ax0 - k, min(ax1 + k, W), ay0 - k, min(ay1 + k, L), stroke='#7d3cc4', sw=1.0,
          dash='2,4')
    if not labels:
        return
    for key, rows in (
            ('battery', ['Battery', '29.6 x 36 x 4.9', 'Y 1.5-37.5', 'wires: top-centre']),
            ('xiao', ['XIAO S3+', '17.5x21x4.5', 'Y 115.9-136.9'])):
        x0, x1, y0, y1, _, st, *_ = part(key)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - (5 if key == 'xiao' else 0)
        for i, r in enumerate(rows):
            sz = 11 if i == 0 else 8.5
            s.text(p.px(cx), p.py(cy) - 10 + i * 12, r, size=sz, fill=st, anchor='middle',
                   weight='bold' if i == 0 else 'normal')
    # battery wire exit
    p.dot(16.65, 37.5, 1.2, stroke='#1a7a3c', fill='#1a7a3c')
    # HAT text in the middle zone
    s.text(p.px(16.65), p.py(84), 'Driver HAT', size=11, fill='#a36400', anchor='middle',
           weight='bold')
    for i, r in enumerate(('30.5 x 65.5 x 5.2', 'Y 38.0-103.5', 'switch end DOWN',
                           'parts Y 54-90 (hatched)')):
        s.text(p.px(16.65), p.py(84) + 12 + i * 11, r, size=8.5, fill='#a36400', anchor='middle')
    s.text(p.px(16.65), p.py(98), 'bare 13.5', size=8, fill='#a36400', anchor='middle')
    s.text(p.px(16.65), p.py(39.5), 'bare 11 (switch end)', size=8, fill='#a36400',
           anchor='middle')
    for key, rows in (
            ('adapter', ['FFC adapter', '32 x 18 x 3.6']),
            ('storage', ['Storage', '21.5 x 17.7 x 2.6']),
            ('antenna', ['WiFi antenna 40 x 20', 'magnets >= 10 away (dotted)'])):
        x0, x1, y0, y1, _, st, *_ = part(key)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for i, r in enumerate(rows):
            s.text(p.px(cx), p.py(cy) - 2 + i * 11, r, size=10 if i == 0 else 8.5, fill=st,
                   anchor='middle', weight='bold' if i == 0 else 'normal')


# ------------------------------------------------------- fig 1: front view
def fig_component_layout():
    k = 5.0
    ox, oy = 250, 115
    s = Svg(1150, 940)
    s.text(30, 38, 'esp-read — front view & component layout (to scale)', size=21, weight='bold')
    s.text(30, 58, f'portrait, looking at the screen · spine on the LEFT · {k:g} px/mm · '
                   'filled parts are internal (behind the front plate / glass) · '
                   'coordinates are the CAD frame (X from spine edge, Y from bottom)',
           size=10, fill='#555')
    p = Plan(s, ox, oy, k)

    p.outline(fill='#e8e4da', stroke='#111', sw=2.4)
    p.outline(inset=FRONT_CHAMFER, stroke='#999', sw=0.8)           # front chamfer
    p.box(SPINE_CAV[0], SPINE_CAV[1], WALL, L - WALL, stroke='#777', sw=0.9, dash='6,3')
    s.line(p.px(X_STEP), p.py(0), p.px(X_STEP), p.py(L), stroke='#555', sw=1.0, dash='10,3,2,3')
    p.box(*GLASS, stroke='#4a6fc4', fill='#dbe6fb', sw=1.4, dash='6,3', op=0.6)

    draw_internal(p)

    # panel FPC: leaves the glass bottom, folds back behind the glass
    s.line(p.px(FPC_X), p.py(GLASS[2]), p.px(FPC_X), p.py(4.0), stroke='#4a6fc4', sw=4.0)
    s.path(f'M{p.px(FPC_X):.1f},{p.py(4.0):.1f} q0,{2.0*k:.1f} -{1.5*k:.1f},{2.0*k:.1f}',
           stroke='#4a6fc4', sw=1.4)

    # visible window: lip opening (inner face) + chamfer opening (front face)
    x0, x1, y0, y1 = WINDOW
    p.box(x0, x1, y0, y1, stroke='#111', sw=1.8)
    c = WIN_CHAMFER
    p.box(x0 - c, x1 + c, y0 - c, y1 + c, stroke='#111', sw=0.8)

    # keys
    for name, ky, shape in KEYS:
        p.box(KEY_X - SWITCH[0] / 2, KEY_X + SWITCH[0] / 2, ky - SWITCH[1] / 2,
              ky + SWITCH[1] / 2, stroke='#5a2a99', sw=0.9, dash='3,2')
        if shape == 'pill':
            cw, ch = PILL_CAP
            s.rect(p.px(KEY_X - cw / 2), p.py(ky + ch / 2), cw * k, ch * k,
                   rx=ch * k / 2, stroke='#5a2a99', fill='#c9a9ee', sw=1.4)
        else:
            p.dot(KEY_X, ky, ROUND_CAP_D, stroke='#5a2a99', fill='#c9a9ee', sw=1.4)
    for _, x, y in LEDS:
        p.dot(x, y, PIPE_D, stroke='#0a7d8c', fill='#bdf3f8', sw=1.2)
    for _, x, y in PINHOLES:
        p.dot(x, y, PINHOLE_D, stroke='#222', fill='#222', sw=0.6)
    # USB-C opening on the top edge
    s.rect(p.px(USBC[0]), p.py(L) - 7, (USBC[1] - USBC[0]) * k, 9, rx=4,
           stroke='#222', fill='#555', sw=1.0)

    # callouts (left margin)
    tx = ox - 22
    a = dict(anchor='end')
    p.callout(KEY_X - 2.0, L, tx, oy - 12, ['USB-C (top edge)', f'X {USBC[0]:.1f}-{USBC[1]:.1f}'],
              **a)
    p.callout(11.4, 133.9, tx, oy + 22, ['RESET pinhole Ø1.0', 'X 11.4, Y 133.9 (drilled)'], **a)
    p.callout(11.4, 131.9, tx, oy + 52, ['charge LED pipe Ø1.5', 'X 11.4, Y 131.9 (outer side)'],
              **a)
    p.callout(21.9, 133.9, tx, oy + 82, ['BOOT pinhole Ø1.0', 'X 21.9, Y 133.9'], **a)
    p.callout(21.9, 131.9, tx, oy + 112, ['user LED pipe Ø1.5', 'X 21.9, Y 131.9'], **a)
    p.callout(KEY_X - 2.5, 103.75, tx, p.py(103.75) - 4,
              ['FWD key (pill)', 'Y 103.75, X 16.65', 'over HAT top edge / free gap'], **a)
    p.callout(KEY_X - 2.5, 91.75, tx, p.py(91.75) + 22,
              ['BACK key (pill)', 'Y 91.75 (glass +82.75)', 'over HAT bare top end'], **a)
    p.callout(KEY_X - 1.8, 44.0, tx, p.py(44.0),
              ['MENU key (round)', 'Y 44, over bare', 'switch end (38-49)'], **a)
    p.callout(SPINE_CAV[0] + 0.3, 75.0, tx, p.py(70.0),
              ['spine cavity X 1.2-32.1', 'switch 6.0 x 3.5 dashed', '(6.0 across X, assumed)'],
              color='#555', **a)
    p.callout(9.0, 26.0, tx, p.py(20.0), ['Battery: NOT rotated', '29.6 across, 36 along'],
              color='#1a7a3c', **a)
    s.text(p.px(16.65), p.py((FREE_GAP[0] + FREE_GAP[1]) / 2) + 3,
           f'free gap {FREE_GAP[0]}-{FREE_GAP[1]}', size=8, fill='#555', anchor='middle')

    # right-side callouts
    rx = ox + W * k + 26
    p.callout(*(lambda g: (g[1], 60))(GLASS), rx, p.py(62),
              ['glass 71.2 x 126.4 x 1.06', 'X 35.1-106.3, Y 9.0-135.4', '(dashed, behind 0.8 lip)'],
              color='#4a6fc4')
    p.callout(WINDOW[1], 100, rx, p.py(104),
              ['visible window 63.5 x 111.65', 'X 38.85-102.35', 'Y 20.25-131.9 (inner face)',
               '+0.8 45° chamfer to front'], color='#111')
    p.callout(FPC_X, 6.0, rx, p.py(14),
              ['panel FPC, X 70.7', 'leaves glass bottom,', 'folds back to adapter'],
              color='#4a6fc4')
    p.callout(ZIF[1], 72.0, rx, p.py(36) - 220,
              ['HAT ZIF (FPC) connector', 'long edge facing glass'], color='#d98a00')
    p.callout(X_STEP, 30, rx, p.py(30) + 6,
              ['back step X 33.3', '(hidden, dash-dot)'], color='#555')

    # overall dims
    dim_h(s, p.px(0), p.px(W), p.py(0) + 34, f'W {W}', above=False)
    dim_h(s, p.px(0), p.px(X_STEP), p.py(0) + 16, 'spine 33.3', size=9, above=False)
    dim_v(s, p.px(W) + 14, p.py(L), p.py(0), f'L {L}', left=False)
    dim_v(s, p.px(GLASS[1]) + 6, p.py(GLASS[2]), p.py(0), 'chin 9', size=8.5)
    dim_v(s, p.px(GLASS[1]) + 6, p.py(L), p.py(GLASS[3]), 'top 3', size=8.5)

    # notes
    ny = p.py(0) + 64
    s.lines(30, ny, [
        'Spine column from the bottom: battery 1.5-37.5 -> HAT 38.0-103.5 (switch end down) -> '
        'free gap 103.5-115.9 -> XIAO 115.9-136.9 (USB-C out the top, top face forward).',
        'Screen section (X > 33.3, 6.8 deep) holds only the glass, FFC adapter, storage module, '
        'antenna sticker and wiring. HAT holes Ø3 at 23 x 58 (centres X 5.15 / 28.15, '
        'Y 41.75 / 99.75).',
        'Plan corners R6 (inner R4.8). Front edge 0.8 chamfer (thin inner line). '
        'Keys, light pipes and pinholes are on the spine front face; cap sizes are indicative.',
    ], size=9.5)
    s.save('component-layout')


# ------------------------------------------------------- fig 2: back view
def fig_back_view():
    k = 5.0
    ox, oy = 250, 115
    s = Svg(1150, 925)
    s.text(30, 38, 'esp-read — back view (to scale)', size=21, weight='bold')
    s.text(30, 58, f'viewed from behind · spine on the RIGHT (X mirrored) · {k:g} px/mm · '
                   'Z values are heights above the spine back (Z = 0)', size=10, fill='#555')
    p = Plan(s, ox, oy, k, mirror=True)

    p.outline(fill='#e8e4da', stroke='#111', sw=2.4)
    # recess floor (screen-section back)
    s.path(f'M{p.px(X_STEP):.1f},{p.py(L):.1f} H{p.px(W) + R_CORNER * k:.1f} '
           f'A{R_CORNER * k},{R_CORNER * k} 0 0 0 {p.px(W):.1f},{p.py(L) + R_CORNER * k:.1f} '
           f'V{p.py(0) - R_CORNER * k:.1f} '
           f'A{R_CORNER * k},{R_CORNER * k} 0 0 0 {p.px(W) + R_CORNER * k:.1f},{p.py(0):.1f} '
           f'H{p.px(X_STEP):.1f} Z', stroke='none', fill='#d4cfc2')
    # spine plateau rounds
    s.line(p.px(R_SPINE_BACK), p.py(L - R_CORNER), p.px(R_SPINE_BACK), p.py(R_CORNER),
           stroke='#888', sw=0.9, dash='5,3')
    s.line(p.px(X_STEP - R_STEP), p.py(L), p.px(X_STEP - R_STEP), p.py(0), stroke='#888',
           sw=0.9, dash='5,3')
    s.line(p.px(X_STEP), p.py(L), p.px(X_STEP), p.py(0), stroke='#111', sw=1.8)
    s.line(p.px(X_STEP + COVE), p.py(L), p.px(X_STEP + COVE), p.py(0), stroke='#a33', sw=1.0)
    p.outline(fill='none', stroke='#111', sw=2.4)

    # hidden internals, faint
    for key in ('battery', 'hat', 'xiao'):
        x0, x1, y0, y1, _, st, *_ = part(key)
        p.box(x0, x1, y0, y1, stroke=st, sw=1.0, dash='3,3')
    ax0, ax1, ay0, ay1, *_ = part('antenna')
    p.box(ax0, ax1, ay0, ay1, stroke='#7d3cc4', sw=1.0, dash='3,3')
    p.box(ax0 - ANT_KEEPOUT, W, ay0 - ANT_KEEPOUT, L, stroke='#7d3cc4', sw=1.0, dash='2,4')

    # grip pad zone + HAT bump + spine screws
    gx0, gx1, gy0, gy1 = GRIP_PAD
    p.box(gx0, gx1, gy0, gy1, stroke='#2d6a8a', fill='#cfe6f2', sw=1.4, op=0.6, rx=2 * k)
    bx0, bx1, by0, by1, bh = HAT_BUMP
    p.box(bx0, bx1, by0, by1, stroke='#d98a00', fill='url(#hatch)', sw=1.8, rx=2 * k)
    for hx, hy in HAT_HOLES:
        p.dot(hx, hy, HAT_HOLE_D, stroke='#2d6a8a', fill='#fff', sw=1.3)

    # stowed cover
    cx0, cx1, cy0, cy1, ct = COVER
    s.rect(p.px(cx1), p.py(cy1), (cx1 - cx0) * k, (cy1 - cy0) * k, rx=R_CORNER * k,
           stroke='#0a5', sw=2.0, dash='9,4')

    # USB-C on top
    s.rect(p.px(USBC[1]), p.py(L) - 7, (USBC[1] - USBC[0]) * k, 9, rx=4, stroke='#222',
           fill='#555', sw=1.0)

    # in-drawing labels
    s.text(p.px(70), p.py(75), 'STOWING RECESS', size=15, fill='#555', anchor='middle',
           weight='bold')
    s.text(p.px(70), p.py(75) + 18, 'floor Z 2.2 (screen back wall 1.0)', size=10, fill='#555',
           anchor='middle')
    s.text(p.px(70), p.py(75) + 32, f'X {X_STEP}-{W}, open at the far edge', size=9.5,
           fill='#555', anchor='middle')
    s.text(p.px(18), p.py(120), 'SPINE', size=13, fill='#333', anchor='middle', weight='bold')
    s.text(p.px(18), p.py(120) + 14, 'plateau Z 0', size=9.5, fill='#333', anchor='middle')
    s.text(p.px(18), p.py(72), 'HAT bump', size=10, fill='#a36400', anchor='middle',
           weight='bold')
    s.text(p.px(18), p.py(72) + 12, f'{bh} proud', size=9, fill='#a36400', anchor='middle')

    # callouts (right = spine side)
    rx = ox + W * k + 30
    p.callout(bx0, 60, rx, p.py(66),
              ['HAT bump X 9-27, Y 52-92', f'{bh} proud of the back (Z -{bh})',
               'over the HAT underside parts', '(inductor 1.5 below PCB)'], color='#a36400')
    p.callout(gx0, 105, rx, p.py(112),
              ['grip pad zone Y 30-110', 'X 4.0-32.0 (between the rounds)',
               '0.6-0.8 TPU/silicone, flush recess', 'hides the M2.5 spine screws'],
              color='#2d6a8a')
    p.callout(HAT_HOLES[0][0], HAT_HOLES[0][1], rx, p.py(30),
              ['4 x M2.5 through HAT holes', 'Ø3 at 23 x 58', 'X 5.15/28.15, Y 41.75/99.75'],
              color='#2d6a8a')
    p.callout(R_SPINE_BACK, 132, rx, p.py(136),
              ['spine outer back edge R4', '(tangent line dashed)'], color='#666')
    p.callout(X_STEP - R_STEP, 20, rx, p.py(14),
              ['step: convex R1.3 at X 32.0-33.3', 'step face X 33.3, Z 0 -> 2.2'], color='#333')

    # callouts (left = recess side)
    tx = ox - 22
    p.callout(X_STEP + COVE, 120, tx, p.py(124),
              ['cove line X 33.9', f'concave R{COVE} (CAD)', 'seats the cover edge'],
              color='#a33', anchor='end')
    p.callout(cx1, 40, tx, p.py(44),
              ['stowed cover (dashed)', f'X {cx0}-{cx1}, full length', f'{ct} thick: Z 0.2-2.2',
               f'magnets {MAGNET[0]:g}x{MAGNET[1]:g}, 4 pairs', '(positions TBD)'],
              color='#0a5', anchor='end')
    p.callout(ax1 - 5, 128, tx, p.py(134),
              ['antenna (inside) +', '10 mm magnet keep-out'], color='#7d3cc4', anchor='end')

    dim_h(s, p.px(W), p.px(0), p.py(0) + 34, f'W {W}', above=False)
    dim_h(s, p.px(X_STEP), p.px(0), p.py(0) + 16, 'spine 33.3', size=9, above=False)
    dim_h(s, p.px(W), p.px(X_STEP), p.py(0) + 16, 'recess 74.4', size=9, above=False)
    dim_v(s, ox - 14, p.py(L), p.py(0), f'L {L}', left=True)

    s.lines(30, p.py(0) + 64, [
        'Depths: spine 9.0 (Z 0-9.0) · screen section 6.8 (Z 2.2-9.0) · step 2.2 = cover 2.0 + '
        '0.2 · closed, the cover lies on the glass and the screen section reads 8.8.',
        'Hidden outlines (dashed): battery, HAT, XIAO inside the spine; antenna sticker on the '
        'inside of the screen back wall.',
    ], size=9.5)
    s.save('back-view')


# ------------------------------------------------------- fig 3: sections
def arc(cx, cz, r, a0, a1, n=10):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


TUB = ([(0, Z_TUB), (0, R_SPINE_BACK)] + arc(R_SPINE_BACK, R_SPINE_BACK, R_SPINE_BACK, 180, 270)
       + [(X_STEP - R_STEP, 0)] + arc(X_STEP - R_STEP, R_STEP, R_STEP, 270, 360)
       + [(X_STEP, Z_RECESS - COVE)] + arc(X_STEP + COVE, Z_RECESS - COVE, COVE, 180, 90)
       + [(W, Z_RECESS), (W, Z_TUB), (W - WALL, Z_TUB), (W - WALL, Z_FLOOR),
          (SPINE_CAV[1], Z_FLOOR), (SPINE_CAV[1], WALL)]
       + arc(R_SPINE_BACK, R_SPINE_BACK, R_SPINE_BACK - WALL, 270, 180)
       + [(WALL, Z_TUB)])

FRONT_L = [(0, Z_TUB), (GLASS[0], Z_TUB), (GLASS[0], GLASS_Z[1]), (WINDOW[0], GLASS_Z[1]),
           (WINDOW[0] - WIN_CHAMFER, T), (FRONT_CHAMFER, T), (0, T - FRONT_CHAMFER)]
FRONT_R = [(W, Z_TUB), (GLASS[1], Z_TUB), (GLASS[1], GLASS_Z[1]), (WINDOW[1], GLASS_Z[1]),
           (WINDOW[1] + WIN_CHAMFER, T), (W - FRONT_CHAMFER, T), (W, T - FRONT_CHAMFER)]


class Sec:
    def __init__(self, s, ox, oz0, kx, kz, zmax):
        self.s, self.ox, self.oz0, self.kx, self.kz, self.zmax = s, ox, oz0, kx, kz, zmax

    def px(self, x):
        return self.ox + x * self.kx

    def pz(self, z):
        return self.oz0 + (self.zmax - z) * self.kz

    def poly(self, pts, **kw):
        d = 'M' + ' L'.join(f'{self.px(x):.1f},{self.pz(z):.1f}' for x, z in pts) + ' Z'
        self.s.path(d, **kw)

    def box(self, x0, x1, z0, z1, **kw):
        self.s.rect(self.px(x0), self.pz(z1), (x1 - x0) * self.kx, (z1 - z0) * self.kz, **kw)

    def note(self, x, z, tx, ty, txt, color='#333', anchor='start'):
        self.s.line(tx + (-3 if anchor == 'start' else 3), ty - 4, self.px(x), self.pz(z),
                    stroke=color, sw=0.7)
        self.s.text(tx, ty, txt, size=9, fill=color, anchor=anchor)


def draw_section(s, ox, oy, y_cut, title, kx=8.0, kz=24.0):
    zmax, zmin = T + 2.6, -1.8
    sec = Sec(s, ox, oy, kx, kz, zmax)
    s.text(ox, oy - 8, title, size=14, weight='bold')
    # Z grid ticks
    for z in (0, Z_RECESS, Z_FLOOR, Z_TUB, T):
        s.line(sec.px(-2), sec.pz(z), sec.px(W + 2), sec.pz(z), stroke='#ddd', sw=0.6)
        s.text(sec.px(-3), sec.pz(z) + 3, f'Z {z:g}', size=8.5, fill='#777', anchor='end')

    button = y_cut == SEC_BUTTON_Y
    case = dict(stroke='#555', fill='#cfcabd', sw=1.2)
    sec.poly(TUB, **case)
    sec.poly(FRONT_L, **case)
    sec.poly(FRONT_R, **case)
    # seam
    s.line(sec.px(0), sec.pz(Z_TUB), sec.px(W), sec.pz(Z_TUB), stroke='#555', sw=0.6, dash='3,2')

    # glass
    sec.box(GLASS[0], GLASS[1], *GLASS_Z, stroke='#4a6fc4', fill='#dbe6fb', sw=1.2)
    # stowed cover (+ ghost of the closed position)
    cx0, cx1, _, _, ct = COVER
    sec.box(cx0, cx1, Z_RECESS - ct, Z_RECESS, stroke='#0a5', fill='#c8ecd6', sw=1.3)
    sec.box(cx0, cx1, T, T + ct, stroke='#0a5', sw=1.0, dash='5,3')

    if button:
        # thinned back wall under the HAT, HAT bare end, back key
        sec.box(part('hat')[0], part('hat')[1], WALL_THIN, WALL, stroke='none', fill=BG)
        z_pcb = WALL_THIN
        sec.box(part('hat')[0], part('hat')[1], z_pcb, z_pcb + HAT_PCB, stroke='#d98a00',
                fill='#fdeacc', sw=1.3)
        z_sw = z_pcb + HAT_PCB + 0.2
        sw0, sw1 = KEY_X - SWITCH[0] / 2, KEY_X + SWITCH[0] / 2
        sec.box(sw0, sw1, z_sw, z_sw + SWITCH_H, stroke='#5a2a99', fill='#e6d7f7', sw=1.2)
        sec.box(KEY_X - 1.55, KEY_X + 1.55, z_sw + SWITCH_H, z_sw + KNOB_H, stroke='#5a2a99',
                fill='#c9a9ee', sw=1.0)
        flange0 = z_sw + KNOB_H + 0.1
        cw = PILL_CAP[0]
        sec.box(KEY_X - cw / 2 - 1.0, KEY_X + cw / 2 + 1.0, flange0, Z_TUB, stroke='#5a2a99',
                fill='#c9a9ee', sw=1.0)
        sec.box(KEY_X - cw / 2 - 0.35, KEY_X + cw / 2 + 0.35, Z_TUB, T, stroke='none', fill=BG)
        sec.box(KEY_X - cw / 2, KEY_X + cw / 2, Z_TUB, T + 0.7, stroke='#5a2a99',
                fill='#c9a9ee', sw=1.0)
        # bump beyond (Y 52-92), dashed
        bx0, bx1, _, _, bh = HAT_BUMP
        sec.box(bx0, bx1, -bh, 0, stroke='#d98a00', sw=1.0, dash='4,3')
    else:
        x0, x1, *_ = part('battery')
        sec.box(x0, x1, WALL, WALL + part('battery')[4], stroke='#1a7a3c', fill='#d9f0e1',
                sw=1.4)
        x0, x1, *_ = part('adapter')
        sec.box(x0, x1, Z_FLOOR, Z_FLOOR + part('adapter')[4], stroke='#7a4a1a',
                fill='#efe0cf', sw=1.3)

    # labels, right margin
    rx = sec.px(W) + 28
    rows = [
        (GLASS[1] + 0.5, T - 0.3, 'front plate 1.2 (Z 7.8-9.0), 0.8 front chamfer', '#555'),
        (WINDOW[1] + 0.4, (GLASS_Z[1] + T) / 2, 'lip 0.8 (Z 8.2-9.0), 45° chamfer', '#555'),
        (GLASS[1] - 2, sum(GLASS_Z) / 2, 'glass 1.06 (Z 7.14-8.2)', '#4a6fc4'),
        (W - 3, Z_TUB - 0.2, 'tub rim / seam Z 7.8', '#555'),
        (W - 3, (Z_RECESS + Z_FLOOR) / 2, 'screen back wall 1.0 (Z 2.2-3.2)', '#555'),
        (W - 3, Z_RECESS - 1.0, 'stowed cover 2.0 (Z 0.2-2.2)', '#0a5'),
        (W - 3, T + 1.0, 'closed cover position (dashed)', '#0a5'),
    ]
    rows.sort(key=lambda r: -r[1])
    for i, (x, z, txt, col) in enumerate(rows):
        sec.note(x, z, rx, oy + 8 + i * 17, txt, col)

    # left-side / in-spine labels
    lx = ox + 20

    def by(i):
        return sec.pz(zmin) + 14 + i * 15
    ly = by(4) + 6
    if button:
        sec.note(KEY_X, T + 0.6, lx + 70, oy + 4, 'BACK key cap ~0.7 proud (indicative)', '#5a2a99')
        sec.note(KEY_X + 3, z_sw + 1.5, sec.px(40), by(0),
                 f'switch 6.0 x 3.6, 4.3 to knob top (Z {z_sw:.1f}-{z_sw + KNOB_H:.1f})',
                 '#5a2a99')
        sec.note(24, z_pcb + 0.8, sec.px(40), by(1),
                 'HAT bare end: PCB 1.7 at Z 0.9-2.6 (+0.2 wire)', '#a36400')
        sec.note(26, WALL_THIN / 2, sec.px(40), by(2),
                 'back wall thinned to 0.9 under the HAT', '#555')
        sec.note(9.5, -0.9, sec.px(40), by(3),
                 'HAT bump beyond the cut (Y 52-92), 1.4 proud', '#a36400')
        stack = (f'stack at the key: 0.9 + 1.7 + 0.2 + 4.3 + 0.1 + 0.6 + 1.2 = '
                 f'{WALL_THIN + HAT_PCB + 0.2 + KNOB_H + 0.1 + 0.6 + FRONT_T:.1f}')
        s.text(lx, ly, stack, size=9.5, fill='#333')
    else:
        sec.note(16.65, WALL + 2.4, sec.px(40), by(0),
                 'battery 4.9 (Z 1.2-6.1), X 1.85-31.45; 1.7 air to front plate', '#1a7a3c')
        sec.note(56, Z_FLOOR + 1.8, sec.px(40), by(1),
                 'FFC adapter 3.6 (Z 3.2-6.8), 0.34 to glass', '#7a4a1a')
        sec.note(3.0, 2.0, sec.px(40), by(2),
                 'spine back R4 + inner R2.8', '#a33')
        s.text(lx, ly, 'screen stack: 1.0 wall + 3.6 adapter + 0.3 + 1.06 glass + 0.8 lip '
                       '= 6.76 (6.8 deep)', size=9.5, fill='#333')
    s.text(lx, ly + 15, 'WARNING: the HAT (X 1.4) and battery (X 1.85) edges overlap the spine '
                        "back R4 / inner R2.8 round: the shell can't be both rounded and this full.",
           size=9.5, fill='#a33', weight='bold')
    # X dims
    dy = ly + 36
    dim_h(s, sec.px(0), sec.px(X_STEP), dy, 'spine 33.3', size=9, above=False)
    dim_h(s, sec.px(X_STEP), sec.px(W), dy, f'screen section {W - X_STEP:.1f}', size=9,
          above=False)
    return dy + 30


def fig_section():
    s = Svg(1340, 1150)
    s.text(30, 38, 'esp-read — cross-sections across the width (X)', size=21, weight='bold')
    s.text(30, 58, 'X at 8 px/mm · Z exaggerated 3x (24 px/mm) · front face at the top, '
                   'back at the bottom · spine on the LEFT (as the front view)',
           size=10, fill='#555')
    y = draw_section(s, 90, 110, SEC_BUTTON_Y,
                     f'Section A-A at Y {SEC_BUTTON_Y:g} — button band (back key, HAT bare end)')
    draw_section(s, 90, y + 70, SEC_BATTERY_Y,
                 f'Section B-B at Y {SEC_BATTERY_Y:g} — through the battery and FFC adapter '
                 '(Y~20; 22 so the cut is inside the window, which starts at 20.25)')
    s.save('section')


if __name__ == '__main__':
    fig_component_layout()
    fig_back_view()
    fig_section()
