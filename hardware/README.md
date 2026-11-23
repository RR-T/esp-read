# Wiring list (direct wiring in the case)

There is no logic board any more. Every part is wired straight to the XIAO
with 30 AWG Kynar wire, and the case's channels, slots and tabs hold the wires
in place (see `enclosure/MEASUREMENTS.md`, "v7 additions"). This list is the
build sheet: solder from it, then tick each wire off with a meter.

The pin plan itself lives in the pin table in `CLAUDE.md`. If the two ever
disagree, the pin table wins and this file needs fixing.

## Before you solder anything

- **Check the pinout card** that comes with the XIAO: D17, D18 and D19 should
  be GPIO13, 12 and 11. Fix the table below if not.
- **Do the underside pads first.** BAT+, BAT-, and the extra pads D11-D19 are
  on the XIAO's underside. Once the XIAO sits in its cradle they can't be
  reached, so wire them, sleeve them and route them clear before it goes in.
- **Shared pins carry two wires.** Where a pin feeds two parts (3V3, GND, SCK,
  MOSI), solder both wires into the same pad, or into the far part's pad as a
  daisy chain. Tin the pad, lay both wires in, then heat once.
- **Lay wires flat and trim every lead flush.** Loose loops eat the case's
  depth.

## Wires

Side "left" and "right" mean the XIAO seen from the front (top face forward,
USB-C up). Left-side wires drop into the left-wall channel; right-side wires
reach the storage board directly. Which physical edge carries D0-D6 is still
to be checked against the real board.

### Display driver HAT (9 wires, to the old PH2.0 pads)

| HAT pad | XIAO pin | GPIO | Notes |
|---|---|---|---|
| VCC | 3V3 | - | Shares the 3V3 pad with the storage board |
| GND | GND | - | The button ground chain also ends here |
| DIN | D10 | GPIO9 | SPI MOSI, shared with storage |
| CLK | D8 | GPIO7 | SPI SCK, shared with storage |
| CS | D0 | GPIO1 | |
| DC | D1 | GPIO2 | |
| RST | D3 | GPIO4 | |
| BUSY | D6 | GPIO43 | |
| PWR | D2 | GPIO3 | **Must go to D2, never to 3V3.** Firmware cuts panel power after every page (see "Panel protection" in `CLAUDE.md`) |

Set the HAT's interface switch to **4-line SPI** before fitting it.

**Bulk capacitor (22uF, 5 × 11 radial):** solder it across the HAT's VCC and
GND pads (+ to VCC). It lies in the two printed saddles just left of the HAT,
leads at the top end, and gets a dab of glue.

### Storage board (6 wires)

| Storage pad | XIAO pin | GPIO |
|---|---|---|
| VCC | 3V3 | - |
| GND | GND | - |
| MOSI / DI | D10 | GPIO9 |
| SCK / CLK | D8 | GPIO7 |
| MISO / DO | D9 | GPIO8 |
| CS | D7 | GPIO44 |

### Keys (4 wires)

| From | To | GPIO |
|---|---|---|
| Page forward, signal leg | D4 | GPIO5 (wakes the device) |
| Page back, signal leg | D5 | GPIO6 (wakes the device) |
| Menu, signal leg | D17 | GPIO13 (wakes the device) |
| Ground leg of each key | HAT GND pad | One wire chained key to key down the left channel |

Debounce is handled in firmware, so there are no capacitors on the keys.

### Battery and power switch

| From | To | Notes |
|---|---|---|
| Battery + | Power switch, middle leg | Up the left-wall channel, over the storage board (see `enclosure/MEASUREMENTS.md`) |
| Power switch, end leg | XIAO BAT+ (underside) | Back the same way, in under the XIAO's bottom end |
| Battery - | XIAO BAT- (underside) | Direct |

The switch cuts the battery from everything, so **the battery only charges
with the switch on**. That's fine for a storage cut-off, but worth knowing.

### Battery level divider (one resistor)

| Part | From | To |
|---|---|---|
| 220k resistor | XIAO BAT+ | GPIO10 (ADC_BAT) |

The XIAO's own R10 (220k) is the lower half. Measure R10 on the board before
trusting it.

### USB-present sense divider (two resistors)

| Part | From | To |
|---|---|---|
| Upper resistor, **150k** | XIAO 5V | Middle point |
| Lower resistor, **220k** | Middle point | XIAO GND |
| Wire | Middle point | D19 (GPIO11) |

**Values changed from 220k / 220k.** The pin reads this as a plain on/off
signal, and the ESP32-S3 only counts a pin as "high" above about 2.5 V.
220k / 220k gives 2.5 V from a perfect 5 V supply and less from a weak
charger, so it would miss some plugs. 150k / 220k gives about 2.8-3.1 V across
the normal USB range, comfortably high without going over 3.3 V.

Both dividers are built inline: solder the parts together, sleeve them in
heat-shrink, and lay them in the left-wall channel beside the XIAO.

### Optional cover sensor (3 wires)

| Sensor pad | To |
|---|---|
| VCC | Storage board VCC pad |
| GND | Storage board GND pad |
| OUT | D18 (GPIO12) |

The sensor is a TI TMAG5131-Q1, 15 mT version (why: `enclosure/MEASUREMENTS.md`,
"Hall sensor part"). Its post sits beside the storage board, so its power
comes from there rather than from the XIAO. Its output goes low when the
cover is closed.

### Antenna

Plug into the XIAO's U.FL socket; the cable runs through the clips between
the HAT and the storage board.

## Still open

- Check which physical edge of the XIAO carries D0-D6 (see above).

## Old build sheets

`archive/` holds the protoboard and ProtoMate build-sheet generators and
their PDFs. They are kept for reference only. **Don't solder from them:** they
predate the move to direct wiring, tie the panel's power straight to 3V3, and
put the menu key and USB sense on old pins.
