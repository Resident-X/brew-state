"""The proof harness: a fanned-out review judged against recorded single-reviewer runs by one pooled criterion.

The forms of a review are plans of the one engine, so the comparison is fair:

- `single` is one unit holding every item, with no shared context (the reviewer finds
  the artefacts itself);
- `single-shared` is the same unit continuing a shared context that holds every artefact;
- `fanned` is the declared review as the planner groups it.

A run of any form is recorded in one shape, the `RunOutcome`. Recorded single-reviewer
runs are baselines in a `BaselineStore`, each keyed by the hash of the seed list, the
design commit, the model, the form and the hash of the prompt. The seeded copy's commit
and the tool commit are recorded with a run and are not part of the key, since the
recorded layout runs were made at five tool commits. A form whose baseline for the key is
recorded is not run again, and a form whose key differs is.

`accept` applies the pooled criterion to the recorded single runs and at least one
fanned-out run, and `build_record` gives the record of the proof. Which finding names
which seed is the caller's: the proof is given the function that decides it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import catalogue as cat
from . import decl, merge, messages, planner, scheduler, store, telemetry
from . import session as sess

SINGLE, SINGLE_SHARED, FANNED = "single", "single-shared", "fanned"
FORMS = (SINGLE, SINGLE_SHARED, FANNED)
#: The forms whose recorded runs are baselines: a proof loads them and does not run them again.
BASELINE_FORMS = (SINGLE, SINGLE_SHARED)

#: The clauses of the pooled criterion, as a failure names them.
SEEDS_FLOOR, SEED_EVERY_SINGLE_FOUND, WALL_TIME, COST = "seeds-floor", "seed-every-single-found", "wall-time", "cost"
#: How close to a bound a passing run is for a second run to be required, as a fraction of the bound.
NEAR = 0.10
#: The fraction of the single mean wall time the fanned-out form may take.
WALL_FRACTION = 0.5
BASELINES_VERSION = 1
SINGLE_LABEL = "single"

Seed = Mapping[str, Any]
#: Whether a finding row names a seed: `match(seed, row)`.
Match = Callable[[Seed, Mapping[str, Any]], bool]


class ProofError(Exception):
    """A proof that cannot be made as asked; the text says what is wrong and what to give."""


class UnknownForm(ProofError):
    def __init__(self, form: Any):
        self.form = form
        super().__init__(f"the form is {form!r}; it must be one of {list(FORMS)}")


class BaselineRecorded(ProofError):
    """The form's baseline for this key is recorded, so the form is not run again."""

    def __init__(self, key: str, form: str, runs: int):
        self.key, self.form, self.runs = key, form, runs
        super().__init__(f"the {form} form already has {runs} recorded run{'s' if runs != 1 else ''} under the baseline key "
                         f"{key}; it is not run again. Change the seed list, the design commit, the model or the prompt to "
                         "make a new key, or use the recorded runs")


class BaselineFileError(ProofError):
    def __init__(self, where: str, problem: str):
        self.where, self.problem = where, problem
        super().__init__(f"{where}: {problem}")


class NotEnoughRuns(ProofError):
    pass


# --- Seeds and keys ----------------------------------------------------------------------------


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def seed_list_hash(seeds: Sequence[Seed]) -> str:
    """The hash of the seed list: its canonical JSON, keys in order, no spaces."""
    return digest(list(seeds))


@dataclass(frozen=True)
class BaselineKey:
    """What a baseline is for: the hashes and names a recorded run is matched on. The seeded copy's commit and the tool
    commit are recorded with a run and are not here."""

    seeds: str
    design: str
    model: str
    form: str
    prompt: str

    def __post_init__(self):
        for name, value in self.as_dict().items():
            if not isinstance(value, str) or not value:
                raise ProofError(f"the baseline key's {name} is {value!r}; it must be non-empty text")
        if self.form not in FORMS:
            raise UnknownForm(self.form)

    def as_dict(self) -> Dict[str, str]:
        return {"seeds": self.seeds, "design": self.design, "model": self.model, "form": self.form, "prompt": self.prompt}

    @property
    def id(self) -> str:
        return digest(self.as_dict())

    def __str__(self) -> str:
        return self.id


