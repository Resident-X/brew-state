"""The caller contract: what a review's caller module supplies, how the kit loads and checks it, and the files it renders.

A caller is a module named `review_caller_<name>` in a folder the command takes. It
supplies, as module attributes:

- `declaration` (required): the declaration of the review as a path (relative to the module's folder), as the mapping the
  declaration file holds, as a `Declaration`, or as a function of the review folder returning the mapping or a
  `Declaration`, for a review whose units come from the folder.
- `checks(tables)` (required): the problems in the merged tables, as a list of text; none when they hold.
- `render(review_folder, tables)` (required): the files of the rendered record, as a mapping of file name to text.
- `retrieval` (optional): the tools a session is granted, the read tools `Read`, `Glob` and `Grep` and the one retrieval
  tool `WebFetch` and no other, as a list of names, or True for all four; the read tools alone when it is absent.
- `checklist` (optional): the items in the order findings are numbered by, as a list or a function of the review folder;
  the declared units' items in declaration order when it is absent. A function is called once, before any session starts.
- `prompt(unit, review_folder)` or `prompt(unit)` (optional): a unit's prompt as text; the declared template's when absent.
- `place(row)`, `round_label(review_folder)`, `earlier_findings(review_folder)` and `first_finding(review_folder)`
  (optional): the place of a finding row, this round's label, the (round, number) pairs of findings the review folder's
  earlier rounds hold, and the number this round's first finding takes. A citation pattern with a round group needs
  `round_label` and `earlier_findings`.

A caller that defines none of the optional attributes behaves as one that defines each with the default above. A module
that lacks a required attribute, or an attribute that cannot be used, is refused naming the caller and the attribute.
"""

from __future__ import annotations

import inspect
import os
import re
import stat
import tempfile
import types
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import decl, merge, messages
from .merge import Refused

READ_TOOLS = ("Read", "Glob", "Grep")
RETRIEVAL_TOOL = "WebFetch"
REQUIRED = ("declaration", "checks", "render")
OPTIONAL = ("retrieval", "checklist", "prompt", "place", "round_label", "earlier_findings", "first_finding")
CALLER_NAME = re.compile(r"[a-z][a-z0-9_]*")
#: The names the kit uses in an output folder, which a rendered file may not take.
KIT_NAMES = ("plan.json", "record.json", "run.lock", "streams")
RENDERED_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
RENDERED_NAME_LONGEST = 64
DEVICE_NAMES = frozenset(["con", "prn", "aux", "nul"] + [f"{kind}{n}" for kind in ("com", "lpt") for n in range(1, 10)])


def accepts(call: Callable[..., Any], count: int) -> bool:
    """Whether `call` can be called with `count` positional arguments; a callable whose signature cannot be read is taken to."""
    try:
        inspect.signature(call).bind(*([None] * count))
    except TypeError:
        return False
    except ValueError:
        return True
    return True


