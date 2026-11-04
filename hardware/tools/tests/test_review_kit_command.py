#!/usr/bin/env python3
"""The review kit's command over a stand-in for the agent command line: a run from the first check to the merged record.

The command starts the program named by the environment variable REVIEW_KIT_AGENT, as the executor's tests do, and here
that is a small script playing the sessions the real command line would. Synthetic callers, declarations and folders in
temporary directories; no model, no network, no KiCad, and the real agent command line is never run.
"""

from __future__ import annotations

import dataclasses
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import catalogue, command, costmodel, decl, ensemble, messages, planner, scheduler, store  # noqa: E402
from review_kit import executor as ex  # noqa: E402
from review_kit import session as sess  # noqa: E402

STUB = '''#!PYTHON
import json, os, re, sys, uuid
sys.path.insert(0, TOOLS)
from review_kit import executor as ex
args = sys.argv[1:]
with open(os.environ["STUB_SCENARIO"], encoding="utf-8") as handle:
    scenario = json.load(handle)
if args[:2] == ["auth", "status"]:
    print(json.dumps({"loggedIn": scenario.get("logged_in", True)}))
    sys.exit(0)
if args == ["--version"]:
    print("9.9.9 (stub)")
    if scenario.get("vanish"):
        os.unlink(sys.argv[0])
    sys.exit(0)
stdin = sys.stdin.read()


def flag(name):
    return args[args.index(name) + 1] if name in args else None


tools = flag("--tools").split(",") + (["StructuredOutput"] if "--json-schema" in args else [])
model = flag("--model") or "stub-model"
resume = flag("--resume")
session_id = "stub-" + uuid.uuid4().hex[:8]
text = " ".join(block.get("text", "") for block in json.loads(stdin)["message"]["content"] if block.get("type") == "text")
with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"args": args, "cwd": os.getcwd(), "session": session_id, "resume": resume,
                             "fork": "--fork-session" in args, "model": model, "text": text}) + "\\n")
mcp = [{"name": "extra", "status": "connected"}] if scenario.get("mcp") else []
if resume is None and scenario.get("root_error"):
    sys.stdout.write(ex.stream_text(session_id, text="the service failed", is_error=True, api_error_status=500, tools=tools,
                                    model=model, cwd=os.getcwd()))
    sys.exit(1)
if resume is None:
    stream = ex.stream_text(session_id, text=scenario.get("ack", "ACK"), cost=0.01, api_ms=100, turns=1, read=0, write=1000,
                            generated=2, tools=tools, model=model, cwd=os.getcwd(), mcp_servers=mcp)
    sys.stdout.write(stream)
    sys.exit(0)
if scenario.get("login_lost"):
    sys.stdout.write(ex.stream_text(session_id, text="Not logged in", is_error=True, api_error_status=401, tools=tools,
                                    model=model, cwd=os.getcwd()))
    sys.exit(1)
items = []
for held in re.findall(r"Judge these items of [^\\n]*:\\n((?:- [^\\n]*\\n?)+)", text):
    items += [line[2:] for line in held.splitlines() if line.startswith("- ")]
if any(f"items of {area}:" in text for area in scenario.get("bad_areas", [])):
    structured, said = None, "I found nothing worth tabulating."
else:
    verdicts = scenario.get("verdicts", {})
    rows = [{"Item": item, "Verdict": verdicts.get(item, "pass"), "Note": ""} for item in items]
    found = [{"No": 1 + number, "Item": row["Item"], "Detail": "seen"} for number, row in
             enumerate(r for r in rows if r["Verdict"] == "fail")]
    structured, said = {"tables": {"Verdicts": rows, "Findings": found}}, "done"
sys.stdout.write(ex.stream_text(session_id, text=said, structured=structured, cost=0.03, api_ms=300, turns=1, read=scenario.get("fork_read", 1000),
                                write=200, generated=50, tools=tools, model=model, cwd=os.getcwd()))
'''

CALLER = '''
import json, os
declaration = json.loads({declaration!r})


def checks(tables):
    return [f"item {{row['Item']}} is judged twice" for row in tables["Verdicts"]["rows"]
            if [r["Item"] for r in tables["Verdicts"]["rows"]].count(row["Item"]) > 1]


def render(review_folder, tables):
    names = os.environ.get("STUB_RENDER", "summary.md").split(",")
    body = "\\n".join(f"{{row['Item']}}: {{row['Verdict']}}" for row in tables["Verdicts"]["rows"]) + "\\n"
    return {{name: body for name in names if name}}
{extra}'''


