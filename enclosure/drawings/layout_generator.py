#!/usr/bin/env python3
"""2D reference drawings of the e-reader case, read straight from the CAD model.

    python3 layout_generator.py [path/to/ereader-case.sc]

Every size and position comes from `enclosure/ereader-case.sc` (SolidCraft).
The .sc file is a zip; its `document.json` holds the parameters and the
feature list. This script works out each feature's size from its expressions
and draws three PNGs next to itself:

  component-layout.png   front view, looking at the screen, spine on the LEFT
  back-view.png          back view, spine on the RIGHT (X mirrored)
  section.png            cuts across the width, through the keys and the battery

So when the model changes, re-run this and the drawings follow. If a feature
the drawings rely on is renamed or deleted, the script stops and names it.

It writes SVG (standard library only) and turns it into PNG with
`rsvg-convert` (librsvg; `brew install librsvg`).

Model frame: X across the width (0 = spine edge), Y along the length
(0 = bottom edge), Z depth (0 = back of the stowed cover, T = front face).
"""
import json
import math
import re
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
MODEL = HERE.parent / 'ereader-case.sc'
BG = '#f5f5f5'
CASE_FILL = '#d6d1c4'
CASE_LINE = '#555'


# ======================================================== expression maths
UNITS = {'mm': 1.0, 'cm': 10.0, 'm': 1000.0, 'in': 25.4, 'deg': 1.0}
FUNCS = {
    'sqrt': math.sqrt, 'abs': abs, 'min': min, 'max': max,
    'sin': lambda d: math.sin(math.radians(d)),
    'cos': lambda d: math.cos(math.radians(d)),
    'tan': lambda d: math.tan(math.radians(d)),
}
TOKEN = re.compile(r'\s*(?:(\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+)|([A-Za-z_]\w*)|(\*\*|[-+*/^(),]))')


class ExprError(Exception):
    pass


def tokenize(text):
    pos, out = 0, []
    text = text.strip()
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise ExprError(f'cannot read {text!r} at {text[pos:]!r}')
        num, name, op = m.groups()
        out.append(('num', float(num)) if num else ('name', name) if name else ('op', op))
        pos = m.end()
    return out


class Parser:
    """Small recursive-descent calculator: + - * / ^, brackets, units, names.

    Nothing is passed to Python's eval; names resolve through `lookup`."""

    def __init__(self, text, lookup):
        self.text, self.toks, self.i, self.lookup = text, tokenize(text), 0, lookup

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self, kind=None, val=None):
        t = self.peek()
        if t[0] is None or (kind and t[0] != kind) or (val and t[1] != val):
            raise ExprError(f'unexpected {t[1]!r} in {self.text!r}')
        self.i += 1
        return t

    def run(self):
        v = self.expr()
        if self.peek()[0] is not None:
            raise ExprError(f'left over {self.peek()[1]!r} in {self.text!r}')
        return v

    def expr(self):
        v = self.term()
        while self.peek() in (('op', '+'), ('op', '-')):
            v = v + self.term() if self.take()[1] == '+' else v - self.term()
        return v

    def term(self):
        v = self.unary()
        while self.peek() in (('op', '*'), ('op', '/')):
            v = v * self.unary() if self.take()[1] == '*' else v / self.unary()
        return v

    def unary(self):
        if self.peek() in (('op', '-'), ('op', '+')):
            return -self.unary() if self.take()[1] == '-' else self.unary()
        return self.power()

    def power(self):
        v = self.atom()
        if self.peek() in (('op', '^'), ('op', '**')):
            self.take()
            v = v ** self.unary()
        return v

    def unit(self, v):
        t = self.peek()
        if t[0] == 'name' and t[1] in UNITS:
            self.take()
            return v * UNITS[t[1]]
        return v

    def atom(self):
        kind, val = self.peek()
        if kind == 'num':
            self.take()
            return self.unit(val)
        if (kind, val) == ('op', '('):
            self.take()
            v = self.expr()
            self.take('op', ')')
            return self.unit(v)
        if kind == 'name':
            self.take()
            if self.peek() == ('op', '(') and val in FUNCS:
                self.take()
                args = [self.expr()]
                while self.peek() == ('op', ','):
                    self.take()
                    args.append(self.expr())
                self.take('op', ')')
                return FUNCS[val](*args)
            return self.lookup(val)
        raise ExprError(f'unexpected {val!r} in {self.text!r}')


# ================================================================ the model
class ModelError(SystemExit):
    pass


