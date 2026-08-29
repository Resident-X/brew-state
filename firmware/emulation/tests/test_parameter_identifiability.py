"""What the identifiability analysis has to have shown before its finding counts
as evidence about which of this machine's coefficients an observation could ever
tell apart.

The perturbed re-runs happen once for the whole emulation tier, on the terms the
dominance suite beside this one is written on: the same cached sweep answers
both, because both read different signals out of the same corner-perturbed runs
and paying for a second set of them would buy two answers that must agree.
Everything asserted below reads what that run produced rather than reaching for
the loops itself.

A second set of them is paid for all the same, once, and it is a different set
rather than the same one again: the same perturbations with the control path
held at the description they were perturbed away from. That is a machine its
controller is wrong about rather than a machine built differently, and the two
readings are what the record this suite covers exists to put side by side. It is
cached on the same terms and for the same reason.

Three assertions cost real work of their own and each is deliberate. One re-runs
one coefficient's two corners through the brew draw and recomputes its signature
from scratch, because a signature the analysis computed and then read back off
itself would agree with itself over any arithmetic. One recomputes a remainder
the expensive way -- directly over every interval of every channel rather than
through the coordinates the analysis reduces them to -- because the affordable
route is the one thing here whose correctness is not obvious from reading it.
And one runs the whole method against a description the shipped one is not,
because a method that can only ever be pointed at one model cannot be shown
repeatable against a replacement.

The verdict logic itself is exercised against synthetic signatures rather than
against this machine's. The three verdicts have to be reachable and told apart,
and this model happens to produce only two of them -- a suite that asserted only
what this model does would leave the third implemented and never run, and would
pass over an implementation that could not produce it at all.

Nothing here asks whether the finding is right about a real machine. It cannot
be: the model it was taken against is estimated throughout, and the solution's
own criteria put a measured model out of scope until one exists.
"""

import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, "..", "tools"))
FIRMWARE_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
REPOSITORY_DIR = os.path.abspath(os.path.join(FIRMWARE_DIR, ".."))
sys.path.insert(0, TOOLS)

import run_closed_loop_check as closed_loop  # noqa: E402
import run_cross_tier_check as cross_tier  # noqa: E402
import run_parameter_identifiability as ident  # noqa: E402
import run_parameter_sweep as sweep  # noqa: E402
import seam_channels  # noqa: E402

FINDINGS = None
FINDING = None
DRIFTED_FINDINGS = None
DRIFTED_FINDING = None

BREW_DRAW_SOURCE = os.path.join(FIRMWARE_DIR, "src", "app", "native", "cross_tier_draw.c")
STEAM_DRAW_SOURCE = os.path.join(FIRMWARE_DIR, "src", "app", "native", "steam_draw.c")

# The coefficient whose signature is recomputed from its own corner runs. The
# one the dominance ranking puts at the head of its list, so the two corners are
# far apart and a signature computed from the wrong pair of runs, or from one
# corner rather than half the difference of two, cannot pass by being small.
RECOMPUTED_COEFFICIENT = "pump.flow_ml_per_s"

# The coefficient whose remainder is recomputed the expensive way. One the
# analysis presently finds identifiable by a wide margin and one it finds
# reproduced by the others, so the cross-check covers both a remainder that
# survives and one that very nearly vanishes -- which is the case the affordable
# route could plausibly get wrong.
CROSS_CHECKED_COEFFICIENTS = ("brew.thermal_mass_j_per_k", "water.heat_capacity_j_per_ml_k")

# A coefficient this suite writes differently to make a description that is a
# different machine and still a machine, borrowed from the dominance suite's own
# choice for the same purpose: the figure the reference machine's owner recalls
# the coffee element being, which the description records as displaced by a
# bench measurement rather than an invented value.
REPLACEMENT_COEFFICIENT = "brew.heater_power_w"
REPLACEMENT_VALUE = "1200.0"

# How far a regenerated figure may sit from the committed one before the
# committed record is out of date rather than merely rounded differently. The
# dominance suite's own reasoning applies unchanged: the analysis is
# deterministic on one host and need not be across hosts, because the plant
# model's arithmetic reaches the platform's own maths library.
FIGURE_TOLERANCE = 0.01


def setUpModule():
    global FINDINGS, FINDING, DRIFTED_FINDINGS, DRIFTED_FINDING
    FINDINGS = sweep.run_once()
    FINDING = ident.determine(FINDINGS)
    DRIFTED_FINDINGS = ident.drifted_sweep(FINDINGS)
    DRIFTED_FINDING = ident.determine(DRIFTED_FINDINGS)


def _committed_record():
    with open(ident.REPORT_PATH, encoding="utf-8") as handle:
        return handle.read()


def _produced_record():
    """The record this method presently produces, over both readings."""
    return ident.report_text(FINDINGS, FINDING, DRIFTED_FINDINGS, DRIFTED_FINDING)


def _sentence_with(text, marker):
    """The record's paragraph carrying one marker, or nothing if it carries
    none.

    A paragraph and not a window of characters: the record writes each one as a
    single line so that a renderer wraps it, which makes the line the unit a
    statement is made in. An assertion that a name is or is not in the same
    statement as a marker is asking about that line and not about the record.
    """
    for line in text.splitlines():
        if marker in line:
            return line
    return ""


def _coefficients_in(sentence):
    """The coefficients one sentence of the record names."""
    return re.findall(r"`([^`]+)`", sentence)


def _entry(coefficient, findings=None):
    for entry in (FINDINGS if findings is None else findings)["swept"]:
        if entry["coefficient"] == coefficient:
            return entry
    raise AssertionError("the sweep did not perturb %s" % coefficient)


def _record(coefficient, finding=None):
    for record in (FINDING if finding is None else finding)["determination"]:
        if record["coefficient"] == coefficient:
            return record
    raise AssertionError("the analysis reports nothing for %s" % coefficient)


def _flow_key_declared_by(path):
    """The name one draw's source declares it reports the drawn rate under.

    Read out of the source rather than imported, on the terms the dominance
    suite reads the quantity names by: these are C, and neither draw can be
    asked for its name by running it.
    """
    with open(path, encoding="utf-8") as handle:
        found = re.search(r'#define\s+FLOW_KEY\s+"([^"]+)"', handle.read())
    if not found:
        raise AssertionError("%s declares no FLOW_KEY to report the drawn rate under" % path)
    return found.group(1)


def _seam_source_with(entries, name="seam-written.c"):
    """A hardware-seam source of this suite's own making, carrying one sensor
    input table and nothing else.

    Written rather than borrowed, because what has to be established is that the
    reading follows the source it is given: a check taken only against the seam
    this project ships would agree with that seam whatever it did, including
    returning the same answer for every channel.
    """
    path = os.path.join(sweep.BUILD_DIR, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("/* a table this suite wrote */\n")
        handle.write("static const uint32_t %s[HW_SENSOR_CHANNEL_COUNT] = {\n"
                     % ident.SENSOR_INPUT_TABLE)
        handle.write(",\n".join("    %s" % entries[at] for at in sorted(entries)))
        handle.write("\n};\n")
    return path


def _synthetic(signatures, reaches_outlet=None, length=8):
    """A findings record of this suite's own making, carrying nothing but the
    signatures an assertion wants the verdict logic put to.

    Written here rather than taken from the machine because the verdicts have to
    be reachable and told apart whatever this particular model happens to
    produce. The channels are given a length and nothing else; every figure the
    analysis reads off a reference run is either the length of a series or a
    peak, and the peaks are set so that the arithmetic floor is far below the
    reading floor the caller passes in -- which lets an assertion state a
    signature directly in multiples of what could be resolved.
    """
    channels = dict((key, [0.0] * length) for key in sweep.OBSERVED_CHANNELS)
    reaches = dict((name, True) for name in signatures) if reaches_outlet is None \
        else reaches_outlet
    return {
        "peaks": dict((side, dict((key, 1.0) for key in sweep.OBSERVED_CHANNELS))
                      for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE)),
        "reference": dict((side, {"channels": channels})
                          for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE)),
        "swept": [{
            "coefficient": name,
            "reaches_outlet": reaches[name],
            "signature": dict(
                (side, dict((key, list(series.get((side, key), [0.0] * length)))
                            for key in sweep.OBSERVED_CHANNELS))
                for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE)),
        } for name, series in signatures.items()],
    }


