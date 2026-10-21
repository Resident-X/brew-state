#!/usr/bin/env python3
"""What a session and a run cost, from the recorded streams.

The agent command line reports a fork's cost and API time cumulatively, as the
session it was forked from already spent them (it restores both from the
parent's saved cost state), and its turns and token usage as its own: in every
recorded stream a fork of one call reports one turn, as its root does. A
session's own figures are therefore its reported cost and time less its
parent's, and its turns and tokens as reported. Its calls are counted by
distinct message identifier, since one call is printed as several records, and
its tokens are split into read from the cache, written to it, fresh and
generated, the generated ones taken from the result report because the records
of a call carry a count that is still growing. A run's figures are built from
the sessions' own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from . import streams

#: The tokens of a call that are read, written and fresh, and where a call reports them.
TOKEN_FIELDS = (("cache_read", "cache_read_input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                ("fresh", "input_tokens"))


class FigureError(ValueError):
    """A session's figures cannot be told; the message names the session and the figure."""


def whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class SessionFigures:
    """One session's own figures, with the cache read of its first call, which the run's duplicate writes are told from."""

    session: str
    parent: Optional[str]
    cost_usd: float
    api_ms: int
    wall_s: float
    turns: int
    calls: int
    tokens: Mapping[str, int]
    first_call_read: Optional[int]

    def as_dict(self) -> Dict[str, Any]:
        return {"session": self.session, "parent": self.parent, "cost_usd": self.cost_usd, "api_ms": self.api_ms,
                "wall_s": self.wall_s, "turns": self.turns, "calls": self.calls, "tokens": dict(self.tokens),
                "first_call_read": self.first_call_read}


def reported(stream: streams.Stream) -> Dict[str, Any]:
    """The figures a stream's result report gives, or a FigureError naming what is missing or of the wrong type."""
    who = stream.session_id or "session"
    result = stream.result
    if result is None:
        raise FigureError(f"{who} has no result report, so its cost, time and turns cannot be told")
    if not number(result.get("total_cost_usd")):
        raise FigureError(f"{who}'s result report gives no total_cost_usd number")
    if not number(result.get("duration_api_ms")):
        raise FigureError(f"{who}'s result report gives no duration_api_ms number")
    if not whole(result.get("num_turns")):
        raise FigureError(f"{who}'s result report gives no num_turns count")
    usage = result.get("usage")
    if not isinstance(usage, dict) or not whole(usage.get("output_tokens")):
        raise FigureError(f"{who}'s result report gives no usage with an output_tokens count")
    return result


def session_figures(stream: streams.Stream, parent: Optional[streams.Stream] = None) -> SessionFigures:
    """The session's own figures. Given the session it was forked from, its cost, API time and turns are its reported
    figures less that session's; a cost or time below its parent's is an error, since the report cannot then be cumulative.
    The turns are the report's own, which does not include the parent's."""
    result = reported(stream)
    cost, api_ms, turns = float(result["total_cost_usd"]), result["duration_api_ms"], result["num_turns"]
    if parent is not None:
        taken = reported(parent)
        for label, mine, theirs in (("cost", cost, taken["total_cost_usd"]), ("API time", api_ms, taken["duration_api_ms"])):
            if mine < theirs:
                raise FigureError(f"{stream.session_id or 'session'}'s reported {label} {mine} is below its parent's "
                                  f"{theirs}, so its own cannot be told")
        cost, api_ms = cost - taken["total_cost_usd"], api_ms - taken["duration_api_ms"]
    tokens: Dict[str, int] = {}
    for label, name in TOKEN_FIELDS:
        tokens[label] = sum(call.usage[name] for call in stream.calls if whole(call.usage.get(name)))
    tokens["generated"] = result["usage"]["output_tokens"]
    wall = result.get("duration_ms")
    return SessionFigures(stream.session_id, parent.session_id if parent is not None else None, round(cost, 6),
                          int(api_ms), round(wall / 1000, 3) if number(wall) else round(api_ms / 1000, 3), int(turns),
                          len(stream.calls), tokens, stream.first_call_read)


