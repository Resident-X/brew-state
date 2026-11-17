"""The main board's seven BAT54SW,115 clamps, R301 and the board's assembled side, read from the committed board and records as the solution's criteria state them."""
from __future__ import annotations

import copy
import datetime
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
import board_check  # noqa: E402
import board_geometry  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
FOLDER = os.path.join("hardware", "sunbeam-em7000", "main-board")
BOARD = os.path.join(REPO, FOLDER)
PROJECT = os.path.join(FOLDER, "main-board.kicad_pro")
LAYOUT = os.path.join(BOARD, "main-board.kicad_pcb")

CLAMPS = ("D502", "D504", "D506", "D523", "D524", "D527", "D528")
OLD_NUMBER = "C47546"
NEW_NUMBER = "C78606"
MPN = "BAT54SW,115"
FOOTPRINT = "SOT-323_SC-70"
#: Each clamp's supply net and signal node, as the schematic carries them; pad 1 is GND on all seven.
SUPPLY = {"D502": "+3V3A", "D504": "+3V3A", "D506": "+3V3A", "D523": "+3V3", "D524": "+3V3", "D527": "+3V3", "D528": "+3V3"}
SIGNAL = {"D502": "NTC_COF", "D504": "NTC_STM", "D506": "NTC_WAND", "D523": "STM_SCL", "D524": "STM_SDA",
          "D527": "BREW_SCL", "D528": "BREW_SDA"}
FRONT = ("D502", "D506", "R301")
#: How near a poured zone's filled copper must come to a pad, in mm, to touch it.
FILL_CONTACT_MM = 0.01
KEEP_CLEAR_MM = 10.0

#: The maker's sheet of the swapped part: Nexperia BAT54W series, product data sheet, Rev. 3, 20 November 2012
#: (https://www.lcsc.com/datasheet/lcsc_datasheet_2407241045_Nexperia-BAT54SW-115_C78606.pdf, the file behind it
#: datasheet.lcsc.com/datasheet/pdf/2d3d1fa2dfdc64e7bd0483bee1291320.pdf, 10 pages, read with pdftotext).
#: Table 7 (page 4), per diode, Tamb = 25 degC, pulse test tp <= 300 us, delta <= 0.02: VF maxima by IF, IR at VR = 25 V, Cd at 1 MHz, VR = 1 V.
SHEET_VF_MAX_V = {0.1e-3: 0.240, 1e-3: 0.320, 10e-3: 0.400, 30e-3: 0.500, 100e-3: 0.800}
SHEET_IR_MAX_A = 2e-6
SHEET_CD_MAX_F = 10e-12
#: Table 5 (page 3), limiting values: VR and IF per diode; Ptot per device, one diode loaded, Tamb <= 25 degC, on FR4 with single-sided copper.
SHEET_VR_MAX_V = 30.0
SHEET_IF_MAX_A = 0.2
SHEET_PTOT_MW = 200.0
#: Table 2 (page 2), the BAT54SW pinning: pin 1 anode of diode 1, pin 2 cathode of diode 2, pin 3 cathode of diode 1 and anode of diode 2.
SHEET_PINS = {"1": "anode (diode 1)", "2": "cathode (diode 2)", "3": "common"}
#: The names the repository's BAT54S-family symbol gives those functions (its pin names in KiCad's netlist: A, K, COM).
SYMBOL_PIN_OF_FUNCTION = {"anode (diode 1)": "A", "cathode (diode 2)": "K", "common": "COM"}
#: Diode model of the clamp decks, which the decks' own comment says is fitted to the Table 7 maxima, and the room it may sit below one in volts (rounding of the fit).
FIT_ROOM_V = 0.001
THERMAL_VOLTAGE_V = 0.025852


# --- Reading the board and the records --------------------------------------------------------


def read_tree(path=LAYOUT):
    with open(path, encoding="utf-8") as handle:
        return sexpr.parse_one(handle.read())


def footprints(tree):
    return board_check.board_footprints(tree)


def layer_of(footprint):
    layer = sexpr.child(footprint, "layer")
    return str(layer[1]) if layer is not None and len(layer) > 1 else "F.Cu"


def properties(footprint):
    found = {}
    for prop in sexpr.children(footprint, "property"):
        if len(prop) > 2:
            found[str(prop[1])] = str(prop[2])
    return found


def library_item(footprint):
    return str(footprint[1]).split(":")[-1]


def pads_of(tree, reference):
    return board_geometry.footprint_pads(footprints(tree)[reference], board_geometry.net_table(tree))


def pad_nets(tree, reference):
    return {pad.number: pad.net for pad in pads_of(tree, reference)}


def bare(net):
    """A net's name without the sheet path KiCad puts before a sheet-local one."""
    return net.rsplit("/", 1)[-1]


def read_text(*parts):
    with open(os.path.join(BOARD, *parts), encoding="utf-8") as handle:
        return handle.read()


def record(name):
    yaml = board_check.require_yaml()
    return board_check.strict_yaml(yaml, read_text(name))


def kicad_cli():
    found = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli")
    if not found:
        raise RuntimeError("kicad-cli is needed to read the schematic's netlist: set KICAD_CLI to it")
    return found


def schematic_netlist():
    """KiCad's own netlist of the main board's schematic: the parts and the nets as the schematic draws them."""
    with tempfile.TemporaryDirectory() as work:
        out = os.path.join(work, "board.net")
        done = subprocess.run([kicad_cli(), "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out,
                               os.path.join(BOARD, "main-board.kicad_sch")], capture_output=True, text=True, timeout=240)
        if done.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError(f"kicad-cli could not export the netlist: {done.stderr or done.stdout}")
        with open(out, encoding="utf-8") as handle:
            return sexpr.parse_one(handle.read())


_NETLIST_CACHE = []


def cached_netlist():
    """The schematic's netlist, exported once for the whole module."""
    if not _NETLIST_CACHE:
        _NETLIST_CACHE.append(schematic_netlist())
    return _NETLIST_CACHE[0]


def schematic_parts(netlist):
    """Each part of the netlist by reference: its footprint, description and the fields it carries."""
    parts = {}
    for group in board_check.walk(netlist, "components"):
        for comp in sexpr.children(group, "comp"):
            ref = str(sexpr.child(comp, "ref")[1])
            fields = {}
            for field in sexpr.children(sexpr.child(comp, "fields") or [], "field"):
                name = sexpr.child(field, "name")
                if name is not None and len(field) > 2:
                    fields[str(name[1])] = str(field[2])
            footprint = sexpr.child(comp, "footprint")
            description = sexpr.child(comp, "description")
            parts[ref] = {"footprint": str(footprint[1]) if footprint is not None else "",
                          "description": str(description[1]) if description is not None and len(description) > 1 else "",
                          "fields": fields}
    return parts


def schematic_pin_nets(netlist):
    """(reference, pin number) -> the net the schematic gives that pin."""
    nets = {}
    for name, pins in board_check.schematic_pin_nodes(netlist).items():
        for pin in pins:
            nets[(pin.ref, pin.pin)] = name
    return nets


def tracked_files():
    done = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True)
    return done.stdout.split("\n")


def design():
    return board_check.Design(PROJECT)


def repository():
    return board_check.Repository(REPO, tracked_files())


# --- The checks, each a function of what it reads so a synthetic fault can be fed to it --------------


def assembled_on_back(tree):
    """The assembled surface-mount parts standing on B.Cu: not left out of the position file, not a fiducial."""
    found = []
    for reference, footprint in footprints(tree).items():
        attributes = sexpr.child(footprint, "attr") or []
        if layer_of(footprint) == "B.Cu" and "smd" in attributes and "exclude_from_pos_files" not in attributes \
                and not board_check.fiducial_pads(footprint):
            found.append(reference)
    return sorted(found)


def back_fiducials(tree):
    return sorted(reference for reference, footprint in footprints(tree).items()
                  if layer_of(footprint) == "B.Cu" and board_check.fiducial_pads(footprint))


def back_non_test_points(tree):
    """The footprints on B.Cu that are not a test point pad."""
    return sorted(reference for reference, footprint in footprints(tree).items()
                  if layer_of(footprint) == "B.Cu" and not library_item(footprint).startswith("TestPoint_Pad"))


def side_problems(tree):
    problems = [f"{reference} is an assembled surface-mount part on B.Cu" for reference in assembled_on_back(tree)]
    problems += [f"{reference} is on B.Cu and is not a test point pad" for reference in back_non_test_points(tree)]
    problems += [f"{reference} is a fiducial on the back side" for reference in back_fiducials(tree)]
    problems += [f"{reference} is not on F.Cu" for reference in FRONT if layer_of(footprints(tree)[reference]) != "F.Cu"]
    problems += [f"{v.rule}: {v.location}" for v in board_check.missing_fiducials(design(), tree)]
    return problems


