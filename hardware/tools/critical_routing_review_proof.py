#!/usr/bin/env python3
"""Prove the fanned-out critical-routing check on a seeded copy of the method proof design, against its single-reviewer run.

The critical-routing proof seeds known defects on the critical nets of a copy of the method proof design, the only committed design
whose layout plan holds a critical routing section, and has a reviewer that did not route the board follow step 4 of the method's
routing section blind. The copy is seeded by a session that has not read the layout practice catalogue, working in a temporary git
work tree outside this repository: it keeps the copy's records consistent, keeps the critical items locked, commits the copy at the
design's path from the repository's root, and writes the seed list apart. This is the one command that does the rest: it renders
the layout review views of the committed copy with the views command, writes the review folder with the review folder command's
critical-routing mode from that commit (the method and the hardware notes taken from this repository), then runs the critical-routing
caller through the review kit's command on the real agent command line, first the single form once on the mid-tier model, which it
records as this review's baseline file because none is recorded in a form the kit loads (a baseline file that already holds the
single run for this key is loaded and the single form is not run again), then the fanned-out form at the full unit count with the
design loop's two replicas on the small-tier model.

    critical_routing_review_proof.py --work <new folder outside the repository> --seeded-repo <git work tree holding the seeded copy>
                                     --seeds <the seed list> [--kicad-cli ...] [--resvg ...] [--baseline-model M] [--design-model M]
                                     [--bound N] [--baselines <file>] [--dry] [--json]

The seeded repository is a git work tree outside this repository holding the seeded copy of hardware/proof/method-proof at that
path, committed, with a clean work tree; the commit judged is its HEAD. The seed list is a JSON file, either a list or an object
with a `seeds` list, each seed an object with a non-empty `id` and `item`, the catalogue item that covers the seed, and a
description; a seed whose item is no item of the layout practice catalogue or of the plan's board items is refused, and so are ids
given twice. The pass holds no findings table in its record, so a seed counts as found when the fanned-out run gives a failing
verdict, with the finding it raises, against the item that covers it.

The fanned-out run is judged by the kit's pooled criterion with a cost multiple of 1.25: the seeds found are no fewer than the
fewest any single run found, no seed every single run found is missed, the wall time is at most half the single mean and the cost
at most 1.25 times its mean. The record, proof-record.json, and its text, proof-record.txt, are written in the work folder; they
name the baseline key, give every seed with the replicas that raised it, the findings that match no seed, the verdicts item by item
with the differences from the single run, each session's time, tokens read, written and generated, cost and the document
retrievals with any that failed, and the calls refused for a rate limit. A seed not reported is closed where the gap lies and the
proof repeated in a new session.

The work folder keeps the review folder alone in <work>/review-tree/review, since a session starts there and can read the folders
above it; the seed list, the views and the exported copy are under <work>/seed/, each run's output under <work>/out/, and the
record in <work>.

--dry prints the plan of the fanned-out run and its predicted cost and time beside the bounds they would be held to, and, where no
single run is recorded, the plan of the single form; it starts no session and calls no model, but it still renders the views and
writes the review folder.

The agent command line is the program named by REVIEW_KIT_AGENT (claude when it is unset), logged in. A run costs money: the
single form, and the shared context and a fork for each group and replica of the fanned-out form.

Each cause is reported on one line beginning REFUSED, a RESULT line comes last, and the exit status is 0 when the criterion holds,
1 when the command refuses, a run fails or the criterion does not hold or asks for a second run, and 2 when a tool or the agent
command line is missing. --json prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import io
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
import review_catalogue  # noqa: E402
import review_folder  # noqa: E402
import review_proof_harness as harness  # noqa: E402
import review_seed  # noqa: E402
import schematic_review_proof as base  # noqa: E402
from review_kit import command, proof, store  # noqa: E402
from review_kit import costmodel as cost_model  # noqa: E402
from review_kit import executor as ex  # noqa: E402

Refused = harness.Refused
REPO = review_seed.REPO
CALLER = "critical_routing"
DESIGN = "hardware/proof/method-proof"
NAME = "method-proof"
#: The critical classes of the design's layout plan, which its views are rendered for.
CLASSES = ("Power", "Supply", "Ground")
SEED_DIR = "seed"
SEEDS = os.path.join(SEED_DIR, "seeds.json")
EXPORT = os.path.join(SEED_DIR, "export")
VIEWS = os.path.join(SEED_DIR, "views")
REVIEW_TREE = "review-tree"
FOLDER = os.path.join(REVIEW_TREE, "review")
OUT_DIR = "out"
SINGLE_OUT = os.path.join(OUT_DIR, "single")
FANNED_OUT = os.path.join(OUT_DIR, "fanned")
RECORD = "proof-record.json"
TEXT = "proof-record.txt"
BASELINES = os.path.join(TOOLS_DIR, "tests", "fixtures", "review_baselines", "critical_routing_single_runs.json")
#: The mid-tier model the single form runs on, and so the baseline's.
BASELINE_MODEL = "claude-sonnet-5-5"
#: The small-tier model the two replicas run on.
DESIGN_MODEL = "claude-haiku-5-5"
#: The cost multiple of the pooled criterion: the layout proof's, for the design loop's two small-tier replicas.
COST_MULTIPLE = 1.25
REPLICAS = 2
#: The recorded source of a baseline file this command writes.
BASELINE_SOURCE = ("One single-reviewer run of the critical-routing proof on its seeded copy, made through the review kit's single "
                   "form on the mid-tier model by critical_routing_review_proof.py; wall time, cost and tokens are the kit's "
                   "figures for the one session of the run.")


# --- The seeded copy and the folder -------------------------------------------------------------


def seeded_causes(seeded: str, work: str) -> List[str]:
    """Why the seeded repository is not a clean git work tree outside this repository holding the committed copy."""
    found = []
    if not os.path.isdir(seeded):
        return [f"the seeded repository {seeded} is not a folder; give the git work tree the seeding session kept the copy in"]
    if review_seed.inside(seeded, REPO):
        found.append(f"the seeded repository {seeded} is inside this repository; give a work tree outside it")
    if review_seed.inside(seeded, work) or review_seed.inside(work, seeded):
        found.append(f"the seeded repository {seeded} and the work folder {work} hold one another; keep them apart")
    if base.git(seeded, "rev-parse", "--verify", "--quiet", "HEAD^{commit}").returncode != 0:
        return found + [f"{seeded} is not a git work tree with a commit; give the work tree the seeding session committed the copy in"]
    if base.git(seeded, "status", "--porcelain").stdout.strip():
        found.append(f"the seeded repository {seeded} has changes that are not committed; the review judges the commit, so commit "
                     "the copy, or leave nothing else in the work tree")
    if base.git(seeded, "rev-parse", f"HEAD:{DESIGN}").returncode != 0:
        found.append(f"the seeded repository {seeded} holds no {DESIGN} at its commit; commit the seeded copy at that path")
    return found


def view_commands() -> List[str]:
    return ["task hw:views -- --board " + f"{NAME}.kicad_pcb --project {NAME}.kicad_pro " + " ".join(f"--class {name}" for name in CLASSES)
            + " --out <review folder>/views, run from the design's folder"]


def prepare(work: str, seeded: str, kicad_cli: str, resvg: str) -> Dict[str, Any]:
    """What the review folder is written from: the layout review views of the committed copy, rendered by the views command from
    the copy's files as the commit holds them."""
    sha = base.git(seeded, "rev-parse", "HEAD").stdout.strip()
    export = os.path.join(work, EXPORT, DESIGN)
    for name, content in review_seed.archived(seeded, sha, DESIGN).items():
        target = os.path.join(work, EXPORT, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(content)
    views = os.path.join(work, VIEWS)
    argv = [sys.executable, os.path.join(TOOLS_DIR, "board_views.py"), "--kicad-cli", kicad_cli, "--resvg", resvg, "--board",
            f"{NAME}.kicad_pcb", "--project", f"{NAME}.kicad_pro"]
    for name in CLASSES:
        argv += ["--class", name]
    done = subprocess.run(argv + ["--out", views], cwd=export, capture_output=True, text=True)
    if done.returncode == 2:
        raise board_check.CannotRun(f"the views could not be rendered: {board_check.clean((done.stderr or done.stdout).strip())}")
    if done.returncode != 0:
        raise Refused([f"the views of the seeded copy could not be rendered: {board_check.clean(done.stdout.strip())}"])
    return {"views": views}


def write_folder(work: str, seeded: str, prepared: Mapping[str, Any], documents_repo: Optional[str] = None) -> str:
    """The review folder, written by the review folder command's critical-routing mode from the seeded copy's commit, with the
    views, and the method and notes of this repository."""
    folder = os.path.join(work, FOLDER)
    os.makedirs(os.path.dirname(folder), exist_ok=True)
    argv = ["--review", review_folder.CRITICAL_ROUTING, "--repo", seeded, "--commit", "HEAD", "--design", DESIGN, "--out", folder,
            "--views", prepared["views"], "--number", "1"] + (["--documents-repo", documents_repo] if documents_repo else [])
    for line in view_commands():
        argv += ["--view-command", line]
    out = io.StringIO()
    status = review_folder.main(argv + ["--json"], out=out)
    written = json.loads(out.getvalue())
    if status != 0:
        raise Refused(written.get("refusals") or [written.get("detail", "the folder command failed")])
    return folder


def load_seeds(path: str, folder: str) -> List[Dict[str, Any]]:
    """The seed list: each seed an id and the item that covers it. A list that is not readable, a seed without an id or an item,
    an id given twice and an item that is no catalogue item or board item of the folder's method and plan are refused."""
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused([f"the seed list {path} cannot be read as JSON ({error})"])
    seeds = loaded.get("seeds") if isinstance(loaded, dict) else loaded
    if not isinstance(seeds, list) or not seeds:
        raise Refused([f"the seed list {path} holds no list of seeds; give a list, or an object with a `seeds` list"])
    causes = []
    for number, seed in enumerate(seeds, 1):
        if not isinstance(seed, dict) or not all(isinstance(seed.get(key), str) and seed[key].strip() for key in ("id", "item")):
            causes.append(f"seed {number} of the seed list has no `id` and `item` as text; give each seed its id and the item "
                          "that covers it")
    ids = [seed["id"] for seed in seeds if isinstance(seed, dict) and isinstance(seed.get("id"), str)]
    causes += [f"the seed list gives the id {each} twice" for each in dict.fromkeys(ids) if ids.count(each) > 1]
    if causes:
        raise Refused(causes)
    try:
        known = {item for _, _, items in review_catalogue.areas(folder) for item in items} | set(review_catalogue.own_items(folder))
    except review_folder.ReviewFolderProblem as error:
        raise Refused([str(error)])
    unknown = [f"the seed {seed['id']} names the item {seed['item']!r}, which is no item of the layout practice catalogue or of the "
               "plan's board items" for seed in seeds if seed["item"] not in known]
    if unknown:
        raise Refused(unknown)
    return seeds


# --- Matching seeds to results ------------------------------------------------------------------


def parsed_round(text: str) -> Dict[str, Any]:
    """The items a merged pass, written as Markdown with or without its section heading, gives a failing verdict: the verdicts
    of the pass's table, a later step of a verdict written `cannot judge, then fail` being the one that stands."""
    _, rows, _ = board_history.table(text.splitlines(), board_history.CRITICAL_TABLE)
    return {"raised_by": [row[0].strip("`") for row in rows if row[3].strip("` ").split(", then ")[-1].startswith("fail")]}


def names(item: str, cell: str) -> bool:
    return cell.strip() == item


def matches(seed: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    """Whether a finding, which a fail raises, is of the item that covers the seed."""
    return str(row.get("Item", "")).strip() == seed["item"]


# --- The record and its text ----------------------------------------------------------------------


def build(seeds: Sequence[Mapping[str, Any]], key: proof.BaselineKey, singles: Sequence[proof.RunOutcome], fanned: proof.RunOutcome,
          extra: Mapping[str, Any], context: Mapping[str, Any]) -> Dict[str, Any]:
    """The kit's record of the proof over the fanned-out run, and what the run's saved streams show."""
    record = proof.build_record(seeds, singles, [fanned], COST_MULTIPLE, [key])
    record["critical_routing"] = dict(context, fanned=extra, baseline_key=key.id)
    return record


def lines_of(record: Mapping[str, Any]) -> List[str]:
    context = record["critical_routing"]
    extra = context["fanned"]
    found = [f"PROOF | single form on {context['baseline_model']} ({context['single_form']}) | fanned form on "
             f"{context['models']['fanned']} with {REPLICAS} replicas | tool commit {context['tool_commit']} | seeded copy "
             f"commit {context['seeded_commit']} | cost multiple {COST_MULTIPLE:g}"]
    found.append(f"BASELINE KEY | {context['baseline_key']}")
    found += [f"CRITERION | {line}" for line in proof.record_lines(record)]
    found.append(f"ROUND | fanned | refused for a rate limit {extra['refused_for_a_rate_limit']} | retrievals "
                 f"{harness.total(extra['retrievals'], 'retrieved')} failed {harness.total(extra['retrievals'], 'failed')} | merged "
                 f"pass {'written' if extra['merged'] else 'refused'} | seeds the merged pass names "
                 f"{', '.join(extra['merged_round_seeds_found'] or []) or 'none'}")
    found += [f"RETRIEVALS | fanned | {label} | retrieved {entry['retrieved']} failed {entry['failed']}"
              for label, entry in extra["retrievals"].items() if entry["retrieved"]]
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
                 f"{extra['refused_for_a_rate_limit']}")
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
    found.append(f"PLAN | fanned | {REPLICAS} replicas on {model} | {len(plan['groups'])} groups | {plan['forks']} forks | bound "
                 f"{plan['bound']} | shared context {plan['shared_tokens']} tokens | variants {', '.join(plan['variants'])}")
    found += [f"GROUP | {group['id']} | units {', '.join(group['units'])} | {group['replicas']} replicas | expected output "
              f"{group['expected_output_tokens']} tokens" for group in plan["groups"]]
    found.append(f"PREDICTED | fanned | ${predicted['cost_usd']} | {predicted['wall_s']} s | cost "
                 f"{'within' if predicted['cost_usd'] <= cost else 'over'} its bound, time "
                 f"{'within' if predicted['wall_s'] <= wall else 'over'} its bound")
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
        found.append(f"the work folder {work} is inside the repository, and so is the review folder {os.path.join(work, FOLDER)} "
                     "it would hold; give a folder outside it")
    if os.path.isfile(work):
        found.append(f"the work folder {work} is a file; give a new or empty folder")
    elif os.path.isdir(work) and os.listdir(work):
        found.append(f"the work folder {work} already holds files; give a new or empty folder")
    return found


def single_key(folder: str, work: str, model: str, seeds: Sequence[Mapping[str, Any]], tree: str,
               environ: Mapping[str, str]) -> proof.BaselineKey:
    """The key the single form would be recorded under: the seed list, the design, the model and the prompt it would be given."""
    run = harness.settled_run(CALLER, TOOLS_DIR, folder, os.path.join(work, SINGLE_OUT), model, environ)
    try:
        formed = harness.single_plan(run, environ)
    except ex.CannotRun as error:
        raise board_check.CannotRun(str(error))
    return harness.baseline_key(seeds, tree, model, formed)


def recorded_under(path: str, key: proof.BaselineKey) -> Optional[List[proof.RunOutcome]]:
    """The single runs recorded under exactly this key, None when the file is absent or holds none; a file that cannot be read is
    refused."""
    if not os.path.exists(path):
        return None
    try:
        return proof.load_baselines(path).recorded(key) or None
    except proof.BaselineFileError as error:
        raise Refused([str(error)])


def main(argv: Optional[List[str]] = None, out=sys.stdout, err=sys.stderr, preparer: Callable[..., Dict[str, Any]] = prepare,
         environ: Optional[Mapping[str, str]] = None, baselines: str = BASELINES, main_command: Callable[..., int] = command.main,
         documents_repo: Optional[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", required=True, help="a new folder outside the repository the run keeps everything in")
    parser.add_argument("--seeded-repo", required=True, help="the git work tree outside the repository holding the committed seeded copy")
    parser.add_argument("--seeds", required=True, help="the seed list the seeding session wrote apart from the copy")
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--resvg", default="resvg", help="the resvg rasteriser (default: resvg on the search path)")
    parser.add_argument("--baseline-model", default=BASELINE_MODEL, help=f"the full model id the single form runs on (default: {BASELINE_MODEL}, the mid-tier)")
    parser.add_argument("--design-model", default=DESIGN_MODEL, help=f"the full model id the two replicas run on (default: {DESIGN_MODEL}, the small tier)")
    parser.add_argument("--bound", type=int, default=None, help="the most sessions at once (default: every fork together)")
    parser.add_argument("--baselines", default=None, help="the baselines file the single run is read from or recorded in (default: the review's own)")
    parser.add_argument("--dry", action="store_true", help="print the plan and the predicted cost and time and start no session")
    parser.add_argument("--json", action="store_true", help="print the result as one JSON document")
    args = parser.parse_args(argv)
    environ = dict(environ if environ is not None else os.environ)
    work, seeded, seeds_path = os.path.abspath(args.work), os.path.abspath(args.seeded_repo), os.path.abspath(args.seeds)
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
    for flag, value in (("--baseline-model", args.baseline_model), ("--design-model", args.design_model)):
        if not value.strip():
            result["refusals"].append(f"{flag} is empty; give a full model id")
    if not result["refusals"]:
        result["refusals"] += seeded_causes(seeded, work) + base.seeds_causes(seeds_path, seeded, work)
    if result["refusals"]:
        return finish(1)
    try:
        os.makedirs(work, exist_ok=True)
        prepared = preparer(work, seeded, args.kicad_cli, args.resvg)
        folder = write_folder(work, seeded, prepared, documents_repo)
        seeds = load_seeds(seeds_path, folder)
        os.makedirs(os.path.join(work, SEED_DIR), exist_ok=True)
        shutil.copyfile(seeds_path, os.path.join(work, SEEDS))
        sha = base.git(seeded, "rev-parse", "HEAD").stdout.strip()
        tree = base.design_tree(seeded, "HEAD", DESIGN)
        key = single_key(folder, work, args.baseline_model, seeds, tree, environ)
        singles = recorded_under(baselines, key)
        if args.dry:
            plan = harness.plan_of(CALLER, TOOLS_DIR, folder, os.path.join(work, FANNED_OUT), args.design_model, REPLICAS, args.bound, environ)
            single_plan = None if singles else harness.single_plan_of(CALLER, TOOLS_DIR, folder, os.path.join(work, SINGLE_OUT),
                                                                      args.baseline_model, environ)
            result.update(result="PLANNED", refusals=[], lines=dry_lines(plan, args.design_model, singles, single_plan, key),
                          plan=plan, detail="no session was started and no model was called")
            return finish(0)
        os.makedirs(os.path.join(work, OUT_DIR), exist_ok=True)
        if singles:
            single_form = f"recorded under key {key}"
        else:
            key, outcome = harness.run_single(CALLER, TOOLS_DIR, folder, os.path.join(work, SINGLE_OUT), args.baseline_model,
                                              environ, seeds, sha, tree, matches, baselines, BASELINE_SOURCE)
            singles, single_form = [outcome], f"run now, recorded in {baselines} under key {key}"
        output = os.path.join(work, FANNED_OUT)
        status, report = harness.run_command(CALLER, TOOLS_DIR, folder, output, args.design_model, REPLICAS, args.bound, environ,
                                             main_command)
        if report.get("cannot_run"):
            raise board_check.CannotRun(report["cannot_run"])
        if not store.holds_record(output):
            raise Refused([f"fanned: {why}" for why in report["refusals"]] or ["fanned: the run wrote no record"])
        fanned, extra = harness.outcome_of(CALLER, TOOLS_DIR, "critical-routing-fanned-2", folder, output, seeds, sha, matches,
                                           parsed_round, names, "fanned")
        extra["command_report"] = {"result": report["result"], "detail": report["detail"], "refusals": report["refusals"],
                                   "bound": report["plan"]["bound"]}
    except Refused as error:
        result["refusals"] = error.causes
        return finish(1)
    except board_check.CannotRun as error:
        result.update(result=command.CANNOT_RUN, refusals=[], detail=str(error))
        return finish(2)
    record = build(seeds, key, singles, fanned, extra, {
        "models": {"fanned": args.design_model}, "baseline_model": key.model, "single_form": single_form,
        "tool_commit": harness.tool_commit(), "seeded_commit": sha, "work": work, "bound": extra["command_report"]["bound"]})
    store.atomic_write_json(os.path.join(work, RECORD), record)
    lines = lines_of(record)
    with open(os.path.join(work, TEXT), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    held = record["verdict"]["accepted"]
    result.update(result="WRITTEN" if held else "FAILED", refusals=[], lines=lines, record=record,
                  detail=os.path.join(work, RECORD) if held else
                  f"the criterion is {record['verdict']['status']}; the record is {os.path.join(work, RECORD)}")
    if not extra["merged"]:
        result["lines"].append("NOTE | the merge was refused, so no pass was written; the seeds are judged from the replicas' findings")
    return finish(0 if held else 1)


if __name__ == "__main__":
    sys.exit(main())
