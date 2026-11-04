#!/usr/bin/env python3
"""The four review callers' context budget and each unit's declared views, over synthetic review folders.

Each caller is loaded as the kit loads it, its declaration resolved for a synthetic review folder the folder command wrote, and
the kit's plan made for it with no session: every group's root is within the budget the caller declares and holds no artefact
none of its units declares. The views a unit declares are those the kit's selection takes from the folder's view index, not the
folder's whole list of views. No model, no KiCad and no agent command line is used.
"""

from __future__ import annotations

import io
import itertools
import json
import os
import re
import sys
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import layout_fixtures as lfx  # noqa: E402
import production_fixtures as pfx  # noqa: E402
import review_caller_critical_routing as critical  # noqa: E402
import review_caller_layout as layout  # noqa: E402
import review_caller_production_files as production  # noqa: E402
import review_caller_schematic as schematic  # noqa: E402
import review_catalogue  # noqa: E402
import test_review_caller_critical_routing as critical_tests  # noqa: E402
import test_review_caller_layout as layout_tests  # noqa: E402
import test_review_caller_production_files as production_tests  # noqa: E402
import test_review_caller_schematic as schematic_tests  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import catalogue, command, costmodel, merge, messages, planner, selection  # noqa: E402

MODEL = "claude-sonnet-5-5"
TEXT_KINDS = ("text", "extract")


def groups(package, folder):
    """The kit's plan for a caller's declaration over its folder, made with no session: the groups, each root built."""
    declaration = package.declaration
    found = catalogue.admit(declaration, folder)
    return declaration, planner.form(declaration, found, MODEL)


_RUNS = itertools.count(1)


def plan_only(case, name, *extra, model=MODEL, fmt="text"):
    """The kit's command run with `--plan-only` on a caller's own replica policy over the case's synthetic folder: (status,
    what it printed)."""
    out, err = io.StringIO(), io.StringIO()
    status = command.main(["--caller", name, "--callers", TOOLS, "--review", case.folder, "--out", os.path.join(case.root, f"plan-{next(_RUNS)}"),
                           "--model", model, "--plan-only", "--format", fmt, *extra], out, err,
                          repo=os.path.join(case.root, "no-repository"))
    return status, out.getvalue() + err.getvalue()


class Replicas:
    """The plan of a caller's own replica policy over several groups: each group a root for each model its replicas run on."""

    def assertPlansEachGroupsRootForTheOtherModel(self, name, other, variants, per_group, fmt, *extra, model=MODEL):
        status, text = plan_only(self, name, *extra, model=model, fmt=fmt)
        self.assertEqual(status, 0, text)
        if fmt == "json":
            plan = json.loads(text)["plan"]
            groups = [group["id"] for group in plan["groups"]]
            self.assertGreater(len(groups), 1, "the round is judged in several groups")
            self.assertEqual([(context["group"], context["model"], context["variants"]) for context in plan["contexts"]],
                             [(group, other, variants) for group in groups], "a root for the other model for each group")
            self.assertEqual(len({context["root_id"] for context in plan["contexts"]}), len(groups))
            self.assertTrue(all(context["root_id"].startswith(f"root.{context['group']}.") for context in plan["contexts"]))
            self.assertEqual(plan["forks"], per_group * len(groups))
        else:
            self.assertRegex(text, r"RESULT \| PLANNED")
            self.assertNotIn("REFUSED", text)
            contexts = [line for line in text.splitlines() if line.startswith("CONTEXT | ")]
            self.assertGreater(len(contexts), 1)
            self.assertEqual(len({line.split(" | ")[1] for line in contexts}), len(contexts), "each root has its own id")
            self.assertTrue(all(f"| model {other} |" in line and line.split(" | ")[-1].startswith("group G") for line in contexts), contexts)

    def assertPlannedAtTwoReplicas(self, name, fmt):
        status, text = plan_only(self, name, "--replicas", "2", fmt=fmt)
        self.assertEqual(status, 0, text)
        if fmt == "json":
            plan = json.loads(text)["plan"]
            self.assertGreater(len(plan["groups"]), 1)
            self.assertEqual(plan["contexts"], [], "no other model's root is built")
            self.assertEqual({group["replicas"] for group in plan["groups"]}, {2})
        else:
            self.assertRegex(text, r"RESULT \| PLANNED")
            self.assertNotIn("REFUSED", text)


