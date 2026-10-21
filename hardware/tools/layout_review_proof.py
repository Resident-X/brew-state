#!/usr/bin/env python3
"""Prove the fanned-out layout review on a seeded copy of the layout review proof design, against the recorded single-reviewer runs.

The layout review proof seeds known defects into a copy of the proof design (review_seed.py) and has reviewers that did not
design the board follow the method's review step blind. This is the one command that does it for the fanned-out form: it
runs the seeding command with its opt-in flag that keeps the seeded copy's git work tree, writes the review folder with the
folder command from that work tree and its commit (the layout facts and the round file included, the method and the hardware
notes taken from this repository as the seeding command takes them), then runs the layout caller through the review kit's
command on the real agent command line, twice: with two replicas, the design loop's round, on the small-tier model, and with
three, the pre-order round's, the first two on the mid-tier model and the third on the small tier. The recorded
single-reviewer runs of the same seed list and design, which ran on the mid-tier model, are the baselines whatever model the
fanned-out run uses, and the single reviewer is never run again.

    layout_review_proof.py --work <new folder outside the repository> [--kicad-cli ...] [--resvg ...]
                           [--design-model M] [--pre-order-model M] [--only design-loop|pre-order] [--bound N] [--dry] [--json]

The design loop's run is judged by the kit's pooled criterion with a cost multiple of 1.25: the seeds found are no fewer than
the fewest any recorded single run found, no seed every single run found is missed, the wall time is at most half the single
mean and the cost at most 1.25 times its mean. The pre-order round's figures are recorded and not bounded. The record,
proof-record.json, and its text, proof-record.txt, are written in the work folder; they give every seed with the replicas
that raised it, the findings that match no seed, the verdicts item by item with the differences from the single runs, each
session's time, tokens read, written and generated, cost, first-call cache read and document retrievals with any that
failed, and the calls refused for a rate limit. A seed not reported is closed where the gap lies and the proof repeated.

The work folder keeps the review folder alone in <work>/review-tree/review, since a session starts there and can read the
folders above it; the seed list, the seeded copy and the kept work tree are under <work>/seed/, each round's output under
<work>/out/<round>/, and the record in <work>. A session that guesses a path two levels up can still read them.

The pre-order round's third replica runs on the layout caller's small-tier model with a shared context of its own, one root
more; the cost model prices each model's sessions at that model's own prices.

--dry prints each selected run's model or models, plan and its predicted cost and time beside the bounds they would be held to (with a warning
when the design loop's prediction is over a bound or within a tenth of it), and starts no
session and calls no model; it still seeds the copy and writes the review folder. --only runs one of the two rounds.

The agent command line is the program named by REVIEW_KIT_AGENT (claude when it is unset), logged in. A run costs money:
the shared context and a fork for each group and replica, for each round.

Each cause is reported on one line beginning REFUSED, a RESULT line comes last, and the exit status is 0 when the criterion
holds (or, with --only pre-order, when the run completed and its figures are recorded), 1 when the command refuses, a run fails
or the criterion does not hold or asks for a second run, and 2 when a tool or the agent command line is missing. --json
prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import types
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_check  # noqa: E402
import board_review_history  # noqa: E402
import review_folder  # noqa: E402
import review_seed  # noqa: E402
from review_kit import caller as kit_caller  # noqa: E402
from review_kit import command, proof, scheduler, store, streams  # noqa: E402
from review_kit import costmodel as cost_model  # noqa: E402
from review_kit import executor as ex  # noqa: E402

REPO = review_seed.REPO
#: Where the work folder keeps each part, relative to it. A session starts in the review folder and can read the folders above
#: it, so the review folder lives alone in a folder of its own and the seed material and the output folders sit beside that
#: folder's parent, not in it.
SEED_DIR = "seed"
SEEDED = os.path.join(SEED_DIR, "seeded-review")
KEPT_TREE = os.path.join(SEED_DIR, "seeded-work")
SEEDS = os.path.join(SEED_DIR, "seeds.json")
REVIEW_TREE = "review-tree"
FOLDER = os.path.join(REVIEW_TREE, "review")
OUT_DIR = "out"
RECORD = "proof-record.json"
TEXT = "proof-record.txt"
BASELINES = os.path.join(TOOLS_DIR, "tests", "fixtures", "review_baselines", "layout_single_runs.json")
#: The mid-tier model of the recorded single-reviewer runs, which the baseline key holds and the pre-order round's first two
#: replicas run on.
BASELINE_MODEL = "claude-sonnet-5-5"
#: The small-tier model the design loop's two replicas run on.
DESIGN_MODEL = "claude-haiku-5-5"
PRE_ORDER_MODEL = BASELINE_MODEL
#: The cost multiple of the pooled criterion for a round of the design loop.
COST_MULTIPLE = 1.25
CALLER = "layout"
#: The two rounds the proof runs, by name: the replicas of each group and the folder the run is kept in.
ROUNDS: Tuple[Tuple[str, int], ...] = (("design-loop", 2), ("pre-order", 3))
#: The tool whose uses retrieve a published document.
RETRIEVAL_TOOL = "WebFetch"
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


# --- The seeded copy and the folder -------------------------------------------------------------


def run_seed(work: str, kicad_cli: str, resvg: str) -> Dict[str, str]:
    """The seeding command, run with its flag that keeps the seeded copy's work tree; the work tree and the commit."""
    os.makedirs(os.path.join(work, SEED_DIR), exist_ok=True)
    command_line = [sys.executable, os.path.join(TOOLS_DIR, "review_seed.py"), "--seeds", os.path.join(work, SEEDS), "--out",
                    os.path.join(work, SEEDED), "--keep-work-tree", os.path.join(work, KEPT_TREE), "--kicad-cli", kicad_cli,
                    "--resvg", resvg]
    done = subprocess.run(command_line, capture_output=True, text=True)
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


