"""Tests of the fit of the exported case to the board's own three-dimensional model (fit.py), and of the right-handed frame the case is exported in.

Run with the interpreter `task hw:cad` creates, from the case folder:  python -m pytest tests/test_case_fit.py
They read the files case.py wrote into out/ and the cached board model; they fail, not skip, when `task hw:case` has not run, and when the board
model was exported from a layout file other than the one in the repository. The exports are read as a printer or viewer reads them and never through
the case model's own frame, except by the one test that compares the renderer's scene with them, which builds the model.
"""

import os
import re
import shutil
import sys

import numpy as np
import pytest

CASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CASE_DIR)
import case  # noqa: E402,I001  (build123d before vtk)
import board_model  # noqa: E402
import fit  # noqa: E402
import logo  # noqa: E402

import trimesh  # noqa: E402
from shapely import affinity  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

T = "SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON"
OUT = os.path.join(CASE_DIR, "out")


def failing(results):
    return {r.name for r in results if not r.ok}


def named(results, name):
    return next(r for r in results if r.name == name)


@pytest.fixture(scope="module")
def board():
    try:
        return fit.load_board_model()
    except SystemExit as error:
        pytest.fail(str(error))


@pytest.fixture(scope="module")
def meshes():
    try:
        return fit.load_meshes(OUT)
    except SystemExit as error:
        pytest.fail(str(error))


@pytest.fixture(scope="module")
def params():
    return case.Params.load()


@pytest.fixture(scope="module")
def geometry_results(meshes, board, params):
    return fit.fit_results(meshes, board, params)


@pytest.fixture(scope="module")
def file_results(meshes):
    try:
        return fit.check_files(OUT, meshes)
    except SystemExit as error:
        pytest.fail(str(error))


# ---------------------------------------------------------------- the cached board model

def test_board_model_cache_is_the_export_of_the_current_layout_file():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    problem = board_model.stale()
    assert problem is None, problem
    import json
    recorded = json.load(open(board_model.SIDECAR, encoding="utf-8"))
    assert recorded["kicad_pcb_sha256"] == board_model.sha256_of(board_model.PCB)
    assert recorded["command"][:4] == ["kicad-cli", "pcb", "export", "step"] and "--user-origin" in recorded["command"] and "--include-pads" in recorded["command"]
    assert recorded["kicad_cli_version"]


def test_a_changed_layout_file_makes_the_cache_stale_and_names_the_task(tmp_path):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    pcb = tmp_path / "board.kicad_pcb"
    shutil.copy(board_model.PCB, pcb)
    assert board_model.stale(str(pcb), board_model.SIDECAR, board_model.STEP) is None
    pcb.write_bytes(pcb.read_bytes() + b"\n")
    message = board_model.stale(str(pcb), board_model.SIDECAR, board_model.STEP)
    assert message and "task hw:case:board-model" in message
    gone = board_model.stale(str(pcb), str(tmp_path / "missing.json"), board_model.STEP)
    assert gone and "task hw:case:board-model" in gone


def test_loading_the_board_model_refuses_a_layout_file_that_differs_from_the_sidecar_and_names_the_task(tmp_path, monkeypatch):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    pcb = tmp_path / "board.kicad_pcb"
    shutil.copy(board_model.PCB, pcb)
    original = board_model.stale
    monkeypatch.setattr(board_model, "stale", lambda: original(str(pcb)))
    fit._BOARD_CACHE.clear()
    fit.load_board_model()       # the unchanged copy loads
    pcb.write_bytes(pcb.read_bytes() + b"\n")
    fit._BOARD_CACHE.clear()
    with pytest.raises(fit.BoardModelError) as refused:
        fit.load_board_model()
    assert "task hw:case:board-model" in str(refused.value) and "layout file" in str(refused.value)
    fit._BOARD_CACHE.clear()


