# DIY E-Ink E-Reader — Build Guide & TODO

An ESP32-S3 based e-reader with a 5" e-paper display, designed for instant wake, weeks-to-months of battery life, and safe LiPo handling.

---

## 1. Hardware

### Core parts list

| # | Part | Source | Approx. price | Notes |
|---|------|--------|--------------|-------|
| 1 | **Seeed XIAO ESP32-S3 Plus** | The Pi Hut | ~£10 | Chosen over the standard XIAO for more I/O and flash. 8MB PSRAM, 16MB flash, 14μA deep sleep, built-in LiPo charging. **20 usable GPIO** (11 through-hole + 9 SMD castellations). The 9 extra are edge pads you solder wires to — no headers — so plan for that. ⚠️ **The variant purchased has a U.FL antenna port and NO onboard trace — an external antenna is required (see item 9).** |
| 2 | Waveshare 5" e-Paper **with driver HAT** (960×552) | Waveshare | $34.99 (~£28) | ~220 PPI, 1.8s full / 0.7s partial refresh, 1-bit mono. Buy the **HAT version**, not the raw panel — the HAT provides the FPC connector, ±15–22V boost rails, and level shifting. |
| 3 | Protected LiPo cell, 3.7V, JST-PH | The Pi Hut | ~£8–10 | **Must say "with protection circuit / PCM / PCB"** — hardware over-discharge/over-charge/short safety net. Verify JST polarity matches the XIAO. Originally targeting 2000mAh; **500mAh also fine** (~weeks-to-months per charge given the deep-sleep budget — see §5). Larger = more margin if real draw exceeds estimate. |
| 4 | Tactile push buttons (6mm slim, 20-pack) | The Pi Hut | £4.80 | Page turn + wake. At least one on an RTC-capable GPIO for deep-sleep wake. 20-pack gives spares for tuning the printed plunger fit. |
| 5 | Divider resistor(s): 220kΩ | any | <£1 | **Confirmed from schematic: the board has NO onboard battery divider** — you must add your own (raw VBAT 4.2V would exceed the ADC range). Use the **GPIO10 `ADC_BAT`** pin. The board already has **R10 (220kΩ) from that node to GND** — this can serve as the divider's **lower leg**, so you may only need to add the **upper 220kΩ** (VBAT → GPIO10) for a ÷2 divider. Verify R10 in situ before relying on it. Any 1/4W; 1% preferred. |
| 6 | Storage (optional) — see decision below | The Pi Hut | £3–12 | **Two options:** (a) removable **microSD module** (~£3–5 + card) — pop out to load books from a computer, ideal during development; or (b) **Adafruit XTSD soldered SPI flash/SD** (2GB £10.60) — soldered-down, wear-levelling + ECC built in, rugged for a portable device, but **no removable card so all books must arrive via WiFi/USB sync.** Both use the shared SPI bus + their own CS. |
| 7 | Power resistor for calibration (see §4) | any | ~£1 | One-time use. E.g. a 47–100Ω, 1–2W resistor sized for a sensible discharge current. |
| 8 | Protoboard + jumper wires | The Pi Hut | ~£3–5 | To wire the HAT lines + buttons + divider. |
| 9 | **2.4GHz U.FL/IPEX antenna (flexible flat type)** | The Pi Hut / Seeed / Adafruit | ~£2–5 | **Required** — the board variant has no onboard trace. Get a flexible flat adhesive antenna (standard U.FL / "MHF1"), 2.4GHz (or dual-band). Adhere to the case wall, clear of the battery. **Never run WiFi with no antenna attached.** |
| 10 | Slide switch (master power cutoff) | The Pi Hut / any | ~£1 | Optional but recommended. In the battery line as a true-zero-off cutoff for storage / crash recovery (see §5). Any small slide switch — current draw is tiny. |
| 11 | Accelerometer — LIS3DH (optional) | Adafruit / any | ~£4–5 | I²C, ~2μA in low-power mode, built-in tap + motion-wake interrupt. For orientation/auto-rotate, tap-to-turn, or lift-to-wake. Shares the I²C bus; +1 GPIO for its interrupt line. See §7. |

