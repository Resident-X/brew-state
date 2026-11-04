#!/usr/bin/env python3
"""The review kit's context budget and the model window table: how a declaration states a budget, what it resolves to,
and what the command refuses before any session starts.

Synthetic declarations and review folders; the agent command line is a stand-in and no model is called.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
import test_review_kit_command as base  # noqa: E402
from review_kit import catalogue, costmodel as cm, decl, messages, planner  # noqa: E402


def declaration_with_budget(budget):
    raw = fx.declaration_dict()
    raw["budget"] = budget
    return raw


def loaded(budget):
    return decl.parse(json.dumps(declaration_with_budget(budget)), "caller.json")


class WindowTable(unittest.TestCase):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C2: a declaration that states no figure is held to the context window the kit declares as data for the review's model multiplied by the headroom fraction the declaration states, so a review with no stated budget is still refused when a session would exceed it, and a model with no declared window and no stated figure is refused naming the model and where its window is declared
    def test_the_models_the_reviews_run_on_have_a_declared_window_and_no_other_model_is_given_one(self):
        self.assertEqual(cm.window_for("claude-sonnet-5-5"), 1_000_000)
        self.assertEqual(cm.window_for("claude-haiku-5-5"), 1_000_000)
        self.assertIsNone(cm.window_for("a-model-nobody-declared"))
        self.assertIsNone(cm.window_for(None))
        self.assertEqual(cm.window_for("small", {"small": 8000}), 8000)

    def test_the_fraction_is_taken_of_the_window_and_rounded_down(self):
        budget = loaded({"context_fraction": 0.5}).budget
        self.assertEqual(planner.context_budget(budget, "claude-sonnet-5-5"), 500_000)
        odd = loaded({"context_fraction": 0.3333337}).budget
        self.assertEqual(planner.context_budget(odd, "claude-sonnet-5-5"), 333_333)
        self.assertEqual(planner.context_budget(loaded({"context_fraction": 1}).budget, "claude-haiku-5-5"), 1_000_000)

    def test_a_figure_is_the_budget_whatever_the_model_and_no_figure_and_no_fraction_is_no_budget(self):
        self.assertEqual(planner.context_budget(loaded({"context_tokens": 1234}).budget, "a-model-nobody-declared"), 1234)
        self.assertEqual(planner.context_budget(loaded({"context_tokens": 1234}).budget, None), 1234)
        self.assertIsNone(planner.context_budget(loaded({"wall_s": 5}).budget, None))

    def test_a_fraction_of_a_window_the_kit_does_not_declare_is_refused_naming_the_model_and_where_to_declare_it(self):
        with self.assertRaises(planner.WindowUndeclared) as refused:
            planner.context_budget(loaded({"context_fraction": 0.5}).budget, "a-model-nobody-declared")
        text = str(refused.exception)
        for part in ("a-model-nobody-declared", "no declared context window", "WINDOW_TOKENS_BY_MODEL", "review_kit/costmodel.py",
                     "context_tokens"):
            self.assertIn(part, text)
        with self.assertRaises(planner.WindowUndeclared) as unnamed:
            planner.context_budget(loaded({"context_fraction": 0.5}).budget, None)
        self.assertIn("--model", str(unnamed.exception))


class BudgetKeys(unittest.TestCase):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C2: a declaration that states both a figure and a headroom fraction is refused naming both
    def test_a_figure_and_a_fraction_together_are_refused_naming_both(self):
        with self.assertRaises(decl.DeclarationError) as refused:
            loaded({"context_tokens": 5000, "context_fraction": 0.5})
        text = "\n".join(refused.exception.lines)
        self.assertIn("caller.json", text)
        self.assertIn("context_tokens (5000)", text)
        self.assertIn("context_fraction (0.5)", text)
        self.assertEqual(len(refused.exception.lines), 1)

    def test_a_fraction_is_above_zero_and_at_most_one(self):
        for bad in (0, -0.1, 1.5, "half", True, None):
            with self.subTest(bad=bad):
                with self.assertRaises(decl.DeclarationError) as refused:
                    loaded({"context_fraction": bad})
                self.assertIn("context_fraction", "\n".join(refused.exception.lines))
        self.assertEqual(loaded({"context_fraction": 0.25}).budget.context_fraction, 0.25)


class CommandRefusals(base.Case):
    def assertNothingStarted(self):
        self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(os.path.join(self.out, "run.lock")))

    def declare(self, budget, name="budgeted"):
        self.write_caller(declaration=declaration_with_budget(budget), name=name)
        return name

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C2: a model with no declared window and no stated figure is refused naming the model and where its window is declared
    def test_a_fraction_with_a_model_that_has_no_declared_window_is_refused_before_any_session(self):
        name = self.declare({"context_fraction": 0.5})
        text = self.refused("window-undeclared", "--model", "a-model-nobody-declared", caller=name)
        self.assertIn("a-model-nobody-declared", text)
        self.assertIn("WINDOW_TOKENS_BY_MODEL", text)
        self.assertNothingStarted()
        self.assertFalse(os.path.exists(self.out))

    def test_a_fraction_with_no_model_named_is_refused_telling_to_name_one(self):
        name = self.declare({"context_fraction": 0.5})
        text = self.refused("window-undeclared", caller=name)
        self.assertIn("--model", text)
        self.assertNothingStarted()

    def test_the_refusal_is_the_same_facts_in_json(self):
        name = self.declare({"context_fraction": 0.5})
        status, out, err = self.run_command("--model", "a-model-nobody-declared", caller=name, fmt="json")
        self.assertEqual((status, err), (1, ""))
        report = json.loads(out)
        self.assertEqual(report["result"], "REFUSED")
        self.assertTrue(any("a-model-nobody-declared" in line and command_cause() in line for line in report["refusals"]))
        self.assertNothingStarted()

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C2: shared documents over the budget on their own are refused naming their size and the budget as before
    def test_a_context_over_the_window_times_the_fraction_is_refused_with_its_size_and_that_budget(self):
        name = self.declare({"context_fraction": 0.000001})
        text = self.refused("over-budget", "--model", "claude-sonnet-5-5", caller=name)
        self.assertIn("budget of 1 tokens", text)
        self.assertNothingStarted()

    def test_a_declaration_stating_both_a_figure_and_a_fraction_is_refused_by_the_command(self):
        name = self.declare({"context_tokens": 100000, "context_fraction": 0.5})
        text = self.refused("declaration-refused", "--model", "claude-sonnet-5-5", caller=name)
        self.assertIn("context_tokens", text)
        self.assertIn("context_fraction", text)
        self.assertNothingStarted()


def command_cause():
    from review_kit import command
    return command.CAUSES["window-undeclared"][0]


if __name__ == "__main__":
    unittest.main()
