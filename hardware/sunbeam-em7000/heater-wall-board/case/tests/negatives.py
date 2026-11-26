"""The negative controls of the case tests, each built and run in a small process pool ahead of the tests that read them.

A negative control rebuilds the whole model with one dimension broken, or with a part altered after the build, and runs
the checks on it. A build takes about twenty seconds, and the controls share nothing, so the session starts them all at
once on up to four worker processes, the nominal check among them, after the main process has built the nominal model the tests read. A test then asks for its
control by name and reads the result, which holds the check results themselves and never a model: a worker keeps its own
build, and a control that alters a model alters the one it built for itself.
"""

import concurrent.futures
import json
import multiprocessing
import os
import subprocess
import sys

CASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CASE_DIR)
import case  # noqa: E402,I001  (build123d before vtk)
import check  # noqa: E402
import skins  # noqa: E402

WORKERS = 4


def broken(overrides, fn, forms=("single",)):
    """Rebuild with overrides and run one check function on the result."""
    m = case.build(overrides, forms)
    check._SCENES.clear()
    return getattr(check, fn)(m)


def refused(overrides, forms=("single",)):
    """The message of the refusal a build with these overrides ends in, or None when it builds."""
    try:
        case.build(overrides, forms)
    except case.OutlineRefused as exc:
        return str(exc)
    return None


def short_plate():
    from build123d import Pos  # noqa: F401
    m = case.build(forms=("single",))
    m.parts["plate"] = case.box(-6.25 + 4.0, 53.75 - 4.0, m.v_plate - 5.0, m.v_plate, -7.0, 23.0)          # a 70 mm plate under the same case
    m._meshes.pop("plate", None)
    check._SCENES.clear()
    return {"results": check.check_c2_c3(m), "refused": refused({"plate.length_mm": 70.0})}


def rib_across_the_slot_mouths():
    m = case.build(forms=("single",))
    m.parts["tray"] = m.parts["tray"] + case.box(43.0, 49.0, 28.6, 29.8, -4.5, -1.7)
    m._meshes.pop("tray", None)
    check._SCENES.clear()
    return {"results": check.check_c8(m), "refused": refused({"case.interior_right_mm": 1.0})}


def tray_without_its_engraving():
    m = case.build(forms=("single", "two"))
    m.parts["tray"] = m.info["tray_envelope"]
    m._meshes.pop("tray", None)
    check._SCENES.clear()
    return check.check_c13(m)


def swap_before_the_logo_floor():
    m = case.build({"forms.two.swap_start_mm": 0.2}, ("single", "two"))
    check._SCENES.clear()
    return check.check_c13(m)


def seat_that_ignores_the_lean():
    m = case.build({"seating.lean_deg": 1.0}, ("single",))
    flat = case.build({"seating.lean_deg": 0.0}, ("single",))
    m.parts["tray"] = flat.parts["tray"]          # a tray printed for no lean under a board that leans
    m._meshes.pop("tray", None)
    check._SCENES.clear()
    return check.check_c6_c9(m)


def small_boots():
    m = case.build({"boots.typical": [8.0, 4.0, 22.0]}, ("single",))
    check._SCENES.clear()
    return check.check_c15(m) + check.check_blade_finger(m)


def one_receptacle_dropped():
    """The nominal model with the receptacle on J921 left off: the other two stay fitted."""
    m = case.build({}, ("single",))
    check._SCENES.clear()
    return check.check_blade_finger(m, "single", fitted=("J941", "J911"))


def wide_outlet_slits():
    m = case.build({"outlets.max_width_mm": 5.0, "skins.flow.outlets.width_mm": 4.5, "skins.flow.outlets.pitch_mm": 6.0}, ("single",))
    check._SCENES.clear()
    return {"outlets": bool(m.info["outlets"]), "results": check.check_c15(m)}


def bend_room_variants():
    """The bend room check on a header exit raised 1.0 mm, on a lid whose underside pad is 0.8 mm thicker, and on an exit above the lid's top."""
    out = {}
    for label, overrides in (("raised_exit", {"parts.header_housing_top_z_mm": 17.5}), ("thicker_underside", {"lid.top_louvre_mm": 3.2}),
                             ("exit_above_the_lid", {"parts.header_housing_top_z_mm": 23.0})):
        m = case.build(overrides, ("single",))
        check._SCENES.clear()
        out[label] = check.check_c20(m)[0]
    return out


class Narrow(skins.FlowSkin):
    """A skin whose tray neck is cut into the board's cavity."""

    def tray(self, c):
        good = self.neck(c)
        return skins.TraySpec(neck=[(u - 3.0 if u > 40 else u, v) if v > 20 else (u, v) for u, v in good])


def narrow_skin():
    return refused_skin(Narrow(case.Params.load()))


def refused_skin(skin):
    try:
        case.build(forms=("single",), skin=skin)
    except case.OutlineRefused as exc:
        return str(exc)
    return None


