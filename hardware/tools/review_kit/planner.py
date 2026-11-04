"""The planner: units into groups, groups into roots, and the plan record.

Units a caller declares as coupled are in one group, and the rest are packed first-fit up to the largest single unit's expected
output: the groups are the units of parallel work, and they are the same whether or not a budget is declared. A group is the
unit of wall time and a root the unit of cost: each group's forks continue a root that holds the artefacts every unit needs, the
artefacts the units of every group the root serves declare, and the extract of the deterministic check's report for the rules
those units judge, and nothing a group of another root alone needs. The roots start as one for each group and are merged, the
pair whose merged root is within the context budget and whose merge writes the fewest tokens first, over and over while the
merge saves tokens, ties by declaration order; a review that states no budget is held to none, so its groups share one root.
A group whose own artefacts with the shared documents are over the context budget, or a root whose message is over the agent
command line's stream limit, is refused, naming the group or root and its size, before any session starts.

Replicas and their variants arrive as plain data: a replica count (one number or
one per unit) and the ids of the variants the replicas take in turn. The prompt of
a variant is the ensemble's to supply, through `prompt_for`.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from . import catalogue as cat
from . import costmodel as cm
from . import decl, extract, messages
from . import session as sess

ROOT, UNIT, REPAIR = "root", "unit", "repair"
PLAN_VERSION = 2
BASE_VARIANT = "base"


class OverBudget(Exception):
    """The artefacts every unit needs are, on their own, larger than the context budget, so no group's root could fit; `lines`
    are this cause and then each group's, which is over the budget with them."""

    def __init__(self, size: int, budget: int, overruns: Sequence["Overrun"] = ()):
        self.size, self.budget, self.overruns = size, budget, list(overruns)
        super().__init__(f"the shared documents (the artefacts every unit needs) are {size} tokens, over the review's context "
                         f"budget of {budget} tokens; take artefacts out of the units' `needs`, or raise the budget's context_tokens")
        self.lines = [str(self)] + [overrun.line(budget) for overrun in self.overruns]


@dataclass(frozen=True)
class Overrun:
    """A group, or for another model a root, over the context budget: its id, its units, its size in tokens and its images."""

    group: str
    units: Tuple[str, ...]
    tokens: int
    images: int
    #: The model whose root it is when that is not the review's, the budget that model's root is held to, the id of that root
    #: and the ids of the groups it serves.
    model: Optional[str] = None
    limit: Optional[int] = None
    root: Optional[str] = None
    groups: Tuple[str, ...] = ()

    def line(self, budget: int) -> str:
        if self.model is None:
            who = (f"unit {self.units[0]} alone" if len(self.units) == 1
                   else f"units {', '.join(self.units)}, which the declaration couples")
            return (f"group {self.group} ({who}) holds {self.tokens} tokens with the shared documents, more than the review's context "
                    f"budget of {budget} tokens, {self.tokens - budget} over; declare fewer views for the units named in their "
                    "`needs`, or raise the budget's context_tokens or context_fraction")
        budget = self.limit if self.limit is not None else budget
        return (f"root {self.root} (groups {', '.join(self.groups)}, units {', '.join(self.units)}) holds {self.tokens} tokens for the "
                f"model {self.model}, more than that model's context budget of {budget} tokens, {self.tokens - budget} over; declare "
                "fewer views for those units in their `needs`, or raise the budget's context_tokens or context_fraction")


class GroupsOverBudget(Exception):
    """One or more groups hold more than the context budget; every one is named."""

    def __init__(self, overruns: Sequence[Overrun], budget: int):
        self.overruns, self.budget = list(overruns), budget
        self.lines = [overrun.line(budget) for overrun in self.overruns]
        super().__init__("; ".join(self.lines))


class WindowUndeclared(Exception):
    """The budget is a fraction of the model's context window and the kit declares no window for the model."""

    def __init__(self, model: Optional[str]):
        self.model = model
        who = ("the review names no model, so it has no declared context window" if model is None
               else f"the model {model!r} has no declared context window")
        super().__init__(f"{who}, and the budget is a fraction of it; state a context_tokens figure, or add the model's window to "
                         "the window table (WINDOW_TOKENS_BY_MODEL in review_kit/costmodel.py)"
                         + ("" if model is not None else " and name the model with --model"))


