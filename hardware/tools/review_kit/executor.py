"""The executors: the one interface the scheduler calls, with a stub, a replay of recorded streams and the real command line.

Every executor takes a Call (a session specification, a message, the session
continued) and returns an Outcome. What the executors share lives in the base
class: the specification guard, the retry of a call refused for a rate limit after
a wait that grows (taken from an injected clock, so a test does not sleep), the
saving of each stream with the hashes that key it, and the check of the start
report against the specification. The only impure edge is ClaudeCliExecutor.

An Outcome is typed. `ok` is an answer, `rate_limit` a call still refused after
the bounded retries, `error` a command line that exited with an error or reported
one, and `empty` a command line that succeeded and returned no answer. The
executor retries nothing else; what to do with `error` and `empty` is the
scheduler's.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .session import QUIET_ENVIRONMENT, Call, SessionSpec, SpecGuard

#: The environment variable the agent command line's name is read from.
AGENT_ENV = "REVIEW_KIT_AGENT"
DEFAULT_AGENT = "claude"
#: The outcome kinds.
OK, RATE_LIMIT, ERROR, EMPTY = "ok", "rate_limit", "error", "empty"
RATE_PATTERN = re.compile(r"rate.?limit|too many requests|\b429\b|overloaded", re.IGNORECASE)
LOGIN_PATTERN = re.compile(r"not logged in|please run /login|invalid api key", re.IGNORECASE)
#: Each file a saved stream is kept in: the stream as printed, and what keys it.
STREAM_SUFFIX, META_SUFFIX = ".jsonl", ".json"
#: The lists a start report must give.
START_LISTS = ("tools", "mcp_servers", "skills", "slash_commands", "plugins")
FIGURE_FIELDS = (("total_cost_usd", (int, float)), ("duration_api_ms", (int, float)), ("num_turns", int))
TOKEN_FIELDS = (("cache_read", "cache_read_input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                ("fresh", "input_tokens"), ("generated", "output_tokens"))
KIND_WORDS = {str: "a non-empty string", list: "a list", dict: "a mapping", bool: "true or false",
              (int, float): "a finite number of zero or more", int: "a whole number of zero or more"}


class CannotRun(Exception):
    """The agent command line is missing or not logged in, so nothing can be run; the text says what to do."""


class NotRecorded(Exception):
    """The replay holds no stream for the hash of a call."""


class StartReportFailed(Exception):
    """A session's start report shows what the specification excludes, or lacks what it must show."""

    def __init__(self, label: str, problems: Sequence[str]):
        self.label, self.problems = label, list(problems)
        super().__init__("; ".join(problems))


def clean(text: Any) -> str:
    """A field that cannot break the line it is printed on."""
    return " ".join(str(text).replace("|", "/").split())


def named(value: Any, kind) -> bool:
    """Whether `value` is of `kind`: a bool is never a number, a number is finite and not negative, and a string is not empty."""
    if kind is str:
        return isinstance(value, str) and bool(value.strip())
    if kind is bool:
        return isinstance(value, bool)
    if isinstance(value, bool) or not isinstance(value, kind):
        return False
    if isinstance(value, (int, float)):
        try:
            return math.isfinite(float(value)) and value >= 0
        except OverflowError:
            return False
    return True


def field_problem(source: Any, key: str, kind, what: str, where: str) -> Optional[str]:
    """Why `source[key]` cannot be relied on: absent, or not of `kind`."""
    if not isinstance(source, dict) or source.get(key) is None:
        return f"{where} has no {what}"
    if not named(source[key], kind):
        return f"{where} gives {what} as {source[key]!r}, which is not {KIND_WORDS[kind]}"
    return None


# --- The clock ---------------------------------------------------------------------------------


class SystemClock:
    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass(frozen=True)
class RetryPolicy:
    """How a call refused for a rate limit is retried: `retries` more calls, the first after `first_s` seconds and each
    later wait `factor` times the one before, none longer than `longest_s`."""

    retries: int = 5
    first_s: float = 30.0
    factor: float = 2.0
    longest_s: float = 900.0

    def wait(self, attempt: int) -> float:
        return min(self.first_s * self.factor ** attempt, self.longest_s)


