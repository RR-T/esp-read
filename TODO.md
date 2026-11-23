# TODO

These are the remaining open items. Bring-up phases and firmware tooling
are tracked in [docs/bring-up-and-assembly.md](docs/bring-up-and-assembly.md)
(§Open decisions, §Tooling that needs writing). This list covers everything
not already tracked there.

## Enclosure (`enclosure/ereader-case.sc`, v7)
- [ ] **Right-edge retention.** The glass is 0.2 from the right wall, so
      there's no room for hooks. Choose a tongue-and-groove seam between
      the tub and the front plate, or glue.
- [ ] **Grip-pad recess** on the back of the spine (agreed in principle,
      not modelled).
- [ ] **Test coupons** to print before the full case: power-switch slot
      and recess, living hinge (PP, 0.35 web), key cap and cradle fit,
      magnet and steel-disc pull, light-pipe press fit.
- [ ] **Update `enclosure/drawings/layout_generator.py` to v7.** It still
      draws the v1/v2 layout.
- [ ] Check the XIAO pin and castellation positions, and the storage
      board's pad end, against the real boards. The wire slots are
      deliberately long to tolerate this.
- [ ] Decide on the switch knob: file 0.3 off the tip for a flush fit, or
      leave it slightly proud in its recess.
- [ ] Optional hall sensor: choose a low-sensitivity part, or calibrate the
      threshold. The stowed cover magnet is ~4.4 away, versus ~2.1 when
      closed.

## Wiring / pins
- [ ] **Menu key pin.** GPIO42 (D11/D15) isn't an RTC GPIO, so it can't
      wake the device. Move the menu key to D17–D19 (GPIO13/12/11) and
      update CLAUDE.md's pin table and the firmware.
- [ ] Assign a castellation for the optional hall sensor (D17–D19) and for
      VBUS sense.
- [ ] At assembly: trim the key-switch legs to 2.4 and the power-switch legs
      to 0.5. The battery+ route goes through the power switch (see
      `enclosure/MEASUREMENTS.md` §v7 additions).

## Housekeeping
- [ ] The protoboard has been **dropped** for direct wiring in the case.
      Retire or rework `hardware/*_build_sheet_generator.py` and the
      protoboard tasks in the bring-up guide.
- [ ] Consider Git LFS for `*.sc` if the repo history grows too large
      (each model save is ~5 MB).
