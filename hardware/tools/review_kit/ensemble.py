"""Replicas: how many a unit has, how their prompts differ, and the shared context of a replica on another model.

A replica is a fork of the same shared context whose prompt differs from the others in
the order of the items, the order of the views and its framing, one of which is a
terse hunt for failures. The variants are declared as data, and the replica numbered n
of a group takes the variants in turn. The number of replicas follows the unit's
stakes, and a round flag overrides it. A variant may name a model other than the
review's; the cache cannot be shared across models, so that replica has a shared
context and a session specification of its own.

Everything here is a function of its arguments: a second build of a prompt is the
same bytes.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import decl, messages, planner
from . import session as sess

GIVEN, REVERSED, SHUFFLED = "given", "reversed", "shuffled"
ORDERS = (GIVEN, REVERSED, SHUFFLED)
TERSE_FRAMING = ("Hunt for failures. Look first for what is wrong, state a failure as soon as the evidence shows it, and keep "
                 "a pass to a few words; judge every item all the same.")
#: The replicas a unit has by its stakes, unless a round flag says otherwise.
BY_STAKES = {"low": 1, "normal": 2, "high": 3}


class PolicyError(ValueError):
    """A replica policy or round flag that cannot be used; the text says what is wrong and what to give."""


@dataclass(frozen=True)
class Variant:
    """How one replica's prompt differs: the order of the items, the order of the views (each `given`, `reversed` or
    `shuffled`, the last by `seed`), an added framing, whether it is the terse hunt for failures, and the model it runs on
    when that is not the review's."""

    id: str
    item_order: str = GIVEN
    view_order: str = GIVEN
    framing: str = ""
    terse: bool = False
    seed: int = 0
    model: Optional[str] = None

    @property
    def opening(self) -> str:
        return "\n\n".join(part for part in (TERSE_FRAMING if self.terse else "", self.framing.strip()) if part)


#: The two variants a review has unless it declares its own: the prompt as declared, and the terse hunt for failures
#: with the items and views the other way round.
DEFAULT_VARIANTS = (Variant("full"), Variant("hunt", REVERSED, REVERSED, terse=True))


@dataclass(frozen=True)
class Policy:
    variants: Tuple[Variant, ...] = DEFAULT_VARIANTS
    by_stakes: Tuple[Tuple[str, int], ...] = tuple(BY_STAKES.items())

    def variant(self, variant_id: str) -> Variant:
        for variant in self.variants:
            if variant.id == variant_id:
                return variant
        raise PolicyError(f"no variant {variant_id!r} is declared; the variants are {[v.id for v in self.variants]}")

    @property
    def ids(self) -> List[str]:
        return [variant.id for variant in self.variants]


def whole_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def parse_policy(raw: Any, where: str = "the replica policy") -> Policy:
    """A policy from plain data: `{"variants": [{"id", "item_order", "view_order", "framing", "terse", "seed", "model"}],
    "replicas": {"low": n, "normal": n, "high": n}}`. Every problem is named; a missing part takes its default."""
    if raw is None:
        return Policy()
    if not isinstance(raw, dict):
        raise PolicyError(f"{where} is not a mapping")
    problems: List[str] = []
    for key in raw:
        if key not in ("variants", "replicas"):
            problems.append(f"{where} has a key {key!r} it does not take; the keys are ['variants', 'replicas']")
    variants: List[Variant] = []
    declared = raw.get("variants")
    if declared is None:
        variants = list(DEFAULT_VARIANTS)
    elif not isinstance(declared, list) or not declared:
        problems.append(f"{where}'s `variants` is not a non-empty list")
    else:
        names = [field.name for field in dataclasses.fields(Variant)]
        for number, entry in enumerate(declared, 1):
            label = f"{where}'s variant {number}"
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"].strip():
                problems.append(f"{label} is not a mapping with an `id`")
                continue
            label = f"{where}'s variant {entry['id']!r}"
            extra = [key for key in entry if key not in names]
            if extra:
                problems.append(f"{label} has a key {extra[0]!r} it does not take; the keys are {names}")
                continue
            made = Variant(**entry)
            for field, value in (("item_order", made.item_order), ("view_order", made.view_order)):
                if value not in ORDERS:
                    problems.append(f"{label} gives {field} as {value!r}, not one of {list(ORDERS)}")
            if not isinstance(made.framing, str) or not isinstance(made.terse, bool):
                problems.append(f"{label} gives a framing that is not text or a terse that is not true or false")
            if isinstance(made.seed, bool) or not isinstance(made.seed, int):
                problems.append(f"{label} gives a seed that is not a whole number")
            if made.model is not None and (not isinstance(made.model, str) or not made.model.strip()):
                problems.append(f"{label} gives a model that is not a full model id")
            if any(made.id == other.id for other in variants):
                problems.append(f"{label} is declared twice")
            variants.append(made)
    counts = dict(BY_STAKES)
    given = raw.get("replicas", {})
    if not isinstance(given, dict):
        problems.append(f"{where}'s `replicas` is not a mapping of stakes to a number")
    else:
        for stakes, count in given.items():
            if stakes not in decl.STAKES:
                problems.append(f"{where}'s `replicas` names the stakes {stakes!r}, not one of {list(decl.STAKES)}")
            elif not whole_count(count):
                problems.append(f"{where} gives {count!r} replicas for {stakes!r} stakes, not a whole number of one or more")
            else:
                counts[stakes] = count
    if problems:
        raise PolicyError("; ".join(problems))
    return Policy(tuple(variants), tuple(counts.items()))


