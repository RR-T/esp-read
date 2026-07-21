"""1-bit conversion for grayscale/photographic content (covers, illustrations).

On a 1-bit panel with no anti-aliasing, *text* should be rendered straight into
the mono framebuffer — PIL/FreeType hints and snaps glyphs to the pixel grid, so
it stays crisp (never dither text). But continuous-tone images have no good 1-bit
representation without **halftoning**: simulating grey by the density of black
pixels. This module provides the three approaches worth having on e-ink.

    threshold  — hard cut at a level. Sharp, posterised; fine for line art /
                 already-bilevel art, loses all tone.
    ordered    — Bayer 8×8 ordered dither. Deterministic per pixel, so it stays
                 stable across partial refreshes (no shimmer when only part of
                 the screen updates) — usually the right default on e-ink.
    floyd      — Floyd–Steinberg error diffusion. Best tonal fidelity for a
                 static full-refresh image, but error diffusion can crawl
                 between frames, so prefer it for covers shown on a full refresh.

A ``gamma`` knob pre-corrects tone before dithering: e-ink reads darker than
sRGB midtones suggest, so gamma < 1 lightens mids and keeps shadow detail.
"""

from __future__ import annotations

from PIL import Image

# Normalised Bayer 8×8 matrix (values 0..63).
_BAYER8 = (
    (0, 32, 8, 40, 2, 34, 10, 42),
    (48, 16, 56, 24, 50, 18, 58, 26),
    (12, 44, 4, 36, 14, 46, 6, 38),
    (60, 28, 52, 20, 62, 30, 54, 22),
    (3, 35, 11, 43, 1, 33, 9, 41),
    (51, 19, 59, 27, 49, 17, 57, 25),
    (15, 47, 7, 39, 13, 45, 5, 37),
    (63, 31, 55, 23, 61, 29, 53, 21),
)

THRESHOLD = "threshold"
ORDERED = "ordered"
FLOYD = "floyd"


def to_1bit(img: Image.Image, method: str = ORDERED,
            threshold: int = 128, gamma: float = 1.0) -> Image.Image:
    """Convert any image to a 1-bit ("1" mode) image via the chosen method."""
    gray = img.convert("L")
    if gamma != 1.0:
        inv = 1.0 / gamma
        gray = gray.point(lambda v: int(round(255 * (v / 255) ** inv)))

    if method == THRESHOLD:
        return gray.point(lambda v: 255 if v >= threshold else 0).convert("1")
    if method == FLOYD:
        return gray.convert("1")          # PIL's built-in Floyd–Steinberg
    if method == ORDERED:
        return _ordered(gray)
    raise ValueError(f"unknown dither method: {method!r}")


def _ordered(gray: Image.Image) -> Image.Image:
    """Bayer 8×8 ordered dither without external deps."""
    w, h = gray.size
    src = gray.load()
    out = Image.new("1", (w, h))
    dst = out.load()
    # Map matrix cell (0..63) to a 0..255 threshold centred on its bucket.
    thr = [[(_BAYER8[y][x] + 0.5) * 4 for x in range(8)] for y in range(8)]
    for y in range(h):
        row = thr[y & 7]
        for x in range(w):
            dst[x, y] = 255 if src[x, y] > row[x & 7] else 0
    return out


def paste(canvas, img: Image.Image, box, method: str = ORDERED,
          gamma: float = 1.0) -> None:
    """Dither ``img`` and paste it onto a Canvas at ``box`` (x, y[, w, h])."""
    if len(box) == 4:
        x, y, bw, bh = box
        img = img.convert("L")
        img.thumbnail((bw, bh))
    else:
        x, y = box
    canvas.image.paste(to_1bit(img, method=method, gamma=gamma), (x, y))
