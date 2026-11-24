# TODO

These are the remaining open items. Bring-up phases and firmware tooling
are tracked in [docs/bring-up-and-assembly.md](docs/bring-up-and-assembly.md)
(§Open decisions, §Tooling that needs writing). This list covers everything
not already tracked there.

## Enclosure (`enclosure/ereader-case.sc`, v9)
- [x] Right-edge retention: a hidden hook lip along the whole right edge
      (v9, case now 0.8 wider). Print a short test piece of the joint before
      the full case.
- [x] Spine grip pad: a flush TPU pad, no recess needed (v9).
- [x] **Test pieces** to print before the full case are all in
      `enclosure/print/` (cover flex lines in PETG, magnet pull, keys,
      light pipes, hook joint, power switch). See "Test pieces to print
      first" in `enclosure/README.md`.
- [ ] Print the test pieces and adjust from what they show.
- [x] `enclosure/drawings/layout_generator.py` now reads every size from the
      model, so the drawings can't go stale. Re-run it after model changes.
- [x] Boards held down properly (v9): XIAO end stops and snap lips, HAT
      right-side shoulders, longer pins on the HAT and storage board for a
      glue dab, battery hold-down ribs.
- [x] Soft support behind the display: 0.4 soft foam squares on printed
      landing pads (v9).
- [ ] Re-export `print/switch-track-coupon-rN.stl` if the top edge changes again
      (v9 didn't touch the switch mount).
- [ ] Check the XIAO pin and castellation positions, and the storage
      board's pad end, against the real boards. The wire slots are
      deliberately long to tolerate this.
- [x] Switch knob: settled with a PSP-style slide cap that press-fits onto
      the knob (v8). Print the three socket sizes in `enclosure/print/` and
      keep the one that grips best.
- [x] Optional hall sensor: TI TMAG5131-Q1, 15 mT version, with an N35
      cover magnet (not N52). Worked out in `enclosure/MEASUREMENTS.md`.
      Still to check on the real case: the stowed cover must not trigger it.

## Wiring / pins
- [x] Menu key moved to D17/GPIO13 so it can wake the device. The hall
      sensor takes D18/GPIO12 and VBUS sense D19/GPIO11, all wake-capable.
      Pin table, build guide, bring-up doc and simulator updated. No
      production firmware exists yet, so nothing else to change.
- [ ] Confirm D17-D19 = GPIO13/12/11 against the pinout card that comes
      with the XIAO before soldering.
- [ ] At assembly: trim the key-switch legs to 1.9 and the power-switch legs
      to 0.5. The battery+ route goes through the power switch (see
      `enclosure/MEASUREMENTS.md` §v7 additions).

## Housekeeping
- [x] Protoboard retired. The old build sheets are in `hardware/archive/`,
      `hardware/README.md` is now a direct-wiring list, and the bring-up
      guide's Phase 5 covers wiring in the case.
- [x] 22uF bulk capacitor: lies in printed saddles beside the HAT (v9).
- [ ] Buy 150k resistors for the USB-sense divider (changed from 220k so
      the pin reliably reads high; see `hardware/README.md`).
- [ ] Consider Git LFS for `*.sc` if the repo history grows too large
      (each model save is ~5 MB).
