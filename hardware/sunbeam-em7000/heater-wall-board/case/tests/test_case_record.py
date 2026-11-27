"""Content tests of the case record (`../case-record.md`): each figure the record quotes is parsed and compared with the file or
the model result it comes from, so the record cannot drift from its sources and a clause cannot be dropped unnoticed.

Run with the interpreter `task hw:cad` creates, from the case folder:  python -m pytest tests/test_case_record.py
The model, the nominal check and the basis come from the session fixtures of `conftest.py`, shared with `test_case.py`.
"""

import json
import math
import os
import re
import struct

import pytest
import sys

import yaml

CASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD_DIR = os.path.dirname(CASE_DIR)
RECORD = os.path.join(BOARD_DIR, "case-record.md")
T = "SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON"
CHECK_TABLE = "**Check against the criterion.**"


def named(results, name):
    return next(r for r in results if r["name"] == name)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def record():
    return read(RECORD)


@pytest.fixture(scope="module")
def params():
    return yaml.safe_load(read(os.path.join(CASE_DIR, "params.yaml")))


@pytest.fixture(scope="module")
def hrng():
    """The plate-height range run's result, `out/check-height-range.json`."""
    return json.loads(read(os.path.join(CASE_DIR, "out", "check-height-range.json")))


@pytest.fixture(scope="module")
def rng():
    """The range run's result, `out/check-range.json`; entries are looked up by name with `named(rng["checks"], name)`."""
    return json.loads(read(os.path.join(CASE_DIR, "out", "check-range.json")))


def sections(text):
    """The record's `## ` sections, in order, as (heading, body)."""
    parts = re.split(r"^## ", text, flags=re.M)
    return [(p.split("\n", 1)[0], p) for p in parts[1:]]


def sec(text, tag):
    """The body of the `## ` section whose heading ends with the criterion tag, for example (C10)."""
    found = [body for head, body in sections(text) if head.rstrip().endswith("(%s)" % tag)]
    assert len(found) == 1, "the record needs exactly one section headed (%s)" % tag
    return found[0]


def tables(body):
    """Every markdown table of `body`, as (header cells, rows of cells)."""
    out, cur = [], None
    for ln in body.split("\n"):
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            cur = [cells] if cur is None else cur + [cells]
        elif cur is not None:
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return [(t[0], t[2:]) for t in out if len(t) >= 2]


def table_rows(body, first_header):
    """The cells of each row of the first markdown table whose header row starts with `first_header`."""
    for header, rows in tables(body):
        if header[0] == first_header:
            return rows
    raise AssertionError("no table headed %r" % first_header)


def num(text, pattern, group=1):
    m = re.search(pattern, text)
    assert m, "the record does not state %r" % pattern
    return float(m.group(group))


def nums(text, pattern):
    return [float(x) for x in re.findall(pattern, text)]


def hms(text):
    h, m, s = (int(x) for x in re.search(r"(\d+)h (\d+)m (\d+)s", text).groups())
    return h * 3600 + m * 60 + s


def slice_summary(part):
    return json.loads(read(os.path.join(CASE_DIR, "slice", part + ".json")))


# ---------------------------------------------------------------- the record as a whole

