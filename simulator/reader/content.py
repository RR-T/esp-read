"""Book model, text pagination, and a few public-domain sample books.

This is the "text mode" device format from the build guide (§10): the device
receives flat blocks — headings and paragraphs — and does layout + pagination
itself. The simulator runs the same logic the ESP firmware eventually will, so
page breaks here predict page breaks on hardware (given matching fonts/metrics).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple

BlockKind = Literal["h", "p"]
Block = Tuple[BlockKind, str]  # ("h", "Chapter I")  /  ("p", "It was ...")


@dataclass
class Line:
    """One laid-out line on a page, positioned relative to the text area top."""
    text: str
    kind: BlockKind
    y: int


@dataclass
class Book:
    title: str
    author: str
    blocks: List[Block]
    cover: Optional[str] = None     # filename in assets/images/, or None
    pages: List[List[Line]] = field(default_factory=list)  # filled by paginate()

    @property
    def page_count(self) -> int:
        return len(self.pages)


@dataclass
class LayoutMetrics:
    """Geometry + line heights, all in device pixels."""
    width: int            # text column width
    height: int           # text column height
    body_leading: int     # baseline-to-baseline for paragraph text
    head_leading: int     # for heading text
    para_gap: int         # extra space after a paragraph
    head_gap_before: int  # space above a heading
    head_gap_after: int   # space below a heading


def _wrap(text: str, font, max_width: int) -> List[str]:
    """Greedy word wrap using the font's real glyph advances."""
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if font.getlength(trial) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def paginate(book: Book, body_font, head_font, m: LayoutMetrics) -> None:
    """Flow the book's blocks into fixed-height pages of positioned lines."""
    pages: List[List[Line]] = []
    page: List[Line] = []
    y = 0

    def flush() -> None:
        nonlocal page, y
        if page:
            pages.append(page)
        page = []
        y = 0

    for kind, text in book.blocks:
        font = head_font if kind == "h" else body_font
        leading = m.head_leading if kind == "h" else m.body_leading

        if kind == "h" and page:
            y += m.head_gap_before

        for line in _wrap(text, font, m.width):
            if y + leading > m.height:
                flush()
            page.append(Line(line, kind, y))
            y += leading

        y += m.head_gap_after if kind == "h" else m.para_gap

    flush()
    book.pages = pages


# --------------------------------------------------------------------------
# Sample library — all public domain (Gutenberg-era texts).
# --------------------------------------------------------------------------

def _book(title, author, *blocks: Block, cover: Optional[str] = None) -> Book:
    return Book(title=title, author=author, blocks=list(blocks), cover=cover)


SAMPLE_BOOKS: List[Book] = [
    _book(
        "Alice's Adventures in Wonderland", "Lewis Carroll",
        ("h", "Chapter I — Down the Rabbit-Hole"),
        ("p", "Alice was beginning to get very tired of sitting by her sister "
              "on the bank, and of having nothing to do: once or twice she had "
              "peeped into the book her sister was reading, but it had no "
              "pictures or conversations in it, “and what is the use of a "
              "book,” thought Alice, “without pictures or "
              "conversations?”"),
        ("p", "So she was considering in her own mind (as well as she could, "
              "for the hot day made her feel very sleepy and stupid), whether "
              "the pleasure of making a daisy-chain would be worth the trouble "
              "of getting up and picking the daisies, when suddenly a White "
              "Rabbit with pink eyes ran close by her."),
        ("p", "There was nothing so very remarkable in that; nor did Alice "
              "think it so very much out of the way to hear the Rabbit say to "
              "itself, “Oh dear! Oh dear! I shall be late!” (when she "
              "thought it over afterwards, it occurred to her that she ought to "
              "have wondered at this, but at the time it all seemed quite "
              "natural); but when the Rabbit actually took a watch out of its "
              "waistcoat-pocket, and looked at it, and then hurried on, Alice "
              "started to her feet, for it flashed across her mind that she had "
              "never before seen a rabbit with either a waistcoat-pocket, or a "
              "watch to take out of it, and burning with curiosity, she ran "
              "across the field after it."),
        ("p", "The rabbit-hole went straight on like a tunnel for some way, and "
              "then dipped suddenly down, so suddenly that Alice had not a "
              "moment to think about stopping herself before she found herself "
              "falling down a very deep well."),
        cover="cover_alice.jpg",
    ),
    _book(
        "The Time Machine", "H. G. Wells",
        ("h", "Chapter I"),
        ("p", "The Time Traveller (for so it will be convenient to speak of "
              "him) was expounding a recondite matter to us. His pale grey eyes "
              "shone and twinkled, and his usually pale face was flushed and "
              "animated. The fire burnt brightly, and the soft radiance of the "
              "incandescent lights in the lilies of silver caught the bubbles "
              "that flashed and passed in our glasses."),
        ("p", "Our chairs, being his patents, embraced and caressed us rather "
              "than submitted to be sat upon, and there was that luxurious "
              "after-dinner atmosphere when thought runs gracefully free of the "
              "trammels of precision. And he put it to us in this way — "
              "marking the points with a lean forefinger — as we sat and "
              "lazily admired his earnestness over this new paradox (as we "
              "thought it) and his fecundity."),
        ("p", "“You must follow me carefully. I shall have to controvert "
              "one or two ideas that are almost universally accepted. The "
              "geometry, for instance, they taught you at school is founded on "
              "a misconception.”"),
        cover="cover_timemachine.jpg",
    ),
    _book(
        "Pride and Prejudice", "Jane Austen",
        ("h", "Chapter I"),
        ("p", "It is a truth universally acknowledged, that a single man in "
              "possession of a good fortune, must be in want of a wife."),
        ("p", "However little known the feelings or views of such a man may be "
              "on his first entering a neighbourhood, this truth is so well "
              "fixed in the minds of the surrounding families, that he is "
              "considered the rightful property of some one or other of their "
              "daughters."),
        ("p", "“My dear Mr. Bennet,” said his lady to him one day, "
              "“have you heard that Netherfield Park is let at last?”"),
        ("p", "Mr. Bennet replied that he had not."),
        ("p", "“But it is,” returned she; “for Mrs. Long has just "
              "been here, and she told me all about it.”"),
        cover="cover_pride.jpg",
    ),
]
