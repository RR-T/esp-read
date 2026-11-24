# Enclosure measurements (measured on the real parts)

Measured by the owner with calipers on 2026-11-22. **These numbers replace the
datasheet figures** in `CLAUDE.md` and in `layout_generator.py`'s `PARTS` dict
wherever the two differ. All values are in mm.

| Part | Measured | Notes |
|------|----------|-------|
| **Display panel (glass)** | 126.4 × 71.2 × **1.06** thick | Datasheet said 0.795 thick. No mounting holes, but has target marks where holes could be cut. **Will be glued to the front shell.** |
| Display visible window | **64 × 110** | Datasheet active area was 62.65 × 110.59. Size the bezel opening from this. |
| Display FPC | exits the **bottom** short edge | Confirmed 2026-07-28. |
| Display inactive border (glass edge → visible area) | **bottom (FPC edge) 11.5, top 3.75, right 4.2, left 4.0** | The visible area is therefore ≈ 63.0 × 111.15. Use these borders, not the 64 × 110 nominal, to place the window. |
| FPC bend allowance | **≥ 5** below the glass's bottom edge | For the fold back behind the panel. `bezel_bottom` = 9 leaves 7.5 inside the 1.5 wall, which is enough. |
| Display FPC (fixed to panel) | leaves from the **bottom edge, centred**, about **23 long** laid flat | It has to fold back to reach the HAT, so allow a sensible bend radius; don't crease it. |
| **Driver HAT** | 65 × 30.5, **6.6 total** | Mounting holes **Ø3.0** at **23 × 58 centre-to-centre**. Made up of: **3.5** of top-side parts (the connector to the ESP and the interface-config switch; these cover only a small area) + **1.7** PCB + **1.5** of chips on the underside. The FPC connector is removable and flush with the board edge. Long edge measured at **65.55**. **Top side (from photos):** the FPC ZIF connector sits at the middle of one long edge, the 9-pin PH2.0 wire connector at the middle of the other long edge, and the interface switch is near a corner hole. The tall parts are all in the middle third of the board. **Underside:** the tallest part is a shielded inductor in the middle (the square marked "K", ~1.5), next to a TSSOP chip and small SMD parts (lower). **The 2×20 Pi header along the PH2.0 edge will be desoldered.** |
| FFC extension adapter board | **32 × 18 × 3.6** | Joins the panel's FPC to the extension ribbon. The ribbon that came with it is **195 long**, much too long for the case, so a short one is needed. |
| **Battery** | 36 × 29.6 × **4.9** | Wires leave from the centre of a short (29.6) side; that end is **5.3** thick. |
| **Storage (2 GB flash module)** | 21.5 × 17.7 × **2.6** | 2 mounting holes **Ø2.5** along the long edge, **16.5** centre-to-centre. |
| **XIAO ESP32-S3 Plus** | 4.5 thick incl. USB-C + board, no wires soldered | Board 17.5 × 21.0 (datasheet). Wire exits add height (30 AWG Kynar ~0.3). |
| XIAO top-face layout | measured in top view, USB-C at the top | **Charge LED** 0.75 left of the USB-C port, 5 down from the connector's front. **User LED** in the mirror position, right of the port. **U.FL socket** at the bottom-left of the board. All on the top face. **RESET** sits 2 above the charge LED (left, outer side), **BOOT** 2 above the user LED (right), so ~3 down from the USB-C front. The underside has the BAT+/BAT− pads (bottom centre), a JTAG pad set, D+/D− and the extra castellations D11–D19. |
| U.FL antenna | cable leaves the **bottom** of the board, **75 long** (can be curved) | The element is a **20 × 40** sticker of negligible thickness. The cable is soldered to the middle of the element and runs along its long side. |
| **Buttons ×3** (KD TC-0120, The Pi Hut 6 mm slim) | body **6.0 × 3.5 × 3.6**, **4.3** to the top of the knob | Knob 3.1 × 1.7, sticks out 0.7. **Travel 0.25 ± 0.1** (very short). Through-hole legs 3.5 long, 0.3 thick, spaced 6.8–8.0. |

## CURRENT design: `ereader-case.sc` (v9 = v8 + firmer mounts, triangle ribs, print fixes)

v8 is kept as `archive/ereader-case-v8.sc`. Renders: `renders/v9-interior.png`, `renders/v9-bumpers.png`.

### Fixes from the third test prints (2026-11-24)
- **Slide cap now has a stem through the wall.** With the socket only in
  the cap, it held 1.2 of the switch's 2.0 long knob, which wasn't enough
  to stay on. The cap now has a square stem (`SwCapStem`, socket +
  2 × `stem_t` 0.6, so 3.05 square with the 1.85 socket) that passes
  through the wall and stops 0.15 (`stem_gap`) short of the switch body.
  The socket runs the full stem, so it grips **1.85 of the knob** (all
  but 0.15 of it; the knob can't give more).
  - **Knob slot widened** to 5.55 × 3.55 (`slot_h` 3.55 + 2.0 travel)
    with 0.6 round corners (`slot_r`), which leaves 0.2 round the
    largest (1.95-socket) stem. Its roof is a 5.55 bridge in the
    back-down tub print.
  - **Cap is bigger to keep the slot hidden** at both ends of the travel:
    **9.4 × 4.8** (was 7.0 × 3.8), still 1.85 thick and 0.95 proud. The
    track recess grows with it to 11.8 × 5.2 (X 21.85–33.65).
  - **Power switch 0.5 lower** (body Z 2.8–6.3, `sw_cz` 4.55) so the
    taller cap and track keep their top edge at Z 6.95 / 7.15, clear of
    the seam reveal. Pad, back lip, spacers and pins moved with it; the
    clamp is 1.55 tall (Z 6.3–7.85) and 0.6 narrower so it misses the
    wall pad.
  - **Wall pad** behind the track is now X 21.7–34.0, Z 1.0–6.85, so the
    longer track still has 0.7 of wall behind it.
  - **Print the cap face down** (as exported): the face on the bed, the
    stem growing up, so the socket is a plain vertical hole. Same three
    socket sizes, **1.75 / 1.85 / 1.95**.
  - Re-exported: the three `switch-cap-socket-*.stl`, `switch-cap.step`,
    `switch-track-coupon.stl`, `debug-tub.stl`, `debug-front.stl`.
    Collision check clean with the cap at both ends of its travel (known
    USB-C artifact only).

### Fixes from the second test prints (2026-11-23)
- **Key icons sagged over the knob pocket.** The pocket ceiling is a 2.1
  bridge directly under each icon. The three key switches and their
  pedestals are now another 0.2 lower (pedestal top Z 3.45, rails top
  4.45) and the pocket is 0.2 shallower (`knob_d` 0.45, ceiling Z 8.25),
  so the 0.5 of play is unchanged but there is now 1.05 of solid between
  the bridge and the icon floor (was 0.85). **Trim the key-switch legs
  to 1.9** (was 2.2): longer legs would now hit the 1.7 floor.
- **Slide cap socket can go bigger.** The cap is 0.4 taller (`cap_h` 3.8,
  was 3.4) so a larger socket still leaves about 0.9 of wall each side.
  To keep the cap's top edge (and the track recess) the same distance
  below the front-plate seam, the power switch moved **0.2 down**
  (body Z 3.3–6.8, knob centre `sw_cz` 5.05) and the cap grows 0.4
  downward (recess Z 2.95–7.15). The pad under the switch, knob slot,
  wall pad, spacers and clamp all moved with it (the clamp is 0.2 thicker
  to keep reaching the switch top). New caps: **1.75, 1.85, 1.95**
  sockets (1.85 in the model); the old 1.45–1.65 files are removed.
  Re-exported: `keys.stl`, the three `switch-cap-socket-*.stl`,
  `switch-cap.step`, `switch-track-coupon.stl`, `coupon-key-tub.stl`,
  `debug-tub.stl`. Collision check clean (known USB-C artifact and key
  ring squeeze only).
- **Seam between front plate and tub: shadow-line reveal plus a
  registration lip** (the flush butt joint showed every 0.1 of mismatch).
  - **Reveal:** a 0.4 × 45° chamfer on the tub rim's outer edge
    (`SeamRevealTub`) and 0.2 on the front plate's lower outer edge
    (`SeamRevealFront`) make a small V-groove all round at Z 7.8. Offsets
    hide in its shadow. The front plate's outer flat was only 0.4 tall
    (between this and the 0.8 face chamfer), hence the uneven split. The
    switch-cap recess (top Z 7.15) is clear of it. The USB-C slot's top
    (Z 7.55) dips 0.15 into the groove's lower face, which is hardly visible.
  - **Lip:** a 0.8 wide, 0.8 tall lip under the front plate (Z 7.0–7.8),
    0.15 inside the tub's inner wall face, along the left, top and bottom
    edges (`SeamLip*` features, joined into `Front` before the debug and
    coupon copies). It keeps the long edges from sitting in or out
    mid-span. It stops at X 84.9 on the right, where the hook tongue
    already locates the plate. Gaps: over the XIAO's USB-C receptacle
    (X 7.5–18), around the bottom-left cover magnet (X 23.5–26.5) and at
    the two snap arms (X 51–59, 76–86) so their roots still flex. No other
    part sits in that band (collision check clean against the tub and
    every REF part). The lip prints upward on the face-down front plate,
    no supports.
  - Re-exported: `debug-tub.stl`, `debug-front.stl`,
    `coupon-key-front.stl`, `coupon-key-tub.stl`, `coupon-light-pipe.stl`,
    `coupon-snap-tub.stl`, `coupon-snap-front.stl`, `hook-coupon-tub.stl`,
    `hook-coupon-front.stl`.
  - **Test piece:** `print/coupon-seam-corner-tub.stl` and
    `-front.stl` (bodies `COUPON_SeamTub` / `COUPON_SeamFront`, hidden) are
    the bottom-left corner (X 0-20, Y 0-20) of each part, full depth, at
    model coordinates. They include the real corner screw (insert boss in
    the front, clearance hole and counterbore in the tub), so one M2.5
    screw and insert hold them together. Print them the same way up as
    the full parts.

### Fixes from the first test prints (2026-11-23)
- **Power-switch pocket 0.3 deeper.** The switch's back (the leg side,
  facing into the case) was too tight. The back lip `SwBack` moved 0.3 into
  the case (now Y 130.5–131.0) and the end stops lengthened to match, so the
  pocket is 3.9 for the 3.6 body. The switch itself didn't move, so the knob
  still lines up with the slot. **At assembly, push the switch against the
  wall and put a small dab of glue between its body and the pad**, so the
  extra room doesn't let it move.
