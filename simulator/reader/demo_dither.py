"""A side-by-side dithering comparison card (``--demo dither``).

The panel can't show grey, so the honest way to judge halftoning is to view the
1-bit *results* next to each other on the real device. This builds a continuous-
tone test image and renders it three ways — hard threshold, Bayer ordered, and
Floyd–Steinberg — so you can see what each buys on actual e-ink pixels.
"""

from __future__ import annotations

import os

from PIL import Image, ImageChops, ImageDraw, ImageOps

from epd_sim import Canvas
from epd_sim.dither import FLOYD, ORDERED, THRESHOLD, to_1bit

BLACK, WHITE = 0, 255
_PHOTO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "assets", "images", "demo_earthrise.jpg")


def _test_image(w: int, h: int) -> Image.Image:
    """A real photo (rich tones show dithering best); synthetic fallback."""
    if os.path.exists(_PHOTO):
        photo = ImageOps.fit(Image.open(_PHOTO).convert("L"), (w, h),
                             method=Image.LANCZOS)
        return ImageOps.autocontrast(photo, cutoff=1)
    radial = Image.radial_gradient("L").resize((w, h))          # black centre
    linear = Image.linear_gradient("L").resize((w, h))          # top→bottom
    img = ImageChops.add(radial, linear, scale=2.0)             # average the two
    img = ImageChops.invert(img)                                # light centre
    d = ImageDraw.Draw(img)
    d.ellipse((w * 0.30, h * 0.12, w * 0.70, h * 0.42), fill=235)  # highlight
    d.ellipse((w * 0.55, h * 0.58, w * 0.92, h * 0.92), fill=40)   # shadow
    return img


def draw_demo(fonts) -> bytes:
    cv = Canvas("landscape")          # comparison card is landscape
    cv.clear(WHITE)
    d = cv.draw
    W, H = cv.width, cv.height

    d.text((40, 18), "1-bit dithering — same image, three conversions",
           font=fonts.head, fill=BLACK)
    d.text((40, 64),
           "Text is never dithered (hinted mono). Images need halftoning to fake grey.",
           font=fonts.ui, fill=BLACK)

    cell_w, img_w, img_h, top = 280, 220, 300, 110
    methods = [
        (THRESHOLD, "Threshold", "hard cut — tone lost"),
        (ORDERED, "Ordered (Bayer 8×8)", "stable across partial refresh"),
        (FLOYD, "Floyd–Steinberg", "best tone, full-refresh only"),
    ]
    src = _test_image(img_w, img_h)
    gap = (W - 2 * 40 - 3 * img_w) // 2
    for i, (method, title, note) in enumerate(methods):
        x = 40 + i * (img_w + gap)
        cv.image.paste(to_1bit(src, method=method), (x, top))
        d.rectangle((x, top, x + img_w, top + img_h), outline=BLACK, width=1)
        d.text((x, top + img_h + 10), title, font=fonts.ui_bold, fill=BLACK)
        d.text((x, top + img_h + 32), note, font=fonts.ui, fill=BLACK)

    return cv.packed()
