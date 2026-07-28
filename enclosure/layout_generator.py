#!/usr/bin/env python3
"""Enclosure layout drawings for esp-read — regenerates the PNGs in this dir.

Emits SVG (no third-party deps) and rasterises with `rsvg-convert`
(`brew install librsvg`). Everything is driven by the PARTS dimensions below, so
a hardware change means editing one dict and re-running:

    python3 layout_generator.py

Figures:
  component-layout.png   plan (portrait, to scale) + depth (Z) stack
  option-b-layout.png    plan + longitudinal section A-A
  curved-back-concept.png  centre cross-section, wedge/curve concept

Source of truth for the numbers: CLAUDE.md section "Mechanical / enclosure" and
docs/bring-up-and-assembly.md Phase 5.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SCALE = 6.0          # px per mm, geometry
BG = '#f5f5f5'

# ---------------------------------------------------------------- dimensions
GLASS_W, GLASS_H, GLASS_T = 71.19, 126.38, 0.795   # portrait
ACTIVE_W, ACTIVE_H = 62.65, 110.59

PARTS = {
    # name:            (w,     h,     thickness, stroke,     fill)
    'hat':             (65.0,  30.5,  1.6,  '#d98a00', '#fdeacc'),
    'battery':         (35.0,  30.0,  5.0,  '#1a7a3c', '#d9f0e1'),
    'logic':           (66.0,  43.0,  1.2,  '#2255cc', '#dde7fb'),   # 26 x 17 holes
    'xiao':            (17.5,  21.0,  4.7,  '#cc2222', '#fbdcdc'),   # incl USB-C
}
NOTCH_W, NOTCH_D = 18.0, 21.5      # 7 x 8.5 holes, cut in from the board edge
WALL_FRONT, WALL_BACK, AIR_GAP = 1.5, 1.5, 1.0

# portrait plan placement (x,y of top-left, mm, origin = glass top-left)
PLACE = {}


def _layout():
    """Stack HAT / battery / logic board down the portrait glass, centred."""
    hat_w, hat_h, *_ = PARTS['hat']
    bat_w, bat_h, *_ = PARTS['battery']
    log_w, log_h, *_ = PARTS['logic']
    margin_top = 6.0
    gap = (GLASS_H - margin_top - hat_h - bat_h - log_h - 6.0) / 2.0
    y = margin_top
    PLACE['hat'] = ((GLASS_W - hat_w) / 2, y)
    y += hat_h + gap
    PLACE['battery'] = ((GLASS_W - bat_w) / 2, y)
    y += bat_h + gap
    PLACE['logic'] = ((GLASS_W - log_w) / 2, y)
    # XIAO sits in a notch cut into the logic board's bottom edge, centred
    lx, ly = PLACE['logic']
    PLACE['xiao'] = (lx + (log_w - PARTS['xiao'][0]) / 2, ly + log_h - PARTS['xiao'][1])
    return gap


VGAP = _layout()

# ------------------------------------------------------------------ svg bits
class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, stroke='#333', fill='none', sw=1.4, dash=None, rx=0):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                 f'rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def path(self, d, stroke='#333', fill='none', sw=1.4, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da}/>')

    def line(self, x1, y1, x2, y2, stroke='#333', sw=1.0, dash=None):
        da = f' stroke-dasharray="{dash}"' if dash else ''
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{da}/>')

    def text(self, x, y, s, size=11, fill='#222', anchor='start', weight='normal',
             style='normal'):
        s = (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="Helvetica,Arial,sans-serif" '
                 f'font-size="{size}" font-weight="{weight}" font-style="{style}" '
                 f'fill="{fill}" text-anchor="{anchor}">{s}</text>')

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
            sys.exit(f'rsvg-convert failed ({e}) — brew install librsvg')
        out_svg.unlink()
        print(f'wrote {out_png.name}  ({self.w}x{self.h})')


def notch_path(x, y, w, h, nw, nd):
    """Logic-board outline with a U notch cut into the bottom edge (px, centred)."""
    nx = x + (w - nw) / 2
    return (f'M{x:.1f},{y:.1f} H{x+w:.1f} V{y+h:.1f} H{nx+nw:.1f} '
            f'V{y+h-nd:.1f} H{nx:.1f} V{y+h:.1f} H{x:.1f} Z')


PITCH = 2.54


def draw_notch_detail(s, ox, oy, ds=4.6):
    """Zoomed view of the notch: 2.54 grid, surviving landing pads, XIAO, stub legs."""
    cols, rows = 12, 11
    board_w, board_h = (cols - 1) * PITCH, (rows - 1) * PITCH
    nx0 = (board_w - NOTCH_W) / 2          # notch left, mm from board left
    ny0 = board_h - NOTCH_D                 # notch top, mm from board top
    lstroke, lfill = PARTS['logic'][3], PARTS['logic'][4]

    s.text(ox, oy - 26, 'Notch detail (zoomed ~4.6 px/mm)', size=13, weight='bold')
    s.text(ox, oy - 11, 'open to the board edge — two straight cuts, both score-and-snappable',
           size=9, fill='#555')

    # board area minus notch
    x, y = ox, oy
    s.path(notch_path(x, y, board_w * ds, board_h * ds, NOTCH_W * ds, NOTCH_D * ds),
           stroke=lstroke, fill=lfill, sw=1.6)

    # pads on the 2.54 grid, skipping any that fall in the notch
    for i in range(cols):
        for j in range(rows):
            mx, my = i * PITCH, j * PITCH
            if nx0 - 0.6 < mx < nx0 + NOTCH_W + 0.6 and my > ny0 - 0.6:
                continue
            cx, cy = x + mx * ds, y + my * ds
            s.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.5" fill="none" '
                  f'stroke="#8fa8d8" stroke-width="1.0"/>')

    # the two landing-pad columns either side of the notch
    for side in (-1, 1):
        mx = nx0 - PITCH if side < 0 else nx0 + NOTCH_W + PITCH
        for j in range(rows):
            my = j * PITCH
            if my <= ny0 - 0.6:
                continue
            cx, cy = x + mx * ds, y + my * ds
            s.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.4" fill="#fff" '
                  f'stroke="{lstroke}" stroke-width="1.7"/>')

    # XIAO in the notch (0.25 mm clearance each side)
    xw, xh, _, xs, xf = PARTS['xiao']
    xx = x + (nx0 + (NOTCH_W - xw) / 2) * ds
    xy = y + (ny0 + (NOTCH_D - xh)) * ds
    s.rect(xx, xy, xw * ds, xh * ds, stroke=xs, fill=xf, sw=1.7)
    s.text(xx + xw * ds / 2, xy + xh * ds / 2, 'XIAO', size=10, fill=xs,
           anchor='middle', weight='bold')
    s.text(xx + xw * ds / 2, xy + xh * ds / 2 + 12, '17.5 x 21', size=8, fill=xs,
           anchor='middle')

    # stub legs: XIAO pad row -> facing protoboard pad
    for side in (-1, 1):
        for k in range(7):
            my = ny0 + 2.0 + k * PITCH
            if my > board_h:
                break
            ly_ = y + my * ds
            if side < 0:
                s.line(xx, ly_, x + (nx0 - PITCH) * ds, ly_, stroke='#c22', sw=1.5)
            else:
                s.line(xx + xw * ds, ly_, x + (nx0 + NOTCH_W + PITCH) * ds, ly_,
                       stroke='#c22', sw=1.5)
    s.text(x + board_w * ds + 14, y + (ny0 + 4) * ds, 'stub legs', size=9, fill='#c22')
    s.text(x + board_w * ds + 14, y + (ny0 + 4) * ds + 12, '26 AWG, bent 90°', size=8.5, fill='#c22')
    s.text(x + board_w * ds + 14, y + (ny0 + 4) * ds + 24, 'into landing pads', size=8.5, fill='#c22')

    # notch dimension arrows
    s.line(x + nx0 * ds, y + board_h * ds + 12, x + (nx0 + NOTCH_W) * ds,
           y + board_h * ds + 12, stroke='#333', sw=1.0)
    s.text(x + (nx0 + NOTCH_W / 2) * ds, y + board_h * ds + 26, '18.0 mm (7 holes)',
           size=9, anchor='middle')
    s.line(x - 12, y + ny0 * ds, x - 12, y + board_h * ds, stroke='#333', sw=1.0)
    s.text(x - 16, y + (ny0 + NOTCH_D / 2) * ds, '21.5', size=9, anchor='end')
    s.text(x - 16, y + (ny0 + NOTCH_D / 2) * ds + 11, 'mm', size=9, anchor='end')
    s.text(ox, y + board_h * ds + 48,
           'USB-C exits here, through the open end of the notch ->', size=9, fill='#d98a00')


def draw_plan(s, ox, oy, buttons=True, labels=True):
    """Portrait plan of the glass with all parts, to scale."""
    gw, gh = GLASS_W * SCALE, GLASS_H * SCALE
    s.rect(ox, oy, gw, gh, stroke='#111', fill='#ffffff', sw=2.4)
    # active area
    ax = ox + (GLASS_W - ACTIVE_W) / 2 * SCALE
    ay = oy + (GLASS_H - ACTIVE_H) / 2 * SCALE
    s.rect(ax, ay, ACTIVE_W * SCALE, ACTIVE_H * SCALE, stroke='#bbb', dash='5,4', sw=1.0)

    for key in ('hat', 'battery', 'logic'):
        w, h, _, stroke, fill = PARTS[key]
        px, py = PLACE[key]
        x, y = ox + px * SCALE, oy + py * SCALE
        if key == 'logic':
            s.path(notch_path(x, y, w * SCALE, h * SCALE, NOTCH_W * SCALE, NOTCH_D * SCALE),
                   stroke=stroke, fill=fill, sw=1.6)
        else:
            s.rect(x, y, w * SCALE, h * SCALE, stroke=stroke, fill=fill, sw=1.6)
        if labels:
            name = {'hat': 'Driver HAT', 'battery': 'Battery', 'logic': 'Logic board'}[key]
            cx, cy = x + w * SCALE / 2, y + h * SCALE / 2
            # logic board: label in the free strip above the notch
            dy = -(NOTCH_D * SCALE) / 2 - 4 if key == 'logic' else 0
            s.text(cx, cy + dy, name, size=13, fill=stroke, anchor='middle', weight='bold')
            dim = {'hat': '65 x 30.5', 'battery': '35 x 30 x 5',
                   'logic': '66 x 43  (26 x 17 holes)'}[key]
            s.text(cx, cy + dy + 14, dim, size=9.5, fill=stroke, anchor='middle')

    # notch outline, so the cut reads as a cut
    lw, lh, _, lstroke, _ = PARTS['logic']
    lx, ly = PLACE['logic']
    nx = ox + (lx + (lw - NOTCH_W) / 2) * SCALE
    ny = oy + (ly + lh - NOTCH_D) * SCALE
    s.rect(nx, ny, NOTCH_W * SCALE, NOTCH_D * SCALE, stroke=lstroke, fill='none',
           sw=1.0, dash='4,3')

    # XIAO in the notch
    w, h, _, stroke, fill = PARTS['xiao']
    px, py = PLACE['xiao']
    x, y = ox + px * SCALE, oy + py * SCALE
    s.rect(x, y, w * SCALE, h * SCALE, stroke=stroke, fill=fill, sw=1.6)
    if labels:
        s.text(x + w * SCALE / 2, y + h * SCALE / 2 - 3, 'XIAO', size=11,
               fill=stroke, anchor='middle', weight='bold')
        s.text(x + w * SCALE / 2, y + h * SCALE / 2 + 10, 'in notch', size=8.5,
               fill=stroke, anchor='middle')
        s.text(nx + NOTCH_W * SCALE + 8, ny + 12, 'notch 18 x 21.5', size=9, fill=lstroke)
        s.text(nx + NOTCH_W * SCALE + 8, ny + 24, '(7 x 8.5 holes,', size=9, fill=lstroke)
        s.text(nx + NOTCH_W * SCALE + 8, ny + 36, 'open to the edge)', size=9, fill=lstroke)

    # USB-C out the bottom
    ux = x + w * SCALE / 2
    s.rect(ux - 27, oy + gh - 5, 54, 13, stroke='#444', fill='#666', sw=1.0)
    s.text(ux + 36, oy + gh + 18, 'USB-C', size=9.5, fill='#444')

    # FPC to HAT
    hx, hy = PLACE['hat']
    s.line(ox + gw / 2, oy - 12, ox + gw / 2, oy + hy * SCALE, stroke='#d98a00',
           sw=1.2, dash='4,3')
    s.text(ox + gw / 2 + 6, oy - 4, 'FPC -> HAT (edge TBC)', size=9, fill='#d98a00')

    if buttons:
        bx = ox + gw
        for i, (lbl, pin) in enumerate((('Fwd', 'D4'), ('Back', 'D5'), ('Menu', 'D11*'))):
            by = oy + gh * 0.42 + i * 34
            s.rect(bx + 10, by, 15, 15, stroke='#7d3cc4', fill='#efe2fb', sw=1.2, rx=2)
            s.text(bx + 32, by + 8, lbl, size=9.5, fill='#7d3cc4', weight='bold')
            s.text(bx + 32, by + 18, pin, size=8.5, fill='#7d3cc4')
        s.text(bx + 10, oy + gh * 0.42 - 8, 'side-edge buttons', size=9, fill='#7d3cc4')
    return gw, gh


# ------------------------------------------------------- fig 1: component layout
def fig_component_layout():
    W, H = 1010, 960
    s = Svg(W, H)
    s.text(30, 40, 'esp-read — component layout & Z-stack (to scale)', size=21, weight='bold')
    s.text(30, 60, 'portrait · 6 px/mm · grey dashed = active display area · '
                   'XIAO in-plane in an edge notch (decided 2026-07-28)', size=10.5, fill='#555')

    gw, gh = draw_plan(s, 60, 90)
    s.text(60, 90 + gh + 26, f'display glass {GLASS_W} x {GLASS_H} mm', size=12, weight='bold')
    s.text(60, 90 + gh + 44, 'vertical budget: 30.5 + 30 + 43 = 103.5 mm of parts + gaps '
                             f'(~{VGAP:.0f} mm each) inside 126.38 mm — fits portrait only.',
           size=9.5, fill='#555')
    s.text(60, 90 + gh + 58, 'A landscape / 2-row arrangement no longer fits: HAT 30.5 + '
                             'logic 43 = 73.5 > 71.19 mm glass width.', size=9.5, fill='#a33')
    s.text(60, 90 + gh + 72, '*D11 menu = wire soldered direct to a XIAO castellation pad, '
                             'before the XIAO is seated.', size=9.5, fill='#7d3cc4')

    # ---- Z stack column, depth exaggerated
    zx, zy, zw, ex = 610, 130, 250, 26.0     # ex = px per mm of depth
    s.text(zx, zy - 34, 'Depth (Z) stack', size=15, weight='bold')
    s.text(zx, zy - 18, f'depth exaggerated {ex/SCALE:.1f}x for legibility', size=9.5, fill='#555')
    layers = [
        ('case front wall 1.5', WALL_FRONT, '#888', '#d5d5d5'),
        ('glass 0.795', GLASS_T, '#4a6fc4', '#dbe6fb'),
        ('air gap 1.0', AIR_GAP, '#bbb', BG),
        ('battery 5.0 — TALLEST ITEM', PARTS['battery'][2],
         PARTS['battery'][3], PARTS['battery'][4]),
        ('case back wall 1.5', WALL_BACK, '#888', '#d5d5d5'),
    ]
    y = zy
    for name, t, stroke, fill in layers:
        h = t * ex
        s.rect(zx, y, zw, h, stroke=stroke, fill=fill, sw=1.3)
        s.text(zx + 8, y + h / 2 + 4, name, size=10,
               fill=stroke if stroke != '#bbb' else '#777')
        y += h
    total = WALL_FRONT + GLASS_T + AIR_GAP + PARTS['battery'][2] + WALL_BACK
    s.line(zx + zw + 16, zy, zx + zw + 16, y, stroke='#111', sw=1.6)
    s.line(zx + zw + 11, zy, zx + zw + 21, zy, stroke='#111', sw=1.6)
    s.line(zx + zw + 11, y, zx + zw + 21, y, stroke='#111', sw=1.6)
    s.text(zx + zw + 26, (zy + y) / 2 + 4, f'= {total:.1f} mm', size=13, weight='bold')

    # in-plane comparison
    cy = y + 46
    s.text(zx, cy, 'The XIAO no longer sets the floor:', size=11, weight='bold')
    rows = [
        ('XIAO in-plane in notch (chosen)', 4.7, '#1a7a3c'),
        ('XIAO stacked on 1.2 mm board', 5.9, '#a33'),
        ('XIAO on 7-pin sockets — never', 13.2, '#a33'),
    ]
    for i, (lbl, v, col) in enumerate(rows):
        ry = cy + 20 + i * 26
        s.rect(zx, ry, v * 8.5, 13, stroke=col, fill=PARTS['xiao'][4], sw=1.2)
        s.text(zx + v * 8.5 + 8, ry + 11, f'{v} mm', size=9.5, fill=col, weight='bold')
        s.text(zx, ry + 24, lbl, size=9, fill=col)
    ty = cy + 20 + 3 * 26 + 14
    for i, ln in enumerate((
            'In-plane saves exactly the board thickness (1.2 mm), and drops the',
            'XIAO below the 5.0 mm battery — so the CELL is now the Z constraint.')):
        s.text(zx, ty + i * 14, ln, size=9.5, fill='#555')
    for i, ln in enumerate((
            'Keep back-side wiring flat (30 AWG Kynar, leads trimmed flush):',
            '~1 mm of wire loom would cancel the whole saving.')):
        s.text(zx, ty + 34 + i * 14, ln, size=9.5, fill='#a33')

    draw_notch_detail(s, zx + 34, ty + 108)
    s.save('component-layout')


# --------------------------------------------------- fig 2: option B plan+section
def fig_option_b():
    W, H = 1080, 985
    s = Svg(W, H)
    s.text(30, 38, 'Option B layout — plan + longitudinal section (portrait, to scale)',
           size=19, weight='bold')
    s.text(30, 57, 'battery centred for balance · XIAO in an edge notch, USB-C out the bottom · '
                   'wedge back: thick lower two-thirds, thin top', size=10, fill='#555')

    ox, oy = 55, 95
    s.text(ox, oy - 8, 'plan', size=11, weight='bold')
    gw, gh = draw_plan(s, ox, oy, buttons=True, labels=True)
    # section cut line
    s.line(ox + gw / 2, oy - 16, ox + gw / 2, oy + gh + 16, stroke='#a33', sw=1.4, dash='7,4')
    s.text(ox + gw / 2 - 4, oy - 20, 'A', size=11, fill='#a33', weight='bold', anchor='end')
    s.text(ox + gw / 2 - 4, oy + gh + 30, 'A', size=11, fill='#a33', weight='bold', anchor='end')

    # ---- section A-A: length down the page to match the plan, depth across, x3
    sx = 660
    dz = 3.0 * SCALE                          # px per mm of depth (3x exaggeration)
    s.text(sx, oy - 8, 'section A-A  (front left | back right · depth x3)', size=11, weight='bold')
    top = oy
    # front wall + glass slab, full length
    s.rect(sx, top, WALL_FRONT * dz, gh, stroke='#888', fill='#d5d5d5', sw=1.2)
    s.rect(sx + WALL_FRONT * dz, top, GLASS_T * dz, gh, stroke='#4a6fc4', fill='#dbe6fb', sw=1.2)
    inner = sx + (WALL_FRONT + GLASS_T + AIR_GAP) * dz

    thin, thick = 5.0, 9.8
    # wedge back profile: thin at the top edge, thick across the lower two thirds
    y_taper0 = top + gh * 0.22
    y_taper1 = top + gh * 0.40
    back_thin = sx + thin * dz
    back_thick = sx + thick * dz
    s.path(f'M{sx:.1f},{top:.1f} H{back_thin:.1f} V{y_taper0:.1f} '
           f'L{back_thick:.1f},{y_taper1:.1f} V{top+gh:.1f} H{sx:.1f} Z',
           stroke='#111', fill='none', sw=2.2)

    for key, lbl in (('hat', 'HAT 1.6'), ('battery', 'battery 5.0'), ('xiao', 'XIAO 4.7')):
        w, h, t, stroke, fill = PARTS[key]
        _, py = PLACE[key]
        y = top + py * SCALE
        ht = (PARTS['logic'][1] if key == 'logic' else h) * SCALE
        s.rect(inner, y, t * dz, ht, stroke=stroke, fill=fill, sw=1.5)
        s.text(sx + thick * dz + 40, y + ht / 2, lbl, size=10, fill=stroke)
    # logic board, in-plane beside the XIAO (drawn as a thin slab at the same depth)
    w, h, t, stroke, fill = PARTS['logic']
    _, py = PLACE['logic']
    s.rect(inner, top + py * SCALE, t * dz, (h - PARTS['xiao'][1]) * SCALE,
           stroke=stroke, fill=fill, sw=1.5)
    s.text(sx + thick * dz + 40, top + py * SCALE + 10, 'logic board 1.2', size=10, fill=stroke)

    s.line(back_thin + 6, top + 4, back_thin + 26, top + 4, stroke='#111', sw=1.0)
    s.text(back_thin + 30, top + 8, f'~{thin:.0f} (thin top)', size=9.5)
    s.line(back_thick + 6, top + gh - 8, back_thick + 26, top + gh - 8, stroke='#111', sw=1.0)
    s.text(back_thick + 30, top + gh - 4, f'~{thick:.1f} (grip)', size=9.5)

    fy = oy + gh + 56
    for i, ln in enumerate((
            'Interior flat (parts on bosses), exterior wedge · battery + boards tile in-plane '
            'in portrait (no Z-stacking) · buttons on a side edge.',
            'The enclosure floor carries a boss/shelf under the notch so the XIAO rests on the '
            'case — its 14 wires are electrical, not structural.',
            'Depth is now set by the 5.0 mm battery, not the electronics: thin top ~5 mm over '
            'the HAT, ~9.8 mm across the battery/XIAO grip zone.')):
        s.text(30, fy + i * 15, ln, size=9.5, fill='#555')
    s.save('option-b-layout')


# ------------------------------------------------ fig 3: curved-back concept
def fig_curved_back():
    W, H = 900, 530
    s = Svg(W, H)
    s.text(30, 38, 'Curved-back concept — cross-section through the centre (A-A)',
           size=19, weight='bold')
    s.text(30, 57, 'thick centre houses the battery / XIAO stack · edges taper to the thin '
                   'HAT/FPC end · exterior curved, interior flat bosses', size=10, fill='#555')

    # cross-section: length across, depth down, depth exaggerated
    ox, oy = 95, 250
    L = 480.0
    dz = 14.0
    s.rect(ox, oy - 22, L, GLASS_T * dz * 1.6, stroke='#4a6fc4', fill='#dbe6fb', sw=1.2)
    s.text(ox + 8, oy - 4, 'glass 0.795 + front bezel', size=9.5, fill='#4a6fc4')
    s.line(ox, oy + 6, ox + L, oy + 6, stroke='#bbb', sw=1.0, dash='5,4')

    thin, thick = 5.0, 9.8
    # quadratic apex sits at 0.5*edge + 0.5*control, so solve the control for a true
    # 9.8 mm centre depth rather than eyeballing it
    y_edge = oy + thin * dz
    y_apex = oy + thick * dz
    y_ctrl = 2 * y_apex - y_edge
    s.path(f'M{ox:.1f},{oy-22:.1f} V{y_edge:.1f} '
           f'Q{ox+L/2:.1f},{y_ctrl:.1f} {ox+L:.1f},{y_edge:.1f} '
           f'V{oy-22:.1f}', stroke='#111', fill='none', sw=2.4)
    s.line(ox + L / 2, oy + 6, ox + L / 2, y_apex, stroke='#111', sw=1.0, dash='4,3')

    # parts in the cut
    hb = PARTS['hat']
    s.rect(ox + 20, oy + 8, 100, hb[2] * dz, stroke=hb[3], fill=hb[4], sw=1.4)
    s.text(ox + 24, oy + 8 + hb[2] * dz + 14, 'HAT/FPC 1.6 (thin edge)', size=9.5, fill=hb[3])

    bb = PARTS['battery']
    s.rect(ox + 175, oy + 10, 150, bb[2] * dz, stroke=bb[3], fill=bb[4], sw=1.6)
    s.text(ox + 250, oy + 10 + bb[2] * dz / 2, 'battery 5.0 (tallest)', size=10.5,
           fill=bb[3], anchor='middle', weight='bold')

    xb = PARTS['xiao']
    s.rect(ox + 355, oy + 10, 90, xb[2] * dz, stroke=xb[3], fill=xb[4], sw=1.6)
    s.text(ox + 400, oy + 10 + xb[2] * dz / 2 - 4, 'XIAO 4.7', size=10, fill=xb[3],
           anchor='middle', weight='bold')
    s.text(ox + 400, oy + 10 + xb[2] * dz / 2 + 10, 'in-plane', size=8.5, fill=xb[3],
           anchor='middle')

    s.text(ox + L / 2, y_apex + 20, f'~{thick:.1f} mm centre (set by the 5.0 mm cell)',
           size=12, weight='bold', anchor='middle')
    s.text(ox - 10, y_edge + 4, f'~{thin:.0f} mm edge', size=9.5, anchor='end')

    # schematic plan inset
    px, py, k = 650, 110, 1.55
    s.text(px, py - 14, 'plan (schematic, portrait)', size=10, weight='bold')
    s.rect(px, py, GLASS_W * k, GLASS_H * k, stroke='#111', fill='#fff', sw=1.8, rx=6)
    for key, lbl in (('hat', 'HAT'), ('battery', 'batt'), ('logic', 'board')):
        w, h, _, stroke, fill = PARTS[key]
        qx, qy = PLACE[key]
        s.rect(px + qx * k, py + qy * k, w * k, h * k, stroke=stroke, fill=fill, sw=1.2, rx=2)
        s.text(px + (qx + w / 2) * k, py + (qy + h / 2) * k + 4, lbl, size=9,
               fill=stroke, anchor='middle')
    qx, qy = PLACE['xiao']
    s.rect(px + qx * k, py + qy * k, PARTS['xiao'][0] * k, PARTS['xiao'][1] * k,
           stroke=PARTS['xiao'][3], fill=PARTS['xiao'][4], sw=1.2)
    cy = py + GLASS_H * k * 0.5
    s.line(px - 26, cy, px + GLASS_W * k + 26, cy, stroke='#a33', sw=1.3, dash='6,4')
    s.text(px - 30, cy + 4, 'A', size=10, fill='#a33', weight='bold', anchor='end')
    s.text(px + GLASS_W * k + 34, cy + 4, 'A', size=10, fill='#a33', weight='bold')
    s.text(px, py + GLASS_H * k + 20, 'USB-C exits the bottom edge via the notch —', size=9,
           fill='#d98a00')
    s.text(px, py + GLASS_H * k + 33, 'no USB-C extension needed.', size=9, fill='#d98a00')

    s.text(30, H - 44, 'Concept only — the decided form is the wedge (see option-b-layout.png); '
                       'this shows the curved variant of the same in-plane arrangement.',
           size=9.5, fill='#555')
    s.text(30, H - 26, 'With the XIAO in-plane the battery is the tallest item, so the centre '
                       'thickness is set by the cell, not the electronics.', size=9.5, fill='#555')
    s.save('curved-back-concept')


if __name__ == '__main__':
    fig_component_layout()
    fig_option_b()
    fig_curved_back()
