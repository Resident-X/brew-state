#!/usr/bin/env python3
"""The schematic review proof command, and the proof harness it shares with the layout review's: one command that checks the
seeded copy, writes the review folder, runs the single form once through the kit and records it as the baseline file, runs the
fanned-out form on the kit's command, and judges it by the kit's pooled criterion.

The kit's command runs over a stand-in for the agent command line, so no model and no KiCad is used, and the real agent command
line is never run. The seeded copy, its netlist, its sheet drawings and its seed list are synthetic stand-ins for what the seeding
session and the commands that export and draw them leave, placed where the proof command expects them. Nothing here is the live
proof, which spends real money and is run by the operator.
"""

from __future__ import annotations

import dataclasses
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import layout_fixtures as lfx  # noqa: E402
import layout_review_proof as lrp  # noqa: E402
import review_kit_fixtures as fx  # noqa: E402
import review_proof_harness as harness  # noqa: E402
import schematic_fixtures as sfx  # noqa: E402
import schematic_review_proof as srp  # noqa: E402
import test_review_caller_schematic as caller_tests  # noqa: E402
from review_kit import executor as ex  # noqa: E402
from review_kit import decl, merge, proof, store  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))


def slurp(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as handle:
        return handle.read()


SMALL = srp.DESIGN_MODEL
MID = srp.BASELINE_MODEL
SEEDS = [{"id": "S1", "item": "STRAP-1", "description": "a strap pin left floating"},
         {"id": "S2", "item": "PINV-1", "description": "a pin driven above its rating"},
         {"id": "S3", "item": "DERATE-1", "description": "a part run at its limit"}]
#: The pairs each seed's finding is raised on, and what each item selects in the synthetic schematic.
PAIRS = {"STRAP-1": ["U1"], "PINV-1": sfx.NETS, "DERATE-1": sfx.PARTS, "DERATE-2": sfx.SHEETS}
ALL_FAIL = {"STRAP-1|U1": "fail", "PINV-1|/IN": "fail", "DERATE-1|R1": "fail"}
#: The mid-tier model's session is dear and slow beside the small tier's, as it is live.
COST = {MID: 1.0, SMALL: 0.03}
API_MS = {MID: 200000, SMALL: 300}
REPORT = ["DESIGN | hardware/synth/board/board.kicad_pro | PASS", "RESULT | PASS"]


def single(run_id, found, wall=1000.0, cost=5.0):
    return proof.RunOutcome(run_id, proof.SINGLE, "tool", "seeded", tuple(found), (), {}, {s: ("single",) for s in found},
                            {s["id"]: ("single",) for s in SEEDS}, (proof.SessionRecord("single", wall, cost, 1, 1, 1),), wall, cost,
                            ("first_call_read",))


class Proofed(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="schematic-proof-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.work = os.path.join(self.root, "work")
        self.source = sfx.make_repo(os.path.join(self.root, "source"))
        self.seeded = self.source
        self.seeds = os.path.join(self.root, "seeds.json")
        lfx.write(self.seeds, json.dumps({"design": sfx.DESIGN, "seeds": SEEDS}))
        self.baselines = os.path.join(self.root, "baselines.json")
        self.log = os.path.join(self.root, "agent.log")
        self.scenario_path = os.path.join(self.root, "scenario.json")
        self.program = os.path.join(self.root, "agent")
        lfx.write(self.program, caller_tests.STUB.replace("PYTHON", sys.executable, 1).replace("TOOLS", repr(TOOLS)))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        for patch in (mock.patch.dict(os.environ, {ex.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path, "STUB_LOG": self.log}),
                      mock.patch.object(srp, "DESIGN", sfx.DESIGN), mock.patch.object(srp, "NAME", sfx.NAME)):
            patch.start()
            self.addCleanup(patch.stop)
        self.scenario(verdicts=ALL_FAIL)

    def scenario(self, **values):
        values.setdefault("model_verdicts", {MID: {"DERATE-1|R1": "pass"}})
        values.setdefault("pairs", PAIRS)
        values.setdefault("cost", COST)
        values.setdefault("api_ms", API_MS)
        lfx.write(self.scenario_path, json.dumps(values))

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def preparer(self, work, seeded, kicad_cli):
        """What the commands that check, export and draw leave, synthetic, written under the work folder's seed folder."""
        inputs = sfx.make_inputs(os.path.join(work, srp.SEED_DIR, "inputs"))
        return {"netlist": inputs["netlist"], "sheets": inputs["sheets"], "report": inputs["report"],
                "netlist_command": sfx.NETLIST_COMMAND}

    def tree(self):
        return lfx.git(self.seeded, "rev-parse", f"HEAD:{sfx.DESIGN}")

    def recorded(self, runs=None, model=MID, seeds=SEEDS, design=None):
        """A baselines file of synthetic single runs of this seed list, design and model: one found two of the three seeds, the
        other all three."""
        runs = runs if runs is not None else [single("one", ["S1", "S2"]), single("two", ["S1", "S2", "S3"])]
        key = proof.BaselineKey(proof.seed_list_hash(seeds), design or self.tree(), model, proof.SINGLE, "p" * 64)
        with open(self.baselines, "w", encoding="utf-8") as handle:
            json.dump({"version": proof.BASELINES_VERSION, "source": "synthetic", "seeds": seeds,
                       "baselines": [{"key": key.as_dict(), "runs": [run.as_dict() for run in runs]}]}, handle)
        return key

    def go(self, *extra, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        status = srp.main(["--work", self.work, "--seeded-repo", self.seeded, "--seeds", self.seeds, *extra], out=out, err=err,
                          preparer=kwargs.pop("preparer", self.preparer), baselines=kwargs.pop("baselines", self.baselines),
                          documents_repo=self.source, **kwargs)
        return status, out.getvalue(), err.getvalue()

    def record(self):
        with open(os.path.join(self.work, srp.RECORD), encoding="utf-8") as handle:
            return json.load(handle)


class TheCommand(Proofed):
    def test_with_no_baseline_recorded_the_single_form_runs_once_and_is_recorded_then_the_fanned_form_is_judged(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.assertFalse(os.path.exists(self.baselines))
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        calls = self.calls()
        single_calls = [call for call in calls if MID in call["args"]]
        fanned_calls = [call for call in calls if SMALL in call["args"]]
        self.assertEqual(len(single_calls), 2, "the single form: a shared context that judges nothing and one session")
        self.assertEqual(len([call for call in single_calls if call["resume"] is not None]), 1)
        fork = next(call for call in single_calls if call["resume"] is not None)
        self.assertEqual(sorted(fork["units"]), sorted(["area-PINV", "area-STRAP", "area-DERATE", "free-pass"]),
                         "one session holds every unit's items")
        for item in ("PINV-1", "PINV-2", "STRAP-1", "DERATE-1", "DERATE-2", "FREE-PASS"):
            self.assertIn(f"- {item}", fork["prompt"])
        self.assertTrue(fanned_calls)
        self.assertEqual(len([call for call in fanned_calls if call["resume"] is None]), 1, "one shared context for the replicas")
        groups = json.loads(json.dumps(self.record()["fanned_runs"][0]))["sessions"]
        self.assertEqual(len(groups), len(fanned_calls))
        for call in calls:
            self.assertEqual(call["tools"], "Read,Glob,Grep,WebFetch")
        record = self.record()
        self.assertEqual(record["verdict"]["status"], "pass")
        self.assertEqual(record["cost_multiple"], 1.25)
        self.assertEqual(record["schematic"]["models"], {"fanned": SMALL})
        self.assertEqual(record["schematic"]["baseline_model"], MID)
        self.assertIn("run now, recorded in", record["schematic"]["single_form"])
        self.assertEqual(record["schematic"]["seeded_commit"], lfx.git(self.seeded, "rev-parse", "HEAD"))
        self.assertEqual(record["seed_list_sha256"], proof.seed_list_hash(SEEDS))
        self.assertEqual([key["form"] for key in record["keys"]], [proof.SINGLE])
        self.assertEqual(record["keys"][0]["design"], self.tree())
        self.assertEqual(record["keys"][0]["model"], MID)
        self.assertEqual(len(record["single_runs"]), 1)
        self.assertEqual(record["single_runs"][0]["seeds_found"], ["S1", "S2"], "the mid-tier reviewer misses the derating seed")
        self.assertEqual(record["fanned_runs"][0]["seeds_found"], ["S1", "S2", "S3"])
        for seed, who in record["seed_replicas"].items():
            self.assertEqual(len(next(iter(who.values()))), 2, f"{seed} is raised by both replicas")
        self.assertIn(f"PROOF | single form on {MID} (run now, recorded in", text)
        self.assertIn(f"fanned form on {SMALL} with 2 replicas", text)
        self.assertIn("cost multiple 1.25", text)
        self.assertIn("CRITERION | PROOF pass", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | WRITTEN"))
        with open(os.path.join(self.work, srp.TEXT), encoding="utf-8") as handle:
            self.assertEqual(handle.read().splitlines(), [line for line in text.splitlines() if not line.startswith("RESULT")])
        loaded = proof.load_baselines(self.baselines)
        (key,) = loaded.keys.values()
        self.assertEqual((key.seeds, key.design, key.model, key.form), (proof.seed_list_hash(SEEDS), self.tree(), MID, proof.SINGLE))
        (run,) = loaded.recorded(key)
        self.assertEqual((run.form, run.seeds_found), (proof.SINGLE, ("S1", "S2")))
        self.assertEqual(run.seeded_commit, lfx.git(self.seeded, "rev-parse", "HEAD"))

    def test_with_the_single_runs_recorded_for_this_seed_list_design_and_model_the_single_form_is_not_run_again(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded()
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        self.assertEqual([call for call in self.calls() if MID in call["args"]], [], "the mid-tier is not started")
        record = self.record()
        self.assertEqual(len(record["single_runs"]), 2)
        self.assertEqual(record["schematic"]["single_form"], "recorded")
        self.assertEqual(record["single_means"], {"wall_s": 1000.0, "cost_usd": 5.0})
        before = slurp(self.baselines, "rb")
        shutil.rmtree(self.work)
        os.remove(self.log)
        self.go()
        self.assertEqual(before, slurp(self.baselines, "rb"), "a recorded baseline file is left as it was")

    def test_a_baseline_file_for_another_seed_list_design_or_model_does_not_stand_in_and_the_single_form_runs(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        other = SEEDS[:2]
        for name, change in (("another seed list", dict(seeds=other)), ("another design", dict(design="e" * 40)),
                             ("another model", dict(model="claude-other-9"))):
            with self.subTest(name=name):
                shutil.rmtree(self.work, ignore_errors=True)
                if os.path.exists(self.log):
                    os.remove(self.log)
                self.recorded(**change)
                status, text, err = self.go()
                self.assertEqual(status, 0, text + err)
                self.assertTrue([call for call in self.calls() if MID in call["args"]], "the single form ran")
                loaded = proof.load_baselines(self.baselines)
                self.assertEqual(len(loaded.keys), 2, "the file keeps the group it held and holds the new one")
                self.assertEqual(self.record()["single_runs"][0]["id"], "single-1")

    def test_the_fanned_run_is_judged_by_the_pooled_criterion_and_a_run_that_fails_it_exits_1(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded([single("one", ["S1", "S2", "S3"], cost=0.01), single("two", ["S1", "S2", "S3"], cost=0.01)])
        status, text, err = self.go()
        self.assertEqual(status, 1, text)
        self.assertIn("RESULT | FAILED | the criterion is fail", text)
        self.assertRegex(text, r"FAIL cost: at most 0\.0125 USD")
        shutil.rmtree(self.work)
        self.scenario(verdicts={"STRAP-1|U1": "fail"})
        self.recorded([single("one", ["S1", "S2", "S3"]), single("two", ["S1", "S2", "S3"])])
        status, text, err = self.go()
        self.assertEqual(status, 1, text)
        self.assertIn("FAIL seeds-floor", text)

    def test_a_seed_the_replicas_did_not_report_is_named_in_the_record_with_the_replicas_that_raised_the_others(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.scenario(verdicts={"STRAP-1|U1": "fail", "PINV-1|/IN": "fail"})
        self.recorded()
        status, text, err = self.go()
        record = self.record()
        self.assertEqual(record["fanned_runs"][0]["seeds_found"], ["S1", "S2"])
        self.assertEqual(record["seed_replicas"]["S3"], {record["fanned_runs"][0]["id"]: []})
        self.assertIn("SEED | S3 | schematic-fanned-2 | raised by none", text)
        self.assertIn("SEED | S1 | schematic-fanned-2 | raised by", text)

    def test_the_findings_that_match_no_seed_and_the_verdicts_pair_by_pair_are_recorded_and_compared(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.scenario(verdicts={**ALL_FAIL, "DERATE-2|board": "fail"})
        self.recorded()
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        record = self.record()
        unmatched = record["fanned_runs"][0]["unmatched"]
        self.assertEqual(len(unmatched), 2, "the finding on DERATE-2 from each replica names no seed")
        self.assertTrue(all("DERATE-2" in each for each in unmatched))
        self.assertIn("UNSEEDED | ", text)
        self.assertIn("verdict_differences", record)
        differences = record["verdict_differences"][record["fanned_runs"][0]["id"]]
        self.assertIsInstance(differences, list)
        self.assertEqual(set(record["fanned_runs"][0]["raised_by"]), {"S1", "S2", "S3"})

    def test_every_session_is_recorded_with_its_figures_and_the_retrievals_and_refused_calls_are_counted(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded()
        status, text, err = self.go()
        record = self.record()
        sessions = record["fanned_runs"][0]["sessions"]
        self.assertGreaterEqual(len(sessions), 3)
        for each in sessions:
            for key in ("session", "wall_s", "cost_usd", "tokens_read", "tokens_written", "tokens_generated", "first_call_read"):
                self.assertIn(key, each)
            self.assertIn(f"SESSION | {each['session']} |", text)
        extra = record["schematic"]["fanned"]
        self.assertEqual(extra["refused_for_a_rate_limit"], 0)
        self.assertTrue(extra["merged"])
        self.assertEqual(extra["merged_round_seeds_found"], ["S1", "S2", "S3"])
        self.assertTrue(all(entry["failed"] == 0 for entry in extra["retrievals"].values()))
        self.assertIn("ROUND | fanned | refused for a rate limit 0 | retrievals 0 failed 0 | merged round written | seeds the merged round names S1, S2, S3", text)
        self.assertEqual(extra["command_report"]["result"], "WRITTEN")
        self.assertTrue(os.path.isfile(os.path.join(self.work, srp.FANNED_OUT, "round-1.md")))

    def test_the_datasheet_retrievals_of_each_session_and_the_ones_that_failed_are_recorded_beside_its_figures(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.scenario(verdicts=ALL_FAIL, fetch=[False, True])
        self.recorded()
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        record = self.record()
        found = record["schematic"]["fanned"]["retrievals"]
        forks = {label: entry for label, entry in found.items() if label.startswith("G")}
        self.assertTrue(forks)
        self.assertTrue(all(entry == {"retrieved": 2, "failed": 1} for entry in forks.values()), found)
        self.assertEqual(found["root"], {"retrieved": 0, "failed": 0})
        count = len(forks)
        self.assertIn(f"retrievals {2 * count} failed {count} |", text)
        self.assertIn("RETRIEVALS | fanned | G1.r1.a1 | retrieved 2 failed 1", text)
        self.assertNotIn("RETRIEVALS | fanned | root", text, "a session that retrieved nothing has no line")

    def test_the_review_folder_is_written_by_the_folder_command_from_the_seeded_commit_with_the_netlist_and_the_sheets(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.go("--dry")
        folder = os.path.join(self.work, srp.FOLDER)
        content = sfx.round_file(folder)
        self.assertEqual(content["number"], 1)
        self.assertEqual(content["commit"], lfx.git(self.seeded, "rev-parse", "HEAD"))
        self.assertEqual(content["netlist"], sfx.NETLIST_COMMAND)
        self.assertEqual(content["records"], [f"{sfx.DESIGN}/constraints.md", f"{sfx.DESIGN}/circuit-proof.md",
                                              f"{sfx.DESIGN}/separation-basis.yaml (accepted_on 2026-10-18)"])
        self.assertTrue(os.path.isfile(os.path.join(folder, "review.net")))
        self.assertTrue(os.path.isfile(os.path.join(folder, "sheets", "board-Power.svg")))
        self.assertTrue(os.path.isfile(os.path.join(folder, "check-report.txt")))
        self.assertFalse(os.path.exists(os.path.join(folder, sfx.DESIGN, "schematic-review.md")))
        self.assertFalse(os.path.exists(os.path.join(folder, "seeds.json")))

    def test_no_folder_from_the_review_folders_parent_up_to_the_work_folder_holds_anything_but_the_review_folder(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded()
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        folder = os.path.join(self.work, srp.FOLDER)
        self.assertEqual(os.path.dirname(os.path.dirname(folder)), self.work)
        self.assertEqual(os.listdir(os.path.dirname(folder)), ["review"])
        everything = [name for _, _, names in os.walk(os.path.join(self.work, srp.REVIEW_TREE)) for name in names]
        for name in ("seeds.json", "proof-record.json", "record.json", "baselines.json"):
            self.assertNotIn(name, everything)
        self.assertTrue(os.path.isfile(os.path.join(self.work, srp.SEEDS)))
        with open(os.path.join(self.work, srp.SEEDS), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["seeds"], SEEDS)
        self.assertTrue(store.holds_record(os.path.join(self.work, srp.FANNED_OUT)))
        for call in self.calls():
            self.assertEqual(os.path.realpath(call["cwd"]), os.path.realpath(folder), "every session starts in the review folder")

    def test_the_command_reports_in_json_with_the_record(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded()
        status, text, err = self.go("--json")
        document = json.loads(text)
        self.assertEqual((status, document["result"], document["record"]["verdict"]["status"]), (0, "WRITTEN", "pass"))
        self.assertEqual(document["lines"][0].split(" | ")[0], "PROOF")

    def test_a_run_over_half_the_single_mean_wall_time_or_missing_a_seed_every_single_run_found_fails_and_exits_1(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded([single("one", ["S1", "S2", "S3"], wall=0.001), single("two", ["S1", "S2", "S3"], wall=0.001)])
        status, text, err = self.go()
        self.assertEqual(status, 1, text)
        self.assertRegex(text, r"FAIL wall")
        self.assertNotRegex(text, r"FAIL cost")
        shutil.rmtree(self.work)
        self.scenario(verdicts={"STRAP-1|U1": "fail", "DERATE-1|R1": "fail"})
        self.recorded([single("one", ["S1", "S2"]), single("two", ["S2", "S3"])])
        status, text, err = self.go()
        self.assertEqual(status, 1, text)
        self.assertNotIn("FAIL seeds-floor", text, "two seeds meet the fewest any single run found")
        self.assertRegex(text, r"FAIL .*S2")

    def test_a_passing_first_run_within_a_tenth_of_a_bound_requires_a_second_fanned_run_and_exits_1(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded()
        self.assertEqual(self.go()[0], 0)
        cost = self.record()["fanned_runs"][0]["cost_usd"]
        shutil.rmtree(self.work)
        self.recorded([single("one", ["S1", "S2"], cost=cost / 0.95 / 1.25), single("two", ["S1", "S2"], cost=cost / 0.95 / 1.25)])
        status, text, err = self.go()
        self.assertEqual(status, 1, text)
        self.assertEqual(self.record()["verdict"]["status"], "second-run-required")
        self.assertIn("a second fanned-out run is required: the first is within ten per cent of a bound", text)

    def test_the_record_is_written_in_text_and_in_json_with_the_same_content(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.scenario(verdicts={**ALL_FAIL, "DERATE-2|board": "fail"})
        self.recorded()
        status, text, err = self.go("--json")
        self.assertEqual(status, 0, text + err)
        record = self.record()
        self.assertEqual(json.loads(text)["record"], record)
        written = slurp(os.path.join(self.work, srp.TEXT))
        run = record["fanned_runs"][0]
        for session in run["sessions"]:
            self.assertIn(f"SESSION | {session['session']} |", written)
        self.assertIn("UNSEEDED | ", written)
        self.assertIn(f"SEED | S1 | {run['id']} | raised by", written)
        self.assertEqual(sorted(line for line in written.splitlines() if line.startswith(("SESSION |", "SEED |", "UNSEEDED |"))),
                         sorted(line for line in json.loads(text)["lines"] if line.startswith(("SESSION |", "SEED |", "UNSEEDED |"))))


class TheDryMode(Proofed):
    def test_the_dry_mode_prints_the_plan_and_the_predicted_cost_and_time_beside_the_bounds_and_starts_no_session(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded()
        status, text, err = self.go("--dry")
        self.assertEqual(status, 0, text + err)
        self.assertEqual(self.calls(), [], "the model is not called")
        self.assertFalse(os.path.exists(os.path.join(self.work, srp.RECORD)))
        self.assertFalse(os.path.exists(os.path.join(self.work, srp.OUT_DIR, "fanned")), "no run folder is made")
        self.assertRegex(text, r"PLAN \| fanned \| 2 replicas on claude-haiku-5-5 \| \d groups \| \d+ forks")
        self.assertRegex(text, r"PREDICTED \| fanned \| \$[0-9.]+ \| [0-9.]+ s \| cost (within|over) its bound")
        self.assertIn("SINGLE | recorded: 2 run(s) | mean $5.00 | mean 1000 s", text)
        self.assertIn("COST MULTIPLE | 1.25 | bounds: cost at most $6.25 (1.25 times the single mean $5.00), wall time at most 500 s "
                      "(half the single mean 1000 s)", text)
        self.assertRegex(text, r"GROUP \| G1 \| units ")
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | PLANNED"))
        self.assertTrue(os.path.isdir(os.path.join(self.work, srp.FOLDER)), "the folder is still written")

    def test_with_no_single_run_recorded_the_dry_mode_plans_the_single_form_and_takes_its_bounds_from_the_prediction(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        status, text, err = self.go("--dry")
        self.assertEqual(status, 0, text + err)
        self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(self.baselines), "a dry run records nothing")
        self.assertRegex(text, rf"SINGLE \| none recorded, so the single form would run once on {MID} \| predicted \$[0-9.]+ \| [0-9.]+ s \| 1 fork \| the bounds below are from the prediction")
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry", "--json")
        document = json.loads(text)
        self.assertEqual((status, document["result"]), (0, "PLANNED"))
        self.assertIn("plan", document)

    def test_the_dry_output_warns_when_the_prediction_is_over_a_bound_or_within_a_tenth_of_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        status, text, err = self.go("--dry", "--json")
        predicted = json.loads(text)["plan"]["predicted"]["cost_usd"]
        for divisor, warned in ((0.8, True), (1.05, True), (1.25, False)):
            with self.subTest(divisor=divisor):
                shutil.rmtree(self.work)
                mean = predicted * divisor / srp.COST_MULTIPLE
                self.recorded([single("one", ["S1", "S2"], cost=mean, wall=1e6), single("two", ["S1", "S2", "S3"], cost=mean, wall=1e6)])
                status, text, err = self.go("--dry")
                self.assertEqual(status, 0, text + err)
                self.assertEqual("WARNING | predicted cost" in text, warned, text)
                if warned:
                    self.assertIn("a live run is likely to fail that bound or to need a second run", text)
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry", "--design-model", "claude-unlisted-9")
        self.assertRegex(text, r"WARNING \| the model 'claude-unlisted-9'.*priced at the default")


class TheRefusals(Proofed):
    def refused(self, *words, args=(), **kwargs):
        status, text, err = self.go(*args, **kwargs)
        self.assertEqual(status, 1, text + err)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | REFUSED"), text)
        for word in words:
            self.assertIn(word, text)
        self.assertEqual(self.calls(), [], "no session was started")
        shutil.rmtree(self.work, ignore_errors=True)
        return text

    def test_a_work_folder_inside_the_repository_a_file_or_not_empty_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        inside = os.path.join(REPO, "proof-work-test")
        self.assertIn("is inside the repository", "; ".join(srp.refusals(inside)))
        lfx.write(os.path.join(self.work, "a.txt"), "x")
        self.refused("already holds files")
        lfx.write(self.work, "x")
        self.refused("is a file")
        os.remove(self.work)

    def test_a_seeded_repository_that_is_missing_not_a_work_tree_dirty_without_the_design_or_inside_this_one_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        real = self.seeded
        self.seeded = os.path.join(self.root, "nowhere")
        self.refused("is not a folder")
        self.seeded = os.path.join(self.root, "plain")
        os.makedirs(self.seeded)
        self.refused("is not a git work tree with a commit")
        self.seeded = real
        lfx.write(os.path.join(real, "stray.txt"), "x")
        self.refused("has changes that are not committed")
        os.remove(os.path.join(real, "stray.txt"))
        self.seeded = os.path.join(REPO, "hardware")
        self.refused("is inside this repository")
        self.seeded = real
        with mock.patch.object(srp, "DESIGN", "hardware/other"):
            self.refused("holds no hardware/other at its commit")
        self.seeded = self.work
        os.makedirs(self.work)
        self.refused("hold one another")

    def test_a_seed_list_that_is_missing_unreadable_empty_malformed_or_names_an_unknown_item_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        for name, content, words in (
                ("not json", "{", ["cannot be read as JSON"]),
                ("an empty list", "[]", ["holds no list of seeds"]),
                ("an object with no seeds", json.dumps({"design": "x"}), ["holds no list of seeds"]),
                ("a seed with no item", json.dumps([{"id": "S1"}]), ["seed 1 of the seed list has no `id` and `item`"]),
                ("a seed with an empty id", json.dumps([{"id": " ", "item": "PINV-1"}]), ["seed 1"]),
                ("a seed that is not an object", json.dumps(["S1"]), ["seed 1"]),
                ("an id twice", json.dumps([{"id": "S1", "item": "PINV-1"}, {"id": "S1", "item": "STRAP-1"}]), ["gives the id S1 twice"]),
                ("an item that is no catalogue item", json.dumps([{"id": "S1", "item": "FLOOR-1"}]),
                 ["the seed S1 names the item 'FLOOR-1'", "no item of the circuit practice catalogue"]),
                ("the free pass entry", json.dumps([{"id": "S1", "item": "FREE-PASS"}]), ["no item of the circuit practice catalogue"])):
            with self.subTest(name=name):
                lfx.write(self.seeds, content)
                self.refused(*words)
        lfx.write(self.seeds, json.dumps(SEEDS))
        os.remove(self.seeds)
        self.refused("does not exist")

    def test_a_seed_list_inside_the_seeded_repository_the_work_folder_or_this_repository_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        for name, path in (("the seeded repository", os.path.join(self.seeded, "seeds.json")),
                           ("this repository", os.path.join(REPO, "seeds-test.json")),
                           ("the work folder", os.path.join(self.work, "seeds.json"))):
            with self.subTest(name=name):
                self.seeds = path
                if name != "this repository":
                    lfx.write(path, json.dumps(SEEDS))
                    if name == "the seeded repository":
                        lfx.git(self.seeded, "add", "-A")
                        lfx.git(self.seeded, "commit", "-q", "-m", "with seeds")
                elif not os.path.exists(path):
                    lfx.write(path, json.dumps(SEEDS))
                    self.addCleanup(os.remove, path)
                self.refused(f"is inside {name}") if name != "the work folder" else self.refused("already holds files")

    def test_a_bound_below_one_and_an_empty_model_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.refused("the bound 0 is below one", args=("--bound", "0"))
        self.refused("--design-model is empty", args=("--design-model", " "))
        self.refused("--baseline-model is empty", args=("--baseline-model", ""))

    def test_a_copy_the_check_refuses_or_a_tool_that_cannot_run_stops_the_command_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        def failing(work, seeded, kicad):
            raise srp.Refused(["the pre-order check fails the seeded copy", "CHECK | VIOLATION | x"])

        self.refused("the pre-order check fails the seeded copy", "CHECK / VIOLATION / x", preparer=failing)

        def missing(work, seeded, kicad):
            raise board_check.CannotRun("no KiCad")
        status, text, err = self.go(preparer=missing)
        self.assertEqual(status, 2)
        self.assertIn("RESULT | CANNOT RUN | no KiCad", err)
        self.assertEqual(self.calls(), [])
        shutil.rmtree(self.work)
        status, text, err = self.go("--json", preparer=missing)
        self.assertEqual((status, json.loads(text)["result"]), (2, "CANNOT RUN"))

    def test_an_agent_command_line_that_is_missing_stops_the_run_with_a_cannot_run(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.recorded()
        with mock.patch.dict(os.environ, {ex.AGENT_ENV: os.path.join(self.root, "no-such-agent")}):
            status, text, err = self.go()
        self.assertEqual(status, 2, text + err)
        self.assertIn("CANNOT RUN", err)
        shutil.rmtree(self.work)
        self.baselines = os.path.join(self.root, "none.json")
        with mock.patch.dict(os.environ, {ex.AGENT_ENV: os.path.join(self.root, "no-such-agent")}):
            status, text, err = self.go()
        self.assertEqual(status, 2, "the single form's run cannot start either")
        self.assertFalse(os.path.exists(self.baselines))

    def test_a_baselines_file_that_cannot_be_read_is_refused_and_one_that_holds_the_key_is_never_added_to(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        lfx.write(self.baselines, "{")
        self.refused("cannot be read as JSON")
        key = self.recorded()
        with self.assertRaises(srp.Refused) as caught:
            harness.write_baseline(self.baselines, "again", SEEDS, key, single("x", ["S1"]))
        self.assertIn("already holds single runs under this key", str(caught.exception))
        lfx.write(self.baselines, "{")
        with self.assertRaises(srp.Refused):
            harness.write_baseline(self.baselines, "again", SEEDS, key, single("x", ["S1"]))
        self.assertEqual(slurp(self.baselines), "{", "an unreadable file is left as it was")


class TheHarness(Proofed):
    def test_the_single_form_is_one_session_with_every_item_recorded_as_a_baseline_file_the_kit_loads(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        folder = srp.write_folder(self.work, self.seeded, self.preparer(self.work, self.seeded, "k"), self.source)
        out = os.path.join(self.root, "single-out")
        key, outcome = harness.run_single("schematic", TOOLS, folder, out, MID, dict(os.environ), SEEDS,
                                          lfx.git(self.seeded, "rev-parse", "HEAD"), self.tree(), srp.matches, self.baselines, "synthetic")
        self.assertEqual((key.form, key.model, key.design), (proof.SINGLE, MID, self.tree()))
        self.assertEqual(outcome.form, proof.SINGLE)
        self.assertEqual(outcome.seeds_found, ("S1", "S2"))
        self.assertEqual(len(outcome.sessions), 2, "the shared context and the one reviewer")
        self.assertEqual(outcome.judged_by["S1"], ("G1.r1",))
        loaded = proof.load_baselines(self.baselines)
        self.assertEqual(loaded.recorded(key)[0].as_dict(), outcome.as_dict())
        self.assertRegex(key.prompt, r"^[0-9a-f]{64}$", "the prompt is named by the hash of the message the session was given")
        with self.assertRaises(srp.Refused) as caught:
            harness.run_single("schematic", TOOLS, folder, os.path.join(self.root, "single-out-2"), MID, dict(os.environ), SEEDS,
                               "c", self.tree(), srp.matches, self.baselines, "synthetic")
        self.assertIn("a recorded baseline is not run again", str(caught.exception))

    def test_a_single_session_that_fails_stops_the_baseline_from_being_written(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        folder = srp.write_folder(self.work, self.seeded, self.preparer(self.work, self.seeded, "k"), self.source)
        self.scenario(fork_tools=["Read", "Bash", "StructuredOutput"], pairs=PAIRS)
        with self.assertRaises(srp.Refused) as caught:
            harness.run_single("schematic", TOOLS, folder, os.path.join(self.root, "single-out"), MID, dict(os.environ), SEEDS,
                               "c", self.tree(), srp.matches, self.baselines, "synthetic")
        self.assertIn("the single form's session failed", str(caught.exception))
        self.assertIn("started with tools", str(caught.exception))
        self.assertFalse(os.path.exists(self.baselines))

    def test_the_single_forms_plan_is_one_fork_and_has_no_replica(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        folder = srp.write_folder(self.work, self.seeded, self.preparer(self.work, self.seeded, "k"), self.source)
        plan = harness.single_plan_of("schematic", TOOLS, folder, os.path.join(self.root, "x"), MID, dict(os.environ))
        self.assertEqual(plan["forks"], 1)
        self.assertEqual(len(plan["groups"]), 1)
        self.assertEqual(plan["groups"][0]["replicas"], 1)
        self.assertEqual(sorted(plan["groups"][0]["units"]), sorted(["area-PINV", "area-STRAP", "area-DERATE", "free-pass"]))

    def test_a_caller_naming_a_fail_verdict_other_than_fail_has_it_stand_in_the_runs_merged_verdicts(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        record = {"plan": {"tool_commit": "tool"}, "merged": None, "rendered": [],
                  "lanes": [{"group": "G1", "replica": index, "units": ["u1"], "failure": None,
                             "record": {"standing": 0, "attempts": [{"tables": {"Verdicts": [
                                 {"Item": "i1", "Verdict": verdict, "Note": ""}], "Findings": []}}]}}
                            for index, verdict in ((1, "matches"), (2, "cannot judge"), (3, "differs"))]}
        declaration = decl.parse(json.dumps(fx.verdict_declaration_dict()), "caller.json")
        rules = merge.Rules(fail="differs")
        prepared = types.SimpleNamespace(declaration=declaration, rules=rules)
        loaded = types.SimpleNamespace(prepare=lambda folder: prepared)
        with mock.patch.object(harness.kit_caller, "load", return_value=loaded), \
                mock.patch.object(harness.store, "read_record", return_value=record), \
                mock.patch.object(harness.command, "figures_of_run", return_value=([], [])), \
                mock.patch.object(harness, "retrievals", return_value=0), \
                mock.patch.object(harness, "refused_for_rate_limit", return_value=0):
            outcome, _ = harness.outcome_of("demo", "callers", "run", "folder", self.root, [], "seeded",
                                            lambda seed, row: False, lambda text: {}, lambda item, cell: False)
        self.assertEqual(outcome.verdicts, {"i1": "differs"}, "the named verdict stands over cannot judge and a pass")
        prepared.rules = merge.Rules()
        with mock.patch.object(harness.kit_caller, "load", return_value=loaded), \
                mock.patch.object(harness.store, "read_record", return_value=record), \
                mock.patch.object(harness.command, "figures_of_run", return_value=([], [])), \
                mock.patch.object(harness, "retrievals", return_value=0), \
                mock.patch.object(harness, "refused_for_rate_limit", return_value=0):
            plain, _ = harness.outcome_of("demo", "callers", "run", "folder", self.root, [], "seeded",
                                          lambda seed, row: False, lambda text: {}, lambda item, cell: False)
        self.assertEqual(plain.verdicts, {"i1": "cannot judge"}, "a caller naming none keeps the kit's fail")

    def test_the_single_forms_recorded_baseline_is_merged_with_the_callers_own_rules(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        folder = srp.write_folder(self.work, self.seeded, self.preparer(self.work, self.seeded, "k"), self.source)
        seen = []
        real_resolve = harness.kit_caller.Prepared.resolve.__func__
        real_outcome = proof.outcome_from_run

        def resolve(cls, caller, review):
            found = real_resolve(cls, caller, review)
            found.rules = dataclasses.replace(found.rules, fail="differs")
            return found

        def outcome(*args, **kwargs):
            seen.append(kwargs.get("rules"))
            return real_outcome(*args, **kwargs)

        with mock.patch.object(harness.kit_caller.Prepared, "resolve", classmethod(resolve)), \
                mock.patch.object(proof, "outcome_from_run", outcome):
            harness.run_single("schematic", TOOLS, folder, os.path.join(self.root, "single-out"), MID, dict(os.environ), SEEDS,
                               lfx.git(self.seeded, "rev-parse", "HEAD"), self.tree(), srp.matches, self.baselines, "synthetic")
        self.assertEqual(len(seen), 1)
        self.assertIsNotNone(seen[0], "the caller's prepared rules are passed, not left to the kit's default")
        self.assertEqual(seen[0].fail, "differs")

    def test_the_layout_proof_keeps_every_name_it_exports_as_a_thin_use_of_the_shared_harness(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        for name in ("saved", "retrievals", "refused_for_rate_limit", "total", "tool_commit"):
            self.assertIs(getattr(lrp, name), getattr(harness, name), name)
        self.assertIs(lrp.Refused, harness.Refused)
        self.assertIs(srp.Refused, harness.Refused)
        for name in ("run_command", "plan_of", "outcome_of", "run_seed", "write_folder", "baseline_runs", "design_tree", "parsed_round",
                     "names", "matches", "build", "lines_of", "small_tier", "models_text", "dry_lines", "refusals", "main", "check_lines",
                     "RECORD", "TEXT", "BASELINES", "SEEDS", "SEEDED", "KEPT_TREE", "FOLDER", "REVIEW_TREE", "OUT_DIR", "COST_MULTIPLE",
                     "BASELINE_MODEL", "DESIGN_MODEL", "PRE_ORDER_MODEL", "CALLER", "ROUNDS", "VIEW_COMMANDS", "REPO"):
            self.assertTrue(hasattr(lrp, name), name)
        self.assertEqual(lrp.CALLER, "layout")
        self.assertEqual(srp.CALLER, "schematic")


class TheMatching(unittest.TestCase):
    def test_a_finding_names_a_seed_by_the_item_that_raised_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        seed = {"id": "S1", "item": "PINV-1"}
        self.assertTrue(srp.matches(seed, {"Item": "PINV-1"}))
        self.assertTrue(srp.matches(seed, {"Item": " PINV-1 "}))
        self.assertFalse(srp.matches(seed, {"Item": "PINV-10"}))
        self.assertFalse(srp.matches(seed, {"Item": "PINV-2", "Raised by": "PINV-1"}))
        self.assertFalse(srp.matches(seed, {}))

    def test_the_merged_rounds_raised_by_cells_are_read_with_or_without_the_round_heading(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        text = ("## Round 1\n\n### Verdicts\n\n| Item | Net or part | Verdict | Rests on | Why |\n|---|---|---|---|---|\n"
                "| PINV-1 | /IN | fail | x | finding 1.1 |\n\n### Findings\n\n| Finding | Raised by | Severity | What and where | Closed by |\n"
                "|---|---|---|---|---|\n| 1.1 | PINV-1 | function | w | |\n| 1.2 | free pass | cosmetic | w | |\n")
        self.assertEqual(srp.parsed_round(text)["raised_by"], ["PINV-1", "free pass"])
        self.assertEqual(srp.parsed_round(text.split("\n", 2)[2])["raised_by"], ["PINV-1", "free pass"])
        self.assertEqual(srp.parsed_round("## Round 1\n\n### Findings\n\nThis round raises no finding.\n")["raised_by"], [])
        self.assertTrue(srp.names("PINV-1", "PINV-1"))
        self.assertTrue(srp.names("PINV-1", "raised by PINV-1, DERATE-1"))
        self.assertFalse(srp.names("PINV-1", "PINV-10"))
        self.assertFalse(srp.names("PINV-1", "XPINV-1"))


class ThePreparation(unittest.TestCase):
    """The pre-order check, the netlist export and the sheet drawing, run as subprocesses; here the programs are replaced."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="schematic-prepare-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.seeded = sfx.make_repo(os.path.join(self.root, "seeded"))
        self.work = os.path.join(self.root, "work")
        patch = mock.patch.object(srp, "DESIGN", sfx.DESIGN)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(srp, "NAME", sfx.NAME)
        patch.start()
        self.addCleanup(patch.stop)

    def runner(self, check=(0, None), export=0, sheets=0, lines=None):
        """A subprocess.run that plays the check, the exporter and the sheet command, recording what it was asked."""
        asked = []
        real = subprocess.run

        def run(command, **kwargs):
            if command[0] == "git":
                return real(command, **kwargs)
            asked.append((command, kwargs))
            if "board_check.py" in command[1]:
                text = "\n".join(lines if lines is not None else [f"DESIGN | {self.seeded}/x | PASS", "RESULT | PASS"])
                return mock.Mock(returncode=check[0], stdout=text, stderr=check[1] or "")
            if "export" in command and "netlist" in command:
                if export == 0:
                    sfx.write(command[command.index("--output") + 1], sfx.NETLIST)
                return mock.Mock(returncode=export, stdout="", stderr="no" if export else "")
            if "schematic_sheets.py" in command[1]:
                if sheets == 0:
                    sfx.make_inputs(os.path.join(self.work, "made"))
                return mock.Mock(returncode=sheets, stdout="DESIGN | x | FAIL" if sheets == 1 else "", stderr="no kicad")
            return mock.Mock(returncode=0, stdout="", stderr="")
        return run, asked

    def test_the_check_is_run_on_the_seeded_copy_and_its_report_names_no_path_outside_the_copy(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        run, asked = self.runner()
        with mock.patch.object(srp.subprocess, "run", run):
            prepared = srp.prepare(self.work, self.seeded, "kicad-x")
        self.assertEqual(prepared["netlist"], os.path.join(self.work, srp.NETLIST))
        self.assertEqual(prepared["sheets"], os.path.join(self.work, srp.SHEETS, sfx.DESIGN))
        self.assertEqual(prepared["netlist_command"], f"kicad-cli sch export netlist --output <work folder>/review.net {sfx.NAME}.kicad_sch")
        report = slurp(prepared["report"])
        self.assertIn("DESIGN | ./x | PASS", report)
        self.assertNotIn(self.seeded, report)
        check = asked[0][0]
        self.assertEqual(check[check.index("--root") + 1], self.seeded)
        self.assertEqual(check[check.index("--kicad-cli") + 1], "kicad-x")
        export = next(command for command, _ in asked if "netlist" in command)
        self.assertEqual(export[:4], ["kicad-x", "sch", "export", "netlist"])
        self.assertEqual(export[-1], f"{sfx.NAME}.kicad_sch")
        self.assertTrue(os.path.isfile(os.path.join(self.work, srp.EXPORT, sfx.DESIGN, "board.kicad_sch")))
        draw = next(command for command, _ in asked if "schematic_sheets.py" in command[1])
        self.assertEqual(draw[draw.index("--root") + 1], self.seeded)

    def test_a_copy_the_check_refuses_a_check_that_cannot_run_and_an_export_or_drawing_that_fails_are_each_refused_or_cannot_run(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        run, _ = self.runner(check=(1, None), lines=["DESIGN | ./x | FAIL", "VIOLATION | ./x | rule | where | what"])
        with mock.patch.object(srp.subprocess, "run", run):
            with self.assertRaises(srp.Refused) as caught:
                srp.prepare(self.work, self.seeded, "k")
        self.assertIn("the pre-order check fails the seeded copy", str(caught.exception))
        self.assertIn("CHECK | VIOLATION | ./x | rule", str(caught.exception))
        run, _ = self.runner(check=(2, "no yaml"))
        with mock.patch.object(srp.subprocess, "run", run):
            with self.assertRaises(board_check.CannotRun) as caught:
                srp.prepare(self.work, self.seeded, "k")
        self.assertIn("no yaml", str(caught.exception))
        run, _ = self.runner(export=1)
        with mock.patch.object(srp.subprocess, "run", run):
            with self.assertRaises(board_check.CannotRun) as caught:
                srp.prepare(self.work, self.seeded, "k")
        self.assertIn("could not export the netlist", str(caught.exception))
        run, _ = self.runner(sheets=2)
        with mock.patch.object(srp.subprocess, "run", run):
            with self.assertRaises(board_check.CannotRun):
                srp.prepare(self.work, self.seeded, "k")
        run, _ = self.runner(sheets=1)
        with mock.patch.object(srp.subprocess, "run", run):
            with self.assertRaises(srp.Refused) as caught:
                srp.prepare(self.work, self.seeded, "k")
        self.assertIn("could not be drawn", str(caught.exception))

    def test_the_records_the_round_reads_are_those_of_the_method_the_committed_copy_holds(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C8: Over the kit's stub and synthetic folders, the proof command `task hw:schematic-review-proof` refuses a work folder inside the repository, a file or non-empty; a bound below 1 or an empty model; a seeded repository that is missing, not a git work tree with a commit, inside this repository or the work folder, dirty, or lacking the design; a seed list that is missing, unreadable, empty or malformed, has an id twice, names an item not in the catalogue, or lies inside this repository, the seeded repository or the work folder; a copy the pre-order check fails; and an unreadable baselines file. It never adds to a baselines file already holding the key, and a failed single session leaves no baseline written. It also checks the command's other behaviour. The single form is one session holding every item, with no replica and one fork, merged by the caller's own rules and written as a baseline file the kit loads; a verdict the caller names as a fail stands in the run's merged verdicts. A finding names a seed by its Item cell, and the merged round's Raised by cells are read with or without the round heading. The review folder is written by the folder command from the seeded commit with the netlist and the sheets, no folder from its parent up to the work folder holds anything else, and the check runs on the seeded copy with a report naming no path outside it and the round's records those of the committed method. A check that cannot run, a copy the check refuses, a failing export or drawing, or a missing agent command line stops the command with a cannot run before any session. The dry mode prints the plan, the group and fork counts and the predicted cost and time beside the bounds, takes the bounds from the prediction when no single run is recorded, warns when the prediction is over a bound or within a tenth of it, and starts no session. The proof record is written in text and in JSON with the same content: each run's seeds found, wall time, cost, findings matching no seed, sessions with their figures, retrievals and those that failed, calls refused for a rate limit, and the verdict differences between the forms, naming a seed no replica reported and the replicas that raised the others. The pooled criterion judges the fanned-out run, failing it, and the command exiting 1, when the seeds found fall below the floor, a seed every single run found is missed, the wall time exceeds half the single mean or the cost exceeds the stated multiple of the single mean, and requires a second fanned-out run when the first is within ten per cent of a bound. Out of scope: any live run, which the schematic proof solution holds.
        self.assertEqual(srp.record_names(self.seeded), ["constraints.md", "circuit-proof.md", "separation-basis.yaml"])
        self.assertIn("bring-up-provision.md", srp.RECORDS)
        self.assertIn("pin-allocation.yaml", srp.RECORDS)
        self.assertIn("parts-specification.yaml", srp.RECORDS)
        self.assertIn("catalogue-extract.yaml", srp.RECORDS)
        self.assertNotIn("schematic-review.md", srp.RECORDS)
        self.assertNotIn("designer-notes.md", srp.RECORDS)


if __name__ == "__main__":
    unittest.main()
