# CLAUDE.md — DIY E-Ink E-Reader

Standing context for Claude Code sessions in this project. A DIY e-ink e-reader built around an ESP32-S3, with a desktop content-conversion microservice. See `ereader-build-guide.md` in this repo for the full design rationale; this file is the quick-reference summary.

## Project overview

A low-power e-ink e-reader:
- **Device:** Seeed XIAO ESP32-S3 Plus driving a Waveshare 5" e-paper panel, battery-powered, deep-sleep architecture, instant wake on button. Target: weeks-to-months per charge.
- **Content pipeline:** a desktop (Ubuntu/Docker) Python microservice that converts DRM-free EPUBs into a simple on-device format and serves them to the reader over LAN WiFi.

Codebases live here:
1. `firmware/` — the ESP32 reader (C/C++, production) + MicroPython tools (bring-up/calibration). Also `firmware/epub-benchmark/` — a C++ PlatformIO sketch to gauge on-device EPUB feasibility + seed the display-driver port.
2. `service/` — the desktop conversion microservice (Python/FastAPI/Docker).
3. `simulator/` — a pixel-perfect tkinter mock of the 960×552 1-bit panel + a sample reader UX, for building the UI without hardware. Its `MonoFrameBuffer` packs to the panel's exact byte format.

## Hard boundaries (do not cross)

- **No DRM circumvention.** The DRM unlock for purchased books happens upstream in established desktop tools (e.g. Calibre + plugins), entirely outside this project. The microservice's input is an **already-DRM-free EPUB**. Never implement, design, or assist with decryption of DRM-protected content, on-device or on the desktop.
- The device only ever handles **DRM-free files**. It does not log into Amazon/B&N or fetch from any store.

## Hardware (locked)

- **MCU:** Seeed XIAO ESP32-S3 Plus — dual-core LX7 @240MHz, 512KB SRAM, 8MB PSRAM, 16MB flash, 20 usable GPIO (11 through-hole + 9 SMD castellations), onboard LiPo charging (110mA, 4.2V cutoff), 14μA deep sleep. **U.FL antenna variant — external 2.4GHz antenna required (no onboard trace).**
- **Display:** Waveshare 5" e-paper with driver HAT, 960×552, ~220 PPI, **1-bit mono**, full refresh ~1.8s / partial ~0.7s. Runs on 3.3V (confirmed). SPI interface (9 lines: PWR, BUSY, RST, DC, CS, SCLK, DIN, GND, VCC). **Controller confirmed: this is Waveshare's `EPD_5in0`, an SSD16xx/SSD1677-family controller** (init: 0x12/0x18/0x01/0x11/0x44-45/0x4E-4F/0x24-26/0x3C/0x22+0x20), **no custom LUT** (internal OTP waveform), also supports a 4-grey mode. Framebuffer = 1-bit packed, 120 B/row, 66,240 B, **bit 1 = white / 0 = black**. Official Waveshare **ESP32-S3 driver exists** (`e-Paper/E-paper_Separate_Program/5inch_e-Paper/ESP32-S3/EPD_5in0.*`) — use it for first bring-up. A faithful minimal port lives in `firmware/epub-benchmark/src/Epd5in0.*`.
- **Battery:** protected LiPo (≥500mAh), 3.7V JST-PH. Protected cell is mandatory (board has charge management but no load-side over-discharge protection).
- **Storage:** microSD (dev) or Adafruit XTSD soldered flash (production). Shares the SPI bus with the panel.
- **Inputs:** 3× 6mm slim tactile buttons (page fwd/wake, page back, menu). At least one on an RTC-capable GPIO for deep-sleep wake.
- **Power switch:** slide switch in the battery line as master cutoff (storage/crash recovery), NOT the daily off.
- **Optional:** LIS3DH accelerometer (I²C) for orientation/tap/lift-to-wake — deferred.
- **Protoboard:** ProtoMate for XIAO, **67 × 29 mm**, hosts the XIAO flat (14× through-hole headers, M2.5 mounting holes). No castellation traces (see pin notes).

