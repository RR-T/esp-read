#!/usr/bin/env python3
"""Entry point for the e-reader display simulator.

    python simulator/run.py                          # portrait, Literata, native 1×
    python simulator/run.py --orientation landscape  # landscape layout
    python simulator/run.py --font pixel             # pick a starting font
    python simulator/run.py --scale 0.5              # fractional zoom (resampled)
    python simulator/run.py --actual-size --ppi 109  # true physical 5" size
    python simulator/run.py --ruler --actual-size --ppi 109   # calibration ruler

Font and orientation are also switchable live from the controls at the top of
the window.

Sizing notes
------------
At 1× one device pixel is one screen pixel, so on a typical ~100 PPI monitor the
panel looks ~2× life-size (the panel is ~220 PPI). For true physical size use
``--actual-size`` with your monitor's PPI, or ``--scale`` directly. macOS/Tk
can't report real PPI (Retina), so use ``--ruler`` to calibrate by eye.

The reader draws into a 1-bit framebuffer and pushes packed bytes through the
mock EPD; the window reconstructs pixels from those bytes (rotating for
portrait), so what you see is the device buffer. Fractional/actual-size zoom
resamples for display only — the buffer stays exact 960×552 1-bit.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from epd_sim import LANDSCAPE, PORTRAIT, Panel
from epd_sim.panel import PANEL_PPI
from reader import ReaderApp, fonts
from reader.ruler import PANEL_DIAG_IN, draw_ruler


def main() -> None:
    p = argparse.ArgumentParser(description='Waveshare 5" e-paper simulator')
    p.add_argument("--scale", type=float, default=1.0,
                   help="zoom factor; integer >=1 is pixel-perfect (default 1.0)")
    p.add_argument("--actual-size", action="store_true",
                   help="show at true physical 5\" size using --ppi")
    p.add_argument("--ppi", type=float, default=109.0,
                   help="your monitor's PPI, for --actual-size (default 109)")
    p.add_argument("--font", choices=fonts.FAMILIES, default=fonts.DEFAULT_FAMILY,
                   help=f"starting font family (default: {fonts.DEFAULT_FAMILY})")
    p.add_argument("--size", choices=fonts.size_steps(), default=fonts.DEFAULT_SIZE,
                   help=f"starting text size (default: {fonts.DEFAULT_SIZE})")
    p.add_argument("--weight", default="Regular",
                   help="starting body weight (e.g. Regular, Medium, SemiBold, Bold)")
    p.add_argument("--orientation", choices=(PORTRAIT, LANDSCAPE), default=PORTRAIT,
                   help="reader orientation (default: portrait)")
    p.add_argument("--ruler", action="store_true",
                   help="show a calibration ruler instead of the reader")
    p.add_argument("--demo", choices=("dither",),
                   help="show a demo card instead of the reader")
    args = p.parse_args()

    if args.actual_size:
        zoom = args.ppi / PANEL_PPI
        caption = f"actual size @ {args.ppi:g} PPI  (~{PANEL_DIAG_IN:.1f}\" diag)"
    else:
        zoom = args.scale
        caption = ""

    if args.ruler:
        # Ruler is a landscape calibration card regardless of reader orientation.
        panel = Panel(zoom=zoom, caption=caption, orientation=LANDSCAPE)
        panel.epd.init()
        panel.epd.display(draw_ruler(fonts.make(args.font)))
        panel.set_status("ruler — adjust --scale/--ppi to match a real ruler")
    elif args.demo == "dither":
        from reader.demo_dither import draw_demo
        panel = Panel(zoom=zoom, caption=caption, orientation=LANDSCAPE)
        panel.epd.init()
        panel.epd.display(draw_demo(fonts.make(args.font)))
        panel.set_status("dither demo — threshold vs ordered vs Floyd–Steinberg")
    else:
        panel = Panel(zoom=zoom, caption=caption, orientation=args.orientation)
        app = ReaderApp(panel, font_family=args.font, orientation=args.orientation,
                        size=args.size, body_weight=args.weight)
        app.start()

    panel.run()


if __name__ == "__main__":
    main()