class TheSweepRecordsEveryChannelTheMachineObserves(unittest.TestCase):
    """SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: The sweep records each
    in-scope parameter's effect on every hw_interface channel, not only the
    delivery-outcome deviation dominance ranked.
    """

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: the sweep additionally records
    # the perturbed run's deviation on each channel the machine observes -- each
    # of them, on both draws, for every coefficient it perturbed. A channel
    # silently absent for one coefficient would leave that coefficient compared
    # against the others over a shorter signature than they were compared over,
    # which is not a comparison at all.
    def test_every_coefficient_has_a_recorded_effect_on_every_channel_of_both_draws(self):
        self.assertTrue(FINDINGS["swept"], "the sweep perturbed nothing, so this asserts about "
                                           "an empty set")
        for entry in FINDINGS["swept"]:
            for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
                expected = len(FINDINGS["reference"][side]["trajectory"])
                with self.subTest(coefficient=entry["coefficient"], side=side):
                    self.assertIn(side, entry["signature"])
                    self.assertEqual(
                        sorted(entry["signature"][side]), sorted(sweep.OBSERVED_CHANNELS),
                        "the recorded effect covers a different set of channels from the one "
                        "everything downstream compares over")
                    for key in sweep.OBSERVED_CHANNELS:
                        self.assertEqual(
                            len(entry["signature"][side][key]), expected,
                            "%s's effect on %s covers %d of the draw's %d intervals"
                            % (entry["coefficient"], key,
                               len(entry["signature"][side][key]), expected))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: brew temperature, steam
    # temperature, brew pressure and steam pressure, already compared by the
    # cross-tier check, plus flow. The set is asserted against the two
    # vocabularies it is drawn from rather than against a list written here: the
    # four are the ones the cross-tier comparison already keys by, and the fifth
    # is the seam's own flow channel. A channel added to the seam and not to
    # this analysis fails here rather than being silently unexamined.
    def test_the_channels_are_the_four_already_compared_plus_the_flow_channel(self):
        self.assertEqual(
            sweep.OBSERVED_CHANNELS[:len(closed_loop.QUANTITY_KEYS)], closed_loop.QUANTITY_KEYS,
            "the four the two tiers compare are not the first four this analysis reads, so a "
            "quantity is being read into the wrong column")
        self.assertEqual(sweep.OBSERVED_CHANNELS[len(closed_loop.QUANTITY_KEYS):],
                         (cross_tier.FLOW_KEY,))

        declared = seam_channels.sensor_channels()
        flow = [name for name in declared.values() if ident.SEAM_FLOW_CHANNEL in name]
        self.assertEqual(
            len(flow), 1,
            "the seam enumerates %d flow channels, so which one the drawn rate stands for cannot "
            "be established" % len(flow))
        self.assertEqual(
            len(sweep.OBSERVED_CHANNELS), len(declared) - 1,
            "the analysis reads %d channels and the seam enumerates %d, so it is not reading "
            "every channel but the knob" % (len(sweep.OBSERVED_CHANNELS), len(declared)))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: the steam knob is out of scope
    # -- it reports an operator's valve position, not a plant-state measurement
    # any in-scope parameter could move. Asserted as an exclusion rather than
    # left to the count above, because a count would be satisfied by dropping
    # some other channel and admitting the knob.
    def test_the_steam_knob_is_not_one_of_the_channels(self):
        declared = seam_channels.sensor_channels()
        knob = [name for name in declared.values() if "KNOB" in name]
        self.assertEqual(len(knob), 1, "the seam enumerates no knob channel to exclude, so this "
                                       "assertion no longer covers anything")
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            for key in sweep.OBSERVED_CHANNELS:
                with self.subTest(side=side, channel=key):
                    self.assertNotIn("knob", key)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: flow, exposed by one small
    # additive print path alongside the existing delivered-temperature line
    # rather than through the four already-compared channels. Both draws are
    # required to declare it, under the same name, and that name is required to
    # be the one the parsers look the field up by -- the three are separate
    # declarations in three files and nothing but this keeps them together.
    def test_both_draws_print_the_drawn_rate_under_the_name_the_parsers_read_it_by(self):
        self.assertEqual(_flow_key_declared_by(BREW_DRAW_SOURCE), cross_tier.FLOW_KEY)
        self.assertEqual(_flow_key_declared_by(STEAM_DRAW_SOURCE), cross_tier.FLOW_KEY)
        self.assertNotIn(
            cross_tier.FLOW_KEY, closed_loop.QUANTITY_KEYS,
            "the drawn rate was folded into the quantities the two tiers compare themselves on, "
            "which puts a channel no converter carries into a comparison of what converters "
            "carried")

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: the perturbed run's deviation
    # on flow -- which is worth nothing if the channel reports a figure that
    # never moves. The rate is required to follow the course the draw commanded,
    # coefficient and level for level, so that a print path returning a constant
    # (or the steam side's rate, or nothing) fails here rather than quietly
    # contributing a column of zeros to every signature.
    def test_the_drawn_rate_reports_the_rate_the_course_commanded(self):
        brew = FINDINGS["reference"][sweep.BREW_SIDE]
        flow = brew["channels"][cross_tier.FLOW_KEY]
        nominal = _entry("pump.flow_ml_per_s")["nominal"]

        levels = set()
        for at, reported in enumerate(brew["trajectory"]):
            levels.add(reported["pump_permille"])
            self.assertAlmostEqual(
                flow[at], nominal * reported["pump_permille"] / 1000.0, places=5,
                msg="at interval %d the pump was commanded %d permille and the drawn rate was "
                    "reported as %g mL/s, which is not that fraction of the %g mL/s the "
                    "description declares at full duty"
                    % (at, reported["pump_permille"], flow[at], nominal))
        self.assertGreater(
            len(levels), 2,
            "the course commanded %d distinct pump levels, so a rate that ignored the level "
            "entirely could have passed the check above" % len(levels))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: on every channel the machine
    # observes -- including the ones a draw should leave alone. The steam draw
    # never commands the brew pump, so its drawn rate has to be nothing
    # throughout: a run reporting anything else would be reporting the steam
    # side's own draw under the brew path's name, which would put a coefficient
    # of the steam block into the brew path's column of every signature.
    def test_the_steam_draw_reports_the_brew_path_standing_still(self):
        steam = FINDINGS["reference"][sweep.STEAM_SIDE]["channels"][cross_tier.FLOW_KEY]
        self.assertEqual(len(steam), len(FINDINGS["courses"][sweep.STEAM_SIDE]))
        self.assertEqual(
            [value for value in steam if value != 0.0], [],
            "the steam draw reported the brew path drawing water, which it never commands")

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: reusing the sensitivity
    # sweep's existing corner-perturbation re-run -- the signature is half the
    # difference between the two corners of the same coefficient's declared
    # error. Recomputed here from its own corner descriptions rather than read
    # back off what the sweep recorded, because a signature checked against
    # itself agrees with itself over any arithmetic, including one corner taken
    # alone or the wrong pair of runs subtracted.
    def test_the_signature_is_half_the_difference_between_the_coefficients_two_corners(self):
        corners = {}
        for corner in ("low", "high"):
            written = os.path.join(FINDINGS["workspace"],
                                   "%s-%s.params" % (RECOMPUTED_COEFFICIENT, corner))
            self.assertTrue(os.path.exists(written), written)
            corners[corner] = sweep.brew_draw(
                FINDINGS["executable"], written, FINDINGS["limits"],
                FINDINGS["courses"][sweep.BREW_SIDE], FINDINGS["converter_scale"],
                "recomputed-%s" % corner)

        recorded = _entry(RECOMPUTED_COEFFICIENT)["signature"][sweep.BREW_SIDE]
        moved = 0
        for key in sweep.OBSERVED_CHANNELS:
            recomputed = [(high - low) / 2.0
                          for high, low in zip(corners["high"]["channels"][key],
                                               corners["low"]["channels"][key])]
            with self.subTest(channel=key):
                self.assertEqual(
                    recomputed, recorded[key],
                    "the recorded effect of %s on %s is not half the difference between the two "
                    "corners this sweep actually ran" % (RECOMPUTED_COEFFICIENT, key))
            moved += sum(1 for value in recomputed if value != 0.0)
        self.assertGreater(
            moved, 0,
            "%s moved no channel at all on either corner, so the comparison above held between "
            "two sets of zeros" % RECOMPUTED_COEFFICIENT)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: the drawn rate is read off the
    # line by name, so a draw that stopped printing it has to fail where it is
    # looked for rather than reading as a machine drawing nothing. Both parsers
    # are put a line without it, because the two draws print through separate
    # tables in separate translation units and either could lose the field on
    # its own.
    def test_a_line_that_stops_reporting_the_drawn_rate_is_refused_by_both_parsers(self):
        quantities = " ".join("%s=1" % key for key in closed_loop.QUANTITY_KEYS)
        converter = " ".join("%s=1" % key for key in cross_tier.CONVERTER_KEYS)
        with self.assertRaises(closed_loop.Unkeyed) as refused:
            cross_tier.parse_host(
                "HOST trajectory interval=0 result=0 pump=0 heater=0 steps=1 %s %s\n"
                % (quantities, converter))
        self.assertIn(cross_tier.FLOW_KEY, str(refused.exception))

        with self.assertRaises(closed_loop.Unkeyed) as steam_refused:
            sweep.parse_steam(
                "HOST steam-trajectory interval=0 result=0 drawing=0 demand=0 heater=0 feed=0 "
                "steps=1 %s\n" % quantities)
        self.assertIn(cross_tier.FLOW_KEY, str(steam_refused.exception))

        # And the same line carrying the field is read, so that the refusals
        # above are about the missing field rather than about a line neither
        # parser was ever going to accept.
        accepted = cross_tier.parse_host(
            "HOST trajectory interval=0 result=0 pump=0 heater=0 steps=1 %s %s %s=2.5\n"
            % (quantities, converter, cross_tier.FLOW_KEY))
        self.assertEqual(accepted["trajectory"][0]["brew_flow_ml_per_s"], 2.5)

    # SOL-CROSS-TIER-CONVERTER-MARGIN-RECURS.C1: a line that stops reporting
    # what the converter itself reconstructed for a sensed quantity has to
    # fail where it is looked for -- the finest converter subcase now compares
    # exactly that figure, so a line silently missing it would read as no
    # divergence rather than as a draw that stopped printing what the
    # comparison needs.
    def test_a_line_that_stops_reporting_a_converter_reading_is_refused(self):
        quantities = " ".join("%s=1" % key for key in closed_loop.QUANTITY_KEYS)
        for missing in cross_tier.CONVERTER_KEYS:
            present = " ".join(
                "%s=1" % key for key in cross_tier.CONVERTER_KEYS if key != missing)
            with self.subTest(missing=missing):
                with self.assertRaises(closed_loop.Unkeyed) as refused:
                    cross_tier.parse_host(
                        "HOST trajectory interval=0 result=0 pump=0 heater=0 steps=1 %s %s "
                        "%s=2.5\n" % (quantities, present, cross_tier.FLOW_KEY))
                self.assertIn(missing, str(refused.exception))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: for every parameter the
    # estimator's reconstructed outlet-temperature state depends on. Which those
    # are is established from the runs -- a coefficient is in scope exactly when
    # its perturbation moved the temperature the coffee side delivers, which is
    # the state the seam reconstructs -- and the set is required to be neither
    # everything nor nothing, since either would mean the test the scope rests
    # on is not discriminating.
    def test_the_scope_is_the_coefficients_the_reconstruction_actually_rests_on(self):
        scoped = set(FINDING["scoped"])
        every = set(entry["coefficient"] for entry in FINDINGS["swept"])
        self.assertTrue(scoped, "no coefficient was found to reach the reconstructed state")
        self.assertNotEqual(
            scoped, every,
            "every coefficient the sweep perturbed was found to reach the reconstruction, "
            "including the steam block's own -- so the test that decides scope is not "
            "discriminating and the comparison is being made over the wrong set")
        for entry in FINDINGS["swept"]:
            with self.subTest(coefficient=entry["coefficient"]):
                self.assertEqual(
                    entry["coefficient"] in scoped, entry["reaches_outlet"],
                    "the scope and the runs disagree about whether %s reaches the reconstructed "
                    "state" % entry["coefficient"])

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: flow, which has no hardware
    # converter behind it. Which channels this board carries an input for is
    # read out of the seam's own implementation, and the record's whole
    # statement about what an instrument would buy turns on that reading -- a
    # reader that returned "fitted" for everything would have the record
    # reporting that no channel is missing, and a reader that returned
    # "unfitted" for everything would have it arguing for four instruments the
    # machine already has.
    #
    # Both directions are put to it against tables this test writes, so that the
    # reading follows the seam rather than agreeing with whatever the seam
    # presently says.
    def test_which_channels_carry_an_input_is_read_from_the_seam_rather_than_assumed(self):
        as_built = ident._channel_is_fitted()
        self.assertEqual(
            as_built[cross_tier.FLOW_KEY], False,
            "the seam is read as carrying a converter input behind the flow channel, so the "
            "record's account of what an instrument on it would buy is about a machine that "
            "already has one")
        for key in closed_loop.QUANTITY_KEYS:
            with self.subTest(channel=key):
                self.assertTrue(
                    as_built[key],
                    "%s is read as having no converter input behind it, though it is one of the "
                    "four the two tiers compare through converters" % key)

        wired = _seam_source_with(dict((at, "ADC_CHANNEL_%d" % at)
                                       for at in range(len(seam_channels.sensor_channels()))))
        self.assertEqual(
            [key for key, fitted in ident._channel_is_fitted(wired).items() if not fitted], [],
            "a seam wiring every channel to a converter input was still read as leaving one "
            "unfitted, so the reading is not following the source it is given")

        bare = _seam_source_with(dict((at, ident.NO_SENSOR_INPUT)
                                      for at in range(len(seam_channels.sensor_channels()))))
        self.assertEqual(
            [key for key, fitted in ident._channel_is_fitted(bare).items() if fitted], [],
            "a seam wiring nothing at all was still read as carrying an input somewhere")

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: read out of the seam, which
    # means a seam that cannot be read has to stop the analysis rather than
    # leave it reporting a guess. All three ways the table can fail to say what
    # it must are put to it -- renamed, no initialiser, and a mapping that does
    # not cover the channels the seam enumerates -- because each would otherwise
    # produce a plausible-looking record about the wrong machine.
    def test_a_seam_whose_input_table_cannot_be_read_stops_the_analysis(self):
        renamed = os.path.join(sweep.BUILD_DIR, "seam-renamed.c")
        with open(renamed, "w", encoding="utf-8") as handle:
            handle.write("static const uint32_t elsewhere[2] = {ADC_CHANNEL_0, ADC_CHANNEL_1};\n")
        with self.assertRaises(ident.IdentifiabilityError) as refused:
            ident._fitted_channels(renamed)
        self.assertIn(ident.SENSOR_INPUT_TABLE, str(refused.exception))

        headless = os.path.join(sweep.BUILD_DIR, "seam-headless.c")
        with open(headless, "w", encoding="utf-8") as handle:
            handle.write("extern const uint32_t %s[];\n" % ident.SENSOR_INPUT_TABLE)
        with self.assertRaises(ident.IdentifiabilityError) as no_body:
            ident._fitted_channels(headless)
        self.assertIn("initialiser", str(no_body.exception))

        short = _seam_source_with({0: "ADC_CHANNEL_0", 1: ident.NO_SENSOR_INPUT},
                                  name="seam-short.c")
        with self.assertRaises(ident.IdentifiabilityError) as mismatched:
            ident._fitted_channels(short)
        self.assertIn("cannot be established", str(mismatched.exception))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C1: not only the delivery-outcome
    # deviation dominance ranked. The two readings of the same runs have to be
    # different readings: a coefficient the dominance ranking cannot weigh at
    # all still has a recorded effect on the channels here, and that is the case
    # that proves the channel record is not the delivery record renamed.
    def test_a_coefficient_the_ranking_could_not_weigh_still_has_a_channel_record(self):
        unweighable = [name for name, _, _ in FINDINGS["unweighed"]]
        self.assertTrue(
            unweighable,
            "this model leaves the dominance ranking able to weigh everything, so the case that "
            "separates the two readings does not arise in this run")
        for name in unweighable:
            with self.subTest(coefficient=name):
                record = _record(name)
                self.assertGreater(
                    max(record["reached"].values()), 0.0,
                    "%s has no dominance figure and no recorded effect on any channel either, so "
                    "the channel record adds nothing the delivery record did not already say"
                    % name)


