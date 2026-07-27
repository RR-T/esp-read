#!/usr/bin/env python3
"""
ProtoMate-for-XIAO build-sheet generator — DIY E-Ink E-Reader.

DIRECT-SOLDER build (no JST connectors — Z-height constrained). Off-board
modules (e-paper HAT, microSD, buttons) have flying leads that solder DIRECTLY
into their target hole. The design minimises rear jumper traces:

  * a lead that only needs a GPIO solders straight into that XIAO pad on
    Column I  (zero jumpers);
  * signals that must fan out (shared SPI SCK/MOSI, the GND/3V3 rails) get a
    small number of short, straight rear jumpers;
  * three Plus-only signals arrive as flying wires from the castellations.

Total rear board jumpers: 7 (see JUMPERS). Everything else is a front solder.

Board geometry (this project's coordinate system, rotated 90 deg from the Pi
Hut photo). 9 columns A-I x 14 rows:

    A B C   D    E    F G H   I
    +---+  GND  3V3  +---+   XIAO pads
   3-hole  bus  bus  3-hole  (one per hole)

CONTINUITY MODEL (confirmed against hardware):
  * Cols A-B-C : each ROW is one node (3-hole strip). ABC1..ABC14.
  * Col  D     : vertical bus, SPLIT at 7/8 -> Dlo (1-7), Dhi (8-14). = GND.
  * Col  E     : vertical bus, SPLIT at 7/8 -> Elo (1-7), Ehi (8-14). = 3V3.
  * Cols F-G-H : each ROW is one node (3-hole strip). FGH1..FGH14.
  * Col  I     : each hole is its OWN node = one XIAO pad (a lead solders here
                 directly; the pad reaches a strip only via a jumper into H).
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm

OUTPUT = 'protomate_build.pdf'
W, H = A4

COL = {
    'board':   colors.HexColor('#111111'),
    'empty':   colors.HexColor('#2a2218'), 'empty_b': colors.HexColor('#4a3a28'),
    'gbus':    colors.HexColor('#1a2a1a'), 'gbus_b':  colors.HexColor('#3a8a3a'),  # 3V3 bus (E)
    'kbus':    colors.HexColor('#2a2020'), 'kbus_b':  colors.HexColor('#8a3a3a'),  # GND bus (D)
    'res':     colors.HexColor('#5a3000'), 'res_b':   colors.HexColor('#ffaa00'),  # resistor leg
    'cast':    colors.HexColor('#003a30'), 'cast_b':  colors.HexColor('#44bbaa'),  # castellation stub
    'white':   colors.white,
    'ltgray':  colors.HexColor('#cccccc'), 'dkgray':  colors.HexColor('#555555'),
    'yellow':  colors.HexColor('#f5c842'), 'teal':    colors.HexColor('#5dcaa5'),
    'lblue':   colors.HexColor('#85b7eb'), 'purple':  colors.HexColor('#afa9ec'),
    'orange':  colors.HexColor('#f0997b'), 'pink':    colors.HexColor('#ed93b1'),
    'green':   colors.HexColor('#88cc44'), 'gray':    colors.HexColor('#9a9a9a'),
    'offwhite':colors.HexColor('#e8e8e0'),
}

MARGIN_L = 16*mm; MARGIN_T = 14*mm
ROWS = 14; HOLE_R = 2.9*mm; ROW_H = 8.2*mm; COL_W = 7.2*mm
GAP_ZONE = 2.4*mm; GAP_MID = 5.5*mm; LABEL_W = 4*mm
COLS = ['A','B','C','D','E','F','G','H','I']

FWD_ORDER = [('A',0),('B',0),('C',GAP_ZONE),('D',GAP_ZONE),('E',GAP_ZONE),
             ('F',0),('G',0),('H',GAP_MID),('I',0)]
BWD_ORDER = [(c,g) for c,g in reversed(FWD_ORDER)]

def build_xs(x0, order):
    xs = {}; x = x0
    for name, extra in order:
        xs[name] = x; x += COL_W + extra
    return xs, x

x0 = MARGIN_L + LABEL_W
col_xs_fwd, br_fwd = build_xs(x0, FWD_ORDER)
col_xs_bwd, br_bwd = build_xs(x0, BWD_ORDER)
board_top = H - MARGIN_T - 16*mm
board_bottom = board_top - ROWS*ROW_H - 4*mm

def ry(r): return board_top - (r-0.5)*ROW_H

# ═════════════════════════════════════════════════════════════════════════════
# COLUMN I — the XIAO ESP32-S3 pads, fixed by the board.
# Row -> (silk on the ProtoMate, XIAO label, GPIO/rail, esp-read function).
# ═════════════════════════════════════════════════════════════════════════════
XIAO_I = [
    (1,  'G',   'GND', 'GND',    'Ground'),
    (2,  '5v',  '5V',  '5V',     'VBUS (dead on battery; VBUS-sense tap)'),
    (3,  '3v',  '3V3', '3V3',    'Peripheral power'),
    (4,  '0',   'D0',  'GPIO1',  'E-paper CS'),
    (5,  '1',   'D1',  'GPIO2',  'E-paper DC'),
    (6,  '2',   'D2',  'GPIO3',  'SPARE (strapping pin)'),
    (7,  '3',   'D3',  'GPIO4',  'E-paper RST'),
    (8,  '9',   'D9',  'GPIO8',  'SPI MISO (SD)'),
    (9,  '8',   'D8',  'GPIO7',  'SPI SCK (shared)'),
    (10, '10',  'D10', 'GPIO9',  'SPI MOSI/DIN (shared)'),
    (11, 'RX',  'D7',  'GPIO44', 'SD CS'),
    (12, 'TX',  'D6',  'GPIO43', 'E-paper BUSY'),
    (13, 'SDA', 'D4',  'GPIO5',  'Button: page fwd / wake'),
    (14, 'SCL', 'D5',  'GPIO6',  'Button: page back'),
]
NET_ROW = {lbl: r for (r, silk, lbl, gpio, fn) in XIAO_I}   # XIAO label -> Column-I row

def node_of(col, row):
    if col == 'I':   return 'I%d' % row                 # isolated XIAO pad
    if col in 'ABC': return 'ABC%d' % row
    if col in 'FGH': return 'FGH%d' % row
    return '%s%s' % (col, 'lo' if row <= 7 else 'hi')    # D / E split at 7/8

RAILS = {'3V3': ('E', ('I', NET_ROW['3V3'])), 'GND': ('D', ('I', NET_ROW['GND']))}  # rail -> (bus col, feed pad)

# ═════════════════════════════════════════════════════════════════════════════
# CASTELLATIONS — XIAO ESP32-S3 *Plus* edge pads, NOT on the 14-pad breakout.
# They arrive as flying wires soldered from the pad to a strip hole (landing).
# net -> (landing col,row, pad label, note). The landing node IS the net source.
# ═════════════════════════════════════════════════════════════════════════════
CASTELLATIONS = [
    ('VBAT',    ('G', 4), 'BAT+',        'Raw cell +, from the XIAO BAT+ pad -> battery divider upper leg'),
    ('ADC_BAT', ('G', 5), 'GPIO10',      'Battery divider tap -> ADC_BAT (GPIO10). Board R10 220k = lower leg'),
    ('VBUS_S',  ('F', 2), 'ADC1 spare',  'VBUS-sense tap -> spare ADC1 castellation (resolves RST/VBUS clash)'),
    ('MENU',    ('H', 8), 'GPIO42/D11',  'Menu button signal -> D11/GPIO42 (RTC-capable)'),
]
CAST_SRC = {net: hole for net, hole, _lbl, _note in CASTELLATIONS}

def net_src(net):
    """Canonical source node-hole for a net (used by the validator).
    Rails resolve to their XIAO feed pad; castellations to their landing hole;
    everything else to the XIAO pad on Column I (keyed by label)."""
    if net in RAILS:    return RAILS[net][1]
    if net in CAST_SRC: return CAST_SRC[net]
    return ('I', NET_ROW[net])

# ═════════════════════════════════════════════════════════════════════════════
# LEADS — off-board module wires, each soldered DIRECTLY into one hole.
# (component, signal label, net, col, row). No JST, no per-lead back-wire.
#   * net == a XIAO label with a single destination -> hole is that Column-I pad.
#   * net == a shared signal (SCK/MOSI) -> hole is the fan-out strip (see JUMPERS).
#   * net == 'GND'/'3V3' -> hole is a free bus hole on col D / col E.
#   * net == 'MENU' -> hole shares the castellation-landing strip.
# ═════════════════════════════════════════════════════════════════════════════
LEADS = [
    # E-paper HAT (9 lines). Direct-to-pad where single-use; strips for shared SPI.
    ('DISP', 'CS',   'D0',  'I', 4),    ('DISP', 'DC',   'D1',  'I', 5),
    ('DISP', 'RST',  'D3',  'I', 7),    ('DISP', 'BUSY', 'D6',  'I', 12),
    ('DISP', 'SCK',  'D8',  'F', 9),    ('DISP', 'MOSI', 'D10', 'F', 10),
    ('DISP', 'VCC',  '3V3', 'E', 9),    ('DISP', 'PWR',  '3V3', 'E', 10),
    ('DISP', 'GND',  'GND', 'D', 6),
    # microSD. SCK/MOSI share the same strips as the display; MISO is SD-only.
    ('SD',   'MISO', 'D9',  'I', 8),    ('SD',   'CS',   'D7',  'I', 11),
    ('SD',   'SCK',  'D8',  'G', 9),    ('SD',   'MOSI', 'D10', 'G', 10),
    ('SD',   'VCC',  '3V3', 'E', 5),    ('SD',   'GND',  'GND', 'D', 9),
    # Buttons (off-board tactile switches; two flying leads each).
    ('BTN-FWD',  'sig', 'D4',   'I', 13),  ('BTN-FWD',  'gnd', 'GND', 'D', 13),
    ('BTN-BACK', 'sig', 'D5',   'I', 14),  ('BTN-BACK', 'gnd', 'GND', 'D', 14),
    ('BTN-MENU', 'sig', 'MENU', 'G', 8),   ('BTN-MENU', 'gnd', 'GND', 'D', 10),
]

# ── Multi-leg PARTS (on-board resistors). leg: ('role', col, row); net_of maps a
#    leg hole to its net. Validator: legs on distinct nodes.
PARTS = []
def add_part(ref, kind, legs, net_of, desc=''):
    PARTS.append({'ref': ref, 'kind': kind, 'legs': legs, 'net_of': net_of, 'desc': desc})

# VBUS-sense divider, tucked beside Column I: 5V direct into I2, tap on FGH2,
# GND on FGH1 (fed by the one short I1->H1 jumper). Series 5V - Rt - tap - Rb - GND.
add_part('R-VBUS-T', 'R', [('v5', 'I', 2), ('tap', 'H', 2)],
         {('I', 2): '5V', ('H', 2): 'VBUS_S'}, 'VBUS-sense upper leg (5V -> tap)')
add_part('R-VBUS-B', 'R', [('tap', 'G', 2), ('gnd', 'G', 1)],
         {('G', 2): 'VBUS_S', ('G', 1): 'GND'}, 'VBUS-sense lower leg (tap -> GND)')
# Battery divider upper leg (board R10 220k is the lower leg, off-board). Both
# ends are castellation flying wires -> zero board jumpers.
add_part('R-BAT', 'R', [('vbat', 'H', 4), ('adc', 'H', 5)],
         {('H', 4): 'VBAT', ('H', 5): 'ADC_BAT'},
         'Upper 220k: VBAT -> ADC_BAT tap (/2 into ADC). Lower leg = board R10')

# ═════════════════════════════════════════════════════════════════════════════
# JUMPERS — the ONLY rear board-to-board traces. Kept few and straight.
#   (frm hole, to hole, net, label). Everything else is a direct front solder.
# ═════════════════════════════════════════════════════════════════════════════
JUMPERS = [
    (('I', 1),  ('D', 1),  'GND', 'GND feed'),      # I1  -> GND bus (lo)
    (('D', 7),  ('D', 8),  'GND', 'GND split'),     # bridge the 7/8 split
    (('I', 3),  ('E', 3),  '3V3', '3V3 feed'),      # I3  -> 3V3 bus (lo)
    (('E', 7),  ('E', 8),  '3V3', '3V3 split'),
    (('I', 9),  ('H', 9),  'D8',  'SCK fanout'),    # SCK  -> FGH9 strip (disp+SD)
    (('I', 10), ('H', 10), 'D10', 'MOSI fanout'),   # MOSI -> FGH10 strip (disp+SD)
    (('I', 1),  ('H', 1),  'GND', 'VBUS-sense GND'),# GND to the divider bottom
]

# WIRES to render on the back = jumpers + castellation flying wires only.
WIRES = []
for frm, to, net, lbl in JUMPERS:
    WIRES.append({'frm': frm, 'to': to, 'net': net, 'label': lbl, 'cast': False,
                  'desc': '%s: %s%d -> %s%d' % (lbl, frm[0], frm[1], to[0], to[1])})
for net, hole, pad, note in CASTELLATIONS:
    WIRES.append({'frm': hole, 'to': ('CAST', 0), 'net': net, 'label': '%s→%s' % (net, pad),
                  'cast': True, 'desc': 'flying wire: %s%d -> %s (%s)' % (hole[0], hole[1], pad, note)})

# ═════════════════════════════════════════════════════════════════════════════
# VALIDATOR — union-find over nodes joined by jumpers. WARN-ONLY.
#   * reach : every lead & powered part-leg reaches its net's source node.
#   * short : a multi-leg part must not have two legs on one node.
#   * collide: no two front solder points share a hole.
# ═════════════════════════════════════════════════════════════════════════════
class _UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x); root = x
        while self.p[root] != root: root = self.p[root]
        while self.p[x] != root: self.p[x], x = root, self.p[x]
        return root
    def union(self, a, b): self.p[self.find(a)] = self.find(b)
    def connected(self, a, b): return self.find(a) == self.find(b)

def validate():
    warnings = []
    def warn(tag, msg): warnings.append((tag, msg))

    uf = _UF()
    for frm, to, net, lbl in JUMPERS:
        uf.union(node_of(*frm), node_of(*to))

    # reach — each lead's hole connects to its net's source
    for comp, sig, net, col, row in LEADS:
        if not uf.connected(node_of(col, row), node_of(*net_src(net))):
            warn('reach', '%s.%s at %s%d does not reach %s' % (comp, sig, col, row, net))
    # reach — powered part legs (those whose net has an on-board/pad source)
    for p in PARTS:
        for (ro, col, row) in p['legs']:
            net = p['net_of'].get((col, row))
            if not net:
                continue
            if not uf.connected(node_of(col, row), node_of(*net_src(net))):
                warn('reach', '%s.%s at %s%d does not reach %s' % (p['ref'], ro, col, row, net))

    # short — part legs on distinct nodes
    for p in PARTS:
        nodes = [node_of(c, r) for (_ro, c, r) in p['legs']]
        if len(set(nodes)) < len(nodes):
            warn('short', '%s legs share a node (%s)'
                 % (p['ref'], ' '.join('%s%d' % (c, r) for (_ro, c, r) in p['legs'])))

    # collide — front solder holes claimed once (leads + part legs + cast landings)
    front = {}
    def claim(col, row, owner):
        if (col, row) in front:
            warn('collide', 'hole %s%d shared by %s and %s' % (col, row, front[(col, row)], owner))
        else:
            front[(col, row)] = owner
    for comp, sig, net, col, row in LEADS:
        claim(col, row, '%s.%s' % (comp, sig))
    for p in PARTS:
        for (ro, col, row) in p['legs']:
            claim(col, row, '%s.%s' % (p['ref'], ro))
    for net, hole, pad, note in CASTELLATIONS:
        claim(hole[0], hole[1], 'cast:%s' % net)

    order = ['reach', 'short', 'collide']
    labels = {'reach': 'REACH  lead/leg does not reach its net',
              'short': 'SHORT  multi-leg part with legs on one node',
              'collide': 'COLLIDE  two front solder points share a hole'}
    print('=' * 70)
    print('BUILD-SHEET VALIDATOR  (warn-only — PDF still generated)')
    print('=' * 70)
    if not warnings:
        print('  OK — no issues found.')
    else:
        for tag in order:
            grp = [m for t, m in warnings if t == tag]
            if not grp: continue
            print('\n[%s]  (%d)' % (labels[tag], len(grp)))
            for m in grp: print('  - ' + m)
        print('\n%d warning(s) total.' % len(warnings))
    print('=' * 70)
    return warnings

# ── Render structures ────────────────────────────────────────────────────────
def net_color(net):
    if net == '3V3': return COL['gbus_b']
    if net == 'GND': return COL['gray']
    if net in ('D4', 'D5', 'MENU'): return COL['purple']            # buttons
    if net in ('5V', 'VBAT', 'ADC_BAT', 'VBUS_S'): return COL['yellow']  # power-sense
    if net in ('D8', 'D10', 'D9', 'D7'): return COL['teal']         # SPI / SD
    if net in ('D0', 'D1', 'D3', 'D6'): return COL['lblue']         # e-paper control
    return COL['ltgray']

# hole -> {fill,border,lbl,text,desc}
FRONT = {}
for comp, sig, net, col, row in LEADS:
    FRONT[(col, row)] = {'fill': net_color(net), 'border': COL['white'],
                         'lbl': sig, 'text': COL['board'],
                         'desc': '%s %s -> %s' % (comp, sig, net)}
for p in PARTS:
    for (ro, col, row) in p['legs']:
        net = p['net_of'].get((col, row))
        FRONT[(col, row)] = {'fill': COL['res'], 'border': COL['res_b'],
                             'lbl': p['ref'].split('-')[-1][:3], 'text': COL['white'],
                             'desc': '%s %s (%s)' % (p['ref'], ro, net)}
for net, hole, pad, note in CASTELLATIONS:
    if hole not in FRONT:
        FRONT[hole] = {'fill': COL['cast'], 'border': COL['cast_b'],
                       'lbl': net[:3], 'text': COL['cast_b'], 'desc': 'castellation %s' % net}

# ── Drawing helpers ──────────────────────────────────────────────────────────
def page_header(c, title, sub, tag):
    c.setFillColor(COL['offwhite']); c.rect(0, H-MARGIN_T-11*mm, W, MARGIN_T+11*mm, fill=1, stroke=0)
    c.setFillColor(COL['board']); c.setFont('Helvetica-Bold', 11); c.drawString(MARGIN_L, H-10*mm, title)
    c.setFont('Helvetica', 7.5); c.setFillColor(colors.HexColor('#444')); c.drawString(MARGIN_L, H-15*mm, sub)
    c.setFont('Helvetica-Bold', 9); c.setFillColor(colors.HexColor('#444')); c.drawRightString(W-MARGIN_L, H-10*mm, tag)

def board_bg(c, board_right):
    c.setFillColor(COL['board'])
    c.roundRect(MARGIN_L-3*mm, board_bottom-4*mm, board_right-MARGIN_L+30*mm,
                board_top-board_bottom+8*mm, 3*mm, fill=1, stroke=0)

def col_headers(c, col_xs):
    c.setFont('Helvetica-Bold', 7); c.setFillColor(COL['dkgray'])
    for col in COLS:
        c.drawCentredString(col_xs[col]+HOLE_R, board_top+2*mm, col)

def zone_brackets(c, col_xs):
    def br(cols, clr, txt):
        xs = [col_xs[cc] for cc in cols]
        x1, x2 = min(xs)-0.8*mm, max(xs)+COL_W+0.8*mm
        yb = board_top+0.2*mm
        c.setStrokeColor(clr); c.setLineWidth(0.6)
        c.line(x1, yb, x2, yb); c.line(x1, yb, x1, yb+1.4*mm); c.line(x2, yb, x2, yb+1.4*mm)
        c.setFont('Helvetica', 4.6); c.setFillColor(clr)
        c.drawCentredString((x1+x2)/2, yb+2.2*mm, txt)
    br(['A','B','C'], COL['ltgray'], 'spare strips')
    br(['D'], COL['kbus_b'], 'GND')
    br(['E'], COL['gbus_b'], '3V3')
    br(['F','G','H'], COL['ltgray'], 'fan-out strips')
    br(['I'], COL['cast_b'], 'XIAO')

def draw_empty_holes(c, col_xs):
    for r in range(1, ROWS+1):
        cy = ry(r)
        for col in COLS:
            hx = col_xs[col]+HOLE_R
            if col == 'E':   fc, bc = COL['gbus'], COL['gbus_b']
            elif col == 'D': fc, bc = COL['kbus'], COL['kbus_b']
            else:            fc, bc = COL['empty'], COL['empty_b']
            c.setFillColor(fc); c.setStrokeColor(bc); c.setLineWidth(0.4)
            c.circle(hx, cy, HOLE_R, fill=1, stroke=1)

def draw_col_i_labels(c, col_xs, right=True):
    ix = col_xs['I']+HOLE_R
    for (r, silk, lbl, gpio, fn) in XIAO_I:
        cy = ry(r)
        c.setFont('Helvetica-Bold', 6.4)
        clr = COL['yellow'] if lbl in ('5V', '3V3', 'GND') else COL['cast_b']
        c.setFillColor(clr); tag = '%s %s' % (silk, lbl)
        if right:
            c.drawString(ix+HOLE_R+2*mm, cy+0.6*mm, tag)
            c.setFont('Helvetica', 5.2); c.setFillColor(COL['ltgray'])
            c.drawString(ix+HOLE_R+2*mm, cy-3.0*mm, fn[:34])
        else:
            c.drawRightString(ix-HOLE_R-2*mm, cy+0.6*mm, tag)

def draw_solder(c, col_xs, col, row, d):
    hx = col_xs[col]+HOLE_R; cy = ry(row)
    c.setFillColor(d['fill']); c.setStrokeColor(d['border']); c.setLineWidth(1.0)
    c.circle(hx, cy, HOLE_R, fill=1, stroke=1)
    lbl = d['lbl']
    if lbl:
        fs = 4.2 if len(lbl) > 4 else (5.0 if len(lbl) > 3 else 6.0)
        c.setFillColor(d['text']); c.setFont('Helvetica-Bold', fs)
        c.drawCentredString(hx, cy-1.9, lbl)

def draw_line(c, col_xs, r1, c1, r2, c2, wc):
    x1 = col_xs[c1]+HOLE_R; y1 = ry(r1); x2 = col_xs[c2]+HOLE_R; y2 = ry(r2)
    c.setStrokeColor(wc); c.setLineWidth(1.6)
    c.line(x1, y1, x2, y2)
    c.setFillColor(wc); c.circle(x1, y1, 1.4*mm, fill=1, stroke=0); c.circle(x2, y2, 1.4*mm, fill=1, stroke=0)

def draw_cast_stub(c, col_xs, r1, c1, wc):
    x1 = col_xs[c1]+HOLE_R; y1 = ry(r1)
    x2 = max(col_xs.values())+COL_W+8*mm
    c.setStrokeColor(wc); c.setLineWidth(1.4); c.setDash(2, 2)
    c.line(x1, y1, x2, y1); c.setDash()
    c.setFillColor(wc); c.circle(x1, y1, 1.3*mm, fill=1, stroke=0)
    c.setFont('Helvetica-Bold', 5); c.drawString(x2+1*mm, y1-1.5, 'castellation')

def draw_legend(c, items, y0, ncols=3):
    c.setFont('Helvetica-Bold', 7); c.setFillColor(colors.HexColor('#222'))
    c.drawString(MARGIN_L, y0, 'Legend:')
    pc = (len(items)+ncols-1)//ncols; cw = (W-2*MARGIN_L)/ncols
    for i, (fc, txt) in enumerate(items):
        lx = MARGIN_L+(i//pc)*cw; ly = y0-5*mm-(i % pc)*4.0*mm
        c.setFillColor(fc); c.setStrokeColor(COL['white']); c.setLineWidth(0.5)
        c.circle(lx+2*mm, ly+1*mm, 2*mm, fill=1, stroke=1)
        c.setFillColor(colors.HexColor('#333')); c.setFont('Helvetica', 6.5)
        c.drawString(lx+5.5*mm, ly-0.2, txt)
    return y0-5*mm-pc*4.0*mm-3*mm

# ════════════════════════════════════════════════════════════════════════════
validate()
cv = canvas.Canvas(OUTPUT, pagesize=A4)

# ── PAGE 1: FRONT (solder map) ────────────────────────────────────────────────
page_header(cv,
    'DIY E-Reader — ProtoMate for XIAO — Sheet 1 of 4: Front solder map',
    'DIRECT SOLDER (no JST). Solder each module flying-lead into the coloured hole. Col D=GND bus, E=3V3 bus, I=XIAO pads.',
    'FRONT')
board_bg(cv, br_fwd)
col_headers(cv, col_xs_fwd)
zone_brackets(cv, col_xs_fwd)
draw_empty_holes(cv, col_xs_fwd)
draw_col_i_labels(cv, col_xs_fwd, right=True)
for (col, row), d in FRONT.items():
    draw_solder(cv, col_xs_fwd, col, row, d)

front_leg = [
    (COL['lblue'],  'E-paper control (CS/DC/RST/BUSY) — direct to XIAO pad'),
    (COL['teal'],   'SPI / SD (SCK/MOSI shared, MISO/CS)'),
    (COL['gray'],   'GND lead -> col D bus'),
    (COL['gbus_b'], '3V3 lead -> col E bus'),
    (COL['purple'], 'Button signal (fwd/back direct; menu via castellation)'),
    (COL['yellow'], 'Power-sense: 5V/VBAT/ADC_BAT/VBUS tap'),
    (COL['res'],    'Divider resistor leg (VBUS-sense, battery)'),
    (COL['cast'],   'Castellation landing (flying wire to XIAO Plus pad)'),
]
leg_end = draw_legend(cv, front_leg, board_bottom-6*mm, ncols=2)
cv.setFont('Helvetica-Bold', 6.5); cv.setFillColor(COL['teal']); cv.drawString(MARGIN_L, leg_end, 'Build notes:')
cv.setFont('Helvetica', 6); cv.setFillColor(colors.HexColor('#444'))
notes = [
    'No connectors: every module wire solders on the FRONT straight into its hole. Only 7 rear jumpers exist (Sheet 2).',
    'Single-GPIO leads go directly into the XIAO pad on Column I (CS->I4, DC->I5, RST->I7, BUSY->I12, MISO->I8, SD-CS->I11, buttons->I13/I14).',
    'Shared SPI: SCK and MOSI each get ONE short fan-out jumper (I9->H9, I10->H10); the display + SD leads then land on that strip (F/G).',
    'GND and 3V3 are the col D / col E buses: fed once (I1->D1, I3->E3) and split-jumpered (D7->D8, E7->E8). Every rail lead solders into a bus hole.',
    'E-paper PWR is hardwired to 3V3 alongside VCC. Cols A-B-C are unused = free prototyping space.',
    'Menu button + battery tap + VBUS-sense are XIAO *Plus* castellations (dashed on Sheet 2), soldered as flying wires, not on Column I.',
    'SPI bus rule: init the SD FIRST, drive both CS lines HIGH at startup, no SD transfer mid-refresh (wait on BUSY).',
]
for i, n in enumerate(notes):
    cv.drawString(MARGIN_L, leg_end-(i+1)*3.4*mm, n)
cv.showPage()

# ── PAGE 2: BACK (jumpers only) ───────────────────────────────────────────────
page_header(cv,
    'DIY E-Reader — ProtoMate for XIAO — Sheet 2 of 4: Back (7 jumpers)',
    'Solder wires to the UNDERSIDE. Board shown flipped left-right. Straight runs, minimal crossing. Dashed = flying wires to XIAO Plus castellations.',
    'BACK')
board_bg(cv, br_bwd)
col_headers(cv, col_xs_bwd)
zone_brackets(cv, col_xs_bwd)
draw_empty_holes(cv, col_xs_bwd)
draw_col_i_labels(cv, col_xs_bwd, right=False)

for w in WIRES:
    wc = net_color(w['net'])
    if w['cast']:
        draw_cast_stub(cv, col_xs_bwd, w['frm'][1], w['frm'][0], wc)
    else:
        draw_line(cv, col_xs_bwd, w['frm'][1], w['frm'][0], w['to'][1], w['to'][0], wc)
# labels on jumper midpoints
for w in WIRES:
    if w['cast']:
        continue
    wc = net_color(w['net'])
    x1 = col_xs_bwd[w['frm'][0]]+HOLE_R; y1 = ry(w['frm'][1])
    x2 = col_xs_bwd[w['to'][0]]+HOLE_R; y2 = ry(w['to'][1])
    xm, ym = (x1+x2)/2, (y1+y2)/2
    txt = w['label']; cv.setFont('Helvetica-Bold', 4.8)
    tw = cv.stringWidth(txt, 'Helvetica-Bold', 4.8)
    cv.setFillColor(colors.white); cv.setFillAlpha(0.95)
    cv.roundRect(xm-tw/2-0.7*mm, ym+0.8*mm, tw+1.4*mm, 2.4*mm, 0.5*mm, fill=1, stroke=0)
    cv.setFillAlpha(1); cv.setStrokeColor(wc); cv.setLineWidth(0.7)
    cv.roundRect(xm-tw/2-0.7*mm, ym+0.8*mm, tw+1.4*mm, 2.4*mm, 0.5*mm, fill=0, stroke=1)
    cv.setFillColor(colors.HexColor('#1a1a1a')); cv.drawCentredString(xm, ym+1.4*mm, txt)

back_leg = [
    (COL['gray'],   'GND jumpers (feed I1->D1, split D7->D8, VBUS-GND I1->H1)'),
    (COL['gbus_b'], '3V3 jumpers (feed I3->E3, split E7->E8)'),
    (COL['teal'],   'SPI fan-out (SCK I9->H9, MOSI I10->H10)'),
    (COL['yellow'], 'Castellation flying wires (dashed): VBAT/ADC_BAT/VBUS/MENU'),
]
leg2_end = draw_legend(cv, back_leg, board_bottom-6*mm, ncols=2)
cv.setFont('Helvetica', 6); cv.setFillColor(colors.HexColor('#444'))
bnotes = [
    'Just 7 rear jumpers. The two long ones are the unavoidable rail feeds (XIAO pad -> central bus); the rest are short.',
    'Split jumpers (D7->D8, E7->E8) bridge the bus 7/8 boundary so the high rows (8-14) are powered.',
    'Fan-out jumpers (I9->H9, I10->H10) turn a single shared SPI pad into a strip both the display and SD leads can reach.',
]
for i, n in enumerate(bnotes):
    cv.drawString(MARGIN_L, leg2_end-(i+1)*3.4*mm, n)
cv.showPage()

# ── PAGE 3: SOLDER MAP + WIRING LIST ──────────────────────────────────────────
cv.setFillColor(colors.HexColor('#f8f8f4')); cv.rect(0, 0, W, H, fill=1, stroke=0)
cv.setFillColor(colors.HexColor('#1a1a1a')); cv.setFont('Helvetica-Bold', 12)
cv.drawString(MARGIN_L, H-15*mm, 'DIY E-Reader — ProtoMate for XIAO — Sheet 3 of 4: Solder map')
cv.setFont('Helvetica', 7.5); cv.setFillColor(colors.HexColor('#555'))
cv.drawString(MARGIN_L, H-21*mm, 'Every module flying-lead and where it solders. Then the 7 rear jumpers + the castellation flying wires.')

# module lead table
lh = ['Module', 'Signal', 'Net', 'Solder hole', 'Notes']; lcw = [24*mm, 20*mm, 18*mm, 24*mm, 92*mm]
ltw = sum(lcw); ltx = MARGIN_L; lty = H-27*mm; lrh = 5.4*mm
cv.setFillColor(colors.HexColor('#1a1a1a')); cv.rect(ltx, lty-lrh, ltw, lrh, fill=1, stroke=0)
cv.setFillColor(colors.white); cv.setFont('Helvetica-Bold', 7); _c = ltx
for k, h in enumerate(lh):
    cv.drawString(_c+1.5*mm, lty-lrh+1.8*mm, h); _c += lcw[k]
lty -= lrh; _alt = False; _prev = None
def _note_for(net, sig):
    if net == 'GND': return 'to GND bus (col D)'
    if net == '3V3': return 'to 3V3 bus (col E)' + (' — PWR hardwired to 3V3' if sig == 'PWR' else '')
    if net in ('D8', 'D10'): return 'shared SPI strip (via fan-out jumper)'
    if net == 'MENU': return 'shares GPIO42 castellation landing'
    return 'direct to XIAO pad %s (I%d)' % (net, NET_ROW.get(net, 0))
for comp, sig, net, col, row in LEADS:
    bg = colors.HexColor('#f0f0e8') if not _alt else colors.HexColor('#e4e4dc')
    cv.setFillColor(bg); cv.rect(ltx, lty-lrh, ltw, lrh, fill=1, stroke=0)
    _c = ltx
    for k, cell in enumerate([comp if comp != _prev else '', sig, net, '%s%d' % (col, row), _note_for(net, sig)]):
        cv.setFillColor(net_color(net) if k == 2 else colors.HexColor('#1a1a1a'))
        cv.setFont('Helvetica-Bold' if k in (0, 3) else 'Helvetica', 6.4)
        cv.drawString(_c+1.5*mm, lty-lrh+1.6*mm, str(cell)); _c += lcw[k]
    lty -= lrh; _alt = not _alt; _prev = comp

# jumper + castellation list
jty = lty-6*mm
cv.setFont('Helvetica-Bold', 8); cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, jty, 'Rear jumpers (7) + castellation flying wires')
jh = ['Net', 'From', 'To', 'Purpose']; jcw = [22*mm, 18*mm, 22*mm, 116*mm]
jtw = sum(jcw); jtx = MARGIN_L; jty -= 3*mm; jrh = 5.4*mm
cv.setFillColor(colors.HexColor('#1a1a1a')); cv.rect(jtx, jty-jrh, jtw, jrh, fill=1, stroke=0)
cv.setFillColor(colors.white); cv.setFont('Helvetica-Bold', 7); _c = jtx
for k, h in enumerate(jh):
    cv.drawString(_c+1.5*mm, jty-jrh+1.8*mm, h); _c += jcw[k]
jty -= jrh; _alt = False
for w in WIRES:
    bg = colors.HexColor('#f0f0e8') if not _alt else colors.HexColor('#e4e4dc')
    cv.setFillColor(bg); cv.rect(jtx, jty-jrh, jtw, jrh, fill=1, stroke=0)
    _frm = '%s%d' % w['frm']; _to = 'CAST' if w['cast'] else '%s%d' % w['to']; _c = jtx
    cv.setFillColor(net_color(w['net'])); cv.circle(_c+2.4*mm, jty-jrh+jrh/2, 1.4*mm, fill=1, stroke=0)
    cv.setFillColor(colors.HexColor('#1a1a1a')); cv.setFont('Helvetica-Bold', 6.5)
    cv.drawString(_c+5.2*mm, jty-jrh+1.6*mm, str(w['net'])); _c += jcw[0]
    cv.setFont('Helvetica', 6.8)
    cv.drawString(_c+1.5*mm, jty-jrh+1.6*mm, _frm); _c += jcw[1]
    cv.drawString(_c+1.5*mm, jty-jrh+1.6*mm, _to); _c += jcw[2]
    cv.setFont('Helvetica', 5.8); cv.drawString(_c+1.5*mm, jty-jrh+1.6*mm, str(w['desc'])[:96])
    jty -= jrh; _alt = not _alt
cv.showPage()

# ── PAGE 4: REFERENCE ─────────────────────────────────────────────────────────
cv.setFillColor(colors.HexColor('#f8f8f4')); cv.rect(0, 0, W, H, fill=1, stroke=0)
cv.setFillColor(colors.HexColor('#1a1a1a')); cv.setFont('Helvetica-Bold', 12)
cv.drawString(MARGIN_L, H-15*mm, 'DIY E-Reader — ProtoMate for XIAO — Sheet 4 of 4: Reference')
cv.setFont('Helvetica', 7.5); cv.setFillColor(colors.HexColor('#555'))
cv.drawString(MARGIN_L, H-21*mm, 'Column I = XIAO pad map (fixed) + on-board parts.')

cv.setFont('Helvetica-Bold', 8); cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, H-28*mm, 'Column I — XIAO ESP32-S3 pad map')
ih = ['Row', 'Silk', 'XIAO', 'GPIO', 'esp-read function']; icw = [12*mm, 14*mm, 14*mm, 18*mm, 78*mm]
itw = sum(icw); itx = MARGIN_L; ity = H-32*mm; irh = 5.0*mm
cv.setFillColor(colors.HexColor('#333')); cv.rect(itx, ity-irh, itw, irh, fill=1, stroke=0)
cv.setFillColor(colors.white); cv.setFont('Helvetica-Bold', 6.5); _c = itx
for k, h in enumerate(ih):
    cv.drawString(_c+1.5*mm, ity-irh+1.6*mm, h); _c += icw[k]
ity -= irh; _alt = False
for (r, silk, lbl, gpio, fn) in XIAO_I:
    bg = colors.HexColor('#f0f0e8') if not _alt else colors.HexColor('#e4e4dc')
    cv.setFillColor(bg); cv.rect(itx, ity-irh, itw, irh, fill=1, stroke=0)
    cv.setFillColor(colors.HexColor('#1a1a1a')); _c = itx
    for k, cell in enumerate(['I%d' % r, silk, lbl, gpio, fn]):
        cv.setFont('Helvetica-Bold' if k == 0 else 'Helvetica', 6.4)
        cv.drawString(_c+1.5*mm, ity-irh+1.5*mm, str(cell)); _c += icw[k]
    ity -= irh; _alt = not _alt

# on-board parts
PARTBOM = []
for p in PARTS:
    holes = ' '.join('%s%d' % (c, r) for (_ro, c, r) in p['legs'])
    PARTBOM.append((p['ref'], '220k 1%', holes, p['desc'][:66]))
for net, hole, pad, note in CASTELLATIONS:
    PARTBOM.append(('cast:'+net, 'flying wire', '%s%d->%s' % (hole[0], hole[1], pad), note[:66]))
bh = ['Ref', 'Value', 'Holes', 'Notes']; bcw = [26*mm, 26*mm, 30*mm, 96*mm]
btw = sum(bcw); btx = MARGIN_L; bty = ity-8*mm; brh = 5.2*mm
cv.setFont('Helvetica-Bold', 8); cv.setFillColor(colors.HexColor('#1a1a1a'))
cv.drawString(MARGIN_L, bty+2*mm, 'On-board parts (resistors) + castellation flying wires')
cv.setFillColor(colors.HexColor('#333')); cv.rect(btx, bty-brh, btw, brh, fill=1, stroke=0)
cv.setFillColor(colors.white); cv.setFont('Helvetica-Bold', 6.5); _c = btx
for k, h in enumerate(bh):
    cv.drawString(_c+1.5*mm, bty-brh+1.6*mm, h); _c += bcw[k]
bty -= brh; _alt = False
for row in PARTBOM:
    bg = colors.HexColor('#f0f0e8') if not _alt else colors.HexColor('#e4e4dc')
    cv.setFillColor(bg); cv.rect(btx, bty-brh, btw, brh, fill=1, stroke=0)
    cv.setFillColor(colors.HexColor('#1a1a1a')); _c = btx
    for k, cell in enumerate(row):
        cv.setFont('Helvetica-Bold' if k == 0 else 'Helvetica', 6.0 if k == 3 else 6.6)
        cv.drawString(_c+1.5*mm, bty-brh+1.5*mm, str(cell)[:66]); _c += bcw[k]
    bty -= brh; _alt = not _alt

cv.save()
print('Wrote', OUTPUT)
