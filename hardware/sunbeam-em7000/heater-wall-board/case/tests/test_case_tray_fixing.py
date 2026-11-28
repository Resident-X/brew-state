"""Tests of the tray-fixing leaf of the printed case: one heat-set insert in each pilaster, the short screw through the bar into it, the heads and
countersinks kept apart, the insert's wall and its distance from mains copper, the bar, the wall bolts and the opening that follow the pilaster width,
the tray root held on the stated insert allowance, and the records that state the fixing once (the case record, the drawings, the division record
and the owner's sign-off record).

Run with the interpreter `task hw:cad` creates, from the case folder:  python -m pytest tests/test_case_tray_fixing.py
The model, the nominal check and the negative controls come from the session fixtures of `conftest.py` and `negatives.py`. A record is read as
committed and each rule is a function of its text, so a failing case is the same text with one phrase changed.
"""

import html
import math
import os
import re
import sys

import pytest

CASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CASE_DIR)
import case  # noqa: E402,I001  (build123d before vtk)
import check  # noqa: E402

BOARD_DIR = os.path.dirname(CASE_DIR)
DIVISION = os.path.join(BOARD_DIR, "..", "..", "..", "docs", "sunbeam-em7000", "controller-board-division.md")
SOLUTION = "SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL"


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def named(results, name):
    return next(r for r in results if r["name"] == name)


def by_name(results):
    return {r["name"]: r for r in results}


def flat(text):
    return " ".join(text.split())


def drawing_text(name):
    svg = read(os.path.join(CASE_DIR, "out", name))
    return " ".join(html.unescape(" ".join(re.findall(r">([^<>]+)</text>", svg))).split())


@pytest.fixture(scope="module")
def record():
    return flat(read(os.path.join(BOARD_DIR, "case-record.md")))


@pytest.fixture(scope="module")
def params():
    return case.Params.load()


# ---------------------------------------------------------------- C1: heads and countersinks apart

def test_c1_every_pair_of_tray_screws_keeps_its_heads_and_countersinks_apart(results, params, record):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C1: The case model's checks require every pair of tray-screw heads, and of the countersinks they sit in at the bar's back face, to stand at least the record's head-to-head distance apart, with the head and countersink diameters taken from the screw's standard and stated in the record, and the case's seeded negatives include two countersunk heads 4.5 mm apart that the check must refuse. Out of scope: the owner's drilling accuracy.
    got = named(results, "c3.tray_screw_heads_apart")
    f = got["figures"]
    assert got["passed"] and len(f["pairs"]) == 1 and f["required_mm"] == params("plate.min_head_to_head_mm") == 6.8
    head, sink = params("screws.tray_plate_head_dia_mm"), params("screws.tray_plate_countersink_dia_mm")
    assert (f["head_dia_mm"], f["countersink_dia_mm"]) == (head, sink) == (5.5, 6.3)
    assert f["required_mm"] == pytest.approx(sink + 0.5) and sink > head, "the distance is the countersink and a 0.5 mm web, and the countersink is wider than the head"
    assert f["pairs"][0]["axes_mm"] > f["required_mm"] and f["pairs"][0]["countersink_gap_mm"] > 0.5
    # the figures come from the screw's standard and are stated in the record
    assert "ISO 7046" in params.entry("screws.tray_plate_head_dia_mm")["source"] and "6.3 mm across" in params.entry("screws.tray_plate_countersink_dia_mm")["source"]
    assert "5.5 mm" in record and "6.3 mm" in record and "6.8 mm" in record and "`c3.tray_screw_heads_apart`" in record
    assert "the ISO 7046 M3 countersunk screw: its head is 5.5 mm across as made" in record


@pytest.mark.controls("c1_heads_4_5_apart")
def test_c1_two_countersunk_heads_4_5_mm_apart_are_refused(controls):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C1: The case model's checks require every pair of tray-screw heads, and of the countersinks they sit in at the bar's back face, to stand at least the record's head-to-head distance apart, with the head and countersink diameters taken from the screw's standard and stated in the record, and the case's seeded negatives include two countersunk heads 4.5 mm apart that the check must refuse. Out of scope: the owner's drilling accuracy.
    got = controls.get("c1_heads_4_5_apart")["heads"]
    assert not got["passed"]
    close = [p for p in got["figures"]["pairs"] if abs(p["axes_mm"] - 4.5) < 1e-6]
    assert len(close) == 2 and all(not p["pass"] for p in close), "the two pairs in the pilasters, 4.5 mm apart on the axes, are the ones refused"
    assert all(p["head_gap_mm"] < 0.0 and p["countersink_gap_mm"] < 0.0 for p in close), "the heads collide and the countersinks merge"


