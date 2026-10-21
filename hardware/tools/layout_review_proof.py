#!/usr/bin/env python3
"""Run the layout review's single-reviewer form and its fanned-out form on one seeded copy, and compare them.

The layout review proof seeds known defects into a copy of the proof design
(review_seed.py) and has a reviewer that did not design the board follow the
method's review step blind. This command does that for the two forms of a round,
on the same copy, with the same four tools, so the fanned-out form is shown to
find what the single reviewer finds, in no more time and at no more cost.

It runs the seeding command with its opt-in flag that keeps the seeded copy's git
work tree, writes the review folder with the folder command from that work tree
and its commit, the method and the hardware notes taken from this repository as the
seeding command takes them, then runs one reviewer on the folder and the fan-out
command's layout caller on the same folder, one reviewer for each unit at the full
unit count, all running together. Both forms are started through the tap
(review_agent_tap.py), which keeps each call's time, the documents it retrieved
and whether any retrieval failed, and whether it was refused for a rate limit.

    layout_review_proof.py --work <new folder outside the repository> [--kicad-cli ...] [--resvg ...]
                           [--model M] [--bound N] [--rate-limit-wait S] [--json]

It writes proof-report.json in the folder and prints, for the setup session and
every unit and for each run, the wall time, the tokens read from the cache,
written to it and generated, the cost, the retrievals and the failed ones; every
seed with whether each form reported it as a finding against the catalogue item
that covers it; the findings that match no seed and the items the forms judged
differently, for a difference to be explained; whether the fanned-out run took no
more time and cost no more; and what the run observed to set the layout caller's
bound on reviewers at once from: the most reviewers that ran together and the
calls refused for a rate limit. It decides nothing: whether a seed not reported
is a gap, and where it is closed, is the review of the report.

    layout_review_proof.py --fanned-only <an earlier run's work folder> [--model M] [--bound N] [--rate-limit-wait S] [--json]

With --fanned-only the single reviewer is not started. The command reuses the single result the earlier run kept (proof-report.json,
single/answer.md and seeds.json in that folder) and runs the fanned-out form alone, on the earlier run's review folder and so on the
same seeded copy, into the first unused folder fanned-2, fanned-3 and so on inside it. If that left units failed, only those are run
once more into the same folder with the fan-out command's rerun. It writes proof-report-<n>.json beside the earlier report and
prints the same lines, with the reuse stated and the wall time and cost of the run and of the rerun apart and added. It refuses,
starting no session, when the folder lacks a piece it reuses or the earlier single result recorded a problem.

The agent command line is the program named by REVIEW_FAN_OUT_AGENT (claude when
it is unset), logged in. A run costs money: it starts one session for the single
reviewer and a setup session and a reviewer for each unit.

Each cause is reported on one line beginning REFUSED, a RESULT line comes last,
and the exit status is 0 when both forms ran and the report is written, 1 when the
command refuses or a form fails, and 2 when a tool or the agent command line is
missing. --json prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import time
from typing import Any, Dict, Iterator, List, Optional, Sequence

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_check  # noqa: E402
import board_review_history  # noqa: E402
import review_agent_tap  # noqa: E402
import review_caller_layout  # noqa: E402
import review_fan_out  # noqa: E402
import review_folder  # noqa: E402
import review_seed  # noqa: E402

REPO = review_seed.REPO
SEEDED = "seeded-review"
KEPT_TREE = "seeded-work"
FOLDER = "review"
FANNED = "fanned"
SINGLE = "single"
TAP = "tap"
REPORT = "proof-report.json"
SEEDS = "seeds.json"
#: The commands the views were rendered with, as the seeding command runs them, stated in the round's Views field.
VIEW_COMMANDS = [
    "task hw:views -- --board review-proof.kicad_pcb --project review-proof.kicad_pro " + " ".join(
        f"--class {name}" for name in review_seed.CLASSES) + " --out <review folder>/views, run from the design's folder",
    "task hw:placement -- --board review-proof.kicad_pcb --project review-proof.kicad_pro --out <review folder>/placement, "
    "run from the design's folder",
]


class Refused(Exception):
    def __init__(self, causes: Sequence[str]):
        super().__init__("; ".join(causes))
        self.causes = list(causes)


# --- The tap ------------------------------------------------------------------------------------


@contextlib.contextmanager
def tapped(work: str, phase: str) -> Iterator[str]:
    """The agent command line replaced by the tap for `phase`, its log in a folder of its own; the environment is put back
    on leaving. The folder of the phase's log is what is yielded."""
    real = review_fan_out.agent_program()
    shim = os.path.join(work, TAP, "agent")
    os.makedirs(os.path.dirname(shim), exist_ok=True)
    with open(shim, "w", encoding="utf-8") as handle:
        handle.write(f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(TOOLS_DIR, "review_agent_tap.py")}" "$@"\n')
    os.chmod(shim, os.stat(shim).st_mode | stat.S_IXUSR)
    log = os.path.join(work, TAP, phase)
    os.makedirs(log, exist_ok=True)
    names = (review_fan_out.AGENT_ENV, review_agent_tap.AGENT_ENV, review_agent_tap.LOG_ENV)
    before = {name: os.environ.get(name) for name in names}
    os.environ[review_fan_out.AGENT_ENV], os.environ[review_agent_tap.AGENT_ENV], os.environ[review_agent_tap.LOG_ENV] = (
        shim, real, log)
    try:
        yield log
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def tap_calls(log: str) -> List[Dict[str, Any]]:
    """Every call the tap kept for a phase, oldest first."""
    found = []
    for name in sorted(os.listdir(log)) if os.path.isdir(log) else []:
        if name.endswith(".json"):
            with open(os.path.join(log, name), encoding="utf-8") as handle:
                found.append(json.load(handle))
    return sorted(found, key=lambda call: call["began"])


