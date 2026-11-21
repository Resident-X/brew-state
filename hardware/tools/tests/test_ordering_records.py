#!/usr/bin/env python3
"""The pin-function reading of each board's order record, held against the records it was read from.

The reading is a table in the order record; this test reads the table back and holds every row to the pin allocation record
and the controller pin table, so a pin moved in either record, or a channel dropped from the reading, fails here and not at
the order.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

import yaml

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

MACHINE = os.path.join(os.path.dirname(TOOLS), "sunbeam-em7000")
#: What each need is judged by in the pin table's function text.
NEED_PATTERNS = {"timer output": r"TIM\d+_CH\d", "plain output": r"^GPIO output", "plain input": r"^GPIO input", "plain GPIO line": r"^GPIO\b",
                 "converter input": r"ADC", "timer-capture or edge-capable input": r"TIM\d+_CH\d|EXTI",
                 "serial bus pins": r"USART\d_|I2C\d_|SPI\d_|OTG_FS|SWDIO|SWCLK"}
#: The main board's port pins that carry no channel the firmware drives or reads: the crystals and the serial-wire output.
NOT_FIRMWARE_CHANNELS = {"hse_in", "hse_out", "lse_in", "lse_out", "swo"}


def reading(board: str):
    """The rows of the pin-function table of a board's order record: (channel, pin, listed function, need, verdict)."""
    with open(os.path.join(MACHINE, board, "ordering-record.md"), encoding="utf-8") as handle:
        text = handle.read()
    section = re.search(r"## Pin functions.*?(?=^## |\Z)", text, re.S | re.M).group(0)
    rows = []
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] not in ("Channel", "---"):
            rows.append(tuple(cells))
    return rows


def carries(row, table) -> bool:
    """Whether the pin table, read at the row's pin, shows the pin carrying the function the row says it needs: the row's listed
    function is the table's text for that pin exactly, and that text matches the need's pattern from its start."""
    channel, pin, listed, need, verdict = row
    return pin in table and table[pin] == listed and re.search(NEED_PATTERNS[need], table[pin]) is not None


def pin_table():
    found = {}
    with open(os.path.join(MACHINE, "main-board", "controller-pin-table.md"), encoding="utf-8") as handle:
        for line in handle:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 7 and re.match(r"\d+$", cells[0]):
                found[cells[1]] = cells[3]
    return found


def allocation(board: str):
    with open(os.path.join(MACHINE, board, "pin-allocation.yaml"), encoding="utf-8") as handle:
        return yaml.safe_load(handle)["channels"]