def test_c1_the_distance_is_a_function_of_the_record_figures_and_the_pair_is_judged_both_ways(params):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C1: The case model's checks require every pair of tray-screw heads, and of the countersinks they sit in at the bar's back face, to stand at least the record's head-to-head distance apart, with the head and countersink diameters taken from the screw's standard and stated in the record, and the case's seeded negatives include two countersunk heads 4.5 mm apart that the check must refuse. Out of scope: the owner's drilling accuracy.
    need = params("plate.min_head_to_head_mm")
    assert check.heads_apart([(0.0, 9.5), (0.0, 9.5 + need)], params)["pass"]
    assert not check.heads_apart([(0.0, 9.5), (0.0, 9.5 + need - 0.01)], params)["pass"], "just under the record's distance is refused"
    assert not check.heads_apart([(0.0, 9.5), (4.5, 9.5)], params)["pass"], "a pair across the plate's length is judged as a pair too"
    assert not check.heads_apart([(0.0, 9.5), (3.0, 9.5 + 4.0), (30.0, 9.5)], params)["pass"], "one close pair among three spoils the set"
    assert check.heads_apart([(0.0, 9.5), (30.0, 9.5), (60.0, 9.5)], params)["pass"] and check.heads_apart([], params)["pass"]


# ---------------------------------------------------------------- C2: one insert in each pilaster

def test_c2_one_insert_in_each_pilaster_with_the_wall_at_the_minimum_and_the_screw_inside_it(results, params, record, model):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C2: The case model places one M3 heat-set insert in each pilaster's end face, in a hole of the size and depth the insert's maker states, with the wall round the hole held at the record's minimum, and a short M3 countersunk screw through the bar threads into it; the record names the insert's size, hole and depth. Out of scope: the insert maker's brand.
    got = named(results, "c3.tray_insert_seat")
    f = got["figures"]
    assert got["passed"] and f["inserts_counted"] == f["screws_counted"] == f["pilasters"] == 2 and f["per_pilaster"] == 1
    assert (f["hole_dia_mm"], f["hole_depth_mm"], f["insert_length_mm"]) == (4.0, 6.7, 5.7)
    assert all(r["least_wall_mm"] >= params("case.insert_wall_min_mm") - 1e-9 for r in f["inserts"]) and params("case.insert_wall_min_mm") == 2.0
    # the screw's engaged length lies within the insert and short of the hole's floor, and it does not leave the bar unclamped
    assert f["engaged_length_mm"] == pytest.approx(params("screws.tray_plate_length_mm") - params("plate.thickness_mm")) == pytest.approx(5.0)
    assert f["minimum_thread_mm"] <= f["engaged_length_mm"] <= f["insert_length_mm"] and f["tip_to_hole_floor_mm"] == pytest.approx(f["hole_depth_mm"] - f["engaged_length_mm"])
    assert f["tip_to_hole_floor_mm"] > 0.0
    assert f["reservoir_mm"] == pytest.approx(f["hole_depth_mm"] - f["insert_length_mm"]) and f["reservoir_mm"] >= 0.5
    assert f["engaged_length_mm"] + f["tip_to_hole_floor_mm"] == pytest.approx(f["hole_depth_mm"]), "the screw ends before the floor"
    # the model really has the holes: the tray's solid shares nothing with each insert's hole and has its wall standing round it
    def volume(shape):
        return float(getattr(shape, "volume", 0.0) or 0.0)

    depth, r = params("case.insert_hole_depth_mm"), params("case.insert_hole_dia_mm") / 2
    for u in model.info["tray_pilaster_u"]:
        z = params("screws.tray_plate_z_mm")[0]
        hole = case.insert_hole_solid(model, u, z)
        inside = case.cyl_v(u, z, model.v_plate + 0.2, model.v_plate + depth - 0.2, r - 0.05)
        assert volume(model.parts["tray"] & inside) < 0.05, "the hole is empty down to its floor"
        wall = case.cyl_v(u, z, model.v_plate + 0.2, model.v_plate + depth - 0.2, r + 0.5) - case.cyl_v(u, z, model.v_plate, model.v_plate + depth, r)
        assert volume(model.parts["tray"] & wall) > 5.0, "the printed wall stands round the hole"
        beyond = case.cyl_v(u, z, model.v_plate + depth + 0.1, model.v_plate + depth + 1.1, r - 0.05)
        assert volume(model.parts["tray"] & beyond) > 0.9 * volume(beyond), "the hole stops at its floor"
        assert volume(hole) > math.pi * r * r * depth
    # the record names the insert's size, hole and depth
    assert "M3 heat-set insert" in record and "5.7 mm long" in record and "a hole 4.0 mm across and 6.7 mm deep" in record
    assert "`c3.tray_insert_seat`" in record and "2.0 mm" in record


