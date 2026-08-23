#!/usr/bin/env python3
"""The estimator's quantity-to-state pairing gate, against synthetic subjects.

The gate exists to fail, so every case here is driven from both sides: a
pairing that holds passes, and a pairing with the specific defect the gate
names is caught. The vacuous case -- a vocabulary with nothing in it -- is
tested too, because that is the state in which a gate reports success without
having established anything.

Nothing here is run against this project's own estimator or its real
vocabulary. The quantities, states and channels below are invented, so a
legitimate change to the machine's vocabulary does not break these tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

CHECK = "check_estimator_pairing.py"

VOCABULARY = """
typedef enum {
    PLANT_QUANTITY_HEAT_C = 0,
    /* A rate, supplied rather than accumulated. */
    PLANT_QUANTITY_SQUEEZE_BAR,
    PLANT_QUANTITY_COUNT
} plant_quantity_t;
"""

MEASUREMENT = """
static bool quantity_measured_by(hw_sensor_channel_t channel, plant_quantity_t *quantity)
{
    switch (channel) {
    case HW_SENSOR_HEAT:
        *quantity = PLANT_QUANTITY_HEAT_C;
        return true;
    case HW_SENSOR_CHANNEL_COUNT:
        return false;
    }
    return false;
}
"""

PAIRING = """
static bool state_observed_by(plant_quantity_t quantity, plant_state_t *state)
{
    switch (quantity) {
    case PLANT_QUANTITY_HEAT_C:
        *state = PLANT_STATE_HEAT_C;
        return true;
    /* Supplied rather than accumulated, so no state could correct it. */
    case PLANT_QUANTITY_SQUEEZE_BAR:
        return false;
    /* Not a quantity, and so observed by nothing. */
    case PLANT_QUANTITY_COUNT:
        return false;
    }
    return false;
}
"""


class SyntheticEstimator:
    """A vocabulary header and an estimator source, in a directory of their own."""

    def __init__(self, pairing: str = PAIRING, vocabulary: str = VOCABULARY,
                 measurement: str | None = None):
        self.root = tempfile.mkdtemp()
        self.include = os.path.join(self.root, "include")
        os.makedirs(self.include)
        self._write(os.path.join(self.include, "plant_types.h"), vocabulary)
        self.estimator = os.path.join(self.root, "estimator.c")
        supplied = MEASUREMENT if measurement is None else measurement
        self._write(self.estimator, supplied + pairing)

    @staticmethod
    def _write(path: str, body: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)

    def cleanup(self) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)


def run(subject: SyntheticEstimator) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            os.path.join(TOOLS, CHECK),
            "--estimator",
            subject.estimator,
            "--include-dir",
            subject.include,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class PairingHolds(unittest.TestCase):
    """SOL-PLANT-STEAM-DRAW-REPORTED.C5: a sound pairing passes the gate."""

    def test_a_sound_pairing_passes(self):
        subject = SyntheticEstimator()
        self.addCleanup(subject.cleanup)
        result = run(subject)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("2 quantities answered", result.stdout)


class PairingIsCaught(unittest.TestCase):
    """SOL-PLANT-STEAM-DRAW-REPORTED.C5: each defect the gate names fails the build.

    An unanswered quantity, a default label, a refused quantity a channel
    measures, a paired quantity nothing measures, and a refusal with no reason
    written above it -- each is driven, and each is required to fail with the
    message that makes it actionable.
    """

    def caught(self, pairing: str) -> str:
        subject = SyntheticEstimator(pairing=pairing)
        self.addCleanup(subject.cleanup)
        result = run(subject)
        self.assertEqual(1, result.returncode, result.stdout)
        return result.stderr

    def test_a_quantity_the_pairing_omits_is_caught(self):
        without = PAIRING.replace(
            """    /* Supplied rather than accumulated, so no state could correct it. */
    case PLANT_QUANTITY_SQUEEZE_BAR:
        return false;