class Case(unittest.TestCase):
    """A stand-in agent program, a caller, a review folder and an output folder, and the command run over them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)
        self.callers = os.path.join(self.base, "callers")
        os.makedirs(self.callers)
        self.review = fx.review_folder(os.path.join(self.base, "review"))
        self.out = os.path.join(self.base, "out")
        self.repo = os.path.join(self.base, "repo")
        os.makedirs(self.repo)
        self.log = os.path.join(self.base, "agent.log")
        self.scenario_path = os.path.join(self.base, "scenario.json")
        self.program = os.path.join(self.base, "agent")
        with open(self.program, "w", encoding="utf-8") as handle:
            handle.write(STUB.replace("PYTHON", sys.executable, 1).replace("TOOLS", repr(TOOLS)))
        os.chmod(self.program, 0o755)
        self.scenario()
        self.write_caller()
        values = {ex.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path, "STUB_LOG": self.log}
        patcher = mock.patch.dict(os.environ, values)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("STUB_RENDER", None)

    def scenario(self, **values):
        with open(self.scenario_path, "w", encoding="utf-8") as handle:
            json.dump(values, handle)

    def write_caller(self, extra="", declaration=None, name="demo"):
        with open(os.path.join(self.callers, f"review_caller_{name}.py"), "w", encoding="utf-8") as handle:
            handle.write(CALLER.format(declaration=json.dumps(declaration or fx.declaration_dict()), extra=textwrap.dedent(extra)))

    def run_command(self, *extra, out=None, review=None, caller="demo", fmt="text", repo=None, skip=()):
        argv = ["--caller", caller, "--callers", self.callers, "--review", review or self.review, "--out", out or self.out]
        argv = [a for a in argv if a not in skip]
        argv += ["--format", fmt] + list(extra)
        stdout, stderr = io.StringIO(), io.StringIO()
        status = command.main(argv, stdout, stderr, repo=repo or self.repo)
        return status, stdout.getvalue(), stderr.getvalue()

    def calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def record(self, out=None):
        return store.read_record(out or self.out)

    def lines(self, text, prefix):
        return [line for line in text.splitlines() if line.startswith(prefix)]

    def refused(self, code, *extra, status=1, stream="out", **kwargs):
        got, out, err = self.run_command(*extra, **kwargs)
        self.assertEqual(got, status, out + err)
        text = out if stream == "out" else err
        cause, action = command.CAUSES[code]
        line = next((line for line in text.splitlines() if line.startswith(("REFUSED", "CANNOT RUN")) and cause in line), None)
        self.assertIsNotNone(line, f"no REFUSED line holds {cause!r}:\n{text}")
        self.assertIn(action, line, "the line says what to do")
        return text


class EndToEnd(Case):
    # SOL-HW-REVIEW-KIT.C10: over the stub with a synthetic declaration and review folder, a run builds the plan, runs the
    # shared context and the forks and replicas, merges, writes the caller's rendered files and the run's figures into the
    # output folder and lists them in the report
    def test_a_run_builds_the_plan_runs_the_context_and_forks_merges_renders_and_lists_the_files(self):
        status, out, err = self.run_command()
        self.assertEqual((status, err), (0, ""), out)
        record = self.record()
        plan = record["plan"]
        forks = [n for n in record["nodes"] if n["role"] == "unit"]
        self.assertEqual(len(plan["groups"]), 3)
        self.assertEqual(sum(g["replicas"] for g in plan["groups"]), len(forks), "one fork for every group and replica")
        calls = self.calls()
        roots = [c for c in calls if c["resume"] is None]
        self.assertEqual(len(roots), 3, "the root of each group is started once")
        self.assertEqual([c["resume"] for c in calls[:3]], [None, None, None], "and before any fork")
        forks_of = {}
        for fork in (c for c in calls if c["resume"] is not None):
            self.assertIn(fork["resume"], {root["session"] for root in roots})
            self.assertTrue(fork["fork"])
            forks_of[fork["resume"]] = forks_of.get(fork["resume"], 0) + 1
        self.assertEqual(sorted(forks_of.values()), sorted(g["replicas"] for g in plan["groups"]),
                         "each group's replicas continue the one root of the group")
        with open(os.path.join(self.out, "summary.md"), encoding="utf-8") as handle:
            self.assertEqual(handle.read().splitlines(), sorted({f"{i}: pass" for i in ("i1", "i2", "j1", "k1", "k2", "m1")}))
        self.assertEqual(record["rendered"], ["summary.md"])
        self.assertEqual(record["not_this_merge"], [])
        self.assertIsNotNone(record["merged"])
        for name in ("plan.json", "record.json", "streams", "summary.md"):
            self.assertTrue(os.path.exists(os.path.join(self.out, name)), name)
        self.assertNotIn("run.lock", os.listdir(self.out), "the lock is released")
        self.assertEqual(self.lines(out, "RENDERED"), ["RENDERED | summary.md"])
        self.assertIn("FILE | summary.md", out)
        self.assertTrue(out.splitlines()[-1].startswith("RESULT | WRITTEN"))
        self.assertEqual(len(self.lines(out, "SESSION")), 3 + len(forks), "each session's own figures")

    # SOL-HW-REVIEW-KIT.C10: the figures written into the output folder are each session's own: a fork's reported cost less
    # its parent's, and the run's, with the predicted against the actual
    def test_the_figures_are_each_sessions_own_and_the_runs_against_the_prediction(self):
        status, out, err = self.run_command(fmt="json")
        self.assertEqual(status, 0, err)
        report = json.loads(out)
        sessions = {s["label"]: s for s in report["sessions"]}
        roots = [s for label, s in sessions.items() if label.startswith("root")]
        self.assertEqual(len(roots), 3)
        for root in roots:
            self.assertAlmostEqual(root["cost_usd"], 0.01)
        forks = [s for label, s in sessions.items() if not label.startswith("root")]
        for fork in forks:
            self.assertAlmostEqual(fork["cost_usd"], 0.02, msg="reported 0.03 cumulatively, 0.01 of it the parent's")
            self.assertEqual(fork["parent"], "root." + fork["label"].split(".")[0])
            self.assertEqual(fork["first_call_read"], 1000)
            self.assertEqual(fork["tokens"]["cache_read"], 1000)
        run = report["run"]
        self.assertAlmostEqual(run["cost_usd"], 0.01 * 3 + 0.02 * len(forks))
        self.assertEqual(run["sessions"], 3 + len(forks))
        self.assertEqual(run["predicted"]["cost_usd"], report["plan"]["predicted"]["cost_usd"])
        self.assertIn("cost_deviation", run["predicted"])
        self.assertIn("wall_deviation", run["predicted"])
        self.assertEqual(self.record()["figures"]["run"]["sessions"], run["sessions"], "and the output folder holds them")

    # SOL-HW-REVIEW-KIT.C10: the report is available as text and as JSON and holds the same facts: the plan, each session's
    # own figures, the run's, the predicted against the actual, the checks that failed and the files rendered
    def test_the_text_report_holds_every_fact_the_json_report_holds(self):
        self.scenario(mcp=False)
        status, out, err = self.run_command(fmt="json")
        self.assertEqual(status, 0, err)
        report = json.loads(out)
        for key in ("plan", "sessions", "run", "checks_failed", "rendered", "not_this_merge", "files", "units", "result"):
            self.assertIn(key, report)
        text = "\n".join(command.render_text(report))
        for group in report["plan"]["groups"]:
            self.assertIn(f"GROUP | {group['id']} | units {', '.join(group['units'])} | {group['replicas']} replicas", text)
        self.assertIn(f"{report['plan']['forks']} forks", text)
        self.assertIn(report["plan"]["prefix_sha"], text)
        self.assertIn(report["plan"]["spec_digest"], text)
        self.assertIn(f"tool commit {report['plan']['tool_commit']}", text)
        self.assertIn(f"PREDICTED | ${report['plan']['predicted']['cost_usd']} | {report['plan']['predicted']['wall_s']} s", text)
        for session in report["sessions"]:
            self.assertIn(f"SESSION | {session['label']} | {session['role']} | {session['kind']}", text)
            self.assertIn(f"${session['cost_usd']}", text)
        run = report["run"]
        self.assertIn(f"TOTAL | {run['sessions']} sessions", text)
        self.assertIn(f"critical path {run['critical_path_s']} s", text)
        self.assertIn(f"AGAINST PREDICTED | cost ${run['actual']['cost_usd']} of ${run['predicted']['cost_usd']}", text)
        self.assertIn(f"deviation {run['predicted']['wall_deviation']}", text)
        for name in report["rendered"]:
            self.assertIn(f"RENDERED | {name}", text)
        for name in report["files"]:
            self.assertIn(f"FILE | {name}", text)
        for table, held in report["tables"].items():
            self.assertIn(f"TABLE | {table} | columns {', '.join(held['columns'])} | {len(held['rows'])} rows", text)
        self.assertIn(f"RESULT | {report['result']}", text)
        # and the text the command prints for a run is the same facts, in the same lines
        status, printed, _ = self.run_command(out=os.path.join(self.base, "out2"))
        self.assertEqual(status, 0)
        for prefix in ("RUN", "AGENT", "PLAN", "GROUP", "PREDICTED", "SESSION", "TOTAL", "AGAINST PREDICTED", "RENDERED", "FILE", "TABLE", "ROW", "RESULT"):
            self.assertTrue(self.lines(printed, prefix), prefix)

    # SOL-HW-REVIEW-KIT.C10: the checks that failed are in both reports
    def test_a_check_that_failed_is_in_the_text_and_the_json_report(self):
        status, out, err = self.run_command(fmt="json")
        self.assertEqual(json.loads(out)["checks_failed"], [], "a run whose forks read the prefix has no failed check")
        self.scenario(fork_read=0)
        status, out, err = self.run_command(out=os.path.join(self.base, "out2"), fmt="json")
        self.assertEqual(status, 0, "a flagged cache miss is reported, and the merged record is still written")
        report = json.loads(out)
        self.assertTrue(report["checks_failed"])
        self.assertTrue(all("cache" in check for check in report["checks_failed"]), report["checks_failed"])
        shown = command.render_text(report)
        for check in report["checks_failed"]:
            self.assertIn(f"CHECK FAILED | {check}", shown)
        status, text, _ = self.run_command(out=os.path.join(self.base, "out3"))
        self.assertEqual(status, 0)
        self.assertEqual(len(self.lines(text, "CHECK FAILED")), len(report["checks_failed"]))

    # SOL-HW-REVIEW-KIT.C10: a second run naming one unit replaces that unit's result and merges again
    def test_a_second_run_naming_one_unit_replaces_its_result_and_merges_again(self):
        self.assertEqual(self.run_command()[0], 0)
        first = self.record()
        before = len(self.calls())
        self.scenario(verdicts={"i1": "fail"})
        status, out, err = self.run_command("--rerun", "u1")
        self.assertEqual((status, err), (0, ""), out)
        record = self.record()
        again = self.calls()[before:]
        group = next(g for g in record["plan"]["groups"] if "u1" in g["units"])
        self.assertEqual(sum(1 for c in again if c["resume"] is None), 1, "a new shared context is started once")
        self.assertEqual(sum(1 for c in again if c["resume"] is not None), group["replicas"], "and only that unit's group runs")
        verdicts = {row["Item"]: row["Verdict"] for row in record["merged"]["tables"]["Verdicts"]["rows"]}
        self.assertEqual(verdicts["i1"], "fail")
        self.assertEqual({v for item, v in verdicts.items() if item != "i1"}, {"pass"}, "the other units' results are kept")
        self.assertEqual([run["kind"] for run in record["runs"]], ["fresh", "rerun"])
        self.assertEqual(record["runs"][1]["units"], ["u1"])
        with open(os.path.join(self.out, "summary.md"), encoding="utf-8") as handle:
            self.assertIn("i1: fail", handle.read())
        self.assertEqual(len(record["lanes"]), len(first["lanes"]))
        self.assertIn("RERUN | u1", out)
        sessions = self.lines(out, "SESSION")
        self.assertEqual(len(sessions), 1 + group["replicas"], "the report's figures are the second run's sessions")
        predicted = json.loads(self.run_command("--rerun", "u1", fmt="json")[1])["run"]["predicted"]
        self.assertLess(predicted["cost_usd"], first["plan"]["predicted"]["cost_usd"], "predicted for the groups run, not the review")


class Refusals(Case):
    """Each cause is refused with a line beginning REFUSED that names the cause and what to do, and nothing is started."""

    def assertNothingStarted(self):
        self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(os.path.join(self.out, "run.lock")))

    # SOL-HW-REVIEW-KIT.C10: a review folder that does not exist or is inside the repository is refused
    def test_a_review_folder_that_does_not_exist_or_is_inside_the_repository_is_refused(self):
        self.refused("review-missing", review=os.path.join(self.base, "nowhere"))
        inside = fx.review_folder(os.path.join(self.repo, "review"))
        self.refused("review-in-repository", review=inside)
        self.assertNothingStarted()
        self.assertFalse(os.path.exists(self.out), "no output folder is made for a refusal")

    # SOL-HW-REVIEW-KIT.C10: an output folder inside the review folder or containing it or inside the repository is refused
    def test_an_output_folder_inside_or_around_the_review_folder_or_inside_the_repository_is_refused(self):
        self.refused("output-in-review", out=os.path.join(self.review, "out"))
        self.refused("output-contains-review", out=self.base)
        self.refused("output-in-repository", out=os.path.join(self.repo, "out"))
        file_path = os.path.join(self.base, "afile")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("x")
        self.refused("output-is-file", out=file_path)
        self.assertNothingStarted()

    def test_a_link_into_the_repository_is_seen_through(self):
        link = os.path.join(self.base, "link")
        os.symlink(self.repo, link)
        self.refused("output-in-repository", out=os.path.join(link, "out"))

    # SOL-HW-REVIEW-KIT.C10: a declaration or caller that cannot be loaded is refused
    def test_a_caller_or_declaration_that_cannot_be_loaded_is_refused(self):
        self.refused("caller-missing", caller="nosuch")
        with open(os.path.join(self.callers, "review_caller_broken.py"), "w", encoding="utf-8") as handle:
            handle.write("raise RuntimeError('boom')\n")
        self.refused("caller-unloadable", caller="broken")
        with open(os.path.join(self.callers, "review_caller_bare.py"), "w", encoding="utf-8") as handle:
            handle.write("declaration = {}\n")
        self.refused("caller-attribute", caller="bare")
        bad = fx.declaration_dict()
        bad["units"]["u1"]["needs"] = ["view_that_is_not_an_artefact"]
        self.write_caller(declaration=bad, name="slip")
        text = self.refused("declaration-refused", caller="slip")
        self.assertIn("view_that_is_not_an_artefact", text, "the slip is named")
        self.assertIn("u1", text)
        self.assertNothingStarted()

    def test_a_replica_policy_that_cannot_be_used_is_refused(self):
        self.write_caller(extra="replica_policy = {'variants': [{'id': 'x', 'item_order': 'sideways'}]}\n")
        text = self.refused("replica-policy")
        self.assertIn("sideways", text)
        self.assertNothingStarted()

    # SOL-HW-REVIEW-KIT.C10: an artefact outside the review folder or on the deny list is refused, naming the rule
    def test_an_artefact_the_review_folder_cannot_supply_is_refused_naming_the_rule(self):
        os.unlink(os.path.join(self.review, "docs", "guide.md"))
        text = self.refused("artefact-refused")
        self.assertIn("guide.md", text)
        self.assertNothingStarted()

    # SOL-HW-REVIEW-KIT.C10: an output folder that holds a record when no unit is named to run again is refused
    def test_an_output_folder_that_holds_a_record_is_refused_unless_a_unit_is_named(self):
        self.assertEqual(self.run_command()[0], 0)
        before = len(self.calls())
        self.refused("output-has-record")
        self.assertEqual(len(self.calls()), before, "nothing was started")
        self.assertEqual(self.run_command("--rerun", "u1")[0], 0, "a unit named to run again is allowed")

    def test_a_rerun_with_no_record_or_an_unreadable_one_is_refused(self):
        self.refused("no-record", "--rerun", "u1")
        os.makedirs(self.out)
        with open(os.path.join(self.out, "record.json"), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.refused("record-unreadable", "--rerun", "u1")
        self.assertNothingStarted()

    # SOL-HW-REVIEW-KIT.C10: an output folder in use by another run is refused
    def test_an_output_folder_in_use_by_another_run_is_refused(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, "run.lock"), "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "started": 0}, handle)
        self.refused("output-in-use")
        self.assertTrue(os.path.exists(os.path.join(self.out, "run.lock")), "another run's lock is left alone")
        with open(os.path.join(self.out, "run.lock"), "w", encoding="utf-8") as handle:
            handle.write("not json")
        self.refused("output-in-use")
        self.assertEqual(self.calls(), [])

    # SOL-HW-REVIEW-KIT.C10: a bound below one is refused
    def test_a_bound_below_one_or_that_is_not_a_number_is_refused(self):
        for value in ("0", "-3"):
            with self.subTest(value=value):
                self.refused("number-below-one", "--bound", value)
        self.refused("number-not-whole", "--bound", "many")
        self.refused("number-below-one", "--replicas", "0")
        self.refused("number-not-whole", "--replicas", "1.5")
        self.assertNothingStarted()

    def test_an_empty_model_a_bad_format_and_a_bad_command_line_are_refused(self):
        self.refused("model-empty", "--model", "  ")
        self.refused("format", fmt="yaml")
        got, out, err = self.run_command(skip=("--caller", "demo"))
        self.assertEqual(got, 1, "a command line that cannot be read is a refusal, not exit 2")
        self.assertIn("run with --help", out)
        self.assertIn(command.CAUSES["usage"][0], out)
        self.assertNothingStarted()

    # SOL-HW-REVIEW-KIT.C10: a shared context over the budget is refused
    def test_a_shared_context_over_the_budget_is_refused_before_any_session(self):
        small = fx.declaration_dict()
        small["budget"] = {"context_tokens": 10}
        self.write_caller(declaration=small, name="small")
        text = self.refused("over-budget", caller="small")
        self.assertIn("10 tokens", text)
        self.assertNothingStarted()

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C2: a model with no declared window and no stated figure is refused naming the model and where its window is declared
    def test_a_budget_stated_as_a_fraction_of_a_window_the_kit_does_not_declare_is_refused_before_any_session(self):
        fractional = fx.declaration_dict()
        fractional["budget"] = {"context_fraction": 0.5}
        self.write_caller(declaration=fractional, name="fractional")
        text = self.refused("window-undeclared", "--model", "a-model-nobody-declared", caller="fractional")
        self.assertIn("a-model-nobody-declared", text)
        self.assertIn("WINDOW_TOKENS_BY_MODEL", text)
        self.assertNothingStarted()
        text = self.refused("window-undeclared", caller="fractional")
        self.assertIn("--model", text)
        self.assertNothingStarted()

    # SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C3: The review kit measures the size of the stream message that holds the shared context, the images base64-encoded as the kit sends them, and refuses the run with a line beginning REFUSED, before any session is started and before anything is spent, when that size is over the agent command line's stream limit of 268,435,456 characters (256 x 1024 x 1024, the figure the agent command line reports as 256M), a named constant of the kit, counted as the command line counts them: the UTF-16 code units of the one JSON line, without its newline. The line names the size, the limit, and the artefact group of the review folder that is largest (the views folder, the placement folder or the documents) with its size, and says what to do: write fewer or smaller views. The check is made where the context budget is checked, so the proof command's forms are held to it too. A context at the limit is not refused. Over the stub with a synthetic review folder and the constant lowered by the test, a context over the limit is refused with that line in text and in JSON and no session is started, a context at the limit runs, and the prediction line is not printed for the refused one. Out of scope: the token budget, which is unchanged.
    def test_a_shared_context_over_the_stream_limit_is_refused_before_any_session_and_the_prediction_in_text_and_json(self):
        declaration = decl.parse(json.dumps(fx.declaration_dict()), "caller.json")
        found = catalogue.admit(declaration, self.review)
        roots = planner.form(declaration, found, None).groups
        widest = max(roots, key=lambda built: messages.stream_size(built.shared.message))
        size = messages.stream_size(widest.shared.message)
        group, held = messages.largest_group(widest.catalogue)
        with mock.patch.object(messages, "STREAM_LIMIT", size - 1):
            text = self.refused("over-stream-limit")
            for part in (str(size), str(size - 1), group, str(held), "write fewer or smaller views"):
                self.assertIn(part, text)
            self.assertNotIn("PREDICTED", text, "the prediction line is not printed for the refused run")
            self.assertNothingStarted()
            self.assertFalse(os.path.exists(self.out), "nothing was written")
            status, out, err = self.run_command(fmt="json")
            self.assertEqual((status, err), (1, ""))
            report = json.loads(out)
            self.assertEqual(report["result"], "REFUSED")
            self.assertTrue(any(command.CAUSES["over-stream-limit"][0] in line and str(size) in line
                                for line in report["refusals"]), report["refusals"])
            self.assertNotIn("PREDICTED", out)
            self.assertNothingStarted()

    # SOL-BOARD-REVIEW-NET-VIEWS-DRAW-ONLY-TILES-HOLDING-THE-NET.C3: The review kit measures the size of the stream message that holds the shared context, the images base64-encoded as the kit sends them, and refuses the run with a line beginning REFUSED, before any session is started and before anything is spent, when that size is over the agent command line's stream limit of 268,435,456 characters (256 x 1024 x 1024, the figure the agent command line reports as 256M), a named constant of the kit, counted as the command line counts them: the UTF-16 code units of the one JSON line, without its newline. The line names the size, the limit, and the artefact group of the review folder that is largest (the views folder, the placement folder or the documents) with its size, and says what to do: write fewer or smaller views. The check is made where the context budget is checked, so the proof command's forms are held to it too. A context at the limit is not refused. Over the stub with a synthetic review folder and the constant lowered by the test, a context over the limit is refused with that line in text and in JSON and no session is started, a context at the limit runs, and the prediction line is not printed for the refused one. Out of scope: the token budget, which is unchanged.
    def test_a_shared_context_exactly_at_the_stream_limit_runs(self):
        declaration = decl.parse(json.dumps(fx.declaration_dict()), "caller.json")
        found = catalogue.admit(declaration, self.review)
        size = max(messages.stream_size(built.shared.message) for built in planner.form(declaration, found, None).groups)
        with mock.patch.object(messages, "STREAM_LIMIT", size):
            status, out, err = self.run_command()
        self.assertEqual((status, err), (0, ""), out)
        self.assertIn("PREDICTED", out)
        self.assertTrue(self.calls(), "the sessions were started")

    def test_a_rerun_of_a_unit_the_review_lacks_or_of_a_changed_folder_is_refused(self):
        self.assertEqual(self.run_command()[0], 0)
        self.refused("unit-unknown", "--rerun", "nosuch")
        with open(os.path.join(self.review, "docs", "guide.md"), "a", encoding="utf-8") as handle:
            handle.write("one more line\n")
        self.refused("review-changed", "--rerun", "u1")

    def test_a_rerun_that_leaves_out_a_failed_unit_is_refused(self):
        self.scenario(bad_areas=["gamma"])
        self.assertEqual(self.run_command()[0], 1)
        self.scenario()
        self.refused("unit-left-out", "--rerun", "u1")

    def test_a_declaration_that_changed_since_the_recorded_run_is_refused_as_a_rerun(self):
        self.assertEqual(self.run_command()[0], 0)
        changed = fx.declaration_dict()
        changed["units"]["u1"]["expected_output_tokens"] = 450
        changed["units"]["u4"]["expected_output_tokens"] = 450
        self.write_caller(declaration=changed)
        self.refused("plan-changed", "--rerun", "u1")

    # SOL-HW-REVIEW-KIT.C10: the exit status is 1 when a unit fails, with a line naming it and what to do
    def test_a_unit_that_fails_is_reported_and_its_siblings_results_are_kept(self):
        self.scenario(bad_areas=["gamma"])
        status, out, err = self.run_command()
        self.assertEqual(status, 1)
        cause, action = command.CAUSES["unit-failed"]
        line = next(line for line in out.splitlines() if line.startswith("REFUSED") and cause in line)
        self.assertIn("u2, u3", line)
        self.assertIn(action, line)
        self.assertTrue(out.splitlines()[-1].startswith("RESULT | REFUSED"))
        record = self.record()
        self.assertIsNone(record["merged"])
        self.assertTrue(record["units"]["u3"]["failed"])
        self.assertFalse(record["units"]["u1"]["failed"], "the others' results are kept")
        self.assertFalse(os.path.exists(os.path.join(self.out, "summary.md")), "nothing is rendered from a partial merge")
        self.assertNotIn("run.lock", os.listdir(self.out))
        self.scenario()
        status, out, err = self.run_command("--rerun", "u2", "--rerun", "u3")
        self.assertEqual((status, err), (0, ""), out)
        self.assertTrue(os.path.exists(os.path.join(self.out, "summary.md")))

    def test_a_start_report_that_shows_what_the_specification_excludes_is_refused(self):
        self.scenario(mcp=True)
        self.refused("start-report")
        self.assertNotIn("run.lock", os.listdir(self.out))

    def test_a_shared_context_that_cannot_be_started_is_reported_and_no_fork_is_started(self):
        self.scenario(root_error=True)
        self.refused("root-failed")
        self.assertEqual([c["resume"] for c in self.calls()], [None, None, None], "every root was started and none failed a fork into being")
        self.assertNotIn("run.lock", os.listdir(self.out))

    def test_an_output_folder_that_cannot_be_written_is_refused(self):
        blocker = os.path.join(self.base, "blocker")
        with open(blocker, "w", encoding="utf-8") as handle:
            handle.write("a file where a folder is needed")
        self.refused("output-unwritable", out=os.path.join(blocker, "out"))

    def test_a_rendered_name_the_output_folder_already_holds_is_refused_and_the_record_is_kept(self):
        os.makedirs(self.out)
        with open(os.path.join(self.out, "summary.md"), "w", encoding="utf-8") as handle:
            handle.write("someone else's file\n")
        self.refused("rendered-name")
        with open(os.path.join(self.out, "summary.md"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "someone else's file\n", "the foreign file is not replaced")
        self.assertIsNone(self.record()["merged"], "the units' results are kept to merge again")

    def test_a_merge_the_callers_checks_refuse_is_reported_with_what_to_do(self):
        self.write_caller(extra="""
            def checks(tables):
                return ["the verdicts table holds a row the caller does not allow"]
            """)
        status, out, _ = self.run_command()
        self.assertEqual(status, 1)
        self.assertIn("REFUSED | the verdicts table holds a row the caller does not allow", out)
        cause, action = command.CAUSES["merge-refused"]
        result = out.splitlines()[-1]
        self.assertTrue(result.startswith("RESULT | REFUSED"), result)
        self.assertIn(cause, result)
        self.assertIn(action, result)


class Coverage(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C11: every cause the command reports is documented as a cause and an action, and each is held to its
    # words by a test that provokes it
    def test_every_documented_cause_is_provoked_by_a_test_that_holds_the_line_to_its_words(self):
        with open(os.path.abspath(__file__), encoding="utf-8") as handle:
            source = handle.read()
        used = set(re.findall(r'refused\(\s*"([a-z-]+)"', source)) | set(re.findall(r'CAUSES\["([a-z-]+)"\]', source))
        self.assertEqual(sorted(set(command.CAUSES) - used), [], "a cause no test provokes")
        self.assertEqual(sorted(used - set(command.CAUSES)), [], "a test names a cause the command does not document")

    def test_every_cause_and_action_phrase_is_distinct_enough_to_tell_the_cause_from_its_action(self):
        for code, (cause, action) in command.CAUSES.items():
            with self.subTest(code=code):
                self.assertTrue(cause.strip() and action.strip())
                self.assertNotEqual(cause, action)


class AgentMissing(Case):
    # SOL-HW-REVIEW-KIT.C10: the exit status is 2 when the agent command line is missing, with a CANNOT RUN line naming the
    # cause and what to do
    def test_a_missing_agent_command_line_is_cannot_run_and_exit_2(self):
        with mock.patch.dict(os.environ, {ex.AGENT_ENV: os.path.join(self.base, "no-such-agent")}):
            text = self.refused("agent-missing", status=2, stream="err")
        self.assertIn(ex.AGENT_ENV, text)
        self.assertFalse(os.path.exists(self.out), "nothing was written")
        self.assertEqual(self.calls(), [])
        with mock.patch.dict(os.environ, {ex.AGENT_ENV: os.path.join(self.base, "no-such-agent")}):
            status, out, err = self.run_command(fmt="json")
        self.assertEqual(status, 2)
        report = json.loads(out)
        self.assertEqual(report["result"], "CANNOT RUN")
        self.assertIn("is not on the search path", report["cannot_run"])

    # SOL-HW-REVIEW-KIT.C10: and when it is not logged in
    def test_an_agent_command_line_that_is_not_logged_in_is_cannot_run_and_exit_2(self):
        self.scenario(logged_in=False)
        self.refused("agent-not-logged-in", status=2, stream="err")
        self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(self.out))

    def test_a_command_line_that_cannot_be_started_during_the_run_is_cannot_run_and_exit_2(self):
        self.scenario(vanish=True)
        self.refused("agent-not-started", status=2, stream="err")
        self.assertNotIn("run.lock", os.listdir(self.out))

    def test_a_refusal_comes_before_the_agent_is_looked_for(self):
        with mock.patch.dict(os.environ, {ex.AGENT_ENV: os.path.join(self.base, "no-such-agent")}):
            status, out, err = self.run_command("--bound", "0")
        self.assertEqual(status, 1, "a cause the command can see itself is refused first")
        self.assertIn("is below 1", out)

    def test_a_login_lost_during_the_run_is_cannot_run_and_leaves_no_lock_or_record(self):
        self.scenario(login_lost=True)
        status, out, err = self.run_command()
        self.assertEqual(status, 2)
        self.assertIn("is not logged in", err)
        self.assertIn("log it in, then run again", err)
        self.assertFalse(store.holds_record(self.out))
        self.assertNotIn("run.lock", os.listdir(self.out))
        self.assertTrue(os.path.isdir(os.path.join(self.out, "streams")), "the streams saved so far are kept")


class StaleLock(Case):
    # SOL-HW-REVIEW-KIT.C10: a lock left by a killed run is taken over when the process it names no longer exists, and the
    # report says so
    def test_a_lock_whose_process_is_gone_is_taken_over_and_reported(self):
        done = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
        os.makedirs(self.out)
        with open(os.path.join(self.out, "run.lock"), "w", encoding="utf-8") as handle:
            json.dump({"pid": int(done.stdout), "started": 0}, handle)
        status, out, err = self.run_command(fmt="json")
        self.assertEqual((status, err), (0, ""), out)
        notes = json.loads(out)["notes"]
        self.assertEqual(len(notes), 1)
        self.assertIn(f"left by process {done.stdout.strip()}", notes[0])
        self.assertNotIn("run.lock", os.listdir(self.out))

    def test_the_takeover_is_decided_by_the_process_check_and_leaves_a_live_or_unreadable_lock(self):
        os.makedirs(self.out)
        path = os.path.join(self.out, "run.lock")
        for content, alive, taken in (('{"pid": 4242}', False, True), ('{"pid": 4242}', True, False), ("garbage", False, False),
                                      ('{"pid": "x"}', False, False), ('{"pid": 0}', False, False), ('{"pid": true}', False, False)):
            with self.subTest(content=content, alive=alive):
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(content)
                note = command.take_over_stale_lock(self.out, lambda pid: alive)
                self.assertEqual(note is not None, taken)
                self.assertEqual(os.path.exists(path), not taken)
                if os.path.exists(path):
                    os.unlink(path)
        self.assertIsNone(command.take_over_stale_lock(self.out), "no lock, nothing to take over")
        self.assertTrue(command.process_alive(os.getpid()))


class RenderedKeys(Case):
    # SOL-HW-REVIEW-KIT.C10: the record carries the rendered and not_this_merge keys, so a later merge replaces only the files
    # an earlier one wrote and names the ones it left
    def test_a_rerun_that_renders_fewer_files_names_the_others_as_not_of_this_merge(self):
        os.environ["STUB_RENDER"] = "a.md,b.md"
        status, out, err = self.run_command()
        self.assertEqual(status, 0, err)
        self.assertEqual(self.record()["rendered"], ["a.md", "b.md"])
        os.environ["STUB_RENDER"] = "a.md"
        status, out, err = self.run_command("--rerun", "u1")
        self.assertEqual(status, 0, err)
        record = self.record()
        self.assertEqual((record["rendered"], record["not_this_merge"]), (["a.md"], ["b.md"]))
        self.assertIn("NOT THIS MERGE | b.md", out)
        self.assertTrue(os.path.exists(os.path.join(self.out, "b.md")), "a file of an earlier merge is left, not deleted")
        os.environ["STUB_RENDER"] = "a.md,b.md"
        status, out, err = self.run_command("--rerun", "u1")
        self.assertEqual(status, 0, err)
        self.assertEqual(self.record()["not_this_merge"], [], "and replaced again when this merge renders it")

    def test_a_failed_rerun_keeps_the_names_the_earlier_merge_rendered(self):
        self.assertEqual(self.run_command()[0], 0)
        self.scenario(bad_areas=["alpha"])
        self.assertEqual(self.run_command("--rerun", "u1")[0], 1)
        self.assertEqual(self.record()["rendered"], ["summary.md"])


def one_group():
    """The base declaration with every unit coupled to the others, so the plan has one group and one root."""
    raw = fx.declaration_dict()
    raw["units"]["u1"]["couples_with"] = ["u2"]
    raw["units"]["u4"]["couples_with"] = ["u1"]
    return raw


def group_tokens(case, raw):
    """The tokens each group's root holds for a declaration over the case's review folder, by group id."""
    declaration = decl.parse(json.dumps(raw), "caller.json")
    found = catalogue.admit(declaration, case.review)
    return {built.id: built.tokens for built in planner.form(declaration, found, None).groups}


class OtherModelReplica(Case):
    POLICY = """
        replica_policy = {"variants": [{"id": "full"}, {"id": "alt", "model": "other-model-id"}],
                          "replicas": {"low": 1, "normal": 2, "high": 2}}
        """
    #: The groups of the base declaration, their roots, and the items each judges: u2 and u3 are coupled, so three groups.
    ITEMS = {"G1": {"i1", "i2"}, "G2": {"j1", "k1", "k2"}, "G3": {"m1"}}
    WINDOWS = {"review-model-id": 1_000_000, "other-model-id": 1_000_000}

    def roots_and_forks(self):
        """Each root's call, and for each the forks that continue it with the group those forks judge."""
        calls = self.calls()
        roots = [call for call in calls if call["resume"] is None]
        group_of = {item: group for group, items in self.ITEMS.items() for item in items}
        held = {}
        for fork in (call for call in calls if call["resume"] is not None):
            groups = {group_of[item] for item in re.findall(r"^- (\S+)$", fork["text"], re.M) if item in group_of}
            held.setdefault(fork["resume"], []).append((fork, groups))
        return calls, roots, held

    # SOL-HW-REVIEW-KIT.C9: a replica declared for a model other than the review's has its own shared context and session
    # specification, which the command starts and the replica forks from, and shares no cache with the others
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: A review over several groups whose replica policy places a replica on a model other than the review's gives each group a root for each such model, held to that model's declared context budget, and each such replica is started from the root of its group and model
    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C17: replicas of a group are each started from that group's root, and the plan's total of tokens written counts the root once for the group and not once per replica
    def test_each_group_gets_a_root_for_each_model_and_each_replica_forks_from_the_root_of_its_group_and_model(self):
        self.write_caller(extra=self.POLICY)
        status, out, err = self.run_command("--model", "review-model-id")
        self.assertEqual((status, err), (0, ""), out)
        calls, roots, held = self.roots_and_forks()
        self.assertEqual(sorted(call["model"] for call in roots), ["other-model-id"] * 3 + ["review-model-id"] * 3,
                         "three groups, a root for each of the two models")
        first_fork = next(i for i, call in enumerate(calls) if call["resume"] is not None)
        self.assertTrue(all(call["resume"] is None for call in calls[:first_fork]), "every root is started before any fork")
        self.assertEqual(first_fork, 6)
        self.assertEqual(len(calls), 6 + 6, "six roots and a fork for each of the two replicas of three groups")
        for root in roots:
            forks = held[root["session"]]
            self.assertEqual(len(forks), 1, "one of the group's two replicas on each model's root")
            fork, groups = forks[0]
            self.assertTrue(fork["fork"])
            self.assertEqual(fork["model"], root["model"], "a fork continues the root of its own model")
            self.assertEqual(len(groups), 1, "a root's fork judges one group")
        sessions = {call["session"] for call in roots}
        self.assertTrue(all(call["resume"] in sessions for call in calls[first_fork:]), "no session starts from another session")
        by_group = {}
        for root in roots:
            (group,) = held[root["session"]][0][1]
            by_group.setdefault(group, set()).add(root["model"])
        self.assertEqual(by_group, {group: {"other-model-id", "review-model-id"} for group in self.ITEMS},
                         "each group has a root on each model")
        record = self.record()
        recorded = [node["id"] for node in record["nodes"] if node["role"] == "root"]
        self.assertEqual(recorded, [f"root.{group}{suffix}" for group in ("G1", "G2", "G3") for suffix in ("", ".other-model-id")])
        self.assertEqual([(c["root_id"], c["group"], c["model"], c["variants"]) for c in record["plan"]["contexts"]],
                         [(f"root.{group}.other-model-id", group, "other-model-id", ["alt"]) for group in ("G1", "G2", "G3")])
        self.assertTrue(all(c["spec_digest"] != record["plan"]["spec_digest"] for c in record["plan"]["contexts"]))
        parents = {node["id"]: node["parent"] for node in record["nodes"] if node["role"] == "unit"}
        self.assertEqual(sorted(parents.values()), sorted(recorded), "every root is the parent of exactly one fork")
        self.assertEqual({node["id"]: node["parent"] for node in record["nodes"] if node["role"] == "unit"}["G2.r2.a1"],
                         "root.G2.other-model-id", "a group's second replica is the variant on the other model")
        for group in record["plan"]["groups"]:
            self.assertEqual(group["root"], f"root.{group['id']}")
        rows = [row["Item"] for row in record["merged"]["tables"]["Verdicts"]["rows"]]
        self.assertEqual(sorted(rows), sorted(item for items in self.ITEMS.values() for item in items),
                         "the merged pass has exactly one verdict row for each item")
        for group in ("G1", "G2", "G3"):
            self.assertIn(f"CONTEXT | root.{group}.other-model-id | model other-model-id", out)
            self.assertIn(f"| group {group}", [line for line in out.splitlines() if f"root.{group}.other-model-id |" in line
                                               and line.startswith("CONTEXT")][0])
        status, out, err = self.run_command("--model", "review-model-id", out=os.path.join(self.base, "o2"), fmt="json")
        self.assertEqual((status, err), (0, ""), out)
        report = json.loads(out)
        labels = {session["label"] for session in report["sessions"]}
        self.assertTrue({f"root.{group}.other-model-id" for group in ("G1", "G2", "G3")} <= labels)
        self.assertEqual(len([session for session in report["sessions"] if session["role"] == "root"]), 6)
        plan = report["plan"]
        self.assertEqual(plan["predicted"]["tokens_written"], 2 * sum(group["tokens"] for group in plan["groups"]),
                         "each root counted once, one for each group and model, and not once per replica")
        self.assertEqual(len(plan["contexts"]), 3)
        verdicts = [row["Item"] for row in report["tables"]["Verdicts"]["rows"]]
        self.assertEqual(sorted(verdicts), sorted(rows))

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a fail raised by a replica on another model's root stands in the merged pass
    def test_a_fail_raised_by_the_replica_on_another_models_root_of_a_group_stands_in_the_merged_pass(self):
        self.write_caller(extra=self.POLICY.replace('{"id": "full"}', '{"id": "full"}, {"id": "third", "model": "other-model-id"}')
                          .replace('"high": 2', '"high": 3'))
        self.scenario(verdicts={"k1": "fail"})
        status, out, err = self.run_command("--model", "review-model-id")
        self.assertEqual(err, "")
        record = self.record()
        verdicts = {row["Item"]: row["Verdict"] for row in record["merged"]["tables"]["Verdicts"]["rows"]}
        self.assertEqual(verdicts["k1"], "fail")
        self.assertEqual({v for item, v in verdicts.items() if item != "k1"}, {"pass"})

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a group whose root for that model is over that model's budget is refused naming the group, the model, the figures and the budget
    def test_a_group_whose_root_for_another_model_is_over_that_models_budget_is_refused_naming_group_model_figures_and_budget(self):
        raw = fx.declaration_dict()
        sizes = group_tokens(self, raw)
        raw["budget"] = {"context_fraction": 0.5}
        largest = max(sizes, key=sizes.get)
        self.assertGreater(sorted(sizes.values())[-1], sorted(sizes.values())[-2], "one group is the largest")
        limit = sizes[largest] - 1
        windows = {"review-model-id": 10 * sizes[largest], "other-model-id": 2 * limit}
        self.write_caller(extra=self.POLICY, declaration=raw)
        with mock.patch.dict(costmodel.WINDOW_TOKENS_BY_MODEL, windows):
            text = self.refused("group-over-budget-model", "--model", "review-model-id")
            lines = [line for line in text.splitlines() if line.startswith("REFUSED")]
            self.assertEqual(len(lines), 1, text)
            self.assertIn(f"group {largest} ", lines[0])
            self.assertIn("for the model other-model-id", lines[0])
            self.assertIn(f"holds {sizes[largest]} tokens", lines[0])
            self.assertIn(f"budget of {limit} tokens, 1 over", lines[0])
            for other in set(sizes) - {largest}:
                self.assertNotIn(f"group {other} ", text)
            self.assertEqual(self.calls(), [], "no session starts")
            self.assertFalse(os.path.exists(self.out), "nothing was written")
            status, out, err = self.run_command("--model", "review-model-id", fmt="json", out=os.path.join(self.base, "j"))
            self.assertEqual((status, err), (1, ""))
            (refusal,) = json.loads(out)["refusals"]
            self.assertIn(f"group {largest} ", refusal)
            self.assertIn(f"holds {sizes[largest]} tokens in its root for the model other-model-id", refusal)
            self.assertIn(f"budget of {limit} tokens", refusal)
            self.assertEqual(self.calls(), [])
            with mock.patch.dict(costmodel.WINDOW_TOKENS_BY_MODEL, {"other-model-id": 2 * sizes[largest]}):
                status, out, err = self.run_command("--model", "review-model-id", "--plan-only", out=os.path.join(self.base, "p"))
            self.assertEqual((status, err), (0, ""), "the other model's window raised so that the largest group fits exactly: planned")

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a figure budget applies to every model's root, and a model with no declared window is refused naming it
    def test_a_figure_budget_holds_every_models_root_and_a_fraction_budget_of_a_model_without_a_window_is_refused_naming_it(self):
        raw = fx.declaration_dict()
        sizes = group_tokens(self, raw)
        largest = max(sizes, key=sizes.get)
        raw["budget"] = {"context_tokens": sizes[largest]}
        self.write_caller(extra=self.POLICY, declaration=raw)
        status, out, err = self.run_command("--model", "review-model-id", "--plan-only")
        self.assertEqual((status, err), (0, ""), "the largest group fits the figure exactly on both models' roots")
        raw["budget"] = {"context_fraction": 0.5}
        self.write_caller(extra=self.POLICY, declaration=raw, name="fraction")
        with mock.patch.dict(costmodel.WINDOW_TOKENS_BY_MODEL, {"review-model-id": 1_000_000}):
            text = self.refused("window-undeclared", "--model", "review-model-id", caller="fraction", out=os.path.join(self.base, "f"))
            self.assertIn("'other-model-id'", text)
            self.assertEqual(self.calls(), [])
            status, out, err = self.run_command("--model", "review-model-id", caller="fraction", fmt="json", out=os.path.join(self.base, "g"))
            self.assertEqual(status, 1)
            self.assertIn("the model 'other-model-id' has no declared context window", json.loads(out)["refusals"][0])

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C9: a rerun behaves as for replicas on one model: only the named unit's group runs, with its roots for each model
    def test_a_rerun_starts_only_the_roots_of_the_named_units_group_for_each_model_and_keeps_the_others(self):
        self.write_caller(extra=self.POLICY)
        self.assertEqual(self.run_command("--model", "review-model-id")[0], 0)
        before = len(self.calls())
        self.scenario(verdicts={"m1": "fail"})
        status, out, err = self.run_command("--model", "review-model-id", "--rerun", "u4")
        self.assertEqual((status, err), (0, ""), out)
        again = self.calls()[before:]
        self.assertEqual(sorted(call["model"] for call in again if call["resume"] is None), ["other-model-id", "review-model-id"],
                         "the root of that group for each model")
        self.assertEqual(len([call for call in again if call["resume"] is not None]), 2, "and its two replicas")
        record = self.record()
        self.assertEqual(sorted(node["id"] for node in record["nodes"] if node["role"] == "root"),
                         sorted(f"root.{group}{suffix}" for group in ("G1", "G2", "G3") for suffix in ("", ".other-model-id")),
                         "the other groups' roots stay in the record")
        verdicts = {row["Item"]: row["Verdict"] for row in record["merged"]["tables"]["Verdicts"]["rows"]}
        self.assertEqual(verdicts["m1"], "fail")
        self.assertEqual(len(record["merged"]["tables"]["Verdicts"]["rows"]), 6)
        self.assertEqual([run["kind"] for run in record["runs"]], ["fresh", "rerun"])
        self.write_caller(extra=self.POLICY.replace('"model": "other-model-id"', '"model": "another-model-id"'))
        text = self.refused("plan-changed", "--model", "review-model-id", "--rerun", "u4")
        self.assertEqual(len(self.calls()), before + 4, "a rerun over other roots than the recorded is refused before any session")

    def test_the_guard_allows_the_other_models_specification_and_still_refuses_any_other_change(self):
        harness = fx.Harness(self, replicas=2)
        policy = ensemble.parse_policy({"variants": [{"id": "full"}, {"id": "alt", "model": "other"}]})
        found = ensemble.group_contexts(harness.spec, harness.formed.groups, policy)
        plan = planner.make_plan(harness.declaration, catalogue.admit(harness.declaration, harness.review), harness.spec, bound=4,
                                 cli_version="1", tool_commit="c", replicas=2, variants=policy.ids, contexts=found,
                                 formed=harness.formed)
        labels = [built.root for built in harness.formed.groups] + [f"{built.root}.other" for built in harness.formed.groups]
        writes = {label: 100 + number for number, label in enumerate(labels)}

        def reply(call, number):
            if call.label.startswith("root"):
                return ex.Reply(text=messages.ACK, write=writes[call.label])
            group = next(g for g in plan.groups if g.id == call.label.split(".")[0])
            return ex.Reply(structured=fx.good_answer(harness.declaration, group.units), text="done")

        executor = ex.StubExecutor(replies=reply, clock=harness.clock)
        runner = scheduler.Scheduler(executor, harness.clock)
        result = runner.run(harness.declaration, plan, harness.roots, harness.spec,
                            ensemble.prompt_for(harness.declaration, policy), contexts=found)
        self.assertEqual(sorted(root["id"] for root in [result.root] + result.extra_roots), sorted(labels))
        roots = {call.label: call for call in executor.calls if not call.fork and call.parent is None}
        self.assertEqual(sorted(roots), sorted(labels))
        self.assertTrue(all(roots[label].spec.model == "other" for label in labels if label.endswith(".other")))
        self.assertTrue(all(roots[label].spec.model == harness.spec.model for label in labels if not label.endswith(".other")))
        forks = [call for call in executor.calls if call.fork]
        self.assertEqual(len(forks), sum(g.replicas for g in plan.groups))
        for fork in forks:
            group = next(g for g in plan.groups if g.id == fork.label.split(".")[0])
            wanted = f"{group.root}.other" if fork.spec.model == "other" else group.root
            self.assertEqual(executor.sessions[fork.parent]["prefix"], writes[wanted],
                             "a fork continues the root of its own group and model, which only that root wrote")
        self.assertEqual({fork.spec.model for fork in forks}, {"other", harness.spec.model})
        self.assertEqual({call.spec.digest for call in forks if call.spec.model == "other"}, {found[1].spec.digest})
        other = next(c for c in executor.calls if c.label.endswith(".other"))
        with self.assertRaises(sess.SpecChanged):
            executor.run(sess.Call(dataclasses.replace(other.spec, system="another system prompt"), harness.shared.message, label="x"))
        with self.assertRaises(sess.SpecChanged):
            executor.run(sess.Call(dataclasses.replace(harness.spec, tools=("Read",)), harness.shared.message, label="y"))

    def test_a_plan_with_other_contexts_cannot_be_run_without_them(self):
        harness = fx.Harness(self, replicas=2)
        policy = ensemble.parse_policy({"variants": [{"id": "full"}, {"id": "alt", "model": "other"}]})
        found = ensemble.group_contexts(harness.spec, harness.formed.groups, policy)
        admitted = catalogue.admit(harness.declaration, harness.review)
        plan = planner.make_plan(harness.declaration, admitted, harness.spec, bound=4, cli_version="1", tool_commit="c",
                                 replicas=2, variants=policy.ids, contexts=found, formed=harness.formed)
        self.assertEqual(sorted(root.id for root in plan.roots),
                         sorted([built.root for built in harness.formed.groups] + [f"{built.root}.other" for built in harness.formed.groups]))
        again = planner.Plan.from_dict(json.loads(json.dumps(plan.to_dict())))
        self.assertEqual(again.contexts, plan.contexts, "the plan record round-trips the contexts")
        with self.assertRaises(ValueError) as caught:
            harness.scheduler.run(harness.declaration, plan, harness.roots, harness.spec)
        self.assertIn("6 roots", str(caught.exception))
        with self.assertRaises(ValueError):
            planner.make_plan(harness.declaration, admitted, harness.spec, bound=4, cli_version="1", tool_commit="c",
                              replicas=2, variants=["full", "unheld"], contexts=found, formed=harness.formed)