@pytest.mark.controls("c2_thin_wall", "c2_long_screw", "c2_short_screw", "c2_shallow_hole", "c3_screw_in_pocket")
def test_c2_a_thin_wall_a_screw_too_long_or_short_and_a_shallow_hole_are_each_refused(controls, params):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C2: The case model places one M3 heat-set insert in each pilaster's end face, in a hole of the size and depth the insert's maker states, with the wall round the hole held at the record's minimum, and a short M3 countersunk screw through the bar threads into it; the record names the insert's size, hole and depth. Out of scope: the insert maker's brand.
    thin = controls.get("c2_thin_wall")
    assert not thin["passed"] and min(r["least_wall_mm"] for r in thin["figures"]["inserts"]) < params("case.insert_wall_min_mm")
    long = controls.get("c2_long_screw")
    assert not long["passed"] and long["figures"]["tip_to_hole_floor_mm"] < 0.0 and long["figures"]["engaged_length_mm"] > long["figures"]["insert_length_mm"], "an M3 x 14 reaches the hole's floor and the head cannot seat"
    short = controls.get("c2_short_screw")
    assert not short["passed"] and short["figures"]["engaged_length_mm"] < short["figures"]["minimum_thread_mm"], "an M3 x 7 engages too little thread"
    shallow = controls.get("c2_shallow_hole")
    assert not shallow["passed"] and shallow["figures"]["reservoir_mm"] < 0.5, "a hole 5.9 mm deep leaves no room for the displaced plastic under the 5.7 mm insert"
    # an insert hole in the lid toe's pocket is refused by the fit check as well, and its wall figure says why
    pocket = controls.get("c3_screw_in_pocket")
    assert not pocket["passed"]


# ---------------------------------------------------------------- C3: the root, the allowance and the proof load