def courtyard_problems(tree, references):
    """Each reference whose courtyard overlaps or touches another part's, on the side it stands on."""
    held = footprints(tree)
    problems = []
    for reference in references:
        side = "F" if layer_of(held[reference]) == "F.Cu" else "B"
        yard = board_check.courtyard(held[reference], side, reference)
        if yard is None:
            problems.append(f"{reference} draws no courtyard")
            continue
        for other, footprint in held.items():
            if other == reference or layer_of(footprint) != layer_of(held[reference]):
                continue
            theirs = board_check.courtyard(footprint, side, other)
            if theirs is not None and board_check.polygon_gap(yard, theirs) <= 0:
                problems.append(f"the courtyard of {reference} meets that of {other}")
    return problems


def clamp_board_problems(tree, parts, pin_nets):
    """Every way the seven clamps on the board differ from what C2 states, against the schematic's parts and pin nets."""
    held = footprints(tree)
    problems = []
    for reference in CLAMPS:
        footprint = held.get(reference)
        if footprint is None:
            problems.append(f"{reference} is not on the board")
            continue
        board = properties(footprint)
        symbol = parts[reference]
        if layer_of(footprint) != "F.Cu":
            problems.append(f"{reference} is not on F.Cu")
        if library_item(footprint) != FOOTPRINT:
            problems.append(f"{reference} has footprint {library_item(footprint)}")
        if board.get("LCSC") != NEW_NUMBER or board.get("MPN") != MPN:
            problems.append(f"{reference} carries {board.get('LCSC')} / {board.get('MPN')} on the board")
        if OLD_NUMBER in sexpr.dump(footprint) or OLD_NUMBER in symbol["fields"].values():
            problems.append(f"{reference} still carries {OLD_NUMBER}")
        if symbol["footprint"].split(":")[-1] != library_item(footprint):
            problems.append(f"{reference} footprint differs: schematic {symbol['footprint']}, board {library_item(footprint)}")
        for name in ("LCSC", "MPN"):
            if symbol["fields"].get(name) != board.get(name):
                problems.append(f"{reference} {name} differs: schematic {symbol['fields'].get(name)}, board {board.get(name)}")
        if symbol["description"] != board.get("Description"):
            problems.append(f"{reference} description differs: schematic {symbol['description']}, board {board.get('Description')}")
        nets = pad_nets(tree, reference)
        wanted = {"1": "GND", "2": SUPPLY[reference], "3": SIGNAL[reference]}
        for number, name in wanted.items():
            if bare(nets.get(number, "")) != name:
                problems.append(f"{reference} pad {number} is on {nets.get(number)!r}, not {name}")
            if nets.get(number) != pin_nets.get((reference, number)):
                problems.append(f"{reference} pad {number} is on {nets.get(number)!r}, the schematic's pin {number} on {pin_nets.get((reference, number))!r}")
    return problems


def pad_touches(pad, tree, net):
    """Whether a track or via of the pad's own net reaches the pad's copper, on the board's own geometry."""
    table = board_geometry.net_table(tree)
    for node in tree:
        kind = sexpr.head(node)
        if kind not in ("segment", "via", "arc") or board_geometry.item_net(node, table, kind) != net:
            continue
        width = board_geometry.number(sexpr.child(node, "width" if kind != "via" else "size"), 1, kind)
        if kind == "via":
            if board_geometry.end_reaches(pad, board_geometry.xy(sexpr.child(node, "at"), "a via"), width):
                return True
            continue
        layer = str(sexpr.child(node, "layer")[1])
        if not pad.on(layer):
            continue
        start, end = board_geometry.xy(sexpr.child(node, "start"), kind), board_geometry.xy(sexpr.child(node, "end"), kind)
        if board_geometry.joins(pad, [start, end], width):
            return True
    return in_fill(pad, tree, net)


def in_fill(pad, tree, net):
    """Whether a poured zone of the pad's net, on a layer the pad has copper on, has its filled copper touching the pad."""
    table = board_geometry.net_table(tree)
    outline = pad.outline()
    for node in tree:
        if sexpr.head(node) != "zone" or board_geometry.item_net(node, table, "a zone") != net:
            continue
        for fill in sexpr.children(node, "filled_polygon"):
            layer = sexpr.child(fill, "layer")
            if layer is None or not pad.on(str(layer[1])):
                continue
            points = [board_geometry.xy(point, "a zone fill") for group in sexpr.children(fill, "pts") for point in sexpr.children(group, "xy")]
            if points and board_geometry.polygon_distance(outline, points) <= FILL_CONTACT_MM:
                return True
    return False


def unjoined_pads(tree, references):
    """Each pad of the references with no track or via of its own net reaching it, as 'REF pad N (net)'."""
    found = []
    for reference in references:
        for pad in pads_of(tree, reference):
            if not pad.net or not pad_touches(pad, tree, pad.net):
                found.append(f"{reference} pad {pad.number} ({pad.net or 'no net'})")
    return found


def exempted(rules, crystal):
    """The references the rule that keeps parts clear of `crystal` exempts, read from its one condition."""
    found = set()
    for rule in rules:
        text = board_check.sole_rule_form(rule)
        if text is not None and re.match(rf"A\.Reference == '{crystal}'", text):
            found |= set(re.findall(r"B\.Reference != '([^']+)'", text))
    return found


def keep_clear_problems(tree, rules):
    held = footprints(tree)
    problems = []
    if layer_of(held["R301"]) != "F.Cu":
        problems.append("R301 is not on F.Cu")
    gap = board_check.polygon_gap(board_check.courtyard(held["R301"], "F", "R301"), board_check.courtyard(held["Y401"], "F", "Y401"))
    if gap < KEEP_CLEAR_MM:
        problems.append(f"the courtyard of R301 is {gap:.2f} mm from that of Y401, under {KEEP_CLEAR_MM:g} mm")
    if "R301" in exempted(rules, "Y401"):
        problems.append("the Y401 keep-clear rule exempts R301")
    problems += [v.message for v in board_check.crystal_keep_clear(design(), rules, tree)]
    return problems


def r301_copper_problems(tree):
    problems = [f"R301 {pad}" for pad in unjoined_pads(tree, ["R301"])]
    nets = {pad.net for pad in pads_of(tree, "R301")}
    if {bare(net) for net in nets} != {"+3V3A_FB", "+3V3A"}:
        problems.append(f"R301 is on {sorted(nets)}")
    table = board_geometry.net_table(tree)
    pads = pads_of(tree, "R301")
    for node in tree:
        if sexpr.head(node) not in ("segment", "arc") or str(sexpr.child(node, "layer")[1]) != "B.Cu":
            continue
        if board_geometry.item_net(node, table, "a track") not in nets:
            continue
        ends = [board_geometry.xy(sexpr.child(node, "start"), "a track"), board_geometry.xy(sexpr.child(node, "end"), "a track")]
        if any(board_geometry.end_reaches(pad, end, 0.0) for pad in pads for end in ends):
            problems.append(f"copper of {board_geometry.item_net(node, table, 'a track')} on B.Cu ends on a pad of R301")
    return problems


def unresolved_clamps(limits, placed, netlist_pins):
    """The clamps the pin-limit check would evaluate against no entry, or against an entry that lacks one of the part's pins."""
    entries = {str(part["lcsc"]).strip(): part for part in limits["parts"]}
    found = []
    for reference in CLAMPS:
        number = ((placed.get(reference) or {}).get("lcsc") or "").strip()
        entry = entries.get(number)
        if entry is None:
            found.append(f"{reference} ({number or 'no LCSC number'}) has no pin-limit entry")
            continue
        listed = {str(pin["pin"]) for pin in entry["pins"]}
        for pin in netlist_pins.get(reference, ()):
            if pin not in listed:
                found.append(f"{reference} pin {pin} is listed by no pin of the entry for {number}")
    return found


def uncommented(name, text, folder=None):
    """The lines of a record that are not whole-line comments, for the formats that have them.

    The circuit-proof decks and generators are read whole, comments included, so no comment there may still name the old part. The yaml
    records keep their comment exemption: pin-limits.yaml and catalogue-extract.yaml each carry one historical comment explaining the replaced part.
    """
    if folder == "circuit-proof":
        return text.split("\n")
    if name.endswith((".yaml", ".py", ".cir")):
        return [line for line in text.split("\n") if not line.lstrip().startswith(("#", "*"))]
    return text.split("\n")


RECORD_FILES = [(name,) for name in ("parts-specification.yaml", "schematic-spec.yaml", "pin-limits.yaml", "catalogue-extract.yaml",
                                     "circuit-verdicts.md", "traceability.md", "derating-policy.yaml")]
