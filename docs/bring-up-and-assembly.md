# Bring-up & assembly plan (hardware in hand)

**Status:** active work plan, 2026-07-28. Supersedes the generic checklist in
`ereader-build-guide.md` §2 (written pre-benchmark, pre-CrossPoint decision).

> **Updated 2026-11-23:** the logic board is gone. Parts are wired straight to
> the XIAO inside the case, and Phase 5 now describes that. The wire list is
> `hardware/README.md`. The pin table in `CLAUDE.md` is the source of truth for
> which pin does what.

What's already settled and must not be re-litigated here: the pin map
(`CLAUDE.md` §pin assignment) and the pin-conflict resolutions
(`hardware/archive/` has the history; `hardware/README.md` is the wire list),
the firmware base (fork CrossPoint — `docs/crosspoint-adoption-plan.md`), the
service shape (OPDS library server). Measured numbers live in
`docs/hardware-spec-sheet.md`; every phase below names the rows it fills.

**Governing principle: nothing gets soldered into the case until it has
worked on flying leads.** It's a direct-solder build with about 30 hand-routed
wires in tight channels, so rework is expensive. Bench-validate
first, commit second (Phase 5).

---

## Phase 0 — Checks before the iron is hot (~1 hour, no soldering)

Cheap now, expensive later. All five are open questions in the repo that a
physical part in your hand answers immediately.

- [ ] **Which panel edge does the FPC exit?** **Answered: it exits the BOTTOM**
      (2026-07-28); the case layout puts the HAT at the bottom and the
      XIAO/USB-C at the top. *(Open item in CLAUDE.md
      §mechanical.)*
- [ ] **Confirm panel VCC = 3.3 V** on the HAT (the 5 V pin is dead on battery —
      all peripherals run from VCC_3V3).
- [ ] **Set the driver HAT's interface switch to `4-line SPI`** (not `3-line SPI`).
      Our `Epd5in0` driver and the vendor `EPD_5in0` example both use a dedicated
      DC pin (GPIO2/D1); 3-line/9-bit SPI has no DC line and folds the D/C bit into a
      9th SPI bit, so it would misread every byte. If the HAT also has a Display
      Config (A/B) switch, set it per Waveshare's wiki for this 5" panel.
- [ ] **Is the flash module SPI-mode?** Path 1 storage (shared SPI + SdFat)
      assumes SPI. If it's an XTSD, confirm the breakout is wired for SPI, not
      SD/SDIO. *(Open item in the adoption plan §6.)*
- [ ] **Check the XIAO's pad positions** against the case's side slots and
      the pinout card (D17-D19 = GPIO13/12/11), and check nothing on its
      **underside** stands proud of the PCB where it rests in the cradle.
- [ ] **Measure the board's R10** (the battery divider's lower leg, 220 kΩ
      expected) in situ before trusting it as half the divider.
- [x] **VBUS-sense: settled.** It's an on/off input on D19/GPIO11, through a
      150k / 220k divider from the 5V pad. Check in Phase 3 that it reads high
      on a few different chargers and low on battery.

**Decision needed (see "Open decisions" below): headers vs. a second XIAO.**

---

## Phase 1 — Panel bring-up on flying leads

**Goal:** pixels on glass, and separate "my wiring is wrong" from "our driver
port is wrong".

