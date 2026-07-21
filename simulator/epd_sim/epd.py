"""Mock of the Waveshare 5" e-paper driver.

This mirrors the surface the ESP firmware would call (init / clear / display /
display_partial / sleep) so reader code written against it is one rename away
from talking to the real Waveshare driver. The simulator deliberately accepts a
**packed byte buffer** in `display()` — exactly what the firmware hands the
panel — so the on-screen pixels come from the device byte layout, not from a
convenient in-memory image. That is what makes the preview pixel-perfect.

Nominal hardware timings (from the build guide) are reported via the callbacks
but not slept through in full, so iterating on the UI stays snappy. The panel
applies a short visual "flash" on a full refresh to echo the real e-ink look.
"""

from __future__ import annotations

from typing import Callable, Optional

from .framebuffer import BUFFER_SIZE, HEIGHT, WIDTH

# Nominal refresh times quoted in the build guide / CLAUDE.md.
FULL_REFRESH_MS = 1800
PARTIAL_REFRESH_MS = 700


class EPD:
    """Driver-shaped facade over the tkinter panel.

    Parameters
    ----------
    on_display:
        Called with (packed_bytes, full_refresh) whenever the firmware pushes a
        frame. The panel window wires this up to repaint itself.
    on_log:
        Optional sink for human-readable driver events (init, sleep, timings).
    """

    WIDTH = WIDTH
    HEIGHT = HEIGHT

    def __init__(
        self,
        on_display: Callable[[bytes, bool], None],
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._on_display = on_display
        self._log = on_log or (lambda *_a: None)
        self._initialised = False
        self._asleep = False
        self.full_refreshes = 0
        self.partial_refreshes = 0

    # -- lifecycle ---------------------------------------------------------
    def init(self) -> None:
        self._initialised = True
        self._asleep = False
        self._log("EPD init (full)")

    def sleep(self) -> None:
        self._asleep = True
        self._log("EPD deep sleep")

    # -- refresh -----------------------------------------------------------
    def clear(self) -> None:
        self._log("EPD clear -> white")
        self._on_display(b"\xff" * BUFFER_SIZE, True)
        self.full_refreshes += 1

    def display(self, packed: bytes) -> None:
        """Full refresh — clears ghosting, ~1.8s on hardware."""
        self._guard(packed)
        self.full_refreshes += 1
        self._log(f"full refresh (~{FULL_REFRESH_MS}ms)  #{self.full_refreshes}")
        self._on_display(packed, True)

    def display_partial(self, packed: bytes) -> None:
        """Partial refresh — faster (~0.7s), accumulates ghosting."""
        self._guard(packed)
        self.partial_refreshes += 1
        self._log(
            f"partial refresh (~{PARTIAL_REFRESH_MS}ms)  #{self.partial_refreshes}"
        )
        self._on_display(packed, False)

    # -- internal ----------------------------------------------------------
    def _guard(self, packed: bytes) -> None:
        if not self._initialised:
            raise RuntimeError("EPD.display() before init()")
        if self._asleep:
            # On real hardware you must re-init after sleep; surface the bug.
            raise RuntimeError("EPD.display() while asleep — call init() first")
        if len(packed) != BUFFER_SIZE:
            raise ValueError(
                f"frame is {len(packed)} bytes, panel expects {BUFFER_SIZE}"
            )
