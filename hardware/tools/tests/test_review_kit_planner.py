#!/usr/bin/env python3
"""The review kit's planner and cost model: grouping, packing, the flat plan, its record, and the refit of prices and rates.

Synthetic declarations and review folders; no session is started.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import catalogue, costmodel as cm, decl, ensemble, messages, planner  # noqa: E402


def plain_units(outputs, **extra):
    """A declaration of uncoupled units with the given expected outputs."""
    raw = fx.declaration_dict()
    raw["units"] = {name: {"items": [f"{name}-item"], "template": "t", "needs": ["guide.md"], "expected_output_tokens": out,
                           "values": {"area": name}} for name, out in outputs.items()}
    raw.update(extra)
    return raw


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.review = fx.review_folder(os.path.join(self.tmp.name, "review"))

    def plan(self, raw=None, **kwargs):
        declaration = decl.parse(json.dumps(raw or fx.declaration_dict()), "caller.json")
        found = catalogue.admit(declaration, self.review)
        shared = messages.shared_context(found)
        spec = messages.make_spec(declaration, ("Read",), "/work", "claude-sonnet-5-5")
        kwargs.setdefault("bound", 4)
        kwargs.setdefault("cli_version", "9.9.9")
        kwargs.setdefault("tool_commit", "abc1234")
        return declaration, found, shared, planner.make_plan(declaration, found, shared, spec, **kwargs)


class GroupingTests(Case):
    def test_coupled_units_are_in_one_group_in_either_direction(self):
        # SOL-HW-REVIEW-KIT.C6: units a caller declares as coupled are in one group
        declaration, _, _, plan = self.plan()
        self.assertIn(("u2", "u3"), [g.units for g in plan.groups])
        raw = plain_units({"a": 100, "b": 100, "c": 100, "d": 100})
        raw["units"]["c"]["couples_with"] = ["a"]
        raw["units"]["d"]["couples_with"] = ["c"]
        _, _, _, chained = self.plan(raw)
        coupled = [g for g in chained.groups if "a" in g.units][0]
        self.assertEqual(set(coupled.units), {"a", "c", "d"})

    def test_units_are_packed_so_no_group_exceeds_the_largest_unit(self):
        # SOL-HW-REVIEW-KIT.C6: units are packed so that no group's expected output exceeds the largest single unit's
        raw = plain_units({"a": 400, "b": 300, "c": 200, "d": 100, "e": 100})
        _, _, _, plan = self.plan(raw)
        self.assertTrue(all(g.expected_output_tokens <= 400 for g in plan.groups))
        self.assertEqual(sorted(g.units for g in plan.groups), [("a",), ("b", "d"), ("c", "e")])
        self.assertEqual(sorted(u for g in plan.groups for u in g.units), ["a", "b", "c", "d", "e"])
        self.assertLess(len(plan.groups), 5)

    def test_a_coupled_set_larger_than_the_largest_unit_stays_whole_and_alone(self):
        # SOL-HW-REVIEW-KIT.C6: units a caller declares as coupled are in one group
        _, _, _, plan = self.plan()
        group = [g for g in plan.groups if "u2" in g.units][0]
        self.assertEqual((group.units, group.expected_output_tokens), (("u2", "u3"), 500))
        self.assertGreater(group.expected_output_tokens, 400)
        self.assertEqual([g.units for g in plan.groups], [("u1",), ("u2", "u3"), ("u4",)])

    def test_group_needs_are_the_union_of_its_units(self):
        # SOL-HW-REVIEW-KIT.C6: units are packed into groups
        _, _, _, plan = self.plan()
        self.assertEqual(plan.group_of("u3").needs, ("facts.txt", "guide.md", "view_b.png"))

    def test_the_same_declaration_gives_the_same_plan(self):
        # SOL-HW-REVIEW-KIT.C6: the same declaration gives the same plan
        _, _, _, first = self.plan()
        _, _, _, second = self.plan()
        self.assertEqual(json.dumps(first.to_dict()), json.dumps(second.to_dict()))
        raw = fx.declaration_dict()
        raw["units"] = dict(reversed(list(raw["units"].items())))
        _, _, _, reordered = self.plan(raw)
        self.assertEqual({frozenset(g.units) for g in reordered.groups}, {frozenset(g.units) for g in first.groups})

    def test_equal_outputs_pack_deterministically(self):
        # SOL-HW-REVIEW-KIT.C6: the same declaration gives the same plan
        raw = plain_units({"a": 100, "b": 100, "c": 100, "d": 100})
        _, _, _, plan = self.plan(raw)
        self.assertEqual([g.units for g in plan.groups], [("a",), ("b",), ("c",), ("d",)])
        raw = plain_units({"a": 50, "b": 50, "c": 100})
        _, _, _, plan = self.plan(raw)
        self.assertEqual([g.units for g in plan.groups], [("a", "b"), ("c",)])


class PlanRecordTests(Case):
    def test_plan_is_flat_one_shared_context_and_one_fork_per_group_and_replica(self):
        # SOL-HW-REVIEW-KIT.C6: the plan has one shared context and one fork per group and replica
        _, _, shared, plan = self.plan(replicas={"u1": 3, "u4": 2}, variants=["full", "terse"])
        roots = [n for n in plan.nodes if n.role == planner.ROOT]
        forks = [n for n in plan.nodes if n.role == planner.UNIT]
        self.assertEqual(len(roots), 1)
        self.assertEqual(len(forks), 3 + 1 + 2)
        self.assertEqual({n.parent for n in forks}, {"root"})
        self.assertEqual([(n.group, n.replica, n.variant) for n in forks if n.group == "G1"],
                         [("G1", 1, "full"), ("G1", 2, "terse"), ("G1", 3, "full")])
        self.assertEqual(len({n.id for n in plan.nodes}), len(plan.nodes))
        self.assertTrue(all(n.attempt == 1 for n in plan.nodes))

    def test_default_is_one_replica_with_the_base_variant(self):
        # SOL-HW-REVIEW-KIT.C6: one fork per group and replica
        _, _, _, plan = self.plan()
        self.assertEqual([(n.replica, n.variant) for n in plan.lanes], [(1, "base")] * 3)
        _, _, _, two = self.plan(replicas=2)
        self.assertEqual(len(two.lanes), 6)

    def test_bad_replica_counts_are_refused(self):
        # SOL-HW-REVIEW-KIT.C6: one fork per group and replica
        for bad in (0, -1, True, 1.5):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.plan(replicas=bad)

    def test_record_holds_every_node_prefix_spec_prediction_version_and_commit(self):
        # SOL-HW-REVIEW-KIT.C6: the plan record lists every node with its role, parent, group, replica and attempt, the hash of each prefix, the session specification, the predicted cost and time with the prices and rates they used, the agent command line's version and the tool commit
        declaration, _, shared, plan = self.plan()
        record = json.loads(json.dumps(plan.to_dict()))
        for node in record["nodes"]:
            self.assertEqual(set(node), {"id", "role", "parent", "group", "replica", "attempt", "variant", "units", "prefix_sha",
                                         "message_sha"})
        self.assertEqual(record["nodes"][0]["role"], "root")
        self.assertEqual(record["nodes"][0]["prefix_sha"], shared.prefix_sha)
        for node in record["nodes"][1:]:
            self.assertEqual((node["role"], node["parent"], node["prefix_sha"]), ("unit", "root", shared.prefix_sha))
            prompt = messages.group_prompt(declaration, node["units"])
            self.assertEqual(node["message_sha"], messages.sha256(messages.prompt_message(prompt)))
        self.assertEqual(record["spec"]["json_schema"], declaration.json_schema())
        self.assertEqual(record["spec"]["model"], "claude-sonnet-5-5")
        self.assertEqual(record["spec_digest"], plan.spec_digest)
        self.assertEqual((record["cli_version"], record["tool_commit"]), ("9.9.9", "abc1234"))
        self.assertEqual(record["prices"], {"read": 0.10, "write": 4.37, "out": 8.95, "source": "measured"})
        self.assertEqual(record["timing"], {"per_call_s": 1.7, "tok_per_s": 134.0, "source": "measured"})
        self.assertEqual(set(record["predicted"]["per_node"]), {n["id"] for n in record["nodes"]})
        self.assertEqual(record["shared"]["prefix_sha"], shared.prefix_sha)

    def test_record_round_trips_through_json(self):
        # SOL-HW-REVIEW-KIT.C6: the plan record is a record that serialises
        _, _, _, plan = self.plan(replicas=2, variants=["a", "b"])
        again = planner.Plan.from_dict(json.loads(json.dumps(plan.to_dict())))
        self.assertEqual(again, plan)
        self.assertEqual(again.to_dict(), plan.to_dict())

    def test_prediction_follows_the_cost_model_by_hand(self):
        # SOL-HW-REVIEW-KIT.C6: the predicted cost and time use 1.7 seconds a call and output tokens at 134 a second
        raw = plain_units({"a": 268})
        declaration, found, shared, plan = self.plan(raw, bound=1)
        fork = plan.lanes[0]
        prompt = messages.group_prompt(declaration, ["a"])
        seconds = 2 * 1.7 + 268 / 134
        self.assertAlmostEqual(plan.predicted["per_node"][fork.id]["wall_s"], seconds, places=5)
        self.assertAlmostEqual(plan.predicted["per_node"]["root"]["wall_s"], 1.7 + 5 / 134, places=5)
        self.assertAlmostEqual(plan.predicted["wall_s"], 1.7 + 5 / 134 + seconds, places=3)
        context = shared.tokens
        expected = (context * 4.37 + 5 * 8.95) / 1e6 + (2 * context * 0.10 + len(prompt) * 4.37 + 268 * 8.95) / 1e6
        self.assertAlmostEqual(plan.predicted["cost_usd"], expected, places=5)

    def test_wall_time_counts_forks_in_waves_of_the_bound(self):
        # SOL-HW-REVIEW-KIT.C6: the largest group meets the review's time target, estimated as calls and output tokens
        raw = plain_units({"a": 1340, "b": 1340, "c": 1340, "d": 1340})
        _, _, _, wide = self.plan(raw, bound=4)
        _, _, _, narrow = self.plan(raw, bound=2)
        fork = 2 * 1.7 + 10
        self.assertAlmostEqual(wide.predicted["wall_s"] - wide.predicted["per_node"]["root"]["wall_s"], fork, places=3)
        self.assertAlmostEqual(narrow.predicted["wall_s"] - narrow.predicted["per_node"]["root"]["wall_s"], 2 * fork, places=3)

    def test_time_target_and_cost_ceiling_are_judged_in_the_record(self):
        # SOL-HW-REVIEW-KIT.C6: the largest group meets the review's time target
        raw = plain_units({"a": 1340})
        raw["budget"] = {"wall_s": 5, "usd": 0.0001, "context_tokens": 100000}
        _, _, _, plan = self.plan(raw)
        self.assertEqual((plan.predicted["meets_wall_target"], plan.predicted["within_cost_ceiling"]), (False, False))
        raw["budget"] = {"wall_s": 600, "usd": 50}
        _, _, _, plan = self.plan(raw)
        self.assertEqual((plan.predicted["meets_wall_target"], plan.predicted["within_cost_ceiling"]), (True, True))
        raw["budget"] = {}
        _, _, _, plan = self.plan(raw)
        self.assertEqual((plan.predicted["meets_wall_target"], plan.predicted["within_cost_ceiling"]), (None, None))

    def test_fitted_prices_and_rates_are_recorded_in_the_plan(self):
        # SOL-HW-REVIEW-KIT.C6: the prices and rates are data, refitted from telemetry, and the fitted values are recorded in the plan
        fitted = cm.Prices(0.2, 5.0, 10.0, "fitted")
        slower = cm.Timing(3.0, 100.0, "fitted")
        _, _, _, plan = self.plan(prices=fitted, timing=slower)
        self.assertEqual(plan.prices, {"read": 0.2, "write": 5.0, "out": 10.0, "source": "fitted"})
        self.assertEqual(plan.timing, {"per_call_s": 3.0, "tok_per_s": 100.0, "source": "fitted"})
        _, _, _, plain = self.plan()
        self.assertGreater(plan.predicted["cost_usd"], plain.predicted["cost_usd"])
        self.assertGreater(plan.predicted["wall_s"], plain.predicted["wall_s"])


class TreeAndBudgetTests(Case):
    def test_record_holds_the_saving_a_tree_would_give_and_the_threshold_and_stays_flat(self):
        # SOL-HW-REVIEW-KIT.C6: the plan record holds the saving a tree would give and the threshold it was compared with
        declaration, found, shared, plan = self.plan()
        calls = {g.id: 2 for g in plan.groups}
        total = sum(calls.values())
        expected = 0.0
        for artefact in found.artefacts:
            using = sum(calls[g.id] for g in plan.groups if artefact.name in g.needs)
            expected += artefact.tokens * (total - using) * 0.10 / 1e6
        self.assertAlmostEqual(plan.tree["saving_usd"], expected, places=6)
        self.assertGreater(plan.tree["saving_usd"], 0)
        self.assertEqual(plan.tree["threshold_usd"], 0.5)
        self.assertEqual((plan.tree["worth_building"], plan.tree["kept"]), (False, "flat"))
        self.assertEqual(len(plan.lanes), 3)

    def test_threshold_is_declared_and_a_saving_above_it_is_recorded_while_the_plan_stays_flat(self):
        # SOL-HW-REVIEW-KIT.C6: the plan record holds the saving a tree would give and the threshold it was compared with
        raw = fx.declaration_dict()
        raw["budget"]["tree_saving_usd"] = 1e-9
        _, _, _, plan = self.plan(raw)
        self.assertEqual(plan.tree["threshold_usd"], 1e-9)
        self.assertTrue(plan.tree["worth_building"])
        self.assertEqual(plan.tree["kept"], "flat")
        self.assertEqual({n.parent for n in plan.lanes}, {"root"})

    def test_a_tree_saves_nothing_when_every_group_needs_every_artefact(self):
        # SOL-HW-REVIEW-KIT.C6: the plan record holds the saving a tree would give
        _, _, _, plan = self.plan(plain_units({"a": 100, "b": 400}))
        self.assertEqual(plan.tree["saving_usd"], 0)

    def test_context_larger_than_the_budget_is_refused_naming_size_and_budget(self):
        # SOL-HW-REVIEW-KIT.C6: a shared context larger than the declared context budget is refused naming its size and the budget before any session starts
        raw = fx.declaration_dict()
        raw["budget"]["context_tokens"] = 1000
        with self.assertRaises(planner.OverBudget) as refused:
            self.plan(raw)
        self.assertEqual(refused.exception.budget, 1000)
        self.assertGreater(refused.exception.size, 1000)
        text = str(refused.exception)
        self.assertIn(str(refused.exception.size), text)
        self.assertIn("1000", text)

    def test_context_exactly_at_the_budget_is_accepted(self):
        # SOL-HW-REVIEW-KIT.C6: a shared context larger than the declared context budget is refused
        _, _, shared, _ = self.plan()
        raw = fx.declaration_dict()
        raw["budget"]["context_tokens"] = shared.tokens
        self.plan(raw)
        raw["budget"]["context_tokens"] = shared.tokens - 1
        with self.assertRaises(planner.OverBudget):
            self.plan(raw)

    def test_bound_below_one_is_refused(self):
        # SOL-HW-REVIEW-KIT.C6: a bound below one is refused
        for bad in (0, -3, 1.5, True, None):
            with self.subTest(bad=bad):
                with self.assertRaises(planner.BoundBelowOne):
                    self.plan(bound=bad)


class CostModelTests(unittest.TestCase):
    def test_makespan(self):
        # SOL-HW-REVIEW-KIT.C6: the time target is estimated from calls and output tokens
        self.assertEqual(cm.makespan([4, 3, 2, 1], 2), 5)
        self.assertEqual(cm.makespan([4, 3, 2, 1], 1), 10)
        self.assertEqual(cm.makespan([4, 3], 9), 4)
        self.assertEqual(cm.makespan([], 3), 0)
        with self.assertRaises(ValueError):
            cm.makespan([1], 0)

    def rows(self, prices, timing, count=8):
        found = []
        for index in range(count):
            read, write, out, calls = 1000 * (index + 1), 500 * ((index * 3) % 5 + 1), 100 * ((index * 7) % 6 + 1), 1 + index % 3
            found.append({"cache_read": read, "cache_write": write, "generated": out, "calls": calls,
                          "cost_usd": (read * prices[0] + write * prices[1] + out * prices[2]) / 1e6,
                          "wall_s": calls * timing[0] + out / timing[1]})
        return found

    def test_fit_recovers_prices_and_rates_from_figures(self):
        # SOL-HW-REVIEW-KIT.C6: the prices and rates are data, refitted from telemetry
        found = cm.fit(self.rows((0.2, 5.0, 10.0), (2.5, 100.0)))
        self.assertEqual((found.prices.read, found.prices.write, found.prices.out, found.prices.source), (0.2, 5.0, 10.0, "fitted"))
        self.assertEqual((found.timing.per_call_s, found.timing.tok_per_s, found.timing.source), (2.5, 100.0, "fitted"))
        self.assertTrue(found.fitted)
        self.assertTrue(any("prices fitted from 8" in note for note in found.notes))

    def test_fit_keeps_the_given_values_when_the_figures_do_not_determine_them(self):
        # SOL-HW-REVIEW-KIT.C6: the prices and rates are data, refitted from telemetry
        two = cm.fit(self.rows((0.2, 5.0, 10.0), (2.5, 100.0), count=2))
        self.assertEqual((two.prices, two.timing), (cm.Prices(), cm.Timing()))
        self.assertFalse(two.fitted)
        same = [{"cache_read": 10, "cache_write": 10, "generated": 10, "calls": 1, "cost_usd": 1.0, "wall_s": 2.0}] * 6
        self.assertFalse(cm.fit(same).fitted)
        nothing = cm.fit([])
        self.assertEqual((nothing.prices, nothing.timing), (cm.Prices(), cm.Timing()))

    def test_fit_rejects_a_negative_price_and_skips_incomplete_rows(self):
        # SOL-HW-REVIEW-KIT.C6: the prices and rates are data, refitted from telemetry
        rows = self.rows((0.2, 5.0, 10.0), (2.5, 100.0))
        for row in rows:
            row["cost_usd"] = -row["cost_usd"]
        self.assertEqual(cm.fit(rows).prices, cm.Prices())
        rows = self.rows((0.2, 5.0, 10.0), (2.5, 100.0)) + [{"calls": "x"}, {"cache_read": True}]
        found = cm.fit(rows)
        self.assertEqual(found.prices.source, "fitted")
        self.assertTrue(any("2 sessions lacked" in note for note in found.notes))

    def test_fit_starts_from_the_values_given_not_the_measured_ones(self):
        # SOL-HW-REVIEW-KIT.C6: the fitted values are recorded in the plan
        custom = cm.Prices(1.0, 2.0, 3.0, "given")
        self.assertEqual(cm.fit([], custom).prices, custom)

    # The cost, cache-read, cache-write and generated tokens of the 13 sessions of a recorded small-tier layout review run,
    # a root, its twelve units' forks and the repairs, with the cost each reported; they total 1.2067 USD.
    HAIKU_SESSIONS = [(0.35256, 269558, 270950, 291), (0.031106, 270276, 2264, 6131), (0.038628, 270276, 4463, 8260),
                      (0.05711, 270276, 10630, 13186), (0.049234, 270276, 5049, 12268), (0.060285, 270276, 4953, 16727),
                      (0.062062, 270276, 6622, 16770), (0.08215, 270276, 6228, 24963), (0.082302, 270276, 5787, 25200),
                      (0.155206, 558782, 38959, 34568), (0.126963, 270276, 8961, 41795), (0.071786, 279237, 40388, 6974),
                      (0.037318, 319625, 7156, 5672)]

    def test_the_small_tier_prices_reproduce_the_run_they_were_fitted_to_within_fifteen_per_cent(self):
        # SOL-HW-REVIEW-KIT.C6: the prices and rates are data, refitted from telemetry
        recorded = sum(cost for cost, *_ in self.HAIKU_SESSIONS)
        self.assertAlmostEqual(recorded, 1.21, delta=0.01)
        prices = cm.prices_for("claude-haiku-5-5")
        predicted = sum(prices.cost(read, write, out) for _, read, write, out in self.HAIKU_SESSIONS)
        self.assertLess(abs(predicted - recorded) / recorded, 0.15)
        sonnet = sum(cm.Prices().cost(read, write, out) for _, read, write, out in self.HAIKU_SESSIONS)
        self.assertGreater(sonnet, 2 * recorded, "the mid-tier prices would have predicted far more, so the model matters")

    # Two later recorded small-tier runs, as run totals: (sessions, cache read, cache written, fresh input, generated, cost USD).
    HELD_OUT_RUNS = {"haiku-3": (23, 7754909, 558264, 64, 412059, 2.048541), "haiku-2": (27, 9165577, 579238, 70, 384898, 2.069024)}

    def test_prices_fitted_only_from_the_first_small_tier_run_predict_two_later_recorded_runs_within_fifteen_per_cent(self):
        # SOL-HW-REVIEW-KIT.C6: the prices and rates are data, refitted from telemetry; held out, the prices are checked against runs they were not fitted to
        rows = [{"cost_usd": cost, "cache_read": read, "cache_write": write, "generated": out}
                for cost, read, write, out in self.HAIKU_SESSIONS]
        prices = cm.fit(rows).prices
        self.assertEqual(prices.source, "fitted")
        for name, (sessions, read, write, fresh, generated, recorded) in self.HELD_OUT_RUNS.items():
            with self.subTest(run=name):
                predicted = prices.cost(read, write, generated)
                self.assertLess(abs(predicted - recorded) / recorded, 0.15, f"{name}: predicted {predicted:.3f}, recorded {recorded}")
                midtier = cm.Prices().cost(read, write, generated)
                self.assertGreater(midtier, 2 * recorded, "the mid-tier prices would have predicted far more")

    def test_the_small_tier_prices_are_the_fit_of_the_recorded_sessions(self):
        # SOL-HW-REVIEW-KIT.C6: the prices and rates are data, refitted from telemetry
        rows = [{"cost_usd": cost, "cache_read": read, "cache_write": write, "generated": out}
                for cost, read, write, out in self.HAIKU_SESSIONS]
        found = cm.fit(rows).prices
        small = cm.prices_for("claude-haiku-5-5")
        for figure in ("read", "write", "out"):
            self.assertAlmostEqual(getattr(found, figure), getattr(small, figure), places=3)
        self.assertEqual(small.source, "fitted")

    def test_a_model_the_table_does_not_hold_is_priced_at_the_default_or_the_one_given(self):
        # SOL-HW-REVIEW-KIT.C6: the prices and rates are data, refitted from telemetry
        self.assertEqual(cm.prices_for("claude-sonnet-5-5"), cm.Prices())
        self.assertEqual(cm.prices_for("unlisted-model"), cm.Prices())
        self.assertEqual(cm.prices_for(None), cm.Prices())
        custom = cm.Prices(1.0, 2.0, 3.0, "given")
        self.assertEqual(cm.prices_for("unlisted-model", default=custom), custom)
        self.assertEqual(cm.prices_for("claude-haiku-5-5", default=custom), cm.HAIKU_PRICES)

    def test_defaults_are_the_measured_figures(self):
        # SOL-HW-REVIEW-KIT.C6: the time target is estimated as 1.7 seconds per call plus the output tokens at the measured rate
        self.assertEqual((cm.Prices().read, cm.Prices().write, cm.Prices().out), (0.10, 4.37, 8.95))
        self.assertEqual((cm.Timing().per_call_s, cm.Timing().tok_per_s), (1.7, 134.0))
        self.assertTrue(math.isclose(cm.Timing().seconds(2, 268), 5.4))


class PerModelPricing(Case):
    def test_the_planner_prices_each_context_and_its_forks_at_the_prices_of_its_own_model(self):
        # SOL-HW-REVIEW-KIT.C6: the predicted cost and time use the prices of each node's model
        raw = fx.declaration_dict()
        declaration = decl.parse(json.dumps(raw), "caller.json")
        found = catalogue.admit(declaration, self.review)
        shared = messages.shared_context(found)
        spec = messages.make_spec(declaration, ("Read",), "/work", "claude-sonnet-5-5")
        policy = ensemble.parse_policy({"variants": [{"id": "full"}, {"id": "small", "model": "claude-haiku-5-5"}]})
        contexts = ensemble.contexts(spec, shared, policy)
        made = planner.make_plan(declaration, found, shared, spec, bound=4, cli_version="9.9.9", tool_commit="abc1234",
                                 replicas=2, variants=policy.ids, contexts=contexts)
        per_node = made.predicted["per_node"]
        small_root = contexts[1].root_id
        self.assertAlmostEqual(per_node["root"]["cost_usd"], cm.root_cost(cm.Prices(), shared.tokens), places=5)
        self.assertAlmostEqual(per_node[small_root]["cost_usd"], cm.root_cost(cm.HAIKU_PRICES, shared.tokens), places=5)
        by_parent = {}
        for node in made.lanes:
            by_parent.setdefault(node.parent, []).append(node)
        self.assertEqual(sorted(by_parent), sorted(["root", small_root]))
        for parent, prices in (("root", cm.Prices()), (small_root, cm.HAIKU_PRICES)):
            for node in by_parent[parent]:
                group = next(g for g in made.groups if g.id == node.group)
                expected = cm.fork_cost(prices, shared.tokens, 0, group.expected_output_tokens)
                self.assertGreater(per_node[node.id]["cost_usd"], expected - 1e-3)
                self.assertLess(per_node[node.id]["cost_usd"], expected + 0.01, "only the unit's prompt tokens are added")
        self.assertEqual(made.contexts[0]["prices"], cm.HAIKU_PRICES.as_dict(), "the plan records each other context's prices")
        self.assertEqual(made.prices, cm.Prices().as_dict(), "and the review's own")

    def test_a_plan_on_the_small_tier_is_cheaper_than_the_same_plan_on_the_mid_tier_and_given_prices_override_the_table(self):
        # SOL-HW-REVIEW-KIT.C6: the predicted cost and time use the prices of each node's model
        declaration = decl.parse(json.dumps(fx.declaration_dict()), "caller.json")
        found = catalogue.admit(declaration, self.review)
        shared = messages.shared_context(found)

        def cost(model, **kwargs):
            spec = messages.make_spec(declaration, ("Read",), "/work", model)
            return planner.make_plan(declaration, found, shared, spec, bound=4, cli_version="9.9.9", tool_commit="abc1234",
                                     **kwargs).predicted["cost_usd"]
        self.assertLess(cost("claude-haiku-5-5") * 2, cost("claude-sonnet-5-5"))
        self.assertEqual(cost("claude-haiku-5-5", prices=cm.Prices()), cost("claude-sonnet-5-5"))


if __name__ == "__main__":
    unittest.main()
