"""1-bit packed mono framebuffer matching the Waveshare 5" panel.

The Waveshare 5" e-paper is 960x552, 1-bit mono. On the device the firmware
composes a packed framebuffer and pushes it to the panel over SPI. The packing
is 8 horizontal pixels per byte, MSB-first, row by row:

    bytes_per_row = 960 / 8 = 120
    total         = 120 * 552 = 66_240 bytes (~64.7 KB per full screen)

That 64.7 KB matches the per-page figure quoted in the build guide (§10), so
this class deliberately stores and round-trips the *exact* device byte layout —
draw into it with PIL, export `.packed()` to get the literal bytes the ESP would
DMA to the panel, then reconstruct from those bytes to validate nothing is lost.

Bit convention (matches PIL mode "1" tobytes): bit set (1) = white, clear (0) =
black. `Image.tobytes()` / `Image.frombytes("1", ...)` use exactly this packing,
so we lean on PIL rather than hand-rolling bit twiddling.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

WIDTH = 960
HEIGHT = 552
ROW_BYTES = WIDTH // 8          # 120
BUFFER_SIZE = ROW_BYTES * HEIGHT  # 66_240

BLACK = 0
WHITE = 255

LANDSCAPE = "landscape"
PORTRAIT = "portrait"


class MonoFrameBuffer:
    """A 960x552 1-bit canvas you draw into, then export as packed bytes."""

    WIDTH = WIDTH
    HEIGHT = HEIGHT
    ROW_BYTES = ROW_BYTES
    BUFFER_SIZE = BUFFER_SIZE

    def __init__(self) -> None:
        # Mode "1" is genuinely 1 bit per pixel in memory and on tobytes().
        self._img = Image.new("1", (WIDTH, HEIGHT), WHITE)
        self._draw = ImageDraw.Draw(self._img)

    # -- drawing surface ---------------------------------------------------
    @property
    def image(self) -> Image.Image:
        """The PIL image. Useful for pasting other 1-bit images in."""
        return self._img

    @property
    def draw(self) -> ImageDraw.ImageDraw:
        """An ImageDraw handle for text/shape rendering."""
        return self._draw

    def clear(self, color: int = WHITE) -> None:
        self._draw.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), fill=color)

    # -- device byte layout ------------------------------------------------
    def packed(self) -> bytes:
        """Return the exact 66_240-byte packed buffer the panel consumes."""
        data = self._img.tobytes()
        assert len(data) == BUFFER_SIZE, (
            f"packed buffer is {len(data)} bytes, expected {BUFFER_SIZE}"
        )
        return data

    @staticmethod
    def unpack(data: bytes) -> Image.Image:
        """Reconstruct an image from packed bytes (the panel's view of them)."""
        if len(data) != BUFFER_SIZE:
            raise ValueError(
                f"expected {BUFFER_SIZE} bytes, got {len(data)}"
            )
        return Image.frombytes("1", (WIDTH, HEIGHT), data)


class Canvas:
    """A logical drawing surface that knows the panel's mounted orientation.

    The hardware framebuffer is *always* 960×552 (the panel is physically a
    landscape strip). To run the reader in portrait you mount the panel on its
    side, draw the UI into a 552×960 surface, and rotate it into the 960×552
    device buffer at push time. This class hides that: draw in logical
    coordinates (``.width``×``.height``), then ``.packed()`` rotates as needed
    and returns the exact device bytes — so portrait is still validated against
    the real packed framebuffer, not a convenient sideways image.
    """

    def __init__(self, orientation: str = LANDSCAPE) -> None:
        if orientation not in (LANDSCAPE, PORTRAIT):
            raise ValueError(f"bad orientation: {orientation!r}")
        self.orientation = orientation
        # Portrait swaps the logical dimensions.
        self.width, self.height = (
            (HEIGHT, WIDTH) if orientation == PORTRAIT else (WIDTH, HEIGHT)
        )
        self._img = Image.new("1", (self.width, self.height), WHITE)
        self._draw = ImageDraw.Draw(self._img)

    @property
    def image(self) -> Image.Image:
        return self._img

    @property
    def draw(self) -> ImageDraw.ImageDraw:
        return self._draw

    def clear(self, color: int = WHITE) -> None:
        self._draw.rectangle((0, 0, self.width - 1, self.height - 1), fill=color)

    def packed(self) -> bytes:
        """Rotate (if portrait) into the 960×552 device layout and pack."""
        img = self._img
        if self.orientation == PORTRAIT:
            img = img.rotate(-90, expand=True)   # 552×960 -> 960×552
        data = img.tobytes()
        assert len(data) == BUFFER_SIZE, (
            f"packed buffer is {len(data)} bytes, expected {BUFFER_SIZE}"
        )
        return data

    @staticmethod
    def display_image(data: bytes, orientation: str = LANDSCAPE) -> Image.Image:
        """Unpack device bytes back to the upright logical image for display."""
        img = MonoFrameBuffer.unpack(data)
        if orientation == PORTRAIT:
            img = img.rotate(90, expand=True)    # 960×552 -> 552×960 (inverse)
        return img
