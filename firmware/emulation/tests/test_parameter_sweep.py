"""What the dominance sweep has to have shown before its ranking counts as
evidence about which of this machine's coefficients are worth measuring first.

The sweep happens once for the whole suite, on the terms every other suite in
this directory is written on: four host draws per coefficient plus the two the
deviations are taken against, some eighty of them put through one artefact, and
every assertion below reads what that run produced rather than reaching for the
loops itself.

One assertion costs a second sweep of the same size, and it is deliberate: it
runs the same method against a description the shipped one is not, because a
method that can only ever be pointed at one model is not repeatable against a
replacement and cannot be shown to be. Nothing in the first run's findings can
answer that. Two others write a description of their own and read only what the
sweep makes of it before any draw is run, which costs nothing: one that claims
no machine, because a sweep that ranked one would be ranking sensitivities of
nothing, and one whose declared error has been taken away, because a coefficient
with nothing to perturb it by has to come back named rather than missing.

Nothing here asks whether the ranking is quantitatively right for a real
machine. It cannot be: the model it was taken against is estimated throughout,
and the solution's own criteria put that question out of scope until a measured
model exists.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, "..", "tools"))
FIRMWARE_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, TOOLS)

import run_closed_loop_check as closed_loop  # noqa: E402
import run_cross_tier_check as cross_tier  # noqa: E402
import run_parameter_sweep as sweep  # noqa: E402

FINDINGS = None

# The description that claims no machine, checked in beside the one that does.
# It exists for another check entirely -- one linked executable run against two
# descriptions producing two trajectories -- and is borrowed here because it is
# the tree's only description that says in the file that it describes nothing
# real, which is precisely the case a dominance ranking must refuse.
NO_MACHINE_DESCRIPTION = os.path.join(FIRMWARE_DIR, "params", "thermoblock-variant.params")

# A coefficient this suite writes differently to make a description that is a
# different machine and still a machine. The figure is the one the reference
# machine's owner recalls the element being, which the description records as
# disputed against the service manual's 1000 W -- a replacement model this
# project might genuinely end up sweeping rather than an invented one.
REPLACEMENT_COEFFICIENT = "brew.heater_power_w"
REPLACEMENT_VALUE = "1200.0"

# The coefficients this model gives the sweep nothing to weigh them against.
# Both sit in the brew path's pressure relation, which the plant models in full
# and which no declaration puts a band on -- so a perturbation of either moves a
# quantity the machine carries and no quantity either delivery is judged by, and
# there is no margin for its uncertainty to be a fraction of. Named here rather
# than taken from the run, so that a later model declaring a band for that
# pressure fails this suite instead of quietly emptying it.
UNWEIGHABLE_COEFFICIENTS = ("pump.pressure_bar", "brew.pressure_time_constant_s")

# How far a regenerated figure may sit from the committed one before the
# committed record is out of date rather than merely rounded differently.
#
# The sweep is deterministic on one host: running it twice writes the same
# bytes. Across hosts it need not be, because the plant model's arithmetic
# reaches the platform's own maths library, and a difference in the last place
# of an exponential accumulated over seven thousand intervals can move a
# reported figure in its third significant digit. A per-cent is far inside any
# change to the ranking that would matter and far outside that.
FIGURE_TOLERANCE = 0.01

# The full heater scale, at or above which the brew loop has nothing further to
# give: what it commands is clamped there, so an interval sitting at it is one
# where the reading could have been anything below the target and the same level
# would have been driven.
FULL_HEATER_SCALE = 1000


def setUpModule():
    global FINDINGS
    FINDINGS = sweep.run_once()


def _committed_record():
    with open(sweep.REPORT_PATH, encoding="utf-8") as handle:
        return handle.read()


def _perturbed_line(path, coefficient):
    """The line one written description carries for one coefficient."""
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            head, separator, _ = line.partition("=")
            if separator and head.strip() == coefficient:
                return line.rstrip("\n")
    raise AssertionError("%s carries no line for %s" % (path, coefficient))


def _entry(coefficient):
    """What the sweep recorded for one coefficient, ranked or not.

    Everything the sweep perturbed rather than everything it ranked, because a
    coefficient it perturbed and then could not weigh still has corners,
    deviations and a written description behind it, and the assertions about
    what the sweep did to it are owed of it just the same.
    """
    for entry in FINDINGS["swept"]:
        if entry["coefficient"] == coefficient:
            return entry
    raise AssertionError("the sweep did not perturb %s" % coefficient)


class TheSweepPerturbsEveryDeclaredErrorAndRunsBothDeliveries(unittest.TestCase):
    """SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: The sweep perturbs every
    parameter carrying a declared error and re-runs the closed loop for both
    deliveries.
    """

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: for each plant parameter that
    # carries a declared error against its nominal value -- every one of them,
    # established against the build-time check's own reader of the description
    # rather than against the sweep's own list of what it did. A sweep that
    # dropped a coefficient and then reported the coefficients it had swept
    # would agree with itself perfectly.
    #
    # What is compared is everything perturbed rather than everything ranked.
    # The two are not the same set -- a coefficient the sweep perturbs and then
    # cannot weigh leaves the ranking -- and asserting this against the ranking
    # would make perturbing a coefficient and being able to weigh it the same
    # condition, which is exactly the conflation the ranking exists to avoid.
    def test_every_coefficient_carrying_a_declared_error_was_perturbed(self):
        vocabulary, marker = sweep._vocabularies()
        declared = sweep.assumed_error.Description(FINDINGS["description"], vocabulary, marker)
        carrying = {name for name, (_, fraction) in declared.values.items()
                    if fraction is not None and float(fraction) != 0.0}

        self.assertTrue(
            carrying,
            "the description carries no declared error at all, so this suite is asserting "
            "about an empty set and would pass over a sweep that did nothing")
        self.assertEqual(
            {entry["coefficient"] for entry in FINDINGS["swept"]}, carrying,
            "the coefficients the sweep perturbed are not the coefficients the description "
            "declares an error against")

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: holds every other parameter
    # at nominal, perturbs the one under test by its declared amount. Both
    # halves are read back off the descriptions the sweep actually handed the
    # machine: exactly one line differs from the reference, and the figure on
    # that line is the nominal scaled by one plus or minus the fraction the same
    # description declares. A sweep moving two coefficients at once, or moving
    # one by something other than its declared error, is the failure that leaves
    # every figure downstream meaningless while the run still completes.
    def test_each_run_moved_exactly_one_coefficient_and_moved_it_by_its_declared_error(self):
        with open(FINDINGS["description"], encoding="utf-8") as handle:
            reference = handle.read().splitlines()

        for entry in FINDINGS["swept"]:
            for corner, expected in entry["corners"].items():
                written = os.path.join(FINDINGS["workspace"],
                                       "%s-%s.params" % (entry["coefficient"], corner))
                with self.subTest(coefficient=entry["coefficient"], corner=corner):
                    self.assertTrue(os.path.exists(written), written)
                    with open(written, encoding="utf-8") as handle:
                        perturbed = handle.read().splitlines()

                    differing = [at for at in range(min(len(reference), len(perturbed)))
                                 if reference[at].strip() != perturbed[at].strip()]
                    self.assertEqual(
                        len(differing), 1,
                        "the %s corner of %s differs from the reference description on %d "
                        "lines, so more than one coefficient moved"
                        % (corner, entry["coefficient"], len(differing)))

                    line = _perturbed_line(written, entry["coefficient"])
                    value = float(line.split("=", 1)[1].split()[0])
                    self.assertAlmostEqual(
                        value, expected, places=4,
                        msg="the %s corner of %s was written as %g, not the %g its declared "
                            "error of %g implies"
                            % (corner, entry["coefficient"], value, expected, entry["fraction"]))

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: perturbs the one under test
    # by its declared amount -- which is a two-sided statement, so both ends of
    # it are run and the coefficient is judged on whichever moved the delivery
    # further. A sweep that took one end would report a relation steep in the
    # direction it did not look as gentle.
    def test_both_ends_of_every_declared_error_were_run(self):
        for entry in FINDINGS["swept"]:
            with self.subTest(coefficient=entry["coefficient"]):
                self.assertEqual(sorted(entry["corners"]), ["high", "low"])
                self.assertLess(entry["corners"]["low"], entry["nominal"])
                self.assertGreater(entry["corners"]["high"], entry["nominal"])
                self.assertIn(entry["deviation"][sweep.BREW_SIDE][1], ("low", "high"))
                self.assertIn(entry["deviation"][sweep.STEAM_SIDE][1], ("low", "high"))

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: once for the coffee side and
    # once for the steam side -- both, for every coefficient. A ranking taken
    # over one side would under-rank whatever dominates the other, which is the
    # reason the solution's own text refuses to treat the two separately.
    def test_both_deliveries_were_re_run_for_every_coefficient(self):
        for entry in FINDINGS["swept"]:
            with self.subTest(coefficient=entry["coefficient"]):
                for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
                    self.assertIn(side, entry["deviation"])
                    self.assertIn(side, entry["dominance"])
                    self.assertIn(side, entry["sensitivity"])

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: re-runs the same closed-loop
    # scenario -- closed, on both sides, over the window the delivery is judged
    # in. A loop sitting at its actuator's limit for the whole of that window is
    # one whose reading changes nothing it commands, and a sweep across it would
    # be reporting an open loop's sensitivity under a closed loop's name. Each
    # side is required to have been off its limit and off nothing.
    def test_both_loops_were_actually_closing_over_the_window_they_are_judged_in(self):
        brew = FINDINGS["reference"][sweep.BREW_SIDE]["trajectory"]
        window = sweep.brew_judged_window(FINDINGS["courses"][sweep.BREW_SIDE])
        levels = [brew[at]["heater_permille"] for at in window]
        self.assertTrue(
            0 < min(levels) and max(levels) < FULL_HEATER_SCALE,
            "the brew loop ran between %d and %d permille across the shot, so it spent part of "
            "the delivery at a limit where its reading changed nothing it commanded"
            % (min(levels), max(levels)))

        steam = FINDINGS["reference"][sweep.STEAM_SIDE]["trajectory"]
        steam_window = sweep.steam_judged_window(
            FINDINGS["courses"][sweep.STEAM_SIDE], steam)
        steam_levels = [steam[at]["heater_permille"] for at in steam_window]
        feeds = [steam[at]["feed_permille"] for at in steam_window]
        self.assertTrue(
            0 < min(steam_levels) and max(steam_levels) < FULL_HEATER_SCALE,
            "the steam loop ran between %d and %d permille across the draw, so it spent part of "
            "the delivery at a limit" % (min(steam_levels), max(steam_levels)))
        self.assertGreater(
            min(feeds), 0,
            "the steam draw's judged window includes an interval nothing was being fed on, so it "
            "is not the window in which steam was actually being delivered")

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: the delivery outcome the loop
    # is judged against. Each side's unperturbed run has to land inside the band
    # the design declares for it, or the deviations measured off it are
    # deviations from a machine that was not delivering and the fractions of the
    # margin they are reported as are fractions of a margin nothing was inside.
    def test_the_unperturbed_run_delivers_inside_the_declared_band_on_both_sides(self):
        brew = FINDINGS["reference"][sweep.BREW_SIDE]["delivered"]
        window = sweep.brew_judged_window(FINDINGS["courses"][sweep.BREW_SIDE])
        worst = max(abs(brew[at] - sweep.BREW_TARGET_C) for at in window)
        self.assertLess(
            worst, FINDINGS["bands"][sweep.BREW_SIDE],
            "the unperturbed shot sat %.3f C from the %.1f C it was commanded, outside the "
            "%.3f C band the design holds a delivery to"
            % (worst, sweep.BREW_TARGET_C, FINDINGS["bands"][sweep.BREW_SIDE]))

        steam = FINDINGS["reference"][sweep.STEAM_SIDE]["delivered"]
        steam_window = sweep.steam_judged_window(
            FINDINGS["courses"][sweep.STEAM_SIDE],
            FINDINGS["reference"][sweep.STEAM_SIDE]["trajectory"])
        floor = sweep._declared_figure(
            FINDINGS["declaration"],
            sweep._declared_word(sweep.STEAM_DECLARATION_HEADER,
                                 sweep.STEAM_FLOOR_MACRO)) / 1000.0
        ceiling = sweep._declared_figure(
            FINDINGS["declaration"],
            sweep._declared_word(sweep.STEAM_DECLARATION_HEADER,
                                 sweep.STEAM_CEILING_MACRO)) / 1000.0
        outside = [at for at in steam_window if not floor <= steam[at] <= ceiling]
        self.assertEqual(
            outside, [],
            "the unperturbed draw left the %.3f..%.3f bar band the design holds it to on %d of "
            "its %d delivered intervals" % (floor, ceiling, len(outside), len(steam_window)))

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: out of scope -- parameters
    # that carry no declared error, since there is nothing to weigh their
    # sensitivity against. A coefficient stripped of its error has to come back
    # named and excluded with the reason, not silently missing: a coefficient
    # dropped from a dominance ranking reads exactly like one that was ranked
    # and came last.
    #
    # This is regression protection as well as verification. Any future change
    # that made the sweep quietly skip a coefficient would have to keep this
    # exclusion working while breaking the census above, and the two together
    # are what pins the covered set to the declared set.
    def test_a_coefficient_carrying_no_declared_error_is_named_and_excluded(self):
        vocabulary, marker = sweep._vocabularies()
        with open(FINDINGS["description"], encoding="utf-8") as handle:
            text = handle.read()

        stripped = _entry("brew.loss_w_per_k")["coefficient"]
        rewritten = []
        for line in text.splitlines():
            head, separator, tail = line.partition("=")
            if separator and head.strip() == stripped:
                # The assumed error taken out and the origin left where it is,
                # which is the shape of the mistake this excludes: a value whose
                # provenance is recorded and whose uncertainty is not.
                account = tail[tail.find(vocabulary.marker):]
                rewritten.append("%s = %g %s" % (stripped, _entry(stripped)["nominal"], account))
            else:
                rewritten.append(line)

        path = os.path.join(sweep.BUILD_DIR, "no-declared-error.params")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(rewritten) + "\n")

        covered, unweighed = sweep.swept_coefficients(path)
        self.assertNotIn(
            stripped, [name for name, _, _ in covered],
            "a coefficient carrying no declared error was perturbed anyway, so the sweep moved "
            "it by an amount nobody declared")
        self.assertIn(
            stripped, [name for name, _, _ in unweighed],
            "a coefficient carrying no declared error vanished from the sweep without being "
            "named, which reads from the outside exactly like one that was ranked last")

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: for each plant parameter --
    # of a plant that is claimed to exist. A description that says in the file
    # that it describes no real machine has no delivery for a perturbation to
    # move, and ranking its coefficients would produce a table of sensitivities
    # of nothing that reads identically to a real one.
    def test_a_description_claiming_no_machine_is_refused_rather_than_ranked(self):
        with self.assertRaises(sweep.SweepError) as refused:
            sweep.swept_coefficients(NO_MACHINE_DESCRIPTION)
        self.assertIn("no real machine", str(refused.exception))


class ParametersAreRankedByWhatTheirOwnUncertaintySpends(unittest.TestCase):
    """SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C2: Parameters are ranked by how
    much of the machine's declared margin their own uncertainty already spends.
    """

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C2: each parameter's recorded
    # deviation from the sweep is divided by the delivery's own declared band --
    # the margin the machine is already held to -- and by nothing else. The
    # arithmetic is recomputed here from the two figures the sweep recorded, the
    # deviation and the band it is a fraction of, rather than read back off
    # itself.
    #
    # The sensitivity figure is checked in the same pass, because the two are
    # one division apart and a run that had them the wrong way round would still
    # carry both keys with plausible numbers in them.
    def test_the_dominance_figure_is_the_deviation_as_a_fraction_of_the_declared_band(self):
        for entry in FINDINGS["ranking"]:
            for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
                with self.subTest(coefficient=entry["coefficient"], side=side):
                    deviation = entry["deviation"][side][0]
                    self.assertAlmostEqual(entry["dominance"][side],
                                           deviation / FINDINGS["bands"][side], places=9)
                    self.assertAlmostEqual(
                        entry["sensitivity"][side],
                        deviation / FINDINGS["bands"][side] / entry["fraction"], places=9)
            self.assertEqual(
                entry["rank_by"], max(entry["dominance"].values()),
                "%s is ranked on something other than the largest fraction of a declared band it "
                "spent" % entry["coefficient"])

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C2: ordered by the resulting
    # fraction of that margin rather than by the raw deviation or by the
    # parameter's own declared error alone. Three things are asserted, and the
    # first is the weakest of them.
    #
    # The second rules out the raw deviation: a degree of brew temperature and a
    # hundredth of a bar of steam pressure are not the same size of statement,
    # and an order taken over the deviations as they stand would be an order
    # over the units the two sides happen to be measured in. Dividing by each
    # side's own band is what makes one list over two deliveries mean anything.
    #
    # The third rules out the figure this ranking was first written against and
    # which reads as the obvious normalisation: the deviation with the declared
    # error divided back out. That figure is the model's sensitivity to the
    # relation and is by construction indifferent to how well the coefficient is
    # known -- perturbing at the declared error puts that error into the
    # deviation, and dividing by it takes it straight back out. Ordering on it
    # answers "which relation is steepest", not "whose uncertainty is spending
    # the margin", and those are different lists. This assertion is what pins
    # the two apart on this model rather than leaving it to the prose.
    def test_the_order_is_the_band_fraction_and_is_neither_the_raw_deviation_nor_the_sensitivity(
            self):
        ranked = [entry["rank_by"] for entry in FINDINGS["ranking"]]
        self.assertEqual(
            ranked, sorted(ranked, reverse=True),
            "the ranking is not in descending order of the figure it claims to be ordered by")

        ordered = [entry["coefficient"] for entry in FINDINGS["ranking"]]

        by_raw_deviation = [entry["coefficient"] for entry in sorted(
            FINDINGS["ranking"],
            key=lambda entry: (-max(reported[0] for reported in entry["deviation"].values()),
                               entry["coefficient"]))]
        self.assertNotEqual(
            by_raw_deviation, ordered,
            "ordering by the deviations in their own units produces the same list as ordering by "
            "the fraction of each side's band they spend, so this run is no evidence that the "
            "bands are being divided by at all")

        by_sensitivity = [entry["coefficient"] for entry in sorted(
            FINDINGS["ranking"],
            key=lambda entry: (-max(entry["sensitivity"].values()), entry["coefficient"]))]
        self.assertNotEqual(
            by_sensitivity, ordered,
            "ordering by the model's sensitivity produces the same list as ordering by how much "
            "margin each coefficient's own uncertainty spends, so this run is no evidence that "
            "the ranking weighs the uncertainty rather than cancelling it out")

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C2: so a well-known parameter
    # with a large raw effect and a poorly-known parameter with a small one are
    # compared on the same footing. The criterion names a specific inversion and
    # the run is required to contain one, but it is the inversion the corrected
    # metric produces and not its opposite: a coefficient the description admits
    # to being loosely known has to be able to outrank a tightly-known one the
    # model answers more steeply, because the loose one's own uncertainty is
    # spending more of the margin today.
    #
    # That is the pair the whole ranking exists to get right. Measurement and
    # procurement are prioritised off this order, and a ranking that put the
    # steeper relation first would send the money at the coefficient already
    # known well enough not to need it. Without such a pair in the run the
    # ranking is untested whatever order it came out in.
    def test_a_loosely_known_parameter_outranks_a_steeper_relation_that_is_known_tightly(self):
        found = []
        for loose in FINDINGS["ranking"]:
            for tight in FINDINGS["ranking"]:
                if loose["fraction"] <= tight["fraction"]:
                    continue
                if max(loose["sensitivity"].values()) >= max(tight["sensitivity"].values()):
                    continue
                if loose["rank_by"] > tight["rank_by"]:
                    found.append((loose["coefficient"], tight["coefficient"]))
        self.assertTrue(
            found,
            "no pair in this ranking has a loosely declared coefficient outranking a tightly "
            "declared one whose relation the model answers more steeply, so the run does not "
            "exercise the comparison this criterion exists to make")

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C2: parameters and channels are
    # ordered -- one order covering both deliveries. A ranking that had come out
    # grouped by side would be two rankings printed one after the other, which
    # is what the solution's own text refuses.
    def test_the_two_sides_are_ranked_into_one_list_rather_than_grouped(self):
        sides = [entry["worst_side"] for entry in FINDINGS["ranking"]]
        self.assertEqual(
            set(sides), {sweep.BREW_SIDE, sweep.STEAM_SIDE},
            "one side set every coefficient's figure, so this ranking does not actually cover "
            "both deliveries")
        changes = sum(1 for at in range(1, len(sides)) if sides[at] != sides[at - 1])
        self.assertGreater(
            changes, 1,
            "the ranking changes side %d time(s), so it is two lists concatenated rather than "
            "one order over both deliveries" % changes)

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C2: how much of the machine's
    # declared margin -- the machine's, read from the declarations, and not a
    # figure written into the sweep. Both bands are asked of a declaration this
    # test writes, and both have to follow it. A band compiled into the tool
    # would answer the same number whatever the design declared, and every
    # fraction in the ranking would be a fraction of it.
    #
    # This is regression protection as well as verification: a later change that
    # replaced either reader with a constant would pass every other assertion in
    # this suite and fail here.
    def test_both_bands_are_read_from_the_declarations_rather_than_written_into_the_sweep(self):
        elsewhere = os.path.join(sweep.BUILD_DIR, "elsewhere.tolerance")
        with open(FINDINGS["tolerance"], encoding="utf-8") as handle:
            text = handle.read()
        word = sweep._declared_word(sweep.TOLERANCE_HEADER, sweep.BREW_BAND_MACRO)
        with open(elsewhere, "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"^\s*%s\s*=\s*\d+" % re.escape(word), "%s = 400" % word, text,
                                flags=re.MULTILINE))
        self.assertAlmostEqual(sweep.brew_band_c(elsewhere), 0.4, places=9)
        self.assertNotAlmostEqual(sweep.brew_band_c(elsewhere),
                                  FINDINGS["bands"][sweep.BREW_SIDE], places=9)

        steam_elsewhere = os.path.join(sweep.BUILD_DIR, "elsewhere.declaration")
        with open(FINDINGS["declaration"], encoding="utf-8") as handle:
            steam_text = handle.read()
        ceiling = sweep._declared_word(sweep.STEAM_DECLARATION_HEADER, sweep.STEAM_CEILING_MACRO)
        with open(steam_elsewhere, "w", encoding="utf-8") as handle:
            handle.write(re.sub(r"^\s*%s\s*=\s*\d+" % re.escape(ceiling), "%s = 1800" % ceiling,
                                steam_text, flags=re.MULTILINE))
        self.assertAlmostEqual(sweep.steam_band_bar(steam_elsewhere), 0.4, places=9)
        self.assertNotAlmostEqual(sweep.steam_band_bar(steam_elsewhere),
                                  FINDINGS["bands"][sweep.STEAM_SIDE], places=9)


class TheSweepAndItsRankingAreCommittedAndRepeatable(unittest.TestCase):
    """SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C3: The sweep and the ranking it
    produced are committed in a form repeatable against a replacement model.
    """

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C3: the sweep's method and the
    # ranking it produced are checked in together. The committed record has to
    # be the one this method presently produces, coefficient for coefficient and
    # figure for figure -- a record that has drifted from the method beside it
    # is a ranking nobody can reproduce, which is the whole of what this
    # criterion is about.
    #
    # This is regression protection as well as verification. Any change to the
    # sweep, to either course, to either loop or to the model that moves the
    # ranking fails here until the record is regenerated, which is exactly the
    # coupling a committed analysis needs and the reason the record is generated
    # rather than written by hand.
    def test_the_committed_ranking_is_the_one_this_method_presently_produces(self):
        committed = sweep.ranking_rows(_committed_record())
        produced = sweep.ranking_rows(sweep.report_text(FINDINGS))

        self.assertTrue(committed, "%s carries no ranking table" % sweep.REPORT_PATH)
        self.assertEqual(
            [(position, name) for position, name, _, _, _ in committed],
            [(position, name) for position, name, _, _, _ in produced],
            "the committed ranking is not in the order this sweep now produces. Re-run "
            "firmware/emulation/tools/run_parameter_sweep.py")

        for (_, name, error, dominance, side), (_, _, now_error, now_dominance, now_side) in zip(
                committed, produced):
            with self.subTest(coefficient=name):
                self.assertEqual(side, now_side)
                self.assertAlmostEqual(error, now_error, places=9)
                self.assertLessEqual(
                    abs(dominance - now_dominance),
                    FIGURE_TOLERANCE * max(abs(now_dominance), 1e-12) + 1e-12,
                    "the committed record gives %s a dominance of %g and this sweep now gives it "
                    "%g. Re-run firmware/emulation/tools/run_parameter_sweep.py" %
                    (name, dominance, now_dominance))

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C3: naming the model they were
    # run against. A name alone does not say which machine, because a path can
    # be rewritten under a record that goes on reading as current -- so each of
    # the four files is named with what it presently holds, and the record is
    # out of date the moment any of them moves.
    def test_the_committed_record_names_the_files_it_was_run_against_as_they_stand(self):
        record = _committed_record()
        for path in (FINDINGS["description"], FINDINGS["limits"], FINDINGS["declaration"],
                     FINDINGS["tolerance"]):
            with self.subTest(file=path):
                self.assertIn(sweep._relative(path), record)
                self.assertIn(
                    sweep.digest_of(path), record,
                    "%s has changed since the committed ranking was taken against it. Re-run "
                    "firmware/emulation/tools/run_parameter_sweep.py" % sweep._relative(path))

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C3: such that pointing the same
    # sweep at a replacement model requires changing only which model it reads.
    # A second machine is written -- the reference description with the disputed
    # element rating at the figure its owner recalls -- and the whole method is
    # run against it by argument alone. What is asserted is that it covers the
    # same coefficients, names the replacement rather than the shipped
    # description, and comes back with figures that moved: a sweep that quietly
    # went on reading the original would satisfy the first two and not the
    # third.
    def test_the_same_method_run_against_a_replacement_model_needs_no_edit_to_it(self):
        replacement = cross_tier.description_with(
            REPLACEMENT_COEFFICIENT, REPLACEMENT_VALUE,
            os.path.join(sweep.BUILD_DIR, "replacement-model.params"),
            source=FINDINGS["description"])

        # Its own scratch directory, so the descriptions this run writes do not
        # stand where the shipped run's are: the assertions in C1's own class
        # go back to those files to establish what that run handed the machine,
        # and would otherwise be reading this replacement model's.
        elsewhere = sweep.run(description=replacement, limits=FINDINGS["limits"],
                              executable=FINDINGS["executable"],
                              workspace=os.path.join(sweep.BUILD_DIR, "replacement"))

        self.assertEqual(
            sorted(entry["coefficient"] for entry in elsewhere["swept"]),
            sorted(entry["coefficient"] for entry in FINDINGS["swept"]),
            "the replacement model was swept over a different set of coefficients")
        self.assertEqual(
            sorted(entry["coefficient"] for entry in elsewhere["ranking"]),
            sorted(entry["coefficient"] for entry in FINDINGS["ranking"]),
            "the replacement model's ranking covers a different set of coefficients, so one of "
            "the two runs weighed something the other could not")

        record = sweep.report_text(elsewhere)
        self.assertIn(sweep.digest_of(replacement), record)
        self.assertNotIn(sweep.digest_of(FINDINGS["description"]), record)

        moved = [entry["coefficient"] for entry in elsewhere["ranking"]
                 if abs(entry["rank_by"] - _entry(entry["coefficient"])["rank_by"]) >
                 FIGURE_TOLERANCE * max(_entry(entry["coefficient"])["rank_by"], 1e-12)]
        self.assertTrue(
            moved,
            "sweeping a machine whose element is %s W rather than the shipped figure produced "
            "the same dominance figures throughout, so the sweep is not reading the description "
            "it was pointed at" % REPLACEMENT_VALUE)

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C3: checked in together -- the
    # method and the ranking, in one record that says which it is. A record
    # somebody edits by hand is one the method no longer produces, so the record
    # says so of itself, and both halves of what it carries are asked for by
    # name rather than assumed to be somewhere in it.
    def test_the_committed_record_carries_the_method_beside_the_ranking(self):
        record = _committed_record()
        self.assertIn("run_parameter_sweep.py", record)
        self.assertIn("Do not edit by hand", record)
        self.assertIn(sweep.RANKING_HEADING, record)
        self.assertIn(sweep.SIDES_HEADING, record)
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            self.assertIn(sweep.JUDGED[side][0], record)

    # SOL-DOMINANCE-RECORD-NAMES-EVERY-SIBLING-ANALYSIS.C1: the committed
    # dominance record names every analysis presently taken from its re-runs,
    # including the stability record -- mirrors the identifiability pointer
    # this record already carries, and is what a reader arriving here first is
    # left without if a further analysis is added and this record is not told.
    def test_the_committed_record_points_at_every_sibling_analysis(self):
        record = _committed_record()
        self.assertIn("run_parameter_identifiability.py", record)
        self.assertIn("docs/parameter-identifiability.md", record)
        self.assertIn("run_parameter_stability.py", record)
        self.assertIn("docs/parameter-stability.md", record)
        self.assertIn("run_protection_margin.py", record)
        self.assertIn("docs/protection-margin.md", record)


class ACoefficientTheSweepCannotWeighIsNamedRatherThanRanked(unittest.TestCase):
    """SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C4: A parameter the sweep cannot
    weigh is named separately rather than given a place in the ranking.
    """

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C4: a parameter whose effect
    # reaches no quantity carrying a declared band is left out of the ranked
    # list entirely. Both of the description's pressure-path coefficients are
    # that case on this model: the brew path's pressure is modelled in full and
    # the design declares no band for it, so neither coefficient moves anything
    # either delivery is judged against.
    #
    # Named rather than derived from the run, because a test that asked the
    # sweep which coefficients it had excluded and then asserted those were
    # excluded would agree with itself over any answer, including none. If a
    # later model declares a band for the brew path's pressure these two stop
    # being the case in point and this test is what says so.
    def test_a_coefficient_reaching_no_quantity_with_a_declared_band_is_not_ranked(self):
        for coefficient in UNWEIGHABLE_COEFFICIENTS:
            with self.subTest(coefficient=coefficient):
                self.assertEqual(
                    _entry(coefficient)["moves_banded"], set(),
                    "%s moved a delivery the design declares a band for, so it is no longer the "
                    "case this asserts about and the coefficient chosen here is stale"
                    % coefficient)
                self.assertNotIn(
                    coefficient, [entry["coefficient"] for entry in FINDINGS["ranking"]],
                    "%s reaches no quantity carrying a declared band and was ranked anyway, so "
                    "the ranked list carries a row whose figure of nothing means the opposite of "
                    "what a reader will take from its position" % coefficient)

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C4: it is not given a row in the
    # ranking with a dominance of nothing, since a reader scanning a ranked list
    # for what matters least would find it there. Asserted against the committed
    # record and not only against the findings, because the record is what such
    # a reader actually has: a sweep that partitioned correctly in memory and
    # went on printing every coefficient into the one table would fail nothing
    # else in this suite.
    def test_the_committed_ranking_table_carries_no_row_for_a_coefficient_it_could_not_weigh(self):
        ranked = [name for _, name, _, _, _ in sweep.ranking_rows(_committed_record())]
        self.assertTrue(ranked, "%s carries no ranking table" % sweep.REPORT_PATH)
        for coefficient in UNWEIGHABLE_COEFFICIENTS:
            with self.subTest(coefficient=coefficient):
                self.assertNotIn(coefficient, ranked)
        self.assertEqual(
            [entry["coefficient"] for entry in FINDINGS["ranking"]], ranked,
            "the committed ranked table is not the set of coefficients this sweep can presently "
            "weigh. Re-run firmware/emulation/tools/run_parameter_sweep.py")

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C4: named instead in a separate
    # account of what the sweep could not weigh and why. Both halves are asked
    # for -- that the coefficient is in that account, and that the account says
    # which of the three conditions put it there. An account that named the
    # coefficient and not the reason would leave a reader unable to tell a
    # coefficient nothing can judge from one the sweep declined to run, and the
    # first is a finding about what this design declares bands for.
    def test_a_coefficient_that_could_not_be_weighed_is_named_with_the_condition_that_excluded_it(
            self):
        recorded = dict((name, condition) for name, condition, _ in FINDINGS["unweighed"])
        written = dict(sweep.unweighed_rows(_committed_record()))
        for coefficient in UNWEIGHABLE_COEFFICIENTS:
            with self.subTest(coefficient=coefficient):
                self.assertEqual(
                    recorded.get(coefficient), sweep.NO_BANDED_QUANTITY_REACHED,
                    "%s is not named as reaching no quantity carrying a declared band, so the "
                    "sweep excluded it without saying what it could not weigh it against"
                    % coefficient)
                self.assertEqual(
                    written.get(coefficient), sweep.NO_BANDED_QUANTITY_REACHED,
                    "%s is not named under \"%s\" in the committed record, so the account a "
                    "reader has does not say the coefficient exists. Re-run "
                    "firmware/emulation/tools/run_parameter_sweep.py"
                    % (coefficient, sweep.UNWEIGHED_HEADING.lstrip("# ")))
        self.assertEqual(
            written, recorded,
            "the committed account of what could not be weighed is not the one this sweep now "
            "produces. Re-run firmware/emulation/tools/run_parameter_sweep.py")

    # SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C4: a parameter carrying no
    # declared error, or a declared error of nothing, is excluded on the same
    # terms and named under its own condition. Neither case arises in the
    # description this project carries, so both are made: a coefficient whose
    # declared error is taken away and one whose declared error is written as
    # nothing, against a description this test writes. Without them the two
    # conditions would be implemented and never exercised, and a later change
    # that collapsed all three into one reason would pass everything above.
    def test_the_two_conditions_visible_from_the_description_alone_are_named_apart(self):
        vocabulary, marker = sweep._vocabularies()
        with open(FINDINGS["description"], encoding="utf-8") as handle:
            text = handle.read()

        stripped = "brew.loss_w_per_k"
        exact = "brew.thermal_mass_j_per_k"
        rewritten = []
        for line in text.splitlines():
            head, separator, tail = line.partition("=")
            name = head.strip()
            if separator and name == stripped:
                account = tail[tail.find(vocabulary.marker):]
                rewritten.append("%s = %g %s" % (name, _entry(name)["nominal"], account))
            elif separator and name == exact:
                rewritten.append(re.sub(r"%s\s*[\d.eE+-]+" % re.escape(marker),
                                        "%s 0.0" % marker, line))
            else:
                rewritten.append(line)

        path = os.path.join(sweep.BUILD_DIR, "unweighable-two-ways.params")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(rewritten) + "\n")

        covered, unweighed = sweep.swept_coefficients(path)
        named = dict((name, condition) for name, condition, _ in unweighed)
        self.assertNotIn(stripped, [name for name, _, _ in covered])
        self.assertNotIn(exact, [name for name, _, _ in covered])
        self.assertEqual(named.get(stripped), sweep.NO_DECLARED_ERROR)
        self.assertEqual(named.get(exact), sweep.ERROR_DECLARED_AS_NOTHING)
        self.assertNotEqual(
            sweep.NO_DECLARED_ERROR, sweep.ERROR_DECLARED_AS_NOTHING,
            "the two conditions are written as the same words, so the account cannot tell a "
            "coefficient with no error declared against it from one declared exact")
        for name, _, why in unweighed:
            with self.subTest(coefficient=name):
                self.assertTrue(why.strip(), "%s is excluded with no reason given" % name)


class TheTwoDrawsReportUnderTheNamesEverythingLooksThemUpBy(unittest.TestCase):
    """SOL-DELIVERY-PARAMETER-DOMINANCE-RANKING.C1: the harness the sweep runs
    the steam side through, asserted on its own account rather than through the
    ranking that consumes it.
    """

    # A smoke test of the native steam draw, which is new infrastructure this
    # sweep needed and which nothing else in the tree exercises. What it
    # establishes is that the draw produces a non-degenerate trajectory: the
    # block is where the declaration says it holds, the wand's report follows
    # the course, feed engages after the declared margin-building interval
    # rather than at once, and the machine was advanced once per interval plus
    # the one settling step it reports. A harness that ran and printed nothing
    # usable would be caught here rather than as an inexplicable ranking.
    def test_the_steam_draw_produces_a_plausible_non_degenerate_draw(self):
        steam = FINDINGS["reference"][sweep.STEAM_SIDE]
        course = FINDINGS["courses"][sweep.STEAM_SIDE]

        self.assertEqual(steam["draw_intervals"], len(course))
        self.assertEqual(steam["settling_steps"], 1)
        self.assertEqual(
            steam["plant_step_count"], len(course) + steam["settling_steps"],
            "the steam draw advanced the machine a different number of times from the intervals "
            "it ran, so what it reported is not one interval per step")

        steam_c = closed_loop.QUANTITY_KEYS.index("steam-c")
        self.assertAlmostEqual(
            steam["trajectory_baseline"][steam_c], FINDINGS["steam_ready_c"], delta=0.1,
            msg="the draw did not begin at the ready state the declaration names")

        self.assertEqual(
            [reported["drawing"] for reported in steam["trajectory"]],
            [rate > 0 for _, rate in course],
            "the wand's microswitch did not follow the course, so the loop was answering a draw "
            "the course did not ask for")

        first_feed = min(reported["interval"] for reported in steam["trajectory"]
                         if reported["feed_permille"] > 0)
        first_draw = min(at for at, (_, rate) in enumerate(course) if rate > 0)
        margin_ms = sweep._declared_figure(
            FINDINGS["declaration"],
            sweep._declared_word(sweep.STEAM_DECLARATION_HEADER,
                                 "STEAM_CONTROL_DECLARATION_MARGIN_INTERVAL_WORD"))
        self.assertGreaterEqual(
            (first_feed - first_draw) * sweep.INTERVAL_MS, margin_ms,
            "feed engaged before the declared margin-building interval had elapsed, so the draw "
            "this sweep measures is not the one the design describes")

    # The steam draw prints its quantities under the same names the brew draw
    # does, and both under the names the parsers look up. The two tables are
    # separate declarations in two translation units, so nothing but a check
    # keeps them from drifting -- and a name that moved in one of them would
    # have a quantity read into the wrong column or not read at all.
    def test_the_two_draws_report_their_quantities_under_the_same_names(self):
        keys = _quantity_keys(os.path.join(FIRMWARE_DIR, "src", "app", "native", "steam_draw.c"))
        brew_keys = _quantity_keys(
            os.path.join(FIRMWARE_DIR, "src", "app", "native", "cross_tier_draw.c"))
        self.assertEqual(keys, closed_loop.QUANTITY_KEYS)
        self.assertEqual(brew_keys, closed_loop.QUANTITY_KEYS)

    # The brew draw reports the temperature an extraction is judged by under the
    # name the sweep reads it back by. It is not one of the compared quantities
    # and so is not covered by the check above; without it the sweep would be
    # ranking coefficients by what they do to the block rather than to the
    # drink, which for the two coefficients that stand between them is a
    # different question entirely.
    def test_the_brew_draw_reports_the_temperature_the_delivery_is_judged_by(self):
        source = os.path.join(FIRMWARE_DIR, "src", "app", "native", "cross_tier_draw.c")
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('#define DELIVERED_KEY "%s"' % cross_tier.OUTLET_KEY, text)

        delivered = FINDINGS["reference"][sweep.BREW_SIDE]["delivered"]
        self.assertEqual(len(delivered), len(FINDINGS["courses"][sweep.BREW_SIDE]))
        self.assertTrue(all(value is not None for value in delivered))


def _quantity_keys(path):
    """The names one draw's source declares it reports its quantities under.

    Read out of the source rather than imported, for the reason the cross-tier
    suite beside this one gives: these are C, and neither can be asked for its
    list by running it.
    """
    with open(path, encoding="utf-8") as handle:
        found = re.search(r"quantity_key\[\]\s*=\s*\{(.*?)\}", handle.read(), re.DOTALL)
    if not found:
        raise AssertionError("%s declares no quantity_key[] to report under" % path)
    return tuple(re.findall(r'"([^"]+)"', found.group(1)))


if __name__ == "__main__":
    unittest.main()
