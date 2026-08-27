"""What the side-by-side run has to have shown before it counts as evidence that
the two tiers' closed loops are running the same plant model.

The run happens once for the whole suite, on the same terms every other suite in
this directory is written: it is one draw put through two loops, and every
assertion below reads what that run produced rather than reaching for either
loop itself.

The negative case is deliberately not a second full run. What it takes to show
the comparison can fail is a draw the two loops disagree about, and producing
one costs a host draw and nothing more -- so the expensive half, the emulated
loop, is the one this suite is careful to run exactly once.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, "..", "tools"))
FIRMWARE_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, TOOLS)

import register_map  # noqa: E402
import run_closed_loop_check as closed_loop  # noqa: E402
import run_cross_tier_check as runner  # noqa: E402

FINDINGS = None

# Read out of the driving script's own source rather than restated here, on the
# terms register_map.py already reads the peripheral models' register constants
# without executing them -- closed_loop.py references the emulator's globals at
# module scope and cannot be imported outside it.
DRAW = register_map.source_constants(closed_loop.EXERCISE)
DRAW_STEPS = DRAW["DRAW_STEPS"]

# The phases the draw's course of pump levels is made of, read from the same
# place and for the same reason.
COURSE_PHASES = ("PRE_INFUSION_STEPS", "RAMP_STEPS", "HOLD_STEPS", "TAPER_STEPS", "REST_STEPS")
PEAK_PUMP_PERMILLE = DRAW["PEAK_PUMP_PERMILLE"]

# Where the host loop's own draw declares the names it reports its quantities
# under. Read rather than restated, because the parser both loops go through
# looks those names up and a name it stopped finding would be a quantity nobody
# compared.
HOST_DRAW_SOURCE = os.path.join(FIRMWARE_DIR, "src", "app", "native", "cross_tier_draw.c")

# The band a delivery is held to, which this comparison's tolerance is
# deliberately not. Read from the declaration rather than written here so the
# distance between the two is measured against what the machine actually
# declares rather than against a figure this file remembers.
TOLERANCE_DECLARATION = os.path.join(FIRMWARE_DIR, "params", "tolerance.declaration")

# How much tighter than that band a same-computation comparison has to be before
# it is asking a different question rather than the same one loosely. Two orders
# of magnitude is not a derivation of the tolerance -- that is derived from what
# single precision accumulates, and is stated where it is defined -- it is the
# margin below which the two questions would have collapsed into one.
BAND_MARGIN = 100.0

# What the deliberate divergence is. Half a watt in a kilowatt: five hundred
# times smaller than the error the description itself declares it is entitled to
# assume for this coefficient, and far below anything a drink could register. A
# perturbation that made a visible difference to the machine would show the
# comparison notices a different machine, which is not the claim -- the claim is
# that it notices two builds of the same model computing different numbers.
DIVERGENT_COEFFICIENT = "brew.heater_power_w"
DIVERGENT_VALUE = "1000.5"

# And the same again on the coefficient only the pump reaches: a hundredth of a
# bar in fifteen, forty times inside the error the description declares it is
# entitled to assume for it. It is a second perturbation rather than a wider one
# because it lands on a different quantity by a different path -- the heater's
# reaches the brew temperature through the loop that reads it, this one reaches
# the brew path's pressure through the water the draw is moving -- so a draw that
# commanded no flow could not produce it at all.
DIVERGENT_PUMP_COEFFICIENT = "pump.pressure_bar"
DIVERGENT_PUMP_VALUE = "15.01"

# And a third, written differently from both of the above because what it is for
# is different: it is not a hair, it is a machine somewhere else. A fifth off the
# coffee element's declared power, which is twice the error the description
# admits for it and still a figure the structure accepts as a machine. What has
# to be shown with it is which half of a draw a description reaches, and a
# perturbation small enough to be argued about would leave that turning on
# whether a difference survived rather than on where it landed.
DRIFT_COEFFICIENT = "brew.heater_power_w"
DRIFT_VALUE = "1200.0"

# A description no structure will accept as a machine, for the path where the
# record the control path is told to drive from is not one. It is the shortest
# of the refusals the loader already declares -- a line with no separator -- so
# what is being established is that the second description goes through that
# loader at all, not which of its refusals it lands on.
UNLOADABLE_DESCRIPTION = "this line has no separator\n"

# The level of full heater scale at or above which the control law has nothing
# further to give: what it commands is clamped there, so an interval sitting at
# it is one where the reconstruction the loop drives from could have been
# anything below the target and the same level would have been driven.
FULL_HEATER_SCALE = 1000

# What the sensed brew temperature has to move by across the draw before the
# comparison is over a trajectory rather than over a machine standing still.
# Generous under what the draw actually reaches, so a run that barely moved
# fails clearly rather than by a coin's width.
MINIMUM_BREW_RISE_C = 2.0

# And what the brew path's pressure has to reach, on the same terms. A draw that
# never moved water leaves this quantity at the nothing it came up at for every
# interval, and two loops agreeing about a quantity neither of them moved agree
# about nothing.
MINIMUM_BREW_PRESSURE_BAR = 1.0


def setUpModule():
    global FINDINGS
    FINDINGS = runner.run_once()


def _declared_band_milli_c():
    with open(TOLERANCE_DECLARATION, encoding="utf-8") as handle:
        for line in handle:
            match = re.match(r"\s*brew-temperature-band\s*=\s*(\d+)\s+milli-c\b", line)
            if match:
                return int(match.group(1))
    raise AssertionError("%s declares no brew temperature band" % TOLERANCE_DECLARATION)


def _declared_keys(path, declaration, pattern):
    """The quoted names one source file declares it reports quantities under.

    Read out of the source rather than imported, for the reason every other
    figure this suite takes off these two files is: the host loop's draw is C and
    the emulated loop's script references the emulator's own globals at module
    scope, so neither can be asked for its list by running it.
    """
    with open(path, encoding="utf-8") as handle:
        match = re.search(pattern, handle.read(), re.DOTALL)
    if not match:
        raise AssertionError("%s declares no %s to report under" % (path, declaration))
    return tuple(re.findall(r'"([^"]+)"', match.group(1)))


def _host_draws_quantity_keys():
    """The names the host tier's draw prints its quantities under, in order."""
    return _declared_keys(
        HOST_DRAW_SOURCE, "quantity_key[]", r"quantity_key\[\]\s*=\s*\{(.*?)\}")


