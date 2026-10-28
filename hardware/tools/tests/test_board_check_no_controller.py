#!/usr/bin/env python3
"""The pre-order check's pin allocation rules for a board that places no controller, and for a rail entry.

Synthetic designs and records in a temporary directory; the netlists are written by hand in KiCad's form, so
nothing here needs KiCad.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import sexpr  # noqa: E402
import test_board_check as base  # noqa: E402

YAML_HEAD = "controller: none\n"

#: The wall-side record: two far channels and two return pins on one header.
WALL_RECORD = YAML_HEAD + """\
channels:
  - channel: wall_heater
    net: HEATER
    connector: J1
    connector_pin: 1
    far_channel: heater_drive
  - channel: wall_pump
    net: PUMP
    connector: J1
    connector_pin: 2
    far_channel: pump_drive
  - channel: return_a
    net: GND
    connector: J1
    connector_pin: 3
    rail: ground
  - channel: return_b
    net: GND
    connector: J1
    connector_pin: 4
    rail: ground
"""

#: A design that satisfies WALL_RECORD and places no controller.
WALL_NETS = {
    "/HEATER": [("J1", "1", "Pin_1_1"), ("Q1", "1", None)],
    "/PUMP": [("J1", "2", "Pin_2_2"), ("Q2", "1", None)],
    "/GND": [("J1", "3", "Pin_3_3"), ("J1", "4", "Pin_4_4"), ("Q1", "2", None)],
    "unconnected-(J1-Pin_5-Pad5)": [("J1", "5", "Pin_5_5")],
}

#: The main-board record: the far side of the two channels, and a rail entry beside them.
MAIN_RECORD = """\
channels:
  - channel: heater_drive
    net: HEATER
    controller_pin: PA0
    connector: J2
    connector_pin: 1
  - channel: pump_drive
    net: PUMP
    controller_pin: PA1
    connector: J2
    connector_pin: 2
  - channel: ground_a
    net: GND
    connector: J2
    connector_pin: 3
    rail: ground
  - channel: ground_b
    net: GND
    connector: J2
    connector_pin: 4
    rail: ground
"""

MAIN_NETS = {
    "/HEATER": [("J2", "1", "Pin_1_1"), ("U1", "7", "PA0_7")],
    "/PUMP": [("J2", "2", "Pin_2_2"), ("U1", "8", "PA1_8")],
    "/GND": [("J2", "3", "Pin_3_3"), ("J2", "4", "Pin_4_4"), ("U1", "1", "VSS_1")],
}

CONTROLLER_PART = """\
part: TEST-MCU-1
lcsc: C9999001
pins:
  - PA0
  - PA1
