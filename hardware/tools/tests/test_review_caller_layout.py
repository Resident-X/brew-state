#!/usr/bin/env python3
"""The layout review as a caller of the review kit command, over synthetic review folders.

The caller is loaded as the kit loads it and run as shipped: its declaration, prompts, tool grant, checks and rendering are
exercised through the kit's own functions, and through the kit's command against a stand-in for the agent command line. The
method, the plan, the board and every verdict are synthetic. No model and no KiCad is used, and the real agent command line
is never run.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_history  # noqa: E402
import board_review_history  # noqa: E402
import layout_fixtures as fx  # noqa: E402
import review_caller_layout  # noqa: E402
import review_folder  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import catalogue, command, costmodel, merge, messages, planner  # noqa: E402
from review_kit import results as kit_results  # noqa: E402
from review_kit import executor as ex  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
PLAN_ENTRY = review_caller_layout.PLAN_ENTRY
ITEMS = {"area-FLOOR": ["FLOOR-1", "FLOOR-2"], "area-GROUND": ["GROUND-1"], "area-CLOCK": ["CLOCK-1"]}

STUB = '''#!PYTHON
import json, os, re, sys, uuid
sys.path.insert(0, TOOLS)
from review_kit import executor as ex
args = sys.argv[1:]
with open(os.environ["STUB_SCENARIO"], encoding="utf-8") as handle:
    scenario = json.load(handle)
if args[:2] == ["auth", "status"]:
    print(json.dumps({"loggedIn": True}))
    sys.exit(0)
if args == ["--version"]:
    print("9.9.9 (stub)")
    sys.exit(0)
stdin = sys.stdin.read()


def flag(name):
    return args[args.index(name) + 1] if name in args else None


tools = flag("--tools").split(",") + (["StructuredOutput"] if "--json-schema" in args else [])
model = flag("--model") or "stub-model"
resume = flag("--resume")
session_id = "stub-" + uuid.uuid4().hex[:8]
text = " ".join(block.get("text", "") for block in json.loads(stdin)["message"]["content"] if block.get("type") == "text")
units = re.findall(r"Your unit: (\\S+)", text)
with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"args": args, "tools": flag("--tools"), "cwd": os.getcwd(), "session": session_id, "resume": resume,
                             "fork": "--fork-session" in args, "units": units}) + "\\n")
if resume is None:
    sys.stdout.write(ex.stream_text(session_id, text="ACK", cost=0.01, api_ms=100, turns=1, read=0, write=1000, generated=2,
                                    tools=tools, model=model, cwd=os.getcwd()))
    sys.exit(0)
report = {}
if scenario.get("fork_tools") is not None:
    report["tools"] = scenario["fork_tools"]
if scenario.get("fork_mcp"):
    report["mcp_servers"] = [{"name": "extra", "status": "connected"}]
if scenario.get("fork_cwd"):
    report["cwd"] = scenario["fork_cwd"]
tables = {"Verdicts": [], "Plan and free pass": [], "Findings": []}
round_number = scenario.get("round", 1)
for unit, body in re.findall(r"Your unit: (\\S+)\\n(.*?)(?=Your unit: |\\Z)", text, re.S):
    found = 0
    for item in re.findall(r"^- ([A-Z]+-\\d+)$", body, re.M):
        verdict = scenario.get("verdicts", {}).get(item, "pass")
        why = scenario.get("why", {}).get(item, "Judged on the views.")
        if verdict == "fail":
            found += 1
            why = scenario.get("why", {}).get(item, f"finding {round_number}.{found}")
            tables["Findings"].append({"Finding": found, "Item": item, "Raised by": item, "Severity": "function",
                                       "What and where": f"layer-F.Cu at ({found}, {found}): off its place", "Rule": "no",
                                       "Added as": "", "Planning shortfall": "—", "Closed by": ""})
        tables["Verdicts"].append({"Item": item, "Kind": "judgement", "Severity": "function", "Verdict": verdict,
                                   "Rests on": "layer-F.Cu", "Why": why})
    tables["Findings"] += scenario.get("findings", {}).get(unit, [])
    if unit == "plan-and-free-pass":
        verdict = scenario.get("verdicts", {}).get("PLAN-AND-FREE-PASS", "pass")
        tables["Verdicts"].append({"Item": "PLAN-AND-FREE-PASS", "Kind": "comparison", "Severity": "—", "Verdict": verdict,
                                   "Rests on": "the plan", "Why": scenario.get("why", {}).get("PLAN-AND-FREE-PASS", "Compared.")})
        tables["Plan and free pass"] += [{"Note": note} for note in scenario.get("notes", ["Compared the plan with the layout."])]
sys.stdout.write(ex.stream_text(session_id, text="done", structured={"tables": tables}, cost=0.03, api_ms=300, turns=1,
                                read=1000, write=200, generated=50, tools=report.get("tools", tools), model=model,
                                cwd=report.get("cwd", os.getcwd()), mcp_servers=report.get("mcp_servers", ())))
'''


def verdict(item, outcome="pass", why="Judged on the views.", rests="layer-F.Cu", kind="judgement"):
    return {"Item": item, "Kind": kind, "Severity": "function", "Verdict": outcome, "Rests on": rests, "Why": why}


def finding(number, item, what="layer-F.Cu at (10, 10): a part is off its place", raised=None):
    return {"Finding": number, "Item": item, "Raised by": raised or item, "Severity": "function", "What and where": what,
            "Rule": "no", "Added as": "", "Planning shortfall": "—", "Closed by": ""}


def note(text):
    return {"Note": text}


def results(items=ITEMS, plan_notes=("Compared every region with the plan; the free pass found nothing else.",), **extra):
    """A synthetic result for every unit of a full round with no board items: every item passes."""
    found = {unit: {"Verdicts": [verdict(item) for item in ids]} for unit, ids in items.items()}
    found["plan-and-free-pass"] = {"Verdicts": [verdict(PLAN_ENTRY, kind="comparison")],
                                   "Plan and free pass": [note(text) for text in plan_notes]}
    for unit, tables in extra.items():
        found[unit.replace("_", "-")] = tables
    return found


#: The couplings the synthetic catalogue is planned with: its areas are not the real ones, so the pairs are the test's own.
SYNTHETIC_COUPLED = (("FLOOR", "GROUND"), ("CLOCK", "FLOOR"))
real_load = kit_caller.load


def load_with_synthetic_couplings(name, folder):
    """The caller as the kit loads it, its couplings those of the synthetic catalogue."""
    loaded = real_load(name, folder)
    loaded.module.COUPLED = SYNTHETIC_COUPLED
    return loaded


def prepared(folder):
    return kit_caller.load("layout", TOOLS).prepare(folder)


def merged(folder, given, order=None, replicas=None):
    """The unit results merged as the command merges them, each unit one replica unless `replicas` gives more."""
    return prepared(folder).merge(order or list(given), {unit: replicas.get(unit, {"r1": tables}) if replicas else {"r1": tables}
                                                         for unit, tables in given.items()})


def rendered(folder, given, number=1):
    package = prepared(folder)
    out = package.merge(list(given), {unit: {"r1": tables} for unit, tables in given.items()})
    return package.render(merge.plain_tables(out))[f"round-{number}.md"]


def slurp(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Folder(unittest.TestCase):
    """A review folder the folder command wrote from a synthetic repository, in a temporary folder."""

    own = fx.OWN_NONE
    narrow = False
    number = 1
    method = fx.METHOD

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="layout-caller-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.folder = self.write_folder(self.root)
        patched = mock.patch.object(kit_caller, "load", load_with_synthetic_couplings)
        patched.start()
        self.addCleanup(patched.stop)

    def write_folder(self, root, number=None, narrow=None, own=None, method=None, extra=None):
        repo = fx.make_repo(root, own if own is not None else self.own, method=method or self.method)
        inputs = fx.make_views(root)
        out = os.path.join(root, "review-folder")
        narrow = self.narrow if narrow is None else narrow
        status, text = fx.run_folder(fx.folder_argv(repo, out, inputs, number or self.number, "narrow" if narrow else "full",
                                                    extra=(fx.NARROW if narrow else []) + list(extra or ())))
        self.assertEqual(status, 0, text)
        return out

    def refused(self, call, *words):
        with self.assertRaises(merge.Refused) as caught:
            call()
        text = "; ".join(caught.exception.causes)
        for word in words:
            self.assertIn(word, text)
        return text

    def copy_of(self, name="broken"):
        folder = os.path.join(self.root, name)
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(self.folder, folder)
        return folder


class TheUnits(Folder):
    def test_the_declaration_gives_one_unit_per_catalogue_area_and_one_for_the_plan_and_the_free_pass(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        package = prepared(self.folder)
        self.assertEqual(list(package.declaration.units), ["area-FLOOR", "area-GROUND", "area-CLOCK", "plan-and-free-pass"])
        self.assertEqual({unit: list(item.items) for unit, item in package.declaration.units.items()},
                         {**ITEMS, "plan-and-free-pass": [PLAN_ENTRY]})
        self.assertEqual(package.checklist, ("FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1", PLAN_ENTRY))

    def test_the_board_items_unit_is_there_when_the_plans_table_has_rows_and_stands_before_the_plan_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        folder = self.write_folder(os.path.join(self.root, "own"), own=fx.OWN_ROWS)
        package = prepared(folder)
        self.assertEqual(list(package.declaration.units), ["area-FLOOR", "area-GROUND", "area-CLOCK", "board-items",
                                                           "plan-and-free-pass"])
        self.assertEqual(list(package.declaration.units["board-items"].items), ["BOARD-1", "BOARD-2"])
        self.assertEqual(package.checklist[-3:], ("BOARD-1", "BOARD-2", PLAN_ENTRY))
        self.assertEqual(package.declaration.units["board-items"].couples_with, (), "the board's own items are coupled with no area")
        self.assertNotIn("board-items", prepared(self.folder).declaration.units)

    def test_the_units_are_planned_into_groups_with_each_coupled_set_in_one_group(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        declaration = prepared(self.folder).declaration
        self.assertEqual(declaration.units["area-FLOOR"].couples_with, ("area-GROUND", "area-CLOCK"))
        self.assertEqual(declaration.units["area-GROUND"].couples_with, ("area-FLOOR",))
        self.assertEqual(declaration.units["plan-and-free-pass"].couples_with, ())
        groups = planner.pack(declaration)
        self.assertEqual(groups, [["area-FLOOR", "area-GROUND", "area-CLOCK"], ["plan-and-free-pass"]])

    def test_a_coupling_the_declaration_states_that_no_cross_reference_of_the_catalogue_supports_fails_the_test(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        linked = fx.METHOD_SENSE.replace("#### CLOCK-1. The crystal sits at its pins\n",
                                         "#### CLOCK-1. The crystal sits at its pins\n\nIt reads `FLOOR-2`.\n")
        linked = linked.replace("#### GROUND-1. Ground is a plane\n", "#### GROUND-1. Ground is a plane\n\nIt reads `FLOOR-1`.\n")
        folder = self.write_folder(os.path.join(self.root, "linked"), method=linked)
        self.assertEqual(self.unsupported_couplings(folder), [], "each declared coupling has a cross-reference behind it")
        self.assertEqual(self.unsupported_couplings(self.folder), [("CLOCK", "FLOOR"), ("FLOOR", "GROUND")],
                         "a catalogue that links nothing supports none of the declared couplings")
        unlinked = linked.replace("It reads `FLOOR-2`.", "It reads the floor.")
        folder = self.write_folder(os.path.join(self.root, "unlinked"), method=unlinked)
        self.assertEqual(self.unsupported_couplings(folder), [("CLOCK", "FLOOR")], "one coupling lost its cross-reference")
        loaded = kit_caller.load("layout", TOOLS)
        loaded.module.COUPLED = ()
        self.assertEqual(self.unsupported_couplings(folder, loaded), [], "a coupling not declared cannot be unsupported")

    def test_a_cross_reference_alone_does_not_make_a_coupling(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        method = fx.METHOD_SENSE.replace("#### CLOCK-1. The crystal sits at its pins\n",
                                         "#### CLOCK-1. The crystal sits at its pins\n\nIt reads `SENSE-1` and `FLOOR-2`.\n")
        folder = self.write_folder(os.path.join(self.root, "linked"), method=method)
        self.assertIn(("CLOCK", "SENSE"), self.links(slurp(os.path.join(folder, "docs", "board-design-method.md"))))
        package = prepared(folder)
        self.assertEqual(package.declaration.units["area-CLOCK"].couples_with, ("area-FLOOR",))
        self.assertEqual(package.declaration.units["area-SENSE"].couples_with, ())
        self.assertEqual(planner.pack(package.declaration), [["area-FLOOR", "area-GROUND", "area-CLOCK"], ["area-SENSE"],
                                                             ["plan-and-free-pass"]], "the linked area stays in its own group")

    def test_every_coupling_the_declaration_states_has_a_cross_reference_in_the_real_catalogue(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        method = slurp(os.path.join(REPO, "docs", "board-design-method.md"))
        folder = self.copy_of("real")
        fx.write(os.path.join(folder, "docs", "board-design-method.md"), method)
        links = self.links(method)
        self.assertGreaterEqual(len(links), 5, "the real catalogue cross-references several areas")
        real = real_load("layout", TOOLS)
        self.assertEqual(sorted(tuple(sorted(pair)) for pair in real.module.COUPLED),
                         [("MAINS", "POWER"), ("MFG", "POWER")])
        self.assertEqual(self.unsupported_couplings(folder, real), [])
        groups = planner.pack(real.prepare(folder).declaration)
        where = {unit: number for number, units in enumerate(groups) for unit in units}
        for first, second in real.module.COUPLED:
            self.assertEqual(where[f"area-{first}"], where[f"area-{second}"], f"{first} and {second} are judged together")

    def test_the_real_method_plans_at_least_six_groups_and_the_largest_is_within_the_wall_budget(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        method = slurp(os.path.join(REPO, "docs", "board-design-method.md"))
        folder = self.copy_of("real")
        fx.write(os.path.join(folder, "docs", "board-design-method.md"), method)
        declaration = real_load("layout", TOOLS).prepare(folder).declaration
        groups = planner.pack(declaration)
        self.assertGreaterEqual(len(groups), 6, f"the groups are {[len(group) for group in groups]}")
        timing = costmodel.Timing()
        seconds = [timing.seconds(costmodel.CALLS_PER_FORK, sum(declaration.units[unit].expected_output_tokens for unit in group))
                   for group in groups]
        self.assertLessEqual(max(seconds), declaration.budget.wall_s,
                             f"the largest group {max(groups, key=len)} is expected to take {max(seconds):.0f} s")

    def links(self, method):
        """The pairs of areas the catalogue's items cross-reference by identifier, each pair in sorted order."""
        section = board_history.LAYOUT_CATALOGUE.search(method).group(1)
        codes = set(re.findall(r"^### .+ \(([A-Z]+)\)[ \t]*$", section, re.M))
        current, found = None, set()
        for line in section.split("\n"):
            heading = review_caller_layout.AREA.match(line)
            if heading:
                current = heading.group(2)
            elif current:
                for cited in re.finditer(r"\b([A-Z]+)-\d+\b", line):
                    if cited.group(1) in codes and cited.group(1) != current:
                        found.add(tuple(sorted((current, cited.group(1)))))
        return sorted(found)

    def unsupported_couplings(self, folder, loaded=None):
        """The couplings the caller declares between two areas of the folder's method that no cross-reference of its catalogue
        links, each pair in sorted order."""
        loaded = loaded or kit_caller.load("layout", TOOLS)
        units = loaded.prepare(folder).declaration.units
        links = self.links(slurp(os.path.join(folder, "docs", "board-design-method.md")))
        declared = {tuple(sorted((unit[len("area-"):], other[len("area-"):])))
                    for unit, found in units.items() for other in found.couples_with}
        return sorted(pair for pair in declared if pair not in links)

    def test_the_shared_context_holds_the_whole_catalogue_and_each_prompt_only_its_own_area_and_items(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        package = prepared(self.folder)
        shared = messages.shared_context(catalogue.admit(package.declaration, self.folder)).message
        for held in ("### Floorplan (FLOOR)", "#### FLOOR-2.", "### Grounding (GROUND)", "#### GROUND-1.", "### Clocks (CLOCK)",
                     "#### CLOCK-1.", "Intro of the catalogue.", "Steps of a review.", "Views of a review.", "LAYOUT FACTS",
                     "=== image: views/layer-F.Cu.png ===", "=== image: placement/placement.png ===", "round.json"):
            self.assertIn(held, shared)
        for unit in package.declaration.units:
            self.assertNotIn(f"Your unit: {unit}", shared, "no unit's prompt is in the shared context")
        floor = package.unit_text("area-FLOOR")
        self.assertIn("### Floorplan (FLOOR)", floor)
        self.assertIn("- FLOOR-1\n- FLOOR-2", floor)
        for other in ("GROUND-1", "CLOCK-1", "### Grounding", "### Clocks"):
            self.assertNotIn(other, floor)
        self.assertIn("Your unit: area-FLOOR", floor)
        plan = package.unit_text("plan-and-free-pass")
        self.assertIn(PLAN_ENTRY, plan)
        for area in ("### Floorplan", "FLOOR-1", "GROUND-1", "CLOCK-1"):
            self.assertNotIn(area, plan, "the comparison unit carries no area block")

    def test_the_shared_context_artefacts_are_the_folders_extracts_records_and_every_image(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        declaration = prepared(self.folder).declaration
        design = fx.DESIGN
        self.assertEqual(sorted(declaration.artefacts), sorted([
            "check-report.txt", "layout-facts.txt", "method-extract.md", "placement/index.txt", "placement/measures.txt",
            "placement/placement.png", "round.json", "views/facts.txt", "views/index.txt", "views/layer-F.Cu.png",
            f"{design}/constraints.md", f"{design}/design-rules.md", f"{design}/layout-plan.md",
            f"{design}/separation-basis.yaml"]))
        self.assertEqual({name: artefact.kind for name, artefact in declaration.artefacts.items() if artefact.kind != "text"},
                         {"layout-facts.txt": "extract", "method-extract.md": "extract", "placement/placement.png": "image",
                          "views/layer-F.Cu.png": "image"})
        self.assertEqual(declaration.added_during_round, ("added-views/*",))
        self.assertEqual(declaration.budget.wall_s, 350)
        self.assertEqual(set(declaration.needed), set(declaration.artefacts))
        for held in fx.BOARD_FILES:
            self.assertNotIn(held, declaration.artefacts if held.endswith(("kicad_pcb", "kicad_sch")) else (), "no board file")

    def test_a_later_round_names_its_record_and_holds_it_in_the_shared_context(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        folder = self.write_folder(os.path.join(self.root, "later"), number=2)
        package = prepared(folder)
        self.assertIn(f"{fx.DESIGN}/layout-review.md", package.declaration.artefacts)
        self.assertNotIn(f"{fx.DESIGN}/layout-review.md", prepared(self.folder).declaration.artefacts)
        text = package.unit_text("area-FLOOR")
        self.assertIn("This is round 2", text)
        self.assertIn("finding 2.<n>", text)
        self.assertNotIn("This is round", prepared(self.folder).unit_text("area-FLOOR"))

    def test_the_real_method_gives_a_unit_for_each_of_its_catalogue_areas(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        method = slurp(os.path.join(REPO, "docs", "board-design-method.md"))
        folder = self.copy_of("real")
        fx.write(os.path.join(folder, "docs", "board-design-method.md"), method)
        found = review_caller_layout.areas(folder)
        self.assertEqual([item for _, _, ids in found for item in ids], list(board_history.catalogue(method)))
        self.assertGreater(len(found), 1)
        self.assertTrue(all(ids for _, _, ids in found), "an area heading of the real method holds no item")
        self.assertEqual(list(prepared(folder).declaration.units), [f"area-{code}" for code, _, _ in found] + ["plan-and-free-pass"])

    def test_a_method_with_no_catalogue_areas_or_lacking_a_section_is_refused_naming_what_is_missing(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        method = os.path.join(self.folder, "docs", "board-design-method.md")
        text = slurp(method)
        fx.write(method, re.sub(r"^### (Floorplan|Grounding|Clocks) \(\w+\)$", r"### \1", text, flags=re.M))
        self.refused(lambda: prepared(self.folder), "no catalogue area heading")
        fx.write(method, text.replace("## Layout practice catalogue", "## Something else"))
        self.refused(lambda: prepared(self.folder), "no `## Layout practice catalogue` section")
        for heading in ("Layout review", "Layout review views"):
            fx.write(method, text.replace(f"## {heading}\n", "## Something else\n"))
            self.refused(lambda: prepared(self.folder), f"no `## {heading}` section", "shared context")
        fx.write(method, text)
        os.remove(method)
        self.refused(lambda: prepared(self.folder), "no readable method")

    def test_a_folder_lacking_an_extract_or_an_index_or_a_view_or_the_extracts_section_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        for path, word in (("layout-facts.txt", "holds no layout-facts.txt"), ("method-extract.md", "holds no method-extract.md"),
                           ("check-report.txt", "holds no check-report.txt"), ("views/index.txt", "holds no views/index.txt"),
                           ("placement/index.txt", "holds no placement/index.txt"),
                           (f"{fx.DESIGN}/layout-plan.md", "no readable plan")):
            with self.subTest(path=path):
                folder = self.copy_of()
                os.remove(os.path.join(folder, path))
                self.refused(lambda: prepared(folder), word)
        folder = self.copy_of()
        fx.write(os.path.join(folder, "method-extract.md"), "# only a heading\n## Layout review\n")
        self.refused(lambda: prepared(folder), "method extract", "no `## Layout review views` section")
        folder = self.copy_of()
        os.remove(os.path.join(folder, "views", "layer-F.Cu.png"))
        os.remove(os.path.join(folder, "placement", "placement.png"))
        self.refused(lambda: prepared(folder), "holds no rendered view image")

    def test_a_plan_whose_table_of_own_items_cannot_be_read_is_refused_naming_what_is_missing(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        plan = os.path.join(self.folder, fx.DESIGN, "layout-plan.md")
        good = fx.plan(fx.OWN_ROWS)
        for name, text, word in (
                ("no table", good.split("### The board's own items")[0], "holds no table of the board's own items"),
                ("no divider", good.replace("|---|---|---|---|---|---|---|---|---|---|\n", ""), "has no divider row"),
                ("a short row", fx.plan("| BOARD-1 | always |"), "has 2 cells where the header has 10"),
                ("a foreign item", fx.plan(fx.OWN_ROWS.replace("BOARD-2", "FLOOR-9")), "not BOARD-<n> or `none`"),
                ("an item twice", fx.plan(fx.OWN_ROWS.replace("BOARD-2", "BOARD-1")), "an item is given twice")):
            with self.subTest(name=name):
                fx.write(plan, text)
                self.refused(lambda: prepared(self.folder), word)

    def test_a_folder_that_holds_no_one_design_or_no_round_file_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        fx.write(os.path.join(self.folder, "second", "other.kicad_pro"), "{}")
        self.refused(lambda: prepared(self.folder), "holds 2 KiCad project files")
        shutil.rmtree(os.path.join(self.folder, "second"))
        os.remove(os.path.join(self.folder, review_folder.ROUND_FILE))
        self.refused(lambda: prepared(self.folder), "round file", "cannot be read")

    def test_a_loaded_caller_meets_the_kits_contract(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        loaded = kit_caller.load("layout", TOOLS)
        for attribute in kit_caller.REQUIRED + ("retrieval", "checklist", "place", "round_label", "earlier_findings"):
            self.assertTrue(hasattr(loaded.module, attribute), attribute)
        self.assertEqual(command.POLICY_ATTRIBUTE, "replica_policy")
        policy = command.ensemble.parse_policy(loaded.module.replica_policy)
        self.assertEqual(policy.ids, ["full", "hunt"])
        self.assertEqual(dict(policy.by_stakes), {"low": 1, "normal": 2, "high": 3})
        self.assertEqual(prepared(self.folder).declaration.budget.wall_s, 350)


class TheNarrowRound(Folder):
    narrow = True
    method = fx.METHOD_SENSE

    def narrow_folder(self, name, items, **changes):
        folder = self.copy_of(name)
        fx.set_round(folder, items=[{"item": item, "reason": f"{item} moved"} for item in items], **changes)
        return folder

    def test_the_units_are_the_areas_the_listed_items_fall_in_and_in_two_groups_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two groups, the caller has a unit for each of the two groups and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one group is judged by a fork of the shared context. Out of scope: how the designer chooses the listed items.
        folder = self.narrow_folder("two", ["CLOCK-1", "SENSE-2"])
        declaration = prepared(folder).declaration
        self.assertEqual({unit: list(item.items) for unit, item in declaration.units.items()},
                         {"area-CLOCK": ["CLOCK-1"], "area-SENSE": ["SENSE-2"]}, "no unit for the other areas or the free pass")
        self.assertEqual(planner.pack(declaration), [["area-CLOCK"], ["area-SENSE"]], "the two fall in two groups")

    def test_each_units_prompt_names_only_its_listed_items(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two groups, the caller has a unit for each of the two groups and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one group is judged by a fork of the shared context. Out of scope: how the designer chooses the listed items.
        folder = self.narrow_folder("prompts", ["FLOOR-1", "SENSE-2"])
        package = prepared(folder)
        floor, sense = package.unit_text("area-FLOOR"), package.unit_text("area-SENSE")
        self.assertIn("This round is narrow", floor)
        self.assertIn("- FLOOR-1: FLOOR-1 moved", floor)
        self.assertIn("#### FLOOR-1.", floor)
        for unlisted in ("FLOOR-2", "GROUND-1", "CLOCK-1", "SENSE-1", "SENSE-2"):
            self.assertNotIn(unlisted, floor)
        self.assertIn("- SENSE-2: SENSE-2 moved", sense)
        self.assertIn("#### SENSE-2.", sense)
        for unlisted in ("SENSE-1", "FLOOR-1", "FLOOR-2", "CLOCK-1", "GROUND-1"):
            self.assertNotIn(unlisted, sense)

    def test_the_merge_accepts_a_verdict_only_for_a_listed_item(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two groups, the caller has a unit for each of the two groups and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one group is judged by a fork of the shared context. Out of scope: how the designer chooses the listed items.
        folder = self.narrow_folder("accepts", ["CLOCK-1", "SENSE-2"])
        given = {"area-CLOCK": {"Verdicts": [verdict("CLOCK-1")]}, "area-SENSE": {"Verdicts": [verdict("SENSE-2")]}}
        self.assertEqual([row["Item"] for row in merged(folder, given)["tables"]["Verdicts"]["rows"]], ["CLOCK-1", "SENSE-2"])
        given["area-CLOCK"]["Verdicts"].append(verdict("CLOCK-9"))
        text = self.refused(lambda: merged(folder, given), "a verdict row for CLOCK-9, which this round does not judge",
                            "an item the narrow round lists")
        self.assertNotIn("SENSE-2", text)
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1"), verdict(PLAN_ENTRY, kind="comparison")]
        self.refused(lambda: merged(folder, given), f"a verdict row for {PLAN_ENTRY}, which this round does not judge")
        given["area-CLOCK"]["Verdicts"], given["area-SENSE"]["Verdicts"] = [], [verdict("SENSE-2")]
        self.refused(lambda: merged(folder, given), "item CLOCK-1 has no verdict row", "unit area-CLOCK")

    def test_a_listed_item_that_is_no_item_of_the_checklist_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two groups, the caller has a unit for each of the two groups and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one group is judged by a fork of the shared context. Out of scope: how the designer chooses the listed items.
        folder = self.narrow_folder("unknown", ["FLOOR-1", "NOPE-9"])
        self.refused(lambda: prepared(folder), "lists NOPE-9", "no item of the catalogue")

    def test_a_narrow_round_in_one_group_is_judged_by_a_fork_of_the_shared_context_like_any_other(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two groups, the caller has a unit for each of the two groups and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one group is judged by a fork of the shared context. Out of scope: how the designer chooses the listed items.
        folder = self.narrow_folder("one", ["FLOOR-1", "GROUND-1"])
        declaration = prepared(folder).declaration
        self.assertEqual(planner.pack(declaration), [["area-FLOOR", "area-GROUND"]])
        run = Command(self, folder)
        run.scenario()
        status, text, _ = run.go("--format", "json")
        report = json.loads(text)
        self.assertEqual(status, 0, text)
        self.assertEqual(len(report["plan"]["groups"]), 1)
        self.assertEqual(report["plan"]["groups"][0]["units"], ["area-FLOOR", "area-GROUND"])
        calls = run.calls()
        roots = [call for call in calls if call["resume"] is None]
        forks = [call for call in calls if call["resume"] is not None]
        self.assertEqual(len(roots), 1)
        self.assertEqual(len(forks), 2, "the group's two replicas")
        for fork in forks:
            self.assertTrue(fork["fork"])
            self.assertEqual(fork["resume"], roots[0]["session"], "a fork of the shared context")
            self.assertEqual(fork["units"], ["area-FLOOR", "area-GROUND"])
        self.assertEqual([row["Item"] for row in report["tables"]["Verdicts"]["rows"]], ["FLOOR-1", "GROUND-1"])

    def test_a_narrow_round_never_asks_for_the_comparison_with_the_plan(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C2: From a synthetic narrow round whose listed items fall in two groups, the caller has a unit for each of the two groups and none for the rest, each unit's prompt names only its listed items, and the merge accepts a verdict only for a listed item; a narrow round whose items fall in one group is judged by a fork of the shared context. Out of scope: how the designer chooses the listed items.
        folder = self.narrow_folder("noplan", ["FLOOR-1"])
        self.assertNotIn("plan-and-free-pass", prepared(folder).declaration.units)
        self.assertEqual(prepared(folder).checklist[-1], PLAN_ENTRY)


class TheBoardsOwnItems(Folder):
    own = fx.OWN_ROWS

    def test_the_merge_gives_the_board_items_one_verdict_each_after_the_catalogues(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results(**{"board_items": {"Verdicts": [verdict("BOARD-1")]}})
        units = list(ITEMS) + ["board-items", "plan-and-free-pass"]
        self.assertIn("item BOARD-2 has no verdict row", self.refused(lambda: merged(self.folder, given, order=units)))
        given["board-items"]["Verdicts"].append(verdict("BOARD-2"))
        order = [row["Item"] for row in merged(self.folder, given, order=units)["tables"]["Verdicts"]["rows"]]
        self.assertEqual(order, ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1", "BOARD-1", "BOARD-2", PLAN_ENTRY])

    def test_the_board_items_unit_prompt_names_the_plan_table_and_holds_no_area_block(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C1: From a synthetic review folder the caller's declaration gives one unit per area heading of the folder's layout practice catalogue, one for the board's own items when the plan's table has rows, and one for the comparison with the plan and the free pass, with the couplings it states, and the units are planned into groups with each coupled set in one group; a coupling the declaration states that no cross-reference of the catalogue supports fails the test, a cross-reference alone does not make a coupling, and the declared couplings (power with mains and the manufacturing items with power, whose item MFG-5 cites a power finding) leave at least six groups, the largest within the declared time budget; the shared context holds the whole catalogue, and each unit's prompt holds its own area and the items to judge; a folder whose method has no catalogue areas or lacks a section the shared context needs, or whose plan's table cannot be read, is refused naming what is missing. Out of scope: the content of any catalogue item and the narrow round's units.
        text = prepared(self.folder).unit_text("board-items")
        self.assertIn("- BOARD-1\n- BOARD-2", text)
        self.assertIn(f"{fx.DESIGN}/layout-plan.md", text)
        for area in ("### Floorplan", "FLOOR-1", "### Clocks"):
            self.assertNotIn(area, text)


class TheMerge(Folder):
    def test_a_full_round_merges_one_verdict_for_every_item_in_the_checklist_order(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        out = merged(self.folder, dict(reversed(list(results().items()))), order=list(results()))
        self.assertEqual([row["Item"] for row in out["tables"]["Verdicts"]["rows"]],
                         ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1", PLAN_ENTRY])

    def test_an_item_with_no_verdict_row_and_an_item_with_two_fail_the_merge_naming_each(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1"), verdict("GROUND-1", "pass", "Judged again.")]
        text = self.refused(lambda: merged(self.folder, given), "item FLOOR-2 has no verdict row")
        self.assertIn("item GROUND-1 has 2 verdict rows", text)
        self.assertIn("judge it in unit area-FLOOR and run that unit again with --rerun", text)
        package = prepared(self.folder)
        twice = {"Verdicts": [verdict("GROUND-1"), verdict("GROUND-1", "pass", "Judged again.")]}
        problems = [problem.what for problem in kit_results.assess({"tables": twice}, "", package.declaration.shape, "area-GROUND", ["GROUND-1"], "1").problems]
        self.assertEqual(problems, ["gives item 'GROUND-1' 2 verdicts"], "and a unit that gives one item two rows is sent back by the kit")

    def test_the_comparison_unit_gives_its_one_verdict_row_and_a_second_units_row_for_an_item_fails_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["plan-and-free-pass"]["Verdicts"] = []
        self.refused(lambda: merged(self.folder, given), f"item {PLAN_ENTRY} has no verdict row", "unit plan-and-free-pass")
        given = results()
        given["area-CLOCK"]["Verdicts"].append(verdict("MISC-7"))
        given["area-FLOOR"]["Verdicts"].append(verdict("CLOCK-1"))
        text = self.refused(lambda: merged(self.folder, given), "a verdict row for MISC-7", "item CLOCK-1 has 2 verdict rows")
        self.assertIn("an item of the checklist", text)

    def test_a_round_whose_fields_are_missing_or_malformed_fails_naming_each_before_any_session_starts(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        for changes, word in (({"number": None}, "the round's number is None"), ({"number": 0}, "the round's number is 0"),
                              ({"number": "1"}, "the round's number is '1'"), ({"kind": None}, "the round's kind is None"),
                              ({"kind": "Full"}, "the round's kind is 'Full'"), ({"commit": None}, "the commit judged is None"),
                              ({"commit": "not a sha"}, "the commit judged is 'not a sha'"),
                              ({"views": None}, "the views are None"), ({"views": []}, "the views are []"),
                              ({"views": ["a\nb"]}, "the views are ['a\\nb']"),
                              ({"check": None}, "the pre-order check's lines are None"),
                              ({"check": ["VIOLATION | x | a | b | c"]}, "no DESIGN line"),
                              ({"check": ["RESULT | PASS"]}, "the pre-order check's lines are ['RESULT | PASS']")):
            with self.subTest(changes=changes):
                folder = self.copy_of()
                fx.set_round(folder, **changes)
                self.refused(lambda: prepared(folder), word, "missing or malformed")

    def test_a_narrow_round_missing_its_reasons_regions_or_why_others_line_fails_naming_each(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        fx.set_round(self.folder, kind="narrow", items=[{"item": "FLOOR-1", "reason": "r"}], regions=["a region"], others="why")
        given = {"area-FLOOR": {"Verdicts": [verdict("FLOOR-1")]}}
        self.assertEqual(len(merged(self.folder, given)["tables"]["Verdicts"]["rows"]), 1)
        for changes, word in (({"items": [{"item": "FLOOR-1", "reason": ""}]}, "a narrow round's listed items are"),
                              ({"regions": None}, "a narrow round's changed regions are None"),
                              ({"others": None}, "line saying why every other item is not judged is None")):
            with self.subTest(changes=changes):
                folder = self.copy_of()
                fx.set_round(folder, **changes)
                self.refused(lambda: prepared(folder), word)

    def test_findings_are_numbered_item_units_first_in_the_checklist_order_then_the_plan_unit_in_its_own(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "Finding 1.2."), verdict("FLOOR-2", "fail", "Finding 1.1.")],
                               "Findings": [finding(1, "FLOOR-2", "layer-F.Cu at (1, 1): second item's finding"),
                                            finding(2, "FLOOR-1", "layer-F.Cu at (2, 2): first item's finding")]}
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1", "layer-F.Cu at (3, 3): clock's finding")]
        given["plan-and-free-pass"]["Findings"] = [
            finding(1, PLAN_ENTRY, "layer-B.Cu at (4, 4): the free pass saw this first", "free pass"),
            finding(2, PLAN_ENTRY, "layer-B.Cu at (5, 5): then this", "plan, row FLOOR-1")]
        out = merged(self.folder, given)
        rows = out["tables"]["Findings"]["rows"]
        self.assertEqual([(row["Finding"], row["Item"]) for row in rows],
                         [(1, "FLOOR-1"), (2, "FLOOR-2"), (3, "CLOCK-1"), (4, PLAN_ENTRY), (5, PLAN_ENTRY)])
        self.assertEqual([row["What and where"].split(": ")[1] for row in rows[3:]], ["the free pass saw this first", "then this"])
        by_item = {row["Item"]: row["Why"] for row in out["tables"]["Verdicts"]["rows"]}
        self.assertEqual((by_item["FLOOR-1"], by_item["FLOOR-2"]), ("Finding 1.1.", "Finding 1.2."), "the citations follow the renumbering")

    def test_two_findings_citing_one_view_and_place_are_reported_and_both_kept(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1", "On crop-U4 at (74.675, 19.0) the capacitor is far from its pin")]
        given["plan-and-free-pass"]["Findings"] = [
            finding(1, PLAN_ENTRY, "crop-U4 shows a capacitor at (74.675, 19) stranded", "free pass"),
            finding(2, PLAN_ENTRY, "crop-U4 shows a capacitor at (60, 19) apart from its pin", "free pass")]
        out = merged(self.folder, given)
        self.assertEqual(len(out["tables"]["Findings"]["rows"]), 3, "neither finding is dropped")
        self.assertEqual(out["same_place"], [{"key": "crop-U4 (74.675, 19)", "findings": [1, 2], "units": ["area-CLOCK", "plan-and-free-pass"]}])

    def test_findings_that_name_no_view_or_no_place_are_not_taken_to_concern_one_place(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        for first, second in (("whole board, no view named", "whole board, no view named"),
                              ("crop-U4 at (1, 1)", "layer-F.Cu at (1, 1)"), ("crop-U4 at (1, 1)", "crop-U4 at (1, 2)"),
                              ("crop-U4 only", "crop-U4 only")):
            given = results()
            given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1", first)]
            given["plan-and-free-pass"]["Findings"] = [finding(1, PLAN_ENTRY, second, "free pass")]
            self.assertEqual(merged(self.folder, given)["same_place"], [], (first, second))

    def test_two_replicas_raising_the_same_finding_are_one_finding_and_a_fail_by_either_stands(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        row = verdict("FLOOR-1", "fail", "Finding 1.1.")
        replicas = {"area-FLOOR": {
            "r1": {"Verdicts": [row, verdict("FLOOR-2")], "Findings": [finding(1, "FLOOR-1")]},
            "r2": {"Verdicts": [verdict("FLOOR-1"), verdict("FLOOR-2")]}}}
        given = results()
        out = merged(self.folder, given, replicas=replicas)
        floor = {r["Item"]: (r["Verdict"], by) for r, by in zip(out["tables"]["Verdicts"]["rows"], out["tables"]["Verdicts"]["raised_by"])}
        self.assertEqual(floor["FLOOR-1"], ("fail", ["r1"]), "a fail by one replica stands")
        self.assertEqual(len(out["tables"]["Findings"]["rows"]), 1)

    def test_a_rule_kind_verdict_is_not_judged_by_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-GROUND"]["Verdicts"] = [{**verdict("GROUND-1"), "Kind": "rule", "Rests on": "nothing the method names", "Why": "pass"}]
        rows = merged(self.folder, given)["tables"]["Verdicts"]["rows"]
        self.assertEqual([row["Rests on"] for row in rows if row["Item"] == "GROUND-1"], ["nothing the method names"])

    def test_a_cannot_judge_fails_the_round_naming_the_item_and_the_view_its_why_asks_for(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = results()
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "needs crop-Y1: the views show no crop of the crystal")]
        self.refused(lambda: merged(self.folder, given), "item CLOCK-1 is still cannot judge", "asks for crop-Y1",
                     "render that view", "--add-view", "unit area-CLOCK", "--rerun")
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "the views do not show it")]
        self.assertIn("'the views do not show it'", self.refused(lambda: merged(self.folder, given),
                                                                 "item CLOCK-1 is still cannot judge"))
        given = results()
        given["plan-and-free-pass"]["Verdicts"] = [verdict(PLAN_ENTRY, "cannot judge", "needs crop-U1: none", kind="comparison")]
        self.refused(lambda: merged(self.folder, given), f"item {PLAN_ENTRY} is still cannot judge", "unit plan-and-free-pass")

    def test_a_cannot_judge_in_a_narrow_round_fails_the_merge_as_in_a_full_one(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        folder = self.copy_of()
        fx.set_round(folder, kind="narrow", items=[{"item": "FLOOR-1", "reason": "r"}, {"item": "CLOCK-1", "reason": "s"}],
                     regions=["r"], others="rest")
        given = {"area-FLOOR": {"Verdicts": [verdict("FLOOR-1", "cannot judge", "needs crop-U9: the views show no crop of U9")]},
                 "area-CLOCK": {"Verdicts": [verdict("CLOCK-1")]}}
        self.refused(lambda: merged(folder, given), "item FLOOR-1 is still cannot judge", "asks for crop-U9", "unit area-FLOOR", "--rerun")

    def add_view(self, item="CLOCK-1", why="needs crop-Y1: no crop of the crystal", name="crop-Y1.svg", folder=None):
        view = os.path.join(self.root, name)
        fx.write(view, "<svg/>")
        status, text = fx.run_folder(["--add-view", folder or self.folder, "--view", view, "--view-command",
                                      "kicad-cli pcb export svg crop", "--cannot-judge-item", item, "--cannot-judge-why", why])
        self.assertEqual(status, 0, text)

    def test_a_recorded_cannot_judge_for_an_item_outside_the_round_fails_the_merge_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        self.add_view(item="CLOCK-9")
        text = self.refused(lambda: merged(self.folder, results()), "CLOCK-9", "not an item this round judges", "exact name")
        self.assertNotIn("still cannot judge", text)

    def test_a_recorded_cannot_judge_for_an_item_with_no_verdict_row_fails_the_merge_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        self.add_view(item="CLOCK-1")
        given = results()
        given["area-CLOCK"]["Verdicts"] = []
        self.refused(lambda: merged(self.folder, given), "records a cannot judge for CLOCK-1", "no verdict row",
                     "item CLOCK-1 has no verdict row")

    def test_a_resolved_cannot_judge_is_one_row_recording_the_cannot_judge_then_the_view_then_the_verdict(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        self.add_view()
        given = results()
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "fail", "Finding 1.1.", "crop-Y1 at (5, 5)")]
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1")]
        text = rendered(self.folder, given)
        row = next(line for line in text.splitlines() if line.startswith("| CLOCK-1 "))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(cells[3], "cannot judge; added-views/crop-Y1.svg; fail")
        self.assertEqual(cells[5], "Cannot judge: needs crop-Y1: no crop of the crystal. Finding 1.1.")
        self.assertEqual(cells[4], "crop-Y1 at (5, 5)", "the row rests on what the re-run's reviewer cites")
        self.assertIn("kicad-cli pcb export svg crop (added view: added-views/crop-Y1.svg)", text.split("### Verdicts")[0],
                      "the added view is folded into the Views field with its command")
        self.assertEqual(text.count("added-views/crop-Y1.svg"), 2, "once in the Views field and once in the row")
        again = results()
        again["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "needs crop-Y2: still not enough")]
        self.refused(lambda: merged(self.folder, again), "item CLOCK-1 is still cannot judge", "asks for crop-Y2")

    def test_a_full_round_whose_plan_unit_wrote_no_note_fails_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        self.refused(lambda: merged(self.folder, results(plan_notes=())), "unit plan-and-free-pass gave no note")
        given = results(plan_notes=("  ",))
        self.refused(lambda: merged(self.folder, given), "the Plan and free pass table's row 1 is empty")

    def test_a_citation_of_an_earlier_rounds_finding_is_left_and_one_the_record_lacks_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        folder = self.write_folder(os.path.join(self.root, "later"), number=2)
        self.assertEqual(review_caller_layout.earlier_findings(folder), [("1", 1)])
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "Finding 1.1 closed by a reason, which no longer applies; "
                                                                        "Finding 2.1 is raised."), verdict("FLOOR-2")],
                               "Findings": [finding(1, "FLOOR-1")]}
        out = merged(folder, given)
        self.assertEqual(out["tables"]["Verdicts"]["rows"][0]["Why"],
                         "Finding 1.1 closed by a reason, which no longer applies; Finding 2.1 is raised.")
        given["area-FLOOR"]["Verdicts"][0]["Why"] = "Finding 1.7."
        self.refused(lambda: merged(folder, given), "cites 'Finding 1.7', a finding of round 1 that the review folder's earlier rounds do not hold")
        given["area-FLOOR"]["Verdicts"][0]["Why"] = "the clearance is 1.3 mm and 0.25 mm wide"
        merged(folder, given)

    def test_the_planning_shortfall_entry_is_the_one_the_unit_that_raised_the_finding_wrote(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        shortfall = "shortfall: the plan row, followed as written, would not have kept the crystal at its pins"
        row = {**finding(1, "CLOCK-1"), "Planning shortfall": shortfall}
        given = results()
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "fail", "Finding 1.1.")]
        given["area-CLOCK"]["Findings"] = [row]
        self.assertEqual(merged(self.folder, given)["tables"]["Findings"]["rows"][0]["Planning shortfall"], shortfall)
        text = rendered(self.folder, given)
        self.assertIn(f"| {shortfall} |", text, "the record carries the unit's entry as written")
        self.assertIn("Planning shortfall", prepared(self.folder).unit_text("area-CLOCK"), "and the unit is told to write it")


class TheNarrowRecord(Folder):
    narrow = True

    def test_a_narrow_round_names_its_changed_regions_items_and_why_the_others_are_not_judged_in_the_record(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        given = {"area-FLOOR": {"Verdicts": [verdict("FLOOR-1")]}, "area-CLOCK": {"Verdicts": [verdict("CLOCK-1")]}}
        text = rendered(self.folder, given)
        opening = text.split("### Verdicts")[0].splitlines()
        marks = [next(index for index, line in enumerate(opening) if line.startswith(f"- **{name}**"))
                 for name in ("Board judged", "Views", "Pre-order check", "Round kind", "Changed regions", "Items judged", "Items not judged")]
        self.assertEqual(marks, sorted(marks))
        self.assertIn("- **Round kind**: narrow", opening)
        self.assertIn("- **Changed regions**: region low voltage, net XTAL1", opening)
        self.assertIn("  - FLOOR-1: the changed region holds its parts", opening)
        self.assertIn("  - CLOCK-1: the crystal moved", opening)
        self.assertIn("- **Items not judged**: no other item touches a changed region or net", opening)
        rows = text.split("### Verdicts")[1].split("### Plan and free pass")[0]
        self.assertNotIn("FLOOR-2", rows)
        self.assertIn("no comparison with the plan or free pass beyond them was made", text)


class TheRenderedRound(Folder):
    HAND_WRITTEN = f"""## Round 1

- **Board judged**: 1234567.
- **Views**: `task hw:views -- ...`.
- **Pre-order check**: the board's `DESIGN` line.

```
DESIGN | x | PASS
```

- **Round kind**: full

### Verdicts

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|
| FLOOR-1 | judgement | function | fail | classes | Finding 1.1. |

### Plan and free pass

The plan was compared.

### Findings

| Finding | Raised by | Severity | What and where | Rule | Added as | Planning shortfall | Closed by |
|---|---|---|---|---|---|---|---|
| 1.1 | FLOOR-1 | function | classes at (10, 10): wrong | no | FLOOR-1 | — | |
"""

    def shape(self, text):
        bodies = board_review_history.round_bodies(text)
        parsed = board_review_history.Round(bodies[1])
        headings = [line for _, line, _ in bodies[1] if line.startswith("###")]
        return {"faults": parsed.faults, "kinds": parsed.kinds, "verdict header": parsed.verdicts[0],
                "verdict cells": {len(row) for row in parsed.verdicts[1]}, "findings header": parsed.findings[0],
                "finding numbers": [bool(re.fullmatch(r"1\.\d+", number)) for number in parsed.numbers],
                "compared": {tuple(sorted(row)) for row in parsed.compared.values()}, "headings": headings,
                "opening starts": parsed.opening[0].split(":")[0]}

    def test_the_merged_round_is_read_by_the_history_commands_reader_as_a_hand_written_round_is(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "Finding 1.1."), verdict("FLOOR-2")],
                               "Findings": [finding(1, "FLOOR-1")]}
        text = rendered(self.folder, given)
        mine, theirs = self.shape(text), self.shape(self.HAND_WRITTEN)
        self.assertEqual(mine["faults"], [], mine["faults"])
        self.assertEqual(theirs["faults"], [])
        self.assertEqual(mine["kinds"], ["full"])
        for key in ("kinds", "verdict header", "findings header", "compared", "headings", "opening starts"):
            self.assertEqual(mine[key], theirs[key], key)
        self.assertEqual(mine["verdict cells"], theirs["verdict cells"])
        self.assertEqual(mine["finding numbers"], [True])
        lines = text.splitlines()
        order = [lines.index(mark) for mark in ("## Round 1", "### Verdicts", "### Plan and free pass", "### Findings")]
        self.assertEqual(order, sorted(order))
        self.assertLess(next(index for index, line in enumerate(lines) if line.startswith("- **Round kind**")), order[1])
        self.assertNotIn(PLAN_ENTRY, text.split("### Plan and free pass")[0], "the comparison's own verdict row is not a row of the record")

    def test_a_round_that_raises_no_finding_has_the_line_saying_so_and_is_read_as_one(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        text = rendered(self.folder, results())
        parsed = board_review_history.Round(board_review_history.round_bodies(text)[1])
        self.assertEqual(parsed.faults, [])
        self.assertEqual(parsed.findings, ([], []))
        self.assertTrue(text.rstrip().endswith("### Findings\n\nThis round raises no finding."))

    def test_a_record_holding_the_merged_round_below_an_earlier_one_is_read_round_by_round(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        folder = self.write_folder(os.path.join(self.root, "later"), number=2)
        given = results()
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1", "fail", "Finding 1.1."), verdict("FLOOR-2")]
        given["area-FLOOR"]["Findings"] = [finding(1, "FLOOR-1")]
        text = rendered(folder, given, number=2)
        record = slurp(os.path.join(folder, fx.DESIGN, "layout-review.md")) + "\n" + text
        numbers, malformed, unclosed = board_review_history.round_headings(record)
        self.assertEqual((numbers, malformed, unclosed), ([1, 2], [], None))
        bodies = board_review_history.round_bodies(record)
        self.assertEqual(board_review_history.Round(bodies[2]).faults, [])
        self.assertEqual(board_review_history.Round(bodies[2]).numbers, ["2.1"])
        self.assertEqual(board_review_history.Round(bodies[2]).kinds, ["full"])

    def test_a_vertical_bar_or_line_break_in_a_cell_is_escaped_by_the_kits_rule_and_the_reader_keeps_the_shape(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "Finding 1.1.", rests="layer-F.Cu | layer-B.Cu"), verdict("FLOOR-2")],
                               "Findings": [finding(1, "FLOOR-1", what="classes at (10, 10):\r\nwrong\n\nplace|b & more")]}
        given["area-GROUND"]["Verdicts"][0]["Why"] = "two\nlines and a||b"
        out = merged(self.folder, given)
        raw = {row["Item"]: row for row in out["tables"]["Verdicts"]["rows"]}
        self.assertEqual(raw["FLOOR-1"]["Rests on"], "layer-F.Cu | layer-B.Cu", "the merged table keeps the raw cell")
        text = rendered(self.folder, given)
        self.assertNotIn("\r", text)
        self.assertIn("layer-F.Cu &#124; layer-B.Cu", text)
        self.assertIn("two&#10;lines and a&#124;&#124;b", text)
        self.assertIn("&amp; more", text)
        parsed = board_review_history.Round(board_review_history.round_bodies(text)[1])
        self.assertEqual(parsed.faults, [])
        self.assertEqual({len(row) for row in parsed.verdicts[1]}, {len(parsed.verdicts[0])})
        self.assertEqual(len(parsed.findings[1][0]), len(parsed.findings[0]))
        self.assertEqual(parsed.numbers, ["1.1"])

    def test_the_rendered_record_is_one_plain_file_named_for_its_round_whose_name_the_kit_accepts(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        package = prepared(self.folder)
        files = package.render(merge.plain_tables(package.merge(list(results()), {unit: {"r1": tables} for unit, tables in results().items()})))
        self.assertEqual(list(files), ["round-1.md"])
        self.assertTrue(kit_caller.rendered_name_ok("round-1.md"))
        later = self.write_folder(os.path.join(self.root, "later"), number=2)
        files = prepared(later).render(merge.plain_tables(prepared(later).merge(
            list(results()), {unit: {"r1": tables} for unit, tables in results().items()})))
        self.assertEqual(list(files), ["round-2.md"])


# --- The command, against the stub --------------------------------------------------------------------


class Command:
    """The kit's command run on a review folder with the layout caller, the stub playing the agent command line."""

    def __init__(self, case: Folder, folder: str = None, out: str = "out"):
        self.case, self.folder = case, folder or case.folder
        self.out = os.path.join(case.root, out)
        self.log = os.path.join(case.root, "agent.log")
        self.scenario_path = os.path.join(case.root, "scenario.json")
        self.program = os.path.join(case.root, "agent")
        fx.write(self.program, STUB.replace("PYTHON", sys.executable, 1).replace("TOOLS", repr(TOOLS)))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        patcher = mock.patch.dict(os.environ, {ex.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path, "STUB_LOG": self.log})
        patcher.start()
        case.addCleanup(patcher.stop)

    def scenario(self, **values):
        fx.write(self.scenario_path, json.dumps(values))

    def go(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        status = command.main(["--caller", "layout", "--callers", TOOLS, "--review", self.folder, "--out", self.out] + list(extra),
                              out, err, repo=os.path.join(self.case.root, "no-repository"))
        return status, out.getvalue(), err.getvalue()

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


class TheToolGrant(Folder):
    GRANT = "Read,Glob,Grep,WebFetch"

    def test_the_caller_grants_the_read_tools_and_the_one_retrieval_tool_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C6: Against the kit's stub, every reviewer of the layout caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a document can be retrieved, which the proof run records.
        package = prepared(self.folder)
        self.assertEqual(package.tools, ("Read", "Glob", "Grep", "WebFetch"))
        spec = messages.make_spec(package.declaration, package.tools, self.folder, "claude-sonnet-5-5")
        self.assertEqual(spec.expected_tools, sorted(["Read", "Glob", "Grep", "WebFetch", "StructuredOutput"]))

    def test_every_reviewer_is_started_with_the_four_tools_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C6: Against the kit's stub, every reviewer of the layout caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a document can be retrieved, which the proof run records.
        run = Command(self)
        run.scenario()
        status, text, err = run.go("--format", "json")
        self.assertEqual(status, 0, text + err)
        calls = run.calls()
        forks = [call for call in calls if call["resume"] is not None]
        self.assertGreaterEqual(len(forks), 2)
        self.assertEqual({call["tools"] for call in calls}, {self.GRANT}, "the shared context and every reviewer")
        for call in calls:
            for tool in ("Bash", "Write", "Edit", "Task"):
                self.assertNotIn(tool, call["tools"].split(","))
            self.assertEqual(os.path.realpath(call["cwd"]), os.path.realpath(self.folder), "in the review folder")
        self.assertEqual(json.loads(text)["result"], "WRITTEN")

    def reviewer_refused(self, **scenario):
        """The command run with forks whose start reports deviate: refused, every reviewer's failure named with its units."""
        self.runs = getattr(self, "runs", 0) + 1
        run = Command(self, out=f"out-{self.runs}")
        run.scenario(**scenario)
        status, text, _ = run.go("--format", "json")
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        self.assertEqual(report["result"], "REFUSED")
        self.assertIsNone(json.loads(slurp(os.path.join(run.out, "record.json")))["merged"])
        lines = report["refusals"]
        named = sorted(re.match(r"unit (.+?) \(group (G\d+), replica (\d+)\) failed", line).groups() for line in lines)
        self.assertEqual(named, [("area-FLOOR, area-GROUND, area-CLOCK", "G1", "1"), ("area-FLOOR, area-GROUND, area-CLOCK", "G1", "2"),
                                 ("plan-and-free-pass", "G2", "1"), ("plan-and-free-pass", "G2", "2")],
                         "every reviewer that started badly is named with the units it was to judge")
        for line in lines:
            self.assertRegex(line, r"session G\d\.r\d\.a1 started")
        return lines[0]

    def test_a_session_that_reports_a_different_tool_set_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C6: Against the kit's stub, every reviewer of the layout caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a document can be retrieved, which the proof run records.
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "WebFetch", "Bash", "StructuredOutput"])
        self.assertIn("started with tools", line)
        self.assertIn("Bash", line)
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "StructuredOutput"])
        self.assertIn("WebFetch", line, "a reviewer that lost the retrieval tool is refused too")

    def test_a_session_that_reports_an_mcp_server_or_another_working_directory_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C6: Against the kit's stub, every reviewer of the layout caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a document can be retrieved, which the proof run records.
        line = self.reviewer_refused(fork_mcp=True)
        self.assertIn("MCP servers", line)
        line = self.reviewer_refused(fork_cwd=os.path.join(self.root, "elsewhere"))
        self.assertIn("started in", line)
        self.assertIn(self.folder, line, "the folder its specification names")


class TheCommandEndToEnd(Folder):
    def test_the_command_writes_the_round_as_text_and_as_json(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C4: The merged round has the round heading, the opening fields with the round kind, the Verdicts table, the Plan and free pass section and the Findings table or the line saying no finding was raised, in the order the method gives. A record holding it and a hand-written round are passed through the reader the review record history command uses, and what it reads from the two has the same shape. Out of scope: the history command's own checks of the repository's history.
        run = Command(self)
        run.scenario(verdicts={"CLOCK-1": "fail"})
        status, text, err = run.go("--format", "json")
        self.assertEqual(status, 0, text + err)
        report = json.loads(text)
        self.assertEqual(report["rendered"], ["round-1.md"])
        written = slurp(os.path.join(run.out, "round-1.md"))
        self.assertTrue(written.startswith("## Round 1\n"))
        self.assertEqual([row["Item"] for row in report["tables"]["Verdicts"]["rows"]],
                         ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1", PLAN_ENTRY])
        parsed = board_review_history.Round(board_review_history.round_bodies(written)[1])
        self.assertEqual(parsed.faults, [])
        self.assertEqual(parsed.numbers, ["1.1"])
        self.assertEqual(report["same_place"], [])
        second = Command(self)
        second.out = os.path.join(self.root, "out-text")
        status, text, err = second.go()
        self.assertEqual(status, 0, text + err)
        self.assertIn("RENDERED | round-1.md", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | WRITTEN"))

    def test_a_round_file_with_a_missing_field_is_refused_by_the_command_before_any_session_starts(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        fx.set_round(self.folder, commit=None, views=[])
        run = Command(self)
        run.scenario()
        status, text, _ = run.go("--format", "json")
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        joined = "; ".join(report["refusals"])
        self.assertIn("the commit judged is None", joined)
        self.assertIn("the views are []", joined)
        self.assertEqual(run.calls(), [], "no session was started")
        self.assertFalse(os.path.exists(run.out))

    def test_a_merge_that_fails_names_the_item_and_keeps_the_units_results(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        run = Command(self)
        run.scenario(verdicts={"GROUND-1": "cannot judge"}, why={"GROUND-1": "needs crop-U3: no crop of U3"})
        status, text, _ = run.go("--format", "json")
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        joined = "; ".join(report["refusals"])
        self.assertIn("item GROUND-1 is still cannot judge", joined)
        self.assertIn("asks for crop-U3", joined)
        self.assertIn("unit area-GROUND", joined)
        self.assertFalse(os.path.exists(os.path.join(run.out, "round-1.md")), "nothing is rendered from a refused merge")
        self.assertTrue(os.path.exists(os.path.join(run.out, "record.json")), "the units' results are kept")

    def test_a_cannot_judge_is_resolved_by_adding_the_view_and_running_that_unit_again_and_the_row_records_all_three(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C3: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item that has two, fails a round whose number, kind, commit judged, views or check lines are missing or malformed, writes the opening lines in the order the method gives with the round kind and, for a narrow round, its changed regions, the listed items with their reasons and the line saying why every other item is not judged, and reports two findings that cite the same view and board place, keeping both. Rule-kind items rest on the check's report and the rules table as the method says, which the merge does not judge. Findings of the item units are numbered in the checklist's order and the findings of the comparison and free-pass unit follow, in the order that unit lists them. A round that still holds a cannot judge verdict fails, naming the item and the view its Why asks for, since the method resolves it within the round; the round's starter renders the view, adds it with the folder command's add-view mode and re-runs that unit, and the merged row, built from the item, Why and view the resolutions file holds and the re-run's verdict, with the added views folded into the round's Views field at the render, records the cannot judge, the view and the verdict reached, in that order. Out of scope: whether a verdict is right.
        run = Command(self)
        run.scenario(verdicts={"CLOCK-1": "cannot judge"}, why={"CLOCK-1": "needs crop-Y1: no crop of the crystal"})
        self.assertEqual(run.go("--format", "json")[0], 1)
        before = {path: slurp(os.path.join(self.folder, path)) for path in ("round.json", "layout-facts.txt", "method-extract.md")}
        view = os.path.join(self.root, "crop-Y1.png")
        fx.write(view, fx.kit_fx.png(60, 40, 90))
        status, text = fx.run_folder(["--add-view", self.folder, "--view", view, "--view-command", "kicad-cli pcb export png crop",
                                      "--cannot-judge-item", "CLOCK-1", "--cannot-judge-why", "needs crop-Y1: no crop of the crystal"])
        self.assertEqual(status, 0, text)
        self.assertEqual(before, {path: slurp(os.path.join(self.folder, path)) for path in before}, "no shared-context file changed")
        calls_before = len(run.calls())
        run.scenario(verdicts={"CLOCK-1": "pass"})
        status, text, err = run.go("--rerun", "area-CLOCK", "--format", "json")
        self.assertEqual(status, 0, text + err)
        report = json.loads(text)
        row = next(row for row in report["tables"]["Verdicts"]["rows"] if row["Item"] == "CLOCK-1")
        self.assertEqual(row["Verdict"], "pass", "the merged table holds the re-run's verdict")
        written = slurp(os.path.join(run.out, "round-1.md"))
        record_row = next(line for line in written.splitlines() if line.startswith("| CLOCK-1 "))
        cells = [cell.strip() for cell in record_row.strip("|").split("|")]
        self.assertEqual(cells[3], "cannot judge; added-views/crop-Y1.png; pass")
        self.assertTrue(cells[5].startswith("Cannot judge: needs crop-Y1: no crop of the crystal."))
        self.assertIn("kicad-cli pcb export png crop (added view: added-views/crop-Y1.png)", written.split("### Verdicts")[0])
        again = run.calls()[calls_before:]
        forks = [call for call in again if call["resume"] is not None]
        self.assertEqual(len(again) - len(forks), 1, "one shared context, started again for the run")
        self.assertEqual({tuple(call["units"]) for call in forks}, {("area-FLOOR", "area-GROUND", "area-CLOCK")},
                         "and forks of the unit's group alone, not the comparison unit's")
        self.assertEqual(report["reran"][0]["units"], ["area-CLOCK"])


class Documentation(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def layout_review(self):
        method = self.read("docs", "board-design-method.md")
        return self.flat(method[method.index("\n## Layout review\n"):].split("\n## Ordering")[0])

    def test_the_layout_review_step_says_a_round_may_be_judged_by_unit_and_what_the_merge_checks(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C7: The method's layout review section says that a round may be judged by unit and what the merge checks, that the round's fields come from whoever starts it, that the unit which raised a finding writes its Planning shortfall entry from the plan row, that a cannot judge is resolved by adding the view and re-running the unit with the row recording the cannot judge, the view and the verdict, that the merged round is appended below the earlier rounds and committed by whoever started the round at the end of the round, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the layout caller and the folder command and what each needs. Checked by reading each place against these clauses. Out of scope: the routing section's critical-routing check.
        section = self.layout_review()
        for words in ("A round may be judged by unit instead of by one reviewer", "changes none of them",
                      "one reviewer for each area of the catalogue, one for the board's own items and one for the comparison with the plan and the free pass",
                      "merges what they return, with no model, into one round of the one record",
                      "come from whoever starts the round", "since the merge has no model to write them",
                      "in which an item the round judges has no verdict row or has two", "in which a verdict row is for an item the round does not judge",
                      "or in which a `cannot judge` is left, and it names the item",
                      "numbers this round's findings in the checklist's order with the comparison and the free pass last",
                      "leaves a citation of an earlier round's finding as written",
                      "reports two findings that cite the same view and board place for the designer to resolve, dropping neither",
                      "The unit that raised a finding writes its Planning shortfall entry from the plan row",
                      "the designer names the item or step to amend, amends it and adds the commit",
                      "add it to the review folder with the folder command's add-view mode", "and run that unit again",
                      "the merged row records the `cannot judge`, the view and the verdict reached, in that order",
                      "appended below the record's earlier rounds, which stay as they are",
                      "whoever started the round commits it at the end of the round", "before any change to the board",
                      "Judging a round with one reviewer, a person or an agent session that does not use the command, stays valid"):
            self.assertIn(words, section, f"the layout review section says {words!r}")

    def test_the_sentence_that_a_proof_is_repeated_names_the_form_that_changed(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C7: The method's layout review section says that a round may be judged by unit and what the merge checks, that the round's fields come from whoever starts it, that the unit which raised a finding writes its Planning shortfall entry from the plan row, that a cannot judge is resolved by adding the view and re-running the unit with the row recording the cannot judge, the view and the verdict, that the merged round is appended below the earlier rounds and committed by whoever started the round at the end of the round, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the layout caller and the folder command and what each needs. Checked by reading each place against these clauses. Out of scope: the routing section's critical-routing check.
        section = self.layout_review()
        sentence = section[section.index("Repeat the proof after changing"):].split("`hardware/README.md` describes")[0]
        for words in ("in the form that changed", "repeats the single-reviewer proof above", "repeats the fanned-out proof",
                      "task hw:review-proof -- --work <folder>", "with the same four tools in both",
                      "to report every seed the single reviewer reports in no more time and at no more cost",
                      "A change to the catalogue or the views repeats both",
                      "The recorded proof of one form stands for that form alone"):
            self.assertIn(words, sentence)
        self.assertNotIn("Repeat the proof after changing the catalogue, the views or this step.", section)

    def test_the_hardware_notes_describe_the_layout_caller_and_the_folder_command_and_what_each_needs(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C7: The method's layout review section says that a round may be judged by unit and what the merge checks, that the round's fields come from whoever starts it, that the unit which raised a finding writes its Planning shortfall entry from the plan row, that a cannot judge is resolved by adding the view and re-running the unit with the row recording the cannot judge, the view and the verdict, that the merged round is appended below the earlier rounds and committed by whoever started the round at the end of the round, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the layout caller and the folder command and what each needs. Checked by reading each place against these clauses. Out of scope: the routing section's critical-routing check.
        notes = self.read("hardware", "README.md")
        section = self.flat(notes[notes.index("## The layout review by unit"):].split("\n## ")[0])
        for words in ("review_folder.py", "review_caller_layout.py", "layout_review_proof.py", "review_agent_tap.py",
                      "It needs git and Python, no KiCad and no model", "needs the agent command line on the search path and logged in",
                      "and no KiCad", "the commit that holds the board", "round.json", "`--round-fields number,kind,commit,views,check`",
                      "The set of fields is a parameter", "--item ITEM=reason", "--add-view", "added-views/", "`--rerun`",
                      "`area-<code>`", "`board-items`", "`plan-and-free-pass`", "`Read`, `Glob`, `Grep` and `WebFetch`",
                      "the setup session keeps the read tools alone", "exactly one verdict row",
                      "round-<n>.md", "committed by whoever started the round", "`BOUND`",
                      "`--keep-work-tree`", "money", "on demand and in neither the build round nor the nightly",
                      "the most reviewers that ran together", "calls refused for a rate limit"):
            self.assertIn(words, section, f"the hardware notes' section says {words!r}")
        listed = self.flat(notes[notes.index("- `task hw:test` runs"):].splitlines()[0])
        for words in ("review fan-out command", "layout review's caller", "review folder command", "layout review proof command"):
            self.assertIn(words, listed)
        commands = notes[notes.index("## The commands"):notes.index("## The schematic sheets")]
        for words in ("task hw:review-folder", "task hw:review-proof"):
            self.assertIn(words, commands)
        self.assertIn("the layout review's caller for it, the command that writes a committed board's review folder", notes.splitlines()[5])
        self.assertIn("--keep-work-tree <folder>", self.flat(notes[notes.index("## The proof designs"):]))

    def test_the_task_runner_names_the_new_commands_and_their_tests(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C7: The method's layout review section says that a round may be judged by unit and what the merge checks, that the round's fields come from whoever starts it, that the unit which raised a finding writes its Planning shortfall entry from the plan row, that a cannot judge is resolved by adding the view and re-running the unit with the row recording the cannot judge, the view and the verdict, that the merged round is appended below the earlier rounds and committed by whoever started the round at the end of the round, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the layout caller and the folder command and what each needs. Checked by reading each place against these clauses. Out of scope: the routing section's critical-routing check.
        taskfile = self.read("Taskfile.yml")
        folder = self.flat(taskfile[taskfile.index("  hw:review-folder:"):].splitlines()[1])
        proof = self.flat(taskfile[taskfile.index("  hw:review-proof:"):].splitlines()[1])
        for words in ("review_folder.py", "on demand", "neither the build round nor the nightly", "Needs git and Python 3.9 or newer, no KiCad and no model",
                      "--add-view", "the set of round fields being a parameter"):
            self.assertIn(words, folder)
        for words in ("layout_review_proof.py", "review_agent_tap.py", "on demand", "neither the build round nor the nightly", "spends the agent command line's usage",
                      "agent command line on the search path and logged in", "the most reviewers that ran together", "the layout caller's bound"):
            self.assertIn(words, proof)
        for text in (taskfile[taskfile.index("  hw:test:\n"):].splitlines()[1], taskfile[taskfile.index("  hw:test:round:"):].splitlines()[1]):
            for words in ("review fan-out command", "layout review", "review folder command", "layout review proof command"):
                self.assertIn(words, text)


if __name__ == "__main__":
    unittest.main()