# --- A session as its stream shows it -----------------------------------------------------------


class Session:
    """One session's start report, calls, tool uses and result report, as the agent command line printed them.

    `malformed` holds every field the command relies on that the output gave with the wrong type, and `absent` the
    figures and text a result report that succeeded lacks; neither is ever defaulted.
    """

    def __init__(self):
        self.start: Dict[str, Any] = {}
        self.tool_uses: List[Tuple[str, Dict[str, Any], str]] = []
        self.failed_tool_uses: set = set()
        self.blocks: List[Tuple[str, str]] = []
        #: One entry per distinct message identifier, in order: its id and token figures.
        self.calls: List[Dict[str, Any]] = []
        self.result: Optional[Dict[str, Any]] = None
        self.malformed: List[str] = []
        self.absent: List[str] = []
        self.exit_code = 0
        self.stderr = ""
        self.wall_s = 0.0

    @property
    def id(self) -> str:
        found = self.start.get("session_id")
        return found if isinstance(found, str) else ""

    @property
    def text(self) -> str:
        found = (self.result or {}).get("result")
        return found if isinstance(found, str) else ""

    @property
    def structured(self) -> Any:
        return (self.result or {}).get("structured_output")

    @property
    def answer(self) -> str:
        """The answer as text: the structured output as JSON when the command line returned one, else the result text."""
        if self.structured is not None:
            return json.dumps(self.structured, ensure_ascii=False)
        return self.text

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and self.result is not None and self.result.get("is_error") is False

    @property
    def first_read(self) -> Optional[int]:
        """What the session's first call read from the cache, None when it made no call."""
        return self.calls[0]["cache_read"] if self.calls else None

    @property
    def prefix_tokens(self) -> Optional[int]:
        """What the session's last call held in the cache, read and written: the prefix a fork of it can read."""
        return self.calls[-1]["cache_read"] + self.calls[-1]["cache_write"] if self.calls else None

    def said(self) -> str:
        """What the session returned, for a failure to quote."""
        return clean(self.text or self.stderr or "nothing")


def parse_stream(text: str) -> Session:
    """The session as the stream shows it. A line that is not a JSON event, an event with no string `type`, and a
    second start or result report are malformed; an event of a type the command does not read is passed over."""
    session = Session()
    for line in text.split("\n"):  # never splitlines: U+2028, U+2029 and U+0085 are raw inside a JSON event
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            session.malformed.append(f"printed a line that is not a JSON event: {clean(line)[:120]!r}")
            continue
        if not isinstance(event, dict):
            session.malformed.append(f"printed a line that is not a JSON event: {clean(line)[:120]!r}")
            continue
        if not isinstance(event.get("type"), str):
            session.malformed.append(f"printed an event with no string `type`: {clean(line)[:120]!r}")
            continue
        kind = event["type"]
        if kind == "system" and event.get("subtype") == "init":
            if session.start:
                session.malformed.append("printed a second start report")
            session.start = event
        elif kind == "assistant":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                session.malformed.append("printed an assistant event with no `message.content` list")
                continue
            parse_usage(session, message)
            for item in content:
                parse_block(session, item)
        elif kind == "user":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            # Only a tool result the stream marks failed is kept, to excuse that read; anything else excuses nothing.
            for item in content if isinstance(content, list) else []:
                if (isinstance(item, dict) and item.get("type") == "tool_result" and item.get("is_error") is True
                        and named(item.get("tool_use_id"), str)):
                    session.failed_tool_uses.add(item["tool_use_id"])
        elif kind == "result":
            if session.result is not None:
                session.malformed.append("printed a second result report")
            session.result = event
            parse_result_report(session, event)
    return session


def parse_usage(session: Session, message: Dict[str, Any]) -> None:
    """Record a model call once however many events carry its blocks: the last usage given for its message identifier stands."""
    identifier, usage = message.get("id"), message.get("usage")
    if not named(identifier, str) or not isinstance(usage, dict):
        session.malformed.append("printed an assistant event with no message `id` and `usage`")
        return
    figures = {"id": identifier}
    for name, key in TOKEN_FIELDS:
        value = usage.get(key)
        if not named(value, int):
            session.malformed.append(f"printed a call whose `usage.{key}` is {value!r}, not a whole number of zero or more")
            value = 0
        figures[name] = value
    for known in session.calls:
        if known["id"] == identifier:
            known.update(figures)
            return
    session.calls.append(figures)


