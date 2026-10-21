#!/usr/bin/env python3
"""The contract smoke: seven small probes of the installed agent command line, and the assertions made over their streams.

The kit relies on three facts about the command line that nothing in its own tests can show, because a stub plays
whatever it is told: a fork carries the same system prompt as the session it was forked from, a fork reads its parent's
prefix from the cache, and a fork started with a different result-schema flag than its root, which adds a tool to the
fork alone, reads nothing from the cache. The smoke runs seven probes on two synthetic images, which costs a few cents,
saves their streams, and asserts all three. Run it on demand, and whenever the installed command line's version changes.

    smoke.py --out <folder>

The streams are saved in the folder as the command line printed them, with the specification and message hashes that key
each, ready to be reduced into fixtures. Each check is one line, CHECK | <name> | PASS or FAIL | <detail>, a RESULT line
comes last, and the exit status is 0 when every assertion holds, 1 when one fails, and 2 when the agent command line is
missing or not logged in, which prints a line beginning CANNOT RUN naming the cause and what to do.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import zlib
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "review_kit"

from .executor import CannotRun, ClaudeCliExecutor, Executor, Session, StartReportFailed, clean, require_agent
from .session import Call, SessionSpec, image_block, text_block, user_message
from .transcripts import TranscriptMissing, session_system_prompt

READ_TOOLS = ("Glob", "Grep", "Read")
SCHEMA = json.dumps({"type": "object", "properties": {"kind": {"type": "string", "enum": ["ack", "result"]},
                                                      "answer": {"type": "string"}}, "required": ["kind", "answer"]},
                    sort_keys=True)


class SmokeFailure(Exception):
    """An assertion about the command line's contract does not hold."""


# --- The assertions ----------------------------------------------------------------------------


def same_system(parent_system: str, fork_system: str) -> Optional[str]:
    """Why a fork's system prompt is not its parent's, or None when it is."""
    if parent_system == fork_system:
        return None
    return (f"the fork's system prompt ({len(fork_system)} characters) is not its parent's ({len(parent_system)} "
            "characters); a fork must carry the system prompt its root was started with")


def cache_miss(parent: Session, fork: Session) -> Optional[str]:
    """Why the fork's first call did not read its parent's prefix from the cache, with both figures, or None when it did."""
    held, read = parent.prefix_tokens, fork.first_read
    if held is None or read is None:
        return "the parent or the fork made no model call, so what the fork read from the cache cannot be told"
    if read < held:
        return f"the fork's first call read {read} tokens from the cache, below the {held} its parent's prefix holds"
    return None


def assert_same_system(parent_system: str, fork_system: str, label: str) -> None:
    why = same_system(parent_system, fork_system)
    if why:
        raise SmokeFailure(f"{label}: {why}")


def assert_prefix_read(parent: Session, fork: Session, label: str) -> None:
    why = cache_miss(parent, fork)
    if why:
        raise SmokeFailure(f"{label}: {why}")


def assert_cache_miss_flagged(parent: Session, fork: Session, label: str) -> None:
    """The check must flag this fork: it was started with a result-schema flag its root lacked and read nothing."""
    if cache_miss(parent, fork) is None:
        raise SmokeFailure(f"{label}: the fork whose result-schema flag differs from its root's was not flagged as a cache "
                           f"miss (it read {fork.first_read} tokens against a prefix of {parent.prefix_tokens}); the check "
                           "cannot see the cache break it exists to catch")


# --- The probes --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Probe:
    """One probe: the session it continues (None for a root), the specification it starts from, whether it forks, and the
    message. `miss` marks the probe the cache check must flag, `same_spec` that its fork must read the parent's prefix."""

    name: str
    parent: Optional[str]
    schema: bool
    extra_tools: Tuple[str, ...]
    message: str
    miss: bool = False
    same_spec: bool = False