def test_c3_the_insert_allowance_the_window_and_the_two_directions_are_recomputed_from_the_params(results, params, record):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C3: The case record states the insert's pull-out allowance as 680 N with its source, the maker's lower moulded-ABS figure, marking the figure for printed ASA in this layer direction as an assumption, and states the insert's height as inside the window the pocket floor, the countersink and the allowance leave. It re-judges the tray root's tension and the triac end's motion at the new fixing in both the push-on and the pull-off direction against the limits the record already states, so that the fixing holds through repeated removal of the tray. The record gives the owner's proof load with home kit: twice the design load, pulled at the blade end in both directions with the bar clamped and the tray fitted, states that it tests beyond the allowance, and names the direct M3 x 16 screw with a 4 mm step as the fallback a failed proof takes. Out of scope: the printed plastic's measured strength.
    root = named(results, "c9.tray_root_tension_and_triac_end_motion")
    f = root["figures"]
    force, span = params("blade.insertion_force_N"), f["span_mm"]
    z, pivot, top, allowance = params("screws.tray_plate_z_mm")[0], f["pivot_z_mm"], params("case.z_wall_top_mm"), params("screws.tray_insert_pullout_N")
    assert allowance == 680.0 and "assumed" in params.entry("screws.tray_insert_pullout_N")["source"] and "moulded-ABS" in params.entry("screws.tray_insert_pullout_N")["source"]
    # arithmetic: each direction is the moment shared between two inserts over the insert's lever
    moment = force * span
    push, pull = moment / (2 * (z - pivot)), moment / (2 * (top - z))
    assert f["tension_max_N"] == pytest.approx(push, rel=1e-9) and f["pull_off_tension_max_N"] == pytest.approx(pull, rel=1e-9)
    assert f["utilisation"] == pytest.approx(push / allowance) and f["pull_off_utilisation"] == pytest.approx(pull / allowance)
    assert 0.60 <= f["utilisation"] <= 0.70 and push < allowance and pull < allowance and pull < push
    # the window the pocket floor, the countersink and the allowance leave, from the figures of the record
    wall, r = params("case.insert_wall_min_mm"), params("case.insert_hole_dia_mm") / 2
    pocket_floor = top - 4.0
    upper = pocket_floor - wall - r * math.sqrt(2.0)
    lower_sink = pivot + params("plate.screw_edge_distance_mm") + params("screws.tray_plate_countersink_dia_mm") / 2
    lower_allowance = pivot + moment / 2 / allowance
    assert upper == pytest.approx(11.67, abs=0.005) and lower_sink == pytest.approx(9.65) and lower_allowance == pytest.approx(9.89, abs=0.005)
    assert max(lower_sink, lower_allowance) < z <= upper, "the insert's height stands inside the window"
    assert moment / 2 / (upper - pivot) == pytest.approx(467, abs=1.0) and moment / 2 / (12.5 - pivot) == pytest.approx(407, abs=1.0) and moment / 2 / (top - 12.5) == pytest.approx(331, abs=1.0)
    # the triac end's motion, in both directions, holds the limit the record already states
    assert max(f["triac_end_motion_mm"], f["pull_off_triac_end_motion_mm"]) < f["allowed_motion_mm"] == 0.05
    assert f["triac_end_motion_mm"] == pytest.approx(f["tray_flexure_at_triac_end_mm"] + f["root_motion_at_triac_end_mm"])
    # the proof load: twice the design load, above the allowance on the push-on side and below the lowest printed-part result
    assert f["proof_factor"] == 2.0 and f["proof_load_N"] == pytest.approx(151.2) and 15.5 * 9.81 == pytest.approx(f["proof_load_N"], abs=1.0)
    assert allowance < f["proof_tension_max_N"] < 1170.0
    # what the record states
    for needle in ("**The pull-out allowance used** for each insert is 680 N", "the insert maker's lower moulded-ABS figure", "an assumption for printed ASA in this layer direction",
                   "%.0f N pushing on" % f["proof_tension_max_N"], "**The insert's height.**", "9.9 to 11.67 mm", "**The owner's proof load, with home kit.**", "15.5 kg", "151 N",
                   "in both directions", "deliberately tests beyond the 680 N allowance", "the direct M3 x 16 screw with a 4 mm step", "**Pull-off.**", "%.0f N, %.3f of the allowance" % (f["pull_off_tension_max_N"], f["pull_off_utilisation"]),
                   "%.4f mm pushing on" % f["triac_end_motion_mm"], "%.4f mm pulling off" % f["pull_off_triac_end_motion_mm"], "bar is clamped to a bench with the tray fitted"):
        assert needle in record, needle
    assert "about 365 N" not in record and "%.3f of its allowance" % f["utilisation"] in record


@pytest.mark.controls("c9_weak_pilot")
def test_c3_an_allowance_below_the_load_fails_in_each_direction_it_is_exceeded(controls):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C3: The case record states the insert's pull-out allowance as 680 N with its source, the maker's lower moulded-ABS figure, marking the figure for printed ASA in this layer direction as an assumption, and states the insert's height as inside the window the pocket floor, the countersink and the allowance leave. It re-judges the tray root's tension and the triac end's motion at the new fixing in both the push-on and the pull-off direction against the limits the record already states, so that the fixing holds through repeated removal of the tray. Out of scope: the printed plastic's measured strength.
    got = named(controls.get("c9_weak_pilot"), "c9.tray_root_tension_and_triac_end_motion")
    f = got["figures"]
    assert not got["passed"] and f["tension_max_N"] > f["pullout_capacity_N"] and f["pull_off_tension_max_N"] > f["pullout_capacity_N"] == 100.0


# ---------------------------------------------------------------- C4: the hole keeps the mains distance

