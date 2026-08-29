"""What the margin a commanded target keeps from the coffee block's protection
comes to, and what a delivery does at every corner of the declared error it was
sized from.

The analysis itself is in emulation/tools/run_protection_margin.py, which reads
the mapping back out of the control path that enforces it and runs a delivery
against every corner that mapping names. This suite is what judges the answer,
and what keeps the committed record from drifting away from the method that
produced it: every figure the record carries is regenerated here and compared,
not only the verdicts. A record comparing verdicts alone would let each figure
drift as far as it liked until one of them happened to cross a threshold, and
the figures are what a verdict can be argued with from.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))

sys.path.insert(0, os.path.join(EMULATION_DIR, "tools"))

import run_cross_tier_check as cross_tier  # noqa: E402
import run_parameter_sweep as sweep  # noqa: E402
import run_protection_margin as margin  # noqa: E402

FINDINGS = None

#: The coefficient a replacement model is written with, and what it is written
#: as. The coffee element's rating, because it is the one figure on this machine
#: that has actually been measured and the one a replacement machine is most
#: likely to differ in -- and because it is a coefficient the mapping already
#: shows a path to the trip-point gap for, so a replacement moves figures rather
#: than leaving the record identical for a reason nobody notices.
REPLACEMENT_COEFFICIENT = "brew.heater_power_w"
REPLACEMENT_VALUE = "1200.0"

#: How far a regenerated figure may sit from the committed one before the
#: committed record is out of date rather than merely rounded differently.
#:
#: The relative part is the one the suites beside this use, and for the reason
#: they give: the analysis is deterministic on one host and need not be across
#: hosts, because the plant model's arithmetic reaches the platform's own maths
#: library. The absolute floor is a hundredth of the band a delivery is held to,
#: which is the coarsest thing a verdict here can turn on -- a figure agreeing
#: to that cannot move one.
FIGURE_TOLERANCE = 0.01


def setUpModule():
    global FINDINGS
    FINDINGS = margin.run_once()


def _committed_record():
    with open(margin.REPORT_PATH, encoding="utf-8") as handle:
        return handle.read()


def _produced_record():
    return margin.report_text(FINDINGS)


def _near(before, after, floor):
    """Whether a committed figure and a regenerated one are the same figure."""
    return abs(before - after) <= FIGURE_TOLERANCE * max(abs(after), floor)


def _floor():
    return FIGURE_TOLERANCE * FINDINGS["band_c"]


class TheMarginIsTheWorstSingleCornerOfTheDeclaredError(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: The commanded
    margin against the protection trip point widens with each declared
    coefficient's model error, combined by worst-corner enumeration.
    """

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: the margin is the
    # largest single-corner degradation and never a sum across corners nor a
    # root-sum-square of them, which is what
    # DEC-MARGIN-COMBINES-DECLARED-ERROR-BY-WORST-CASE rules. Asserted against
    # the corners the loop itself reported rather than against a figure this
    # file recomputes: what is being checked is that the loop combined them the
    # way the decision says, so a second arithmetic here would be checking this
    # file against itself.
    def test_the_margin_is_the_worst_single_corner_and_not_a_sum_or_a_root_sum_square(self):
        record = FINDINGS["shipped"]["margin"]
        contributions = [corner["contribution_c"] for corner in FINDINGS["shipped"]["corners"]
                         if corner["ran"] and corner["contribution_c"] > 0.0]
        self.assertTrue(contributions,
                        "no corner of the declared error costs the trip-point gap anything, so "
                        "the margin is the un-widened gap and this case establishes nothing")

        self.assertAlmostEqual(
            record["worst_c"], max(contributions), places=5,
            msg="the margin's worst corner is not the widest contribution the enumeration "
                "reported")
        self.assertAlmostEqual(
            record["widened_c"],
            record["unwidened_c"] + max(contributions) + record["sensing_error_c"], places=5,
            msg="the widened margin is not the un-widened gap plus the worst corner plus the "
                "declared sensing error")
        self.assertEqual(len(contributions), record["contributing"])

        if len(contributions) >= 2:
            summed = sum(contributions)
            squared = sum(value * value for value in contributions) ** 0.5
            self.assertLess(record["worst_c"], summed,
                            "the margin is the sum of every corner's contribution rather than "
                            "the worst single corner")
            self.assertLess(record["worst_c"], squared,
                            "the margin is the root-sum-square of the corners' contributions "
                            "rather than the worst single corner")

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: strictly larger than
    # the un-widened gap wherever a coefficient with a path to that gap carries
    # a nonzero declared error, and never narrower than it anywhere -- a corner
    # that carries the machine away from the trip point has made the gap safer,
    # and a margin sized on the strength of it would be sized by the corner that
    # did not happen.
    def test_the_margin_is_wider_than_the_gap_and_never_narrower(self):
        record = FINDINGS["shipped"]["margin"]
        self.assertGreater(record["widened_c"], record["unwidened_c"],
                           "no declared error widened the margin at all, so nothing here is "
                           "reading the budget")
        for corner in FINDINGS["shipped"]["corners"]:
            with self.subTest(corner=corner["which"]):
                self.assertGreaterEqual(corner["contribution_c"], 0.0,
                                        "a corner contributed a negative figure, so a corner "
                                        "moving the gap the safe way is narrowing the margin")

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: one corner per
    # coefficient run independently, plus one corner per stated joint
    # dependence run together. The enumeration has to carry the joint corner as
    # its own entry moving more than one coefficient, or the one case where two
    # declared errors are stated to move together is being weighed as though
    # they moved apart.
    def test_the_enumeration_carries_the_stated_joint_corner_moving_more_than_one_coefficient(
            self):
        joint = [corner for corner in FINDINGS["shipped"]["corners"] if corner["joint"]]
        self.assertEqual(1, len(joint),
                         "the enumeration carries %d joint corners, and the description states "
                         "one dependence" % len(joint))
        self.assertGreater(joint[0]["moves"], 1,
                           "the joint corner moves one coefficient, so it is an independent "
                           "corner wearing the joint corner's name")
        self.assertEqual(len(joint[0]["writes"]), joint[0]["moves"])
        self.assertEqual("low", joint[0]["end"],
                         "the joint corner is not the sag it stands for")

        independent = [corner for corner in FINDINGS["shipped"]["corners"] if not corner["joint"]]
        self.assertEqual(len(independent), 2 * len(set(corner["at"] for corner in independent)),
                         "the enumeration does not carry both ends of every coefficient")


