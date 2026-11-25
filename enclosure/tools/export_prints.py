#!/usr/bin/env python3
"""Export every print file from ereader-case.sc, with automatic revisions.

The debug shells and test coupons are not kept in the model (they made every
rebuild slower). This script describes them instead:

  1. `python3 tools/export_prints.py batch [names...]`
     writes `.rebuild/export-batch.json`. Run it in SolidCraft through the MCP
     `batch` tool (`path` = that file). It builds each part as temporary
     features, exports it to `.rebuild/out/`, and deletes the temporary
     features again, so the model is left as it was.
  2. `python3 tools/export_prints.py sync`
     compares each file in `.rebuild/out/` with the newest `print/<name>-rN`
     file. Identical files are left alone; changed or new ones are copied in as
     the next revision and the old revision is removed (`git rm`).

Run from the `enclosure/` folder. Names default to every part.
"""
import json
import math
import pathlib
import re
import shutil
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent  # enclosure/
OUT = HERE / ".rebuild" / "out"
PRINT = HERE / "print"
BATCH = HERE / ".rebuild" / "export-batch.json"

# Windows cut into the debug shells (corner, size).
DEBUG_WINDOWS = [
    ([-1.0, 12.0, 2.2], [4.3, 28, 6.2]), ([-1.0, 46.0, 2.2], [4.3, 16, 6.2]),
    ([-1.0, 68.0, 2.2], [4.3, 14, 6.2]), ([-1.0, 94.0, 2.2], [4.3, 14, 6.2]),
    ([12.0, -1.0, 3.4], [10, 2.3, 5]), ([35.0, -1.0, 3.4], [21, 2.3, 5]),
    ([60.0, -1.0, 3.4], [22, 2.3, 5]), ([36.0, 135.3, 3.4], [16, 2.7, 5]),
    ([56.0, 135.3, 3.4], [16, 2.7, 5]), ([76.0, 135.3, 3.4], [12, 2.7, 5]),
    ([90.6, 15.0, 3.4], [3.4, 20, 5]), ([90.6, 50.0, 3.4], [3.4, 20, 5]),
    ([90.6, 85.0, 3.4], [3.4, 20, 5]),
]

# Test pieces cut from a body by a box: name -> (source body, corner, size).
BOX_COUPONS = {
    "coupon-key-front": ("Front", [-1, 76, 0], [17, 39, 12]),
    "coupon-key-tub": ("Tub", [-1, 76, -1], [17, 39, 12]),
    "coupon-light-pipe": ("Front", [3, 124, 0], [19, 14, 12]),
    "coupon-snap-tub": ("Tub", [47, 124, -1], [16, 14, 12]),
    "coupon-snap-front": ("Front", [47, 124, 0], [16, 14, 12]),
    "coupon-seam-corner-tub": ("Tub", [-1, -1, -1], [21, 21, 10]),
    "coupon-seam-corner-front": ("Front", [-1, -1, -1], [21, 21, 11]),
    "hook-coupon-tub": ("Tub", [80, 62, 2.2], [14, 16, 8]),
    "hook-coupon-front": ("Front", [86.75, 62, 0], [8, 16, 10]),
    "switch-track-coupon": ("Tub", [18, 128.5, -1], [20, 12, 12]),
    "coupon-tub-back": ("Tub", [-1, 28, -1], [61, 25, 5]),
    "coupon-cover-hinge": ("PRINT_CoverFlatFinal", [28, 55, 20], [30, 20, 10]),
    "coupon-cover-disc": ("PRINT_CoverFlatFinal", [60, 33.25, 20], [14, 14, 10]),
}

# Parts exported straight from model bodies.
DIRECT = {
    "keys": ["KeyBack", "KeyFwd", "KeyMenu"],
    "hat-bridge": ["HatBridge"],
    "tpu-bumpers": ["TPU_Bumpers"],
    "tpu-grip-pad": ["TPU_GripPad"],
    "cover-flat": ["PRINT_CoverFlatFinal"],
}