def cli(arguments):
    """The command line run in a fresh interpreter: its exit status, its standard output and, if it wrote one, its JSON file."""
    out = os.path.join(CASE_DIR, "out", "logs", f"negatives-cli-{os.getpid()}.json")
    command = [sys.executable, os.path.join(CASE_DIR, "check.py")] + list(arguments) + (["--json-out", out] if "--format" in arguments else [])
    done = subprocess.run(command, capture_output=True, text=True)
    written = None
    if os.path.exists(out):
        with open(out, encoding="utf-8") as handle:
            written = json.load(handle)
        os.remove(out)
    return {"returncode": done.returncode, "stdout": done.stdout, "file": written}


CORNERS = {"corner_low": ("min", "min", "min"), "corner_high": ("max", "max", "max")}

def nominal():
    """Every check on the nominal model: the results the tests that read `results` share."""
    return check.run_all(case.build())


# the control, what it builds and runs, and about how many seconds it takes
JOBS = {
    "nominal": (nominal, 120),
    "c4_short_gate": (lambda: broken({"skins.flow.cable_gate_lead_mm": 2.0}, "check_c4"), 65),
    "c4_tight": (lambda: broken({"plate.wall_opening_clearance_mm": 0.0, "lid.sweep_tilt_deg": 8.0}, "check_c4"), 65),
    "corner_low": (lambda: check._seating_combo(({}, None, CORNERS["corner_low"])), 80),
    "corner_high": (lambda: check._seating_combo(({}, None, CORNERS["corner_high"])), 80),
    "c13_no_engraving": (tray_without_its_engraving, 45),
    "c13_swap_too_early": (swap_before_the_logo_floor, 45),
    "c1_high": (lambda: broken({"film.height_under_body_mm": 3.0}, "check_c1"), 22),
    "c1_low": (lambda: broken({"film.height_under_body_mm": 0.5}, "check_c1"), 22),
    "c1_thick": (lambda: broken({"film.thickness_mm": 0.6}, "check_c1"), 22),
    "cli_json": (lambda: cli(["--format", "json", "--only", "c1.,c15."]), 30),
    "cli_fails": (lambda: cli(["--only", "c1.", "--set", "film.height_under_body_mm=3.0"]), 25),
    "c5_no_barb": (lambda: broken({"lid.toe_barb": False}, "check_c5_c11"), 24),
    "c11_driver": (lambda: broken({"screws.driver_max_tilt_deg": 1.0}, "check_c5_c11"), 24),
    "c6_no_finger": (lambda: broken({"seat.finger": False}, "check_c6_c9"), 22),
    "c9_soft": (lambda: broken({"material.modulus_MPa": 20.0}, "check_c6_c9"), 22),
    "c14_bed": (lambda: broken({"printer.bed_x_mm": 50.0}, "check_c14"), 22),
    "c18_tight": (lambda: broken({"lid.aperture_clearance_mm": 0.2}, "check_c18"), 22),
    "c18_big": (lambda: broken({"boots.largest_common": [17.0, 7.8, 25.0]}, "check_c18"), 22),
    "c19_reversed": (lambda: broken({"louvre.angle_deg": 0.0, "installed.gravity": [0.0, 0.0, -1.0]}, "check_c15"), 22),
    "c19_installed": (lambda: broken({"louvre.angle_deg": 0.0}, "check_c15"), 22),
    "c3_short_plate": (short_plate, 22),
    "c8_rib": (rib_across_the_slot_mouths, 22),
    "c15_small_boots": (small_boots, 22),
    "c15_one_receptacle_off": (one_receptacle_dropped, 22),
    "c15_wide_outlet": (wide_outlet_slits, 22),
    "c16_no_lean": (seat_that_ignores_the_lean, 40),
    "c20_bend_room": (bend_room_variants, 70),
    "c20_worst_lean": (lambda: broken({"seating.lean_deg": 1.0}, "check_c20")[0], 22),
    "c20_best_lean": (lambda: broken({"seating.lean_deg": -1.0}, "check_c20")[0], 22),
    "skin_narrow": (narrow_skin, 22),
}


def run(name):
    return JOBS[name][0]()


def _initialise():
    os.nice(5)


class Controls:
    """The pool, and the futures of the controls the selected tests will read."""

    def __init__(self, wanted):
        self.futures = {}
        names = sorted({n for n in wanted if n in JOBS}, key=lambda n: -JOBS[n][1])
        if not names:
            self.pool = None
            return
        self.pool = concurrent.futures.ProcessPoolExecutor(max_workers=min(WORKERS, len(names)), mp_context=multiprocessing.get_context("spawn"),
                                                           initializer=_initialise)
        for name in names:
            self.futures[name] = self.pool.submit(run, name)

    def get(self, name):
        return self.futures[name].result()

    def close(self):
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)