def peak(calls: Sequence[Dict[str, Any]]) -> int:
    """The most calls that were running at once."""
    marks = sorted([(call["began"], 1) for call in calls] + [(call["ended"], -1) for call in calls],
                   key=lambda mark: (mark[0], mark[1]))
    now = most = 0
    for _, step in marks:
        now += step
        most = max(most, now)
    return most


def retrievals(calls: Sequence[Dict[str, Any]], sessions: Optional[Sequence[str]] = None) -> Dict[str, int]:
    """The documents retrieved by the calls, of `sessions` when given, and how many retrievals failed."""
    chosen = [call for call in calls if sessions is None or call["session"] in sessions]
    made = [fetch for call in chosen for fetch in call["retrievals"]]
    return {"retrieved": len(made), "failed": sum(1 for fetch in made if fetch["failed"])}


# --- The seeded copy and the folder -------------------------------------------------------------


def run_seed(work: str, kicad_cli: str, resvg: str) -> Dict[str, str]:
    """The seeding command, run with its flag that keeps the seeded copy's work tree; the work tree and the commit."""
    command = [sys.executable, os.path.join(TOOLS_DIR, "review_seed.py"), "--seeds", os.path.join(work, SEEDS), "--out",
               os.path.join(work, SEEDED), "--keep-work-tree", os.path.join(work, KEPT_TREE), "--kicad-cli", kicad_cli,
               "--resvg", resvg]
    done = subprocess.run(command, capture_output=True, text=True)
    kept = [line.split(" | ") for line in done.stdout.splitlines() if line.startswith("KEPT | ")]
    if done.returncode == 2:
        raise board_check.CannotRun(f"the seeding command could not run: {board_check.clean((done.stderr or done.stdout).strip())}")
    if done.returncode != 0 or not kept:
        raise Refused([f"the seeding command did not write the seeded copy: {board_check.clean(done.stdout.strip())}"])
    return {"repository": kept[0][1], "commit": kept[0][2].strip()}