class OverStreamLimit(Exception):
    def __init__(self, size: int, limit: int, group: str, group_size: int, root: Optional[str] = None):
        self.size, self.limit, self.group, self.group_size, self.root = size, limit, group, group_size, root
        whose = f"root {root}'s" if root else "the shared context's"
        super().__init__(f"{whose} stream message is {size} characters, over the agent command line's stream "
                         f"limit of {limit} characters; the largest group of artefacts is {group} at {group_size} "
                         "characters; write fewer or smaller views")


class BoundBelowOne(ValueError):
    def __init__(self, bound: Any):
        self.bound = bound
        super().__init__(f"the bound on sessions at once is {bound}; it must be a whole number of one or more")


@dataclass(frozen=True)
class Node:
    """One session of the plan: its role, the node it continues, the group and replica it belongs to, its attempt, the
    hash of the prefix it continues from and of its own message."""

    id: str
    role: str
    parent: Optional[str]
    group: Optional[str]
    replica: Optional[int]
    attempt: int
    variant: Optional[str]
    units: Tuple[str, ...]
    prefix_sha: str
    message_sha: str

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "role": self.role, "parent": self.parent, "group": self.group, "replica": self.replica,
                "attempt": self.attempt, "variant": self.variant, "units": list(self.units), "prefix_sha": self.prefix_sha,
                "message_sha": self.message_sha}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Node":
        return cls(raw["id"], raw["role"], raw["parent"], raw["group"], raw["replica"], raw["attempt"], raw["variant"],
                   tuple(raw["units"]), raw["prefix_sha"], raw["message_sha"])


@dataclass(frozen=True)
class Group:
    id: str
    units: Tuple[str, ...]
    needs: Tuple[str, ...]
    expected_output_tokens: int
    replicas: int
    #: The id of the root the group's forks continue, the images and tokens the group's own artefacts hold with the shared
    #: documents (what a root of its own would hold), and its check extract: the rules the units declare, the lines of the
    #: report held and the (unit, rule) pairs the report holds no line for.
    root: str = "root"
    images: int = 0
    tokens: int = 0
    extract: Mapping[str, Any] = field(default_factory=lambda: {"rules": [], "lines": 0, "missing": []})

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "units": list(self.units), "needs": list(self.needs),
                "expected_output_tokens": self.expected_output_tokens, "replicas": self.replicas, "root": self.root,
                "images": self.images, "tokens": self.tokens,
                "extract": {"rules": list(self.extract["rules"]), "lines": self.extract["lines"],
                            "missing": [dict(entry) for entry in self.extract["missing"]]}}


@dataclass(frozen=True)
class Root:
    """A root of the plan: the groups it serves, the artefacts it holds (the union of their needs), the images and tokens it
    holds in all, the hash of its prefix, and whether it is started: a root none of whose groups has a replica on the review's
    own model is not."""

    id: str
    groups: Tuple[str, ...]
    needs: Tuple[str, ...]
    images: int
    tokens: int
    prefix_sha: str
    started: bool = True

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "groups": list(self.groups), "needs": list(self.needs), "images": self.images,
                "tokens": self.tokens, "prefix_sha": self.prefix_sha, "started": self.started}