def test_the_record_has_one_section_per_criterion_each_with_its_check_table(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C10: The case record states how the spreader plate is bonded to protective earth: the mechanism assumed, the plate screwed to the machine's steel wall, earthed through the mains-inlet earth, which the owner confirms, and the four-wire measurement the bring-up task holds it to. It also records the owner's decision, with his words and the date, whether the plate carries its own dedicated earth strap or relies on the wall alone, and the case drawing shows the strap if there is one. Taking the measurement is out of scope.
    heads = [h for h, _ in sections(record)]
    assert heads[0] == "The case" and heads[-1] == "Owner list"
    tagged = [re.search(r"\(C(\d+)\)$", h.rstrip()) for h in heads[1:-1]]
    assert all(tagged) and [int(m.group(1)) for m in tagged] == list(range(1, 22)), "one section per criterion, C1 to C21, in order"
    for n in range(1, 22):
        body = sec(record, "C%d" % n)
        assert CHECK_TABLE in body, "(C%d) ends with its check against the criterion" % n
        header, rows = tables(body.split(CHECK_TABLE)[1])[0]
        assert header == ["Clause", "Shown by", "Result"] and len(rows) >= 2, n
        assert all(len(r) == 3 and all(r) for r in rows), "every clause row of (C%d) is complete" % n


def test_every_check_the_record_names_is_a_real_result_and_passed(record, results, rng, hrng):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C1: The case's fixed base, the tray the board is screwed to and never the removable lid, carries an insulating barrier between the bare spreader plate face and the board's mains copper wherever the separation basis's basic creepage to the earthed plate would not otherwise hold. The barrier is a creepage barrier only and is not relied on as solid insulation. It is designed for the board as the assembler delivers it, with the triacs seated on their lead shoulders, from the board's layout file and the triac's package model, and it tolerates the delivered triacs' seating scatter. The case drawing or model states the barrier's minimum solid thickness, its height above the board face at each point along the plate edge, that it spans the board's width, the creepage path it gives from each triac pad edge to the first bare plate against the 2.6 mm the basis signs, and the gap it leaves between the board edge and the plate. The barrier is a printed wall of the tray, or a thin bought insulating film that the tray holds, and the drawing states which; a printed wall is at least 0.8 mm thick wherever it stands in the board-to-plate gap or the gap is shown wide enough for it. If neither can be made, the case instead holds the plate's lower edge at least 6.0 mm above the board's component face, which leaves the triac's leads 3.4 mm from the plate; that fallback reverses the owner's recorded plate position and takes the owner's recorded decision before it is used, and the drawing states which form the case takes. Making the plate and printing the case are out of scope.
    known = {r["name"]: r for r in results}
    known.update({r["name"]: r for r in rng["checks"]})
    known.update({r["name"]: r for r in hrng["checks"]})
    cited = sorted(set(re.findall(r"`(c\d+\.[a-z0-9_]+)`", record)))
    assert len(cited) >= 30, "the record cites its checks by name"
    for name in cited:
        assert name in known, "the record names `%s`, which no result carries" % name
        if known[name]["kind"] == "finding":
            assert known[name]["passed"] is None, name
        else:
            assert known[name]["passed"] is True, "`%s` is cited and does not pass" % name
    for r in results:
        assert r["passed"] is True or r["kind"] == "finding", r["name"]


def test_the_intro_counts_are_the_nominal_and_range_runs(record, results, rng):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C16: The board-to-plate fit takes the scatter of the delivered triacs' seating, stated as a range of tab-hole height and lean, without loading the soldered leads: the tray's board seat and the barrier are shown by the model to meet at the range's extremes. The plate's tab holes are either a short slot or an oversize hole, or tapped holes drilled at the measured height of the delivered triacs with the tray printed to the measured values, and the case record states which the case takes; for tapped holes it states that the owner's acceptance of that departure from his ruling of 2026-11-24 (slot or oversize hole) is outstanding. The range with its source is recorded as unconfirmed for the owner to check at assembly.
    intro = record.split("## The case")[0]
    checks = [r for r in results if r["kind"] == "check"]
    findings = [r for r in results if r["kind"] == "finding"]
    assert all(r["passed"] for r in checks)
    assert "%d of %d checks pass, with one finding reported and not counted" % (len(checks), len(checks)) in intro
    assert len(findings) == 1
    rchecks = [r for r in rng["checks"] if r["kind"] == "check"]
    rfind = [r for r in rng["checks"] if r["kind"] == "finding"]
    assert all(r["passed"] for r in rchecks) and rng["passed"] is True and len(rng["checks"]) == len(results) + 2
    assert "%d of %d pass, with two findings reported and not counted" % (len(rchecks), len(rchecks)) in intro
    assert len(rfind) == 2
    assert "all 64 extremes of the seating range" in intro and "twenty-one criteria" in intro
    assert "Nothing has been printed yet" in intro


# ---------------------------------------------------------------- C1 to C3

def test_c1_the_record_states_the_raised_plate_the_gap_and_the_straight_lines_with_the_models_figures(record, results, rng, basis):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C1: The case's fixed base, the tray the board is screwed to and never the removable lid, carries an insulating barrier between the bare spreader plate face and the board's mains copper wherever the separation basis's basic creepage to the earthed plate would not otherwise hold, or the case holds the plate's lower edge 6.0 mm above the board; the 6.0 mm fallback is taken here
    body = sec(record, "C1")
    assert "**the case holds the spreader plate's lower edge 6.0 mm above the board's component face**" in body and "**No barrier is used**" in body
    lift = named(results, "c1.plate_lower_edge_raised")["figures"]
    assert "z %.3f" % lift["plate_lower_edge_z_mm"] in body and "{:.3f} mm".format(lift["derived_least_mm"]) in body
    assert "4.55 + sqrt(2.6^2 - 2.40^2) = %.3f mm" % lift["derived_least_mm"] in body
    gap = named(results, "c1.gap_over_tolerances")["figures"]
    assert "%.3f to %.3f mm over the" % tuple(gap["package_range_mm"]) in body or "%.3f to %.3f mm (ST DS2114" % tuple(gap["package_range_mm"]) in body
    assert "%.3f - 0.2 - 0.305 = %.3f mm and %.3f + 0.2 + 0.305 = %.3f mm" % (gap["package_range_mm"][0], gap["gap_min_mm"], gap["package_range_mm"][1], gap["gap_max_mm"]) in body
    assert gap["arithmetic"].startswith("0.785 - 0.200 - 0.305 = 0.280")
    pad = named(results, "c1.creepage_pad_to_plate")["figures"]
    lead = named(results, "c1.creepage_bare_lead_to_plate")["figures"]
    wall = named(results, "c1.straight_to_wall_plane")["figures"]
    assert "Nominal: %.3f mm from the nearest pad edge" % pad["creepage_mm"] in body and "%.3f mm from a bare lead" % lead["creepage_mm"] in body
    assert "%.3f mm from the wall plane" % wall["copper_mm"] in body
    worst = named(rng["checks"], "c16.seating_range")["figures"]["combinations"]
    assert "the least is %.3f mm from any Mains copper and %.3f mm from a bare lead" % (min(c["least_creepage_mm"] for c in worst), min(c["least_lead_mm"] for c in worst)) in body
    assert num(body, r"against the basis's (\d\.\d) mm creepage and (\d\.\d) mm clearance") == pytest.approx(basis["creepage_mains_mm"])
    assert num(body, r"against the basis's \d\.\d mm creepage and (\d\.\d) mm clearance") == pytest.approx(basis["clearance_mains_mm"])
    wallf = named(results, "c1.end_wall_stands_off")["figures"]
    assert "stands %.3f mm from the board and %.3f mm from Mains copper at the nominal seating" % (wallf["to_board_mm"], wallf["to_mains_copper_mm"]) in body
    assert "(z -6.60)" in body and "(z 6.00, 12.6 mm above the floor's underside)" in body and wallf["top_z_mm"] == pytest.approx(6.0) and wallf["back_in_front_of_wall_plane_mm"] == pytest.approx(0.5) and wallf["front_behind_plate_plane_mm"] == pytest.approx(0.2)
    assert "credited with no creepage and no clearance" in body and "unfilled printed plastic" in body
    assert "film" not in body.split("**Check against the criterion.**")[1].replace("no film", "")
    assert "case-drawings.svg" in body and os.path.exists(os.path.join(CASE_DIR, "out", "case-drawings.svg"))
    assert "W-10's barrier in the tray is not built" in body and "restores the lift of W-9 1c" in body


def test_c2_the_case_inside_the_former_outline_and_the_wall_opening_are_the_models(record, results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C2: The case drawing or model lies wholly within the spreader plate's outline in both directions across the wall, so that only the plate touches the wall, and states the opening in the plastic wall as the plate outline plus a stated clearance, with no larger opening needed for the case, the blades or the harness, which sit in the cavity. Cutting the wall is out of scope.
    body = sec(record, "C2")
    c2 = named(results, "c2.case_within_former_outline")["figures"]
    ext, plate = c2["case_extent_mm"], c2["former_outline_mm"]
    got = [float(x) for x in re.search(r"case extent u (-?\d+\.\d+) to (-?\d+\.\d+), z (-?\d+\.\d+) to (-?\d+\.\d+), v (-?\d+\.\d+) to (-?\d+\.\d+)", body).groups()]
    assert got == pytest.approx([ext["u0"], ext["u1"], ext["z0"], ext["z1"], ext["v0"], ext["v1"]], abs=0.006)
    got = [float(x) for x in re.search(r"outline is u (-?\d+\.\d+) to (-?\d+\.\d+), z (-?\d+\.\d+) to (-?\d+\.\d+)", body).groups()]
    assert got == pytest.approx([plate["u0"], plate["u1"], plate["z0"], plate["z1"]], abs=0.0006)
    assert num(body, r"is (\d+\.\d+) mm wide at the pilasters") == pytest.approx(named(results, "c3.plate_length")["figures"]["case_outer_width_mm"])
    assert num(body, r"(\d+\.\d+) mm tall") == pytest.approx(ext["z1"] - ext["z0"], abs=0.006)
    assert num(body, r"(\d+\.\d+) mm long \(") == pytest.approx(ext["v1"] - ext["v0"], abs=0.006)
    m = c2["margins_mm"]
    assert num(body, r"with (\d\.\d+) mm least margin") == pytest.approx(min(m.values()), abs=0.001)
    assert num(body, r"\((\d\.\d+) needed\)") == pytest.approx(c2["required_mm"]) == params["plate"]["min_margin_mm"]["value"]
    assert num(body, r": (\d+\.\d+) mm at each end") == pytest.approx(m["left"], abs=0.006) == pytest.approx(m["right"], abs=0.006)
    assert num(body, r"and (\d\.\d+) mm above and below") == pytest.approx(m["bottom"], abs=0.001) == pytest.approx(m["top"], abs=0.001)
    assert c2["parts_inside_plate_outline"] is True and "board, the blades and the parts lie inside it too" in body
    opening = named(results, "c2.wall_opening_stated")["figures"]
    assert num(body, r"together plus (\d\.\d) mm each side") == pytest.approx(opening["plate_clearance_mm"]) == params["plate"]["wall_opening_clearance_mm"]["value"]
    assert num(body, r"(\d+\.\d) x \d+\.\d mm, and nothing else") == pytest.approx(opening["opening_width_mm"])
    assert num(body, r"\d+\.\d x (\d+\.\d) mm, and nothing else") == pytest.approx(opening["opening_height_mm"])
    assert opening["opening_mm"]["u0"] == pytest.approx(plate["u0"] - opening["plate_clearance_mm"])
    assert opening["opening_mm"]["z1"] == pytest.approx(named(results, "c2.plate_covers_case_top")["figures"]["plate_upper_edge_z_mm"] + opening["plate_clearance_mm"]), "the opening covers the bar, not the former outline"
    assert num(body, r"\(u (\d+\.\d)\)\.") == pytest.approx(opening["cable_exit_u_mm"])
    assert opening["cable_exit_u_mm"] < opening["opening_mm"]["u1"] and "Cutting the wall is out of scope" in body
    wall = named(results, "c2.only_plate_touches_wall")["figures"]
    assert num(body, r"stands (\d\.\d+) mm in front of the machine wall's plane") == pytest.approx(wall["nearest_mm"]["tray"]) and "only the plate touches the wall" in body


def test_c3_the_plate_length_arithmetic_is_the_models_wherever_the_record_states_it(record, results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C3: The plate drawing states a length not less than the case drawing's outer width plus a bolt zone at each end for the wall bolts, with the arithmetic shown. The plate's size is provisional until the owner cuts and measures the wall, and the criterion holds at the figure then recorded. Making the plate is out of scope.
    c3 = named(results, "c3.plate_length")["figures"]
    assert c3["arithmetic"] == "%.2f + 2 x %.1f = %.2f <= %.2f" % (c3["case_outer_width_mm"], c3["bolt_zone_mm"], c3["required_mm"], c3["plate_length_mm"])
    assert (c3["case_outer_width_mm"], c3["bolt_zone_mm"], c3["plate_length_mm"]) == (59.5, params["plate"]["bolt_zone_mm"]["value"], params["plate"]["length_mm"]["value"])
    assert c3["required_mm"] == pytest.approx(c3["case_outer_width_mm"] + 2 * c3["bolt_zone_mm"]) and c3["margin_mm"] == pytest.approx(0.5)
    stated = "%.2f + 2 x %.1f = %.2f <= %.1f" % (c3["case_outer_width_mm"], c3["bolt_zone_mm"], c3["required_mm"], c3["plate_length_mm"])
    margin = "margin %.2f mm" % c3["margin_mm"]
    for tag in ("C3", "C11"):
        assert stated in sec(record, tag) and margin in sec(record, tag), tag
    assert "%.2f + 2 x %.1f = %.2f)" % (c3["case_outer_width_mm"], c3["bolt_zone_mm"], c3["required_mm"]) in sec(record, "C12")
    body = sec(record, "C3")
    assert num(body, r"plate is (\d+\.\d) mm long") == pytest.approx(c3["plate_length_mm"])
    assert num(body, r"case is (\d+\.\d+) mm wide at the pilasters") == pytest.approx(c3["case_outer_width_mm"])
    assert num(body, r"each end carries a (\d+\.\d) mm bolt zone") == pytest.approx(c3["bolt_zone_mm"])
    assert num(body, r"with a (\d\.\d) mm washer") == pytest.approx(params["plate"]["bolt_washer_dia_mm"]["value"])
    assert "one M4 bolt" in body and "provisional until the owner cuts and measures the wall" in body
    assert re.search(r"^4\. Plate size", record.split("## Owner list")[1], flags=re.M), "the provisional size is owner list item 4"
    bolts = named(results, "c3.wall_bolts_outside_case")["figures"]["bolts"]
    for tag in ("C10", "C11"):
        assert "u %.2f and %.2f" % tuple(b["bolt_u_mm"] for b in bolts) in sec(record, tag), tag
    washer_slack = (params["plate"]["bolt_zone_mm"]["value"] - params["plate"]["bolt_washer_dia_mm"]["value"]) / 2
    assert num(sec(record, "C11"), r"washer stands (\d\.\d+) mm clear of the case \((\d\.\d) asked\)", 1) == pytest.approx(min(b["washer_clear_of_case_mm"] for b in bolts), abs=0.005)
    assert num(sec(record, "C11"), r"\((\d\.\d) asked\)") == pytest.approx(washer_slack)


# ---------------------------------------------------------------- C4 to C9

def test_c4_the_lid_clearance_table_is_the_sweeps(record, results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C4: The case drawing or model shows the lid fitted and then removed by sliding or angling it away with the plate, case and board already placed at the machine's wall opening of the recorded plate outline plus clearance, with the lid's swept path clear of the opening, the plate and the case, and without removing the case or the plate. The check is made on the model against the board's layout geometry and the recorded opening, and the model's lid clearances are stated. The physical demonstration on a printed case is a separate leaf's. Designing the machine's wall opening is out of scope.
    body = sec(record, "C4")
    sweep = named(results, "c4.lid_sweep")["figures"]
    rows = table_rows(body, "Pose")
    fitted, whole = rows[0], rows[1]
    assert fitted[0] == "fitted" and whole[0] == "whole sweep"
    assert num(fitted[1], r"(\d\.\d+) mm") == pytest.approx(sweep["fitted_minimum_mm"], abs=0.0005)
    assert num(whole[1], r"(\d\.\d+) mm") == pytest.approx(sweep["minimum_clearance_mm"], abs=0.0005)
    fc = sweep["fitted_clearances_mm"]
    assert min(fc, key=fc.get) == sweep["worst_obstacle"] == "tray" and fitted[2].startswith("tray")
    assert num(fitted[2], r"\((\d\.\d+) mm to the plate") == pytest.approx(fc["plate"], abs=0.0005)
    assert num(fitted[2], r"(\d\.\d+) mm to the opening frame") == pytest.approx(fc["wall opening frame"], abs=0.0005)
    assert whole[2].startswith(sweep["worst_obstacle"])
    assert num(whole[2], r"tilt of (\d\.\d) degrees") == pytest.approx(num(sweep["worst_pose"], r"tilt (\d\.\d) deg"))
    assert num(body, r"The check's floor is (\d\.\d+) mm") == pytest.approx(sweep["floor_mm"])
    assert num(body, r"through (\d+) poses") == sweep["poses"]
    assert num(body, r"tilted (\d) degrees about") == pytest.approx(sweep["tilt_deg"]) == params["lid"]["sweep_tilt_deg"]["value"]
    assert num(body, r"out to a (\d+) mm slide") == pytest.approx(sweep["installed_frame"]["slide_checked_to_mm"])
    assert num(body, r"framed (\d+\.\d) mm deep") == pytest.approx(params["plate"]["wall_frame_depth_mm"]["value"])
    assert "framed %.1f mm deep" % params["plate"]["wall_frame_depth_mm"]["value"] in sweep["wall_aperture"]
    assert "without their vents, grooves and engraving" in body and "the same or smaller" in body
    assert "delivered-board leaf" in body and "without removing the case or the plate" in body


def test_c5_the_lid_screw_and_the_toes_are_where_the_model_puts_them(record, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C5: The case drawing or model places every lid screw or fixing where a driver reaches it with the case installed, and none right against the wall opening; the drawing states the driver's approach for each. If the lid is retained without screws, the drawing states the retention. Out of scope: the lid's shape and the machine's wall opening.
    body = sec(record, "C5")
    screw = named(results, "c5.lid_screw_reached")["figures"]
    u, v = screw["lid_screw_uv_mm"]
    assert "at u %.2f, v %.2f" % (u, v) in body
    assert num(body, r"(\d+\.\d) mm from the wall plane") == pytest.approx(screw["distance_to_wall_plane_mm"])
    assert num(body, r"\(at least (\d+) is asked\)") == pytest.approx(screw["required_distance_to_wall_mm"])
    assert num(body, r"and (\d+\.\d) mm from the opening frame") == pytest.approx(screw["distance_to_opening_frame_mm"], abs=0.05)
    assert screw["driver_shaft_interference_mm3"] == 0.0 and screw["head_proud_of_lid_top_mm"] == 0.0
    fixings = named(results, "c5.fixings_reached_installed")["figures"]["fixings"]
    shaft = next(f for f in fixings if f["fixing"] == "board screw H1")["driver_shaft_dia_mm"]
    assert num(body, r"a (\d\.\d) mm shaft") == pytest.approx(shaft)
    assert "straight along the screw's axis from below the installed case" in body and "head sits flush with the lid face" in body
    toes = named(results, "c5.toes_hold_plate_end")["figures"]
    assert "u %.1f and %.1f" % tuple(toes["toe_u_mm"]) in body
    assert num(body, r"up (\d\.\d) mm at the plate end") == pytest.approx(toes["lift_mm"])
    assert num(body, r"\((\d\.\d+) mm3 of interference each") == pytest.approx(min(toes["interference_mm3"]), abs=0.006)
    assert named(results, "c5.retention_stated")["passed"] and "two toes of the lid tuck under 45 degree hooks" in body
    assert "M3 x 10 countersunk" in body


def test_c6_what_holds_the_board_is_the_models_seat_and_the_h1_screw_is_the_params(record, results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C6: The board is held securely and stably by its one mounting hole H1 and by a printed ledge, hold-down fingers or ribs that belong to the tray and not to the removable lid, so that taking the lid off leaves the board held, and the case drawing states what holds the board. The case is printable at home and fixed with ordinary screws. Which of the ledge, fingers or ribs it uses is the case design's choice. Out of scope: the choice among ledge, fingers and ribs, and the board's outline.
    body = sec(record, "C6")
    seat = named(results, "c6.board_seat")["figures"]
    points = seat["seat_points"]
    assert "%d seat points" % len(points) in body and "within %.2f mm" % seat["tolerance_mm"] in body
    assert seat["contact_polygon_contains_board_centroid"] is True and "contact polygon holds the board's centroid" in body
    pillars = [p for p in points if p["support"].startswith("pillar")]
    words = {11: "eleven"}
    assert len(pillars) == 11 and "%s printed pillars" % words[len(pillars)] in body
    hold = named(results, "c6.hold_down_and_h1")["figures"]
    assert "%d pillars" % len(pillars) in hold["what_holds_the_board"]
    assert num(body, r"stands its hook (\d\.\d+) mm over the board's edge at v (\d+\.\d)") == pytest.approx(hold["hook_gap_over_board_mm"])
    assert num(body, r"over the board's edge at v (\d+\.\d)") == pytest.approx(hold["finger_v_mm"])
    u, v = hold["h1_uv_mm"]
    assert "(u %.1f, v %.1f)" % (u, v) in body
    h1_len = params["screws"]["h1_length_mm"]["value"]
    assert h1_len == 5.0 and "M3 x %.0f pan-head thread-forming screw" % h1_len in body
    assert num(body, r"into a (\d\.\d) mm pilot") == pytest.approx(params["case"]["pilot_dia_mm"]["value"])
    assert num(body, r"The lid's underside is (\d+\.\d) mm from the board") == pytest.approx(hold["lid_to_board_mm"], abs=0.05)
    assert "touches nothing of it" in body and "taking the lid off leaves the board held" in body
    for held in ("backing rib under the three blades", "hold-down finger on the left wall", "locating ribs on the left and far walls"):
        assert held in body
    assert {"blade backing rib", "hold-down finger on the left wall", "locating ribs on the left and far walls"} <= set(hold["what_holds_the_board"])


def test_c7_every_screw_row_is_the_checks_distance_and_figure(record, results, basis):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C7: Each screw or post of the case that meets the board, and the board's hole H1, keeps its pad and courtyard at the larger of the separation basis's signed clearance and creepage from mains copper, as the pre-order check's mounting_hole rule holds it, on every layer, so no safety property depends on a screw's material. The case drawing or model states each screw's centre and its distance from the nearest mains copper in the board's design. Out of scope: the position of the board's hole H1, which the layout fixed.
    body = sec(record, "C7")
    check = named(results, "c7.screws_clear_of_mains_copper")["figures"]
    rows = table_rows(body, "Screw")

    def key(label):
        return re.sub(r"[^a-z0-9.\-]", "", label.lower())

    by = {key(s["screw"]): s for s in check["screws"]}
    assert len(rows) == len(check["screws"]) == 8
    for label, centre, least, nearest, figure in rows:
        s = by[key(label)]
        assert [float(x) for x in centre.split(",")] == pytest.approx(s["centre_uvz_mm"], abs=0.006), label
        assert num(least, r"(\d+\.\d+) mm") == pytest.approx(s["distance_mm"], abs=0.006), label
        assert num(figure, r"(\d+\.\d) mm") == pytest.approx(s["required_mm"]), label
        assert ("top copper" if s["layer"] == "F.Cu" else "bottom copper") in nearest, label
        if nearest.startswith("pad"):
            assert s["nearest_item"] in nearest, label
        assert s["pass"] is True
    margins = {s["screw"]: s["distance_mm"] - s["required_mm"] for s in check["screws"]}
    least = min(margins, key=margins.get)
    assert num(body, r"The least margin over its figure is (\d\.\d+) mm") == pytest.approx(margins[least], abs=0.005)
    assert least == "lid screw" and "at the lid screw" in body
    assert named(results, "c7.screws_clear_of_mains_copper")["summary"].count("%.2f" % margins[least]) == 1
    h1 = named(results, "c7.h1_pad_and_courtyard")["figures"]
    top, bottom = h1["layers"]["F.Cu"], h1["layers"]["B.Cu"]
    assert num(body, r"pad stands (\d+\.\d+) mm \(top\) and (\d+\.\d+) mm \(bottom\)") == pytest.approx(top["pad_mm"])
    assert num(body, r"pad stands \d+\.\d+ mm \(top\) and (\d+\.\d+) mm \(bottom\)") == pytest.approx(bottom["pad_mm"])
    assert num(body, r"courtyard (\d+\.\d+) mm and (\d+\.\d+) mm from mains copper") == pytest.approx(top["courtyard_mm"])
    assert num(body, r"courtyard \d+\.\d+ mm and (\d+\.\d+) mm from mains copper") == pytest.approx(bottom["courtyard_mm"])
    assert num(body, r"against (\d\.\d) mm, the larger of") == pytest.approx(h1["required_mm"]) == max(basis["clearance_mains_mm"], basis["creepage_mains_mm"])
    assert num(body, r"clearance \((\d\.\d) mm\)") == pytest.approx(basis["clearance_mains_mm"])
    assert num(body, r"creepage \((\d\.\d) mm\)\.") == pytest.approx(basis["creepage_mains_mm"])
    assert num(body, r"least (\d+\.\d+) mm against") == pytest.approx(min(top["courtyard_mm"], bottom["courtyard_mm"], top["pad_mm"], bottom["pad_mm"]), abs=0.006)
    assert "No safety property depends on a screw's material" in body


def test_c8_both_slot_rows_are_the_checks_gaps(record, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C8: No part of the tray, the lid or any rib or barrier crosses the mouth of either 1.5 mm slot open at the board's right edge (slot A from board (51.0, 49.44) to (65.0, 50.94) and slot B from (51.0, 65.46) to (65.0, 66.96), as the board's layout plan states them), so the creepage the slots lengthen is not shortened; the case drawing or model shows the clearance at each mouth. Out of scope: the slots' dimensions, which the layout fixed.
    body = sec(record, "C8")
    check = named(results, "c8.slot_mouths_clear")["figures"]
    slots = {s["slot"]: s for s in check["slots"]}
    rows = {r[0]: r for r in table_rows(body, "Slot")}
    assert set(rows) == set(slots) == {"A", "B"}
    for name, (_, tray, lid, least) in rows.items():
        g = slots[name]["gaps_mm"]
        assert num(tray, r"(\d+\.\d+)") == pytest.approx(g["tray"], abs=0.0005)
        assert num(lid, r"(\d+\.\d+)") == pytest.approx(g["lid_single"], abs=0.006)
        assert "film" not in g
        assert num(least, r"(\d+\.\d+)") == pytest.approx(slots[name]["least_mm"], abs=0.0005)
        assert slots[name]["least_mm"] >= check["required_mm"]
        v0, v1 = slots[name]["v_mm"]
        assert re.search(r"[Ss]lot %s \(board \(51\.0, [\d.]+\) to \(65\.0, [\d.]+\)\) (?:lies )?at v %.2f to %.2f" % (name, v0, v1), body), name
    assert num(body, r"within (\d\.\d) mm of either slot's open area") == pytest.approx(check["required_mm"])
    assert "its mouth at the board's right edge (u %.0f) included" % slots["A"]["mouth_u_mm"] in body
    assert num(body, r"The (\d\.\d) mm is the right wall's inner face") == pytest.approx(min(s["least_mm"] for s in slots.values()))
    assert num(body, r"stands (\d\.\d) mm off the board's edge") == pytest.approx(min(s["least_mm"] for s in slots.values()))
    assert num(body, r"least (\d\.\d+) mm against (\d\.\d) mm") == pytest.approx(min(s["least_mm"] for s in slots.values()))
    assert "mouth 3.0 to wall (needs 2.0)" in body


def test_c9_the_backing_rib_the_force_and_the_deflection_arithmetic(record, results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C9: The tray carries rigid backing, a rib or pad, under the board face beneath J911, J921 and J941, and the case drawing shows the push-on direction of the 6.3 mm terminals and the support. The model shows the backing's contact over the board face under each blade and a stated stiffness basis for it (its section and span), so that a terminal pushed on does not move the board against the triac leads. The physical push-on demonstration on a printed tray is a separate leaf's. Out of scope: the terminals' own retention force.
    body = sec(record, "C9")
    fig = named(results, "c9.backing_contact_and_stiffness")["figures"]
    assert len(fig["contact"]) == 3 and all(c["contact_fraction"] == 1.0 for c in fig["contact"])
    width, depth = fig["rib_section_mm"]
    assert "%.1f mm wide and %.1f mm deep" % (width, depth) in body
    v0, v1 = fig["contact"][0]["rib_v_mm"]
    assert "at v %.2f to %.2f" % (v0, v1) in body
    assert "%.1f mm2 of contact under each" % fig["contact"][0]["contact_area_mm2"] in body and "contact fraction 1.0" in body
    assert "it spans %.1f and %.1f mm between buttresses" % tuple(fig["rib_span_between_buttresses_mm"]) in body
    assert num(body, r"push-on force is (\d+\.\d) N") == pytest.approx(fig["insertion_force_N"]) == params["blade"]["insertion_force_N"]["value"]
    assert 17 * 4.4482216 == pytest.approx(fig["insertion_force_N"], abs=0.05) and "17 lbf" in body
    assert num(body, r"section it has at v (\d+)") == pytest.approx(fig["section_at_v_mm"])
    assert num(body, r"\(area (\d+\.\d) mm2") == pytest.approx(fig["section_area_mm2"], abs=0.05)
    assert num(body, r"second moment (\d+) mm4") == pytest.approx(fig["second_moment_mm4"], abs=0.5)
    assert num(body, r"modulus (\d+) MPa") == pytest.approx(fig["modulus_MPa"])
    assert num(body, r"over a span of (\d+\.\d+) mm") == pytest.approx(fig["span_mm"])
    force, span, young, inertia = fig["insertion_force_N"], fig["span_mm"], fig["modulus_MPa"], fig["second_moment_mm4"]
    deflection = force * span ** 3 / (3 * young * inertia)
    assert deflection == pytest.approx(fig["deflection_at_blades_mm"], abs=0.0006)
    assert "%.1f x %.2f^3 / (3 x %d x %d) = %.3f mm" % (force, span, young, round(inertia), deflection) in body
    assert num(body, r"triac end against the plate, which is (\d\.\d+) mm\. That is compared with (\d\.\d+) mm, a design figure") == pytest.approx(fig["deflection_at_triac_end_mm"], abs=0.0005)
    assert num(body, r"compared with (\d\.\d+) mm, a design figure") == pytest.approx(fig["allowed_mm"])
    assert fig["deflection_at_triac_end_mm"] < fig["allowed_mm"] and "0.006 mm at the triac end against 0.05 mm, a design allowance with no external source" in body
    assert "`material.allowed_board_motion_mm`" in body and "not compared with anything" in body and fig["allowed_mm"] == params["material"]["allowed_board_motion_mm"]["value"]
    assert "ASA sheet's 2010 MPa rounded down" in body and "delivered-board leaf" in body
    assert "from below when installed" in body and "along `-z`, into the board" in body


# ---------------------------------------------------------------- C10 to C12

def test_c10_earth_bond_mechanism_measurement_and_recommendation(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C10: The case record states how the spreader plate is bonded to protective earth: the mechanism assumed, the plate screwed to the machine's steel wall, earthed through the mains-inlet earth, which the owner confirms, and the four-wire measurement the bring-up task holds it to. It also records the owner's decision, with his words and the date, whether the plate carries its own dedicated earth strap or relies on the wall alone, and the case drawing shows the strap if there is one. Taking the measurement is out of scope.
    body = sec(record, "C10")
    assert "screwed to the machine's metal wall" in body and "mains-inlet earth" in body
    assert "The owner confirms" in body
    assert "four-wire" in body and "DEL-HW-BRING-UP.C6" in body
    rec = body.split("**Recommendation.**")[1].split("**Owner's decision.**")[0]
    assert "dedicated earth strap" in rec and "ring terminal under one wall bolt" in rec
    assert "unknown finish" in rec and "not known until it is measured" in rec
    # the record states where the declared figure and test current are declared; it states none it does not have
    assert "declared" in body and "test current" in body
    assert not re.search(r"\d+(\.\d+)? ?(m?(ohm|Ω)|A\b)", body.split("**Measurement.**")[1].split("**Recommendation.**")[0].replace("four-wire", "")), \
        "no resistance or test current is stated until a repository source declares one"


def test_c10_owners_decision_field_exists_and_the_drawing_carries_a_strap_if_one_is_chosen(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C10: The case record states how the spreader plate is bonded to protective earth: the mechanism assumed, the plate screwed to the machine's steel wall, earthed through the mains-inlet earth, which the owner confirms, and the four-wire measurement the bring-up task holds it to. It also records the owner's decision, with his words and the date, whether the plate carries its own dedicated earth strap or relies on the wall alone, and the case drawing shows the strap if there is one. Taking the measurement is out of scope.
    body = sec(record, "C10")
    field = re.search(r"^Owner's decision \(strap or wall alone\), in his words:(.*?)Date:(.*)$", body, flags=re.M)
    assert field, "the owner's decision field is missing from the earth bond section"
    words = field.group(1).strip().strip("_").strip()
    svg_path = os.path.join(CASE_DIR, "out", "plate-drawing.svg")
    assert os.path.exists(svg_path)
    if words and re.search(r"\bstrap\b", words, flags=re.I) and not re.search(r"no strap|wall alone", words, flags=re.I):
        assert re.search(r"strap", read(svg_path), flags=re.I), "the owner chose a strap but the plate drawing does not show it"
        assert field.group(2).strip().strip("_").strip(), "a decision is recorded with its date"
    if not words:
        assert "**open: the field is blank until the owner fills it**" in body, "a blank decision is stated as open"
        assert "no strap is decided; the drawing shows none" in body


def test_c11_fitting_and_removal_order_and_wall_bolts_outside_the_case(record, results, rng):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C11: The case record states the order in which the plate, case, board and lid are fitted and removed, and shows that the wall bolts stand outside the case so the plate, case and board leave the wall as one unit, that each triac tab screw is reached by a driver through the case, and that the blade terminals stay reachable with the lid on. Making the parts and fitting them to the machine are out of scope.
    body = sec(record, "C11")
    fitting = body.split("**Installation order**")[1].split("**Silent failures")[0]
    assert [int(n) for n in re.findall(r"^(\d+)\. ", fitting, flags=re.M)] == list(range(1, 11))
    order = ["tray is fixed to the bar", "board is lowered straight into the tray", "tab is bolted to the bar",
             "lid is fitted", "bar is bolted to the wall", "receptacles are pushed on"]
    at = [fitting.index(w) for w in order]
    assert at == sorted(at), "plate, tray, board, tabs, lid, wall, receptacles must be fitted in this order"
    removal = body.split("**Removal**")[1].split("**Wall bolts")[0]
    assert removal.index("pull the receptacles") < removal.index("unbolt the bar from the wall") < removal.index("remove the lid screw")
    assert "Nothing is desoldered and no lead is bent" in removal
    assert "leave the wall as one unit" in body
    bolts = named(results, "c3.wall_bolts_outside_case")
    assert bolts["passed"] and all(b["washer_clear_of_case_mm"] >= 0.5 for b in bolts["figures"]["bolts"])
    drivers = named(results, "c11.tab_screw_driver_reached")["figures"]
    tilt = {d["tilt_deg"] for d in drivers["drivers"].values()}
    assert tilt == {5.5} and num(body, r"rising toward `\+v` at (\d\.\d) degrees") == 5.5
    gap = {round(d["nearest_gap_mm"], 2) for d in drivers["drivers"].values()}
    assert num(body, r"nearest tray wall (\d\.\d+) mm") in gap
    tilts = [t for c in named(rng["checks"], "c16.seating_range")["figures"]["combinations"] for t in c["driver_tilt_deg"].values()]
    assert num(body, r"\((?:nominal seating; )?(\d\.\d) to \d\.\d degrees across the seating range") == min(tilts)
    assert num(body, r"nominal seating; \d\.\d to (\d\.\d) degrees across the seating range") == max(tilts)
    assert num(body, r"against a (\d+) degree limit") == pytest.approx(drivers["limit_deg"])
    assert num(body, r"the nearest tray wall (\d\.\d+) mm from the (\d\.\d) mm shaft", 2) == pytest.approx(drivers["driver_shaft_dia_mm"])
    blades = named(results, "c11.blade_terminals_reachable_lid_on")["figures"]["blades"]
    assert all(b["line_from_above_reaches_blade"] and b["blade_inside_aperture"] for b in blades)
    assert "stay reachable with the lid on" in body
    assert num(body, r"(\d\.\d) x \d+\.\d+ mm bay") == pytest.approx(blades[0]["aperture_mm"][0])
    assert num(body, r"\d\.\d x (\d+\.\d+) mm bay") == pytest.approx(blades[0]["aperture_mm"][1], abs=0.005)


def test_c12_the_plate_is_flat_with_only_the_listed_holes_and_the_sizes_are_the_models(record, params, model, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C12: The case record gives the spreader plate's drawing in the printed-case form, a flat plate with nothing cut from it, how the plate is made or sourced, and the interface material of the triac faces to the plate and of the plate to the wall, since none is in the catalogue
    body = sec(record, "C12")
    plate = params["plate"]
    info = model.info["plate"]
    height = info["z1"] - info["z0"]
    m = re.search(r"\*\*(\d+\.\d) mm long, (\d+) mm wide \(its height installed\) and (\d+\.\d) mm thick\*\*", body)
    assert m and tuple(float(x) for x in m.groups()) == pytest.approx((plate["length_mm"]["value"], height, plate["thickness_mm"]["value"])) and height == plate["height_mm"]["value"]
    assert info["u1"] - info["u0"] == pytest.approx(plate["length_mm"]["value"]) and info["z0"] == plate["lower_edge_z_mm"]["value"] == 6.0
    assert "nothing cut from it" in body and "eight holes" in body
    tap, tray_screws, bolts = 2, params["screws"]["tray_plate_count_per_pilaster"]["value"] * 2, len(info["bolt_zs"]) * 2
    assert tap + tray_screws + bolts == 8 and len(info["bolt_zs"]) == 1
    assert "two M3 holes tapped through the whole plate from the triac side" in body and "four M3 countersunk holes" in body and "two 4.5 mm holes for the M4 wall bolts" in body
    assert num(body, r"\((\d\.\d) mm tapping drill") == pytest.approx(params["triac"]["plate_tap_drill_mm"]["value"])
    assert num(body, r"tapping drill, (\d\.\d) mm deep") == pytest.approx(plate["thickness_mm"]["value"]), "tapped through the whole plate"
    assert params["plate"]["bolt_dia_mm"]["value"] + 0.5 == pytest.approx(4.5)
    assert num(body, r"head diameter (\d\.\d) mm") == pytest.approx(params["screws"]["tray_plate_head_dia_mm"]["value"])
    assert "standard 20 x %d mm flat aluminium bar and cuts it to 80 mm" % plate["thickness_mm"]["value"] in body
    assert "not in the catalogue and is not priced" in body
    assert num(body, r"bar is at least (\d+\.\d) mm long") == pytest.approx(named(results, "c3.plate_length")["figures"]["required_mm"])
    assert "59.50 + 2 x 10.0 = 79.50)" in body and "%.0f mm wide, a standard stock width" % height in body


def test_c12_the_departure_from_the_owners_slot_words_interface_depth_and_what_it_replaces_are_stated(record, params, model, results, rng):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C12: The case record gives the spreader plate's drawing in the printed-case form, a flat plate with nothing cut from it, how the plate is made or sourced, and the interface material of the triac faces to the plate and of the plate to the wall, since none is in the catalogue and none is priced. It states the depth the case and plate add behind the board and grades it as unconfirmed for the owner to check at assembly, and states the order in which the board, case and plate are fitted and removed. It replaces what the earlier ear-and-bracket form recorded for these (the bracket's drawing, its spacers and its mounts); the thermal analysis of the triacs' interface to the wall is the assembly judgement's and is out of scope, as is making or sourcing the plate.
    body = sec(record, "C12")
    said = "short vertical slot or a hole about 1 mm oversize"
    assert said in body and said in read(os.path.join(BOARD_DIR, "assembler-fitting-record.md")), "the owner's words quoted are the ones the repository records"
    assert "needs a nut on the face that lies on the wall" in body and "would put a screw head in the heat path" in body
    assert "`owner-sign-off.md` W-19 records the departure, signed on the owner's behalf; owner list item 3 asks him to confirm it" in body
    assert "tip stands at most" in body and "4.01 mm inside the 5.0 mm plate" in body and "engages at least 4.76 - 1.32 = 3.44 mm of thread" in body
    seat = params["seating"]
    hi = seat["body_underside_mm"]["max"] + params["triac"]["A_mm"]["value"] - params["triac"]["L_mm"]["value"]
    lo = seat["body_underside_mm"]["min"] + params["triac"]["A_mm"]["value"] - params["triac"]["L_mm"]["value"]
    assert "derived (%.1f mm, range %.1f to %.1f)" % (named(results, "c16.seat_clear_of_leads_and_plate_hole")["figures"]["tab_hole_z_mm"], lo, hi) in body
    assert "thermal compound" in body and "0.027 K/W" in body and "0.027 K/W" in read(os.path.join(BOARD_DIR, "circuit-proof.md"))
    assert "not in the catalogue and is not priced" in body
    assert "unconfirmed" in body.split("**Depth the case and plate add")[1].split("**Order of fitting")[0]
    behind = -params["case"]["z_floor_bottom_mm"]["value"] - params["parts"]["board_thickness_mm"]["value"]
    assert num(body, r"adds (\d\.\d) mm \(the tray's outer top face") == pytest.approx(behind)
    v1 = named(results, "c2.case_within_former_outline")["figures"]["case_extent_mm"]["v1"]
    plate_face = model.v_plate
    wall_face = plate_face - params["plate"]["thickness_mm"]["value"]
    assert num(body, r"stands (\d+\.\d) mm from the plate's wall face") == pytest.approx(v1 - wall_face, abs=0.01)
    assert num(body, r"inner face at v (-\d\.\d)") == pytest.approx(plate_face, abs=0.01)
    assert num(body, r"wall face at v (-\d\.\d)") == pytest.approx(wall_face, abs=0.01)
    assert num(body, r"the case then runs from v (-\d\.\d+) to (\d+\.\d+)") == pytest.approx(named(results, "c2.case_within_former_outline")["figures"]["case_extent_mm"]["v0"], abs=0.006)
    replaced = body.split("**What this replaces.**")[1]
    division = read(os.path.join(os.path.dirname(os.path.dirname(BOARD_DIR)), "..", "docs", "sunbeam-em7000", "controller-board-division.md"))
    for heading in ("**The bracket.**", "**The two mounts are mounting holes", "**The order of fitting and of removal.**", "**The depth the bracket adds, unconfirmed.**"):
        assert heading in division, "the earlier form's record %s must still exist where the record says it is" % heading
    for word in ("bracket drawing", "spacers", "mounts", "controller-board-division.md"):
        assert word in replaced
    assert "*Fitting and removal order*" in body and "*The plate's earth bond*" in body


# ---------------------------------------------------------------- C13

FORMS = ("single", "stone", "two")
VERDICT = re.compile(r"met|not met \(judge: partly met\)")


def render_path(folder, path):
    return os.path.join(folder, path)


def camera(path, form):
    """The camera a render is of: the file name without its form and extension."""
    stem = os.path.basename(path)[:-len(".png")]
    for prefix in ("flow-%s-" % form, "%s-" % form):
        if stem.startswith(prefix):
            return stem[len(prefix):]
    return stem


def verdict_table(body):
    found = [rows for header, rows in tables(body) if header[:2] == ["#", "Bone"]]
    assert len(found) == 1, "one table of the judge's verdicts"
    return found[0]


def test_c13_the_rubric_is_the_judges_eight_lines(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    body = sec(record, "C13")
    rubric = [rows for header, rows in tables(body) if header[:2] == ["#", "Rubric line"]]
    assert len(rubric) == 1 and [r[0] for r in rubric[0]] == ["R%d" % n for n in range(1, 9)]
    assert all(len(r) == 3 and r[1] and r[2] for r in rubric[0]), "each line states the rule and why it belongs"
    assert "The rubric and every verdict in this section are the judge's" in body
    assert "judged the case four times" in body and "only the fourth was made from correctly-handed images" in body and "kept as history" in body and "the design owner's own earlier table is withdrawn" in body


def test_c13_every_rubric_line_has_a_verdict_per_form_and_an_existing_render_for_each_view(record, renders):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    body = sec(record, "C13")
    rows = verdict_table(body)
    assert [r[0] for r in rows] == ["R%d" % n for n in range(1, 9)] and all(len(r) == 8 for r in rows)
    seen = {form: set() for form in FORMS}
    for row in rows:
        for form, (verdict, views) in zip(FORMS, ((row[1], row[2]), (row[3], row[4]), (row[5], row[6]))):
            assert VERDICT.fullmatch(verdict), "each rubric line is recorded as met or not met per form: %r" % row
            paths = re.findall(r"`([^`]+\.png)`", views)
            assert paths, "each verdict names the view that shows it: %r" % row
            for p in paths:
                assert os.path.isfile(render_path(renders, p)), "the view %s must be a render that exists" % p
                assert "logo-preview" not in p, "the logo preview is not used in the judgement"
                seen[form].add(camera(p, form))
        assert row[7], "the judge's reason is recorded"
    for form, cameras in seen.items():
        assert len(cameras) >= 3, "each form is judged from at least three angles: %s %s" % (form, sorted(cameras))
        assert len(cameras) >= 5, "the record says the table names at least five cameras per form: %s" % form
    assert "logo-preview.png" in body and "is not used in the judgement" in body
    assert os.path.isfile(os.path.join(CASE_DIR, "renders", "directions", "logo-preview.png"))


def test_c13_the_score_sentence_and_r6_are_what_the_table_says(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    body = sec(record, "C13")
    rows = verdict_table(body)
    met = [sum(1 for r in rows if r[col] == "met") for col in (1, 3, 5)]
    assert [sum(1 for r in rows if r[col].startswith("not met")) for col in (1, 3, 5)] == [8 - m for m in met]
    m = re.search(r"Score: bone meets (\d+) of 8, stone (\d+) of 8, two-colour (\d+) of 8", body)
    assert m and [int(x) for x in m.groups()] == met
    assert "recorded: %d, %d and %d of 8 met" % tuple(met) in body
    assert all(rows[5][col] == "met" for col in (1, 3, 5)) and rows[5][0] == "R6"
    assert "No line was judged failed outright in any form" in body
    partly = re.search(r"bone partly meets (\d) \(R2, R5\), stone (\d) \(R5\) and two-colour (\d) \(R4, R7\)", body)
    assert partly and [int(x) for x in partly.groups()] == [8 - m for m in met] == [2, 1, 2] and met == [6, 7, 6]
    assert "The judge's verdicts, fourth judgement, per form" in body and "regenerated renders" in body and "hero" not in body
    assert all(r[col] != "not met" for r in rows for col in (1, 3, 5)), "a middle verdict is recorded as not met with the judge's word beside it"
    assert "Good enough to publish: yes, all three" in body


def test_c13_the_views_the_record_lists_all_exist(record, renders):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    views = sec(record, "C13").split("**The views.**")[1].split("\n\n")[0]
    installed, other = views.split("Six more per form")
    names = lambda text: [n for n in re.findall(r"`([^`]+)`", text) if re.fullmatch(r"[a-z0-9-]+", n) and n not in FORMS]
    flow, plain = names(installed), names(other.split("Two sheets")[0])
    assert len(flow) == 10 and len(plain) == 6 and "ten per form" in installed and "Six more" in views
    for form in FORMS:
        for n in flow:
            assert os.path.isfile(render_path(renders, "directions/flow-%s-%s.png" % (form, n))), (form, n)
        for n in plain:
            assert os.path.isfile(render_path(renders, "%s-%s.png" % (form, n))), (form, n)
    for sheet in re.findall(r"`(directions/[a-z-]+-sheet\.png)`", views):
        assert os.path.isfile(render_path(renders, sheet)), sheet
    assert "1600 x 1200" in views and "cut at its swap layers" in views
    with open(render_path(renders, "directions/flow-single-above.png"), "rb") as fh:
        head = fh.read(24)
    assert struct.unpack(">II", head[16:24]) == (1600, 1200)


def test_c13_logo_forms_swap_layers_and_colours_match_the_model(record, params, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    body = sec(record, "C13")
    assert os.path.exists(os.path.join(CASE_DIR, "staircase-logo.svg")) and "case/staircase-logo.svg" in body
    assert "owner-held" in body and "owner's permission" in body
    logo = named(results, "c13.logo_present_in_each_form")["figures"]
    assert num(body, r"engraved (\d\.\d) mm deep") == pytest.approx(params["logo"]["groove_depth_mm"]["value"]) == pytest.approx(logo["groove_depth_mm"])
    assert num(body, r"in grooves (\d\.\d) mm wide") == pytest.approx(params["logo"]["groove_width_mm"]["value"]) == pytest.approx(logo["groove_width_mm"])
    assert num(body, r"(\d+\.\d) mm tall on the tray") == pytest.approx(params["logo"]["tray_height_mm"]["value"]) == pytest.approx(logo["tray_height_mm"])
    assert num(body, r"(\d+\.\d) mm tall on the lid") == pytest.approx(params["skins"]["flow"]["mark"]["lid_height_mm"]["value"]) == pytest.approx(logo["lid_height_mm"])
    assert num(body, r"stands (\d\.\d) mm toward the plate from the centre") == pytest.approx(logo["tray_logo_off_face_centre_mm"])
    assert logo["forms"] == ["single", "two"] and named(results, "c13.mark_on_lid")["passed"]
    assert named(results, "c13.forms_share_dimensions")["figures"]["geometry_identical"] is True
    assert named(results, "c13.forms_share_dimensions")["figures"]["inlay_part_present"] is False and "No inlay part exists" in body
    forms = params["skins"]["flow"]["forms"]
    assert re.search(r"\*\*bone\*\* \(%s," % re.escape(forms["single"]["tray_colour"]["value"]), body) and forms["single"]["tray_colour"]["value"] == forms["single"]["lid_colour"]["value"]
    assert re.search(r"\*\*stone\*\* \(%s," % re.escape(forms["single"]["alternate_colour"]["value"]), body) and forms["single"]["alternate_name"]["value"] == "stone"
    assert "a graphite tray (%s) and a bone lid" % forms["two"]["tray_colour"]["value"] in body
    assert forms["two"]["lid_colour"]["value"] == forms["single"]["lid_colour"]["value"] and forms["two"]["tray_floor_colour"]["value"] == forms["single"]["tray_colour"]["value"]
    swap = named(results, "c13.swap_layers_stated_and_proved")["figures"]
    start, thick, layer = swap["swap_start_mm"], swap["swap_thickness_mm"], swap["layer_mm"]
    assert start == forms["two"]["swap_start_mm"]["value"] and thick / layer == pytest.approx(forms["two"]["swap_layers"]["value"])
    assert "to %.1f mm, then three whole layers in the other colour, from %.1f to %.1f mm" % (start, start, swap["band_top_mm"]) in body
    assert swap["band_top_mm"] == pytest.approx(start + thick) and swap["start_whole_layers"] and swap["thickness_whole_layers"]
    assert "pinstripe %.1f mm high in the middle of each part's %.1f mm chamfer" % (thick, swap["chamfer_height_mm"]["lid"]) in body
    assert swap["chamfer_height_mm"]["lid"] == swap["chamfer_height_mm"]["tray"]
    assert "two swaps per part" in body
    assert round(swap["reliefs"]["tray logo"]["swap_layers_over_the_floor"]) == 3 and "three layers of bone lie over the tray logo's floor" in body
    assert round(min(swap["reliefs"][k]["swap_layers_over_the_floor"] for k in ("lid logo", "streamline grooves", "far-end block bars"))) == 2
    assert "two or three layers of graphite over the lid's groove floors" in body
    crossed = swap["lid_openings_crossed"]
    assert "all %d vents, the three bays and the screw's countersink" % crossed["vents"] in body and crossed["vents"] == crossed["vents_total"]
    assert len(crossed["bays"]) == 3 and crossed["countersink"] is True
    assert swap["tray_outlet_slits_crossed"] == [] and "It crosses no outlet slit of the tray" in body
    assert all(r["ok"] for r in swap["reliefs"].values()) and "The check `c13.swap_layers_stated_and_proved` holds the band to whole layers" in body
    assert swap["far_end_block"]["bars"] == 8 and "a blind block of eight bars" in record


def test_c13_the_cosmetic_items_the_judge_left_are_listed_with_the_models_figures(record, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    body = sec(record, "C13")
    items = re.findall(r"^(\d)\. (.*)$", body.split("**Known cosmetic items, as the judge left them.**")[1].split(CHECK_TABLE)[0], flags=re.M)
    assert [int(n) for n, _ in items] == [1, 2, 3, 4] and "None blocks publishing" in body
    gate = named(results, "c4.cable_gate_follows_the_slide")["figures"]
    length = gate["gate_v_mm"][1] - gate["gate_v_mm"][0]
    assert "cable gate" in items[0][1] and "%.1f mm of the rim is open" % length in items[0][1] and "on one side only" in items[0][1]
    assert "stepped left edge" in items[1][1] and "two-far-end.png" in items[1][1]
    assert "unproven on a real printer" in items[2][1] and "bone floor of the tray's logo" in items[2][1] and "pinstripe" in items[2][1]
    assert "flat in shadow" in items[3][1]


def test_c13_who_judged_and_how(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    body = sec(record, "C13")
    who = body.split("**Who judged.**")[1].split("\n\n")[0]
    assert "independent judge who did not design the case" in who
    assert "did not read this record or the model" in who
    assert "judged it as installed, with the board, the receptacle boots, their wires and the cable drawn in it" in who
    assert "The owner chooses between the options offered and is not a gate" in who
    assert "the single colour the judge recommends" in body and "leading with two-colour" in body
    assert re.search(r"^8\. Confirm that the traced logo vector", record.split("## Owner list")[1], flags=re.M)
    assert all(re.search(r"^%d\. " % n, record.split("## Owner list")[1], flags=re.M) for n in (9, 10, 11, 12))


# ---------------------------------------------------------------- C14

PARTS = ("tray", "lid_single", "lid_two")


def test_c14_printer_baseline_material_and_per_part_orientation_and_bed_fit(record, params, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    body = sec(record, "C14")
    pr = params["printer"]
    assert "common low-cost open-frame FDM machine" in body
    assert "%d x %d mm bed (%d mm tall)" % (pr["bed_x_mm"]["value"], pr["bed_y_mm"]["value"], pr["bed_z_mm"]["value"]) in body
    assert "%.1f mm nozzle" % pr["nozzle_mm"]["value"] in body and "%.1f mm layers" % pr["layer_mm"]["value"] in body
    assert "ASA is the baseline" in body
    for need in ("draft shield", "brim", "cardboard box"):
        assert need in body
    for other in ("PETG", "PLA", "PC"):
        assert other in body
    assert "are not the baseline" in body
    ini = read(os.path.join(CASE_DIR, "printer-220-asa.ini"))
    nozzle_t = int(re.search(r"^temperature = (\d+)", ini, flags=re.M).group(1))
    bed_t = int(re.search(r"^bed_temperature = (\d+)", ini, flags=re.M).group(1))
    brim = int(re.search(r"^brim_width = (\d+)", ini, flags=re.M).group(1))
    assert re.search(r"^draft_shield = enabled", ini, flags=re.M)
    assert "sets a %d mm brim, a draft shield and a %d degC nozzle with a %d degC bed" % (brim, nozzle_t, bed_t) in body
    fit = named(results, "c14.bed_fit")
    assert fit["passed"] and fit["figures"]["bed_mm"] == [pr["bed_x_mm"]["value"], pr["bed_y_mm"]["value"], pr["bed_z_mm"]["value"]]
    rows = table_rows(body, "Part")
    sizes = {"tray": rows[0], "lid_single": rows[1], "lid_two": rows[2]}
    assert len(rows) == 3 and rows[0][0] == "tray" and rows[1][0].startswith("lid, single") and rows[2][0].startswith("lid, two")
    for p in fit["figures"]["parts"]:
        cells = sizes[p["part"]]
        assert p["fits"] is True and cells[3] == "yes" and p["orientation"].startswith(cells[1])
        got = nums(cells[2], r"\d+\.\d+")
        assert got == pytest.approx(p["size_mm"], abs=0.006)
        assert max(got[:2]) <= pr["bed_x_mm"]["value"] and got[2] <= pr["bed_z_mm"]["value"]
    assert len(fit["figures"]["parts"]) == 3 and "not yet printed" in body and "Sliced and checked by geometry" in body
    assert "ventilation" in body and "unpleasant" in body


def test_c14_slicer_results_per_part_are_the_slicer_summaries(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    body = sec(record, "C14")
    summary = {part: slice_summary(part) for part in PARTS}
    by = dict(zip(PARTS, table_rows(body.split("**Supports, per part.**")[1], "Part")))
    for part, cells in by.items():
        off = summary[part]["supports_off"]
        assert off["support_generated"] is False
        assert "PrusaSlicer 2.9.7" in cells[1] and summary[part]["slicer"].startswith("PrusaSlicer-2.9.7")
        assert hms(cells[2]) == pytest.approx(off["print_time_s"], abs=1)
        assert num(cells[3], r"([\d.]+) g") == pytest.approx(off["filament_g"], abs=0.006)
        assert num(cells[3], r"\(([\d.]+) cm3\)") == pytest.approx(off["filament_cm3"], abs=0.006)
        assert int(cells[4]) == off["layers"]
        assert nums(cells[5], r"\d+\.\d+") == pytest.approx(off["bounding_box_mm"]["size"], abs=0.006)
    auto = dict(zip(PARTS, table_rows(body.split("**Supports-auto diagnostic.**")[1], "Part")))
    for part, cells in auto.items():
        sa = summary[part]["supports_auto"]
        assert num(cells[2], r"([\d.]+) mm3") == pytest.approx(sa["support_volume_mm3"], abs=0.06)
        assert num(cells[2], r"\(([\d.]+) mm of filament") == pytest.approx(sa["support_filament_mm"], abs=0.06)
        delta = sa["print_time_s"] - summary[part]["supports_off"]["print_time_s"]
        mm, ss = (int(x) for x in re.search(r"\+(\d+)m (\d+)s", cells[3]).groups())
        assert mm * 60 + ss == pytest.approx(delta, abs=1)
        assert num(cells[1], r"up to ([\d.]+) mm above the bed") == pytest.approx(max(r["print_z_mm"][1] for r in sa["regions"]), abs=0.06)
        assert int(num(cells[1], r"(\d+) places")) == len(sa["regions"])
    assert summary["lid_single"]["supports_off"]["print_time_s"] == summary["lid_two"]["supports_off"]["print_time_s"]
    assert summary["lid_single"]["supports_off"]["filament_g"] == summary["lid_two"]["supports_off"]["filament_g"]
    assert "lid, two-colour" in body and "two filament changes, after the layers that end at 0.4 and 1.0 mm" in body


def test_c14_support_totals_by_kind_and_the_diagnostic_entry_are_the_slicers(record, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    body = sec(record, "C14")
    tray, lid = slice_summary("tray"), slice_summary("lid_single")
    where = body.split("Where the slicer would add support, and why each is accepted.")[1].split("Every one of these places is accepted")[0]
    tray_text, lid_text = where.split("Lid:")[0], where.split("Lid:")[1].split("At the slicer's own detection")[0]
    kinds = tray["supports_auto"]["support_by_kind_mm"]
    for kind in ("flat_roof", "bed_side_roll_in", "sloped_face", "first_layer_patch"):
        assert "(%.1f mm" % kinds[kind] in tray_text, kind
    slits = len([o for o in named(results, "c15.openings_enumerated")["figures"]["openings"] if o["kind"] == "outlet slit"])
    assert "the roofs of the %d outlet slits (%.1f mm" % (slits, kinds["flat_roof"]) in tray_text
    lkinds = lid["supports_auto"]["support_by_kind_mm"]
    for kind in ("bed_side_roll_in", "sloped_faces_and_flat_roofs", "flat_roof", "first_layer_patch"):
        assert "(%.1f mm" % lkinds[kind] in lid_text, kind
    for part in ("lid_single", "lid_two"):
        assert slice_summary(part)["supports_auto"]["support_by_kind_mm"] == lkinds
    assert "the totals fall to %.1f mm on the tray and %.1f mm on each lid" % (tray["supports_auto_threshold_0"]["support_filament_mm"],
                                                                              lid["supports_auto_threshold_0"]["support_filament_mm"]) in body
    entries = {e["critical_feature"]: e for e in lid["supports_auto"]["supported_faces_that_are_critical"]}
    assert set(entries) == {"screw seat"} and len(lid["supports_auto"]["supported_faces_that_are_critical"]) == 1
    seat = entries["screw seat"]
    assert seat["flat_roof"] is False
    for part in ("lid_single", "lid_two"):
        s = slice_summary(part)
        assert s["supports_auto"]["supported_faces_that_are_critical"] == lid["supports_auto"]["supported_faces_that_are_critical"]
        assert len(s["supports_auto_threshold_0"]["supported_faces_that_are_critical"]) == 1
    zero = lid["supports_auto_threshold_0"]["supported_faces_that_are_critical"][0]
    assert zero["critical_feature"] == "screw seat"
    noise = lid["limits"]["noise_area_mm2"]
    assert seat["facet_area_mm2"] < noise, "the entry is under the noise area the rule tolerates"
    diag = body.split("**The diagnostic entry on a critical face.**")[1].split("\n\n")[0]
    assert "%.2f mm of support filament under %.2f mm2, facets at %.1f to %.1f degrees, none a flat roof" % ((seat["filament_mm"], seat["facet_area_mm2"]) + tuple(seat["angle_deg"])) in diag
    assert "(%.2f mm at the slicer's own threshold)" % zero["filament_mm"] in diag
    assert "`critical_entry_problems` of `case/slice.py`" in diag and "1.0 mm2 (`printer.noise_area_mm2`" in diag and noise == 1.0
    assert "at or above that area the rule stands unchanged, entry by entry" in diag and "summed over every entry of a part's run" in diag
    assert "The one entry, %.2f mm2, is under it" % seat["facet_area_mm2"] in diag
    assert "The entries move with the mesh" in diag and "the geometry of the seat did not change" in diag
    assert tray["supports_auto"]["supported_faces_that_are_critical"] == [] and tray["supports_auto_threshold_0"]["supported_faces_that_are_critical"] == []
    assert "The tray has no such entry" in diag
    flush = tray["supports_auto"]["flush_to_critical_plane"]
    slot = [f for f in flush if f["critical_face"] == "slot-rule faces"]
    barrier = [f for f in flush if f["critical_face"] == "plate-end faces"]
    assert len(slot) + len(barrier) == len(flush)
    assert "in %d places the diagnostic support would stand flush" % len(flush) in diag
    assert "(%d beside the slot-rule face at the outlet slits, %d beside a plate-end face)" % (len(slot), len(barrier)) in diag
    assert lid["supports_auto"]["flush_to_critical_plane"] == []
    for part in PARTS:
        assert slice_summary(part)["supports_off"]["support_generated"] is False
    assert "The design owner accepts the entry as a diagnostic entry, not a support that remains" in diag


def test_c14_geometry_check_of_overhangs_critical_faces_screws_and_no_machining(record, results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    body = sec(record, "C14")
    check = named(results, "c14.overhang")
    assert check["passed"] and check["figures"]["limit_deg"] == 45.0 and check["figures"]["bridge_limit_mm"] == 3.5
    parts = {p["part"]: p for p in check["figures"]["parts"]}
    for name, p in parts.items():
        assert p["non_bridgeable_clusters"] == [] and p["critical_faces_support_free"] is True
    tray, lid = parts["tray"], parts["lid_single"]
    assert parts["lid_two"]["overhang_clusters"] == lid["overhang_clusters"]
    assert num(body, r"the tray has (\d+) bridged roofs") == pytest.approx(tray["overhang_clusters"])
    assert num(body, r"each lid (\d+) of spans") == pytest.approx(lid["overhang_clusters"])
    assert "(%d degree overhang limit, %.1f mm bridge limit)" % (check["figures"]["limit_deg"], check["figures"]["bridge_limit_mm"]) in body
    for sentence, p in ((r"bridged roofs of spans ([\d., and]+) mm", tray), (r"of spans ([\d., and]+) mm, and none unbridgeable", lid)):
        quoted = nums(re.search(sentence, body).group(1), r"\d+\.\d+")
        spans = sorted({round(b["span_mm"], 2) for b in p["bridged_clusters"]})
        assert len(quoted) == len(spans) and quoted == pytest.approx(spans, abs=0.05), (quoted, spans)
    crit = body.split("Critical faces:")[1].split("no critical face needs support")[0]
    tray_crit, lid_crit = crit.split("; each lid's")
    for face, count in tray["critical_faces"].items():
        assert re.search(r"%s \(%d\)" % (re.escape(face), count), tray_crit), face
    for face, count in lid["critical_faces"].items():
        assert re.search(r"%s \(%d\)" % (re.escape(face), count), lid_crit), face
    assert "no critical face needs support" in body and "each slit's roof is a 2.0 mm bridge" in body
    assert tray["bridged_clusters"][0]["span_mm"] == pytest.approx(params["skins"]["flow"]["outlets"]["width_mm"]["value"], abs=0.01)
    fixing = body.split("**Fixings.**")[1].split("**Honest grade.**")[0]
    assert "M3 x %.0f countersunk (four, tray to plate)" % params["screws"]["tray_plate_length_mm"]["value"] in fixing
    assert "M3 x %.0f pan head (H1)" % params["screws"]["h1_length_mm"]["value"] in fixing
    assert "M3 x 10 countersunk (lid)" in fixing and "M3 x 5 pan head through the tab holes (two)" in fixing and "M4 wall bolts (two)" in fixing
    assert "No part needs post-print machining" in fixing
    for where in ("plate-end faces", "screw seats", "slot-mouth faces", "lid-fit faces"):
        assert where in body
    for why in ("exactly 45 degrees", "bridged", "first-layer patches"):
        assert why in body
    r10 = wall_resistance(10, params["plate"]["height_mm"]["value"] / 1000.0, params["plate"]["length_mm"]["value"] / 1000.0)
    nominal, hot = 25 + 9.09 * (r10 + 1), 40 + 9.09 * (r10 + 3)
    assert "nominal plate temperature of %.1f degC and a bound of %.1f degC" % (nominal, hot) in body


# ---------------------------------------------------------------- C15

def test_c15_finger_and_drip_result_per_opening_kind_match_the_model(record, results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    body = sec(record, "C15")
    fin = named(results, "c15.finger")
    kinds = {}
    for o in named(results, "c15.openings_enumerated")["figures"]["openings"]:
        kinds.setdefault(o["kind"], []).append(o)
    total = sum(len(v) for v in kinds.values())
    assert fin["passed"] and total == 52 and "all %d openings admit nothing" % total in body
    rows = {r[0]: r for r in table_rows(body, "Opening kind")}
    mapping = {"lid vent (louvre)": "louvre", "tray outlet slit": "outlet slit", "blade bay": "blade aperture",
               "cable notch": "cable notch", "finger slit": "finger slit", "seam": "seam"}
    assert set(rows) == set(mapping)
    for label, kind in mapping.items():
        assert int(rows[label][1]) == len(kinds[kind]), label
    assert all(o["admits"] == "nothing" for o in fin["figures"]["openings"])
    assert num(rows["lid vent (louvre)"][2], r"^(\d\.\d+) mm") == pytest.approx(kinds["louvre"][0]["smaller_dimension_mm"])
    assert num(rows["lid vent (louvre)"][2], r"\((\d\.\d+) mm at the face\)") == pytest.approx(params["skins"]["flow"]["louvre_width_mm"]["value"] / math.cos(math.radians(params["louvre"]["angle_deg"]["value"])), abs=0.005)
    assert num(rows["tray outlet slit"][2], r"(\d\.\d+) mm") == pytest.approx(kinds["outlet slit"][0]["smaller_dimension_mm"])
    notch, slit = kinds["cable notch"][0], kinds["finger slit"][0]
    assert "%.1f x %.1f mm" % (notch["smaller_dimension_mm"], notch["larger_dimension_mm"]) in rows["cable notch"][2]
    assert "%.1f x %.1f mm" % (slit["smaller_dimension_mm"], slit["larger_dimension_mm"]) in rows["finger slit"][2]
    assert "%.1f x %.2f mm" % (kinds["blade aperture"][0]["smaller_dimension_mm"], kinds["blade aperture"][0]["larger_dimension_mm"]) in rows["blade bay"][2]
    seams = sorted({o["smaller_dimension_mm"] for o in kinds["seam"]})
    assert nums(rows["seam"][2], r"(\d\.\d+) mm") == pytest.approx(seams) and seams == pytest.approx([0.2, 0.45])
    by_id = {o["opening"]: o for o in fin["figures"]["openings"]}

    def least(kind):
        return min(o["remaining_to_mains_copper_mm"] for o in fin["figures"]["openings"] if o["kind"] == kind)

    assert num(rows["lid vent (louvre)"][3], r"mains copper (\d+\.\d) mm") == pytest.approx(least("louvre"), abs=0.05)
    assert num(rows["tray outlet slit"][3], r"mains copper (\d+\.\d) mm") == pytest.approx(least("outlet slit"), abs=0.05)
    assert num(rows["cable notch"][3], r"(\d+\.\d) mm to mains copper") == pytest.approx(least("cable notch"), abs=0.05)
    assert num(rows["finger slit"][3], r"(\d+\.\d) mm to copper") == pytest.approx(least("finger slit"), abs=0.05)
    boots = named(results, "c15.finger_blades_receptacle_fitted")["figures"]["envelopes"]
    assert num(rows["blade bay"][3], r"disc of (\d\.\d+) mm \(typical\)") == pytest.approx(boots["typical"]["widest_disc_in_the_free_opening_mm"], abs=0.006)
    assert num(rows["blade bay"][3], r"and (\d\.\d+) mm \(largest common\)") == pytest.approx(boots["largest_common"]["widest_disc_in_the_free_opening_mm"], abs=0.006)
    assert by_id["blade bay J941"]["remaining_to_blade_mm"] == pytest.approx(num(rows["blade bay"][3], r"(\d\.\d+) mm from the boot to the blade"), abs=0.0006)
    assert float(params["finger"]["tip_dia_mm"]["value"]) < min(o["smaller_dimension_mm"] for o in kinds["blade aperture"])
    fp = params["finger"]
    assert "%.1f mm hemispherical tip" % fp["tip_dia_mm"]["value"] in body and "%d mm cone" % fp["cone_length_mm"]["value"] in body
    assert "%d mm cylinder" % fp["probe_dia_mm"]["value"] in body and "Lisun" in body and "61032" in body
    drip = named(results, "c15.drip")
    assert drip["passed"]
    assert "%d degree cone about the installed vertical" % drip["figures"]["cone_half_angle_deg"] in body
    assert "casts %d lines" % drip["figures"]["cone_lines_per_point"] in body
    assert all(r["reachable_from_outside"] == 0 and not r["reaches_mains_copper"] for r in drip["figures"]["per_opening"])
    assert len(drip["figures"]["per_opening"]) == total


def test_c15_receptacle_off_state_is_a_finding_with_the_models_figures_and_never_a_pass(record, results, rng):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    body = sec(record, "C15")
    heads = re.findall(r"^### (.*)$", body, flags=re.M)
    assert any(h.startswith("Finding:") for h in heads), "the receptacle-off state is stated under a heading that calls it a finding"
    finding = body.split("### Finding:")[1].split("\n**The enclosure the pollution-degree credit relies on.**")[0]
    assert not re.search(r"\bpass(es|ed)?\b", finding, flags=re.I), "the finding is never called a pass"
    assert "This is a finding, stated as one. It is not counted in any verdict" in finding
    for line in body.split("\n"):
        if re.search(r"-1\.62|-1\.99", line):
            assert not re.search(r"\bpass", line, flags=re.I)
    fig = named(results, "c15.finding_blades_no_receptacle")
    assert fig["kind"] == "finding" and fig["passed"] is None
    blades = fig["figures"]["blades"]
    stated = num(finding, r"within \*\*(-\d\.\d+) mm\*\* of the blade at J941 and at J921")
    assert stated == pytest.approx(blades["J941"]["tip_to_blade_mm"], abs=0.005)
    assert stated == pytest.approx(blades["J921"]["tip_to_blade_mm"], abs=0.005)
    assert num(finding, r"\*\*\+(\d\.\d+) mm\*\* at J911") == pytest.approx(blades["J911"]["tip_to_blade_mm"], abs=0.005)
    bay = blades["J941"]["bay_mm"]
    assert num(finding, r"The bay is (\d\.\d) x") == bay["across_thickness_u"] and num(finding, r"x (\d+\.\d+) mm, the gap") == pytest.approx(bay["across_width_v"], abs=0.005)
    assert num(finding, r"the gap the finger enters is (\d+\.\d) mm at J941") == pytest.approx(blades["J941"]["gap_the_finger_enters_mm"])
    assert num(finding, r"and (\d\.\d) mm at J911") == pytest.approx(blades["J911"]["gap_the_finger_enters_mm"])
    assert num(finding, r"fails from a lean of \+(\d\.\d+) degrees") == pytest.approx(blades["J941"]["standing_check_fails_at_lean"]["leaning_far_end_up_deg"])
    pitch = fig["figures"]["blade_pitch_mm"]["J941-J921"]
    assert num(finding, r"stand (\d\.\d) mm apart") == pytest.approx(pitch)
    assert num(finding, r"leaves (\d\.\d+) mm between two boots") == pytest.approx(named(results, "c18.boot_clearance")["figures"]["boot_to_boot_gap_mm"]["typical"]["J941-J921"])
    combos = named(rng["checks"], "c16.seating_range")["figures"]["combinations"]
    assert len(combos) == 64
    for combo in combos:
        found = combo["findings"]["c15.finding_blades_no_receptacle"]
        for blade in ("J941", "J911"):
            assert "%.2f" % abs(found[blade]["tip_to_blade_mm"]) in finding, "the range's receptacle-off figure %s is stated" % found[blade]["tip_to_blade_mm"]
    assert fig["figures"]["touchable_blades"] == ["J941", "J921"]
    ranged = named(rng["checks"], "c15.finding_blades_no_receptacle_seating_range")
    assert ranged["kind"] == "finding" and ranged["passed"] is None
    assert "reached in %s extreme seatings" % re.search(r"(\d+ of \d+) extreme seatings", ranged["summary"]).group(1) in finding
    assert ranged["summary"].count("64 of 64") == 1 and "64 of 64 extreme seatings" in finding
    assert "The owner accepted this residual on 2026-11-26" in finding and "\"Accept, state the rule (Recommended)\"" in finding and "service state inside the machine's own enclosure" in finding
    assert "**The rule: the machine is never energised with a receptacle off a blade.**" in finding


def test_c15_enclosure_statement_states_the_basis_credit_and_what_the_openings_leave(record, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    body = sec(record, "C15")
    enc = body.split("**The enclosure the pollution-degree credit relies on.**")[1]
    basis_text = read(os.path.join(BOARD_DIR, "separation-basis.yaml"))
    degree = int(re.search(r"^pollution_degree: (\d)", basis_text, flags=re.M).group(1))
    assert "pollution degree %d" % degree in enc and "case is the enclosure" in enc
    areas = named(results, "c15.openings_enumerated")["figures"]["open_areas"]
    assert num(enc, r"(\d+\.\d) mm2 of lid inlets \((\d+) slots\)") == pytest.approx(areas["lid_inlet_free_area_mm2"], abs=0.05)
    assert int(num(enc, r"mm2 of lid inlets \((\d+) slots\)")) == areas["lid_inlet_slot_count"]
    assert num(enc, r"(\d+\.\d) mm2 of tray outlets") == pytest.approx(areas["side_outlet_free_area_mm2"], abs=0.05)
    assert int(num(enc, r"tray outlets \((\d+) slits\)")) == areas["side_outlet_slit_count"]
    boots = named(results, "c15.finger_blades_receptacle_fitted")["figures"]["envelopes"]["typical"]["free_opening_area_mm2"]
    assert num(enc, r"(\d+\.\d) mm2 left round the three fitted boots") == pytest.approx(boots, abs=0.05)
    openings = named(results, "c15.openings_enumerated")["figures"]["openings"]
    notch = [o for o in openings if o["kind"] == "cable notch"][0]
    slits = [o for o in openings if o["kind"] == "finger slit"]
    assert num(enc, r"(\d+\.\d) mm2 of cable notch") == pytest.approx(notch["smaller_dimension_mm"] * notch["larger_dimension_mm"], abs=0.05)
    assert num(enc, r"(\d+\.\d) mm2 of finger slits") == pytest.approx(sum(o["smaller_dimension_mm"] * o["larger_dimension_mm"] for o in slits), abs=0.05)
    total = areas["lid_inlet_free_area_mm2"] + areas["side_outlet_free_area_mm2"] + boots + notch["smaller_dimension_mm"] * notch["larger_dimension_mm"] \
        + sum(o["smaller_dimension_mm"] * o["larger_dimension_mm"] for o in slits)
    assert num(enc, r"about (\d+) mm2 in all") == pytest.approx(total, abs=1.0)
    assert "%d openings of six kinds" % len(openings) in enc
    for what in ("What cannot enter", "What can", "air, fine dust, vapour"):
        assert what in enc


# ---------------------------------------------------------------- C16

def test_c16_range_with_sources_unconfirmed_and_the_32_extremes_result(record, params, rng, basis, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C16: The board-to-plate fit takes the scatter of the delivered triacs' seating, stated as a range of tab-hole height and lean, without loading the soldered leads: the tray's board seat and the barrier are shown by the model to meet at the range's extremes. The plate's tab holes are either a short slot or an oversize hole, or tapped holes drilled at the measured height of the delivered triacs with the tray printed to the measured values, and the case record states which the case takes; for tapped holes it states that the owner's acceptance of that departure from his ruling of 2026-11-24 (slot or oversize hole) is outstanding. The range with its source is recorded as unconfirmed for the owner to check at assembly.
    body = sec(record, "C16")
    seat = params["seating"]
    rows = {r[0]: r for r in table_rows(body, "Quantity")}
    assert "**unconfirmed**" in body
    assert all(seat[k]["unconfirmed"] is True for k in ("body_underside_mm", "lean_deg", "differential_lean_deg", "tab_face_to_lead_centre_mm", "lead_protrusion_below_board_mm", "outline_routing_mm", "lead_play_mm"))
    assert all(r[3] for r in rows.values()), "every bound has its source"
    assert "-%.1f to +%.1f mm" % (seat["outline_routing_mm"]["max"], seat["outline_routing_mm"]["max"]) in rows["board outline routing tolerance"][2]
    assert "-%.3f to +%.3f mm" % (seat["lead_play_mm"]["max"], seat["lead_play_mm"]["max"]) in rows["lead play in its drilled hole"][2]
    lo, hi = seat["body_underside_mm"]["min"], seat["body_underside_mm"]["max"]
    assert "%.2f to %.2f mm" % (lo, hi) in rows["body underside above the board face"][2]
    assert "%.1f to %.1f degrees" % (seat["lean_deg"]["min"], seat["lean_deg"]["max"]) in rows["common lean of both triacs"][2].replace("+", "")
    assert "0 to %.1f degrees" % seat["differential_lean_deg"]["max"] in rows["difference of lean between the two triacs"][2]
    assert "%.3f to %.2f mm" % (seat["tab_face_to_lead_centre_mm"]["min"], seat["tab_face_to_lead_centre_mm"]["max"]) in rows["tab face to lead centre"][2]
    assert "0 to %.1f mm" % seat["lead_protrusion_below_board_mm"]["max"] in rows["leads below the board"][2]
    for label, key in (("body underside above the board face", "body_underside_mm"), ("tab face to lead centre", "tab_face_to_lead_centre_mm")):
        assert rows[label][1].startswith("%s mm" % ("%g" % seat[key]["value"]))
    tab_lo = lo + (params["triac"]["A_mm"]["value"] - params["triac"]["L_mm"]["value"])
    tab_hi = hi + (params["triac"]["A_mm"]["value"] - params["triac"]["L_mm"]["value"])
    assert "%.1f to %.1f mm" % (tab_lo, tab_hi) in rows["tab-hole height above the board face"][2]
    assert "%.1f mm (derived)" % named(results, "c16.seat_clear_of_leads_and_plate_hole")["figures"]["tab_hole_z_mm"] in rows["tab-hole height above the board face"][1]
    seating = named(rng["checks"], "c16.seating_range")
    combos = seating["figures"]
    assert len(combos["combinations"]) == 64 and all(c["all_pass"] for c in combos["combinations"]) and seating["passed"] is True
    assert "model is built at all 64 extremes of body height, lean, tab-face distance, outline routing tolerance, lead play and plate edge" in body
    assert num(body, r"from any Mains copper to the plate is (\d\.\d+) mm") == pytest.approx(combos["worst_creepage_mm"], abs=0.0005)
    assert num(body, r"from a bare lead (\d\.\d+) mm, against") == pytest.approx(min(c["least_lead_mm"] for c in combos["combinations"]), abs=0.0005)
    assert num(body, r"against (\d\.\d) mm; the gap") == pytest.approx(basis["creepage_mains_mm"])
    assert num(body, r"the boot clearance is at least (\d\.\d+) mm") == pytest.approx(min(c["boot_least_clearance_mm"] for c in combos["combinations"]), abs=0.005)
    assert num(body, r"lid sweep clearance is at least (\d\.\d+) mm") == pytest.approx(min(c["lid_sweep_min_mm"] for c in combos["combinations"]), abs=0.0005)
    gaps = sorted({c["gap_mm"] for c in combos["combinations"]})
    assert num(body, r"the gap to the plate is (\d\.\d+) to") == gaps[0] and num(body, r"the gap to the plate is \d\.\d+ to (\d\.\d+) mm") == gaps[-1]
    tilts = [t for c in combos["combinations"] for t in c["driver_tilt_deg"].values()]
    assert num(body, r"reaches each tab screw at (\d\.\d) to") == min(tilts) and num(body, r"reaches each tab screw at \d\.\d to (\d\.\d) degrees") == max(tilts)
    seated = named(results, "c16.seat_clear_of_leads_and_plate_hole")["figures"]
    assert num(body, r"stand off the tray by at least (\d\.\d+) mm at the nominal seating") == pytest.approx(min(seated["lead_to_tray_mm"].values()), abs=0.005)
    assert "the owner measures the delivered board" in body and "printed to the measured values" in body
    assert "recorded in `owner-sign-off.md` W-19, signed on the owner's behalf; he is asked to confirm it (item 3)" in body and "M3 holes tapped through the plate at the measured tab-hole height" in body
    i4 = params["triac"]["I4_mm"]
    assert "about %.1f mm with a range of %.1f to %.1f mm" % (i4["value"], i4["min"], i4["max"]) in body and "deliberately wider than I4's and covers it" in body
    assert tab_lo <= i4["min"] and tab_hi >= i4["max"]
    assert "item 3" in body and re.search(r"^3\. Confirm the tapped M3 tab holes in the plate", record.split("## Owner list")[1], flags=re.M)


# ---------------------------------------------------------------- C17

def wall_resistance(h, height_m, length_m, t_m=0.0025, k=110.0):
    perimeter = 2 * (height_m + length_m)
    return 1.0 / (h * height_m * length_m + perimeter * math.sqrt(h * k * t_m))


def test_c17_plate_temperatures_are_recomputed_from_the_thermal_figures_and_graded(record, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C17: The case record derives the temperature the case reaches at the plate and the barrier from the thermal records, states the printed material's heat-deflection temperature from its maker's document, and grades the material against it
    body = sec(record, "C17")
    proof = read(os.path.join(BOARD_DIR, "circuit-proof.md"))
    narrower = proof.split("## The narrower plate and the triacs' thermal judgement on it")[1].split("\n## ")[0]
    assert "T_air + 9.09 x (R_wall" in proof and "2.572 K/W at h = 10, and 3.704 K/W at h = 5" in proof, "the former plate's section is unchanged"
    watts = 9.09
    height = params["plate"]["height_mm"]["value"] / 1000.0
    length = params["plate"]["length_mm"]["value"] / 1000.0
    r10, r5 = wall_resistance(10, height, length), wall_resistance(5, height, length)
    assert "%.3f K/W at h = 10 and %.3f K/W at h = 5" % (r10, r5) in narrower
    assert "R_wall = %.3f K/W at h = 10 and %.3f K/W at h = 5" % (r10, r5) in body
    cases = [(25, 10, r10, 1), (40, 10, r10, 3), (40, 5, r5, 3)]
    temps = [air + watts * (r + rc) for air, _, r, rc in cases]
    rows = table_rows(body, "Case")
    assert len(rows) == 3
    for row, t, (air, h, r, rc) in zip(rows, temps, cases):
        assert num(row[5], r"(\d+\.\d) degC") == pytest.approx(t, abs=0.06), row
        assert "%d degC" % air in row[1] and row[2] == str(h) and "%d K/W" % rc in row[3]
        assert row[4] == "%d + %.2f x (%.3f + %d)" % (air, watts, r, rc), row
    assert "9.09 W together" in body and "P = 2 x (H + L) = %.3f m" % (2 * (height + length)) in body and "H = %.3f m" % height in body
    hdt = [102.6, 98.0, 96.0]
    assert "96 to 103 degC" in body
    for maker in ("Polymaker PolyLite ASA", "Ricoh Rapid Fab ASA", "TDS_ASA_Filament.pdf"):
        assert maker in body
    for figure in hdt:
        assert re.search(r"\b%s degC \(" % ("%g" % figure), body), figure
    margin = min(hdt) - temps[1]
    assert num(body, r"margin (\d\.\d) K to the lowest maker figure") == pytest.approx(margin, abs=0.06) and margin > 0
    assert "ASA **holds** at the nominal case (%.1f degC) and at the %.1f degC bound" % (temps[0], temps[1]) in body
    assert "ASA **does not hold** at the %.1f degC bound" % temps[2] in body and "nor on a stainless wall" in body
    assert temps[2] > max(hdt) and min(hdt) > temps[1] > temps[0], "above the makers' band at the still-air bound, under its lowest figure at the hot bound"
    stainless = [wall_resistance(10, height, length, k=15.0), wall_resistance(5, height, length, k=15.0)]
    assert "wall resistance of %.3f and %.3f K/W" % tuple(stainless) in body
    for t in (25 + watts * (stainless[0] + 1), 40 + watts * (stainless[0] + 3), 40 + watts * (stainless[1] + 3)):
        assert "%.1f" % t in body
    assert "pilaster end faces, the screw pilots and the end wall's ledge" in body
    assert "continuous full power on both triacs" in body and "no film on it" in body
    assert "film" not in params
    # the plate is narrower than the one the earlier figures were drawn for, so every temperature is higher
    older = [25 + watts * (wall_resistance(10, 0.030, length) + 1), 40 + watts * (wall_resistance(10, 0.030, length) + 3), 40 + watts * (wall_resistance(5, 0.030, length) + 3)]
    assert all(new > old for new, old in zip(temps, older)) and [round(t, 1) for t in older] == [57.5, 90.6, 100.9]


def test_c17_owner_acceptance_does_not_claim_a_bring_up_measurement_and_the_flame_rating_item_is_recorded(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C17: The case record derives the temperature the case reaches at the plate and the barrier from the thermal records, states the printed material's heat-deflection temperature from its maker's document, and grades the material as holding or not holding; where it does not hold the record names the owner acceptance needed. It states the material's flame rating against the mains pads' 10 A and records that no rating is asked of the case, as an item for the owner.
    body = sec(record, "C17")
    acceptance = body.split("**Owner acceptance needed.**")[1].split("**Flame.**")[0]
    assert "continuous duty the machine does not run" in acceptance and "or name another material" in acceptance
    assert "The acceptance rests on analysis alone: no bring-up criterion asks for the plate's temperature to be measured" in acceptance
    assert "DEL-HW-BRING-UP.C11" not in body
    assert "bring-up plate-temperature measurement" not in body, "no criterion is said to hold a plate temperature measurement"
    assert "85 degC" in acceptance and "11 K under the lowest maker figure" in acceptance and "the material is changed" in acceptance
    assert "**does not hold**" in body and "**the acceptance is open**" in body.split(CHECK_TABLE)[1]
    flame = body.split("**Flame.**")[1].split(CHECK_TABLE)[0]
    assert "UL 94 HB" in flame and "10 A" in flame and "No flame rating is asked of the case by any requirement" in flame
    assert "owner item" in flame and "flame-retardant filament" in flame and "No film is used, so none is specified" in flame
    owner = record.split("## Owner list")[1]
    assert re.search(r"^6\. Flame rating: ASA is HB", owner, flags=re.M) and re.search(r"^5\. Plate temperature", owner, flags=re.M)
    assert "No bring-up criterion measures the plate" in owner.split("\n6. ")[0]
    assert "owner list item 5" in body and "owner list item 6" in body


# ---------------------------------------------------------------- C18

def test_c18_boot_envelopes_clearances_bend_room_and_lid_removal_match_the_model(record, params, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C18: The case leaves room around each of the three 6.3 mm blades for a receptacle with its insulating boot fitted, with the boot's outer size and the figure's source stated in the case record, so that a receptacle is pushed on and pulled off along the stated direction, with the lid on and with it off, without the receptacle or its boot touching the case, the lid or the film, and the wire leaving the boot has a stated bend room. The model shows the boot's swept envelope clear of the case at its stated size and at the largest size of a common insulated receptacle the record names, and no case dimension that another criterion of this leaf fixes is reduced to make it.
    body = sec(record, "C18")
    boots = params["boots"]
    t, lg = boots["typical"]["value"], boots["largest_common"]["value"]
    assert "typical %.1f x %.1f x %.1f mm" % tuple(t) in body and "largest common %.1f x %.1f x %.1f mm" % tuple(lg) in body
    for source in ("Vogt 3906", "JST LVDDF2-250A", "Vogt 3933", "JST LVDDF5.5-250A", "catalogue p.376", "catalogue p.375"):
        assert source in body
    assert "assumed" in body.lower() and "No maker figure was found for a separate rubber boot" in body and "unconfirmed" in body
    c18 = named(results, "c18.boot_clearance")
    assert c18["passed"]
    fig = c18["figures"]
    on = min(b["lid_on_least_clearance_mm"] for b in fig["boots"])
    off = min(b["lid_off_least_clearance_mm"] for b in fig["boots"])
    assert num(body, r"keeps \*\*(\d\.\d+) mm\*\* to the lid") == pytest.approx(on, abs=0.005)
    assert num(body, r"and \*\*(\d\.\d+) mm\*\* with it off") == pytest.approx(off, abs=0.005)
    assert fig["required_clearance_mm"] == boots["clearance_mm"]["value"] == num(body, r"\(needs (\d\.\d)\)")
    for b in fig["boots"]:
        assert b["lid_on_least_clearance_mm"] == pytest.approx(on, abs=0.005) and b["lid_on_nearest"] == "lid"
    typical_off = {b["blade"]: b["lid_off_least_clearance_mm"] for b in fig["boots"] if b["envelope"] == "typical"}
    largest_off = {b["blade"]: b["lid_off_least_clearance_mm"] for b in fig["boots"] if b["envelope"] == "largest_common"}
    assert "lid off %.2f mm (J941), %.2f mm (J921) and %.2f mm (J911) at typical" % tuple(typical_off[k] for k in ("J941", "J921", "J911")) in body
    assert "and %.2f, %.2f and %.2f mm at largest common" % tuple(largest_off[k] for k in ("J941", "J921", "J911")) in body
    gaps = fig["boot_to_boot_gap_mm"]["typical"]
    assert num(body, r"(\d\.\d+) mm between J941 and J921") == pytest.approx(gaps["J941-J921"])
    assert num(body, r"(\d\.\d+) mm between J921 and J911") == pytest.approx(gaps["J921-J911"])
    assert fig["boot_to_boot_gap_mm"]["largest_common"] == gaps and "at both envelopes" in body
    wire = fig["wire"]
    assert wire["od_mm"] == boots["wire_od_mm"]["value"] and wire["bend_room_mm"] == pytest.approx(boots["bend_od_multiple"]["value"] * boots["wire_od_mm"]["value"])
    assert "%.0f x %.1f mm = %.1f mm" % (boots["bend_od_multiple"]["value"], wire["od_mm"], wire["bend_room_mm"]) in body
    depth = fig["depth_below_lid_face_for_boot_and_bend_mm"]
    assert num(body, r"\*\*(\d+\.\d+) mm\*\* \(typical\)") == depth["typical"] and num(body, r"or \*\*(\d+\.\d+) mm\*\* \(largest\)") == depth["largest_common"]
    assert "pushed on along `-z` from below" in body
    removal = fig["lid_removal_with_receptacles_fitted"]
    assert removal["typical"]["boots_only"]["removable"] is True and removal["typical"]["boots_and_straight_wire"]["removable"] is False
    assert num(body, r"blocks it at a (\d\.\d+) mm slide; with the largest") == pytest.approx(removal["typical"]["boots_and_straight_wire"]["first_contact"]["slide_mm"])
    assert num(body, r"boots alone block it at a (\d\.\d) mm slide") == pytest.approx(removal["largest_common"]["boots_only"]["first_contact"]["slide_mm"])
    assert "The lid does not come off with receptacles fitted" in body and "Pull the receptacles first" in body


def test_c18_no_dimension_another_criterion_fixes_was_reduced(record, results, basis):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C18: The case leaves room around each of the three 6.3 mm blades for a receptacle with its insulating boot fitted, with the boot's outer size and the figure's source stated in the case record, so that a receptacle is pushed on and pulled off along the stated direction, with the lid on and with it off, without the receptacle or its boot touching the case, the lid or the film, and the wire leaving the boot has a stated bend room. The model shows the boot's swept envelope clear of the case at its stated size and at the largest size of a common insulated receptacle the record names, and no case dimension that another criterion of this leaf fixes is reduced to make it.
    body = sec(record, "C18").split("**No dimension another criterion fixes was reduced.**")[1]
    assert num(body, r"nearest Mains copper to the plate \((\d\.\d+) mm against") == pytest.approx(named(results, "c1.creepage_pad_to_plate")["figures"]["creepage_mm"], abs=0.0005)
    assert num(body, r"the bare lead's \((\d\.\d+) mm against") == pytest.approx(named(results, "c1.creepage_bare_lead_to_plate")["figures"]["creepage_mm"], abs=0.0005)
    slot = min(s["least_mm"] for s in named(results, "c8.slot_mouths_clear")["figures"]["slots"])
    assert num(body, r"slot-mouth clearance \((\d\.\d) mm against") == pytest.approx(slot)
    assert num(body, r"case-to-plate margin \((\d\.\d+) mm against") == pytest.approx(min(named(results, "c2.case_within_former_outline")["figures"]["margins_mm"].values()), abs=0.001)
    assert "79.50 against 80.0" in body
    bay = named(results, "c11.blade_terminals_reachable_lid_on")["figures"]["blades"][0]["aperture_mm"]
    assert "to %.1f x %.2f mm" % tuple(bay) in body
    for name in ("c1.creepage_pad_to_plate", "c1.creepage_bare_lead_to_plate", "c8.slot_mouths_clear", "c2.case_within_former_outline", "c3.plate_length", "c18.boot_clearance"):
        assert named(results, name)["passed"]
    assert basis["creepage_mains_mm"] == 2.6 and basis["clearance_mains_mm"] == 1.5
    assert "at the model's nominal and at all 64 seating extremes" in body


# ---------------------------------------------------------------- C19

def test_c19_installed_orientation_is_the_owners_and_each_judgement_is_stated_for_it(record, params, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C19: The case record states the installed orientation as the owner gave it: the plate is vertical on the machine's wall, the board projects from it horizontally with its component side facing down, the tray holds the board's bare back above the parts, and the lid closes the underside and comes off downward. The case is judged in that orientation: the lid removal sweep, the reach of every fixing and of each receptacle, the test finger and drip paths of every opening (falling onto the bare back, not onto parts), and the heat release through the vents given that warm air rises past the board, are each stated for it. Each printed part's print orientation is stated separately from its installed orientation.
    body = sec(record, "C19")
    for clause in ("The plate is vertical on the machine's wall", "The board projects from it horizontally with its component side facing down",
                   "The tray holds the board's bare back, above the parts", "The lid closes the underside and comes off downward"):
        assert clause in body
    inst = params["installed"]
    assert inst["plate_vertical"]["value"] is True and inst["tray_up"]["value"] is True and inst["gravity"]["value"] == [0.0, 0.0, 1.0]
    assert "gravity is `(0, 0, 1)`" in body
    sweep = named(results, "c4.lid_sweep")["figures"]
    frame = sweep["installed_frame"]
    assert num(body, r"far end down (\d) degrees") == sweep["tilt_deg"] == frame["tilt_deg"] == params["lid"]["sweep_tilt_deg"]["value"]
    assert num(body, r"far end drops (\d\.\d+) mm") == pytest.approx(frame["drop_at_far_end_during_tilt_mm"], abs=0.005)
    assert num(body, r"away from the wall (\d\.\d) mm to free the toes") == pytest.approx(frame["slide_to_free_the_toes_mm"])
    assert num(body, r"lowest point drops (\d\.\d+) mm when the toes are free") == pytest.approx(frame["lowest_point_drop_when_toes_free_mm"], abs=0.005)
    assert num(body, r"so (\d\.\d+) mm of clear space is needed below") == pytest.approx(frame["clear_space_needed_below_the_case_mm"], abs=0.005)
    assert num(body, r"least clearance of (\d\.\d+) mm") == pytest.approx(sweep["minimum_clearance_mm"], abs=0.0005)
    assert num(body, r"(\d\.\d+) mm in the fitted pose") == pytest.approx(sweep["fitted_minimum_mm"], abs=0.0005)
    assert num(body, r"through (\d+) poses") == pytest.approx(sweep["poses"])
    assert num(body, r"to a (\d+) mm slide") == pytest.approx(frame["slide_checked_to_mm"])
    assert "Reach of every fixing and each receptacle" in body and "Test finger and drip paths of every opening" in body
    fix = named(results, "c5.fixings_reached_installed")["figures"]["fixings"]
    assert {f["fixing"] for f in fix} == {"lid screw", "board screw H1", "tab screw T921", "tab screw T911", "tray-to-plate screws (4)"}
    reach = {r[0]: r for r in table_rows(body, "Fixing")}
    assert len(reach) == 5 and any(k.startswith("lid screw") for k in reach) and any(k.startswith("four tray screws") for k in reach)
    lid_row = next(v for k, v in reach.items() if k.startswith("lid screw"))
    screw = named(results, "c5.lid_screw_reached")["figures"]
    assert num(lid_row[1], r"(\d+\.\d) mm from the wall plane") == pytest.approx(screw["distance_to_wall_plane_mm"])
    assert num(lid_row[1], r"(\d+\.\d) mm from the opening frame") == pytest.approx(screw["distance_to_opening_frame_mm"], abs=0.05)
    h1 = next(f for f in fix if f["fixing"] == "board screw H1")
    h1_row = next(v for k, v in reach.items() if k.startswith("board screw H1"))
    assert "nearest tray %.2f mm" % h1["nearest_gap_mm"] in h1_row[1] and h1_row[2] == "yes" and lid_row[2] == "no"
    drivers = named(results, "c11.tab_screw_driver_reached")["figures"]["drivers"]
    tab_row = next(v for k, v in reach.items() if k.startswith("tab screws"))
    assert "%.1f degrees below level" % drivers["T921"]["tilt_deg"] in tab_row[1] and "nearest tray %.2f mm" % drivers["T921"]["nearest_gap_mm"] in tab_row[1]
    drip = named(results, "c15.drip")["figures"]
    assert num(body, r"within (\d+) degrees of vertical from outside enters any of the (\d+) openings") == pytest.approx(drip["cone_half_angle_deg"])
    assert int(num(body, r"within \d+ degrees of vertical from outside enters any of the (\d+) openings")) == len(drip["per_opening"])
    assert "not to be mounted lid up" in body and set(drip["information_only_pairs_reaching_copper"]) == {"blade bay J941 down -z", "blade bay J921 down -z", "blade bay J911 down -z"}


def test_c19_heat_release_is_stated_as_placed_for_convection_and_not_sized_and_print_orientation_is_separate(record, results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C19: The case record states the installed orientation as the owner gave it: the plate is vertical on the machine's wall, the board projects from it horizontally with its component side facing down, the tray holds the board's bare back above the parts, and the lid closes the underside and comes off downward. The case is judged in that orientation: the lid removal sweep, the reach of every fixing and of each receptacle, the test finger and drip paths of every opening (falling onto the bare back, not onto parts), and the heat release through the vents given that warm air rises past the board, are each stated for it. Each printed part's print orientation is stated separately from its installed orientation.
    body = sec(record, "C19")
    areas = named(results, "c15.openings_enumerated")["figures"]["open_areas"]
    assert "The lid's %d slots are the air inlets" % areas["lid_inlet_slot_count"] in body
    assert num(body, r"with (\d+\.\d) mm2 of free area; the") == pytest.approx(areas["lid_inlet_free_area_mm2"], abs=0.05)
    assert "the %d equal slits" % areas["side_outlet_slit_count"] in body
    assert num(body, r"outlets, with (\d+\.\d) mm2") == pytest.approx(areas["side_outlet_free_area_mm2"], abs=0.05)
    assert num(body, r"outlet to inlet (\d\.\d+)\)") == pytest.approx(areas["outlet_to_inlet_ratio"], abs=0.0005)
    outlets = params["skins"]["flow"]["outlets"]
    width, height, pitch = outlets["width_mm"]["value"], outlets["height_mm"]["value"], outlets["pitch_mm"]["value"]
    assert "slits %.1f mm wide and %.1f mm high on a %.1f mm pitch" % (width, height, pitch) in body
    right, left = (round(areas["side_outlet_area_by_wall_mm2"][w] / (width * height)) for w in ("right", "left"))
    assert "%d in the right wall and %d in the left" % (right, left) in body and right + left == areas["side_outlet_slit_count"]
    assert num(body, r"is (\d+) mm2 now") == pytest.approx(areas["lid_inlet_free_area_mm2"], abs=0.5)
    assert num(body, r"The inlet area was (\d+) mm2 before") == 230 and "owner list item 13" in body
    assert "placed for convection, in low and out high" in body and "were not sized by a thermal calculation" in body
    assert "9.09 W is taken by the plate and the machine's wall" in body and "not by the case air" in body
    assert "Warm air rises past the board" in body and "70 degC in `circuit-proof.md`" in body
    rows = {r[0]: r for r in table_rows(body, "Part")}
    parts = {p["part"]: p for p in named(results, "c14.bed_fit")["figures"]["parts"]}
    for label, part in (("tray", "tray"), ("lid, single-colour form", "lid_single"), ("lid, two-colour form", "lid_two")):
        assert rows[label][1] == parts[part]["orientation"] and rows[label][2] == parts[part]["installed_orientation"]
    assert "Print orientation, stated separately" in body and "none of these is the installed orientation" in body
    assert "The plate is cut from bar and does not print; no film is made" in body


# ---------------------------------------------------------------- C20

def test_c20_the_cable_exit_notch_gate_and_slide_are_the_models(record, results, params, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C20: The case lets the low-voltage cable that mates with the board's header leave the closed case, and the lid is fitted and removed with that cable in place. The case drawing or model shows the cable's exit through the case with the lid on, the cable's own swept path as the lid slides along its removal path, and the clearance between the cable and every case edge along that path, and no part of the lid or tray traps or bends the cable beyond the bend room the record states. The record states the largest outside diameter of wire the bend room supports, at three times the wire's diameter, computed from the lid's clearance above the header's wire exit and recomputed by the case model, and lists the owner's confirmation that his cable fits as an owner item. No case dimension that another criterion of this leaf fixes is reduced to make room for it.
    body = sec(record, "C20")
    pads = model.board.refs["J931"]["pads"]
    us = sorted(p["u"] for p in pads)
    assert len(us) == 3 and "pins at u %.2f, %.2f and %.2f, v %.1f" % (us[0], us[1], us[2], pads[0]["v"]) in body
    assert all(p["v"] == pytest.approx(pads[0]["v"]) for p in pads)
    lid = params["lid"]
    n0, n1 = lid["cable_notch_v_mm"]["value"]
    height, top = lid["cable_notch_height_mm"]["value"], params["case"]["z_wall_top_mm"]["value"]
    housing = params["parts"]["header_housing_top_z_mm"]["value"]
    assert (n0 + n1) / 2 == pytest.approx(pads[0]["v"], abs=0.005)
    assert "%.1f mm wide (v %.1f to %.1f, centred on the header)" % (n1 - n0, n0, n1) in body
    assert "%.1f mm high (z %.1f to the wall's top at %.1f)" % (height, top - height, top) in body
    assert "%.1f mm above the top of a mated housing" % (top - height - housing) in body
    gate = named(results, "c4.cable_gate_follows_the_slide")
    g = gate["figures"]
    assert gate["passed"] and g["notch_v_mm"] == [n0, n1] and g["gate_spans_notch_at_every_pose"] is True and g["outward_rays_blocked"] == []
    assert "from v %.1f to %.1f, %.1f mm long" % (g["gate_v_mm"][0], g["gate_v_mm"][1], g["gate_v_mm"][1] - g["gate_v_mm"][0]) in body
    assert "a line from each of %s points" % {5: "five"}[g["sample_points"]] in body
    assert num(body, r"The exit is at u (\d+\.\d)") == pytest.approx(named(results, "c2.wall_opening_stated")["figures"]["cable_exit_u_mm"])
    slide = g["slide_to_free_the_toes_mm"]
    tilt = named(results, "c4.lid_sweep")["figures"]["tilt_deg"]
    seam = params["case"]["seam_mm"]["value"]
    assert g["lead_toward_the_plate_mm"] == pytest.approx(params["skins"]["flow"]["cable_gate_lead_mm"]["value"] + seam)
    assert "drawn %.1f mm away from the wall" % slide in body and "leads the notch toward the plate by %.1f mm" % g["lead_toward_the_plate_mm"] in body
    assert "an %.1f mm lead and the %.1f mm seam" % (g["lead_toward_the_plate_mm"] - seam, seam) in body
    assert "%d degrees and drawn" % tilt in body and "0.1 mm poses" in body
    rows = table_rows(body, "Edge")
    assert len(rows) == 4
    far = g["gate_v_mm"][1] - n1
    assert num(rows[0][1], r"(\d\.\d+) mm") == pytest.approx(far, abs=0.005) == pytest.approx(g["least_margin_mm"], abs=0.005)
    assert "(%.1f against %.1f)" % (g["gate_v_mm"][1], n1) in rows[0][2]
    plate_end = g["lead_toward_the_plate_mm"] - slide * math.cos(math.radians(tilt))
    assert num(rows[1][1], r"(\d\.\d+) mm") == pytest.approx(plate_end, abs=0.005)
    assert "(%.1f less %.1f x cos %d degrees)" % (g["lead_toward_the_plate_mm"], slide, tilt) in rows[1][2]
    assert "none stands there" in rows[2][1]
    under = params["case"]["z_lid_under_mm"]["value"]
    axis = named(results, "c4.lid_sweep")["figures"]["tilt_axis"]["v_mm"]
    pin_v = pads[0]["v"]
    assert num(rows[3][1], r"(\d\.\d+) mm above the wall's top when fitted") == pytest.approx(under - top, abs=0.005)
    assert num(rows[3][1], r"(\d\.\d+) mm further once tilted") == pytest.approx((pin_v - axis) * math.sin(math.radians(tilt)), abs=0.005)
    assert "%.2f mm from the tilt line x sin %d degrees" % (pin_v - axis, tilt) in rows[3][2]
    assert "model's tilt line (v %.2f)" % axis in body
    assert "`least_margin_mm` %.2f" % g["least_margin_mm"] in body
    assert "the model does not carry the cable as a solid" in body and "pinched in the %.2f mm seam" % (under - top) in body
    assert "Three wires of 1.3 mm lie %.1f mm wide in the %.1f mm notch" % (3 * 1.3, n1 - n0) in body


@pytest.mark.controls("c20_worst_lean", "c20_best_lean")
def test_c20_the_bend_room_table_and_the_finding_are_arithmetic_on_the_models_figures(record, results, params, model, controls, rng):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C20: The case lets the low-voltage cable that mates with the board's header leave the closed case, and the lid is fitted and removed with that cable in place. The case drawing or model shows the cable's exit through the case with the lid on, the cable's own swept path as the lid slides along its removal path, and the clearance between the cable and every case edge along that path, and no part of the lid or tray traps or bends the cable beyond the bend room the record states. The record states the largest outside diameter of wire the bend room supports, at three times the wire's diameter, computed from the lid's clearance above the header's wire exit and recomputed by the case model, and lists the owner's confirmation that his cable fits as an owner item. No case dimension that another criterion of this leaf fixes is reduced to make room for it.
    body = sec(record, "C20")
    pads = model.board.refs["J931"]["pads"]
    under = params["case"]["z_lid_under_mm"]["value"]
    pad_h = named(results, "c15.openings_enumerated")["figures"]["gill"]["pad_h"]
    housing = params["parts"]["header_housing_top_z_mm"]["value"]
    room = under - pad_h - housing
    assert "%.2f mm from the housing's top (z %.1f" % (room, housing) in body and "(z %.2f)" % (under - pad_h) in body
    assert room == pytest.approx(3.65)
    wall_u = named(results, "c8.slot_mouths_clear")["figures"]["slots"][0]["mouth_u_mm"] + params["case"]["interior_right_mm"]["value"]
    pin_u = sorted(p["u"] for p in pads)
    assert "%.1f to %.1f mm from a pin to the wall's inner face (u %.1f)" % (wall_u - pin_u[-1], wall_u - pin_u[0], wall_u) in body
    assert "**3 times the wire's outside diameter**" in body and "no maker figure" in body
    rows = table_rows(body, "Wire outside diameter")
    assert [r[0] for r in rows] == ["1.0 mm", "1.2 mm", "1.3 mm", "1.5 mm"]
    fits = []
    for diameter, need, left, verdict in rows:
        d = float(diameter.split()[0])
        assert need == "%.1f mm" % (3 * d) and left == "%.2f mm" % room, diameter
        short = 3 * d - room
        assert verdict == ("within" if short <= 0.0001 else "%.2f mm short" % short), diameter
        if short <= 0.0001:
            fits.append(d)
    bend = named(results, "c20.cable_bend_room")["figures"]
    assert bend["bend_room_mm"] == pytest.approx(room, abs=1e-6) and bend["largest_wire_od_stated_mm"] == max(fits) == 1.2
    assert "**%.1f mm**" % bend["largest_wire_od_stated_mm"] in body and "`c20.cable_bend_room`" in body and "%.2f mm from the housing's top" % bend["bend_room_mm"] in body
    assert "3.65 / 3 = %.3f mm" % bend["largest_wire_od_mm"] in body
    worst, best = controls.get("c20_worst_lean")["figures"], controls.get("c20_best_lean")["figures"]
    assert "the room is %.2f mm, which supports %.2f / 3 = %.3f mm, **%.1f mm** of wire" % (worst["bend_room_mm"], worst["bend_room_mm"], worst["largest_wire_od_mm"], worst["largest_wire_od_stated_mm"]) in body
    assert "at -1.0 degree it is %.2f mm (%.1f mm of wire)" % (best["bend_room_mm"], best["largest_wire_od_stated_mm"]) in body and worst["largest_wire_od_stated_mm"] == 1.0
    assert "1.0 mm outside diameter at most over the seating range" in body.split("## Owner list")[0] + record.split("## Owner list")[1]
    assert "`test_c20_bend_room_over_the_seating_range_is_least_at_the_far_end_up_lean`" in body and "it is not a line of `case/out/check-range.json`" in body
    ranged = [c for c in rng["checks"] if c["name"] == "c20.cable_bend_room"]
    assert len(ranged) == 1 and ranged[0]["figures"]["bend_room_mm"] == pytest.approx(3.65, abs=1e-6), "check-range.json holds the nominal figure only" and "wire of %.1f mm outside diameter or less" % max(fits) in body
    assert "a housing taller than %.1f mm" % housing in body and "recomputed from the lid's clearance of %.2f mm" % room in body.split(CHECK_TABLE)[1]
    heads = re.findall(r"^### (.*)$", body, flags=re.M)
    assert len(heads) == 1 and heads[0].startswith("Finding:")
    finding = body.split("### Finding:")[1].split("\n**No dimension another criterion fixes was reduced.**")[0]
    assert "This is a finding, stated as one." in finding and not re.search(r"\bpass(es|ed)?\b", finding, flags=re.I), "never called a pass"
    assert "figures the case model recomputes" in finding and "Neither the wire nor the housing is specified by any record" in finding
    assert "owner list item 15" in finding and "No record specifies that cable's wire" in body
    assert "No case dimension was changed for this" in finding
    item = re.search(r"^15\. Cable: confirm that your three-way cable fits\..*$", record.split("## Owner list")[1], flags=re.M).group(0)
    assert "1.0 mm outside diameter at most over the seating range, 1.2 mm at the nominal seating" in item and "recomputed by the case model" in item and "no record specifies the wire" in item
    assert "**whether the owner's cable fits is his to confirm, owner item 15**" in body.split(CHECK_TABLE)[1] and "1.2 mm outside diameter at the nominal seating and 1.0 mm over the seating range (`c20.cable_bend_room`" in body.split(CHECK_TABLE)[1]
    last = body.split("**No dimension another criterion fixes was reduced.**")[1].split(CHECK_TABLE)[0]
    assert num(last, r"The lid sweep \((\d\.\d+) mm\)") == pytest.approx(named(results, "c4.lid_sweep")["figures"]["minimum_clearance_mm"], abs=0.0005)
    assert num(last, r"slot-mouth clearance \((\d\.\d+) mm against") == pytest.approx(min(s["least_mm"] for s in named(results, "c8.slot_mouths_clear")["figures"]["slots"]), abs=0.0005)
    n = len(named(results, "c15.drip")["figures"]["per_opening"])
    assert "the notch admits nothing; %d of %d" % (n, n) in last


# ---------------------------------------------------------------- C21

@pytest.fixture(scope="module")
def fit_module():
    sys.path.insert(0, CASE_DIR)
    import fit
    return fit


@pytest.fixture(scope="module")
def fit_results(fit_module):
    """Every result of `fit.py` on the exported files, by name."""
    try:
        results = fit_module.all_results(os.path.join(CASE_DIR, "out"))
    except SystemExit as error:
        pytest.fail(str(error))
    return {r.name: r for r in results}


def fit_rows(record):
    """The C21 section's fit table as {result name: (measured cell, tolerance cell)}."""
    rows = table_rows(sec(record, "C21"), "Result")
    out = {}
    for cells in rows:
        m = re.fullmatch(r"`([a-z0-9_]+)`", cells[0])
        assert m, cells
        out[m.group(1)] = (cells[1], cells[2])
    return out


def test_c21_the_fit_table_is_every_result_of_the_check_with_its_figures(record, fit_results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    body = sec(record, "C21")
    rows = fit_rows(record)
    assert set(rows) == set(fit_results), "the record's fit table names exactly the results of fit.py"
    assert all(r.ok for r in fit_results.values()), [n for n, r in fit_results.items() if not r.ok]
    assert "%d of %d results pass" % (len(fit_results), len(fit_results)) in body
    for name, r in fit_results.items():
        measured, tolerance = rows[name]
        if isinstance(r.measured, str):
            worst = max(float(x) for x in re.findall(r"([\d.]+) %", r.measured))
            assert measured.startswith("at most %.3f %%" % worst), (name, measured)
        elif isinstance(r.measured, (list, tuple)):
            assert measured.startswith(", ".join("%.3f" % v for v in r.measured)), (name, measured)
        elif isinstance(r.measured, float):
            assert measured.startswith("%.3f" % r.measured), (name, measured)
        else:
            assert measured.startswith("%d" % r.measured), (name, measured)
        if name.startswith("logo_reads"):
            assert "85 per cent" in tolerance and "0.4 above every other reading" in tolerance, name
        elif isinstance(r.tolerance, (int, float)) and r.tolerance:
            assert num(tolerance, r"([\d.]+)") == pytest.approx(r.tolerance), (name, tolerance)


def test_c21_the_logo_figures_and_thresholds_are_the_checks(record, fit_results, fit_module):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    body = sec(record, "C21")
    assert fit_module.LOGO_IOU_MIN == 0.85 and fit_module.LOGO_IOU_MARGIN == 0.4 and "reach 85 per cent and beat each other by 0.4" in body
    for part, others in (("lid_single", "The lid's grooves read"), ("tray_top", "the tray top's read")):
        r = fit_results["logo_reads_right_way_round_" + part]
        assert r.ok and r.measured >= fit_module.LOGO_IOU_MIN
        note = r.note
        rivals = [float(x) for x in re.findall(r"(?:mirrored_x|mirrored_y|half_turn) ([\d.]+)", note)]
        assert len(rivals) == 3 and max(rivals) <= r.measured - fit_module.LOGO_IOU_MARGIN
        assert "%s %.3f against" % (others, r.measured) in body
        assert "%.3f, %.3f and %.3f" % tuple(rivals) in body
    assert fit_results["logo_reads_right_way_round_lid_single"].measured == pytest.approx(fit_results["logo_reads_right_way_round_lid_two"].measured, abs=0.0005)
    lid_note = fit_results["logo_reads_right_way_round_lid_single"].note
    tray_note = fit_results["logo_reads_right_way_round_tray_top"].note
    assert "with the wall at the bottom of the view (view right -X, view up -Y)" in lid_note and "with the wall at the top of the view (view right -X, view up +Y)" in tray_note
    assert "seen from below with the wall at the bottom of the view: the artwork's right runs along `-X` and its up along `-Y`" in body
    assert "seen from above with the wall at the top of the view: right along `-X`, up along `+Y`" in body
    assert "stands in front of the wall the plate is on, facing it" in body and "the viewer's forward is `+Y`, up is `-Z` and right is `-X`" in body


def test_c21_the_controls_fail_what_the_record_says_they_fail(record, fit_module):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    body = sec(record, "C21")
    run = fit_module.controls(os.path.join(CASE_DIR, "out"))
    rows = {cells[0]: cells for cells in table_rows(body, "Control")}
    expected = {"mirror_x": "exports mirrored in X", "mirror_y": "exports mirrored in Y", "mirrored_artwork": "the logo's artwork mirrored"}
    assert set(run) == set(expected)
    for key, label in expected.items():
        failed = [r.name for r in run[key] if not r.ok]
        cells = rows[label]
        assert int(cells[1]) == len(failed) > 0, key
        assert re.findall(r"`([a-z0-9_]+)`", cells[2]) == failed, key
    assert "the mirror in X fails %d results, the mirror in Y %d and the mirrored artwork %d" % tuple(len([r for r in run[k] if not r.ok]) for k in expected) in body


def test_c21_the_section_states_the_frames_placement_and_the_views_that_turned(record, fit_module):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    body = sec(record, "C21")
    assert "`X = u`, `Y = -v`, `Z = z`" in body and "`case.PHYSICAL`, `case.physical`, `case.physical_mesh`" in body
    assert "`(u, v, z)` is a left-handed frame" in body and "translation alone" in body
    assert "a board model whose component face looked toward `-Z` is refused" in body
    assert "(lean 0)" in body and "the handedness of the exports does not depend on the lean" in body
    assert "`task hw:case:board-model`" in body and "`task hw:case:fit`" in body
    assert hasattr(fit_module, "load_board_model") and "refused" in fit_module.__doc__
    for phrase in ("the `lid` view and the lid logo close-ups (`logo-lid-30` and `logo-lid-60`) now have the wall at the bottom of the picture",
                   "the `top` view and the tray logo close-ups have the wall at the top",
                   "The case drawings' plan is drawn from the lid side with the plate at the top"):
        assert phrase in body, phrase
    for phrase in ("the lid slides along `v`", "the cable gate and notch are at the header's side of the board", "the hold-down finger", "the drip and gravity rules",
                   "*left wall* (low `u`) and *right wall* (high `u`) are as seen from the lid side with the plate at the top"):
        assert phrase in body, phrase
    assert "The fit is made at the nominal seating, lean 0" in body
    owner = sections(record)[-1][1]
    item9 = re.search(r"^9\. (.*)$", owner, flags=re.M).group(1)
    assert "set upright for a viewer in front of the wall looking up at the lid" in item9 and "`Engraving.placed` of `logo.py`" in item9
    clause = body.split(CHECK_TABLE)[1]
    assert "the tests check that their names are among the export's written files but read no STEP geometry" in clause
    assert "no test reads one" in body and "the side and end elevations of `case-drawings.svg` are not compared with the meshes by any test" in clause


def test_c21_every_fit_result_the_record_cites_is_real_and_every_one_is_cited(record, fit_results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    body = sec(record, "C21")
    cited = set(re.findall(r"`([a-z0-9_]+)`", body))
    assert set(fit_results) <= cited, "every result of fit.py is cited: %s" % sorted(set(fit_results) - cited)
    unknown = {n for n in cited if n not in fit_results and re.fullmatch(r"(pilot|bays|no_bay|plate|film|tapped|slot|tray|board|logo|exports|print|swap|3mf)_[a-z0-9_]*", n)}
    assert not unknown, "the section names fit results that fit.py does not carry: %s" % sorted(unknown)


# ---------------------------------------------------------------- the owner list

def test_the_owner_list_is_the_last_section_and_has_every_item(record):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C10: The case record states how the spreader plate is bonded to protective earth: the mechanism assumed, the plate screwed to the machine's steel wall, earthed through the mains-inlet earth, which the owner confirms, and the four-wire measurement the bring-up task holds it to. It also records the owner's decision, with his words and the date, whether the plate carries its own dedicated earth strap or relies on the wall alone, and the case drawing shows the strap if there is one. Taking the measurement is out of scope.
    heads = [h for h, _ in sections(record)]
    assert heads[-1] == "Owner list"
    items = re.findall(r"^(\d+)\. (.*)$", sections(record)[-1][1], flags=re.M)
    assert [int(n) for n, _ in items] == list(range(1, 20))
    keys = {
        1: "Earth strap", 2: "Measure the delivered triacs' seating", 3: "tapped M3 tab holes", 4: "Plate size", 5: "Plate temperature",
        6: "Flame rating", 7: "Measure the boots", 8: "traced logo vector", 9: "which face", 10: "Colour: two-colour",
        11: "Two-colour: accept the pinstripe", 12: "Outline: the far-corner radius", 13: "Inlet area", 14: "Cable gate",
        15: "Cable: confirm that your", 16: "assumed shapes and colours", 17: "never energise with a receptacle off a blade",
        18: "depth the case and plate add", 19: "physical demonstrations",
    }
    assert len(keys) == 19
    for n, text in items:
        assert keys[int(n)].lower() in text.lower(), (n, text)
        assert len(text.split(". ")) <= 3, "each item is one or two plain sentences: %r" % text
    assert "13.6" not in record
    occurrences = [record[max(0, m.start() - 70):m.end() + 40] for m in re.finditer(r"0\.85", record)]
    assert len(occurrences) == 3, "0.85 stands only where its source says so: the hook gap, the bend shortfall and the vent web: %r" % occurrences
    assert sum("over the board's edge" in o for o in occurrences) == 1 and sum("mm short" in o for o in occurrences) == 1 and sum("web between slots" in o for o in occurrences) == 1