def png(width: int, height: int, shade: int) -> bytes:
    """A small valid greyscale PNG, a gradient: a synthetic image for a probe."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + bytes((shade + x * 255 // max(width - 1, 1)) % 256 for x in range(width)) for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def root_message(token: str, schema: bool) -> str:
    answer = f"answer kind ack, answer {token}" if schema else f"Your whole answer is the single token {token}"
    text = ("The material below is held for later sessions that continue from this one. Take it in; do not judge it, open "
            f"nothing, call no tool other than the answer. {answer}.\n\n=== note.txt ===\nProbe fixture. The two images are "
            "synthetic gradients; the first is darker than the second.\n")
    blocks = [text_block(text)]
    for name, shade in (("first.png", 0), ("second.png", 128)):
        blocks += [text_block(f"=== image: {name} ==="), image_block(png(160, 120, shade))]
    return user_message(blocks)


def question(schema: bool) -> str:
    ask = "How many images were you given in this conversation? Answer in one sentence."
    return user_message([text_block(ask + (" Answer kind result." if schema else ""))])


def node_message() -> str:
    return user_message([text_block("One more note for the sessions that continue from here: the images are gradients. "
                                    "Take it in; call no tool other than the answer; answer kind ack, answer NODE-READY.")])


PROBES: Tuple[Probe, ...] = (
    Probe("p1", None, False, (), root_message("ROOT-READY", False)),
    Probe("p2", "p1", True, (), question(True), miss=True),
    Probe("p3", "p1", False, ("WebFetch",), question(False)),
    Probe("p4", None, True, (), root_message("ROOT-READY", True)),
    Probe("p5", "p4", True, (), question(True), same_spec=True),
    Probe("p6", "p4", True, (), node_message(), same_spec=True),
    Probe("p7", "p6", True, (), question(True), same_spec=True),
)


def spec_for(probe: Probe, cwd: str, model: Optional[str]) -> SessionSpec:
    return SessionSpec(READ_TOOLS + probe.extra_tools, cwd, model=model, json_schema=SCHEMA if probe.schema else None)


def run_probes(make_executor: Callable[[], Executor], cwd: str, model: Optional[str] = None) -> Dict[str, Session]:
    """Run the seven probes, each from its own executor since a probe may differ from its root in the specification, and
    return each probe's session by name. A start report that shows what the specification excludes stops the smoke."""
    sessions: Dict[str, Session] = {}
    for probe in PROBES:
        parent = sessions[probe.parent].id if probe.parent else None
        call = Call(spec_for(probe, cwd, model), probe.message, parent=parent, fork=parent is not None, label=probe.name)
        outcome = make_executor().run(call)
        if outcome.kind != "ok":
            raise SmokeFailure(f"probe {probe.name} returned {outcome.kind}: {outcome.said()}")
        sessions[probe.name] = outcome.session
    return sessions


def checks(sessions: Dict[str, Session], systems: Dict[str, str]) -> List[Tuple[str, bool, str]]:
    """The smoke's assertions over the probes' sessions and the system prompts read from their transcripts, as
    (name, held, detail) in order: each fork's system prompt equals its parent's, each fork started from its parent's
    specification reads the prefix from the cache, and the fork whose result-schema flag differs is flagged."""
    found: List[Tuple[str, bool, str]] = []

    def record(name: str, assertion: Callable[[], None]) -> None:
        try:
            assertion()
            found.append((name, True, "holds"))
        except SmokeFailure as error:
            found.append((name, False, str(error)))

    for probe in PROBES:
        if probe.parent is None:
            continue
        parent = sessions[probe.parent]
        if probe.name in systems and probe.parent in systems:
            record(f"system prompt {probe.name} = {probe.parent}",
                   lambda probe=probe: assert_same_system(systems[probe.parent], systems[probe.name], probe.name))
        if probe.same_spec:
            record(f"cache read {probe.name}",
                   lambda probe=probe, parent=parent: assert_prefix_read(parent, sessions[probe.name], probe.name))
        if probe.miss:
            record(f"cache miss flagged {probe.name}",
                   lambda probe=probe, parent=parent: assert_cache_miss_flagged(parent, sessions[probe.name], probe.name))
    return found


def system_prompts(sessions: Dict[str, Session], cwd: str, root: Optional[str] = None) -> Dict[str, str]:
    """The system prompt each probe used, read from the transcript Claude Code wrote for its session."""
    return {name: session_system_prompt(session.id, cwd, root) for name, session in sessions.items()}


def report_lines(results: Sequence[Tuple[str, bool, str]], version: str) -> List[str]:
    lines = [f"CHECK | {clean(name)} | {'PASS' if held else 'FAIL'} | {clean(detail)}" for name, held, detail in results]
    failed = [name for name, held, _ in results if not held]
    lines.append(f"RESULT | {'FAIL' if failed else 'PASS'} | agent command line version {clean(version)}: "
                 f"{len(results) - len(failed)} of {len(results)} assertions hold")
    return lines


def main(argv: Optional[List[str]] = None, out=sys.stdout, err=sys.stderr, environ: Optional[Dict[str, str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the contract smoke against the installed agent command line.")
    parser.add_argument("--out", required=True, help="the folder the probes' streams are saved in")
    parser.add_argument("--model", help="a full model id for the probes; the command line's default when unset")
    parser.add_argument("--transcripts", help="the folder Claude Code writes its transcripts to, when not the default")
    args = parser.parse_args(argv)
    try:
        program = require_agent(environ)
    except CannotRun as error:
        print(f"CANNOT RUN | {clean(error)}", file=err)
        return 2
    cwd = os.path.join(os.path.abspath(args.out), "work")
    os.makedirs(cwd, exist_ok=True)
    streams = os.path.join(os.path.abspath(args.out), "streams")
    try:
        sessions = run_probes(lambda: ClaudeCliExecutor(program, out=streams), cwd, args.model)
        systems = system_prompts(sessions, cwd, args.transcripts)
    except CannotRun as error:
        print(f"CANNOT RUN | {clean(error)}", file=err)
        return 2
    except (SmokeFailure, StartReportFailed, TranscriptMissing) as error:
        print(f"CHECK | probes | FAIL | {clean(error)}", file=out)
        print("RESULT | FAIL | the probes could not be run to the end; fix the cause above, then run again", file=out)
        return 1
    version = str(next(iter(sessions.values())).start.get("claude_code_version", "unknown"))
    results = checks(sessions, systems)
    print("\n".join(report_lines(results, version)), file=out)
    return 0 if all(held for _, held, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
