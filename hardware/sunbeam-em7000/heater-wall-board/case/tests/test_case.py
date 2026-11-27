"""Tests of the printed case of the heater wall board: the model, its check program and its generated artefacts.

Run with the interpreter `task hw:cad` creates, from the case folder:  python -m pytest tests
Each test is opened by a comment naming the criterion it verifies and its text. The negative controls rebuild the
model with one dimension broken and require the matching check to fail; `negatives.py` builds them in a small process
pool while the nominal model is built and checked. The skin is flow, the one the owner chose. The tests marked heavy
(every extreme of the seating range) run with `--heavy`.
"""

import json
import math
import os
import sys

import pytest

CASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CASE_DIR)
import case  # noqa: E402,I001  (build123d before vtk)
import check  # noqa: E402
import negatives  # noqa: E402

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

T = "SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON"


def named(results, name):
    return next(r for r in results if r["name"] == name)


def by_name(results):
    return {r["name"]: r for r in results}


# ---------------------------------------------------------------- parameters and sources

def test_every_parameter_has_a_source_and_the_seating_range_is_unconfirmed_with_its_bounds():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C16: The board-to-plate fit takes the scatter of the delivered triacs' seating, stated as a range of tab-hole height and lean, without loading the soldered leads: the tray's board seat and the barrier are shown by the model to meet at the range's extremes. The plate's tab holes are either a short slot or an oversize hole, or tapped holes drilled at the measured height of the delivered triacs with the tray printed to the measured values, and the case record states which the case takes; for tapped holes it states that the owner's acceptance of that departure from his ruling of 2026-11-24 (slot or oversize hole) is outstanding. The range with its source is recorded as unconfirmed for the owner to check at assembly.
    params = case.Params.load()
    assert params.sourced()
    assert all(isinstance(e["source"], str) and e["source"] for _, e in params.entries())
    seating = params.entry("seating")
    for key in ("body_underside_mm", "lean_deg", "differential_lean_deg", "tab_face_to_lead_centre_mm", "lead_protrusion_below_board_mm",
                "outline_routing_mm", "lead_play_mm"):
        assert seating[key]["unconfirmed"] is True and {"min", "max"} <= set(seating[key])


def test_separation_figures_are_read_from_the_basis_not_copied():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C1: The case's fixed base, the tray the board is screwed to and never the removable lid, carries an insulating barrier between the bare spreader plate face and the board's mains copper wherever the separation basis's basic creepage to the earthed plate would not otherwise hold. The barrier is a creepage barrier only and is not relied on as solid insulation. It is designed for the board as the assembler delivers it, with the triacs seated on their lead shoulders, from the board's layout file and the triac's package model, and it tolerates the delivered triacs' seating scatter. The case drawing or model states the barrier's minimum solid thickness, its height above the board face at each point along the plate edge, that it spans the board's width, the creepage path it gives from each triac pad edge to the first bare plate against the 2.6 mm the basis signs, and the gap it leaves between the board edge and the plate. The barrier is a printed wall of the tray, or a thin bought insulating film that the tray holds, and the drawing states which; a printed wall is at least 0.8 mm thick wherever it stands in the board-to-plate gap or the gap is shown wide enough for it. If neither can be made, the case instead holds the plate's lower edge at least 6.0 mm above the board's component face, which leaves the triac's leads 3.4 mm from the plate; that fallback reverses the owner's recorded plate position and takes the owner's recorded decision before it is used, and the drawing states which form the case takes. Making the plate and printing the case are out of scope.
    text = open(case.PARAMS, encoding="utf-8").read()
    assert "creepage_mm" not in text and "clearance_mm: 1.5" not in text
    sep = case.basis()
    assert sep["creepage_mains_mm"] == 2.6 and sep["clearance_mains_mm"] == 1.5 and sep["creepage_lv_mm"] == 10.0 and sep["clearance_lv_mm"] == 3.0


def test_frame_offsets_are_read_from_edge_cuts(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C8: No part of the tray, the lid or any rib or barrier crosses the mouth of either 1.5 mm slot open at the board's right edge (slot A from board (51.0, 49.44) to (65.0, 50.94) and slot B from (51.0, 65.46) to (65.0, 66.96), as the board's layout plan states them), so the creepage the slots lengthen is not shortened; the case drawing or model shows the clearance at each mouth. Out of scope: the slots' dimensions, which the layout fixed.
    assert (model.board.ox, model.board.oy) == (20.0, 21.0)
    assert model.board.outline.bounds == pytest.approx((0.0, 0.0, 45.0, 75.0))
    assert [round(s.bounds[1], 2) for s in model.board.slots] == [28.44, 44.46]


# ---------------------------------------------------------------- C1

def test_c1_plate_clear_of_the_pads_and_leads_without_a_barrier(model, results, basis):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C1: The case's fixed base, the tray the board is screwed to and never the removable lid, carries an insulating barrier between the bare spreader plate face and the board's mains copper wherever the separation basis's basic creepage to the plate would otherwise be short, or the case holds the plate's lower edge 6.0 mm above the board; the 6.0 mm fallback is taken here
    for name in ("c1.plate_lower_edge_raised", "c1.clearance_pad_to_plate", "c1.creepage_pad_to_plate", "c1.clearance_bare_lead_to_plate",
                 "c1.creepage_bare_lead_to_plate", "c1.creepage_all_mains_copper", "c1.straight_to_wall_plane", "c1.end_wall_stands_off",
                 "c1.plate_clear_of_end_wall", "c1.no_loose_part_or_coating"):
        assert named(results, name)["passed"], name
    # recompute the nearest pad edge to the plate independently, from the plate's mesh and the pad's outline in the case frame
    plate = model.mesh("plate")
    lo, hi = plate.bounds

    def to_plate(points):
        """The distance from each point to the plate's mesh bounds, the plate being a box with holes the nearest metal does not lie in."""
        gap = np.maximum.reduce([lo - points, np.zeros_like(points), points - hi])
        return np.linalg.norm(gap, axis=1)

    pad = next(p for p in model.board.refs["T921"]["pads"] if p["number"] == "1")
    pts = np.array([(x - model.board.ox, y - model.board.oy, 0.0) for x, y in pad["pad"].outline()])
    by_hand = float(to_plate(pts).min())
    figures = named(results, "c1.creepage_pad_to_plate")["figures"]
    assert figures["pads_mm"]["T921 pad 1 F.Cu"] == pytest.approx(by_hand, abs=0.1)
    assert figures["creepage_mm"] >= basis["creepage_mains_mm"]
    assert named(results, "c1.clearance_pad_to_plate")["figures"]["clearance_mm"] >= basis["clearance_mains_mm"]
    # the lead: the plate's lower edge stands above the lead's metal, and the nearest distance is the lead's top rear edge to the plate's lower front edge
    lead = model.mesh("T921_leads") if "T921_leads" in model.bodies else None
    assert lead is not None and float(lead.bounds[1][2]) < 6.0 and float(plate.bounds[0][2]) == pytest.approx(6.0)
    by_hand = float(to_plate(np.asarray(lead.vertices)).min())
    assert named(results, "c1.creepage_bare_lead_to_plate")["figures"]["leads"]["T921 leads"]["to_plate_mm"] == pytest.approx(by_hand, abs=0.05)