def images_of(declaration, names):
    return {name for name in names if declaration.artefacts[name].kind == "image"}


def every_image(declaration):
    return {name for name, artefact in declaration.artefacts.items() if artefact.kind == "image"}


class Budgeted:
    """What each caller's declaration is held to."""

    def assertWithinBudget(self, declaration, formed, module):
        self.assertEqual(declaration.budget.context_fraction, module.HEADROOM)
        self.assertIsNone(declaration.budget.context_tokens)
        self.assertEqual(formed.budget["tokens"], int(costmodel.window_for(MODEL) * module.HEADROOM))
        self.assertTrue(all(built.tokens <= formed.budget["tokens"] for built in formed.groups))
        for built in formed.groups:
            held = {artefact.name for artefact in built.catalogue.artefacts if artefact.kind != "extract"
                    or not artefact.name.startswith("extract/")}
            declared = {name for unit in built.units for name in declaration.units[unit].needs}
            self.assertEqual(held, declared, f"group {built.id}'s root holds what its units declare and nothing else")


    def assertPackedAsTheKitPacks(self, declaration, formed):
        packed = planner.pack(declaration)
        self.assertEqual([list(built.units) for built in formed.groups], packed,
                         "the groups are the kit's packing of the declaration, no view overlap saving enough to merge past its cap")
        self.assertGreater(len(formed.groups), 1, "the caller's round is not judged from one root")

    def assertMergedOnlyWithinTheKitsCap(self, declaration, formed):
        """The units' own views overlap, so groups may merge, but never past the cap the kit packs to, and never into one group."""
        cap = planner.output_cap(declaration)
        packed = planner.pack(declaration)
        self.assertGreater(len(formed.groups), 1, "the caller's round is not judged from one root")
        self.assertLessEqual(len(formed.groups), len(packed))
        for built in formed.groups:
            self.assertLessEqual(built.expected_output_tokens, cap, f"group {built.id} is within the largest single unit's output")

    def assertOneCoupledGroup(self, declaration, formed):
        self.assertEqual(len(planner.coupled_sets(declaration)), 1)
        self.assertEqual([list(built.units) for built in formed.groups], planner.pack(declaration))
        self.assertEqual(len(formed.groups), 1, "a single coupled set is one group")


