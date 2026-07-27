"""EPUB identity + metadata extraction.

Shared by the OPDS library server (raw-EPUB path, current architecture) and the
text-mode converter (build-your-own-firmware fallback). This module reads only
what we need to catalogue a book — it does NOT flatten or transform content.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ebooklib import epub


@dataclass(frozen=True)
class EpubMetadata:
    title: str
    author: str | None
    language: str | None
    identifier: str | None


def hash_file(src: Path) -> str:
    """Full SHA-256 hex digest of a file. Used both for the content-addressed id
    and as the end-to-end integrity hash the device verifies after download (see
    docs/crosspoint-adoption-plan.md §3.2)."""
    return hashlib.sha256(src.read_bytes()).hexdigest()


def book_id_from_hash(digest: str) -> str:
    """The 16-char content id derived from a full SHA-256 digest."""
    return digest[:16]


def compute_book_id(src: Path) -> str:
    """Content-addressed id: first 16 hex chars of the source file's SHA-256.

    Deterministic, so re-adding the same EPUB reuses the cached ingest.
    """
    return book_id_from_hash(hash_file(src))


def _first(book: epub.EpubBook, name: str) -> str | None:
    values = book.get_metadata("DC", name)
    if values and values[0] and values[0][0]:
        return str(values[0][0]).strip()
    return None


def read_metadata(src: Path) -> EpubMetadata:
    """Parse Dublin Core metadata from an EPUB. Falls back to the filename stem
    for a missing title."""
    # ignore_ncx=True adopts ebooklib's announced future default (we rely on the
    # OPF/spine, never the NCX).
    book = epub.read_epub(str(src), options={"ignore_ncx": True})
    return EpubMetadata(
        title=_first(book, "title") or src.stem,
        author=_first(book, "creator"),
        language=_first(book, "language"),
        identifier=_first(book, "identifier"),
    )
