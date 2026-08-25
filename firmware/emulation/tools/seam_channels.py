#!/usr/bin/env python3
"""What the hardware seam declares, read out of its own source.

The emulation run and the suites that judge it work from figures the seam
declares: the channels it enumerates, and the scale the converter behind those
channels reports at. Written down and left there, each of those is a copy, and a
copy is a thing that eventually disagrees with the original -- a channel added to
the seam without a converter input or a compare register behind it, exactly the
defect this tier exists to catch, would be a channel the run never reaches and
the suite never misses, and every assertion would pass over the smaller, older
set.

So the declarations are read here, and the callers assert their own figures
against what this returns. The reading follows the same convention as the
build-time header checks beside it (`firmware/tools/check_actuation_declaration.py`):
comments and string literals are stripped first, the enum body is found by the
type it names, and the terminating count is named rather than taken as "the last
one", so a channel appended after the count is reported instead of silently
becoming the terminator.

A source that cannot be read, or that declares no such enumeration or no such
macro, raises rather than returning an empty list or a stand-in figure. A check
that inspects nothing must not report success.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIRMWARE_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
INCLUDE_DIR = os.path.join(FIRMWARE_DIR, "include")
FIRMWARE_TOOLS = os.path.join(FIRMWARE_DIR, "tools")

if FIRMWARE_TOOLS not in sys.path:
    sys.path.insert(0, FIRMWARE_TOOLS)

from vendor_symbols import strip_comments_and_strings  # noqa: E402

#: The sensor channels the control logic can read, and the count terminating them.
SENSOR_HEADER = os.path.join(INCLUDE_DIR, "hw_interface.h")
SENSOR_TYPE = "hw_sensor_channel_t"
SENSOR_COUNT = "HW_SENSOR_CHANNEL_COUNT"

#: The output channels the control logic can command, and the count terminating them.
OUTPUT_HEADER = os.path.join(INCLUDE_DIR, "machine_actuation.h")
OUTPUT_TYPE = "actuation_channel_t"
OUTPUT_COUNT = "ACTUATION_CHANNEL_COUNT"

_ENUMERATOR = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)")


class Unreadable(RuntimeError):
    """The source is not there, or declares no such enumeration or macro."""


def defined_value(path, macro):
    """The whole number a source file defines a macro as.

    Written once here rather than in each caller, because two of them already
    ask this of the same file about the same pair of macros -- the converter's
    full scale -- and two readers of one declaration are what eventually
    disagree about it. Deliberately narrow: it reads a decimal figure and
    nothing else, so a macro defined as an expression is reported as absent
    rather than guessed at.
    """
    if not os.path.isfile(path):
        raise Unreadable("no source at %s to read %s out of" % (path, macro))

    with open(path, "r", encoding="utf-8") as handle:
        found = re.search(r"#define\s+%s\s+(\d+)\b" % re.escape(macro), handle.read())
    if found is None:
        raise Unreadable("%s declares no #define %s" % (path, macro))
    return int(found.group(1))


def declared(path, type_name, count_name):
    """The enumerators of `type_name` in declaration order, without the count."""
    if not os.path.isfile(path):
        raise Unreadable("no header at %s to read %s out of" % (path, type_name))

    with open(path, "r", encoding="utf-8") as handle:
        cleaned = strip_comments_and_strings(handle.read())

    body = re.search(
        r"\benum\b[^;{]*\{([^}]*)\}\s*" + re.escape(type_name) + r"\s*;",
        cleaned, re.DOTALL)
    if body is None:
        raise Unreadable(
            "%s declares no %s, so the channels it is meant to enumerate "
            "cannot be established" % (path, type_name))

    names = []
    for entry in body.group(1).split(","):
        matched = _ENUMERATOR.match(entry)
        if matched is not None:
            names.append(matched.group(1))

    if count_name not in names:
        raise Unreadable(
            "%s declares %s without a terminating %s, so how many channels "
            "there are cannot be established" % (path, type_name, count_name))
    if names[-1] != count_name:
        raise Unreadable(
            "%s declares a channel after %s, which the count does not cover"
            % (path, count_name))
    return [name for name in names if name != count_name]


def sensor_channels():
    """{index: name} for every sensor channel the seam declares."""
    return dict(enumerate(declared(SENSOR_HEADER, SENSOR_TYPE, SENSOR_COUNT)))


def output_channels():
    """{index: name} for every output channel the seam declares."""
    return dict(enumerate(declared(OUTPUT_HEADER, OUTPUT_TYPE, OUTPUT_COUNT)))