def _emulated_draws_quantity_keys():
    """The names the emulated loop prints its quantities under, in order."""
    return _declared_keys(
        closed_loop.EXERCISE, "TRAJECTORY_QUANTITIES",
        r"TRAJECTORY_QUANTITIES\s*=\s*\((.*?)\n\)")


def _diverged_host_draw(coefficient=DIVERGENT_COEFFICIENT, value=DIVERGENT_VALUE, name="diverged"):
    """One host draw of the same commanded draw against a description the
    emulated loop is not using."""
    perturbed = runner.description_with(
        coefficient, value, os.path.join(runner.BUILD_DIR, "%s.params" % name))
    return runner.host_draw(
        FINDINGS["executable"], perturbed, FINDINGS["limits"],
        FINDINGS["emulation"]["target_brew_c"], FINDINGS["course"],
        FINDINGS["converter_scale"], name=name)


def _drifted_description(name="drifted"):
    """A description of the same machine somewhere else, for the runs that have
    to establish which half of a draw a description reaches."""
    return runner.description_with(
        DRIFT_COEFFICIENT, DRIFT_VALUE, os.path.join(runner.BUILD_DIR, "%s.params" % name))


def _draw_described_by(machine, control, name):
    """One host draw of the same commanded draw, with the machine and the
    control path each built from a description this caller names."""
    return runner.host_draw(
        FINDINGS["executable"], machine, FINDINGS["limits"],
        FINDINGS["emulation"]["target_brew_c"], FINDINGS["course"],
        FINDINGS["converter_scale"], name=name, control_description=control)


def _trajectory_of(findings):
    """What the plant model carried at every interval of one draw, as the
    figures alone.

    Compared exactly rather than within a tolerance wherever this is used. Both
    sides of every such comparison are read back from what one artefact printed,
    at the nine significant digits that round-trip the single precision the
    model carries -- so two runs of the same machine produce the same characters
    and two runs of different ones do not.
    """
    return [reported["quantities"] for reported in findings["trajectory"]]


def _host_draw_at(scale, name):
    """One host draw of the same commanded draw, read through a converter of a
    different full scale."""
    return runner.host_draw(
        FINDINGS["executable"], FINDINGS["description"], FINDINGS["limits"],
        FINDINGS["emulation"]["target_brew_c"], FINDINGS["course"], scale, name=name)