def write_folder(work: str, seeded: Dict[str, str], documents_repo: Optional[str] = None) -> str:
    """The review folder, written by the folder command from the kept work tree's commit, with the views and the check's
    report the seeding command rendered, and the method and notes of this repository."""
    folder = os.path.join(work, FOLDER)
    os.makedirs(os.path.dirname(folder), exist_ok=True)
    report = os.path.join(work, SEEDED, review_seed.REPORT)
    argv = ["--repo", seeded["repository"], "--commit", seeded["commit"], "--design", review_seed.DESIGN, "--out", folder,
            "--views", os.path.join(work, SEEDED, review_seed.VIEWS),
            "--placement", os.path.join(work, SEEDED, review_seed.PLACEMENT), "--check-report", report,
            "--number", "1", "--kind", "full"] + (["--documents-repo", documents_repo] if documents_repo else [])
    for line in VIEW_COMMANDS:
        argv += ["--view-command", line]
    for line in check_lines(report):
        argv += ["--check-line", line]
    out = io.StringIO()
    status = review_folder.main(argv + ["--json"], out=out)
    written = json.loads(out.getvalue())
    if status != 0:
        raise Refused(written.get("refusals") or [written.get("detail", "the folder command failed")])
    return folder


# --- The baselines ------------------------------------------------------------------------------


def design_tree(repo: str = REPO, ref: str = "HEAD", design: str = review_seed.DESIGN) -> str:
    """The git tree id of the proof design's folder, which the baseline key holds as the design."""
    done = subprocess.run(["git", "-C", repo, "rev-parse", f"{ref}:{design}"], capture_output=True, text=True)
    if done.returncode != 0:
        raise Refused([f"the tree of {design} at {ref} in {repo} cannot be read: {board_check.clean(done.stderr.strip())}"])
    return done.stdout.strip()


