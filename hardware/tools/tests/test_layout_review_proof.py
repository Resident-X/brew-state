#!/usr/bin/env python3
"""The layout review proof command: one command that seeds, writes the review folder, runs the fanned-out form on the review kit's
command at two replicas and at three, and judges it against the recorded single-reviewer runs.

The kit's command runs over a stand-in for the agent command line, so no model and no KiCad is used, and the real agent command
line is never run. The seeded copy, its views and its seed list are synthetic stand-ins for what the seeding command writes,
placed where the proof command expects them; the baselines are synthetic runs of the same synthetic seed list.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import layout_fixtures as fx  # noqa: E402
import layout_review_proof as lrp  # noqa: E402
import review_caller_layout  # noqa: E402
import review_seed  # noqa: E402
import test_review_caller_layout as layout_tests  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import executor as ex  # noqa: E402
from review_kit import proof, store  # noqa: E402
from review_kit import session as sess  # noqa: E402

kit_small = review_caller_layout.SMALL_MODEL
REPO = os.path.dirname(os.path.dirname(TOOLS))
SEEDS = [{"id": "S1", "item": "FLOOR-1"}, {"id": "S2", "item": "CLOCK-1"}, {"id": "S3", "item": "GROUND-1"}]
ALL_FAIL = {"FLOOR-1": "fail", "CLOCK-1": "fail", "GROUND-1": "fail"}
TREE = "d" * 40
PROMPT = "p" * 64
REPORT_LINES = [f"DESIGN | {review_seed.DESIGN}/x.kicad_pro | PASS", f"FIGURE | {review_seed.DESIGN}/x.kicad_pro | WORK-2 | 1.3",
                "RESULT | PASS"]


def single(run_id, found, wall=1000.0, cost=5.0):
    return proof.RunOutcome(run_id, proof.SINGLE, "tool", "seeded", tuple(found), (), {}, {s: ("single",) for s in found},
                            {s["id"]: ("single",) for s in SEEDS}, (proof.SessionRecord("single", wall, cost, 1, 1, 1),), wall, cost,
                            ("first_call_read",))


def baselines_file(path, runs=None, seeds=SEEDS, design=TREE, model=lrp.BASELINE_MODEL):
    """A baselines file of synthetic single runs: one found two of the three seeds, the other all three."""
    runs = runs if runs is not None else [single("one", ["S1", "S2"]), single("two", ["S1", "S2", "S3"])]
    key = proof.BaselineKey(proof.seed_list_hash(SEEDS), design, model, proof.SINGLE, PROMPT)
    if seeds is not SEEDS:
        key = proof.BaselineKey(proof.seed_list_hash(seeds), design, model, proof.SINGLE, PROMPT)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"version": proof.BASELINES_VERSION, "source": "synthetic", "seeds": seeds,
                   "baselines": [{"key": key.as_dict(), "runs": [run.as_dict() for run in runs]}]}, handle)
    return path


class Proofed(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="layout-proof-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.work = os.path.join(self.root, "work")
        self.source = fx.make_repo(os.path.join(self.root, "source"), design=review_seed.DESIGN)
        self.baselines = baselines_file(os.path.join(self.root, "baselines.json"))
        self.log = os.path.join(self.root, "agent.log")
        self.scenario_path = os.path.join(self.root, "scenario.json")
        self.program = os.path.join(self.root, "agent")
        fx.write(self.program, layout_tests.STUB.replace("    found = 0\n", '    found = len(tables["Findings"])\n').replace("PYTHON", sys.executable, 1).replace("TOOLS", repr(TOOLS)))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        for patch in (mock.patch.dict(os.environ, {ex.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path,
                                                   "STUB_LOG": self.log}),
                      mock.patch.object(kit_caller, "load", layout_tests.load_with_synthetic_couplings)):
            patch.start()
            self.addCleanup(patch.stop)
        self.scenario(verdicts=ALL_FAIL)

    def scenario(self, **values):
        fx.write(self.scenario_path, json.dumps(values))

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def seed(self, work, kicad, resvg):
        """What the seeding command leaves, synthetic: the kept work tree with a committed board, the folder it rendered into and
        the seed list."""
        inputs = fx.make_views(os.path.join(work, "inputs"))
        review = os.path.join(work, lrp.SEEDED)
        shutil.copytree(inputs["views"], os.path.join(review, review_seed.VIEWS))
        shutil.copytree(inputs["placement"], os.path.join(review, review_seed.PLACEMENT))
        fx.write(os.path.join(review, review_seed.REPORT), "\n".join(REPORT_LINES) + "\n")
        fx.write(os.path.join(work, lrp.SEEDS), json.dumps({"design": review_seed.DESIGN, "seeds": SEEDS}))
        return {"repository": self.source, "commit": fx.git(self.source, "rev-parse", "HEAD")}

    def go(self, *extra, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        status = lrp.main(["--work", self.work, *extra], out=out, err=err, seed_runner=kwargs.pop("seed_runner", self.seed),
                          baselines=kwargs.pop("baselines", self.baselines), tree=kwargs.pop("tree", lambda: TREE),
                          documents_repo=self.source, **kwargs)
        return status, out.getvalue(), err.getvalue()

    def record(self):
        with open(os.path.join(self.work, lrp.RECORD), encoding="utf-8") as handle:
            return json.load(handle)


class TheCommand(Proofed):
    def test_one_command_seeds_runs_both_rounds_on_the_kits_command_and_writes_the_kits_record(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: A fanned-out blind review of the layout review proof's seeded copy meets the kit's pooled criterion against the recorded single-reviewer runs: the one command runs the fanned-out form at the baselines' model with two replicas and again with three, and judges the first with a cost multiple of 2.0
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        calls = self.calls()
        self.assertEqual(len(calls), (1 + 2 * 2) + (2 + 3 * 2), "a shared context and two groups of two replicas, then a second shared context for the small model and two groups of three")
        self.assertEqual(len([call for call in calls if call["resume"] is None]), 3,
                         "a shared context for the design loop, two for the pre-order round, and no single reviewer")
        models = [call["args"][call["args"].index("--model") + 1] for call in calls]
        self.assertEqual(sorted(set(models)), sorted({lrp.BASELINE_MODEL, kit_small}))
        self.assertEqual(models.count(lrp.BASELINE_MODEL), 1 + 2 * 2, "the pre-order round's mid-tier root and its first two replicas of each group")
        self.assertEqual(models.count(kit_small), (1 + 2 * 2) + (1 + 2), "the design loop's root and four forks, and the pre-order round's small-tier root and third replicas")
        record = self.record()
        self.assertEqual(record["verdict"]["status"], "pass")
        self.assertEqual(record["cost_multiple"], 1.25)
        self.assertEqual(record["layout"]["models"], {"design-loop": kit_small, "pre-order": lrp.BASELINE_MODEL})
        self.assertEqual(record["layout"]["baseline_model"], lrp.BASELINE_MODEL)
        self.assertEqual(record["layout"]["seeded_commit"], fx.git(self.source, "rev-parse", "HEAD"))
        self.assertEqual(record["seed_list_sha256"], proof.seed_list_hash(SEEDS))
        self.assertEqual([key["form"] for key in record["keys"]], [proof.SINGLE])
        self.assertEqual(len(record["single_runs"]), 2)
        self.assertEqual(record["fanned_runs"][0]["seeds_found"], ["S1", "S2", "S3"])
        for seed, who in record["seed_replicas"].items():
            self.assertEqual(len(next(iter(who.values()))), 2, f"{seed} is raised by both replicas")
        self.assertEqual({seed: len(who) for seed, who in record["pre_order"]["seed_replicas"].items()}, {"S1": 3, "S2": 3, "S3": 3})
        self.assertIn("PROOF | design loop on claude-haiku-5-5, pre-order on claude-sonnet-5-5 (third replica on the small tier) | baselines on claude-sonnet-5-5", text)
        self.assertIn("cost multiple 1.25", text)
        self.assertIn("CRITERION | PROOF pass", text)
        self.assertIn("PRE-ORDER | three replicas | seeds 3 of 3", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | WRITTEN"))
        with open(os.path.join(self.work, lrp.TEXT), encoding="utf-8") as handle:
            self.assertEqual(handle.read().splitlines(), [line for line in text.splitlines() if not line.startswith("RESULT")])
        as_json = io.StringIO()
        shutil.rmtree(self.work)
        os.remove(self.log)
        self.assertEqual(lrp.main(["--work", self.work, "--json", "--only", "design-loop"], out=as_json, err=io.StringIO(),
                                  seed_runner=self.seed, baselines=self.baselines, tree=lambda: TREE, documents_repo=self.source), 0)
        document = json.loads(as_json.getvalue())
        self.assertEqual((document["result"], document["record"]["verdict"]["status"]), ("WRITTEN", "pass"))

    def test_the_layout_facts_and_the_round_file_are_in_the_folder_the_runs_read_and_the_seeding_keeps_its_work_tree(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag
        self.go("--dry")
        folder = os.path.join(self.work, lrp.FOLDER)
        content = fx.round_file(folder)
        self.assertEqual((content["number"], content["kind"]), (1, "full"))
        self.assertEqual(content["commit"], fx.git(self.source, "rev-parse", "HEAD"))
        self.assertEqual(content["check"], REPORT_LINES[:2])
        self.assertEqual(content["views"], lrp.VIEW_COMMANDS)
        self.assertTrue(os.path.isfile(os.path.join(folder, "layout-facts.txt")))
        self.assertTrue(os.path.isfile(os.path.join(folder, review_seed.DESIGN, "board.kicad_pcb")))
        self.assertFalse(os.path.exists(os.path.join(folder, review_seed.DESIGN, "layout-review.md")))
        self.assertFalse(os.path.exists(os.path.join(folder, "seeds.json")))
        done = mock.Mock(returncode=0, stdout="SEEDS | 21 seeds | f\nKEPT | /kept/repository | abc123\nRESULT | WRITTEN | out\n", stderr="")
        with mock.patch.object(lrp.subprocess, "run", return_value=done) as run:
            kept = lrp.run_seed(self.work, "kicad", "resvg")
        self.assertEqual(kept, {"repository": "/kept/repository", "commit": "abc123"})
        argv = run.call_args[0][0]
        self.assertEqual(argv[argv.index("--keep-work-tree") + 1], os.path.join(self.work, lrp.KEPT_TREE))
        self.assertEqual(argv[argv.index("--seeds") + 1], os.path.join(self.work, lrp.SEEDS))
        for returncode, error in ((1, lrp.Refused), (2, lrp.board_check.CannotRun)):
            with mock.patch.object(lrp.subprocess, "run", return_value=mock.Mock(returncode=returncode, stdout="REFUSED | x", stderr="no kicad")):
                with self.assertRaises(error):
                    lrp.run_seed(self.work, "kicad", "resvg")
        with mock.patch.object(lrp.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="RESULT | WRITTEN", stderr="")):
            with self.assertRaises(lrp.Refused):
                lrp.run_seed(self.work, "kicad", "resvg")

    def test_a_folder_the_folder_command_refuses_stops_the_command_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the review folder the folder command assembles; a report with no check report cannot be assembled and no session starts
        def bare(work, kicad, resvg):
            seeded = self.seed(work, kicad, resvg)
            os.remove(os.path.join(work, lrp.SEEDED, review_seed.REPORT))
            return seeded
        with self.assertRaises((lrp.Refused, OSError)):
            lrp.write_folder(self.work, bare(self.work, "k", "r"))
        self.assertEqual(self.calls(), [])

    def test_the_dry_mode_prints_each_plan_and_its_predicted_cost_and_time_and_starts_no_session(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: a plan mode that prints the plan and the predicted cost and time without calling the model, beside the bounds of the cost multiple of 1.25 and half the single mean time
        status, text, err = self.go("--dry")
        self.assertEqual(status, 0, text + err)
        self.assertEqual(self.calls(), [], "the model is not called")
        self.assertFalse(os.path.exists(os.path.join(self.work, lrp.RECORD)))
        for name in ("design-loop", "pre-order"):
            self.assertFalse(os.path.exists(os.path.join(self.work, lrp.OUT_DIR, name)), "no run folder is made")
            self.assertRegex(text, rf"PLAN \| {name} \| \d replicas \| 2 groups \| \d forks")
            self.assertRegex(text, rf"PREDICTED \| {name} \| \$[0-9.]+ \| [0-9.]+ s \|")
        self.assertIn("PLAN | design-loop | 2 replicas | 2 groups | 4 forks", text)
        self.assertIn("PLAN | pre-order | 3 replicas | 2 groups | 6 forks", text)
        self.assertIn("COST MULTIPLE | 1.25 | design loop bounds: cost at most $6.25 (1.25 times the single mean $5.00), wall time at most 500 s "
                      "(half the single mean 1000 s)", text)
        self.assertIn("figures recorded, not bounded", text)
        self.assertRegex(text, r"PREDICTED \| design-loop .*cost within its bound, time within its bound")
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | PLANNED"))
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry", "--json", "--only", "pre-order")
        self.assertEqual(status, 0, text + err)
        document = json.loads(text)
        self.assertEqual(list(document["plans"]), ["pre-order"])
        self.assertEqual(document["result"], "PLANNED")

    def test_no_folder_from_the_review_folders_parent_up_to_the_work_folder_holds_anything_but_the_review_folder(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: sessions with no record of the seeds, and no unit holding another unit's verdicts, so nothing sensitive is in a folder above a session's working directory
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        folder = os.path.join(self.work, lrp.FOLDER)
        self.assertEqual(os.path.dirname(os.path.dirname(folder)), self.work)
        seen = []
        above = os.path.dirname(folder)
        while above != self.work:
            self.assertEqual(os.listdir(above), [os.path.basename(folder) if not seen else os.path.basename(seen[-1])],
                             f"{above} lists only the folder below it")
            seen.append(above)
            above = os.path.dirname(above)
        self.assertEqual(seen, [os.path.join(self.work, lrp.REVIEW_TREE)])
        everything = [name for _, _, names in os.walk(os.path.join(self.work, lrp.REVIEW_TREE)) for name in names]
        for name in ("seeds.json", "proof-record.json", "record.json"):
            self.assertNotIn(name, everything)
        self.assertTrue(os.path.isfile(os.path.join(self.work, lrp.SEEDS)))
        self.assertTrue(os.path.isdir(os.path.join(self.work, lrp.SEEDED)))
        for name in ("design-loop", "pre-order"):
            self.assertTrue(store.holds_record(os.path.join(self.work, lrp.OUT_DIR, name)), name)
            self.assertFalse(os.path.exists(os.path.join(self.work, name)), "no output folder directly in the work folder")
        for call in self.calls():
            self.assertEqual(os.path.realpath(call["cwd"]), os.path.realpath(folder), "every session starts in the review folder")

    def dry_with_mean_cost(self, divisor):
        """The dry output over baselines whose mean cost makes the design loop's cost bound the predicted cost times `divisor`."""
        status, text, err = self.go("--dry", "--json", "--only", "design-loop")
        self.assertEqual(status, 0, text + err)
        predicted = json.loads(text)["plans"]["design-loop"]["predicted"]["cost_usd"]
        shutil.rmtree(self.work)
        mean = predicted * divisor / lrp.COST_MULTIPLE
        runs = [single("one", ["S1", "S2"], cost=mean), single("two", ["S1", "S2", "S3"], cost=mean)]
        status, text, err = self.go("--dry", "--only", "design-loop", baselines=baselines_file(os.path.join(self.root, f"d{divisor}.json"), runs))
        self.assertEqual(status, 0, text + err)
        shutil.rmtree(self.work)
        return text

    def test_the_dry_output_warns_when_the_prediction_is_over_a_bound_or_within_a_tenth_of_it(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: a plan mode that prints the plan and the predicted cost and time without calling the model, beside the bounds of the cost multiple of 1.25 and half the single mean time
        text = self.dry_with_mean_cost(0.8)
        self.assertRegex(text, r"PREDICTED \| design-loop .*cost over its bound")
        self.assertRegex(text, r"WARNING \| design-loop \| predicted cost \$[0-9.]+ against its bound \$[0-9.]+, over it or within 10% of it; "
                               r"a live run is likely to fail that bound or to need a second run")
        text = self.dry_with_mean_cost(1.05)
        self.assertRegex(text, r"PREDICTED \| design-loop .*cost within its bound")
        self.assertIn("WARNING | design-loop | predicted cost", text, "within a tenth below the bound is warned too")
        self.assertIn("a live run is likely to fail that bound or to need a second run", text)
        text = self.dry_with_mean_cost(1.25)
        self.assertNotIn("WARNING", text, "a prediction clear of the bound by more than a tenth is not warned")

    def test_the_dry_output_names_the_small_tier_replica_and_prices_each_model_at_its_own_prices(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the pre-order round's three replicas, the first two on the mid-tier and the third on the small-tier model with a root of its own, each predicted at its model's prices
        status, text, err = self.go("--dry", "--json")
        self.assertEqual(status, 0, text + err)
        document = json.loads(text)
        self.assertEqual(document["plans"]["design-loop"]["contexts"], [], "two replicas of one model need no second root")
        pre_order = document["plans"]["pre-order"]
        self.assertEqual([context["model"] for context in pre_order["contexts"]], [kit_small])
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry")
        self.assertIn(f"MODEL | design-loop | all 4 forks on {kit_small}", text)
        lines = [line for line in text.splitlines() if line.startswith("MODEL | pre-order")]
        self.assertEqual(len(lines), 1, text)
        self.assertIn(f"4 forks on {lrp.BASELINE_MODEL}, 2 on {kit_small} from a shared context of its own", lines[0])
        self.assertNotIn("SMALL TIER", text)
        self.assertNotIn("upper bound", text)

    def test_the_dry_prediction_of_the_small_tier_design_loop_is_below_the_bound_of_the_cost_multiple(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: both on the small-tier model ... a cost multiple of 1.25
        recorded = [single("one", ["S1", "S2"], cost=2.839), single("two", ["S1", "S2", "S3"], cost=2.839)]
        status, text, err = self.go("--dry", "--json", baselines=baselines_file(os.path.join(self.root, "recorded.json"), recorded))
        self.assertEqual(status, 0, text + err)
        plans = json.loads(text)["plans"]
        bound = lrp.COST_MULTIPLE * 2.839
        small = plans["design-loop"]["predicted"]["cost_usd"]
        self.assertLess(small, bound)
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry", "--json", "--design-model", lrp.BASELINE_MODEL,
                                    baselines=baselines_file(os.path.join(self.root, "again.json"), recorded))
        self.assertEqual(status, 0, text + err)
        self.assertGreater(json.loads(text)["plans"]["design-loop"]["predicted"]["cost_usd"], small * 2,
                           "the same design loop on the mid-tier is priced at the mid-tier's much higher prices")

    def test_a_flag_runs_only_one_of_the_two_rounds_and_the_pre_order_figures_alone_are_recorded_not_judged(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the replicas the design-loop round uses, and the pre-order round's three replicas run once and their figures recorded
        status, text, err = self.go("--only", "design-loop")
        self.assertEqual(status, 0, text + err)
        self.assertEqual(len(self.calls()), 5)
        record = self.record()
        self.assertNotIn("pre_order", record)
        self.assertEqual(list(record["layout"]["rounds"]), ["design-loop"])
        shutil.rmtree(self.work)
        os.remove(self.log)
        status, text, err = self.go("--only", "pre-order")
        self.assertEqual(status, 0, text + err)
        self.assertEqual(len(self.calls()), 8)
        record = self.record()
        self.assertIsNone(record["verdict"], "no criterion is applied to the pre-order round")
        self.assertEqual(record["pre_order"]["seeds_found_count"], 3)
        self.assertIn("CRITERION | not judged", text)

    def test_the_cost_multiple_is_one_and_a_quarter_so_a_run_inside_it_passes_and_one_over_it_fails(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the kit's pooled criterion, with a cost multiple of 1.25 ... the cost at most 1.25 times its mean
        self.go("--only", "design-loop")
        spent = self.record()["fanned_runs"][0]["cost_usd"]
        self.assertGreater(spent, 0)
        shutil.rmtree(self.work)
        mean = spent / 1.1
        runs = [single("one", ["S1", "S2"], cost=mean), single("two", ["S1", "S2", "S3"], cost=mean)]
        status, text, err = self.go("--only", "design-loop", baselines=baselines_file(os.path.join(self.root, "dear.json"), runs))
        self.assertEqual(status, 0, text + err)
        record = self.record()
        self.assertAlmostEqual(record["verdict"]["bounds"]["cost_usd"], 1.25 * mean)
        self.assertGreater(record["fanned_runs"][0]["cost_usd"], mean, "over the single mean, inside the multiple")
        cost = next(clause for clause in record["verdict"]["clauses"] if clause["clause"] == proof.COST)
        self.assertTrue(cost["ok"])
        shutil.rmtree(self.work)
        runs = [single("one", ["S1", "S2"], cost=spent / 1.4), single("two", ["S1", "S2", "S3"], cost=spent / 1.4)]
        status, text, err = self.go("--only", "design-loop", baselines=baselines_file(os.path.join(self.root, "dearer.json"), runs))
        self.assertEqual(status, 1, "a run over 1.25 times the single mean fails")
        self.assertIn("FAIL cost", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | FAILED"))

    def test_a_run_that_misses_a_seed_every_single_run_found_fails_the_criterion_and_the_record_is_still_written(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the seeds found are no fewer than the fewest any recorded single run found, no seed every single run found is missed
        self.scenario(verdicts={"FLOOR-1": "fail"})
        status, text, _ = self.go("--only", "design-loop")
        self.assertEqual(status, 1)
        record = self.record()
        self.assertEqual(record["verdict"]["status"], "fail")
        self.assertEqual(set(record["verdict"]["failed_clauses"]), {proof.SEEDS_FLOOR, proof.SEED_EVERY_SINGLE_FOUND})
        self.assertIn("FAIL seeds-floor", text)
        self.assertIn("FAIL seed-every-single-found", text)
        self.assertIn("RESULT | FAILED", text)

    def test_the_findings_that_match_no_seed_and_the_replicas_that_raised_each_seed_are_recorded(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: The record gives every seeded defect reported as a finding against the catalogue item that covers it, the findings that match no seed, and the replicas that raised each seed
        stray = {"Finding": 1, "Item": layout_tests.PLAN_ENTRY,"Raised by": "free pass", "Severity": "quality",
                 "What and where": "layer-F.Cu at (2, 2): a stray mark", "Rule": "no", "Added as": "", "Planning shortfall": "—",
                 "Closed by": ""}
        self.scenario(verdicts=ALL_FAIL, findings={"plan-and-free-pass": [stray]})
        status, text, err = self.go("--only", "design-loop")
        self.assertEqual(status, 0, text + err)
        run = self.record()["fanned_runs"][0]
        self.assertEqual(len(run["unmatched"]), 2, "the stray finding once for each replica")
        self.assertTrue(all("a stray mark" in each for each in run["unmatched"]))
        self.assertIn("UNSEEDED | ", text)
        self.assertEqual(sorted(self.record()["layout"]["rounds"]["design-loop"]["merged_round_seeds_found"]), ["S1", "S2", "S3"])

    def test_a_seed_only_one_replica_raised_names_that_replica_and_still_counts_as_found(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the replicas that raised each seed; a seed is found when any replica raised it
        self.go("--only", "design-loop")
        output = os.path.join(self.work, lrp.OUT_DIR, "design-loop")
        record = store.read_record(output)
        lane = next(lane for lane in record["lanes"] if lane["replica"] == 2 and "area-GROUND" in lane["units"])
        attempt = lane["record"]["attempts"][lane["record"]["standing"]]
        attempt["tables"]["Findings"] = [row for row in attempt["tables"]["Findings"] if row["Item"] != "GROUND-1"]
        store.write_record(output, record)
        folder = os.path.join(self.work, lrp.FOLDER)
        outcome, _ = lrp.outcome_of("again", folder, output, SEEDS, "seeded")
        self.assertEqual(outcome.raised_by["S3"], (f"{lane['group']}.r1",))
        self.assertEqual(len(outcome.raised_by["S1"]), 2)
        self.assertEqual(outcome.seeds_found, ("S1", "S2", "S3"))
        self.assertEqual(outcome.judged_by["S3"], (f"{lane['group']}.r1", f"{lane['group']}.r2"))

    def test_a_run_that_cannot_be_judged_is_refused_naming_the_cause_and_writes_no_record(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: a fork whose start report shows tools other than the grant stops the run, and nothing is judged
        self.scenario(verdicts=ALL_FAIL, fork_tools=["Read"])
        status, text, err = self.go("--only", "design-loop")
        self.assertEqual(status, 1, text + err)
        self.assertIn("REFUSED | design-loop:", text)
        self.assertFalse(os.path.exists(os.path.join(self.work, lrp.RECORD)))
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | REFUSED"))

    def test_a_missing_agent_command_line_is_cannot_run_with_status_two(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the proof starts the real agent command line, so a missing one stops it
        with mock.patch.dict(os.environ, {ex.AGENT_ENV: os.path.join(self.root, "no-such-agent")}):
            status, text, err = self.go("--only", "design-loop")
        self.assertEqual(status, 2)
        self.assertIn("RESULT | CANNOT RUN", err)
        self.assertFalse(os.path.exists(os.path.join(self.work, lrp.RECORD)))

    def test_the_command_refuses_a_work_folder_that_is_not_new_a_bound_below_one_and_an_empty_model(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the proof command refuses what it cannot run before it starts a session
        os.makedirs(self.work)
        fx.write(os.path.join(self.work, "held.txt"), "held")
        status, text, _ = self.go()
        self.assertEqual(status, 1)
        self.assertIn("already holds files", text)
        os.remove(os.path.join(self.work, "held.txt"))
        status, text, _ = self.go("--bound", "0")
        self.assertEqual((status, "the bound 0 is below one" in text), (1, True))
        for flag in ("--design-model", "--pre-order-model"):
            status, text, _ = self.go(flag, " ")
            self.assertEqual((status, f"{flag} is empty" in text), (1, True))
        status, text, _ = self.go("--json", "--bound", "0")
        self.assertEqual(json.loads(text)["result"], "REFUSED")

        def refusing(work, kicad, resvg):
            raise lrp.Refused(["the seeding command did not write the seeded copy: nothing"])

        def missing(work, kicad, resvg):
            raise lrp.board_check.CannotRun("KiCad is not on the search path")
        status, text, _ = self.go(seed_runner=refusing)
        self.assertEqual(status, 1)
        self.assertIn("REFUSED | the seeding command did not write the seeded copy", text)
        status, _, err = self.go(seed_runner=missing)
        self.assertEqual(status, 2)
        self.assertIn("RESULT | CANNOT RUN | KiCad is not on the search path", err)
        inside = io.StringIO()
        self.assertEqual(lrp.main(["--work", os.path.join(REPO, "never-written")], out=inside, err=inside), 1)
        self.assertIn("is inside the repository", inside.getvalue())
        self.assertFalse(os.path.exists(os.path.join(REPO, "never-written")))
        self.assertEqual(self.calls(), [])


class TheBaselines(Proofed):
    def test_baselines_of_another_seed_list_design_or_model_are_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the recorded single-reviewer runs, the baseline key giving the same seed list, design and model
        other = os.path.join(self.root, "other.json")
        cases = {"seed list": dict(seeds=SEEDS[:2]), "design": dict(design="e" * 40), "model": dict(model="claude-haiku-5-5")}
        for name, changed in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.work, ignore_errors=True)
                status, text, _ = self.go("--only", "design-loop", baselines=baselines_file(other, **changed))
                self.assertEqual(status, 1)
                self.assertIn("holds no single-reviewer runs of this seed list, design and model", text)
                self.assertIn("they are not baselines for this run", text)
        self.assertEqual(self.calls(), [], "no session was started")
        shutil.rmtree(self.work, ignore_errors=True)
        status, text, _ = self.go("--only", "design-loop", baselines=baselines_file(other, model=kit_small))
        self.assertEqual(status, 1)
        self.assertIn(f"model is {kit_small} and this run's is {lrp.BASELINE_MODEL}", text)
        shutil.rmtree(self.work, ignore_errors=True)
        status, text, _ = self.go("--only", "design-loop", baselines=os.path.join(self.root, "absent.json"))
        self.assertEqual(status, 1)
        self.assertIn("cannot be read as JSON", text)
        self.assertEqual(self.calls(), [])

    def test_the_baseline_key_holds_the_single_runs_model_so_a_small_tier_run_is_accepted_and_a_different_seed_list_is_not(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the baseline key giving the same seed list and design as the single runs and the model they ran on, which is the mid-tier, and not the model of the fanned-out run
        status, text, err = self.go("--only", "design-loop")
        self.assertEqual(status, 0, text + err)
        record = self.record()
        self.assertEqual(record["layout"]["models"]["design-loop"], kit_small)
        self.assertEqual([key["model"] for key in record["keys"]], [lrp.BASELINE_MODEL], "the key holds the baselines' model")
        shutil.rmtree(self.work, ignore_errors=True)
        status, text, _ = self.go("--only", "design-loop", baselines=baselines_file(os.path.join(self.root, "seeds.json"), seeds=SEEDS[:2]))
        self.assertEqual(status, 1)
        self.assertIn("holds no single-reviewer runs of this seed list", text)

    def test_the_five_recorded_runs_are_the_baselines_for_the_seed_list_and_design_the_proof_seeds(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C9: the proof command takes the five recorded single-reviewer runs as baselines
        seeds = review_seed.seed_list(review_seed.SEEDS)["seeds"]
        key, runs = lrp.baseline_runs(lrp.BASELINES, seeds, lrp.design_tree(), lrp.BASELINE_MODEL)
        self.assertEqual(len(runs), 5)
        self.assertEqual(key.prompt, "ca90e542e3fc18fa114622aac0376f016c0dd74b386de98dedf9e9f7676f5c4e", "the prompt hash as recorded")
        self.assertEqual(round(proof.mean([run.cost_usd for run in runs]), 3), 2.839)
        self.assertEqual(round(proof.mean([run.wall_s for run in runs])), 862)
        self.assertEqual(sorted(run.found for run in runs), [19, 20, 21, 21, 21])
        edited = [dict(seed, item="MFG-9") if seed["id"] == "S10" else seed for seed in seeds]
        with self.assertRaises(lrp.Refused):
            lrp.baseline_runs(lrp.BASELINES, edited, lrp.design_tree(), lrp.BASELINE_MODEL)


class TheStreamFigures(unittest.TestCase):
    """The figures the kit's telemetry does not count, read from saved streams."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="layout-proof-streams-")
        self.addCleanup(shutil.rmtree, self.folder, True)

    def save(self, label, uses=(), results=(), attempts=1, kind="ok"):
        """A saved session: its stream holds the tool uses (name, id) and the results (id, is_error), its meta the retries."""
        blocks = [{"type": "tool_use", "id": ident, "name": name, "input": {"url": "https://example.invalid/" + ident}}
                  for name, ident in uses]
        stream = ex.stream_text("s-" + label, blocks=blocks or None, text="done")
        for ident, is_error in results:
            stream += json.dumps({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ident, "is_error": is_error, "content": "x"}]}}) + "\n"
        number = len([n for n in os.listdir(self.folder) if n.endswith(".jsonl")]) + 1
        stem = os.path.join(self.folder, f"{number:04d}-{label}")
        with open(stem + ".jsonl", "w", encoding="utf-8") as handle:
            handle.write(stream)
        with open(stem + ".json", "w", encoding="utf-8") as handle:
            json.dump({"label": label, "key": label, "kind": kind, "attempts": attempts, "waits": []}, handle)

    def test_document_retrievals_and_the_failed_ones_are_counted_by_session_from_the_saved_streams(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: each session's document retrievals with any that failed, counted from the saved streams since the kit's telemetry does not count them
        self.save("G1.r1", uses=[("WebFetch", "a"), ("WebFetch", "b"), ("Read", "c")], results=[("a", False), ("b", True), ("c", False)])
        self.save("G1.r2", uses=[("WebFetch", "d")], results=[("d", False)])
        self.save("G2.r1", uses=[("Read", "e")], results=[("e", False)])
        self.save("G3.r1", uses=[("WebFetch", "f")], results=[])
        self.save("root")
        found = lrp.retrievals(self.folder)
        self.assertEqual(found["G1.r1"], {"retrieved": 2, "failed": 1})
        self.assertEqual(found["G1.r2"], {"retrieved": 1, "failed": 0})
        self.assertEqual(found["G2.r1"], {"retrieved": 0, "failed": 0}, "a read of a file is not a retrieval")
        self.assertEqual(found["G3.r1"], {"retrieved": 1, "failed": 1}, "a retrieval with no result did not succeed")
        self.assertEqual(found["root"], {"retrieved": 0, "failed": 0})
        self.assertEqual(lrp.total(found, "retrieved"), 4)
        self.assertEqual(lrp.retrievals(os.path.join(self.folder, "nowhere")), {})

    def test_calls_refused_for_a_rate_limit_are_counted_from_the_executors_retries(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: any call refused for a rate limit, counted from the executor's retries
        self.save("first", attempts=1)
        self.save("retried", attempts=3)
        self.save("lost", attempts=2, kind=ex.RATE_LIMIT)
        self.assertEqual(lrp.refused_for_rate_limit(self.folder), 0 + 2 + 2)
        self.assertEqual(lrp.refused_for_rate_limit(os.path.join(self.folder, "nowhere")), 0)

    def test_the_executor_saves_the_retry_count_the_figure_is_read_from(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: any call refused for a rate limit, counted from the executor's retries
        limited = ex.Reply(is_error=True, api_error_status=429, text="Rate limit reached", exit_code=1)
        clock = mock.Mock(now=mock.Mock(return_value=0.0))
        call = sess.Call(sess.SessionSpec(("Read",), "/work", model=lrp.BASELINE_MODEL, system="s"), sess.user_message([sess.text_block("m")]),
                         label="u")
        out = os.path.join(self.folder, "saved")
        ex.StubExecutor(lambda made, number: [limited, limited, ex.Reply(text="ok")], clock=clock, out=out, check_start=False).run(call)
        self.assertEqual(lrp.refused_for_rate_limit(out), 2)
        lost = os.path.join(self.folder, "lost")
        ex.StubExecutor([limited], clock=clock, policy=ex.RetryPolicy(retries=1), out=lost, check_start=False).run(call)
        self.assertEqual(lrp.refused_for_rate_limit(lost), 2)


class TheMatching(unittest.TestCase):
    ANSWER = """## Round 1

- **Board judged**: the design files in this folder.

### Verdicts

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|
| FLOOR-1 | judgement | function | fail | classes | Finding 1.1. |
| CLOCK-1 | judgement | function | pass | crop-U4 | Fine. |

### Plan and free pass

Compared the plan.

### Findings

| Finding | Raised by | Severity | What and where | Rule | Added as | Planning shortfall | Closed by |
|---|---|---|---|---|---|---|---|
| 1.1 | FLOOR-1 | function | classes at (1, 1): wrong | no | | — | |
| 1.2 | free pass | quality | layer-F.Cu at (2, 2): a stray mark | no | | — | |
"""

    def test_a_round_written_as_markdown_gives_its_verdicts_and_its_findings_raised_by(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: the seeds are matched to the findings that name the item that covers them
        parsed = lrp.parsed_round(self.ANSWER)
        self.assertEqual(parsed["verdicts"], {"FLOOR-1": "fail", "CLOCK-1": "pass"})
        self.assertEqual(parsed["raised_by"], ["FLOOR-1", "free pass"])
        self.assertEqual(lrp.parsed_round(self.ANSWER.replace("## Round 1\n\n", ""))["raised_by"], ["FLOOR-1", "free pass"])
        self.assertEqual(lrp.parsed_round("nothing to read here"), {"verdicts": {}, "raised_by": []})

    def test_an_item_is_named_whole_and_a_seed_matches_the_finding_whose_raised_by_names_its_item(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: every seeded defect reported as a finding against the catalogue item that covers it
        self.assertTrue(lrp.names("FLOOR-1", "FLOOR-1"))
        self.assertTrue(lrp.names("FLOOR-1", "FLOOR-1, GROUND-1"))
        self.assertFalse(lrp.names("FLOOR-1", "FLOOR-10"))
        self.assertFalse(lrp.names("FLOOR-1", "XFLOOR-1"))
        self.assertFalse(lrp.names("FLOOR-1", "free pass"))
        self.assertTrue(lrp.matches(SEEDS[0], {"Raised by": "FLOOR-1 and GROUND-1"}))
        self.assertFalse(lrp.matches(SEEDS[0], {"Raised by": "GROUND-1", "What and where": "FLOOR-1 is mentioned here"}))
        self.assertFalse(lrp.matches(SEEDS[0], {}))


class TheCutover(unittest.TestCase):
    RETIRED = re.compile(r"review_fan_out|review_agent_tap|SETUP_RULE|SETUP-READ-COMPLETE|hw:review-fan-out|REVIEW_FAN_OUT")
    #: The recorded streams kept as the kit's evidence, which hold the retired setup token as the rejected examples.
    EVIDENCE = os.path.join("hardware", "tools", "tests", "fixtures", "review_streams")

    def hits(self):
        found = []
        here = os.path.abspath(__file__)
        for root in (os.path.join(REPO, "hardware"), os.path.join(REPO, "docs"), os.path.join(REPO, "Taskfile.yml")):
            walk = [(os.path.dirname(root), [], [os.path.basename(root)])] if os.path.isfile(root) else os.walk(root)
            for folder, folders, files in walk:
                folders[:] = [name for name in folders if name != "__pycache__"]
                for name in files:
                    path = os.path.join(folder, name)
                    relative = os.path.relpath(path, REPO)
                    if path == here or relative.startswith(self.EVIDENCE) or name.endswith((".png", ".jpg", ".pyc", ".step")):
                        continue
                    try:
                        with open(path, encoding="utf-8") as handle:
                            text = handle.read()
                    except (UnicodeDecodeError, OSError):
                        continue
                    found += [f"{relative}:{number}: {line.strip()[:100]}" for number, line in enumerate(text.splitlines(), 1)
                              if self.RETIRED.search(line)]
        return found

    def test_no_tool_test_task_or_document_names_the_earlier_driver_its_setup_rule_or_the_tap(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C9: a search of the repository's tools, tests, task runner and documents finds, outside the review kit's recorded-stream fixtures, no reference to the earlier driver's module, its setup rule, its task entry or the tap shim
        self.assertEqual(self.hits(), [])

    def test_the_earlier_drivers_files_tests_stub_and_task_are_gone_and_the_notes_hold_the_kits_section(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C9: the earlier driver's and caller seam's tests and stub are gone, and the hardware notes' sections on them are replaced by the kit's
        for relative in ("review_fan_out.py", "review_agent_tap.py", os.path.join("tests", "test_review_fan_out.py"),
                         os.path.join("tests", "review_fan_out_stub.py")):
            self.assertFalse(os.path.exists(os.path.join(TOOLS, relative)), relative)
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            notes = handle.read()
        self.assertNotIn("## The review fan-out command", notes)
        self.assertIn("## The review kit command", notes)
        with open(os.path.join(REPO, "Taskfile.yml"), encoding="utf-8") as handle:
            self.assertNotIn("  hw:review-fan-out:", handle.read())

    def test_the_search_catches_a_reference_it_is_looking_for(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C9: the search fails on a hit
        for text in ("import review_fan_out", "SETUP_RULE = 1", "SETUP-READ-COMPLETE", "task hw:review-fan-out", "exec review_agent_tap.py",
                     "REVIEW_FAN_OUT_AGENT"):
            self.assertTrue(self.RETIRED.search(text), text)
        self.assertFalse(self.RETIRED.search("task hw:review-run and review_run.py and the review kit"))

    def test_the_layout_caller_and_its_proof_run_on_the_kit_and_import_no_retired_module(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C9: the layout caller is a declaration with checks and a rendered record that runs on the review kit, the proof command runs the kit's proof harness
        for name in ("review_caller_layout.py", "layout_review_proof.py"):
            with open(os.path.join(TOOLS, name), encoding="utf-8") as handle:
                source = handle.read()
            self.assertIsNone(self.RETIRED.search(source), name)
        self.assertTrue(hasattr(lrp.proof, "accept") and hasattr(lrp.proof, "build_record"))
        for retired in ("run_single", "run_fanned", "tapped", "tap_calls", "prove_fanned_only"):
            self.assertFalse(hasattr(lrp, retired), f"{retired} belonged to the setup-session proof")


if __name__ == "__main__":
    unittest.main()
