# Enclosure

A 3D-printed case for the reader: a portrait Oasis-style grip spine on the
left, side keys, and a removable living-hinge cover that stows on the back.
It's modelled in SolidCraft. Printed in PETG, with a few small TPU parts.

| Path | What it is |
|---|---|
| `ereader-case.sc` | **The current model (v9: firmer board mounts, triangle ribs behind the display, print fixes).** It holds separate bodies (tub, front plate, keys, cover, light pipes) and coloured `REF_*` reference parts. |
| `MEASUREMENTS.md` | Measured part sizes and every design decision. **Read this first.** |
| `SOLIDCRAFT-NOTES.md` | How to drive SolidCraft through its MCP server efficiently, and the traps to avoid. |
| `print/` | Print-ready parts: the power-switch slide caps (three socket sizes to find the best press fit), a test coupon of the switch edge, a test slice of the right-edge hook joint, the cover laid flat for printing, the keys, the TPU cover bumpers, spine grip pad and key rings, and the support bridge that sits over the HAT. |
| `renders/` | Renders of the current model. |
| `drawings/` | `layout_generator.py` and its 2D PNGs (front, back, cross-sections). It reads every number from `ereader-case.sc`, so re-run it after changing the model. |
| `archive/` | Earlier model versions (v1-v8, plus the wedge variant). |

## How to print it

Mostly simple. Two parts need care: the tub (supports under part of its back)
and the cover (a pause to drop in the steel discs).

| Part | Material | Orientation | Supports | Notes |
|---|---|---|---|---|
| Tub | PETG | **Back down** | Build plate only | Only the spine's back touches the bed. The display section's back sits 1.5 higher and needs a flat support under it, plus the shallow slope between them and the bottom of the palm round. That surface is hidden by the stowed cover. Everything inside (ribs, posts, pins, walls) then grows straight up and needs nothing. |
| Front plate | PETG | Face down | None | Flat front face on the bed. **Use 0.1 layers for the first 1 mm** so the 45° face chamfers come out smooth. The six small lips on the key cradles overhang 1.5; they print with a little droop, which doesn't matter there. |
| Keys (3) | PETG | `print/keys.stl`, flange down | None | The lip is 0.4 (two 0.2 layers). The grooves on top print best at 0.1 layers for the last 0.3. |
| Key rings (3) | TPU 95A | `print/tpu-key-rings-0.3.stl` (or `-0.4`), flat | None | Optional; compare against foam on the key test print. Slip one over each key onto its lip before fitting the front plate. |
| Cover | PETG | `print/cover-flat.stl`, smooth face down | None | Print the flat version, not the stowed shape. **0.1 layers, and pause at 0.5 mm** to drop the five steel discs into their sealed slots (four Ø8, one Ø5 at the spine end). |
| Slide cap | PETG | Face up (as exported) | None | 0.1 layers. |
| Debug shell (optional) | PETG | `print/debug-tub.stl` and `debug-front.stl`, same way up as the real tub and front plate | Same as the real parts | A test-fit copy of the shell with viewing windows in all four walls, cut across the join between tub and front plate, so you can see how the boards, battery, keys and XIAO sit against the display. The real `Tub` and `Front` are unchanged. The front plate is only 0.6 thick over each window, so handle it gently. |
| Cover bumpers (9) | TPU 95A | `print/tpu-bumpers.stl`, flat end down | None | Slow (about 20 mm/s), 0.1 layers. Print a few spares; they're tiny. Push into the front frame with a drop of CA glue. |
| Spine grip pad | TPU 95A | `print/tpu-grip-pad.stl`, flat, grooved face up | None | Stick on with thin double-sided tape; peel off to reach the spine screws. |
| HAT support bridge | PETG | `print/hat-bridge.stl`, **flipped**, flat top on the bed | None | Slips over the HAT's two right-hand pins after the HAT goes in. 0.4 soft foam on top. |
| Light pipes | | | | Use 1.5 mm clear acrylic rod cut to length, glued in. It carries light far better than a printed pipe. |