class TheLayoutCaller(layout_tests.Folder, Budgeted):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C5: Over a synthetic review folder for each of the four callers, the caller's declaration states a model-context budget, each unit declares only the artefacts it needs, its views chosen through the kit's selection from the folder's view index and not by taking the folder's whole view list, and the kit's plan for it gives every group a context within the budget, none holding an artefact that none of its units declares.
    def test_the_declaration_states_the_budget_and_each_unit_its_views_chosen_from_the_index_and_the_plan_is_within_it(self):
        package = kit_caller.load("layout", TOOLS).prepare(self.folder)
        declaration, formed = groups(package, self.folder)
        self.assertWithinBudget(declaration, formed, layout)
        self.assertPackedAsTheKitPacks(declaration, formed)
        total = every_image(declaration)
        index = {f"views/{entry['file']}" for entry in lfx.VIEW_ENTRIES}
        needs = {unit: set(item.needs) for unit, item in declaration.units.items()}
        floor, ground, clock, plan = (images_of(declaration, needs[unit]) for unit in
                                      ("area-FLOOR", "area-GROUND", "area-CLOCK", "plan-and-free-pass"))
        placement = {"placement/placement.png"}
        self.assertEqual(floor, {"views/assembly-top.png", "views/assembly-bottom.png", "views/classes.png",
                                 "views/layer-F.Cu.png"} | placement, "FLOOR-1's assembly views, class map and placement and FLOOR-2's F.Cu")
        self.assertEqual(ground, {"views/net-CLK.png", "views/net-GND.png", "views/layer-F.Cu.png", "views/layer-B.Cu.png"},
                         "GROUND-1's net tiles and every copper layer, and no placement view")
        self.assertEqual(clock, {"views/crop-U1.png", "views/layer-F.Cu.png"})
        self.assertEqual(plan, {"views/layer-F.Cu.png", "views/layer-B.Cu.png", "views/assembly-top.png", "views/assembly-bottom.png",
                                "views/classes.png"} | placement, "the free pass is over the whole-board views")
        for unit, held in ((u, images_of(declaration, needs[u])) for u in needs):
            self.assertLess(held, total, f"{unit} does not take the folder's whole view list")
        self.assertNotIn("views/layer-F.Mask.png", set().union(floor, ground, clock, plan), "a layer no item names is in no unit")
        self.assertTrue(index <= total)

    def test_a_view_the_index_does_not_list_is_in_no_unit_though_the_folder_holds_it(self):
        with open(os.path.join(self.folder, "views", "index.json"), encoding="utf-8") as handle:
            listed = json.load(handle)
        listed["images"] = [entry for entry in listed["images"] if entry["file"] != "classes.png"]
        with open(os.path.join(self.folder, "views", "index.json"), "w", encoding="utf-8") as handle:
            json.dump(listed, handle)
        declaration = kit_caller.load("layout", TOOLS).prepare(self.folder).declaration
        self.assertTrue(os.path.isfile(os.path.join(self.folder, "views", "classes.png")))
        self.assertTrue(all("views/classes.png" not in unit.needs for unit in declaration.units.values()))

    def test_a_folder_with_no_view_index_is_refused_naming_it(self):
        os.remove(os.path.join(self.folder, "views", "index.json"))
        self.refused(lambda: kit_caller.load("layout", TOOLS).prepare(self.folder), "view index", "views/index.json")

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C16: each group's root holds the extract of that report, the report's own lines for the rules its units declare they judge and no other group's rules, and a unit whose declared rule has no line in the report is flagged in the plan naming the unit and the rule, informationally
    def test_the_layout_callers_units_declare_the_check_rules_their_rule_items_judge_and_the_root_holds_the_extract_not_the_report(self):
        package = kit_caller.load("layout", TOOLS).prepare(self.folder)
        declaration, formed = groups(package, self.folder)
        self.assertEqual(declaration.units["area-GROUND"].check_rules, ("clearance_floor",))
        self.assertEqual(declaration.units["area-FLOOR"].check_rules, ())
        self.assertEqual(declaration.check_extract.report, "check-report.txt")
        root = json.loads(formed.groups[0].shared.message)
        text = "\n".join(block["text"] for block in root["message"]["content"] if block["type"] == "text")
        self.assertNotIn("=== check-report.txt ===", text, "the whole report is in no root")
        self.assertIn("=== extract/check-report.txt ===", text)
        self.assertIn("The check's report holds no line for the rules: clearance_floor.", text)
        self.assertEqual(formed.groups[0].extract["missing"], [{"unit": "area-GROUND", "rule": "clearance_floor"}],
                         "the rule the report holds no line for is flagged in the plan naming the unit and the rule")

    def test_a_rule_the_report_holds_lines_for_is_in_the_extract_with_the_checks_own_figure(self):
        report = os.path.join(self.folder, "check-report.txt")
        with open(report, "a", encoding="utf-8") as handle:
            handle.write("VIOLATION | hardware/synth/board/board.kicad_pro | clearance_floor | (3, 4) | gap 0.07 mm under 0.10 mm\n"
                         "VIOLATION | hardware/synth/board/board.kicad_pro | silk_overlap | (5, 6) | unrelated\n")
        package = kit_caller.load("layout", TOOLS).prepare(self.folder)
        _, formed = groups(package, self.folder)
        text = "\n".join(block["text"] for block in json.loads(formed.groups[0].shared.message)["message"]["content"]
                         if block["type"] == "text")
        self.assertIn("clearance_floor | (3, 4) | gap 0.07 mm under 0.10 mm", text)
        self.assertNotIn("silk_overlap", text, "a rule no unit of the group judges is not in its extract")
        self.assertEqual(formed.groups[0].extract["missing"], [])


