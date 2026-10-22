#!/usr/bin/env python3
"""The parts of a review's proof command that do not depend on the review: the figures the kit does not count, one run of the
fanned-out form on the kit's command, the plan it would run, the saved run in the proof's shape, and one run of the single form
recorded as a baseline file.

A review's proof command seeds a copy of its proof design, writes the review folder, and runs its caller through the review kit's
command; what differs from one review to the next is the seeding, the folder, the caller's name, how a finding names a seed, and
how the merged round is read. This module takes those as arguments, so the layout review's proof and the schematic review's are
thin commands over one set of functions.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import types
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_check  # noqa: E402
import review_seed  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import command, ensemble, proof, scheduler, store, streams  # noqa: E402
from review_kit import executor as ex  # noqa: E402

REPO = review_seed.REPO
#: The tool whose uses retrieve a published document.
RETRIEVAL_TOOL = "WebFetch"
#: The key of a baselines file and the version it is read with.
SINGLE_RUN_ID = "single-1"


class Refused(Exception):
    def __init__(self, causes: Sequence[str]):
        super().__init__("; ".join(causes))
        self.causes = list(causes)


# --- The figures the kit's telemetry does not count -----------------------------------------------


def saved(folder: str) -> List[Tuple[Dict[str, Any], str]]:
    """Every session the executor saved in a streams folder, oldest first: its meta record and its stream as printed."""
    found = []
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(ex.META_SUFFIX):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as handle:
            meta = json.load(handle)
        with open(os.path.join(folder, name[:-len(ex.META_SUFFIX)] + ex.STREAM_SUFFIX), encoding="utf-8", newline="") as handle:
            found.append((meta, handle.read()))
    return found


def retrievals(folder: str) -> Dict[str, Dict[str, int]]:
    """The documents each session retrieved and how many retrievals failed, by session label, from the saved streams. A
    retrieval failed when its result is an error or the stream holds no result for it."""
    found: Dict[str, Dict[str, int]] = {}
    for meta, text in saved(folder):
        stream = streams.read_stream(text)
        entry = found.setdefault(meta.get("label") or meta.get("key", "")[:12], {"retrieved": 0, "failed": 0})
        for call in stream.calls:
            for use in call.tool_uses:
                if use.get("name") != RETRIEVAL_TOOL:
                    continue
                entry["retrieved"] += 1
                result = stream.tool_results.get(use.get("id") or "")
                if result is None or result.get("is_error") is True:
                    entry["failed"] += 1
    return found


def refused_for_rate_limit(folder: str) -> int:
    """The calls the service refused for a rate limit: each call the executor started again was refused once for each start
    beyond its first, and a call that ended refused was refused on its last start too."""
    total = 0
    for meta, _ in saved(folder):
        attempts = meta.get("attempts", 1)
        total += attempts - 1 + (1 if meta.get("kind") == ex.RATE_LIMIT else 0)
    return total


def total(figure: Mapping[str, Mapping[str, int]], name: str) -> int:
    return sum(entry[name] for entry in figure.values())


def tool_commit() -> str:
    done = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else "unknown"


# --- One run of the fanned-out form ---------------------------------------------------------------


def run_command(caller: str, callers: str, folder: str, out: str, model: str, replicas: int, bound: Optional[int],
                environ: Mapping[str, str], main: Callable[..., int] = command.main) -> Tuple[int, Dict[str, Any]]:
    """The kit's command on the folder with the caller; its exit status and report. The sessions run together."""
    argv = ["--caller", caller, "--callers", callers, "--review", folder, "--out", out, "--replicas", str(replicas),
            "--model", model, "--format", "json"] + (["--bound", str(bound)] if bound is not None else [])
    printed, error = io.StringIO(), io.StringIO()
    status = main(argv, printed, error, environ)
    try:
        report = json.loads(printed.getvalue())
    except ValueError:
        report = {"result": command.REFUSED, "refusals": [f"the command printed no report: {error.getvalue().strip()[:300]}"],
                  "cannot_run": None, "detail": "nothing was run"}
    return status, report


def plan_of(caller: str, callers: str, folder: str, out: str, model: str, replicas: int, bound: Optional[int],
            environ: Mapping[str, str]) -> Dict[str, Any]:
    """The plan the command would run, with its predicted cost and time, made with no session and no model call."""
    args = argparse.Namespace(caller=caller, callers=callers, review=folder, out=out, bound=None if bound is None else str(bound),
                              replicas=str(replicas), model=model, rerun=[], format="text")
    run = command.Run(args, folder, out, command.REPO)
    try:
        run.settle(environ)
        run.build_plan(ex.agent_program(environ))
    except command.Refusal as error:
        raise Refused(error.causes)
    return run.report["plan"]


