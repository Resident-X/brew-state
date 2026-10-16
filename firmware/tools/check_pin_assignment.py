#!/usr/bin/env python3
"""Fail when the firmware's channel-to-pin assignment differs from a pin allocation record.

A board and the code that drives it must not disagree about which output is
which. The board's side of that is held by the board check; this holds the
firmware's side, so the board tool never reads firmware source and this tier
never reads a board. Both are held to the same record.

The firmware's assignment is read out of its source rather than restated here:

  * the output pin table, the positional array of pins in the order of the
    channel vocabulary's enumerators -- so a channel is identified by its place
    in the table and never by a comment beside the entry, and
  * the port the table's pins are initialised on, read from the
    HAL_GPIO_Init call in the function that consumes the table, so a port moved
    in the firmware is a port moved here too.

Each pin is written as the port letter then number, as in PC6, which is how the
record writes it. The record is the pin allocation record's `channels` list; an
entry takes part when it carries a `firmware_channel` key naming a channel by
the identifier the vocabulary gives it, and the rest of the record belongs to
the board check. The record is read strictly: a key given twice or a YAML merge
key is refused, since a reader and this check could each take a different value.

Checked, each failure naming the channel and both pins where both exist:

  * a channel the firmware assigns that no record entry names,
  * a record entry naming a channel the firmware does not assign,
  * a channel assigned to a different pin than the record names,
  * a channel the record names twice, and two channels on one pin, whether the
    repeat is in the firmware table or in the record,
  * a record that cannot be parsed, has no entry naming a channel, or has an
    entry naming a channel without a usable controller_pin.

It fails rather than passes when there is nothing to inspect: an empty record
would otherwise pass any firmware, and firmware in which no pin table is found
would pass any record.

Exit status: 0 when the assignment matches, 1 when it does not, 2 when the check
could not inspect its input (a file that is not there, no vocabulary, or PyYAML
not installed).

Usage: check_pin_assignment.py --firmware <source> --include-dir <dir> --record <yaml>
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_actuation_declaration import VOCABULARY_HEADER, vocabulary  # noqa: E402
from check_support_status import Uninspectable, read_input  # noqa: E402
from vendor_symbols import strip_comments_and_strings  # noqa: E402

#: The array the firmware lists each output channel's pin in.
PIN_TABLE = "output_pin"

#: The keys of the record this check reads. The rest belong to the board check.
RECORD_CHANNELS = "channels"
RECORD_CHANNEL = "firmware_channel"
RECORD_PIN = "controller_pin"

#: A controller pin as the record writes it: the port letter then the number.
_RECORD_PIN = re.compile(r"^P([A-K])([0-9]|1[0-5])$")
_TABLE_PIN = re.compile(r"^GPIO_PIN_([0-9]|1[0-5])$")
_PORT_INIT = re.compile(r"\bHAL_GPIO_Init\s*\(\s*GPIO([A-K])\s*,")

_TABLE_DECLARATION = re.compile(
    r"\b" + PIN_TABLE + r"\s*\[[^\]]*\]\s*=\s*\{"
)
_TABLE_NAME = re.compile(r"\b" + PIN_TABLE + r"\s*\[")

INSTALL_HINT = "install it (pip install pyyaml, or the python3-yaml package)"


class RecordForm(Exception):
    """The record is YAML, but not in the one form this check reads."""


def load_yaml():
    """PyYAML, or the reason this check cannot run without it."""
    try:
        import yaml
    except ImportError as absent:
        raise Uninspectable(
            f"PyYAML is needed to read the pin allocation record and is not installed; "
            f"{INSTALL_HINT}"
        ) from absent
    return yaml


def strict_yaml(yaml, text: str):
    """The YAML document in `text`, refusing a key given twice or a merge key."""

    class Loader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        keys = set()
        for key_node, _ in node.value:
            line = key_node.start_mark.line + 1
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise RecordForm(
                    f"it uses a YAML merge key (<<) at line {line}; write every key out in full"
                )
            key = loader.construct_object(key_node, deep=True)
            if key in keys:
                raise RecordForm(
                    f"it gives the key '{key}' more than once (again at line {line}); "
                    "give it once"
                )
            keys.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    return yaml.load(text, Loader=Loader)


def read_record(
    path: str, key: str = RECORD_CHANNEL
) -> tuple[dict[str, list[str]], list[str]]:
    """The record's pins by channel, and what stops the record being usable.

    `key` is the entry key that names a channel for the check reading the
    record; an entry without it belongs to another check and takes no part.
    Each channel maps to every pin the record gives it, in order, so a channel
    named twice is visible rather than collapsed into the last entry.
    """
    yaml = load_yaml()
    if not os.path.isfile(path):
        raise Uninspectable(f"no pin allocation record at {path}")

    problems: list[str] = []
    text = read_input(path, "pin allocation record")
    try:
        document = strict_yaml(yaml, text)
    except RecordForm as refused:
        return {}, [f"record {path}: {refused}"]
    except yaml.YAMLError as unreadable:
        detail = str(unreadable).replace("\n", " ")
        return {}, [f"record {path}: it cannot be parsed as YAML ({detail})"]

    if not isinstance(document, dict) or not isinstance(document.get(RECORD_CHANNELS), list):
        return {}, [f"record {path}: it has no '{RECORD_CHANNELS}' list"]

    pins: dict[str, list[str]] = {}
    for index, entry in enumerate(document[RECORD_CHANNELS], start=1):
        where = f"record entry {index}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: it is not a mapping of keys")
            continue
        if key not in entry:
            # Held by the board check, which compares the rest of the record.
            continue
        channel = entry[key]
        if not isinstance(channel, str) or not channel.strip():
            problems.append(f"{where}: its '{key}' is empty or not a name")
            continue
        pin = entry.get(RECORD_PIN)
        if pin is None:
            problems.append(f"{where} ({channel}): it has no '{RECORD_PIN}'")
            continue
        if not isinstance(pin, str) or _RECORD_PIN.match(pin) is None:
            problems.append(
                f"{where} ({channel}): '{RECORD_PIN}' {pin!r} is not a pin written as the "
                "port letter then number, as in PC6"
            )
            continue
        pins.setdefault(channel, []).append(pin)

    if not pins and not problems:
        problems.append(
            f"record {path}: no entry carries '{key}', so it names no channel to "
            "compare and would pass any firmware"
        )
    return pins, problems


def top_level_blocks(source: str) -> list[tuple[int, int]]:
    """The spans of every outermost brace pair in already-stripped source."""
    spans: list[tuple[int, int]] = []
    depth = 0
    start = 0
    for position, character in enumerate(source):
        if character == "{":
            if depth == 0:
                start = position
            depth += 1
        elif character == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                spans.append((start, position))
    return spans


def read_firmware(path: str, channels: list[str]) -> tuple[dict[str, str], list[str]]:
    """The pin the firmware gives each channel, and what stops the table being read.

    The table is positional, so the channel at each place is the vocabulary's
    enumerator at that place. A place beyond the vocabulary names no channel,
    and a channel beyond the table is one the firmware does not assign.
    """
    if not os.path.isfile(path):
        raise Uninspectable(f"no firmware source at {path}")

    cleaned = strip_comments_and_strings(read_input(path, "firmware source"))

    declarations = list(_TABLE_DECLARATION.finditer(cleaned))
    if not declarations:
        return {}, [f"firmware {path}: no pin table named '{PIN_TABLE}' is found"]
    if len(declarations) > 1:
        return {}, [f"firmware {path}: '{PIN_TABLE}' is declared more than once"]

    declaration = declarations[0]
    close = cleaned.find("}", declaration.end())
    if close < 0:
        return {}, [f"firmware {path}: the '{PIN_TABLE}' table is never closed"]

    elements = [element.strip() for element in cleaned[declaration.end():close].split(",")]
    if elements and elements[-1] == "":
        elements.pop()
    if not elements:
        return {}, [f"firmware {path}: the '{PIN_TABLE}' table lists no pin"]

    problems: list[str] = []
    numbers: list[int | None] = []
    for place, element in enumerate(elements):
        named = _TABLE_PIN.match(element)
        if named is None:
            label = channels[place] if place < len(channels) else f"place {place}"
            problems.append(
                f"firmware {PIN_TABLE}[{place}] ({label}): '{element}' is not a plain GPIO_PIN_n "
                "constant, so the pin cannot be read"
            )
            numbers.append(None)
        else:
            numbers.append(int(named.group(1)))

    if len(elements) > len(channels):
        problems.append(
            f"firmware {PIN_TABLE} lists {len(elements)} pin(s) for a vocabulary of "
            f"{len(channels)} channel(s), so a pin names no channel"
        )

    port, port_problems = table_port(cleaned, declaration.start())
    problems.extend(port_problems)

    assigned: dict[str, str] = {}
    if port is not None:
        for channel, number in zip(channels, numbers):
            if number is not None:
                assigned[channel] = f"P{port}{number}"
    return assigned, problems


def table_port(cleaned: str, declaration_start: int) -> tuple[str | None, list[str]]:
    """The port letter the table's pins are initialised on, from where the table is used."""
    uses = [
        match.start()
        for match in _TABLE_NAME.finditer(cleaned)
        if match.start() != declaration_start
    ]
    blocks = [
        (start, end)
        for start, end in top_level_blocks(cleaned)
        if any(start < use < end for use in uses)
    ]
    if not blocks:
        return None, [
            f"firmware: '{PIN_TABLE}' is never used inside a function, so the port its pins "
            "are initialised on cannot be read"
        ]

    ports = sorted(
        {
            found.group(1)
            for start, end in blocks
            for found in _PORT_INIT.finditer(cleaned, start, end)
        }
    )
    if len(ports) != 1:
        found = ", ".join(f"GPIO{port}" for port in ports) or "none"
        return None, [
            f"firmware: the function using '{PIN_TABLE}' initialises pins on {found} through "
            "HAL_GPIO_Init(GPIOx, ...); exactly one port is needed to write each pin as a "
            "port letter then number"
        ]
    return ports[0], []


