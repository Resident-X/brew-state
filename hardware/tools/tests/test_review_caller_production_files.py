#!/usr/bin/env python3
"""The production-files check as a caller of the review kit command, over synthetic review folders.

The caller is loaded as the kit loads it and run as shipped: its declaration, prompts, tool grant, checks and rendering are
exercised through the kit's own functions, and through the kit's command against a stand-in for the agent command line. The
method, the placement file, the drawings, the layers and every verdict are synthetic. No model, no KiCad and no gerbonara is
used, and the real agent command line is never run.
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

import layout_fixtures as fx  # noqa: E402
import production_fixtures as pf  # noqa: E402
import review_caller_layout  # noqa: E402
import review_caller_production_files as caller  # noqa: E402
import review_folder  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import command, ensemble, merge, messages, planner  # noqa: E402
from review_kit import results as kit_results  # noqa: E402
from review_kit import executor as ex  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
MATCHES, DIFFERS, CANNOT = "matches", "differs", "cannot judge"
GRANT = "Read,Glob,Grep"
MID = "claude-sonnet-5-5"
SMALL = "claude-haiku-5-5"
PART_UNIT, TWO_UNIT, NODRAW_UNIT, BARE_UNIT = "fp2-lib-c-0603", "fp1-lib-r-0603-2", "nodrawing4-lib-odd-1", "nodrawing5-no-drawing"

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
layers = scenario["layers"]
found = 0
for unit, body in re.findall(r"Your unit: (\\S+)\\n(.*?)(?=Your unit: |\\Z)", text, re.S):
    for item in re.findall(r"^- (\\S+)$", body, re.M):
        verdict = scenario.get("model_verdicts", {}).get(model, {}).get(item) or scenario.get("verdicts", {}).get(item)
        verdict = verdict or ("cannot judge" if unit.startswith("nodrawing") else "matches")
        why = scenario.get("why", {}).get(item, "Agrees with the preview.")
        if verdict == "differs":
            found += 1
            why = scenario.get("why", {}).get(item, "finding %d" % found)
            tables["Findings"].append({"Finding": found, "Item": item, "What and where": "off its place at (%d, %d)" % (found, found)})
        if verdict == "cannot judge" and item not in scenario.get("why", {}):
            why = "needs a drawing of the footprint"
        part = item not in layers
        tables["Verdicts"].append({"Item": item, "Position (file / preview)": "same" if part else "\\u2014",
                                   "Rotation (file / preview)": "same" if part else "\\u2014",
                                   "Polarity or first pin (file / preview)": "none" if part else "\\u2014",
                                   "Catalogue part (record / parts list)": "same" if part else "\\u2014",
                                   "File": "\\u2014" if part else item + ".gbr", "Compared with": "\\u2014" if part else "its view",
                                   "Verdict": verdict, "Why": why})
sys.stdout.write(ex.stream_text(session_id, text="done", structured={"tables": tables}, cost=0.03, api_ms=300, turns=1,
                                read=1000, write=200, generated=50, tools=report.get("tools", tools), model=model,
                                cwd=report.get("cwd", os.getcwd()), mcp_servers=report.get("mcp_servers", ())))
'''

LAYER_SET = set(pf.LAYERS)


def row(item, verdict=MATCHES, why="Agrees with the preview.", **cells):
    """A verdict row of the kind the item is: a part's four comparisons or a layer's file and what it was compared with."""
    if item in LAYER_SET:
        base = {**{column: "—" for column in caller.PART_COLUMNS}, "File": f"{item}.gbr", "Compared with": "its view"}
    else:
        base = {**{column: "same" for column in caller.PART_COLUMNS}, "File": "—", "Compared with": "—"}
    return {"Item": item, **base, **cells, "Verdict": verdict, "Why": why}


def finding(number, item, what="off its place at (3, 4)"):
    return {"Finding": number, "Item": item, "What and where": what}


def good_rows(unit, items):
    """Every item of a unit judged as a sound reviewer judges it: matches, and cannot judge for a part with no drawing."""
    if unit.startswith("nodrawing"):
        return [row(item, CANNOT, "needs a drawing of the footprint") for item in items]
    return [row(item) for item in items]


def prepared(folder):
    return kit_caller.load("production_files", TOOLS).prepare(folder)


def results(package):
    return {unit: {"Verdicts": good_rows(unit, held.items), "Findings": []} for unit, held in package.declaration.units.items()}


def slurp(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def merged(package, given, replicas=None):
    return package.merge(list(given), {unit: replicas.get(unit, {"r1": tables}) if replicas else {"r1": tables}
                                       for unit, tables in given.items()})


def rendered(package, given, replicas=None):
    return package.render(merge.plain_tables(merged(package, given, replicas)))[caller.RENDERED_NAME]


class Folder(unittest.TestCase):
    """A review folder the folder command wrote from a synthetic repository, in a temporary folder."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="production-files-caller-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.inputs = pf.make_inputs(self.root)
        self.folder = pf.write_folder(self.root, self.inputs)
        shutil.copytree(self.folder, self.root + "/pristine")

    def refused(self, call, *words):
        with self.assertRaises(merge.Refused) as caught:
            call()
        text = "; ".join(caught.exception.causes)
        for word in words:
            self.assertIn(word, text)
        return text

    def path(self, *names):
        return os.path.join(self.folder, *names)

    def pristine(self):
        """The folder as the folder command wrote it, put back after a case that damaged it."""
        if not os.path.isdir(self.root + "/pristine"):
            shutil.copytree(self.folder, self.root + "/pristine")
        shutil.rmtree(self.folder)
        shutil.copytree(self.root + "/pristine", self.folder)

    def edit(self, name, change):
        text = slurp(self.path(name))
        pf.fx.write(self.path(name), change(text))

    def units(self):
        return {unit: list(held.items) for unit, held in prepared(self.folder).declaration.units.items()}