@dataclass(frozen=True)
class Plan:
    """The plan record. Everything in it is plain data and `to_dict` is the JSON the record is written as."""

    groups: Tuple[Group, ...]
    nodes: Tuple[Node, ...]
    spec: Dict[str, Any]
    spec_digest: str
    #: The shared documents: the artefacts every unit needs, which every root holds.
    shared: Dict[str, Any]
    variants: Tuple[str, ...]
    bound: int
    prices: Dict[str, Any]
    timing: Dict[str, Any]
    calls_per_fork: int
    predicted: Dict[str, Any]
    tree: Dict[str, Any]
    cli_version: str
    tool_commit: str
    #: The roots built for the review's own model: each with the groups it serves.
    root_records: Tuple[Root, ...] = ()
    #: The roots built besides those, one for each root and each other model its groups' replicas run on: the root node's id,
    #: the root it holds the views of and the groups that root serves, the model, the specification and its digest, the prefix
    #: hash and the variants that fork from it.
    contexts: Tuple[Dict[str, Any], ...] = ()
    #: The paths the declaration lists as added to the review folder during the round; the folder hash leaves them out.
    added_during_round: Tuple[str, ...] = ()
    #: The context budget every root is held to, in tokens (None when the declaration states none), the fraction and window
    #: it was taken from when it was stated as a fraction, and the model whose window it is.
    budget: Mapping[str, Any] = field(default_factory=lambda: {"tokens": None, "fraction": None, "window": None, "model": None})

    @property
    def roots(self) -> List[Node]:
        """The node of every root started: those of the review's own model, then the roots for each other model."""
        return [node for node in self.nodes if node.role == ROOT]

    @property
    def lanes(self) -> List[Node]:
        """The first node of each group and replica: the forks the roots have."""
        return [node for node in self.nodes if node.role == UNIT]

    @property
    def root(self) -> Node:
        return self.nodes[0]

    def root_of(self, group: str) -> Root:
        """The root the group's forks continue."""
        wanted = next(g.root for g in self.groups if g.id == group)
        return next(root for root in self.root_records if root.id == wanted)

    def group_of(self, unit: str) -> Group:
        for group in self.groups:
            if unit in group.units:
                return group
        raise KeyError(unit)

    @property
    def units(self) -> List[str]:
        return [unit for group in self.groups for unit in group.units]

    def to_dict(self) -> Dict[str, Any]:
        return {"version": PLAN_VERSION, "groups": [group.as_dict() for group in self.groups],
                "roots": [root.as_dict() for root in self.root_records],
                "nodes": [node.as_dict() for node in self.nodes], "spec": self.spec, "spec_digest": self.spec_digest,
                "shared": self.shared, "variants": list(self.variants), "bound": self.bound, "prices": self.prices,
                "timing": self.timing, "calls_per_fork": self.calls_per_fork, "predicted": self.predicted,
                "tree": self.tree, "cli_version": self.cli_version, "tool_commit": self.tool_commit,
                "contexts": [dict(context) for context in self.contexts],
                "added_during_round": list(self.added_during_round), "budget": dict(self.budget)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Plan":
        groups = tuple(Group(g["id"], tuple(g["units"]), tuple(g["needs"]), g["expected_output_tokens"], g["replicas"], g["root"],
                             g["images"], g["tokens"], g["extract"]) for g in raw["groups"])
        roots = tuple(Root(r["id"], tuple(r["groups"]), tuple(r["needs"]), r["images"], r["tokens"], r["prefix_sha"], r["started"])
                      for r in raw["roots"])
        return cls(groups, tuple(Node.from_dict(n) for n in raw["nodes"]), raw["spec"], raw["spec_digest"], raw["shared"],
                   tuple(raw["variants"]), raw["bound"], raw["prices"], raw["timing"], raw["calls_per_fork"],
                   raw["predicted"], raw["tree"], raw["cli_version"], raw["tool_commit"], roots,
                   tuple(raw.get("contexts", ())), tuple(raw.get("added_during_round", ())), raw["budget"])


# --- The budget --------------------------------------------------------------------------------


def context_budget(budget: decl.Budget, model: Optional[str]) -> Optional[int]:
    """The most tokens a session's context may hold: the declared figure; else the headroom fraction of the model's declared
    context window, rounded down; else None, for a review that states no budget. A fraction with no declared window for the
    model is refused, never given a default."""
    if budget.context_tokens is not None:
        return budget.context_tokens
    if budget.context_fraction is None:
        return None
    window = cm.window_for(model)
    if window is None:
        raise WindowUndeclared(model)
    return int(window * budget.context_fraction)


# --- Grouping ----------------------------------------------------------------------------------


def coupled_sets(declaration: decl.Declaration) -> List[List[str]]:
    """The sets of units that must share a group: the connected sets of the `couples_with` links, in either direction, each
    in declaration order and the sets in the order of their first unit."""
    order = list(declaration.units)
    parent = {unit: unit for unit in order}

    def find(unit: str) -> str:
        while parent[unit] != unit:
            parent[unit] = parent[parent[unit]]
            unit = parent[unit]
        return unit

    for unit in declaration.units.values():
        for other in unit.couples_with:
            parent[find(unit.id)] = find(other)
    sets: Dict[str, List[str]] = {}
    for unit in order:
        sets.setdefault(find(unit), []).append(unit)
    return list(sets.values())


def pack(declaration: decl.Declaration) -> List[List[str]]:
    """Groups of units: each coupled set whole, small sets packed together first-fit, largest first, up to the largest single
    unit's expected output. Deterministic for a declaration, and the groups of every review, whatever its budget."""
    output = {uid: unit.expected_output_tokens for uid, unit in declaration.units.items()}
    cap = max(output.values())
    order = list(declaration.units)
    sets = sorted(coupled_sets(declaration), key=lambda units: (-sum(output[u] for u in units), order.index(units[0])))
    groups: List[List[str]] = []
    loads: List[int] = []
    for units in sets:
        size = sum(output[u] for u in units)
        for index, load in enumerate(loads):
            if load + size <= cap:
                groups[index].extend(units)
                loads[index] += size
                break
        else:
            groups.append(list(units))
            loads.append(size)
    for units in groups:
        units.sort(key=order.index)
    groups.sort(key=lambda units: order.index(units[0]))
    return groups


def replica_counts(declaration: decl.Declaration, groups: Sequence[Sequence[str]],
                   replicas: Union[int, Mapping[str, int]]) -> List[int]:
    if not isinstance(replicas, (int, Mapping)):
        raise ValueError(f"the replica count is {replicas!r}; it must be a whole number of one or more, or a mapping of unit to one")
    counts = []
    for units in groups:
        wanted = [replicas] if isinstance(replicas, int) else [replicas.get(u, 1) for u in units]
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in wanted):
            raise ValueError(f"the replica count for {list(units)} is {wanted}; it must be a whole number of one or more")
        counts.append(max(wanted))
    return counts


