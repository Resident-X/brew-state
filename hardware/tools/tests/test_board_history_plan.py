#!/usr/bin/env python3
"""The placement and critical routing history check, run on throwaway git repositories: the plan part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import os
import sys
import tempfile

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_fixtures import footprint  # noqa: E402
from board_fixtures import pad  # noqa: E402
from board_fixtures import uuid  # noqa: E402
import board_fixtures  # noqa: E402
import board_history  # noqa: E402
from board_history_fixtures import Base, HAND, LOCKED, MEASURES, PLACES, PLAN, ROUTED, Repo, board, candidate, critical, critical_pass, placement, pour, short_of  # noqa: E402,F401


WIDE = PLAN.replace("(0, 0)–(40, 40)", "(0, 0)–(60, 40)")


#: The plan with R2 appended to low voltage's parts, and with the analog region given bounds and no parts.
WITH_R2 = PLAN.replace("J1, R1 |", "J1, R1, R2 |")


SENSING = "| analog sensing | none: the schematic carries no sensing front end | nothing | none |"


BOUNDED = PLAN.replace(SENSING, "| analog sensing | (40, 0)–(60, 40) | nothing | none |")


class PlanAndCopperFails(Base):
    """The orderings a final review found the command passing."""

    def candidates_two(self, first_board, second_board):
        one = self.repo.commit(first_board, "b: placement candidate 1")
        two = self.repo.commit(second_board, "b: placement candidate 2")
        return one, two

    def record(self, one, two, board_text, chosen=1, measures=None, message="b: placement"):
        measures = measures or {}
        return self.repo.commit(board_text, message, placement=placement(
            [candidate(1, one, measures=measures.get(1)), candidate(2, two, measures=measures.get(2))], chosen))

    def assertOnly(self, failed, *names):
        self.assertEqual(sorted({line.split(":")[0] for line in failed}), sorted(names), "\n".join(failed))

    # --- Candidates are told apart by their placements ---------------------------------------------

    def test_two_candidates_differing_only_in_the_files_text_fail_as_one_placement(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Change the history command so that it fails two candidates whose parts sit identically, judged by each part's reference, position, angle and side rather than by the board file's bytes
        label = '(gr_text "rev B" (at 30 30) (layer "F.SilkS") (uuid ' + uuid() + ') (effects (font (size 1 1))))'
        variants = {"a label": board(PLACES[1], copper=[label]),
                    "the paper size": board(PLACES[1]).replace('(paper "A4")', '(paper "A3")')}
        for name, second in variants.items():
            with self.subTest(differing_in=name):
                self.repo = Repo(self)
                self.assertNotEqual(board(PLACES[1]), second, "the two files differ in their bytes")
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), second)
                self.record(one, two, board(PLACES[1]), measures={2: MEASURES[1]})
                failed = self.assertFails("candidates 1 and 2 place every part alike", check="distinct candidates")
                self.assertOnly(failed, "distinct candidates")

    def test_candidates_differing_in_a_parts_angle_or_in_which_parts_they_hold_are_distinct(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        self.repo.planned()
        one, two = self.candidates_two(board(PLACES[1]), board(PLACES[1], r1_angle=180))
        # R1 turned half way round puts its pads at (20, 11) on A and (20, 9) on GND: each net 15.1327 mm, and the two
        # connections cross.
        turned = ["LENGTH | total | 30.2655 mm", "CROSSINGS | total | 1", "OUTSIDE | total | 0"]
        self.record(one, two, board(PLACES[1]), measures={2: turned})
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | distinct candidates | PASS | no two candidates place their parts alike", "\n".join(lines))

    def test_candidates_holding_different_sets_of_parts_are_distinct_though_one_part_sits_alike(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails two candidates whose parts sit identically
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended to the floorplan")
        two = self.repo.commit(board(PLACES[1], r2=(30, 25)), "b: placement candidate 2, R2 added")
        self.record(one, two, board(PLACES[1], r2=(30, 25)), chosen=2, measures={2: MEASURES[1]})
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | distinct candidates | PASS", "\n".join(lines))

    def test_candidates_differing_only_by_the_side_their_parts_sit_on_are_distinct(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: judged by each part's reference, position, angle and side rather than by the board file's bytes
        self.repo.planned()
        front = board(PLACES[1])
        back = front.replace('(footprint "proof:Part" (layer "F.Cu")', '(footprint "proof:Part" (layer "B.Cu")')
        self.assertNotEqual(front, back)
        one, two = self.candidates_two(front, back)
        self.record(one, two, front, measures={2: MEASURES[1]})
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | distinct candidates | PASS | no two candidates place their parts alike",
                      "\n".join(lines))

    def test_one_turn_written_two_ways_fails_as_one_placement(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails two candidates whose parts sit identically, judged by each part's reference, position, angle and side
        plain = board(PLACES[1])
        r1 = "(at 20 10)"
        self.assertEqual(plain.count(r1), 1)
        for name, first, second, measures in (("0 and 360", "0", "360", MEASURES[1]),
                                              ("0 and -0", "0", "-0", MEASURES[1]),
                                              ("-90 and 270", "-90", "270", None)):
            with self.subTest(turns=name):
                self.repo = Repo(self)
                self.repo.planned()
                one = plain.replace(r1, f"(at 20 10 {first})" if first != "0" else r1)
                two = plain.replace(r1, f"(at 20 10 {second})")
                self.assertNotEqual(one, two, "the two files differ in their bytes")
                if measures is None:
                    # R1 turned to 270 puts its pads at (21, 10) on A and (19, 10) on GND: 16.0312 mm and 14.0357 mm.
                    measures = ["LENGTH | total | 30.0669 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
                first_commit, second_commit = self.candidates_two(one, two)
                self.record(first_commit, second_commit, one, measures={1: measures, 2: measures})
                failed = self.assertFails("candidates 1 and 2 place every part alike", check="distinct candidates")
                self.assertOnly(failed, "distinct candidates")

    def test_a_negative_zero_in_a_position_reads_as_zero(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails two candidates whose parts sit identically, judged by each part's reference, position, angle and side
        with tempfile.TemporaryDirectory() as directory:
            placed = {}
            for name, at in (("zero", "0 0 0"), ("negative", "-0 -0.0 -0")):
                path = os.path.join(directory, name + ".kicad_pcb")
                with open(path, "w") as handle:
                    handle.write(board_fixtures.layout([footprint("R1", 0, 0, [pad(1, 0, -1, "A", "passive")]).replace(
                        "(at 0 0)", f"(at {at})", 1)]))
                placed[name] = board_history.parts_placed(board_history.locked_copper.read_layout(path))
        self.assertEqual(placed["zero"], placed["negative"])
        self.assertEqual(placed["zero"]["R1"][0], "(0, 0) at 0 degrees")

    def test_turns_a_full_circle_apart_or_a_tiny_step_under_one_stay_whole(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: judged by each part's reference, position, angle and side rather than by the board file's bytes
        self.assertEqual({board_history.turn_text(angle) for angle in (0, 360, -360, 720, -0.0)}, {"0"})
        self.assertEqual(board_history.turn_text(-1e-20), "0")
        self.assertEqual({board_history.turn_text(angle) for angle in (-90, 270, 630)}, {"270"})
        self.assertEqual(board_history.turn_text(180), "180")
        self.assertNotEqual(board_history.turn_text(180), board_history.turn_text(360))
        self.assertEqual(board_history.turn_text(-0.5), "359.5")

    def test_positions_equal_to_six_significant_digits_fail_as_one_placement_and_a_sixth_digit_apart_stay_distinct(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: a position or angle read to six significant digits
        plain = board(PLACES[1])
        self.repo.planned()
        nudged = plain.replace("(at 20 10)", "(at 20.0000001 10.00000001)")
        self.assertNotEqual(plain, nudged, "the two files differ in their bytes")
        one, two = self.candidates_two(plain, nudged)
        self.record(one, two, plain, measures={2: MEASURES[1]})
        failed = self.assertFails("candidates 1 and 2 place every part alike", check="distinct candidates")
        self.assertOnly(failed, "distinct candidates")
        with tempfile.TemporaryDirectory() as directory:
            placed = {}
            for name, x in (("whole", "20"), ("seventh digit", "20.00001"), ("sixth digit", "20.0001")):
                path = os.path.join(directory, name.replace(" ", "_") + ".kicad_pcb")
                with open(path, "w") as handle:
                    handle.write(board_fixtures.layout([footprint("R1", 0, 0, [pad(1, 0, -1, "A", "passive")]).replace(
                        "(at 0 0)", f"(at {x} 5)", 1)]))
                placed[name] = board_history.parts_placed(board_history.locked_copper.read_layout(path))
        self.assertEqual(placed["whole"], placed["seventh digit"])
        self.assertNotEqual(placed["whole"], placed["sixth digit"])

    def test_a_half_turn_stays_distinct_from_a_full_turn(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails two candidates whose parts sit identically, judged by each part's reference, position, angle and side
        self.repo.planned()
        plain = board(PLACES[1])
        full = plain.replace("(at 20 10)", "(at 20 10 360)")
        half = plain.replace("(at 20 10)", "(at 20 10 180)")
        one, two = self.candidates_two(full, half)
        turned = ["LENGTH | total | 30.2655 mm", "CROSSINGS | total | 1", "OUTSIDE | total | 0"]
        self.record(one, two, full, measures={1: MEASURES[1], 2: turned})
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | distinct candidates | PASS", "\n".join(lines))

    # --- A pour is the first copper ------------------------------------------------------------------

    def test_a_pour_drawn_before_the_placement_section_is_recorded_is_the_first_track(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: counts a copper pour as the first copper when it lands before any track, arc or via
        self.repo.planned()
        one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
        poured = self.repo.commit(board(PLACES[1], copper=[pour()]), "b: a ground pour, drawn by hand")
        self.record(one, two, board(PLACES[1], copper=[pour()]), message="b: placement recorded after the pour")
        self.repo.commit(board(copper=[pour(), HAND]), "b: route A")
        self.assertFails("holds no `## Placement` section", check="placement section")
        _, lines, _ = self.repo.run()
        self.assertIn(f"CHECK | first track | PASS | {short_of(poured)} is the first commit carrying a track, arc, via "
                      "or pour", "\n".join(lines))

    def test_the_same_history_with_the_section_recorded_before_the_pour_keeps_the_order_and_passes(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        self.repo.placed()
        poured = self.repo.commit(board(copper=[pour()]), "b: a ground pour, drawn by hand")
        judged = self.repo.routed()
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        lines, _ = self.assertPasses()
        self.assertIn(f"CHECK | first track | PASS | {short_of(poured)} is the first commit carrying a track, arc, via "
                      "or pour", "\n".join(lines))

    def test_a_rule_area_is_no_copper_and_a_history_drawing_one_before_the_section_passes(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: a zone that is a rule area being no copper
        self.repo.planned()
        one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
        self.repo.commit(board(PLACES[1], copper=[pour(rule_area=True)]), "b: a keepout over the connector")
        self.record(one, two, board(PLACES[1], copper=[pour(rule_area=True)]))
        self.repo.routed()
        self.repo.commit(message="b: critical routing pass 1",
                         critical=critical([critical_pass(1, self.repo.git("rev-parse", "HEAD"))]))
        lines, _ = self.assertPasses()
        first = self.repo.git("rev-parse", "HEAD~2")
        self.assertIn(f"CHECK | first track | PASS | {first[:12]} is the first commit carrying a track", "\n".join(lines),
                      "the hand route, not the rule area, is the first copper")

    def test_a_zone_on_a_layer_that_is_no_copper_is_no_pour_and_one_on_the_back_copper_is(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: counts a copper pour as the first copper when it lands before any track, arc or via, a pour being a zone on a copper layer
        def zone_on(layers):
            return pour().replace('(layer "F.Cu")', layers)
        for name, drawn, copper in (("silkscreen", zone_on('(layer "F.SilkS")'), False),
                                    ("mask", zone_on('(layers "F.Mask" "B.Mask")'), False),
                                    ("back copper", zone_on('(layer "B.Cu")'), True),
                                    ("both coppers", zone_on('(layers "F&B.Cu")'), True)):
            with self.subTest(zone=name):
                self.repo = Repo(self)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.commit(board(PLACES[1], copper=[drawn]), f"b: a zone on the {name}")
                self.record(one, two, board(PLACES[1], copper=[drawn]))
                if copper:
                    self.assertFails("holds no `## Placement` section", check="placement section")
                else:
                    lines, _ = self.assertPasses()
                    self.assertIn("CHECK | first track | PASS | no commit carries a track, arc, via or pour yet",
                                  "\n".join(lines))

    def test_an_unlocked_pour_between_the_board_judged_commit_and_the_router_is_not_the_routers_commit(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: counts a copper pour as the first copper when it lands before any track, arc or via
        self.repo.placed()
        judged = self.repo.routed()
        self.repo.commit(board(copper=[LOCKED, pour()]), "b: an unlocked ground pour, after the critical routing")
        self.repo.commit(message="b: critical routing pass 1", critical=critical([critical_pass(1, judged)]))
        router = self.repo.commit(board(copper=[LOCKED, pour(), ROUTED]), "b: router")
        lines, _ = self.assertPasses("--routed")
        self.assertIn(f"CHECK | pass 1 before router | PASS | the pass is as it stood before the router's commit "
                      f"{router[:12]}", "\n".join(lines))

    # --- The plan is held to the plan committed before placement --------------------------------------

    def test_a_region_widened_in_the_commit_that_records_the_section_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails a placement section judged against a floorplan whose set of region names, region bounds or parts differ from the floorplan in the commit before the first commit whose board holds a footprint
        self.repo.planned()
        one, two = self.candidates_two(board((50, 10)), board(PLACES[2]))
        self.repo.replan(WIDE)
        wide = ["LENGTH | total | 90 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
        self.record(one, two, board((50, 10)), measures={1: wide})
        failed = self.assertFails("the region 'low voltage' has the bounds (0, 0)–(60, 40) where the plan before "
                                  "placement gives (0, 0)–(40, 40)", check="plan before placement")
        self.assertOnly(failed, "plan before placement")

    def test_a_region_widened_after_an_unrecorded_placement_and_before_the_first_candidate_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails a placement section judged against a floorplan whose set of region names, region bounds or parts differ from the floorplan in the commit before the first commit whose board holds a footprint, the commit the method judges the plan in
        self.repo.planned()
        self.repo.commit(board(PLACES[2]), "b: a placement no section records")
        self.repo.replan(WIDE)
        one, two = self.candidates_two(board((50, 10)), board(PLACES[2]))
        wide = ["LENGTH | total | 90 mm", "CROSSINGS | total | 0", "OUTSIDE | total | 0"]
        self.record(one, two, board((50, 10)), measures={1: wide})
        self.assertFails("the region 'low voltage' has the bounds (0, 0)–(60, 40)", check="plan before placement")

    def test_a_part_removed_moved_or_a_region_added_in_the_plan_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails a placement section judged against a floorplan whose set of region names, region bounds or parts differ from the floorplan in the commit before the first commit whose board holds a footprint
        changes = {
            "a part removed": (PLAN, PLAN.replace("J1, R1 |", "J1 |"),
                               "R1 is listed in the region 'low voltage' in the plan before placement and not now"),
            "a part moved to another region": (BOUNDED, BOUNDED.replace(
                "| nothing | none |\n| digital", "| nothing | R1 |\n| digital"),
                "R1 is listed in the region 'analog sensing', where the plan before placement lists it only in "
                "'low voltage': a reference is not moved between regions"),
            "a bound moved": (BOUNDED, BOUNDED.replace("(40, 0)–(60, 40)", "(35, 0)–(60, 40)"),
                              "the region 'analog sensing' has the bounds (35, 0)–(60, 40) where the plan before "
                              "placement gives (40, 0)–(60, 40)"),
            "a region row added": (PLAN, PLAN.replace("\n\n## Plan", "\n| extra | none | nothing | none |\n\n## Plan"),
                                   "the floorplan's set of region names is"),
        }
        for name, (then, now, words) in changes.items():
            with self.subTest(change=name):
                self.assertNotEqual(then, now, "the change was made to the plan")
                self.repo = Repo(self)
                self.repo.replan(then)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.replan(now)
                self.record(one, two, board(PLACES[1]))
                self.assertFails(words, check="plan before placement")

    def test_a_repeated_region_name_stops_the_plan_check_rather_than_comparing_a_plan_with_its_own_copy(self):
        # SOL-BOARD-FLOORPLAN-REGION-NAMES-DISTINCT.C1: Change the floorplan reader so it stops, naming the region, when two rows of the floorplan carry the same region name, so the history command's plan compare never judges a plan against an identical copy of itself as changed and never hides a change to one row behind another. Tests in throwaway repositories show a plan with a repeated region name stops rather than fails as changed, in the history command and in the placement command, and that a plan with distinct names is read as before.
        twice = PLAN.replace("\n\n## Plan", "\n| digital | none | nothing | none |\n\n## Plan")
        hidden = PLAN.replace("\n\n## Plan", "\n| low voltage | (0, 0)–(60, 40) | a second row | R1 |\n\n## Plan")
        cases = {
            "an identical plan before and after": (twice, twice),
            "the repeat only in the plan judged": (PLAN, twice),
            "the repeat only in the plan before placement": (twice, PLAN),
            "a changed second row behind the first": (PLAN, hidden),
        }
        for name, (then, now) in cases.items():
            with self.subTest(case=name):
                self.repo = Repo(self)
                self.repo.replan(then)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.replan(now)
                self.record(one, two, board(PLACES[1]))
                failed = self.assertFails("repeats the name of an earlier region row", check="plan before placement")
                text = "\n".join(failed)
                self.assertNotIn("set of region names", text)
                self.assertNotIn("has the bounds", text)
                self.assertNotIn("agrees with", text)

    def test_region_names_differing_only_in_case_or_spacing_are_distinct_regions_and_pass(self):
        # SOL-BOARD-FLOORPLAN-REGION-NAMES-DISTINCT.C1: Change the floorplan reader so it stops, naming the region, when two rows of the floorplan carry the same region name, so the history command's plan compare never judges a plan against an identical copy of itself as changed and never hides a change to one row behind another. Tests in throwaway repositories show a plan with a repeated region name stops rather than fails as changed, in the history command and in the placement command, and that a plan with distinct names is read as before.
        variants = PLAN.replace("\n\n## Plan", "\n| Digital | none | nothing | none |\n| digital 2 | none | nothing | none |"
                                "\n\n## Plan")
        self.repo.replan(variants)
        self.repo.placed()
        lines, _ = self.assertPasses()
        self.assertIn("CHECK | plan before placement | PASS |", "\n".join(lines))

    def test_a_part_appended_to_a_region_before_its_footprint_first_appears_passes(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without R2")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended to low voltage")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: placement candidate 2, with R2")
        self.record(one, two, board(PLACES[2], r2=(30, 25)), chosen=2)
        lines, _ = self.assertPasses()
        text = "\n".join(lines)
        self.assertIn("CHECK | plan before placement | PASS | the floorplan in HEAD", text)
        self.assertIn("with R2 appended to its parts, each committed before its footprint first appears on the board",
                      text)
        self.assertIn("CHECK | candidate 1 measures | PASS", text, "candidate 1 is measured without R2, which it lacks")

    def test_a_part_appended_in_the_commit_that_places_it_or_after_it_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        for name in ("in the same commit", "after"):
            with self.subTest(appended=name):
                self.repo = Repo(self)
                self.repo.planned()
                one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1")
                placed = board(PLACES[2], r2=(30, 25))
                if name == "in the same commit":
                    self.repo.replan(WITH_R2)
                    two = self.repo.commit(placed, "b: candidate 2, with R2 and the amendment in one commit")
                else:
                    two = self.repo.commit(placed, "b: candidate 2, with R2 placed before it is planned")
                    self.repo.replan(WITH_R2)
                    self.repo.commit(message="b: R2 appended to low voltage, too late")
                self.record(one, two, placed, chosen=2)
                self.assertFails("R2 is appended to the parts of 'low voltage' and its footprint first appears on the "
                                 "board at", "but the plan does not list it, after the commit before the first placement",
                                 check="plan before placement")

    def test_a_part_listed_once_dropped_before_placement_and_listed_again_after_it_is_placed_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 listed with the floorplan")
        self.repo.replan(PLAN)
        self.repo.planned()
        placed = board(PLACES[1], r2=(30, 25))
        one = self.repo.commit(placed, "b: candidate 1 places R2, which the plan dropped")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 listed again, after it was placed")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: candidate 2")
        self.record(one, two, placed, measures={2: MEASURES[2]})
        failed = self.assertFails("R2 is appended to the parts of 'low voltage' and its footprint first appears on the "
                                  "board at", "but the plan does not list it, after the commit before the first "
                                  "placement", check="plan before placement")
        self.assertOnly(failed, "plan before placement")

    def test_a_part_placed_in_the_first_placement_commit_and_listed_only_afterwards_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.planned()
        placed = board(PLACES[1], r2=(30, 25))
        one = self.repo.commit(placed, "b: the first placement holds R2, which the plan does not list")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 listed after the first placement")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: candidate 2")
        self.record(one, two, placed, measures={2: MEASURES[2]})
        self.assertFails("R2 is appended to the parts of 'low voltage' and its footprint first appears on the board at "
                         f"{short_of(one)}", check="plan before placement")

    def test_a_part_listed_dropped_and_listed_again_all_before_it_is_placed_passes_as_the_plan_holds_it_when_placed(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without R2")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended")
        self.repo.replan(PLAN)
        self.repo.commit(message="b: R2 dropped again")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended again")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: placement candidate 2, with R2")
        self.record(one, two, board(PLACES[2], r2=(30, 25)), chosen=2)
        self.assertPasses()

    def test_a_part_first_placed_in_a_merge_commit_fails_unless_every_parent_lists_it(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        for name, main_lists, side_lists in (("every parent lists it", True, True),
                                             ("only the side branch lists it", False, True),
                                             ("only the main line lists it", True, False)):
            with self.subTest(merge_of=name):
                self.repo = Repo(self)
                self.repo.planned()
                one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without R2")
                self.repo.git("checkout", "-q", "-b", "side")
                if side_lists:
                    self.repo.replan(WITH_R2)
                    self.repo.commit(message="side: R2 listed")
                else:
                    self.repo.write("README.md", "one line\n")
                    self.repo.commit(message="side: a change that leaves R2 unlisted")
                side = self.repo.git("rev-parse", "HEAD")
                self.repo.git("checkout", "-q", "main")
                if main_lists:
                    self.repo.replan(WITH_R2)
                    self.repo.commit(message="main: R2 listed")
                else:
                    self.repo.write("README.md", "one line\n")
                    self.repo.commit(message="main: a change that leaves R2 unlisted")
                main = self.repo.git("rev-parse", "HEAD")
                two = self.repo.merge("side", board(PLACES[2], r2=(30, 25)), "b: candidate 2, with R2, in a merge")
                self.repo.replan(WITH_R2)
                self.repo.commit(message="b: R2 listed in the plan the section is judged in")
                self.record(one, two, board(PLACES[2], r2=(30, 25)), chosen=2)
                if main_lists and side_lists:
                    self.assertPasses()
                else:
                    unlisted = side if main_lists else main
                    failed = self.assertFails("R2 is appended to the parts of 'low voltage' and its footprint first "
                                              f"appears on the board at {short_of(two)}",
                                              f"in {short_of(unlisted)}: the amendment", check="plan before placement")
                    self.assertOnly(failed, "plan before placement")

    def test_a_plan_text_the_compare_does_not_cover_may_change_and_the_report_says_what_it_covers(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: a region's description, a reason given for no bounds and the order of rows not being compared
        reordered = PLAN.replace("| mains | none: the board carries no mains | nothing | none |\n", "").replace(
            "| digital |", "| mains | none: the board carries no mains | nothing | none |\n| digital |")
        changes = {"a What it holds cell rewritten": PLAN.replace("the connector and its resistor", "something else"),
                   "a reason given for none reworded": PLAN.replace("none: the board carries no mains", "none: no mains"),
                   "the rows reordered": reordered}
        for name, now in changes.items():
            with self.subTest(change=name):
                self.assertNotEqual(PLAN, now, "the change was made to the plan")
                self.repo = Repo(self)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.replan(now)
                self.record(one, two, board(PLACES[1]))
                lines, _ = self.assertPasses()
                self.assertIn(f"in {board_history.PLAN_COMPARED}", "\n".join(lines))

    def test_the_pass_says_none_placed_yet_for_an_appended_part_no_footprint_has_reached(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: each listed in the plan of every parent of the commit where its footprint first appears
        both = PLAN.replace("J1, R1 |", "J1, R1, R2, R3 |")
        for name, plan, placed, words in (
                ("none placed", WITH_R2, None,
                 "with R2 appended to its parts, none placed yet"),
                ("one of two placed", both, (30, 25),
                 "with R2, R3 appended to its parts, R2 committed before its footprint first appears on the board "
                 "and R3 not placed yet")):
            with self.subTest(appended=name):
                self.repo = Repo(self)
                self.repo.planned()
                one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without the appended parts")
                self.repo.replan(plan)
                self.repo.commit(message="b: parts appended to low voltage")
                two = self.repo.commit(board(PLACES[2], r2=placed), "b: placement candidate 2")
                self.record(one, two, board(PLACES[2], r2=placed), chosen=2)
                lines, _ = self.assertPasses()
                text = "\n".join(line for line in lines if line.startswith("CHECK | plan before placement"))
                self.assertIn(words, text)
                self.assertNotIn("each committed before its footprint", text)

    def test_a_part_appended_and_placed_after_the_first_copper_passes_with_the_section_left_as_it_is(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        one, two = self.repo.placed()
        self.repo.through_router(self.repo.routed())
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 added to the plan after the router")
        self.repo.commit(board(copper=[LOCKED, ROUTED], r2=(30, 25)), "b: R2 placed after the router")
        lines, _ = self.assertPasses("--routed")
        self.assertNotIn("appended", "\n".join(line for line in lines if line.startswith("CHECK | plan before placement")))
        self.repo.commit(message="b: the placement section recorded again after the first copper",
                         placement=placement([candidate(1, one), candidate(2, two)], 2))
        self.assertFails("section now differs from the one in", check="placement section")

    def test_a_part_appended_before_the_first_copper_is_held_to_the_plan_when_it_is_placed_after_it(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        for name, kept in (("the plan regenerated without it", False), ("the plan keeping it", True)):
            with self.subTest(plan=name):
                self.repo = Repo(self)
                self.repo.planned()
                one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
                self.repo.replan(WITH_R2)
                self.repo.commit(message="b: R2 appended before the first copper, not placed")
                self.record(one, two, board(PLACES[1]))
                self.repo.commit(board(PLACES[1], copper=[HAND]), "b: the first route")
                judged = self.repo.commit(board(PLACES[1], copper=[LOCKED]), "b: lock the route")
                self.repo.through_router(judged)
                self.repo.replan(WITH_R2 if kept else PLAN)
                self.repo.commit(message="b: the plan regenerated")
                self.repo.commit(board(PLACES[1], copper=[LOCKED, ROUTED], r2=(30, 25)),
                                 "b: R2 placed after the first copper")
                if kept:
                    self.assertPasses("--routed")
                else:
                    failed = self.assertFails("R2 is appended to the parts of 'low voltage'", "but the plan does not "
                                              "list it, after the commit before the first placement",
                                              check="plan before placement", args=("--routed",))
                    self.assertOnly(failed, "plan before placement")

    def test_a_part_dropped_from_the_plan_when_it_is_placed_fails_though_listed_earlier_after_the_first_placement(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.planned()
        one = self.repo.commit(board(PLACES[1]), "b: placement candidate 1, without R2")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 appended")
        self.repo.replan(PLAN)
        self.repo.commit(message="b: R2 dropped")
        two = self.repo.commit(board(PLACES[2], r2=(30, 25)), "b: placement candidate 2, with R2 the plan does not hold")
        self.repo.replan(WITH_R2)
        self.repo.commit(message="b: R2 listed again, after it was placed")
        self.record(one, two, board(PLACES[2], r2=(30, 25)), chosen=2)
        self.assertFails("but the plan does not list it, after the commit before the first placement",
                         check="plan before placement")

    def test_a_part_appended_and_placed_after_the_chosen_candidate_still_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: the only allowed difference being references appended to a region's parts, each listed in the plan of every parent of the commit where its footprint first appears, each such parent coming after the commit before the first placement
        self.repo.planned()
        one, two = self.candidates_two(board(PLACES[1]), board(PLACES[2]))
        self.repo.replan(WITH_R2)
        self.record(one, two, board(PLACES[1]))
        self.repo.commit(board(copper=[HAND], r2=(30, 25)), "b: R2 placed with the first route")
        self.assertFails("R2 is on the board at", "and not in the chosen candidate", check="parts at first track")

    # --- The commit the plan is judged in comes from the history alone -------------------------------

    def test_a_plan_committed_with_the_first_placement_or_after_it_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails when that commit is the root, is a merge, or is one of several first appearances on separate lines of history, and when no plan is readable in it
        def root():
            self.repo.commit(board(PLACES[1]), "b: plan and first placement together")
            return "the root commit", "first placement"

        def no_plan():
            self.repo.write("README.md", "a repository\n")
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "a root commit")
            self.repo.commit(board(PLACES[1]), "b: plan and first placement together")
            return "holds no readable floorplan, so the plan was not committed before placement", \
                "plan before placement"

        def plan_later():
            self.repo.write("README.md", "a repository\n")
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "a root commit")
            self.repo.write("b/b.kicad_pcb", board(PLACES[1]))
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "b: placed, no plan yet")
            self.repo.commit(message="b: the plan, after the placement")
            return "holds no readable floorplan, so the plan was not committed before placement", \
                "plan before placement"

        def no_floorplan():
            self.repo.write("README.md", "a repository\n")
            self.repo.write("b/layout-plan.md", "# Layout plan\n\nnothing yet\n")
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "b: a plan with no floorplan")
            self.repo.write("b/b.kicad_pcb", board(PLACES[1]))
            self.repo.plan()
            self.repo.git("add", "-A")
            self.repo.git("commit", "-q", "-m", "b: the floorplan, with the first placement")
            return "holds no readable floorplan, so the plan was not committed before placement", \
                "plan before placement"

        for build in (root, no_plan, plan_later, no_floorplan):
            with self.subTest(case=build.__name__):
                self.repo = Repo(self)
                words, check = build()
                self.assertFails(words, check=check)

    def test_footprints_first_appearing_in_a_merge_or_on_two_lines_of_history_fail(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails when that commit is the root, is a merge, or is one of several first appearances on separate lines of history, and when no plan is readable in it
        self.repo.planned()
        self.repo.git("checkout", "-q", "-b", "other")
        self.repo.write("README.md", "one line\n")
        self.repo.commit(message="other: a change")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(message="main: a change")
        merge = self.repo.merge("other", board(PLACES[1]), "merge, the parts placed in the merge")
        self.assertFails(f"a footprint first appears in the merge commit {merge[:12]}", check="first placement")

        self.repo = Repo(self)
        self.repo.planned()
        self.repo.git("checkout", "-q", "-b", "other")
        side = self.repo.commit(board(PLACES[1]), "other: parts placed on one line")
        self.repo.git("checkout", "-q", "main")
        here = self.repo.commit(board(PLACES[2]), "main: parts placed on another")
        self.repo.git("merge", "-q", "-s", "ours", "-m", "merge both lines", "other")
        self.assertFails("a footprint first appears on 2 separate lines of history, at", short_of(side),
                         short_of(here), check="first placement")

    def test_a_first_placement_that_does_not_come_before_the_sections_commit_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails a placement section judged against a floorplan whose set of region names, region bounds or parts differ from the floorplan in the commit before the first commit whose board holds a footprint, the commit the method judges the plan in
        self.repo.planned()
        self.repo.git("checkout", "-q", "-b", "side")
        self.repo.write("README.md", "side\n")
        before = self.repo.commit(message="side: the commit before the first placement")
        self.repo.commit(board(PLACES[1]), "side: the first placement")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit(board_fixtures.layout([HAND]), "main: copper and no footprint")
        self.repo.git("merge", "-q", "-s", "ours", "-m", "merge the side line", "side")
        self.assertFails(f"the commit before the first placement, {before[:12]}, is not an ancestor of",
                         check="first placement")

    def test_a_board_that_never_holds_a_footprint_fails(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: fails when that commit is the root, is a merge, or is one of several first appearances on separate lines of history, and when no plan is readable in it
        self.repo.planned()
        self.repo.commit(board_fixtures.layout([]), "b: an empty board")
        self.assertFails("no commit's board holds a footprint", check="first placement")

    def test_a_plan_committed_alone_before_the_first_placement_passes(self):
        # SOL-BOARD-HISTORY-PLACEMENT-HARDENING.C1: Tests in throwaway repositories built outside this one show each of the fails on a history that commits it and that a history keeping the order still passes
        self.repo.placed()
        planned = self.repo.git("rev-parse", "HEAD~3")
        lines, _ = self.assertPasses()
        text = "\n".join(lines)
        self.assertIn("CHECK | first placement | PASS", text)
        self.assertIn(f"in the commit before it, {planned[:12]}", text,
                      "the plan is judged in the commit before the first placement")
        self.assertIn("CHECK | plan before placement | PASS | the floorplan in HEAD", text)