# --- The forms as plans ------------------------------------------------------------------------


@dataclass(frozen=True)
class FormPlan:
    """A form ready to run: the declaration it runs, the shared context its sessions continue and its plan."""

    form: str
    declaration: decl.Declaration
    shared: messages.SharedContext
    plan: planner.Plan


def one_unit(declaration: decl.Declaration, needs: bool) -> decl.Declaration:
    """The declaration with every unit coupled to every other, so the planner makes one group holding every item. Without
    `needs` no unit asks for an artefact, so the shared context holds none."""
    ids = list(declaration.units)
    units = {uid: dataclasses.replace(unit, needs=unit.needs if needs else (), couples_with=tuple(o for o in ids if o != uid))
             for uid, unit in declaration.units.items()}
    return dataclasses.replace(declaration, units=units)


def form_plan(form: str, declaration: decl.Declaration, catalogue: cat.Catalogue, spec: sess.SessionSpec, *, bound: int,
              cli_version: str, tool_commit: str, replicas: Any = 1, variants: Sequence[str] = (),
              prompt_for: Optional[Callable[[Sequence[str], str], str]] = None, **options: Any) -> FormPlan:
    """The plan of a form by the planner. The single forms are one group with one session and no replica; the fanned form
    takes the declaration as it is, with its replicas and variants. `catalogue` is the review's admitted catalogue: the
    single form with no shared context ignores it."""
    if form not in FORMS:
        raise UnknownForm(form)
    if form == FANNED:
        shaped, held = declaration, catalogue
    else:
        shaped = one_unit(declaration, needs=form == SINGLE_SHARED)
        held = catalogue if form == SINGLE_SHARED else cat.Catalogue(())
        replicas, variants, bound = 1, (), 1
    shared = messages.shared_context(held)
    plan = planner.make_plan(shaped, held, shared, spec, bound=bound, cli_version=cli_version, tool_commit=tool_commit,
                             replicas=replicas, variants=variants, prompt_for=prompt_for, **options)
    return FormPlan(form, shaped, shared, plan)


def run_form(runner: scheduler.Scheduler, formed: FormPlan, spec: sess.SessionSpec,
             prompt_for: Optional[Callable[[Sequence[str], str], str]] = None,
             round_label: Optional[str] = None) -> scheduler.RunResult:
    """The form's plan run by the scheduler, as any review is."""
    return runner.run(formed.declaration, formed.plan, formed.shared, spec, prompt_for, round_label)


# --- One run, in one shape ---------------------------------------------------------------------


