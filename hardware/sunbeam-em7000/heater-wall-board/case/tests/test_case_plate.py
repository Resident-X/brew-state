"""Tests of the plate-clearance leaf of the printed case: the plate's lower edge raised above the pads and leads, the gap over the board outline's
routing tolerance and the leads' play, the range check at the extremes of six tolerances, the ledge on the tray's end wall, the plate-height range, the tray's end wall, the narrower plate's screws and
bolts, the triac screw's depth and thread, the tray root, and the records that state them (the case record, the thermal proof, the owner's sign-off
record and the separation basis).

Run with the interpreter `task hw:cad` creates, from the case folder:  python -m pytest tests/test_case_plate.py
The model, the nominal check and the negative controls come from the session fixtures of `conftest.py` and `negatives.py`. A record is read as
committed and each rule is a function of its text, so a failing case is the same text with one phrase changed.
"""

import html
import math
import os
import re
import subprocess
import sys

import pytest
import yaml

CASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CASE_DIR)
import case  # noqa: E402,I001  (build123d before vtk)
import check  # noqa: E402

BOARD_DIR = os.path.dirname(CASE_DIR)
PROOF_DIR = os.path.join(BOARD_DIR, "circuit-proof")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def named(results, name):
    return next(r for r in results if r["name"] == name)


def by_name(results):
    return {r["name"]: r for r in results}


def sections(text):
    parts = re.split(r"^## ", text, flags=re.M)
    return [(p.split("\n", 1)[0], p) for p in parts[1:]]


def sec(text, tag):
    found = [body for head, body in sections(text) if head.rstrip().endswith("(%s)" % tag)]
    assert len(found) == 1, tag
    return found[0]


@pytest.fixture(scope="module")
def record():
    return read(os.path.join(BOARD_DIR, "case-record.md"))


@pytest.fixture(scope="module")
def params():
    return case.Params.load()


# ---------------------------------------------------------------- C1: the gap over the three tolerances

def test_c1_the_gap_is_stated_over_the_package_range_the_outline_routing_tolerance_and_the_lead_play(params, record):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C1: The case record and its parameters state the gap between the board edge and the plate over the maker's tab-face-to-lead-centre range, the board outline's routing tolerance at the fabricator's regular tier, the board's thickness tolerance, the print allowance of the ledge's height and the play of a lead in its drilled hole, each with its source or marked as an assumption. Out of scope: measuring the delivered boards' real lead play, and changing the board outline.
    for key in ("tab_face_to_lead_centre_mm", "outline_routing_mm", "lead_play_mm"):
        entry = params.entry("seating." + key)
        assert entry["unconfirmed"] is True and {"min", "max"} <= set(entry) and entry["source"], key
    assert "regular tier" in params.entry("seating.outline_routing_mm")["source"] and "0.2" in params.entry("seating.outline_routing_mm")["source"]
    assert "1.1 mm" in params.entry("seating.lead_play_mm")["source"] and "0.305" in params.entry("seating.lead_play_mm")["source"]
    assert "assumption" in sec(record, "C1") and "`seating.lead_play_mm`" in sec(record, "C1")
    # the board's thickness tolerance and the ledge's print allowance, each with its source and marked unconfirmed or as a design figure
    edge = params.entry("seating.plate_edge_offset_mm")
    assert edge["unconfirmed"] is True and (edge["min"], edge["max"]) == pytest.approx((-(params("plate.ledge_print_allowance_mm") + 0.16), 0.0)) and edge["min"] == pytest.approx(-0.36)
    assert "0.16" in edge["source"] and "board-manufacturer-jlcpcb" in edge["source"] and "print allowance" in edge["source"] and "same distance in the same direction" in edge["source"]
    assert params.entry("plate.ledge_print_allowance_mm")["value"] == 0.2 and "design figure" in params.entry("plate.ledge_print_allowance_mm")["source"]
    body1 = sec(record, "C1")
    assert "board's thickness tolerance is 1.6 mm plus or minus 10 percent, 0.16 mm" in body1 and "Board thickness tolerance" in body1 and "print allowance is 0.2 mm" in body1
    assert "6.0 - 0.2 - 0.16 = 5.64 mm" in body1 and "same distance in the same direction" in body1 and "unconfirmed" in body1
    assert case.plate_geometry(case.frame({"seating.plate_edge_offset_mm": -0.36}))["z0"] == pytest.approx(5.64)
    gap = check.gap_range(params)
    assert gap["min_mm"] == pytest.approx(0.28) and gap["max_mm"] == pytest.approx(1.715) and gap["nominal_mm"] == pytest.approx(1.0)
    assert gap["package_min_mm"] == pytest.approx(0.785) and gap["package_max_mm"] == pytest.approx(1.21)
    body = sec(record, "C1")
    assert "0.785 - 0.2 - 0.305 = 0.280 mm and 1.210 + 0.2 + 0.305 = 1.715 mm" in body and "1.000 mm nominal" in body
    assert "regular tier" in body and "Board outline tolerance" in body
    # the model carries the gap: the built gap at each extreme is the stated sum, the outline moving the board edge and the play moving the plate
    for overrides, expected in (({"seating.tab_face_to_lead_centre_mm": 2.645, "seating.lead_play_mm": 0.305, "seating.outline_routing_mm": -0.2}, 0.28),
                                ({"seating.tab_face_to_lead_centre_mm": 3.07, "seating.lead_play_mm": -0.305, "seating.outline_routing_mm": 0.2}, 1.715),
                                ({"seating.outline_routing_mm": 0.2}, 1.2), ({"seating.lead_play_mm": 0.305}, 0.695)):
        m = case.frame(overrides)
        assert float(m.board.outline.bounds[1]) - m.v_plate == pytest.approx(expected, abs=1e-9), overrides


@pytest.mark.controls("c1_gap_narrowest", "c1_gap_widest")
def test_c1_the_checks_hold_at_the_narrowest_and_the_widest_gap(controls, basis):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C3: Over every extreme of the stated range, the straight-air clearance and the creepage from every mains pad edge and every bare lead to the nearest bare plate metal meet the separation basis's signed figures, with no barrier, film or coating credited. Out of scope: the separation basis's figures themselves, and solid-insulation credit for any material.
    for which, gap in (("c1_gap_narrowest", 0.28), ("c1_gap_widest", 1.715)):
        got = by_name(controls.get(which))
        assert got["c1.gap_over_tolerances"]["passed"] and got["c1.gap_over_tolerances"]["figures"]["gap_of_this_build_mm"] == pytest.approx(gap)
        for name in ("c1.clearance_pad_to_plate", "c1.creepage_pad_to_plate", "c1.clearance_bare_lead_to_plate", "c1.creepage_bare_lead_to_plate",
                     "c1.creepage_all_mains_copper", "c1.straight_to_wall_plane", "c1.end_wall_stands_off"):
            assert got[name]["passed"], (which, name)
        assert got["c1.creepage_pad_to_plate"]["figures"]["creepage_mm"] >= basis["creepage_mains_mm"]
        assert got["c1.clearance_pad_to_plate"]["figures"]["clearance_mm"] >= basis["clearance_mains_mm"]
        assert got["c1.creepage_bare_lead_to_plate"]["figures"]["creepage_mm"] >= basis["creepage_mains_mm"]
    # the end wall stands 0.2 mm behind the plate plane, so 0.48 mm from the board edge at the narrowest gap
    assert by_name(controls.get("c1_gap_narrowest"))["c1.end_wall_stands_off"]["figures"]["to_board_mm"] == pytest.approx(0.48, abs=1e-6)


