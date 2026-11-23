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
- **Display:** Waveshare 5" e-paper with driver HAT, 960×552, ~220 PPI, **1-bit mono**, full refresh ~1.8s / partial ~0.7s. Runs on 3.3V (confirmed). SPI interface (9 lines: PWR, BUSY, RST, DC, CS, SCLK, DIN, GND, VCC). **HAT interface switch MUST be set to `4-line SPI`** (we use a dedicated DC pin; 3-line/9-bit SPI has no DC line and would misread every byte). **Controller confirmed: this is Waveshare's `EPD_5in0`, an SSD16xx/SSD1677-family controller** (init: 0x12/0x18/0x01/0x11/0x44-45/0x4E-4F/0x24-26/0x3C/0x22+0x20), **no custom LUT** (internal OTP waveform), also supports a 4-grey mode. Framebuffer = 1-bit packed, 120 B/row, 66,240 B, **bit 1 = white / 0 = black**. Official Waveshare **ESP32-S3 driver exists** (`e-Paper/E-paper_Separate_Program/5inch_e-Paper/ESP32-S3/EPD_5in0.*`) — use it for first bring-up. A faithful minimal port lives in `firmware/epub-benchmark/src/Epd5in0.*`.
- **Battery:** protected LiPo (≥500mAh), 3.7V JST-PH. Protected cell is mandatory (board has charge management but no load-side over-discharge protection).
- **Storage:** microSD (dev) or Adafruit XTSD soldered flash (production). Shares the SPI bus with the panel.
- **Inputs:** 3× 6mm slim tactile buttons (page fwd/wake, page back, menu). At least one on an RTC-capable GPIO for deep-sleep wake.
- **Power switch:** slide switch in the battery line as master cutoff (storage/crash recovery), NOT the daily off. **Part: SS12D01 vertical slide (8.5 × 3.5 × 3.6, L=2 knob), mounted on the case's top edge beside the USB-C port** — see `enclosure/MEASUREMENTS.md` §v7 additions.
- **Optional:** LIS3DH accelerometer (I²C) for orientation/tap/lift-to-wake — deferred.
- **Protoboard: plain double-sided 2.54 mm through-hole prototyping PCB (DECIDED 2026-07-28 — replaces the ProtoMate).** Cut to size from stock boards the owner has. **Every hole is an isolated plated pad — no strips, no buses, zero continuity**: every net is a wire or a deliberate solder bridge. Chosen for lower Z (cut-to-fit + optional XIAO cutout) and free placement. Consequence: the ProtoMate continuity model (`ABC`/`Dlo-hi`/`Elo-hi`/`FGH`/Column I) and its 7-jumper plan **no longer apply** — `hardware/` needs a re-layout. Upside: no castellation-vs-breakout problem, since nothing is pre-routed. **Board population is minimal by design (DECIDED 2026-07-28, see the NOTE below):** only genuinely shared nets (GND/3V3 rails, SCK/MOSI fan-outs) route through the board at all; every single-consumer signal — including all 3 flying-wire pads (VBAT, ADC_BAT, MENU) — solders directly to the XIAO, bypassing the board entirely. See `docs/bring-up-and-assembly.md` §Phase 5 for build technique.

