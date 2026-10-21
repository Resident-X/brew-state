"""The scheduler: a plan run through an executor, the repairs it appends, and the rerun of named units.

The shared context is started once, before any fork, and its answer is checked
to be a shared-context node. The forks then run together, at most the stated
number at once. The plan grows as results come back:

- a fatal result (no object, a violation that cannot be mapped, an error exit, an
  empty answer) appends a fresh fork of the same parent as the next attempt;
- a local problem appends a repair turn in that unit's own session;
- a call refused for a rate limit waits on the clock and is retried by the
  executor, the same call each time; a refusal that outlasts the retries counts as
  an error.

A group gets a stated number of attempts, repair turns included. A group that still
holds a problem on its last attempt is reported, naming its units and what it
returned, and the other groups' results are kept. Every attempt is kept, and the
one that stands is chosen by `results.standing`.

The unit of work is the group: its fork answers for every unit it holds, and its
answer is read against the union of their items. A rerun of named units therefore
runs the groups that hold them.

The clock and the way sessions run together are injected, so a test sleeps nowhere
and chooses the order the sessions finish in.
"""

from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from . import decl, messages, planner, results, store, streamcheck, streams
from . import executor as ex
from . import session as sess

#: How many calls one group may take, repair turns included, unless the caller states otherwise.
DEFAULT_ATTEMPTS = 3


class RootFailed(Exception):
    """The shared context could not be started, so no fork can be made; the text says what the session returned."""


# --- Running sessions together -----------------------------------------------------------------


class ThreadedConcurrency:
    """Runs tasks on threads, at most `bound` at once. Results come back in the order of the tasks, whichever finishes first;
    an exception in a task is raised after all have ended."""

    def run(self, tasks: Sequence[Callable[[], Any]], bound: int) -> List[Any]:
        if bound < 1:
            raise planner.BoundBelowOne(bound)
        gate = threading.Semaphore(bound)
        found: List[Any] = [None] * len(tasks)
        errors: List[Optional[BaseException]] = [None] * len(tasks)

        def one(index: int) -> None:
            with gate:
                try:
                    found[index] = tasks[index]()
                except BaseException as error:  # reported to the caller after every task has ended
                    errors[index] = error

        threads = [threading.Thread(target=one, args=(index,)) for index in range(len(tasks))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for error in errors:
            if error is not None:
                raise error
        return found


class SerialConcurrency:
    """Runs tasks one after another in the order `order` gives (indexes), or the tasks' own; for a test that fixes the order."""

    def __init__(self, order: Optional[Callable[[int], Sequence[int]]] = None):
        self.order = order

    def run(self, tasks: Sequence[Callable[[], Any]], bound: int) -> List[Any]:
        if bound < 1:
            raise planner.BoundBelowOne(bound)
        found: List[Any] = [None] * len(tasks)
        for index in (self.order(len(tasks)) if self.order else range(len(tasks))):
            found[index] = tasks[index]()
        return found


# --- Results -----------------------------------------------------------------------------------


@dataclass
class LaneResult:
    """One group and replica: its nodes, every attempt's assessment, and, when the attempt that stands still has a problem,
    what is reported."""

    group: str
    replica: int
    units: Tuple[str, ...]
    nodes: List[Dict[str, Any]]
    unit_record: results.UnitRecord
    failure: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"group": self.group, "replica": self.replica, "units": list(self.units),
                "record": self.unit_record.as_dict(), "failure": self.failure}


@dataclass
class RunResult:
    root: Dict[str, Any]
    lanes: List[LaneResult]
    new_shared_context: bool

    @property
    def failures(self) -> List[Dict[str, Any]]:
        return [lane.failure for lane in self.lanes if lane.failure is not None]


def clip(text: str, width: int = 300) -> str:
    one = " ".join(text.split())
    return one if len(one) <= width else one[:width] + "..."


def stamp(seconds: float) -> str:
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def failed_assessment(kind: str, said: str, label: str) -> results.Assessment:
    return results.Assessment(results.NONE, said, None,
                              problems=[results.Problem(results.FATAL, f"unit {label}", f"the session ended as {kind}: {said}")])