@dataclass(frozen=True)
class SessionRecord:
    """One session's own figures. `first_call_read` is None where the run did not keep it."""

    session: str
    wall_s: float
    cost_usd: float
    tokens_read: int
    tokens_written: int
    tokens_generated: int
    first_call_read: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_figures(cls, figures: telemetry.SessionFigures) -> "SessionRecord":
        return cls(figures.session, figures.wall_s, figures.cost_usd, figures.tokens["cache_read"],
                   figures.tokens["cache_write"], figures.tokens["generated"], figures.first_call_read)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class RunOutcome:
    """One run of a form.

    `raised_by` gives, for each seed, the replicas that raised it, and `judged_by` the replicas that judged its item; a
    seed is found when any replica raised it. `verdicts` is the run's verdict for each item, the merged one when the run
    had replicas. `unmatched` is the findings that name no seed. `not_recorded` names the figures the run did not keep.
    """

    id: str
    form: str
    tool_commit: str
    seeded_commit: str
    seeds_found: Tuple[str, ...]
    unmatched: Tuple[str, ...]
    verdicts: Mapping[str, str]
    raised_by: Mapping[str, Tuple[str, ...]]
    judged_by: Mapping[str, Tuple[str, ...]]
    sessions: Tuple[SessionRecord, ...]
    wall_s: float
    cost_usd: float
    not_recorded: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "form": self.form, "tool_commit": self.tool_commit, "seeded_commit": self.seeded_commit,
                "seeds_found": list(self.seeds_found), "unmatched": list(self.unmatched), "verdicts": dict(self.verdicts),
                "raised_by": {seed: list(who) for seed, who in self.raised_by.items()},
                "judged_by": {seed: list(who) for seed, who in self.judged_by.items()},
                "sessions": [item.as_dict() for item in self.sessions], "wall_s": self.wall_s, "cost_usd": self.cost_usd,
                "not_recorded": list(self.not_recorded)}

    @classmethod
    def from_dict(cls, raw: Any, where: str = "a run") -> "RunOutcome":
        if not isinstance(raw, dict):
            raise BaselineFileError(where, "is not a mapping")
        try:
            sessions = tuple(SessionRecord(**item) for item in raw["sessions"])
            made = cls(raw["id"], raw["form"], raw["tool_commit"], raw["seeded_commit"], tuple(raw["seeds_found"]),
                       tuple(raw["unmatched"]), dict(raw["verdicts"]),
                       {seed: tuple(who) for seed, who in raw["raised_by"].items()},
                       {seed: tuple(who) for seed, who in raw["judged_by"].items()}, sessions, raw["wall_s"],
                       raw["cost_usd"], tuple(raw.get("not_recorded", ())))
        except (KeyError, TypeError, AttributeError) as error:
            raise BaselineFileError(where, f"is malformed: {type(error).__name__} {error}") from error
        if made.form not in FORMS:
            raise BaselineFileError(where, f"names the form {made.form!r}, not one of {list(FORMS)}")
        for name in ("wall_s", "cost_usd"):
            if not is_number(getattr(made, name)) or getattr(made, name) < 0:
                raise BaselineFileError(where, f"gives {name} as {getattr(made, name)!r}, not a number from zero")
        if len(set(made.seeds_found)) != len(made.seeds_found):
            raise BaselineFileError(where, "lists a found seed twice")
        return made

    @property
    def found(self) -> int:
        return len(self.seeds_found)


def label_of(lane: scheduler.LaneResult) -> str:
    return f"{lane.group}.r{lane.replica}"


def finding_text(row: Mapping[str, Any], columns: Sequence[str]) -> str:
    return " | ".join(str(row.get(column, "")) for column in columns)


def outcome_from_run(run_id: str, formed: FormPlan, run: scheduler.RunResult, figures: Sequence[telemetry.SessionFigures],
                     seeds: Sequence[Seed], match: Match, *, seeded_commit: str,
                     seed_item: Callable[[Seed], str] = lambda seed: seed["item"]) -> RunOutcome:
    """A run of a form recorded in the proof's shape.

    The replicas' answers are read lane by lane: a seed is raised by a replica when `match(seed, row)` holds for a row of
    its findings table, and found when any replica raised it. A replica judged a seed's item when its group holds that
    item. The wall time is the critical path of the sessions and the cost their sum."""
    shape = formed.declaration.shape
    if shape.findings is None:
        raise ProofError("the declaration has no findings table, so no finding can name a seed")
    columns = shape.table(shape.findings.table).columns
    raised: Dict[str, List[str]] = {seed["id"]: [] for seed in seeds}
    judged: Dict[str, List[str]] = {seed["id"]: [] for seed in seeds}
    unmatched: List[str] = []
    given: Dict[str, List[str]] = {}
    for lane in run.lanes:
        who = label_of(lane)
        tables = lane.unit_record.standing.tables or {}
        items = {item for unit in lane.units for item in formed.declaration.units[unit].items}
        rows = list(tables.get(shape.findings.table, []))
        for seed in seeds:
            if seed_item(seed) in items:
                judged[seed["id"]].append(who)
            if any(match(seed, row) for row in rows):
                raised[seed["id"]].append(who)
        for row in rows:
            if not any(match(seed, row) for seed in seeds):
                unmatched.append(f"{who}: {finding_text(row, columns)}")
        for table in shape.tables:
            if table.verdict_column and table.key:
                for row in tables.get(table.name, []):
                    given.setdefault(row[table.key], []).append(row[table.verdict_column])
    verdict_table = next((t for t in shape.tables if t.verdict_column and t.key), None)
    verdicts = ({item: merge.merged_verdict(verdict_table, merge.Rules(), found) for item, found in given.items()}
                if verdict_table else {})
    totals = telemetry.run_figures(figures)
    return RunOutcome(run_id, formed.form, formed.plan.tool_commit, seeded_commit,
                      tuple(seed["id"] for seed in seeds if raised[seed["id"]]), tuple(unmatched), verdicts,
                      {seed: tuple(who) for seed, who in raised.items() if who},
                      {seed: tuple(who) for seed, who in judged.items()},
                      tuple(SessionRecord.from_figures(item) for item in figures), totals.critical_path_s, totals.cost_usd)