def parse_block(session: Session, item: Any) -> None:
    """One content block of an assistant event, kept in the session's history; what it relies on is typed here."""
    if not isinstance(item, dict) or not isinstance(item.get("type"), str):
        session.blocks.append(("untyped", ""))
        session.malformed.append("printed a content block with no string `type`")
        return
    kind = item["type"]
    if kind == "text":
        text = item.get("text")
        if not isinstance(text, str):
            session.malformed.append("printed a text block with no string `text`")
        session.blocks.append((kind, text if isinstance(text, str) else ""))
        return
    if kind == "thinking":
        # Its text is kept so that only a thinking block with none can be passed; a missing field cannot be shown empty.
        thought = item.get("thinking")
        session.blocks.append((kind, thought if isinstance(thought, str) else "(no text field)"))
        return
    session.blocks.append((kind, ""))
    if kind != "tool_use":
        return
    name = item.get("name")
    if not named(name, str):
        session.malformed.append("printed a tool use with no string `name`")
        return
    given = item.get("input")
    if not isinstance(given, dict):
        session.malformed.append(f"printed a {name} tool use with no `input` mapping")
        return
    session.tool_uses.append((name, given, item["id"] if named(item.get("id"), str) else ""))


def parse_result_report(session: Session, result: Dict[str, Any]) -> None:
    """Type the result report's fields: a mistyped one is malformed, and one a session that succeeded lacks is absent."""
    where = "printed a result report that"
    if not isinstance(result.get("is_error"), bool):
        session.malformed.append(f"{where} has no `is_error` true or false")
    usage = result.get("usage")
    checks = [(result, key, kind, key) for key, kind in FIGURE_FIELDS] + [(result, "usage", dict, "usage")]
    checks += [(usage, key, int, f"usage.{key}") for _, key in TOKEN_FIELDS] if isinstance(usage, dict) else []
    for source, key, kind, label in checks:
        if source.get(key) is None:
            session.absent.append(label)
        elif not named(source[key], kind):
            session.malformed.append(f"{where} gives `{label}` as {source[key]!r}, which is not {KIND_WORDS[kind]}")
    if result.get("result") is None:
        session.absent.append("result")
    elif not isinstance(result["result"], str):
        session.malformed.append(f"{where} gives `result` as {result['result']!r}, which is not text")
    if result.get("session_id") is not None and not isinstance(result["session_id"], str):
        session.malformed.append(f"{where} gives `session_id` as {result['session_id']!r}, which is not a string")


def same_path(given: str, folder: str) -> bool:
    """Whether a path the agent command line printed is `folder`; one that cannot be a path is not."""
    try:
        return os.path.realpath(given) == os.path.realpath(folder)
    except (ValueError, OSError):
        return False


