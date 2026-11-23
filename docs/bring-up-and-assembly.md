# Bring-up & assembly plan (hardware in hand)

**Status:** active work plan, 2026-07-28. Supersedes the generic checklist in
`ereader-build-guide.md` §2 (written pre-benchmark, pre-CrossPoint decision).

> **KNOWN STALE (2026-07-29) — not yet fully synced with this session's fixes:**
> Phase 0's "which FPC edge / resolve VBUS-sense" items below are now **answered**
> (FPC confirmed bottom-exit, layout swapped; VBUS-sense resolved to D2/GPIO3 —
> both in `CLAUDE.md`), and the board-population philosophy changed a lot (most
> signals now solder direct-to-XIAO, not through the board — see
> `hardware/protoboard_build_sheet_generator.py` and `hardware/README.md` for the
> current model). The hole-budget table below is fixed; the Phase 0 checklist and
> later wiring-step prose are not — treat `CLAUDE.md` and the generator as the
> source of truth where they conflict with this doc until a fuller sync pass.

What's already settled and must not be re-litigated here: the pin map
(`CLAUDE.md` §pin assignment) and the pin-conflict resolutions
(`hardware/README.md` §conflicts — the ProtoMate *layout* is superseded, Phase 5),
the firmware base (fork CrossPoint — `docs/crosspoint-adoption-plan.md`), the
service shape (OPDS library server). Measured numbers live in
`docs/hardware-spec-sheet.md`; every phase below names the rows it fills.

**Governing principle: nothing gets soldered to the logic board until it has
worked on flying leads.** It's a direct-solder, Z-height-constrained build with
~25 hand-routed point-to-point wires — rework on it is expensive. Bench-validate
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
- [ ] **Dry-fit the XIAO on a protoboard and measure its pad row-to-row
      spacing** with calipers (likely 12.7 mm / 5 pitches). This sets the notch
      dimensions in Phase 5 — measure before cutting anything, and check whether
      anything on the XIAO's **underside** protrudes below its PCB (it decides
      whether the case needs a clearance pocket or a flat boss).
- [ ] **Measure the board's R10** (the battery divider's lower leg, 220 kΩ
      expected) in situ before trusting it as half the divider.
- [ ] **Resolve VBUS-sense.** `hardware/README.md` moves it to "a spare ADC1
      castellation" — verify that's actually possible: ESP32-S3 **ADC1 is
      GPIO1–10 only, and ADC2 is unusable while WiFi is up**. The castellations
      are high-numbered GPIOs, so they are likely ADC2 → not viable as an analog
      pin. Two clean outs:
      - **Preferred: make VBUS-sense digital.** You only need *presence*, not a
        level ("full" is detected by the battery holding ~4.2 V, not by VBUS).
        A divided 5 V into any spare GPIO as a digital input works and dodges
        ADC2 entirely.
      - Or use **D2/GPIO3 (hole I6)** — the one genuinely free ADC1 pin,
        already broken out. Caveat: it's a strapping pin (JTAG source select);
        a divided VBUS present at boot pulls it to ~2.5 V. Verify boot behaviour
        with USB attached before committing.
      Whichever you pick, record it in `hardware/README.md` and in the new
      protoboard layout (Phase 5).

> Note: with the plain protoboard (Phase 5) the "not broken out" half of this
> problem disappears — nothing is pre-routed, so every pin is equally reachable.
> The **ADC1-vs-ADC2** constraint is a silicon fact and still applies.

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

## Phase 5 — Commit: build the logic board (plain protoboard)

**Board decided 2026-07-28: a plain double-sided 2.54 mm through-hole
prototyping PCB, cut to size — not the ProtoMate.** `hardware/protomate_build.pdf`
and its generator are **superseded**: that build sheet encodes the ProtoMate's
continuity (row strips `ABC`/`FGH`, split buses `D`/`E`, Column I = XIAO pads)
and only 7 jumpers. **A plain protoboard has zero continuity — every hole is an
isolated plated pad**, so every net is a wire or a deliberate solder bridge, and
the layout has to be redone. See "Re-layout needed" below.

### What the change buys, and what it costs

Gain (see `CLAUDE.md` §mechanical for the arithmetic): Z drops from ~11 mm to
**~10.7 mm** with the XIAO on top of a 1.2 mm board, and to **~9.8 mm** with the
XIAO **in-plane in an edge notch** (DECIDED — see below), at which point the 5 mm
battery becomes the tallest item. Also: free placement, and the castellation-vs-
breakout problem evaporates (nothing is pre-routed, so VBAT / ADC_BAT / VBUS_S /
MENU are just four more point-to-point wires rather than exceptions).

