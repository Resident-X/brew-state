#!/usr/bin/env python3
"""The gate that refuses a control figure nobody accounted for.

Every case here is driven against a synthetic tree written into a temporary
directory: an include directory carrying the origin vocabulary, a control
directory carrying definitions, and declarations written by the test. That is
deliberate, and it is the same reason the plant gates are exercised that way. A
check that could only be run against the real tree could only be shown to pass;
these are checks whose whole purpose is to fail when something has been
forgotten, and a check nobody has seen fail is a check nobody has established.

What is asserted is the failing direction as much as the passing one. A gate
that accepts a correct tree and also accepts a tree with an unaccounted gain in
it has established nothing, and would go on reporting success for as long as it
took somebody to notice.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

#: The vocabulary the gate loads its admissible origin kinds out of. Only the
#: parts the loader reads are reproduced, because a copy of the whole header
#: would be a second statement of what the vocabulary is, and it would stop
#: agreeing with the first the moment a kind was added.
ORIGIN_HEADER = """
#ifndef PLANT_ORIGIN_H
#define PLANT_ORIGIN_H
typedef enum {
    PLANT_ORIGIN_DOCUMENT = 0,
    PLANT_ORIGIN_ESTIMATED,
    PLANT_ORIGIN_MEASURED,
    PLANT_ORIGIN_KIND_COUNT
} plant_origin_kind_t;
#define PLANT_ORIGIN_DOCUMENT_WORD "document"
#define PLANT_ORIGIN_ESTIMATED_WORD "estimated"
#define PLANT_ORIGIN_MEASURED_WORD "measured"
#define PLANT_ORIGIN_KIND_WORDS                                                                    \\
    {                                                                                              \\
        PLANT_ORIGIN_DOCUMENT_WORD, PLANT_ORIGIN_ESTIMATED_WORD, PLANT_ORIGIN_MEASURED_WORD        \\
    }