class TheLayoutCallersReplicas(layout_tests.Folder, Replicas):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: A review over several groups whose replica policy places a replica on a model other than the review's gives each group a root for each such model, held to that model's declared context budget, and each such replica is started from the root of its group and model
    def test_the_pre_order_rounds_three_replicas_over_several_groups_plan_a_small_model_root_for_each_group_in_text_and_json(self):
        for fmt in ("text", "json"):
            with self.subTest(fmt=fmt):
                self.assertPlansEachGroupsRootForTheOtherModel("layout", layout.SMALL_MODEL, ["small"], 3, fmt, "--replicas", "3")

    def test_two_replicas_plan_over_the_same_groups_in_text_and_json(self):
        for fmt in ("text", "json"):
            with self.subTest(fmt=fmt):
                self.assertPlannedAtTwoReplicas("layout", fmt)


class TheCriticalRoutingCaller(critical_tests.Folder, Budgeted):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C5: The critical-routing caller's units declare the views of the nets and areas they judge and not the whole folder's views.
    def test_each_unit_declares_the_views_of_the_nets_and_areas_it_judges_and_the_plan_is_within_the_budget(self):
        package = kit_caller.load("critical_routing", TOOLS).prepare(self.folder)
        declaration, formed = groups(package, self.folder)
        self.assertWithinBudget(declaration, formed, critical)
        self.assertOneCoupledGroup(declaration, formed)
        total = every_image(declaration)
        needs = {unit: set(item.needs) for unit, item in declaration.units.items()}
        self.assertEqual(images_of(declaration, needs["area-GROUND"]), {"views/net-CLK.png", "views/net-GND.png",
                                                                        "views/layer-F.Cu.png", "views/layer-B.Cu.png"})
        self.assertEqual(images_of(declaration, needs["area-CLOCK"]), {"views/crop-U1.png", "views/layer-F.Cu.png"})
        self.assertEqual(images_of(declaration, needs["area-FLOOR"]),
                         {"views/assembly-top.png", "views/assembly-bottom.png", "views/classes.png", "views/layer-F.Cu.png"},
                         "FLOOR-1's assembly views and class map and FLOOR-2's F.Cu, and no placement view, since none was rendered")
        for unit, held in needs.items():
            self.assertLess(images_of(declaration, held), total, f"{unit} does not take the folder's whole view list")
            self.assertNotIn("views/layer-F.Mask.png", held)

    def test_a_folder_with_no_view_index_is_refused_naming_it(self):
        os.remove(os.path.join(self.folder, "views", "index.json"))
        self.refused(lambda: kit_caller.load("critical_routing", TOOLS).prepare(self.folder), "view index", "views/index.json")


class TheProductionFilesCaller(production_tests.Folder, Budgeted):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C5: the production-files caller's declaration states the budget and each unit's images, the design's views chosen from the folder's view index
    def test_the_declaration_states_the_budget_and_each_unit_its_own_images_and_the_plan_is_within_it(self):
        package = kit_caller.load("production_files", TOOLS).prepare(self.folder)
        declaration, formed = groups(package, self.folder)
        self.assertWithinBudget(declaration, formed, production)
        self.assertMergedOnlyWithinTheKitsCap(declaration, formed)
        layers_unit = set(declaration.units[production.LAYERS_UNIT].needs)
        self.assertEqual(images_of(declaration, layers_unit),
                         {"views/layer-F.Cu-r1c1.png"} | {f"production/layers/layer-{name}.png" for name in pfx.LAYERS})
        part_units = [unit for unit in declaration.units if unit != production.LAYERS_UNIT]
        self.assertTrue(part_units)
        for unit in part_units:
            held = images_of(declaration, declaration.units[unit].needs)
            self.assertNotIn("views/layer-F.Cu-r1c1.png", held, "a part unit takes no layer view")
            self.assertTrue(all(not name.startswith("production/layers/") for name in held), "nor a fabrication layer's image")
            self.assertIn("views/assembly-top-r1c1.png", held)
        self.assertLess(layers_unit & every_image(declaration), every_image(declaration))

    def test_the_views_come_from_the_index_and_not_from_the_folders_listing(self):
        index = os.path.join(self.folder, "views", "index.json")
        with open(index, encoding="utf-8") as handle:
            listed = json.load(handle)
        listed["images"] = [entry for entry in listed["images"] if entry["view"] != "assembly"]
        with open(index, "w", encoding="utf-8") as handle:
            json.dump(listed, handle)
        os.remove(os.path.join(self.folder, "views", "assembly-top-r1c1.png"))
        declaration = kit_caller.load("production_files", TOOLS).prepare(self.folder).declaration
        for unit in declaration.units.values():
            self.assertNotIn("views/assembly-top-r1c1.png", unit.needs)