**Rough total: ~£55–70** plus Waveshare shipping/import to Jersey. Battery size, storage choice, and optional accelerometer shift this.

### Key decisions already locked in

- **Board: ESP32-S3** over Pico (more RAM, native WiFi) and Pi Zero (idle power, boot time, SD-corruption risk).
- **Display: Waveshare 5" with HAT** for the best size-vs-sharpness balance (~220 PPI). Higher-PPI panels exist (6"/7.8" HD at ~300 PPI) but require parallel/IT8951 interfaces and push you back toward a Pi Zero build.
- **Power: protected cell + XIAO's onboard charger + firmware low-voltage cutoff.** Rejected the PowerBoost 1000C (boost-converter quiescent draw wrecks deep-sleep battery life) and the bare TP4056 charger (redundant with the XIAO).
- **Battery sensing: resistor divider + custom discharge curve** (not a MAX17048 fuel gauge) — sufficient for 5–10% display increments once calibrated against your own cell.

### GPIO pin budget (XIAO ESP32-S3 Plus — 20 usable GPIO)

| Function | Pins | Notes |
|----------|------|-------|
| E-paper: SCLK, DIN (MOSI), CS, DC, RST, BUSY | 6 | Core SPI + control lines |
| E-paper PWR | 0–1 | Can hardwire to 3.3V to save a pin, or gate via GPIO |
| Storage (SD/XTSD): MISO + own CS | 2 | Shares SCLK/MOSI with the panel; only MISO + CS are new |
| Battery divider | 1 | Must be an **ADC-capable** pin |
| Buttons ×3 | 3 | At least one **RTC-capable** for deep-sleep wake |
| **Total** | **~12–13** | Comfortable against 20 usable; room for an LED or 4th button |

**Wiring caveats (ESP32-S3 specific — verify against the board pinout before soldering):**

- **A11 / A12 (GPIO41 / GPIO42) are NOT ADC-capable** despite being analog-labelled. Use one of the other ADC pins for the battery divider.
- **Strapping pins GPIO0, GPIO3, GPIO45, GPIO46** are pulled at boot — keep buttons and CS lines off these to avoid boot/programming issues. Use pins the board docs mark "safe for general GPIO."
- **Shared SPI bus**: panel + storage share SCLK/MOSI/MISO; each device needs only its own CS. This is why storage costs just 2 extra pins.
- The 9 extra GPIO on the Plus are **SMD castellations** — solder wires directly to the edge pads (no header option).

---

## 2. Build Guide

### Step 1 — Bench test the board
- [ ] Flash a blinky / serial "hello" to the XIAO ESP32-S3 over USB-C; confirm toolchain (Arduino or ESP-IDF / PlatformIO) works.
- [ ] Confirm you can read the ADC and enter/exit deep sleep with a GPIO wake source.

### Step 2 — Wire the e-paper HAT
- [ ] Connect the 9 SPI lines from the HAT to the XIAO: PWR, BUSY, RST, DC, CS, SCLK (CLK), DIN (MOSI), GND, VCC (3.3V).
- [ ] Pull Waveshare's ESP32 example code for this exact panel and confirm a test image renders.
- [ ] Verify both full refresh (~1.8s) and partial refresh (~0.7s) work.

### Step 3 — Buttons
- [ ] Wire 2–3 tactile buttons to GPIOs, at least one RTC-capable (for deep-sleep wake).
- [ ] Decap with a small capacitor or debounce in firmware.
- [ ] Confirm a button press wakes the board from deep sleep.

### Step 4 — Battery + charging
- [ ] Connect the **protected** LiPo to the XIAO's battery pads (check polarity!).
- [ ] Confirm charging works over USB-C and that the board runs from battery alone.
- [ ] **Do not** add the PowerBoost or external charger — the onboard charger plus protected cell is the right combination.

