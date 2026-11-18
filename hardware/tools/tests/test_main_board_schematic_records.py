"""The main board's schematic and design records, read as the schematic leaf's criteria state them: the wall-board header and its channels, and the four design records."""
from __future__ import annotations

import os
import subprocess
import sys
import datetime
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import board_check  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
BOARD = os.path.join(REPO, "hardware", "sunbeam-em7000", "main-board")
#: The channels the header carries to the wall board, each with the controller pin the pin allocation record gives it.
HEADER_CHANNELS = {"heat_c_drv": "PD11", "heat_s_drv": "PD12", "mains_pres_c": "PE15", "mains_pres_s": "PB11"}
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


def schematic_pins(kicad_cli):
    """KiCad's own netlist of the whole main board schematic: net name -> the (reference, pin, pin function) it joins."""
    with tempfile.TemporaryDirectory() as folder:
        out = os.path.join(folder, "netlist.net")
        subprocess.run([kicad_cli, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out,
                        os.path.join(BOARD, "main-board.kicad_sch")], check=True, capture_output=True, timeout=300)
        with open(out, encoding="utf-8") as handle:
            nodes = board_check.schematic_pin_nodes(sexpr.parse_one(handle.read()))
    return {name: [(n.ref, n.pin, n.names()[0] if n.names() else "") for n in pins] for name, pins in nodes.items()}


def usb_findings(nets, selector_symbol):
    """What departs from the panel-cable USB connection the criterion describes, read from a net -> pins map."""
    found = []
    where = {(ref, pin): name for name, pins in nets.items() for ref, pin, _ in pins}
    members = lambda name: {(ref, pin) for ref, pin, _ in nets.get(name, [])}  # noqa: E731
    controller = lambda name: {function.split("_")[0] for ref, _, function in nets.get(name, []) if ref == "U401"}  # noqa: E731
    for net, port, header, clamp in (("/Controller/USB_DP", "PA12", "1", ("1", "6")), ("/Controller/USB_DM", "PA11", "2", ("3", "4"))):
        if port not in controller(net):
            found.append(f"{net} does not reach the controller's {port}")
        if where.get(("J402", header)) != net:
            found.append(f"J402 pin {header} is not on {net}")
        for pin in clamp:
            if where.get(("D401", pin)) != net:
                found.append(f"D401 pin {pin} (data-line protection) is not on {net}")
    if where.get(("D401", "2")) != "GND" or where.get(("D401", "5")) != "/Controller/USB_VBUS":
        found.append("D401 is not between the cable supply and ground")
    if members("/Controller/USB_SHIELD") != {("J402", "4"), ("R403", "1"), ("C419", "1")}:
        found.append("the shield net joins something beyond J402 pin 4, R403 and C419, or lacks one of them")
    if where.get(("R403", "2")) != "GND" or where.get(("C419", "2")) != "GND":
        found.append("R403 and C419 in parallel do not both return the shield to ground")
    if where.get(("J402", "3")) != "GND":
        found.append("J402 pin 3 is not ground")
    if "Connector_Generic:Conn_01x03" not in selector_symbol:
        found.append("JP301 is not a three-pin selector header (a bridged jumper symbol would join two pins)")
    rails = {1: "/Logic supply/+5V_MOD", 2: "+5V", 3: "/USB_VBUS_F"}
    for pin, rail in rails.items():
        if where.get(("JP301", str(pin))) != rail:
            found.append(f"JP301 pin {pin} is not on {rail}")
    for ref in {ref for pins in nets.values() for ref, _, _ in pins} - {"JP301"}:
        touched = {name for name in rails.values() if any(r == ref for r, _, _ in nets.get(name, []))}
        if len(touched) > 1:
            found.append(f"{ref} joins {sorted(touched)}, a path round the selector between the module and the cable supply")
    if where.get(("F401", "1")) != "/Controller/USB_VBUS" or where.get(("F401", "2")) != "/USB_VBUS_F":
        found.append("F401 is not between the cable supply and the selector")
    if where.get(("J402", "5")) != "/Controller/USB_VBUS" or where.get(("D402", "1")) != "/Controller/USB_VBUS" or where.get(("D402", "2")) != "GND":
        found.append("the surge part D402 does not clamp the cable supply to ground ahead of the fuse")
    for pin, net, port in (("2", "/Controller/SWDIO", "PA13"), ("4", "/Controller/SWCLK", "PA14")):
        if where.get(("J401", pin)) != net or port not in controller(net):
            found.append(f"the debug header J401 pin {pin} does not reach {port} on {net}")
    if where.get(("J401", "3")) != "GND":
        found.append("the debug header has no ground pin")
    return found


