"""Reading the hosted workflows the way the checks over them need to.

Two suites inspect `.github/workflows/`: the sweep's, for what its hosted run
may pull in and when it may start, and the complete verification's, for the
nightly that calls the sweep. They read the same declarations and have to agree
on what a reference to other code is, so the reading lives here once rather
than as two copies that drift apart the next time a workflow gains a new kind
of reference.

A `uses:` line names one of two things. A remote action or workflow,
`owner/repo[/path]@ref`, is fetched from somewhere else on the day the run
starts, so it is held to a full commit digest with the release it was in a
trailing comment. A local one is read from the very commit the run was started
on, so it has no ref to pin and is not a way for unchosen code to come in: the
dedicated self-repository form `$/path`, which the workflow linter asks for,
or the older `./path` it replaces. Anything that is neither is refused rather
than waved through, since a check that skips what it cannot classify passes in
exactly the way a check nobody ran does.
"""

from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
WORKFLOWS = os.path.join(REPO, ".github", "workflows")

#: Read from the same commit as the workflow naming it.
LOCAL = re.compile(r"^[.$]/[\w./-]+$")
#: Fetched from elsewhere, pinned to the full digest a release points at.
REMOTE = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")


def workflows():
    """Each workflow file's name and text, in name order."""
    for name in sorted(os.listdir(WORKFLOWS)):
        if name.endswith((".yml", ".yaml")):
            with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as handle:
                yield name, handle.read()


#: A mapping key and whatever follows it on its line.
_ENTRY = re.compile(r"^([\w-]+):(?:\s+(.*?))?\s*$")
#: The markers that open a block scalar, whose body is text rather than keys.
_BLOCK_SCALAR = ("|", "|-", "|+", ">", ">-", ">+")