def start_problems(session: Session, label: str, spec: SessionSpec) -> List[str]:
    """What the session's reports show that the specification excludes or does not give, each naming the session.

    A field the command relies on that the output leaves out or gives the wrong type is a problem naming the
    field, never a default. The system prompt is not here: the start report carries none, and it is read from
    the session's transcript.
    """
    found = [f"session {label} {why}" for why in session.malformed]
    if session.succeeded and session.absent:
        found.append(f"session {label} printed a result report without {', '.join(session.absent)}; its cost and "
                     "answer cannot be told")
    start = session.start
    if not start:
        return found + [f"session {label} printed no start report; check the agent command line prints stream-json events"]
    typed = {}
    for key in ("model", "cwd", "session_id"):
        why = field_problem(start, key, str, f"`{key}`", f"session {label}'s start report")
        found += [why] if why else []
        typed[key] = start.get(key) if not why else None
    for key in START_LISTS:
        why = field_problem(start, key, list, f"`{key}`", f"session {label}'s start report")
        found += [why] if why else []
        typed[key] = start.get(key) if not why else None
    if typed["tools"] is not None:
        if not all(isinstance(tool, str) for tool in typed["tools"]):
            found.append(f"session {label}'s start report gives `tools` as {typed['tools']!r}, which is not a list of names")
        elif sorted(typed["tools"]) != spec.expected_tools:
            found.append(f"session {label} started with tools {sorted(typed['tools'])}, not the {spec.expected_tools} "
                         "its specification grants")
    if typed["model"] is not None and spec.model and typed["model"] != spec.model:
        found.append(f"session {label} started with model {typed['model']}, not {spec.model}")
    if typed["mcp_servers"]:
        found.append(f"session {label} started with MCP servers {typed['mcp_servers']}; none may be loaded")
    if typed["skills"]:
        found.append(f"session {label} started with skills {typed['skills']}, which it was asked to exclude")
    if typed["slash_commands"]:
        found.append(f"session {label} started with commands {typed['slash_commands']}, which it was asked to exclude")
    outside = [str(plugin.get("name") if isinstance(plugin, dict) else plugin) for plugin in typed["plugins"] or []
               if not (isinstance(plugin, dict) and plugin.get("path") == "builtin")]
    if outside:
        found.append(f"session {label} started with plugins {outside}, which it was asked to exclude")
    if typed["cwd"] is not None and not same_path(typed["cwd"], spec.cwd):
        found.append(f"session {label} started in {typed['cwd']!r}, not the folder {spec.cwd} its specification names")
    return found


# --- Outcomes ----------------------------------------------------------------------------------


@dataclass
class Outcome:
    """What a call returned, typed: the session its stream shows, the stream and standard error as printed, the exit status,
    how many times the command line was called and the waits between those calls."""

    kind: str
    session: Session
    stream: str = ""
    stderr: str = ""
    exit_code: int = 0
    attempts: int = 1
    waits: List[float] = field(default_factory=list)

    @property
    def answer(self) -> str:
        return self.session.answer

    def said(self) -> str:
        return self.session.said()


def classify(session: Session, exit_code: int, stderr: str, program: str = DEFAULT_AGENT) -> str:
    """The kind of outcome a call's reports show; a command line that is not logged in raises CannotRun."""
    result = session.result or {}
    failed = bool(result.get("is_error")) or exit_code != 0 or session.result is None
    text = session.text
    if failed and (result.get("api_error_status") == 401 or LOGIN_PATTERN.search(stderr)):
        raise CannotRun(f"the agent command line {program} is not logged in; log it in, then run again")
    if failed and (result.get("api_error_status") == 429 or RATE_PATTERN.search(stderr)
                   or (bool(result.get("is_error")) and RATE_PATTERN.search(text))):
        return RATE_LIMIT
    if failed:
        return ERROR
    if session.structured is None and not text.strip():
        return EMPTY
    return OK


class StreamStore:
    """The streams of a review as files in its output folder: each stream exactly as the command line printed it, and
    beside it the specification, parent, message hash and key that found it."""

    def __init__(self, folder: str):
        self.folder = folder
        self.lock = threading.Lock()

    def write(self, call: Call, outcome: Outcome, wall_s: float = 0.0) -> str:
        with self.lock:
            os.makedirs(self.folder, exist_ok=True)
            taken = [name for name in os.listdir(self.folder) if name.endswith(STREAM_SUFFIX)]
            number = 1 + max([int(name.split("-", 1)[0]) for name in taken if name.split("-", 1)[0].isdigit()] or [0])
            stem = os.path.join(self.folder, f"{number:04d}-{call.key[:12]}")
            with open(stem + STREAM_SUFFIX, "w", encoding="utf-8", newline="") as handle:
                handle.write(outcome.stream)
            meta = {"key": call.key, "spec_digest": call.spec.digest, "message_digest": call.message_digest,
                    "parent": call.parent, "fork": call.fork, "label": call.label, "kind": outcome.kind,
                    "exit_code": outcome.exit_code, "stderr": outcome.stderr, "wall_s": round(wall_s, 3),
                    "attempts": outcome.attempts, "waits": list(outcome.waits),
                    "spec": call.spec.as_dict(), "arguments": call.arguments}
            with open(stem + META_SUFFIX, "w", encoding="utf-8") as handle:
                json.dump(meta, handle, indent=1, ensure_ascii=False)
                handle.write("\n")
            return stem + STREAM_SUFFIX

    def load(self) -> Dict[str, List[Dict[str, Any]]]:
        """Every saved stream by key, oldest first: each a mapping with its `stream`, `stderr` and `exit_code`."""
        found: Dict[str, List[Dict[str, Any]]] = {}
        for name in sorted(os.listdir(self.folder)):
            if not name.endswith(META_SUFFIX):
                continue
            with open(os.path.join(self.folder, name), encoding="utf-8") as handle:
                meta = json.load(handle)
            with open(os.path.join(self.folder, name[:-len(META_SUFFIX)] + STREAM_SUFFIX), encoding="utf-8", newline="") as handle:
                stream = handle.read()
            found.setdefault(meta["key"], []).append({"stream": stream, "stderr": meta["stderr"],
                                                      "exit_code": meta["exit_code"]})
        return found


