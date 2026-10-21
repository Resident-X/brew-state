#!/usr/bin/env python3
"""Reduce a recorded stream or a Claude Code session transcript to the form the stream checks read and the repository may hold.

A recording carries what the repository must not: the image bytes of every view
a session was given, and the absolute paths of the machine it ran on. This tool
writes the reduced form that `streams.py` describes. It replaces each image's
bytes by their size, replaces every absolute path of the recording machine, and
keeps everything the checks read: the start report, each model call with its
blocks and usage, the tool results with their error flag, the result report,
and the system prompt of the session.

    reduce.py <in> <out> [--root DIR]... [--after PARENT] [--transcripts DIR] [--limit N] [--result-limit N]

--root names a folder of the recording machine; a path under it is written
relative to it, and any other absolute path as <path>/<file name>. --after names
the transcript of the session this one was forked from; a fork's transcript
repeats its parent's records, and those are left out. --transcripts names the
folder Claude Code keeps its transcripts under; for a stream, the system prompt
is taken from the transcript found there by the session's identifier, because
the start report carries none. A text longer than --limit characters (1500) keeps
its start, the header lines `=== name ===` it held and a count of what was
omitted; a tool result is limited to --result-limit (400). The output is checked
for a path or image bytes left before it is written, and nothing is written if
one remains.

The exit status is 0 when the reduction is written, 1 when the command refuses
(a limit below one, the input named as the output, a transcript that cannot be
found, an output that would still hold a path or image bytes) and 2 when it
cannot run (a file that cannot be read or written), with a line beginning
REFUSED or CANNOT RUN that says why.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from review_kit import streams  # type: ignore[no-redef]
else:
    from . import streams

DEFAULT_LIMIT = 1500
DEFAULT_RESULT_LIMIT = 400
#: An absolute path of the machines recordings are made on.
ABSOLUTE_PATH = re.compile(r"(?<![\w.~/-])/(?:Users|home|private|tmp|var|opt|mnt|root)/[^\s\"'`<>,;:()\[\]{}\\|]+")
#: The name Claude Code gives a working directory's transcript folder, which spells the directory's path with hyphens.
ENCODED_PATH = re.compile(r"-(?:Users|private-tmp|home)-[A-Za-z0-9._-]+")
#: A long unbroken run of base64 characters, which is image bytes or something as little fit to publish.
BASE64_RUN = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
START_KEYS = ("type", "subtype", "session_id", "cwd", "tools", "mcp_servers", "model", "permissionMode", "slash_commands",
              "skills", "plugins", "claude_code_version", "output_style", "additional_directories")
RESULT_KEYS = ("type", "subtype", "session_id", "is_error", "result", "structured_output", "stop_reason", "terminal_reason",
               "total_cost_usd", "duration_ms", "duration_api_ms", "num_turns", "usage")
#: The usage figures a check reads; the nested breakdowns are left out.
USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


class Refusal(Exception):
    """Why the reduction is not made, as a line for the person running it."""


class CannotRun(Exception):
    """Why a file the reduction needs cannot be read or written."""


class Reduction:
    def __init__(self, roots: Sequence[str], limit: int, result_limit: int):
        self.roots = sorted((root.rstrip("/") for root in roots if root.rstrip("/")), key=len, reverse=True)
        self.limit = limit
        self.result_limit = result_limit
        self.images = 0

    def path(self, match: "re.Match[str]") -> str:
        found = match.group(0)
        trailing = len(found) - len(found.rstrip(".…"))
        tail = found[len(found) - trailing:] if trailing else ""
        found = found[:len(found) - trailing] if trailing else found
        for root in self.roots:
            if found == root:
                return "." + tail
            if found.startswith(root + "/"):
                return found[len(root) + 1:] + tail
        return "<path>/" + found.rsplit("/", 1)[-1] + tail

    def scrub(self, text: str) -> str:
        return ENCODED_PATH.sub("<recording-dir>", ABSOLUTE_PATH.sub(self.path, text))

    def text(self, text: str, limit: Optional[int] = None) -> str:
        """The text with its paths replaced, cut to the limit: its start, then the header lines of what was cut."""
        limit = self.limit if limit is None else limit
        text = self.scrub(text)
        if len(text) <= limit:
            return text
        headers = [match.group(0) for match in streams.HEADER.finditer(text[limit:])]
        return "\n".join([text[:limit], *headers, f"[{len(text) - limit} characters omitted]"])

    def value(self, value: Any, limit: Optional[int] = None) -> Any:
        """A JSON value with every string reduced as text."""
        if isinstance(value, str):
            return self.text(value, limit)
        if isinstance(value, list):
            return [self.value(item, limit) for item in value]
        if isinstance(value, dict):
            return {key: self.value(item, limit) for key, item in value.items()}
        return value

    def block(self, block: Any, limit: Optional[int] = None) -> Any:
        if not isinstance(block, dict):
            return self.value(block, limit)
        kind = block.get("type")
        if kind == "image":
            source = block.get("source") if isinstance(block.get("source"), dict) else {}
            self.images += 1
            return {"type": "image", "source": {"type": source.get("type", "base64"), "media_type": source.get("media_type"),
                                                "bytes": image_size(source)}}
        if kind == "thinking":
            return {"type": "thinking", "thinking": self.text(block.get("thinking") or "", limit)}
        if kind == "redacted_thinking":
            return {"type": "redacted_thinking"}
        if kind == "tool_result":
            content = block.get("content")
            reduced = self.text(content, self.result_limit) if isinstance(content, str) else (
                [self.block(item, self.result_limit) for item in content] if isinstance(content, list) else content)
            return {"type": "tool_result", "tool_use_id": block.get("tool_use_id"), "is_error": block.get("is_error") is True,
                    "content": reduced}
        if kind == "tool_use":
            return {"type": "tool_use", "id": block.get("id"), "name": block.get("name"), "input": self.value(block.get("input"), limit)}
        return {key: self.value(item, limit) for key, item in block.items() if key != "signature"}

    def record(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The reduced record, or None when the checks read nothing of this type."""
        kind = event.get("type")
        session = event.get("session_id") or event.get("sessionId")
        if kind == "system" and event.get("subtype") == "init":
            return {key: self.value(event[key]) for key in START_KEYS if key in event}
        if kind in ("assistant", "user"):
            message = event.get("message")
            if not isinstance(message, dict):
                return None
            content = message.get("content")
            if isinstance(content, str):
                reduced: Any = self.text(content)
            elif isinstance(content, list):
                reduced = [self.block(item) for item in content]
            else:
                return None
            kept: Dict[str, Any] = {"role": message.get("role", kind), "content": reduced}
            if kind == "assistant":
                usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
                kept = {"id": message.get("id"), "model": message.get("model"), **kept,
                        "usage": {key: usage[key] for key in USAGE_KEYS if key in usage}}
            return {"type": kind, "session_id": session, "message": kept}
        if kind == "result":
            return {key: self.value(event[key]) for key in RESULT_KEYS if key in event}
        if kind == "api-request-shape" and isinstance(event.get("shape"), dict):
            return self.shape(event)
        return None

    def shape(self, event: Dict[str, Any]) -> Dict[str, Any]:
        shape = event["shape"]
        system = [{"type": "text", "text": self.scrub(item["text"])} for item in shape.get("system") or []
                  if isinstance(item, dict) and isinstance(item.get("text"), str)]
        tools = [tool if isinstance(tool, str) else str((tool or {}).get("name")) for tool in shape.get("tools") or []]
        return {"type": "api-request-shape", "sessionId": event.get("sessionId") or event.get("session_id"),
                "shapeHash": event.get("shapeHash"), "shape": {"system": system, "tools": tools}}