""",
            "",
        )
        self.assertIn("names nothing for ['PLANT_QUANTITY_SQUEEZE_BAR']", self.caught(without))

    def test_a_refused_quantity_paired_with_a_state_is_caught(self):
        """The mutation the compiler cannot see: a refusal quietly made a pairing."""
        paired = PAIRING.replace(
            """    case PLANT_QUANTITY_SQUEEZE_BAR:
        return false;""",
            """    case PLANT_QUANTITY_SQUEEZE_BAR:
        *state = PLANT_STATE_HEAT_C;
        return true;""",
        )
        self.assertIn("measured by no channel", self.caught(paired))

    def test_a_measured_quantity_that_is_refused_is_caught(self):
        refused = PAIRING.replace(
            """    case PLANT_QUANTITY_HEAT_C:
        *state = PLANT_STATE_HEAT_C;
        return true;""",
            """    /* Refused, wrongly: a channel measures it. */
    case PLANT_QUANTITY_HEAT_C:
        return false;""",
        )
        self.assertIn("are refused by state_observed_by but measured by", self.caught(refused))

    def test_a_default_label_is_caught(self):
        with_default = PAIRING.replace(
            """    case PLANT_QUANTITY_COUNT:
        return false;""",
            """    case PLANT_QUANTITY_COUNT:
        return false;
    default:
        return false;""",
        )
        self.assertIn("carries a default label", self.caught(with_default))

    def test_a_refusal_with_no_reason_is_caught(self):
        silent = PAIRING.replace(
            "    /* Supplied rather than accumulated, so no state could correct it. */\n", ""
        )
        self.assertIn("with no comment above them", self.caught(silent))


class ParsingIsNotDefeatedByFormatting(unittest.TestCase):
    """SOL-PLANT-STEAM-DRAW-REPORTED.C5: the gate reads code rather than layout.

    Each case here is a way of writing the same C that an earlier form of this
    gate read wrongly. A refusal it cannot see is reported as a pairing, which
    is the direction that passes -- so these are the cases that decide whether
    the gate protects anything at all.
    """

    def caught(self, pairing=None, vocabulary=None, measurement=None):
        subject = SyntheticEstimator(
            pairing=PAIRING if pairing is None else pairing,
            vocabulary=VOCABULARY if vocabulary is None else vocabulary,
            measurement=measurement,
        )
        self.addCleanup(subject.cleanup)
        result = run(subject)
        self.assertEqual(1, result.returncode, result.stdout)
        return result.stderr

    def passes(self, pairing=None, vocabulary=None, measurement=None):
        subject = SyntheticEstimator(
            pairing=PAIRING if pairing is None else pairing,
            vocabulary=VOCABULARY if vocabulary is None else vocabulary,
            measurement=measurement,
        )
        self.addCleanup(subject.cleanup)
        result = run(subject)
        self.assertEqual(0, result.returncode, result.stderr)

    PAIRED_HEAT = "    case PLANT_QUANTITY_HEAT_C:\n        *state = PLANT_STATE_HEAT_C;\n        return true;"

    def test_a_measured_quantity_refused_inside_braces_is_caught(self):
        braced = PAIRING.replace(
            self.PAIRED_HEAT,
            "    /* Refused, wrongly: a channel measures it. */\n"
            "    case PLANT_QUANTITY_HEAT_C: { return false; }",
        )
        self.assertIn("are refused by state_observed_by but measured by", self.caught(braced))

    def test_a_measured_quantity_refused_after_a_statement_is_caught(self):
        delayed = PAIRING.replace(
            self.PAIRED_HEAT,
            "    /* Refused, wrongly: a channel measures it. */\n"
            "    case PLANT_QUANTITY_HEAT_C:\n        (void)state;\n        return false;",
        )
        self.assertIn("are refused by state_observed_by but measured by", self.caught(delayed))

    def test_a_default_appended_to_an_existing_line_is_caught(self):
        inline = PAIRING.replace(
            "    case PLANT_QUANTITY_COUNT:\n        return false;",
            "    case PLANT_QUANTITY_COUNT: return false; default: return false;",
        )
        self.assertIn("carries a default label", self.caught(inline))

    def test_prose_beginning_default_is_not_read_as_a_label(self):
        prosaic = PAIRING.replace(
            "    /* Supplied rather than accumulated, so no state could correct it. */",
            "    /* A note about the switch.\n"
            "     * default: is written here in prose and nowhere in the code.\n"
            "     */",
        )
        self.passes(pairing=prosaic)

    def test_a_refusal_reasoned_with_a_line_comment_is_accepted(self):
        line_commented = PAIRING.replace(
            "    /* Supplied rather than accumulated, so no state could correct it. */",
            "    // Supplied rather than accumulated, so no state could correct it.",
        )
        self.passes(pairing=line_commented)

    def test_a_refusal_stacked_under_one_shared_comment_is_accepted(self):
        vocabulary = VOCABULARY.replace(
            "    PLANT_QUANTITY_COUNT",
            "    PLANT_QUANTITY_WRING_BAR,\n    PLANT_QUANTITY_COUNT",
        )
        stacked = PAIRING.replace(
            "    case PLANT_QUANTITY_SQUEEZE_BAR:\n        return false;",
            "    case PLANT_QUANTITY_SQUEEZE_BAR:\n"
            "    case PLANT_QUANTITY_WRING_BAR:\n        return false;",
        )
        self.passes(pairing=stacked, vocabulary=vocabulary)

    def test_a_quantity_named_only_in_a_string_literal_is_not_measured(self):
        """A log line mentioning a quantity must not make it a measured one."""
        logging = MEASUREMENT.replace(
            "    case HW_SENSOR_HEAT:",
            '    case HW_SENSOR_HEAT:\n        (void)"PLANT_QUANTITY_SQUEEZE_BAR";',
        )
        self.passes(measurement=logging)

    def test_a_quantity_whose_name_prefixes_another_is_told_apart(self):
        """Substring is not the same as named: only the longer one is measured."""
        vocabulary = VOCABULARY.replace(
            "    PLANT_QUANTITY_COUNT",
            "    PLANT_QUANTITY_HEAT_C_FILTERED,\n    PLANT_QUANTITY_COUNT",
        )
        measurement = MEASUREMENT.replace(
            "*quantity = PLANT_QUANTITY_HEAT_C;", "*quantity = PLANT_QUANTITY_HEAT_C_FILTERED;"
        )
        pairing = PAIRING.replace(
            self.PAIRED_HEAT,
            self.PAIRED_HEAT + "\n    case PLANT_QUANTITY_HEAT_C_FILTERED:\n"
            "        *state = PLANT_STATE_HEAT_C;\n        return true;",
        )
        stderr = self.caught(pairing=pairing, vocabulary=vocabulary, measurement=measurement)
        self.assertIn("measured by no channel", stderr)
        self.assertIn("PLANT_QUANTITY_HEAT_C'", stderr)

    def test_a_body_ending_at_a_braced_case_is_not_truncated(self):
        """A closing brace in the first column must not end the body early."""
        wrapped = PAIRING.replace(
            self.PAIRED_HEAT,
            "    case PLANT_QUANTITY_HEAT_C:\n{\n        *state = PLANT_STATE_HEAT_C;\n"
            "        return true;\n}",
        )
        self.passes(pairing=wrapped)


class NothingToInspect(unittest.TestCase):
    """SOL-PLANT-STEAM-DRAW-REPORTED.C5: the gate stops rather than passing vacuously."""

    def test_an_empty_vocabulary_stops_rather_than_passing(self):
        subject = SyntheticEstimator(vocabulary="typedef enum { } plant_quantity_t;\n")
        self.addCleanup(subject.cleanup)
        result = run(subject)
        self.assertEqual(2, result.returncode)
        self.assertIn("would report success without inspecting anything", result.stderr)

    def test_an_absent_pairing_function_stops_rather_than_passing(self):
        subject = SyntheticEstimator(pairing="")
        self.addCleanup(subject.cleanup)
        result = run(subject)
        self.assertEqual(2, result.returncode)
        self.assertIn("does not declare both", result.stderr)


if __name__ == "__main__":
    unittest.main()