- **Slide cap grips 1.2 of the knob (was 0.8).** The cap is 0.4 thicker
  (`cap_t` 1.85) with a 1.25 deep socket (`sock_d`); its face stays where
  it was (0.95 proud), so the extra 0.4 goes into the case: the track floor
  is now 0.4 deeper (`rec_y` 135.6). To keep the wall solid behind the
  deeper track, a 0.6 pad (`SwWallPad`) fills the gap between the switch's
  front face and the top wall (Y 134.9–135.5, around the knob slot), so
  0.7 of wall is left behind the track. The switch, knob slot and clamp are
  unchanged. The cap prints face-up as before (now 1.85 tall).
- **Slide cap grooves simplified for printing:** two 1.0 wide, 0.35 deep
  grooves at ±2.0 (was four 0.6 grooves), leaving a 3.0 plain centre and a
  1.0 land at each end.
- **Storage board moved 0.6 down in all** (board Y 112.4–130.1, pins at
  Y 114.4), leaving 0.7 between it and the power switch's leg tips for the
  soldering iron and wires. It's still 1.4 clear of the HAT's top end, so
  the HAT didn't need to move, and the antenna cable still fits in that gap.
- **Keys: 0.5 of free play above each switch (was 0.1).** The keys pressed
  their switches as soon as the case closed. The key's knob pocket is 0.2
  deeper (`knob_d` 0.65), and the three switch pedestals are 0.2 lower
  (top at Z 3.65), so the switch knob tops sit at Z 7.95 against a pocket
  ceiling at 8.45. The TPU ring or foam on the key lip holds the key up
  across that play. **Trim the key-switch legs to 2.2** (was 2.4).
- **Keys stay put when the case is open.** Each pedestal now has two side
  rails (0.8 wide, 4 long, 1.0 above the pedestal top) that hold the switch
  body with 0.1 clearance each side. The legs leave from the ends, clear of
  the rails. Add a small dab of glue under each switch for a firm hold.
- **Key-top icons simplified and made to read as forward/back:** forward
  has one bold ">" pointing toward the screen, back has one "<" pointing
  away (each 2.8 × 4.4, about 1.0 stroke, 0.4 deep; was three thin
  chevrons pointing up/down the spine). Menu has a single round dimple
  (Ø2.2, 0.4 deep) instead of a ring.
- **HAT brace is solid full height and wider:** the bar now stands on the
  board all the way along (Z 5.05–6.8, was a 1.2 bar floating 0.6 above
  it) and is 5 wide (X 31–36, was 33–36), widened to the left only so it
  still clears the ZIF connector and interface switch. Wires can no longer
  pass under it: route any that cross the HAT around its ends (about 2 of
  board is free beyond each end). `print/hat-bridge.stl` re-exported.