def outcome_of(caller: str, callers: str, run_id: str, folder: str, out: str, seeds: Sequence[Mapping[str, Any]],
               seeded_commit: str, matches: proof.Match, parse_round: Callable[[str], Mapping[str, Any]],
               names: Callable[[str, str], bool], name: Optional[str] = None) -> Tuple[proof.RunOutcome, Dict[str, Any]]:
    """The saved run in the proof's shape, and the facts about it the kit does not count: the retrievals by session, the calls
    refused for a rate limit, and whether the merged round names the seeds the replicas' findings name. `name` is the round a
    refusal names; `parse_round` reads a rendered round into its `raised_by` cells and `names(item, cell)` says whether a cell names
    an item."""
    name = name or run_id
    record = store.read_record(out)
    failed = [lane["failure"] for lane in record["lanes"] if lane["failure"] is not None]
    if failed:
        raise Refused([f"{name}: group {each['group']} replica {each['replica']} failed: {'; '.join(each['problems'])}; "
                       f"the run is kept in {out}" for each in failed])
    figures, problems = command.figures_of_run(os.path.join(out, command.STREAMS_FOLDER), set())
    if problems:
        raise Refused([f"{name}: {problem}" for problem in problems])
    lanes = []
    for lane in record["lanes"]:
        entry = lane["record"]
        tables = entry["attempts"][entry["standing"]]["tables"] if entry["standing"] is not None else {}
        lanes.append(types.SimpleNamespace(group=lane["group"], replica=lane["replica"], units=tuple(lane["units"]),
                                           unit_record=types.SimpleNamespace(standing=types.SimpleNamespace(tables=tables)),
                                           failure=None))
    declaration = kit_caller.load(caller, callers).prepare(folder).declaration
    formed = proof.FormPlan(proof.FANNED, declaration, None, types.SimpleNamespace(tool_commit=record["plan"]["tool_commit"]))
    outcome = proof.outcome_from_run(run_id, formed, scheduler.RunResult({}, lanes, False), figures, seeds, matches,
                                     seeded_commit=seeded_commit)
    streams_folder = os.path.join(out, command.STREAMS_FOLDER)
    rendered = [file for file in record.get("rendered", []) if file.endswith(".md")]
    merged_round = None
    if rendered:
        with open(os.path.join(out, rendered[0]), encoding="utf-8") as handle:
            merged_round = parse_round(handle.read())
    merged_found = ([seed["id"] for seed in seeds if any(names(seed["item"], cell) for cell in merged_round["raised_by"])]
                    if merged_round else None)
    return outcome, {"retrievals": retrievals(streams_folder), "refused_for_a_rate_limit": refused_for_rate_limit(streams_folder),
                     "merged_round_seeds_found": merged_found, "merged": record["merged"] is not None}


# --- One run of the single form, recorded as a baseline ---------------------------------------------


def single_plan(run: "command.Run", environ: Mapping[str, str]) -> proof.FormPlan:
    """The single form of the review a settled run holds: one unit with every item, no shared context, run once."""
    program = ex.require_agent(environ)
    declaration = run.prepared.declaration
    shaped = proof.one_unit(declaration, needs=False)
    prompt_for = lambda units, variant: ensemble.variant_prompt(shaped, units, ensemble.Variant("single"), run.prepared.unit_text)
    return proof.form_plan(proof.SINGLE, declaration, run.catalogue, run.spec, bound=1, cli_version=command.agent_version(program),
                           tool_commit=command.tool_commit(run.repo), prompt_for=prompt_for)


def settled_run(caller: str, callers: str, folder: str, out: str, model: str, environ: Mapping[str, str]) -> "command.Run":
    args = argparse.Namespace(caller=caller, callers=callers, review=folder, out=out, bound=None, replicas="1", model=model,
                              rerun=[], format="text")
    run = command.Run(args, folder, out, command.REPO)
    try:
        run.settle(environ)
    except command.Refusal as error:
        raise Refused(error.causes)
    return run


def single_plan_of(caller: str, callers: str, folder: str, out: str, model: str, environ: Mapping[str, str]) -> Dict[str, Any]:
    """The plan the single form would run, with its predicted cost and time, made with no session and no model call."""
    run = settled_run(caller, callers, folder, out, model, environ)
    try:
        formed = single_plan(run, environ)
    except ex.CannotRun as error:
        raise board_check.CannotRun(str(error))
    return command.plan_summary(formed.plan, formed.shared, 1)