Cost: hand-routing everything, with no pre-printed structure to lean on. The
laid-out reality (see the generator below): **4 bare-wire buses + 14 insulated
wires + 4 part bridges + 4 castellation flying wires + 14 XIAO stub legs.**
Recreating the rails as buses is what keeps the insulated-wire count that low —
a naive one-wire-per-connection layout would be ~40. Both mitigations are
non-negotiable: a validated layout before you start, and a meter-verified net
list before power.

### The XIAO cutout (DECIDED: edge notch, in-plane)

"In-plane" means the XIAO's **own PCB is no longer stacked on top of the
protoboard** — the protoboard has material removed so the XIAO drops into the
gap, its underside flush with the protoboard's underside. The two are side by
side in Z rather than one on the other.

**What it actually saves: exactly the protoboard's thickness** (~1.2–1.6 mm), no
more. Stacked, the XIAO's 4.7 mm sits on 1.2 mm of FR-4 = 5.9 mm. In-plane, the
tall item is the XIAO's 4.7 mm alone — and since the battery is 5.0 mm, **the
battery becomes the constraint and the electronics stop being the limiting
factor**. That's the real prize: further Z reduction is now a battery-selection
question, not a layout question.

Two ways to do it:

**A. Interior window** — a closed rectangular hole ≈ XIAO outline + 0.4 mm
clearance (**≈ 18 × 21.5 mm, i.e. 7 × 8.5 holes**), pads surviving all four
sides. Sounds tidy, is worse: four internal cuts you can't score-and-snap (needs
a drill + jeweller's saw or a rotary tool), and the XIAO hangs suspended on its
own wires with nothing to rest on.

**B. Edge notch — recommended.** A U-shaped bay cut into the board edge, open on
one side, ≈ **18 mm wide × 21.5 mm deep (7 × 8.5 holes)**. Better on every axis
that matters here:

- **Two straight cuts**, both score-and-snappable from the edge.
- The layout already puts the XIAO at the bottom edge with **USB-C facing out of
  the case** — an open notch lets the connector sit proud of the board outline
  with no third cut in its way.
- **The enclosure can support it.** A flat boss or a shelf moulded into the case
  floor carries the XIAO directly, so the 14 wires are electrical connections,
  not structure. With variant A they are both, which is how solder joints fail.
- Easier to align and adjust during dry-fit; easier to rework.

**Mount it in the notch like this:**

1. **Measure the XIAO first.** Its 14 pads are on 2.54 mm pitch, 7 per side; the
   **row-to-row spacing is likely 12.7 mm (5 pitches) but confirm with calipers**
   and a dry-fit before cutting. Getting this wrong wastes a board, and you have
   several — dry-fit is free.
2. Cut the notch so a **ring of protoboard pads survives along both long edges**
   of the XIAO, one hole outside each pad row. Those are your landing pads.
3. **Stub-leg technique:** solder a short length of solid 26 AWG wire vertically
   into each XIAO hole, bend it 90° outward at board level, and solder the leg
   into the facing protoboard pad. This gives an adjustable, mechanically sound
   joint and lets you set the XIAO's Z precisely — shim it so USB-C lines up with
   the case port before committing the legs.
4. Do the **four castellation wires (VBAT, ADC_BAT, VBUS_S, MENU) before** the
   XIAO goes into the notch. Unreachable after.
5. **Keep the U.FL antenna edge clear** — no wires crossing it, battery foil away
   from it.
6. Epoxy or hot-glue fillets at two corners after electrical testing, plus a bead
   on the USB-C end for strain relief.

> The 4.7 mm figure includes the USB-C connector, which is the tall part. Confirm
> nothing on the XIAO's **underside** protrudes below its PCB — if it does, it
> sets how flush you can actually go, and the notch depth needs a clearance
> pocket in the case floor rather than a flat boss.

### Z discipline (or the saving evaporates)

Back-side wiring is now part of the stack. ~1 mm of wire loom cancels the entire
gain over the ProtoMate.

- [ ] **30 AWG Kynar (wire-wrap) wire**, laid flat against the board, not looped.
- [ ] **Trim every lead flush** with flush-cutters — bare protoboard leads stick
      out ~2–3 mm, more than the whole Z saving.
- [ ] Decide which face is the enclosure-inside face and keep wiring on it.
- [ ] Re-measure real assembled Z here and feed it to Phase 8.