def check_lines(report: str) -> List[str]:
    """The lines of the pre-order check's report that a round states: the board's DESIGN line and every FIGURE and VIOLATION line."""
    with open(report, encoding="utf-8") as handle:
        return [line.rstrip("\n") for line in handle if review_folder.CHECK_LINE.match(line)]


def write_folder(work: str, seeded: Dict[str, str]) -> str:
    """The review folder, written by the folder command from the kept work tree's commit, with the views and the check's
    report the seeding command rendered, and the method and notes of this repository."""
    folder = os.path.join(work, FOLDER)
    report = os.path.join(work, SEEDED, review_seed.REPORT)
    argv = ["--repo", seeded["repository"], "--commit", seeded["commit"], "--design", review_seed.DESIGN, "--out", folder,
            "--views", os.path.join(work, SEEDED, review_seed.VIEWS),
            "--placement", os.path.join(work, SEEDED, review_seed.PLACEMENT), "--check-report", report,
            "--number", "1", "--kind", "full"]
    for command in VIEW_COMMANDS:
        argv += ["--view-command", command]
    for line in check_lines(report):
        argv += ["--check-line", line]
    out = io.StringIO()
    status = review_folder.main(argv + ["--json"], out=out)
    written = json.loads(out.getvalue())
    if status != 0:
        raise Refused(written.get("refusals") or [written.get("detail", "the folder command failed")])
    return folder


# --- The two forms ------------------------------------------------------------------------------


def run_single(folder: str, work: str, model: Optional[str], wait: float) -> Dict[str, Any]:
    """One reviewer judging the whole round, with the four tools; its answer is kept in the work folder."""
    with tapped(work, SINGLE) as log:
        program = review_fan_out.require_agent()
        prompt = review_caller_layout.single_prompt(folder)
        began = time.time()
        session = review_fan_out.with_rate_retry(
            lambda: review_fan_out.call_agent(program, prompt, review_caller_layout.TOOLS, folder, model=model), wait)
        wall = round(time.time() - began, 3)
    problems = review_fan_out.start_problems(session, "the single reviewer", review_caller_layout.TOOLS, model, folder)
    os.makedirs(os.path.join(work, SINGLE), exist_ok=True)
    with open(os.path.join(work, SINGLE, "answer.md"), "w", encoding="utf-8") as handle:
        handle.write(session.text)
    calls = tap_calls(log)
    figure = review_fan_out.figures(session)
    return {"session": session.id, "model": session.start.get("model", ""), "answer": session.text,
            "problems": problems, "reported": session.reported, "wall_s": wall, "cost_usd": figure["cost_usd"],
            "tokens": figure["tokens"], "turns": figure["turns"], "api_ms": figure["api_ms"], **retrievals(calls),
            "rate_limited_calls": sum(1 for call in calls if call["rate_limited"]), "calls": len(calls)}


def run_fanned(folder: str, work: str, model: Optional[str], bound: int, wait: float, name: str = FANNED,
               rerun: Sequence[str] = ()) -> Dict[str, Any]:
    """The fan-out command on the folder with the layout caller, every reviewer running together; its record, each
    unit's and the setup session's figures with the documents each retrieved, and what the tap saw. Named units are run
    again into the output folder `name` already holds, and the tap's log of that folder then holds both runs' calls."""
    output = os.path.join(work, name)
    argv = ["--caller", "layout", "--review", folder, "--out", output, "--bound", str(bound), "--rate-limit-wait", str(wait),
            "--json"] + (["--model", model] if model else [])
    for unit in rerun:
        argv += ["--rerun", unit]
    out, err = io.StringIO(), io.StringIO()
    with tapped(work, name) as log:
        began = time.time()
        status = review_fan_out.main(argv, out=out, err=err)
        wall = round(time.time() - began, 3)
    calls = tap_calls(log)
    try:
        report = json.loads(out.getvalue())
    except ValueError:
        report = {"result": "FAILED", "refusals": [f"the fan-out command printed no report: {err.getvalue().strip()[:300]}"],
                  "units": [], "setup_sessions": [], "tables": {}, "totals": review_fan_out.empty_figures()}
    sessions = unit_sessions(output)
    for unit in report["units"]:
        unit.update(retrievals(calls, sessions.get(unit["unit"], [])))
    for setup in report["setup_sessions"]:
        setup.update(retrievals(calls, [setup["id"]]))
    forks = [call for call in calls if call["fork"]]
    return {"status": status, "wall_s": wall, "report": report, **retrievals(calls), "calls": len(calls), "bound": bound,
            "peak_reviewers_together": peak(forks), "rate_limited_calls": sum(1 for call in calls if call["rate_limited"])}


