# CrossPoint adoption — investigation & feature plan

**Status:** proposal (pending ratification). **Date:** 2026-07.
**Question it answers:** should we build our reader firmware on top of
[CrossPoint Reader](https://github.com/iandchasse/crosspoint-reader-de-link)
(branch `s3-port`, MIT) instead of writing our own, and what would we have to
build across display, storage, battery, service integration, and OTA?

> This document is the durable record of the source-level investigation of
> CrossPoint. Once the decision below is ratified, fold the outcome into
> `CLAUDE.md` and `ereader-build-guide.md` and delete the "UNDECIDED" language
> there.

---

## 1. Verdict

**Adopting CrossPoint is viable and attractive, and the port is smaller than it
looks.** On every axis, CrossPoint already implements the hard version of the
thing on our controller/CPU family:

- Its panel driver is **already an SSD1677**; its framebuffer polarity is
  **identical to ours** (bit 1 = white).
- Its power model is **already `esp_deep_sleep` + wake-as-reset + state-to-SD** —
  the same months-of-battery architecture in `CLAUDE.md`.
- **Pagination is cached to disk**, so a warm wake is *load position → deserialize
  one page → render*, with no re-parse. On-device parsing does **not** break the
  battery budget.
- OTA already reads a **GitHub Releases JSON** and works over plain LAN HTTP with
  zero code change.

**The one strategic consequence:** CrossPoint parses EPUB on-device, so our
`service/` **pivots from an EPUB→text converter to a library server** (OPDS feed
+ raw EPUB + optional progress sync + OTA host). The text-v1 converter is shelved
(kept only as the fallback if we ever build our own firmware).

**Commitment being made:** a fork we maintain — a hardware port on an actively
moving upstream. The `de-link` branch exists specifically to run CrossPoint on
non-Xteink hardware, so we are on a supported path. Upside: we inherit a very
capable reader (EPUB 2/3, hyphenation, kerning, footnotes, bookmarks, TOC/chapter
nav, OPDS, Calibre, WebDAV, KOReader sync, OTA, themes, 24 languages, RTL) for
mostly plumbing effort.

---

## 2. How adoption works structurally

Portability in CrossPoint is **not** virtual interfaces. `lib/hal/*` is a single
concrete layer that composes driver objects from a git submodule SDK
(`open-x4-sdk` → `github.com/iandchasse/community-sdk-de-link`), symlinked as
PlatformIO libs (`EInkDisplay`, `BatteryMonitor`, `InputManager`,
`SDCardManager`, `FrontlightManager`).

So the port is:

1. **Rewrite the `lib/hal/*` wrappers** to call our own drivers instead of the
   submodule drivers.
2. **Repin `lib/hal/HalGPIO.h`** to our pin map.
3. **Repoint two URLs** (OPDS server, OTA release).

`GfxRenderer`, the EPUB engine (`lib/Epub/*`), OPDS/KOReader, OTA logic, and the
UI/themes are untouched.

---

## 3. Per-dimension plan

### 3.1 Display

**Already there:** `lib/hal/HalDisplay` wraps `EInkDisplay` (SSD1677, 800×480
GDEQ0426T82 panel), register-init, internal OTP waveform (no LUT for normal
refresh). Framebuffer is **1 = white / 0 = black, MSB-first, `WIDTH/8` bytes/row**
— identical scheme to our `Epd5in0`. `GfxRenderer` reads geometry at runtime.

**Work items:**

- [ ] Rewrite `lib/hal/HalDisplay.{h,cpp}` to **own a `uint8_t framebuffer[66240]`**
      and wrap **our `Epd5in0`** (drop the `EInkDisplay` submodule dep). Wire
      `constexpr DISPLAY_WIDTH/HEIGHT/BUFFER_SIZE` to `Epd5in0::WIDTH/HEIGHT`
      (960/552) / `BUFFER_SIZE` (66240).
- [ ] Map refresh modes: `displayBuffer(FULL_REFRESH)` → `epd.displayFull(fb,
      invert=false)`; `FAST_REFRESH`/`HALF_REFRESH` → `epd.displayPartialFull(fb)`.
      **Do not invert** — polarity already matches.
- [ ] **Blocking compile fix:** `GfxRenderer`'s
      `static_assert(BW_BUFFER_CHUNK_SIZE * N == BUFFER_SIZE)` — 8000 does not
      divide 66240. Change chunk size to a divisor (e.g. 6624 → 10 chunks).
- [ ] Fix `GfxRenderer::drawPixel()` bounds-check (uses constexpr geometry) once
      constexpr is 960/552.
- [ ] Repin `HalGPIO.h` EPD/SPI (SCK7/MISO8/MOSI9/CS1/DC2/RST4/BUSY43); drop
      C3/X3 branches; stub grayscale (S3 already no-ops it); pick landscape
      orientation and verify text isn't mirrored/upside-down.

**Gotcha:** CrossPoint's FAST (partial) refresh is differential against the
controller's **RED RAM** (previous frame). Our `Epd5in0::displayPartialFull` is
currently approximate and does not seed that bank — **finish the RED-RAM
baseline in our driver**, or fall back to full-only refresh initially.

**Refs:** `lib/hal/HalDisplay.{h,cpp}`, `lib/hal/HalGPIO.{h,cpp}`,
`lib/GfxRenderer/GfxRenderer.{h,cpp}`, submodule
`open-x4-sdk/libs/display/EInkDisplay/*`. Our driver:
`firmware/epub-benchmark/src/Epd5in0.{h,cpp}`.

### 3.2 Storage

**Already there:** a writable **FAT filesystem is CrossPoint's single source of
truth** — downloaded EPUBs, the pagination/metadata cache
(`/.crosspoint/epub_<hash>/book.bin` + `sections/*.bin`), settings, reading
position (`progress.bin`, rewritten **every page turn**), SD fonts, screenshots.
Our **internal 16 MB flash is not the book store** — its partition table
(`app0`/`app1` 6.25 MB each, `nvs`, 3.5 MB `spiffs`, `coredump`) fits our chip
unchanged.

The code is split two ways:

| Layer | Backend | Bus |
|---|---|---|
| Submodule `SDCardManager` (`SdMan`) | **SdFat** | SPI, dedicated, `SD_CS=12`, 40 MHz |
| S3 `lib/hal/HalStorage` (`Storage`) | **`SD_MMC`** (SDIO) | dedicated SDIO pins |

**Either way CrossPoint assumes storage owns its own bus** — it implements none
of our shared-SPI discipline (init SD first, both CS parked high, no SD transfer
mid-refresh). Our design puts SD on the **shared** SPI bus with the panel
(`SD_CS=44`).

Capacity worry is **gone**: we now serve ~1 MB EPUBs + a few MB of per-book
cache, not 26 MB bitmaps → **XTSD 2 GB is ample**, and its wear-leveling + ECC
absorbs the per-page `progress.bin` writes.

**Decision — Path 1 (DECIDED).** Throughput was the deciding analysis: per-wake
reads are a few KB (dominated ~50–1000× by the e-ink refresh) and book downloads
are WiFi-bound, so Path 2's 3–5× SD speed only shows up in USB-MSC bulk copies —
not worth a pin-map/enclosure rework. Both paths were:

- **Path 1 (recommended): keep shared SPI; retarget storage to SdFat-over-SPI.**
  Point the storage HAL at `SdFat` on our shared `SPIClass` with `SD_CS=44`, and
  fold in the shared-bus discipline. Works with XTSD (SPI) and dev microSD; keeps
  the locked pin map. The submodule already contains an SdFat-SPI implementation
  to base this on (effectively reverting the S3 branch's `SD_MMC` change). The
  deep-sleep-per-page loop serialises SD vs panel access, so the shared bus is
  low-risk.
- **Path 2: give storage its own bus** (adopt `SD_MMC` as-is, or SdFat on a 2nd
  SPI host). Removes the "one device works, not both" bug class, but costs 3+
  dedicated SDIO pins, a pin-map rework, and wiring microSD/XTSD in SD mode
  (most microSD breakout *modules* are SPI-only).

**Work items (Path 1):**

- [ ] Repin `SD_CS` 12 → 44 (part of the general repin).
- [ ] Retarget the S3 storage backend `SD_MMC` → SdFat on the shared SPI bus.
- [ ] Add shared-bus CS/BUSY coordination into the storage HAL (net-new; our
      rules exist in `CLAUDE.md`, CrossPoint's code does not).
- [ ] Confirm the XTSD is wired for SPI mode.

**Integrity checking (Path 1 companion — required).** A shared SPI bus can
silently corrupt SD reads/writes, so we defend in three layers:

1. **Bus level** *(firmware)* — enable SdFat's SPI CRC (`USE_SD_CRC`). SD SPI mode
   leaves per-block CRC off by default for speed; turning it on catches bus
   read/write errors at the transport. Cheapest, most direct.
2. **Cache level** *(firmware/fork)* — add a CRC32 to CrossPoint's cached
   artifacts (`book.bin`, `section.bin`, `progress.bin`); verify on read, and
   rebuild (cache) or ignore (position) on mismatch → self-healing. CrossPoint
   already versions these files; we add a content checksum to the header.
3. **End-to-end** *(service done, firmware verify later)* — the service publishes
   each book's **full SHA-256** (`LibraryBook.sha256`, surfaced in `/library` JSON
   and as `<esp:sha256>` in the OPDS entry, namespace `urn:esp-read`); the device
   verifies the downloaded EPUB against it. We already hash for the `book_id`, so
   this is nearly free. CrossPoint's parser ignores the unknown element today; the
   firmware verify is a small future add.

CRC32 suffices for the on-device cache layer (corruption detection, not
security); SHA-256 is reused for the whole-file download check.

- [ ] *(firmware)* Enable `USE_SD_CRC` in the SdFat config.
- [ ] *(firmware/fork)* Add CRC32 header + verify/rebuild to the cache serializers.
- [ ] *(firmware/fork)* Verify downloaded EPUB against `<esp:sha256>` post-download.
- [x] *(service)* Publish `sha256` per book in `/library` + OPDS.

**Refs:** `lib/hal/HalStorage.{h,cpp}`, `lib/hal/FsCompat.h`, submodule
`open-x4-sdk/libs/hardware/SDCardManager/*`, `partitions.csv`, `platformio.ini`.
Service: `app/epub_meta.py` (`hash_file`), `app/opds.py` (`<esp:sha256>`).

### 3.3 Battery calibration

**Already there:** `BatteryMonitor` (submodule) = divider + ADC, **no fuel-gauge
IC** (matches our plan). Deep-sleep + state persistence match our model. Single
seam: `HalPowerManager::getBatteryPercentage()`. But its assumptions are
Xteink-specific and thin, so this is the dimension with the most net-new work.

**Work items:**

- [ ] Repoint battery ADC **GPIO4 → GPIO10** (`HalGPIO.h BAT_GPIO4`,
      `HalPowerManager.cpp`); ÷2 multiplier already matches our 220k/220k.
- [ ] Replace the **single un-averaged** ADC read with our **50–100-sample
      average**; expose `getBatteryMillivolts()`.
- [ ] Replace the hardcoded **cubic-polynomial** SOC with **our resting-voltage→
      SOC LUT** (from the MicroPython calibration tool) + 10% quantization +
      **hysteresis** (persist bucket in RTC memory).
- [ ] Replace **MCP73832 STAT-pin** charging detection (we don't have it) with
      **VBUS-presence** on our divided-5V ADC pin; add "holds ~4.2 V ⇒ full".
- [ ] Make the status bar show **"Charging…"** instead of the inflated CV-phase %
      (`BaseTheme::fillBatteryIcon`/`drawBatteryLeft`/`drawBatteryRight`).
- [ ] **Add a low-battery cutoff** (~3.4–3.5 V → save state + deep sleep). None
      exists upstream — design it ourselves.
- [ ] Rework `HalPowerManager::startDeepSleep()` ext1 wake from **one active-high
      power button** to **our 3 buttons (GPIO5/6/42)** — polarity TBD (tactile-to-
      GND ⇒ `ESP_EXT1_WAKEUP_ANY_LOW` + pullups).

**Deep-sleep findings (good news):** their model matches ours — true
`esp_deep_sleep_start()`, wake = chip reset, WiFi/display torn down, position +
settings on SD, clock in NVS + `RTC_NOINIT_ATTR`. That last is the pattern for
our persisted last-sync time. No light-sleep/LP-timer dependency to fight.

**Refs:** `lib/hal/HalPowerManager.{h,cpp}`, submodule
`open-x4-sdk/libs/hardware/BatteryMonitor/*`, `lib/hal/HalGPIO.{h,cpp}`,
`lib/hal/HalClock.cpp`, `src/main.cpp` (`enterDeepSleep`),
`src/components/themes/BaseTheme.cpp`.

### 3.4 Service integration (the pivot)

**The gating question — answered:** CrossPoint parses + **paginates on-device and
caches both to disk**, so a warm re-open/wake is *load position → deserialize one
page → render*. Cache lives at `/.crosspoint/epub_<std::hash(path)>/`:
`book.bin` (metadata cache v6) + `sections/<spineIndex>.bin` (pagination cache
v24, with a per-page `u32 lut[]` for random seek). Position is `progress.bin` (6
bytes). First open of each chapter pays a one-time pagination cost ("Indexing"),
then it's cached; the next chapter is pre-built on the penultimate page. Cache
key includes font/viewport/orientation/CSS, so those changes invalidate it.

**Consequence:** our desktop text-v1 flattening is **mooted** — pagination
*cannot* be precomputed on desktop (it depends on device font/viewport/CSS), and
CrossPoint consumes raw EPUB, not our text format. **Serve raw DRM-free EPUB via
OPDS.**

**OPDS feed contract.** `OpdsParser` is a streaming, namespace-tolerant expat
parser for **OPDS 1.x Atom XML**. Per `<entry>` it reads `<title>` (required),
`<author><name>`, `<id>`; a **book** is a `<link
rel="…opds-spec.org/acquisition…" type="application/epub+zip" href="…">`
(prefers href containing `.epub`/`/epub/`); a **nav** entry is a `<link
type="application/atom+xml" href="…">`. Feed-level `rel="next"/"previous"`
(pagination) and `rel="search"` with `{searchTerms}` (OpenSearch) are optional.
**Cover art is not parsed.** Entry kept only if title AND href are non-empty.

**Download path:** `HttpDownloader` = `esp_http_client`, transport from URL
scheme — **plain http for LAN**, https verified against the CA bundle. Preemptive
HTTP Basic auth; streams to SD in 2 KB chunks; follows redirects. On-device
config via `OpdsServerStore` → `/.crosspoint/opds.json` (`name, url, username,
password`; ≤8 servers), set in the OPDS settings menu.

**KOReader progress sync:** standard koreader-sync-server API —
`GET /users/auth`, `GET /syncs/progress/{document}`, `PUT /syncs/progress`.
Headers: `x-auth-user`, `x-auth-key: MD5(password)`,
`Accept: application/vnd.koreader.v1+json`. PUT body `{document, progress,
percentage(0..1), device, device_id}`. `document` id is a partial-MD5 of file
*content* (computed device-side). **Our service can self-host this** as a
per-(user, document) key/value store. Caveat: the client base URL defaults to
`sync.koreader.rocks` and its configurability is unconfirmed — self-hosting may
need a one-line firmware change.

**Service work items (buildable now, no hardware):**

- [ ] Add an **OPDS Atom acquisition feed** (`GET /opds`) and serve raw EPUB at
      the acquisition href (`GET /book/{id}.epub`, `application/epub+zip`).
- [ ] **Drop text-v1 conversion** from the serving path; store/serve raw EPUBs.
      (Keep the converter module as the build-your-own fallback.)
- [x] Implement the **koreader-sync-server API** to self-host reading progress
      (`/users/create`, `/users/auth`, `GET`+`PUT /syncs/progress`). DECIDED:
      self-host (user runs Ubuntu + docker-compose + Komodo + Caddy). Auth is
      trust-on-first-use; progress persisted under `library/sync/` and doubles as
      an off-device backup of `progress.bin`. The device's Sync Server URL **is**
      user-settable (`KOReaderSettingsActivity`) and auto-prepends `http://` for
      bare LAN hosts — so **no firmware change** is needed.
- [x] Make the service **proxy-aware** for Caddy (uvicorn `--proxy-headers`), so
      OPDS absolute URLs use the external scheme behind the reverse proxy.
- [ ] *(Optional)* OpenSearch `{searchTerms}` + `next`/`prev` pagination for large
      libraries.
- [ ] `/time` is unused by CrossPoint (clock is out of scope upstream) — keep only
      if our own additions need it.

**Firmware config:** add our server in the OPDS settings UI → `opds.json`
(`url=http://<PC-IP>:8000/opds`, optional Basic creds). Plain HTTP avoids the
~55 KB TLS heap requirement.

**Refs:** `lib/OpdsParser/*`, `src/OpdsServerStore.*`,
`src/activities/browser/OpdsBookBrowserActivity.*`, `src/network/HttpDownloader.*`,
`lib/Epub/Epub/{Page,Section,BookMetadataCache}.*`, `src/util/BookCacheUtils.*`,
`src/activities/reader/EpubReaderActivity.*`, `lib/KOReaderSync/*`.

### 3.5 OTA updates from our repo

**Already there:** two paths. (a) **Network OTA** — `OtaUpdater` uses ESP-IDF
`esp_https_ota`, streaming the `.bin` from the asset URL (no SD staging); the
manifest is stream-parsed by `HttpDownloader`. (b) **SD-card OTA** —
`FirmwareFlasher::flashFromSdPath()` writes the next OTA partition directly and
`OtaBootSwitch` flips `otadata` (validates magic/segments/XOR/SHA256 trailer).

**Manifest = the standard GitHub Releases `/releases/latest` object.**
`ReleaseJsonParser` reads `tag_name` (→ version) and, from `assets[]`, the asset
named exactly **`firmware.bin`** → `browser_download_url` + `size`. Minimum JSON:

```json
{
  "tag_name": "1.4.0",
  "assets": [
    { "name": "firmware.bin", "browser_download_url": "https://…/firmware.bin", "size": 1572864 }
  ]
}
```

**URL repoint = one hardcoded constant** in `OtaUpdater.cpp`:

```cpp
constexpr char latestReleaseUrl[] =
  "https://api.github.com/repos/crosspoint-reader/crosspoint-reader/releases/latest";
```

**DECIDED: GitHub Releases** — point it at `…/repos/RR-T/esp-read/releases/latest`
(HTTPS; the bundled CA already covers GitHub). The LAN-service option
(`http://<PC-IP>:8000/ota/latest`) was considered and not chosen. Requires the
repo be public (or the device carry a token) for the API + asset to be reachable.

**Partitions:** dual OTA slots (`ota_0`/`ota_1`, 6.25 MB each) **already fit our
16 MB** — no change. `board = esp32-s3-devkitc-1` is a generic S3 target that
runs on the XIAO.

**Work items:**

- [ ] Change the `latestReleaseUrl` constant → our GitHub repo.
- [ ] Publish firmware to **GitHub Releases** with an asset named exactly
      `firmware.bin` and **numeric tags (`1.4.0`, no `v`)**. Add a release
      workflow (build S3 env → upload `firmware.bin`).
- [ ] Ensure `CROSSPOINT_VERSION` (`platformio.ini [crosspoint] version`) uses the
      same numeric scheme.
- [ ] Add/confirm an `s3` PlatformIO env for our board.
- [ ] **Bring-up first via SD:** build `firmware.bin` → copy to SD → Settings →
      SD firmware update. No network/manifest — fastest path to a flashed device.

**Footguns:** version compare is `sscanf("%d.%d.%d")` — **a leading `v` breaks
it**. Only integrity protection is the image's SHA256 trailer (no signature) —
fine on a trusted LAN, worth knowing. Skip the X4-specific
`esp_ota_set_boot_partition` bypass — a clean XIAO doesn't need it. No
rollback/anti-brick beyond manual SD recovery.

**Refs:** `src/network/{OtaUpdater,FirmwareFlasher,OtaBootSwitch,HttpDownloader}.*`,
`lib/JsonParser/ReleaseJsonParser.*`,
`src/activities/settings/{OtaUpdateActivity,SdFirmwareUpdateActivity}.*`,
`.github/workflows/release.yml`, `partitions.csv`.

### 3.6 Also required (beyond the four named)

A working device also needs the **input HAL** (buttons → `MappedInputManager`,
submodule `InputManager`) repinned to our 3 buttons, and the **FrontlightManager**
stubbed (we have no frontlight). Same "rewrite `lib/hal/*` wrapper + repin"
pattern.

---

## 4. What this does to `service/`

`service/` pivots from **EPUB→text converter** to **library server**:

- **Keep:** raw EPUB storage, metadata extraction (title/author for OPDS
  entries), the watcher, the Docker/LAN deployment.
- **Add:** OPDS Atom feed + raw-EPUB acquisition endpoint (+ later, KOReader sync,
  OTA host).
- **Shelve:** the text-v1 flattening (`converter.py`, `device_format.py`) — kept
  in-tree as the fallback for a build-your-own-firmware path, not wired into the
  OPDS server.

---

## 5. Sequencing

1. **Now, no hardware:** pivot `service/` to OPDS + raw-EPUB serving. *(This step
   is being implemented alongside this doc.)*
2. **On real silicon (benchmark, 2026-07 — partially done):** ran
   `firmware/epub-benchmark/` on the XIAO S3 (no panel/SD yet).
   - ✅ **PSRAM 8.0 MB detected**, ~7.9 MB free, ~7.0 MB min free after the render
     bench; internal SRAM min free ~229 KB. `qio_opi` confirmed correct.
   - ✅ **Page render ~11.5 ms** (paginate+rasterise one page) — negligible vs the
     e-ink refresh.
   - ✅ **Cold-open / pagination** (measured via an embedded sample, no SD):
     strip-tags 8 ms for 28 KB; **paginate ~1 ms/page** (20 pages in 19 ms) →
     a ~400-page book ≈ 0.4 s one-time, and CrossPoint caches it anyway.
     Min internal free after the run: **212 KB**; min PSRAM free 7.0 MB.
   - ✅ **On-device image decode** (JPEGDEC → Bayer-dither → 1-bit): 480×320 JPEG
     **82 ms**, 240×240 **32 ms**, with **near-zero heap growth** (block-based).
     → image handling stays on-device; the service-side image-optimizer is NOT
     needed (revisit only for pathological images).
   - Numbers use our proxy paginator (Adafruit GFX + JPEGDEC), not CrossPoint's
     heavier engine — treat as a comfortable floor, not exact.
   - Refresh timings from a no-panel run are bogus (BUSY floats) — ignore until
     the panel is wired.
   **Read:** the memory/render axis — the real worry behind on-device parsing —
   is cleared. CrossPoint already runs its engine on the X4's C3 with far less
   RAM, so 8 MB PSRAM is comfortably above baseline. Fork decision is supported by
   real silicon.
3. **Fork + port HAL:** display first (SD-flash the fork to see something on the
   panel), then input, then storage (Path 1), then the battery seam, then
   deep-sleep wake for 3 buttons. Apply the build-config tuning in
   `firmware-perf-tuning.md` (flash QIO, `-DCORE_DEBUG_LEVEL=0`, WiFi
   `setSleep(false)` + BSSID/channel fast-connect cache) — CrossPoint currently
   builds `flash_mode = dio`, which we switch to QIO.
4. **Finish partial-refresh** RED-RAM baseline in `Epd5in0`.
5. **Wire OTA:** SD path first, then repoint the URL.
6. **Calibration tool → SOC LUT →** drop into the battery seam.

---

## 6. Decisions

**Decided:**
- ✅ **Adopt CrossPoint as a fork.** Shelves the text-mode `service/`; we maintain
  a hardware port on a moving upstream. (`.txt` is read natively by CrossPoint —
  no plugin needed; a service-side `.txt` emitter is a trivial future add.)
- ✅ **OTA via GitHub Releases** (HTTPS). Numeric tags, asset `firmware.bin`.

- ✅ **Storage: Path 1** (shared SPI + SdFat), with a three-layer integrity
  scheme (SD CRC + cache CRC32 + end-to-end SHA-256) — see §3.2.

- ✅ **KOReader sync: self-host** in our service (built — §3.4). Device points at
  it via the user-settable Sync Server URL; no firmware change.

**Still open:**
- **Confirm the XTSD talks SPI** in our wiring (relevant to Path 1).
- **Final go/no-go** on the whole fork is gated on the on-device benchmark (§5).

---

## 7. Risks

- Fork maintenance against an actively-developed upstream.
- Partial-refresh RED-RAM baseline must be finished in our driver or FAST refresh
  ghosts.
- Shared-SPI coordination is net-new code CrossPoint doesn't have (Path 1).
- Battery: no averaging, no hysteresis, no cutoff upstream — all net-new.
- OTA on plain LAN HTTP has no authenticity beyond the image's SHA256 trailer.
- Hardware mismatch is the dominant risk overall — validated only by the
  on-device benchmark (step 2).

---

## 8. Source references

- CrossPoint: `github.com/iandchasse/crosspoint-reader-de-link` @ `s3-port` (MIT).
- HAL SDK submodule: `github.com/iandchasse/community-sdk-de-link` (`open-x4-sdk`).
- Our driver seed: `firmware/epub-benchmark/src/Epd5in0.{h,cpp}`.
- Our benchmark (decision gate): `firmware/epub-benchmark/`.
