"""API tests for the OPDS library server, driven off a temp library."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import _make_epub

ATOM = "{http://www.w3.org/2005/Atom}"
ESP = "{urn:esp-read}"


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    library = tmp_path / "library"
    incoming = library / "incoming"
    incoming.mkdir(parents=True)
    _make_epub(incoming / "sample.epub")

    monkeypatch.setenv("LIBRARY_ROOT", str(library))

    from app.main import app

    with TestClient(app) as c:  # runs lifespan: scan + ingest on startup
        yield c


def _book_id(client: TestClient) -> str:
    return client.get("/library").json()["books"][0]["id"]


def test_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}


def test_library_lists_ingested_book(client: TestClient):
    body = client.get("/library").json()
    assert body["count"] == 1
    book = body["books"][0]
    assert book["title"] == "Test Book"
    assert book["author"] == "A. Author"
    assert book["size_bytes"] > 0
    assert len(book["sha256"]) == 64  # full SHA-256 hex
    assert book["id"] == book["sha256"][:16]


def test_download_matches_published_hash(client: TestClient):
    """End-to-end integrity: the served EPUB hashes to the sha256 we advertise."""
    book = client.get("/library").json()["books"][0]
    epub = client.get(f"/book/{book['id']}.epub").content
    assert hashlib.sha256(epub).hexdigest() == book["sha256"]


def test_opds_feed_is_valid_acquisition_catalog(client: TestClient):
    resp = client.get("/opds")
    assert resp.status_code == 200
    assert "application/atom+xml" in resp.headers["content-type"]

    feed = ET.fromstring(resp.text)
    entries = feed.findall(f"{ATOM}entry")
    assert len(entries) == 1

    entry = entries[0]
    assert entry.find(f"{ATOM}title").text == "Test Book"
    assert entry.find(f"{ATOM}author/{ATOM}name").text == "A. Author"

    link = entry.find(f"{ATOM}link")
    assert link.get("rel") == "http://opds-spec.org/acquisition"
    assert link.get("type") == "application/epub+zip"
    # Absolute href pointing at the acquisition endpoint.
    assert link.get("href").endswith(f"/book/{_book_id(client)}.epub")

    # Integrity hash advertised for the device's post-download verify.
    sha = entry.find(f"{ESP}sha256")
    assert sha is not None and len(sha.text) == 64


def test_download_raw_epub(client: TestClient):
    book_id = _book_id(client)
    resp = client.get(f"/book/{book_id}.epub")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/epub+zip"
    assert resp.content[:2] == b"PK"  # zip magic — a real EPUB, not flattened text


def test_time_endpoint(client: TestClient):
    body = client.get("/time").json()
    assert body["unix"] > 0
    assert "T" in body["iso"]


def test_missing_book_is_404(client: TestClient):
    assert client.get("/book/deadbeefdeadbeef.epub").status_code == 404


# --- KOReader sync -------------------------------------------------------

ALICE = {"x-auth-user": "alice", "x-auth-key": "md5-of-secret"}


def test_kosync_auth_tofu_then_rejects_wrong_key(client: TestClient):
    # First auth registers the user (trust-on-first-use).
    ok = client.get("/users/auth", headers=ALICE)
    assert ok.status_code == 200 and ok.json() == {"authorized": "OK"}
    # Same user, wrong key → rejected.
    bad = client.get("/users/auth", headers={**ALICE, "x-auth-key": "wrong"})
    assert bad.status_code == 401


def test_kosync_progress_roundtrip(client: TestClient):
    client.get("/users/auth", headers=ALICE)  # register
    put = client.put(
        "/syncs/progress",
        headers=ALICE,
        json={
            "document": "doc-hash-1",
            "progress": "/body/DocFragment[3]",
            "percentage": 0.42,
            "device": "reader",
            "device_id": "esp-read",
        },
    )
    assert put.status_code == 200
    assert put.json()["document"] == "doc-hash-1"
    assert put.json()["timestamp"] > 0

    got = client.get("/syncs/progress/doc-hash-1", headers=ALICE).json()
    assert got["percentage"] == 0.42
    assert got["progress"] == "/body/DocFragment[3]"


def test_kosync_requires_auth(client: TestClient):
    assert client.get("/syncs/progress/doc-hash-1").status_code == 401
    assert client.put("/syncs/progress", json={"document": "x"}).status_code == 401


def test_kosync_create_user_conflict(client: TestClient):
    first = client.post("/users/create", json={"username": "bob", "password": "k"})
    assert first.status_code == 200 and first.json() == {"username": "bob"}
    dupe = client.post("/users/create", json={"username": "bob", "password": "k"})
    assert dupe.status_code == 402