def test_c3_the_nominal_distances_are_straight_lines_to_the_plate_and_the_wall_plane(results, basis, model):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C3: Over every extreme of the stated range, the straight-air clearance and the creepage from every mains pad edge and every bare lead to the nearest bare plate metal meet the separation basis's signed figures, with no barrier, film or coating credited. Out of scope: the separation basis's figures themselves, and solid-insulation credit for any material.
    wall = named(results, "c1.straight_to_wall_plane")["figures"]
    assert wall["copper_mm"] >= basis["creepage_mains_mm"] and wall["leads_mm"] >= basis["creepage_mains_mm"]
    assert wall["wall_plane_v_mm"] == pytest.approx(model.v_plate - model.P("plate.thickness_mm"))
    creep = named(results, "c1.creepage_pad_to_plate")["figures"]
    assert set(creep["pads_mm"]) == {f"{ref} pad {n} {layer}" for ref in ("T911", "T921") for n in "123" for layer in ("F.Cu", "B.Cu")}
    assert creep["basis"].startswith("straight-line distance")
    # the nearest Mains copper is a triac pad on the top copper and the plate's lower edge is what keeps it 6 mm away
    nearest = named(results, "c1.creepage_all_mains_copper")["figures"]
    assert "pad" in nearest["item"] and "F.Cu" in nearest["item"] and nearest["least_mm"] == pytest.approx(creep["creepage_mm"], abs=0.5)


@pytest.mark.controls("c1_low_plate")
def test_c3_a_plate_edge_too_low_breaks_the_creepage_checks(controls):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C3: Over every extreme of the stated range, the straight-air clearance and the creepage from every mains pad edge and every bare lead to the nearest bare plate metal meet the separation basis's signed figures, with no barrier, film or coating credited. Out of scope: the separation basis's figures themselves, and solid-insulation credit for any material.
    low = by_name(controls.get("c1_low_plate"))
    assert not low["c1.creepage_pad_to_plate"]["passed"] and not low["c1.creepage_all_mains_copper"]["passed"]
    assert low["c1.creepage_pad_to_plate"]["figures"]["creepage_mm"] < 2.6


# ---------------------------------------------------------------- C2: the range at the extremes of five tolerances

def test_c2_the_range_rebuilds_at_every_extreme_of_the_six_tolerances(params):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C2: The case's seating-range check rebuilds the case at every extreme of body height, lean, tab-face distance, outline routing tolerance, board thickness, the ledge's print allowance and lead play, and runs every check at each. Out of scope: the tolerance figures themselves.
    combos = check.seating_combinations()
    assert len(combos) == 64 == len(set(combos)) and len(check.SEATING_AXES) == 6
    for axis in range(6):
        assert {c[axis] for c in combos} == {"min", "max"}
    seen = {}
    for c in combos:
        o = check.combo_overrides({}, None, c)
        assert set(o) == {"seating.body_underside_mm", "seating.lean_deg", "seating.tab_face_to_lead_centre_mm", "seating.outline_routing_mm", "seating.lead_play_mm",
                          "seating.plate_edge_offset_mm"}
        for key, value in o.items():
            seen.setdefault(key, set()).add(round(value, 3))
    entries = {k: params.entry(k) for k in seen}
    assert seen["seating.outline_routing_mm"] == {-0.2, 0.2} and seen["seating.lead_play_mm"] == {-0.305, 0.305}
    assert seen["seating.body_underside_mm"] == {2.55, 4.55} and seen["seating.tab_face_to_lead_centre_mm"] == {2.645, 3.07}
    assert seen["seating.lean_deg"] == {-1.0, 1.0} == {entries["seating.lean_deg"]["min"], entries["seating.lean_deg"]["max"]}
    assert seen["seating.plate_edge_offset_mm"] == {-0.36, 0.0}, "the board's thickness tolerance and the ledge's print allowance, combined into one axis"
    # the axis moves the plate's lower edge: the model built at each extreme carries it, and the ledge stands at the same height
    for offset in (0.0, -0.36):
        m = case.frame({"seating.plate_edge_offset_mm": offset})
        assert case.plate_geometry(m)["z0"] == pytest.approx(6.0 + offset) and case.plate_lower_edge(m) == pytest.approx(6.0 + offset)


@pytest.mark.controls("corner_low", "corner_high")
def test_c2_every_check_runs_at_each_corner_and_the_plate_checks_are_among_them(controls):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C2: The case's seating-range check rebuilds the case at every extreme of body height, lean, tab-face distance, outline routing tolerance, board thickness, the ledge's print allowance and lead play, and runs every check at each. Out of scope: the tolerance figures themselves.
    for name in ("corner_low", "corner_high"):
        got = controls.get(name)
        assert got["all_pass"] and got["failed"] == [] and got["checks_run"] >= 42
        assert {"outline_routing_mm", "lead_play_mm", "plate_edge_offset_mm"} <= set(got["seating"])
        assert got["seating"]["plate_edge_offset_mm"] == (-0.36 if name == "corner_low" else 0.0), "the ledge follows the edge at the extreme: every check, the ledge check among them, passes there"
        assert got["least_lead_mm"] >= got["creepage_required_mm"] and got["least_creepage_mm"] >= got["creepage_required_mm"]


@pytest.mark.heavy
def test_c2_the_range_rebuilds_all_sixty_four_extremes_and_every_check_passes():
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C2: The case's seating-range check rebuilds the case at every extreme of body height, lean, tab-face distance, outline routing tolerance, board thickness, the ledge's print allowance and lead play, and runs every check at each. Out of scope: the tolerance figures themselves.
    r = check.seating_range({})[0]
    rows = r["figures"]["combinations"]
    assert len(rows) == 64 and all(c["all_pass"] and c["failed"] == [] for c in rows) and r["passed"] is True
    gaps = sorted(round(c["gap_mm"], 3) for c in rows)
    assert gaps[0] == 0.28 and gaps[-1] == 1.715 and {round(c["seating"]["lean_deg"], 3) for c in rows} == {-1.0, 1.0}
    assert {round(c["seating"]["plate_edge_offset_mm"], 3) for c in rows} == {-0.36, 0.0}
    assert min(c["least_creepage_mm"] for c in rows) >= 2.6 and min(c["least_lead_mm"] for c in rows) >= 2.6


# ---------------------------------------------------------------- C4 and C5: no loose part, and a plate of full height cannot be seated

@pytest.mark.controls("c1_loose_part")
def test_c4_a_loose_part_in_the_model_fails_and_the_record_lists_none(controls, record, results):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C4: The case record's parts list and assembly steps contain no insulating film, coating, shim or other loose part, and no step whose omission leaves clearance or creepage short of the signed figures. Out of scope: the lid, screws and fixings that hold the case together.
    assert named(results, "c1.no_loose_part_or_coating")["passed"] and named(results, "c1.no_loose_part_or_coating")["figures"]["loose_parts"] == []
    got = named(controls.get("c1_loose_part"), "c1.no_loose_part_or_coating")
    assert not got["passed"] and got["figures"]["loose_parts"] == ["film"]
    body = sec(record, "C11")
    fitting = body.split("**Installation order**")[1].split("**Removal**")[0]
    assert "no film, coating, shim or other loose part" in fitting and "film is laid" not in fitting and "film clamped" not in fitting
    assert "no insulating film, coating, shim or other loose part" in sec(record, "C1")
    assert not [k for k in case.Params.load().data if k in ("film", "coating", "shim")]