# --- The interface -----------------------------------------------------------------------------


class Executor:
    """What every executor does around one attempt. A subclass gives `execute`, one attempt of a call."""

    def __init__(self, clock=None, policy: Optional[RetryPolicy] = None, guard: Optional[SpecGuard] = None,
                 out: Optional[str] = None, check_start: bool = True):
        self.clock = clock or SystemClock()
        self.policy = policy or RetryPolicy()
        self.guard = guard or SpecGuard()
        self.store = StreamStore(out) if out else None
        self.check_start = check_start

    def execute(self, call: Call) -> Outcome:
        raise NotImplementedError

    def run(self, call: Call) -> Outcome:
        """The call's outcome. A specification other than the review's first raises SpecChanged; a call refused for a
        rate limit is retried after a wait that grows, up to the policy's bound; a start report that shows what the
        specification excludes raises StartReportFailed naming the session. Nothing else is retried."""
        self.guard.bind(call.spec)
        waits: List[float] = []
        began = self.clock.now()
        for attempt in range(self.policy.retries + 1):
            outcome = self.execute(call)
            if outcome.kind != RATE_LIMIT or attempt == self.policy.retries:
                break
            waits.append(self.policy.wait(attempt))
            self.clock.sleep(waits[-1])
        outcome.attempts, outcome.waits = attempt + 1, waits
        outcome.session.wall_s = self.clock.now() - began
        if self.store is not None:
            self.store.write(call, outcome, outcome.session.wall_s)
        if self.check_start and outcome.kind in (OK, EMPTY):
            problems = start_problems(outcome.session, call.label or call.key[:12], call.spec)
            if problems:
                raise StartReportFailed(call.label or call.key[:12], problems)
        return outcome


def outcome_of(stream: str, stderr: str, exit_code: int, program: str = DEFAULT_AGENT) -> Outcome:
    session = parse_stream(stream)
    session.exit_code, session.stderr = exit_code, stderr.strip()
    return Outcome(classify(session, exit_code, session.stderr, program), session, stream, session.stderr, exit_code)


# --- The real command line -----------------------------------------------------------------------


def agent_program(environ: Optional[Dict[str, str]] = None) -> str:
    return (environ if environ is not None else os.environ).get(AGENT_ENV) or DEFAULT_AGENT


