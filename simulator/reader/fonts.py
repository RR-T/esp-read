"""Selectable font families (with optional weight + size) for the reader.

In text mode the ESP rasterises fonts on-device, so the simulator does the same
with PIL ImageFont at *device-pixel* sizes (the panel is ~220 PPI, so sizes map
1:1 to hardware). Text is drawn into a 1-bit surface, where FreeType hints and
snaps glyphs to the pixel grid — crisp without anti-aliasing.

Families (switchable live in the GUI or via ``--font``):

* ``literata``     — Literata (OFL), Google's screen/e-reader serif. Default.
                     Variable, so Regular→Bold weights are all selectable.
* ``bitter``       — Bitter (OFL), a slab serif designed for low-DPI screen
                     reading — sturdy stems hold up well on 1-bit e-ink. Ships
                     several static weights.
* ``crimson``      — Crimson Text (OFL), a classic literary book serif.
* ``atkinson``     — Atkinson Hyperlegible (OFL), the Braille Institute's
                     legibility-first sans; disambiguated letterforms read well
                     small and on 1-bit e-ink.
* ``palladio``     — P052 / URW Palladio (AGPL+font-exception), an open Palatino
                     clone — the redistributable stand-in for "Palatino" faces.
* ``source-serif`` — Source Serif 4 (OFL, Adobe), a clean modern serif.
* ``pixel``        — Pixel Operator (CC0), a proportional bitmap face; crisp 1-bit
                     at native 16 / multiples. The literal low-PPI mono look.
* ``serif``        — whatever host TrueType serif is installed (fallback/compare).

Choosing a heavier body weight (e.g. Medium/SemiBold for Literata/Bitter) can
improve contrast on e-ink, which tends to render fine strokes a little thin.
Families that only ship Regular/Bold expose just those two. All bundled fonts
live in ``assets/fonts/`` with their licenses (see ``NOTICE.md``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional, Tuple

from PIL import ImageFont

from .content import LayoutMetrics

_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

# Host serif candidates (best-first) for the "serif" fallback family.
SERIF_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
)
SERIF_BOLD_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
)

# Discrete reading-size steps (body scale factor), shown in the GUI.
SIZE_SCALES: Dict[str, float] = {"S": 0.82, "M": 1.0, "L": 1.18, "XL": 1.38}
DEFAULT_SIZE = "M"


@dataclass(frozen=True)
class _Spec:
    label: str
    body: int                       # base body size (px) at scale M
    head: int                       # base heading size (px) at scale M
    weights: Tuple[str, ...]        # selectable body weights
    kind: str = "static"            # "static" | "variable" | "host"
    files: Optional[Dict[str, str]] = None   # weight -> filename (static)
    var_file: Optional[str] = None           # variable-font filename
    head_weight: str = "Bold"
    leading_factor: float = 1.5


SPECS: Dict[str, _Spec] = {
    "literata": _Spec(
        "Literata (e-reader)", body=25, head=36, kind="variable",
        var_file="Literata.ttf",
        weights=("Regular", "Medium", "SemiBold", "Bold")),
    "bitter": _Spec(
        "Bitter (slab)", body=24, head=36, kind="static",
        files={
            "Regular": "Bitter/static/Bitter-Regular.ttf",
            "Medium": "Bitter/static/Bitter-Medium.ttf",
            "SemiBold": "Bitter/static/Bitter-SemiBold.ttf",
            "Bold": "Bitter/static/Bitter-Bold.ttf",
        },
        weights=("Regular", "Medium", "SemiBold", "Bold")),
    "crimson": _Spec(
        "Crimson Text", body=28, head=40, kind="static",
        files={"Regular": "CrimsonText-Regular.ttf",
               "Bold": "CrimsonText-Bold.ttf"},
        weights=("Regular", "Bold")),
    "atkinson": _Spec(
        "Atkinson Hyperlegible", body=23, head=34, kind="static",
        files={"Regular": "AtkinsonHyperlegible-Regular.ttf",
               "Bold": "AtkinsonHyperlegible-Bold.ttf"},
        weights=("Regular", "Bold")),
    "palladio": _Spec(
        "Palladio (Palatino)", body=25, head=35, kind="static",
        files={"Regular": "P052-Roman.otf", "Bold": "P052-Bold.otf"},
        weights=("Regular", "Bold")),
    "source-serif": _Spec(
        "Source Serif 4", body=25, head=35, kind="static",
        files={"Regular": "SourceSerif4-Regular.ttf",
               "Bold": "SourceSerif4-Bold.ttf"},
        weights=("Regular", "Bold")),
    "pixel": _Spec(
        "Pixel Operator", body=32, head=48, kind="static",
        files={"Regular": "PixelOperator.ttf", "Bold": "PixelOperator-Bold.ttf"},
        weights=("Regular", "Bold"), leading_factor=1.375),
    "serif": _Spec(
        "Host serif", body=26, head=34, kind="host",
        weights=("Regular", "Bold")),
}

FAMILIES = tuple(SPECS.keys())
DEFAULT_FAMILY = "literata"


# -- face resolution -------------------------------------------------------
@lru_cache(maxsize=None)
def _static(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=None)
def _variable(path: str, size: int, weight: str) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(path, size)
    try:
        font.set_variation_by_name(weight)
    except (OSError, ValueError, AttributeError):
        try:
            font.set_variation_by_name("Regular")
        except (OSError, ValueError, AttributeError):
            pass
    return font


@lru_cache(maxsize=None)
def _host(candidates: Tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def face(family: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Resolve one font face for a family at a given weight + pixel size."""
    s = SPECS[family]
    if s.kind == "host":
        cands = SERIF_BOLD_CANDIDATES if weight == "Bold" else SERIF_CANDIDATES
        return _host(cands, size)
    if s.kind == "variable":
        assert s.var_file
        return _variable(os.path.join(_ASSET_DIR, s.var_file), size, weight)
    assert s.files
    fname = s.files.get(weight) or s.files.get("Regular") or next(iter(s.files.values()))
    return _static(os.path.join(_ASSET_DIR, fname), size)