def baseline_key(seeds: Sequence[Mapping[str, Any]], design: str, model: str, formed: proof.FormPlan) -> proof.BaselineKey:
    """What a baseline run of the single form is for: the seed list, the design, the model and the prompt the session was given,
    named by the hash of its message."""
    group = formed.plan.nodes[-1]
    return proof.BaselineKey(proof.seed_list_hash(seeds), design, model, proof.SINGLE, group.message_sha)


def write_baseline(path: str, source: str, seeds: Sequence[Mapping[str, Any]], key: proof.BaselineKey, outcome: proof.RunOutcome) -> None:
    """The baselines file with a group of runs added for the key: the file whole or not at all. A file that already holds runs
    under the key is refused, since a recorded baseline is not run again; one that holds other keys keeps them."""
    held: Dict[str, Any] = {"version": proof.BASELINES_VERSION, "source": source, "seeds": list(seeds), "baselines": []}
    if os.path.exists(path):
        try:
            loaded = proof.load_baselines(path)
            with open(path, encoding="utf-8") as handle:
                held = json.load(handle)
        except (proof.BaselineFileError, OSError, ValueError) as error:
            raise Refused([f"the baselines file {path} cannot be added to ({error}); move it away, or give another file"])
        if loaded.recorded(key):
            raise Refused([f"the baselines file {path} already holds single runs under this key; a recorded baseline is not run again"])
        held["source"] = f"{held.get('source', '')} {source}".strip()
    held["baselines"] = list(held["baselines"]) + [{"key": key.as_dict(), "runs": [outcome.as_dict()]}]
    store.atomic_write_json(path, held)


def run_single(caller: str, callers: str, folder: str, out: str, model: str, environ: Mapping[str, str],
               seeds: Sequence[Mapping[str, Any]], seeded_commit: str, design: str, matches: proof.Match, path: str,
               source: str, run_id: str = SINGLE_RUN_ID) -> Tuple[proof.BaselineKey, proof.RunOutcome]:
    """Run the kit's single form once on the real executor, as the proof's baseline, and write it as a baseline file.

    The form is one unit holding every item of the review, with no shared context, run on `model` in one session through the
    kit's own plan and scheduler. The run is written to `path` under the key of the seed list, the design, the model and the
    prompt; an output folder `out` that already holds a record, or a baselines file that already holds the key, is refused."""
    run = settled_run(caller, callers, folder, out, model, environ)
    try:
        formed = single_plan(run, environ)
    except ex.CannotRun as error:
        raise board_check.CannotRun(str(error))
    key = baseline_key(seeds, design, model, formed)
    if os.path.exists(path):
        try:
            if proof.load_baselines(path).recorded(key):
                raise Refused([f"the baselines file {path} already holds single runs under this key; a recorded baseline is not run "
                               "again"])
        except proof.BaselineFileError as error:
            raise Refused([str(error)])
    clock = ex.SystemClock()
    executor = ex.ClaudeCliExecutor(program=ex.require_agent(environ), environ=dict(environ), clock=clock, out=run.streams_folder)
    rules = run.prepared.rules
    runner = scheduler.Scheduler(executor, clock, cannot_judge=rules.cannot_judge, fail=rules.fail,
                                 retrieval=kit_caller.RETRIEVAL_TOOL in run.prepared.tools)
    before = command.saved_names(run.streams_folder)
    prompt_for = lambda units, variant: ensemble.variant_prompt(formed.declaration, units, ensemble.Variant("single"),
                                                                run.prepared.unit_text)
    try:
        result = proof.run_form(runner, formed, run.spec, prompt_for, rules.round_label)
    except ex.CannotRun as error:
        raise board_check.CannotRun(str(error))
    except (scheduler.RootFailed, ex.StartReportFailed) as error:
        raise Refused([f"the single form's run failed: {error}"])
    failures = [lane.failure for lane in result.lanes if lane.failure is not None]
    if failures:
        raise Refused([f"the single form's session failed: {'; '.join(each['problems'])}" for each in failures])
    figures, problems = command.figures_of_run(run.streams_folder, before)
    if problems:
        raise Refused([f"the single form's {problem}" for problem in problems])
    outcome = proof.outcome_from_run(run_id, formed, result, figures, seeds, matches, seeded_commit=seeded_commit)
    write_baseline(path, source, seeds, key, outcome)
    return key, outcome
