#!/usr/bin/env python3
"""Prove the fanned-out production-files check on the seeded production files of the layout review proof design, against its single-reviewer run.

The production-files proof takes the layout review proof design's production files as `task hw:production-seed` seeds them: a
rotated part, a reversed polarised part, an integrated circuit's first pin turned, a part moved, a catalogue number replaced, and
a layer missing content, shifted and mirrored. That command is scripted, so no session seeds anything; it writes the production files
folder, which holds the unseeded design's rendered views and placement view for the assembler's preview but no preview folder and no
round file, and the seed list apart from it. This is the one command that does the rest: it completes a copy of the folder as a
review folder, then runs the production-files caller through the review kit's command on the real agent command line, first the single form once on the
mid-tier model, which it records as this review's baseline file because none is recorded in a form the kit loads (a baseline file
that already holds the single run for this key is loaded and the single form is not run again), then the fanned-out form at the full
unit count with the pre-order round's three replicas, two of them on the mid-tier model.

    production_files_review_proof.py --work <new folder outside the repository> --folder <the production-files folder>
                                     --seeds <the seed list> [--baseline-model M] [--fanned-model M] [--bound N]
                                     [--baselines <file>] [--dry] [--json]

The folder and the seed list are those `task hw:production-seed -- --seeds <seed list> --out <folder>` writes; the folder is outside
this repository, outside the work folder and apart from the seed list, and it is never written to. The command copies it to
<work>/review and completes the copy as the production-files caller reads a review folder: a preview/ folder of the placement view's
images, which stand in for the assembler's preview, and a round file written by the review folder command's own code naming the commit
of this repository's HEAD, the versions of kicad-cli, gerbonara and resvg (as far as they can be read), the seeding command as the one command, and a line saying
the preview is the unseeded design's rendered placement view standing in for the assembler's. The commit judged is that commit. The seed
list is a JSON file, either a list or an object with a `seeds` list, each seed an object with a non-empty `id` and `target`, the
placed part or the layers the seed lands on (`R4`, `F.SilkS`, `drill, F.Mask, B.Mask`); a target that is neither a part of the placement
file nor a layer of the layer images is refused, and so are ids given twice. A seed counts as found when the fanned-out check gives a
row that is not a match, with its finding, against the parts row or a layer the seed list names for it.

The fanned-out run is judged by the kit's pooled criterion with a cost multiple of 2.25, the multiple the layout pre-order run's 2.1
times the single mean sets for three replicas of which two are on the mid-tier: the seeds found are no fewer than the fewest any
single run found, no seed every single run found is missed, the wall time is at most half the single mean and the cost at most 2.25
times its mean. When the first fanned-out run holds every clause but is within ten per cent of a bound, the command runs the fanned-out form a second time in its own folder, <work>/out/fanned-2, and judges both runs together; it never runs a third. The record, proof-record.json, and its text, proof-record.txt, are written in the work folder; they name the baseline
key, give every seed with the replicas that raised it, the findings that match no seed, the verdicts row by row with the differences
from the single run, each session's time, tokens read, written and generated and cost, and the calls refused for a rate limit. A seed
not reported is closed where the gap lies and the proof repeated in a new session.

Each run's output is under <work>/out/ and the record in <work>; the seed list is copied to <work>/seed/ and the review folder given to
the kit is <work>/review, which holds no seed list.

--dry prints the plan of the fanned-out run, a line saying a second run may follow, and its predicted cost and time (up to twice, counting the second) beside the bounds they would be held to, and, where no
single run is recorded, the plan of the single form; it starts no session and calls no model.

The agent command line is the program named by REVIEW_KIT_AGENT (claude when it is unset), logged in. A run costs money: the
single form, and the shared context and a fork for each group and replica of the fanned-out form, twice over when a second run follows.

Each cause is reported on one line beginning REFUSED, a RESULT line comes last, and the exit status is 0 when the criterion holds,
1 when the command refuses, a run fails or the criterion does not hold or asks for a second run, and 2 when the agent command line is
missing. --json prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_check  # noqa: E402
import board_history  # noqa: E402
import review_caller_production_files as caller  # noqa: E402
import review_folder  # noqa: E402
import review_proof_harness as harness  # noqa: E402
import review_seed  # noqa: E402
import schematic_review_proof as base  # noqa: E402
from review_kit import command, proof, store  # noqa: E402
from review_kit import costmodel as cost_model  # noqa: E402
from review_kit import executor as ex  # noqa: E402

Refused = harness.Refused
REPO = review_seed.REPO
CALLER = "production_files"
DESIGN = review_seed.DESIGN
SEED_DIR = "seed"
SEEDS = os.path.join(SEED_DIR, "seeds.json")
REVIEW_DIR = "review"
OUT_DIR = "out"
SINGLE_OUT = os.path.join(OUT_DIR, "single")
FANNED_OUT = os.path.join(OUT_DIR, "fanned")
RECORD = "proof-record.json"
TEXT = "proof-record.txt"
BASELINES = os.path.join(TOOLS_DIR, "tests", "fixtures", "review_baselines", "production_files_single_runs.json")
#: The mid-tier model the single form runs on, and so the baseline's, and the model the fanned-out run is started with.
BASELINE_MODEL = "claude-sonnet-5-5"
#: The cost multiple of the pooled criterion: the layout pre-order run's 2.1 times the single mean sets it for three replicas, two
#: of them on the mid-tier.
COST_MULTIPLE = 2.25
REPLICAS = 3
#: The recorded source of a baseline file this command writes.
BASELINE_SOURCE = ("One single-reviewer run of the production-files proof on its seeded production files, made through the review "
                   "kit's single form on the mid-tier model by production_files_review_proof.py; wall time, cost and tokens are "
                   "the kit's figures for the one session of the run.")


#: The tools line when a tool's version cannot be read, and gerbonara's, which the seeding pins and which is run in an environment of
#: its own.
GERBONARA = "gerbonara 1.6.3"
UNREAD = "version not read"
PLACEMENT_VIEW = "placement"
#: The ordering step's first two steps, which the seeding command runs on the unseeded design's last commit, as the round file's one
#: command line.
SEEDING_COMMAND = "task hw:production-seed -- --seeds <seed list> --out <folder>"
PREVIEW_NOTE = ("the unseeded design's rendered placement view standing in for the assembler's preview, which a read-only session "
                "cannot obtain; no assembler's preview was saved")


# --- The folder and the seed list -----------------------------------------------------------------


def folder_causes(folder: str, work: str) -> List[str]:
    """Why the production-files folder is not a folder outside this repository and the work folder that the caller can read."""
    if not os.path.isdir(folder):
        return [f"the review folder {folder} is not a folder; give the folder `task hw:production-seed` wrote"]
    found = []
    if review_seed.inside(folder, REPO):
        found.append(f"the review folder {folder} is inside the repository; give the folder outside it that the seeding wrote")
    if review_seed.inside(folder, work) or review_seed.inside(work, folder):
        found.append(f"the review folder {folder} and the work folder {work} hold one another; keep them apart")
    return found


def seeds_causes(seeds: str, folder: str, work: str) -> List[str]:
    found = []
    if not os.path.isfile(seeds):
        return [f"the seed list {seeds} does not exist; give the file `task hw:production-seed` wrote apart"]
    for name, where in (("this repository", REPO), ("the review folder", folder), ("the work folder", work)):
        if review_seed.inside(seeds, where):
            found.append(f"the seed list {seeds} is inside {name} {where}; keep it apart from the files and the review folder")
    return found


def targets(item: str) -> List[str]:
    """The parts and layers a seed's target names, a target naming several separated by commas."""
    return [each.strip() for each in item.split(",") if each.strip()]


