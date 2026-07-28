# Board layout — plain protoboard (current) + ProtoMate (superseded)

## Current build: `protoboard_build_sheet_generator.py` → `protoboard_build.pdf`

**Plain double-sided 2.54 mm protoboard, cut to 26 × 17 holes (~66 × 43 mm), with
an edge notch so the XIAO sits in-plane.** This is the build to solder from.

```bash
python3 protoboard_build_sheet_generator.py      # needs reportlab
```

Edit the data model (`SIDE_A`/`SIDE_B`, `BUSES`, `LEADS`, `WIRES`, `WAYPOINTS`,
`PARTS`, `CASTELLATIONS`) and re-run — it revalidates and re-renders the 4 sheets:
Front (component side), Back (14 wires), Wiring lists, Reference.

**Coordinates:** cols A–Z left→right, rows 1–17 top→bottom, holes written
hyphenated (`G-14`) so they can't be confused with net names like `D10`. The notch
removes cols J–P, rows 10–17.

**Three connection mechanisms**, since no hole is connected to any other:

| Mechanism | Used for | Count |
|---|---|---|
| **Bus** — bare tinned copper threaded along a hole row, soldered at every hole | GND rail (row 2), 3V3 rail (row 3), shared SCK/MOSI fan-outs (rows 5/6) | 4 |
| **Wire** — insulated 30 AWG Kynar, point to point | everything else | 14 |
| **Part legs** — a component bridging two holes | 3 dividers + bulk cap | 4 |
| **Stub legs** — 26 AWG into the XIAO's pads, bent 90°, into the landing pads | XIAO ↔ board | 14 |
| **Flying wires** — to the XIAO Plus SMD castellations | VBAT, ADC_BAT, VBUS_S, MENU | 4 |

Recreating the rails as buses is what keeps the insulated-wire count down to 14.
Holes used: 65 of 386 usable (17%) — deliberately uncrowded.

### Validator (warn-only, printed on every run)

| Check | Catches |
|---|---|
| `offboard` | a hole off-grid or inside the notch |
| `route` | a wire or bus crossing the notch void (rows 10–17 exist only in cols A–I / Q–Z) |
| `crossnet` | one node carrying two nets — a short |
| `reach` | a lead or part leg that doesn't connect to its net's source |
| `short` | a multi-leg part with both legs on one node |
| `crowd` | more conductors in a hole than it can take (limit 2, or 3 where `COLAND` says a junction is intended) |

All six were fault-injection tested. `route` earned its place immediately: the
first layout ran three wires (5V feed, SCK, MOSI) straight across the notch void,
which is why `WAYPOINTS` now dresses them around above row 10.

### Open before cutting

- **XIAO pad sides/direction are UNVERIFIED** — which physical row is side A, and
  whether side B runs the same top→bottom. Dry-fit, measure the row-to-row
  spacing (expect 12.7 mm), check against the silk, then flip `FLIP_SIDE_A/B`.
- **VBUS-sense pin still open** — ADC1 is GPIO1–10 only and ADC2 is dead while
  WiFi is up, so a high-numbered castellation can't do analog. Prefer digital
  presence sense, or `D2`/GPIO3 (hole `I-16`, the free ADC1 pin, with a
  strapping-pin caveat).
- **Board R10 value** — confirm before trusting it as the battery divider's lower leg.

---

# ProtoMate-for-XIAO board layout (historical)

> ## ⚠️ SUPERSEDED (2026-07-28)
>
> The build moved to a **plain double-sided 2.54 mm through-hole prototyping
> PCB, cut to size** — for lower Z and free placement. **Do not solder from
> `protomate_build.pdf`:** every hole coordinate in it assumes ProtoMate
> continuity (row strips `ABC`/`FGH`, split buses `Dlo/Dhi`/`Elo/Ehi`,
> Column I = the XIAO pads). A plain protoboard has **zero continuity — every
> hole is an isolated plated pad**, so the ~7-jumper plan becomes ~25+
> point-to-point wires and the layout must be redone.
>
> Still valid and worth keeping from this document: the **pin-conflict
> resolutions** (§conflicts — battery divider, VBUS-sense vs RST, menu button),
> the **divider values**, and the **shared-SPI build rule**. The generator's
> union-find net validator is also worth retargeting rather than discarding.
>
> Current build technique: `docs/bring-up-and-assembly.md` §Phase 5.
> Note the flying-wire/castellation distinction below is now moot — nothing on a
> plain protoboard is pre-routed, so all pins are equally reachable.