#define PLANT_ORIGIN_MARKER '@'
#define PLANT_ORIGIN_NO_MACHINE_DECLARATION "describes-no-machine"
#endif
"""

#: A control source with one figure in it, accounted for below. The shape a
#: passing tree has, so that every failing case differs from it in exactly one
#: way and the case is about that one thing.
CONTROL_SOURCE = "#define CONTROL_PROPORTIONAL_PERMILLE_PER_K 30.0f\n"

ACCOUNTED = (
    "CONTROL_PROPORTIONAL_PERMILLE_PER_K @estimated Estimated from the reference description "
    "so the loop crosses over below the slowest lag it lives with.\n"
)

BAND = (
    "brew-temperature-band = 2000 milli-c @document Taken from the extraction literature's "
    "treatment of two degrees as the span across which a difference becomes tasteable.\n"
)

#: The second band the tolerance declaration is required to carry, on the same
#: footing BAND above is: present in every fixture that is meant to pass, and
#: substituted for or withdrawn by the cases below that are about it
#: specifically.
FLOW_BAND = (
    "flow-departure-band = 300 milli-ml-s @estimated Sized against the commanded rates the "
    "shipped delivery profiles use.\n"
)

#: The third band, on the same footing as the two above. It is stated in the
#: same unit as the first and bounded far more tightly, which is the case that
#: distinguishes a bound held per band from a bound shared by unit: a figure this
#: band must refuse is one the first band admits without complaint.
POST_DRAW_BAND = (
    "post-draw-match-band = 500 milli-c @estimated Taken as half the brew-temperature band, "
    "since two runs inside half of it are not different drinks.\n"
)

#: The two bands stating the drinking-temperature window, on the same footing
#: the three above are: present in every fixture meant to pass, and
#: substituted for or withdrawn by the cases below that are about them
#: specifically. Unlike the three above, each states an absolute edge rather
#: than a half-width, which is the shape the range-checking cases below are
#: written to exercise.
DRINKING_FLOOR_BAND = (
    "drinking-temperature-floor = 60000 milli-c @document Taken from the serving-temperature "
    "literature's treatment of the point below which a hot beverage reads as merely warm.\n"
)

DRINKING_CEILING_BAND = (
    "drinking-temperature-ceiling = 96000 milli-c @document Taken from the serving-temperature "
    "literature's treatment of the point above which a beverage handed to a person is a scald "
    "risk.\n"
)

#: A header belonging to one of the sources under inspection, carrying no figure
#: of its own. It sits in the shared include directory because a caller has to
#: see it, which is exactly the arrangement that lets a figure in a header go
#: unasked about while the same figure in the source beside it is accounted for.
LOADER_HEADER = "#ifndef DELIVERY_LOADER_H\n#define DELIVERY_LOADER_H\n#endif\n"

#: A header in the same directory belonging to somebody else -- a vocabulary the
#: whole tree reads, whose figures are answered for under the check that owns
#: them. Nothing about where it sits distinguishes it from the one above, which
#: is why the gate is told which headers to read rather than left to sweep the
#: directory up.
OTHER_HEADER = "#define PLANT_PARAMETER_LIMIT 64\n"


class ControlDeclarationGate(unittest.TestCase):
    """The tree the gate is run against, and how each case perturbs it."""

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.include = os.path.join(self.root.name, "include")
        self.control = os.path.join(self.root.name, "src", "control")
        self.delivery = os.path.join(self.root.name, "src", "delivery")
        os.makedirs(self.include)
        os.makedirs(self.control)
        os.makedirs(self.delivery)
        self.write(os.path.join(self.include, "plant_origin.h"), ORIGIN_HEADER)
        self.write(os.path.join(self.include, "plant_types.h"), OTHER_HEADER)
        self.header(LOADER_HEADER)
        self.source(CONTROL_SOURCE)
        self.declaration(ACCOUNTED)
        self.tolerance(BAND + FLOW_BAND + POST_DRAW_BAND + DRINKING_FLOOR_BAND + DRINKING_CEILING_BAND)

    @staticmethod
    def write(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def source(self, content: str, name: str = "control.c") -> str:
        path = os.path.join(self.control, name)
        self.write(path, content)
        return path

    def elsewhere(self, content: str, name: str = "main.c") -> str:
        """A source outside the control logic, as an entry point sits outside it."""
        directory = os.path.join(self.root.name, "src", "app")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        self.write(path, content)
        return path

    def header(self, content: str, name: str = "delivery_loader.h") -> str:
        """A header the sources under inspection rest on, in the shared include directory."""
        path = os.path.join(self.include, name)
        self.write(path, content)
        return path

    def declaration(self, content: str) -> str:
        path = os.path.join(self.root.name, "control.declaration")
        self.write(path, content)
        return path

    def tolerance(self, content: str) -> str:
        path = os.path.join(self.root.name, "tolerance.declaration")
        self.write(path, content)
        return path

    def run_gate(
        self, *, control_dir: str | None = None, tree_dir: str | None = None
    ) -> subprocess.CompletedProcess:
        """The gate, over the tree the fixture built.

        The two directories a case may substitute are the ones an invocation can
        get wrong: a source directory and a tree directory that are not there.
        Everything else is fixed, so a case differs from the passing shape in
        exactly one way and is about that one thing.
        """
        return subprocess.run(
            [
                sys.executable,
                os.path.join(TOOLS, "check_control_declaration.py"),
                "--include-dir",
                self.include,
                "--source-dir",
                control_dir if control_dir is not None else self.control,
                "--source-dir",
                self.delivery,
                "--source-header",
                os.path.join(self.include, "delivery_loader.h"),
                "--declaration",
                os.path.join(self.root.name, "control.declaration"),
                "--tolerance",
                os.path.join(self.root.name, "tolerance.declaration"),
                "--tree-dir",
                tree_dir if tree_dir is not None else os.path.join(self.root.name, "src"),
                "--tree-dir",
                self.include,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    # --- The shape that passes ---------------------------------------------

    def test_a_tree_whose_figures_all_account_for_themselves_passes(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a figure accounted for once, with one home, is accepted."""
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)

    # --- Every figure accounts for itself ----------------------------------

    def test_a_figure_added_beside_the_declaration_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a literal added beside the declaration fails rather than passing unnoticed."""
        self.source(CONTROL_SOURCE + "#define CONTROL_DERIVATIVE_PERMILLE_S_PER_K 4.0f\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("CONTROL_DERIVATIVE_PERMILLE_S_PER_K", result.stderr)
        self.assertIn("accounts for itself nowhere", result.stderr)

    def test_a_figure_in_a_second_control_file_is_reached(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: the gate covers the control logic rather than one file of it."""
        self.source("#define CONTROL_LEAK_PERMILLE 7\n", name="another.c")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("CONTROL_LEAK_PERMILLE", result.stderr)

    def test_a_definition_built_from_accounted_names_needs_no_account(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a definition introducing no number of its own is not a second figure."""
        self.source(
            CONTROL_SOURCE
            + "#define CONTROL_DOUBLE_GAIN (CONTROL_PROPORTIONAL_PERMILLE_PER_K + "
            "CONTROL_PROPORTIONAL_PERMILLE_PER_K)\n"
        )
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_figure_in_a_second_directory_is_reached(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: the gate reaches every directory whose figures the loop rests on, not only the loop's own."""
        with open(os.path.join(self.delivery, "loader.c"), "w", encoding="utf-8") as handle:
            handle.write("#define DELIVERY_BUFFER_MAX 64\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("DELIVERY_BUFFER_MAX", result.stderr)

    def test_a_figure_continued_onto_the_next_line_is_reached(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a definition wrapped over two lines is one figure, and the wrapping is not a way past the gate."""
        self.source(CONTROL_SOURCE + "#define CONTROL_SECRET_GAIN \\\n    42.5f\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("CONTROL_SECRET_GAIN", result.stderr)
        self.assertIn("accounts for itself nowhere", result.stderr)

    def test_a_comment_carrying_a_digit_is_not_a_figure(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a note beside a definition is prose, and the gate does not ask prose to account for itself."""
        self.source(
            CONTROL_SOURCE
            + "#define CONTROL_DOUBLE_GAIN (CONTROL_PROPORTIONAL_PERMILLE_PER_K + "
            "CONTROL_PROPORTIONAL_PERMILLE_PER_K) /* about 60 permille per kelvin */\n"
        )
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_figure_in_a_header_the_sources_rest_on_is_reached(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a bound declared in a header is the same figure it would be in the source beside it."""
        self.header(LOADER_HEADER + "#define DELIVERY_LOADER_NAME_MAX 48\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("DELIVERY_LOADER_NAME_MAX", result.stderr)
        self.assertIn("accounts for itself nowhere", result.stderr)

    def test_a_header_the_sources_do_not_rest_on_is_not_asked(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a figure of another loader is answered for under the check that owns it, not collected here."""
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("PLANT_PARAMETER_LIMIT", result.stderr)

    def test_a_named_header_that_is_not_there_stops(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: an invocation naming a file nothing reads must not go on reading as though it covered one."""
        os.remove(os.path.join(self.include, "delivery_loader.h"))
        result = self.run_gate()
        self.assertEqual(2, result.returncode)
        self.assertIn("no header to scan", result.stderr)

    def test_a_source_directory_that_is_not_there_stops(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a scan over a directory that does not exist finds nothing and would report every figure accounted for."""
        result = self.run_gate(control_dir=os.path.join(self.root.name, "src", "absent"))
        self.assertEqual(2, result.returncode)
        self.assertIn("no such directory", result.stderr)

    def test_a_tree_directory_that_is_not_there_stops(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band's second home cannot be looked for in a directory that is not there."""
        result = self.run_gate(tree_dir=os.path.join(self.root.name, "absent"))
        self.assertEqual(2, result.returncode)
        self.assertIn("no such directory", result.stderr)

    def test_a_word_is_not_a_figure(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a definition spelling a word for a declaration is not a number."""
        self.source(CONTROL_SOURCE + '#define CONTROL_SOME_WORD "brew-1"\n')
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_cadence_figures_are_left_to_their_own_check(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a figure accounted for elsewhere is not required to be accounted for twice."""
        self.source(CONTROL_SOURCE + "#define CONTROL_STEP_INTERVAL_MS 10u\n")
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_cadence_figure_accounted_for_here_as_well_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: two accounts of one figure are two answers that will disagree."""
        self.source(CONTROL_SOURCE + "#define CONTROL_STEP_INTERVAL_MS 10u\n")
        self.declaration(ACCOUNTED + "CONTROL_STEP_INTERVAL_MS @estimated Estimated as ten.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("cadence.declaration", result.stderr)

    # --- The coefficient the drinking-point yield rests on ------------------

    def test_the_yield_coefficient_is_refused_as_a_bare_number(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C7: the yield coefficient is refused as a bare number, on the same terms every other control figure is."""
        self.source(CONTROL_SOURCE + "#define CONTROL_YIELD_PERMILLE_PER_K_BELOW_FLOOR 250.0f\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("CONTROL_YIELD_PERMILLE_PER_K_BELOW_FLOOR", result.stderr)
        self.assertIn("accounts for itself nowhere", result.stderr)

    def test_the_yield_coefficient_passes_once_accounted_for(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C7: the same figure is accepted once its declaration line is added, with one home and a recorded origin."""
        self.source(CONTROL_SOURCE + "#define CONTROL_YIELD_PERMILLE_PER_K_BELOW_FLOOR 250.0f\n")
        self.declaration(
            ACCOUNTED
            + "CONTROL_YIELD_PERMILLE_PER_K_BELOW_FLOOR @estimated Estimated as the rate the "
            "commanded flow backs off per kelvin below the drinking floor.\n"
        )
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)

    # --- Every figure has one home -----------------------------------------

    def test_a_figure_accounted_for_and_defined_nowhere_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a declaration must not describe software that does not exist."""
        self.declaration(ACCOUNTED + "CONTROL_GHOST_GAIN @estimated Estimated from nothing.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("CONTROL_GHOST_GAIN", result.stderr)
        self.assertIn("defined nowhere", result.stderr)

    def test_a_figure_with_two_homes_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a figure spelled twice stops agreeing with itself."""
        second = self.source(CONTROL_SOURCE, name="second.c")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn(
            f"CONTROL_PROPORTIONAL_PERMILLE_PER_K is defined in "
            f"{os.path.join(self.control, 'control.c')}, {second}",
            result.stderr,
        )
        self.assertIn("stops agreeing with itself", result.stderr)

    # --- Every account is an account ---------------------------------------

    def test_a_figure_with_no_origin_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a number with nothing asserting it is the shape of one about to be treated as settled."""
        self.declaration("CONTROL_PROPORTIONAL_PERMILLE_PER_K\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("records no origin", result.stderr)

    def test_a_kind_outside_the_vocabulary_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a kind nobody declared is one the author declared alone."""
        self.declaration("CONTROL_PROPORTIONAL_PERMILLE_PER_K @guessed Arrived at by feel.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("guessed", result.stderr)

    def test_a_kind_with_no_account_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a figure that cannot be reproduced or challenged is not accounted for."""
        self.declaration("CONTROL_PROPORTIONAL_PERMILLE_PER_K @estimated\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("no account", result.stderr)

    def test_a_value_written_into_the_declaration_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: a second copy of a value is the site that goes stale silently."""
        self.declaration("CONTROL_PROPORTIONAL_PERMILLE_PER_K = 30 @estimated Estimated.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("carries a value", result.stderr)

    def test_one_figure_accounted_for_twice_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: two lines for one figure are two answers to one question."""
        self.declaration(ACCOUNTED + ACCOUNTED)
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("already accounted for", result.stderr)

    def test_a_declaration_line_naming_no_figure_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: an account with nothing in front of it accounts for nothing, and reads as a figure covered."""
        self.declaration(ACCOUNTED + "@estimated Estimated from the reference description.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("names no figure", result.stderr)

    def test_a_missing_declaration_stops_rather_than_reporting_success(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C7: reporting success over an absent declaration would say every figure was accounted for."""
        os.remove(os.path.join(self.root.name, "control.declaration"))
        result = self.run_gate()
        self.assertEqual(2, result.returncode)
        self.assertIn("no declaration", result.stderr)

    # --- The band lives in data --------------------------------------------

    def test_a_band_left_undeclared_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band left undeclared fails the gate rather than quietly defaulting."""
        self.tolerance("# nothing declared here\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("brew-temperature-band", result.stderr)
        self.assertIn("declared nowhere", result.stderr)

    def test_an_absent_tolerance_declaration_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: an absent artefact establishes nothing and must not read as one."""
        os.remove(os.path.join(self.root.name, "tolerance.declaration"))
        result = self.run_gate()
        self.assertEqual(2, result.returncode)
        self.assertIn("no tolerance declaration to inspect", result.stderr)

    def test_a_band_with_no_origin_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: the band carries a recorded origin the way the declarations beside it do."""
        self.tolerance("brew-temperature-band = 2000 milli-c\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("records no origin", result.stderr)

    def test_a_band_with_a_kind_and_no_account_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a recorded origin is a kind and what the figure was arrived at from."""
        self.tolerance("brew-temperature-band = 2000 milli-c @document\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("no account", result.stderr)

    def test_a_band_compiled_into_the_control_logic_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band with a second home in the source is the one the software would hold deliveries to."""
        self.source(CONTROL_SOURCE + "#define CONTROL_TEMPERATURE_BAND_MILLI_C 2000\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("compiled in cannot be varied", result.stderr)

    def test_a_band_compiled_in_outside_the_control_logic_is_reached(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band spelled in an entry point is as much a second home as one spelled in the loop."""
        self.elsewhere("#define APP_TEMPERATURE_BAND_MILLI_C 2000\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("compiled in cannot be varied", result.stderr)

    def test_a_band_that_is_not_a_number_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band the loader cannot read is not a band that has been declared."""
        self.tolerance("brew-temperature-band = wide milli-c @document Taken from a feeling.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("not a whole number of milli-c", result.stderr)

    def test_a_band_of_nothing_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band of zero is a criterion no delivery could meet, and the loader refuses it."""
        self.tolerance("brew-temperature-band = 0 milli-c @document Taken from nothing.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("declared as nothing at all", result.stderr)

    def test_a_negative_band_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band is a half-width, and no delivery sits less than no distance from what was asked for."""
        self.tolerance("brew-temperature-band = -100 milli-c @document Taken from nothing.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("declared as -100", result.stderr)

    def test_a_band_wider_than_its_own_bound_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band that accepts everything the machine can do is a declaration the machine will not start on."""
        self.tolerance(
            "brew-temperature-band = 2147483648 milli-c @document Taken from nothing.\n"
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("wider than the 20000 the loader admits", result.stderr)

    def test_a_band_declared_in_another_bands_unit_is_refused(self):
        """SOL-DELIVERY-PROFILE-DEPARTURE-REPORTED.C3: a figure in the wrong unit is a band measuring the wrong quantity, not a loose one."""
        self.tolerance(
            "brew-temperature-band = 1000 milli-ml-s @document Taken from nothing.\n"
            "flow-departure-band = 200 milli-c @estimated Taken from nothing either.\n"
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("is declared in 'milli-ml-s', but this build holds it in 'milli-c'",
                      result.stderr)
        self.assertIn("is declared in 'milli-c', but this build holds it in 'milli-ml-s'",
                      result.stderr)

    def test_a_band_carrying_no_unit_is_refused(self):
        """SOL-DELIVERY-PROFILE-DEPARTURE-REPORTED.C3: a number with no unit rests on the reader already knowing which quantity it measures."""
        self.tolerance("brew-temperature-band = 1000 @document Taken from nothing.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("not a whole number followed by the word for its unit", result.stderr)

    def test_a_tolerance_line_that_is_not_a_band_and_a_value_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a line the loader cannot read declares nothing, however much it looks like a band."""
        self.tolerance("brew-temperature-band 2000 @document No separator.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("is not a band and a value", result.stderr)

    def test_a_band_with_an_empty_value_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a band named with nothing after the equals sign holds a delivery to nothing at all."""
        self.tolerance("brew-temperature-band =  @document Taken from nothing.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("carries no value", result.stderr)

    def test_a_band_nothing_holds_a_delivery_to_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: a line nothing reads is not a band that has been declared."""
        self.tolerance(BAND + "steam-dryness-band-permille = 50 @estimated Estimated.\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("steam-dryness-band-permille", result.stderr)

    def test_a_band_declared_twice_is_refused(self):
        """SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: two bands for one delivery are two criteria, and which applies is whichever the eye landed on."""
        self.tolerance(BAND + BAND)
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("already declared", result.stderr)

    # --- A second band lives in data on the same terms the first does ------

    def test_the_second_band_left_undeclared_is_refused(self):
        """SOL-DELIVERY-DEPARTURE-REPORTED.C3: a second band is required exactly as the first is -- the gate is not satisfied by any one of the bands it holds a delivery to."""
        self.tolerance(BAND + POST_DRAW_BAND)
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("flow-departure-band", result.stderr)
        self.assertIn("declared nowhere", result.stderr)

    def test_the_second_band_compiled_into_the_control_logic_is_refused(self):
        """SOL-DELIVERY-DEPARTURE-REPORTED.C3: a second band with a second home in the source is the one the software would hold deliveries to, the same fault the first band's second home is."""
        self.source(CONTROL_SOURCE + "#define CONTROL_FLOW_DEPARTURE_BAND_MILLI_ML_S 300\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("compiled in cannot be varied", result.stderr)

    def test_the_second_band_with_no_origin_is_refused(self):
        """SOL-DELIVERY-DEPARTURE-REPORTED.C3: the second band carries a recorded origin on the same terms the first does."""
        self.tolerance(BAND + "flow-departure-band = 300 milli-ml-s\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("records no origin", result.stderr)

    def test_the_second_band_declared_twice_is_refused(self):
        """SOL-DELIVERY-DEPARTURE-REPORTED.C3: two declarations of the second band are two criteria, the same fault two declarations of the first band are."""
        self.tolerance(BAND + FLOW_BAND + FLOW_BAND + POST_DRAW_BAND)
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("already declared", result.stderr)

    # --- The band holding two deliveries against each other ----------------

    def test_the_post_draw_band_left_undeclared_is_refused(self):
        """SOL-BREW-RECOVERS-AFTER-DRAW.C1: a declaration omitting the post-draw band is refused rather than defaulting to zero or to the temperature band."""
        self.tolerance(BAND + FLOW_BAND)
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("post-draw-match-band", result.stderr)
        self.assertIn("declared nowhere", result.stderr)

    def test_the_post_draw_band_is_bounded_apart_from_the_temperature_band(self):
        """SOL-BREW-RECOVERS-AFTER-DRAW.C1: the post-draw band is range-checked against an admissible bound of its own rather than one shared with the temperature band."""
        shared = "20000 milli-c @document Taken from nothing."
        self.tolerance(
            f"brew-temperature-band = {shared}\n"
            + FLOW_BAND
            + f"post-draw-match-band = {shared}\n"
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        # The identical figure, admitted for one band and refused for the other.
        self.assertIn("wider than the 2000 the loader admits", result.stderr)
        self.assertNotIn("wider than the 20000 the loader admits", result.stderr)

    def test_the_post_draw_band_with_no_origin_is_refused(self):
        """SOL-BREW-RECOVERS-AFTER-DRAW.C1: the post-draw band carries a recorded origin on the same terms the bands beside it do."""
        self.tolerance(BAND + FLOW_BAND + "post-draw-match-band = 500 milli-c\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("records no origin", result.stderr)

    def test_the_post_draw_band_compiled_into_the_control_logic_is_refused(self):
        """SOL-BREW-RECOVERS-AFTER-DRAW.C1: a post-draw band with a second home in the source is the one the software would hold a pair of runs to."""
        self.source(CONTROL_SOURCE + "#define CONTROL_POST_DRAW_MATCH_BAND_MILLI_C 500\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("compiled in cannot be varied", result.stderr)

    def test_the_post_draw_band_in_another_unit_is_refused(self):
        """SOL-BREW-RECOVERS-AFTER-DRAW.C1: the post-draw band is held in thousandths of a degree, and a figure in another quantity is refused rather than read."""
        self.tolerance(
            BAND
            + FLOW_BAND
            + "post-draw-match-band = 500 milli-ml-s @estimated Taken from nothing.\n"
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn(
            "'post-draw-match-band' is declared in 'milli-ml-s', but this build holds it in "
            "'milli-c'",
            result.stderr,
        )

    # --- The window a delivery served at the drinking point is held inside -

    def test_the_drinking_floor_left_undeclared_is_refused(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: a declaration omitting the drinking floor is refused rather than defaulting to zero or to a band beside it."""
        self.tolerance(BAND + FLOW_BAND + POST_DRAW_BAND + DRINKING_CEILING_BAND)
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("drinking-temperature-floor", result.stderr)
        self.assertIn("declared nowhere", result.stderr)

    def test_the_drinking_ceiling_left_undeclared_is_refused(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: the ceiling is required exactly as the floor is -- the gate is not satisfied by either edge alone."""
        self.tolerance(BAND + FLOW_BAND + POST_DRAW_BAND + DRINKING_FLOOR_BAND)
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("drinking-temperature-ceiling", result.stderr)
        self.assertIn("declared nowhere", result.stderr)

    def test_the_drinking_edges_are_bounded_apart_from_the_half_width_bands(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: each edge is range-checked against an admissible bound of its own rather than one shared with the half-width bands beside it."""
        self.tolerance(
            BAND
            + FLOW_BAND
            + POST_DRAW_BAND
            + "drinking-temperature-floor = 20000 milli-c @document Taken from nothing.\n"
            + DRINKING_CEILING_BAND
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        # Admissible for the temperature band above, refused for the edge: the
        # two do not share a bound even though both are stated in milli-c.
        self.assertIn("below the 40000 this build admits", result.stderr)

    def test_a_drinking_edge_above_its_own_bound_is_refused(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: an edge past its own admissible range is refused as measuring the wrong quantity, not accepted as an unusually hot one."""
        self.tolerance(
            BAND
            + FLOW_BAND
            + POST_DRAW_BAND
            + DRINKING_FLOOR_BAND
            + "drinking-temperature-ceiling = 150000 milli-c @document Taken from nothing.\n"
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("above the 99000 this build admits", result.stderr)

    def test_the_drinking_floor_with_no_origin_is_refused(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: each edge carries its own recorded origin on the same terms every other band does."""
        self.tolerance(
            BAND + FLOW_BAND + POST_DRAW_BAND + "drinking-temperature-floor = 60000 milli-c\n" +
            DRINKING_CEILING_BAND
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("records no origin", result.stderr)

    def test_a_drinking_edge_compiled_into_the_control_logic_is_refused(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: an edge with a second home in the source is the one the software would hold deliveries to."""
        self.source(CONTROL_SOURCE + "#define CONTROL_DRINKING_TEMPERATURE_FLOOR_MILLI_C 60000\n")
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("compiled in cannot be varied", result.stderr)

    def test_a_drinking_edge_in_another_unit_is_refused(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: the floor is held in thousandths of a degree, and a figure in another quantity is refused rather than read."""
        self.tolerance(
            BAND
            + FLOW_BAND
            + POST_DRAW_BAND
            + "drinking-temperature-floor = 60000 milli-ml-s @document Taken from nothing.\n"
            + DRINKING_CEILING_BAND
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn(
            "'drinking-temperature-floor' is declared in 'milli-ml-s', but this build holds "
            "it in 'milli-c'",
            result.stderr,
        )

    def test_a_floor_at_or_above_its_own_ceiling_is_refused(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: a floor that is not below its own ceiling is a window admitting nothing, refused rather than accepted as an unusually narrow one."""
        self.tolerance(
            BAND
            + FLOW_BAND
            + POST_DRAW_BAND
            + "drinking-temperature-floor = 96000 milli-c @document Taken from nothing.\n"
            + DRINKING_CEILING_BAND
        )
        result = self.run_gate()
        self.assertEqual(1, result.returncode)
        self.assertIn("is not below", result.stderr)

    def test_a_floor_comfortably_below_its_ceiling_passes(self):
        """SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS.C1: two edges in the right order, each inside its own admissible range, are accepted."""
        result = self.run_gate()
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