def default_prompt(declaration: decl.Declaration) -> Callable[[Sequence[str], str], str]:
    return lambda units, variant: messages.group_prompt(declaration, units)


# --- The roots ---------------------------------------------------------------------------------


class Sizing:
    """What a root holding a set of artefacts and the extract for a set of rules weighs, by the catalogue's own measures, without
    building its message. `tokens(needs, rules)` equals the `tokens` of the context built from the same."""

    def __init__(self, declaration: decl.Declaration, catalogue: cat.Catalogue):
        self.cost = {a.name: a.tokens + messages.framing_of(a) for a in catalogue.artefacts}
        self.images = {a.name for a in catalogue.artefacts if a.kind == "image"}
        pattern = declaration.check_extract.rule if declaration.check_extract else None
        self.extractor = extract.Extractor(catalogue.report, pattern) if pattern is not None and catalogue.report else None
        self.extract_framing = (len(messages.header(self.extractor.artefact(()))) + 1) if self.extractor else 0

    def extract_tokens(self, rules: Iterable[str]) -> int:
        wanted = set(rules)
        if not wanted or self.extractor is None:
            return 0
        return self.extractor.size(wanted) + self.extract_framing

    def tokens(self, needs: Iterable[str], rules: Iterable[str] = ()) -> int:
        return messages.BASE_FRAMING + sum(self.cost[name] for name in needs) + self.extract_tokens(rules)


@dataclass(frozen=True)
class Built:
    """A group: its units, the artefacts they declare, the root its forks continue, its check extract, and the images and
    tokens a root holding only its artefacts and the shared documents would hold."""

    id: str
    units: Tuple[str, ...]
    needs: Tuple[str, ...]
    expected_output_tokens: int
    root: str
    extract: Mapping[str, Any]
    images: int
    tokens: int


