"""The firmware's channel-to-pin assignment check, against synthetic firmware and records.

The check exists to fail when the firmware and the pin allocation record
disagree about which output is which, so every case that matters is a seeded
fault in an otherwise agreeing pair, and the pair itself is shown to pass. The
vacuous states are tested too -- an empty record, a record naming nothing, a
firmware with no table -- because those are where a comparison reports success
having compared nothing.

Nothing here reads this project's own firmware or any real record. The
vocabulary, the firmware source and the record are synthetic and live in a
temporary directory, so a legitimate change to the machine's channels or pins
does not break these tests. PyYAML is required, not optional: a test that
skipped without it would pass on a host that cannot run the check.
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

SCRIPT = "check_pin_assignment.py"

CHANNELS = ["TEST_CHANNEL_ALPHA", "TEST_CHANNEL_BETA", "TEST_CHANNEL_GAMMA"]

VOCABULARY = """
#ifndef MACHINE_ACTUATION_H
#define MACHINE_ACTUATION_H
typedef enum {
    TEST_CHANNEL_ALPHA = 0,
    TEST_CHANNEL_BETA,
    TEST_CHANNEL_GAMMA,
    ACTUATION_CHANNEL_COUNT
} actuation_channel_t;
#endif
"""


def firmware_source(pins=("GPIO_PIN_3", "GPIO_PIN_4", "GPIO_PIN_5"), port="GPIOB", labels=None):
    """A firmware source with one positional pin table and the init call consuming it."""
    labels = labels or CHANNELS
    rows = ",\n".join(
        f"    {pin} /* {label} */" for pin, label in zip(pins, labels)
    )
    return f"""
#include "hal.h"
/* output_pin[] = {{ GPIO_PIN_9 }} is only a comment */
static const uint16_t output_pin[] = {{
{rows}
}};

static bool init_outputs(void)
{{
    GPIO_InitTypeDef init = {{ 0 }};
    uint32_t mask = 0;
    for (int i = 0; i < 3; i++) {{
        mask |= output_pin[i];
    }}
    init.Pin = mask;
    HAL_GPIO_Init({port}, &init);
    return true;
}}
"""


def record_text(entries=None, extra=""):
    """A pin allocation record; `entries` are (channel, pin) pairs."""
    entries = entries if entries is not None else [
        ("TEST_CHANNEL_ALPHA", "PB3"),
        ("TEST_CHANNEL_BETA", "PB4"),
        ("TEST_CHANNEL_GAMMA", "PB5"),
    ]
    lines = ["channels:"]
    for channel, pin in entries:
        lines.append(f"  - net: NET_{channel}")
        lines.append(f"    firmware_channel: {channel}")
        if pin is not None:
            lines.append(f"    controller_pin: {pin}")
    return "\n".join(lines) + "\n" + extra


class Pair:
    """A synthetic include directory, firmware source and record on disk."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.include = os.path.join(self.root, "include")
        os.makedirs(self.include)
        self.vocabulary_path = os.path.join(self.include, "machine_actuation.h")
        self.firmware = os.path.join(self.root, "hw_test.c")
        self.record = os.path.join(self.root, "pin-allocation.yaml")
        self.write(self.vocabulary_path, VOCABULARY)
        self.write(self.firmware, firmware_source())
        self.write(self.record, record_text())

    def cleanup(self):
        self._tmp.cleanup()

    @staticmethod
    def write(path, text):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def run(self, *, hide_yaml=False):
        args = ["--firmware", self.firmware, "--include-dir", self.include, "--record", self.record]
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


class PinAssignmentCase(unittest.TestCase):
    def setUp(self):
        self.pair = Pair()
        self.addCleanup(self.pair.cleanup)

    def failing(self, *mentions):
        result = self.pair.run()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        for mention in mentions:
            self.assertIn(mention, result.stderr)
        return result

    def uninspectable(self, *mentions):
        result = self.pair.run()
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        for mention in mentions:
            self.assertIn(mention, result.stderr)
        return result

    def firmware(self, **kwargs):
        self.pair.write(self.pair.firmware, firmware_source(**kwargs))

    def record(self, entries=None, extra=""):
        self.pair.write(self.pair.record, record_text(entries, extra))