- Collision check is clean (apart from the known USB-C block artifact and
  the key rings' intended 0.1 squeeze). Re-exported: `keys.stl`, the three
  `switch-cap-socket-*.stl`, `switch-cap.step`, `switch-track-coupon.stl`,
  `coupon-key-tub.stl`, `debug-tub.stl`. The front plate didn't change.

- **XIAO no longer rattles or gets pushed in by a USB-C plug.** Two end stops
  sit behind its bottom edge (0.1 gap) and take the push of a plug going in;
  the top wall already takes the pull coming out. Two small lips (0.2 over the
  board edge, 0.1 above it) on the right-hand posts snap over the board, to
  match the front-plate clamp on the left.
- **HAT right-hand side is now supported.** Before, only the left side was
  clamped and the right side floated on its pins. Its two floor pins now have
  Ø4.6 shoulders up to the PCB, and stand 1.0 proud of it. **Fix with a dab of
  hot glue on each pin top** (peels off for rework), or melt the tip over with
  a soldering iron for a permanent hold.
- **Storage board pins** stand 0.9 proud for the same glue dab.
- **Battery hold-down:** two ribs under the front plate stop 0.15 above the
  cell. Add a strip of 0.5 foam tape on top of the cell if it still moves.
- **Bulk capacitor (22uF, 5 × 11) has a home:** lying along the left side of
  the spine at X 3.8-8.8, Y 69-80, in two printed saddles, next to the HAT's
  wire pads. Leads at the top end, bent across to the HAT's VCC and GND.
  Body `REF_BulkCap`. Glue it into the saddles.
- **Ribbon bay above the adapter:** the grid behind the display now starts at
  Y 50.5 (was 31) and the channel's right rail starts there too, so there is
  a clear 22 mm bay across the whole width for the ribbon to leave the
  adapter and turn into the channel. The two lower magnet posts stand on
  their own in the bay.
- **Triangle ribs:** every grid cell behind the display now has an X brace,
  turning the squares into triangles. Diagonals stiffen the screen side
  against twisting, which is the main load when the device is held by the
  spine. The braces run through the upper magnet posts (pockets kept open).
- **Right-edge retention: hidden hook lip along the whole right edge.** The
  right wall is now **2.0** (parameter `sh_r`; the other walls stay 1.2), so
  the case is **92.9 × 136.6** (0.8 wider; the cover grows with it). Along
  the straight part of the edge (Y 4-132.6) the wall's top has a step on the
  inside, with a 45° underside so it prints without support either way up, and a notch 0.4 deep and 1.0 tall (Z 6.2-7.2) in its 0.9 outer
  skin, leaving 0.6 of wall above it. The front plate has a 0.9 tongue
  (Y 6-130.6, down to Z 6.4) that drops into the step, with a hook 0.6 tall
  that reaches 0.35 into the notch. Every gap in the joint is at least 0.15
  (0.2 above and below the hook), so a print that is a layer off still fits. From outside, the seam looks the same as before.
  - **To fit the front plate:** right edge down first, with the plate about
    0.4 to the left. Slide it right so the hook enters the notch, swing the
    spine side down, then fit the spine screws. The screws stop the plate
    sliding back, which keeps the hook engaged (at least 0.2 even with the
    screw-hole play).
  - **To open:** take out the spine screws, lift the spine side, slide the
    plate left and lift it off.
  - **Test piece:** `print/hook-coupon-tub.stl` and `print/hook-coupon-front.stl`
    are a 16 mm slice of the right edge (Y 62-78) from each part, at model
    coordinates. Print the tub piece rim-down and the front piece face-down,
    as the full parts will be, and try the slide-and-swing fit.
- **Print review (2026-11-23).** See "How to print it" in `enclosure/README.md`.
  Fixes made: hook-joint gaps opened from 0.05 to 0.15-0.2; light-pipe holes
  Ø1.6 to Ø1.8 (printed holes shrink, so Ø1.6 would grip a Ø1.5 pipe too
  hard); a flat print version of the cover (`PRINT_CoverFlatFinal`, hidden,
  parked 15 above the model; `PRINT_CoverFlat` is its working copy, so the
  two overlap in a clash check) since the stowed shape can't be printed flat.
  The flat cover has the tapered front edge on the bed side and the hinge
  grooves on top, as on the real cover.
- **Steel discs are sealed inside the cover** (no longer open pockets):
  0.2 of plastic, a 0.3 slot for the 0.3 disc, then 0.2 more. Print at 0.1 layers
  and pause at **0.5** (after the slot's last layer) to drop the five discs
  in; the next layers bridge over them. A dab of glue stick in each slot
  stops a disc sliding while the nozzle passes. The discs now sit 0.2
  further from the case magnets than before, a small loss of pull.
- **Chin magnet pair and steel disc moved from X 22.5 to X 25.0.** The
  disc's pocket overlapped the cover's tapered front edge and broke out
  through it. It now sits fully on the full-thickness part, and the case
  magnets keep 0.5 of wall to the S6 screw counterbore.
- **Cover hall-magnet hole is off by default** (`OPT_HallMagnetHole`
  suppressed), because the sensor is optional and the through-hole showed on
  the outside. If you fit the sensor, unsuppress `OPT_CovPrintHallPocket`
  and re-export the flat cover: a 0.5 deep pocket from the inside face,
  leaving 0.2 of plastic over the magnet so nothing shows. Print at 0.1 layers.
- **Foam support behind the display:** the grid, its braces and the magnet
  posts all stop at Z 6.8, 0.34 below the glass, with 5 × 5 landing pads at
  the 9 rib crossings and the 4 brace crossings. Stick a square of **0.4
  very soft closed-cell foam** (Poron-type) on each pad and a ring on each
  magnet post. 0.4 squashes by about 15%: enough to stop the glass buzzing
  and spread a squeeze, without pushing the front plate off the right edge.
  (0.5 foam would squash 32% and push about three times harder.)
- **XIAO front clamps moved to the board's corners.** The old clamp ran along
  the left pad row and would have pressed on the solder joints. The new
  clamps and the right-hand lips sit only on the bare 2 at each end.
- **Board clamps leave room for foam tape.** The front-plate columns that
  press on the boards (the two HAT shoulders on its left side and the two
  XIAO corner clamps) now stop 0.8 above the board instead of touching it.
  Stick a square of **1 mm foam tape** on each column end (punch a hole for
  the HAT pin), so the foam, not hard plastic, holds each board. The gap is
  one setting (`pcb_foam`); change it to suit thinner or thicker tape.
- **TPU bumpers under the cover.** Nine small TPU plugs (Ø2.5, 0.75 tall,
  rounded top) push into 0.4 deep sockets on the front frame and stand
  **0.35 proud**, so the closed cover rests on soft TPU rather than the
  frame. They sit in the middle of the flat part of each frame strip,
  about 3.5 from the outer edge: three along the chin and three along the
  top (X 45, 67.35, 89.7), and five down the right edge, evenly spaced
  including the two corners. Sockets over the glass edge leave 0.4 of
  plastic above the glass. None on the left: that frame strip is only 2.2
  wide beside the window, too narrow for a socket, and the cover's left
  edge is held by the chin magnet and its own seat. Print
  `print/tpu-bumpers.stl` in TPU (95A) and add a tiny drop of CA glue in
  each socket. The cover sits 0.35 further from the magnets (0.55 in all
  with the sealed discs); test the magnet coupon before the full print.
- **Key lips thinned for a soft top-out.** Each key's lip (the flange under
  the front plate) is now 0.4 instead of 0.6, leaving a 0.2 gap above it.
  Fill that gap with either option, and compare them on the key test piece:
  - **TPU rings** (`print/tpu-key-rings-0.3.stl` and `-0.4.stl`): one ring
    per key, sitting on the lip, squeezed 0.1 (0.3 version) or 0.2 (0.4
    version). They hold each key gently on its switch so it can't rattle,
    soften the tick as it springs back, and keep dust out. They don't add to
    the press force. Start with 0.3; use 0.4 only if the key still rattles.
  - **Foam:** a ring or a few dots of 0.4 soft foam on the lip instead.
  Neither stops a key tipping when pressed at one end. With one switch per
  key, the far end of the lip catching on the plate is already the best
  pivot this layout allows. End stops were looked at and rejected: any stop
  close enough to help would block the click on an end press.
- **Key tops have a texture you can tell apart by feel.** Forward has three
  small chevrons pointing up, back has three pointing down, and menu has a
  small ring. The grooves are 0.25 deep and 0.6 wide, matching the grip
  pad's chevrons. Render: `renders/v9-key-texture.png`.
- **Front plate stiffened where nothing sits below.** The plate is 1.0
  thicker (2.2 in all) under two strips: along the spine, between the keys
  and the screen edge above the HAT (X 11.6-19.1, Y 45-127.5), and along the
  chin between the chin magnet/screw and the far screw (X 33.5-83). Both
  keep clear of every part, insert hole and magnet pocket; the HAT still has
  1.8 of clearance above it for wires. Over the screen the plate can't
  thicken (it is the 0.8 lip on the glass). Thickness is one setting
  (`stiff_t`). **Print the front plate at 0.1 layers for the first 1 mm** so
  the face chamfers come out smooth rather than stepped.
- **Debug shell for test fitting.** `DEBUG_Tub` and `DEBUG_Front` (hidden
  in the model; `print/debug-tub.stl`, `print/debug-front.stl`) are copies
  of the shell with 13 viewing windows: four down the spine wall, three in
  the chin, three in the top and three down the right edge. Each runs from
  just above the floor to 0.6 into the front plate, so the glass edge shows
  alongside the parts below it. They avoid the corners, screw bosses,
  magnets, the power switch and the XIAO. They're copied from the real
  parts at the end of the timeline, so they pick up later changes.
  Render: `renders/v9-debug-shell.png`.
- **Cover now printed in PETG, not PP.** The cover isn't hinged to the
  case (magnets hold it); its two flex lines only bend about 6° so it can
  follow the back's curve when stowed. PETG copes with that once the
  grooves are wider: they are now **3.0 wide** (`hinge_w`, was 1.5) with
  the same 0.35 web, which halves the bending strain to about 0.6%. The
  first groove runs X 33-36, shifted toward the spine so it stays clear of
  the optional hall-magnet pocket at X 38.5; the second is centred on
  X 50.5. PETG avoids PP's bed-adhesion and warping trouble and matches the
  rest of the case. It is stiffer, so it springs back a little more; check
  with `print/coupon-cover-hinge.stl`.
- **Test pieces** (`print/coupon-*.stl`): the cover flex lines, magnet
  pull (a block with the real plastic gaps either side of a magnet stack,
  plus a cover slice with one sealed disc), the key spine section (front
  and tub halves, held by the upper spine screw), and the light-pipe
  corner. They are hidden `COUPON_*` bodies in the model, cut from the
  finished parts at the end of the timeline, so they follow later changes.
  How to use each one: `enclosure/README.md`, "Test pieces to print first".
- **Two snap catches hold the top edge.** The top edge had no fastening
  between the power switch and the right corner. A corner screw like the
  chin's won't fit: the glass runs to within 1.8 of the top wall inside, so
  there is no solid front plate to take an insert. Instead, two springy
  arms (6 wide, 0.8 thick, 4.25 long) hang from the front plate into that
  gap at X 55 and 80, each with a small catch that clicks 0.3 into a notch
  in the tub's top wall. The catch has a sloped lead-in, so it snaps in as
  the plate swings down, and an angled top, so it pulls free again when
  you open the case (no tool needed). Bending strain is about 2%, within
  what PETG takes repeatedly. The notches leave 0.85 of wall and are wide
  enough for the plate's 0.4 slide when the right-edge hook engages.
  - **Fitting** is unchanged; as the spine side swings down, press along
    the top edge until both catches click.
  - **Opening:** after the spine screws are out, lift the spine side
    firmly; the top catches pop free on their angled faces.
  - **Test piece:** `print/coupon-snap-tub.stl` + `print/coupon-snap-front.stl`,
    a 16 mm slice of the top edge around one catch. Press them together
    and pull apart a dozen times; the arm should click in cleanly, hold,
    and not whiten.
  The debug shell has the catches and notches too.
- **TPU grip pad on the spine.** A 0.55 TPU pad on thin double-sided tape
  (about 0.15) covers the spine's back from the palm round to where the
  stowed cover starts. Pad plus tape is 0.7, so it sits **flush with the
  stowed cover** and the back reads as one flat surface. No recess was cut:
  the spine's back sits 0.7 above the stowed cover already, and a recess
  would thin the 1.0 back wall and leave a bridged ceiling when printing
  back-down. It has a chevron groove pattern (0.2 deep, 3 mm pitch, pointing
  up the device) for grip. It hides the three spine screws (the chin
  screw at X 30 stays where it was, uncovered, under the stowed cover). The upper
  spine screw moved from X 6.5 to X 7.5, in line with the middle one, so its
  head is fully under the pad too. Peel the pad off to open the case. Print `print/tpu-grip-pad.stl` flat in TPU 95A, grooved
  face up.
- **Display support over the HAT.** The grid behind the display starts at
  X 56, so the glass had no back support over the HAT. A printed bridge
  (`print/hat-bridge.stl`, PETG) now slips over the two right-hand HAT floor
  pins once the HAT is in, so it also replaces the glue dabs there. Its bar
  runs down the HAT on the left of the ZIF connector and the interface
  switch, with a short arm out to each pin and a small column in the middle
  standing on the board. Its top is level with the foam lands (0.34 below
  the glass), so it takes the same 0.4 soft foam. The bar clears the board
  by 0.6 for the 30 AWG wires that cross it. **Check the column's foot
  lands on bare board** on your HAT, and trim it if not. Print it upside
  down (flat top on the bed). The strip between the HAT's edge and the grid
  (X 42-56) is the ribbon channel and is still unsupported.
- **Wire routes checked** with stand-in wires against the model; all clear:
  the left-wall channel, XIAO slots to the channel and to the storage board,
  the channel to the HAT pads (passing above the capacitor's end), the
  battery to the channel, the channel to the keys, under the XIAO to its
  BAT+ pad, and BAT+ over the storage board. Two need a detour:
  - **XIAO to HAT (right-side pins):** the HAT's top-left clamp blocks the
    straight line at X 14. Run down at X 18-19, right of the clamp, then
    across to X 14 at about Y 100 and down beside the guide fins.
  - **BAT+ from the channel to the XIAO:** the top spine screw post blocks
    the gap at the left. Leave the channel at about Y 106 (between the
    forward key and that post), go up beside the post at X 10-11, then
    across the gap.
- **Print fixes:** the slide cap's outer grooves left a 0.15 sliver at each
  end, so it now has four 0.6 grooves (at ±1.4 and ±2.5) with 0.5 lands and a
  0.7 plain end. The cover's front edge was a 0.2 feather (one layer); it is
  now 0.4, so the cover starts at X 20.4 (was 19.3).

## v8 (superseded by v9 only where v9 says so)

v7 is kept as `archive/ereader-case-v7.sc`. **v8 only changes the power switch
on the top edge:** a retro, PSP-style slide cap that press-fits onto the
switch knob and rides in a track, hiding the knob slot in both positions.
Render: `renders/v8-switch-cap.png`. Print files: `print/`.

- **Track:** the old 6 × 3 recess is now a **9.4 × 3.8 stadium, still 0.6
  deep** (the wall is only 1.2 here, so it can't go deeper). Its top edge
  stays 0.65 below the front-plate seam. The 3.9 × 1.9 knob slot through
  the wall is unchanged.
- **Cap (`SwCap`):** a **7.0 × 3.4 stadium, 1.45 thick**, with a 0.3 chamfer
  round the face and six 0.5 wide, 0.3 deep grip grooves either side of a
  plain centre. It clears the track by 0.2 at each end of its 2.0 travel
  and floats 0.1 off the track floor, so it never rubs. It stands **0.95
  proud** of the case edge. Darker colour in the model so it reads as a
  separate part.
- **Press fit:** a 0.85 deep square socket on the back fits the switch's
  1.5 square knob. The socket size is a parameter (`sw_sock`, 1.55 in the
  model). Printed holes come out small, so `print/` has caps at **1.45,
  1.55 and 1.65**: try them on the real switch and keep the one that grips
  firmly without splitting. A dot of CA glue is a fine backup.
- **Printing:** the cap STLs are already laid face-up (back on the bed, so
  the socket needs no support). Use 0.1 layers if you can, so the grooves
  come out crisp. `print/switch-track-coupon.stl` is a 20 mm cut of the
  case's top edge with the switch mount, to test the slide before printing
  the whole tub.
- This settles the old "file the knob flush or leave it proud" question:
  neither, the cap covers it.

## v7 (superseded by v8 only at the power switch)

v6 is kept as `archive/ereader-case-v6.sc`. **v7 changes only the back, the cover's
first segment and a few mounts:**
- **Back (X profile), one gradient only:** the spine's back plane is flat at
  **Z 0.7** from the palm round (R4) to X 35.5. It's then one **15 gradient**
  (X 35.5 → 50.5, R20 blends) to the **6.8 display section** (Z 2.2), flat
  to the right edge. The v6 ramp and seat are gone. **The bare spine is
  8.3 deep** (Z 0.7–9.0). The inner floor is at Z 1.7 under the spine
  (1.0 wall), set by the battery (Z 1.75) and the HAT underside (Z 1.8).
- **Cover:** segment **A** (X 19.3–35.5) now sits **on** the flat spine
  plane at Z 0–0.7, so **with the cover stowed the spine is exactly 9.0**,
  and nothing on the device exceeds 9.0. Its leading edge has the same
  bevel as the closed state: 0.5 → 0.7 at X 19.3, rising to full
  thickness by X 22.15. B and C, and the living hinges at X 35.5 / 50.5
  (1.5 wide, 0.35 web, about 6° flex each), are unchanged. Print it in PP.
- **Battery moved to X 3.6–33.2** (`bat_x0` 3.6, was 2.5) to keep ~1.0 of
  wall between its back-left corner and the palm round. The battery mounts
  (`BattPad`, `BattStopL/R`, `BattWallR`) now follow `bat_x0`.
- **Spine screw counterbores** (S7, S8, S1) start at Z 0.6 (1.9 deep from
  the new back plane). The washer face under each is 1.0 of boss.
- **Switch legs: trim to 2.4** (was 3.5 as supplied, modelled 2.8). The
  floor under the pedestals is now at Z 1.7.
- The collision check is clean, except the known USB-C artifact (square
  reference block against the slot's rounded ends).

### v7 additions: power switch and wiring (2026-11-23)
- **Power switch: SS12D01 vertical slide** (body 8.5 × 3.5 × 3.6, 1.5
  square knob, L = 2, 2.0 travel, 3 legs at 2.5 pitch). Body
  `REF_PowerSwitch`. It sits on the **top edge at X 23.5–32**, Y 131.3–134.9,
  Z 3.5–7.0, between the XIAO and the hall post, with the USB-C port beside
  it.
  - **Mount:** a pad below the body, end stops at X 22.7 / 32.0 that take
    the slide force, a back lip (Y 130.8–131.3, Z ≤ 4.5) under the legs, two
    0.5 spacer ribs against the wall, and `SwClamp` on the front plate on
    top.
  - **Knob opening:** a 3.9 × 1.9 slot through the wall, inside a
    6 × 3 stadium recess 0.6 deep. The knob tip ends 0.3 proud of the case
    edge (0.9 above the recess floor). File 0.3 off the POM knob if you
    want it flush.
  - **Legs: trim to 0.5** and solder the wires bent upward. Longer legs
    would hit the storage board's top end.
- **Battery-line route:** BAT+ from the battery runs up the left-wall
  channel (tabs at Y 54/76/95/124), across the gap between the XIAO and the
  HAT (Y 111–114.4), over the storage board (Z 5.3–7.1 is free) to the
  switch legs, then back the same way and in under the XIAO's bottom end
  to its underside BAT+ pad. BAT− goes straight to the XIAO.
- **XIAO side walls now have open wire slots:** Y 116.3–133.35,
  Z 2.9–4.4, both sides, so every edge pad can exit sideways whatever the
  exact pin pitch. Short locating posts stay at Y 115–116.3 and
  133.4–134.6. Left-side wires drop into the left-wall channel. Right-side
  wires reach the storage board directly.
- **Inline resistors** (both dividers), sleeved in heat-shrink, lie in the
  **left-wall channel** (X 1.2–3.1, beside the XIAO). The new `WireTab4`
  at Y 124 holds them.
- **XIAO → HAT:** an extra front-plate fin, `HatWireGuide4`, at
  (14.8, 111.6) bridges the gap between the XIAO and the HAT and continues
  the X 14.8 guide line.
- **Antenna cable:** the existing clip pairs at X 47 and X 60 (Y ~111)
  keep it in the gap between the HAT and the storage board.
- **Optional hall sensor moved** from the chin, where its wires would have
  run ~200 mm around the screw bosses, to a **post under the top glass
  border at (38.5, 132.9)**. The sensor sits at Z 5.9–6.9 (0.24 below
  the glass), ~20 mm of wire from the XIAO. Its cover magnet hole moved to
  (38.5, 132.9), clear of the X 35.5 hinge groove. With the cover stowed,
  the magnet is ~4.4 from the sensor, versus ~2.1 when closed.
- **Hall sensor part (chosen 2026-11-23): TI TMAG5131-Q1, 15 mT version
  (TMAG5131G1D)**, SOT-23, 1.65-5.5 V, about 1.4 uA average, push-pull output
  (low when it sees the magnet). It turns on between 12 and 18 mT and off
  between 6.4 and 10.4 mT. Worked out for the Ø4 × 0.5 cover magnet:
  **closed it sees ~26-40 mT** (well over 18, so it always triggers) and
  **stowed ~7-9 mT** (under 12, so it never triggers). The range allows for
  the sensing element sitting up to 0.6 below the package top. **Buy N35
  magnets, not N52:** an N52 disc gives ~11 mT stowed, too close to the
  12 mT trigger. The stronger 37 and 40 mT parts would need a thicker magnet
  than the 0.7 cover can hold. Check on the real case: the cover stowed must
  not trigger it.
- Menu key moved to D17/GPIO13 (2026-11-23); the hall sensor takes D18 and
  VBUS sense D19. Still open: right-edge retention, the grip pad, the
  remaining test coupons and `layout_generator.py`. See `TODO.md`.

## v6 (superseded): Oasis profile with a cover seat

v5 (single-plane back with a wedge cover) is kept as `archive/ereader-case-v5.sc`.
**v6 is 92.1 × 136.6.** Layout as in v5 (keys X 8, battery under the key
strip, HAT X 11.5–42, XIAO top-left), with a new back and cover:
- **Back (X profile):** spine plane Z 0 to X 18.15. A 4 ramp (R10 blends)
  leads into a **0.7 seat** (X 22.15–35.5) for the cover's first segment.
  Then a **15 gradient** (X 35.5 → 50.5, R20 blends) down to the **6.8
  display section**, flat to the right edge. The seat depth is capped at
  0.7 by the battery (bottom Z 1.75).
- **Hinged cover, 0.7 thick:** **A** is rigid (X 19.3–35.5, bevelled
  0.2 → 0.7 on the ramp), **B** follows the gradient, **C** covers the
  display back. **Living hinges at X 35.5 and 50.5** (1.5 wide grooves on
  the hidden face, leaving a 0.35 web), each flexing ~6°. Print it in a
  living-hinge material (PP is best). **Stowed and closed it keeps the
  Oasis shape: 9.0 at the spine → 7.5 over the display** (6.8 bare).
  `VIEW_CoverClosed` is the hidden flat/closed copy.
- **Magnets:** the cover has **steel discs** (Ø8 × 0.3; Ø5 at the chin) in
  0.35 pockets on its hidden face. The body has **4 stacks (Ø6 × 2 +
  Ø6 × 1.5)** in posts in the rib cells at (67/81, 40.25 / 100.25), each
  ~1.1 from the stowed cover and ~2.2 from the closed cover. There's also
  a **chin pair of Ø4 × 2** at (22.5, 4.1): one in the tub, one in the
  front plate.
- **Optional hall sensor** (features `OPT_HallMagnetHole`,
  `OPT_HallPocket`, body `OPT_HallSensor`): a Ø4 × 0.5 magnet glued in a
  through-hole in cover C at (75, 3.8), and an SOT-23 sensor in a pocket
  under the chin of the front plate. It's >30 from every body magnet, and
  it only sees the cover magnet when the cover is closed.
- **Light pipes:** bodies `LightPipeCharge` / `LightPipeUser` (Ø1.5, with
  half-moon flanges away from the pinholes), printed in clear PETG.
- **Right-edge hooks aren't possible**: the glass is 0.2 from the right
  wall. Retention there is a TODO (tongue-and-groove seam or glue).

## v5 (superseded)

v4 (two-slope back plus the hinged-cover option) is kept as
`archive/ereader-case-v4.sc`. **v5 is 92.1 × 136.6 × 9.0.**
- **Back: ONE plane.** Flat to X 6 (after the palm R4, with an R30 blend),
  then **1.46° straight to the right edge** (Z 2.2 there; the device is 6.8
  deep at the right edge). No recess and no steps. **Cover: a thin wedge**
  (0.41 → 2.2), stowed flush, so the device is a flat 9.0 slab. Closed, its
  outer face slopes gently. The hinged cover was dropped (a single plane
  gives it nothing to bend over).
- **Keys at X 8.0** (back / forward Y 87 / 101 = glass + 80 / + 94; **menu
  pill at Y 50**), on separate printed pedestals. The pedestals are 5.6
  long so the **switch legs drop straight down past each end** (trim them
  to ~2.5, leaving a solder/wire gap above the floor). Cradle posts start
  at Z 5.2 so they clear the HAT.
- **HAT X 11.5–42.0, Y 45.5–111** (1.5 from the key pedestals). **Battery
  X 2.5–32.1, Y 7.5–43.5**, under the key strip, with a 2 gap below the HAT
  for its wires, stop tabs and a pad.
- **Wire routes:** (1) switches and battery → XIAO along the channel by the
  left wall (tabs at Y 54 / 76 / 95). (2) HAT (old PH pads, left edge) →
  XIAO along the HAT's bare top-left strip, with 3 guide posts from the
  front plate at X 14.8. (3) The FFC from the adapter to the HAT ZIF runs in
  a 13 wide railed channel (X 42.3–55.8, Y 28.5–66). (4) Antenna cable
  clips at Y 110–112.
- **Screws (M2.5 ×5):** S7 (8, 4.15) and S6 (30, 4.15) chin left, S5
  (86.1, 4.15) chin right, S8 (7.5, 65), S1 (6.5, 111). The rib grid is split
  into segments whose bases follow the sloped floor.
- **Interference check is clean**, with the switch legs modelled (except
  the USB reference block's corners).

## v3 (superseded)

Earlier versions: `archive/ereader-case-v1.sc` (first flat) and `-v2.sc` (option B,
98.4 wide). **v3 is 92.1 × 136.6.** The spine is **9.0** deep (front-view
width ≈ 22.7 to the window) and the screen section 6.8. **Stowed and closed
it is an even 9.0 slab**: the cover's flat face is outward when stowed and
on the glass when closed.
- **Back profile (X):** palm R4 → spine plane Z 0 to X 22.15 (the cover's
  left edge) → **0.6 step** (the cover strip seat) → flat to X 43.6 → 12
  ramp to the recess at Z 2.2 (X 55.6) → recess to the right edge. The
  battery and HAT sit on the 1.6 floor under the cover strip, partly under
  the glass. **No HAT bump.**
- **Glass at X 19.5**, limited by the user-LED pipe at X 18.0. **Chin 7**
  (FPC fold 5 inside the wall), top bezel 3.2.
- **Keys at X 8.5, near the left edge, all on printed pedestals** (no
  longer over the HAT). Back / forward at **glass + 80 / + 94** (device Y
  87 / 101). **Menu is a short 4.5 × 7 pill** at Y 44; a round cap's
  cradle post hit the battery.
- **XIAO in the top-left corner** (X 4–21.5, USB-C centre X 12.75, Z 5.7).
  Column: battery Y 7.5–43.5, HAT Y 44–109.5 (X 13–43.5). Storage
  X 22.5–44, Y 113–130.7 (pins 25 / 41.5). Adapter X 44.5–76.5, Y 9–27.
  Antenna X 50–90, Y 113–133.
- **Screws (M2.5 ×5):** spine S7 (7.5, 20), S8 (7.5, 65), S1 (6.5, 111);
  chin S6 (30, 4.15) and S5 (86.1, 4.15). HAT: left pins with clamping
  shoulders from the front plate, right pins rising from the floor.
- **Weights (PETG, solid):** tub ≈ 22.7 g, front plate ≈ 7.5 g, cover ≈ 19 g
  (less with infill).
- **Interference check is clean** (except the USB reference block's corners).

### Previous refined-flat notes (v1 → v2, superseded)

The old flat model is kept as `archive/ereader-case-v1.sc`.
**UPDATE (option B, glass moved left):** the glass is at **X 25.8** (limited by
the user-LED pipe at X 24.3), so the **device is 98.4 × 138.6**. Battery and
HAT now sit under the left part of the glass. **The cover is rebuilt:** its
glass-side face is flat, with a 0.6 strip over the spine's back that ramps
to 2.2 over the recess. **Stowed and closed it is an even 9.0 slab**; bare it
is 8.4 at the spine and 6.8 at the screen. Because they'd be under the
glass, these were removed: the right-hand HAT shoulder pins (now **floor
pins** at X 30.55), screw S2, and the XIAO's right clamp. The case keeps 4
screws (S1, S3, S6 and S5, now at X 92.4). The HAT bump is narrowed to X
11.4–28.4. Storage is now X 29–50.5 (pins at 31.5 / 48) and the antenna
X 55–95. The ramp-cover notes below for 106 × 138.6 are superseded where
they differ.

Original refined-flat notes: **106.0 × 138.6 × 8.4**. The spine and the
stowed reading slab are both 8.4, and the screen section is 6.8. All
dimensions are SolidCraft parameters.
- **Back:** a palm round R4, then a **12 wide ramp** (X 32.35 → 44.35) into
  a 1.6 recess. **Cover: 1.6 thick, bevelled** across the ramp (0.4 → 1.6),
  stowed flush. Closed, the bevel faces outward. `VIEW_CoverClosed` is a
  hidden copy in the closed position. `OPT_CoverHinged` is the rejected
  hinge option, kept to show that its flap sticks out 1.6 at the ramp.
- **Plan corners R4** (an R6 corner clashed with the glass corner and XIAO).
  Top bezel 3.2, chin 9.
- **Key stack (8.4):** the switch knob sits in a 0.45 pocket in the cap,
  and the cap flange sits in a 0.6 recess in the front plate's underside.
  Switches are **rotated 90°** (6.0 along Y) so the cradles can grip their
  long sides without hitting the bent-out legs. Keys from the device's
  bottom: back 93.5, forward 107.5, menu 44 (from the glass's bottom: 84.5 /
  98.5 / 35).
- **Column** (X 3.8–34.3; battery 4.25–33.85): battery Y 2–38, HAT Y
  38.5–104 (PCB back at Z 1.35, with an underside-parts pocket/bump 0.85
  proud at X 11.4–30.1, Y 52.4–92.6), gap with the forward pedestal, XIAO Y
  116.4–137.4 (USB-C centre Z 5.1).
- **Mounts:** HAT located/clamped by 4 shouldered pins on the front plate
  through its Ø3 holes, into floor sockets. **Case screws: M2.5 ×5**:
  spine S1 (7, 110.5), S2 (30, 110.5), S3 (6, 127) under the grip pad;
  chin S5 (100, 4.5), S6 (45, 4.5) under the stowed cover. Each has a
  Ø3.6 heat-set insert hole in a front-plate boss (3.9 deep in the spine,
  2.9 in the chin), a Ø2.8 clearance hole and a **Ø4.8 × 1.9 head
  counterbore** in the tub. Also: switch cradles, a forward-switch pedestal,
  battery side walls, XIAO rails/side walls/clamps, storage pins (holes
  assumed 2 from the long edge, 16.5 c-c), adapter walls and pad, a 4×3
  glass-support rib grid, wire tabs along the spine wall channel, and
  antenna-cable clips.
- **Interference check is clean** (except the USB-C reference block's
  square corners against the rounded slot ends, which isn't a real clash).
- **Not yet modelled:** grip-pad recess, magnets and hall-sensor pocket,
  right-edge hooks, light-pipe bodies, pinhole guide tubes, test coupons.

## Design variants under evaluation (2026-11-22)

- `ereader-case.sc` is the **flat design**: a 9.0 spine with a stepped
  stowing recess and a flat 2.0 cover, 107.7 × 138.4. Known clashes: the
  R4 palm round cuts into the HAT and battery, and the battery breaks
  through the R6 corner.
- `archive/ereader-case-wedge.sc` is the **narrow wedge, option B**, currently
  preferred. It is 92.4 × 136.6. The glass sits over the electronics, with
  keys in their own strip at the left edge on pedestals. The back is 9.0 to
  X 46, then tapers (R40 blend) to 5.0 at the right edge. The cover is a
  **flat 2.0 plate**. Closed it gives a clean wedge, 11 → 7. Stowed on the
  back it rests on the flat 9.0 zone (11 slab) and leaves an air wedge under
  its right side. Plan corners are R4. Reference parts are `REF_*` bodies;
  `VIEW_CoverClosed` is a hidden copy showing the closed state.
  (Option C, a matching wedge cover, was rejected: closed it gives a
  "folded" profile.) Mounts are not modelled yet.
- Several numbers in the decisions list below (positions, spine width,
  bump) apply to the flat design only. The wedge design's numbers are
  its SolidCraft parameters.

## Decisions taken with these measurements

- **Form: Oasis-style grip spine** along one long edge (thick parts gathered
  into the spine, thin back behind the screen). Replaces the "option B"
  top-to-bottom wedge.
- **The spine is on the LEFT by default** (owner is left-handed). Firmware
  offers a **180° rotation** that flips the image and swaps the button
  mapping, so the device also works right-handed. In the default
  orientation USB-C is on the top edge; rotated, it's on the bottom.
- **Everything thick goes in the spine, and the spine sits BESIDE the glass,
  not behind it.** From top to bottom the column holds XIAO (21), battery
  (36) and HAT (65.5). The HAT connects to the panel's FPC through the
  FFC extension and its adapter board. The screen section only holds the
  glass, the adapter, the storage module and wiring.
- **The screen section is modelled around the current 3.6 mm adapter**
  (≈ 6.0 mm deep). The adapter height is a parameter, so a low-profile
  adapter later only changes a value.
- **Spine width is a parameter, and two variants get modelled.**
  (A) **≈ 33 wide:** the whole HAT and battery sit beside the glass; the
  spine is ≈ 9.3 deep. (B) **≈ 22 wide:** the HAT and battery reach
  ≈ 10 mm in under the glass edge. The back curves from the spine down to
  the screen section, which absorbs the extra depth where the parts overlap
  the glass.
- **Cover: a magnetic plate covering the screen section only**
  (≈ 75 × 131 × 2.5). Closed, it lies on the glass and stands 2.5 proud of
  the spine's front face, so the closed device is an even ≈ 9.3 slab. Stowed,
  it sits in the recess behind the screen section, against the spine step.
  It's held by ~6 × 2 neodymium discs sealed inside the print (pause the
  print to insert them) in **alternating-polarity pairs**, so it pulls
  itself into place, fits one way round, and works on both faces.
- **Buttons: page forward and back on the FRONT FACE of the spine**
  (Oasis style), stacked vertically ~15–20 apart at thumb height, with
  "next" lower. The 180° rotation swaps them. **Menu goes on the TOP edge**,
  next to USB-C. Each tactile switch is mounted with its plunger pointing
  forward (4.3 tall into the ~6.9 interior of the spine).
- **Key caps: start with separate captive plungers** (option b). Each is
  its own printed cap, flanged so it can't fall out of its hole, standing
  ~0.6–0.8 proud, with 0.3–0.4 clearance. **Fallback (c):** flexure tongues
  in the front wall with thin raised caps glued on, if the plungers feel
  bad (wobble, gaps, dust).
- **The page switches have to sit over a thin end of the HAT.** The depth
  at a button is ≈ 7.7 (wall 1.2 + cap flange 0.6 + gap 0.1 + switch 4.3 +
  legs/wire 0.3 + back wall 1.2). The spine column is full, so each switch
  sits on top of something. Over the battery, or over the middle third of the
  HAT (connectors, inductor), it's too deep. Over either end third of the HAT
  (bare 1.7 board) it's ≈ 9.6, which needs either the spine raised to ≈ 9.6
  or the back wall thinned locally to ≈ 0.9 under the buttons, inside where
  it doesn't show. With the HAT at the bottom of the column, the usable
  heights are ~0–22 and ~44–65 up from the bottom edge. Reordering the
  column to XIAO / HAT / battery moves them higher.
- **The owner's natural thumb position** (large hands, measured from the
  glass's bottom edge): page forward ≈ **90**, back ≈ **80**. With a bottom
  bezel of ≈ 6 (room for the FPC fold), that's ≈ 96 and ≈ 86 from the
  device's bottom edge. Recommended spacing is 12–13 (back ≈ 83).
- **Switch legs get trimmed** to stubs with the wires soldered to the
  side, which removes 0.3 from the stack. Over a thin end of the HAT the
  stack is then 9.3. Still thin the back wall to 0.9 under the buttons as
  margin.
- **PROPOSED column from top to bottom (pending the HAT measurements):**
  XIAO (USB-C at the top, ~113–134 from the bottom) → a ~15 free gap
  (storage, hall sensor, or a button) → HAT (~32–98), with its upper thin end
  under the page buttons → battery **rotated** so 29.6 runs along the length
  (~1.5–31). Its 36 side runs across the spine and reaches ~6 under the glass
  edge (≈ 8.0 deep there, absorbed by the back curve).
- **Menu moves to the spine's front face** over the HAT's lower thin end
  (≈ 40 from the bottom), with a round cap to tell it apart from the pill
  page keys. This replaces the top-edge position.
- **Bare HAT ends (measured):** on the top side, the ESP (PH2.0) connector
  and the FPC connector both start **24** from each short end (centred), and
  the interface switch is **11** from one end (the "switch end"). On the
  underside (estimated from the photo), parts start ≈ 16 from the switch
  end and ≈ 13.5 from the other end (TSSOP chip). **Bare on both faces:
  switch end ≈ 11, other end ≈ 13.5.**
- **The PH2.0 (ESP) connector will be desoldered** and the 9 wires
  soldered straight to its pads, because the sideways plug and wires would
  otherwise need the spine ~8 wider. The FPC connector and interface switch
  are both **2.0** tall, so **the HAT stack is now 5.2** (2.0 + 1.7 PCB +
  1.5 inductor), no longer 6.6. The **ZIF long edge faces the glass**
  (ribbon from the adapter). Where the PH pads were, on the outer long
  edge, the wires leave toward the outer wall's channel.
- **The battery's wire end faces the outer wall** (wires up the wall channel
  to the XIAO). Its plain 4.9 edge is the one that tucks under the glass.
- **The spine is FLAT at 9.0 deep** (set by the back button over the
  HAT's bare end: 1.2 + 0.6 + 0.1 + 4.3 + 0.2 + 1.7 PCB + 0.9 thinned back
  wall). Without the buttons it could be 8.0 (battery). **Possible later
  improvement:** an 8.0 spine with a grip swell on the back rising to 9.0
  over the button band (~80–105). The screen section stays 6.0, so the
  **step is 3.0 and the cover stays 2.5**.
- **Case split:** a front plate (front face, glass window and glue ledge,
  key holes, internal bosses; printed face-down) and a back tub (walls plus
  stepped back; printed rim-down, with supports only on the inside). The
  seam runs along the front perimeter edge inside a 0.5 chamfer.
- **Fastening:** **hidden screws on the spine side.** On the thin (screen)
  side, use hooks and/or countersunk screws. Those are inside the area the
  stowed cover covers, so they're only visible while the cover is on the
  front. Thin-side plan: hooks along the right edge plus one countersunk
  M2.5 near each corner of the recess.
- **Spine screws are hidden under a grip pad.** M2.5 screws go through the
  spine's back into threaded inserts in front-plate bosses. **Four of them
  go through the HAT's Ø3 mounting holes** (clamping the HAT and closing the
  case at once), plus one or two beside the XIAO and the battery. A
  0.6–0.8 pad (printed TPU or cut silicone, on thin double-sided tape) sits
  flush in a shallow recess across the spine's back. To open the case, peel
  the pad off and re-stick it with fresh tape.
- **The glass sits behind a 0.8 lip** (four 0.2 layers, the first ones
  printed face-down). The lip overlaps the inactive border and has a 45°
  chamfer down into a ~64.5 × 110.5 window, so it hides the border marks and
  protects the glass edges. **The screen section is now 6.8 deep**
  (0.8 + 1.06 + 3.6 adapter + 0.3 + 1.0). **The step to the spine is 2.2,
  so the cover is 2.0** (6 × 1 magnets). Closed, the device is 8.8 at the
  screen section against a 9.0 spine.
- **The WiFi antenna sticks to the inside of the back wall, at the
  top-right corner of the screen section**, behind the glass, with its 40
  side along the top edge. It's as far as possible from the battery, the
  HAT and the gripping hand. The cable is ~40–50 from the XIAO, and the
  spare length curls in a channel. **Keep magnets ≥ 10 from the
  antenna**, and check RSSI inside the closed case before final printing.
- **Storage module** goes behind the glass at the top-left of the screen
  section (next to the XIAO, ~11 from the antenna), located on two printed
  pins through its Ø2.5 holes plus glue. **Wiring** runs in moulded
  channels on the inside of the back tub (~1.5 wide × 1.0 deep, with
  clips). **XIAO** sits in a printed cradle at the top of the spine, clamped
  from behind with no holes through the board. USB-C goes through the top
  edge with a chamfered opening big enough for a standard cable's plug.
- **Charge LED light pipe:** printed in transparent PETG with a small
  flange on its inside end, pushed in from inside before assembly so the
  flange stops it coming out. Printed light only travels straight, so the
  LED dot appears on whichever face the LED points at.
- **The XIAO's top face points FORWARD**, with USB-C at the top. The
  charge LED is on the outer side of the port, so its light-pipe dot sits
  on the spine's front face ~6.5 below the top edge (pipe ≈ 4.5 long). The
  U.FL socket is at the board's lower outer corner on the front face, so
  its cable crosses in front of the XIAO (≈ 2 spare depth) and then runs
  to the antenna behind the glass.
- **Two light pipes**, one each side of USB-C (charge LED on the outer
  side, firmware-driven user LED on the glass side). They're **Ø1.5 in a
  Ø1.6 hole**, each with a **half-moon lip on the side away from the
  pinhole tube**, because the pinhole centres are only **2** away (above
  each LED). The pinhole tube bore is Ø1.0, leaving ~0.7 of wall between
  them.
- **RESET pinhole: drilled after printing.** Model a guide tube from the
  inside, stopping **0.4 short of the outer surface**, plus a drill centre
  mark on the outside. Drill through with a 0.8–1.0 bit and press with a
  paperclip. Recommended: also model a matching undrilled tube over
  **BOOT** (needed with RESET to get into download mode after a bad flash).
- **⚠ SUPERSEDES the rotated battery in the "PROPOSED column" note above.**
  Nothing may reach under the glass anywhere along the cover's length.
  Otherwise the stowing recess (≈ 64.7) is narrower than the cover
  (≥ 68.5). **The battery is unrotated** (29.6 across the spine, which fits
  with 1.2 walls; 36 along the length). **Column from the device's
  bottom:** battery 1.5–37.5 → HAT 38–103.5 (switch end down) → free gap →
  XIAO at the top (top inner edge at L − 1.5). **Buttons from the device's
  bottom:** back ≈ 91.75 (over the HAT's bare top end, 90–103.5), forward
  ≈ 103.75 (12 spacing), menu ≈ 44 (over the switch-end bare zone, 38–49).
- **Glass position is a parameter: `bezel_bottom` = 9** (a slight chin;
  `bezel_top` = 3), so the device is **≈ 138.4 long**. Buttons from the
  glass's bottom edge: back ≈ 83, forward ≈ 95, about 3 above the owner's
  measured 80/90. Raise `bezel_bottom` to 12 to hit them exactly (141.4
  long); every 1 of chin moves the buttons 1 closer.
- **Exterior style: soft back, crisp front.** The front edge has a 0.8
  chamfer all round (prints cleanly face-down and hides the seam), and
  the outline has 6 corner radii in plan. The spine's outer back edge (in
  the palm) has a 4 fillet, printed with variable layer height. The step
  from spine to recess is a concave 3-radius cove, which also seats the
  stowed cover's edge. Other back edges get 1.5 fillets.
- **The HAT is oriented with its switch end DOWN.** With the HAT at ~32–97.5
  from the bottom, the bare band for the page buttons runs from 84 (top
  of the HAT's end zone) through the free gap to 113 (XIAO). **Page
  forward ≈ 98, back ≈ 86** (from the device's bottom edge; ≈ 92 / 80 from
  the glass's bottom edge). **Menu ≈ 38**, over the 11 bare at the switch end
  (32–43).
- **Optional: a hall sensor** that detects the cover so removing it wakes
  the reader and replacing it puts it to sleep. Leave a pocket for it next to
  one of the cover magnets and plan one RTC-capable GPIO (a spare XIAO
  castellation).
- **Protoboard dropped.** Parts are wired directly, or a small cut board
  goes in the spine. The case must provide **wire channels / cable
  routing** so wiring is enclosed and tidy.
- **Fasteners available:** M2.5 nylon screws and nuts, plus M2.5 threaded
  inserts. Use these for component mounting and closing the case.
