"""The command: a declared review run from the first check to the merged record.

    review_run.py --caller <name> --review <review folder> --out <output folder>
                  [--callers <folder>] [--bound N] [--replicas N] [--model <full model id>]
                  [--rerun <unit>]... [--format text|json]

The caller is a module `review_caller_<name>` in the callers folder (this tool's folder unless `--callers` says
otherwise); it supplies the review's declaration, the checks of the merged tables and the files to render. The command
admits the declaration's artefacts against the review folder, builds the one shared context every session continues
from, plans one fork for each group of units and replica, starts the shared context and then the forks together, repairs
what the scheduler repairs, merges the replicas with no model, writes the caller's rendered files into the output
folder, and prints a report. A review whose replicas run on more than one model starts a shared context of its own for
each model, since the cache cannot be shared across models.

The agent command line is started from the program named by the environment variable REVIEW_KIT_AGENT (claude when it
is unset), which must be on the search path and logged in. The output folder holds the plan, the record, the saved
stream of every session and the rendered files; `--rerun` runs the named units again against a record already there.

Each cause is reported on one line beginning REFUSED or CANNOT RUN that names the cause and what to do, a RESULT line
comes last, and the exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and
2 when the agent command line is missing or not logged in. `--format json` prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from . import caller as caller_module
from . import catalogue as cat
from . import costmodel as cm
from . import decl, ensemble, merge, messages, planner, scheduler, store, streams, telemetry
from . import executor as ex

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(TOOLS_DIR))
STREAMS_FOLDER = "streams"
FORMATS = ("text", "json")
#: The statuses the result line takes and the exit status each gives.
WRITTEN, REFUSED, CANNOT_RUN = "WRITTEN", "REFUSED", "CANNOT RUN"
EXIT_STATUS = {WRITTEN: 0, REFUSED: 1, CANNOT_RUN: 2}
#: The optional caller attribute holding the replica policy as plain data (variants and replicas by stakes).
POLICY_ATTRIBUTE = "replica_policy"

#: Every cause the command reports on a line beginning REFUSED or CANNOT RUN, by code: a phrase the line says the cause
#: in and a phrase it says what to do in. The hardware notes give each cause and action in these words, and the tests
#: hold each line, in its own scenario, to them.
CAUSES: Dict[str, Tuple[str, str]] = {
    "usage": ("the command line cannot be used", "run with --help for the options"),
    "review-missing": ("does not exist", "give the folder the review's starter wrote"),
    "review-in-repository": ("could read the design as committed", "give a review folder outside it"),
    "output-is-file": ("is a file", "give a new or empty folder"),
    "output-in-repository": ("is inside the repository", "give a folder outside it"),
    "output-in-review": ("is inside the review folder", "give a folder apart from it"),
    "output-contains-review": ("contains the review folder", "give a folder apart from it"),
    "number-not-whole": ("is not a whole number", "give a whole number of 1 or more"),
    "number-below-one": ("is below 1", "give a whole number of 1 or more"),
    "format": ("is none of", "give text or json"),
    "model-empty": ("the model is empty", "give a full model id"),
    "caller-missing": ("there is no caller module", "give the name of a review_caller_<name> module"),
    "caller-unloadable": ("cannot be loaded", "fix the module"),
    "caller-attribute": ("lacks the attribute", "add it to the module"),
    "declaration-refused": ("declaration is refused", "fix the declaration the caller supplies"),
    "replica-policy": (POLICY_ATTRIBUTE, "fix the caller's replica_policy"),
    "artefact-refused": ("refused by the rule", "change the declaration's artefact or the review folder"),
    "over-budget": ("over the review's context budget", "take artefacts out of the units' `needs`, or raise the budget's context_tokens"),
    "over-stream-limit": ("over the agent command line's stream limit", "write fewer or smaller views"),
    "output-has-record": ("already holds a record", "use a new output folder, or name the units to run again"),
    "no-record": ("so there is no run to run units of again", "start a fresh run"),
    "record-unreadable": ("cannot be read", "start a fresh run in a new output folder"),
    "output-in-use": ("is in use by another run", "wait for it to end, or remove"),
    "unit-unknown": ("is not a unit of this review", "name units from that list"),
    "unit-left-out": ("failed on its last run and is not named", "name it too"),
    "review-changed": ("differs from the recorded", "run the whole review again in a new output folder"),
    "plan-changed": ("now gives different", "run the whole review again in a new output folder"),
    "unit-failed": ("failed:", "with --rerun to run them again"),
    "rendered-name": ("no earlier merge wrote under that name", "name another file, or move that one away"),
    "merge-refused": ("the merge or the rendering was refused", "fix what the REFUSED lines name, then run one unit again with --rerun to merge again"),
    "root-failed": ("the shared context session", "check the agent command line runs, then run again"),
    "start-report": ("shows what the specification excludes", "check the agent command line's version and settings, then run again"),
    "output-unwritable": ("could not be written", "give a folder this user can write"),
    "agent-missing": ("is not on the search path", "install it, or name the program in the environment variable REVIEW_KIT_AGENT"),
    "agent-not-logged-in": ("is not logged in", "log it in, then run again"),
    "agent-not-started": ("could not be started", "check it is installed and runs, then run again"),
}


class UsageError(Exception):
    """The command line cannot be read; the text says what to give."""


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise UsageError(message)


class Refusal(Exception):
    """The command refuses before any session is started; each cause names what is wrong and what to do."""

    def __init__(self, causes: Sequence[str]):
        super().__init__("; ".join(causes))
        self.causes = list(causes)


# --- The folders -------------------------------------------------------------------------------


def inside(path: str, folder: str) -> bool:
    return cat.inside(os.path.realpath(path), os.path.realpath(folder))


def folder_refusals(review: str, out: str, repo: str) -> List[str]:
    """Why the review folder or the output folder cannot be used where they are asked to go."""
    found = []
    if not os.path.isdir(review):
        found.append(f"the review folder {review} does not exist; give the folder the review's starter wrote")
    elif inside(review, repo):
        found.append(f"the review folder {review} is inside the repository; a reviewer working there could read the design "
                     "as committed and the earlier rounds' verdicts, so give a review folder outside it")
    if os.path.isfile(out):
        found.append(f"the output folder {out} is a file; give a new or empty folder")
    if inside(out, repo):
        found.append(f"the output folder {out} is inside the repository; give a folder outside it")
    if os.path.isdir(review):
        if inside(out, review):
            found.append(f"the output folder {out} is inside the review folder, where a reviewer could read another unit's "
                         "verdicts; give a folder apart from it")
        elif inside(review, out):
            found.append(f"the output folder {out} contains the review folder, so a reviewer could read another unit's "
                         "verdicts; give a folder apart from it")
    return found


def process_alive(pid: int) -> bool:
    """Whether a process with this identifier exists on this machine."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def lock_pid(path: str) -> Optional[int]:
    try:
        with open(path, encoding="utf-8") as handle:
            pid = json.load(handle)["pid"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return pid if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 else None


def take_over_stale_lock(out: str, alive: Callable[[int], bool] = process_alive) -> Optional[str]:
    """Takes over the lock a run killed before it could release it left in the output folder. The lock records the identifier
    of the process that holds it; a lock whose process no longer exists is removed, and the note says so. A lock whose
    process exists, or that records none, is left as it is, so the run is refused as in use."""
    path = os.path.join(out, store.LOCK_NAME)
    if not os.path.lexists(path):
        return None
    pid = lock_pid(path)
    if pid is None or alive(pid):
        return None
    moved = f"{path}.stale-{os.getpid()}"
    try:
        os.rename(path, moved)
    except OSError:
        return None
    if lock_pid(moved) != pid:  # another run took the lock over and made its own between the look and the move
        try:
            os.link(moved, path)
        except OSError:
            pass
        os.unlink(moved)
        return None
    os.unlink(moved)
    return f"took over {path}, a lock left by process {pid}, which no longer exists"


# --- The command line --------------------------------------------------------------------------


def parser() -> Parser:
    found = Parser(prog="review_run.py", description=__doc__.split("\n\n")[0])
    found.add_argument("--caller", required=True, help="the caller's name: the module review_caller_<name>")
    found.add_argument("--callers", default=TOOLS_DIR, help="the folder to look for caller modules in (default: the tools folder)")
    found.add_argument("--review", required=True, help="the review folder the sessions read, outside the repository")
    found.add_argument("--out", required=True, help="the output folder, apart from the review folder and outside the repository")
    found.add_argument("--bound", default=None, help="the most sessions at once (default: the caller's bound, else one for every fork the plan has)")
    found.add_argument("--replicas", default=None, help="the number of replicas of every unit, in place of the declared stakes' number")
    found.add_argument("--model", default=None, help="the full model id every session uses (default: the agent command line's own)")
    found.add_argument("--rerun", action="append", default=[], help="a unit to run again, with the others' results kept; repeat for each")
    found.add_argument("--format", default="text", help="the report as text or json (default: text)")
    return found


def whole_number(text: Optional[str], what: str, causes: List[str]) -> Optional[int]:
    """The whole number a flag was given as, or None; a cause is added for one that is not a number or is below one."""
    if text is None:
        return None
    try:
        value = int(text)
    except ValueError:
        causes.append(f"{what} {text!r} is not a whole number; give a whole number of 1 or more")
        return None
    if value < 1:
        causes.append(f"{what} {value} is below 1; give a whole number of 1 or more")
        return None
    return value


# --- The report --------------------------------------------------------------------------------


def new_report(caller_name: str, review: str, out: str) -> Dict[str, Any]:
    return {"result": REFUSED, "detail": "nothing was run", "caller": caller_name, "review": review, "out": out,
            "refusals": [], "cannot_run": None, "notes": [], "agent": None, "plan": None, "sessions": [], "run": None,
            "checks_failed": [], "units": {}, "same_place": [], "tables": {}, "rendered": [], "not_this_merge": [],
            "files": [], "reran": []}


def figure_text(figure: Mapping[str, Any], wall: Optional[float] = None) -> str:
    tokens = figure["tokens"]
    return (f"{figure['api_ms']} ms API | {figure['wall_s'] if wall is None else wall} s | {figure['turns']} turns | {figure['calls']} calls | "
            f"${figure['cost_usd']} | read {tokens['cache_read']} wrote {tokens['cache_write']} fresh {tokens['fresh']} "
            f"generated {tokens['generated']}")


def render_text(report: Mapping[str, Any]) -> List[str]:
    """The report as lines; every fact the JSON holds is in one of them."""
    clean = ex.clean
    lines = [f"RUN | {clean(report['caller'])} | {clean(report['review'])} | {clean(report['out'])}"]
    lines += [f"NOTE | {clean(note)}" for note in report["notes"]]
    lines += [f"REFUSED | {clean(why)}" for why in report["refusals"]]
    if report["cannot_run"]:
        lines.append(f"CANNOT RUN | {clean(report['cannot_run'])}")
    if report["agent"]:
        lines.append(f"AGENT | {clean(report['agent']['program'])} | version {clean(report['agent']['version'])}")
    plan = report["plan"]
    if plan:
        lines.append(f"PLAN | {len(plan['groups'])} groups | {plan['forks']} forks | bound {plan['bound']} | shared context "
                     f"{plan['shared_tokens']} tokens | prefix {plan['prefix_sha']} | specification {plan['spec_digest']} | "
                     f"tool commit {clean(plan['tool_commit'])} | tree saving ${plan['tree']['saving_usd']} against "
                     f"${plan['tree']['threshold_usd']}, kept {plan['tree']['kept']} | variants {', '.join(plan['variants'])}")
        for group in plan["groups"]:
            lines.append(f"GROUP | {group['id']} | units {', '.join(group['units'])} | {group['replicas']} replicas | "
                         f"expected output {group['expected_output_tokens']} tokens | needs {', '.join(group['needs'])}")
        for context in plan["contexts"]:
            lines.append(f"CONTEXT | {context['root_id']} | model {clean(context['model'])} | specification "
                         f"{context['spec_digest']} | variants {', '.join(context['variants'])}")
        predicted = plan["predicted"]
        lines.append(f"PREDICTED | ${predicted['cost_usd']} | {predicted['wall_s']} s")
    for session in report["sessions"]:
        flags = "; ".join(session["flags"]) or "no flag"
        lines.append(f"SESSION | {session['label']} | {session['role']} | {session['kind']} | parent {session['parent'] or 'none'} | "
                     f"{figure_text(session)} | first call read {session['first_call_read']} | {clean(flags)}")
    run = report["run"]
    if run:
        lines.append(f"TOTAL | {run['sessions']} sessions | {figure_text(run, run['critical_path_s'])} | sharing ratio {run['sharing_ratio']} | "
                     f"duplicate writes {run['duplicate_write_tokens']} | critical path {run['critical_path_s']} s")
        if run["predicted"]:
            lines.append(f"AGAINST PREDICTED | cost ${run['actual']['cost_usd']} of ${run['predicted']['cost_usd']} "
                         f"(deviation {run['predicted']['cost_deviation']}) | time {run['actual']['wall_s']} s of "
                         f"{run['predicted']['wall_s']} s (deviation {run['predicted']['wall_deviation']})")
    lines += [f"CHECK FAILED | {clean(check)}" for check in report["checks_failed"]]
    for unit, state in report["units"].items():
        lines.append(f"UNIT | {unit} | group {state['group']} | {'failed' if state['failed'] else 'judged'}")
    for rerun in report["reran"]:
        lines.append(f"RERUN | {', '.join(rerun['units'])} | {rerun['at']} | new shared context {'yes' if rerun['new_shared_context'] else 'no'}")
    for place in report["same_place"]:
        lines.append(f"SAME PLACE | {clean(place['key'])} | findings {', '.join(str(n) for n in place['findings'])} | "
                     f"units {', '.join(place['units'])}")
    for name in report["rendered"]:
        lines.append(f"RENDERED | {clean(name)}")
    for name in report["not_this_merge"]:
        lines.append(f"NOT THIS MERGE | {clean(name)} | written by an earlier merge, not by this one")
    lines += [f"FILE | {clean(name)}" for name in report["files"]]
    for name, table in report["tables"].items():
        lines.append(f"TABLE | {clean(name)} | columns {clean(', '.join(table['columns']))} | {len(table['rows'])} rows")
        for row, by in zip(table["rows"], table["raised_by"]):
            lines.append(f"ROW | {clean(name)} | " + " | ".join(f"{clean(column)} {clean(row[column])}" for column in table["columns"])
                         + f" | raised by {', '.join(by)}")
    lines.append(f"RESULT | {report['result']} | {clean(report['detail'])}")
    return lines


def finish(report: Dict[str, Any], as_json: bool, out_stream, err_stream) -> int:
    if as_json:
        json.dump(report, out_stream, indent=1, ensure_ascii=False)
        out_stream.write("\n")
    else:
        for line in render_text(report):
            print(line, file=err_stream if line.startswith("CANNOT RUN") else out_stream)
    return EXIT_STATUS[report["result"]]


def plan_summary(plan: planner.Plan, shared: messages.SharedContext, bound: int) -> Dict[str, Any]:
    return {"groups": [group.as_dict() for group in plan.groups], "forks": len(plan.lanes), "bound": bound,
            "shared_tokens": shared.tokens, "prefix_sha": shared.prefix_sha, "spec_digest": plan.spec_digest,
            "variants": list(plan.variants), "contexts": [dict(context) for context in plan.contexts],
            "predicted": {key: plan.predicted[key] for key in ("cost_usd", "wall_s")}, "tree": plan.tree,
            "cli_version": plan.cli_version, "tool_commit": plan.tool_commit}


# --- Figures from the saved streams -------------------------------------------------------------


def saved_names(folder: str) -> Set[str]:
    return {name for name in os.listdir(folder) if name.endswith(ex.META_SUFFIX)} if os.path.isdir(folder) else set()


def figures_of_run(folder: str, before: Set[str]) -> Tuple[List[telemetry.SessionFigures], List[str]]:
    """The figures of the sessions saved since `before`, each named by its node, and the sessions whose figures cannot be
    told. A session's own cost and time are its reported figures less those of the session it continues."""
    found: List[telemetry.SessionFigures] = []
    problems: List[str] = []
    streams_by_label: Dict[str, streams.Stream] = {}
    owner: Dict[str, str] = {}
    for name in sorted(saved_names(folder) - before):
        with open(os.path.join(folder, name), encoding="utf-8") as handle:
            meta = json.load(handle)
        label = meta.get("label") or name
        with open(os.path.join(folder, name[:-len(ex.META_SUFFIX)] + ex.STREAM_SUFFIX), encoding="utf-8", newline="") as handle:
            stream = streams.read_stream(handle.read())
        parent_label = owner.get(meta.get("parent") or "")
        try:
            figure = telemetry.session_figures(stream, streams_by_label.get(parent_label) if parent_label else None)
        except telemetry.FigureError as error:
            problems.append(f"the figures of session {label} cannot be told: {error}")
            continue
        finally:
            streams_by_label[label] = stream
            if stream.session_id:
                owner[stream.session_id] = label
        found.append(dataclasses.replace(figure, session=label, parent=parent_label))
    return found, problems


def predicted_for(plan: planner.Plan, groups: Optional[Set[str]]) -> telemetry.Prediction:
    """What the plan predicted for the sessions of this run: all of them, or the roots and the forks of the groups run."""
    per_node = plan.predicted["per_node"]
    nodes = [node for node in plan.nodes if node.role == planner.ROOT or groups is None or node.group in groups]
    lanes = [node for node in nodes if node.role == planner.UNIT]
    roots = [node for node in nodes if node.role == planner.ROOT]
    cost = sum(per_node[node.id]["cost_usd"] for node in nodes)
    wall = max(per_node[node.id]["wall_s"] for node in roots) + cm.makespan([per_node[node.id]["wall_s"] for node in lanes], plan.bound)
    return telemetry.Prediction(round(cost, 6), round(wall, 3))


# --- The run -----------------------------------------------------------------------------------


def agent_version(program: str) -> str:
    try:
        done = subprocess.run([program, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    first = (done.stdout.strip().splitlines() or [""])[0].strip()
    return first if done.returncode == 0 and first else "unknown"


def tool_commit(repo: str) -> str:
    try:
        done = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else "unknown"


def replica_policy(prepared: caller_module.Prepared) -> ensemble.Policy:
    given = getattr(prepared.caller.module, POLICY_ATTRIBUTE, None)
    try:
        return ensemble.parse_policy(given, f"the caller {prepared.caller.name}'s {POLICY_ATTRIBUTE}")
    except ensemble.PolicyError as error:
        raise Refusal([f"{error}; fix the caller's replica_policy"])


def used_variants(policy: ensemble.Policy, counts: Sequence[int]) -> List[str]:
    """The variants some replica of some group takes, in the policy's order."""
    ids = policy.ids
    used = {ids[index % len(ids)] for count in counts for index in range(count)}
    return [variant for variant in ids if variant in used]


class Run:
    """One invocation: what it settled before any session started, and what it does with the run's record."""

    def __init__(self, args: argparse.Namespace, review: str, out: str, repo: str):
        self.args, self.review, self.out, self.repo = args, review, out, repo
        self.report = new_report(args.caller, review, out)
        self.streams_folder = os.path.join(out, STREAMS_FOLDER)

    # Everything that is settled before an agent is started ---------------------------------------

    def settle(self, environ: Mapping[str, str]) -> None:
        causes = folder_refusals(self.review, self.out, self.repo)
        bound = whole_number(self.args.bound, "the bound", causes)
        flag = whole_number(self.args.replicas, "the replicas flag", causes)
        if self.args.format not in FORMATS:
            causes.append(f"the report format {self.args.format!r} is none of {list(FORMATS)}; give text or json")
        if self.args.model is not None and not self.args.model.strip():
            causes.append("the model is empty; give a full model id, or leave --model out")
        try:
            loaded = caller_module.load(self.args.caller, os.path.abspath(self.args.callers))
            self.prepared = loaded.prepare(self.review)
        except merge.Refused as error:
            causes += [cause + ("; fix the declaration the caller supplies" if "declaration is refused" in cause else "")
                       for cause in error.causes]
        if causes:
            raise Refusal(causes)
        self.policy = replica_policy(self.prepared)
        declaration = self.prepared.declaration
        try:
            self.counts = ensemble.replicas_by_unit(declaration, self.policy, flag)
            self.groups = planner.pack(declaration)
            self.group_counts = planner.replica_counts(declaration, self.groups, self.counts)
        except (ensemble.PolicyError, ValueError) as error:
            raise Refusal([f"{error}; give a whole number of 1 or more"])
        forks = max(1, sum(self.group_counts))
        declared = getattr(loaded.module, "bound", None)
        self.bound = bound if bound is not None else forks if declared is None else min(declared, forks)
        try:
            self.catalogue = cat.admit(declaration, self.review, results_folder=self.out)
        except cat.Refused as error:
            raise Refusal([refusal.line() + "; change the declaration's artefact or the review folder, then run again"
                           for refusal in error.refusals])
        self.shared = messages.shared_context(self.catalogue)
        budget = declaration.budget.context_tokens
        if budget is not None and self.shared.tokens > budget:
            raise Refusal([str(planner.OverBudget(self.shared.tokens, budget))])
        try:
            planner.check_stream(self.catalogue, self.shared)
        except planner.OverStreamLimit as error:
            raise Refusal([str(error)])
        self.spec = messages.make_spec(declaration, self.prepared.tools, self.review, self.args.model)
        self.names = list(dict.fromkeys(self.args.rerun))
        self.check_output_folder()

    def check_output_folder(self) -> None:
        try:
            if self.names:
                store.read_record(self.out)
            else:
                store.check_fresh(self.out)
        except store.StoreRefusal as error:
            raise Refusal([str(error)])
        note = take_over_stale_lock(self.out)
        if note:
            self.report["notes"].append(note)
        lock = os.path.join(self.out, store.LOCK_NAME)
        if os.path.lexists(lock):
            raise Refusal([f"the output folder {self.out} is in use by another run ({store.LOCK_NAME} is held by a running "
                           f"process, or records none); wait for it to end, or remove {lock} if no run is in the folder"])

    def build_plan(self, program: str) -> None:
        self.program, self.version = program, agent_version(program)
        found = ensemble.contexts(self.spec, self.shared, self.policy, used_variants(self.policy, self.group_counts))
        self.contexts = found if len(found) > 1 else None
        declaration = self.prepared.declaration
        try:
            self.plan = planner.make_plan(declaration, self.catalogue, self.shared, self.spec, bound=self.bound,
                                          cli_version=self.version, tool_commit=tool_commit(self.repo), replicas=self.counts,
                                          variants=self.policy.ids, contexts=found if len(found) > 1 else (),
                                          prompt_for=ensemble.prompt_for(declaration, self.policy, self.prepared.unit_text))
        except (planner.OverBudget, planner.OverStreamLimit, planner.BoundBelowOne, ValueError) as error:
            raise Refusal([str(error)])
        self.report["agent"] = {"program": program, "version": self.version}
        self.report["notes"] += [cm.unpriced_text(model) for model in
                                 cm.unpriced([self.args.model] + [context.model for context in found[1:]])]
        self.report["plan"] = plan_summary(self.plan, self.shared, self.bound)

    # The record after the sessions, before it is written ------------------------------------------

    def finish_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Called under the lock with the run's record: the figures, the merge, and the rendered files."""
        report = self.report
        prior = store.read_record(self.out) if store.holds_record(self.out) else None
        figures, problems = figures_of_run(self.streams_folder, self.before)
        groups = {self.plan.group_of(name).id for name in self.names if name in self.plan.units} if self.names else None
        run = telemetry.run_figures(figures, predicted_for(self.plan, groups)) if figures else None
        by_label = {node["id"]: node for node in record["nodes"]}
        report["sessions"] = [dict(figure.as_dict(), label=figure.session, role=by_label.get(figure.session, {}).get("role", ""),
                                   kind=by_label.get(figure.session, {}).get("kind", ""),
                                   flags=list(by_label.get(figure.session, {}).get("flags", [])))
                              for figure in figures]
        report["run"] = run.as_dict() if run else None
        checks = list(problems)
        checks += [f"{node['id']}: {flag}" for node in record["nodes"] if node["id"] in {f.session for f in figures}
                   for flag in node.get("flags", [])]
        report["units"] = record["units"]
        report["reran"] = [entry for entry in record["runs"] if entry["kind"] == "rerun"]
        failed = [lane for lane in record["lanes"] if lane["failure"] is not None]
        for lane in failed:
            failure = lane["failure"]
            checks.append(f"group {failure['group']} replica {failure['replica']} (units {', '.join(failure['units'])}) still "
                          f"holds a problem on its last attempt: {'; '.join(failure['problems'])}")
        report["checks_failed"] = checks
        record["figures"] = {"sessions": report["sessions"], "run": report["run"]}
        record["rendered"] = list(prior.get("rendered", [])) if prior else []
        record["not_this_merge"] = list(prior.get("not_this_merge", [])) if prior else []
        if failed:
            report["refusals"] += [f"unit {', '.join(lane['failure']['units'])} (group {lane['failure']['group']}, replica "
                                   f"{lane['failure']['replica']}) failed: {'; '.join(lane['failure']['problems'])}; name its "
                                   "units with --rerun to run them again" for lane in failed]
            report["detail"] = f"{len(failed)} of {len(record['lanes'])} replicas failed; the record is kept in {self.out}"
            record["merged"] = None
            return record
        units: Dict[str, Dict[str, Any]] = {}
        for lane in record["lanes"]:
            attempt = lane["record"]["attempts"][lane["record"]["standing"]]
            units.setdefault(lane["group"], {})[f"r{lane['replica']}"] = attempt["tables"]
        try:
            merged = self.prepared.merge([group.id for group in self.plan.groups], units)
            files = self.prepared.render(merge.plain_tables(merged))
            written = caller_module.write_rendered(self.prepared.caller.name, self.out, files, caller_module.earlier_names(prior))
        except merge.Refused as error:
            report["refusals"] += error.causes
            report["detail"] = (f"the merge or the rendering was refused; the units' results are kept in {self.out}; fix what the "
                                "REFUSED lines name, then run one unit again with --rerun to merge again")
            record["merged"] = None
            return record
        record["merged"] = merged
        record.update(written)
        report["rendered"], report["not_this_merge"] = written["rendered"], written["not_this_merge"]
        report["same_place"] = merged["same_place"]
        report["tables"] = merge.plain_tables(merged)
        report["checks_failed"] += [f"{len(merged['same_place'])} places hold more than one finding, and neither is dropped"] \
            if merged["same_place"] else []
        report["result"], report["detail"] = WRITTEN, f"the merged record is written to {os.path.join(self.out, store.RECORD_NAME)}"
        return record

    def execute(self, environ: Mapping[str, str]) -> None:
        clock = ex.SystemClock()
        executor = ex.ClaudeCliExecutor(program=self.program, environ=dict(environ), clock=clock, out=self.streams_folder)
        rules = self.prepared.rules
        runner = scheduler.Scheduler(executor, clock, cannot_judge=rules.cannot_judge, fail=rules.fail,
                                     retrieval=caller_module.RETRIEVAL_TOOL in self.prepared.tools)
        self.before = saved_names(self.streams_folder)
        prompt_for = ensemble.prompt_for(self.prepared.declaration, self.policy, self.prepared.unit_text)
        common = dict(prompt_for=prompt_for, round_label=self.prepared.rules.round_label, contexts=self.contexts,
                      finish=self.finish_record)
        if self.names:
            scheduler.rerun_review(runner, self.prepared.declaration, self.plan, self.shared, self.spec, self.out, self.review,
                                   self.names, **common)
        else:
            scheduler.run_review(runner, self.prepared.declaration, self.plan, self.shared, self.spec, self.out, self.review,
                                 **common)
        self.report["files"] = [store.PLAN_NAME, store.RECORD_NAME, STREAMS_FOLDER + "/"] + list(self.report["rendered"])


def main(argv: Optional[Sequence[str]] = None, out=sys.stdout, err=sys.stderr, environ: Optional[Mapping[str, str]] = None,
         repo: str = REPO) -> int:
    environ = environ if environ is not None else os.environ
    try:
        args = parser().parse_args(argv)
    except UsageError as error:
        print(f"REFUSED | the command line cannot be used ({ex.clean(error)}); run with --help for the options", file=out)
        return EXIT_STATUS[REFUSED]
    as_json = args.format == "json"
    review, folder = os.path.abspath(args.review), os.path.abspath(args.out)
    run = Run(args, review, folder, repo)
    report = run.report

    def refused(causes: Sequence[str], detail: str = "nothing was run") -> int:
        report["refusals"] += list(causes)
        report["result"], report["detail"] = REFUSED, detail
        return finish(report, as_json, out, err)

    try:
        run.settle(environ)
        try:
            program = ex.require_agent(environ)
        except ex.CannotRun as error:
            report["result"], report["cannot_run"], report["detail"] = CANNOT_RUN, str(error), "nothing was run"
            return finish(report, as_json, out, err)
        run.build_plan(program)
    except Refusal as error:
        return refused(error.causes)
    try:
        run.execute(environ)
    except ex.CannotRun as error:
        report["result"], report["cannot_run"] = CANNOT_RUN, str(error)
        report["detail"] = f"the run stopped before its record was written; the streams saved so far are in {run.streams_folder}"
    except store.StoreRefusal as error:
        return refused([str(error)])
    except scheduler.RootFailed as error:
        return refused([str(error)], "no fork was started")
    except ex.StartReportFailed as error:
        return refused([f"the start report of session {error.label} shows what the specification excludes: {error}; "
                        "check the agent command line's version and settings, then run again"], "no fork was started")
    except OSError as error:
        return refused([f"the output folder {folder} could not be written ({error}); give a folder this user can write, "
                        "then run again"], "the run stopped")
    return finish(report, as_json, out, err)
