#!/usr/bin/env python3
"""The review kit's roots: what each root holds, how the groups are formed and the roots made from them, how they are sized, what
the merge holds the groups' results to, and the proof's key for a run over them.

Synthetic designs of generic units and views in temporary folders. The views are written as images whose header states a
size, which is all the kit measures; the stand-in for the agent command line plays the sessions and no model is called.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import threading
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
import test_review_kit_command as base  # noqa: E402
import test_review_kit_proof as proof_tests  # noqa: E402
from review_kit import catalogue, decl, merge, messages, planner, proof, results, scheduler  # noqa: E402
from review_kit import executor as ex  # noqa: E402

TILE = (280, 280)
HEADER = re.compile(r"=== (?:image: )?(.+?) ===")
RULE = r"^VIOLATION \| [^|]*\| (?P<rule>[^|]+?) \|"


def view(name):
    return f"views/{name}.png"


def synthetic(units, *, docs=("guide.md",), sizes=None, budget=None, couples=(), rules=None, report=None, spare=(), outputs=None):
    """A declaration of generic units, each needing the documents and the views listed for it, and the function that writes
    the review folder it names. `units` maps a unit to its view names, `sizes` a view name to its pixel size (TILE by
    default), `spare` views the folder holds that no unit needs, `outputs` a unit to its expected output tokens (200 by default), `couples` pairs of units declared coupled, `rules` a unit to the check rules it judges, `report` the text of the
    deterministic check's report."""
    raw = fx.declaration_dict()
    names = sorted({name for views in units.values() for name in views} | set(spare))
    raw["artefacts"] = {doc: {"kind": "text", "source": f"docs/{doc}"} for doc in docs}
    raw["artefacts"].update({view(name): {"kind": "image", "source": view(name)} for name in names})
    raw["units"] = {uid: {"items": [f"{uid}-i1", f"{uid}-i2"], "template": "t", "needs": list(docs) + [view(n) for n in views],
                          "expected_output_tokens": (outputs or {}).get(uid, 200), "values": {"area": uid}} for uid, views in units.items()}
    for first, second in couples:
        raw["units"][first].setdefault("couples_with", []).append(second)
    if report is not None:
        raw["artefacts"]["check-report.txt"] = {"kind": "text", "source": "check-report.txt"}
        raw["check_extract"] = {"report": "check-report.txt", "rule": RULE}
    for uid, held in (rules or {}).items():
        raw["units"][uid]["check_rules"] = list(held)
    raw["budget"] = dict(budget or {})
    sizes = sizes or {}

    def prepare(folder):
        for doc in docs:
            fx.write(folder, f"docs/{doc}", f"# {doc}\n" + "A line of the document. " * 4)
        for name in names:
            width, height = sizes.get(name, TILE)
            fx.write(folder, view(name), fx.header_png(width, height))
        if report is not None:
            fx.write(folder, "check-report.txt", report)

    return raw, prepare


def parsed(raw):
    return decl.parse(json.dumps(raw), "caller.json")


def formed(test, raw, prepare, model="claude-sonnet-5-5"):
    """The groups of a synthetic design, formed with no session: the declaration, the catalogue and the groups."""
    import tempfile
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    folder = os.path.join(tmp.name, "review")
    prepare(folder)
    declaration = parsed(raw)
    found = catalogue.admit(declaration, folder)
    return declaration, found, planner.form(declaration, found, model, hold_groups=True)


def held_names(message):
    """The artefact names a context message holds, in order, read from its own blocks."""
    names = []
    for block in json.loads(message)["message"]["content"]:
        if block["type"] == "text":
            found = HEADER.match(block["text"])
            if found:
                names.append(found.group(1))
    return names


def declared(raw, units):
    return sorted({name for uid in units for name in raw["units"][uid]["needs"]})


def tokens_of(declaration, found, units):
    """What a root holding what the units declare weighs, measured from the catalogue's artefacts and not from the plan."""
    names = {n for u in units for n in declaration.units[u].needs}
    return messages.root_tokens(found.subset(names).artefacts)


def apart(test, raw, prepare):
    """The declaration with a budget no two groups' roots fit together within: the size of the largest group alone, which a root
    holding anything more than a group's own artefacts exceeds. Every group's root is its own, whatever the overlap."""
    _, _, result = formed(test, dict(raw, budget={}), prepare)
    raw["budget"] = {"context_tokens": max(group.tokens for group in result.groups)}
    return raw