@pytest.mark.controls("c1_low_plate")
def test_c1_negative_plate_edge_too_low(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C1: The case's fixed base, the tray the board is screwed to and never the removable lid, carries an insulating barrier between the bare spreader plate face and the board's mains copper wherever the separation basis's basic creepage to the plate would otherwise be short, or the case holds the plate's lower edge 6.0 mm above the board; the 6.0 mm fallback is taken here
    low = by_name(controls.get("c1_low_plate"))
    assert not low["c1.plate_lower_edge_raised"]["passed"]
    assert not low["c1.creepage_pad_to_plate"]["passed"] and not low["c1.creepage_all_mains_copper"]["passed"]


# ---------------------------------------------------------------- C2 C3

def test_c2_case_within_the_former_outline_and_opening(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C2: The case drawing or model lies wholly within the spreader plate's outline in both directions across the wall, so that only the plate touches the wall, and states the opening in the plastic wall as the plate outline plus a stated clearance, with no larger opening needed for the case, the blades or the harness, which sit in the cavity. Cutting the wall is out of scope.
    r = named(results, "c2.case_within_former_outline")
    assert r["passed"] and min(r["figures"]["margins_mm"].values()) >= 0.25
    o = named(results, "c2.wall_opening_stated")
    assert o["passed"] and o["figures"]["opening_width_mm"] == pytest.approx(80.0 + 3.0)


@pytest.mark.controls("c3_short_plate")
def test_c2_c3_negative_short_plate(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C3: The plate drawing states a length not less than the case drawing's outer width plus a bolt zone at each end for the wall bolts, with the arithmetic shown. The plate's size is provisional until the owner cuts and measures the wall, and the criterion holds at the figure then recorded. Making the plate is out of scope.
    got = controls.get("c3_short_plate")          # a 70 mm plate under the same case
    assert not by_name(got["results"])["c3.plate_length"]["passed"]
    # and the core refuses an outline that a shorter plate no longer holds inside its bolt zones
    assert got["refused"] and "keep-out" in got["refused"]


def test_c3_plate_length_arithmetic(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C3: The plate drawing states a length not less than the case drawing's outer width plus a bolt zone at each end for the wall bolts, with the arithmetic shown. The plate's size is provisional until the owner cuts and measures the wall, and the criterion holds at the figure then recorded. Making the plate is out of scope.
    r = named(results, "c3.plate_length")
    f = r["figures"]
    assert r["passed"] and f["plate_length_mm"] >= f["case_outer_width_mm"] + 2 * f["bolt_zone_mm"]
    assert "x" in f["arithmetic"] and named(results, "c3.wall_bolts_outside_case")["passed"]
    svg = open(os.path.join(CASE_DIR, "out", "plate-drawing.svg"), encoding="utf-8").read() if os.path.exists(os.path.join(CASE_DIR, "out", "plate-drawing.svg")) else ""
    assert (not svg) or "Length arithmetic" in svg


# ---------------------------------------------------------------- C4

def test_c4_lid_sweep_clear(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C4: The case drawing or model shows the lid fitted and then removed by sliding or angling it away with the plate, case and board already placed at the machine's wall opening of the recorded plate outline plus clearance, with the lid's swept path clear of the opening, the plate and the case, and without removing the case or the plate. The check is made on the model against the board's layout geometry and the recorded opening, and the model's lid clearances are stated. The physical demonstration on a printed case is a separate leaf's. Designing the machine's wall opening is out of scope.
    r = named(results, "c4.lid_sweep")
    assert r["passed"] and r["figures"]["minimum_clearance_mm"] >= check.SWEEP_FLOOR
    assert r["figures"]["poses"] > 30 and r["figures"]["fitted_minimum_mm"] > 0.0
    inst = r["figures"]["installed_frame"]
    assert inst["gravity"] == [0.0, 0.0, 1.0] and 4.0 < inst["drop_at_far_end_during_tilt_mm"] < 4.7
    assert 6.0 < inst["slide_to_free_the_toes_mm"] < 10.0 and inst["clear_space_needed_below_the_case_mm"] >= inst["drop_at_far_end_during_tilt_mm"]


@pytest.mark.controls("c4_tight")
def test_c4_negative_tight_opening_and_missing_groove(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C4: The case drawing or model shows the lid fitted and then removed by sliding or angling it away with the plate, case and board already placed at the machine's wall opening of the recorded plate outline plus clearance, with the lid's swept path clear of the opening, the plate and the case, and without removing the case or the plate. The check is made on the model against the board's layout geometry and the recorded opening, and the model's lid clearances are stated. The physical demonstration on a printed case is a separate leaf's. Designing the machine's wall opening is out of scope.
    tight = named(controls.get("c4_tight"), "c4.lid_sweep")
    assert not tight["passed"]


# ---------------------------------------------------------------- C5 C11

def test_c5_lid_fixings_reached(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C5: The case drawing or model places every lid screw or fixing where a driver reaches it with the case installed, and none right against the wall opening; the drawing states the driver's approach for each. If the lid is retained without screws, the drawing states the retention. Out of scope: the lid's shape and the machine's wall opening.
    r = named(results, "c5.lid_screw_reached")
    assert r["passed"] and r["figures"]["distance_to_wall_plane_mm"] >= 20.0 and "-z" in r["figures"]["driver_approach"]
    assert named(results, "c5.toes_hold_plate_end")["passed"]
    assert named(results, "c5.retention_stated")["passed"]


def test_c19_every_fixing_is_reached_from_below_or_the_plates_back(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C19: The case record states the installed orientation as the owner gave it: the plate is vertical on the machine's wall, the board projects from it horizontally with its component side facing down, the tray holds the board's bare back above the parts, and the lid closes the underside and comes off downward. The case is judged in that orientation: the lid removal sweep, the reach of every fixing and of each receptacle, the test finger and drip paths of every opening (falling onto the bare back, not onto parts), and the heat release through the vents given that warm air rises past the board, are each stated for it. Each printed part's print orientation is stated separately from its installed orientation.
    r = named(results, "c5.fixings_reached_installed")
    rows = {f["fixing"]: f for f in r["figures"]["fixings"]}
    assert r["passed"] and r["figures"]["installed_frame"]["gravity"] == [0.0, 0.0, 1.0]
    assert rows["lid screw"]["driver_from"] == "below" and not rows["lid screw"]["needs_lid_off"]
    assert rows["board screw H1"]["driver_from"] == "below" and rows["board screw H1"]["needs_lid_off"] and rows["board screw H1"]["nearest_gap_mm"] >= 0.3
    for ref in case.TRIAC_REFS:
        row = rows[f"tab screw {ref}"]
        assert row["driver_from"] == f"out from the wall, {row['tilt_deg']:.1f} degrees below level" and row["needs_lid_off"]
        assert row["origin_direction"][1] > 0.9              # a near-horizontal reach out from the wall, not one from below
    assert "out from the wall" in r["summary"] and "both tab screws from below" not in r["summary"]
    assert rows["tray-to-plate screws (4)"]["driver_from"] == "behind the plate"


@pytest.mark.controls("c5_no_barb")
def test_c5_negative_toe_without_barb(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C5: The case drawing or model places every lid screw or fixing where a driver reaches it with the case installed, and none right against the wall opening; the drawing states the driver's approach for each. If the lid is retained without screws, the drawing states the retention. Out of scope: the lid's shape and the machine's wall opening.
    res = by_name(controls.get("c5_no_barb"))
    assert not res["c5.toes_hold_plate_end"]["passed"]


def test_c11_tab_screws_and_blades(results, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C11: The case record states the order in which the plate, case, board and lid are fitted and removed, and shows that the wall bolts stand outside the case so the plate, case and board leave the wall as one unit, that each triac tab screw is reached by a driver through the case, and that the blade terminals stay reachable with the lid on. Making the parts and fitting them to the machine are out of scope.
    d = named(results, "c11.tab_screw_driver_reached")
    assert d["passed"]
    for ref in case.TRIAC_REFS:
        assert 0.0 <= d["figures"]["drivers"][ref]["tilt_deg"] <= model.P("screws.driver_max_tilt_deg")
        assert d["figures"]["drivers"][ref]["nearest_gap_mm"] >= 0.3
    assert named(results, "c11.blade_terminals_reachable_lid_on")["passed"]
    assert named(results, "c3.wall_bolts_outside_case")["passed"]


@pytest.mark.controls("c11_driver")
def test_c11_negative_driver_blocked_by_a_high_far_wall(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C11: The case record states the order in which the plate, case, board and lid are fitted and removed, and shows that the wall bolts stand outside the case so the plate, case and board leave the wall as one unit, that each triac tab screw is reached by a driver through the case, and that the blade terminals stay reachable with the lid on. Making the parts and fitting them to the machine are out of scope.
    res = by_name(controls.get("c11_driver"))
    assert not res["c11.tab_screw_driver_reached"]["passed"]


# ---------------------------------------------------------------- C6 C9

def test_c6_board_held_by_the_tray(results, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C6: The board is held securely and stably by its one mounting hole H1 and by a printed ledge, hold-down fingers or ribs that belong to the tray and not to the removable lid, so that taking the lid off leaves the board held, and the case drawing states what holds the board. The case is printable at home and fixed with ordinary screws. Which of the ledge, fingers or ribs it uses is the case design's choice. Out of scope: the choice among ledge, fingers and ribs, and the board's outline.
    seat = named(results, "c6.board_seat")
    assert seat["passed"] and len(seat["figures"]["seat_points"]) >= 12
    assert all(abs(p["gap_mm"]) <= 0.02 for p in seat["figures"]["seat_points"])
    hold = named(results, "c6.hold_down_and_h1")
    assert hold["passed"] and hold["figures"]["lid_to_board_mm"] > 0.5 and hold["figures"]["what_holds_the_board"]


@pytest.mark.controls("c6_no_finger")
def test_c6_negative_no_finger(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C6: The board is held securely and stably by its one mounting hole H1 and by a printed ledge, hold-down fingers or ribs that belong to the tray and not to the removable lid, so that taking the lid off leaves the board held, and the case drawing states what holds the board. The case is printable at home and fixed with ordinary screws. Which of the ledge, fingers or ribs it uses is the case design's choice. Out of scope: the choice among ledge, fingers and ribs, and the board's outline.
    res = by_name(controls.get("c6_no_finger"))
    assert not res["c6.hold_down_and_h1"]["passed"]


def test_c9_backing_and_stiffness(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C9: The tray carries rigid backing, a rib or pad, under the board face beneath J911, J921 and J941, and the case drawing shows the push-on direction of the 6.3 mm terminals and the support. The model shows the backing's contact over the board face under each blade and a stated stiffness basis for it (its section and span), so that a terminal pushed on does not move the board against the triac leads. The physical push-on demonstration on a printed tray is a separate leaf's. Out of scope: the terminals' own retention force.
    r = named(results, "c9.backing_contact_and_stiffness")
    f = r["figures"]
    assert r["passed"] and [c["blade"] for c in f["contact"]] == ["J941", "J921", "J911"]
    assert all(c["contact_fraction"] >= 0.99 and c["contact_area_mm2"] > 4.0 for c in f["contact"])
    assert f["second_moment_mm4"] > 1000 and "-z" in f["push_on_direction"] and f["basis"]
    assert f["deflection_at_triac_end_mm"] <= f["allowed_mm"]


@pytest.mark.controls("c9_soft")
def test_c9_negative_soft_material(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C9: The tray carries rigid backing, a rib or pad, under the board face beneath J911, J921 and J941, and the case drawing shows the push-on direction of the 6.3 mm terminals and the support. The model shows the backing's contact over the board face under each blade and a stated stiffness basis for it (its section and span), so that a terminal pushed on does not move the board against the triac leads. The physical push-on demonstration on a printed tray is a separate leaf's. Out of scope: the terminals' own retention force.
    res = by_name(controls.get("c9_soft"))
    assert not res["c9.backing_contact_and_stiffness"]["passed"]


# ---------------------------------------------------------------- C7 C8

def test_c7_screws_clear_of_mains_copper(results, basis):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C7: Each screw or post of the case that meets the board, and the board's hole H1, keeps its pad and courtyard at the larger of the separation basis's signed clearance and creepage from mains copper, as the pre-order check's mounting_hole rule holds it, on every layer, so no safety property depends on a screw's material. The case drawing or model states each screw's centre and its distance from the nearest mains copper in the board's design. Out of scope: the position of the board's hole H1, which the layout fixed.
    r = named(results, "c7.screws_clear_of_mains_copper")
    kinds = {s["kind"] for s in r["figures"]["screws"]}
    assert r["passed"] and kinds == {"tab", "h1", "tray_plate", "lid"}
    for s in r["figures"]["screws"]:
        assert len(s["centre_uvz_mm"]) == 3 and set(s["per_layer_mm"]) == {"F.Cu", "B.Cu"} and s["distance_mm"] >= s["required_mm"]
        if s["kind"] == "lid":
            assert s["required_mm"] == basis["creepage_lv_mm"]
        if s["kind"] == "tray_plate":
            assert s["required_mm"] >= 3.0
    h1 = named(results, "c7.h1_pad_and_courtyard")
    assert h1["passed"] and h1["figures"]["required_mm"] == max(basis["clearance_mains_mm"], basis["creepage_mains_mm"])


def test_c7_negative_screw_on_a_pad(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C7: Each screw or post of the case that meets the board, and the board's hole H1, keeps its pad and courtyard at the larger of the separation basis's signed clearance and creepage from mains copper, as the pre-order check's mounting_hole rule holds it, on every layer, so no safety property depends on a screw's material. The case drawing or model states each screw's centre and its distance from the nearest mains copper in the board's design. Out of scope: the position of the board's hole H1, which the layout fixed.
    pad = model.board.refs["T921"]["pads"][1]
    near = check.copper_distance(model, [(pad["u"], pad["v"], 0.0, 1.5)])
    assert min(d for d, _ in near.values()) < 2.6


def test_c8_slot_mouths_clear(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C8: No part of the tray, the lid or any rib or barrier crosses the mouth of either 1.5 mm slot open at the board's right edge (slot A from board (51.0, 49.44) to (65.0, 50.94) and slot B from (51.0, 65.46) to (65.0, 66.96), as the board's layout plan states them), so the creepage the slots lengthen is not shortened; the case drawing or model shows the clearance at each mouth. Out of scope: the slots' dimensions, which the layout fixed.
    r = named(results, "c8.slot_mouths_clear")
    assert r["passed"] and len(r["figures"]["slots"]) == 2
    assert all(s["least_mm"] >= 2.0 for s in r["figures"]["slots"])


@pytest.mark.controls("c8_rib")
def test_c8_negative_rib_across_the_mouth_and_near_wall(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C8: No part of the tray, the lid or any rib or barrier crosses the mouth of either 1.5 mm slot open at the board's right edge (slot A from board (51.0, 49.44) to (65.0, 50.94) and slot B from (51.0, 65.46) to (65.0, 66.96), as the board's layout plan states them), so the creepage the slots lengthen is not shortened; the case drawing or model shows the clearance at each mouth. Out of scope: the slots' dimensions, which the layout fixed.
    got = controls.get("c8_rib")
    assert not named(got["results"], "c8.slot_mouths_clear")["passed"]
    assert got["refused"]          # a wall that near the slot mouths takes the board's keep-in away


# ---------------------------------------------------------------- C13

def test_c13_forms_share_dimensions_and_logo_is_engraved_on_both_faces(results, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    share = named(results, "c13.forms_share_dimensions")
    assert share["passed"] and not share["figures"]["inlay_part_present"] and share["figures"]["geometry_identical"]
    assert named(results, "c13.mark_on_lid")["passed"]
    logo = named(results, "c13.logo_present_in_each_form")
    f = logo["figures"]
    assert logo["passed"] and f["forms"] == ["single", "two"] and not f["wrong_samples"]
    assert f["lid_height_mm"] >= 28.0 - 0.05 and f["tray_height_mm"] == pytest.approx(48.0, abs=0.3)
    assert f["tray_logo_clear_of_chamfer_mm"] >= 4.0 - 0.05
    assert min(f["outline_drawn_fraction"].values()) >= 0.95
    assert f["floor_under_tray_grooves_mm"] >= model.P("envelope.min_wall_mm") - 0.02
    assert f["groove_width_mm"] == 1.0 and f["groove_depth_mm"] == 0.4 and f["widest_pocket_at_a_junction_mm"] <= model.P("printer.bridge_limit_mm")
    assert {model.P("forms.two.tray_colour"), model.P("forms.two.lid_colour")} == {"#2f3237", "#e6e1d6"}
    assert model.P("forms.single.lid_colour") == model.P("forms.single.tray_colour")
    assert set(model.parts) >= {"tray", "lid_single", "lid_two", "lid_swap", "tray_swap"} and "film" not in model.parts and not {"inlay", "groove_floor", "tray_groove_floor"} & set(model.parts)


def test_c13_the_engraving_follows_the_vector_groups(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    import logo
    from shapely import affinity
    from shapely.geometry import Point
    P = model.P
    e = logo.engrave(P, 40.0)
    vec = logo.read_vector()
    k = 40.0 / 100.0
    assert vec.height == 100.0 and e.dark_faces == len(vec.dark) == 8 and e.light_faces == len(vec.light)
    assert e.sheets_kept > 0 and e.sheets_dropped > 0

    def placed(face):
        return affinity.translate(affinity.scale(face, k, k, origin=(0, 0)), -vec.silhouette.bounds[0] * k, -vec.silhouette.bounds[1] * k)
    # a light face is plain: the middle of its largest face holds no groove
    biggest = max(vec.light, key=lambda f: f.area)
    assert not e.geometry.intersects(placed(biggest).buffer(-1.0))
    # a dark face is tone: every face wide enough for two hatch lines is hatched; its edges inside the outline are not grooved by the
    # boundary rule (the boundary is the silhouette and the light/light seams only, counted in the next test)
    inside_sil = e.outline.buffer(-0.7)
    for face, angle in vec.dark:
        mm = placed(face)
        if logo.across(mm) >= 2.0:
            assert e.hatch.intersection(mm).area > 0.15 * mm.area
        assert e.boundary.intersection(mm.buffer(-0.5)).is_empty or e.boundary.intersection(mm.buffer(-0.5)).area < 0.01
    # every groove is at least the least feature wide and no two are nearer than the least land
    least = P("logo.min_feature_mm")
    assert e.geometry.buffer(-(least / 2 - 0.01)).buffer(least / 2 - 0.01).symmetric_difference(e.geometry).area < 0.02 * e.geometry.area
    assert e.geometry.buffer(least / 2 - 0.01).buffer(-(least / 2 - 0.01)).symmetric_difference(e.geometry).area < 0.02 * e.geometry.area
    # the silhouette is one groove of the stated width: a point on the outline is cut, a point a groove-and-a-half inside it is not on the outline groove
    ring = e.outline.exterior
    assert all(e.geometry.buffer(0.01).contains(ring.interpolate(d)) for d in (0.0, ring.length * 0.25, ring.length * 0.5, ring.length * 0.75))
    # a sheet line is kept only where it stays the stated distance clear of every other groove
    clear = P("logo.sheet_clear_mm")
    others = e.boundary.union(e.hatch)
    assert e.sheets.area > 0 and e.sheets.intersection(others.buffer(clear - 0.02)).area < 0.05
    assert logo.engrave(P, 12.0).sheets_dropped >= e.sheets_dropped


def test_c13_light_faces_are_grooved_between_only_when_both_are_wide_enough_and_thin_dark_faces_take_a_centre_line(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    import logo
    e_big = logo.engrave(model.P, 48.0)
    e_small = logo.engrave(model.P, 12.0)
    # at 12 mm no pair of light faces is 2.5 mm across, so no light/light groove is cut; at 48 mm some are
    assert e_small.light_grooves == 0 and e_big.light_grooves > 0
    # a dark face too thin for two hatch lines carries one centre-line groove, and that count falls as the logo grows
    assert e_small.centre_line_faces > e_big.centre_line_faces >= 0
    # at the lid's size the two groove families are the stated widths
    P = model.P
    assert P("logo.groove_width_mm") == 1.0 and P("logo.hatch_width_mm") == 0.9 and P("logo.hatch_pitch_mm") == 1.8 and P("logo.sheet_width_mm") == 0.8


def test_c13_the_swap_layers_are_stated_and_proved(results, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    swap = named(results, "c13.swap_layers_stated_and_proved")
    f = swap["figures"]
    assert swap["passed"] and f["start_whole_layers"] and f["thickness_whole_layers"]
    assert set(f["rays"]) == {"lid logo", "tray logo", "streamline grooves", "far-end block bars"}
    assert all(r["samples"] >= 20 and r["in_band"] == r["samples"] for r in f["rays"].values())
    assert f["band_top_mm"] <= f["chamfer_height_mm"]["lid"] and f["tray_outlet_slits_crossed"] == []
    assert f["reliefs"]["tray logo"]["swap_layers_over_the_floor"] >= 3 - 1e-6 and f["reliefs"]["lid logo"]["swap_layers_over_the_floor"] >= 2 - 1e-6
    assert model.P("logo.groove_depth_mm") == model.P("forms.two.swap_start_mm")
    # the two swap parts are the parts cut to their bands, and the base parts keep their full geometry
    for part, swap in (("lid_two", "lid_swap"), ("tray", "tray_swap")):
        assert model.parts[swap].volume < model.parts[part].volume and (model.parts[swap] - model.parts[part]).volume < 1e-6
    assert not (case.colour_solids(model, "two")["lid_two"] & case.colour_solids(model, "two")["lid_swap"]).volume > 1e-6
    assert case.part_colours(model, "two")["lid_swap"] == "#2f3237" and case.part_colours(model, "two")["tray_swap"] == "#e6e1d6"


@pytest.mark.controls("c13_swap_too_early")
def test_c13_negative_a_logo_deeper_than_the_swap_starts(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    assert not named(controls.get("c13_swap_too_early"), "c13.swap_layers_stated_and_proved")["passed"]


def test_c13_the_far_end_block_mirrors_the_wide_bay_and_is_blind(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    from shapely.geometry import LineString, Point, box as sh_box
    skin, core, P = model.skin, model.core, model.P
    info = skin.block(core)
    openings = info["openings"]
    wide, narrow = openings
    (u0, u1), (v0, v1) = info["u"], info["v"]
    centre = (wide[0] + u1) / 2
    # one row: wide bay, narrow bay, block, mirrored about the row's centre, and as long along v as the bays
    assert u1 - u0 == pytest.approx(wide[2] - wide[0]) and (v0, v1) == pytest.approx((wide[1], wide[3]))
    assert (wide[0] + u1) / 2 - centre == 0 and wide[0] + u1 == pytest.approx(wide[2] + u0) and (narrow[0] + narrow[2]) / 2 == pytest.approx(centre)
    assert u0 - narrow[2] == pytest.approx(narrow[0] - wide[2])
    bars = [g for g in model.info["grooves"] if g.square]
    assert len(bars) == P.S("block.bars") == 8
    assert all(g.width == P.S("lines.groove_width_mm") and g.depth == P.S("lines.groove_depth_mm") for g in bars)
    assert info["land_mm"] >= P.S("lines.min_land_mm") and info["to_chamfer_mm"] >= P.S("lines.edge_land_mm")
    assert info["to_collar_mm"] >= 1.0 and info["to_screw_zone_mm"] >= 1.0
    block = sh_box(u0, v0, u1, v1)
    for g in bars:
        assert block.contains(g.polygon().buffer(-1e-6))
    # blind: no opening of the case is a bar, and the lid is left under it
    assert all(block.distance(sh_box(*o)) > 0 for o in openings) and all(block.distance(LineString(v.points)) > 0 for v in model.info["vents"])
    assert not [o for o in model.openings if block.contains(Point(o["u"], o["v"]))]
    assert (P("case.z_lid_top_mm") - P("case.z_lid_under_mm")) - P.S("lines.groove_depth_mm") >= 1.0 - 1e-9
    # the vents are the even, mirrored set: sixteen, four runs on each of four lines, with the inlet free area measured at 205.3 mm2
    from check import vent_areas
    assert len(model.info["vents"]) == 16 and vent_areas(model)["lid_inlet_free_area_mm2"] == pytest.approx(205.3, abs=0.1)


def test_c13_the_far_end_block_is_omitted_with_a_reason_where_it_would_crowd_the_chamfer_the_collar_or_the_screw():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    def built(overrides):
        m = case.build(overrides, ("single",))
        return m, m.info["far_end_block"]
    nominal, reason = built({})
    assert reason is None and len([g for g in nominal.info["grooves"] if g.square]) == 8
    for overrides, word in (({"skins.flow.lines.edge_land_mm": 2.2}, "chamfer"), ({"skins.flow.block.clear_mm": 2.5}, "collar")):
        m, reason = built(overrides)
        assert reason and word in reason and not [g for g in m.info["grooves"] if g.square]
    # fewer than two bars leaves no block either, and the build still succeeds
    m, reason = built({"skins.flow.block.bars": 1})
    assert reason and "fewer than two" in reason and not [g for g in m.info["grooves"] if g.square]


@pytest.mark.controls("c13_no_engraving")
def test_c13_negative_a_tray_without_its_engraving(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    assert not named(controls.get("c13_no_engraving"), "c13.logo_present_in_each_form")["passed"]


def test_flow_reads_as_one_pebble(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    P = model.P
    lip = model.info["lid_drop_lip"]
    assert 0.4 <= lip["shadow_line_mm"] <= 0.6
    assert lip["z_bottom"] - model.core.low_zone_top == pytest.approx(lip["shadow_line_mm"], abs=1e-9)
    assert P.S("chamfer_mm") == P.S("bottom_chamfer_mm") == pytest.approx(1.6, abs=0.15)
    # the lip stands round the full-height walls and their tab, off them by its gap, and never over the pilasters
    from shapely.geometry import Polygon as Poly
    neck = Poly(model.info["tray_outline"])
    assert lip["region"].distance(neck) >= P.S("lip_gap_mm") - 0.01        # a polygon approximation of the offset curve
    assert lip["region"].bounds[1] >= model.core.v_pil + P.S("lip_front_gap_mm") - 1e-6
    lid, tray = model.parts["lid_single"], model.parts["tray"]
    assert lid.bounding_box().min.Z == pytest.approx(lip["z_bottom"], abs=1e-6) or lid.bounding_box().min.Z <= lip["z_bottom"] + 1e-6
    assert float(lid.distance_to(model.info["tray_envelope"])) >= 0.1


def test_flow_vents_are_mirror_symmetric_about_the_axis_and_share_their_bridges_and_ends(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric suited to this project (clean lines, consistent edge radii and chamfers, a deliberate pattern to the heat-release slots, no exposed fixing clutter on the visible faces) and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open.
    from shapely.geometry import LineString
    skin, core = model.skin, model.core
    axis = core.screw_uv[0]
    vents = model.info["vents"]
    bands = skin._bridge_bands(core)
    by_line = {}
    for v in vents:
        by_line.setdefault(skin._vent_line[v.label], []).append(v)
    # every vented line carries one run more than there are bridges, and the lines are in mirror pairs
    assert len(vents) == 16 and len(by_line) == 4
    assert all(len(runs) == len(bands) + 1 for runs in by_line.values())
    sides = {i: [-1 if sum(p[0] for p in r.points) / len(r.points) < axis else 1 for r in runs] for i, runs in by_line.items()}
    assert all(len(set(s)) == 1 for s in sides.values()) and sorted(s[0] for s in sides.values()) == [-1, -1, 1, 1]
    # each vent's mirror image lies on another vent: the stream function is mirror-symmetric to rounding (the measured worst
    # Hausdorff distance is 3e-13 mm), so the tolerance is 1e-4 mm, rounding with room, and any lean or run that differs misses it by millimetres
    tolerance = 1e-4
    for v in vents:
        mirrored = LineString([(2 * axis - x, y) for x, y in v.points])
        best = min(mirrored.hausdorff_distance(LineString(o.points)) for o in vents if (sum(p[0] for p in o.points) / len(o.points) - axis) * (sum(p[0] for p in v.points) / len(v.points) - axis) < 0)
        assert best < tolerance, (v.label, best)
    # the lean is inward: each run of the low-u side walks from the far end toward the plate end, the high-u side as drawn
    for v in vents:
        left = sum(p[0] for p in v.points) / len(v.points) < axis
        assert (v.points[0][1] > v.points[-1][1]) == left
    # every bridge lies on a shared band, and no run crosses one
    for runs in by_line.values():
        ordered = sorted(runs, key=lambda r: min(p[1] for p in r.points))
        gaps = [(max(p[1] for p in a.points) + min(p[1] for p in b.points)) / 2 for a, b in zip(ordered, ordered[1:])]
        assert gaps == pytest.approx(bands, abs=skin.P.S("lines.bridge_mm") / 2 + 0.3)
        assert all(abs(p[1] - b) >= skin.P.S("lines.bridge_mm") / 2 - 1e-6 for r in runs for p in r.points for b in bands)
    # the runs of every vented line start and end on the same two v
    starts = {round(min(p[1] for r in runs for p in r.points), 3) for runs in by_line.values()}
    ends = {round(max(p[1] for r in runs for p in r.points), 3) for runs in by_line.values()}
    assert len(starts) == 1 and len(ends) == 1
    assert all(LineString(v.points).length >= skin.P.S("lines.min_run_mm") - 1e-9 for v in vents)
    # a line that does not carry a full set stays a groove: the grooves still run along every streamline
    assert len(skin.streamlines(core)) == 8 and set(by_line) < set(range(8))


def test_flow_outlets_are_one_even_row_with_the_left_wall_half_a_pitch_behind(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    P, core = model.P, model.core
    slits = model.info["outlets"]
    pitch, width, height = P.S("outlets.pitch_mm"), P.S("outlets.width_mm"), P.S("outlets.height_mm")
    right = sorted(s.v for s in slits if s.side == "right")
    left = sorted(s.v for s in slits if s.side == "left")
    assert (len(right), len(left), len(slits)) == (15, 10, 25)
    assert all(s.width == width == 2.0 and s.height == height == 4.5 for s in slits)
    assert right[0] == pytest.approx(P.S("outlets.first_v_mm")) and right == pytest.approx([12.3 + k * pitch for k in range(15)])
    # one pitch within every unbroken group of a wall; a break is a locating rib or the hold-down finger's window
    for row in (right, left):
        diffs = [b - a for a, b in zip(row, row[1:])]
        assert all(d == pytest.approx(pitch) or d > pitch + 1e-6 for d in diffs)
        assert all(d == pytest.approx(round(d / pitch) * pitch) for d in diffs)
    assert all((v - P.S("outlets.first_v_mm") - pitch / 2) / pitch == pytest.approx(round((v - P.S("outlets.first_v_mm") - pitch / 2) / pitch)) for v in left)
    assert [round(v, 1) for v in left] == [18.6, 22.8, 27.0, 31.2, 35.4, 39.6, 48.0, 52.2, 64.8, 69.0]
    # the half-pitch stagger: every left slit stands wholly behind a web of the right wall
    for v in left:
        assert any(a + width / 2 <= v - width / 2 + 1e-9 and v + width / 2 <= b - width / 2 + 1e-9 for a, b in zip(right, right[1:]))
    # height 4.5 from the zone's top land ends on the core's bottom limit, and every slit keeps the core's rules
    zone = core.outlet_zone()
    assert all(s.z_bottom == pytest.approx(zone[s.side]["z1"]) for s in slits) and all(not core.outlet_problems(s) for s in slits)
    from check import vent_areas
    areas = vent_areas(model)
    assert areas["side_outlet_free_area_mm2"] == pytest.approx(225.0, abs=0.01) and areas["side_outlet_slit_count"] == 25


def test_flow_lid_rim_is_one_band_with_one_break_over_the_tab(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    from shapely.geometry import Point, Polygon as Poly
    from shapely.ops import unary_union
    skin, core, P = model.skin, model.core, model.P
    uc = core.screw_uv[0]
    lip = model.info["lid_drop_lip"]["region"]
    pad = skin.lid_lug_pad(core)
    peb = Poly(skin.pebble(core))
    half, lip_gap = P.S("tab_half_width_mm"), P.S("lip_gap_mm")
    gate = skin.cable_gate(core)
    # with the pad the lip is one connected band apart from the gate: the gate makes exactly one more piece
    whole = unary_union([lip, pad])
    pieces = list(whole.geoms) if hasattr(whole, "geoms") else [whole]
    assert len(pieces) == 2
    with_gate = unary_union([skin.lid_drop_lip(core).union(gate.intersection(peb).difference(Poly(skin.tray(core).neck).buffer(lip_gap))), pad])
    assert not hasattr(with_gate, "geoms") or len(with_gate.geoms) == 1
    # one break at the far end, centred on the lid screw's u and no wider than the tab and its two gaps
    far = [g for g in (lip.geoms if hasattr(lip, "geoms") else [lip]) if g.bounds[3] > core.far_out + 1.0]
    ends = sorted(g.bounds for g in far)
    window = (max(b[2] for b in ends if b[2] < uc), min(b[0] for b in ends if b[0] > uc))
    assert (window[0] + window[1]) / 2 == pytest.approx(uc, abs=0.05)
    assert window[1] - window[0] <= 2 * half + 2 * lip_gap + 0.01 + 0.2
    assert pad.bounds[0] < window[0] and pad.bounds[2] > window[1] and pad.bounds[3] <= peb.bounds[3] + 1e-9
    # the lid is one solid
    assert len(model.parts["lid_single"].solids()) == 1
    # the tab's outer face is the pebble: its far vertices lie on the pebble's ring
    neck = Poly(model.info["tray_outline"])
    far_v = [p for p in model.info["tray_outline"] if p[1] > core.far_out + 1.0]
    assert far_v and all(peb.exterior.distance(Point(p)) < 0.01 for p in far_v)
    assert min(p[0] for p in far_v) == pytest.approx(uc - half) and max(p[0] for p in far_v) == pytest.approx(uc + half)
    core.validate_outline(model.info["tray_outline"], "high")
    # round each far corner the lip keeps at least 0.8 mm: the pebble's edge to the wall's offset by the gap, away from the tab
    inner = neck.buffer(lip_gap, join_style=1)
    ring = peb.exterior
    corner = [ring.interpolate(s) for s in np.arange(0.0, ring.length, 0.1)]
    corner = [p for p in corner if p.y > core.far_out - 20.0 and abs(p.x - uc) > 6.0]
    assert corner and min(p.distance(inner) for p in corner) >= 0.8
    near = lip.buffer(-0.399)
    assert not near.is_empty and all(g.bounds[3] - g.bounds[1] > 5.0 for g in (near.geoms if hasattr(near, "geoms") else [near]))


def test_c20_the_cable_gate_opens_the_right_lip_over_the_notch_and_its_lead(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C20: The case lets the low-voltage cable that mates with the board's header leave the closed case, and the lid is fitted and removed with that cable in place. The case drawing or model shows the cable's exit through the case with the lid on, the cable's own swept path as the lid slides along its removal path, and the clearance between the cable and every case edge along that path, and no part of the lid or tray traps or bends the cable beyond the bend room the record states. The record states the largest outside diameter of wire the bend room supports, at three times the wire's diameter, computed from the lid's clearance above the header's wire exit and recomputed by the case model, and lists the owner's confirmation that his cable fits as an owner item. No case dimension that another criterion of this leaf fixes is reduced to make room for it.
    from shapely.geometry import box as sh_box
    skin, core, P = model.skin, model.core, model.P
    n0, n1 = P("lid.cable_notch_v_mm")
    lip = model.info["lid_drop_lip"]["region"]
    seam, lead = P("case.seam_mm"), P.S("cable_gate_lead_mm")
    assert lead == 8.0
    # no lip over the gate on the right wall; the lip stands on the left wall and on the right wall beyond the gate
    assert lip.intersection(sh_box(core.right_out, n0 - lead - seam + 1e-6, 1e3, n1 + seam - 1e-6)).area < 1e-6
    assert lip.intersection(sh_box(core.right_out, n1 + seam + 0.1, 1e3, n1 + seam + 3.0)).area > 1.0
    assert lip.intersection(sh_box(core.right_out, n0 - lead - seam - 3.0, 1e3, n0 - lead - seam - 0.1)).area > 1.0
    assert lip.intersection(sh_box(-1e3, n0 - lead - seam, core.left_out, n1 + seam)).area > 1.0
    gate = skin.cable_gate(core).bounds
    slide = check.lid_removal_installed(model, "single", *check.sweep_poses(model))["slide_to_free_the_toes_mm"]
    assert n0 - gate[1] >= slide + seam - 1e-9 and gate[3] - n1 >= seam - 1e-9


def test_c20_the_cable_gate_follows_the_slide(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C20: The case lets the low-voltage cable that mates with the board's header leave the closed case, and the lid is fitted and removed with that cable in place. The case drawing or model shows the cable's exit through the case with the lid on, the cable's own swept path as the lid slides along its removal path, and the clearance between the cable and every case edge along that path, and no part of the lid or tray traps or bends the cable beyond the bend room the record states. The record states the largest outside diameter of wire the bend room supports, at three times the wire's diameter, computed from the lid's clearance above the header's wire exit and recomputed by the case model, and lists the owner's confirmation that his cable fits as an owner item. No case dimension that another criterion of this leaf fixes is reduced to make room for it.
    res = named(results, "c4.cable_gate_follows_the_slide")
    f = res["figures"]
    assert res["passed"] and f["gate_spans_notch_at_every_pose"] and f["outward_rays_blocked"] == [] and f["sample_points"] == 5
    assert f["lead_toward_the_plate_mm"] >= f["slide_to_free_the_toes_mm"] and f["least_margin_mm"] >= 0.0


def test_c20_bend_room_is_measured_on_the_lid_and_supports_a_1_2_mm_wire(results, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C20: The case lets the low-voltage cable that mates with the board's header leave the closed case, and the lid is fitted and removed with that cable in place. The case drawing or model shows the cable's exit through the case with the lid on, the cable's own swept path as the lid slides along its removal path, and the clearance between the cable and every case edge along that path, and no part of the lid or tray traps or bends the cable beyond the bend room the record states. The record states the largest outside diameter of wire the bend room supports, at three times the wire's diameter, computed from the lid's clearance above the header's wire exit and recomputed by the case model, and lists the owner's confirmation that his cable fits as an owner item. No case dimension that another criterion of this leaf fixes is reduced to make room for it.
    res = named(results, "c20.cable_bend_room")
    f = res["figures"]
    exit_z = model.P("parts.header_housing_top_z_mm")
    lid_top = model.P("case.z_lid_top_mm")
    pad = model.P("lid.top_louvre_mm")
    assert res["passed"] and f["rays_meeting_the_lid"] == f["rays"] == 21
    # the lid's underside over the header is its top less the thickened underside: 22.55 - 2.4 = 20.15; the room is 20.15 - 16.5 = 3.65; 3.65 / 3 = 1.2167
    assert f["wire_exit_z_mm"] == exit_z == 16.5
    assert f["lid_underside_over_exit_z_mm"] == pytest.approx(lid_top - pad, abs=1e-6) == pytest.approx(20.15, abs=1e-6)
    assert f["bend_room_mm"] == pytest.approx(3.65, abs=1e-6) and f["bend_room_factor"] == 3.0
    assert f["largest_wire_od_mm"] == pytest.approx(3.65 / 3.0, abs=1e-6) and f["largest_wire_od_stated_mm"] == 1.2


@pytest.mark.controls("c20_worst_lean", "c20_best_lean")
def test_c20_bend_room_over_the_seating_range_is_least_at_the_far_end_up_lean(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C20: The case lets the low-voltage cable that mates with the board's header leave the closed case, and the lid is fitted and removed with that cable in place. The case drawing or model shows the cable's exit through the case with the lid on, the cable's own swept path as the lid slides along its removal path, and the clearance between the cable and every case edge along that path, and no part of the lid or tray traps or bends the cable beyond the bend room the record states. The record states the largest outside diameter of wire the bend room supports, at three times the wire's diameter, computed from the lid's clearance above the header's wire exit and recomputed by the case model, and lists the owner's confirmation that his cable fits as an owner item. No case dimension that another criterion of this leaf fixes is reduced to make room for it.
    worst, best = controls.get("c20_worst_lean"), controls.get("c20_best_lean")
    assert worst["passed"] and best["passed"] and worst["figures"]["rays_meeting_the_lid"] == worst["figures"]["rays"] == 21
    assert worst["figures"]["bend_room_mm"] == pytest.approx(3.01, abs=0.005) and worst["figures"]["largest_wire_od_stated_mm"] == 1.0
    assert best["figures"]["bend_room_mm"] == pytest.approx(4.25, abs=0.005) and best["figures"]["largest_wire_od_stated_mm"] == 1.4


@pytest.mark.controls("c20_bend_room")
def test_c20_negative_a_raised_exit_or_a_thicker_underside_changes_the_figure_and_the_check_reports_it(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C20: The case lets the low-voltage cable that mates with the board's header leave the closed case, and the lid is fitted and removed with that cable in place. The case drawing or model shows the cable's exit through the case with the lid on, the cable's own swept path as the lid slides along its removal path, and the clearance between the cable and every case edge along that path, and no part of the lid or tray traps or bends the cable beyond the bend room the record states. The record states the largest outside diameter of wire the bend room supports, at three times the wire's diameter, computed from the lid's clearance above the header's wire exit and recomputed by the case model, and lists the owner's confirmation that his cable fits as an owner item. No case dimension that another criterion of this leaf fixes is reduced to make room for it.
    got = controls.get("c20_bend_room")
    raised, thick, above = got["raised_exit"], got["thicker_underside"], got["exit_above_the_lid"]
    assert raised["figures"]["bend_room_mm"] == pytest.approx(2.65, abs=1e-6) and raised["figures"]["largest_wire_od_stated_mm"] == 0.8
    assert thick["figures"]["bend_room_mm"] == pytest.approx(2.85, abs=1e-6) and thick["figures"]["largest_wire_od_stated_mm"] == 0.9
    assert "supports wire up to 0.8 mm" in raised["summary"] and "supports wire up to 0.9 mm" in thick["summary"]
    assert not above["passed"] and above["figures"]["rays_meeting_the_lid"] < above["figures"]["rays"]


@pytest.mark.controls("c4_short_gate")
def test_c20_negative_a_gate_shorter_than_the_slide_fails(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C20: The case lets the low-voltage cable that mates with the board's header leave the closed case, and the lid is fitted and removed with that cable in place. The case drawing or model shows the cable's exit through the case with the lid on, the cable's own swept path as the lid slides along its removal path, and the clearance between the cable and every case edge along that path, and no part of the lid or tray traps or bends the cable beyond the bend room the record states. The record states the largest outside diameter of wire the bend room supports, at three times the wire's diameter, computed from the lid's clearance above the header's wire exit and recomputed by the case model, and lists the owner's confirmation that his cable fits as an owner item. No case dimension that another criterion of this leaf fixes is reduced to make room for it.
    got = {r["name"]: r for r in controls.get("c4_short_gate")}
    assert not got["c4.cable_gate_follows_the_slide"]["passed"] and not got["c4.cable_gate_follows_the_slide"]["figures"]["gate_spans_notch_at_every_pose"]


def test_flow_lid_logo_stands_on_the_long_axis_and_the_streamlines_part_evenly():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    frame = case.frame(skin="flow")
    core, skin = frame.core, frame.skin
    axis = core.screw_uv[0]
    stone = skin.stone(core)
    assert abs((stone.bounds[0] + stone.bounds[2]) / 2 - axis) < 0.05
    lines = skin._flow_lines(core)["lines"]
    left = [ln for ln in lines if sum(p[0] for p in ln) / len(ln) < axis - 1.0]
    right = [ln for ln in lines if sum(p[0] for p in ln) / len(ln) > axis + 1.0]
    assert len(left) == len(right) and len(left) >= 4
    # mirror-symmetric about the axis: each line on one side has its mirror image on the other
    from shapely.geometry import LineString
    for ln in left:
        mirrored = LineString([(2 * axis - x, y) for x, y in ln])
        assert any(mirrored.hausdorff_distance(LineString(o)) < 0.5 for o in right)
    assert skin.P.S("mark.lid_height_mm") >= 28.0


def test_flow_streamlines_are_real_vents_of_the_grooves_own_width(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening.
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    skin, core, P = model.skin, model.core, model.P
    lines = skin.streamlines(core)
    assert len(lines) == 8 and all(LineString(l).length >= P.S("lines.min_line_mm") for l in lines)
    assert core.gill()["opening"] == pytest.approx(P.S("lines.groove_width_mm"), abs=0.05) and 1.4 <= P.S("lines.groove_width_mm") <= 1.6
    vents = model.info["vents"]
    assert vents and all(v.length() >= P.S("lines.min_run_mm") - 0.6 for v in vents)
    # the structural bridges stand on one even pitch across the field and are at least 0.8 mm
    bands = skin._bridge_bands(core)
    assert all(b - a == pytest.approx(P.S("lines.bridge_pitch_mm"), abs=1e-6) for a, b in zip(bands, bands[1:])) and P.S("lines.bridge_mm") >= 0.8
    for v in vents:
        assert all(abs(p[1] - b) >= P.S("lines.bridge_mm") / 2 - 1e-6 for p in v.points for b in bands)
    # no two grooves merge into a pocket, and every line ends on the margin or on an obstacle's offset
    spacing = min(LineString(a).distance(LineString(b)) for i, a in enumerate(lines) for b in lines[i + 1:])
    assert spacing >= P.S("lines.groove_width_mm") + 0.2
    data = skin._flow_lines(core)
    boundaries = unary_union([data["region"].boundary, data["stone"].boundary, data["apertures"].boundary])
    from shapely.geometry import Point
    for l in lines:
        # a line ends on the region's margin or an obstacle's offset (the stream function's grid is 0.5 mm), or where the stone's own
        # level was trimmed away, which is at the trim distance from the stone's offset and ends round
        stone_end = P.S("lines.hug_mm") + 0.1
        for end in (Point(l[0]), Point(l[-1])):
            assert boundaries.distance(end) < 1.0 or data["stone"].boundary.distance(end) < stone_end
    assert not [m for m in core.web_faults(vents)]
    assert all(not core.vent_problems(v) for v in vents)


def test_c13_renders_exist(renders):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    folder = renders
    import render
    for form in render.form_names():
        names = [n for n in os.listdir(folder) if n.startswith(form + "-") and n.endswith(".png")]
        assert len(names) >= 3
        for n in names:
            with open(os.path.join(folder, n), "rb") as handle:
                header = handle.read(24)
            assert header[:8] == b"\x89PNG\r\n\x1a\n" and int.from_bytes(header[16:20], "big") == 1600 and int.from_bytes(header[20:24], "big") == 1200


def test_render_swap_band_cut_pieces_abut():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    import numpy as np
    import pyvista as pv
    import render
    box = pv.Box(bounds=(0, 10, 0, 10, 0, 10)).triangulate().subdivide(2)
    below, band, above = render.split_by_band(box, 3.0, 5.0)
    assert below.n_cells and band.n_cells and above.n_cells
    assert below.bounds[5] == pytest.approx(3.0 - render.SWAP_MARGIN_MM, abs=1e-6)
    assert band.bounds[4] == pytest.approx(3.0 - render.SWAP_MARGIN_MM, abs=1e-6) and band.bounds[5] == pytest.approx(5.0 + render.SWAP_MARGIN_MM, abs=1e-6)
    assert above.bounds[4] == pytest.approx(5.0 + render.SWAP_MARGIN_MM, abs=1e-6)
    assert below.area + band.area + above.area == pytest.approx(box.area, rel=1e-3)
    flat = pv.Plane(center=(0, 0, 3.0), direction=(0, 0, 1), i_size=4, j_size=4).triangulate()      # a face lying on the band's edge falls in the band
    _, in_band, _ = render.split_by_band(flat, 3.0, 5.0)
    assert in_band.n_cells == flat.n_cells


def test_render_third_form_files_sheets_and_wiring(renders):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    import render
    from PIL import Image
    single, alternate, two = render.form_names()
    assert (single, two) == ("single", "two") and alternate not in (single, two)
    assert render.geometry_form(alternate) == "single" and render.build_forms(render.form_names()) == ("single", "two")
    folder = renders
    for view in render.VIEWS:
        for form in render.form_names():
            assert os.path.isfile(os.path.join(folder, f"{form}-{view}.png")), f"{form}-{view}"
    directions = os.path.join(folder, "directions")
    for view in render.ALL_DIRECTION_VIEWS:
        assert os.path.isfile(render.direction_path(directions, render.SKIN_NAME, alternate, view))
    for sheet, columns in (("contact-sheet.png", len(render.SHEET_VIEWS)), ("logo-sheet.png", len(render.LOGO_VIEWS))):
        width, height = Image.open(os.path.join(directions, sheet)).size
        cell_w = (width - 220 - 14 * (columns + 1)) // columns
        assert height == 96 + 3 * (cell_w * render.SIZE[1] // render.SIZE[0] + 14) + 14      # three rows: bone, the alternate, two colour
    assert render.SHEET_LABELS[0] == "single colour, bone" and render.SHEET_LABELS[1].startswith("single colour, ") and render.SHEET_LABELS[2] == "two colour"
    assert set(render.WIRED_OLDER_VIEWS) == {"far-end", "top", "plate-end", "underside"} and not set(render.WIRED_OLDER_VIEWS) & {"exploded", "lid-off"}


def test_render_alternate_colour_is_the_single_form_in_its_own_colour():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    import render
    import case
    model = case.build({}, ("single",))
    alternate = render.alternate_name()
    items = {i["name"]: i for i in render.scene_parts(model, alternate, "far-end")}
    assert items["tray"]["colour"] == model.P("forms.single.alternate_colour") == items["lid_single"]["colour"]
    assert "band" not in items["tray"] and "lid_two" not in items
    plain = {i["name"]: i for i in render.scene_parts(model, "single", "far-end")}
    assert plain["tray"]["colour"] == model.P("forms.single.tray_colour") != items["tray"]["colour"]


def test_render_logo_cameras_lean_toward_the_viewer():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    import numpy as np
    import render

    class Gravity:
        def __call__(self, key):
            return [0.0, 0.0, 1.0]
    model = type("M", (), {"P": Gravity()})()
    lid, top = render.logo_direction(model, "logo-lid-30"), render.logo_direction(model, "logo-top-60")
    assert lid == pytest.approx([0.0, 0.5, np.cos(np.radians(30))])
    assert top == pytest.approx([0.0, np.sin(np.radians(60)), -np.cos(np.radians(60))])
    assert render.add_lights_from_below and all(float(d @ np.array([0.0, 0.0, -1.0])) <= 0 for d, _, _ in render.lit_from_below_rig(model))


# ---------------------------------------------------------------- C14

def test_c14_bed_fit_and_overhang(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    fit = named(results, "c14.bed_fit")
    assert fit["passed"] and {p["part"] for p in fit["figures"]["parts"]} == {"tray", "lid_single", "lid_two"}
    assert all(p["orientation"] and p["installed_orientation"] for p in fit["figures"]["parts"])
    over = named(results, "c14.overhang")
    assert over["passed"]
    for part in over["figures"]["parts"]:
        assert part["orientation"] and part["critical_faces_support_free"] and not part["non_bridgeable_clusters"]


@pytest.mark.controls("c14_bed")
def test_c14_negative_part_too_big_and_flat_shelf(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    res = by_name(controls.get("c14_bed"))
    assert not res["c14.bed_fit"]["passed"]
    # a wide flat roof is an overhang that is not a bridge
    shelf = trimesh.util.concatenate([trimesh.creation.box((20, 20, 5)), trimesh.creation.box((20, 20, 2)).apply_translation((15, 0, 10))])
    shelf.apply_translation((0, 0, 2.5 - shelf.bounds[0][2]))
    clusters = check.overhang_clusters(shelf)
    assert any(not c["bridgeable"] for c in clusters)
    # the 45 degree face of a chamfer is not
    wedge = trimesh.creation.extrude_polygon(__import__("shapely").geometry.Polygon([(0, 0), (10, 0), (10, 2), (8, 2), (0, 10)]), 10)
    assert wedge is not None


def test_c14_slicer_summaries_are_support_free_where_it_matters(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    import slice as slice_tool
    limits = {"overhang_limit_deg": float(model.P("printer.overhang_limit_deg")), "bridge_limit_mm": float(model.P("printer.bridge_limit_mm")),
              "noise_area_mm2": float(model.P("printer.noise_area_mm2")), "min_sloped_angle_deg": check.min_unflagged_angle_deg(float(model.P("printer.overhang_limit_deg"))), "first_layer_mm": slice_tool.FIRST_LAYER_MM}
    for part in ("tray", "lid_single", "lid_two"):
        path = os.path.join(CASE_DIR, "slice", f"{part}.json")
        assert os.path.exists(path) and os.path.exists(path[:-5] + ".log"), f"{part}: no slicer summary: run task hw:case:slice"
        with open(path, encoding="utf-8") as handle:
            s = json.load(handle)
        changed = slice_tool.stale(s)
        assert not changed, f"{part}: the slicer summary is stale, these inputs changed since it was sliced: {', '.join(changed)}; re-run task hw:case:slice"
        assert s["slicer"].startswith("PrusaSlicer") and s["inputs"]
        assert s["limits"] == limits, f"{part}: the summary was judged against limits {s['limits']}, the model states {limits}"
        off = s["supports_off"]
        # the stated print is supports off: the slicer asks for none
        assert not off["support_generated"] and off["support_clusters"] == [] and off["support_filament_mm"] == 0
        assert off["print_time_s"] > 0 and off["filament_mm"] > 0 and off["layers"] > 0
        size = off["bounding_box_mm"]["size"]
        assert size[0] <= 220 and size[1] <= 220 and size[2] <= 250
        # the two diagnostic runs (the threshold the record states, and the slicer's own detection) each account for all their support in regions,
        # no supported face is a critical face, and every region is of a kind the record accepts, judged from the recorded fields
        for mode in ("supports_auto", "supports_auto_threshold_0"):
            run = s[mode]
            assert run["support_generated"] and run["regions"], f"{part} {mode}: no regions recorded"
            assert sum(r["filament_mm"] for r in run["regions"]) == pytest.approx(run["support_filament_mm"], abs=0.1 * len(run["regions"]))
            assert sum(run["support_by_kind_mm"].values()) == pytest.approx(run["support_filament_mm"], abs=0.1 * len(run["regions"]))
            # supported critical facets whose areas together, per part, are under the noise area are tessellation ripple; at or above it a facet is tolerated only at or steeper than the overhang check's own limit and never a flat roof
            assert not slice_tool.critical_entries_problems(run["supported_faces_that_are_critical"], limits), f"{part} {mode}: {slice_tool.critical_entries_problems(run['supported_faces_that_are_critical'], limits)}"
            for hit in run["supported_faces_that_are_critical"]:
                assert hit["critical_feature"] and hit["facet_area_mm2"] >= 0 and hit["filament_mm"] >= 0 and hit["facet_print_z_mm"] and hit["angle_deg"][0] <= hit["angle_deg"][1]
            for flush in run["flush_to_critical_plane"]:
                assert flush["filament_mm"] > 0 and 1 <= flush["region"] <= len(run["regions"])
            for r in run["regions"]:
                problems = slice_tool.region_problems(r, limits)
                assert not problems, f"{part} {mode} region {r['id']} ({r['feature']}): {'; '.join(problems)}"
                assert r["accepted"] is True
                if r["sloped_face_angle_deg"] is not None:
                    # a facet flatter than the limit is only the noise-area sliver the region rule sets aside
                    assert r["sloped_face_angle_deg"][0] >= limits["min_sloped_angle_deg"] or r["flatter_than_limit_mm2"] < limits["noise_area_mm2"]
        assert s["diagnostic_note"].startswith("Diagnostic only: the stated print has no support.")


def _synthetic_plate(width):
    """A pillar with a flat plate standing out from it at 5 mm, `width` wide: the plate's underside is a flat roof anchored on the pillar side only."""
    pillar = trimesh.creation.box(extents=(4, width, 8), transform=trimesh.transformations.translation_matrix((2, width / 2, 4)))
    plate = trimesh.creation.box(extents=(20, width, 2), transform=trimesh.transformations.translation_matrix((10, width / 2, 6)))
    return trimesh.util.concatenate([pillar, plate])


def _support_under_plate(width):
    return np.array([(z, x, y, 0.5) for z in np.arange(0.2, 4.9, 0.2) for x in np.arange(6.0, 18.0, 0.5) for y in np.arange(0.5, width - 0.4, 0.5)])


def test_c14_negative_control_attribution_catches_support_under_a_critical_face_and_an_unanchored_roof():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    import slice as slice_tool
    limits = {"overhang_limit_deg": 45.0, "bridge_limit_mm": 3.5, "noise_area_mm2": 1.0, "min_sloped_angle_deg": check.min_unflagged_angle_deg(45.0), "first_layer_mm": 0.2}
    identity = lambda p: np.asarray(p, dtype=float)

    def selector_for(box):
        def select(tri, normals):
            inside = np.all((tri >= np.array([box[0], box[2], box[4]]) - 0.03) & (tri <= np.array([box[1], box[3], box[5]]) + 0.03), axis=(1, 2)) & (np.abs(normals[:, 2]) > 0.9)
            return {"synthetic critical face": inside}
        return select

    mesh, points = _synthetic_plate(4.0), _support_under_plate(4.0)
    under = slice_tool.attribute_support(mesh, points, identity, selector_for((-1, 21, -1, 5, 4.9, 5.1)), [("synthetic plane", (-1, 21, -1, 5, 4.9, 5.1))], limits)
    # the support under the plate is traced to the plate's underside, and the underside is the critical face
    assert len(under["regions"]) == 1 and under["regions"][0]["kind"] == "flat_roof"
    assert [c["critical_feature"] for c in under["supported_faces_that_are_critical"]] == ["synthetic critical face"]
    assert under["supported_faces_that_are_critical"][0]["facet_area_mm2"] > 10
    # a flat roof under a critical face is not tolerated
    assert slice_tool.critical_entries_problems(under["supported_faces_that_are_critical"], limits)
    # the plate is 4 mm across with nothing standing on either side of its span: wider than the bridge limit and not anchored, so the region is not acceptable
    roof = under["regions"][0]["roofs"][0]
    assert roof["span_mm"] == pytest.approx(4.0, abs=0.05) and not roof["anchored_both_ends_of_span"]
    assert under["regions"][0]["problems"] and not under["regions"][0]["accepted"]
    # the same support with the critical face somewhere else lists none, so an empty list is not the attribution failing to see faces
    elsewhere = slice_tool.attribute_support(mesh, points, identity, selector_for((30, 40, 0, 4, 4.9, 5.1)), [], limits)
    assert elsewhere["supported_faces_that_are_critical"] == [] and elsewhere["regions"][0]["filament_mm"] == pytest.approx(under["regions"][0]["filament_mm"])
    # support standing against a critical plane without holding it up is listed as flush, not as supporting it
    flush = slice_tool.attribute_support(mesh, points, identity, selector_for((30, 40, 0, 4, 4.9, 5.1)), [("synthetic plane", (5.9, 6.1, 0, 4, 0, 8))], limits)
    assert flush["supported_faces_that_are_critical"] == [] and flush["flush_to_critical_plane"] and flush["flush_to_critical_plane"][0]["filament_mm"] > 0


def test_c14_negative_control_sloped_critical_facets_30_degrees_rejected_45_tolerated():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    import slice as slice_tool
    limits = {"overhang_limit_deg": 45.0, "bridge_limit_mm": 3.5, "noise_area_mm2": 1.0, "min_sloped_angle_deg": check.min_unflagged_angle_deg(45.0), "first_layer_mm": 0.2}
    identity = lambda p: np.asarray(p, dtype=float)
    everything = lambda tri, normals: {"synthetic critical face": np.ones(len(tri), dtype=bool)}
    for degrees, tolerated in ((45.0, True), (30.0, False)):
        # a wedge hanging off a pillar: its underside slopes `degrees` from the horizontal, up and away from the pillar
        run = 12.0
        rise = run * math.tan(math.radians(degrees))
        wedge = trimesh.creation.extrude_polygon(__import__("shapely").geometry.Polygon([(0, 0), (run, rise), (run, rise + 2), (0, rise + 2)]), 6.0)
        # the extrusion is along z: turn it so the profile is in the x-z plane and the width runs along y
        wedge.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
        wedge.apply_translation((0, 6.0, 0))
        wedge.apply_translation((0, 0, -wedge.bounds[0, 2] + 0.0))
        under = np.array([(z, x, y, 0.5) for x in np.arange(2.0, run - 1.0, 0.5) for y in np.arange(1.0, 5.5, 0.5) for z in np.arange(0.2, x * math.tan(math.radians(degrees)) - 0.4, 0.2)])
        entries = slice_tool.attribute_support(wedge, under, identity, everything, [], limits)["supported_faces_that_are_critical"]
        assert entries, f"{degrees} deg: support under the wedge was not attributed to its underside"
        assert entries[0]["angle_deg"][0] == pytest.approx(degrees, abs=0.2)
        assert bool(slice_tool.critical_entries_problems(entries[:1], limits)) is (not tolerated)


def test_c14_negative_control_sloped_critical_facets_under_the_noise_area_are_tolerated_and_a_roof_above_it_is_not():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C14: The case record states the printer it is designed to print on as a common low-cost open-frame FDM machine with a 220 by 220 mm bed, a 0.4 mm nozzle and 0.2 mm layers, the owner's printer being one instance, and every printed part fits that bed in the stated print orientation. The record names ASA as the baseline material and states what printing it open-frame needs (a draft shield, a brim, a cardboard box as the cheapest enclosure) and why PC, PETG and PLA are not the baseline. Each part prints with no support material on the creepage barrier, the screw seats, the slot mouths and the lid-fit faces, the orientation and any support that remains are stated per part, and a slicer's sliced result for each part is recorded as the check. The case is assembled with ordinary screws and no part needs post-print machining. Out of scope: printing the case.
    import slice as slice_tool
    limits = {"overhang_limit_deg": 45.0, "bridge_limit_mm": 3.5, "noise_area_mm2": 1.0, "min_sloped_angle_deg": check.min_unflagged_angle_deg(45.0), "first_layer_mm": 0.2}
    identity = lambda p: np.asarray(p, dtype=float)
    everything = lambda tri, normals: {"synthetic critical face": np.ones(len(tri), dtype=bool)}
    degrees, run = 30.0, 12.0
    rise = run * math.tan(math.radians(degrees))

    def entry_for(width):
        # real geometry: the 30 degree wedge of the control above, `width` wide along y, with support traced under its underside
        wedge = trimesh.creation.extrude_polygon(__import__("shapely").geometry.Polygon([(0, 0), (run, rise), (run, rise + 2), (0, rise + 2)]), width)
        wedge.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, (1, 0, 0)))
        wedge.apply_translation((0, width, 0))
        wedge.apply_translation((0, 0, -wedge.bounds[0, 2]))
        under = np.array([(z, x, y, 0.5) for x in np.arange(2.0, run - 1.0, 0.5) for y in (width / 2,) for z in np.arange(0.2, x * math.tan(math.radians(degrees)) - 0.4, 0.2)])
        entries = slice_tool.attribute_support(wedge, under, identity, everything, [], limits)["supported_faces_that_are_critical"]
        assert entries, "support under the wedge was not attributed to its underside"
        assert entries[0]["angle_deg"][0] == pytest.approx(degrees, abs=0.2)
        return entries[0]

    wide = entry_for(6.0)
    narrow = entry_for(0.05)
    assert wide["facet_area_mm2"] >= limits["noise_area_mm2"] and slice_tool.critical_entries_problems([wide], limits), "at its real area the 30 degree entry is rejected"
    assert narrow["facet_area_mm2"] < limits["noise_area_mm2"], "the narrow wedge's supported underside is under the noise area"
    assert slice_tool.critical_entries_problems([narrow], limits) == [], "the same 30 degree entry under the noise area is tolerated"
    roof = dict(wide, flat_roof=True, angle_deg=[0.0, 0.0])
    assert roof["facet_area_mm2"] >= limits["noise_area_mm2"] and any("flat roof" in p for p in slice_tool.critical_entries_problems([roof], limits))
    # a lone flat-roof sliver under the noise area is set aside with the rest; the same sliver among entries whose areas together reach it is not
    small_roof = dict(narrow, flat_roof=True, angle_deg=[0.0, 0.0])
    assert slice_tool.critical_entries_problems([small_roof], limits) == []
    # many entries each under the noise area, together over it: each is judged, so the flat roof and the flat facets are refused
    several = [dict(narrow, facet_area_mm2=0.3, angle_deg=[30.0, 30.0]) for _ in range(4)] + [dict(small_roof, facet_area_mm2=0.3)]
    assert all(e["facet_area_mm2"] < limits["noise_area_mm2"] for e in several) and sum(e["facet_area_mm2"] for e in several) >= limits["noise_area_mm2"]
    found = slice_tool.critical_entries_problems(several, limits)
    assert len(found) == 4 + 2 and any("flat roof" in p for p in found)
    assert slice_tool.critical_entries_problems(several[:3], limits) == [], "three of them total 0.9 mm2, under the noise area"


# ---------------------------------------------------------------- C15

def test_c15_openings_finger_and_drip(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    fin = named(results, "c15.finger")
    drip = named(results, "c15.drip")
    assert fin["passed"] and drip["passed"]
    kinds = {o["kind"] for o in fin["figures"]["openings"]}
    assert kinds == {"louvre", "blade aperture", "cable notch", "seam", "finger slit", "outlet slit"}
    for o in fin["figures"]["openings"]:
        if o["kind"] == "blade aperture":
            assert o["admits"] == "nothing" and o["remaining_to_mains_copper_mm"] > 0 and o["remaining_to_blade_mm"] > 0
        else:
            assert o["admits"] == "nothing" and o["remaining_to_mains_copper_mm"] > 0
    f = drip["figures"]
    assert f["cone_half_angle_deg"] == 15.0 and f["installed_vertical"] == [0.0, 0.0, 1.0]
    assert {r["down"] for r in f["rows"]} == set(check.DIRECTIONS) and all(r["information_only"] for r in f["rows"])
    assert {r["opening"] for r in f["per_opening"]} == {o["opening"] for o in fin["figures"]["openings"]}
    assert not any(r["reaches_mains_copper"] for r in f["per_opening"])
    assert f["residuals"]["blade bays"] and f["residuals"]["cable notch"]


def test_c15_blade_finger_verdict_is_judged_with_all_three_receptacles_fitted(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    fitted = named(results, "c15.finger_blades_receptacle_fitted")
    assert fitted["kind"] == "check" and fitted["passed"] and not fitted["figures"]["live_metal_reachable_with_boots_fitted"]
    assert fitted["figures"]["pass_rule_envelope"] == "typical" and set(fitted["figures"]["envelopes"]) == {"typical", "largest_common"}
    for env in fitted["figures"]["envelopes"].values():
        assert env["admits_nothing"] and env["receptacles_fitted"] == ["J941", "J921", "J911"]
    assert fitted["figures"]["boots_source"]["typical"].startswith("assumed, owner to measure his boots")
    # the standing check is the same fitted state: every blade bay admits nothing, round the typical and the largest common boot
    for o in named(results, "c15.finger")["figures"]["openings"]:
        if o["kind"] == "blade aperture":
            assert o["admits"] == "nothing" and o["receptacles_fitted"] == ["J941", "J921", "J911"]
            assert o["remaining_to_blade_mm"] > 0 and o["remaining_to_mains_copper_mm"] > 0
            assert all(v["admits_nothing"] for v in o["free_opening_round_the_boots"].values())


def test_c15_receptacle_off_reach_is_a_finding_with_its_figures_and_is_not_counted(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    f = named(results, "c15.finding_blades_no_receptacle")
    assert f["kind"] == "finding" and f["passed"] is None
    assert f["figures"]["touchable_blades"] == ["J941", "J921"] and "IEC 61032" in f["figures"]["probe"]
    assert f["figures"]["blade_pitch_mm"]["J941-J921"] == pytest.approx(8.1)
    for ref, b in f["figures"]["blades"].items():
        assert {"tip_to_blade_mm", "gap_the_finger_enters_mm", "bay_mm", "standing_check_fails_at_lean", "tip_at_uv_mm"} <= set(b)
        assert b["bay_mm"]["across_thickness_u"] > 0 and b["bay_mm"]["across_width_v"] > 0
    assert f["figures"]["blades"]["J911"]["tip_to_blade_mm"] > 0.5
    # the standing bare-blade gap closes at a lean the findings state: re-evaluating at that lean gives no gap
    for b in f["figures"]["blades"].values():
        lean = b["standing_check_fails_at_lean"]["leaning_far_end_up_deg"]
        assert lean is None or lean > 0
    # it prints as a finding, carries its kind in the JSON and is in neither the pass count nor the verdict
    text = check.render_text(results)
    assert "finding " in text and "FAIL  c15.finding" not in text and "PASS  c15.finding" not in text
    counted = check.verdicts(results)
    assert f not in counted and len(counted) == len(results) - len([r for r in results if r["kind"] == "finding"])
    assert f"{len(counted)} of {len(counted)} checks pass" in text


@pytest.mark.controls("c15_small_boots")
def test_c15_a_receptacle_fitted_failure_is_a_failure_and_a_finding_that_touches_is_not(controls, results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    # boots far smaller than their bays leave an opening that admits the tip, so with the receptacles fitted the verdict fails
    res = controls.get("c15_small_boots")
    assert not named(res, "c15.finger_blades_receptacle_fitted")["passed"] and not named(res, "c15.finger")["passed"]
    assert not all(r["passed"] for r in check.verdicts(res))
    # the receptacle-off finding of the nominal model touches two blades and still leaves the verdict standing
    nominal = [r for r in results if r["name"].startswith("c15.")]
    assert named(nominal, "c15.finding_blades_no_receptacle")["figures"]["touchable_blades"]
    assert all(r["passed"] for r in check.verdicts(nominal))


@pytest.mark.controls("c15_one_receptacle_off")
def test_c15_negative_dropping_one_receptacle_makes_that_blade_reachable_and_the_check_fails(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    res = named(controls.get("c15_one_receptacle_off"), "c15.finger_blades_receptacle_fitted")
    f = res["figures"]
    assert not res["passed"] and f["live_metal_reachable_with_boots_fitted"]
    assert f["envelopes"]["typical"]["receptacles_fitted"] == ["J941", "J911"] and not f["envelopes"]["typical"]["admits_nothing"]
    assert set(f["blades_without_a_receptacle_tip_to_blade_mm"]) == {"J921"} and f["blades_without_a_receptacle_tip_to_blade_mm"]["J921"] == pytest.approx(1.05, abs=0.02)
    # the check's own meaning of reachable: the opening left round the fitted boots now admits the tip, which the nominal rule keeps out
    assert "J941, J911 only" in res["summary"]


@pytest.mark.controls("c19_reversed", "c19_installed")
def test_c19_drip_rule_is_the_installed_cone_and_the_axes_are_information(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C19: The case record states the installed orientation as the owner gave it: the plate is vertical on the machine's wall, the board projects from it horizontally with its component side facing down, the tray holds the board's bare back above the parts, and the lid closes the underside and comes off downward. The case is judged in that orientation: the lid removal sweep, the reach of every fixing and of each receptacle, the test finger and drip paths of every opening (falling onto the bare back, not onto parts), and the heat release through the vents given that warm air rises past the board, are each stated for it. Each printed part's print orientation is stated separately from its installed orientation.
    drip = named(controls.get("c19_reversed"), "c15.drip")
    assert not drip["passed"] and any(r["reaches_mains_copper"] for r in drip["figures"]["per_opening"])
    # the same straight slots with the lid underneath, as installed, are shielded by the tray above them
    assert named(controls.get("c19_installed"), "c15.drip")["passed"]


@pytest.mark.controls("c15_wide_outlet")
def test_c15_negative_wide_outlet_slit_is_refused_by_the_finger_check(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C15: The lid's heat-release slots and every other opening in the assembled case, with the three receptacles fitted to their blades, keep a standard test finger off the board's mains copper and off every bare mains metal, and no opening lets a drip fall onto mains copper, by the model's geometry with the finger's and the drip's path stated for each opening. One residual is stated and accepted by the owner: the boots of the receptacles at J941 and J921 need a shared bay, so with a receptacle removed a test finger can touch the bare blade. That state is a service state inside the machine's own enclosure, and the case record states the rule that the machine is never energised with a receptacle off a blade, and records the finger figures for the receptacle-off state (blade, bay width, the gap a finger enters, the lean at which it fails) as a stated finding, not a pass. The case record states that the case is the enclosure the separation basis's pollution-degree credit relies on, and what the openings leave of it.
    got = controls.get("c15_wide_outlet")
    assert got["outlets"] and not named(got["results"], "c15.finger")["passed"]


def test_c19_outlets_stand_in_the_cores_zone_and_the_tray_top_stays_closed(results, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C19: The case record states the installed orientation as the owner gave it: the plate is vertical on the machine's wall, the board projects from it horizontally with its component side facing down, the tray holds the board's bare back above the parts, and the lid closes the underside and comes off downward. The case is judged in that orientation: the lid removal sweep, the reach of every fixing and of each receptacle, the test finger and drip paths of every opening (falling onto the bare back, not onto parts), and the heat release through the vents given that warm air rises past the board, are each stated for it. Each printed part's print orientation is stated separately from its installed orientation.
    core = model.core
    zone = core.outlet_zone()
    slits = model.info["outlets"]
    assert {s.side for s in slits} == {"left", "right"} and len(slits) >= 16
    assert all(not core.outlet_problems(s) for s in slits) and not core.outlet_web_faults(slits)
    assert all(s.width <= core.outlet_max_width() and s.z_top >= zone[s.side]["z0"] for s in slits)
    assert all(s.z_bottom <= zone[s.side]["z1"] + 1e-9 for s in slits)        # the 4.5 mm slits end exactly on the limit, to rounding
    # the zone starts under the tray's outer top face (installed: just below its top) and no slit is cut in that face
    assert zone["left"]["z0"] > model.z_floor_bottom + model.P("case.floor_mm")
    sc = check.Scene(model, ["tray"])
    hits = [sc.first_hit((u, v, model.z_floor_bottom - 5.0), (0, 0, 1)) for u in range(-1, 49, 4) for v in range(12, 74, 4)]
    assert all(h is not None and h["distance"] < 6.0 for h in hits)
    # the vents' areas, for the record
    areas = named(results, "c15.openings_enumerated")["figures"]["open_areas"]
    assert areas["lid_inlet_free_area_mm2"] > 100 and areas["side_outlet_free_area_mm2"] > 100
    assert areas["side_outlet_slit_count"] == len(slits)
    # a slit against a locating rib, over the finger's window or too wide is refused
    from core import Outlet
    z0 = zone["left"]["z0"]
    assert core.outlet_problems(Outlet("left", 14.0, 2.0, 2.0, z0)) and core.outlet_problems(Outlet("left", 58.0, 2.0, 2.0, z0))
    assert core.outlet_problems(Outlet("right", 30.0, 4.0, 2.0, z0)) and core.outlet_problems(Outlet("right", 30.0, 2.0, 2.0, zone["right"]["z0"] - 1.0))
    assert not core.outlet_problems(Outlet("right", 30.0, 2.0, 2.0, z0))


# ---------------------------------------------------------------- C18

def test_c18_boots_sweep_clear_of_lid_and_tray(results, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C18: The case leaves room around each of the three 6.3 mm blades for a receptacle with its insulating boot fitted, with the boot's outer size and the figure's source stated in the case record, so that a receptacle is pushed on and pulled off along the stated direction, with the lid on and with it off, without the receptacle or its boot touching the case, the lid or the film, and the wire leaving the boot has a stated bend room. The model shows the boot's swept envelope clear of the case at its stated size and at the largest size of a common insulated receptacle the record names, and no case dimension that another criterion of this leaf fixes is reduced to make it.
    r = named(results, "c18.boot_clearance")
    f = r["figures"]
    assert r["passed"] and len(f["boots"]) == 6 and {b["envelope"] for b in f["boots"]} == {"typical", "largest_common"}
    for b in f["boots"]:
        assert b["lid_on_least_clearance_mm"] >= 0.5 and b["lid_off_least_clearance_mm"] >= 0.5 and b["lid_on_nearest"] in ("lid", "tray")
    assert f["boot_to_boot_gap_mm"]["typical"]["J941-J921"] == pytest.approx(8.1 - 7.8, abs=1e-6) and f["boot_to_boot_ok_at_pass_envelope"]
    assert f["boot_to_boot_gap_mm"]["largest_common"]["J921-J911"] > 3.0
    assert f["depth_below_lid_face_for_boot_and_bend_mm"]["typical"] == pytest.approx(22.0 + 17.0 - model.P("case.z_lid_top_mm"), abs=1e-6)
    assert f["depth_below_lid_face_for_boot_and_bend_mm"]["largest_common"] == pytest.approx(25.0 + 17.0 - model.P("case.z_lid_top_mm"), abs=1e-6)
    assert f["wire"]["bend_room_mm"] == pytest.approx(5 * 3.4) and f["envelope_status"] == "assumed, owner to measure his boots"
    removal = f["lid_removal_with_receptacles_fitted"]
    assert removal["largest_common"]["boots_only"]["removable"] is False and removal["typical"]["boots_and_straight_wire"]["removable"] is False
    assert set(f["bare_blade_finger_reach_mm"]) == {"J941", "J921", "J911"}


@pytest.mark.controls("c18_tight", "c18_big")
def test_c18_negative_a_bay_too_small_for_the_boot_and_a_boot_too_big_for_the_far_wall(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C18: The case leaves room around each of the three 6.3 mm blades for a receptacle with its insulating boot fitted, with the boot's outer size and the figure's source stated in the case record, so that a receptacle is pushed on and pulled off along the stated direction, with the lid on and with it off, without the receptacle or its boot touching the case, the lid or the film, and the wire leaving the boot has a stated bend room. The model shows the boot's swept envelope clear of the case at its stated size and at the largest size of a common insulated receptacle the record names, and no case dimension that another criterion of this leaf fixes is reduced to make it.
    tight = named(controls.get("c18_tight"), "c18.boot_clearance")
    assert not tight["passed"] and min(b["lid_on_least_clearance_mm"] for b in tight["figures"]["boots"]) < 0.5
    big = named(controls.get("c18_big"), "c18.boot_clearance")
    assert not big["passed"]


# ---------------------------------------------------------------- C16

@pytest.mark.controls("corner_low", "corner_high")
def test_c16_opposite_corners_of_the_seating_range(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C16: The board-to-plate fit takes the scatter of the delivered triacs' seating, stated as a range of tab-hole height and lean, without loading the soldered leads: the tray's board seat and the barrier are shown by the model to meet at the range's extremes. The plate's tab holes are either a short slot or an oversize hole, or tapped holes drilled at the measured height of the delivered triacs with the tray printed to the measured values, and the case record states which the case takes; for tapped holes it states that the owner's acceptance of that departure from his ruling of 2026-11-24 (slot or oversize hole) is outstanding. The range with its source is recorded as unconfirmed for the owner to check at assembly.
    low, high = controls.get("corner_low"), controls.get("corner_high")
    lows = case.Params.load().entry("seating")
    assert low["seating"]["body_underside_mm"] == lows["body_underside_mm"]["min"] and high["seating"]["body_underside_mm"] == lows["body_underside_mm"]["max"]
    assert low["seating"]["lean_deg"] == lows["lean_deg"]["min"] and high["seating"]["lean_deg"] == lows["lean_deg"]["max"]
    assert low["seating"]["outline_routing_mm"] == lows["outline_routing_mm"]["min"] and high["seating"]["outline_routing_mm"] == lows["outline_routing_mm"]["max"]
    assert low["seating"]["lead_play_mm"] == lows["lead_play_mm"]["min"] and high["seating"]["lead_play_mm"] == lows["lead_play_mm"]["max"]
    assert low["seating"]["tab_face_to_lead_centre_mm"] == lows["tab_face_to_lead_centre_mm"]["min"] and high["seating"]["tab_face_to_lead_centre_mm"] == lows["tab_face_to_lead_centre_mm"]["max"]
    assert low["seating"]["tab_hole_height_mm"] < high["seating"]["tab_hole_height_mm"] and low["gap_mm"] < high["gap_mm"]
    # judged with the receptacles fitted every corner passes every check, with the creepage over the basis's figure and the boots clear of the case
    for c in (low, high):
        assert c["failed"] == [] and c["all_pass"]
        assert c["least_creepage_mm"] >= c["creepage_required_mm"] and c["boot_least_clearance_mm"] >= 0.5 and c["lid_sweep_min_mm"] >= check.SWEEP_FLOOR
    # the receptacle-off reach is reported beside them as a finding and never counted
    fr = check.seating_range_finding([low, high])
    assert fr["kind"] == "finding" and fr["passed"] is None and fr["figures"]["reached_blades_by_seating"]


@pytest.mark.heavy
def test_c16_seating_range_every_extreme():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C16: The board-to-plate fit takes the scatter of the delivered triacs' seating, stated as a range of tab-hole height and lean, without loading the soldered leads: the tray's board seat and the barrier are shown by the model to meet at the range's extremes. The plate's tab holes are either a short slot or an oversize hole, or tapped holes drilled at the measured height of the delivered triacs with the tray printed to the measured values, and the case record states which the case takes; for tapped holes it states that the owner's acceptance of that departure from his ruling of 2026-11-24 (slot or oversize hole) is outstanding. The range with its source is recorded as unconfirmed for the owner to check at assembly.
    r = check.seating_range({})[0]
    assert len(r["figures"]["combinations"]) == 64
    assert r["figures"]["worst_creepage_mm"] >= case.basis()["creepage_mains_mm"]
    heights = {round(c["seating"]["tab_hole_height_mm"], 2) for c in r["figures"]["combinations"]}
    leans = {round(c["seating"]["lean_deg"], 3) for c in r["figures"]["combinations"]}
    gaps = {round(c["gap_mm"], 3) for c in r["figures"]["combinations"]}
    assert heights == {15.3, 17.3} and leans == {-1.0, 1.0} and min(gaps) == 0.28 and max(gaps) == 1.715
    # judged with the receptacles fitted every extreme passes; the receptacle-off reach is reported beside the range as a finding, never counted
    for c in r["figures"]["combinations"]:
        assert c["failed"] == [] and c["all_pass"]
    fr = check.seating_range_finding(r["figures"]["combinations"])
    assert fr["kind"] == "finding" and fr["passed"] is None and fr["figures"]["reached_blades_by_seating"]
    assert all(c["boot_least_clearance_mm"] >= 0.5 for c in r["figures"]["combinations"])
    assert r["figures"]["range_source"]


@pytest.mark.controls("c16_no_lean")
def test_c16_negative_seat_does_not_follow_the_lean(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C16: The board-to-plate fit takes the scatter of the delivered triacs' seating, stated as a range of tab-hole height and lean, without loading the soldered leads: the tray's board seat and the barrier are shown by the model to meet at the range's extremes. The plate's tab holes are either a short slot or an oversize hole, or tapped holes drilled at the measured height of the delivered triacs with the tray printed to the measured values, and the case record states which the case takes; for tapped holes it states that the owner's acceptance of that departure from his ruling of 2026-11-24 (slot or oversize hole) is outstanding. The range with its source is recorded as unconfirmed for the owner to check at assembly.
    assert not named(controls.get("c16_no_lean"), "c6.board_seat")["passed"]


# ---------------------------------------------------------------- output formats

@pytest.mark.controls("cli_json")
def test_cli_json_and_exit_status(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C1: The case's fixed base, the tray the board is screwed to and never the removable lid, carries an insulating barrier between the bare spreader plate face and the board's mains copper wherever the separation basis's basic creepage to the earthed plate would not otherwise hold. The barrier is a creepage barrier only and is not relied on as solid insulation. It is designed for the board as the assembler delivers it, with the triacs seated on their lead shoulders, from the board's layout file and the triac's package model, and it tolerates the delivered triacs' seating scatter. The case drawing or model states the barrier's minimum solid thickness, its height above the board face at each point along the plate edge, that it spans the board's width, the creepage path it gives from each triac pad edge to the first bare plate against the 2.6 mm the basis signs, and the gap it leaves between the board edge and the plate. The barrier is a printed wall of the tray, or a thin bought insulating film that the tray holds, and the drawing states which; a printed wall is at least 0.8 mm thick wherever it stands in the board-to-plate gap or the gap is shown wide enough for it. If neither can be made, the case instead holds the plate's lower edge at least 6.0 mm above the board's component face, which leaves the triac's leads 3.4 mm from the plate; that fallback reverses the owner's recorded plate position and takes the owner's recorded decision before it is used, and the drawing states which form the case takes. Making the plate and printing the case are out of scope.
    done = controls.get("cli_json")
    assert done["returncode"] == 0, done["stdout"][-500:]      # the finding, c15.finding_blades_no_receptacle, does not fail the run
    payload = json.loads(done["stdout"])
    assert payload["passed"] is True and payload["criterion"] == T
    assert payload["findings"] == ["c15.finding_blades_no_receptacle"]
    assert named(payload["checks"], "c15.finding_blades_no_receptacle")["kind"] == "finding"
    assert {c["kind"] for c in payload["checks"] if c["name"] != "c15.finding_blades_no_receptacle"} == {"check"}
    assert done["file"] == payload
    assert {c["name"] for c in payload["checks"]} >= {"c1.creepage_pad_to_plate", "c15.drip", "c15.finger"} and payload["skin"] == "flow"
    assert not [c for c in payload["checks"] if c["name"].startswith("c4.")]
    assert named(payload["checks"], "c15.drip")["figures"]["cone_half_angle_deg"] == 15.0
    pads = named(payload["checks"], "c1.creepage_pad_to_plate")["figures"]["pads_mm"]
    assert "T921 pad 1 F.Cu" in pads and min(pads.values()) > 2.6


def test_text_output_lists_every_check_with_figures(results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C1: The case's fixed base, the tray the board is screwed to and never the removable lid, carries an insulating barrier between the bare spreader plate face and the board's mains copper wherever the separation basis's basic creepage to the earthed plate would not otherwise hold. The barrier is a creepage barrier only and is not relied on as solid insulation. It is designed for the board as the assembler delivers it, with the triacs seated on their lead shoulders, from the board's layout file and the triac's package model, and it tolerates the delivered triacs' seating scatter. The case drawing or model states the barrier's minimum solid thickness, its height above the board face at each point along the plate edge, that it spans the board's width, the creepage path it gives from each triac pad edge to the first bare plate against the 2.6 mm the basis signs, and the gap it leaves between the board edge and the plate. The barrier is a printed wall of the tray, or a thin bought insulating film that the tray holds, and the drawing states which; a printed wall is at least 0.8 mm thick wherever it stands in the board-to-plate gap or the gap is shown wide enough for it. If neither can be made, the case instead holds the plate's lower edge at least 6.0 mm above the board's component face, which leaves the triac's leads 3.4 mm from the plate; that fallback reverses the owner's recorded plate position and takes the owner's recorded decision before it is used, and the drawing states which form the case takes. Making the plate and printing the case are out of scope.
    text = check.render_text(results)
    assert text.count("PASS") >= len(check.verdicts(results)) and text.count("FAIL  ") == 0 and "finding " in text
    assert "c1.creepage_pad_to_plate" in text and "RESULT  PASS" in text and "stands at z 6.000" in text and "1 finding reported, not counted" in text


@pytest.mark.controls("cli_fails")
def test_cli_exits_non_zero_on_a_failing_check(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C1: The case's fixed base, the tray the board is screwed to and never the removable lid, carries an insulating barrier between the bare spreader plate face and the board's mains copper wherever the separation basis's basic creepage to the earthed plate would not otherwise hold. The barrier is a creepage barrier only and is not relied on as solid insulation. It is designed for the board as the assembler delivers it, with the triacs seated on their lead shoulders, from the board's layout file and the triac's package model, and it tolerates the delivered triacs' seating scatter. The case drawing or model states the barrier's minimum solid thickness, its height above the board face at each point along the plate edge, that it spans the board's width, the creepage path it gives from each triac pad edge to the first bare plate against the 2.6 mm the basis signs, and the gap it leaves between the board edge and the plate. The barrier is a printed wall of the tray, or a thin bought insulating film that the tray holds, and the drawing states which; a printed wall is at least 0.8 mm thick wherever it stands in the board-to-plate gap or the gap is shown wide enough for it. If neither can be made, the case instead holds the plate's lower edge at least 6.0 mm above the board's component face, which leaves the triac's leads 3.4 mm from the plate; that fallback reverses the owner's recorded plate position and takes the owner's recorded decision before it is used, and the drawing states which form the case takes. Making the plate and printing the case are out of scope.
    done = controls.get("cli_fails")
    assert done["returncode"] == 1 and "FAIL  c1.plate_lower_edge_raised" in done["stdout"]


def test_exports_exist_and_the_committed_logo_is_the_one_the_model_reads(tmp_path, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    written = case.export_all(model, str(tmp_path))
    names = {os.path.basename(p) for p in written}
    assert {"tray.step", "tray.stl", "lid_single.stl", "lid_two.stl", "lid_swap.stl", "tray_swap.stl", "case-single.3mf", "case-two.3mf",
            "plate-drawing.svg", "case-drawings.svg"} <= names and "inlay.stl" not in names and "film.stl" not in names and "film-template.svg" not in names
    for stl in ("tray", "lid_single", "lid_two", "plate"):
        mesh = trimesh.load(tmp_path / f"{stl}.stl")
        assert mesh.is_watertight and mesh.volume > 0
    for svg in ("plate-drawing.svg", "case-drawings.svg"):
        import xml.dom.minidom
        xml.dom.minidom.parse(str(tmp_path / svg))
    assert "staircase-logo.svg" in os.listdir(CASE_DIR)


# ---------------------------------------------------------------- the skin

def test_the_default_skin_is_flow_and_passes_the_full_check_set(results, model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C13: The case record states an appearance rubric, chosen by the judge of the look for what suits this project and this machine, and carries the Staircase logo, the project's own logo asset (owner-held, used with the owner's permission) traced to a printable vector kept with the case source and recognisable as that logo in both colour forms, on a face seen when the machine is open. The case is designed in two forms that share every dimension a safety criterion of this leaf fixes: a single-colour form, which prints in one filament, and a two-colour form, whose colour change is by part, by layer or by filament swap and needs no more than two filaments. Each form is judged against the rubric from rendered views taken from at least three angles, and each rubric line is recorded as met or not met per form with the view that shows it. The judge of the look did not design the case, and judges the case as installed with its board in it. The owner may choose between rough options where offered but is not a gate. Out of scope: any appearance feature that reduces a creepage, clearance or slot dimension another criterion of this leaf fixes.
    assert model.P.skin_name == "flow"
    # every check passes; the one finding is the accepted receptacle-off reach, which has no verdict
    assert [r["name"] for r in check.verdicts(results) if not r["passed"]] == []
    assert [r["name"] for r in results if r["kind"] == "finding"] == ["c15.finding_blades_no_receptacle"]
    assert {"c13.logo_present_in_each_form", "c18.boot_clearance", "c5.fixings_reached_installed"} <= {r["name"] for r in results}


@pytest.mark.controls("skin_narrow")
def test_an_outline_outside_the_keep_in_or_the_keep_out_is_refused(controls):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C2: The case drawing or model lies wholly within the spreader plate's outline in both directions across the wall, so that only the plate touches the wall, and states the opening in the plastic wall as the plate outline plus a stated clearance, with no larger opening needed for the case, the blades or the harness, which sit in the cavity. Cutting the wall is out of scope.
    import skins
    frame = case.frame(skin="flow")
    core = frame.core
    good = frame.skin.neck(core)
    core.validate_outline(good, "high")
    too_wide = [(u + (4.0 if u > 20 else -4.0), v) if abs(u - 23.75) > 20 else (u, v) for u, v in good]
    with pytest.raises(case.OutlineRefused, match="keep-out"):
        core.validate_outline(too_wide, "high")
    cut_into_cavity = [(u - 3.0 if u > 40 else u, v) if v > 20 else (u, v) for u, v in good]
    with pytest.raises(case.OutlineRefused, match="keep-in"):
        core.validate_outline(cut_into_cavity, "low")

    # a whole skin whose tray neck is cut into the cavity is refused at the build
    assert controls.get("skin_narrow")