def baseline_runs(path: str, seeds: Sequence[Mapping[str, Any]], design: str, model: str
                  ) -> Tuple[proof.BaselineKey, List[proof.RunOutcome]]:
    """The recorded single-reviewer runs whose key holds this seed list, design and model, with the key. The prompt hash is the
    one recorded. A file that holds none for them is refused, naming what differs, since runs of another seed list, design or
    model are not baselines for this one."""
    try:
        loaded = proof.load_baselines(path)
    except proof.BaselineFileError as error:
        raise Refused([str(error)])
    keys = [key for key in loaded.keys.values() if key.form == proof.SINGLE]
    wanted = {"seeds": proof.seed_list_hash(seeds), "design": design, "model": model}
    for key in keys:
        if all(getattr(key, name) == value for name, value in wanted.items()):
            return key, loaded.recorded(key)
    differs = "; ".join(f"the recorded runs' {name} is {getattr(keys[0], name) if keys else 'absent'} and this run's is {value}"
                        for name, value in wanted.items() if not keys or getattr(keys[0], name) != value)
    raise Refused([f"{path} holds no single-reviewer runs of this seed list, design and model ({differs}); they are not baselines for "
                   "this run, so change the run to match them or record runs for it"])


# --- Matching seeds to findings -----------------------------------------------------------------


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


