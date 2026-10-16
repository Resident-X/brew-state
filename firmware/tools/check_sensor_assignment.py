#!/usr/bin/env python3
"""Fail when the firmware's sensor-channel-to-pin assignment differs from a pin allocation record.

A board and the code that reads it must not disagree about which sensor is
which. The board's side of that is held by the board check; this holds the
firmware's side, so the board tool never reads firmware source and this tier
never reads a board. Both are held to the same record.

A sensor channel is held on a converter input, and a converter input names a
controller pin only through a map specific to the controller. So three things
are read and joined:

  * the firmware's converter-channel table, the positional array of converter
    inputs in the order of the sensor channel enumeration -- a channel is
    identified by its place in the table and never by a comment beside the
    entry. An entry written as the firmware's no-input constant states that the
    channel is wired to no input, which is not an assignment;
  * the controller's converter-input map, a `inputs` list whose entries give a
    `converter_input` as the firmware names it and the `controller_pin` it
    reaches;
  * the pin allocation record's `channels` list, of which an entry takes part
    when it carries a `firmware_sensor` key naming a channel by the identifier
    the enumeration gives it. The rest of the record belongs to the board check
    and to the output pin check.

Each pin is written as the port letter then number, as in PC6. Both YAML files
are read strictly, as the output pin check reads its record.

Checked, each failure naming the channel and both pins where both exist:

  * a channel the firmware assigns that no record entry names, and a record
    entry naming a channel the firmware does not assign,
  * a channel whose converter input resolves through the map to a different pin
    than the record names,
  * a record entry naming a pin for a channel the firmware states as wired to no
    input,
  * a converter input the map does not list,
  * a channel or converter input named twice, and two channels on one pin,
  * a map, record or firmware that cannot be parsed or lists nothing to compare.

Exit status: 0 when the assignment matches, 1 when it does not, 2 when the check
could not inspect its input (a file that is not there, no enumeration, or PyYAML
not installed).

Usage: check_sensor_assignment.py --firmware <source> --include-dir <dir>
           --record <yaml> --map <yaml>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_estimator_limits import CHANNEL_COUNT, CHANNEL_HEADER, CHANNEL_TYPE  # noqa: E402
from check_parameter_origins import enumerators  # noqa: E402
from check_pin_assignment import (  # noqa: E402
    _RECORD_PIN,
    RECORD_CHANNELS,
    RECORD_PIN,
    RecordForm,
    load_yaml,
    read_record,
    strict_yaml,
)
from check_support_status import Uninspectable, read_input  # noqa: E402
from vendor_symbols import strip_comments_and_strings  # noqa: E402

#: The array the firmware lists each sensor channel's converter input in, and the
#: constant it writes for a channel wired to no input.
INPUT_TABLE = "sensor_adc_channel"
NO_INPUT = "SENSOR_INPUT_NONE"

#: The record key that names a sensor channel, and the map's keys.
RECORD_SENSOR = "firmware_sensor"
MAP_INPUTS = "inputs"
MAP_INPUT = "converter_input"

_TABLE_INPUT = re.compile(r"^ADC_CHANNEL_[0-9]+$")
_TABLE_DECLARATION = re.compile(r"\b" + INPUT_TABLE + r"\s*\[[^\]]*\]\s*=\s*\{")


def read_map(path: str) -> tuple[dict[str, list[str]], list[str]]:
    """The map's pins by converter input, and what stops the map being usable.

    Each input maps to every pin the map gives it, in order, so an input listed
    twice is visible rather than collapsed into the last entry.
    """
    yaml = load_yaml()
    if not os.path.isfile(path):
        raise Uninspectable(f"no converter-input map at {path}")

    text = read_input(path, "converter-input map")
    try:
        document = strict_yaml(yaml, text)
    except RecordForm as refused:
        return {}, [f"map {path}: {refused}"]
    except yaml.YAMLError as unreadable:
        detail = str(unreadable).replace("\n", " ")
        return {}, [f"map {path}: it cannot be parsed as YAML ({detail})"]

    if not isinstance(document, dict) or not isinstance(document.get(MAP_INPUTS), list):
        return {}, [f"map {path}: it has no '{MAP_INPUTS}' list"]

    pins: dict[str, list[str]] = {}
    problems: list[str] = []
    for index, entry in enumerate(document[MAP_INPUTS], start=1):
        where = f"map entry {index}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: it is not a mapping of keys")
            continue
        name = entry.get(MAP_INPUT)
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{where}: its '{MAP_INPUT}' is missing, empty or not a name")
            continue
        pin = entry.get(RECORD_PIN)
        if not isinstance(pin, str) or _RECORD_PIN.match(pin) is None:
            problems.append(
                f"{where} ({name}): '{RECORD_PIN}' {pin!r} is not a pin written as the "
                "port letter then number, as in PC6"
            )
            continue
        pins.setdefault(name, []).append(pin)

    if not pins and not problems:
        problems.append(f"map {path}: it lists no converter input, so no channel could resolve")
    return pins, problems


def read_firmware(path: str, channels: list[str]) -> tuple[dict[str, str | None], list[str]]:
    """The converter input the firmware gives each channel, and what stops the table being read.

    A channel the firmware states as wired to no input maps to None. The table
    is positional, so the channel at each place is the enumeration's enumerator
    at that place; a channel beyond the table is one the firmware does not
    assign.
    """
    if not os.path.isfile(path):
        raise Uninspectable(f"no firmware source at {path}")

    cleaned = strip_comments_and_strings(read_input(path, "firmware source"))

    declarations = list(_TABLE_DECLARATION.finditer(cleaned))
    if not declarations:
        return {}, [f"firmware {path}: no converter-channel table named '{INPUT_TABLE}' is found"]
    if len(declarations) > 1:
        return {}, [f"firmware {path}: '{INPUT_TABLE}' is declared more than once"]

    close = cleaned.find("}", declarations[0].end())
    if close < 0:
        return {}, [f"firmware {path}: the '{INPUT_TABLE}' table is never closed"]

    elements = [element.strip() for element in cleaned[declarations[0].end():close].split(",")]
    if elements and elements[-1] == "":
        elements.pop()
    if not elements:
        return {}, [f"firmware {path}: the '{INPUT_TABLE}' table lists no input"]

    problems: list[str] = []
    assigned: dict[str, str | None] = {}
    for place, element in enumerate(elements):
        label = channels[place] if place < len(channels) else f"place {place}"
        if element == NO_INPUT:
            value = None
        elif _TABLE_INPUT.match(element):
            value = element
        else:
            problems.append(
                f"firmware {INPUT_TABLE}[{place}] ({label}): '{element}' is neither a plain "
                f"ADC_CHANNEL_n constant nor {NO_INPUT}, so the input cannot be read"
            )
            continue
        if place < len(channels):
            assigned[channels[place]] = value

    if len(elements) > len(channels):
        problems.append(
            f"firmware {INPUT_TABLE} lists {len(elements)} input(s) for an enumeration of "
            f"{len(channels)} channel(s), so an input names no channel"
        )
    return assigned, problems


def compare(
    channels: list[str],
    assigned: dict[str, str | None],
    mapped: dict[str, list[str]],
    recorded: dict[str, list[str]],
) -> list[str]:
    """Every way the firmware's assignment and the record's disagree."""
    findings: list[str] = []

    for channel in channels:
        if channel in assigned and assigned[channel] is not None and channel not in recorded:
            findings.append(
                f"channel {channel}: firmware assigns {assigned[channel]}, no record entry names it"
            )
    for channel, pins in recorded.items():
        if channel not in channels:
            findings.append(
                f"channel {channel}: record names {pins[0]}, the enumeration has no such channel "
                "so the firmware does not assign it"
            )
        elif channel not in assigned:
            findings.append(
                f"channel {channel}: record names {pins[0]}, the firmware does not assign it"
            )
        elif assigned[channel] is None:
            findings.append(
                f"channel {channel}: record names {pins[0]}, the firmware states it as wired to "
                "no input"
            )
        if len(pins) > 1:
            findings.append(
                f"channel {channel}: record names it {len(pins)} times ({', '.join(pins)})"
            )

    for name, pins in mapped.items():
        if len(pins) > 1:
            findings.append(f"converter input {name}: map lists it {len(pins)} times ({', '.join(pins)})")

    by_input: dict[str, list[str]] = {}
    for channel in channels:
        name = assigned.get(channel)
        if name is not None:
            by_input.setdefault(name, []).append(channel)
    for name, sharing in by_input.items():
        if len(sharing) > 1:
            findings.append(f"converter input {name}: firmware assigns it to {', '.join(sharing)}")

    resolved: dict[str, str] = {}
    for channel in channels:
        name = assigned.get(channel)
        if name is None:
            continue
        if name not in mapped:
            findings.append(f"channel {channel}: converter input {name} is not listed in the map")
            continue
        resolved[channel] = mapped[name][0]
        if channel in recorded and resolved[channel] not in recorded[channel]:
            findings.append(
                f"channel {channel}: firmware assigns {name}, which the map gives as "
                f"{resolved[channel]}; record names {', '.join(recorded[channel])}"
            )

    by_pin: dict[str, list[str]] = {}
    for channel, pin in resolved.items():
        by_pin.setdefault(pin, []).append(channel)
    for pin, sharing in by_pin.items():
        if len(sharing) > 1:
            findings.append(f"pin {pin}: firmware assigns it to {', '.join(sharing)}")

    by_record: dict[str, list[str]] = {}
    for channel, pins in recorded.items():
        for pin in set(pins):
            by_record.setdefault(pin, []).append(channel)
    for pin, sharing in by_record.items():
        if len(sharing) > 1:
            findings.append(f"pin {pin}: record gives it to {', '.join(sorted(sharing))}")

    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--firmware", required=True, help="the source file holding the converter-channel table")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the sensor channel enumeration sits in"
    )
    parser.add_argument(
        "--record",
        required=True,
        help=f"the pin allocation record (YAML, a '{RECORD_CHANNELS}' list whose entries carry "
        f"'{RECORD_SENSOR}' and '{RECORD_PIN}')",
    )
    parser.add_argument(
        "--map",
        required=True,
        help=f"the controller's converter-input map (YAML, an '{MAP_INPUTS}' list whose entries "
        f"carry '{MAP_INPUT}' and '{RECORD_PIN}')",
    )
    args = parser.parse_args(argv)

    try:
        header = os.path.join(args.include_dir, CHANNEL_HEADER)
        if not os.path.isfile(header):
            raise Uninspectable(f"no sensor channel enumeration header at {header}")
        header_text = read_input(header, "sensor channel enumeration header")
        channels = [name for name in enumerators(header_text, CHANNEL_TYPE) if name != CHANNEL_COUNT]
        if not channels:
            raise Uninspectable(
                "the enumeration declares no sensor channel, so there is nothing for a pin to be "
                "assigned to"
            )
        recorded, record_problems = read_record(args.record, RECORD_SENSOR)
        mapped, map_problems = read_map(args.map)
        assigned, firmware_problems = read_firmware(args.firmware, channels)
    except Uninspectable as absent:
        print(f"check_sensor_assignment: could not inspect: {absent}", file=sys.stderr)
        return 2

    # Compared only when every part was read in full: a part that was not would
    # report everything it lost as a disagreement of its own.
    findings = firmware_problems + record_problems + map_problems
    if not findings:
        findings = compare(channels, assigned, mapped, recorded)

    if findings:
        print(
            "check_sensor_assignment: the firmware's sensor-channel-to-pin assignment is not the "
            "one the record names",
            file=sys.stderr,
        )
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1

    count = sum(1 for name in assigned.values() if name is not None)
    print(f"check_sensor_assignment: {count} channel(s) are assigned the pins the record names")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