@dataclass(frozen=True)
class Prediction:
    """What the plan predicted for the run: its cost and its critical-path time."""

    cost_usd: float
    wall_s: float


@dataclass
class RunFigures:
    sessions: int
    cost_usd: float
    api_ms: int
    turns: int
    calls: int
    tokens: Dict[str, int]
    sharing_ratio: Optional[float]
    duplicate_write_tokens: int
    critical_path_s: float
    predicted: Optional[Dict[str, Optional[float]]] = None
    actual: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"sessions": self.sessions, "cost_usd": self.cost_usd, "api_ms": self.api_ms, "turns": self.turns,
                "calls": self.calls, "tokens": dict(self.tokens), "sharing_ratio": self.sharing_ratio,
                "duplicate_write_tokens": self.duplicate_write_tokens, "critical_path_s": self.critical_path_s,
                "predicted": self.predicted, "actual": dict(self.actual)}


def deviation(actual: float, predicted: float) -> Optional[float]:
    """How far the actual figure is from the predicted, as a fraction of it; None when nothing was predicted."""
    return None if predicted == 0 else round((actual - predicted) / predicted, 4)


def run_figures(figures: Sequence[SessionFigures], prediction: Optional[Prediction] = None) -> RunFigures:
    """A run's figures from its sessions' own.

    The sharing ratio is the tokens read from the cache over those read and those written. The duplicate-write tokens
    are the tokens of a parent's prefix that a fork wrote again because its first call read less than the prefix: a
    fork whose parent is not among the sessions counts none. The critical path is the longest chain of wall time from a
    session with no parent to a session below it, the forks of one parent running together. The cost, time and tokens a
    session reports as its own are summed as given."""
    by_name = {item.session: item for item in figures}
    if len(by_name) != len(figures):
        raise FigureError("two sessions of the run carry one identifier, so their figures cannot be told apart")
    tokens = {label: sum(item.tokens[label] for item in figures) for label in (*(label for label, _ in TOKEN_FIELDS), "generated")}
    written = {item.session: item.tokens["cache_write"] for item in figures}

    def prefix(item: SessionFigures) -> Optional[int]:
        """What the chain above the session wrote to the cache; None when the chain leaves the run."""
        total, parent, seen = 0, item.parent, {item.session}
        while parent is not None:
            if parent not in by_name or parent in seen:
                return None
            total += written[parent]
            seen.add(parent)
            parent = by_name[parent].parent
        return total

    duplicates = 0
    for item in figures:
        above = prefix(item)
        if above is not None and item.parent is not None and item.first_call_read is not None:
            duplicates += max(0, above - item.first_call_read)

    def chain(item: SessionFigures, seen: frozenset = frozenset()) -> float:
        above = by_name.get(item.parent) if item.parent is not None and item.session not in seen else None
        return item.wall_s + (chain(above, seen | {item.session}) if above is not None else 0.0)

    cost = round(sum(item.cost_usd for item in figures), 6)
    critical = round(max((chain(item) for item in figures), default=0.0), 3)
    read_and_written = tokens["cache_read"] + tokens["cache_write"]
    run = RunFigures(len(figures), cost, sum(item.api_ms for item in figures), sum(item.turns for item in figures),
                     sum(item.calls for item in figures), tokens,
                     round(tokens["cache_read"] / read_and_written, 4) if read_and_written else None, duplicates, critical)
    run.actual = {"cost_usd": cost, "wall_s": critical}
    if prediction is not None:
        run.predicted = {"cost_usd": prediction.cost_usd, "wall_s": prediction.wall_s,
                         "cost_deviation": deviation(cost, prediction.cost_usd),
                         "wall_deviation": deviation(critical, prediction.wall_s)}
    return run


def within_report(run_cost: float, reported_cost: float, tolerance: float = 0.02) -> bool:
    """Whether the sum of the sessions' own cost is within the tolerance of the cost the run's report gives."""
    return reported_cost > 0 and round(abs(run_cost - reported_cost), 9) <= round(tolerance * reported_cost, 9)
