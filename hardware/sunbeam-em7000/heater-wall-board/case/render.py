#!/usr/bin/env python3
"""Offscreen renders of the printed case, written to renders/.

    python render.py                          the six views of the three forms (single colour in bone, single colour in the alternate
                                              colour, two colour) of the default skin, renders/<form>-<view>.png
    python render.py --form stone             one form (single, the alternate colour's name from params.yaml `forms.single.alternate_name`,
                                              or two)
    python render.py --view top               one view (far-end, top, plate-end, underside, exploded, lid-off)
    python render.py --skin flow              the same views of the named skin
    python render.py --directions             the installed set: the skin, the three forms, the views above, below, below-lit, side, lid and
                                              tray-top of the assembled case on its plate in its installed orientation (plate vertical
                                              like a wall, tray up, lid down), the logo close-ups logo-lid-30, logo-lid-60, logo-top-30
                                              and logo-top-60, renders/directions/<skin>-<form>-<view>.png, a contact sheet
                                              renders/directions/contact-sheet.png (a row a form, bone then the alternate colour then two colour, a column a view) and a logo sheet
                                              renders/directions/logo-sheet.png (a row a form, a column a close-up)
    python render.py --directions --direction-form two --direction-view logo-top-30
                                              one image alone; `--direction-form` and a repeated `--direction-view` split a full run
                                              into pieces (no sheet is made then), and `--sheet-only` makes both sheets from the
                                              images already drawn

Everything is drawn in the right-handed PHYSICAL frame (case.PHYSICAL: X = u, Y = -v, Z = z), the frame the exports are written in, so
each image is a true view of the object that will be printed, from the place its name says. The model frame (u, v, z) is left-handed and
never reaches the renderer: every mesh and every point goes through the one reflection (`case.physical_mesh`, `physical_poly`, `phys`),
the winding fixed, and the camera positions, focal points, up vectors and light directions below, written in the model frame, are
reflected by `camera_for` and the lights. The views straight at a logo face are drawn as the installed viewer in front of the wall sees
them: the lid view and the lid close-ups have the wall at the bottom of the picture (+v up the page), the top view and the top close-ups
have the wall at the top; in both, +u is to the left.

The alternate single colour is the single-colour form's own geometry (its tray and lid and its meshes) drawn in
`forms.single.alternate_colour`; its images are renders/<name>-<view>.png and renders/directions/<skin>-<name>-<view>.png.

Each image is 1600 x 1200: smooth shading with normals split at a 30 degree feature angle and no edge lines, three-point soft
lighting, screen-space ambient occlusion where the machine's graphics stack allows it, anti-aliasing, a light grey gradient
behind the part and a perspective camera (the lid and tray-top views are orthographic). The directions are drawn with installed up
on the page: the case frame's +z points down, so the cameras take (0, 0, -1) as up, read from params.yaml `installed`. The board and
its parts are drawn in every view, inside the case. The tray and lid carry the form's colours from params.yaml and are matte
plastic; the plate is brushed aluminium, the film amber, the board and its parts muted.

The two-colour form is drawn as it prints. Each part prints outer face down, in its own colour, then `forms.two.swap_layers` whole
layers in the second colour from `forms.two.swap_start_mm` above the bed, then in its own colour again; a filament change colours the
whole layer. The tray and lid meshes are cut at the band's two planes (`case.swap_bands`) and the band piece takes the second
colour, so the groove floors and a line round the chamfer and every opening wall the band crosses show, as they print.

The installed views and the four lid-on older views (far-end, top, plate-end, underside) also draw wiring that is not part of the model: on each of the blades J941, J921 and J911 a fitted
receptacle in its boot (the `typical` envelope of params.yaml `boots`, placed on the blade as the lid-withdrawal check places a
fitted boot), a 3.2 mm wire leaving the boot's outer end along the blade axis for 45 mm, and a 2.2 mm round cable leaving the cable
notch outward 12 mm and turning down 30 mm. The boots, the wire and the cable are assumed envelopes for the picture, not checked
geometry. The exploded and lid-off views carry no wiring, since they show the inside.

The logo close-ups are perspective views aimed at the centre of the logo, 30 and 60 degrees off the face's normal, leaning toward
a viewer who stands in front of the machine (toward +v); below-lit and the lid close-ups are lit as the inside of an open machine
is lit, from the front and below, with nothing from above. The lid close-ups (logo-lid-30 and logo-lid-60) are kept unwired, since the hanging wires stand
between the camera and the lid.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import case  # noqa: E402,I001  (build123d before vtk)

import numpy as np  # noqa: E402
import pyvista as pv  # noqa: E402
import trimesh  # noqa: E402

SIZE = (1600, 1200)
WIRED_OLDER_VIEWS = ("far-end", "top", "plate-end", "underside")
VIEWS = ("far-end", "top", "plate-end", "underside", "exploded", "lid-off")
DIRECTION_VIEWS = ("above", "below", "below-lit", "side", "lid", "tray-top")
LOGO_VIEWS = ("logo-lid-30", "logo-lid-60", "logo-top-30", "logo-top-60")
ALL_DIRECTION_VIEWS = DIRECTION_VIEWS + LOGO_VIEWS
INSTALLED_VIEWS = ALL_DIRECTION_VIEWS          # the views that draw the case installed and wired
DIRECTION_FILE = {"tray-top": "top"}       # the file name of a direction view where it differs from the view's name
SKIN_NAME = "flow"
BOARD_COLOUR = "#5c7566"
BOOT_COLOUR = "#6f747a"
WIRE_COLOUR = "#eeeae2"
CABLE_COLOUR = "#8d9196"
WIRE_DIA_MM, WIRE_LEN_MM = 3.2, 45.0
CABLE_DIA_MM, CABLE_OUT_MM, CABLE_DOWN_MM = 2.2, 12.0, 30.0
SWAP_MARGIN_MM = 0.005
VIEW_GAIN = {"logo-top-30": 0.82, "logo-top-60": 0.82, "above": 0.8}      # views whose bone tray clipped at full light are lit lower
STONE_GAIN = {"lid": 1.2, "below": 1.4, "below-lit": 1.4, "logo-lid-30": 1.15, "logo-lid-60": 1.15}                                          # per-view light gain of the alternate colour, where it differs from VIEW_GAIN
LOGO_FRAME_MM = 45.0
LOGO_ANGLES = (30, 60)
BLADES = ("J941", "J921", "J911")
PART_COLOURS = {"T921_body": "#7b7f86", "T911_body": "#7b7f86", "T921_leads": "#b9bcc0", "T911_leads": "#b9bcc0",
                "RV911": "#8a6a56", "RV921": "#8a6a56", "U911": "#3b3d42", "U921": "#3b3d42",
                "R911": "#8b8e93", "R912": "#8b8e93", "R921": "#8b8e93", "R922": "#8b8e93",
                "J931": "#c9c3ad", "J941": "#b8905a", "J921": "#b8905a", "J911": "#b8905a"}
FEATURE_ANGLE = 30.0
CENTRE = np.array([23.75, 40.0, 8.0])
MATERIALS = {
    "plastic": {"specular": 0.15, "specular_power": 12.0, "ambient": 0.16, "diffuse": 0.92},
    "wiring": {"specular": 0.1, "specular_power": 10.0, "ambient": 0.34, "diffuse": 0.9},
    "film": {"specular": 0.2, "specular_power": 14.0, "ambient": 0.2, "diffuse": 0.9},
    "aluminium": {"specular": 0.55, "specular_power": 28.0, "ambient": 0.2, "diffuse": 0.85},
}
_MESHES: Dict[Tuple[int, str], pv.PolyData] = {}
_TEXTURES: Dict[int, pv.Texture] = {}


def phys(vector: Sequence[float]) -> Tuple[float, float, float]:
    """A direction or a point of the model frame in the physical frame."""
    v = case.PHYSICAL @ np.asarray(vector, dtype=float)
    return (float(v[0]), float(v[1]), float(v[2]))


def physical_poly(poly: pv.PolyData) -> pv.PolyData:
    """A triangulated surface of the model frame in the physical frame: points reflected, each triangle's winding reversed so its normal stays outward."""
    tri = poly.triangulate()
    faces = np.asarray(tri.faces).reshape(-1, 4).copy()
    faces[:, [2, 3]] = faces[:, [3, 2]]
    return pv.PolyData(np.asarray(tri.points) @ case.PHYSICAL.T, faces.ravel())