class Model:
    def __init__(self, path):
        try:
            with zipfile.ZipFile(path) as z:
                doc = json.loads(z.read('document.json'))
        except (OSError, KeyError, zipfile.BadZipFile, ValueError) as e:
            raise ModelError(f'cannot read the model {path}: {e}')
        self.path = path
        self.raw = {p['name']: p['expr'] for p in doc['params']}
        self.vals, self.busy = {}, set()
        self.features = [f for f in doc['features'] if not f.get('suppressed')]
        self.by_name = {f['name']: f for f in doc['features']}
        self.colors = {k: v['color'] for k, v in
                       doc.get('appearances', {}).get('bodies', {}).items()}
        self.moves = {}
        self.stale = set()

    # -- numbers
    def p(self, name):
        if name in self.vals:
            return self.vals[name]
        if name not in self.raw:
            raise ModelError(f'the model has no parameter named {name!r}')
        if name in self.busy:
            raise ModelError(f'parameter {name!r} refers to itself')
        self.busy.add(name)
        v = self.ev(self.raw[name])
        self.busy.discard(name)
        self.vals[name] = v
        return v

    def ev(self, x):
        if isinstance(x, (int, float)):
            return float(x)
        try:
            return float(Parser(str(x), self.p).run())
        except ExprError as e:
            raise ModelError(f'bad expression in the model: {e}')

    # -- features
    def feature(self, name):
        f = self.by_name.get(name)
        if f is None:
            raise ModelError(f'the model has no feature named {name!r}; the drawings need it. '
                             f'Was it renamed in {self.path.name}?')
        if f.get('suppressed'):
            raise ModelError(f'feature {name!r} is suppressed in the model; the drawings need it')
        return f

    def prefixed(self, prefix):
        return [f for f in self.features if f['name'].startswith(prefix)]

    def box(self, name):
        """(x0, x1, y0, y1, z0, z1) of a box feature."""
        return prim_box(self, self.feature(name))

    def cyl(self, name):
        """(x, y, z, r, h, axis) of a cylinder feature."""
        f = self.feature(name)
        if f['type'] != 'cylinder':
            raise ModelError(f'feature {name!r} is a {f["type"]}, expected a cylinder')
        x, y, z = (self.ev(v) for v in f['base'])
        return x, y, z, self.ev(f['radius']), self.ev(f['height']), tuple(f['axis'])

    def sketch_loop(self, name):
        """Closed profile of an XZ-plane sketch as [(X, Z), ...]."""
        f = self.feature(name)
        plane = f.get('plane', {})
        base = plane.get('base', plane)
        if base.get('name') != 'XZ':
            raise ModelError(f'sketch {name!r} is not on the XZ plane; cannot draw it')
        sk = f['sketch']
        pts = sk['points']
        # Points tied to parameters use the parameter value, not the saved
        # position, which goes stale when a parameter changes after a save.
        # Free points (arc ends, tangent points) keep their saved position.
        where = []
        for pt in pts:
            pos = list(pt['pos'])
            for i, k in enumerate('xy'):
                if k in (pt.get('exprs') or {}):
                    v = self.ev(pt['exprs'][k])
                    if abs(v - pos[i]) > 1e-3:
                        self.stale.add(name)
                    pos[i] = v
            where.append(pos)
        segs = []
        for c in sk['curves']:
            if c.get('construction'):
                continue
            a, b = where[c['a']], where[c['b']]
            if c['type'] == 'line':
                segs.append([tuple(a), tuple(b)])
            elif c['type'] == 'arc':
                segs.append(arc_points(a, b, where[c['c']]))
            else:
                raise ModelError(f'sketch {name!r} has a {c["type"]} curve; only lines and arcs '
                                 'are supported')
        loop = chain(segs, name)
        return [(x, -y) for x, y in loop]    # sketch y is -Z on the XZ plane

    def extrude_y(self, f):
        """Y range of an extrude whose sketch is on (an offset of) the XZ plane."""
        i = self.features.index(f)
        prev = [g for g in self.features[:i] if g['type'] == 'sketch']
        if not prev:
            raise ModelError(f'extrude {f["name"]!r} has no sketch before it')
        sk = prev[-1]
        plane = sk.get('plane', {})
        y0 = self.ev(plane['distance']) if plane.get('type') == 'offset' else 0.0
        ext = f['extent']
        if ext.get('direction', 'positive') != 'positive':
            raise ModelError(f'extrude {f["name"]!r} is not one-sided positive; not supported')
        return sk, y0, y0 + self.ev(ext['distance'])

    def extrude_on_xz(self, f):
        """True when the sketch an extrude uses sits on (an offset of) the XZ plane."""
        i = self.features.index(f)
        prev = [g for g in self.features[:i] if g['type'] == 'sketch']
        if not prev:
            return False
        plane = prev[-1].get('plane', {})
        return plane.get('base', plane).get('name') == 'XZ'

    def body_ops(self, body, _depth=0):
        """[(op, feature)] that build `body`, op 'join' or 'cut', in timeline order.

        Follows combine features into their tool bodies. Fillets, chamfers and
        plan-rounding intersects are skipped (they only touch corners)."""
        ops, found = [], False
        for f in self.features:
            op, names = f.get('operation'), f.get('body_names') or []
            if op == 'new_body' and body in names:
                ops.append(('join', f))
                found = True
            elif f['type'] in ('box', 'cylinder') and body in (f.get('participants') or []):
                if op in ('join', 'cut'):
                    ops.append((op, f))
            elif f['type'] == 'extrude' and body in (f.get('targets') or []):
                if op in ('join', 'cut'):
                    ops.append((op, f))
            elif f['type'] == 'move' and body in (f.get('bodies') or []):
                # A copying move (used for print copies) leaves this body where it is.
                if not f.get('copy'):
                    self.add_move(f, [g for _, g in ops])
            elif f['type'] == 'combine' and f.get('target') == body and op in ('join', 'cut'):
                for tool in f.get('tools', []):
                    for o, g in self.body_ops(tool, _depth + 1):
                        # Shallow textures sketched flat (key-top grooves) are
                        # too small to draw; skip them.
                        if g['type'] == 'extrude' and not self.extrude_on_xz(g):
                            continue
                        if o == 'join':
                            ops.append((op, g))
        if not found:
            raise ModelError(f'the model has no body named {body!r}; the drawings need it')
        return ops

    def add_move(self, f, feats):
        """Record a move (turn about a Z axis, then shift) for features made so far."""
        ax = f.get('rotate_axis', [0, 0, 1])
        ang = self.ev(f.get('angle', 0))
        if ang and (abs(ax[0]) > 1e-9 or abs(ax[1]) > 1e-9):
            raise ModelError(f'move {f["name"]!r} turns about an axis other than Z; '
                             'the drawings cannot show that')
        if ang and ax[2] < 0:
            ang = -ang
        org = [self.ev(v) for v in f.get('origin', [0, 0, 0])]
        tr = [self.ev(v) for v in f.get('translate', [0, 0, 0])]
        for g in feats:
            # An extrude can only be shifted straight along Z (the closed
            # cover sitting on its bumpers); its plan and section follow.
            if g['type'] == 'extrude' and not ang and not tr[0] and not tr[1]:
                pass
            elif g['type'] not in ('box', 'cylinder'):
                raise ModelError(f'move {f["name"]!r} moves a {g["type"]}; not supported')
            self.moves.setdefault(g['name'], []).append((org, ang, tr))

    def plan_xy(self, f, x, y):
        """Plan point (x, y) of feature f after any moves."""
        for (ox, oy, _), ang, (tx, ty, _) in self.moves.get(f['name'], []):
            a = math.radians(ang)
            dx, dy = x - ox, y - oy
            x, y = ox + dx * math.cos(a) - dy * math.sin(a) + tx, \
                oy + dx * math.sin(a) + dy * math.cos(a) + ty
        return x, y

    def z_shift(self, f):
        return sum(tr[2] for _, _, tr in self.moves.get(f['name'], []))

    def color(self, body, default=(90, 90, 90)):
        return tuple(self.colors.get(body, default))


def prim_box(m, f):
    if f['type'] != 'box':
        raise ModelError(f'feature {f["name"]!r} is a {f["type"]}, expected a box')
    x, y, z = (m.ev(v) for v in f['corner'])
    dx, dy, dz = m.ev(f['length']), m.ev(f['width']), m.ev(f['height'])
    if f.get('centred'):              # 'corner' is then the middle of the box
        x, y, z = x - dx / 2, y - dy / 2, z - dz / 2
    xs, ys, zs = sorted((x, x + dx)), sorted((y, y + dy)), sorted((z, z + dz))
    return xs[0], xs[1], ys[0], ys[1], zs[0], zs[1]


def arc_points(a, b, c, n=16):
    """Short arc from a to b about centre c, as points."""
    r = math.dist(a, c)
    t0 = math.atan2(a[1] - c[1], a[0] - c[0])
    t1 = math.atan2(b[1] - c[1], b[0] - c[0])
    d = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi
    return [(c[0] + r * math.cos(t0 + d * i / n), c[1] + r * math.sin(t0 + d * i / n))
            for i in range(n + 1)]


def chain(segs, name, tol=1e-3):
    loop = list(segs.pop(0))
    while segs:
        end = loop[-1]
        for i, s in enumerate(segs):
            if math.dist(s[0], end) < tol:
                loop += s[1:]
                break
            if math.dist(s[-1], end) < tol:
                loop += s[::-1][1:]
                break
        else:
            raise ModelError(f'sketch {name!r} is not one closed loop; cannot draw it')
        segs.pop(i)
    if math.dist(loop[0], loop[-1]) > tol:
        raise ModelError(f'sketch {name!r} does not close')
    return loop[:-1]