class GroupRoots(Case):
    """Each group is judged from a root of its own, held to the context budget, and the plan can be made without a session."""

    def budgeted(self, budget, raw=None, name="budgeted"):
        raw = raw or fx.declaration_dict()
        raw["budget"] = dict(budget)
        self.write_caller(declaration=raw, name=name)
        return name

    def group_tokens(self, raw):
        declaration = decl.parse(json.dumps(raw), "caller.json")
        found = catalogue.admit(declaration, self.review)
        return {built.id: built.tokens for built in planner.form(declaration, found, None).groups}

    def merging(self):
        """The base declaration with a budget under which u4 (whose needs u1's include) merges into u1's group and the group of
        u2 and u3 stays apart. The units' expected outputs let u1 and u4 meet the largest single unit's together."""
        raw = fx.declaration_dict()
        raw["units"]["u1"]["expected_output_tokens"] = 300
        raw["units"]["u2"]["expected_output_tokens"] = 400
        raw["budget"] = {"context_tokens": 8500}
        return raw

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C2: a group whose own artefacts, measured by the kit's existing token measure, added to the shared documents measure more than the budget is refused before any session starts, the refusal naming the group, its size in tokens and the budget; over a declaration with several oversize groups, every one is named; the command prints a REFUSED line naming the cause and what to do, exits 1, and starts no session
    def test_every_group_over_the_budget_is_named_with_its_size_and_the_budget_and_no_session_starts(self):
        sizes = self.group_tokens(fx.declaration_dict())
        budget = sizes["G3"] + 10
        self.assertLess(budget, sizes["G1"], "the declaration has a group that fits and two that do not")
        name = self.budgeted({"context_tokens": budget})
        text = self.refused("group-over-budget", caller=name)
        lines = [line for line in text.splitlines() if line.startswith("REFUSED")]
        self.assertEqual(len(lines), 2, text)
        self.assertIn(f"group G1 (unit u1 alone) holds {sizes['G1']} tokens", lines[0])
        self.assertIn(f"group G2 (units u2, u3, which the declaration couples) holds {sizes['G2']} tokens", lines[1])
        for line in lines:
            self.assertIn(f"budget of {budget} tokens", line)
        self.assertNotIn("G3", text)
        self.assertNothingStarted()
        self.assertFalse(os.path.exists(self.out), "nothing was written")
        status, out, err = self.run_command(caller=name, fmt="json", out=os.path.join(self.base, "json"))
        self.assertEqual((status, err), (1, ""))
        report = json.loads(out)
        self.assertEqual([line.split(" holds ")[0] for line in report["refusals"]],
                         ["group G1 (unit u1 alone)", "group G2 (units u2, u3, which the declaration couples)"])
        self.assertNothingStarted()

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C2: a group that fits exactly is accepted
    def test_a_group_that_fits_the_budget_exactly_is_accepted_and_one_token_less_is_refused(self):
        raw = one_group()
        size = self.group_tokens(raw)["G1"]
        name = self.budgeted({"context_tokens": size}, raw)
        status, out, err = self.run_command("--plan-only", caller=name)
        self.assertEqual((status, err), (0, ""), out)
        self.assertIn(f"{size} tokens | budget {size} | margin 0", out)
        name = self.budgeted({"context_tokens": size - 1}, raw, "tight")
        text = self.refused("group-over-budget", "--plan-only", caller=name, out=os.path.join(self.base, "o2"))
        self.assertIn(f"holds {size} tokens in its root, more than the review's context budget of {size - 1} tokens, 1 over", text)

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C3: a plan-only invocation writes the plan and the report, exits 0 and starts no session, or exits 1 with the refusal when a group is over the budget
    def test_a_plan_only_invocation_writes_the_plan_and_the_report_and_starts_no_session(self):
        raw = self.merging()
        name = self.budgeted(raw["budget"], raw)
        sizes = self.group_tokens(raw)
        os.environ.pop(ex.AGENT_ENV)
        status, out, err = self.run_command("--plan-only", caller=name)
        self.assertEqual((status, err), (0, ""), "no agent program is asked for")
        self.assertEqual(self.calls(), [])
        self.assertEqual(sorted(os.listdir(self.out)), ["plan.json"], "no record, no streams and no lock")
        self.assertTrue(out.splitlines()[-1].startswith("RESULT | PLANNED"), out)
        self.assertIn("AGENT", "".join(self.lines(out, "AGENT")) or "AGENT")
        plan = store_plan(self.out)
        self.assertEqual([g["tokens"] for g in plan["groups"]], [sizes[g["id"]] for g in plan["groups"]])
        self.assertEqual(plan["budget"], {"tokens": 8500, "fraction": None, "window": None, "model": None})
        self.assertEqual([g["units"] for g in plan["groups"]], [["u1", "u4"], ["u2", "u3"]])
        status, as_json, err = self.run_command("--plan-only", "--format", "json", caller=name, out=os.path.join(self.base, "j"), skip=("--format", "text"))
        self.assertEqual((status, err), (0, ""))
        report = json.loads(as_json)
        self.assertEqual(report["result"], "PLANNED")
        self.assertIsNone(report["agent"])
        self.assertEqual(report["sessions"], [])

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C3: the plan record and the report, in text and in JSON with the same content, give the shared documents' tokens, then for each group the number of images and the tokens its sessions hold in all, the budget they are held to and the margin; the predicted cost counts each group's root as written once for the group
    def test_the_plan_report_gives_each_groups_images_tokens_budget_and_margin_the_same_in_text_and_json(self):
        raw = self.merging()
        name = self.budgeted(raw["budget"], raw)
        status, out, err = self.run_command("--plan-only", caller=name, fmt="json")
        self.assertEqual((status, err), (0, ""))
        plan = json.loads(out)["plan"]
        self.assertEqual(plan["shared_tokens"], messages.shared_context(catalogue.Catalogue(())).tokens, "no artefact is needed by every unit")
        self.assertEqual([g["images"] for g in plan["groups"]], [1, 1])
        for group in plan["groups"]:
            self.assertEqual(group["budget"], 8500)
            self.assertEqual(group["margin"], 8500 - group["tokens"])
        self.assertEqual(plan["predicted"]["tokens_written"], sum(g["tokens"] for g in plan["groups"]), "each root once, whatever the replicas")
        status, text, err = self.run_command("--plan-only", caller=name, out=os.path.join(self.base, "t"))
        groups = self.lines(text, "GROUP")
        self.assertEqual(len(groups), 2)
        for line, group in zip(groups, plan["groups"]):
            self.assertIn(f"| {group['images']} images | {group['tokens']} tokens | budget 8500 | margin {group['margin']} |", line)
        self.assertIn(f"shared documents {plan['shared_tokens']} tokens | context budget 8500 tokens", "".join(self.lines(text, "PLAN")))
        self.assertIn(f"{plan['predicted']['tokens_written']} tokens written", "".join(self.lines(text, "PREDICTED")))

    # SOL-HW-REVIEW-KIT-SESSIONS-HOLD-ONLY-THEIR-GROUP-IMAGES.C3: exits 1 with the refusal when a group is over the budget
    def test_a_plan_only_invocation_over_the_budget_exits_1_with_the_refusal_and_writes_no_plan(self):
        name = self.budgeted({"context_tokens": 2000})
        os.environ.pop(ex.AGENT_ENV)
        text = self.refused("group-over-budget", "--plan-only", caller=name)
        self.assertNotIn("RESULT | PLANNED", text)
        self.assertFalse(os.path.exists(self.out))

    def test_plan_only_and_rerun_together_are_refused(self):
        self.refused("plan-only-rerun", "--plan-only", "--rerun", "u1")
        self.assertNothingStarted()

    def test_a_plan_only_run_in_an_output_folder_that_cannot_be_written_is_refused(self):
        blocker = os.path.join(self.base, "blocker")
        with open(blocker, "w", encoding="utf-8") as handle:
            handle.write("a file where a folder is needed")
        self.refused("output-unwritable", "--plan-only", out=os.path.join(blocker, "inside"))

    def test_plan_only_is_in_the_help(self):
        text = command.parser().format_help()
        self.assertIn("--plan-only", text)
        self.assertIn("without the agent program and without starting a session", " ".join(text.split()))

    def assertNothingStarted(self):
        self.assertEqual(self.calls(), [])
        self.assertFalse(os.path.exists(os.path.join(self.out, "run.lock")))