@pytest.mark.controls("c1_full_height_plate", "c5_plate_below_ledge", "c5_ledge_cut_away")
def test_c5_a_plate_below_the_ledge_cannot_be_seated_because_the_ledge_sets_the_edge_in_the_tray_frame(controls, results, model):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C5: The case model's check shows the plate's lower edge is set by the ledge in the tray's own frame: a plate at the ledge's height shares no volume with the tray, and a plate 0.05 mm below it shares a positive volume, so a lower plate cannot be seated; a plate at its former position, 7.025 mm below the component face, is refused likewise. Out of scope: the plate's own drawing.
    nominal = named(results, "c1.plate_seated_on_ledge")
    f = nominal["figures"]
    assert nominal["passed"] and f["shared_volume_at_ledge_mm3"] == pytest.approx(0.0, abs=1e-6)
    assert f["step_below_mm"] == 0.05 and f["shared_volume_below_ledge_mm3"] > 1.0, "a plate 0.05 mm below the ledge shares a positive volume with the tray"
    assert f["shared_volume_at_former_position_mm3"] > 1000.0 and f["former_lower_edge_z_mm"] == pytest.approx(-7.025)
    # the edge is set in the tray's own frame: 12.6 mm above the floor's underside, 63 layers of the printer's 0.2 mm
    assert f["ledge_above_floor_underside_mm"] == pytest.approx(12.6) == pytest.approx(6.0 - model.z_floor_bottom)
    assert f["layers_of_0.2_mm"] == pytest.approx(63.0) and f["ledge_z_mm"] == pytest.approx(f["plate_lower_edge_z_mm"]) == pytest.approx(6.0)
    # the end wall's board-side recess is its own figure, apart from the ledge's height, and stays 0.2 mm
    assert model.P("plate.end_wall_board_recess_mm") == 0.2 and named(results, "c1.end_wall_stands_off")["figures"]["front_behind_plate_plane_mm"] == pytest.approx(0.2)
    assert named(results, "c1.end_wall_stands_off")["figures"]["gap_under_plate_edge_mm"] == pytest.approx(0.0, abs=1e-9), "the end wall's top is the ledge itself"
    # the edge follows the ledge, not the board: a build with the edge moved takes the ledge with it
    low = case.frame({"seating.plate_edge_offset_mm": -0.36})
    assert case.plate_lower_edge(low) == pytest.approx(5.64)
    # the negative controls: a plate lowered 0.05 mm, a ledge cut away, and the plate at its former position each fail the check
    lowered = named(controls.get("c5_plate_below_ledge"), "c1.plate_seated_on_ledge")
    assert not lowered["passed"] and lowered["figures"]["shared_volume_at_ledge_mm3"] > 1.0
    cut = named(controls.get("c5_ledge_cut_away"), "c1.plate_seated_on_ledge")
    assert not cut["passed"] and cut["figures"]["shared_volume_below_ledge_mm3"] == pytest.approx(0.0, abs=1e-6), "with no ledge a lower plate would be seated"
    former = by_name(controls.get("c1_full_height_plate"))
    assert not former["c1.plate_seated_on_ledge"]["passed"] and not former["c1.plate_clear_of_end_wall"]["passed"]
    assert former["c1.plate_seated_on_ledge"]["figures"]["shared_volume_at_ledge_mm3"] > 1000.0
    assert former["c1.plate_clear_of_end_wall"]["figures"]["plate_lower_edge_z_mm"] == pytest.approx(-7.025)


# ---------------------------------------------------------------- C6 and C7: the thermal judgement at the plate's height

H_PLATE = 20.0 / 1000.0


def junction(k, air, h, rc, load):
    perimeter = 2 * (H_PLATE + 0.080)
    r_wall = 1.0 / (h * H_PLATE * 0.080 + perimeter * math.sqrt(h * k * 0.0025))
    path = r_wall + 0.005 / (15.0 * 0.080 * H_PLATE) + 0.027 + rc
    if load == "both heaters on":
        return air + 9.09 * path + 9.09 * 0.5325 * (0.50 + 2.1)
    return air + 4.84 * (path + 0.50 + 2.1)


def narrower_section(out):
    start = out.index("== (e) amendment 2026-11-27")
    return out[start:out.index("\n== ", start + 3)]


def run_script():
    done = subprocess.run([sys.executable, "-I", os.path.join(PROOF_DIR, "W_margins.py")], capture_output=True, text=True, cwd=PROOF_DIR, check=False)
    return done.returncode, done.stdout


def printed_cases(section):
    cases = {}
    wall = None
    for line in section.splitlines():
        head = re.match(r"\s+-- wall: (aluminium|304 stainless), k (\d+) W", line)
        if head:
            wall = float(head.group(2))
            continue
        row = re.match(r"\s+air (\d+) degC, h = +(\d+), Rc = (\d+) K/W, (both heaters on|steam heater alone) *: junction +([\d.]+) degC", line)
        if row and wall is not None:
            cases[(wall, float(row.group(1)), float(row.group(2)), float(row.group(3)), row.group(4))] = float(row.group(5))
    return cases


def test_c6_the_margin_script_is_re_run_at_the_plate_height_the_case_takes_with_the_plate_conduction_recomputed(params):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C6: The wall-assembly thermal judgement is re-run from its margin script at the plate height the case takes, with the plate's own conduction recomputed for that height, and every case holds the maker's junction limit. Out of scope: the bolted joint's measured resistance, which the bring-up measurement closes.
    code, out = run_script()
    assert code == 0 and out == read(os.path.join(PROOF_DIR, "W_margins.log")), "W_margins.log is stale: regenerate it with python3 -I W_margins.py > W_margins.log"
    section = narrower_section(out)
    # the script's plate height is the case's: the bar's height from the model's own plate geometry and from params.yaml
    geometry = case.plate_geometry(case.frame())
    assert geometry["z1"] - geometry["z0"] == pytest.approx(H_PLATE * 1000.0) == pytest.approx(params("plate.height_mm"))
    assert re.search(r"^N_PLATE_HEIGHT_MM = %s " % re.escape(str(params("plate.height_mm"))), read(os.path.join(PROOF_DIR, "W_margins.py")), re.M), "the script's plate height input is the case's"
    assert "plate term 0.2083 K/W (the former plate's 0.1390 K/W)" in section
    cases = printed_cases(section)
    assert len(cases) == 48
    for (k, air, h, rc, load), printed in cases.items():
        assert printed == pytest.approx(junction(k, air, h, rc, load), abs=0.006), (k, air, h, rc, load)
    aluminium = {key: v for key, v in cases.items() if key[0] == 110.0}
    assert len(aluminium) == 24 and max(aluminium.values()) < 125.0 and max(aluminium.values()) == pytest.approx(119.48, abs=0.006)
    assert "PASS  narrower plate holds the maker's 125 degC in every case" in section
    # the former plate's section is unchanged beside it
    assert "== (e) amendment 2026-11-21" in out and "R_wall = 1 / (10 x 0.0024" in out


