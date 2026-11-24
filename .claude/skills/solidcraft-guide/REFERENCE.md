# SolidCraft command shapes and procedures

Shapes the bundled `solidcraft-modeling` reference leaves out, found by use (SolidCraft 0.46).

## Command shapes

- `timeline.edit {feature, set:{field:value}}`: the key is `set`, not `params`. `timeline.inspect {feature}` lists a feature's field names. A cylinder's fields are `radius`, `base`, `height`, `axis`; there is no `diameter` field, although creation accepts one.
- `timeline.delete {feature}`. Deleting a feature that joined into a tool body is safe.
- `solid.combine {target, tools:[..], operation:"join"|"cut"|"intersect", touching:"one_body"}`.
- `solid.move {bodies, translate:[x, y, "expr"], copy:true, body_name}` copies a body (for example an open and a closed view). Rotate with `axis:[0,1,0], angle:"-7.6 deg", origin:[x,y,z]`.
- `solid.cylinder {axis:"Y", base:[x,y,z], ...}` makes a horizontal hole or slot.
- `inspect.interference {bodies:[..], exclude_pairs:[[a,b]], budget_s}`: about 0.4 s for 17 bodies.
- `inspect.measure {bodies:[..], summary:true}` through `execute`, or a `measure` step inside a batch.
- `appearance.assign {bodies:[..], color:"#hex"}`: it needs `bodies`, as a list.
- `browser.visibility {items:[..], visible:false}` hides bodies such as `VIEW_*` and `OPT_*` copies.

## Screenshot camera presets

`screenshot {source:"model", camera:{target:[x,y,z], yaw, pitch, distance}}`, with yaw and pitch in radians and distance in mm.

- Top view, portrait: `pitch 1.5, yaw 0`.
- End view: `pitch 0.02, yaw 0`.
- Close-up: set `target` on the detail and `distance` to a few times its size. The standard views fit the whole part and are too far out to show small features on anything large.

## Editing a profile sketch in place

A profile can change shape (fewer or more corners) without rebuilding the design:

1. `sketch.edit {sketch}`.
2. `sketch.inspect`, then `sketch.delete` every curve and every expression-fixed corner point. The points stay behind when only the curves are deleted, and fillet corner points are renumbered once the curves go, so inspect before deleting the points.
3. `sketch.line` with the new expression points, then `sketch.fillet` on the corners.
4. `sketch.finish`.

New curve ids carry on from the old maximum and are never reused. Later extrudes and combines rebuild cleanly; fillet dimension parameters come back renamed (`d1`...).
