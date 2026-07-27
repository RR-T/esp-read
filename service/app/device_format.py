"""The on-device "text-v1" format.

A converted book is a directory `converted/{book_id}/` containing:

    meta.json     BookMeta (see models.py) — index, title, chapter table
    content.txt   the flattened book text, UTF-8

content.txt layout
------------------
* Chapters are separated by a single FORM FEED byte (0x0C).
* Within a chapter, paragraphs are separated by a blank line ("\\n\\n").
* A paragraph that is a heading is prefixed with a single STX byte (0x02) at
  its very start, so the firmware can render it larger/bold. The 0x02 is part
  of the byte stream and counts toward chapter byte offsets.

Reading position on the device is simply a byte offset into content.txt.
Byte offsets (not character offsets) are used because the firmware seeks the
file by byte and streams UTF-8; this keeps the device dumb.

This module is the single source of truth for those control bytes so the
converter (writer) and any reader/validator agree.
"""

from __future__ import annotations

FORMAT_VERSION = "text-v1"

CHAPTER_BREAK = "\f"  # U+000C FORM FEED — between chapters
PARAGRAPH_BREAK = "\n\n"  # between paragraphs within a chapter
HEADING_MARK = "\x02"  # U+0002 STX — prefixes a heading paragraph

CONTENT_FILENAME = "content.txt"
META_FILENAME = "meta.json"


def build_content(chapters: list[list[tuple[bool, str]]]) -> tuple[str, list[int]]:
    """Assemble content.txt text and return (content, chapter_start_offsets).

    Args:
        chapters: list of chapters; each chapter is a list of (is_heading, text)
            paragraph blocks in reading order.

    Returns:
        (content, starts) where `starts[i]` is the UTF-8 BYTE offset at which
        chapter i's text begins (i.e. just after the preceding FORM FEED).
    """
    parts: list[str] = []
    starts: list[int] = []
    byte_offset = 0

    for blocks in chapters:
        if parts:  # separate from previous chapter
            parts.append(CHAPTER_BREAK)
            byte_offset += len(CHAPTER_BREAK.encode("utf-8"))

        starts.append(byte_offset)

        rendered_blocks = [
            (HEADING_MARK + text if is_heading else text) for is_heading, text in blocks
        ]
        chunk = PARAGRAPH_BREAK.join(rendered_blocks)
        parts.append(chunk)
        byte_offset += len(chunk.encode("utf-8"))

    return "".join(parts), starts
