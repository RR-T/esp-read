"""Pixel-perfect simulator of the Waveshare 5" e-paper panel."""

from . import dither
from .epd import EPD
from .framebuffer import (
    HEIGHT,
    LANDSCAPE,
    PORTRAIT,
    WIDTH,
    Canvas,
    MonoFrameBuffer,
)
from .panel import Panel

__all__ = [
    "EPD", "MonoFrameBuffer", "Canvas", "Panel", "dither",
    "WIDTH", "HEIGHT", "LANDSCAPE", "PORTRAIT",
]
