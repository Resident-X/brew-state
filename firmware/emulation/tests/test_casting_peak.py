"""How hot each thermoblock's casting gets while the controller holds its heater,
and what the controller boards' figures record derives from it.

The analysis itself is in emulation/tools/run_casting_peak.py, which runs the
shipped control path through warm-up, the hold, each delivery, the recovery
after it and a delivery started on the next interval, at every corner the
control path's own enumeration names. This suite is what judges the answer, and
what keeps the committed record, and the figures record that quotes it, from
drifting away from the method that produced it.

Questions that need only the method's own arithmetic are asked of synthetic
series and files, and cost nothing. The ones that ask what the control path
does run it once, on first use, and share the run.
"""

import copy
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(EMULATION_DIR, ".."))
REPOSITORY_DIR = os.path.abspath(os.path.join(FIRMWARE_DIR, ".."))

sys.path.insert(0, os.path.join(EMULATION_DIR, "tools"))

import run_casting_peak as casting  # noqa: E402
import run_cross_tier_check as cross_tier  # noqa: E402
import run_parameter_sweep as sweep  # noqa: E402

#: The controller boards' figures record, which quotes the peaks and keeps the
#: proof-of-life removal interval pending.
FIGURES_RECORD = os.path.join(REPOSITORY_DIR, "docs", "sunbeam-em7000",
                              "controller-board-design-constraints.md")

#: How far a regenerated figure may sit from the committed one before the
#: committed record is out of date rather than merely rounded differently. The
#: analysis is deterministic on one host and need not be across hosts, because
#: the plant model's arithmetic reaches the platform's own maths library; a
#: tenth of a kelvin is the last digit the record is written to.
FIGURE_TOLERANCE_C = 0.15

FINDINGS = None


def _findings():
    """The whole analysis, run on first use and shared."""
    global FINDINGS
    if FINDINGS is None:
        FINDINGS = casting.run_once()
    return FINDINGS


def _text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _committed_record():
    return _text(casting.REPORT_PATH)


def _inputs():
    """The files the committed record was generated from, as the method reads
    them by default, without running it."""
    description, limits = cross_tier.carried_declarations()
    return [description, limits, sweep.TOLERANCE_DECLARATION, sweep.STEAM_CONTROL_DECLARATION]


def _runs(side):
    return [run for run in _findings()["runs"] if run["side"] == side]


