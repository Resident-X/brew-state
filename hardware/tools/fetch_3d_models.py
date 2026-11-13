#!/usr/bin/env python3
"""Fetch the 3D models a picture of a board needs, into a folder git ignores.

usage: fetch_3d_models.py BOARD.kicad_pcb [--cache DIR] [--delay SECONDS] [--offline]

For every footprint of the board that the board gives no model, this reads the footprint's `LCSC`
property and asks the public LCSC / EasyEDA component service, over HTTPS on this machine, for the part's
3D model. A model found is kept in the cache folder (default `3d-cache/` beside the board) by part number,
so a second run downloads nothing. The models are the vendor's: they stay on this machine, are not part of
this repository and are not redistributed, and each carries the licence the service states. The board's
own files are never changed and name no model; render_board_3d.py reads the cache's manifest.json and
adds the models only to a scratch copy it draws.

A vendor model is drawn in the vendor's own frame, which is not the footprint's. Each is therefore
aligned to the footprint's pads (its pins, or the bottom of its leads, against the pad positions, over the four
quarter turns); a model whose pins cannot be matched to every pad is not used. A part with no vendor model, or
whose model did not align, gets a simplified body of the footprint's own, from render_fallback_models.py,
written to the cache too. Test points, fiducials, mounting holes and net ties need no body.

Exit status: 0 on success (parts without a vendor model are reported, not an error), 2 when the board
cannot be read.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import board_models_3d as bm  # noqa: E402
import render_fallback_models as fallback  # noqa: E402

COMPONENT_URL = "https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5"
OBJ_URL = "https://modules.easyeda.com/3dmodel/{uuid}"
STEP_URL = "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}"
# The service refuses a browser's User-Agent and answers a plain client's.
USER_AGENT = "curl/8.7.1"
UNIT_MM = 0.254  # the service draws in 10 mil units

# The sign KiCad's (rotate (xyz 0 0 z)) turns a model by, against the counter-clockwise turn seen from above.
ROT_SIGN = -1.0


# ---------------------------------------------------------------- network
def http_get(url: str, timeout: float = 60.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def extract_model_ref(component: dict) -> Optional[Tuple[str, float]]:
    """The 3D model uuid and its z (mm) from the service's component answer, or None when it has none."""
    try:
        shapes = component["result"]["packageDetail"]["dataStr"]["shape"]
    except (KeyError, TypeError):
        return None
    for shape in shapes:
        if isinstance(shape, str) and shape.startswith("SVGNODE~"):
            try:
                attrs = json.loads(shape[len("SVGNODE~"):])["attrs"]
            except (ValueError, KeyError):
                continue
            if attrs.get("c_etype") == "outline3D" and attrs.get("uuid"):
                return attrs["uuid"], float(attrs.get("z", 0) or 0) * UNIT_MM
    return None


def fetch_vendor(lcsc: str, folder: str, delay: float, offline: bool) -> Tuple[str, str]:
    """Make sure `folder` holds the part's model. Returns (status, detail): status is `cached`, `fetched`,
    `none` (the service has no model for it, kept so it is not asked again) or `error` (not kept)."""
    meta_path = os.path.join(folder, lcsc + ".json")
    step_path = os.path.join(folder, lcsc + ".step")
    obj_path = os.path.join(folder, lcsc + ".obj")
    if os.path.isfile(meta_path):
        meta = json.load(open(meta_path))
        if meta.get("status") == "none":
            return "none", meta.get("detail", "")
        if os.path.isfile(step_path) and os.path.isfile(obj_path):
            return "cached", ""
    if offline:
        return "error", "offline and not cached"
    os.makedirs(folder, exist_ok=True)
    try:
        time.sleep(delay)
        component = json.loads(http_get(COMPONENT_URL.format(lcsc=lcsc)))
        if not component.get("success", True) or not component.get("result"):
            return _remember_none(meta_path, "the service does not know the part")
        ref = extract_model_ref(component)
        if ref is None:
            return _remember_none(meta_path, "the service holds no 3D model for the part")
        uuid, z_mm = ref
        time.sleep(delay)
        step = http_get(STEP_URL.format(uuid=uuid))
        time.sleep(delay)
        obj = http_get(OBJ_URL.format(uuid=uuid))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return _remember_none(meta_path, "404 from the service")
        return "error", f"HTTP {error.code}"
    except (urllib.error.URLError, OSError, ValueError) as error:
        return "error", str(error)
    if not step.startswith(b"ISO-10303") or b"v " not in obj[:4000] + obj[-4000:]:
        return "error", "the service's answer is not a STEP and an OBJ file"
    with open(step_path, "wb") as handle:
        handle.write(step)
    with open(obj_path, "wb") as handle:
        handle.write(obj)
    with open(meta_path, "w") as handle:
        json.dump({"status": "ok", "uuid": uuid, "z_mm": z_mm, "lcsc": lcsc}, handle, indent=1)
    return "fetched", uuid


