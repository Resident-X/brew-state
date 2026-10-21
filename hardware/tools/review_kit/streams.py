#!/usr/bin/env python3
"""Read a recorded session: the stream the agent command line printed, or the transcript Claude Code wrote for it.

The stream checks and the telemetry work over a `Stream`, which this module
reads from either record and from the reduced form the reduction tool writes.
No clock, no process and no network is used.

The reduced form (what is committed as a fixture) is one JSON record per line,
and the records are of these types; every other record type is dropped by the
reduction.

- `system` with subtype `init`, the start report: `session_id`, `cwd`, `tools`,
  `mcp_servers`, `model`, `permissionMode`, `slash_commands`, `skills`,
  `plugins`, `claude_code_version`, `output_style`, `additional_directories`.
- `assistant`, one model call or one block of it: `session_id` (a transcript
  record gives `sessionId`), `message` holding `id`, `model`, `content` (blocks
  of type `text`, `thinking`, `redacted_thinking` or `tool_use`) and `usage`.
  Blocks that arrive in several records with one `message.id` are one call.
- `user`: `message.content` is a string or blocks. A `tool_result` block gives
  `tool_use_id`, `is_error` and its `content`; any other block is part of a
  message the session was sent.
- `result`, the result report: `is_error`, `result`, `structured_output`,
  `total_cost_usd`, `duration_ms`, `duration_api_ms`, `num_turns`, `usage`,
  `session_id`. The cost, API time and turns are cumulative over the session
  the report's session was forked from; the usage is the session's own.
- `api-request-shape`, which only a transcript holds: `sessionId`,
  `shapeHash` and `shape`, where `shape.system` lists `{"type": "text",
  "text": ...}` blocks and `shape.tools` lists tool names. The start report
  carries no system prompt, so the system prompt a session used is read from
  this record, which the reduction takes from the transcript found by the
  session's identifier (`transcripts.find_transcript`) and writes next to the stream.

An image block is `{"type": "image", "source": {"type": "base64",
"media_type": ..., "bytes": N}}`: the bytes are replaced by their decoded size.
A text longer than the reduction's limit keeps its start, then any header line
of the form `=== name ===` it held (a document or image the message carries),
then `[N characters omitted]`. An absolute path of the recording machine is
replaced by a path relative to the folder the recording was made in, or by
`<path>/<file name>`.
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

#: The tool whose uses open an artefact.
OPEN_TOOL = "Read"
#: A header line naming a document or an image a message carries: `=== docs/a.md (section: x) ===` or `=== image: v.png ===`.
HEADER = re.compile(r"^=== (?:image: )?(?P<name>.+?)(?: \(.*\))? ===$", re.M)


@dataclass
class Call:
    """One model call, its blocks gathered from every record that carried its message identifier."""

    id: str
    blocks: List[Dict[str, Any]] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)

    @property
    def tool_uses(self) -> List[Dict[str, Any]]:
        return [block for block in self.blocks if block.get("type") == "tool_use"]

    @property
    def text(self) -> str:
        return "".join(block.get("text", "") for block in self.blocks if block.get("type") == "text"
                       and isinstance(block.get("text"), str))


@dataclass(frozen=True)
class Open:
    """An artefact a session opened with a tool, and whether the tool reported the open failed."""

    path: str
    failed: bool


@dataclass
class Stream:
    """One session as its record shows it. `malformed` lists every line that could not be read, so a check can say so."""

    session_id: str = ""
    start: Dict[str, Any] = field(default_factory=dict)
    calls: List[Call] = field(default_factory=list)
    messages: List[List[Dict[str, Any]]] = field(default_factory=list)
    tool_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    system: Optional[Tuple[str, ...]] = None
    shape_hash: str = ""
    tools: Optional[Tuple[str, ...]] = None
    malformed: List[str] = field(default_factory=list)

    @property
    def system_prompt(self) -> Optional[str]:
        """The system prompt as one text, or None when the record holds none (a stream alone carries none)."""
        return None if self.system is None else "\n\n".join(self.system)

    @property
    def first_call_read(self) -> Optional[int]:
        """The tokens the first call read from the cache, or None when the session made no call or reported none."""
        if not self.calls:
            return None
        found = self.calls[0].usage.get("cache_read_input_tokens")
        return found if isinstance(found, int) and not isinstance(found, bool) else None

    def opens(self, tool: str = OPEN_TOOL) -> List[Open]:
        """The artefacts opened with the tool, in order, each with whether its result was an error."""
        found = []
        for call in self.calls:
            for use in call.tool_uses:
                if use.get("name") != tool:
                    continue
                path = (use.get("input") or {}).get("file_path") if isinstance(use.get("input"), dict) else None
                if isinstance(path, str):
                    failed = (self.tool_results.get(use.get("id") or "") or {}).get("is_error") is True
                    found.append(Open(path, failed))
        return found


def records(text: str) -> Iterator[Tuple[int, Any]]:
    """Each line of a recorded stream as (line number, parsed value); a line that is not JSON gives (number, None)."""
    for number, line in enumerate(text.split("\n"), 1):  # never splitlines: U+2028 is raw inside a JSON event
        if not line.strip():
            continue
        try:
            yield number, json.loads(line)
        except (ValueError, RecursionError):
            yield number, None


def read_stream(text: str) -> Stream:
    """The session a recorded stream, transcript or reduced file shows. A record of a type the checks do not read is
    passed over; a line that is not a JSON object, or an assistant record with no content list, is listed as malformed."""
    stream = Stream()
    by_id: Dict[str, Call] = {}
    for number, event in records(text):
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            stream.malformed.append(f"line {number} is not a JSON object with a string type")
            continue
        kind = event["type"]
        found = event.get("session_id") or event.get("sessionId")
        if isinstance(found, str) and found and not stream.session_id:
            stream.session_id = found
        if kind == "system" and event.get("subtype") == "init":
            stream.start = event
        elif kind == "assistant":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                stream.malformed.append(f"line {number} is an assistant record with no message.content list")
                continue
            ident = message.get("id") if isinstance(message.get("id"), str) else f"unnamed-{number}"
            call = by_id.get(ident)
            if call is None:
                call = by_id[ident] = Call(ident)
                stream.calls.append(call)
            call.blocks.extend(block for block in content if isinstance(block, dict))
            if isinstance(message.get("usage"), dict):
                call.usage = message["usage"]
        elif kind == "user":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
            if not isinstance(blocks, list):
                stream.malformed.append(f"line {number} is a user record with no message.content")
                continue
            sent = []
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_result" and isinstance(block.get("tool_use_id"), str):
                    stream.tool_results[block["tool_use_id"]] = block
                elif isinstance(block, dict):
                    sent.append(block)
            if sent:
                stream.messages.append(sent)
        elif kind == "result":
            stream.result = event
        elif kind == "api-request-shape":
            shape = event.get("shape")
            system = shape.get("system") if isinstance(shape, dict) else None
            if isinstance(system, list):
                stream.system = tuple(item["text"] for item in system if isinstance(item, dict)
                                      and isinstance(item.get("text"), str))
                stream.shape_hash = event.get("shapeHash") if isinstance(event.get("shapeHash"), str) else ""
                tools = shape.get("tools")
                if isinstance(tools, list):
                    stream.tools = tuple(tool if isinstance(tool, str) else str((tool or {}).get("name")) for tool in tools)
    return stream


def read_stream_file(path: str) -> Stream:
    with open(path, encoding="utf-8") as handle:
        return read_stream(handle.read())


def names_in_message(blocks: Iterable[Dict[str, Any]]) -> List[str]:
    """The documents and images a message carries, by the last component of the name its header lines give."""
    found = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            found.extend(match.group("name").rsplit("/", 1)[-1] for match in HEADER.finditer(block["text"]))
    return found


def held_names(stream: Stream) -> List[str]:
    """Every document and image named in the messages the session was sent."""
    return [name for message in stream.messages for name in names_in_message(message)]


def artefact_name(path: str) -> str:
    """The name an artefact is told apart by: the last component of its path."""
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def lineage_written(lineage: Sequence[Stream]) -> int:
    """The tokens a chain of sessions wrote to the cache, root first: the prefix a fork of the last one should read."""
    total = 0
    for stream in lineage:
        for call in stream.calls:
            written = call.usage.get("cache_creation_input_tokens")
            if isinstance(written, int) and not isinstance(written, bool):
                total += written
    return total
