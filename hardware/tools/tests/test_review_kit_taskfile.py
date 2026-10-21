#!/usr/bin/env python3
"""The task runner's entries for the review kit and the hardware notes that describe them.

A description holding a colon followed by a space once made the task runner's file invalid without any test noticing, so
the file's review tasks are parsed here and each description is read. The board tools take no YAML dependency, so the
parse is a faithful check of the one form the file uses (a one-line plain scalar under the task's own key) and, where
PyYAML is installed, it is cross-checked against PyYAML. The notes' section on the command is read for the clauses the
command's description holds and for the cause and action of every line the command refuses with.
"""

from __future__ import annotations

import ast
import os
import re
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, TOOLS)

from review_kit import command  # noqa: E402
from review_kit import executor as ex  # noqa: E402

TASKFILE = os.path.join(REPO, "Taskfile.yml")
README = os.path.join(REPO, "hardware", "README.md")
COMMAND_SOURCE = os.path.join(TOOLS, "review_kit", "command.py")
#: A plain scalar may not begin with one of these indicators, and the next lines of a block are indented more than its key.
INDICATORS = "!&*|>'\"%@`#,[]{}"


class TaskfileError(Exception):
    """The file is not one the task runner reads; the text names the task and the line."""


def plain_scalar_problem(text: str) -> str:
    """Why a one-line plain scalar is not valid YAML, or the empty string when it is."""
    if not text:
        return "is empty"
    if text[0] in INDICATORS or (text[0] in "-?:" and (len(text) == 1 or text[1] == " ")):
        return f"begins with {text[0]!r}, which a plain scalar may not"
    if ": " in text or text.endswith(":"):
        at = text.index(": ") if ": " in text else len(text) - 1
        return f"holds a colon followed by a space near {text[max(0, at - 30):at + 10]!r}, which starts a mapping"
    if " #" in text:
        return f"holds a space followed by # near {text[max(0, text.index(' #') - 30):text.index(' #') + 10]!r}, which starts a comment"
    return ""


def descriptions(text: str) -> dict:
    """Every task's `desc` in a Taskfile, by task name. Raises TaskfileError for a description that is not valid YAML."""
    found, task, lines = {}, None, text.splitlines()
    in_tasks = False
    for number, line in enumerate(lines):
        if re.match(r"^tasks:\s*$", line):
            in_tasks = True
            continue
        if in_tasks and re.match(r"^\S", line) and not line.startswith("#"):
            in_tasks = False
        if not in_tasks:
            continue
        key = re.match(r"^  ([^\s#].*):\s*$", line)
        if key:
            task = key.group(1).strip("'\"")
            continue
        desc = re.match(r"^    desc:(?: +(.*?))?\s*$", line)
        if desc and task is not None:
            value = desc.group(1) or ""
            if value[:1] in ("|", ">"):
                block = []
                for follow in lines[number + 1:]:
                    if follow.strip() and not follow.startswith("      "):
                        break
                    block.append(follow.strip())
                found[task] = " ".join(part for part in block if part)
                continue
            if value[:1] in ("'", '"'):
                quote = value[0]
                if len(value) < 2 or not value.endswith(quote) or (quote == '"' and value.endswith("\\" + quote)):
                    raise TaskfileError(f"task {task}: the quoted description on line {number + 1} is not closed on its line")
                found[task] = value[1:-1]
                continue
            problem = plain_scalar_problem(value)
            if problem:
                raise TaskfileError(f"task {task}: the description on line {number + 1} {problem}")
            for follow in lines[number + 1:]:
                if follow.strip() and re.match(r"^ {5,}\S", follow) and not follow.lstrip().startswith("#"):
                    raise TaskfileError(f"task {task}: the description continues on a following line, {follow.strip()[:40]!r}")
                if follow.strip():
                    break
            found[task] = value
    return found


def read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def section(text: str, heading: str) -> str:
    start = text.index(f"\n{heading}\n") + 1
    end = text.find("\n## ", start + len(heading))
    return text[start:end if end != -1 else len(text)]