def unit_sessions(output: str) -> Dict[str, List[str]]:
    """The session ids behind each unit, from the results and failed attempts the fan-out command kept."""
    found: Dict[str, List[str]] = {}
    for folder, key in ((review_fan_out.UNITS_FOLDER, None), (review_fan_out.FAILED_FOLDER, None)):
        path = os.path.join(output, folder)
        for name in sorted(os.listdir(path)) if os.path.isdir(path) else []:
            if not name.endswith(".json"):
                continue
            content = review_fan_out.read_json(os.path.join(path, name))
            sessions = content["sessions"] + content.get("superseded", []) if isinstance(content, dict) else content
            found.setdefault(name[:-5], []).extend(entry["session"] for entry in sessions)
    return found


# --- The comparison -----------------------------------------------------------------------------


def parsed_round(text: str) -> Dict[str, Any]:
    """The verdicts, by item, and the findings' Raised by cells of a round written as Markdown, with or without its heading."""
    if not board_review_history.round_numbers(text):
        text = "## Round 1\n\n" + text
    bodies = board_review_history.round_bodies(text)
    body = bodies[min(bodies)] if bodies else []
    parsed = board_review_history.Round(body)
    header, rows = parsed.verdicts
    verdicts = {row[0]: row[header.index("Verdict")] for row in rows} if "Verdict" in header else {}
    header, rows = parsed.findings
    raised = [dict(zip(header, row)).get("Raised by", "") for row in rows] if "Raised by" in header else []
    return {"verdicts": verdicts, "raised_by": raised}


def names(item: str, cell: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9-]){re.escape(item)}(?![A-Za-z0-9-])", cell))


def compare(seeds: Sequence[Dict[str, Any]], single: Dict[str, Any], fanned: Dict[str, Any]) -> Dict[str, Any]:
    """Each seed against each form's findings, the findings that match no seed and the items judged differently."""
    items = {seed["item"] for seed in seeds}
    rows = []
    for seed in seeds:
        rows.append({"id": seed["id"], "item": seed["item"],
                     "single": any(names(seed["item"], cell) for cell in single["raised_by"]),
                     "fanned": any(names(seed["item"], cell) for cell in fanned["raised_by"])})
    return {"seeds": rows,
            "fanned_misses_a_seed_single_finds": [row["id"] for row in rows if row["single"] and not row["fanned"]],
            "neither_finds": [row["id"] for row in rows if not row["single"] and not row["fanned"]],
            "unseeded_findings": {form: [cell for cell in found["raised_by"] if not any(names(item, cell) for item in items)]
                                  for form, found in (("single", single), ("fanned", fanned))},
            "verdict_differences": [{"item": item, "single": single["verdicts"].get(item, "none"),
                                     "fanned": fanned["verdicts"].get(item, "none")}
                                    for item in sorted(set(single["verdicts"]) | set(fanned["verdicts"]))
                                    if single["verdicts"].get(item) != fanned["verdicts"].get(item)]}


def fanned_round(record: Dict[str, Any]) -> Dict[str, Any]:
    tables = record.get("tables", {})
    verdicts = {row["Item"]: row["Verdict"] for row in tables.get("Verdicts", {}).get("rows", [])}
    return {"verdicts": verdicts, "raised_by": [row["Raised by"] for row in tables.get("Findings", {}).get("rows", [])]}


