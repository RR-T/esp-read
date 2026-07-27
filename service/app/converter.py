"""EPUB -> text-v1 conversion.

SHELVED FALLBACK — not used by the OPDS library server. The reader parses EPUB
on-device (CrossPoint), so this desktop text-flattening path is only relevant if
we ever build our own firmware. See docs/crosspoint-adoption-plan.md §4. Kept
in-tree (with tests) so that option stays cheap to revive.

Input is an ALREADY-DRM-FREE EPUB (see the hard boundary in CLAUDE.md — DRM
unlock happens upstream in Calibre, never here). This module parses the spine,
flattens each document to paragraphs/headings, and writes the device format.
"""

from __future__ import annotations

import logging
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from . import device_format as fmt
from .epub_meta import compute_book_id
from .models import BookMeta, Chapter

logger = logging.getLogger(__name__)

# Block-level tags whose text we keep, in document order.
_BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"]
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def _first_metadata(book: epub.EpubBook, name: str) -> str | None:
    values = book.get_metadata("DC", name)
    if values and values[0] and values[0][0]:
        return str(values[0][0]).strip()
    return None


def _flatten_document(html: bytes) -> list[tuple[bool, str]]:
    """Return [(is_heading, text)] paragraph blocks from one XHTML document."""
    soup = BeautifulSoup(html, "lxml")
    for bad in soup(["script", "style"]):
        bad.decompose()

    root = soup.body or soup
    blocks: list[tuple[bool, str]] = []
    for tag in root.find_all(_BLOCK_TAGS):
        # Skip a block that merely wraps another block we'll also visit
        # (e.g. a <blockquote> containing <p>), to avoid duplicated text.
        if tag.find(_BLOCK_TAGS):
            continue
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        blocks.append((tag.name in _HEADING_TAGS, text))
    return blocks


def _is_navigation(item) -> bool:
    """True for the EPUB3 nav document, which lives in the spine but is a table
    of contents, not readable body text."""
    return "nav" in getattr(item, "properties", []) or item.get_name().endswith(
        ("nav.xhtml", "toc.xhtml")
    )


def _spine_documents(book: epub.EpubBook):
    """Yield spine document items in reading order, skipping the nav/ToC doc."""
    for idref, _linear in book.spine:
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        if _is_navigation(item):
            continue
        yield item


def _derive_chapter_title(blocks: list[tuple[bool, str]], index: int) -> str:
    for is_heading, text in blocks:
        if is_heading:
            return text[:120]
    return f"Section {index + 1}"


def convert_epub(src: Path, converted_dir: Path, *, force: bool = False) -> BookMeta:
    """Convert one EPUB into converted/{book_id}/ and return its BookMeta.

    If the book is already cached (same content hash) the existing conversion is
    returned untouched unless `force` is set.
    """
    book_id = compute_book_id(src)
    out_dir = converted_dir / book_id
    meta_path = out_dir / fmt.META_FILENAME

    if meta_path.exists() and not force:
        logger.info("Book %s already converted, skipping (%s)", book_id, src.name)
        return BookMeta.model_validate_json(meta_path.read_text("utf-8"))

    logger.info("Converting %s -> %s", src.name, book_id)
    # ignore_ncx=True adopts ebooklib's announced future default (spine order is
    # authoritative for us; we don't use the NCX).
    book = epub.read_epub(str(src), options={"ignore_ncx": True})

    chapters_blocks: list[list[tuple[bool, str]]] = []
    chapter_titles: list[str] = []
    for index, item in enumerate(_spine_documents(book)):
        blocks = _flatten_document(item.get_content())
        if not blocks:
            continue
        chapters_blocks.append(blocks)
        chapter_titles.append(_derive_chapter_title(blocks, index))

    content, starts = fmt.build_content(chapters_blocks)
    content_bytes = content.encode("utf-8")

    title = _first_metadata(book, "title") or src.stem
    chapters = [
        Chapter(title=t, start=s) for t, s in zip(chapter_titles, starts, strict=True)
    ]

    meta = BookMeta(
        id=book_id,
        title=title,
        author=_first_metadata(book, "creator"),
        language=_first_metadata(book, "language"),
        source_filename=src.name,
        format=fmt.FORMAT_VERSION,
        content_bytes=len(content_bytes),
        chapter_count=len(chapters),
        chapters=chapters,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / fmt.CONTENT_FILENAME).write_bytes(content_bytes)
    meta_path.write_text(meta.model_dump_json(indent=2), "utf-8")

    logger.info(
        "Converted %s: %d chapters, %d KB", title, len(chapters), len(content_bytes) // 1024
    )
    return meta
