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
from review_kit import catalogue, command, ensemble, messages, planner, scheduler, store  # noqa: E402
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
        self.assertEqual(len(roots), 1, "the shared context is started once")
        self.assertEqual(calls[0]["resume"], None, "and before any fork")
        for fork in (c for c in calls if c["resume"] is not None):
            self.assertEqual(fork["resume"], roots[0]["session"])
            self.assertTrue(fork["fork"])
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
        self.assertEqual(len(self.lines(out, "SESSION")), 1 + len(forks), "each session's own figures")

    # SOL-HW-REVIEW-KIT.C10: the figures written into the output folder are each session's own: a fork's reported cost less
    # its parent's, and the run's, with the predicted against the actual
    def test_the_figures_are_each_sessions_own_and_the_runs_against_the_prediction(self):
        status, out, err = self.run_command(fmt="json")
        self.assertEqual(status, 0, err)
        report = json.loads(out)
        sessions = {s["label"]: s for s in report["sessions"]}
        root = sessions["root"]
        self.assertAlmostEqual(root["cost_usd"], 0.01)
        forks = [s for label, s in sessions.items() if label != "root"]
        for fork in forks:
            self.assertAlmostEqual(fork["cost_usd"], 0.02, msg="reported 0.03 cumulatively, 0.01 of it the parent's")
            self.assertEqual(fork["parent"], "root")
            self.assertEqual(fork["first_call_read"], 1000)
            self.assertEqual(fork["tokens"]["cache_read"], 1000)
        run = report["run"]
        self.assertAlmostEqual(run["cost_usd"], 0.01 + 0.02 * len(forks))
        self.assertEqual(run["sessions"], 1 + len(forks))
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
        self.assertEqual([c["resume"] for c in self.calls()], [None])
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