def texts(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and all(isinstance(item, str) and item.strip() for item in value)


@dataclass
class Caller:
    """A loaded caller module and the name and path it was loaded under."""

    name: str
    path: str
    module: Any

    def defined(self, attribute: str) -> bool:
        return hasattr(self.module, attribute)

    def refuse(self, attribute: str, what: str) -> Refused:
        return Refused([f"the caller {self.name} ({self.path}): {attribute} {what}"])

    def prepare(self, review: str) -> "Prepared":
        """Everything about the caller that is settled before a session starts: the declaration, the checklist, the tools
        and the rules of the merge. The checklist function is called here, once; a failure is a refusal naming the caller."""
        return Prepared.resolve(self, review)


def load(name: str, folder: str) -> Caller:
    """The caller module review_caller_<name> in `folder`, or the cause it cannot be used."""
    if not isinstance(name, str) or not CALLER_NAME.fullmatch(name):
        raise Refused([f"the caller name {name!r} is not a lower-case name; give the <name> of a review_caller_<name> module"])
    path = os.path.join(folder, f"review_caller_{name}.py")
    if not os.path.isfile(path):
        raise Refused([f"there is no caller module {path}; give the name of a review_caller_<name> module in the folder "
                       f"{folder}, or the folder holding it"])
    module = types.ModuleType(f"review_caller_{name}_loaded")
    module.__file__ = path
    try:
        with open(path, encoding="utf-8") as handle:
            code = compile(handle.read(), path, "exec")
        exec(code, module.__dict__)
    except Exception as error:  # a caller that does not import is refused with the reason
        raise Refused([f"the caller module {path} cannot be loaded ({type(error).__name__}: {error}); fix the module"])
    caller = Caller(name, path, module)
    missing = [attribute for attribute in REQUIRED if not hasattr(module, attribute)]
    if missing:
        raise Refused([f"the caller {name} ({path}) lacks the attribute {attribute}; add it to the module" for attribute in missing])
    problems = attribute_problems(caller)
    if problems:
        raise Refused(problems)
    return caller


def attribute_problems(caller: Caller) -> List[str]:
    """Why the module's attributes cannot be relied on, each naming the caller and the attribute."""
    module, found = caller.module, []

    def bad(attribute: str, what: str) -> None:
        found.append(f"the caller {caller.name} ({caller.path}) gives {attribute} that {what}")
    if not (isinstance(module.declaration, (str, dict, decl.Declaration)) or callable(module.declaration)):
        bad("declaration", "is not a path, a mapping, a Declaration or a function of the review folder")
    elif callable(module.declaration) and not accepts(module.declaration, 1):
        bad("declaration", "is a function that does not accept the review folder; make it declaration(review_folder)")
    if not callable(module.checks) or not accepts(module.checks, 1):
        bad("checks", "is not a function of the merged tables; make it checks(tables)")
    if not callable(module.render) or not accepts(module.render, 2):
        bad("render", "is not a function of the review folder and the merged tables; make it render(review_folder, tables)")
    if caller.defined("retrieval"):
        grant = module.retrieval
        allowed = READ_TOOLS + (RETRIEVAL_TOOL,)
        if grant is None or isinstance(grant, bool):
            pass
        elif not texts(grant) or not grant or len(set(grant)) != len(grant) or any(tool not in allowed for tool in grant):
            bad("retrieval", f"is {grant!r:.100}; grant some of {', '.join(READ_TOOLS)} and, to fetch a published document, "
                             f"{RETRIEVAL_TOOL}, and no other tool, or True for all four")
    if caller.defined("checklist") and not callable(module.checklist) and module.checklist is not None:
        if not texts(module.checklist) or not module.checklist or len(set(module.checklist)) != len(module.checklist):
            bad("checklist", "is not a list of distinct item names or a function of the review folder returning one")
    elif caller.defined("checklist") and callable(module.checklist) and not accepts(module.checklist, 1):
        bad("checklist", "is a function that does not accept the review folder; make it checklist(review_folder)")
    if caller.defined("prompt") and module.prompt is not None:
        if not callable(module.prompt) or not (accepts(module.prompt, 1) or accepts(module.prompt, 2)):
            bad("prompt", "is not a function of the unit and, optionally, the review folder; make it prompt(unit, review_folder)")
    for attribute, count in (("place", 1), ("round_label", 1), ("earlier_findings", 1), ("first_finding", 1)):
        if caller.defined(attribute) and getattr(module, attribute) is not None:
            if not callable(getattr(module, attribute)) or not accepts(getattr(module, attribute), count):
                bad(attribute, f"is not a function of {'a finding row' if attribute == 'place' else 'the review folder'}")
    return found


def granted_tools(caller: Caller) -> Tuple[str, ...]:
    grant = getattr(caller.module, "retrieval", None)
    if grant is True:
        return READ_TOOLS + (RETRIEVAL_TOOL,)
    if not grant:
        return READ_TOOLS
    order = READ_TOOLS + (RETRIEVAL_TOOL,)
    return tuple(sorted(grant, key=order.index))


def call_hook(caller: Caller, what: str, call: Callable[..., Any], *args: Any) -> Any:
    """What a caller's function returns; an exception from it is a refusal naming the caller and the function."""
    try:
        return call(*args)
    except Refused:
        raise
    except Exception as error:  # the caller's code is not the kit's; its defect is reported, not raised
        raise Refused([f"the caller {caller.name}'s {what} raised {type(error).__name__}: {error}; fix the caller"])


def resolved_declaration(caller: Caller, review: str) -> decl.Declaration:
    given = caller.module.declaration
    file = caller.path
    if callable(given):
        given = call_hook(caller, "declaration function", given, review)
    if isinstance(given, decl.Declaration):
        return given
    try:
        if isinstance(given, str):
            return decl.load(os.path.join(os.path.dirname(caller.path), given))
        if isinstance(given, dict):
            return decl.build(given, file)
    except decl.DeclarationError as error:
        raise Refused([f"the caller {caller.name}'s declaration is refused: {line}" for line in error.lines])
    raise Refused([f"the caller {caller.name}'s declaration is {given!r:.100}, not a path, a mapping or a Declaration; fix the caller"])


def default_checklist(declaration: decl.Declaration) -> List[str]:
    return list(dict.fromkeys(item for unit in declaration.units.values() for item in unit.items))


def resolved_checklist(caller: Caller, review: str, declaration: decl.Declaration) -> List[str]:
    given = getattr(caller.module, "checklist", None)
    if given is None:
        return default_checklist(declaration)
    if callable(given):
        given = call_hook(caller, "checklist function", given, review)
    if not texts(given) or not given:
        raise Refused([f"the caller {caller.name}'s checklist function returned {given!r:.200}, which is not a list of item names; "
                       "fix the caller"])
    repeated = [name for name in dict.fromkeys(given) if list(given).count(name) > 1]
    if repeated:
        raise Refused([f"the caller {caller.name}'s checklist repeats the name {repeated[0]!r}; each item needs a name of its own, "
                       "so fix the caller"])
    return list(given)


@dataclass
class Prepared:
    """A caller settled for one review folder: its declaration, checklist, tools and merge rules, and the functions that
    run its prompt, checks and rendering with every failure named for the caller."""

    caller: Caller
    review: str
    declaration: decl.Declaration
    checklist: Tuple[str, ...]
    tools: Tuple[str, ...]
    rules: merge.Rules

    @classmethod
    def resolve(cls, caller: Caller, review: str) -> "Prepared":
        declaration = resolved_declaration(caller, review)
        checklist = resolved_checklist(caller, review, declaration)
        module, who = caller.module, f"the caller {caller.name}"
        shape = declaration.shape
        label, earlier, first = None, frozenset(), 1
        if shape.findings is not None and "round" in shape.findings.citation.groupindex:
            for attribute in ("round_label", "earlier_findings"):
                if getattr(module, attribute, None) is None:
                    raise caller.refuse(attribute, "is needed because the declaration's citation pattern has a round group; "
                                                   f"add {attribute}(review_folder) to the module")
            label = call_hook(caller, "round_label function", module.round_label, review)
            if not isinstance(label, str) or not label.strip():
                raise Refused([f"{who}'s round_label function returned {label!r:.100}, not this round's label as text; fix the caller"])
            pairs = call_hook(caller, "earlier_findings function", module.earlier_findings, review)
            if not isinstance(pairs, (list, tuple, set, frozenset)) or not all(
                    isinstance(pair, (list, tuple)) and len(pair) == 2 and isinstance(pair[0], str)
                    and isinstance(pair[1], int) and not isinstance(pair[1], bool) and pair[1] >= 1 for pair in pairs):
                raise Refused([f"{who}'s earlier_findings function returned {pairs!r:.200}, not a collection of (round label, "
                               "finding number) pairs; fix the caller"])
            earlier = frozenset((pair[0], pair[1]) for pair in pairs)
        if getattr(module, "first_finding", None) is not None:
            first = call_hook(caller, "first_finding function", module.first_finding, review)
            if isinstance(first, bool) or not isinstance(first, int) or first < 1:
                raise Refused([f"{who}'s first_finding function returned {first!r:.100}, not a whole number of one or more; "
                               "fix the caller"])
        rules = merge.Rules(tuple(checklist), getattr(module, "place", None), label, earlier, first, caller=who)
        return cls(caller, review, declaration, tuple(checklist), granted_tools(caller), rules)

    def unit_text(self, unit: str, items: Optional[Sequence[str]] = None) -> str:
        """A unit's prompt: the caller's, given the review folder when it takes it, else the declared template's. Items in
        another order than the unit's own are added after a caller's prompt as the order to take them in."""
        prompt = getattr(self.caller.module, "prompt", None)
        if prompt is None:
            return messages.unit_prompt(self.declaration, unit, items)
        text = call_hook(self.caller, f"prompt function for unit {unit}", prompt,
                         *((unit, self.review) if accepts(prompt, 2) else (unit,)))
        if not isinstance(text, str) or not text.strip():
            raise Refused([f"the caller {self.caller.name}'s prompt function returned {text!r:.100} for unit {unit}, not the "
                           "unit's prompt as text; fix the caller"])
        if items is not None and list(items) != list(self.declaration.units[unit].items):
            text += "\n\nTake the items in this order:\n" + "\n".join(f"- {item}" for item in items)
        return text

    def merge(self, order: Sequence[str], units: Mapping[str, Mapping[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """The merge of the units' replicas under the declared tables, with the caller's checks of the merged tables."""
        return merge.merge(self.declaration.shape, self.rules, order, units, self.check)

    def check(self, tables: Mapping[str, Any]) -> List[str]:
        found = call_hook(self.caller, "checks function", self.caller.module.checks, tables)
        if not texts(found):
            raise Refused([f"the caller {self.caller.name}'s checks function returned {found!r:.200}, not a list of problems as "
                           "text; fix the caller"])
        return list(found)

    def render(self, tables: Mapping[str, Any]) -> Dict[str, str]:
        """The files the caller renders from the merged tables."""
        found = call_hook(self.caller, "render function", self.caller.module.render, self.review, tables)
        if not isinstance(found, dict) or not all(isinstance(name, str) and isinstance(text, str) for name, text in found.items()):
            raise Refused([f"the caller {self.caller.name}'s render function returned {found!r:.200}, not a mapping of file name to "
                           "text; fix the caller"])
        return dict(found)


# --- The rendered record -----------------------------------------------------------------------


def name_key(name: str) -> str:
    """A file name as a folder that ignores case would hold it."""
    return name.casefold()


def rendered_name_ok(name: str) -> bool:
    """Whether a name is one plain component of ASCII letters, digits, full stops, underscores and hyphens that begins with a
    letter or digit, does not end in a full stop, is at most RENDERED_NAME_LONGEST characters and is not a device name."""
    return (bool(RENDERED_NAME.fullmatch(name)) and not name.endswith(".") and len(name) <= RENDERED_NAME_LONGEST
            and name.split(".")[0].casefold() not in DEVICE_NAMES)


def is_regular_file(path: str) -> bool:
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False


def earlier_names(record: Optional[Mapping[str, Any]]) -> List[str]:
    """The rendered names an earlier merge wrote, from the run record: those it rendered and those it named as left over
    from a merge before it; none when there is no record. A record that gives them in another form is refused."""
    if record is None:
        return []
    names: List[str] = []
    for key in ("rendered", "not_this_merge"):
        listed = record.get(key, [])
        if not isinstance(listed, list) or not all(isinstance(name, str) for name in listed):
            raise Refused([f"the record gives {key} as {listed!r:.80}, not a list of file names; restore it, or run into a new "
                           "output folder"])
        names += listed
    reserved = {name_key(own) for own in KIT_NAMES}
    return list(dict.fromkeys(name for name in names if rendered_name_ok(name) and name_key(name) not in reserved))


def rendered_problems(caller_name: str, folder: str, files: Mapping[str, str], earlier: Sequence[str],
                      reserved: Sequence[str] = KIT_NAMES) -> List[str]:
    """Why the files a caller renders cannot be written. Names are compared without regard to case, since a folder on some
    systems holds one file for names that differ in it; the names an earlier merge wrote are compared exactly, as the record
    holds them exactly, so a held name that is not one of them is foreign."""
    who, found = f"the caller {caller_name}'s render function", []
    kit = {name_key(name) for name in reserved}
    wrote = set(earlier)
    held: Dict[str, List[str]] = {}
    for entry in os.listdir(folder) if os.path.isdir(folder) else []:
        held.setdefault(name_key(entry), []).append(entry)
    seen: Dict[str, str] = {}
    for name in files:
        key = name_key(name)
        if name in (".", "..") or any(mark in name for mark in ("/", "\\", "\0")):
            found.append(f"{who} names a file {name!r} with a path in it; name a file in the output folder alone")
        elif key in kit:
            found.append(f"{who} names a file {name!r}, which the kit uses in the output folder; use a name other than "
                         f"{', '.join(reserved)}")
        elif not rendered_name_ok(name):
            found.append(f"{who} names a file {name!r}, which is not one plain component of ASCII letters, digits, full stops, "
                         f"underscores and hyphens that begins with a letter or digit, does not end in a full stop, is at most "
                         f"{RENDERED_NAME_LONGEST} characters long and is not a name Windows reserves for a device (CON, PRN, AUX, "
                         "NUL, COM1 to COM9, LPT1 to LPT9, with or without an extension); rename it")
        elif key in seen:
            found.append(f"{who} names {seen[key]!r} and {name!r}, which differ only in case; name them apart")
        else:
            present = held.get(key, [])
            if not present and os.path.lexists(os.path.join(folder, name)):
                present = [name]
            foreign = [entry for entry in present if entry not in wrote]
            if foreign:
                found.append(f"{who} names a file {name!r}, which the output folder already holds as {foreign[0]!r} and no earlier "
                             "merge wrote under that name; name another file, or move that one away")
            else:
                for entry in present:
                    if not is_regular_file(os.path.join(folder, entry)):
                        found.append(f"{who} names a file {name!r}, which an earlier merge wrote but the output folder now holds "
                                     f"{entry!r} as a link or a folder, not a file; move it away")
        seen.setdefault(key, name)
    return found


def same_file(first: str, second: str) -> bool:
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def left_over(folder: str, earlier: Sequence[str], rendered: Sequence[str]) -> List[str]:
    """The files an earlier merge wrote that are still in the folder and that this merge does not render again."""
    again = set(rendered)
    return [name for name in earlier if name not in again and is_regular_file(os.path.join(folder, name))
            and not any(same_file(os.path.join(folder, name), os.path.join(folder, new)) for new in rendered)]


def write_rendered(caller_name: str, folder: str, files: Mapping[str, str], earlier: Sequence[str],
                   reserved: Sequence[str] = KIT_NAMES) -> Dict[str, List[str]]:
    """Write the rendered files into the output folder, after the merge, and say what was written. Nothing is written when
    any name is refused. A file an earlier merge wrote is replaced, one it wrote that is not rendered again is named as not
    of this merge and left, and no other file is touched."""
    problems = rendered_problems(caller_name, folder, files, earlier, reserved)
    if problems:
        raise Refused(problems)
    os.makedirs(folder, exist_ok=True)
    for name, text in files.items():
        handle, temporary = tempfile.mkstemp(prefix=".part-", suffix=".txt", dir=folder)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="") as out:
                out.write(text)
            os.replace(temporary, os.path.join(folder, name))
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise
    return {"rendered": list(files), "not_this_merge": left_over(folder, earlier, list(files))}


def summary_lines(summary: Mapping[str, Sequence[str]]) -> List[str]:
    """The same content as the summary's JSON, as the lines a text report gives."""
    lines = [f"rendered: {name}" for name in summary["rendered"]]
    return lines + [f"left from an earlier merge, not of this one: {name}" for name in summary["not_this_merge"]]
