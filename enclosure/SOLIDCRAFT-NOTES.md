# SolidCraft MCP: how to drive it efficiently

Lessons from building `ereader-case.sc` (SolidCraft 0.46.2, Flatpak, ~1,000
commands over several rebuilds). Read this **before** the next modelling session.

## 1. Setup
- The MCP server is `~/.local/bin/solidcraft-cli mcp --allow-path
  /home/reuben/Documents/dev/esp-read/enclosure`. It's a wrapper around the
  Flatpak's `solidcraft-cli`. It was registered with the VS Code extension's
  bundled `claude` binary (`~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude`),
  because `claude` isn't on PATH.
- **To drive the user's open window**, turn on Preferences › AI → agent
  connections in the app. The server finds the port and token in
  `~/.var/app/io.tangencylabs.solidcraft/data/solidcraft/control/` by itself.
  `version` should report `mode: app`. If it says `headless`, the app's AI
  setting is off.
- **Saving:** `save {path}` only writes inside `--allow-path` folders (plus
  the app's recovery folder). The project's `enclosure/` folder is allowed.
- After `/mcp` reconnects, the tool schemas have to be reloaded with
  ToolSearch (`select:mcp__solidcraft__batch,...`). **Always call the full
  name** `mcp__solidcraft__batch`, not `batch`.

## 2. Workflow that worked (fastest to slowest)
1. **Everything is a parameter.** Put every dimension in `parameters.add`
   and use expressions in feature fields (`"key_x - key_w/2"`), so layout
   changes become `parameters.change` batches with `coalesce_parameters: true`.
2. **Build shells from cross-section profiles:** `sketch.create {plane:"XZ"}`
   → `sketch.line {points:[[x,"-z"],...], closed:true}` (XZ plane: sketch y =
   **−Z**; expression points stay at dof 0) → `sketch.fillet {a:"l7", b:"l1",
   radius}` for the rounds → `solid.extrude {distance:"L"}`. The tub took
   ~0.1 s this way; the earlier 3D-fillet approach took 60–70 s and failed
   often.
3. **Plan-view corner rounding:** make a box, fillet its 4 vertical edges, and
   `solid.combine {operation:"intersect"}` it with the body. **Hollowing:**
   build a cavity the same way (a profile offset by the wall thickness,
   intersected with a box with rounded corners), then `combine cut`. Never use
   `solid.shell` (see traps).
4. **Many small features:** build them into one tool body (`TubAdd`,
   `TubCut`, `FrontAdd`, `FrontCut`) with primitive joins (fast, ~1–150 ms
   each), then do one `solid.combine` join/cut per tool. A boolean directly on
   the complex tub costs ~2.7 s each. One 80-step batch built every mount in
   ~10 s.
5. **Check every stage:** batch `expect {volume_mm3, bodies, bbox}` with your
   own estimate (it catches mistakes immediately; analytic estimates matched
   to <0.1%). Then **`inspect.interference`** over the real bodies plus the
   `REF_*` parts (~0.4 s for 17 bodies).
6. **Reference parts:** model every component as a `REF_*` body, give it its
   real holes, and colour it with `appearance.assign {bodies:[..], color:"#hex"}`.
   Keep views and options as hidden `VIEW_*` / `OPT_*` bodies
   (`browser.visibility {items:[..], visible:false}`).
7. **A big rework is faster as a clean rebuild** (`new_design` + 3 large
   batches: shells and front features → caps, covers and REF parts → mounts)
   than as dozens of `timeline.edit`s. Keep the batch JSON recipe in
   your head or notes, and back up the `.sc` first (`cp x.sc archive/x-vN.sc`).

## 3. Command shapes that aren't obvious
- `timeline.edit {feature, set:{field:value}}` (not `params`). Cylinder
  fields are `radius` / `base` / `height` / `axis` (**no `diameter`**,
  although creation accepts it). `timeline.inspect` lists a feature's fields.
- **Don't run dependent calls in parallel** (e.g. an edit plus the
  interference check): the parallel call sees the old state.
- `timeline.delete {feature}`. Deleting a feature that joined into a tool body is fine.
- `solid.move {bodies, translate:[x,y,"expr"], copy:true, body_name}` makes copies (closed-state
  views). Rotate: `axis:[0,1,0], angle:"-7.6 deg", origin:[...]`.
- `solid.combine {target, tools:[..], operation:"join|cut|intersect", touching:"one_body"}`.
- `solid.cylinder {axis:"Y", base:[...]}` works for horizontal holes (the USB slot).
- `inspect.interference {bodies:[..], exclude_pairs:[[a,b]], budget_s}`.
- `inspect.measure {bodies:[..], summary:true}` (through `execute`), or the
  `measure` step inside a batch.
- `list_commands {filter|prefix, fields:["id","params"]}` gives one line per
  command. **Avoid `describe_command`** (~6 KB schema each).
- Screenshot without moving the user's camera: `screenshot {source:"model",
  camera:{target,yaw,pitch,distance}}`. Top view: `pitch 1.5, yaw 0`
  (portrait). End view: `pitch 0.02, yaw 0`.

## 4. Traps hit
- **Fillets** are the kernel's weak point: they fail when the chain runs into
  other blends ("contact line leaves the face"), and a fillet can't end
  tangentially against an unblended edge. Small blends on long chains are
  **slow** (one 0.6 mm cove took 60 s, and every later rebuild repeats it).
  → Put rounds in the **sketch profile** instead.
- `solid.shell` failed on filleted bodies (a convex blend smaller than the
  wall folds; an offset-gap error) → use a cavity tool body.
- A box cavity with square corners **breaks through** rounded outer corners
  → round the cavity first.
- A pick exactly on a vertex is refused ("2 edges meet") → pick mid-edge,
  away from splits.
- `appearance.assign` needs `bodies:[...]`, and `opacity` has no visible
  effect in model renders → hide bodies instead.
- **Mount bases over a sloped floor:** a base at a fixed Z pokes out through
  the back where the floor rises. Each base Z has to lie between the outer
  back surface and the inner floor **at that X**.
- `inspect.interference` false positives: REF parts without holes (pins),
  and a square USB block against the slot's rounded ends. Ignore the second.
- `solid.combine join` of a tool body that touches another body only
  along a line → separate pieces. Use `touching:"one_body"` when it's intended.
- The batch `expect` bbox includes **hidden** bodies (VIEW/OPT copies).

## 5. Editing a profile sketch in place (v6 → v7)
- Changing a profile's topology (fewer corners) doesn't need a rebuild:
  `sketch.edit {sketch}` → `sketch.delete` every curve **and** the
  expression-fixed corner points (they stay behind; `sketch.inspect` lists
  them, and virtual fillet corners get renumbered after the curves are
  deleted, so inspect before deleting points) → `sketch.line` with the new
  expression points → `sketch.fillet` → `sketch.finish`. New curve ids
  continue from the old maximum (never reused). Downstream extrudes and
  combines rebuild cleanly, and fillet dimension params are renamed (d1…).
- `parameters.list {filter}` returns **every** parameter with `used_by`
  (~240 KB here), so it overflows the reply. To find what uses a parameter,
  `timeline.inspect` the likely features instead.