class AParameterNotToldApartIsNamedRatherThanAssumed(unittest.TestCase):
    """SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: A parameter whose channel
    signature is indistinguishable from another's, or from the sweep's own
    resolution, is named as not shown identifiable.
    """

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: a parameter is identifiable
    # only when no combination of the others reproduces its signature. Put to
    # the verdict logic as four synthetic signatures, three of which stand in an
    # exact dependency -- which is the case the whole criterion exists for and
    # which this model does not produce in its exact form.
    #
    # All three of the dependent set have to come back named, not only the one
    # written as the combination. Each of the three is a combination of the
    # other two, so no observation could say which of them was wrong, and an
    # implementation that named only the one it happened to be handed last would
    # report the other two as distinguishable when nothing distinguishes them.
    # The fourth signature is independent of all of them and has to come back
    # identifiable in the same run, or an implementation that named everything
    # unidentifiable would pass this.
    def test_a_signature_that_is_a_combination_of_the_others_is_named_not_shown_identifiable(self):
        where = (sweep.BREW_SIDE, "brew-c")
        first = [10.0, 0.0, 0.0, 30.0, 0.0, 0.0, 5.0, 0.0]
        second = [0.0, 40.0, 0.0, 0.0, 20.0, 0.0, 0.0, 7.0]
        combination = [2.0 * a - 0.5 * b for a, b in zip(first, second)]
        apart = [0.0, 0.0, 60.0, 0.0, 0.0, -25.0, 0.0, 0.0]

        finding = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "combination": {where: combination},
            "apart": {where: apart},
        }), reading=1.0)
        verdicts = dict((record["coefficient"], record["verdict"])
                        for record in finding["determination"])
        for name in ("first", "second", "combination"):
            with self.subTest(coefficient=name):
                self.assertEqual(verdicts[name], ident.REPRODUCED_BY_THE_OTHERS)
        self.assertEqual(verdicts["apart"], ident.IDENTIFIABLE)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: two parameters whose
    # signatures are the same one are each reproduced by the other, and neither
    # may be reported as distinguishable on the strength of the other having
    # been named first. Order is what an implementation working down a list and
    # subtracting as it goes would get wrong, and it would get it wrong in the
    # direction that reports the first of a pair as identifiable.
    def test_neither_of_two_identical_signatures_is_reported_as_distinguishable(self):
        where = (sweep.STEAM_SIDE, "steam-bar")
        same = [12.0, 0.0, -9.0, 4.0, 0.0, 0.0, 0.0, 3.0]
        finding = ident.determine(_synthetic({
            "one": {where: same},
            "other": {where: list(same)},
        }), reading=1.0)
        for record in finding["determination"]:
            with self.subTest(coefficient=record["coefficient"]):
                self.assertEqual(record["verdict"], ident.REPRODUCED_BY_THE_OTHERS)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: or whose effect on every
    # observed channel sits at the sweep's own resolution floor. A signature
    # that reaches every channel by less than what a reading could carry is
    # named for that reason and not for the other -- the two are different
    # findings about the machine, and only one of them can be answered by
    # separating the coefficient from something.
    def test_a_signature_below_what_a_reading_could_carry_is_named_for_that_reason(self):
        where = (sweep.BREW_SIDE, "brew-c")
        finding = ident.determine(_synthetic({
            "unreachable": {where: [0.9, -0.5, 0.0, 0.25, 0.0, 0.0, 0.0, 0.0]},
            "reachable": {where: [0.0, 0.0, 90.0, 0.0, 0.0, -40.0, 0.0, 0.0]},
        }), reading=1.0)
        verdicts = dict((record["coefficient"], record["verdict"])
                        for record in finding["determination"])
        self.assertEqual(verdicts["unreachable"], ident.BELOW_WHAT_A_READING_CARRIES)
        self.assertEqual(verdicts["reachable"], ident.IDENTIFIABLE)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: named as not shown
    # identifiable rather than omitted or assumed identifiable -- and the two
    # ways of failing named apart, because one asks for a channel that does not
    # exist and the other for a channel that separates two coefficients, which
    # may already be fitted. A run that collapsed them into one phrase would
    # leave a reader unable to tell which.
    def test_the_two_ways_of_failing_are_named_apart_and_both_say_not_shown(self):
        self.assertNotEqual(ident.BELOW_WHAT_A_READING_CARRIES, ident.REPRODUCED_BY_THE_OTHERS)
        for verdict in (ident.BELOW_WHAT_A_READING_CARRIES, ident.REPRODUCED_BY_THE_OTHERS):
            with self.subTest(verdict=verdict):
                self.assertTrue(verdict.startswith("not shown identifiable"))
        self.assertNotIn("not shown", ident.IDENTIFIABLE)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: every in-scope parameter's
    # signature is compared -- every one of them comes back with a verdict, and
    # every one of them is named in the committed record. A parameter dropped
    # from the finding reads exactly like one that was never in scope, which is
    # the omission the criterion refuses.
    def test_every_in_scope_coefficient_leaves_the_analysis_with_a_verdict(self):
        verdicts = dict((record["coefficient"], record["verdict"])
                        for record in FINDING["determination"] if record["in_scope"])
        self.assertEqual(sorted(verdicts), sorted(FINDING["scoped"]))
        for name, verdict in verdicts.items():
            with self.subTest(coefficient=name):
                self.assertIn(verdict, (ident.IDENTIFIABLE, ident.BELOW_WHAT_A_READING_CARRIES,
                                        ident.REPRODUCED_BY_THE_OTHERS))

        written = dict((row["coefficient"], row["verdict"])
                       for row in ident.determination_rows(_committed_record()))
        self.assertEqual(
            written, verdicts,
            "the committed record's verdicts are not the ones this analysis now produces. Re-run "
            "firmware/emulation/tools/run_parameter_identifiability.py")

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: against the sweep's own
    # resolution -- which is read off the machine's own declarations rather than
    # written into the analysis. Two things are asserted: that the arithmetic
    # floor is one unit in the last place of a single-precision figure at the
    # magnitude the channel reached, and that the floor actually decides
    # something, by making it coarse enough to put a coefficient this run finds
    # identifiable below it. A floor compiled in as a constant would pass
    # nothing here.
    def test_the_resolution_floor_is_derived_rather_than_written_into_the_analysis(self):
        for peak in (1.0, 104.389, 0.0293, 1.5e-7):
            with self.subTest(peak=peak):
                self.assertEqual(
                    ident.arithmetic_resolution(peak),
                    2.0 ** (math.frexp(peak)[1] - ident.SINGLE_PRECISION_SIGNIFICAND_BITS))
                self.assertNotEqual(
                    ident.arithmetic_resolution(peak), ident.arithmetic_resolution(peak * 4.0),
                    "the arithmetic floor did not move with the magnitude it is a last place of")

        counts, milli = cross_tier.converter_scale()
        self.assertAlmostEqual(ident.reading_resolution(), float(milli) / float(counts) / 1000.0,
                               places=12)

        identifiable = [record["coefficient"] for record in FINDING["determination"]
                        if record["verdict"] == ident.IDENTIFIABLE]
        self.assertTrue(identifiable, "this run found nothing identifiable, so coarsening the "
                                      "floor cannot be shown to change anything")
        widest = max(_record(name)["largest"] for name in identifiable)
        coarsened = ident.determine(FINDINGS, reading=ident.reading_resolution() * widest * 2.0)
        self.assertEqual(
            [record["verdict"] for record in coarsened["determination"] if record["in_scope"]],
            [ident.BELOW_WHAT_A_READING_CARRIES] * len(coarsened["scoped"]),
            "coarsening what a reading could carry past every coefficient's largest reach left "
            "some of them still identifiable, so the verdict is not being taken against that "
            "figure at all")

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: no combination of the others
    # reproduces its signature -- the part that none of them reproduces is
    # computed through the coordinates the analysis reduces the signatures to,
    # which is the one step here whose correctness is not evident from reading
    # it. Recomputed the expensive way, directly over every interval of every
    # channel, and required to agree. A projection that quietly lost part of the
    # span would report a remainder that is not there and call an
    # indistinguishable coefficient identifiable.
    def test_the_affordable_remainder_is_the_one_the_direct_computation_gives(self):
        layout = ident.component_layout(FINDINGS)
        floor = ident.floors(FINDINGS)
        laid = dict((entry["coefficient"], ident.scaled_signature(entry, layout, floor))
                    for entry in FINDINGS["swept"])

        for name in CROSS_CHECKED_COEFFICIENTS:
            with self.subTest(coefficient=name):
                remainder = list(laid[name])
                for direction in ident.orthonormal_basis(
                        [laid[other] for other in FINDING["scoped"] if other != name]):
                    overlap = ident._dot(direction, remainder)
                    remainder = [value - overlap * along
                                 for value, along in zip(remainder, direction)]
                directly = max(abs(value) for value in remainder)
                affordably = _record(name)["against_scoped"]["unique"]
                self.assertAlmostEqual(
                    directly, affordably, delta=1e-6 * max(directly, 1.0),
                    msg="%s's unreproduced part is %g computed directly and %g computed through "
                        "the coordinates, so the affordable route is not the same computation"
                        % (name, directly, affordably))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: the comparison is against the
    # other in-scope parameters, and the analysis reports beside it what every
    # coefficient the sweep touched would do. Both figures have to be there for
    # every in-scope coefficient, and the wider comparison can never leave more
    # of a signature unreproduced than the narrower one: a projection onto a
    # larger span cannot leave a larger remainder.
    #
    # Asserted on the remainder's size and not on its largest single figure,
    # and the difference is the reason both are recorded. The size can only
    # fall as the span grows. The largest single figure can move either way,
    # because a fit that shrinks the whole remainder is free to shift where its
    # widest disagreement lands -- so an assertion made on that figure would be
    # asserting something untrue of the arithmetic and would fail on a model
    # that had done nothing wrong.
    def test_the_wider_comparison_is_reported_and_can_never_leave_more_unreproduced(self):
        for record in FINDING["determination"]:
            if not record["in_scope"]:
                continue
            with self.subTest(coefficient=record["coefficient"]):
                for what in ("against_scoped", "against_every"):
                    self.assertIn("unique", record[what])
                    self.assertIn("fraction", record[what])
                self.assertLessEqual(
                    record["against_every"]["fraction"],
                    record["against_scoped"]["fraction"] * (1.0 + 1e-9) + 1e-12,
                    "%s has more of its signature left unreproduced by every coefficient than by "
                    "the in-scope ones alone, which cannot be true of a larger span"
                    % record["coefficient"])

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: no combination of the others
    # reproduces its signature -- and whether that finding is about a machine or
    # about arithmetic depends on how large the combination has to be. Every
    # signature is scaled to one declared error of its own coefficient, so a
    # combination totalling less than one sits inside the errors the description
    # already admits.
    #
    # Two things are required of it. The size has to be reported for every
    # in-scope coefficient, so that a future model's "reproduced by the others"
    # verdict cannot rest silently on the others being wrong by a hundred times
    # their declared errors. And the arithmetic has to be right, which is
    # checked against a synthetic case whose weights are known by construction.
    def test_the_size_of_the_reproducing_combination_is_computed_and_reported(self):
        where = (sweep.BREW_SIDE, "brew-c")
        first = [10.0, 0.0, 0.0, 30.0, 0.0, 0.0, 5.0, 0.0]
        second = [0.0, 40.0, 0.0, 0.0, 20.0, 0.0, 0.0, 7.0]
        finding = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "combination": {where: [2.0 * a - 0.5 * b for a, b in zip(first, second)]},
        }), reading=1.0)
        used = dict((record["coefficient"], record["against_scoped"]["used"])
                    for record in finding["determination"])
        self.assertAlmostEqual(
            used["combination"], 2.5, places=6,
            msg="a signature written as twice the first minus half the second was reported as "
                "needing %g of the others rather than the 2.5 it is made of" % used["combination"])

        for record in FINDING["determination"]:
            if not record["in_scope"]:
                continue
            with self.subTest(coefficient=record["coefficient"]):
                self.assertIn("used", record["against_scoped"])
                self.assertGreaterEqual(record["against_scoped"]["used"], 0.0)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: compared against every other
    # in-scope parameter's signature -- which is only worth anything if the
    # comparison survives a signature that very nearly lies inside what the
    # others span. That is the case the criterion exists to catch and the case
    # an orthogonalisation loses accuracy on, and losing it does not produce an
    # obviously wrong answer: it produces a remainder made of rounding, read as
    # a coefficient being distinguishable when the arithmetic simply could not
    # tell that it is not.
    #
    # A signature is written as a combination of three others plus a hundred
    # thousand millionths of a fourth direction, against components of order a
    # million. What is required is that the remainder come back as that
    # deliberate hair -- not as nothing, which would mean the hair was lost, and
    # not as something far larger, which would mean the projection through three
    # near-parallel directions had left rounding behind. This model produces
    # nothing that near, so without a case written here the arithmetic's one
    # delicate step would never be exercised at all.
    def test_a_signature_almost_inside_the_others_leaves_the_hair_and_not_rounding(self):
        where = (sweep.BREW_SIDE, "brew-c")
        first = [1.0e6, -4.0e5, 7.0e5, 2.0e5, -9.0e5, 3.0e5, 6.0e5, -1.0e5]
        second = [3.0e5, 8.0e5, -2.0e5, 5.0e5, 1.0e5, -7.0e5, 2.0e5, 4.0e5]
        third = [-6.0e5, 2.0e5, 5.0e5, -3.0e5, 4.0e5, 9.0e5, -1.0e5, 7.0e5]
        fourth = [2.0e5, 5.0e5, 3.0e5, -8.0e5, -2.0e5, 1.0e5, 9.0e5, -4.0e5]
        hair = 1.0e-10
        almost = [0.5 * a - 0.25 * b + 0.125 * c + hair * d
                  for a, b, c, d in zip(first, second, third, fourth)]

        # The direction the hair points along is deliberately not one of the
        # signatures the comparison is made against -- it belongs to a
        # coefficient no reconstruction rests on. Were it in the compared set,
        # the signature would lie exactly inside what that set spans and the
        # hair would be reproduced along with everything else, which would make
        # this a test of nothing.
        finding = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "third": {where: third},
            "fourth": {where: fourth},
            "almost": {where: almost},
        }, reaches_outlet={"first": True, "second": True, "third": True,
                           "fourth": False, "almost": True}), reading=1.0)
        left = dict((record["coefficient"], record["against_scoped"]["fraction"])
                    for record in finding["determination"] if record["in_scope"])["almost"]

        self.assertGreater(
            left, hair * 1.0e-2,
            "the deliberate hair was lost entirely, so a signature differing from a combination "
            "of the others by a real amount would be reported as reproduced by them exactly")
        self.assertLess(
            left, hair * 1.0e2,
            "what was left after removing the three directions the signature was built from is "
            "%g of its own size, far more than the hair of %g actually put there -- so the "
            "remainder is the arithmetic's rounding rather than the difference" % (left, hair))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C2: a parameter is named rather
    # than assumed -- so a run in which nothing reaches the reconstructed state
    # has to be refused rather than reported as a finding about nothing. An
    # analysis that returned an empty determination would read, from the record
    # it wrote, exactly like one that found everything identifiable.
    def test_a_run_reaching_no_reconstructed_state_is_refused_rather_than_reported(self):
        where = (sweep.BREW_SIDE, "brew-c")
        with self.assertRaises(ident.IdentifiabilityError) as refused:
            ident.determine(
                _synthetic({"only": {where: [50.0] * 8}}, reaches_outlet={"only": False}),
                reading=1.0)
        self.assertIn("reconstructs", str(refused.exception))