1. Wire the HAT's 9 lines to the XIAO per `CLAUDE.md` (GPIO / board-pin label:
   CS=GPIO1/D0, DC=GPIO2/D1, RST=GPIO4/D3, BUSY=GPIO43/D6, SCK=GPIO7/D8,
   DIN=GPIO9/D10, **PWR=GPIO3/D2 driven HIGH — NOT tied to 3V3**, VCC=3V3, GND).
   The HAT's dupont cable is the right tool here; do not solder yet.
   > **Panel protection (do this from the very first bring-up).** The panel's HV
   > source drivers must not sit energised — *"prolonged exposure to high voltage
   > can damage the film"* (irreparable). Sequence: `refresh → sleep(0x10) the
   > instant BUSY clears → wait ≥2s → PWR low`. The ≥2s is the HV-rail discharge
   > wait *before cutting power*; there is **no** minimum delay between refresh and
   > sleep, and the real risk is leaving the panel active/idle (do SD/WiFi work
   > with it asleep). Waveshare's own `EPD_5in0` example already does this
   > (`Sleep()` then `DEV_Module_Exit()`); our `firmware/epub-benchmark` mirrors
   > it at the end of `setup()`. This is why PWR is a GPIO (D2), not hardwired.
   > On idle/low-battery/storage shutdown, `clearWhite()` **before** sleeping so no
   > stale static image is left on the bistable panel (Waveshare: *"store it with a
   > white image"*) — sequence `clearWhite → sleep(0x10) → ≥2s → PWR low`.
2. **Flash Waveshare's own `EPD_5in0` ESP32-S3 example first**, unmodified apart
   from pins. This is the reference oracle — if it renders, wiring is good.
3. Then flash `firmware/epub-benchmark/` and compare. It times panel init, full
   and partial refresh, and now has a real BUSY line (the earlier no-panel run's
   refresh numbers were bogus).
4. Check **orientation and mirroring**. If the image is vertically mirrored,
   flip the `0x11` data-entry mode / `0x45` Y window in
   `firmware/epub-benchmark/src/Epd5in0.cpp` (Waveshare's values are copied
   verbatim there and known-suspect).
5. Note the partial-refresh path in our driver is **approximate** — it doesn't
   seed the `0x26` "previous" RAM bank. Expect ghosting on partial; that's the
   known gap, fixed in Phase 6.

**Pass:** stock example renders; our `Epd5in0` renders the same, correct
orientation; full ≈1.8 s, partial ≈0.7 s.
**Fills spec sheet:** E-ink section (full refresh, partial refresh, partial
RED-RAM correctness, ghosting cadence).
**Unblocks:** the Phase 6 display HAL port — and this is the single biggest
remaining hardware risk in the project.

---

## Phase 2 — Storage on the shared bus

**Goal:** prove the shared-SPI discipline that CrossPoint does *not* implement,
before inheriting responsibility for it.

> **What's actually "shared":** SCK=GPIO7/D8 and MOSI=GPIO9/D10 are the common
> bus lines — they were already wired in Phase 1 (the panel drives them), so the
> SD reuses them rather than adding new pins. That's why the wiring step below
> only lists two pins. Each device keeps its **own** CS (panel EPD-CS=GPIO1/D0,
> SD-CS=GPIO44/D7), and MISO=GPIO8/D9 is SD-only (the panel is write-only, no
> MISO). Sharing SCK/MOSI is exactly what the discipline below exists to police.

1. Add the storage module to the same bus — it adds only its **two own** signal
   pins: MISO=GPIO8/D9 and SD-CS=GPIO44/D7. (SCK=GPIO7/D8 and MOSI=GPIO9/D10 are
   already present from Phase 1.)
   > **Power the module from its `3V3` pin, NOT `VIN`.** Dual-input SD breakouts
   > route `VIN` (5V) through an onboard regulator + level shifter (for 5V-logic
   > boards); `3V3` feeds the card directly. Two reasons to use 3V3: (a) the 5V
   > rail is **dead on battery**, so a VIN-powered SD would fail off-USB; (b) the
   > XIAO is 3.3V logic, so the direct path avoids the level shifter — a shifter in
   > the MISO return is a classic "card won't init / CMD0 fail" cause. Leave VIN
   > (and CD/card-detect) unconnected.
2. Enforce the rules from `CLAUDE.md`: both CS (EPD-CS=GPIO1/D0, SD-CS=GPIO44/D7)
   as outputs driven **HIGH** before any init; **SD initialised first**; bus clock
   at the SD's tolerated speed; never start an SD transfer while BUSY is asserted.
3. Test SD **and** panel in one sketch, alternating — the "one device works, not
   both" bug class shows up only when both are live.
4. Enable SdFat's **`USE_SD_CRC`** now (integrity layer 1 from the adoption plan
   §3.2) and measure the cost.
5. Measure read throughput, write throughput, and a small (6-byte)
   `progress.bin`-sized write — the per-page-turn cost.

**Pass:** panel and storage both work in the same sketch across many
alternations, with CRC on.
**Fills spec sheet:** Storage section (all three TBDs), plus SD read speed in
the EPUB benchmark's step 6 when `/sample.xhtml` is present.

---

## Phase 3 — Buttons, deep sleep, and the meter

**Goal:** validate the power architecture the whole battery claim rests on.

1. Wire the 3 buttons (fwd GPIO5/D4, back GPIO6/D5, menu GPIO13/D17-castellation)
   to GND with pullups. GPIO13/D17 needs a wire directly to the XIAO castellation
   pad — solder it **before** the XIAO is ever seated flat.
2. Test `ESP_EXT1_WAKEUP_ANY_LOW` across all three, and confirm wake = chip
   reset (CrossPoint's model, and ours).
3. Build the epub-benchmark with `-DBENCH_SLEEP_CYCLES=N` to get real
   wake-latency numbers over repeated cycles.
4. **Get out the multimeter** (or PPK2) — firmware cannot self-measure current:
   - deep-sleep current (target ~14 µA; **USB detached**, watch for stray LEDs),
   - active / render / refresh current,
   - WiFi-peak current.
5. Confirm no busy-wait loop holds a core awake.

**Pass:** all 3 buttons wake from deep sleep; deep-sleep current in the tens of
µA at worst.
**Fills spec sheet:** Wake/power section (full-reset-to-render, wake latency,
and all three `meter` rows).
**If deep-sleep current is milliamps, stop and find it here** — this is the
number that decides whether "weeks-to-months per charge" is real.

---

## Phase 4 — Battery: divider, then a multi-day calibration run

Start this **early and in parallel** — the discharge curve is wall-clock-bound
(days), not effort-bound, and Phase 6's battery seam needs its output.

1. Connect the **protected** LiPo (polarity!). Confirm USB-C charging and
   battery-only operation.
2. Build the divider: on-board upper 220 kΩ (`R-BAT`), board R10 as the lower
   leg (value confirmed in Phase 0), tap → GPIO10 (`ADC_BAT`, pin 20 — a dedicated
   pad, not a D-labelled header pin) via a castellation flying wire.
3. One-point calibrate against a multimeter; average 50–100 samples with
   `esp_adc_cal` eFuse calibration.
4. Run the characterisation: log **calibrated voltages, not raw ADC counts**
   (MicroPython and C differ in attenuation/calibration defaults; the curve is
   voltage→SOC anyway, so voltages transfer). Discharge under a realistic
   reading load down to ~3.4 V.
5. Output: a resting-voltage→SOC **LUT**, dropped into the battery seam in
   Phase 6 to replace CrossPoint's hardcoded cubic polynomial.

**Tooling gap:** the MicroPython calibration tool described in `CLAUDE.md` and
`ereader-build-guide.md` §3–4 **does not exist yet** — it needs writing before
this phase can run.
**Fills:** the SOC LUT (a project artifact, not a spec-sheet row).

---

## Phase 5 - Commit: wire it into the case

**There is no logic board.** Every part is wired straight to the XIAO, and the
case's channels, slots and tabs hold the wires. The wire-by-wire list is
`hardware/README.md`; solder from that. (The old protoboard and ProtoMate build
sheets are in `hardware/archive/`, for reference only.)

### Before the iron is hot

- [ ] Phases 1-4 all passed on flying leads.
- [ ] The XIAO pinout card agrees with `hardware/README.md` (D17-D19 =
      GPIO13/12/11), and you know which physical edge carries D0-D6.
- [ ] Every part dry-fits in a printed case: XIAO in its cradle with USB-C
      lined up, HAT on its pins, storage board on its pins, battery between its
      stops, keys in their cradles, power switch in its mount.
- [ ] Legs trimmed: key switches to 2.4, power switch to 0.5.

### Solder order

Access is the constraint: the XIAO's underside can't be reached once it sits
in its cradle.

1. **XIAO underside first, off the case.** BAT+ and BAT- (bottom centre), and
   the extra pads you use: D17 (menu), D18 (cover sensor, if fitted), D19 (USB
   sense). Sleeve each joint and route the wires clear.
2. **Build the two dividers inline** (resistors soldered together, sleeved in
   heat-shrink) and attach them to the XIAO.
3. **Edge pins.** Two wires go into each shared pad (3V3, GND, SCK, MOSI).
4. **Seat the XIAO**, then run the wires out through the side slots.
5. **HAT**: the 9 wires to its old PH2.0 pads, along the guide fins.
6. **Storage board**, then the optional cover sensor (powered from the storage
   board's pads).
7. **Keys**: the three signal legs, then one ground wire chained key to key
   and on to the HAT's GND pad.
8. **Power switch and battery last**, so nothing is live while you work.
9. Strain-relieve the USB-C end and the battery wires with a dab of hot glue
   once everything has been tested.

### Keep it thin

- 30 AWG Kynar, laid flat in the channels, never looped.
- Trim every lead flush.
- Re-measure the assembled depth here and feed it to Phase 8.

### Iron and consumables

- Fine chisel tip (about 1.5 mm), around 350 °C, leaded 0.5-0.7 mm solder if
  you have it, and a flux pen for the small castellated pads.
- Tin the pad, tin the wire, join. Heat 1-2 s; the XIAO's pads are small and
  lift if cooked.

### Check before power

- [ ] Meter every wire end to end against `hardware/README.md`.
- [ ] Check 3V3 to GND and BAT+ to GND for shorts **before the battery goes
      anywhere near it**.
- [ ] First power from USB with the switch off, then switch on.
- [ ] **Re-run Phases 1-3 in the case.** A wiring fault found now is rework;
      found after the front plate is screwed down, it's a rebuild.

---

## Phase 6 — Fork CrossPoint and port the HAL

Full work-item lists are in `docs/crosspoint-adoption-plan.md` §3 — don't
duplicate them here. Order, and why:

1. **Display** (§3.1) — visible progress, and it includes the blocking compile
   fix (`GfxRenderer`'s `static_assert`: 8000 doesn't divide 66240 → use 6624).
   Flash via SD firmware update for the fastest loop.
2. **Input** (§3.6) — repin to our 3 buttons.
3. **Storage** (§3.2, Path 1) — `SD_MMC` → SdFat on the shared bus, plus the
   shared-bus coordination that is net-new code.
4. **Battery** (§3.3) — the LUT from Phase 4, averaging, hysteresis, VBUS-based
   charge detection, and the low-battery cutoff (none exists upstream).
5. **Deep-sleep wake** for 3 buttons.
6. Apply `docs/firmware-perf-tuning.md` (flash QIO — CrossPoint ships `dio`;
   `-DCORE_DEBUG_LEVEL=0`; WiFi `setSleep(false)` + BSSID/channel cache).
7. **Finish the partial-refresh RED-RAM baseline** in `Epd5in0`, or run
   full-refresh-only until it's done.

Prototype any UI restyling in `simulator/` first — it's pixel-exact.

---

## Phase 7 — End-to-end service integration

1. Deploy `service/` (Docker) on the Ubuntu box; add the OPDS server on-device
   (`http://<IP>:8000/opds`) via the settings UI.
