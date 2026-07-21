"""Calibration ruler for the ``--actual-size`` / ``--ruler`` modes.

macOS/Tk reports a useless 72 "PPI" (logical points, Retina-blind), so there is
no reliable way to auto-detect physical screen size. Instead we draw a ruler
*into the framebuffer at the panel's real 220 PPI* and let you calibrate by eye:
hold a physical ruler to the screen and tweak ``--scale`` until the on-screen
centimetres match real ones. At that zoom the whole panel is shown at true size
(≈ 5" diagonal), because the ruler and the UI share the same scaling.
"""

from __future__ import annotations

from epd_sim.framebuffer import HEIGHT, WIDTH, MonoFrameBuffer

PANEL_PPI = 220
BLACK, WHITE = 0, 255

# True physical panel size, for the on-screen note.
PANEL_W_IN = WIDTH / PANEL_PPI            # ≈ 4.36"
PANEL_H_IN = HEIGHT / PANEL_PPI           # ≈ 2.51"
PANEL_DIAG_IN = (PANEL_W_IN**2 + PANEL_H_IN**2) ** 0.5  # ≈ 5.03"


def draw_ruler(fonts) -> bytes:
    """Render the calibration screen and return its packed bytes."""
    fb = MonoFrameBuffer()
    fb.clear(WHITE)
    d = fb.draw

    margin = 40
    d.text((margin, 18), "Actual-size calibration", font=fonts.head, fill=BLACK)
    lines = [
        "Hold a real ruler to the screen and adjust --scale until these",
        "marks match. Then the panel is shown at its true physical size.",
        f"Panel: {PANEL_W_IN:.2f}in x {PANEL_H_IN:.2f}in  (~{PANEL_DIAG_IN:.1f}in diagonal),"
        f" {WIDTH}x{HEIGHT} @ {PANEL_PPI} PPI.",
    ]
    y = 64
    for line in lines:
        d.text((margin, y), line, font=fonts.ui, fill=BLACK)
        y += 26

    # --- inch ruler ---
    inch_y = 230
    px_per_in = PANEL_PPI
    d.text((margin, inch_y - 30), "inches", font=fonts.ui_bold, fill=BLACK)
    d.line((margin, inch_y, margin + int(PANEL_W_IN * px_per_in), inch_y),
           fill=BLACK, width=2)
    inch = 0
    x = margin
    while x <= WIDTH - margin:
        for t in range(10):  # tenths
            tx = margin + int((inch + t / 10) * px_per_in)
            if tx > WIDTH - margin:
                break
            h = 26 if t == 0 else (16 if t == 5 else 9)
            d.line((tx, inch_y, tx, inch_y - h), fill=BLACK, width=2 if t == 0 else 1)
        if inch >= 1:  # skip 0 to avoid colliding with the section label
            d.text((margin + int(inch * px_per_in) + 4, inch_y - 26),
                   str(inch), font=fonts.ui, fill=BLACK)
        inch += 1
        x = margin + int(inch * px_per_in)

    # --- cm ruler ---
    cm_y = 360
    px_per_cm = PANEL_PPI / 2.54
    d.text((margin, cm_y - 30), "centimetres", font=fonts.ui_bold, fill=BLACK)
    d.line((margin, cm_y, margin + int(PANEL_W_IN * 2.54 * px_per_cm), cm_y),
           fill=BLACK, width=2)
    cm = 0
    while margin + cm * px_per_cm <= WIDTH - margin:
        for mm in range(10):
            mx = margin + int((cm + mm / 10) * px_per_cm)
            if mx > WIDTH - margin:
                break
            h = 26 if mm == 0 else (16 if mm == 5 else 9)
            d.line((mx, cm_y, mx, cm_y - h), fill=BLACK, width=2 if mm == 0 else 1)
        if cm >= 1:
            d.text((margin + int(cm * px_per_cm) + 4, cm_y - 26),
                   str(cm), font=fonts.ui, fill=BLACK)
        cm += 1

    d.text((margin, HEIGHT - 60),
           "Run without --ruler at the same --scale to use the reader at this size.",
           font=fonts.ui, fill=BLACK)
    return fb.packed()
