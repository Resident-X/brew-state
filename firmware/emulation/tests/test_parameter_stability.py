"""What the stability analysis has to have shown before its verdicts count as
evidence that this machine's closed loops stay bounded across the error its
description declares.

The corners happen once for the whole suite, on the terms the two suites beside
this one are written on: two host draws per corner over courses several times the
length of the sweep's own is the most expensive thing in this tier, and every
assertion below reads what that run produced rather than reaching for the loops
itself.

Six assertions cost real draws of their own and each is deliberate. One runs a
corner at a horizon deliberately too short, because a horizon that is long enough
and one that has never been shown to be long enough read the same from a table of
verdicts. One runs the upper corner of a coefficient this description declares
one-sided -- a machine the description does not claim, run here and nowhere else
-- because on this model every corner the description does claim settles, and a
detector that has never been seen to say otherwise on the real apparatus is not a
detector. One runs the whole method against a description the shipped one is not,
because a method that can only be pointed at one model cannot be shown repeatable
against a replacement. One re-runs a coefficient's own corner to establish that
the joint corner is not that corner under another name.

And two put a corner the machine's own loader really refuses through the paths
that have to record it rather than raise: one through the whole method, against a
description declaring an error wide enough that a corner of it is no longer a
machine of this architecture, and one through the joint corner in particular,
which is the path that claimed to be admitted on the same terms as the others
while it was not. Neither can be shown with an exception raised on purpose: what
has to be established is that the structure's own refusal reaches the record.

The verdict logic itself is exercised against synthetic separations as well as
against this machine's. All three verdicts have to be reachable and told apart,
and this model presently produces one of them -- a suite that asserted only what
this model does would leave the other two implemented and never run, and would
pass over an implementation that could not produce them at all.

Nothing here asks whether the verdicts are right about a real machine. They
cannot be: the model they were taken against is estimated throughout, and the
solution's own text puts a measured model out of scope until one exists.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, "..", "tools"))
FIRMWARE_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
REPOSITORY_DIR = os.path.abspath(os.path.join(FIRMWARE_DIR, ".."))
sys.path.insert(0, TOOLS)

import run_cross_tier_check as cross_tier  # noqa: E402
import run_parameter_stability as stability  # noqa: E402
import run_parameter_sweep as sweep  # noqa: E402

FINDINGS = None

# The coefficient whose corner is re-run at a horizon deliberately too short.
# The one whose declared error produces the widest excursion on the coffee side
# and therefore the slowest recovery, so a horizon that is too short for anything
# is too short for this -- and a check taken on a coefficient that settles inside
# the first few seconds would pass whatever the horizon was.
SLOWEST_COEFFICIENT = "pump.flow_ml_per_s"

# The corner the detector is put to on the real apparatus, and it is deliberately
# one the analysis itself will not run: the upper end of a coefficient the
# description declares reaches downwards only. It is a machine the description
# does not claim, which is exactly why the analysis leaves it out -- and exactly
# why it is available here, since on the corners the description does claim this
# model settles everywhere and there would otherwise be nothing on the real
# machinery for the failure path to be shown against.
EXCLUDED_UPPER_CORNER = "pump.flow_ml_per_s"

# A coefficient this suite writes differently to make a description that is a
# different machine and still a machine, borrowed from the two suites beside this
# one for the same purpose: the figure the reference machine's owner recalls the
# coffee element being, which the description records as displaced by a bench
# measurement rather than an invented value.
REPLACEMENT_COEFFICIENT = "brew.heater_power_w"
REPLACEMENT_VALUE = "1200.0"

# How far a regenerated figure may sit from the committed one before the
# committed record is out of date rather than merely rounded differently.
#
# The relative part is the one the two suites beside this one already use, and
# for the reason they give: the analysis is deterministic on one host and need
# not be across hosts, because the plant model's arithmetic reaches the
# platform's own maths library. What is added here is an absolute floor, because
# these figures are separations in a delivery's own unit and run from millionths
# to several kelvin -- a purely relative tolerance would demand agreement to
# eight decimal places on a figure that means nothing. The floor is a hundredth
# of one count of the machine's own converter, which is the coarsest thing either
# of the two tests a verdict is taken on can turn on: a figure agreeing to that
# cannot move a verdict.
FIGURE_TOLERANCE = 0.01


def setUpModule():
    global FINDINGS
    FINDINGS = stability.run_once()


def _committed_record():
    with open(stability.REPORT_PATH, encoding="utf-8") as handle:
        return handle.read()


def _produced_record():
    return stability.report_text(FINDINGS)


def _near(before, after, floor):
    """Whether a committed figure and a regenerated one are the same figure."""
    return abs(before - after) <= FIGURE_TOLERANCE * max(abs(after), floor)


def _corner(coefficient, corner):
    for record in FINDINGS["corners"]:
        if record["coefficient"] == coefficient and record["corner"] == corner:
            return record
    raise AssertionError("the analysis ran no %s corner of %s" % (corner, coefficient))


def _corners_of(coefficient):
    return sorted(record["corner"] for record in FINDINGS["corners"]
                  if record["coefficient"] == coefficient)


def _covered():
    """What the description declares an error against, read through the sweep's
    own reader rather than off what this analysis says it ran."""
    return sweep.swept_coefficients(FINDINGS["description"])[0]


def _perturbed_lines(path, reference):
    """Which lines one written description differs from the reference on."""
    with open(path, encoding="utf-8") as handle:
        written = handle.read().splitlines()
    return [(reference[at], written[at]) for at in range(min(len(reference), len(written)))
            if reference[at].strip() != written[at].strip()]


def _value_on(line):
    return float(line.split("=", 1)[1].split()[0])


def _reference_lines():
    with open(FINDINGS["description"], encoding="utf-8") as handle:
        return handle.read().splitlines()


def _with_declared_errors(errors, destination, source=None):
    """A description with one or more coefficients' declared errors written
    differently, and every value left where it stands.

    Written here rather than borrowed, because the rewrite the tools share moves
    a coefficient's value and carries its account of itself -- including the
    error -- across untouched, which is exactly right for running a corner and
    exactly wrong for asking what a wider declared error would make this analysis
    do. What is wanted is the same machine with the description claiming to be
    more wrong about it than it does, so that a corner the declared error implies
    lands outside what the structure will admit as a machine at all.
    """
    source = source or FINDINGS["description"]
    with open(source, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    rewritten = []
    for line in lines:
        head, separator, tail = line.partition("=")
        name = head.strip()
        if separator and name in errors:
            value, marker, account = tail.partition("~")
            if not marker:
                raise AssertionError("%s declares no error against '%s' to widen" % (source, name))
            account = account.strip()
            at = account.find("@")
            rewritten.append("%s =%s~ %g %s" % (name, value, errors[name],
                                                account[at:] if at >= 0 else ""))
        else:
            rewritten.append(line)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rewritten) + "\n")
    return destination


def _flat(value, length):
    """A separation series that does not change."""
    return [value] * length


def _series(early, late, length):
    """A separation series whose two halves reach two stated worst cases.

    Built as two flat halves rather than as a decay or a ramp, because what the
    settle determination reads is the worst case in each half and a shape between
    them would leave an assertion depending on where the two windows happened to
    fall. The reference is a series of zeros, so the separation is the series
    itself.
    """
    at = length - length // 2
    return [early] * at + [late] * (length - at)


class EveryDeclaredErrorIsRunToItsCornersAndCheckedForSettling(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: Every parameter
    carrying a declared error is run to its corners and checked for a response
    that settles within the delivery's own tolerance band, not only a bounded
    deviation.
    """

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: every parameter
    # carrying a declared error -- established against the description's own
    # reader rather than against the list of what this analysis says it ran. An
    # analysis that dropped a coefficient and then reported the coefficients it
    # had run would agree with itself perfectly.
    def test_every_coefficient_carrying_a_declared_error_was_run(self):
        carrying = set(name for name, _, _ in _covered())
        self.assertTrue(
            carrying,
            "the description carries no declared error at all, so this suite is asserting about "
            "an empty set and would pass over an analysis that ran nothing")
        ran = set(record["coefficient"] for record in FINDINGS["corners"]
                  if not record["joint"])
        self.assertEqual(
            ran, carrying,
            "the coefficients run to their corners are not the coefficients the description "
            "declares an error against")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: run to its corners
    # -- one coefficient moved, by exactly the declared error, and nothing else
    # touched. Read back off the descriptions the runs were actually handed. An
    # analysis moving two coefficients at once, or moving one by something other
    # than its declared error, is the failure that leaves every verdict
    # meaningless while the run still completes.
    def test_each_corner_moved_exactly_one_coefficient_by_its_declared_error(self):
        reference = _reference_lines()
        declared = dict((name, (nominal, fraction)) for name, nominal, fraction in _covered())
        for record in FINDINGS["corners"]:
            if record["joint"]:
                continue
            nominal, fraction = declared[record["coefficient"]]
            factor = 1.0 - fraction if record["corner"] == "low" else 1.0 + fraction
            with self.subTest(coefficient=record["coefficient"], corner=record["corner"]):
                differing = _perturbed_lines(record["description"], reference)
                self.assertEqual(
                    len(differing), 1,
                    "the %s corner of %s differs from the reference description on %d lines, so "
                    "more than one coefficient moved"
                    % (record["corner"], record["coefficient"], len(differing)))
                self.assertTrue(differing[0][1].startswith(record["coefficient"]))
                self.assertAlmostEqual(
                    _value_on(differing[0][1]), nominal * factor, places=4,
                    msg="the %s corner of %s was not written at the value its declared error of "
                        "%g "
                        "implies" % (record["corner"], record["coefficient"], fraction))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: to its corners --
    # both of them where the declared error has two, and the one declared end
    # where the description says it reaches in one direction only. Both halves
    # are asserted, and the census of one-sided coefficients is asserted against
    # this description rather than taken from the record: a name that has gone
    # stale would otherwise leave this analysis running both corners of something
    # the record still claims it ran one of, and nothing would say so.
    def test_a_one_sided_coefficient_is_run_at_its_one_declared_end_and_others_at_both(self):
        self.assertEqual(
            sorted(FINDINGS["one_sided_found"]), sorted(stability.ONE_SIDED),
            "this description does not carry every coefficient recorded as one-sided, so the "
            "record of which they are has gone stale against the machine it is about")
        self.assertEqual(FINDINGS["one_sided_missing"], [])

        for name, _, _ in _covered():
            with self.subTest(coefficient=name):
                if name in stability.ONE_SIDED:
                    self.assertEqual(
                        _corners_of(name), [stability.ONE_SIDED[name]],
                        "%s is declared as reaching in one direction only and was run at more "
                        "than that one corner, so a machine the description does not claim was "
                        "put through the loop" % name)
                else:
                    self.assertEqual(
                        _corners_of(name), ["high", "low"],
                        "%s carries a two-sided declared error and was not run at both ends of "
                        "it, so half its declared range is unchecked" % name)

        # And a record naming a direction that is not a corner at all has to be
        # refused rather than leaving the coefficient run at nothing, which would
        # take its whole declared range out of the analysis while every census
        # above went on passing.
        name, nominal, fraction = _covered()[0]
        was = stability.ONE_SIDED
        try:
            stability.ONE_SIDED = dict(was, **{name: "sideways"})
            with self.assertRaises(stability.StabilityError) as refused:
                stability.corners_of(name, nominal, fraction)
        finally:
            stability.ONE_SIDED = was
        self.assertIn("left unchecked", str(refused.exception))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1 and .C4: the two
    # departures from a plain two-sided sweep -- which coefficients reach in one
    # direction only, and which two move together -- are facts stated in
    # firmware/params/thermoblock.md's prose and nowhere else. The description's
    # grammar carries a value, an error and an origin, and has nowhere to put
    # either claim, so the tool holds them in tables of its own.
    #
    # Nothing structural ties those tables to the prose they came from, and
    # nothing can: a fourth coefficient declared one-sided in that prose, or a
    # value or fraction moved under one of these five lines, would leave this
    # analysis running the old assumption and reporting it as current. This is
    # the tripwire. It pins what the live description presently says about each
    # of the five, read through the sweep's own reader, so any movement fails
    # here rather than being carried silently into a record that claims to be
    # about the machine as described.
    #
    # The sag the joint corner is run at falls out of two of these figures and is
    # pinned with them: it is the smaller of the two element errors, so it is the
    # coffee element's own declared error and not the steam element's -- which is
    # why the coffee side has a like-for-like comparison against the joint corner
    # and the steam side has none.
    def test_the_prose_facts_these_tables_encode_are_what_the_description_still_says(self):
        pinned = {
            "pump.pressure_bar": (15.0, 0.4),
            "pump.flow_ml_per_s": (7.0, 0.6),
            "steam.feed_flow_ml_per_s": (3.0, 0.7),
            "brew.heater_power_w": (1004.0, 0.1),
            "steam.heater_power_w": (1126.0, 0.15),
        }
        self.assertEqual(
            sorted(pinned), sorted(set(stability.ONE_SIDED) | set(stability.MAINS_COUPLED)),
            "the coefficients this tool holds prose facts about are not the ones pinned here, so "
            "a claim read out of firmware/params/thermoblock.md has been added to or dropped from "
            "a table with nothing checking it against the description")

        declared = dict((name, (nominal, fraction))
                        for name, nominal, fraction in _covered())
        for name, (nominal, fraction) in sorted(pinned.items()):
            with self.subTest(coefficient=name):
                self.assertIn(
                    name, declared,
                    "the description no longer declares an error against `%s`, which this tool "
                    "carries a prose fact about" % name)
                self.assertAlmostEqual(
                    declared[name][0], nominal, places=6,
                    msg="`%s` is now stated as %g rather than the %g this tool's account of it "
                        "was written against. Re-read what firmware/params/thermoblock.md says "
                        "about it before updating this figure"
                        % (name, declared[name][0], nominal))
                self.assertAlmostEqual(
                    declared[name][1], fraction, places=9,
                    msg="`%s` now declares an error of %g rather than %g. Which corners this "
                        "analysis runs, and what the joint corner's sag is, both follow from "
                        "these fractions" % (name, declared[name][1], fraction))

        coupled = [declared[name][1] for name in stability.MAINS_COUPLED]
        self.assertAlmostEqual(FINDINGS["joint"]["fraction"], min(coupled), places=9)
        self.assertAlmostEqual(
            FINDINGS["joint"]["fraction"],
            declared[stability.MAINS_COUPLED_BY_SIDE[sweep.BREW_SIDE]][1], places=9,
            msg="the joint corner's sag is no longer the coffee element's own declared error, so "
                "which side has a like-for-like comparison against it has moved")
        self.assertNotAlmostEqual(
            FINDINGS["joint"]["fraction"],
            declared[stability.MAINS_COUPLED_BY_SIDE[sweep.STEAM_SIDE]][1], places=9,
            msg="the two elements now declare the same error, so both sides would have a "
                "comparable independent corner and the record's account of why one does not has "
                "gone stale")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: checked for a
    # response that settles, not only a bounded deviation. This is the whole of
    # what separates this analysis from the dominance record beside it, and it
    # cannot be shown from this model's own corners because they all settle. Two
    # separations of exactly the same size are put to the determination, one
    # falling and one growing, and they have to come back different: a check that
    # read only how far the delivery moved could not tell them apart at all.
    def test_two_separations_of_the_same_size_are_told_apart_by_whether_they_settle(self):
        window = list(range(0, 400))
        band, floor = 1.0, 0.01
        reference = _flat(0.0, 400)

        falling = stability.settle_of(reference, _series(0.5, 0.2, 400), window, band, floor)
        growing = stability.settle_of(reference, _series(0.2, 0.5, 400), window, band, floor)
        self.assertEqual(
            falling["worst"], growing["worst"],
            "the two synthetic responses do not reach the same worst separation, so this "
            "assertion is not about the distinction it exists to make")
        self.assertEqual(falling["verdict"], stability.SETTLED)
        self.assertEqual(
            growing["verdict"], stability.STILL_DIVERGING,
            "a separation still growing at the horizon was called settled, which is the one "
            "conclusion a deviation figure alone would already have reached")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: within the
    # delivery's own tolerance band -- the band decides, and it is that side's
    # own. Put to the determination twice around one separation, so a band
    # compiled in as a constant, or read off the other side, fails here.
    def test_the_band_the_verdict_turns_on_is_the_one_it_is_given(self):
        window = list(range(0, 200))
        reference = _flat(0.0, 200)
        separation = _flat(0.5, 200)
        inside = stability.settle_of(reference, separation, window, 0.6, 0.01)
        outside = stability.settle_of(reference, separation, window, 0.4, 0.01)
        self.assertEqual(inside["verdict"], stability.SETTLED)
        self.assertEqual(
            outside["verdict"], stability.SETTLED_OUTSIDE_THE_BAND,
            "the same separation was called settled inside a band narrower than itself, so the "
            "band is not what the verdict turns on")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: within the
    # delivery's own tolerance band -- each side's own, each over its own side's
    # extension. The two bands and the two windows are asserted against the
    # declarations and the courses they come from, because a verdict taken with
    # the wrong side's band, or over the window belonging to the other side's
    # course, would be a plausible-looking table about nothing.
    def test_each_side_is_judged_over_its_own_extension_against_its_own_band(self):
        self.assertAlmostEqual(FINDINGS["bands"][sweep.BREW_SIDE],
                               sweep.brew_band_c(FINDINGS["tolerance"]), places=9)
        self.assertAlmostEqual(FINDINGS["bands"][sweep.STEAM_SIDE],
                               sweep.steam_band_bar(FINDINGS["declaration"]), places=9)
        self.assertNotAlmostEqual(
            FINDINGS["bands"][sweep.BREW_SIDE], FINDINGS["bands"][sweep.STEAM_SIDE], places=3,
            msg="the two sides are held to the same figure, so a verdict taken with the wrong "
                "side's band would pass every assertion here")

        for side, ends, tail, course in (
                (sweep.BREW_SIDE, stability.brew_hold_ends_at(FINDINGS["tails"][sweep.BREW_SIDE]),
                 FINDINGS["tails"][sweep.BREW_SIDE], FINDINGS["courses"][sweep.BREW_SIDE]),
                (sweep.STEAM_SIDE,
                 stability.steam_draw_ends_at(FINDINGS["tails"][sweep.STEAM_SIDE]),
                 FINDINGS["tails"][sweep.STEAM_SIDE], FINDINGS["courses"][sweep.STEAM_SIDE])):
            first, last = FINDINGS["windows"][side]
            with self.subTest(side=side):
                self.assertEqual(last, ends - 1)
                self.assertEqual(
                    last - first + 1, int(round(tail * stability.SETTLING_WINDOW_FRACTION)),
                    "the %s side's verdict window is not the trailing part of its "
                    "extension" % side)
                self.assertTrue(
                    all(course[at][1] > 0 for at in range(first, last + 1)),
                    "the %s side's verdict window covers an interval nothing was being delivered "
                    "on, so the band it is judged against does not apply there" % side)
                self.assertEqual(
                    len(FINDINGS["reference"][side]["delivered"]), len(course),
                    "the %s side's reference run does not cover the course it was given" % side)

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: run to a horizon
    # long enough to show whether the response settles. A horizon that is long
    # enough and one that has never been shown to be long enough produce the same
    # table, so the slowest corner on this model is re-run at a horizon
    # deliberately too short and required to come back unsettled there while it
    # settles at the committed one. Without this the horizon could be shortened
    # to nothing and every assertion in this suite would still pass.
    def test_a_horizon_too_short_reaches_the_opposite_verdict_on_the_slowest_corner(self):
        settled = _corner(SLOWEST_COEFFICIENT, stability.ONE_SIDED[SLOWEST_COEFFICIENT])
        self.assertEqual(settled["sides"][sweep.BREW_SIDE]["verdict"], stability.SETTLED)

        short = sweep.BREW_FLUSH_STEPS
        course = stability.brew_course(short)
        window = stability.settling_window(stability.brew_hold_ends_at(short), short)
        runs = [sweep.brew_draw(FINDINGS["executable"], description, FINDINGS["limits"], course,
                                FINDINGS["converter_scale"], "stability-short-%s" % label)
                for label, description in (("nominal", FINDINGS["description"]),
                                           ("corner", settled["description"]))]
        hurried = stability.settle_of(runs[0]["delivered"], runs[1]["delivered"], window,
                                      FINDINGS["bands"][sweep.BREW_SIDE],
                                      FINDINGS["floors"][sweep.BREW_SIDE])
        self.assertNotEqual(
            hurried["verdict"], stability.SETTLED,
            "%s's corner is reported as settled over a horizon a fifteenth of the committed one, "
            "so nothing establishes that the committed horizon is doing any work and it could be "
            "shortened to nothing without this suite noticing" % SLOWEST_COEFFICIENT)

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: a horizon long
    # enough -- which the record has to be able to say of itself rather than
    # leaving a reader to trust it. Every settling corner has to have been inside
    # its band well before the verdict window opens, and the margin is what says
    # how well. A margin creeping up on the window's own edge is a horizon that
    # has quietly become too short for a model that moved.
    def test_the_horizon_leaves_every_settling_corner_inside_the_band_before_the_window(self):
        for side, (fraction, coefficient, corner) in stability.horizon_margin(FINDINGS).items():
            with self.subTest(side=side):
                self.assertLess(
                    fraction, stability.SETTLING_WINDOW_FRACTION,
                    "on the %s side the latest a settling corner stood outside its band was %g of "
                    "the extension, at or past the %g the verdict window opens at — so %s's %s "
                    "corner is being called settled on a horizon that barely reached it"
                    % (side, fraction, stability.SETTLING_WINDOW_FRACTION, coefficient, corner))
        self.assertGreater(
            stability.horizon_margin(FINDINGS)[sweep.BREW_SIDE][0], 0.0,
            "no corner ever left the coffee side's band anywhere in the extension, so this run is "
            "no evidence that the horizon is long enough for one that does")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: checked against the
    # delivery's own band -- which is only a comparison at all if the machine the
    # corners are compared against had itself settled. A reference still
    # travelling would leave every separation below a comparison of two
    # transients, and the table would look exactly the same. Both sides' refusals
    # are put to it, because either could fail on its own.
    def test_a_reference_that_had_not_settled_stops_the_analysis(self):
        windows = dict((side, list(range(first, last + 1)))
                       for side, (first, last) in FINDINGS["windows"].items())
        as_run = dict((side, {"delivered": list(run["delivered"])})
                      for side, run in FINDINGS["reference"].items())
        stability.reference_delivers_in_band(as_run, windows, FINDINGS["bands"],
                                             FINDINGS["declaration"])

        adrift = dict((side, {"delivered": list(run["delivered"])})
                      for side, run in FINDINGS["reference"].items())
        for at in windows[sweep.BREW_SIDE]:
            adrift[sweep.BREW_SIDE]["delivered"][at] = sweep.BREW_TARGET_C + 10.0
        with self.assertRaises(stability.StabilityError) as refused:
            stability.reference_delivers_in_band(adrift, windows, FINDINGS["bands"],
                                                 FINDINGS["declaration"])
        self.assertIn("had not settled", str(refused.exception))

        adrift = dict((side, {"delivered": list(run["delivered"])})
                      for side, run in FINDINGS["reference"].items())
        for at in windows[sweep.STEAM_SIDE]:
            adrift[sweep.STEAM_SIDE]["delivered"][at] = 0.0
        with self.assertRaises(stability.StabilityError) as steam_refused:
            stability.reference_delivers_in_band(adrift, windows, FINDINGS["bands"],
                                                 FINDINGS["declaration"])
        self.assertIn("bar band", str(steam_refused.exception))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: within the
    # delivery's own tolerance band -- which a separation from the reference only
    # stands in for where the reference is itself near the target. Somewhere
    # inside the band is not enough and is what this guard asked for first: a
    # reference on one edge and a corner on the other are a band apart, the
    # separation between them reads as one band, and the corner is called settled
    # while both deliveries are marginal. So a reference inside its band and off
    # the target by more than the stated fraction of it has to be refused, on
    # both sides, and every figure below turns on that having been established.
    def test_a_reference_inside_its_band_but_far_off_target_is_refused(self):
        windows = dict((side, list(range(first, last + 1)))
                       for side, (first, last) in FINDINGS["windows"].items())
        bands = FINDINGS["bands"]
        allowed = stability.REFERENCE_CENTRED_WITHIN
        self.assertLess(allowed, 1.0, "the guard admits a reference anywhere inside its band, "
                                      "which is the bound this test exists to say is not enough")

        # The coffee side, put just inside the band and well off the commanded
        # temperature. The old guard admitted this and every verdict taken
        # against it would have been a comparison with a machine most of a band
        # from where the design puts it.
        off = dict((side, {"delivered": list(run["delivered"])})
                   for side, run in FINDINGS["reference"].items())
        edge = sweep.BREW_TARGET_C + bands[sweep.BREW_SIDE] * (1.0 + allowed) / 2.0
        self.assertLess(abs(edge - sweep.BREW_TARGET_C), bands[sweep.BREW_SIDE],
                        "the doctored reference is outside the band, so this is the refusal the "
                        "guard beside this one already makes")
        for at in windows[sweep.BREW_SIDE]:
            off[sweep.BREW_SIDE]["delivered"][at] = edge
        with self.assertRaises(stability.StabilityError) as refused:
            stability.reference_delivers_in_band(off, windows, bands, FINDINGS["declaration"])
        self.assertIn("too far off the target", str(refused.exception))

        # The steam side, put just inside the declared span and near its ceiling.
        settled = FINDINGS["reference_settled"]
        middle = settled["steam_middle"]
        off = dict((side, {"delivered": list(run["delivered"])})
                   for side, run in FINDINGS["reference"].items())
        near_edge = middle + bands[sweep.STEAM_SIDE] * (1.0 + allowed) / 2.0
        self.assertLess(near_edge, settled["steam_ceiling"],
                        "the doctored steam reference is outside the declared span, so this is "
                        "the refusal the guard beside this one already makes")
        for at in windows[sweep.STEAM_SIDE]:
            off[sweep.STEAM_SIDE]["delivered"][at] = near_edge
        with self.assertRaises(stability.StabilityError) as steam_refused:
            stability.reference_delivers_in_band(off, windows, bands, FINDINGS["declaration"])
        self.assertIn("too far off the target", str(steam_refused.exception))

        # And the machine the committed verdicts were taken against passes it
        # with room in hand, which is what makes the fraction a guard against a
        # model that moved rather than one fitted to this one.
        for side, distance in ((sweep.BREW_SIDE, settled["brew_worst_from_target"]),
                               (sweep.STEAM_SIDE, settled["steam_worst_from_middle"])):
            with self.subTest(side=side):
                self.assertLess(
                    distance, allowed * bands[side],
                    "the unperturbed machine sits %g from the middle of the %s side's band, "
                    "which is at or past the %g of it this analysis requires -- the verdicts "
                    "were taken against a reference the guard was written to refuse"
                    % (distance, side, allowed))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: across the declared
    # error and not beyond it, which is the standard the robustness declaration
    # states rather than one this analysis chose. The class is required to be
    # read from that declaration rather than written into the tool, and a
    # declaration classifying the behaviour otherwise -- or not at all -- has to
    # stop the analysis, because corners drawn from a declared range cannot
    # establish a behaviour that has to hold however wrong the model is.
    def test_the_standard_is_read_from_the_robustness_declaration_and_a_change_stops_the_run(self):
        carried, bounded = stability.declared_class()
        self.assertEqual(carried, bounded)
        self.assertEqual(FINDINGS["robustness_class"], carried)

        with open(stability.ROBUSTNESS_DECLARATION, encoding="utf-8") as handle:
            text = handle.read()
        words, problems = stability.robustness.load_vocabulary(sweep.INCLUDE_DIR)
        self.assertIsNotNone(words, problems)
        other = [word for kind, word in words.items() if kind != stability.BOUNDED]
        self.assertTrue(other, "the vocabulary declares only one class, so a reclassification "
                               "cannot be put to this")

        promoted = os.path.join(FINDINGS["workspace"], "promoted.declaration")
        with open(promoted, "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"^%s\s*=.*$" % re.escape(stability.THE_BEHAVIOUR),
                                "%s = %s" % (stability.THE_BEHAVIOUR, other[0]), text,
                                flags=re.MULTILINE))
        with self.assertRaises(stability.StabilityError) as reclassified:
            stability.bounded_or_refuse(promoted)
        self.assertIn(stability.THE_BEHAVIOUR, str(reclassified.exception))

        silent = os.path.join(FINDINGS["workspace"], "silent.declaration")
        with open(silent, "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"^%s\s*=.*$" % re.escape(stability.THE_BEHAVIOUR), "", text,
                                flags=re.MULTILINE))
        with self.assertRaises(stability.StabilityError) as unclassified:
            stability.bounded_or_refuse(silent)
        self.assertIn("not declared anywhere", str(unclassified.exception))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C1: run to a horizon --
    # one this description answers for. The steam block climbs for as long as a
    # wand is held open, and past the temperature the machine's own protection
    # takes over at this description's saturation relation is a quarter of the
    # truth. A run that went there has to stop the analysis rather than produce a
    # verdict, and the bound has to be the one the grammar declares rather than a
    # number written into the tool.
    def test_a_horizon_carrying_the_steam_block_past_what_the_description_answers_for_stops_it(
            self):
        ceiling = stability.steam_block_ceiling_c()
        self.assertEqual(FINDINGS["steam_block_ceiling_c"], ceiling)
        self.assertLess(
            FINDINGS["steam_block_peak_c"], ceiling,
            "the committed horizon already carries a steam block past what the description "
            "answers for, so the verdicts above were taken in a regime it cannot be believed in")
        stability._under_the_ceiling(ceiling - 1.0, ceiling, "a run")
        with self.assertRaises(stability.StabilityError) as past:
            stability._under_the_ceiling(ceiling + 1.0, ceiling, "a run")
        self.assertIn("protection", str(past.exception))

        elsewhere = os.path.join(FINDINGS["workspace"], "elsewhere-grammar.c")
        with open(elsewhere, "w", encoding="utf-8") as handle:
            handle.write("#define %s 150000\n" % stability.STEAM_BLOCK_CEILING_MACRO)
        self.assertAlmostEqual(stability.steam_block_ceiling_c(elsewhere), 150.0, places=9)

        headless = os.path.join(FINDINGS["workspace"], "headless-grammar.c")
        with open(headless, "w", encoding="utf-8") as handle:
            handle.write("/* no bound here */\n")
        with self.assertRaises(stability.StabilityError) as unreadable:
            stability.steam_block_ceiling_c(headless)
        self.assertIn(stability.STEAM_BLOCK_CEILING_MACRO, str(unreadable.exception))