def store_plan(out):
    with open(os.path.join(out, store.PLAN_NAME), encoding="utf-8") as handle:
        return json.load(handle)


class Options(Case):
    # SOL-HW-REVIEW-KIT.C10: a replicas override and a bound change the plan
    def test_the_replicas_override_and_the_bound_change_the_plan(self):
        status, out, err = self.run_command("--replicas", "1", "--bound", "2", fmt="json")
        self.assertEqual(status, 0, err)
        plan = json.loads(out)["plan"]
        self.assertEqual((plan["forks"], plan["bound"]), (len(plan["groups"]), 2))
        self.assertTrue(all(group["replicas"] == 1 for group in plan["groups"]))
        status, out, _ = self.run_command("--replicas", "3", out=os.path.join(self.base, "o3"), fmt="json")
        self.assertEqual(json.loads(out)["plan"]["forks"], 3 * len(plan["groups"]))
        self.assertEqual(json.loads(out)["plan"]["bound"], 3 * len(plan["groups"]), "the default bound runs every fork at once")

    def planned_bound(self, *extra, caller_extra=None, out=None):
        if caller_extra is not None:
            self.write_caller(extra=caller_extra)
        status, text, err = self.run_command(*extra, out=out, fmt="json")
        self.assertEqual(status, 0, text + err)
        plan = json.loads(text)["plan"]
        return plan["bound"], plan["forks"]

    # SOL-HW-REVIEW-KIT.C13: a caller's optional bound is the most sessions at once, the plan's forks when it is absent
    def test_the_callers_bound_defaults_to_every_fork_and_a_valid_one_sets_the_bound_never_above_the_forks(self):
        bound, forks = self.planned_bound()
        self.assertEqual(bound, forks, "absent: every fork at once")
        self.assertGreater(forks, 1)
        shutil.rmtree(self.out)
        self.assertEqual(self.planned_bound(caller_extra="bound = 1\n"), (1, forks))
        shutil.rmtree(self.out)
        self.assertEqual(self.planned_bound(caller_extra="bound = None\n"), (forks, forks), "None is absent")
        shutil.rmtree(self.out)
        self.assertEqual(self.planned_bound(caller_extra=f"bound = {forks + 50}\n"), (forks, forks), "never above the forks")

    def test_the_bound_flag_overrides_the_callers_bound(self):
        # SOL-HW-REVIEW-KIT.C13: the command's --bound overrides the caller's bound
        self.assertEqual(self.planned_bound("--bound", "2", caller_extra="bound = 1\n")[0], 2)

    def test_an_invalid_caller_bound_is_refused_naming_the_caller_and_the_attribute(self):
        # SOL-HW-REVIEW-KIT.C13: a bound that is not a whole number of 1 or more is refused naming the caller and the attribute
        for source in ("0", "-2", "1.5", "'many'", "True", "[3]"):
            with self.subTest(bound=source):
                self.write_caller(extra=f"bound = {source}\n")
                status, out, err = self.run_command()
                self.assertEqual(status, 1, out + err)
                line = next(line for line in out.splitlines() if line.startswith("REFUSED"))
                self.assertIn("the caller demo", line)
                self.assertIn("gives bound", line)
                self.assertIn("whole number of 1 or more", line)
        self.assertEqual(self.calls(), [], "no session was started")
        self.write_caller(extra="bound = 0\n")
        status, out, err = self.run_command(fmt="json")
        self.assertEqual(status, 1)
        self.assertTrue(any("gives bound" in line for line in json.loads(out)["refusals"]))

    def test_a_model_flag_is_given_to_every_session_as_a_full_model_id(self):
        self.assertEqual(self.run_command("--model", "a-full-model-id")[0], 0)
        self.assertEqual({c["model"] for c in self.calls()}, {"a-full-model-id"})
        self.assertTrue(all(c["args"][c["args"].index("--model") + 1] == "a-full-model-id" for c in self.calls()))

    def test_a_model_the_price_table_lacks_is_noted_as_priced_at_the_default(self):
        # SOL-HW-REVIEW-KIT.C6: the prices are data by model; a model with no entry is priced at the default and the plan says so
        status, out, err = self.run_command("--model", "a-full-model-id", fmt="json")
        self.assertEqual(status, 0, err)
        notes = json.loads(out)["notes"]
        self.assertEqual(len([n for n in notes if "price table" in n]), 1)
        self.assertIn("'a-full-model-id'", [n for n in notes if "price table" in n][0])
        self.assertIn("priced at the default", "\n".join(notes))
        shutil.rmtree(self.out)
        status, out, err = self.run_command("--model", "claude-haiku-5-5", fmt="json")
        self.assertEqual(status, 0, err)
        self.assertEqual([n for n in json.loads(out)["notes"] if "price table" in n], [])
        shutil.rmtree(self.out)
        status, out, err = self.run_command(fmt="json")
        self.assertEqual([n for n in json.loads(out)["notes"] if "price table" in n], [], "no model flag leaves the model to the agent")

    def cannot_judge_turns(self):
        return [c["text"] for c in self.calls() if c["resume"] is not None and not c["fork"] and "You gave cannot judge" in c["text"]]

    def test_the_cannot_judge_turn_advises_retrieval_when_the_caller_grants_the_tool_and_does_not_otherwise(self):
        # SOL-HW-REVIEW-KIT.C6: a cannot judge in the first answer appends one repair turn advising retrieval with the retrieval tool the caller grants and otherwise to keep the cannot judge naming the view or document it needs
        self.scenario(verdicts={"i1": "cannot judge"})
        self.write_caller(extra="retrieval = True\n")
        self.run_command()
        granted = self.cannot_judge_turns()
        self.assertTrue(granted)
        self.assertTrue(all("retrieval tool you have" in turn for turn in granted))
        shutil.rmtree(self.out)
        os.remove(self.log)
        self.write_caller()
        self.run_command()
        plain = self.cannot_judge_turns()
        self.assertEqual(len(plain), len(granted), "the turn still applies")
        for turn in plain:
            self.assertIn("i1:", turn)
            self.assertIn("name the view or document you need", turn)
            self.assertNotIn("retriev", turn)

    def test_every_session_is_started_in_the_review_folder_with_one_set_of_flags(self):
        self.assertEqual(self.run_command()[0], 0)
        calls = self.calls()
        self.assertTrue(all(os.path.realpath(c["cwd"]) == os.path.realpath(self.review) for c in calls))
        def stripped(call):
            args = list(call["args"])
            for flag in ("--resume",):
                if flag in args:
                    del args[args.index(flag):args.index(flag) + 2]
            return [a for a in args if a != "--fork-session"]
        self.assertEqual(len({json.dumps(stripped(c)) for c in calls}), 1, "only the resume differs between sessions")

    def test_the_streams_are_saved_verbatim_beside_the_record(self):
        self.assertEqual(self.run_command()[0], 0)
        folder = os.path.join(self.out, "streams")
        saved = [n for n in os.listdir(folder) if n.endswith(".jsonl")]
        self.assertEqual(len(saved), len(self.calls()))


