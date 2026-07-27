# E-Reader Library Service

Desktop microservice that serves **DRM-free EPUBs** to the ESP32-S3 reader over
LAN WiFi as an **OPDS catalog**. The reader (CrossPoint) parses EPUB on-device,
so this service stores and serves the *raw* EPUB — it does not convert them.

See `../docs/crosspoint-adoption-plan.md` for why the architecture pivoted from a
text converter to a library server.

> **Boundary:** the input is an *already-DRM-free* EPUB. DRM unlock happens
> upstream in Calibre — never in this service or on the device.

## What it does

1. Watches `library/incoming/` for `*.epub` files (drop one in → auto-ingests).
2. Ingests each into a content-addressed store: `library/books/{id}.epub` (the
   file) + `library/books/{id}.json` (title/author/language metadata). `id` =
   SHA-256 of the source, so re-adding a book reuses the entry.
3. Serves the library as an **OPDS 1.x Atom acquisition feed** plus raw EPUB
   downloads, for the reader's WiFi sync.

## API

| Method | Path                 | Purpose                                       |
|--------|----------------------|-----------------------------------------------|
| GET    | `/health`            | liveness probe                                |
| GET    | `/opds`              | OPDS Atom acquisition feed (point the reader here) |
| GET    | `/book/{id}.epub`    | raw EPUB (`application/epub+zip`, supports `Range`) |
| GET    | `/library`           | human/debug JSON index                        |
| GET    | `/time`              | server wall-clock (optional; unused by CrossPoint) |
| POST   | `/rescan`            | re-ingest everything in `incoming/`           |
| POST   | `/users/create`      | register a sync user                          |
| GET    | `/users/auth`        | validate sync credentials                     |
| GET    | `/syncs/progress/{document}` | fetch last reading progress           |
| PUT    | `/syncs/progress`    | store reading progress                        |

OPDS hrefs are absolute, built from the request host, so the reader's downloader
doesn't have to resolve them relative to the feed URL.

Each OPDS entry also carries `<esp:sha256>` (namespace `urn:esp-read`) — the full
digest of the EPUB, for the device to verify the download against (integrity;
adoption plan §3.2). CrossPoint ignores the unknown element today.

**Reading-progress sync (self-hosted koreader-sync-server).** The four
`/users/*` + `/syncs/*` endpoints implement the standard protocol CrossPoint's
KOReaderSyncClient speaks. Auth uses `x-auth-user` + `x-auth-key` (the client
sends `x-auth-key` as MD5(password) — we store/compare that, never the
plaintext). An unknown user's first authenticated request registers them
(trust-on-first-use), so no setup step is needed on the device. Progress is
stored per `(user, document)` under `library/sync/` and doubles as an off-device
backup of your place.

On the device: Settings → KOReader Sync → set Sync Server URL to
`http://<pc-ip>:8000` (or your proxied hostname), plus a username/password.

**OTA** is handled via GitHub Releases (adoption plan §3.5), so there is no OTA
endpoint here.

## Point the reader at it

On the device: Settings → OPDS Servers → add `http://<pc-ip>:8000/opds`
(find `<pc-ip>` with `ip addr`). Plain HTTP on the LAN avoids the ~55 KB TLS heap
cost on the ESP32.

## Run it

### Docker (intended deployment)

```bash
docker compose up --build
# LAN: http://<pc-ip>:8000/opds
```

Drop EPUBs into `service/library/incoming/` — they ingest automatically.

**Behind a reverse proxy (Caddy).** The container runs uvicorn with
`--proxy-headers --forwarded-allow-ips=*`, so `X-Forwarded-Proto` from Caddy is
honoured and OPDS absolute URLs use the external `https` scheme. Caddy preserves
the `Host` header by default, so no extra config is needed; a minimal site block
is just `reverse_proxy ereader-service:8000`.

### Local (development)

```bash
cd service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

### Tests

```bash
pip install -r requirements-dev.txt
pytest            # synthetic EPUB → ingest → OPDS + download, no real books needed
```

## Configuration

| Env var        | Default      | Meaning                              |
|----------------|--------------|--------------------------------------|
| `LIBRARY_ROOT` | `./library`  | holds `incoming/` and `books/`       |
| `HOST`         | `0.0.0.0`    | uvicorn bind host (LAN reachable)    |
| `PORT`         | `8000`       | uvicorn bind port                    |

## The shelved text-mode converter

`app/converter.py` + `app/device_format.py` are the old "text-v1" flattening path.
They're **not used** by the OPDS server (the device parses EPUB itself), but are
kept in-tree with tests as the fallback should we ever build our own firmware
instead of adopting CrossPoint.