# --- Baselines ---------------------------------------------------------------------------------


class BaselineStore:
    """Recorded runs, each under its baseline key; the runs of a key are kept in the order they were added."""

    def __init__(self):
        self.runs: Dict[str, List[RunOutcome]] = {}
        self.keys: Dict[str, BaselineKey] = {}

    def add(self, key: BaselineKey, outcome: RunOutcome) -> None:
        if outcome.form != key.form:
            raise ProofError(f"the run {outcome.id} is of the {outcome.form} form and the key is of the {key.form} form")
        if any(run.id == outcome.id for run in self.runs.get(key.id, [])):
            raise ProofError(f"the baseline key {key} already holds a run {outcome.id}")
        self.keys[key.id] = key
        self.runs.setdefault(key.id, []).append(outcome)

    def recorded(self, key: BaselineKey) -> List[RunOutcome]:
        return list(self.runs.get(key.id, []))

    def refuse_if_recorded(self, key: BaselineKey) -> None:
        """Raise `BaselineRecorded`, naming the key, when the form is a baseline form with runs recorded under it."""
        found = self.runs.get(key.id, [])
        if key.form in BASELINE_FORMS and found:
            raise BaselineRecorded(key.id, key.form, len(found))

    def run_unless_recorded(self, key: BaselineKey, make: Callable[[], RunOutcome]) -> RunOutcome:
        """Run a form through `make` unless its baseline is recorded under the key, and record what it returns."""
        self.refuse_if_recorded(key)
        outcome = make()
        self.add(key, outcome)
        return outcome


def read_key(raw: Any, where: str) -> BaselineKey:
    if not isinstance(raw, dict):
        raise BaselineFileError(where, "has no key mapping")
    missing = [name for name in ("seeds", "design", "model", "form", "prompt") if name not in raw]
    if missing:
        raise BaselineFileError(where, f"has a key without {missing}")
    try:
        return BaselineKey(**{name: raw[name] for name in ("seeds", "design", "model", "form", "prompt")})
    except ProofError as error:
        raise BaselineFileError(where, str(error)) from error