class TheTwoLoopsReportTheSamePlantTrajectory(unittest.TestCase):
    """SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: The host tier's closed loop and
    the emulation tier's closed loop report the same plant trajectory for an
    identical commanded draw.
    """

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: an identical commanded draw -- the
    # two loops have to have been asked for the same thing over the same number
    # of intervals against the same description before anything they report can
    # be compared at all. Both halves of the ask are checked: the intervals, and
    # the level the pump was commanded at on each of them.
    def test_the_two_loops_were_driven_through_the_same_draw(self):
        emulation, host = FINDINGS["emulation"], FINDINGS["host"]
        self.assertEqual(
            emulation["draw_steps"], DRAW_STEPS,
            "the emulated loop did not run the draw its own script declares")
        self.assertEqual(
            host["draw_intervals"], DRAW_STEPS,
            "the host loop was not driven through as many intervals as the emulated one")
        self.assertEqual(
            len(FINDINGS["course"]), DRAW_STEPS,
            "the course the host loop was driven along is not the emulated loop's")
        self.assertEqual(
            [level for _, level in FINDINGS["course"]],
            [reported["pump_permille"] for reported in emulation["trajectory"]],
            "the course handed to the host loop is not the one the emulated loop commanded")
        self.assertEqual(
            [reported["pump_permille"] for reported in host["trajectory"]],
            [reported["pump_permille"] for reported in emulation["trajectory"]],
            "the two loops did not command the pump at the same level on every interval, so "
            "they were not asked for the same draw")
        self.assertEqual(
            os.path.abspath(FINDINGS["description"]),
            os.path.abspath(closed_loop.PLANT_PARAMETERS),
            "the host loop's machine is described by a different file from the one the "
            "emulated loop's bridge loads, so the two are not drawing from the same machine")

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: an identical commanded draw --
    # which is the course the emulated script declares, whole. A course whose
    # phases summed to fewer intervals than the draw would leave the rest of it
    # commanding whatever the last phase happened to fall through to.
    def test_the_declared_course_covers_every_interval_of_the_draw(self):
        self.assertEqual(
            sum(DRAW[phase] for phase in COURSE_PHASES), DRAW_STEPS,
            "the phases the draw's course is declared in do not add to the draw's own length")
        commanded = [reported["pump_permille"] for reported in FINDINGS["emulation"]["trajectory"]]
        self.assertEqual(
            max(commanded), PEAK_PUMP_PERMILLE,
            "the draw never reached the level its course declares it holds at")
        self.assertEqual(
            commanded[0], 0,
            "the draw drew water before the course says anything was asked for")
        self.assertEqual(
            commanded[-1], 0,
            "the draw was still drawing water at its last interval, so the pressure it "
            "leaves behind is a shot that never ended")

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: across a full simulated draw --
    # from the same starting point. Bringing either loop up drives its outputs,
    # and a comparison begun from wherever that left each model would be
    # reporting the bring-up rather than the models.
    #
    # SOL-EMULATION-BRINGUP-DISCARDED-BEFORE-DRAW.C1: whatever a draw's
    # bring-up moves the plant model by is undone before the draw starts --
    # the pre_draw_quantities == trajectory_baseline assertions below are that
    # undoing, checked on both tiers.
    #
    # SOL-EMULATION-BRINGUP-DISCARDED-BEFORE-DRAW.C2: the discarded bring-up
    # interval count is reported so a run can confirm its pre-draw state is
    # unperturbed -- the pre_draw_steps assertions below are that report,
    # checked on both tiers.
    def test_the_draw_began_with_both_models_where_they_came_up(self):
        emulation = FINDINGS["emulation"]
        self.assertEqual(
            emulation["pre_draw_quantities"], emulation["trajectory_baseline"],
            "bringing the emulated loop up moved its plant model away from the state it "
            "came up in, so the draw the host loop was given does not begin where this one did")
        self.assertEqual(
            FINDINGS["host"]["trajectory_baseline"], emulation["trajectory_baseline"],
            "the two loops' models did not come up in the same state")
        self.assertGreater(
            emulation["pre_draw_steps"], 0,
            "the emulated loop's bring-up drove nothing, so this run is not evidence that "
            "what it drove was undone")
        self.assertGreater(
            FINDINGS["host"]["pre_draw_steps"], 0,
            "the host loop's bring-up drove nothing, so this run is not evidence that what "
            "it drove was undone either")

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: the plant model's four sensed
    # quantities ... at every control interval -- all four of them, at all of
    # them. A comparison that quietly covered one quantity, or stopped part way
    # through the draw, would pass exactly as this one does.
    def test_every_sensed_quantity_was_compared_at_every_interval(self):
        comparison = FINDINGS["comparison"]
        self.assertEqual(comparison["intervals"], DRAW_STEPS)
        for side in ("emulation", "host"):
            for interval, reported in enumerate(FINDINGS[side]["trajectory"]):
                with self.subTest(side=side, interval=interval):
                    self.assertEqual(
                        len(reported["quantities"]), len(runner.QUANTITY_NAMES),
                        "the %s tier reported %d quantities at interval %d, not the four this "
                        "comparison is over"
                        % (side, len(reported["quantities"]), interval))

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: the plant model's four sensed
    # quantities -- which the comparison finds by name. A loop that renamed one,
    # or printed them in another order, would have its figures read into the
    # wrong quantity or not read at all, and both loops have to be reporting
    # under the names the parser looks up.
    def test_both_loops_report_the_quantities_under_the_names_the_comparison_looks_up(self):
        self.assertEqual(
            _host_draws_quantity_keys(), closed_loop.QUANTITY_KEYS,
            "the host tier's draw prints its quantities under names the comparison does not "
            "look up")
        self.assertEqual(
            _emulated_draws_quantity_keys(), closed_loop.QUANTITY_KEYS,
            "the emulated loop prints its quantities under names the comparison does not "
            "look up")

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: report the same plant trajectory
    # -- a trajectory, which means the model has to have gone somewhere. Two
    # loops agreeing about a model that never moved agree about nothing, and
    # that is asked of the quantities a brew draw reaches: the block's own
    # temperature, and the pressure the pump puts in the brew path.
    def test_the_draw_moved_the_model_on_both_sides(self):
        brew_c, brew_bar = 0, 2
        for side in ("emulation", "host"):
            with self.subTest(side=side):
                trajectory = FINDINGS[side]["trajectory"]
                started = FINDINGS[side]["trajectory_baseline"][brew_c]
                ended = trajectory[-1]["quantities"][brew_c]
                self.assertGreaterEqual(
                    ended - started, MINIMUM_BREW_RISE_C,
                    "the %s tier's brew temperature moved by only %.3fC across the draw, so "
                    "there is no trajectory here to have agreed about"
                    % (side, ended - started))
                reached = max(
                    reported["quantities"][brew_bar] for reported in trajectory)
                self.assertGreaterEqual(
                    reached, MINIMUM_BREW_PRESSURE_BAR,
                    "the %s tier's brew pressure reached only %.3f bar across the draw, so "
                    "the draw never moved water and that quantity was compared dead"
                    % (side, reached))

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: brew and steam temperature and
    # pressure -- and this machine's steam pair sit still throughout, which the
    # criterion states as its own boundary. Asserted rather than left implicit,
    # because the reason is structural and a run where they did move would mean
    # something had commanded a channel no control entry point on this machine
    # reaches: the steam mass moves only under its own heater's duty, and the
    # steam path's pressure only once that mass is above saturation.
    def test_the_steam_pair_stand_still_because_a_brew_draw_reaches_neither(self):
        steam_c, steam_bar = 1, 3
        for side in ("emulation", "host"):
            baseline = FINDINGS[side]["trajectory_baseline"]
            for interval, reported in enumerate(FINDINGS[side]["trajectory"]):
                with self.subTest(side=side, interval=interval):
                    self.assertEqual(
                        reported["quantities"][steam_c], baseline[steam_c],
                        "the %s tier's steam temperature moved at interval %d, which nothing "
                        "a brew draw commands can do" % (side, interval))
                    self.assertEqual(
                        reported["quantities"][steam_bar], baseline[steam_bar],
                        "the %s tier's steam pressure moved at interval %d, which nothing a "
                        "brew draw commands can do" % (side, interval))

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: stay within a stated numerical
    # tolerance of each other at every control interval. This is the comparison
    # itself; everything above establishes it is being asked of the right thing.
    def test_the_two_loops_stayed_within_tolerance_at_every_interval(self):
        comparison = FINDINGS["comparison"]
        self.assertEqual(
            comparison["divergences"], [],
            "the two loops' plant models did not agree across the draw:\n%s"
            % "\n".join(comparison["divergences"][:20]))

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: both loops advanced the model the
    # same number of times. Two trajectories that agreed while one loop had
    # stepped its model more often than the other would be two different draws
    # that happened to arrive at the same figures.
    def test_both_loops_advanced_the_model_once_for_every_interval_of_the_draw(self):
        self.assertEqual(FINDINGS["emulation"]["plant_step_count"], DRAW_STEPS)
        self.assertEqual(FINDINGS["host"]["plant_step_count"], DRAW_STEPS)

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: not from the machine's brew or
    # flow delivery-tolerance bands, which answer a different question and are
    # looser than a same-computation comparison warrants. A tolerance that had
    # drifted up toward the band would be answering the band's question.
    def test_the_tolerance_is_far_tighter_than_the_band_a_delivery_is_held_to(self):
        band_c = _declared_band_milli_c() / 1000.0
        self.assertLess(
            runner.TOLERANCE * BAND_MARGIN, band_c,
            "the tolerance this comparison uses (%.3e C) is within %g of the +/-%.3f C band a "
            "delivery is held to, so it is no longer asking a tighter question than the band"
            % (runner.TOLERANCE, BAND_MARGIN, band_c))

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: a round trip through the modelled
    # peripherals, which is the difference between the two routes this criterion
    # exists to cover. A draw that held the heater at full scale on every
    # interval would put the converter outside the loop entirely -- what it
    # reported could not change what was commanded next -- so the two loops
    # would agree about a plant driven open-loop, and the round trip would be
    # covered by nothing. Both loops have to have been controlling.
    def test_the_loop_left_the_heaters_limit_on_both_sides(self):
        for side in ("emulation", "host"):
            levels = [reported["heater_permille"] for reported in FINDINGS[side]["trajectory"]]
            with self.subTest(side=side):
                self.assertTrue(
                    any(level >= FULL_HEATER_SCALE for level in levels),
                    "the %s tier's heater never reached full scale across the draw, so this "
                    "run is not evidence the loop leaves it" % side)
                self.assertTrue(
                    any(level < FULL_HEATER_SCALE for level in levels),
                    "the %s tier's heater sat at full scale for every interval of the draw, so "
                    "nothing the converter reported could change what was commanded next and "
                    "the round trip this comparison is over was not exercised" % side)

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C1: an identical commanded draw --
    # identical in what each loop drove as well as in what each was asked for.
    # Two loops that agreed about the plant while commanding the heater
    # differently would be agreeing about a model that had been driven by two
    # different inputs.
    def test_the_two_loops_drove_the_heater_identically_at_every_interval(self):
        self.assertEqual(
            [reported["heater_permille"] for reported in FINDINGS["host"]["trajectory"]],
            [reported["heater_permille"] for reported in FINDINGS["emulation"]["trajectory"]],
            "the two loops commanded the heater at different levels, so the plant each drove "
            "was not driven by the same actuation")