### Step 5 — Battery sensing divider
- [ ] Solder the two ~220kΩ resistors as a divider from BAT+ to GND, tap to an ADC-capable GPIO (halves battery voltage into the 0–3.3V ADC range).
- [ ] In firmware: average 50–100 ADC samples, use `esp_adc_cal` eFuse calibration, double the result.
- [ ] One-point calibrate: compare against a multimeter reading and apply a correction factor.

### Step 5b — Storage
- [ ] Decide: removable microSD module (dev-friendly, can load books from a computer) vs Adafruit XTSD soldered flash/SD (rugged, sync-only). A sensible path is **develop with removable microSD, switch to XTSD for the final build** if you want ruggedness.
- [ ] Wire on the shared SPI bus: MISO/MOSI/SCLK shared with the panel, plus a dedicated CS GPIO (off the strapping pins).
- [ ] Confirm read/write with the standard SD library; format FAT if needed (XTSD ships pre-formatted).
- [ ] If using XTSD: confirm your WiFi (or USB) sync path works *before* committing, since it's the only way to get books on.

**Shared SPI bus — confirmed fine, but follow these rules (cause of most "one device works, not both" bugs):**
- [ ] Set **both** CS pins as outputs and drive them **HIGH (deselected)** at startup, before initialising either device. Only one device's CS low at a time.
- [ ] **Initialise the SD card first**, before the panel — a shared-bus SD may not be recognised otherwise (it powers on in SDIO mode and must switch to SPI mode cleanly before other bus traffic).
- [ ] Run the bus at a clock speed the **SD tolerates** (library default) — the SD is the speed-limiting device, not the panel. Fine for a reader; neither needs to be fast.
- [ ] Don't start an SD transfer mid-refresh: wait for the panel's **BUSY** line to clear. Natural in the read-page → render → refresh → sleep loop, since the two never overlap.

### Firmware approach (decided)
- **Production firmware: C/C++ (Arduino/PlatformIO).** Chosen because the project-defining requirements — microamp deep sleep, clean wake timing, memory-careful page rendering in PSRAM — are where C/C++ has the advantage and where MicroPython's overhead works against the battery goals.
- **Reference libros for structure, not as a base.** Read it for how it organises book listing, text layout, page-turn navigation, and state — write a clean implementation rather than adopting its (admittedly messy, under-documented) code wholesale.
- **Calibration & test tools: MicroPython.** Battery characterisation, ADC-reading checks, panel bring-up, button-wake tests — run-once, iterate-fast jobs that run plugged in over USB, where C's compile-flash cycle is pure friction and deep-sleep efficiency is irrelevant.
- **Consider stealing the Open Book text format** (plain text, title on line 1, optional ASCII control codes for chapter/format) as a lightweight alternative/fallback to full EPUB parsing on an MCU.

> ⚠️ **ADC portability between MicroPython and C:** the two stacks can use different ADC attenuation/calibration defaults, so a raw ADC count in MicroPython may not match the same pin read from C. To keep the calibration curve valid: have the MicroPython tool log **calibrated voltages** (verified against a multimeter at known points), not raw counts — voltages transfer cleanly across languages. The curve is voltage→SOC anyway, so this fits.

### Step 6 — Firmware: core reading loop
- [ ] Deep-sleep architecture: wake on button → read battery at rest (before refresh/WiFi) → render page → partial refresh → sleep.
- [ ] Full refresh every N page turns (e.g. 5–10) to clear ghosting.
- [ ] Save reading position to flash/SD before sleeping.

### Step 7 — Firmware: battery UI + protection
- [ ] Map measured voltage through your **calibrated curve** (see §3–4) to SOC%.
- [ ] Display in 10% increments with hysteresis (only change shown value past a threshold, to avoid flicker).
- [ ] Low-voltage cutoff: at ~3.4–3.5V, show "low battery" and deep-sleep instead of operating — long before the cell's own ~2.5V hardware protection trips.