RECORD_FILES += [("sheets", name) for name in sorted(os.listdir(os.path.join(BOARD, "sheets")))]
RECORD_FILES += [("circuit-proof", name) for name in sorted(os.listdir(os.path.join(BOARD, "circuit-proof")))
                 if name.startswith("C_") and name.endswith((".py", ".cir"))]


def old_number_lines(files=None):
    """Every non-comment line of the records that names the old number, as file:line."""
    found = []
    for path in files or RECORD_FILES:
        for number, line in enumerate(uncommented(path[-1], read_text(*path), path[0] if len(path) > 1 else None), 1):
            if OLD_NUMBER in line:
                found.append(f"{'/'.join(path)}:{number}")
    return found


def verdict_rows(text):
    return [line for line in text.split("\n") if re.match(r"\| (D\d{3}) \(", line)]


def row_problems(text, rows_of=verdict_rows):
    """Clamp rows of the circuit verdicts that do not name BAT54SW and C78606, and rows naming C78606 for another reference."""
    problems = []
    for row in rows_of(text):
        reference = re.match(r"\| (D\d{3}) \(", row).group(1)
        if reference in CLAMPS:
            if "BAT54SW" not in row.split("|")[1] or NEW_NUMBER not in row.split("|")[1] or OLD_NUMBER in row:
                problems.append(f"{reference}: {row.split('|')[1].strip()}")
        elif NEW_NUMBER in row.split("|")[1]:
            problems.append(f"{reference} names {NEW_NUMBER} but is not a clamp of the seven")
    return problems


def traceability_problems(text):
    problems = []
    for line in text.split("\n"):
        if OLD_NUMBER in line:
            problems.append(f"names {OLD_NUMBER}: {line[:60]}")
        for match in re.finditer(r"\b(D5\d\d)\b[^|]{0,6}?BAT54S(?!W)", line):
            problems.append(f"{match.group(1)} is paired with BAT54S, not BAT54SW")
    return problems


def part_entry_problems(entries, key, number_key):
    """The entries of a per-reference record that name C78606: they are the seven and each carries what C2 and C5 state."""
    problems = []
    named = {entry[key] for entry in entries if str(entry.get(number_key)) == NEW_NUMBER}
    if named != set(CLAMPS):
        problems.append(f"entries naming {NEW_NUMBER}: {sorted(named)}")
    for entry in entries:
        if entry.get(key) in CLAMPS and (str(entry.get(number_key)) != NEW_NUMBER or "BAT54SW" not in str(entry.get("value"))
                                         or FOOTPRINT not in str(entry.get("package") or entry.get("footprint"))):
            problems.append(f"{entry.get(key)} reads {entry.get(number_key)} / {entry.get('value')}")
    return problems


def sheet_entries():
    found = []
    for name in sorted(os.listdir(os.path.join(BOARD, "sheets"))):
        data = record(os.path.join("sheets", name))
        found += [entry for entry in (data.get("parts") if isinstance(data, dict) and "parts" in data else
                                      data.get("symbols") if isinstance(data, dict) and "symbols" in data else data
                                      if isinstance(data, list) else [])]
    return found


# --- The sheet comparison (C6) -----------------------------------------------------------------


def model_voltage(current, saturation=7.793e-9, emission=1.04, resistance=3.6):
    return emission * THERMAL_VOLTAGE_V * math.log(current / saturation + 1) + current * resistance


def model_of(text):
    """The diode model a clamp deck or the generator that writes it states: (IS, N, RS)."""
    match = re.search(r"\.model DSCH D\(IS=([0-9.e+-]+) N=([0-9.]+) RS=([0-9.]+)\)", text)
    return tuple(float(value) for value in match.groups()) if match else None


def deck_model():
    """The model the generator writes into the clamp decks."""
    return model_of(read_text("circuit-proof", "C_gen_decks.py"))


def deck_names():
    return [name for name in sorted(os.listdir(os.path.join(BOARD, "circuit-proof"))) if re.match(r"C_.*_clamp\.cir$", name)]


def deck_models():
    """The model of each clamp deck as the committed deck is run."""
    return [model_of(read_text("circuit-proof", name)) for name in deck_names()]


def used_leakage(text=None):
    """The clamp's reverse leakage the front-end proof script carries, the first term of its ILEAK sum."""
    text = text if text is not None else read_text("circuit-proof", "C_front_ends.py")
    return float(re.search(r"^ILEAK = ([0-9.e+-]+) \+", text, re.M).group(1))


def term_value(term):
    value = 1.0
    for factor in term.split("*"):
        value *= float(factor)
    return value


def pin_capacitance_terms(text=None):
    """The terms of the line-capacitance sum the front-end script evaluates, in the order it writes them (the clamp's is the last)."""
    text = text if text is not None else read_text("circuit-proof", "C_front_ends.py")
    expression = re.search(r"^c_pins = ([^#\n]+?)\s*(?:#|$)", text, re.M).group(1)
    return [term_value(term.strip()) for term in expression.split("+")]


def used_capacitance(text=None):
    return pin_capacitance_terms(text)[-1]


def budget_leakage(text=None):
    text = text if text is not None else read_text("error-budget.md")
    return [float(v) * 1e-6 for v in re.findall(r"BAT54SW ([0-9.]+) uA", text)]


def clamp_rows(text=None):
    text = text if text is not None else read_text("circuit-verdicts.md")
    return [row for row in verdict_rows(text) if re.match(r"\| D\d{3} \(BAT54SW", row)]


def verdict_power_mw(rows=None):
    """Every Ptot the verdict rows of the seven state for the clamps, in mW."""
    return [float(f) for row in (rows if rows is not None else clamp_rows()) for f in re.findall(r"against Ptot ([0-9.]+) mW", row)]


def verdict_current_limits_a(rows=None):
    return [float(f) * 1e-3 for row in (rows if rows is not None else clamp_rows()) for f in re.findall(r"IF [0-9.]+ mA of ([0-9.]+) mA", row)]


def verdict_voltage_limits_v(rows=None):
    return [float(f) for row in (rows if rows is not None else clamp_rows()) for f in re.findall(r"VR [0-9.]+ V of ([0-9.]+) V", row)]


def verdict_leakages_a(rows=None):
    return [float(f) * 1e-6 for row in (rows if rows is not None else clamp_rows()) for f in re.findall(r"Leakage ([0-9.]+) uA", row)]


def verdict_capacitances_f(rows=None):
    return [float(f) * 1e-12 for row in (rows if rows is not None else clamp_rows()) for f in re.findall(r"Capacitance ([0-9.]+) pF max", row)]


def verdict_forward_points(rows=None):
    """(current in A, volts) of every forward-voltage figure the rows use: the 'N mA point (VF x V)' of the thermistor rows, the
    'the N A point of Table 7 (x V)' of the I2C rows, and the 'I mA x V' bound of the power estimate, which Table 7 bounds at its next point up."""
    points = []
    for row in (rows if rows is not None else clamp_rows()):
        points += [(float(i) * 1e-3, float(v)) for i, v in re.findall(r"([0-9.]+) mA point \(VF ([0-9.]+) V\)", row)]
        points += [(float(i), float(v)) for i, v in re.findall(r"the ([0-9.]+) A point of Table 7 \(([0-9.]+) V\)", row)]
        points += [(float(i) * 1e-3, float(v)) for i, v in re.findall(r"([0-9.]+) mA x ([0-9.]+) V", row)]
    return points


def sheet_forward_ceiling(current):
    """The sheet's VF maximum at the first tabulated current at or above `current`, or None above the table."""
    above = [limit for point, limit in sorted(SHEET_VF_MAX_V.items()) if point >= current * (1 - 1e-9)]
    return above[0] if above else None


def symbol_pins(netlist):
    """reference -> {pin number: (pin name, pin type)} of each of the seven clamps in the schematic's netlist."""
    found = {}
    for group in board_check.walk(netlist, "nets"):
        for net in sexpr.children(group, "net"):
            for node in sexpr.children(net, "node"):
                reference = str(sexpr.child(node, "ref")[1])
                if reference not in CLAMPS:
                    continue
                pin, function, kind = (str(sexpr.child(node, key)[1]) for key in ("pin", "pinfunction", "pintype"))
                if function.endswith("_" + pin):
                    function = function[:-len(pin) - 1]
                found.setdefault(reference, {})[pin] = (function, kind)
    return found


