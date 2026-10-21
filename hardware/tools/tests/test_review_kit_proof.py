#!/usr/bin/env python3
"""The review kit's proof harness: the forms as plans, the baselines and their keys, the pooled criterion and its record.

Logic is tested on synthetic runs and a stub; the recorded layout baselines are loaded from the committed data file. No
model, no network and no KiCad are used.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import catalogue, planner, proof, scheduler, telemetry  # noqa: E402
from review_kit import executor as ex  # noqa: E402

BASELINES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "review_baselines", "layout_single_runs.json")
SEEDS = [{"id": f"S{n}", "item": f"item-{n}", "note": f"synthetic seed {n}"} for n in range(1, 8)]
ALL21 = [f"S{n}" for n in range(1, 22)]
KEY = proof.BaselineKey(proof.seed_list_hash(SEEDS), "design-1", "model-1", proof.SINGLE, "prompt-1")


def run(run_id, form=proof.SINGLE, found=7, wall=100.0, cost=1.0, verdicts=None, raised=None, judged=None, unmatched=()):
    """A synthetic run that found the first `found` seeds (or those named), with the given wall time and cost."""
    ids = list(found) if isinstance(found, (list, tuple)) else [s["id"] for s in SEEDS[:found]]
    who = {seed: tuple(raised[seed]) if raised else (proof.SINGLE_LABEL,) for seed in ids}
    return proof.RunOutcome(run_id, form, "tool-" + run_id, "seeded-" + run_id, tuple(ids), tuple(unmatched),
                            dict(verdicts or {}), who,
                            dict(judged) if judged else {s["id"]: (proof.SINGLE_LABEL,) for s in SEEDS},
                            (proof.SessionRecord("s-" + run_id, wall, cost, 10, 20, 30),), wall, cost)


def singles():
    """Three single runs: 5, 6 and 7 seeds found, mean wall 100 s, mean cost 2.0."""
    return [run("a", found=5, wall=80, cost=1.5), run("b", found=6, wall=100, cost=2.0), run("c", found=7, wall=120, cost=2.5)]


def fan(run_id, **kw):
    kw.setdefault("form", proof.FANNED)
    return run(run_id, **kw)


class FormsAsPlans(unittest.TestCase):
    def setUp(self):
        self.h = fx.Harness(self)
        self.catalogue = catalogue.admit(self.h.declaration, self.h.review, results_folder=self.h.out)

    def plan(self, form, **kw):
        return proof.form_plan(form, self.h.declaration, self.catalogue, self.h.spec, bound=4, cli_version="9.9.9",
                               tool_commit="abc1234", **kw)

    # SOL-HW-REVIEW-KIT.C12: the single-reviewer form is a plan with one unit holding every item and no shared context
    def test_single_is_one_group_of_every_item_with_an_empty_shared_context(self):
        formed = self.plan(proof.SINGLE, replicas=3, variants=("full", "hunt"))
        items = [i for unit in self.h.declaration.units.values() for i in unit.items]
        self.assertEqual(1, len(formed.plan.groups))
        group = formed.plan.groups[0]
        self.assertEqual(tuple(self.h.declaration.units), group.units)
        self.assertEqual(items, [i for u in group.units for i in formed.declaration.units[u].items])
        self.assertEqual(("root", "G1.r1.a1"), tuple(n.id for n in formed.plan.nodes))
        self.assertEqual((), group.needs)
        self.assertEqual([], formed.shared.as_dict()["artefacts"])
        self.assertEqual(1, formed.plan.bound)
        self.assertEqual(1, group.replicas)

    # SOL-HW-REVIEW-KIT.C12: the single reviewer under the shared context is the same unit under a shared context
    def test_single_shared_is_the_same_group_under_the_shared_context(self):
        alone, shared = self.plan(proof.SINGLE), self.plan(proof.SINGLE_SHARED)
        self.assertEqual(alone.plan.groups[0].units, shared.plan.groups[0].units)
        self.assertEqual(1, len(shared.plan.groups))
        names = [a["name"] for a in shared.shared.as_dict()["artefacts"]]
        self.assertEqual(self.h.declaration.needed, names)
        self.assertGreater(shared.shared.tokens, alone.shared.tokens)
        self.assertEqual(tuple(sorted(self.h.declaration.needed)), shared.plan.groups[0].needs)
        self.assertNotEqual(alone.plan.root.prefix_sha, shared.plan.root.prefix_sha)

    # SOL-HW-REVIEW-KIT.C12: the fanned-out form is the grouped plan
    def test_fanned_is_the_grouped_plan_with_its_replicas(self):
        formed = self.plan(proof.FANNED, replicas=2)
        self.assertEqual([["u1"], ["u2", "u3"], ["u4"]], [list(g.units) for g in formed.plan.groups])
        self.assertEqual(6, len(formed.plan.lanes))
        self.assertEqual(4, formed.plan.bound)
        self.assertIs(self.h.declaration, formed.declaration)

    def test_unknown_form_is_refused_by_name(self):
        with self.assertRaises(proof.UnknownForm) as caught:
            self.plan("batch")
        self.assertIn("'batch'", str(caught.exception))
        self.assertIn("single-shared", str(caught.exception))

    def test_the_declaration_is_not_changed_by_making_a_single_plan(self):
        before = {u: (unit.needs, unit.couples_with) for u, unit in self.h.declaration.units.items()}
        self.plan(proof.SINGLE)
        self.assertEqual(before, {u: (unit.needs, unit.couples_with) for u, unit in self.h.declaration.units.items()})


class RunsRecordedInOneShape(unittest.TestCase):
    """Each form is run by the same scheduler and recorded in the same shape."""

    SEEDS = [{"id": "S1", "item": "i1"}, {"id": "S2", "item": "j1"}, {"id": "S3", "item": "m1"}]

    def setUp(self):
        self.h = fx.Harness(self)
        self.catalogue = catalogue.admit(self.h.declaration, self.h.review, results_folder=self.h.out)

    @staticmethod
    def match(seed, row):
        return row.get("Item") == seed["item"]

    def play(self, formed, raises):
        """Run a form on the stub. `raises` maps a lane label (`G2.r1`) to the findings rows its replica returns."""
        declaration = formed.declaration

        def reply(call, number):
            if call.label == "root":
                return ex.Reply(text="ack", write=100)
            group = next(g for g in formed.plan.groups if g.id == call.label.split(".")[0])
            lane = ".".join(call.label.split(".")[:2])
            items = [i for u in group.units for i in declaration.units[u].items]
            rows = raises.get(lane, [])
            failing = {row["Item"] for row in rows}
            verdicts = [{"Item": i, "Verdict": "fail" if i in failing else "pass", "Note": ""} for i in items]
            findings = [{"No": n, "Item": row["Item"], "Detail": row["Detail"]} for n, row in enumerate(rows, 1)]
            return ex.Reply(structured={"tables": {"Verdicts": verdicts, "Findings": findings}}, text="done")

        executor = ex.StubExecutor(replies=reply, clock=self.h.clock, policy=self.h.policy)
        runner = scheduler.Scheduler(executor, self.h.clock, scheduler.SerialConcurrency(), 1)
        return proof.run_form(runner, formed, self.h.spec)

    def figures(self, session, wall, cost, parent=None):
        return telemetry.SessionFigures(session, parent, cost, 1000, wall, 1, 1,
                                        {"cache_read": 100, "cache_write": 50, "fresh": 1, "generated": 7}, 40)

    def formed(self, form, **kw):
        return proof.form_plan(form, self.h.declaration, self.catalogue, self.h.spec, bound=4, cli_version="9.9.9",
                               tool_commit="abc1234", **kw)

    # SOL-HW-REVIEW-KIT.C12: each run by the same scheduler and recorded in the same shape
    def test_a_fanned_run_records_seeds_replicas_unmatched_findings_and_sessions(self):
        formed = self.formed(proof.FANNED, replicas=2)
        result = self.play(formed, {"G1.r1": [{"Item": "i1", "Detail": "seeded"}],
                                    "G1.r2": [{"Item": "i2", "Detail": "other"}],
                                    "G3.r2": [{"Item": "m1", "Detail": "seeded"}]})
        figures = [self.figures("root", 5, 0.5), self.figures("a", 20, 0.25, "root"), self.figures("b", 30, 0.25, "root")]
        outcome = proof.outcome_from_run("r1", formed, result, figures, self.SEEDS, self.match, seeded_commit="seeded-1")
        self.assertEqual(("S1", "S3"), outcome.seeds_found)
        self.assertEqual({"S1": ("G1.r1",), "S3": ("G3.r2",)}, dict(outcome.raised_by))
        self.assertEqual({"S1": ("G1.r1", "G1.r2"), "S2": ("G2.r1", "G2.r2"), "S3": ("G3.r1", "G3.r2")},
                         dict(outcome.judged_by))
        self.assertEqual(("G1.r2: 1 | i2 | other",), outcome.unmatched)
        self.assertEqual("fail", outcome.verdicts["i1"])
        self.assertEqual("pass", outcome.verdicts["k1"])
        self.assertEqual(35.0, outcome.wall_s)
        self.assertEqual(1.0, outcome.cost_usd)
        self.assertEqual(("root", "a", "b"), tuple(s.session for s in outcome.sessions))
        self.assertEqual((100, 50, 7, 40), (outcome.sessions[0].tokens_read, outcome.sessions[0].tokens_written,
                                            outcome.sessions[0].tokens_generated, outcome.sessions[0].first_call_read))
        self.assertEqual("seeded-1", outcome.seeded_commit)
        self.assertEqual("abc1234", outcome.tool_commit)

    def test_a_single_run_is_recorded_in_the_same_shape_with_one_replica(self):
        formed = self.formed(proof.SINGLE)
        result = self.play(formed, {"G1.r1": [{"Item": "j1", "Detail": "seeded"}]})
        outcome = proof.outcome_from_run("one", formed, result, [self.figures("only", 60, 0.75)], self.SEEDS, self.match,
                                         seeded_commit="seeded-1")
        self.assertEqual(("S2",), outcome.seeds_found)
        self.assertEqual({"S1": ("G1.r1",), "S2": ("G1.r1",), "S3": ("G1.r1",)}, dict(outcome.judged_by))
        self.assertEqual(proof.SINGLE, outcome.form)
        self.assertEqual(set(outcome.as_dict()), set(self.fanned_shape()))

    def fanned_shape(self):
        formed = self.formed(proof.FANNED)
        result = self.play(formed, {})
        return proof.outcome_from_run("x", formed, result, [self.figures("only", 1, 0.1)], self.SEEDS, self.match,
                                      seeded_commit="s").as_dict()

    def test_the_match_function_is_the_callers(self):
        formed = self.formed(proof.SINGLE)
        result = self.play(formed, {"G1.r1": [{"Item": "i1", "Detail": "mentions m1 only in words"}]})
        by_detail = lambda seed, row: seed["item"] in row["Detail"]  # noqa: E731
        outcome = proof.outcome_from_run("o", formed, result, [self.figures("only", 1, 0.1)], self.SEEDS, by_detail,
                                         seeded_commit="s")
        self.assertEqual(("S3",), outcome.seeds_found)
        self.assertEqual((), outcome.unmatched)

    def test_a_declaration_without_a_findings_table_is_refused(self):
        formed = self.formed(proof.SINGLE)
        bare = replace(formed, declaration=replace(formed.declaration, shape=replace(formed.declaration.shape, findings=None)))
        result = self.play(formed, {})
        with self.assertRaises(proof.ProofError):
            proof.outcome_from_run("o", bare, result, [self.figures("only", 1, 0.1)], self.SEEDS, self.match, seeded_commit="s")


class Keys(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C12: baselines keyed by the hash of the seed list, the design commit, the model, the form and the prompt hash
    def test_each_part_of_the_key_changes_it(self):
        base = KEY.id
        changed = [replace(KEY, seeds=proof.seed_list_hash(SEEDS[:-1])), replace(KEY, design="design-2"),
                   replace(KEY, model="model-2"), replace(KEY, form=proof.SINGLE_SHARED), replace(KEY, prompt="prompt-2")]
        self.assertEqual(5, len({k.id for k in changed} | {base}) - 1)
        for other in changed:
            self.assertNotEqual(base, other.id)

    def test_the_seed_list_hash_follows_content_and_not_key_order(self):
        reordered = [dict(reversed(list(s.items()))) for s in SEEDS]
        self.assertEqual(proof.seed_list_hash(SEEDS), proof.seed_list_hash(reordered))
        edited = [dict(s) for s in SEEDS]
        edited[3]["note"] = "changed"
        self.assertNotEqual(proof.seed_list_hash(SEEDS), proof.seed_list_hash(edited))
        self.assertNotEqual(proof.seed_list_hash(SEEDS), proof.seed_list_hash(list(reversed(SEEDS))))

    def test_a_key_without_a_part_or_with_an_unknown_form_is_refused(self):
        with self.assertRaises(proof.ProofError):
            proof.BaselineKey("", "d", "m", proof.SINGLE, "p")
        with self.assertRaises(proof.UnknownForm):
            proof.BaselineKey("s", "d", "m", "batch", "p")

    # SOL-HW-REVIEW-KIT.C12: the seeded and tool commits being recorded with each run and not matched
    def test_runs_at_different_commits_share_a_key(self):
        loaded = proof.BaselineStore()
        loaded.add(KEY, run("a"))
        loaded.add(KEY, run("b"))
        self.assertEqual(["tool-a", "tool-b"], [r.tool_commit for r in loaded.recorded(KEY)])
        self.assertEqual(["seeded-a", "seeded-b"], [r.seeded_commit for r in loaded.recorded(KEY)])
        self.assertNotIn("tool_commit", KEY.as_dict())
        self.assertNotIn("seeded_commit", KEY.as_dict())

    def test_a_run_of_another_form_or_a_repeated_run_is_not_added(self):
        loaded = proof.BaselineStore()
        loaded.add(KEY, run("a"))
        with self.assertRaises(proof.ProofError):
            loaded.add(KEY, run("a"))
        with self.assertRaises(proof.ProofError):
            loaded.add(KEY, fan("z"))


class Refusal(unittest.TestCase):
    def setUp(self):
        self.store = proof.BaselineStore()
        for name in "abc":
            self.store.add(KEY, run(name))

    # SOL-HW-REVIEW-KIT.C12: refuses to run a form whose baseline for the key is recorded and names the key
    def test_a_recorded_form_is_refused_and_the_key_is_named(self):
        ran = []
        with self.assertRaises(proof.BaselineRecorded) as caught:
            self.store.run_unless_recorded(KEY, lambda: ran.append(1))
        self.assertEqual([], ran)
        self.assertEqual(KEY.id, caught.exception.key)
        self.assertIn(KEY.id, str(caught.exception))
        self.assertIn("3 recorded runs", str(caught.exception))
        self.assertEqual(3, len(self.store.recorded(KEY)))

    # SOL-HW-REVIEW-KIT.C12: runs a form whose key differs
    def test_a_form_whose_key_differs_is_run_and_recorded(self):
        for other in (replace(KEY, model="model-2"), replace(KEY, form=proof.SINGLE_SHARED),
                      replace(KEY, seeds=proof.seed_list_hash(SEEDS[:3])), replace(KEY, prompt="prompt-2"),
                      replace(KEY, design="design-2")):
            made = run("new-" + other.id[:6], form=other.form)
            self.assertIs(made, self.store.run_unless_recorded(other, lambda made=made: made))
            self.assertEqual([made], self.store.recorded(other))
        self.assertEqual(3, len(self.store.recorded(KEY)))

    def test_the_fanned_form_is_never_a_baseline_and_runs_again(self):
        key = replace(KEY, form=proof.FANNED)
        for number in range(2):
            self.store.run_unless_recorded(key, lambda number=number: fan(f"f{number}"))
        self.assertEqual(2, len(self.store.recorded(key)))


class Loading(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C12: loads the five recorded layout runs as baselines
    def test_five_layout_runs_are_loaded_under_one_key(self):
        loaded = proof.load_baselines(BASELINES)
        self.assertEqual(1, len(loaded.runs))
        key = next(iter(loaded.keys.values()))
        recorded = loaded.recorded(key)
        self.assertEqual(5, len(recorded))
        self.assertEqual(proof.SINGLE, key.form)
        self.assertEqual("claude-sonnet-5-5", key.model)
        self.assertEqual([21, 21, 19, 20, 21], [r.found for r in recorded])
        self.assertEqual(5, len({r.tool_commit for r in recorded}))
        self.assertEqual(5, len({r.seeded_commit for r in recorded}))
        for r in recorded:
            self.assertEqual(proof.SINGLE, r.form)

    def test_recorded_figures(self):
        recorded = proof.load_baselines(BASELINES).recorded(next(iter(proof.load_baselines(BASELINES).keys.values())))
        walls, costs = [r.wall_s for r in recorded], [r.cost_usd for r in recorded]
        self.assertEqual((652.932, 1061.89), (min(walls), max(walls)))
        self.assertAlmostEqual(862.3, proof.mean(walls), delta=0.5)
        self.assertAlmostEqual(2.84, proof.mean(costs), delta=0.005)
        self.assertAlmostEqual(3.45, max(costs), delta=0.005)
        self.assertEqual(sorted(("S1", "S11")), sorted(set(f"S{n}" for n in range(1, 22)) - set(recorded[2].seeds_found)))
        self.assertEqual(["S1"], sorted(set(f"S{n}" for n in range(1, 22)) - set(recorded[3].seeds_found)))
        for r in recorded:
            self.assertEqual(1, len(r.sessions))
            self.assertEqual(r.wall_s, r.sessions[0].wall_s)
            self.assertGreater(r.sessions[0].tokens_read, r.sessions[0].tokens_written)
            self.assertIn("first_call_read", r.not_recorded)
            self.assertIsNone(r.sessions[0].first_call_read)
            self.assertGreater(len(r.verdicts), 60)
            self.assertEqual(set(r.seeds_found), set(r.raised_by))

    def test_the_recorded_key_refuses_the_single_form_and_lets_another_run(self):
        loaded = proof.load_baselines(BASELINES)
        key = next(iter(loaded.keys.values()))
        with self.assertRaises(proof.BaselineRecorded) as caught:
            loaded.refuse_if_recorded(key)
        self.assertIn(key.id, str(caught.exception))
        loaded.refuse_if_recorded(replace(key, form=proof.SINGLE_SHARED))
        loaded.refuse_if_recorded(replace(key, model="another-model"))

    def test_the_file_is_scrubbed_of_machine_paths_and_stays_a_reduction(self):
        with open(BASELINES, encoding="utf-8") as handle:
            text = handle.read()
        for needle in ("/Users", "/private", "/tmp", "/var/", "data:image", "base64"):
            self.assertNotIn(needle, text)
        raw = json.loads(text)
        self.assertIn("first-call cache read", raw["source"])
        self.assertIn("seed list", raw["source"])
        self.assertNotIn("description", text)

    def test_every_malformed_file_is_refused_naming_the_cause(self):
        with open(BASELINES, encoding="utf-8") as handle:
            good = json.load(handle)

        def broken(change):
            raw = json.loads(json.dumps(good))
            change(raw)
            return raw

        cases = {
            "version": lambda r: r.update(version=9),
            "baselines": lambda r: r.update(baselines=[]),
            "runs": lambda r: r["baselines"][0].update(runs="none"),
            "key": lambda r: r["baselines"][0].pop("key"),
            "model": lambda r: r["baselines"][0]["key"].pop("model"),
            "form": lambda r: r["baselines"][0]["runs"][0].update(form="batch"),
            "wall": lambda r: r["baselines"][0]["runs"][0].update(wall_s=-1),
            "cost": lambda r: r["baselines"][0]["runs"][0].update(cost_usd="free"),
            "twice": lambda r: r["baselines"][0]["runs"][0].update(seeds_found=["S1", "S1"]),
            "sessions": lambda r: r["baselines"][0]["runs"][0].pop("sessions"),
            "dup": lambda r: r["baselines"][0]["runs"].append(r["baselines"][0]["runs"][0]),
            "shape": lambda r: r["baselines"][0]["runs"].append(7),
        }
        with tempfile.TemporaryDirectory() as folder:
            for name, change in cases.items():
                path = os.path.join(folder, f"{name}.json")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(broken(change), handle)
                with self.assertRaises(proof.BaselineFileError, msg=name) as caught:
                    proof.load_baselines(path)
                self.assertIn(path, str(caught.exception), name)
            with open(os.path.join(folder, "text.json"), "w", encoding="utf-8") as handle:
                handle.write("{not json")
            with self.assertRaises(proof.BaselineFileError):
                proof.load_baselines(os.path.join(folder, "text.json"))
            with self.assertRaises(proof.BaselineFileError):
                proof.load_baselines(os.path.join(folder, "absent.json"))

    def test_a_run_survives_its_dictionary_form(self):
        made = run("a", found=[ "S2", "S5"], wall=12.5, cost=0.25, verdicts={"x": "pass"}, unmatched=("odd",))
        self.assertEqual(made, proof.RunOutcome.from_dict(json.loads(json.dumps(made.as_dict()))))


class Pooled(unittest.TestCase):
    """Singles: seeds 5, 6, 7 (floor 5), wall mean 100 s (bound 50 s), cost mean 2.0 (bound 2.5 at a multiple of 1.25)."""

    def accept(self, fanned, multiple=1.25):
        return proof.accept(singles(), fanned, multiple)

    # SOL-HW-REVIEW-KIT.C12: the criterion passes when the seeds found in each fanned-out run are no fewer than the fewest any single run found, ...
    def test_a_run_inside_every_bound_passes_with_no_second_run(self):
        verdict = self.accept([fan("f", found=7, wall=30, cost=2.0)])
        self.assertTrue(verdict.accepted)
        self.assertEqual("pass", verdict.status)
        self.assertEqual([], verdict.failed)
        self.assertFalse(verdict.second_run_required)
        self.assertEqual({"seeds_floor": 5, "wall_s": 50.0, "cost_usd": 2.5}, dict(verdict.bounds))

    def test_fewer_seeds_than_the_fewest_single_fails_naming_the_clause(self):
        spread = [run("a", found=["S1", "S2", "S3", "S4", "S5"], wall=100, cost=2.0),
                  run("b", found=["S3", "S4", "S5", "S6", "S7"], wall=100, cost=2.0)]
        verdict = proof.accept(spread, [fan("f", found=["S3", "S4", "S5", "S6"], wall=30, cost=2.0)], 1.25)
        self.assertEqual([proof.SEEDS_FLOOR], verdict.failed)
        self.assertEqual("fail", verdict.status)
        self.assertIn("f found 4", verdict.clauses[0].detail)
        self.assertIn("is 5", verdict.clauses[0].detail)

    def test_every_fanned_run_must_meet_the_floor(self):
        verdict = self.accept([fan("f1", found=7, wall=30, cost=2.0), fan("f2", found=4, wall=30, cost=2.0)])
        self.assertEqual([proof.SEEDS_FLOOR], verdict.failed)
        self.assertIn("f2 found 4", verdict.clauses[0].detail)
        self.assertNotIn("f1 found", verdict.clauses[0].detail)

    # SOL-HW-REVIEW-KIT.C12: no seed every single run found is missed by every fanned-out run
    def test_a_seed_every_single_found_and_every_fanned_run_missed_fails_naming_the_seed(self):
        verdict = self.accept([fan("f", found=["S2", "S3", "S4", "S6", "S7"], wall=30, cost=2.0)])
        self.assertEqual([proof.SEED_EVERY_SINGLE_FOUND], verdict.failed)
        self.assertIn("['S1', 'S5']", verdict.clauses[1].detail.replace('"', "'"))

    def test_a_seed_found_by_one_fanned_run_is_not_missed_by_every_fanned_run(self):
        both = [fan("f1", found=["S1", "S2", "S3", "S4", "S5"], wall=30, cost=2.0),
                fan("f2", found=["S2", "S3", "S4", "S5", "S6"], wall=30, cost=2.0)]
        self.assertTrue(self.accept(both).accepted)

    def test_a_seed_some_single_run_missed_may_be_missed_by_the_fanned_run(self):
        # single a missed S6 and S7, so missing them in the fanned run breaks no clause
        verdict = self.accept([fan("f", found=["S1", "S2", "S3", "S4", "S5"], wall=30, cost=2.0)])
        self.assertEqual([], verdict.failed)

    # SOL-HW-REVIEW-KIT.C12: the fanned-out wall time is at most half the single mean
    def test_a_wall_time_over_half_the_single_mean_fails_and_exactly_half_passes(self):
        slow = self.accept([fan("f", found=7, wall=50.01, cost=2.0)])
        self.assertEqual([proof.WALL_TIME], slow.failed)
        self.assertIn("f took 50.01 s", slow.clauses[2].detail)
        self.assertIn("at most 50 s", slow.clauses[2].detail)
        self.assertEqual([], self.accept([fan("f", found=7, wall=50.0, cost=2.0)]).failed)

    # SOL-HW-REVIEW-KIT.C12: the cost is at most the stated multiple of the single mean cost, the multiple a parameter
    def test_cost_is_judged_against_the_stated_multiple(self):
        dear = self.accept([fan("f", found=7, wall=30, cost=2.6)])
        self.assertEqual([proof.COST], dear.failed)
        self.assertIn("1.25 times", dear.clauses[3].detail)
        self.assertEqual([], self.accept([fan("f", found=7, wall=30, cost=2.5)]).failed)
        self.assertEqual([], self.accept([fan("f", found=7, wall=30, cost=2.6)], multiple=1.5).failed)
        self.assertEqual([proof.COST], self.accept([fan("f", found=7, wall=30, cost=2.1)], multiple=1.0).failed)

    def test_every_clause_that_fails_is_named(self):
        verdict = self.accept([fan("f", found=2, wall=500, cost=9)])
        self.assertEqual([proof.SEEDS_FLOOR, proof.SEED_EVERY_SINGLE_FOUND, proof.WALL_TIME, proof.COST], verdict.failed)
        self.assertFalse(verdict.second_run_required)

    # SOL-HW-REVIEW-KIT.C12: a second fanned-out run is required only when the first is within ten per cent of a bound
    def test_a_first_run_within_ten_per_cent_of_a_bound_requires_a_second(self):
        for near in (dict(found=5, wall=30, cost=2.0), dict(found=7, wall=45.0, cost=2.0), dict(found=7, wall=30, cost=2.25)):
            verdict = self.accept([fan("f", **near)])
            self.assertTrue(verdict.second_run_required, near)
            self.assertFalse(verdict.accepted, near)
            self.assertEqual("second-run-required", verdict.status)
            self.assertEqual([], verdict.failed, near)

    def test_a_first_run_clear_of_every_bound_requires_none(self):
        verdict = self.accept([fan("f", found=7, wall=44.99, cost=2.249)])
        self.assertFalse(verdict.second_run_required)
        self.assertTrue(verdict.accepted)

    def test_with_a_second_run_recorded_the_pooled_runs_decide(self):
        near = dict(found=5, wall=45, cost=2.25)
        verdict = self.accept([fan("f1", **near), fan("f2", **near)])
        self.assertFalse(verdict.second_run_required)
        self.assertTrue(verdict.accepted)
        worse = self.accept([fan("f1", **near), fan("f2", found=7, wall=60, cost=2.0)])
        self.assertEqual([proof.WALL_TIME], worse.failed)
        self.assertFalse(worse.accepted)

    def test_a_failing_first_run_fails_and_does_not_ask_for_a_second(self):
        verdict = self.accept([fan("f", found=7, wall=46, cost=2.6)])
        self.assertEqual("fail", verdict.status)
        self.assertFalse(verdict.second_run_required)

    def test_the_bounds_use_the_mean_of_all_the_single_runs(self):
        one = proof.accept([run("a", found=7, wall=200, cost=4.0)], [fan("f", found=7, wall=99, cost=4.0)], 1.0)
        self.assertEqual([], one.failed)
        self.assertEqual({"seeds_floor": 7, "wall_s": 100.0, "cost_usd": 4.0}, dict(one.bounds))

    def test_a_proof_needs_single_runs_and_a_fanned_run_and_a_sound_multiple(self):
        with self.assertRaises(proof.NotEnoughRuns):
            proof.accept([], [fan("f")], 1.25)
        with self.assertRaises(proof.NotEnoughRuns):
            proof.accept(singles(), [], 1.25)
        for bad in (0, -1, True, "1.25", None):
            with self.assertRaises(proof.ProofError, msg=bad):
                proof.accept(singles(), [fan("f")], bad)

    def test_a_run_without_a_wall_time_cannot_be_judged(self):
        broken = replace(fan("f"), wall_s=None)
        with self.assertRaises(proof.ProofError):
            proof.accept(singles(), [broken], 1.25)

    def test_the_recorded_layout_runs_set_the_bounds(self):
        loaded = proof.load_baselines(BASELINES)
        recorded = loaded.recorded(next(iter(loaded.keys.values())))
        every = [s for s in (f"S{n}" for n in range(1, 22)) if s not in ("S1", "S11")]
        verdict = proof.accept(recorded, [fan("f", found=every, wall=300, cost=3.5)], 1.25)
        self.assertEqual(19, verdict.bounds["seeds_floor"])
        self.assertAlmostEqual(431.15, verdict.bounds["wall_s"], delta=0.05)
        self.assertAlmostEqual(3.55, verdict.bounds["cost_usd"], delta=0.01)
        self.assertEqual("second-run-required", verdict.status)
        self.assertEqual([proof.WALL_TIME], proof.accept(recorded, [fan("f", found=ALL21, wall=440, cost=3.0)], 1.25).failed)
        # the seeds all five found are every seed but S1 and S11: missing one of those is the clause, missing S1 is not
        lost = every[1:]
        self.assertIn(proof.SEED_EVERY_SINGLE_FOUND,
                      proof.accept(recorded, [fan("f", found=lost, wall=100, cost=1.0)], 1.25).failed)
        self.assertNotIn(proof.SEED_EVERY_SINGLE_FOUND,
                         proof.accept(recorded, [fan("f", found=every, wall=100, cost=1.0)], 1.25).failed)


class Replicas(unittest.TestCase):
    def outcome(self, raised, judged):
        return proof.RunOutcome(
            "f", proof.FANNED, "t", "s", tuple(raised), (), {}, {k: tuple(v) for k, v in raised.items()},
            {k: tuple(v) for k, v in judged.items()}, (), 1.0, 1.0)

    # SOL-HW-REVIEW-KIT.C12: from the replicas that raised each seed, the rate at which one replica misses a seed
    def test_miss_rate_counts_replicas_that_judged_a_seed_and_did_not_raise_it(self):
        out = self.outcome({"S1": ["a", "b"], "S2": ["a"], "S3": ["c"]},
                           {"S1": ["a", "b"], "S2": ["a", "b"], "S3": ["c", "d", "e"], "S4": ["f", "g"]})
        stats = proof.replica_statistics([out])
        self.assertEqual(9, stats["trials"])
        self.assertEqual(1 + 2 + 2, stats["misses"])
        self.assertAlmostEqual(5 / 9, stats["miss_rate"], places=4)

    def test_miss_rate_pools_the_runs(self):
        a = self.outcome({"S1": ["a"]}, {"S1": ["a", "b"]})
        b = self.outcome({"S1": ["a", "b"]}, {"S1": ["a", "b"]})
        self.assertEqual((4, 1, 0.25), tuple(proof.replica_statistics([a, b])[k] for k in ("trials", "misses", "miss_rate")))

    # SOL-HW-REVIEW-KIT.C12: and the correlation between replicas
    def test_replicas_that_always_miss_together_correlate_fully(self):
        judged = {f"S{n}": ["a", "b"] for n in range(1, 7)}
        raised = {"S1": ["a", "b"], "S2": ["a", "b"], "S3": ["a", "b"]}
        stats = proof.replica_statistics([self.outcome(raised, judged)])
        self.assertEqual(1.0, stats["correlation"])
        self.assertEqual(6, stats["replica_pairs"])

    def test_replicas_that_miss_apart_correlate_negatively(self):
        judged = {f"S{n}": ["a", "b"] for n in range(1, 5)}
        raised = {"S1": ["a"], "S2": ["b"], "S3": ["a"], "S4": ["b"]}
        self.assertEqual(-1.0, proof.replica_statistics([self.outcome(raised, judged)])["correlation"])

    def test_independent_misses_give_zero(self):
        judged = {f"S{n}": ["a", "b"] for n in range(1, 5)}
        raised = {"S1": ["a", "b"], "S2": ["a"], "S3": ["b"], "S4": []}
        self.assertEqual(0.0, proof.replica_statistics([self.outcome(raised, judged)])["correlation"])

    def test_correlation_is_none_without_variation_or_pairs(self):
        everything = self.outcome({"S1": ["a", "b"], "S2": ["a", "b"]}, {"S1": ["a", "b"], "S2": ["a", "b"]})
        self.assertIsNone(proof.replica_statistics([everything])["correlation"])
        alone = self.outcome({"S1": ["a"]}, {"S1": ["a"], "S2": ["a"]})
        stats = proof.replica_statistics([alone])
        self.assertIsNone(stats["correlation"])
        self.assertEqual(0, stats["replica_pairs"])
        self.assertEqual(0.5, stats["miss_rate"])
        empty = proof.replica_statistics([])
        self.assertEqual((0, None, None), (empty["trials"], empty["miss_rate"], empty["correlation"]))


class Record(unittest.TestCase):
    def build(self, **kw):
        s = singles()
        s[0] = replace(s[0], verdicts={"X-1": "fail", "X-2": "pass", "X-3": "pass"}, unmatched=("odd one",))
        s[1] = replace(s[1], verdicts={"X-1": "fail", "X-2": "fail", "X-3": "pass"})
        s[2] = replace(s[2], verdicts={"X-1": "fail", "X-2": "pass", "X-3": "pass"})
        f = replace(fan("f1", found=["S1", "S2", "S3", "S4", "S5", "S6"], wall=30, cost=2.0,
                        verdicts={"X-1": "fail", "X-2": "pass", "X-3": "fail", "X-4": "pass"},
                        raised={"S1": ["G1.r1", "G1.r2"], "S2": ["G1.r1"], "S3": ["G2.r2"], "S4": ["G2.r1"], "S5": ["G1.r2"],
                                "S6": ["G2.r1", "G2.r2"]},
                        judged={"S1": ("G1.r1", "G1.r2"), "S2": ("G1.r1", "G1.r2"), "S3": ("G2.r1", "G2.r2"),
                                "S4": ("G2.r1", "G2.r2"), "S5": ("G1.r1", "G1.r2"), "S6": ("G2.r1", "G2.r2"),
                                "S7": ("G2.r1", "G2.r2")},
                        unmatched=("G1.r1: a, b", "G2.r2: c")), not_recorded=("first_call_read",))
        return s, f, proof.build_record(SEEDS, s, [f], 1.25, [KEY], **kw)

    # SOL-HW-REVIEW-KIT.C12: the record gives each run's seeds found, the findings matching no seed and each session's figures
    def test_the_record_gives_each_runs_figures(self):
        s, f, record = self.build()
        self.assertEqual(["a", "b", "c"], [r["id"] for r in record["single_runs"]])
        self.assertEqual([5, 6, 7], [r["seeds_found_count"] for r in record["single_runs"]])
        fanned = record["fanned_runs"][0]
        self.assertEqual(["S1", "S2", "S3", "S4", "S5", "S6"], fanned["seeds_found"])
        self.assertEqual(["G1.r1: a, b", "G2.r2: c"], fanned["unmatched"])
        self.assertEqual(["odd one"], record["single_runs"][0]["unmatched"])
        self.assertEqual({"session": "s-f1", "wall_s": 30, "cost_usd": 2.0, "tokens_read": 10, "tokens_written": 20,
                          "tokens_generated": 30, "first_call_read": None}, fanned["sessions"][0])
        self.assertEqual({"wall_s": 100.0, "cost_usd": 2.0}, record["single_means"])
        self.assertEqual("pass", record["verdict"]["status"])
        self.assertEqual(KEY.id, record["keys"][0]["id"])
        self.assertEqual(proof.seed_list_hash(SEEDS), record["seed_list_sha256"])

    # SOL-HW-REVIEW-KIT.C12: for each seed the replicas that raised it
    def test_the_record_gives_each_seed_its_replicas(self):
        _, _, record = self.build()
        self.assertEqual(["G1.r1", "G1.r2"], record["seed_replicas"]["S1"]["f1"])
        self.assertEqual(["G2.r2"], record["seed_replicas"]["S3"]["f1"])
        self.assertEqual([], record["seed_replicas"]["S7"]["f1"])
        self.assertEqual({seed["id"] for seed in SEEDS}, set(record["seed_replicas"]))

    # SOL-HW-REVIEW-KIT.C12: from which the miss rate and the correlation are reported
    def test_the_record_reports_the_miss_rate_and_the_correlation(self):
        _, f, record = self.build()
        self.assertEqual(proof.replica_statistics([f]), record["replicas"])
        self.assertEqual(14, record["replicas"]["trials"])
        self.assertEqual(6, record["replicas"]["misses"])

    # SOL-HW-REVIEW-KIT.C12: the verdict differences with an explanation
    def test_verdict_differences_carry_an_explanation_field(self):
        _, _, record = self.build(explanations={("f1", "X-3"): "the run read the rule strictly"})
        found = {d["item"]: d for d in record["verdict_differences"]["f1"]}
        self.assertEqual({"X-3", "X-4"}, set(found))
        self.assertEqual("the run read the rule strictly", found["X-3"]["explanation"])
        self.assertEqual("", found["X-4"]["explanation"])
        self.assertEqual({"fanned": "fail", "single": "pass", "singles": {"a": "pass", "b": "pass", "c": "pass"}},
                         {k: found["X-3"][k] for k in ("fanned", "single", "singles")})
        self.assertIsNone(found["X-4"]["single"])
        self.assertNotIn("X-2", found)

    def test_an_item_the_fanned_run_did_not_judge_is_a_difference(self):
        s = [replace(r, verdicts={"X-1": "fail"}) for r in singles()]
        f = fan("f", found=7, wall=30, cost=2.0, verdicts={})
        record = proof.build_record(SEEDS, s, [f], 1.25)
        self.assertEqual([("X-1", None, "fail")], [(d["item"], d["fanned"], d["single"])
                                                      for d in record["verdict_differences"]["f"]])

    def test_the_single_runs_most_common_verdict_is_the_reference(self):
        s = singles()
        for r, v in zip(range(3), ("pass", "fail", "fail")):
            s[r] = replace(s[r], verdicts={"X": v})
        f = fan("f", verdicts={"X": "fail"}, wall=30, cost=2.0)
        self.assertEqual([], proof.build_record(SEEDS, s, [f], 1.25)["verdict_differences"]["f"])

    # SOL-HW-REVIEW-KIT.C12: the failure names the clause, in the JSON record and in text
    def test_the_record_and_its_text_name_a_failed_clause(self):
        s = singles()
        record = proof.build_record(SEEDS, s, [fan("f", found=7, wall=70, cost=2.0)], 1.25)
        self.assertEqual("fail", record["verdict"]["status"])
        self.assertEqual([proof.WALL_TIME], record["verdict"]["failed_clauses"])
        lines = proof.record_lines(record)
        self.assertTrue(lines[0].startswith("PROOF fail"))
        self.assertTrue(any(line.startswith("FAIL wall-time") for line in lines))
        self.assertTrue(any(line.startswith("ok   cost") for line in lines))

    def test_the_text_gives_each_runs_figures_and_the_second_run_notice(self):
        s = singles()
        record = proof.build_record(SEEDS, s, [fan("f", found=7, wall=46, cost=2.0, unmatched=("x",))], 1.25)
        lines = proof.record_lines(record)
        self.assertTrue(lines[0].startswith("PROOF second-run-required"))
        self.assertIn("a second fanned-out run is required: the first is within ten per cent of a bound", lines)
        self.assertIn("fanned f: seeds 7 of 7, 46 s, 2 USD, 1 findings matching no seed, 1 sessions", lines)
        self.assertIn("single a: seeds 5 of 7, 80 s, 1.5 USD, 0 findings matching no seed, 1 sessions", lines)
        self.assertTrue(any(line.startswith("replicas: ") for line in lines))

    def test_the_record_is_plain_json_and_is_written_whole(self):
        _, _, record = self.build()
        again = json.loads(json.dumps(record))
        self.assertEqual(record, again)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "out", "proof.json")
            proof.write_record(path, record)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(record, json.load(handle))
            self.assertEqual(["proof.json"], os.listdir(os.path.dirname(path)))

    def test_a_record_over_the_loaded_layout_baselines_is_built(self):
        loaded = proof.load_baselines(BASELINES)
        key = next(iter(loaded.keys.values()))
        recorded = loaded.recorded(key)
        seeds = [{"id": f"S{n}", "item": f"item-{n}"} for n in range(1, 22)]
        record = proof.build_record(seeds, recorded, [fan("f", found=ALL21, wall=300, cost=3.0)], 1.25, [key])
        self.assertEqual("pass", record["verdict"]["status"])
        self.assertEqual(5, len(record["single_runs"]))
        self.assertEqual(key.id, record["keys"][0]["id"])
        self.assertEqual(["S1", "S11"], sorted(set(f"S{n}" for n in range(1, 22)) - set(record["single_runs"][2]["seeds_found"])))
        buffer = io.StringIO()
        json.dump(record, buffer)
        self.assertNotIn("/Users", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
