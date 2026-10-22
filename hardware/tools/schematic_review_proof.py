#!/usr/bin/env python3
"""Prove the fanned-out schematic review on a seeded copy of the circuit review proof design, against its single-reviewer run.

The schematic review proof seeds known defects into a copy of the circuit review proof design and has a reviewer that did not
draw the schematic follow the method's schematic review step blind. The copy is seeded by a session that has not read the circuit
practice catalogue, working in a temporary git work tree outside this repository: it keeps the copy's records consistent, commits
the copy at the design's path from the repository's root, and writes the seed list apart. This is the one command that does the
rest for the fanned-out form: it runs the pre-order check on the committed copy and refuses a copy it does not pass, exports the
copy's netlist, draws its sheets, writes the review folder with the schematic folder command from that commit (the method and the
hardware notes taken from this repository), then runs the schematic caller through the review kit's command on the real agent
command line, first the single form once on the mid-tier model, which it records as this review's baseline file because none is
recorded in a form the kit loads (a baseline file that already holds the single runs of this seed list, design and model is
loaded and the single form is not run again), then the fanned-out form at the full unit count with the design loop's two replicas
on the small-tier model.

    schematic_review_proof.py --work <new folder outside the repository> --seeded-repo <git work tree holding the seeded copy>
                              --seeds <the seed list> [--kicad-cli ...] [--baseline-model M] [--design-model M] [--bound N]
                              [--baselines <file>] [--dry] [--json]

The seeded repository is a git work tree outside this repository holding the seeded copy of hardware/proof/circuit-review-proof at
that path, committed, with a clean work tree; the commit judged is its HEAD. The seed list is a JSON file, either a list or an
object with a `seeds` list, each seed an object with a non-empty `id` and `item`, the catalogue item that covers the seed, and a
description; a seed whose item is no item of the method's circuit practice catalogue is refused, and so are ids given twice.

The fanned-out run is judged by the kit's pooled criterion with a cost multiple of 1.25: the seeds found are no fewer than the
fewest any single run found, no seed every single run found is missed, the wall time is at most half the single mean and the cost
at most 1.25 times its mean. The record, proof-record.json, and its text, proof-record.txt, are written in the work folder; they
give every seed with the replicas that raised it, the findings that match no seed, the verdicts item by item and net, part or sheet
with the differences from the single run, each session's time, tokens read, written and generated, cost, first-call cache read
and the document retrievals with any that failed, per unit, and the calls refused for a rate limit. A seed not reported is closed
where the gap lies and the proof repeated in a new session.

The work folder keeps the review folder alone in <work>/review-tree/review, since a session starts there and can read the folders
above it; the seed list, the check's report, the netlist export and the sheets are under <work>/seed/, each run's output under
<work>/out/, and the record in <work>.

--dry prints the plan of the fanned-out run and its predicted cost and time beside the bounds they would be held to, and, where
no single run is recorded, the plan of the single form; it starts no session and calls no model, but it still runs the check,
exports the netlist, draws the sheets and writes the review folder.

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
import re
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_check  # noqa: E402
import board_prove  # noqa: E402
import board_review_history  # noqa: E402
import review_catalogue  # noqa: E402
import review_folder  # noqa: E402
import review_proof_harness as harness  # noqa: E402
import review_seed  # noqa: E402
import schematic_review_folder  # noqa: E402
from review_kit import command, proof, store  # noqa: E402
from review_kit import costmodel as cost_model  # noqa: E402

Refused = harness.Refused
REPO = review_seed.REPO
CALLER = "schematic"
DESIGN = board_prove.REVIEW_DESIGN
NAME = board_prove.REVIEW_NAME
#: Where the work folder keeps each part, relative to it. A session starts in the review folder and can read the folders above
#: it, so the review folder lives alone in a folder of its own and the seed material and the output folders sit beside that
#: folder's parent, not in it.
SEED_DIR = "seed"
SEEDS = os.path.join(SEED_DIR, "seeds.json")
EXPORT = os.path.join(SEED_DIR, "export")
NETLIST = os.path.join(SEED_DIR, "review.net")
SHEETS = os.path.join(SEED_DIR, "sheets")
REPORT = os.path.join(SEED_DIR, "check-report.txt")
REVIEW_TREE = "review-tree"
FOLDER = os.path.join(REVIEW_TREE, "review")
OUT_DIR = "out"
SINGLE_OUT = os.path.join(OUT_DIR, "single")
FANNED_OUT = os.path.join(OUT_DIR, "fanned")
RECORD = "proof-record.json"
TEXT = "proof-record.txt"
BASELINES = os.path.join(TOOLS_DIR, "tests", "fixtures", "review_baselines", "schematic_single_runs.json")
#: The mid-tier model the single form runs on, and so the baseline's.
BASELINE_MODEL = "claude-sonnet-5-5"
#: The small-tier model the two replicas run on.
DESIGN_MODEL = "claude-haiku-5-5"
#: The cost multiple of the pooled criterion: the layout proof's, for the design loop's two small-tier replicas.
COST_MULTIPLE = 1.25
REPLICAS = 2
#: The records of the design the round reads, as the method names them; those the committed copy holds are the round's.
RECORDS = ("constraints.md", "circuit-proof.md", "bring-up-provision.md", "separation-basis.yaml", "pin-allocation.yaml",
           "parts-specification.yaml", "catalogue-extract.yaml", "pin-limits.yaml", "derating-policy.yaml", "board-rules.yaml")
#: The recorded source of a baseline file this command writes.
BASELINE_SOURCE = ("One single-reviewer run of the schematic review proof on its seeded copy, made through the review kit's single "
                   "form on the mid-tier model by schematic_review_proof.py; wall time, cost and tokens are the kit's figures for "
                   "the one session of the run.")


# --- The seeded copy and the folder -------------------------------------------------------------


def git(repo: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def seeded_causes(seeded: str, work: str) -> List[str]:
    """Why the seeded repository is not a clean git work tree outside this repository holding the committed copy."""
    found = []
    if not os.path.isdir(seeded):
        return [f"the seeded repository {seeded} is not a folder; give the git work tree the seeding session kept the copy in"]
    if review_seed.inside(seeded, REPO):
        found.append(f"the seeded repository {seeded} is inside this repository; give a work tree outside it")
    if review_seed.inside(seeded, work) or review_seed.inside(work, seeded):
        found.append(f"the seeded repository {seeded} and the work folder {work} hold one another; keep them apart")
    head = git(seeded, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if head.returncode != 0:
        return found + [f"{seeded} is not a git work tree with a commit; give the work tree the seeding session committed the copy in"]
    if git(seeded, "status", "--porcelain").stdout.strip():
        found.append(f"the seeded repository {seeded} has changes that are not committed; the review judges the commit, so commit "
                     "the copy, or leave nothing else in the work tree")
    if git(seeded, "rev-parse", f"HEAD:{DESIGN}").returncode != 0:
        found.append(f"the seeded repository {seeded} holds no {DESIGN} at its commit; commit the seeded copy at that path")
    return found


def seeds_causes(seeds: str, seeded: str, work: str) -> List[str]:
    found = []
    if not os.path.isfile(seeds):
        return [f"the seed list {seeds} does not exist; give the file the seeding session wrote apart"]
    for name, where in (("this repository", REPO), ("the seeded repository", seeded), ("the work folder", work)):
        if review_seed.inside(seeds, where):
            found.append(f"the seed list {seeds} is inside {name} {where}; keep it apart from the copy and the review folder")
    return found


def run_check(seeded: str, kicad_cli: str) -> Tuple[int, List[str], str]:
    """The pre-order check run on the seeded repository."""
    done = subprocess.run([sys.executable, os.path.join(TOOLS_DIR, "board_check.py"), "--root", seeded, "--kicad-cli", kicad_cli],
                          capture_output=True, text=True)
    return done.returncode, done.stdout.splitlines(), done.stderr.strip()


def prepare(work: str, seeded: str, kicad_cli: str) -> Dict[str, Any]:
    """What the review folder is written from: the check's report on the committed copy, the netlist exported from it and the
    drawing of each of its sheets, the last two by KiCad's own command-line tool; the facts about each."""
    os.makedirs(os.path.join(work, SEED_DIR), exist_ok=True)
    status, lines, stderr = run_check(seeded, kicad_cli)
    if status == 2:
        raise board_check.CannotRun(f"the pre-order check could not run on the seeded copy: {board_check.clean(stderr)}")
    report = [line.replace(os.path.realpath(seeded), ".").replace(seeded, ".") for line in lines]
    if status != 0:
        raise Refused(["the pre-order check fails the seeded copy, and a review begins only once it passes a board, so a seed the "
                       "check catches is no test of the review"] + [f"CHECK | {line}" for line in report[1:]])
    with open(os.path.join(work, REPORT), "w", encoding="utf-8") as handle:
        handle.write("\n".join(report) + "\n")
    sha = git(seeded, "rev-parse", "HEAD").stdout.strip()
    export = os.path.join(work, EXPORT, DESIGN)
    for name, content in review_seed.archived(seeded, sha, DESIGN).items():
        target = os.path.join(work, EXPORT, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(content)
    netlist = os.path.join(work, NETLIST)
    exporter = [kicad_cli, "sch", "export", "netlist", "--output", netlist, f"{NAME}.kicad_sch"]
    done = subprocess.run(exporter, cwd=export, capture_output=True, text=True)
    if done.returncode != 0 or not os.path.isfile(netlist):
        raise board_check.CannotRun(f"KiCad could not export the netlist of the seeded copy ({board_check.clean((done.stderr or done.stdout).strip())})")
    sheets = os.path.join(work, SHEETS)
    done = subprocess.run([sys.executable, os.path.join(TOOLS_DIR, "schematic_sheets.py"), "--root", seeded, "--kicad-cli", kicad_cli,
                           "--out", sheets], capture_output=True, text=True)
    if done.returncode == 2:
        raise board_check.CannotRun(f"the sheets could not be drawn: {board_check.clean((done.stderr or done.stdout).strip())}")
    if done.returncode != 0:
        raise Refused([f"the sheets of the seeded copy could not be drawn: {board_check.clean(done.stdout.strip())}"])
    return {"netlist": netlist, "sheets": os.path.join(sheets, DESIGN), "report": os.path.join(work, REPORT),
            "netlist_command": f"kicad-cli sch export netlist --output <work folder>/review.net {NAME}.kicad_sch"}


def record_names(seeded: str) -> List[str]:
    """The records of the design the round reads that the committed copy holds."""
    held = review_seed.archived(seeded, "HEAD", DESIGN)
    return [name for name in RECORDS if f"{DESIGN}/{name}" in held]


def write_folder(work: str, seeded: str, prepared: Mapping[str, Any], documents_repo: Optional[str] = None) -> str:
    """The review folder, written by the schematic folder command from the seeded copy's commit, with the netlist, the sheets and
    the check's report, and the method and notes of this repository."""
    folder = os.path.join(work, FOLDER)
    os.makedirs(os.path.dirname(folder), exist_ok=True)
    argv = ["--repo", seeded, "--commit", "HEAD", "--design", DESIGN, "--out", folder, "--netlist", prepared["netlist"],
            "--netlist-command", prepared["netlist_command"], "--sheets", prepared["sheets"], "--check-report",
            prepared["report"], "--number", "1"] + (["--documents-repo", documents_repo] if documents_repo else [])
    for name in record_names(seeded):
        argv += ["--record", name]
    out = io.StringIO()
    status = schematic_review_folder.main(argv + ["--json"], out=out)
    written = json.loads(out.getvalue())
    if status != 0:
        raise Refused(written.get("refusals") or [written.get("detail", "the folder command failed")])
    return folder


def load_seeds(path: str, folder: str) -> List[Dict[str, Any]]:
    """The seed list: each seed an id and the catalogue item that covers it. A list that is not readable, a seed without an id or
    an item, an id given twice and an item the circuit practice catalogue of the folder's method lacks are refused."""
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
            causes.append(f"seed {number} of the seed list has no `id` and `item` as text; give each seed its id and the catalogue item "
                          "that covers it")
    ids = [seed["id"] for seed in seeds if isinstance(seed, dict) and isinstance(seed.get("id"), str)]
    causes += [f"the seed list gives the id {each} twice" for each in dict.fromkeys(ids) if ids.count(each) > 1]
    if causes:
        raise Refused(causes)
    try:
        known = {item for _, _, items in review_catalogue.areas(folder, review_folder.CIRCUIT_SECTION) for item in items}
    except review_folder.ReviewFolderProblem as error:
        raise Refused([str(error)])
    unknown = [f"the seed {seed['id']} names the item {seed['item']!r}, which is no item of the circuit practice catalogue"
               for seed in seeds if seed["item"] not in known]
    if unknown:
        raise Refused(unknown)
    return seeds


# --- The baseline -------------------------------------------------------------------------------


def design_tree(repo: str, ref: str = "HEAD", design: Optional[str] = None) -> str:
    """The git tree id of the proof design's folder in the seeded copy, which the baseline key holds as the design."""
    design = design or DESIGN
    done = git(repo, "rev-parse", f"{ref}:{design}")
    if done.returncode != 0:
        raise Refused([f"the tree of {design} at {ref} in {repo} cannot be read: {board_check.clean(done.stderr.strip())}"])
    return done.stdout.strip()


def recorded_baseline(path: str, seeds: Sequence[Mapping[str, Any]], design: str, model: str
                      ) -> Optional[Tuple[proof.BaselineKey, List[proof.RunOutcome]]]:
    """The recorded single runs whose key holds this seed list, design and model, with the key; None when the file is absent or
    holds none for them, so the single form is run. A file that cannot be read is refused."""
    if not os.path.exists(path):
        return None
    try:
        loaded = proof.load_baselines(path)
    except proof.BaselineFileError as error:
        raise Refused([str(error)])
    wanted = {"seeds": proof.seed_list_hash(seeds), "design": design, "model": model}
    for key in loaded.keys.values():
        if key.form == proof.SINGLE and all(getattr(key, name) == value for name, value in wanted.items()):
            return key, loaded.recorded(key)
    return None


# --- Matching seeds to findings -----------------------------------------------------------------


def parsed_round(text: str) -> Dict[str, Any]:
    """The findings' Raised by cells of a round written as Markdown, with or without its heading."""
    if not board_review_history.round_numbers(text):
        text = "## Round 1\n\n" + text
    bodies = board_review_history.round_bodies(text)
    parsed = board_review_history.Round(bodies[min(bodies)] if bodies else [])
    header, rows = parsed.findings
    return {"raised_by": [dict(zip(header, row)).get("Raised by", "") for row in rows] if "Raised by" in header else []}


def names(item: str, cell: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9-]){re.escape(item)}(?![A-Za-z0-9-])", cell))