SOCKETS = ["1.75", "1.85", "1.95"]   # slide cap socket sizes (sw_sock)
SOCKET_DEFAULT = "1.85 mm"
RINGS = ["0.3", "0.4"]               # TPU key ring thickness (ring_t)
RING_DEFAULT = "0.3"


def out(name, ext="stl"):
    return str(OUT / f"{name}.{ext}")


def export(path, bodies):
    return {"command": "export", "params": {"path": path, "bodies": bodies}}


def build(names):
    steps = []

    def temp(feats):
        """Add temporary features, then the deletes that undo them."""
        return feats, [{"command": "timeline.delete", "params": {"feature": f["params"]["name"]}}
                       for f in reversed(feats)]

    for name, bodies in DIRECT.items():
        if name in names:
            steps.append(export(out(name), bodies))

    if "tpu-key-rings" in names:
        for r in RINGS:
            steps.append({"command": "parameters.change", "params": {"name": "ring_t", "expression": r}})
            steps.append(export(out(f"tpu-key-rings-{r}"), ["TPU_KeyRings"]))
        steps.append({"command": "parameters.change", "params": {"name": "ring_t", "expression": RING_DEFAULT}})

    if "switch-cap" in names:
        steps.append(export(out("switch-cap", "step"), ["SwCap"]))
        for s in SOCKETS:
            steps.append({"command": "parameters.change", "params": {"name": "sw_sock", "expression": s + " mm"}})
            add, undo = temp([{"command": "solid.move", "params": {
                "bodies": ["SwCap"], "copy": True, "axis": [1, 0, 0], "angle": "-90 deg",
                "origin": [27.75, 137.55, 4.55], "body_name": "TMP_Cap", "name": "TMP_CapRot"}}])
            steps += add + [export(out(f"switch-cap-socket-{s}"), ["TMP_Cap"])] + undo
        steps.append({"command": "parameters.change", "params": {"name": "sw_sock", "expression": SOCKET_DEFAULT}})

    for part, src in (("debug-tub", "Tub"), ("debug-front", "Front")):
        if part not in names:
            continue
        feats = [{"command": "solid.move", "params": {"bodies": [src], "translate": [0, 0, 0], "copy": True,
                                                      "body_name": "TMP_Debug", "name": "TMP_DebugCopy"}}]
        for i, (corner, size) in enumerate(DEBUG_WINDOWS):
            p = {"corner": corner, "length": size[0], "width": size[1], "height": size[2],
                 "name": f"TMP_DebugWin{i}"}
            p.update({"operation": "new_body", "body_name": "TMP_DebugCutter"} if i == 0
                     else {"operation": "join", "participants": ["TMP_DebugCutter"]})
            feats.append({"command": "solid.box", "params": p})
        feats.append({"command": "solid.combine", "params": {"target": "TMP_Debug", "tools": ["TMP_DebugCutter"],
                                                             "operation": "cut", "name": "TMP_DebugCut"}})
        add, undo = temp(feats)
        steps += add + [export(out(part), ["TMP_Debug"])] + undo

    for part, (src, corner, size) in BOX_COUPONS.items():
        if part not in names:
            continue
        add, undo = temp([
            {"command": "solid.move", "params": {"bodies": [src], "translate": [0, 0, 0], "copy": True,
                                                 "body_name": "TMP_C", "name": "TMP_CCopy"}},
            {"command": "solid.box", "params": {"corner": corner, "length": size[0], "width": size[1],
                                                "height": size[2], "operation": "new_body",
                                                "body_name": "TMP_CBox", "name": "TMP_CBoxF"}},
            {"command": "solid.combine", "params": {"target": "TMP_C", "tools": ["TMP_CBox"],
                                                    "operation": "intersect", "name": "TMP_CCut"}},
        ])
        steps += add + [export(out(part), ["TMP_C"])] + undo

    if "coupon-magnet-block" in names:
        add, undo = temp([
            {"command": "solid.box", "params": {"corner": [120, 0, 0], "length": 12, "width": 12, "height": 7.15,
                                                "operation": "new_body", "body_name": "TMP_Mag",
                                                "name": "TMP_MagBlock"}},
            {"command": "solid.cylinder", "params": {"axis": "Z", "base": [126, 6, 1.1], "radius": 3.1,
                                                     "height": 3.5, "operation": "cut",
                                                     "participants": ["TMP_Mag"], "name": "TMP_MagPocket"}},
        ])
        steps += add + [export(out("coupon-magnet-block"), ["TMP_Mag"])] + undo

    return steps


