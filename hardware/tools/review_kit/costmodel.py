"""The cost and time model of a plan: data, a prediction from it, and a refit from telemetry.

The figures are those measured on the live runs: a call costs 1.7 seconds before
it writes anything, output is written at 134 tokens a second, and a million
tokens cost 0.10 USD read from the cache, 4.37 written to it and 8.95 generated, on the mid-tier model the
runs used. Each model has its own prices, keyed by model id in `PRICES_BY_MODEL`.
They are data, not constants of the code: a plan names the values it used and
whether they were fitted, and `fit` refits them from the figures of earlier runs
given as plain mappings, so this module does not depend on how they were taken.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

MILLION = 1_000_000


@dataclass(frozen=True)
class Prices:
    """USD per million tokens."""

    read: float = 0.10
    write: float = 4.37
    out: float = 8.95
    source: str = "measured"

    def cost(self, read: float, write: float, out: float) -> float:
        return (read * self.read + write * self.write + out * self.out) / MILLION

    def as_dict(self) -> Dict[str, Any]:
        return {"read": self.read, "write": self.write, "out": self.out, "source": self.source}


#: The prices of the small-tier model, fitted by least squares from the 13 sessions of the recorded small-tier layout
#: review run of 2026-10-22 (a root and its twelve forks and repairs: cache read, cache write and generated tokens against
#: the cost each reported); the fit reproduces that run's 1.207 USD total to 0.3 per cent.
HAIKU_PRICES = Prices(read=0.0389, write=1.2552, out=2.5202, source="fitted")

#: The prices of each model the kit knows, by full model id. A model not listed is priced at the default `Prices()`.
PRICES_BY_MODEL: Dict[str, Prices] = {
    "claude-sonnet-5-5": Prices(),
    "claude-haiku-5-5": HAIKU_PRICES,
}


def prices_for(model: Optional[str], table: Mapping[str, Prices] = PRICES_BY_MODEL, default: Optional[Prices] = None) -> Prices:
    """The prices of a model: its entry in the table, else the default."""
    return table.get(model, default or Prices()) if model is not None else (default or Prices())


@dataclass(frozen=True)
class Timing:
    """Seconds per call and output tokens per second."""

    per_call_s: float = 1.7
    tok_per_s: float = 134.0
    source: str = "measured"

    def seconds(self, calls: int, out_tokens: float) -> float:
        return calls * self.per_call_s + out_tokens / self.tok_per_s

    def as_dict(self) -> Dict[str, Any]:
        return {"per_call_s": self.per_call_s, "tok_per_s": self.tok_per_s, "source": self.source}


#: The calls a unit's fork makes: the answer, and the call that returns it through the result schema.
CALLS_PER_FORK = 2
#: The output a shared-context node writes: its acknowledgement.
ACK_TOKENS = 5


def fork_cost(prices: Prices, context_tokens: int, prompt_tokens: int, out_tokens: int, calls: int = CALLS_PER_FORK) -> float:
    """A fork's cost: each call reads the shared context from the cache, the unit's prompt is written once, the answer generated."""
    return prices.cost(calls * context_tokens, prompt_tokens, out_tokens)


def root_cost(prices: Prices, context_tokens: int) -> float:
    return prices.cost(0, context_tokens, ACK_TOKENS)


def makespan(durations: Sequence[float], slots: int) -> float:
    """The time the sessions take when at most `slots` run at once, longest first onto the first free slot."""
    if slots < 1:
        raise ValueError("a bound below one runs no session")
    free = [0.0] * min(slots, max(len(durations), 1))
    for duration in sorted(durations, reverse=True):
        free.sort()
        free[0] += duration
    return max(free)


def hoist_saving(prices: Prices, sizes: Mapping[str, int], calls: Mapping[str, int], needed_by: Mapping[str, Sequence[str]]) -> float:
    """What a tree with the artefacts needed by only some groups held above them would at most save over the flat plan.

    In the flat plan every call of every fork reads every artefact of the shared context, though a group's calls need
    only its own; a tree would not read an artefact for a group that does not need it. The bound is the read price over
    the sum, for each artefact, of its size times the calls of the groups that do not need it. It leaves out the extra
    writes and the extra call a level costs, so it is the most a tree could save.
    """
    total = sum(calls.values())
    saved = 0.0
    for name, size in sizes.items():
        using = sum(calls[group] for group in needed_by.get(name, ()))
        saved += size * (total - using)
    return saved * prices.read / MILLION


# --- Refit -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Fit:
    prices: Prices
    timing: Timing
    #: What was and was not fitted, and why, one line each.
    notes: Tuple[str, ...]

    @property
    def fitted(self) -> bool:
        return self.prices.source == "fitted" or self.timing.source == "fitted"


def solve(matrix: List[List[float]], vector: List[float]) -> Optional[List[float]]:
    """The solution of a small linear system by elimination, None when it is singular or nearly so."""
    size = len(vector)
    rows = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    scale = max((abs(value) for row in matrix for value in row), default=0.0)
    if scale == 0:
        return None
    for column in range(size):
        pivot = max(range(column, size), key=lambda index: abs(rows[index][column]))
        if abs(rows[pivot][column]) < 1e-9 * scale:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for index in range(size):
            if index != column:
                factor = rows[index][column] / rows[column][column]
                rows[index] = [a - factor * b for a, b in zip(rows[index], rows[column])]
    return [rows[index][size] / rows[index][index] for index in range(size)]


def least_squares(rows: Sequence[Sequence[float]], targets: Sequence[float]) -> Optional[List[float]]:
    size = len(rows[0]) if rows else 0
    if size == 0 or len(rows) < size:
        return None
    normal = [[sum(row[i] * row[j] for row in rows) for j in range(size)] for i in range(size)]
    return solve(normal, [sum(row[i] * target for row, target in zip(rows, targets)) for i in range(size)])


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def fit(figures: Sequence[Mapping[str, Any]], prices: Prices = Prices(), timing: Timing = Timing()) -> Fit:
    """The prices and timing refitted from earlier sessions' figures, by least squares.

    Each mapping gives a session's `calls`, `generated`, `cache_read`, `cache_write`, `cost_usd` and `wall_s` (the
    session's own, not cumulative). A part is refitted only when the figures determine it and every fitted value is
    positive; otherwise the value given stays, and the notes say why.
    """
    notes: List[str] = []
    timed = [f for f in figures if all(number(f.get(key)) for key in ("calls", "generated", "wall_s"))]
    costed = [f for f in figures if all(number(f.get(key)) for key in ("cache_read", "cache_write", "generated", "cost_usd"))]
    if len(timed) < len(figures):
        notes.append(f"{len(figures) - len(timed)} sessions lacked calls, generated or wall_s figures and were not used for the timing")
    if len(costed) < len(figures):
        notes.append(f"{len(figures) - len(costed)} sessions lacked token or cost figures and were not used for the prices")
    found = least_squares([[f["calls"], f["generated"]] for f in timed], [f["wall_s"] for f in timed])
    if found is not None and found[0] > 0 and found[1] > 0:
        timing = Timing(round(found[0], 4), round(1 / found[1], 2), "fitted")
        notes.append(f"timing fitted from {len(timed)} sessions")
    else:
        notes.append(f"timing kept: {len(timed)} sessions do not determine a positive call time and output rate")
    found = least_squares([[f["cache_read"] / MILLION, f["cache_write"] / MILLION, f["generated"] / MILLION] for f in costed],
                          [f["cost_usd"] for f in costed])
    if found is not None and all(value > 0 for value in found):
        prices = Prices(round(found[0], 4), round(found[1], 4), round(found[2], 4), "fitted")
        notes.append(f"prices fitted from {len(costed)} sessions")
    else:
        notes.append(f"prices kept: {len(costed)} sessions do not determine three positive prices")
    return Fit(prices, timing, tuple(notes))