def test_c6_the_plate_height_is_an_input_of_the_script_and_moves_every_case(tmp_path):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C6: The wall-assembly thermal judgement is re-run from its margin script at the plate height the case takes, with the plate's own conduction recomputed for that height, and every case holds the maker's junction limit. Out of scope: the bolted joint's measured resistance, which the bring-up measurement closes.
    text = read(os.path.join(PROOF_DIR, "W_margins.py"))
    assert text.count("N_PLATE_HEIGHT_MM = 20.0 ") == 1
    base = printed_cases(narrower_section(run_script()[1]))
    for height in (16.8, 27.5):
        path = tmp_path / ("W_margins_%s.py" % height)
        path.write_text(text.replace("N_PLATE_HEIGHT_MM = 20.0 ", "N_PLATE_HEIGHT_MM = %s " % height, 1), encoding="utf-8")
        done = subprocess.run([sys.executable, "-I", str(path)], capture_output=True, text=True, cwd=str(tmp_path), check=False)
        assert done.returncode == 0, done.stdout[-400:]
        moved = printed_cases(narrower_section(done.stdout))
        h = height / 1000.0
        for (k, air, hc, rc, load), printed in moved.items():
            perimeter = 2 * (h + 0.080)
            r_wall = 1.0 / (hc * h * 0.080 + perimeter * math.sqrt(hc * k * 0.0025))
            path_r = r_wall + 0.005 / (15.0 * 0.080 * h) + 0.027 + rc
            expected = air + 9.09 * path_r + 9.09 * 0.5325 * (0.50 + 2.1) if load == "both heaters on" else air + 4.84 * (path_r + 0.50 + 2.1)
            assert printed == pytest.approx(expected, abs=0.006), (height, k, air, hc, rc, load)
        hottest = max(v for key, v in moved.items() if key[0] == 110.0)
        assert hottest == pytest.approx({16.8: 121.25, 27.5: 116.03}[height], abs=0.006) and hottest < 125.0
        key = (110.0, 40.0, 5.0, 3.0, "both heaters on")
        assert (moved[key] > base[key]) == (height < 20.0), "a lower plate carries the heat less well, a taller one better"


def test_c6_the_judgement_is_the_plate_height_and_not_the_former_one():
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C6: The wall-assembly thermal judgement is re-run from its margin script at the plate height the case takes, with the plate's own conduction recomputed for that height, and every case holds the maker's junction limit. Out of scope: the bolted joint's measured resistance, which the bring-up measurement closes.
    code, out = run_script()
    former = {key: v for key, v in printed_cases(out[out.index("== (e) amendment 2026-11-21"):out.index("== (e) amendment 2026-11-27")]).items() if key[0] == 110.0}
    narrower = {key: v for key, v in printed_cases(narrower_section(out)).items() if key[0] == 110.0}
    assert set(former) == set(narrower) and all(narrower[key] > former[key] for key in former), "a narrower plate carries the heat less well in every case"


def test_c7_the_records_list_every_case_over_the_policy_share_with_its_load_air_film_coefficient_and_joint_resistance():
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C7: The records that quote the thermal judgement list, at the plate height the case takes, each case that misses the 100 degC policy share, with the load, air temperature, film coefficient and joint resistance of each. Out of scope: any change to the policy share.
    code, out = run_script()
    over = sorted((a, h, rc, load, t) for (k, a, h, rc, load), t in printed_cases(narrower_section(out)).items() if k == 110.0 and t > 100.0)
    assert len(over) == 4
    proof = read(os.path.join(BOARD_DIR, "circuit-proof.md"))
    new = proof.split("## The narrower plate and the triacs' thermal judgement on it")[1].split("\n## ")[0]
    assert "20 of 24 hold the 100 degC share" in new
    for air, h, rc, load, t in over:
        who = "both triacs on" if load.startswith("both") else "steam alone"
        assert "%s at %d degC air, air film coefficient h = %d W/(m2.K), joint resistance Rc = %d K/W, %.2f degC" % (who, air, h, rc, t) in new
    rows = [line for line in new.splitlines() if re.match(r"\| (25|40) \| (10|5) \| \d \| ", line)]
    assert len(rows) == 24
    for line in rows:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        air, h, rc, load = float(cells[0]), float(cells[1]), float(cells[2]), "both heaters on" if cells[3] == "both on" else "steam heater alone"
        assert float(cells[4]) == pytest.approx(junction(110.0, air, h, rc, load), abs=0.006)
        assert cells[6] == ("holds" if float(cells[4]) <= 100.0 else "fails")
    owner = read(os.path.join(BOARD_DIR, "owner-sign-off.md"))
    for air, h, rc, load, t in over:
        assert "%.1f degC" % junction(110.0, air, h, rc, load) in owner.split("11. W-19")[1], t
    assert "4 of the 24 aluminium-wall cases miss the 100 degC policy share" in owner


# ---------------------------------------------------------------- C8: the owner's sign-off record

def w19_problems(text):
    problems = []
    entry = re.search(r"^- W-19\..*$", text, re.M)
    if not entry:
        return ["no W-19 entry"]
    e = entry.group(0)
    for needle, why in (("accepted_by: Claude, on behalf of David Baker (owner), under his standing instruction of 2026-11-07", "not signed on his behalf"),
                        ("accepted_on: 2026-11-27", "not dated"), ("lower edge stands 6.0 mm above the board's component face", "the raised lower edge is not stated"),
                        ("tapped M3 through the whole plate", "the tapped-through holes are not stated"), ("the acceptance that the printed case's seating-scatter criterion", "the outstanding acceptance is not closed"),
                        ("ruling of 2026-11-24", "the ruling it departs from is not named"), ("earth bond rests on two wall bolts", "the earth-bond item is missing"),
                        ("4 of the 24 aluminium-wall cases", "the 100 degC item is missing"),
                        ("on a ledge at the top of the tray's end wall", "the ledge is not stated"), ("standard flat aluminium bar 20 mm wide", "the standard bar is not stated"), ("M3 tapped holes through the 5.0 mm plate", "the tapped-hole item is missing")):
        if needle not in e:
            problems.append(why)
    behalf = text.index("## Signed on behalf")
    carried = text.index("## Carried to named later steps")
    if not behalf < text.index("- W-19.") < carried:
        problems.append("W-19 is not in the signed-on-behalf section")
    if "Keeper's note 2026-11-27: superseded by W-19" not in text or "Keeper's note 2026-11-27:** the barrier text" not in text.replace("**Keeper's note 2026-11-27:**", "Keeper's note 2026-11-27:**"):
        problems.append("the keeper's notes on W-10 and W-12 are missing")
    count = re.search(r"There are (\d+) entries", text)
    own, on_behalf = re.search(r"## Owner's own words \((\d+) entries\)", text), re.search(r"## Signed on behalf \((\d+) entries", text)
    body = text[text.index("## Owner's own words"):text.index("## For David to sign")]
    entries = set(re.findall(r"^- (W-\d+[a-d]?)\b", body, re.M))
    if not (count and own and on_behalf and int(count.group(1)) == len(entries) == int(own.group(1)) + int(on_behalf.group(1))):
        problems.append("the entry counts disagree")
    if "11. W-19 (signed on his behalf" not in text:
        problems.append("W-19 is not on the end-of-work list")
    return problems