def compare(
    channels: list[str],
    assigned: dict[str, str],
    recorded: dict[str, list[str]],
) -> list[str]:
    """Every way the firmware's assignment and the record's disagree."""
    findings: list[str] = []

    for channel in channels:
        if channel in assigned and channel not in recorded:
            findings.append(
                f"channel {channel}: firmware assigns {assigned[channel]}, "
                "no record entry names it"
            )
    for channel, pins in recorded.items():
        if channel not in assigned and channel in channels:
            findings.append(
                f"channel {channel}: record names {pins[0]}, the firmware does not assign it"
            )
        elif channel not in channels:
            findings.append(
                f"channel {channel}: record names {pins[0]}, the vocabulary has no such channel "
                "so the firmware does not assign it"
            )
    for channel, pins in recorded.items():
        if len(pins) > 1:
            findings.append(
                f"channel {channel}: record names it {len(pins)} times ({', '.join(pins)})"
            )
    for channel in channels:
        if channel in assigned and channel in recorded:
            if assigned[channel] not in recorded[channel]:
                findings.append(
                    f"channel {channel}: firmware assigns {assigned[channel]}, "
                    f"record names {', '.join(recorded[channel])}"
                )

    by_firmware: dict[str, list[str]] = {}
    for channel in channels:
        if channel in assigned:
            by_firmware.setdefault(assigned[channel], []).append(channel)
    for pin, sharing in by_firmware.items():
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
    parser.add_argument("--firmware", required=True, help="the source file holding the output pin table")
    parser.add_argument(
        "--include-dir", required=True, help="the directory the channel vocabulary sits in"
    )
    parser.add_argument(
        "--record",
        required=True,
        help=f"the pin allocation record (YAML, a '{RECORD_CHANNELS}' list whose entries carry "
        f"'{RECORD_CHANNEL}' and '{RECORD_PIN}')",
    )
    args = parser.parse_args(argv)

    try:
        channels = vocabulary(os.path.join(args.include_dir, VOCABULARY_HEADER))
        if not channels:
            raise Uninspectable(
                "the vocabulary declares no channel, so there is nothing for a pin to be assigned to"
            )
        recorded, record_problems = read_record(args.record)
        assigned, firmware_problems = read_firmware(args.firmware, channels)
    except Uninspectable as absent:
        print(f"check_pin_assignment: could not inspect: {absent}", file=sys.stderr)
        return 2

    # Compared only when both halves were read in full: a half that was not
    # would report every channel it lost as a disagreement of its own.
    findings = firmware_problems + record_problems
    if not findings:
        findings = compare(channels, assigned, recorded)

    if findings:
        print(
            "check_pin_assignment: the firmware's channel-to-pin assignment is not the one the "
            "record names",
            file=sys.stderr,
        )
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1

    print(
        f"check_pin_assignment: {len(assigned)} channel(s) are assigned the pins the record names"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
