#!/usr/bin/env python3
"""The production-files review proof command: one command that takes the folder and the seed list `task hw:production-seed` writes,
runs the single form once through the kit and records it as the baseline file, runs the fanned-out form on the kit's command with
the pre-order round's three replicas, and judges it by the kit's pooled criterion.

The kit's command runs over a stand-in for the agent command line, so no model, no KiCad and no gerbonara is used, and the real agent
command line is never run. The production-files folder is the synthetic one the production folder command's tests write, and the
seed list is a synthetic stand-in for the one the seeding writes apart. The harness and the pooled criterion's arithmetic are held by
the schematic and layout proofs' tests and the kit's. Nothing here is the live proof, which spends real money and is run by the
operator.
"""

from __future__ import annotations

import fcntl
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import layout_fixtures as lfx  # noqa: E402
import production_files_review_proof as pfp  # noqa: E402
import production_fixtures as pf  # noqa: E402
import review_caller_production_files as caller  # noqa: E402
import review_proof_harness as harness  # noqa: E402
import test_review_caller_production_files as caller_tests  # noqa: E402
from review_kit import executor as ex  # noqa: E402
from review_kit import proof  # noqa: E402
from review_kit import results as kit_results  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
MID = pfp.BASELINE_MODEL
SEEDS = [{"id": "S1", "area": "placement file: rotation", "target": "R1", "description": "R1 turned in the placement file"},
         {"id": "S2", "area": "fabrication layer: shifted content", "target": "drill, F.Mask, B.Mask",
          "description": "a hole moved, so its drill and mask openings stand off"},
         {"id": "S3", "area": "placement file: polarity", "target": "U1", "description": "U1 reversed in the placement file"}]
#: The mid-tier model misses the part U1, as the replicas on it do; the small tier finds all three.
ALL_DIFFER = {"R1": "differs", "B.Mask": "differs", "U1": "differs"}


#: The caller tests' stand-in gives `cannot judge` to the parts without a drawing by the name of their unit; the single form holds
#: every unit in one, so the stand-in is changed to give it by the part, as a reviewer who finds no drawing does.
STUB = caller_tests.STUB.replace('if unit.startswith("nodrawing") else "matches"',
                                 'if unit.startswith("nodrawing") or item in ("X1", "X2", "Y1") else "matches"')
assert STUB != caller_tests.STUB