class TheUnits(Folder):
    def test_the_parts_are_grouped_by_the_footprint_the_drawings_index_gives_each_designator(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C1: From synthetic placement and parts records the caller's units are groups of rows that share a footprint, none holding more than ten rows and every row in exactly one group, and one unit for the fabrication layers, the drill file and the outline. A folder whose placement file cannot be read is refused naming it. A part whose footprint has no drawing is in a unit of its own footprint name and its prompt says so. Out of scope: judging a row and the kit's mechanics.
        units = self.units()
        self.assertEqual(units["fp2-lib-c-0603"], ["C1", "C2"])
        self.assertEqual(units["fp3-lib-u-8"], ["U1"])
        self.assertEqual([item for unit, items in units.items() if unit.startswith("fp1-") for item in items], pf.RESISTORS)
        package = prepared(self.folder)
        for unit in units:
            if unit.startswith("fp"):
                named = {footprint for footprint in ("Lib:R_0603", "Lib:C_0603", "Lib:U_8") if footprint in package.unit_text(unit)}
                self.assertEqual(len(named), 1, f"{unit} holds the rows of one footprint")
        self.assertIn("footprint-Lib_C_0603.png", package.unit_text("fp2-lib-c-0603"))
        self.assertNotIn("footprint-Lib_R_0603.png", package.unit_text("fp2-lib-c-0603"))

    def test_no_unit_holds_more_than_ten_rows_and_every_row_is_in_exactly_one_group_in_placement_file_order(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C1: From synthetic placement and parts records the caller's units are groups of rows that share a footprint, none holding more than ten rows and every row in exactly one group, and one unit for the fabrication layers, the drill file and the outline. A folder whose placement file cannot be read is refused naming it. A part whose footprint has no drawing is in a unit of its own footprint name and its prompt says so. Out of scope: judging a row and the kit's mechanics.
        self.assertEqual(caller.PARTS_PER_UNIT, 10)
        for count in (1, 9, 10, 11, 20, 21, 35):
            with self.subTest(rows=count):
                names = [f"R{n}" for n in range(1, count + 1)] + ["C1"]
                folder = os.path.join(self.root, f"count-{count}")
                shutil.copytree(self.folder, folder)
                pf.fx.write(os.path.join(folder, "production", "placement.csv"), pf.placement_text(names))
                index = json.loads(slurp(os.path.join(folder, "production", "footprints", "index.json")))
                index["images"][0]["used_by"] = names[:-1]
                index["images"][1]["used_by"] = ["C1"]
                pf.fx.write(os.path.join(folder, "production", "footprints", "index.json"), json.dumps(index))
                units = {unit: list(held.items) for unit, held in prepared(folder).declaration.units.items()}
                parts = [unit for unit in units if unit != "layers"]
                self.assertTrue(all(len(units[unit]) <= 10 for unit in parts))
                self.assertEqual([item for unit in parts for item in units[unit]], names, "every row once, in the file's order")
                resistors = [unit for unit in parts if unit.startswith("fp1-")]
                self.assertEqual([len(units[unit]) for unit in resistors], [10] * (count // 10) + ([count % 10] if count % 10 else []))

    def test_the_fabrication_layers_the_drill_file_and_the_outline_are_one_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C1: From synthetic placement and parts records the caller's units are groups of rows that share a footprint, none holding more than ten rows and every row in exactly one group, and one unit for the fabrication layers, the drill file and the outline. A folder whose placement file cannot be read is refused naming it. A part whose footprint has no drawing is in a unit of its own footprint name and its prompt says so. Out of scope: judging a row and the kit's mechanics.
        units = self.units()
        self.assertEqual(units["layers"], pf.LAYERS)
        self.assertIn("drill", units["layers"])
        self.assertIn("Edge.Cuts", units["layers"])
        self.assertEqual(sum(unit == "layers" for unit in units), 1)
        self.assertEqual(list(units)[-1], "layers")
        package = prepared(self.folder)
        self.assertEqual(package.checklist, tuple(pf.PLACED + pf.LAYERS))
        text = package.unit_text("layers")
        for layer in pf.LAYERS:
            self.assertIn(f"production/layers/layer-{layer}.png", text)

    def test_a_part_whose_footprint_has_no_drawing_is_in_a_unit_of_its_own_footprint_name_and_its_prompt_says_so(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C1: From synthetic placement and parts records the caller's units are groups of rows that share a footprint, none holding more than ten rows and every row in exactly one group, and one unit for the fabrication layers, the drill file and the outline. A folder whose placement file cannot be read is refused naming it. A part whose footprint has no drawing is in a unit of its own footprint name and its prompt says so. Out of scope: judging a row and the kit's mechanics.
        units = self.units()
        self.assertEqual(units[NODRAW_UNIT], ["X1", "X2"], "grouped by the parts list's footprint name")
        self.assertEqual(units[BARE_UNIT], ["Y1"], "no-drawing when the parts list names none")
        package = prepared(self.folder)
        text = package.unit_text(NODRAW_UNIT)
        for words in ("Lib:Odd_1", "has no drawing in production/footprints/", "cannot judge", "blocks the order"):
            self.assertIn(words, text)
        self.assertIn("no-drawing", package.unit_text(BARE_UNIT))
        self.assertIn("has no drawing", package.unit_text(BARE_UNIT))
        self.assertNotIn("has no drawing", package.unit_text(PART_UNIT))
        other = os.path.join(self.root, "many")
        shutil.copytree(self.folder, other)
        names = [f"Z{n}" for n in range(1, 24)]
        pf.fx.write(os.path.join(other, "production", "placement.csv"), pf.placement_text(names))
        pf.fx.write(os.path.join(other, "production", "parts-list.csv"), "Comment,Designator,Footprint,LCSC\nz,\"" + ", ".join(names) + "\",Lib:Odd_9,C1\n")
        counts = [len(held.items) for unit, held in prepared(other).declaration.units.items() if unit.startswith("nodrawing")]
        self.assertEqual(counts, [10, 10, 3])

    def test_a_placement_file_that_cannot_be_read_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C1: From synthetic placement and parts records the caller's units are groups of rows that share a footprint, none holding more than ten rows and every row in exactly one group, and one unit for the fabrication layers, the drill file and the outline. A folder whose placement file cannot be read is refused naming it. A part whose footprint has no drawing is in a unit of its own footprint name and its prompt says so. Out of scope: judging a row and the kit's mechanics.
        name = "production/placement.csv"
        good = slurp(self.path(name))
        for what, change, word in (
                ("an empty file", lambda text: "", "has the columns none"),
                ("the wrong columns", lambda text: text.replace("Mid X", "X"), "has the columns Designator,X"),
                ("no part", lambda text: text.splitlines()[0] + "\n", "lists no part"),
                ("a short row", lambda text: text + "Q1,1,2\n", "has 3 columns, not 5"),
                ("no designator", lambda text: text + ",1,2,Top,0\n", "names no designator"),
                ("a part twice", lambda text: text + "r1,1,2,Top,0\n", "lists r1 twice"),
                ("not text", None, "cannot be read")):
            with self.subTest(what=what):
                if change is None:
                    with open(self.path(name), "wb") as handle:
                        handle.write(b"\xff\xfe\x00bad")
                else:
                    pf.fx.write(self.path(name), change(good))
                text = self.refused(lambda: prepared(self.folder), "placement file", name, word)
                self.assertIn("folder command", text)
        os.remove(self.path(name))
        self.refused(lambda: prepared(self.folder), "placement file", "cannot be read")

    def test_an_index_or_a_parts_list_that_cannot_be_used_is_refused_naming_what_is_wrong(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C1: From synthetic placement and parts records the caller's units are groups of rows that share a footprint, none holding more than ten rows and every row in exactly one group, and one unit for the fabrication layers, the drill file and the outline. A folder whose placement file cannot be read is refused naming it. A part whose footprint has no drawing is in a unit of its own footprint name and its prompt says so. Out of scope: judging a row and the kit's mechanics.
        footprints, layers, parts = "production/footprints/index.json", "production/layers/index.json", "production/parts-list.csv"
        good = {name: slurp(self.path(name)) for name in (footprints, layers, parts)}

        def index(name, change):
            held = json.loads(good[name])
            change(held)
            return json.dumps(held)
        cases = [
            (footprints, "{not json", "footprint drawings index"),
            (footprints, json.dumps({"images": "none"}), "lists no images"),
            (footprints, index(footprints, lambda held: held["images"].__setitem__(0, {"file": "x.png"})), "not a drawing with its file"),
            (footprints, index(footprints, lambda held: held["images"][0].__setitem__("file", "gone.png")), "gone.png"),
            (footprints, index(footprints, lambda held: held["images"][1]["used_by"].append("R1")), "R1 under two drawings"),
            (layers, index(layers, lambda held: held["images"].append(dict(held["images"][0]))), "layer F.Cu twice"),
            (layers, index(layers, lambda held: held["images"].__setitem__(slice(None), [i for i in held["images"] if i["layer"] != "drill"])),
             "no image of the drill file"),
            (layers, index(layers, lambda held: held["images"].__setitem__(slice(None), [i for i in held["images"] if i["layer"] != "Edge.Cuts"])),
             "no image of the outline"),
            (layers, index(layers, lambda held: held["images"][0].__setitem__("file", "gone.png")), "gone.png"),
            (layers, index(layers, lambda held: held["images"].__setitem__(0, {"layer": "F.Cu"})), "not an image with its file and layer"),
            (parts, "Comment,Designator\nx,R1\n", "lack Designator or Footprint"),
            (parts, "", "lack Designator or Footprint"),
        ]
        for name, text, word in cases:
            with self.subTest(name=name, word=word):
                self.pristine()
                pf.fx.write(self.path(name), text)
                self.refused(lambda: prepared(self.folder), word)
        self.pristine()
        self.assertTrue(prepared(self.folder).declaration.units)
        os.remove(self.path(parts))
        self.refused(lambda: prepared(self.folder), "parts list", "cannot be read")
        self.pristine()
        pf.fx.write(self.path("elsewhere", pf.RECORD), "x: 1\n")
        self.refused(lambda: prepared(self.folder), "2 files named parts-specification.yaml")
        os.remove(self.path("elsewhere", pf.RECORD))
        os.remove(self.path("hardware", "synth", "board", pf.RECORD))
        self.refused(lambda: prepared(self.folder), "0 files named parts-specification.yaml")

    def test_a_part_named_like_a_layer_or_a_folder_without_the_images_the_units_need_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C1: From synthetic placement and parts records the caller's units are groups of rows that share a footprint, none holding more than ten rows and every row in exactly one group, and one unit for the fabrication layers, the drill file and the outline. A folder whose placement file cannot be read is refused naming it. A part whose footprint has no drawing is in a unit of its own footprint name and its prompt says so. Out of scope: judging a row and the kit's mechanics.
        name = "production/placement.csv"
        pf.fx.write(self.path(name), slurp(self.path(name)) + "drill,1,2,Top,0\n")
        self.refused(lambda: prepared(self.folder), "drill", "also the name of a fabrication layer")
        for what, folder, keep, word in (("no preview image", "preview", None, "no preview image"),
                                         ("no layer view", "views", lambda held: not held.startswith("layer-"), "no layer view image"),
                                         ("no placement or assembly view", "placement", None, "no placement or assembly view image")):
            with self.subTest(what=what):
                self.pristine()
                for held in os.listdir(self.path(folder)):
                    if held.endswith(".png") and (keep is None or not keep(held)):
                        os.remove(self.path(folder, held))
                if folder == "placement":
                    for held in os.listdir(self.path("views")):
                        if held.startswith("assembly-"):
                            os.remove(self.path("views", held))
                self.refused(lambda: prepared(self.folder), word)
        self.pristine()
        self.assertTrue(prepared(self.folder).declaration.units)

    def test_a_folder_lacking_a_file_the_shared_context_holds_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C1: From synthetic placement and parts records the caller's units are groups of rows that share a footprint, none holding more than ten rows and every row in exactly one group, and one unit for the fabrication layers, the drill file and the outline. A folder whose placement file cannot be read is refused naming it. A part whose footprint has no drawing is in a unit of its own footprint name and its prompt says so. Out of scope: judging a row and the kit's mechanics.
        for name in ("production/placement.csv", "production/parts-list.csv", "round.json", "production/layers/index.txt",
                     "production/footprints/index.txt", "views/index.txt", "placement/index.txt"):
            with self.subTest(name=name):
                self.pristine()
                os.remove(self.path(name))
                self.refused(lambda: prepared(self.folder), name.split("/")[-1])
        self.pristine()
        self.assertTrue(prepared(self.folder).declaration.units)

    def test_each_units_prompt_names_its_rows_the_three_verdicts_and_where_the_drawings_and_images_lie(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        for unit, held in package.declaration.units.items():
            text = package.unit_text(unit)
            self.assertIn(f"Your unit: {unit}", text)
            for item in held.items:
                self.assertIn(f"\n- {item}\n", text + "\n")
            for verdict in ("`matches`", "`differs`", "`cannot judge`"):
                self.assertIn(verdict, text)
            for place in ("production/layers/", "production/footprints/", "views/", "placement/", "preview/", "index.txt"):
                self.assertIn(place, text)
            for column in caller.VERDICT_TABLE + caller.FINDING_TABLE:
                self.assertIn(column, text)
            self.assertIn("blocks the order", text)
        parts = package.unit_text(PART_UNIT)
        self.assertIn("production/footprints/footprint-Lib_C_0603.png", parts)
        self.assertIn("\n- C1, 34, -17, Top, 0\n", parts)
        for other in ("U1", "R1", "F.Cu"):
            self.assertNotIn(f"\n- {other}", parts)
        layers = package.unit_text("layers")
        self.assertIn("production/layers/layer-drill.png", layers)
        self.assertIn("missing content", layers)
        self.assertIn("shifted content", layers)
        self.assertIn("mirrored content", layers)

    def test_a_units_artefacts_are_its_own_drawing_the_preview_and_the_views_and_no_other_units_drawing(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        declaration = prepared(self.folder).declaration
        needs = {unit: set(held.needs) for unit, held in declaration.units.items()}
        self.assertIn("production/footprints/footprint-Lib_C_0603.png", needs[PART_UNIT])
        self.assertNotIn("production/footprints/footprint-Lib_R_0603.png", needs[PART_UNIT])
        self.assertNotIn("production/footprints/footprint-Lib_C_0603.png", needs[NODRAW_UNIT])
        for unit in needs:
            self.assertIn("production/placement.csv", needs[unit])
            self.assertIn("round.json", needs[unit])
        self.assertIn("preview/preview-top.png", needs[PART_UNIT])
        self.assertNotIn("preview/preview-top.png", needs["layers"])
        self.assertIn("views/layer-F.Cu-r1c1.png", needs["layers"])
        self.assertIn("production/layers/layer-drill.png", needs["layers"])
        self.assertEqual(set(declaration.artefacts), set().union(*needs.values()))


class TheMerge(Folder):
    @staticmethod
    def assess_rows(package, unit, rows):
        return kit_results.assess({"tables": {"Verdicts": rows, "Findings": []}}, "", package.declaration.shape, unit,
                                  list(package.declaration.units[unit].items))

    def test_the_check_merges_one_row_for_every_placement_row_and_every_layer_in_checklist_order(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        out = merged(package, results(package))
        rows = out["tables"]["Verdicts"]["rows"]
        self.assertEqual(sorted(row["Item"] for row in rows), sorted(pf.PLACED + pf.LAYERS))
        self.assertEqual(out["tables"]["Verdicts"]["columns"], caller.VERDICT_TABLE)
        order = package.render(merge.plain_tables(out))[caller.RENDERED_NAME]
        self.assertLess(order.index("| R1 "), order.index("| U1 "))
        self.assertLess(order.index("| U1 "), order.index("| F.Cu "))

    def test_a_placement_row_with_no_parts_row_or_two_and_a_layer_with_no_layers_row_fail_the_merge_naming_each(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        base = results(package)
        gone = {**base, PART_UNIT: {"Verdicts": [row("C1")], "Findings": []}}
        text = self.refused(lambda: merged(package, gone), "C2 is a placement-file row and has no verdict row")
        twice = {**base, TWO_UNIT: {"Verdicts": base[TWO_UNIT]["Verdicts"] + [row("C2")], "Findings": []}}
        text = self.refused(lambda: merged(package, twice), "C2 has 2 verdict rows")
        within = self.assess_rows(package, PART_UNIT, [row("C1"), row("C2"), row("C2")])
        self.assertIn("gives item 'C2' 2 verdicts", "; ".join(problem.line() for problem in within.problems), "one reviewer's two rows")
        for layer in ("F.Cu", "drill", "Edge.Cuts"):
            with self.subTest(layer=layer):
                held = [r for r in base["layers"]["Verdicts"] if r["Item"] != layer]
                self.refused(lambda: merged(package, {**base, "layers": {"Verdicts": held, "Findings": []}}),
                             f"{layer} is a fabrication layer, the drill file or the outline and has no verdict row")
        self.assertNotIn("C1 is", self.refused(lambda: merged(package, gone), "C2"), "only the missing row is named")

    def test_a_parts_row_for_a_part_not_in_the_file_and_a_layers_row_for_a_layer_not_rendered_fail_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        base = results(package)
        extra = {**base, PART_UNIT: {"Verdicts": base[PART_UNIT]["Verdicts"] + [row("Q9")], "Findings": []}}
        self.refused(lambda: merged(package, extra), "a verdict row for Q9", "no part of the placement file")
        extra = {**base, "layers": {"Verdicts": base["layers"]["Verdicts"] + [row("In9.Cu")], "Findings": []}}
        self.refused(lambda: merged(package, extra), "a verdict row for In9.Cu")

    def test_a_verdict_outside_the_three_is_rejected_and_the_three_are_accepted(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        self.assertEqual(sorted(caller.VERDICTS), sorted([MATCHES, DIFFERS, CANNOT]))
        for verdict in ("pass", "fail", "Matches", "match", "not applicable", ""):
            with self.subTest(verdict=verdict):
                bad = {**results(package), PART_UNIT: {"Verdicts": [row("C1", verdict), row("C2")], "Findings": []}}
                self.refused(lambda: merged(package, bad), "verdict", "outside")
        ok = {**results(package), PART_UNIT: {"Verdicts": [row("C1", CANNOT, "needs the preview"), row("C2")], "Findings": []}}
        self.assertEqual(len(merged(package, ok)["tables"]["Verdicts"]["rows"]), len(pf.PLACED + pf.LAYERS))

    def test_opening_fields_that_are_missing_or_malformed_are_refused_before_any_session_starts(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        good = pf.fx.round_file(self.folder)
        for change, word in (({"commit": None}, "the commit judged is None"), ({"commit": "not-hex"}, "the commit judged is 'not-hex'"),
                             ({"tools": None}, "the tools are None"), ({"tools": "a\nb"}, "the tools are"),
                             ({"tools": "```"}, "the tools are"), ({"commands": None}, "the commands are None"),
                             ({"commands": []}, "the commands are []"), ({"commands": ["ok", "two\nlines"]}, "the commands are"),
                             ({"commands": "kicad-cli"}, "the commands are"), ({"preview": None}, "the preview line is None"),
                             ({"preview": "  "}, "the preview line is"), ({"preview": 4}, "the preview line is 4")):
            with self.subTest(change=change):
                pf.fx.set_round(self.folder, **change)
                self.refused(lambda: prepared(self.folder), word, "round file")
                pf.fx.write(self.path("round.json"), json.dumps(good))
        self.assertTrue(prepared(self.folder).declaration.units)

    def test_a_round_file_that_is_another_reviews_or_carries_keys_the_mode_does_not_own_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        good = pf.fx.round_file(self.folder)
        for name, content, word in (
                ("a layout round", {**good, "fields": ["number", "kind", "commit", "views", "check"]}, "holds"),
                ("a critical-routing pass", {**good, "fields": ["number", "commit", "views"]}, "holds"),
                ("fields mixed with a layout field", {**good, "fields": ["commit", "tools", "commands", "preview", "kind"]}, "mixes"),
                ("fields mixed the other way", {**good, "fields": ["number", "commit", "tools"]}, "mixes"),
                ("a kind key", {**good, "kind": "full"}, "holds kind"),
                ("a check key", {**good, "check": ["DESIGN | x"]}, "holds check"),
                ("a bogus key", {**good, "bogus": 1}, "holds bogus"),
                ("several stray keys", {**good, "views": ["v"], "number": 1}, "holds number, views"),
                ("a foreign tool marker", {**good, "tool": "other"}, "not one the folder command wrote"),
                ("fields that are no list", {**good, "fields": "commit"}, "not one the folder command wrote"),
                ("an unknown field", {**good, "fields": ["commit", "tools", "commands", "preview", "colour"]}, "not one the folder")):
            with self.subTest(name=name):
                pf.fx.write(self.path("round.json"), json.dumps(content))
                self.refused(lambda: prepared(self.folder), word)
                self.refused(lambda: caller.declaration(self.folder), word)
                self.refused(lambda: kit_caller.load("production_files", TOOLS).prepare(self.folder), word)
        pf.fx.write(self.path("round.json"), "{not json")
        self.refused(lambda: prepared(self.folder), "round file", "cannot be read")
        os.remove(self.path("round.json"))
        self.refused(lambda: prepared(self.folder), "round file", "cannot be read")

    def test_a_layout_folder_is_refused_naming_the_fields_and_the_command_that_writes_the_right_one(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        layout = fx.write_review_folder(os.path.join(self.root, "layout"))
        text = self.refused(lambda: prepared(layout), "number, kind, commit, views, check", "not the production-files check's")
        self.assertIn("production-files folder command", text)

    def test_a_part_with_no_drawing_is_refused_any_verdict_but_cannot_judge_naming_the_part_and_footprint(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        for verdict in (MATCHES, DIFFERS):
            with self.subTest(verdict=verdict):
                rows = [row("X1", verdict, "finding 1" if verdict == DIFFERS else "Fine."), row("X2", CANNOT, "no drawing")]
                bad = {**results(package), NODRAW_UNIT: {"Verdicts": rows, "Findings": [finding(1, "X1")] if verdict == DIFFERS else []}}
                text = self.refused(lambda: merged(package, bad), "part X1", "Lib:Odd_1", "has no drawing", "only verdict is cannot judge")
                self.assertNotIn("part X2", text)
        text = self.refused(lambda: merged(package, {**results(package), BARE_UNIT: {"Verdicts": [row("Y1")], "Findings": []}}),
                            "part Y1", "no-drawing")
        rows = {r["Item"]: r["Verdict"] for r in merged(package, results(package))["tables"]["Verdicts"]["rows"]}
        self.assertEqual([rows[name] for name in pf.ODD + pf.BARE], [CANNOT] * 3)

    def test_a_row_without_its_cells_or_a_row_that_is_not_a_match_without_a_why_fails_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        for item, unit, column, word in (("C1", PART_UNIT, "Rotation (file / preview)", "part C1 leaves Rotation (file / preview) empty"),
                                          ("C2", PART_UNIT, "Catalogue part (record / parts list)", "part C2 leaves Catalogue part"),
                                          ("F.Cu", "layers", "File", "layer F.Cu leaves File empty"),
                                          ("drill", "layers", "Compared with", "layer drill leaves Compared with empty")):
            with self.subTest(item=item, column=column):
                held = results(package)
                held[unit]["Verdicts"] = [{**r, column: "  "} if r["Item"] == item else r for r in held[unit]["Verdicts"]]
                self.refused(lambda: merged(package, held), word)
        held = results(package)
        held[PART_UNIT]["Verdicts"] = [row("C1", CANNOT, " "), row("C2")]
        self.refused(lambda: merged(package, held), "item C1 is cannot judge with no Why")
        held[PART_UNIT] = {"Verdicts": [row("C1", DIFFERS, ""), row("C2")], "Findings": [finding(1, "C1")]}
        self.refused(lambda: merged(package, held), "item C1 is differs with no Why")
        held[PART_UNIT] = {"Verdicts": [row("C1", MATCHES, ""), row("C2")], "Findings": []}
        merged(package, held)

    def test_a_differs_needs_a_finding_a_finding_needs_a_row_that_is_not_a_match_and_a_cited_finding_is_the_rows_own(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        base = results(package)
        cases = [
            ("no finding", {"Verdicts": [row("C1", DIFFERS, "Rotated."), row("C2")], "Findings": []}, "item C1 differs and no finding names it"),
            ("a cited finding never raised", {"Verdicts": [row("C1", DIFFERS, "finding 1"), row("C2")], "Findings": []}, "cites a finding 1"),
            ("a finding of a match", {"Verdicts": [row("C1"), row("C2")], "Findings": [finding(1, "C1")]}, "names item C1, which matches"),
            ("a finding of no item", {"Verdicts": [row("C1"), row("C2")], "Findings": [finding(1, "ZZ")]}, "is no item"),
            ("an empty finding", {"Verdicts": [row("C1", DIFFERS, "finding 1"), row("C2")], "Findings": [finding(1, "C1", " ")]},
             "says nothing under What and where"),
            ("another row's finding", {"Verdicts": [row("C1", DIFFERS, "finding 2"), row("C2", DIFFERS, "finding 1")],
                                       "Findings": [finding(1, "C1"), finding(2, "C2")]}, "cites finding 2, which names item C2")]
        for name, tables, word in cases:
            with self.subTest(name=name):
                self.refused(lambda: merged(package, {**base, PART_UNIT: tables}), word)
        ok = {"Verdicts": [row("C1", CANNOT, "needs the preview"), row("C2", DIFFERS, "finding 1")],
              "Findings": [finding(1, "C2")]}
        merged(package, {**base, PART_UNIT: ok})
        also = {"Verdicts": [row("C1", CANNOT, "needs the preview"), row("C2")], "Findings": [finding(1, "C1", "the preview is not of this side")]}
        merged(package, {**base, PART_UNIT: also})

    def test_replicas_merge_with_any_row_that_is_not_a_match_standing_and_a_cannot_judge_over_a_difference(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        base = results(package)
        order = {MATCHES: 0, DIFFERS: 1, CANNOT: 2}
        for first in order:
            for second in order:
                for third in order:
                    given = [first, second, third]
                    expected = CANNOT if CANNOT in given else DIFFERS if DIFFERS in given else MATCHES
                    replicas = {}
                    for number, verdict in enumerate(given, 1):
                        why = {MATCHES: "Fine.", DIFFERS: "finding 1", CANNOT: "needs the preview"}[verdict]
                        tables = {"Verdicts": [row("C1", verdict, why), row("C2")],
                                  "Findings": [finding(1, "C1")] if verdict == DIFFERS else []}
                        replicas[f"r{number}"] = tables
                    out = merged(package, base, replicas={PART_UNIT: replicas})
                    chosen = next(r for r in out["tables"]["Verdicts"]["rows"] if r["Item"] == "C1")
                    self.assertEqual(chosen["Verdict"], expected, given)
        self.assertEqual(caller.VERDICTS[0], DIFFERS, "the kit takes the earliest verdict after a cannot judge, so a difference stands")

    def test_a_cannot_judge_stands_and_blocks_the_order_and_is_not_refused_or_resolved_in_the_check(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        held = {**results(package), PART_UNIT: {"Verdicts": [row("C1", CANNOT, "needs the assembler's preview of the bottom side"), row("C2")],
                                                 "Findings": []}}
        text = rendered(package, held)
        self.assertIn("Part `C1` is `cannot judge`: needs the assembler's preview of the bottom side", text)
        self.assertIn("It blocks the order", text)
        self.assertFalse(hasattr(caller, "ADDED"), "no add-view or add-document resolution")
        self.assertEqual(package.declaration.added_during_round, ())


class TheGuards(Folder):
    """A producer that omits, skips, duplicates or substitutes is refused on every path an answer takes: the first answer, a
    repair turn, the turn about its cannot judge rows, a re-run and the merge of replicas."""

    #: A defect another replica's answer for the same row hides in the merged check: the merged verdict, then the other's.
    MASKED_BY_A_REPLICA = {
        "matches for a part with no drawing": "another replica's cannot judge stands over it",
        "differs for a part with no drawing": "another replica's cannot judge stands over it",
        "leaves a cell empty": "another replica's complete row of the same verdict is the one merged",
        "gives no Why for a row that is not a match": "another replica's row of the same verdict, with its Why, is the one merged",
    }

    @staticmethod
    def defects():
        """Each defect: the unit kinds it applies to and a function from a good answer, the unit's items and the items of
        another unit to the bad answer."""
        def swap(tables, rows):
            return {**tables, "Verdicts": rows}
        every = ("parts", "nodrawing", "layers")
        parts_and_layers = ("parts", "layers")
        return {
            "omits an item": (every, lambda t, items, other: swap(t, t["Verdicts"][:-1])),
            "gives an item twice": (every, lambda t, items, other: swap(t, t["Verdicts"] + [dict(t["Verdicts"][0])])),
            "substitutes another unit's item": (every, lambda t, items, other: swap(t, t["Verdicts"][:-1] + [row(other, **{})])),
            "gives a row for an item off the checklist": (every, lambda t, items, other: swap(t, t["Verdicts"] + [row("ZZ9")])),
            "gives a verdict outside the three": (every, lambda t, items, other: swap(t, [row(items[0], "pass")] + t["Verdicts"][1:])),
            "differs with no finding": (parts_and_layers, lambda t, items, other: swap(
                t, [row(items[0], DIFFERS, "finding 1")] + t["Verdicts"][1:])),
            "raises a finding for a row that matches": (parts_and_layers, lambda t, items, other: {**t, "Findings": [finding(1, items[0])]}),
            "cites another row's finding": (parts_and_layers, lambda t, items, other: {
                "Verdicts": [row(items[0], DIFFERS, "finding 2")] + [row(items[1], DIFFERS, "finding 1")] + t["Verdicts"][2:],
                "Findings": [finding(1, items[0]), finding(2, items[1])]} if len(items) > 1 else
                {"Verdicts": [row(items[0], DIFFERS, "finding 9")], "Findings": []}),
            "raises an empty finding": (parts_and_layers, lambda t, items, other: {
                "Verdicts": [row(items[0], DIFFERS, "finding 1")] + t["Verdicts"][1:], "Findings": [finding(1, items[0], "")]}),
            "matches for a part with no drawing": (("nodrawing",), lambda t, items, other: swap(
                t, [row(items[0], MATCHES)] + t["Verdicts"][1:])),
            "differs for a part with no drawing": (("nodrawing",), lambda t, items, other: {
                "Verdicts": [row(items[0], DIFFERS, "finding 1")] + t["Verdicts"][1:], "Findings": [finding(1, items[0])]}),
            "leaves a cell empty": (parts_and_layers, lambda t, items, other: swap(
                t, [{**t["Verdicts"][0], ("File" if items[0] in LAYER_SET else "Rotation (file / preview)"): ""}] + t["Verdicts"][1:])),
            "gives no Why for a row that is not a match": (("nodrawing",), lambda t, items, other: swap(
                t, [row(items[0], CANNOT, "")] + t["Verdicts"][1:])),
        }

    UNITS = {"parts": (PART_UNIT, "U1"), "nodrawing": (NODRAW_UNIT, "R1"), "layers": ("layers", "R1")}

    def assess(self, package, unit, tables):
        return kit_results.assess({"tables": tables}, "", package.declaration.shape, unit, list(package.declaration.units[unit].items))

    def causes(self, package, unit, attempt, replicas=False):
        """Why the run is refused for the answer that stands: the problems the kit holds against the attempt, which fail its unit
        when it still stands, and the causes the merge refuses the check for."""
        found = [problem.line() for problem in attempt.problems]
        if attempt.tables is not None:
            units = {name: {"r1": tables} for name, tables in results(package).items()}
            units[unit] = {"r1": results(package)[unit], "r2": attempt.tables} if replicas else {"r1": attempt.tables}
            try:
                package.merge([unit] + [name for name in results(package) if name != unit], units)
            except merge.Refused as error:
                found += error.causes
        return found

    def test_every_defect_is_refused_on_the_first_answer_a_repair_the_cannot_judge_turn_a_rerun_and_the_replica_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        covered = set()
        for name, (kinds, make) in self.defects().items():
            for kind in kinds:
                unit, other = self.UNITS[kind]
                items = list(package.declaration.units[unit].items)
                bad = make(results(package)[unit], items, other)
                with self.subTest(defect=name, unit=unit):
                    covered.add(name)
                    first = self.assess(package, unit, bad)
                    self.assertTrue(self.causes(package, unit, first), f"first answer: {name}")
                    record = kit_results.UnitRecord(unit)
                    record.add(self.assess(package, unit, bad))
                    record.add(self.assess(package, unit, bad))
                    self.assertTrue(self.causes(package, unit, record.standing), f"repair turn: {name}")
                    turn = kit_results.UnitRecord(unit)
                    asked = results(package)[unit]
                    asked = {**asked, "Verdicts": [row(items[0], CANNOT, "needs the preview")] + asked["Verdicts"][1:]}
                    held = self.assess(package, unit, asked)
                    held.judge_asked = True
                    turn.add(held)
                    turn.add(self.assess(package, unit, bad))
                    self.assertTrue(turn.standing is held or self.causes(package, unit, turn.standing),
                                    f"cannot judge turn: {name}: a defective answer never stands in place of the sound one asked about")
                    if turn.standing is held:
                        self.assertTrue(turn.attempts[1].problems, f"cannot judge turn: {name}: it stands only over a defective answer")
                    again = prepared(self.folder)
                    self.assertTrue(self.causes(again, unit, self.assess(again, unit, bad)), f"rerun: {name}")
                    if name not in self.MASKED_BY_A_REPLICA:
                        self.assertTrue(self.causes(package, unit, self.assess(package, unit, bad), replicas=True),
                                        f"replica merge: {name}")
        self.assertEqual(covered, set(self.defects()), "every defect was applied to some unit")

    def test_a_defect_another_replicas_row_hides_leaves_that_replicas_row_in_the_check(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        for name, why in self.MASKED_BY_A_REPLICA.items():
            kinds, make = self.defects()[name]
            unit, other = self.UNITS[kinds[0]]
            items = list(package.declaration.units[unit].items)
            bad = make(results(package)[unit], items, other)
            with self.subTest(defect=name):
                self.assertEqual(self.causes(package, unit, self.assess(package, unit, bad), replicas=True), [], why)
                units = {u: {"r1": t} for u, t in results(package).items()}
                units[unit] = {"r1": results(package)[unit], "r2": bad}
                rows = package.merge(list(units), units)["tables"]["Verdicts"]["rows"]
                chosen = next(r for r in rows if r["Item"] == items[0])
                self.assertEqual(chosen, results(package)[unit]["Verdicts"][0], why)

    def test_a_pass_whose_every_answer_is_good_is_refused_on_none_of_those_paths(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        for unit in results(package):
            good = self.assess(package, unit, results(package)[unit])
            self.assertEqual(self.causes(package, unit, good), [], unit)
            self.assertEqual(self.causes(package, unit, good, replicas=True), [], unit)

    def test_the_rendered_file_name_is_held_to_an_allow_list_of_the_one_record_name(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        self.assertTrue(caller.RENDERED.fullmatch("production-files-check.md"))
        for name in ("production-files-check.MD", "production-files-check.md.", "../production-files-check.md", "production-files-check.md/",
                     "production-files-check.txt", "production-files-check-2.md", "record.json", "plan.json", "CON.md",
                     "production-files-check.md\n", "Production-files-check.md", " production-files-check.md"):
            self.assertIsNone(caller.RENDERED.fullmatch(name), name)
        package = prepared(self.folder)
        files = package.render(merge.plain_tables(merged(package, results(package))))
        self.assertEqual(list(files), ["production-files-check.md"])
        for name in files:
            self.assertTrue(kit_caller.rendered_name_ok(name))
            self.assertTrue(caller.RENDERED.fullmatch(name))

    def test_the_checks_and_the_render_refuse_to_run_before_the_declaration_was_resolved(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        caller.ROUND.clear()
        self.assertIn("before its declaration was resolved", "; ".join(caller.checks({"Verdicts": {"rows": []}, "Findings": {"rows": []}})))
        self.refused(lambda: caller.render(self.folder, {"Verdicts": {"rows": []}, "Findings": {"rows": []}}), "before its declaration")


class TheRecord(Folder):
    def render(self, held=None, folder=None):
        package = prepared(folder or self.folder)
        return rendered(package, held if held is not None else results(package))

    def test_the_record_has_the_opening_lines_from_the_round_file_and_the_parts_and_layers_tables_in_the_methods_form(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        text = self.render()
        round_ = pf.fx.round_file(self.folder)
        self.assertTrue(text.startswith(f"- **Board judged**: {round_['commit']}\n- **Tools**: {pf.TOOLS_LINE}\n- **Commands**:\n"))
        for command_line in pf.COMMANDS:
            self.assertIn(command_line, text)
        self.assertIn(f"- **Preview**: {pf.PREVIEW_NOTE}", text)
        method = slurp(os.path.join(REPO, "docs", "board-design-method.md"))
        for header in ("| Part | Position (file / preview) | Rotation (file / preview) | Polarity or first pin (file / preview) | Catalogue part (record / parts list) | Verdict | Why |",
                       "| Layer | File | Compared with | Verdict | Why |"):
            self.assertIn(header, method, "the form the ordering step gives")
            self.assertIn(header, text)
        self.assertIn("### Parts", text)
        self.assertIn("### Layers", text)
        self.assertIn("### Findings", text)
        parts = text.split("### Parts")[1].split("### Layers")[0]
        layers = text.split("### Layers")[1].split("### Findings")[0]
        self.assertEqual(len(re.findall(r"^\| (?:R|C|U|X|Y)\d+ ", parts, re.M)), len(pf.PLACED), "a row for every placed part")
        self.assertEqual(len(re.findall(r"^\| (?:[FB]\.|Edge|drill)", layers, re.M)), len(pf.LAYERS))
        self.assertNotIn("| F.Cu ", parts)
        self.assertNotIn("| R1 ", layers)

    def test_every_row_that_is_not_a_match_is_named_with_what_it_blocks_and_a_record_of_matches_names_none(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        held = results(package)
        held[PART_UNIT] = {"Verdicts": [row("C1", DIFFERS, "finding 1"), row("C2", CANNOT, "needs the preview of the bottom side")],
                           "Findings": [finding(1, "C1", "rotated 90 degrees from the design's")]}
        held["layers"] = {"Verdicts": [row("F.Cu", DIFFERS, "finding 1") if r["Item"] == "F.Cu" else r for r in held["layers"]["Verdicts"]],
                          "Findings": [finding(1, "F.Cu", "mirrored at (10, 20)")]}
        text = rendered(package, held)
        blocking = text.split("### Blocking the order")[1]
        for line in ("Part `C1` is `differs`: rotated 90 degrees from the design's", "Part `C2` is `cannot judge`: needs the preview of the bottom side",
                     "Layer `F.Cu` is `differs`: mirrored at (10, 20)", "Part `X1` is `cannot judge`", "Part `X2` is `cannot judge`",
                     "Part `Y1` is `cannot judge`"):
            self.assertIn(line, blocking)
        self.assertEqual(blocking.count("It blocks the order until the design is corrected and the files are exported again."), 6)
        self.assertNotIn("`R1`", blocking)
        self.assertNotIn("Nothing blocks the order", blocking)
        self.assertIn("rotated 90 degrees from the design's", text.split("### Parts")[1].split("### Layers")[0], "the finding is in the row's Why")
        self.assertIn("| 1 | C1 | rotated 90 degrees from the design's | open: blocks the order |", text)
        clean = os.path.join(self.root, "clean")
        pf.fx.write(os.path.join(clean, "x"), "")
        folder = os.path.join(self.root, "clean-folder")
        names = [name for name in pf.PLACED if name not in pf.ODD + pf.BARE]
        inputs = pf.make_inputs(os.path.join(self.root, "clean-inputs"))
        pf.fx.write(os.path.join(inputs["work"], "placement.csv"), pf.placement_text(names))
        folder = pf.write_folder(os.path.join(self.root, "clean-inputs"), inputs)
        package = prepared(folder)
        self.assertIn("- Nothing blocks the order: every part of the placement file and every layer, the drill file and the outline matches.",
                      rendered(package, results(package)))

    def test_a_cell_with_a_bar_or_a_line_break_is_escaped_so_the_tables_keep_their_shape(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        held = results(package)
        held[PART_UNIT] = {"Verdicts": [row("C1", CANNOT, "needs a | bar\nand a line"), row("C2")], "Findings": []}
        text = rendered(package, held)
        line = next(line for line in text.splitlines() if line.startswith("| C1 "))
        self.assertEqual(line.count("|"), len(caller.PARTS_TABLE) + 1 + line.count("&#124;") * 0)
        self.assertNotIn("a | bar", text.split("### Blocking")[0])

    def test_the_findings_are_numbered_in_the_checklist_order_across_units_and_citations_follow_the_renumbering(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        package = prepared(self.folder)
        held = results(package)
        held["layers"] = {"Verdicts": [row("B.Cu", DIFFERS, "finding 1") if r["Item"] == "B.Cu" else r for r in held["layers"]["Verdicts"]],
                          "Findings": [finding(1, "B.Cu", "shifted")]}
        held[PART_UNIT] = {"Verdicts": [row("C1", DIFFERS, "finding 1"), row("C2")], "Findings": [finding(1, "C1", "reversed")]}
        text = rendered(package, held)
        findings = text.split("### Findings")[1].split("### Blocking")[0]
        self.assertLess(findings.index("C1"), findings.index("B.Cu"))
        self.assertIn("| 1 | C1 | reversed |", findings)
        self.assertIn("| 2 | B.Cu | shifted |", findings)


class Command:
    """The kit's command run on a review folder with the production-files caller, the stub playing the agent command line."""

    def __init__(self, case: Folder, folder: str = None, out: str = "out"):
        self.case, self.folder = case, folder or case.folder
        self.out = os.path.join(case.root, out)
        self.log = os.path.join(case.root, "agent.log")
        self.scenario_path = os.path.join(case.root, "scenario.json")
        self.program = os.path.join(case.root, "agent")
        pf.fx.write(self.program, STUB.replace("PYTHON", sys.executable, 1).replace("TOOLS", repr(TOOLS)))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        patcher = mock.patch.dict(os.environ, {ex.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path, "STUB_LOG": self.log})
        patcher.start()
        case.addCleanup(patcher.stop)

    def scenario(self, **values):
        pf.fx.write(self.scenario_path, json.dumps({"layers": pf.LAYERS, **values}))

    def go(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        status = command.main(["--caller", "production_files", "--callers", TOOLS, "--review", self.folder, "--out", self.out]
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
    def test_the_command_writes_the_record_as_text_and_as_json_blocking_on_every_row_that_is_not_a_match(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        run = Command(self)
        run.scenario(verdicts={"C1": "differs", "F.Cu": "differs"}, why={"C2": "x"})
        status, text, err = run.go("--format", "json", "--model", MID)
        self.assertEqual(status, 0, text + err)
        report = json.loads(text)
        self.assertEqual(report["rendered"], ["production-files-check.md"])
        written = slurp(os.path.join(run.out, "production-files-check.md"))
        self.assertTrue(written.startswith("- **Board judged**: "))
        verdicts = {row_["Item"]: row_["Verdict"] for row_ in report["tables"]["Verdicts"]["rows"]}
        self.assertEqual([verdicts[name] for name in ("C1", "F.Cu", "C2", "X1")], [DIFFERS, DIFFERS, MATCHES, CANNOT])
        self.assertEqual(sorted(verdicts), sorted(pf.PLACED + pf.LAYERS))
        self.assertIn("Part `C1` is `differs`: off its place at (1, 1)", written)
        self.assertIn("Layer `F.Cu` is `differs`", written)
        self.assertIn("Part `X1` is `cannot judge`", written)
        second = Command(self)
        second.out = os.path.join(self.root, "out-text")
        status, text, err = second.go("--model", MID)
        self.assertEqual(status, 0, text + err)
        self.assertIn("RENDERED | production-files-check.md", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | WRITTEN"))

    def test_a_round_file_with_a_missing_field_a_stray_key_or_another_reviews_is_refused_before_any_session_starts(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        for change in ({"commit": None, "preview": None}, {"bogus": 1}, {"kind": "full"}, {"fields": ["number", "commit", "views"]}):
            with self.subTest(change=change):
                folder = os.path.join(self.root, "broken")
                shutil.rmtree(folder, ignore_errors=True)
                shutil.copytree(self.folder, folder)
                pf.fx.set_round(folder, **change)
                run = Command(self, folder=folder, out="out-broken")
                run.scenario()
                status, text, _ = run.go("--format", "json")
                report = json.loads(text)
                self.assertEqual(status, 1, text)
                self.assertTrue(report["refusals"])
                self.assertEqual(run.calls(), [], "no session was started")
                self.assertFalse(os.path.exists(run.out))

    def test_a_merge_that_fails_names_the_row_and_keeps_the_units_results(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        run = Command(self)
        run.scenario(verdicts={"X1": "matches"})
        status, text, _ = run.go("--format", "json", "--model", MID)
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        joined = "; ".join(report["refusals"])
        self.assertIn("part X1", joined)
        self.assertIn("Lib:Odd_1", joined)
        self.assertFalse(os.path.exists(os.path.join(run.out, "production-files-check.md")), "nothing is rendered from a refused merge")
        self.assertTrue(os.path.exists(os.path.join(run.out, "record.json")), "the units' results are kept")

    def test_a_cannot_judge_does_not_fail_the_merge_and_no_second_run_is_asked_for(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C2: Over a synthetic placement file and synthetic unit results, the merge fails naming a placement row with no parts row or with two, a parts row for a part not in the file, and a fabrication layer, the drill file or the outline with no layers row. It rejects a verdict outside the three the ordering step allows, refuses, before any session starts, opening fields that are missing or malformed, refuses a verdict other than cannot judge for a part whose footprint has no drawing, writes the check record in the form the ordering step gives, and reports every row that is not a match as blocking the order. Over the same inputs each unit's prompt names the unit's rows, the three verdicts and where the drawings and images lie in the review folder, so a reviewer on the small tier needs only the folder and the prompt, and the record names every row that is not a match with what it blocks. Out of scope: whether a verdict is right.
        run = Command(self)
        run.scenario(verdicts={"C1": "cannot judge"}, why={"C1": "needs the preview of the bottom side"})
        status, text, err = run.go("--format", "json", "--model", MID)
        self.assertEqual(status, 0, text + err)
        self.assertIn("needs the preview of the bottom side", slurp(os.path.join(run.out, "production-files-check.md")))
        self.assertNotIn("--rerun", text)


class TheToolGrant(Folder):
    def test_the_caller_grants_the_read_tools_only_and_no_retrieval_tool(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C6: Over synthetic declarations and a stub executor, the production-files declaration grants a reviewer the read tools only and no retrieval tool; sets three replicas, the full and hunt framings on the mid-tier model and the third on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        package = prepared(self.folder)
        self.assertEqual(package.tools, ("Read", "Glob", "Grep"))
        self.assertFalse(hasattr(caller, "retrieval"), "no retrieval attribute: the read tools alone")
        spec = messages.make_spec(package.declaration, package.tools, self.folder, MID)
        self.assertEqual(spec.expected_tools, sorted(["Read", "Glob", "Grep", "StructuredOutput"]))
        loaded = kit_caller.load("production_files", TOOLS)
        self.assertEqual(kit_caller.attribute_problems(loaded), [])
        self.assertEqual(kit_caller.granted_tools(loaded), ("Read", "Glob", "Grep"))
        for tool in ("WebFetch", "Bash", "Write", "Edit", "Task", "NotebookEdit"):
            self.assertNotIn(tool, package.tools)

    def test_every_reviewer_is_started_with_the_three_read_tools_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C6: Over synthetic declarations and a stub executor, the production-files declaration grants a reviewer the read tools only and no retrieval tool; sets three replicas, the full and hunt framings on the mid-tier model and the third on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        run = Command(self)
        run.scenario()
        status, text, err = run.go("--format", "json", "--model", MID)
        self.assertEqual(status, 0, text + err)
        calls = run.calls()
        self.assertTrue([call for call in calls if call["resume"] is not None])
        self.assertEqual({call["tools"] for call in calls}, {GRANT}, "the shared contexts and every reviewer")
        for call in calls:
            for tool in ("WebFetch", "Bash", "Write", "Edit", "Task"):
                self.assertNotIn(tool, call["tools"].split(","))
            self.assertEqual(os.path.realpath(call["cwd"]), os.path.realpath(self.folder), "in the review folder")

    def reviewer_refused(self, **scenario):
        """The command run with forks whose start reports deviate: refused, every reviewer's failure named with its units."""
        self.runs = getattr(self, "runs", 0) + 1
        sound = Command(self, out=f"sound-{self.runs}")
        sound.scenario()
        status, text, _ = sound.go("--format", "json", "--model", MID)
        forks = json.loads(text)["plan"]["forks"]
        run = Command(self, out=f"out-{self.runs}")
        run.scenario(**scenario)
        status, text, _ = run.go("--format", "json", "--model", MID)
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        self.assertEqual(report["result"], "REFUSED")
        self.assertIsNone(json.loads(slurp(os.path.join(run.out, "record.json")))["merged"])
        lines = report["refusals"]
        for line in lines:
            self.assertRegex(line, r"unit .+ \(group G\d+, replica \d+\) failed")
            self.assertRegex(line, r"session G\d\.r\d\.a1 started")
        self.assertEqual(len(lines), forks, "every reviewer that started badly is named with the units it was to judge")
        return lines[0]

    def test_a_session_that_reports_a_different_tool_set_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C6: Over synthetic declarations and a stub executor, the production-files declaration grants a reviewer the read tools only and no retrieval tool; sets three replicas, the full and hunt framings on the mid-tier model and the third on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "WebFetch", "StructuredOutput"])
        self.assertIn("started with tools", line)
        self.assertIn("WebFetch", line, "the retrieval tool is not granted, so a reviewer holding it is refused")
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "Bash", "StructuredOutput"])
        self.assertIn("Bash", line)
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "StructuredOutput"])
        self.assertIn("Grep", line, "a reviewer that lost a read tool is refused too")
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "Write", "Edit", "StructuredOutput"])
        self.assertIn("Write", line)

    def test_a_session_that_reports_an_mcp_server_or_another_working_directory_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C6: Over synthetic declarations and a stub executor, the production-files declaration grants a reviewer the read tools only and no retrieval tool; sets three replicas, the full and hunt framings on the mid-tier model and the third on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        line = self.reviewer_refused(fork_mcp=True)
        self.assertIn("MCP servers", line)
        line = self.reviewer_refused(fork_cwd=os.path.join(self.root, "elsewhere"))
        self.assertIn("started in", line)
        self.assertIn(self.folder, line, "the folder its specification names")


class TheReplicasBudgetAndBound(Folder):
    def test_the_declaration_sets_three_replicas_a_full_and_a_hunt_framing_on_the_mid_tier_model_and_the_third_on_the_small_tier(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C6: Over synthetic declarations and a stub executor, the production-files declaration grants a reviewer the read tools only and no retrieval tool; sets three replicas, the full and hunt framings on the mid-tier model and the third on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        loaded = kit_caller.load("production_files", TOOLS)
        policy = ensemble.parse_policy(loaded.module.replica_policy)
        self.assertEqual(policy.ids, ["full", "hunt", "small"])
        self.assertEqual([variant.model for variant in policy.variants], [MID, MID, SMALL])
        self.assertEqual((caller.MID_MODEL, caller.SMALL_MODEL), (MID, SMALL))
        self.assertEqual(review_caller_layout.SMALL_MODEL, caller.SMALL_MODEL, "the layout caller's small tier")
        full, hunt, small = policy.variants
        self.assertEqual((full.item_order, full.view_order, full.terse), ("given", "given", False))
        self.assertEqual((hunt.item_order, hunt.view_order, hunt.terse), ("reversed", "reversed", True))
        self.assertEqual((small.item_order, small.view_order, small.terse), ("given", "given", False))
        self.assertEqual(dict(policy.by_stakes)["high"], 3)
        package = prepared(self.folder)
        self.assertEqual({unit.stakes for unit in package.declaration.units.values()}, {"high"}, "the last check before payment")
        counts = ensemble.replicas_by_unit(package.declaration, policy)
        self.assertEqual(set(counts.values()), {3})
        self.assertEqual(set(counts), set(package.declaration.units))

    def test_the_time_budget_is_350_seconds_and_the_bound_30(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C6: Over synthetic declarations and a stub executor, the production-files declaration grants a reviewer the read tools only and no retrieval tool; sets three replicas, the full and hunt framings on the mid-tier model and the third on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        self.assertEqual(caller.WALL_SECONDS, 350)
        self.assertEqual(prepared(self.folder).declaration.budget.wall_s, 350)
        self.assertEqual(caller.bound, 30)
        self.assertEqual(review_caller_layout.bound, caller.bound)
        loaded = kit_caller.load("production_files", TOOLS)
        self.assertEqual(loaded.module.bound, 30)
        self.assertEqual(kit_caller.attribute_problems(loaded), [])

    def test_the_run_plans_three_replicas_of_each_group_two_shared_contexts_and_the_small_model_for_the_third(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C6: Over synthetic declarations and a stub executor, the production-files declaration grants a reviewer the read tools only and no retrieval tool; sets three replicas, the full and hunt framings on the mid-tier model and the third on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        run = Command(self)
        run.scenario()
        status, text, err = run.go("--format", "json", "--model", MID)
        self.assertEqual(status, 0, text + err)
        plan = json.loads(text)["plan"]
        self.assertEqual(plan["variants"], ["full", "hunt", "small"])
        self.assertEqual([(context["model"], context["variants"]) for context in plan["contexts"]], [(SMALL, ["small"])])
        calls = run.calls()
        forks = [call for call in calls if call["resume"] is not None and "Your unit:" in call["prompt"]]
        self.assertEqual(len(forks), plan["forks"])
        self.assertEqual(len(forks) % 3, 0)
        self.assertEqual({model_of(call) for call in forks}, {MID, SMALL})
        self.assertEqual(sum(model_of(call) == SMALL for call in forks) * 3, len(forks))
        prompts = [call["prompt"] for call in forks]
        self.assertEqual(sum(prompt.startswith("Hunt for failures.") for prompt in prompts) * 3, len(prompts))
        hunt = next(prompt for prompt in prompts if prompt.startswith("Hunt for failures.") and "- C2\n" in prompt)
        self.assertLess(hunt.index("- C2\n"), hunt.index("- C1\n"), "the hunt takes the items the other way round")

    def test_a_plan_of_forty_forks_runs_at_most_thirty_at_once_and_a_smaller_plan_all_of_its_forks(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C6: Over synthetic declarations and a stub executor, the production-files declaration grants a reviewer the read tools only and no retrieval tool; sets three replicas, the full and hunt framings on the mid-tier model and the third on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
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
            status, text, err = run.go("--format", "json", "--replicas", "40", "--model", MID)
        self.assertEqual(status, 0, text + err)
        plan = json.loads(text)["plan"]
        self.assertGreaterEqual(plan["forks"], 40)
        self.assertEqual(plan["bound"], 30)
        self.assertEqual(state["bounds"][-1], 30)
        self.assertLessEqual(state["peak"], 30)
        self.assertGreater(state["peak"], 1)
        small = Command(self, out="out-small")
        small.scenario()
        status, text, err = small.go("--format", "json", "--model", MID)
        self.assertEqual(status, 0, text + err)
        plan = json.loads(text)["plan"]
        self.assertLessEqual(plan["bound"], 30)
        self.assertEqual(plan["bound"], min(30, plan["forks"]))


class Documentation(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def ordering(self):
        method = self.read("docs", "board-design-method.md")
        found = re.search(r"^## Ordering[ \t]*\n(.*?)(?=^## |\Z)", method, re.M | re.S)
        return self.flat(found.group(1))

    def test_the_ordering_section_says_the_check_may_be_judged_by_unit_what_the_merge_checks_and_where_the_preview_step_stays(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C4: The method's ordering section says that the production-files check may be judged by unit, what the merge checks, that the assembler's preview is obtained outside the reviewers, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes' description of the production-files proof names the fanned-out run. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout, routing and schematic sections.
        section = self.ordering()
        for words in ("This check may be judged by unit instead of by one reviewer", "a way of carrying out steps 4 and 5, and it changes none of them",
                      "one reviewer for each group of at most ten placed parts that share a footprint drawing",
                      "one for every fabrication layer, the drill file and the outline",
                      "A placed part whose footprint has no drawing is judged by a reviewer of its own, which gives it `cannot judge`",
                      "and the merge refuses any other verdict for it", "task hw:review-run -- --caller production_files",
                      "with no model, into one production-files check record in which every row of the placement file has one row in the parts table",
                      "every fabrication layer, the drill file and the outline has one row in the layers table",
                      "come from whoever runs the check", "since the merge has no model to write them", "task hw:production-review-folder",
                      "The merge refuses a folder whose fields are missing or malformed before any reviewer starts",
                      "in which a placement-file row has no parts row or has two", "in which a row is for a part or a layer the check does not judge",
                      "in which a part with no drawing has a verdict other than `cannot judge`",
                      "in which a row lacks the cells its kind of row has or is not `matches` and says nothing",
                      "in which a `differs` has no finding or a finding is of a row that matches",
                      "every row that is not `matches` named and said to block the order",
                      "A `cannot judge` is not resolved within the check: it stands and blocks the order",
                      "The step that obtains the assembler's preview, step 3, stays outside every reviewer",
                      "the review folder holds the preview as it was saved",
                      "Judging the check with one reviewer, a person or an agent session that does not use the command, stays valid"):
            self.assertIn(words, section, f"the ordering section says {words!r}")

    def test_the_method_says_the_fanned_out_form_is_relied_on_only_once_its_proof_is_recorded(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C4: The method's ordering section says that the production-files check may be judged by unit, what the merge checks, that the assembler's preview is obtained outside the reviewers, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes' description of the production-files proof names the fanned-out run. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout, routing and schematic sections.
        self.assertIn("The fanned-out form is relied on only once its proof is recorded, and until then this step is carried out with one reviewer.",
                      self.ordering())

    def test_the_sentence_that_a_proof_is_repeated_names_the_form_that_changed(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C4: The method's ordering section says that the production-files check may be judged by unit, what the merge checks, that the assembler's preview is obtained outside the reviewers, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes' description of the production-files proof names the fanned-out run. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout, routing and schematic sections.
        section = self.ordering()
        sentence = section[section.index("Repeat the proof after changing this step"):]
        for words in ("in the form that changed", "a change to the step as one reviewer follows it repeats the single-reviewer form",
                      "a change to how the check is judged by unit, to the production-files caller or to the review folder it reads repeats the fanned-out form",
                      "each form's recorded proof standing for that form alone"):
            self.assertIn(words, sentence)
        self.assertNotIn("Repeat the proof after changing this step.", section)

    def test_the_hardware_notes_describe_the_caller_the_folder_command_and_the_fanned_out_proof_run(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C4: The method's ordering section says that the production-files check may be judged by unit, what the merge checks, that the assembler's preview is obtained outside the reviewers, and that judging it with one reviewer stays valid; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes' description of the production-files proof names the fanned-out run. Checked by reading each place against these clauses. The method also states that the fanned-out form is relied on only once its proof is recorded. Out of scope: the layout, routing and schematic sections.
        notes = self.read("hardware", "README.md")
        section = self.flat(notes[notes.index("## The production-files check by unit"):].split("\n## ")[0])
        for words in ("production_review_folder.py", "review_caller_production_files.py", "`task hw:production-review-folder", "`--caller production_files`",
                      "The assembler's preview, step 3, is obtained outside every reviewer", "Judging the check with one reviewer stays valid",
                      "the fanned-out form is relied on only once its proof is recorded", "at most ten rows a unit", "`layers`", "`no-drawing`",
                      "`matches`, `differs` and `cannot judge`", "`Read`, `Glob` and `Grep` and no retrieval tool", "`claude-sonnet-5-5`",
                      "`claude-haiku-5-5`", "350 seconds", "`bound`, 30", "there is no add-view or add-document mode",
                      "it stands and blocks the order", "`production-files-check.md`", "`round.json` holding the commit, the tools, the commands and the preview line",
                      "does not detect a mismatch", "`write_folder`", "the seeding command and its tests are unchanged",
                      "a symbolic link or a check record in any folder given", "a round file with a key the production-files check does not have",
                      "the tests need no model, no KiCad and no gerbonara", "The record is committed in the board's folder by whoever runs the check"):
            self.assertIn(words, section, f"the hardware notes' section says {words!r}")
        proof = self.flat(notes[notes.index("The same design also proves the method's [ordering step]"):].split("\n\n")[0])
        self.assertIn("The fanned-out check", proof)
        self.assertIn("a fanned-out run of its own", proof)
        self.assertIn("task hw:production-review-folder", proof)
        self.assertIn("until that run is recorded the method relies on the single-reviewer form of the check", proof)
        commands = notes[notes.index("## The commands"):notes.index("## When the board check runs")]
        self.assertIn("`task hw:production-review-folder", commands)

    def test_the_task_runner_names_the_folder_command_and_the_new_tests_in_both_test_descriptions_and_the_notes_list_them(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses a folder inside the repository, a folder that is not new or empty, and a missing preview. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        taskfile = self.read("Taskfile.yml")
        folder = self.flat(taskfile[taskfile.index("  hw:production-review-folder:"):].splitlines()[1])
        for words in ("production_review_folder.py", "the commit the production files were exported from", "gerbers/, layers/ and footprints/",
                      "through the assembly the production-files seeding command writes its own folder with", "holds no check record",
                      "takes the commit as an input and records it without detecting a mismatch", "refuses a folder inside the repository",
                      "a folder that is not new or empty", "a missing preview", "on demand, in neither gate"):
            self.assertIn(words, folder)
        self.assertIn("python3", taskfile[taskfile.index("  hw:production-review-folder:"):].split("cmds:")[1].splitlines()[1])
        descriptions = (taskfile[taskfile.index("  hw:test:\n"):].splitlines()[1], taskfile[taskfile.index("  hw:test:round:"):].splitlines()[1])
        for text in descriptions:
            self.assertIn("production-files check", text)
            self.assertIn("folder command", text)
        notes = self.read("hardware", "README.md")
        listed = next(line for line in notes.splitlines() if line.startswith("- `task hw:test` runs"))
        self.assertIn("the production-files check's caller and its folder command", listed)
        self.assertIn("the production-files check's caller and the command that writes a real order's review folder", notes.splitlines()[5])


if __name__ == "__main__":
    unittest.main()
