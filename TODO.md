# TODO

These are the remaining open items. Bring-up phases and firmware tooling
are tracked in [docs/bring-up-and-assembly.md](docs/bring-up-and-assembly.md)
(§Open decisions, §Tooling that needs writing). This list covers everything
not already tracked there.

## Enclosure (`enclosure/ereader-case.sc`, v8)
- [ ] **Right-edge retention.** The glass is 0.2 from the right wall, so
      there's no room for hooks. Choose a tongue-and-groove seam between
      the tub and the front plate, or glue. Leaning tongue-and-groove so
      the case can still be opened.
- [ ] **Grip-pad recess** on the back of the spine (agreed in principle,
      not modelled).
- [ ] **Test coupons** to print before the full case. The power-switch
      track and slide caps are done (`enclosure/print/`). Still to make:
      living hinge (PP, 0.35 web), key cap and cradle fit,
      magnet and steel-disc pull, light-pipe press fit.
- [ ] **Update `enclosure/drawings/layout_generator.py` to v8.** It still
      draws the v1/v2 layout.
- [ ] Check the XIAO pin and castellation positions, and the storage
      board's pad end, against the real boards. The wire slots are
      deliberately long to tolerate this.
- [x] Switch knob: settled with a PSP-style slide cap that press-fits onto
      the knob (v8). Print the three socket sizes in `enclosure/print/` and
      keep the one that grips best.
- [ ] Optional hall sensor: choose a low-sensitivity part, or calibrate the
      threshold. The stowed cover magnet is ~4.4 away, versus ~2.1 when
      closed.

## Wiring / pins
- [x] Menu key moved to D17/GPIO13 so it can wake the device. The hall
      sensor takes D18/GPIO12 and VBUS sense D19/GPIO11, all wake-capable.
      Pin table, build guide, bring-up doc and simulator updated. No
      production firmware exists yet, so nothing else to change.
- [ ] Confirm D17-D19 = GPIO13/12/11 against the pinout card that comes
      with the XIAO before soldering.
- [ ] At assembly: trim the key-switch legs to 2.4 and the power-switch legs
      to 0.5. The battery+ route goes through the power switch (see
      `enclosure/MEASUREMENTS.md` §v7 additions).

## Housekeeping
- [ ] The protoboard has been **dropped** for direct wiring in the case.
      Retire or rework `hardware/*_build_sheet_generator.py` and the
      protoboard tasks in the bring-up guide.
- [ ] Consider Git LFS for `*.sc` if the repo history grows too large
      (each model save is ~5 MB).