class Scheduler:
    def __init__(self, executor: ex.Executor, clock, concurrency=None, attempts: int = DEFAULT_ATTEMPTS):
        if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
            raise ValueError(f"a unit gets {attempts!r} attempts; it must be a whole number of one or more")
        self.executor, self.clock = executor, clock
        self.concurrency = concurrency or ThreadedConcurrency()
        self.attempts = attempts

    # The shared context ----------------------------------------------------------------------

    def start_root(self, spec: sess.SessionSpec, shared: messages.SharedContext, plan: planner.Plan) -> Tuple[Dict[str, Any], str, streams.Stream, bool]:
        call = sess.Call(spec, shared.message, label="root")
        outcome = self.executor.run(call)
        if outcome.kind != ex.OK:
            raise RootFailed(f"the shared context session ended as {outcome.kind}: {outcome.said()}; check the agent command "
                             "line runs, then run again")
        stream = streams.read_stream(outcome.stream)
        first = outcome.session.calls[0] if outcome.session.calls else {"cache_read": 0, "cache_write": 0}
        node = {"id": plan.root.id, "role": planner.ROOT, "parent": None, "group": None, "replica": None, "attempt": 1,
                "variant": None, "units": [], "prefix_sha": shared.prefix_sha, "message_sha": shared.prefix_sha,
                "kind": outcome.kind, "tries": outcome.attempts, "waits": list(outcome.waits),
                "flags": [str(flag) for flag in streamcheck.node_shape(stream, messages.ACK)],
                "first_call": {"cache_read": first["cache_read"], "cache_write": first["cache_write"]},
                "started_at": self.clock.now()}
        return node, outcome.session.id, stream, first["cache_write"] > first["cache_read"]

    # One group and replica -------------------------------------------------------------------

    def lane(self, declaration: decl.Declaration, plan: planner.Plan, spec: sess.SessionSpec, root_id: str,
             root_stream: streams.Stream, first: planner.Node, prompt: str, round_label: Optional[str]) -> LaneResult:
        group = next(g for g in plan.groups if g.id == first.group)
        label = "+".join(group.units)
        items = [item for unit in group.units for item in declaration.units[unit].items]
        record = results.UnitRecord(label)
        lane = LaneResult(group.id, first.replica, group.units, [], record)
        prefix = streams.lineage_written([root_stream])
        parent_id, parent_session, fork, message = plan.root.id, root_id, True, messages.prompt_message(prompt)
        fresh_message = message
        for attempt in range(1, self.attempts + 1):
            node_id = f"{group.id}.r{first.replica}.a{attempt}"
            role = planner.UNIT if fork else planner.REPAIR
            node = {"id": node_id, "role": role, "parent": parent_id, "group": group.id, "replica": first.replica,
                    "attempt": attempt, "variant": first.variant, "units": list(group.units), "prefix_sha": first.prefix_sha,
                    "message_sha": messages.sha256(message)}
            lane.nodes.append(node)
            try:
                outcome = self.executor.run(sess.Call(spec, message, parent=parent_session, fork=fork, label=node_id))
            except ex.StartReportFailed as error:
                node.update(kind="start-report", tries=1, waits=[], flags=[], problems=error.problems)
                record.add(failed_assessment("a start report that shows what the specification excludes", "; ".join(error.problems), label))
                break
            node.update(kind=outcome.kind, tries=outcome.attempts, waits=list(outcome.waits), flags=[])
            if outcome.kind == ex.OK:
                if fork:
                    miss = streamcheck.prefix_miss(streams.read_stream(outcome.stream), prefix)
                    node["flags"] = [str(miss)] if miss else []
                assessed = results.assess(outcome.session.structured, outcome.session.text, declaration.shape, label, items,
                                          round_label)
            else:
                assessed = failed_assessment(outcome.kind, outcome.said(), label)
            record.add(assessed)
            node["problems"] = [problem.line() for problem in assessed.problems]
            if not assessed.problems:
                break
            if assessed.fatal:
                parent_id, parent_session, fork, message = plan.root.id, root_id, True, fresh_message
            else:
                parent_id, parent_session, fork = node_id, outcome.session.id, False
                message = messages.prompt_message(messages.repair_prompt([problem.line() for problem in assessed.local]))
        standing = record.standing
        if standing.problems:
            lane.failure = {"group": group.id, "replica": first.replica, "units": list(group.units),
                            "returned": clip(standing.raw), "problems": [problem.line() for problem in standing.problems]}
        return lane

    # A run -----------------------------------------------------------------------------------

    def run(self, declaration: decl.Declaration, plan: planner.Plan, shared: messages.SharedContext, spec: sess.SessionSpec,
            prompt_for: Optional[Callable[[Sequence[str], str], str]] = None, round_label: Optional[str] = None,
            only: Optional[Set[str]] = None) -> RunResult:
        """Run the plan, or only the groups `only` names. The bound comes from the plan."""
        if plan.bound < 1:
            raise planner.BoundBelowOne(plan.bound)
        prompt_for = prompt_for or planner.default_prompt(declaration)
        root, root_id, root_stream, new = self.start_root(spec, shared, plan)
        firsts = [node for node in plan.lanes if only is None or node.group in only]
        tasks = [(lambda node=node: self.lane(declaration, plan, spec, root_id, root_stream, node,
                                              prompt_for(node.units, node.variant), round_label)) for node in firsts]
        return RunResult(root, self.concurrency.run(tasks, plan.bound), new)