class TheProductionFilesCallersReplicas(production_tests.Folder, Replicas):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: A review over several groups whose replica policy places a replica on a model other than the review's gives each group a root for each such model, held to that model's declared context budget, and each such replica is started from the root of its group and model
    def test_the_checks_default_policy_over_several_groups_plans_a_small_model_root_for_each_group_in_text_and_json(self):
        for fmt in ("text", "json"):
            with self.subTest(fmt=fmt):
                self.assertPlansEachGroupsRootForTheOtherModel("production_files", production.SMALL_MODEL, ["small"], 3, fmt,
                                                               model=production.MID_MODEL)

    def test_two_replicas_plan_over_the_same_groups_in_text_and_json(self):
        for fmt in ("text", "json"):
            with self.subTest(fmt=fmt):
                self.assertPlannedAtTwoReplicas("production_files", fmt)


class TheCriticalRoutingCallersReplicas(critical_tests.Folder):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a plan with no other model's replicas is unaffected
    def test_the_callers_policy_plans_in_text_and_json_on_its_own_model_and_a_single_group_takes_another_models_root(self):
        status, text = plan_only(self, "critical_routing", model="claude-haiku-5-5")
        self.assertEqual(status, 0, text)
        self.assertRegex(text, r"RESULT \| PLANNED")
        status, text = plan_only(self, "critical_routing", model="claude-haiku-5-5", fmt="json")
        self.assertEqual(status, 0, text)
        plan = json.loads(text)["plan"]
        self.assertEqual(len(plan["groups"]), 1)
        self.assertEqual(plan["contexts"], [], "both variants run on the review's model")
        status, text = plan_only(self, "critical_routing", fmt="json")
        self.assertEqual(status, 0, text)
        plan = json.loads(text)["plan"]
        self.assertEqual(len(plan["contexts"]), 1, "one group, so a root for the other model is built")
        self.assertEqual(plan["predicted"]["tokens_written"], plan["groups"][0]["tokens"],
                         "every replica runs on the other model, so the review's own model has no root, started or written")


class TheSchematicCallersReplicas(schematic_tests.Folder, Replicas):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a review over groups whose replicas run on another model gives each group a root for it, and one whose replicas run on the review's own model builds none
    def test_the_callers_policy_run_on_another_model_over_several_groups_plans_each_groups_root_and_on_its_own_model_builds_none(self):
        for fmt in ("text", "json"):
            with self.subTest(fmt=fmt):
                self.assertPlansEachGroupsRootForTheOtherModel("schematic", schematic.SMALL_MODEL, ["full", "hunt"], 2, fmt)
        status, text = plan_only(self, "schematic", model=schematic.SMALL_MODEL, fmt="json")
        self.assertEqual(status, 0, text)
        plan = json.loads(text)["plan"]
        self.assertGreater(len(plan["groups"]), 1)
        self.assertEqual(plan["contexts"], [], "both variants run on the review's model")


class TheSchematicCaller(schematic_tests.Folder, Budgeted):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C5: the schematic caller's declaration states the budget and each unit's needs, which are the documents, the round holding no image
    def test_the_declaration_states_the_budget_and_each_units_needs_and_the_plan_is_within_it(self):
        package = kit_caller.load("schematic", TOOLS).prepare(self.folder)
        declaration, formed = groups(package, self.folder)
        self.assertWithinBudget(declaration, formed, schematic)
        self.assertPackedAsTheKitPacks(declaration, formed)
        self.assertEqual(every_image(declaration), set(), "the sheets' drawings are opened by the reviewer, not held in a root")
        for unit in declaration.units.values():
            self.assertEqual(set(unit.needs), set(declaration.needed))