"""


class WallTree(base.PinRecordTree):
    """A design in a machine folder, hardware/m/wall, whose record is read as the check reads it."""

    design = board_check.Design("hardware/m/wall/wall.kicad_pro")
    where = "hardware/m/wall/pin-allocation.yaml"

    def record(self, text: str, not_for_manufacture: bool = False):
        self.write(self.where, text)
        return board_check.read_pin_record(board_check.require_yaml(), self.root, self.design, self.where, not_for_manufacture)

    def usable(self, text: str = WALL_RECORD):
        channels, problems = self.record(text)
        self.assertEqual(problems, [])
        return channels

    def assertFails(self, text: str, location_end: str, words: str, not_for_manufacture: bool = False):
        channels, problems = self.record(text, not_for_manufacture)
        self.assertIsNone(channels)
        self.assertTrue(any(v.rule == "pin_allocation" and v.location.endswith(location_end) and words in v.message
                            for v in problems), [(v.location, v.message) for v in problems])

    def connectivity(self, nets: dict, text: str = WALL_RECORD):
        nodes = board_check.schematic_pin_nodes(sexpr.parse_one(base.netlist_text(nets)))
        return board_check.connectivity(self.design, self.where, self.usable(text), nodes)

    def controller(self, nets: dict, placed: dict, text: str = WALL_RECORD, record=None, path=None):
        channels = self.usable(text)
        nodes = board_check.schematic_pin_nodes(sexpr.parse_one(base.netlist_text(nets)))
        return board_check.controller_part(self.design, path, record, channels, self.where, nodes, placed)


class TheDeclarationIsHeldToTheDesign(WallTree):
    def selected(self):
        self.write("hardware/m/controller-part.yaml", CONTROLLER_PART)
        record, path, problems = board_check.read_controller_record(
            board_check.require_yaml(), self.root, self.everything(), self.design, False)
        self.assertEqual(problems, [])
        return record, path

    def test_a_declared_design_that_places_a_part_with_a_port_named_pin_fails_naming_the_part(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C1: The declaration fails a design that places a part with a port-named pin or a part whose catalogue number equals the machine's controller part record, naming the part, and a design that places no controller and carries no declaration fails as it does now. Comparing the cable between two headers pin for pin is out of scope.
        nets = dict(WALL_NETS)
        nets["/HEATER"] = nets["/HEATER"] + [("U1", "7", "PA0_7")]
        found = self.controller(nets, {"U1": {"lcsc": "C1234567"}, "Q1": {"lcsc": "C1"}})
        self.assertEqual([(v.rule, v.location) for v in found], [("controller_part", "hardware/m/wall/wall.kicad_sch U1")])
        self.assertIn("declares controller: none, but the design places U1", found[0].message)

    def test_a_declared_design_that_places_the_selected_catalogue_number_fails_though_no_pin_is_port_named(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C1: The declaration fails a design that places a part with a port-named pin or a part whose catalogue number equals the machine's controller part record, naming the part, and a design that places no controller and carries no declaration fails as it does now. Comparing the cable between two headers pin for pin is out of scope.
        record, path = self.selected()
        found = self.controller(WALL_NETS, {"U7": {"lcsc": "C9999001"}, "Q1": {"lcsc": "C1"}}, record=record, path=path)
        self.assertEqual([(v.rule, v.location) for v in found], [("controller_part", "hardware/m/wall/wall.kicad_sch U7")])
        self.assertIn("catalogue number C9999001 of the selected TEST-MCU-1", found[0].message)

    def test_a_declared_design_that_places_neither_passes(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C1: The declaration fails a design that places a part with a port-named pin or a part whose catalogue number equals the machine's controller part record, naming the part, and a design that places no controller and carries no declaration fails as it does now. Comparing the cable between two headers pin for pin is out of scope.
        record, path = self.selected()
        self.assertEqual(self.controller(WALL_NETS, {"Q1": {"lcsc": "C1"}, "Q2": {"lcsc": None}}, record=record, path=path), [])

    def test_where_the_machine_holds_no_controller_part_record_the_declared_design_is_held_to_port_pins_alone(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C1: The declaration fails a design that places a part with a port-named pin or a part whose catalogue number equals the machine's controller part record, naming the part, and a design that places no controller and carries no declaration fails as it does now. Comparing the cable between two headers pin for pin is out of scope.
        self.assertEqual(self.controller(WALL_NETS, {"U7": {"lcsc": "C9999001"}}, path=None), [])
        nets = dict(WALL_NETS)
        nets["/PUMP"] = nets["/PUMP"] + [("U1", "8", "PA1_8")]
        found = self.controller(nets, {"U1": {"lcsc": "C9999001"}}, path=None)
        self.assertEqual([v.location for v in found], ["hardware/m/wall/wall.kicad_sch U1"])
        found = self.controller(nets, {"U1": {"lcsc": "C9999001"}}, path="hardware/m/controller-part.yaml", record=None)
        self.assertEqual([v.location for v in found], ["hardware/m/wall/wall.kicad_sch U1"])

    def test_a_design_that_places_no_controller_and_carries_no_declaration_still_fails(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C1: The declaration fails a design that places a part with a port-named pin or a part whose catalogue number equals the machine's controller part record, naming the part, and a design that places no controller and carries no declaration fails as it does now. Comparing the cable between two headers pin for pin is out of scope.
        rails_only = "channels:\n  - channel: ground_a\n    net: GND\n    connector: J2\n    connector_pin: 3\n    rail: ground\n"
        self.assertFails(rails_only, "channels", "lists no channel with a controller pin")
        channels, problems = self.record(MAIN_RECORD)
        self.assertEqual(problems, [])
        nodes = board_check.schematic_pin_nodes(sexpr.parse_one(base.netlist_text(WALL_NETS)))
        found = board_check.connectivity(self.design, self.where, channels, nodes)
        self.assertTrue(any("channel heater_drive" in v.message and "no controller pin" in v.message for v in found), found)

    def test_a_controller_key_other_than_none_fails(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C1: The declaration fails a design that places a part with a port-named pin or a part whose catalogue number equals the machine's controller part record, naming the part, and a design that places no controller and carries no declaration fails as it does now. Comparing the cable between two headers pin for pin is out of scope.
        for value in ("PA0", "'yes'", "true", "[none]"):
            with self.subTest(value=value):
                self.assertFails(WALL_RECORD.replace("controller: none", f"controller: {value}"), "controller", "controller is")

    def test_a_record_with_no_declaration_is_not_a_declared_design(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C1: The declaration fails a design that places a part with a port-named pin or a part whose catalogue number equals the machine's controller part record, naming the part, and a design that places no controller and carries no declaration fails as it does now. Comparing the cable between two headers pin for pin is out of scope.
        channels, problems = self.record(MAIN_RECORD)
        self.assertEqual(problems, [])
        self.assertFalse(channels.no_controller)
        self.assertTrue(self.usable(WALL_RECORD).no_controller)


class ADeclaredRecordsEntriesAreHeld(WallTree):
    def test_a_complete_record_gives_each_entry_its_net_connector_pin_and_far_channel_or_rail(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        channels = self.usable()
        self.assertEqual([(c.channel, c.net, c.controller_pin, c.connector, c.connector_pin, c.far_channel, c.rail) for c in channels],
                         [("wall_heater", "HEATER", None, "J1", "1", "heater_drive", None),
                          ("wall_pump", "PUMP", None, "J1", "2", "pump_drive", None),
                          ("return_a", "GND", None, "J1", "3", None, "ground"),
                          ("return_b", "GND", None, "J1", "4", None, "ground")])

    def test_an_entry_with_neither_a_far_channel_nor_a_rail_fails_naming_the_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        self.assertFails(WALL_RECORD.replace("    far_channel: heater_drive\n", ""), "channel wall_heater", "carries neither far_channel nor rail")

    def test_an_entry_with_both_a_far_channel_and_a_rail_fails_naming_the_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        self.assertFails(WALL_RECORD.replace("    far_channel: heater_drive\n", "    far_channel: heater_drive\n    rail: x\n"),
                         "channel wall_heater", "carries both far_channel and rail")

    def test_an_entry_carrying_a_controller_pin_fails_naming_the_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        self.assertFails(WALL_RECORD.replace("    far_channel: heater_drive\n", "    far_channel: heater_drive\n    controller_pin: PA0\n"),
                         "channel wall_heater", "carries no controller_pin")

    def test_an_entry_without_its_connector_or_connector_pin_fails(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        self.assertFails(WALL_RECORD.replace("    connector: J1\n    connector_pin: 1\n", "", 1), "channel wall_heater", "lacks connector")
        self.assertFails(WALL_RECORD.replace("    connector_pin: 2\n", "", 1), "channel wall_pump", "lacks connector_pin")

    def test_an_entry_without_its_net_or_with_a_blank_far_channel_or_rail_fails(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        self.assertFails(WALL_RECORD.replace("    net: HEATER\n", "", 1), "channel wall_heater", "lacks net")
        self.assertFails(WALL_RECORD.replace("far_channel: heater_drive", "far_channel: ''"), "channel wall_heater", "far_channel is ''")
        self.assertFails(WALL_RECORD.replace("rail: ground", "rail: ''", 1), "channel return_a", "rail is ''")

    def test_a_connector_pin_listed_twice_or_a_channel_named_twice_fails_though_rails_may_share_a_net(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        self.assertFails(WALL_RECORD.replace("connector_pin: 4", "connector_pin: 3"), "channel return_b", "connector pin J1 pin 3 is listed")
        self.assertFails(WALL_RECORD.replace("channel: return_b", "channel: return_a"), "channel return_a", "channel return_a is listed")
        self.assertFails(WALL_RECORD.replace("net: PUMP", "net: HEATER"), "channel wall_pump", "net HEATER is listed")

    def test_a_design_that_matches_its_record_passes_the_connectivity_rule(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        self.assertEqual(self.connectivity(WALL_NETS), [])

    def test_a_net_that_does_not_reach_its_connector_pin_fails_naming_the_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        nets = dict(WALL_NETS)
        nets["/HEATER"] = [("J1", "5", "Pin_5_5"), ("Q1", "1", None)]
        nets.pop("unconnected-(J1-Pin_5-Pad5)")
        found = self.connectivity(nets)
        self.assertTrue(any(v.rule == "connectivity" and v.location.endswith("channel wall_heater")
                            and "net /HEATER reaches connector pin J1 pin 5, where the record names connector pin J1 pin 1" in v.message
                            for v in found), found)
        self.assertFalse(any("controller pin" in v.message for v in found), found)

    def test_a_listed_channel_the_design_lacks_fails_naming_the_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        nets = dict(WALL_NETS)
        nets.pop("/PUMP")
        found = self.connectivity(nets)
        self.assertEqual([(v.rule, v.location) for v in found], [("connectivity", f"{self.where} channel wall_pump")])
        self.assertIn("the record lists net PUMP, which the design does not have", found[0].message)

    def test_a_net_on_a_pin_of_a_listed_connector_that_the_record_omits_fails(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        nets = dict(WALL_NETS)
        nets["/SPARE"] = [("J1", "5", "Pin_5_5"), ("Q3", "1", None)]
        nets.pop("unconnected-(J1-Pin_5-Pad5)")
        found = self.connectivity(nets)
        self.assertEqual([(v.rule, v.location) for v in found], [("connectivity", "hardware/m/wall/wall.kicad_sch J1 pin 5")])
        self.assertIn("net /SPARE is on connector pin J1 pin 5, which the record does not list", found[0].message)

    def test_a_declared_record_leaves_the_port_named_pins_of_a_part_to_the_part_rule(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C2: An entry with neither or both of far_channel and rail fails, an entry carrying a controller pin fails, a channel whose net does not reach its connector pin fails, a listed channel the design lacks fails, and any net on a pin of a listed connector that the record does not list fails. The firmware tier's checks are out of scope and unchanged.
        nets = dict(WALL_NETS)
        nets["/HEATER"] = nets["/HEATER"] + [("U1", "7", "PA0_7")]
        self.assertEqual(self.connectivity(nets), [])


class AFarChannelIsHeldAgainstTheOtherDesignsRecords(base.Tree):
    def setUp(self):
        super().setUp()
        self.wall = board_check.Design("hardware/m/wall/wall.kicad_pro")
        self.main = board_check.Design("hardware/m/main/main.kicad_pro")
        self.write("hardware/m/wall/pin-allocation.yaml", WALL_RECORD)
        self.write("hardware/m/main/pin-allocation.yaml", MAIN_RECORD)

    def far(self, others=None, text=None):
        if text is not None:
            self.write("hardware/m/wall/pin-allocation.yaml", text)
        yaml = board_check.require_yaml()
        channels, problems = board_check.read_pin_record(yaml, self.root, self.wall, "hardware/m/wall/pin-allocation.yaml", False)
        self.assertEqual(problems, [])
        files = [os.path.relpath(os.path.join(d, n), self.root) for d, _, names in os.walk(self.root) for n in names]
        if others is None:
            others = board_check.other_designs_records(self.wall, [self.wall, self.main], set(files), self.root,
                                                       "hardware/m/wall/pin-allocation.yaml")
        return board_check.far_channels(yaml, self.root, self.wall, "hardware/m/wall/pin-allocation.yaml", channels, others)

    def test_far_channels_that_another_design_lists_with_a_controller_pin_and_a_connector_pass(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        self.assertEqual(self.far(), [])

    def test_a_far_channel_that_no_record_lists_fails_naming_the_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        found = self.far(text=WALL_RECORD.replace("far_channel: pump_drive", "far_channel: pump_drivee"))
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("pin_allocation", "hardware/m/wall/pin-allocation.yaml channel wall_pump")])
        self.assertIn("names far channel pump_drivee, which no other design's record in the machine folder lists", found[0].message)
        self.assertIn("hardware/m/main/pin-allocation.yaml", found[0].message)

    def test_a_channel_another_record_lists_without_a_controller_pin_or_without_a_connector_is_not_a_far_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        for old, new in (("    controller_pin: PA0\n", ""), ("    connector: J2\n    connector_pin: 1\n", "")):
            with self.subTest(removed=old):
                self.write("hardware/m/main/pin-allocation.yaml", MAIN_RECORD.replace(old, "", 1))
                found = self.far()
                self.assertEqual([v.location.split(" channel ")[1] for v in found], ["wall_heater"])

    def test_a_rail_or_far_entry_of_another_record_is_not_a_far_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        self.write("hardware/m/main/pin-allocation.yaml", MAIN_RECORD)
        found = self.far(text=WALL_RECORD.replace("far_channel: heater_drive", "far_channel: ground_a"))
        self.assertEqual([v.location.split(" channel ")[1] for v in found], ["wall_heater"])

    def test_a_record_the_design_is_itself_held_to_is_not_another_designs(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        shared = "hardware/m/pin-allocation.yaml"
        self.write(shared, WALL_RECORD)
        os.remove(os.path.join(self.root, "hardware/m/wall/pin-allocation.yaml"))
        os.remove(os.path.join(self.root, "hardware/m/main/pin-allocation.yaml"))
        files = {shared, "hardware/m/wall/wall.kicad_pro", "hardware/m/main/main.kicad_pro"}
        self.assertEqual(board_check.other_designs_records(self.wall, [self.wall, self.main], files, self.root, shared), [])

    def test_a_record_that_cannot_be_read_lists_nothing_and_a_lone_design_has_no_one_to_list_it(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        self.write("hardware/m/main/pin-allocation.yaml", "channels: [unclosed\n")
        self.assertEqual(len(self.far()), 2)
        found = self.far(others=[])
        self.assertEqual(len(found), 2)
        self.assertIn("it has no other design with a record", found[0].message)

    def test_only_designs_in_the_same_machine_folder_are_others_and_a_design_with_no_machine_folder_has_none(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        elsewhere = board_check.Design("hardware/n/main/main.kicad_pro")
        self.write("hardware/n/main/pin-allocation.yaml", MAIN_RECORD)
        files = {"hardware/m/main/pin-allocation.yaml", "hardware/n/main/pin-allocation.yaml", "hardware/m/wall/pin-allocation.yaml"}
        self.assertEqual(board_check.other_designs_records(self.wall, [self.wall, self.main, elsewhere], files, self.root, None),
                         ["hardware/m/main/pin-allocation.yaml"])
        proof = board_check.Design("hardware/proof/p/p.kicad_pro")
        loose = board_check.Design("p/p.kicad_pro")
        for design in (proof, loose):
            self.assertEqual(board_check.other_designs_records(design, [design, self.main, self.wall], files, self.root, None), [])

    def test_the_records_of_the_other_designs_in_the_machine_folder_are_among_what_a_design_reads(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        for name in ("wall", "main"):
            self.write(f"hardware/m/{name}/{name}.kicad_pro", "{}")
            self.write(f"hardware/m/{name}/{name}.kicad_sch", "(kicad_sch)")
            self.write(f"hardware/m/{name}/{name}.kicad_pcb", "(kicad_pcb)")
        self.git("init", "-q")
        self.git("add", "-A")
        self.assertEqual(sorted(board_check.other_designs_records(self.wall, board_check.discover(self.root, board_check.tracked_files("git", self.root))[0],
                                                                    set(board_check.tracked_files("git", self.root)), self.root, None)),
                         ["hardware/m/main/pin-allocation.yaml"])
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertIn("hardware/m/main/pin-allocation.yaml", reads)
        self.assertIn("hardware/m/wall/pin-allocation.yaml", reads)


class ARailEntryListsASupplyOrReturnPin(base.PinRecordTree):
    def usable(self, text: str = MAIN_RECORD):
        channels, problems = self.record(text)
        self.assertEqual(problems, [])
        return channels

    def violations(self, nets: dict, text: str = MAIN_RECORD):
        nodes = board_check.schematic_pin_nodes(sexpr.parse_one(base.netlist_text(nets)))
        return board_check.connectivity(self.design, "hardware/m/pin-allocation.yaml", self.usable(text), nodes)

    def test_a_controller_design_lists_a_connectors_several_return_pins_in_full_and_passes(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        channels = self.usable()
        self.assertEqual([(c.channel, c.controller_pin, c.rail) for c in channels],
                         [("heater_drive", "PA0", None), ("pump_drive", "PA1", None), ("ground_a", None, "ground"), ("ground_b", None, "ground")])
        self.assertEqual(self.violations(MAIN_NETS), [])

    def test_a_rail_entrys_net_that_does_not_reach_its_connector_pin_fails_naming_the_channel(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        nets = dict(MAIN_NETS)
        nets["/GND"] = [("J2", "3", "Pin_3_3"), ("J2", "5", "Pin_5_5"), ("U1", "1", "VSS_1")]
        found = self.violations(nets)
        self.assertTrue(any(v.location.endswith("channel ground_b") and "reaches connector pin J2 pin 3, J2 pin 5, where the record names connector pin J2 pin 4" in v.message for v in found), found)
        nets.pop("/GND")
        nets["/RET"] = [("J2", "3", "Pin_3_3"), ("J2", "4", "Pin_4_4")]
        self.assertTrue(any(v.location.endswith("channel ground_a") and "the record lists net GND, which the design does not have" in v.message
                            for v in self.violations(nets)))

    def test_a_pin_of_the_connector_that_no_entry_lists_still_fails(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        nets = dict(MAIN_NETS)
        nets["/GND"] = nets["/GND"] + [("J2", "6", "Pin_6_6")]
        found = self.violations(nets)
        self.assertTrue(any("is on connector pin J2 pin 6, which the record does not list" in v.message for v in found), found)

    def test_rail_entries_share_a_net_while_each_connector_pin_and_each_channel_label_is_listed_once(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        self.assertFails(MAIN_RECORD.replace("connector_pin: 4", "connector_pin: 3"), "channel ground_b", "connector pin J2 pin 3 is listed")
        self.assertFails(MAIN_RECORD.replace("channel: ground_b", "channel: ground_a"), "channel ground_a", "channel ground_a is listed")
        self.assertFails(MAIN_RECORD.replace("channel: ground_b", "channel: heater_drive"), "channel heater_drive", "channel heater_drive is listed")

    def test_a_net_listed_by_a_signal_channel_is_still_listed_once_among_signal_channels(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        self.assertFails(MAIN_RECORD.replace("net: PUMP", "net: HEATER"), "channel pump_drive", "net HEATER is listed")

    def test_a_rail_entry_carrying_a_controller_pin_or_lacking_its_connector_fails(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        self.assertFails(MAIN_RECORD.replace("    rail: ground\n", "    rail: ground\n    controller_pin: PA2\n", 1), "channel ground_a", "carries both rail and controller_pin")
        self.assertFails(MAIN_RECORD.replace("    connector: J2\n    connector_pin: 3\n", "", 1), "channel ground_a", "lacks connector")

    def test_entries_that_carry_a_controller_pin_are_held_as_before(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        self.assertFails(MAIN_RECORD.replace("    controller_pin: PA0\n", "", 1), "channel heater_drive", "lacks controller_pin")
        nets = dict(MAIN_NETS)
        nets["/HEATER"] = [("J2", "1", "Pin_1_1"), ("U1", "7", "PA1_7")]
        self.assertTrue(any("reaches controller pin PA1, where the record names controller pin PA0" in v.message for v in self.violations(nets)))

    def test_a_controller_pin_is_not_asked_of_a_rail_by_the_controller_part_rule(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        channels = self.usable()
        record = board_check.ControllerRecord("hardware/m/controller-part.yaml", "TEST-MCU-1", "C9999001", {"PA0", "PA1"})
        nodes = board_check.schematic_pin_nodes(sexpr.parse_one(base.netlist_text(MAIN_NETS)))
        self.assertEqual(board_check.controller_part(self.design, record.path, record, channels, "hardware/m/pin-allocation.yaml", nodes,
                                                     {"U1": {"lcsc": "C9999001"}}), [])


class EachFailureIsReportedInTheTextReport(WallTree):
    def lines(self, found):
        return [violation.line() for violation in found]

    def test_each_failing_case_names_the_rule_and_the_channel_or_the_part(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C5: The check's text report names, for each failing case of the pin allocation and connectivity rules, the rule and the channel or part, and a passing controller-less design reports no failure. The check has no machine-readable report, and none is added here. Failures of rules other than the pin allocation and connectivity rules are out of scope.
        cases = []
        for text, rule, name in (
                (WALL_RECORD.replace("    far_channel: heater_drive\n", ""), "pin_allocation", "channel wall_heater"),
                (WALL_RECORD.replace("far_channel: heater_drive", "far_channel: heater_drive\n    rail: x"), "pin_allocation", "channel wall_heater"),
                (WALL_RECORD.replace("far_channel: heater_drive", "far_channel: heater_drive\n    controller_pin: PA0"), "pin_allocation", "channel wall_heater")):
            channels, problems = self.record(text)
            cases.append((problems, rule, name))
        nets = dict(WALL_NETS)
        nets["/PUMP"] = [("J1", "5", "Pin_5_5")]
        cases.append((self.connectivity(nets), "connectivity", "channel wall_pump"))
        nets = dict(WALL_NETS)
        nets["/HEATER"] = nets["/HEATER"] + [("U1", "7", "PA0_7")]
        cases.append((self.controller(nets, {"U1": {}}), "controller_part", "wall.kicad_sch U1"))
        for found, rule, name in cases:
            with self.subTest(rule=rule, name=name):
                self.assertTrue(found)
                self.assertTrue(any(line.startswith("VIOLATION | hardware/m/wall/wall.kicad_pro | " + rule + " | ") and name in line
                                    for line in self.lines(found)), self.lines(found))

    def test_a_far_channel_failure_names_the_rule_and_the_channel_in_the_report_line(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C5: The check's text report names, for each failing case of the pin allocation and connectivity rules, the rule and the channel or part, and a passing controller-less design reports no failure. The check has no machine-readable report, and none is added here. Failures of rules other than the pin allocation and connectivity rules are out of scope.
        yaml = board_check.require_yaml()
        channels = self.usable()
        found = board_check.far_channels(yaml, self.root, self.design, self.where, channels, [])
        self.assertEqual(len(found), 2)
        self.assertTrue(found[0].line().startswith("VIOLATION | hardware/m/wall/wall.kicad_pro | pin_allocation | "
                                                   "hardware/m/wall/pin-allocation.yaml channel wall_heater | channel wall_heater names far channel heater_drive"))

    def test_a_passing_controller_less_design_reports_no_failure(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C5: The check's text report names, for each failing case of the pin allocation and connectivity rules, the rule and the channel or part, and a passing controller-less design reports no failure. The check has no machine-readable report, and none is added here. Failures of rules other than the pin allocation and connectivity rules are out of scope.
        channels = self.usable()
        self.assertEqual(self.connectivity(WALL_NETS), [])
        self.assertEqual(self.controller(WALL_NETS, {"Q1": {"lcsc": "C1"}}), [])
        self.write("hardware/m/main/pin-allocation.yaml", MAIN_RECORD)
        others = board_check.other_designs_records(self.design, [self.design, board_check.Design("hardware/m/main/main.kicad_pro")],
                                                   {"hardware/m/main/pin-allocation.yaml"}, self.root, self.where)
        self.assertEqual([v.line() for v in board_check.far_channels(board_check.require_yaml(), self.root, self.design, self.where, channels, others)], [])

    def test_the_check_has_no_machine_readable_report(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C5: The check's text report names, for each failing case of the pin allocation and connectivity rules, the rule and the channel or part, and a passing controller-less design reports no failure. The check has no machine-readable report, and none is added here. Failures of rules other than the pin allocation and connectivity rules are out of scope.
        with self.assertRaises(SystemExit):
            board_check.main(["--format", "json"])
        with self.assertRaises(SystemExit):
            board_check.main(["--json"])


if __name__ == "__main__":
    unittest.main()
