"""The two declarations the estimator's bounds and the loop's cadence are carried in.

Both checks exist to catch an absence rather than a wrong number, which is why
both are driven from the failing side here. A channel with no declared bounds
does not look like anything on a running machine: the estimator goes on
correcting against whatever arrives, the residual it reports looks ordinary, and
the file reads as covered to everybody who opens it. A cadence figure spelled in
two places is the same kind of silence -- the two stop agreeing the first time
either is touched, on exactly the timing question nobody re-reads.

So each check is exercised against a subject carrying the specific defect it
exists for, and the diagnostic is asserted as well as the exit status. The two
are told apart: a finding is exit 1, and a subject the check could not look at
-- a header that declares a channel no word spells, a declaration that is not
there -- is exit 2, because a tree with nothing to inspect that reported success
would be the same silence one layer up.

Nothing here is run against this project's own headers or descriptions except
the two closing cases, which exist to establish that what the project ships
answers the question rather than that the checks merely run.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_plant_checks import (  # noqa: E402
    ORIGIN_VOCABULARY,
    TOOLS,
    SyntheticTree,
    run_check,
    write,
)

# --- The channels a declaration has to account for ---------------------------

#: A hardware seam declaring two channels. Deliberately not this project's four:
#: the check reads the channels out of the seam and derives the word each is
#: spelled as, so a fixture naming the real ones would agree with a check that
#: had hard-coded them.
CHANNEL_SEAM = """
#ifndef HW_INTERFACE_H
#define HW_INTERFACE_H
#include <stdbool.h>
#include <stdint.h>
typedef enum {
    HW_SENSOR_ALPHA_TEMPERATURE = 0,
    HW_SENSOR_BETA_PRESSURE,
    HW_SENSOR_CHANNEL_COUNT
} hw_sensor_channel_t;
typedef struct {
    bool valid;
    int32_t value_milli;
} hw_reading_t;
#endif
"""

#: The header declaring what a limits declaration may say: a word per channel,
#: the two words that are not about any one channel, and what separates a
#: channel's low from its high.
LIMITS_SHAPE = """
#ifndef ESTIMATOR_LIMITS_H
#define ESTIMATOR_LIMITS_H
#include "hw_interface.h"
#include "plant_origin.h"
#define ESTIMATOR_LIMITS_ALPHA_TEMPERATURE_WORD "alpha-temperature"
#define ESTIMATOR_LIMITS_BETA_PRESSURE_WORD "beta-pressure"
#define ESTIMATOR_LIMITS_TOLERANCE_WINDOW_WORD "loss-tolerance-window-ms"
#define ESTIMATOR_LIMITS_EXCURSION_BOUND_WORD "excursion-bound-milli-c"
#define ESTIMATOR_LIMITS_RANGE_MARKER ".."
#endif
"""

#: A declaration bounding every channel the seam above reports and both figures
#: that are not about any one channel, each accounting for where it came from.
BOUNDED = (
    "# What a reading off this synthetic machine may plausibly be.\n"
    "\n"
    "alpha-temperature = -10000 .. 250000 @estimated from a comparable machine of the "
    "same architecture\n"
    "beta-pressure = -1000 .. 20000 @document a datasheet nobody has read for this one\n"
    "\n"
    "loss-tolerance-window-ms = 500 @estimated fifty steps at the declared interval\n"
    "excursion-bound-milli-c = 15000 @estimated the error at which the control law would "
    "respond differently\n"
)


class LimitsTree(SyntheticTree):
    """A tree of structures, the seam's channels, and a declaration per structure.

    Nothing here is the project's own machine-describing structure. A test
    reading the real declaration would fail on the day a commissioned
    measurement displaced an estimate, which is a legitimate edit rather than a
    defect.
    """

    def __init__(self, structures=("alpha",)):
        super().__init__(structures=structures)
        self.params = os.path.join(self.root.name, "params")
        os.makedirs(self.params)
        self.seam(CHANNEL_SEAM)
        self.shape(LIMITS_SHAPE)
        self.origins(ORIGIN_VOCABULARY)

    def seam(self, text: str) -> None:
        """Rewrite the hardware seam, which is where the channels come from."""
        self._write(os.path.join(self.include, "hw_interface.h"), text)

    def shape(self, text: str) -> None:
        """Rewrite the header declaring what a declaration may say."""
        self._write(os.path.join(self.include, "estimator_limits.h"), text)

    def origins(self, text: str) -> None:
        """Rewrite the vocabulary a figure records its origin in."""
        self._write(os.path.join(self.include, "plant_origin.h"), text)

    def declaration(self, structure: str, text: str) -> str:
        """Write one structure's limits declaration, as it ships beside the description."""
        path = os.path.join(self.params, f"{structure}.limits")
        self._write(path, text)
        return path