def comparison_problems(leaks_a, models, voltage_limits_v, power_mw, capacitances_f, current_limits_a, forward_points, pins):
    """Each way a figure the records use is worse than the sheet's, the use being the number it is passed."""
    problems = []
    if not leaks_a:
        problems.append("no record states the leakage")
    for leak in leaks_a:
        if leak < SHEET_IR_MAX_A:
            problems.append(f"the leakage used, {leak:g} A, is below the sheet's {SHEET_IR_MAX_A:g} A at 25 V, 25 degC")
    if not models or None in models:
        problems.append("a clamp deck states no diode model")
    for model in models:
        for current, ceiling in SHEET_VF_MAX_V.items():
            if model is not None and model_voltage(current, *model) < ceiling - FIT_ROOM_V:
                problems.append(f"the deck model gives {model_voltage(current, *model):.4f} V at {current:g} A, under the sheet's {ceiling} V maximum")
    if not forward_points:
        problems.append("no verdict row states a forward voltage")
    for current, volts in forward_points:
        ceiling = sheet_forward_ceiling(current)
        if ceiling is None:
            problems.append(f"a forward voltage used at {current:g} A is above the sheet's table")
        elif volts < ceiling - FIT_ROOM_V:
            problems.append(f"a record uses {volts:g} V at {current:g} A, under the sheet's {ceiling} V maximum")
    if not voltage_limits_v:
        problems.append("no record states the reverse voltage")
    for limit in voltage_limits_v:
        if limit > SHEET_VR_MAX_V:
            problems.append(f"a pin limit of {limit:g} V is above the sheet's {SHEET_VR_MAX_V:g} V")
    for figure in power_mw:
        if figure > SHEET_PTOT_MW:
            problems.append(f"a power rating of {figure:g} mW is above the sheet's {SHEET_PTOT_MW:g} mW")
    if not power_mw:
        problems.append("no verdict row states the sheet's power figure")
    if not capacitances_f:
        problems.append("no record states the capacitance")
    for capacitance in capacitances_f:
        if capacitance < SHEET_CD_MAX_F:
            problems.append(f"the capacitance used, {capacitance:g} F, is below the sheet's {SHEET_CD_MAX_F:g} F")
    if not current_limits_a:
        problems.append("no verdict row states the forward current rating")
    for current in current_limits_a:
        if current > SHEET_IF_MAX_A:
            problems.append(f"a forward current rating of {current:g} A is above the sheet's {SHEET_IF_MAX_A:g} A")
    for reference in CLAMPS:
        held = pins.get(reference)
        if held is None:
            problems.append(f"{reference} has no pins in the schematic's netlist")
            continue
        if set(held) != set(SHEET_PINS):
            problems.append(f"{reference} has pins {sorted(held)}, the sheet's package has {sorted(SHEET_PINS)}")
        for number, function in SHEET_PINS.items():
            name = (held.get(number) or ("", ""))[0]
            if name != SYMBOL_PIN_OF_FUNCTION[function]:
                problems.append(f"{reference} pin {number} is {name!r} in the symbol, the sheet's pin {number} is the {function}")
    return problems


def pin_limit_figures():
    limits = record("pin-limits.yaml")
    entry = [part for part in limits["parts"] if str(part["lcsc"]) == NEW_NUMBER][0]
    return entry, [abs(float(pin[side])) for pin in entry["pins"] for side in ("absolute_max_v", "absolute_min_v")]


def derated_voltage_v():
    policy = record("derating-policy.yaml")
    share = [c for c in policy["classes"] if c["class"] == "semiconductor"][0]["voltage"]["share"]
    return share * SHEET_VR_MAX_V


def unsigned_violation_lines(lines):
    """The VIOLATION lines of a check's output: the check prints a line the signed records accept as ACCEPTED or WARNING."""
    return [line for line in lines if line.startswith("VIOLATION")]


def line_rule(line):
    """The rule or class a report line names: its third ' | ' field."""
    fields = line.split(" | ")
    return fields[2] if len(fields) > 2 else ""


def accepted_rule(line):
    """The rule class a signed-workmanship ACCEPTED line covers: it opens the line's fifth field, its message, before ' at '."""
    fields = line.split(" | ")
    if len(fields) < 5 or fields[2] != "workmanship_acceptance":
        return ""
    return fields[4].split(" at ", 1)[0]


def signed_classes():
    """The rule classes the committed workmanship-acceptance record signs, and those the severity-policy record marks WARNING."""
    yaml = board_check.require_yaml()
    with open(os.path.join(BOARD, board_check.WORKMANSHIP_ACCEPTANCE_NAME), encoding="utf-8") as handle:
        accepted = {entry["rule"] for entry in yaml.safe_load(handle)["accepted_workmanship"]}
    with open(os.path.join(BOARD, board_check.SEVERITY_POLICY_NAME), encoding="utf-8") as handle:
        warning = {entry["class"] for entry in yaml.safe_load(handle)["severity_policy"] if entry["severity"] == "WARNING"}
    return accepted, warning


def full_check_problems(lines, accepted, warned):
    """What a full-check result lacks or carries wrongly: an unsigned violation, a missing tier of signed lines, a side_fiducials line."""
    signed, policy = signed_classes()
    problems = [f"unsigned: {line}" for line in unsigned_violation_lines(lines)]
    if not any(line.startswith("ACCEPTED") and accepted_rule(line) in signed for line in accepted):
        problems.append("no ACCEPTED line of a signed workmanship class")
    if not any(line.startswith("WARNING") and line_rule(line) in policy for line in warned):
        problems.append("no WARNING line of a class the severity policy marks WARNING")
    problems += [f"side_fiducials line: {line}" for line in lines if "side_fiducials" in line]
    return problems


def covered_shortfall_problems(accepted):
    """What a full-check result shows wrongly of the covered shortfall pairs: none judged at all, or a covering line missing its ground or bound.
    A run that judged no pair proves nothing about coverage, and a covering line must state the ground of the exception and the element bounding the fault."""
    covered = [line for line in accepted if line.startswith("ACCEPTED") and line_rule(line) == "spacing_exception"]
    if not covered:
        return ["no ACCEPTED spacing_exception line: the run judged no covered shortfall pair"]
    return [f"covering line without ground or bound: {line}" for line in covered
            if "accepted exception:" not in line or "reason: " not in line or "bounded by: " not in line]


def full_check_lines():
    """The lines of the repository's own pre-order check of the main board design alone, as the report prints them."""
    accepted, warned = [], []
    found = board_check.check_design(design(), repository(), kicad_cli(), board_check.require_yaml(), datetime.date.today(),
                                     [], None, accepted, warned)
    return [v.line() for v in found] + accepted + warned, accepted, warned


# --- Fixtures ----------------------------------------------------------------------------------


class Committed(unittest.TestCase):
    """The committed board and its schematic's netlist (exported once for the module)."""

    @classmethod
    def setUpClass(cls):
        cls.tree = read_tree()
        cls.netlist = cached_netlist()
        cls.parts = schematic_parts(cls.netlist)
        cls.pin_nets = schematic_pin_nets(cls.netlist)


class BoardSide(Committed):
    # SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.C1: On the committed main board no assembled surface-mount part stands on B.Cu, D502, D506 and R301 stand on F.Cu, the back side carries no fiducial, and the pre-order check on the main board prints no side_fiducials line. The test fails on a board with any assembled surface-mount part on B.Cu, and on a synthetic board with an assembled surface-mount part on B.Cu and no fiducial there. Out of scope: any other rule's line.
    def test_no_assembled_part_stands_on_the_back_and_a_synthetic_back_part_without_a_fiducial_is_found(self):
        self.assertEqual(board_check.missing_fiducials(design(), self.tree), [])
        self.assertEqual(side_problems(self.tree), [])
        self.assertEqual(assembled_on_back(self.tree), [])
        self.assertEqual(back_fiducials(self.tree), [])
        # Every footprint on B.Cu of the committed board is a test point pad, which is the measured fact behind the smd-attribute rule.
        self.assertEqual(back_non_test_points(self.tree), [])
        for reference in FRONT:
            self.assertEqual(layer_of(footprints(self.tree)[reference]), "F.Cu")
        # The board's back side holds only test points left out of the position file: the faults below are real faults.
        back = [r for r, f in footprints(self.tree).items() if layer_of(f) == "B.Cu"]
        self.assertTrue(back)
        # A synthetic board with D502 on B.Cu and no fiducial there: both the part list and the check's own rule find it.
        moved = copy.deepcopy(self.tree)
        sexpr.child(footprints(moved)["D502"], "layer")[1] = "B.Cu"
        self.assertEqual(assembled_on_back(moved), ["D502"])
        self.assertIn("side_fiducials", [v.rule for v in board_check.missing_fiducials(design(), moved)])
        self.assertIn("D502 is not on F.Cu", side_problems(moved))
        # R301 and D506 moved to the back are named too.
        for reference in ("D506", "R301"):
            again = copy.deepcopy(self.tree)
            sexpr.child(footprints(again)[reference], "layer")[1] = "B.Cu"
            self.assertIn(f"{reference} is not on F.Cu", side_problems(again))
        # A footprint on B.Cu that is no test point pad is found even with no smd attribute (a back-side part the attribute rule would miss).
        renamed = copy.deepcopy(self.tree)
        back_one = next(r for r, f in footprints(renamed).items() if layer_of(f) == "B.Cu")
        footprints(renamed)[back_one][1] = "main-board:R_0603_1608Metric"
        self.assertEqual(back_non_test_points(renamed), [back_one])
        self.assertIn(f"{back_one} is on B.Cu and is not a test point pad", side_problems(renamed))
        # A back-side footprint that is smd and left out of the position file but is no test point pad is found by the non-test-point rule.
        hidden = copy.deepcopy(self.tree)
        back_two = next(r for r, f in footprints(hidden).items() if layer_of(f) == "B.Cu")
        node = footprints(hidden)[back_two]
        node[1] = "main-board:R_0603_1608Metric"
        sexpr.child(node, "attr")[1:] = ["smd", "exclude_from_pos_files"]
        self.assertEqual(assembled_on_back(hidden), [])
        self.assertEqual(back_non_test_points(hidden), [back_two])
        self.assertIn(f"{back_two} is on B.Cu and is not a test point pad", side_problems(hidden))
        # A fiducial on the back side is found.
        fiducial = copy.deepcopy(self.tree)
        front = next(r for r, f in footprints(fiducial).items() if board_check.fiducial_pads(f))
        sexpr.child(footprints(fiducial)[front], "layer")[1] = "B.Cu"
        self.assertEqual(back_fiducials(fiducial), [front])
        self.assertIn(f"{front} is a fiducial on the back side", side_problems(fiducial))