def matches(seed: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    """Whether a finding names the catalogue item that covers the seed, in its Raised by cell."""
    return names(seed["item"], str(row.get("Raised by", "")))


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


# --- One run of the fanned-out form ---------------------------------------------------------------


def run_command(folder: str, out: str, model: str, replicas: int, bound: Optional[int], environ: Mapping[str, str],
                main: Callable[..., int] = command.main) -> Tuple[int, Dict[str, Any]]:
    """The kit's command on the folder with the layout caller; its exit status and report. The sessions run together."""
    argv = ["--caller", CALLER, "--callers", TOOLS_DIR, "--review", folder, "--out", out, "--replicas", str(replicas),
            "--model", model, "--format", "json"] + (["--bound", str(bound)] if bound is not None else [])
    printed, error = io.StringIO(), io.StringIO()
    status = main(argv, printed, error, environ)
    try:
        report = json.loads(printed.getvalue())
    except ValueError:
        report = {"result": command.REFUSED, "refusals": [f"the command printed no report: {error.getvalue().strip()[:300]}"],
                  "cannot_run": None, "detail": "nothing was run"}
    return status, report


def plan_of(folder: str, out: str, model: str, replicas: int, bound: Optional[int], environ: Mapping[str, str]) -> Dict[str, Any]:
    """The plan the command would run, with its predicted cost and time, made with no session and no model call."""
    args = argparse.Namespace(caller=CALLER, callers=TOOLS_DIR, review=folder, out=out, bound=None if bound is None else str(bound),
                              replicas=str(replicas), model=model, rerun=[], format="text")
    run = command.Run(args, folder, out, command.REPO)
    try:
        run.settle(environ)
        run.build_plan(ex.agent_program(environ))
    except command.Refusal as error:
        raise Refused(error.causes)
    return run.report["plan"]


def outcome_of(run_id: str, folder: str, out: str, seeds: Sequence[Mapping[str, Any]], seeded_commit: str,
               name: Optional[str] = None) -> Tuple[proof.RunOutcome, Dict[str, Any]]:
    """The saved run in the proof's shape, and the facts about it the kit does not count: the retrievals by session, the
    calls refused for a rate limit, and whether the merged round names the seeds the replicas' findings name. `name` is the round
    a refusal names."""
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
    declaration = kit_caller.load(CALLER, TOOLS_DIR).prepare(folder).declaration
    formed = proof.FormPlan(proof.FANNED, declaration, None, types.SimpleNamespace(tool_commit=record["plan"]["tool_commit"]))
    outcome = proof.outcome_from_run(run_id, formed, scheduler.RunResult({}, lanes, False), figures, seeds, matches,
                                     seeded_commit=seeded_commit)
    streams_folder = os.path.join(out, command.STREAMS_FOLDER)
    rendered = [file for file in record.get("rendered", []) if file.endswith(".md")]
    merged_round = None
    if rendered:
        with open(os.path.join(out, rendered[0]), encoding="utf-8") as handle:
            merged_round = parsed_round(handle.read())
    merged_found = ([seed["id"] for seed in seeds if any(names(seed["item"], cell) for cell in merged_round["raised_by"])]
                    if merged_round else None)
    return outcome, {"retrievals": retrievals(streams_folder), "refused_for_a_rate_limit": refused_for_rate_limit(streams_folder),
                     "merged_round_seeds_found": merged_found, "merged": record["merged"] is not None}


# --- The record and its text ----------------------------------------------------------------------


def total(figure: Mapping[str, Mapping[str, int]], name: str) -> int:
    return sum(entry[name] for entry in figure.values())


def build(seeds: Sequence[Mapping[str, Any]], key: proof.BaselineKey, singles: Sequence[proof.RunOutcome],
          runs: Mapping[str, Tuple[proof.RunOutcome, Dict[str, Any]]], context: Mapping[str, Any]) -> Dict[str, Any]:
    """The kit's record of the proof over the design loop's run, with the pre-order round's figures beside it, recorded and not
    bounded, and what each run's saved streams show."""
    design = runs.get("design-loop")
    if design:
        record = proof.build_record(seeds, singles, [design[0]], COST_MULTIPLE, [key])
    else:
        record = {"version": 1, "seeds": [seed["id"] for seed in seeds], "seed_list_sha256": proof.seed_list_hash(seeds),
                  "cost_multiple": COST_MULTIPLE, "keys": [dict(key.as_dict(), id=key.id)], "verdict": None,
                  "single_runs": [proof.run_report(run) for run in singles], "fanned_runs": [],
                  "single_means": {"wall_s": round(proof.mean([run.wall_s for run in singles]), 3),
                                   "cost_usd": round(proof.mean([run.cost_usd for run in singles]), 6)}}
    pre_order = runs.get("pre-order")
    if pre_order:
        record["pre_order"] = proof.run_report(pre_order[0])
        record["pre_order"]["seed_replicas"] = {seed["id"]: list(pre_order[0].raised_by.get(seed["id"], ())) for seed in seeds}
    record["layout"] = dict(context, rounds={name: extra for name, (_, extra) in runs.items()})
    return record


def lines_of(record: Mapping[str, Any]) -> List[str]:
    found = []
    layout = record["layout"]
    found.append(f"PROOF | design loop on {layout['models']['design-loop']}, pre-order on {layout['models']['pre-order']} (third "
                 f"replica on the small tier) | baselines on {layout['baseline_model']} | tool commit {layout['tool_commit']} | "
                 f"seeded copy commit {layout['seeded_commit']} | cost multiple {COST_MULTIPLE:g}")
    if record["verdict"] is not None:
        found += [f"CRITERION | {line}" for line in proof.record_lines(record)]
    else:
        found.append("CRITERION | not judged: the design loop's round was not run, so the pre-order round's figures are only recorded")
    for name, extra in layout["rounds"].items():
        found.append(f"ROUND | {name} | refused for a rate limit {extra['refused_for_a_rate_limit']} | retrievals "
                     f"{total(extra['retrievals'], 'retrieved')} failed {total(extra['retrievals'], 'failed')} | merged round "
                     f"{'written' if extra['merged'] else 'refused'} | seeds the merged round names "
                     f"{', '.join(extra['merged_round_seeds_found'] or []) or 'none'}")
        found += [f"RETRIEVALS | {name} | {label} | retrieved {entry['retrieved']} failed {entry['failed']}"
                  for label, entry in extra["retrievals"].items() if entry["retrieved"]]
    if record.get("pre_order"):
        run = record["pre_order"]
        found.append(f"PRE-ORDER | three replicas | seeds {run['seeds_found_count']} of {len(record['seeds'])} | {run['wall_s']:g} s | "
                     f"{run['cost_usd']:g} USD | {len(run['unmatched'])} findings matching no seed | recorded, not bounded")
    for seed in record["seeds"]:
        for name, replicas in record.get("seed_replicas", {}).get(seed, {}).items():
            found.append(f"SEED | {seed} | design loop {name} | raised by {', '.join(replicas) or 'none'}")
        if record.get("pre_order"):
            found.append(f"SEED | {seed} | pre-order | raised by {', '.join(record['pre_order']['seed_replicas'][seed]) or 'none'}")
    for run in record["fanned_runs"]:
        found += [f"UNSEEDED | {board_check.clean(each)}" for each in run["unmatched"]]
        found += [f"SESSION | {each['session']} | {each['wall_s']:g} s | read {each['tokens_read']} wrote {each['tokens_written']} "
                  f"generated {each['tokens_generated']} | {each['cost_usd']:g} USD | first call read {each['first_call_read']}"
                  for each in run["sessions"]]
    for run_id, differences in record.get("verdict_differences", {}).items():
        found += [f"VERDICT DIFFERENCE | {run_id} | {each['item']} | fanned {each['fanned']} | single {each['single']}"
                  for each in differences]
    found.append(f"BOUND | groups at once in the run {layout['bound']} | calls refused for a rate limit "
                 f"{sum(extra['refused_for_a_rate_limit'] for extra in layout['rounds'].values())}")
    return found


def small_tier(plan: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The forks a plan runs on a model other than the review's, and that model, none when every replica runs on the review's."""
    variants = plan["variants"]
    found = {}
    for context in plan.get("contexts", ()):
        count = sum(1 for group in plan["groups"] for replica in range(1, group["replicas"] + 1)
                    if variants[(replica - 1) % len(variants)] in context["variants"])
        found[context["model"]] = count
    return {"model": ", ".join(found), "forks": sum(found.values())} if found else None


def models_text(model: str, plan: Mapping[str, Any]) -> str:
    """The model or models a round's sessions run on: the round's own, and the small tier's forks from a shared context of
    its own, which is one root more."""
    small = small_tier(plan)
    if not small:
        return f"all {plan['forks']} forks on {model}"
    return (f"{plan['forks'] - small['forks']} forks on {model}, {small['forks']} on {small['model']} from a shared context of its "
            "own (one root more); each is priced at its model's prices")


#: Why the layout caller's bound is what it is, printed beside the plan's bound.
BOUND_BASIS = ("the layout caller's bound, the largest number of reviewers at once the live runs ran with no call refused for a rate limit "
               "(20 in the design loop, 30 in the pre-order round), and never more than the plan's forks")


def dry_lines(plans: Mapping[str, Mapping[str, Any]], singles: Sequence[proof.RunOutcome], models: Mapping[str, str]) -> List[str]:
    """The plan and predicted cost and time of each selected run, beside the bounds the design loop's run is held to."""
    cost = COST_MULTIPLE * proof.mean([run.cost_usd for run in singles])
    wall = proof.WALL_FRACTION * proof.mean([run.wall_s for run in singles])
    found = ["DRY | no session is started and no model is called",
             f"COST MULTIPLE | {COST_MULTIPLE:g} | design loop bounds: cost at most ${cost:.2f} ({COST_MULTIPLE:g} times the single "
             f"mean ${proof.mean([run.cost_usd for run in singles]):.2f}), wall time at most {wall:.0f} s (half the single mean "
             f"{proof.mean([run.wall_s for run in singles]):.0f} s)"]
    for name, plan in plans.items():
        replicas = dict(ROUNDS)[name]
        predicted = plan["predicted"]
        found.append(f"MODEL | {name} | {models_text(models[name], plan)}")
        found += [f"WARNING | {name} | {cost_model.unpriced_text(model)}" for model in cost_model.unpriced(
            [models[name]] + [context["model"] for context in plan.get("contexts", ())])]
        found.append(f"PLAN | {name} | {replicas} replicas | {len(plan['groups'])} groups | {plan['forks']} forks | bound {plan['bound']} | "
                     f"shared context {plan['shared_tokens']} tokens | variants {', '.join(plan['variants'])}")
        found.append(f"BOUND | {name} | {plan['bound']} at once | {BOUND_BASIS}")
        found += [f"GROUP | {name} | {group['id']} | units {', '.join(group['units'])} | {group['replicas']} replicas | expected "
                  f"output {group['expected_output_tokens']} tokens" for group in plan["groups"]]
        found.append(f"PREDICTED | {name} | ${predicted['cost_usd']} | {predicted['wall_s']} s | " + (
            f"cost {'within' if predicted['cost_usd'] <= cost else 'over'} its bound, time {'within' if predicted['wall_s'] <= wall else 'over'} "
            "its bound" if name == "design-loop" else "figures recorded, not bounded"))
        if name == "design-loop":
            near = [f"{what} ${figure} against its bound ${limit:.2f}" if what == "cost" else f"{what} {figure} s against its bound {limit:.0f} s"
                    for what, figure, limit in (("cost", predicted["cost_usd"], cost), ("wall time", predicted["wall_s"], wall))
                    if figure > limit * (1 - proof.NEAR)]
            if near:
                found.append(f"WARNING | {name} | predicted " + " and ".join(near) + f", over it or within {proof.NEAR:.0%} of it; a live run "
                             "is likely to fail that bound or to need a second run")
    return found


# --- The command --------------------------------------------------------------------------------


def tool_commit() -> str:
    done = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else "unknown"


def refusals(work: str) -> List[str]:
    found = []
    if review_seed.inside(work, REPO):
        found.append(f"the work folder {work} is inside the repository; give a folder outside it")
    if os.path.isfile(work):
        found.append(f"the work folder {work} is a file; give a new or empty folder")
    elif os.path.isdir(work) and os.listdir(work):
        found.append(f"the work folder {work} already holds files; give a new or empty folder")
    return found


def main(argv: Optional[List[str]] = None, out=sys.stdout, err=sys.stderr, seed_runner=run_seed,
         environ: Optional[Mapping[str, str]] = None, baselines: str = BASELINES, tree: Callable[[], str] = design_tree,
         main_command: Callable[..., int] = command.main, documents_repo: Optional[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", required=True, help="a new folder outside the repository the run keeps everything in")
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--resvg", default="resvg", help="the resvg program the views are drawn with (default: resvg on the search path)")
    parser.add_argument("--design-model", default=DESIGN_MODEL, help=f"the full model id the design-loop round's replicas run on (default: {DESIGN_MODEL}, the small tier)")
    parser.add_argument("--pre-order-model", default=PRE_ORDER_MODEL, help=f"the full model id the pre-order round's first two replicas run on; the third runs on the layout caller's small-tier model (default: {PRE_ORDER_MODEL}, the mid-tier)")
    parser.add_argument("--only", choices=[name for name, _ in ROUNDS], default=None,
                        help="run one round: design-loop (two replicas) or pre-order (three); default both")
    parser.add_argument("--bound", type=int, default=None, help="the most sessions at once (default: every fork together)")
    parser.add_argument("--dry", action="store_true", help="print each run's plan and predicted cost and time and start no session")
    parser.add_argument("--json", action="store_true", help="print the result as one JSON document")
    args = parser.parse_args(argv)
    environ = dict(environ if environ is not None else os.environ)
    work = os.path.abspath(args.work)
    result: Dict[str, Any] = {"result": command.REFUSED, "refusals": refusals(work), "detail": "nothing was run", "lines": []}

    def finish(status: int) -> int:
        if args.json:
            json.dump(result, out, indent=1)
            out.write("\n")
        else:
            for line in result["lines"]:
                print(line, file=out)
            for why in result["refusals"]:
                print(f"REFUSED | {board_check.clean(why)}", file=out)
            print(f"RESULT | {result['result']} | {board_check.clean(result['detail'])}", file=err if status == 2 else out)
        return status

    if args.bound is not None and args.bound < 1:
        result["refusals"].append(f"the bound {args.bound} is below one; give one or more sessions at once")
    for flag, value in (("--design-model", args.design_model), ("--pre-order-model", args.pre_order_model)):
        if not value.strip():
            result["refusals"].append(f"{flag} is empty; give a full model id")
    models = {"design-loop": args.design_model, "pre-order": args.pre_order_model}
    if result["refusals"]:
        return finish(1)
    chosen = [(name, replicas) for name, replicas in ROUNDS if args.only in (None, name)]
    try:
        os.makedirs(work, exist_ok=True)
        seeded = seed_runner(work, args.kicad_cli, args.resvg)
        folder = write_folder(work, seeded, documents_repo)
        with open(os.path.join(work, SEEDS), encoding="utf-8") as handle:
            seeds = json.load(handle)["seeds"]
        key, singles = baseline_runs(baselines, seeds, tree(), BASELINE_MODEL)
        if args.dry:
            plans = {name: plan_of(folder, os.path.join(work, OUT_DIR, name), models[name], replicas, args.bound, environ)
                     for name, replicas in chosen}
            result.update(result="PLANNED", refusals=[], lines=dry_lines(plans, singles, models), plans=plans,
                          detail="no session was started and no model was called")
            return finish(0)
        runs: Dict[str, Tuple[proof.RunOutcome, Dict[str, Any]]] = {}
        os.makedirs(os.path.join(work, OUT_DIR), exist_ok=True)
        for name, replicas in chosen:
            output = os.path.join(work, OUT_DIR, name)
            status, report = run_command(folder, output, models[name], replicas, args.bound, environ, main_command)
            if report.get("cannot_run"):
                raise board_check.CannotRun(report["cannot_run"])
            if not store.holds_record(output):
                raise Refused([f"{name}: {why}" for why in report["refusals"]] or [f"{name}: the run wrote no record"])
            runs[name] = outcome_of(f"layout-fanned-{replicas}", folder, output, seeds, seeded["commit"], name)
            runs[name][1]["command_report"] = {"result": report["result"], "detail": report["detail"],
                                               "refusals": report["refusals"], "bound": report["plan"]["bound"]}
    except Refused as error:
        result["refusals"] = error.causes
        return finish(1)
    except board_check.CannotRun as error:
        result.update(result=command.CANNOT_RUN, refusals=[], detail=str(error))
        return finish(2)
    record = build(seeds, key, singles, runs, {"models": models, "baseline_model": key.model, "tool_commit": tool_commit(), "seeded_commit": seeded["commit"],
                                                 "work": work, "bound": next(iter(runs.values()))[1]["command_report"]["bound"]})
    store.atomic_write_json(os.path.join(work, RECORD), record)
    lines = lines_of(record)
    with open(os.path.join(work, TEXT), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    held = record["verdict"] is None or record["verdict"]["accepted"]
    refused_merge = [name for name, (_, extra) in runs.items() if not extra["merged"]]
    result.update(result="WRITTEN" if held else "FAILED", refusals=[], lines=lines, record=record,
                  detail=os.path.join(work, RECORD) if held else
                  f"the criterion is {record['verdict']['status']}; the record is {os.path.join(work, RECORD)}")
    if refused_merge:
        result["lines"].append(f"NOTE | the merge of {', '.join(refused_merge)} was refused, so no round was written; the seeds are "
                               "judged from the replicas' findings")
    return finish(0 if held else 1)


if __name__ == "__main__":
    sys.exit(main())
