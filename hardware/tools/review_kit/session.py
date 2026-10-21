"""The session specification: how every session of a review is started, and the one place that builds the agent command line's arguments.

A review starts its sessions from one specification. The root, every fork of it, a
repair turn and an adjudication turn are started with the same system prompt,
appended prompt, tool list, model and schema arguments; what differs between them is
the message, which is sent on standard input, and the session resumed and whether it
is forked. A specification that changes after the first session of a review has
started is refused, naming the field.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional, Sequence

#: The flags that start a session with no MCP server and without the instruction sources the command line can exclude.
QUIET_ARGUMENTS = ("--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
                   "--settings", json.dumps({"disableAllHooks": True}), "--exclude-dynamic-system-prompt-sections")
#: Environment variables set for every session, so that no memory or instruction file of the machine reaches it.
QUIET_ENVIRONMENT = {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
#: The tool the command line adds to a session started with a result schema, through which the schema's answer arrives.
SCHEMA_TOOL = "StructuredOutput"


class SpecChanged(Exception):
    """A session of a review was asked to start from a specification other than the one the review began with."""

    def __init__(self, field: str, first: Any, now: Any):
        self.field, self.first, self.now = field, first, now
        super().__init__(f"the session specification's {field} changed after the review's first session started, from "
                         f"{first!r:.120} to {now!r:.120}; every session of a review starts from one specification, so "
                         "start the review again with the new one")


@dataclass(frozen=True)
class SessionSpec:
    """Everything about a session's start that is the same for every session of one review.

    `json_schema` is the result schema as the JSON text the command line is given, or None for a
    session that returns text. `cwd` is the folder the sessions run in. `model` is a full model id.
    """

    tools: Sequence[str]
    cwd: str
    model: Optional[str] = None
    system: Optional[str] = None
    append_system: Optional[str] = None
    json_schema: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "tools", tuple(self.tools))

    def as_dict(self) -> Dict[str, Any]:
        return {"tools": list(self.tools), "cwd": self.cwd, "model": self.model, "system": self.system,
                "append_system": self.append_system, "json_schema": self.json_schema}

    @property
    def digest(self) -> str:
        return text_digest(json.dumps(self.as_dict(), sort_keys=True, ensure_ascii=False))

    @property
    def expected_tools(self) -> List[str]:
        """The tools a session started from this specification reports: the granted ones, and the schema's tool."""
        return sorted(set(self.tools) | ({SCHEMA_TOOL} if self.json_schema else set()))


@dataclass(frozen=True)
class Call:
    """One call of the agent command line: the specification, the message sent on standard input, and what it continues.

    `parent` is the identifier of the session resumed, None for a root. `fork` starts a new session from the parent
    and not a further turn of it. `label` names the session in reports.
    """

    spec: SessionSpec
    message: str
    parent: Optional[str] = None
    fork: bool = False
    label: str = ""

    def __post_init__(self):
        if self.fork and not self.parent:
            raise ValueError("a fork needs the session it forks from")

    @property
    def message_digest(self) -> str:
        return text_digest(self.message)

    @property
    def key(self) -> str:
        """The hash a recorded stream is found by: the specification, the parent and the message."""
        return text_digest("\n".join([self.spec.digest, self.parent or "", self.message_digest]))

    @property
    def arguments(self) -> List[str]:
        return arguments(self.spec, self.parent, self.fork)


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def arguments(spec: SessionSpec, resume: Optional[str] = None, fork: bool = False) -> List[str]:
    """The agent command line's arguments, after its program name, built from the specification alone.

    Print mode, stream-json in and out, the tool list, no permission prompt, the flags that exclude what the
    command line can exclude, then the resume and fork arguments when the session continues another, then the
    model, system prompts and schema when the specification has them.
    """
    tools = ",".join(spec.tools)
    found = ["-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
             "--tools", tools, "--allowedTools", tools, "--permission-mode", "dontAsk", *QUIET_ARGUMENTS]
    if resume:
        found += ["--resume", resume] + (["--fork-session"] if fork else [])
    for flag, value in (("--model", spec.model), ("--system-prompt", spec.system),
                        ("--append-system-prompt", spec.append_system), ("--json-schema", spec.json_schema)):
        if value is not None:
            found += [flag, value]
    return found


def user_message(blocks: Sequence[Dict[str, Any]]) -> str:
    """One stream-json user message holding the content blocks (text and image blocks), as the one line the command line reads."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": list(blocks)}}, ensure_ascii=False)


def text_block(text: str) -> Dict[str, Any]:
    return {"type": "text", "text": text}


def image_block(png: bytes, media_type: str = "image/png") -> Dict[str, Any]:
    import base64
    return {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                        "data": base64.b64encode(png).decode("ascii")}}


class SpecGuard:
    """Holds the specification the review began with and refuses any other, naming the field that differs."""

    def __init__(self):
        self.first: Optional[SessionSpec] = None
        self.lock = threading.Lock()

    def bind(self, spec: SessionSpec) -> None:
        with self.lock:
            if self.first is None:
                self.first = spec
                return
            for field in fields(SessionSpec):
                before, now = getattr(self.first, field.name), getattr(spec, field.name)
                if before != now:
                    raise SpecChanged(field.name, before, now)