### Mechanical / enclosure (confirmed dims)
- **MEASURED PART DIMENSIONS (2026-11-22) live in `enclosure/MEASUREMENTS.md` and replace the datasheet numbers below where they differ.** The important ones: glass **1.06 mm** thick (not 0.795), visible window **64 × 110**, battery **36 × 29.6 × 4.9** (5.3 at the wire end), XIAO **4.5 mm** tall. **Enclosure form changed to an Oasis-style grip spine** along one long edge, replacing the wedge described under "Enclosure direction" below. **The protoboard is dropped** (wire directly, or use a small cut board); the case provides wire channels. The case is modelled in SolidCraft via its MCP server.
- **Display glass outline 126.38 × 71.19 × 0.795 mm**; active area 110.59 × 62.65 mm (220 PPI). Separate **driver HAT board 30.5 × 65 mm** (plugs into the panel FPC). Inactive glass border ≈ 4 mm/side, wider on the FPC edge.
- **Footprint fit: confirmed everything hides under the panel.** Driver HAT (30.5×65) + logic board (cut to ~67×29 or smaller) + battery (35×30×5) ≈ 55% of the glass area; they tile in ~2 rows within 126×71 with margin. So a small bezel is feasible — the bezel floor is set by the **glass border + case wall + button placement + the FPC-edge HAT fold**, NOT by component packing (~6 mm on three edges, wider on the FPC edge). Buttons go on a **case edge** (a side edge in portrait), not under the glass.
- **Depth (Z) is the real constraint, ≈ 9.5–10.7 mm** (was ≈11 mm on the ProtoMate). **Solder the XIAO flat** — never on sockets/headers (+~8.5 mm). Three cases, tallest interior item:
  - XIAO on top of a 1.2 mm protoboard = **5.9 mm** → stack ≈ 1.5 front wall + 0.8 glass + 1 gap + 5.9 + 1.5 back wall ≈ **10.7 mm**.
  - **DECIDED: XIAO in-plane in an edge notch** (U-shaped bay cut into the board edge, ≈18 × 21.5 mm / 7 × 8.5 holes, USB-C facing out of the case; enclosure boss carries the XIAO, wires are electrical not structural) = **4.7 mm** → then the **battery (5.0 mm) becomes the tallest item** → stack ≈ **9.8 mm**. The notch saves exactly the protoboard's thickness; its real value is that the electronics stop being the Z constraint. Board cut size **26 × 17 holes ≈ 66 × 43 mm** (hole budget ~91 pads +50% slack; the portrait envelope has ~22 mm vertical slack, so the old 67×29 was conservative packing; 66 mm keeps ~2.6 mm clearance per side under the 71.19 mm glass).
  - Floor is therefore the battery, not the electronics: ≈ **9.5 mm** with thinner walls. Further Z only comes from a thinner cell.
  Also: **back-side wiring adds height** — use 30 AWG Kynar laid flat (~0.3 mm) and **trim every lead flush**, or the ~1 mm of wire loom eats the saving. Fold the FPC/HAT flat behind; keep the battery clear of the antenna foil.
- **Enclosure direction (SUPERSEDED 2026-11-22):** the early "option B" wedge-back concept (and its `option-b-layout.png` / `curved-back-concept.png`, now deleted) is replaced by the Oasis-style grip-spine case. FPC exits the BOTTOM edge (confirmed 2026-07-28), so the HAT sits near the bottom and the XIAO/USB-C at the top. **Current design: `enclosure/ereader-case.sc` (v7), documented in `enclosure/MEASUREMENTS.md`.**
- **2D drawings (OUTDATED — v1/v2-era layout):** `enclosure/drawings/layout_generator.py` renders three PNGs into `enclosure/drawings/` from one `PARTS` dict (SVG → `rsvg-convert`; `brew install librsvg`). Change a dimension there and re-run rather than hand-editing images. Needs updating to v7 before it is trusted again; CAD renders of the current model are in `enclosure/renders/`. **TODO: fix the protoboard's final cut size + mounting-hole positions (the stock corner M2.5 holes are lost when the board is cut down — plan new ones, or bond to bosses).**

## Pin assignment (validated against board schematic)

All D0–D10 are ADC1 (WiFi-safe). D2/GPIO3 is a strapping pin, now used for the **E-paper PWR enable** (verify boot behaviour). D11/D12 (GPIO42/41) have no ADC.

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
| **E-paper PWR (enable)** | D2 | GPIO3 | **drive HIGH to power the panel, LOW to cut it — MUST be a controlled GPIO, not tied to 3V3** (see Panel protection). The vendor `EPD_5in0` driver does exactly this. Strapping pin, verify boot; an optional 100kΩ pulldown keeps the panel off until firmware drives PWR |
| VBUS sense (charge detect) | castellation | spare | **digital-presence input** on a spare Plus castellation (moved off D2 to free it for PWR). Only USB-present is needed — "full" = battery holding ~4.2V — so no ADC pin required, which also dodges the ADC2-while-WiFi limit |
| Button: page fwd/wake | D4 | GPIO5 | RTC wake |
| Button: page back | D5 | GPIO6 | RTC |
| Button: menu/select | D11 | GPIO42 | RTC castellation — **hand-wire (see note)**. **⚠ UNRESOLVED (2026-11-22): Seeed's official XIAO ESP32-S3 Plus pinout shows D11 = GPIO38 and D15 = GPIO42, and the ESP32-S3's RTC (deep-sleep wake) GPIOs are only GPIO0–21. So GPIO42 can't wake the device. The pinout marks D17/D18/D19 (GPIO13/12/11) as RTC: move menu there if it needs to wake, and use one of them for the optional cover hall sensor.** |

