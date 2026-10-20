#!/usr/bin/env python3
"""The pre-order check's board rules record, sensing-clearance rule and ground-return rule, driven on synthetic designs with no KiCad involved.

What is under test is everything the rules decide for themselves: how the board
rules record is read, which forms of it fail, which rules the sensing
declaration becomes and in what order, which local clearance overrides fail,
and how a connector's pins are counted against the declared ratio. Each of these
can be wrong while the check still reports a pass, which is the failure worth a
test. The check run against KiCad, the tracked designs and the seeded-fault
proof are in test_board_check_kicad.py.
"""

from __future__ import annotations

import copy
import os
import re
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
DESIGN = board_check.Design("hw/machine/board/board.kicad_pro")
RECORD = "hw/machine/board-rules.yaml"
SOURCE = "none -- a synthetic figure"

SENSING = {"classes": ["Sensing"], "noisy_classes": ["Power", "Mains"], "clearance_mm": 0.5, "source": SOURCE}
GROUND_RETURNS = {"ground_classes": ["Ground"], "non_signal_classes": ["Power", "Supply", "Mains"],
                  "signal_classes": [{"class": "Default", "signal_pins_per_return": 2, "source": SOURCE},
                                     {"class": "Sensing", "signal_pins_per_return": 1, "source": SOURCE}]}
COMPLETE = {"sensing": SENSING, "ground_returns": GROUND_RETURNS, "synthetic": True}


def changed(**edits) -> dict:
    """The complete record with the top-level keys given replaced, a key set to Ellipsis removed."""
    record = copy.deepcopy(COMPLETE)
    for key, value in edits.items():
        if value is Ellipsis:
            del record[key]
        else:
            record[key] = value
    return record


def with_sensing(**edits) -> dict:
    sensing = copy.deepcopy(SENSING)
    for key, value in edits.items():
        if value is Ellipsis:
            del sensing[key]
        else:
            sensing[key] = value
    return changed(sensing=sensing)


def with_returns(**edits) -> dict:
    returns = copy.deepcopy(GROUND_RETURNS)
    for key, value in edits.items():
        if value is Ellipsis:
            del returns[key]
        else:
            returns[key] = value
    return changed(ground_returns=returns)


def with_signal_class(**edits) -> dict:
    """The first signal class of the complete record with the keys given replaced, a key set to Ellipsis removed."""
    entry = copy.deepcopy(GROUND_RETURNS["signal_classes"][0])
    for key, value in edits.items():
        if value is Ellipsis:
            del entry[key]
        else:
            entry[key] = value
    return with_returns(signal_classes=[entry])


