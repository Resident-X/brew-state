#!/usr/bin/env python3
"""Draw 3D pictures of a board, with a model on every part that has a body, without changing the board.

usage: render_board_3d.py BOARD.kicad_pcb OUT_DIR [--cache DIR] [--size WxH] [--views top,bottom,angled,angled_opposite,low_side,side]
                          [--close-up REF[:ZOOM][,REF...]] [--quality basic|high] [--kicad-cli PATH]

Makes a scratch copy of the board in OUT_DIR, adds a `(model ...)` block to each footprint that has none
(from the manifest fetch_3d_models.py wrote into the cache folder; run that first), runs
`kicad-cli pcb render` on the copy and writes one PNG per view into OUT_DIR. The board file given is only
read. A footprint that already names a model (the library's stock models, through
${KICAD10_3DMODEL_DIR}) keeps it. `--close-up` draws the parts named, each at a larger scale from above and from an angle.
The pictures are for looking at: the vendor models they use are not part of the repository.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import board_models_3d as bm  # noqa: E402

DEFAULT_KICAD_DIRS = (
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels",
    "/usr/share/kicad/3dmodels",
    "/usr/local/share/kicad/3dmodels",
)
GLB_DETAIL = {
    "full": ["--include-tracks", "--include-pads", "--include-zones", "--include-silkscreen", "--include-soldermask"],
    "light": ["--include-pads", "--include-silkscreen", "--include-soldermask"],
    "minimal": ["--include-pads", "--include-silkscreen", "--min-distance", "0.1mm"],
    "nosilk": ["--include-pads", "--include-soldermask"],
}
ANGLES = {
    "angled": ["--rotate", "-45,0,45", "--perspective"],
    "angled_opposite": ["--rotate", "-45,0,225", "--perspective"],
    "low_side": ["--rotate", "-78,0,20", "--perspective"],
    "top": ["--side", "top"],
    "bottom": ["--side", "bottom"],
    "side": ["--side", "front"],
}


def model_blocks(text: str, manifest: dict, cache: str, model_dir: str = ""):
    """Model blocks for the footprints of `text` that lack one, by footprint order, and a report of the rest."""
    footprints = bm.read_footprints(text)
    blocks, report = {}, {"stock": 0, "vendor": 0, "fallback": 0, "none": 0, "unlisted": []}
    for index, fp in enumerate(footprints):
        if fp.has_usable_model(model_dir):
            report["stock"] += 1
            continue
        entry = manifest.get(fp.lib_id + "|" + fp.lcsc)
        if entry is None:
            report["unlisted"].append(fp.reference)
        elif entry["source"] == "none":
            report["none"] += 1
        elif entry["source"] == "stock":
            report["stock"] += 1
            blocks[index] = entry["block"]
        else:
            report[entry["source"]] += 1
            blocks[index] = bm.model_line(
                os.path.abspath(os.path.join(cache, entry["file"])), entry["offset"], entry["rotate"]
            )
    return blocks, report


TOOL_PACKAGES = ("numpy==2.5.4", "trimesh==5.2.1", "fast-simplification==0.2.0", "pillow==13.0.0")


def tool_python(cache: str) -> str:
    """Python of a virtual environment in the cache folder holding the packages glb_simplify.py needs,
    made (from PyPI, on this machine) the first time it is asked for."""
    env = os.path.join(cache, "venv")
    python = os.path.join(env, "Scripts" if os.name == "nt" else "bin", "python")
    marker = os.path.join(env, ".packages")
    if os.path.isfile(python) and os.path.isfile(marker) and open(marker).read() == " ".join(TOOL_PACKAGES):
        return python
    subprocess.run([sys.executable, "-m", "venv", env], check=True)
    subprocess.run([python, "-m", "pip", "install", "-q", *TOOL_PACKAGES], check=True)
    with open(marker, "w") as handle:
        handle.write(" ".join(TOOL_PACKAGES))
    return python


def find_model_dir() -> str:
    env = os.environ.get("KICAD10_3DMODEL_DIR")
    if env:
        return env
    for path in DEFAULT_KICAD_DIRS:
        if os.path.isdir(path):
            return path
    return ""


def find_kicad_cli(given: str) -> str:
    if given:
        return given
    for candidate in (os.environ.get("KICAD_CLI"), shutil.which("kicad-cli"),
                      "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"):
        if candidate and (os.path.isfile(candidate) or shutil.which(candidate)):
            return candidate
    raise SystemExit("kicad-cli not found: pass --kicad-cli or set KICAD_CLI")


def render(kicad_cli: str, scratch: str, output: str, width: int, height: int, quality: str, extra, env) -> None:
    cmd = [kicad_cli, "pcb", "render", "--width", str(width), "--height", str(height), "--quality", quality,
           "--background", "opaque", "--output", output, *extra, scratch]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(output):
        raise SystemExit(f"kicad-cli failed for {output}:\n{result.stdout}\n{result.stderr}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("board")
    parser.add_argument("out")
    parser.add_argument("--cache")
    parser.add_argument("--size", default="1800x1100")
    parser.add_argument("--views", default="top,bottom,angled,angled_opposite,low_side")
    parser.add_argument("--close-up", default="")
    parser.add_argument("--collisions", action="store_true",
                        help="also write collisions.txt: pairs of parts on one side of the board whose bodies overlap or "
                             "stand closer than 0.3 mm, judged from the models the pictures use (board_collisions_3d.py)")
    parser.add_argument("--close-up-bottom", default="",
                        help="parts to draw close from below (a part soldered on the back, like the tank reed)")
    parser.add_argument("--glb", default="", help="also write the scratch board as a GLB file for an interactive viewer")
    parser.add_argument("--simplify", action="store_true",
                        help="with --glb: merge by colour, quantise, draw the mask opaque (glb_simplify.py); writes "
                             "the simplified file as the --glb file and the raw export beside it as .raw.glb")
    parser.add_argument("--glb-detail", default="light", choices=tuple(GLB_DETAIL),
                        help="full: copper, silkscreen and mask; light: no tracks or zones; minimal: light, coarser mesh")
    parser.add_argument("--quality", default="basic", choices=("basic", "high"))
    parser.add_argument("--kicad-cli", default="")
    args = parser.parse_args(argv)
    cache = args.cache or os.path.join(os.path.dirname(os.path.abspath(args.board)), "3d-cache")
    manifest_path = os.path.join(cache, "manifest.json")
    if not os.path.isfile(manifest_path):
        print(f"no {manifest_path}: run fetch_3d_models.py on the board first", file=sys.stderr)
        return 2
    manifest = json.load(open(manifest_path))
    width, height = (int(v) for v in args.size.lower().split("x"))
    text = open(args.board, encoding="utf-8").read()
    model_dir = find_model_dir()
    blocks, report = model_blocks(text, manifest, cache, model_dir)
    os.makedirs(args.out, exist_ok=True)
    scratch = os.path.join(args.out, "scratch-" + os.path.basename(args.board))
    with open(scratch, "w", encoding="utf-8") as handle:
        handle.write(bm.inject_models(text, blocks))
    env = dict(os.environ)
    if model_dir:
        env["KICAD10_3DMODEL_DIR"] = model_dir
    kicad_cli = find_kicad_cli(args.kicad_cli)
    if args.glb:
        glb = [kicad_cli, "pcb", "export", "glb", "--force", "--subst-models", *GLB_DETAIL[args.glb_detail],
               "--output", args.glb, scratch]
        result = subprocess.run(glb, env=env, capture_output=True, text=True)
        if result.returncode != 0 or not os.path.isfile(args.glb):
            raise SystemExit(f"kicad-cli GLB export failed:\n{result.stdout}\n{result.stderr}")
        print("wrote", args.glb, os.path.getsize(args.glb), "bytes")
        if args.simplify:
            raw = args.glb[:-4] + ".raw.glb" if args.glb.endswith(".glb") else args.glb + ".raw"
            os.replace(args.glb, raw)
            python = tool_python(cache)
            done = subprocess.run([python, os.path.join(HERE, "glb_simplify.py"), raw, args.glb],
                                  capture_output=True, text=True)
            if done.returncode != 0:
                raise SystemExit("glb_simplify.py failed:\n" + done.stdout + done.stderr)
            print("wrote", args.glb, os.path.getsize(args.glb), "bytes simplified;", done.stdout.strip())
    if args.collisions:
        glb = os.path.join(args.out, "collisions.glb")
        result = subprocess.run([kicad_cli, "pcb", "export", "glb", "--force", "--subst-models", "--min-distance", "0.1mm",
                                 "--output", glb, scratch], env=env, capture_output=True, text=True)
        if result.returncode != 0 or not os.path.isfile(glb):
            raise SystemExit(f"kicad-cli GLB export failed:\n{result.stdout}\n{result.stderr}")
        flags_path = os.path.join(args.out, "collisions-flags.json")
        with open(flags_path, "w") as handle:
            json.dump(hand_fitted(bm.read_footprints(text)), handle, indent=1, sort_keys=True)
        done = subprocess.run([tool_python(cache), os.path.join(HERE, "board_collisions_3d.py"), glb, "--flags", flags_path],
                              capture_output=True, text=True)
        if done.returncode != 0:
            raise SystemExit("board_collisions_3d.py failed:\n" + done.stdout + done.stderr)
        with open(os.path.join(args.out, "collisions.txt"), "w") as handle:
            handle.write(done.stdout)
        print("wrote", os.path.join(args.out, "collisions.txt"), "-", done.stdout.strip().splitlines()[-1])
    for view in [v for v in args.views.split(",") if v]:
        render(kicad_cli, scratch, os.path.join(args.out, view + ".png"), width, height, args.quality, ANGLES[view], env)
        print("wrote", os.path.join(args.out, view + ".png"))
    footprints = {fp.reference: fp for fp in bm.read_footprints(text)}
    for spec in [r for r in args.close_up.split(",") if r]:
        ref, _, zoom_text = spec.partition(":")
        zoom = float(zoom_text) if zoom_text else 4.0
        fp = footprints.get(ref)
        if fp is None:
            print(f"no footprint {ref}", file=sys.stderr)
            continue
        for name, extra, tilt in (("top", ANGLES["top"], 0.0), ("angled", ["--rotate", "-50,0,0"], 50.0)):
            render(kicad_cli, scratch, os.path.join(args.out, f"closeup-{ref}-{name}.png"), width, height,
                   args.quality, extra + close_up_args(text, fp, zoom, tilt=tilt), env)
            print("wrote", os.path.join(args.out, f"closeup-{ref}-{name}.png"))
    for spec in [r for r in args.close_up_bottom.split(",") if r]:
        ref, _, zoom_text = spec.partition(":")
        zoom = float(zoom_text) if zoom_text else 4.0
        fp = footprints.get(ref)
        if fp is None:
            print(f"no footprint {ref}", file=sys.stderr)
            continue
        name = os.path.join(args.out, f"closeup-{ref}-bottom.png")
        render(kicad_cli, scratch, name, width, height, args.quality, ANGLES["bottom"] + close_up_args(text, fp, zoom, mirror=True), env)
        print("wrote", name)
    print(f"models: stock {report['stock']}, vendor {report['vendor']}, own simplified {report['fallback']}, "
          f"no body {report['none']}, unlisted {len(report['unlisted'])} {report['unlisted']}")
    return 0


HAND_FITTED_MARKS = (("Relay", "relay"), ("RELAY", "relay"), ("Fuse", "fuse holder or clips"), ("FUSEHOLDER", "fuse holder"),
                     ("Tab_", "blade tab"), ("REED", "reed"), ("Converter_ACDC", "module"), ("WireLink", "wire link"))


def hand_fitted(footprints) -> dict:
    """Reference -> kind for the parts the owner fits by hand or that stand tall and loose: relays, fuse holders and
    clips, blade tabs, the reed, the mains module and the wire links."""
    out = {}
    for fp in footprints:
        for mark, kind in HAND_FITTED_MARKS:
            if mark in fp.lib_id and "Resistor" not in fp.lib_id and "Fuse_" not in fp.lib_id:
                out[fp.reference] = kind
                break
    return out


def board_centre(text: str):
    """Centre of the board's edge cuts, in mm, from its gr_ items on Edge.Cuts."""
    import re
    xs, ys = [], []
    for block in re.findall(r"\(gr_(?:rect|line|arc|circle|poly)\b.*?Edge\.Cuts", text, re.S):
        nums = re.findall(r"\((?:start|end|mid|center|xy) (-?[\d.]+) (-?[\d.]+)\)", block)
        xs += [float(a) for a, _ in nums]
        ys += [float(b) for _, b in nums]
    if not xs:
        return 0.0, 0.0, 100.0
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(max(xs) - min(xs), max(ys) - min(ys))