class ThePinFunctionReading(unittest.TestCase):
    """SOL-HW-CONTROLLER-BOARDS-ORDERED.C9: Each firmware channel's function is carried by the pin the board gives it, shown before payment"""

    def test_every_main_board_channel_is_read_at_the_pin_the_allocation_record_gives_it_and_carries_its_function(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C9: for every output, sensor and serial channel the firmware drives or reads, the controller pin table record is read at the pin the board gives that channel and shows the pin carries the function the channel needs
        pins = {c["channel"]: c["controller_pin"] for c in allocation("main-board") if c.get("controller_pin")}
        table = pin_table()
        rows = reading("main-board")
        self.assertEqual(sorted(row[0] for row in rows), sorted(set(pins) - NOT_FIRMWARE_CHANNELS),
                         "the reading names every channel with a controller pin, bar the crystals and the serial-wire output, once")
        for channel, pin, listed, need, verdict in rows:
            with self.subTest(channel=channel):
                self.assertEqual(pin, pins[channel], "the reading's pin is the allocation record's")
                self.assertEqual(table[pin], listed, "the listed function is the pin table's text for the pin, whole")
                self.assertRegex(table[pin], NEED_PATTERNS[need])
                self.assertEqual(verdict, "yes")

    def test_the_required_function_classes_are_each_read_on_the_channels_the_criterion_names(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C9: such as a timer output for each phase-controlled pump gate, a plain output for each heater drive, a converter input for each sensor, a timer-capture or edge-capable input for the supply crossing detection and the flow meter, and the bus pins for each serial link
        needs = {row[0]: row[3] for row in reading("main-board")}
        for channel in ("pump_s_gate", "pump_c_gate"):
            self.assertEqual(needs[channel], "timer output")
        for channel in ("heat_c_drv", "heat_s_drv"):
            self.assertEqual(needs[channel], "plain output")
        for channel in ("ntc_cof", "ntc_stm", "ntc_wand", "stmp_an", "brew_an", "curr1_an", "curr2_an"):
            self.assertEqual(needs[channel], "converter input")
        for channel in ("zc_in", "flow_in"):
            self.assertEqual(needs[channel], "timer-capture or edge-capable input")
        for channel in ("display_tx", "display_rx", "spi3_sck", "spi3_miso", "spi3_mosi", "stm_scl", "stm_sda"):
            self.assertEqual(needs[channel], "serial bus pins")

    def test_the_wall_boards_header_channels_are_read_at_the_main_boards_pins(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C9: Each firmware channel's function is carried by the pin the board gives it
        main = {c["channel"]: c["controller_pin"] for c in allocation("main-board") if c.get("controller_pin")}
        far = [c["far_channel"] for c in allocation("heater-wall-board") if c.get("far_channel")]
        rows = reading("heater-wall-board")
        self.assertEqual([row[0] for row in rows], far)
        for channel, pin, listed, need, verdict in rows:
            self.assertEqual(pin, main[channel])
            self.assertRegex(pin_table()[pin], NEED_PATTERNS[need])
            self.assertEqual(verdict, "yes")

    def test_a_channel_whose_pin_lacks_its_function_would_be_failed_by_the_reading(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C9: a channel whose pin does not carry its function stops the order
        table = {"PA8": "TIM1_CH1 AF1 (MCO1 is AF0)", "PE2": "GPIO (panel key/indicator line, owner D)",
                 "PB2": "GPIO output", "PA2": "USART2_TX AF7 or GPIO"}
        good = [("pump_s_gate", "PA8", table["PA8"], "timer output", "yes"), ("key1", "PE2", table["PE2"], "plain GPIO line", "yes"),
                ("buzzer", "PB2", table["PB2"], "plain output", "yes")]
        for row in good:
            self.assertTrue(carries(row, table), row)
        bad = [("pump_s_gate", "PB2", "GPIO output", "timer output", "yes"),
               ("key1", "PA8", table["PA8"], "plain GPIO line", "yes"),
               ("tx", "PA2", table["PA2"], "plain GPIO line", "yes"),
               ("key1", "PE2", "GPIO", "plain GPIO line", "yes"),
               ("key1", "PE9", "GPIO", "plain GPIO line", "yes"),
               ("buzzer", "PE2", table["PE2"], "plain output", "yes")]
        for row in bad:
            with self.subTest(row=row):
                self.assertFalse(carries(row, table), row)
        mutated = list(reading("main-board"))
        index = next(k for k, row in enumerate(mutated) if row[3] == "timer output")
        mutated[index] = mutated[index][:3] + ("plain output",) + mutated[index][4:]
        real = pin_table()
        self.assertTrue(all(carries(row, real) for row in reading("main-board")))
        self.assertFalse(all(carries(row, real) for row in mutated), "a row whose need the pin does not meet is failed")


def real_position_records():
    found = {}
    for board in ("main-board", "heater-wall-board"):
        with open(os.path.join(MACHINE, board, "parts-specification.yaml"), encoding="utf-8") as handle:
            found[board] = yaml.safe_load(handle)["positions"]
    return found


class TheRealBoardRecords(unittest.TestCase):
    """SOL-HW-CONTROLLER-BOARDS-ORDERED.C7 and .C4: record checks of the two boards' committed records, not tests of the tool."""

    def test_record_check_every_position_of_both_real_boards_states_who_fits_it(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: The parts specification records for every part whether the assembler or the owner fits it.
        import board_check
        for board, positions in real_position_records().items():
            self.assertTrue(positions)
            for entry in positions:
                if entry.get("fitted") == board_check.NOT_FITTED:
                    continue
                with self.subTest(board=board, reference=entry["reference"]):
                    self.assertIn(entry.get("fitted_by"), board_check.FITTED_BY_VALUES)

    def test_record_check_the_parts_list_of_both_real_boards_writes_with_one_comment_for_each_number(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: Each board's parts list gives one comment for each catalogue number
        import contextlib
        import csv
        import io
        import json
        import tempfile
        import production_files
        for board in ("main-board", "heater-wall-board"):
            folder = os.path.join(MACHINE, board)
            with self.subTest(board=board), tempfile.TemporaryDirectory() as out:
                stream = io.StringIO()
                none = os.path.join(out, "unavailable.yaml")
                with open(none, "w", encoding="utf-8") as handle:
                    handle.write("source: test\nread_on: 2030-01-02\nunavailable: []\n")
                with contextlib.redirect_stdout(stream):
                    status = production_files.main(["parts-list", "--unavailable", none, "--schematic", os.path.join(folder, f"{board}.kicad_sch"),
                                                    "--board", os.path.join(folder, f"{board}.kicad_pcb"),
                                                    "--fitting", os.path.join(folder, "parts-specification.yaml"),
                                                    "--catalogue", os.path.join(folder, "catalogue-extract.yaml"),
                                                    "--out", os.path.join(out, "list"), "--format", "json"])
                document = json.loads(stream.getvalue())
                self.assertEqual((status, document["result"]), (0, "WRITTEN"), document)
                for name in production_files.SET_FILES["parts"]:
                    with open(os.path.join(out, "list", name), encoding="utf-8", newline="") as handle:
                        rows = list(csv.reader(handle))[1:]
                    numbers = [row[3] for row in rows]
                    self.assertEqual(len(numbers), len(set(numbers)), f"{name}: one row for each catalogue number")
                    for row in rows:
                        self.assertTrue(row[0].strip(), f"{name}: {row[3]} has a comment")
                with open(os.path.join(folder, "catalogue-extract.yaml"), encoding="utf-8") as handle:
                    entries = yaml.safe_load(handle)["entries"]
                self.assertTrue(all(isinstance(e.get("comment"), str) and e["comment"].strip() for e in entries),
                                "every catalogue number of the extract carries a comment")

    def test_record_check_the_via_counts_and_layers_in_the_order_records_are_the_committed_layouts(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C4: the via sizes each board uses and its copper layer count, read from the committed layout
        import collections
        import sexpr
        for board, layers, rows in (("main-board", 6, {"0.60 / 0.30": 466, "0.70 / 0.30": 6, "0.75 / 0.30": 69}),
                                    ("heater-wall-board", 2, {"0.70 / 0.30": 1})):
            with open(os.path.join(MACHINE, board, f"{board}.kicad_pcb"), encoding="utf-8") as handle:
                tree = sexpr.parse_one(handle.read())
            copper = [x for x in sexpr.child(tree, "layers")[1:] if isinstance(x, list) and str(x[1]).endswith(".Cu")]
            counted = collections.Counter(f"{float(sexpr.child(v, 'size')[1]):.2f} / {float(sexpr.child(v, 'drill')[1]):.2f}"
                                          for v in sexpr.children(tree, "via"))
            with self.subTest(board=board):
                self.assertEqual(len(copper), layers)
                self.assertEqual(dict(counted), rows)
                with open(os.path.join(MACHINE, board, "ordering-record.md"), encoding="utf-8") as handle:
                    text = handle.read()
                self.assertIn(f"The board has {layers} copper layers.", text)
                for size, count in rows.items():
                    self.assertRegex(text, rf"\| {re.escape(size)} \| {count} \|")

if __name__ == "__main__":
    unittest.main()