def require_agent(environ: Optional[Dict[str, str]] = None) -> str:
    """The agent command line's path, or a CannotRun naming what to do."""
    program = agent_program(environ)
    found = shutil.which(program)
    if found is None:
        raise CannotRun(f"the agent command line {program} is not on the search path; install it, or name the program "
                        f"in the environment variable {AGENT_ENV}")
    try:
        status = subprocess.run([found, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise CannotRun(f"the agent command line {program} could not report its login ({error}); check it runs")
    try:
        parsed = json.loads(status.stdout)
    except (ValueError, RecursionError):
        parsed = None
    if status.returncode != 0 or not isinstance(parsed, dict) or parsed.get("loggedIn") is not True:
        printed = clean(status.stdout.strip())[:200] or "nothing"
        raise CannotRun(f"the agent command line {program} is not logged in: `auth status` exited {status.returncode} and "
                        f"printed {printed!r}, not an object whose loggedIn is true; log it in, then run again")
    return found


class ClaudeCliExecutor(Executor):
    """The real agent command line, started from the specification with the message on standard input. The only impure
    executor; it is never run by a test."""

    def __init__(self, program: Optional[str] = None, environ: Optional[Dict[str, str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.program = program or agent_program(environ)

    def execute(self, call: Call) -> Outcome:
        try:
            done = subprocess.run([self.program] + call.arguments, input=call.message + "\n", cwd=call.spec.cwd,
                                  capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  env={**os.environ, **QUIET_ENVIRONMENT})
        except (OSError, subprocess.SubprocessError) as error:
            raise CannotRun(f"the agent command line {self.program} could not be started ({error}); check it is installed "
                            "and runs, then run again")
        return outcome_of(done.stdout, done.stderr, done.returncode, self.program)


# --- The replay --------------------------------------------------------------------------------


class ReplayExecutor(Executor):
    """Returns the recorded stream for the hash of a call's specification, parent and message, and fails naming the hash
    when none is recorded. A key recorded more than once returns its recordings in order, the last again after them."""

    def __init__(self, recordings: Dict[str, List[Dict[str, Any]]], **kwargs):
        super().__init__(**kwargs)
        self.recordings = {key: list(entries) for key, entries in recordings.items()}
        self.used: Dict[str, int] = {}
        self.lock = threading.Lock()

    @classmethod
    def from_folder(cls, folder: str, **kwargs) -> "ReplayExecutor":
        return cls(StreamStore(folder).load(), **kwargs)

    def execute(self, call: Call) -> Outcome:
        with self.lock:
            entries = self.recordings.get(call.key)
            if not entries:
                raise NotRecorded(f"no stream is recorded for the hash {call.key} (session {call.label or 'unnamed'}: "
                                  f"specification {call.spec.digest[:12]}, parent {call.parent or 'none'}, message "
                                  f"{call.message_digest[:12]}); record it by running the review against the real command "
                                  "line, or change the call to one that is recorded")
            number = self.used.get(call.key, 0)
            self.used[call.key] = number + 1
        entry = entries[min(number, len(entries) - 1)]
        return outcome_of(entry["stream"], entry.get("stderr", ""), entry.get("exit_code", 0))


# --- The stub ----------------------------------------------------------------------------------


@dataclass
class Reply:
    """What a stub session plays: the answer, how it ended, and what its start report shows. A field left None is what a
    well-behaved session shows: the specification's tools, model and folder, no MCP server and only built-in plugins."""

    text: str = "ok"
    structured: Any = None
    exit_code: int = 0
    stderr: str = ""
    is_error: bool = False
    api_error_status: Optional[int] = None
    cost: float = 0.01
    api_ms: int = 100
    turns: int = 1
    read: Optional[int] = None
    write: int = 100
    generated: int = 10
    tools: Optional[Sequence[str]] = None
    model: Optional[str] = None
    cwd: Optional[str] = None
    mcp_servers: Sequence[Any] = ()
    skills: Sequence[Any] = ()
    slash_commands: Sequence[Any] = ()
    plugins: Optional[Sequence[Any]] = None
    blocks: Optional[Sequence[Dict[str, Any]]] = None
    raw: Optional[str] = None


def stream_text(session_id: str, *, text: str = "ok", structured: Any = None, cost: float = 0.01, api_ms: int = 100,
                turns: int = 1, read: int = 0, write: int = 100, generated: int = 10, tools: Sequence[str] = ("Read",),
                model: str = "stub-model", cwd: str = ".", mcp_servers: Sequence[Any] = (), skills: Sequence[Any] = (),
                slash_commands: Sequence[Any] = (), plugins: Optional[Sequence[Any]] = None, is_error: bool = False,
                api_error_status: Optional[int] = None, blocks: Optional[Sequence[Dict[str, Any]]] = None,
                message_id: Optional[str] = None) -> str:
    """A stream-json stream of the shape the agent command line prints: a start report, one model call and a result report."""
    usage = {"input_tokens": 2, "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
             "output_tokens": generated}
    start = {"type": "system", "subtype": "init", "session_id": session_id, "cwd": cwd, "tools": list(tools),
             "mcp_servers": list(mcp_servers), "model": model, "skills": list(skills),
             "slash_commands": list(slash_commands),
             "plugins": list(plugins) if plugins is not None else [{"name": "builtin-plugin", "path": "builtin"}]}
    content = list(blocks) if blocks is not None else [{"type": "text", "text": text}]
    assistant = {"type": "assistant", "message": {"id": message_id or f"msg_{session_id}", "role": "assistant",
                                                  "content": content, "usage": usage}}
    result = {"type": "result", "subtype": "error" if is_error else "success", "is_error": is_error,
              "api_error_status": api_error_status, "session_id": session_id, "total_cost_usd": cost,
              "duration_api_ms": api_ms, "num_turns": turns, "result": text, "usage": usage}
    if structured is not None:
        result["structured_output"] = structured
    return "\n".join(json.dumps(event, ensure_ascii=False) for event in (start, assistant, result)) + "\n"


class StubExecutor(Executor):
    """Plays sessions without a model. It keeps every call it was given, with the arguments built from its
    specification, so a test can compare how sessions were started; a fork reads its parent's prefix from the cache and
    reports the cost, time and turns cumulatively from its parent, as the real command line does.

    `replies` is None (every call is answered with the default Reply), a list consumed in order (the last repeats), or
    a function of the call and its number returning a Reply or a list of Replies played on successive attempts of the
    call (a rate limit's retries).
    """

    def __init__(self, replies=None, **kwargs):
        super().__init__(**kwargs)
        self.replies = replies
        self.calls: List[Call] = []
        self.arguments: List[List[str]] = []
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.pending: Dict[str, List[Reply]] = {}
        self.count = 0
        #: How many times the command line would have been started, retries included.
        self.executions = 0

    def reply_for(self, call: Call, number: int) -> Reply:
        if self.replies is None:
            return Reply()
        if callable(self.replies):
            made = self.replies(call, number)
        else:
            made = self.replies[min(number, len(self.replies) - 1)]
        return made

    def execute(self, call: Call) -> Outcome:
        with self.lock:
            self.executions += 1
            pending = self.pending.get(call.key)
            if pending:
                reply = pending.pop(0)
                number = None
            else:
                number = self.count
                self.count += 1
                self.calls.append(call)
                self.arguments.append(call.arguments)
                reply = self.reply_for(call, number)
                if isinstance(reply, (list, tuple)):
                    self.pending[call.key] = list(reply[1:])
                    reply = reply[0]
            parent = self.sessions.get(call.parent or "", {"prefix": 0, "cost": 0.0, "api_ms": 0, "turns": 0})
            if call.parent and not call.fork:
                session_id = call.parent
            else:
                session_id = f"stub-session-{len(self.sessions) + 1}"
            held = parent["prefix"] if call.parent else 0
            read = reply.read if reply.read is not None else held
            cumulative = {"cost": parent["cost"] + reply.cost, "api_ms": parent["api_ms"] + reply.api_ms,
                          "turns": parent["turns"] + reply.turns}
            self.sessions[session_id] = {"prefix": read + reply.write, **cumulative}
        if reply.raw is not None:
            return outcome_of(reply.raw, reply.stderr, reply.exit_code)
        spec = call.spec
        stream = stream_text(
            session_id, text=reply.text, structured=reply.structured, cost=cumulative["cost"], api_ms=cumulative["api_ms"],
            turns=cumulative["turns"], read=read, write=reply.write, generated=reply.generated,
            tools=reply.tools if reply.tools is not None else spec.expected_tools,
            model=reply.model or spec.model or "stub-model", cwd=reply.cwd or spec.cwd, mcp_servers=reply.mcp_servers,
            skills=reply.skills, slash_commands=reply.slash_commands, plugins=reply.plugins,
            is_error=reply.is_error, api_error_status=reply.api_error_status, blocks=reply.blocks)
        return outcome_of(stream, reply.stderr, reply.exit_code)
