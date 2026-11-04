"""The planner: units into groups, groups into a plan with a root of its own for each, and the plan record.

Units a caller declares as coupled are in one group. A review that states a context budget has its groups formed from one
group per coupled set by merging, over and over, the pair whose merge writes the fewest tokens (the tokens of the artefacts
the two groups' needs share, and the framing one root less holds), never past the budget, ties by declaration order, until
no pair fits; a review that states none has its units packed up to the largest single unit's expected output, as before.
Each group is judged from a root of its own that holds the artefacts every unit needs, the artefacts its own units declare
and the extract of the deterministic check's report for the rules they judge, and nothing another group alone needs; a
group's forks continue its root, so the plan has one root for each group and a fork for each group and replica. A group whose
root is over the context budget, or whose message is over the agent command line's stream limit, is refused, naming the group
and its size, before any session starts.

Replicas and their variants arrive as plain data: a replica count (one number or
one per unit) and the ids of the variants the replicas take in turn. The prompt of
a variant is the ensemble's to supply, through `prompt_for`.
"""

from __future__ import annotations

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
    """A group whose root is over the context budget: its id, its units, its size in tokens and its images."""

    group: str
    units: Tuple[str, ...]
    tokens: int
    images: int

    def line(self, budget: int) -> str:
        who = f"unit {self.units[0]} alone" if len(self.units) == 1 else f"units {', '.join(self.units)}, which the declaration couples"
        return (f"group {self.group} ({who}) holds {self.tokens} tokens in its root, more than the review's context budget of "
                f"{budget} tokens, {self.tokens - budget} over; declare fewer views for the units named in their `needs`, or raise "
                "the budget's context_tokens or context_fraction")


class GroupsOverBudget(Exception):
    """One or more groups hold more than the context budget; every one is named."""

    def __init__(self, overruns: Sequence[Overrun], budget: int):
        self.overruns, self.budget = list(overruns), budget
        self.lines = [overrun.line(budget) for overrun in self.overruns]
        super().__init__("; ".join(self.lines))


class GroupsWithOtherModel(Exception):
    """Groups are each judged from a root of their own, and a replica on another model needs a root per model."""

    def __init__(self, groups: int, models: Sequence[str]):
        self.groups, self.models = groups, list(models)
        super().__init__(f"the review has {groups} groups, each judged from a root of its own, and its replicas run on another model "
                         f"({', '.join(self.models)}); replicas on another model are not built for groups, so give every variant of the "
                         "replica policy the review's model")


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
        whose = f"the root of group {root}'s" if root else "the shared context's"
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
    #: The id of the group's root node, the images and tokens its root holds, the hash of its prefix, and its check extract:
    #: the rules the units declare, the lines of the report held and the (unit, rule) pairs the report holds no line for.
    root: str = "root"
    images: int = 0
    tokens: int = 0
    prefix_sha: str = ""
    extract: Mapping[str, Any] = field(default_factory=lambda: {"rules": [], "lines": 0, "missing": []})

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "units": list(self.units), "needs": list(self.needs),
                "expected_output_tokens": self.expected_output_tokens, "replicas": self.replicas, "root": self.root,
                "images": self.images, "tokens": self.tokens, "prefix_sha": self.prefix_sha,
                "extract": {"rules": list(self.extract["rules"]), "lines": self.extract["lines"],
                            "missing": [dict(entry) for entry in self.extract["missing"]]}}


