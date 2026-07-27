"""Service configuration, resolved from environment with sensible defaults.

Kept dependency-free (plain os.environ) so the container needs nothing beyond
the runtime requirements.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Resolved, absolute paths and network binding for the service."""

    library_root: Path
    incoming_dir: Path
    books_dir: Path
    sync_dir: Path
    host: str
    port: int


def load_settings() -> Settings:
    """Build Settings from environment variables, creating the library dirs.

    Env vars:
        LIBRARY_ROOT  base dir holding incoming/ and books/ (default ./library)
        HOST          uvicorn bind host (default 0.0.0.0 — LAN reachable)
        PORT          uvicorn bind port (default 8000)
    """
    root = Path(os.environ.get("LIBRARY_ROOT", "./library")).resolve()
    incoming = root / "incoming"
    books = root / "books"
    sync = root / "sync"

    for directory in (incoming, books, sync):
        directory.mkdir(parents=True, exist_ok=True)

    return Settings(
        library_root=root,
        incoming_dir=incoming,
        books_dir=books,
        sync_dir=sync,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