### Board size — cut 26 × 17 holes ≈ 66 × 43 mm

Derived from the hole budget, not guessed. **This table is a snapshot (2026-07-29)
of `protoboard_build_sheet_generator.py`'s own printed summary — don't hand-update
it when the generator changes; just re-run the script and copy its "Holes used"
line.** It predates two later decisions that shrank the real number a lot: (1)
the board-population philosophy (only genuinely SHARED nets touch the board —
E-paper CS/DC/RST/BUSY, SD MISO/CS, button signals, MENU, and both dividers all
solder **direct to the XIAO** now, no board hole at all) and (2) settling button
debounce in **firmware**, not hardware (no RC caps on the board).

| Item | Count | Note |
|---|---:|---|
| XIAO header pins with a REAL stub leg into the board | 4 | GND, 3V3, D8/SCK, D10/MOSI only — the shared nets |
| XIAO header pins, reference position (no board hole) | 10 | D0,D1,D2,D3,D4,D5,D6,D7,D9 + the 5V pad — wire direct to their destination |
| Castellation/underside flying wires that touch a board hole | 0 | VBAT, ADC_BAT, MENU are all direct-to-XIAO now |
| Module leads landing on the board (shared-bus consumers only) | 12 | DISP: SCK/MOSI/VCC/PWR/GND (5); SD: SCK/MOSI/VCC/GND (4); 3× button GND legs (3) |
| Direct-to-XIAO leads (no board hole at all) | 13 | DISP CS/DC/RST/BUSY, SD MISO/CS, 3× button signals, MENU, 5V + D2 (VBUS-sense), VBAT + ADC_BAT (battery divider) |
| On-board parts | 1 | `C-BULK` only (bridges the GND/3V3 rails directly) |
| Off-board parts (built inline near the XIAO, not on this board) | 3 | `R-BAT` (fully off-board), `R-VBUS-T`/`R-VBUS-B` (off-board except one GND tap) |
| Board wires (board hole to board hole) | 5 | GND/3V3 rail feeds, SCK/MOSI fan-out feeds, the VBUS-sense divider's one GND tap |
| Buses (GND rail, 3V3 rail, SCK + MOSI fan-outs) | 4 | bare-wire, soldered at every hole they pass |
| **Holes actually used** | **60 (16%)** | of 386 usable — see the generator's own "Holes used" summary line |

**26 × 17 holes = 442 pads**, minus 56 lost to the notch = **386 usable** —
over 6× the current requirement. That headroom is deliberate: on an
isolated-pad board, crowding is what causes accidental bridges, and spare pads
are free. (It's also simply more than needed now that most signals bypass the
board entirely — the board was originally sized for a much busier population.)

**Why not smaller?** The old `CLAUDE.md` layout allotted the logic board
~67 × 29 mm, but check the portrait envelope: HAT 30.5 + battery 30 + logic 43
= 103.5 mm of parts, ~115 mm with gaps, inside 126.38 mm of glass height.
**There is ~22 mm of vertical slack**, so the 29 mm figure was conservative
packing, not a constraint. Spending some of it on hand-wiring room is the right
trade.

**Why not wider than 66 mm?** Drawing it to scale settled this: the board must
hide under the 71.19 mm glass, so 66 mm leaves ~2.6 mm clearance per side.
68 mm (27 holes) left only 1.6 mm — too tight to be worth 17 extra pads.

- **Minimum viable** if you'd rather keep the original envelope: 26 × 12 holes
  ≈ 66 × 30.5 mm (~252 pads less the notch ≈ 189). Workable, tighter routing.
- **Recommended: 26 × 17 holes ≈ 66 × 43 mm.** Cut from a 7×9 cm or larger stock
  board.
- Enclosure drawings are regenerated from these numbers by
  `enclosure/layout_generator.py` — edit its `PARTS` dict and re-run.

### Cutting the board

- [ ] Score deeply along a hole row both sides with a knife against a steel rule,
      then snap over a table edge; or cut with a razor saw. **Wear a mask** —
      FR-4 dust is glass fibre. Deburr with a file.
- [ ] Cut **before** soldering anything.
- [ ] The stock corner M2.5 mounting holes are lost when the board is cut down —
      plan new hole positions (or bond to enclosure bosses) at layout time.
- [ ] Cut the USB-C end so the connector overhangs flush with the board edge.

### Solder order

Access is the constraint: anything under the XIAO footprint is unreachable once
the XIAO is down.