def test_board_model_is_placed_by_translation_from_its_own_corners_and_pads(board):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    x0, y0, x1, y1 = board.outline.bounds
    assert (x0, y1) == pytest.approx((0.0, 0.0), abs=1e-6)                  # the low-X, high-Y corner is the origin
    assert (x1, y0) == pytest.approx((45.0, -75.0), abs=1e-6)
    assert board.component_face["+Z"] > 2 * board.component_face["-Z"] > 0    # most pad solids with no drilled hole beside them sit on the +Z face: that is the component face
    assert board.thickness == pytest.approx(1.6, abs=0.02) and board.bottom == pytest.approx(-board.thickness)
    assert len(board.slots) == 2 and len(board.blades) == 3 and len(board.triac_rows) == 2
    assert board.h1.d == pytest.approx(3.2, abs=0.05)
    assert all(abs(s.bounds[2] - 45.0) < 1e-6 for s in board.slots)         # both slots open at the right edge


# ---------------------------------------------------------------- the features, on the real exports

def test_pilot_lies_on_the_mounting_hole_axis(geometry_results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    r = named(geometry_results, "pilot_on_h1_axis")
    assert r.ok and r.measured <= r.tolerance == fit.POSITION_TOL_MM


@pytest.mark.parametrize("lid", ["lid_single", "lid_two"])
def test_blade_bays_hold_every_blade_centred_across_x_and_none_is_empty(geometry_results, lid):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    holds = named(geometry_results, f"bays_hold_blade_pad_holes_{lid}")
    centred = named(geometry_results, f"bays_centred_on_blades_across_x_{lid}")
    empty = named(geometry_results, f"no_bay_without_blade_{lid}")
    assert holds.ok and holds.measured == holds.expected == 3
    assert centred.ok and centred.measured <= fit.POSITION_TOL_MM
    assert empty.ok and empty.measured == 0


def test_triac_tapped_holes_film_notches_and_faces_sit_on_the_leads(geometry_results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    for name in ("tapped_holes_on_triac_middle_leads", "tapped_holes_at_tab_hole_height", "film_notches_on_triac_middle_leads"):
        r = named(geometry_results, name)
        assert r.ok and r.measured <= fit.POSITION_TOL_MM, (name, r)
    for name in ("plate_inner_face_at_tab_face_distance", "film_inner_face_at_seating_distance"):
        r = named(geometry_results, name)
        assert r.ok and abs(r.measured - r.expected) <= fit.FACE_TOL_MM, (name, r)
    assert named(geometry_results, "plate_and_film_beyond_the_plate_side_edge").ok
    assert "triac_lead_rows_in_board_model" not in {r.name for r in geometry_results}      # both rows of three lead holes were found in the board model


def test_slot_mouths_keep_the_clear_air_and_the_right_wall_stands_at_them(geometry_results, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    clear = named(geometry_results, "slot_mouths_clear_air")
    assert clear.ok and clear.measured >= params("seat.slot_keepout_mm") - fit.CLEARANCE_TOL_MM
    wall = named(geometry_results, "tray_right_wall_at_slot_mouths")
    assert wall.ok and all(abs(a - params("case.interior_right_mm")) <= fit.POSITION_TOL_MM for a in wall.measured) and len(wall.measured) == 2


def test_board_body_shares_no_volume_with_the_case_and_lies_on_its_seats(geometry_results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    for part in ("tray", "lid_single", "lid_two", "film", "plate"):
        r = named(geometry_results, f"board_body_clear_of_{part}")
        assert r.ok and r.measured <= fit.VOLUME_BOUND_MM3
    seats = named(geometry_results, "board_lies_on_its_seats")
    assert seats.ok and seats.measured <= fit.SEAT_ABOVE_MAX_MM2


def test_a_board_pushed_into_the_tray_floor_is_caught_by_the_volume_and_the_seat_checks(meshes, board):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    import dataclasses
    sunk = dataclasses.replace(board, body=trimesh.Trimesh(vertices=board.body.vertices + [0, 0, -0.5], faces=board.body.faces, process=False), bottom=board.bottom - 0.5)
    results = fit.check_clearance(meshes, sunk)
    assert "board_body_clear_of_tray" in failing(results) and "board_lies_on_its_seats" in failing(results)


# ---------------------------------------------------------------- the logo

def test_logo_reads_the_right_way_round_on_both_lid_forms_and_the_tray_top(geometry_results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    for name in ("lid_single", "lid_two", "tray_top"):
        r = named(geometry_results, f"logo_reads_right_way_round_{name}")
        assert r.ok and r.measured >= fit.LOGO_IOU_MIN, (name, r)


def test_the_logo_overlap_of_the_artwork_as_read_beats_each_mirror_and_the_half_turn(meshes, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    art = fit.artworks(params)
    depth = params("logo.groove_depth_mm")
    for mesh, face in ((meshes["lid_single"], "lid"), (meshes["lid_two"], "lid"), (meshes["tray"], "tray")):
        scores = fit.read_logo(mesh, face, art[face], depth)
        assert scores["as_read"] >= fit.LOGO_IOU_MIN
        for other in ("mirrored_x", "mirrored_y", "half_turn"):
            assert scores["as_read"] - scores[other] >= fit.LOGO_IOU_MARGIN, (face, other, scores)


def test_engraving_placed_maps_the_artwork_for_the_installed_viewer_in_front_of_the_wall():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    # a right triangle with its right angle at the artwork's lower left, 4 wide and 2 tall: x right is along the base, y up along the upright
    art = Polygon([(0, 0), (4, 0), (0, 2)])
    engraving = logo.Engraving(geometry=art, outline=art, width=4.0, height=2.0)
    for face, expected_corner in (("tray", (10.0 + 2.0, 20.0 + 1.0)), ("lid", (10.0 + 2.0, 20.0 - 1.0))):
        g, _ = engraving.placed(face, (10.0, 20.0))
        corner = min(g.exterior.coords, key=lambda p: (p[0] - expected_corner[0]) ** 2 + (p[1] - expected_corner[1]) ** 2)
        assert corner == pytest.approx(expected_corner)
        # the base of the triangle (the artwork's x) runs along -u on both faces: the right angle sits at the greatest u
        assert max(p[0] for p in g.exterior.coords) == pytest.approx(12.0)
        assert g.bounds[0] == pytest.approx(8.0)
    # the artwork's upright (its y, 2 mm from the corner to the apex) runs toward -v on the tray top and toward +v on the lid face
    for face, apex_v in (("tray", 19.0), ("lid", 21.0)):
        g, _ = engraving.placed(face, (10.0, 20.0))
        at_greatest_u = sorted(p[1] for p in g.exterior.coords if abs(p[0] - 12.0) < 1e-9)
        assert at_greatest_u[0] == pytest.approx(19.0) and at_greatest_u[-1] == pytest.approx(21.0)
        apex = next(p for p in g.exterior.coords if abs(p[0] - 12.0) < 1e-9 and abs(p[1] - (21.0 if face == "tray" else 19.0)) > 1e-9)
        assert apex[1] == pytest.approx(apex_v)


# ---------------------------------------------------------------- negative controls

def test_mirroring_the_exports_in_x_fails_the_named_locating_results(meshes, board, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    flipped = fit.mirrored(meshes, 0, board.placed_centre[0])
    assert all(m.is_watertight and m.volume > 0 and m.volume == pytest.approx(meshes[n].volume) for n, m in flipped.items())      # only the handedness differs
    bad = failing(fit.fit_results(flipped, board, params))
    assert {"pilot_on_h1_axis", "bays_hold_blade_pad_holes_lid_single", "bays_hold_blade_pad_holes_lid_two", "bays_centred_on_blades_across_x_lid_single",
            "tapped_holes_on_triac_middle_leads", "film_notches_on_triac_middle_leads", "logo_reads_right_way_round_lid_single",
            "logo_reads_right_way_round_lid_two", "logo_reads_right_way_round_tray_top"} <= bad


def test_mirroring_the_exports_in_y_fails_the_named_locating_results(meshes, board, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    flipped = fit.mirrored(meshes, 1, board.placed_centre[1])
    assert all(m.is_watertight and m.volume > 0 and m.volume == pytest.approx(meshes[n].volume) for n, m in flipped.items())
    bad = failing(fit.fit_results(flipped, board, params))
    assert {"pilot_on_h1_axis", "bays_hold_blade_pad_holes_lid_single", "bays_hold_blade_pad_holes_lid_two", "no_bay_without_blade_lid_single",
            "plate_inner_face_at_tab_face_distance", "film_inner_face_at_seating_distance", "plate_and_film_beyond_the_plate_side_edge",
            "logo_reads_right_way_round_lid_single", "logo_reads_right_way_round_lid_two", "logo_reads_right_way_round_tray_top"} <= bad


def test_the_logo_check_fails_on_the_mirrored_artwork_and_the_mirror_of_one_face_alone(meshes, params):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    art = fit.artworks(params)
    assert failing(fit.check_logo(meshes, params, fit.mirror_artwork(art))) == {"logo_reads_right_way_round_lid_single", "logo_reads_right_way_round_lid_two", "logo_reads_right_way_round_tray_top"}
    assert not failing(fit.check_logo(meshes, params, art))
    # the tray's logo as the lid's reading (the view taken from the wrong side, up the wrong way) is also refused
    tray_as_lid = fit.read_logo(meshes["tray"], "lid", art["tray"], params("logo.groove_depth_mm"))
    assert tray_as_lid["as_read"] < fit.LOGO_IOU_MIN


# ---------------------------------------------------------------- handedness of every file

def test_every_export_is_watertight_with_outward_winding_and_the_print_stls_and_3mfs_are_the_same_shapes(file_results):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    names = {r.name for r in file_results}
    assert {"exports_watertight_with_outward_winding", "print_stl_is_the_stl_turned_tray", "print_stl_is_the_stl_turned_lid_single", "print_stl_is_the_stl_turned_lid_two",
            "3mf_single_objects_are_the_stls", "3mf_two_objects_are_the_stls", "swap_bands_inside_their_base_parts"} <= names
    assert not failing(file_results), [r for r in file_results if not r.ok]


def test_a_mirrored_print_stl_or_3mf_object_is_not_the_same_shape(meshes):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    for name in fit.PRINTED:
        printed = trimesh.load(os.path.join(OUT, f"{name}.print.stl"))
        assert printed.is_watertight and printed.volume > 0
        turned = fit._turned(meshes[name], case.print_rotation(name))
        assert fit._same(fit._signature(printed), fit._signature(turned))[0]
        for axis in (0, 1):
            flipped = fit.mirror_mesh(printed, axis, float(printed.bounds[:, axis].mean()))
            assert flipped.volume > 0 and not fit._same(fit._signature(flipped), fit._signature(turned))[0]
    three = fit.read_3mf(os.path.join(OUT, "case-single.3mf"))
    for axis in (0, 1):
        for name, obj in three.items():
            if name in ("tray", "lid_single"):
                flipped = fit.mirror_mesh(obj, axis, float(obj.bounds[:, axis].mean()))
                assert not fit._same(fit._signature(flipped), fit._signature(meshes[name]))[0]


def test_print_rotation_is_a_proper_rotation_and_the_lids_print_face_down():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    for name in fit.PRINTED:
        rotation = case.print_rotation(name)
        assert np.linalg.det(rotation) == pytest.approx(1.0)
        assert np.allclose(rotation @ rotation.T, np.eye(3))
    assert np.allclose(case.print_rotation("tray"), np.eye(3))
    assert np.allclose(case.print_rotation("lid_two"), np.diag([1.0, -1.0, -1.0]))


def test_slice_placement_carries_a_print_point_back_to_the_model_frame_through_the_reflection(meshes):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    import slice as slice_tool
    for name in ("tray", "lid_two"):
        placement = slice_tool.Placement(name, OUT)
        printed = trimesh.load(os.path.join(OUT, f"{name}.print.stl"))
        exported = meshes[name]
        # a vertex of the exported STL, in the physical frame, is a vertex of the print STL after the turn and the lowering to the bed
        rotated = np.asarray(exported.vertices) @ case.print_rotation(name).T
        sample = np.asarray(exported.vertices)[:200]
        on_bed = rotated[:200] - rotated.min(axis=0) + placement.offset
        model_frame = placement.to_model(on_bed)
        assert np.allclose(model_frame, sample * np.array([1.0, -1.0, 1.0]), atol=1e-6)                 # the case model's (u, v, z): Y is -v
        assert printed.bounds[0] == pytest.approx(np.zeros(3), abs=1e-6)


# ---------------------------------------------------------------- the frame itself

def test_physical_reflection_keeps_solids_valid_and_meshes_outward():
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    from build123d import Box, Pos
    assert np.linalg.det(case.PHYSICAL) == pytest.approx(-1.0)
    assert np.allclose(case.PHYSICAL @ [1.0, 2.0, 3.0], [1.0, -2.0, 3.0])
    shape = Pos(1, 2, 3) * Box(2, 3, 4)
    flipped = case.physical(shape)
    assert flipped.is_valid and flipped.volume == pytest.approx(shape.volume)
    assert flipped.bounding_box().min.Y == pytest.approx(-3.5) and flipped.bounding_box().max.Y == pytest.approx(-0.5)
    mesh = case.to_mesh(shape)
    out = case.physical_mesh(mesh)
    assert out.is_watertight and out.is_winding_consistent and out.volume == pytest.approx(mesh.volume) and out.volume > 0
    assert np.allclose(out.vertices[:, 1], -np.asarray(mesh.vertices)[:, 1])
    outward = np.einsum("ij,ij->i", out.face_normals, out.triangles_center - out.centroid)
    assert (outward > 0).all()


def test_the_physical_export_of_a_part_is_the_reflection_of_the_model_part(model, meshes):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    for name in ("tray", "plate", "film", "lid_single", "lid_two"):
        exported = meshes[name]
        reflected = case.physical_mesh(model.mesh(name))
        ok, note = fit._same(fit._signature(reflected), fit._signature(exported))
        assert ok, (name, note)


# ---------------------------------------------------------------- the renderer's scene

def _section_distance_ok(a, b, tolerance):
    """Both meshes cut by the same planes: each section lies within `tolerance` of the other (a Hausdorff bound over the sampled planes)."""
    for axis in (0, 1, 2):
        lo, hi = max(a.bounds[0][axis], b.bounds[0][axis]), min(a.bounds[1][axis], b.bounds[1][axis])
        levels = np.linspace(lo, hi, 5)[1:-1] + 0.0137 * (axis + 1)
        for value in levels[: (3 if axis == 2 else 2)]:
            sa, sb = fit.section_material(a, axis, float(value)), fit.section_material(b, axis, float(value))
            if sa.is_empty and sb.is_empty:
                continue
            if sa.difference(sb.buffer(tolerance)).area > 1e-3 or sb.difference(sa.buffer(tolerance)).area > 1e-3:
                return False
    return True


def test_render_scene_meshes_are_the_exported_stls_and_a_mirror_is_not(model, meshes, board):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    import render
    scene = render.scene_meshes(model)
    assert set(scene) == {"tray", "lid_single", "lid_two", "film", "plate"}
    for name, mesh in scene.items():
        exported = meshes[name]
        assert mesh.is_watertight and mesh.volume > 0, name
        assert fit._same(fit._signature(mesh), fit._signature(exported))[0], name
        assert _section_distance_ok(mesh, exported, 0.05), name
        if name in ("tray", "lid_single", "film"):
            for axis in (0, 1):
                flipped = fit.mirror_mesh(mesh, axis, board.placed_centre[axis])       # about the board's centre line, as the fit controls do
                assert not (fit._same(fit._signature(flipped), fit._signature(exported))[0] and _section_distance_ok(flipped, exported, 0.05)), (name, axis)


def test_render_cameras_are_written_in_the_physical_frame_with_the_wall_at_the_bottom_of_the_lid_view(model):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    import render
    up_world = render.installed_up(model)
    # the lid view looks along -Z with the far end (v large, Y negative) toward the top of the page, so +u (X positive) is to the left of the page
    pos, focal, up, scale = render.camera_for("lid", render.CENTRE, up_world, model)
    forward = np.asarray(focal) - np.asarray(pos)
    right = np.cross(forward, up)
    assert forward[2] < 0 and up == pytest.approx((0.0, -1.0, 0.0)) and right[0] < 0 and scale
    # the top view looks along +Z with the wall (Y positive) toward the top of the page; +u is to the left there too
    pos, focal, up, scale = render.camera_for("tray-top", render.CENTRE, up_world, model)
    forward = np.asarray(focal) - np.asarray(pos)
    right = np.cross(forward, up)
    assert forward[2] > 0 and up == pytest.approx((0.0, 1.0, 0.0)) and right[0] < 0 and scale
    # a close-up of the lid logo is aimed at the logo and leans toward the viewer in front of the machine: the physical -Y (the model's +v)
    pos, focal, up, _ = render.camera_for("logo-lid-30", render.CENTRE, up_world, model)
    assert np.asarray(pos)[1] < np.asarray(focal)[1] and up == pytest.approx((0.0, -1.0, 0.0))
    # the reflected helper keeps the winding outward
    from pyvista import Box
    poly = render.physical_poly(Box(bounds=(0, 1, 0, 2, 0, 3)))
    tri = trimesh.Trimesh(poly.points, poly.faces.reshape(-1, 4)[:, 1:], process=True)
    assert tri.is_watertight and tri.volume == pytest.approx(6.0)


# ---------------------------------------------------------------- the 2D drawings against the exported meshes

def _svg(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as handle:
        return handle.read()


def _svg_polygons(text, style):
    """The polygons of an SVG whose style or fill attribute holds `style`, as shapely polygons in the drawing's own coordinates."""
    found = re.findall(r'<polygon points="([^"]+)" (?:style|fill)="([^"]*)"', text)
    return [Polygon([tuple(float(c) for c in pair.split(",")) for pair in pts.split()]) for pts, st in found if style in st]


def _silhouette(mesh, axes, signs):
    tri = mesh.vertices[mesh.faces][:, :, list(axes)] * np.array(signs)
    flat = [Polygon(t) for t in tri if abs((t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1])) > 1e-9]
    return unary_union([p.buffer(0.001) for p in flat])


def _filled(geometry):
    return unary_union([Polygon(p.exterior) for p in (geometry.geoms if hasattr(geometry, "geoms") else [geometry])])


def _onto(drawing, mesh_shape):
    """The drawing moved so its lowest-x, lowest-y corner is the mesh shape's: the drawing's sheet offset is not a fact about the object."""
    dx0, dy0 = drawing.bounds[0], drawing.bounds[1]
    return affinity.translate(drawing, xoff=mesh_shape.bounds[0] - dx0, yoff=mesh_shape.bounds[1] - dy0)


def _mirror(geometry, axis):
    b = geometry.bounds
    return affinity.scale(geometry, xfact=-1 if axis == 0 else 1, yfact=-1 if axis == 1 else 1, origin=((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))


def _overlap(a, b):
    return a.intersection(b).area / a.union(b).area


def test_the_plan_drawing_shows_the_pillars_where_the_exported_tray_has_them_and_a_mirrored_plan_does_not(meshes):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    plan_text = _svg("case-drawings.svg").split("SIDE ELEVATION")[0]
    # the plan is drawn from the lid side with the plate at the top and u to the right: drawing x is the physical X and drawing y is minus the physical Y
    body = unary_union([_silhouette(meshes["tray"], (0, 1), (1, -1)), _silhouette(meshes["lid_single"], (0, 1), (1, -1))])
    outline = _filled(unary_union(_svg_polygons(plan_text, "fill:#eef0f2")))
    assert _overlap(_onto(outline, body), body) >= 0.99 and _overlap(_onto(_mirror(outline, 1), body), body) < 0.98
    # the pillars (pink squares) are islands in a section of the exported tray a little under the board's underside; the layout is not symmetric in X or Y
    pillars = [Polygon(p.exterior) for p in _svg_polygons(plan_text, "fill:#d79bc0")]
    assert len(pillars) >= 10
    shift = (body.bounds[0] - outline.bounds[0], body.bounds[1] - outline.bounds[1])
    seen = [(p.centroid.x + shift[0], p.centroid.y + shift[1]) for p in pillars]
    section = fit.section_material(meshes["tray"], 2, -2.5)
    islands = [(i.centroid.x, -i.centroid.y) for i in fit.polygons_of(section) if 10.0 < i.area < 60.0]
    def unmatched(points):
        return [p for p in points if min(np.hypot(p[0] - q[0], p[1] - q[1]) for q in islands) > 0.3]
    assert unmatched(seen) == []
    centre = ((body.bounds[0] + body.bounds[2]) / 2, (body.bounds[1] + body.bounds[3]) / 2)
    assert len(unmatched([(2 * centre[0] - x, y) for x, y in seen])) >= 3, "a plan mirrored in X puts pillars where the tray has none"
    assert len(unmatched([(x, 2 * centre[1] - y) for x, y in seen])) >= 3, "a plan mirrored in Y puts pillars where the tray has none"


def test_the_film_template_outline_is_the_exported_film_seen_from_the_case_side_and_a_mirror_is_not(meshes):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    # seen from the case side, looking toward the wall: u to the right (physical X) and z up (drawing y is minus Z)
    film = _silhouette(meshes["film"], (0, 2), (1, -1))
    drawn = unary_union(_svg_polygons(_svg("film-template.svg"), "#fdf1d2"))
    assert _overlap(_onto(drawn, film), film) >= 0.97
    assert _overlap(_onto(_mirror(drawn, 0), film), film) < 0.93 and _overlap(_onto(_mirror(drawn, 1), film), film) < 0.7


def test_the_plate_drawing_puts_the_tapped_holes_where_the_exported_plate_has_them_and_a_mirror_does_not(meshes):
    # SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON.C21: The exported case meshes are right-handed physical shapes that fit the board as built. Placed against the board's own three-dimensional model exported from its KiCad file, each case feature that depends on a board feature (the blade bays, the triac tab faces and lead pad holes, the mounting-hole pilot, the slot mouths) lies on that feature within a stated tolerance, and the Staircase logo reads the right way round when the lid is viewed from below in the installed orientation. The check runs on the exported files and the board's exported model, not on the case model's own coordinate frame, and a control that mirrors one exported axis makes it fail. The renders and the record's views are drawn from the same physical frame.
    plate = meshes["plate"]
    text = _svg("plate-drawing.svg")
    edge = _svg_polygons(text, "fill:#e9ebee")[0].bounds
    holes = [(float(x), float(y)) for x, y in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="[\d.]+" style="fill:#fff;stroke:#c00', text)]
    assert len(holes) == 2
    drawn = sorted((x - edge[0], y - edge[1]) for x, y in holes)       # from the plate's left edge and top edge as drawn
    section = fit.section_material(plate, 1, float(plate.bounds[0][1]) + 2.0)
    tapped = [v for v in fit.voids_of(section) if abs(fit.equivalent_diameter(v) - 2.5) < 0.3]
    top = float(plate.bounds[1][2])
    left = float(plate.bounds[0][0])
    mesh_side = sorted((v.centroid.x - left, top - v.centroid.y) for v in tapped)
    assert len(mesh_side) == 2 and np.allclose(drawn, mesh_side, atol=0.05)
    width = edge[2] - edge[0]
    mirrored_x = sorted((width - x, y) for x, y in drawn)
    assert not np.allclose(mirrored_x, mesh_side, atol=0.05), "a drawing mirrored in X puts the holes on the other side of the plate"