@dataclass(frozen=True)
class BuiltRoot:
    """A root built: the groups it serves, the artefacts and extract it holds, and the context and its size."""

    id: str
    groups: Tuple[str, ...]
    needs: Tuple[str, ...]
    catalogue: cat.Catalogue
    shared: messages.SharedContext

    @property
    def images(self) -> int:
        return sum(1 for artefact in self.catalogue.artefacts if artefact.kind == "image")

    @property
    def tokens(self) -> int:
        return self.shared.tokens


@dataclass(frozen=True)
class Formed:
    """The groups of a review with the roots that serve them built and held to the budget: what the plan is made from and what
    the scheduler starts."""

    groups: Tuple[Built, ...]
    built_roots: Tuple[BuiltRoot, ...]
    #: The context of the shared documents, the artefacts every unit needs.
    shared: messages.SharedContext
    #: The most tokens a root may hold and what it was taken from.
    budget: Mapping[str, Any]

    @property
    def roots(self) -> Dict[str, messages.SharedContext]:
        """Each root's context by the id of its root node."""
        return {built.id: built.shared for built in self.built_roots}

    def root_of(self, group: str) -> BuiltRoot:
        wanted = next(built.root for built in self.groups if built.id == group)
        return next(root for root in self.built_roots if root.id == wanted)


def shared_names(declaration: decl.Declaration) -> List[str]:
    """The artefacts every unit needs, by name: the shared documents every root holds."""
    sets = [set(unit.needs) for unit in declaration.units.values()]
    return sorted(set.intersection(*sets)) if sets else []


def group_figures(declaration: decl.Declaration, sizing: Sizing, units: Sequence[str], number: int, expected_output: int) -> Built:
    """One group: the artefacts its units need and the extract of the check's report for the rules they judge, and what a root
    of its own would hold. Its root is named once the roots are formed."""
    needs = sorted({name for uid in units for name in declaration.units[uid].needs})
    rules = sorted({rule for uid in units for rule in declaration.units[uid].check_rules})
    missing = set(sizing.extractor.missing(rules)) if sizing.extractor is not None else set()
    lines = sum(1 for rule, _ in sizing.extractor.lines if rule in rules) if sizing.extractor is not None else 0
    entry = {"rules": rules, "lines": lines,
             "missing": [{"unit": uid, "rule": rule} for uid in units for rule in declaration.units[uid].check_rules if rule in missing]}
    return Built(f"G{number}", tuple(units), tuple(needs), expected_output, "", entry, sum(1 for name in needs if name in sizing.images),
                 sizing.tokens(needs, rules))


@dataclass
class _Held:
    """A root being formed: the groups it serves by position, what it holds and what that weighs."""

    groups: List[int]
    needs: set
    rules: set
    tokens: int


def merge_roots(declaration: decl.Declaration, sizing: Sizing, groups: Sequence[Built], budget: Optional[int]) -> List[List[int]]:
    """The groups, by position, each root serves. The roots start as one for each group; the pair whose merged root is within the
    budget and whose merge writes the fewest tokens (the tokens of both roots less those of the root holding what both hold, so
    the artefacts both hold and the fixed text one root less writes) is merged, over and over while that saving is above zero,
    ties by declaration order of the pairs' first groups. No group is parted. With no budget every merge fits."""
    held = [_Held([index], set(group.needs), {rule for uid in group.units for rule in declaration.units[uid].check_rules}, group.tokens)
            for index, group in enumerate(groups)]
    while True:
        best: Optional[Tuple[Tuple[int, int, int], int, int, int]] = None
        for first in range(len(held)):
            for second in range(first + 1, len(held)):
                a, b = held[first], held[second]
                merged = sizing.tokens(a.needs | b.needs, a.rules | b.rules)
                saving = a.tokens + b.tokens - merged
                if saving <= 0 or (budget is not None and merged > budget):
                    continue
                key = (-saving, a.groups[0], b.groups[0])
                if best is None or key < best[0]:
                    best = (key, first, second, merged)
        if best is None:
            return [root.groups for root in held]
        _, first, second, merged = best
        a, b = held[first], held[second]
        held[first] = _Held(sorted(a.groups + b.groups), a.needs | b.needs, a.rules | b.rules, merged)
        del held[second]
        held.sort(key=lambda root: root.groups[0])