class TheFindingIsCommittedWithItsDataAndItsModel(unittest.TestCase):
    """SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C3: The identifiability finding is
    committed with the per-channel data it was derived from, pointed at the model
    it was run against.
    """

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C3: the per-parameter, per-channel
    # signatures and the determination they produced are committed together. The
    # committed record has to be the one this method presently produces, and
    # both halves are asked for by name: a record carrying the verdicts and not
    # the figures they were drawn from is a finding nobody can check.
    def test_the_committed_record_is_the_one_this_method_presently_produces(self):
        committed = _committed_record()
        produced = _produced_record()

        was = ident.determination_rows(committed)
        now = ident.determination_rows(produced)
        self.assertTrue(was, "%s carries no determination table" % ident.REPORT_PATH)
        self.assertEqual(
            [row["coefficient"] for row in was], [row["coefficient"] for row in now],
            "the committed record covers a different set of coefficients, or covers them in a "
            "different order, from the one this analysis now produces. Re-run "
            "firmware/emulation/tools/run_parameter_identifiability.py")

        # Every figure, not only the verdict. A check that compared verdicts
        # alone would let each figure in the table drift as far as it liked
        # until one of them happened to cross the threshold -- and the figures
        # are half of what the record exists to carry, since a verdict with
        # nothing behind it cannot be argued with. The dominance record beside
        # this one went stale in exactly this way once already.
        for before, after in zip(was, now):
            with self.subTest(coefficient=before["coefficient"]):
                self.assertEqual(before["verdict"], after["verdict"])
                self.assertEqual(before["loudest"], after["loudest"])
                for figure in ("largest", "unique_scoped", "unique_every", "fraction", "used"):
                    self.assertLessEqual(
                        abs(before[figure] - after[figure]),
                        FIGURE_TOLERANCE * max(abs(after[figure]), 1e-12) + 1e-12,
                        "the committed record gives %s a %s of %g and this analysis now gives it "
                        "%g. Re-run firmware/emulation/tools/run_parameter_identifiability.py"
                        % (before["coefficient"], figure, before[figure], after[figure]))

        self.assertEqual(
            ident.scope_rows(committed), ident.scope_rows(produced),
            "the committed record is about a different set of coefficients from the one this "
            "analysis now covers. Re-run "
            "firmware/emulation/tools/run_parameter_identifiability.py")

        for heading in (ident.MODEL_HEADING, ident.FLOOR_HEADING, ident.SCOPE_HEADING,
                        ident.SIGNATURE_HEADING, ident.DETERMINATION_HEADING):
            with self.subTest(heading=heading):
                self.assertIn(heading, committed)
        self.assertIn("run_parameter_identifiability.py", committed)
        self.assertIn("Do not edit by hand", committed)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C3: with the per-channel data it
    # was derived from -- the data, meaning the figures and not merely a table
    # of the right shape. Every per-channel figure the committed record carries
    # is compared against what the analysis now produces, on both draws. Without
    # this the whole signature record could drift while the verdicts stood, and
    # a reader checking the finding would be checking it against numbers that
    # describe an earlier model.
    def test_the_committed_per_channel_figures_are_the_ones_this_method_now_produces(self):
        committed = _committed_record()
        produced = _produced_record()
        for reading in (ident.BUILT_DIFFERENTLY, ident.DRIFTED):
            for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
                was = ident.signature_rows(committed, side, reading)
                now = ident.signature_rows(produced, side, reading)
                self.assertTrue(
                    was, "the committed record carries no %s draw table for the machine %s"
                         % (side, reading))
                self.assertEqual(sorted(was), sorted(now))
                for coefficient, figures in was.items():
                    with self.subTest(reading=reading, side=side, coefficient=coefficient):
                        self.assertEqual(len(figures), len(sweep.OBSERVED_CHANNELS))
                        for at, before in enumerate(figures):
                            after = now[coefficient][at]
                            self.assertLessEqual(
                                abs(before - after),
                                FIGURE_TOLERANCE * max(abs(after), 1e-12) + 1e-12,
                                "the committed record has %s moving the %s draw's %s by %g on a "
                                "machine %s and this analysis now has it moving it by %g. Re-run "
                                "firmware/emulation/tools/run_parameter_identifiability.py"
                                % (coefficient, side, sweep.OBSERVED_CHANNELS[at], before,
                                   reading, after))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C3: with the per-channel data it
    # was derived from. Every coefficient the analysis covers has to appear in
    # the per-channel tables with a figure for every channel of both draws, so
    # that the verdict beside it can be argued with rather than only read.
    def test_the_committed_record_carries_a_figure_for_every_coefficient_and_channel(self):
        committed = _committed_record()
        for reading, of in ((ident.BUILT_DIFFERENTLY, FINDING), (ident.DRIFTED, DRIFTED_FINDING)):
            for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
                heading = ident.signature_heading(side, reading)
                self.assertIn(heading, committed)
                block = committed.split(heading, 1)[1].split("\n#", 1)[0]
                header = [line for line in block.splitlines() if line.startswith("| Coefficient")]
                self.assertEqual(
                    len(header), 1,
                    "the %s draw's table for a machine %s has no single header row"
                    % (side, reading))
                for key in sweep.OBSERVED_CHANNELS:
                    with self.subTest(reading=reading, side=side, channel=key):
                        self.assertIn("`%s`" % key, header[0])
                for record in of["determination"]:
                    with self.subTest(reading=reading, side=side,
                                      coefficient=record["coefficient"]):
                        row = [line for line in block.splitlines()
                               if line.startswith("| `%s` |" % record["coefficient"])]
                        self.assertEqual(len(row), 1)
                        cells = [cell.strip() for cell in row[0].strip("|").split("|")]
                        self.assertEqual(
                            len(cells), len(sweep.OBSERVED_CHANNELS) + 1,
                            "%s's row on the %s draw carries %d cells for %d channels"
                            % (record["coefficient"], side, len(cells) - 1,
                               len(sweep.OBSERVED_CHANNELS)))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C3: naming the parameter and limit
    # files, and their digests, the sweep was run against. A name alone does not
    # say which machine: a path can be rewritten under a record that goes on
    # reading as current, so each file is named with what it presently holds and
    # the record is out of date the moment any of them moves.
    def test_the_committed_record_names_the_files_it_was_run_against_as_they_stand(self):
        record = _committed_record()
        for path in (FINDINGS["description"], FINDINGS["limits"], FINDINGS["declaration"],
                     FINDINGS["tolerance"]):
            with self.subTest(file=path):
                self.assertIn(sweep._relative(path), record)
                self.assertIn(
                    sweep.digest_of(path), record,
                    "%s has changed since the committed finding was taken against it. Re-run "
                    "firmware/emulation/tools/run_parameter_identifiability.py"
                    % sweep._relative(path))

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C3: so it can be reproduced
    # against a replacement model by re-pointing the sweep rather than
    # rewritten. A second machine is written -- the reference description with
    # the coffee element at the figure its owner recalls rather than the
    # measured one -- and the whole method is run against it by argument alone.
    # It has to cover the same coefficients, name the replacement rather than
    # the shipped description, and come back with figures that moved: a method
    # quietly still reading the original satisfies the first two and not the
    # third.
    def test_the_same_method_run_against_a_replacement_model_needs_no_edit_to_it(self):
        replacement = cross_tier.description_with(
            REPLACEMENT_COEFFICIENT, REPLACEMENT_VALUE,
            os.path.join(sweep.BUILD_DIR, "identifiability-replacement.params"),
            source=FINDINGS["description"])

        elsewhere = sweep.run(
            description=replacement, limits=FINDINGS["limits"],
            executable=FINDINGS["executable"],
            workspace=os.path.join(sweep.BUILD_DIR, "identifiability-replacement"))
        finding = ident.determine(elsewhere)

        self.assertEqual(
            sorted(record["coefficient"] for record in finding["determination"]),
            sorted(record["coefficient"] for record in FINDING["determination"]),
            "the replacement model was analysed over a different set of coefficients")

        # Both readings are re-pointed, not only the first. A second reading
        # that went on being taken of the shipped machine would put that
        # machine's drift finding into a record naming the replacement, which is
        # the one way this could go wrong and still look right.
        elsewhere_drifted = ident.drifted_sweep(elsewhere)
        self.assertEqual(elsewhere_drifted["description"], replacement)
        self.assertNotEqual(
            elsewhere_drifted["workspace"], DRIFTED_FINDINGS["workspace"],
            "the replacement model's second reading wrote its perturbed descriptions where the "
            "shipped machine's second reading wrote its own, so one of the two is standing on "
            "files the other wrote")

        written = ident.report_text(elsewhere, finding, elsewhere_drifted,
                                    ident.determine(elsewhere_drifted))
        self.assertIn(sweep.digest_of(replacement), written)
        self.assertNotIn(sweep.digest_of(FINDINGS["description"]), written)

        moved = [record["coefficient"] for record in finding["determination"]
                 if record["in_scope"] and
                 abs(record["largest"] - _record(record["coefficient"])["largest"]) >
                 FIGURE_TOLERANCE * max(_record(record["coefficient"])["largest"], 1e-12)]
        self.assertTrue(
            moved,
            "analysing a machine whose coffee element is %s W rather than the measured figure "
            "produced the same reach on every channel for every coefficient, so the method is not "
            "reading the description it was pointed at" % REPLACEMENT_VALUE)

    # SOL-ESTIMATOR-PARAMETER-IDENTIFIABILITY.C3: mirrors how
    # docs/parameter-dominance.md already works for the sibling dominance
    # ranking -- and the two records are taken from the same runs, so the one a
    # reader arrives at first has to point at the other. The dominance record
    # used to say identifiability was not asked anywhere; a record left saying
    # that after this analysis exists would send a reader away from the answer.
    def test_the_dominance_record_points_at_this_one(self):
        with open(sweep.REPORT_PATH, encoding="utf-8") as handle:
            dominance = handle.read()
        self.assertIn(os.path.relpath(ident.REPORT_PATH, REPOSITORY_DIR), dominance)
        self.assertIn("run_parameter_identifiability.py", dominance)
        self.assertNotIn(
            "is not asked here", dominance,
            "the dominance record still says identifiability is asked nowhere, which stopped "
            "being true. Re-run firmware/emulation/tools/run_parameter_sweep.py")