def prove(folder: str, work: str, seeds: Sequence[Dict[str, Any]], model: Optional[str], bound: Optional[int],
          wait: float) -> Dict[str, Any]:
    """Both forms on the folder and the report that compares them."""
    units = review_caller_layout.units(folder)
    single = run_single(folder, work, model, wait)
    fanned = run_fanned(folder, work, model, bound or len(units), wait)
    report = fanned["report"]
    totals = report.get("totals", review_fan_out.empty_figures())
    found = fanned_round(report) if fanned["status"] == 0 else {"verdicts": {}, "raised_by": []}
    parsed = parsed_round(single["answer"])
    if not parsed["verdicts"]:
        single["problems"] = [*single["problems"], "the single reviewer's answer holds no Verdicts table that can be read, so "
                              "no seed can be matched to anything it reported"]
    both = compare(seeds, parsed, found)
    return {"units": units, "single": {key: value for key, value in single.items() if key != "answer"}, "fanned": fanned,
            "comparison": {**both, "time": {"single_s": single["wall_s"], "fanned_s": fanned["wall_s"],
                                            "fanned_no_more": fanned["wall_s"] <= single["wall_s"]},
                           "cost": {"single_usd": single["cost_usd"], "fanned_usd": totals["cost_usd"],
                                    "fanned_no_more": totals["cost_usd"] <= single["cost_usd"]}},
            "for_the_bound": {"bound_now": review_caller_layout.BOUND, "bound_run_with": fanned["bound"],
                              "most_reviewers_together": fanned["peak_reviewers_together"],
                              "rate_limited_calls": single["rate_limited_calls"] + fanned["rate_limited_calls"]}}


# --- The fanned-out form alone, against a single result already kept --------------------------


FANNED_ONLY_FILES = (REPORT, os.path.join(SINGLE, "answer.md"), SEEDS)


def first_unused(work: str) -> int:
    """The number of the first fanned-out output folder, from 2, the work folder does not hold."""
    number = 2
    while os.path.lexists(os.path.join(work, f"{FANNED}-{number}")) or os.path.lexists(os.path.join(work, f"proof-report-{number}.json")):
        number += 1
    return number


def kept_proof(work: str) -> Dict[str, Any]:
    """The earlier run's report and what the fanned-out form alone needs of it, or a refusal naming each piece missing."""
    if not os.path.isdir(work):
        raise Refused([f"the work folder {work} is not a folder; give the work folder of an earlier run"])
    missing = [name for name in FANNED_ONLY_FILES if not os.path.isfile(os.path.join(work, name))]
    causes = [f"the work folder {work} holds no {name}, which the fanned-out form alone reuses" for name in missing]
    if causes:
        raise Refused(causes)
    try:
        with open(os.path.join(work, REPORT), encoding="utf-8") as handle:
            earlier = json.load(handle)
        with open(os.path.join(work, SEEDS), encoding="utf-8") as handle:
            seeds = json.load(handle)["seeds"]
        folder, single = earlier["folder"], earlier["single"]
        problems = single["problems"]
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise Refused([f"the work folder {work} holds a {REPORT} or {SEEDS} that cannot be read: {type(error).__name__}: {error}"])
    if not isinstance(folder, str) or not os.path.isdir(folder):
        raise Refused([f"the review folder {folder} that the earlier run's {REPORT} names is not there"])
    if problems:
        raise Refused([f"the earlier run's single result recorded a problem, so it is not a result to compare with: "
                       f"{'; '.join(str(why) for why in problems)}"])
    with open(os.path.join(work, SINGLE, "answer.md"), encoding="utf-8") as handle:
        answer = parsed_round(handle.read())
    if not answer["verdicts"]:
        raise Refused([f"the single reviewer's kept answer holds no Verdicts table that can be read, so no seed can be matched to it"])
    return {"earlier": earlier, "seeds": seeds, "folder": folder, "single_round": answer}