def matches(seed: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    """Whether a finding is raised by the catalogue item that covers the seed, in its Item cell."""
    return str(row.get("Item", "")).strip() == seed["item"]


# --- The record and its text ----------------------------------------------------------------------


def build(seeds: Sequence[Mapping[str, Any]], key: proof.BaselineKey, singles: Sequence[proof.RunOutcome], fanned: proof.RunOutcome,
          extra: Mapping[str, Any], context: Mapping[str, Any]) -> Dict[str, Any]:
    """The kit's record of the proof over the fanned-out run, and what the run's saved streams show."""
    record = proof.build_record(seeds, singles, [fanned], COST_MULTIPLE, [key])
    record["schematic"] = dict(context, fanned=extra)
    return record


def lines_of(record: Mapping[str, Any]) -> List[str]:
    schematic = record["schematic"]
    extra = schematic["fanned"]
    found = [f"PROOF | single form on {schematic['baseline_model']} ({schematic['single_form']}) | fanned form on "
             f"{schematic['models']['fanned']} with {REPLICAS} replicas | tool commit {schematic['tool_commit']} | seeded copy "
             f"commit {schematic['seeded_commit']} | cost multiple {COST_MULTIPLE:g}"]
    found += [f"CRITERION | {line}" for line in proof.record_lines(record)]
    found.append(f"ROUND | fanned | refused for a rate limit {extra['refused_for_a_rate_limit']} | retrievals "
                 f"{harness.total(extra['retrievals'], 'retrieved')} failed {harness.total(extra['retrievals'], 'failed')} | merged "
                 f"round {'written' if extra['merged'] else 'refused'} | seeds the merged round names "
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
    found.append(f"BOUND | groups at once in the run {schematic['bound']} | calls refused for a rate limit "
                 f"{extra['refused_for_a_rate_limit']}")
    return found


def dry_lines(plan: Mapping[str, Any], model: str, single: Optional[List[proof.RunOutcome]],
              single_plan: Optional[Mapping[str, Any]]) -> List[str]:
    """The plan and predicted cost and time of the fanned-out run, beside the bounds it is held to."""
    found = ["DRY | no session is started and no model is called"]
    if single:
        mean_cost, mean_wall = proof.mean([run.cost_usd for run in single]), proof.mean([run.wall_s for run in single])
        found.append(f"SINGLE | recorded: {len(single)} run(s) | mean ${mean_cost:.2f} | mean {mean_wall:.0f} s")
    else:
        mean_cost, mean_wall = single_plan["predicted"]["cost_usd"], single_plan["predicted"]["wall_s"]
        found.append(f"SINGLE | none recorded, so the single form would run once on {BASELINE_MODEL} | predicted ${mean_cost:.2f} | "
                     f"{mean_wall:.0f} s | {single_plan['forks']} fork | the bounds below are from the prediction")
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
        found.append(f"the work folder {work} is inside the repository; give a folder outside it")
    if os.path.isfile(work):
        found.append(f"the work folder {work} is a file; give a new or empty folder")
    elif os.path.isdir(work) and os.listdir(work):
        found.append(f"the work folder {work} already holds files; give a new or empty folder")
    return found


def main(argv: Optional[List[str]] = None, out=sys.stdout, err=sys.stderr, preparer: Callable[..., Dict[str, Any]] = prepare,
         environ: Optional[Mapping[str, str]] = None, baselines: str = BASELINES, main_command: Callable[..., int] = command.main,
         documents_repo: Optional[str] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", required=True, help="a new folder outside the repository the run keeps everything in")
    parser.add_argument("--seeded-repo", required=True, help="the git work tree outside the repository holding the committed seeded copy")
    parser.add_argument("--seeds", required=True, help="the seed list the seeding session wrote apart from the copy")
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
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
        result["refusals"] += seeded_causes(seeded, work) + seeds_causes(seeds_path, seeded, work)
    if result["refusals"]:
        return finish(1)
    try:
        os.makedirs(work, exist_ok=True)
        prepared = preparer(work, seeded, args.kicad_cli)
        folder = write_folder(work, seeded, prepared, documents_repo)
        seeds = load_seeds(seeds_path, folder)
        os.makedirs(os.path.join(work, SEED_DIR), exist_ok=True)
        shutil.copyfile(seeds_path, os.path.join(work, SEEDS))
        sha = git(seeded, "rev-parse", "HEAD").stdout.strip()
        tree = design_tree(seeded)
        recorded = recorded_baseline(baselines, seeds, tree, args.baseline_model)
        if args.dry:
            plan = harness.plan_of(CALLER, TOOLS_DIR, folder, os.path.join(work, FANNED_OUT), args.design_model, REPLICAS, args.bound, environ)
            single_plan = None if recorded else harness.single_plan_of(CALLER, TOOLS_DIR, folder, os.path.join(work, SINGLE_OUT),
                                                                        args.baseline_model, environ)
            result.update(result="PLANNED", refusals=[], lines=dry_lines(plan, args.design_model, recorded[1] if recorded else None, single_plan),
                          plan=plan, detail="no session was started and no model was called")
            return finish(0)
        os.makedirs(os.path.join(work, OUT_DIR), exist_ok=True)
        if recorded:
            key, singles = recorded
            single_form = "recorded"
        else:
            key, outcome = harness.run_single(CALLER, TOOLS_DIR, folder, os.path.join(work, SINGLE_OUT), args.baseline_model,
                                              environ, seeds, sha, tree, matches, baselines, BASELINE_SOURCE)
            singles, single_form = [outcome], "run now, recorded in " + baselines
        output = os.path.join(work, FANNED_OUT)
        status, report = harness.run_command(CALLER, TOOLS_DIR, folder, output, args.design_model, REPLICAS, args.bound, environ,
                                             main_command)
        if report.get("cannot_run"):
            raise board_check.CannotRun(report["cannot_run"])
        if not store.holds_record(output):
            raise Refused([f"fanned: {why}" for why in report["refusals"]] or ["fanned: the run wrote no record"])
        fanned, extra = harness.outcome_of(CALLER, TOOLS_DIR, "schematic-fanned-2", folder, output, seeds, sha, matches, parsed_round,
                                           names, "fanned")
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
        result["lines"].append("NOTE | the merge was refused, so no round was written; the seeds are judged from the replicas' findings")
    return finish(0 if held else 1)


if __name__ == "__main__":
    sys.exit(main())