### Mechanical / enclosure (confirmed dims)
- **Display glass outline 126.38 × 71.19 × 0.795 mm**; active area 110.59 × 62.65 mm (220 PPI). Separate **driver HAT board 30.5 × 65 mm** (plugs into the panel FPC). Inactive glass border ≈ 4 mm/side, wider on the FPC edge.
- **Footprint fit: confirmed everything hides under the panel.** Driver HAT (30.5×65) + Protomate (67×29) + battery (35×30×5) ≈ 55% of the glass area; they tile in ~2 rows within 126×71 with margin. So a small bezel is feasible — the bezel floor is set by the **glass border + case wall + button placement + the FPC-edge HAT fold**, NOT by component packing (~6 mm on three edges, wider on the FPC edge). Buttons go on a **case edge** (a side edge in portrait), not under the glass.
- **Depth (Z) is the real constraint, ≈ 11 mm.** Tallest item = ProtoMate PCB (1.6) + **XIAO 4.7 mm incl USB-C** = 6.3 mm (battery is 5.0, side-by-side so doesn't add). Stack = front wall 1.5 + glass 0.8 + gap ~1 + 6.3 + back wall 1.5 ≈ **11 mm**. **Solder the XIAO flat** (the Protomate's 7-pin sockets would add ~8.5 mm), fold the FPC/HAT flat behind, keep the battery clear of the antenna foil.
- **Enclosure direction (portrait, decided — "option B").** **Wedge back**: thick across the lower two-thirds (~10 mm, over the battery + XIAO/USB-C stack) tapering to a thin top edge (~5 mm). Exterior wedge, interior keeps flat mounting bosses. Layout (portrait 71×126): **Driver HAT at top, battery centred** (heaviest → left-right balance), **ProtoMate+XIAO at the bottom edge with USB-C out the bottom** (no USB-C extension needed). These three **tile coplanar in portrait — no Z-stacking** (the earlier 127>126 clash only applied to a rotated central-spine arrangement, now dropped). Buttons on a **side (long) edge** in the grip zone; D11 menu still hand-wired to the XIAO castellation. See `enclosure/option-b-layout.png` (plan + section); `enclosure/curved-back-concept.png` for the curve concept. **Open: confirm the FPC exit edge** — assumed TOP (feeds the HAT); if it exits the bottom, swap the HAT and the XIAO/USB-C ends.
- See `enclosure/component-layout.png` for the to-scale top-down + Z-stack drawing. **TODO: confirm which panel edge the FPC exits (dictates widest bezel); grab the Protomate STEP file for exact outline.**

## Pin assignment (validated against board schematic)

All D0–D10 are ADC1 (WiFi-safe). D2/GPIO3 is a strapping pin (unused). D11/D12 (GPIO42/41) have no ADC.

| Function | Label | GPIO | Notes |
|----------|-------|------|-------|
| SPI SCK (shared) | D8 | GPIO7 | |
| SPI MOSI/DIN (shared) | D10 | GPIO9 | |
| SPI MISO (SD) | D9 | GPIO8 | |
| E-paper CS | D0 | GPIO1 | |
| E-paper DC | D1 | GPIO2 | |
| E-paper RST | D3 | GPIO4 | off strapping pin |
| E-paper BUSY (in) | D6 | GPIO43 | UART TX pad; OK (USB debug) |
| SD CS | D7 | GPIO44 | UART RX pad; OK |
| Battery divider (ADC) | pin 20 | GPIO10 | `ADC_BAT`. Board R10 220kΩ = lower leg; add upper 220kΩ from VBAT |
| VBUS sense (charge detect) | D3* | GPIO4 | divided-down VBUS — note: shares with RST, re-check; move to a spare if needed |
| Button: page fwd/wake | D4 | GPIO5 | RTC wake |
| Button: page back | D5 | GPIO6 | RTC |
| Button: menu/select | D11 | GPIO42 | RTC castellation — **hand-wire (see note)** |