def prove_fanned_only(work: str, kept: Dict[str, Any], model: Optional[str], bound: Optional[int], wait: float) -> Dict[str, Any]:
    """The fanned-out form alone on the kept review folder, into a new output folder; the units it left failed run once more,
    only those, into the same folder; compared with the single result the earlier run kept."""
    folder, earlier = kept["folder"], kept["earlier"]
    number = first_unused(work)
    name = f"{FANNED}-{number}"
    units = review_caller_layout.units(folder)
    first = run_fanned(folder, work, model, bound or len(units), wait, name)
    failed = [unit["unit"] for unit in first["report"]["units"] if unit["status"] == "failed"]
    fanned, again = first, None
    if failed:
        again = run_fanned(folder, work, model, bound or len(units), wait, name, rerun=failed)
        fanned = again
    totals_first = first["report"].get("totals", review_fan_out.empty_figures())
    totals = fanned["report"].get("totals", review_fan_out.empty_figures())
    wall = round(first["wall_s"] + (again["wall_s"] if again else 0.0), 3)
    # The rerun's totals hold every session the folder has cost, the first run's included, so the rerun phase is the difference.
    phases = {"output": os.path.join(work, name), "run": {"wall_s": first["wall_s"], "cost_usd": totals_first["cost_usd"],
                                                           "status": first["status"]},
              "rerun": None if again is None else {"units": failed, "wall_s": again["wall_s"], "status": again["status"],
                                                  "cost_usd": round(totals["cost_usd"] - totals_first["cost_usd"], 6)},
              "wall_s": wall, "cost_usd": totals["cost_usd"]}
    final = {**fanned, "wall_s": wall}
    found = fanned_round(fanned["report"]) if fanned["status"] == 0 else {"verdicts": {}, "raised_by": []}
    single = earlier["single"]
    both = compare(kept["seeds"], kept["single_round"], found)
    return {"number": number, "units": units, "single": single, "fanned": final, "fanned_phases": phases,
            "reused_single": {"from": os.path.join(work, REPORT), "wall_s": single["wall_s"], "cost_usd": single["cost_usd"],
                              "seeded_commit": earlier["seeded_commit"], "tool_commit": earlier["tool_commit"],
                              "same_seeded_copy": True},
            "comparison": {**both, "time": {"single_s": single["wall_s"], "fanned_s": wall, "fanned_no_more": wall <= single["wall_s"]},
                           "cost": {"single_usd": single["cost_usd"], "fanned_usd": totals["cost_usd"],
                                    "fanned_no_more": totals["cost_usd"] <= single["cost_usd"]}},
            "for_the_bound": {"bound_now": review_caller_layout.BOUND, "bound_run_with": final["bound"],
                              "most_reviewers_together": final["peak_reviewers_together"],
                              "rate_limited_calls": single["rate_limited_calls"] + final["rate_limited_calls"]}}


def reuse_lines(report: Dict[str, Any]) -> List[str]:
    clean = board_check.clean
    reused, phases = report["reused_single"], report["fanned_phases"]
    found = [f"REUSED SINGLE | the single result is reused from {clean(reused['from'])} (wall {reused['wall_s']} s, cost "
             f"${reused['cost_usd']}, tool commit {reused['tool_commit']}); it ran on the same seeded copy, commit {reused['seeded_commit']}",
             f"PHASES | {clean(phases['output'])} | run: wall {phases['run']['wall_s']} s, cost ${phases['run']['cost_usd']}"]
    if phases["rerun"]:
        found[-1] += (f" | rerun of {', '.join(phases['rerun']['units'])}: wall {phases['rerun']['wall_s']} s, cost "
                      f"${phases['rerun']['cost_usd']} | round: wall {phases['wall_s']} s, cost ${phases['cost_usd']}")
    else:
        found[-1] += f" | no unit failed, so no rerun | round: wall {phases['wall_s']} s, cost ${phases['cost_usd']}"
    return found


# --- The report ---------------------------------------------------------------------------------


def tool_commit() -> str:
    done = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else "unknown"