class ADeliveryLandsWithinToleranceAtEveryDeclaredErrorCorner(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: A delivery lands
    within tolerance at the widened margin, at every independent and joint
    declared-error corner.
    """

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: the delivery is
    # checked to land within its own tolerance band at that corner. Every corner
    # the enumeration ran, including the joint one, which is the only corner an
    # independent sweep cannot reach.
    def test_every_corner_delivered_within_the_declared_band(self):
        self.assertTrue(FINDINGS["verdicts"],
                        "no corner of the declared error was delivered against at all, so "
                        "nothing here was established")
        for verdict in FINDINGS["verdicts"]:
            corner = verdict["corner"]
            if not verdict["claimed"]:
                continue
            with self.subTest(corner=corner["which"]):
                self.assertTrue(
                    verdict["within_band"],
                    "corner %d -- %s, %s at %g of nominal -- left the delivery %.4f degrees from "
                    "the %.4f degree target it was commanded at, against a declared band of %.4f"
                    % (corner["which"], "joint mains droop" if corner["joint"] else "independent",
                       ", ".join(corner["writes"]), corner["factor"],
                       verdict["worst_departure_c"], FINDINGS["target_c"], FINDINGS["band_c"]))

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: at every independent
    # and joint corner -- so the joint one has to have been delivered against
    # and not merely enumerated.
    def test_the_joint_corner_was_delivered_against_to_the_same_standard(self):
        for side in ("verdicts", "steam_verdicts"):
            joint = [verdict for verdict in FINDINGS[side] if verdict["corner"]["joint"]]
            with self.subTest(side=side):
                self.assertEqual(1, len(joint),
                                 "the joint corner was not delivered against to the same "
                                 "standard the independent corners were")
                self.assertTrue(joint[0]["claimed"] and joint[0]["within_band"])

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: on both the coffee
    # side and the steam side. The steam loop sizes a margin of its own against
    # a trip point of its own out of the same declared error, and a draw at
    # every corner of it has to come to rest inside the band the design declares
    # for it.
    def test_every_steam_corner_drew_within_the_declared_band(self):
        self.assertTrue(FINDINGS["steam_verdicts"],
                        "no corner of the declared error was drawn against on the steam side")
        floor, ceiling = FINDINGS["steam_band_milli_bar"]
        for verdict in FINDINGS["steam_verdicts"]:
            corner = verdict["corner"]
            if not verdict["claimed"]:
                continue
            with self.subTest(corner=corner["which"]):
                self.assertTrue(
                    verdict["within_band"],
                    "corner %d -- %s, %s at %g of nominal -- left the delivered pressure at %d "
                    "milli-bar, outside the declared band of %d to %d"
                    % (corner["which"], "joint mains droop" if corner["joint"] else "independent",
                       ", ".join(corner["writes"]), corner["factor"],
                       verdict["worst_milli_bar"], floor, ceiling))

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: a coefficient the
    # plant description declares one-sided is run at its single declared corner,
    # to the same standard as a two-sided coefficient's pair. The other end is
    # still enumerated -- the margin weighs it, which can only widen the margin
    # -- and is reported as a machine the description does not claim rather than
    # as a delivery that passed or failed.
    def test_the_end_the_description_does_not_claim_is_reported_and_not_judged(self):
        unclaimed = [verdict for verdict in FINDINGS["verdicts"] + FINDINGS["steam_verdicts"]
                     if not verdict["claimed"]]
        self.assertEqual(
            2 * len(margin.ONE_SIDED), len(unclaimed),
            "the description calls %d coefficients one-sided and %d rows across the two sides "
            "were reported as unclaimed" % (len(margin.ONE_SIDED), len(unclaimed)))
        for verdict in unclaimed:
            with self.subTest(corner=verdict["corner"]["which"]):
                self.assertEqual("not-claimed", margin._verdict_word(verdict))

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: the corner is the
    # machine and not the model the loop drives from. A run whose control path
    # reconstructed from the very coefficients the machine was perturbed with
    # would carry no model error at all, and every corner would land in band
    # whatever the margin was -- so what is asserted here is that the two
    # descriptions the run was given are different files.
    def test_the_loop_believed_the_shipped_description_while_the_machine_moved(self):
        for verdict in FINDINGS["verdicts"]:
            with self.subTest(corner=verdict["corner"]["which"]):
                self.assertNotEqual(
                    os.path.abspath(verdict["description"]),
                    os.path.abspath(FINDINGS["description"]),
                    "the corner was delivered against the shipped description itself, so the "
                    "machine was never perturbed")


class WhereACommandedTargetActuallyStopsIsAFinding(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: the delivery is
    commanded at the widened margin rather than at a nominal target — which is a
    claim about which of the admission path's ceilings actually stops a command
    on this machine, and therefore a finding the record has to carry rather than
    an assumption the method may make.
    """

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: commanded at the
    # widened margin. The sweep is commanded at the highest target the loop
    # takes, which is as close to the margin as a delivery on this machine can
    # be commanded -- and whether that is the margin itself or some earlier
    # ceiling decides what the sweep is evidence for. The record has to say
    # which, in the words the loop itself reports, because a reader taking a
    # sweep stopped by the saturation ceiling for evidence about the protection
    # margin would be taking it for something it is not.
    def test_the_record_names_the_bound_that_stops_a_commanded_target(self):
        record = _committed_record()
        self.assertIn(FINDINGS["shipped"]["capping_bound_name"], record)
        self.assertEqual(FINDINGS["margin_binds"],
                         FINDINGS["shipped"]["capping_bound_name"] == margin.MARGIN_BOUND)
        if FINDINGS["margin_binds"]:
            self.assertTrue(FINDINGS["shipped"]["trip_known"],
                            "the margin is the bound that stops a command and the loop's own "
                            "refusal reported no trip point, so the record cannot say what the "
                            "margin is measured against")
            self.assertAlmostEqual(
                FINDINGS["target_c"],
                FINDINGS["shipped"]["trip_c"] - FINDINGS["shipped"]["margin"]["widened_c"],
                places=2,
                msg="the command was not stopped at the trip point less the widened margin, so "
                    "the sweep is not commanded at the margin's own edge")
        else:
            self.assertIn("not that bound", record,
                          "the protection margin refuses nothing on this machine and the record "
                          "does not say so, so it reads as evidence the margin was exercised")

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: the widened margin
    # is what the controller enforces rather than a figure computed and left
    # unused. Where some other ceiling is presently tighter, that claim is only
    # answerable by asking how far the declared error would have to move before
    # the margin overtakes it -- and it has to be a figure the method narrows on
    # rather than a sentence somebody wrote, or nothing notices when a corrected
    # coefficient moves it.
    def test_the_record_says_how_far_the_declared_error_is_from_binding(self):
        if FINDINGS["margin_binds"]:
            self.assertIsNone(FINDINGS["widening"])
            return
        widening = FINDINGS["widening"]
        self.assertIsNotNone(widening)
        self.assertGreater(widening["widened_to"], widening["declared"],
                           "the margin does not bind at the declared error and the widening the "
                           "method found is no wider than it")
        self.assertIn(widening["coefficient"], _committed_record())
        self.assertIn(margin.FIGURE_FORMAT % widening["widened_to"], _committed_record())


class TheMappingAndTheCornerVerdictsAreCommitted(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C3: The error-to-margin
    mapping and its corner verdicts are committed in a repeatable form.
    """

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C3: the mapping is
    # committed. The committed record has to be the one this method presently
    # produces, corner for corner and figure for figure -- a record that has
    # drifted from the method beside it is a mapping nobody can reproduce, which
    # is the whole of what this criterion is about.
    def test_the_committed_mapping_is_the_one_this_method_presently_produces(self):
        was = margin.mapping_rows(_committed_record())
        now = margin.mapping_rows(_produced_record())
        self.assertTrue(was, "%s carries no mapping table" % margin.REPORT_PATH)
        self.assertEqual([row[:4] for row in was], [row[:4] for row in now],
                         "the committed record covers a different set of corners, or covers them "
                         "in a different order, from the one this analysis now produces. Re-run "
                         "firmware/emulation/tools/run_protection_margin.py")
        for before, after in zip(was, now):
            with self.subTest(corner=before[0]):
                self.assertEqual(before[4:7], after[4:7])
                self.assertTrue(
                    _near(float(before[7]), float(after[7]), _floor()),
                    "the committed record gives corner %s a contribution of %s and this analysis "
                    "now gives it %s. Re-run "
                    "firmware/emulation/tools/run_protection_margin.py"
                    % (before[0], before[7], after[7]))
        self.assertEqual([int(row[0]) for row in was],
                         [corner["which"] for corner in FINDINGS["shipped"]["corners"]],
                         "the committed record does not carry every corner the enumeration ran")

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C3: and its corner
    # verdicts. Every figure and not only the verdict word: a check comparing
    # verdicts alone would let each departure drift as far as it liked until one
    # of them happened to cross the band, and the departures are what a verdict
    # can be argued with from.
    def test_the_committed_verdicts_are_the_ones_this_method_presently_produces(self):
        was = margin.verdict_rows(_committed_record())
        now = margin.verdict_rows(_produced_record())
        self.assertTrue(was, "%s carries no verdict table" % margin.REPORT_PATH)
        self.assertEqual([row[:3] for row in was], [row[:3] for row in now],
                         "the committed record's verdicts cover a different set of corners from "
                         "the one this analysis now produces. Re-run "
                         "firmware/emulation/tools/run_protection_margin.py")
        for before, after in zip(was, now):
            with self.subTest(corner=before[0]):
                self.assertEqual(before[3], after[3])
                self.assertEqual(before[5], after[5])
                self.assertTrue(
                    _near(float(before[4]), float(after[4]), _floor()),
                    "the committed record gives corner %s a worst departure of %s and this "
                    "analysis now gives it %s. Re-run "
                    "firmware/emulation/tools/run_protection_margin.py"
                    % (before[0], before[4], after[4]))

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C3: committed against a
    # replacement model rather than only against this one. The record names
    # where a commanded target stops and what the margin came to, and both move
    # with the description -- a record carrying them and not the state of the
    # files they were taken against is one nobody can tell is stale.
    def test_the_committed_record_names_the_files_it_was_run_against_as_they_stand(self):
        record = _committed_record()
        for path in (FINDINGS["description"], FINDINGS["limits"], FINDINGS["tolerance"],
                     FINDINGS["declaration"]):
            with self.subTest(path=path):
                self.assertIn(margin._relative(path), record)
                self.assertIn(sweep.digest_of(path), record,
                              "%s has changed since the record was taken. Re-run "
                              "firmware/emulation/tools/run_protection_margin.py" % path)

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C3: repeatable against a
    # replacement model -- the same method pointed at another description has to
    # produce that description's mapping with nothing here edited, or the record
    # is a scratch calculation about one machine wearing a method's name.
    def test_the_same_method_run_against_a_replacement_model_needs_no_edit_to_it(self):
        replacement = cross_tier.description_with(
            REPLACEMENT_COEFFICIENT, REPLACEMENT_VALUE,
            os.path.join(FINDINGS["workspace"], "margin-replacement.params"),
            source=FINDINGS["description"])

        elsewhere = margin.run(
            description=replacement, limits=FINDINGS["limits"],
            executable=FINDINGS["executable"],
            workspace=os.path.join(FINDINGS["workspace"], "replacement"))

        self.assertNotEqual(
            elsewhere["workspace"], FINDINGS["workspace"],
            "the replacement model wrote its corner descriptions where the shipped machine's run "
            "wrote its own, so one of the two is standing on files the other wrote")
        self.assertEqual(
            [corner["writes"] for corner in elsewhere["shipped"]["corners"]],
            [corner["writes"] for corner in FINDINGS["shipped"]["corners"]],
            "the replacement model was enumerated over a different set of corners")

        written = margin.report_text(elsewhere)
        self.assertIn(sweep.digest_of(replacement), written)
        self.assertNotIn(sweep.digest_of(FINDINGS["description"]), written)

        moved = [corner["which"] for corner, was in
                 zip(elsewhere["shipped"]["corners"], FINDINGS["shipped"]["corners"])
                 if not _near(corner["contribution_c"], was["contribution_c"], _floor())]
        self.assertTrue(
            moved,
            "running a machine whose coffee element is %s W rather than the measured figure "
            "produced the same contribution at every corner, so the method is not reading the "
            "description it was pointed at" % REPLACEMENT_VALUE)

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C3: the mapping and its
    # corner verdicts, on both sides. The steam loop's margin is a second figure
    # sized from the same declared error against a different trip point, and a
    # record carrying only the coffee side's would leave half of what this
    # criterion commits uncommitted.
    def test_the_committed_steam_tables_are_the_ones_this_method_presently_produces(self):
        for reader in (margin.steam_mapping_rows, margin.steam_verdict_rows):
            was = reader(_committed_record())
            now = reader(_produced_record())
            with self.subTest(table=reader.__name__):
                self.assertTrue(was, "%s carries no %s table"
                                % (margin.REPORT_PATH, reader.__name__))
                self.assertEqual([row[:3] for row in was], [row[:3] for row in now],
                                 "the committed record's steam tables cover a different set of "
                                 "corners from the one this analysis now produces. Re-run "
                                 "firmware/emulation/tools/run_protection_margin.py")
                self.assertEqual([row[-1] for row in was], [row[-1] for row in now])

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C3: committed -- as a
    # record the method writes rather than one somebody maintains beside it, and
    # one that says so of itself. Both halves are asked for by name rather than
    # assumed to be somewhere in it.
    def test_the_committed_record_says_it_is_generated_and_carries_every_section(self):
        record = _committed_record()
        self.assertIn("run_protection_margin.py", record)
        self.assertIn("Do not edit by hand", record)
        for heading in (margin.MODEL_HEADING, margin.STANDING_HEADING, margin.MAPPING_HEADING,
                        margin.VERDICT_HEADING, margin.STEAM_MAPPING_HEADING,
                        margin.STEAM_VERDICT_HEADING, margin.REFUSED_HEADING):
            with self.subTest(heading=heading):
                self.assertIn(heading, record)

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C3: the record has to
    # carry the corners it could not deliver against as their own finding. A
    # corner the structure would not admit as a machine and a corner that was
    # delivered against and landed in band are opposite findings, and a record
    # that dropped the first would read as one where every corner was checked.
    def test_the_committed_record_accounts_for_every_corner_the_enumeration_covers(self):
        for side, verdicts, corners in (
                ("coffee", FINDINGS["verdicts"], FINDINGS["shipped"]["corners"]),
                ("steam", FINDINGS["steam_verdicts"], FINDINGS["shipped"]["steam_corners"])):
            delivered = set(verdict["corner"]["which"] for verdict in verdicts)
            undelivered = set(corner["which"] for corner, _ in FINDINGS["refused"]
                              if corner in corners)
            with self.subTest(side=side):
                self.assertEqual(
                    delivered | undelivered, set(corner["which"] for corner in corners),
                    "a corner of the enumeration is neither delivered against nor accounted for")
                self.assertEqual(set(), delivered & undelivered)
        record = _committed_record()
        for corner, why in FINDINGS["refused"]:
            with self.subTest(corner=corner["which"]):
                self.assertIn(why, record)


class TheDeclaredSensingErrorAddsToTheCommandedMargin(unittest.TestCase):
    """SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-SENSING-ERROR.C1-C3: the declared
    sensing error on each loop's guarded channel is added on top of the
    model-error margin, and the sensing-error mapping and corner verdicts are
    committed in the same repeatable form the model-error margin already uses.
    """

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-SENSING-ERROR.C1: the reading names
    # a nonzero declared sensing error on both loops -- carried explicitly
    # rather than folded silently into the worst-corner figure -- and that
    # figure adds to, rather than competes with, the model-error corner: the
    # combined margin is exactly the un-widened gap plus the worst corner plus
    # the declared sensing error, on both loops.
    def test_both_loops_carry_a_nonzero_declared_sensing_error(self):
        for side, record in (("coffee", FINDINGS["shipped"]["margin"]),
                             ("steam", FINDINGS["shipped"]["steam_margin"])):
            with self.subTest(side=side):
                self.assertGreater(record["sensing_error_c"], 0.0,
                                   "this loop's margin reading carries no declared sensing error "
                                   "at all")
                self.assertAlmostEqual(
                    record["widened_c"],
                    record["unwidened_c"] + record["worst_c"] + record["sensing_error_c"],
                    places=5,
                    msg="the widened margin is not the un-widened gap plus the worst corner "
                        "plus the declared sensing error")

    # SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-SENSING-ERROR.C3: the committed
    # record carries the declared sensing error as its own figure, on both
    # loops, rather than only the combined total -- so a reader can tell how
    # much of the margin the model-error enumeration earned and how much the
    # declared sensing error added on top, on the same terms the record
    # already separates the un-widened gap from what the enumeration widened
    # it by.
    def test_the_committed_record_names_the_declared_sensing_error_on_both_loops(self):
        record = _committed_record()
        for side, margin_record in (("coffee", FINDINGS["shipped"]["margin"]),
                                    ("steam", FINDINGS["shipped"]["steam_margin"])):
            with self.subTest(side=side):
                self.assertIn(
                    margin.FIGURE_FORMAT % margin_record["sensing_error_c"], record,
                    "the committed record does not name %s's declared sensing error figure"
                    % side)
        self.assertIn("declared sensing error", record)


if __name__ == "__main__":
    unittest.main()
