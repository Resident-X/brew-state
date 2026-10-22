#!/usr/bin/env python3
"""The critical-routing check as a caller of the review kit command, over synthetic review folders.

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
import threading
import time
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_history  # noqa: E402
import layout_fixtures as fx  # noqa: E402
import review_caller_critical_routing as caller  # noqa: E402
import review_caller_layout  # noqa: E402
import review_catalogue  # noqa: E402
import review_folder  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import catalogue, command, ensemble, merge, messages, planner  # noqa: E402
from review_kit import results as kit_results  # noqa: E402
from review_kit import executor as ex  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
NOT_BEARING = "bears on no critical net"
ITEMS = {"area-FLOOR": ["FLOOR-1", "FLOOR-2"], "area-GROUND": ["GROUND-1"], "area-CLOCK": ["CLOCK-1"]}
GRANT = "Read,Glob,Grep,WebFetch"
SMALL = "claude-haiku-5-5"

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
                             "fork": "--fork-session" in args, "units": units, "prompt": text}) + "\\n")
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
tables = {"Verdicts": [], "Findings": []}
for unit, body in re.findall(r"Your unit: (\\S+)\\n(.*?)(?=Your unit: |\\Z)", text, re.S):
    found = 0
    for item in re.findall(r"^- ([A-Z]+-\\d+)$", body, re.M):
        verdict = scenario.get("model_verdicts", {}).get(model, {}).get(item) or scenario.get("verdicts", {}).get(item, "pass")
        why = scenario.get("why", {}).get(item, "Judged on the views.")
        rests = "layer-F.Cu"
        if verdict == "fail":
            found += 1
            why = scenario.get("why", {}).get(item, f"finding {found}")
            tables["Findings"].append({"Finding": found, "Item": item, "What and where": f"layer-F.Cu at ({found}, {found}): off its place"})
        if verdict == "bears on no critical net":
            rests = "\\u2014"
            why = scenario.get("why", {}).get(item, "No critical net's copper decides it.")
        tables["Verdicts"].append({"Item": item, "Kind": "judgement", "Severity": "function", "Verdict": verdict,
                                   "Rests on": rests, "Why": why})
sys.stdout.write(ex.stream_text(session_id, text="done", structured={"tables": tables}, cost=0.03, api_ms=300, turns=1,
                                read=1000, write=200, generated=50, tools=report.get("tools", tools), model=model,
                                cwd=report.get("cwd", os.getcwd()), mcp_servers=report.get("mcp_servers", ())))
'''


def verdict(item, outcome="pass", why="Judged on the views.", rests="layer-F.Cu", kind="judgement"):
    return {"Item": item, "Kind": kind, "Severity": "function", "Verdict": outcome, "Rests on": rests, "Why": why}


def unbearing(item, why="No critical net's copper decides it."):
    return verdict(item, NOT_BEARING, why, "—")


def finding(number, item, what="layer-F.Cu at (10, 10): a track is thin"):
    return {"Finding": number, "Item": item, "What and where": what}


def results(items=ITEMS):
    """A synthetic result for every unit of a pass with no board items: every item passes."""
    return {unit: {"Verdicts": [verdict(item) for item in ids], "Findings": []} for unit, ids in items.items()}


#: The couplings the synthetic catalogue is planned with: its areas are not the real ones, so the pairs are the test's own.
SYNTHETIC_COUPLED = (("FLOOR", "GROUND"), ("CLOCK", "FLOOR"))
real_load = kit_caller.load


def load_with_synthetic_couplings(name, folder):
    """The caller as the kit loads it, its couplings those of the synthetic catalogue."""
    loaded = real_load(name, folder)
    loaded.module.COUPLED = SYNTHETIC_COUPLED
    return loaded


def prepared(folder):
    return kit_caller.load("critical_routing", TOOLS).prepare(folder)


def merged(folder, given, order=None, replicas=None):
    """The unit results merged as the command merges them, each unit one replica unless `replicas` gives more."""
    return prepared(folder).merge(order or list(given), {unit: replicas.get(unit, {"r1": tables}) if replicas else {"r1": tables}
                                                         for unit, tables in given.items()})


def rendered(folder, given, number=1, replicas=None):
    package = prepared(folder)
    out = package.merge(list(given), {unit: replicas.get(unit, {"r1": tables}) if replicas else {"r1": tables}
                                      for unit, tables in given.items()})
    return package.render(merge.plain_tables(out))[f"pass-{number}.md"]


def slurp(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Folder(unittest.TestCase):
    """A review folder the folder command wrote from a synthetic repository, in a temporary folder."""

    own = fx.OWN_NONE
    number = 1
    method = fx.METHOD_ROUTING

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="critical-routing-caller-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.folder = self.write_folder(self.root)
        patched = mock.patch.object(kit_caller, "load", load_with_synthetic_couplings)
        patched.start()
        self.addCleanup(patched.stop)

    def write_folder(self, root, number=None, own=None, method=None, placement=False, extra=None):
        return fx.write_critical_folder(root, own if own is not None else self.own, number or self.number, placement,
                                        method or self.method, extra)

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

    def add_view(self, item="CLOCK-1", why="needs crop-Y1: no crop of the crystal", name="crop-Y1.svg", folder=None):
        view = os.path.join(self.root, name)
        fx.write(view, "<svg/>")
        status, text = fx.run_folder(["--add-view", folder or self.folder, "--view", view, "--view-command",
                                      "kicad-cli pcb export svg crop", "--cannot-judge-item", item, "--cannot-judge-why", why])
        self.assertEqual(status, 0, text)

    def add_document(self, item="CLOCK-1", why="needs the datasheet of Y1: the pin spacing is not in the folder", name="y1-pins.txt"):
        document = os.path.join(self.root, name)
        fx.write(document, "Pin spacing: 2.54 mm\n")
        status, text = fx.run_folder(fx.add_document_argv(self.folder, document, "manufacturer datasheet", item, why))
        self.assertEqual(status, 0, text)


class TheUnits(Folder):
    def test_the_units_are_the_catalogue_areas_and_none_is_for_a_comparison_with_the_plan_or_a_free_pass(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        package = prepared(self.folder)
        self.assertEqual(list(package.declaration.units), ["area-FLOOR", "area-GROUND", "area-CLOCK"])
        self.assertEqual({unit: list(item.items) for unit, item in package.declaration.units.items()}, ITEMS)
        self.assertEqual(package.checklist, ("FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1"))
        for absent in ("plan-and-free-pass", "PLAN-AND-FREE-PASS"):
            self.assertNotIn(absent, package.declaration.units)
            self.assertNotIn(absent, package.checklist)
        self.assertEqual([code for code, _, _ in review_catalogue.areas(self.folder)], ["FLOOR", "GROUND", "CLOCK"])

    def test_the_board_items_unit_is_there_when_the_plans_table_has_rows_and_only_then(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        folder = self.write_folder(os.path.join(self.root, "own"), own=fx.OWN_ROWS)
        package = prepared(folder)
        self.assertEqual(list(package.declaration.units), ["area-FLOOR", "area-GROUND", "area-CLOCK", "board-items"])
        self.assertEqual(list(package.declaration.units["board-items"].items), ["BOARD-1", "BOARD-2"])
        self.assertEqual(package.checklist[-2:], ("BOARD-1", "BOARD-2"))
        self.assertEqual(package.declaration.units["board-items"].couples_with, (), "the board's own items are coupled with no area")
        self.assertNotIn("board-items", prepared(self.folder).declaration.units)
        text = package.unit_text("board-items")
        self.assertIn("Your unit: board-items", text)
        self.assertIn("- BOARD-1\n- BOARD-2", text)
        self.assertIn(f"{fx.DESIGN}/layout-plan.md", text)
        self.assertNotIn("### Floorplan", text, "the board items unit carries no area block")

    def test_each_units_prompt_asks_for_a_row_for_every_item_and_the_reason_for_each_that_bears_on_no_net(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        package = prepared(self.folder)
        floor = package.unit_text("area-FLOOR")
        self.assertIn("Your unit: area-FLOOR", floor)
        self.assertIn("- FLOOR-1\n- FLOOR-2", floor)
        self.assertIn("### Floorplan (FLOOR)", floor)
        for words in (f"`{NOT_BEARING}`", "give one verdict row to each of them and to no other item",
                      "an item that bears on the critical nets", "with the reason for one that does not",
                      "the one line saying why no critical net's copper decides the item", "step 4 of the routing section",
                      "the router has not run", "the pre-order check is not run here"):
            self.assertIn(words, floor)
        for other in ("GROUND-1", "CLOCK-1", "### Grounding", "### Clocks"):
            self.assertNotIn(other, floor, "a unit's prompt holds its own area only")
        for unit in package.declaration.units:
            self.assertIn(f"Your unit: {unit}", package.unit_text(unit))
        for column in caller.VERDICT_TABLE + caller.FINDING_TABLE:
            self.assertIn(column, floor)
        self.assertIn("never give such an item another verdict to avoid judging it", floor)

    def test_the_couplings_are_the_layout_callers_and_a_coupled_set_is_planned_into_one_group(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        self.assertEqual(caller.COUPLED, review_caller_layout.COUPLED)
        self.assertEqual(caller.COUPLED, (("POWER", "MAINS"), ("MFG", "POWER")))
        package = prepared(self.folder)
        units = package.declaration.units
        self.assertEqual(tuple(units["area-FLOOR"].couples_with), ("area-GROUND", "area-CLOCK"))
        self.assertEqual(tuple(units["area-GROUND"].couples_with), ("area-FLOOR",))
        groups = planner.pack(package.declaration)
        self.assertEqual([sorted(group) for group in groups], [["area-CLOCK", "area-FLOOR", "area-GROUND"]],
                         "a coupled set is judged in one group")
        loaded = real_load("critical_routing", TOOLS)
        loaded.module.COUPLED = review_catalogue.COUPLED
        self.assertEqual(loaded.module.coupled_to("area-POWER", {"area-POWER": [], "area-MAINS": [], "area-MFG": []}),
                         ["area-MAINS", "area-MFG"])
        self.assertEqual(loaded.module.coupled_to("board-items", {"board-items": [], "area-POWER": []}), [])

    def links(self, method):
        """The pairs of areas the catalogue's items cross-reference by identifier, each pair in sorted order."""
        section = board_history.LAYOUT_CATALOGUE.search(method).group(1)
        codes = set(re.findall(r"^### .+ \(([A-Z]+)\)[ \t]*$", section, re.M))
        current, found = None, set()
        for line in section.split("\n"):
            heading = review_catalogue.AREA.match(line)
            if heading:
                current = heading.group(2)
            elif current:
                for cited in re.finditer(r"\b([A-Z]+)-\d+\b", line):
                    if cited.group(1) in codes and cited.group(1) != current:
                        found.add(tuple(sorted((current, cited.group(1)))))
        return sorted(found)

    def test_every_coupling_the_caller_states_has_a_cross_reference_in_the_real_catalogue(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        method = slurp(os.path.join(REPO, "docs", "board-design-method.md"))
        folder = fx.write_critical_folder(os.path.join(self.root, "real"), method=method)
        loaded = real_load("critical_routing", TOOLS)
        units = loaded.prepare(folder).declaration.units
        self.assertEqual([item for found in units.values() for item in found.items], list(board_history.catalogue(method)))
        declared = {tuple(sorted((unit[len("area-"):], other[len("area-"):]))) for unit, found in units.items()
                    for other in found.couples_with}
        self.assertEqual(declared, {("MAINS", "POWER"), ("MFG", "POWER")}, "the real catalogue has the areas the couplings name")
        self.assertEqual(sorted(pair for pair in declared if pair not in self.links(method)), [])
        self.assertEqual(list(units), [f"area-{code}" for code, _, _ in review_catalogue.areas(folder)])

    def test_a_method_with_no_catalogue_areas_or_lacking_a_section_is_refused_naming_what_is_missing(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        method = os.path.join(self.folder, "docs", "board-design-method.md")
        text = slurp(method)
        fx.write(method, re.sub(r"^### (Floorplan|Grounding|Clocks) \(\w+\)$", r"### \1", text, flags=re.M))
        self.refused(lambda: prepared(self.folder), "no catalogue area heading")
        fx.write(method, text.replace("## Layout practice catalogue", "## Something else"))
        self.refused(lambda: prepared(self.folder), "no `## Layout practice catalogue` section")
        for heading in ("Routing: critical nets by hand and locked, then the rest", "Layout review", "Layout review views"):
            fx.write(method, text.replace(f"## {heading}\n", "## Something else\n"))
            self.refused(lambda: prepared(self.folder), f"no `## {heading}` section", "shared context")
        extract = os.path.join(self.folder, "method-extract.md")
        held = slurp(extract)
        fx.write(extract, held.replace("## Routing: critical nets by hand and locked, then the rest\n", "## Renamed\n"))
        fx.write(method, text)
        self.refused(lambda: prepared(self.folder), "method extract", "no `## Routing: critical nets by hand and locked, then the rest` section")
        fx.write(extract, held)
        os.remove(method)
        self.refused(lambda: prepared(self.folder), "no readable method")

    def test_a_plan_whose_table_of_own_items_cannot_be_read_is_refused_naming_what_is_missing(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
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
        os.remove(plan)
        self.refused(lambda: prepared(self.folder), "no readable plan")

    def test_a_folder_lacking_an_extract_an_index_or_an_image_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        for path, word in (("layout-facts.txt", "holds no layout-facts.txt"), ("method-extract.md", "holds no method-extract.md"),
                           ("views/index.txt", "holds no views/index.txt")):
            with self.subTest(path=path):
                folder = self.copy_of()
                os.remove(os.path.join(folder, path))
                self.refused(lambda: prepared(folder), word)
        folder = self.copy_of()
        os.remove(os.path.join(folder, "views", "layer-F.Cu.png"))
        self.refused(lambda: prepared(folder), "holds no rendered view image")
        folder = self.write_folder(os.path.join(self.root, "placed"), placement=True)
        os.remove(os.path.join(folder, "placement", "index.txt"))
        self.refused(lambda: prepared(folder), "placement folder with no placement/index.txt")
        fx.write(os.path.join(self.folder, "second", "other.kicad_pro"), "{}")
        self.refused(lambda: prepared(self.folder), "holds 2 KiCad project files")

    def test_a_layout_reviews_folder_is_refused_naming_the_fields_and_the_mode_that_writes_the_right_one(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        layout = fx.write_review_folder(os.path.join(self.root, "layout"))
        text = self.refused(lambda: prepared(layout), "number, kind, commit, views, check", "number, commit, views",
                            "--review critical-routing")
        self.assertIn("not a critical-routing pass's", text)

    def test_the_layout_callers_units_and_helpers_are_what_they_were_beside_the_shared_module(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        layout = fx.write_review_folder(os.path.join(self.root, "layout"), own=fx.OWN_ROWS)
        shared = review_catalogue.areas(layout, review_catalogue.LAYOUT_SECTION)
        self.assertEqual(review_caller_layout.areas(layout), shared)
        self.assertEqual(review_caller_layout.catalogue_split(layout), review_catalogue.catalogue_split(layout))
        self.assertEqual(review_caller_layout.own_items(layout), review_catalogue.own_items(layout))
        self.assertEqual(review_caller_layout.own_items(layout), ["BOARD-1", "BOARD-2"])
        self.assertEqual(list(review_caller_layout.unit_items(layout)),
                         [f"area-{code}" for code, _, _ in shared] + ["board-items", "plan-and-free-pass"])
        self.assertEqual(review_caller_layout.COUPLED, review_catalogue.COUPLED)
        self.assertIs(review_caller_layout.AREA, review_catalogue.AREA)
        with mock.patch.object(review_caller_layout, "COUPLED", (("FLOOR", "CLOCK"),)):
            units = review_caller_layout.unit_items(layout)
            self.assertEqual(review_caller_layout.coupled_to("area-FLOOR", units), ["area-CLOCK"],
                             "the layout caller still reads its own module's couplings")
        self.assertEqual(review_caller_layout.coupled_to("area-FLOOR", units), [])

    def test_the_catalogue_helpers_take_the_section_heading_and_name_one_that_is_missing(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        circuit = ("## Circuit practice catalogue\n\nThe circuit introduction.\n\n### Rails (RAIL)\n\n#### RAIL-1. A rail\n\n"
                   "#### RAIL-2. Another\n\n### Parts (PART)\n\n#### PART-1. A part\n\n")
        method = os.path.join(self.folder, "docs", "board-design-method.md")
        fx.write(method, slurp(method).replace("## Ordering", circuit + "## Ordering"))
        self.assertEqual(review_catalogue.areas(self.folder, "Circuit practice catalogue"),
                         [("RAIL", "Rails", ["RAIL-1", "RAIL-2"]), ("PART", "Parts", ["PART-1"])])
        self.assertEqual(review_catalogue.areas(self.folder)[0][0], "FLOOR", "the layout catalogue is the default")
        intro, blocks = review_catalogue.catalogue_split(self.folder, "Circuit practice catalogue")
        self.assertEqual((intro, sorted(blocks)), ("The circuit introduction.", ["PART", "RAIL"]))
        self.assertEqual(review_catalogue.listed_items_only(blocks["RAIL"], ["RAIL-2"]).count("#### "), 1)
        self.assertEqual(review_catalogue.coupled_to("area-A", {"area-A": [], "area-B": []}, (("A", "B"),)), ["area-B"])
        self.assertEqual(review_catalogue.coupled_to("area-A", {"area-A": [], "area-B": []}, ()), [])
        with self.assertRaises(review_catalogue.ReviewFolderProblem) as caught:
            review_catalogue.areas(self.folder, "Schematic practice catalogue")
        self.assertIn("no `## Schematic practice catalogue` section", str(caught.exception))
        fx.write(method, slurp(method).replace("The circuit introduction.", ""))
        with self.assertRaises(review_catalogue.ReviewFolderProblem) as caught:
            review_catalogue.catalogue_split(self.folder, "Circuit practice catalogue")
        self.assertIn("circuit practice catalogue in the method", str(caught.exception))
        self.assertIn("no introduction", str(caught.exception))


class TheSharedContext(Folder):
    def test_the_shared_context_holds_the_routing_section_and_the_whole_catalogue_and_no_unit_prompt(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        package = prepared(self.folder)
        shared = messages.shared_context(catalogue.admit(package.declaration, self.folder)).message
        for held in ("## Routing: critical nets by hand and locked, then the rest", "Steps of routing.", "### Floorplan (FLOOR)",
                     "#### FLOOR-2.", "### Grounding (GROUND)", "#### GROUND-1.", "### Clocks (CLOCK)", "#### CLOCK-1.",
                     "Intro of the catalogue.", "Steps of a review.", "LAYOUT FACTS", "=== image: views/layer-F.Cu.png ===",
                     "round.json"):
            self.assertIn(held, shared)
        for unit in package.declaration.units:
            self.assertNotIn(f"Your unit: {unit}", shared, "no unit's prompt is in the shared context")
        for absent in ("placement/", "PRE-ORDER", "check-report"):
            self.assertNotIn(absent, shared, "the pass has no placement view or check report unless given")

    def test_the_shared_context_artefacts_are_the_folders_extracts_records_and_every_image(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        declaration = prepared(self.folder).declaration
        design = fx.DESIGN
        self.assertEqual(sorted(declaration.artefacts), sorted([
            "layout-facts.txt", "method-extract.md", "round.json", "views/facts.txt", "views/index.txt", "views/layer-F.Cu.png",
            f"{design}/constraints.md", f"{design}/design-rules.md", f"{design}/layout-plan.md", f"{design}/separation-basis.yaml"]))
        self.assertEqual({name: artefact.kind for name, artefact in declaration.artefacts.items() if artefact.kind != "text"},
                         {"layout-facts.txt": "extract", "method-extract.md": "extract", "views/layer-F.Cu.png": "image"})
        self.assertEqual(declaration.added_during_round, ("added-views/*", "added-documents/*"))
        self.assertEqual(declaration.budget.wall_s, 350)
        self.assertEqual(set(declaration.needed), set(declaration.artefacts))
        for held in fx.BOARD_FILES:
            self.assertNotIn(held, declaration.artefacts if held.endswith(("kicad_pcb", "kicad_sch")) else (), "no board file")
        placed = prepared(self.write_folder(os.path.join(self.root, "placed"), placement=True)).declaration
        self.assertEqual(sorted(set(placed.artefacts) - set(declaration.artefacts)),
                         ["placement/index.txt", "placement/measures.txt", "placement/placement.png"])
        self.assertIn("the placement view was not rendered", prepared(self.folder).unit_text("area-FLOOR"))
        self.assertIn("the placement view among them", prepared(self.write_folder(os.path.join(self.root, "p2"), placement=True))
                      .unit_text("area-FLOOR"))

    def test_a_pass_after_the_first_names_no_review_record_in_its_context(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C1: From a synthetic review folder the caller's units are the layout catalogue's areas, found by the layout caller's own finding, and each unit's prompt asks for a verdict row for every item of its area that bears on the critical nets and `bears on no critical net` with the reason for every item that does not, and the units include one for the board's own items when the plan's table has rows, and none for a comparison with the plan or a free pass; the couplings are the layout caller's. A folder with no catalogue areas is refused naming what is missing. The layout caller's units and tests are unchanged by the shared helpers. Out of scope: the content of any catalogue item and which items do bear, which is the reviewer's judgement.
        folder = self.write_folder(os.path.join(self.root, "later"), number=2)
        package = prepared(folder)
        self.assertNotIn(f"{fx.DESIGN}/layout-review.md", package.declaration.artefacts)
        self.assertNotIn("earlier rounds", package.unit_text("area-FLOOR"))


class TheMerge(Folder):
    def test_a_pass_merges_one_verdict_for_every_item_in_the_checklist_order(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        out = merged(self.folder, dict(reversed(list(results().items()))), order=list(results()))
        self.assertEqual([row["Item"] for row in out["tables"]["Verdicts"]["rows"]], ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1"])
        folder = self.write_folder(os.path.join(self.root, "own"), own=fx.OWN_ROWS)
        given = {**results(), "board-items": {"Verdicts": [verdict("BOARD-1"), verdict("BOARD-2")], "Findings": []}}
        rows = merged(folder, given)["tables"]["Verdicts"]["rows"]
        self.assertEqual([row["Item"] for row in rows], ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1", "BOARD-1", "BOARD-2"])

    def test_an_item_with_no_verdict_row_and_an_item_with_two_fail_the_merge_naming_each(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1"), verdict("GROUND-1", "pass", "Judged again.")]
        text = self.refused(lambda: merged(self.folder, given), "item FLOOR-2 has no verdict row")
        self.assertIn("item GROUND-1 has 2 verdict rows", text)
        self.assertIn("judge it in unit area-FLOOR and run that unit again with --rerun", text)
        given = results()
        given["area-CLOCK"]["Verdicts"].append(verdict("MISC-7"))
        text = self.refused(lambda: merged(self.folder, given), "a verdict row for MISC-7")
        self.assertIn("an item of the checklist", text)
        folder = self.write_folder(os.path.join(self.root, "own"), own=fx.OWN_ROWS)
        given = {**results(), "board-items": {"Verdicts": [verdict("BOARD-1")], "Findings": []}}
        self.refused(lambda: merged(folder, given), "item BOARD-2 has no verdict row", "unit board-items")

    def test_a_pass_whose_number_commit_or_views_are_missing_or_malformed_fails_naming_each_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        for changes, word in (({"number": None}, "the round's number is None"), ({"number": 0}, "the round's number is 0"),
                              ({"number": "1"}, "the round's number is '1'"), ({"number": True}, "the round's number is True"),
                              ({"commit": None}, "the commit judged is None"),
                              ({"commit": "not a sha"}, "the commit judged is 'not a sha'"),
                              ({"views": None}, "the views are None"), ({"views": []}, "the views are []"),
                              ({"views": ["a\nb"]}, "the views are ['a\\nb']"), ({"views": [3]}, "the views are [3]"),
                              ({"views": ["```"]}, "the views are ['```']")):
            with self.subTest(changes=changes):
                folder = self.copy_of()
                fx.set_round(folder, **changes)
                self.refused(lambda: prepared(folder), word, "missing or malformed")
        folder = self.copy_of()
        fx.set_round(folder, fields=["number", "commit", "views", "kind"], kind="full")
        self.refused(lambda: prepared(folder), "not a critical-routing pass's")
        folder = self.copy_of()
        os.remove(os.path.join(folder, review_folder.ROUND_FILE))
        self.refused(lambda: prepared(folder), "round file", "cannot be read")
        folder = self.copy_of()
        fx.set_round(folder, number=2)
        fx.set_round(folder, number=None)
        self.refused(lambda: prepared(folder), "the round's number is None")

    def test_findings_are_numbered_in_the_checklist_order_and_the_citations_follow_the_renumbering(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1", "fail", "finding 2"), verdict("FLOOR-2", "fail", "finding 1")],
                               "Findings": [finding(1, "FLOOR-2", "layer-F.Cu at (1, 1): second item's"),
                                            finding(2, "FLOOR-1", "layer-F.Cu at (2, 2): first item's")]}
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "fail", "finding 1")]
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1", "layer-F.Cu at (3, 3): clock's")]
        out = merged(self.folder, given)
        rows = out["tables"]["Findings"]["rows"]
        self.assertEqual([(row["Finding"], row["Item"]) for row in rows], [(1, "FLOOR-1"), (2, "FLOOR-2"), (3, "CLOCK-1")])
        by_item = {row["Item"]: row["Why"] for row in out["tables"]["Verdicts"]["rows"]}
        self.assertEqual((by_item["FLOOR-1"], by_item["FLOOR-2"], by_item["CLOCK-1"]), ("finding 1", "finding 2", "finding 3"))

    def test_a_replicas_bears_on_no_critical_net_gives_way_to_another_replicas_verdict_for_the_item(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        for other, expected in (("pass", "pass"), ("not applicable", "not applicable")):
            with self.subTest(other=other):
                for order in (("r1", "r2"), ("r2", "r1")):
                    replicas = {"area-FLOOR": {
                        order[0]: {"Verdicts": [unbearing("FLOOR-1"), verdict("FLOOR-2")], "Findings": []},
                        order[1]: {"Verdicts": [verdict("FLOOR-1", other), verdict("FLOOR-2")], "Findings": []}}}
                    out = merged(self.folder, results(), replicas=replicas)
                    row = next(r for r in out["tables"]["Verdicts"]["rows"] if r["Item"] == "FLOOR-1")
                    by = out["tables"]["Verdicts"]["raised_by"][out["tables"]["Verdicts"]["rows"].index(row)]
                    self.assertEqual((row["Verdict"], by), (expected, [order[1]]), "the replica that judged it wins")
        replicas = {"area-FLOOR": {
            "r1": {"Verdicts": [unbearing("FLOOR-1"), verdict("FLOOR-2")], "Findings": []},
            "r2": {"Verdicts": [verdict("FLOOR-1", "fail", "finding 1"), verdict("FLOOR-2")], "Findings": [finding(1, "FLOOR-1")]}}}
        out = merged(self.folder, results(), replicas=replicas)
        rows = {r["Item"]: r for r in out["tables"]["Verdicts"]["rows"]}
        self.assertEqual(rows["FLOOR-1"]["Verdict"], "fail", "a fail by one replica stands over the other's bearing on no net")
        both = {"area-FLOOR": {r: {"Verdicts": [unbearing("FLOOR-1", "Both agree."), verdict("FLOOR-2")], "Findings": []}
                               for r in ("r1", "r2")}}
        out = merged(self.folder, results(), replicas=both)
        self.assertEqual(next(r for r in out["tables"]["Verdicts"]["rows"] if r["Item"] == "FLOOR-1")["Verdict"], NOT_BEARING)
        replicas = {"area-FLOOR": {
            "r1": {"Verdicts": [unbearing("FLOOR-1"), verdict("FLOOR-2")], "Findings": []},
            "r2": {"Verdicts": [verdict("FLOOR-1", "cannot judge", "needs crop-X: none"), verdict("FLOOR-2")], "Findings": []}}}
        self.refused(lambda: merged(self.folder, results(), replicas=replicas), "item FLOOR-1 is still cannot judge")

    def test_a_cannot_judge_fails_the_pass_naming_the_item_and_the_view_its_why_asks_for(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "needs crop-Y1: the views show no crop of the crystal")]
        self.refused(lambda: merged(self.folder, given), "item CLOCK-1 is still cannot judge", "asks for crop-Y1",
                     "render that view", "--add-view", "unit area-CLOCK", "--rerun")
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "the views do not show it")]
        self.assertIn("'the views do not show it'", self.refused(lambda: merged(self.folder, given), "item CLOCK-1 is still cannot judge"))
        for why in ("needs the datasheet of U1: the figure is not in the views", "the Specification gives the rating"):
            given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", why)]
            self.refused(lambda: merged(self.folder, given), "or run unit area-CLOCK again with --rerun if the document can be retrieved",
                         "`--add-document <review folder> --document <file> --source <where the figure comes from> "
                         "--cannot-judge-item CLOCK-1 --cannot-judge-why <the Why>`")
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "needs crop-Y1: no crop")]
        self.assertNotIn("--add-document", self.refused(lambda: merged(self.folder, given), "--add-view"), "a view is not a document")

    def test_a_recorded_cannot_judge_for_an_item_outside_the_pass_or_without_a_row_fails_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        self.add_view(item="CLOCK-9")
        text = self.refused(lambda: merged(self.folder, results()), "CLOCK-9", "not an item this pass judges", "exact name")
        self.assertNotIn("still cannot judge", text)
        folder = self.write_folder(os.path.join(self.root, "second"))
        self.add_view(item="CLOCK-1", folder=folder)
        given = results()
        given["area-CLOCK"]["Verdicts"] = []
        self.refused(lambda: merged(folder, given), "records a cannot judge for CLOCK-1", "no verdict row", "item CLOCK-1 has no verdict row")

    def test_a_reason_missing_for_an_item_bearing_on_no_net_and_a_pass_with_no_bearing_item_fail_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        for why in ("", "   ", "—", " - "):
            with self.subTest(why=why):
                given = results()
                given["area-CLOCK"]["Verdicts"] = [unbearing("CLOCK-1", why)]
                self.refused(lambda: merged(self.folder, given), "item CLOCK-1 is given as bearing on no critical net with no reason")
        given = {unit: {"Verdicts": [unbearing(item) for item in ids], "Findings": []} for unit, ids in ITEMS.items()}
        self.refused(lambda: merged(self.folder, given), "no item bears on a critical net in this pass")
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "not applicable", "No crystal.")]
        self.assertEqual(len(merged(self.folder, given)["tables"]["Verdicts"]["rows"]), 4, "one judged item is enough")

    def test_a_fail_needs_a_finding_of_its_own_item_and_a_finding_needs_a_fail(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "fail", "The crystal is far.")]
        self.refused(lambda: merged(self.folder, given), "item CLOCK-1 fails and no finding names it")
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "pass")]
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1")]
        self.refused(lambda: merged(self.folder, given), "finding 1 names item CLOCK-1, which does not fail in this pass")
        given["area-CLOCK"]["Verdicts"] = [unbearing("CLOCK-1")]
        self.refused(lambda: merged(self.folder, given), "which does not fail")
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "fail", "finding 1")]
        given["area-CLOCK"]["Findings"] = [finding(1, "CLOCK-1", "  ")]
        self.refused(lambda: merged(self.folder, given), "says nothing under What and where")
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1", "fail", "finding 1"), verdict("FLOOR-2", "fail", "finding 2")]
        given["area-FLOOR"]["Findings"] = [finding(1, "FLOOR-2"), finding(2, "FLOOR-1")]
        given["area-CLOCK"] = results()["area-CLOCK"]
        text = self.refused(lambda: merged(self.folder, given), "item FLOOR-1's Why cites finding 2")
        self.assertIn("a verdict cites only findings of its own item", text)
        out = merged(self.folder, {**results(), "area-CLOCK": {"Verdicts": [verdict("CLOCK-1", "fail", "finding 1")],
                                                              "Findings": [finding(1, "CLOCK-1")]}})
        self.assertEqual(len(out["tables"]["Findings"]["rows"]), 1)

    def test_a_rule_kind_verdict_is_not_judged_by_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-GROUND"]["Verdicts"] = [{**verdict("GROUND-1"), "Kind": "rule", "Rests on": "nothing the method names", "Why": "pass"}]
        rows = merged(self.folder, given)["tables"]["Verdicts"]["rows"]
        self.assertEqual([row["Rests on"] for row in rows if row["Item"] == "GROUND-1"], ["nothing the method names"])

    def test_a_checks_run_before_the_declaration_was_resolved_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        problems = real_load("critical_routing", TOOLS).module.checks({"Verdicts": {"rows": []}, "Findings": {"rows": []}})
        self.assertEqual(len(problems), 1)
        self.assertIn("before its declaration was resolved", problems[0])