SUPPLY_AND_RETURN = {"+5V_WB", "GND"}


def header_crossings(nets, channels):
    """What departs from the header listing, read from a net -> pins map and the pin allocation channels.

    Every net on a J761 pin is a signal net the listing must account for, except the wall board's supply +5V_WB and
    the return GND (they carry no controller channel) and a pin left unconnected (KiCad's "unconnected-" net, which
    joins nothing else). A channel reaches the header from its controller net by crossing parts one at a time: a
    series part (exactly two pins) to its other net, and a three-pin transistor only from its gate to its drain (the
    one explicit rule; its source and any other path are not followed). The walk never enters or leaves through the
    controller, the header or a supply or return net (+5V_WB, GND, or any net of more than ten pins), so a part
    shared with a rail joins nothing. The mapping is one to one: each listed header channel reaches exactly one header
    signal net, and each header signal net is reached from exactly one listed channel.
    """
    pins_of = lambda name: nets.get(name, [])  # noqa: E731
    parts = {}
    for name, pins in nets.items():
        for ref, pin, function in pins:
            parts.setdefault(ref, []).append((name, pin, function))
    rails = {name for name, pins in nets.items() if len(pins) > 10 or name.split("/")[-1] in SUPPLY_AND_RETURN}

    def crossings(ref, name):
        joined = parts[ref]
        if len(joined) == 2:
            return [other for other, _, _ in joined if other != name or joined[0][0] == joined[1][0]][:1]
        if len(joined) == 3 and ref.startswith("Q"):
            gates = {n for n, _, function in joined if function == "G"}
            drains = [n for n, _, function in joined if function == "D"]
            return drains if name in gates else []
        return []

    def reach(start):
        seen, todo = {start}, [start]
        while todo:
            name = todo.pop()
            for ref, _, _ in pins_of(name):
                if ref in ("U401", "J761"):
                    continue
                for other in crossings(ref, name):
                    if other not in seen and other not in rails:
                        seen.add(other)
                        todo.append(other)
        return seen

    header = {name for name, pins in nets.items() if any(p[0] == "J761" for p in pins)}
    signals = {name for name in header if name.split("/")[-1] not in SUPPLY_AND_RETURN and not name.startswith("unconnected-")}
    channel_net = {key: "/" + c["net"] if "/" + c["net"] in nets else c["net"] for key, c in channels.items()}
    reached = {key: reach(channel_net[key]) & signals for key in HEADER_CHANNELS if key in channel_net}
    found = []
    for name in sorted(signals):
        owners = sorted(key for key, got in reached.items() if name in got)
        if not owners:
            found.append(f"{name} is on the header and no channel's net reaches it")
        elif len(owners) > 1:
            found.append(f"{name} is on the header and is reached from more than one channel: {owners}")
    for channel in HEADER_CHANNELS:
        got = reached.get(channel, set())
        if not got:
            found.append(f"{channel}'s net {channels.get(channel, {}).get('net')} does not reach the header")
        elif len(got) > 1:
            found.append(f"{channel} reaches more than one header signal net: {sorted(got)}")
    return found


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
        # The drawn header and landing, and each listed channel's controller pin, as KiCad's own netlist joins them.
        nets = schematic_pins(os.environ.get("KICAD_CLI", "kicad-cli"))
        where = {(ref, pin): name for name, pins in nets.items() for ref, pin, _ in pins}
        header_nets = {"1": "+5V_WB", "4": "GND", "2": "HEAT_C_LED_K", "3": "HEAT_S_LED_K",
                       "5": "MAINS_PRES_C_J", "6": "MAINS_PRES_S_J"}
        for pin, name in header_nets.items():
            with self.subTest(header_pin=pin):
                self.assertEqual(where.get(("J761", pin), "").split("/")[-1], name)
        self.assertEqual(where.get(("J110", "1")), "/NEUTRAL")
        for channel, pin in HEADER_CHANNELS.items():
            with self.subTest(controller_net=channel):
                joined = [p for p in nets["/" + channels[channel]["net"]] if p[0] == "U401"]
                self.assertEqual([function.split("_")[0] for _, _, function in joined], [pin])
        # Every signal net on the header's ten pins is a channel of the record (through the series part to its net field)
        # or a named supply or return net, +5V_WB and GND, which carry no controller channel; each listed header channel's
        # net reaches J761, not only U401.
        self.assertEqual(header_crossings(nets, channels), [])
        # Synthetic faults: an unlisted net on a header pin, then a channel whose net field names a net off the header.
        extra = {name: list(pins) for name, pins in nets.items()}
        extra["UNLISTED_CH"] = [("J761", "8", ""), ("R999", "1", "")]
        self.assertTrue(header_crossings(extra, channels))
        extra = {name: [p for p in pins if p[:2] != ("J761", "7")] for name, pins in nets.items()}
        extra["/Sheet/UNLISTED_PIN7"] = [("J761", "7", "")]
        self.assertTrue(header_crossings(extra, channels))
        # Synthetic faults on the walk itself: an unlisted header net joined by a series part to a listed channel's net,
        # and an unlisted header net joined by a part to +5V_WB (which no channel's walk may cross).
        for listed in ("/MAINS_PRES_C", "/HEAT_C_DRV"):
            extra = {name: [p for p in pins if p[:2] != ("J761", "8")] for name, pins in nets.items()}
            extra["UNLISTED_CH"] = [("J761", "8", ""), ("R999", "1", "")]
            extra[listed] = extra[listed] + [("R999", "2", "")]
            self.assertTrue(header_crossings(extra, channels), listed)
        extra = {name: [p for p in pins if p[:2] != ("J761", "8")] for name, pins in nets.items()}
        extra["UNLISTED_CH"] = [("J761", "8", ""), ("R998", "1", "")]
        extra["+5V_WB"] = extra["+5V_WB"] + [("R998", "2", "")]
        self.assertTrue(header_crossings(extra, channels))
        extra = {name: list(pins) for name, pins in nets.items()}
        extra["+5V_WB"] = extra["+5V_WB"] + [("R997", "1", "")]
        extra["/MAINS_PRES_C"] = extra["/MAINS_PRES_C"] + [("R997", "2", "")]
        extra["/Sheet/UNLISTED_PIN9"] = [("J761", "9", ""), ("R996", "1", "")]
        extra["/MAINS_PRES_S"] = extra["/MAINS_PRES_S"] + [("R996", "2", "")]
        self.assertTrue(header_crossings(extra, channels))
        wrong = {name: dict(c) for name, c in channels.items()}
        wrong["heat_c_drv"]["net"] = "HEAT_C_DRV_TYPO"
        self.assertTrue(header_crossings(nets, wrong))


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
        # The extract and the two records the check reads in a form of their own are read by the check's own readers,
        # with no violation, and the extract's age is held by the check's own rule against a fixed injected today.
        yaml = board_check.require_yaml()
        rel = os.path.relpath(BOARD, REPO).replace(os.sep, "/")
        design = board_check.Design(f"{rel}/main-board.kicad_pro")
        repository = board_check.Repository(REPO, {f"{rel}/{name}" for name in RECORDS})
        read_on = board_check.iso_date(str(extract["read_on"]))
        limit = extract["max_age_days"]
        self.assertEqual(board_check.load_derating(yaml, REPO, repository, design, False)[1], [])
        self.assertEqual(board_check.load_pin_limits(yaml, REPO, repository, design, False)[1], [])

        def extract_problems(today):
            got, problems = board_check.read_extract(yaml, REPO, repository, design, today, False)
            self.assertIsNotNone(got)
            return [v for v in problems if v.rule == "parts_catalogue" and "read_on" in v.location]

        day = datetime.timedelta(days=1)
        self.assertEqual(extract_problems(read_on + datetime.timedelta(days=limit)), [])
        self.assertEqual(extract_problems(read_on), [])
        self.assertTrue(extract_problems(read_on + datetime.timedelta(days=limit) + day), "an extract one day past its limit")
        self.assertTrue(extract_problems(read_on - day), "an extract dated later than today")


