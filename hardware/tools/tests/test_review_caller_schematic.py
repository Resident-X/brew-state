#!/usr/bin/env python3
"""The schematic review as a caller of the review kit command, over synthetic review folders.

The caller is loaded as the kit loads it and run as shipped: its declaration, prompts, tool grant, checks and rendering are
exercised through the kit's own functions, and through the kit's command against a stand-in for the agent command line. The
method, the schematic, the netlist and every verdict are synthetic. No model and no KiCad is used, and the real agent command line
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

import board_review_history  # noqa: E402
import review_caller_layout  # noqa: E402
import review_caller_schematic as caller  # noqa: E402
import review_catalogue  # noqa: E402
import review_folder  # noqa: E402
import schematic_fixtures as sfx  # noqa: E402
import schematic_review_folder  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import command, merge, messages, planner  # noqa: E402
from review_kit import results as kit_results  # noqa: E402
from review_kit import executor as ex  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
GRANT = "Read,Glob,Grep,WebFetch"
SMALL = "claude-haiku-5-5"
UNITS = {"area-PINV": ["PINV-1", "PINV-2"], "area-STRAP": ["STRAP-1"], "area-DERATE": ["DERATE-1", "DERATE-2"],
         "free-pass": ["FREE-PASS"]}
#: What each item of the synthetic catalogue selects on the synthetic schematic: PINV-1 every net, DERATE-1 every part and DERATE-2
#: every sheet; the others select nothing.
SELECTS = {"PINV-1": sfx.NETS, "DERATE-1": sfx.PARTS, "DERATE-2": sfx.SHEETS}

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
found = 0
for unit, body in re.findall(r"Your unit: (\\S+)\\n(.*?)(?=Your unit: |\\Z)", text, re.S):
    for item in re.findall(r"^- ([A-Z]+-\\d+|FREE-PASS)$", body, re.M):
        cells = scenario.get("pairs", {}).get(item, ["none"])
        for cell in cells:
            verdict = (scenario.get("model_verdicts", {}).get(model, {}).get(item + "|" + cell)
                       or scenario.get("verdicts", {}).get(item + "|" + cell) or scenario.get("verdicts", {}).get(item)
                       or ("not applicable" if cell == "none" and item != "FREE-PASS" else "pass"))
            why = scenario.get("why", {}).get(item, "Judged on the schematic.")
            if verdict == "fail":
                found += 1
                why = f"finding 1.{found}"
                tables["Findings"].append({"Finding": found, "Item": item, "Raised by": item, "Severity": "function",
                                           "What and where": f"sheet board, net {cell}: out of its rating", "Closed by": ""})
            tables["Verdicts"].append({"Item": item, "Net or part": cell, "Verdict": verdict, "Rests on": "sheet board, MCU datasheet",
                                       "Why": why})
fetch = scenario.get("fetch") or []
uses = [{"type": "tool_use", "id": "f%d" % number, "name": "WebFetch", "input": {"url": "https://example.invalid/%d" % number}}
        for number in range(len(fetch))] or None
sys.stdout.write(ex.stream_text(session_id, text="done", structured={"tables": tables}, blocks=uses,
                                cost=scenario.get("cost", {}).get(model, 0.03), api_ms=scenario.get("api_ms", {}).get(model, 300), turns=1,
                                read=1000, write=200, generated=50, tools=report.get("tools", tools), model=model,
                                cwd=report.get("cwd", os.getcwd()), mcp_servers=report.get("mcp_servers", ())))
for number, failed in enumerate(fetch):
    sys.stdout.write(json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "f%d" % number, "is_error": bool(failed), "content": "x"}]}}) + "\\n")
'''


def verdict(item, cell, outcome="pass", why="Judged on the schematic.", rests="sheet board, net /IN"):
    return {"Item": item, "Net or part": cell, "Verdict": outcome, "Rests on": rests, "Why": why}


def finding(number, item, what="sheet board, net /IN: a pin above its rating", severity="function", raised=None, closed=""):
    return {"Finding": number, "Item": item, "Raised by": raised or ("free pass" if item == "FREE-PASS" else item),
            "Severity": severity, "What and where": what, "Closed by": closed}


def rows_of(item, cells=None, outcome="pass"):
    """The rows an item gives on what it selects on the synthetic schematic, `none` for an item that selects nothing."""
    cells = SELECTS.get(item, ["none"]) if cells is None else cells
    return [verdict(item, cell, "not applicable" if cell == "none" and item != "FREE-PASS" else outcome,
                    "It does not apply." if cell == "none" else "Judged on the schematic.") for cell in cells]


def results(units=UNITS):
    """A synthetic result for every unit of a round: every item passes on every net, part and sheet it selects."""
    return {unit: {"Verdicts": [row for item in items for row in rows_of(item)], "Findings": []} for unit, items in units.items()}


def prepared(folder):
    return kit_caller.load("schematic", TOOLS).prepare(folder)


def merged(folder, given, order=None, replicas=None):
    """The unit results merged as the command merges them, each unit one replica unless `replicas` gives more."""
    return prepared(folder).merge(order or list(given), {unit: replicas.get(unit, {"r1": tables}) if replicas else {"r1": tables}
                                                         for unit, tables in given.items()})


def rendered(folder, given, replicas=None):
    package = prepared(folder)
    out = package.merge(list(given), {unit: replicas.get(unit, {"r1": tables}) if replicas else {"r1": tables}
                                      for unit, tables in given.items()})
    return package.render(merge.plain_tables(out))


def slurp(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Folder(unittest.TestCase):
    """A review folder the folder command wrote from a synthetic repository, in a temporary folder."""

    number = 1
    record = sfx.RECORD

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="schematic-caller-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.folder = sfx.write_review_folder(self.root, self.number, self.record)

    def refused(self, call, *words):
        with self.assertRaises(merge.Refused) as caught:
            call()
        text = "; ".join(caught.exception.causes)
        for word in words:
            self.assertIn(word, text)
        return text

    def path(self, name):
        return os.path.join(self.folder, name)

    def add_document(self, item="STRAP-1", why="needs the datasheet of U1: the strap levels are not in the folder",
                     name="u1-strap.txt", target=None):
        document = os.path.join(self.root, name)
        sfx.write(document, "Strap high: at least 2.0 V\n")
        status, text = sfx.run_folder(sfx.add_document_argv(self.folder, document, "manufacturer datasheet", item, why, target))
        self.assertEqual(status, 0, text)

    def add_view(self, item="STRAP-1", why="needs the sheet Power: its drawing is blurred", name="power-large.svg", target=None):
        view = os.path.join(self.root, name)
        sfx.write(view, "<svg/>")
        status, text = sfx.run_folder(sfx.add_view_argv(self.folder, view, item, why, target))
        self.assertEqual(status, 0, text)


class TheUnits(Folder):
    def test_the_units_are_the_catalogue_areas_and_one_for_the_free_pass(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C1: From a synthetic review folder the caller's units are one per area heading of the folder's circuit practice catalogue and one for the whole-schematic free pass; a folder whose method has no circuit catalogue areas is refused naming what is missing. A method whose catalogue repeats an area code, or holds an item outside any area, is refused naming it, since the item would otherwise drop out of every unit. Items that select every net or every part stay in their area's unit. Out of scope: the content of any catalogue item and the kit's mechanics.
        package = prepared(self.folder)
        self.assertEqual(list(package.declaration.units), list(UNITS))
        self.assertEqual({unit: list(item.items) for unit, item in package.declaration.units.items()}, UNITS)
        self.assertEqual(package.checklist, ("PINV-1", "PINV-2", "STRAP-1", "DERATE-1", "DERATE-2", "FREE-PASS"),
                         "the checklist is the catalogue's items in the method's order and the free pass's entry last")
        self.assertEqual([code for code, _, _ in review_catalogue.areas(self.folder, review_folder.CIRCUIT_SECTION)],
                         ["PINV", "STRAP", "DERATE"])
        self.assertNotIn("NOT-1", package.checklist, "an item of a section outside the circuit catalogue is no unit's")

    def test_an_item_that_selects_every_net_or_part_stays_in_its_areas_unit_and_is_not_split(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C1: From a synthetic review folder the caller's units are one per area heading of the folder's circuit practice catalogue and one for the whole-schematic free pass; a folder whose method has no circuit catalogue areas is refused naming what is missing. A method whose catalogue repeats an area code, or holds an item outside any area, is refused naming it, since the item would otherwise drop out of every unit. Items that select every net or every part stay in their area's unit. Out of scope: the content of any catalogue item and the kit's mechanics.
        package = prepared(self.folder)
        units = package.declaration.units
        self.assertEqual(list(units["area-PINV"].items), ["PINV-1", "PINV-2"], "the item that selects every net stays with its area")
        self.assertEqual(list(units["area-DERATE"].items), ["DERATE-1", "DERATE-2"], "the items that select every part and sheet too")
        every = caller.selects_all(self.folder)
        self.assertEqual(every, {"PINV-1": "net", "DERATE-1": "part", "DERATE-2": "sheet"})
        self.assertEqual(sum(1 for unit in units.values() for item in unit.items if item == "PINV-1"), 1, "in exactly one unit")
        names = caller.schematic_names(self.folder)
        self.assertGreater(units["area-PINV"].expected_output_tokens, units["area-STRAP"].expected_output_tokens,
                           "a unit with an item that selects every net is expected to give more rows")
        self.assertEqual(caller.expected_tokens(["PINV-1"], every, names) - caller.expected_tokens(["PINV-2"], every, names),
                         caller.TOKENS_PER_NAME * len(names.nets))

    def test_the_free_pass_unit_judges_the_whole_schematic_and_each_area_unit_holds_its_own_area_only(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C1: From a synthetic review folder the caller's units are one per area heading of the folder's circuit practice catalogue and one for the whole-schematic free pass; a folder whose method has no circuit catalogue areas is refused naming what is missing. A method whose catalogue repeats an area code, or holds an item outside any area, is refused naming it, since the item would otherwise drop out of every unit. Items that select every net or every part stay in their area's unit. Out of scope: the content of any catalogue item and the kit's mechanics.
        package = prepared(self.folder)
        free = package.unit_text("free-pass")
        self.assertIn("Your unit: free-pass", free)
        self.assertIn("- FREE-PASS", free)
        self.assertIn("anything else wrong with it", free)
        self.assertNotIn("### Pin voltages", free, "the free pass holds no area block")
        pinv = package.unit_text("area-PINV")
        self.assertIn("Your unit: area-PINV", pinv)
        self.assertIn("- PINV-1\n- PINV-2", pinv)
        self.assertIn("### Pin voltages (PINV)", pinv)
        for other in ("STRAP-1", "DERATE-1", "### Boot and strap", "### Derating"):
            self.assertNotIn(other, pinv, "a unit's prompt holds its own area only")
        for words in ("Net or part", "exactly as the netlist writes it", "`none`", "a datasheet is opened at its address",
                      "never recalled", "needs <the document or sheet>", "board-Power.svg", "sheets/board.svg"):
            self.assertIn(words, pinv.replace("A datasheet", "a datasheet"))
        for column in caller.VERDICT_TABLE + caller.FINDING_TABLE:
            self.assertIn(column, pinv)

    def test_a_folder_whose_method_has_no_circuit_catalogue_areas_is_refused_naming_what_is_missing(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C1: From a synthetic review folder the caller's units are one per area heading of the folder's circuit practice catalogue and one for the whole-schematic free pass; a folder whose method has no circuit catalogue areas is refused naming what is missing. A method whose catalogue repeats an area code, or holds an item outside any area, is refused naming it, since the item would otherwise drop out of every unit. Items that select every net or every part stay in their area's unit. Out of scope: the content of any catalogue item and the kit's mechanics.
        extract = self.path("method-extract.md")
        text = slurp(extract)
        sfx.write(extract, re.sub(r"^### (Pin voltages|Boot and strap|Derating) \(\w+\)$", r"### \1", text, flags=re.M))
        method = self.path("docs/board-design-method.md")
        held = slurp(method)
        sfx.write(method, re.sub(r"^### (Pin voltages|Boot and strap|Derating) \(\w+\)$", r"### \1", held, flags=re.M))
        self.refused(lambda: prepared(self.folder), "no catalogue area heading")
        sfx.write(method, held.replace("## Circuit practice catalogue", "## Something else"))
        self.refused(lambda: prepared(self.folder), "no `## Circuit practice catalogue` section")
        sfx.write(extract, text)
        sfx.write(method, held.replace("### Boot and strap (STRAP)\n\n#### STRAP-1. A strap pin is not left floating",
                                       "### Boot and strap (STRAP)\n\nNo item.\n\n#### notanitem"))
        self.refused(lambda: prepared(self.folder), "the area STRAP with no item")
        sfx.write(method, held.replace("Intro of the circuit catalogue.\n\n### How a circuit item is read\n\nEvery item carries fields.\n\n", ""))
        self.refused(lambda: prepared(self.folder), "no introduction")
        os.remove(method)
        self.refused(lambda: prepared(self.folder), "no readable method")

    def test_an_area_code_given_twice_or_an_item_outside_any_area_is_refused_naming_it_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C1: From a synthetic review folder the caller's units are one per area heading of the folder's circuit practice catalogue and one for the whole-schematic free pass; a folder whose method has no circuit catalogue areas is refused naming what is missing. A method whose catalogue repeats an area code, or holds an item outside any area, is refused naming it, since the item would otherwise drop out of every unit. Items that select every net or every part stay in their area's unit. Out of scope: the content of any catalogue item and the kit's mechanics.
        method = self.path("docs/board-design-method.md")
        held = slurp(method)
        self.assertIn("### Pin voltages (PINV)\n", held)
        sfx.write(method, held.replace("### Pin voltages (PINV)\n", "### Pin voltages again (PINV)\n\n#### PINV-9. Again.\n\nText.\n\n"
                                       "### Pin voltages (PINV)\n", 1))
        text = self.refused(lambda: prepared(self.folder), "repeats an area code", "PINV")
        self.assertNotIn("PINV-9 is", text)
        self.assertEqual(len(re.findall("PINV", text.split("(")[1].split(")")[0])), 1, "the repeated code is named once")
        with self.assertRaises(merge.Refused):
            caller.checklist(self.folder)
        sfx.write(method, held.replace("### Pin voltages (PINV)\n", "#### OUT-9. Outside any area.\n\nText.\n\n### Pin voltages (PINV)\n", 1))
        self.refused(lambda: prepared(self.folder), "the item OUT-9 before any area heading")
        sfx.write(method, held)
        self.assertEqual(list(prepared(self.folder).declaration.units), list(UNITS), "the unedited catalogue is accepted")

    def test_the_real_methods_circuit_catalogue_gives_one_unit_for_each_of_its_areas(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C1: From a synthetic review folder the caller's units are one per area heading of the folder's circuit practice catalogue and one for the whole-schematic free pass; a folder whose method has no circuit catalogue areas is refused naming what is missing. A method whose catalogue repeats an area code, or holds an item outside any area, is refused naming it, since the item would otherwise drop out of every unit. Items that select every net or every part stay in their area's unit. Out of scope: the content of any catalogue item and the kit's mechanics.
        method = slurp(os.path.join(REPO, "docs", "board-design-method.md"))
        folder = sfx.write_review_folder(os.path.join(self.root, "real"), method=method)
        package = prepared(folder)
        areas = review_catalogue.areas(folder, review_folder.CIRCUIT_SECTION)
        self.assertEqual(list(package.declaration.units), [f"area-{code}" for code, _, _ in areas] + ["free-pass"])
        self.assertEqual([item for found in package.declaration.units.values() for item in found.items][:-1],
                         [item for _, _, items in areas for item in items])
        self.assertTrue(all(items for _, _, items in areas))
        every = caller.selects_all(folder)
        self.assertEqual(sorted(every.values()), ["net", "part", "sheet"], "PINV-1, DERATE-2 and DRAW-1 select every net, part, sheet")
        for item, what in every.items():
            unit = [name for name, found in package.declaration.units.items() if item in found.items]
            self.assertEqual(len(unit), 1, f"{item} is in one unit")
            self.assertTrue(unit[0].startswith("area-"), "an item that selects everything stays in its area's unit")


class TheSharedContext(Folder):
    def test_the_shared_context_holds_the_extract_the_round_the_netlist_the_records_and_the_schematic_and_no_unit_prompt(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. It also refuses a folder inside any input or that is a file; a commit the repository lacks; a design without exactly one project and its schematic; an unreadable or uncommitted schematic or sheet file; a sheet with a slash in its name or no name; a netlist that is unreadable, not a netlist in the design tool's format, empty, cut off or a symlink, or a netlist command that is not one line; an empty or symlinked drawing; no sheets folder; a missing or symlinked check report; no record, a record given twice, or a record that is an absolute path, escapes the commit, is not at the commit, is not a markdown or yaml file or is named schematic-review.md, designer-notes*, session* or *-review.md; those names are matched without regard to case and in every component of the record's path, not only its basename; a round number that is not a whole number of 1 or more; a method lacking the schematic review, schematic drawing convention or circuit practice catalogue section, or a documents repository lacking the method or README; and a later round whose commit's record lacks an earlier round. The add modes refuse a target that is not a net, part or sheet of the folder, --cannot-judge-target on a folder that is not a schematic one, and a resolutions file carrying a target in a non-schematic folder or unknown entry keys; the round-file readers of every review refuse unknown keys. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        package = prepared(self.folder)
        names = sorted(package.declaration.artefacts)
        design = sfx.DESIGN
        self.assertEqual(names, sorted(["method-extract.md", "review.net", "round.json", "check-report.txt",
                                        f"{design}/board.kicad_sch", f"{design}/power.kicad_sch", f"{design}/board.kicad_sym",
                                        f"{design}/constraints.md", f"{design}/circuit-proof.md", f"{design}/separation-basis.yaml"]))
        self.assertEqual(package.declaration.artefacts["method-extract.md"].kind, "extract")
        self.assertEqual(package.declaration.artefacts["review.net"].kind, "text")
        for unit in package.declaration.units.values():
            self.assertEqual(sorted(unit.needs), names, "every unit needs the whole shared context")
        extract = slurp(self.path("method-extract.md"))
        for heading in schematic_review_folder.SECTIONS:
            self.assertIn(f"## {heading}", extract)
        self.assertNotIn("Unrelated: a layout review section", extract)
        self.assertNotIn("NOT-1", extract)
        text = package.unit_text("area-STRAP")
        self.assertNotIn("PINV-1", text)

    def test_a_round_after_the_first_holds_the_earlier_rounds_in_its_context_and_a_first_round_none(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. It also refuses a folder inside any input or that is a file; a commit the repository lacks; a design without exactly one project and its schematic; an unreadable or uncommitted schematic or sheet file; a sheet with a slash in its name or no name; a netlist that is unreadable, not a netlist in the design tool's format, empty, cut off or a symlink, or a netlist command that is not one line; an empty or symlinked drawing; no sheets folder; a missing or symlinked check report; no record, a record given twice, or a record that is an absolute path, escapes the commit, is not at the commit, is not a markdown or yaml file or is named schematic-review.md, designer-notes*, session* or *-review.md; those names are matched without regard to case and in every component of the record's path, not only its basename; a round number that is not a whole number of 1 or more; a method lacking the schematic review, schematic drawing convention or circuit practice catalogue section, or a documents repository lacking the method or README; and a later round whose commit's record lacks an earlier round. The add modes refuse a target that is not a net, part or sheet of the folder, --cannot-judge-target on a folder that is not a schematic one, and a resolutions file carrying a target in a non-schematic folder or unknown entry keys; the round-file readers of every review refuse unknown keys. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.assertNotIn(f"{sfx.DESIGN}/schematic-review.md", prepared(self.folder).declaration.artefacts)
        later = sfx.write_review_folder(os.path.join(self.root, "later"), 2)
        package = prepared(later)
        self.assertIn(f"{sfx.DESIGN}/schematic-review.md", package.declaration.artefacts)
        self.assertIn("This is round 2", package.unit_text("area-PINV"))
        self.assertIn("`finding <that round>.<n>`", package.unit_text("area-PINV"))
        self.assertNotIn("This is round", prepared(self.folder).unit_text("area-PINV"))

    def test_a_folder_lacking_a_file_the_command_writes_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        for name in ("method-extract.md", "review.net", "round.json", "check-report.txt"):
            with self.subTest(missing=name):
                held = slurp(self.path(name))
                os.remove(self.path(name))
                text = self.refused(lambda: prepared(self.folder))
                self.assertTrue(name in text or "round file" in text or "readable" in text, text)
                sfx.write(self.path(name), held)
        for name in ("board.kicad_sch",):
            held = slurp(self.path(f"{sfx.DESIGN}/{name}"))
            os.remove(self.path(f"{sfx.DESIGN}/{name}"))
            self.refused(lambda: prepared(self.folder), "board.kicad_sch")
            sfx.write(self.path(f"{sfx.DESIGN}/{name}"), held)
        extract = self.path("method-extract.md")
        held = slurp(extract)
        for heading in schematic_review_folder.SECTIONS:
            sfx.write(extract, held.replace(f"## {heading}\n", "## Renamed\n"))
            self.refused(lambda: prepared(self.folder), "method extract", f"no `## {heading}` section")
        sfx.write(extract, held)
        self.assertTrue(prepared(self.folder).declaration.units)
        shutil.rmtree(self.path("sheets"))
        self.refused(lambda: prepared(self.folder), "no drawing for the sheet", "write the folder with the folder command")

    def test_a_layout_reviews_or_a_hand_edited_round_file_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        good = sfx.round_file(self.folder)
        for name, content, word in (
                ("a layout round", {**good, "fields": ["number", "kind", "commit", "views", "check"]}, "holds"),
                ("a critical-routing pass", {"tool": good["tool"], "fields": ["number", "commit", "views"], "number": 1,
                                             "commit": good["commit"], "views": ["v"]}, "not a schematic review's"),
                ("a production round", {"tool": good["tool"], "fields": ["commit", "tools", "commands", "preview"],
                                        "commit": good["commit"], "tools": "t", "commands": ["c"], "preview": "p"},
                 "not a schematic review's"),
                ("a stray key", {**good, "bogus": 1}, "holds bogus"),
                ("a kind key", {**good, "kind": "full"}, "holds kind"),
                ("fields mixed with a layout field", {**good, "fields": ["number", "commit", "netlist", "records", "kind"]}, "mixes"),
                ("a missing netlist", {k: v for k, v in good.items() if k != "netlist"}, "netlist"),
                ("a netlist of two lines", {**good, "netlist": "a\nb"}, "netlist command"),
                ("no records", {**good, "records": []}, "records read"),
                ("a record twice", {**good, "records": ["a", "a"]}, "name a record twice"),
                ("a number of zero", {**good, "number": 0}, "round's number"),
                ("a bad commit", {**good, "commit": "xyz"}, "commit judged"),
                ("a foreign marker", {**good, "tool": "other"}, "not one the folder command wrote")):
            with self.subTest(name=name):
                sfx.write(self.path("round.json"), json.dumps(content))
                self.refused(lambda: prepared(self.folder), word)
                self.refused(lambda: caller.declaration(self.folder), word)
        sfx.write(self.path("round.json"), json.dumps(good))
        self.assertTrue(prepared(self.folder).declaration.units)

    def test_a_netlist_that_names_other_parts_or_sheets_than_the_schematic_is_refused_when_the_declaration_is_resolved(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        held = slurp(self.path("review.net"))
        sfx.write(self.path("review.net"), held.replace('(comp (ref "R2") (value "1k"))', '(comp (ref "R9") (value "1k"))'))
        text = self.refused(lambda: prepared(self.folder), "names parts other than the schematic's")
        self.assertIn("R2", text)
        self.assertIn("R9", text)
        sfx.write(self.path("review.net"), held.replace('(name "/Power/")', '(name "/Other/")'))
        self.refused(lambda: prepared(self.folder), "names sheets other than the schematic's", "Other")
        sfx.write(self.path("review.net"), "(not a netlist)")
        self.refused(lambda: prepared(self.folder), "not a KiCad netlist")
        sfx.write(self.path("review.net"), "(export (version \"E\"))")
        self.refused(lambda: prepared(self.folder), "holds no component and no net")
        sfx.write(self.path("review.net"), "(export (")
        self.refused(lambda: prepared(self.folder), "cannot be read as KiCad's netlist")
        sfx.write(self.path("review.net"), held)
        self.assertTrue(prepared(self.folder).declaration.units)


class TheMerge(Folder):
    def test_a_round_merges_one_row_for_every_pair_in_the_checklist_order_whatever_order_the_units_arrive_in(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        first = merged(self.folder, given)["tables"]["Verdicts"]["rows"]
        order = ["free-pass", "area-DERATE", "area-PINV", "area-STRAP"]
        second = merged(self.folder, given, order=order)["tables"]["Verdicts"]["rows"]
        self.assertEqual(rendered(self.folder, given), rendered(self.folder, {unit: given[unit] for unit in reversed(list(given))}),
                         "the rendered record is the same whatever order the units arrive in")
        self.assertEqual({(row["Item"], row["Net or part"]) for row in first}, {(row["Item"], row["Net or part"]) for row in second})
        pairs = [(row["Item"], row["Net or part"]) for row in first]
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertEqual(len(pairs), len(sfx.NETS) + 1 + 1 + len(sfx.PARTS) + len(sfx.SHEETS) + 1)
        self.assertEqual(merged(self.folder, given)["tables"]["Findings"]["rows"], [])

    def test_an_item_with_no_verdict_row_fails_the_merge_naming_it_and_its_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-PINV"]["Verdicts"] = [row for row in given["area-PINV"]["Verdicts"] if row["Item"] != "PINV-2"]
        text = self.refused(lambda: merged(self.folder, given), "item PINV-2 has no verdict row", "unit area-PINV", "--rerun")
        self.assertNotIn("PINV-1 has no", text)

    def test_a_net_part_or_sheet_in_no_items_rows_fails_the_merge_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        for item, cell, kind in (("PINV-1", "/MID", "net"), ("DERATE-1", "U1", "part"), ("DERATE-2", "Power", "sheet")):
            with self.subTest(left_out=cell):
                given = results()
                unit = next(name for name, items in UNITS.items() if item in items)
                given[unit]["Verdicts"] = [row for row in given[unit]["Verdicts"]
                                           if (row["Item"], row["Net or part"]) != (item, cell)]
                text = self.refused(lambda: merged(self.folder, given), f"1 {kind} appear", cell)
                self.assertNotIn("has no verdict row", text, "the item still has its other rows")

    def test_a_net_named_only_by_another_items_rows_is_covered_by_them(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        base = len(merged(self.folder, given)["tables"]["Verdicts"]["rows"])
        given["area-PINV"]["Verdicts"] = [row for row in given["area-PINV"]["Verdicts"]
                                          if (row["Item"], row["Net or part"]) != ("PINV-1", "GND")]
        self.refused(lambda: merged(self.folder, given), "1 net appear", "GND")
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "GND", "not applicable", "No strap on it.")]
        rows = merged(self.folder, given)["tables"]["Verdicts"]["rows"]
        self.assertEqual(len(rows), base - 1, "STRAP-1's row for GND stands in for PINV-1's, and its none row is gone")

    def test_a_row_naming_a_net_part_or_sheet_that_does_not_exist_fails_the_merge_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        for cell in ("/GHOST", "R99", "Missing sheet", "gnd", "IN"):
            with self.subTest(cell=cell):
                given = results()
                given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", cell, "pass", "Judged.")]
                text = self.refused(lambda: merged(self.folder, given), "STRAP-1 on", repr(cell), "no net, part or sheet",
                                    "unit area-STRAP")
                self.assertIn("--rerun", text)

    def test_the_free_pass_has_exactly_one_row_with_none_and_names_nothing(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["free-pass"]["Verdicts"] = [verdict("FREE-PASS", "GND", "pass", "x")]
        self.refused(lambda: merged(self.folder, given), "free pass's row names 'GND'")
        given["free-pass"]["Verdicts"] = [verdict("FREE-PASS", "none"), verdict("FREE-PASS", "none", "pass", "again")]
        package = prepared(self.folder)
        assessed = kit_results.assess({"tables": given["free-pass"]}, "", package.declaration.shape, "free-pass", ["FREE-PASS"])
        self.assertTrue([problem for problem in assessed.problems if "2 verdicts" in problem.line()],
                        "the kit holds the unit to one row for the pair")

    def test_an_item_with_a_none_row_and_another_row_fails_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "none", "not applicable", "No strap pin."),
                                           verdict("STRAP-1", "U1", "pass", "Judged.")]
        text = self.refused(lambda: merged(self.folder, given), "STRAP-1 has a `none` row", "selects nothing", "1 more")
        self.assertIn("unit area-STRAP", text)

    def test_a_pass_or_fail_without_rests_on_and_a_not_applicable_or_fail_without_why_fail_naming_the_pair(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        for outcome, rests, why, word in (("pass", " ", "ok", "cites nothing under Rests on"), ("fail", "", "finding 1.1", "cites nothing"),
                                          ("not applicable", "", " ", "gives no Why"), ("fail", "sheet", " ", "gives no Why")):
            with self.subTest(outcome=outcome, rests=rests, why=why):
                given = results()
                given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "U1", outcome, why, rests)]
                if outcome == "fail":
                    given["area-STRAP"]["Findings"] = [finding(1, "STRAP-1")]
                self.refused(lambda: merged(self.folder, given), "STRAP-1 on U1", word)
        given = results()
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "U1", "pass", "", "datasheet SLVS165O p.4")]
        self.assertTrue(merged(self.folder, given), "a pass needs no Why")

    def test_the_free_pass_row_needs_rests_on_for_a_pass_or_fail_and_a_why_for_a_not_applicable_or_fail(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        for outcome, rests, why, word in (("pass", "", "x", "cites nothing under Rests on"), ("fail", " ", "finding 1.1", "cites nothing"),
                                          ("not applicable", "", "", "gives no Why"), ("fail", "sheet", "", "gives no Why")):
            with self.subTest(outcome=outcome, rests=rests, why=why):
                given = results()
                given["free-pass"]["Verdicts"] = [verdict("FREE-PASS", "none", outcome, why, rests)]
                if outcome == "fail":
                    given["free-pass"]["Findings"] = [finding(1, "FREE-PASS")]
                self.refused(lambda: merged(self.folder, given), "FREE-PASS on none", word)
        given = results()
        given["free-pass"]["Verdicts"] = [verdict("FREE-PASS", "none", "pass", "", "sheet board")]
        self.assertTrue(merged(self.folder, given), "a free pass that rests on a sheet needs no Why")

    def test_findings_are_numbered_in_the_checklist_order_and_the_citations_follow_the_renumbering(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-DERATE"]["Verdicts"] = [row if row["Item"] != "DERATE-1" or row["Net or part"] != "R1" else
                                            verdict("DERATE-1", "R1", "fail", "finding 1.1") for row in given["area-DERATE"]["Verdicts"]]
        given["area-DERATE"]["Findings"] = [finding(1, "DERATE-1", "sheet board, part R1: derated badly")]
        given["area-PINV"]["Verdicts"] = [row if row["Net or part"] != "/IN" or row["Item"] != "PINV-1" else
                                          verdict("PINV-1", "/IN", "fail", "finding 1.1") for row in given["area-PINV"]["Verdicts"]]
        given["area-PINV"]["Findings"] = [finding(1, "PINV-1")]
        given["free-pass"] = {"Verdicts": [verdict("FREE-PASS", "none", "fail", "finding 1.1")],
                              "Findings": [finding(1, "FREE-PASS", "sheet Power: two circuits on one sheet", "cosmetic")]}
        out = merged(self.folder, given)["tables"]
        self.assertEqual([(row["Finding"], row["Item"]) for row in out["Findings"]["rows"]],
                         [(1, "PINV-1"), (2, "DERATE-1"), (3, "FREE-PASS")], "numbered at the merge, the free pass's last")
        why = {(row["Item"], row["Net or part"]): row["Why"] for row in out["Verdicts"]["rows"] if row["Verdict"] == "fail"}
        self.assertEqual(why, {("PINV-1", "/IN"): "finding 1.1", ("DERATE-1", "R1"): "finding 1.2", ("FREE-PASS", "none"): "finding 1.3"})

    def test_a_fail_needs_a_finding_of_its_own_item_and_a_finding_needs_a_fail(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        def pinv_fail(why="finding 1.1", findings=(finding(1, "PINV-1"),), item="PINV-1"):
            given = results()
            given["area-PINV"]["Verdicts"] = [verdict("PINV-1", "/IN", "fail", why)] + [
                row for row in given["area-PINV"]["Verdicts"] if (row["Item"], row["Net or part"]) != ("PINV-1", "/IN")]
            given["area-PINV"]["Findings"] = list(findings)
            return given
        self.assertTrue(merged(self.folder, pinv_fail()))
        self.refused(lambda: merged(self.folder, pinv_fail(findings=())), "the unit did not raise")
        self.refused(lambda: merged(self.folder, pinv_fail(why="it is wrong")), "fails and cites no finding of this round or of an earlier")
        self.refused(lambda: merged(self.folder, pinv_fail(findings=(finding(1, "PINV-2"),))), "cites finding 1, which names item PINV-2")
        self.refused(lambda: merged(self.folder, pinv_fail(findings=(finding(1, "PINV-1"), finding(2, "PINV-2")))),
                     "finding 2 names item PINV-2, which does not fail")
        given = results()
        given["area-STRAP"]["Findings"] = [finding(1, "STRAP-1")]
        self.refused(lambda: merged(self.folder, given), "names item STRAP-1, which does not fail")

    def test_a_findings_row_with_a_wrong_raised_by_a_severity_outside_the_four_a_closed_by_or_no_place_fails_the_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        def with_finding(**changes):
            given = results()
            given["area-PINV"]["Verdicts"] = [verdict("PINV-1", "/IN", "fail", "finding 1.1")] + [
                row for row in given["area-PINV"]["Verdicts"] if (row["Item"], row["Net or part"]) != ("PINV-1", "/IN")]
            given["area-PINV"]["Findings"] = [{**finding(1, "PINV-1"), **changes}]
            return given
        self.assertTrue(merged(self.folder, with_finding()))
        self.refused(lambda: merged(self.folder, with_finding(**{"Raised by": "PINV-2"})), "finding 1 is raised by 'PINV-2', not 'PINV-1'")
        self.refused(lambda: merged(self.folder, with_finding(**{"Raised by": "free pass"})), "not 'PINV-1'")
        self.refused(lambda: merged(self.folder, with_finding(Severity="minor")), "severity 'minor', outside")
        self.refused(lambda: merged(self.folder, with_finding(**{"Closed by": "met: it is fine"})), "has a Closed by")
        self.refused(lambda: merged(self.folder, with_finding(**{"What and where": " "})), "says nothing under What and where")
        given = results()
        given["free-pass"] = {"Verdicts": [verdict("FREE-PASS", "none", "fail", "finding 1.1")],
                              "Findings": [finding(1, "FREE-PASS", raised="FREE-PASS")]}
        self.refused(lambda: merged(self.folder, given), "not 'free pass'")

    def test_a_cannot_judge_fails_the_round_naming_the_item_the_net_and_the_document_or_sheet_it_needs(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "U1", "cannot judge", "needs the datasheet of U1: the levels are unknown")]
        text = self.refused(lambda: merged(self.folder, given), "item STRAP-1 on U1 is still cannot judge",
                            "asks for the datasheet of U1", "unit area-STRAP", "--add-view --cannot-judge-target U1",
                            "--add-document", "--cannot-judge-item STRAP-1 --cannot-judge-target U1")
        self.assertIn("--rerun", text)
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "none", "cannot judge", "needs sheet Power: it is blurred")]
        text = self.refused(lambda: merged(self.folder, given), "item STRAP-1 on none is still cannot judge", "asks for sheet Power")
        self.assertNotIn("--cannot-judge-target none", text)
        self.assertNotIn("--add-document", text, "a sheet is a view, not a document")
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "none", "cannot judge", "unsure")]
        self.refused(lambda: merged(self.folder, given), "asks for 'unsure'")

    def test_a_cannot_judge_already_resolved_by_an_added_file_says_to_run_the_unit_again(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.add_document(target="U1")
        given = results()
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "U1", "cannot judge", "needs the datasheet of U1: x")]
        text = self.refused(lambda: merged(self.folder, given), "the folder already holds a document added for this item",
                            "run unit area-STRAP again with --rerun")
        self.assertNotIn("--cannot-judge-target U1 and", text)

    def test_a_recorded_cannot_judge_for_an_item_or_pair_without_a_row_fails_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.add_document(item="STRAP-1", target="U1")
        given = results()
        text = self.refused(lambda: merged(self.folder, given), "cannot judge for STRAP-1 on 'U1', which has no verdict row")
        self.assertIn("unit area-STRAP", text)
        given["area-STRAP"]["Verdicts"] = []
        self.refused(lambda: merged(self.folder, given), "item STRAP-1 has no verdict row")
        folder = sfx.write_review_folder(os.path.join(self.root, "other"))
        view = os.path.join(self.root, "v.svg")
        sfx.write(view, "<svg/>")
        status, text = sfx.run_folder(sfx.add_view_argv(folder, view, "FREE-PASS", "needs sheet board: blurred"))
        self.assertEqual(status, 0, text)
        sfx.write(os.path.join(folder, "added-views", "resolutions.json"),
                  slurp(os.path.join(folder, "added-views", "resolutions.json")).replace("FREE-PASS", "NOPE-9"))
        self.refused(lambda: merged(folder, results()), "cannot judge for 'NOPE-9', which is not an item this round judges")

    def test_a_row_for_an_item_off_the_checklist_fails_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-STRAP"]["Verdicts"] += [verdict("MISC-7", "U1")]
        self.refused(lambda: merged(self.folder, given), "a verdict row for MISC-7", "does not judge")

    def test_a_table_with_a_column_the_methods_table_lacks_or_without_one_it_has_is_rejected_on_every_path(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        package = prepared(self.folder)
        shape = package.declaration.shape
        self.assertEqual(list(shape.table("Verdicts").columns), caller.VERDICT_TABLE)
        self.assertEqual(list(shape.table("Verdicts").key_columns), ["Item", "Net or part"])
        self.assertEqual(list(shape.table("Findings").columns), caller.FINDING_TABLE)
        good = results()["area-STRAP"]
        for name, table, change, word in (
                ("an extra verdicts column", "Verdicts", lambda row: {**row, "Colour": "red"}, "has a column 'Colour' the table does not have"),
                ("a missing verdicts column", "Verdicts", lambda row: {k: v for k, v in row.items() if k != "Rests on"}, "lacks the column"),
                ("a renamed verdicts column", "Verdicts", lambda row: {("Net" if k == "Net or part" else k): v for k, v in row.items()},
                 "has a column 'Net' the table does not have")):
            with self.subTest(name=name):
                answer = {"Verdicts": [change(row) for row in good["Verdicts"]], "Findings": []}
                assessed = kit_results.assess({"tables": answer}, "", shape, "area-STRAP", ["STRAP-1"])
                self.assertIsNone(assessed.tables, "an answer with such a table is not mapped to the record")
                self.assertTrue([problem for problem in assessed.problems if problem.cls == kit_results.FATAL and word in problem.line()],
                                [problem.line() for problem in assessed.problems])
        extra_finding = {"Verdicts": good["Verdicts"], "Findings": [{**finding(1, "STRAP-1"), "Rule": "no"}]}
        assessed = kit_results.assess({"tables": extra_finding}, "", shape, "area-STRAP", ["STRAP-1"])
        self.assertIsNone(assessed.tables)
        self.assertTrue([problem for problem in assessed.problems if "has a column 'Rule'" in problem.line()])
        given = results()
        given["area-STRAP"] = {"Verdicts": [{**row, "Colour": "red"} for row in good["Verdicts"]], "Findings": []}
        self.refused(lambda: merged(self.folder, given), "Colour")

    def test_replicas_are_merged_any_fail_per_pair_and_a_pair_one_replica_alone_gave_stands(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        first, second = results(), results()
        second["area-PINV"]["Verdicts"] = [row if (row["Item"], row["Net or part"]) != ("PINV-1", "GND") else
                                           verdict("PINV-1", "GND", "fail", "finding 1.1") for row in second["area-PINV"]["Verdicts"]]
        second["area-PINV"]["Findings"] = [finding(1, "PINV-1", "sheet board, net GND: a pin above its rating")]
        out = merged(self.folder, first, replicas={"area-PINV": {"r1": first["area-PINV"], "r2": second["area-PINV"]}})["tables"]
        by_pair = {(row["Item"], row["Net or part"]): row["Verdict"] for row in out["Verdicts"]["rows"]}
        self.assertEqual(by_pair[("PINV-1", "GND")], "fail", "one replica's fail stands for its pair")
        self.assertEqual(by_pair[("PINV-1", "/IN")], "pass", "the other pairs stay as both gave them")
        self.assertEqual(len(out["Verdicts"]["rows"]), len(merged(self.folder, first)["tables"]["Verdicts"]["rows"]))
        self.assertEqual([row["Finding"] for row in out["Findings"]["rows"]], [1])
        third = results()
        third["area-PINV"]["Verdicts"] = [row for row in third["area-PINV"]["Verdicts"] if row["Net or part"] != "/MID"]
        out = merged(self.folder, first, replicas={"area-PINV": {"r1": first["area-PINV"], "r2": third["area-PINV"]}})["tables"]
        self.assertIn(("PINV-1", "/MID"), {(row["Item"], row["Net or part"]) for row in out["Verdicts"]["rows"]},
                      "a pair only one replica gave stands, so the net is covered")

    @staticmethod
    def disagreeing():
        """Two replicas of the unit that judges PINV-1, which selects every net: one says it selects nothing, the other judges
        every net."""
        selects_nothing, selects = results(), results()
        selects_nothing["area-PINV"]["Verdicts"] = [row for row in selects_nothing["area-PINV"]["Verdicts"] if row["Item"] != "PINV-1"] + [
            verdict("PINV-1", "none", "not applicable", "It does not apply.")]
        return selects_nothing, selects

    def test_replicas_that_disagree_whether_an_item_selects_anything_leave_the_rows_of_those_that_judged_what_it_selects(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        selects_nothing, selects = self.disagreeing()
        wanted = {(row["Item"], row["Net or part"]) for row in merged(self.folder, selects)["tables"]["Verdicts"]["rows"]}
        for name, replicas in (("none first", {"r1": selects_nothing["area-PINV"], "r2": selects["area-PINV"]}),
                               ("none second", {"r1": selects["area-PINV"], "r2": selects_nothing["area-PINV"]})):
            with self.subTest(order=name):
                out = merged(self.folder, selects, replicas={"area-PINV": replicas})["tables"]["Verdicts"]["rows"]
                self.assertEqual({(row["Item"], row["Net or part"]) for row in out}, wanted | {("PINV-1", "none")})
                self.assertEqual(len(out), len(wanted) + 1, "the merged record still holds the none row, for the replica that gave it")
                text = rendered(self.folder, selects, replicas={"area-PINV": replicas})["round-1.md"]
                self.assertNotIn("| PINV-1 | none |", text, "the round rendered holds no none row for an item that selects something")
                self.assertIn("| PINV-1 | /IN |", text)
                self.assertEqual(text, rendered(self.folder, selects)["round-1.md"], "the round is the one the replica that judged gives")

    def test_replicas_that_disagree_still_have_every_other_merge_check_applied_to_the_rows_that_stand(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        selects_nothing, selects = self.disagreeing()
        left_out = {**selects["area-PINV"], "Verdicts": [row for row in selects["area-PINV"]["Verdicts"]
                                                         if (row["Item"], row["Net or part"]) != ("PINV-1", "/MID")]}
        self.refused(lambda: merged(self.folder, selects, replicas={"area-PINV": {"r1": selects_nothing["area-PINV"], "r2": left_out}}),
                     "1 net appear", "/MID")
        ghost = {**selects["area-PINV"], "Verdicts": selects["area-PINV"]["Verdicts"] + [verdict("PINV-1", "/GHOST")]}
        self.refused(lambda: merged(self.folder, selects, replicas={"area-PINV": {"r1": selects_nothing["area-PINV"], "r2": ghost}}),
                     "/GHOST")
        no_why = {**selects["area-PINV"], "Verdicts": [verdict("PINV-1", "/IN", "pass", "ok", " ")] + selects["area-PINV"]["Verdicts"][1:]}
        self.refused(lambda: merged(self.folder, selects, replicas={"area-PINV": {"r1": selects_nothing["area-PINV"], "r2": no_why}}),
                     "cites nothing under Rests on")

    def test_a_replica_that_gives_none_and_other_rows_in_its_own_answer_is_refused_beside_a_replica_that_agrees_with_neither(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        selects_nothing, selects = self.disagreeing()
        both = {**selects["area-PINV"], "Verdicts": selects["area-PINV"]["Verdicts"] + [verdict("PINV-1", "none", "not applicable", "No pin.")]}
        for name, replicas in (("alone", {"r1": both}), ("beside an agreeing replica", {"r1": selects["area-PINV"], "r2": both}),
                               ("beside one that says none", {"r1": selects_nothing["area-PINV"], "r2": both}),
                               ("first of two", {"r1": both, "r2": selects_nothing["area-PINV"]})):
            with self.subTest(replicas=name):
                self.refused(lambda: merged(self.folder, selects, replicas={"area-PINV": replicas}), "item PINV-1 has a `none` row")

    def test_a_none_row_whose_replicas_own_real_rows_all_lost_to_another_replicas_verdicts_gives_way_as_the_merged_table_cannot_show_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        selects_nothing, selects = self.disagreeing()
        failing = results()
        failing["area-PINV"]["Verdicts"] = [row if (row["Item"], row["Net or part"]) != ("PINV-1", "/IN") else
                                            verdict("PINV-1", "/IN", "fail", "finding 1.1") for row in failing["area-PINV"]["Verdicts"]]
        failing["area-PINV"]["Findings"] = [finding(1, "PINV-1", "sheet board, net /IN: a pin above its rating")]
        both = {**selects["area-PINV"], "Verdicts": [row for row in selects["area-PINV"]["Verdicts"] if row["Item"] != "PINV-1"] + [
            verdict("PINV-1", "/IN", "pass", "ok"), verdict("PINV-1", "none", "not applicable", "No pin.")]}
        out = merged(self.folder, selects, replicas={"area-PINV": {"r1": failing["area-PINV"], "r2": both}})["tables"]["Verdicts"]["rows"]
        by_pair = {(row["Item"], row["Net or part"]): row["Verdict"] for row in out}
        self.assertEqual(by_pair[("PINV-1", "/IN")], "fail", "the other replica's verdict stands for the pair")
        text = rendered(self.folder, selects, replicas={"area-PINV": {"r1": failing["area-PINV"], "r2": both}})["round-1.md"]
        self.assertNotIn("| PINV-1 | none |", text, "the round is accepted without the none row, which the merged table cannot attribute")

    def test_an_item_every_replica_says_selects_nothing_keeps_its_none_row(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        selects = results()
        out = merged(self.folder, selects, replicas={"area-STRAP": {"r1": selects["area-STRAP"], "r2": selects["area-STRAP"]}})
        rows = [row for row in out["tables"]["Verdicts"]["rows"] if row["Item"] == "STRAP-1"]
        self.assertEqual([(row["Item"], row["Net or part"]) for row in rows], [("STRAP-1", "none")])
        self.assertIn("| STRAP-1 | none |", rendered(self.folder, selects,
                                                    replicas={"area-STRAP": {"r1": selects["area-STRAP"], "r2": selects["area-STRAP"]}})["round-1.md"])

    def test_a_checks_run_before_the_declaration_was_resolved_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        caller.ROUND.clear()
        self.assertIn("before its declaration was resolved", caller.checks({"Verdicts": {"rows": []}, "Findings": {"rows": []}})[0])


class TheEarlierRounds(Folder):
    number = 2

    def test_a_fail_may_cite_an_earlier_rounds_finding_and_needs_no_finding_of_this_round(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.assertEqual(sorted(caller.earlier_findings(self.folder)), [("1", 1)])
        self.assertEqual(caller.round_label(self.folder), "2")
        given = results()
        given["area-PINV"]["Verdicts"] = [verdict("PINV-1", "/IN", "fail", "finding 1.1, closed by a reason")] + [
            row for row in given["area-PINV"]["Verdicts"] if (row["Item"], row["Net or part"]) != ("PINV-1", "/IN")]
        out = merged(self.folder, given)
        self.assertEqual(out["tables"]["Findings"]["rows"], [])
        given["area-PINV"]["Verdicts"][0]["Why"] = "finding 1.7, closed by a reason"
        self.refused(lambda: merged(self.folder, given))
        given["area-PINV"]["Verdicts"][0]["Why"] = "finding 2.1"
        self.refused(lambda: merged(self.folder, given), "the unit did not raise")
        given["area-PINV"]["Verdicts"][0]["Why"] = "finding 2.1"
        given["area-PINV"]["Findings"] = [finding(1, "PINV-1")]
        out = merged(self.folder, given)["tables"]
        self.assertEqual(out["Verdicts"]["rows"][0]["Why"], "finding 2.1")

    def test_the_rendered_later_round_is_headed_with_its_number_and_the_findings_are_numbered_with_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-PINV"]["Verdicts"] = [verdict("PINV-1", "/IN", "fail", "finding 2.1")] + [
            row for row in given["area-PINV"]["Verdicts"] if (row["Item"], row["Net or part"]) != ("PINV-1", "/IN")]
        given["area-PINV"]["Findings"] = [finding(1, "PINV-1")]
        files = rendered(self.folder, given)
        self.assertEqual(list(files), ["round-2.md"])
        text = files["round-2.md"]
        self.assertTrue(text.startswith("## Round 2\n"))
        self.assertIn("| 2.1 | PINV-1 | function |", text)
        self.assertIn("finding 2.1", text)


class TheGuards(Folder):
    """A producer that omits, skips, duplicates or substitutes is refused on every path an answer takes: the first answer, a
    repair turn, the turn about its cannot judge rows, a re-run and the merge of replicas."""

    UNIT = "area-PINV"
    #: What another replica that judged the item makes no defect of the round: the pair or item has its row from the other.
    MASKED_BY_A_REPLICA = ("leaves a net out of the rows of the item that selects every net", "gives a pair no reason where it needs one",
                           "gives a pass no Rests on")

    @staticmethod
    def defects():
        def omit(tables):
            return {**tables, "Verdicts": [row for row in tables["Verdicts"] if row["Item"] != "PINV-2"]}

        def twice(tables):
            return {**tables, "Verdicts": tables["Verdicts"] + [verdict("PINV-1", "/IN", "pass", "Again.")]}

        def substitute(tables):
            return {**tables, "Verdicts": [row for row in tables["Verdicts"] if row["Item"] != "PINV-2"] + [verdict("STRAP-1", "none")]}

        def off_checklist(tables):
            return {**tables, "Verdicts": tables["Verdicts"] + [verdict("MISC-7", "none")]}

        def outside_the_set(tables):
            return {**tables, "Verdicts": [verdict("PINV-1", "/IN", "maybe")] + tables["Verdicts"][1:]}

        def net_left_out(tables):
            return {**tables, "Verdicts": [row for row in tables["Verdicts"] if (row["Item"], row["Net or part"]) != ("PINV-1", "GND")]}

        def ghost(tables):
            return {**tables, "Verdicts": tables["Verdicts"] + [verdict("PINV-1", "/GHOST")]}

        def none_and_more(tables):
            return {**tables, "Verdicts": tables["Verdicts"] + [verdict("PINV-1", "none", "not applicable", "No pin.")]}

        def fail_without_finding(tables):
            return {**tables, "Verdicts": [verdict("PINV-1", "/IN", "fail", "Too high.")] + tables["Verdicts"][1:]}

        def finding_for_a_pass(tables):
            return {**tables, "Findings": [finding(1, "PINV-2")]}

        def finding_of_another_item(tables):
            return {"Verdicts": [verdict("PINV-1", "/IN", "fail", "finding 1.2")] + tables["Verdicts"][1:-1]
                    + [verdict("PINV-2", "none", "fail", "finding 1.1")],
                    "Findings": [finding(1, "PINV-1"), finding(2, "PINV-2")]}

        def cannot_judge_held(tables):
            return {**tables, "Verdicts": tables["Verdicts"][:-1] + [verdict("PINV-2", "none", "cannot judge", "needs the datasheet: none")]}

        def no_reason(tables):
            return {**tables, "Verdicts": tables["Verdicts"][:-1] + [verdict("PINV-2", "none", "not applicable", " ")]}

        def no_rests_on(tables):
            return {**tables, "Verdicts": [verdict("PINV-1", "/IN", "pass", "ok", " ")] + tables["Verdicts"][1:]}

        def empty_finding(tables):
            return {"Verdicts": [verdict("PINV-1", "/IN", "fail", "finding 1.1")] + tables["Verdicts"][1:],
                    "Findings": [finding(1, "PINV-1", "")]}

        def wrong_raised_by(tables):
            return {"Verdicts": [verdict("PINV-1", "/IN", "fail", "finding 1.1")] + tables["Verdicts"][1:],
                    "Findings": [finding(1, "PINV-1", raised="PINV-2")]}

        def closed_by_reviewer(tables):
            return {"Verdicts": [verdict("PINV-1", "/IN", "fail", "finding 1.1")] + tables["Verdicts"][1:],
                    "Findings": [finding(1, "PINV-1", closed="met: fine")]}

        def odd_severity(tables):
            return {"Verdicts": [verdict("PINV-1", "/IN", "fail", "finding 1.1")] + tables["Verdicts"][1:],
                    "Findings": [finding(1, "PINV-1", severity="major")]}
        return {"omits an item": omit, "gives a pair twice": twice, "substitutes another unit's item": substitute,
                "gives a row for an item off the checklist": off_checklist, "gives a verdict outside the set": outside_the_set,
                "leaves a net out of the rows of the item that selects every net": net_left_out, "names a net that does not exist": ghost,
                "gives an item a none row and another": none_and_more, "fails without a finding": fail_without_finding,
                "raises a finding for an item that passes": finding_for_a_pass, "cites another item's finding": finding_of_another_item,
                "leaves a cannot judge": cannot_judge_held, "gives a pair no reason where it needs one": no_reason,
                "gives a pass no Rests on": no_rests_on, "raises an empty finding": empty_finding,
                "writes a Raised by that is not its item": wrong_raised_by, "writes a Closed by": closed_by_reviewer,
                "gives a severity outside the four": odd_severity}

    def others(self):
        return {unit: tables for unit, tables in results().items() if unit != self.UNIT}

    def assess(self, package, tables):
        return kit_results.assess({"tables": tables}, "", package.declaration.shape, self.UNIT,
                                  list(package.declaration.units[self.UNIT].items), "1")

    def causes(self, package, attempt, others=None, replicas=False):
        """Why the run is refused for the answer that stands: the problems the kit holds against the attempt, which fail its unit
        when it still stands, and the causes the merge refuses the round for."""
        found = [problem.line() for problem in attempt.problems]
        if attempt.tables is not None:
            units = {unit: {"r1": tables} for unit, tables in (others or self.others()).items()}
            units[self.UNIT] = {"r1": results()[self.UNIT], "r2": attempt.tables} if replicas else {"r1": attempt.tables}
            try:
                package.merge([self.UNIT] + list(others or self.others()), units)
            except merge.Refused as error:
                found += error.causes
        return found

    def drive(self, defects, masked):
        """Every defect refused on the first answer, a repair, the cannot judge turn, a re-run and the merge of replicas."""
        package = prepared(self.folder)
        last = package.declaration.units[self.UNIT].items[-1]
        for name, make in defects.items():
            bad = make(results()[self.UNIT])
            with self.subTest(defect=name):
                first = self.assess(package, bad)
                self.assertTrue(self.causes(package, first), f"first answer: {name}")
                record = kit_results.UnitRecord(self.UNIT)
                record.add(self.assess(package, bad))
                record.add(self.assess(package, bad))
                self.assertTrue(self.causes(package, record.standing), f"repair turn: {name}")
                turn = kit_results.UnitRecord(self.UNIT)
                held = self.assess(package, {**results()[self.UNIT], "Verdicts": results()[self.UNIT]["Verdicts"][:-1] + [
                    verdict(last, "none", "cannot judge", "needs the datasheet: none")]})
                held.judge_asked = True
                turn.add(held)
                turn.add(self.assess(package, bad))
                self.assertTrue(self.causes(package, turn.standing), f"cannot judge turn: {name}")
                again = prepared(self.folder)
                self.assertTrue(self.causes(again, self.assess(again, bad)), f"rerun: {name}")
                if name in masked:
                    continue
                self.assertTrue(self.causes(package, self.assess(package, bad), replicas=True), f"replica merge: {name}")

    def test_every_defect_is_refused_on_the_first_answer_a_repair_the_cannot_judge_turn_a_rerun_and_the_replica_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.drive(self.defects(), self.MASKED_BY_A_REPLICA)

    @staticmethod
    def free_pass_defects():
        def no_rests_on(tables):
            return {**tables, "Verdicts": [verdict("FREE-PASS", "none", "pass", "ok", " ")]}

        def fail_no_rests_on(tables):
            return {"Verdicts": [verdict("FREE-PASS", "none", "fail", "finding 1.1", "")], "Findings": [finding(1, "FREE-PASS")]}

        def not_applicable_no_why(tables):
            return {**tables, "Verdicts": [verdict("FREE-PASS", "none", "not applicable", "", "sheet board")]}

        def fail_no_why(tables):
            return {"Verdicts": [verdict("FREE-PASS", "none", "fail", " ", "sheet board")], "Findings": [finding(1, "FREE-PASS")]}
        return {"gives the free pass a pass no Rests on": no_rests_on, "gives the free pass a fail no Rests on": fail_no_rests_on,
                "gives the free pass a not applicable no Why": not_applicable_no_why, "gives the free pass a fail no Why": fail_no_why}

    def test_the_free_pass_is_held_to_rests_on_and_why_on_every_path_an_answer_takes(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.UNIT = "free-pass"
        self.drive(self.free_pass_defects(), ("gives the free pass a pass no Rests on", "gives the free pass a not applicable no Why"))

    def test_a_pair_one_replica_left_out_or_gave_no_reason_is_covered_by_the_replica_that_gave_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        package = prepared(self.folder)
        for name in self.MASKED_BY_A_REPLICA:
            with self.subTest(defect=name):
                bad = self.assess(package, self.defects()[name](results()[self.UNIT]))
                own = {problem.line() for problem in bad.problems}
                self.assertEqual([cause for cause in self.causes(package, bad, replicas=True) if cause not in own], [],
                                 "the other replica's rows leave nothing for the merge to refuse")
        bad = self.defects()["leaves a net out of the rows of the item that selects every net"](results()[self.UNIT])
        units = {unit: {"r1": tables} for unit, tables in self.others().items()}
        units[self.UNIT] = {"r1": results()[self.UNIT], "r2": bad}
        rows = package.merge([self.UNIT] + list(self.others()), units)["tables"]["Verdicts"]["rows"]
        self.assertIn(("PINV-1", "GND"), {(row["Item"], row["Net or part"]) for row in rows})

    def test_a_round_whose_every_answer_is_good_is_refused_on_none_of_those_paths(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        package = prepared(self.folder)
        good = self.assess(package, results()[self.UNIT])
        self.assertEqual(self.causes(package, good), [])
        self.assertEqual(self.causes(package, good, replicas=True), [])

    def test_a_repair_that_passes_a_fail_never_clears_it_on_the_first_answer_the_repair_or_the_cannot_judge_turn(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        package = prepared(self.folder)
        shape, items = package.declaration.shape, list(package.declaration.units[self.UNIT].items)
        base = results()[self.UNIT]["Verdicts"]
        failed = {"Verdicts": [verdict("PINV-1", "/IN", "fail", "finding 1.1")] + base[1:], "Findings": [finding(1, "PINV-1")]}
        for name, later in (("passes it", results()[self.UNIT]),
                            ("leaves it out", {"Verdicts": base[1:], "Findings": []}),
                            ("gives it not applicable", {"Verdicts": [verdict("PINV-1", "/IN", "not applicable", "No pin.")] + base[1:],
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
                    self.assertEqual(second.cleared, ["[\"PINV-1\", \"/IN\"]"], turn)
                    verdicts = {(row["Item"], row["Net or part"]): row["Verdict"] for row in record.standing.tables["Verdicts"]}
                    self.assertEqual(verdicts[("PINV-1", "/IN")], "fail", f"the {turn} did not clear the fail")
                    out = package.merge([self.UNIT] + list(self.others()), {**{unit: {"r1": tables} for unit, tables in self.others().items()},
                                                                         self.UNIT: {"r1": record.standing.tables}})
                    self.assertIn("fail", [row["Verdict"] for row in out["tables"]["Verdicts"]["rows"]])

    def test_the_rendered_file_name_is_held_to_an_allow_list_of_the_round_number_alone(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.assertEqual(list(caller.render(self.folder, merge.plain_tables(merged(self.folder, results())))), ["round-1.md"])
        for number in (0, -1, True, "1", 1.5, None, "../x", 10 ** 30):
            with self.subTest(number=number):
                good = sfx.round_file(self.folder)
                sfx.write(self.path("round.json"), json.dumps({**good, "number": number}))
                if isinstance(number, int) and not isinstance(number, bool) and number > 0:
                    self.assertEqual(list(caller.render(self.folder, merge.plain_tables(merged(self.folder, results())))),
                                     [f"round-{number}.md"])
                else:
                    with self.assertRaises(merge.Refused):
                        caller.render(self.folder, merge.plain_tables(merged(self.folder, results())))
        self.assertTrue(caller.RENDERED.fullmatch("round-12.md"))
        for name in ("round-0.md", "round-01.md", "Round-1.md", "round-1.txt", "round-1.md/x", "../round-1.md", "round-.md", "round-1.md "):
            self.assertFalse(caller.RENDERED.fullmatch(name), name)
        self.assertTrue(kit_caller.rendered_name_ok("round-1.md"))


class TheRenderedRound(Folder):
    def row_of(self, text, item, cell):
        line = next(line for line in text.splitlines() if line.startswith(f"| {item} | {cell} |"))
        return [part.strip() for part in line.strip("|").split("|")]

    def test_the_merged_round_is_the_methods_record_with_its_opening_fields_a_verdicts_table_and_a_findings_table(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-PINV"]["Verdicts"] = [verdict("PINV-1", "/IN", "fail", "finding 1.1")] + [
            row for row in given["area-PINV"]["Verdicts"] if (row["Item"], row["Net or part"]) != ("PINV-1", "/IN")]
        given["area-PINV"]["Findings"] = [finding(1, "PINV-1")]
        given["free-pass"] = {"Verdicts": [verdict("FREE-PASS", "none", "fail", "finding 1.1")],
                              "Findings": [finding(1, "FREE-PASS", "sheet Power: crowded", "cosmetic")]}
        text = rendered(self.folder, given)["round-1.md"]
        head = text.split("### Verdicts")[0]
        self.assertTrue(text.startswith("## Round 1\n"))
        self.assertIn(f"- **Schematic judged**: {sfx.round_file(self.folder)['commit']}", head)
        self.assertIn(f"```\n{sfx.NETLIST_COMMAND}\n```", head)
        self.assertIn("  - hardware/synth/board/separation-basis.yaml (accepted_on 2026-10-18)", head)
        self.assertIn("  - hardware/synth/board/constraints.md\n", head)
        self.assertIn("| Item | Net or part | Verdict | Rests on | Why |", text)
        self.assertIn("| Finding | Raised by | Severity | What and where | Closed by |", text)
        self.assertNotIn("FREE-PASS", text.split("### Findings")[0], "the free pass has no row in the verdicts table")
        self.assertIn("| 1.1 | PINV-1 | function |", text)
        self.assertIn("| 1.2 | free pass | cosmetic |", text)
        self.assertNotIn("| Item |", text.split("### Findings")[1], "the findings table carries no Item column")
        verdicts = text.split("### Verdicts")[1].split("### Findings")[0]
        order = [re.match(r"\| (\S+) \| (\S+)", line).groups() for line in verdicts.splitlines() if line.startswith("| ")][2:]
        items = [item for item, _ in order]
        self.assertEqual(items, sorted(items, key=["PINV-1", "PINV-2", "STRAP-1", "DERATE-1", "DERATE-2"].index),
                         "rows are in the checklist order")

    def test_a_round_with_no_finding_says_so_in_the_methods_words(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        text = rendered(self.folder, results())["round-1.md"]
        self.assertTrue(text.rstrip().endswith("### Findings\n\nThis round raises no finding."))

    def test_the_rendered_round_is_read_by_the_layout_review_histories_round_reader(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-PINV"]["Verdicts"] = [verdict("PINV-1", "/IN", "fail", "finding 1.1")] + [
            row for row in given["area-PINV"]["Verdicts"] if (row["Item"], row["Net or part"]) != ("PINV-1", "/IN")]
        given["area-PINV"]["Findings"] = [finding(1, "PINV-1")]
        text = rendered(self.folder, given)["round-1.md"]
        parsed = board_review_history.Round(board_review_history.round_bodies(text)[1])
        header, rows = parsed.findings
        self.assertEqual(header, ["Finding", "Raised by", "Severity", "What and where", "Closed by"])
        self.assertEqual([row[0] for row in rows], ["1.1"])
        header, rows = parsed.verdicts
        self.assertEqual(header, caller.VERDICT_TABLE)
        self.assertEqual(len(rows), 12)
        self.assertEqual(caller.earlier_findings(self.folder), [])
        sfx.write(self.path(f"{sfx.DESIGN}/schematic-review.md"), "## Round 1\n\n" + text.split("## Round 1\n")[1])
        self.assertEqual(caller.earlier_findings(self.folder), [("1", 1)])

    def test_a_resolved_cannot_judge_is_one_row_recording_cannot_judge_then_the_verdict_with_the_file_added_in_rests_on(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.add_document(item="STRAP-1", target="U1")
        given = results()
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "U1", "pass", "Strap is high.", "datasheet SLVS165O p.4"),
                                           verdict("STRAP-1", "R1", "not applicable", "Not a strap.", "sheet board")]
        text = rendered(self.folder, given)["round-1.md"]
        row = self.row_of(text, "STRAP-1", "U1")
        self.assertEqual(row[2], "cannot judge, then pass")
        self.assertEqual(row[3], "datasheet SLVS165O p.4; `added-documents/u1-strap.txt`")
        self.assertTrue(row[4].startswith("Cannot judge: needs the datasheet of U1: the strap levels are not in the folder."))
        self.assertTrue(row[4].endswith("Strap is high."))
        self.assertEqual(self.row_of(text, "STRAP-1", "R1")[2], "not applicable", "a row the cannot judge was not about is untouched")

    def test_a_resolved_cannot_judge_without_a_target_marks_every_row_of_the_item_and_a_view_is_recorded_too(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.add_view(item="DERATE-2")
        given = results()
        text = rendered(self.folder, given)["round-1.md"]
        for sheet in sfx.SHEETS:
            row = self.row_of(text, "DERATE-2", sheet)
            self.assertEqual(row[2], "cannot judge, then pass")
            self.assertIn("`added-views/power-large.svg`", row[3])
        self.assertEqual(self.row_of(text, "DERATE-1", "R1")[2], "pass")

    def test_two_files_added_for_one_pair_are_both_recorded_in_the_order_they_were_added(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.add_view(item="STRAP-1", target="U1")
        self.add_document(item="STRAP-1", target="U1")
        given = results()
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "U1", "pass", "ok", "sheet board")]
        row = self.row_of(rendered(self.folder, given)["round-1.md"], "STRAP-1", "U1")
        self.assertEqual(row[3], "sheet board; `added-views/power-large.svg`; `added-documents/u1-strap.txt`")
        self.assertEqual(row[4].count("Cannot judge:"), 2)

    def test_a_vertical_bar_or_line_break_in_a_table_cell_is_escaped_and_the_reader_keeps_the_shape(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        given["area-STRAP"]["Verdicts"] = [verdict("STRAP-1", "U1", "pass", "a | b\nc", "sheet | board")]
        text = rendered(self.folder, given)["round-1.md"]
        parsed = board_review_history.Round(board_review_history.round_bodies(text)[1])
        header, rows = parsed.verdicts
        self.assertTrue(all(len(row) == len(header) for row in rows))

    def test_the_render_sorts_rows_by_the_checklist_and_then_the_cell_whatever_order_the_units_returned_them_in(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        given = results()
        shuffled = {unit: {"Verdicts": list(reversed(tables["Verdicts"])), "Findings": tables["Findings"]} for unit, tables in given.items()}
        self.assertEqual(rendered(self.folder, given), rendered(self.folder, shuffled))
        text = rendered(self.folder, given)["round-1.md"]
        cells = [line.split("|")[2].strip() for line in text.splitlines() if line.startswith("| PINV-1 ")]
        self.assertEqual(cells, sorted(sfx.NETS))

    def test_a_round_file_that_cannot_be_read_when_the_round_is_rendered_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        os.remove(self.path("round.json"))
        with self.assertRaises(merge.Refused) as caught:
            caller.render(self.folder, {"Verdicts": {"rows": []}, "Findings": {"rows": []}})
        self.assertIn("round file", str(caught.exception))


class Command:
    """The kit's command run on a review folder with the schematic caller, the stub playing the agent command line."""

    def __init__(self, case: Folder, folder: str = None, out: str = "out"):
        self.case, self.folder = case, folder or case.folder
        self.out = os.path.join(case.root, out)
        self.log = os.path.join(case.root, "agent.log")
        self.scenario_path = os.path.join(case.root, "scenario.json")
        self.program = os.path.join(case.root, "agent")
        sfx.write(self.program, STUB.replace("PYTHON", sys.executable, 1).replace("TOOLS", repr(TOOLS)))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        patcher = mock.patch.dict(os.environ, {ex.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path, "STUB_LOG": self.log})
        patcher.start()
        case.addCleanup(patcher.stop)

    def scenario(self, **values):
        values.setdefault("pairs", {item: list(cells) for item, cells in SELECTS.items()})
        sfx.write(self.scenario_path, json.dumps(values))

    def go(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        status = command.main(["--caller", "schematic", "--callers", TOOLS, "--review", self.folder, "--out", self.out]
                              + list(extra), out, err, repo=os.path.join(self.case.root, "no-repository"))
        return status, out.getvalue(), err.getvalue()

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


class TheCommandEndToEnd(Folder):
    def test_the_command_writes_the_round_as_text_and_as_json_and_the_reader_reads_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        run = Command(self)
        run.scenario(verdicts={"STRAP-1": "fail"}, pairs={**{item: list(cells) for item, cells in SELECTS.items()}, "STRAP-1": ["U1"]})
        status, text, err = run.go("--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        report = json.loads(text)
        self.assertEqual(report["rendered"], ["round-1.md"])
        written = slurp(os.path.join(run.out, "round-1.md"))
        self.assertTrue(written.startswith("## Round 1\n"))
        parsed = board_review_history.Round(board_review_history.round_bodies(written)[1])
        self.assertEqual(len(parsed.findings[1]), 1, "the two replicas' findings, the same in every cell, are one finding")
        self.assertEqual({(row["Item"], row["Net or part"]) for row in report["tables"]["Verdicts"]["rows"]
                          if row["Verdict"] == "fail"}, {("STRAP-1", "U1")})
        second = Command(self)
        second.out = os.path.join(self.root, "out-text")
        status, text, err = second.go("--model", SMALL)
        self.assertEqual(status, 0, text + err)
        self.assertIn("RENDERED | round-1.md", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | WRITTEN"))

    def test_a_round_file_with_a_missing_field_or_another_reviews_is_refused_before_any_session_starts(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        sfx.set_round(self.folder, netlist=None, records=[])
        run = Command(self)
        run.scenario()
        status, text, _ = run.go("--format", "json")
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        joined = "; ".join(report["refusals"])
        self.assertIn("the netlist command is None", joined)
        self.assertIn("the records read are []", joined)
        self.assertEqual(run.calls(), [], "no session was started")
        self.assertFalse(os.path.exists(run.out))
        other = sfx.write_review_folder(os.path.join(self.root, "other"))
        sfx.write(os.path.join(other, "round.json"), json.dumps({"tool": "review-folder", "fields": ["number", "commit", "views"],
                                                                 "number": 1, "commit": "a" * 40, "views": ["v"]}))
        run2 = Command(self, folder=other, out="out-other")
        run2.scenario()
        status, text, _ = run2.go("--format", "json")
        self.assertEqual(status, 1, text)
        self.assertIn("not a schematic review's", "; ".join(json.loads(text)["refusals"]))
        self.assertEqual(run2.calls(), [])

    def test_a_merge_that_fails_names_the_item_and_keeps_the_units_results(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        run = Command(self)
        run.scenario(verdicts={"STRAP-1": "cannot judge"}, why={"STRAP-1": "needs the datasheet of U1: no strap table"})
        status, text, _ = run.go("--format", "json", "--model", SMALL)
        report = json.loads(text)
        self.assertEqual(status, 1, text)
        joined = "; ".join(report["refusals"])
        self.assertIn("item STRAP-1 on none is still cannot judge", joined)
        self.assertIn("asks for the datasheet of U1", joined)
        self.assertIn("unit area-STRAP", joined)
        self.assertFalse(os.path.exists(os.path.join(run.out, "round-1.md")), "nothing is rendered from a refused merge")
        self.assertTrue(os.path.exists(os.path.join(run.out, "record.json")), "the units' results are kept")

    def test_a_cannot_judge_is_resolved_by_adding_the_file_and_running_that_unit_again_and_the_row_records_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It also fails a row for an item not on the checklist, a net, part or sheet in no item's rows, a free-pass row that is not none, a none row beside other rows of the same item raised by one and the same replica, a pass or fail with empty Rests on, a not applicable or fail with empty Why, a fail citing no finding of its own item or valid earlier-round finding or citing another item's finding, a finding for an item that does not fail, a finding whose Raised by is not its item or `free pass`, a severity outside safety, function, quality and cosmetic, a non-empty Closed by, an empty What and where, and a recorded cannot judge for an unknown item or a pair with no row. The caller refuses before any session starts a round file that is not a schematic one, a netlist whose parts or sheets differ from the schematic's, a missing netlist, method-extract section, drawing, check report or schematic, and a catalogue area with no item; the rendered round file is named round-<n>.md. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. When replicas disagree whether an item selects anything, the rows of the replica that judged what it selects stand and the none row gives way, as does the none row of a replica whose own real rows lost to another replica's verdicts for the same pair. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        run = Command(self)
        run.scenario(verdicts={"STRAP-1|U1": "cannot judge"}, pairs={**{i: list(c) for i, c in SELECTS.items()}, "STRAP-1": ["U1"]},
                     why={"STRAP-1": "needs the datasheet of U1: no strap table"})
        self.assertEqual(run.go("--format", "json", "--model", SMALL)[0], 1)
        before = {path: slurp(self.path(path)) for path in ("round.json", "method-extract.md", "review.net")}
        self.add_document(item="STRAP-1", target="U1", why="needs the datasheet of U1: no strap table")
        self.assertEqual(before, {path: slurp(self.path(path)) for path in before}, "no shared-context file changed")
        calls_before = len(run.calls())
        run.scenario(verdicts={"STRAP-1|U1": "pass"}, pairs={**{i: list(c) for i, c in SELECTS.items()}, "STRAP-1": ["U1"]})
        status, text, err = run.go("--rerun", "area-STRAP", "--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        written = slurp(os.path.join(run.out, "round-1.md"))
        row = next(line for line in written.splitlines() if line.startswith("| STRAP-1 | U1 |"))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        self.assertEqual(cells[2], "cannot judge, then pass")
        self.assertIn("`added-documents/u1-strap.txt`", cells[3])
        again = run.calls()[calls_before:]
        forks = [call for call in again if call["resume"] is not None]
        self.assertEqual(len(again) - len(forks), 1, "one shared context, started again for the run")
        self.assertEqual(json.loads(text)["reran"][0]["units"], ["area-STRAP"])
        self.assertTrue(all("u1-strap.txt" in call["prompt"] and "(about U1)" in call["prompt"] for call in forks),
                        "the unit run again is told which file was added for which pair")


class TheToolGrant(Folder):
    def test_the_caller_grants_the_read_tools_and_the_one_retrieval_tool_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C7: Over synthetic declarations and a stub executor, the schematic declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        package = prepared(self.folder)
        self.assertEqual(package.tools, ("Read", "Glob", "Grep", "WebFetch"))
        self.assertIs(caller.retrieval, True)
        spec = messages.make_spec(package.declaration, package.tools, self.folder, SMALL)
        self.assertEqual(spec.expected_tools, sorted(["Read", "Glob", "Grep", "WebFetch", "StructuredOutput"]))
        loaded = kit_caller.load("schematic", TOOLS)
        self.assertEqual(kit_caller.attribute_problems(loaded), [])
        self.assertEqual(kit_caller.granted_tools(loaded), ("Read", "Glob", "Grep", "WebFetch"))
        for tool in ("Bash", "Write", "Edit", "Task", "NotebookEdit"):
            self.assertNotIn(tool, package.tools)

    def test_every_reviewer_is_started_with_the_four_tools_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C3: Against the kit's stub, every reviewer of the schematic caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a datasheet can be retrieved, which the proof run records.
        run = Command(self)
        run.scenario()
        status, text, err = run.go("--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text + err)
        calls = run.calls()
        forks = [call for call in calls if call["resume"] is not None]
        self.assertGreaterEqual(len(forks), 2)
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
        self.assertTrue(named and all(units for units, _, _ in named), "every reviewer that started badly is named with its units")
        self.assertTrue(any("area-PINV" in units for units, _, _ in named))
        for line in lines:
            self.assertRegex(line, r"session G\d\.r\d\.a1 started")
        return lines[0]

    def test_a_session_that_reports_a_different_tool_set_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C3: Against the kit's stub, every reviewer of the schematic caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a datasheet can be retrieved, which the proof run records.
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "WebFetch", "Bash", "StructuredOutput"])
        self.assertIn("started with tools", line)
        self.assertIn("Bash", line)
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "StructuredOutput"])
        self.assertIn("WebFetch", line, "a reviewer that lost the retrieval tool is refused too")
        line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "WebFetch", "Write", "Edit", "StructuredOutput"])
        self.assertIn("Write", line)

    def test_the_kits_check_of_the_start_report_against_the_grant_fails_a_reviewer_holding_any_other_tool(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C7: Over synthetic declarations and a stub executor, the schematic declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        for extra in ("Task", "NotebookEdit", "Bash", "WebSearch"):
            with self.subTest(extra=extra):
                line = self.reviewer_refused(fork_tools=["Read", "Glob", "Grep", "WebFetch", extra, "StructuredOutput"])
                self.assertIn("started with tools", line)
                self.assertIn(extra, line)

    def test_a_session_that_reports_an_mcp_server_or_another_working_directory_fails_naming_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C3: Against the kit's stub, every reviewer of the schematic caller is started with the read tools and the one retrieval tool and no other, and a run whose session reports a different tool set, any MCP server or another working directory fails naming the unit. Out of scope: whether a datasheet can be retrieved, which the proof run records.
        line = self.reviewer_refused(fork_mcp=True)
        self.assertIn("MCP servers", line)
        line = self.reviewer_refused(fork_cwd=os.path.join(self.root, "elsewhere"))
        self.assertIn("started in", line)
        self.assertIn(self.folder, line, "the folder its specification names")


class TheReplicasBudgetAndBound(Folder):
    def test_the_declaration_sets_two_replicas_a_full_and_a_hunt_framing_on_the_small_tier_model(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C7: Over synthetic declarations and a stub executor, the schematic declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        loaded = kit_caller.load("schematic", TOOLS)
        policy = loaded.module.replica_policy
        self.assertEqual([variant["id"] for variant in policy["variants"]], ["full", "hunt"])
        self.assertEqual({variant["model"] for variant in policy["variants"]}, {SMALL})
        self.assertEqual(policy["replicas"], {"low": 1, "normal": 2, "high": 2})
        self.assertEqual(caller.SMALL_MODEL, SMALL)
        self.assertTrue(policy["variants"][1]["terse"])
        self.assertEqual(policy["variants"][1]["item_order"], "reversed")
        run = Command(self)
        run.scenario()
        status, text, _ = run.go("--format", "json", "--model", SMALL)
        self.assertEqual(status, 0, text)
        plan = json.loads(text)["plan"]
        self.assertEqual({group["replicas"] for group in plan["groups"]}, {2})
        self.assertEqual(plan["variants"], ["full", "hunt"])
        forks = [call for call in run.calls() if call["resume"] is not None]
        self.assertTrue(all(model_of(call) == SMALL for call in forks))
        self.assertTrue(any("Hunt for failures" in call["prompt"] for call in forks), "the hunt framing is in a replica's prompt")

    def test_the_time_budget_is_350_seconds_and_the_bound_30(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C7: Over synthetic declarations and a stub executor, the schematic declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
        loaded = kit_caller.load("schematic", TOOLS)
        self.assertEqual(loaded.module.WALL_SECONDS, 350)
        self.assertEqual(loaded.module.bound, 30)
        self.assertEqual(prepared(self.folder).declaration.budget.wall_s, 350)
        self.assertEqual(caller.bound, review_caller_layout.bound)

    def test_a_plan_of_forty_forks_runs_at_most_thirty_at_once_and_a_smaller_plan_all_of_its_forks(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C7: Over synthetic declarations and a stub executor, the schematic declaration grants a reviewer the read tools and the one read-only retrieval tool and no other; sets two replicas, the full and hunt framings, on the small-tier model; sets the time budget at 350 seconds and the bound on reviewers at once at 30; and the kit's check of the start report against the grant fails a run whose reviewer holds any other tool. Out of scope: a live session.
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
        self.assertGreaterEqual(plan["forks"], 40)
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


def model_of(call):
    return call["args"][call["args"].index("--model") + 1]


class Documentation(unittest.TestCase):
    def read(self, *path):
        return slurp(os.path.join(REPO, *path))

    def schematic_section(self):
        method = self.read("docs", "board-design-method.md")
        return review_folder.method_section(method, "Schematic review")

    def test_the_schematic_review_step_says_a_round_may_be_judged_by_unit_what_the_merge_checks_and_that_one_reviewer_stays_valid(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C5: The method's schematic review section says that a round may be judged by unit, what the merge checks including the coverage of every net, part and sheet, and that judging it with one reviewer stays valid; its list of what the circuit review's proof folder holds names the sheet drawings; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the circuit review proof's fanned-out run and the task runner's description says what the command needs. Checked by reading each place against these clauses. Out of scope: the layout and ordering sections.
        section = " ".join(self.schematic_section().split())
        for words in ("may be judged by unit", "one reviewer for each area of the circuit practice catalogue and one for the free pass",
                      "task hw:schematic-review-folder", "task hw:review-run -- --caller schematic",
                      "the coverage of every net, part and sheet", "appears in no item's rows", "names something that does not exist",
                      "`cannot judge, then <verdict>`", "--add-document", "--add-view", "--cannot-judge-target"):
            self.assertIn(words, section)
        self.assertRegex(section, r"Judging a round with one reviewer[^.]*stays valid")

    def test_the_method_lists_every_refusal_the_folder_command_and_the_merge_enforce(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C5: The method's schematic review section says that a round may be judged by unit, what the merge checks including the coverage of every net, part and sheet, and that judging it with one reviewer stays valid; its list of what the circuit review's proof folder holds names the sheet drawings; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the circuit review proof's fanned-out run and the task runner's description says what the command needs. Checked by reading each place against these clauses. Out of scope: the layout and ordering sections.
        section = " ".join(self.schematic_section().split())
        for words in ("a folder inside the repository", "a folder that is not new or empty", "a missing netlist",
                      "a netlist whose parts or sheets differ from the committed schematic's", "a sheet with no drawing",
                      "a missing check report", "a record that is not a Markdown or YAML file", "the schematic review record",
                      "a designer's notes or a session record", "a method lacking a section the review needs",
                      "an item that selects nothing and also selects something", "a pass or fail with nothing under Rests on",
                      "a not applicable or fail with nothing under Why", "a severity outside the catalogue's four",
                      "a Closed by the reviewer wrote", "a finding not raised by its item"):
            self.assertIn(words, section)

    def test_the_method_says_the_fanned_out_form_is_relied_on_only_once_its_proof_is_recorded(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C5: The method's schematic review section says that a round may be judged by unit, what the merge checks including the coverage of every net, part and sheet, and that judging it with one reviewer stays valid; its list of what the circuit review's proof folder holds names the sheet drawings; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the circuit review proof's fanned-out run and the task runner's description says what the command needs. Checked by reading each place against these clauses. Out of scope: the layout and ordering sections.
        section = " ".join(self.schematic_section().split())
        self.assertRegex(section, r"fanned-out form[^.]*is relied on only once its proof is recorded")

    def test_the_proof_folders_list_names_the_sheet_drawings_and_the_sentence_that_a_proof_is_repeated_names_the_form_that_changed(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C5: The method's schematic review section says that a round may be judged by unit, what the merge checks including the coverage of every net, part and sheet, and that judging it with one reviewer stays valid; its list of what the circuit review's proof folder holds names the sheet drawings; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the circuit review proof's fanned-out run and the task runner's description says what the command needs. Checked by reading each place against these clauses. Out of scope: the layout and ordering sections.
        section = " ".join(self.schematic_section().split())
        listing = section.split("with no record of the seeds then follows this section on a review folder holding only")[1].split("It is granted")[0]
        self.assertIn("the drawing of each sheet", listing)
        self.assertIn("its netlist", listing)
        self.assertRegex(section, r"repeated .{0,80}the form that (changed|the step changed)|the form that changed")

    def test_the_hardware_notes_describe_the_proofs_fanned_out_run_and_what_each_command_needs(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C5: The method's schematic review section says that a round may be judged by unit, what the merge checks including the coverage of every net, part and sheet, and that judging it with one reviewer stays valid; its list of what the circuit review's proof folder holds names the sheet drawings; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the circuit review proof's fanned-out run and the task runner's description says what the command needs. Checked by reading each place against these clauses. Out of scope: the layout and ordering sections.
        notes = " ".join(self.read("hardware", "README.md").split())
        section = notes.split("### The schematic review by unit")[1].split("\n###")[0] if "### The schematic review by unit" in notes else notes
        for words in ("task hw:schematic-review-folder", "task hw:schematic-review-proof", "task hw:review-run -- --caller schematic",
                      "--cannot-judge-target", "--add-document", "--add-view", "two small-tier replicas", "1.25",
                      "schematic_single_runs.json", "pin-voltage", "the sheets folder", "a sheet with no drawing"):
            self.assertIn(words, notes)

    def test_the_task_runner_names_the_new_commands_and_the_new_tests_in_both_test_descriptions(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C5: The method's schematic review section says that a round may be judged by unit, what the merge checks including the coverage of every net, part and sheet, and that judging it with one reviewer stays valid; its list of what the circuit review's proof folder holds names the sheet drawings; the sentence that a proof is repeated after the step changes names the form that changed; the hardware notes describe the circuit review proof's fanned-out run and the task runner's description says what the command needs. Checked by reading each place against these clauses. Out of scope: the layout and ordering sections.
        taskfile = self.read("Taskfile.yml")
        for task in ("hw:schematic-review-folder", "hw:schematic-review-proof"):
            self.assertRegex(taskfile, rf"(?m)^  {re.escape(task)}:\n    desc: ")
        folder = re.search(r"(?ms)^  hw:schematic-review-folder:\n    desc: (.*?)\n    # Run", taskfile).group(1)
        for words in ("netlist", "sheet", "check's report", "cannot judge", "--add-view", "--add-document", "Needs git"):
            self.assertIn(words, folder)
        proof = re.search(r"(?ms)^  hw:schematic-review-proof:\n    desc: (.*?)\n    # Run", taskfile).group(1)
        for words in ("--dry", "baseline", "1.25", "two replicas", "seeding session", "KiCad", "spends"):
            self.assertIn(words, proof)
        for task in ("hw:test", "hw:test:round"):
            description = re.search(rf"(?ms)^  {re.escape(task)}:\n    desc: (.*?)\n    dir:", taskfile).group(1)
            for words in ("schematic review's caller", "schematic review folder command", "schematic review proof command"):
                self.assertIn(words, description, task)


if __name__ == "__main__":
    unittest.main()