def test_c8_the_sign_off_record_carries_a_dated_entry_for_the_narrower_plate_and_the_tapped_holes():
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C8: The owner's sign-off record carries a dated entry for the narrower plate with its lower edge raised and for the plate's triac holes tapped through, the second being the acceptance the printed case's seating-scatter criterion leaves outstanding. Out of scope: the owner's reasons, which the entry records as said.
    text = read(os.path.join(BOARD_DIR, "owner-sign-off.md"))
    assert w19_problems(text) == []
    assert "Signed on behalf (5 entries: W-5a, W-5b, W-5d, W-18, W-19;" in text and "There are 22 entries, W-1 to W-19" in text
    for broken, expect in ((text.replace("accepted_on: 2026-11-27", "accepted_on: 2026-11-26", 1), "not dated"),
                           (text.replace("tapped M3 through the whole plate", "tapped M3 blind", 1), "tapped-through"),
                           (text.replace("accepted_by: Claude, on behalf of David Baker (owner), under his standing instruction of 2026-11-07. accepted_on: 2026-11-27", "accepted_by: David Baker (owner). accepted_on: 2026-11-27", 1), "his behalf"),
                           (text.replace("There are 22 entries", "There are 21 entries", 1), "counts")):
        assert broken != text and any(expect in p for p in w19_problems(broken)), expect


# ---------------------------------------------------------------- C9: the separation basis

def test_c9_the_signed_basis_states_the_cases_form_with_no_barrier_credited_and_is_re_signed():
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C9: The separation basis's barrier text states the case's form, with no film credited, and carries the owner's re-signature, since the text it replaces was signed. Out of scope: the basis's figures.
    path = os.path.join(BOARD_DIR, "separation-basis.yaml")
    basis = yaml.safe_load(read(path))
    barrier = next(b for b in basis["barrier_types"] if b["barrier"] == "mains-to-earthed-plate")
    text = barrier["formed_by"]
    assert "lower edge 6.0 mm above the component face" in text and "no barrier credited" in text and "no creepage credit" in text
    assert "insulating barrier in the case's fixed tray" not in text and "film" not in text.lower().replace("fills", "")
    assert "owner-sign-off.md W-19" in text
    assert str(basis["accepted_on"]) == "2026-11-27" and "on his behalf" in basis["accepted_by"] and "W-19" in basis["accepted_by"]
    assert max(str(e["accepted_on"]) for e in basis["accepted_exceptions"]) <= str(basis["accepted_on"]), "no exception is dated after the record's acceptance"
    # the figures are not changed by the re-signing
    assert (basis["mains_to_mains"]["clearance_mm"], basis["mains_to_mains"]["terminal_clearance_mm"], basis["mains_to_mains"]["creepage_mm"]) == (1.5, 2.0, 2.6)
    assert (basis["mains_to_low_voltage"]["clearance_mm"], basis["mains_to_low_voltage"]["creepage_mm"]) == (3.0, 10.0)
    assert len(basis["accepted_exceptions"]) == 24
    assert case.basis()["creepage_mains_mm"] == 2.6
    header = read(path).split("standard:")[0]
    assert "Re-signed 2026-11-27, on the owner's behalf" in header


# ---------------------------------------------------------------- C10: the material

def material_problems(text):
    problems = []
    body = text.split("**The case's material, conductive filament excluded.**")
    if len(body) != 2:
        return ["no material section"]
    para = body[1].split("**Flame.**")[0]
    for needle in ("tray, its end wall and the lid are printed in unfilled ASA", "carbon-fibre, metal-filled and other conductive filament is not used", "end wall stands within the signed clearance and creepage"):
        if needle not in para:
            problems.append("lacks '%s'" % needle)
    return problems


def test_c10_the_material_section_excludes_conductive_filament_and_says_why(record):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C10: The case record's material section states that the tray, its end wall and the lid are printed in unfilled plastic and that carbon-fibre, metal-filled and other conductive filament is not used, because the end wall stands within the signed clearance of the mains pads at the tolerance extremes. Out of scope: the print settings and the plastic's choice among unfilled materials.
    body = sec(record, "C17")
    assert material_problems(body) == []
    assert material_problems(body.replace("unfilled ASA", "ASA")) and material_problems(body.replace("conductive filament is not used", "conductive filament is used"))
    assert material_problems(body.replace("end wall stands within the signed clearance and creepage", "wall stands"))


# ---------------------------------------------------------------- C11: the former outline and the wall

@pytest.mark.controls("c2_tray_at_the_wall", "c2_short_former", "c15_plate_too_tall")
def test_c11_the_case_lies_within_the_former_outline_the_opening_covers_the_plate_and_the_end_wall_and_only_the_plate_touches_the_wall(results, controls, params):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C11: The case model lies within the plate's former 80 by 30 mm outline, the plastic-wall opening covers the plate and the end wall together plus the case record's clearance each side and lies within the unit's opening in the plastic wall, and no printed part comes within 0.5 mm of the machine wall's plane, so only the plate touches the wall. Out of scope: the owner's wall cut and the plastic wall's own tolerance.
    nominal = by_name(results)
    assert nominal["c2.case_within_former_outline"]["passed"] and nominal["c2.only_plate_touches_wall"]["passed"] and nominal["c2.wall_opening_stated"]["passed"]
    assert nominal["c2.wall_opening_within_unit_opening"]["passed"]
    wall = nominal["c2.only_plate_touches_wall"]["figures"]
    assert wall["nearest_mm"]["tray"] == pytest.approx(0.5) and wall["required_mm"] == 0.5
    outline = nominal["c2.case_within_former_outline"]["figures"]["former_outline_mm"]
    assert (outline["u0"], outline["u1"], outline["z0"], outline["z1"]) == pytest.approx((-16.25, 63.75, -7.025, 22.975)), "the former outline is its own figure and does not follow the bar's height"
    # the opening covers the plate (z 6.0 to 26.0) and the end wall (z -6.6 to 6.0) together plus 1.5 mm each side: z -8.1 to 27.5, 83.0 x 35.6
    opening = nominal["c2.wall_opening_stated"]["figures"]
    assert opening["opening_width_mm"] == pytest.approx(83.0) and opening["opening_height_mm"] == pytest.approx(35.6)
    assert (opening["opening_mm"]["z0"], opening["opening_mm"]["z1"]) == pytest.approx((-6.6 - 1.5, 26.0 + 1.5))
    assert min(min(v.values()) for v in opening["outside_each_solid_mm"].values()) == pytest.approx(1.5) == params("plate.wall_opening_clearance_mm")
    unit = nominal["c2.wall_opening_within_unit_opening"]["figures"]
    assert unit["unit_opening_z_mm"] == [-10.0, 35.0] and unit["margin_below_mm"] == pytest.approx(1.9) and unit["margin_above_mm"] == pytest.approx(7.5)
    assert "docs/sunbeam-em7000/controller-board-division.md" in params.entry("plate.unit_opening_bottom_z_mm")["source"] and "D11" in params.entry("plate.unit_opening_bottom_z_mm")["source"]
    assert params("plate.unit_opening_bottom_z_mm") == -10.0 and params("plate.unit_opening_top_z_mm") == 35.0
    touching = by_name(controls.get("c2_tray_at_the_wall"))
    assert not touching["c2.only_plate_touches_wall"]["passed"] and touching["c2.only_plate_touches_wall"]["figures"]["nearest_mm"]["tray"] < 0.5
    short = by_name(controls.get("c2_short_former"))
    assert not short["c2.case_within_former_outline"]["passed"]
    tall = by_name(controls.get("c15_plate_too_tall"))
    assert not tall["c2.wall_opening_within_unit_opening"]["passed"] and tall["c2.wall_opening_within_unit_opening"]["figures"]["margin_above_mm"] < 0.0
    assert tall["c2.wall_opening_stated"]["passed"], "the opening still covers a taller plate: only the unit's opening refuses it"