def _remember_none(meta_path: str, detail: str) -> Tuple[str, str]:
    with open(meta_path, "w") as handle:
        json.dump({"status": "none", "detail": detail}, handle)
    return "none", detail


# ---------------------------------------------------------------- alignment
def _contained(vertices, bounds, tol: float = 0.3) -> bool:
    """The OBJ's extent lies inside the STEP's (whose control points only ever widen it)."""
    cols = list(zip(*vertices))
    return all(bounds[2 * i] - tol <= min(cols[i]) and max(cols[i]) <= bounds[2 * i + 1] + tol for i in range(3))


def read_obj_vertices(path: str) -> List[Tuple[float, float, float]]:
    out = []
    with open(path, errors="replace") as handle:
        for line in handle:
            if line.startswith("v "):
                parts = line.split()
                out.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return out


def step_bounds(path: str) -> Optional[Tuple[float, float, float, float, float, float]]:
    text = open(path, encoding="latin-1").read()
    pts = re.findall(
        r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)", text
    )
    if not pts:
        return None
    cols = list(zip(*[(float(a), float(b), float(c)) for a, b, c in pts]))
    return (min(cols[0]), max(cols[0]), min(cols[1]), max(cols[1]), min(cols[2]), max(cols[2]))


def _rotate(points, quarter: int):
    out = []
    for x, y, *rest in points:
        for _ in range(quarter):
            x, y = -y, x
        out.append((x, y, *rest))
    return out


def _cluster(points: List[Tuple[float, float]], radius: float) -> List[Tuple[float, float]]:
    clusters: List[List[Tuple[float, float]]] = []
    for p in points:
        for c in clusters:
            cx = sum(q[0] for q in c) / len(c)
            cy = sum(q[1] for q in c) / len(c)
            if math.hypot(p[0] - cx, p[1] - cy) <= radius:
                c.append(p)
                break
        else:
            clusters.append([p])
    return [(sum(q[0] for q in c) / len(c), sum(q[1] for q in c) / len(c)) for c in clusters]