class ThePeakIsFoundAcrossEveryPhaseAndEveryCorner(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the highest casting temperature
    the plant model reaches while the controller holds a heater, found across
    every operating phase the controller commands and across the declared
    corners of the model's coefficients.
    """

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: found across every operating
    # phase the controller commands: warm-up from a cold machine, holding at it
    # with no draw until settled, each delivery that heater serves, recovery
    # after each delivery, and each delivery started back-to-back after each of
    # its deliveries. The phases partition the run, so no interval is left out
    # of the peak by belonging to none, and each run goes through them in order.
    def test_every_phase_is_run_for_each_thermoblock_and_the_phases_cover_every_interval(self):
        for side in (casting.COFFEE, casting.STEAM):
            for run in _runs(side):
                with self.subTest(side=side, kind=run["kind"], corner=run["corner"] and
                                  run["corner"]["which"]):
                    phases = run["phases"]
                    self.assertEqual(0, phases[0]["start"])
                    self.assertEqual(run["intervals"], phases[-1]["end"])
                    for before, after in zip(phases, phases[1:]):
                        self.assertEqual(before["end"], after["start"],
                                         "the phases leave an interval in none of them")
                    names = [phase["phase"] for phase in phases]
                    self.assertEqual(
                        [casting.WARM_UP, casting.HOLD], names[:2],
                        "a run begins cold and must come to rest before its first delivery")
                    expected = [casting.DELIVERY, casting.RECOVERY, casting.DELIVERY,
                                casting.BACK_TO_BACK, casting.RECOVERY_AFTER_BACK_TO_BACK]
                    self.assertEqual(expected * len(run["levels"]), names[2:])
                    for index, level in enumerate(run["levels"]):
                        block = phases[2 + index * len(expected):2 + (index + 1) * len(expected)]
                        for phase in block:
                            if phase["phase"] in (casting.DELIVERY, casting.BACK_TO_BACK):
                                self.assertEqual(level, phase["level"])
                            else:
                                self.assertEqual(0, phase["level"])

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: each delivery that heater serves
    # (coffee and hot water on the coffee thermoblock, a steam draw on the steam
    # thermoblock), each heater on its own.
    def test_each_delivery_a_heater_serves_is_run_on_that_heater_alone(self):
        self.assertEqual({casting.COFFEE, casting.HOT_WATER},
                         {run["kind"] for run in _runs(casting.COFFEE)})
        self.assertEqual({casting.STEAM}, {run["kind"] for run in _runs(casting.STEAM)})
        self.assertEqual(set(casting.COFFEE_LEVELS),
                         {phase["level"] for run in _runs(casting.COFFEE)
                          for phase in run["phases"] if phase["phase"] == casting.DELIVERY})
        self.assertGreater(len(set(casting.COFFEE_LEVELS)), 1,
                           "a delivery at one pump level cannot show the recovery getting "
                           "hotter as the heater spends longer at its limit")

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the corners are the control
    # path's own enumeration: each end of each coefficient carrying a declared
    # error, run on its own, plus each stated joint corner.
    def test_the_corners_run_are_the_control_paths_own_enumeration(self):
        found = _findings()
        for side, enumerated in ((casting.COFFEE, found["shipped"]["corners"]),
                                 (casting.STEAM, found["shipped"]["steam_corners"])):
            ran = {corner["which"] for corner in enumerated if corner["ran"]}
            refused = {corner["which"] for refused_side, corner, _ in found["refused"]
                       if refused_side == side}
            self.assertEqual(ran, {run["corner"]["which"] for run in _runs(side)
                                   if run["corner"] is not None},
                             "a corner the enumeration covers was not run, or one it does not "
                             "cover was")
            self.assertEqual({corner["which"] for corner in enumerated} - ran, refused,
                             "a corner that was not run is not accounted for as refused")
            self.assertTrue(any(corner["joint"] for corner in enumerated),
                            "the enumeration carries no joint corner to run")
            self.assertEqual(len({run["kind"] for run in _runs(side)}),
                             len([run for run in _runs(side) if run["corner"] is None]),
                             "the machine at the declared coefficients is run once for each "
                             "delivery it serves, and not otherwise")

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the corners are run as machines,
    # not as labels. The coffee casting's thermal mass at its low end heats
    # faster under the same heater and runs further past the target; a run whose
    # corner machine was the declared one would report the same peak.
    def test_a_corner_is_run_as_the_machine_it_names(self):
        by_corner = {}
        for run in _runs(casting.COFFEE):
            if run["kind"] != casting.COFFEE:
                continue
            key = "nominal" if run["corner"] is None else (
                tuple(run["corner"]["writes"]), run["corner"]["end"])
            by_corner[key] = run
        low_mass = by_corner[(("brew.thermal_mass_j_per_k",), "low")]
        high_mass = by_corner[(("brew.thermal_mass_j_per_k",), "high")]
        nominal = by_corner["nominal"]
        self.assertGreater(low_mass["peak_c"], nominal["peak_c"] + 1.0)
        self.assertLess(high_mass["peak_c"], nominal["peak_c"] - 1.0)

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the figure is the worst single
    # corner. It is one run's peak, and not a sum of what each corner adds to
    # the declared machine's.
    def test_the_figure_is_the_worst_single_corner_and_not_a_sum(self):
        for side in (casting.COFFEE, casting.STEAM):
            runs = _runs(side)
            figure = _findings()["figures"][side]
            self.assertEqual(max(run["peak_c"] for run in runs), figure["peak_c"])
            self.assertIn(figure["peak_c"], [run["peak_c"] for run in runs])
            nominal = next(run for run in runs if run["corner"] is None)
            additions = [run["peak_c"] - nominal["peak_c"] for run in runs
                         if run["kind"] == nominal["kind"] and run["peak_c"] > nominal["peak_c"]]
            self.assertGreater(len(additions), 1, "fewer than two corners add anything")
            self.assertLess(figure["peak_c"], nominal["peak_c"] + sum(additions),
                            "the figure is as large as every corner's addition summed")

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: a worst corner is chosen by peak
    # whichever way the runs are ordered, and ties are broken by order.
    def test_the_worst_run_is_the_highest_wherever_it_falls(self):
        runs = [{"peak_c": peak, "at": at} for at, peak in enumerate((3.0, 9.0, 4.0, 9.0, 1.0))]
        self.assertEqual(1, casting.worst_run(runs)["at"])
        self.assertEqual(3, casting.worst_run(list(reversed(runs)))["at"])
        self.assertEqual(0, casting.worst_run(runs[:1])["at"])
        with self.assertRaises(casting.CastingError):
            casting.worst_run([])


class EachDeliveryIsCommandedAtTheHighestTargetTheControlPathAdmits(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: at the highest target its
    control path admits for each delivery it serves, read from the control
    path's own admission rather than chosen.
    """

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the coffee target is the one the
    # loop's own admission narrows to, and the loop does refuse a target above
    # it: a draw commanded at the boiling point it stops at is refused outright.
    def test_the_coffee_target_is_the_highest_the_loop_admits_and_nothing_above_it(self):
        found = _findings()
        executable, description, limits = found["executable"], found["description"], found["limits"]
        for run in _runs(casting.COFFEE):
            if run["kind"] == casting.COFFEE:
                self.assertEqual(found["shipped"]["target_c"], run["target_c"])
        scale = cross_tier.converter_scale()
        ceiling = found["shipped"]["target_c"]
        # A target the loop admits runs.
        sweep.brew_draw(executable, description, limits, [(sweep.INTERVAL_MS, 0)] * 10, scale,
                        "casting-peak-test-admitted", control_description=description,
                        target_c=ceiling)
        # The boiling point it stops just short of is refused before the draw
        # begins.
        self.assertLess(ceiling, 100.0)
        self.assertGreater(ceiling, 100.0 - 0.001)
        with self.assertRaises(cross_tier.CrossTierError):
            sweep.brew_draw(executable, description, limits, [(sweep.INTERVAL_MS, 0)] * 10,
                            scale, "casting-peak-test-refused", control_description=description,
                            target_c=100.0)

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: hot water is served at the
    # drinking point, whose window the control path refuses a target at or above
    # the ceiling of. The target is read out of the declaration that states the
    # ceiling, so a replacement declaration moves it, and it is the number just
    # under the ceiling, which the loop's single-precision comparison admits.
    def test_the_hot_water_target_is_read_from_the_declared_drinking_ceiling(self):
        found = _findings()
        ceiling = casting.drinking_ceiling_c(found["tolerance"])
        target = found["coffee_targets"][casting.HOT_WATER]
        self.assertLess(target, ceiling)
        self.assertGreater(target, ceiling - 0.001)
        self.assertEqual(casting.float32_below(ceiling), target)
        for run in _runs(casting.COFFEE):
            if run["kind"] == casting.HOT_WATER:
                self.assertEqual(target, run["target_c"])

        with tempfile.TemporaryDirectory() as directory:
            elsewhere = os.path.join(directory, "tolerance.declaration")
            with open(found["tolerance"], encoding="utf-8") as handle:
                text = handle.read()
            replaced = re.sub(r"(drinking-temperature-ceiling\s*=\s*)\d+", r"\g<1>90000", text)
            self.assertNotEqual(text, replaced)
            with open(elsewhere, "w", encoding="utf-8") as handle:
                handle.write(replaced)
            moved = casting.targets_admitted(found["shipped"], elsewhere)
            self.assertEqual(casting.float32_below(90.0), moved[casting.HOT_WATER])
            self.assertEqual(found["shipped"]["target_c"], moved[casting.COFFEE])

    def test_the_largest_single_precision_number_below_a_figure_is_the_next_one_down(self):
        import struct
        for value in (96.0, 100.0, 90.0, 1.0):
            below = casting.float32_below(value)
            self.assertLess(below, value)
            self.assertEqual(value, struct.unpack("<f", struct.pack("<f", value))[0])
            self.assertEqual(
                struct.unpack("<I", struct.pack("<f", value))[0] - 1,
                struct.unpack("<I", struct.pack("<f", below))[0])

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the steam target is the highest
    # ready temperature the steam loop comes up at, and the loop does not come up
    # above it. No machine is run at more than the machine at the declared
    # coefficients admits, since the shipped loop commands no more.
    def test_the_steam_target_is_the_highest_the_loop_comes_up_at_and_it_refuses_above(self):
        found = _findings()
        highest = found["shipped"]["steam_highest_c"]
        runs = _runs(casting.STEAM)
        nominal = next(run for run in runs if run["corner"] is None)
        self.assertEqual(highest, nominal["target_c"])
        self.assertTrue(all(run["target_c"] <= highest for run in runs))
        self.assertGreater(highest, found["shipped"]["steam_ready_c"],
                           "the highest target is no higher than the declared one, so the "
                           "run is not at the highest the loop admits")

        scale = [(sweep.INTERVAL_MS, 0)] * 10
        with tempfile.TemporaryDirectory() as directory:
            def drawn(ready_c):
                declaration = casting.declaration_with_ready_temperature(
                    found["declaration"], int(round(ready_c * 1000.0)),
                    os.path.join(directory, "steam-%d.declaration" % int(ready_c * 1000)))
                return sweep.steam_draw(found["executable"], found["description"],
                                        found["limits"], declaration, 20.0, scale,
                                        "casting-peak-test-steam")
            self.assertTrue(drawn(highest)["completed"])
            with self.assertRaises(sweep.SweepError):
                drawn(highest + 0.5)

    def test_a_declaration_without_a_ready_temperature_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "empty.declaration")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write("# nothing declared here\n")
            with self.assertRaises(casting.CastingError):
                casting.declaration_with_ready_temperature(
                    source, 125000, os.path.join(directory, "out.declaration"))