# ---------------------------------------------------------------- C12: the tray root

def test_c12_the_tray_root_and_the_triac_end_are_re_judged_at_the_new_stance_with_the_pull_out_allowance_stated(results, params, record):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C12: The case record re-judges the tray root's tension under the push-on load and the triac end's motion at the tray screws' stance after the plate narrows, states the pull-out allowance it uses for the printed pilots, and the re-judged figures hold the limits the record already states for them. Out of scope: the printed plastic's measured strength.
    root = named(results, "c9.tray_root_tension_and_triac_end_motion")
    f = root["figures"]
    assert root["passed"] and f["screw_z_mm"] == [9.5, 14.0] and f["pivot_z_mm"] == pytest.approx(6.0)
    # recomputed by hand from the figures of the params
    force, span = params("blade.insertion_force_N"), f["span_mm"]
    moment = force * span
    levers = [9.5 - 6.0, 14.0 - 6.0]
    k = moment / (2 * sum(a * a for a in levers))
    assert f["tension_max_N"] == pytest.approx(k * levers[1], rel=1e-9) and f["tension_per_screw_N"]["z 9.5"] == pytest.approx(k * levers[0], rel=1e-9)
    assert f["pullout_allowance_MPa"] == params("screws.tray_pilot_pullout_MPa") == 5.0
    capacity = 5.0 * math.pi * 3.0 * (params("screws.tray_plate_length_mm") - params("plate.thickness_mm"))
    assert f["pullout_capacity_N"] == pytest.approx(capacity) and f["tension_max_N"] < capacity
    assert f["triac_end_motion_mm"] == pytest.approx(f["tray_flexure_at_triac_end_mm"] + f["root_motion_at_triac_end_mm"]) and f["triac_end_motion_mm"] < f["allowed_motion_mm"] == 0.05
    body = sec(record, "C9")
    assert "The pull-out allowance used" in body and "5.0 MPa" in body and "%.0f N" % f["tension_max_N"] in body and "%.4f mm" % f["triac_end_motion_mm"] in body
    assert "assumed" in params.entry("screws.tray_pilot_pullout_MPa")["source"]


@pytest.mark.controls("c9_weak_pilot")
def test_c12_a_weak_pilot_fails_the_re_judgement(controls):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C12: The case record re-judges the tray root's tension under the push-on load and the triac end's motion at the tray screws' stance after the plate narrows, states the pull-out allowance it uses for the printed pilots, and the re-judged figures hold the limits the record already states for them. Out of scope: the printed plastic's measured strength.
    got = named(controls.get("c9_weak_pilot"), "c9.tray_root_tension_and_triac_end_motion")
    assert not got["passed"] and got["figures"]["tension_max_N"] > got["figures"]["pullout_capacity_N"]


# ---------------------------------------------------------------- C13: the triac screw

@pytest.mark.controls("c16_long_screw", "c16_short_screw")
def test_c13_the_triac_screw_tip_stops_short_of_the_back_face_and_engages_enough_thread(results, controls, params):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C13: The case model's check computes, over the screw's length tolerance and the triac tab's thickness range, how far a triac screw's tip stands inside the plate and how much thread it engages, and requires the tip to stop short of the plate's back face and the engagement to be at least the figure the record states for the torque it specifies. Out of scope: the triac's thermal contact and the tab hole's own tolerance.
    got = named(results, "c16.triac_screw_tip_and_engagement")
    f = got["figures"]
    length, b2 = params.entry("triac.tab_screw_length_mm"), params.entry("triac.b2_mm")
    assert got["passed"] and f["tip_depth_max_mm"] == pytest.approx(length["max"] - b2["min"]) == pytest.approx(4.01)
    assert f["engagement_min_mm"] == pytest.approx(length["min"] - b2["max"]) == pytest.approx(3.44)
    assert f["tip_depth_max_mm"] < params("plate.thickness_mm") and f["engagement_min_mm"] >= params("triac.tab_screw_min_engagement_mm") == 3.0
    assert (length["min"], length["max"]) == pytest.approx((4.76, 5.24)) and (b2["min"], b2["max"]) == pytest.approx((1.23, 1.32))
    assert f["clamp_force_N"] == pytest.approx(0.70 * 1000.0 / (0.20 * 3.0)) and f["shear_stress_MPa"] < f["alloy_shear_MPa"]
    long = named(controls.get("c16_long_screw"), "c16.triac_screw_tip_and_engagement")
    assert not long["passed"] and long["figures"]["tip_depth_max_mm"] >= 5.0, "an M3 x 6 reaches the plate's back face and lifts it off the wall"
    short = named(controls.get("c16_short_screw"), "c16.triac_screw_tip_and_engagement")
    assert not short["passed"] and short["figures"]["engagement_min_mm"] < 3.0, "an M3 x 4 engages too little thread"


# ---------------------------------------------------------------- C14: the tray screws and wall bolts

@pytest.mark.controls("c3_screw_in_pocket", "c3_one_edge_screw")
def test_c14_the_tray_screws_and_wall_bolts_fit_the_narrower_plate(results, controls):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C14: The case model's checks require each tray screw's pilot and head to stand clear of the lid-toe pocket and to keep the record's edge distance from the plate's edges, and each wall bolt's washer to fit within the plate. Out of scope: the owner's wall cut and the toothed-washer hedge.
    nominal = named(results, "c3.tray_screws_fit_plate")
    assert nominal["passed"] and len(nominal["figures"]["screws"]) == 4
    for row in nominal["figures"]["screws"]:
        assert row["least_edge_mm"] >= 0.5 - 1e-9 and min(row["to_pocket_mm"].values()) >= 0.4 and row["pilot_top_z_mm"] <= 20.5 - 1.6
    assert {r["screw"].split(" z ")[1] for r in nominal["figures"]["screws"]} == {"9.5", "14"}
    bolts = named(results, "c3.wall_bolts_outside_case")
    assert bolts["passed"] and len(bolts["figures"]["bolts"]) == 2 and all(b["washer_inside_plate_in_z_mm"] == pytest.approx(5.5) and b["bolt_z_mm"] == pytest.approx(16.0) for b in bolts["figures"]["bolts"])
    pocket = controls.get("c3_screw_in_pocket")
    assert not pocket["passed"] and min(min(r["to_pocket_mm"].values()) for r in pocket["figures"]["screws"]) < 0.4
    assert any(r["pilot_top_z_mm"] > 20.5 - 1.6 for r in pocket["figures"]["screws"]), "a pilot at 19.5 mm breaks out of the pilaster's top"
    edge = by_name(controls.get("c3_one_edge_screw"))["c3.tray_screws_fit_plate"]
    assert not edge["passed"] and min(r["least_edge_mm"] for r in edge["figures"]["screws"]) < 0.5


# ---------------------------------------------------------------- C15: both ends of the plate-height range

def height_range_problems(text, params):
    problems = []
    body = sec(text, "C2")
    lo, hi = params("plate.height_min_mm"), params("plate.height_max_mm")
    for needle, why in (("**The least is %.1f mm**" % lo, "the least height is not stated"), ("**The greatest is %.1f mm**" % hi, "the greatest height is not stated"),
                        ("The standard bar widths between them are **20 mm and 25 mm**", "the standard sizes between the ends are not stated"),
                        ("with the lower edge unchanged", "the lower edge is not said to stay"), ("`c16.plate_height_range`", "the range check is not named")):
        if needle not in body:
            problems.append(why)
    return problems


