#!/usr/bin/env python3
"""Fetch the 3D models a picture of a board needs, into a folder git ignores.

usage: fetch_3d_models.py BOARD.kicad_pcb [--cache DIR] [--delay SECONDS] [--offline]

For every footprint of the board that the board gives no model, this first looks for the model KiCad's own
footprint library gives that footprint (a board written without its stock models still draws them), and for
the rest reads the footprint's `LCSC`
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

# These are the unofficial endpoints of a vendor's web editor, not a documented API. The service answers a
# plain client's User-Agent and refuses a browser's. The opaque path token in STEP_URL and the version string
# in COMPONENT_URL were observed from the service and can change or stop working at any time. The models it
# returns are the vendor's property under the service's own terms: they are cached in an ignored directory and
# never committed. This command is run on demand, and whoever runs it answers for the service's terms.
COMPONENT_URL = "https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5"
OBJ_URL = "https://modules.easyeda.com/3dmodel/{uuid}"
STEP_URL = "https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{uuid}"
# The service refuses a browser's User-Agent and answers a plain client's.
USER_AGENT = "curl/8.7.1"
UNIT_MM = 0.254  # the service draws in 10 mil units
NONE_TTL_SECONDS = 24 * 3600  # how long "the service has no model" is believed

# A footprint whose part has no catalogue number of its own is drawn from the model of the catalogue part it
# stands for: the HF115F-I/005-1HS3A is in the catalogue (C2976795), so a board that gives the footprint no
# number still gets the part's own model.
DONOR_PARTS = {"Relay_HF115F-I_1HS3A": "C2976795"}

# The sign KiCad's (rotate (xyz 0 0 z)) turns a model by, against the counter-clockwise turn seen from above.
ROT_SIGN = -1.0


# ---------------------------------------------------------------- network
def http_get(url: str, timeout: float = 60.0, attempts: int = 3) -> bytes:
    """The body of `url`; a timeout, a dropped connection or a 5xx/429 answer is tried again, with a pause that
    doubles, before the error is raised. Any other HTTP error (a 404 says the service has no such file) is raised at once."""
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, OSError):
            if attempt == attempts - 1:
                raise
        time.sleep(2.0 * 2**attempt)
    raise OSError("unreachable")


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


def fetch_vendor(lcsc: str, folder: str, delay: float, offline: bool, retry_none: bool = False) -> Tuple[str, str]:
    """Make sure `folder` holds the part's model. Returns (status, detail): status is `cached`, `fetched`,
    `none` (the service has no model for it, kept for a day so it is not asked again, or asked again at once with
    `retry_none`) or `error` (not kept)."""
    meta_path = os.path.join(folder, lcsc + ".json")
    step_path = os.path.join(folder, lcsc + ".step")
    obj_path = os.path.join(folder, lcsc + ".obj")
    if os.path.isfile(meta_path):
        meta = json.load(open(meta_path))
        if meta.get("status") == "none" and not retry_none and time.time() - meta.get("at", 0) < NONE_TTL_SECONDS:
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
        json.dump({"status": "none", "detail": detail, "at": time.time()}, handle)
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
    """Centres of the groups of points joined by steps of at most `radius` (single linkage), each group's
    bounding-box centre, so a pin drawn as two prongs or a wide blade is one pin."""
    groups: List[List[Tuple[float, float]]] = []
    for p in points:
        joined = [g for g in groups if any(math.hypot(p[0] - q[0], p[1] - q[1]) <= radius for q in g)]
        merged = [p]
        for g in joined:
            merged.extend(g)
            groups.remove(g)
        groups.append(merged)
    return [((min(q[0] for q in g) + max(q[0] for q in g)) / 2, (min(q[1] for q in g) + max(q[1] for q in g)) / 2)
            for g in groups]


BOARD_THICKNESS = 1.6
PIN_TOLERANCE = 0.5  # how far a pin may stand from its pad's centre, mm (the most a vendor model's fit error may be)
OVERSHOOT_LIMIT = 1.0  # how far a vendor model's body may stand outside the footprint's courtyard, mm
# Footprints whose part number is a body the footprint does not draw as the vendor does (F101's leads are formed
# to the footprint's 28.0 mm pitch where the vendor model's are straight): drawn from our own body, whatever the
# service holds under that number.
OWN_ONLY = {"Fuse_SETfuse_SCT520PT_Axial_P28.0mm"}


def align_model(pads: List[bm.Pad], vertices, courtyard=None) -> Tuple[Optional[dict], str]:
    """Find the offset and turn that put the model's pins on the footprint's pads.

    Footprint coordinates have y down; a model's frame has y up, so a pad (x, y) is compared with a model
    point at (x, -y). A through-hole part is tried with the model's origin on the board surface (its pins
    the points below z = -0.2) and, for a model drawn about its own middle (one reaching more than 4.6 mm below
    its origin, tried first), with its lowest 1.9 mm taken as the pin and the whole model moved so that pin ends
    at the board's underside. Returns (placement, note);
    placement is None when no turn and offset match every pad.
    """
    if not pads or not vertices:
        return None, "no pads or no vertices"
    tht = [p for p in pads if p.kind == "thru_hole"]
    zmin = min(v[2] for v in vertices)
    modes = [("surface", 0.0)] if not tht else [("surface", 0.0), ("tail", -BOARD_THICKNESS - zmin)]
    if tht and zmin < -(BOARD_THICKNESS + 3.0):  # pins far longer than a board is thick: drawn about the middle
        modes.reverse()
    notes = []
    for mode, z_move in modes:
        if mode == "tail" and zmin > -2.0:
            continue
        placement, note = _align(pads, vertices, bool(tht), mode, z_move, zmin, courtyard)
        if placement is not None:
            return placement, note
        notes.append(note)
    return None, "; ".join(notes)


def _align(pads, vertices, tht: bool, mode: str, z_move: float, zmin: float, courtyard=None):
    targets = [(p.x, -p.y, p) for p in pads]
    best = None
    for quarter in range(4):
        rotated = _rotate(vertices, quarter)
        if tht:
            low = [(x, y) for x, y, z in rotated if (z < -0.2 if mode == "surface" else z < zmin + 1.9)]
            if not low:
                return None, "the model has no pin below the board surface"
            sources = _cluster(low, 1.4 if len(pads) > 1 else 10.0)
            if len(sources) > 40:
                return None, "too many pin clusters"
            candidates = [(tx - px, ty - py) for (px, py) in sources for (tx, ty, _) in targets]
            if len(sources) == len(targets):  # a maker's pin pitch a little off the footprint's: centre the one on the other
                candidates.append((sum(t[0] for t in targets) / len(targets) - sum(q[0] for q in sources) / len(sources),
                                   sum(t[1] for t in targets) / len(targets) - sum(q[1] for q in sources) / len(sources)))
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
            missed, total = _score(targets, sources, dx, dy, tht)
            score = (missed, _overshoot(rotated, dx, dy, courtyard) + total)
            if best is None or score < best[0]:
                best = (score, quarter, dx, dy, sources)
    score, quarter, dx, dy, sources = best
    missed, total = score[0], score[1]
    if missed > 0:
        return None, f"{mode} fit leaves {missed} of {len(pads)} pads without a pin or lead on them"
    # KiCad turns the model about its own origin and then offsets it; the offset is in the model's frame (y up).
    z_offset = z_move if tht else (0.0 if abs(zmin) < 0.05 else -zmin)
    rotated = _rotate(vertices, quarter)
    fit = max((min(math.hypot(sx + dx - tx, sy + dy - ty) for sx, sy in sources) for tx, ty, _ in targets), default=0.0) \
        if tht else 0.0
    return {"offset": [round(dx, 4), round(dy, 4), round(z_offset, 4)], "rotate_z": ROT_SIGN * 90.0 * quarter,
            "quarter": quarter, "fit_error_mm": round(fit, 3),
            "overshoot_mm": round(_overshoot(rotated, dx, dy, courtyard), 3)}, "aligned"


def _overshoot(rotated, dx: float, dy: float, courtyard) -> float:
    """How far the model's outline, moved by (dx, dy), stands outside the footprint's courtyard (zero without
    one); among turns that put the pins on the pads it picks the one that keeps the body inside."""
    if courtyard is None:
        return 0.0
    xs = [x + dx for x, _, _ in rotated]
    ys = [-(y + dy) for _, y, _ in rotated]
    x0, y0, x1, y1 = courtyard
    return max(0.0, x0 - min(xs)) + max(0.0, max(xs) - x1) + max(0.0, y0 - min(ys)) + max(0.0, max(ys) - y1)


def _score(targets, sources, dx: float, dy: float, tht: bool) -> Tuple[int, float]:
    """(pads missed, summed distance) of the pads against the model's pins or leads moved by (dx, dy)."""
    missed = 0
    total = 0.0
    for tx, ty, pad in targets:
        if tht:
            d = min(math.hypot(sx + dx - tx, sy + dy - ty) for sx, sy in sources)
            if d > PIN_TOLERANCE:
                missed += 1
            total += d
        elif pad.w < 1.0 and pad.h < 1.0 and any(t[2].w >= 1.0 or t[2].h >= 1.0 for t in targets):
            continue  # a sense pad beside the terminals: the maker's model has no lead on it
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
    path = os.path.join(folder, safe + ".wrl")
    if name in fallback.PARTS:
        fallback.write_wrl(path, name, fallback.PARTS[name]())
        return os.path.join("fallback", safe + ".wrl"), "simplified body from render_fallback_models.py"
    box = fp.courtyard
    if box is None:
        xs = [p.x for p in fp.pads]
        ys = [p.y for p in fp.pads]
        box = (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)
    height = 5.0 if any(p.kind == "thru_hole" for p in fp.pads) else 2.0
    fallback.write_wrl(path, name, [fallback.body(box[0], box[2], box[1], box[3], 0.3, height, "body", chamfer=0.2)])
    return os.path.join("fallback", safe + ".wrl"), f"generic block over the courtyard, {height:g} mm high"