class TaskfileParse(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C11: a test parses the task runner's file and finds each review task's description
    def test_every_review_task_has_a_description_that_is_valid_yaml(self):
        found = descriptions(read(TASKFILE))
        reviews = sorted(name for name in found if name.startswith("hw:review-"))
        for needed in ("hw:review-run", "hw:review-smoke", "hw:review-fan-out", "hw:review-folder", "hw:review-proof",
                       "hw:review-seed", "hw:review-history"):
            self.assertIn(needed, reviews)
        for name in reviews:
            with self.subTest(task=name):
                self.assertIsInstance(found[name], str)
                self.assertGreater(len(found[name]), 40, "a description that says what the task is")
        for name in ("hw:test", "hw:test:round"):
            self.assertIn(name, found, "and the board tooling's test tasks are read the same way")

    # SOL-HW-REVIEW-KIT.C11: a description holding a colon followed by a space once made the file invalid
    def test_a_description_with_a_colon_and_a_space_or_a_comment_or_a_bad_start_is_found_invalid(self):
        good = "tasks:\n  hw:review-x:\n    desc: Run a review on demand, in neither gate\n    cmds:\n      - echo\n"
        self.assertEqual(descriptions(good), {"hw:review-x": "Run a review on demand, in neither gate"})
        for bad in ("Run a review: on demand", "Run a review on demand:", "Run a review # on demand", "- starts with a dash",
                    "'unclosed", "[flow", "@at", "%percent"):
            with self.subTest(desc=bad):
                with self.assertRaises(TaskfileError) as caught:
                    descriptions(good.replace("Run a review on demand, in neither gate", bad))
                self.assertIn("hw:review-x", str(caught.exception))
        with self.assertRaises(TaskfileError):
            descriptions(good.replace("neither gate\n", "neither gate\n      and a second line\n"))
        self.assertEqual(descriptions(good.replace("Run a review on demand, in neither gate", "'quoted: fine'")),
                         {"hw:review-x": "quoted: fine"})
        self.assertEqual(descriptions(good.replace("Run a review on demand, in neither gate", "colon:in word and a-b")),
                         {"hw:review-x": "colon:in word and a-b"})
        self.assertEqual(descriptions(good.replace("desc: Run a review on demand, in neither gate", "desc: |\n      a: block\n      scalar")),
                         {"hw:review-x": "a: block scalar"})

    def test_the_parse_agrees_with_pyyaml_where_it_is_installed(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML is not installed, so only the faithful check of the file's one form runs")
        text = read(TASKFILE)
        loaded = yaml.safe_load(text)["tasks"]
        found = descriptions(text)
        self.assertEqual({name: " ".join(task["desc"].split()) for name, task in loaded.items() if "desc" in task},
                         {name: " ".join(desc.split()) for name, desc in found.items()})
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load("tasks:\n  t:\n    desc: a review: on demand\n")


class CommandClauses(unittest.TestCase):
    """The clauses C11 names, in each place that must hold them."""

    CLAUSES = (
        ("forks of one shared context", "runs a declared review as forks of one shared context"),
        ("on demand", "that it is on demand"),
        ("in neither the build round nor the nightly", "that it is in neither the build round nor the nightly"),
        ("agent command line on the search path and logged in", "that it needs the agent command line on the path and logged in"),
        (ex.AGENT_ENV, "the one environment variable the command line's name is read from"),
        ("full model id", "that the model flag takes a full model id"),
        ("start report", "what a start report cannot show or exclude"),
        ("records", "what the report records"),
    )

    def assertClauses(self, text: str, where: str, clauses=CLAUSES):
        flat = " ".join(text.split())
        for needle, meaning in clauses:
            with self.subTest(where=where, clause=meaning):
                self.assertIn(needle, flat, f"{where} does not say {meaning}")

    # SOL-HW-REVIEW-KIT.C11: the task runner's description of the command says what it is, what it needs, that it is on demand,
    # the environment variable, what the report records and what a start report cannot show or exclude
    def test_the_task_runners_description_of_the_command_holds_each_clause(self):
        desc = descriptions(read(TASKFILE))["hw:review-run"]
        self.assertClauses(desc, "the task runner's description of hw:review-run")
        for needle in ("each session's own", "the predicted against the actual", "the checks that failed", "the files rendered",
                       "cannot show the system prompt", "cannot exclude the built-in plugins and agents", "account email",
                       "git status and recent commit subjects", "REFUSED or CANNOT RUN"):
            self.assertIn(needle, desc)
        self.assertNotIn("setup session", desc.replace("a session that judges nothing", ""), "no earlier driver wording")

    def test_the_smoke_is_described_as_on_demand_and_in_neither_gate(self):
        desc = descriptions(read(TASKFILE))["hw:review-smoke"]
        self.assertClauses(desc, "the task runner's description of hw:review-smoke",
                           [c for c in self.CLAUSES if c[0] in ("on demand", "in neither the build round nor the nightly",
                                                                  ex.AGENT_ENV)])
        self.assertIn("whenever the installed agent command line's version changes", desc)

    # SOL-HW-REVIEW-KIT.C11: the hardware notes' section on the command holds the same clauses
    def test_the_hardware_notes_section_holds_each_clause(self):
        text = section(read(README), "## The review kit command")
        self.assertClauses(text, "the hardware notes' section on the review kit command",
                           self.CLAUSES + (("task hw:review-run", "the command's task"), ("exit status", "the exit statuses"),
                                           ("`record.json`", "the output it writes"), ("not_this_merge", "the record's keys")))
        for needle in ("account email", "recent commit subjects", "built-in plugins and agents", "git work tree",
                       "a full model id", "predicted cost and time against the actual", "checks that failed", "`--rerun`",
                       "A lock left by a killed run", "no longer exists"):
            self.assertIn(needle, " ".join(text.split()))

    # SOL-HW-REVIEW-KIT.C11: the descriptions of the board tooling's tests and the list of tested tools name the kit's tests
    def test_the_tests_descriptions_and_the_notes_list_name_the_kits_tests(self):
        found = descriptions(read(TASKFILE))
        for name in ("hw:test", "hw:test:round"):
            self.assertIn("review kit", found[name], name)
        listed = next(line for line in read(README).splitlines() if line.startswith("- `task hw:test` runs the tests"))
        self.assertIn("the review kit (", listed)
        self.assertIn("the command", listed)
        commands = section(read(README), "## The commands")
        self.assertIn("`task hw:review-run", commands)
        self.assertIn("`task hw:review-smoke", commands)

    def test_the_notes_name_every_review_task_the_task_runner_defines(self):
        notes = read(README)
        for name in descriptions(read(TASKFILE)):
            if name.startswith("hw:review-") and name != "hw:review-history":
                with self.subTest(task=name):
                    self.assertIn(f"task {name}", notes)


def literal_text(node: ast.AST) -> str:
    """The text a node's string constants hold, f-string parts included, in source order; none for a plain name or a call."""
    return "".join(part.value for part in ast.walk(node) if isinstance(part, ast.Constant) and isinstance(part.value, str))


def refusal_literals(source: str):
    """The (line, text) of every message the command's own code puts on a REFUSED or CANNOT RUN line: the arguments of its
    refusal calls and appends and what it adds to the report's refusals. Messages made from another module's text have no
    literal and are held to their words by the tests that provoke them."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            owner = func.value.id if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else None
            if name in ("Refusal", "refused") or (isinstance(func, ast.Attribute) and func.attr == "append"
                                                  and owner in ("causes", "found")):
                if node.args:
                    found.append((node.lineno, literal_text(node.args[0])))
            elif name == "print" and node.args and literal_text(node.args[0]).startswith("REFUSED |"):
                found.append((node.lineno, literal_text(node.args[0])))
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Subscript) and literal_text(node.target) == "refusals":
            found.append((node.lineno, literal_text(node.value)))
    return [(line, text) for line, text in found if text.strip()]


class RefusalNotes(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C11: a session holding only the hardware notes' section and the command's refusal lines can state the
    # command's inputs, its outputs and the cause of each refusal: the structural half
    def test_every_cause_and_its_action_is_in_the_notes_section_in_one_row(self):
        text = section(read(README), "## The review kit command")
        rows = [line for line in text.splitlines() if line.startswith("| `")]
        for code, (cause, action) in command.CAUSES.items():
            with self.subTest(code=code):
                held = [row for row in rows if cause in row and action in row]
                self.assertTrue(held, f"the notes' table has no row giving {cause!r} and {action!r}")
        self.assertGreaterEqual(len(rows), len(command.CAUSES))

    def test_every_refusal_the_command_words_itself_names_a_documented_cause_and_its_action(self):
        literals = refusal_literals(read(COMMAND_SOURCE))
        self.assertGreater(len(literals), 10, "the scan found the command's refusals")
        for line, text in literals:
            with self.subTest(line=line, text=text[:60]):
                held = [code for code, (cause, action) in command.CAUSES.items() if action in text]
                self.assertTrue(held, f"command.py line {line} words a refusal that says no documented action: {text!r}")

    def test_every_cause_is_worded_by_the_command_or_by_a_module_it_reports(self):
        source = read(COMMAND_SOURCE)
        elsewhere = "".join(read(os.path.join(TOOLS, "review_kit", name)) for name in
                            ("store.py", "executor.py", "caller.py", "planner.py", "catalogue.py", "scheduler.py", "merge.py"))
        for code, (cause, action) in command.CAUSES.items():
            with self.subTest(code=code):
                self.assertTrue(cause in source or cause in elsewhere, f"nothing words {cause!r}")
                self.assertTrue(action.split("<")[0] in source or action.split("<")[0] in elsewhere, f"nothing words {action!r}")


if __name__ == "__main__":
    unittest.main()
