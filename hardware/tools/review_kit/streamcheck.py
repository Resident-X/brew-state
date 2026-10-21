#!/usr/bin/env python3
"""Checks over a recorded session: the shape of a shared-context node, a cache miss, a differing system prompt, the
artefacts a unit opened again, and the citations that rest on a view the unit never had.

Every check is pure over `streams.Stream` values and returns what it found as
`Flag`s, each naming the session or row it is about and giving the figures or
text that make it so; an empty list is a pass. The recorded streams the checks
are held to are fixtures made from what ran.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from . import streams

#: The tool a session answers through when it is given a result schema.
SCHEMA_TOOL = "StructuredOutput"
#: What a citation of a view looks like in a cell: a file name ending in an image extension.
VIEW_NAME = re.compile(r"[A-Za-z0-9_+\-][A-Za-z0-9_.+\-]*\.(?:png|jpg|jpeg|svg)")


@dataclass(frozen=True)
class Flag:
    """One thing a check found: which check, about what, and the figures or text that show it."""

    check: str
    subject: str
    detail: str

    def __str__(self) -> str:
        return f"{self.subject}: {self.detail}"


def clip(text: str, width: int = 80) -> str:
    one = " ".join(text.split())
    return one if len(one) <= width else one[:width] + "..."


# --- A shared-context node ---------------------------------------------------------------------


def acknowledges(call: streams.Call, ack: str, schema_tool: str = SCHEMA_TOOL) -> bool:
    """Whether the call's whole answer is the acknowledgement, as its text or as a value of the schema tool's input."""
    texts = [block["text"].strip() for block in call.blocks
             if block.get("type") == "text" and isinstance(block.get("text"), str) and block["text"].strip()]
    uses = call.tool_uses
    if texts and not uses:
        return texts == [ack]
    if uses and not texts:
        return len(uses) == 1 and uses[0].get("name") == schema_tool and isinstance(uses[0].get("input"), dict) and any(
            isinstance(value, str) and value.strip() == ack for value in uses[0]["input"].values())
    return False


def node_shape(stream: streams.Stream, ack: str, schema_tool: str = SCHEMA_TOOL) -> List[Flag]:
    """Why a session is not a shared-context node: it made other than one model call, used a tool other than the
    acknowledgement the schema asks for, wrote a text other than the acknowledgement, carried a thinking block with text
    or a redacted one, or reported an error."""
    who = stream.session_id or "session"
    found = []

    def flag(detail: str) -> None:
        found.append(Flag("node-shape", who, detail))

    if len(stream.calls) != 1:
        used = Counter(use.get("name") for call in stream.calls for use in call.tool_uses)
        narrated = sum(1 for call in stream.calls if call.text.strip())
        flag(f"made {len(stream.calls)} model calls, not one"
             + (f", using {', '.join(f'{name} {count} times' for name, count in sorted(used.items(), key=str))}" if used else "")
             + (f", and wrote text in {narrated} of them" if narrated else ""))
    other_tools = sorted({str(use.get("name")) for call in stream.calls for use in call.tool_uses} - {schema_tool})
    if other_tools:
        flag(f"used the {', '.join(other_tools)} tool{'s' if len(other_tools) > 1 else ''}, and a node may use no tool "
             "but the acknowledgement")
    for call in stream.calls:
        for block in call.blocks:
            if block.get("type") == "thinking" and isinstance(block.get("thinking"), str) and block["thinking"].strip():
                flag(f"carries a thinking block with text: {clip(block['thinking'])!r}")
            elif block.get("type") == "redacted_thinking":
                flag("carries a redacted thinking block")
    if len(stream.calls) == 1 and not other_tools and not acknowledges(stream.calls[0], ack, schema_tool):
        flag(f"answered {clip(stream.calls[0].text) or 'no text'!r} and not the acknowledgement {ack!r}")
    if not stream.calls:
        flag("made no model call")
    if stream.result is not None and stream.result.get("is_error") is True:
        flag("reported an error result")
    for problem in stream.malformed:
        flag(f"has a record that could not be read: {problem}")
    return found


# --- The cache ---------------------------------------------------------------------------------


def prefix_miss(fork: streams.Stream, prefix_tokens: int) -> Optional[Flag]:
    """A fork whose first call read fewer tokens from the cache than the prefix it was forked from holds. The prefix is
    what the chain of sessions above it wrote to the cache (`streams.lineage_written`)."""
    who = fork.session_id or "fork"
    read = fork.first_call_read
    if read is None:
        return Flag("prefix-miss", who, "made no call that reports a cache read, so it cannot be shown to read the prefix")
    if read < prefix_tokens:
        return Flag("prefix-miss", who, f"first call read {read} tokens from the cache, below the parent's prefix of "
                    f"{prefix_tokens} tokens, so {prefix_tokens - read} tokens of it were written again")
    return None


# --- The system prompt -------------------------------------------------------------------------


def digest(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


def first_difference(left: str, right: str) -> str:
    at = next((i for i, (a, b) in enumerate(zip(left, right)) if a != b), min(len(left), len(right)))
    return f"they first differ at character {at}: {clip(left[at:at + 60])!r} against {clip(right[at:at + 60])!r}"


def same_system(sessions: Mapping[str, streams.Stream], parents: Optional[Mapping[str, str]] = None,
                appended: Optional[str] = None) -> List[Flag]:
    """The sessions of one review must carry one system prompt. Flagged: a session whose record holds none, a fork
    whose prompt differs from its parent's, any session whose prompt differs from the first session's, and, when the
    appended prompt the specification names is given, a session whose prompt does not end with it."""
    parents = parents or {}
    found: List[Flag] = []
    prompts: Dict[str, str] = {}
    for name, stream in sessions.items():
        if stream.system_prompt is None:
            found.append(Flag("system-prompt", name, "its record holds no system prompt, so it cannot be compared"))
        else:
            prompts[name] = stream.system_prompt
    for name, parent in parents.items():
        if name in prompts and parent in prompts and prompts[name] != prompts[parent]:
            found.append(Flag("system-prompt", name, f"its system prompt differs from its parent {parent}'s "
                              f"({digest(prompts[name])} against {digest(prompts[parent])}); "
                              + first_difference(prompts[parent], prompts[name])))
    if prompts:
        first = next(iter(prompts))
        for name, prompt in prompts.items():
            if prompt != prompts[first] and parents.get(name) != first and name != first:
                found.append(Flag("system-prompt", name, f"its system prompt differs from {first}'s "
                                  f"({digest(prompt)} against {digest(prompts[first])}); "
                                  + first_difference(prompts[first], prompt)))
    if appended is not None:
        for name, prompt in prompts.items():
            if not prompt.rstrip().endswith(appended.strip()):
                tail = prompt.rstrip()[-len(appended.strip()):] if appended.strip() else ""
                found.append(Flag("system-prompt", name, "its system prompt does not end with the appended prompt the "
                                  f"specification names; it ends {clip(tail, 120)!r}, not {clip(appended.strip(), 120)!r}"))
    return found


# --- Artefacts opened again --------------------------------------------------------------------


@dataclass
class Opens:
    """How many opens of an artefact the prefix already held and how many were new, over the sessions counted."""

    total: int = 0
    held: int = 0
    new: int = 0
    repeated: int = 0
    failed: int = 0
    distinct: int = 0
    names: Counter = field(default_factory=Counter)

    def as_dict(self) -> Dict[str, int]:
        return {"total": self.total, "held": self.held, "new": self.new, "repeated": self.repeated,
                "failed": self.failed, "distinct": self.distinct}


def reopens_in_context(sessions: Iterable[streams.Stream], held: Iterable[str],
                       suffixes: Optional[Sequence[str]] = None,
                       key: Callable[[str], str] = streams.artefact_name) -> Opens:
    """The opens the sessions made, split into those of an artefact the prefix held and new ones. An open that the
    tool reported failed is counted as failed and as neither. `repeated` counts the opens of an artefact the same
    session had already opened. `suffixes` limits the count to artefacts whose name ends with one of them; `key` gives
    the name an artefact is told apart by."""
    held_keys = {key(name) for name in held}
    counted = Opens()
    for stream in sessions:
        seen: Set[str] = set()
        for opened in stream.opens():
            name = key(opened.path)
            if suffixes is not None and not name.endswith(tuple(suffixes)):
                continue
            counted.total += 1
            counted.names[name] += 1
            if opened.failed:
                counted.failed += 1
            elif name in held_keys:
                counted.held += 1
            else:
                counted.new += 1
            if name in seen:
                counted.repeated += 1
            seen.add(name)
    counted.distinct = len(counted.names)
    return counted


def cited_views(cell: Any, pattern: "re.Pattern[str]" = VIEW_NAME) -> List[str]:
    """The artefacts a cell cites, by name, in the order first cited."""
    if not isinstance(cell, str):
        return []
    return list(dict.fromkeys(pattern.findall(cell)))


def rests_on_within_context(rows: Iterable[Mapping[str, Any]], held: Iterable[str], opened: Iterable[str],
                            column: str = "Rests on", label: str = "Item",
                            pattern: "re.Pattern[str]" = VIEW_NAME, unit: str = "") -> List[Flag]:
    """A verdict row that cites a view neither the unit's prefix held nor the unit opened is flagged, naming the row. A
    row that is not an object, or whose citation cell is not text, is flagged too, since nothing in it can be checked."""
    known = {streams.artefact_name(name) for name in list(held) + list(opened)}
    prefix = f"{unit} " if unit else ""
    found = []
    for position, row in enumerate(rows):
        if not isinstance(row, Mapping):
            found.append(Flag("foreign-citation", f"{prefix}row {position + 1}", "is not an object, so its citations cannot be read"))
            continue
        name = f"{prefix}row {row.get(label) if isinstance(row.get(label), str) else position + 1}"
        if column in row and not isinstance(row[column], str):
            found.append(Flag("foreign-citation", name, f"holds a {column!r} that is not text, so its citations cannot be read"))
            continue
        for view in cited_views(row.get(column), pattern):
            if view not in known:
                found.append(Flag("foreign-citation", name, f"cites {view}, which neither the unit's prefix held nor the unit opened"))
    return found
