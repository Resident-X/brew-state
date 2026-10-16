"""The firmware's sensor-channel-to-pin assignment check, against synthetic tables, maps and records.

The check exists to fail when the firmware and the pin allocation record
disagree about which sensor is on which controller pin, so every case that
matters is a seeded fault in an otherwise agreeing set, and the set itself is
shown to pass. The vacuous states are tested too -- an empty record, an empty
map, a firmware with no table -- because those are where a comparison reports
success having compared nothing.

Nothing here reads this project's own firmware, map or any real record. The
enumeration, the firmware source, the map and the record are synthetic and live
in a temporary directory. PyYAML is required, not optional: a test that skipped
without it would pass on a host that cannot run the check.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

import yaml  # noqa: F401  -- required; an import failure is the failure

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

from test_plant_checks import run_check  # noqa: E402

SCRIPT = "check_sensor_assignment.py"

ENUMERATION = """
#ifndef HW_INTERFACE_H
#define HW_INTERFACE_H
typedef enum {
    TEST_SENSOR_ALPHA = 0,
    /* a comment, with commas, naming TEST_SENSOR_WRONG */
    TEST_SENSOR_BETA,
    TEST_SENSOR_GAMMA,
    HW_SENSOR_CHANNEL_COUNT
} hw_sensor_channel_t;
#endif
"""

DEFAULT_INPUTS = ("ADC_CHANNEL_0", "ADC_CHANNEL_1", "SENSOR_INPUT_NONE")
DEFAULT_MAP = [("ADC_CHANNEL_0", "PA0"), ("ADC_CHANNEL_1", "PA1"), ("ADC_CHANNEL_7", "PA7")]
DEFAULT_RECORD = [("TEST_SENSOR_ALPHA", "PA0"), ("TEST_SENSOR_BETA", "PA1")]


def firmware_source(inputs=DEFAULT_INPUTS, labels=None):
    """A firmware source with one positional converter-channel table."""
    labels = labels or ["TEST_SENSOR_ALPHA", "TEST_SENSOR_BETA", "TEST_SENSOR_GAMMA"]
    rows = ",\n".join(f"    {name} /* {label} */" for name, label in zip(inputs, labels))
    return f"""
#include "hal.h"
#define SENSOR_INPUT_NONE 0xFFFFFFFFu
/* sensor_adc_channel[] = {{ ADC_CHANNEL_9 }} is only a comment */
static const uint32_t sensor_adc_channel[HW_SENSOR_CHANNEL_COUNT] = {{
{rows}
}};
"""


def map_text(entries=None, extra=""):
    entries = entries if entries is not None else DEFAULT_MAP
    lines = ["inputs:"]
    for name, pin in entries:
        lines.append(f"  - converter_input: {name}")
        if pin is not None:
            lines.append(f"    controller_pin: {pin}")
    return "\n".join(lines) + "\n" + extra


def record_text(entries=None, extra=""):
    entries = entries if entries is not None else DEFAULT_RECORD
    lines = ["channels:"]
    for channel, pin in entries:
        lines.append(f"  - net: NET_{channel}")
        lines.append(f"    firmware_sensor: {channel}")
        if pin is not None:
            lines.append(f"    controller_pin: {pin}")
    return "\n".join(lines) + "\n" + extra


class Set:
    """A synthetic include directory, firmware source, map and record on disk."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.include = os.path.join(self.root, "include")
        os.makedirs(self.include)
        self.enumeration = os.path.join(self.include, "hw_interface.h")
        self.firmware = os.path.join(self.root, "hw_test.c")
        self.map = os.path.join(self.root, "controller-input-map.yaml")
        self.record = os.path.join(self.root, "pin-allocation.yaml")
        self.write(self.enumeration, ENUMERATION)
        self.write(self.firmware, firmware_source())
        self.write(self.map, map_text())
        self.write(self.record, record_text())

    def cleanup(self):
        self._tmp.cleanup()

    @staticmethod
    def write(path, text):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    @staticmethod
    def write_bytes(path, data):
        with open(path, "wb") as handle:
            handle.write(data)

    def run(self, *, hide_yaml=False):
        args = [
            "--firmware", self.firmware, "--include-dir", self.include,
            "--record", self.record, "--map", self.map,
        ]
        if not hide_yaml:
            return run_check(SCRIPT, *args)
        # sys.modules['yaml'] = None makes `import yaml` raise ImportError.
        program = (
            "import sys, runpy; sys.modules['yaml'] = None; "
            f"sys.argv = {[os.path.join(TOOLS, SCRIPT), *args]!r}; "
            f"runpy.run_path({os.path.join(TOOLS, SCRIPT)!r}, run_name='__main__')"
        )
        return subprocess.run(
            [sys.executable, "-c", program], capture_output=True, text=True, check=False
        )