### Step 8 — Firmware: WiFi sync
- [ ] Bring WiFi up **only** on an explicit "sync books" action.
- [ ] Use static IP (saves 1–3s vs DHCP); store channel/BSSID in RTC memory for faster reconnect.
- [ ] Connect → fetch → disconnect as fast as possible, then back to the deep-sleep loop.

### Step 9 — Power validation
- [ ] Measure real deep-sleep current with a multimeter (expect microamps; watch for stray LEDs or USB left connected).
- [ ] Measure a page-turn wake's duration and current (the screen refresh + boost rails dominate, not the CPU).
- [ ] Confirm no busy-wait loops keeping a core awake.

---

## 3. Battery Calibration Tool — Recommendations

The goal: build a **voltage → state-of-charge lookup table** from *your* actual cell, divider, and ADC, so the firmware can read SOC accurately through the LiPo's flat mid-discharge plateau (where voltage barely moves and generic curves are unreliable).

### Why DIY characterisation beats a generic curve
- Runs through the **same divider resistors and ADC pin** you'll use in the reader, so resistor tolerance and ADC quirks bake into the curve and cancel out.
- Captures **your** cell's real plateau shape, not a textbook approximation.
- Re-running it yearly tracks **capacity fade** as the cell ages.

> Build this tool in **MicroPython** (iterate-fast, runs over USB). Log **calibrated voltages, not raw ADC counts**, so the curve transfers to the C production firmware regardless of ADC-stack differences. Verify the MicroPython voltage reading against a multimeter at 2 known points before trusting the run.

### Design principles
- **Measure resting voltage, not under-load voltage.** Your reader always reads the battery at rest right after wake, so the calibration should map *resting* voltage → SOC. Discharge in steps, pause to let voltage settle, then log.
- **Log against cumulative charge (mAh), not just time.** Discharge through a known fixed resistor (current = V/R, integrable) so the mapping is load-independent and directly meaningful. This turns "a curve" into a calibrated capacity map.
- **Same hardware end-to-end.** Run on the XIAO ESP32-S3 with the production divider and the same averaging/calibration code.
- **Characterise at room temperature** (LiPo curves shift with temperature) and don't expect the map to hold when very cold.

### Tool structure
1. Fixed resistor load across the battery (sized for a sensible, safe discharge current — e.g. a few tens of mA).
2. Loop: read averaged + ADC-calibrated voltage → log (timestamp, voltage, cumulative mAh) over USB serial to your computer → repeat.
3. Periodically pause the load briefly to capture **resting** voltage points.
4. **Hard low-voltage stop at ~3.3V** — don't chase the curve to empty; over-discharge stresses the cell. The protected cell's PCB is a backstop, not the routine stop.
5. Output a small lookup table (voltage → SOC%) to embed in the reader firmware.

### Safety cautions
- Never leave the discharge run **unattended** (resistor heat + the usual LiPo caution).
- Stream/log data **as you go** so a crash doesn't lose the dataset.
- Keep the firm software low-voltage stop; rely on the cell's protection only as a backstop.

---

## 4. Calibration Procedure — Steps

- [ ] **Prep:** fully charge the cell to 4.2V. Assemble the XIAO + production divider + fixed discharge resistor. Connect USB serial logging to your computer.
- [ ] **Record full point:** log the resting voltage at 100% (after a brief rest off charge).
- [ ] **Discharge in steps:** apply the resistor load, drawing a known current. Track cumulative charge drawn (mAh = current × time).
- [ ] **Rest and measure:** every step (e.g. every ~5–10% of estimated capacity), disconnect the load, let the cell rest a few minutes, log the **resting** voltage + cumulative mAh.
- [ ] **Repeat** down the curve — aim for ~15–20 points across the range for a good plateau model.
- [ ] **Stop at ~3.3V** resting voltage. Do not go lower.
- [ ] **Build the table:** convert cumulative mAh at each point to SOC% (mAh drawn ÷ total mAh capacity). You now have resting-voltage → SOC% pairs.
- [ ] **Embed** the lookup table in the reader firmware; interpolate between points at runtime.
- [ ] **Validate:** charge back up, run the reader, sanity-check that displayed % tracks sensibly (tight at the top/bottom, smoothed through the plateau).
- [ ] **Optional:** re-run annually to refresh the table and monitor capacity fade.