2. Download a DRM-free EPUB over LAN, verify against the published
   `<esp:sha256>`, read it, confirm progress syncs to the self-hosted KOReader
   endpoint.
3. OTA: **SD-card path first** (build `firmware.bin` → SD → Settings), then
   repoint `latestReleaseUrl` at our GitHub Releases. Numeric tags only — a
   leading `v` breaks the `sscanf` version compare.
4. Add the cache CRC32 + download SHA-256 verification (integrity layers 2–3).

---

## Phase 8 — Enclosure

Oasis-style grip spine, portrait (`enclosure/ereader-case.sc`, v8; see
`enclosure/MEASUREMENTS.md`). Check it against the real soldered Z-heights measured in Phase 5.
PETG, captive top-hat button plungers (~0.3–0.4 mm clearance), buttons on a side
long edge, battery clear of the antenna foil.

---

## Open decisions

1. **Headers vs. a second XIAO.** Phases 1–4 want a breadboard-friendly XIAO;
   the final build needs it **soldered flat** (any socket/header adds ~8.5 mm and
   blows the Z budget). Desoldering 14 header pins from a
   validated XIAO is real risk. **Recommendation: solder male headers for all
   bench work and buy a second XIAO (~£15) to solder flat for the final build.**
   Cheap insurance, and it keeps a known-good spare.
2. **VBUS-sense pin:** settled. D19/GPIO11 as an on/off input, through a
   150k / 220k divider (see `hardware/README.md`).
3. **microSD for dev, flash module for production?** `ereader-build-guide.md`
   §5b suggests developing on removable microSD (books via card reader) and
   switching later. With OPDS download working that matters less, but a
   removable card is much easier for Phase 2 debugging and SD-card OTA.

## Tooling that needs writing

- MicroPython battery calibration tool (blocks Phase 4).
- A minimal panel-only bring-up sketch, if the epub-benchmark proves too
  coarse for iterating on the `0x11`/`0x45` orientation fix (Phase 1).
- A buttons + deep-sleep-wake test sketch (Phase 3) — the benchmark's
  `BENCH_SLEEP_CYCLES` covers timing but not multi-button ext1 wake.