> NOTE: VBUS sense and E-paper RST are both tentatively on GPIO4 — resolve this conflict during wiring (move VBUS sense to a spare castellation GPIO). Flag if working on wiring/firmware that touches either.
> NOTE (Protomate): the ProtoMate for XIAO breaks out only the **11 through-hole pins (D0–D10 + power)** — it has **no traces for the 9 SMD castellation pads**. Of the current pin map, only **D11/GPIO42 (menu button)** lives on a castellation, so it must be **hand-soldered with a wire directly to the XIAO's castellation pad** (and a 2nd wire if VBUS sense moves to a spare castellation). Solder castellation wires **before** seating the XIAO on the Protomate (or keep them edge-accessible) — they're hard to reach once mounted. Everything else lands on the Protomate headers.

## Firmware approach

- **Production firmware: C/C++ (Arduino framework + PlatformIO).** Chosen because deep-sleep current, wake timing, and memory-careful page rendering are where C/C++ wins.
- **Reference `libros`** (github.com/joeycastillo/libros) for framework *structure* (book listing, text layout, page navigation) — do NOT copy wholesale; write clean code. It targets ESP32-S3 in C/C++.
- **Build-vs-reuse — CrossPoint Reader (UNDECIDED).** `github.com/iandchasse/crosspoint-reader-de-link` branch `s3-port` is mature MIT-licensed e-reader firmware (Xteink X4, ESP32-C3→S3) that already does C++/PlatformIO, deep-sleep wake, 1-bit packed framebuffer (byte-identical to ours), partial/full refresh, and an **SSD1677 display driver = our panel's controller family** (so porting its `EInkDisplay` to our panel is low effort — swap dims to 960×552 + paste `EPD_5in0` init). **The catch:** it parses EPUB **on-device**, which would largely moot the `service/` desktop-conversion architecture. Open question gating the decision: does it cache pagination so each deep-sleep wake is just load-position→render-one-page, or re-parse per wake? Measure with the benchmark below before committing. If we build our own instead, CrossPoint is still the best reference (lift its EInkDisplay, GfxRenderer, deep-sleep HAL).
- **On-device EPUB feasibility benchmark:** `firmware/epub-benchmark/` — a flash-and-read PlatformIO sketch (probes PSRAM, times panel refresh, parse→paginate→render with heap watermarks). Run it when the board arrives; it also contains the minimal `EPD_5in0` driver port.
- **CrossPoint extension paths (if adopted) — clean seams, reviewed:** (a) **OTA via our service** — `OtaUpdater` uses one constant URL + JSON manifest + `esp_https_ota`; repoint = change URL + serve a matching manifest/`.bin` (caveat: HTTPS expected, LAN HTTP needs an embedded cert or signature check). (b) **Auto-sync** — CrossPoint already speaks OPDS/WebDAV/Calibre + KOReader progress sync, so expose our service as an **OPDS feed** → near-zero firmware change; keep sync to explicit wake/connect (SCOPE.md rejects background WiFi). (c) **UI** — clean `BaseTheme` system; restyle = subclass it, prototype in `simulator/` first.
- **DEFERRED TODO (gated on the feasibility test):** sketch two `service/` FastAPI endpoints — an **OPDS acquisition feed** (wrap `/library`) and an **OTA manifest + `.bin`** endpoint. End state if CrossPoint is adopted: one microservice = OPDS library + OTA + NTP (the `service/` role pivots from EPUB *converter* → *library server*, since CrossPoint parses on-device).
- **Calibration & test tools: MicroPython** — run-once, iterate-fast, over USB. Hardware bring-up, ADC checks, battery characterisation. (Exception: the EPUB benchmark above is C++, because it measures the C++ engine + display port.)
- **ADC portability:** MicroPython tools must log **calibrated voltages, not raw ADC counts** (the two stacks differ in ADC attenuation/calibration) so the discharge curve transfers to C firmware.

### Core reading loop (deep-sleep state machine)
wake on button → read battery at rest (before refresh/WiFi) → render/fetch page → push to panel → refresh (partial; full every N pages to clear ghosting) → save reading position → deep sleep.