class SensorAssignmentCase(unittest.TestCase):
    def setUp(self):
        self.set = Set()
        self.addCleanup(self.set.cleanup)

    def failing(self, *mentions):
        result = self.set.run()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        for mention in mentions:
            self.assertIn(mention, result.stderr)
        return result

    def uninspectable(self, *mentions):
        result = self.set.run()
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        for mention in mentions:
            self.assertIn(mention, result.stderr)
        return result

    def firmware(self, **kwargs):
        self.set.write(self.set.firmware, firmware_source(**kwargs))

    def map(self, entries=None, extra=""):
        self.set.write(self.set.map, map_text(entries, extra))

    def record(self, entries=None, extra=""):
        self.set.write(self.set.record, record_text(entries, extra))


class UnmodifiedSet(SensorAssignmentCase):
    def test_the_unmodified_synthetic_set_passes(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The unmodified synthetic set passes.
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A firmware assignment that matches the record on every channel passes.
        result = self.set.run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("2 channel(s)", result.stdout)

    def test_a_channel_the_firmware_states_as_wired_to_no_input_needs_no_record_entry(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A channel the firmware states as wired to no input is not an assignment.
        result = self.set.run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("TEST_SENSOR_GAMMA", result.stdout + result.stderr)

    def test_a_record_entry_without_a_firmware_sensor_takes_no_part(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: Only record entries that carry a firmware_sensor key take part in the comparison; the other checks hold the rest.
        self.record(
            extra=(
                "  - net: BOARD_ONLY\n    controller_pin: PA1\n"
                "  - firmware_channel: TEST_OUTPUT_ALPHA\n    controller_pin: PB3\n"
                "  - net: NO_PIN_AT_ALL\n"
            )
        )
        result = self.set.run()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_comment_labels_beside_the_table_are_not_what_names_a_channel(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: The converter input is read from the table by the enumeration's order, never by a comment beside the entry.
        self.firmware(labels=["WRONG_ONE", "WRONG_TWO", "WRONG_THREE"])
        result = self.set.run()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_an_input_named_in_a_comment_is_not_read_as_the_table(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A channel on a different pin than the record names fails.
        self.map([("ADC_CHANNEL_0", "PA0"), ("ADC_CHANNEL_1", "PA1"), ("ADC_CHANNEL_9", "PA9")])
        self.record([("TEST_SENSOR_ALPHA", "PA9"), ("TEST_SENSOR_BETA", "PA1")])
        self.failing("TEST_SENSOR_ALPHA", "PA0", "PA9")


class PinDisagreement(SensorAssignmentCase):
    def test_a_channel_on_a_different_pin_than_the_record_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: The check fails when the converter input the firmware assigns a sensor channel resolves, through the map, to a pin other than the one the record names, naming the channel and both pins.
        self.record([("TEST_SENSOR_ALPHA", "PA0"), ("TEST_SENSOR_BETA", "PA5")])
        result = self.failing("TEST_SENSOR_BETA", "PA1", "PA5")
        self.assertNotIn("TEST_SENSOR_ALPHA", result.stderr)

    def test_the_pin_follows_the_map_and_not_the_converter_input_number(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: The pin comes from the map's entry for the channel's converter input.
        self.map([("ADC_CHANNEL_0", "PC4"), ("ADC_CHANNEL_1", "PA1")])
        self.failing("TEST_SENSOR_ALPHA", "PC4", "PA0")
        self.record([("TEST_SENSOR_ALPHA", "PC4"), ("TEST_SENSOR_BETA", "PA1")])
        result = self.set.run()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_same_number_on_another_port_is_a_different_pin(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A channel on a different pin than the record names fails.
        self.record([("TEST_SENSOR_ALPHA", "PB0"), ("TEST_SENSOR_BETA", "PA1")])
        self.failing("TEST_SENSOR_ALPHA", "PA0", "PB0")

    def test_a_record_entry_naming_a_pin_for_a_channel_wired_to_no_input_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A channel the firmware states as wired to no input is not an assignment, so a record entry naming a pin for it fails.
        self.record(DEFAULT_RECORD + [("TEST_SENSOR_GAMMA", "PA7")])
        self.failing("TEST_SENSOR_GAMMA", "PA7", "wired to no input")

    def test_a_channel_named_twice_in_the_record_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A channel named twice fails.
        self.record(DEFAULT_RECORD + [("TEST_SENSOR_ALPHA", "PA0")])
        self.failing("TEST_SENSOR_ALPHA", "2 times")

    def test_a_converter_input_named_twice_in_the_firmware_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A converter input named twice fails.
        self.firmware(inputs=("ADC_CHANNEL_0", "ADC_CHANNEL_0", "SENSOR_INPUT_NONE"))
        self.failing("ADC_CHANNEL_0", "TEST_SENSOR_ALPHA", "TEST_SENSOR_BETA")

    def test_a_converter_input_named_twice_in_the_map_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A converter input named twice fails.
        self.map(DEFAULT_MAP + [("ADC_CHANNEL_0", "PA0")])
        self.failing("ADC_CHANNEL_0", "2 times")

    def test_two_channels_on_one_pin_fail_in_the_map_and_in_the_record(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A channel on a different pin than the record names fails (two channels cannot share a pin).
        self.map([("ADC_CHANNEL_0", "PA0"), ("ADC_CHANNEL_1", "PA0")])
        self.record([("TEST_SENSOR_ALPHA", "PA0"), ("TEST_SENSOR_BETA", "PA0")])
        self.failing("pin PA0", "firmware assigns it to", "record gives it to")

    def test_a_pin_not_written_as_port_letter_then_number_fails_in_the_record_and_the_map(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: A pin is written as the record writes a pin; any other form is an input that cannot be read.
        for written in ("pa0", "0", "PA16", "A0", "PA-0"):
            with self.subTest(written=written, where="record"):
                self.record([("TEST_SENSOR_ALPHA", f"'{written}'"), ("TEST_SENSOR_BETA", "PA1")])
                self.failing("TEST_SENSOR_ALPHA", written)
                self.record()
            with self.subTest(written=written, where="map"):
                self.map([("ADC_CHANNEL_0", f"'{written}'"), ("ADC_CHANNEL_1", "PA1")])
                self.failing("ADC_CHANNEL_0", written)
                self.map()

    def test_a_table_entry_that_is_not_a_plain_input_constant_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C1: The converter input is read from the firmware table's plain constants.
        for written in ("ADC_CHANNEL_0 | ADC_CHANNEL_1", "ADC_CHANNEL_ALL", "3", "0xFFFFFFFFu"):
            with self.subTest(written=written):
                self.firmware(inputs=(written, "ADC_CHANNEL_1", "SENSOR_INPUT_NONE"))
                self.failing("TEST_SENSOR_ALPHA", "cannot be read")


class OneSided(SensorAssignmentCase):
    def test_a_firmware_channel_no_record_entry_names_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A sensor channel the firmware assigns that no such entry names fails the check, naming the channel.
        self.record([("TEST_SENSOR_ALPHA", "PA0")])
        self.failing("TEST_SENSOR_BETA", "ADC_CHANNEL_1", "no record entry names it")

    def test_a_record_entry_for_a_channel_the_firmware_does_not_assign_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A record entry naming a sensor channel the firmware does not assign fails the check, naming the channel.
        self.firmware(inputs=("ADC_CHANNEL_0", "ADC_CHANNEL_1"))
        self.record(DEFAULT_RECORD + [("TEST_SENSOR_GAMMA", "PA7")])
        self.failing("TEST_SENSOR_GAMMA", "PA7", "the firmware does not assign it")

    def test_a_record_entry_for_a_channel_outside_the_enumeration_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A record entry naming a sensor channel the firmware does not assign fails the check, naming the channel.
        self.record(DEFAULT_RECORD + [("TEST_SENSOR_DELTA", "PA6")])
        self.failing("TEST_SENSOR_DELTA", "PA6", "no such channel")

    def test_a_firmware_table_longer_than_the_enumeration_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A sensor channel present in only one of the firmware assignment and the record fails the check.
        self.firmware(
            inputs=DEFAULT_INPUTS + ("ADC_CHANNEL_7",),
            labels=["A", "B", "C", "EXTRA"],
        )
        self.failing("4 input(s) for an enumeration of 3")

    def test_a_converter_input_the_map_does_not_list_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A converter input the map does not list fails.
        self.map([("ADC_CHANNEL_0", "PA0")])
        self.failing("TEST_SENSOR_BETA", "ADC_CHANNEL_1", "not listed in the map")

    def test_every_one_sided_channel_is_named_in_the_one_run(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: Each fault names the channel.
        self.record([("TEST_SENSOR_ALPHA", "PA0"), ("TEST_SENSOR_DELTA", "PA6")])
        self.failing("TEST_SENSOR_BETA", "TEST_SENSOR_DELTA")


class UnusableInputs(SensorAssignmentCase):
    def test_a_record_that_is_not_yaml_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A record that cannot be read fails.
        self.set.write(self.set.record, "channels: [unclosed\n  - : :\n")
        self.failing("cannot be parsed")

    def test_a_record_repeating_a_key_or_using_a_merge_key_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A record that cannot be read fails.
        self.set.write(
            self.set.record,
            "channels:\n  - firmware_sensor: TEST_SENSOR_ALPHA\n    controller_pin: PA0\n"
            "    controller_pin: PA1\n",
        )
        self.failing("controller_pin", "more than once")
        self.set.write(
            self.set.record,
            "base: &b\n  controller_pin: PA0\nchannels:\n"
            "  - <<: *b\n    firmware_sensor: TEST_SENSOR_ALPHA\n",
        )
        self.failing("merge key")

    def test_an_empty_or_shapeless_record_fails_rather_than_passing_any_firmware(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A record that lists nothing to compare fails, since an empty subject would otherwise pass.
        for text, mention in (
            ("", "'channels' list"),
            ("channels: notalist\n", "'channels' list"),
            ("channels: []\n", "names no channel"),
            ("channels:\n  - net: ONLY_THE_BOARD\n    controller_pin: PA0\n", "names no channel"),
            ("channels:\n  - firmware_channel: TEST_OUTPUT\n    controller_pin: PB3\n", "names no channel"),
        ):
            with self.subTest(text=text):
                self.set.write(self.set.record, text)
                self.failing(mention)

    def test_an_entry_missing_its_pin_or_name_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A record that cannot be read fails.
        self.record([("TEST_SENSOR_ALPHA", "PA0"), ("TEST_SENSOR_BETA", None)])
        self.failing("TEST_SENSOR_BETA", "no 'controller_pin'")
        for value in ("", "~", "[a, b]"):
            with self.subTest(value=value):
                self.record(extra=f"  - firmware_sensor: {value}\n    controller_pin: PA6\n")
                self.failing("firmware_sensor", "empty or not a name")

    def test_a_map_that_cannot_be_read_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A map that cannot be read fails.
        for text, mention in (
            ("inputs: [unclosed\n  - : :\n", "cannot be parsed"),
            ("", "'inputs' list"),
            ("inputs: notalist\n", "'inputs' list"),
            ("other: 1\n", "'inputs' list"),
            ("inputs:\n  - justastring\n", "not a mapping"),
            ("inputs:\n  - controller_pin: PA0\n", "converter_input"),
            ("inputs:\n  - converter_input: ADC_CHANNEL_0\n", "controller_pin"),
            (
                "inputs:\n  - converter_input: ADC_CHANNEL_0\n    converter_input: ADC_CHANNEL_1\n"
                "    controller_pin: PA0\n",
                "more than once",
            ),
        ):
            with self.subTest(text=text):
                self.set.write(self.set.map, text)
                self.failing(mention)

    def test_a_record_with_bytes_that_are_not_text_cannot_be_inspected(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A record that cannot be read fails.
        self.set.write_bytes(self.set.record, b"\xff\xfe\x00bad")
        self.uninspectable("pin allocation record", "cannot be read")

    def test_a_map_with_bytes_that_are_not_text_cannot_be_inspected(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A map that cannot be read fails.
        self.set.write_bytes(self.set.map, b"\xff\xfe\x00bad")
        self.uninspectable("converter-input map", "cannot be read")

    def test_a_firmware_source_with_bytes_that_are_not_text_cannot_be_inspected(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A firmware source that cannot be read fails.
        self.set.write_bytes(self.set.firmware, b"\xff\xfe\x00bad")
        self.uninspectable("firmware source", "cannot be read")

    def test_an_enumeration_header_with_bytes_that_are_not_text_cannot_be_inspected(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A firmware that cannot be read fails.
        self.set.write_bytes(self.set.enumeration, b"\xff\xfe\x00bad")
        self.uninspectable("sensor channel enumeration header", "cannot be read")

    def test_an_empty_map_fails_rather_than_passing_any_firmware(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A map that lists nothing to compare fails, since an empty subject would otherwise pass.
        self.set.write(self.set.map, "inputs: []\n")
        self.failing("lists no converter input")

    def test_firmware_with_no_converter_table_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A firmware that cannot be read or lists nothing to compare fails.
        self.set.write(self.set.firmware, "int main(void) { return 0; }\n")
        self.failing("no converter-channel table")

    def test_a_table_only_inside_a_comment_is_not_a_table(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A firmware that cannot be read or lists nothing to compare fails.
        self.set.write(
            self.set.firmware,
            "/* static const uint32_t sensor_adc_channel[3] = { ADC_CHANNEL_0, ADC_CHANNEL_1 }; */\n",
        )
        self.failing("no converter-channel table")

    def test_an_empty_table_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A firmware that cannot be read or lists nothing to compare fails.
        self.set.write(self.set.firmware, "static const uint32_t sensor_adc_channel[] = { };\n")
        self.failing("lists no input")

    def test_a_table_declared_twice_fails(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: A firmware that cannot be read fails (two tables are not one).
        self.set.write(self.set.firmware, firmware_source() + firmware_source())
        self.failing("more than once")

    def test_a_missing_file_is_reported_as_not_inspected(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: An input that is not there is reported as not inspected, not as passing.
        for attribute, mention in (
            ("record", "no pin allocation record"),
            ("map", "no converter-input map"),
            ("firmware", "no firmware source"),
            ("enumeration", "no sensor channel enumeration"),
        ):
            with self.subTest(attribute=attribute):
                path = getattr(self.set, attribute)
                with open(path, encoding="utf-8") as handle:
                    saved = handle.read()
                os.remove(path)
                self.uninspectable("could not inspect", mention)
                self.set.write(path, saved)

    def test_an_enumeration_declaring_no_channel_is_reported_as_not_inspected(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C2: An enumeration with nothing in it leaves nothing to compare, which is not a pass.
        self.set.write(
            self.set.enumeration,
            "typedef enum { HW_SENSOR_CHANNEL_COUNT } hw_sensor_channel_t;\n",
        )
        self.uninspectable("could not inspect", "no sensor channel")


class SeededFaults(SensorAssignmentCase):
    """Each comparison fault, introduced into the passing set, must fail and be named."""

    def test_the_set_each_fault_is_seeded_into_passes(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The unmodified synthetic set passes.
        result = self.set.run()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_channel_on_another_pin_is_caught_and_named(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a channel on another pin and require the check to fail on it and to name it.
        self.record([("TEST_SENSOR_ALPHA", "PA0"), ("TEST_SENSOR_BETA", "PA5")])
        self.failing("TEST_SENSOR_BETA", "PA1", "PA5")

    def test_a_channel_missing_from_the_firmware_is_caught_and_named(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a channel missing from the firmware and require the check to fail on it and to name it.
        self.firmware(inputs=("ADC_CHANNEL_0",))
        self.failing("TEST_SENSOR_BETA")

    def test_a_channel_missing_from_the_record_is_caught_and_named(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a channel missing from the record and require the check to fail on it and to name it.
        self.record([("TEST_SENSOR_BETA", "PA1")])
        self.failing("TEST_SENSOR_ALPHA")

    def test_an_input_missing_from_the_map_is_caught_and_named(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce an input missing from the map and require the check to fail on it and to name it.
        self.map([("ADC_CHANNEL_1", "PA1")])
        self.failing("TEST_SENSOR_ALPHA", "ADC_CHANNEL_0")

    def test_a_channel_named_twice_is_caught_and_named(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a channel named twice and require the check to fail on it and to name it.
        self.record(DEFAULT_RECORD + [("TEST_SENSOR_BETA", "PA1")])
        self.failing("TEST_SENSOR_BETA")

    def test_a_record_entry_for_a_channel_wired_to_no_input_is_caught_and_named(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a record entry naming a pin for a channel the firmware states as wired to no input and require the check to fail on it and to name it.
        self.record(DEFAULT_RECORD + [("TEST_SENSOR_GAMMA", "PA7")])
        self.failing("TEST_SENSOR_GAMMA")

    def test_an_unreadable_map_is_caught_and_named(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce an unreadable map and require the check to fail on it and to name it.
        self.set.write(self.set.map, "inputs: [unclosed\n  - : :\n")
        self.failing("map", "cannot be parsed")
        os.remove(self.set.map)
        self.uninspectable("could not inspect", "converter-input map")

    def test_an_empty_record_is_caught_and_named(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce an empty record and require the check to fail on it and to name it.
        self.set.write(self.set.record, "channels: []\n")
        self.failing("record", "names no channel")

    def test_a_run_without_pyyaml_reports_it_could_not_inspect_rather_than_passing(self):
        # SOL-FW-SENSOR-ASSIGNMENT-MATCHES-RECORD.C3: A run without PyYAML reports that it could not inspect rather than passing.
        result = self.set.run(hide_yaml=True)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("could not inspect", result.stderr)
        self.assertIn("PyYAML", result.stderr)
        self.assertNotIn("assigned the pins the record names", result.stdout)


if __name__ == "__main__":
    unittest.main()