def alternate_name() -> str:
    """The name of the single-colour form's second colour, read from params.yaml."""
    return str(case.Params.load().entry("forms.single.alternate_name")["value"])


def form_names() -> Tuple[str, str, str]:
    """The three render forms in sheet order: single colour (bone), the alternate single colour, two colour."""
    return ("single", alternate_name(), "two")


def geometry_form(form: str) -> str:
    """The model form whose geometry a render form draws: the alternate colour is the single-colour form's own."""
    return "single" if form == alternate_name() else form


def tint(m: case.Model, form: str, part: str) -> str:
    """The colour of the tray or the lid ("tray", "lid") in a render form."""
    if form == alternate_name():
        return m.P("forms.single.alternate_colour")
    return m.P(f"forms.{form}.{part}_colour")


def base_mesh(m: case.Model, name: str) -> pv.PolyData:
    """A part tessellated finely enough that curved faces shade smoothly and reflected into the physical frame, once for the process (callers copy before they move it)."""
    shape = m.parts[name] if name in m.parts else m.bodies[name]["shape"]
    for (model_id, other), mesh in _MESHES.items():
        if model_id == id(m) and other != name:
            other_shape = m.parts[other] if other in m.parts else m.bodies.get(other, {}).get("shape")
            if other_shape is shape:          # the two lids are one solid
                _MESHES[(id(m), name)] = mesh
                break
    if (id(m), name) not in _MESHES:
        _MESHES[(id(m), name)] = pv.wrap(case.physical_mesh(case.to_mesh(shape, 0.01, 0.12)))
    return _MESHES[(id(m), name)]