def build_root(declaration: decl.Declaration, catalogue: cat.Catalogue, sizing: Sizing, groups: Sequence[Built], root_id: str
               ) -> BuiltRoot:
    """A root: the artefacts the units of its groups need and the extract of the check's report for the rules they judge."""
    units = [uid for group in groups for uid in group.units]
    needs = sorted({name for group in groups for name in group.needs})
    rules = sorted({rule for uid in units for rule in declaration.units[uid].check_rules})
    extra = [sizing.extractor.artefact(rules)] if rules and sizing.extractor is not None else []
    held = catalogue.subset(needs, extra)
    return BuiltRoot(root_id, tuple(group.id for group in groups), tuple(needs), held, messages.shared_context(held))


def check_stream(catalogue: cat.Catalogue, shared: messages.SharedContext, root: Optional[str] = None) -> None:
    """Refuse a context whose message is over the agent command line's stream limit, naming the largest group of artefacts
    and, given it, the root."""
    size = messages.stream_size(shared.message)
    if size > messages.STREAM_LIMIT:
        raise OverStreamLimit(size, messages.STREAM_LIMIT, *messages.largest_group(catalogue), root=root)


def form(declaration: decl.Declaration, catalogue: cat.Catalogue, model: Optional[str], hold_groups: bool = False) -> Formed:
    """The groups of a review as `pack` packs them, the roots that serve them built, and every root held to the context budget:
    refused before any session starts when the budget is a fraction of a window the kit does not declare, when the shared
    documents are over the budget on their own, when any group's own artefacts with them are over it (every one is named), or
    when a root's message is over the agent command line's limit. The groups are held to the budget here only when `hold_groups`
    is given true: `make_plan` is the one point that holds them, those that start a root for the review's model, a group whose
    replicas all run on another model being held to that model's budget instead."""
    budget = context_budget(declaration.budget, model)
    sizing = Sizing(declaration, catalogue)
    shared = messages.shared_context(catalogue.subset(shared_names(declaration)))
    alone = [group_figures(declaration, sizing, units, number, sum(declaration.units[uid].expected_output_tokens for uid in units))
             for number, units in enumerate(pack(declaration), 1)]
    if budget is not None:
        over = [Overrun(group.id, group.units, group.tokens, group.images) for group in alone if group.tokens > budget]
        if shared.tokens > budget:
            raise OverBudget(shared.tokens, budget, over)
        if over and hold_groups:
            raise GroupsOverBudget(over, budget)
    served = merge_roots(declaration, sizing, alone, budget)
    ids = [ROOT] if len(served) == 1 else [f"{ROOT}.R{number}" for number in range(1, len(served) + 1)]
    roots = tuple(build_root(declaration, catalogue, sizing, [alone[index] for index in indexes], root_id)
                  for indexes, root_id in zip(served, ids))
    root_of = {group_id: root.id for root in roots for group_id in root.groups}
    groups = tuple(dataclasses.replace(group, root=root_of[group.id]) for group in alone)
    for root in roots:
        check_stream(root.catalogue, root.shared, root.id if len(roots) > 1 else None)
    window = cm.window_for(model) if declaration.budget.context_fraction is not None else None
    return Formed(groups, roots, shared, {"tokens": budget, "fraction": declaration.budget.context_fraction, "window": window, "model": model})


# --- The plan ----------------------------------------------------------------------------------


