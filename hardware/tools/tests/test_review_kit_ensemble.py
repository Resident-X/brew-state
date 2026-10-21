#!/usr/bin/env python3
"""The review kit's replicas: their number by stakes or a round flag, the prompts that differ as declared, and a replica on another model.

Synthetic declarations and review folders; no session is started.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import catalogue, decl, ensemble, messages, planner  # noqa: E402
from review_kit import session as sess  # noqa: E402

DECLARATION = decl.parse(json.dumps(fx.declaration_dict()), "caller.json")


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.review = fx.review_folder(os.path.join(self.tmp.name, "review"))

    def plan(self, policy, flag=None, model="claude-sonnet-5-5"):
        found = catalogue.admit(DECLARATION, self.review)
        shared = messages.shared_context(found)
        spec = messages.make_spec(DECLARATION, ("Read",), "/work", model)
        made = planner.make_plan(DECLARATION, found, shared, spec, bound=4, cli_version="9.9.9", tool_commit="abc1234",
                                 replicas=ensemble.replicas_by_unit(DECLARATION, policy, flag), variants=policy.ids,
                                 prompt_for=ensemble.prompt_for(DECLARATION, policy))
        return shared, spec, made


class Counts(Case):
    # SOL-HW-REVIEW-KIT.C9: a unit of normal stakes has two replicas and a unit of high stakes three
    def test_a_unit_of_normal_stakes_has_two_replicas_and_one_of_high_stakes_three(self):
        policy = ensemble.Policy()
        self.assertEqual(ensemble.replica_count(policy, "normal"), 2)
        self.assertEqual(ensemble.replica_count(policy, "high"), 3)
        self.assertEqual(ensemble.replica_count(policy, "low"), 1)
        self.assertEqual(ensemble.replicas_by_unit(DECLARATION), {"u1": 2, "u2": 2, "u3": 3, "u4": 2})

    # SOL-HW-REVIEW-KIT.C9: a round flag overrides the declared number
    def test_a_round_flag_overrides_the_number_for_every_stakes(self):
        self.assertEqual(ensemble.replicas_by_unit(DECLARATION, flag=1), {"u1": 1, "u2": 1, "u3": 1, "u4": 1})
        self.assertEqual(ensemble.replicas_by_unit(DECLARATION, flag=5), {"u1": 5, "u2": 5, "u3": 5, "u4": 5})

    def test_a_flag_that_is_not_a_whole_number_of_one_or_more_is_refused(self):
        for flag in (0, -1, True, 2.0, "2"):
            with self.assertRaises(ensemble.PolicyError, msg=repr(flag)) as caught:
                ensemble.replica_count(ensemble.Policy(), "normal", flag)
            self.assertIn("whole number of one or more", str(caught.exception))

    def test_the_declared_counts_replace_the_defaults_and_the_planner_gives_a_coupled_group_the_most_of_its_units(self):
        policy = ensemble.parse_policy({"replicas": {"normal": 1, "high": 4}})
        _, _, made = self.plan(policy)
        counts = {group.units: group.replicas for group in made.groups}
        self.assertEqual(counts[("u2", "u3")], 4)
        self.assertEqual(counts[("u1",)], 1)
        self.assertEqual(len([node for node in made.lanes if node.group == "G2"]), 4)

    def test_replicas_take_the_declared_variants_in_turn(self):
        _, _, made = self.plan(ensemble.Policy())
        lane = {(node.group, node.replica): node.variant for node in made.lanes}
        self.assertEqual(lane[("G1", 1)], "full")
        self.assertEqual(lane[("G1", 2)], "hunt")
        self.assertEqual(lane[("G2", 3)], "full")


class Policies(unittest.TestCase):
    def test_an_absent_policy_is_the_default_one_full_and_one_terse(self):
        policy = ensemble.parse_policy(None)
        self.assertEqual(policy.ids, ["full", "hunt"])
        self.assertTrue(policy.variant("hunt").terse)
        self.assertFalse(policy.variant("full").terse)

    def test_declared_variants_are_read_with_every_field(self):
        policy = ensemble.parse_policy({"variants": [{"id": "a"}, {"id": "b", "item_order": "shuffled", "view_order": "reversed",
                                                        "framing": "Think of the bench.", "seed": 7, "model": "claude-haiku-4-5"}]})
        self.assertEqual(policy.variant("b"), ensemble.Variant("b", "shuffled", "reversed", "Think of the bench.", False, 7,
                                                                 "claude-haiku-4-5"))

    def test_every_slip_in_a_policy_is_named(self):
        cases = [("x", "not a mapping"), ({"junk": 1}, "'junk'"), ({"variants": []}, "non-empty list"),
                 ({"variants": [{"item_order": "given"}]}, "`id`"), ({"variants": [{"id": "a", "item_order": "random"}]}, "'random'"),
                 ({"variants": [{"id": "a"}, {"id": "a"}]}, "declared twice"), ({"variants": [{"id": "a", "colour": 1}]}, "'colour'"),
                 ({"variants": [{"id": "a", "terse": "yes"}]}, "terse"), ({"variants": [{"id": "a", "seed": True}]}, "seed"),
                 ({"variants": [{"id": "a", "model": " "}]}, "model"),
                 ({"replicas": {"urgent": 2}}, "'urgent'"), ({"replicas": {"normal": 0}}, "0 replicas"), ({"replicas": []}, "mapping")]
        for raw, expected in cases:
            with self.assertRaises(ensemble.PolicyError, msg=repr(raw)) as caught:
                ensemble.parse_policy(raw)
            self.assertIn(expected, str(caught.exception))

    def test_an_unknown_variant_is_refused_naming_the_declared_ones(self):
        with self.assertRaises(ensemble.PolicyError) as caught:
            ensemble.Policy().variant("nope")
        self.assertIn("['full', 'hunt']", str(caught.exception))


class Prompts(Case):
    def group(self, policy, variant, units=("u1",)):
        return ensemble.prompt_for(DECLARATION, policy)(list(units), variant)

    # SOL-HW-REVIEW-KIT.C9: each replica's prompt differs from the others in the declared item order, view order and framing and is byte-identical on a second build
    def test_each_replicas_prompt_differs_in_item_order_view_order_and_framing(self):
        policy = ensemble.parse_policy({"variants": [
            {"id": "given"},
            {"id": "items", "item_order": "reversed"},
            {"id": "views", "view_order": "reversed"},
            {"id": "framing", "framing": "Mind the clearances."},
            {"id": "terse", "terse": True}]})
        prompts = {variant: self.group(policy, variant) for variant in policy.ids}
        self.assertEqual(len(set(prompts.values())), 5)
        self.assertLess(prompts["given"].index("- i1"), prompts["given"].index("- i2"))
        self.assertLess(prompts["items"].index("- i2"), prompts["items"].index("- i1"))
        self.assertIn("Take the views in this order: view_a.png, guide.md.", prompts["views"])
        self.assertNotIn("Take the views", prompts["given"])
        self.assertTrue(prompts["framing"].startswith("Mind the clearances.\n\n"))
        self.assertTrue(prompts["terse"].startswith(ensemble.TERSE_FRAMING))
        self.assertNotIn("Hunt for failures", prompts["given"])

    def test_the_terse_framing_comes_before_a_declared_framing(self):
        policy = ensemble.parse_policy({"variants": [{"id": "a", "terse": True, "framing": "And the bench."}]})
        self.assertEqual(self.group(policy, "a").split("\n\n")[:2], [ensemble.TERSE_FRAMING, "And the bench."])

    def test_a_prompt_is_byte_identical_on_a_second_build_from_a_fresh_declaration(self):
        policy = ensemble.parse_policy({"variants": [{"id": "s", "item_order": "shuffled", "view_order": "shuffled", "seed": 3,
                                                      "framing": "x", "terse": True}]})
        again = decl.parse(json.dumps(fx.declaration_dict()), "caller.json")
        first = ensemble.prompt_for(DECLARATION, policy)(["u2", "u3"], "s")
        second = ensemble.prompt_for(again, ensemble.parse_policy(json.loads(json.dumps(
            {"variants": [{"id": "s", "item_order": "shuffled", "view_order": "shuffled", "seed": 3, "framing": "x", "terse": True}]}))))(["u2", "u3"], "s")
        self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))

    def test_the_planner_records_the_hash_of_each_replicas_message_and_they_differ_and_repeat(self):
        _, _, first = self.plan(ensemble.Policy())
        _, _, second = self.plan(ensemble.Policy())
        by_replica = {(node.group, node.replica): node.message_sha for node in first.lanes}
        self.assertNotEqual(by_replica[("G1", 1)], by_replica[("G1", 2)])
        self.assertEqual([n.message_sha for n in first.lanes], [n.message_sha for n in second.lanes])

    def test_the_prompt_as_declared_is_the_one_a_unit_without_replicas_has(self):
        policy = ensemble.Policy()
        for units in (["u1"], ["u2", "u3"]):
            self.assertEqual(self.group(policy, "full", units), messages.group_prompt(DECLARATION, units))

    def test_a_variants_prompt_holds_the_same_items_whatever_the_order(self):
        policy = ensemble.parse_policy({"variants": [{"id": "s", "item_order": "shuffled", "seed": 11}]})
        text = self.group(policy, "s", ("u2", "u3"))
        for item in ("j1", "k1", "k2"):
            self.assertEqual(text.count(f"- {item}"), 1, item)

    def test_a_shuffle_is_fixed_by_its_seed_and_unit_and_is_a_permutation(self):
        names = [f"n{number}" for number in range(12)]
        first = ensemble.ordered(names, ensemble.SHUFFLED, 1, "u1")
        self.assertEqual(first, ensemble.ordered(names, ensemble.SHUFFLED, 1, "u1"))
        self.assertEqual(sorted(first), sorted(names))
        self.assertNotEqual(first, names)
        self.assertNotEqual(first, ensemble.ordered(names, ensemble.SHUFFLED, 2, "u1"))
        self.assertNotEqual(first, ensemble.ordered(names, ensemble.SHUFFLED, 1, "u2"))
        self.assertEqual(ensemble.ordered(names, ensemble.REVERSED, 0, "u"), names[::-1])
        with self.assertRaises(ensemble.PolicyError):
            ensemble.ordered(names, "sideways", 0, "u")

    def test_a_unit_text_function_supplies_the_units_own_prompt_and_gets_the_items_in_the_variants_order(self):
        seen = []

        def text(unit, items):
            seen.append((unit, list(items)))
            return f"JUDGE {unit}"
        policy = ensemble.Policy()
        prompt = ensemble.variant_prompt(DECLARATION, ["u1"], policy.variant("hunt"), text)
        self.assertEqual(seen, [("u1", ["i2", "i1"])])
        self.assertTrue(prompt.endswith("JUDGE u1\n\nTake the views in this order: view_a.png, guide.md."))


class OtherModels(Case):
    # SOL-HW-REVIEW-KIT.C9: a replica declared for a model other than the review's has its own shared context and session specification and shares no cache with the others
    def test_a_replica_on_another_model_has_its_own_context_specification_and_cache(self):
        policy = ensemble.parse_policy({"variants": [{"id": "full"}, {"id": "hunt", "terse": True}, {"id": "small", "model": "claude-haiku-4-5"}]})
        shared, spec, _ = self.plan(policy)
        found = ensemble.contexts(spec, shared, policy)
        self.assertEqual([context.model for context in found], ["claude-sonnet-5-5", "claude-haiku-4-5"])
        own, other = found
        self.assertEqual(own.variants, ("full", "hunt"))
        self.assertEqual(other.variants, ("small",))
        self.assertEqual((own.root_id, other.root_id), ("root", "root.claude-haiku-4-5"))
        self.assertIs(own.spec, spec)
        self.assertEqual(other.spec.model, "claude-haiku-4-5")
        for name in ("tools", "cwd", "system", "append_system", "json_schema"):
            self.assertEqual(getattr(other.spec, name), getattr(spec, name))
        self.assertNotEqual(other.spec.digest, spec.digest)
        self.assertNotEqual(other.cache_key, own.cache_key)
        self.assertEqual(other.shared.prefix_sha, own.shared.prefix_sha)
        arguments = sess.arguments(other.spec)
        self.assertEqual(arguments[arguments.index("--model") + 1], "claude-haiku-4-5")

    def test_a_variant_on_the_reviews_own_model_or_none_forks_from_the_reviews_own_context(self):
        policy = ensemble.parse_policy({"variants": [{"id": "a"}, {"id": "b", "model": "claude-sonnet-5-5"}]})
        shared, spec, _ = self.plan(policy)
        found = ensemble.contexts(spec, shared, policy)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].variants, ("a", "b"))

    def test_each_other_model_gets_one_context_whatever_the_number_of_variants_on_it(self):
        policy = ensemble.parse_policy({"variants": [{"id": "a"}, {"id": "b", "model": "m-two"}, {"id": "c", "model": "m-two"},
                                                     {"id": "d", "model": "m-three"}]})
        shared, spec, _ = self.plan(policy)
        found = ensemble.contexts(spec, shared, policy)
        self.assertEqual([(c.model, c.variants) for c in found], [("claude-sonnet-5-5", ("a",)), ("m-three", ("d",)), ("m-two", ("b", "c"))])
        self.assertEqual(len({c.cache_key for c in found}), 3)
        self.assertEqual(ensemble.context_of(found, "c").model, "m-two")

    def test_only_the_variants_in_use_decide_which_contexts_are_built(self):
        policy = ensemble.parse_policy({"variants": [{"id": "a"}, {"id": "b", "model": "m-two"}]})
        shared, spec, _ = self.plan(policy)
        self.assertEqual(len(ensemble.contexts(spec, shared, policy, ["a"])), 1)
        with self.assertRaises(ensemble.PolicyError):
            ensemble.context_of(ensemble.contexts(spec, shared, policy, ["a"]), "b")
        with self.assertRaises(ensemble.PolicyError):
            ensemble.contexts(spec, shared, policy, ["zz"])

    def test_a_review_with_no_model_set_treats_a_variant_with_a_model_as_another_model(self):
        policy = ensemble.parse_policy({"variants": [{"id": "a"}, {"id": "b", "model": "m-two"}]})
        shared, spec, _ = self.plan(policy, model=None)
        found = ensemble.contexts(spec, shared, policy)
        self.assertEqual([c.model for c in found], [None, "m-two"])


if __name__ == "__main__":
    unittest.main()