@pytest.mark.controls("c15_height_min", "c15_height_max", "c15_plate_too_short", "c15_plate_too_tall")
def test_c15_the_checks_hold_at_the_least_and_the_greatest_plate_height_and_the_record_states_both(controls, params, record):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C15: The case's checks hold at the least plate height that keeps the case inside the plate's footprint and at the greatest height the unit's opening in the plastic wall admits, with the lower edge unchanged, and the case record states both heights and the standard bar sizes between them. Out of scope: the owner's wall cut.
    lo, hi = params("plate.height_min_mm"), params("plate.height_max_mm")
    assert lo == pytest.approx(params("case.z_lid_top_mm") + params("plate.min_margin_mm") - params("plate.lower_edge_z_mm")) == pytest.approx(16.8)
    assert hi == pytest.approx(params("plate.unit_opening_top_z_mm") - params("plate.wall_opening_clearance_mm") - params("plate.lower_edge_z_mm")) == pytest.approx(27.5)
    assert lo < params("plate.height_mm") == 20.0 < 25.0 < hi, "the standard bar the case takes and the 25 mm bar both lie inside the range"
    ends = {}
    for name, height in (("c15_height_min", lo), ("c15_height_max", hi)):
        rows = controls.get(name)
        counted = check.verdicts(rows)
        assert len(counted) >= 44 and all(r["passed"] for r in counted), (name, [r["name"] for r in counted if not r["passed"]])
        got = by_name(rows)
        assert got["c2.wall_opening_within_unit_opening"]["figures"]["plate_height_mm"] == pytest.approx(height)
        assert got["c1.plate_lower_edge_raised"]["figures"]["plate_lower_edge_z_mm"] == pytest.approx(6.0), "the lower edge is unchanged"
        ends[name] = got
    assert ends["c15_height_min"]["c2.plate_covers_case_top"]["figures"]["margin_mm"] == pytest.approx(params("plate.min_margin_mm")), "at the least height the plate covers the case's top by exactly the margin"
    assert ends["c15_height_max"]["c2.wall_opening_within_unit_opening"]["figures"]["margin_above_mm"] == pytest.approx(0.0, abs=1e-6), "at the greatest height the opening reaches the unit's opening"
    # 0.5 mm beyond either end is refused
    short = by_name(controls.get("c15_plate_too_short"))
    assert not short["c2.plate_covers_case_top"]["passed"] and short["c2.plate_covers_case_top"]["figures"]["margin_mm"] < params("plate.min_margin_mm")
    tall = by_name(controls.get("c15_plate_too_tall"))
    assert not tall["c2.wall_opening_within_unit_opening"]["passed"]
    # the record states both heights and the standard sizes between them
    assert height_range_problems(record, params) == []
    assert height_range_problems(record.replace("**The least is 16.8 mm**", "**The least is 17 mm**"), params) and height_range_problems(record.replace("**20 mm and 25 mm**", "**20 mm**"), params)
    assert height_range_problems(record.replace("**The greatest is 27.5 mm**", "**The greatest is 28 mm**"), params) and height_range_problems(record.replace("with the lower edge unchanged", "with the edge moved"), params)


@pytest.mark.heavy
def test_c15_the_height_range_rebuilds_both_ends_at_the_nominal_gap_and_at_its_extremes():
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C15: The case's checks hold at the least plate height that keeps the case inside the plate's footprint and at the greatest height the unit's opening in the plastic wall admits, with the lower edge unchanged, and the case record states both heights and the standard bar sizes between them. Out of scope: the owner's wall cut.
    r = check.plate_height_range({})[0]
    rows = r["figures"]["rows"]
    assert len(rows) == 6 and r["passed"] is True and all(c["all_pass"] and c["failed"] == [] for c in rows)
    assert {(c["end"], c["state"]) for c in rows} == {(e, st) for e in ("min", "max") for st in check.HEIGHT_RANGE_STATES}
    assert {round(c["plate_height_mm"], 3) for c in rows} == {16.8, 27.5}
    assert sorted(round(c["gap_mm"], 3) for c in rows)[0] == 0.28 and sorted(round(c["gap_mm"], 3) for c in rows)[-1] == 1.715
    assert min(c["least_creepage_mm"] for c in rows) >= 2.6


# ---------------------------------------------------------------- C16: the record and the drawing name the standard bar

def drawing_text(name):
    svg = read(os.path.join(CASE_DIR, "out", name))
    return " ".join(html.unescape(" ".join(re.findall(r">([^<>]+)</text>", svg))).split())


def bar_problems(record, drawing, params):
    problems = []
    height, thick, length = params("plate.height_mm"), params("plate.thickness_mm"), params("plate.length_mm")
    form = " ".join(sec(record, "C12").split("**The tab holes' position")[0].split())
    size = " ".join(sec(record, "C12").split("**Size, and the standard bar.**")[1].split("**How it is made")[0].split())
    for needle, why in (("A standard flat aluminium bar, **%.1f mm long, %.0f mm wide (its height installed) and %.1f mm thick**" % (length, height, thick), "the record's form does not name the bar"),):
        if needle not in form:
            problems.append(why)
    for needle, why in (("the standard sizes between those ends are 20 mm and 25 mm", "the record does not state the standard sizes"), ("thickness, %.1f mm, is a standard stock thickness" % thick, "the thickness is not stated"),
                        ("**The stock's width tolerance is an assumption: it is to be read from the supplier's standard when the bar is sourced, and no figure is stated here.**", "the width tolerance is neither sourced nor marked")):
        if needle not in size:
            problems.append(why)
    for needle, why in (("a standard flat aluminium bar", "the drawing does not name the bar"), ("%.0f mm wide (its height installed) x %.0f mm thick, cut to %.0f mm long" % (height, thick, length), "the drawing does not give the section and length"),
                        ("The stock's width tolerance is an assumption, to be read from the supplier's standard when the bar is sourced", "the drawing does not mark the width tolerance")):
        if needle not in drawing:
            problems.append(why)
    return problems


def test_c16_the_record_and_the_plate_drawing_name_the_standard_bar_with_its_section_length_and_width_tolerance(params, record):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C16: The case record and the plate drawing name the plate as a standard flat aluminium bar of the height the case takes, its thickness and its length, and state the stock's width tolerance from the supplier's standard or mark it as an assumption. Out of scope: the plate's thermal contact, which the thermal judgement covers.
    drawing = drawing_text("plate-drawing.svg")
    assert bar_problems(record, drawing, params) == []
    assert "source" in params.entry("plate.height_mm") and "standard flat aluminium bar" in params.entry("plate.height_mm")["source"] and "width tolerance" in params.entry("plate.height_mm")["source"]
    size = " ".join(sec(record, "C12").split("**Size, and the standard bar.**")[1].split("**How it is made")[0].split())
    assert not re.search(r"tolerance (of|is) [\d.]+|plus or minus|\u00b1", size), "no stock tolerance figure is invented: the only tolerance statement is the assumption"
    assert bar_problems(record.replace("A standard flat aluminium bar,", "A flat aluminium plate,"), drawing, params)
    assert bar_problems(record.replace("**The stock's width tolerance is an assumption", "**The stock's width is exact"), drawing, params)
    assert bar_problems(record, drawing.replace("a standard flat aluminium bar", "an aluminium plate"), params)
    assert bar_problems(record, drawing.replace("cut to 80 mm long", "cut to length"), params)
    assert bar_problems(record, drawing.replace("is an assumption, to be read from the supplier's standard", "is 0.5 mm"), params)