### Shared SPI bus rules (critical — most "one device works not both" bugs)
- Both CS pins set as outputs, driven HIGH (deselected) at startup before init.
- **Initialise the SD card FIRST**, before the panel.
- Bus clock at the SD's tolerated speed (library default).
- Never start an SD transfer mid-refresh — wait for BUSY to clear (natural in the sequential loop).

## Power & battery

- Deep sleep ~14μA is the everyday "off". Reading ~5mAh/hr (e-paper refresh + boost rails dominate, not CPU). 500mAh cell → ~weeks-to-months light use.
- **Battery sensing:** voltage divider on GPIO10 → average 50–100 ADC samples → `esp_adc_cal` eFuse calibration → map through a **custom discharge curve** (built by the MicroPython calibration tool from the actual cell). Display SOC in 10% increments with hysteresis. Low-voltage cutoff ~3.4–3.5V → save state + deep sleep.
- **Charging UI:** charger status pin is NOT broken out (drives onboard LED only). Detect charging via **VBUS presence**; detect "full" when voltage holds ~4.2V. While charging, voltage reads high (CV phase) → show "Charging…" not a precise %, show accurate % only on battery at rest.
- **Don't overclock past 240MHz rated spec** (a crash that fails to sleep wrecks battery life). 240MHz "race to sleep" only helps in text-render mode; irrelevant in bitmap mode.

## Timekeeping

ESP32 has no battery-backed RTC. Set clock via **NTP during WiFi sync**. Store last-sync time in RTC memory. **Display the clock only if synced within the last ~24h** (never show a stale time). Optional DS3231 RTC if precise always-on time is ever needed.

## Content pipeline (`service/`)

**Input:** DRM-free EPUB. **Output:** simple device format, served over LAN.

- **Stack:** Python 3.12-slim, FastAPI + uvicorn, ebooklib, lxml, beautifulsoup4, Pillow, watchdog. Dockerised; bind-mount `./library` (incoming + converted cache); publish port 8000.
- **Flow:** watch `library/incoming` → parse EPUB (spine + metadata) → flatten (strip CSS/scripts, keep paragraphs/headings/chapter breaks) → convert to device format → cache in `library/converted/{book_id}/` (book_id = source hash) → serve.
- **API:** `GET /library` (JSON index), `GET /book/{id}`, `GET /book/{id}/page/{n}` (bitmap mode), `GET /time` (NTP-on-sync).
- **ESP fetches over LAN during WiFi sync; find PC IP via `ip addr` (mDNS later).**

### Device format: text vs bitmap
- **Text mode:** ~0.5–1MB/book; ESP does layout + font rendering; allows on-device font resize; reading position = char offset. Higher on-device work/power.
- **Bitmap mode:** ~26MB/book (pre-rendered 1-bit pages @960×552); ESP just blits; near-zero CPU; fixed font; clean "page N of M"; lowest power, fastest, simplest firmware.
- **Plan:** **text mode for development** (fast iterate, change fonts), **bitmap or multi-size hybrid for production**. Match bitmap packing to the panel's exact 1-bit 960×552 framebuffer format (no on-device repacking).

## Suggested build order

1. `service/` conversion microservice in **text mode** — can be built NOW (no hardware needed). Test against existing DRM-free EPUBs.
2. (When parts arrive) MicroPython hardware bring-up: panel render, shared-SPI test, button wake-from-sleep, battery/VBUS divider reads.
3. MicroPython battery characterisation tool → discharge curve.
4. C/C++ production firmware: deep-sleep loop, shared-SPI init, page render/refresh, battery UI, WiFi sync, NTP.
5. Bitmap-mode pipeline + firmware (production optimisation).
6. Enclosure (3D-printed, PETG): captive top-hat button plungers (~0.3–0.4mm clearance), antenna clear of battery foil.

## Conventions

- Confirm hardware specifics against `ereader-build-guide.md` and the board schematic before writing wiring-dependent code.
- Flag any of the open hardware questions if touched: VBUS/RST pin conflict; R10 value confirmation; that the panel VCC runs at 3.3V (the 5V pin is dead on battery — all peripherals from VCC_3V3).
- Keep the device firmware as simple as possible; push heavy work (parsing, pagination, rendering) to the desktop service.
