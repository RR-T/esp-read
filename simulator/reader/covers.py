"""1-bit book-cover thumbnails for the library.

A book with a real cover image (``book.cover`` → a file in ``assets/images/``)
gets that artwork cover-cropped to the thumbnail and **ordered-dithered** to
1-bit (ordered, not error diffusion, so it stays stable across partial
refreshes). Books without art fall back to a procedural cover: a tonal field
dithered the same way, with a crisp, *undithered* initial on top — the rule for
1-bit panels in miniature: halftone the picture, render the glyph straight to
mono.

Either way the cover is built at its exact on-screen pixel size — the dither is
never rescaled afterwards, which would wreck the pattern.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageOps

from epd_sim.dither import ORDERED, to_1bit

from . import fonts

BLACK, WHITE = 0, 255
_IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "images")


def _background(w: int, h: int, seed: int) -> Image.Image:
    """A grayscale tonal field; style + tone vary by seed for distinct covers."""
    style = seed % 3
    if style == 0:                                   # vertical gradient
        g = Image.linear_gradient("L").resize((w, h))
    elif style == 1:                                 # radial, light centre
        g = Image.radial_gradient("L").resize((w, h))
        g = g.point(lambda v: 255 - v)
    else:                                            # diagonal
        g = Image.linear_gradient("L").rotate(45, expand=True).resize((w, h))
    # Compress into a mid-tone band (so dithering has greys to work with) and
    # nudge the overall darkness by seed.
    lo = 40 + (seed % 4) * 18
    hi = min(235, lo + 150)
    return g.point(lambda v: lo + v * (hi - lo) // 255)


def make_cover(title: str, family: str, w: int, h: int, seed: int,
               image: str | None = None) -> Image.Image:
    """Return a 1-bit ("1") cover thumbnail of size (w, h).

    Uses real artwork from ``assets/images/<image>`` when available, otherwise
    a procedural tonal cover with the title's initial.
    """
    if image:
        path = os.path.join(_IMAGE_DIR, image)
        if os.path.exists(path):
            return _from_image(path, w, h)
    return _procedural(title, family, w, h, seed)


def _from_image(path: str, w: int, h: int) -> Image.Image:
    src = ImageOps.exif_transpose(Image.open(path)).convert("L")
    src = ImageOps.fit(src, (w, h), method=Image.LANCZOS)   # cover-crop to thumb
    src = ImageOps.autocontrast(src, cutoff=1)              # use the full range
    cover = to_1bit(src, method=ORDERED, gamma=1.2)         # lighten to keep detail
    ImageDraw.Draw(cover).rectangle((0, 0, w - 1, h - 1), outline=BLACK, width=1)
    return cover


def _procedural(title: str, family: str, w: int, h: int, seed: int) -> Image.Image:
    cover = to_1bit(_background(w, h, seed), method=ORDERED, gamma=0.9)
    d = ImageDraw.Draw(cover)
    d.rectangle((0, 0, w - 1, h - 1), outline=BLACK, width=2)

    # Crisp white disc + black initial (legible over any dither pattern).
    initial = next((c for c in title if c.isalnum()), "?").upper()
    disc = int(min(w, h) * 0.56)
    cx, cy = w // 2, h // 2
    d.ellipse((cx - disc // 2, cy - disc // 2, cx + disc // 2, cy + disc // 2),
              fill=WHITE, outline=BLACK, width=2)
    f = fonts.face(family, "Bold", int(disc * 0.7))
    box = d.textbbox((0, 0), initial, font=f)
    d.text((cx - (box[2] - box[0]) / 2 - box[0], cy - (box[3] - box[1]) / 2 - box[1]),
           initial, font=f, fill=BLACK)
    return cover
