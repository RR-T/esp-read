"""Filesystem watcher: auto-convert EPUBs dropped into incoming/.

Runs a watchdog Observer on incoming/. On a created/moved .epub it triggers a
conversion on the watchdog worker thread. Editors often write then rename, so
both events are handled.
"""

from __future__ import annotations

import logging
from pathlib import Path

from watchdog.events import (
    FileCreatedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from .config import Settings
from .library import Library

logger = logging.getLogger(__name__)


class _IncomingHandler(FileSystemEventHandler):
    def __init__(self, library: Library) -> None:
        self._library = library

    def _handle(self, path_str: str) -> None:
        path = Path(path_str)
        if path.suffix.lower() != ".epub":
            return
        logger.info("Detected new EPUB: %s", path.name)
        self._library.ingest_file(path)

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            self._handle(event.dest_path)


def start_watcher(settings: Settings, library: Library) -> Observer:
    """Start and return a running Observer. Caller must .stop()/.join() it."""
    observer = Observer()
    observer.schedule(
        _IncomingHandler(library), str(settings.incoming_dir), recursive=False
    )
    observer.start()
    logger.info("Watching %s for new EPUBs", settings.incoming_dir)
    return observer
