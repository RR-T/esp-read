"""The e-reader UX: a small deep-sleep-style state machine.

Two screens — a library list and a reading view — drawn into a 1-bit ``Canvas``
(which rotates into the real 960×552 device framebuffer) and pushed through the
mock ``EPD``. Three buttons drive it, matching the hardware:

    fwd  : next item / next page
    back : previous item / previous page
    menu : open the selected book / return to the library

Runs **portrait** by default (panel mounted on its side, 552×960 logical) with
slim chrome so more text fits per page; landscape is still available. Font family
and orientation can be changed live from the GUI.

The reader mirrors the firmware's refresh discipline from CLAUDE.md: partial
refreshes for page turns, a full refresh every ``FULL_EVERY`` turns (and on any
screen change) to clear e-ink ghosting. Reading positions are remembered per
book, as the device would save them before sleeping.
"""

from __future__ import annotations

import time
from typing import Dict, List

from epd_sim import EPD, PORTRAIT, Canvas

from . import covers, fonts
from .content import SAMPLE_BOOKS, Book, paginate

FULL_EVERY = 6           # full refresh cadence (page turns)
BLACK, WHITE = 0, 255
UI_PX = 16               # status/footer text size


class ReaderApp:
    def __init__(self, panel, font_family: str = fonts.DEFAULT_FAMILY,
                 orientation: str = PORTRAIT, size: str = fonts.DEFAULT_SIZE,
                 body_weight: str = "Regular") -> None:
        self.panel = panel
        self.epd: EPD = panel.epd
        self.font_family = font_family
        self.orientation = orientation
        self.size = size
        self.body_weight = body_weight

        self.books: List[Book] = SAMPLE_BOOKS

        # State.
        self.mode = "library"          # "library" | "reading"
        self.selection = 0
        self.book: Book | None = None
        self.page = 0
        self.positions: Dict[int, int] = {}   # book index -> last page
        self.turns_since_full = 0
        self.battery = 72              # simulated telemetry
        self._covers: Dict[tuple, object] = {}

        self._load_fonts()
        self._apply_geometry()
        self._rebuild_layout()

        panel.bind_button("back", self.on_back)
        panel.bind_button("fwd", self.on_fwd)
        panel.bind_button("menu", self.on_menu)
        panel.set_display_orientation(orientation)
        # Optional GUI controls (no-ops if the panel doesn't provide them).
        if hasattr(panel, "add_font_selector"):
            panel.add_font_selector(fonts.FAMILIES, font_family, self.set_font,
                                    labeller=fonts.label)
        if hasattr(panel, "add_weight_selector"):
            panel.add_weight_selector(fonts.weights(font_family), body_weight,
                                      self.set_weight)
        if hasattr(panel, "add_size_selector"):
            panel.add_size_selector(fonts.size_steps(), size, self.set_size,
                                    labeller=self._size_label)
        if hasattr(panel, "add_orientation_selector"):
            panel.add_orientation_selector(orientation, self.set_orientation)

    # -- configuration -----------------------------------------------------
    def _load_fonts(self) -> None:
        self.fonts = fonts.make(self.font_family, self.size, self.body_weight)
        self.f_body = self.fonts.body
        self.f_head = self.fonts.head
        self.f_ui = self.fonts.ui
        self.f_ui_bold = self.fonts.ui_bold
        self.f_list_title = self.fonts.list_title
        self.f_list_author = self.fonts.list_author

    def _apply_geometry(self) -> None:
        portrait = self.orientation == PORTRAIT
        # Logical screen size for this orientation.
        cv = Canvas(self.orientation)
        self.W, self.H = cv.width, cv.height
        # Slim chrome — slimmer still in portrait, where vertical space is gold.
        self.margin_x = 34 if portrait else 56
        self.header_h = 34 if portrait else 42
        self.footer_h = 30 if portrait else 36
        gap_top = 12 if portrait else 16
        self.text_top = self.header_h + gap_top
        self.text_w = self.W - 2 * self.margin_x
        self.text_h = self.H - self.text_top - self.footer_h - 8

    def _rebuild_layout(self) -> None:
        self._covers.clear()           # sizes/faces changed → regenerate covers
        self.metrics = self.fonts.layout(self.text_w, self.text_h)
        for book in self.books:
            paginate(book, self.f_body, self.f_head, self.metrics)
        if self.book is not None:
            self.page = min(self.page, self.book.page_count - 1)

    def set_font(self, family: str) -> None:
        self.font_family = family
        if self.body_weight not in fonts.weights(family):
            self.body_weight = "Regular"
        self._load_fonts()
        self._rebuild_layout()
        if hasattr(self.panel, "set_weight_options"):
            self.panel.set_weight_options(fonts.weights(family), self.body_weight)
        if hasattr(self.panel, "set_size_options"):
            self.panel.set_size_options(fonts.size_steps(), self.size,
                                        self._size_label)
        self.render(full=True)

    def _size_label(self, step: str) -> str:
        return f"{step} · {fonts.body_px(self.font_family, step)}px"

    def set_weight(self, weight: str) -> None:
        self.body_weight = weight
        self._load_fonts()
        self._rebuild_layout()
        self.render(full=True)

    def set_size(self, size: str) -> None:
        self.size = size
        self._load_fonts()
        self._rebuild_layout()
        self.render(full=True)

    def set_orientation(self, orientation: str) -> None:
        if self.book is not None:
            self.positions[self.selection] = self.page
        self.orientation = orientation
        self.panel.set_display_orientation(orientation)
        self._apply_geometry()
        self._rebuild_layout()
        if self.book is not None:
            self.page = min(self.positions.get(self.selection, 0),
                            self.book.page_count - 1)
        self.render(full=True)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self.epd.init()
        self.render(full=True)

    # -- input handlers ----------------------------------------------------
    def on_fwd(self) -> None:
        if self.mode == "library":
            self.selection = (self.selection + 1) % len(self.books)
            self.render(full=True)
        else:
            assert self.book is not None
            if self.page < self.book.page_count - 1:
                self.page += 1
                self.render()

    def on_back(self) -> None:
        if self.mode == "library":
            self.selection = (self.selection - 1) % len(self.books)
            self.render(full=True)
        else:
            if self.page > 0:
                self.page -= 1
                self.render()

    def on_menu(self) -> None:
        if self.mode == "library":
            self._open_book(self.selection)
        else:
            self._return_to_library()

    def _open_book(self, index: int) -> None:
        self.book = self.books[index]
        self.page = self.positions.get(index, 0)
        self.mode = "reading"
        self.render(full=True)

    def _return_to_library(self) -> None:
        # Save reading position, as the firmware would before sleeping.
        self.positions[self.selection] = self.page
        self.mode = "library"
        self.book = None
        self.render(full=True)

    # -- rendering ---------------------------------------------------------
    def render(self, full: bool = False) -> None:
        cv = Canvas(self.orientation)
        cv.clear(WHITE)
        if self.mode == "library":
            self._draw_library(cv)
        else:
            self._draw_reading(cv)

        if full:
            self.turns_since_full = 0
            self.epd.display(cv.packed())
        else:
            self.turns_since_full += 1
            if self.turns_since_full >= FULL_EVERY:
                self.turns_since_full = 0
                self.epd.display(cv.packed())          # ghost-clearing full
            else:
                self.epd.display_partial(cv.packed())

    # -- screens -----------------------------------------------------------
    def _draw_library(self, cv: Canvas) -> None:
        d = cv.draw
        self._status_bar(cv, left="Library")

        tsize = getattr(self.f_list_title, "size", 30)
        asize = getattr(self.f_list_author, "size", 18)
        content_h = tsize + 6 + asize
        thumb_h = max(content_h + 24, 116)     # roomy enough for cover art to read
        thumb_w = round(thumb_h * 0.68)
        row_h = thumb_h + 18
        text_x = self.margin_x + thumb_w + 16
        text_w = self.W - text_x - self.margin_x
        y = self.text_top - 4
        for i, book in enumerate(self.books):
            y0 = y + i * row_h
            selected = i == self.selection
            if selected:
                d.rounded_rectangle((self.margin_x - 12, y0 - 6,
                                     self.W - self.margin_x + 12, y0 + thumb_h + 6),
                                    radius=10, fill=BLACK)
            cv.image.paste(self._cover(i, thumb_w, thumb_h), (self.margin_x, y0))
            fg = WHITE if selected else BLACK
            ty = y0 + (thumb_h - content_h) // 2
            title = _ellipsize(d, book.title, self.f_list_title, text_w)
            d.text((text_x, ty), title, font=self.f_list_title, fill=fg)
            pages = "page" if book.page_count == 1 else "pages"
            meta = f"{book.author}   ·   {book.page_count} {pages}"
            d.text((text_x, ty + tsize + 6), meta,
                   font=self.f_list_author, fill=fg)

        self._footer_text(cv, "back / fwd: choose      menu: open")

    def _cover(self, index: int, w: int, h: int):
        key = (index, self.font_family, w, h)
        img = self._covers.get(key)
        if img is None:
            book = self.books[index]
            img = covers.make_cover(book.title, self.font_family, w, h,
                                    seed=index * 7 + len(book.title),
                                    image=book.cover)
            self._covers[key] = img
        return img

    def _draw_reading(self, cv: Canvas) -> None:
        assert self.book is not None
        d = cv.draw
        self._status_bar(cv, left=self.book.title)

        for line in self.book.pages[self.page]:
            font = self.f_head if line.kind == "h" else self.f_body
            d.text((self.margin_x, self.text_top + line.y), line.text,
                   font=font, fill=BLACK)

        self._reading_footer(cv)

    # -- chrome ------------------------------------------------------------
    def _status_bar(self, cv: Canvas, left: str) -> None:
        d = cv.draw
        ty = (self.header_h - UI_PX) // 2
        left = _ellipsize(d, left, self.f_ui_bold, self.text_w * 0.62)
        d.text((self.margin_x, ty), left, font=self.f_ui_bold, fill=BLACK)

        right = self.W - self.margin_x
        clock = time.strftime("%H:%M")
        cw = d.textlength(clock, font=self.f_ui)
        d.text((right - cw, ty), clock, font=self.f_ui, fill=BLACK)
        right -= cw + 18

        pct = f"{self.battery}%"
        pw = d.textlength(pct, font=self.f_ui)
        d.text((right - pw, ty), pct, font=self.f_ui, fill=BLACK)
        right -= pw + 8
        self._battery_icon(cv, right)

        d.line((self.margin_x, self.header_h, self.W - self.margin_x,
                self.header_h), fill=BLACK, width=1)

    def _battery_icon(self, cv: Canvas, right_x: float) -> None:
        d = cv.draw
        w, h = 28, 14
        x1, x0 = right_x, right_x - w
        y0 = (self.header_h - h) // 2
        y1 = y0 + h
        d.rectangle((x0, y0, x1, y1), outline=BLACK, width=2)
        d.rectangle((x1 + 1, y0 + 4, x1 + 3, y1 - 4), fill=BLACK)  # terminal nub
        fill_w = int((w - 6) * max(0, min(100, self.battery)) / 100)
        if fill_w > 0:
            d.rectangle((x0 + 3, y0 + 3, x0 + 3 + fill_w, y1 - 3), fill=BLACK)

    def _reading_footer(self, cv: Canvas) -> None:
        assert self.book is not None
        d = cv.draw
        fy = self.H - self.footer_h
        ty = fy + (self.footer_h - UI_PX) // 2
        d.line((self.margin_x, fy, self.W - self.margin_x, fy),
               fill=BLACK, width=1)
        d.text((self.margin_x, ty),
               f"Page {self.page + 1} of {self.book.page_count}",
               font=self.f_ui, fill=BLACK)

        bar_w = min(200, self.text_w // 2)
        bar_h = 9
        bx1 = self.W - self.margin_x
        bx0 = bx1 - bar_w
        by = fy + (self.footer_h - bar_h) // 2
        d.rectangle((bx0, by, bx1, by + bar_h), outline=BLACK, width=1)
        frac = (self.page + 1) / self.book.page_count
        d.rectangle((bx0, by, bx0 + int(bar_w * frac), by + bar_h), fill=BLACK)

    def _footer_text(self, cv: Canvas, text: str) -> None:
        d = cv.draw
        fy = self.H - self.footer_h
        ty = fy + (self.footer_h - UI_PX) // 2
        d.line((self.margin_x, fy, self.W - self.margin_x, fy),
               fill=BLACK, width=1)
        d.text((self.margin_x, ty), text, font=self.f_ui, fill=BLACK)


def _ellipsize(draw, text: str, font, max_w: float) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"
