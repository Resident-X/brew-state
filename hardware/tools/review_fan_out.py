#!/usr/bin/env python3
"""Run a judged review as a setup session and one forked read-only reviewer per unit, and merge the units' results.

A judged review divides into units that do not depend on one another. Judging
them one after another in one long context costs the slowest unit's time many
times over, so this command starts one setup session that reads the review's
shared material and nothing else, then judges each unit in its own reviewer
forked from that session, the reviewers running together, up to a bound. It
returns each unit's result to a merge that holds no model. A review with one
unit is judged in a second turn of the setup session and is not forked.

What a review is, and so which units it has, which prompt every session starts
from, which tools a reviewer is granted, which tables a result may hold and
which checks the merge makes, is a caller's: a Python module named
review_caller_<name> beside this command, or in the folder --callers names. It
exposes SETUP_PROMPT, unit_prompt(unit, review_folder), units(review_folder),
TOOLS, BOUND, TABLES, FINDINGS and CHECK, and may define the retrieval grant, the
checklist as a function and the rendered record. TOOLS is some of the read tools
and, as the retrieval grant, WebFetch, which fetches a published document and
writes nothing; the setup session keeps the read tools alone. unit_prompt takes
the unit and the review folder, so a prompt can name what the starter wrote
there. FINDINGS["checklist"] is a list, or a function of the review folder
resolved once per run before the setup session starts. RENDER(review_folder,
tables) returns file names with their text, which are written into the output
folder after the merge and named in the report. No caller is registered here.

FINDINGS names the findings table and how the merge numbers it, and holds a
`citation` pattern with a `number` group that finds the cells' citations of a
finding. A pattern with no `round` group matches this round's citations only: a
citation of an earlier round's finding must not match it, and the merge
renumbers every match. A pattern with a `round` group also needs FINDINGS["round"]
(review folder -> this round's label) and FINDINGS["earlier"] (review folder ->
the (round, number) pairs the folder's earlier rounds hold). The merge renumbers
a match whose round is this round's, checked against the unit's own numbers; it
leaves any other match as written and refuses one that "earlier" does not hold.
A cell with digits no pattern matches is not a citation. A reviewer that writes
an earlier round's citation in this round's tagged form cannot be told from a
this-round one by any merge, so the unit prompt must forbid it.

    review_fan_out.py --caller <name> --review <review folder> --out <output folder>
                      [--bound N] [--model M] [--rerun <unit>]... [--json]

The review folder is what the reviewers read. The output folder is kept apart
from it, and outside the repository, so a reviewer cannot read another unit's
verdicts. Each unit's result is kept there, so --rerun runs only the units named,
in a new setup session, and merges the kept results with the new ones.

The agent command line is started from the program named by the environment
variable REVIEW_FAN_OUT_AGENT (claude when it is unset), which must be on the
search path and logged in. Every session is started with no MCP server and with
the instruction sources the installed command line can exclude, excluded; each
session's start report is checked.

Each cause is reported on one line beginning REFUSED or CANNOT RUN, a RESULT
line comes last, and the exit status is 0 when the merged record is written, 1
when the command refuses or a unit fails, and 2 when the agent command line is
missing or not logged in. --json prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import inspect
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_check  # noqa: E402
import review_seed  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS_DIR))

#: The environment variable naming the agent command line.
AGENT_ENV = "REVIEW_FAN_OUT_AGENT"
DEFAULT_AGENT = "claude"
#: The one token the setup session answers with, so it has judged nothing for a fork to inherit.
ACK = "SETUP-READ-COMPLETE"
#: What the setup prompt always ends with, after the caller's text.
ACK_INSTRUCTION = ("Open no image and judge nothing. Write no text before, between or after your reads: no sentence "
                   "about what you are about to read, no summary, no remark on content. When you have read what is "
                   f"asked, your only text is the single token {ACK} after the last read, and nothing else.")
#: The tools the setup session is granted, and the only tools a reviewer may be granted.
READ_TOOLS = ("Read", "Glob", "Grep")
#: The one retrieval tool a caller may grant its reviewers beside the read tools: it fetches a published document and writes nothing.
RETRIEVAL_TOOLS = ("WebFetch",)
#: What a caller module must expose.
REQUIRED = ("SETUP_PROMPT", "unit_prompt", "units", "TOOLS", "BOUND", "TABLES", "FINDINGS", "CHECK")
#: Files read as images or other non-text, whether or not they exist yet.
NON_TEXT_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".pdf", ".step",
                     ".stp", ".zip", ".gz", ".bin", ".svgz")
RECORD = "record.json"
UNITS_FOLDER = "units"
SETUPS = "setups.json"
FAILED_FOLDER = "failed"
#: A unit named to run again is marked unsettled before its reviewer starts, and the mark is cleared only when its result is kept.
UNSETTLED_FOLDER = "unsettled"
RERUNS = "reruns.json"
LOCK = ".review-fan-out.lock"
#: How many times a call refused for a rate limit is retried, with the wait doubling each time.
RATE_RETRIES = 5
#: Matched against the command line's own stderr only, never a reviewer's words.
RATE_PATTERN = re.compile(r"rate.?limit|too many requests|\b429\b|overloaded", re.IGNORECASE)
LOGIN_PATTERN = re.compile(r"not logged in|please run /login|invalid api key", re.IGNORECASE)
#: The names in the output folder the driver uses itself, which a rendered record may not take.
RESERVED_NAMES = (RECORD, SETUPS, RERUNS, LOCK, UNITS_FOLDER, FAILED_FOLDER, UNSETTLED_FOLDER)
UNIT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CALLER_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
#: The environment variables that keep a session from loading the project's and user's instructions and memory.
QUIET_ENVIRONMENT = {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}


class Refused(Exception):
    """The command is refused, with each cause and what to do about it."""

    def __init__(self, causes: Sequence[str]):
        super().__init__("; ".join(causes))
        self.causes = list(causes)


class UnitFailed(Exception):
    """A unit that could not be judged, with what the reviewer returned and the sessions that cost something."""

    def __init__(self, message: str, sessions: Sequence[Dict[str, Any]] = ()):
        super().__init__(message)
        self.sessions = list(sessions)


class LoginLost(UnitFailed):
    """A unit whose call found the agent command line no longer logged in or no longer startable, with the cause."""

    def __init__(self, unit: str, cause: str, sessions: Sequence[Dict[str, Any]] = ()):
        super().__init__(f"unit {unit} failed: {cause}", sessions)
        self.cause = cause


class RateLimited(Exception):
    """A call the agent command line refused for a rate limit."""


class Malformed(Exception):
    """A reviewer's result that is not the tables its caller allows."""

    def __init__(self, problems: Sequence[str]):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


# --- Folders and callers -----------------------------------------------------------------------


def inside(path: str, folder: str) -> bool:
    return review_seed.inside(path, folder)


def refusals(review: str, out: str, repo: str = REPO) -> List[str]:
    """Why the review folder or the output folder cannot be used where they are asked to go."""
    found = []
    if not os.path.isdir(review):
        found.append(f"the review folder {review} does not exist; give the folder the review's starter wrote")
    elif inside(review, repo):
        found.append(f"the review folder {review} is inside the repository; a reviewer working there could read the "
                     "design as committed and the earlier rounds' verdicts, so give the starter's folder outside it")
    if os.path.isfile(out):
        found.append(f"the output folder {out} is a file; give a new or empty folder")
    if inside(out, repo):
        found.append(f"the output folder {out} is inside the repository; give a folder outside it")
    if os.path.isdir(review):
        if inside(out, review):
            found.append(f"the output folder {out} is inside the review folder, where a reviewer could read another "
                         "unit's verdicts; give a folder apart from it")
        elif inside(review, out):
            found.append(f"the output folder {out} contains the review folder, so a reviewer could read another "
                         "unit's verdicts; give a folder apart from it")
    return found