# --------------------------------------------- shapes of a feature, 2 ways
def moved_plan(m, f):
    """Footprint of a moved box (a turned polygon) or Z cylinder."""
    if f['type'] == 'cylinder':
        x, y, z = (m.ev(v) for v in f['base'])
        if abs(f['axis'][2]) < 0.5:
            raise ModelError(f'moved cylinder {f["name"]!r} is not upright; not supported')
        return ('circle', *m.plan_xy(f, x, y), m.ev(f['radius']))
    x0, x1, y0, y1, *_ = prim_box(m, f)
    return ('poly', [m.plan_xy(f, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])


def moved_section(m, f, yc):
    sh = moved_plan(m, f)
    dz = m.z_shift(f)
    if sh[0] == 'circle':
        _, x, y, r = sh
        if abs(yc - y) >= r:
            return None
        w = math.sqrt(r * r - (yc - y) ** 2)
        z, h, a = m.ev(f['base'][2]), m.ev(f['height']), f['axis'][2]
        return ('rect', x - w, x + w, *sorted((z + dz, z + dz + h * a)))
    pts, xs = sh[1], []
    for (xa, ya), (xb, yb) in zip(pts, pts[1:] + pts[:1]):
        if (ya - yc) * (yb - yc) <= 0 and ya != yb:
            xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
    if len(xs) < 2:
        return None
    *_, z0, z1 = prim_box(m, f)
    return ('rect', min(xs), max(xs), z0 + dz, z1 + dz)


def plan_shape(m, f):
    """Footprint seen along Z: ('rect', x0, x1, y0, y1) or ('circle', x, y, r)."""
    t = f['type']
    if f['name'] in m.moves and t != 'extrude':
        return moved_plan(m, f)
    if t == 'box':
        x0, x1, y0, y1, *_ = prim_box(m, f)
        return ('rect', x0, x1, y0, y1)
    if t == 'cylinder':
        x, y, z = (m.ev(v) for v in f['base'])
        r, h, ax = m.ev(f['radius']), m.ev(f['height']), [abs(a) for a in f['axis']]
        if ax[2] > 0.5:
            return ('circle', x, y, r)
        if ax[1] > 0.5:
            return ('rect', x - r, x + r, *sorted((y, y + h * f['axis'][1])))
        return ('rect', *sorted((x, x + h * f['axis'][0])), y - r, y + r)
    if t == 'extrude':
        sk, y0, y1 = m.extrude_y(f)
        xs = [p[0] for p in m.sketch_loop(sk['name'])]
        return ('rect', min(xs), max(xs), y0, y1)
    return None


def section_shape(m, f, yc):
    """What a feature leaves on the plane Y = yc, in (X, Z), or None."""
    t = f['type']
    if f['name'] in m.moves and t != 'extrude':
        return moved_section(m, f, yc)
    if t == 'box':
        x0, x1, y0, y1, z0, z1 = prim_box(m, f)
        return ('rect', x0, x1, z0, z1) if y0 <= yc <= y1 else None
    if t == 'cylinder':
        x, y, z = (m.ev(v) for v in f['base'])
        r, h, axis = m.ev(f['radius']), m.ev(f['height']), f['axis']
        if abs(axis[2]) > 0.5:
            if abs(yc - y) >= r:
                return None
            w = math.sqrt(r * r - (yc - y) ** 2)
            return ('rect', x - w, x + w, *sorted((z, z + h * axis[2])))
        if abs(axis[1]) > 0.5:
            lo, hi = sorted((y, y + h * axis[1]))
            return ('circle', x, z, r) if lo <= yc <= hi else None
        if abs(yc - y) >= r:
            return None
        w = math.sqrt(r * r - (yc - y) ** 2)
        return ('rect', *sorted((x, x + h * axis[0])), z - w, z + w)
    if t == 'extrude':
        sk, y0, y1 = m.extrude_y(f)
        dz = m.z_shift(f)
        loop = [(x, z + dz) for x, z in m.sketch_loop(sk['name'])]
        return ('poly', loop) if y0 <= yc <= y1 else None
    return None


# =================================================================== svg
def hexc(rgb):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, c))) for c in rgb)


def light(rgb, k=0.72):
    return hexc([c + (255 - c) * k for c in rgb])


