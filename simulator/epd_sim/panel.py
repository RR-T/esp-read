"""Tkinter window that renders the simulated panel pixel-perfect.

The window does *not* draw the reader UI directly. It only knows how to take a
packed byte buffer (the device framebuffer), reconstruct it via
``MonoFrameBuffer.unpack`` — proving the bytes survive a round trip — and paint
the resulting 1-bit pixels with an e-ink-ish palette at an integer scale
(NEAREST, so one device pixel is exactly N screen pixels).

It also draws the three physical buttons from the build guide's pin map and
forwards both clicks and keyboard shortcuts to handlers the reader registers.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, Iterable

from PIL import Image, ImageTk

from .epd import EPD
from .framebuffer import HEIGHT, LANDSCAPE, PORTRAIT, WIDTH, Canvas

# E-ink palette — two tones only (still 1-bit data, just themed for the eye).
PAPER = (0xDD, 0xDB, 0xD2)   # warm off-white
INK = (0x26, 0x26, 0x24)     # near-black
BEZEL = "#3a3a3e"
CHROME_BG = "#1f1f22"
CHROME_FG = "#c8c8cc"

# Physical buttons (label, logical name, pin note) — see CLAUDE.md pin map.
BUTTONS = [
    ("◀  Back", "back", "D5 / GPIO6"),
    ("Menu", "menu", "D11 / GPIO42"),
    ("Fwd  ▶", "fwd", "D4 / GPIO5"),
]

# Keyboard -> logical button.
KEYS = {
    "Left": "back",
    "Right": "fwd",
    "space": "fwd",
    "m": "menu",
    "Return": "menu",
}


# The real panel is ~220 PPI; used to label/derive physical-size zoom.
PANEL_PPI = 220


class Panel:
    def __init__(self, zoom: float = 1.0, caption: str = "",
                 orientation: str = LANDSCAPE,
                 title: str = "esp-read panel sim") -> None:
        self.zoom = max(0.05, float(zoom))
        # Integer zoom >=1 -> NEAREST (pixel-perfect). Otherwise LANCZOS
        # (fractional / downscale for actual physical size), which softens to
        # grays — realistic for e-ink, but no longer a 1:1 pixel mapping.
        self._integer_zoom = abs(self.zoom - round(self.zoom)) < 1e-6 and self.zoom >= 1
        self.orientation = orientation
        self._recompute_dst()

        self.root = tk.Tk()
        self.root.title(title)
        self.root.configure(bg=CHROME_BG)
        self.root.resizable(False, False)

        self._handlers: Dict[str, Callable[[], None]] = {}
        self._photo: ImageTk.PhotoImage | None = None
        self._flashing = False
        self._after_ids: list[str] = []
        self._font_label_to_name: Dict[str, str] = {}
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        zlabel = f"{self.zoom:g}×" + ("" if self._integer_zoom else " (resampled)")
        text = f'Waveshare 5"  ·  {WIDTH}×{HEIGHT}  ·  1-bit mono  ·  {zlabel}'
        if caption:
            text += f"  ·  {caption}"
        tk.Label(self.root, text=text, bg=CHROME_BG, fg=CHROME_FG,
                 font=("Helvetica", 12), pady=6).pack()

        # Live controls (font / orientation selectors added by the reader).
        self._controls = tk.Frame(self.root, bg=CHROME_BG)
        self._controls.pack(pady=(0, 6))

        # The panel image, inside a bezel.
        bezel = tk.Frame(self.root, bg=BEZEL, padx=10, pady=10)
        bezel.pack(padx=16)
        self._screen = tk.Label(bezel, bd=0, bg=PAPER_HEX())
        self._screen.pack()

        # Button row.
        row = tk.Frame(self.root, bg=CHROME_BG)
        row.pack(fill="x", padx=16, pady=(12, 4))
        for label, name, pin in BUTTONS:
            col = tk.Frame(row, bg=CHROME_BG)
            col.pack(side="left", expand=True, fill="x", padx=6)
            tk.Button(
                col, text=label, font=("Helvetica", 13, "bold"),
                command=lambda n=name: self._fire(n),
                bg="#2c2c30", fg=CHROME_FG, activebackground="#3a3a40",
                activeforeground="#ffffff", relief="flat", bd=0, pady=8,
            ).pack(fill="x")
            tk.Label(col, text=pin, bg=CHROME_BG, fg="#6a6a70",
                     font=("Helvetica", 9)).pack()

        # Status line (driver log).
        self._status = tk.Label(
            self.root, text="", bg=CHROME_BG, fg="#7a9a7a",
            font=("Menlo", 10), anchor="w", padx=16,
        )
        self._status.pack(fill="x", pady=(2, 10))

        for key, name in KEYS.items():
            self.root.bind(f"<{key}>", lambda _e, n=name: self._fire(n))

        # The driver the reader draws through.
        self.epd = EPD(on_display=self._render, on_log=self.set_status)

    # -- public API --------------------------------------------------------
    def bind_button(self, name: str, handler: Callable[[], None]) -> None:
        self._handlers[name] = handler

    def set_status(self, text: str) -> None:
        self._status.configure(text=f"epd: {text}")

    def set_display_orientation(self, orientation: str) -> None:
        """Rotate the displayed image to match the reader's orientation."""
        self.orientation = orientation
        self._recompute_dst()

    def add_font_selector(self, names: Iterable[str], current: str,
                          callback: Callable[[str], None],
                          labeller: Callable[[str], str] = str) -> None:
        names = list(names)
        self._font_label_to_name = {labeller(n): n for n in names}
        var = tk.StringVar(value=labeller(current))
        tk.Label(self._controls, text="Font:", bg=CHROME_BG, fg=CHROME_FG,
                 font=("Helvetica", 11)).pack(side="left", padx=(0, 4))
        om = tk.OptionMenu(self._controls, var, *[labeller(n) for n in names],
                           command=lambda lbl: callback(self._font_label_to_name[lbl]))
        om.configure(bg="#2c2c30", fg=CHROME_FG, highlightthickness=0,
                     relief="flat", font=("Helvetica", 11),
                     activebackground="#3a3a40", activeforeground="#fff")
        om["menu"].configure(bg="#2c2c30", fg=CHROME_FG)
        om.pack(side="left", padx=(0, 18))

    def add_weight_selector(self, weights: Iterable[str], current: str,
                            callback: Callable[[str], None]) -> None:
        self._weight_cb = callback
        self._weight_var = tk.StringVar(value=current)
        tk.Label(self._controls, text="Weight:", bg=CHROME_BG, fg=CHROME_FG,
                 font=("Helvetica", 11)).pack(side="left", padx=(0, 4))
        self._weight_menu = tk.OptionMenu(self._controls, self._weight_var, current,
                                          command=lambda w: callback(w))
        self._weight_menu.configure(bg="#2c2c30", fg=CHROME_FG, highlightthickness=0,
                                    relief="flat", font=("Helvetica", 11),
                                    activebackground="#3a3a40", activeforeground="#fff")
        self._weight_menu["menu"].configure(bg="#2c2c30", fg=CHROME_FG)
        self._weight_menu.pack(side="left", padx=(0, 18))
        self.set_weight_options(weights, current)

    def set_weight_options(self, weights: Iterable[str], current: str) -> None:
        """Repopulate the weight dropdown (called when the font changes)."""
        menu = self._weight_menu["menu"]
        menu.delete(0, "end")
        for w in weights:
            menu.add_command(
                label=w, command=lambda v=w: (self._weight_var.set(v),
                                              self._weight_cb(v)))
        self._weight_var.set(current)

    def add_size_selector(self, steps: Iterable[str], current: str,
                          callback: Callable[[str], None],
                          labeller: Callable[[str], str] = str) -> None:
        self._size_cb = callback
        self._size_var = tk.StringVar()
        tk.Label(self._controls, text="Size:", bg=CHROME_BG, fg=CHROME_FG,
                 font=("Helvetica", 11)).pack(side="left", padx=(0, 4))
        self._size_menu = tk.OptionMenu(self._controls, self._size_var, "")
        self._size_menu.configure(bg="#2c2c30", fg=CHROME_FG, highlightthickness=0,
                                  relief="flat", font=("Helvetica", 11),
                                  activebackground="#3a3a40", activeforeground="#fff")
        self._size_menu["menu"].configure(bg="#2c2c30", fg=CHROME_FG)
        self._size_menu.pack(side="left", padx=(0, 18))
        self.set_size_options(steps, current, labeller)

    def set_size_options(self, steps: Iterable[str], current: str,
                         labeller: Callable[[str], str] = str) -> None:
        """(Re)populate the size dropdown — labels carry the px for the font."""
        menu = self._size_menu["menu"]
        menu.delete(0, "end")
        for s in steps:
            lbl = labeller(s)
            menu.add_command(label=lbl, command=lambda l=lbl, v=s: (
                self._size_var.set(l), self._size_cb(v)))
        self._size_var.set(labeller(current))

    def add_orientation_selector(self, current: str,
                                 callback: Callable[[str], None]) -> None:
        var = tk.StringVar(value=current)
        tk.Label(self._controls, text="Orientation:", bg=CHROME_BG, fg=CHROME_FG,
                 font=("Helvetica", 11)).pack(side="left", padx=(0, 4))
        for val in (PORTRAIT, LANDSCAPE):
            tk.Radiobutton(
                self._controls, text=val.capitalize(), value=val, variable=var,
                command=lambda v=val: callback(v), bg=CHROME_BG, fg=CHROME_FG,
                selectcolor="#2c2c30", activebackground=CHROME_BG,
                activeforeground="#fff", font=("Helvetica", 11),
                highlightthickness=0, bd=0,
            ).pack(side="left")

    def run(self) -> None:
        self.root.mainloop()

    # -- rendering ---------------------------------------------------------
    def _render(self, packed: bytes, full_refresh: bool) -> None:
        if full_refresh and not self._flashing:
            self._flash(packed)
        else:
            self._paint(packed)

    def _flash(self, packed: bytes) -> None:
        """Brief invert-and-settle to echo a full e-ink refresh."""
        self._flashing = True
        black = b"\x00" * len(packed)
        white = b"\xff" * len(packed)
        self._paint(black)
        self._after_ids += [
            self.root.after(55, lambda: self._paint(white)),
            self.root.after(110, lambda: self._paint(packed)),
            self.root.after(120, self._end_flash),
        ]

    def _end_flash(self) -> None:
        self._flashing = False

    def _on_close(self) -> None:
        for aid in self._after_ids:
            try:
                self.root.after_cancel(aid)
            except tk.TclError:
                pass
        self.root.destroy()

    def _paint(self, packed: bytes) -> None:
        try:
            self._paint_now(packed)
        except tk.TclError:
            pass  # window torn down mid-flash; nothing to draw

    def _recompute_dst(self) -> None:
        # Displayed image size depends on orientation (portrait is rotated).
        base = (HEIGHT, WIDTH) if self.orientation == PORTRAIT else (WIDTH, HEIGHT)
        self._dst = (round(base[0] * self.zoom), round(base[1] * self.zoom))

    def _paint_now(self, packed: bytes) -> None:
        # Round-trip through the device bytes, then rotate upright for display.
        img = Canvas.display_image(packed, self.orientation)
        gray = img.convert("L")
        r = gray.point(_lut(INK[0], PAPER[0]))
        g = gray.point(_lut(INK[1], PAPER[1]))
        b = gray.point(_lut(INK[2], PAPER[2]))
        rgb = Image.merge("RGB", (r, g, b))
        if self._dst != rgb.size:
            resample = Image.NEAREST if self._integer_zoom else Image.LANCZOS
            rgb = rgb.resize(self._dst, resample)
        self._photo = ImageTk.PhotoImage(rgb)
        self._screen.configure(image=self._photo)

    # -- input -------------------------------------------------------------
    def _fire(self, name: str) -> None:
        handler = self._handlers.get(name)
        if handler:
            handler()


def _lut(ink_val: int, paper_val: int) -> list[int]:
    # mode "1"->"L" yields 0 (black) or 255 (white); map each tone.
    return [ink_val if v < 128 else paper_val for v in range(256)]


def PAPER_HEX() -> str:
    return "#%02x%02x%02x" % PAPER
