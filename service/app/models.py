"""Pydantic models — the JSON contract between the service and the reader.

The reader (CrossPoint) consumes the OPDS Atom feed and raw EPUBs; the JSON
models below back the human-facing `/library` index and the on-disk book
records. `Chapter`/`BookMeta` belong to the shelved text-mode converter (the
build-your-own-firmware fallback) and are not used by the OPDS server path.
"""

from __future__ import annotations

from pydantic import BaseModel


# --- OPDS library server (current architecture) --------------------------


class LibraryBook(BaseModel):
    """One catalogued raw EPUB. Persisted as books/{id}.json and surfaced in
    both the OPDS feed and the /library JSON index."""

    id: str
    title: str
    author: str | None = None
    language: str | None = None
    identifier: str | None = None
    filename: str
    size_bytes: int
    sha256: str  # full digest; device verifies the download against this


class LibraryIndex(BaseModel):
    """Top-level response for GET /library."""

    count: int
    books: list[LibraryBook]


class TimeResponse(BaseModel):
    """Server wall-clock time (optional; unused by CrossPoint upstream)."""

    unix: int
    iso: str


# --- text-mode converter fallback (shelved; see converter.py) ------------


class Chapter(BaseModel):
    """A chapter within a text-v1 converted book. `start` is a byte offset."""

    title: str
    start: int


class BookMeta(BaseModel):
    """Full metadata for a text-v1 converted book (fallback path)."""

    id: str
    title: str
    author: str | None = None
    language: str | None = None
    source_filename: str
    format: str = "text-v1"
    content_bytes: int
    chapter_count: int
    chapters: list[Chapter]