def lines_of(report: Dict[str, Any]) -> List[str]:
    clean = board_check.clean
    figure = review_fan_out.figure_line
    single, fanned = report["single"], report["fanned"]
    inner = fanned["report"]
    found = [f"PROOF | {clean(report['work'])} | tool commit {report['tool_commit']} | seeded copy commit {report['seeded_commit']}"]
    found += reuse_lines(report) if "reused_single" in report else []
    found += [f"SINGLE | model {clean(single['model'])} | wall {single['wall_s']} s | {figure(single)} | retrievals "
             f"{single['retrieved']} failed {single['failed']} | refused for a rate limit {single['rate_limited_calls']}"]
    found += [f"SINGLE PROBLEM | {clean(why)}" for why in single["problems"]]
    found += [f"SETUP | {entry['id']} | {entry['model']} | {figure(entry)} | retrievals {entry['retrieved']} failed {entry['failed']}"
              for entry in inner["setup_sessions"]]
    for entry in inner["units"]:
        found.append(f"UNIT | {entry['unit']} | {entry['status']} | {figure(entry['own'])} | retrievals {entry['retrieved']} failed "
                     f"{entry['failed']} | {clean('; '.join(entry['flags']) or 'no flag')}")
        if entry["status"] == "failed":
            found.append(f"UNIT FAILED | {entry['unit']} | {clean(entry['detail'])}")
    found += [f"FANNED REFUSED | {clean(why)}" for why in inner.get("refusals", [])]
    found.append(f"FANNED | status {fanned['status']} | bound {fanned['bound']} | wall {fanned['wall_s']} s | "
                 f"{figure(inner['totals'])} | retrievals {fanned['retrieved']} failed {fanned['failed']} | refused for a rate "
                 f"limit {fanned['rate_limited_calls']}")
    comparison = report["comparison"]
    found += [f"SEED | {row['id']} | {row['item']} | single {'reported' if row['single'] else 'not reported'} | fanned "
              f"{'reported' if row['fanned'] else 'not reported'}" for row in comparison["seeds"]]
    found += [f"UNSEEDED | {form} | {len(cells)} findings | {clean('; '.join(cells) or 'none')}"
              for form, cells in comparison["unseeded_findings"].items()]
    found += [f"VERDICT DIFFERENCE | {row['item']} | single {row['single']} | fanned {row['fanned']}"
              for row in comparison["verdict_differences"]]
    found.append(f"COMPARE | time: fanned {comparison['time']['fanned_s']} s, single {comparison['time']['single_s']} s, fanned no "
                 f"more {comparison['time']['fanned_no_more']} | cost: fanned ${comparison['cost']['fanned_usd']}, single "
                 f"${comparison['cost']['single_usd']}, fanned no more {comparison['cost']['fanned_no_more']} | seeds the "
                 f"single reviewer found and the fanned-out form did not: {', '.join(comparison['fanned_misses_a_seed_single_finds']) or 'none'}")
    bound = report["for_the_bound"]
    found.append(f"BOUND | caller's bound now {bound['bound_now']} | run with {bound['bound_run_with']} | most reviewers "
                 f"together {bound['most_reviewers_together']} | calls refused for a rate limit {bound['rate_limited_calls']}")
    return found


def refusals(work: str) -> List[str]:
    found = []
    if review_seed.inside(work, REPO):
        found.append(f"the work folder {work} is inside the repository; give a folder outside it")
    if os.path.isfile(work):
        found.append(f"the work folder {work} is a file; give a new or empty folder")
    elif os.path.isdir(work) and os.listdir(work):
        found.append(f"the work folder {work} already holds files; give a new or empty folder")
    return found


