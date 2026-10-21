#!/usr/bin/env python3
"""The review kit's caller contract: the module a review's caller supplies, its optional attributes, and the files it renders.

Synthetic caller modules written to temporary folders; no real caller, no session.
"""

from __future__ import annotations

import json
import os
import string
import sys
import tempfile
import textwrap
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import caller, merge  # noqa: E402

PARTS = {
    "declaration": "import json\nDECLARATION = json.loads({declaration!r})\ndeclaration = DECLARATION\n",
    "checks": "def checks(tables):\n    return []\n",
    "render": "def render(review_folder, tables):\n    return {{}}\n",
}


def write_caller(folder, name="demo", extra="", declaration=None, drop=()):
    """A caller module with the required attributes but those dropped, and `extra` source after them."""
    head = "import json\nDECLARATION = json.loads({declaration!r})\n".format(declaration=json.dumps(declaration or fx.declaration_dict()))
    body = "".join(PARTS[part] for part in ("checks", "render") if part not in drop)
    if "declaration" not in drop:
        body += "declaration = DECLARATION\n"
    path = os.path.join(folder, f"review_caller_{name}.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(head + body + textwrap.dedent(extra))
    return path


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.callers = os.path.join(self.tmp.name, "callers")
        os.makedirs(self.callers)
        self.review = fx.review_folder(os.path.join(self.tmp.name, "review"))

    def load(self, extra="", **kwargs):
        write_caller(self.callers, extra=extra, **kwargs)
        return caller.load("demo", self.callers)

    def refused(self, call, *args):
        with self.assertRaises(merge.Refused) as caught:
            call(*args)
        return "\n".join(caught.exception.causes)


class Loading(Case):
    # SOL-HW-REVIEW-KIT.C13: a module missing a required attribute is refused at load naming it
    def test_a_module_missing_a_required_attribute_is_refused_at_load_naming_it_and_the_caller(self):
        for attribute in caller.REQUIRED:
            write_caller(self.callers, drop=(attribute,))
            text = self.refused(caller.load, "demo", self.callers)
            self.assertIn(f"lacks the attribute {attribute}", text)
            self.assertIn("the caller demo", text)

    def test_a_module_lacking_several_required_attributes_names_each(self):
        write_caller(self.callers, drop=("checks", "render"))
        text = self.refused(caller.load, "demo", self.callers)
        self.assertIn("lacks the attribute checks", text)
        self.assertIn("lacks the attribute render", text)

    def test_a_module_that_breaks_an_attribute_is_refused_naming_it(self):
        cases = [("checks = 5", "checks"), ("render = lambda only_one: {}", "render"), ("checks = lambda: []", "checks"),
                 ("retrieval = ['Read', 'Bash']", "retrieval"), ("retrieval = ['Read', 'Read']", "retrieval"), ("retrieval = []", "retrieval"),
                 ("retrieval = 'WebFetch'", "retrieval"), ("checklist = ['a', 'a']", "checklist"), ("checklist = [1]", "checklist"),
                 ("checklist = lambda: ['a']", "checklist"), ("prompt = 'text'", "prompt"), ("prompt = lambda a, b, c: ''", "prompt"),
                 ("place = 3", "place"), ("round_label = lambda: 'r'", "round_label"), ("declaration = 7", "declaration"),
                 ("declaration = lambda: {}", "declaration")]
        for source, attribute in cases:
            text = self.refused(lambda s=source: self.load(s))
            self.assertIn(f"gives {attribute} that", text, source)
            self.assertIn("the caller demo", text, source)

    def test_a_module_that_does_not_import_a_missing_file_and_a_bad_name_are_refused(self):
        with open(os.path.join(self.callers, "review_caller_bad.py"), "w") as handle:
            handle.write("raise RuntimeError('boom')\n")
        self.assertIn("cannot be loaded (RuntimeError: boom)", self.refused(caller.load, "bad", self.callers))
        self.assertIn("there is no caller module", self.refused(caller.load, "absent", self.callers))
        self.assertIn("not a lower-case name", self.refused(caller.load, "../x", self.callers))
        self.assertIn("not a lower-case name", self.refused(caller.load, "Demo", self.callers))

    # SOL-HW-REVIEW-KIT.C13: a caller name with a trailing line break is not a lower-case name and is refused
    def test_a_caller_name_with_a_trailing_line_break_is_refused(self):
        with open(os.path.join(self.callers, "review_caller_a.py"), "w") as handle:
            handle.write("raise RuntimeError('boom')\n")
        for name in ("a\n", "a\n\n", "\na"):
            self.assertIn("not a lower-case name", self.refused(caller.load, name, self.callers), repr(name))

    def test_a_good_module_loads_and_a_declaration_can_be_given_four_ways(self):
        self.assertEqual(sorted(self.load().prepare(self.review).declaration.units), ["u1", "u2", "u3", "u4"])
        self.assertEqual(len(self.load("declaration = lambda review: DECLARATION").prepare(self.review).declaration.units), 4)
        with open(os.path.join(self.callers, "decl.json"), "w") as handle:
            json.dump(fx.declaration_dict(), handle)
        self.assertEqual(len(self.load("declaration = 'decl.json'").prepare(self.review).declaration.units), 4)
        text = "from review_kit import decl as kit_decl\ndeclaration = kit_decl.build(DECLARATION, 'x.json')\n"
        self.assertEqual(len(self.load(text).prepare(self.review).declaration.units), 4)

    def test_a_declaration_that_is_a_function_of_the_review_folder_produces_that_folders_units(self):
        extra = """
        import os
        def declaration(review_folder):
            raw = json.loads(json.dumps(DECLARATION))
            names = sorted(os.listdir(os.path.join(review_folder, 'units')))
            raw['units'] = {n: {'items': [n + '-item'], 'template': 't', 'needs': ['guide.md'], 'expected_output_tokens': 100,
                                'values': {'area': n}} for n in names}
            return raw
        """
        os.makedirs(os.path.join(self.review, "units"))
        for name in ("a", "b", "c"):
            open(os.path.join(self.review, "units", name), "w").close()
        self.assertEqual(list(self.load(extra).prepare(self.review).declaration.units), ["a", "b", "c"])

    def test_a_declaration_with_errors_is_refused_naming_the_caller_and_the_slip(self):
        bad = fx.declaration_dict()
        bad["units"]["u1"]["needs"] = ["nothing.png"]
        text = self.refused(lambda: self.load(declaration=bad).prepare(self.review))
        self.assertIn("the caller demo's declaration is refused", text)
        self.assertIn("nothing.png", text)

    def test_a_declaration_function_that_raises_is_refused_naming_the_function_and_the_caller(self):
        text = self.refused(lambda: self.load("def declaration(review_folder):\n    raise OSError('gone')\n").prepare(self.review))
        self.assertIn("the caller demo's declaration function raised OSError: gone", text)


class Defaults(Case):
    # SOL-HW-REVIEW-KIT.C13: a caller defining none of the retrieval grant, the checklist function and the review folder in the prompt behaves as one defining their defaults
    def test_a_caller_defining_none_behaves_as_one_defining_the_defaults(self):
        bare = self.load().prepare(self.review)
        explicit = self.load("""
        from review_kit import decl as kit_decl, messages
        retrieval = ('Read', 'Glob', 'Grep')
        def checklist(review_folder):
            return ['i1', 'i2', 'j1', 'k1', 'k2', 'm1']
        def prompt(unit, review_folder):
            return messages.unit_prompt(kit_decl.build(DECLARATION, 'x.json'), unit)
        """).prepare(self.review)
        self.assertEqual(bare.tools, explicit.tools)
        self.assertEqual(bare.checklist, explicit.checklist)
        self.assertEqual(bare.rules.first, explicit.rules.first)
        self.assertEqual(bare.rules.round_label, explicit.rules.round_label)
        for unit in bare.declaration.units:
            self.assertEqual(bare.unit_text(unit), explicit.unit_text(unit))

    def test_the_default_tools_are_the_read_tools_and_the_default_checklist_is_the_declared_items_once_in_order(self):
        prepared = self.load().prepare(self.review)
        self.assertEqual(prepared.tools, ("Read", "Glob", "Grep"))
        raw = fx.declaration_dict()
        raw["units"]["u4"]["items"] = ["i1", "m1"]
        self.assertEqual(self.load(declaration=raw).prepare(self.review).checklist, ("i1", "i2", "j1", "k1", "k2", "m1"))

    # SOL-HW-REVIEW-KIT.C13: optional attributes behave as defaults, retrieval grant
    def test_a_retrieval_grant_adds_the_one_retrieval_tool_to_the_read_tools_and_no_other(self):
        self.assertEqual(self.load("retrieval = True").prepare(self.review).tools, ("Read", "Glob", "Grep", "WebFetch"))
        self.assertEqual(self.load("retrieval = ['WebFetch', 'Grep', 'Read']").prepare(self.review).tools, ("Read", "Grep", "WebFetch"))
        self.assertEqual(self.load("retrieval = False").prepare(self.review).tools, ("Read", "Glob", "Grep"))
        self.assertEqual(self.load("retrieval = None").prepare(self.review).tools, ("Read", "Glob", "Grep"))
        for tool in ("Bash", "Write", "Edit", "WebSearch", "read"):
            text = self.refused(lambda t=tool: self.load(f"retrieval = ['Read', {t!r}]"))
            self.assertIn("grant some of Read, Glob, Grep and, to fetch a published document, WebFetch, and no other tool", text)

    # SOL-HW-REVIEW-KIT.C13: the review folder passed to the prompt function with the unit
    def test_the_prompt_function_is_given_the_unit_and_the_review_folder_when_it_takes_both_and_the_unit_alone_when_it_takes_one(self):
        both = self.load("def prompt(unit, review_folder):\n    return f'both {unit} {review_folder}'\n").prepare(self.review)
        self.assertEqual(both.unit_text("u1"), f"both u1 {self.review}")
        one = self.load("def prompt(unit):\n    return f'one {unit}'\n").prepare(self.review)
        self.assertEqual(one.unit_text("u2"), "one u2")

    def test_a_prompt_in_another_item_order_is_followed_by_that_order_and_in_the_declared_order_is_not(self):
        prepared = self.load("def prompt(unit, review_folder):\n    return 'judge ' + unit\n").prepare(self.review)
        self.assertEqual(prepared.unit_text("u1", ["i1", "i2"]), "judge u1")
        self.assertEqual(prepared.unit_text("u1", ["i2", "i1"]), "judge u1\n\nTake the items in this order:\n- i2\n- i1")

    def test_a_prompt_that_raises_or_returns_no_text_is_refused_naming_the_caller_and_the_unit(self):
        raising = self.load("def prompt(unit, review_folder):\n    raise KeyError(unit)\n").prepare(self.review)
        text = self.refused(raising.unit_text, "u3")
        self.assertIn("the caller demo's prompt function for unit u3 raised KeyError", text)
        empty = self.load("def prompt(unit, review_folder):\n    return '  '\n").prepare(self.review)
        self.assertIn("returned '  ' for unit u1", self.refused(empty.unit_text, "u1"))

    def test_a_citation_pattern_with_a_round_needs_the_round_label_and_earlier_findings_and_first_finding_is_checked(self):
        raw = fx.declaration_dict()
        raw["schema"]["findings"]["citation"] = "finding (?P<round>[a-z0-9]+)/(?P<number>\\d+)"
        text = self.refused(lambda: self.load(declaration=raw).prepare(self.review))
        self.assertIn("round_label is needed", text)
        text = self.refused(lambda: self.load("round_label = lambda review_folder: 'r2'", declaration=raw).prepare(self.review))
        self.assertIn("earlier_findings is needed", text)
        extra = "round_label = lambda review_folder: 'r2'\nearlier_findings = lambda review_folder: [('r1', 1)]\nfirst_finding = lambda review_folder: 5\n"
        prepared = self.load(extra, declaration=raw).prepare(self.review)
        self.assertEqual((prepared.rules.round_label, prepared.rules.earlier, prepared.rules.first), ("r2", frozenset({("r1", 1)}), 5))
        for source, expected in (("round_label = lambda r: ''\nearlier_findings = lambda r: []", "round_label function returned"),
                                 ("round_label = lambda r: 'r2'\nearlier_findings = lambda r: [('r1', 0)]", "earlier_findings function returned"),
                                 ("round_label = lambda r: 'r2'\nearlier_findings = lambda r: []\nfirst_finding = lambda r: 0", "first_finding function returned"),
                                 ("round_label = lambda r: 1/0\nearlier_findings = lambda r: []", "round_label function raised ZeroDivisionError")):
            self.assertIn(expected, self.refused(lambda s=source: self.load(s, declaration=raw).prepare(self.review)))


class Checklist(Case):
    COUNTING = """
    CALLS = []
    def checklist(review_folder):
        CALLS.append(review_folder)
        return ['i1', 'i2', 'j1', 'k1', 'k2', 'm1']
    """

    # SOL-HW-REVIEW-KIT.C13: a checklist function is resolved once before any session starts and a function that raises or returns a list with a repeated name fails the run naming the caller
    def test_a_checklist_function_is_resolved_once_in_prepare_and_never_again_by_the_merge_or_the_prompts(self):
        loaded = self.load(self.COUNTING)
        self.assertEqual(loaded.module.CALLS, [])
        prepared = loaded.prepare(self.review)
        self.assertEqual(loaded.module.CALLS, [self.review])
        units = {"u1": {"r1": {"Verdicts": [], "Findings": []}}}
        prepared.merge(["u1"], units)
        prepared.unit_text("u1")
        prepared.merge(["u1"], units)
        self.assertEqual(loaded.module.CALLS, [self.review])
        self.assertEqual(prepared.checklist, ("i1", "i2", "j1", "k1", "k2", "m1"))
        self.assertEqual(prepared.rules.checklist, prepared.checklist)

    def test_the_merge_numbers_findings_by_the_resolved_list_not_the_declared_order(self):
        loaded = self.load("def checklist(review_folder):\n    return ['m1', 'k2', 'k1', 'j1', 'i2', 'i1']\n")
        prepared = loaded.prepare(self.review)
        units = {"u1": {"r1": {"Verdicts": [], "Findings": [{"No": 1, "Item": "i1", "Detail": "a"}, {"No": 2, "Item": "i2", "Detail": "b"}]}}}
        rows = prepared.merge(["u1"], units)["tables"]["Findings"]["rows"]
        self.assertEqual([(row["No"], row["Item"]) for row in rows], [(1, "i2"), (2, "i1")])

    def test_a_checklist_function_that_raises_or_repeats_a_name_fails_naming_the_caller_before_anything_runs(self):
        text = self.refused(lambda: self.load("def checklist(review_folder):\n    raise OSError('no folder')\n").prepare(self.review))
        self.assertIn("the caller demo's checklist function raised OSError: no folder", text)
        text = self.refused(lambda: self.load("def checklist(review_folder):\n    return ['a', 'b', 'a']\n").prepare(self.review))
        self.assertIn("the caller demo's checklist repeats the name 'a'", text)
        text = self.refused(lambda: self.load("def checklist(review_folder):\n    return 'abc'\n").prepare(self.review))
        self.assertIn("the caller demo's checklist function returned 'abc'", text)
        text = self.refused(lambda: self.load("def checklist(review_folder):\n    return []\n").prepare(self.review))
        self.assertIn("checklist function returned []", text)

    def test_a_checklist_given_as_a_list_is_the_checklist(self):
        self.assertEqual(self.load("checklist = ['k1', 'i1']").prepare(self.review).checklist, ("k1", "i1"))


class ChecksAndRender(Case):
    def test_the_callers_checks_run_on_the_merged_tables_and_a_problem_refuses_the_merge(self):
        prepared = self.load("def checks(tables):\n    return ['bad %d' % len(tables['Verdicts']['rows'])]\n").prepare(self.review)
        text = self.refused(prepared.merge, ["u1"], {"u1": {"r1": {"Verdicts": [{"Item": "i1", "Verdict": "pass", "Note": ""}], "Findings": []}}})
        self.assertEqual(text, "bad 1")

    def test_checks_that_raise_or_return_other_than_a_list_of_text_are_refused_naming_the_caller(self):
        units = {"u1": {"r1": {"Verdicts": [], "Findings": []}}}
        text = self.refused(self.load("def checks(tables):\n    raise ValueError('x')\n").prepare(self.review).merge, ["u1"], units)
        self.assertIn("the caller demo's checks function raised ValueError: x", text)
        text = self.refused(self.load("def checks(tables):\n    return 'problem'\n").prepare(self.review).merge, ["u1"], units)
        self.assertIn("returned 'problem', not a list of problems", text)

    def test_render_is_given_the_review_folder_and_the_merged_tables_and_must_return_names_with_text(self):
        prepared = self.load("def render(review_folder, tables):\n    return {'round.md': review_folder + ':' + ','.join(tables)}\n").prepare(self.review)
        self.assertEqual(prepared.render({"Verdicts": {}, "Findings": {}}), {"round.md": f"{self.review}:Verdicts,Findings"})
        for source, expected in (("def render(review_folder, tables):\n    return ['a']\n", "not a mapping of file name to text"),
                                 ("def render(review_folder, tables):\n    return {'a': 5}\n", "not a mapping of file name to text"),
                                 ("def render(review_folder, tables):\n    raise KeyError('k')\n", "render function raised KeyError")):
            self.assertIn(expected, self.refused(self.load(source).prepare(self.review).render, {}))


class Names(Case):
    def folder(self, **files):
        out = os.path.join(self.tmp.name, "out")
        os.makedirs(out, exist_ok=True)
        for name, text in files.items():
            with open(os.path.join(out, name), "w") as handle:
                handle.write(text)
        return out

    def problems(self, out, names, earlier=()):
        return caller.rendered_problems("demo", out, {name: "x" for name in names}, list(earlier))

    # SOL-HW-REVIEW-KIT.C13: a name that is not one plain component of ASCII letters, digits, full stops, underscores and hyphens, begins with a letter or digit, ends with a full stop, is over sixty-four characters, is a reserved device name ... is refused
    def test_a_name_that_is_not_one_plain_ascii_component_is_refused(self):
        out = self.folder()
        for name in ("a/b.md", "../x.md", "a\\b.md", "a b.md", "café.md", ".hidden.md", "-x.md", "_x.md", "a$.md", "", "a\0b", ".", "..",
                     "x\n.md", "a:b.md"):
            self.assertTrue(self.problems(out, [name]), repr(name))

    # SOL-HW-REVIEW-KIT.C13: a name that is not one plain component of ASCII letters, digits, full stops, underscores and hyphens, begins with a letter or digit, ends with a full stop, is over sixty-four characters, is a reserved device name ... is refused
    def test_every_code_point_to_0x2ff_and_the_lookalikes_at_the_start_middle_and_end_of_a_name_agree_with_an_independent_oracle(self):
        out = self.folder()
        allowed = set(string.ascii_letters + string.digits + "._-")
        devices = {"con", "prn", "aux", "nul"} | {f"{kind}{n}" for kind in ("com", "lpt") for n in range(1, 10)}

        def oracle(name):
            return (bool(name) and all(c in allowed for c in name) and name[0] in string.ascii_letters + string.digits
                    and not name.endswith(".") and len(name) <= 64 and name.split(".")[0].lower() not in devices)

        marks = [chr(code) for code in range(0x300)]
        marks += ["\uff0e", "\u212a", "\u0660", "\u0661", "\u0669", "\u06f1", "\uff21", "\uff41", "\uff10", "\u2024", "\u2215",
                  "\u2044", "\u212b", "\u017f", "\u0131", "\u1d00", "\u2010", "\u2212", "\u00a0", "\u200b", "\U0001d7ce"]
        names = [shape.format(mark) for mark in marks for shape in ("{}x", "x{}x", "x{}")]
        names += ["a\n", "a" * 64, "a" * 65, "CON", "x.", "aux.txt", "com10"]
        for name in names:
            if "\0" in name or "/" in name or "\\" in name:
                continue
            accepted = self.problems(out, [name]) == []
            self.assertEqual(accepted, oracle(name), repr(name))
        self.assertTrue(any(oracle(n) for n in names) and any(not oracle(n) for n in names))

    def test_a_name_ending_in_a_full_stop_is_refused_and_one_with_inner_stops_and_hyphens_is_not(self):
        out = self.folder()
        self.assertIn("does not end in a full stop", "".join(self.problems(out, ["round-2."])))
        self.assertEqual(self.problems(out, ["round-2.v1_a.md", "9.txt", "A"]), [])

    def test_a_name_is_at_most_sixty_four_characters(self):
        out = self.folder()
        self.assertEqual(self.problems(out, ["a" * 64]), [])
        self.assertIn("at most 64 characters", "".join(self.problems(out, ["a" * 65])))

    def test_a_name_windows_reserves_for_a_device_is_refused_with_or_without_an_extension_in_any_case(self):
        out = self.folder()
        for name in ("CON", "con.txt", "Nul.md", "aux", "PRN.tar.gz", "com1", "COM9.log", "lpt1.txt", "LPT9"):
            self.assertTrue(self.problems(out, [name]), name)
        for name in ("com0", "com10", "console.md", "lpt", "auxiliary.md"):
            self.assertEqual(self.problems(out, [name]), [], name)

    def test_a_name_the_kit_uses_or_another_rendered_name_equal_without_regard_to_case_is_refused(self):
        out = self.folder()
        for name in caller.KIT_NAMES + ("PLAN.JSON", "Record.json", "RUN.LOCK", "Streams"):
            self.assertIn("which the kit uses", "".join(self.problems(out, [name])), name)
        text = "".join(self.problems(out, ["Round.md", "round.MD"]))
        self.assertIn("differ only in case", text)
        self.assertEqual(self.problems(out, ["round.md", "round2.md"]), [])

    def test_a_name_already_in_the_output_folder_that_the_earlier_merge_did_not_write_is_refused_and_one_it_wrote_is_not(self):
        out = self.folder(**{"mine.md": "x", "theirs.md": "y"})
        text = "".join(self.problems(out, ["theirs.md"], earlier=["mine.md"]))
        self.assertIn("already holds as 'theirs.md'", text)
        self.assertIn("no earlier merge wrote", text)
        self.assertEqual(self.problems(out, ["mine.md"], earlier=["mine.md"]), [])

    def test_a_name_the_earlier_merge_wrote_that_has_since_become_a_link_or_a_folder_is_refused(self):
        out = self.folder(**{"target.txt": "t"})
        os.symlink(os.path.join(out, "target.txt"), os.path.join(out, "linked.md"))
        os.mkdir(os.path.join(out, "folder.md"))
        text = "".join(self.problems(out, ["linked.md", "folder.md"], earlier=["linked.md", "folder.md"]))
        self.assertEqual(text.count("as a link or a folder"), 2)

    def test_a_dangling_link_in_the_name_s_place_is_not_a_file_the_merge_may_replace(self):
        out = self.folder()
        os.symlink(os.path.join(out, "nowhere"), os.path.join(out, "dangling.md"))
        self.assertTrue(self.problems(out, ["dangling.md"]))

    # SOL-HW-REVIEW-KIT.C13: the rendered record's files are written into the output folder after the merge and named in the record and the report in text and JSON with the same content
    def test_the_rendered_files_are_written_and_named_in_a_summary_whose_text_and_json_say_the_same(self):
        out = self.folder()
        summary = caller.write_rendered("demo", out, {"round-2.md": "a | b\n", "notes.txt": "n"}, [])
        self.assertEqual(summary, {"rendered": ["round-2.md", "notes.txt"], "not_this_merge": []})
        with open(os.path.join(out, "round-2.md"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "a | b\n")
        lines = caller.summary_lines(json.loads(json.dumps(summary)))
        self.assertEqual(lines, ["rendered: round-2.md", "rendered: notes.txt"])
        self.assertEqual([name for name in os.listdir(out) if name.startswith(".part")], [])

    def test_a_merge_after_a_rerun_replaces_the_files_the_earlier_merge_wrote_and_names_one_it_no_longer_renders(self):
        out = self.folder()
        first = caller.write_rendered("demo", out, {"a.md": "one", "b.md": "two"}, [])
        second = caller.write_rendered("demo", out, {"a.md": "three"}, first["rendered"])
        self.assertEqual(second, {"rendered": ["a.md"], "not_this_merge": ["b.md"]})
        with open(os.path.join(out, "a.md")) as handle:
            self.assertEqual(handle.read(), "three")
        self.assertEqual(caller.summary_lines(second), ["rendered: a.md", "left from an earlier merge, not of this one: b.md"])

    def test_a_refused_name_writes_nothing_and_leaves_a_foreign_file_as_it_was(self):
        out = self.folder(**{"theirs.md": "keep"})
        with self.assertRaises(merge.Refused):
            caller.write_rendered("demo", out, {"fine.md": "x", "theirs.md": "overwritten"}, [])
        self.assertEqual(sorted(os.listdir(out)), ["theirs.md"])
        with open(os.path.join(out, "theirs.md")) as handle:
            self.assertEqual(handle.read(), "keep")

    def test_no_rendered_files_is_a_valid_empty_summary(self):
        out = self.folder()
        self.assertEqual(caller.write_rendered("demo", out, {}, []), {"rendered": [], "not_this_merge": []})
        self.assertEqual(caller.summary_lines({"rendered": [], "not_this_merge": []}), [])

    def test_the_names_an_earlier_merge_wrote_are_read_from_the_run_record(self):
        self.assertEqual(caller.earlier_names(None), [])
        self.assertEqual(caller.earlier_names({}), [])
        record = {"rendered": ["a.md", "plan.json", "bad name"], "not_this_merge": ["b.md", "a.md"]}
        self.assertEqual(caller.earlier_names(record), ["a.md", "b.md"])
        for broken in ({"rendered": "a.md"}, {"not_this_merge": [1]}):
            self.assertIn("not a list of file names", self.refused(caller.earlier_names, broken))


if __name__ == "__main__":
    unittest.main()