def mesh_of(m: case.Model, name: str, offset: Tuple[float, float, float] = (0, 0, 0)) -> pv.PolyData:
    return base_mesh(m, name).translate(offset, inplace=False)


def split_by_band(poly: pv.PolyData, z0: float, z1: float) -> Tuple[pv.PolyData, pv.PolyData, pv.PolyData]:
    """A mesh cut at the planes z = z0 and z = z1 into the piece below z0, the piece between and the piece above z1 (pieces abut, no caps).

    Each plane is moved out by SWAP_MARGIN_MM so that a face lying exactly on a band's edge (a groove floor, which is the first layer
    of the band) falls inside the band whatever the tessellation does to its z."""
    n = (0.0, 0.0, 1.0)
    z0, z1 = z0 - SWAP_MARGIN_MM, z1 + SWAP_MARGIN_MM
    below = poly.clip(normal=n, origin=(0.0, 0.0, z0), invert=True)
    band = poly.clip(normal=n, origin=(0.0, 0.0, z0), invert=False).clip(normal=n, origin=(0.0, 0.0, z1), invert=True)
    above = poly.clip(normal=n, origin=(0.0, 0.0, z1), invert=False)
    return below, band, above


def brushed_texture(size: int = 1024, seed: int = 7) -> pv.Texture:
    """A brushed aluminium look: noise smeared along one axis, a little banding, light grey."""
    if (size, seed) in _TEXTURES:
        return _TEXTURES[(size, seed)]
    rng = np.random.default_rng(seed)
    noise = rng.normal(size=(size, size))
    k = 48
    kernel = np.ones(k) / k
    smeared = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="same"), 1, noise)
    smeared = (smeared - smeared.min()) / (smeared.max() - smeared.min())
    grey = np.clip(0.74 + 0.20 * (smeared - 0.5) + 0.03 * rng.normal(size=(size, 1)), 0.0, 1.0)
    rgb = np.stack([grey * 0.98, grey * 0.99, grey * 1.0], axis=-1)
    _TEXTURES[(size, seed)] = pv.Texture((rgb * 255).astype(np.uint8))
    return _TEXTURES[(size, seed)]


def plate_texture_coords(poly: pv.PolyData) -> pv.PolyData:
    """Texture coordinates laid on the plate's length, so the brushing runs along it on every face."""
    pts = poly.points
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    span = np.maximum(hi - lo, 1e-6)
    s = (pts[:, 0] - lo[0]) / span[0] * 2.0
    t = (pts[:, 2] - lo[2]) / span[2] * 0.6 + (pts[:, 1] - lo[1]) / span[1] * 0.4
    poly.active_texture_coordinates = np.stack([s, t], axis=1)
    return poly


def scene_parts(m: case.Model, form: str, view: str) -> List[Dict[str, Any]]:
    """Every mesh of a view with its colour, material and the offset the view puts it at.

    A part carrying `band` (z0, z1, colour) is printed in two colours: its mesh is cut at the two planes and the piece between takes the colour."""
    P = m.P
    items: List[Dict[str, Any]] = []
    ex = view == "exploded"
    lid_off = view == "lid-off"
    lift_lid = (0, 0, 46) if ex else (0, 0, 0)
    board_lift = (0, 0, 20) if ex else (0, 0, 0)
    film_move = (0, -22, 0) if ex else (0, 0, 0)
    plate_move = (0, -44, 0) if ex else (0, 0, 0)
    bands = case.swap_bands(m) if form == "two" else {}
    geo = geometry_form(form)
    tray = {"name": "tray", "colour": tint(m, form, "tray"), "offset": (0, 0, 0), "material": "plastic"}
    if "tray" in bands:
        tray["band"] = (*bands["tray"], P("forms.two.tray_floor_colour"))
    items.append(tray)
    if not lid_off:
        lid = {"name": f"lid_{geo}", "colour": tint(m, form, "lid"), "offset": lift_lid, "material": "plastic"}
        if "lid" in bands:
            lid["band"] = (*bands["lid"], P("forms.two.lid_floor_colour"))
        items.append(lid)
    items.append({"name": "film", "colour": P("forms.film_colour"), "offset": film_move, "material": "film"})
    items.append({"name": "plate", "colour": P("forms.plate_colour"), "offset": plate_move, "material": "aluminium"})
    items.append({"name": "board", "colour": BOARD_COLOUR, "offset": board_lift, "material": "plastic"})
    for name in m.bodies:
        if name != "board":
            items.append({"name": name, "colour": PART_COLOURS.get(name, "#888888"), "offset": board_lift, "material": "plastic"})
    for item in items:
        item["offset"] = phys(item["offset"])
    return items