def image_size(source: Dict[str, Any]) -> int:
    """The decoded size in bytes of an image source's data; an image already reduced keeps its stated size."""
    if isinstance(source.get("bytes"), int):
        return source["bytes"]
    data = source.get("data")
    if not isinstance(data, str):
        return 0
    try:
        return len(base64.b64decode(data, validate=False))
    except (binascii.Error, ValueError):
        return len(data) * 3 // 4


def leftovers(text: str) -> List[str]:
    """What a reduced text still holds that a fixture may not: an absolute path of a recording machine, the encoded
    form of one, or a long run of base64. Each is named with a short excerpt."""
    found = [f"absolute path {match.group(0)[:60]!r}" for match in ABSOLUTE_PATH.finditer(text)]
    found += [f"encoded path {match.group(0)[:60]!r}" for match in ENCODED_PATH.finditer(text)]
    found += [f"base64 run of {len(match.group(0))} characters at {match.start()}" for match in BASE64_RUN.finditer(text)]
    return found


def reduce_text(text: str, roots: Sequence[str] = (), limit: int = DEFAULT_LIMIT, result_limit: int = DEFAULT_RESULT_LIMIT,
                skip: frozenset = frozenset(), shape: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, int]]:
    """The reduced text of a recording and what the reduction did. `skip` holds the uuids of the records of a parent
    session, which are left out; `shape` is a system-prompt record to write first when the recording holds none."""
    reduction = Reduction(roots, limit, result_limit)
    lines: List[str] = []
    counts = {"read": 0, "kept": 0, "dropped_unreadable": 0, "images": 0}
    shaped = False
    if shape is not None:
        lines.append(json.dumps(reduction.shape(shape), ensure_ascii=False))
        shaped = True
    for _, event in streams.records(text):
        counts["read"] += 1
        if not isinstance(event, dict):
            counts["dropped_unreadable"] += 1
            continue
        if event.get("uuid") in skip:
            continue
        if event.get("type") == "api-request-shape":
            if shaped:
                continue
            shaped = True
        kept = reduction.record(event)
        if kept is not None:
            lines.append(json.dumps(kept, ensure_ascii=False))
            counts["kept"] += 1
    counts["images"] = reduction.images
    return "\n".join(lines) + ("\n" if lines else ""), counts