---

## 5. Power Architecture

**Battery life summary (deep-sleep model):** reading costs ~5mAh/hr (CPU render + e-paper refresh including boost rails — the screen, not the CPU, dominates each wake). Deep sleep ~14μA (plus board parasitics). On a 500mAh cell at ~80% usable: ~80 days at 1hr/day, ~40 days at 2hr/day, ~20 days of sustained 4hr/day. Consumption is **not** the limiting factor — self-discharge and any stray parasitic draw matter more. Numbers are estimates; the screen-refresh portion needs a meter on the actual HAT to pin down.

**Deep sleep is the everyday "off"** — wake on button in milliseconds, page intact. This is the primary power model.

**Charging (confirmed from board schematic):** the onboard charger (SGM40567) is fixed at **110mA charge current** (`ICharge = 24000/220K`), 4.2V cutoff. On a 500mAh cell that's a gentle ~0.22C — safe, but a full charge from empty takes **~5+ hours**. Fine for overnight charging; don't expect fast top-ups. Charges over USB-C (VBUS). Still **no load-side over-discharge protection** on the board → protected cell + firmware cutoff remain required.

**Slide switch = master cutoff (recommended backstop), NOT the daily off.** It covers what deep sleep can't:
- Long storage (months in a drawer) without slowly flattening + over-discharging the cell.
- Firmware lock-up that fails to sleep (a busy-loop bug would otherwise drain the battery) — physical off/on always recovers.
- True-zero "really off" for transport.

Wiring/usage notes:
- [ ] Wire the switch in the **battery line** (cell ↔ XIAO battery input) so off truly disconnects the cell.
- [ ] Treat it as a **"flip when not mid-action"** control — cutting power is safe for the ESP32 (no OS/SD-corruption risk like the Pi) BUT a cut mid-write (e.g. during a WiFi sync writing to SD) could corrupt that file.
- [ ] Check the **charging interaction** — confirm you can still charge over USB with the switch in its expected position, and that no switch position is unsafe with the charger.

**v2 option — soft-latch power circuit.** A P-MOSFET + button (or a Pololu-style pushbutton power switch) lets a button power the board on and lets *firmware cut its own power* after saving state. Best-of-both: true-zero-off, but graceful (never mid-write). More complexity than a first build needs; documented here as the natural upgrade.

### Charging status / UI

The charger's status pin is **not broken out** — it only drives the onboard charge LED (good for a visual check during dev, but firmware can't read it). So derive the charging UI from **battery voltage + VBUS-presence sensing** instead:

- **Charging detection:** sense VBUS (USB 5V) presence via a divided-down VBUS line on an ADC pin (5V scaled into the 3.3V range, like the battery divider). VBUS present = on charge.
- **Full detection:** on charge + battery voltage pinned at ~4.2V and no longer climbing = charging complete (charger tapers/stops at 4.2V).
- **Charge level:** read the same battery divider as in normal use.

⚠️ **Caveat — voltage reads high while charging.** Charge current elevates terminal voltage above the true resting level; in the CV phase it sits at ~4.2V before the cell is actually 100%. The resting-voltage calibration curve doesn't apply under charge. So:
- **While charging:** show a charging animation / "Charging…" and only "✓ Full" when voltage holds at ~4.2V — **don't** show a precise % (it would read optimistically high).
- **On battery (resting):** show the accurate % from the calibration curve, in 10% increments.

Costs **one extra ADC pin** for the VBUS sense (assigned to D3/GPIO4 — see §8). Wire it during the build if you want the charging UI.

---

## 6. Buttons & Enclosure (3D-printed)

The 6mm slim tactile switches already provide the click and spring-back via their internal dome. The printed parts must transfer a press cleanly then get out of the way. Most bad-feeling DIY buttons come from the plunger binding (kills spring-back) or wrong height.