def scene_meshes(m: case.Model) -> Dict[str, trimesh.Trimesh]:
    """The case parts the renderer draws (tray, the lid of each built form, film, plate), unmoved, as meshes in the physical frame: the same
    surfaces, in the same frame, as the exported STL files."""
    names = [n for n in ("tray", "lid_single", "lid_two", "film", "plate") if n in m.parts]
    out: Dict[str, trimesh.Trimesh] = {}
    for name in names:
        poly = base_mesh(m, name)
        out[name] = trimesh.Trimesh(vertices=np.asarray(poly.points), faces=np.asarray(poly.faces).reshape(-1, 4)[:, 1:], process=False)
    return out


def to_case_frame(m: case.Model, points: np.ndarray) -> np.ndarray:
    """Points drawn in the board's own untilted frame (u, v, z up from the component face), carried to where the board's lean puts them."""
    out = np.empty_like(points, dtype=float)
    for i, p in enumerate(points):
        out[i] = m.board_global((float(p[0]), float(p[1]), float(p[2])))
    return out


def blade_centre(m: case.Model, ref: str) -> Tuple[float, float]:
    pads = m.board.refs[ref]["pads"]
    return pads[0]["hole_u"], sum(p["hole_v"] for p in pads) / len(pads)


def wiring_items(m: case.Model) -> List[Dict[str, Any]]:
    """The wiring drawn on the installed views: assumed envelopes for the picture, not model parts and not checked geometry."""
    P = m.P
    items: List[Dict[str, Any]] = []
    env = case.boot_box(m, "typical")
    for ref in BLADES:
        uc, vc = blade_centre(m, ref)
        boot = pv.Box(bounds=(uc - env["across_thickness"] / 2, uc + env["across_thickness"] / 2, vc - env["across_width"] / 2, vc + env["across_width"] / 2,
                              0.0, env["length"]))
        boot.points = to_case_frame(m, np.asarray(boot.points))
        boot = physical_poly(boot)
        wire = pv.Cylinder(center=(uc, vc, env["length"] + WIRE_LEN_MM / 2), direction=(0, 0, 1), radius=WIRE_DIA_MM / 2, height=WIRE_LEN_MM, resolution=40, capping=True)
        wire.points = to_case_frame(m, np.asarray(wire.points))
        items.append({"mesh": boot, "colour": BOOT_COLOUR})
        items.append({"mesh": physical_poly(wire), "colour": WIRE_COLOUR})
    n0, n1 = P("lid.cable_notch_v_mm")
    right_out = 45.0 + P("case.interior_right_mm") + P("case.wall_mm")
    v = (n0 + n1) / 2
    z = P("case.z_wall_top_mm") - P("lid.cable_notch_height_mm") / 2
    r = CABLE_DIA_MM / 2
    run = pv.Cylinder(center=(right_out + CABLE_OUT_MM / 2, v, z), direction=(1, 0, 0), radius=r, height=CABLE_OUT_MM, resolution=40, capping=True)
    drop = pv.Cylinder(center=(right_out + CABLE_OUT_MM, v, z + CABLE_DOWN_MM / 2), direction=(0, 0, 1), radius=r, height=CABLE_DOWN_MM, resolution=40, capping=True)
    elbow = pv.Sphere(radius=r, center=(right_out + CABLE_OUT_MM, v, z), theta_resolution=40, phi_resolution=40)
    for piece in (run, drop, elbow):
        items.append({"mesh": physical_poly(piece), "colour": CABLE_COLOUR})
    return items


def installed_up(m: Optional[case.Model] = None) -> np.ndarray:
    """The page's up for the installed renders: against gravity."""
    return -case.gravity(m) if m is not None else np.array([0.0, 0.0, -1.0])


