"""The planner: units into groups, groups into a flat plan, and the plan record.

Units a caller declares as coupled are in one group. The remaining units are
packed into groups up to the largest single unit's expected output (a coupled
set larger than that stays alone, since its units cannot be parted), so that the
largest group sets the review's time, which is estimated as the cost model gives
it. The plan is flat: one shared context, then one fork per group and replica.
It records what a tree with the artefacts only some groups need held above them
would at most save, and the threshold that saving was compared with, and keeps the
flat plan. A shared context larger than the context budget is refused, naming its
size and the budget, before any session starts.

Replicas and their variants arrive as plain data: a replica count (one number or
one per unit) and the ids of the variants the replicas take in turn. The prompt of
a variant is the ensemble's to supply, through `prompt_for`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from . import catalogue as cat
from . import costmodel as cm
from . import decl, messages
from . import session as sess

ROOT, UNIT, REPAIR = "root", "unit", "repair"
PLAN_VERSION = 1
BASE_VARIANT = "base"


class OverBudget(Exception):
    def __init__(self, size: int, budget: int):
        self.size, self.budget = size, budget
        super().__init__(f"the shared context is {size} tokens, over the review's context budget of {budget} tokens; "
                         "take artefacts out of the units' `needs`, or raise the budget's context_tokens")


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

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "units": list(self.units), "needs": list(self.needs),
                "expected_output_tokens": self.expected_output_tokens, "replicas": self.replicas}


@dataclass(frozen=True)
class Plan:
    """The plan record. Everything in it is plain data and `to_dict` is the JSON the record is written as."""

    groups: Tuple[Group, ...]
    nodes: Tuple[Node, ...]
    spec: Dict[str, Any]
    spec_digest: str
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
    #: The shared contexts built besides the review's own, one for each other model a replica runs on: the root node's id,
    #: the model, the specification and its digest, the prefix hash and the variants that fork from it.
    contexts: Tuple[Dict[str, Any], ...] = ()
    #: The paths the declaration lists as added to the review folder during the round; the folder hash leaves them out.
    added_during_round: Tuple[str, ...] = ()

    @property
    def roots(self) -> List[Node]:
        """The root of every shared context, the review's own first."""
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
                "added_during_round": list(self.added_during_round)}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Plan":
        groups = tuple(Group(g["id"], tuple(g["units"]), tuple(g["needs"]), g["expected_output_tokens"], g["replicas"])
                       for g in raw["groups"])
        return cls(groups, tuple(Node.from_dict(n) for n in raw["nodes"]), raw["spec"], raw["spec_digest"], raw["shared"],
                   tuple(raw["variants"]), raw["bound"], raw["prices"], raw["timing"], raw["calls_per_fork"],
                   raw["predicted"], raw["tree"], raw["cli_version"], raw["tool_commit"],
                   tuple(raw.get("contexts", ())), tuple(raw.get("added_during_round", ())))


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


# --- The plan ----------------------------------------------------------------------------------