# ---------------------------------------------------------------- C17: the installation order

def install_problems(text):
    problems = []
    body = sec(text, "C11")
    if "**Installation order**" not in body or "**Silent failures the design does not prevent.**" not in body:
        return ["no installation order"]
    order = body.split("**Installation order**")[1].split("**Silent failures the design does not prevent.**")[0]
    steps = re.findall(r"^(\d+)\. (.*)$", order, re.M)
    if [int(n) for n, _ in steps] != list(range(1, 11)):
        problems.append("the steps are not the ten in order")
        return problems
    by = {int(n): t for n, t in steps}
    if "bought bar" not in order.split("\n\n1.")[0] or "receptacles pushed on" not in order.split("\n\n1.")[0]:
        problems.append("the order's span, from the bought bar to the receptacles pushed on, is not stated")
    for n in (2, 3, 4, 9):
        if "**Owner**" not in by[n]:
            problems.append("step %d does not mark the owner's action" % n)
    for n in (2, 3, 4, 5, 6, 7, 8, 9):
        if "Tool" not in by[n] and "Tools" not in by[n]:
            problems.append("step %d states no tool" % n)
    for n in (3, 4, 5, 6, 7, 8, 9):
        if "Access" not in by[n]:
            problems.append("step %d states no access" % n)
    if not ("marks the four tray-screw holes" in by[3] and "ledge" in by[3] and "tapped" not in by[3]) or "taps M3 through" not in by[4]:
        problems.append("the tray holes are not marked before the tab holes are tapped")
    if "tray is fixed to the bar" not in by[5] or "M3 x 12" not in by[5]:
        problems.append("the bench step of fixing the tray to the bar is missing")
    if "bolted to the bar" not in by[7] or "M4" not in by[9] or "hex" not in by[9]:
        problems.append("the tab screws or the wall bolts are not stated")
    if "pushed on" not in by[10]:
        problems.append("the receptacles are not pushed on last")
    silent = body.split("**Silent failures the design does not prevent.**")[1].split("**Removal**")[0]
    for needle, why in (("A wrong-length tab screw", "the wrong-length tab screw is not stated"), ("A skipped tab screw", "the skipped tab screw is not stated"), ("A countersunk head left proud", "the proud countersunk head is not stated")):
        if needle not in silent:
            problems.append(why)
    return problems


def test_c17_the_record_states_the_installation_order_with_tools_access_and_the_silent_failures(record, results):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C17: The case record states the installation order, from the bought bar to the unit bolted to the wall and the receptacles pushed on, marking the owner's actions, and for each step that uses a tool states the tool and the access the model shows, and states the silent failures the design does not prevent: a wrong-length tab screw, a skipped tab screw and a countersunk head left proud. Out of scope: any step the owner performs on the machine's own wall.
    assert install_problems(record) == []
    # the access figures it quotes are the model's
    body = sec(record, "C11")
    tab = named(results, "c11.tab_screw_driver_reached")["figures"]["drivers"]
    assert all("rising" in d["line"] for d in tab.values()) and "0.39 mm" in body and "5.0 to 9.0 degrees" in body
    wall = named(results, "c3.wall_bolts_outside_case")["figures"]["bolts"]
    assert [round(b["bolt_u_mm"], 2) for b in wall] == [-11.25, 58.75] and "u -11.25 and 58.75" in body and "5.05 mm" in body and "0.55 mm clear" in body
    assert named(results, "c5.lid_screw_reached")["passed"] and "81.5 mm from the wall plane" in body
    # a missing owner mark, tool, access, step or silent failure is found
    for old, new, expect in (("3. **Owner**: buys", "3. Buys", "step 3 does not mark"), ("Tools: a drill, a 2.5 mm bit, an M3 tap and wrench, calipers.", "", "step 4 states no tool"),
                             ("Access: tilted 5.0 to 9.0 degrees", "Reach: tilted 5.0 to 9.0 degrees", "step 7 states no access"), ("A skipped tab screw:", "A tab screw:", "skipped tab screw"),
                             ("A countersunk head left proud:", "A head:", "proud countersunk head"), ("A wrong-length tab screw:", "A tab screw:", "wrong-length"),
                             ("10. The receptacles are pushed on", "10. The receptacles go on", "pushed on last")):
        assert old in record and any(expect in p for p in install_problems(record.replace(old, new, 1))), expect


# ---------------------------------------------------------------- C18: the bar's tray holes are marked from the printed tray

def holes_problems(record, drawing, params):
    problems = []
    plate = " ".join(sec(record, "C12").split())
    for needle, why in (("marked from the printed tray with the bar seated on the ledge", "the record does not say the tray holes are marked from the tray on the ledge"),
                        ("each countersunk head sits **flush with or below the bar's back face**", "the record does not say the heads sit flush or below"),
                        ("**10.5 mm nominal, 9.3 to 11.3 mm over the seating range**", "the record does not give the tab holes' distance from the lower edge")):
        if needle not in plate:
            problems.append(why)
    lift = params("plate.lower_edge_z_mm")
    seat = params.entry("seating.body_underside_mm")
    hole = params("triac.A_mm") - params("triac.L_mm")
    lo, nom, hi = seat["min"] + hole - lift, seat["value"] + hole - lift, seat["max"] + hole - lift
    for needle, why in (("marked from the printed tray with the bar seated on its ledge", "the drawing does not say the tray holes are marked from the tray on the ledge"),
                        ("each head sits flush with or below the back face", "the drawing does not say the heads sit flush or below"),
                        ("The tab holes stand %.2f to %.2f mm (nominal %.2f) above the bar's lower edge" % (lo, hi, nom), "the drawing does not give the tab holes' distance from the lower edge")):
        if needle not in drawing:
            problems.append(why)
    return problems


def test_c18_the_record_and_the_drawing_state_how_the_tray_holes_are_marked_and_position_the_tab_holes_from_the_lower_edge(params, record):
    # SOL-HW-HEATER-WALL-BOARD-PLATE-CLEARANCE-HOLDS-OVER-OUTLINE-AND-LEAD-PLAY-TOLERANCE.C18: The case record and the plate drawing state that the bar's four tray-screw holes are marked from the printed tray with the bar seated on the ledge and that each countersunk head sits flush or below the bar's back face, and the drawing gives the tab holes' position as a distance from the bar's lower edge. Out of scope: the owner's drilling accuracy.
    drawing = drawing_text("plate-drawing.svg")
    assert holes_problems(record, drawing, params) == []
    for old, new in (("marked from the printed tray with the bar seated on the ledge", "marked from the drawing"), ("flush with or below the bar's back face", "flush with the bar's back face")):
        assert holes_problems(record.replace(old, new), drawing, params)
    assert holes_problems(record, drawing.replace("marked from the printed tray with the bar seated on its ledge", "marked from the drawing"), params)
    assert holes_problems(record, drawing.replace("each head sits flush with or below the back face", "each head is countersunk"), params)
    assert holes_problems(record, drawing.replace("above the bar's lower edge", "above the board face"), params)