def body_centre(fp: bm.Footprint):
    """The centre of the footprint's courtyard (else its pads) in board coordinates, turned by the footprint's
    rotation (counter-clockwise on screen, y down) and mirrored in x for a footprint on the back."""
    if fp.courtyard is not None:
        lx, ly = (fp.courtyard[0] + fp.courtyard[2]) / 2, (fp.courtyard[1] + fp.courtyard[3]) / 2
    elif fp.pads:
        lx, ly = (min(p.x for p in fp.pads) + max(p.x for p in fp.pads)) / 2, (min(p.y for p in fp.pads) + max(p.y for p in fp.pads)) / 2
    else:
        return fp.x, fp.y
    if fp.layer.startswith("B."):
        lx = -lx
    a = math.radians(fp.rot)
    return fp.x + lx * math.cos(a) + ly * math.sin(a), fp.y - lx * math.sin(a) + ly * math.cos(a)


def close_up_args(text: str, fp: bm.Footprint, zoom: float = 4.0, tilt: float = 0.0, mirror: bool = False):
    """kicad-cli's --pan is in centimetres of the board, positive x moving the board right and positive y up
    (measured by shifting a render), from a view centred on the board's edge cuts; `tilt` is the camera's
    tilt from straight above in degrees (`mirror` for a view from below), which foreshortens the y shift by its cosine."""
    cx, cy, _ = board_centre(text)
    px, py = body_centre(fp)
    sign = -1.0 if mirror else 1.0  # seen from below the board's x runs the other way
    return ["--zoom", f"{zoom:.2f}", "--pan", f"{sign * (cx - px) / 10:.3f},{(py - cy) / 10 * math.cos(math.radians(tilt)):.3f},0"]


if __name__ == "__main__":
    sys.exit(main())