class ACornerThatFailsToSettleIsNamedAsAnInstabilityFinding(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: A corner that fails
    to settle is reported as an instability finding distinct from the existing
    deviation measure.
    """

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: a corner that fails
    # to settle -- which it can do in two different ways, and both have to be
    # reachable and named apart. A response still growing needs a different loop;
    # one that has come to rest outside the band needs a wider band or a smaller
    # draw. A record collapsing them into one phrase would leave a reader unable
    # to tell which, and this model produces neither, so both are put to the
    # determination directly.
    def test_the_two_ways_of_failing_are_both_reachable_and_named_apart(self):
        window = list(range(0, 400))
        reference = _flat(0.0, 400)
        floor = 0.01

        growing = stability.settle_of(reference, _series(0.2, 0.9, 400), window, 2.0, floor)
        self.assertEqual(
            growing["verdict"], stability.STILL_DIVERGING,
            "a separation growing across the window was called settled because it was still "
            "inside the band, which is the case the band cannot answer")
        outside = stability.settle_of(reference, _series(0.9, 0.5, 400), window, 0.4, floor)
        self.assertEqual(outside["verdict"], stability.SETTLED_OUTSIDE_THE_BAND)
        self.assertEqual(
            stability.settle_of(reference, _series(0.3, 0.2, 400), window, 0.4,
                                floor)["verdict"],
            stability.SETTLED,
            "nothing came back settled in this run, so an implementation that named everything "
            "unsettled would pass the two assertions above")

        self.assertNotEqual(stability.STILL_DIVERGING, stability.SETTLED_OUTSIDE_THE_BAND)
        for verdict in (stability.STILL_DIVERGING, stability.SETTLED_OUTSIDE_THE_BAND):
            with self.subTest(verdict=verdict):
                self.assertTrue(verdict.startswith("did not settle"))
        self.assertNotIn("did not settle", stability.SETTLED)

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: a corner that fails
    # to settle is reported -- on the real apparatus and not only against
    # synthetic series. On the corners this description claims, this model
    # settles everywhere, so the failure path is shown against a corner the
    # description does not claim: the upper end of a coefficient it declares
    # reaches downwards only, which the analysis itself will not run for exactly
    # that reason. Put through the same lengthened course and the same
    # determination, it has to come back not settled -- otherwise the detector
    # has never been seen to say anything but "settled" on this machinery at all.
    def test_the_detector_reports_a_real_corner_that_does_not_settle(self):
        nominal, fraction = [(nominal, fraction) for name, nominal, fraction in _covered()
                             if name == EXCLUDED_UPPER_CORNER][0]
        self.assertIn(
            EXCLUDED_UPPER_CORNER, stability.ONE_SIDED,
            "%s is no longer declared one-sided, so its upper corner is one the analysis runs "
            "itself and this is no longer a case it excludes" % EXCLUDED_UPPER_CORNER)

        beyond = cross_tier.description_with(
            EXCLUDED_UPPER_CORNER, stability.VALUE_FORMAT % (nominal * (1.0 + fraction)),
            os.path.join(FINDINGS["workspace"], "excluded-upper-corner.params"),
            source=FINDINGS["description"])
        run = sweep.brew_draw(FINDINGS["executable"], beyond, FINDINGS["limits"],
                              FINDINGS["courses"][sweep.BREW_SIDE], FINDINGS["converter_scale"],
                              "stability-excluded-upper-corner")
        first, last = FINDINGS["windows"][sweep.BREW_SIDE]
        settle = stability.settle_of(
            FINDINGS["reference"][sweep.BREW_SIDE]["delivered"], run["delivered"],
            list(range(first, last + 1)), FINDINGS["bands"][sweep.BREW_SIDE],
            FINDINGS["floors"][sweep.BREW_SIDE])
        self.assertEqual(
            settle["verdict"], stability.SETTLED_OUTSIDE_THE_BAND,
            "a corner that leaves the coffee loop drawing more than its element can carry was "
            "reported as %s, so the determination has never been seen to reach any verdict but "
            "settled on a real run" % settle["verdict"])
        self.assertGreater(settle["worst"], FINDINGS["bands"][sweep.BREW_SIDE])

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: an instability
    # finding, which means the growth test has to decide something and has to
    # decide it on a floor read off the machine rather than on exact inequality.
    # Both directions are put to it: a change smaller than one count of the
    # machine's own converter is the loop's command quantisation and not a
    # divergence, and a change larger than one is. A floor of nothing would have
    # this model's own command beat reported as three diverging corners; a floor
    # of anything would have a real divergence called settled.
    def test_the_growth_floor_is_the_seams_own_figure_and_decides_in_both_directions(self):
        counts, milli = cross_tier.converter_scale()
        self.assertAlmostEqual(stability.reading_resolution(),
                               float(milli) / float(counts) / 1000.0, places=12)
        self.assertAlmostEqual(FINDINGS["reading"], stability.reading_resolution(), places=12)

        window = list(range(0, 400))
        reference = _flat(0.0, 400)
        floor = stability.reading_resolution()
        beat = stability.settle_of(reference, _series(0.1, 0.1 + floor / 2.0, 400), window, 1.0,
                                   floor)
        self.assertEqual(
            beat["verdict"], stability.SETTLED,
            "a change smaller than one count of the machine's own converter was reported as "
            "growth, which is what turns this loop's integer command quantisation into an "
            "instability finding")
        real = stability.settle_of(reference, _series(0.1, 0.1 + floor * 2.0, 400), window, 1.0,
                                   floor)
        self.assertEqual(
            real["verdict"], stability.STILL_DIVERGING,
            "a change of two counts was not reported as growth, so the floor has swallowed the "
            "finding it exists to protect")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: an instability
    # finding, which a floor large against the band it is judged beside would
    # swallow. The seam declares one converter full scale for every channel
    # alike, so its count is a figure about the board rather than about either
    # delivery: it is a twentieth of the coffee side's band and a quarter of the
    # steam side's, and a response growing at just under a quarter of the band
    # per half-window is not settled by any reading of the word. So each side's
    # floor is asserted against that side's own band and not only against the
    # seam -- an assertion that the floor is the seam's figure passes at any full
    # scale whatsoever, including one that made the floor half the band.
    def test_each_sides_growth_floor_is_bounded_by_a_fraction_of_that_sides_own_band(self):
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            band = FINDINGS["bands"][side]
            with self.subTest(side=side):
                self.assertLessEqual(
                    FINDINGS["floors"][side], stability.GROWTH_FLOOR_BAND_FRACTION * band,
                    "the %s side calls a change of %g settled, which is more than %g of the %g "
                    "band that side is judged against -- a response growing at that rate spends "
                    "the margin the verdict is about while the verdict says it came to rest"
                    % (side, FINDINGS["floors"][side], stability.GROWTH_FLOOR_BAND_FRACTION,
                       band))
                self.assertLessEqual(FINDINGS["floors"][side], FINDINGS["reading"])
                self.assertAlmostEqual(
                    FINDINGS["floors"][side],
                    min(FINDINGS["reading"], stability.GROWTH_FLOOR_BAND_FRACTION * band),
                    places=12)
                self.assertGreater(FINDINGS["floors"][side], 0.0)

        # And the bound is doing work rather than being a formality on this
        # machine: the steam band is narrow enough that the seam's own count
        # stands well above a twentieth of it, so that side is held by its band
        # and not by the converter. A run in which both sides were held by the
        # seam would be no evidence that the band ever bounds anything.
        self.assertLess(
            FINDINGS["floors"][sweep.STEAM_SIDE], FINDINGS["reading"],
            "the steam side's floor is the seam's own count, so nothing here establishes that a "
            "floor large against a narrow band is bounded at all")
        self.assertAlmostEqual(FINDINGS["floors"][sweep.BREW_SIDE], FINDINGS["reading"], places=12)

        # A verdict actually turns on the difference: a steam response growing by
        # more than its own bounded floor and less than the seam's count is
        # growth here and would have been called settled by the seam's figure.
        window = list(range(0, 400))
        reference = _flat(0.0, 400)
        between = (FINDINGS["floors"][sweep.STEAM_SIDE] + FINDINGS["reading"]) / 2.0
        band = FINDINGS["bands"][sweep.STEAM_SIDE]
        self.assertEqual(
            stability.settle_of(reference, _series(0.01, 0.01 + between, 400), window, band,
                                FINDINGS["floors"][sweep.STEAM_SIDE])["verdict"],
            stability.STILL_DIVERGING)
        self.assertEqual(
            stability.settle_of(reference, _series(0.01, 0.01 + between, 400), window, band,
                                FINDINGS["reading"])["verdict"],
            stability.SETTLED,
            "the seam's own count no longer swallows a steam response growing by %g per "
            "half-window, so this assertion is not about the distinction it exists to make"
            % between)

        # And a side held to no band at all has no fraction to bound a floor by,
        # which is a refusal rather than a floor of nothing.
        with self.assertRaises(stability.StabilityError) as refused:
            stability.growth_floors({sweep.BREW_SIDE: 0.0})
        self.assertIn("no margin", str(refused.exception))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: reported -- which a
    # corner the structure will not admit as a machine has to be too, rather than
    # ending the run. It is a finding about the description's declared error: the
    # error reaches a value at which these equations stop describing a machine of
    # this architecture, and a record of what the declared error implies that
    # stopped there would report nothing at all about the corners that did run.
    #
    # Put to the whole method rather than to the verdict-combining function on
    # its own, and with a refusal the structure really makes rather than a raised
    # exception standing in for one: a description declaring an ambient it may be
    # two and a half times wrong about implies an upper corner above anything the
    # structure admits as a room, and the machine's own loader refuses it. Every
    # part of the path has to hold -- the draw refused, the refusal recorded
    # against that side, the corner's verdict taken from it, and the record
    # naming it -- and none of it is exercised by a synthetic verdict at all.
    def test_a_corner_the_structure_refuses_is_recorded_and_reported_rather_than_stopping_the_run(
            self):
        widened = 2.5
        refusable = "ambient_temperature_c"
        nominal, declared = [(nominal, fraction) for name, nominal, fraction in _covered()
                             if name == refusable][0]
        self.assertLess(declared, 1.0)
        self.assertNotIn(refusable, stability.ONE_SIDED,
                         "%s is declared one-sided, so its upper corner is not run and this test "
                         "has nothing to refuse" % refusable)

        workspace = os.path.join(FINDINGS["workspace"], "refused")
        description = _with_declared_errors(
            {refusable: widened}, os.path.join(workspace, "refusable.params"))
        findings = stability.run(description=description, limits=FINDINGS["limits"],
                                 executable=FINDINGS["executable"], workspace=workspace)

        refused = [record for record in findings["corners"] if record["refused"]]
        self.assertEqual(
            [(record["coefficient"], record["corner"]) for record in refused],
            [(refusable, "high")],
            "the corner the structure refuses is not the one this description's widened error "
            "puts outside what the machine admits, so this run is not about the refusal path")
        record = refused[0]
        self.assertAlmostEqual(record["values"][refusable], nominal * (1.0 + widened), places=6)
        self.assertEqual(
            sorted(record["refused"]), sorted([sweep.BREW_SIDE, sweep.STEAM_SIDE]),
            "a side of a machine the structure refuses came back with a run, so what was judged "
            "is not the description that was written")
        self.assertEqual(record["sides"], {})
        self.assertEqual(record["verdict"], stability.CORNER_REFUSED)
        for side, why in record["refused"].items():
            with self.subTest(side=side):
                self.assertTrue(why, "the %s side records no reason for the refusal, so the "
                                     "record cannot say what the declared error reached" % side)

        # The corner beside it, at the other end of the same widened error, is
        # still a machine and still ran: a run that refused everything would pass
        # every assertion above.
        low = [other for other in findings["corners"]
               if other["coefficient"] == refusable and other["corner"] == "low"][0]
        self.assertEqual(low["refused"], {})
        self.assertEqual(sorted(low["sides"]), sorted([sweep.BREW_SIDE, sweep.STEAM_SIDE]))

        # And it is reported, in both places a reader would look for it.
        named = stability.unsettled(findings)
        self.assertEqual(
            sorted(side for entry, side, _ in named if entry is record),
            sorted([sweep.BREW_SIDE, sweep.STEAM_SIDE]))
        written = stability.report_text(findings)
        self.assertIn(stability.CORNER_REFUSED, written)
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            with self.subTest(side=side):
                self.assertIn("`%s`, high corner, %s side" % (refusable, side), written)

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: distinct from the
    # existing deviation measure, and not folded into it. Three things are asked,
    # each of which a record could fail on its own: this analysis writes its own
    # record rather than into the dominance one, that record carries the verdict
    # vocabulary, and the dominance record carries none of it. A verdict written
    # into the dominance table would be exactly the folding the criterion refuses.
    def test_the_finding_is_committed_apart_from_the_deviation_measure(self):
        self.assertNotEqual(stability.REPORT_PATH, sweep.REPORT_PATH)
        committed = _committed_record()
        with open(sweep.REPORT_PATH, encoding="utf-8") as handle:
            dominance = handle.read()
        for verdict in (stability.SETTLED, stability.SETTLED_OUTSIDE_THE_BAND,
                        stability.STILL_DIVERGING):
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, committed)
                self.assertNotIn(
                    verdict, dominance,
                    "the dominance record carries this analysis's verdicts, so the settling "
                    "finding has been folded into the deviation measure it is meant to be "
                    "distinct from")
        self.assertNotIn(
            stability.VERDICT_HEADING, dominance,
            "the dominance record carries this analysis's verdict table")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: reported -- every
    # corner leaves the analysis with one of the named verdicts, on both sides,
    # and the corner's own verdict is the worse of the two. A corner that settled
    # on one side and not the other has not settled, and an implementation taking
    # either side's own answer would report half of a failure as a success.
    def test_every_corner_leaves_a_verdict_and_the_corners_own_is_the_worse_of_the_two(self):
        named = (stability.SETTLED, stability.SETTLED_OUTSIDE_THE_BAND,
                 stability.STILL_DIVERGING, stability.CORNER_REFUSED)
        for record in FINDINGS["corners"]:
            with self.subTest(coefficient=record["coefficient"], corner=record["corner"]):
                # Every side is accounted for exactly once, either by a verdict
                # or by a refusal. Compared as sets built from both, rather than
                # as two sorted lists laid end to end: that concatenation is not
                # itself sorted, so it would fail or pass on which side happened
                # to be refused rather than on whether both were accounted for.
                self.assertEqual(
                    set(record["sides"]) | set(record["refused"]),
                    {sweep.BREW_SIDE, sweep.STEAM_SIDE},
                    "the %s corner of %s leaves a side neither judged nor recorded as refused"
                    % (record["corner"], record["coefficient"]))
                self.assertFalse(
                    set(record["sides"]) & set(record["refused"]),
                    "a side is both judged and recorded as refused, so one of the two is about a "
                    "run that did not happen")
                for settle in record["sides"].values():
                    self.assertIn(settle["verdict"], named)
                self.assertIn(record["verdict"], named)

        for worse, better in ((stability.STILL_DIVERGING, stability.SETTLED),
                              (stability.SETTLED_OUTSIDE_THE_BAND, stability.SETTLED),
                              (stability.STILL_DIVERGING, stability.SETTLED_OUTSIDE_THE_BAND)):
            for sides in ((worse, better), (better, worse)):
                with self.subTest(sides=sides):
                    self.assertEqual(
                        stability._verdict_of({
                            "sides": dict(zip((sweep.BREW_SIDE, sweep.STEAM_SIDE),
                                              ({"verdict": sides[0]}, {"verdict": sides[1]}))),
                            "refused": {},
                        }),
                        worse,
                        "a corner that reached %s on one side and %s on the other was reported as "
                        "the better of the two" % sides)
        self.assertEqual(
            stability._verdict_of({"sides": {}, "refused": {sweep.BREW_SIDE: "why"}}),
            stability.CORNER_REFUSED)

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C2: reported -- which
    # means the record has to say so when nothing fails as well as when something
    # does. A record that spoke up only where a corner failed would leave a
    # reader unable to tell "every corner settled" from "nobody looked", and
    # those are opposite findings.
    def test_the_record_states_what_did_not_settle_whether_or_not_anything_did(self):
        committed = _committed_record()
        self.assertIn(stability.UNSETTLED_HEADING, committed)
        did_not = stability.unsettled(FINDINGS)
        section = committed.split(stability.UNSETTLED_HEADING, 1)[1].split("\n## ", 1)[0]
        if did_not:
            for record, side, _ in did_not:
                with self.subTest(coefficient=record["coefficient"], side=side):
                    self.assertIn("`%s`, %s corner, %s side" %
                                  (record["coefficient"], record["corner"], side), section)
        else:
            self.assertIn("Every corner settled inside the band on both sides", section)

        # And the account is derived from the verdicts rather than written: a
        # corner whose side failed has to appear there, put to the reader through
        # a record this suite generates rather than the committed one.
        doctored = dict(FINDINGS)
        broken = dict(FINDINGS["corners"][0])
        broken["sides"] = dict((side, dict(settle, verdict=stability.STILL_DIVERGING))
                               for side, settle in broken["sides"].items())
        doctored["corners"] = [broken] + list(FINDINGS["corners"][1:])
        doctored["joint"] = FINDINGS["joint"]
        self.assertIn(
            "`%s`, %s corner" % (broken["coefficient"], broken["corner"]),
            stability.report_text(doctored),
            "a corner reported as diverging is not named under what did not settle, so the "
            "account is not taken off the verdicts")


class TheCornersTheHorizonAndTheVerdictsAreCommitted(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C3: The corners run, the
    horizon used, and the verdict at each corner are committed in a form
    repeatable against a replacement model.
    """

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C3: the corners run and
    # the verdict at each are committed. The committed record has to be the one
    # this method presently produces, corner for corner and figure for figure --
    # a record that has drifted from the method beside it is a set of verdicts
    # nobody can reproduce, which is the whole of what this criterion is about.
    #
    # Every figure and not only the verdict. A check comparing verdicts alone
    # would let each figure in the table drift as far as it liked until one of
    # them happened to cross a threshold, and the figures are what a verdict can
    # be argued with from. The dominance record beside this one went stale in
    # exactly that way once already.
    def test_the_committed_verdicts_are_the_ones_this_method_presently_produces(self):
        was = stability.verdict_rows(_committed_record())
        now = stability.verdict_rows(_produced_record())
        self.assertTrue(was, "%s carries no verdict table" % stability.REPORT_PATH)
        self.assertEqual(
            [(row["coefficient"], row["corner"]) for row in was],
            [(row["coefficient"], row["corner"]) for row in now],
            "the committed record covers a different set of corners, or covers them in a "
            "different order, from the one this analysis now produces. Re-run "
            "firmware/emulation/tools/run_parameter_stability.py")

        for before, after in zip(was, now):
            with self.subTest(coefficient=before["coefficient"], corner=before["corner"]):
                self.assertEqual(before["written_as"], after["written_as"])
                for key in ("brew_verdict", "steam_verdict"):
                    self.assertEqual(before[key], after[key])
                for key in ("brew_early", "brew_late", "steam_early", "steam_late"):
                    if before[key] == "—" or after[key] == "—":
                        self.assertEqual(before[key], after[key])
                        continue
                    self.assertTrue(
                        _near(float(before[key]), float(after[key]), FINDINGS["reading"]),
                        "the committed record gives %s's %s corner a %s of %s and this analysis "
                        "now gives it %s. Re-run "
                        "firmware/emulation/tools/run_parameter_stability.py"
                        % (before["coefficient"], before["corner"], key, before[key], after[key]))

        self.assertEqual(
            [(row["coefficient"], row["corner"]) for row in was],
            [(record["coefficient"], record["corner"]) for record in FINDINGS["corners"]],
            "the committed record does not carry every corner this analysis ran")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C3: the horizon used is
    # committed. The same corners run to a shorter horizon give different
    # verdicts, so a record carrying verdicts and not the horizon they were taken
    # over is one nobody can reproduce -- and the horizon has to be the one this
    # method presently uses rather than a figure somebody wrote once.
    def test_the_committed_record_names_the_horizon_the_verdicts_were_taken_over(self):
        was = dict((row["side"], row) for row in stability.horizon_rows(_committed_record()))
        now = dict((row["side"], row) for row in stability.horizon_rows(_produced_record()))
        self.assertEqual(sorted(was), sorted([sweep.BREW_SIDE, sweep.STEAM_SIDE]))
        self.assertEqual(was, now,
                         "the committed record's horizon is not the one this analysis now runs. "
                         "Re-run firmware/emulation/tools/run_parameter_stability.py")
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            first, last = FINDINGS["windows"][side]
            with self.subTest(side=side):
                self.assertIn("%d intervals" % len(FINDINGS["courses"][side]), was[side]["course"])
                self.assertIn("%d intervals" % FINDINGS["tails"][side], was[side]["extension"])
                self.assertIn("%d–%d" % (first, last), was[side]["window"])
                self.assertIn(stability.FIGURE_FORMAT % FINDINGS["bands"][side], was[side]["band"])

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C3: naming the model the
    # corners were run against. A name alone does not say which machine, because
    # a path can be rewritten under a record that goes on reading as current -- so
    # each of the four files is named with what it presently holds, and the record
    # is out of date the moment any of them moves.
    def test_the_committed_record_names_the_files_it_was_run_against_as_they_stand(self):
        record = _committed_record()
        for path in (FINDINGS["description"], FINDINGS["limits"], FINDINGS["declaration"],
                     FINDINGS["tolerance"], FINDINGS["robustness_declaration"]):
            with self.subTest(file=path):
                self.assertIn(stability._relative(path), record)
        for path in (FINDINGS["description"], FINDINGS["limits"], FINDINGS["declaration"],
                     FINDINGS["tolerance"]):
            with self.subTest(digest=path):
                self.assertIn(
                    sweep.digest_of(path), record,
                    "%s has changed since the committed verdicts were taken against it. Re-run "
                    "firmware/emulation/tools/run_parameter_stability.py"
                    % stability._relative(path))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C3: in a form repeatable
    # against a replacement model, which means re-pointing rather than rewriting.
    # A second machine is written -- the reference description with the coffee
    # element at the figure its owner recalls rather than the measured one -- and
    # the whole method is run against it by argument alone. It has to cover the
    # same corners, name the replacement rather than the shipped description, and
    # come back with figures that moved: a method quietly still reading the
    # original satisfies the first two and not the third.
    def test_the_same_method_run_against_a_replacement_model_needs_no_edit_to_it(self):
        replacement = cross_tier.description_with(
            REPLACEMENT_COEFFICIENT, REPLACEMENT_VALUE,
            os.path.join(FINDINGS["workspace"], "stability-replacement.params"),
            source=FINDINGS["description"])

        elsewhere = stability.run(
            description=replacement, limits=FINDINGS["limits"],
            executable=FINDINGS["executable"],
            workspace=os.path.join(FINDINGS["workspace"], "replacement"))

        self.assertNotEqual(
            elsewhere["workspace"], FINDINGS["workspace"],
            "the replacement model wrote its perturbed descriptions where the shipped machine's "
            "run wrote its own, so one of the two is standing on files the other wrote")
        self.assertEqual(
            [(record["coefficient"], record["corner"]) for record in elsewhere["corners"]],
            [(record["coefficient"], record["corner"]) for record in FINDINGS["corners"]],
            "the replacement model was run over a different set of corners")

        written = stability.report_text(elsewhere)
        self.assertIn(sweep.digest_of(replacement), written)
        self.assertNotIn(sweep.digest_of(FINDINGS["description"]), written)

        moved = [record["coefficient"] for record in elsewhere["corners"]
                 for side, settle in record["sides"].items()
                 if not _near(settle["early"],
                              _corner(record["coefficient"],
                                      record["corner"])["sides"][side]["early"],
                              FINDINGS["reading"])]
        self.assertTrue(
            moved,
            "running a machine whose coffee element is %s W rather than the measured figure "
            "produced the same separation at every corner on both sides, so the method is not "
            "reading the description it was pointed at" % REPLACEMENT_VALUE)

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C3: committed -- as a
    # record the method writes rather than one somebody maintains beside it, and
    # one that says so of itself. Both halves are asked for by name rather than
    # assumed to be somewhere in it.
    def test_the_committed_record_says_it_is_generated_and_carries_every_section(self):
        record = _committed_record()
        self.assertIn("run_parameter_stability.py", record)
        self.assertIn("Do not edit by hand", record)
        for heading in (stability.MODEL_HEADING, stability.STANDARD_HEADING,
                        stability.HORIZON_HEADING, stability.CORNERS_HEADING,
                        stability.VERDICT_HEADING, stability.JOINT_HEADING,
                        stability.UNSETTLED_HEADING):
            with self.subTest(heading=heading):
                self.assertIn(heading, record)
        self.assertIn(stability.THE_BEHAVIOUR, record)
        self.assertIn(FINDINGS["robustness_class"], record)


class TheOneDependenceTheDescriptionStatesIsRunAsAJointCorner(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C4: The one dependence
    the reference description's own construction implies — brew and steam element
    ratings sagging together under a shared mains supply — is run as a joint
    corner alongside the independent ones.
    """

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C4: brew and steam
    # element ratings sagging together -- both written low in one description,
    # read back off the file the run was actually handed. Two lines differing and
    # not one is the whole of what makes this a joint corner rather than a
    # relabelled independent one, and a chained rewrite that lost the first
    # coefficient would leave a record claiming a dependence it did not run.
    def test_the_joint_corner_writes_both_element_ratings_low_in_one_description(self):
        joint = FINDINGS["joint"]
        self.assertIsNotNone(joint, "no joint corner was run against a description carrying both "
                                    "of the mains-coupled coefficients")
        reference = _reference_lines()
        differing = _perturbed_lines(joint["description"], reference)
        self.assertEqual(
            sorted(line.split("=", 1)[0].strip() for _, line in differing),
            sorted(stability.MAINS_COUPLED),
            "the joint corner's description does not differ from the reference on exactly the two "
            "coefficients the dependence is about")

        declared = dict((name, (nominal, fraction)) for name, nominal, fraction in _covered())
        for _, line in differing:
            name = line.split("=", 1)[0].strip()
            nominal, fraction = declared[name]
            with self.subTest(coefficient=name):
                self.assertAlmostEqual(
                    _value_on(line), nominal * (1.0 - joint["fraction"]), places=4,
                    msg="%s was not written at the joint corner's own sag" % name)
                self.assertLess(_value_on(line), nominal, "%s was not written low" % name)
                self.assertGreaterEqual(
                    _value_on(line), nominal * (1.0 - fraction) - 1e-9,
                    "%s was written outside the range its own declared error admits, which is the "
                    "one thing this analysis does not do" % name)

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C4: sagging together
    # under a shared mains supply -- one shared fractional movement rather than
    # each coefficient at its own corner, since power goes as the square of the
    # voltage on both alike. The sag has to be the largest equal fraction both
    # declared errors admit, which is the smaller of the two; anything larger
    # would put the tighter of them outside the declared range, and anything
    # smaller would be a sag nothing chose.
    def test_the_sag_is_the_largest_equal_fractional_movement_both_declared_errors_admit(self):
        declared = dict((name, fraction) for name, _, fraction in _covered())
        fractions = [declared[name] for name in stability.MAINS_COUPLED]
        self.assertNotEqual(
            fractions[0], fractions[1],
            "the two coupled coefficients declare the same error, so this run is no evidence that "
            "the smaller of the two is what the sag is taken from")
        self.assertAlmostEqual(FINDINGS["joint"]["fraction"], min(fractions), places=12)

        # And the dependence is a statement about two named values: a model
        # carrying only one of them has nothing to move together.
        self.assertIsNone(
            stability.joint_sag([(stability.MAINS_COUPLED[0], 1000.0, 0.1)]),
            "a joint corner was produced against a covered set carrying one of the two coupled "
            "coefficients, so what was moved together is one value and itself")
        self.assertIsNotNone(stability.joint_sag(
            [(name, 1000.0, 0.1 + at * 0.05) for at, name in enumerate(stability.MAINS_COUPLED)]))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C4: alongside the
    # independent ones and not instead of them. Both element ratings still have
    # their own corners in the run and in the committed record, and the joint
    # corner is an addition to them -- a run that replaced the two independent
    # corners with one joint one would satisfy every other assertion in this
    # class.
    def test_the_joint_corner_is_run_alongside_the_independent_corners_not_instead_of_them(self):
        for name in stability.MAINS_COUPLED:
            with self.subTest(coefficient=name):
                self.assertEqual(_corners_of(name), ["high", "low"])
        committed = [(row["coefficient"], row["corner"])
                     for row in stability.verdict_rows(_committed_record())]
        for name in stability.MAINS_COUPLED:
            for corner in ("low", "high"):
                with self.subTest(coefficient=name, corner=corner):
                    self.assertIn((name, corner), committed)
        self.assertIn((stability.JOINT_COEFFICIENT, stability.JOINT_CORNER), committed)
        self.assertEqual(
            len(committed), len(_covered()) * 2 - len(stability.ONE_SIDED) + 1,
            "the committed record does not carry one row per two-sided coefficient's pair, one "
            "per one-sided coefficient's single corner, and one for the joint corner")

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C4: is run as a joint
    # corner -- checked for settling on the same standard as every independent
    # one, over the same windows against the same bands, and reported distinctly
    # rather than folded into the per-coefficient table as though it were a
    # coefficient of the description.
    def test_the_joint_corner_is_judged_on_the_same_standard_and_reported_distinctly(self):
        joint = FINDINGS["joint"]
        independent = _corner(stability.MAINS_COUPLED[0], "low")
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            with self.subTest(side=side):
                self.assertEqual(sorted(joint["sides"][side]),
                                 sorted(independent["sides"][side]))
                self.assertEqual(joint["sides"][side]["band"], independent["sides"][side]["band"])
                self.assertEqual(joint["sides"][side]["floor"],
                                 independent["sides"][side]["floor"])
                self.assertIn(joint["sides"][side]["verdict"],
                              (stability.SETTLED, stability.SETTLED_OUTSIDE_THE_BAND,
                               stability.STILL_DIVERGING))

        self.assertNotIn(
            stability.JOINT_COEFFICIENT, [name for name, _, _ in _covered()],
            "the joint corner is named as though it were a coefficient the description carries")
        named = stability.joint_rows(_committed_record())
        self.assertEqual(
            [(what, side) for what, _, side, _ in named],
            [(stability.JOINT_COEFFICIENT, side)
             for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE)],
            "the committed record does not carry the joint corner's own account of both sides. "
            "Re-run firmware/emulation/tools/run_parameter_stability.py")
        for _, _, side, verdict in named:
            with self.subTest(side=side):
                self.assertEqual(verdict, joint["sides"][side]["verdict"])

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C4: run as a joint
    # corner alongside the independent ones -- which means admitted on the terms
    # they are admitted on, including the one that only shows up when a corner is
    # refused. An inadmissible independent corner is recorded and the run goes
    # on; an inadmissible joint corner that ended the run instead would take
    # every verdict in the record with it, and the difference would be invisible
    # on this description because its joint corner is admissible.
    #
    # So a description declaring both element ratings more than a hundred per
    # cent uncertain is put to the joint corner, which makes the shared sag drive
    # both elements below zero, and the machine's own loader refuses it. The
    # corner has to come back recorded rather than raised, with the same shape an
    # independent refusal leaves, and it has to be reported.
    def test_a_joint_corner_the_structure_refuses_is_recorded_on_the_same_terms(self):
        workspace = os.path.join(FINDINGS["workspace"], "joint-refused")
        description = _with_declared_errors(
            dict((name, 1.2) for name in stability.MAINS_COUPLED),
            os.path.join(workspace, "wide-elements.params"))
        covered = sweep.swept_coefficients(description)[0]
        sag, values = stability.joint_sag(covered)
        self.assertAlmostEqual(sag, 1.2, places=9)
        for name in stability.MAINS_COUPLED:
            with self.subTest(coefficient=name):
                self.assertLess(values[name], 0.0,
                                "%s does not sag below zero at this declared error, so the "
                                "structure has no reason to refuse the joint machine" % name)

        windows = dict((side, list(range(first, last + 1)))
                       for side, (first, last) in FINDINGS["windows"].items())
        tails = dict((side, list(range(FINDINGS["ends"][side] - FINDINGS["tails"][side],
                                       FINDINGS["ends"][side])))
                     for side in FINDINGS["ends"])
        refused = stability.joint_corner(
            covered, FINDINGS["executable"], description, FINDINGS["limits"],
            FINDINGS["declaration"], FINDINGS["steam_ready_c"], FINDINGS["converter_scale"],
            FINDINGS["courses"], FINDINGS["reference"], windows, tails, FINDINGS["bands"],
            FINDINGS["floors"], FINDINGS["steam_block_ceiling_c"], workspace)

        self.assertIsNotNone(refused)
        self.assertEqual(refused["sides"], {})
        self.assertEqual(sorted(refused["refused"]), sorted([sweep.BREW_SIDE, sweep.STEAM_SIDE]),
                         "a side of a joint machine the structure refuses came back with a run")
        self.assertEqual(refused["verdict"], stability.CORNER_REFUSED)
        # The same record a joint corner that ran leaves, less the one field only
        # a steam run can produce. Anything else missing is a shape a reader of
        # these records would have to know which kind of corner it was holding to
        # cope with.
        self.assertEqual(
            sorted(refused), sorted(set(FINDINGS["joint"]) - {"steam_block_peak_c"}),
            "a refused joint corner leaves a differently shaped record from one that ran, so "
            "what reads it has to know which kind it is holding")

        # And it is reported the way a refused independent corner is: through the
        # same account, in the same words, under the same heading.
        doctored = dict(FINDINGS)
        doctored["corners"] = [record for record in FINDINGS["corners"]
                               if not record["joint"]] + [refused]
        doctored["joint"] = refused
        written = stability.report_text(doctored)
        section = written.split(stability.UNSETTLED_HEADING, 1)[1].split("\n## ", 1)[0]
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            with self.subTest(side=side):
                self.assertIn("`%s`, %s corner, %s side"
                              % (stability.JOINT_COEFFICIENT, stability.JOINT_CORNER, side),
                              section)
        self.assertIn("The structure would not admit it as a machine", section)

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C4: the one dependence
    # the description's own construction implies -- and what that dependence
    # actually produces on this description has to be established from the runs
    # rather than asserted. The coffee element's own corner at the same sag is
    # re-run here and required to be what the joint corner produced on that side:
    # these relations carry no coupling between the two sides, so the record's
    # statement that the joint corner reproduces the independent one is a finding
    # about the description and has to be checked against a real pair of runs
    # rather than against the analysis's own bookkeeping.
    #
    # The steam side is the other half and is the one this comparison got wrong
    # first. The sag is the smaller of the two declared errors, which is the
    # coffee element's, so the steam element's own corner was run at a wider
    # movement and there is no like-for-like comparison to be had on that side at
    # all. Comparing it against the *coffee* element's corner instead -- which is
    # what matching by fraction alone did -- holds a perturbation up against
    # something that never touched the steam delivery, reports "differing"
    # because a coefficient with no path to that side does nothing to it, and
    # writes that up as a coupling. The correct answer is that the comparison is
    # not available, and the record has to say so without claiming a finding.
    def test_what_the_joint_corner_reproduces_is_established_from_the_runs(self):
        joint = FINDINGS["joint"]
        same, differing, incomparable = stability.joint_against_the_independent_corners(FINDINGS)
        self.assertEqual(
            set([side for side, _ in same] + [side for side, _ in differing]
                + list(incomparable)),
            {sweep.BREW_SIDE, sweep.STEAM_SIDE},
            "the comparison of the joint corner against the independent ones does not account for "
            "both sides, so a side has been dropped rather than reported one way or the other")
        self.assertTrue(
            same or differing,
            "neither side had an independent corner at the joint corner's own sag to compare "
            "against, so the record says nothing about what moving the two together did")

        # Whatever a side is reported as, the coefficient it was compared against
        # is the element that makes that side's delivery. Nothing else is a
        # comparison: this is the structural assertion the original defect would
        # have failed, whatever the two sides' figures happened to be.
        for side, name in same + differing:
            with self.subTest(side=side, coefficient=name):
                self.assertEqual(
                    name, stability.MAINS_COUPLED_BY_SIDE[side],
                    "the %s side's joint corner was compared against `%s`, which is not the "
                    "element that makes that delivery -- so two different perturbations are "
                    "being reported as though one reproduced or failed to reproduce the other"
                    % (side, name))

        # And a differing verdict has to mean something about the machine. It is
        # only a finding where the coefficient compared against reaches that
        # side's delivery at all: a coefficient that moves it nowhere differs
        # from anything trivially, and reporting that as the joint corner
        # reaching a delivery differently is the shape of the original defect.
        for side, name in differing:
            alone = _corner(name, "low")["sides"][side]
            with self.subTest(side=side, coefficient=name):
                self.assertTrue(
                    alone["moved"],
                    "the %s side is reported as differing from `%s`, which moves that delivery "
                    "nowhere at all -- so the difference is between a perturbation and nothing, "
                    "not between two ways of reaching the same delivery" % (side, name))

        # The coffee side is where the like-for-like comparison exists on this
        # description, and it is checked against a real re-run rather than
        # against the analysis's own bookkeeping.
        self.assertEqual(
            [side for side, _ in same], [sweep.BREW_SIDE],
            "the coffee side is no longer the one side whose own element carries the joint "
            "corner's sag, so what this description makes comparable has changed")
        self.assertEqual(
            incomparable, [sweep.STEAM_SIDE],
            "the steam side is expected to have no comparison available: the sag is the smaller "
            "of the two declared errors and the steam element declares the wider one, so its own "
            "corner is a further-moved machine and there is nothing at this sag to hold the joint "
            "corner against")
        self.assertEqual(differing, [],
                         "a side is reported as reaching its delivery differently when the two "
                         "moved together, which these relations carry no path for")

        for side, name in same:
            alone = sweep.brew_draw if side == sweep.BREW_SIDE else None
            with self.subTest(side=side, coefficient=name):
                self.assertIsNotNone(
                    alone, "only the coffee side is re-run here; a steam-side match would need "
                           "its own draw and this assertion has gone stale")
                declared = dict((n, (nominal, fraction))
                                for n, nominal, fraction in _covered())
                nominal, _ = declared[name]
                written = cross_tier.description_with(
                    name, stability.VALUE_FORMAT % (nominal * (1.0 - joint["fraction"])),
                    os.path.join(FINDINGS["workspace"], "joint-cross-check.params"),
                    source=FINDINGS["description"])
                run = alone(FINDINGS["executable"], written, FINDINGS["limits"],
                            FINDINGS["courses"][side], FINDINGS["converter_scale"],
                            "stability-joint-cross-check")
                first, last = FINDINGS["windows"][side]
                settle = stability.settle_of(
                    FINDINGS["reference"][side]["delivered"], run["delivered"],
                    list(range(first, last + 1)), FINDINGS["bands"][side],
                    FINDINGS["floors"][side])
                self.assertEqual(
                    (settle["early"], settle["late"]),
                    (joint["sides"][side]["early"], joint["sides"][side]["late"]),
                    "the record says the joint corner reproduces `%s` alone on the %s side, and a "
                    "run of that coefficient alone at the same sag does not produce the joint "
                    "corner's figures" % (name, side))

    # SOL-SIM-ROBUSTNESS-STABILITY-ACROSS-DECLARED-ERROR.C4: run as a joint
    # corner and reported -- which means the record has to say what the
    # comparison found and must not say what it did not. The side with no
    # like-for-like comparison is the one a record can go wrong about most
    # quietly: a sentence claiming the two sides are coupled reads as a finding,
    # contradicts the description these runs were taken against, and nothing in a
    # table of figures would show it up.
    def test_the_record_does_not_claim_a_coupling_on_the_side_it_cannot_compare(self):
        record = _committed_record()
        section = record.split(stability.JOINT_HEADING, 1)[1].split("\n## ", 1)[0]
        _, differing, incomparable = stability.joint_against_the_independent_corners(FINDINGS)
        self.assertTrue(incomparable, "no side is without a comparison, so this test is not about "
                                      "the case it exists for")
        self.assertFalse(differing, "a side is reported as differing, and the assertion below "
                                    "would then be refusing prose that had become correct")
        for side in incomparable:
            with self.subTest(side=side):
                self.assertIn("On the %s side there is no like-for-like comparison" % side,
                              section)
        self.assertNotIn(
            "does not reproduce that side's own element corner", section,
            "the committed record reports a side as reaching its delivery differently when the "
            "two elements moved together, and no side did")
        self.assertNotIn(
            "That is what a description carrying a coupling between the two sides produces.",
            section,
            "the committed record states that a coupling between the two sides was found, which "
            "the description these runs were taken against says it does not carry")
        self.assertIn("carry no coupling between the two sides at all", section)


if __name__ == "__main__":
    unittest.main()