class RootsHoldOnlyTheirGroupsArtefacts(unittest.TestCase):
    SHARED = [f"shared-{n}" for n in range(40)]

    def design(self):
        """Three coupled pairs of units over two hundred to three hundred views each, of which the second pair alone needs one
        view, and a budget the first two groups fit together within and the third group fills: two roots."""
        per = {"a": [f"a-{n}" for n in range(120)], "b": [f"b-{n}" for n in range(120)], "c": [f"c-{n}" for n in range(300)]}
        units = {}
        for g, own in per.items():
            half = len(own) // 2
            units[f"{g}1"] = self.SHARED + own[:half] + (["exclusive-b"] if g == "b" else [])
            units[f"{g}2"] = self.SHARED + own[half:]
        couples = [("a1", "a2"), ("b1", "b2"), ("c1", "c2")]
        raw, prepare = synthetic(units, couples=couples)
        declaration, found, _ = formed(self, raw, prepare)
        raw["budget"] = {"context_tokens": tokens_of(declaration, found, ["c1", "c2"])}
        return raw, prepare

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C1: Over a synthetic review folder of generic units whose declared needs total at least five hundred images, split between shared documents, views every group needs and views only one group needs, each root holds the shared documents and only the views the units of the groups it serves declare, and no session of a group is given an image that none of the units of the groups its root serves declare. The test includes an artefact that exactly one other group needs, served by a different root, and fails if it appears in this group's root; two groups that share a root are served by a root that holds both groups' views. Replicas of one group hold the same artefacts.
    def test_each_root_holds_the_shared_artefacts_and_only_the_views_of_its_groups_and_a_run_gives_no_session_another(self):
        raw, prepare = self.design()
        images = [name for name, entry in raw["artefacts"].items() if entry["kind"] == "image"]
        self.assertGreaterEqual(len(images), 500)
        harness = fx.Harness(self, raw=raw, prepare=prepare, replicas=2, variants=["full", "hunt"])
        plan = harness.plan
        self.assertEqual([g.units for g in plan.groups], [("a1", "a2"), ("b1", "b2"), ("c1", "c2")])
        self.assertEqual([(r.id, r.groups) for r in plan.root_records], [("root.R1", ("G1", "G2")), ("root.R2", ("G3",))],
                         "the first two groups' views fit one root together, the third's fill a root")
        served = {r.id: [g for g in plan.groups if g.id in r.groups] for r in plan.root_records}
        for root in plan.root_records:
            expected = declared(raw, [u for g in served[root.id] for u in g.units])
            self.assertEqual(held_names(harness.roots[root.id].message), expected, root.id)
            self.assertEqual(list(root.needs), expected)
        first, second = (held_names(harness.roots[r.id].message) for r in plan.root_records)
        for both in ("guide.md", view("exclusive-b")):
            self.assertIn(both, first)
        self.assertIn(view("a-3"), first)
        self.assertIn(view("b-3"), first, "two groups that share a root are served by a root that holds both groups' views")
        self.assertNotIn(view("exclusive-b"), second, "the view exactly one other group needs is in the other root, not this one")
        self.assertFalse({view(n) for n in ("a-3", "b-3")} & set(second))
        self.assertFalse({view("c-3")} & set(first))
        for shared in ["guide.md"] + [view(n) for n in self.SHARED]:
            self.assertIn(shared, first)
            self.assertIn(shared, second)
        harness.fresh()
        calls = harness.executor.calls
        sent = {call.label: held_names(call.message) for call in calls if call.label.startswith("root")}
        self.assertEqual(sorted(sent), ["root.R1", "root.R2"])
        for root in plan.root_records:
            self.assertEqual(sent[root.id], list(root.needs), "a session is given only what its root's groups' units declare")
        sessions = {}
        for session, call in zip(harness.executor.sessions, calls):
            sessions[call.label] = session
        for call in calls:
            if call.fork:
                self.assertEqual(held_names(call.message), [], "a fork's message carries no artefact")
                self.assertEqual(call.parent, sessions[plan.root_of(call.label.split(".")[0]).id])
        for group in plan.groups:
            forks = [c for c in calls if c.label.startswith(group.id + ".") and c.fork]
            self.assertEqual({c.parent for c in forks}, {sessions[group.root]}, "the replicas of a group hold the same root")
            self.assertGreaterEqual(len(forks), 2)

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C1: A verdict row that cites a view held only by another root is flagged naming the row and the view.
    def test_a_verdict_row_citing_a_view_only_another_root_holds_is_flagged_naming_the_row_and_the_view(self):
        raw, prepare = self.design()
        answer = fx.good_answer(parsed(raw), ["c1", "c2"])
        answer["tables"]["Verdicts"][0]["Note"] = f"the clearance is shown on {view('exclusive-b')}"
        harness = fx.Harness(self, raw=raw, prepare=prepare, script={"G3.r1.a1": ex.Reply(structured=answer, text="x")})
        record = harness.fresh()
        first = next(n for n in record["nodes"] if n["id"] == "G3.r1.a1")
        self.assertEqual(len(first["problems"]), 1, first["problems"])
        line = first["problems"][0]
        for part in ("row 1", "c1-i1", view("exclusive-b"), "only another root holds"):
            self.assertIn(part, line)
        repair = next(n for n in record["nodes"] if n["id"] == "G3.r1.a2")
        self.assertEqual(repair["role"], "repair", "the unit is asked to correct the row")
        self.assertIn(view("exclusive-b"), next(c for c in harness.executor.calls if c.label == "G3.r1.a2").message)

    def test_a_row_citing_a_view_its_own_root_holds_though_only_another_group_of_that_root_needs_it_is_not_flagged(self):
        raw, prepare = self.design()
        answer = fx.good_answer(parsed(raw), ["a1", "a2"])
        answer["tables"]["Verdicts"][0]["Note"] = f"see {view('exclusive-b')}"
        harness = fx.Harness(self, raw=raw, prepare=prepare, script={"G1.r1.a1": ex.Reply(structured=answer, text="x")})
        self.assertEqual(harness.plan.group_of("a1").root, harness.plan.group_of("b1").root, "the views are held by the one root")
        record = harness.fresh()
        self.assertEqual([n["id"] for n in record["nodes"] if n["group"] == "G1"], ["G1.r1.a1"])

    def test_a_row_citing_a_view_its_own_group_needs_or_citing_nothing_is_not_flagged(self):
        raw, prepare = self.design()
        answer = fx.good_answer(parsed(raw), ["c1", "c2"])
        answer["tables"]["Verdicts"][0]["Note"] = f"see {view('c-3')} and {view('shared-4')}"
        harness = fx.Harness(self, raw=raw, prepare=prepare, script={"G3.r1.a1": ex.Reply(structured=answer, text="x")})
        record = harness.fresh()
        self.assertEqual([n["id"] for n in record["nodes"] if n["group"] == "G3"], ["G3.r1.a1"])

    def test_a_view_is_cited_by_its_last_component_too_unless_a_held_view_has_it(self):
        found = results.cited("see exclusive-b.png in the second tile", [view("exclusive-b")], [view("a-1")])
        self.assertEqual(found, [view("exclusive-b")])
        self.assertEqual(results.cited("see same.png", ["views/same.png"], ["other/same.png"]), [], "a held view has that name")
        self.assertEqual(results.cited("nothing here", [view("exclusive-b")], []), [])

    def test_a_foreign_views_name_is_matched_as_a_whole_name_so_a_held_view_that_ends_with_it_is_not_a_citation(self):
        self.assertEqual(results.cited("see x-layer.png in the second tile", ["views/layer.png"], ["views/x-layer.png"]), [],
                         "the held view's name ends with the foreign one's")
        self.assertEqual(results.cited("see layer.png and x-layer.png", ["views/layer.png"], ["views/x-layer.png"]), ["views/layer.png"],
                         "a foreign name cited on its own is still flagged beside the held one")
        self.assertEqual(results.cited("see (layer.png).", ["views/layer.png"], []), ["views/layer.png"],
                         "a name between punctuation is a citation")
        self.assertEqual(results.cited("see views/layer.png", ["views/layer.png"], ["views/x-layer.png"]), ["views/layer.png"],
                         "the whole name is a citation")