def load_baselines(path: str) -> BaselineStore:
    """The recorded runs in a baselines file, each under the key its group of runs states."""
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as error:
        raise BaselineFileError(path, f"cannot be read as JSON: {error}") from error
    if not isinstance(raw, dict) or raw.get("version") != BASELINES_VERSION:
        raise BaselineFileError(path, f"is not a baselines file of version {BASELINES_VERSION}")
    groups = raw.get("baselines")
    if not isinstance(groups, list) or not groups:
        raise BaselineFileError(path, "holds no baselines")
    loaded = BaselineStore()
    for number, group in enumerate(groups, 1):
        where = f"{path} baseline {number}"
        if not isinstance(group, dict) or not isinstance(group.get("runs"), list):
            raise BaselineFileError(where, "has no list of runs")
        key = read_key(group.get("key"), where)
        for index, entry in enumerate(group["runs"], 1):
            try:
                loaded.add(key, RunOutcome.from_dict(entry, f"{where} run {index}"))
            except BaselineFileError:
                raise
            except ProofError as error:
                raise BaselineFileError(where, str(error)) from error
    return loaded


# --- The pooled criterion ----------------------------------------------------------------------


@dataclass(frozen=True)
class Clause:
    """One clause of the criterion, judged for the fanned-out runs together. `near` is true when a run that meets the
    clause is within ten per cent of its bound."""

    name: str
    ok: bool
    near: bool
    detail: str

    def as_dict(self) -> Dict[str, Any]:
        return {"clause": self.name, "ok": self.ok, "near_bound": self.near, "detail": self.detail}


@dataclass(frozen=True)
class Verdict:
    """The criterion's verdict. `second_run_required` is true when the criterion holds for a single fanned-out run that is
    within ten per cent of a bound; the proof is then not accepted until a second fanned-out run is recorded."""

    accepted: bool
    clauses: Tuple[Clause, ...]
    second_run_required: bool
    bounds: Mapping[str, float]

    @property
    def failed(self) -> List[str]:
        return [clause.name for clause in self.clauses if not clause.ok]

    @property
    def status(self) -> str:
        return "pass" if self.accepted else "second-run-required" if self.second_run_required else "fail"

    def as_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "accepted": self.accepted, "failed_clauses": self.failed,
                "second_run_required": self.second_run_required, "bounds": dict(self.bounds),
                "clauses": [clause.as_dict() for clause in self.clauses]}


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def accept(singles: Sequence[RunOutcome], fanned: Sequence[RunOutcome], cost_multiple: float) -> Verdict:
    """The pooled criterion over recorded single runs and at least one fanned-out run.

    - the seeds found in each fanned-out run are no fewer than the fewest any single run found;
    - no seed that every single run found is missed by every fanned-out run;
    - each fanned-out run's wall time is at most half the single mean;
    - each fanned-out run's cost is at most `cost_multiple` times the single mean cost.

    It fails naming each clause that does not hold. When the criterion holds for exactly one fanned-out run that is within
    ten per cent of a bound (a count of seeds at most ten per cent above the fewest, a time or cost at least ninety per
    cent of its bound), a second fanned-out run is required."""
    if not singles:
        raise NotEnoughRuns("the pooled criterion needs at least one recorded single run; none was given")
    if not fanned:
        raise NotEnoughRuns("the pooled criterion needs at least one fanned-out run; none was given")
    if not is_number(cost_multiple) or cost_multiple <= 0:
        raise ProofError(f"the cost multiple is {cost_multiple!r}; it must be a number above zero")
    for run in (*singles, *fanned):
        if not is_number(run.wall_s) or not is_number(run.cost_usd):
            raise ProofError(f"the run {run.id} has no wall time or cost, so it cannot be judged")
    floor = min(run.found for run in singles)
    always = sorted(set.intersection(*(set(run.seeds_found) for run in singles)))
    wall_bound = WALL_FRACTION * mean([run.wall_s for run in singles])
    cost_bound = cost_multiple * mean([run.cost_usd for run in singles])
    short = [f"{run.id} found {run.found}" for run in fanned if run.found < floor]
    clauses = [Clause(SEEDS_FLOOR, not short, not short and any(run.found <= floor * (1 + NEAR) for run in fanned),
                      f"the fewest seeds any single run found is {floor}" + (f"; {'; '.join(short)}" if short else
                      f"; fanned-out runs found {[run.found for run in fanned]}"))]
    union = set().union(*(set(run.seeds_found) for run in fanned))
    lost = [seed for seed in always if seed not in union]
    clauses.append(Clause(SEED_EVERY_SINGLE_FOUND, not lost, False,
                          f"missed by every fanned-out run though every single run found it: {lost}" if lost else
                          f"{len(always)} seeds were found by every single run and each is found by a fanned-out run"))
    slow = [f"{run.id} took {run.wall_s:g} s" for run in fanned if run.wall_s > wall_bound]
    clauses.append(Clause(WALL_TIME, not slow, not slow and any(run.wall_s >= (1 - NEAR) * wall_bound for run in fanned),
                          f"at most {wall_bound:g} s, half the single mean" + (f"; {'; '.join(slow)}" if slow else "")))
    dear = [f"{run.id} cost {run.cost_usd:g}" for run in fanned if run.cost_usd > cost_bound]
    clauses.append(Clause(COST, not dear, not dear and any(run.cost_usd >= (1 - NEAR) * cost_bound for run in fanned),
                          f"at most {cost_bound:g} USD, {cost_multiple:g} times the single mean" +
                          (f"; {'; '.join(dear)}" if dear else "")))
    holds = all(clause.ok for clause in clauses)
    second = holds and len(fanned) == 1 and any(clause.near for clause in clauses)
    return Verdict(holds and not second, tuple(clauses), second,
                   {"seeds_floor": floor, "wall_s": wall_bound, "cost_usd": cost_bound})