# ---------------------------------------------------------------- main
def run(board: str, cache: str, delay: float, offline: bool, out=sys.stdout, retry_none: bool = False,
        own: Tuple[str, ...] = ()) -> dict:
    text = open(board, encoding="utf-8").read()
    footprints = bm.read_footprints(text)
    manifest: Dict[str, dict] = {}
    vendor_dir = os.path.join(cache, "vendor")
    fallback_dir = os.path.join(cache, "fallback")
    seen: Dict[str, bm.Footprint] = {}
    footprint_dir = bm.find_dir("KICAD10_FOOTPRINT_DIR", bm.DEFAULT_FOOTPRINT_DIRS)
    model_dir = bm.find_dir("KICAD10_3DMODEL_DIR", bm.DEFAULT_MODEL_DIRS)
    for fp in footprints:
        if fp.has_usable_model(model_dir):
            continue
        seen.setdefault(fp.lib_id + "|" + fp.lcsc, fp)
    for key, fp in sorted(seen.items()):
        entry: dict = {"lib_id": fp.lib_id, "lcsc": fp.lcsc}
        users = sorted(f.reference for f in footprints if f.lib_id == fp.lib_id and f.lcsc == fp.lcsc and not f.has_usable_model(model_dir))
        entry["references"] = users
        if not fp.has_body:
            entry.update(source="none", note="no physical body")
            manifest[key] = entry
            continue
        stock = bm.stock_model_block(fp.lib_id, footprint_dir, model_dir)
        if stock is not None:
            entry.update(source="stock", block=stock, note="KiCad's own library model")
            manifest[key] = entry
            continue
        reason = "own body asked for" if ("all" in own or fp.short_name in own) else "no LCSC part number"
        part = "" if ("all" in own or fp.short_name in own or fp.short_name in OWN_ONLY) else fp.lcsc if re.fullmatch(r"C\d+", fp.lcsc) else DONOR_PARTS.get(fp.short_name, "")
        if part:
            status, detail = fetch_vendor(part, vendor_dir, delay, offline, retry_none)
            reason = detail or status
            if status in ("cached", "fetched"):
                vertices = read_obj_vertices(os.path.join(vendor_dir, part + ".obj"))
                bounds = step_bounds(os.path.join(vendor_dir, part + ".step"))
                zs = [v[2] for v in vertices]
                if bounds is None or not vertices or not _contained(vertices, bounds):
                    reason = "the STEP and the OBJ the service gave do not share a frame"
                else:
                    placement, note = align_model(fp.pads, vertices, fp.courtyard)
                    if placement is not None and placement["fit_error_mm"] > PIN_TOLERANCE:
                        placement, note = None, f"fit error {placement['fit_error_mm']} mm is over {PIN_TOLERANCE} mm"
                    if placement is not None and placement["overshoot_mm"] > OVERSHOOT_LIMIT:
                        placement, note = None, (f"the body stands {placement['overshoot_mm']} mm outside the courtyard, "
                                                 f"over {OVERSHOOT_LIMIT} mm")
                    if placement is not None:
                        entry.update(source="vendor", file=os.path.join("vendor", part + ".step"),
                                     offset=placement["offset"], rotate=[0.0, 0.0, placement["rotate_z"]],
                                     fit_error_mm=placement["fit_error_mm"], overshoot_mm=placement["overshoot_mm"], note=f"vendor model {part} ({status})")
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
    counts = {"stock": 0, "vendor": 0, "fallback": 0, "none": 0}
    for key, entry in sorted(manifest.items(), key=lambda kv: (kv[1]["source"], kv[0])):
        counts[entry["source"]] += 1
        fit = (f" fit error {entry['fit_error_mm']} mm, {entry['overshoot_mm']} mm outside the courtyard"
               if entry["source"] == "vendor" else "")
        flag = "GENERIC BLOCK, no maker model and no body of our own: " if "generic block" in entry.get("note", "") else ""
        print(f"{entry['source']:8s} {flag}{entry['lib_id']} {entry['lcsc'] or '-'} "
              f"[{', '.join(entry['references'][:6])}{'...' if len(entry['references']) > 6 else ''}] {entry['note']}{fit}", file=out)
    print(f"footprint kinds without a model in the board: {len(manifest)}; KiCad stock {counts['stock']}, vendor {counts['vendor']}, "
          f"own simplified body {counts['fallback']}, no body needed {counts['none']}", file=out)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("board")
    parser.add_argument("--cache", help="cache folder (default: 3d-cache beside the board)")
    parser.add_argument("--delay", type=float, default=0.6, help="seconds before each request (default 0.6)")
    parser.add_argument("--retry-none", action="store_true",
                        help="ask the service again for parts it earlier said it holds no model for")
    parser.add_argument("--own", default="",
                        help="footprint names (or `all`) to draw with the repository's own simplified body "
                             "even where a vendor model aligns, comma separated")
    parser.add_argument("--offline", action="store_true", help="use only what the cache holds")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.board):
        print(f"no such board file: {args.board}", file=sys.stderr)
        return 2
    cache = args.cache or os.path.join(os.path.dirname(os.path.abspath(args.board)), "3d-cache")
    run(args.board, cache, args.delay, args.offline, retry_none=args.retry_none,
        own=tuple(n for n in args.own.split(",") if n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