def align_model(pads: List[bm.Pad], vertices) -> Tuple[Optional[dict], str]:
    """Find the offset and turn that put the model's pins on the footprint's pads.

    Footprint coordinates have y down; a model's frame has y up, so a pad (x, y) is compared with a model
    point at (x, -y). Returns (placement, note); placement is None when no turn and offset match every pad.
    """
    if not pads or not vertices:
        return None, "no pads or no vertices"
    targets = [(p.x, -p.y, p) for p in pads]
    tht = [p for p in pads if p.kind == "thru_hole"]
    zmin = min(v[2] for v in vertices)
    best = None
    for quarter in range(4):
        rotated = _rotate(vertices, quarter)
        if tht:
            low = [(x, y) for x, y, z in rotated if z < -0.2]
            if not low:
                return None, "the model has no pin below the board surface"
            pins = _cluster(low, 0.8)
            if len(pins) > 40:
                return None, "too many pin clusters"
            sources = pins
            candidates = [(tx - px, ty - py) for (px, py) in pins for (tx, ty, _) in targets]
        else:
            low = [(x, y) for x, y, z in rotated if z <= zmin + 0.15]
            if not low:
                return None, "no bottom vertices"
            sources = low
            pcx = (min(t[0] for t in targets) + max(t[0] for t in targets)) / 2
            pcy = (min(t[1] for t in targets) + max(t[1] for t in targets)) / 2
            mcx = (min(p[0] for p in low) + max(p[0] for p in low)) / 2
            mcy = (min(p[1] for p in low) + max(p[1] for p in low)) / 2
            candidates = [(pcx - mcx, pcy - mcy)]
        for dx, dy in candidates:
            score = _score(targets, sources, dx, dy, bool(tht))
            if best is None or score[0] < best[0][0] or (score[0] == best[0][0] and score[1] < best[0][1]):
                best = (score, quarter, dx, dy)
    score, quarter, dx, dy = best
    missed, total = score[0], score[1]
    if missed > 0:
        return None, f"best fit leaves {missed} of {len(pads)} pads without a pin or lead on them"
    # KiCad turns the model about its own origin and then offsets it; the offset is in the model's frame (y up).
    z_offset = 0.0 if tht or abs(zmin) < 0.05 else -zmin
    return {"offset": [round(dx, 4), round(dy, 4), round(z_offset, 4)], "rotate_z": ROT_SIGN * 90.0 * quarter,
            "quarter": quarter, "fit_error_mm": round(total, 3)}, "aligned"


def _score(targets, sources, dx: float, dy: float, tht: bool) -> Tuple[int, float]:
    """(pads missed, summed distance) of the pads against the model's pins or leads moved by (dx, dy)."""
    missed = 0
    total = 0.0
    for tx, ty, pad in targets:
        if tht:
            d = min(math.hypot(sx + dx - tx, sy + dy - ty) for sx, sy in sources)
            if d > 0.4:
                missed += 1
            total += d
        else:
            hx, hy = pad.w / 2 + 0.15, pad.h / 2 + 0.15
            inside = [s for s in sources if abs(s[0] + dx - tx) <= hx and abs(s[1] + dy - ty) <= hy]
            if not inside:
                missed += 1
                total += 1.0
            else:
                total += min(math.hypot(s[0] + dx - tx, s[1] + dy - ty) for s in inside)
    if tht:
        # a pin with no pad under it also counts against the fit
        for sx, sy in sources:
            if min(math.hypot(sx + dx - tx, sy + dy - ty) for tx, ty, _ in targets) > 0.6:
                missed += 1
    return missed, total


# ---------------------------------------------------------------- fallback bodies
def fallback_model(fp: bm.Footprint, folder: str) -> Tuple[Optional[str], str]:
    """Write our own simplified body for the footprint into `folder`; returns (file name, how)."""
    os.makedirs(folder, exist_ok=True)
    name = fp.short_name
    safe = re.sub(r"[^A-Za-z0-9_.+-]", "_", name)
    if name in fallback.PARTS:
        path = os.path.join(folder, safe + ".step")
        fallback.write_step(path, name, fallback.PARTS[name]())
        return os.path.join("fallback", safe + ".step"), "simplified body from render_fallback_models.py"
    box = fp.courtyard
    if box is None:
        xs = [p.x for p in fp.pads]
        ys = [p.y for p in fp.pads]
        box = (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)
    path = os.path.join(folder, safe + ".step")
    fallback.write_step(
        path, name, [fallback.box(box[0], box[2], box[1], box[3], 0.3, 2.0, fallback.BLACK)]
    )
    return os.path.join("fallback", safe + ".step"), "generic block over the courtyard, 2 mm high"


