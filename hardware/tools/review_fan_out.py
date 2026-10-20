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
exposes SETUP_PROMPT, unit_prompt(unit), units(review_folder), TOOLS, BOUND,
TABLES, FINDINGS and CHECK. No caller is registered here.

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
import json
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
ACK_INSTRUCTION = ("Open no image and judge nothing. When you have read what is asked, answer with exactly "
                   f"{ACK} and nothing else.")
#: The tools the setup session is granted, and the only tools a reviewer may be granted.
READ_TOOLS = ("Read", "Glob", "Grep")
#: What a caller module must expose.
REQUIRED = ("SETUP_PROMPT", "unit_prompt", "units", "TOOLS", "BOUND", "TABLES", "FINDINGS", "CHECK")
#: Files read as images or other non-text, whether or not they exist yet.
NON_TEXT_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico", ".pdf", ".step",
                     ".stp", ".zip", ".gz", ".bin", ".svgz")
RECORD = "record.json"
UNITS_FOLDER = "units"
SETUPS = "setups.json"
LOCK = ".review-fan-out.lock"
#: How many times a call refused for a rate limit is retried, with the wait doubling each time.
RATE_RETRIES = 5
RATE_PATTERN = re.compile(r"rate.?limit|too many requests|\b429\b|overloaded", re.IGNORECASE)
LOGIN_PATTERN = re.compile(r"not logged in|please run /login|invalid api key|authentication", re.IGNORECASE)
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
    """A unit that could not be judged, with what the reviewer returned."""


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
    missing = [attribute for attribute in REQUIRED if not hasattr(module, attribute)]
    if missing:
        raise Refused([f"the caller module {path} lacks {', '.join(missing)}; add each to the module"])
    problems = []
    if not isinstance(module.TOOLS, (list, tuple)) or not module.TOOLS or any(tool not in READ_TOOLS for tool in module.TOOLS):
        problems.append(f"the caller module {path} grants tools {module.TOOLS!r}; a reviewer is read-only, so grant "
                        f"some of {', '.join(READ_TOOLS)} and no others")
    if not isinstance(module.BOUND, int) or isinstance(module.BOUND, bool) or module.BOUND < 1:
        problems.append(f"the caller module {path} states a BOUND of {module.BOUND!r}; state a whole number of one or more")
    if problems:
        raise Refused(problems)
    return module


def unit_names(caller, review: str) -> List[str]:
    """The review's units in the order the caller lists them, each a name safe to keep a file under."""
    names = list(caller.units(review))
    problems = [f"the unit name {name!r} is not a plain name of letters, digits, dots, dashes and underscores; fix the "
                "caller's units" for name in names if not isinstance(name, str) or not UNIT_NAME.match(name)]
    if len(set(names)) != len(names):
        problems.append("the caller lists a unit name twice; each unit needs a name of its own")
    if not names:
        problems.append(f"the caller finds no unit in the review folder {review}; check the folder is the one the "
                        "review's starter wrote")
    if problems:
        raise Refused(problems)
    return names


# --- The agent command line --------------------------------------------------------------------