def load_caller(name: str, folder: str):
    """The caller module review_caller_<name> in `folder`, or the causes it cannot be used."""
    if not CALLER_NAME.match(name):
        raise Refused([f"the caller name {name!r} is not a lower-case name; give the <name> of a "
                       "review_caller_<name> module"])
    path = os.path.join(folder, f"review_caller_{name}.py")
    if not os.path.isfile(path):
        raise Refused([f"there is no caller module {path}; give the name of a review_caller_<name> module in the "
                       f"folder {folder}, or the folder holding it with --callers"])
    spec = importlib.util.spec_from_file_location(f"review_caller_{name}_loaded", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:  # a caller that does not import is refused with the reason
        raise Refused([f"the caller module {path} cannot be loaded ({type(error).__name__}: {error}); fix the module"])
    module.REVIEW_CALLER_NAME = name
    missing = [attribute for attribute in REQUIRED if not hasattr(module, attribute)]
    if missing:
        raise Refused([f"the caller module {path} lacks {', '.join(missing)}; add each to the module"])
    try:
        problems = caller_problems(module, path)
    except Exception as error:  # a caller value the typing did not foresee is a refusal naming the module, never a traceback
        problems = [f"the caller module {path} has an attribute that cannot be checked ({type(error).__name__}: {error}); "
                    "fix the module"]
    if problems:
        raise Refused(problems)
    return module


def caller_problems(module, path: str) -> List[str]:
    """Why the caller module's attributes cannot be relied on, each naming the attribute; the one place they are typed."""
    found = []

    def bad(what: str, value: Any, want: str) -> None:
        found.append(f"the caller module {path} gives {what} as {value!r:.200}; {want}")
    if not named(module.SETUP_PROMPT, str):
        bad("SETUP_PROMPT", module.SETUP_PROMPT, "give the setup session's prompt as text")
    for attribute in ("unit_prompt", "units", "CHECK"):
        if not callable(getattr(module, attribute)):
            bad(attribute, getattr(module, attribute), "make it a function")
    if callable(module.unit_prompt) and not accepts(module.unit_prompt, 2):
        found.append(f"the caller {module.REVIEW_CALLER_NAME} ({path}) gives a unit_prompt that does not accept the unit "
                     "and the review folder; make it unit_prompt(unit, review_folder)")
    if hasattr(module, "RENDER"):
        if not callable(module.RENDER):
            bad("RENDER", module.RENDER, "make it a function of the review folder and the merged tables")
        elif not accepts(module.RENDER, 2):
            found.append(f"the caller {module.REVIEW_CALLER_NAME} ({path}) gives a RENDER that does not accept the review "
                         "folder and the merged tables; make it RENDER(review_folder, tables)")
    if not isinstance(module.TOOLS, (list, tuple)) or not module.TOOLS or any(tool not in READ_TOOLS + RETRIEVAL_TOOLS
                                                                              for tool in module.TOOLS):
        found.append(f"the caller module {path} grants tools {module.TOOLS!r}; a reviewer is read-only, so grant "
                     f"some of {', '.join(READ_TOOLS)} and, to fetch a published document, {', '.join(RETRIEVAL_TOOLS)}, "
                     "and no others")
    if not isinstance(module.BOUND, int) or isinstance(module.BOUND, bool) or module.BOUND < 1:
        found.append(f"the caller module {path} states a BOUND of {module.BOUND!r}; state a whole number of one or more")
    tables = module.TABLES
    if not isinstance(tables, dict) or not tables or not all(named(name, str) for name in tables):
        bad("TABLES", tables, "give a mapping of each table's name to its columns")
        tables = {}
    for name, spec in tables.items():
        columns = spec.get("columns") if isinstance(spec, dict) else None
        if not isinstance(columns, (list, tuple)) or not texts(columns) or not columns or len(set(columns)) != len(columns):
            bad(f"TABLES[{name!r}]", spec, "give its `columns` as a list of distinct column names")
        elif spec.get("verdict_column") is not None and (not named(spec["verdict_column"], str)
                                                         or spec["verdict_column"] not in columns or not texts(spec.get("verdicts"))):
            bad(f"TABLES[{name!r}]", spec, "give a `verdict_column` among its columns and its `verdicts` as a collection of names")
    findings = module.FINDINGS
    if findings is None:
        return found
    if not isinstance(findings, dict):
        bad("FINDINGS", findings, "give a mapping, or None for a caller with no findings table")
        return found
    table = findings.get("table")
    columns = list(tables[table]["columns"]) if named(table, str) and table in tables and isinstance(
        tables[table], dict) and isinstance(tables[table].get("columns"), (list, tuple)) else None
    if columns is None:
        bad("FINDINGS['table']", table, "name one of TABLES")
    for key in ("number", "item"):
        if columns is not None and findings.get(key) not in columns:
            bad(f"FINDINGS[{key!r}]", findings.get(key), f"name a column of the table {table!r}")
    checklist = findings.get("checklist")
    if not callable(checklist) and (not isinstance(checklist, (list, tuple)) or not texts(checklist)
                                    or len(set(checklist)) != len(checklist)):
        bad("FINDINGS['checklist']", checklist, "give the checklist's items in order as a list of distinct names, or a "
                                              "function of the review folder that returns one")
    citations = findings.get("citations")
    if not isinstance(citations, (list, tuple)) or not all(
            isinstance(pair, (list, tuple)) and len(pair) == 2 and named(pair[0], str) and pair[0] in tables
            and isinstance(tables[pair[0]], dict) and isinstance(tables[pair[0]].get("columns"), (list, tuple))
            and named(pair[1], str) and pair[1] in tables[pair[0]]["columns"] for pair in citations):
        bad("FINDINGS['citations']", citations, "give a list of (table, column) pairs of TABLES")
    pattern = findings.get("citation")
    if not isinstance(pattern, re.Pattern) or "number" not in pattern.groupindex:
        bad("FINDINGS['citation']", pattern, "give a compiled pattern with a `number` group")
    elif "round" in pattern.groupindex:
        for name in ("round", "earlier"):
            if not callable(findings.get(name)):
                found.append(f"the caller module {path} has a citation pattern with a round group but no callable "
                             f"FINDINGS[{name!r}]; add FINDINGS['round'] and FINDINGS['earlier'] or drop the round group")
    if not callable(findings.get("key")):
        bad("FINDINGS['key']", findings.get("key"), "give a function of a findings row")
    if "first" in findings and not callable(findings["first"]):
        bad("FINDINGS['first']", findings["first"], "give a function of the review folder, or leave it out")
    return found


def accepts(call, count: int) -> bool:
    """Whether `call` can be called with `count` positional arguments; a callable whose signature cannot be read is taken to."""
    try:
        inspect.signature(call).bind(*([None] * count))
    except TypeError:
        return False
    except ValueError:
        return True
    return True


def texts(value: Any) -> bool:
    """Whether `value` is a collection of non-empty strings."""
    return isinstance(value, (list, tuple, set, frozenset)) and all(named(item, str) for item in value)


#: What each of a caller's hooks must return, and the words that say so.
RETURNS = {
    "units": (lambda value: isinstance(value, (list, tuple)), "a list of unit names"),
    "unit_prompt": (lambda value: named(value, str), "the unit's prompt as text"),
    "checklist": (lambda value: isinstance(value, (list, tuple)) and texts(value) and len(set(value)) == len(value),
                  "a list of distinct item names"),
    "RENDER": (lambda value: isinstance(value, dict) and all(named(name, str) and isinstance(text, str)
                                                             for name, text in value.items()),
               "a mapping of file name to text"),
    "CHECK": (lambda value: isinstance(value, (list, tuple)) and texts(value), "a list of refusals, each text"),
    "round": (lambda value: named(value, str), "this round's label as text"),
    "earlier": (lambda value: isinstance(value, (list, tuple, set, frozenset)) and all(
        isinstance(pair, (list, tuple)) and len(pair) == 2 and named(pair[0], str) and named(pair[1], int) and pair[1] >= 1
        for pair in value), "a collection of (round label, finding number) pairs"),
    "first": (lambda value: named(value, int) and value >= 1, "a whole number of one or more"),
    "key": (lambda value: value is None or named(value, str), "None or a place as text"),
}


def hook(what: str, call, *args, caller=None):
    """What a caller's hook `call` returns; an exception from it, or a return that is not what RETURNS asks, is a
    refusal naming the hook, and the caller when it is given, never a traceback or a value coerced into shape."""
    fix = f"fix the caller {caller.REVIEW_CALLER_NAME}" if caller is not None else "fix the caller"
    try:
        value = call(*args)
    except Refused:
        raise
    except Exception as error:  # the caller's code is not this command's; its defect is reported, not raised
        raise Refused([f"the caller's {what} raised {type(error).__name__}: {error}; {fix}"])
    allowed, words = RETURNS[what]
    if not allowed(value):
        raise Refused([f"the caller's {what} returned {value!r:.200}, which is not {words}; {fix}"])
    return value


def unit_names(caller, review: str) -> List[str]:
    """The review's units in the order the caller lists them, each a name safe to keep a file under."""
    names = list(hook("units", caller.units, review))
    problems = [f"the unit name {name!r} is not a plain name of letters, digits, dots, dashes and underscores; fix the "
                "caller's units" for name in names if not isinstance(name, str) or not UNIT_NAME.match(name)]
    if len(set(map(repr, names))) != len(names):
        problems.append("the caller lists a unit name twice; each unit needs a name of its own")
    if not names:
        problems.append(f"the caller finds no unit in the review folder {review}; check the folder is the one the "
                        "review's starter wrote")
    if problems:
        raise Refused(problems)
    return names


# --- The agent command line --------------------------------------------------------------------


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
    """Why `source[key]` cannot be relied on: absent, or not of `kind`. The one place the agent output's fields are typed."""
    if not isinstance(source, dict) or source.get(key) is None:
        return f"{where} has no {what}"
    if not named(source[key], kind):
        return f"{where} gives {what} as {source[key]!r}, which is not {KIND_WORDS[kind]}"
    return None


KIND_WORDS = {str: "a non-empty string", list: "a list", dict: "a mapping", bool: "true or false",
              (int, float): "a finite number of zero or more", int: "a whole number of zero or more"}
#: The figures a result report must give for a session that succeeded, with the kind of each.
FIGURE_FIELDS = (("total_cost_usd", (int, float)), ("duration_api_ms", (int, float)), ("num_turns", int))
TOKEN_FIELDS = (("cache_read", "cache_read_input_tokens"), ("cache_write", "cache_creation_input_tokens"),
                ("fresh", "input_tokens"), ("generated", "output_tokens"))
#: The lists a start report must give.
START_LISTS = ("tools", "mcp_servers", "skills", "slash_commands", "plugins")


class Session:
    """One session's start report, tool uses and result report, as the agent command line printed them.

    `malformed` holds every field the command relies on that the output gave
    with the wrong type, and `absent` the figures and text a result report that
    succeeded lacks; neither is ever defaulted.
    """

    def __init__(self):
        self.start: Dict[str, Any] = {}
        self.tool_uses: List[Tuple[str, Dict[str, Any], str]] = []
        self.failed_tool_uses: set = set()
        self.blocks: List[Tuple[str, str]] = []
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
    def succeeded(self) -> bool:
        return self.exit_code == 0 and self.result is not None and self.result.get("is_error") is False

    @property
    def reported(self) -> bool:
        """Whether the result report gave every figure, so the session's cost can be told."""
        result = self.result or {}
        usage = result.get("usage")
        return (all(named(result.get(key), kind) for key, kind in FIGURE_FIELDS) and isinstance(usage, dict)
                and all(named(usage.get(key), int) for _, key in TOKEN_FIELDS))

    def said(self) -> str:
        """What the session returned, for a failure to quote."""
        return board_check.clean(self.text or self.stderr or "nothing")


def agent_program() -> str:
    return os.environ.get(AGENT_ENV) or DEFAULT_AGENT


def require_agent() -> str:
    """The agent command line's path, or a CANNOT RUN naming what to do."""
    program = agent_program()
    found = shutil.which(program)
    if found is None:
        raise board_check.CannotRun(f"the agent command line {program} is not on the search path; install it, or name "
                                    f"the program in the environment variable {AGENT_ENV}")
    try:
        status = subprocess.run([found, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise board_check.CannotRun(f"the agent command line {program} could not report its login ({error}); check it runs")
    try:
        parsed = json.loads(status.stdout)
    except (ValueError, RecursionError):
        parsed = None
    if status.returncode != 0 or not isinstance(parsed, dict) or parsed.get("loggedIn") is not True:
        printed = board_check.clean(status.stdout.strip())[:200] or "nothing"
        raise board_check.CannotRun(f"the agent command line {program} is not logged in: `auth status` exited "
                                    f"{status.returncode} and printed {printed!r}, not an object whose loggedIn is true; "
                                    "log it in, then run again")
    return found


def quiet_arguments() -> List[str]:
    """The flags that start a session with no MCP server and without the instruction sources the command line can exclude."""
    return ["--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
            "--settings", json.dumps({"disableAllHooks": True}), "--exclude-dynamic-system-prompt-sections"]


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
            session.malformed.append(f"printed a line that is not a JSON event: {board_check.clean(line)[:120]!r}")
            continue
        if not isinstance(event, dict):
            session.malformed.append(f"printed a line that is not a JSON event: {board_check.clean(line)[:120]!r}")
            continue
        if not isinstance(event.get("type"), str):
            session.malformed.append(f"printed an event with no string `type`: {board_check.clean(line)[:120]!r}")
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
    if name == "Read" and not named(given.get("file_path"), str):
        session.malformed.append("printed a Read tool use with no string `input.file_path`; it cannot be shown which file was read")
    session.tool_uses.append((name, given, item["id"] if named(item.get("id"), str) else ""))


def parse_result_report(session: Session, result: Dict[str, Any]) -> None:
    """Type the result report's fields: a mistyped one is malformed, and one a session that succeeded lacks is absent."""
    where = "printed a result report that"
    flag = result.get("is_error")
    if not isinstance(flag, bool):
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


def call_agent(program: str, prompt: str, tools: Sequence[str], cwd: str, resume: Optional[str] = None,
               fork: bool = False, model: Optional[str] = None) -> Session:
    """One call of the agent command line, its stream of events read; a call refused for a rate limit raises RateLimited."""
    command = [program, "-p", prompt, "--output-format", "stream-json", "--verbose", "--tools", ",".join(tools),
               "--allowedTools", ",".join(tools), "--permission-mode", "dontAsk"] + quiet_arguments()
    if resume:
        command += ["--resume", resume]
        if fork:
            command += ["--fork-session"]
    if model:
        command += ["--model", model]
    began = time.time()
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env={**os.environ, **QUIET_ENVIRONMENT})
    except (OSError, subprocess.SubprocessError) as error:
        raise board_check.CannotRun(f"the agent command line {program} could not be started ({error}); check it is "
                                    "installed and runs, then run again")
    session = parse_stream(done.stdout)
    session.exit_code, session.stderr = done.returncode, done.stderr.strip()
    session.wall_s = time.time() - began
    result = session.result or {}
    failed = bool(result.get("is_error")) or done.returncode != 0
    if failed and (result.get("api_error_status") == 401 or LOGIN_PATTERN.search(session.stderr)):
        raise board_check.CannotRun(f"the agent command line {program} is not logged in; log it in, then run again")
    if failed and (result.get("api_error_status") == 429 or RATE_PATTERN.search(session.stderr)):
        raise RateLimited(session.said())
    return session


def with_rate_retry(call: Callable[[], Session], wait: float, sleep: Callable[[float], None] = time.sleep) -> Session:
    """`call`, retried after a wait that doubles each time when it is refused for a rate limit, up to RATE_RETRIES times."""
    for attempt in range(RATE_RETRIES + 1):
        try:
            return call()
        except RateLimited as error:
            if attempt == RATE_RETRIES:
                raise UnitFailed(f"still refused for a rate limit after {RATE_RETRIES} retries: {error}")
            sleep(wait * (2 ** attempt))
    raise AssertionError("unreachable")


def start_problems(session: Session, label: str, tools: Sequence[str], model: Optional[str], review: str) -> List[str]:
    """What the session's reports show that they should not, each naming the session.

    A field the command relies on that the output leaves out or gives the wrong
    type is a problem naming the field, never a default.
    """
    found = [f"{label} {why}" for why in session.malformed]
    if session.succeeded and session.absent:
        found.append(f"{label} printed a result report without {', '.join(session.absent)}; its cost and answer cannot be told")
    start = session.start
    if not start:
        return found + [f"{label} printed no start report; check the agent command line prints stream-json events"]
    typed = {}
    for key in ("model", "cwd", "session_id"):
        why = field_problem(start, key, str, f"`{key}`", f"{label}'s start report")
        found += [why] if why else []
        typed[key] = start.get(key) if not why else None
    for key in START_LISTS:
        why = field_problem(start, key, list, f"`{key}`", f"{label}'s start report")
        found += [why] if why else []
        typed[key] = start.get(key) if not why else None
    if typed["tools"] is not None:
        if not all(isinstance(tool, str) for tool in typed["tools"]):
            found.append(f"{label}'s start report gives `tools` as {typed['tools']!r}, which is not a list of names")
        elif sorted(typed["tools"]) != sorted(tools):
            found.append(f"{label} started with tools {sorted(typed['tools'])}, not the {sorted(tools)} it was granted")
    if typed["model"] is not None and model and typed["model"] != model:
        found.append(f"{label} started with model {typed['model']}, not {model}")
    if typed["mcp_servers"]:
        found.append(f"{label} started with MCP servers {typed['mcp_servers']}; none may be loaded")
    if typed["skills"]:
        found.append(f"{label} started with skills {typed['skills']}, which it was asked to exclude")
    if typed["slash_commands"]:
        found.append(f"{label} started with commands {typed['slash_commands']}, which it was asked to exclude")
    outside = [str(plugin.get("name") if isinstance(plugin, dict) else plugin) for plugin in typed["plugins"] or []
               if not (isinstance(plugin, dict) and plugin.get("path") == "builtin")]
    if outside:
        found.append(f"{label} started with plugins {outside}, which it was asked to exclude")
    if typed["cwd"] is not None and not same_path(typed["cwd"], review):
        found.append(f"{label} started in {typed['cwd']!r}, not the review folder {review}")
    return found


def same_path(given: str, folder: str) -> bool:
    """Whether a path the agent command line printed is `folder`; one that cannot be a path is not."""
    try:
        return os.path.realpath(given) == os.path.realpath(folder)
    except (ValueError, OSError):
        return False


def non_text(path: str, review: str) -> bool:
    """Whether a read of `path` opens a file whose type is not text, or one that cannot be shown to be text."""
    full = path if os.path.isabs(path) else os.path.join(review, path)
    if full.lower().endswith(NON_TEXT_SUFFIXES):
        return True
    try:
        with open(full, "rb") as handle:
            head = handle.read(8192)
    except (OSError, ValueError):
        return True
    if b"\0" in head:
        return True
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as error:
        return error.start < len(head) - 4
    return False


def setup_problems(session: Session, review: str) -> List[str]:
    """What the setup session's history shows: an image opened, a tool outside its grant, nothing read, or text that may be a judgement."""
    found = []
    reads = 0
    for name, given, use in session.tool_uses:
        if name not in READ_TOOLS:
            found.append(f"the setup session used {name}, a tool it was not granted")
        elif name == "Read":
            reads += 1
            path = given.get("file_path")
            if not isinstance(path, str):
                continue  # the start_problems naming the missing file_path fails the run
            if use and use in session.failed_tool_uses:
                continue  # the stream itself shows the read failed, so it opened nothing
            if non_text(path, review):
                found.append(f"the setup session opened {path}, a file whose type is not text, or cannot be shown to be "
                             "text; it may read documents and records only, so the forked reviewers stay as blind as fresh ones")
    if not reads:
        found.append("the setup session read nothing; it must read what its prompt asks before a fork can start from it")
    for kind, text in session.blocks:
        if kind == "text" and text.strip() not in ("", ACK):
            found.append(f"the setup session wrote {board_check.clean(text.strip())[:200]!r} between or before its answer; it "
                         "may write only the token, or a forked reviewer would inherit what it wrote")
        elif kind not in ("text", "tool_use"):
            found.append(f"the setup session's history holds a {kind} block, which cannot be shown to hold no verdict; "
                         "a forked reviewer would inherit it")
    if session.text.strip() != ACK:
        found.append(f"the setup session answered {board_check.clean(session.text.strip())[:200]!r} and not {ACK}; "
                     "it may judge nothing, or a forked reviewer would inherit the verdict")
    return found


# --- What a session cost -----------------------------------------------------------------------


def figures(session: Session) -> Dict[str, Any]:
    """The cumulative figures a result report gives, and the tokens as the session reports them; zero when it gave none."""
    if not session.reported:
        return {**empty_figures(), "wall_s": round(session.wall_s, 3)}
    result, usage = session.result, session.result["usage"]
    return {"cost_usd": float(result["total_cost_usd"]), "api_ms": int(result["duration_api_ms"]),
            "turns": int(result["num_turns"]), "wall_s": round(session.wall_s, 3),
            "tokens": {key: int(usage[field]) for key, field in TOKEN_FIELDS}}


def own(cumulative: Dict[str, Any], setup: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """A session's own figures: its cumulative cost, API time and turns less the setup session's it includes."""
    taken = setup or {"cost_usd": 0, "api_ms": 0, "turns": 0}
    return {"cost_usd": round(cumulative["cost_usd"] - taken["cost_usd"], 6),
            "api_ms": cumulative["api_ms"] - taken["api_ms"], "turns": cumulative["turns"] - taken["turns"],
            "wall_s": cumulative["wall_s"], "tokens": dict(cumulative["tokens"])}


def below(cumulative: Dict[str, Any], setup: Optional[Dict[str, Any]]) -> List[str]:
    """The cumulative figures that are lower than those of the session they include, so the session's own cannot be told."""
    taken = setup or {}
    return [key for key in ("cost_usd", "api_ms", "turns") if cumulative[key] < taken.get(key, 0)]


def total(parts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    tokens = {key: sum(part["tokens"][key] for part in parts) for key in ("cache_read", "cache_write", "fresh", "generated")}
    return {"cost_usd": round(sum(part["cost_usd"] for part in parts), 6), "api_ms": sum(part["api_ms"] for part in parts),
            "turns": sum(part["turns"] for part in parts), "wall_s": round(sum(part["wall_s"] for part in parts), 3),
            "tokens": tokens}


# --- The merge ---------------------------------------------------------------------------------


def parse_result(text: str) -> Dict[str, Any]:
    """The tables a reviewer returned: a JSON object, alone or in a code fence, with a `tables` mapping."""
    body = text.strip()
    fenced = re.match(r"^```[a-z]*\n(.*)\n```$", body, re.DOTALL)
    body = fenced.group(1) if fenced else body
    try:
        found = json.loads(body)
    except (ValueError, RecursionError):
        raise Malformed(["the reviewer's answer is not a JSON object"])
    if not isinstance(found, dict) or not isinstance(found.get("tables"), dict):
        raise Malformed(["the reviewer's answer has no `tables` mapping"])
    return found["tables"]


def table_problems(caller, review: str, unit: str, tables: Dict[str, Any]) -> List[str]:
    """Why a unit's tables are not what the caller allows: a table, column or verdict it does not have."""
    declared, found = caller.TABLES, []
    for name, rows in tables.items():
        if name not in declared:
            found.append(f"unit {unit} returned a table {name!r} the caller does not have; the tables are {sorted(declared)}")
            continue
        columns = list(declared[name]["columns"])
        if not isinstance(rows, list):
            found.append(f"unit {unit}'s table {name!r} is not a list of rows")
            continue
        for number, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                found.append(f"unit {unit}'s table {name!r} row {number} is not a mapping of column to cell")
                continue
            extra, absent = sorted(set(row) - set(columns)), [column for column in columns if column not in row]
            if extra:
                found.append(f"unit {unit}'s table {name!r} row {number} has a column {extra} the caller's table does not have; "
                             f"its columns are {columns}")
            if absent:
                found.append(f"unit {unit}'s table {name!r} row {number} lacks the column {absent}")
            odd = [column for column in columns if column in row and not cell(row[column])]
            if odd:
                found.append(f"unit {unit}'s table {name!r} row {number} has " + ", ".join(
                    f"{column!r} as {row[column]!r:.80}" for column in odd) + ", not text or a finite number")
            verdict = declared[name].get("verdict_column")
            if verdict and verdict in row and (not isinstance(row[verdict], str)
                                               or row[verdict] not in declared[name]["verdicts"]):
                found.append(f"unit {unit}'s table {name!r} row {number} has the verdict {row[verdict]!r}, outside "
                             f"{list(declared[name]['verdicts'])}")
    findings = caller.FINDINGS
    if findings and not found:
        found += finding_problems(findings, review, unit, tables)
    return found


def cell(value: Any) -> bool:
    """Whether a table cell is text or a finite number, the only cells a record holds."""
    if isinstance(value, str):
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


def this_round(findings: Dict[str, Any], review: str) -> Optional[str]:
    """This round's label when the caller's citation pattern carries a round, otherwise None."""
    return hook("round", findings["round"], review) if "round" in findings["citation"].groupindex else None


def finding_problems(findings: Dict[str, Any], review: str, unit: str, tables: Dict[str, Any]) -> List[str]:
    found, numbers = [], []
    for row in tables.get(findings["table"], []):
        number = row[findings["number"]]
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            found.append(f"unit {unit} numbered a finding {number!r}; a reviewer numbers its findings with whole numbers from 1")
        elif number in numbers:
            found.append(f"unit {unit} numbered two findings {number}")
        else:
            numbers.append(number)
        if row[findings["item"]] not in findings["checklist"]:
            found.append(f"unit {unit} raised a finding on {row[findings['item']]!r}, which is no item of the checklist")
    current = this_round(findings, review)
    earlier = {(round_, number) for round_, number in hook("earlier", findings["earlier"], review)
               } if current is not None else set()
    for table, column in findings["citations"]:
        for row in tables.get(table, []):
            for match in findings["citation"].finditer(str(row[column])):
                if current is None or match.group("round") == current:
                    if int(match.group("number")) not in numbers:
                        found.append(f"unit {unit}'s {table!r} row cites a finding {match.group('number')} the unit did not raise")
                elif (match.group("round"), int(match.group("number"))) not in earlier:
                    found.append(f"unit {unit}'s {table!r} {column!r} cell {str(row[column])!r} cites {match.group(0)!r}, a "
                                 f"finding of round {match.group('round')} that the review folder's earlier rounds do not "
                                 f"hold (this round is {current}); cite only findings the earlier rounds raised")
    return found


def merge(caller, review: str, order: Sequence[str], results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The units' tables as one record. Units are taken in `order`, never in the order they arrived in.

    It rejects a table, column or verdict the caller does not have, replaces
    every finding number of this round with the one the checklist's order gives
    and rewrites the citations of them in the rows that cite them, leaves any
    citation the caller's pattern does not match, or whose round is an earlier
    one, as written, and reports findings
    the caller's key puts at one place, keeping each. It reads no model and no
    file outside the unit results and the review folder.
    """
    problems = []
    for unit in order:
        problems += table_problems(caller, review, unit, results[unit])
    if problems:
        raise Refused(problems)
    rows = {name: [(unit, dict(row)) for unit in order for row in results[unit].get(name, [])] for name in caller.TABLES}
    same_place: List[Dict[str, Any]] = []
    findings = caller.FINDINGS
    if findings:
        renamed, same_place = renumber(findings, review, order, results, rows)
        current = this_round(findings, review)
        for table, column in findings["citations"]:
            for unit, row in rows[table]:
                row[column] = findings["citation"].sub(
                    lambda match, unit=unit: (match.group(0) if current is not None and match.group("round") != current
                                              else replace_number(match, renamed, unit)), str(row[column]))
    tables = {name: {"columns": list(spec["columns"]), "rows": [row for _, row in rows[name]]}
              for name, spec in caller.TABLES.items()}
    refused = hook("CHECK", caller.CHECK, review, list(order), tables)
    if refused:
        raise Refused(refused)
    return {"tables": tables, "same_place": same_place}


def renumber(findings: Dict[str, Any], review: str, order: Sequence[str], results: Dict[str, Dict[str, Any]],
             rows: Dict[str, List[Tuple[str, Dict[str, Any]]]]) -> Tuple[Dict[Tuple[str, int], int], List[Dict[str, Any]]]:
    """This round's findings numbered in the checklist's order; each unit's old number against its new, and the findings at one place."""
    first = hook("first", findings["first"], review) if callable(findings.get("first")) else 1
    checklist = list(findings["checklist"])
    raised = sorted(((checklist.index(row[findings["item"]]), order.index(unit), row[findings["number"]], unit, row)
                     for unit, row in rows[findings["table"]]), key=lambda entry: entry[:3])
    renamed: Dict[Tuple[str, int], int] = {}
    for offset, (_, _, old, unit, row) in enumerate(raised):
        renamed[(unit, old)] = first + offset
        row[findings["number"]] = first + offset
    rows[findings["table"]] = [(unit, row) for _, _, _, unit, row in raised]
    groups: Dict[str, List[Tuple[int, str]]] = {}
    for _, _, _, unit, row in raised:
        key = hook("key", findings["key"], row)
        if key is not None:
            groups.setdefault(key, []).append((row[findings["number"]], unit))
    same = [{"key": key, "findings": sorted(number for number, _ in members),
             "units": sorted({unit for _, unit in members})}
            for key, members in groups.items() if len(members) > 1]
    return renamed, sorted(same, key=lambda place: place["findings"][0])


def replace_number(match: "re.Match", renamed: Dict[Tuple[str, int], int], unit: str) -> str:
    """The matched citation with the digits of the finding it names swapped for the number the merge gave it."""
    whole, (start, end) = match.group(0), match.span("number")
    new = renamed[(unit, int(match.group("number")))]
    return whole[:start - match.start()] + str(new) + whole[end - match.start():]


# --- Files ----------------------------------------------------------------------------------------


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(path: str, content: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scratch = f"{path}.part"
    with open(scratch, "w", encoding="utf-8") as handle:
        json.dump(content, handle, indent=1, sort_keys=True)
        handle.write("\n")
    os.replace(scratch, path)


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# --- The records kept in the output folder -------------------------------------------------------

#: A string that may be empty, as a session's id is when it printed no start report.
ANY_TEXT = "any text"
KIND_WORDS[ANY_TEXT] = "text"
#: The figures every kept session and setup session carries, as `figures` and `own` make them.
FIGURES_SHAPE = {"cost_usd": (int, float), "api_ms": int, "turns": int, "wall_s": (int, float),
                 "tokens": {"cache_read": int, "cache_write": int, "fresh": int, "generated": int}}
SESSION_SHAPE = {**FIGURES_SHAPE, "attempt": int, "session": ANY_TEXT, "mode": str, "flags": [str]}
SETUP_SHAPE = {**FIGURES_SHAPE, "id": str, "at": str, "kind": str, "units": [str], "model": str}
RERUN_SHAPE = {"at": str, "units": [str], "new_setup_session": bool, "setup_session": str}
UNIT_SHAPE = {"unit": str, "tables": dict, "raw": str, "sessions": [SESSION_SHAPE], "superseded": [SESSION_SHAPE],
              "ran_at": str, "setup": int, "attempts": int}


def shape_problem(value: Any, shape: Any, where: str) -> Optional[str]:
    """Why a kept record is not of `shape`: a mapping of keys to shapes, a one-item list of the shape of each item, or
    a kind. The one place the records read back from the output folder are typed."""
    if isinstance(shape, dict):
        if not isinstance(value, dict):
            return f"{where} is not a mapping"
        for key, inner in shape.items():
            why = f"{where} has no `{key}`" if key not in value else shape_problem(value[key], inner, f"{where}.{key}")
            if why:
                return why
        return None
    if isinstance(shape, list):
        if not isinstance(value, list):
            return f"{where} is not a list"
        for number, item in enumerate(value):
            why = shape_problem(item, shape[0], f"{where}[{number}]")
            if why:
                return why
        return None
    if shape is ANY_TEXT and isinstance(value, str) or shape is not ANY_TEXT and named(value, shape):
        return None
    return f"{where} is {value!r:.80}, not {KIND_WORDS[shape]}"


def read_record(path: str, shape: Any, what: str, advice: str, extra: Callable[[Any], Optional[str]] = lambda _: None) -> Any:
    """A record kept in the output folder, typed against `shape` and `extra`; one that cannot be read or is not of its
    shape is a refusal naming the file and what to do, never a traceback or a default."""
    try:
        content = read_json(path)
    except (OSError, ValueError, RecursionError) as error:
        why = str(error)
    else:
        why = shape_problem(content, shape, os.path.basename(path)) or extra(content)
        if why is None:
            return content
    raise Refused([f"the {what} {path} cannot be read ({why}); {advice}"])


RESTORE = "restore it, or run into a new output folder"


def kept_setups(folder: str) -> List[Dict[str, Any]]:
    path = os.path.join(folder, SETUPS)
    return read_record(path, [SETUP_SHAPE], "list of setup sessions", RESTORE) if os.path.lexists(path) else []


def kept_reruns(folder: str) -> List[Dict[str, Any]]:
    path = os.path.join(folder, RERUNS)
    return read_record(path, [RERUN_SHAPE], "list of runs again", RESTORE) if os.path.lexists(path) else []


def kept_result(folder: str, unit: str, setups: int) -> Dict[str, Any]:
    """The unit's kept result, which names the unit, holds a session for each attempt and cites a kept setup session."""
    def extra(kept: Dict[str, Any]) -> Optional[str]:
        if kept["unit"] != unit:
            return f"it holds unit {kept['unit']!r}"
        if not kept["sessions"] or kept["attempts"] < 1:
            return "it holds no attempt"
        if kept["setup"] >= setups:
            return f"it cites setup session {kept['setup']}, and the list of setup sessions holds {setups}"
        return None
    return read_record(os.path.join(folder, UNITS_FOLDER, f"{unit}.json"), UNIT_SHAPE, f"kept result of unit {unit}",
                       f"restore it, or name {unit} with --rerun to judge it again", extra)


def kept_failed(folder: str, unit: str) -> List[Dict[str, Any]]:
    path = os.path.join(folder, FAILED_FOLDER, f"{unit}.json")
    return read_record(path, [SESSION_SHAPE], f"record of unit {unit}'s failed attempts",
                       "restore it, or delete it to run the unit again without its cost") if os.path.lexists(path) else []


def folder_problems(folder: str, order: Sequence[str]) -> List[str]:
    """Why a record the output folder keeps for this review cannot be read, each naming its file."""
    found: List[str] = []
    setups: List[Dict[str, Any]] = []
    for read in (lambda: setups.extend(kept_setups(folder)), lambda: kept_reruns(folder)):
        try:
            read()
        except Refused as error:
            found += error.causes
    for unit in order:
        reads = [lambda unit=unit: kept_failed(folder, unit)]
        if os.path.lexists(os.path.join(folder, UNITS_FOLDER, f"{unit}.json")):
            reads.append(lambda unit=unit: kept_result(folder, unit, len(setups)))
        for read in reads:
            try:
                read()
            except Refused as error:
                found += error.causes
    return found


def holds_any(folder: str) -> bool:
    return os.path.isdir(folder) and bool(os.listdir(folder))


# --- The run -----------------------------------------------------------------------------------


class Run:
    """One run of the command: a caller's review, judged unit by unit, into an output folder."""

    def __init__(self, caller, review: str, out: str, program: str, bound: int, model: Optional[str], wait: float,
                 sleep: Callable[[float], None] = time.sleep):
        self.caller, self.review, self.out, self.program = caller, review, out, program
        self.bound, self.model, self.wait, self.sleep = bound, model, wait, sleep

    def unit_path(self, unit: str) -> str:
        return os.path.join(self.out, UNITS_FOLDER, f"{unit}.json")

    def failed_path(self, unit: str) -> str:
        return os.path.join(self.out, FAILED_FOLDER, f"{unit}.json")

    def unsettled_path(self, unit: str) -> str:
        return os.path.join(self.out, UNSETTLED_FOLDER, f"{unit}.json")

    def earlier_sessions(self, unit: str) -> List[Dict[str, Any]]:
        """The sessions the unit already cost in earlier runs: those behind its kept result and its failed attempts."""
        found: List[Dict[str, Any]] = []
        if os.path.lexists(self.unit_path(unit)):
            kept = kept_result(self.out, unit, len(kept_setups(self.out)))
            found += kept["superseded"] + kept["sessions"]
        return found + self.failed_sessions(unit)

    def judge(self, unit: str, resume: str, fork: bool, setup: Dict[str, Any], model: str, setup_index: int) -> Dict[str, Any]:
        """One unit, run once more when its reviewer errors, returns nothing or returns tables the caller does not allow."""
        label, sessions, last = f"the reviewer of unit {unit}", [], "nothing"
        # A fork reports the setup session's figures with its own, and so does a turn resumed without a fork, which
        # also reports the turns before it.
        base = setup["cumulative"]
        try:
            prompt = hook("unit_prompt", self.caller.unit_prompt, unit, self.review, caller=self.caller)
            for number in (1, 2):
                try:
                    session = with_rate_retry(lambda: call_agent(self.program, prompt, self.caller.TOOLS, self.review, resume,
                                                                 fork, model), self.wait, self.sleep)
                except UnitFailed as error:
                    raise UnitFailed(f"unit {unit} failed: {error}", sessions)
                cumulative = figures(session)
                short = below(cumulative, base) if session.reported else []
                # A session that gave no figures, or figures below those it includes, cost nothing that can be told.
                figure = own(cumulative, base) if session.reported and not short else {**empty_figures(), "wall_s": cumulative["wall_s"]}
                if not fork and session.reported and not short:
                    base = cumulative
                flags = ["no report"] if not session.reported else ["figures below those it includes"] if short else (
                    ["no cache read"] if fork and figure["tokens"]["cache_read"] == 0 else [])
                sessions.append({"attempt": number, "session": session.id, "mode": "fork" if fork else "setup session",
                                 "flags": flags, **figure})
                problems = start_problems(session, label, self.caller.TOOLS, model, self.review) + (
                    [f"{label} reported a cumulative {', '.join(short)} below that of the session it was resumed from, so "
                     "its own cannot be told"] if short else [])
                if problems:
                    raise UnitFailed(f"unit {unit} failed: " + "; ".join(problems), sessions)
                result = session.result or {}
                if session.exit_code != 0 or result.get("is_error") or not session.text.strip():
                    last = session.said()
                    continue
                try:
                    tables = parse_result(session.text)
                    problems = table_problems(self.caller, self.review, unit, tables)
                    if problems:
                        raise Malformed(problems)
                except Malformed as error:
                    last = f"{error}: {board_check.clean(session.text)[:300]}"
                    continue
                kept = {"unit": unit, "tables": tables, "raw": session.text, "sessions": sessions, "ran_at": stamp(),
                        "setup": setup_index, "attempts": number, "superseded": self.earlier_sessions(unit)}
                write_json(self.unit_path(unit), kept)
                for settled in (self.failed_path(unit), self.unsettled_path(unit)):
                    if os.path.lexists(settled):
                        os.remove(settled)
                return kept
            raise UnitFailed(f"unit {unit} failed after {len(sessions)} attempts; the reviewer returned: {last}", sessions)
        except UnitFailed:
            raise
        except Refused as error:
            raise UnitFailed(f"unit {unit} failed: {'; '.join(error.causes)}", sessions)
        except board_check.CannotRun as error:
            raise LoginLost(unit, str(error), sessions)
        except Exception as error:  # a defect in one unit's worker is that unit's failure and the others go on
            raise UnitFailed(f"unit {unit} failed: {type(error).__name__}: {error}", sessions)

    def resolve_checklist(self) -> None:
        """A checklist given as a function becomes its list, once, before the setup session starts, so the per-unit
        checks and the merge read the same list; a list is left as it is."""
        findings = self.caller.FINDINGS
        if findings and callable(findings["checklist"]):
            listed = hook("checklist", findings["checklist"], self.review, caller=self.caller)
            self.caller.FINDINGS = {**findings, "checklist": list(listed)}

    def setup_session(self, model: Optional[str]) -> Tuple[Session, Dict[str, Any]]:
        """The checked setup session and its figures; anything that stops the check is a refusal, never a traceback."""
        try:
            return self.checked_setup(model)
        except (Refused, board_check.CannotRun):
            raise
        except Exception as error:  # the setup session's output is not this command's; what it breaks is reported
            raise Refused([f"the setup session could not be checked ({type(error).__name__}: {error}); check the agent "
                           "command line's output, then run again"])

    def checked_setup(self, model: Optional[str]) -> Tuple[Session, Dict[str, Any]]:
        prompt = f"{self.caller.SETUP_PROMPT.rstrip()}\n\n{ACK_INSTRUCTION}"
        try:
            session = with_rate_retry(lambda: call_agent(self.program, prompt, READ_TOOLS, self.review, model=model),
                                      self.wait, self.sleep)
        except UnitFailed as error:
            raise Refused([f"the setup session {error}; wait, then run again"])
        problems = start_problems(session, "the setup session", READ_TOOLS, model, self.review)
        result = session.result or {}
        if session.exit_code != 0 or result.get("is_error") is not False:
            raise Refused(problems + [f"the setup session failed and returned: {session.said()}; check the agent command "
                                      "line runs from the review folder, then run again"])
        problems += setup_problems(session, self.review)
        if problems:
            raise Refused(problems)
        return session, figures(session)

    def failed_sessions(self, unit: str) -> List[Dict[str, Any]]:
        return kept_failed(self.out, unit)

    def run(self, order: Sequence[str], named: Sequence[str]) -> Tuple[Dict[str, Any], Dict[str, Optional[UnitFailed]]]:
        """Judge `named` units (all of `order` when none), returning the setup entry and each unit's failure, if any."""
        self.resolve_checklist()
        session, cumulative = self.setup_session(self.model)
        model = session.start["model"]
        setup = {"id": session.id, "at": stamp(), "kind": "rerun" if named else "initial",
                 "units": list(named or order), "model": model, "cumulative": cumulative, **own(cumulative, None)}
        known = kept_setups(self.out)
        setup_index = len(known)
        write_json(os.path.join(self.out, SETUPS), known + [{key: value for key, value in setup.items() if key != "cumulative"}])
        failures: Dict[str, Optional[UnitFailed]] = {}
        todo = list(named or order)
        fork = len(order) > 1
        # Each unit named to run again is unsettled from before its reviewer starts until its result is kept, so
        # whatever stops it, a later run that leaves it out is refused.
        for unit in named:
            write_json(self.unsettled_path(unit), {"unit": unit, "at": setup["at"], "setup_session": setup["id"]})

        def one(unit: str) -> None:
            try:
                self.judge(unit, session.id, fork, setup, model, setup_index)
                failures[unit] = None
            except UnitFailed as error:
                failures[unit] = error
                try:
                    if error.sessions:
                        write_json(self.failed_path(unit), self.failed_sessions(unit) + error.sessions)
                except (OSError, Refused) as lost:
                    failures[unit] = UnitFailed(f"{error}; its cost could not be kept ({lost})", error.sessions)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.bound) as pool:
            if fork:
                list(pool.map(one, todo))
            else:
                one(todo[0])
        return setup, failures


# --- The report --------------------------------------------------------------------------------


def empty_figures() -> Dict[str, Any]:
    return {"cost_usd": 0.0, "api_ms": 0, "turns": 0, "wall_s": 0.0,
            "tokens": {"cache_read": 0, "cache_write": 0, "fresh": 0, "generated": 0}}


def figure_line(part: Dict[str, Any]) -> str:
    tokens = part["tokens"]
    return (f"{part['api_ms']} ms API | {part['wall_s']} s | {part['turns']} turns | ${part['cost_usd']} | "
            f"read {tokens['cache_read']} wrote {tokens['cache_write']} fresh {tokens['fresh']} generated {tokens['generated']}")


def render_text(report: Dict[str, Any]) -> List[str]:
    clean = board_check.clean
    lines = [f"RUN | {clean(report['caller'])} | {clean(report['review'])} | {clean(report['out'])}"]
    lines += [f"REFUSED | {clean(why)}" for why in report["refusals"]]
    if report["cannot_run"]:
        lines.append(f"CANNOT RUN | {clean(report['cannot_run'])}")
    for setup in report["setup_sessions"]:
        lines.append(f"SETUP | {setup['id']} | {setup['kind']} | {setup['model']} | {setup['at']} | "
                     f"units {', '.join(setup['units'])} | {figure_line(setup)}")
    for unit in report["units"]:
        flags = "; ".join(unit["flags"]) or "no flag"
        lines.append(f"UNIT | {unit['unit']} | {unit['status']} | {unit['mode']} | {unit['session']} | "
                     f"{unit['attempts']} attempts | {figure_line(unit['own'])} | {clean(flags)} | "
                     f"ran {unit['ran_at'] or 'never kept'} | setup session {unit['setup_session']}"
                     + (" | run again" if unit["run_again"] else ""))
        if unit["status"] == "failed":
            lines.append(f"FAILED | {clean(unit['detail'])}")
    for rerun in report["reruns"]:
        lines.append(f"RERUN | {', '.join(rerun['units'])} | {rerun['at']} | new setup session {rerun['setup_session']}")
    for name in report.get("rendered", []):
        lines.append(f"RENDERED | {clean(name)}")
    for name in report.get("not_this_merge", []):
        lines.append(f"NOT THIS MERGE | {clean(name)} | written by an earlier merge, not by this one")
    for place in report["same_place"]:
        lines.append(f"SAME PLACE | {clean(place['key'])} | findings {', '.join(str(n) for n in place['findings'])} | "
                     f"units {', '.join(place['units'])}")
    if report["setup_sessions"] or report["units"]:
        lines.append(f"TOTAL | {figure_line(report['totals'])}")
    for name, table in report["tables"].items():
        lines.append(f"TABLE | {clean(name)} | columns {clean(', '.join(table['columns']))} | {len(table['rows'])} rows")
        for row in table["rows"]:
            lines.append(f"ROW | {clean(name)} | " + " | ".join(f"{clean(column)} {clean(row[column])}" for column in table["columns"]))
    lines.append(f"RESULT | {report['result']} | {clean(report['detail'])}")
    return lines


def new_report(caller_name: str, review: str, out: str) -> Dict[str, Any]:
    return {"result": "REFUSED", "detail": "nothing was run", "caller": caller_name, "review": review, "out": out,
            "refusals": [], "cannot_run": None, "units": [], "setup_sessions": [], "reruns": [], "same_place": [],
            "totals": empty_figures(), "tables": {}}


def unit_entry(kept: Dict[str, Any], rerun: bool, setups: List[Dict[str, Any]], failed: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """A kept unit; its own figures are every session it cost, the earlier runs' and failed attempts' included."""
    final = kept["sessions"][-1]
    behind = kept["sessions"] + kept.get("superseded", []) + list(failed)
    flags = sorted({flag for session in kept["sessions"] for flag in session["flags"]})
    return {"unit": kept["unit"], "status": "judged", "mode": final["mode"], "session": final["session"],
            "attempts": kept["attempts"], "own": total(behind), "flags": flags, "run_again": rerun,
            "detail": "", "ran_at": kept["ran_at"], "setup_session": setups[kept["setup"]]["id"]}


def finish(report: Dict[str, Any], out_stream, as_json: bool, err) -> int:
    status = {"WRITTEN": 0, "REFUSED": 1, "FAILED": 1, "CANNOT RUN": 2}[report["result"]]
    if as_json:
        json.dump(report, out_stream, indent=1)
        out_stream.write("\n")
    else:
        for line in render_text(report):
            print(line, file=err if line.startswith("CANNOT RUN") else out_stream)
    return status


def main(argv: Optional[List[str]] = None, out=sys.stdout, err=sys.stderr) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--caller", required=True, help="the caller's name: the module review_caller_<name>")
    parser.add_argument("--callers", default=TOOLS_DIR, help="the folder to look for caller modules in (default: this tool's folder)")
    parser.add_argument("--review", required=True, help="the review folder the reviewers read, outside the repository")
    parser.add_argument("--out", required=True, help="the output folder the results are kept in, apart from the review folder and outside the repository")
    parser.add_argument("--bound", default=None, help="the most reviewers at once (default: the caller's)")
    parser.add_argument("--model", default=None, help="the model every session uses (default: the agent command line's own)")
    parser.add_argument("--rerun", action="append", default=[], help="a unit to run again, with the others' kept results merged; repeat for each")
    parser.add_argument("--rate-limit-wait", default="5", help="seconds before the first retry of a call refused for a rate limit; it doubles each time")
    parser.add_argument("--json", action="store_true", help="print the report as one JSON document")
    args = parser.parse_args(argv)
    review, folder = os.path.abspath(args.review), os.path.abspath(args.out)
    report = new_report(args.caller, review, folder)

    def refuse(causes: Sequence[str]) -> int:
        report["refusals"] += list(causes)
        return finish(report, out, args.json, err)

    causes = refusals(review, folder, REPO)
    bound = None
    if args.bound is not None:
        try:
            bound = int(args.bound)
        except ValueError:
            causes.append(f"the bound {args.bound!r} is not a whole number; give one or more")
        else:
            if bound < 1:
                causes.append(f"the bound {bound} is below one; give one or more reviewers at once")
    try:
        wait = float(args.rate_limit_wait)
    except ValueError:
        wait = None
    if wait is None or not named(wait, (int, float)):
        causes.append(f"the rate limit wait {args.rate_limit_wait!r} is not a finite number of seconds of zero or more; give one")
    if args.model is not None and not named(args.model, str):
        causes.append(f"the model {args.model!r} is empty; give a full model id, or leave --model out")
    try:
        caller = load_caller(args.caller, os.path.abspath(args.callers))
    except Refused as error:
        causes += error.causes
        caller = None
    if causes or caller is None:
        return refuse(causes)
    try:
        order = unit_names(caller, review)
    except Refused as error:
        return refuse(error.causes)
    named_units = list(dict.fromkeys(args.rerun))
    unknown = [name for name in named_units if name not in order]
    if unknown:
        return refuse([f"{', '.join(unknown)} is not a unit of the review; the units are {', '.join(order)}"])
    created = not os.path.isdir(folder)
    lock = os.path.join(folder, LOCK)
    try:
        os.makedirs(folder, exist_ok=True)
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return refuse([f"the output folder {folder} is in use by another run (it holds {LOCK}); wait for that run, or "
                       "delete the file if no run is in the folder"])
    except OSError as error:
        return refuse([f"the output folder {folder} cannot be written ({error}); give a folder this user can write"])
    os.close(handle)
    try:
        held = any(os.path.lexists(os.path.join(folder, name)) for name in (RECORD, SETUPS, RERUNS)) or any(
            holds_any(os.path.join(folder, name)) for name in (UNITS_FOLDER, FAILED_FOLDER, UNSETTLED_FOLDER))
        if held and not named_units:
            return refuse([f"the output folder {folder} already holds a record; give a new or empty folder, or name the "
                           "units to run again with --rerun"])
        if named_units and not held:
            return refuse([f"the output folder {folder} holds no earlier result to run {', '.join(named_units)} again "
                           "against; run without --rerun into a new folder first"])
        if named_units:
            lacking = [name for name in order if name not in named_units
                       and not os.path.lexists(os.path.join(folder, UNITS_FOLDER, f"{name}.json"))]
            if lacking:
                return refuse([f"the output folder holds no result for {', '.join(lacking)}; name each of them with --rerun too"])
            unreadable = folder_problems(folder, order)
            unsettled = [name for name in order if name not in named_units
                         and os.path.lexists(os.path.join(folder, UNSETTLED_FOLDER, f"{name}.json"))]
            if unreadable or unsettled:
                return refuse(unreadable + [f"unit {name}'s last run again failed, so its kept result is not settled; name "
                                            f"{name} with --rerun too" for name in unsettled])
        try:
            program = require_agent()
        except board_check.CannotRun as error:
            report["result"], report["cannot_run"], report["detail"] = "CANNOT RUN", str(error), "nothing was run"
            return finish(report, out, args.json, err)
        return execute(report, caller, review, folder, order, named_units, program, bound or caller.BOUND, wait, args, out, err)
    finally:
        os.remove(lock)
        if created and not os.listdir(folder):
            os.rmdir(folder)


def execute(report, caller, review, folder, order, named, program, bound, wait, args, out, err) -> int:
    run = Run(caller, review, folder, program, bound, args.model, wait)
    try:
        setup, failures = run.run(order, named)
    except board_check.CannotRun as error:
        report["result"], report["cannot_run"], report["detail"] = "CANNOT RUN", str(error), (
            f"this run kept nothing; the earlier results stay in {folder}" if named else "nothing was kept")
        return finish(report, out, args.json, err)
    except Refused as error:
        report["refusals"] += error.causes
        report["detail"] = "no unit was started"
        return finish(report, out, args.json, err)
    except OSError as error:
        report["refusals"].append(f"the output folder {folder} could not be written ({error}); give a folder this user "
                                  "can write, then run again")
        report["detail"] = "no unit was started"
        return finish(report, out, args.json, err)
    try:
        return report_run(report, run, caller, review, folder, order, named, setup, failures, args, out, err)
    except Refused as error:
        report["refusals"] += error.causes
        report["detail"] = f"a kept record could not be read back; the units' results are kept in {folder}"
        return finish(report, out, args.json, err)


def report_run(report, run, caller, review, folder, order, named, setup, failures, args, out, err) -> int:
    setups = kept_setups(folder)
    report["setup_sessions"] = list(setups)
    results, parts = {}, []
    for unit in order:
        failed = failures.get(unit)
        if failed:
            detail = str(failed)
            try:
                behind = run.earlier_sessions(unit)
            except Refused as error:
                behind = list(failed.sessions)
                detail += f"; its earlier cost could not be read ({'; '.join(error.causes)})"
            report["units"].append({"unit": unit, "status": "failed", "mode": "fork" if len(order) > 1 else "setup session",
                                    "session": failed.sessions[-1]["session"] if failed.sessions else "",
                                    "attempts": len(failed.sessions), "own": total(behind) if behind else empty_figures(),
                                    "flags": sorted({flag for session in behind for flag in session["flags"]}),
                                    "run_again": unit in named, "detail": detail, "ran_at": "", "setup_session": setup["id"]})
            continue
        kept = kept_result(folder, unit, len(setups))
        results[unit] = kept["tables"]
        report["units"].append(unit_entry(kept, unit in named, setups, run.failed_sessions(unit)))
    for entry in report["units"]:
        parts.append(entry["own"])
    report["totals"] = total([{key: entry[key] for key in empty_figures()} for entry in setups] + parts)
    again = kept_reruns(folder)
    if named:
        again.append({"at": setup["at"], "units": list(named), "new_setup_session": True, "setup_session": setup["id"]})
        write_json(os.path.join(folder, RERUNS), again)
    report["reruns"] = again
    broken = [unit for unit in order if failures.get(unit)]
    if broken:
        report["result"], report["detail"] = "FAILED", f"{len(broken)} of {len(order)} units failed: {', '.join(broken)}; the others' results are kept in {folder}"
        lost = [failures[unit] for unit in broken if isinstance(failures[unit], LoginLost)]
        if lost:
            report["result"], report["cannot_run"] = "CANNOT RUN", lost[0].cause
        return finish(report, out, args.json, err)
    try:
        merged = merge(caller, review, order, results)
    except Refused as error:
        report["refusals"] += error.causes
        report["detail"] = f"the merge refused the units' results; they are kept in {folder}"
        return finish(report, out, args.json, err)
    report["tables"], report["same_place"] = merged["tables"], merged["same_place"]
    files = {}
    if hasattr(caller, "RENDER"):
        earlier = rendered_earlier(folder)
        try:
            files = hook("RENDER", caller.RENDER, review, merged["tables"], caller=caller)
        except Refused as error:
            report["refusals"] += error.causes
            report["rendered"], report["not_this_merge"] = [], left_over(folder, earlier, [])
            report["result"], report["detail"] = "FAILED", (f"the caller's rendered record was not made; the record in table "
                                                            f"form is written to {os.path.join(folder, RECORD)}")
            write_json(os.path.join(folder, RECORD), report)
            return finish(report, out, args.json, err)
        refused = rendered_problems(caller, folder, files, earlier)
        if refused:
            report["refusals"] += refused
            report["detail"] = f"nothing was written; the units' results are kept in {folder}"
            return finish(report, out, args.json, err)
        report["rendered"], report["not_this_merge"] = list(files), left_over(folder, earlier, files)
    report["result"], report["detail"] = "WRITTEN", os.path.join(folder, RECORD)
    write_json(os.path.join(folder, RECORD), report)
    for name, text in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    return finish(report, out, args.json, err)


def rendered_earlier(folder: str) -> List[str]:
    """The rendered names an earlier merge wrote into the folder, from the record it wrote: those it made and those it
    named as left over from a merge before it; none when the folder holds no record."""
    path = os.path.join(folder, RECORD)
    if not os.path.lexists(path):
        return []
    try:
        record = read_json(path)
    except (OSError, ValueError, RecursionError) as error:
        raise Refused([f"the record {path} cannot be read ({error}); {RESTORE}"])
    names = []
    for key in ("rendered", "not_this_merge"):
        listed = record.get(key, []) if isinstance(record, dict) else None
        if not isinstance(listed, list) or not all(isinstance(name, str) for name in listed):
            raise Refused([f"the record {path} gives {key} as {listed!r:.80}, not a list of file names; {RESTORE}"])
        names += listed
    return list(dict.fromkeys(names))


def name_key(name: str) -> str:
    """A file name as a folder that ignores case and trailing dots and spaces would hold it."""
    return name.rstrip(". ").casefold()


def left_over(folder: str, earlier: Sequence[str], rendered: Sequence[str]) -> List[str]:
    """The files an earlier merge wrote that are still in the folder and that this merge does not render again."""
    again = {name_key(name) for name in rendered}
    return [name for name in earlier if name_key(name) not in again and os.path.lexists(os.path.join(folder, name))]


def rendered_problems(caller, folder: str, files: Dict[str, str], earlier: Sequence[str]) -> List[str]:
    """Why the files a caller's RENDER returned cannot be written: a name with a path in it, a name the driver uses
    itself, two names that differ only in case or in trailing dots and spaces, or one the output folder holds that no earlier merge wrote. Names are
    compared without regard to case or trailing dots and spaces, since a folder on some systems holds one file for names that differ in them."""
    who, found = f"caller {caller.REVIEW_CALLER_NAME}", []
    reserved = {name_key(name) for name in RESERVED_NAMES}
    wrote = {name_key(name) for name in earlier}
    held = {name_key(name) for name in os.listdir(folder)} if os.path.isdir(folder) else set()
    seen: Dict[str, str] = {}
    for name in files:
        key = name_key(name)
        if name in (".", "..") or any(mark in name for mark in ("/", "\\", "\0")):
            found.append(f"the {who}'s RENDER names a file {name!r} with a path in it; name a file in the output folder alone")
        elif key in reserved:
            found.append(f"the {who}'s RENDER names a file {name!r}, which the command uses in the output folder; "
                         f"use a name other than {', '.join(RESERVED_NAMES)}")
        elif key in seen:
            found.append(f"the {who}'s RENDER names {seen[key]!r} and {name!r}, which differ only in case or trailing dots and spaces; name them apart")
        elif (key in held or os.path.lexists(os.path.join(folder, name))) and key not in wrote:
            found.append(f"the {who}'s RENDER names a file {name!r}, which the output folder already holds and no earlier "
                         "merge wrote; name another file, or move that one away")
        seen.setdefault(key, name)
    return found


if __name__ == "__main__":
    sys.exit(main())