Perfboard layout + build sheet for the DIY e-reader, mounting a **Seeed XIAO
ESP32-S3 Plus** on a [ProtoMate for XIAO](https://thepihut.com/products/protomate-for-xiao).
Ported from the pico-deploy build-sheet generator (continuity model + union-find
validator + multi-page PDF).

**Direct-solder build (no JST connectors — Z-height constrained).** Off-board
modules (e-paper HAT, microSD, buttons) have flying leads that solder **directly**
into their target hole. Rear jumper traces are minimised to **7 total**: a lead
that only needs a GPIO solders straight into that XIAO pad on Column I (zero
jumpers); only the shared SPI lines and the GND/3V3 rails get short, straight
break-out jumpers.

## Files

- `protomate_build_sheet_generator.py` — the generator. Edit the data model
  (`XIAO_I`, `LEADS`, `PARTS`, `CASTELLATIONS`, `JUMPERS`), run it, and it
  re-validates + re-renders the PDF.
- `protomate_build.pdf` — 4 sheets: Front (solder map), Back (7 jumpers),
  Solder map + wiring list, Reference (Column I pad map + parts).

Regenerate: `python3 protomate_build_sheet_generator.py` (needs `reportlab`).
The validator is **warn-only** — it prints issues and still writes the PDF.

## Board continuity model (this project's coordinate system)

Rotated 90° from the Pi Hut product photo. 9 columns A–I × 14 rows:

| Cols | Continuity | Node |
|------|-----------|------|
| A B C | each **row** is one 3-hole strip | `ABC1`…`ABC14` |
| D | vertical bus, **split** at 7/8 | `Dlo` (1–7), `Dhi` (8–14) — used as **GND** |
| E | vertical bus, **split** at 7/8 | `Elo` (1–7), `Ehi` (8–14) — used as **3V3** |
| F G H | each **row** is one 3-hole strip | `FGH1`…`FGH14` |
| I | each hole is its own node = one **XIAO pad** | `I1`…`I14` |

Rails are fed from a XIAO pad into the low half (`I1→D1`, `I3→E3`) and jumpered
across the split (`D7→D8`, `E7→E8`) so both halves are live. Consumers tap the
nearest free bus hole on their own row.

## Column I = the XIAO pads (fixed by the board)

Top→bottom is the product-photo header left→right:

| Row | Silk | XIAO | GPIO | esp-read function |
|-----|------|------|------|-------------------|
| I1 | G | GND | — | Ground |
| I2 | 5v | 5V | — | VBUS (dead on battery; VBUS-sense tap) |
| I3 | 3v | 3V3 | — | Peripheral power |
| I4 | 0 | D0 | GPIO1 | E-paper CS |
| I5 | 1 | D1 | GPIO2 | E-paper DC |
| I6 | 2 | D2 | GPIO3 | **SPARE** (strapping pin) |
| I7 | 3 | D3 | GPIO4 | E-paper RST |
| I8 | 9 | D9 | GPIO8 | SPI MISO (SD) |
| I9 | 8 | D8 | GPIO7 | SPI SCK (shared) |
| I10 | 10 | D10 | GPIO9 | SPI MOSI/DIN (shared) |
| I11 | RX | D7 | GPIO44 | SD CS |
| I12 | TX | D6 | GPIO43 | E-paper BUSY |
| I13 | SDA | D4 | GPIO5 | Button: page fwd / wake |
| I14 | SCL | D5 | GPIO6 | Button: page back |

## Conflicts with CLAUDE.md §8, and how they were resolved

The ProtoMate only breaks out the **14 standard XIAO pads**. The locked pin plan
uses two signals that live on the ESP32-S3 **Plus castellations**, plus one
double-booked pin. Resolutions (confirmed with the owner):

1. **Battery divider (GPIO10 / ADC_BAT)** — not on the 14-pad breakout. Arrives
   as a **flying wire** from the Plus castellation. Only the **upper 220 kΩ** is
   on-board (`R-BAT`, G10↔G11); the board's own **R10 (220 kΩ)** is the lower
   leg. Tap → ADC_BAT.
2. **VBUS-sense vs E-paper RST (both on D3/GPIO4)** — real collision. **RST stays
   on D3/I7; VBUS-sense moves to a spare ADC1 castellation** (flying wire).
   Divider `R-VBUS-T`/`R-VBUS-B` taps VBUS(5V, `I2`) → sense → GND.
3. **Menu button (GPIO42 / D11)** — Plus castellation, kept there as CLAUDE.md
   specifies (RTC-capable). Flying wire from the pad to the button signal leg.

Net effect: **D2/GPIO3 (I6) stays a true spare.** Three signals never touch
Column I — they are flying wires to the Plus edge pads (see the "Castellation
flying wires" group on the wiring list).

> ⚠️ Divider values: both dividers are drawn as 220 kΩ (÷2). 5 V→2.5 V is inside
> the 3.3 V ADC range, so 220 k/220 k is fine for VBUS-sense too; swap if you
> want a different scale. Confirm the board's R10 value in situ before relying
> on it as the battery lower leg.

## Solder map (direct solder, no connectors)

Every module lead solders straight into one hole — see Sheet 1 (visual) and
Sheet 3 (per-lead table). Highlights:

- **Direct to Column I** (zero jumpers): DISP CS→I4, DC→I5, RST→I7, BUSY→I12;
  SD MISO→I8, CS→I11; BTN-FWD→I13, BTN-BACK→I14; VBUS 5V tap→I2.
- **Shared SPI** lands on fan-out strips: SCK→FGH9, MOSI→FGH10 (display + SD
  leads both solder to the strip).
- **Rails**: every GND lead → col D bus, every 3V3 lead → col E bus. PWR is
  hardwired to 3V3 alongside VCC.
- **VBUS-sense divider** `R-VBUS-T`/`R-VBUS-B`: 5V(I2) → tap(FGH2) → GND(FGH1).
- **Battery divider** `R-BAT`: VBAT(FGH4) ↔ ADC_BAT(FGH5), both castellation
  flying wires; board R10 is the lower leg.
- Cols A–B–C are unused = free prototyping space.

## The 7 rear jumpers (Sheet 2)

| Net | From → To | Why |
|-----|-----------|-----|
| GND | I1 → D1 | feed the GND bus |
| GND | D7 → D8 | bridge the 7/8 split |
| 3V3 | I3 → E3 | feed the 3V3 bus |
| 3V3 | E7 → E8 | bridge the 7/8 split |
| SCK (D8) | I9 → H9 | fan a shared pad out to a strip |
| MOSI (D10) | I10 → H10 | fan a shared pad out to a strip |
| GND | I1 → H1 | GND to the VBUS-sense divider bottom |

Plus 4 castellation flying wires (VBAT, ADC_BAT, VBUS_S, MENU) — inherent to the
Plus edge pads, not board jumpers.

Shared-SPI build rule (from CLAUDE.md): init the **SD first**, drive both CS
lines HIGH at startup, never start an SD transfer mid-refresh (wait on BUSY).