def test_c4_each_insert_hole_and_its_wall_keeps_the_larger_of_the_signed_clearance_and_creepage_from_mains_copper(results, basis, record):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C4: The case model states the distance from each insert hole and its wall to the nearest mains copper in the board's design, and it is at least the larger of the separation basis's signed clearance and creepage, whatever the screw is made of. Out of scope: the position of the board's own mounting holes.
    check7 = named(results, "c7.screws_clear_of_mains_copper")
    inserts = [s for s in check7["figures"]["screws"] if s["kind"] == "insert"]
    assert len(inserts) == 2 and check7["passed"]
    need = max(basis["clearance_mains_mm"], basis["creepage_mains_mm"])
    assert need == 2.6 and all(s["required_mm"] == need and s["distance_mm"] >= need and s["pass"] for s in inserts)
    assert all(s["nearest_item"] and set(s["per_layer_mm"]) == {"F.Cu", "B.Cu"} for s in inserts), "the nearest copper is named and both layers are measured"
    for s in inserts:
        assert ("insert (u %g, z %g)" % (s["centre_uvz_mm"][0], s["centre_uvz_mm"][2])) in record and ("%.2f mm" % s["distance_mm"]) in record
    assert "each insert's hole and its wall keep the larger of the signed clearance and creepage, 2.6 mm" in record and "whatever the screw is made of" in record


@pytest.mark.controls("c4_insert_near_mains")
def test_c4_an_insert_wall_between_the_clearance_and_the_creepage_of_mains_copper_is_refused(controls, basis):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C4: The case model states the distance from each insert hole and its wall to the nearest mains copper in the board's design, and it is at least the larger of the separation basis's signed clearance and creepage, whatever the screw is made of. Out of scope: the position of the board's own mounting holes.
    got = controls.get("c4_insert_near_mains")
    assert not got["passed"] and got["row"]["pass"] is False and got["base"]["pass"] is True
    assert basis["clearance_mains_mm"] <= got["row"]["distance_mm"] < basis["creepage_mains_mm"], "1.5 mm clears the clearance and not the creepage: the larger figure governs"
    assert got["row"]["required_mm"] == max(basis["clearance_mains_mm"], basis["creepage_mains_mm"])


# ---------------------------------------------------------------- C5: the bar, the bolts and the opening follow the pilasters

def test_c5_the_bar_the_wall_bolts_and_the_opening_follow_the_pilaster_width(results, params, record, model):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C5: The plate's length, its wall-bolt positions and the opening in the machine's plastic wall follow the pilaster width with the bolt zones unchanged, the case lies between the bolt zones with the record's clearance to each washer, and the record, the drawings and the division record state the new figures. Out of scope: the owner's wall cut and signing of the sign-off lines.
    length = named(results, "c3.plate_length")["figures"]
    pil, wall = params("case.pilaster_out_mm"), params("case.wall_mm")
    assert pil + wall == 8.0 and params("plate.bolt_zone_mm") == 10.0
    width = 45.0 + params("case.interior_left_mm") + params("case.interior_right_mm") + 2 * (wall + pil)
    assert length["case_outer_width_mm"] == pytest.approx(width) == pytest.approx(64.5)
    assert length["required_mm"] == pytest.approx(width + 20.0) and length["plate_length_mm"] == params("plate.length_mm") == 85.0 and length["margin_mm"] == pytest.approx(0.5)
    bolts = named(results, "c3.wall_bolts_outside_case")
    assert bolts["passed"]
    washer_need = params("plate.washer_to_case_clearance_mm")
    assert all(b["washer_clear_of_case_mm"] >= washer_need for b in bolts["figures"]["bolts"]) and [round(b["bolt_u_mm"], 2) for b in bolts["figures"]["bolts"]] == [-13.75, 61.25]
    opening = named(results, "c2.wall_opening_stated")
    assert opening["passed"] and opening["figures"]["opening_width_mm"] == pytest.approx(params("plate.length_mm") + 2 * params("plate.wall_opening_clearance_mm")) == pytest.approx(88.0)
    for needle in ("85.0 mm long", "64.50 + 2 x 10.0 = 84.50 <= 85.0", "88.0 x 35.6 mm", "u -13.75 and 61.25", "0.55 mm clear of the case"):
        assert needle in record, needle
    plate = drawing_text("plate-drawing.svg")
    assert "cut to 85 mm long" in plate and "case outer width at the plate 64.50 + 2 x bolt zone 10.0 = 84.50" in plate and "88.0 x 35.6" in plate and "margin 0.50" in plate
    division = flat(read(DIVISION))
    assert "**88.0 mm long**" in division and "its span along the wall is set by the case" in division and "85 mm bar" in division
    assert model.info["plate"]["u1"] - model.info["plate"]["u0"] == pytest.approx(85.0)