# --- The replicas' statistics ------------------------------------------------------------------


def replica_statistics(fanned: Sequence[RunOutcome]) -> Dict[str, Any]:
    """The rate at which one replica misses a seed, and the correlation between replicas.

    A trial is a replica that judged a seed's item in one run; it misses when it did not raise the seed. The correlation
    is the Pearson correlation between the misses of two replicas of one group over every seed they both judged, taking
    each pair both ways round; it is None when the misses do not vary or no seed was judged by two replicas."""
    trials = misses = 0
    pairs: List[Tuple[int, int]] = []
    for run in fanned:
        for seed, judges in run.judged_by.items():
            missed = [0 if who in run.raised_by.get(seed, ()) else 1 for who in judges]
            trials += len(missed)
            misses += sum(missed)
            for i in range(len(missed)):
                for j in range(i + 1, len(missed)):
                    pairs += [(missed[i], missed[j]), (missed[j], missed[i])]
    correlation = None
    if pairs:
        xs, ys = [x for x, _ in pairs], [y for _, y in pairs]
        mx, my = mean(xs), mean(ys)
        sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
        sy = math.sqrt(sum((y - my) ** 2 for y in ys))
        if sx > 0 and sy > 0:
            correlation = round(sum((x - mx) * (y - my) for x, y in pairs) / (sx * sy), 4)
    return {"trials": trials, "misses": misses, "miss_rate": round(misses / trials, 4) if trials else None,
            "replica_pairs": len(pairs) // 2, "correlation": correlation}


# --- The record --------------------------------------------------------------------------------


def common_verdict(singles: Sequence[RunOutcome], item: str) -> Optional[str]:
    """The verdict most single runs gave an item, the first run's among equals; None when none judged it."""
    given = [run.verdicts[item] for run in singles if item in run.verdicts]
    if not given:
        return None
    return max(dict.fromkeys(given), key=given.count)


def verdict_differences(singles: Sequence[RunOutcome], run: RunOutcome,
                        explanations: Mapping[Tuple[str, str], str]) -> List[Dict[str, Any]]:
    """The items a fanned-out run judged otherwise than the single runs' most common verdict (an item no single judged, or the
    run did not, counts), each with the verdict every single run gave and an explanation, empty until one is written."""
    items = sorted(set(run.verdicts).union(*(set(single.verdicts) for single in singles)))
    found = []
    for item in items:
        common, own = common_verdict(singles, item), run.verdicts.get(item)
        if own != common:
            found.append({"item": item, "fanned": own, "single": common,
                          "singles": {single.id: single.verdicts.get(item) for single in singles},
                          "explanation": explanations.get((run.id, item), "")})
    return found


def run_report(run: RunOutcome) -> Dict[str, Any]:
    return {"id": run.id, "form": run.form, "tool_commit": run.tool_commit, "seeded_commit": run.seeded_commit,
            "seeds_found": list(run.seeds_found), "seeds_found_count": run.found, "unmatched": list(run.unmatched),
            "wall_s": run.wall_s, "cost_usd": run.cost_usd, "sessions": [item.as_dict() for item in run.sessions],
            "raised_by": {seed: list(who) for seed, who in run.raised_by.items()}, "not_recorded": list(run.not_recorded)}


def build_record(seeds: Sequence[Seed], singles: Sequence[RunOutcome], fanned: Sequence[RunOutcome], cost_multiple: float,
                 keys: Sequence[BaselineKey] = (), explanations: Optional[Mapping[Tuple[str, str], str]] = None) -> Dict[str, Any]:
    """The record of a proof over recorded runs: the verdict, each run's seeds found, findings matching no seed, sessions
    and, for each seed, the replicas that raised it, with the rate at which one replica misses a seed and the correlation
    between replicas, and the verdict differences of each fanned-out run, each with an explanation field."""
    explanations = explanations or {}
    verdict = accept(singles, fanned, cost_multiple)
    return {"version": 1, "seeds": [seed["id"] for seed in seeds], "seed_list_sha256": seed_list_hash(seeds),
            "cost_multiple": cost_multiple, "keys": [dict(key.as_dict(), id=key.id) for key in keys],
            "verdict": verdict.as_dict(),
            "single_runs": [run_report(run) for run in singles], "fanned_runs": [run_report(run) for run in fanned],
            "single_means": {"wall_s": round(mean([run.wall_s for run in singles]), 3),
                             "cost_usd": round(mean([run.cost_usd for run in singles]), 6)},
            "seed_replicas": {seed["id"]: {run.id: list(run.raised_by.get(seed["id"], ())) for run in fanned}
                              for seed in seeds},
            "replicas": replica_statistics(fanned),
            "verdict_differences": {run.id: verdict_differences(singles, run, explanations) for run in fanned}}


def record_lines(record: Mapping[str, Any]) -> List[str]:
    """The record as text: the verdict and the clause that fails first, then each run's figures."""
    verdict = record["verdict"]
    lines = [f"PROOF {verdict['status']} | single runs {len(record['single_runs'])} | fanned-out runs {len(record['fanned_runs'])}"
             f" | cost multiple {record['cost_multiple']:g}"]
    for clause in verdict["clauses"]:
        lines.append(f"{'ok  ' if clause['ok'] else 'FAIL'} {clause['clause']}: {clause['detail']}")
    if verdict["status"] == "second-run-required":
        lines.append("a second fanned-out run is required: the first is within ten per cent of a bound")
    for label, runs in (("single", record["single_runs"]), ("fanned", record["fanned_runs"])):
        for run in runs:
            lines.append(f"{label} {run['id']}: seeds {run['seeds_found_count']} of {len(record['seeds'])}, "
                         f"{run['wall_s']:g} s, {run['cost_usd']:g} USD, {len(run['unmatched'])} findings matching no seed, "
                         f"{len(run['sessions'])} sessions")
    stats = record["replicas"]
    lines.append(f"replicas: {stats['misses']} misses in {stats['trials']} trials, miss rate {stats['miss_rate']}, "
                 f"correlation {stats['correlation']}")
    for run_id, differences in record["verdict_differences"].items():
        lines.append(f"verdict differences of {run_id}: {len(differences)}")
    return lines


def write_record(path: str, record: Mapping[str, Any]) -> None:
    store.atomic_write_json(path, record)
