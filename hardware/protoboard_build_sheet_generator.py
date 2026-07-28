#!/usr/bin/env python3
"""
Protoboard build-sheet generator — DIY E-Ink E-Reader.

Target board: a PLAIN double-sided 2.54 mm through-hole prototyping PCB, cut to
26 x 17 holes (~66 x 43 mm), with an EDGE NOTCH so the XIAO ESP32-S3 Plus sits
IN-PLANE with the board (Z budget — see docs/bring-up-and-assembly.md Phase 5).

Replaces protomate_build_sheet_generator.py. The difference that drives every
design choice here:

    EVERY HOLE IS AN ISOLATED PLATED PAD. There is no continuity anywhere.

So there are no "strips" or "buses" to land on — a net exists only because we
put a conductor there. Three mechanisms, in order of preference:

  * BUS   — bare tinned copper wire threaded along one hole row, soldered at
            every hole it passes. This is how we deliberately recreate the
            rails (GND, 3V3) and the shared-SPI fan-outs.
  * WIRE  — insulated 30 AWG Kynar, point to point.
  * PART  — a component's own legs bridging two holes (dividers, bulk cap).

The XIAO is NOT on the grid: it sits in the notch and connects via 14 STUB LEGS
(short solid 26 AWG wires soldered into its pads, bent 90 deg, soldered into the
facing landing pads in col I and col Q).

COORDINATES: cols A..Z (1..26) left to right, rows 1..17 top to bottom. Holes are
written HYPHENATED (`G-14`) so they can never be confused with net names like
`D10`. The notch removes cols J..P, rows 10..17.

Run: python3 protoboard_build_sheet_generator.py   (needs reportlab)
The validator is warn-only: it prints findings and still writes the PDF.
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm

OUTPUT = 'protoboard_build.pdf'
W, H = A4

# ═════════════════════════════════════════════════════════════════════════════
# BOARD GEOMETRY
# ═════════════════════════════════════════════════════════════════════════════
GRID_COLS, GRID_ROWS = 26, 17            # 66.0 x 43.2 mm at 2.54 pitch
NOTCH_COLS = range(10, 17)               # J..P
NOTCH_ROWS = range(10, 18)               # 10..17 (open to the bottom edge)

# XIAO landing pads: the surviving columns either side of the notch
SIDE_A_COL, SIDE_B_COL = 9, 17           # I and Q
PAD_ROWS = range(11, 18)                 # 7 pads per side

# ── XIAO pad order. Taken from the validated 14-pad sequence in CLAUDE.md /
#    hardware/README.md, split into the two 7-pin rows.
#    label, gpio, function
SIDE_A = [
    ('GND', '—',      'Ground'),
    ('5V',  '—',      'VBUS (dead on battery; VBUS-sense tap)'),
    ('3V3', '—',      'Peripheral power'),
    ('D0',  'GPIO1',  'E-paper CS'),
    ('D1',  'GPIO2',  'E-paper DC'),
    ('D2',  'GPIO3',  'SPARE (strapping pin; ADC1 — VBUS-sense fallback)'),
    ('D3',  'GPIO4',  'E-paper RST'),
]
SIDE_B = [
    ('D9',  'GPIO8',  'SPI MISO (SD)'),
    ('D8',  'GPIO7',  'SPI SCK (shared)'),
    ('D10', 'GPIO9',  'SPI MOSI/DIN (shared)'),
    ('D7',  'GPIO44', 'SD CS'),
    ('D6',  'GPIO43', 'E-paper BUSY'),
    ('D4',  'GPIO5',  'Button: page fwd / wake'),
    ('D5',  'GPIO6',  'Button: page back'),
]
# ⚠ UNVERIFIED: which physical side is A vs B, and whether side B runs in the
# same top->bottom direction. Dry-fit and check against the silk before cutting
# (Phase 0). Flip these if wrong — nothing else in the file needs changing.
FLIP_SIDE_A = False
FLIP_SIDE_B = False

PAD_HOLE = {}          # net label -> (col,row) landing pad
PAD_AT = {}            # (col,row) -> (label,gpio,function)
for _side, _col, _flip in ((SIDE_A, SIDE_A_COL, FLIP_SIDE_A),
                           (SIDE_B, SIDE_B_COL, FLIP_SIDE_B)):
    _seq = list(reversed(_side)) if _flip else list(_side)
    for _i, (_lbl, _gpio, _fn) in enumerate(_seq):
        _hole = (_col, list(PAD_ROWS)[_i])
        PAD_HOLE[_lbl] = _hole
        PAD_AT[_hole] = (_lbl, _gpio, _fn)


def hole(s):
    """'G-14' -> (7, 14)."""
    col, row = s.split('-')
    return (ord(col.upper()) - 64, int(row))


def hlabel(h):
    return '%s-%d' % (chr(64 + h[0]), h[1])


def in_notch(h):
    return h[0] in NOTCH_COLS and h[1] in NOTCH_ROWS


def on_board(h):
    return 1 <= h[0] <= GRID_COLS and 1 <= h[1] <= GRID_ROWS and not in_notch(h)


# ═════════════════════════════════════════════════════════════════════════════
# BUSES — bare tinned copper wire along a row, soldered at every hole it passes.
# (net, from hole, to hole, note). Must be straight (same row or same col).
# ═════════════════════════════════════════════════════════════════════════════
BUSES = [
    ('GND', 'D-2',  'X-2',  'GND rail — bare 0.5 mm tinned wire, 21 holes'),
    ('3V3', 'D-3',  'I-3',  '3V3 rail — bare 0.5 mm tinned wire, 6 holes'),
    ('D8',  'K-5',  'O-5',  'shared SCK fan-out (display + SD)'),
    ('D10', 'K-6',  'O-6',  'shared MOSI fan-out (display + SD)'),
]

# ═════════════════════════════════════════════════════════════════════════════
# CASTELLATIONS — XIAO *Plus* SMD edge pads. Flying wires, soldered BEFORE the
# XIAO is seated in the notch. The landing hole IS the net source.
# ═════════════════════════════════════════════════════════════════════════════
CASTELLATIONS = [
    ('VBAT',    'X-5', 'BAT+',       'Raw cell + -> battery divider upper leg'),
    ('ADC_BAT', 'X-6', 'GPIO10',     'Divider tap -> ADC_BAT. Board R10 220k = lower leg'),
    ('VBUS_S',  'U-7', 'see Phase 0','VBUS-sense tap. NOTE: ADC2 pads are unusable with '
                                     'WiFi up — prefer DIGITAL presence sense, or D2/GPIO3'),
    ('MENU',    'X-8', 'GPIO42/D11', 'Menu button signal -> D11/GPIO42 (RTC-capable)'),
]

# ═════════════════════════════════════════════════════════════════════════════
# LEADS — off-board module flying leads, each soldered into one hole.
# (component, signal, net, hole)
# ═════════════════════════════════════════════════════════════════════════════
LEADS = [
    # E-paper HAT (9). Control leads land one hole outboard of their landing pad.
    ('DISP', 'CS',   'D0',  'G-14'), ('DISP', 'DC',   'D1',  'G-15'),
    ('DISP', 'RST',  'D3',  'G-17'), ('DISP', 'BUSY', 'D6',  'S-15'),
    ('DISP', 'SCK',  'D8',  'K-5'),  ('DISP', 'MOSI', 'D10', 'K-6'),
    ('DISP', 'VCC',  '3V3', 'F-3'),  ('DISP', 'PWR',  '3V3', 'G-3'),
    ('DISP', 'GND',  'GND', 'F-2'),
    # Storage (microSD dev / XTSD production). SCK+MOSI share the fan-out buses.
    ('SD',   'MISO', 'D9',  'S-11'), ('SD',   'CS',   'D7',  'S-14'),
    ('SD',   'SCK',  'D8',  'L-5'),  ('SD',   'MOSI', 'D10', 'L-6'),
    ('SD',   'VCC',  '3V3', 'H-3'),  ('SD',   'GND',  'GND', 'H-2'),
    # Buttons — leads exit to the case side edge (grip zone).
    ('BTN-FWD',  'sig', 'D4',   'U-16'), ('BTN-FWD',  'gnd', 'GND', 'T-2'),
    ('BTN-BACK', 'sig', 'D5',   'U-17'), ('BTN-BACK', 'gnd', 'GND', 'V-2'),
    ('BTN-MENU', 'sig', 'MENU', 'W-8'),  ('BTN-MENU', 'gnd', 'GND', 'X-2'),
]

# ═════════════════════════════════════════════════════════════════════════════
# WIRES — insulated 30 AWG point-to-point. (net, from, to, purpose)
# ═════════════════════════════════════════════════════════════════════════════
WIRES = [
    ('GND',  'I-11', 'I-2',  'GND rail feed (XIAO pad -> bus)'),
    ('3V3',  'I-13', 'I-3',  '3V3 rail feed (XIAO pad -> bus)'),
    ('5V',   'I-12', 'U-5',  'VBUS -> VBUS-sense divider top'),
    ('D8',   'Q-12', 'O-5',  'SCK -> fan-out bus'),
    ('D10',  'Q-13', 'O-6',  'MOSI -> fan-out bus'),
    ('D0',   'G-14', 'I-14', 'display CS'),
    ('D1',   'G-15', 'I-15', 'display DC'),
    ('D3',   'G-17', 'I-17', 'display RST'),
    ('D6',   'S-15', 'Q-15', 'display BUSY'),
    ('D9',   'S-11', 'Q-11', 'SD MISO'),
    ('D7',   'S-14', 'Q-14', 'SD CS'),
    ('D4',   'U-16', 'Q-16', 'button: page fwd / wake'),
    ('D5',   'U-17', 'Q-17', 'button: page back'),
    ('MENU', 'W-8',  'X-8',  'menu button -> castellation landing'),
]

# ── ROUTING. Rows 10-17 exist only in cols A-I and Q-Z, so a wire between the
#    two side blocks MUST detour above the notch (row 9 or higher). Waypoints are
#    the corner holes the wire is dressed around; the 'route' validator check
#    fails any segment that crosses the void.
WAYPOINTS = {
    ('I-12', 'U-5'): ['I-9', 'U-9'],    # VBUS feed: left block -> over the notch -> right
    ('Q-12', 'O-5'): ['Q-9'],           # SCK: up col Q, then in over the notch top
    ('Q-13', 'O-6'): ['Q-9'],           # MOSI: same dress
}


def wire_path(frm, to):
    """Full hole sequence for a wire, including any routing waypoints."""
    return [hole(frm)] + [hole(h) for h in WAYPOINTS.get((frm, to), [])] + [hole(to)]

# ═════════════════════════════════════════════════════════════════════════════
# PARTS — on-board components. legs: (role, hole, net)
# ═════════════════════════════════════════════════════════════════════════════
PARTS = [
    {'ref': 'R-VBUS-T', 'value': '220k 1%', 'legs': [('5V', 'U-5', '5V'),
                                                     ('tap', 'U-7', 'VBUS_S')],
     'desc': 'VBUS-sense upper leg (5V -> tap)'},
    {'ref': 'R-VBUS-B', 'value': '220k 1%', 'legs': [('tap', 'U-7', 'VBUS_S'),
                                                     ('gnd', 'U-2', 'GND')],
     'desc': 'VBUS-sense lower leg (tap -> GND rail)'},
    {'ref': 'R-BAT',    'value': '220k 1%', 'legs': [('vbat', 'X-5', 'VBAT'),
                                                     ('adc', 'X-6', 'ADC_BAT')],
     'desc': 'Battery divider upper 220k. Lower leg = board R10 (confirm value)'},
    {'ref': 'C-BULK',   'value': '10-22uF', 'legs': [('+', 'D-3', '3V3'),
                                                     ('-', 'D-2', 'GND')],
     'desc': 'Bulk decoupling near the panel rail — e-paper boost draws spikes'},
]

# Holes where more than one conductor is INTENDED (divider junctions, a flying
# wire twisted with a resistor leg, etc). Anything else that stacks up is flagged.
COLAND = {hole(h) for h in ('U-5', 'U-7', 'X-5', 'X-6', 'X-8')}

# ═════════════════════════════════════════════════════════════════════════════
# NET SOURCES
# ═════════════════════════════════════════════════════════════════════════════
CAST_SRC = {net: hole(h) for net, h, _p, _n in CASTELLATIONS}


def net_src(net):
    if net in CAST_SRC:
        return CAST_SRC[net]
    return PAD_HOLE[net]


# ═════════════════════════════════════════════════════════════════════════════
# VALIDATOR — union-find over holes. Warn-only.
#   offboard : a referenced hole is off-grid or inside the notch
#   reach    : a lead / part leg does not connect to its net's source
#   crossnet : two different nets end up on the same node  (= a short)
#   short    : a multi-leg part with two legs on one node
#   crowd    : more conductors in one hole than it can take
# ═════════════════════════════════════════════════════════════════════════════
class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        root = x
        while self.p[root] != root:
            root = self.p[root]
        while self.p[x] != root:
            self.p[x], x = root, self.p[x]
        return root

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)

    def connected(self, a, b):
        return self.find(a) == self.find(b)


def crosses_notch(a, b, steps=200):
    """Does the straight segment a->b pass over the notch void?"""
    c0, c1 = min(NOTCH_COLS) - 0.5, max(NOTCH_COLS) + 0.5
    r0, r1 = min(NOTCH_ROWS) - 0.5, max(NOTCH_ROWS) + 0.5
    for i in range(steps + 1):
        t = i / steps
        x = a[0] + (b[0] - a[0]) * t
        y = a[1] + (b[1] - a[1]) * t
        if c0 < x < c1 and r0 < y < r1:
            return True
    return False


def bus_holes(frm, to):
    (c1, r1), (c2, r2) = hole(frm), hole(to)
    if r1 == r2:
        return [(c, r1) for c in range(min(c1, c2), max(c1, c2) + 1)]
    if c1 == c2:
        return [(c1, r) for r in range(min(r1, r2), max(r1, r2) + 1)]
    return []      # flagged by the validator


def validate():
    warn = []

    def w(tag, msg):
        warn.append((tag, msg))

    uf = _UF()
    for net, frm, to, _note in BUSES:
        hs = bus_holes(frm, to)
        if not hs:
            w('offboard', 'bus %s %s->%s is not straight (must share a row or col)'
              % (net, frm, to))
            continue
        for h in hs[1:]:
            uf.union(hs[0], h)
    for net, frm, to, _p in WIRES:
        uf.union(hole(frm), hole(to))

    # offboard — every referenced hole must exist
    refs = []
    for net, frm, to, _n in BUSES:
        refs += [(h, 'bus %s' % net) for h in bus_holes(frm, to)]
    for net, frm, to, _p in WIRES:
        refs += [(hole(frm), 'wire %s' % net), (hole(to), 'wire %s' % net)]
    for comp, sig, net, h in LEADS:
        refs.append((hole(h), '%s.%s' % (comp, sig)))
    for p in PARTS:
        refs += [(hole(h), '%s.%s' % (p['ref'], ro)) for ro, h, _net in p['legs']]
    for net, h, _pad, _note in CASTELLATIONS:
        refs.append((hole(h), 'cast:%s' % net))
    for net, frm, to, _p in WIRES:
        refs += [(h, 'waypoint %s' % net) for h in wire_path(frm, to)]
    for h, owner in refs:
        if not on_board(h):
            why = 'inside the notch' if in_notch(h) else 'off-grid'
            w('offboard', '%s at %s is %s' % (owner, hlabel(h), why))

    # route — no wire or bus may cross the notch void
    for net, frm, to, _p in WIRES:
        path = wire_path(frm, to)
        for a, b in zip(path, path[1:]):
            if crosses_notch(a, b):
                w('route', 'wire %s %s->%s crosses the notch void (%s->%s) — '
                  'add a WAYPOINTS detour above row 10'
                  % (net, frm, to, hlabel(a), hlabel(b)))
    for net, frm, to, _n in BUSES:
        hs = bus_holes(frm, to)
        if hs and crosses_notch(hs[0], hs[-1]):
            w('route', 'bus %s %s->%s crosses the notch void' % (net, frm, to))
    for lbl, h in PAD_HOLE.items():
        if not on_board(h):
            w('offboard', 'XIAO landing pad %s at %s is not on the board'
              % (lbl, hlabel(h)))

    # reach
    for comp, sig, net, h in LEADS:
        if not uf.connected(hole(h), net_src(net)):
            w('reach', '%s.%s at %s does not reach %s (source %s)'
              % (comp, sig, h, net, hlabel(net_src(net))))
    for p in PARTS:
        for ro, h, net in p['legs']:
            if not uf.connected(hole(h), net_src(net)):
                w('reach', '%s.%s at %s does not reach %s (source %s)'
                  % (p['ref'], ro, h, net, hlabel(net_src(net))))

    # crossnet — one node must not carry two nets
    root_net = {}
    def claim_net(h, net, owner):
        r = uf.find(h)
        if r in root_net and root_net[r][0] != net:
            w('crossnet', 'node %s carries both %s (%s) and %s (%s) — SHORT'
              % (hlabel(r), root_net[r][0], root_net[r][1], net, owner))
        else:
            root_net.setdefault(r, (net, owner))
    for lbl, h in PAD_HOLE.items():
        claim_net(h, lbl, 'XIAO pad')
    for net, h, _pad, _note in CASTELLATIONS:
        claim_net(hole(h), net, 'castellation')
    for comp, sig, net, h in LEADS:
        claim_net(hole(h), net, '%s.%s' % (comp, sig))
    for p in PARTS:
        for ro, h, net in p['legs']:
            claim_net(hole(h), net, '%s.%s' % (p['ref'], ro))

    # short — a part's legs must be on distinct nodes
    for p in PARTS:
        nodes = [uf.find(hole(h)) for _ro, h, _net in p['legs']]
        if len(set(nodes)) < len(nodes):
            w('short', '%s legs share a node (%s)'
              % (p['ref'], ' '.join(h for _ro, h, _net in p['legs'])))

    # crowd — conductors per hole
    conductors = {}
    def add_cond(h, what):
        conductors.setdefault(h, []).append(what)
    for lbl, h in PAD_HOLE.items():
        add_cond(h, 'stub leg %s' % lbl)
    for net, frm, to, _n in BUSES:
        for h in bus_holes(frm, to):
            add_cond(h, 'bus %s' % net)
    for net, frm, to, _p in WIRES:
        add_cond(hole(frm), 'wire %s' % net)
        add_cond(hole(to), 'wire %s' % net)
    for comp, sig, net, h in LEADS:
        add_cond(hole(h), '%s.%s' % (comp, sig))
    for p in PARTS:
        for ro, h, _net in p['legs']:
            add_cond(hole(h), '%s.%s' % (p['ref'], ro))
    for net, h, _pad, _note in CASTELLATIONS:
        add_cond(hole(h), 'flying %s' % net)
    for h, items in sorted(conductors.items()):
        limit = 3 if (h in COLAND or h in PAD_AT) else 2
        if len(items) > limit:
            w('crowd', '%s has %d conductors (limit %d): %s'
              % (hlabel(h), len(items), limit, ', '.join(items)))

    labels = {
        'offboard': 'OFFBOARD  hole off-grid or inside the notch',
        'route':    'ROUTE     wire/bus crossing the notch void',
        'reach':    'REACH     lead/leg does not reach its net source',
        'crossnet': 'CROSSNET  one node carrying two nets (short)',
        'short':    'SHORT     multi-leg part with legs on one node',
        'crowd':    'CROWD     too many conductors in one hole',
    }
    print('=' * 74)
    print('PROTOBOARD BUILD-SHEET VALIDATOR  (warn-only — PDF still generated)')
    print('=' * 74)
    if not warn:
        print('  OK — no issues found.')
    else:
        for tag in ('offboard', 'route', 'crossnet', 'reach', 'short', 'crowd'):
            grp = [m for t, m in warn if t == tag]
            if not grp:
                continue
            print('\n[%s]  (%d)' % (labels[tag], len(grp)))
            for m in grp:
                print('  - ' + m)
        print('\n%d warning(s) total.' % len(warn))
    pads = GRID_COLS * GRID_ROWS - len(NOTCH_COLS) * len(NOTCH_ROWS)
    used = len(conductors)
    print('-' * 74)
    print('Board %d x %d = %d pads, minus %d to the notch = %d usable'
          % (GRID_COLS, GRID_ROWS, GRID_COLS * GRID_ROWS,
             len(NOTCH_COLS) * len(NOTCH_ROWS), pads))
    print('Holes used: %d (%.0f%%) · buses %d · wires %d · flying %d · stub legs %d'
          % (used, 100.0 * used / pads, len(BUSES), len(WIRES),
             len(CASTELLATIONS), len(PAD_HOLE)))
    print('=' * 74)
    return warn


# ═════════════════════════════════════════════════════════════════════════════
# RENDER
# ═════════════════════════════════════════════════════════════════════════════
COL = {
    'board':  colors.HexColor('#0f1a12'), 'board_b': colors.HexColor('#2c4230'),
    'empty':  colors.HexColor('#16241a'), 'empty_b': colors.HexColor('#3d5a44'),
    'notch':  colors.HexColor('#f5f5f0'),
    'white':  colors.white, 'ltgray': colors.HexColor('#cccccc'),
    'dkgray': colors.HexColor('#555555'), 'gray': colors.HexColor('#9a9a9a'),
    'yellow': colors.HexColor('#f5c842'), 'teal': colors.HexColor('#5dcaa5'),
    'lblue':  colors.HexColor('#85b7eb'), 'purple': colors.HexColor('#afa9ec'),
    'green':  colors.HexColor('#88cc44'), 'red': colors.HexColor('#e8705a'),
    'res':    colors.HexColor('#5a3000'), 'res_b': colors.HexColor('#ffaa00'),
    'cast':   colors.HexColor('#003a30'), 'cast_b': colors.HexColor('#44bbaa'),
    'offwhite': colors.HexColor('#e8e8e0'),
}

MARGIN_L, MARGIN_T = 14 * mm, 13 * mm
PITCH = 6.55 * mm
HOLE_R = 2.35 * mm
GRID_W = (GRID_COLS - 1) * PITCH
GRID_H = (GRID_ROWS - 1) * PITCH
grid_top = H - MARGIN_T - 26 * mm
grid_left = MARGIN_L + 6 * mm


def gx(col, mirror=False):
    c = (GRID_COLS + 1 - col) if mirror else col
    return grid_left + (c - 1) * PITCH


def gy(row):
    return grid_top - (row - 1) * PITCH


def net_color(net):
    if net == '3V3':
        return COL['green']
    if net == 'GND':
        return COL['gray']
    if net in ('D4', 'D5', 'MENU'):
        return COL['purple']
    if net in ('5V', 'VBAT', 'ADC_BAT', 'VBUS_S'):
        return COL['yellow']
    if net in ('D8', 'D10', 'D9', 'D7'):
        return COL['teal']
    if net in ('D0', 'D1', 'D3', 'D6'):
        return COL['lblue']
    return COL['ltgray']


def page_header(c, title, sub, tag):
    c.setFillColor(COL['offwhite'])
    c.rect(0, H - MARGIN_T - 11 * mm, W, MARGIN_T + 11 * mm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor('#111'))
    c.setFont('Helvetica-Bold', 11)
    c.drawString(MARGIN_L, H - 9 * mm, title)
    c.setFont('Helvetica', 7.2)
    c.setFillColor(colors.HexColor('#444'))
    c.drawString(MARGIN_L, H - 14 * mm, sub)
    c.setFont('Helvetica-Bold', 9)
    c.drawRightString(W - MARGIN_L, H - 9 * mm, tag)


def draw_board(c, mirror=False):
    """Board outline with the notch, plus every empty hole."""
    pad = 3.6 * mm
    c.setFillColor(COL['board'])
    c.setStrokeColor(COL['board_b'])
    c.setLineWidth(1.0)
    x0, y0 = grid_left - pad, gy(GRID_ROWS) - pad
    c.roundRect(x0, y0, GRID_W + 2 * pad, GRID_H + 2 * pad, 2 * mm, fill=1, stroke=1)
    # notch = removed material
    nc = sorted(NOTCH_COLS)
    nr = sorted(NOTCH_ROWS)
    nx = min(gx(nc[0], mirror), gx(nc[-1], mirror)) - PITCH / 2
    ny = gy(nr[-1]) - pad
    nw = (len(nc) - 1) * PITCH + PITCH
    nh = gy(nr[0]) - ny + PITCH / 2
    c.setFillColor(COL['notch'])
    c.setStrokeColor(colors.HexColor('#888'))
    c.setDash(2, 2)
    c.rect(nx, ny, nw, nh, fill=1, stroke=1)
    c.setDash()
    c.setFont('Helvetica-Bold', 6)
    c.setFillColor(colors.HexColor('#666'))
    c.drawCentredString(nx + nw / 2, ny + nh - 5 * mm, 'NOTCH — cut out')
    c.setFont('Helvetica', 5.4)
    c.drawCentredString(nx + nw / 2, ny + nh - 8.4 * mm, '18.0 x 21.5 mm')
    for row in range(1, GRID_ROWS + 1):
        for col in range(1, GRID_COLS + 1):
            if in_notch((col, row)):
                continue
            c.setFillColor(COL['empty'])
            c.setStrokeColor(COL['empty_b'])
            c.setLineWidth(0.35)
            c.circle(gx(col, mirror), gy(row), HOLE_R, fill=1, stroke=1)
    # coordinate labels
    c.setFont('Helvetica-Bold', 5.6)
    c.setFillColor(COL['dkgray'])
    for col in range(1, GRID_COLS + 1):
        c.drawCentredString(gx(col, mirror), grid_top + 5 * mm, chr(64 + col))
    for row in range(1, GRID_ROWS + 1):
        c.drawRightString(grid_left - pad - 1.5 * mm, gy(row) - 1.6, str(row))


def draw_xiao(c, mirror=False):
    """XIAO body in the notch + its 14 stub legs to the landing pads."""
    nc = sorted(NOTCH_COLS)
    nr = sorted(NOTCH_ROWS)
    x1 = min(gx(nc[0], mirror), gx(nc[-1], mirror)) - PITCH / 2 + 1.2 * mm
    wid = (len(nc) - 1) * PITCH + PITCH - 2.4 * mm
    ytop = gy(nr[0]) + PITCH / 2 - 1.2 * mm
    hgt = ytop - (gy(nr[-1]) - 3.0 * mm)
    c.setFillColor(colors.HexColor('#3a1414'))
    c.setStrokeColor(COL['red'])
    c.setLineWidth(1.2)
    c.rect(x1, ytop - hgt, wid, hgt, fill=1, stroke=1)
    c.setFillColor(COL['red'])
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(x1 + wid / 2, ytop - hgt / 2 + 4, 'XIAO')
    c.setFont('Helvetica', 5.2)
    c.drawCentredString(x1 + wid / 2, ytop - hgt / 2 - 3, 'ESP32-S3 Plus')
    c.drawCentredString(x1 + wid / 2, ytop - hgt / 2 - 9, 'in-plane, USB-C out')
    # stub legs + the landing pads they solder into
    for h, (lbl, _gpio, _fn) in PAD_AT.items():
        px, py = gx(h[0], mirror), gy(h[1])
        inner = x1 if px < x1 else x1 + wid
        c.setStrokeColor(COL['red'])
        c.setLineWidth(1.4)
        c.line(px, py, inner, py)
        # mark the landing pad itself — the builder needs to see these 14 holes
        c.setFillColor(colors.HexColor('#5a1f1f'))
        c.setStrokeColor(COL['red'])
        c.setLineWidth(1.2)
        c.circle(px, py, HOLE_R, fill=1, stroke=1)
        c.setFillColor(colors.HexColor('#ffc9c0'))
        c.setFont('Helvetica-Bold', 4.4)
        c.drawCentredString(px, py - 1.4, lbl)


def draw_buses(c, mirror=False):
    for net, frm, to, _note in BUSES:
        hs = bus_holes(frm, to)
        if not hs:
            continue
        wc = net_color(net)
        c.setStrokeColor(wc)
        c.setLineWidth(2.6)
        c.line(gx(hs[0][0], mirror), gy(hs[0][1]),
               gx(hs[-1][0], mirror), gy(hs[-1][1]))
        c.setFillColor(wc)
        for h in hs:
            c.circle(gx(h[0], mirror), gy(h[1]), 1.15 * mm, fill=1, stroke=0)
        # label at the far end
        c.setFont('Helvetica-Bold', 5.6)
        ex = gx(hs[-1][0], mirror)
        c.drawString(ex + 3 * mm if not mirror else ex - 12 * mm,
                     gy(hs[-1][1]) - 1.6, '%s bus' % net)


def draw_front_solders(c):
    # leads
    for comp, sig, net, h in LEADS:
        col, row = hole(h)
        wc = net_color(net)
        c.setFillColor(wc)
        c.setStrokeColor(COL['white'])
        c.setLineWidth(0.9)
        c.circle(gx(col), gy(row), HOLE_R, fill=1, stroke=1)
        c.setFillColor(colors.HexColor('#111'))
        fs = 4.0 if len(sig) > 4 else 5.0
        c.setFont('Helvetica-Bold', fs)
        c.drawCentredString(gx(col), gy(row) - 1.6, sig)
    # part legs
    for p in PARTS:
        legs = [hole(h) for _ro, h, _net in p['legs']]
        c.setStrokeColor(COL['res_b'])
        c.setLineWidth(1.8)
        c.line(gx(legs[0][0]), gy(legs[0][1]), gx(legs[1][0]), gy(legs[1][1]))
        for (col, row) in legs:
            c.setFillColor(COL['res'])
            c.setStrokeColor(COL['res_b'])
            c.setLineWidth(1.0)
            c.circle(gx(col), gy(row), HOLE_R, fill=1, stroke=1)
        mx = (gx(legs[0][0]) + gx(legs[1][0])) / 2
        my = (gy(legs[0][1]) + gy(legs[1][1])) / 2
        c.setFont('Helvetica-Bold', 4.6)
        c.setFillColor(COL['res_b'])
        c.drawCentredString(mx + 5 * mm, my - 1.4, p['ref'])
    # castellation landings
    for net, h, _pad, _note in CASTELLATIONS:
        col, row = hole(h)
        c.setFillColor(COL['cast'])
        c.setStrokeColor(COL['cast_b'])
        c.setLineWidth(1.1)
        c.circle(gx(col), gy(row), HOLE_R, fill=1, stroke=1)
        c.setFillColor(COL['cast_b'])
        c.setFont('Helvetica-Bold', 4.2)
        c.drawCentredString(gx(col), gy(row) - 1.4, net[:4])


def draw_legend(c, items, y0, ncols=2):
    c.setFont('Helvetica-Bold', 7)
    c.setFillColor(colors.HexColor('#222'))
    c.drawString(MARGIN_L, y0, 'Legend:')
    per = (len(items) + ncols - 1) // ncols
    cw = (W - 2 * MARGIN_L) / ncols
    for i, (fc, txt) in enumerate(items):
        lx = MARGIN_L + (i // per) * cw
        ly = y0 - 5 * mm - (i % per) * 4.0 * mm
        c.setFillColor(fc)
        c.setStrokeColor(COL['white'])
        c.setLineWidth(0.5)
        c.circle(lx + 2 * mm, ly + 1 * mm, 2 * mm, fill=1, stroke=1)
        c.setFillColor(colors.HexColor('#333'))
        c.setFont('Helvetica', 6.4)
        c.drawString(lx + 5.5 * mm, ly - 0.2, txt)
    return y0 - 5 * mm - per * 4.0 * mm - 3 * mm


def notes_block(c, y, lines, colr='#444', size=6.0, lead=3.3):
    c.setFont('Helvetica', size)
    c.setFillColor(colors.HexColor(colr))
    for i, n in enumerate(lines):
        c.drawString(MARGIN_L, y - (i + 1) * lead * mm, n)
    return y - (len(lines) + 1) * lead * mm


def table(c, x, y, headers, widths, rows, rh=5.0 * mm, hdr_bg='#1a1a1a',
          fs=6.3, bold_cols=(0,)):
    tw = sum(widths)
    c.setFillColor(colors.HexColor(hdr_bg))
    c.rect(x, y - rh, tw, rh, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 6.8)
    cx = x
    for k, hd in enumerate(headers):
        c.drawString(cx + 1.4 * mm, y - rh + 1.7 * mm, hd)
        cx += widths[k]
    y -= rh
    alt = False
    for r in rows:
        c.setFillColor(colors.HexColor('#f0f0e8' if not alt else '#e4e4dc'))
        c.rect(x, y - rh, tw, rh, fill=1, stroke=0)
        cx = x
        for k, cell in enumerate(r):
            c.setFillColor(colors.HexColor('#1a1a1a'))
            c.setFont('Helvetica-Bold' if k in bold_cols else 'Helvetica', fs)
            c.drawString(cx + 1.4 * mm, y - rh + 1.6 * mm, str(cell))
            cx += widths[k]
        y -= rh
        alt = not alt
    return y


# ════════════════════════════════════════════════════════════════════════════
validate()
cv = canvas.Canvas(OUTPUT, pagesize=A4)

# ── SHEET 1: FRONT ───────────────────────────────────────────────────────────
page_header(cv,
    'DIY E-Reader — protoboard %dx%d — Sheet 1 of 4: Front (component side)'
    % (GRID_COLS, GRID_ROWS),
    'PLAIN protoboard: every hole is isolated. Rails are BARE-WIRE BUSES; '
    'everything else is a wire (Sheet 2). Cols A-Z left-right, rows 1-17 top-bottom.',
    'FRONT')
draw_board(cv)
draw_buses(cv)
draw_front_solders(cv)
draw_xiao(cv)

leg1 = [
    (COL['lblue'],  'E-paper control lead (CS/DC/RST/BUSY)'),
    (COL['teal'],   'SPI / storage lead (SCK, MOSI, MISO, CS)'),
    (COL['gray'],   'GND lead -> lands on the GND bus (row 2)'),
    (COL['green'],  '3V3 lead -> lands on the 3V3 bus (row 3)'),
    (COL['purple'], 'Button lead (fwd / back / menu)'),
    (COL['yellow'], 'Power-sense: 5V / VBAT / ADC_BAT / VBUS tap'),
    (COL['res'],    'Component leg (dividers, bulk cap) — body drawn between legs'),
    (COL['cast'],   'Castellation landing — flying wire to a XIAO Plus edge pad'),
    (COL['red'],    'XIAO stub leg (26 AWG, bent 90 deg into the landing pad)'),
]
end1 = draw_legend(cv, leg1, gy(GRID_ROWS) - 12 * mm, ncols=2)
cv.setFont('Helvetica-Bold', 6.6)
cv.setFillColor(COL['cast_b'].clone())
cv.setFillColor(colors.HexColor('#1a6a5a'))
cv.drawString(MARGIN_L, end1, 'Build order (access is the constraint):')
notes_block(cv, end1, [
    '1. CUT the board to 26 x 17 holes and the notch (two straight cuts from the bottom edge). Deburr. Mask on — FR-4 dust is glass fibre.',
    '2. Solder the 4 CASTELLATION flying wires to the XIAO edge pads FIRST, off-board — they are unreachable once the XIAO is in the notch.',
    '3. Lay the two BARE-WIRE BUSES (GND row 2, 3V3 row 3) and the two short fan-out buses (SCK row 5, MOSI row 6). Solder every hole they pass.',
    '4. Fit the PARTS (3 resistors + bulk cap). Reuse the cut-off legs as jumper wire.',
    '5. Run the 14 insulated WIRES (Sheet 2) — 30 AWG Kynar, laid FLAT, leads trimmed FLUSH (back-side loom is part of the Z budget).',
    '6. Solder the MODULE LEADS into their holes (panel HAT, storage, buttons).',
    '7. XIAO LAST: stub-leg it into the notch, shimmed so USB-C lines up with the case port. Then continuity-check every net BEFORE power.',
], colr='#333')
cv.showPage()

# ── SHEET 2: BACK ────────────────────────────────────────────────────────────
page_header(cv,
    'DIY E-Reader — protoboard %dx%d — Sheet 2 of 4: Back (%d wires)'
    % (GRID_COLS, GRID_ROWS, len(WIRES)),
    'Board shown FLIPPED left-right (as you see it soldering the back). '
    'Buses are on the FRONT; these are the insulated point-to-point runs.',
    'BACK')
draw_board(cv, mirror=True)
for _net, _frm, _to, _purpose in WIRES:
    path = wire_path(_frm, _to)
    wc = net_color(_net)
    cv.setStrokeColor(wc)
    cv.setLineWidth(1.5)
    for a, b in zip(path, path[1:]):
        cv.line(gx(a[0], True), gy(a[1]), gx(b[0], True), gy(b[1]))
    cv.setFillColor(wc)
    for h in (path[0], path[-1]):
        cv.circle(gx(h[0], True), gy(h[1]), 1.3 * mm, fill=1, stroke=0)
    for h in path[1:-1]:      # dressed corner, not a solder joint
        cv.setStrokeColor(wc)
        cv.setLineWidth(0.9)
        cv.circle(gx(h[0], True), gy(h[1]), 0.9 * mm, fill=0, stroke=1)
for _net, _frm, _to, _purpose in WIRES:
    path = wire_path(_frm, _to)
    mid = len(path) // 2
    a, b = path[mid - 1], path[mid]
    xm = (gx(a[0], True) + gx(b[0], True)) / 2
    ym = (gy(a[1]) + gy(b[1])) / 2
    cv.setFont('Helvetica-Bold', 4.8)
    tw = cv.stringWidth(_net, 'Helvetica-Bold', 4.8)
    cv.setFillColor(colors.white)
    cv.setFillAlpha(0.95)
    cv.roundRect(xm - tw / 2 - 0.7 * mm, ym + 0.7 * mm, tw + 1.4 * mm, 2.4 * mm,
                 0.5 * mm, fill=1, stroke=0)
    cv.setFillAlpha(1)
    cv.setStrokeColor(net_color(_net))
    cv.setLineWidth(0.6)
    cv.roundRect(xm - tw / 2 - 0.7 * mm, ym + 0.7 * mm, tw + 1.4 * mm, 2.4 * mm,
                 0.5 * mm, fill=0, stroke=1)
    cv.setFillColor(colors.HexColor('#1a1a1a'))
    cv.drawCentredString(xm, ym + 1.3 * mm, _net)
# castellation stubs, dashed off the board edge
for _net, _h, _pad, _note in CASTELLATIONS:
    a = hole(_h)
    x1, y1 = gx(a[0], True), gy(a[1])
    # run the stub to whichever page edge has room (mirroring flips these holes
    # to the left, where the label would fall off the sheet)
    right = x1 < (grid_left + GRID_W / 2)
    x2 = (grid_left + GRID_W + 9 * mm) if right else (grid_left - 9 * mm)
    cv.setStrokeColor(net_color(_net))
    cv.setLineWidth(1.3)
    cv.setDash(2, 2)
    cv.line(x1, y1, x2, y1)
    cv.setDash()
    cv.setFont('Helvetica-Bold', 4.8)
    cv.setFillColor(net_color(_net))
    txt = '%s (flying)' % _net
    if right:
        cv.drawString(x2 + 1 * mm, y1 - 1.4, txt)
    else:
        cv.drawRightString(x2 - 1 * mm, y1 - 1.4, txt)

leg2 = [
    (COL['gray'],   'GND rail feed (XIAO GND pad -> row-2 bus)'),
    (COL['green'],  '3V3 rail feed (XIAO 3V3 pad -> row-3 bus)'),
    (COL['teal'],   'Shared SPI: SCK / MOSI pad -> fan-out bus'),
    (COL['lblue'],  'E-paper control: lead hole -> landing pad'),
    (COL['purple'], 'Button signal: lead hole -> landing pad'),
    (COL['yellow'], 'VBUS tap + castellation flying wires (dashed)'),
]
end2 = draw_legend(cv, leg2, gy(GRID_ROWS) - 12 * mm, ncols=2)
notes_block(cv, end2, [
    'Only %d insulated wires, because the GND/3V3 rails and the shared SPI fan-outs are bare-wire BUSES on the front instead.' % len(WIRES),
    'Use 30 AWG Kynar (wire-wrap). Lay it FLAT against the board and trim leads FLUSH — ~1 mm of loom cancels the notch Z saving.',
    'Colour-code by net and the board documents itself. Do not bridge more than ~4 adjacent pads with solder anywhere.',
    'The two rail feeds are the longest runs (XIAO pad up to the bus); everything else is short and local by design.',
], colr='#333')
cv.showPage()

# ── SHEET 3: WIRING LISTS ────────────────────────────────────────────────────
cv.setFillColor(colors.HexColor('#f8f8f4'))
cv.rect(0, 0, W, H, fill=1, stroke=0)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.setFont('Helvetica-Bold', 12)
cv.drawString(MARGIN_L, H - 14 * mm, 'Sheet 3 of 4: Wiring lists (tick as you go)')
cv.setFont('Helvetica', 7.2)
cv.setFillColor(colors.HexColor('#555'))
cv.drawString(MARGIN_L, H - 19 * mm,
              'Buses first, then parts, then wires, then module leads. '
              'Hole labels are col-letter + row (e.g. G-14).')

y = H - 24 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, y, 'Buses — bare tinned copper along a hole row')
y = table(cv, MARGIN_L, y - 2 * mm, ['Net', 'Run', 'Holes', 'Note'],
          [20 * mm, 26 * mm, 16 * mm, 120 * mm],
          [(n, '%s -> %s' % (f, t), len(bus_holes(f, t)), note)
           for n, f, t, note in BUSES])

y -= 6 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, y, 'On-board parts')
y = table(cv, MARGIN_L, y - 2 * mm, ['Ref', 'Value', 'Legs', 'Nets', 'Note'],
          [22 * mm, 19 * mm, 22 * mm, 27 * mm, 92 * mm],
          [(p['ref'], p['value'], ' '.join(h for _r, h, _n in p['legs']),
            ' / '.join(n for _r, _h, n in p['legs']), p['desc'][:74])
           for p in PARTS], fs=6.0)

y -= 6 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, y, 'Insulated wires (%d) + castellation flying wires (%d)'
              % (len(WIRES), len(CASTELLATIONS)))
rows = []
for n, f, t, p in WIRES:
    via = WAYPOINTS.get((f, t))
    rows.append((n, f, t, p + ('  [dress via %s]' % ', '.join(via) if via else '')))
rows += [(n, h, 'XIAO %s' % pad, note[:84]) for n, h, pad, note in CASTELLATIONS]
y = table(cv, MARGIN_L, y - 2 * mm, ['Net', 'From', 'To', 'Purpose'],
          [20 * mm, 18 * mm, 26 * mm, 118 * mm], rows, fs=6.0)

y -= 6 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, y, 'Module leads (%d)' % len(LEADS))


def lead_note(net, sig):
    if net == 'GND':
        return 'lands on the GND bus (row 2)'
    if net == '3V3':
        return 'lands on the 3V3 bus (row 3)' + (' — PWR tied to 3V3' if sig == 'PWR' else '')
    if net in ('D8', 'D10'):
        return 'lands on the shared %s fan-out bus' % ('SCK' if net == 'D8' else 'MOSI')
    if net == 'MENU':
        return 'wire to the MENU castellation landing'
    return 'wire to landing pad %s (%s)' % (hlabel(PAD_HOLE[net]), net)


y = table(cv, MARGIN_L, y - 2 * mm, ['Module', 'Signal', 'Net', 'Hole', 'How it connects'],
          [24 * mm, 20 * mm, 18 * mm, 20 * mm, 100 * mm],
          [(comp, sig, net, h, lead_note(net, sig)) for comp, sig, net, h in LEADS],
          rh=4.6 * mm, bold_cols=(0, 3))
cv.showPage()

# ── SHEET 4: REFERENCE ───────────────────────────────────────────────────────
cv.setFillColor(colors.HexColor('#f8f8f4'))
cv.rect(0, 0, W, H, fill=1, stroke=0)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.setFont('Helvetica-Bold', 12)
cv.drawString(MARGIN_L, H - 14 * mm, 'Sheet 4 of 4: Reference')
cv.setFont('Helvetica', 7.2)
cv.setFillColor(colors.HexColor('#555'))
cv.drawString(MARGIN_L, H - 19 * mm,
              'XIAO landing-pad map, board budget, and the rules that bite.')

y = H - 24 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, y, 'XIAO landing pads — stub-leg targets')
prows = []
for h in sorted(PAD_AT, key=lambda k: (k[0], k[1])):
    lbl, gpio, fn = PAD_AT[h]
    side = 'A (col %s)' % chr(64 + SIDE_A_COL) if h[0] == SIDE_A_COL \
        else 'B (col %s)' % chr(64 + SIDE_B_COL)
    prows.append((hlabel(h), side, lbl, gpio, fn))
y = table(cv, MARGIN_L, y - 2 * mm, ['Hole', 'Side', 'XIAO', 'GPIO', 'esp-read function'],
          [18 * mm, 24 * mm, 16 * mm, 20 * mm, 104 * mm], prows, rh=4.8 * mm)

y -= 8 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#a33'))
cv.drawString(MARGIN_L, y, 'VERIFY BEFORE YOU CUT (Phase 0)')
y = notes_block(cv, y, [
    'Side A / side B assignment and their top-to-bottom direction are UNVERIFIED. Dry-fit the XIAO on a scrap board, measure the pad',
    'row-to-row spacing with calipers (expected 12.7 mm = 5 pitches), and check the order against the silk. Flip FLIP_SIDE_A/B in this',
    'script if wrong, re-run, and the whole sheet follows. Getting this wrong wastes a board.',
    'VBUS-sense pin is still OPEN: ESP32-S3 ADC1 is GPIO1-10 only and ADC2 is unusable while WiFi is up, so a high-numbered',
    'castellation cannot do analog. Prefer DIGITAL VBUS-presence sense (any spare GPIO), or use D2/GPIO3 (the free ADC1 pin, hole',
    'I-16) and verify boot behaviour — it is a strapping pin. Confirm the board R10 value before trusting it as the divider lower leg.',
    'Check nothing on the XIAO underside protrudes below its PCB — it decides whether the case needs a clearance pocket or a flat boss.',
], colr='#a33', size=6.2)

y -= 3 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, y, 'Board budget')
pads_total = GRID_COLS * GRID_ROWS
pads_notch = len(NOTCH_COLS) * len(NOTCH_ROWS)
y = notes_block(cv, y, [
    '%d x %d holes. Pad-centre span %.1f x %.1f mm; CUT SIZE ~%.1f x %.1f mm '
    '(half a pitch of margin all round). Pads: %d total, -%d to the notch = %d usable.'
    % (GRID_COLS, GRID_ROWS, (GRID_COLS - 1) * 2.54, (GRID_ROWS - 1) * 2.54,
       GRID_COLS * 2.54, GRID_ROWS * 2.54,
       pads_total, pads_notch, pads_total - pads_notch),
    'Connections: %d bare-wire buses, %d insulated wires, %d castellation flying wires, '
    '%d XIAO stub legs, %d module leads, %d parts.'
    % (len(BUSES), len(WIRES), len(CASTELLATIONS), len(PAD_HOLE), len(LEADS), len(PARTS)),
    'Rows 1-9 span the full width (above the notch): rails + fan-outs + module leads. '
    'Rows 10-17 exist only in cols A-I and Q-Z.',
    'Cols A-C and the right-hand block are deliberately left free — spare pads cost nothing '
    'and crowding is what causes accidental bridges.',
], colr='#333', size=6.2)

y -= 3 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#1a6a5a'))
cv.drawString(MARGIN_L, y, 'Shared-SPI build rule (from CLAUDE.md — most "one device works, not both" bugs)')
y = notes_block(cv, y, [
    'Both CS pins are outputs driven HIGH (deselected) at startup, before either device is initialised.',
    'Initialise the SD FIRST, then the panel. Run the bus at the SD-tolerated clock (library default).',
    'Never start an SD transfer mid-refresh — wait for the panel BUSY line to clear.',
    'Enable SdFat USE_SD_CRC: a shared bus can silently corrupt SD transfers (integrity layer 1).',
], colr='#333', size=6.2)

y -= 3 * mm
cv.setFont('Helvetica-Bold', 8)
cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, y, 'Test before power')
notes_block(cv, y, [
    'Continuity-check EVERY net against Sheet 3, then check for shorts: rail-to-rail, and adjacent pads along each bus run.',
    'Clean with IPA and inspect under magnification first — flux residue hides bridges on 2.54 mm pitch.',
    'Confirm GND and 3V3 are not shorted BEFORE the battery goes anywhere near the board. Power from USB first.',
    'Iron: chisel/bevel tip 1.5-2.4 mm at ~350 C, leaded 60/40 0.7 mm, flux pen. A needle tip on plated-through holes gives cold joints.',
], colr='#333', size=6.2)

cv.save()
print('Wrote', OUTPUT)