def fanned_only(work: str, args, result: Dict[str, Any], finish) -> int:
    """The fanned-out form alone against the kept single result; the report is proof-report-<n>.json in the work folder."""
    try:
        kept = kept_proof(work)
        proof = prove_fanned_only(work, kept, args.model, args.bound, args.rate_limit_wait)
    except Refused as error:
        result["refusals"] = error.causes
        return finish(1)
    except board_check.CannotRun as error:
        result.update(result="CANNOT RUN", refusals=[], detail=str(error))
        return finish(2)
    earlier = kept["earlier"]
    proof.update({"work": work, "tool_commit": tool_commit(), "seeded_commit": earlier["seeded_commit"], "folder": kept["folder"]})
    path = os.path.join(work, f"proof-report-{proof['number']}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(proof, handle, indent=1)
        handle.write("\n")
    ran = proof["fanned"]["status"] == 0
    result.update(proof)
    result.update(result="WRITTEN" if ran else "FAILED", refusals=[], lines=lines_of(proof),
                  detail=path if ran else f"the fanned-out form did not run clean; the report is {path}")
    return finish(0 if ran else 1)


def main(argv: Optional[List[str]] = None, out=sys.stdout, err=sys.stderr,
         seed_runner=run_seed) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", default=None, help="a new folder outside the repository the run keeps everything in")
    parser.add_argument("--fanned-only", default=None, metavar="WORK",
                        help="an earlier run's work folder: run only the fanned-out form on its review folder, into a new "
                        "folder inside it, run the units it left failed once more, and compare it with the single result "
                        "the earlier run kept")
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--resvg", default="resvg", help="the resvg program the views are drawn with (default: resvg on the search path)")
    parser.add_argument("--model", default=None, help="the model both forms use (default: the agent command line's own)")
    parser.add_argument("--bound", type=int, default=None, help="the most reviewers at once (default: the full unit count)")
    parser.add_argument("--rate-limit-wait", type=float, default=5.0,
                        help="seconds before the first retry of a call refused for a rate limit; it doubles each time")
    parser.add_argument("--json", action="store_true", help="print the report as one JSON document")
    args = parser.parse_args(argv)
    if (args.work is None) == (args.fanned_only is None):
        parser.error("give --work for a new run, or --fanned-only with an earlier run's work folder, and not both")
    work = os.path.abspath(args.work or args.fanned_only)
    result: Dict[str, Any] = {"result": "REFUSED", "refusals": [] if args.fanned_only else refusals(work),
                              "detail": "nothing was run"}

    def finish(status: int) -> int:
        if args.json:
            json.dump(result, out, indent=1)
            out.write("\n")
        else:
            for line in result.get("lines", []):
                print(line, file=out)
            for why in result["refusals"]:
                print(f"REFUSED | {board_check.clean(why)}", file=out)
            print(f"RESULT | {result['result']} | {board_check.clean(result['detail'])}", file=err if status == 2 else out)
        return status

    if args.bound is not None and args.bound < 1:
        result["refusals"].append(f"the bound {args.bound} is below one; give one or more reviewers at once")
    if result["refusals"]:
        return finish(1)
    if args.fanned_only:
        return fanned_only(work, args, result, finish)
    try:
        os.makedirs(work, exist_ok=True)
        seeded = seed_runner(work, args.kicad_cli, args.resvg)
        folder = write_folder(work, seeded)
        with open(os.path.join(work, SEEDS), encoding="utf-8") as handle:
            seeds = json.load(handle)["seeds"]
        proof = prove(folder, work, seeds, args.model, args.bound, args.rate_limit_wait)
    except Refused as error:
        result["refusals"] = error.causes
        return finish(1)
    except board_check.CannotRun as error:
        result.update(result="CANNOT RUN", refusals=[], detail=str(error))
        return finish(2)
    proof.update({"work": work, "tool_commit": tool_commit(), "seeded_commit": seeded["commit"], "folder": folder})
    with open(os.path.join(work, REPORT), "w", encoding="utf-8") as handle:
        json.dump(proof, handle, indent=1)
        handle.write("\n")
    ran = proof["fanned"]["status"] == 0 and not proof["single"]["problems"]
    result = {**proof, "result": "WRITTEN" if ran else "FAILED", "refusals": [], "lines": lines_of(proof),
              "detail": os.path.join(work, REPORT) if ran else f"a form did not run clean; the report is {os.path.join(work, REPORT)}"}
    return finish(0 if ran else 1)


if __name__ == "__main__":
    sys.exit(main())