class TheDeterminationIsTakenOverPerturbationsAppliedToTheMachineAlone(unittest.TestCase):
    """SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C2: The determination is taken
    over perturbations applied to the machine alone.

    The second reading is the same sweep with one thing withheld, and the whole
    of what has to be shown is that the one thing really was withheld. A second
    sweep that quietly handed each perturbed description to the control path as
    well would produce a second reading identical to the first, and a record
    carrying two identical readings reads exactly like a machine drift cannot
    hide anything from.
    """

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C2: applied to the machine alone
    # -- the control path is held at the description the perturbations move away
    # from, and the sweep records that it was rather than leaving it to be
    # inferred. Both sweeps are asked, because a field that said the same thing
    # about each would say nothing about either.
    def test_the_second_reading_held_the_control_path_at_the_unperturbed_description(self):
        self.assertEqual(
            DRIFTED_FINDINGS["description"], FINDINGS["description"],
            "the two readings are of two different machines, so nothing can be concluded from "
            "their disagreeing")
        self.assertEqual(
            DRIFTED_FINDINGS["control_description"], FINDINGS["description"],
            "the second reading's control path was not held at the description the perturbations "
            "move the machine away from")
        self.assertFalse(
            DRIFTED_FINDINGS["control_path_follows_the_machine"],
            "the second reading records its control path as following the machine, which is the "
            "first reading again")
        self.assertTrue(
            FINDINGS["control_path_follows_the_machine"],
            "the first reading records its control path as held at a description of its own, so "
            "it is not the coupled reading the record and the sealed evidence say it is")
        self.assertEqual(
            DRIFTED_FINDINGS["reference"][sweep.BREW_SIDE]["control_description"],
            FINDINGS["description"],
            "the second reading's unperturbed brew draw did not record which description its "
            "control path drove from")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C2: over perturbations applied
    # to the machine alone -- recomputed from the corner descriptions the second
    # reading actually wrote, because a signature checked against itself agrees
    # with itself over any arithmetic. The same two corners are then put through
    # the draw coupled, and the two recomputations have to differ: that is the
    # one comparison that says the perturbation was withheld rather than merely
    # that a second sweep was run.
    def test_the_recorded_signature_is_the_one_a_machine_alone_perturbation_produces(self):
        machine_alone = {}
        coupled = {}
        for corner in ("low", "high"):
            written = os.path.join(DRIFTED_FINDINGS["workspace"],
                                   "%s-%s.params" % (RECOMPUTED_COEFFICIENT, corner))
            self.assertTrue(os.path.exists(written), written)
            machine_alone[corner] = sweep.brew_draw(
                FINDINGS["executable"], written, FINDINGS["limits"],
                FINDINGS["courses"][sweep.BREW_SIDE], FINDINGS["converter_scale"],
                "drifted-recomputed-%s" % corner,
                control_description=DRIFTED_FINDINGS["control_description"])
            coupled[corner] = sweep.brew_draw(
                FINDINGS["executable"], written, FINDINGS["limits"],
                FINDINGS["courses"][sweep.BREW_SIDE], FINDINGS["converter_scale"],
                "drifted-recomputed-coupled-%s" % corner)

        def half_the_difference(runs, key):
            return [(high - low) / 2.0
                    for high, low in zip(runs["high"]["channels"][key],
                                         runs["low"]["channels"][key])]

        recorded = _entry(RECOMPUTED_COEFFICIENT, DRIFTED_FINDINGS)["signature"][sweep.BREW_SIDE]
        as_coupled = _entry(RECOMPUTED_COEFFICIENT)["signature"][sweep.BREW_SIDE]
        withheld = 0
        for key in sweep.OBSERVED_CHANNELS:
            held_still = half_the_difference(machine_alone, key)
            following = half_the_difference(coupled, key)
            with self.subTest(channel=key):
                self.assertEqual(
                    held_still, recorded[key],
                    "the second reading's recorded effect of %s on %s is not what those two "
                    "corner descriptions produce when the control path is held still"
                    % (RECOMPUTED_COEFFICIENT, key))
                self.assertEqual(
                    following, as_coupled[key],
                    "the same two corner descriptions run with the control path following the "
                    "machine did not reproduce the first reading's recorded effect on %s, so the "
                    "two readings are not perturbing the same machine by the same amount" % key)
            withheld += sum(1 for was, now in zip(held_still, following) if was != now)
        self.assertGreater(
            withheld, 0,
            "the same corner descriptions produced the same effect on every channel whether the "
            "control path was held still or not, so nothing was withheld from it and the second "
            "reading is the first one again")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C2: the machine alone -- and the
    # two readings can only come apart where a control path drives from a model
    # of the machine. The coffee side has one and the steam side does not: its
    # law is built from its own declaration and from no description of a casting.
    # So exactly one side has to move. A run where neither moved would mean
    # nothing was withheld anywhere; a run where the steam side moved would mean
    # the second reading changed something no description of a casting reaches.
    def test_the_readings_differ_where_a_control_path_drives_from_a_model_and_nowhere_else(self):
        self.assertEqual(
            ident.sides_the_readings_differ_on(FINDINGS, DRIFTED_FINDINGS), [sweep.BREW_SIDE],
            "the sides the two readings disagree about are not the coffee side alone: the coffee "
            "side's control path reconstructs from the description and the steam side's law is "
            "built from its own declaration, so that side and only that side can answer a "
            "description withheld from a control path")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C2: the determination is taken
    # over them -- a determination, meaning every in-scope coefficient leaves the
    # second reading with a verdict of its own, and one taken off the second
    # reading's own figures rather than the first's. A second determination that
    # reproduced the first's numbers would be the first one relabelled.
    def test_the_second_reading_produces_a_determination_of_its_own(self):
        drifted = dict((record["coefficient"], record)
                       for record in DRIFTED_FINDING["determination"] if record["in_scope"])
        self.assertEqual(sorted(drifted), sorted(DRIFTED_FINDING["scoped"]))
        for name, record in drifted.items():
            with self.subTest(coefficient=name):
                self.assertIn(record["verdict"],
                              (ident.IDENTIFIABLE, ident.BELOW_WHAT_A_READING_CARRIES,
                               ident.REPRODUCED_BY_THE_OTHERS))

        moved = [name for name, record in drifted.items()
                 if abs(record["largest"] - _record(name)["largest"]) >
                 FIGURE_TOLERANCE * max(_record(name)["largest"], 1e-12)]
        self.assertTrue(
            moved,
            "every coefficient reached every channel by the same amount under both readings, so "
            "holding the control path still changed nothing the determination is taken over")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C2: the same perturbations. The
    # two readings write a description per coefficient per corner under the same
    # names, so they need directories of their own or one reading stands on the
    # files the other wrote. What has to hold is both: the directories differ,
    # and the descriptions in them are the same machines -- since the whole claim
    # is that only where the description went changed.
    def test_the_two_readings_perturb_the_same_machines_in_directories_of_their_own(self):
        self.assertNotEqual(
            DRIFTED_FINDINGS["workspace"], FINDINGS["workspace"],
            "the second reading wrote its perturbed descriptions where the first wrote its own")
        for corner in ("low", "high"):
            first = os.path.join(FINDINGS["workspace"],
                                 "%s-%s.params" % (RECOMPUTED_COEFFICIENT, corner))
            second = os.path.join(DRIFTED_FINDINGS["workspace"],
                                  "%s-%s.params" % (RECOMPUTED_COEFFICIENT, corner))
            with self.subTest(corner=corner):
                self.assertTrue(os.path.exists(first) and os.path.exists(second))
                self.assertEqual(
                    sweep.digest_of(first), sweep.digest_of(second),
                    "the two readings perturbed %s's %s corner to different machines, so what "
                    "separates their answers is not only where the description went"
                    % (RECOMPUTED_COEFFICIENT, corner))