def load_seeds(path: str, folder: str) -> List[Dict[str, Any]]:
    """The seed list: each seed an id and the part or layers it lands on, kept as the seed's `item`. A list that is not readable,
    a seed without an id or a target, an id given twice and a target that is no placed part or layer of the folder are refused."""
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused([f"the seed list {path} cannot be read as JSON ({error})"])
    listed = loaded.get("seeds") if isinstance(loaded, dict) else loaded
    if not isinstance(listed, list) or not listed:
        raise Refused([f"the seed list {path} holds no list of seeds; give a list, or an object with a `seeds` list"])
    causes = []
    for number, seed in enumerate(listed, 1):
        if not isinstance(seed, dict) or not all(isinstance(seed.get(key), str) and seed[key].strip() for key in ("id", "target")):
            causes.append(f"seed {number} of the seed list has no `id` and `target` as text; give each seed its id and the part "
                          "or layers it lands on")
    ids = [seed["id"] for seed in listed if isinstance(seed, dict) and isinstance(seed.get("id"), str)]
    causes += [f"the seed list gives the id {each} twice" for each in dict.fromkeys(ids) if ids.count(each) > 1]
    if causes:
        raise Refused(causes)
    try:
        known = {row[0] for row in caller.placement_rows(folder)} | {entry["layer"] for entry in caller.layer_images(folder)}
    except review_folder.ReviewFolderProblem as error:
        raise Refused([str(error)])
    unknown = [f"the seed {seed['id']} names {each!r}, which is no placed part of the placement file or layer of the layer images"
               for seed in listed for each in targets(seed["target"]) if each not in known]
    if unknown:
        raise Refused(unknown)
    return [{**seed, "item": seed["target"].strip()} for seed in listed]