class Tree(unittest.TestCase):
    """A synthetic repository holding one design under hw/machine/board/ and the records it is held to."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = self.scratch.name
        self.yaml = board_check.require_yaml()

    def write(self, path: str, text: str) -> None:
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    def repository(self, tracked=True):
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names] if tracked else []
        return board_check.Repository(self.root, files)

    def load(self, record, path: str = RECORD, manufacturable: bool = False, tracked: bool = True):
        """The mapping and violations the reader gives for `record`, a mapping or the text of the file, written at `path`."""
        if record is not None:
            self.write(path, record if isinstance(record, str) else self.yaml.safe_dump(record, sort_keys=False))
        return board_check.load_board_rules(self.yaml, self.root, self.repository(tracked), DESIGN, not manufacturable)

    def problems(self, record, **more):
        return self.load(record, **more)[1]

    def assertFails(self, record, where: str, words: str, **more):
        problems = self.problems(record, **more)
        self.assertTrue([v for v in problems if v.location.endswith(where) and words in v.message],
                        [(v.location, v.message) for v in problems])
        self.assertEqual({v.rule for v in problems}, {"board_rules_record"})
        return problems


class TheBoardRulesRecordIsRead(Tree):
    def test_a_complete_synthetic_record_is_accepted_for_a_design_not_for_manufacture_and_its_mapping_returned(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C3: This leaf extends the check's record reader to accept the board rules record and its sensing and ground_returns keys
        data, problems = self.load(COMPLETE)
        self.assertEqual(problems, [])
        self.assertEqual(data, COMPLETE)

    def test_each_mapping_may_state_none_explicitly(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C5: A design with no connector or sensing class the rule inspects is not failed for that; an explicit none is accepted
        for edits in ({"sensing": "none"}, {"ground_returns": "none"}, {"sensing": "none", "ground_returns": "none"}):
            with self.subTest(edits=edits):
                data, problems = self.load(changed(**edits))
                self.assertEqual(problems, [])
                self.assertIsNotNone(data)

    def test_a_design_whose_folders_hold_no_record_fails_naming_where_one_belongs(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C5: A missing record or declaration the rule needs fails
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C4: A failure of any rule in this leaf is reported with the rule's name, the design, and the offending item
        data, problems = self.load(None)
        self.assertIsNone(data)
        self.assertEqual([(v.design, v.rule, v.location) for v in problems],
                         [("hw/machine/board/board.kicad_pro", "board_rules_record", "hw/machine/board/board-rules.yaml")])
        self.assertIn("no board-rules.yaml in the design's folder or any folder above it", problems[0].message)

    def test_the_record_in_the_nearest_folder_at_or_above_the_design_is_the_one_read(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: A board rules record, board-rules.yaml, found by the nearest-folder rule
        self.write(RECORD, self.yaml.safe_dump(COMPLETE, sort_keys=False))
        near = changed(sensing="none")
        self.assertEqual(self.load(near, path="hw/machine/board/board-rules.yaml")[0], near)

    def test_a_record_silent_on_either_mapping_fails_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: each mapping may state none explicitly; silence fails
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: it may state none explicitly, and a missing mapping fails
        self.assertFails(changed(sensing=...), "board-rules.yaml sensing", "lacks sensing")
        self.assertFails(changed(ground_returns=...), "board-rules.yaml ground_returns", "lacks ground_returns")

    def test_a_record_that_is_not_a_mapping_cannot_be_parsed_and_fails(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C3: This leaf extends the check's record reader to accept the board rules record
        problems = self.problems("- not a mapping\n")
        self.assertEqual([v.rule for v in problems], ["board_rules_record"])
        self.assertIn("not a mapping", problems[0].message)
        self.assertIn("cannot be parsed", self.problems("sensing: [unclosed\n")[0].message)

    def test_a_key_given_twice_or_a_merge_key_fails_because_the_shared_reader_refuses_both(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C3: The rules extend the existing pre-order check and its record reader
        self.assertIn("more than once", self.problems("sensing: none\nsensing: none\nground_returns: none\n")[0].message)
        self.assertIn("merge key", self.problems("base: &b {x: 1}\nsensing: none\nground_returns: none\n<<: *b\n")[0].message)

    def test_a_record_the_repository_does_not_track_fails(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C3: This leaf extends the check's record reader to accept the board rules record
        problems = self.problems(COMPLETE, tracked=False)
        self.assertEqual([v.rule for v in problems], ["board_rules_record"])
        self.assertIn("not tracked", problems[0].message)

    def test_a_synthetic_record_passes_only_a_design_marked_not_for_manufacture(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C6: carrying the records they read, synthetic where the design is not for manufacture
        self.assertFails(COMPLETE, "board-rules.yaml synthetic", "marked synthetic", manufacturable=True)
        self.assertEqual(self.problems(changed(synthetic=False), manufacturable=True), [])
        self.assertFails(changed(synthetic="yes"), "board-rules.yaml synthetic", "where it is true on a board rules record")

    def test_a_key_the_decisions_do_not_define_fails_at_every_depth_naming_it(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C3: the reader still fails a key the decisions do not define
        cases = [
            (dict(COMPLETE, sensng=SENSING), "board-rules.yaml sensng", "holds the key 'sensng'"),
            (with_sensing(clearence_mm=1), "sensing.clearence_mm", "holds the key 'clearence_mm'"),
            (with_returns(ground_class=["Ground"]), "ground_returns.ground_class", "holds the key 'ground_class'"),
            (with_signal_class(signal_pins_per_retun=2), "signal_classes[0].signal_pins_per_retun", "holds the key 'signal_pins_per_retun'"),
        ]
        for record, where, words in cases:
            with self.subTest(where=where):
                self.assertFails(record, where, words)

    def test_the_sensing_mapping_needs_every_key_and_a_usable_value_for_each(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: a sensing mapping of classes, noisy_classes, clearance_mm and source; silence, a clearance without its source, or no figure fails
        for key in ("classes", "noisy_classes", "clearance_mm", "source"):
            with self.subTest(missing=key):
                self.assertFails(with_sensing(**{key: ...}), f"sensing.{key}", f"lacks {key}")
        for figure in (0, -0.5, "0.5", True, None, float("nan")):
            with self.subTest(figure=figure):
                self.assertFails(with_sensing(clearance_mm=figure), "sensing.clearance_mm", "not a positive number")
        for source in ("", "  ", 3, None):
            with self.subTest(source=source):
                self.assertFails(with_sensing(source=source), "sensing.source", "non-empty string")

    def test_the_sensing_classes_are_non_empty_lists_of_names_each_listed_once_and_in_one_list(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: holds a sensing mapping of classes (net classes carrying precision sensing), noisy_classes
        self.assertFails(with_sensing(classes=[]), "sensing.classes", "lists no net classes")
        self.assertFails(with_sensing(noisy_classes="Power"), "sensing.noisy_classes", "not a list")
        self.assertFails(with_sensing(classes=["Sensing", 3]), "sensing.classes[1]", "non-empty string")
        self.assertFails(with_sensing(noisy_classes=["Power", "Power"]), "sensing.noisy_classes", "more than once")
        self.assertFails(with_sensing(noisy_classes=["Sensing", "Power"]), "board-rules.yaml sensing", "both a sensing and a noisy class")

    def test_a_mapping_that_is_neither_a_mapping_nor_the_word_none_fails(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C5: A missing record or declaration the rule needs fails; an explicit none is accepted
        for value in ("None", "nothing", [], 3, True, ""):
            with self.subTest(value=value):
                self.assertFails(changed(sensing=value), "board-rules.yaml sensing", "where it is a mapping or the word none")
                self.assertFails(changed(ground_returns=value), "board-rules.yaml ground_returns", "where it is a mapping or the word none")

    def test_the_ground_return_mapping_needs_all_three_keys_and_an_entry_for_each_signal_class(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: ground_classes, non_signal_classes and signal_classes, a list with one entry per signal net class, each holding class, signal_pins_per_return and source
        for key in ("ground_classes", "non_signal_classes", "signal_classes"):
            with self.subTest(missing=key):
                self.assertFails(with_returns(**{key: ...}), f"ground_returns.{key}", f"lacks {key}")
        for key in ("class", "signal_pins_per_return", "source"):
            with self.subTest(missing=key):
                self.assertFails(with_signal_class(**{key: ...}), f"signal_classes[0].{key}", f"lacks {key}")
        self.assertFails(with_signal_class(source=" "), "signal_classes[0].source", "non-empty string")
        self.assertFails(with_returns(signal_classes=["Default"]), "signal_classes[0]", "not a mapping")

    def test_the_ratio_must_be_a_positive_whole_number(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: a non-positive or non-whole signal_pins_per_return fails
        for figure in (0, -1, 1.5, 2.0, "2", True, None):
            with self.subTest(figure=figure):
                self.assertFails(with_signal_class(signal_pins_per_return=figure), "signal_classes[0].signal_pins_per_return",
                                 "where it is a positive whole number, the most signal pins one ground-return pin may serve")
        self.assertEqual(self.problems(with_signal_class(signal_pins_per_return=1)), [])

    def test_an_empty_rule_fails_while_an_empty_list_of_non_signal_classes_is_accepted(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: a missing mapping, an entry without its source or a non-positive or non-whole signal_pins_per_return, or an empty rule, fails
        self.assertFails(with_returns(ground_classes=[]), "ground_returns.ground_classes", "lists no net classes")
        self.assertFails(with_returns(signal_classes=[]), "ground_returns.signal_classes", "lists no signal net classes")
        self.assertFails(changed(ground_returns={}), "ground_returns.ground_classes", "lacks ground_classes")
        self.assertEqual(self.problems(with_returns(non_signal_classes=[])), [])

    def test_a_class_is_declared_once_across_ground_non_signal_and_signal_classes(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: a connector pin on a class declared none of ground, signal or non-signal fails
        self.assertFails(with_returns(non_signal_classes=["Ground", "Power"]), "ground_returns", "the class 'Ground' more than once")
        self.assertFails(with_returns(ground_classes=["Ground", "Default"]), "ground_returns", "the class 'Default' more than once")
        self.assertFails(with_returns(signal_classes=GROUND_RETURNS["signal_classes"] * 2), "ground_returns", "more than once")

    def test_the_record_is_among_the_files_a_design_reads_wherever_it_sits(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C6: A change to a design's board files or to any record these rules read re-runs the board tier of the build round
        for name in ("board.kicad_pro", "board.kicad_sch", "board.kicad_pcb"):
            self.write(f"hardware/m/board/{name}", "{}" if name.endswith("pro") else "(x)")
        self.write("hardware/m/board-rules.yaml", self.yaml.safe_dump(COMPLETE))
        subprocess_run = __import__("subprocess").run
        subprocess_run(["git", "init", "-q", self.root], check=True)
        subprocess_run(["git", "-C", self.root, "add", "-A"], check=True)
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertIn("hardware/m/board-rules.yaml", reads)

    def test_the_reads_listing_description_names_the_board_rules_record(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C6: The board-reads listing's description names the board rules record this leaf adds
        with open(os.path.join(REPO, "Taskfile.yml"), encoding="utf-8") as handle:
            description = self.yaml.safe_load(handle)["tasks"]["hw:reads"]["desc"]
        self.assertIn("board rules", description)


def tree_of(*items: str) -> list:
    return sexpr.parse_one("(kicad_pcb (version 20260206) " + " ".join(items) + ")")


def pad(number, net, x=0, extra="", kind="thru_hole"):
    layers = '"*.Cu"' if kind == "thru_hole" else '"F.Cu" "F.Mask"'
    drill = "(drill 0.8)" if kind == "thru_hole" else ""
    net_text = f'(net "{net}")' if net else ""
    return f'(pad "{number}" {kind} circle (at {x} 0) (size 1.6 1.6) {drill} (layers {layers}) {extra} {net_text})'


def part(reference, pads, extra="", at=(10, 10)):
    return (f'(footprint "lib:part" (layer "F.Cu") (at {at[0]} {at[1]}) {extra} '
            f'(property "Reference" "{reference}" (at 0 -3 0) (layer "F.SilkS")) ' + " ".join(pads) + ")")


def connector(reference, *pins, at=(10, 10)):
    """A connector with a pad for each (number, net) given."""
    return part(reference, [pad(number, net, 2.54 * index) for index, (number, net) in enumerate(pins)], at=at)


#: The nets of a design with a Ground class, a Power class, a Supply class, a Mains class and a Sensing class.
MEMBERS = {"Ground": {"/GND"}, "Power": {"/+5V", "/LOAD_RTN"}, "Supply": {"/+3V3"}, "Mains": {"/MAINS_L"},
           "Sensing": {"/AMP_IN", "/AMP_OUT", "/AMP_FB"}}


class TheGroundReturnRule(unittest.TestCase):
    def found(self, *items, returns=GROUND_RETURNS, members=MEMBERS):
        return board_check.ground_returns(DESIGN, tree_of(*items), RECORD, returns, members)

    def test_a_connector_whose_signal_pins_are_within_the_ratio_of_its_returns_passes_and_one_pin_over_fails(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: fails a connector whose signal pins exceed its signal class's signal_pins_per_return times its ground-return pins, compared exactly on whole pins
        # Default holds two signal pins per return: a nets are /X, /Y, ... in the Default class (in no listed class).
        def signals(count, grounds):
            return connector("J1", *[(str(i + 1), f"/S{i}") for i in range(count)],
                             *[(str(count + i + 1), "/GND") for i in range(grounds)])
        for count, grounds, fails in ((2, 1, False), (3, 1, True), (4, 2, False), (5, 2, True), (1, 1, False), (0, 0, False), (6, 3, False),
                                      (7, 3, True)):
            with self.subTest(signals=count, grounds=grounds):
                self.assertEqual(len(self.found(signals(count, grounds))), 1 if fails else 0)

    def test_a_connector_with_signal_pins_and_no_ground_return_pin_fails(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: so a connector with signal pins and no ground-return pin fails
        found = self.found(connector("J1", ("1", "/S0"), ("2", "/+5V")))
        self.assertEqual([v.rule for v in found], ["ground_return"])
        self.assertIn("has 1 signal pins (1 [/S0]) and 0 ground-return pins (none)", found[0].message)

    def test_a_ratio_of_one_holds_a_precision_signal_to_a_return_of_its_own(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: signal_pins_per_return (a positive whole number, the most signal pins one ground-return pin may serve)
        self.assertEqual(self.found(connector("J1", ("1", "/AMP_IN"), ("2", "/GND"))), [])
        found = self.found(connector("J1", ("1", "/AMP_IN"), ("2", "/AMP_OUT"), ("3", "/GND")))
        self.assertEqual(len(found), 1)
        self.assertIn("lets one return serve 1 signal pins at most, so it needs at least 2", found[0].message)

    def test_a_connector_of_several_signal_classes_is_held_to_the_smallest_ratio_among_them(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: a connector that carries several signal classes is held to the smallest signal_pins_per_return among them
        mixed = connector("J1", ("1", "/AMP_IN"), ("2", "/S0"), ("3", "/GND"))
        found = self.found(mixed)
        self.assertEqual(len(found), 1, "Default alone would allow two signals on one return, Sensing allows one")
        self.assertIn("lets one return serve 1 signal pins at most", found[0].message)
        looser = with_returns(signal_classes=[{"class": "Default", "signal_pins_per_return": 3, "source": SOURCE},
                                              {"class": "Sensing", "signal_pins_per_return": 2, "source": SOURCE}])["ground_returns"]
        self.assertEqual(self.found(mixed, returns=looser), [])
        self.assertEqual(len(self.found(connector("J1", ("1", "/AMP_IN"), ("2", "/S0"), ("3", "/S1"), ("4", "/GND")), returns=looser)), 1)

    def test_non_signal_pins_count_for_neither_side_of_the_ratio(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: non_signal_classes, the net classes such as power rails and Mains whose pins the ratio does not apply to
        self.assertEqual(self.found(connector("J1", ("1", "/+5V"), ("2", "/+3V3"), ("3", "/MAINS_L"), ("4", "/LOAD_RTN"))), [])
        self.assertEqual(self.found(connector("J1", ("1", "/S0"), ("2", "/S1"), ("3", "/GND"), ("4", "/+5V"), ("5", "/MAINS_L"))), [])
        self.assertEqual(len(self.found(connector("J1", ("1", "/S0"), ("2", "/S1"), ("3", "/S2"), ("4", "/GND"), ("5", "/+5V")))), 1)

    def test_a_pin_on_a_class_declared_none_of_ground_signal_or_non_signal_fails_naming_the_class_and_pin(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: A connector pin on a class declared none of ground, signal or non-signal fails
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C4: A failure of any rule in this leaf is reported with the rule's name, the design, and the offending item (net, pin, part reference, record key or figure)
        members = dict(MEMBERS, Relay={"/COIL"})
        found = self.found(connector("J1", ("1", "/COIL"), ("2", "/GND")), members=members)
        self.assertEqual([(v.design, v.rule) for v in found], [("hw/machine/board/board.kicad_pro", "ground_return")])
        self.assertEqual(found[0].location, "hw/machine/board/board.kicad_pcb connector J1 pin 1 [/COIL]")
        self.assertIn("pin 1 of connector J1 is on net /COIL, in the net class Relay, which hw/machine/board-rules.yaml ground_returns "
                      "declares as none of ground, signal or non-signal", found[0].message)

    def test_a_net_in_no_listed_class_is_in_default_and_fails_unless_default_is_declared(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: A connector pin on a class declared none of ground, signal or non-signal fails
        undeclared = with_returns(signal_classes=[{"class": "Sensing", "signal_pins_per_return": 1, "source": SOURCE}])["ground_returns"]
        found = self.found(connector("J1", ("1", "/S0"), ("2", "/GND")), returns=undeclared)
        self.assertIn("in the net class Default", found[0].message)
        self.assertEqual(self.found(connector("J1", ("1", "/S0"), ("2", "/GND"))), [])

    def test_the_classes_asked_of_kicad_are_the_projects_and_the_layouts_own_blocks_without_default(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: A connector pin on a class declared none of ground, signal or non-signal fails
        project = {"net_settings": {"classes": [{"name": "Default"}, {"name": "Proj", "track_width": "abc"}]}}
        layout = sexpr.parse_one('(kicad_pcb (net_class "Foo" "d" (add_net "/F")) (net_class Bare) (net_class) (net_class "Proj"))')
        self.assertEqual(board_check.layout_class_names(layout), {"Foo", "Bare", "Proj"})
        self.assertEqual(board_check.resolvable_classes(project, layout), {"Default", "Proj", "Foo", "Bare", "Mains"})
        self.assertEqual(board_check.resolvable_classes({}, sexpr.parse_one("(kicad_pcb)")), {"Mains"})

    def resolved(self, project, assigned):
        """The members a layout resolves to for the classes the check asks KiCad about, given each net's project class."""
        asked = board_check.project_class_names(project) - {board_check.DEFAULT_CLASS}
        return {name: {net for net, held in assigned.items() if held == name} for name in sorted(asked)}

    def test_a_class_whose_track_width_cannot_be_read_is_still_resolved_so_its_pin_is_not_taken_for_default(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: A connector pin on a class declared none of ground, signal or non-signal fails
        for width in ("abc", 0, -0.2, True):
            project = {"net_settings": {"classes": [{"name": "Default", "track_width": 0.2}, {"name": "Ground", "track_width": 0.3}, {"name": "Foo", "track_width": width}]}}
            self.assertIn("Foo", board_check.project_class_names(project))
            self.assertNotIn("Foo", board_check.class_widths(project)[0])
            found = self.found(connector("J1", ("1", "/F0"), ("2", "/GND")), members=self.resolved(project, {"/F0": "Foo", "/GND": "Ground"}))
            self.assertEqual([v.rule for v in found], ["ground_return"], width)
            self.assertIn("in the net class Foo, which", found[0].message)

    def test_an_unreadable_width_class_declared_ground_counts_as_a_return_not_a_default_signal(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: the signal pins, being pins on a net of a signal class the mapping declares, and the pins on a ground class
        project = {"net_settings": {"classes": [{"name": "Default", "track_width": 0.2}, {"name": "Ground", "track_width": "abc"}]}}
        members = self.resolved(project, {"/S0": "Default", "/S1": "Default", "/GND": "Ground"})
        self.assertEqual(self.found(connector("J1", ("1", "/S0"), ("2", "/S1"), ("3", "/GND")), members=members), [])
        found = self.found(connector("J1", ("1", "/S0"), ("2", "/S1"), ("3", "/S2"), ("4", "/GND")), members=dict(members, Ground={"/GND"}))
        self.assertEqual([v.rule for v in found], ["ground_return"])

    def test_a_net_in_a_ground_class_and_a_signal_class_cannot_be_told_and_fails(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: the signal pins, being pins on a net of a signal class the mapping declares, and the pins on a ground class
        members = dict(MEMBERS, Sensing=MEMBERS["Sensing"] | {"/GND"})
        found = self.found(connector("J1", ("1", "/GND")), members=members)
        self.assertEqual(len(found), 1)
        self.assertIn("declares as ground and signal, so whether it is a ground return or a signal cannot be told", found[0].message)

    def test_a_design_with_no_connector_is_not_failed_and_a_part_that_is_not_a_connector_is_not_counted(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: a design with no connector is not failed for that. Out of scope: parts that are not connectors
        self.assertEqual(self.found(), [])
        self.assertEqual(self.found(part("R1", [pad(1, "/S0", kind="smd"), pad(2, "/S1", 3, kind="smd"), pad(3, "/S2", 6, kind="smd")])), [])
        self.assertEqual(self.found(part("U1", [pad(1, "/S0"), pad(2, "/S1", 3), pad(3, "/S2", 6)])), [])

    def test_a_connector_is_any_part_whose_designator_begins_with_j_including_a_jumper(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: a connector being a part whose reference designator begins with J
        for reference in ("J1", "JP2", "J10", "j3"):
            with self.subTest(reference=reference):
                found = self.found(connector(reference, ("1", "/S0"), ("2", "/S1"), ("3", "/S2"), ("4", "/GND")))
                self.assertEqual(len(found), 1)
                self.assertIn(f"connector {reference} has 3 signal pins", found[0].message)

    def test_a_pad_on_no_net_or_on_a_net_nothing_else_joins_is_no_pin(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: the signal pins, being pins on a net of a signal class the mapping declares
        mounting = pad("", "", 20, kind="thru_hole")
        found = self.found(part("J1", [pad("1", "/S0"), pad("2", "/S1", 3), pad("3", "/GND", 6), mounting, pad("4", "unconnected-(J1-Pin_4)", 9),
                                       pad("5", "/sub/unconnected-(J1-Pin_5)", 12)]))
        self.assertEqual(found, [])

    def test_several_pads_numbered_alike_are_one_pin_and_are_counted_once(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: compared exactly on whole pins
        shield = part("J1", [pad("1", "/S0"), pad("2", "/S1", 3), pad("3", "/GND", 6), pad("3", "/GND", 9), pad("3", "/GND", 12)])
        self.assertEqual(self.found(shield), [])
        two_pads = part("J1", [pad("1", "/S0"), pad("1", "/S0", 3), pad("2", "/S1", 6), pad("3", "/GND", 9)])
        self.assertEqual(self.found(two_pads), [], "two signal pins on one return, however many pads carry the first")

    def test_unnumbered_pads_on_ground_are_never_returns_so_a_connector_with_none_numbered_still_fails(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: so a connector with signal pins and no ground-return pin fails
        tabs = part("J9", [pad("1", "/S0"), pad("2", "/S1", 3), pad("3", "/S2", 6), pad("4", "/S3", 9), pad("", "/GND", 12), pad("", "/GND", 15)])
        found = self.found(tabs)
        self.assertEqual(len(found), 1)
        self.assertIn("connector J9 has 4 signal pins", found[0].message)
        self.assertIn("and 0 ground-return pins (none)", found[0].message)

    def test_an_unnumbered_pad_on_a_signal_net_is_a_signal_pin_each(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: the signal pins, being pins on a net of a signal class the mapping declares
        at_ratio = part("J1", [pad("1", "/S0"), pad("", "/S1", 3), pad("3", "/GND", 6)])
        self.assertEqual(self.found(at_ratio), [])
        over = part("J1", [pad("1", "/S0"), pad("", "/S1", 3), pad("", "/S2", 6), pad("4", "/GND", 9)])
        found = self.found(over)
        self.assertEqual(len(found), 1)
        self.assertIn("connector J1 has 3 signal pins", found[0].message)
        two_blank = part("J1", [pad("1", "/S0"), pad("", "/S0", 3), pad("", "/S0", 6), pad("4", "/GND", 9)])
        self.assertEqual(len(self.found(two_blank)), 1, "each unnumbered pad is a pin of its own, even on one net")

    def test_unnumbered_pads_on_a_non_signal_class_are_ignored_and_on_an_undeclared_class_still_fail(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: A connector pin on a class declared none of ground, signal or non-signal fails
        ignored = part("J1", [pad("1", "/S0"), pad("2", "/GND", 3), pad("", "/+5V", 6), pad("", "/+5V", 9)])
        self.assertEqual(self.found(ignored), [])
        members = dict(MEMBERS, Relay={"/COIL"})
        found = self.found(part("J1", [pad("1", "/S0"), pad("2", "/GND", 3), pad("", "/COIL", 6)]), members=members)
        self.assertEqual(len(found), 1)
        self.assertIn("in the net class Relay", found[0].message)

    def test_a_net_named_unconnected_is_no_pin_only_when_one_pad_carries_it(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: the signal pins, being pins on a net of a signal class the mapping declares
        named = part("J9", [pad("1", "/S0"), pad("2", "/S1", 3), pad("3", "/unconnected-(SIG)", 6), pad("4", "/GND", 9)])
        elsewhere = part("U1", [pad("1", "/unconnected-(SIG)")], at=(40, 10))
        found = self.found(named, elsewhere)
        self.assertEqual(len(found), 1, "the shared net is real, so its pad on the connector is a third signal pin")
        self.assertIn("connector J9 has 3 signal pins", found[0].message)
        self.assertEqual(self.found(named), [], "carried by one pad it is no pin")
        both = part("J9", [pad("1", "/S0"), pad("2", "/unconnected-(SIG)", 3), pad("3", "/unconnected-(SIG)", 6), pad("4", "/GND", 9)])
        self.assertEqual(len(self.found(both)), 1)
        lone = part("J1", [pad("1", "/S0"), pad("2", "/S1", 3), pad("3", "/GND", 6), pad("4", "unconnected-(J1-Pin_4)", 9)])
        self.assertEqual(self.found(lone), [])

    def test_a_ground_return_failure_names_the_connector_its_pins_the_ratio_and_the_record(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C4: reported with the rule's name, the design, and the offending item in terms a builder can act on
        found = self.found(connector("J3", ("1", "/S0"), ("2", "/S1"), ("3", "/S2"), ("4", "/GND")))
        self.assertEqual(len(found), 1)
        v = found[0]
        self.assertEqual((v.design, v.rule, v.location), ("hw/machine/board/board.kicad_pro", "ground_return", "hw/machine/board/board.kicad_pcb connector J3"))
        self.assertIn("connector J3 has 3 signal pins (1 [/S0], 2 [/S1], 3 [/S2]) and 1 ground-return pins (4 [/GND])", v.message)
        self.assertIn("hw/machine/board-rules.yaml ground_returns lets one return serve 2 signal pins at most, so it needs at least 2", v.message)
        self.assertIn("add ground-return pins to the connector", v.message)
        self.assertTrue(v.line().startswith("VIOLATION | hw/machine/board/board.kicad_pro | ground_return | "))

    def test_each_connector_is_judged_on_its_own(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: The rule counts per connector
        found = self.found(connector("J1", ("1", "/S0"), ("2", "/S1"), ("3", "/GND")), connector("J2", ("1", "/S0"), ("2", "/S1"), ("3", "/S2")),
                           connector("J3", ("1", "/S0"), ("2", "/GND"), at=(30, 10)))
        self.assertEqual([v.location.rsplit(" ", 1)[-1] for v in found], ["J2"])


class TheSensingRules(unittest.TestCase):
    SIGNED = (3.0, 4.0)

    def test_a_pair_without_the_mains_class_is_written_ahead_of_the_signed_rule_at_the_declared_clearance(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: inserts on a temporary copy, after the design's own rules and ahead of the signed Mains rule, one rule per sensing and noisy class pair that does not involve the Mains class at the declared clearance
        ahead, after, named = board_check.sensing_rules(SENSING, self.SIGNED)
        self.assertIn("A.hasNetclass('Sensing') && B.hasNetclass('Power')", ahead)
        self.assertIn("(constraint clearance (min 0.5mm))", ahead)
        self.assertNotIn("Power", after)
        self.assertEqual(ahead.count("(rule "), 1)
        self.assertEqual(named["pre-order check: sensing clearance: Sensing against Power"], ("Sensing", "Power", 0.5))

    def test_a_pair_with_the_mains_class_is_written_after_the_signed_rule_on_the_clearance_alone_at_the_larger_figure(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: and after the signed rule, one rule per pair that involves the Mains class holding a clearance constraint only at the larger of the declared clearance and the signed clearance
        for declared, larger in ((0.5, 3.0), (3.0, 3.0), (6.0, 6.0)):
            with self.subTest(declared=declared):
                ahead, after, named = board_check.sensing_rules(dict(SENSING, clearance_mm=declared), self.SIGNED)
                self.assertIn("A.hasNetclass('Sensing') && B.hasNetclass('Mains')", after)
                self.assertNotIn("Mains", ahead)
                self.assertIn(f"(constraint clearance (min {larger:g}mm))", after)
                self.assertNotIn("creepage", after)
                self.assertNotIn("creepage", ahead)
                self.assertEqual(after.count("constraint"), 1)
                self.assertEqual(named["pre-order check: sensing clearance: Sensing against Mains"], ("Sensing", "Mains", larger))

    def test_a_pair_with_mains_is_written_ahead_when_a_design_has_no_signed_figure_to_follow(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: so that no rule loosens the signed figure
        ahead, after, named = board_check.sensing_rules(SENSING, None)
        self.assertEqual(after, "")
        self.assertEqual(ahead.count("(rule "), 2)
        self.assertEqual({figure for _, _, figure in named.values()}, {0.5})

    def test_every_sensing_and_noisy_pair_has_its_own_rule_of_its_own_name(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: one rule per sensing and noisy class pair
        sensing = dict(SENSING, classes=["Sensing", "Reference"], noisy_classes=["Power", "Relay", "Mains"])
        ahead, after, named = board_check.sensing_rules(sensing, self.SIGNED)
        self.assertEqual(len(named), 6)
        self.assertEqual(ahead.count("(rule ") + after.count("(rule "), 6)
        self.assertEqual(after.count("(rule "), 2)

    def test_the_rules_are_named_for_the_check_so_a_design_cannot_pass_a_rule_of_its_own_for_them(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C4: reported with the rule's name
        _, _, named = board_check.sensing_rules(SENSING, self.SIGNED)
        self.assertTrue(all(name.startswith(board_check.RESERVED) for name in named))

    def sensing_classes(self, **edits):
        sensing = dict(SENSING, **edits)
        members = {"Sensing": {"/AMP_IN"}, "Power": {"/+5V"}, "Mains": {"/MAINS_L"}, "Empty": set()}
        return board_check.sensing_classes(DESIGN, RECORD, sensing, {"Sensing", "Power", "Mains", "Empty", "Default"}, members)

    def test_a_declared_class_that_is_not_a_project_class_or_holds_no_net_fails_so_a_misspelling_cannot_pass(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: Out of scope: inferring classes from net names. A class the rules would apply to nothing for fails
        self.assertEqual(self.sensing_classes(), [])
        found = self.sensing_classes(classes=["Sensng"])
        self.assertEqual([(v.rule, v.location) for v in found], [("sensing_clearance", f"{RECORD} sensing.classes")])
        self.assertIn("the class 'Sensng' is no net class of the design's project file", found[0].message)
        found = self.sensing_classes(noisy_classes=["Power", "Empty"])
        self.assertIn("the class 'Empty' holds no net on the layout", found[0].message)
        self.assertEqual(found[0].location, f"{RECORD} sensing.noisy_classes")

    def test_a_class_name_a_rule_condition_cannot_carry_fails_rather_than_being_written_into_one(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: the check inserts rules on a temporary copy
        for name in ("a'b", 'a"b', "a\\b"):
            with self.subTest(name=name):
                found = board_check.sensing_classes(DESIGN, RECORD, dict(SENSING, classes=[name]), {name, "Power", "Mains"},
                                                    {name: {"/X"}, "Power": {"/+5V"}, "Mains": {"/MAINS_L"}})
                self.assertEqual([v.rule for v in found], ["sensing_clearance"])
                self.assertIn("cannot carry", found[0].message)


def net_pad(number, net, extra=""):
    return f'(pad "{number}" smd rect (at {number} 0) (size 1 1) (layers "F.Cu") {extra} (net "{net}"))'


class TheSensingOverrideRule(unittest.TestCase):
    NETS = {"/AMP_IN", "/+5V"}

    def found(self, *items, figure=0.5):
        return board_check.sensing_overrides(DESIGN, tree_of(*items), RECORD, figure, self.NETS)

    def test_a_pad_override_below_the_figure_on_a_sensing_or_noisy_net_fails_naming_the_pad_net_and_part(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: A local clearance override on a pad or footprint on a sensing or noisy class net that is below the declared sensing clearance fails
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C4: reported with the rule's name, the design, and the offending item
        for net in sorted(self.NETS):
            with self.subTest(net=net):
                found = self.found(part("U1", [net_pad(1, net, "(clearance 0.1)")], at=(4, 5)))
                self.assertEqual([(v.design, v.rule) for v in found], [("hw/machine/board/board.kicad_pro", "sensing_override")])
                self.assertEqual(found[0].location, f"pad 1 [{net}] of U1 (footprint at (4, 5) mm)")
                self.assertIn(f"pad 1 of U1 is on the sensing or noisy class net {net} and sets a local clearance override of 0.1 mm, "
                              f"below the 0.5 mm that {RECORD} declares for sensing", found[0].message)

    def test_an_override_at_or_above_the_figure_or_on_another_net_or_on_no_net_passes(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: that is below the declared sensing clearance fails
        for pad_text in (net_pad(1, "/AMP_IN", "(clearance 0.5)"), net_pad(1, "/AMP_IN", "(clearance 0.8)"), net_pad(1, "/AMP_IN"),
                         net_pad(1, "/OTHER", "(clearance 0.1)"), '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (clearance 0.1))'):
            with self.subTest(pad=pad_text):
                self.assertEqual(self.found(part("U1", [pad_text])), [])

    def test_a_footprint_override_is_on_a_sensing_or_noisy_net_when_any_of_its_pads_is(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: A local clearance override on a pad or footprint
        found = self.found(part("U1", [net_pad(1, "/OTHER"), net_pad(2, "/+5V")], "(clearance 0.1)"))
        self.assertEqual([(v.rule, v.location) for v in found], [("sensing_override", "footprint U1 at (10, 10) mm")])
        self.assertIn("footprint U1 has a pad on a sensing or noisy class net and sets a local clearance override of 0.1 mm", found[0].message)
        self.assertEqual(self.found(part("U1", [net_pad(1, "/OTHER"), net_pad(2, "/OTHER")], "(clearance 0.1)")), [])
        self.assertEqual(self.found(part("U1", [net_pad(1, "/+5V")], "(clearance 0.5)")), [])

    def test_the_figure_compared_is_the_declared_sensing_clearance_not_the_signed_one(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: since a design with no Mains may still declare sensing classes
        item = part("U1", [net_pad(1, "/AMP_IN", "(clearance 0.4)")])
        self.assertEqual(len(self.found(item, figure=0.5)), 1)
        self.assertEqual(self.found(item, figure=0.3), [])


class TheRulesAreRunOnTheDesignsTheyHold(unittest.TestCase):
    """What check_design is told, read without KiCad: which designs the rules inspect and which stay out."""

    def test_the_new_rule_names_are_the_ones_the_hardware_notes_table_gives(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C7: The hardware notes' table of the pre-order check's rules carries one entry for each of the sensing-clearance rule and the ground-return rule, naming what fails it, what exempts a design, and the name its failure is reported under
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            rows = {line.split("|")[1].strip(): line for line in handle.read().splitlines() if line.startswith("| `")}
        for name, exempt in (("sensing_clearance", "exempt"), ("sensing_override", "exempt"), ("ground_return", "exempt"),
                             ("board_rules_record", "")):
            with self.subTest(rule=name):
                self.assertIn(f"`{name}`", rows)
                self.assertIn(exempt, rows[f"`{name}`"])
        self.assertIn("a connector", rows["`ground_return`"])
        self.assertIn("none", rows["`ground_return`"])
        self.assertIn("none", rows["`sensing_clearance`"])
        self.assertIn("board-rules.yaml", rows["`board_rules_record`"])

    def test_the_catalogue_carries_the_enforced_sensing_item_beside_the_judgement_item_and_defines_its_form(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: The layout practice catalogue's sensing item moves from reviewer judgement to enforced
        with open(os.path.join(REPO, "docs", "board-design-method.md"), encoding="utf-8") as handle:
            method = handle.read()

        def item(identifier: str) -> str:
            start = method.index(f"#### {identifier}. ")
            return method[start:method.index("\n#### ", start + 1) if "\n#### " in method[start + 1:] else len(method)]
        enforced, judged = item("SENSE-6"), item("SENSE-4")
        self.assertIn("**Kind:** rule.", enforced)
        for words in ("`sensing_clearance`", "`sensing_override`", "sensing.clearance_mm", "applies when"):
            self.assertIn(words.lower() if words == "applies when" else words, enforced.lower() if words == "applies when" else enforced)
        self.assertIn("**Kind:** judgement.", judged)
        self.assertIn("`SENSE-6`", judged)
        self.assertIn("The fifth is a **record figure**", method)
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C7: the notes link the enforced item by the anchor its heading has on GitHub
        heading = re.search(r"^#### (SENSE-6\. .*)$", method, re.M).group(1)
        slug = re.sub(r"[^a-z0-9 _-]", "", heading.lower()).replace(" ", "-")
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            notes = handle.read()
        targets = set(re.findall(r"board-design-method\.md#(sense-6[^)\s]*)", notes))
        self.assertEqual(targets, {slug})
        self.assertNotIn("one of the four forms", method)


if __name__ == "__main__":
    unittest.main()