class ClampParts(Committed):
    # SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.C2: D502, D504, D506, D523, D524, D527 and D528 carry the Nexperia BAT54SW,115 (LCSC C78606) in a SOT-323 footprint in both the schematic symbol and the board, with matching footprint, LCSC, MPN and description fields; the bill of materials holds that one line for the seven parts; D502 and D506 stand on F.Cu, D504, D523, D524, D527 and D528 stay on F.Cu, and each of the seven has its courtyard clear of every other courtyard; and on the board pad 1 is on GND, pad 2 on its supply (+3V3A for D502, D504 and D506, +3V3 for the others) and pad 3 on its signal node (NTC_COF for D502, NTC_STM for D504, NTC_WAND for D506, STM_SCL and STM_SDA for D523 and D524, BREW_SCL and BREW_SDA for D527 and D528), each the net the schematic symbol's pin of the same number carries. The test fails on a swapped pad 1 and 2, on a footprint field that disagrees with the schematic, on any of the seven still carrying C47546 in the symbol, board or bill of materials, and on a pad on a net other than the schematic's. Out of scope: the records that name the part (the part-records criterion covers them), the electrical-equivalence reading, the routing of the moved parts, R301 and the vias.
    def test_the_seven_clamps_are_the_sot_323_part_with_the_schematics_fields_and_nets_and_clear_courtyards(self):
        self.assertEqual(clamp_board_problems(self.tree, self.parts, self.pin_nets), [])
        self.assertEqual(courtyard_problems(self.tree, CLAMPS), [])
        # The parts the schematic and the board both carry as C78606 are the seven and no other.
        on_board = sorted(r for r, f in footprints(self.tree).items() if properties(f).get("LCSC") == NEW_NUMBER)
        in_schematic = sorted(r for r, p in self.parts.items() if p["fields"].get("LCSC") == NEW_NUMBER)
        self.assertEqual(on_board, sorted(CLAMPS))
        self.assertEqual(in_schematic, sorted(CLAMPS))
        # The bill of materials groups parts by value, footprint and number: the seven are one line.
        lines = {(properties(footprints(self.tree)[r]).get("Value"), library_item(footprints(self.tree)[r]),
                  properties(footprints(self.tree)[r]).get("LCSC")) for r in CLAMPS}
        self.assertEqual(lines, {("BAT54SW", FOOTPRINT, NEW_NUMBER)})
        specification = {p["reference"]: p for p in record("parts-specification.yaml")["positions"] if p["reference"] in CLAMPS}
        self.assertEqual({(p["value"], p["package"], p["rating"], str(p["lcsc"])) for p in specification.values()},
                         {("BAT54SW", FOOTPRINT, "dual series Schottky 30V 200mA", NEW_NUMBER)})
        # Faults: swapped pads 1 and 2, a footprint field that disagrees, the old number, a wrong net, a courtyard overlap.
        swapped = copy.deepcopy(self.tree)
        for pad in sexpr.children(footprints(swapped)["D504"], "pad"):
            if str(pad[1]) in ("1", "2"):
                sexpr.child(pad, "net")[1] = "+3V3A" if str(pad[1]) == "1" else "GND"
        self.assertTrue(any("D504 pad 1" in p for p in clamp_board_problems(swapped, self.parts, self.pin_nets)))
        wrong = copy.deepcopy(self.tree)
        for prop in sexpr.children(footprints(wrong)["D523"], "property"):
            if str(prop[1]) == "MPN":
                prop[2] = "BAT54S,215"
        self.assertTrue(any("D523 MPN differs" in p for p in clamp_board_problems(wrong, self.parts, self.pin_nets)))
        old = copy.deepcopy(self.tree)
        for prop in sexpr.children(footprints(old)["D527"], "property"):
            if str(prop[1]) == "LCSC":
                prop[2] = OLD_NUMBER
        self.assertTrue(any("D527" in p and OLD_NUMBER in p for p in clamp_board_problems(old, self.parts, self.pin_nets)))
        # Only the symbol/netlist LCSC field of one clamp still says C47546, everything else swapped: that clamp is named, and no other.
        symbol_only = copy.deepcopy(self.parts)
        symbol_only["D524"]["fields"]["LCSC"] = OLD_NUMBER
        named = clamp_board_problems(self.tree, symbol_only, self.pin_nets)
        self.assertIn(f"D524 still carries {OLD_NUMBER}", named)
        self.assertTrue(any("D524 LCSC differs" in p for p in named))
        self.assertTrue(all(p.startswith("D524 ") for p in named))
        other = copy.deepcopy(self.parts)
        other["D528"]["footprint"] = "Package_TO_SOT_SMD:SOT-23"
        self.assertTrue(any("D528 footprint differs" in p for p in clamp_board_problems(self.tree, other, self.pin_nets)))
        net = copy.deepcopy(self.pin_nets)
        net[("D506", "3")] = "/NTC_COF"
        self.assertTrue(any("D506 pad 3" in p for p in clamp_board_problems(self.tree, self.parts, net)))
        crowded = copy.deepcopy(self.tree)
        near = footprints(crowded)["D502"]
        node, other_at = sexpr.child(near, "at"), sexpr.child(footprints(crowded)["D504"], "at")
        node[1], node[2] = other_at[1], other_at[2]
        self.assertTrue(any("courtyard of D502" in p for p in courtyard_problems(crowded, ["D502"])))
        # The board and the schematic's netlist both agree on a wrong supply for D502: only the stated constants can name it.
        both = copy.deepcopy(self.tree)
        agreed = copy.deepcopy(self.pin_nets)
        for pad in sexpr.children(footprints(both)["D502"], "pad"):
            if str(pad[1]) == "2":
                sexpr.child(pad, "net")[1] = "+3V3"
                agreed[("D502", "2")] = sexpr.child(pad, "net")[1]
        named = clamp_board_problems(both, self.parts, agreed)
        self.assertTrue(any(p.startswith("D502 pad 2") for p in named), named)
        self.assertTrue(all(p.startswith("D502 ") for p in named), named)
        # One clamp with a different LCSC (and one with a different value) no longer forms the one bill-of-materials line.
        for field, value in (("LCSC", "C12345"), ("Value", "BAT54S")):
            split = copy.deepcopy(self.tree)
            for prop in sexpr.children(footprints(split)["D524"], "property"):
                if str(prop[1]) == field:
                    prop[2] = value
            split_lines = {(properties(footprints(split)[r]).get("Value"), library_item(footprints(split)[r]),
                            properties(footprints(split)[r]).get("LCSC")) for r in CLAMPS}
            self.assertNotEqual(split_lines, {("BAT54SW", FOOTPRINT, NEW_NUMBER)}, field)
            self.assertEqual(len(split_lines), 2, field)
        # A courtyard overlap on a clamp other than D502.
        stacked = copy.deepcopy(self.tree)
        node, other_at = sexpr.child(footprints(stacked)["D528"], "at"), sexpr.child(footprints(stacked)["D527"], "at")
        node[1], node[2] = other_at[1], other_at[2]
        self.assertTrue(any("courtyard of D528" in p for p in courtyard_problems(stacked, ["D528"])))