class PanelCableUsbDrawn(unittest.TestCase):
    def test_the_panel_cable_usb_connection_is_drawn_with_its_protection_shield_path_and_three_way_selector(self):
        # SOL-HW-MAIN-BOARD-SCHEMATIC-PROVEN.C11: The schematic carries a panel-cable connection from the controller's full-speed USB port to a panel-mounted connector on the side of the machine, with ESD protection on the data lines and the shield, and the serial-wire debug header is kept. The shield reaches controller ground only through a resistor and capacitor in parallel. A three-way selector joins the board's 5 V rail to either the cable's supply or the logic supply module, never both, so the board can run from the cable with mains off for bench work, never sources current into a computer's port, and with the selector on the module the cable carries data only while mains is connected. The cable position is a bench state with mains off: a plug-in transient up to the clamp level of the surge part on the cable path is accepted, and that transient can damage only the relay-driver buffers, whose failure leaves the safety relay open. With mains connected and a computer on the cable, no current path joins a mains-referenced net to a conductor of the cable beyond what the signed separation basis allows. The supply budget of a standard USB port and the hold-off of every load on cable power are shown. Placing the panel connector and the firmware's USB handling are out of scope.
        nets = schematic_pins(os.environ.get("KICAD_CLI", "kicad-cli"))
        selector = symbol_block("30-logic-supply.kicad_sch", "JP301")
        self.assertEqual(usb_findings(nets, selector), [])
        channels = {c["channel"]: c for c in record("pin-allocation.yaml")["channels"]}
        for channel, port, pin in (("usb_dm", "PA11", "2"), ("usb_dp", "PA12", "1")):
            with self.subTest(channel=channel):
                self.assertEqual((channels[channel]["controller_pin"], channels[channel]["connector"], channels[channel]["connector_pin"]), (port, "J402", pin))
        with open(os.path.join(BOARD, "circuit-proof.md"), encoding="utf-8") as handle:
            rows = [line for line in handle if line.startswith("| USB power: supply budget, bench state, F401 and the cable |")]
        self.assertEqual(len(rows), 1)
        self.assertIn("0.500 A", rows[0])
        self.assertIn("0.3359 A", rows[0])

        def without(ref, pin):
            return {name: [p for p in pins if p[:2] != (ref, pin)] for name, pins in nets.items()}

        def moved(ref, pin, name):
            copy = without(ref, pin)
            copy[name] = copy[name] + [(ref, pin, "")]
            return copy

        bridge = {name: list(pins) for name, pins in nets.items()}
        bridge["/Logic supply/+5V_MOD"] = bridge["/Logic supply/+5V_MOD"] + [("R999", "1", "")]
        bridge["/USB_VBUS_F"] = bridge["/USB_VBUS_F"] + [("R999", "2", "")]
        faults = {
            "shield resistor removed": without("R403", "1"),
            "shield capacitor removed": without("C419", "1"),
            "shield tied to ground": moved("J402", "4", "GND"),
            "selector bridged by a part between module and cable": bridge,
            "selector pin 3 on the 5 V rail": moved("JP301", "3", "+5V"),
            "data-line protection removed": without("D401", "1"),
            "surge part removed from the cable supply": without("D402", "1"),
            "fuse removed from the cable supply": without("F401", "2"),
            "debug clock pin lost": without("J401", "4"),
        }
        for fault, broken in faults.items():
            with self.subTest(fault=fault):
                self.assertTrue(usb_findings(broken, selector), fault)
        self.assertTrue(usb_findings(nets, selector.replace("Connector_Generic:Conn_01x03", "Jumper:SolderJumper_3_Bridged12")))


if __name__ == "__main__":
    unittest.main()