class EstimatorLimitsCase(unittest.TestCase):
    """One structure, one complete declaration, and the headers behind both."""

    def setUp(self):
        self.tree = LimitsTree()
        self.addCleanup(self.tree.cleanup)
        self.path = self.tree.declaration("alpha", BOUNDED)

    def declare(self, text: str) -> None:
        self.tree.declaration("alpha", text)

    def check(self, **overrides):
        return run_check(
            "check_estimator_limits.py",
            "--include-dir",
            overrides.get("include_dir", self.tree.include),
            "--plant-root",
            overrides.get("plant_root", self.tree.plant),
            "--params-dir",
            overrides.get("params_dir", self.tree.params),
        )


class EveryChannelTheSeamReportsCarriesABound(EstimatorLimitsCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C1: every channel the estimator corrects against carries a low and a high, and the check names the one that does not."""

    def test_a_declaration_bounding_every_channel_passes(self):
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("1 declaration(s)", result.stdout)

    def test_a_channel_with_no_line_fails_and_names_it(self):
        # The failure this whole arrangement exists for. It has no symptom on
        # the running machine, so it has to be caught on the file.
        self.declare(BOUNDED.replace("beta-pressure = -1000 .. 20000", "# beta-pressure"))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("beta-pressure", result.stderr)
        self.assertIn("carries no line", result.stderr)

    def test_a_figure_that_is_not_about_a_channel_and_has_no_line_fails(self):
        # The window and the excursion bound are as defaultable as a channel
        # is, and default the same silent way.
        self.declare(BOUNDED.replace("loss-tolerance-window-ms = 500", "# nothing here"))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("loss-tolerance-window-ms", result.stderr)
        self.assertIn("carries no line", result.stderr)

    def test_a_low_that_is_not_below_its_high_fails(self):
        # A span admitting no reading at all refuses every sample the channel
        # ever takes, which is a channel switched off rather than one bounded.
        self.declare(
            BOUNDED.replace(
                "beta-pressure = -1000 .. 20000", "beta-pressure = 20000 .. -1000"
            )
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("beta-pressure", result.stderr)
        self.assertIn("is not below its high", result.stderr)

    def test_a_low_equal_to_its_high_fails(self):
        self.declare(
            BOUNDED.replace("beta-pressure = -1000 .. 20000", "beta-pressure = 20000 .. 20000")
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("is not below its high", result.stderr)

    def test_a_channel_given_one_figure_rather_than_a_span_fails(self):
        # One figure is not half a span: nothing says whether it was meant as
        # the floor or the ceiling.
        self.declare(BOUNDED.replace("beta-pressure = -1000 .. 20000", "beta-pressure = 20000"))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("beta-pressure", result.stderr)
        self.assertIn("carries no ..", result.stderr)

    def test_a_channel_whose_span_is_not_two_whole_numbers_fails(self):
        self.declare(
            BOUNDED.replace("beta-pressure = -1000 .. 20000", "beta-pressure = low .. high")
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("does not carry two whole numbers", result.stderr)

    def test_a_channel_given_twice_fails(self):
        # Two lines for one channel leave which of them the machine runs on
        # decided by the order they happen to be read in.
        self.declare(BOUNDED + "beta-pressure = -2000 .. 30000 @estimated a second opinion\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("beta-pressure", result.stderr)
        self.assertIn("was already given on line", result.stderr)

    def test_a_name_the_vocabulary_does_not_carry_fails(self):
        # A misspelt channel is worse than an absent one: it looks bounded and
        # leaves the channel it was meant for defaulted.
        self.declare(BOUNDED + "gamma-flow = 0 .. 100 @estimated from nothing\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("gamma-flow", result.stderr)
        self.assertIn("is not something a limits declaration carries", result.stderr)

    def test_a_line_that_is_not_name_equals_value_fails(self):
        self.declare(BOUNDED + "beta pressure is fine\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("is not name = value", result.stderr)

    def test_a_structure_shipping_no_declaration_at_all_fails_and_names_the_structure(self):
        # Every structure carries its own rather than inheriting one, so a
        # structure arriving without a declaration is caught by name.
        self.tree.structure("gamma")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("the 'gamma' structure ships no gamma.limits", result.stderr)

    def test_comments_and_blank_lines_are_not_lines(self):
        # The declaration is written and read by people, and the reasoning
        # behind a bound belongs beside it.
        self.declare(
            "# Why these bounds and not others.\n"
            "\n"
            "   \n"
            "# A comment indented under the line it explains.\n"
            + BOUNDED
            + "\n# And a trailing word about all of it.\n"
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)


class EveryFigureAccountsForWhereItCameFrom(EstimatorLimitsCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C1: each declared figure carries an origin from the vocabulary with an account behind it, unless the declaration says it describes no machine."""

    def test_a_figure_with_no_origin_fails(self):
        self.declare(
            BOUNDED.replace(
                "beta-pressure = -1000 .. 20000 @document a datasheet nobody has read for "
                "this one",
                "beta-pressure = -1000 .. 20000",
            )
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("beta-pressure", result.stderr)
        self.assertIn("carries no origin", result.stderr)

    def test_a_declaration_describing_no_machine_owes_no_origins(self):
        # Numbers that mean nothing have no origin to record, and requiring one
        # would produce a form of words rather than an account.
        self.declare(
            "@describes-no-machine\n"
            "alpha-temperature = -10000 .. 250000\n"
            "beta-pressure = -1000 .. 20000\n"
            "loss-tolerance-window-ms = 500\n"
            "excursion-bound-milli-c = 15000\n"
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_exemption_is_read_wherever_it_is_written(self):
        # It is a statement about the file, so it holds over figures written
        # above it as well as below.
        self.declare(
            "alpha-temperature = -10000 .. 250000\n"
            "beta-pressure = -1000 .. 20000\n"
            "loss-tolerance-window-ms = 500\n"
            "excursion-bound-milli-c = 15000\n"
            "\n@describes-no-machine\n"
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_declaration_claiming_a_machine_still_owes_them(self):
        # The other direction of the same property: without the statement the
        # same file is required to account for every figure it carries.
        self.declare(
            "alpha-temperature = -10000 .. 250000\n"
            "beta-pressure = -1000 .. 20000\n"
            "loss-tolerance-window-ms = 500\n"
            "excursion-bound-milli-c = 15000\n"
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("does not state that it 'describes-no-machine'", result.stderr)

    def test_a_statement_the_declaration_may_not_make_fails(self):
        self.declare(BOUNDED + "@describes-a-machine-nobody-has-seen\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("is not a statement a declaration may make", result.stderr)

    def test_an_origin_kind_outside_the_vocabulary_fails(self):
        # A word nobody declared is a word that no longer separates an estimate
        # from a measurement, which is the whole point of recording one.
        self.declare(BOUNDED.replace("@document a datasheet", "@about-right a datasheet"))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("about-right", result.stderr)
        self.assertIn("which is not one of", result.stderr)

    def test_an_origin_kind_with_no_account_fails(self):
        # The kind says which sort of fact it is; the account is what makes the
        # figure reproducible and challengeable by a reader.
        self.declare(
            BOUNDED.replace("@document a datasheet nobody has read for this one", "@document")
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("beta-pressure", result.stderr)
        self.assertIn("records a kind and no account", result.stderr)

    def test_a_scalar_figure_with_no_account_fails_too(self):
        self.declare(
            BOUNDED.replace(
                "@estimated fifty steps at the declared interval", "@estimated"
            )
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("loss-tolerance-window-ms", result.stderr)
        self.assertIn("records a kind and no account", result.stderr)


class TheLimitsCheckStopsRatherThanReportingSuccess(EstimatorLimitsCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C1: a subject the check cannot look at is told apart from one it looked at and found nothing wrong with."""

    def test_a_channel_the_shape_header_spells_no_word_for_is_could_not_look(self):
        # No declaration could name that channel and no inspection of a
        # declaration would notice it missing, so this is not a finding about
        # any declaration -- it is the check reporting it cannot look.
        self.tree.seam(
            CHANNEL_SEAM.replace(
                "    HW_SENSOR_CHANNEL_COUNT",
                "    HW_SENSOR_GAMMA_FLOW,\n    HW_SENSOR_CHANNEL_COUNT",
            )
        )
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("ESTIMATOR_LIMITS_GAMMA_FLOW_WORD", result.stderr)
        self.assertIn("declares no word", result.stderr)

    def test_a_seam_declaring_no_channel_is_could_not_look(self):
        self.tree.seam(
            CHANNEL_SEAM.replace(
                "    HW_SENSOR_ALPHA_TEMPERATURE = 0,\n    HW_SENSOR_BETA_PRESSURE,\n", ""
            )
        )
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("declares no sensor channels", result.stderr)

    def test_a_shape_header_with_no_range_marker_is_could_not_look(self):
        self.tree.shape(LIMITS_SHAPE.replace('#define ESTIMATOR_LIMITS_RANGE_MARKER ".."', ""))
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("no range marker is declared", result.stderr)

    def test_a_missing_shape_header_is_could_not_look(self):
        os.remove(os.path.join(self.tree.include, "estimator_limits.h"))
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("no estimator_limits.h at", result.stderr)

    def test_a_plant_root_holding_no_structure_is_not_a_pass(self):
        # Nothing to inspect is the state in which a check reports success
        # having established nothing at all.
        empty = os.path.join(self.tree.root.name, "src", "nothing")
        os.makedirs(empty, exist_ok=True)
        result = self.check(plant_root=empty)
        self.assertEqual(1, result.returncode)
        self.assertIn("no plant structure under", result.stderr)


# --- The figures the cadence and the loss behaviour rest on ------------------

#: The two figures that are the same on every machine, as they live in the
#: source: one definition each, in one file.
CADENCE_SOURCE = (
    "#ifndef CONTROL_H\n"
    "#define CONTROL_H\n"
    "\n"
    "/* What one step of the control loop represents. */\n"
    "#define CONTROL_STEP_INTERVAL_MS 10u\n"
    "\n"
    "/* The multiple of it past which a step arrived late. */\n"
    "#define CONTROL_STEP_LATE_MULTIPLE 3u\n"
    "\n"
    "#endif\n"
)

#: A declaration accounting for both of them and carrying no values, because
#: the value lives at the figure's one site in the source.
ACCOUNTED = (
    "# Where the cadence figures came from.\n"
    "\n"
    "step-interval-ms @estimated Estimated from the thermal time constants of the brew "
    "path, which are seconds rather than milliseconds.\n"
    "late-step-multiple @estimated Estimated as the smallest multiple that is a scheduling "
    "failure rather than ordinary jitter.\n"
)


class CadenceTree:
    """A source tree carrying the compiled-in figures, and a declaration of them."""

    def __init__(self):
        self.root = tempfile.TemporaryDirectory()
        self.include = os.path.join(self.root.name, "include")
        self.source = os.path.join(self.root.name, "src")
        os.makedirs(self.include)
        os.makedirs(os.path.join(self.source, "control"))
        write(os.path.join(self.include, "plant_origin.h"), ORIGIN_VOCABULARY)
        self.define("control/control.h", CADENCE_SOURCE)
        self.path = os.path.join(self.root.name, "cadence.declaration")

    def define(self, relative: str, text: str) -> str:
        """Write one source file under the tree, creating the directory it sits in."""
        path = os.path.join(self.source, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, text)
        return path

    def declare(self, text: str) -> str:
        write(self.path, text)
        return self.path

    def cleanup(self) -> None:
        self.root.cleanup()


class CadenceCase(unittest.TestCase):
    """A tree defining each compiled-in figure once, and a declaration of both."""

    def setUp(self):
        self.tree = CadenceTree()
        self.addCleanup(self.tree.cleanup)
        self.tree.declare(ACCOUNTED)

    def declare(self, text: str) -> None:
        self.tree.declare(text)

    def check(self, **overrides):
        return run_check(
            "check_cadence_declaration.py",
            "--include-dir",
            overrides.get("include_dir", self.tree.include),
            "--source-dir",
            overrides.get("source_dir", self.tree.source),
            "--declaration",
            overrides.get("declaration", self.tree.path),
        )


class EveryCadenceFigureAccountsForItself(CadenceCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C10: each compiled-in cadence figure records the kind of fact it is and what it was arrived at from."""

    def test_a_declaration_accounting_for_both_figures_passes(self):
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("2 cadence figure(s)", result.stdout)

    def test_a_figure_accounted_for_nowhere_fails_and_names_it(self):
        # A bare constant with nothing asserting it is the shape a load-bearing
        # number takes just before everybody starts treating it as settled.
        self.declare(
            "step-interval-ms @estimated Estimated from the thermal time constants.\n"
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("late-step-multiple", result.stderr)
        self.assertIn("accounts for itself nowhere", result.stderr)

    def test_a_figure_with_no_origin_marker_fails(self):
        # A name and nothing else is the figure standing there with nothing
        # asserting it, which is the state the declaration exists to end.
        self.declare(
            "step-interval-ms\n"
            "late-step-multiple @estimated Estimated as the smallest unambiguous multiple.\n"
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("step-interval-ms", result.stderr)
        self.assertIn("records no origin", result.stderr)

    def test_a_kind_outside_the_vocabulary_fails(self):
        self.declare(ACCOUNTED.replace("step-interval-ms @estimated", "step-interval-ms @guessed"))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("guessed", result.stderr)
        self.assertIn("which is not one of", result.stderr)

    def test_a_kind_with_no_account_fails(self):
        self.declare(
            "step-interval-ms @estimated\n"
            "late-step-multiple @estimated Estimated as the smallest unambiguous multiple.\n"
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("step-interval-ms", result.stderr)
        self.assertIn("records a kind and no account", result.stderr)

    def test_a_figure_accounted_for_twice_fails(self):
        self.declare(ACCOUNTED + "step-interval-ms @document a second account of the same thing\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("step-interval-ms", result.stderr)
        self.assertIn("was already accounted for on line", result.stderr)

    def test_a_name_no_figure_answers_to_fails(self):
        self.declare(ACCOUNTED + "steppe-interval-ms @estimated a misspelling nothing reads\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("steppe-interval-ms", result.stderr)
        self.assertIn("is not a figure the cadence rests on", result.stderr)

    def test_a_line_naming_no_figure_fails(self):
        self.declare(ACCOUNTED + "@estimated an account of nothing in particular\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("names no figure", result.stderr)

    def test_comments_and_blank_lines_are_not_lines(self):
        self.declare("# The reasoning behind both.\n\n   \n" + ACCOUNTED + "\n# And after them.\n")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)


class EachFigureHasOneHomeAndOnlyOne(CadenceCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C10: a compiled-in figure is defined in exactly one place, and a per-machine figure is defined in none."""

    def test_a_compiled_in_figure_defined_in_two_files_fails_and_names_both(self):
        # Two spellings stop agreeing the first time either is touched, and
        # nothing about the running machine says which one it ran on.
        second = self.tree.define(
            "estimator/estimator.h", "#define CONTROL_STEP_INTERVAL_MS 10u\n"
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("CONTROL_STEP_INTERVAL_MS is defined in", result.stderr)
        self.assertIn(os.path.join(self.tree.source, "control", "control.h"), result.stderr)
        self.assertIn(second, result.stderr)

    def test_a_compiled_in_figure_defined_nowhere_fails(self):
        # The declaration would then describe a figure the software does not
        # have, which reads exactly like one it does.
        self.tree.define("control/control.h", "#define CONTROL_STEP_LATE_MULTIPLE 3u\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("CONTROL_STEP_INTERVAL_MS", result.stderr)
        self.assertIn("defined nowhere", result.stderr)

    def test_a_per_machine_figure_compiled_in_fails_and_names_the_file(self):
        # Worse than a duplicated constant: it goes on reading as declared in
        # every limits file the tree ships while the software ignores all of
        # them.
        offender = self.tree.define(
            "estimator/estimator.c", "#define LOSS_TOLERANCE_WINDOW 500u\n"
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("loss-tolerance-window-ms", result.stderr)
        self.assertIn("belongs to a machine's limits declaration", result.stderr)
        self.assertIn(offender, result.stderr)

    def test_the_excursion_bound_compiled_in_fails_the_same_way(self):
        offender = self.tree.define("estimator/estimator.c", "#define EXCURSION_BOUND 15000\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("excursion-bound-milli-c", result.stderr)
        self.assertIn(offender, result.stderr)

    def test_the_same_identifiers_defined_as_words_are_not_figures(self):
        # The identifiers the two tests above are caught on, carrying string
        # values instead of numbers. A definition whose value is a string
        # spells the name a declaration writes rather than fixing the figure
        # that declaration carries, and a header has to be able to do that for
        # a per-machine figure to be declarable at all.
        write(
            os.path.join(self.tree.include, "estimator_limits.h"),
            '#define LOSS_TOLERANCE_WINDOW "loss-tolerance-window-ms"\n'
            '#define EXCURSION_BOUND "excursion-bound-milli-c"\n',
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_per_machine_figure_given_a_line_here_fails(self):
        # Its account belongs beside its value in the machine's own
        # declaration, and a second account here would stop agreeing with the
        # first the moment either was corrected.
        self.declare(
            ACCOUNTED + "loss-tolerance-window-ms @estimated fifty steps at the interval\n"
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("loss-tolerance-window-ms", result.stderr)
        self.assertIn("varies with the machine", result.stderr)


class AFigureIsFoundHoweverTheFileAroundItIsWritten(CadenceCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C10: a figure is seen wherever it sits in a header, so the check cannot go blind on a file that plainly defines one."""

    #: An include guard immediately above the figure it guards, with no comment
    #: or blank line between them. It is ordinary C and it is the shape that
    #: defeats a scan treating any run of whitespace as the gap between a
    #: definition's name and its value: the guard takes the name and the whole
    #: of the next line becomes its value, so the figure below is never seen at
    #: all. A check blinded that way reports the figure as defined nowhere, and
    #: -- far worse -- stops noticing a second home for it, which is the thing
    #: it exists to catch.
    TIGHT_GUARD = (
        "#ifndef CONTROL_H\n"
        "#define CONTROL_H\n"
        "#define CONTROL_STEP_INTERVAL_MS 10u\n"
        "#define CONTROL_STEP_LATE_MULTIPLE 3u\n"
        "#endif\n"
    )

    def test_a_figure_directly_below_an_include_guard_is_still_found(self):
        self.tree.define("control/control.h", self.TIGHT_GUARD)
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_second_home_directly_below_an_include_guard_is_still_caught(self):
        self.tree.define("control/control.h", self.TIGHT_GUARD)
        self.tree.define(
            "control/cadence_again.h",
            "#ifndef CADENCE_AGAIN_H\n"
            "#define CADENCE_AGAIN_H\n"
            "#define CONTROL_STEP_INTERVAL_MS 10u\n"
            "#endif\n",
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("CONTROL_STEP_INTERVAL_MS is defined in", result.stderr)
        self.assertIn("cadence_again.h", result.stderr)


class TheCadenceCheckStopsRatherThanReportingSuccess(CadenceCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C10: a declaration that is not there, or a tree that cannot be read, is told apart from a clean sweep."""

    def test_a_missing_declaration_is_could_not_look(self):
        os.remove(self.tree.path)
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("no cadence declaration at", result.stderr)

    def test_a_declaration_accounting_for_nothing_is_could_not_look(self):
        self.declare("# Nothing but the reasoning, and none of the figures.\n")
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("there was no declaration to inspect", result.stderr)

    def test_a_source_directory_that_is_not_there_is_could_not_look(self):
        result = self.check(source_dir=os.path.join(self.tree.root.name, "nowhere"))
        self.assertEqual(2, result.returncode)
        self.assertIn("no such directory", result.stderr)

    def test_no_origin_vocabulary_is_could_not_look(self):
        os.remove(os.path.join(self.tree.include, "plant_origin.h"))
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("the origin vocabulary could not be read", result.stderr)


# --- What the project ships --------------------------------------------------


class TheShippedDeclarationsAnswerTheQuestion(unittest.TestCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C1, .C10: what this project ships bounds every channel and gives every cadence figure one home, and both checks pass over it."""

    def setUp(self):
        self.project = os.path.dirname(TOOLS)

    def test_every_structure_this_project_ships_bounds_every_channel(self):
        result = run_check(
            "check_estimator_limits.py",
            "--include-dir",
            os.path.join(self.project, "include"),
            "--plant-root",
            os.path.join(self.project, "src", "plant"),
            "--params-dir",
            os.path.join(self.project, "params"),
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_every_cadence_figure_this_project_ships_accounts_for_itself(self):
        result = run_check(
            "check_cadence_declaration.py",
            "--include-dir",
            os.path.join(self.project, "include"),
            "--source-dir",
            os.path.join(self.project, "src"),
            "--declaration",
            os.path.join(self.project, "params", "cadence.declaration"),
        )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()


class EachGateThisSliceAddsIsShownToFailOnItsOwnDefect(unittest.TestCase):
    """SOL-USABLE-ESTIMATE-EVERY-STEP.C11: each build gate this slice adds carries a hand-written mutant, and every mutant's subject still exists in the file it edits."""

    #: The two checks this slice adds, by the script each mutation must run.
    GATES = ("check_estimator_limits.py", "check_cadence_declaration.py")

    def setUp(self):
        sys.path.insert(0, TOOLS)
        import mutate  # noqa: PLC0415 -- imported here so a broken tool fails this test

        self.mutations = mutate.MUTATIONS
        self.firmware = os.path.dirname(TOOLS)

    def mutations_running(self, script: str) -> list[dict]:
        return [entry for entry in self.mutations if any(script in part for part in entry["command"])]

    def test_each_gate_this_slice_adds_has_a_mutant_naming_it(self):
        for script in self.GATES:
            with self.subTest(gate=script):
                self.assertTrue(
                    self.mutations_running(script),
                    f"{script} is run by no mutation, so nothing establishes it can fail at "
                    "all -- which is the state a check that only reads as thorough is in",
                )

    def test_every_mutants_subject_still_exists_exactly_once(self):
        # The failure this guards against has happened: a mutation's subject was
        # edited out from under it, its find string matched nothing, and the run
        # aborted on it -- taking every mutation after it down too, so the whole
        # hand-curated set silently stopped establishing anything. An aborted run
        # reads as a broken tool rather than as lost coverage, which is why it
        # went unnoticed. Here it reads as a failing test instead.
        for entry in self.mutations:
            with self.subTest(mutation=entry["name"]):
                path = os.path.join(self.firmware, entry["file"])
                self.assertTrue(os.path.isfile(path), f"{entry['file']} is not there")
                with open(path, "r", encoding="utf-8") as handle:
                    body = handle.read()
                self.assertEqual(
                    1,
                    body.count(entry["find"]),
                    f"{entry['name']}: its subject appears "
                    f"{body.count(entry['find'])} times in {entry['file']}, so the mutation "
                    "is not the one it describes",
                )

    def test_a_mutants_replacement_actually_changes_the_file(self):
        for entry in self.mutations:
            with self.subTest(mutation=entry["name"]):
                self.assertNotEqual(
                    entry["find"],
                    entry["replace"],
                    f"{entry['name']}: introduces no defect, so the check it names would be "
                    "asked to notice nothing and would pass having established nothing",
                )