# ---------------------------------------------------------------- main
def run(board: str, cache: str, delay: float, offline: bool, out=sys.stdout) -> dict:
    text = open(board, encoding="utf-8").read()
    footprints = bm.read_footprints(text)
    manifest: Dict[str, dict] = {}
    vendor_dir = os.path.join(cache, "vendor")
    fallback_dir = os.path.join(cache, "fallback")
    seen: Dict[str, bm.Footprint] = {}
    for fp in footprints:
        if fp.has_model:
            continue
        seen.setdefault(fp.lib_id + "|" + fp.lcsc, fp)
    for key, fp in sorted(seen.items()):
        entry: dict = {"lib_id": fp.lib_id, "lcsc": fp.lcsc}
        users = sorted(f.reference for f in footprints if f.lib_id == fp.lib_id and f.lcsc == fp.lcsc and not f.has_model)
        entry["references"] = users
        if not fp.has_body:
            entry.update(source="none", note="no physical body")
            manifest[key] = entry
            continue
        reason = "no LCSC part number"
        if re.fullmatch(r"C\d+", fp.lcsc):
            status, detail = fetch_vendor(fp.lcsc, vendor_dir, delay, offline)
            reason = detail or status
            if status in ("cached", "fetched"):
                vertices = read_obj_vertices(os.path.join(vendor_dir, fp.lcsc + ".obj"))
                bounds = step_bounds(os.path.join(vendor_dir, fp.lcsc + ".step"))
                zs = [v[2] for v in vertices]
                if bounds is None or not vertices or not _contained(vertices, bounds):
                    reason = "the STEP and the OBJ the service gave do not share a frame"
                else:
                    placement, note = align_model(fp.pads, vertices)
                    if placement is not None:
                        entry.update(source="vendor", file=os.path.join("vendor", fp.lcsc + ".step"),
                                     offset=placement["offset"], rotate=[0.0, 0.0, placement["rotate_z"]],
                                     fit_error_mm=placement["fit_error_mm"], note=f"vendor model ({status})")
                        manifest[key] = entry
                        continue
                    reason = "vendor model does not align to the pads: " + note
            elif status == "error":
                reason = "download failed: " + detail
            else:
                reason = "no vendor model: " + detail
        path, how = fallback_model(fp, fallback_dir)
        entry.update(source="fallback", file=path, offset=[0.0, 0.0, 0.0], rotate=[0.0, 0.0, 0.0],
                     note=f"{how}; {reason}")
        manifest[key] = entry
    os.makedirs(cache, exist_ok=True)
    with open(os.path.join(cache, "manifest.json"), "w") as handle:
        json.dump(manifest, handle, indent=1, sort_keys=True)
    counts = {"vendor": 0, "fallback": 0, "none": 0}
    for key, entry in sorted(manifest.items(), key=lambda kv: (kv[1]["source"], kv[0])):
        counts[entry["source"]] += 1
        print(f"{entry['source']:8s} {entry['lib_id']} {entry['lcsc'] or '-'} "
              f"[{', '.join(entry['references'][:6])}{'...' if len(entry['references']) > 6 else ''}] {entry['note']}", file=out)
    print(f"footprint kinds without a model in the board: {len(manifest)}; vendor {counts['vendor']}, "
          f"own simplified body {counts['fallback']}, no body needed {counts['none']}", file=out)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("board")
    parser.add_argument("--cache", help="cache folder (default: 3d-cache beside the board)")
    parser.add_argument("--delay", type=float, default=0.6, help="seconds before each request (default 0.6)")
    parser.add_argument("--offline", action="store_true", help="use only what the cache holds")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.board):
        print(f"no such board file: {args.board}", file=sys.stderr)
        return 2
    cache = args.cache or os.path.join(os.path.dirname(os.path.abspath(args.board)), "3d-cache")
    run(args.board, cache, args.delay, args.offline)
    return 0


if __name__ == "__main__":
    sys.exit(main())