class TheGuards(Folder):
    """A producer that omits, skips, duplicates or substitutes is refused on every path an answer takes: the first answer, a
    repair turn, the turn about its cannot judge rows, a re-run and the merge of replicas."""

    UNIT = "area-FLOOR"
    #: A reason left out for an item one replica gives as bearing on no critical net is no defect of the pass when another replica
    #: judged the item: the item has its verdict, and nothing of the empty row reaches the pass.
    MASKED_BY_A_REPLICA = ("lists an item with no reason",)

    @staticmethod
    def defects():
        def omit(tables):
            return {**tables, "Verdicts": [verdict("FLOOR-1")]}

        def twice(tables):
            return {**tables, "Verdicts": [verdict("FLOOR-1"), verdict("FLOOR-1", "pass", "Again."), verdict("FLOOR-2")]}

        def substitute(tables):
            return {**tables, "Verdicts": [verdict("FLOOR-1"), verdict("CLOCK-1")]}

        def off_checklist(tables):
            return {**tables, "Verdicts": tables["Verdicts"] + [verdict("MISC-7")]}

        def outside_the_set(tables):
            return {**tables, "Verdicts": [verdict("FLOOR-1"), verdict("FLOOR-2", "maybe")]}

        def fail_without_finding(tables):
            return {**tables, "Verdicts": [verdict("FLOOR-1", "fail", "Too thin."), verdict("FLOOR-2")]}

        def finding_for_a_pass(tables):
            return {"Verdicts": [verdict("FLOOR-1"), verdict("FLOOR-2")], "Findings": [finding(1, "FLOOR-2")]}

        def finding_of_another_item(tables):
            return {"Verdicts": [verdict("FLOOR-1", "fail", "finding 2"), verdict("FLOOR-2", "fail", "finding 1")],
                    "Findings": [finding(1, "FLOOR-1"), finding(2, "FLOOR-2")]}

        def cannot_judge_held(tables):
            return {**tables, "Verdicts": [verdict("FLOOR-1"), verdict("FLOOR-2", "cannot judge", "needs crop-X: none")]}

        def no_reason(tables):
            return {**tables, "Verdicts": [verdict("FLOOR-1"), unbearing("FLOOR-2", " ")]}

        def empty_finding(tables):
            return {"Verdicts": [verdict("FLOOR-1", "fail", "finding 1"), verdict("FLOOR-2")], "Findings": [finding(1, "FLOOR-1", "")]}

        def all_unbearing(tables):
            return {**tables, "Verdicts": [unbearing("FLOOR-1"), unbearing("FLOOR-2")]}
        return {"omits an item": omit, "gives an item twice": twice, "substitutes another unit's item": substitute,
                "gives a row for an item off the checklist": off_checklist, "gives a verdict outside the set": outside_the_set,
                "fails without a finding": fail_without_finding, "raises a finding for an item that passes": finding_for_a_pass,
                "cites another item's finding": finding_of_another_item, "leaves a cannot judge": cannot_judge_held,
                "lists an item with no reason": no_reason, "raises an empty finding": empty_finding}

    def others(self):
        return {unit: tables for unit, tables in results().items() if unit != self.UNIT}

    def assess(self, package, tables):
        return kit_results.assess({"tables": tables}, "", package.declaration.shape, self.UNIT,
                                  list(package.declaration.units[self.UNIT].items))

    def causes(self, package, attempt, others=None, replicas=False):
        """Why the run is refused for the answer that stands: the problems the kit holds against the attempt, which fail its unit
        when it still stands, and the causes the merge refuses the pass for."""
        found = [problem.line() for problem in attempt.problems]
        if attempt.tables is not None:
            units = {unit: {"r1": tables} for unit, tables in (others or self.others()).items()}
            units[self.UNIT] = {"r1": results()[self.UNIT], "r2": attempt.tables} if replicas else {"r1": attempt.tables}
            try:
                package.merge([self.UNIT] + list(others or self.others()), units)
            except merge.Refused as error:
                found += error.causes
        return found

    def test_every_defect_is_refused_on_the_first_answer_a_repair_the_cannot_judge_turn_a_rerun_and_the_replica_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        package = prepared(self.folder)
        for name, make in self.defects().items():
            bad = make(results()[self.UNIT])
            with self.subTest(defect=name):
                first = self.assess(package, bad)
                self.assertTrue(self.causes(package, first), f"first answer: {name}")
                record = kit_results.UnitRecord(self.UNIT)
                record.add(self.assess(package, bad))
                record.add(self.assess(package, bad))
                self.assertTrue(self.causes(package, record.standing), f"repair turn: {name}")
                turn = kit_results.UnitRecord(self.UNIT)
                held = self.assess(package, {**results()[self.UNIT], "Verdicts": [
                    verdict("FLOOR-1"), verdict("FLOOR-2", "cannot judge", "needs crop-X: none")]})
                held.judge_asked = True
                turn.add(held)
                turn.add(self.assess(package, bad))
                self.assertTrue(self.causes(package, turn.standing), f"cannot judge turn: {name}")
                again = prepared(self.folder)
                self.assertTrue(self.causes(again, self.assess(again, bad)), f"rerun: {name}")
                if name in self.MASKED_BY_A_REPLICA:
                    continue
                self.assertTrue(self.causes(package, self.assess(package, bad), replicas=True), f"replica merge: {name}")

    def test_a_replica_that_gives_no_reason_for_an_item_another_replica_judged_leaves_the_judged_verdict_in_the_pass(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        package = prepared(self.folder)
        bad = self.defects()["lists an item with no reason"](results()[self.UNIT])
        self.assertEqual(self.causes(package, self.assess(package, bad), replicas=True), [])
        units = {unit: {"r1": tables} for unit, tables in self.others().items()}
        units[self.UNIT] = {"r1": results()[self.UNIT], "r2": bad}
        rows = package.merge([self.UNIT] + list(self.others()), units)["tables"]["Verdicts"]["rows"]
        self.assertEqual({row["Item"]: row["Verdict"] for row in rows}["FLOOR-2"], "pass")
        self.assertFalse([row for row in rows if row["Verdict"] == NOT_BEARING])

    def test_a_pass_whose_every_answer_is_good_is_refused_on_none_of_those_paths(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        package = prepared(self.folder)
        good = self.assess(package, results()[self.UNIT])
        self.assertEqual(self.causes(package, good), [])
        self.assertEqual(self.causes(package, good, replicas=True), [])

    def test_a_repair_that_passes_a_fail_never_clears_it_on_the_first_answer_the_repair_or_the_cannot_judge_turn(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        package = prepared(self.folder)
        shape, items = package.declaration.shape, list(package.declaration.units[self.UNIT].items)
        failed = {"Verdicts": [verdict("FLOOR-1", "fail", "finding 1"), verdict("FLOOR-2")], "Findings": [finding(1, "FLOOR-1")]}
        for name, later in (("passes it", results()[self.UNIT]),
                            ("leaves it out", {"Verdicts": [verdict("FLOOR-2")], "Findings": []}),
                            ("gives it bears on no critical net", {"Verdicts": [unbearing("FLOOR-1"), verdict("FLOOR-2")], "Findings": []}),
                            ("gives it not applicable", {"Verdicts": [verdict("FLOOR-1", "not applicable"), verdict("FLOOR-2")],
                                                         "Findings": []})):
            with self.subTest(repair=name):
                for turn in ("repair", "cannot judge turn"):
                    record = kit_results.UnitRecord(self.UNIT)
                    first = self.assess(package, failed)
                    first.judge_asked = turn == "cannot judge turn"
                    record.add(first)
                    second = self.assess(package, later)
                    kit_results.mark_cleared(record.attempts, second, shape, "fail", items, self.UNIT)
                    record.add(second)
                    self.assertEqual(second.cleared, ["FLOOR-1"], turn)
                    verdicts = {row["Item"]: row["Verdict"] for row in record.standing.tables["Verdicts"]}
                    self.assertEqual(verdicts["FLOOR-1"], "fail", f"the {turn} did not clear the fail")
                    out = package.merge([self.UNIT] + list(self.others()), {**{unit: {"r1": tables} for unit, tables in self.others().items()},
                                                                         self.UNIT: {"r1": record.standing.tables}})
                    self.assertIn("fail", [row["Verdict"] for row in out["tables"]["Verdicts"]["rows"]])

    def test_the_rendered_file_name_is_held_to_an_allow_list_of_the_pass_number_alone(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        self.assertTrue(caller.RENDERED.fullmatch("pass-1.md"))
        self.assertTrue(caller.RENDERED.fullmatch("pass-120.md"))
        for name in ("pass-0.md", "pass-01.md", "pass-1.MD", "pass-1.md.", "../pass-1.md", "pass-1.md/", "pass-a.md", "pass-1 .md",
                     "pass--1.md", "record.json", "plan.json", "CON.md", "pass-1.txt", "pass-1.md\n"):
            self.assertIsNone(caller.RENDERED.fullmatch(name), name)
        files = rendered_files(self.folder, results())
        self.assertEqual(list(files), ["pass-1.md"])
        for name in files:
            self.assertTrue(kit_caller.rendered_name_ok(name))
            self.assertTrue(caller.RENDERED.fullmatch(name))
        for number in (0, -3, "2", None):
            package = prepared(self.folder)
            package.caller.module.pass_round = lambda review, number=number: {"number": number, "commit": "abc1234", "views": ["v"]}
            out = package.merge(list(results()), {unit: {"r1": tables} for unit, tables in results().items()})
            with self.assertRaises(merge.Refused) as caught:
                package.render(merge.plain_tables(out))
            self.assertIn("does not give a file name of the form pass-<n>.md", "; ".join(caught.exception.causes))


def rendered_files(folder, given):
    package = prepared(folder)
    out = package.merge(list(given), {unit: {"r1": tables} for unit, tables in given.items()})
    return package.render(merge.plain_tables(out))


class FakeHistory:
    """What the history command's verdict check reads of a repository: the method and the plan at one commit."""

    def __init__(self, method, plan):
        self.texts = {board_history.METHOD: method, "layout-plan.md": plan}
        self.order = ["c1"]

    def text(self, commit, path):
        return self.texts.get(path)

    def resolve(self, commit):
        return commit if commit in ("c0", "c1") else None

    def is_ancestor(self, first, second):
        return True


class TheRenderedPass(Folder):
    HAND_WRITTEN = """### Pass 1

**Board judged**: 1234567

**Views**: `task hw:views -- --board board.kicad_pcb --project board.kicad_pro --class Power --out <views>`, the placement view not rendered.

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|
| FLOOR-1 | judgement | function | pass | `layer-F.Cu` | Judged on the views. |
| GROUND-1 | judgement | function | fail | `layer-F.Cu` | A track is thin at (10, 10). |
| CLOCK-1 | judgement | function | cannot judge, then pass | `layer-F.Cu`; `added-views/crop-Y1.svg` | Cannot judge: needs crop-Y1. Judged on the views. |
| BOARD-1 | judgement | function | not applicable | `layout-plan.md` | The board has no such part. |

- `FLOOR-2`: No critical net's copper decides it.
- `BOARD-2`: It asks where the mounting holes sit, not of any critical net's copper.
"""

    def setUp(self):
        super().setUp()
        self.owned = self.write_folder(os.path.join(self.root, "owned"), own=fx.OWN_ROWS)

    def given(self):
        out = results(ITEMS)
        out["area-FLOOR"] = {"Verdicts": [verdict("FLOOR-1"), unbearing("FLOOR-2")], "Findings": []}
        out["area-GROUND"] = {"Verdicts": [verdict("GROUND-1", "fail", "finding 1")], "Findings": [finding(1, "GROUND-1", "A track is thin at (10, 10).")]}
        out["area-CLOCK"] = {"Verdicts": [verdict("CLOCK-1", "pass", "Judged on the views.")], "Findings": []}
        out["board-items"] = {"Verdicts": [verdict("BOARD-1", "not applicable", "The board has no such part.", "layout-plan.md"),
                                           unbearing("BOARD-2", "It asks where the mounting holes sit, not of any critical net's copper.")],
                              "Findings": []}
        return out

    def plan_with(self, folder, section):
        return slurp(os.path.join(folder, fx.DESIGN, "layout-plan.md")).rstrip("\n") + "\n\n" + section

    def read(self, folder, plan_text, name="pass 1"):
        """What the history command's reader finds in a plan's critical routing section, and the verdict check's lines."""
        lines = board_history.section(plan_text, board_history.CRITICAL)
        before, passes, other = board_history.subsections(lines, board_history.PASS)
        number, body = passes[0]
        header, rows, faults = board_history.table(body, board_history.CRITICAL_TABLE)[0], *board_history.table(body, board_history.CRITICAL_TABLE)[1:]
        given = board_history.fields(body, ["Board judged", "Views"])
        report = board_history.Report()
        method = slurp(os.path.join(folder, "docs", "board-design-method.md"))
        board_history.judge_verdicts(FakeHistory(method, plan_text), "layout-plan.md", name, body, None, None, "c1", report)
        return {"before": before, "other": other, "numbers": [n for n, _ in passes], "fields": sorted(given),
                "header": header is not None, "faults": faults, "cells": {len(row) for row in rows},
                "items": [row[0].strip("`") for row in rows],
                "steps": {row[0].strip("`"): [verdict for verdict, _ in board_history.steps(row[3])] for row in rows},
                "listed": [match.group(1) for match in (board_history.LISTED.match(line.strip()) for line in body) if match],
                "checks": [(check["verdict"], re.sub(r"\bc1\b", "<commit>", check["detail"])) for check in report.checks]}

    def resolved_folder(self):
        self.add_view(item="CLOCK-1", name="crop-Y1.svg", folder=self.owned)
        return self.owned

    def test_the_merged_pass_is_read_by_the_history_commands_reader_as_a_hand_written_pass_is(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        folder = self.resolved_folder()
        text = rendered(folder, self.given())
        mine = self.read(folder, self.plan_with(folder, text))
        theirs = self.read(folder, self.plan_with(folder, "## Critical routing\n\n" + self.HAND_WRITTEN))
        self.assertEqual(mine, theirs)
        self.assertEqual(mine["numbers"], [1])
        self.assertEqual(mine["fields"], ["Board judged", "Views"])
        self.assertEqual(mine["faults"], [])
        self.assertEqual(mine["before"], [])
        self.assertEqual(mine["other"], [])
        self.assertEqual(mine["items"], ["FLOOR-1", "GROUND-1", "CLOCK-1", "BOARD-1"])
        self.assertEqual(mine["listed"], ["FLOOR-2", "BOARD-2"])
        self.assertEqual(mine["steps"]["CLOCK-1"], ["cannot judge", "pass"])
        self.assertEqual(mine["steps"]["GROUND-1"], ["fail"], "a fail is a plain fail for the designer to put right")
        self.assertEqual(mine["cells"], {6})
        failed = [detail for verdict_, detail in mine["checks"] if verdict_ == "FAIL"]
        self.assertEqual(len(failed), 1)
        self.assertIn("fail for GROUND-1 has no later verdict with the commit that put it right", failed[0])
        self.assertFalse([detail for detail in failed if "neither judges" in detail or "times, in its table" in detail],
                         "every checklist item is judged or listed, once")

    def test_a_pass_with_no_fail_passes_the_history_commands_verdict_check_as_a_hand_written_one_does(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-1"), unbearing("FLOOR-2")]
        folder = self.owned
        text = rendered(folder, {**given, "board-items": {"Verdicts": [verdict("BOARD-1"), unbearing("BOARD-2")], "Findings": []}})
        mine = self.read(folder, self.plan_with(folder, text))
        self.assertTrue(all(verdict_ == "PASS" for verdict_, _ in mine["checks"]), mine["checks"])
        self.assertIn("every one of the 6 checklist items", mine["checks"][-1][1])
        hand = self.HAND_WRITTEN.replace("| GROUND-1 | judgement | function | fail | `layer-F.Cu` | A track is thin at (10, 10). |\n",
                                         "| GROUND-1 | judgement | function | pass | `layer-F.Cu` | Judged on the views. |\n").replace(
            "cannot judge, then pass", "pass")
        theirs = self.read(folder, self.plan_with(folder, "## Critical routing\n\n" + hand))
        self.assertEqual(mine["checks"], theirs["checks"])

    def test_an_item_left_out_or_listed_twice_in_a_pass_is_refused_by_the_reader_and_so_the_merge_refuses_it_first(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        folder = self.owned
        good = rendered(folder, {**results(), "board-items": {"Verdicts": [verdict("BOARD-1"), verdict("BOARD-2")], "Findings": []}})
        reader = self.read(folder, self.plan_with(folder, good))
        self.assertTrue(all(verdict_ == "PASS" for verdict_, _ in reader["checks"]), reader["checks"])
        broken = good.replace("| BOARD-2 | judgement | function | pass | layer-F.Cu | Judged on the views. |\n", "")
        self.assertNotEqual(broken, good)
        reader = self.read(folder, self.plan_with(folder, broken))
        self.assertIn("neither judges BOARD-2", " ".join(detail for _, detail in reader["checks"]))
        twice = good + "\n- `FLOOR-1`: Listed as well.\n"
        reader = self.read(folder, self.plan_with(folder, twice))
        self.assertIn("gives FLOOR-1 2 times", " ".join(detail for _, detail in reader["checks"]))
        given = {**results(), "board-items": {"Verdicts": [verdict("BOARD-1")], "Findings": []}}
        self.refused(lambda: merged(folder, given), "item BOARD-2 has no verdict row")
        given = {**results(), "board-items": {"Verdicts": [verdict("BOARD-1"), verdict("BOARD-2"), verdict("FLOOR-1")], "Findings": []}}
        self.refused(lambda: merged(folder, given), "item FLOOR-1 has 2 verdict rows")

    def test_the_first_pass_holds_the_section_heading_and_a_later_pass_the_pass_heading_alone(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        first = rendered(self.owned, {**results(), "board-items": {"Verdicts": [verdict("BOARD-1"), verdict("BOARD-2")], "Findings": []}})
        self.assertTrue(first.startswith("## Critical routing\n\n### Pass 1\n\n- **Board judged**: "))
        self.assertEqual(first.count("## Critical routing"), 1)
        later = self.write_folder(os.path.join(self.root, "later"), number=3, own=fx.OWN_ROWS)
        text = rendered(later, {**results(), "board-items": {"Verdicts": [verdict("BOARD-1"), verdict("BOARD-2")], "Findings": []}}, number=3)
        self.assertTrue(text.startswith("### Pass 3\n\n- **Board judged**: "))
        self.assertNotIn("## Critical routing", text)
        base = slurp(os.path.join(later, fx.DESIGN, "layout-plan.md"))
        earlier = base.rstrip("\n") + "\n\n## Critical routing\n\n" + self.HAND_WRITTEN + "\n### Pass 2\n\nplaceholder\n\n"
        appended = earlier + text
        lines = board_history.section(appended, board_history.CRITICAL)
        numbers = [number for number, _ in board_history.subsections(lines, board_history.PASS)[1]]
        self.assertEqual(numbers, [1, 2, 3], "appended below the earlier passes, which stay as they are")
        self.assertTrue(appended.startswith(base.rstrip("\n")))
        self.assertIn(self.HAND_WRITTEN, appended)

    def test_the_pass_holds_the_commit_the_views_as_run_and_says_when_the_placement_view_was_not_rendered(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        text = rendered(self.folder, results())
        sha = fx.round_file(self.folder)["commit"]
        self.assertIn(f"- **Board judged**: {sha}\n", text)
        self.assertIn("; the placement view was not rendered:", text)
        for command_line in fx.VIEW_COMMANDS:
            self.assertIn(command_line, text.split("```")[1])
        self.assertEqual(text.count("```"), 2)
        placed = self.write_folder(os.path.join(self.root, "placed"), placement=True)
        self.assertNotIn("was not rendered", rendered(placed, results()))
        self.add_view()
        resolved = {**results(), "area-CLOCK": {"Verdicts": [verdict("CLOCK-1")], "Findings": []}}
        self.assertIn("kicad-cli pcb export svg crop (added view: added-views/crop-Y1.svg)", rendered(self.folder, resolved))

    def test_a_resolved_cannot_judge_is_one_row_recording_cannot_judge_then_the_verdict_with_the_view_in_rests_on(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        self.add_view()
        for outcome in ("pass", "fail", "not applicable"):
            with self.subTest(outcome=outcome):
                given = results()
                given["area-CLOCK"] = {"Verdicts": [verdict("CLOCK-1", outcome, "finding 1" if outcome == "fail" else "Judged again.",
                                                             "crop-Y1 at (5, 5)")],
                                       "Findings": [finding(1, "CLOCK-1", "crop-Y1 at (5, 5): the crystal is far")] if outcome == "fail" else []}
                text = rendered(self.folder, given)
                row = next(line for line in text.splitlines() if line.startswith("| CLOCK-1 "))
                cells = [cell.strip() for cell in row.strip("|").split("|")]
                self.assertEqual(cells[3], f"cannot judge, then {outcome}")
                self.assertEqual(cells[4], "crop-Y1 at (5, 5); `added-views/crop-Y1.svg`")
                self.assertTrue(cells[5].startswith("Cannot judge: needs crop-Y1: no crop of the crystal."))
                self.assertEqual(board_history.steps(cells[3]), [("cannot judge", None), (outcome, None)])
        again = results()
        again["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "cannot judge", "needs crop-Y2: still not enough")]
        self.refused(lambda: merged(self.folder, again), "item CLOCK-1 is still cannot judge", "asks for crop-Y2")

    def test_a_resolved_cannot_judge_with_a_document_and_one_that_ends_bearing_on_no_net_are_recorded_too(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        self.add_document()
        given = results()
        given["area-CLOCK"]["Verdicts"] = [verdict("CLOCK-1", "pass", "The pin spacing is 2.54 mm.", "y1-pins.txt")]
        text = rendered(self.folder, given)
        row = next(line for line in text.splitlines() if line.startswith("| CLOCK-1 "))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(cells[3], "cannot judge, then pass")
        self.assertEqual(cells[4], "y1-pins.txt; `added-documents/y1-pins.txt`")
        self.assertNotIn("added view", text, "a document has no rendering command")
        given["area-CLOCK"]["Verdicts"] = [unbearing("CLOCK-1", "On reading the datasheet no critical net's copper decides it.")]
        text = rendered(self.folder, {**given, "area-GROUND": results()["area-GROUND"]})
        self.assertNotIn("| CLOCK-1 ", text)
        listed = next(line for line in text.splitlines() if line.startswith("- `CLOCK-1`"))
        self.assertIn("Cannot judge: needs the datasheet of Y1", listed)
        self.assertIn("On reading the datasheet", listed)

    def test_a_fail_is_rendered_as_a_plain_fail_with_the_findings_what_and_where_in_its_why(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-GROUND"] = {"Verdicts": [verdict("GROUND-1", "fail", "Ground is thin, finding 1.")],
                                "Findings": [finding(1, "GROUND-1", "layer-F.Cu at (10, 10): the ground is a 0.2 mm trace")]}
        text = rendered(self.folder, given)
        row = next(line for line in text.splitlines() if line.startswith("| GROUND-1 "))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(cells[3], "fail")
        self.assertEqual(cells[5], "Ground is thin, layer-F.Cu at (10, 10): the ground is a 0.2 mm trace.")
        self.assertNotIn("then", cells[3])
        self.assertNotIn("Findings", text)
        self.assertNotIn("finding 1", text)
        self.assertEqual(board_history.steps(cells[3]), [("fail", None)])
        two = {"Verdicts": [verdict("GROUND-1", "fail", "finding 1")],
               "Findings": [finding(1, "GROUND-1", "layer-F.Cu at (1, 1): first"), finding(2, "GROUND-1", "layer-F.Cu at (2, 2): second")]}
        row = next(line for line in rendered(self.folder, {**results(), "area-GROUND": two}).splitlines() if line.startswith("| GROUND-1 "))
        self.assertTrue(row.rstrip(" |").endswith("layer-F.Cu at (1, 1): first Also: layer-F.Cu at (2, 2): second"), row)

    def test_bears_on_no_critical_net_items_are_listed_once_with_their_reasons_below_the_table(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-FLOOR"]["Verdicts"] = [unbearing("FLOOR-1", "It asks of the\nplacement | alone &\r\nnothing else."), unbearing("FLOOR-2")]
        text = rendered(self.folder, given)
        table, _, listed = text.partition("\n\n- `")
        self.assertNotIn("| FLOOR-1 ", table)
        self.assertNotIn("| FLOOR-2 ", table)
        lines = ("- `" + listed).splitlines()
        self.assertEqual(lines, ["- `FLOOR-1`: It asks of the placement | alone & nothing else.", "- `FLOOR-2`: No critical net's copper decides it."])
        self.assertEqual(text.count("`FLOOR-1`"), 1)
        self.assertEqual(text.count("`FLOOR-2`"), 1)
        for line in lines:
            self.assertRegex(line, board_history.LISTED)

    def test_a_vertical_bar_or_line_break_in_a_table_cell_is_escaped_and_the_reader_keeps_the_shape(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-GROUND"]["Verdicts"] = [verdict("GROUND-1", "pass", "two\nlines and a||b & more", "layer-F.Cu | layer-B.Cu")]
        text = rendered(self.folder, given)
        self.assertNotIn("\r", text)
        self.assertIn("layer-F.Cu &#124; layer-B.Cu", text)
        self.assertIn("two&#10;lines and a&#124;&#124;b &amp; more", text)
        reader = self.read(self.folder, self.plan_with(self.folder, text))
        self.assertEqual(reader["faults"], [])
        self.assertEqual(reader["cells"], {6})

    def test_the_rendered_pass_is_one_plain_file_named_for_its_number_whose_name_the_kit_accepts(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        files = rendered_files(self.folder, results())
        self.assertEqual(list(files), ["pass-1.md"])
        self.assertTrue(kit_caller.rendered_name_ok("pass-1.md"))
        later = self.write_folder(os.path.join(self.root, "later"), number=12)
        self.assertEqual(list(rendered_files(later, results())), ["pass-12.md"])
        self.assertTrue(files["pass-1.md"].endswith("\n"))
        self.assertFalse(files["pass-1.md"].endswith("\n\n"))

    def test_the_render_sorts_rows_by_the_checklist_whatever_order_the_units_returned_them_in(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        given = results()
        given["area-FLOOR"]["Verdicts"] = [verdict("FLOOR-2"), verdict("FLOOR-1")]
        text = rendered(self.folder, given)
        order = [text.index(f"| {item} ") for item in ("FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1")]
        self.assertEqual(order, sorted(order))


class Command:
    """The kit's command run on a review folder with the critical-routing caller, the stub playing the agent command line."""

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
        status = command.main(["--caller", "critical_routing", "--callers", TOOLS, "--review", self.folder, "--out", self.out]
                              + list(extra), out, err, repo=os.path.join(self.case.root, "no-repository"))
        return status, out.getvalue(), err.getvalue()

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


def model_of(call):
    return call["args"][call["args"].index("--model") + 1]


class TheCommandEndToEnd(Folder):
    def test_the_command_writes_the_pass_as_text_and_as_json_and_the_history_reader_reads_it(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        run = Command(self)
        run.scenario(verdicts={"CLOCK-1": "fail", "FLOOR-2": NOT_BEARING})
        status, text, err = run.go("--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        report = json.loads(text)
        self.assertEqual(report["rendered"], ["pass-1.md"])
        written = slurp(os.path.join(run.out, "pass-1.md"))
        self.assertTrue(written.startswith("## Critical routing\n\n### Pass 1\n"))
        self.assertEqual([row["Item"] for row in report["tables"]["Verdicts"]["rows"]], ["FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1"])
        plan = slurp(os.path.join(self.folder, fx.DESIGN, "layout-plan.md")).rstrip("\n") + "\n\n" + written
        lines = board_history.section(plan, board_history.CRITICAL)
        passes = board_history.subsections(lines, board_history.PASS)[1]
        self.assertEqual([number for number, _ in passes], [1])
        rows = board_history.table(passes[0][1], board_history.CRITICAL_TABLE)[1]
        self.assertEqual([(row[0], row[3]) for row in rows], [("FLOOR-1", "pass"), ("GROUND-1", "pass"), ("CLOCK-1", "fail")])
        self.assertIn("layer-F.Cu at (1, 1): off its place", written, "the finding's what and where is in the fail's Why")
        self.assertEqual(report["same_place"], [])
        second = Command(self)
        second.out = os.path.join(self.root, "out-text")
        status, text, err = second.go("--model", SMALL)
        self.assertEqual(status, 0, text + err)
        self.assertIn("RENDERED | pass-1.md", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | WRITTEN"))

    def test_a_round_file_with_a_missing_field_or_a_layout_reviews_is_refused_before_any_session_starts(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
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
        layout = fx.write_review_folder(os.path.join(self.root, "layout"))
        other = Command(self, folder=layout, out="out-layout")
        other.scenario()
        status, text, _ = other.go("--format", "json")
        self.assertEqual(status, 1, text)
        self.assertIn("not a critical-routing pass's", "; ".join(json.loads(text)["refusals"]))
        self.assertEqual(other.calls(), [])

    def test_a_merge_that_fails_names_the_item_and_keeps_the_units_results(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        run = Command(self)
        run.scenario(verdicts={"GROUND-1": "cannot judge"}, why={"GROUND-1": "needs crop-U3: no crop of U3"})
        status, text, _ = run.go("--format", "json", "--model", SMALL)
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        joined = "; ".join(report["refusals"])
        self.assertIn("item GROUND-1 is still cannot judge", joined)
        self.assertIn("asks for crop-U3", joined)
        self.assertIn("unit area-GROUND", joined)
        self.assertFalse(os.path.exists(os.path.join(run.out, "pass-1.md")), "nothing is rendered from a refused merge")
        self.assertTrue(os.path.exists(os.path.join(run.out, "record.json")), "the units' results are kept")

    def test_a_cannot_judge_is_resolved_by_adding_the_view_and_running_that_unit_again_and_the_row_records_it(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C2: Over synthetic unit results, the merge fails naming an item that has no verdict row and an item given twice; it fails a pass whose number, commit judged or views are missing or malformed; and it renders the pass in the form the method gives for the plan's critical routing section as a file in the output folder, which the check's runner appends below the earlier passes and never in place of one. A plan holding the rendered pass appended to a synthetic plan and a hand-written pass are passed through the reader the board placement and critical routing history command uses, and what it reads from the two has the same shape. It fails a pass that still holds a cannot judge, naming the item and the view it needs, and renders a resolved one as `cannot judge, then <verdict>`; a fail is rendered as a plain fail for the designer to put right in the row before the router runs. A replica's `bears on no critical net` gives way to another replica's verdict for the same item. Out of scope: whether a verdict is right and the history command's checks of the repository's history.
        run = Command(self)
        run.scenario(verdicts={"CLOCK-1": "cannot judge"}, why={"CLOCK-1": "needs crop-Y1: no crop of the crystal"})
        self.assertEqual(run.go("--format", "json", "--model", SMALL)[0], 1)
        before = {path: slurp(os.path.join(self.folder, path)) for path in ("round.json", "layout-facts.txt", "method-extract.md")}
        view = os.path.join(self.root, "crop-Y1.png")
        fx.write(view, fx.kit_fx.png(60, 40, 90))
        status, text = fx.run_folder(["--add-view", self.folder, "--view", view, "--view-command", "kicad-cli pcb export png crop",
                                      "--cannot-judge-item", "CLOCK-1", "--cannot-judge-why", "needs crop-Y1: no crop of the crystal"])
        self.assertEqual(status, 0, text)
        self.assertEqual(before, {path: slurp(os.path.join(self.folder, path)) for path in before}, "no shared-context file changed")
        calls_before = len(run.calls())
        run.scenario(verdicts={"CLOCK-1": "pass"})
        status, text, err = run.go("--rerun", "area-CLOCK", "--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        written = slurp(os.path.join(run.out, "pass-1.md"))
        row = next(line for line in written.splitlines() if line.startswith("| CLOCK-1 "))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(cells[3], "cannot judge, then pass")
        self.assertIn("`added-views/crop-Y1.png`", cells[4])
        self.assertIn("kicad-cli pcb export png crop (added view: added-views/crop-Y1.png)", written.split("| Item |")[0])
        again = run.calls()[calls_before:]
        forks = [call for call in again if call["resume"] is not None]
        self.assertEqual(len(again) - len(forks), 1, "one shared context, started again for the run")
        self.assertEqual(json.loads(text)["reran"][0]["units"], ["area-CLOCK"])
        self.assertEqual({tuple(call["units"]) for call in forks}, {("area-FLOOR", "area-GROUND", "area-CLOCK")},
                         "forks of the unit's group alone")


class TheToolGrant(Folder):
    def test_the_caller_grants_the_read_tools_and_the_one_retrieval_tool_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C6: Over synthetic declarations and a stub executor, the critical-routing declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        package = prepared(self.folder)
        self.assertEqual(package.tools, ("Read", "Glob", "Grep", "WebFetch"))
        self.assertIs(caller.retrieval, True)
        spec = messages.make_spec(package.declaration, package.tools, self.folder, SMALL)
        self.assertEqual(spec.expected_tools, sorted(["Read", "Glob", "Grep", "WebFetch", "StructuredOutput"]))
        loaded = real_load("critical_routing", TOOLS)
        self.assertEqual(kit_caller.attribute_problems(loaded), [])
        self.assertEqual(kit_caller.granted_tools(loaded), ("Read", "Glob", "Grep", "WebFetch"))
        for tool in ("Bash", "Write", "Edit", "Task", "NotebookEdit"):
            self.assertNotIn(tool, package.tools)

    def test_every_reviewer_is_started_with_the_four_tools_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C6: Over synthetic declarations and a stub executor, the critical-routing declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        run = Command(self)
        run.scenario()
        status, text, err = run.go("--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        calls = run.calls()
        forks = [call for call in calls if call["resume"] is not None]
        self.assertEqual(len(forks), 2, "one group of two replicas")
        self.assertEqual({call["tools"] for call in calls}, {GRANT}, "the shared context and every reviewer")
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
        status, text, _ = run.go("--format", "json", "--model", SMALL)
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        self.assertEqual(report["result"], "REFUSED")
        self.assertIsNone(json.loads(slurp(os.path.join(run.out, "record.json")))["merged"])
        lines = report["refusals"]
        named = sorted(re.match(r"unit (.+?) \(group (G\d+), replica (\d+)\) failed", line).groups() for line in lines)
        self.assertEqual(named, [("area-FLOOR, area-GROUND, area-CLOCK", "G1", "1"), ("area-FLOOR, area-GROUND, area-CLOCK", "G1", "2")],
                         "every reviewer that started badly is named with the units it was to judge")
        for line in lines:
            self.assertRegex(line, r"session G\d\.r\d\.a1 started")
        return lines[0]

    def test_a_session_that_reports_a_different_tool_set_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C6: Over synthetic declarations and a stub executor, the critical-routing declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "WebFetch", "Bash", "StructuredOutput"])
        self.assertIn("started with tools", line)
        self.assertIn("Bash", line)
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "StructuredOutput"])
        self.assertIn("WebFetch", line, "a reviewer that lost the retrieval tool is refused too")
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "WebFetch", "Write", "Edit", "StructuredOutput"])
        self.assertIn("Write", line)

    def test_a_session_that_reports_an_mcp_server_or_another_working_directory_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C6: Over synthetic declarations and a stub executor, the critical-routing declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        line = self.reviewer_refused(fork_mcp=True)
        self.assertIn("MCP servers", line)
        line = self.reviewer_refused(fork_cwd=os.path.join(self.root, "elsewhere"))
        self.assertIn("started in", line)
        self.assertIn(self.folder, line, "the folder its specification names")


class TheReplicasBudgetAndBound(Folder):
    def test_the_declaration_sets_two_replicas_a_full_and_a_hunt_framing_on_the_small_tier_model(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C6: Over synthetic declarations and a stub executor, the critical-routing declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        loaded = real_load("critical_routing", TOOLS)
        self.assertEqual(command.POLICY_ATTRIBUTE, "replica_policy")
        policy = ensemble.parse_policy(loaded.module.replica_policy)
        self.assertEqual(policy.ids, ["full", "hunt"])
        self.assertEqual([variant.model for variant in policy.variants], [SMALL, SMALL])
        self.assertEqual(caller.SMALL_MODEL, SMALL)
        self.assertEqual(review_caller_layout.SMALL_MODEL, caller.SMALL_MODEL, "the layout caller's small tier")
        full, hunt = policy.variants
        self.assertEqual((full.item_order, full.view_order, full.terse), ("given", "given", False))
        self.assertEqual((hunt.item_order, hunt.view_order, hunt.terse), ("reversed", "reversed", True))
        self.assertEqual(dict(policy.by_stakes)["normal"], 2, "a design loop's units carry normal stakes")
        self.assertEqual(max(count for stakes, count in policy.by_stakes if stakes != "low"), 2)
        package = prepared(self.folder)
        self.assertEqual({unit.stakes for unit in package.declaration.units.values()}, {"normal"})
        counts = ensemble.replicas_by_unit(package.declaration, policy)
        self.assertEqual(set(counts.values()), {2})

    def test_the_time_budget_is_350_seconds_and_the_bound_30(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C6: Over synthetic declarations and a stub executor, the critical-routing declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        self.assertEqual(caller.WALL_SECONDS, 350)
        self.assertEqual(prepared(self.folder).declaration.budget.wall_s, 350)
        self.assertEqual(caller.bound, 30)
        self.assertEqual(review_caller_layout.bound, caller.bound)
        loaded = real_load("critical_routing", TOOLS)
        self.assertEqual(loaded.module.bound, 30)
        self.assertEqual(kit_caller.attribute_problems(loaded), [])

    def test_the_two_replicas_run_on_the_small_model_with_one_shared_context_when_it_is_the_reviews_model(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C6: Over synthetic declarations and a stub executor, the critical-routing declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        run = Command(self)
        run.scenario()
        status, text, err = run.go("--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        plan = json.loads(text)["plan"]
        self.assertEqual(plan["variants"], ["full", "hunt"])
        self.assertEqual(plan["contexts"], [], "the replicas' model is the review's own, so no second shared context")
        calls = run.calls()
        self.assertEqual({model_of(call) for call in calls}, {SMALL})
        self.assertEqual(len([call for call in calls if call["resume"] is None]), 1)
        self.assertEqual(len([call for call in calls if call["resume"] is not None]), 2)
        prompts = [call["prompt"] for call in calls if call["resume"] is not None]
        self.assertTrue(any(prompt.startswith("Hunt for failures.") for prompt in prompts), "the hunt framing")
        self.assertTrue(any(not prompt.startswith("Hunt for failures.") for prompt in prompts), "the full framing")
        hunt = next(prompt for prompt in prompts if prompt.startswith("Hunt for failures."))
        self.assertLess(hunt.index("- FLOOR-2"), hunt.index("- FLOOR-1"), "the hunt takes the items the other way round")
        other = Command(self, out="out-default")
        other.scenario()
        status, text, err = other.go("--format", "json")
        self.assertEqual(status, 0, text + err)
        self.assertEqual([(context["model"], context["variants"]) for context in json.loads(text)["plan"]["contexts"]],
                         [(SMALL, ["full", "hunt"])], "without the review's model set, the replicas have a context of their own")

    def test_a_plan_of_forty_forks_runs_at_most_thirty_at_once_and_a_smaller_plan_all_of_its_forks(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C6: Over synthetic declarations and a stub executor, the critical-routing declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        from review_kit import scheduler
        state = {"now": 0, "peak": 0, "bounds": []}
        lock = threading.Lock()
        real = scheduler.ThreadedConcurrency.run

        def counted(self, tasks, bound):
            state["bounds"].append(bound)

            def wrap(task):
                def inner():
                    with lock:
                        state["now"] += 1
                        state["peak"] = max(state["peak"], state["now"])
                    try:
                        time.sleep(0.05)
                        return task()
                    finally:
                        with lock:
                            state["now"] -= 1
                return inner
            return real(self, [wrap(task) for task in tasks], bound)
        run = Command(self)
        run.scenario()
        with mock.patch.object(scheduler.ThreadedConcurrency, "run", counted):
            status, text, err = run.go("--format", "json", "--replicas", "40", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        plan = json.loads(text)["plan"]
        self.assertEqual(plan["forks"], 40)
        self.assertEqual(plan["bound"], 30)
        self.assertEqual(state["bounds"][-1], 30)
        self.assertLessEqual(state["peak"], 30)
        self.assertGreater(state["peak"], 1)
        small = Command(self, out="out-small")
        small.scenario()
        status, text, err = small.go("--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        plan = json.loads(text)["plan"]
        self.assertLess(plan["forks"], 30)
        self.assertEqual(plan["bound"], plan["forks"])


class Documentation(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def step(self):
        method = self.read("docs", "board-design-method.md")
        start = method.index("### 4. Check the critical routing against the catalogue, before the router runs")
        return self.flat(method[start:method.index("### 5. Record the critical-class copper", start)])

    def test_the_routing_step_says_the_check_may_be_judged_by_unit_what_the_merge_checks_and_who_supplies_the_fields(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C3: The method's routing section, in its step that checks the critical routing against the catalogue, says that the check may be judged by unit, what the merge checks, that its pass numbers and views are supplied by whoever runs it, and that judging it with one reviewer stays valid; the hardware notes describe the caller and what it needs. The sentence that a proof is repeated after the step changes names the form that changed. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout review section.
        step = self.step()
        for words in ("This check may be judged by unit instead of by one reviewer", "a way of carrying out this step, and it changes none of it",
                      "one reviewer for each area of the", "one for the board's own items",
                      "decides which of the items of its unit bear on the critical nets", "`bears on no critical net` with the reason",
                      "with no model, into one pass in which every item of the checklist has one verdict row in the table or one line in the list below it",
                      "The pass's own fields, its number, the commit judged and the views, come from whoever runs the check",
                      "since the merge has no model to write them", "task hw:review-folder -- --review critical-routing",
                      "in which an item has no verdict row or has two", "in which a verdict row is for an item that is not on the checklist",
                      "in which a `cannot judge` is left, in which a finding is of an item that does not fail, in which a `fail` cites another item's finding, in which a finding's what and where is empty, in which an item that bears on no critical net has no reason, or in which no item bears on a critical net, and it names the item", "renders a `fail` as a plain `fail`",
                      "for the designer to put right in the row before the router runs",
                      "the row is written `cannot judge, then <verdict>`",
                      "appends below the section's earlier passes, never in place of one the router has run after",
                      "judging the whole pass with one reviewer, a person or an agent session that does not use the command, stays valid",
                      "every pass already recorded stands", "task hw:review-run -- --caller critical_routing",
                      "with two reviewers of each so that a fail either raises stands"):
            self.assertIn(words, step, f"the routing step says {words!r}")

    def test_the_method_says_the_fanned_out_form_is_relied_on_only_once_its_proof_is_recorded(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C3: The method's routing section, in its step that checks the critical routing against the catalogue, says that the check may be judged by unit, what the merge checks, that its pass numbers and views are supplied by whoever runs it, and that judging it with one reviewer stays valid; the hardware notes describe the caller and what it needs. The sentence that a proof is repeated after the step changes names the form that changed. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout review section.
        step = self.step()
        self.assertIn("The fanned-out form is relied on only once its proof is recorded, and until then this step is carried out with one reviewer.", step)

    def test_the_sentence_that_a_proof_is_repeated_names_the_form_that_changed(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C3: The method's routing section, in its step that checks the critical routing against the catalogue, says that the check may be judged by unit, what the merge checks, that its pass numbers and views are supplied by whoever runs it, and that judging it with one reviewer stays valid; the hardware notes describe the caller and what it needs. The sentence that a proof is repeated after the step changes names the form that changed. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout review section.
        step = self.step()
        sentence = step[step.index("Repeat the proof after changing this step"):]
        for words in ("in the form that changed", "a change to the step as one reviewer follows it repeats the single-reviewer form",
                      "a change to how the pass is judged by unit, to the critical-routing caller or to the review folder it reads repeats the fanned-out form",
                      "each form's recorded proof standing for that form alone"):
            self.assertIn(words, sentence)
        self.assertNotIn("Repeat the proof after changing this step.", step)

    def test_the_hardware_notes_describe_the_caller_and_the_folder_mode_and_what_each_needs(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C3: The method's routing section, in its step that checks the critical routing against the catalogue, says that the check may be judged by unit, what the merge checks, that its pass numbers and views are supplied by whoever runs it, and that judging it with one reviewer stays valid; the hardware notes describe the caller and what it needs. The sentence that a proof is repeated after the step changes names the form that changed. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout review section.
        notes = self.read("hardware", "README.md")
        section = self.flat(notes[notes.index("## The critical-routing check by unit"):].split("\n## ")[0])
        for words in ("review_folder.py", "review_caller_critical_routing.py", "review_catalogue.py", "--review critical-routing",
                      "`round.json` holds no kind and no check lines", "`method-extract.md` holds the routing section",
                      "The placement view is taken only when `--placement` is given, and the pre-order check's report not at all",
                      "A pass after the first copies no review record", "`area-<code>`", "`board-items`",
                      "there is no unit for a comparison with the plan or a free pass", "power with mains and the manufacturing items with power",
                      "`Read`, `Glob`, `Grep` and `WebFetch`", "`bears on no critical net`", "last of the verdicts",
                      "exactly one verdict row", "`pass-<n>.md`", "`## Critical routing`", "`| Item | Kind | Severity | Verdict | Rests on | Why |`",
                      "A fail is rendered as a plain `fail`", "`fail, then <verdict> at <commit>`", "no findings table and no round number",
                      "never in place of one", "the pass number, the commit judged and the views are theirs to give",
                      "`cannot judge, then <verdict>`", "`--add-view` and `--add-document`", "`--rerun`", "`claude-haiku-5-5`",
                      "`--model`", "a full and a hunt framing", "350 seconds", "`bound`, 30", "the agent command line on the search path and logged in",
                      "no KiCad", "The tests need no model and no KiCad", "relied on only once its proof is recorded"):
            self.assertIn(words, section, f"the hardware notes' section says {words!r}")
        listed = self.flat(next(line for line in notes.splitlines() if line.startswith("- `task hw:test` runs")))
        for words in ("review kit", "layout review's caller", "critical-routing check's caller", "review folder command",
                      "layout review proof command"):
            self.assertIn(words, listed)
        self.assertIn("the critical-routing check's caller and the catalogue helpers it shares with the layout caller", notes.splitlines()[5])
        self.assertIn("the layout review's caller for it, the command that writes a committed board's review folder", notes.splitlines()[5])
        commands = notes[notes.index("## The commands"):notes.index("## The schematic sheets")]
        self.assertIn("--review critical-routing", commands)

    def test_the_task_runner_names_the_folder_mode_and_the_new_callers_tests_in_both_test_descriptions(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING.C3: The method's routing section, in its step that checks the critical routing against the catalogue, says that the check may be judged by unit, what the merge checks, that its pass numbers and views are supplied by whoever runs it, and that judging it with one reviewer stays valid; the hardware notes describe the caller and what it needs. The sentence that a proof is repeated after the step changes names the form that changed. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout review section.
        taskfile = self.read("Taskfile.yml")
        folder = self.flat(taskfile[taskfile.index("  hw:review-folder:"):].splitlines()[1])
        for words in ("--review critical-routing", "round file holds the pass number, the commit judged and the views and no kind or check lines",
                      "method extract adds the routing section", "takes the placement view only when --placement is given",
                      "takes no pre-order check report", "copies no review record for a later pass"):
            self.assertIn(words, folder)
        descriptions = (taskfile[taskfile.index("  hw:test:\n"):].splitlines()[1], taskfile[taskfile.index("  hw:test:round:"):].splitlines()[1])
        for text in descriptions:
            for words in ("review kit", "layout review", "critical-routing check", "review folder command", "layout review proof command"):
                self.assertIn(words, text)
        notes = self.read("hardware", "README.md")
        listed = next(line for line in notes.splitlines() if line.startswith("- `task hw:test` runs"))
        for words in ("critical-routing check's caller", "shared catalogue helpers"):
            self.assertIn(words, listed)
            self.assertIn(words.replace("shared catalogue helpers", "catalogue helpers"), descriptions[0])


if __name__ == "__main__":
    unittest.main()