# --- The record --------------------------------------------------------------------------------


def unit_states(lanes: Sequence[LaneResult]) -> Dict[str, Dict[str, Any]]:
    states: Dict[str, Dict[str, Any]] = {}
    for lane in lanes:
        for unit in lane.units:
            state = states.setdefault(unit, {"group": lane.group, "failed": False, "problems": []})
            if lane.failure is not None:
                state["failed"] = True
                state["problems"] += [f"replica {lane.replica}: {line}" for line in lane.failure["problems"]]
    return states


def lane_order(plan: planner.Plan, lanes: Sequence[LaneResult]) -> List[LaneResult]:
    position = {(node.group, node.replica): index for index, node in enumerate(plan.lanes)}
    return sorted(lanes, key=lambda lane: position[(lane.group, lane.replica)])


def build_record(plan: planner.Plan, review_hash: str, run: RunResult, clock, kind: str,
                 names: Sequence[str] = (), earlier: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The run record: the plan, every node with its figures, each lane's attempts, each unit's state, and the runs made.
    Given the earlier record and the rerun's results, the rerun's lanes replace those of the groups it ran."""
    lanes = lane_order(plan, run.lanes)
    ran = {(lane.group, lane.replica) for lane in lanes}
    kept_lanes = [lane for lane in (earlier["lanes"] if earlier else []) if (lane["group"], lane["replica"]) not in ran]
    kept_nodes = [node for node in (earlier["nodes"] if earlier else [])
                  if node["role"] != planner.ROOT and (node["group"], node["replica"]) not in ran]
    units = dict(earlier["units"]) if earlier else {}
    units.update(unit_states(lanes))
    all_lanes = sorted(kept_lanes + [lane.as_dict() for lane in lanes],
                       key=lambda lane: (plan.units.index(lane["units"][0]), lane["replica"]))
    all_nodes = sorted(kept_nodes + [node for lane in lanes for node in lane.nodes],
                       key=lambda node: (plan.units.index(node["units"][0]), node["replica"], node["attempt"]))
    runs = list(earlier["runs"]) if earlier else []
    runs.append({"kind": kind, "at": stamp(run.root["started_at"]), "units": list(names) if names else plan.units,
                 "new_shared_context": run.new_shared_context})
    return {"version": store.RECORD_VERSION, "review_hash": review_hash, "plan": plan.to_dict(),
            "shared_context": {"prefix_sha": plan.shared["prefix_sha"], "tokens": plan.shared["tokens"],
                               "started_at": run.root["started_at"], "new": run.new_shared_context},
            "nodes": [run.root] + all_nodes, "lanes": all_lanes, "units": {u: units[u] for u in plan.units},
            "runs": runs}


def run_review(scheduler: Scheduler, declaration: decl.Declaration, plan: planner.Plan, shared: messages.SharedContext,
               spec: sess.SessionSpec, out: str, review_folder: str, prompt_for=None,
               round_label: Optional[str] = None) -> Dict[str, Any]:
    """A fresh run: refused when the output folder already holds a record, holding the folder's lock while it is in it, and
    ending with the record written."""
    with store.RunLock(out, scheduler.clock.now()):
        store.check_fresh(out)
        store.write_plan(out, plan.to_dict())
        run = scheduler.run(declaration, plan, shared, spec, prompt_for, round_label)
        record = build_record(plan, store.folder_hash(review_folder), run, scheduler.clock, "fresh")
        store.write_record(out, record)
        return record


def rerun_review(scheduler: Scheduler, declaration: decl.Declaration, plan: planner.Plan, shared: messages.SharedContext,
                 spec: sess.SessionSpec, out: str, review_folder: str, names: Sequence[str], prompt_for=None,
                 round_label: Optional[str] = None) -> Dict[str, Any]:
    """Run the named units again along the recorded path: the shared context's identical bytes, then a fork for each replica
    of each group that holds a named unit. The named units' results replace the recorded ones, and the record says which units
    were run again, when, and whether the shared context had to be written anew."""
    with store.RunLock(out, scheduler.clock.now()):
        record = store.read_record(out)
        review_hash = store.folder_hash(review_folder)
        known = {unit for group in plan.groups for unit in group.units}
        groups = {plan.group_of(name).id for name in names if name in known}
        running = [unit for group in plan.groups if group.id in groups for unit in group.units]
        store.check_rerun(record, review_hash, list(names), running)
        store.check_same_path(record, plan)
        run = scheduler.run(declaration, plan, shared, spec, prompt_for, round_label, only=groups)
        record = build_record(plan, review_hash, run, scheduler.clock, "rerun", list(names), record)
        store.write_record(out, record)
        return record