class RStandsClear(Committed):
    # SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.C3: R301 stands on F.Cu with its courtyard 10 mm or more from the Y401 courtyard, so the 'Crystal keep-clear Y401' rule holds with no exemption for R301 in the rules file; the +3V3A_FB and +3V3A nets are connected to every pad of R301, on the board and not only in the netlist, with no B.Cu track of either net ending on a pad of R301. The test fails on a courtyard within 10 mm of the Y401 courtyard, on a rule exemption for R301, and on an R301 pad not joined by copper to its net, and on a B.Cu track of either net ending on an R301 pad. Out of scope: the seven BAT54SW,115 clamps.
    def test_r301_stands_on_the_front_clear_of_the_crystal_with_no_exemption_and_joined_to_its_nets(self):
        rules, problems = board_check.read_rules(REPO, design(), repository())
        self.assertEqual(problems, [])
        self.assertEqual(keep_clear_problems(self.tree, rules), [])
        self.assertEqual(r301_copper_problems(self.tree), [])
        # Faults: an exemption written into the rule, a part moved inside the 10 mm, a pad with its copper removed, copper of the net on B.Cu.
        with open(os.path.join(BOARD, "main-board.kicad_dru"), encoding="utf-8") as handle:
            text = handle.read()
        exempting = text.replace("(rule \"Crystal keep-clear Y401\"\n\t(condition \"A.Reference == 'Y401' && ",
                                 "(rule \"Crystal keep-clear Y401\"\n\t(condition \"A.Reference == 'Y401' && B.Reference != 'R301' && ")
        self.assertNotEqual(exempting, text)
        self.assertIn("the Y401 keep-clear rule exempts R301", keep_clear_problems(self.tree, sexpr.parse(exempting, comments=True)))
        close = copy.deepcopy(self.tree)
        at = sexpr.child(footprints(close)["R301"], "at")
        crystal = sexpr.child(footprints(close)["Y401"], "at")
        at[1], at[2] = crystal[1], str(float(crystal[2]) + 3)
        self.assertTrue(any("from that of Y401, under" in p for p in keep_clear_problems(close, rules)))
        back = copy.deepcopy(self.tree)
        sexpr.child(footprints(back)["R301"], "layer")[1] = "B.Cu"
        self.assertIn("R301 is not on F.Cu", keep_clear_problems(back, rules))
        bare_tree = [node for node in self.tree if not (sexpr.head(node) in ("segment", "via") and self.touches_r301(node))]
        self.assertTrue(any("R301 pad" in p for p in r301_copper_problems(bare_tree)))
        stray = copy.deepcopy(self.tree)
        pad = pads_of(stray, "R301")[0]
        stray.append(sexpr.parse_one(f'(segment (start {pad.centre[0]} {pad.centre[1]}) (end {pad.centre[0] + 0.5} {pad.centre[1]}) '
                                     f'(width 0.2) (layer "B.Cu") (net "{pad.net}"))'))
        self.assertTrue(any("on B.Cu ends on a pad of R301" in p for p in r301_copper_problems(stray)))

    def touches_r301(self, node):
        pads = pads_of(self.tree, "R301")
        table = board_geometry.net_table(self.tree)
        return board_geometry.item_net(node, table, "x") in {pad.net for pad in pads} and any(
            pad_touches(pad, [node], pad.net) for pad in pads)


class RecordsNameTheSwappedPart(Committed):
    # SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.C5: Every record in the main board folder that names the clamp part for any of D502, D504, D506, D523, D524, D527 and D528 states the swapped part, Nexperia BAT54SW,115 (LCSC C78606): the per-reference rows of the parts specification, the per-reference rows of the schematic specification and of every sheet record that names a clamp, the per-reference clamp rows of the circuit verdicts, the circuit-proof clamp decks and the generators and comments that write them, the traceability rows that name the clamp, and the catalogue extract, which carries an entry for C78606 so the board tier's catalogue check passes. The pin-limits record's single shared clamp entry is re-keyed to C78606 with pins 1, 2 and 3 limited from the maker's sheet, with no split entries, and the C47546 clamp entry is gone unless another part still uses it, so the pin-limit and derating check evaluates all seven references and prints no skipped-part line for any. The test fails when any such record still names C47546 for one of the seven, when a record names C78606 for a reference outside the seven, when the pin-limits record lacks the C78606 entry or keeps a second clamp entry for the same references, when the catalogue extract lacks C78606, and when the check run on the main board evaluates a clamp reference against no entry. Out of scope: the electrical-equivalence reading (the equivalence criterion), and the schematic symbol and board fields.
    def test_every_record_naming_a_clamp_states_the_swapped_part_and_the_pin_limit_check_resolves_all_seven(self):
        self.assertEqual(old_number_lines(), [])
        limits = record("pin-limits.yaml")
        clamp = [part for part in limits["parts"] if str(part["lcsc"]) == NEW_NUMBER]
        self.assertEqual(len(clamp), 1)
        self.assertEqual({str(pin["pin"]) for pin in clamp[0]["pins"]}, {"1", "2", "3"})
        self.assertEqual([part for part in limits["parts"] if str(part["lcsc"]) == OLD_NUMBER], [])
        loaded, problems = board_check.load_pin_limits(board_check.require_yaml(), REPO, repository(), design(), False)
        self.assertEqual(problems, [])
        placed, _, _ = board_check.placed_positions(REPO, design(), repository())
        pins = {}
        for (reference, pin), _ in self.pin_nets.items():
            pins.setdefault(reference, set()).add(pin)
        self.assertEqual(unresolved_clamps(loaded, placed, pins), [])
        extract = record("catalogue-extract.yaml")
        self.assertIn(NEW_NUMBER, [str(entry["lcsc"]) for entry in extract["entries"]])
        # The per-reference records, row by row.
        self.assertEqual(part_entry_problems(record("parts-specification.yaml")["positions"], "reference", "lcsc"), [])
        spec = [part for sheet in record("schematic-spec.yaml")["sheets"] for part in sheet["parts"]]
        self.assertEqual(part_entry_problems(spec, "ref", "lcsc"), [])
        spoiled = copy.deepcopy(spec)
        next(part for part in spoiled if part["ref"] == "D506")["lcsc"] = OLD_NUMBER
        self.assertTrue(part_entry_problems(spoiled, "ref", "lcsc"))
        self.assertEqual(part_entry_problems(sheet_entries(), "ref", "lcsc"), [])
        self.assertEqual(row_problems(read_text("circuit-verdicts.md")), [])
        self.assertEqual(traceability_problems(read_text("traceability.md")), [])
        self.assertIn("D502 BAT54SW", read_text("traceability.md"))
        self.assertIn("D523/D524 BAT54SW", read_text("traceability.md"))
        # Faults, each fed as a synthetic input.
        stale = copy.deepcopy(loaded)
        for part in stale["parts"]:
            if str(part["lcsc"]) == NEW_NUMBER:
                part["lcsc"] = OLD_NUMBER
        self.assertEqual(len(unresolved_clamps(stale, placed, pins)), len(CLAMPS))
        split = copy.deepcopy(loaded)
        for part in split["parts"]:
            if str(part["lcsc"]) == NEW_NUMBER:
                part["pins"] = part["pins"][:2]
        self.assertTrue(all("pin 3" in p for p in unresolved_clamps(split, placed, pins)))
        wrong = copy.deepcopy(placed)
        wrong["D524"]["lcsc"] = OLD_NUMBER
        self.assertEqual(len(unresolved_clamps(loaded, wrong, pins)), 1)
        rows = read_text("circuit-verdicts.md").replace("| D523 (BAT54SW C78606)", "| D523 (BAT54S C47546)")
        self.assertTrue(any("D523" in p for p in row_problems(rows)))
        outsider = read_text("circuit-verdicts.md").replace("| D521 (PESD5V0F1BL C45961)", "| D521 (PESD5V0F1BL C78606)")
        self.assertTrue(any("D521 names" in p for p in row_problems(outsider)))
        self.assertTrue(traceability_problems(read_text("traceability.md").replace("D502 BAT54SW", "D502 BAT54S")))
        entries = copy.deepcopy(record("parts-specification.yaml")["positions"])
        next(e for e in entries if e["reference"] == "D504")["lcsc"] = OLD_NUMBER
        self.assertTrue(part_entry_problems(entries, "reference", "lcsc"))
        extra = copy.deepcopy(entries)
        next(e for e in extra if e["reference"] == "D521")["lcsc"] = NEW_NUMBER
        self.assertTrue(any("entries naming" in p for p in part_entry_problems(extra, "reference", "lcsc")))
        self.assertEqual(uncommented("x.yaml", "# C47546 history\nlcsc: C78606"), ["lcsc: C78606"])
        self.assertEqual(len(uncommented("x.yaml", "lcsc: C47546")), 1)
        self.assertEqual(len(uncommented("x.md", "# heading naming C47546")), 1)
        deck = "* clamp deck\n# generator comment still naming C47546\n.model D"
        self.assertEqual(sum(OLD_NUMBER in line for line in uncommented("C_x.py", deck, "circuit-proof")), 1)
        self.assertEqual(sum(OLD_NUMBER in line for line in uncommented("C_x.cir", "* deck naming C47546", "circuit-proof")), 1)
        self.assertEqual(sum(OLD_NUMBER in line for line in uncommented("pin-limits.yaml", "# SOT-23 BAT54S (C47546) to this part", None)), 0)
        self.assertEqual(sum(OLD_NUMBER in line for line in uncommented("pin-limits.yaml", "# SOT-23 BAT54S (C47546) to this part", "sheets")), 0)