def tool_version(program: str) -> str:
    """The first line a tool prints for --version, or that its version was not read."""
    try:
        done = subprocess.run([program, "--version"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return UNREAD
    lines = (done.stdout or done.stderr).strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else UNREAD


def tools_line(environ: Mapping[str, str]) -> str:
    return (f"kicad-cli {tool_version(environ.get('KICAD_CLI', 'kicad-cli'))}, {GERBONARA}, "
            f"resvg {tool_version(environ.get('RESVG', 'resvg'))}")


def complete_folder(folder: str, review: str, environ: Mapping[str, str]) -> str:
    """Complete a copy of the seeded folder as a review folder at `review`, which is new or empty, and return the commit it names:
    the placement view's images become its preview/ folder, and the round file is written by the review folder command's own code.
    The seeded folder is only read. Refused when the copy cannot be made or holds no placement image."""
    try:
        board = review_folder.committed_board(REPO, "HEAD", DESIGN)
    except review_folder.Refused as error:
        raise Refused(error.causes)
    if os.path.exists(review):
        raise Refused([f"the review folder {review} already exists; give a new work folder"])
    held = {PLACEMENT_VIEW: caller.images_in(folder, PLACEMENT_VIEW)}
    if not held[PLACEMENT_VIEW]:
        raise Refused([f"the folder {folder} holds no placement image ({PLACEMENT_VIEW}/ with a PNG or JPEG), which stands in for the "
                       "assembler's preview; give the folder `task hw:production-seed` wrote"])
    for stale in (review_folder.ROUND_FILE, review_folder.PREVIEW):
        if os.path.exists(os.path.join(folder, stale)):
            raise Refused([f"the folder {folder} already holds {stale}; give the folder `task hw:production-seed` wrote, which holds "
                           "neither"])
    shutil.copytree(folder, review, symlinks=True)
    os.makedirs(os.path.join(review, review_folder.PREVIEW))
    for name in held[PLACEMENT_VIEW]:
        shutil.copyfile(os.path.join(folder, name), os.path.join(review, review_folder.PREVIEW, os.path.basename(name)))
    values = {"commit": board["sha"], "tools": tools_line(environ), "commands": [SEEDING_COMMAND], "preview": PREVIEW_NOTE}
    problems = review_folder.round_problems(values, review_folder.PRODUCTION_FIELDS)
    if problems:
        shutil.rmtree(review, ignore_errors=True)
        raise Refused(problems)
    with open(os.path.join(review, review_folder.ROUND_FILE), "w", encoding="utf-8") as handle:
        handle.write(review_folder.settled(review_folder.round_content(review_folder.PRODUCTION_FIELDS, values)))
    return board["sha"]


# --- Matching seeds to results ------------------------------------------------------------------


def parsed_round(text: str) -> Dict[str, Any]:
    """The rows, of the merged record's Parts and Layers tables, whose verdict is not a match."""
    lines = text.splitlines()
    found = []
    for header in (caller.PARTS_TABLE, caller.LAYERS_TABLE):
        _, rows, _ = board_history.table(lines, header)
        found += [row[0].strip("`") for row in rows if row[-2].strip("` ") != caller.MATCHES]
    return {"raised_by": found}


def unraised(tables: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The verdict rows that are not a match and have no finding of their own, as findings of the row's item, so a seeded part or
    layer judged `cannot judge` is raised as one that differs is."""
    named = {finding.get("Item") for finding in tables.get("Findings", [])}
    return [{"Finding": "", "Item": row.get("Item", ""), "What and where": row.get("Why", "")}
            for row in tables.get("Verdicts", []) if row.get("Verdict") != caller.MATCHES and row.get("Item", "") not in named]


def names(item: str, cell: str) -> bool:
    return cell.strip().casefold() in [each.casefold() for each in targets(item)]


def matches(seed: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    """Whether a finding, which a `differs` row raises, is of the part or a layer the seed lands on."""
    return names(seed["item"], str(row.get("Item", "")))


# --- The record and its text ----------------------------------------------------------------------


def build(seeds: Sequence[Mapping[str, Any]], key: proof.BaselineKey, singles: Sequence[proof.RunOutcome], fanned: Sequence[proof.RunOutcome],
          extras: Sequence[Mapping[str, Any]], context: Mapping[str, Any]) -> Dict[str, Any]:
    """The kit's record of the proof over the fanned-out runs (one, or two when the first is within ten per cent of a bound), and what each run's saved streams show."""
    record = proof.build_record(seeds, singles, list(fanned), COST_MULTIPLE, [key])
    record["production_files"] = dict(context, fanned=extras[0], fanned_runs=list(extras), baseline_key=key.id)
    return record


def lines_of(record: Mapping[str, Any]) -> List[str]:
    context = record["production_files"]
    found = [f"PROOF | single form on {context['baseline_model']} ({context['single_form']}) | fanned form on "
             f"{context['models']['fanned']} with {REPLICAS} replicas | tool commit {context['tool_commit']} | files exported at "
             f"commit {context['seeded_commit']} | cost multiple {COST_MULTIPLE:g}"]
    found.append(f"BASELINE KEY | {context['baseline_key']}")
    found += [f"CRITERION | {line}" for line in proof.record_lines(record)]
    for number, extra in enumerate(context["fanned_runs"], 1):
        round_label = "fanned" if number == 1 else f"fanned-{number}"
        found.append(f"ROUND | {round_label} | refused for a rate limit {extra['refused_for_a_rate_limit']} | merged check "
                     f"{'written' if extra['merged'] else 'refused'} | seeds the merged check names "
                     f"{', '.join(extra['merged_round_seeds_found'] or []) or 'none'}")
    for seed in record["seeds"]:
        for name, replicas in record["seed_replicas"].get(seed, {}).items():
            found.append(f"SEED | {seed} | {name} | raised by {', '.join(replicas) or 'none'}")
    for run in record["fanned_runs"]:
        found += [f"UNSEEDED | {board_check.clean(each)}" for each in run["unmatched"]]
        found += [f"SESSION | {each['session']} | {each['wall_s']:g} s | read {each['tokens_read']} wrote {each['tokens_written']} "
                  f"generated {each['tokens_generated']} | {each['cost_usd']:g} USD | first call read {each['first_call_read']}"
                  for each in run["sessions"]]
    for run_id, differences in record.get("verdict_differences", {}).items():
        found += [f"VERDICT DIFFERENCE | {run_id} | {each['item']} | fanned {each['fanned']} | single {each['single']}"
                  for each in differences]
    found.append(f"BOUND | groups at once in the run {context['bound']} | calls refused for a rate limit "
                 f"{sum(each['refused_for_a_rate_limit'] for each in context["fanned_runs"])}")
    return found


def dry_lines(plan: Mapping[str, Any], model: str, single: Optional[List[proof.RunOutcome]],
              single_plan: Optional[Mapping[str, Any]], key: Optional[proof.BaselineKey] = None) -> List[str]:
    """The plan and predicted cost and time of the fanned-out run, beside the bounds it is held to."""
    found = ["DRY | no session is started and no model is called"]
    if single:
        mean_cost, mean_wall = proof.mean([run.cost_usd for run in single]), proof.mean([run.wall_s for run in single])
        found.append(f"SINGLE | recorded under key {key}: {len(single)} run(s) | mean ${mean_cost:.2f} | mean {mean_wall:.0f} s")
    else:
        mean_cost, mean_wall = single_plan["predicted"]["cost_usd"], single_plan["predicted"]["wall_s"]
        found.append(f"SINGLE | none recorded under key {key}, so the single form would run once on {BASELINE_MODEL} | predicted "
                     f"${mean_cost:.2f} | {mean_wall:.0f} s | {single_plan['forks']} fork | the bounds below are from the prediction")
    cost, wall = COST_MULTIPLE * mean_cost, proof.WALL_FRACTION * mean_wall
    found.append(f"COST MULTIPLE | {COST_MULTIPLE:g} | bounds: cost at most ${cost:.2f} ({COST_MULTIPLE:g} times the single mean "
                 f"${mean_cost:.2f}), wall time at most {wall:.0f} s (half the single mean {mean_wall:.0f} s)")
    predicted = plan["predicted"]
    other = [context["model"] for context in plan.get("contexts", ())]
    found += [f"WARNING | {cost_model.unpriced_text(each)}" for each in cost_model.unpriced([model] + other)]
    found.append(f"PLAN | fanned | {REPLICAS} replicas | {len(plan['groups'])} groups | {plan['forks']} forks | bound "
                 f"{plan['bound']} | shared context {plan['shared_tokens']} tokens | variants {', '.join(plan['variants'])}")
    found += [f"GROUP | {group['id']} | units {', '.join(group['units'])} | {group['replicas']} replicas | expected output "
              f"{group['expected_output_tokens']} tokens" for group in plan["groups"]]
    found.append(f"PREDICTED | fanned | ${predicted['cost_usd']} | {predicted['wall_s']} s | cost "
                 f"{'within' if predicted['cost_usd'] <= cost else 'over'} its bound, time "
                 f"{'within' if predicted['wall_s'] <= wall else 'over'} its bound")
    found.append(f"SECOND RUN | a second fanned-out run follows when the first is within {proof.NEAR:.0%} of a bound | with it the "
                 f"cost is up to ${2 * predicted['cost_usd']:.2f} and the time up to {2 * predicted['wall_s']:.0f} s")
    near = [f"{what} {figure} against its bound {limit:.2f}" for what, figure, limit in
            (("cost", predicted["cost_usd"], cost), ("wall time", predicted["wall_s"], wall)) if figure > limit * (1 - proof.NEAR)]
    if near:
        found.append("WARNING | predicted " + " and ".join(near) + f", over it or within {proof.NEAR:.0%} of it; a live run is "
                     "likely to fail that bound or to need a second run")
    return found


# --- The command --------------------------------------------------------------------------------


def refusals(work: str) -> List[str]:
    found = []
    if review_seed.inside(work, REPO):
        found.append(f"the work folder {work} is inside the repository; give a folder outside it")
    if os.path.isfile(work):
        found.append(f"the work folder {work} is a file; give a new or empty folder")
    elif os.path.isdir(work) and os.listdir(work):
        found.append(f"the work folder {work} already holds files; give a new or empty folder")
    return found


def main(argv: Optional[List[str]] = None, out=sys.stdout, err=sys.stderr, environ: Optional[Mapping[str, str]] = None,
         baselines: str = BASELINES, main_command: Callable[..., int] = command.main) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", required=True, help="a new folder outside the repository the run keeps its output in")
    parser.add_argument("--folder", required=True, help="the production-files folder `task hw:production-seed` wrote, outside the repository")
    parser.add_argument("--seeds", required=True, help="the seed list `task hw:production-seed` wrote apart from the folder")
    parser.add_argument("--baseline-model", default=BASELINE_MODEL, help=f"the full model id the single form runs on (default: {BASELINE_MODEL}, the mid-tier)")
    parser.add_argument("--fanned-model", default=BASELINE_MODEL, help=f"the full model id the fanned-out run is started with (default: {BASELINE_MODEL}); the caller's own replica policy names the model of each replica")
    parser.add_argument("--bound", type=int, default=None, help="the most sessions at once (default: every fork together)")
    parser.add_argument("--baselines", default=None, help="the baselines file the single run is read from or recorded in (default: the review's own)")
    parser.add_argument("--dry", action="store_true", help="print the plan and the predicted cost and time and start no session")
    parser.add_argument("--json", action="store_true", help="print the result as one JSON document")
    args = parser.parse_args(argv)
    environ = dict(environ if environ is not None else os.environ)
    work, folder, seeds_path = os.path.abspath(args.work), os.path.abspath(args.folder), os.path.abspath(args.seeds)
    baselines = os.path.abspath(args.baselines) if args.baselines else baselines
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
    for flag, value in (("--baseline-model", args.baseline_model), ("--fanned-model", args.fanned_model)):
        if not value.strip():
            result["refusals"].append(f"{flag} is empty; give a full model id")
    if not result["refusals"]:
        result["refusals"] += folder_causes(folder, work) + seeds_causes(seeds_path, folder, work)
    if result["refusals"]:
        return finish(1)
    try:
        seeds = load_seeds(seeds_path, folder)
        review = os.path.join(work, REVIEW_DIR)
        commit = complete_folder(folder, review, environ)
        folder = review
        os.makedirs(os.path.join(work, SEED_DIR), exist_ok=True)
        shutil.copyfile(seeds_path, os.path.join(work, SEEDS))
        tree = base.design_tree(REPO, "HEAD", DESIGN)
        key = harness.single_key(CALLER, TOOLS_DIR, folder, os.path.join(work, SINGLE_OUT), args.baseline_model, seeds, tree, environ)
        singles = harness.recorded_under(baselines, key)
        if args.dry:
            plan = harness.plan_of(CALLER, TOOLS_DIR, folder, os.path.join(work, FANNED_OUT), args.fanned_model, REPLICAS, args.bound, environ)
            single_plan = None if singles else harness.single_plan_of(CALLER, TOOLS_DIR, folder, os.path.join(work, SINGLE_OUT),
                                                                      args.baseline_model, environ)
            result.update(result="PLANNED", refusals=[], lines=dry_lines(plan, args.fanned_model, singles, single_plan, key),
                          plan=plan, detail="no session was started and no model was called")
            return finish(0)
        os.makedirs(os.path.join(work, OUT_DIR), exist_ok=True)
        with harness.baseline_lock(baselines):
            singles = harness.recorded_under(baselines, key)
            if singles:
                single_form = f"recorded under key {key}"
            else:
                key, outcome = harness.run_single(CALLER, TOOLS_DIR, folder, os.path.join(work, SINGLE_OUT), args.baseline_model,
                                                  environ, seeds, commit, tree, matches, baselines, BASELINE_SOURCE, extra_rows=unraised)
                singles, single_form = [outcome], f"run now, recorded in {baselines} under key {key}"

        def fan_out(index: int) -> Tuple[proof.RunOutcome, Dict[str, Any]]:
            run_id, output = harness.numbered("production-files-fanned-3", os.path.join(work, FANNED_OUT), index)
            status, report = harness.run_command(CALLER, TOOLS_DIR, folder, output, args.fanned_model, REPLICAS, args.bound, environ,
                                                 main_command)
            if report.get("cannot_run"):
                raise board_check.CannotRun(report["cannot_run"])
            if not store.holds_record(output):
                raise Refused([f"fanned: {why}" for why in report["refusals"]] or ["fanned: the run wrote no record"])
            fanned, extra = harness.outcome_of(CALLER, TOOLS_DIR, run_id, folder, output, seeds, commit, matches, parsed_round, names,
                                               "fanned", extra_rows=unraised)
            extra["command_report"] = {"result": report["result"], "detail": report["detail"], "refusals": report["refusals"],
                                       "bound": report["plan"]["bound"]}
            return fanned, extra

        runs = harness.fanned_runs(fan_out, singles, COST_MULTIPLE)
    except Refused as error:
        result["refusals"] = error.causes
        return finish(1)
    except board_check.CannotRun as error:
        result.update(result=command.CANNOT_RUN, refusals=[], detail=str(error))
        return finish(2)
    record = build(seeds, key, singles, [run for run, _ in runs], [extra for _, extra in runs], {
        "models": {"fanned": args.fanned_model}, "baseline_model": key.model, "single_form": single_form,
        "tool_commit": harness.tool_commit(), "seeded_commit": commit, "work": work, "bound": runs[0][1]["command_report"]["bound"]})
    store.atomic_write_json(os.path.join(work, RECORD), record)
    lines = lines_of(record)
    with open(os.path.join(work, TEXT), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    held = record["verdict"]["accepted"]
    result.update(result="WRITTEN" if held else "FAILED", refusals=[], lines=lines, record=record,
                  detail=os.path.join(work, RECORD) if held else
                  f"the criterion is {record['verdict']['status']}; the record is {os.path.join(work, RECORD)}")
    if not all(extra["merged"] for _, extra in runs):
        result["lines"].append("NOTE | the merge was refused, so no check record was written; the seeds are judged from the replicas' findings")
    return finish(0 if held else 1)


if __name__ == "__main__":
    sys.exit(main())