def logo_target(m: case.Model, view: str) -> np.ndarray:
    """The centre of the logo a close-up is aimed at, on the face it is engraved in."""
    if view.startswith("logo-lid"):
        c = m.info["logo_outline"].centroid
        return np.array([c.x, c.y, m.P("case.z_lid_top_mm")])
    c = m.info["tray_logo"]["outline"].centroid
    return np.array([c.x, c.y, m.z_floor_bottom])


def logo_direction(m: case.Model, view: str) -> np.ndarray:
    """The unit vector from the logo to the camera: cos(a) along the face's normal (gravity for the lid, up for the tray top) plus sin(a) toward +v."""
    angle = np.radians(float(view.rsplit("-", 1)[1]))
    normal = case.gravity(m) if view.startswith("logo-lid") else installed_up(m)
    return np.cos(angle) * normal + np.sin(angle) * np.array([0.0, 1.0, 0.0])


def camera_for(view: str, centre: np.ndarray, up_world: Optional[np.ndarray] = None, m: Optional[case.Model] = None) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float], Optional[float]]:
    """Camera position, focal point, up vector and a parallel scale (None for perspective).

    The installed views take up from `up_world` (against gravity): above looks at the tray's top face, one long side and the far
    end from above; below (and below-lit) at the lid face, the same side and the far end from below; side is level and square-on to
    the long side; lid is orthographic straight at the lid face with the wall toward the bottom of the page (the lid is seen from below, so
    the far end is nearer the viewer and higher in the view); the logo close-ups (which need the model `m`) are perspective, aimed at the
    logo's centre, the lid's with the wall toward the bottom of the page and the tray top's toward the top.

    The vectors are written in the model frame and returned in the physical frame.
    """
    pos, focal, up_vec, scale = _camera_model(view, centre, up_world, m)
    return (phys(pos), phys(focal), phys(up_vec), scale)


def _camera_model(view: str, centre: np.ndarray, up_world: Optional[np.ndarray], m: Optional[case.Model]) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float], Optional[float]]:
    """camera_for in the model frame."""
    up = tuple(up_world) if up_world is not None else (0.0, 0.0, -1.0)
    g = -np.asarray(up)
    if view in LOGO_VIEWS:
        assert m is not None
        focal = logo_target(m, view)
        distance = LOGO_FRAME_MM / 2 / np.tan(np.radians(15.0))      # 30 degree view angle: the frame is the image's shorter side
        wall_up = 1.0 if view.startswith("logo-lid") else -1.0       # the lid is seen from below: its far end is the top of the view
        return (tuple(focal + distance * logo_direction(m, view)), tuple(focal), (0, wall_up, 0), None)
    if view == "far-end":
        return ((centre[0] + 120, centre[1] + 190, centre[2] + 95), tuple(centre), (0, 0, 1), None)
    if view == "top":
        return ((centre[0], centre[1] + 2.0, centre[2] + 400), (centre[0], centre[1] + 2.0, centre[2]), (0, 1, 0), 56.0)
    if view == "plate-end":
        return ((centre[0] + 140, centre[1] - 150, centre[2] + 80), tuple(centre), (0, 0, 1), None)
    if view == "underside":
        return ((centre[0] - 110, centre[1] + 150, centre[2] - 120), tuple(centre), (0, 0, 1), None)
    if view == "exploded":
        return ((centre[0] + 190, centre[1] + 40, centre[2] + 150), (centre[0], centre[1] - 8, centre[2] + 22), (0, 0, 1), None)
    if view == "lid-off":
        return ((centre[0] + 70, centre[1] + 150, centre[2] + 190), tuple(centre), (0, 0, 1), None)
    if view == "above":
        focal = centre + np.array([0.0, 2.0, 0.0]) + 14.0 * np.asarray(up)
        return (tuple(focal + np.array([150.0, 175.0, 0.0]) + 125.0 * np.asarray(up)), tuple(focal), up, None)
    if view in ("below", "below-lit"):
        focal = centre + np.array([0.0, 2.0, 0.0]) + 14.0 * g
        return (tuple(focal + np.array([150.0, 175.0, 0.0]) + 125.0 * g), tuple(focal), up, None)
    if view == "side":
        focal = centre + np.array([0.0, 14.0, 0.0])
        return (tuple(focal + np.array([520.0, 0.0, 0.0])), tuple(focal), up, None)
    if view == "lid":
        focal = centre + np.array([0.0, 2.0, 0.0])
        return (tuple(focal + 400.0 * g), tuple(focal), (0, 1, 0), 56.0)
    if view == "tray-top":
        focal = centre + np.array([0.0, 2.0, 0.0])
        return (tuple(focal + 400.0 * np.asarray(up)), tuple(focal), (0, -1, 0), 56.0)
    raise SystemExit(f"unknown view {view}")