class OtherModelReplica(Case):
    POLICY = """
        replica_policy = {"variants": [{"id": "full"}, {"id": "alt", "model": "other-model-id"}],
                          "replicas": {"low": 1, "normal": 2, "high": 2}}
        """

    # SOL-HW-REVIEW-KIT.C9: a replica declared for a model other than the review's has its own shared context and session
    # specification, which the command starts and the replica forks from, and shares no cache with the others
    def test_a_replica_on_another_model_gets_its_own_root_session_and_forks_from_it(self):
        self.write_caller(extra=self.POLICY)
        status, out, err = self.run_command("--model", "review-model-id")
        self.assertEqual((status, err), (0, ""), out)
        calls = self.calls()
        roots = [c for c in calls if c["resume"] is None]
        self.assertEqual(sorted(c["model"] for c in roots), ["other-model-id", "review-model-id"])
        first_fork = next(i for i, c in enumerate(calls) if c["resume"] is not None)
        self.assertTrue(all(c["resume"] is None for c in calls[:first_fork]), "every root is started before any fork")
        self.assertEqual(first_fork, 2)
        by_session = {c["session"]: c for c in roots}
        forks = [c for c in calls if c["resume"] is not None]
        self.assertTrue(forks)
        for fork in forks:
            self.assertEqual(by_session[fork["resume"]]["model"], fork["model"], "a fork continues the root of its own model")
        self.assertEqual({f["model"] for f in forks}, {"other-model-id", "review-model-id"})
        record = self.record()
        roots_recorded = [n for n in record["nodes"] if n["role"] == "root"]
        self.assertEqual([n["id"] for n in roots_recorded], ["root", "root.other-model-id"])
        self.assertEqual(len(record["plan"]["contexts"]), 1)
        context = record["plan"]["contexts"][0]
        self.assertEqual((context["root_id"], context["model"], context["variants"]), ("root.other-model-id", "other-model-id", ["alt"]))
        self.assertNotEqual(context["spec_digest"], record["plan"]["spec_digest"])
        parents = {n["id"]: n["parent"] for n in record["nodes"] if n["role"] == "unit"}
        self.assertEqual(sorted(set(parents.values())), ["root", "root.other-model-id"])
        self.assertIn("CONTEXT | root.other-model-id | model other-model-id", out)
        figures = {s["label"] for s in json.loads(self.run_command("--model", "review-model-id", out=os.path.join(self.base, "o2"), fmt="json")[1])["sessions"]}
        self.assertIn("root.other-model-id", figures)

    def test_the_guard_allows_the_other_models_specification_and_still_refuses_any_other_change(self):
        harness = fx.Harness(self, replicas=2)
        policy = ensemble.parse_policy({"variants": [{"id": "full"}, {"id": "alt", "model": "other"}]})
        found = ensemble.contexts(harness.spec, harness.shared, policy)
        plan = planner.make_plan(harness.declaration, catalogue.admit(harness.declaration, harness.review), harness.shared,
                                 harness.spec, bound=4, cli_version="1", tool_commit="c", replicas=2, variants=policy.ids,
                                 contexts=found)

        def reply(call, number):
            if call.label.startswith("root"):
                return ex.Reply(text=messages.ACK, write=100)
            group = next(g for g in plan.groups if g.id == call.label.split(".")[0])
            return ex.Reply(structured=fx.good_answer(harness.declaration, group.units), text="done")

        executor = ex.StubExecutor(replies=reply, clock=harness.clock)
        runner = scheduler.Scheduler(executor, harness.clock)
        result = runner.run(harness.declaration, plan, harness.shared, harness.spec,
                            ensemble.prompt_for(harness.declaration, policy), contexts=found)
        self.assertEqual([root["id"] for root in [result.root] + result.extra_roots], ["root", "root.other"])
        roots = {call.label: call for call in executor.calls if not call.fork and call.parent is None}
        self.assertEqual(roots["root.other"].spec.model, "other")
        self.assertEqual(roots["root"].spec.model, harness.spec.model)
        session_of = {}
        for call, args in zip(executor.calls, executor.arguments):
            if call.label in roots:
                session_of[call.label] = next(s for s, held in executor.sessions.items() if s not in session_of.values())
        forks = [call for call in executor.calls if call.fork]
        self.assertEqual(len(forks), sum(g.replicas for g in plan.groups))
        for fork in forks:
            wanted = "root.other" if fork.spec.model == "other" else "root"
            self.assertEqual(fork.parent, session_of[wanted], "a fork continues the root of its own model's context")
        self.assertEqual({fork.spec.model for fork in forks}, {"other", harness.spec.model})
        self.assertEqual({call.spec.digest for call in forks if call.spec.model == "other"}, {found[1].spec.digest})
        for fork in forks:
            first_read = executor.sessions[fork.parent]["prefix"]
            self.assertGreater(first_read, 0, "each fork reads its own root's prefix, which only its own root wrote")
        other = next(c for c in executor.calls if c.label == "root.other")
        with self.assertRaises(sess.SpecChanged):
            executor.run(sess.Call(dataclasses.replace(other.spec, system="another system prompt"), harness.shared.message, label="x"))
        with self.assertRaises(sess.SpecChanged):
            executor.run(sess.Call(dataclasses.replace(harness.spec, tools=("Read",)), harness.shared.message, label="y"))

    def test_a_plan_with_other_contexts_cannot_be_run_without_them(self):
        harness = fx.Harness(self, replicas=2)
        policy = ensemble.parse_policy({"variants": [{"id": "full"}, {"id": "alt", "model": "other"}]})
        found = ensemble.contexts(harness.spec, harness.shared, policy)
        plan = planner.make_plan(harness.declaration, catalogue.admit(
            harness.declaration, harness.review), harness.shared, harness.spec, bound=4, cli_version="1", tool_commit="c",
            replicas=2, variants=policy.ids, contexts=found)
        self.assertEqual([root.id for root in plan.roots], ["root", "root.other"])
        again = planner.Plan.from_dict(json.loads(json.dumps(plan.to_dict())))
        self.assertEqual(again.contexts, plan.contexts, "the plan record round-trips the contexts")
        with self.assertRaises(ValueError) as caught:
            harness.scheduler.run(harness.declaration, plan, harness.shared, harness.spec)
        self.assertIn("2 shared contexts", str(caught.exception))
        with self.assertRaises(ValueError):
            planner.make_plan(harness.declaration, catalogue.admit(
                harness.declaration, harness.review), harness.shared, harness.spec, bound=4, cli_version="1", tool_commit="c",
                replicas=2, variants=["full", "unheld"], contexts=found)


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


if __name__ == "__main__":
    unittest.main()
