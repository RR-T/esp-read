"""FastAPI app: an OPDS library server for the ESP32 reader over LAN.

The reader (CrossPoint) browses an OPDS catalog and downloads raw EPUBs, which it
parses on-device. So this service stores + serves raw DRM-free EPUBs; it no longer
flattens them (that text-mode path is the shelved fallback in converter.py).

Endpoints:
    GET  /health              liveness probe
    GET  /opds                OPDS Atom acquisition feed (the catalog)
    GET  /book/{id}.epub      raw EPUB (application/epub+zip, supports Range)
    GET  /library             human/debug JSON index
    GET  /time                server wall-clock (optional; unused by CrossPoint)
    POST /rescan              re-ingest everything in incoming/

    -- self-hosted koreader-sync-server (reading progress) --
    POST /users/create        register a sync user
    GET  /users/auth          validate credentials
    GET  /syncs/progress/{document}   fetch last progress
    PUT  /syncs/progress      store progress

Deployment note: intended to run behind a reverse proxy (Caddy). The app is
started with uvicorn --proxy-headers so X-Forwarded-Proto is honoured and OPDS
absolute URLs use the external scheme; Caddy preserves the Host header by default.

Planned (see docs/crosspoint-adoption-plan.md §3.5): an OTA path — currently
handled via GitHub Releases, so no service endpoint needed.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response

from .config import load_settings
from .koreader import ProgressUpdate, SyncStore
from .library import Library
from .models import LibraryIndex, TimeResponse
from .opds import FEED_TYPE, build_catalog
from .watcher import start_watcher

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("ereader.service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    library = Library(settings)
    library.scan_and_ingest_all()
    observer = start_watcher(settings, library)

    app.state.library = library
    app.state.settings = settings
    app.state.sync = SyncStore(settings.sync_dir)
    try:
        yield
    finally:
        observer.stop()
        observer.join(timeout=5)
        logger.info("Watcher stopped")


app = FastAPI(title="E-Reader Library Service", version="0.2.0", lifespan=lifespan)


def _library(app: FastAPI) -> Library:
    return app.state.library


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/time", response_model=TimeResponse)
def get_time() -> TimeResponse:
    now = datetime.now(timezone.utc)
    return TimeResponse(unix=int(now.timestamp()), iso=now.isoformat())


@app.get("/library", response_model=LibraryIndex)
def get_library() -> LibraryIndex:
    return _library(app).index()


@app.post("/rescan", response_model=LibraryIndex)
def rescan() -> LibraryIndex:
    lib = _library(app)
    lib.scan_and_ingest_all()
    return lib.index()


@app.get("/opds")
def get_opds(request: Request) -> Response:
    # Absolute hrefs built from how the reader reached us (e.g. http://<pc-ip>:8000).
    base_url = str(request.base_url).rstrip("/")
    updated = datetime.now(timezone.utc).isoformat()
    xml = build_catalog(_library(app).index(), base_url=base_url, updated_iso=updated)
    return Response(content=xml, media_type=FEED_TYPE)


@app.get("/book/{book_id}.epub")
def get_book_epub(book_id: str) -> FileResponse:
    path = _library(app).book_path(book_id)
    if path is None:
        raise HTTPException(status_code=404, detail="book not found")
    # FileResponse honours HTTP Range, so the downloader can resume/stream.
    return FileResponse(
        path, media_type="application/epub+zip", filename=f"{book_id}.epub"
    )


# --- self-hosted koreader-sync-server ------------------------------------


def require_user(
    request: Request,
    x_auth_user: str | None = Header(default=None),
    x_auth_key: str | None = Header(default=None),
) -> str:
    """Auth dependency for the sync endpoints. Registers unknown users (TOFU)."""
    store: SyncStore = request.app.state.sync
    if not store.authenticate(x_auth_user, x_auth_key):
        raise HTTPException(status_code=401, detail="unauthorized")
    return x_auth_user  # type: ignore[return-value]  # non-None once authenticated


@app.post("/users/create")
def kosync_create_user(payload: dict, request: Request) -> dict:
    user = payload.get("username")
    key = payload.get("password")  # client sends MD5(password)
    if not user or not key:
        raise HTTPException(status_code=400, detail="username and password required")
    if not request.app.state.sync.create_user(user, key):
        raise HTTPException(status_code=402, detail="username is already registered")
    return {"username": user}


@app.get("/users/auth")
def kosync_auth(user: str = Depends(require_user)) -> dict:
    return {"authorized": "OK"}


@app.get("/syncs/progress/{document}")
def kosync_get_progress(
    document: str, request: Request, user: str = Depends(require_user)
) -> dict:
    return request.app.state.sync.get_progress(user, document) or {}


@app.put("/syncs/progress")
def kosync_put_progress(
    update: ProgressUpdate, request: Request, user: str = Depends(require_user)
) -> dict:
    timestamp = request.app.state.sync.put_progress(user, update)
    return {"document": update.document, "timestamp": timestamp}