**Why not tub rim-down?** It gives the back a perfect top-surface finish, but
then the whole floor, every rib, post and pin starts in mid-air and needs
support inside the rib cells, which is very hard to get out.

**Fits to expect** (printed holes come out about 0.1-0.2 small):

| Fit | Holes | Expect |
|---|---|---|
| Magnets Ø6 and Ø4 | Ø6.2 / Ø4.2 | Snug press fit. Add a drop of CA glue anyway. |
| M2.5 heat-set inserts | Ø3.6 | Check your insert's recommended hole; most short M2.5 inserts want 3.5-3.6. |
| M2.5 screw clearance | Ø2.8 | Free fit. |
| M2.5 screw head counterbore | Ø4.8 | Fits a 4.5 head; may need a twist with a 5 mm drill. |
| HAT pins | Ø2.6 in the board's Ø3.0 | Free fit. |
| Storage pins | Ø2.2 in the board's Ø2.5 | Close fit; sand the pin if tight. |
| Light-pipe holes | Ø1.8 | 1.5 rod slides in. |
| Key caps in their holes | 0.3 each side | Free sliding fit. |
| Right-edge hook joint | 0.15-0.2 gaps | Print the `hook-coupon` pair first. |

**Test pieces to print first** (all in `print/`, at model positions, same
orientation and settings as the full part they come from):

| Test piece | Files | What it checks |
|---|---|---|
| Cover flex lines | `coupon-cover-hinge.stl` | A 30 × 20 slice of the cover with both flex lines. Bend each line about 10° a few dozen times; it should spring back without whitening or cracking. |
| Magnet pull | `coupon-magnet-block.stl` + `coupon-cover-disc.stl` | The block has the same plastic either side of a magnet stack as the real case: 2.55 on the top face (the gap to the closed cover, glass and bumpers included) and 1.1 on the bottom (the gap to the stowed cover). **Pause at 4.6 mm** to drop in a Ø6 × 2 and a Ø6 × 1.5 magnet. The disc piece is a slice of the cover with one sealed Ø8 steel disc (pause at 0.5 mm). Hold the disc piece on each face of the block to feel the closed and stowed pull. |
| Keys | `coupon-key-front.stl` + `coupon-key-tub.stl` + `keys.stl` | The spine around the back and forward keys, with the upper spine screw to hold the two halves together. Fit two switches and keys, then try the TPU rings against foam. |
| Light pipes | `coupon-light-pipe.stl` | The top corner of the front plate with both light-pipe holes, for the 1.5 mm acrylic rod's press fit. |
| Right-edge hook | `hook-coupon-tub.stl` + `hook-coupon-front.stl` | The slide-and-swing fit of the right edge. |
| Top-edge snap catch | `coupon-snap-tub.stl` + `coupon-snap-front.stl` | One of the two catches on the top edge. Press together and pull apart a dozen times: it should click in, hold, and come apart again without whitening. |
| Power switch | `switch-track-coupon.stl` + the three `switch-cap-socket` sizes | The slide cap's grip and travel. |
| Slide cap on switch knob | 1.45 / 1.55 / 1.65 | Try all three. |
| TPU bumpers | Ø2.5 sockets, Ø2.5 plugs | Snug, since printed holes come out a little small. Glue them in. |
| Board clamps | 0.8 gap above each board | Filled by 1 mm foam tape on each clamp end. |
| HAT bridge on the HAT pins | Ø2.9 over the Ø2.6 pins | Free fit; add a dab of glue on each pin. |

**Thinnest parts (all intended):** cover 0.7 with 0.35 hinge webs and 0.2
either side of the sealed steel discs; the power switch's back lip and the ribbon-channel
rails are 0.5 (one extrusion line, not load-bearing, no room to thicken);
the side wire tabs overhang 1.4 with a little droop. Walls are 1.2 (right
wall 2.0), the display back 1.0, ribs 1.0.