def add_lights(plotter: pv.Plotter, focal: Sequence[float], position: Sequence[float], up: Sequence[float], raking: bool = False, gain: float = 1.0) -> None:
    """Three soft lights placed from the camera (a key high and to one side, a weaker cool fill from the other, a rim from behind) and a faint headlight.

    `raking` is for the views straight at a face: the key stands near the camera, which keeps a colour true, and a weak fill
    comes in low across the face, so the 0.6 mm grooves of a single-colour face cast a shadow instead of vanishing."""
    plotter.remove_all_lights()
    f = np.asarray(focal, dtype=float)
    d = np.asarray(position, dtype=float) - f
    d /= np.linalg.norm(d)
    u = np.asarray(up, dtype=float)
    u = u - d * float(u @ d)
    u /= np.linalg.norm(u)
    r = np.cross(u, d)
    rig = [(0.9 * d + 0.8 * u + 0.6 * r, 0.70, "#fff6ea"), (0.8 * d + 0.2 * u - 1.0 * r, 0.55, "#e8f0ff"),
           (-0.5 * d + 0.9 * u - 0.3 * r, 0.45, "#ffffff"), (0.2 * d - 1.0 * u, 0.15, "#ffffff")]
    headlight = 0.22
    if raking:
        rig = [(0.7 * d + 0.5 * u + 0.4 * r, 0.62, "#fff6ea"),          # the key close to the camera, so a face keeps its true colour
               (0.8 * d + 0.2 * u - 1.0 * r, 0.3, "#e8f0ff"), (-0.5 * d + 0.9 * u - 0.3 * r, 0.25, "#ffffff"),
               (0.12 * d + 0.95 * u + 0.45 * r, 0.38, "#ffffff")]       # a weak fill raking across the face, so the grooves cast a shadow
        headlight = 0.16
    for offset, intensity, colour in rig:
        plotter.add_light(pv.Light(position=tuple(f + 280.0 * offset), focal_point=tuple(f), color=colour, intensity=intensity * gain, light_type="scene light"))
    plotter.add_light(pv.Light(color="#ffffff", intensity=headlight * gain, light_type="headlight"))


def lit_from_below_rig(m: case.Model) -> List[Tuple[np.ndarray, float, str]]:
    """The lights of the inside of an open machine: a key from the front (+v, away from the wall) and below (gravity), a weak fill from below and the plate-end side, nothing from above."""
    g = case.gravity(m)
    front = np.array([0.0, 1.0, 0.0])
    side = np.array([1.0, 0.0, 0.0])
    return [(0.75 * g + 0.65 * front, 0.85, "#fff6ea"), (0.9 * g - 0.3 * front - 0.5 * side, 0.3, "#e8f0ff")]


def add_lights_from_below(plotter: pv.Plotter, m: case.Model, focal: Sequence[float], gain: float = 1.0) -> None:
    plotter.remove_all_lights()
    f = np.asarray(focal, dtype=float)
    for direction, intensity, colour in lit_from_below_rig(m):
        direction = np.asarray(phys(direction))
        direction = direction / np.linalg.norm(direction)
        plotter.add_light(pv.Light(position=tuple(f + 280.0 * direction), focal_point=tuple(f), color=colour, intensity=intensity * gain, light_type="scene light"))
    plotter.add_light(pv.Light(color="#ffffff", intensity=0.1 * gain, light_type="headlight"))


def add_item(plotter: pv.Plotter, poly: pv.PolyData, colour: str, material: str, texture: Optional[pv.Texture] = None, **extra: Any) -> None:
    if poly.n_points == 0 or poly.n_cells == 0:
        return
    kwargs: Dict[str, Any] = dict(smooth_shading=True, split_sharp_edges=True, feature_angle=FEATURE_ANGLE, show_edges=False, **MATERIALS[material])
    if texture is not None:
        kwargs["texture"] = texture
    else:
        kwargs["color"] = colour
    kwargs.update(extra)
    plotter.add_mesh(poly, **kwargs)


