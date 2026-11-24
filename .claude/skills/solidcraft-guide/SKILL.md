---
name: solidcraft-guide
description: SolidCraft CAD house workflow. Use before any mcp__solidcraft__ design work - building a new part, editing an existing design, or exporting files for 3D printing.
---

How to build parts in SolidCraft quickly and hand back print-ready files. This adds to SolidCraft's own bundled reference (`skill_reference {"skill":"solidcraft-modeling"}`), which holds command shapes and plane axes; read that once per session before the first build. Command shapes it leaves out, and editing a profile sketch in place, are in [REFERENCE.md](REFERENCE.md).

## Steps

1. **Connect to the user's app.** Call `version` (or read the first reply): it should say `mode: app`. If it says headless, ask the user to open SolidCraft and turn on Preferences › AI › agent connections, then wait. A headless session that already has features stays headless, so the user never sees the model. After `/mcp` reconnects, reload the tool schemas with ToolSearch and call tools by their full `mcp__solidcraft__` names. Done when the reply says `mode: app`, or the user says to carry on headless.

2. **Get real measurements.** For any bought part the design must fit (a cable plug, a board, a battery, a screw), ask the user for caliper numbers up front. Amazon and UGREEN pages refuse automated fetches, and listings rarely publish the sizes that matter. Done when every fit-critical size is a measured number or is named to the user as an estimate.

3. **Plan the numbers.** Every size becomes a named parameter, used through expressions in feature fields, so a layout change is one `parameters.change` batch with `coalesce_parameters: true`. Model each bought part as a `REF_*` body with its real holes. Work out the expected volume and bounding box of each stage before building it.

4. **Build in stages, one `batch` per stage,** using the construction moves under Building fast. Use `verbose: false`, name every feature, and pass `expect`. `expect` counts every body, hidden `VIEW_*`/`OPT_*` copies included, so add the untouched bodies to the volume and bbox. Done when each stage's `expect` passes.

5. **Check fit and look at it.** Run `inspect.interference` over the real bodies and the `REF_*` parts. Then aim `screenshot {source:"model", camera}` at the detail just built (presets in REFERENCE.md); this leaves the user's own camera alone. Done when interference shows only known false positives (a `REF_*` part modelled without its holes, a square block against a rounded slot end) and the render shows the feature where it should be.

6. **Export and deliver.** In one batch, export each print variant, the STEP and the `.sc`. Then make sure the files are in the project folder (see Saving). Done when an `ls` of the project folder shows fresh timestamps on every file the change touched.

## Saving

`save` and `export` only write inside `--allow-path` folders and the app's recovery folder. A server started without `--allow-path` writes only to its temp folder (`/private/var/folders/.../solidcraft-mcp-<pid>-<id>/` on macOS, named in the error), so save there and `cp` into the project. The lasting fix is for the user to add `--allow-path <project folder>` to the SolidCraft entry in their MCP config. Before a big rework, back up the `.sc` (`cp x.sc archive/x-vN.sc`).

## Building fast

Booleans and fillets on a complex body are the slow part (seconds each, repeated on every rebuild); primitives and sketches are milliseconds. So:

- **Rounds go in the sketch, not in 3D.** Build shells from a cross-section: `sketch.line` with expression points, `sketch.fillet {a, b, radius}` on its corners, then extrude. This took 0.1 s where 3D fillets took 60-70 s and often failed.
- **Round plan-view corners by intersecting:** a box with its four vertical edges filleted, `solid.combine {operation:"intersect"}` with the body.
- **Hollow with a cavity body, never `solid.shell`.** Build the cavity the same way (profile offset by the wall, intersected with a rounded box), then `combine` cut. Round the cavity's corners too, or it breaks through rounded outer corners.
- **Gather small features into tool bodies.** Join bosses, mounts and cutters into one add body and one cut body using primitives, then apply each with a single `solid.combine`. One 80-step batch built every mount this way in about 10 s.
- **A big rework is faster as a clean rebuild** (`new_design` and three or four large batches) than as dozens of `timeline.edit`s.
- **Variants are one feature toggled** with `timeline.suppress`. One batch: unsuppress, measure, export, re-suppress, export, save.
- **`edit.checkpoint` before an exploratory or styling pass,** so `edit.restore_checkpoint` undoes it in one step.
- **Look up commands cheaply:** `list_commands {filter, fields:["id","params"]}` gives one line each. Use `describe_command` (about 6 KB) only when that line isn't enough.
- **Learn an existing design:** `inspect_design {"timeline":"summary","sketches":false}`, then `parameters.list {"filter":"feature"}` on a small design. On a large one that reply overflows (240 KB), so `timeline.inspect` the likely features instead.
- **Send dependent calls one after another.** A call run in parallel with an edit sees the design from before the edit.

## Gotchas

- Fillets fail when the chain runs into other blends ("contact line leaves the face") or has to end against an unblended edge. A failed fillet names the largest radius that fits; use that, or move the round into the sketch.
- A pick exactly on a vertex is refused ("2 edges meet"); pick mid-edge. One pick takes the whole tangent chain, and sharp corners end it.
- `solid.chamfer` with `distance2`: `distance` runs along the most upward-facing face unless `flip: true`.
- A cut or join that leaves the volume unchanged has missed, even with `ok: true`.
- A join of a body that touches another only along a line gives separate pieces. Pass `touching:"one_body"` when that contact is intended.
- A feature placed at a fixed height over a sloped surface can poke through it. Check its height against the surface at that feature's own position.
- If `opacity` doesn't show in a model render, hide the bodies in front with `browser.visibility` instead.

## Printability (Prusa Core One, 250 x 220 bed)

- Decide the print orientation first and design so it needs no supports: overhangs at 45 degrees or steeper, short bridges only, decorative grooves on top-facing surfaces.
- Bevel a bed-facing edge with a 45 degree chamfer, not a fillet.
- Keep at least 1 mm of material over any hidden pocket, and check decorative cuts never eat into it.