class TheDeclaredSensingErrorIsAddedToTheCastingTheRunsReport(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: each loop's declared sensing
    error is then added to the casting temperature the runs report, as a
    simultaneous degradation, and the figure reported for each thermoblock is
    that sum, with the sensing error it carries stated beside it.
    """

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the figure is the peak plus the
    # sensing error the control path's own margin carries for that loop.
    def test_the_figure_is_the_peak_plus_each_loops_declared_sensing_error(self):
        found = _findings()
        carried = {casting.COFFEE: found["shipped"]["margin"]["sensing_error_c"],
                   casting.STEAM: found["shipped"]["steam_margin"]["sensing_error_c"]}
        for side in (casting.COFFEE, casting.STEAM):
            figure = found["figures"][side]
            self.assertGreater(carried[side], 0.0, "the loop declares no sensing error")
            self.assertEqual(carried[side], figure["sensing_error_c"])
            self.assertAlmostEqual(figure["peak_c"] + carried[side], figure["figure_c"], places=6)
            self.assertGreater(figure["figure_c"], max(run["peak_c"] for run in _runs(side)))

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: and the record states the
    # sensing error beside the figure it carries.
    def test_the_record_states_the_sensing_error_beside_the_figure(self):
        rows = {row[0]: row for row in casting.figure_rows(_committed_record())}
        found = _findings()
        for side, label in ((casting.COFFEE, "Coffee thermoblock"),
                            (casting.STEAM, "Steam thermoblock")):
            peak, sensing, total = (float(cell) for cell in rows[label][1:4])
            self.assertAlmostEqual(found["figures"][side]["sensing_error_c"], sensing, places=6)
            self.assertAlmostEqual(peak + sensing, total, places=6)


class ThePeakIsTakenOverEveryReportedCastingTemperature(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the peak is taken over every
    casting temperature the runs report, once per control interval, and a test
    fails if the extraction reports a peak lower than any of them.
    """

    def _short_drawn(self):
        """A coffee draw and a steam draw, kept with the artefact's own output."""
        found = _findings()
        course = [(sweep.INTERVAL_MS, 0)] * 6000
        coffee = sweep.brew_draw(found["executable"], found["description"], found["limits"],
                                 course, cross_tier.converter_scale(), "casting-peak-test-short",
                                 control_description=found["description"],
                                 target_c=found["coffee_targets"][casting.COFFEE])
        steam = sweep.steam_draw(found["executable"], found["description"], found["limits"],
                                 found["declaration"], 20.0, course + [(sweep.INTERVAL_MS, 1000)]
                                 * 500, "casting-peak-test-short-steam")
        return (("brew-c", coffee), ("steam-c", steam))

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the extraction is held against
    # what the artefact printed, line by line, read independently of the parsing
    # the runs go through; and the same comparison fails for an extraction that
    # samples the series or reports its first interval.
    def test_the_extraction_is_not_lower_than_any_casting_temperature_reported(self):
        def agrees(extract, series, reported):
            self.assertEqual(len(reported), len(series))
            return extract(series)[0] >= max(reported)

        def sampled(series):
            return casting.peak_of(series[::50])

        def the_first(series):
            return series[0], 0

        for channel, drawn in self._short_drawn():
            with self.subTest(channel=channel):
                series = drawn["channels"][channel]
                reported = casting.reported_castings(drawn["stdout"], channel)
                self.assertTrue(agrees(casting.peak_of, series, reported))
                peak, at = casting.peak_of(series)
                self.assertEqual(max(reported), peak)
                self.assertEqual(peak, series[at])
                for broken in (sampled, the_first):
                    self.assertFalse(
                        agrees(broken, series, reported),
                        "a comparison of the extraction with what was reported does not notice "
                        "an extraction that misses intervals")

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: and one that stops short of the
    # last interval, or starts after the first, is caught by the same comparison
    # when the hot interval is the one it drops.
    def test_an_extraction_that_drops_an_end_of_the_series_is_caught(self):
        def without_the_last(series):
            return casting.peak_of(series[:-1])

        def without_the_first(series):
            return casting.peak_of(series[1:])

        for at in (0, 9):
            series = [20.0] * 10
            series[at] = 140.0
            self.assertEqual((140.0, at), casting.peak_of(series))
            broken = without_the_last if at == 9 else without_the_first
            self.assertLess(broken(series)[0], max(series))

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: and the extraction finds a
    # single hot interval wherever in a series it falls, over a window or over
    # all of it.
    def test_a_single_hot_interval_is_found_wherever_it_falls(self):
        for length in (2, 7, 1000):
            for at in sorted({0, 1, length // 2, length - 1}):
                series = [20.0] * length
                series[at] = 99.5
                with self.subTest(length=length, at=at):
                    self.assertEqual((99.5, at), casting.peak_of(series))
                    self.assertEqual((99.5, at), casting.peak_of(series, max(0, at - 1),
                                                                  min(length, at + 2)))
        self.assertEqual((5.0, 2), casting.peak_of([5.0, 1.0, 5.0], 1, 3))
        self.assertEqual((5.0, 0), casting.peak_of([5.0, 5.0]))
        with self.assertRaises(casting.CastingError):
            casting.peak_of([1.0, 2.0], 2, 2)
        with self.assertRaises(casting.CastingError):
            casting.peak_of([])

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: every run's peak is the highest
    # of its phases', and the thermoblock's is the highest of its runs'.
    def test_a_runs_peak_is_the_highest_of_its_phases(self):
        for run in _findings()["runs"]:
            with self.subTest(side=run["side"], kind=run["kind"],
                              corner=run["corner"] and run["corner"]["which"]):
                self.assertEqual(max(phase["peak_c"] for phase in run["phases"]), run["peak_c"])
                phase = next(found for found in run["phases"]
                             if found["start"] <= run["peak_at"] < found["end"])
                self.assertEqual(phase["phase"], run["peak_phase"])
                self.assertEqual(run["peak_c"], phase["peak_c"])


class TheSteamPeakIsReportedAgainstHowLongTheWandIsHeldOpen(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the highest casting temperature
    the plant model reaches while the controller holds that heater is found
    across every operating phase the controller commands -- and a steam draw has
    no end of its own, so the length it was run for is reported with the figure.
    """

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the record gives the peak for
    # the draw every corner was run with and for longer ones, and the claim it
    # makes in words -- that the casting climbs once a draw is held longer than
    # the feed can replace -- is one the figures bear out, so the sentence cannot
    # outlive the behaviour.
    def test_the_steam_peak_climbs_when_the_draw_is_held_longer(self):
        found = _findings()
        lengths = found["steam_lengths"]
        self.assertEqual(list(casting.STEAM_DRAW_SECONDS), [seconds for seconds, _ in lengths])
        peaks = [peak for _, peak in lengths]
        self.assertTrue(all(longer >= shorter for shorter, longer in zip(peaks, peaks[1:])),
                        "a longer draw reports a lower peak than a shorter one: %s" % peaks)
        self.assertGreater(peaks[-1], peaks[0] + 10.0,
                           "the steam peak no longer climbs with the draw, so the record's "
                           "account of a casting that does not settle is out of date: %s" % peaks)
        nominal = next(run for run in _runs(casting.STEAM) if run["corner"] is None)
        draw = next(phase for phase in nominal["phases"] if phase["phase"] == casting.DELIVERY)
        self.assertAlmostEqual(peaks[0], draw["peak_c"], delta=FIGURE_TOLERANCE_C)

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: and what the record gives is what
    # the method presently produces.
    def test_the_committed_draw_length_table_is_the_one_this_method_presently_produces(self):
        was = casting.length_rows(_committed_record())
        now = _findings()["steam_lengths"]
        self.assertEqual([str(seconds) for seconds, _ in now], [row[0] for row in was])
        for (seconds, peak), row in zip(now, was):
            self.assertAlmostEqual(peak, float(row[1]), delta=FIGURE_TOLERANCE_C)


class ASettledWindowIsOneThatHasComeToRest(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: warm-up from a cold machine to
    the commanded figure; holding at it with no draw until settled; and recovery
    after each delivery, continued until the casting has passed its
    post-delivery maximum and settled back to its holding value.
    """

    def _course(self, hold, delivery, recovery):
        return casting.course_of((300,), hold, delivery, recovery)

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: a run that rose past its holding
    # value and came back to it has settled, and its warm-up ends where it came
    # to rest for good.
    def test_a_run_that_overshoots_and_returns_has_settled_where_it_came_to_rest(self):
        tail = 50
        steps, windows = self._course(hold=400, delivery=100, recovery=300)
        series = [20.0 + 80.0 * min(1.0, at / 100.0) for at in range(400)]
        series[100:200] = [100.0 + 30.0 * (1.0 - (at - 100) / 100.0) for at in range(100, 200)]
        series[200:400] = [100.0] * 200
        for window in windows[1:]:
            length = window["end"] - window["start"]
            if window["phase"].startswith(casting.RECOVERY):
                series.extend([100.0 + 20.0 * max(0.0, 1.0 - at / 100.0) for at in range(length)])
            else:
                series.extend([60.0] * length)
        phases, problems, hold_c = casting.analyse(series, windows, band=0.25, tail=tail)
        self.assertEqual([], problems)
        self.assertAlmostEqual(100.0, hold_c)
        warm, hold = phases[0], phases[1]
        self.assertEqual(casting.WARM_UP, warm["phase"])
        self.assertEqual(casting.HOLD, hold["phase"])
        self.assertEqual(200, warm["end"])
        self.assertEqual(130.0, warm["peak_c"])
        self.assertEqual(100.0, hold["peak_c"])

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: a hold still moving at its end
    # has not settled, and the run is refused rather than reported over it.
    def test_a_hold_still_moving_at_its_end_is_not_settled(self):
        steps, windows = self._course(hold=400, delivery=100, recovery=300)
        series = [20.0 + 0.2 * at for at in range(windows[0]["end"])]
        for window in windows[1:]:
            series.extend([series[-1]] * (window["end"] - window["start"]))
        _, problems, _ = casting.analyse(series, windows, band=0.25, tail=50)
        self.assertTrue(any("come to rest" in problem for problem in problems), problems)

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: a recovery whose casting is
    # still rising at its end has not passed its post-delivery maximum, and one
    # that has passed it but not come back to the holding value has not settled
    # back to it. Neither is reported as a recovery.
    def test_a_recovery_that_has_not_passed_its_maximum_or_come_back_is_not_settled(self):
        steps, windows = self._course(hold=400, delivery=100, recovery=300)
        tail = 50

        def built(recovery_values):
            series = [100.0] * windows[0]["end"]
            for window in windows[1:]:
                length = window["end"] - window["start"]
                if window["phase"] == casting.RECOVERY:
                    series.extend(recovery_values(length))
                elif window["phase"].startswith(casting.RECOVERY):
                    series.extend([100.0] * length)
                else:
                    series.extend([60.0] * length)
            return series

        rising = built(lambda length: [100.0 + 0.1 * at for at in range(length)])
        _, problems, _ = casting.analyse(rising, windows, band=0.25, tail=tail)
        self.assertTrue(any("still rising" in problem for problem in problems), problems)

        high = built(lambda length: [105.0 - 0.0 * at for at in range(length)])
        _, problems, _ = casting.analyse(high, windows, band=0.25, tail=tail)
        self.assertTrue(any("not settled back" in problem for problem in problems), problems)

        settled = built(lambda length: [100.0 + 30.0 * max(0.0, 1.0 - at / 100.0)
                                        for at in range(length)])
        phases, problems, _ = casting.analyse(settled, windows, band=0.25, tail=tail)
        self.assertEqual([], problems)
        recovery = next(phase for phase in phases if phase["phase"] == casting.RECOVERY)
        self.assertEqual(130.0, recovery["peak_c"])

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: each delivery is started on the
    # interval after the last one ends, and the course keeps every window of
    # every level in order.
    def test_the_second_delivery_follows_the_first_on_the_next_interval(self):
        steps, windows = casting.course_of((300, 1000), 400, 100, 300)
        self.assertEqual(len(steps), windows[-1]["end"])
        starts = [window for window in windows if window["phase"] == casting.DELIVERY]
        followers = [window for window in windows if window["phase"] == casting.BACK_TO_BACK]
        self.assertEqual(4, len(starts))
        self.assertEqual(2, len(followers))
        for follower in followers:
            lead = next(window for window in windows if window["end"] == follower["start"])
            self.assertEqual(casting.DELIVERY, lead["phase"])
            self.assertEqual(lead["level"], follower["level"])
        self.assertTrue(all(level == 0 for level in steps[:400]))
        for window in windows:
            if window["phase"].startswith(casting.RECOVERY):
                self.assertTrue(all(level == 0 for level in steps[window["start"]:window["end"]]))
            if window["phase"] in (casting.DELIVERY, casting.BACK_TO_BACK):
                self.assertTrue(all(level == window["level"]
                                    for level in steps[window["start"]:window["end"]]))

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: a run that has not settled is
    # lengthened and run again, and refused if it still has not settled at the
    # longest, rather than reported over a recovery that had not finished.
    def test_an_unsettled_run_is_lengthened_and_then_refused(self):
        calls = []

        def never_settles(course):
            calls.append(len(course))
            return {"channels": {"x": [20.0 + 0.01 * at for at in range(len(course))]},
                    "stdout": ""}
        with self.assertRaises(casting.CastingError):
            casting.run_phased(never_settles, (300,), 1500, 200, 1200, "x")
        self.assertEqual(len(casting.LENGTHENINGS), len(calls))
        self.assertTrue(all(longer > shorter for shorter, longer in zip(calls, calls[1:])))

        second = len(casting.course_of((300,), 1500 * 2, 200, 1200 * 2)[0])

        def settles_when_long(course):
            length = len(course)
            if length < second:
                return {"channels": {"x": [20.0 + 0.01 * at for at in range(length)]},
                        "stdout": ""}
            return {"channels": {"x": [100.0] * length}, "stdout": ""}
        result = casting.run_phased(settles_when_long, (300,), 1500, 200, 1200, "x")
        self.assertEqual(2, result["lengthened"])
        self.assertEqual(100.0, result["peak_c"])


class TheGeneratedRecordIsCommittedAndKeptCurrent(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the figure is reported with the
    phase and corner that produce it, graded inferred from the model, in a
    generated record that states the command regenerating it and prints the
    sha256 of each input it was generated from, and a test fails when that
    record is stale.
    """

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: reported with the phase and
    # corner that produce it, graded inferred, in a record that says it is
    # generated and states the command regenerating it.
    def test_the_committed_record_says_it_is_generated_and_carries_every_section(self):
        record = _committed_record()
        self.assertIn("run_casting_peak.py", record)
        self.assertIn("Do not edit by hand", record)
        self.assertIn(casting.REGENERATE_COMMAND, record)
        for heading in (casting.RUNS_HEADING, casting.FIGURES_HEADING, casting.PHASES_HEADING,
                        casting.CORNERS_HEADING, casting.REFUSED_HEADING):
            self.assertIn(heading, record)
        self.assertIn("inferred", record)
        rows = casting.figure_rows(record)
        self.assertEqual(["Coffee thermoblock", "Steam thermoblock"], [row[0] for row in rows])
        for row in rows:
            self.assertIn(row[4], casting.PHASES)
            self.assertRegex(row[5], r"^(nominal|\d+)$")

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: prints the sha256 of each input
    # it was generated from; and the record is stale when any of them has
    # changed, a comment included.
    def test_the_committed_record_prints_the_digest_of_each_input_as_it_stands(self):
        record = _committed_record()
        for path in _inputs():
            with self.subTest(path=path):
                self.assertIn(casting._relative(path), record)
                self.assertIn(sweep.digest_of(path), record,
                              "%s has changed since the record was taken. Re-run %s"
                              % (path, casting.REGENERATE_COMMAND))
        self.assertEqual([], casting.stale_inputs(record, _inputs()))

    def test_a_changed_input_makes_the_record_stale(self):
        record = _committed_record()
        with tempfile.TemporaryDirectory() as directory:
            for path in _inputs():
                with self.subTest(path=os.path.basename(path)):
                    copied = os.path.join(directory, os.path.basename(path))
                    shutil.copyfile(path, copied)
                    record_of_copy = record.replace(sweep.digest_of(path), sweep.digest_of(copied))
                    self.assertEqual([], casting.stale_inputs(record_of_copy, [copied]))
                    with open(copied, "a", encoding="utf-8") as handle:
                        handle.write("# a comment changes nothing a run reads, and still\n")
                    self.assertEqual([copied], casting.stale_inputs(record_of_copy, [copied]))

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the committed record is the one
    # this method presently produces: the figure, the phase and corner that
    # produce it, and every corner's peak, not only the headline.
    def test_the_committed_figures_are_the_ones_this_method_presently_produces(self):
        found = _findings()
        record = _committed_record()
        rows = {row[0]: row for row in casting.figure_rows(record)}
        for side, label in ((casting.COFFEE, "Coffee thermoblock"),
                            (casting.STEAM, "Steam thermoblock")):
            figure = found["figures"][side]
            row = rows[label]
            corner = figure["run"]["corner"]
            with self.subTest(side=side):
                self.assertAlmostEqual(figure["peak_c"], float(row[1]), delta=FIGURE_TOLERANCE_C,
                                       msg="the committed peak differs from the one this method "
                                           "now produces. Re-run %s" % casting.REGENERATE_COMMAND)
                self.assertAlmostEqual(figure["figure_c"], float(row[3]),
                                       delta=FIGURE_TOLERANCE_C)
                self.assertEqual(figure["run"]["peak_phase"], row[4])
                self.assertEqual("nominal" if corner is None else str(corner["which"]), row[5])
                self.assertEqual(figure["run"]["kind"], row[6])

    def test_the_committed_corner_table_is_the_one_this_method_presently_produces(self):
        found = _findings()
        was = casting.corner_rows(_committed_record())
        self.assertEqual(len(found["runs"]), len(was),
                         "the committed record covers a different set of runs. Re-run %s"
                         % casting.REGENERATE_COMMAND)
        for run, row in zip(found["runs"], was):
            corner = run["corner"]
            with self.subTest(side=run["side"], kind=run["kind"],
                              corner=corner and corner["which"]):
                self.assertEqual(("Coffee" if run["side"] == casting.COFFEE else "Steam",
                                  run["kind"],
                                  "nominal" if corner is None else str(corner["which"])),
                                 (row[0], row[1], row[3]))
                self.assertAlmostEqual(run["peak_c"], float(row[9]), delta=FIGURE_TOLERANCE_C)
                self.assertAlmostEqual(run["target_c"], float(row[2]), delta=FIGURE_TOLERANCE_C)
                self.assertEqual(run["peak_phase"], row[10])

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: and every phase is in the
    # per-phase table for each thermoblock.
    def test_the_committed_record_gives_the_hottest_of_every_phase_for_each_thermoblock(self):
        rows = casting.phase_rows(_committed_record())
        for label in ("Coffee thermoblock", "Steam thermoblock"):
            self.assertEqual(list(casting.PHASES),
                             [row[1] for row in rows if row[0] == label])
        for label in ("Coffee thermoblock", "Steam thermoblock"):
            figure = float(next(row for row in casting.figure_rows(_committed_record())
                                if row[0] == label)[1])
            self.assertAlmostEqual(figure, max(float(row[2]) for row in rows
                                               if row[0] == label and row[2] != casting.NOTHING),
                                   places=6)

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: pointing the method at a
    # replacement description changes the record it writes, with nothing here
    # edited: the digest of the file it was run against is the one it prints.
    def test_the_record_a_run_writes_names_the_files_it_was_given(self):
        found = _findings()
        written = casting.report_text(found)
        for path in casting.input_paths(found):
            self.assertIn(sweep.digest_of(path), written)
        with tempfile.TemporaryDirectory() as directory:
            elsewhere = os.path.join(directory, "other.params")
            shutil.copyfile(found["description"], elsewhere)
            with open(elsewhere, "a", encoding="utf-8") as handle:
                handle.write("# a replacement\n")
            replaced = copy.copy(found)
            replaced["description"] = elsewhere
            replaced["digests"] = dict(found["digests"])
            replaced["digests"][elsewhere] = sweep.digest_of(elsewhere)
            text = casting.report_text(replaced)
            self.assertIn(sweep.digest_of(elsewhere), text)
            self.assertNotIn(sweep.digest_of(found["description"]), text)


def _disagreements(figures_text, record_text):
    """Every thermoblock whose peak the figures record quotes differently from
    the generated record's."""
    quoted = casting.quoted_peaks(figures_text)
    generated = {row[0]: row for row in casting.figure_rows(record_text)}
    differing = []
    for side, label in ((casting.COFFEE, "Coffee thermoblock"),
                        (casting.STEAM, "Steam thermoblock")):
        if side not in quoted:
            differing.append((side, "the figures record quotes no peak"))
        elif quoted[side] != tuple(generated[label][1:4]):
            differing.append((side, "quotes %s where the record gives %s"
                              % (quoted[side], tuple(generated[label][1:4]))))
    return differing


class TheFiguresRecordQuotesThePeakTheGeneratedRecordGives(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: a test fails if the peak the
    figures record quotes for either thermoblock differs from the generated
    record's.
    """

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the peak, the sensing error
    # carried and their sum, for both thermoblocks.
    def test_the_figures_record_quotes_the_peak_the_generated_record_gives(self):
        self.assertEqual([], _disagreements(_text(FIGURES_RECORD), _committed_record()))

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: and the comparison notices a
    # quote that has drifted, a quote removed, and a record that has moved on.
    def test_a_quote_that_differs_or_is_missing_is_noticed(self):
        figures = _text(FIGURES_RECORD)
        record = _committed_record()
        quoted = casting.quoted_peaks(figures)
        for side in (casting.COFFEE, casting.STEAM):
            peak = quoted[side][0]
            drifted = figures.replace("| %s | %s |" % (peak, quoted[side][1]),
                                      "| %s | %s |" % ("%.1f" % (float(peak) + 0.1),
                                                       quoted[side][1]), 1)
            self.assertNotEqual(figures, drifted)
            self.assertEqual([side], [found[0] for found in _disagreements(drifted, record)])

        removed = "\n".join(line for line in figures.splitlines()
                            if not line.startswith("| Steam thermoblock | " + quoted[casting.STEAM][0]))
        self.assertEqual([casting.STEAM], [found[0] for found in _disagreements(removed, record)])

        moved = record.replace("| Coffee thermoblock | %s |" % quoted[casting.COFFEE][0],
                               "| Coffee thermoblock | %.1f |" % (float(quoted[casting.COFFEE][0])
                                                                    + 1.0), 1)
        self.assertNotEqual(record, moved)
        self.assertEqual([casting.COFFEE], [found[0] for found in _disagreements(figures, moved)])


SIBLING = "SOL-PROOF-OF-LIFE-INTERVAL-DERIVED-FROM-HELD-CASTING-PEAK"


def _interval_row(text):
    """The figures record's row for the proof-of-life removal interval, as its
    cells, or None when there is no such row."""
    for line in text.splitlines():
        if line.startswith("| Proof-of-life removal interval | **"):
            return [cell.strip() for cell in line.strip().strip("|").split("|")]
    return None


def _interval_problems(figures_text):
    """Every way the figures record fails to keep the interval pending against
    the work that settles it, or presents a time as a figure."""
    problems = []
    row = _interval_row(figures_text)
    if row is None:
        return ["the figures record has no pending row for the interval"]
    if not row[1].startswith("**Pending**"):
        problems.append("the interval is not marked pending")
    if SIBLING not in row[1]:
        problems.append("the interval is not pending against %s" % SIBLING)
    if re.search(r"-?\d+(\.\d+)? s\b", row[1]):
        problems.append("the pending row states a time")
    for trip, start in re.findall(r"(?m)^- (?:Coffee|Steam): .*?\(([0-9.]+) − ([0-9.]+)\) K",
                                  figures_text):
        if float(start) > float(trip):
            problems.append("the record works a time from a start above the trip point")
    registers = [line for line in figures_text.splitlines()
                 if line.startswith("| Proof-of-life removal interval | ")
                 and not line.startswith("| Proof-of-life removal interval | **")]
    if not any(SIBLING in line for line in registers):
        problems.append("the pending-marks register does not list the interval against %s"
                        % SIBLING)
    return problems


class TheFiguresRecordKeepsTheIntervalPendingWhileTheCastingExceedsItsTrip(unittest.TestCase):
    """SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1 stops at the peak: the interval
    is derived by the sibling solution once the control holds the casting, so
    the figures record must keep it pending until then.
    """

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the figures record quotes the
    # peak and still marks the interval pending against the sibling solution,
    # and presents no time as a figure.
    def test_the_interval_is_pending_against_the_sibling_solution(self):
        self.assertEqual([], _interval_problems(_text(FIGURES_RECORD)))

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: and the check notices each way
    # the record could stop saying so.
    def test_the_check_notices_a_derived_interval_or_a_lost_pending_mark(self):
        figures = _text(FIGURES_RECORD)
        row = next(line for line in figures.splitlines()
                   if line.startswith("| Proof-of-life removal interval | **Pending**"))
        mutations = {
            "the pending mark removed": figures.replace(row, row.replace("**Pending**", "**Derived**", 1), 1),
            "the sibling named no longer": figures.replace(SIBLING, "SOL-OTHER", 1),
            "a time stated in the row": figures.replace(row, row.replace(
                "**Pending**", "**Pending** (-8.2 s)", 1), 1),
            "the arithmetic shown": figures + "\n- Coffee: 192 J/K × (107 − 158.8) K = −9946 J; "
                                             "−9946 J / 1215 W = −8.2 s.\n",
            "the row removed": figures.replace(row, "", 1),
            "the register entry removed": "\n".join(
                line for line in figures.splitlines()
                if not (line.startswith("| Proof-of-life removal interval | The control")
                        and SIBLING in line)),
        }
        for name, mutated in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(figures, mutated)
                self.assertTrue(_interval_problems(mutated),
                                "the check does not notice %s" % name)

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the finding the figures record
    # states reads the generated record's own peaks, for both thermoblocks and the
    # steam draw length.
    def test_the_finding_states_the_peaks_the_generated_record_gives(self):
        figures = _text(FIGURES_RECORD)
        record = _committed_record()
        generated = {row[0]: row for row in casting.figure_rows(record)}
        finding = next(line for line in figures.splitlines()
                       if line.startswith("**Finding: no interval can be derived"))
        for label in ("Coffee thermoblock", "Steam thermoblock"):
            for figure in generated[label][1:4]:
                self.assertIn("%s °C" % figure, finding)
        self.assertIn("DEL-CASTING-MARGIN-HELD-IN-EVERY-PHASE", finding)
        self.assertIn("20-second", finding)
        self.assertIn("Nothing in this finding is a board figure", finding)

        drifted = finding.replace("%s °C" % generated["Steam thermoblock"][1],
                                  "%.1f °C" % (float(generated["Steam thermoblock"][1]) + 0.1), 1)
        self.assertNotEqual(finding, drifted)
        self.assertNotIn("%s °C" % generated["Steam thermoblock"][1], drifted)


class TheGeneratedRecordSaysWhatItsPeaksAre(unittest.TestCase):
    """The record is diagnostic: its peaks are those of the control as shipped."""

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the committed record opens with
    # the banner the generator writes, so a record read alone is not taken for a
    # board input.
    def test_the_committed_record_carries_the_generators_banner(self):
        record = _committed_record()
        self.assertIn(casting.BANNER, record)
        head = record.split("## ", 2)[0]
        self.assertIn("control as it shipped", head)
        self.assertIn("not a board input", head)
        self.assertIn("draw length", head)

    # SOL-CASTING-PEAK-UNDER-CONTROL-DERIVED.C1: the banner comes from the
    # generator's template for any findings, so a regeneration cannot drop it.
    def test_the_generated_text_carries_the_banner(self):
        self.assertIn(casting.BANNER, casting.report_text(_findings()))


if __name__ == "__main__":
    unittest.main()