def render_scene(m: case.Model, form: str, view: str, path: str, size: Tuple[int, int] = SIZE) -> str:
    """One image of one view of one form, written to path."""
    installed = view in INSTALLED_VIEWS
    gain = STONE_GAIN if form == alternate_name() else VIEW_GAIN
    plotter = pv.Plotter(off_screen=True, window_size=list(size))
    plotter.set_background("#e6e9ed", top="#fafbfc")
    plate_texture = brushed_texture()
    for item in scene_parts(m, form, view):
        poly = base_mesh(m, item["name"])
        offset = item["offset"]
        if item["material"] == "aluminium":
            add_item(plotter, plate_texture_coords(poly.translate(offset, inplace=False)), item["colour"], "aluminium", plate_texture)
        elif "band" in item:
            z0, z1, band_colour = item["band"]
            below, band, above = split_by_band(poly, z0, z1)
            for piece, colour in ((below, item["colour"]), (band, band_colour), (above, item["colour"])):
                add_item(plotter, piece.translate(offset, inplace=False), colour, item["material"])
        else:
            extra = {"opacity": 0.95} if item["material"] == "film" else {}
            add_item(plotter, poly.translate(offset, inplace=False), item["colour"], item["material"], **extra)
    wired = (installed and not view.startswith("logo-lid")) or view in WIRED_OLDER_VIEWS   # the hanging wires would stand between the camera and the lid logo
    wiring = wiring_items(m) if wired else []
    pos, focal, up, scale = camera_for(view, CENTRE, installed_up(m) if installed else None, m)
    if view == "below-lit" or view.startswith("logo-lid"):
        add_lights_from_below(plotter, m, focal, gain.get(view, 1.0))
    elif view in LOGO_VIEWS:
        add_lights(plotter, focal, pos, phys(installed_up(m)), raking=True, gain=gain.get(view, VIEW_GAIN[view] if form != alternate_name() else 1.0))
    else:
        add_lights(plotter, focal, pos, up, raking=view in ("lid", "tray-top"), gain=gain.get(view, 1.0))
    plotter.camera_position = [pos, focal, up]
    if scale:
        plotter.camera.parallel_projection = True
        plotter.camera.parallel_scale = scale
    elif view in LOGO_VIEWS:
        plotter.camera.view_angle = 30.0
        plotter.reset_camera_clipping_range()
    else:
        plotter.camera.view_angle = 30.0 if view != "side" else 10.0
        if installed:
            if view == "side" and wiring:
                spans = np.array([w["mesh"].bounds for w in wiring]).reshape(-1, 3, 2)
                lo = np.minimum(np.array(plotter.bounds).reshape(3, 2)[:, 0], spans[:, :, 0].min(axis=0))
                hi = np.maximum(np.array(plotter.bounds).reshape(3, 2)[:, 1], spans[:, :, 1].max(axis=0))
                plotter.reset_camera(bounds=tuple(np.stack([lo, hi], axis=1).ravel()))
            else:
                plotter.reset_camera()
            plotter.camera.zoom({"above": 1.3, "below": 1.3, "below-lit": 1.3, "side": 1.15}.get(view, 1.2))
        else:
            plotter.camera.zoom(1.55 if view != "exploded" else 1.2)
    for w in wiring:
        add_item(plotter, w["mesh"], w["colour"], "wiring")
    plotter.enable_anti_aliasing("ssaa")
    try:
        plotter.enable_ssao(radius=4.0, bias=0.2, kernel_size=128, blur=True)
    except Exception as error:  # an offscreen stack without the passes still renders, just without the occlusion
        print(f"ambient occlusion unavailable: {error}", file=sys.stderr)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    plotter.screenshot(path)
    plotter.close()
    return path


def render_view(m: case.Model, form: str, view: str, out_dir: str) -> str:
    return render_scene(m, form, view, os.path.join(out_dir, f"{form}-{view}.png"))


SHEET_VIEWS = ("above", "below", "below-lit", "side", "lid", "tray-top")
SHEET_LABELS = ("single colour, bone", "single colour, {alternate}", "two colour")


def direction_path(out_dir: str, name: str, form: str, view: str) -> str:
    return os.path.join(out_dir, f"{name}-{form}-{DIRECTION_FILE.get(view, view)}.png")