def uuids_of(path: str) -> frozenset:
    with open(path, encoding="utf-8") as handle:
        return frozenset(event["uuid"] for _, event in streams.records(handle.read())
                         if isinstance(event, dict) and isinstance(event.get("uuid"), str))


def reduce_file(source: str, target: str, roots: Sequence[str] = (), after: Optional[str] = None,
                transcripts: Optional[str] = None, limit: int = DEFAULT_LIMIT,
                result_limit: int = DEFAULT_RESULT_LIMIT) -> Dict[str, int]:
    """Write the reduction of `source` to `target`, refusing when the output would still hold a path or image bytes."""
    if os.path.abspath(source) == os.path.abspath(target):
        raise Refusal("the output is the input; name a different output file")
    try:
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as error:
        raise CannotRun(f"the input {source} cannot be read ({error.strerror or error}); name a recorded stream or transcript")
    skip: frozenset = frozenset()
    if after is not None:
        try:
            skip = uuids_of(after)
        except OSError as error:
            raise CannotRun(f"the parent transcript {after} cannot be read ({error.strerror or error}); name the transcript "
                            "of the session this one was forked from")
    shape = None
    if transcripts is not None:
        stream = streams.read_stream(text)
        if stream.system is None:
            found = streams.find_transcript(stream.session_id, transcripts)
            if found is None:
                raise Refusal(f"no transcript named {stream.session_id}.jsonl lies under {transcripts}, so the system "
                              "prompt of the session cannot be taken; name the folder Claude Code keeps its transcripts in")
            shape = streams.shape_record(found)
    reduced, counts = reduce_text(text, roots, limit, result_limit, skip, shape)
    left = leftovers(reduced)
    if left:
        raise Refusal(f"the reduction would still hold {len(left)} thing(s) a fixture may not: {'; '.join(left[:3])}")
    try:
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(reduced)
    except OSError as error:
        raise CannotRun(f"the output {target} cannot be written ({error.strerror or error}); name a file in a folder that exists")
    return counts


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--after")
    parser.add_argument("--transcripts")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--result-limit", type=int, default=DEFAULT_RESULT_LIMIT)
    args = parser.parse_args(argv)
    if args.limit < 1 or args.result_limit < 1:
        print("REFUSED: --limit and --result-limit must be at least 1 character; give a larger limit")
        return 1
    try:
        counts = reduce_file(args.input, args.output, args.root, args.after, args.transcripts, args.limit, args.result_limit)
    except Refusal as error:
        print(f"REFUSED: {error}")
        return 1
    except CannotRun as error:
        print(f"CANNOT RUN: {error}")
        return 2
    print(f"RESULT: wrote {args.output}: kept {counts['kept']} of {counts['read']} records, replaced {counts['images']} "
          f"image(s) by their size, passed over {counts['dropped_unreadable']} line(s) that were not JSON")
    return 0


if __name__ == "__main__":
    sys.exit(main())