def make_plan(declaration: decl.Declaration, catalogue: cat.Catalogue, spec: sess.SessionSpec, *, bound: int, cli_version: str,
              tool_commit: str, replicas: Union[int, Mapping[str, int]] = 1, variants: Sequence[str] = (),
              prices: Optional[cm.Prices] = None, timing: cm.Timing = cm.Timing(), calls_per_fork: int = cm.CALLS_PER_FORK,
              prompt_for: Optional[Callable[[Sequence[str], str], str]] = None, contexts: Sequence[Any] = (),
              formed: Optional[Formed] = None) -> Plan:
    """The plan for a declaration: the roots, and a fork of a root for each group it serves and replica. Refused when the bound is
    below one, and as `form` refuses; `formed` is the groups and roots already formed for these arguments.

    `contexts` are the shared contexts to build, each of a root and a model: objects giving `root_id`, `root`, `model`, `spec`,
    `shared` and `variants`, as `ensemble.root_contexts` gives them (a context for the review's own model is the root itself, and
    one with no root is the only root's). A replica on a model other than the review's forks from the context of its group's root
    that holds its variant, a root of its own held to that model's context budget, and a root for such a model over that budget
    is refused naming the groups, the model, the figures and the budget. A replica whose variant no context holds is refused;
    with no contexts given every replica forks from its group's root. Each root is priced at its own model's prices
    (`costmodel.PRICES_BY_MODEL`); `prices`, when given, prices every root alike. A root none of whose groups' replicas fork from
    it for the review's own model is not started, priced or written."""
    if isinstance(bound, bool) or not isinstance(bound, int) or bound < 1:
        raise BoundBelowOne(bound)
    formed = formed or form(declaration, catalogue, spec.model)
    by_group = {built.id: built for built in formed.groups}
    by_root = {built.id: built for built in formed.built_roots}
    owned: List[Tuple[Any, str]] = []
    for context in contexts:
        owner = context.root if context.root is not None else (formed.built_roots[0].id if len(formed.built_roots) == 1 else None)
        if owner not in by_root:
            raise ValueError(f"the context {context.root_id} belongs to the root {context.root!r}, which the plan does not hold")
        owned.append((context, owner))
    others = [(context, owner) for context, owner in owned if context.model != spec.model]
    counts = dict(zip(by_group, replica_counts(declaration, [built.units for built in formed.groups], replicas)))
    other_variants = {(owner, variant_id) for context, owner in others for variant_id in context.variants}

    def forks_of(group: str) -> List[str]:
        return [(variants[(replica - 1) % len(variants)] if variants else BASE_VARIANT) for replica in range(1, counts[group] + 1)]

    started = {root.id: any((root.id, variant) not in other_variants for group in root.groups for variant in forks_of(group))
               for root in formed.built_roots}
    budget = formed.budget["tokens"]
    over = [Overrun(built.id, built.units, built.tokens, built.images) for built in formed.groups
            if budget is not None and built.tokens > budget and started[built.root]]
    for context, owner in others:
        limit = context_budget(declaration.budget, context.model)
        if limit is not None and context.shared.tokens > limit:
            root = by_root[owner]
            units = tuple(uid for group in root.groups for uid in by_group[group].units)
            over.append(Overrun(", ".join(root.groups), units, context.shared.tokens, root.images, context.model, limit, owner,
                                root.groups))
    if over:
        raise GroupsOverBudget(over, budget if budget is not None else over[0].limit)
    prompt_for = prompt_for or default_prompt(declaration)
    root_prices = prices or cm.prices_for(spec.model)
    prices_of: Dict[str, cm.Prices] = {root.id: root_prices for root in formed.built_roots}
    for context, _ in others:
        prices_of[context.root_id] = prices or cm.prices_for(context.model)
    groups = [Group(built.id, built.units, built.needs, built.expected_output_tokens, counts[built.id], built.root, built.images,
                    built.tokens, built.extract) for built in formed.groups]
    nodes: List[Node] = []
    per_node: Dict[str, Dict[str, float]] = {}
    for root in formed.built_roots:
        if not started[root.id]:
            continue
        nodes.append(Node(root.id, ROOT, None, None, None, 1, None, (), root.shared.prefix_sha, root.shared.prefix_sha))
        per_node[root.id] = {"cost_usd": cm.root_cost(root_prices, root.tokens), "wall_s": timing.seconds(1, cm.ACK_TOKENS)}
    parent_of: Dict[Tuple[str, str], str] = {}
    held: Dict[str, int] = {root.id: root.tokens for root in formed.built_roots}
    for context, owner in others:
        for variant_id in context.variants:
            parent_of[(owner, variant_id)] = context.root_id
        held[context.root_id] = context.shared.tokens
        nodes.append(Node(context.root_id, ROOT, None, None, None, 1, None, (), context.shared.prefix_sha,
                          context.shared.prefix_sha))
        per_node[context.root_id] = {"cost_usd": cm.root_cost(prices_of[context.root_id], context.shared.tokens),
                                     "wall_s": timing.seconds(1, cm.ACK_TOKENS)}
    held_variants = {(owner, variant_id) for context, owner in owned for variant_id in context.variants}
    durations: List[float] = []
    for group in groups:
        for replica, variant in enumerate(forks_of(group.id), 1):
            prompt = prompt_for(group.units, variant)
            if contexts and (group.root, variant) not in held_variants:
                raise ValueError(f"the variant {variant!r} forks from no shared context of the root {group.root} that serves the group "
                                 f"{group.id}; its contexts hold {sorted(name for owner, name in held_variants if owner == group.root)}")
            parent = parent_of.get((group.root, variant), group.root)
            node = Node(f"{group.id}.r{replica}.a1", UNIT, parent, group.id, replica, 1, variant, group.units,
                        by_root[group.root].shared.prefix_sha, messages.sha256(messages.prompt_message(prompt)))
            nodes.append(node)
            seconds = timing.seconds(calls_per_fork, group.expected_output_tokens)
            per_node[node.id] = {"cost_usd": cm.fork_cost(prices_of[parent], held[parent], len(prompt), group.expected_output_tokens,
                                                          calls_per_fork), "wall_s": seconds}
            durations.append(seconds)
    wall = max(entry["wall_s"] for key, entry in per_node.items() if key == ROOT or key.startswith(ROOT + ".")) \
        + cm.makespan(durations, bound)
    target = declaration.budget.wall_s
    cost = sum(entry["cost_usd"] for entry in per_node.values())
    written = sum(root.tokens for root in formed.built_roots if started[root.id]) + sum(context.shared.tokens for context, _ in others)
    predicted = {"cost_usd": round(cost, 6), "wall_s": round(wall, 3), "tokens_written": written,
                 "wall_target_s": target, "meets_wall_target": None if target is None else wall <= target,
                 "cost_ceiling_usd": declaration.budget.usd,
                 "within_cost_ceiling": None if declaration.budget.usd is None else cost <= declaration.budget.usd,
                 "per_node": {key: {k: round(v, 6) for k, v in entry.items()} for key, entry in per_node.items()}}
    sizes = {a.name: a.tokens for a in catalogue.artefacts}
    written_roots: List[Tuple[Any, BuiltRoot]] = [(root_prices, root) for root in formed.built_roots if started[root.id]]
    written_roots += [(prices_of[context.root_id], by_root[owner]) for context, owner in others]
    saving = 0.0
    for price in {id(price): price for price, _ in written_roots}.values():
        holders = {name: sum(1 for p, root in written_roots if p is price and name in root.needs) for name in sizes}
        saving += cm.shared_write_saving(price, sizes, holders)
    threshold = declaration.budget.tree_saving_usd
    tree = {"saving_usd": round(saving, 6), "threshold_usd": threshold, "worth_building": saving >= threshold,
            "kept": "flat"}
    root_records = tuple(Root(root.id, root.groups, root.needs, root.images, root.tokens, root.shared.prefix_sha, started[root.id])
                         for root in formed.built_roots)
    return Plan(tuple(groups), tuple(nodes), spec.as_dict(), spec.digest, formed.shared.as_dict(), tuple(variants), bound,
                root_prices.as_dict(), timing.as_dict(), calls_per_fork, predicted, tree, cli_version, tool_commit, root_records,
                tuple({"root_id": context.root_id, "root": owner, "groups": list(by_root[owner].groups), "model": context.model,
                       "spec": context.spec.as_dict(), "spec_digest": context.spec.digest, "prices": prices_of[context.root_id].as_dict(),
                       "prefix_sha": context.shared.prefix_sha, "variants": list(context.variants)} for context, owner in others),
                tuple(declaration.added_during_round), dict(formed.budget))