class UnmodifiedPair(PinAssignmentCase):
    def test_the_unmodified_synthetic_pair_passes(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The unmodified synthetic pair passes.
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: A firmware assignment that matches the record on every channel passes.
        result = self.pair.run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("3 channel(s)", result.stdout)

    def test_a_record_entry_without_a_firmware_channel_takes_no_part(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: Only record entries that carry a firmware_channel key take part in the comparison; the board check holds the rest.
        self.pair.write(
            self.pair.record,
            record_text(
                extra="  - net: BOARD_ONLY\n    controller_pin: PB4\n  - net: NO_PIN_AT_ALL\n"
            ),
        )
        result = self.pair.run()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_comment_labels_beside_the_table_are_not_what_names_a_channel(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The check reads the pin from the firmware table's port and pin constants, matching the firmware channel by the vocabulary's order.
        self.firmware(labels=["WRONG_ONE", "WRONG_TWO", "WRONG_THREE"])
        result = self.pair.run()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_pin_named_in_a_comment_is_not_read_as_the_table(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The check reads it from the firmware table's port and pin constants.
        self.record([("TEST_CHANNEL_ALPHA", "PB9"), ("TEST_CHANNEL_BETA", "PB4"), ("TEST_CHANNEL_GAMMA", "PB5")])
        self.failing("TEST_CHANNEL_ALPHA", "PB3", "PB9")


class PinDisagreement(PinAssignmentCase):
    def test_a_channel_on_a_different_pin_than_the_record_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The check fails when the firmware assigns a channel to a controller pin other than the one the pin allocation record names for it, naming the channel and both pins.
        self.firmware(pins=("GPIO_PIN_3", "GPIO_PIN_8", "GPIO_PIN_5"))
        result = self.failing("TEST_CHANNEL_BETA", "PB8", "PB4")
        self.assertNotIn("TEST_CHANNEL_ALPHA:", result.stderr)

    def test_the_port_is_read_from_the_init_call_and_not_fixed_in_the_check(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The pin is the controller pin's own name, port letter then number; the check reads it from the firmware table's port and pin constants.
        self.firmware(port="GPIOD")
        self.failing("TEST_CHANNEL_ALPHA", "PD3", "PB3")
        self.record([("TEST_CHANNEL_ALPHA", "PD3"), ("TEST_CHANNEL_BETA", "PD4"), ("TEST_CHANNEL_GAMMA", "PD5")])
        result = self.pair.run()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_same_number_on_another_port_is_a_different_pin(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The pin is the controller pin's own name, port letter then number.
        self.record([("TEST_CHANNEL_ALPHA", "PA3"), ("TEST_CHANNEL_BETA", "PB4"), ("TEST_CHANNEL_GAMMA", "PB5")])
        self.failing("TEST_CHANNEL_ALPHA", "PB3", "PA3")

    def test_a_channel_named_twice_in_the_record_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: A channel named twice fails whether the repeat is in the firmware table or in the record.
        self.record(
            [
                ("TEST_CHANNEL_ALPHA", "PB3"),
                ("TEST_CHANNEL_BETA", "PB4"),
                ("TEST_CHANNEL_GAMMA", "PB5"),
                ("TEST_CHANNEL_ALPHA", "PB3"),
            ]
        )
        self.failing("TEST_CHANNEL_ALPHA", "2 times")

    def test_two_channels_on_one_pin_in_the_firmware_table_fail(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: Two channels on one controller pin fail whether the repeat is in the firmware table or in the record.
        self.firmware(pins=("GPIO_PIN_3", "GPIO_PIN_3", "GPIO_PIN_5"))
        self.failing("pin PB3", "firmware assigns it to", "TEST_CHANNEL_ALPHA", "TEST_CHANNEL_BETA")

    def test_two_channels_on_one_pin_in_the_record_fail(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: Two channels on one controller pin fail whether the repeat is in the firmware table or in the record.
        self.record([("TEST_CHANNEL_ALPHA", "PB3"), ("TEST_CHANNEL_BETA", "PB3"), ("TEST_CHANNEL_GAMMA", "PB5")])
        self.failing("pin PB3", "record gives it to", "TEST_CHANNEL_ALPHA", "TEST_CHANNEL_BETA")

    def test_a_pin_not_written_as_port_letter_then_number_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The pin is the controller pin's own name, port letter then number, as in PC6.
        for written in ("pb3", "3", "PB16", "B3", "PB-3", "pin 3"):
            with self.subTest(written=written):
                self.record(
                    [("TEST_CHANNEL_ALPHA", f"'{written}'"), ("TEST_CHANNEL_BETA", "PB4"), ("TEST_CHANNEL_GAMMA", "PB5")]
                )
                self.failing("TEST_CHANNEL_ALPHA", written)

    def test_a_table_entry_that_is_not_a_plain_pin_constant_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The check reads the pin from the firmware table's port and pin constants.
        for written in ("GPIO_PIN_3 | GPIO_PIN_4", "GPIO_PIN_All", "3", "GPIO_PIN_16"):
            with self.subTest(written=written):
                self.firmware(pins=(written, "GPIO_PIN_4", "GPIO_PIN_5"))
                self.failing("TEST_CHANNEL_ALPHA", "cannot be read")


class OneSided(PinAssignmentCase):
    def test_a_firmware_channel_no_record_entry_names_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A channel the firmware assigns that no record entry names fails the check, naming the channel.
        self.record([("TEST_CHANNEL_ALPHA", "PB3"), ("TEST_CHANNEL_BETA", "PB4")])
        self.failing("TEST_CHANNEL_GAMMA", "PB5", "no record entry names it")

    def test_a_record_entry_for_a_channel_the_firmware_does_not_assign_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record entry naming a channel the firmware does not assign fails the check, naming the channel.
        self.firmware(pins=("GPIO_PIN_3", "GPIO_PIN_4"))
        self.failing("TEST_CHANNEL_GAMMA", "PB5", "the firmware does not assign it")

    def test_a_record_entry_for_a_channel_outside_the_vocabulary_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record entry naming a channel the firmware does not assign fails the check, naming the channel.
        self.record(
            [
                ("TEST_CHANNEL_ALPHA", "PB3"),
                ("TEST_CHANNEL_BETA", "PB4"),
                ("TEST_CHANNEL_GAMMA", "PB5"),
                ("TEST_CHANNEL_DELTA", "PB6"),
            ]
        )
        self.failing("TEST_CHANNEL_DELTA", "PB6", "no such channel")

    def test_a_firmware_table_longer_than_the_vocabulary_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A channel present in only one of the firmware assignment and the record fails the check.
        self.firmware(
            pins=("GPIO_PIN_3", "GPIO_PIN_4", "GPIO_PIN_5", "GPIO_PIN_6"),
            labels=CHANNELS + ["EXTRA"],
        )
        self.failing("4 pin(s) for a vocabulary of 3")

    def test_every_one_sided_channel_is_named_in_the_one_run(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: Each fault names the channel.
        self.record([("TEST_CHANNEL_ALPHA", "PB3"), ("TEST_CHANNEL_BETA", "PB4"), ("TEST_CHANNEL_DELTA", "PB6")])
        self.failing("TEST_CHANNEL_GAMMA", "TEST_CHANNEL_DELTA")


class UnusableRecord(PinAssignmentCase):
    def test_a_record_that_is_not_yaml_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that cannot be parsed fails.
        self.pair.write(self.pair.record, "channels: [unclosed\n  - : :\n")
        self.failing("cannot be parsed")

    def test_a_record_with_bytes_that_are_not_text_cannot_be_inspected(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that cannot be parsed fails.
        with open(self.pair.record, "wb") as handle:
            handle.write(b"\xff\xfe\x00bad")
        self.uninspectable("pin allocation record", "cannot be read")

    def test_a_record_repeating_a_key_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that repeats a key fails.
        self.pair.write(
            self.pair.record,
            "channels:\n  - firmware_channel: TEST_CHANNEL_ALPHA\n    controller_pin: PB3\n"
            "    controller_pin: PB4\n",
        )
        self.failing("controller_pin", "more than once")

    def test_a_record_using_a_merge_key_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that repeats a key fails (a merge key folds one in unseen).
        self.pair.write(
            self.pair.record,
            "base: &b\n  controller_pin: PB3\nchannels:\n"
            "  - <<: *b\n    firmware_channel: TEST_CHANNEL_ALPHA\n",
        )
        self.failing("merge key")

    def test_a_record_with_no_channels_list_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that has no entry naming a channel fails.
        for text in ("", "other: 1\n", "channels: notalist\n", "- just\n- a list\n"):
            with self.subTest(text=text):
                self.pair.write(self.pair.record, text)
                self.failing("'channels' list")

    def test_an_empty_channels_list_fails_rather_than_passing_any_firmware(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that has no entry naming a channel fails, since an empty record would otherwise pass any firmware.
        self.pair.write(self.pair.record, "channels: []\n")
        self.failing("names no channel")

    def test_a_record_whose_entries_name_no_channel_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that has no entry naming a channel fails.
        self.pair.write(
            self.pair.record,
            "channels:\n  - net: ONLY_THE_BOARD\n    controller_pin: PB3\n",
        )
        self.failing("names no channel")

    def test_an_entry_missing_its_controller_pin_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that has an entry missing its controller_pin fails.
        self.record([("TEST_CHANNEL_ALPHA", "PB3"), ("TEST_CHANNEL_BETA", None), ("TEST_CHANNEL_GAMMA", "PB5")])
        self.failing("TEST_CHANNEL_BETA", "no 'controller_pin'")

    def test_an_entry_whose_firmware_channel_is_empty_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that has an entry missing its firmware_channel fails.
        for value in ("", "~", "[a, b]", "7"):
            with self.subTest(value=value):
                self.record(extra=f"  - firmware_channel: {value}\n    controller_pin: PB6\n")
                self.failing("firmware_channel", "empty or not a name")

    def test_an_entry_that_is_not_a_mapping_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: A record that cannot be parsed into entries fails.
        self.record(extra="  - justastring\n")
        self.failing("not a mapping")


class UnusableFirmware(PinAssignmentCase):
    def test_firmware_with_no_pin_table_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: Firmware in which no pin table is found fails.
        self.pair.write(self.pair.firmware, "static bool init_outputs(void) { return true; }\n")
        self.failing("no pin table")

    def test_a_table_only_inside_a_comment_is_not_a_table(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: Firmware in which no pin table is found fails.
        self.pair.write(
            self.pair.firmware,
            "/* static const uint16_t output_pin[] = { GPIO_PIN_3, GPIO_PIN_4, GPIO_PIN_5 }; */\n",
        )
        self.failing("no pin table")

    def test_an_empty_pin_table_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: Firmware in which no pin table is found fails.
        self.pair.write(self.pair.firmware, "static const uint16_t output_pin[] = { };\n")
        self.failing("lists no pin")

    def test_a_table_no_function_uses_leaves_no_port_to_read_and_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The port is read from the source and never fixed in the check.
        self.pair.write(
            self.pair.firmware,
            "static const uint16_t output_pin[] = { GPIO_PIN_3, GPIO_PIN_4, GPIO_PIN_5 };\n",
        )
        self.failing("never used inside a function")

    def test_a_table_used_with_no_recognisable_port_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The port is read from the source and never fixed in the check.
        self.pair.write(
            self.pair.firmware,
            firmware_source().replace("HAL_GPIO_Init(GPIOB,", "HAL_GPIO_Init(OUTPUT_PORT,"),
        )
        self.failing("exactly one port")

    def test_a_table_initialised_on_two_ports_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C1: The port is read from the source and never fixed in the check.
        self.pair.write(
            self.pair.firmware,
            firmware_source().replace(
                "return true;", "HAL_GPIO_Init(GPIOC, &init);\n    return true;"
            ),
        )
        self.failing("GPIOB, GPIOC", "exactly one port")

    def test_a_table_declared_twice_fails(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: Firmware in which no pin table is found fails (and two are not one).
        self.pair.write(self.pair.firmware, firmware_source() + firmware_source())
        self.failing("more than once")


class NotInspectable(PinAssignmentCase):
    def test_a_missing_record_file_is_reported_as_not_inspected(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: The check reports an input it could not read as not inspected, not as passing.
        os.remove(self.pair.record)
        self.uninspectable("could not inspect", "no pin allocation record")

    def test_a_missing_firmware_file_is_reported_as_not_inspected(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: The check reports an input it could not read as not inspected, not as passing.
        os.remove(self.pair.firmware)
        self.uninspectable("could not inspect", "no firmware source")

    def test_a_missing_vocabulary_is_reported_as_not_inspected(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C2: The check reports an input it could not read as not inspected, not as passing.
        os.remove(self.pair.vocabulary_path)
        self.uninspectable("could not inspect", "no vocabulary header")


class SeededFaults(PinAssignmentCase):
    """Each comparison fault, introduced into the passing pair, must fail and be named."""

    def test_the_pair_each_fault_is_seeded_into_passes(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The unmodified synthetic pair passes.
        result = self.pair.run()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_channel_on_another_pin_is_caught_and_named(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a channel on another pin and require the check to fail on it and to name it.
        self.record([("TEST_CHANNEL_ALPHA", "PB3"), ("TEST_CHANNEL_BETA", "PB7"), ("TEST_CHANNEL_GAMMA", "PB5")])
        self.failing("TEST_CHANNEL_BETA", "PB4", "PB7")

    def test_a_channel_missing_from_the_firmware_is_caught_and_named(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a channel missing from the firmware and require the check to fail on it and to name it.
        self.firmware(pins=("GPIO_PIN_3", "GPIO_PIN_4"))
        self.failing("TEST_CHANNEL_GAMMA")

    def test_a_channel_missing_from_the_record_is_caught_and_named(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a channel missing from the record and require the check to fail on it and to name it.
        self.record([("TEST_CHANNEL_BETA", "PB4"), ("TEST_CHANNEL_GAMMA", "PB5")])
        self.failing("TEST_CHANNEL_ALPHA")

    def test_a_channel_named_twice_is_caught_and_named(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a channel named twice and require the check to fail on it and to name it.
        self.record(
            [
                ("TEST_CHANNEL_ALPHA", "PB3"),
                ("TEST_CHANNEL_BETA", "PB4"),
                ("TEST_CHANNEL_BETA", "PB4"),
                ("TEST_CHANNEL_GAMMA", "PB5"),
            ]
        )
        self.failing("TEST_CHANNEL_BETA")

    def test_two_channels_on_one_pin_are_caught_and_named(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce two channels on one pin and require the check to fail on it and to name it.
        self.firmware(pins=("GPIO_PIN_3", "GPIO_PIN_4", "GPIO_PIN_4"))
        self.record([("TEST_CHANNEL_ALPHA", "PB3"), ("TEST_CHANNEL_BETA", "PB4"), ("TEST_CHANNEL_GAMMA", "PB4")])
        self.failing("TEST_CHANNEL_BETA", "TEST_CHANNEL_GAMMA", "PB4")

    def test_an_entry_missing_its_controller_pin_is_caught_and_named(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce an entry missing its controller pin and require the check to fail on it and to name it.
        self.record([("TEST_CHANNEL_ALPHA", "PB3"), ("TEST_CHANNEL_BETA", "PB4"), ("TEST_CHANNEL_GAMMA", None)])
        self.failing("TEST_CHANNEL_GAMMA")

    def test_an_empty_record_is_caught(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce an empty record and require the check to fail on it and to name it.
        self.pair.write(self.pair.record, "channels: []\n")
        self.failing("record", "names no channel")

    def test_a_firmware_source_with_no_pin_table_is_caught(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: The tests introduce a firmware source with no pin table and require the check to fail on it and to name it.
        self.pair.write(self.pair.firmware, "int main(void) { return 0; }\n")
        self.failing("firmware", "no pin table")

    def test_a_run_without_pyyaml_reports_it_could_not_inspect_rather_than_passing(self):
        # SOL-FW-PIN-ASSIGNMENT-MATCHES-RECORD.C3: A run without PyYAML reports that it could not inspect rather than passing.
        result = self.pair.run(hide_yaml=True)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("could not inspect", result.stderr)
        self.assertIn("PyYAML", result.stderr)
        self.assertIn("pip install pyyaml", result.stderr)
        self.assertNotIn("assigned the pins the record names", result.stdout)


if __name__ == "__main__":
    unittest.main()