@dataclass(frozen=True)
class Plan:
    """The plan record. Everything in it is plain data and `to_dict` is the JSON the record is written as."""

    groups: Tuple[Group, ...]
    nodes: Tuple[Node, ...]
    spec: Dict[str, Any]
    spec_digest: str
    #: The shared documents: the artefacts every unit needs, which every group's root holds.
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
    #: The roots built besides the groups' own, one for each other model a replica runs on: the root node's id,
    #: the model, the specification and its digest, the prefix hash and the variants that fork from it.
    contexts: Tuple[Dict[str, Any], ...] = ()
    #: The paths the declaration lists as added to the review folder during the round; the folder hash leaves them out.
    added_during_round: Tuple[str, ...] = ()
    #: The context budget every root is held to, in tokens (None when the declaration states none), the fraction and window
    #: it was taken from when it was stated as a fraction, and the model whose window it is.
    budget: Mapping[str, Any] = field(default_factory=lambda: {"tokens": None, "fraction": None, "window": None, "model": None})

    @property
    def roots(self) -> List[Node]:
        """The root of every group, then the root of each other model's context."""
        return [node for node in self.nodes if node.role == ROOT]

    @property
    def lanes(self) -> List[Node]:
        """The first node of each group and replica: the forks the shared context has."""
        return [node for node in self.nodes if node.role == UNIT]

    @property
    def root(self) -> Node:
        return self.nodes[0]

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
                "nodes": [node.as_dict() for node in self.nodes], "spec": self.spec, "spec_digest": self.spec_digest,
                "shared": self.shared, "variants": list(self.variants), "bound": self.bound, "prices": self.prices,
                "timing": self.timing, "calls_per_fork": self.calls_per_fork, "predicted": self.predicted,
                "tree": self.tree, "cli_version": self.cli_version, "tool_commit": self.tool_commit,
                "contexts": [dict(context) for context in self.contexts],
                "added_during_round": list(self.added_during_round), "budget": dict(self.budget)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Plan":
        groups = tuple(Group(g["id"], tuple(g["units"]), tuple(g["needs"]), g["expected_output_tokens"], g["replicas"], g["root"],
                             g["images"], g["tokens"], g["prefix_sha"], g["extract"]) for g in raw["groups"])
        return cls(groups, tuple(Node.from_dict(n) for n in raw["nodes"]), raw["spec"], raw["spec_digest"], raw["shared"],
                   tuple(raw["variants"]), raw["bound"], raw["prices"], raw["timing"], raw["calls_per_fork"],
                   raw["predicted"], raw["tree"], raw["cli_version"], raw["tool_commit"],
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
    unit's expected output. Deterministic for a declaration."""
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


def check_stream(catalogue: cat.Catalogue, shared: messages.SharedContext, root: Optional[str] = None) -> None:
    """Refuse a context whose message is over the agent command line's stream limit, naming the largest group of artefacts
    and, given it, the group whose root it is."""
    size = messages.stream_size(shared.message)
    if size > messages.STREAM_LIMIT:
        raise OverStreamLimit(size, messages.STREAM_LIMIT, *messages.largest_group(catalogue), root=root)


# --- The groups' roots -------------------------------------------------------------------------


class Sizing:
    """What a root holding a set of artefacts and the extract for a set of rules weighs, by the catalogue's own measures, without
    building its message. `tokens(needs, rules)` equals the `tokens` of the context built from the same."""

    def __init__(self, declaration: decl.Declaration, catalogue: cat.Catalogue):
        self.cost = {a.name: a.tokens + messages.framing_of(a) for a in catalogue.artefacts}
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
    """A group with its root built: the units, the artefacts and extract its root holds, and the context and its size."""

    id: str
    units: Tuple[str, ...]
    needs: Tuple[str, ...]
    expected_output_tokens: int
    root: str
    catalogue: cat.Catalogue
    shared: messages.SharedContext
    extract: Mapping[str, Any]

    @property
    def images(self) -> int:
        return sum(1 for artefact in self.catalogue.artefacts if artefact.kind == "image")

    @property
    def tokens(self) -> int:
        return self.shared.tokens


@dataclass(frozen=True)
class Formed:
    """The groups of a review with their roots built and held to the budget: what the plan is made from and what the
    scheduler starts."""

    groups: Tuple[Built, ...]
    #: The context of the shared documents, the artefacts every unit needs.
    shared: messages.SharedContext
    #: The most tokens a root may hold and what it was taken from.
    budget: Mapping[str, Any]

    @property
    def roots(self) -> Dict[str, messages.SharedContext]:
        """Each group's context by the id of its root node."""
        return {built.root: built.shared for built in self.groups}


def shared_names(declaration: decl.Declaration) -> List[str]:
    """The artefacts every unit needs, by name: the shared documents every group's root holds."""
    sets = [set(unit.needs) for unit in declaration.units.values()]
    return sorted(set.intersection(*sets)) if sets else []


@dataclass
class _Candidate:
    units: List[str]
    needs: set
    rules: set
    cost: int


def form_groups(declaration: decl.Declaration, sizing: Sizing, budget: Optional[int]) -> List[List[str]]:
    """The groups of units. With a budget: one group for each set of units the declaration couples, then the pair whose merged
    root is within the budget and whose merge writes the fewest tokens, which is the tokens of the artefacts their needs share
    and the framing a root less holds, is merged again and again, ties by declaration order, until no pair fits; units the
    declaration couples are never parted. Without one the units are packed by expected output."""
    if budget is None:
        return pack(declaration)
    order = {uid: index for index, uid in enumerate(declaration.units)}
    groups: List[_Candidate] = []
    for units in coupled_sets(declaration):
        needs = {name for uid in units for name in declaration.units[uid].needs}
        rules = {rule for uid in units for rule in declaration.units[uid].check_rules}
        groups.append(_Candidate(list(units), needs, rules, sizing.tokens(needs, rules)))
    while True:
        best: Optional[Tuple[int, int, int, _Candidate]] = None
        for first in range(len(groups)):
            for second in range(first + 1, len(groups)):
                a, b = groups[first], groups[second]
                needs, rules = a.needs | b.needs, a.rules | b.rules
                merged = sizing.tokens(needs, rules)
                saving = a.cost + b.cost - merged
                if merged > budget or saving <= 0:
                    continue
                if best is None or saving > best[0]:
                    best = (saving, first, second, _Candidate(sorted(a.units + b.units, key=order.get), needs, rules, merged))
        if best is None:
            break
        _, first, second, merged_group = best
        groups[first] = merged_group
        del groups[second]
        groups.sort(key=lambda group: order[group.units[0]])
    return [group.units for group in groups]


def build_group(declaration: decl.Declaration, catalogue: cat.Catalogue, sizing: Sizing, units: Sequence[str], number: int,
                total: int, expected_output: int) -> Built:
    """One group's root: the artefacts its units need and the extract of the check's report for the rules they judge."""
    needs = sorted({name for uid in units for name in declaration.units[uid].needs})
    rules = sorted({rule for uid in units for rule in declaration.units[uid].check_rules})
    extra = [sizing.extractor.artefact(rules)] if rules and sizing.extractor is not None else []
    held = catalogue.subset(needs, extra)
    missing = set(sizing.extractor.missing(rules)) if sizing.extractor is not None else set()
    lines = sum(1 for rule, _ in sizing.extractor.lines if rule in rules) if sizing.extractor is not None else 0
    entry = {"rules": rules, "lines": lines,
             "missing": [{"unit": uid, "rule": rule} for uid in units for rule in declaration.units[uid].check_rules if rule in missing]}
    return Built(f"G{number}", tuple(units), tuple(needs), expected_output, ROOT if total == 1 else f"{ROOT}.G{number}", held,
                 messages.shared_context(held), entry)


def form(declaration: decl.Declaration, catalogue: cat.Catalogue, model: Optional[str]) -> Formed:
    """The groups of a review with each root built and held to the context budget, refused before any session starts when the
    budget is a fraction of a window the kit does not declare, when the shared documents are over the budget on their own,
    when any group's root is over it (every one is named), or when a root's message is over the agent command line's limit."""
    budget = context_budget(declaration.budget, model)
    sizing = Sizing(declaration, catalogue)
    shared = messages.shared_context(catalogue.subset(shared_names(declaration)))
    packed = form_groups(declaration, sizing, budget)
    built = tuple(build_group(declaration, catalogue, sizing, units, number, len(packed),
                              sum(declaration.units[uid].expected_output_tokens for uid in units))
                  for number, units in enumerate(packed, 1))
    if budget is not None:
        over = [Overrun(group.id, group.units, group.tokens, group.images) for group in built if group.tokens > budget]
        if shared.tokens > budget:
            raise OverBudget(shared.tokens, budget, over)
        if over:
            raise GroupsOverBudget(over, budget)
    for group in built:
        check_stream(group.catalogue, group.shared, group.id if len(built) > 1 else None)
    window = cm.window_for(model) if declaration.budget.context_fraction is not None else None
    return Formed(built, shared, {"tokens": budget, "fraction": declaration.budget.context_fraction, "window": window, "model": model})


# --- The plan ----------------------------------------------------------------------------------


def make_plan(declaration: decl.Declaration, catalogue: cat.Catalogue, spec: sess.SessionSpec, *, bound: int, cli_version: str,
              tool_commit: str, replicas: Union[int, Mapping[str, int]] = 1, variants: Sequence[str] = (),
              prices: Optional[cm.Prices] = None, timing: cm.Timing = cm.Timing(), calls_per_fork: int = cm.CALLS_PER_FORK,
              prompt_for: Optional[Callable[[Sequence[str], str], str]] = None, contexts: Sequence[Any] = (),
              formed: Optional[Formed] = None) -> Plan:
    """The plan for a declaration: a root for each group and a fork for each group and replica. Refused when the bound is below
    one, and as `form` refuses; `formed` is the groups already formed for these arguments.

    `contexts` are the contexts to build when a replica runs on a model other than the review's: objects giving `root_id`,
    `model`, `spec`, `shared` and `variants`, the review's own first. They are refused for a review of more than one group. A
    group's replica forks from the context that holds its variant; with none given every replica forks from its group's root.
    Each context is priced at its own model's prices (`costmodel.PRICES_BY_MODEL`); `prices`, when given, prices every node
    alike."""
    if isinstance(bound, bool) or not isinstance(bound, int) or bound < 1:
        raise BoundBelowOne(bound)
    formed = formed or form(declaration, catalogue, spec.model)
    if len(contexts) > 1 and len(formed.groups) > 1:
        raise GroupsWithOtherModel(len(formed.groups), [context.model for context in list(contexts)[1:]])
    for context in list(contexts)[1:]:
        limit = context_budget(declaration.budget, context.model)
        if limit is not None and context.shared.tokens > limit:
            only = formed.groups[0]
            raise GroupsOverBudget([Overrun(only.id, only.units, context.shared.tokens, only.images)], limit)
    prompt_for = prompt_for or default_prompt(declaration)
    root_prices = prices or cm.prices_for(spec.model)
    prices_of: Dict[str, cm.Prices] = {built.root: root_prices for built in formed.groups}
    for context in list(contexts)[1:]:
        prices_of[context.root_id] = prices or cm.prices_for(context.model)
    counts = replica_counts(declaration, [built.units for built in formed.groups], replicas)
    groups: List[Group] = []
    nodes: List[Node] = []
    per_node: Dict[str, Dict[str, float]] = {}
    for built, count in zip(formed.groups, counts):
        groups.append(Group(built.id, built.units, built.needs, built.expected_output_tokens, count, built.root, built.images,
                            built.tokens, built.shared.prefix_sha, built.extract))
        nodes.append(Node(built.root, ROOT, None, None, None, 1, None, (), built.shared.prefix_sha, built.shared.prefix_sha))
        per_node[built.root] = {"cost_usd": cm.root_cost(root_prices, built.tokens), "wall_s": timing.seconds(1, cm.ACK_TOKENS)}
    parent_of: Dict[str, str] = {}
    for context in contexts:
        for variant_id in context.variants:
            parent_of[variant_id] = context.root_id
    for context in list(contexts)[1:]:
        nodes.append(Node(context.root_id, ROOT, None, None, None, 1, None, (), context.shared.prefix_sha,
                          context.shared.prefix_sha))
        per_node[context.root_id] = {"cost_usd": cm.root_cost(prices_of[context.root_id], context.shared.tokens),
                                     "wall_s": timing.seconds(1, cm.ACK_TOKENS)}
    root_of = {built.id: built for built in formed.groups}
    durations: List[float] = []
    for group in groups:
        built = root_of[group.id]
        for replica in range(1, group.replicas + 1):
            variant = (variants[(replica - 1) % len(variants)] if variants else BASE_VARIANT)
            prompt = prompt_for(group.units, variant)
            if contexts and variant not in parent_of:
                raise ValueError(f"the variant {variant!r} forks from no shared context; the contexts hold {sorted(parent_of)}")
            parent = parent_of.get(variant, built.root)
            node = Node(f"{group.id}.r{replica}.a1", UNIT, parent, group.id, replica, 1, variant, group.units,
                        built.shared.prefix_sha, messages.sha256(messages.prompt_message(prompt)))
            nodes.append(node)
            seconds = timing.seconds(calls_per_fork, group.expected_output_tokens)
            held = built.tokens if parent == built.root else next(c.shared.tokens for c in contexts if c.root_id == parent)
            per_node[node.id] = {"cost_usd": cm.fork_cost(prices_of[parent], held, len(prompt), group.expected_output_tokens,
                                                          calls_per_fork), "wall_s": seconds}
            durations.append(seconds)
    wall = max(entry["wall_s"] for key, entry in per_node.items() if key == ROOT or key.startswith(ROOT + ".")) \
        + cm.makespan(durations, bound)
    target = declaration.budget.wall_s
    cost = sum(entry["cost_usd"] for entry in per_node.values())
    written = sum(built.tokens for built in formed.groups) + sum(context.shared.tokens for context in list(contexts)[1:])
    predicted = {"cost_usd": round(cost, 6), "wall_s": round(wall, 3), "tokens_written": written,
                 "wall_target_s": target, "meets_wall_target": None if target is None else wall <= target,
                 "cost_ceiling_usd": declaration.budget.usd,
                 "within_cost_ceiling": None if declaration.budget.usd is None else cost <= declaration.budget.usd,
                 "per_node": {key: {k: round(v, 6) for k, v in entry.items()} for key, entry in per_node.items()}}
    holders = {a.name: sum(1 for built in formed.groups if a.name in built.needs) for a in catalogue.artefacts}
    saving = cm.shared_write_saving(root_prices, {a.name: a.tokens for a in catalogue.artefacts}, holders)
    threshold = declaration.budget.tree_saving_usd
    tree = {"saving_usd": round(saving, 6), "threshold_usd": threshold, "worth_building": saving >= threshold,
            "kept": "flat"}
    return Plan(tuple(groups), tuple(nodes), spec.as_dict(), spec.digest, formed.shared.as_dict(), tuple(variants), bound,
                root_prices.as_dict(), timing.as_dict(), calls_per_fork, predicted, tree, cli_version, tool_commit,
                tuple({"root_id": context.root_id, "model": context.model, "spec": context.spec.as_dict(),
                       "spec_digest": context.spec.digest, "prices": prices_of[context.root_id].as_dict(), "prefix_sha": context.shared.prefix_sha,
                       "variants": list(context.variants)} for context in list(contexts)[1:]),
                tuple(declaration.added_during_round), dict(formed.budget))