ALL = (list(DIRECT) + ["tpu-key-rings", "switch-cap", "debug-tub", "debug-front", "coupon-magnet-block"]
       + list(BOX_COUPONS))


def latest(base, ext):
    best = None
    for p in PRINT.glob(f"{base}-r*.{ext}"):
        m = re.fullmatch(re.escape(base) + r"-r(\d+)\." + ext, p.name)
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), p)
    return best


def stl_shape(path):
    """Volume, area and bounding box of a binary STL (the mesh itself varies
    a little between exports, and the header holds the file name)."""
    data = path.read_bytes()
    n = struct.unpack_from("<I", data, 80)[0]
    vol = area = 0.0
    lo, hi = [1e9] * 3, [-1e9] * 3
    for i in range(n):
        v = struct.unpack_from("<9f", data, 84 + i * 50 + 12)
        p, q, r = v[0:3], v[3:6], v[6:9]
        vol += (p[0] * (q[1] * r[2] - q[2] * r[1]) - p[1] * (q[0] * r[2] - q[2] * r[0])
                + p[2] * (q[0] * r[1] - q[1] * r[0])) / 6
        u = [q[k] - p[k] for k in range(3)]
        w = [r[k] - p[k] for k in range(3)]
        c = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        area += math.sqrt(sum(x * x for x in c)) / 2
        for pt in (p, q, r):
            for k in range(3):
                lo[k] = min(lo[k], pt[k])
                hi[k] = max(hi[k], pt[k])
    return vol, area, lo + hi


def same(a, b):
    if a.suffix.lower() != ".stl":
        # STEP: compare with the file name (written into several entities) blanked.
        def strip(p):
            name = re.escape(a.stem)
            return re.sub(r"'" + name + r"(-r\d+)?(\.step)?'", "''", p.read_text(errors="ignore"))
        return strip(a) == strip(b)
    va, aa, ba = stl_shape(a)
    vb, ab, bb = stl_shape(b)
    return (abs(va - vb) <= max(0.05, 5e-4 * abs(vb)) and abs(aa - ab) <= max(0.1, 1e-3 * ab)
            and all(abs(x - y) <= 0.01 for x, y in zip(ba, bb)))


def sync():
    changed = []
    for f in sorted(OUT.iterdir()):
        base, ext = f.stem, f.suffix[1:]
        cur = latest(base, ext)
        if cur and same(f, cur[1]):
            continue
        rev = (cur[0] + 1) if cur else 1
        dest = PRINT / f"{base}-r{rev}.{ext}"
        shutil.copyfile(f, dest)
        if cur:
            subprocess.run(["git", "rm", "-q", "-f", str(cur[1])], cwd=HERE, check=False)
            if cur[1].exists():
                cur[1].unlink()
        changed.append(dest.name)
    print("\n".join(changed) if changed else "no print files changed")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "batch"
    if mode == "batch":
        names = sys.argv[2:] or ALL
        OUT.mkdir(parents=True, exist_ok=True)
        for old in OUT.iterdir():
            old.unlink()
        BATCH.write_text(json.dumps({"commands": build(set(names))}))
        print(f"wrote {BATCH} ({len(build(set(names)))} steps)")
    elif mode == "sync":
        sync()
    else:
        sys.exit(__doc__)