@dataclass
class FontSet:
    """Concrete faces + line metrics the reader draws with (device px)."""
    body: ImageFont.FreeTypeFont
    head: ImageFont.FreeTypeFont
    ui: ImageFont.FreeTypeFont
    ui_bold: ImageFont.FreeTypeFont
    list_title: ImageFont.FreeTypeFont
    list_author: ImageFont.FreeTypeFont
    body_leading: int
    head_leading: int
    para_gap: int
    head_gap_before: int
    head_gap_after: int

    def layout(self, width: int, height: int) -> LayoutMetrics:
        return LayoutMetrics(
            width=width, height=height,
            body_leading=self.body_leading, head_leading=self.head_leading,
            para_gap=self.para_gap, head_gap_before=self.head_gap_before,
            head_gap_after=self.head_gap_after,
        )


def weights(family: str) -> Tuple[str, ...]:
    return SPECS[family].weights


def size_steps() -> Tuple[str, ...]:
    return tuple(SIZE_SCALES.keys())


def body_px(family: str, size: str) -> int:
    """Body text size in device pixels for a family at a given size step."""
    return round(SPECS[family].body * SIZE_SCALES.get(size, 1.0))


def label(family: str) -> str:
    return SPECS[family].label


def make(family: str, size: str = DEFAULT_SIZE,
         body_weight: str = "Regular") -> FontSet:
    if family not in SPECS:
        raise ValueError(f"unknown font family {family!r}; use one of {FAMILIES}")
    s = SPECS[family]
    scale = SIZE_SCALES.get(size, 1.0)
    if body_weight not in s.weights:
        body_weight = "Regular"
    bsize, hsize = round(s.body * scale), round(s.head * scale)
    return FontSet(
        body=face(family, body_weight, bsize),
        head=face(family, s.head_weight, hsize),
        ui=face(family, "Regular", 16),
        ui_bold=face(family, "Bold", 16),
        list_title=face(family, s.head_weight, min(hsize, 32)),
        list_author=face(family, "Regular", 18),
        body_leading=round(bsize * s.leading_factor),
        head_leading=round(hsize * 1.25),
        para_gap=round(bsize * 0.5),
        head_gap_before=round(bsize * 0.45),
        head_gap_after=round(bsize * 0.85),
    )