@pytest.mark.controls("c5_wide_pilasters_short_bar", "c5_wide_pilasters_long_bar", "c5_washer_too_close")
def test_c5_a_wider_pilaster_with_the_same_bar_is_refused_and_with_a_longer_bar_the_opening_follows(controls, params):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C5: The plate's length, its wall-bolt positions and the opening in the machine's plastic wall follow the pilaster width with the bolt zones unchanged, the case lies between the bolt zones with the record's clearance to each washer, and the record, the drawings and the division record state the new figures. Out of scope: the owner's wall cut and signing of the sign-off lines.
    short = controls.get("c5_wide_pilasters_short_bar")["refused"]
    assert short and "keep-out" in short, "pilasters 2.0 mm wider each leave the 85 mm bar short of the case and its bolt zones"
    longer = by_name(controls.get("c5_wide_pilasters_long_bar"))
    assert longer["c3.plate_length"]["passed"] and longer["c3.plate_length"]["figures"]["case_outer_width_mm"] == pytest.approx(68.5)
    assert longer["c2.wall_opening_stated"]["figures"]["opening_width_mm"] == pytest.approx(95.0 + 3.0), "the opening follows the bar"
    assert [round(b["bolt_u_mm"], 2) for b in longer["c3.wall_bolts_outside_case"]["figures"]["bolts"]] != [-13.75, 61.25], "the bolts move out with the bar's ends"
    tight = by_name(controls.get("c5_washer_too_close"))["c3.wall_bolts_outside_case"]
    assert not tight["passed"] and min(b["washer_clear_of_case_mm"] for b in tight["figures"]["bolts"]) < 2.0


# ---------------------------------------------------------------- C6: set flush, marked from the tray

def flush_problems(record, plate, case_drawing):
    problems = []
    for where, text in (("the record", record), ("the plate drawing", plate), ("the case drawings", case_drawing)):
        if not re.search(r"inserts? (is|are)? ?set flush and square|set each M3 heat-set insert flush and square|inserts set flush and square", text, re.I):
            problems.append("%s does not say the inserts are set flush and square" % where)
        if "proud insert holds the tray off the bar" not in text:
            problems.append("%s does not say a proud insert holds the tray off" % where)
        if not re.search(r"marked from the printed tray with the bar seated on (the|its) ledge", text):
            problems.append("%s does not say the holes are marked from the tray with the bar on the ledge" % where)
        if not re.search(r"(each|every) (countersunk )?head sits flush with or below the (bar's )?back face|sitting flush with or below the bar's back face", text):
            problems.append("%s does not say the heads sit flush or below" % where)
        if not re.search(r"two (tray-screw )?holes|two M3 countersunk holes|two tray screws|two M3 x \d+ countersunk screws", text, re.I):
            problems.append("%s does not give the two holes" % where)
    return problems


def test_c6_the_record_and_every_drawing_state_the_flush_inserts_the_proud_insert_and_the_marking_from_the_tray(record):
    record = record.replace("**", "")
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C6: The case record and every drawing the case model emits, the plate drawing among them, state that each insert is set flush and square before the bar is fitted, that a proud insert holds the tray off the bar, that the bar's two tray-screw holes are marked from the printed tray with the bar seated on the ledge, and that each countersunk head sits flush or below the bar's back face. Out of scope: the owner's drilling accuracy.
    plate, drawings = drawing_text("plate-drawing.svg"), drawing_text("case-drawings.svg")
    assert flush_problems(record, plate, drawings) == []
    # the drawings the model emits are exactly these two SVGs
    emitted = sorted(f for f in os.listdir(os.path.join(CASE_DIR, "out")) if f.endswith(".svg"))
    assert emitted == ["case-drawings.svg", "plate-drawing.svg"]
    for old, new, expect in (("proud insert holds the tray off the bar", "insert holds the tray", "proud insert"), ("marked from the printed tray with the bar seated on the ledge", "marked from the drawing", "marked from the tray"),
                             ("flush with or below the bar's back face", "flush with the bar's back face", "heads sit flush or below"), ("flush and square", "flush", "flush and square")):
        assert old in record
        assert any(expect in p for p in flush_problems(record.replace(old, new), plate, drawings)), expect
    assert any("proud insert" in p for p in flush_problems(record, plate.replace("proud insert holds the tray off the bar", "insert"), drawings))
    assert any("case drawings" in p for p in flush_problems(record, plate, drawings.replace("a proud insert holds the tray off the bar", "an insert")))
    assert any("heads sit flush" in p for p in flush_problems(record, plate.replace("each head sits flush with or below the back face", "each head is countersunk"), drawings))