class ADeliberateDivergenceFailsTheComparison(unittest.TestCase):
    """SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C2: A deliberate divergence between
    the two closed loops fails the comparison.
    """

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C2: a parameter file that differs
    # between the two ... fails the trajectory comparison in .C1 rather than
    # passing it. The emulated loop is left exactly as it ran; the host loop is
    # given a description differing in one coefficient by half a watt in a
    # kilowatt, and the comparison has to notice.
    def test_a_description_differing_between_the_two_loops_fails_the_comparison(self):
        diverged = _diverged_host_draw()
        comparison = runner.compare(FINDINGS["emulation"], diverged)

        self.assertTrue(
            comparison["divergences"],
            "the two loops were run against descriptions differing in %s and the comparison "
            "reported no divergence, so a passing result from it means nothing"
            % DIVERGENT_COEFFICIENT)
        self.assertGreater(
            comparison["worst"][0], runner.TOLERANCE,
            "the divergence the comparison reported is not above the tolerance it is measured "
            "against")

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C2: a parameter file that differs
    # between the two -- differing in the one coefficient nothing but the pump
    # reaches. The perturbation above travels to the brew temperature through the
    # loop that reads it; this one travels to the brew path's pressure through
    # the water the draw is moving, so a draw commanding no flow could not
    # produce it at all and the comparison over that quantity would never have
    # been asked anything.
    def test_a_description_differing_in_what_the_pump_makes_fails_on_the_pressure(self):
        diverged = _diverged_host_draw(
            DIVERGENT_PUMP_COEFFICIENT, DIVERGENT_PUMP_VALUE, name="diverged-pump")
        comparison = runner.compare(FINDINGS["emulation"], diverged)
        brew_bar = 2

        self.assertGreater(
            comparison["worst"][brew_bar], runner.TOLERANCE,
            "the two loops were run against descriptions differing in %s and their brew "
            "pressures stayed within the tolerance, so the pressure the draw moves is not "
            "actually being compared" % DIVERGENT_PUMP_COEFFICIENT)
        self.assertTrue(
            any(runner.QUANTITY_NAMES[brew_bar] in divergence
                for divergence in comparison["divergences"]),
            "the comparison reported no divergence naming %s"
            % runner.QUANTITY_NAMES[brew_bar])

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C2: demonstrating that the check is
    # sensitive to a real divergence. What the divergence is has to be legible
    # from the failure, or a run that fails leaves whoever has to fix it running
    # the whole thing again by hand to find out where.
    def test_the_failure_names_the_quantity_the_interval_and_how_far_apart(self):
        diverged = _diverged_host_draw()
        comparison = runner.compare(FINDINGS["emulation"], diverged)
        first = comparison["divergences"][0]

        self.assertIn("interval ", first)
        self.assertIn(runner.QUANTITY_NAMES[0], first)
        self.assertIn("apart", first)
        self.assertIn(comparison["worst_at"][0], [
            "interval %d" % reported["interval"] for reported in diverged["trajectory"]])

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C2: demonstrating that the check is
    # sensitive to a real divergence -- and a run that passed it whatever the
    # place a divergence sat in would be reporting somewhere nobody can act on.
    # A run where the two loops agreed everywhere still happened somewhere, and
    # the report has to name it.
    def test_a_run_that_diverged_nowhere_still_names_where_it_was_worst(self):
        comparison = FINDINGS["comparison"]
        for index, name in enumerate(runner.QUANTITY_NAMES):
            with self.subTest(quantity=name):
                self.assertIsNotNone(
                    comparison["worst_at"][index],
                    "the comparison reports the worst separation on %s as having happened "
                    "nowhere" % name)

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C2: not a tolerance so loose it passes
    # regardless of input. The draw above moves two of the four quantities, so
    # the divergence it produces only ever lands on those; this asks the
    # comparison the same question about each of the four in turn, just over the
    # tolerance and just under it.
    def test_the_comparison_turns_on_the_tolerance_for_every_quantity(self):
        quantities = len(runner.QUANTITY_NAMES)
        baseline = [1.0] * quantities

        def one_interval(values):
            return {
                "trajectory_baseline": list(baseline),
                "trajectory": [{"interval": 0, "result": 0, "plant_steps": 1,
                                "quantities": list(values)}],
            }

        unmoved = one_interval(baseline)
        for index in range(quantities):
            just_under = list(baseline)
            just_under[index] += runner.TOLERANCE * 0.9
            just_over = list(baseline)
            just_over[index] += runner.TOLERANCE * 1.1

            with self.subTest(quantity=runner.QUANTITY_NAMES[index]):
                self.assertEqual(
                    runner.compare(unmoved, one_interval(just_under))["divergences"], [],
                    "a separation inside the tolerance was reported as a divergence")
                over = runner.compare(unmoved, one_interval(just_over))["divergences"]
                self.assertTrue(
                    over,
                    "a separation outside the tolerance on %s was not reported, so that "
                    "quantity is not actually being compared" % runner.QUANTITY_NAMES[index])
                self.assertIn(runner.QUANTITY_NAMES[index], over[0])

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C2: the check is sensitive to a real
    # divergence and not a tolerance so loose it passes regardless of input --
    # of input, which includes the instrument the loop reads itself through. A
    # comparison run over a loop the converter sits outside of would agree
    # whatever the converter did, and would go on agreeing after the round trip
    # this criterion's own .C1 is over had stopped working. So the same draw is
    # put through the host loop again with the converter's full scale moved, and
    # the trajectory has to come out somewhere else.
    def test_the_reading_the_converter_reports_changes_what_the_draw_does(self):
        counts, milli = FINDINGS["converter_scale"]
        as_run = [reported["quantities"] for reported in FINDINGS["host"]["trajectory"]]

        # The finest case is a few counts rather than one. A single count moves
        # the scale by roughly a four-thousandth of the full span (one part in
        # ADC_FULL_SCALE_COUNTS), which was found by measurement to be fine
        # enough that whether it survives to a reported difference is not
        # robust: growing SOL-HOT-WATER-BAND-HOLDS-RATE-YIELDS's
        # delivery_tolerance_t by two fields (embedded by value in
        # control_state_t) made this subcase report no difference at all,
        # even though that slice's own logic is provably unreached by this
        # draw -- it never commands a profile-based delivery, so
        # delivery_running stays false throughout and every branch the new
        # yield logic added is skipped. Comparing the host tier alone before
        # and after that struct growth on the same course produced
        # byte-identical trajectories, which rules out a host-side
        # floating-point rounding shift as the cause; the more likely
        # explanation is that the larger struct shifted per-step execution
        # time on the emulated (Renode) tier enough to move the clock jitter
        # that tier's run records, which this host-only comparison then
        # replays -- but that half was not directly confirmed. Whatever the
        # exact mechanism, one count is evidently not a robust distance
        # against unrelated, semantically inert changes elsewhere in the
        # tree, which is a false failure this test exists to avoid rather
        # than to produce. A handful of counts is still far finer than
        # "coarser" and "finer" above and stays a converter-granularity
        # question, not a tolerance-width one. See
        # SOL-CROSS-TIER-CONVERTER-MARGIN-WIDENED for the discovery this
        # restates.
        for name, scale in (("coarser", (counts // 4, milli)),
                            ("finer", (counts * 4, milli)),
                            ("few-counts", (counts - 5, milli))):
            with self.subTest(converter=name):
                elsewhere = _host_draw_at(scale, "converter-%s" % name)
                self.assertEqual(
                    len(elsewhere["trajectory"]), len(as_run),
                    "the draw read through a %s converter did not run to the same length" % name)
                self.assertNotEqual(
                    [reported["quantities"] for reported in elsewhere["trajectory"]], as_run,
                    "moving the converter's full scale to %s left the host loop's trajectory "
                    "byte for byte where it was, so what the converter reports reaches nothing "
                    "the loop commands and the round trip is outside the comparison" % name)

    # SOL-PLANT-MODEL-AGREES-ACROSS-TIERS.C2: demonstrating that the check is
    # sensitive to a real divergence. Two runs that did not even cover the same
    # intervals are not a divergence the tolerance could measure -- there is no
    # pair of figures to put a distance between -- so the comparison has to
    # refuse them outright rather than compare whatever the two happen to have in
    # common and report agreement over that.
    def test_two_loops_that_did_not_run_the_same_draw_fail_the_comparison(self):
        emulation = FINDINGS["emulation"]

        shortened = dict(FINDINGS["host"])
        shortened["trajectory"] = FINDINGS["host"]["trajectory"][:-1]
        self.assertTrue(
            runner.compare(emulation, shortened)["divergences"],
            "a host run that stopped an interval short was compared as though it had not")

        restepped = dict(FINDINGS["host"])
        restepped["trajectory"] = [dict(reported) for reported in FINDINGS["host"]["trajectory"]]
        restepped["trajectory"][0]["plant_steps"] += 1
        self.assertTrue(
            runner.compare(emulation, restepped)["divergences"],
            "a host run that advanced the model a different number of times was compared as "
            "though it had not")


class ADrawTakesOneDescriptionForTheMachineAndAnotherForTheControlPath(unittest.TestCase):
    """SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C1: A draw takes one
    description for the machine and another for the control path.

    Four runs of the one draw the suite above already established is a draw:
    both halves described the same way, each half described differently in turn,
    and both described differently together. What each has to show is different,
    and no one of them shows it alone -- a run where a second description
    changed the trajectory says only that something reached something, and a run
    where it changed nothing says only that this course could not tell.

    The comparisons are exact. Both sides of each are read back from figures one
    artefact printed at the precision that round-trips them, so a run of the
    same machine under the same loop produces the same characters.
    """

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C1: a draw takes one description
    # for the machine and another for the control path -- and a draw handed the
    # same one for both is the draw it always was. This is what says the second
    # description is an addition to the harness and not a change to it: every
    # run this repository's sealed evidence rests on names no second description,
    # and a draw that had started answering differently for them would have
    # moved the machine underneath that evidence.
    def test_a_draw_handed_the_same_description_twice_is_the_draw_it_was_before(self):
        again = _draw_described_by(FINDINGS["description"], FINDINGS["description"], "same-twice")

        self.assertEqual(
            _trajectory_of(again), _trajectory_of(FINDINGS["host"]),
            "naming the machine's own description for the control path as well moved the "
            "trajectory, so a draw that names no second description and one that names the same "
            "one are not the same run")
        self.assertEqual(
            [reported["heater_permille"] for reported in again["trajectory"]],
            [reported["heater_permille"] for reported in FINDINGS["host"]["trajectory"]],
            "the loop commanded the heater differently when handed its own description twice")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C1: another for the control path
    # -- which is worth nothing unless the control path is what it reaches. The
    # machine is left exactly as the run above built it and only the record the
    # loop reconstructs from is moved, so anything that changes did so through
    # the loop's own reconstruction and through nothing else.
    def test_a_description_named_for_the_control_path_alone_reaches_the_loop(self):
        drifted = _drifted_description()
        elsewhere = _draw_described_by(FINDINGS["description"], drifted, "control-elsewhere")

        self.assertEqual(
            elsewhere["description"], FINDINGS["description"],
            "the run recorded a machine other than the one it was given")
        self.assertEqual(
            elsewhere["control_description"], drifted,
            "the run did not record the description its control path was told to drive from")
        self.assertNotEqual(
            _trajectory_of(elsewhere), _trajectory_of(FINDINGS["host"]),
            "moving only the description the control path reconstructs from left the trajectory "
            "byte for byte where it was, so the second description reaches nothing the loop does "
            "and this draw cannot represent a machine its controller is wrong about")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C1: one description for the
    # machine and another for the control path -- the two being separate is the
    # whole of it, and separateness is only shown by a run where the two differ
    # coming out somewhere neither of the runs where they agree came out. A
    # perturbation reaching the machine alone has to differ from the same
    # perturbation reaching both, or the control path is being handed the
    # machine's description whatever the caller asked for.
    def test_a_perturbation_kept_from_the_control_path_is_not_the_run_that_reaches_it(self):
        drifted = _drifted_description()
        machine_alone = _draw_described_by(drifted, FINDINGS["description"], "machine-alone")
        both = _draw_described_by(drifted, drifted, "both-elsewhere")

        self.assertNotEqual(
            _trajectory_of(machine_alone), _trajectory_of(FINDINGS["host"]),
            "perturbing the machine alone left the trajectory where the unperturbed run put it, "
            "so the first description reaches neither half of the draw")
        self.assertNotEqual(
            _trajectory_of(machine_alone), _trajectory_of(both),
            "a perturbation given to the machine alone produced the same trajectory as the same "
            "perturbation given to the machine and the control path together, so the control "
            "path was built from the machine's description whichever was named for it")
        self.assertEqual(
            len(machine_alone["trajectory"]), len(both["trajectory"]),
            "the two runs did not cover the same intervals, so the comparison above is between "
            "two different draws rather than two different machines")

    # SOL-ESTIMATOR-IDENTIFIABILITY-UNDER-DRIFT.C1: a description, which means a
    # record admitted on the terms every description is. A control path told to
    # drive from something no structure will accept as a machine is not a
    # drifted machine, it is a broken run, and it has to stop rather than fall
    # back on the machine's own description and report a coupled run under a
    # decoupled run's name. Both ways of failing to be one are put to it: a file
    # that is not there, and a file that is there and is not a machine.
    def test_a_control_description_that_is_not_a_machine_stops_the_draw(self):
        missing = os.path.join(runner.BUILD_DIR, "no-such.params")
        if os.path.exists(missing):
            os.remove(missing)
        with self.assertRaises(runner.CrossTierError):
            _draw_described_by(FINDINGS["description"], missing, "control-missing")

        unloadable = os.path.join(runner.BUILD_DIR, "unloadable.params")
        os.makedirs(os.path.dirname(unloadable), exist_ok=True)
        with open(unloadable, "w", encoding="utf-8") as handle:
            handle.write(UNLOADABLE_DESCRIPTION)
        with self.assertRaises(runner.CrossTierError) as refused:
            _draw_described_by(FINDINGS["description"], unloadable, "control-unloadable")
        self.assertIn(
            unloadable, str(refused.exception),
            "the draw was refused without naming which of the two descriptions it refused, which "
            "is the one thing whoever has to fix it needs")


if __name__ == "__main__":
    unittest.main()