def entries(declared: str):
    """Every mapping key in a workflow as (indent, key, value), in file order.

    The indent is the key's own column, a list item's key counting from after
    its dash, so a step's keys share one indent. A block scalar's body -- a
    step's script -- is text, not keys, and is skipped. A line in a form this
    does not read -- a quoted key, a flow mapping -- is refused rather than
    skipped, because a check that steps over what it cannot read passes in the
    way a check nobody ran does.
    """
    scalar = None
    for number, line in enumerate(declared.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if scalar is not None:
            if indent > scalar:
                continue
            scalar = None
        body = line.strip()
        if body.startswith("- "):
            indent += 2
            body = body[2:].strip()
        match = _ENTRY.match(body)
        if not match:
            if line.lstrip().startswith("- ") and not body.startswith(("{", '"', "'")):
                continue  # a plain list item: a value, not a key
            raise ValueError(f"line {number} is in a form this reader does not read: {line!r}")
        key, value = match.group(1), match.group(2) or ""
        if value.startswith("{"):
            raise ValueError(f"line {number} is a flow mapping this reader does not read: {line!r}")
        if value in _BLOCK_SCALAR:
            scalar = indent
        yield indent, key, value


def find(declared: str, *path: str) -> tuple[str, list[tuple[int, str, str]]]:
    """The value and nested entries of the key at a path, e.g. ('jobs', 'gates').

    Raises KeyError when the path is not declared.
    """
    items = list(entries(declared))
    start, end, parent, value = 0, len(items), -1, ""
    for key in path:
        children = [i for i in range(start, end) if items[i][0] > parent]
        depth = min((items[i][0] for i in children), default=None)
        found = next((i for i in children if items[i][0] == depth and items[i][1] == key), None)
        if found is None:
            raise KeyError("/".join(path))
        parent, value = items[found][0], items[found][2]
        start = found + 1
        end = next((j for j in range(start, end) if items[j][0] <= parent), end)
    return value, items[start:end]


def keys(declared: str, *path: str) -> list[str]:
    """The keys directly under a path, in order."""
    _, nested = find(declared, *path)
    depth = min((indent for indent, _, _ in nested), default=None)
    return [key for indent, key, _ in nested if indent == depth]


def uses(declared: str):
    """Every `uses:` value in a workflow, trailing comment included."""
    for _, key, value in entries(declared):
        if key == "uses":
            yield value


def scripts(declared: str):
    """Every step's `run:` script, its lines dedented, as a list of lines."""
    lines = declared.splitlines()
    for position, line in enumerate(lines):
        body = line.strip()
        if body.startswith("- "):
            body = body[2:].strip()
        match = _ENTRY.match(body)
        if not match or match.group(1) != "run" or line.lstrip().startswith("#"):
            continue
        value = match.group(2) or ""
        if value not in _BLOCK_SCALAR:
            yield [value]
            continue
        indent = len(line) - len(line.lstrip(" "))
        script = []
        for following in lines[position + 1:]:
            if following.strip() and len(following) - len(following.lstrip(" ")) <= indent:
                break
            script.append(following)
        depth = min((len(s) - len(s.lstrip(" ")) for s in script if s.strip()), default=0)
        yield [s[depth:] for s in script]


def permissions(declared: str) -> list[tuple[str, str]]:
    """Every grant a workflow makes, at the top or on a job, as (scope, access).

    A grant written on one line -- `write-all`, `read-all`, `{}` -- is returned
    as ('*', that value), so it reads as the broad grant it is rather than as
    nothing.
    """
    items = list(entries(declared))
    grants = []
    for position, (indent, key, value) in enumerate(items):
        if key != "permissions":
            continue
        if value:
            grants.append(("*", value))
            continue
        for nested_indent, scope, access in items[position + 1:]:
            if nested_indent <= indent:
                break
            grants.append((scope, access))
    return grants


# --- Expressions -------------------------------------------------------------
#
# Where a value depends on the run -- a concurrency group, whether a run may be
# cancelled -- reading its text says nothing about what it comes to. These
# evaluate the subset of the code host's expression language the workflows use,
# against a context the check states, so the check is about the value a run
# gets. Anything outside that subset is refused rather than guessed at.

_TOKEN = re.compile(r"\s*(?:('(?:[^']|'')*')|(==|!=|&&|\|\||!|\(|\))|([A-Za-z_][\w.-]*)|(\d+))")


def _tokens(expression: str) -> list[tuple[str, str]]:
    tokens, position = [], 0
    expression = expression.rstrip()
    while position < len(expression):
        match = _TOKEN.match(expression, position)
        if not match or match.end() == position:
            raise ValueError(f"cannot read the expression {expression!r} at {position}")
        string, operator, name, number = match.groups()
        if string is not None:
            tokens.append(("value", string[1:-1].replace("''", "'")))
        elif operator is not None:
            tokens.append(("op", operator))
        elif number is not None:
            tokens.append(("value", number))
        else:
            tokens.append(("name", name))
        position = match.end()
    return tokens


def _truthy(value) -> bool:
    return value not in (False, "", None)


def _text(value) -> str:
    return {True: "true", False: "false"}.get(value, value) if isinstance(value, bool) else str(value)


def evaluate(expression: str, context: dict[str, str]):
    """The value of one expression (the text inside ${{ }}) in a context."""
    tokens = _tokens(expression)
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else (None, None)

    def take():
        nonlocal position
        position += 1
        return tokens[position - 1]

    def primary():
        kind, token = take() if position < len(tokens) else (None, None)
        if kind == "op" and token == "(":
            value = either()
            if take() != ("op", ")"):
                raise ValueError(f"unbalanced parentheses in {expression!r}")
            return value
        if kind == "op" and token == "!":
            return not _truthy(primary())
        if kind == "value":
            return token
        if kind == "name":
            if token in ("true", "false"):
                return token == "true"
            if token not in context:
                raise ValueError(f"{token} is not in the context the check states")
            return context[token]
        raise ValueError(f"cannot read the expression {expression!r}")

    def comparison():
        left = primary()
        while peek() in (("op", "=="), ("op", "!=")):
            _, operator = take()
            right = primary()
            equal = _text(left).lower() == _text(right).lower()
            left = equal if operator == "==" else not equal
        return left

    def both():
        left = comparison()
        while peek() == ("op", "&&"):
            take()
            right = comparison()
            left = right if _truthy(left) else left
        return left

    def either():
        left = both()
        while peek() == ("op", "||"):
            take()
            right = both()
            left = left if _truthy(left) else right
        return left

    value = either()
    if position != len(tokens):
        raise ValueError(f"cannot read the expression {expression!r}")
    return value


def interpolate(value: str, context: dict[str, str]):
    """A workflow value with each ${{ }} replaced by what it comes to.

    A value that is one expression and nothing else keeps that expression's
    own value, so a flag set by an expression comes back as a flag.
    """
    value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    whole = re.fullmatch(r"\$\{\{((?:(?!\}\}).)*)\}\}", value)
    if whole:
        return evaluate(whole.group(1), context)
    return re.sub(r"\$\{\{(.*?)\}\}", lambda m: _text(evaluate(m.group(1), context)), value)


def flag(value: str, context: dict[str, str]) -> bool:
    result = interpolate(value, context)
    if isinstance(result, bool):
        return result
    if result in ("true", "false"):
        return result == "true"
    raise ValueError(f"{value!r} comes to {result!r}, which is not a flag")


def concurrency(declared: str, context: dict[str, str]) -> list[tuple[str, bool]]:
    """Every concurrency group a workflow's run joins, top level or per job, as
    (group, whether a newer run cancels it), evaluated in a context."""
    items = list(entries(declared))
    groups = []
    for position, (indent, key, value) in enumerate(items):
        if key != "concurrency":
            continue
        if value:
            groups.append((_text(interpolate(value, context)), False))
            continue
        nested = {}
        for nested_indent, name, setting in items[position + 1:]:
            if nested_indent <= indent:
                break
            nested[name] = setting
        if "group" not in nested:
            raise ValueError("a concurrency block names no group")
        cancel = nested.get("cancel-in-progress", "false")
        groups.append((_text(interpolate(nested["group"], context)), flag(cancel, context)))
    return groups


def is_local(used: str) -> bool:
    return bool(LOCAL.match(used.split("#", 1)[0].strip()))


def unpinned(used: str) -> str | None:
    """Why a `uses:` value could pull in code nobody chose, or None when it cannot."""
    reference, marker, comment = used.partition("#")
    reference = reference.strip()
    if LOCAL.match(reference):
        return None
    if "@" not in reference:
        return f"'{used}' is neither a path in this repository nor a remote reference with a version"
    if not REMOTE.match(reference):
        return f"'{used}' is pinned to a moving reference rather than a digest"
    if not (marker and comment.strip()):
        return f"'{used}' is a digest with nothing saying which release it is"
    return None


def triggers(declared: str) -> list[str]:
    """The event names in a workflow's top-level `on:` block."""
    lines = declared.splitlines()
    if "on:" not in lines:
        raise ValueError("the workflow declares no top-level 'on:' block")
    events = []
    for line in lines[lines.index("on:") + 1:]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        match = re.match(r"^  ([\w-]+):", line)
        if match:
            events.append(match.group(1))
    return events
