#!/usr/bin/env python3
"""The critical-routing review proof command: one command that renders the views of the seeded copy, writes the review folder with
the folder command's critical-routing mode, runs the single form once through the kit and records it as the baseline file, runs the
fanned-out form on the kit's command, and judges it by the kit's pooled criterion.

The kit's command runs over a stand-in for the agent command line, so no model and no KiCad is used, and the real agent command
line is never run. The seeded copy, its views and its seed list are synthetic stand-ins for what the seeding session and the views
command leave. The harness and the pooled criterion's arithmetic are held by the schematic and layout proofs' tests and the kit's.
Nothing here is the live proof, which spends real money and is run by the operator.
"""

from __future__ import annotations

import fcntl
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

import critical_routing_review_proof as crp  # noqa: E402
import layout_fixtures as lfx  # noqa: E402
import review_folder  # noqa: E402
import review_proof_harness as harness  # noqa: E402
import test_review_caller_critical_routing as caller_tests  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import executor as ex  # noqa: E402
from review_kit import proof  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
MID = crp.BASELINE_MODEL
SMALL = crp.DESIGN_MODEL
SEEDS = [{"id": "S1", "item": "FLOOR-1", "description": "a ground drawn as thin traces"},
         {"id": "S2", "item": "GROUND-1", "description": "a decoupling capacitor routed the long way round"},
         {"id": "S3", "item": "CLOCK-1", "description": "a sense connection tapped off a load track"}]
ALL_FAIL = {"FLOOR-1": "fail", "GROUND-1": "fail", "CLOCK-1": "fail"}


#: The caller tests' stand-in numbers findings from 1 in each unit; a fork that holds several units numbers them from 1 once, as the
#: prompt asks, so the stand-in is changed to count across the whole answer.
STUB = caller_tests.STUB.replace('''
for unit, body in re.findall(r"Your unit: (\\S+)\\n(.*?)(?=Your unit: |\\Z)", text, re.S):
    found = 0
''', '''
found = 0
for unit, body in re.findall(r"Your unit: (\\S+)\\n(.*?)(?=Your unit: |\\Z)", text, re.S):
''')
assert STUB != caller_tests.STUB


