"""Self-hosted koreader-sync-server, so reading progress stays on our LAN.

CrossPoint's KOReaderSyncClient speaks the standard protocol:
    POST /users/create              register (username + md5(password))
    GET  /users/auth                validate credentials
    GET  /syncs/progress/{document} fetch last progress for a document
    PUT  /syncs/progress            store progress

Auth headers: `x-auth-user` and `x-auth-key` (the client sends `x-auth-key` as
MD5(password) — we store and compare that value; we never see the plaintext).
The `document` id is a content hash the device computes, so we just key on it.

Registration is trust-on-first-use: an unknown user's first authenticated
request registers them with the key they present, so no separate setup step is
needed on the device. Safe on a private LAN; documented in the adoption plan.

Progress is a per-book position, so it also serves as an off-device backup should
the SD copy (`progress.bin`) ever corrupt.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ProgressUpdate(BaseModel):
    """Body of PUT /syncs/progress (fields per the koreader-sync protocol)."""

    document: str
    progress: str = ""  # position marker (e.g. an xpath); opaque to us
    percentage: float = 0.0  # 0..1 — the real cross-device signal
    device: str = ""
    device_id: str = ""


class SyncStore:
    """JSON-backed credential + progress store, persisted under sync_dir so it
    survives container rebuilds (the library dir is bind-mounted)."""

    def __init__(self, sync_dir: Path) -> None:
        sync_dir.mkdir(parents=True, exist_ok=True)
        self._users_path = sync_dir / "users.json"
        self._progress_path = sync_dir / "progress.json"
        self._lock = threading.Lock()
        self._users: dict[str, str] = self._load(self._users_path)
        self._progress: dict[str, dict[str, dict]] = self._load(self._progress_path)

    @staticmethod
    def _load(path: Path) -> dict:
        try:
            return json.loads(path.read_text("utf-8")) if path.exists() else {}
        except Exception:  # noqa: BLE001 — a corrupt store must not crash startup
            logger.exception("Unreadable sync store %s; starting empty", path)
            return {}

    @staticmethod
    def _save(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, indent=2), "utf-8")

    def authenticate(self, user: str | None, key: str | None) -> bool:
        """Validate credentials; register the user (TOFU) if unknown."""
        if not user or not key:
            return False
        with self._lock:
            existing = self._users.get(user)
            if existing is None:
                self._users[user] = key
                self._save(self._users_path, self._users)
                logger.info("kosync: registered user %r (trust-on-first-use)", user)
                return True
            return existing == key

    def create_user(self, user: str, key: str) -> bool:
        """Explicit registration. Returns False if the user already exists."""
        with self._lock:
            if user in self._users:
                return False
            self._users[user] = key
            self._save(self._users_path, self._users)
            return True

    def get_progress(self, user: str, document: str) -> dict | None:
        with self._lock:
            return self._progress.get(user, {}).get(document)

    def put_progress(self, user: str, update: ProgressUpdate) -> int:
        """Store progress, returning the server timestamp."""
        timestamp = int(time.time())
        record = {
            "document": update.document,
            "progress": update.progress,
            "percentage": update.percentage,
            "device": update.device,
            "device_id": update.device_id,
            "timestamp": timestamp,
        }
        with self._lock:
            self._progress.setdefault(user, {})[update.document] = record
            self._save(self._progress_path, self._progress)
        return timestamp