**Printed plunger ("top-hat" captive cap):**
- [ ] Height: at rest lightly touching / a hair above the actuator; ~0.5mm press triggers the click. Too tall = mushy/pre-pressed; too short = dead travel before action.
- [ ] Clearance: ~0.3–0.4mm per side in the guide hole — free movement, no bind. FDM prints fat, so err loose and tune.
- [ ] Top-hat flange at the bottom so it's captive and can't fall out the front; switch dome holds it up against the lip.
- [ ] Print sliding surfaces as **vertical walls**; bore the guide hole along Z for roundness. Chamfer/ream the bore to remove first-layer lip.

**Spring-back options (easiest first):**
1. Rely on the switch's own dome + low-friction captive plunger (**start here**).
2. Printed flexure / living hinge (PETG or TPU — not PLA, which fatigues and cracks).
3. Tiny physical compression spring (only if you want longer travel than ~0.5mm).

**Mounting (quietly ruins feel if wrong):**
- [ ] Switch must be **rigidly held** (printed pocket or protoboard clipped/screwed in) — if the switch shifts, the click feels mushy.
- [ ] Actuator must align **exactly** under the plunger; locating pocket prevents sideways drift and tilt-binding.

**Material:** PETG recommended (tougher than PLA, slightly self-lubricating, won't soften in a warm bag at ~50–60°C). PLA fine for prototypes.

**Reader-specific:** domed/proud caps on the side edges where thumbs rest; a slight recess around each to prevent accidental presses in a bag. Shape the cap top (dish or pip) for nicer feel than a flat switch.

- [ ] **Do a tolerance test print** (plunger + hole at 0.25 / 0.35 / 0.45mm clearance) before committing — teaches you more than any spec, specific to your printer.

**Antenna placement (U.FL variant):** adhere the flexible flat antenna to the inside case wall, **clear of the LiPo's metal pouch** and any foil/copper, near a plastic edge (RF-transparent). Route the pigtail so it isn't pinched when the case closes. Connect the U.FL plug once, straight down until it clicks — it's fragile and rated for few mating cycles.

---

## 7. Accelerometer (optional — LIS3DH)

Adds orientation/gesture features. I²C (shares SDA/SCL with any other I²C device — doesn't touch the SPI bus), ~2μA in low-power mode.

Possible features:
- **Auto-rotate** — debounce heavily (rotate only after new orientation held ~1–2s); each rotation is a full e-paper refresh with its flash, so it's less seamless than LCD. Treat as secondary.
- **Tap / double-tap page turn** — gesture alternative to buttons.
- **Lift-to-wake** — the chip's motion-wake interrupt line can be an ESP32 deep-sleep wake source, like the buttons.

Wiring: 2 shared I²C pins + 1 GPIO for the interrupt line (worth wiring for motion-wake). Earns its place mainly if you want gesture interaction or lift-to-wake; auto-rotate alone is a weak reason on e-paper. Wire the I²C bus out during the initial build even if deferring, to avoid a retrofit.

---

## 8. Pin Assignment (XIAO ESP32-S3 Plus)

Confirmed against the official board pinout. All D0–D10 pads are **ADC1** (ADC1 is unaffected by WiFi, unlike ADC2 — correct choice for battery sensing). **D2 (GPIO3) is a strapping pin** and is left unused. **D11/D12 (GPIO42/41) have no ADC.** No I²C in use, so D4/D5 are free for other roles.

| Function | Label | GPIO | Notes |
|----------|-------|------|-------|
| SPI SCK (shared: panel + SD) | D8 | GPIO7 | Native SCK |
| SPI MOSI / DIN (shared) | D10 | GPIO9 | Native MOSI |
| SPI MISO (SD only) | D9 | GPIO8 | Native MISO; panel doesn't use it |
| E-paper CS | D0 | GPIO1 | Non-strapping |
| E-paper DC | D1 | GPIO2 | Non-strapping |
| E-paper RST | D3 | GPIO4 | Non-strapping (deliberately off D2/GPIO3) |
| E-paper BUSY (input) | D6 | GPIO43 | Input only; fine on TX pad |
| SD CS | D7 | GPIO44 | Output; fine on RX pad |
| Battery divider (ADC) | (pin 20) | GPIO10 | `ADC_BAT`, ADC1_CH9 (WiFi-safe). Board's R10 220kΩ = divider lower leg; add upper 220kΩ from VBAT |
| VBUS sense (charging detect) | D3 | GPIO4 | ADC1, divided-down from VBUS (5V → scale into 3.3V range). Detects USB-present = charging |
| Button: page fwd / wake | D4 | GPIO5 | RTC-capable wake source |
| Button: page back | D5 | GPIO6 | RTC-capable |
| Button: menu / select | D11 | GPIO42 | RTC-capable castellation |
| (unused) | D2 | GPIO3 | Strapping pin — left free |

**Spares for later:** D2/GPIO3 (input-only if used), more castellation pads (GPIO33–40, 45–48), GPIO21 (User_LED), and the I²C pads D4/D5 if I²C is ever added (would displace the battery divider / button — re-plan then).

**Verify before soldering:**
- [ ] ~~GPIO10 ADC_BAT onboard divider~~ **RESOLVED (schematic):** no onboard divider; R10 (220kΩ to GND) can be the lower leg — add an upper 220kΩ from VBAT to GPIO10 for ÷2. Confirm R10 value in situ.
- [ ] **D6/D7 (GPIO43/44) are the UART TX/RX pads** — fine for BUSY/CS since you flash/debug over native USB, but confirm you don't need hardware serial on them.
- [ ] ~~E-paper HAT VCC at 3.3V~~ **CONFIRMED** the display runs on 3.3V. All peripherals run from **VCC_3V3** (header pin 12); the **5V/VBUS pin is dead on battery** so never wire peripheral power to it.

---

## 9. Timekeeping (NTP-on-sync)

The ESP32 has **no battery-backed RTC**. Its internal RTC counts through deep sleep (so daily use keeps time) but is lost on a hard power cut (the §5 slide switch zeroes it), and it drifts on an internal RC oscillator (minutes/day) even across sleep. A reader doesn't fundamentally need wall-clock time, so:

- **Default: set the clock via NTP during each WiFi book sync** — fetch network time right after WiFi connects, before disconnecting. Every sync re-corrects both the drift and any hard-switch loss, so the switch's clock-loss becomes a non-issue. No extra hardware.
- [ ] Store last-known time + last-sync timestamp in **RTC memory** (survives deep sleep, not the hard switch) for an approximate running clock between syncs.
- [ ] **Display rule:** show the clock in the top bar **only if an NTP sync has occurred within the last ~24h** — otherwise hide it, so a stale/wrong time is never shown confidently.
- **Optional upgrade — DS3231 battery-backed RTC** (I²C, shares the bus): precision, temperature-compensated, keeps correct time across long switch-off periods and infrequent syncs on its own coin cell. Only worth it if you want an always-correct clock independent of sync frequency.

---

## 10. Content Pipeline (DRM-free EPUB → device format)

**Boundary:** the DRM unlock for purchased books happens **upstream in established desktop tools** (e.g. Calibre + plugins) — out of scope here. This pipeline's input is an **already-DRM-free EPUB**. The device never touches DRM, Amazon, or B&N — no on-device decryption (not feasible on the chip and not something to implement). The reader only ever handles DRM-free files.

### Why a desktop microservice
EPUB parsing (zip + XHTML + CSS reflow + pagination) is heavy and memory-hungry — wrong job for a 512KB-SRAM MCU. Do it once on the PC; ship the ESP a trivially simple format. Powerful machine does the hard part; ESP just paginates/draws.

### Architecture (Docker on Ubuntu)
- **Watcher** → monitors `./library/incoming` for new EPUBs (`watchdog`, or rescan on request).
- **Converter** → `ebooklib`/`lxml` parse spine + metadata → flatten to device format → cache in `./library/converted/{book_id}/` (book_id = hash of source).
- **HTTP API (FastAPI)** → `GET /library` (JSON index), `GET /book/{id}`, `GET /book/{id}/page/{n}` (bitmap mode), `GET /time` (folds into NTP-on-sync).
- ESP WiFi sync hits the API over LAN; find PC IP via `ip addr` (or add mDNS later).

Stack: `python:3.12-slim` base, `fastapi` + `uvicorn`, `ebooklib`, `lxml`, `beautifulsoup4`, `pillow`, `watchdog`. Bind-mount `./library` so books + cache persist across rebuilds; publish port 8000 to LAN.

### Device format: text vs bitmap

| Factor | Text mode | Bitmap mode |
|--------|-----------|-------------|
| Storage/book | ~0.5–1MB | ~26MB (400pp × 64.5KB) — **25–50× more** |
| On-device work/page | Parse, lay out, rasterise fonts | Read bitmap, blit. Near zero |
| Firmware complexity | Needs layout + font engine | Trivial — none |
| Power/page turn | Higher (CPU works) | Lowest (CPU barely wakes) |
| Page turn speed | Slower | Fastest |
| Font/size change on device | ✅ re-layout | ❌ fixed at render time |
| Reading position | Char offset + re-paginate | Clean "page N of M" |

Storage cost of bitmap is real but **trivial at your scale** (2GB ≈ 75 books; 32GB ≈ 1000+). 1-bit pages compress 5–10× if ever needed. Bitmap trades abundant storage for scarce resources (battery, firmware simplicity, page-turn speed) — aligns with project priorities.

**Hybrid:** PC pre-renders at 2–3 font sizes, device switches between them — bitmap simplicity + some flexibility, few× storage.

**Recommendation:** **text mode for development** (fast iterate, debug, change fonts freely, don't need exact panel bitmap format yet) → **bitmap or multi-size hybrid for production** (lowest power, simplest firmware). Match bitmap packing to the panel's exact 1-bit 960×552 format so the ESP streams straight to the display with no repacking.

### Overclocking during render?
Race-to-sleep: higher clock helps **only if the CPU is the bottleneck**. In **text mode** layout is real CPU work → running at rated 240MHz to finish and sleep sooner is a legitimate (modest) saving. In **bitmap mode** the wake is SD-read + e-paper-refresh bound (CPU idle-waits on BUSY) → overclocking buys ~nothing. **Don't exceed rated spec** (instability risks a crash that fails to sleep — the one thing that wrecks battery life). Measure render vs refresh timings before bothering; it's a tuning detail, not a design driver.

---

## 11. Open Items / Future

- [ ] Storage architecture: ~~decide flash-only vs microSD~~ **decided** — microSD for dev, XTSD optional for final build (see §1/§2). Still TODO: filesystem layout for the book library.
- [ ] Enclosure / case design (button mechanics + antenna placement covered in §6).
- [ ] EPUB parser + font rendering choice (rendering to PSRAM framebuffer). Consider the lightweight Open Book text format as a fallback.
- [ ] Content pipeline (§10): build the Docker conversion microservice; decide text vs bitmap vs hybrid output format.
- [ ] Partial-vs-full refresh cadence tuning for best ghosting/speed balance.
- [ ] Sleep-current audit on the final assembled hardware (verify board parasitics aren't inflating the ~14μA chip figure).
- [ ] Concrete pin assignment: map each panel line, the two CS pins (off strapping pins), the ADC pin (not A11/A12), the RTC wake button, and optional I²C/accelerometer interrupt.
- [ ] Decide on the accelerometer (§7) and the soft-latch power v2 (§5).

### References
- **libros** (github.com/joeycastillo/libros) — ESP32-S3 Open Book firmware in C/C++. Reference for framework structure (book listing, text layout, page navigation). WIP and lightly documented.
- **The Open Book** (github.com/joeycastillo/The-Open-Book) — hardware reference (Pico-based, custom PCB — not our build). Useful for the castellated e-paper driver schematic and the lightweight text format.