# ---------------------------------------------------------------- C7: the fixing is stated once

EARLIER_FIXING = (
    (r"\bfour\b[^.|]{0,50}(tray|countersunk|M3)", "the earlier count of four tray screws"),
    (r"\bfour\b screws", "the earlier count of four screws"),
    (r"tray[- ]screws?[^.|]{0,60}pilot|pilot[^.|]{0,60}(tray[- ]screw|pilaster)|screw pilots?\b|pilots? holes? in the pilaster", "the pilot hole of the earlier fixing"),
    (r"M3 x 12", "the earlier screw length"),
    (r"z 9\.5 and 14\.0|9\.5 and 14\.0 mm", "the earlier stance"),
    (r"two (tray )?screws in each pilaster|two in each pilaster", "two screws in a pilaster"),
    (r"cut(s)? (it )?to 80 mm|80\.0 mm long, 20 mm wide|at least 79\.5|83\.0 x 35\.6|59\.50 mm wide", "the earlier bar length, width or opening"),
)


def earlier_fixing_problems(text):
    return [why for pattern, why in EARLIER_FIXING if re.search(pattern, text)]


def test_c7_no_earlier_count_pilot_hole_screw_length_or_bar_length_remains_in_the_record_or_the_drawings(record, params, results):
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C7: The case record and every drawing the case model emits, the plate drawing and the case drawings among them, state the tray's fixing once, as this solution gives it: the number of screws and inserts, their stance, the bar's length and the wall opening, and no earlier count, stance or length of the fixing remains stated in them, which the test shows by searching each for the earlier count, the pilot hole and the earlier screw length. The division record's opening carries the new length and says its span along the wall is set by the case. Out of scope: the owner's sign-off lines, which the next criterion covers.
    plate, drawings = drawing_text("plate-drawing.svg"), drawing_text("case-drawings.svg")
    for name, text in (("the case record", record), ("the plate drawing", plate), ("the case drawings", drawings)):
        assert earlier_fixing_problems(text) == [], name
    # the searches find what they are for
    assert earlier_fixing_problems("The tray is fixed with four M3 x 12 countersunk screws into the pilots") == ["the earlier count of four tray screws", "the earlier screw length"]
    assert "the pilot hole of the earlier fixing" in earlier_fixing_problems("marks the holes through the pilot holes of the tray screws")
    assert "the pilot hole of the earlier fixing" in earlier_fixing_problems("two M3 screws into the screw pilots")
    assert "the earlier stance" in earlier_fixing_problems("the tray screws stand at z 9.5 and 14.0")
    assert "the earlier bar length, width or opening" in earlier_fixing_problems("the owner cuts it to 80 mm") and "two screws in a pilaster" in earlier_fixing_problems("with two screws in each pilaster")
    # and the fixing the record gives is the model's, stated in each of the three
    zs = [float(z) for z in params("screws.tray_plate_z_mm")]
    assert len(zs) == 1 and zs == [11.65]
    n_tray = len(named(results, "c3.tray_screws_fit_plate")["figures"]["screws"])
    assert n_tray == 2 == named(results, "c3.tray_insert_seat")["figures"]["inserts_counted"]
    assert "two screws, one in each pilaster" in record and "z 11.65" in record and "M3 x 10" in record and "85.0 mm long" in record
    assert "Two M3 countersunk holes" in plate and "z 11.65" in plate and "cut to 85 mm long" in plate
    assert "two M3 x 10 countersunk screws, one in each pilaster" in drawings and "heat-set insert" in drawings
    # the division record's opening carries the new length and says its span along the wall is set by the case
    division = flat(read(DIVISION))
    assert "**88.0 mm long**" in division and "its span along the wall is set by the case" in division and "retired bracket's mounting ears" in division
    # the model builds no pilot for the tray screws: the only hole it cuts in a pilaster along v is the insert's
    assert not hasattr(case, "pilot_solid") and hasattr(case, "insert_hole_solid")


