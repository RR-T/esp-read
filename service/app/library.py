"""Library management: ingest raw EPUBs, index them, serve them.

The reader parses EPUB on-device (CrossPoint), so this service stores and serves
the *raw* DRM-free EPUB — no flattening/conversion. Ingest is content-addressed:
books/{id}.epub (the file) + books/{id}.json (its LibraryBook record).

Thread-safe enough for the watcher (background thread) and the API (request
thread): a single lock guards ingest so the same file isn't processed twice.
"""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path

from .config import Settings
from .epub_meta import book_id_from_hash, hash_file, read_metadata
from .models import LibraryBook, LibraryIndex

logger = logging.getLogger(__name__)

_EPUB_SUFFIX = ".epub"


class Library:
    """Owns the raw-EPUB store and drives ingest of incoming files."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ingest_lock = threading.Lock()

    # -- ingest -------------------------------------------------------------

    def ingest_file(self, src: Path, *, force: bool = False) -> LibraryBook | None:
        """Ingest one incoming file into the book store. Returns None for
        non-EPUBs / errors."""
        if src.suffix.lower() != _EPUB_SUFFIX:
            return None
        with self._ingest_lock:
            try:
                return self._ingest(src, force=force)
            except Exception:  # noqa: BLE001 — one bad EPUB must not kill the service
                logger.exception("Failed to ingest %s", src)
                return None

    def _ingest(self, src: Path, *, force: bool) -> LibraryBook:
        digest = hash_file(src)  # full SHA-256; hashed once, reused for id + integrity
        book_id = book_id_from_hash(digest)
        epub_path = self._settings.books_dir / f"{book_id}{_EPUB_SUFFIX}"
        record_path = self._settings.books_dir / f"{book_id}.json"

        if record_path.exists() and epub_path.exists() and not force:
            logger.info("Book %s already ingested, skipping (%s)", book_id, src.name)
            return LibraryBook.model_validate_json(record_path.read_text("utf-8"))

        logger.info("Ingesting %s -> %s", src.name, book_id)
        meta = read_metadata(src)
        shutil.copyfile(src, epub_path)

        record = LibraryBook(
            id=book_id,
            title=meta.title,
            author=meta.author,
            language=meta.language,
            identifier=meta.identifier,
            filename=src.name,
            size_bytes=epub_path.stat().st_size,
            sha256=digest,
        )
        record_path.write_text(record.model_dump_json(indent=2), "utf-8")
        logger.info("Ingested %r (%d KB)", record.title, record.size_bytes // 1024)
        return record

    def scan_and_ingest_all(self) -> int:
        """Ingest every EPUB currently in incoming/. Returns count ingested."""
        count = 0
        for src in sorted(self._settings.incoming_dir.glob(f"*{_EPUB_SUFFIX}")):
            if self.ingest_file(src) is not None:
                count += 1
        logger.info("Initial scan complete: %d book(s) in incoming/", count)
        return count

    # -- reading the store --------------------------------------------------

    def _iter_records(self):
        for record_path in self._settings.books_dir.glob("*.json"):
            try:
                yield LibraryBook.model_validate_json(record_path.read_text("utf-8"))
            except Exception:  # noqa: BLE001
                logger.exception("Skipping unreadable record: %s", record_path)

    def index(self) -> LibraryIndex:
        books = sorted(self._iter_records(), key=lambda b: b.title.lower())
        return LibraryIndex(count=len(books), books=books)

    def get_record(self, book_id: str) -> LibraryBook | None:
        record_path = self._settings.books_dir / f"{book_id}.json"
        if not record_path.exists():
            return None
        return LibraryBook.model_validate_json(record_path.read_text("utf-8"))

    def book_path(self, book_id: str) -> Path | None:
        path = self._settings.books_dir / f"{book_id}{_EPUB_SUFFIX}"
        return path if path.exists() else None