class TheHeadroomIsStatedWithItsArithmetic(unittest.TestCase):
    def test_each_caller_states_the_same_conservative_headroom_with_the_arithmetic_and_that_a_measured_run_sets_it(self):
        for module in (layout, critical, production, schematic):
            with self.subTest(caller=module.__name__):
                self.assertEqual(module.HEADROOM, 0.4)
                with open(module.__file__, encoding="utf-8") as handle:
                    source = handle.read()
                self.assertIn("(400,000 - 50,000) / 4,400 = 79 images", source)
                self.assertIn("to be set from a measured first run", " ".join(source.split()))
        self.assertEqual(int(costmodel.window_for(MODEL) * 0.4), 400_000)
        self.assertEqual((400_000 - 50_000) // 4_400, 79)


class SelectionByKindNetClassLayerAndRegion(unittest.TestCase):
    INDEX = {"images": [
        {"view": "layer", "file": "layer-F.Cu-r1c1.png", "layers": [{"name": "F.Cu"}], "region_mm": {"x0": 0, "y0": 0, "x1": 30, "y1": 20}},
        {"view": "layer", "file": "layer-F.Cu-r1c2.png", "layers": [{"name": "F.Cu"}], "region_mm": {"x0": 30, "y0": 0, "x1": 60, "y1": 20}},
        {"view": "layer", "file": "layer-B.Cu-r1c1.png", "layers": [{"name": "B.Cu"}], "region_mm": {"x0": 0, "y0": 0, "x1": 30, "y1": 20}},
        {"view": "net", "file": "net-CLK-r1c1.png", "net": "CLK", "classes": ["Clock"], "layers": [{"name": "F.Cu"}],
         "region_mm": {"x0": 0, "y0": 0, "x1": 30, "y1": 20}},
        {"view": "net", "file": "net-GND-r1c2.png", "net": "GND", "classes": ["Ground", "Power"], "layers": [{"name": "F.Cu"}],
         "region_mm": {"x0": 30, "y0": 0, "x1": 60, "y1": 20}},
        {"view": "class map", "file": "classes.png", "classes": [{"name": "Clock", "colour": "red"}, {"name": "Ground"}],
         "layers": [{"name": "F.Cu"}]},
        {"view": "crop", "file": "crop-U1.png", "circuit": "U1", "layers": [{"name": "F.Cu"}], "region_mm": {"x0": 10, "y0": 5, "x1": 20, "y1": 15}},
        {"view": "3d", "file": "3d-top.png"}]}

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C15: each declaring the views it needs by view kind, net, net class, layer and board region taken from the folder's view index and resolved to artefact names
    def test_a_unit_selects_by_each_of_kind_net_class_layer_and_region_and_the_descriptions_narrow_one_another(self):
        pick = lambda **kw: selection.select(self.INDEX, **kw)  # noqa: E731
        self.assertEqual(pick(view="layer"), ["views/layer-B.Cu-r1c1.png", "views/layer-F.Cu-r1c1.png", "views/layer-F.Cu-r1c2.png"])
        self.assertEqual(pick(view=["net", "crop"]), ["views/crop-U1.png", "views/net-CLK-r1c1.png", "views/net-GND-r1c2.png"])
        self.assertEqual(pick(nets="GND"), ["views/net-GND-r1c2.png"])
        self.assertEqual(pick(classes="Power"), ["views/net-GND-r1c2.png"], "a net of two classes is in each")
        self.assertEqual(pick(classes=["Clock"]), ["views/classes.png", "views/net-CLK-r1c1.png"], "a class map is of its classes")
        self.assertEqual(pick(view="layer", layers="B.Cu"), ["views/layer-B.Cu-r1c1.png"])
        self.assertEqual(pick(region=(31, 1, 40, 10)), ["views/layer-F.Cu-r1c2.png", "views/net-GND-r1c2.png"])
        self.assertEqual(pick(view="layer", layers="F.Cu", region=(0, 0, 5, 5)), ["views/layer-F.Cu-r1c1.png"])
        self.assertEqual(pick(fields={"circuit": "U1"}), ["views/crop-U1.png"])
        self.assertEqual(pick(view="3d"), ["views/3d-top.png"])
        self.assertEqual(pick(view="layer", folder="rendered"), ["rendered/layer-B.Cu-r1c1.png", "rendered/layer-F.Cu-r1c1.png",
                                                                  "rendered/layer-F.Cu-r1c2.png"])

    def test_the_names_a_selection_returns_are_artefacts_a_declaration_accepts_and_the_selection_reads_only_the_index(self):
        listed = review_catalogue.views_for.__module__
        self.assertEqual(listed, "review_catalogue")
        with mock.patch("review_kit.selection.read_index", return_value=self.INDEX):
            names = review_catalogue.views_for("a-review-folder", ["layer-<copper layer>", "net-<net>", "classes", "crop-<reference>",
                                                                     "assembly-top", "3d-top", "facts.txt", "placement"])
            literal = review_catalogue.views_for("a-review-folder", ["layer-B.Cu", "net-CLK", "crop-U1"])
        self.assertEqual(names, ["views/3d-top.png", "views/classes.png", "views/crop-U1.png", "views/layer-B.Cu-r1c1.png",
                                 "views/layer-F.Cu-r1c1.png", "views/layer-F.Cu-r1c2.png", "views/net-CLK-r1c1.png",
                                 "views/net-GND-r1c2.png"])
        self.assertEqual(literal, ["views/crop-U1.png", "views/layer-B.Cu-r1c1.png", "views/net-CLK-r1c1.png"])

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C5: Over a synthetic review folder for each of the four callers, the caller's declaration states a model-context budget, each unit declares only the artefacts it needs, its views chosen through the kit's selection from the folder's view index and not by taking the folder's whole view list, and the kit's plan for it gives every group a context within the budget, none holding an artefact that none of its units declares.
    def test_a_placeholder_direction_names_every_three_dimensional_view_and_a_literal_one_names_its_own(self):
        index = {**self.INDEX, "images": self.INDEX["images"] + [{"view": "3d", "file": "3d-bottom.png"}]}
        with mock.patch("review_kit.selection.read_index", return_value=index):
            every = review_catalogue.views_for("a-review-folder", ["3d-<direction>"])
            one = review_catalogue.views_for("a-review-folder", ["3d-bottom"])
        self.assertEqual(every, ["views/3d-bottom.png", "views/3d-top.png"])
        self.assertEqual(one, ["views/3d-bottom.png"])


class TheItemsNamesAreReadFromTheCatalogue(layout_tests.Folder):
    def test_a_units_views_follow_its_items_judged_on_lines_and_a_board_item_follows_its_plans_cell(self):
        names = review_catalogue.judged_on(self.folder, ["FLOOR-1", "GROUND-1"])
        self.assertEqual(names, ["assembly-top", "assembly-bottom", "classes", "placement", "net-<net>", "layer-<copper layer>", "facts.txt"])
        self.assertEqual(review_catalogue.judged_on(self.folder, ["NO-SUCH-ITEM"]), [])
        rules = review_catalogue.declared_rules(self.folder, ["GROUND-1", "FLOOR-1"])
        self.assertEqual(rules, ["clearance_floor"], "only a rule-kind item names check rules")
        self.assertEqual(review_catalogue.declared_rules(self.folder, ["GROUND-1"], known=["WORK-2"]), ["clearance_floor"])
        self.assertEqual(review_catalogue.report_rules("VIOLATION | d | clearance | l | m\nFIGURE | d | WORK-2 | 1 | p | r\nnone\n",
                                                       re.compile(layout.CHECK_RULE)), ["clearance", "WORK-2"])


if __name__ == "__main__":
    unittest.main()


class GoodResultsCoverTheChecklist:
    """A caller's good results, built from its own units and checklist, held to the coverage the command holds a merge to."""

    def assertCovered(self, package, folder, given):
        declaration = package.declaration
        found = catalogue.admit(declaration, folder)
        spec = messages.make_spec(declaration, package.tools, folder, MODEL)
        plan = planner.make_plan(declaration, found, spec, bound=4, cli_version="9.9.9", tool_commit="abc1234")
        holds = {group.id: [item for unit in group.units for item in declaration.units[unit].items] for group in plan.groups}
        order = [group.id for group in plan.groups]
        self.assertEqual(set(declaration.units), set(given), "the results are for the units the caller declares")
        self.assertEqual(sorted(item for items in holds.values() for item in items), sorted(set(package.rules.checklist)),
                         "the groups hold the checklist's items, each once")
        by_group = {}
        for group in plan.groups:
            tables = {}
            for unit in group.units:
                for name, rows in given[unit].items():
                    tables.setdefault(name, []).extend(rows)
            by_group[group.id] = {"r1": tables}
        self.assertEqual(merge.coverage_problems(declaration.shape, package.rules, order, by_group, holds), [])
        victim = order[0]
        item = holds[victim][0]
        dropped = {name: [row for row in rows if row.get("Item") != item] for name, rows in by_group[victim]["r1"].items()}
        problems = merge.coverage_problems(declaration.shape, package.rules, order, {**by_group, victim: {"r1": dropped}}, holds)
        self.assertTrue(any(item in problem for problem in problems), "a group that leaves out an item it holds is caught")


class TheLayoutCallersFullRoundIsCovered(layout_tests.Folder, GoodResultsCoverTheChecklist):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a group's replicas judge the units of the group
    def test_the_good_results_of_a_full_round_pass_the_coverage_with_the_holds_the_plan_gives(self):
        package = kit_caller.load("layout", TOOLS).prepare(self.folder)
        self.assertCovered(package, self.folder, layout_tests.results())


class TheLayoutCallersNarrowRoundIsCovered(layout_tests.Folder, GoodResultsCoverTheChecklist):
    narrow = True
    method = lfx.METHOD_SENSE

    def narrowed(self, items):
        folder = self.copy_of("narrowed")
        lfx.set_round(folder, items=[{"item": item, "reason": f"{item} moved"} for item in items])
        return folder

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a group's replicas judge the units of the group
    def test_the_good_results_of_a_narrow_round_pass_the_coverage_with_the_holds_the_plan_gives(self):
        for items in (["CLOCK-1", "SENSE-2"], ["FLOOR-1", "GROUND-1"], ["FLOOR-1"]):
            with self.subTest(items=items):
                folder = self.narrowed(items)
                package = kit_caller.load("layout", TOOLS).prepare(folder)
                given = {unit: {"Verdicts": [layout_tests.verdict(item) for item in held.items]}
                         for unit, held in package.declaration.units.items()}
                self.assertCovered(package, folder, given)

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a group's replicas judge the units of the group
    def test_a_narrow_round_run_through_the_command_merges_exactly_the_listed_items_in_text_and_json(self):
        folder = self.narrowed(["CLOCK-1", "SENSE-2"])
        run = layout_tests.Command(self, folder)
        run.scenario()
        status, text, err = run.go("--format", "json")
        self.assertEqual((status, err), (0, ""), text)
        report = json.loads(text)
        self.assertEqual([row["Item"] for row in report["tables"]["Verdicts"]["rows"]], ["CLOCK-1", "SENSE-2"])
        self.assertEqual(report["refusals"], [])
        second = layout_tests.Command(self, folder, out="out-text")
        second.scenario()
        status, text, err = second.go()
        self.assertEqual((status, err), (0, ""), text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | WRITTEN"), text)
        self.assertNotIn("REFUSED", text)


class TheCriticalRoutingCallersGoodResultsAreCovered(critical_tests.Folder, GoodResultsCoverTheChecklist):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a group's replicas judge the units of the group
    def test_the_good_results_pass_the_coverage_with_the_holds_the_plan_gives(self):
        package = kit_caller.load("critical_routing", TOOLS).prepare(self.folder)
        self.assertCovered(package, self.folder, critical_tests.results())


class TheSchematicCallersGoodResultsAreCovered(schematic_tests.Folder, GoodResultsCoverTheChecklist):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a group's replicas judge the units of the group
    def test_the_good_results_pass_the_coverage_with_the_holds_the_plan_gives(self):
        package = kit_caller.load("schematic", TOOLS).prepare(self.folder)
        self.assertCovered(package, self.folder, schematic_tests.results())


class TheProductionFilesCallersGoodResultsAreCovered(production_tests.Folder, GoodResultsCoverTheChecklist):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a group's replicas judge the units of the group
    def test_the_good_results_pass_the_coverage_with_the_holds_the_plan_gives(self):
        package = kit_caller.load("production_files", TOOLS).prepare(self.folder)
        self.assertCovered(package, self.folder, production_tests.results(package))