# ---------------------------------------------------------------- C8: the owner's sign-off record

def restated_problems(text):
    problems = []
    entry = re.search(r"^- W-19, restated.*$", text, re.M)
    if not entry:
        return ["no restated W-19 entry"]
    e = entry.group(0)
    for needle, why in (("accepted_by: Claude, on behalf of David Baker (owner), under his standing instruction of 2026-11-07", "not signed on his behalf"), ("accepted_on: 2026-11-28", "not dated 2026-11-28"),
                        ("one M3 heat-set insert in each pilaster", "the insert is not stated"), ("85 mm in place of 80 mm", "the 85 mm bar in place of the 80 mm cut is not stated"),
                        ("88.0 mm long in place of 83.0 mm", "the wider opening is not stated"), ("two tray-screw holes", "the two holes are not stated"),
                        ("\"I could probably mount an 80 x 30-35 mm spreader\"", "the owner's recorded statement is not set beside the bar"), ("5 mm longer than the 80 mm he said he could probably mount", "the 85 mm is not set beside his 80 mm"),
                        ("quotes no word of his beyond the one already recorded", "the entry does not say whose words it quotes")):
        if needle not in e:
            problems.append(why)
    behalf, carried = text.index("## Signed on behalf"), text.index("## Carried to named later steps")
    if not behalf < text.index("- W-19, restated") < carried:
        problems.append("the restated entry is not in the signed-on-behalf section")
    if "- W-19. The plate's form" not in text:
        problems.append("the first W-19 entry is gone")
    if "Restated 2026-11-28" not in text.split("## For David to sign or confirm at the end of the work")[1]:
        problems.append("the end-of-work item does not carry the restatement")
    return problems


def test_c8_the_sign_off_record_states_w19_again_at_the_new_fixing_and_the_longer_bar():
    # SOL-HW-HEATER-WALL-BOARD-TRAY-FIXING-SEATS-AND-HOLDS-THE-TRAY-THROUGH-REPEATED-REMOVAL.C8: The owner's sign-off record states its W-19 entry again at the new fixing, the 85 mm bar and the wider opening in place of the 80 mm cut, as a dated entry signed on the owner's behalf under his standing instruction. The entry sets the 85 mm bar beside the owner's recorded statement that he could probably mount an 80 by 30 to 35 mm spreader. Out of scope: the owner's reasons, which the entry records as said.
    text = read(os.path.join(BOARD_DIR, "owner-sign-off.md"))
    assert restated_problems(text) == []
    # the words quoted are the ones the division record holds
    assert "I could probably mount an 80 x 30-35 mm spreader" in read(DIVISION)
    for old, new, expect in (("accepted_on: 2026-11-28", "accepted_on: 2026-11-27", "not dated"), ("85 mm in place of 80 mm", "85 mm", "85 mm bar"), ("88.0 mm long in place of 83.0 mm", "88.0 mm long", "wider opening"),
                             ("5 mm longer than the 80 mm he said he could probably mount", "longer", "set beside his 80 mm"), ("\"I could probably mount an 80 x 30-35 mm spreader\"", "his words", "recorded statement"),
                             ("accepted_by: Claude, on behalf of David Baker (owner), under his standing instruction of 2026-11-07. accepted_on: 2026-11-28", "accepted_by: David Baker (owner). accepted_on: 2026-11-28", "his behalf"),
                             ("Restated 2026-11-28", "Noted", "end-of-work item")):
        assert old in text and any(expect in p for p in restated_problems(text.replace(old, new, 1))), expect
    # the earlier entry and its counts are untouched
    assert re.search(r"^- W-19\. The plate's form", text, re.M) and "There are 22 entries, W-1 to W-19" in text