class GroupsAreFormedFromTheUnitsNeeds(unittest.TestCase):
    """The groups are the kit's packing whatever the budget, and the roots are made from them."""

    def tokens(self, declaration, found, units):
        return tokens_of(declaration, found, units)

    def roots(self, result):
        return [list(root.groups) for root in result.built_roots]

    def serving(self, result):
        """The units each root serves, root by root."""
        by_group = {g.id: g.units for g in result.groups}
        return [[unit for group in root.groups for unit in by_group[group]] for root in result.built_roots]

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C15: A test of units with high overlap shows their groups served by one root with a total of all roots' tokens below that of a partition that separates them, a test of units with no overlap shows no view written twice, and in every case the groups equal the kit's packing of the same declaration, and every root is under the budget.
    def test_units_with_high_overlap_are_served_by_one_root_written_once_and_below_a_partition_that_separates_them(self):
        x, y = [f"x{n}" for n in range(30)], [f"y{n}" for n in range(30)]
        units = {"u1": x + ["p1"], "u4": y + ["q1"], "u2": x + ["p2"], "u5": y + ["q2"], "u3": x + ["p3"], "big": ["z"]}
        outputs = {"u1": 100, "u2": 100, "u3": 100, "u4": 100, "u5": 100, "big": 300}
        raw, prepare = synthetic(units, outputs=outputs, budget={"context_tokens": 1_000_000})
        declaration, found, result = formed(self, raw, prepare)
        packed = planner.pack(declaration)
        self.assertGreater(len(packed), 1)
        self.assertEqual([list(g.units) for g in result.groups], packed, "the groups are the kit's packing")
        self.assertEqual(self.roots(result), [[g.id for g in result.groups]], "one root serves every group")
        (root,) = result.built_roots
        whole = self.tokens(declaration, found, list(units))
        self.assertEqual(root.tokens, whole)
        separating = [[u for u in group] for group in packed]
        self.assertLess(root.tokens, sum(self.tokens(declaration, found, part) for part in separating),
                        "the total written is below that of a partition that separates the groups")
        self.assertLessEqual(root.tokens, 1_000_000)

    def test_a_small_design_with_no_budget_declared_shares_one_root_whatever_the_overlap(self):
        units = {"u1": ["a"], "u2": ["b"], "u3": ["c"]}
        raw, prepare = synthetic(units)
        _, _, result = formed(self, raw, prepare)
        self.assertEqual([g.units for g in result.groups], [("u1",), ("u2",), ("u3",)])
        self.assertEqual(self.roots(result), [["G1", "G2", "G3"]])
        self.assertEqual([r.id for r in result.built_roots], ["root"], "one root is named root")
        self.assertEqual([g.root for g in result.groups], ["root"] * 3)
        self.assertEqual(held_names(result.built_roots[0].shared.message), ["guide.md"] + [view(n) for n in "abc"])
        self.assertEqual(result.budget["tokens"], None)

    def test_views_that_force_the_budget_give_several_roots_each_within_it_and_the_groups_are_unchanged(self):
        x, y = [f"x{n}" for n in range(30)], [f"y{n}" for n in range(30)]
        units = {"a1": x + ["p1"], "b1": y + ["q1"], "a2": x + ["p2"], "b2": y + ["q2"]}
        raw, prepare = synthetic(units, outputs={uid: 200 for uid in units})
        declaration, found, unbudgeted = formed(self, raw, prepare)
        self.assertEqual(len(unbudgeted.groups), 4, "outputs of 200 each pack no two together: the cap is the largest single unit's")
        self.assertEqual(len(unbudgeted.built_roots), 1)
        raw["budget"] = {"context_tokens": self.tokens(declaration, found, ["a1", "a2"]) + 20}
        declaration, found, result = formed(self, raw, prepare)
        self.assertEqual([list(g.units) for g in result.groups], planner.pack(declaration), "the groups are the kit's packing")
        self.assertEqual([g.units for g in result.groups], [g.units for g in unbudgeted.groups], "and are the same as with no budget")
        self.assertGreater(self.tokens(declaration, found, list(units)), raw["budget"]["context_tokens"])
        self.assertEqual(self.serving(result), [["a1", "a2"], ["b1", "b2"]], "the units that share views share a root")
        for root in result.built_roots:
            self.assertLessEqual(root.tokens, raw["budget"]["context_tokens"])
            self.assertEqual(root.tokens, messages.measured_size(root.shared.message))
        self.assertEqual([r.id for r in result.built_roots], ["root.R1", "root.R2"])
        self.assertEqual([g.root for g in result.groups], ["root.R1", "root.R2", "root.R1", "root.R2"])

    def test_with_zero_overlap_the_roots_still_merge_since_the_shared_documents_are_written_once_a_root_otherwise(self):
        units = {f"u{n}": [f"v{n}-{k}" for k in range(20)] for n in range(1, 7)}
        raw, prepare = synthetic(units, outputs={uid: 200 for uid in units})
        declaration, found, _ = formed(self, raw, prepare)
        two = self.tokens(declaration, found, ["u1", "u2"])
        raw["budget"] = {"context_tokens": two}
        declaration, _, result = formed(self, raw, prepare)
        self.assertEqual([list(g.units) for g in result.groups], planner.pack(declaration), "the groups equal the kit's packing")
        self.assertEqual(len(result.groups), 6)
        self.assertEqual(self.serving(result), [["u1", "u2"], ["u3", "u4"], ["u5", "u6"]],
                         "no view is shared, only the guide, and that alone merges the pairs, first pairs first")
        seen = [name for root in result.built_roots for name in held_names(root.shared.message)]
        self.assertEqual(sorted(name for name in seen if name != "guide.md"),
                         sorted(view(f"v{n}-{k}") for n in range(1, 7) for k in range(20)), "no view is written twice")
        self.assertEqual(seen.count("guide.md"), 3, "the shared document once for each root, not once for each group")
        self.assertTrue(all(root.tokens <= two for root in result.built_roots))

    def test_zero_overlap_and_a_roomy_budget_share_one_root_and_write_the_shared_documents_once(self):
        units = {"u1": ["a", "b"], "u2": ["c", "d"], "u3": ["e", "f"], "u4": ["g"]}
        raw, prepare = synthetic(units, outputs={"u1": 100, "u2": 100, "u3": 200, "u4": 150}, budget={"context_tokens": 1_000_000})
        declaration, found, result = formed(self, raw, prepare)
        self.assertEqual([list(g.units) for g in result.groups], planner.pack(declaration))
        self.assertEqual([g.units for g in result.groups], [("u1", "u2"), ("u3",), ("u4",)])
        self.assertEqual(self.roots(result), [["G1", "G2", "G3"]])
        raw["budget"] = {}
        _, _, unbudgeted = formed(self, raw, prepare)
        self.assertEqual([g.units for g in unbudgeted.groups], [g.units for g in result.groups], "a budget changes no group")
        self.assertEqual(self.roots(unbudgeted), self.roots(result))
        alone = sum(g.tokens for g in result.groups)
        self.assertEqual(alone - result.built_roots[0].tokens, 2 * messages.root_tokens(found.subset(["guide.md"]).artefacts),
                         "what is saved is the shared document and the fixed text of the two roots one root replaces")

    def test_a_coupled_set_is_never_parted_and_its_root_may_serve_other_groups_when_they_fit(self):
        shared = [f"s{n}" for n in range(10)]
        units = {"u1": shared + ["a"], "u2": shared + ["b"], "u3": shared + ["c"]}
        raw, prepare = synthetic(units, couples=[("u1", "u2")], outputs={"u1": 200, "u2": 200, "u3": 100},
                                 budget={"context_tokens": 1_000_000})
        declaration, _, result = formed(self, raw, prepare)
        self.assertEqual([g.units for g in result.groups], [("u1", "u2"), ("u3",)], "the coupled set is whole and alone in its group")
        self.assertEqual(self.roots(result), [["G1", "G2"]])
        raw["budget"] = {}
        _, _, unbudgeted = formed(self, raw, prepare)
        self.assertEqual([g.units for g in unbudgeted.groups], [("u1", "u2"), ("u3",)])

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C15: roots are merged ... ties by declaration order of the pairs' first groups
    def test_a_tie_in_what_two_merges_save_is_settled_by_the_declaration_order_of_the_pairs_first_groups(self):
        units = {"u1": ["a", "b"], "u2": ["a", "c"], "u3": ["a", "d"]}
        outputs = {uid: 200 for uid in units}
        raw, prepare = synthetic(units, outputs=outputs)
        declaration, found, _ = formed(self, raw, prepare)
        self.assertEqual(declaration.needed.count(view("a")), 1)
        raw["budget"] = {"context_tokens": self.tokens(declaration, found, ["u1", "u2"])}
        _, _, result = formed(self, raw, prepare)
        self.assertEqual(self.serving(result), [["u1", "u2"], ["u3"]], "the three merges save alike, and the first pair's goes first")
        reordered = dict(reversed(list(raw["units"].items())))
        raw["units"] = reordered
        _, _, result = formed(self, raw, prepare)
        self.assertEqual(self.serving(result), [["u3", "u2"], ["u1"]], "declaration order is the new order's")

    def test_the_pair_that_saves_most_is_merged_first_whatever_its_place(self):
        units = {"u1": ["s", "a"], "u2": ["s", "c", "d", "e"], "u3": ["c", "d", "e", "x"]}
        raw, prepare = synthetic(units, docs=(), outputs={uid: 200 for uid in units})
        declaration, found, _ = formed(self, raw, prepare)
        first, second = (self.tokens(declaration, found, pair) for pair in (["u1", "u2"], ["u2", "u3"]))
        self.assertEqual(first, second, "both pairs fit the budget, and not all three")
        raw["budget"] = {"context_tokens": first}
        self.assertGreater(self.tokens(declaration, found, list(units)), first)
        _, _, result = formed(self, raw, prepare)
        self.assertEqual(self.serving(result), [["u1"], ["u2", "u3"]], "the pair sharing three views, not the first two")

    def test_no_root_exceeds_the_budget_after_merging_whatever_the_budget(self):
        views = {f"u{n}": [f"v{k}" for k in range(n, n + 6)] for n in range(1, 9)}
        raw, prepare = synthetic(views, outputs={uid: 200 for uid in views})
        declaration, found, _ = formed(self, raw, prepare)
        alone = max(self.tokens(declaration, found, [uid]) for uid in views)
        everything = self.tokens(declaration, found, list(views))
        for budget in range(alone, everything + 1, max(1, (everything - alone) // 9)):
            with self.subTest(budget=budget):
                raw["budget"] = {"context_tokens": budget}
                _, _, result = formed(self, raw, prepare)
                self.assertEqual([list(g.units) for g in result.groups], planner.pack(declaration))
                self.assertTrue(all(root.tokens <= budget for root in result.built_roots))
                self.assertEqual(sorted(g for root in result.built_roots for g in root.groups), sorted(g.id for g in result.groups),
                                 "every group is served by one root")
                for root in result.built_roots:
                    units_held = [u for g in result.groups if g.id in root.groups for u in g.units]
                    self.assertEqual(root.tokens, self.tokens(declaration, found, units_held))

    def test_units_the_declaration_couples_are_never_parted_and_a_coupled_set_over_the_budget_is_refused_whole(self):
        units = {"u1": ["a"] * 1 + ["b"], "u2": ["c", "d"], "u3": ["e"]}
        raw, prepare = synthetic(units, couples=[("u1", "u2")])
        declaration, found, _ = formed(self, raw, prepare)
        alone = self.tokens(declaration, found, ["u3"])
        raw["budget"] = {"context_tokens": alone + 30}
        with self.assertRaises(planner.GroupsOverBudget) as refused:
            formed(self, raw, prepare)
        self.assertEqual([o.units for o in refused.exception.overruns], [("u1", "u2")])
        self.assertIn("units u1, u2, which the declaration couples", refused.exception.lines[0])

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C2: a group whose own artefacts added to the shared documents measure more than the budget is refused naming the group, its size in tokens and the budget; a group that fits exactly is accepted
    def test_a_group_alone_over_the_budget_is_refused_naming_the_group_its_figures_and_the_budget_and_one_that_fits_exactly_is_not(self):
        units = {"u1": ["a"], "u2": ["b"], "u3": [f"big{n}" for n in range(10)]}
        raw, prepare = synthetic(units, outputs={"u1": 200, "u2": 200, "u3": 200})
        declaration, found, _ = formed(self, raw, prepare)
        big = self.tokens(declaration, found, ["u3"])
        raw["budget"] = {"context_tokens": big}
        formed(self, raw, prepare)
        raw["budget"] = {"context_tokens": big - 1}
        with self.assertRaises(planner.GroupsOverBudget) as refused:
            formed(self, raw, prepare)
        (overrun,) = refused.exception.overruns
        self.assertEqual((overrun.group, overrun.units, overrun.tokens), ("G3", ("u3",), big))
        (line,) = refused.exception.lines
        for part in ("group G3", "unit u3 alone", f"holds {big} tokens", f"budget of {big - 1} tokens", "1 over"):
            self.assertIn(part, line)

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C15: A single unit whose own needs exceed the budget alone is refused naming the unit, its tokens and the budget.
    def test_a_single_unit_over_the_budget_alone_is_refused_naming_the_unit_its_tokens_and_the_budget(self):
        raw, prepare = synthetic({"u1": ["a"], "u2": [f"big{n}" for n in range(30)]})
        declaration, found, _ = formed(self, raw, prepare)
        small = self.tokens(declaration, found, ["u1"])
        big = self.tokens(declaration, found, ["u2"])
        raw["budget"] = {"context_tokens": small + 10}
        with self.assertRaises(planner.GroupsOverBudget) as refused:
            formed(self, raw, prepare)
        (line,) = refused.exception.lines
        self.assertIn("unit u2 alone", line)
        self.assertIn(f"holds {big} tokens", line)
        self.assertIn(f"budget of {small + 10} tokens", line)
        self.assertEqual(refused.exception.budget, small + 10)

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C15: every root is held to the budget of the model's window multiplied by a declared headroom fraction, which is the declared budget of the budget criterion when the caller states the fraction in place of a figure
    def test_every_root_is_held_to_the_window_times_the_headroom_fraction_when_the_caller_states_a_fraction(self):
        units = {"u1": ["a", "b", "c"], "u2": ["d", "e", "f"], "u3": ["g", "h", "i"]}
        raw, prepare = synthetic(units, budget={"context_fraction": 0.001}, outputs={uid: 200 for uid in units})
        _, _, result = formed(self, raw, prepare)
        self.assertEqual(result.budget, {"tokens": 1000, "fraction": 0.001, "window": 1_000_000, "model": "claude-sonnet-5-5"})
        self.assertEqual(len(result.groups), 3)
        self.assertEqual(len(result.built_roots), 3, "no two groups' roots fit the budget together")
        self.assertTrue(all(root.tokens <= 1000 for root in result.built_roots))
        raw["budget"] = {"context_fraction": 0.0005}
        with self.assertRaises(planner.GroupsOverBudget) as refused:
            formed(self, raw, prepare)
        self.assertEqual(refused.exception.budget, 500)


class TheEstimateOfAGroupsRoot(unittest.TestCase):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C11: Over a synthetic declaration, before any session starts, the command estimates each group's root in tokens from the declared images' pixel dimensions and the documents' text, prints the estimate per group, and refuses a group whose estimate exceeds the declared budget, naming the group, the estimate and the budget. A test with images of differing dimensions shows the estimate rises with the pixel count and that two images of the same dimensions are estimated alike.
    def test_the_estimate_rises_with_the_pixel_count_and_equal_dimensions_are_estimated_alike(self):
        units = {"small": ["s"], "same-a": ["m1"], "same-b": ["m2"], "large": ["l"]}
        sizes = {"s": (280, 280), "m1": (560, 560), "m2": (560, 560), "l": (1120, 560)}
        raw, prepare = synthetic(units, sizes=sizes, outputs={uid: 200 for uid in units})
        declaration, found, result = formed(self, raw, prepare)
        tokens = {g.units[0]: g.tokens for g in result.groups}
        self.assertLess(tokens["small"], tokens["same-a"])
        self.assertLess(tokens["same-a"], tokens["large"])
        self.assertEqual(tokens["same-a"], tokens["same-b"])
        document = messages.root_tokens(found.subset(["guide.md"]).artefacts)
        for unit, name, size in (("small", "s", (280, 280)), ("same-a", "m1", (560, 560)), ("large", "l", (1120, 560))):
            image = found.get(view(name))
            self.assertEqual(image.tokens, catalogue.image_tokens(*size), "the image is measured by the patch formula")
            self.assertEqual(tokens[unit], messages.BASE_FRAMING + (document - messages.BASE_FRAMING) + image.tokens + messages.framing_of(image),
                             "the document's text and the image's measure make the estimate")
            self.assertEqual(next(g for g in result.groups if g.units[0] == unit).images, 1)

    def test_the_estimate_is_the_tokens_of_the_message_the_session_is_given(self):
        raw, prepare = synthetic({"u1": ["a", "b"], "u2": ["c"]}, sizes={"a": (700, 300), "b": (96, 1000), "c": (28, 28)},
                                 outputs={"u1": 200, "u2": 200})
        declaration, found, result = formed(self, raw, prepare)
        for root in result.built_roots:
            self.assertEqual(root.tokens, messages.measured_size(root.shared.message))
            self.assertEqual(root.tokens, root.shared.tokens)
        for group in result.groups:
            alone = messages.shared_context(found.subset(group.needs))
            self.assertEqual(group.tokens, messages.measured_size(alone.message), "the estimate is the message the group would be given alone")

    def test_the_estimate_is_printed_for_each_group_and_each_root_in_the_plan_in_text_and_json(self):
        class Plan(base.Case):
            def runTest(self):
                pass
        case = Plan()
        case.setUp()
        try:
            raw, prepare = synthetic({"u1": ["a"], "u2": ["b", "c"]}, sizes={"b": (560, 560)}, outputs={"u1": 200, "u2": 200},
                                     budget={"context_tokens": 100000})
            prepare(case.review)
            case.write_caller(declaration=raw, name="sized")
            status, text, _ = case.run_command("--plan-only", caller="sized", out=os.path.join(case.base, "text"))
            self.assertEqual(status, 0, text)
            status, as_json, _ = case.run_command("--plan-only", caller="sized", out=os.path.join(case.base, "json"), fmt="json")
            self.assertEqual(status, 0, as_json)
            plan = json.loads(as_json)["plan"]
            for group, line in zip(plan["groups"], case.lines(text, "GROUP")):
                self.assertIn(f"| {group['tokens']} tokens alone with the shared documents |", line)
                self.assertGreater(group["tokens"], 0)
            self.assertLess(plan["groups"][0]["tokens"], plan["groups"][1]["tokens"])
            for root, line in zip(plan["roots"], case.lines(text, "ROOT")):
                self.assertIn(f"| {root['tokens']} tokens |", line)
        finally:
            case.doCleanups()


class TheCheckExtractOfAGroup(unittest.TestCase):
    REPORT = "\n".join([
        "DESIGN | board | FAIL",
        "VIOLATION | board | Plated hole spacing | (10, 20) | hole to hole 0.12 mm, under the 0.25 mm minimum",
        "VIOLATION | board | Copper clearance | (30, 40) | clearance 0.18 mm",
        "VIOLATION | board | Plated hole spacing | (11, 21) | hole to hole 0.20 mm, under the 0.25 mm minimum",
        "VIOLATION | board | Pour gap | (50, 60) | gap 1.4 mm",
        "a free line that names no rule"]) + "\n"

    def design(self):
        units = {"u1": ["a"], "u2": ["b"], "u3": ["c"]}
        rules = {"u1": ["Plated hole spacing"], "u2": ["Copper clearance", "Silk overlap"], "u3": ["Pour gap"]}
        return synthetic(units, rules=rules, report=self.REPORT)

    def extract_of(self, root):
        """The text of the extract block of a root: its header line, then the lines held."""
        return next(block["text"] for block in json.loads(root.shared.message)["message"]["content"]
                    if block["type"] == "text" and block["text"].startswith("=== extract/"))

    def roots_by_unit(self, result):
        """The root each unit's group continues, by the unit's name."""
        return {unit: result.root_of(group.id) for group in result.groups for unit in group.units}

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C16: each root holds the extract of that report, the report's own lines for the rules its groups' units declare they judge and no other root's rules
    def test_each_roots_holds_the_reports_own_lines_for_its_groups_rules_and_no_other_roots(self):
        raw, prepare = self.design()
        raw = apart(self, raw, prepare)
        declaration, found, result = formed(self, raw, prepare)
        self.assertEqual(len(result.built_roots), 3, "the budget gives each group a root of its own")
        by_unit = self.roots_by_unit(result)
        first = self.extract_of(by_unit["u1"])
        self.assertIn("=== extract/check-report.txt ===", json.dumps(json.loads(by_unit["u1"].shared.message)))
        self.assertEqual(first.split("\n", 1)[1].splitlines(),
                         [line for line in self.REPORT.splitlines() if "Plated hole spacing" in line])
        self.assertIn("hole to hole 0.12 mm", first, "the extract carries the check's own figure for the rule")
        self.assertIn("0.20 mm", first)
        self.assertNotIn("Copper clearance", first)
        self.assertNotIn("Pour gap", first)
        second = self.extract_of(by_unit["u2"])
        self.assertIn("clearance 0.18 mm", second)
        self.assertNotIn("Plated hole spacing", second)
        third = self.extract_of(by_unit["u3"])
        self.assertEqual(third.split("\n", 1)[1].strip(), "VIOLATION | board | Pour gap | (50, 60) | gap 1.4 mm")

    def test_a_figure_the_report_did_not_carry_is_not_in_the_extract_and_a_line_naming_no_rule_is_left_out(self):
        raw, prepare = self.design()
        raw = apart(self, raw, prepare)
        _, _, result = formed(self, raw, prepare)
        everything = " ".join(self.extract_of(root) for root in result.built_roots)
        for absent in ("0.07", "DESIGN | board", "a free line"):
            self.assertNotIn(absent, everything)
        report_figures = set(re.findall(r"\d+\.\d+", self.REPORT))
        self.assertLessEqual(set(re.findall(r"\d+\.\d+", everything)), report_figures)

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C16: a unit whose declared rule has no line in the report is flagged in the plan naming the unit and the rule, informationally and without refusing
    def test_a_declared_rule_with_no_line_is_flagged_in_the_plan_naming_the_unit_and_the_rule_without_refusing(self):
        raw, prepare = self.design()
        harness = fx.Harness(self, raw=raw, prepare=prepare)
        by_unit = {g.units[0]: g for g in harness.plan.groups}
        self.assertEqual(by_unit["u2"].extract["missing"], [{"unit": "u2", "rule": "Silk overlap"}])
        self.assertEqual(by_unit["u1"].extract["missing"], [])
        self.assertEqual(by_unit["u1"].extract["lines"], 2)
        self.assertEqual(by_unit["u2"].extract["rules"], ["Copper clearance", "Silk overlap"])
        self.assertIn("holds no line for the rules: Silk overlap", self.extract_of(harness.formed.root_of("G2")))
        harness.fresh()

    def test_a_root_serving_several_groups_holds_the_extract_of_the_rules_of_all_their_units(self):
        # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C16: each root holds the extract of that report, the report's own lines for the rules its groups' units declare they judge
        raw, prepare = self.design()
        _, _, result = formed(self, raw, prepare)
        (root,) = result.built_roots
        self.assertEqual(root.groups, ("G1", "G2", "G3"))
        held = self.extract_of(root)
        for line in self.REPORT.splitlines()[1:5]:
            self.assertIn(line, held)
        self.assertEqual({g.units[0]: g.extract["rules"] for g in result.groups},
                         {"u1": ["Plated hole spacing"], "u2": ["Copper clearance", "Silk overlap"], "u3": ["Pour gap"]},
                         "each group's own rules are in the plan")

    def test_the_flag_and_the_extract_are_in_the_text_and_json_report_of_the_plan(self):
        class Plan(base.Case):
            def runTest(self):
                pass
        case = Plan()
        case.setUp()
        try:
            raw, prepare = self.design()
            prepare(case.review)
            case.write_caller(declaration=raw, name="extracting")
            status, out, err = case.run_command("--plan-only", caller="extracting", fmt="json")
            self.assertEqual((status, err), (0, ""), out)
            groups = {g["units"][0]: g for g in json.loads(out)["plan"]["groups"]}
            self.assertEqual(groups["u2"]["extract"]["missing"], [{"unit": "u2", "rule": "Silk overlap"}])
            status, out, err = case.run_command("--plan-only", caller="extracting", out=os.path.join(case.base, "text"))
            self.assertEqual((status, err), (0, ""), out)
            self.assertIn("NOTE | unit u2 declares the rule Silk overlap, which the check's report holds no line for", out)
            self.assertIn("EXTRACT | G1 | rules Plated hole spacing | 2 lines of the check's report", out)
        finally:
            case.doCleanups()

    def test_the_declaration_is_refused_for_rules_with_no_report_a_report_a_unit_needs_or_a_pattern_without_a_rule(self):
        raw, _ = self.design()
        text = lambda changed: "\n".join(self.refused(changed).lines)  # noqa: E731
        without = json.loads(json.dumps(raw))
        del without["check_extract"]
        self.assertIn("declares check_rules and the declaration has no `check_extract`", text(without))
        needed = json.loads(json.dumps(raw))
        needed["units"]["u1"]["needs"].append("check-report.txt")
        self.assertIn("no unit needs the report itself", text(needed))
        pattern = json.loads(json.dumps(raw))
        pattern["check_extract"]["rule"] = r"^VIOLATION \| (?P<other>[^|]+)"
        self.assertIn("has no `rule` group", text(pattern))
        broken = json.loads(json.dumps(raw))
        broken["check_extract"]["rule"] = "("
        self.assertIn("does not compile", text(broken))
        missing = json.loads(json.dumps(raw))
        missing["check_extract"]["report"] = "nowhere.txt"
        self.assertIn("which is not an artefact of the declaration", text(missing))
        image = json.loads(json.dumps(raw))
        image["artefacts"]["check-report.txt"]["kind"] = "image"
        self.assertIn("which is a image, not a text", text(image))
        rules = json.loads(json.dumps(raw))
        rules["units"]["u1"]["check_rules"] = ["a", "a"]
        self.assertIn("not a list of distinct rule names", text(rules))

    def refused(self, raw):
        with self.assertRaises(decl.DeclarationError) as caught:
            parsed(raw)
        return caught.exception


class ReplicasShareTheirRoot(unittest.TestCase):
    def design(self):
        """Three groups of five views each, and a budget two groups' views fit within and three groups' do not: two roots."""
        units = {f"u{n}": [f"v{n}-{k}" for k in range(5)] for n in range(1, 4)}
        raw, prepare = synthetic(units, outputs={uid: 200 for uid in units})
        declaration, found, _ = formed(self, raw, prepare)
        raw["budget"] = {"context_tokens": tokens_of(declaration, found, ["u1", "u2"])}
        return raw, prepare, declaration, found

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C17: Over a synthetic declaration, replicas of a group are each started from the root that holds that group's views, and the plan's total of tokens written counts each root once, not once per group served and not once per replica.
    def test_replicas_are_started_from_the_root_holding_their_groups_views_and_each_root_is_counted_once_in_the_tokens_written(self):
        raw, prepare, declaration, found = self.design()
        sizes = {"root.R1": tokens_of(declaration, found, ["u1", "u2"]), "root.R2": tokens_of(declaration, found, ["u3"])}
        totals = {}
        for replicas in (1, 3):
            harness = fx.Harness(self, raw=raw, prepare=prepare, replicas=replicas, variants=["full", "hunt", "terse"])
            plan = harness.plan
            self.assertEqual([(r.id, r.groups) for r in plan.root_records], [("root.R1", ("G1", "G2")), ("root.R2", ("G3",))])
            written = plan.predicted["tokens_written"]
            self.assertEqual(written, sum(sizes.values()), "each root once, not once for each group it serves")
            totals[replicas] = written
            forks = [n for n in plan.nodes if n.role == planner.UNIT]
            self.assertEqual(len(forks), 3 * replicas)
            self.assertTrue(all(n.parent == plan.root_of(n.group).id for n in forks), "each fork continues the root holding its group's views")
            for root_id, size in sizes.items():
                self.assertEqual(plan.predicted["per_node"][root_id]["cost_usd"],
                                 round(planner.cm.root_cost(planner.cm.Prices(), size), 6), "one root cost for each root")
        self.assertEqual(totals[1], totals[3], "more replicas read the roots and write none")

    def test_a_root_serving_two_groups_is_started_once_and_both_groups_forks_continue_its_one_session(self):
        # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: replicas of a group each started from the root that holds that group's views and no session started from another session
        raw, prepare, _, _ = self.design()
        harness = fx.Harness(self, raw=raw, prepare=prepare, replicas=2, variants=["full", "hunt"])
        harness.fresh()
        calls = harness.executor.calls
        sessions = {call.label: session for session, call in zip(harness.executor.sessions, calls)}
        self.assertEqual([c.label for c in calls if c.label.startswith("root")], ["root.R1", "root.R2"], "each root once")
        for group in ("G1", "G2"):
            self.assertEqual({c.parent for c in calls if c.label.startswith(group + ".")}, {sessions["root.R1"]}, group)
        self.assertEqual({c.parent for c in calls if c.label.startswith("G3.")}, {sessions["root.R2"]})


class EachGroupIsJudgedFromTheRootHoldingItsViews(unittest.TestCase):
    def design(self):
        units = {f"u{n}": [f"g{n}-{k}" for k in range(12)] + ["common"] for n in range(1, 4)}
        raw, prepare = synthetic(units)
        declaration, found, _ = formed(self, raw, prepare)
        one = messages.root_tokens(found.subset(declaration.units["u1"].needs).artefacts)
        raw["budget"] = {"context_tokens": int(one * 1.4)}
        return raw, prepare

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: Over a synthetic review folder of generic units in at least three groups, each unit declaring its own subset of views, the plan gives every group a flat root that holds its views, one root serving several groups when their views fit the budget together, and the stub's record of what each session received shows the groups' sessions started in parallel, replicas of a group each started from the root that holds that group's views and no session started from another session.
    def test_the_roots_are_started_in_parallel_and_replicas_continue_the_root_holding_their_groups_views(self):
        raw, prepare = self.design()
        rendezvous = threading.Barrier(3, timeout=10)

        class Together(ex.StubExecutor):
            def execute(self, call):
                if call.label.startswith("root"):
                    rendezvous.wait()
                return super().execute(call)

        harness = fx.Harness(self, raw=raw, prepare=prepare, replicas=2, variants=["full", "hunt"], executor_class=Together,
                             concurrency=scheduler.ThreadedConcurrency(), bound=6)
        plan = harness.plan
        self.assertEqual(len(plan.groups), 3)
        self.assertEqual([n.id for n in plan.roots], ["root.R1", "root.R2", "root.R3"], "the views fill a root each")
        self.assertEqual([r.groups for r in plan.root_records], [("G1",), ("G2",), ("G3",)])
        self.assertEqual(len({harness.roots[g.root].prefix_sha for g in plan.groups}), 3, "each root is its own context")
        harness.fresh()
        calls = harness.executor.calls
        self.assertEqual(len([c for c in calls if c.label.startswith("root")]), 3)
        self.assertTrue(all(c.label.startswith("root") for c in calls[:3]), "every root is started before any fork, together")
        sessions = {call.label: session for session, call in zip(harness.executor.sessions, calls)}
        for call in calls:
            if call.label.startswith("root"):
                self.assertIsNone(call.parent)
            else:
                self.assertEqual(call.parent, sessions[plan.root_of(call.label.split(".")[0]).id])
                self.assertNotIn(call.parent, [s for s, c in zip(harness.executor.sessions, calls) if not c.label.startswith("root")],
                                 "no session is started from another session")
        self.assertEqual(len([c for c in calls if c.fork]), 6)

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: Each group's results are merged into one pass holding exactly one verdict row per checklist item; a checklist item with no row, with two rows, or with a row from a group that does not hold the item's unit is refused each refused by the merge naming the item, and a fail raised by any replica stands in the merged pass.
    def test_the_merged_pass_holds_one_verdict_row_for_each_item_and_a_fail_by_any_replica_stands(self):
        raw, prepare = self.design()
        harness = fx.Harness(self, raw=raw, prepare=prepare, replicas=2, variants=["full", "hunt"])
        failing = fx.good_answer(harness.declaration, ["u2"], "pass")
        failing["tables"]["Verdicts"][0]["Verdict"] = "fail"
        failing["tables"]["Findings"] = [{"No": 1, "Item": "u2-i1", "Detail": "seen"}]
        harness.script["G2.r2.a1"] = ex.Reply(structured=failing, text="x")
        record = harness.fresh()
        shape = harness.declaration.shape
        rules = merge.Rules(checklist=tuple(i for u in harness.declaration.units.values() for i in u.items))
        units = {lane["group"]: {} for lane in record["lanes"]}
        for lane in record["lanes"]:
            attempt = lane["record"]["attempts"][lane["record"]["standing"]]
            units[lane["group"]][f"r{lane['replica']}"] = attempt["tables"]
        holds = {g.id: [i for u in g.units for i in harness.declaration.units[u].items] for g in harness.plan.groups}
        merged = merge.merge(shape, rules, [g.id for g in harness.plan.groups], units, None, holds)
        verdicts = [row["Item"] for row in merged["tables"]["Verdicts"]["rows"]]
        self.assertEqual(sorted(verdicts), sorted(i for items in holds.values() for i in items), "one row for each item")
        row = next(r for r in merged["tables"]["Verdicts"]["rows"] if r["Item"] == "u2-i1")
        self.assertEqual(row["Verdict"], "fail", "a fail raised by one replica stands")

        def refused(changed):
            with self.assertRaises(merge.Refused) as caught:
                merge.merge(shape, rules, [g.id for g in harness.plan.groups], changed, None, holds)
            return caught.exception.causes

        def copy():
            return json.loads(json.dumps(units))

        missing = copy()
        missing["G1"]["r1"]["Verdicts"] = [r for r in missing["G1"]["r1"]["Verdicts"] if r["Item"] != "u1-i2"]
        self.assertEqual([c for c in refused(missing) if "u1-i2" in c], ["group G1 replica r1 gives no verdict row for the checklist item "
                                                                         "'u1-i2'; each item has one"])
        twice = copy()
        twice["G3"]["r2"]["Verdicts"].append(dict(twice["G3"]["r2"]["Verdicts"][0]))
        self.assertIn("group G3 replica r2 gives 2 verdict rows for the checklist item 'u3-i1'; each item has one", refused(twice))
        foreign = copy()
        foreign["G1"]["r2"]["Verdicts"].append({"Item": "u3-i2", "Verdict": "pass", "Note": ""})
        self.assertIn("group G1 replica r2 gives a verdict row for the checklist item 'u3-i2', which is no item of the units its group "
                      "holds", refused(foreign))
        self.assertEqual(merge.merge(shape, rules, [g.id for g in harness.plan.groups], units)["tables"]["Verdicts"]["rows"],
                         merged["tables"]["Verdicts"]["rows"], "without `holds` the merge reads what it did")

    def merge_inputs(self):
        raw, prepare = self.design()
        harness = fx.Harness(self, raw=raw, prepare=prepare, replicas=2, variants=["full", "hunt"])
        record = harness.fresh()
        units = {lane["group"]: {} for lane in record["lanes"]}
        for lane in record["lanes"]:
            attempt = lane["record"]["attempts"][lane["record"]["standing"]]
            units[lane["group"]][f"r{lane['replica']}"] = attempt["tables"]
        holds = {g.id: [i for u in g.units for i in harness.declaration.units[u].items] for g in harness.plan.groups}
        return harness.declaration.shape, [g.id for g in harness.plan.groups], units, holds

    def causes(self, rules, order, shape, units, holds):
        with self.assertRaises(merge.Refused) as caught:
            merge.merge(shape, rules, order, units, None, holds)
        return caught.exception.causes

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: Each group's results are merged into one pass holding exactly one verdict row per checklist item; a checklist item with no row, with two rows, or with a row from a group that does not hold the item's unit is refused each refused by the merge naming the item, and a fail raised by any replica stands in the merged pass.
    def test_a_checklist_item_no_group_holds_and_an_item_two_groups_hold_are_refused_naming_the_item(self):
        shape, order, units, holds = self.merge_inputs()
        every = tuple(i for items in holds.values() for i in items)
        ghost = self.causes(merge.Rules(checklist=every + ("ghost-1",)), order, shape, units, holds)
        self.assertEqual([c for c in ghost if "ghost-1" in c], ["the checklist item 'ghost-1' is held by no group's units, so no group "
                                                                "gives it a verdict row; each item has one"])
        twice = {**holds, "G2": holds["G2"] + [holds["G1"][0]]}
        shared = self.causes(merge.Rules(checklist=every), order, shape, units, twice)
        self.assertEqual([c for c in shared if holds["G1"][0] in c and "groups" in c],
                         [f"the checklist item {holds['G1'][0]!r} is held by the units of 2 groups (G1, G2); each item is held by one group"])

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: Each group's results are merged into one pass holding exactly one verdict row per checklist item; a checklist item with no row, with two rows, or with a row from a group that does not hold the item's unit is refused each refused by the merge naming the item, and a fail raised by any replica stands in the merged pass.
    def test_an_empty_checklist_expects_the_items_the_groups_hold(self):
        shape, order, units, holds = self.merge_inputs()
        rules = merge.Rules(checklist=())
        rows = merge.merge(shape, rules, order, units, None, holds)["tables"]["Verdicts"]["rows"]
        self.assertEqual(sorted(r["Item"] for r in rows), sorted(i for items in holds.values() for i in items))
        short = json.loads(json.dumps(units))
        short["G2"]["r1"]["Verdicts"] = short["G2"]["r1"]["Verdicts"][1:]
        self.assertEqual(len(self.causes(rules, order, shape, short, holds)), 1)
        twice = {**holds, "G2": holds["G2"] + [holds["G1"][0]]}
        self.assertTrue([c for c in self.causes(rules, order, shape, units, twice) if "2 groups" in c])

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: Each group's results are merged into one pass holding exactly one verdict row per checklist item; a checklist item with no row, with two rows, or with a row from a group that does not hold the item's unit is refused each refused by the merge naming the item, and a fail raised by any replica stands in the merged pass.
    def test_a_custom_checklist_item_no_unit_holds_is_refused_by_the_command_in_text_and_in_json(self):
        class Run(base.Case):
            def runTest(self):
                pass
        case = Run()
        case.setUp()
        try:
            raw, prepare = self.design()
            prepare(case.review)
            items = [f"u{n}-i{k}" for n in range(1, 4) for k in (1, 2)]
            case.write_caller(declaration=raw, name="three", extra=f"\n\ndef checklist(review_folder):\n    return {items + ['ghost-1']!r}\n")
            status, text, _ = case.run_command(caller="three")
            self.assertEqual(status, 1, text)
            self.assertEqual(len([l for l in case.lines(text, "REFUSED") if "'ghost-1'" in l and "held by no group" in l]), 1, text)
            status, as_json, _ = case.run_command(caller="three", out=os.path.join(case.base, "json"), fmt="json")
            report = json.loads(as_json)
            self.assertEqual(status, 1)
            self.assertEqual(report["result"], "REFUSED")
            self.assertEqual(len([c for c in report["refusals"] if "'ghost-1'" in c and "held by no group" in c]), 1)
        finally:
            case.doCleanups()

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: Each group's results are merged into one pass holding exactly one verdict row per checklist item; a checklist item with no row, with two rows, or with a row from a group that does not hold the item's unit is refused each refused by the merge naming the item, and a fail raised by any replica stands in the merged pass.
    def test_a_shape_with_no_verdict_table_keyed_by_item_has_no_row_to_count(self):
        shape, order, units, holds = self.merge_inputs()
        bare = dataclasses.replace(shape, tables=tuple(dataclasses.replace(t, key=None) for t in shape.tables))
        self.assertEqual(merge.coverage_problems(bare, merge.Rules(checklist=("ghost-1",)), order, units, holds), [])

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: The plan, a run and the merged record are produced in text and in JSON.
    def test_the_plan_a_run_and_the_merged_record_are_produced_in_text_and_in_json(self):
        class Run(base.Case):
            def runTest(self):
                pass
        case = Run()
        case.setUp()
        try:
            raw, prepare = self.design()
            prepare(case.review)
            case.write_caller(declaration=raw, name="three")
            status, text, err = case.run_command(caller="three")
            self.assertEqual((status, err), (0, ""), text)
            status, as_json, err = case.run_command(caller="three", out=os.path.join(case.base, "json"), fmt="json")
            self.assertEqual((status, err), (0, ""))
            report = json.loads(as_json)
            self.assertEqual(report["result"], "WRITTEN")
            self.assertEqual(len(report["plan"]["groups"]), 3)
            self.assertEqual([line.split(" | ")[1] for line in case.lines(text, "GROUP")], [g["id"] for g in report["plan"]["groups"]])
            rows = [row["Item"] for row in report["tables"]["Verdicts"]["rows"]]
            self.assertEqual(len(rows), len(set(rows)), "one verdict row for each item")
            self.assertEqual(len(case.lines(text, "ROW | Verdicts")), len(rows), "the same rows in the text")
            self.assertEqual(len(case.lines(text, "SESSION | root.")), 3)
            self.assertEqual([line.split(" | ")[1] for line in case.lines(text, "ROOT")], [r["id"] for r in report["plan"]["roots"]])
        finally:
            case.doCleanups()


class FiveHundredSixtyViews(unittest.TestCase):
    BIG = (1792, 1792)

    def design(self, every=False):
        names = [f"t{n:03d}" for n in range(560)]
        units = {}
        for group in range(6):
            for part in range(2):
                start = group * 90 + part * 20
                units[f"g{group}u{part}"] = names if every else names[start:start + 20]
        couples = [(f"g{g}u0", f"g{g}u1") for g in range(6)]
        sizes = {name: self.BIG for name in names}
        raw, prepare = synthetic(units, sizes=sizes, couples=couples, budget={"context_tokens": 200000}, spare=names)
        return raw, prepare

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C4: Over a synthetic tempdir design of generic units with five hundred and sixty views, in the sizes of the full-size board's critical-routing folder, grouped in six groups, each declaring a subset of the views, against the stub with a declared budget of two hundred thousand tokens, each group's views measured by the kit's existing token measure, the plan is accepted, the run completes, and the largest context any session was given, measured from the stub's record of the message each session received, is no greater than the budget; the same design with every unit declaring every view is refused naming the groups over the budget.
    def test_a_design_of_five_hundred_and_sixty_views_plans_and_runs_with_no_session_over_the_budget(self):
        raw, prepare = self.design()
        views = [n for n, entry in raw["artefacts"].items() if entry["kind"] == "image"]
        self.assertEqual(len(views), 560)
        harness = fx.Harness(self, raw=raw, prepare=prepare, replicas=2, variants=["full", "hunt"],
                             concurrency=scheduler.SerialConcurrency())
        plan = harness.plan
        self.assertEqual(len(plan.groups), 6)
        self.assertEqual(catalogue.image_tokens(*self.BIG), 4260, "about 4.4 thousand tokens an image, the full-size board's")
        self.assertTrue(all(g.tokens <= 200000 and g.images == 40 for g in plan.groups), [(g.tokens, g.images) for g in plan.groups])
        self.assertEqual([r.groups for r in plan.root_records], [(g.id,) for g in plan.groups],
                         "the groups' views are disjoint and two groups' together are over the budget: a root each")
        self.assertTrue(all(r.tokens <= 200000 and r.images == 40 for r in plan.root_records))
        record = harness.fresh()
        self.assertEqual(record["units"].keys(), raw["units"].keys())
        self.assertFalse(any(state["failed"] for state in record["units"].values()))
        by_session = dict(zip(harness.executor.sessions, harness.executor.calls))
        largest = 0
        for call in harness.executor.calls:
            context = messages.measured_size(call.message)
            if call.fork or call.parent is not None:
                parent = by_session[call.parent]
                while parent.parent is not None:
                    context += messages.measured_size(parent.message)
                    parent = by_session[parent.parent]
                context += messages.measured_size(parent.message)
            largest = max(largest, context)
        self.assertGreater(largest, 100000, "the sessions hold the views")
        self.assertLessEqual(largest, 200000)

    def test_the_same_design_with_every_unit_declaring_every_view_is_refused_naming_the_groups_over_the_budget(self):
        raw, prepare = self.design(every=True)
        with self.assertRaises(planner.OverBudget) as refused:
            formed(self, raw, prepare)
        lines = refused.exception.lines
        self.assertIn("the shared documents", lines[0])
        self.assertEqual([line.split(" (")[0] for line in lines[1:]], [f"group G{n}" for n in range(1, 7)], lines)
        self.assertTrue(all("more than the review's context budget of 200000 tokens" in line for line in lines[1:]))


class TheFannedRunUnderTheProof(unittest.TestCase):
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C12: A test over a synthetic declaration proves that each root holds only the views its groups' units declare, and that the plan of a fanned-out run over the roots records each root's own prefix hash and size, differing from the single form's root prefix hash and from every other root's, that recording such a run adds it to the proof's run record under the form fanned, and that no baseline is edited and every existing baseline refusal still holds.
    def test_the_fanned_plan_records_each_roots_own_prefix_and_the_run_is_recorded_as_fanned_beside_untouched_baselines(self):
        raw, prepare = synthetic({"u1": ["a", "b"], "u2": ["c"], "u3": ["d", "e"]}, outputs={"u1": 200, "u2": 200, "u3": 200})
        raw = apart(self, raw, prepare)
        harness = fx.Harness(self, raw=raw, prepare=prepare)
        self.assertEqual(len(harness.plan.root_records), 3, "the budget gives each group's views a root")
        found = catalogue.admit(harness.declaration, harness.review, results_folder=harness.out)

        unbudgeted = dataclasses.replace(harness.declaration, budget=decl.Budget())

        def plan(form):
            """The single forms hold every view in one session, which the budget the fanned form is held to would refuse."""
            return proof.form_plan(form, harness.declaration if form == proof.FANNED else unbudgeted, found, harness.spec, bound=4,
                                   cli_version="9.9.9", tool_commit="abc1234")

        fanned = plan(proof.FANNED)
        for root in fanned.plan.root_records:
            units = [u for g in fanned.plan.groups if g.id in root.groups for u in g.units]
            self.assertEqual(held_names(fanned.roots[root.id].message), declared(raw, units))
        single_shared = plan(proof.SINGLE_SHARED)
        hashes = [root.prefix_sha for root in fanned.plan.root_records]
        self.assertEqual(len(set(hashes)), len(hashes), "each root's prefix hash differs from every other root's")
        self.assertTrue(all(h != single_shared.plan.root_records[0].prefix_sha for h in hashes),
                        "and from the single form's one root")
        recorded = fanned.plan.to_dict()["roots"]
        self.assertEqual([(r["prefix_sha"], r["tokens"]) for r in recorded],
                         [(fanned.roots[r.id].prefix_sha, fanned.roots[r.id].tokens) for r in fanned.plan.root_records],
                         "the plan record carries each root's prefix hash and size")
        self.assertTrue(all(r["tokens"] > 0 for r in recorded))
        outcome = self.fanned_run(harness, fanned)
        self.assertEqual(outcome.form, proof.FANNED, "the run is recorded under the form fanned")
        single = proof_tests.singles()[0]
        recorded = proof.build_record([{"id": "S1", "item": "u1-i1"}], [single], [outcome], 2.0)
        self.assertEqual([run["id"] for run in recorded["fanned_runs"]], [outcome.id], "the run is in the proof's fanned runs")
        self.assertEqual([run["form"] for run in recorded["fanned_runs"]], [proof.FANNED])
        self.assertNotIn(outcome.id, [run["id"] for run in recorded["single_runs"]], "and not among the single runs")
        self.assertNotIn(proof.FANNED, proof.BASELINE_FORMS, "no baseline key is made for it")
        seeds = [{"id": "S1", "item": "u1-i1"}]
        keys = {form: proof.BaselineKey(proof.seed_list_hash(seeds), "design-sha", "claude-sonnet-5-5", form,
                                        plan(form).plan.nodes[-1].message_sha)
                for form in (proof.SINGLE, proof.SINGLE_SHARED)}
        store = proof.BaselineStore()
        store.add(keys[proof.SINGLE], proof_tests.singles()[0])
        store.add(keys[proof.SINGLE_SHARED], proof_tests.run("shared", form=proof.SINGLE_SHARED))
        before = {key: [r.as_dict() for r in runs] for key, runs in store.runs.items()}
        for baseline in (proof.SINGLE, proof.SINGLE_SHARED):
            with self.assertRaises(proof.BaselineRecorded):
                store.refuse_if_recorded(keys[baseline])
        with self.assertRaises(proof.ProofError):
            store.add(keys[proof.SINGLE], outcome)
        self.assertEqual({key: [r.as_dict() for r in runs] for key, runs in store.runs.items()}, before, "no baseline is edited")

    def test_a_small_design_over_the_fanned_form_is_one_root_with_the_prefix_hash_the_single_shared_form_has_when_it_holds_the_same_views(self):
        # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C12: the plan of a fanned-out run records each root's own prefix hash and size
        raw, prepare = synthetic({"u1": ["a", "b"], "u2": ["c"], "u3": ["d", "e"]}, outputs={"u1": 200, "u2": 200, "u3": 200})
        harness = fx.Harness(self, raw=raw, prepare=prepare)
        found = catalogue.admit(harness.declaration, harness.review, results_folder=harness.out)
        fanned = proof.form_plan(proof.FANNED, harness.declaration, found, harness.spec, bound=4, cli_version="9.9.9", tool_commit="abc1234")
        shared = proof.form_plan(proof.SINGLE_SHARED, harness.declaration, found, harness.spec, bound=4, cli_version="9.9.9",
                                 tool_commit="abc1234")
        self.assertEqual(len(fanned.plan.groups), 3)
        self.assertEqual([r.id for r in fanned.plan.root_records], ["root"], "the groups' views fit one root together")
        self.assertEqual(fanned.plan.root_records[0].prefix_sha, shared.plan.root_records[0].prefix_sha)
        self.assertEqual(fanned.plan.root_records[0].tokens, shared.plan.root_records[0].tokens)

    def fanned_run(self, harness, fanned):
        """The fanned form played on the stub and recorded in the proof's shape."""
        declaration = harness.declaration

        def reply(call, number):
            if call.label.startswith("root"):
                return ex.Reply(text="ack", write=100)
            group = next(g for g in fanned.plan.groups if g.id == call.label.split(".")[0])
            return ex.Reply(structured=fx.good_answer(declaration, list(group.units)), text="done")

        executor = ex.StubExecutor(replies=reply, clock=harness.clock, policy=harness.policy)
        runner = scheduler.Scheduler(executor, harness.clock, scheduler.SerialConcurrency(), 1)
        result = proof.run_form(runner, fanned, harness.spec)
        figures = [proof_tests.RunsRecordedInOneShape.figures(None, "only", 1, 0.1)]
        return proof.outcome_from_run("f1", fanned, result, figures, [{"id": "S1", "item": "u1-i1"}],
                                      lambda seed, row: row.get("Item") == seed["item"], seeded_commit="seeded-1")


if __name__ == "__main__":
    unittest.main()
