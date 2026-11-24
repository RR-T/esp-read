# SolidCraft notes for this project

The general workflow, speed tricks and traps for driving SolidCraft through
its MCP server now live in the `solidcraft-guide` Claude Code skill in this
repo (`.claude/skills/solidcraft-guide/`). Claude loads it before any
SolidCraft work. This file keeps only what is specific to this machine and this model.

## Setup on this machine
- The MCP server is `~/.local/bin/solidcraft-cli mcp --allow-path
  /home/reuben/Documents/dev/esp-read/enclosure`, a wrapper around the
  Flatpak's `solidcraft-cli`. It was registered with the VS Code extension's
  bundled `claude` binary (`~/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude`),
  because `claude` isn't on PATH.
- With agent connections on in the app, the server finds the port and token in
  `~/.var/app/io.tangencylabs.solidcraft/data/solidcraft/control/` by itself.
- `enclosure/` is the allowed save folder, so `save` writes straight into the
  project. Back up to `archive/ereader-case-vN.sc` before a big rework.

## How `ereader-case.sc` is organised
- Small features are gathered into the tool bodies `TubAdd`, `TubCut`,
  `FrontAdd` and `FrontCut`, each applied to its part with one `solid.combine`.
- Bought parts are coloured `REF_*` bodies with their real holes. Run the
  interference check against them after every change. Known false positives:
  pins modelled without holes, and the square USB block against the slot's
  rounded ends.
- Views and options are hidden `VIEW_*` and `OPT_*` copies. They still count
  in a batch's `expect` bounding box.
- The tub floor slopes, so each mount base's height has to sit between the
  outer back surface and the inner floor at that mount's own X position.
- The last full rebuild took three large batches: shells and front features,
  then caps, covers and `REF_*` parts, then mounts.
- `parameters.list` returns about 240 KB on this model; use `timeline.inspect`
  on the likely features to find what uses a parameter.

## Lessons from the sanding-skin round (0.47.0)
- `solid.offset_face` and `solid.shell` (outside) are refused on the tub
  even at its simple 15-face stage ("no certified bound" where the plan
  rounds meet the sloped back). Build the offset shape from primitives
  instead (redraw the profile sketch 0.3 out, a 0.3-bigger rounded box),
  subtract the original, and carve openings back by cutting the skin with
  copies of (envelope − finished part) shifted 0.3 outward along each axis.
- `envelope − part` can split into many pieces (one per hole); join the
  pieces into one body before shifting, or the small holes get covered.
- `solid.box {centred:true}` doesn't centre on all axes the way it looks;
  give explicit corners and rotate with `solid.move {axis, angle, origin}`.
- A ~600-feature timeline replays seconds per edit near the start; the
  app's memory grows with every undo step and checkpoint. Restarting the
  app frees it.