class SheetFigures(Committed):
    # SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.C6: The maker's sheet for the swapped part (https://www.lcsc.com/datasheet/lcsc_datasheet_2407241045_Nexperia-BAT54SW-115_C78606.pdf, fetched by curl and read with pdftotext) is read, and each figure the records use for each of the seven clamp references is compared with the sheet's figure for the BAT54SW,115 with the arithmetic shown in the evidence. The uses are read from the netlist: the thermistor inputs NTC_COF (D502), NTC_STM (D504) and NTC_WAND (D506), the steam-path pressure I2C pins STM_SCL and STM_SDA (D523, D524) and the brew-path pressure I2C pins BREW_SCL and BREW_SDA (D527, D528). The figures compared are reverse leakage against the 2 uA at 25 V and 25 degC that the error budget's 0.56 degC clamp-leakage term and the front-end proof script use; forward voltage against the 0.24 V at 0.1 mA and 0.32 V at 1 mA maxima that fit the thermistor clamp decks, the shorted-lead verdict rows and the I2C pin-voltage rows; reverse voltage against the 30 V of the pin limits and the 0.75 derating share of 22.5 V; total power and forward current against the 200 mW and 200 mA the derating rows use; diode capacitance against the 10 pF of the line-capacitance sums, thermistor and I2C bus alike; and the sheet's pin functions against the board's pads, pin 1 the anode of diode 1, pin 2 the cathode of diode 2 and pin 3 the common node. Each figure of the swapped part is at least as good as the one used, or the record that uses it is re-derived with the sheet's figure and its margin shown to hold. The inspection fails on a sheet figure worse than the one a record uses with that record unchanged, on a node among the seven uses left uncompared, and on a figure compared without the sheet's test condition. Out of scope: parts other than the BAT54SW,115, and measurement on built boards.
    def test_every_figure_the_records_use_for_the_clamps_is_no_better_than_the_sheet_states_and_the_pins_match(self):
        _, limits_v = pin_limit_figures()
        rows = clamp_rows()
        self.assertEqual(len(rows), len(CLAMPS))
        decks = deck_models()
        self.assertEqual(len(decks), 3)
        self.assertEqual(decks, [deck_model()] * 3)
        terms = pin_capacitance_terms()
        # The generator's own statement of the pins' capacitance is the sum of the terms the script evaluates.
        self.assertAlmostEqual(sum(terms) * 1e12, float(re.search(r"the pins take ([0-9.]+) pF", read_text("circuit-proof", "C_gen_decks.py")).group(1)), places=6)
        used = dict(leaks_a=[used_leakage()] + budget_leakage() + verdict_leakages_a(rows), models=decks,
                    voltage_limits_v=limits_v + verdict_voltage_limits_v(rows), power_mw=verdict_power_mw(rows),
                    capacitances_f=[used_capacitance()] + verdict_capacitances_f(rows), current_limits_a=verdict_current_limits_a(rows),
                    forward_points=verdict_forward_points(rows), pins=symbol_pins(self.netlist))
        self.assertEqual(comparison_problems(**used), [])
        # What each reading found, so a clause that stopped matching would leave a count short: three thermistor rows and four I2C rows.
        self.assertEqual(len(used["current_limits_a"]), 3)
        self.assertEqual(len(used["power_mw"]), 3)
        self.assertEqual(used["current_limits_a"], [SHEET_IF_MAX_A] * 3)
        self.assertEqual(len(used["leaks_a"]), 1 + len(budget_leakage()) + 3)
        self.assertGreaterEqual(len(budget_leakage()), 1)
        self.assertEqual(len(verdict_capacitances_f(rows)), 4)
        self.assertEqual(len(used["forward_points"]), 3 * 2 + 4)
        # The derating row's 0.75 share of the sheet's 30 V is 22.5 V, above the 3.929 V the highest clamp pin reaches.
        self.assertAlmostEqual(derated_voltage_v(), 22.5)
        # The pins are the symbol's own, in the netlist the schematic exports, for each of the seven: pin 1 A, pin 2 K, pin 3 COM, all passive;
        # on the board pin 1 is on GND, pin 2 on the supply and pin 3 on the signal node.
        for reference in CLAMPS:
            self.assertEqual(used["pins"][reference], {"1": ("A", "passive"), "2": ("K", "passive"), "3": ("COM", "passive")})
            nets = pad_nets(self.tree, reference)
            self.assertEqual((bare(nets["1"]), bare(nets["2"]), bare(nets["3"])), ("GND", SUPPLY[reference], SIGNAL[reference]))
        # The seven uses are the thermistor inputs and the two I2C buses, each a clamp of the seven on the node it names.
        self.assertEqual(set(SIGNAL.values()), {"NTC_COF", "NTC_STM", "NTC_WAND", "STM_SCL", "STM_SDA", "BREW_SCL", "BREW_SDA"})

        def worse(**change):
            return comparison_problems(**dict(used, **change))

        # Faults, each fed as a synthetic record text or reading: every figure made worse than the sheet's is found.
        # (a) forward current: a verdict row text with a limit above the sheet's 200 mA, read the way the real rows are.
        bigger = [row.replace("of 200 mA", "of 400 mA") for row in rows]
        self.assertTrue(any("forward current rating" in p for p in worse(current_limits_a=verdict_current_limits_a(bigger))))
        self.assertTrue(worse(current_limits_a=[]))
        # (b) pins: a symbol whose pins 1 and 2 are swapped, and one missing its pin 3.
        swapped = copy.deepcopy(used["pins"])
        swapped["D506"]["1"], swapped["D506"]["2"] = swapped["D506"]["2"], swapped["D506"]["1"]
        self.assertTrue(any(p.startswith("D506 pin 1") for p in worse(pins=swapped)))
        short = copy.deepcopy(used["pins"])
        del short["D528"]["3"]
        self.assertTrue(any("D528 has pins" in p for p in worse(pins=short)))
        self.assertTrue(any("D502 has no pins" in p for p in worse(pins={r: v for r, v in used["pins"].items() if r != "D502"})))
        # (c) capacitance: the front-end script's sum with the clamp's term made smaller than the sheet's 10 pF, and a verdict row text likewise.
        script = read_text("circuit-proof", "C_front_ends.py")
        smaller = script.replace("2 * 0.55e-12 + 10e-12", "2 * 0.55e-12 + 6e-12")
        self.assertNotEqual(smaller, script)
        self.assertEqual(used_capacitance(smaller), 6e-12)
        self.assertTrue(any("capacitance used" in p for p in worse(capacitances_f=[used_capacitance(smaller)])))
        small_rows = [row.replace("Capacitance 10 pF max", "Capacitance 4 pF max") for row in rows]
        self.assertTrue(any("capacitance used" in p for p in worse(capacitances_f=verdict_capacitances_f(small_rows))))
        # (d) forward voltage: a deck whose model gives less than the sheet's maxima, and a verdict row text with a lower figure than Table 7's.
        deck = read_text("circuit-proof", deck_names()[0])
        weak = deck.replace("N=1.04", "N=1.00")
        self.assertNotEqual(weak, deck)
        self.assertTrue(any("deck model gives" in p for p in worse(models=decks[1:] + [model_of(weak)])))
        low_rows = [row.replace("(VF 0.5 V)", "(VF 0.4 V)").replace("Table 7 (0.8 V)", "Table 7 (0.6 V)") for row in rows]
        self.assertEqual(len([p for p in worse(forward_points=verdict_forward_points(low_rows)) if "a record uses" in p]), 3 + 4)
        # (e) leakage in the error budget and the verdict rows, reverse voltage, power: each made worse than the sheet's.
        self.assertTrue(any("leakage used" in p for p in worse(leaks_a=budget_leakage(read_text("error-budget.md").replace("BAT54SW 2 uA", "BAT54SW 1 uA")))))
        self.assertTrue(any("leakage used" in p for p in worse(leaks_a=verdict_leakages_a([row.replace("Leakage 2 uA", "Leakage 1 uA") for row in rows]))))
        self.assertTrue(any("leakage used" in p for p in worse(leaks_a=[used_leakage(script.replace("ILEAK = 2e-6", "ILEAK = 1e-6"))])))
        self.assertTrue(any("pin limit" in p for p in worse(voltage_limits_v=limits_v + [36.0])))
        self.assertTrue(any("pin limit" in p for p in worse(voltage_limits_v=verdict_voltage_limits_v([row.replace("of 30 V", "of 40 V") for row in rows]))))
        self.assertTrue(any("power rating" in p for p in worse(power_mw=[250.0])))
        self.assertTrue(worse(power_mw=[]))
        self.assertTrue(worse(leaks_a=[]))
        self.assertTrue(worse(capacitances_f=[]))