def sheet_of(out_dir: str, name: str, views: Sequence[str], title: str, file: str, width: int) -> str:
    """One row a colour form (single in bone, single in the alternate colour, two), one column a view, the images already drawn."""
    sheet_forms = tuple(zip(form_names(), (label.format(alternate=alternate_name()) for label in SHEET_LABELS)))
    from PIL import Image, ImageDraw, ImageFont
    label_w, pad = 220, 14
    cell_w = (width - label_w - pad * (len(views) + 1)) // len(views)
    cell_h = cell_w * SIZE[1] // SIZE[0]
    head_h = 96
    height = head_h + len(sheet_forms) * (cell_h + pad) + pad
    sheet = Image.new("RGB", (width, height), "#f4f5f7")
    draw = ImageDraw.Draw(sheet)
    head_font = ImageFont.load_default(size=26)
    sub_font = ImageFont.load_default(size=24)
    draw.text((width // 2, 22), f"{name}, {title}", fill="#20242a", font=head_font, anchor="mm")
    for c, view in enumerate(views):
        x = label_w + pad + c * (cell_w + pad)
        draw.text((x + cell_w // 2, head_h - 26), DIRECTION_FILE.get(view, view), fill="#444a52", font=sub_font, anchor="mm")
    for r, (form, label) in enumerate(sheet_forms):
        y = head_h + pad + r * (cell_h + pad)
        draw.text((label_w // 2, y + cell_h // 2), label, fill="#20242a", font=sub_font, anchor="mm")
        for c, view in enumerate(views):
            image = Image.open(direction_path(out_dir, name, form, view)).convert("RGB").resize((cell_w, cell_h), Image.LANCZOS)
            sheet.paste(image, (label_w + pad + c * (cell_w + pad), y))
    path = os.path.join(out_dir, file)
    sheet.save(path)
    return path


def contact_sheet(out_dir: str, name: str = SKIN_NAME, width: int = 3600) -> str:
    """One row a colour form (single bone, single alternate, two), one column a view (above, below, below-lit, side, lid, top)."""
    return sheet_of(out_dir, name, SHEET_VIEWS, "installed: tray up, lid down", "contact-sheet.png", width)


def logo_sheet(out_dir: str, name: str = SKIN_NAME, width: int = 3200) -> str:
    """One row a colour form, one column a logo close-up (lid-30, lid-60, top-30, top-60)."""
    return sheet_of(out_dir, name, LOGO_VIEWS, "the logos, 30 and 60 degrees off the face's normal", "logo-sheet.png", width)


def render_directions(out_dir: str, overrides: Dict[str, Any], skin: Optional[str] = None, views: Sequence[str] = ALL_DIRECTION_VIEWS,
                      forms: Optional[Sequence[str]] = None) -> List[str]:
    """The named forms and installed views, and both sheets when every view of all three forms was drawn."""
    forms = form_names() if forms is None else tuple(forms)
    written: List[str] = []
    model = case.build(overrides, build_forms(forms), skin)
    name = model.P.skin_name
    for form in forms:
        for view in views:
            path = render_scene(model, form, view, direction_path(out_dir, name, form, view))
            print(os.path.relpath(path, HERE))
            written.append(path)
    if tuple(views) == ALL_DIRECTION_VIEWS and tuple(forms) == form_names():
        for sheet in (contact_sheet(out_dir, name), logo_sheet(out_dir, name)):
            print(os.path.relpath(sheet, HERE))
            written.append(sheet)
    return written


def build_forms(forms: Sequence[str]) -> Tuple[str, ...]:
    """The model forms to build for the render forms named (the alternate colour shares the single-colour form's meshes)."""
    return tuple(dict.fromkeys(geometry_form(f) for f in forms))


def pick_forms(choice: str) -> Tuple[str, ...]:
    return form_names() if choice in ("all", "both") else (choice,)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render the printed case, one set of views per colour form.")
    parser.add_argument("--out", default=None, help="folder the images are written to")
    forms_all = form_names()
    parser.add_argument("--form", choices=forms_all + ("all", "both"), default="all", help="one render form, or all three (both is the same as all)")
    parser.add_argument("--view", choices=VIEWS + ("all",), default="all")
    parser.add_argument("--skin", help="the skin to render (flow); the params.yaml default when omitted")
    parser.add_argument("--directions", action="store_true", help="the installed set: the three forms, the above, below, below-lit, side, lid and top views and the four logo close-ups of the installed case, and a contact sheet and a logo sheet")
    parser.add_argument("--direction-view", action="append", choices=ALL_DIRECTION_VIEWS, help="with --directions: draw only the named view (repeatable); no sheet is made then")
    parser.add_argument("--direction-form", choices=forms_all + ("all", "both"), default="all", help="with --directions: draw only the named colour form; no sheet is made then")
    parser.add_argument("--sheet-only", action="store_true", help="with --directions: rebuild the contact sheet and the logo sheet from the images already drawn")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a params.yaml value")
    args = parser.parse_args(argv)
    overrides = case.parse_overrides(args.set)
    if args.directions:
        out_dir = args.out or os.path.join(HERE, "renders", "directions")
        if args.sheet_only:
            for sheet in (contact_sheet(out_dir, args.skin or SKIN_NAME), logo_sheet(out_dir, args.skin or SKIN_NAME)):
                print(os.path.relpath(sheet, HERE))
            return 0
        render_directions(out_dir, overrides, args.skin, tuple(args.direction_view) if args.direction_view else ALL_DIRECTION_VIEWS, pick_forms(args.direction_form))
        return 0
    forms = pick_forms(args.form)
    views = VIEWS if args.view == "all" else (args.view,)
    model = case.build(overrides, build_forms(forms), args.skin)
    out = args.out or os.path.join(HERE, "renders")
    for form in forms:
        for view in views:
            print(os.path.relpath(render_view(model, form, view, out), HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