def ink(rgb):
    """A readable text colour from a body colour."""
    lum = (0.3 * rgb[0] + 0.59 * rgb[1] + 0.11 * rgb[2]) / 255
    return hexc([c * (0.45 if lum > 0.6 else 0.8) for c in rgb])


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def fmt(v):
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return '0' if s == '-0' else s


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts, self.nclip = w, h, [], 0
        self.add('<defs><marker id="arr" viewBox="0 0 10 10" refX="10" refY="5" '
                 'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                 '<path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker>'
                 '<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" '
                 'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" '
                 'stroke="#888" stroke-width="1"/></pattern></defs>')

    def add(self, s):
        self.parts.append(s)

    @staticmethod
    def _style(stroke, fill, sw, dash, op, extra=''):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        return (f'fill="{fill}" fill-opacity="{op}" stroke="{stroke}" '
                f'stroke-width="{sw}"{d}{extra}')

    def rect(self, x, y, w, h, stroke='#333', fill='none', sw=1.2, dash=None, rx=0, op=1.0,
             clip=None):
        c = f' clip-path="url(#{clip})"' if clip else ''
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" '
                 f'height="{max(h, 0):.1f}" rx="{rx:.1f}" '
                 f'{self._style(stroke, fill, sw, dash, op, c)}/>')

    def circle(self, cx, cy, r, stroke='#333', fill='none', sw=1.2, dash=None, op=1.0,
               clip=None):
        c = f' clip-path="url(#{clip})"' if clip else ''
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                 f'{self._style(stroke, fill, sw, dash, op, c)}/>')

    def path(self, d, stroke='#333', fill='none', sw=1.2, dash=None, op=1.0, clip=None,
             extra=''):
        c = f' clip-path="url(#{clip})"' if clip else ''
        self.add(f'<path d="{d}" {self._style(stroke, fill, sw, dash, op, c + extra)}/>')

    def clip_path(self, d):
        self.nclip += 1
        cid = f'clip{self.nclip}'
        self.add(f'<clipPath id="{cid}"><path d="{d}"/></clipPath>')
        return cid

    def line(self, x1, y1, x2, y2, stroke='#333', sw=1.0, dash=None, arrows=False):
        da = f' stroke-dasharray="{dash}"' if dash else ''
        mk = ' marker-start="url(#arr)" marker-end="url(#arr)"' if arrows else ''
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{da}{mk}/>')

    def text(self, x, y, s, size=11, fill='#222', anchor='start', weight='normal'):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="Helvetica,Arial,sans-serif" '
                 f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
                 f'text-anchor="{anchor}">{esc(s)}</text>')

    def lines(self, x, y, rows, size=9.5, fill='#555'):
        for i, r in enumerate(rows):
            self.text(x, y + i * size * 1.5, r, size=size, fill=fill)
        return y + len(rows) * size * 1.5

    def save(self, name):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}"><rect width="100%" height="100%" '
               f'fill="{BG}"/>' + ''.join(self.parts) + '</svg>')
        out_svg, out_png = HERE / f'{name}.svg', HERE / f'{name}.png'
        out_svg.write_text(svg)
        try:
            subprocess.run(['rsvg-convert', '-o', str(out_png), str(out_svg)], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            sys.exit(f'rsvg-convert failed ({e}). Install it with: brew install librsvg. '
                     f'The SVG was left at {out_svg}')
        out_svg.unlink()
        print(f'wrote {out_png.name}  ({self.w}x{self.h})')


class Callouts:
    """Labels stacked down a margin, each with a leader to its feature."""

    def __init__(self, svg, x, anchor, top, size=9.5):
        self.s, self.x, self.anchor, self.top, self.size, self.items = svg, x, anchor, top, size, []

    def add(self, fx, fy, rows, color='#333'):
        self.items.append((fy, fx, rows, color))

    def draw(self):
        y = self.top
        step = self.size * 1.3
        for fy, fx, rows, color in sorted(self.items, key=lambda t: t[0]):
            ty = max(y, fy - step * (len(rows) - 1) / 2)
            ex = self.x + (4 if self.anchor == 'end' else -4)
            self.s.line(ex, ty - 4, fx, fy, stroke=color, sw=0.7)
            self.s.circle(fx, fy, 1.6, stroke=color, fill=color, sw=0.5)
            for i, r in enumerate(rows):
                self.s.text(self.x, ty + i * step, r, size=self.size, fill=color,
                            anchor=self.anchor, weight='bold' if i == 0 else 'normal')
            y = ty + step * len(rows) + 6


def dim_h(s, x0, x1, y, txt, size=10):
    s.line(x0, y, x1, y, sw=0.9, arrows=True)
    s.text((x0 + x1) / 2, y + 13, txt, size=size, anchor='middle')


def dim_v(s, x, y0, y1, txt, size=10, left=False):
    s.line(x, y0, x, y1, sw=0.9, arrows=True)
    s.text(x - 5 if left else x + 5, (y0 + y1) / 2 + 4, txt, size=size,
           anchor='end' if left else 'start')


# ============================================================== geometry
class Case:
    """The numbers the drawings use, all read from the model."""

    # body name in the model -> plain label
    PARTS = {
        'REF_Battery': 'Battery', 'REF_HAT': 'Driver HAT', 'REF_XIAO': 'XIAO ESP32-S3 Plus',
        'REF_Adapter': 'FFC adapter', 'REF_Storage': 'Storage board',
        'REF_Antenna': 'WiFi antenna sticker', 'REF_PowerSwitch': 'Power switch',
        'REF_SwitchBack': 'Back key switch', 'REF_SwitchFwd': 'Forward key switch',
        'REF_SwitchMenu': 'Menu key switch', 'REF_Magnets': 'Cover magnets',
        'OPT_HallSensor': 'Hall sensor (optional)', 'REF_BulkCap': '22uF capacitor',
    }

    def __init__(self, m):
        self.m = m
        P = m.p
        self.W, self.L, self.T = P('W'), P('L'), P('T')
        self.r_corner, self.sh, self.ht = P('r_corner'), P('sh'), P('ht')
        self.sh_r = P('sh_r')                      # the right wall is thicker
        self.tongue = m.box('RightTongue')         # hook joint on the right edge
        self.hook_cut = m.feature('RightHookCut')
        self.x_g0, self.x_g1 = P('x_g0'), P('x_g1')
        self.r_palm, self.t_h, self.zr = P('r_palm'), P('t_h'), P('zr')
        self.cover_x0 = P('a0')
        self.glass = m.box('RefGlass')
        self.window = m.box('Window')
        self.win_ch = m.ev(m.feature('WindowChamfer')['distance'])
        self.front_ch = m.ev(m.feature('FrontChamfer')['distance'])
        self.battery = m.box('RefBattery')
        self.hat = m.box('RefHatPcb')
        self.xiao = m.box('RefXiaoBoard')
        self.adapter = m.box('RefAdapter')
        self.storage = m.box('RefStorage')
        self.antenna = m.box('RefAntenna')
        self.power = m.box('RefSw')
        self.hall = m.box('RefHall')
        self.sw_back, self.sw_fwd, self.sw_menu = (m.box(n) for n in ('RefSwB', 'RefSwF', 'RefSwM'))
        self.mags = [m.cyl(n) for n in ('RefMag1', 'RefMag2', 'RefMag3', 'RefMag4')]
        self.chin_mags = [m.cyl(n) for n in ('RefMag0a', 'RefMag0b')]
        self.lp = [m.cyl('LpC'), m.cyl('LpU')]
        self.pins = [m.cyl('PinReset'), m.cyl('PinBoot')]
        self.usb = m.box('UsbMid')
        self.usb_r = m.cyl('UsbL')[3]
        self.sw_track = m.box('SwRecess')
        self.sw_cap = m.box('SwCapMid')
        self.cap_r = m.cyl('SwCapL')[3]
        self.bosses = {n[5:]: m.cyl(n) for n in
                       ('TBossS7', 'TBossS8', 'TBossS1', 'TBossS6', 'TBossS5')}
        self.hinges = [m.box('HingeGroove1'), m.box('HingeGroove2')]
        self.cover_box = m.box('CovToolBox')
        self.tub = m.sketch_loop('TubProfile')
        self.cav = m.sketch_loop('CavProfile')
        self.cover = m.sketch_loop('CoverProfile')
        # where the back surface sits under the spine and under the display
        self.z_spine_back = min(z for x, z in self.tub)
        self.z_disp_back = min(z for x, z in self.tub if x > self.x_g1 + 1)
        self.z_floor_spine = min(z for x, z in self.cav)
        self.z_floor_disp = min(z for x, z in self.cav if x > self.x_g1 + 1)
        # section planes: through the back key, and through the battery middle
        self.y_keys = (self.sw_back[2] + self.sw_back[3]) / 2
        self.y_batt = (self.battery[2] + self.battery[3]) / 2


def size3(b):
    return f'{fmt(b[1] - b[0])} x {fmt(b[3] - b[2])} x {fmt(b[5] - b[4])}'


def xr(b):
    return f'X {fmt(b[0])}-{fmt(b[1])}'


def yr(b):
    return f'Y {fmt(b[2])}-{fmt(b[3])}'


def zr_(b):
    return f'Z {fmt(b[4])}-{fmt(b[5])}'


# ============================================================ plan views
class Plan:
    """Plan mm (X, Y) to px. mirror=True is the back view (X flipped)."""

    def __init__(self, s, c, ox, oy, k, mirror=False):
        self.s, self.c, self.ox, self.oy, self.k, self.mirror = s, c, ox, oy, k, mirror

    def px(self, x):
        return self.ox + ((self.c.W - x) if self.mirror else x) * self.k

    def py(self, y):
        return self.oy + (self.c.L - y) * self.k

    def box(self, x0, x1, y0, y1, **kw):
        a, b = sorted((self.px(x0), self.px(x1)))
        self.s.rect(a, self.py(y1), b - a, (y1 - y0) * self.k, **kw)

    def dot(self, x, y, r, **kw):
        self.s.circle(self.px(x), self.py(y), r * self.k, **kw)

    def outline(self, inset=0.0, **kw):
        c = self.c
        r = max(c.r_corner - inset, 0)
        self.s.rect(self.ox + inset * self.k, self.oy + inset * self.k,
                    (c.W - 2 * inset) * self.k, (c.L - 2 * inset) * self.k, rx=r * self.k, **kw)

    def vline(self, x, **kw):
        self.s.line(self.px(x), self.py(0), self.px(x), self.py(self.c.L), **kw)

    def shape(self, sh, **kw):
        if sh is None:
            return
        if sh[0] == 'rect':
            self.box(*sh[1:], **kw)
        elif sh[0] == 'poly':
            kw.pop('rx', None)
            self.s.path('M' + ' L'.join(f'{self.px(x):.1f},{self.py(y):.1f}' for x, y in sh[1])
                        + ' Z', **kw)
        else:
            self.dot(sh[1], sh[2], sh[3], **kw)

    def body(self, body, op=0.75, sw=1.3, dash=None, keep=None, fill=True):
        """Draw a body's footprint: outer outline, then fill, then holes."""
        m = self.c.m
        rgb = m.color(body)
        ops = [(o, f) for o, f in m.body_ops(body) if keep is None or keep(f)]
        joins = [plan_shape(m, f) for o, f in ops if o == 'join']
        for sh in joins:
            self.shape(sh, stroke=hexc(rgb), sw=sw * 2, dash=dash)
        if fill:
            for sh in joins:
                self.shape(sh, stroke='none', fill=light(rgb), op=op, sw=0)
        for o, f in ops:
            if o == 'cut':
                self.shape(plan_shape(m, f), stroke=hexc(rgb), fill='#fff', sw=0.8)
        return rgb


def internals(p, dash=None, fill=True, op=0.75):
    for body in ('REF_Battery', 'REF_HAT', 'REF_XIAO', 'REF_Adapter', 'REF_Storage',
                 'REF_Antenna', 'REF_PowerSwitch', 'REF_Magnets', 'OPT_HallSensor',
                 'REF_BulkCap'):
        p.body(body, dash=dash, fill=fill, op=op)


def fig_component_layout(c):
    m, k = c.m, 5.0
    ox, oy = 300, 120
    s = Svg(1180, int(oy + c.L * k + 135))
    s.text(30, 38, 'esp-read: front view and component layout (to scale)', size=21,
           weight='bold')
    s.text(30, 58, f'Looking at the screen, spine on the LEFT. {k:g} px/mm. Filled parts are '
                   'inside the case. Read from ereader-case.sc; X from the spine edge, Y from '
                   'the bottom.', size=10, fill='#555')
    p = Plan(s, c, ox, oy, k)

    p.outline(fill='#e8e4da', stroke='#111', sw=2.4)
    p.outline(inset=c.front_ch, stroke='#999', sw=0.8)
    p.outline(inset=c.sh, stroke='#888', sw=0.8, dash='6,3')
    for x in (c.x_g0, c.x_g1):
        p.vline(x, stroke='#777', sw=0.9, dash='10,3,2,3')

    # parts inside, then screw bosses (hidden)
    internals(p)
    for name, (x, y, z, r, h, ax) in c.bosses.items():
        p.dot(x, y, r, stroke='#777', sw=0.9, dash='3,2')
        p.dot(x, y, 0.6, stroke='#777', fill='#777', sw=0.5)

    # glass (under the lip) and the window
    g, w = c.glass, c.window
    p.box(g[0], g[1], g[2], g[3], stroke='#4a6fc4', sw=1.4, dash='6,3')
    p.box(w[0], w[1], w[2], w[3], stroke='#111', sw=1.8)
    p.box(w[0] - c.win_ch, w[1] + c.win_ch, w[2] - c.win_ch, w[3] + c.win_ch,
          stroke='#111', sw=0.7)

    # things you can see on the front face
    face = c.T - 0.01
    for body in ('KeyBack', 'KeyFwd', 'KeyMenu'):
        p.body(body, op=1.0, keep=lambda f: section_top(m, f) > face + 0.01)
    for body in ('LightPipeCharge', 'LightPipeUser'):
        p.body(body, op=1.0, keep=lambda f: section_top(m, f) >= face and f['type'] != 'box')
    for n in ('DimpleReset', 'DimpleBoot'):
        x, y, *_ = m.cyl(n)
        p.dot(x, y, m.cyl(n)[3], stroke='#222', fill='#222', sw=0.5)
    # USB-C slot and power-switch cap on the top edge
    ux0, ux1 = c.usb[0] - c.usb_r, c.usb[1] + c.usb_r
    s.rect(p.px(ux0), p.py(c.L) - 5, (ux1 - ux0) * k, 8, rx=4, stroke='#222', fill='#555',
           sw=1.0)
    cx0, cx1 = c.sw_cap[0] - c.cap_r, c.sw_cap[1] + c.cap_r
    cap_rgb = m.color('SwCap')
    p.box(cx0, cx1, c.sw_cap[2], c.sw_cap[3], stroke=hexc(cap_rgb), fill=light(cap_rgb, 0.4),
          sw=1.0, rx=c.cap_r * k * 0.5)

    # callouts, left margin
    L = Callouts(s, ox - 24, 'end', oy - 20)
    b, xi, ps = c.battery, c.xiao, c.power
    L.add(p.px((ux0 + ux1) / 2), p.py(c.L), ['USB-C (top edge)', f'X {fmt(ux0)}-{fmt(ux1)}'])
    L.add(p.px(cx0), p.py(c.sw_cap[3]),
          ['Power switch + slide cap', f'switch {xr(ps)}, top edge',
           f'cap stands {fmt(c.sw_cap[3] - c.L)} proud'], ink(m.color('REF_PowerSwitch')))
    lpc, pr = c.lp[0], c.pins[0]
    L.add(p.px(lpc[0]), p.py(lpc[1]), ['Light pipes (charge, user LED)',
                                       f'Ø{fmt(2 * lpc[3])} at X {fmt(lpc[0])} / '
                                       f'{fmt(c.lp[1][0])}, Y {fmt(lpc[1])}'], '#0a6e7a')
    L.add(p.px(pr[0]), p.py(pr[1]), ['RESET / BOOT pinholes',
                                     f'Y {fmt(pr[1])}, under a thin skin', 'press with a pin'])
    L.add(p.px(xi[0]), p.py((xi[2] + xi[3]) / 2),
          ['XIAO ESP32-S3 Plus', f'{xr(xi)}, {yr(xi)}', 'USB-C out the top'],
          ink(m.color('REF_XIAO')))
    for label, sw in (('Forward key', c.sw_fwd), ('Back key', c.sw_back), ('Menu key', c.sw_menu)):
        L.add(p.px(sw[0]), p.py((sw[2] + sw[3]) / 2),
              [label, f'X {fmt((sw[0] + sw[1]) / 2)}, Y {fmt((sw[2] + sw[3]) / 2)}'], '#333')
    h = c.hat
    L.add(p.px(h[0]), p.py(h[2] + 8), ['Driver HAT', f'{xr(h)}, {yr(h)}',
                                       'parts below the board (inner box)'],
          ink(m.color('REF_HAT')))
    L.add(p.px(b[0]), p.py((b[2] + b[3]) / 2),
          ['Battery', f'{fmt(b[1] - b[0])} x {fmt(b[3] - b[2])} x {fmt(b[5] - b[4])}',
           f'{xr(b)}, {yr(b)}'], ink(m.color('REF_Battery')))
    bc = plan_shape(m, m.feature('RefBulkCap'))
    L.add(p.px(bc[1]), p.py((bc[3] + bc[4]) / 2),
          ['22uF capacitor', f'X {fmt(bc[1])}-{fmt(bc[2])}, Y {fmt(bc[3])}-{fmt(bc[4])}'],
          ink(m.color('REF_BulkCap')))
    s7 = c.bosses['S7']
    L.add(p.px(s7[0]), p.py(s7[1]), ['M2.5 screw bosses (dashed)',
                                     f'{len(c.bosses)} screws'], '#666')
    L.draw()

    # callouts, right margin
    R = Callouts(s, ox + c.W * k + 30, 'start', oy - 20)
    hl, st, an, ad = c.hall, c.storage, c.antenna, c.adapter
    R.add(p.px(hl[1]), p.py(hl[3]), ['Hall sensor (optional)', f'at X {fmt((hl[0] + hl[1]) / 2)},'
                                     f' Y {fmt((hl[2] + hl[3]) / 2)}'], ink(m.color('OPT_HallSensor')))
    R.add(p.px(an[1]), p.py(an[3] - 4), ['WiFi antenna sticker', f'{fmt(an[1] - an[0])} x '
                                         f'{fmt(an[3] - an[2])}, {xr(an)}, {yr(an)}',
                                         'on the inside of the back'], ink(m.color('REF_Antenna')))
    R.add(p.px(st[1]), p.py(st[2] + 3), ['Storage board', size3(st), f'{xr(st)}, {yr(st)}'],
          ink(m.color('REF_Storage')))
    R.add(p.px(w[1]), p.py(w[3] - 20),
          ['Visible window', f'{fmt(w[1] - w[0])} x {fmt(w[3] - w[2])}', f'{xr(w)}, {yr(w)}',
           f'{fmt(c.win_ch)} chamfer to the front'], '#111')
    R.add(p.px(g[1]), p.py(g[3] - 45),
          ['Glass (dashed, behind the lip)', size3(g), f'{xr(g)}, {yr(g)}'], '#4a6fc4')
    mg = c.mags[3]
    R.add(p.px(mg[0] + mg[3]), p.py(mg[1]), ['Cover magnets x4', f'Ø{fmt(2 * mg[3])} at X '
                                             f'{fmt(c.mags[0][0])} / {fmt(mg[0])}',
                                             f'Y {fmt(c.mags[0][1])} / {fmt(mg[1])}'],
          ink(m.color('REF_Magnets')))
    R.add(p.px(c.x_g1), p.py(60), ['Back steps down here (hidden)',
                                   f'X {fmt(c.x_g0)}-{fmt(c.x_g1)}, dash-dot'], '#666')
    R.add(p.px(ad[1]), p.py((ad[2] + ad[3]) / 2), ['FFC adapter', size3(ad), f'{xr(ad)}, {yr(ad)}'],
          ink(m.color('REF_Adapter')))
    R.draw()

    dim_h(s, p.px(0), p.px(c.W), p.py(0) + 34, f'W {fmt(c.W)}')
    dim_h(s, p.px(0), p.px(g[0]), p.py(0) + 14, f'to glass {fmt(g[0])}', size=9)
    dim_v(s, p.px(c.W) + 14, p.py(c.L), p.py(0), f'L {fmt(c.L)}')
    s.lines(30, p.py(0) + 74, [
        f'Spine column from the bottom: battery ({yr(b)}), HAT ({yr(h)}), XIAO ({yr(xi)}) with '
        'USB-C out of the top edge. The keys sit on the spine face over the battery and HAT.',
        'Behind the glass: FFC adapter at the bottom, storage board and antenna at the top, '
        'four cover magnets in the rib grid.',
        f'Plan corners R{fmt(c.r_corner)}. Front edge {fmt(c.front_ch)} chamfer (thin inner line), '
        f'walls {fmt(c.sh)}, right wall {fmt(c.sh_r)} (inner line dashed).',
    ])
    s.save('component-layout')


def section_top(m, f):
    """Top Z of a box or cylinder feature (for 'can I see it from the front')."""
    if f['type'] == 'box':
        return prim_box(m, f)[5]
    if f['type'] == 'cylinder':
        z, h, a = m.ev(f['base'][2]), m.ev(f['height']), f['axis'][2]
        return max(z, z + h * a)
    return -1


def fig_back_view(c):
    m, k = c.m, 5.0
    ox, oy = 300, 120
    s = Svg(1180, int(oy + c.L * k + 120))
    s.text(30, 38, 'esp-read: back view (to scale)', size=21, weight='bold')
    s.text(30, 58, f'Seen from behind, spine on the RIGHT (X mirrored). {k:g} px/mm. Z is the '
                   'depth from the back of the stowed cover (Z 0).', size=10, fill='#555')
    p = Plan(s, c, ox, oy, k, mirror=True)

    # back surfaces: spine plane, palm round, the gradient, the display back
    s.add('<defs><linearGradient id="grad" x1="0" x2="1" y1="0" y2="0">'
          '<stop offset="0" stop-color="#c9c3b3"/><stop offset="1" stop-color="#e3dfd4"/>'
          '</linearGradient></defs>')
    clip = s.clip_path(f'M{p.ox},{p.oy + c.r_corner * k} a{c.r_corner * k},{c.r_corner * k} '
                       f'0 0 1 {c.r_corner * k},{-c.r_corner * k} h{(c.W - 2 * c.r_corner) * k} '
                       f'a{c.r_corner * k},{c.r_corner * k} 0 0 1 {c.r_corner * k},'
                       f'{c.r_corner * k} v{(c.L - 2 * c.r_corner) * k} '
                       f'a{c.r_corner * k},{c.r_corner * k} 0 0 1 {-c.r_corner * k},'
                       f'{c.r_corner * k} h{-(c.W - 2 * c.r_corner) * k} '
                       f'a{c.r_corner * k},{c.r_corner * k} 0 0 1 {-c.r_corner * k},'
                       f'{-c.r_corner * k} z')
    p.box(c.x_g1, c.W, 0, c.L, stroke='none', fill='#e3dfd4', clip=clip, sw=0)
    p.box(c.x_g0, c.x_g1, 0, c.L, stroke='none', fill='#d6d0c2', clip=clip, sw=0)
    p.box(c.r_palm, c.x_g0, 0, c.L, stroke='none', fill='#c9c3b3', clip=clip, sw=0)
    p.box(0, c.r_palm, 0, c.L, stroke='none', fill='#bdb6a5', clip=clip, sw=0)
    p.outline(stroke='#111', sw=2.4)
    for x in (c.r_palm, c.x_g0, c.x_g1):
        p.vline(x, stroke='#888', sw=0.9, dash='5,3')

    # inside, dashed
    for body in ('REF_Battery', 'REF_HAT', 'REF_XIAO', 'REF_Antenna', 'REF_Magnets'):
        p.body(body, dash='4,3', fill=False, sw=0.6)

    # screw holes open at the back (counterbores), and the chin magnet
    cbs = [m.cyl(f['name']) for f in m.prefixed('CbS')]
    if not cbs:
        raise ModelError('the model has no screw counterbores (features named CbS...)')
    for x, y, z, r, h, ax in cbs:
        p.dot(x, y, r, stroke='#333', fill='#fff', sw=1.2)
        p.dot(x, y, 0.7, stroke='#333', fill='#333', sw=0.5)

    # stowed cover: outline, living hinges, steel discs, hall magnet hole
    cov_rgb = m.color('Cover')
    cv = c.cover_box
    ro = m.ev(m.feature('CovToolR')['radius']) * k     # outer (right-edge) corners
    ri = m.ev(m.feature('CovToolL')['radius']) * k     # inner (spine-side) corners
    xo, xi, yt, yb = p.px(cv[1]), p.px(c.cover_x0), p.py(c.L), p.py(0)
    s.path(f'M{xo + ro:.1f},{yt:.1f} H{xi - ri:.1f} A{ri:.1f},{ri:.1f} 0 0 1 {xi:.1f},'
           f'{yt + ri:.1f} V{yb - ri:.1f} A{ri:.1f},{ri:.1f} 0 0 1 {xi - ri:.1f},{yb:.1f} '
           f'H{xo + ro:.1f} A{ro:.1f},{ro:.1f} 0 0 1 {xo:.1f},{yb - ro:.1f} V{yt + ro:.1f} '
           f'A{ro:.1f},{ro:.1f} 0 0 1 {xo + ro:.1f},{yt:.1f} Z', stroke=hexc(cov_rgb), sw=2.2,
           dash='9,4')
    for hg in c.hinges:
        p.box(hg[0], hg[1], 0, c.L, stroke=hexc(cov_rgb), fill=light(cov_rgb), sw=0.8, op=0.7)
    steel = [m.cyl(f['name']) for f in m.prefixed('SteelPocket')]
    for x, y, z, r, h, ax in steel:
        p.dot(x, y, r, stroke=hexc(cov_rgb), sw=1.0, dash='3,2')
    # The cover's hall-magnet hole is optional and off by default.
    if not m.by_name.get('OPT_HallMagnetHole', {}).get('suppressed', True):
        hm = m.cyl('OPT_HallMagnetHole')
        p.dot(hm[0], hm[1], hm[3], stroke=hexc(cov_rgb), fill='#fff', sw=1.2)

    # top edge: USB-C and the switch cap
    ux0, ux1 = c.usb[0] - c.usb_r, c.usb[1] + c.usb_r
    s.rect(p.px(ux1), p.py(c.L) - 5, (ux1 - ux0) * k, 8, rx=4, stroke='#222', fill='#555', sw=1)
    cap_rgb = m.color('SwCap')
    cx0, cx1 = c.sw_cap[0] - c.cap_r, c.sw_cap[1] + c.cap_r
    p.box(cx0, cx1, c.sw_cap[2], c.sw_cap[3], stroke=hexc(cap_rgb), fill=light(cap_rgb, 0.4),
          sw=1.0)

    # big labels
    s.text(p.px((c.r_palm + c.x_g0) / 2), p.py(c.L * 0.55), 'SPINE', size=13, anchor='middle',
           weight='bold')
    s.text(p.px((c.r_palm + c.x_g0) / 2), p.py(c.L * 0.55) + 14,
           f'flat, Z {fmt(c.z_spine_back)}', size=9.5, anchor='middle')
    s.text(p.px((c.x_g1 + c.W) / 2), p.py(c.L * 0.55), 'DISPLAY SECTION', size=13,
           anchor='middle', weight='bold', fill='#555')
    s.text(p.px((c.x_g1 + c.W) / 2), p.py(c.L * 0.55) + 14,
           f'flat, Z {fmt(c.z_disp_back)}', size=9.5, anchor='middle', fill='#555')

    # callouts, right (spine side)
    R = Callouts(s, ox + c.W * k + 30, 'start', oy - 20)
    R.add(p.px(c.r_palm / 2), p.py(c.L - 20), ['Palm round', f'R{fmt(c.r_palm)} along the spine '
                                               'edge'], '#666')
    bare = [v for v in cbs if v[0] + v[3] < c.cover_x0]    # not under the stowed cover
    R.add(p.px(bare[len(bare) // 2][0]), p.py(bare[len(bare) // 2][1]),
          ['M2.5 screws, from the back', f'{len(bare)} on the spine stay visible,',
           f'{len(cbs) - len(bare)} sit under the stowed cover',
           f'counterbores Ø{fmt(2 * bare[0][3])}'], '#333')
    hb = c.battery
    R.add(p.px(hb[1]), p.py(hb[3] - 6), ['Battery (inside, dashed)', f'{xr(hb)}, {yr(hb)}'],
          ink(m.color('REF_Battery')))
    R.add(p.px(c.hat[1]), p.py(c.hat[3] - 10), ['HAT (inside, dashed)', xr(c.hat)],
          ink(m.color('REF_HAT')))
    R.add(p.px(c.xiao[0]), p.py(c.xiao[3] - 4), ['XIAO (inside, dashed)', xr(c.xiao)],
          ink(m.color('REF_XIAO')))
    R.draw()

    # callouts, left (display side)
    Lc = Callouts(s, ox - 24, 'end', oy - 20)
    Lc.add(p.px(c.W), p.py(c.L - 12),
           ['Stowed cover (dashed)', f'X {fmt(c.cover_x0)}-{fmt(c.W)}, full length',
            f'{fmt(c.t_h)} thick, print in PP'], ink(cov_rgb))
    if not m.by_name.get('OPT_HallMagnetHole', {}).get('suppressed', True):
        Lc.add(p.px(hm[0]), p.py(hm[1]), ['Hall magnet hole', 'in the cover (optional)'],
               ink(cov_rgb))
    for i, hg in enumerate(c.hinges):
        Lc.add(p.px((hg[0] + hg[1]) / 2), p.py(25 + 18 * i),
               [f'Living hinge {i + 1}', f'X {fmt((hg[0] + hg[1]) / 2)}, '
                                         f'{fmt(hg[1] - hg[0])} wide'], ink(cov_rgb))
    Lc.add(p.px((c.x_g0 + c.x_g1) / 2), p.py(c.L * 0.3),
           ['Back gradient', f'X {fmt(c.x_g0)}-{fmt(c.x_g1)}',
            f'Z {fmt(c.z_spine_back)} down to {fmt(c.z_disp_back)}'], '#555')
    st = steel[0]
    Lc.add(p.px(st[0]), p.py(st[1]), ['Steel discs in the cover', f'{len(steel)} pockets, '
                                      'over the body magnets'], ink(cov_rgb))
    an = c.antenna
    Lc.add(p.px(an[1]), p.py((an[2] + an[3]) / 2), ['Antenna (inside, dashed)', xr(an)],
           ink(m.color('REF_Antenna')))
    Lc.draw()

    dim_h(s, p.px(c.W), p.px(0), p.py(0) + 34, f'W {fmt(c.W)}')
    dim_h(s, p.px(c.x_g0), p.px(0), p.py(0) + 14, f'spine plane to {fmt(c.x_g0)}', size=9)
    dim_v(s, ox - 14, p.py(c.L), p.py(0), f'L {fmt(c.L)}', left=True)
    s.lines(30, p.py(0) + 74, [
        f'Depths: bare spine {fmt(c.T - c.z_spine_back)}, display section '
        f'{fmt(c.T - c.z_disp_back)}. With the cover stowed: spine {fmt(c.T)}, display section '
        f'{fmt(c.T - c.z_disp_back + c.t_h)}.',
        'The grip pad on the back of the spine is planned but not modelled yet, so it is not '
        'shown.',
    ])
    s.save('back-view')


# ============================================================== sections
class Sec:
    def __init__(self, s, ox, oy, kx, kz, zmax):
        self.s, self.ox, self.oy, self.kx, self.kz, self.zmax = s, ox, oy, kx, kz, zmax

    def px(self, x):
        return self.ox + x * self.kx

    def pz(self, z):
        return self.oy + (self.zmax - z) * self.kz

    def d(self, sh):
        """SVG path data for a section shape."""
        if sh[0] == 'rect':
            _, x0, x1, z0, z1 = sh
            return (f'M{self.px(x0):.1f},{self.pz(z0):.1f} H{self.px(x1):.1f} '
                    f'V{self.pz(z1):.1f} H{self.px(x0):.1f} Z')
        if sh[0] == 'circle':      # an ellipse once Z is stretched
            _, x, z, r = sh
            rx, rz = r * self.kx, r * self.kz
            return (f'M{self.px(x) - rx:.1f},{self.pz(z):.1f} a{rx:.1f},{rz:.1f} 0 1 0 '
                    f'{2 * rx:.1f},0 a{rx:.1f},{rz:.1f} 0 1 0 {-2 * rx:.1f},0 Z')
        return 'M' + ' L'.join(f'{self.px(x):.1f},{self.pz(z):.1f}' for x, z in sh[1]) + ' Z'

    def body(self, m, body, y, fill, stroke, sw=1.1, dash=None, op=1.0, solid_clip=False):
        """Draw a body cut at Y = y. Returns its shapes (joins) or [] if it misses."""
        ops = [(o, section_shape(m, f, y)) for o, f in m.body_ops(body)]
        ops = [(o, sh) for o, sh in ops if sh is not None]
        joins = [sh for o, sh in ops if o == 'join']
        if not joins:
            return []
        clip = self.s.clip_path(' '.join(self.d(sh) for sh in joins)) if solid_clip else None
        # Work in timeline order. Each run of joins is drawn outline first, then
        # fill, so only the outer edge of the run shows. A cut paints background
        # and redraws its edge where it bites into solid.
        # For the case parts, a join's outline is hidden where it lands on solid
        # already drawn, so added walls and ribs merge without a seam.
        i, done = 0, []
        while i < len(ops):
            if ops[i][0] == 'cut':
                d = self.d(ops[i][1])
                self.s.path(d, stroke='none', fill=BG, sw=0)
                if clip:
                    self.s.path(d, stroke=stroke, sw=sw, clip=clip)
                done.append(('cut', d))
                i += 1
                continue
            run = []
            while i < len(ops) and ops[i][0] == 'join':
                run.append(self.d(ops[i][1]))
                i += 1
            extra = ''
            if solid_clip and done:
                self.s.nclip += 1
                mid = f'mask{self.s.nclip}'
                self.s.add(f'<mask id="{mid}" maskUnits="userSpaceOnUse" x="0" y="0" '
                           f'width="{self.s.w}" height="{self.s.h}"><rect x="0" y="0" '
                           f'width="{self.s.w}" height="{self.s.h}" fill="#fff"/>'
                           + ''.join(f'<path d="{d}" fill="{"#000" if o == "join" else "#fff"}"/>'
                                     for o, d in done) + '</mask>')
                extra = f' mask="url(#{mid})"'
            for d in run:
                self.s.path(d, stroke=stroke, sw=sw * 2, dash=dash, extra=extra)
            done += [('join', d) for d in run]
            if fill != 'none':
                for d in run:
                    # case parts: a thin rim of fill hides hairline seams
                    rim = (fill, sw * 0.8) if solid_clip else ('none', 0)
                    self.s.path(d, stroke=rim[0], fill=fill, sw=rim[1], op=op)
        return joins


def bbox(shapes):
    xs, zs = [], []
    for sh in shapes:
        if sh[0] == 'rect':
            xs += sh[1:3]
            zs += sh[3:5]
        elif sh[0] == 'circle':
            xs += [sh[1] - sh[3], sh[1] + sh[3]]
            zs += [sh[2] - sh[3], sh[2] + sh[3]]
        else:
            xs += [p[0] for p in sh[1]]
            zs += [p[1] for p in sh[1]]
    return min(xs), max(xs), min(zs), max(zs)


SECTION_PARTS = ['REF_Battery', 'REF_HAT', 'REF_XIAO', 'REF_Adapter', 'REF_Storage',
                 'REF_Antenna', 'REF_SwitchBack', 'REF_SwitchFwd', 'REF_SwitchMenu',
                 'REF_Magnets', 'REF_PowerSwitch', 'OPT_HallSensor', 'REF_BulkCap',
                 'KeyBack', 'KeyFwd',
                 'KeyMenu', 'LightPipeCharge', 'LightPipeUser', 'SwCap']
PART_LABEL = dict(Case.PARTS, KeyBack='Back key cap', KeyFwd='Forward key cap',
                  KeyMenu='Menu key cap', LightPipeCharge='Light pipe', LightPipeUser='Light pipe',
                  SwCap='Switch slide cap')


def draw_section(s, c, ox, oy, y, title, kx=8.0, kz=24.0):
    m = c.m
    zmax, zmin = c.T + 1.4, -0.6
    sec = Sec(s, ox, oy, kx, kz, zmax)
    s.text(ox, oy - 10, title, size=14, weight='bold')
    for z in sorted({0.0, c.z_spine_back, c.z_disp_back, c.z_floor_spine, c.z_floor_disp,
                     c.ht, c.T}):
        s.line(sec.px(-2), sec.pz(z), sec.px(c.W + 2), sec.pz(z), stroke='#ddd', sw=0.6)
        s.text(sec.px(-3), sec.pz(z) + 3, f'Z {fmt(z)}', size=8.5, fill='#777', anchor='end')

    # case: tub, front plate (with its two chamfers), stowed cover, closed-cover ghost
    sec.body(m, 'Tub', y, CASE_FILL, CASE_LINE, solid_clip=True)
    sec.body(m, 'Front', y, CASE_FILL, CASE_LINE, solid_clip=True)
    f = c.front_ch
    for x0, x1 in ((0, f), (c.W, c.W - f)):
        s.path(f'M{sec.px(x0):.1f},{sec.pz(c.T - f):.1f} L{sec.px(x0):.1f},{sec.pz(c.T + .2):.1f}'
               f' L{sec.px(x1):.1f},{sec.pz(c.T + .2):.1f} L{sec.px(x1):.1f},{sec.pz(c.T):.1f} Z',
               stroke='none', fill=BG, sw=0)
        s.line(sec.px(x0), sec.pz(c.T - f), sec.px(x1), sec.pz(c.T), stroke=CASE_LINE, sw=1.1)
    w = c.window
    if w[2] <= y <= w[3]:
        ch = c.win_ch
        for xe, xo in ((w[0], w[0] - ch), (w[1], w[1] + ch)):
            s.path(f'M{sec.px(xe):.1f},{sec.pz(c.T - ch):.1f} L{sec.px(xo):.1f},'
                   f'{sec.pz(c.T):.1f} L{sec.px(xe):.1f},{sec.pz(c.T):.1f} Z', stroke='none',
                   fill=BG, sw=0)
            s.line(sec.px(xe), sec.pz(c.T - ch), sec.px(xo), sec.pz(c.T), stroke=CASE_LINE,
                   sw=1.1)
    cov_rgb = m.color('Cover')
    cover = sec.body(m, 'Cover', y, light(cov_rgb, 0.55), hexc(cov_rgb), solid_clip=True)
    sec.body(m, 'VIEW_CoverClosed', y, 'none', hexc(cov_rgb), sw=0.6, dash='5,3')

    # glass and every part the cut passes through
    g_rgb = m.color('REF_Glass')
    sec.body(m, 'REF_Glass', y, light(g_rgb), hexc(g_rgb))
    hits = []
    for body in SECTION_PARTS:
        rgb = m.color(body)
        sh = sec.body(m, body, y, light(rgb, 0.6), hexc(rgb), sw=0.9)
        if sh:
            hits.append((body, bbox(sh), rgb))

    # case notes, right margin
    R = Callouts(s, sec.px(c.W) + 26, 'start', oy - 4, size=9)
    g = c.glass
    R.add(sec.px(g[1] - 3), sec.pz((g[4] + g[5]) / 2),
          [f'Glass {fmt(g[5] - g[4])} ({zr_(g)})'], ink(g_rgb))
    R.add(sec.px(c.W - c.front_ch - 1), sec.pz(c.T - 0.3),
          [f'Front plate {fmt(c.T - c.ht)} (Z {fmt(c.ht)}-{fmt(c.T)})'], '#555')
    R.add(sec.px(c.W - c.sh_r / 2), sec.pz(c.ht - 2.6),
          [f'Right wall {fmt(c.sh_r)}, other walls {fmt(c.sh)}', f'seam at Z {fmt(c.ht)}'],
          '#555')
    tg = c.tongue
    if tg[2] <= y <= tg[3]:
        R.add(sec.px((tg[0] + tg[1]) / 2), sec.pz((tg[4] + tg[5]) / 2),
              ['Hook lip: tongue on the front plate,', 'hook in a notch in the wall'], '#555')
    R.add(sec.px(c.W - 4), sec.pz((c.z_disp_back + c.z_floor_disp) / 2),
          [f'Display back wall {fmt(c.z_floor_disp - c.z_disp_back)} '
           f'(Z {fmt(c.z_disp_back)}-{fmt(c.z_floor_disp)})'], '#555')
    if cover:
        R.add(sec.px(c.W - 6), sec.pz(c.z_disp_back - c.t_h / 2),
              [f'Stowed cover {fmt(c.t_h)} thick', 'living hinges are the notches'],
              ink(cov_rgb))
    R.add(sec.px(c.W - 8), sec.pz(c.T + c.t_h / 2), ['Closed cover (dashed)'], ink(cov_rgb))
    R.draw()

    # part notes, below the section, sorted left to right
    base = sec.pz(zmin) + 18
    hits.sort(key=lambda h: (h[1][0] + h[1][1]) / 2)
    cols = 3
    colw = (c.W * kx) / cols
    for i, (body, (x0, x1, z0, z1), rgb) in enumerate(hits):
        tx = ox + (i % cols) * colw
        ty = base + (i // cols) * 15
        txt = (f'{PART_LABEL.get(body, body)}: X {fmt(x0)}-{fmt(x1)}, Z {fmt(z0)}-{fmt(z1)}')
        s.line(tx - 3, ty - 4, sec.px((x0 + x1) / 2), sec.pz((z0 + z1) / 2), stroke=ink(rgb),
               sw=0.6)
        s.text(tx, ty, txt, size=9, fill=ink(rgb))
    ny = base + ((len(hits) + cols - 1) // cols) * 15 + 8

    # depths at this cut
    s.text(ox, ny, f'Spine: back at Z {fmt(c.z_spine_back)}, {fmt(c.T - c.z_spine_back)} deep '
                   f'bare, {fmt(c.T)} with the cover stowed. Display section: back at Z '
                   f'{fmt(c.z_disp_back)}, {fmt(c.T - c.z_disp_back)} deep bare, '
                   f'{fmt(c.T - c.z_disp_back + c.t_h)} with the cover.', size=9.5, fill='#333')
    dy = ny + 22
    s.line(sec.px(c.x_g0), sec.pz(zmin), sec.px(c.x_g0), dy, stroke='#bbb', sw=0.6, dash='2,3')
    s.line(sec.px(c.x_g1), sec.pz(zmin), sec.px(c.x_g1), dy, stroke='#bbb', sw=0.6, dash='2,3')
    dim_h(s, sec.px(0), sec.px(c.x_g0), dy, f'spine {fmt(c.x_g0)}', size=9)
    dim_h(s, sec.px(c.x_g0), sec.px(c.x_g1), dy, f'gradient {fmt(c.x_g1 - c.x_g0)}', size=9)
    dim_h(s, sec.px(c.x_g1), sec.px(c.W), dy, f'display section {fmt(c.W - c.x_g1)}', size=9)
    return dy + 34


def fig_section(c):
    s = Svg(1360, 1010)
    s.text(30, 38, 'esp-read: cross-sections across the width (X)', size=21, weight='bold')
    s.text(30, 58, 'X at 8 px/mm, Z stretched 3x (24 px/mm). Front face at the top, back at '
                   'the bottom, spine on the LEFT as in the front view. Cover shown stowed, '
                   'closed position dashed.', size=10, fill='#555')
    yk, yb = c.y_keys, c.y_batt
    y = draw_section(s, c, 90, 110, yk, f'Section A-A at Y {fmt(yk)}: through the back key')
    end = draw_section(s, c, 90, y + 60, yb,
                       f'Section B-B at Y {fmt(yb)}: through the middle of the battery')
    s.h = int(end)
    s.save('section')


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else MODEL
    m = Model(path)
    c = Case(m)
    fig_component_layout(c)
    fig_back_view(c)
    fig_section(c)
    if m.stale:
        print(f'note: {len(m.stale)} sketches were saved before a parameter change '
              f'({", ".join(sorted(m.stale))}); drawn from the current parameters')


if __name__ == '__main__':
    main()