> NOTE (RESOLVED): VBUS sense and E-paper RST were both tentatively on GPIO4 — fixed by moving VBUS sense off D3. E-paper RST now has D3/GPIO4 to itself.
> **UPDATE (panel protection):** D2/GPIO3 is now the **E-paper PWR enable** — the panel's PWR line must be GPIO-controlled, not tied to 3V3 (see Panel protection). VBUS sense therefore moves off D2 to a **spare Plus castellation as a digital-presence input** (it only needs USB-present, so it needs no ADC pin — also sidesteps the ADC2-while-WiFi limit). The layout generators (`hardware/*_build_sheet_generator.py`) + `hardware/README.md` need regenerating for PWR→D2 and VBUS→castellation.
> NOTE (castellations): on the plain protoboard nothing is pre-routed, so the old ProtoMate "only D0–D10 are broken out" limitation is gone — every pin is equally reachable. **D11/GPIO42 (menu) and ADC_BAT are wires soldered directly to the XIAO's SMD edge castellations**, attached BEFORE the XIAO is seated flat (unreachable afterwards). **VBAT (BAT+) is different again — it's on the XIAO's UNDERSIDE, not an edge castellation**, so it's not merely hard to reach afterward, it's impossible; wire and route it clear before the module goes anywhere near the notch.
> NOTE (board population, DECIDED 2026-07-28): this is a compact build, so the protoboard only hosts **genuinely shared nets** — GND rail, 3V3 rail, and the SCK/MOSI fan-outs (shared between the display and SD). Every single-consumer signal (E-paper CS/DC/RST/BUSY, SD MISO/CS, all 3 button signal legs, MENU, and both battery/VBUS dividers) solders **directly to the XIAO's own pad**, never touching a board hole. Consequence: only **4 of the 14 header pins** get a real stub leg into the board (GND/3V3/D8/D10); the board footprint drops from 14 stub legs + 3 castellation holes + 19 module leads to 4 stub legs + 0 castellation holes + 12 module leads. Both dividers (R-VBUS-T/B, R-BAT) are now built **off-board**, inline near the XIAO — R-VBUS-B's GND leg is the only part of either divider that still reaches the board. See `hardware/protoboard_build_sheet_generator.py`'s `XIAO_DIRECT` / `OFFBOARD_PARTS` lists and Sheet 3 of the build PDF ("Direct-to-XIAO leads").

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
wake on button → read battery at rest (before refresh/WiFi) → render/fetch page → push to panel → refresh (partial; full every N pages to clear ghosting) → **sleep the panel (`0x10`) the instant BUSY clears** → save reading position → **cut panel PWR (≥2s after the sleep command)** → deep sleep.

> **Panel protection (CRITICAL — irreparable if ignored).** Waveshare: *"prolonged exposure to high voltage can damage the film … set it to sleep mode or power it off."* The constraint is a **maximum**, not a minimum: there is no required delay between refresh and sleep (the refresh already waits on BUSY), and the danger is leaving the HV source drivers **energised while idle**. Rules:
> 1. **Sleep the panel (`0x10`) the moment a refresh completes.** Do SD writes / WiFi / pagination with the panel **asleep** — never between refresh and sleep, never idle with the rails up.
> 2. The image is **bistable** — it persists with power off, so there is never a reason to keep it energised.
> 3. To fully power down, cut **PWR (D2/GPIO3)** — but **wait ≥2s after the `0x10` command** so the HV rails discharge first (yanking power early is itself stressful). Sequence: `refresh → sleep(0x10) → [any other I/O] → ≥2s after sleep → PWR low → deep sleep`.
> 4. **On long idle / low-battery / storage shutdown, clear the panel to WHITE first** (Waveshare: *"store it with a white image displayed"*). Because the image is bistable it persists indefinitely with power off, so leave white — not a stale page. Shutdown sequence: `clearWhite → sleep(0x10) → ≥2s → PWR low`.
>
> Vendor reference: `EPD_5in0` `Sleep()` (`0x10`/`0x01`, 100ms) then `DEV_Module_Exit()` (PWR low), with the demo's *"important, at least 2s"* between them. Our `firmware/epub-benchmark` mirrors this at the end of `setup()` (incl. the clear-to-white). *(Waveshare also advises a ≥180s full-refresh interval + a refresh once/24h; we accept the faster UI-driven cadence and rely on rule 4 for long idle — not treating 180s as a hard limit.)*

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
