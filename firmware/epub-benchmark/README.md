# On-device EPUB feasibility benchmark

A throwaway PlatformIO sketch to flash on the **XIAO ESP32-S3 Plus** the day it
arrives. It answers the open question behind the [CrossPoint adoption
decision](../../ereader-build-guide.md): *can the device parse/paginate/render
EPUBs comfortably, and what do refresh/page-turn costs do to the
deep-sleep-per-page power model?*

> This is a C/C++ tool, not MicroPython like the other bring-up tools — on
> purpose, because it measures the C++ EPUB/render path and the display port,
> which is exactly what we need real numbers on.

## What it measures

1. **Board & memory** — flash, PSRAM size, heap, largest free block.
2. **PSRAM** — 1 MB alloc + memset bandwidth vs internal RAM (PSRAM is slower; matters for parse buffers).
3. **E-ink timing** — panel init, full refresh (~1.8s expected), partial (~0.7s).
4. **1-bit text render** — paginate + rasterise a page with a real font.
5. **EPUB-style workload** — read a chapter off SD, strip tags, paginate the whole thing, render page 1, with heap watermarks.

It degrades gracefully: no panel → still reports memory/PSRAM/render; no SD →
skips step 5.

## Hardware / wiring

Pins follow `CLAUDE.md` (SCK=GPIO7, MOSI=GPIO9, MISO=GPIO8, EPD CS/DC/RST/BUSY =
GPIO1/2/4/43, SD CS=GPIO44). Panel + SD share the SPI bus; both CS are driven
high before any traffic and the SD is initialised first.

## SD prep (for step 5)

Put one chapter of a **DRM-free** book on a FAT32 microSD as **`/sample.xhtml`**
(or `/sample.txt`). Easiest source: the text-mode output of the desktop
conversion service, or any single XHTML file unzipped from an EPUB.

## Run

```bash
cd firmware/epub-benchmark
pio run -t upload && pio device monitor -b 115200
```

If PSRAM reports 0 bytes, flip `board_build.arduino.memory_type` between
`qio_opi` and `qio_qspi` in `platformio.ini` (XIAO S3 variants differ).

## Reading the results

- **full ~1.8s / partial ~0.7s** refresh is normal for this panel — these
  dominate page-turn latency and per-wake energy.
- **page render** should be well under a few hundred ms.
- **pagination time × page count** ≈ the cold-open cost. If it's large, the
  firmware must **cache pagination to flash** so each deep-sleep wake is just
  *load position → render one page → sleep* (the crux for months of battery).
- Watch **min internal free** — on an 8 MB-PSRAM S3, fragmentation of internal
  RAM, not total memory, is the usual ceiling.

## Note on the display driver

`Epd5in0.{h,cpp}` is a faithful, minimal port of Waveshare's `EPD_5in0` init
(SSD16xx/SSD1677-family, internal OTP waveform — no custom LUT). It's written to
be lifted straight into CrossPoint's `EInkDisplay` as the port seed. The partial
path here is approximate (enough to time the ~0.7s update); a production partial
refresh also seeds the `0x26` "previous" RAM bank and tweaks the border. If the
image renders vertically mirrored, flip the `0x11` data-entry mode / `0x45` Y
window — Waveshare's values are mirrored here verbatim.