def slurp(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as handle:
        return handle.read()


def dear(*found):
    """Two single runs, slow and dear beside the stub's, the first finding the seeds named and the second one fewer, so the
    floor is one below what the fanned run finds and no bound is near."""
    return [single("one", found, wall=1e6, cost=1e3), single("two", found[:-1], wall=1e6, cost=1e3)]


def single(run_id, found, wall=1000.0, cost=5.0):
    return proof.RunOutcome(run_id, proof.SINGLE, "tool", "seeded", tuple(found), (), {}, {s: ("single",) for s in found},
                            {s["id"]: ("single",) for s in SEEDS}, (proof.SessionRecord("single", wall, cost, 1, 1, 1),), wall, cost,
                            ("first_call_read",))


class Proofed(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="critical-routing-proof-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.work = os.path.join(self.root, "work")
        self.source = lfx.make_repo(os.path.join(self.root, "source"), method=lfx.METHOD_ROUTING)
        self.seeded = self.source
        self.views = lfx.make_views(self.root)["views"]
        self.seeds = os.path.join(self.root, "seeds.json")
        lfx.write(self.seeds, json.dumps({"design": lfx.DESIGN, "seeds": SEEDS}))
        self.baselines = os.path.join(self.root, "baselines.json")
        self.log = os.path.join(self.root, "agent.log")
        self.scenario_path = os.path.join(self.root, "scenario.json")
        self.program = os.path.join(self.root, "agent")
        lfx.write(self.program, STUB.replace("PYTHON", sys.executable, 1).replace("TOOLS", repr(TOOLS)))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        for patch in (mock.patch.dict(os.environ, {ex.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path, "STUB_LOG": self.log}),
                      mock.patch.object(crp, "DESIGN", lfx.DESIGN), mock.patch.object(crp, "NAME", "board"),
                      mock.patch.object(kit_caller, "load", caller_tests.load_with_synthetic_couplings)):
            patch.start()
            self.addCleanup(patch.stop)
        self.scenario(verdicts=ALL_FAIL)

    def scenario(self, **values):
        values.setdefault("model_verdicts", {MID: {"CLOCK-1": "pass"}})
        lfx.write(self.scenario_path, json.dumps(values))

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def mid_calls(self):
        return [call for call in self.calls() if MID in call["args"]]

    def preparer(self, work, seeded, kicad_cli, resvg):
        """What the views command leaves, synthetic."""
        return {"views": self.views}

    def tree(self):
        return lfx.git(self.seeded, "rev-parse", f"HEAD:{lfx.DESIGN}")

    def prompt(self):
        """The hash of the message the single form's session is given for this seeded copy, as the command computes it."""
        self.go("--dry")
        folder = os.path.join(self.work, crp.FOLDER)
        key = harness.single_key(crp.CALLER, crp.TOOLS_DIR, folder, os.path.join(self.work, crp.SINGLE_OUT), MID,
                                 crp.load_seeds(self.seeds, folder), self.tree(), dict(os.environ))
        shutil.rmtree(self.work)
        return key.prompt

    def recorded(self, runs=None, model=MID, seeds=SEEDS, design=None, prompt=None):
        """A baselines file of synthetic single runs under a key of this seed list, design, model and prompt; by default the
        key the command would record the single form under."""
        runs = runs if runs is not None else [single("one", ["S1", "S2"])]
        prompt = prompt or self.prompt()
        key = proof.BaselineKey(proof.seed_list_hash(seeds), design or self.tree(), model, proof.SINGLE, prompt)
        with open(self.baselines, "w", encoding="utf-8") as handle:
            json.dump({"version": proof.BASELINES_VERSION, "source": "synthetic", "seeds": seeds,
                       "baselines": [{"key": key.as_dict(), "runs": [run.as_dict() for run in runs]}]}, handle)
        return key

    def go(self, *extra, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        status = crp.main(["--work", self.work, "--seeded-repo", self.seeded, "--seeds", self.seeds, *extra], out=out, err=err,
                          preparer=kwargs.pop("preparer", self.preparer), baselines=kwargs.pop("baselines", self.baselines),
                          documents_repo=self.source, **kwargs)
        return status, out.getvalue(), err.getvalue()

    def record(self):
        return json.loads(slurp(os.path.join(self.work, crp.RECORD)))

    def again(self, *extra):
        """The command run once more on a fresh work folder and a fresh agent log."""
        shutil.rmtree(self.work, ignore_errors=True)
        if os.path.exists(self.log):
            os.remove(self.log)
        return self.go(*extra)


class TheBaseline(Proofed):
    def test_the_single_run_is_made_once_through_the_kit_and_written_as_a_baseline_file_the_kit_loads_under_its_own_key(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.assertFalse(os.path.exists(self.baselines))
        status, text, err = self.go()
        self.assertIn(status, (0, 1), text + err)
        single_calls = self.mid_calls()
        self.assertEqual(len(single_calls), 2, "the single form: a shared context that judges nothing and one session")
        fork = next(call for call in single_calls if call["resume"] is not None)
        self.assertEqual(sorted(fork["units"]), ["area-CLOCK", "area-FLOOR", "area-GROUND"], "one session holds every unit")
        for item in ("FLOOR-1", "FLOOR-2", "GROUND-1", "CLOCK-1"):
            self.assertIn(f"- {item}", fork["prompt"])
        loaded = proof.load_baselines(self.baselines)
        (key,) = loaded.keys.values()
        self.assertEqual((key.seeds, key.design, key.model, key.form), (proof.seed_list_hash(SEEDS), self.tree(), MID, proof.SINGLE))
        self.assertRegex(key.prompt, r"^[0-9a-f]{64}$")
        (run,) = loaded.recorded(key)
        self.assertEqual((run.form, run.seeds_found), (proof.SINGLE, ("S1", "S2")), "the mid-tier reviewer misses the clock seed")
        self.assertEqual(run.seeded_commit, lfx.git(self.seeded, "rev-parse", "HEAD"))
        record = self.record()
        self.assertEqual(len(record["keys"]), 1)
        self.assertEqual(record["keys"][0]["design"], self.tree())
        self.assertEqual(record["critical_routing"]["baseline_key"], key.id)
        self.assertIn("run now, recorded in", record["critical_routing"]["single_form"])
        self.assertIn(key.id, record["critical_routing"]["single_form"])

    def test_run_again_for_a_key_whose_baseline_is_recorded_the_single_form_is_refused_and_the_key_named(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.go()
        (key,) = proof.load_baselines(self.baselines).keys.values()
        before = slurp(self.baselines, "rb")
        status, text, err = self.again()
        self.assertIn(status, (0, 1), text + err)
        self.assertEqual(self.mid_calls(), [], "no single session is started the second time")
        self.assertEqual(slurp(self.baselines, "rb"), before, "the recorded baseline file is left as it was")
        record = self.record()
        self.assertEqual(record["critical_routing"]["single_form"], f"recorded under key {key.id}")
        self.assertEqual(record["critical_routing"]["baseline_key"], key.id)
        self.assertIn(f"BASELINE KEY | {key.id}", text)
        self.assertIn(f"(recorded under key {key.id})", text)
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry")
        self.assertEqual(status, 0, text + err)
        self.assertIn(f"SINGLE | recorded under key {key.id}", text)

    def test_for_a_key_that_differs_in_seed_list_design_model_or_prompt_the_single_form_is_run_and_added_beside_the_recorded_one(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        for name, change in (("another seed list", dict(seeds=SEEDS[:2])), ("another design", dict(design="e" * 40)),
                             ("another model", dict(model="claude-other-9")), ("another prompt", dict(prompt="q" * 64))):
            with self.subTest(name=name):
                self.recorded(**change)
                status, text, err = self.again()
                self.assertIn(status, (0, 1), text + err)
                self.assertEqual(len(self.mid_calls()), 2, "the single form ran")
                self.assertEqual(len(proof.load_baselines(self.baselines).keys), 2, "the file keeps the key it held and holds the new one")

    def test_a_baselines_file_that_cannot_be_read_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        lfx.write(self.baselines, "{")
        status, text, err = self.go()
        self.assertEqual(status, 1, text + err)
        self.assertIn("cannot be read as JSON", text)
        self.assertEqual(self.calls(), [], "no session was started")
        self.assertEqual(slurp(self.baselines), "{", "an unreadable file is left as it was")

    def test_a_baselines_file_that_holds_the_key_with_no_runs_or_is_unusable_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.recorded(runs=[])
        held = slurp(self.baselines, "rb")
        status, text, err = self.go()
        self.assertEqual(status, 1, text + err)
        self.assertIn("with no runs", text)
        self.assertEqual((self.calls(), slurp(self.baselines, "rb")), ([], held), "no session, and the file is left as it was")
        good = {"key": {"seeds": "a", "design": "b", "model": "c", "form": proof.SINGLE, "prompt": "d"}, "runs": []}
        for name, content in (("a wrong version", {"version": 0, "baselines": [good]}),
                              ("no baselines", {"version": proof.BASELINES_VERSION, "baselines": []}),
                              ("a group without runs", {"version": proof.BASELINES_VERSION, "baselines": [{"key": good["key"]}]}),
                              ("a run missing fields", {"version": proof.BASELINES_VERSION,
                                                         "baselines": [{**good, "runs": [{"id": "one"}]}]})):
            with self.subTest(name=name):
                lfx.write(self.baselines, json.dumps(content))
                status, text, err = self.again()
                self.assertEqual(status, 1, text + err)
                self.assertIn("REFUSED", text)
                self.assertEqual(self.calls(), [], "no session was started")

    def test_a_baselines_file_whose_lock_is_held_refuses_a_second_invocation_without_a_session(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        with open(self.baselines + ".lock", "a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            status, text, err = self.go()
        self.assertEqual(status, 1, text + err)
        self.assertIn(self.baselines + ".lock", text)
        self.assertEqual(self.calls(), [], "no session was started")
        self.assertFalse(os.path.exists(self.baselines), "no baseline was written")
        status, text, err = self.again()
        self.assertIn(status, (0, 1), text + err)
        self.assertTrue(os.path.exists(self.baselines), "the lock is released when the run ends")

    def test_the_record_is_written_in_text_and_in_json_with_the_same_content(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.scenario(verdicts={**ALL_FAIL, "FLOOR-2": "fail"})
        self.recorded(dear("S1", "S2", "S3"))
        status, text, err = self.go("--json")
        self.assertEqual(status, 0, text + err)
        document = json.loads(text)
        record = self.record()
        self.assertEqual(document["record"], record)
        written = slurp(os.path.join(self.work, crp.TEXT))
        run = record["fanned_runs"][0]
        for session in run["sessions"]:
            self.assertIn(f"SESSION | {session['session']} |", written)
        self.assertIn("UNSEEDED | ", written, "the failing verdict on the item no seed names")
        self.assertIn(f"SEED | S1 | {run['id']} | raised by", written)
        kinds = ("SESSION |", "SEED |", "UNSEEDED |", "BASELINE KEY |")
        self.assertEqual(sorted(line for line in written.splitlines() if line.startswith(kinds)),
                         sorted(line for line in document["lines"] if line.startswith(kinds)))
        self.assertEqual(written.splitlines(), document["lines"])


class TheReviewSpecifics(Proofed):
    def test_a_seed_is_found_when_the_fanned_run_gives_a_failing_verdict_against_the_item_that_covers_it(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.scenario(verdicts={"FLOOR-1": "fail", "GROUND-1": "fail"})
        self.recorded(dear("S1", "S2"))
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        record = self.record()
        self.assertEqual(record["fanned_runs"][0]["seeds_found"], ["S1", "S2"])
        self.assertEqual(record["critical_routing"]["fanned"]["merged_round_seeds_found"], ["S1", "S2"],
                         "the merged pass names the same seeds as the replicas' findings")
        self.assertEqual(record["seed_replicas"]["S3"], {record["fanned_runs"][0]["id"]: []})
        self.assertIn("SEED | S3 | critical-routing-fanned-2 | raised by none", text)

    def test_a_seed_is_matched_by_the_exact_item_and_a_pass_row_that_stood_after_a_cannot_judge_counts_by_its_last_verdict(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        seed = {"id": "S1", "item": "FLOOR-1"}
        self.assertTrue(crp.matches(seed, {"Item": "FLOOR-1"}))
        self.assertFalse(crp.matches(seed, {"Item": "FLOOR-10"}))
        self.assertFalse(crp.matches(seed, {"Item": "XFLOOR-1"}))
        self.assertFalse(crp.matches(seed, {"Item": "FLOOR-2"}))
        text = "\n".join(["## Critical routing", "", "### Pass 1", "", "| Item | Kind | Severity | Verdict | Rests on | Why |",
                          "|---|---|---|---|---|---|",
                          "| FLOOR-1 | judgement | function | fail | layer-F.Cu | finding 1 |",
                          "| FLOOR-2 | judgement | function | pass | layer-F.Cu | fine |",
                          "| `GROUND-1` | judgement | function | cannot judge, then fail at abc1234 | layer-F.Cu | finding 2 |",
                          "| CLOCK-1 | judgement | function | cannot judge, then pass at abc1234 | layer-F.Cu | fine |", ""])
        self.assertEqual(crp.parsed_round(text), {"raised_by": ["FLOOR-1", "GROUND-1"]})
        self.assertEqual(crp.parsed_round(text.split("### Pass 1")[1]), {"raised_by": ["FLOOR-1", "GROUND-1"]},
                         "read with or without the pass heading")
        self.assertTrue(crp.names("FLOOR-1", "FLOOR-1"))
        self.assertFalse(crp.names("FLOOR-1", "FLOOR-10"))

    def test_the_fanned_form_runs_two_replicas_and_is_judged_at_a_cost_multiple_of_one_and_a_quarter(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.assertEqual((crp.REPLICAS, crp.COST_MULTIPLE), (2, 1.25))
        self.recorded(dear("S1", "S2", "S3"))
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        record = self.record()
        self.assertEqual(record["cost_multiple"], 1.25)
        for seed, who in record["seed_replicas"].items():
            self.assertEqual(len(next(iter(who.values()))), 2, f"{seed} is raised by both replicas")
        small = [call for call in self.calls() if SMALL in call["args"]]
        self.assertEqual(len([call for call in small if call["resume"] is None]), 1, "one shared context for the replicas")
        self.assertIn(f"fanned form on {SMALL} with 2 replicas", text)
        self.assertIn("cost multiple 1.25", text)
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry")
        self.assertRegex(text, r"PLAN \| fanned \| 2 replicas on claude-haiku-5-5 \| \d groups")
        self.assertIn("COST MULTIPLE | 1.25 | bounds: cost at most $1250.00 (1.25 times the single mean $1000.00)", text)

    def test_the_review_folder_is_the_critical_routing_mode_of_the_folder_command_with_the_views_and_no_check_report(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        status, text, err = self.go("--dry")
        self.assertEqual(status, 0, text + err)
        folder = os.path.join(self.work, crp.FOLDER)
        content = lfx.round_file(folder)
        self.assertTrue(review_folder.is_critical_routing_fields(content["fields"]), content["fields"])
        self.assertEqual(content["number"], 1)
        self.assertEqual(content["commit"], lfx.git(self.seeded, "rev-parse", "HEAD"))
        self.assertTrue(content["views"][0].startswith("task hw:views -- --board board.kicad_pcb --project board.kicad_pro --class Power "
                                                       "--class Supply --class Ground"))
        self.assertTrue(os.path.isfile(os.path.join(folder, "views", "layer-F.Cu.png")))
        self.assertFalse(os.path.exists(os.path.join(folder, "check-report.txt")))
        self.assertEqual(os.listdir(os.path.dirname(folder)), ["review"], "the folder is alone where a session can read upward")
        self.assertFalse(os.path.exists(os.path.join(folder, "seeds.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.work, crp.SEEDS)), "the seed list is kept apart from the folder")

    def test_the_views_are_rendered_by_the_command_from_the_seeded_commit_for_the_critical_classes(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        said = []

        def fake(argv, **kwargs):
            said.append((argv, kwargs.get("cwd")))
            return subprocess.CompletedProcess(argv, 0, "", "")

        with mock.patch.object(crp, "subprocess", types.SimpleNamespace(run=fake)):
            prepared = crp.prepare(self.work, self.seeded, "kicad-cli-x", "resvg-x")
        (argv, cwd), = said
        self.assertEqual(os.path.basename(argv[1]), "board_views.py")
        self.assertEqual(argv[argv.index("--kicad-cli") + 1], "kicad-cli-x")
        self.assertEqual(argv[argv.index("--resvg") + 1], "resvg-x")
        self.assertEqual([argv[at + 1] for at, word in enumerate(argv) if word == "--class"], ["Power", "Supply", "Ground"])
        self.assertEqual(prepared["views"], argv[argv.index("--out") + 1])
        self.assertEqual(os.path.realpath(cwd), os.path.realpath(os.path.join(self.work, crp.EXPORT, lfx.DESIGN)))
        self.assertTrue(os.path.isfile(os.path.join(cwd, "board.kicad_pcb")), "the copy as the commit holds it")
        with mock.patch.object(crp, "subprocess", types.SimpleNamespace(run=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 2, "", "no resvg"))):
            with self.assertRaises(crp.board_check.CannotRun):
                crp.prepare(os.path.join(self.root, "again"), self.seeded, "k", "r")


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

    def test_a_work_folder_inside_the_repository_is_refused_naming_it_and_the_review_folder_it_would_hold(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        inside = os.path.join(REPO, "critical-routing-proof-test")
        said = "; ".join(crp.refusals(inside))
        self.assertIn(f"the work folder {inside} is inside the repository", said)
        self.assertIn(os.path.join(inside, crp.FOLDER), said)
        lfx.write(os.path.join(self.work, "a.txt"), "x")
        self.refused("already holds files")
        lfx.write(self.work, "x")
        self.refused("is a file")
        os.remove(self.work)

    def test_a_seed_list_inside_the_repository_the_seeded_repository_or_the_work_folder_or_missing_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        inside_repo = os.path.join(REPO, "seeds-critical-routing-test.json")
        lfx.write(inside_repo, json.dumps(SEEDS))
        self.addCleanup(os.remove, inside_repo)
        inside_seeded = os.path.join(self.seeded, "seeds.json")
        lfx.write(inside_seeded, json.dumps(SEEDS))
        lfx.git(self.seeded, "add", "-A")
        lfx.git(self.seeded, "commit", "-q", "-m", "with seeds")
        for name, path in (("this repository", inside_repo), ("the seeded repository", inside_seeded)):
            with self.subTest(name=name):
                self.seeds = path
                self.refused(f"the seed list {path} is inside {name}")
        self.seeds = os.path.join(self.root, "nowhere.json")
        self.refused("does not exist")

    def test_a_seed_list_that_is_unreadable_malformed_or_names_an_item_the_method_lacks_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        for name, content, words in (
                ("not json", "{", ["cannot be read as JSON"]),
                ("an empty list", "[]", ["holds no list of seeds"]),
                ("a seed with no item", json.dumps([{"id": "S1"}]), ["seed 1 of the seed list has no `id` and `item`"]),
                ("an id twice", json.dumps([{"id": "S1", "item": "FLOOR-1"}, {"id": "S1", "item": "CLOCK-1"}]), ["gives the id S1 twice"]),
                ("an item of no catalogue", json.dumps([{"id": "S1", "item": "NOPE-1"}]),
                 ["the seed S1 names the item 'NOPE-1'", "no item of the layout practice catalogue"])):
            with self.subTest(name=name):
                lfx.write(self.seeds, content)
                self.refused(*words)

    def test_a_seeded_repository_that_is_missing_dirty_without_the_design_or_inside_this_one_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        real = self.seeded
        self.seeded = os.path.join(self.root, "nowhere")
        self.refused("is not a folder")
        self.seeded = real
        lfx.write(os.path.join(real, "stray.txt"), "x")
        self.refused("has changes that are not committed")
        os.remove(os.path.join(real, "stray.txt"))
        self.seeded = os.path.join(REPO, "hardware")
        self.refused("is inside this repository")
        self.seeded = real
        with mock.patch.object(crp, "DESIGN", "hardware/other"):
            self.refused("holds no hardware/other at its commit")

    def test_a_bound_below_one_and_an_empty_model_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.refused("the bound 0 is below one", args=("--bound", "0"))
        self.refused("--design-model is empty", args=("--design-model", " "))
        self.refused("--baseline-model is empty", args=("--baseline-model", ""))

    def test_a_missing_agent_command_line_stops_the_run_with_a_cannot_run_and_writes_no_baseline(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        with mock.patch.dict(os.environ, {ex.AGENT_ENV: os.path.join(self.root, "no-such-agent")}):
            status, text, err = self.go()
        self.assertEqual(status, 2, text + err)
        self.assertIn("CANNOT RUN", err)
        self.assertFalse(os.path.exists(self.baselines))


class TheModule(unittest.TestCase):
    def test_the_command_is_a_thin_use_of_the_shared_harness_and_names_its_own_baseline_file(self):
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        # SOL-HW-REVIEW-FAN-OUT-CRITICAL-ROUTING-PROOF.C2: Over the kit's stub, the proof command for the critical-routing check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a seed list or review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        for name in ("run_single", "outcome_of", "single_key", "recorded_under", "baseline_lock", "plan_of", "run_command",
                     "fanned_runs", "numbered"):
            self.assertIs(getattr(crp, "harness"), harness)
            self.assertFalse(hasattr(crp, name), f"{name} is the harness's, not copied into the command")
        source = slurp(crp.__file__)
        for call in ("harness.run_single(", "harness.outcome_of(", "harness.single_key(", "harness.recorded_under(",
                     "harness.baseline_lock(", "harness.fanned_runs(", "harness.numbered("):
            self.assertIn(call, source)
        self.assertIs(crp.Refused, harness.Refused)
        self.assertEqual(os.path.relpath(crp.BASELINES, TOOLS), os.path.join("tests", "fixtures", "review_baselines",
                                                                              "critical_routing_single_runs.json"))
        self.assertEqual((crp.CALLER, crp.DESIGN, crp.CLASSES), ("critical_routing", "hardware/proof/method-proof",
                                                                  ("Power", "Supply", "Ground")))


if __name__ == "__main__":
    unittest.main()