def slurp(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as handle:
        return handle.read()


def single(run_id, found, wall=1000.0, cost=5.0):
    return proof.RunOutcome(run_id, proof.SINGLE, "tool", "seeded", tuple(found), (), {}, {s: ("single",) for s in found},
                            {s["id"]: ("single",) for s in SEEDS}, (proof.SessionRecord("single", wall, cost, 1, 1, 1),), wall, cost,
                            ("first_call_read",))


def dear(*found):
    """Two single runs, slow and dear beside the stub's, the first finding the seeds named and the second one fewer, so the
    floor is one below what the fanned run finds and no bound is near."""
    return [single("one", found, wall=1e6, cost=1e3), single("two", found[:-1], wall=1e6, cost=1e3)]


class Proofed(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="production-files-proof-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.work = os.path.join(self.root, "proof-work")
        self.folder = pf.write_folder(self.root)
        # The folder `task hw:production-seed` writes holds no round file and no preview folder.
        os.remove(os.path.join(self.folder, "round.json"))
        shutil.rmtree(os.path.join(self.folder, "preview"))
        self.seeds = os.path.join(self.root, "seeds.json")
        lfx.write(self.seeds, json.dumps({"design": pf.DESIGN, "seeds": SEEDS}))
        self.baselines = os.path.join(self.root, "baselines.json")
        self.log = os.path.join(self.root, "agent.log")
        self.scenario_path = os.path.join(self.root, "scenario.json")
        self.program = os.path.join(self.root, "agent")
        lfx.write(self.program, STUB.replace("PYTHON", sys.executable, 1).replace("TOOLS", repr(TOOLS)))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        patch = mock.patch.dict(os.environ, {ex.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path, "STUB_LOG": self.log})
        patch.start()
        self.addCleanup(patch.stop)
        self.scenario(verdicts=ALL_DIFFER)

    def scenario(self, **values):
        values.setdefault("model_verdicts", {MID: {"U1": "matches"}})
        lfx.write(self.scenario_path, json.dumps({"layers": pf.LAYERS, **values}))

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def single_sessions(self):
        """The sessions the single form saved in this work folder, with a repair or cannot judge turn's number left off: none when
        it did not run, the shared context and the one reviewer's session when it did."""
        return sorted({meta["label"].split(".a")[0] for meta, _ in harness.saved(os.path.join(self.work, pfp.SINGLE_OUT, "streams"))})

    def tree(self):
        return pfp.base.design_tree(REPO, "HEAD", pfp.DESIGN)

    def loaded(self):
        return pfp.load_seeds(self.seeds, self.folder)

    def prompt(self):
        """The hash of the message the single form's session is given for this folder, as the command computes it."""
        shutil.rmtree(self.work, ignore_errors=True)
        review = os.path.join(self.work, pfp.REVIEW_DIR)
        pfp.complete_folder(self.folder, review, dict(os.environ))
        key = harness.single_key(pfp.CALLER, pfp.TOOLS_DIR, review, os.path.join(self.work, pfp.SINGLE_OUT), MID, self.loaded(),
                                 self.tree(), dict(os.environ))
        shutil.rmtree(self.work, ignore_errors=True)
        return key.prompt

    def recorded(self, runs=None, model=MID, seeds=None, design=None, prompt=None):
        """A baselines file of synthetic single runs under a key of this seed list, design, model and prompt; by default the
        key the command would record the single form under."""
        runs = runs if runs is not None else [single("one", ["S1", "S2"])]
        seeds = seeds if seeds is not None else self.loaded()
        key = proof.BaselineKey(proof.seed_list_hash(seeds), design or self.tree(), model, proof.SINGLE, prompt or self.prompt())
        with open(self.baselines, "w", encoding="utf-8") as handle:
            json.dump({"version": proof.BASELINES_VERSION, "source": "synthetic", "seeds": seeds,
                       "baselines": [{"key": key.as_dict(), "runs": [run.as_dict() for run in runs]}]}, handle)
        return key

    def go(self, *extra, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        status = pfp.main(["--work", self.work, "--folder", self.folder, "--seeds", self.seeds, *extra], out=out, err=err,
                          baselines=kwargs.pop("baselines", self.baselines), **kwargs)
        return status, out.getvalue(), err.getvalue()

    def record(self):
        return json.loads(slurp(os.path.join(self.work, pfp.RECORD)))

    def again(self, *extra):
        """The command run once more on a fresh work folder and a fresh agent log."""
        shutil.rmtree(self.work, ignore_errors=True)
        if os.path.exists(self.log):
            os.remove(self.log)
        return self.go(*extra)


class TheBaseline(Proofed):
    def test_the_single_run_is_made_once_through_the_kit_and_written_as_a_baseline_file_the_kit_loads_under_its_own_key(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.assertFalse(os.path.exists(self.baselines))
        status, text, err = self.go()
        self.assertIn(status, (0, 1), text + err)
        self.assertEqual(self.single_sessions(), ["G1.r1", "root"], "the single form: a shared context that judges nothing and one session")
        fork = next(call for call in self.calls() if call["resume"] is not None and len(call["units"]) > 1 and
                    all(f"- {item}" in call["prompt"] for item in pf.PLACED + pf.LAYERS))
        self.assertEqual(sorted(fork["units"]), sorted(set(fork["units"])), "one session holds every unit's rows")
        self.assertIn("layers", fork["units"])
        loaded = proof.load_baselines(self.baselines)
        (key,) = loaded.keys.values()
        self.assertEqual((key.seeds, key.design, key.model, key.form), (proof.seed_list_hash(self.loaded()), self.tree(), MID, proof.SINGLE))
        self.assertRegex(key.prompt, r"^[0-9a-f]{64}$")
        (run,) = loaded.recorded(key)
        self.assertEqual((run.form, run.seeds_found), (proof.SINGLE, ("S1", "S2")), "the mid-tier reviewer misses the part U1")
        self.assertEqual(run.seeded_commit, pfp.review_folder.committed_board(REPO, "HEAD", pfp.DESIGN)["sha"])
        record = self.record()
        self.assertEqual(len(record["keys"]), 1)
        self.assertEqual(record["production_files"]["baseline_key"], key.id)
        self.assertIn(key.id, record["production_files"]["single_form"])
        self.assertIn("run now, recorded in", record["production_files"]["single_form"])

    def test_run_again_for_a_key_whose_baseline_is_recorded_the_single_form_is_refused_and_the_key_named(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.go()
        (key,) = proof.load_baselines(self.baselines).keys.values()
        before = slurp(self.baselines, "rb")
        status, text, err = self.again()
        self.assertIn(status, (0, 1), text + err)
        self.assertEqual(self.single_sessions(), [], "no single session is started the second time")
        self.assertEqual(slurp(self.baselines, "rb"), before, "the recorded baseline file is left as it was")
        record = self.record()
        self.assertEqual(record["production_files"]["single_form"], f"recorded under key {key.id}")
        self.assertEqual(record["production_files"]["baseline_key"], key.id)
        self.assertIn(f"BASELINE KEY | {key.id}", text)
        self.assertIn(f"(recorded under key {key.id})", text)
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry")
        self.assertEqual(status, 0, text + err)
        self.assertIn(f"SINGLE | recorded under key {key.id}", text)

    def test_for_a_key_that_differs_in_seed_list_design_model_or_prompt_the_single_form_is_run_and_added_beside_the_recorded_one(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        for name, change in (("another seed list", dict(seeds=[dict(SEEDS[0], item="R1")])), ("another design", dict(design="e" * 40)),
                             ("another model", dict(model="claude-other-9")), ("another prompt", dict(prompt="q" * 64))):
            with self.subTest(name=name):
                self.recorded(**change)
                status, text, err = self.again()
                self.assertIn(status, (0, 1), text + err)
                self.assertEqual(self.single_sessions(), ["G1.r1", "root"], "the single form ran")
                self.assertEqual(len(proof.load_baselines(self.baselines).keys), 2, "the file keeps the key it held and holds the new one")

    def test_a_baselines_file_that_cannot_be_read_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        lfx.write(self.baselines, "{")
        status, text, err = self.go()
        self.assertEqual(status, 1, text + err)
        self.assertIn("cannot be read as JSON", text)
        self.assertEqual(self.calls(), [], "no session was started")
        self.assertEqual(slurp(self.baselines), "{", "an unreadable file is left as it was")

    def test_a_baselines_file_that_holds_the_key_with_no_runs_or_is_unusable_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
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
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
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
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.scenario(verdicts={**ALL_DIFFER, "R2": "differs"})
        self.recorded(dear("S1", "S2", "S3"))
        status, text, err = self.go("--json")
        self.assertEqual(status, 0, text + err)
        document = json.loads(text)
        record = self.record()
        self.assertEqual(document["record"], record)
        written = slurp(os.path.join(self.work, pfp.TEXT))
        run = record["fanned_runs"][0]
        for session in run["sessions"]:
            self.assertIn(f"SESSION | {session['session']} |", written)
        self.assertIn("UNSEEDED | ", written, "the differs row on the part no seed names")
        self.assertIn(f"SEED | S1 | {run['id']} | raised by", written)
        self.assertEqual(written.splitlines(), document["lines"])


class TheReviewSpecifics(Proofed):
    def test_a_seed_is_found_when_the_fanned_check_gives_a_row_that_is_not_a_match_against_a_part_or_a_layer_the_seed_names(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.scenario(verdicts={"B.Mask": "differs"}, model_verdicts={})
        self.recorded([single("one", ["S2"], wall=1e6, cost=1e3), single("two", [], wall=1e6, cost=1e3)])
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        record = self.record()
        run = record["fanned_runs"][0]
        self.assertEqual(run["seeds_found"], ["S2"], "one of the three layers the seed names is enough; no part row differs")
        self.assertEqual(record["production_files"]["fanned"]["merged_round_seeds_found"], ["S2"],
                         "the merged check record names the same seeds as the replicas' findings")
        self.assertEqual(record["seed_replicas"]["S1"], {run["id"]: []})
        self.assertIn("SEED | S1 | production-files-fanned-3 | raised by none", text)

    def test_a_seeded_part_the_fanned_check_cannot_judge_is_found_as_a_row_that_is_not_a_match(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.scenario(verdicts={"U1": "cannot judge"}, model_verdicts={})
        self.recorded([single("one", ["S1"], wall=1e6, cost=1e3), single("two", [], wall=1e6, cost=1e3)])
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        run = self.record()["fanned_runs"][0]
        self.assertEqual(run["seeds_found"], ["S3"], "U1 is judged cannot judge, raising no finding, and still names the seed")

    def test_rows_that_are_not_a_match_and_have_no_finding_are_given_as_findings_of_their_item(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        tables = {"Verdicts": [{"Item": "U1", "Verdict": "cannot judge", "Why": "no drawing"},
                               {"Item": "R1", "Verdict": "differs", "Why": "see 1"}, {"Item": "R2", "Verdict": "matches", "Why": "ok"}],
                  "Findings": [{"Finding": 1, "Item": "R1", "What and where": "turned"}]}
        self.assertEqual(pfp.unraised(tables), [{"Finding": "", "Item": "U1", "What and where": "no drawing"}])
        self.assertEqual(pfp.unraised({}), [])

    def test_a_seed_is_matched_by_the_exact_part_or_any_layer_it_names_without_regard_to_case(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        seed = {"id": "S2", "item": "drill, F.Mask, B.Mask"}
        for cell, expected in (("drill", True), ("F.Mask", True), ("b.mask", True), (" B.Mask ", True), ("F.SilkS", False),
                               ("B.Mas", False), ("R1", False), ("", False)):
            self.assertEqual(pfp.matches(seed, {"Item": cell}), expected, cell)
        self.assertFalse(pfp.matches({"id": "S1", "item": "R1"}, {"Item": "R10"}))
        self.assertTrue(pfp.names("R1", "R1"))
        self.assertEqual([each for each in pfp.targets("drill, F.Mask ,B.Mask,")], ["drill", "F.Mask", "B.Mask"])

    def test_the_merged_check_record_gives_the_rows_that_are_not_a_match_whether_part_or_layer(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        parts = [{"Part": "R1", **{column: "x" for column in caller.PART_COLUMNS}, "Verdict": "differs", "Why": "finding 1"},
                 {"Part": "R2", **{column: "x" for column in caller.PART_COLUMNS}, "Verdict": "matches", "Why": "ok"},
                 {"Part": "U1", **{column: "x" for column in caller.PART_COLUMNS}, "Verdict": "cannot judge", "Why": "no drawing"}]
        layers = [{"Layer": "F.Mask", "File": "f.gbr", "Compared with": "view", "Verdict": "matches", "Why": "ok"},
                  {"Layer": "drill", "File": "d.drl", "Compared with": "view", "Verdict": "differs", "Why": "finding 2"}]
        text = "\n".join(["### Parts", ""] + kit_results.table_lines(caller.PARTS_TABLE, parts) + ["", "### Layers", ""]
                         + kit_results.table_lines(caller.LAYERS_TABLE, layers) + ["", "### Findings", ""])
        self.assertEqual(pfp.parsed_round(text), {"raised_by": ["R1", "U1", "drill"]})

    def test_the_seeds_are_kept_with_the_parts_and_layers_they_name_and_a_target_the_folder_lacks_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        seeds = self.loaded()
        self.assertEqual([seed["item"] for seed in seeds], ["R1", "drill, F.Mask, B.Mask", "U1"])
        self.assertEqual([seed["id"] for seed in seeds], ["S1", "S2", "S3"])
        lfx.write(self.seeds, json.dumps([{"id": "S1", "target": "R1"}, {"id": "S2", "target": "F.Mask, Z99"}]))
        with self.assertRaises(pfp.Refused) as caught:
            pfp.load_seeds(self.seeds, self.folder)
        self.assertIn("the seed S2 names 'Z99', which is no placed part of the placement file or layer of the layer images",
                      str(caught.exception))

    def test_the_fanned_form_runs_three_replicas_and_is_judged_at_a_cost_multiple_of_two_and_a_quarter(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.assertEqual((pfp.REPLICAS, pfp.COST_MULTIPLE), (3, 2.25))
        self.scenario(verdicts=ALL_DIFFER, model_verdicts={})
        self.recorded(dear("S1", "S2", "S3"))
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        record = self.record()
        self.assertEqual(record["cost_multiple"], 2.25)
        for seed, who in record["seed_replicas"].items():
            self.assertEqual(len(next(iter(who.values()))), 3, f"{seed} is raised by all three replicas")
        labels = {session["session"].split(".")[1] for session in record["fanned_runs"][0]["sessions"] if session["session"].startswith("G")}
        self.assertEqual(labels, {"r1", "r2", "r3"})
        self.assertIn("with 3 replicas", text)
        self.assertIn("cost multiple 2.25", text)
        shutil.rmtree(self.work)
        status, text, err = self.go("--dry")
        self.assertRegex(text, r"PLAN \| fanned \| 3 replicas \| \d+ groups")
        self.assertIn("COST MULTIPLE | 2.25 | bounds: cost at most $2250.00 (2.25 times the single mean $1000.00)", text)

    def test_the_folder_is_read_where_the_seeding_wrote_it_and_the_seed_list_is_kept_apart_from_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        before = sorted(os.path.join(directory, name) for directory, _, names in os.walk(self.folder) for name in names)
        status, text, err = self.go("--dry")
        self.assertEqual(status, 0, text + err)
        self.assertEqual(self.calls(), [], "no session was started")
        self.assertFalse(os.path.exists(self.baselines), "a dry run records nothing")
        self.assertEqual(sorted(os.path.join(directory, name) for directory, _, names in os.walk(self.folder) for name in names), before,
                         "the folder is not written to")
        self.assertTrue(os.path.isfile(os.path.join(self.work, pfp.SEEDS)))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "seeds.json")))
        self.assertRegex(text, rf"SINGLE \| none recorded under key [0-9a-f]{{64}}, so the single form would run once on {MID}")


def tree_of(root):
    return {os.path.relpath(os.path.join(d, n), root): slurp(os.path.join(d, n), "rb")
            for d, _, names in os.walk(root) for n in names}


class TheCompletion(Proofed):
    def complete(self):
        review = os.path.join(self.root, "completed")
        return review, pfp.complete_folder(self.folder, review, {"KICAD_CLI": "/nonexistent/kicad-cli"})

    def test_the_seeded_folder_is_completed_in_a_copy_that_the_callers_prepare_accepts_and_the_folder_is_left_as_it_was(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: the proof command for the production-files check completes a copy of the seeded folder with a preview folder and a round file, and leaves the seeded folder as it was.
        before = tree_of(self.folder)
        review, commit = self.complete()
        self.assertEqual(tree_of(self.folder), before, "the user's folder is byte-identical")
        self.assertEqual(commit, pfp.review_folder.committed_board(REPO, "HEAD", pfp.DESIGN)["sha"])
        round_ = caller.production_round(review)
        self.assertEqual(round_["commit"], commit)
        self.assertEqual(round_["commands"], [pfp.SEEDING_COMMAND])
        self.assertIn("standing in for the assembler's preview", round_["preview"])
        self.assertIn("gerbonara 1.6.3", round_["tools"])
        self.assertTrue(caller.images_in(review, "preview"))
        self.assertEqual(sorted(os.listdir(os.path.join(review, "preview"))),
                         sorted(os.path.basename(each) for each in caller.images_in(self.folder, "placement")))
        self.assertTrue(caller_tests.prepared(review).declaration.units)

    def test_a_folder_that_holds_no_placement_image_or_already_holds_a_round_file_is_refused_and_nothing_is_written(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: the proof command refuses a folder it cannot complete naming the cause.
        review = os.path.join(self.root, "completed")
        with open(os.path.join(self.folder, "round.json"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        with self.assertRaises(pfp.Refused) as raised:
            pfp.complete_folder(self.folder, review, {})
        self.assertIn("round.json", " ".join(raised.exception.causes))
        os.remove(os.path.join(self.folder, "round.json"))
        shutil.rmtree(os.path.join(self.folder, "placement"))
        with self.assertRaises(pfp.Refused) as raised:
            pfp.complete_folder(self.folder, review, {})
        self.assertIn("no placement image", " ".join(raised.exception.causes))
        self.assertFalse(os.path.exists(review))

    def test_the_review_folder_the_kit_is_given_is_the_completed_copy_and_holds_no_seed_list(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: the folder given to the kit is the completed copy in the work folder, apart from the seed list.
        before = tree_of(self.folder)
        status, text, err = self.go("--dry")
        self.assertEqual(status, 0, text + err)
        review = os.path.join(self.work, pfp.REVIEW_DIR)
        self.assertTrue(os.path.isfile(os.path.join(review, "round.json")))
        self.assertFalse(os.path.exists(os.path.join(review, "seeds.json")))
        self.assertEqual(tree_of(self.folder), before)
        self.assertIn(f"{pfp.REVIEW_DIR}/", "".join(os.path.relpath(os.path.join(d, n), self.work) for d, _, ns in os.walk(review) for n in ns))


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

    def test_a_review_folder_inside_the_repository_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.folder = os.path.join(REPO, "hardware")
        self.refused(f"the review folder {self.folder} is inside the repository")
        self.folder = os.path.join(self.root, "nowhere")
        self.refused("is not a folder")

    def test_a_review_folder_and_a_work_folder_that_hold_one_another_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.work = os.path.join(self.folder, "work")
        self.refused("hold one another")
        self.work = self.root
        os.remove(self.seeds)
        self.refused("already holds files")

    def test_a_work_folder_inside_the_repository_a_file_or_not_empty_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.assertIn("is inside the repository", "; ".join(pfp.refusals(os.path.join(REPO, "production-proof-test"))))
        lfx.write(os.path.join(self.work, "a.txt"), "x")
        self.refused("already holds files")
        lfx.write(self.work, "x")
        self.refused("is a file")
        os.remove(self.work)

    def test_a_seed_list_inside_the_review_folder_the_work_folder_or_this_repository_or_missing_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        inside_repo = os.path.join(REPO, "seeds-production-files-test.json")
        lfx.write(inside_repo, json.dumps(SEEDS))
        self.addCleanup(os.remove, inside_repo)
        for name, path in (("the review folder", os.path.join(self.folder, "seeds.json")), ("this repository", inside_repo)):
            with self.subTest(name=name):
                lfx.write(path, json.dumps(SEEDS))
                self.seeds = path
                self.refused(f"the seed list {path} is inside {name}")
        self.seeds = os.path.join(self.root, "nowhere.json")
        self.refused("does not exist")

    def test_a_seed_list_that_is_unreadable_malformed_or_names_a_target_the_folder_lacks_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        for name, content, words in (
                ("not json", "{", ["cannot be read as JSON"]),
                ("an empty list", "[]", ["holds no list of seeds"]),
                ("a seed with no target", json.dumps([{"id": "S1", "item": "R1"}]), ["seed 1 of the seed list has no `id` and `target`"]),
                ("an id twice", json.dumps([{"id": "S1", "target": "R1"}, {"id": "S1", "target": "U1"}]), ["gives the id S1 twice"]),
                ("a part the file lacks", json.dumps([{"id": "S1", "target": "Z99"}]), ["the seed S1 names 'Z99'"])):
            with self.subTest(name=name):
                lfx.write(self.seeds, content)
                self.refused(*words)

    def test_a_bound_below_one_and_an_empty_model_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.refused("the bound 0 is below one", args=("--bound", "0"))
        self.refused("--fanned-model is empty", args=("--fanned-model", " "))
        self.refused("--baseline-model is empty", args=("--baseline-model", ""))

    def near_bound_singles(self):
        """Single runs whose cost bound the stub's first fanned-out run sits at ninety-five per cent of, so no other clause is near."""
        self.recorded(dear("S1", "S2", "S3"))
        self.assertEqual(self.go()[0], 0)
        cost = self.record()["fanned_runs"][0]["cost_usd"]
        shutil.rmtree(self.work)
        each = cost / 0.95 / 2.25
        return [single("one", ["S1", "S2", "S3"], wall=1e6, cost=each), single("two", ["S1", "S2"], wall=1e6, cost=each)], each

    def test_a_first_fanned_run_within_a_tenth_of_a_bound_is_followed_by_a_second_and_both_are_judged_together_one_inside_every_bound_runs_once(self):
        # SOL-HW-REVIEW-PROOFS-RUN-A-SECOND-FANNED-OUT-RUN.C1: When the first fanned-out run of a proof command is within ten per cent of a bound of the kit's pooled criterion, the command runs the fanned-out form a second time in its own output folder and judges both runs together, and never runs a third.
        singles, each = self.near_bound_singles()
        self.recorded(singles)
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        record = self.record()
        self.assertEqual([run["id"] for run in record["fanned_runs"]], ["production-files-fanned-3", "production-files-fanned-3-run-2"])
        self.assertEqual(len(record["production_files"]["fanned_runs"]), 2)
        self.assertTrue(os.path.isdir(os.path.join(self.work, pfp.FANNED_OUT)))
        self.assertTrue(os.path.isdir(os.path.join(self.work, pfp.FANNED_OUT + "-2")))
        self.assertEqual(record["cost_multiple"], 2.25)
        self.assertAlmostEqual(record["verdict"]["bounds"]["cost_usd"], 2.25 * each, places=6)
        self.assertEqual(record["verdict"]["status"], "pass")
        self.assertFalse(record["verdict"]["second_run_required"])
        shutil.rmtree(self.work)
        self.recorded(dear("S1", "S2", "S3"))
        status, text, err = self.go()
        self.assertEqual(status, 0, text + err)
        record = self.record()
        self.assertEqual([run["id"] for run in record["fanned_runs"]], ["production-files-fanned-3"])
        self.assertEqual(len(record["production_files"]["fanned_runs"]), 1)
        self.assertFalse(os.path.exists(os.path.join(self.work, pfp.FANNED_OUT + "-2")))
        self.assertAlmostEqual(record["verdict"]["bounds"]["cost_usd"], 2.25 * 1e3, places=6)

    def test_a_single_session_that_fails_writes_no_baseline_and_the_command_starts_no_fanned_run(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        self.scenario(verdicts=ALL_FAIL if "production_files" == "critical_routing" else ALL_DIFFER, fork_tools=["Read", "Bash", "StructuredOutput"])
        status, text, err = self.go()
        self.assertEqual(status, 1, text + err)
        self.assertIn("the single form's session failed", text + err)
        self.assertFalse(os.path.exists(self.baselines))
        self.assertEqual([call for call in self.calls() if MID not in call["args"]], [], "no session of the fanned-out form was started")
        self.assertFalse(os.path.exists(os.path.join(self.work, pfp.RECORD)))

    def test_a_missing_agent_command_line_stops_the_run_with_a_cannot_run_and_writes_no_baseline(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        with mock.patch.dict(os.environ, {ex.AGENT_ENV: os.path.join(self.root, "no-such-agent")}):
            status, text, err = self.go()
        self.assertEqual(status, 2, text + err)
        self.assertIn("CANNOT RUN", err)
        self.assertFalse(os.path.exists(self.baselines))


class TheModule(unittest.TestCase):
    def test_the_command_is_a_thin_use_of_the_shared_harness_and_names_its_own_baseline_file(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES-PROOF.C2: Over the kit's stub, the proof command for the production-files check runs the single form once through the kit and writes it as a baseline file the kit's proof loads, keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash; run again for a key whose baseline is recorded it refuses to run the single form and names the key, and for a key that differs it runs it; a review folder that lies inside the repository is refused naming it. The command's record is written in text and JSON with the same content. Out of scope: any live run and the pooled criterion's arithmetic, which the kit's own tests hold.
        for name in ("run_single", "outcome_of", "single_key", "recorded_under", "baseline_lock", "plan_of", "run_command",
                     "fanned_runs", "numbered"):
            self.assertIs(getattr(pfp, "harness"), harness)
            self.assertFalse(hasattr(pfp, name), f"{name} is the harness's, not copied into the command")
        source = slurp(pfp.__file__)
        for call in ("harness.run_single(", "harness.outcome_of(", "harness.single_key(", "harness.recorded_under(",
                     "harness.baseline_lock(", "harness.fanned_runs(", "harness.numbered("):
            self.assertIn(call, source)
        self.assertIs(pfp.Refused, harness.Refused)
        self.assertEqual(os.path.relpath(pfp.BASELINES, TOOLS), os.path.join("tests", "fixtures", "review_baselines",
                                                                              "production_files_single_runs.json"))
        self.assertEqual(pfp.CALLER, "production_files")


if __name__ == "__main__":
    unittest.main()