class Session:
    """One session's start report, tool uses and result report, as the agent command line printed them."""

    def __init__(self):
        self.start: Dict[str, Any] = {}
        self.tool_uses: List[Tuple[str, Dict[str, Any]]] = []
        self.result: Optional[Dict[str, Any]] = None
        self.exit_code = 0
        self.stderr = ""
        self.wall_s = 0.0

    @property
    def id(self) -> str:
        return str((self.result or {}).get("session_id") or self.start.get("session_id") or "")

    @property
    def text(self) -> str:
        return str((self.result or {}).get("result") or "")

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
        status = subprocess.run([found, "auth", "status"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise board_check.CannotRun(f"the agent command line {program} could not report its login ({error}); check it runs")
    logged_out = status.returncode != 0
    try:
        logged_out = logged_out or json.loads(status.stdout).get("loggedIn") is False
    except (ValueError, AttributeError):
        pass
    if logged_out:
        raise board_check.CannotRun(f"the agent command line {program} is not logged in; log it in, then run again")
    return found


def quiet_arguments() -> List[str]:
    """The flags that start a session with no MCP server and without the instruction sources the command line can exclude."""
    return ["--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
            "--settings", json.dumps({"disableAllHooks": True}), "--exclude-dynamic-system-prompt-sections"]


def parse_stream(text: str) -> Session:
    session = Session()
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            session.start = event
        elif kind == "assistant":
            for item in (event.get("message") or {}).get("content") or []:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    session.tool_uses.append((str(item.get("name")), item.get("input") or {}))
        elif kind == "result":
            session.result = event
    return session


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
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, env={**os.environ, **QUIET_ENVIRONMENT})
    session = parse_stream(done.stdout)
    session.exit_code, session.stderr = done.returncode, done.stderr.strip()
    session.wall_s = time.time() - began
    result = session.result or {}
    said = f"{session.text}\n{session.stderr}"
    if (result.get("is_error") or done.returncode != 0) and LOGIN_PATTERN.search(said):
        raise board_check.CannotRun(f"the agent command line {program} is not logged in; log it in, then run again")
    if (result.get("is_error") or done.returncode != 0) and (result.get("api_error_status") == 429 or RATE_PATTERN.search(said)):
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
    """What the session's start report shows that it should not, each naming the session."""
    start, found = session.start, []
    if not start:
        return [f"{label} printed no start report; check the agent command line prints stream-json events"]
    if sorted(start.get("tools") or []) != sorted(tools):
        found.append(f"{label} started with tools {sorted(start.get('tools') or [])}, not the {sorted(tools)} it was granted")
    if model and start.get("model") != model:
        found.append(f"{label} started with model {start.get('model')}, not {model}")
    if start.get("mcp_servers"):
        found.append(f"{label} started with MCP servers {start.get('mcp_servers')}; none may be loaded")
    if start.get("skills"):
        found.append(f"{label} started with skills {start.get('skills')}, which it was asked to exclude")
    if start.get("slash_commands"):
        found.append(f"{label} started with commands {start.get('slash_commands')}, which it was asked to exclude")
    outside = [str(plugin.get("name") if isinstance(plugin, dict) else plugin) for plugin in start.get("plugins") or []
               if not (isinstance(plugin, dict) and plugin.get("path") == "builtin")]
    if outside:
        found.append(f"{label} started with plugins {outside}, which it was asked to exclude")
    if os.path.realpath(str(start.get("cwd") or "")) != os.path.realpath(review):
        found.append(f"{label} started in {start.get('cwd')}, not the review folder {review}")
    return found


def non_text(path: str, review: str) -> bool:
    """Whether a read of `path` opens a file whose type is not text."""
    full = path if os.path.isabs(path) else os.path.join(review, path)
    if full.lower().endswith(NON_TEXT_SUFFIXES):
        return True
    try:
        with open(full, "rb") as handle:
            head = handle.read(8192)
    except OSError:
        return False
    if b"\0" in head:
        return True
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as error:
        return error.start < len(head) - 4
    return False


def setup_problems(session: Session, review: str) -> List[str]:
    """What the setup session's tool uses and answer show: an image opened, a tool outside its grant, or a judgement."""
    found = []
    for name, given in session.tool_uses:
        if name not in READ_TOOLS:
            found.append(f"the setup session used {name}, a tool it was not granted")
        elif name == "Read":
            path = str(given.get("file_path") or "")
            if non_text(path, review):
                found.append(f"the setup session opened {path}, a file whose type is not text; it may read documents "
                             "and records only, so the forked reviewers stay as blind as fresh ones")
    if session.text.strip() != ACK:
        found.append(f"the setup session answered {board_check.clean(session.text.strip())[:200]!r} and not {ACK}; "
                     "it may judge nothing, or a forked reviewer would inherit the verdict")
    return found


# --- What a session cost -----------------------------------------------------------------------


def figures(session: Session) -> Dict[str, Any]:
    """The cumulative figures a result report gives, and the tokens as the session reports them."""
    result, usage = session.result or {}, (session.result or {}).get("usage") or {}
    return {"cost_usd": float(result.get("total_cost_usd") or 0), "api_ms": int(result.get("duration_api_ms") or 0),
            "turns": int(result.get("num_turns") or 0), "wall_s": round(session.wall_s, 3),
            "tokens": {"cache_read": int(usage.get("cache_read_input_tokens") or 0),
                       "cache_write": int(usage.get("cache_creation_input_tokens") or 0),
                       "fresh": int(usage.get("input_tokens") or 0),
                       "generated": int(usage.get("output_tokens") or 0)}}


def own(cumulative: Dict[str, Any], setup: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """A session's own figures: its cumulative cost, API time and turns less the setup session's it includes."""
    taken = setup or {"cost_usd": 0, "api_ms": 0, "turns": 0}
    return {"cost_usd": round(cumulative["cost_usd"] - taken["cost_usd"], 6),
            "api_ms": cumulative["api_ms"] - taken["api_ms"], "turns": cumulative["turns"] - taken["turns"],
            "wall_s": cumulative["wall_s"], "tokens": dict(cumulative["tokens"])}


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
    except ValueError:
        raise Malformed(["the reviewer's answer is not a JSON object"])
    if not isinstance(found, dict) or not isinstance(found.get("tables"), dict):
        raise Malformed(["the reviewer's answer has no `tables` mapping"])
    return found["tables"]


def table_problems(caller, unit: str, tables: Dict[str, Any]) -> List[str]:
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
            verdict = declared[name].get("verdict_column")
            if verdict and verdict in row and row[verdict] not in declared[name]["verdicts"]:
                found.append(f"unit {unit}'s table {name!r} row {number} has the verdict {row[verdict]!r}, outside "
                             f"{list(declared[name]['verdicts'])}")
    findings = caller.FINDINGS
    if findings and not found:
        found += finding_problems(findings, unit, tables)
    return found


def finding_problems(findings: Dict[str, Any], unit: str, tables: Dict[str, Any]) -> List[str]:
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
    for table, column in findings["citations"]:
        for row in tables.get(table, []):
            for match in findings["citation"].finditer(str(row[column])):
                if int(match.group("number")) not in numbers:
                    found.append(f"unit {unit}'s {table!r} row cites a finding {match.group('number')} the unit did not raise")
    return found


def merge(caller, review: str, order: Sequence[str], results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The units' tables as one record. Units are taken in `order`, never in the order they arrived in.

    It rejects a table, column or verdict the caller does not have, replaces
    every finding number of this round with the one the checklist's order gives
    and rewrites the citations of them in the rows that cite them, leaves any
    citation the caller's pattern does not match as written, and reports findings
    the caller's key puts at one place, keeping each. It reads no model and no
    file outside the unit results and the review folder.
    """
    problems = []
    for unit in order:
        problems += table_problems(caller, unit, results[unit])
    if problems:
        raise Refused(problems)
    rows = {name: [(unit, dict(row)) for unit in order for row in results[unit].get(name, [])] for name in caller.TABLES}
    same_place: List[Dict[str, Any]] = []
    findings = caller.FINDINGS
    if findings:
        renamed, same_place = renumber(findings, review, order, results, rows)
        for table, column in findings["citations"]:
            for unit, row in rows[table]:
                row[column] = findings["citation"].sub(lambda match, unit=unit: replace_number(match, renamed, unit),
                                                       str(row[column]))
    tables = {name: {"columns": list(spec["columns"]), "rows": [row for _, row in rows[name]]}
              for name, spec in caller.TABLES.items()}
    refused = list(caller.CHECK(review, list(order), tables))
    if refused:
        raise Refused(refused)
    return {"tables": tables, "same_place": same_place}


def renumber(findings: Dict[str, Any], review: str, order: Sequence[str], results: Dict[str, Dict[str, Any]],
             rows: Dict[str, List[Tuple[str, Dict[str, Any]]]]) -> Tuple[Dict[Tuple[str, int], int], List[Dict[str, Any]]]:
    """This round's findings numbered in the checklist's order; each unit's old number against its new, and the findings at one place."""
    first = findings["first"](review) if callable(findings.get("first")) else 1
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
        key = findings["key"](row)
        if key is not None:
            groups.setdefault(str(key), []).append((row[findings["number"]], unit))
    same = [{"key": key, "findings": sorted(number for number, _ in members),
             "units": sorted({unit for _, unit in members})}
            for key, members in groups.items() if len(members) > 1]
    return renamed, sorted(same, key=lambda place: place["findings"][0])


def replace_number(match: "re.Match", renamed: Dict[Tuple[str, int], int], unit: str) -> str:
    """The matched citation with the digits of the finding it names swapped for the number the merge gave it."""
    whole, (start, end) = match.group(0), match.span("number")
    new = renamed[(unit, int(match.group("number")))]
    return whole[:start - match.start()] + str(new) + whole[end - match.start():]


# --- The run -----------------------------------------------------------------------------------


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


class Run:
    """One run of the command: a caller's review, judged unit by unit, into an output folder."""

    def __init__(self, caller, review: str, out: str, program: str, bound: int, model: Optional[str], wait: float,
                 sleep: Callable[[float], None] = time.sleep):
        self.caller, self.review, self.out, self.program = caller, review, out, program
        self.bound, self.model, self.wait, self.sleep = bound, model, wait, sleep

    def unit_path(self, unit: str) -> str:
        return os.path.join(self.out, UNITS_FOLDER, f"{unit}.json")

    def attempt(self, prompt: str, tools: Sequence[str], label: str, resume: str, fork: bool,
                model: str) -> Tuple[Session, Dict[str, Any]]:
        """One session of a unit, its start report checked; returns the session and the figures it reports."""
        session = with_rate_retry(lambda: call_agent(self.program, prompt, tools, self.review, resume, fork, model),
                                  self.wait, self.sleep)
        problems = start_problems(session, label, tools, model, self.review)
        if problems:
            raise UnitFailed("; ".join(problems))
        return session, figures(session)

    def judge(self, unit: str, resume: str, fork: bool, setup: Dict[str, Any], model: str, setup_index: int) -> Dict[str, Any]:
        """One unit, run once more when its reviewer errors, returns nothing or returns tables the caller does not allow."""
        label, sessions, last = f"the reviewer of unit {unit}", [], "nothing"
        # A fork reports the setup session's figures with its own, and so does a turn resumed without a fork, which
        # also reports the turns before it.
        base = setup["cumulative"]
        for number in (1, 2):
            try:
                session, cumulative = self.attempt(self.caller.unit_prompt(unit), self.caller.TOOLS, label, resume, fork, model)
            except UnitFailed as error:
                raise UnitFailed(f"unit {unit} failed: {error}")
            figure = own(cumulative, base)
            if not fork:
                base = cumulative
            flags = ["no cache read"] if fork and figure["tokens"]["cache_read"] == 0 else []
            sessions.append({"attempt": number, "session": session.id, "mode": "fork" if fork else "setup session",
                             "flags": flags, **figure})
            result = session.result or {}
            if session.exit_code != 0 or result.get("is_error") or not session.text.strip():
                last = session.said()
                continue
            try:
                tables = parse_result(session.text)
                problems = table_problems(self.caller, unit, tables)
                if problems:
                    raise Malformed(problems)
            except Malformed as error:
                last = f"{error}: {board_check.clean(session.text)[:300]}"
                continue
            kept = {"unit": unit, "tables": tables, "raw": session.text, "sessions": sessions, "ran_at": stamp(),
                    "setup": setup_index, "attempts": number}
            write_json(self.unit_path(unit), kept)
            return kept
        raise UnitFailed(f"unit {unit} failed after {len(sessions)} attempts; the reviewer returned: {last}")

    def setup_session(self, model: Optional[str]) -> Tuple[Session, Dict[str, Any]]:
        prompt = f"{self.caller.SETUP_PROMPT.rstrip()}\n\n{ACK_INSTRUCTION}"
        session = with_rate_retry(lambda: call_agent(self.program, prompt, READ_TOOLS, self.review, model=model),
                                  self.wait, self.sleep)
        result = session.result or {}
        if session.exit_code != 0 or result.get("is_error") or not session.id:
            raise Refused([f"the setup session failed and returned: {session.said()}; check the agent command line runs "
                           "from the review folder, then run again"])
        problems = start_problems(session, "the setup session", READ_TOOLS, model, self.review) + setup_problems(session, self.review)
        if problems:
            raise Refused(problems)
        return session, figures(session)

    def run(self, order: Sequence[str], named: Sequence[str]) -> Tuple[Dict[str, Any], Dict[str, Optional[str]]]:
        """Judge `named` units (all of `order` when none), returning the setup entry and each unit's failure, if any."""
        session, cumulative = self.setup_session(self.model)
        model = str(session.start.get("model"))
        setup = {"id": session.id, "at": stamp(), "kind": "rerun" if named else "initial",
                 "units": list(named or order), "model": model, "cumulative": cumulative, **own(cumulative, None)}
        known = read_json(os.path.join(self.out, SETUPS)) if os.path.isfile(os.path.join(self.out, SETUPS)) else []
        setup_index = len(known)
        write_json(os.path.join(self.out, SETUPS), known + [{key: value for key, value in setup.items() if key != "cumulative"}])
        failures: Dict[str, Optional[str]] = {}
        todo = list(named or order)
        fork = len(order) > 1

        def one(unit: str) -> None:
            try:
                self.judge(unit, session.id, fork, setup, model, setup_index)
                failures[unit] = None
            except UnitFailed as error:
                failures[unit] = str(error)

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
    lines = [f"REFUSED | {clean(why)}" for why in report["refusals"]]
    if report["cannot_run"]:
        lines.append(f"CANNOT RUN | {clean(report['cannot_run'])}")
    for setup in report["setup_sessions"]:
        lines.append(f"SETUP | {setup['id']} | {setup['kind']} | {setup['model']} | {figure_line(setup)}")
    for unit in report["units"]:
        flags = "; ".join(unit["flags"]) or "no flag"
        lines.append(f"UNIT | {unit['unit']} | {unit['status']} | {unit['mode']} | {unit['session']} | "
                     f"{unit['attempts']} attempts | {figure_line(unit['own'])} | {clean(flags)}"
                     + (" | run again" if unit["run_again"] else ""))
        if unit["status"] == "failed":
            lines.append(f"FAILED | {clean(unit['detail'])}")
    for rerun in report["reruns"]:
        lines.append(f"RERUN | {', '.join(rerun['units'])} | {rerun['at']} | new setup session {rerun['setup_session']}")
    for place in report["same_place"]:
        lines.append(f"SAME PLACE | {clean(place['key'])} | findings {', '.join(str(n) for n in place['findings'])} | "
                     f"units {', '.join(place['units'])}")
    if report["setup_sessions"] or report["units"]:
        lines.append(f"TOTAL | {figure_line(report['totals'])}")
    lines.append(f"RESULT | {report['result']} | {clean(report['detail'])}")
    return lines


def new_report(caller_name: str, review: str, out: str) -> Dict[str, Any]:
    return {"result": "REFUSED", "detail": "nothing was run", "caller": caller_name, "review": review, "out": out,
            "refusals": [], "cannot_run": None, "units": [], "setup_sessions": [], "reruns": [], "same_place": [],
            "totals": empty_figures(), "tables": {}}


def unit_entry(kept: Dict[str, Any], rerun: bool, setups: List[Dict[str, Any]]) -> Dict[str, Any]:
    final = kept["sessions"][-1]
    flags = sorted({flag for session in kept["sessions"] for flag in session["flags"]})
    return {"unit": kept["unit"], "status": "judged", "mode": final["mode"], "session": final["session"],
            "attempts": kept["attempts"], "own": total(kept["sessions"]), "flags": flags, "run_again": rerun,
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
    parser.add_argument("--rate-limit-wait", type=float, default=5.0, help="seconds before the first retry of a call refused for a rate limit; it doubles each time")
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
    named = list(dict.fromkeys(args.rerun))
    unknown = [name for name in named if name not in order]
    if unknown:
        return refuse([f"{', '.join(unknown)} is not a unit of the review; the units are {', '.join(order)}"])
    held = os.path.isfile(os.path.join(folder, RECORD)) or (
        os.path.isdir(os.path.join(folder, UNITS_FOLDER)) and bool(os.listdir(os.path.join(folder, UNITS_FOLDER))))
    if held and not named:
        return refuse([f"the output folder {folder} already holds a record; give a new or empty folder, or name the "
                       "units to run again with --rerun"])
    if named and not held:
        return refuse([f"the output folder {folder} holds no earlier result to run {', '.join(named)} again against; "
                       "run without --rerun into a new folder first"])
    if named:
        lacking = [name for name in order if name not in named and not os.path.isfile(os.path.join(folder, UNITS_FOLDER, f"{name}.json"))]
        if lacking:
            return refuse([f"the output folder holds no result for {', '.join(lacking)}; name each of them with --rerun too"])
    try:
        program = require_agent()
    except board_check.CannotRun as error:
        report["result"], report["cannot_run"], report["detail"] = "CANNOT RUN", str(error), "nothing was run"
        return finish(report, out, args.json, err)
    os.makedirs(folder, exist_ok=True)
    lock = os.path.join(folder, LOCK)
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return refuse([f"the output folder {folder} is in use by another run (it holds {LOCK}); wait for that run, or "
                       "delete the file if no run is in the folder"])
    os.close(handle)
    try:
        return execute(report, caller, review, folder, order, named, program, bound or caller.BOUND, args, out, err)
    finally:
        os.remove(lock)


def execute(report, caller, review, folder, order, named, program, bound, args, out, err) -> int:
    run = Run(caller, review, folder, program, bound, args.model, args.rate_limit_wait)
    try:
        setup, failures = run.run(order, named)
    except board_check.CannotRun as error:
        report["result"], report["cannot_run"], report["detail"] = "CANNOT RUN", str(error), "nothing was kept"
        return finish(report, out, args.json, err)
    except Refused as error:
        report["refusals"] += error.causes
        report["detail"] = "no unit was started"
        return finish(report, out, args.json, err)
    setups = read_json(os.path.join(folder, SETUPS))
    report["setup_sessions"] = [{key: value for key, value in entry.items() if key != "cumulative"} for entry in setups]
    results, parts = {}, []
    for unit in order:
        path = run.unit_path(unit)
        failed = failures.get(unit)
        if failed:
            report["units"].append({"unit": unit, "status": "failed", "mode": "fork" if len(order) > 1 else "setup session",
                                    "session": "", "attempts": 0, "own": empty_figures(), "flags": [],
                                    "run_again": unit in named, "detail": failed, "ran_at": "", "setup_session": setup["id"]})
            continue
        kept = read_json(path)
        results[unit] = kept["tables"]
        report["units"].append(unit_entry(kept, unit in named, setups))
    for entry in report["units"]:
        parts.append(entry["own"])
    report["totals"] = total([{key: entry[key] for key in empty_figures()} for entry in setups] + parts)
    again = read_json(os.path.join(folder, "reruns.json")) if os.path.isfile(os.path.join(folder, "reruns.json")) else []
    if named:
        again.append({"at": setup["at"], "units": list(named), "new_setup_session": True, "setup_session": setup["id"]})
        write_json(os.path.join(folder, "reruns.json"), again)
    report["reruns"] = again
    broken = [unit for unit, why in failures.items() if why]
    if broken:
        report["result"], report["detail"] = "FAILED", f"{len(broken)} of {len(order)} units failed: {', '.join(broken)}; the others' results are kept in {folder}"
        return finish(report, out, args.json, err)
    try:
        merged = merge(caller, review, order, results)
    except Refused as error:
        report["refusals"] += error.causes
        report["detail"] = f"the merge refused the units' results; they are kept in {folder}"
        return finish(report, out, args.json, err)
    report["tables"], report["same_place"] = merged["tables"], merged["same_place"]
    report["result"], report["detail"] = "WRITTEN", os.path.join(folder, RECORD)
    write_json(os.path.join(folder, RECORD), report)
    return finish(report, out, args.json, err)


if __name__ == "__main__":
    sys.exit(main())