def make_plan(declaration: decl.Declaration, catalogue: cat.Catalogue, shared: messages.SharedContext,
              spec: sess.SessionSpec, *, bound: int, cli_version: str, tool_commit: str,
              replicas: Union[int, Mapping[str, int]] = 1, variants: Sequence[str] = (),
              prices: cm.Prices = cm.Prices(), timing: cm.Timing = cm.Timing(), calls_per_fork: int = cm.CALLS_PER_FORK,
              prompt_for: Optional[Callable[[Sequence[str], str], str]] = None, contexts: Sequence[Any] = ()) -> Plan:
    """The flat plan for a declaration: refused when the bound is below one or the shared context is over the budget.

    `contexts` are the shared contexts to build when a replica runs on a model other than the review's: objects giving
    `root_id`, `model`, `spec`, `shared` and `variants`, the review's own first. A group's replica forks from the context
    that holds its variant; with none given every replica forks from the one root."""
    if isinstance(bound, bool) or not isinstance(bound, int) or bound < 1:
        raise BoundBelowOne(bound)
    budget = declaration.budget.context_tokens
    if budget is not None and shared.tokens > budget:
        raise OverBudget(shared.tokens, budget)
    prompt_for = prompt_for or default_prompt(declaration)
    packed = pack(declaration)
    counts = replica_counts(declaration, packed, replicas)
    groups: List[Group] = []
    for number, (units, count) in enumerate(zip(packed, counts), 1):
        needs = sorted({name for u in units for name in declaration.units[u].needs})
        groups.append(Group(f"G{number}", tuple(units), tuple(needs),
                            sum(declaration.units[u].expected_output_tokens for u in units), count))
    root = Node("root", ROOT, None, None, None, 1, None, (), shared.prefix_sha, shared.prefix_sha)
    nodes = [root]
    per_node = {"root": {"cost_usd": cm.root_cost(prices, shared.tokens), "wall_s": timing.seconds(1, cm.ACK_TOKENS)}}
    parent_of: Dict[str, str] = {}
    for context in contexts:
        for variant_id in context.variants:
            parent_of[variant_id] = context.root_id
    for context in list(contexts)[1:]:
        nodes.append(Node(context.root_id, ROOT, None, None, None, 1, None, (), context.shared.prefix_sha,
                          context.shared.prefix_sha))
        per_node[context.root_id] = {"cost_usd": cm.root_cost(prices, context.shared.tokens),
                                     "wall_s": timing.seconds(1, cm.ACK_TOKENS)}
    durations: List[float] = []
    calls_of: Dict[str, int] = {}
    for group in groups:
        for replica in range(1, group.replicas + 1):
            variant = (variants[(replica - 1) % len(variants)] if variants else BASE_VARIANT)
            prompt = prompt_for(group.units, variant)
            if contexts and variant not in parent_of:
                raise ValueError(f"the variant {variant!r} forks from no shared context; the contexts hold {sorted(parent_of)}")
            node = Node(f"{group.id}.r{replica}.a1", UNIT, parent_of.get(variant, "root"), group.id, replica, 1, variant, group.units,
                        shared.prefix_sha, messages.sha256(messages.prompt_message(prompt)))
            nodes.append(node)
            seconds = timing.seconds(calls_per_fork, group.expected_output_tokens)
            per_node[node.id] = {"cost_usd": cm.fork_cost(prices, shared.tokens, len(prompt), group.expected_output_tokens,
                                                          calls_per_fork), "wall_s": seconds}
            durations.append(seconds)
            calls_of[group.id] = calls_of.get(group.id, 0) + calls_per_fork
    wall = max(entry["wall_s"] for key, entry in per_node.items() if key == "root" or key.startswith("root.")) \
        + cm.makespan(durations, bound)
    target = declaration.budget.wall_s
    cost = sum(entry["cost_usd"] for entry in per_node.values())
    predicted = {"cost_usd": round(cost, 6), "wall_s": round(wall, 3),
                 "wall_target_s": target, "meets_wall_target": None if target is None else wall <= target,
                 "cost_ceiling_usd": declaration.budget.usd,
                 "within_cost_ceiling": None if declaration.budget.usd is None else cost <= declaration.budget.usd,
                 "per_node": {key: {k: round(v, 6) for k, v in entry.items()} for key, entry in per_node.items()}}
    saving = cm.hoist_saving(prices, {a.name: a.tokens for a in catalogue.artefacts}, calls_of,
                             {a.name: [g.id for g in groups if a.name in g.needs] for a in catalogue.artefacts})
    threshold = declaration.budget.tree_saving_usd
    tree = {"saving_usd": round(saving, 6), "threshold_usd": threshold, "worth_building": saving >= threshold,
            "kept": "flat"}
    return Plan(tuple(groups), tuple(nodes), spec.as_dict(), spec.digest, shared.as_dict(), tuple(variants), bound,
                prices.as_dict(), timing.as_dict(), calls_per_fork, predicted, tree, cli_version, tool_commit,
                tuple({"root_id": context.root_id, "model": context.model, "spec": context.spec.as_dict(),
                       "spec_digest": context.spec.digest, "prefix_sha": context.shared.prefix_sha,
                       "variants": list(context.variants)} for context in list(contexts)[1:]),
                tuple(declaration.added_during_round))