def replica_count(policy: Policy, stakes: str, flag: Optional[int] = None) -> int:
    """The replicas of a unit: the round flag when one is given, else the number the policy gives its stakes."""
    if flag is not None:
        if not whole_count(flag):
            raise PolicyError(f"the round flag gives {flag!r} replicas; give a whole number of one or more")
        return flag
    counts = dict(policy.by_stakes)
    if stakes not in counts:
        raise PolicyError(f"the stakes {stakes!r} are none of {list(counts)}")
    return counts[stakes]


def replicas_by_unit(declaration: decl.Declaration, policy: Policy = Policy(), flag: Optional[int] = None) -> Dict[str, int]:
    """Each unit's replica count, in the form the planner takes; a group takes the most of its units."""
    return {uid: replica_count(policy, unit.stakes, flag) for uid, unit in declaration.units.items()}


# --- Prompts -----------------------------------------------------------------------------------


def ordered(names: Sequence[str], how: str, seed: int, unit: str) -> List[str]:
    """`names` in the order asked for. A shuffle is by the hash of the seed, the unit and the name, so it is the same on
    every machine and every build, and different for different units."""
    if how == REVERSED:
        return list(reversed(names))
    if how == SHUFFLED:
        return sorted(names, key=lambda name: hashlib.sha256(f"{seed}\0{unit}\0{name}".encode("utf-8")).hexdigest())
    if how != GIVEN:
        raise PolicyError(f"the order {how!r} is none of {list(ORDERS)}")
    return list(names)


def views_line(declaration: decl.Declaration, unit_id: str, variant: Variant) -> str:
    """The line that gives a unit's views in this variant's order; empty for the order as declared, which adds nothing to the
    prompt the unit has without replicas."""
    needs = declaration.units[unit_id].needs
    if variant.view_order == GIVEN or len(needs) < 2:
        return ""
    return "Take the views in this order: " + ", ".join(ordered(needs, variant.view_order, variant.seed, unit_id)) + "."


def variant_prompt(declaration: decl.Declaration, units: Sequence[str], variant: Variant,
                   unit_text: Optional[Callable[[str, Optional[Sequence[str]]], str]] = None) -> str:
    """The prompt of a group for one variant: each unit's prompt with its items in the variant's order and its views line,
    one after another as `messages.group_prompt` gives them, under the variant's framing. `unit_text(unit, items)` is the
    unit's own prompt, by default the declared template's."""
    unit_text = unit_text or (lambda uid, items: messages.unit_prompt(declaration, uid, items))
    parts = []
    for uid in units:
        items = ordered(declaration.units[uid].items, variant.item_order, variant.seed, uid)
        text = unit_text(uid, items)
        views = views_line(declaration, uid, variant)
        parts.append(text + ("\n\n" + views if views else ""))
    body = parts[0] if len(parts) == 1 else "\n\n".join(f"## Unit {uid}\n{part}" for uid, part in zip(units, parts))
    opening = variant.opening
    return (opening + "\n\n" + body) if opening else body


def prompt_for(declaration: decl.Declaration, policy: Policy = Policy(),
               unit_text: Optional[Callable[[str, Optional[Sequence[str]]], str]] = None) -> Callable[[Sequence[str], str], str]:
    """The function the planner and scheduler take: a group's units and a variant id to the prompt of that replica."""
    return lambda units, variant_id: variant_prompt(declaration, units, policy.variant(variant_id), unit_text)


# --- A replica on another model ----------------------------------------------------------------


@dataclass(frozen=True)
class Context:
    """One shared context to build: the model it runs on (None for the review's), its session specification, the message
    and prefix hash it holds, the id its root node takes and the variants that fork from it. The cache is per model and
    specification, so contexts of different models share none; `cache_key` is what makes that checkable."""

    model: Optional[str]
    spec: sess.SessionSpec
    shared: messages.SharedContext
    root_id: str
    variants: Tuple[str, ...]

    @property
    def cache_key(self) -> str:
        return messages.sha256(f"{self.spec.digest}\0{self.shared.prefix_sha}")


def contexts(spec: sess.SessionSpec, shared: messages.SharedContext, policy: Policy = Policy(),
             variants: Optional[Sequence[str]] = None) -> List[Context]:
    """The shared contexts a review needs: the review's own, and one for each other model a variant in use runs on, each with
    the specification the review's has but for its model. The review's own comes first and is the root `root`."""
    used = [policy.variant(variant_id) for variant_id in (variants if variants is not None else policy.ids)]
    own = [v.id for v in used if v.model is None or v.model == spec.model]
    found = [Context(spec.model, spec, shared, planner.ROOT, tuple(own))]
    for model in sorted({v.model for v in used if v.model is not None and v.model != spec.model}):
        found.append(Context(model, dataclasses.replace(spec, model=model), shared, f"{planner.ROOT}.{model}",
                             tuple(v.id for v in used if v.model == model)))
    return found


def context_of(found: Sequence[Context], variant_id: str) -> Context:
    """The context a variant's replicas fork from."""
    for context in found:
        if variant_id in context.variants:
            return context
    raise PolicyError(f"no shared context is built for the variant {variant_id!r}")
