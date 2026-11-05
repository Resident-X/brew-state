"""The main board's schematic and design records, read as the schematic leaf's criteria state them: the wall-board header and its channels, and the four design records."""
from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import board_check  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
BOARD = os.path.join(REPO, "hardware", "sunbeam-em7000", "main-board")
#: The channels the header carries to the wall board, each with the controller pin the pin allocation record gives it.
HEADER_CHANNELS = {"heat_c_drv": "PD2", "heat_s_drv": "PD3", "mains_pres_c": "PE15", "mains_pres_s": "PD7"}
RECORDS = ("pin-allocation.yaml", "parts-specification.yaml", "derating-policy.yaml", "pin-limits.yaml", "catalogue-extract.yaml")


def record(name):
    yaml = board_check.require_yaml()
    with open(os.path.join(BOARD, name), encoding="utf-8") as handle:
        return board_check.strict_yaml(yaml, handle.read())


def symbol_block(sheet, reference):
    """The text of the schematic symbol whose Reference property is `reference`, from its opening to the next symbol."""
    with open(os.path.join(BOARD, sheet), encoding="utf-8") as handle:
        text = handle.read()
    marker = f'(property "Reference" "{reference}"'
    start = text.index(marker)
    begin = text.rfind("\n\t(symbol\n", 0, start)
    end = text.find("\n\t(symbol\n", start)
    return text[begin:end if end > 0 else len(text)]


class WallBoardHeaderDrawn(unittest.TestCase):
    def test_the_ten_way_header_and_the_neutral_landing_are_drawn_and_each_crossing_channel_has_its_controller_pin(self):
        # SOL-HW-MAIN-BOARD-SCHEMATIC-PROVEN.C10: The ten-way low-voltage header to the wall board and the neutral return landing are drawn to the interface the division record fixes, and every channel crossing the header is listed in the pin allocation record with its controller pin, so the wall board's record can resolve to it. Comparing the cable between the two boards' headers pin for pin is out of scope.
        header = symbol_block("720-heater-led-drive-and-wall-board-header.kicad_sch", "J761")
        self.assertIn('(lib_id "Connector_Generic:Conn_01x10")', header)
        self.assertIn('(property "Value" "WB_LV10"', header)
        self.assertIn("PinHeader_1x10_P2.54mm_Vertical", header)
        landing = symbol_block("101-mains-entry-and-load-feed.kicad_sch", "J110")
        self.assertIn('(property "Value" "WB_RET"', landing)
        channels = {c["channel"]: c for c in record("pin-allocation.yaml")["channels"]}
        for channel, pin in HEADER_CHANNELS.items():
            with self.subTest(channel=channel):
                self.assertIn(channel, channels)
                self.assertEqual(channels[channel]["controller_pin"], pin)


class DesignRecordsAuthored(unittest.TestCase):
    def test_the_four_design_records_and_the_catalogue_extract_exist_and_the_extract_states_its_read_date_and_age_limit(self):
        # SOL-HW-MAIN-BOARD-SCHEMATIC-PROVEN.C5: The pin allocation record, the parts specification record, the derating policy record and the pin-limit record are authored for the board and the catalogue extract is current, so the connectivity and parts checks have records to hold the board to. The pre-order check passing on the finished layout, and comparing the cable between the two boards' headers pin for pin, are out of scope.
        for name in RECORDS:
            with self.subTest(record=name):
                self.assertTrue(os.path.isfile(os.path.join(BOARD, name)))
                self.assertTrue(record(name))
        extract = record("catalogue-extract.yaml")
        self.assertRegex(str(extract["read_on"]), r"^\d{4}-\d{2}-\d{2}$")
        self.assertIsInstance(extract["max_age_days"], int)
        self.assertGreater(extract["max_age_days"], 0)


if __name__ == "__main__":
    unittest.main()