1. **Dry-fit first.** Push the XIAO's pads onto the grid and confirm both 7-pin
   rows land on holes before committing to a layout.
2. **All four flying wires** (VBAT, ADC_BAT, VBUS_S, MENU) to the XIAO's
   castellation pads — tin the pad, tin the wire, join. Do these **off-board,
   before the XIAO goes anywhere**; they are unreachable afterwards.
3. **Any wire routed under the XIAO footprint**, flush.
4. **Rails** (GND, 3V3) — see the bus technique below.
5. **Passives** — the two divider pairs. Reuse the cut-off resistor legs as
   jumper wire.
6. **Off-board module leads** (panel HAT, storage, buttons).
7. **The XIAO last** — it's the heat-sensitive, hardest-to-remove part.
8. **Strain-relieve** every flying lead and the USB-C end with a bead of hot
   glue or epoxy after testing. Kapton tape under the FPC/HAT fold.

### Making nets on an isolated-pad board

Four techniques; use each where it fits.

| Technique | Use for | Notes |
|---|---|---|
| **Insulated 30 AWG Kynar, point-to-point** | Every signal | Default choice. Low profile, cannot short against neighbours, self-documenting if you colour-code. Strip 2 mm, pre-tin. |
| **Bare solid tinned copper (0.4–0.6 mm) threaded through a hole row** | GND / 3V3 rails | Best rail method: lay the wire along a row on the component side, solder each pad it passes. Gives you the ProtoMate's D/E buses back, deliberately. |
| **Solder-bridging adjacent pads** | Short 2–4 hole fan-outs (shared SCK/MOSI) | Tempting but the weak option — solder-only bridges crack, and hairline breaks are near-invisible. Never bridge more than ~4 pads; prefer a bare-wire run. |
| **Component leads as jumpers** | Divider taps, anything <10 mm | Free, stiff, flat. |

### Iron and consumables

- **Chisel/bevel tip, 1.5–2.4 mm** — not a fine conical. Plated-through holes
  wick heat; a needle tip gives cold joints.
- **~350 °C**, leaded 60/40 rosin-core 0.7 mm if you have it (much more forgiving
  than lead-free here). A **flux pen** on oxidised pads.
- Heat pad **and** lead together ~1–2 s, then feed solder; these holes drink
  solder, so feed sparingly or it wicks through and blobs the far side.
- Keep the tip tinned and wipe often — most "bad protoboard" is a dirty tip.

### Verify before power

- [ ] **Continuity-check every net** against your layout drawing with a meter.
- [ ] **Then check for shorts**: every rail against every other rail, and
      adjacent pads along each bridged run. Large pads on 2.54 mm pitch make
      accidental bridges easy and invisible under flux residue — clean with IPA
      and inspect under light/magnification.
- [ ] Confirm GND and 3V3 aren't shorted **before the battery is anywhere near
      the board**.
- [ ] Power from USB first, current-limited if you can.
- [ ] **Re-run Phases 1–3 on the soldered board.** A rewire found now is rework;
      found after the enclosure it's a rebuild.

### The layout — DONE

`hardware/protoboard_build_sheet_generator.py` → `hardware/protoboard_build.pdf`
(4 sheets: Front, Back, Wiring lists, Reference). Coordinates are cols A–Z ×
rows 1–17, holes written hyphenated (`G-14`) so they can't be confused with net
names like `D10`. Full details in `hardware/README.md`.

**Do not solder from `protomate_build.pdf`** — every hole coordinate in it assumes
buses this board does not have.

The generator's validator runs on every invocation and covers `offboard`,
`route`, `crossnet`, `reach`, `short`, `crowd` — all six fault-injection tested.
The `route` check exists because the first layout ran three wires straight across
the notch void; the notch means rows 10–17 only exist in cols A–I and Q–Z, so
cross-board wires must be dressed above row 10.

Before cutting, settle the two open items on Sheet 4: the **XIAO side/direction**
assumption (`FLIP_SIDE_A/B`) and the **VBUS-sense pin**.

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

Oasis-style grip spine, portrait (`enclosure/ereader-case.sc`, v7; see
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
2. **VBUS-sense pin** — Phase 0 above; digital-presence detection is the
   recommendation.
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
- **Protoboard layout + net list** (blocks Phase 5) — either retarget
  `hardware/protomate_build_sheet_generator.py` to an isolated-pad grid or draw
  it by hand. Also decide the board cut size, the XIAO-cutout question, and new
  mounting-hole positions.