class FullCheck(Committed):
    # SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.C4: The full pre-order check on the committed main board passes with no violation line other than its signed accepted lines, and the locked critical copper at the seven clamps, the NTC_COF, NTC_STM and NTC_WAND copper, carries the copper lock flag on the committed board. The evidence names the gate run and the commit it ran on. Out of scope: the owner's decision on vias in pads.
    def test_the_full_pre_order_check_of_the_committed_main_board_has_no_violation_line_beyond_its_accepted_ones(self):
        # SOL-MAIN-BOARD-EXCEPTIONS-COVER-EVERY-REPORTED-SHORTFALL-PAIR.C1: A run of the pre-order check on the finished main board lists no mains-to-mains shortfall pair that no draft entry of the separation basis record covers, and each pair added to the record has a draft entry stating its ground and the element bounding the fault. Out of scope is signing any entry.
        lines, accepted, warned = full_check_lines()
        self.assertEqual(unsigned_violation_lines(lines), [])
        self.assertTrue(all(line.startswith("ACCEPTED") for line in accepted))
        # The tiers ran: accepted lines of a class the workmanship record signs, warning lines of a class the severity policy marks, and no side_fiducials line.
        self.assertEqual(full_check_problems(lines, accepted, warned), [])
        # Faults for that assertion: a result whose ACCEPTED list is emptied (a skipped tier), one whose WARNING lines are dropped, one with a side_fiducials line.
        self.assertIn("no ACCEPTED line of a signed workmanship class", full_check_problems(lines, [], warned))
        self.assertIn("no WARNING line of a class the severity policy marks WARNING", full_check_problems(lines, accepted, []))
        extra = board_check.Violation("main-board", "side_fiducials", "B.Cu", "a synthetic fault").line()
        found = full_check_problems(lines + [extra], accepted, warned)
        self.assertTrue(any("side_fiducials" in p for p in found))
        # Self-test of the line filter only (not evidence the check can fail): it returns exactly the VIOLATION lines it is given.
        self.assertEqual(unsigned_violation_lines(lines + [extra]), [extra])
        # The uncovered-pair half of the criterion is the VIOLATION-free assertion above: an uncovered shortfall prints as a VIOLATION.
        # This half: at least one covered pair was judged, and every covering line states its ground and bound.
        self.assertEqual(covered_shortfall_problems(accepted), [])
        self.assertEqual(covered_shortfall_problems([]), ["no ACCEPTED spacing_exception line: the run judged no covered shortfall pair"])
        covering = next(line for line in accepted if line.startswith("ACCEPTED") and line_rule(line) == "spacing_exception")
        for token in ("bounded by: ", "reason: ", "accepted exception:"):
            self.assertEqual(covered_shortfall_problems([covering.replace(token, "")]),
                             [f"covering line without ground or bound: {covering.replace(token, '')}"])

    # SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.C4: The full pre-order check on the committed main board passes with no violation line other than its signed accepted lines, and the locked critical copper at the seven clamps, the NTC_COF, NTC_STM and NTC_WAND copper, carries the copper lock flag on the committed board. The evidence names the gate run and the commit it ran on. Out of scope: the owner's decision on vias in pads.
    def test_the_locked_critical_copper_of_the_thermistor_nets_carries_the_copper_lock_flag_on_the_committed_board(self):
        text = read_text("main-board.kicad_pcb")
        items = board_items(text)
        for net in THERMISTOR_NETS:
            copper = [item for item in items if bare(item["net"]) == net]
            self.assertTrue(copper, net)
            self.assertTrue(all(item["locked"] for item in copper), net)
        self.assertEqual(unlocked_thermistor(items), [])
        # Fault: the board's own text with the lock token removed from one item of each net, read by the same parser as the real board.
        for net in THERMISTOR_NETS:
            found = unlocked_thermistor(board_items(unlock_one(text, net)))
            self.assertEqual(len(found), 1, net)
            self.assertTrue(found[0].endswith(f"on /{net}"), found)


class ClampCopper(Committed):
    # SOL-MAIN-BOARD-BACK-SIDE-PARTS-AND-VIAS-IN-PADS-MOVED-BY-THE-PLACEMENT-METHOD.C7: On the committed board the pads of D502, D504, D506, D523, D524, D527 and D528 are connected by copper, and not only in the netlist, to the nets they carry in the schematic (GND, the supply, and the signal node: NTC_COF for D502, NTC_STM for D504, NTC_WAND for D506, STM_SCL and STM_SDA for D523 and D524, BREW_SCL and BREW_SDA for D527 and D528), checked from the board file's copper; and the locked critical copper at the seven clamps, the NTC_COF, NTC_STM and NTC_WAND copper, carries the copper lock flag on the committed board. The test fails on a pad of any of the seven joined to a different net or left unconnected, and on locked critical copper that does not carry the lock flag. Out of scope: R301, the copper lock for any other net, and the question whether any via should leave a surface-mount pad (the sibling vias-in-pads item owns the decision).
    def test_the_clamp_pads_are_joined_by_copper_to_their_nets_and_the_thermistor_copper_there_is_locked(self):
        self.assertEqual(unjoined_pads(self.tree, CLAMPS), [])
        text = read_text("main-board.kicad_pcb")
        self.assertEqual(unlocked_thermistor(board_items(text)), [])
        # Faults: a pad whose net is changed to another net is not joined to it; a pad with its copper removed is unjoined;
        # thermistor copper with its lock token removed from the board text is found.
        moved = copy.deepcopy(self.tree)
        for pad in sexpr.children(footprints(moved)["D506"], "pad"):
            if str(pad[1]) == "3":
                sexpr.child(pad, "net")[1] = "/NTC_STM"
        self.assertTrue(any("D506 pad 3" in p for p in unjoined_pads(moved, ["D506"])))
        stripped = [node for node in self.tree if sexpr.head(node) not in ("segment", "via")]
        self.assertEqual(len(unjoined_pads(stripped, CLAMPS)), 2 * len(CLAMPS))
        self.assertEqual(len(unlocked_thermistor(board_items(unlock_one(text, "NTC_COF")))), 1)


THERMISTOR_NETS = ("NTC_COF", "NTC_STM", "NTC_WAND")


def board_items(text):
    """The copper of a board's text read by the parser the real board goes through: the file read, then the copper of its layout."""
    with tempfile.TemporaryDirectory() as work:
        path = os.path.join(work, "board.kicad_pcb")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return locked_copper.copper(locked_copper.read_layout(path), path)


def unlock_one(text, net):
    """The board's text with the lock token removed from the first locked item of `net`, and nothing else changed."""
    for found in re.finditer(r"\n\t\((?:segment|arc|via)\n(?:\t\t.*\n)*?\t\)", text):
        item = found.group(0)
        if f'(net "/{net}")' in item and "\t\t(locked yes)\n" in item:
            return text[:found.start()] + item.replace("\t\t(locked yes)\n", "", 1) + text[found.end():]
    raise AssertionError(f"no locked item on {net}")


def unlocked_thermistor(items):
    """Each track, via or zone on a thermistor net the clamps stand on (NTC_COF, NTC_STM, NTC_WAND and their sensed ends) that is not locked."""
    nets = {"NTC_COF", "NTC_STM", "NTC_WAND", "NTC_COF_SENS", "NTC_STM_SENS", "NTC_WAND_SENS"}
    return [f"{item['kind']} {item['uuid']} on {item['net']}" for item in items if bare(item["net"]) in nets and not item["locked"]]


if __name__ == "__main__":
    unittest.main()