class AParameterHiddenByDriftIsNamedAsSuch(unittest.TestCase):
    """SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: A parameter identifiable
    when built differently and not when drifted is named as such.

    Both halves are asserted. The two readings have to be in the one record --
    a reader given one of them has been given one answer while the other
    question goes on looking answered -- and the crossing between them has to be
    named coefficient by coefficient, because it is the finding neither reading
    carries on its own.

    The crossing is put to the logic against synthetic readings as well as
    against this machine's, for the reason the verdicts themselves are: a
    coefficient can leave the second reading in three different ways and this
    model presently produces one of them. A suite asserting only what this model
    does would leave the other two implemented and never run.

    The criterion's other half is asserted here too, and it is the half a
    record satisfies by accident least often: a coefficient neither reading
    shows identifiable, and one both do, each stated once. Once means derived
    and written rather than left as two lists a reader intersects by eye, and
    it means once rather than under each reading with that reading's own
    figures -- two paragraphs about one unchanged verdict read as a
    disagreement to be resolved.

    And what the record may say around the crossing is held to what the two
    determinations carry. Two claims that do not survive them were in it: that
    a loop no longer told about its machine lets less of a coefficient's error
    reach the channels, which the figures contradict in both directions, and
    that what drift hides is what an instrument would be bought for, which the
    verdict's own definition rules out and which the record contradicted
    sixteen lines earlier.
    """

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: both readings are reported
    # together rather than one replacing the other. The committed record has to
    # carry the second reading's determination as well as the first's, with its
    # own figures, and the two have to be different tables -- a record that
    # wrote one of them twice would satisfy every structural check while
    # answering the drift question with the commissioning answer.
    def test_the_record_carries_both_readings_with_their_own_figures(self):
        committed = _committed_record()
        produced = _produced_record()

        for heading in (ident.READINGS_HEADING, ident.DETERMINATION_HEADING,
                        ident.DRIFT_DETERMINATION_HEADING, ident.HIDDEN_HEADING):
            with self.subTest(heading=heading):
                self.assertIn(heading, committed)

        was = ident.determination_rows(committed, ident.DRIFT_DETERMINATION_HEADING)
        now = ident.determination_rows(produced, ident.DRIFT_DETERMINATION_HEADING)
        self.assertTrue(was, "the committed record carries no drifted determination table")
        self.assertEqual([row["coefficient"] for row in was],
                         [row["coefficient"] for row in now])
        for before, after in zip(was, now):
            with self.subTest(coefficient=before["coefficient"]):
                self.assertEqual(before["verdict"], after["verdict"])
                for figure in ("largest", "unique_scoped", "unique_every", "fraction", "used"):
                    self.assertLessEqual(
                        abs(before[figure] - after[figure]),
                        FIGURE_TOLERANCE * max(abs(after[figure]), 1e-12) + 1e-12,
                        "the committed record gives %s a drifted %s of %g and this analysis now "
                        "gives it %g. Re-run "
                        "firmware/emulation/tools/run_parameter_identifiability.py"
                        % (before["coefficient"], figure, before[figure], after[figure]))

        coupled = ident.determination_rows(committed)
        self.assertNotEqual(
            coupled, was,
            "the record's two determinations are the same table, so one reading was written "
            "twice and the drift question has been answered with the commissioning answer")
        self.assertIn(
            sweep._relative(DRIFTED_FINDINGS["control_description"]), committed,
            "the record does not say which description the second reading's control path was "
            "held at, so what was withheld from it cannot be established from the record")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: is named as such. Every
    # coefficient the two readings disagree about in that direction is named in
    # the committed record, and each one's two verdicts are read back out of the
    # record's own tables rather than out of this run -- a record naming a
    # coefficient the tables beside it do not support is a finding nobody can
    # check.
    def test_every_coefficient_the_crossing_covers_is_named_in_the_committed_record(self):
        committed = _committed_record()
        computed = ident.hidden_by_drift(FINDING, DRIFTED_FINDING)
        named = ident.hidden_rows(committed)

        self.assertEqual(
            sorted(entry["coefficient"] for entry in computed),
            sorted(coefficient for coefficient, _ in named),
            "the committed record does not name the coefficients this analysis now finds "
            "identifiable when built differently and not when drifted. Re-run "
            "firmware/emulation/tools/run_parameter_identifiability.py")

        coupled = dict((row["coefficient"], row["verdict"])
                       for row in ident.determination_rows(committed))
        drifted = dict((row["coefficient"], row["verdict"])
                       for row in ident.determination_rows(
                           committed, ident.DRIFT_DETERMINATION_HEADING))
        for coefficient, verdict_when_drifted in named:
            with self.subTest(coefficient=coefficient):
                self.assertEqual(
                    coupled.get(coefficient), ident.IDENTIFIABLE,
                    "%s is named as hidden by drift and the record's own first reading does not "
                    "show it identifiable" % coefficient)
                self.assertNotEqual(
                    drifted.get(coefficient), ident.IDENTIFIABLE,
                    "%s is named as hidden by drift and the record's own second reading shows it "
                    "identifiable" % coefficient)
                self.assertEqual(drifted.get(coefficient, ident.REACHES_NO_RECONSTRUCTION),
                                 verdict_when_drifted)

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: not when drifted -- which a
    # coefficient can fail to be in three ways, and all three have to be caught.
    # It can be reproduced by the others once the loop absorbs part of it, it can
    # fall below what a reading could carry altogether, and the second reading
    # can find no reconstruction resting on it at all. The last is the one most
    # easily missed, because such a coefficient leaves the second reading with no
    # verdict rather than with a bad one -- and a machine that reveals nothing
    # about a coefficient reveals nothing about it whichever of the three is why.
    def test_the_crossing_is_found_whichever_way_the_second_reading_loses_a_coefficient(self):
        where = (sweep.BREW_SIDE, "brew-c")
        first = [10.0, 0.0, 0.0, 30.0, 0.0, 0.0, 5.0, 0.0]
        second = [0.0, 40.0, 0.0, 0.0, 20.0, 0.0, 0.0, 7.0]
        apart = [0.0, 0.0, 60.0, 0.0, 0.0, -25.0, 0.0, 0.0]
        built = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "crossing": {where: apart},
        }), reading=1.0)
        self.assertEqual(
            [record["verdict"] for record in built["determination"]],
            [ident.IDENTIFIABLE] * 3,
            "the first reading of this synthetic pair does not show all three identifiable, so "
            "there is nothing for the second to lose")

        # Reproduced by the others: the crossing coefficient is written as a
        # combination of the two it stood apart from.
        reproduced = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "crossing": {where: [2.0 * a - 0.5 * b for a, b in zip(first, second)]},
        }), reading=1.0)
        # Below what a reading could carry: it still stands apart and no longer
        # reaches any channel by as much as one count.
        faded = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "crossing": {where: [value / 1000.0 for value in apart]},
        }), reading=1.0)
        # No reconstruction resting on it: the second reading found the coffee
        # side's delivered temperature unmoved by it, so it has no verdict at all.
        unscoped = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "crossing": {where: apart},
        }, reaches_outlet={"first": True, "second": True, "crossing": False}), reading=1.0)

        for what, drifted, expected in (
                ("reproduced", reproduced, ident.REPRODUCED_BY_THE_OTHERS),
                ("faded", faded, ident.BELOW_WHAT_A_READING_CARRIES),
                ("unscoped", unscoped, ident.REACHES_NO_RECONSTRUCTION)):
            with self.subTest(way=what):
                hidden = dict((entry["coefficient"], entry["verdict_when_drifted"])
                              for entry in ident.hidden_by_drift(built, drifted))
                self.assertIn(
                    "crossing", hidden,
                    "a coefficient the first reading shows identifiable and the second loses by "
                    "being %s was not named as hidden by drift" % what)
                self.assertEqual(hidden["crossing"], expected)

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: identifiable when built
    # differently and not when drifted -- both halves, so neither a coefficient
    # both readings show identifiable nor one neither reading shows identifiable
    # may be named. The second is the one worth asserting: such a coefficient is
    # already named as not shown identifiable by the first reading, and naming it
    # again here would report a machine as having drifted out of a capability it
    # never had.
    def test_only_a_coefficient_the_first_reading_shows_identifiable_is_named(self):
        where = (sweep.BREW_SIDE, "brew-c")
        first = [10.0, 0.0, 0.0, 30.0, 0.0, 0.0, 5.0, 0.0]
        second = [0.0, 40.0, 0.0, 0.0, 20.0, 0.0, 0.0, 7.0]
        combination = [2.0 * a - 0.5 * b for a, b in zip(first, second)]
        apart = [0.0, 0.0, 60.0, 0.0, 0.0, -25.0, 0.0, 0.0]

        neither = _synthetic({
            "first": {where: first},
            "second": {where: second},
            "combination": {where: combination},
            "apart": {where: apart},
        })
        finding = ident.determine(neither, reading=1.0)
        self.assertEqual(
            ident.hidden_by_drift(finding, finding), [],
            "a reading put beside itself named a coefficient as hidden by drift, so the crossing "
            "is being read off one reading rather than off the disagreement between two")

        # And a second reading that loses the one coefficient the first reading
        # could show and treats the other three exactly as the first did. Only
        # that one may be named: the three the first reading could not show are
        # already named as not shown identifiable there, and naming them again
        # here would report a machine as having drifted out of a capability it
        # never had.
        faded = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "combination": {where: combination},
            "apart": {where: [value / 1000.0 for value in apart]},
        }), reading=1.0)
        named = [entry["coefficient"] for entry in ident.hidden_by_drift(finding, faded)]
        self.assertEqual(
            named, ["apart"],
            "the crossing named %s, where the first reading shows only `apart` identifiable and "
            "the second reading loses only that one" % named)

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: named as such -- which means
    # the record has to say so when nothing crosses as well as when something
    # does. A record that spoke up only where drift hid something would leave a
    # reader unable to tell "drift hides nothing here" from "nobody looked", and
    # those are opposite findings. Put to it by writing a record whose two
    # readings are the same one, which is the case that necessarily has no
    # crossing.
    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: naming what the two readings
    # show means naming it and nothing more. The obvious sentence to write
    # between two readings -- that a loop no longer told about its machine lets
    # less of a coefficient's error reach the channels, so the first reading is
    # optimistic relative to the second -- is a claim about a direction, and the
    # record's own two determination tables can falsify it. They do here: the
    # figure each verdict is taken on rises under drift for some coefficients
    # and falls for others. A record asserting the one direction anyway would
    # have a reader read both tables through a pattern the figures do not carry,
    # and would make the first reading look like a safe bound on the second.
    # Read out of the committed record's own tables rather than out of this run,
    # so that a record whose prose and figures had come apart fails here.
    def test_no_direction_is_claimed_between_the_readings_that_the_figures_deny(self):
        committed = _committed_record()
        coupled = dict((row["coefficient"], row)
                       for row in ident.determination_rows(committed))
        drifted = dict((row["coefficient"], row)
                       for row in ident.determination_rows(
                           committed, ident.DRIFT_DETERMINATION_HEADING))
        self.assertTrue(coupled and drifted, "the committed record carries no determination")

        fell, rose = [], []
        for coefficient, row in coupled.items():
            other = drifted.get(coefficient)
            if other is None:
                continue
            # Three significant figures is what the record carries, so a
            # difference smaller than that is a difference the record does not
            # claim either way.
            was, now = row["unique_scoped"], other["unique_scoped"]
            if abs(now - was) <= FIGURE_TOLERANCE * max(abs(was), abs(now)):
                continue
            (fell if now < was else rose).append(coefficient)

        self.assertTrue(
            fell and rose,
            "the committed record's two determinations move one way only (%d down, %d up), so "
            "the claim this asserts against is not falsified by them and this assertion has "
            "stopped testing anything" % (len(fell), len(rose)))
        self.assertIn(
            ident.NEITHER_READING_BOUNDS, committed,
            "the record's own figures move both ways between the two readings and it does not "
            "say so, so a reader is left to infer a direction from two tables")

        # The four sentences that stated the one direction, each of which the
        # tables above contradict. Named exactly, because each stood in the
        # record until the two determinations were read against it.
        for claimed in ("the channels move less",
                        "carry less of the coefficient's own error",
                        "is optimistic relative to",
                        "optimistic about drift"):
            with self.subTest(claim=claimed):
                self.assertNotIn(
                    claimed, committed,
                    "the record claims drift moves the channels one way, and its own two "
                    "determinations disagree: %s move further from the others under drift and "
                    "%s move nearer"
                    % (", ".join(sorted(rose)), ", ".join(sorted(fell))))

        # And the split the record states is the split its own tables carry.
        stated = _sentence_with(committed, ident.NEITHER_READING_BOUNDS)
        for coefficient in fell + rose:
            with self.subTest(coefficient=coefficient):
                self.assertIn(
                    "`%s`" % coefficient, stated,
                    "the record's comparison of the two readings does not say which way %s "
                    "moved. Re-run "
                    "firmware/emulation/tools/run_parameter_identifiability.py" % coefficient)

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: a coefficient drift hides is
    # named as such and as nothing else. It is not thereby a coefficient an
    # instrument would buy back: one hidden because what it does to every
    # channel modelled here is what a combination of the others drifting would
    # do is hidden by a confounding, and an instrument on any of those channels
    # carries that confounding rather than breaking it. The record said both --
    # that the unfitted channel is presently not worth spending on, and sixteen
    # lines later that the coefficient it hides is one an instrument would be
    # bought for -- and only the first followed from the figures.
    def test_a_coefficient_no_instrument_recovers_is_not_named_as_one_to_buy_for(self):
        committed = _committed_record()
        hidden = ident.hidden_by_drift(FINDING, DRIFTED_FINDING)
        if not hidden:
            self.skipTest("this model has no crossing for the record to say anything about")

        # The invariant, put to the analysis rather than to the prose. Both
        # figures a verdict is taken on are maxima over every channel the
        # signature is laid out against, so a coefficient the drifted reading
        # could not show identifiable is one no channel here separates -- the
        # unfitted ones included. An instrument on one of them therefore
        # recovers nothing, whatever a record might say.
        fitted = ident._channel_is_fitted()
        for entry in hidden:
            drifted = entry["drifted"]
            if drifted is None or not drifted["in_scope"]:
                continue
            with self.subTest(coefficient=entry["coefficient"]):
                by_channel = drifted["against_scoped"]["unique_by_channel"]
                on_unfitted = max((value for (side, key), value in by_channel.items()
                                   if not fitted[key]), default=0.0)
                reach_unfitted = max((value for (side, key), value in drifted["reached"].items()
                                      if not fitted[key]), default=0.0)
                self.assertTrue(
                    on_unfitted <= 1.0 or reach_unfitted <= 1.0,
                    "%s is hidden by drift and an unfitted channel carries both its reach and the "
                    "part nothing else reproduces above what that channel could resolve, so the "
                    "verdict it failed was not taken over that channel" % entry["coefficient"])

        said = _sentence_with(committed, ident.NO_INSTRUMENT_RECOVERS)
        self.assertTrue(
            said,
            "the committed record names coefficients drift hides and does not say what an "
            "instrument would do about them, so the section reads as a shopping list. Re-run "
            "firmware/emulation/tools/run_parameter_identifiability.py")
        self.assertNotIn(
            "the coefficients an instrument would be bought for", committed,
            "the record names what drift hides as what an instrument would be bought for, and its "
            "own account of the unfitted channel concludes from the same figures that the channel "
            "is presently not worth spending on")

        # And each one is given the reason its own verdict supplies, so a
        # coefficient hidden three different ways is not accounted for once.
        accounted = ident.why_no_instrument_recovers(hidden)
        self.assertEqual(
            sorted(entry["coefficient"] for entry, _ in accounted),
            sorted(entry["coefficient"] for entry in hidden),
            "the account of what an instrument would do does not cover every coefficient drift "
            "hides")
        for entry, why in accounted:
            with self.subTest(coefficient=entry["coefficient"]):
                self.assertIn(
                    "`%s`" % entry["coefficient"], committed)
                self.assertIn(
                    why, committed,
                    "the committed record does not carry the reason no instrument recovers %s. "
                    "Re-run firmware/emulation/tools/run_parameter_identifiability.py"
                    % entry["coefficient"])

        # The three ways the second reading can lose a coefficient are three
        # different things to tell a reader, and this model produces one of
        # them. Put to the logic against synthetic readings so the other two
        # are not left implemented and never run.
        where = (sweep.BREW_SIDE, "brew-c")
        first = [10.0, 0.0, 0.0, 30.0, 0.0, 0.0, 5.0, 0.0]
        second = [0.0, 40.0, 0.0, 0.0, 20.0, 0.0, 0.0, 7.0]
        apart = [0.0, 0.0, 60.0, 0.0, 0.0, -25.0, 0.0, 0.0]
        built = ident.determine(_synthetic({
            "first": {where: first},
            "second": {where: second},
            "crossing": {where: apart},
        }), reading=1.0)
        given = set()
        for what, signatures, reaches in (
                ("reproduced",
                 {"crossing": {where: [2.0 * a - 0.5 * b for a, b in zip(first, second)]}}, None),
                ("faded", {"crossing": {where: [value / 1000.0 for value in apart]}}, None),
                ("unscoped", {"crossing": {where: apart}},
                 {"first": True, "second": True, "crossing": False})):
            with self.subTest(way=what):
                drifted = ident.determine(_synthetic(dict(
                    {"first": {where: first}, "second": {where: second}}, **signatures),
                    reaches_outlet=reaches), reading=1.0)
                reasons = dict((entry["coefficient"], why) for entry, why
                               in ident.why_no_instrument_recovers(
                                   ident.hidden_by_drift(built, drifted)))
                self.assertIn(
                    "crossing", reasons,
                    "a coefficient the second reading loses by being %s was given no account of "
                    "what an instrument would do about it" % what)
                given.add(reasons["crossing"])
        self.assertEqual(
            len(given), 3,
            "the three ways drift can hide a coefficient are given the same reason for an "
            "instrument buying nothing, so a reader is told a confounding where the machine "
            "observes nothing at all")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C3: a parameter neither reading
    # shows identifiable, and one both do, are each stated once. Two readings
    # and two verdicts leave four ways for a coefficient to come out, and a
    # record naming only the crossing leaves the other three to be got by
    # intersecting two tables by eye -- which is the comparison the criterion
    # says a reader will not perform. So each of the three is derived and
    # stated, once: not repeated under both readings' accounts, and not left
    # implicit in the difference between two lists.
    def test_the_sets_the_two_readings_agree_on_are_each_stated_once(self):
        committed = _committed_record()
        both, neither, only_drifted = ident.readings_agree_on(FINDING, DRIFTED_FINDING)

        for marker in (ident.BOTH_READINGS_SHOW, ident.NEITHER_READING_SHOWS,
                       ident.ONLY_DRIFTED_SHOWS):
            with self.subTest(marker=marker):
                self.assertEqual(
                    committed.count(marker), 1,
                    "the committed record states '%s' %d times, and a set the two readings agree "
                    "on is one finding stated once" % (marker, committed.count(marker)))

        for marker, expected in ((ident.BOTH_READINGS_SHOW, both),
                                 (ident.NEITHER_READING_SHOWS, neither),
                                 (ident.ONLY_DRIFTED_SHOWS, only_drifted)):
            with self.subTest(marker=marker):
                self.assertEqual(
                    sorted(_coefficients_in(_sentence_with(committed, marker))), sorted(expected),
                    "the committed record's '%s' does not name what this analysis now computes. "
                    "Re-run firmware/emulation/tools/run_parameter_identifiability.py" % marker)

        # And the verdict paragraph for a coefficient neither reading could show
        # appears once over the whole record rather than under each reading with
        # that reading's own figures. Two paragraphs about one unchanged verdict
        # read as a disagreement to be resolved rather than as one finding.
        for coefficient in neither:
            with self.subTest(coefficient=coefficient):
                self.assertEqual(
                    committed.count("- `%s` — " % coefficient), 1,
                    "%s is not shown identifiable under either reading and the record accounts "
                    "for it %d times" % (coefficient, committed.count("- `%s` — " % coefficient)))

        # The three sets and the crossing between them account for every
        # coefficient a verdict was reached about, so nothing the reconstruction
        # rests on is left out of all four.
        crossing = [entry["coefficient"] for entry in ident.hidden_by_drift(FINDING,
                                                                            DRIFTED_FINDING)]
        self.assertEqual(
            sorted(both + neither + only_drifted + crossing),
            sorted(record["coefficient"] for record in FINDING["determination"]
                   if record["in_scope"]),
            "the four cases do not partition the coefficients the reconstruction rests on, so a "
            "coefficient is named under two of them or under none")

    def test_a_record_with_nothing_crossing_says_so_rather_than_falling_silent(self):
        nothing_crosses = ident.report_text(FINDINGS, FINDING, FINDINGS, FINDING)

        self.assertIn(ident.HIDDEN_HEADING, nothing_crosses)
        self.assertEqual(
            ident.hidden_rows(nothing_crosses), [],
            "a record whose two readings are the same one still named a coefficient as hidden "
            "by drift")
        self.assertIn(
            "No coefficient is in this position", nothing_crosses,
            "a record with nothing crossing left the section empty, so it reads as a question "
            "nobody asked rather than as an answer")
        crossing = ident.hidden_by_drift(FINDING, DRIFTED_FINDING)
        if crossing:
            self.assertNotIn(
                "No coefficient is in this position", _committed_record(),
                "the committed record says nothing crosses while this analysis finds %d that do. "
                "Re-run firmware/emulation/tools/run_parameter_identifiability.py" % len(crossing))
        else:
            self.assertIn(
                "No coefficient is in this position", _committed_record(),
                "this analysis finds nothing crossing and the committed record does not say so. "
                "Re-run firmware/emulation/tools/run_parameter_identifiability.py")


if __name__ == "__main__":
    unittest.main()