class Entry(unittest.TestCase):
    def test_the_wrapper_runs_the_command_and_exits_with_its_status(self):
        wrapper = os.path.join(TOOLS, "review_run.py")
        done = subprocess.run([sys.executable, wrapper, "--help"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0)
        self.assertIn("--review", done.stdout)
        done = subprocess.run([sys.executable, wrapper], capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertTrue(done.stdout.startswith("REFUSED | "), done.stdout)



class NamedFailVerdict(Case):
    def named(self, name):
        self.write_caller(extra=f"fail_verdict = {name!r}\n", declaration=fx.verdict_declaration_dict())
        self.scenario(verdicts={item: "matches" for item in ("i1", "i2", "j1", "k1", "k2", "m1")})

    def test_a_name_outside_the_verdicts_of_the_table_is_refused_before_any_session_starts(self):
        # SOL-HW-REVIEW-KIT.C15: Over synthetic declarations and a stub executor, a caller may name which of its verdicts is its fail verdict, a verdict of the verdict set of a table it declares; the kit then treats that verdict exactly as it treats fail: replicas are merged any-fail with it standing over a passing verdict, and no repair turn, cannot-judge turn or rerun clears it, the refusal naming the item and the verdict. A caller naming none keeps fail as its fail verdict, and a caller that names fail behaves as one that names none. A name carried by the verdict set of at least one table that has a key and a verdict column is accepted, a table whose verdict set lacks the name having no fail to hold. A name outside the verdicts of every such table is refused before any session starts, the refusal naming it and listing each verdict table with its verdict set, or saying that the declaration has no verdict table. A name that is not text or is blank is refused when the caller loads, naming the caller and the attribute, and so is the name cannot judge, naming the attribute, since the merge and the cannot-judge turn would otherwise collapse the two verdicts. Out of scope: any real caller.
        self.named("broken")
        status, out, err = self.run_command()
        self.assertEqual(status, 1, out + err)
        line = next(line for line in out.splitlines() if line.startswith("REFUSED"))
        self.assertIn("'broken'", line)
        self.assertIn("table 'Verdicts'", line)
        self.assertIn("the caller demo", line)
        self.assertEqual(self.calls(), [], "no session was started")
        self.assertFalse(os.path.exists(self.out))
        status, out, err = self.run_command(fmt="json")
        self.assertEqual(status, 1)
        self.assertIn("table 'Verdicts'", json.loads(out)["refusals"][0])

    def test_a_run_for_a_caller_naming_a_verdict_merges_it_and_renders_it(self):
        # SOL-HW-REVIEW-KIT.C15: Over synthetic declarations and a stub executor, a caller may name which of its verdicts is its fail verdict, a verdict of the verdict set of a table it declares; the kit then treats that verdict exactly as it treats fail: replicas are merged any-fail with it standing over a passing verdict, and no repair turn, cannot-judge turn or rerun clears it, the refusal naming the item and the verdict. A caller naming none keeps fail as its fail verdict, and a caller that names fail behaves as one that names none. A name carried by the verdict set of at least one table that has a key and a verdict column is accepted, a table whose verdict set lacks the name having no fail to hold. A name outside the verdicts of every such table is refused before any session starts, the refusal naming it and listing each verdict table with its verdict set, or saying that the declaration has no verdict table. A name that is not text or is blank is refused when the caller loads, naming the caller and the attribute, and so is the name cannot judge, naming the attribute, since the merge and the cannot-judge turn would otherwise collapse the two verdicts. Out of scope: any real caller.
        self.named("differs")
        self.scenario(verdicts={"i1": "differs", "i2": "matches", "j1": "matches", "k1": "matches", "k2": "matches",
                                "m1": "matches"})
        status, out, err = self.run_command()
        self.assertEqual((status, err), (0, ""), out)
        with open(os.path.join(self.out, "summary.md"), encoding="utf-8") as handle:
            rendered = handle.read().splitlines()
        self.assertIn("i1: differs", rendered)
        self.assertIn("i2: matches", rendered)


if __name__ == "__main__":
    unittest.main()
