#!/usr/bin/env python3
"""The pre-order check: every board design in the repository, through KiCad's own rule checks.

A board design is a KiCad project file together with the schematic and layout
beside it, and the check finds every one git tracks, wherever it sits, so a
design is checked because it exists rather than because a list names it. Each
is put through KiCad's own command-line electrical rule check and layout rule
check, the layout check with schematic parity and freshly filled zones, and is
held to the signed separation basis in the nearest separation-basis.yaml at or
above it rather than to whatever figure the design itself declares.

Nothing is judged here that KiCad can judge. What this adds is the part KiCad
leaves open: that a check set to ignore, a violation marked as excluded, or a
rules file KiCad silently declines to load would otherwise read as a pass, and
that a design's own rules and overrides could otherwise undercut the signed
separation figure. A design is read only as git holds it -- only tracked files
are copied for KiCad, and the separation basis record must be committed exactly
as it stands -- and nothing a design writes can pass for the check's own rules.

Wherever KiCad can answer a question -- which nets are in a class, which rule
file it loaded, what a zone fills to, which library a symbol comes from -- the
check asks KiCad, run with a configuration of its own so nothing set up on one
machine reaches the answer. Wherever the check has to read a file itself, it
accepts the one form it reads exactly as KiCad does and fails any other form by
name, rather than guessing what KiCad will make of it.

Every finding is printed on one line of a fixed shape,

    VIOLATION | <design> | <rule> | <location> | <message>

after a verdict line for its design, and the exit status is the verdict: 0 when
every design passes, 1 when any fails, 2 when the check cannot run at all.

With --list-reads it runs no check and needs no KiCad and no PyYAML: it lists,
one per line, every file the designs git tracks read, so a build round can tell
whether a changed path reaches a board design.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_geometry  # noqa: E402
import sexpr  # noqa: E402

MIN_PYTHON = (3, 9)
MIN_KICAD = (10, 0)
MIN_PYYAML = (5, 1)
#: The first git whose status takes --porcelain=v1, which is how a committed
#: record is told from one changed since.
MIN_GIT = (2, 11)

#: The one condition a design's Mains separation rule may carry, and the one the
#: signed rule is appended with: a Mains-class item against any item outside it.
MAINS_CONDITION = "A.hasNetclass('Mains') && !B.hasNetclass('Mains')"

RECORD_NAME = "separation-basis.yaml"

#: The record a design's connectivity is held to, found the way RECORD_NAME is.
PIN_RECORD_NAME = "pin-allocation.yaml"

#: Every rule the check adds to the temporary copy's rules file is named with
#: this, and a design rule whose name contains it fails, so a line of KiCad's
#: report naming it can only come from the check.
RESERVED = "pre-order check"

#: The signed rule, which the report shows wherever it finds low-voltage copper
#: too close; its name stays the same from run to run so the report reads alike.
SIGNED_RULE = f"{RESERVED}: signed separation basis"


def marker_rule(nonce: str) -> str:
    """The rule whose firing shows KiCad loaded the rules file at all."""
    return f"{RESERVED} {nonce}: rules loaded"


def probe_rule(nonce: str, netclass: str = "Mains") -> str:
    """The rule reporting every item KiCad places in `netclass`."""
    return f"{RESERVED} {nonce}: {netclass} item"

#: A value standing in for a signature rather than being one.
PLACEHOLDERS = {"unsigned", "tbd", "todo", "none", "placeholder"}

#: Generous, because a dense board's zone refill takes real time; a run that
#: hangs past it fails the design rather than the check waiting forever.
KICAD_TIMEOUT_S = 900

#: The most failures of one kind KiCad's command-line layout check reports, as
#: KiCad 10.0.7 is observed to do. Past it KiCad reports that many and drops the
#: rest, and which it drops changes from run to run, so a report holding this
#: many failures of one kind cannot be read as holding them all.
REPORT_LIMIT = 199

#: Characters a name cannot hold and still be written into a rule's condition
#: or a rule's name.
UNWRITABLE = set("'\"\\")

TOOL_HELP = "see hardware/README.md for what the check needs and where to get it"


class CannotRun(Exception):
    """The check cannot be run at all, so it reports nothing rather than a pass."""


class Violation:
    """One finding, in the shape every report line takes."""

    def __init__(self, design: str, rule: str, location: str, message: str):
        self.design = design
        self.rule = rule
        self.location = location
        self.message = message

    def line(self) -> str:
        fields = (self.design, self.rule, self.location, self.message)
        return "VIOLATION | " + " | ".join(clean(field) for field in fields)

    def __repr__(self) -> str:
        return self.line()


def clean(text: str) -> str:
    """A field that cannot break the line it is printed on."""
    return " ".join(str(text).replace("|", "/").split())


# --- Tools --------------------------------------------------------------------


def version_tuple(text: str) -> Optional[Tuple[int, int]]:
    match = re.search(r"(\d+)\.(\d+)", text)
    return (int(match.group(1)), int(match.group(2))) if match else None


def require_python(version_info: Sequence[int] = tuple(sys.version_info)) -> None:
    if tuple(version_info[:2]) < MIN_PYTHON:
        found = ".".join(str(part) for part in version_info[:3])
        raise CannotRun(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is needed to run the check, and this is "
            f"Python {found}. Install a newer Python from https://www.python.org/downloads/ ({TOOL_HELP})."
        )


def require_yaml():
    """PyYAML, which reads the separation basis record, at its minimum version."""
    try:
        import yaml
    except ImportError as error:
        raise CannotRun(
            f"PyYAML {MIN_PYYAML[0]}.{MIN_PYYAML[1]} or newer is needed to read the separation basis "
            "record, and is not installed. Install it (pip install pyyaml, or your system's "
            f"python3-yaml package) ({TOOL_HELP})."
        ) from error
    found = version_tuple(getattr(yaml, "__version__", ""))
    if found is None or found < MIN_PYYAML:
        raise CannotRun(
            f"PyYAML {MIN_PYYAML[0]}.{MIN_PYYAML[1]} or newer is needed to read the separation basis "
            f"record, and the installed one is {getattr(yaml, '__version__', 'of unknown version')}. "
            f"Upgrade it (pip install --upgrade pyyaml) ({TOOL_HELP})."
        )
    return yaml


def require_git(git: str, root: str) -> str:
    """The top of the git work tree holding `root`, which is where designs are looked for."""
    how = f"Install git {MIN_GIT[0]}.{MIN_GIT[1]} or newer from https://git-scm.com/downloads ({TOOL_HELP})."
    try:
        version = subprocess.run([git, "--version"], capture_output=True, text=True)
    except OSError as error:
        raise CannotRun(
            f"git is needed to find the board designs the repository tracks, and '{git}' could not be "
            f"run ({error}). {how}"
        ) from error
    found = version_tuple(version.stdout)
    if version.returncode != 0 or found is None or found < MIN_GIT:
        said = " ".join((version.stdout + version.stderr).split())[:200] or f"exit {version.returncode}"
        raise CannotRun(
            f"git {MIN_GIT[0]}.{MIN_GIT[1]} or newer is needed to tell a committed file from one changed since, "
            f"and '{git}' reports {said}. {how}"
        )
    result = subprocess.run([git, "-C", root, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if result.returncode != 0:
        raise CannotRun(
            f"the check finds board designs through git, and {root} is not inside a git work tree "
            f"({result.stderr.strip()})."
        )
    return result.stdout.strip()


def require_kicad(kicad_cli: str) -> str:
    """KiCad's command-line tool at its minimum version; its version string."""
    how = (
        f"Install KiCad {MIN_KICAD[0]}.{MIN_KICAD[1]} or newer from https://www.kicad.org/download/. "
        "kicad-cli is often installed off the search path: if so, run the task with "
        "KICAD_CLI=/path/to/kicad-cli (hardware/README.md gives its usual location on each operating system)."
    )
    try:
        result = subprocess.run([kicad_cli, "version"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CannotRun(f"kicad-cli was not found or could not be run at '{kicad_cli}' ({error}). {how}") from error
    found = version_tuple(result.stdout)
    if result.returncode != 0 or found is None:
        raise CannotRun(
            f"'{kicad_cli}' did not report a KiCad version (exit {result.returncode}: "
            f"{(result.stdout + result.stderr).strip()[:200]}). {how}"
        )
    if found < MIN_KICAD:
        raise CannotRun(
            f"kicad-cli at '{kicad_cli}' is KiCad {result.stdout.strip()}, older than the "
            f"{MIN_KICAD[0]}.{MIN_KICAD[1]} this repository's board files need. {how}"
        )
    return result.stdout.strip()


#: The environment every KiCad run of the check is given, set by isolate_kicad;
#: None runs KiCad as the caller's environment leaves it.
KICAD_ENVIRONMENT: Optional[Dict[str, str]] = None


def isolate_kicad(kicad_cli: str, version: str, home: str) -> Dict[str, str]:
    """An environment running KiCad with a configuration of the check's own, in `home`.

    KiCad otherwise reads the user's own configuration: their machine-wide
    library tables, the path variables they defined, and any KICAD variable in
    their environment. A design leaning on any of those would pass on the
    machine it was drawn on and nowhere else. Here KiCad sees, besides the
    design's own tables, only the libraries it installs with itself, named
    through its own template variable so it finds them wherever it is
    installed; a library from anywhere else is then reported by KiCad as one
    its configuration does not include.
    """
    environment = {name: value for name, value in os.environ.items()
                   if not name.upper().startswith("KICAD") and name.upper() != "KIPRJMOD"}
    environment["KICAD_CONFIG_HOME"] = home
    subprocess.run([kicad_cli, "version"], env=environment, capture_output=True, timeout=120)
    folders = [name for name in os.listdir(home) if os.path.isdir(os.path.join(home, name))]
    if len(folders) != 1:
        raise CannotRun(f"KiCad did not set up a configuration of its own in {home} (found {folders or 'nothing'}), "
                        f"so the check cannot keep this machine's KiCad settings out of the result ({TOOL_HELP}).")
    major = version_tuple(version)[0]
    for kind in ("sym", "fp"):
        with open(os.path.join(home, folders[0], f"{kind}-lib-table"), "w", encoding="utf-8") as handle:
            handle.write(f'({kind}_lib_table\n\t(version 7)\n\t(lib (name "KiCad")(type "Table")'
                         f'(uri "${{KICAD{major}_TEMPLATE_DIR}}/{kind}-lib-table")(options "")'
                         '(descr "The libraries KiCad installs with itself"))\n)\n')
    return environment


# --- Finding the designs -------------------------------------------------------


class Design:
    """One KiCad project and the schematic and layout beside it, by repository-relative path."""

    def __init__(self, project: str):
        self.project = project
        stem = project[: -len(".kicad_pro")]
        self.directory = os.path.dirname(project)
        self.schematic = stem + ".kicad_sch"
        self.layout = stem + ".kicad_pcb"
        self.rules = stem + ".kicad_dru"
        self.name = os.path.basename(stem)


class Repository:
    """The files git tracks, which are all the check ever reads of a design."""

    def __init__(self, root: str, tracked, git: str = "git"):
        self.root = root
        self.tracked = set(tracked)
        self.git = git

    def on_disk(self, path: str) -> bool:
        return os.path.lexists(os.path.join(self.root, path))

    def untracked(self, path: str) -> Optional[str]:
        """Why a file present beside a design is not one the check may read, or None when git tracks it."""
        if path in self.tracked or not self.on_disk(path):
            return None
        ignored = subprocess.run([self.git, "-C", self.root, "check-ignore", "-q", "--", path], capture_output=True)
        return "is ignored by git" if ignored.returncode == 0 else "is not tracked in the repository"

    def uncommitted(self, path: str) -> Optional[str]:
        """Why a file is not committed exactly as it stands on disk, or None when it is."""
        if path not in self.tracked:
            return self.untracked(path) or "is not tracked in the repository"
        status = subprocess.run([self.git, "-C", self.root, "status", "--porcelain=v1", "--ignored", "--", path],
                                capture_output=True, text=True)
        if status.returncode != 0:
            return f"could not be compared with the last commit ({status.stderr.strip()})"
        code = status.stdout[:2]
        if not code:
            return None
        if "D" in code:
            return "is deleted in the working tree but not in the last commit"
        if code[0] == "A":
            return "is staged but has never been committed"
        return "has changes that are not committed"


def tracked_files(git: str, root: str) -> List[str]:
    result = subprocess.run([git, "-C", root, "ls-files", "-z"], capture_output=True)
    if result.returncode != 0:
        raise CannotRun(f"git could not list the files tracked under {root}: {result.stderr.decode(errors='replace').strip()}")
    return [path for path in result.stdout.decode("utf-8", errors="replace").split("\0") if path]


def sheet_files(root: str, schematic: str, tracked: Set[str], seen: Optional[Set[str]] = None,
                missing: Optional[List[Tuple[str, str]]] = None,
                unnamed: Optional[List[Tuple[str, str, int]]] = None) -> Set[str]:
    """Every schematic file a root schematic reaches through its hierarchical sheets.

    A sheet git does not track is never read, since the check reads a design
    only as the repository holds it; it is added to `missing` as (the sheet,
    the schematic naming it) instead. A sheet is read in the one form KiCad 10
    writes, naming its file in exactly one Sheetfile property; one naming its
    file any other way, or more than once, is added to `unnamed` as (the
    schematic, the sheet's name, how many files it names), since which file
    KiCad would open for it is not something to guess. Raises SexprError or
    OSError when a tracked sheet cannot be read.
    """
    seen = set() if seen is None else seen
    if schematic in seen:
        return seen
    seen.add(schematic)
    with open(os.path.join(root, schematic), encoding="utf-8") as handle:
        tree = sexpr.parse_one(handle.read())
    for sheet in sexpr.children(tree, "sheet"):
        named = [prop for prop in sexpr.children(sheet, "property") if len(prop) > 1 and prop[1] == "Sheetfile"]
        if len(named) != 1 or len(named[0]) < 3 or isinstance(named[0][2], list):
            if unnamed is not None:
                title = next((str(prop[2]) for prop in sexpr.children(sheet, "property")
                              if len(prop) > 2 and prop[1] == "Sheetname"), "(unnamed)")
                unnamed.append((schematic, title, len(named)))
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(schematic), named[0][2])).replace(os.sep, "/")
        if target not in tracked:
            if missing is not None and target not in seen:
                missing.append((target, schematic))
            seen.add(target)
            continue
        sheet_files(root, target, tracked, seen, missing, unnamed)
    return seen


def sheet_instances(root: str, schematic: str, tracked: Set[str], trail: Tuple[str, ...] = (),
                    ancestry: Tuple[str, ...] = ()) -> List[Tuple[str, ...]]:
    """Every sheet instance a root schematic draws, as the chain of sheet names from the root down.

    The root is the empty chain. A sheet file placed twice is two instances,
    one under each name it is placed under, and a sheet below a sheet is
    reached through the sheet above it. A sheet read as `sheet_files` reads
    it; one it would not follow (untracked, or naming no one file) is not
    counted, since `discover` reports it. A schematic that places itself
    again below itself is followed once. Raises SexprError or OSError when a
    tracked sheet cannot be read.
    """
    found: List[Tuple[str, ...]] = [trail]
    if schematic in ancestry:
        return found
    with open(os.path.join(root, schematic), encoding="utf-8") as handle:
        tree = sexpr.parse_one(handle.read())
    for sheet in sexpr.children(tree, "sheet"):
        props = sexpr.children(sheet, "property")
        named = [prop for prop in props if len(prop) > 1 and prop[1] == "Sheetfile"]
        if len(named) != 1 or len(named[0]) < 3 or isinstance(named[0][2], list):
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(schematic), named[0][2])).replace(os.sep, "/")
        if target not in tracked:
            continue
        title = next((str(prop[2]) for prop in props if len(prop) > 2 and prop[1] == "Sheetname"), "")
        found.extend(sheet_instances(root, target, tracked, trail + (title,), ancestry + (schematic,)))
    return found


#: What KiCad names a sheet nobody named, optionally numbered when a second is left unnamed.
DEFAULT_SHEET_NAME = re.compile(r"Untitled Sheet( [0-9]+)?")


def sheet_names(root: str, schematic: str, tracked: Set[str], ancestry: Tuple[str, ...] = ()
                ) -> List[Tuple[str, str]]:
    """Every sheet symbol a schematic and the sheets below it draw, as (the schematic drawing it, its Sheetname).

    Sheets are followed as `sheet_instances` follows them, so the root, which
    has no sheet symbol, is not among them; a sheet with no Sheetname property
    reads as a blank one. Raises SexprError or OSError when a tracked sheet
    cannot be read.
    """
    if schematic in ancestry:
        return []
    with open(os.path.join(root, schematic), encoding="utf-8") as handle:
        tree = sexpr.parse_one(handle.read())
    found: List[Tuple[str, str]] = []
    for sheet in sexpr.children(tree, "sheet"):
        props = sexpr.children(sheet, "property")
        found.append((schematic, next((str(prop[2]) for prop in props if len(prop) > 2 and prop[1] == "Sheetname"), "")))
        named = [prop for prop in props if len(prop) > 1 and prop[1] == "Sheetfile"]
        if len(named) != 1 or len(named[0]) < 3 or isinstance(named[0][2], list):
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(schematic), named[0][2])).replace(os.sep, "/")
        if target in tracked:
            found.extend(sheet_names(root, target, tracked, ancestry + (schematic,)))
    return found


def unnamed_sheets(design: Design, repository: Repository) -> List[Violation]:
    """A hierarchical sheet whose name is blank or the tool's default fails; a sheet that cannot be read is `discover`'s to report."""
    try:
        sheets = sheet_names(repository.root, design.schematic, repository.tracked)
    except (OSError, sexpr.SexprError):
        return []
    found = []
    for parent, name in sheets:
        if name.strip() and not DEFAULT_SHEET_NAME.fullmatch(name.strip()):
            continue
        shown = f"{name!r}, KiCad's default for a sheet nobody named" if name.strip() else "blank"
        found.append(Violation(
            design.project, "unnamed_sheet", parent,
            f"a sheet drawn in {parent} carries no name of its own: its name is {shown}, so a reader "
            "following the schematic by what each sheet does is told nothing; rename the sheet for its function "
            "in its Sheetname property"))
    return found


def discover(root: str, files: List[str]) -> Tuple[List[Design], List[Violation], Dict[str, List[Violation]]]:
    """The designs among the tracked files, the files belonging to none, and what is wrong with each design's set."""
    tracked = set(files)
    designs = [Design(path) for path in sorted(files) if path.endswith(".kicad_pro")]
    owned: Set[str] = set()
    problems: Dict[str, List[Violation]] = {}
    for design in designs:
        found = problems.setdefault(design.project, [])
        for path, kind in ((design.schematic, "schematic"), (design.layout, "layout")):
            owned.add(path)
            if path not in tracked:
                found.append(Violation(
                    design.project, "design_discovery", path,
                    f"the project has no {kind} beside it: {path} is not tracked in the repository, so the "
                    "design cannot be checked; a board design is a project file with both its schematic and "
                    "its layout beside it, so commit the missing file or remove the project"))
        if design.schematic in tracked and os.path.exists(os.path.join(root, design.schematic)):
            missing: List[Tuple[str, str]] = []
            unnamed: List[Tuple[str, str, int]] = []
            try:
                owned.update(sheet_files(root, design.schematic, tracked, missing=missing, unnamed=unnamed))
            except (OSError, sexpr.SexprError) as error:
                found.append(Violation(
                    design.project, "design_unreadable", design.schematic,
                    f"the schematic or one of its sheets cannot be read ({error}); correct the file at that point, "
                    "or restore it from the repository's history"))
            for sheet, parent in missing:
                found.append(Violation(
                    design.project, "design_discovery", sheet,
                    f"{parent} names the sheet {sheet}, which is not tracked in the repository, so the design "
                    "is only half committed and its schematic cannot be checked as the repository holds it; "
                    "commit the sheet, or remove it from the schematic"))
            for parent, title, count in unnamed:
                found.append(Violation(
                    design.project, "design_discovery", f"{parent} sheet '{title}'",
                    f"the sheet {('has no Sheetfile property', 'has a Sheetfile property naming no file')[count] if count < 2 else f'has {count} Sheetfile properties'}, "
                    "where KiCad 10 writes exactly one naming the sheet's file, so which file it holds cannot be told "
                    "and the design cannot be checked whole; give the sheet one Sheetfile property naming its file"))
    orphans = []
    for path in sorted(files):
        if path.endswith((".kicad_sch", ".kicad_pcb")) and path not in owned:
            kind = "schematic" if path.endswith(".kicad_sch") else "layout"
            orphans.append(Violation(
                path, "design_discovery", path,
                f"a {kind} is tracked without being part of any board design: no project file "
                f"(.kicad_pro) beside it names it, so it would otherwise escape the check; commit its "
                "project beside it, or remove it"))
    return designs, orphans, problems


#: The library tables a KiCad project may carry beside it.
LIBRARY_TABLES = ("sym-lib-table", "fp-lib-table")

#: Variables naming the libraries KiCad installs with itself, which a reader
#: holding the named tools has; every other variable is set on one machine.
KICAD_LIBRARY_VARIABLE = re.compile(r"KICAD\d*_(SYMBOL|FOOTPRINT|3DMODEL|TEMPLATE)_DIR")


def library_path(design: Design, uri: str) -> Tuple[Optional[str], str]:
    """Where in the repository a library table entry points, or why it points nowhere a reader has.

    Returns (repository-relative path, '') for a library the repository can
    hold, (None, '') for one KiCad installs with itself, and (None, why) for one
    that only the machine the table was written on can reach.
    """
    text = str(uri).replace("\\", "/")
    anchored = re.match(r"\$[{(]KIPRJMOD[)}]/*", text)
    if anchored:
        text = text[anchored.end():]
    variables = re.findall(r"\$[{(]([^)}]*)[)}]", text)
    if variables:
        if all(KICAD_LIBRARY_VARIABLE.fullmatch(name) for name in variables):
            return None, ""
        foreign = ", ".join(f"${{{name}}}" for name in variables if not KICAD_LIBRARY_VARIABLE.fullmatch(name))
        return None, (f"it is reached through {foreign}, which this machine's KiCad configuration defines and the "
                      "repository does not")
    if re.match(r"/|[A-Za-z]:/|~", text):
        return None, "it is named by an absolute path, which holds only on the machine the table was written on"
    path = os.path.normpath(os.path.join(design.directory, text)).replace(os.sep, "/")
    if path == ".." or path.startswith("../"):
        return None, "it lies outside the repository"
    return path, ""


#: Each clause a library table entry may hold, and whether it must be there.
LIBRARY_CLAUSES = {"name": True, "type": True, "uri": True, "options": False, "descr": False,
                   "disabled": False, "hidden": False}


def library_entries(design: Design, path: str, table: list) -> Tuple[List[Tuple[str, str]], List[Violation]]:
    """The (nickname, location) of each library a table names, and every part of it not in the form KiCad writes.

    The one form read is the table KiCad writes: a list headed for its kind,
    an optional (version ...), and (lib ...) entries, each holding exactly one
    name, one type of KiCad, one location, and at most one of each other clause
    KiCad writes. Anything else -- another kind of library, which a reader may
    not have the means to open, a nickname given twice, of which KiCad uses only
    one, or a clause the check does not know -- fails by name rather than being
    read past.
    """
    kind = os.path.basename(path).replace("-", "_")
    found: List[Violation] = []

    def fail(where: str, message: str) -> None:
        found.append(Violation(design.project, "design_library", where,
                               f"{message}; a library table holds only (version ...) and (lib (name ...) (type \"KiCad\") "
                               "(uri ...) (options ...) (descr ...)) entries, as KiCad writes them, so write it in that form"))

    if sexpr.head(table) != kind:
        fail(path, f"the file is headed ({sexpr.head(table) or '...'} ...), not ({kind} ...)")
        return [], found
    entries: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    versions = 0
    for item in table[1:]:
        if sexpr.head(item) == "version":
            versions += 1
            if versions > 1:
                fail(path, "the table states its (version ...) more than once")
            continue
        if sexpr.head(item) != "lib":
            fail(path, f"the table holds a ({sexpr.head(item) or str(item)} ...) form, which is not a library entry")
            continue
        clauses: Dict[str, List[list]] = {}
        for clause in item[1:]:
            clauses.setdefault(sexpr.head(clause) or str(clause), []).append(clause)
        name_clause = clauses.get("name", [[]])[0]
        name = str(name_clause[1]) if len(name_clause) > 1 else "(unnamed)"
        where = f"{path} library '{name}'"
        problems = [f"a ({clause} ...) clause, which is not one KiCad writes in a library entry"
                    for clause in clauses if clause not in LIBRARY_CLAUSES]
        for clause, required in LIBRARY_CLAUSES.items():
            count = len(clauses.get(clause, []))
            if count > 1:
                problems.append(f"{count} ({clause} ...) clauses, of which KiCad reads only one")
            elif required and count == 0:
                problems.append(f"no ({clause} ...) clause")
            elif count and clause in ("name", "type", "uri") and (len(clauses[clause][0]) != 2
                                                                    or isinstance(clauses[clause][0][1], list)):
                problems.append(f"a ({clause} ...) clause holding something other than one value")
        library_type = clauses.get("type", [[]])[0]
        if not problems and str(library_type[1]) != "KiCad":
            problems.append(f"the type '{library_type[1]}', where the check reads only KiCad's own library format, "
                            "the one a reader holding the named tools can open")
        if not problems and name in seen:
            problems.append(f"the nickname '{name}', which an earlier entry already takes, so KiCad uses only one of them")
        if problems:
            fail(where, "the library entry holds " + "; ".join(problems))
            continue
        seen.add(name)
        entries.append((name, str(clauses["uri"][0][1])))
    return entries, found


def design_files(design: Design, repository: Repository) -> Tuple[List[str], List[Violation]]:
    """Every tracked file KiCad reads for a design, and every file it would read that a reader does not have.

    That is everything tracked in the design's own folder, the sheets its
    schematic reaches wherever they sit, and each library its tables name
    wherever in the repository it sits, so a design reaching above its own
    folder is checked with what it reaches rather than without it. A library
    the repository does not hold fails by name instead of KiCad quietly
    loading it from wherever this machine keeps it, or not at all.
    """
    tracked = repository.tracked
    prefix = design.directory + "/" if design.directory else ""
    files = {path for path in tracked if path.startswith(prefix)}
    try:
        files |= sheet_files(repository.root, design.schematic, tracked) & tracked
    except (OSError, sexpr.SexprError):
        pass
    found = []
    for table in LIBRARY_TABLES:
        path = prefix + table
        untracked = repository.untracked(path)
        if untracked is not None:
            found.append(Violation(design.project, "design_library", path,
                                   f"the library table {untracked}, so KiCad would load the design's libraries "
                                   "here from a table the repository does not hold; commit it, or remove it"))
            continue
        if path not in tracked or not os.path.isfile(os.path.join(repository.root, path)):
            continue
        try:
            with open(os.path.join(repository.root, path), encoding="utf-8") as handle:
                table = sexpr.parse_one(handle.read())
        except (OSError, sexpr.SexprError) as error:
            found.append(Violation(design.project, "design_unreadable", path,
                                   f"the library table cannot be read ({error}); correct the file at that point, "
                                   "or restore it from the repository's history"))
            continue
        entries, misread = library_entries(design, path, table)
        found += misread
        for name, uri in entries:
            target, why = library_path(design, uri)
            where = f"{path} library '{name}'"
            if why:
                found.append(Violation(design.project, "design_library", where,
                                       f"the library '{name}' is at {uri}, and {why}, so a reader holding only the "
                                       "repository and the named tools cannot check the design with it; put the "
                                       "library in the repository and name it from the table through ${KIPRJMOD}"))
                continue
            if target is None:
                continue
            held = {file for file in tracked if file == target or file.startswith(target + "/")}
            if not held:
                found.append(Violation(design.project, "design_library", where,
                                       f"the library '{name}' is at {uri}, which is {target} in the repository, and "
                                       "git tracks nothing there, so the design cannot be checked with the library "
                                       "it names; commit the library, or correct the table"))
            files |= held
    return sorted(files), found


# --- The separation basis record ---------------------------------------------


def find_record(root: str, directory: str, tracked: Set[str] = frozenset(), name: str = RECORD_NAME) -> Optional[str]:
    """The nearest record called `name` at or above a design's folder, repository-relative.

    One that is on disk or tracked counts, so an uncommitted record nearer the
    design than a committed one is the one found, and fails, rather than being
    passed over for the committed one above it.
    """
    current = directory
    while True:
        candidate = (os.path.join(current, name) if current else name).replace(os.sep, "/")
        if candidate in tracked or os.path.lexists(os.path.join(root, candidate)):
            return candidate
        if not current:
            return None
        current = os.path.dirname(current)


def is_placeholder(value: str) -> bool:
    text = value.strip()
    return text.lower() in PLACEHOLDERS or re.search(r"<[^>]*>", text) is not None


def positive_number(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


#: The keys a separation basis record holds, and the two each mains_to_low_voltage-style pair holds.
RECORD_KEYS = {"standard", "supply", "working_voltage", "pollution_degree", "material_group", "environment",
               "barriers", "mains_to_low_voltage", "accepted_by", "accepted_on", "synthetic",
               "overvoltage_category", "altitude_m", "barrier_types", "table_rows"}
PAIR_KEYS = {"clearance_mm", "creepage_mm"}
#: The keys inside the inputs a record states, each of which is optional on a record; the rest of the forms the
#: separation basis decision fixes for them are read in read_inputs.
INSULATIONS = ("basic", "reinforced")
BARRIER_KEYS = ("barrier", "insulation", "earth_bonded", "touchable", "formed_by")
CITATION_KEYS = ("document", "edition", "locator")
ROW_KEYS = ("citation", "inputs", "figure")
ROW_INPUT_KEYS = ("working_voltage_v", "insulation", "overvoltage_category", "pollution_degree", "material_group",
                  "altitude_m")


class Signed(tuple):
    """The signed mains_to_low_voltage figures as (clearance, creepage) in mm, carrying the record they were read from.

    `basis` is the record's mapping, so the rules that hold a design to more
    than the two figures read the inputs and table rows from the one reading.
    """

    def __new__(cls, clearance: float, creepage: float, basis: dict):
        signed = super().__new__(cls, (clearance, creepage))
        signed.basis = basis
        return signed


class RecordForm(Exception):
    """The record is YAML, but not in the one form the check reads."""


def strict_yaml(yaml, text: str):
    """The YAML document in `text`, refusing a key given twice or a merge key.

    PyYAML keeps the last of two equal keys and folds a merge key's mapping in
    beneath the keys written beside it, so a record read past either could say
    one thing to a reader and another to the check.
    """
    class Loader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        keys = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise RecordForm(f"it uses a YAML merge key (<<) at line {key_node.start_mark.line + 1}, which the "
                                 "check does not read; write every key out in full")
            key = loader.construct_object(key_node, deep=True)
            if key in keys:
                raise RecordForm(f"it gives the key '{key}' more than once (again at line {key_node.start_mark.line + 1}), "
                                 "and a reader and the check could each take a different one; give it once")
            keys.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    return yaml.load(text, Loader=Loader)


class Reading:
    """The violations found in one record, each at a path inside it, and the forms a record's values are read in."""

    def __init__(self, design: Design, rule: str, record: str, what: str):
        self.design = design
        self.rule = rule
        self.record = record
        self.what = what
        self.found: List[Violation] = []

    def bad(self, path: str, message: str) -> None:
        self.found.append(Violation(self.design.project, self.rule, f"{self.record} {path}".strip(), message))

    def distinct(self, path: str, keys: Sequence[str], what: str) -> None:
        """Reports each key that `keys` holds more than once, since a reader that indexes by it would let the later entry replace the earlier."""
        seen: Set[str] = set()
        for key in keys:
            if key in seen:
                self.bad(path, f"{path} lists {what} '{key}' more than once, so one entry would replace another; list it once")
            seen.add(key)

    def mapping(self, path: str, value, keys: Sequence[str], required: Sequence[str] = (), whose: str = "") -> bool:
        """Whether `value` is a mapping; if so, every key in it that `keys` does not hold and every `required` one it lacks is reported."""
        label = path or "the record"
        if not isinstance(value, dict):
            self.bad(path, f"{label} is not a mapping of the keys {', '.join(keys)}")
            return False
        for key in sorted(set(map(str, value)) - set(keys)):
            self.bad(f"{path}.{key}" if path else key,
                     f"{label} holds the key '{key}', which is not one {whose or 'a ' + self.what} has: its keys are "
                     f"{', '.join(sorted(keys))}; correct the key's spelling, or remove it")
        for key in required:
            if key not in value:
                self.bad(f"{path}.{key}" if path else key, f"{label} lacks {key}, which every {whose or self.what} states")
        return True

    def listed(self, path: str, value, what: str, empty: bool = False) -> bool:
        if not isinstance(value, list):
            self.bad(path, f"{path} is not a list of {what}")
            return False
        if not value and not empty:
            self.bad(path, f"{path} lists no {what}, so it would hold a design to nothing")
            return False
        return True

    def text(self, path: str, value) -> bool:
        if not isinstance(value, str) or not value.strip():
            self.bad(path, f"{path} is {value!r}, where it is a non-empty string; quote a value that YAML would read as a number")
            return False
        return True

    def positive(self, path: str, value, unit: str = "") -> bool:
        if not positive_number(value):
            self.bad(path, f"{path} is {value!r}, which is not a positive number{unit}")
            return False
        return True

    def number(self, path: str, value) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            self.bad(path, f"{path} is {value!r}, which is not a number")
            return False
        return True

    def whole(self, path: str, value, low: int, high: int) -> bool:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            self.bad(path, f"{path} is {value!r}, where it is a whole number from {low} to {high}")
            return False
        return True

    def boolean(self, path: str, value) -> bool:
        if not isinstance(value, bool):
            self.bad(path, f"{path} is {value!r}, where it is true or false")
            return False
        return True

    def date(self, path: str, value) -> bool:
        if iso_date(value) is None:
            self.bad(path, f"{path} {value!s} is not a valid calendar date written as YYYY-MM-DD")
            return False
        return True

    def one_of(self, path: str, value, choices: Sequence[str]) -> bool:
        if value not in choices or not isinstance(value, str):
            self.bad(path, f"{path} is {value!r}, where it is {' or '.join(choices)}")
            return False
        return True


def read_inputs(design: Design, record: str, data: dict) -> List[Violation]:
    """The form of the inputs a separation basis record states its figures at, each key optional on the record."""
    reading = Reading(design, "separation_basis", record, "separation basis record")
    if "overvoltage_category" in data:
        reading.whole("overvoltage_category", data["overvoltage_category"], 1, 4)
    if "altitude_m" in data:
        reading.positive("altitude_m", data["altitude_m"], " of metres")

    if "barrier_types" in data:
        named = data.get("barriers", [])
        names: Optional[Set[str]] = None
        if not isinstance(named, list) or not all(isinstance(item, str) and item.strip() for item in named):
            reading.bad("barriers", "barriers is not a list of the barriers' names, so barrier_types cannot name an "
                                    "entry for each; write each barrier as a name")
        else:
            names = set(named)
        if reading.listed("barrier_types", data["barrier_types"], "barrier entries", empty=True):
            entries = {}
            for index, entry in enumerate(data["barrier_types"]):
                where = f"barrier_types[{index}]"
                if not reading.mapping(where, entry, BARRIER_KEYS, BARRIER_KEYS, "a barrier entry"):
                    continue
                if "insulation" in entry:
                    reading.one_of(f"{where}.insulation", entry["insulation"], INSULATIONS)
                if "earth_bonded" in entry:
                    reading.boolean(f"{where}.earth_bonded", entry["earth_bonded"])
                if "formed_by" in entry:
                    reading.text(f"{where}.formed_by", entry["formed_by"])
                if "touchable" in entry and reading.listed(f"{where}.touchable", entry["touchable"], "parts", empty=True):
                    for position, part in enumerate(entry["touchable"]):
                        reading.text(f"{where}.touchable[{position}]", part)
                name = entry.get("barrier")
                if "barrier" in entry and reading.text(f"{where}.barrier", name):
                    if names is not None and name not in names:
                        reading.bad(f"{where}.barrier", f"{where}.barrier is '{name}', which barriers does not list; "
                                                        "name a barrier the record relies on, or list it under barriers")
                    elif name in entries:
                        reading.bad(f"{where}.barrier", f"{where}.barrier is '{name}', which the entry at "
                                                        f"barrier_types[{entries[name]}] already describes; each barrier has one entry")
                    else:
                        entries[name] = index
            for name in sorted((names or set()) - set(entries)):
                reading.bad("barrier_types", f"barriers lists '{name}' and barrier_types holds no entry for it; "
                                             "each barrier relied on has exactly one entry")

    if "table_rows" in data and reading.listed("table_rows", data["table_rows"], "table rows", empty=True):
        for index, row in enumerate(data["table_rows"]):
            where = f"table_rows[{index}]"
            if not reading.mapping(where, row, ROW_KEYS, ROW_KEYS, "a table row"):
                continue
            if "citation" in row and reading.mapping(f"{where}.citation", row["citation"], CITATION_KEYS, CITATION_KEYS, "a citation"):
                for key in CITATION_KEYS:
                    if key in row["citation"]:
                        reading.text(f"{where}.citation.{key}", row["citation"][key])
            inputs = row.get("inputs")
            if "inputs" in row and reading.mapping(f"{where}.inputs", inputs, ROW_INPUT_KEYS, (), "a table row's inputs"):
                if not inputs:
                    reading.bad(f"{where}.inputs", f"{where}.inputs is empty, so it states no input the row is read at")
                form = {"working_voltage_v": lambda path, value: reading.positive(path, value, " of volts"),
                        "insulation": lambda path, value: reading.one_of(path, value, INSULATIONS),
                        "overvoltage_category": lambda path, value: reading.whole(path, value, 1, 4),
                        "pollution_degree": lambda path, value: reading.whole(path, value, 1, 4),
                        "material_group": reading.text,
                        "altitude_m": lambda path, value: reading.positive(path, value, " of metres")}
                for key in ROW_INPUT_KEYS:
                    if key in inputs:
                        form[key](f"{where}.inputs.{key}", inputs[key])
            figure = row.get("figure")
            if "figure" in row and reading.mapping(f"{where}.figure", figure, tuple(sorted(PAIR_KEYS)), (), "a table row's figure"):
                if not figure:
                    reading.bad(f"{where}.figure", f"{where}.figure is empty, where it holds clearance_mm, creepage_mm or both")
                for key in sorted(PAIR_KEYS):
                    if key in figure:
                        reading.positive(f"{where}.figure.{key}", figure[key], " of millimetres")
    return reading.found


def read_record(yaml, root: str, design: Design, record: Optional[str], not_for_manufacture: bool,
                today: datetime.date, uncommitted: Optional[str] = None
                ) -> Tuple[Optional[Signed], List[Violation]]:
    """The signed mains-to-low-voltage (clearance, creepage) in mm with the record's inputs and table rows, or what stops it being usable.

    `uncommitted` is why the record is not committed exactly as it stands, if it
    is not: the commit that adds or changes a record is its audit trail, so a
    record the commit does not hold is not one anybody has been seen to accept.
    """
    def fail(location: str, message: str) -> Tuple[None, List[Violation]]:
        return None, [Violation(design.project, "separation_basis", location, message)]

    if record is None:
        return fail(
            os.path.join(design.directory, RECORD_NAME),
            f"MAINS is present but there is no {RECORD_NAME} in the design's folder or any folder above it, "
            "so there is no signed separation basis to hold the design to; the separation basis must be "
            "declared and signed before layout")
    if uncommitted is not None:
        return fail(record, f"the separation basis record {uncommitted}; the commit that adds or changes it is its "
                            "audit trail, so the check holds a design only to a record committed exactly as it "
                            "stands: commit it, or discard the change")
    try:
        with open(os.path.join(root, record), encoding="utf-8") as handle:
            data = strict_yaml(yaml, handle.read())
    except RecordForm as error:
        return fail(record, f"the separation basis record cannot be parsed as the check reads it: {error}")
    except Exception as error:  # a YAML error, or a file that cannot be read
        return fail(record, f"the separation basis record cannot be parsed ({' '.join(str(error).split())})")
    if not isinstance(data, dict):
        return fail(record, "the separation basis record cannot be parsed: it is not a mapping of keys")

    pair = data.get("mains_to_low_voltage")
    if not isinstance(pair, dict):
        return fail(f"{record} mains_to_low_voltage",
                    "the record lacks mains_to_low_voltage, the mapping holding clearance_mm and creepage_mm")
    figures = []
    problems = []
    for key, value in sorted(data.items(), key=lambda item: str(item[0])):
        key = str(key)
        if key in RECORD_KEYS:
            continue
        if isinstance(value, dict) and set(map(str, value)) == PAIR_KEYS:
            continue
        problems.append(Violation(design.project, "separation_basis", f"{record} {key}",
                                  f"the record holds the key '{key}', which is not one a separation basis record has: "
                                  f"its keys are {', '.join(sorted(RECORD_KEYS))}, and any further pair of distances "
                                  "for readers is a mapping holding exactly clearance_mm and creepage_mm; correct the "
                                  "key's spelling, or remove it"))
    for key in sorted(set(map(str, pair)) - PAIR_KEYS):
        problems.append(Violation(design.project, "separation_basis", f"{record} mains_to_low_voltage.{key}",
                                  f"mains_to_low_voltage holds '{key}', where it holds only clearance_mm and "
                                  "creepage_mm, the figures compared; correct the key's spelling, or remove it"))
    problems += read_inputs(design, record, data)
    for key in ("clearance_mm", "creepage_mm"):
        if key not in pair:
            problems.append(Violation(design.project, "separation_basis", f"{record} mains_to_low_voltage.{key}",
                                      f"the record lacks mains_to_low_voltage.{key}, so there is no signed figure to hold the design to"))
        elif not positive_number(pair[key]):
            problems.append(Violation(design.project, "separation_basis", f"{record} mains_to_low_voltage.{key}",
                                      f"mains_to_low_voltage.{key} is {pair[key]!r}, which is not a positive number of millimetres"))
        else:
            figures.append(float(pair[key]))

    acceptor = data.get("accepted_by")
    if not isinstance(acceptor, str) or not acceptor.strip():
        problems.append(Violation(design.project, "separation_basis", f"{record} accepted_by",
                                  "the record is unsigned: accepted_by is missing; it must name who accepted the basis"))
    elif is_placeholder(acceptor):
        problems.append(Violation(design.project, "separation_basis", f"{record} accepted_by",
                                  f"the record is unsigned: accepted_by '{acceptor}' is a placeholder, not the identity of whoever accepted the basis"))

    accepted = data.get("accepted_on")
    when: Optional[datetime.date] = None
    if isinstance(accepted, datetime.datetime):
        when = None
    elif isinstance(accepted, datetime.date):
        when = accepted
    elif isinstance(accepted, str):
        try:
            when = datetime.date.fromisoformat(accepted.strip())
        except ValueError:
            when = None
    if accepted is None:
        problems.append(Violation(design.project, "separation_basis", f"{record} accepted_on",
                                  "the record is unsigned: accepted_on, the date the basis was accepted, is missing"))
    elif when is None:
        problems.append(Violation(design.project, "separation_basis", f"{record} accepted_on",
                                  f"the record is unsigned: accepted_on {accepted!s} is not a valid calendar date written as YYYY-MM-DD"))
    elif when > today:
        problems.append(Violation(design.project, "separation_basis", f"{record} accepted_on",
                                  f"the record is unsigned: accepted_on {when.isoformat()} is later than today ({today.isoformat()})"))

    synthetic = data.get("synthetic")
    if "synthetic" in data and not isinstance(synthetic, bool):
        problems.append(Violation(design.project, "separation_basis", f"{record} synthetic",
                                  f"synthetic is {synthetic!r}, where it is true on a record made only to prove the "
                                  "check and false or absent otherwise; write true or false"))
    elif synthetic is True and not not_for_manufacture:
        problems.append(Violation(design.project, "separation_basis", f"{record} synthetic",
                                  "the record is marked synthetic, made only to prove the check, and the design is not "
                                  "marked not for manufacture (NOT_FOR_MANUFACTURE=true), so a proof record cannot let it pass"))

    if problems:
        return None, problems
    return Signed(figures[0], figures[1], data), []


#: The inputs a separation basis record states that the floor is read at, required when a design declares mains present.
FLOOR_KEYS = ("overvoltage_category", "altitude_m", "barrier_types")
#: How strong each insulation is, the strongest of a record's barriers being the one its table rows are read at.
STRENGTH = {"basic": 1, "reinforced": 2}
LEADING_NUMBER = re.compile(r"\s*([0-9]+(?:\.[0-9]+)?)")


def basis_voltage(value) -> Optional[float]:
    """The working voltage in volts rms a basis states, the leading number of its text, or None when it states none."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    found = LEADING_NUMBER.match(value) if isinstance(value, str) else None
    return float(found.group(1)) if found and float(found.group(1)) > 0 else None


def row_applies(inputs: dict, basis: dict, voltage: float, insulation: Optional[str]) -> bool:
    """Whether a table row's inputs hold at the basis: an input the row omits does not constrain it.

    The row's working voltage and altitude are at or above the basis's, its
    overvoltage category, pollution degree and material group equal the
    basis's, and its insulation is the strongest of the basis's barriers; a
    row stating an insulation does not apply when the basis lists no barrier,
    and a row stating an input the basis does not state does not apply.
    """
    for key, held in (("working_voltage_v", voltage), ("altitude_m", basis.get("altitude_m"))):
        if key in inputs and (held is None or inputs[key] < held):
            return False
    for key in ("overvoltage_category", "pollution_degree", "material_group"):
        if key in inputs and inputs[key] != basis.get(key):
            return False
    return "insulation" not in inputs or inputs["insulation"] == insulation


def separation_floor(design: Design, record: str, signed: Signed) -> List[Violation]:
    """What is wrong with the signed figures against the floor the record's own table rows give.

    The basis keys overvoltage_category, altitude_m and barrier_types are
    required here, and so is a working_voltage that begins with a number: a
    design that declares mains present and omits one fails by key. The floor
    for each figure is the largest of that figure over the applicable rows
    that give it; a figure with no applicable row to give it has no floor and
    fails, as does a signed figure below its floor.
    """
    basis = signed.basis
    found = []
    for key in FLOOR_KEYS:
        if key not in basis:
            found.append(Violation(design.project, "separation_floor", f"{record} {key}",
                                   f"the record lacks {key}, which a design that declares mains present must state so "
                                   "the floor its table rows give can be found; add it to the signed record"))
    voltage = basis_voltage(basis.get("working_voltage"))
    if voltage is None:
        found.append(Violation(design.project, "separation_floor", f"{record} working_voltage",
                               f"working_voltage is {basis.get('working_voltage')!r}, which does not begin with a number "
                               "of volts rms, so the rows' working_voltage_v cannot be compared with it; write it as "
                               "'<number> V rms'"))
    if found:
        return found
    strongest = max((entry["insulation"] for entry in basis["barrier_types"]), key=STRENGTH.get, default=None)
    rows = [(index, row) for index, row in enumerate(basis.get("table_rows") or [])
            if row_applies(row["inputs"], basis, voltage, strongest)]
    for index, key in enumerate(("clearance_mm", "creepage_mm")):
        given = [(position, row["figure"][key]) for position, row in rows if key in row["figure"]]
        where = f"{record} mains_to_low_voltage.{key}"
        if not given:
            found.append(Violation(design.project, "separation_floor", where,
                                   f"no table row of the record gives a {key} that applies at working_voltage_v {voltage:g}, "
                                   f"overvoltage_category {basis['overvoltage_category']}, altitude_m {basis['altitude_m']:g} and "
                                   f"{strongest or 'no'} insulation, so the signed {key} has no floor to be held to; "
                                   "add the table row that gives it, or correct the inputs the rows are read at"))
            continue
        floor = max(figure for _, figure in given)
        if signed[index] < floor - 1e-9:
            at = ", ".join(f"table_rows[{position}]" for position, figure in given if figure == floor)
            found.append(Violation(design.project, "separation_floor", where,
                                   f"the signed {key} is {signed[index]:g} mm, below the {floor:g} mm floor the record's own "
                                   f"table rows give ({at}); raise the signed figure to at least {floor:g} mm, or correct "
                                   "the row or the inputs it is read at"))
    return found


#: The two rules written after the signed rule to hold a non-plated hole and a plated hole to the signed distance.
HOLE_RULE = f"{RESERVED}: mounting hole"
PLATED_RULE = f"{RESERVED}: plated hole"
#: The pad types of a drilled pad, plated and not.
DRILLED = ("thru_hole", "np_thru_hole")


def drilled(pad: list) -> bool:
    """Whether a pad is a drilled hole, plated or not."""
    return len(pad) > 2 and str(pad[2]) in DRILLED and sexpr.child(pad, "drill") is not None


def hole_footprints(tree: list) -> List[str]:
    """The references of the footprints that are fixings: at least one pad, each a drilled hole, and any of four marks.

    A footprint with a pad that is not drilled, a surface-mount pad, is a part.
    One of drilled pads is a fixing when every pad is non-plated, or it is left
    out of the bill of materials (KiCad's footprint attribute exclude_from_bom,
    which its stock mounting-hole footprints carry), or its library item name
    begins with MountingHole, or it has exactly one pad. The last two keep a
    forgotten bill-of-materials flag on a custom plated mounting pad from
    skipping the extent checks; they also take in a one-pin through-hole part,
    which is held to the larger distance on purpose. A non-plated hole in any
    other footprint is held by the hole rules.
    """
    found = []
    for reference, footprint in board_footprints(tree).items():
        pads = sexpr.children(footprint, "pad")
        if not pads or not all(drilled(pad) for pad in pads):
            continue
        name = str(footprint[1]).split(":")[-1] if len(footprint) > 1 else ""
        if (all(str(pad[2]) == "np_thru_hole" for pad in pads) or "exclude_from_bom" in (sexpr.child(footprint, "attr") or [])
                or name.startswith("MountingHole") or len(pads) == 1):
            found.append(reference)
    return sorted(found)


def hole_rules(distance: float) -> str:
    """The rules, in KiCad's own form, holding every hole to `distance` mm of a Mains-class item on every layer.

    A non-plated hole is held by its hole and the pad it is drilled through;
    a plated hole on a net outside Mains is held by its hole. A fixing's own
    pad copper and courtyard are measured from the layout file by fixing_gaps.
    """
    return (f'(rule "{HOLE_RULE}"\n\t(condition "A.Pad_Type == \'NPTH, mechanical\' && B.hasNetclass(\'Mains\')")\n'
            f'\t(constraint hole_clearance (min {distance:g}mm))\n\t(constraint physical_clearance (min {distance:g}mm)))\n'
            f'(rule "{PLATED_RULE}"\n\t(condition "A.Pad_Type == \'Through-hole\' && !A.hasNetclass(\'Mains\') && '
            f'B.hasNetclass(\'Mains\')")\n\t(constraint hole_clearance (min {distance:g}mm)))\n')


def hole_probes(nonce: str, tree: list) -> Tuple[str, List[str]]:
    """The assertion rules that show KiCad matches the pad-type conditions the hole rules use, and the names they must fire as.

    One probe for a non-plated pad and one for a plated one, each limited to
    the first footprint of the layout (in reference order) that has such a
    pad, so a probe reports once and cannot crowd the report. A kind the
    layout has no pad of, or only on references that cannot be written into
    a condition, is given no probe.
    """
    text, expected = "", []
    for kind, pad_type, condition in (("non-plated", "np_thru_hole", "NPTH, mechanical"), ("plated", "thru_hole", "Through-hole")):
        names = sorted(name for name, footprint in board_footprints(tree).items()
                       if not UNWRITABLE & set(name)
                       and any(len(pad) > 2 and str(pad[2]) == pad_type for pad in sexpr.children(footprint, "pad")))
        if names:
            rule = f"{RESERVED} {nonce}: {kind} hole item"
            text += (f'(rule "{rule}"\n\t(condition "A.Pad_Type == \'{condition}\' && A.Reference == \'{names[0]}\'")\n'
                     '\t(constraint assertion "false"))\n')
            expected.append(rule)
    return text, expected


def fixing_extents(tree: list, holes: Sequence[str], mains: Set[str]) -> Dict[str, List[Tuple[str, List[Tuple[float, float]]]]]:
    """Each mounting-hole footprint's extent: a polygon for each of its pads' copper and one for its courtyard.

    A pad on a Mains net is left out, being the fixing's own Mains copper. The
    courtyard is the one on the side the footprint is placed on, and a
    footprint that draws none is measured by its pads alone.
    """
    table = board_geometry.net_table(tree)
    found = {}
    for footprint in sexpr.children(tree, "footprint"):
        name = board_geometry.reference(footprint)
        if name not in holes:
            continue
        extents = [(f"pad {pad.number or '(unnumbered)'}", pad.outline())
                   for pad in board_geometry.footprint_pads(footprint, table) if pad.net not in mains]
        layer = sexpr.child(footprint, "layer")
        yard = courtyard(footprint, "B" if layer is not None and len(layer) > 1 and str(layer[1]).startswith("B.") else "F", name)
        if yard is not None:
            extents.append(("courtyard", yard))
        found[name] = extents
    return found


def fixing_gaps(design: Design, tree: list, fills, holes: Sequence[str], mains: Set[str], distance: float) -> List[Violation]:
    """Every mounting hole whose pad copper or courtyard stands inside `distance` mm of a pad, track, via or pour fill of a Mains net.

    The Mains copper is measured on every copper layer, a fixing being a hole
    through the board. The copper of the net a fixing's own pads are on is its
    own and is not measured against it; every other Mains copper is, including
    another fixing's Mains pad. A gap of exactly `distance` meets it. One
    failure is reported for each fixing extent, net and kind of copper, at the
    nearest gap found.
    """
    if not holes:
        return []
    stack = copper_layers(tree)
    every = board_geometry.pads(tree)
    held = set(holes)
    pieces = [(None, piece) for piece in copper_pieces(tree, stack, [pad for pad in every if pad.reference not in held], fills)
              if piece.net in mains]
    pieces += [(pad.reference, Piece("pad", pad.net, [layer for layer in stack if pad.on(layer)], [pad.outline()]))
               for pad in every if pad.reference in held and pad.net in mains]
    extents = fixing_extents(tree, holes, mains)
    own_nets = {name: {pad.net for pad in every if pad.reference == name and pad.net in mains} for name in holes}
    found = []
    for name in holes:
        nearest: Dict[Tuple[str, str, str], Tuple[float, Piece]] = {}
        for label, polygon in extents.get(name, []):
            xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
            for owner, piece in pieces:
                if owner == name or piece.net in own_nets[name]:
                    continue
                left, top, right, bottom = piece.bounds
                if left > max(xs) + distance or right < min(xs) - distance or top > max(ys) + distance or bottom < min(ys) - distance:
                    continue
                gap = min(board_geometry.polygon_distance(polygon, other) for other in piece.polygons)
                key = (label, piece.net, piece.kind)
                if gap < distance - ROUNDING and (key not in nearest or gap < nearest[key][0]):
                    nearest[key] = (gap, piece)
        for (label, net, kind), (gap, piece) in sorted(nearest.items()):
            found.append(Violation(
                design.project, "mounting_hole", f"{design.layout} {name} {label}; {kind} of {net} on {', '.join(piece.layers)}",
                f"the {label} of the mounting hole {name} stands {gap:.3f} mm from a {kind} of Mains-class net {net} on "
                f"{', '.join(piece.layers)}, inside the {distance:g} mm that is the larger of the signed clearance and "
                "creepage, whether or not the fixing is bonded to protective earth; move the hole or the Mains copper apart, "
                "or revise the signed basis"))
    return found


DISTANCE_REPORTED = re.compile(r"actual ([0-9.]+) mm")


def mounting_holes(kicad_cli: str, design: Design, copy: str, layout: str, rules_copy: str, existing: str,
                   signed: Signed, nonce: str, net: Optional[str], tree: list, mains: Set[str], fills=()) -> List[Violation]:
    """Every hole, plated hole or fixing the layout puts inside the larger of the signed figures of a Mains item.

    The distance is the larger of the signed clearance and creepage, on every
    layer, however the fixing is bonded. A fixing's pad copper and courtyard
    are measured from the layout file against the Mains copper, `fills` being
    the layout's fills as KiCad has refilled them. A second KiCad run on the
    copy, after the signed rule and the Mains class are known, holds the rules
    hole_rules writes after them, with a probe for each kind of pad the layout
    has, which must fire for the rules' pad-type conditions to be known to
    match; only the rules' own findings are read. A design with no hole is held
    to nothing for that: its rules fire on nothing.
    """
    distance = max(signed[0], signed[1])
    try:
        measured = fixing_gaps(design, tree, fills, hole_footprints(tree), mains, distance)
    except board_geometry.Unreadable as unread:
        return [Violation(design.project, "design_unreadable", design.layout,
                          f"the layout's copper cannot be read for the distance of its mounting holes from Mains ({unread})")]
    probes, expected = hole_probes(nonce, tree)
    with open(rules_copy, "w", encoding="utf-8") as handle:
        handle.write(existing + appended_rules(signed, nonce, net) + hole_rules(distance) + probes)
    report, why = run_report([kicad_cli, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", layout], copy)
    if report is None:
        return measured + [Violation(design.project, "mounting_hole", design.layout,
                                     f"the holes' distance to Mains cannot be checked: {why}")]
    if not fired(report, marker_rule(nonce)) and not cut_short(report):
        return measured + [Violation(design.project, "mounting_hole", design.layout,
                                     "KiCad did not load the rules that hold the holes to the signed distance from Mains, so no hole was checked")]
    if cut_short(report):
        return measured + [Violation(design.project, "mounting_hole", design.layout,
                                     f"KiCad's report was cut short at {REPORT_LIMIT} assertion failures, so a hole inside the "
                                     "distance may have been dropped from it; correct the design's own assertion failures first")]
    unmatched = [rule for rule in expected if not fired(report, rule)]
    if unmatched:
        return measured + [Violation(design.project, "mounting_hole", design.layout,
                                     "KiCad loaded the rules that hold the holes to the signed distance from Mains but "
                                     "matched no pad of a kind the layout has by its pad type, so a hole inside the "
                                     "distance would pass unseen; run the check with KiCad 10.0 or newer")]
    found = list(measured)
    seen = set()
    ours = tuple(f"(rule '{name}" for name in (HOLE_RULE, PLATED_RULE))
    for entry in report.get("violations") or []:
        description = entry.get("description", "")
        if not any(mark in description for mark in ours):
            continue
        items = entry.get("items") or []
        gap = DISTANCE_REPORTED.search(description)
        kind = "a plated hole on a net outside Mains" if PLATED_RULE in description else "a non-plated hole or its pad"
        location = "; ".join(item_text(item) for item in items) or design.layout
        pair = (kind, frozenset(item_text(item) for item in items))
        if pair in seen:
            continue
        seen.add(pair)
        found.append(Violation(design.project, "mounting_hole", location,
                               f"{kind} stands {gap.group(1) + ' mm' if gap else 'too close'} from a Mains-class item, inside "
                               f"the {distance:g} mm that is the larger of the signed clearance {signed[0]:g} mm and "
                               f"creepage {signed[1]:g} mm, whether or not the fixing is bonded to protective earth; move "
                               "the hole or the Mains copper apart, or revise the signed basis"))
    return found


# --- The pin allocation record and the connectivity it holds a design to ------


class Channel:
    """One entry of the pin allocation record: where a channel's net must land."""

    def __init__(self, channel: str, net: str, controller_pin: str, connector: Optional[str], connector_pin: Optional[str]):
        self.channel = channel
        self.net = net
        self.controller_pin = controller_pin
        self.connector = connector
        self.connector_pin = connector_pin


#: A controller pin's own name: port letter, then number, as in PC6.
PORT_PIN = re.compile(r"P[A-Z][0-9]+")

#: What KiCad names a net no pin joins to anything, which carries no connection.
UNCONNECTED_NET = "unconnected-("

#: How KiCad begins the name of a net the designer left unnamed, wherever in a sheet path it sits.
GENERATED_NET = re.compile(r"(^|/)Net-\(")


def read_pin_record(yaml, root: str, design: Design, record: Optional[str], not_for_manufacture: bool
                    ) -> Tuple[Optional[List[Channel]], List[Violation]]:
    """The channels of the pin allocation record, or what stops it being usable.

    The record holds a list under `channels`; each entry holds `channel`, `net`
    and `controller_pin`, and `connector` with `connector_pin` unless the channel
    stays on the board. Keys the check does not read, such as the firmware's
    own, are ignored.
    """
    def fail(location: str, message: str) -> Tuple[None, List[Violation]]:
        return None, [Violation(design.project, "pin_allocation", location, message)]

    if record is None:
        return fail(os.path.join(design.directory, PIN_RECORD_NAME),
                    f"there is no {PIN_RECORD_NAME} in the design's folder or any folder above it, so there is no pin "
                    "allocation to hold the design's connectivity to; the record must list every channel's net, "
                    "controller pin, connector and connector pin before the board is ordered")
    try:
        with open(os.path.join(root, record), encoding="utf-8") as handle:
            data = strict_yaml(yaml, handle.read())
    except RecordForm as error:
        return fail(record, f"the pin allocation record cannot be parsed as the check reads it: {error}")
    except Exception as error:  # a YAML error, or a file that cannot be read
        return fail(record, f"the pin allocation record cannot be parsed ({' '.join(str(error).split())})")
    if not isinstance(data, dict):
        return fail(record, "the pin allocation record cannot be parsed: it is not a mapping of keys")
    entries = data.get("channels")
    if not isinstance(entries, list):
        return fail(f"{record} channels", "the record lacks channels, the list of the channels with the net, controller pin, "
                                           "connector and connector pin of each")
    if not entries:
        return fail(f"{record} channels", "the record lists no channel, so it would hold any design to nothing; list "
                                          "every channel the board carries")

    problems: List[Violation] = []
    channels: List[Channel] = []

    def text(entry: dict, key: str, where: str, required: bool = True) -> Optional[str]:
        value = entry.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and key == "connector_pin":
            value = str(value)
        if value is None:
            if required:
                problems.append(Violation(design.project, "pin_allocation", where, f"the entry lacks {key}"))
            return None
        if not isinstance(value, str) or not value.strip():
            problems.append(Violation(design.project, "pin_allocation", where,
                                      f"{key} is {value!r}, where it is the text naming the {key.replace('_', ' ')}"))
            return None
        return value.strip()

    for index, entry in enumerate(entries):
        where = f"{record} channels[{index}]"
        if not isinstance(entry, dict):
            problems.append(Violation(design.project, "pin_allocation", where,
                                      "the entry is not a mapping holding channel, net, controller_pin, connector and connector_pin"))
            continue
        name = text(entry, "channel", where)
        where = f"{record} channel {name}" if name else where
        net = text(entry, "net", where)
        controller = text(entry, "controller_pin", where)
        connector = text(entry, "connector", where, required=False)
        connector_pin = text(entry, "connector_pin", where, required=False)
        if (connector is None) != (connector_pin is None):
            problems.append(Violation(design.project, "pin_allocation", where,
                                      "the entry gives only one of connector and connector_pin; give both, or neither for a "
                                      "channel that stays on the board with no connector"))
        if name and net and controller:
            channels.append(Channel(name, net, controller, connector, connector_pin))

    for label, key in (("channel", lambda c: c.channel), ("net", lambda c: c.net),
                       ("controller pin", lambda c: c.controller_pin),
                       ("connector pin", lambda c: (c.connector, c.connector_pin) if c.connector else None)):
        seen: Dict[object, Channel] = {}
        for channel in channels:
            value = key(channel)
            if value is None:
                continue
            if value in seen:
                problems.append(Violation(design.project, "pin_allocation", f"{record} channel {channel.channel}",
                                          f"the {label} {value if isinstance(value, str) else ' pin '.join(value)} is listed for "
                                          f"channel {seen[value].channel} as well; each {label} is listed once"))
            seen.setdefault(value, channel)

    synthetic = data.get("synthetic")
    if "synthetic" in data and not isinstance(synthetic, bool):
        problems.append(Violation(design.project, "pin_allocation", f"{record} synthetic",
                                  f"synthetic is {synthetic!r}, where it is true on a record made only to prove the "
                                  "check and false or absent otherwise; write true or false"))
    elif synthetic is True and not not_for_manufacture:
        problems.append(Violation(design.project, "pin_allocation", f"{record} synthetic",
                                  "the record is marked synthetic, made only to prove the check, and the design is not "
                                  "marked not for manufacture (NOT_FOR_MANUFACTURE=true), so a proof record cannot let it pass"))
    if problems:
        return None, problems
    return channels, []


class PinNode:
    """One pin a net joins in KiCad's netlist: the part, the pin's number and the pin's own name."""

    def __init__(self, ref: str, pin: str, function: str):
        self.ref = ref
        self.pin = pin
        self.function = function

    def names(self) -> List[str]:
        """The names the pin answers to: its own name without the pin number KiCad appends, split at each slash."""
        name = self.function
        if name.endswith("_" + self.pin):
            name = name[:-len(self.pin) - 1]
        return [part for part in name.split("/") if part]

    def ports(self) -> List[str]:
        return [part for part in self.names() if PORT_PIN.fullmatch(part)]

    def describe(self) -> str:
        return f"{self.ref} pin {self.pin}"


def schematic_pin_nodes(netlist: list) -> Dict[str, List[PinNode]]:
    """Every net in KiCad's own netlist of the schematic: name -> the pins it joins, each with its pin name."""
    nets: Dict[str, List[PinNode]] = {}
    for group in walk(netlist, "nets"):
        for net in sexpr.children(group, "net"):
            name = sexpr.child(net, "name")
            if name is None or len(name) < 2:
                continue
            pins = []
            for node in sexpr.children(net, "node"):
                ref, pin, function = sexpr.child(node, "ref"), sexpr.child(node, "pin"), sexpr.child(node, "pinfunction")
                if ref is not None and len(ref) > 1 and pin is not None and len(pin) > 1:
                    pins.append(PinNode(str(ref[1]), str(pin[1]), str(function[1]) if function is not None and len(function) > 1 else ""))
            nets[str(name[1])] = pins
    return nets


def connectivity(design: Design, record: str, channels: List[Channel], nets: Dict[str, List[PinNode]]) -> List[Violation]:
    """The ways the schematic's netlist departs from the channels of the pin allocation record.

    A record names a net as the schematic writes it, or without the leading
    slash KiCad puts before a net of the top sheet. A controller pin is any pin
    named as a port pin, such as PC6, on a part the record names no connector
    for, and a connector pin is any pin of a connector reference the record names.
    """
    def fail(location: str, message: str) -> Violation:
        return Violation(design.project, "connectivity", location, message)

    connectors = {channel.connector for channel in channels if channel.connector}
    found: List[Violation] = []

    def pins_of(net: str) -> Optional[Tuple[str, List[PinNode]]]:
        for name in (net, "/" + net, net[1:] if net.startswith("/") else net):
            if name in nets:
                return name, nets[name]
        return None

    for channel in channels:
        where = f"{record} channel {channel.channel}"
        wanted = f"controller pin {channel.controller_pin}" + (
            f" and connector pin {channel.connector} pin {channel.connector_pin}" if channel.connector else "")
        reached = pins_of(channel.net)
        if reached is None:
            found.append(fail(where, f"channel {channel.channel}: the record lists net {channel.net}, which the design does "
                                     f"not have; the record names {wanted}"))
            continue
        name, pins = reached
        controller = sorted({port for pin in pins if pin.ref not in connectors for port in pin.ports()})
        if channel.controller_pin not in controller:
            found.append(fail(where, f"channel {channel.channel}: net {name} reaches "
                                     f"{'controller pin ' + ', '.join(controller) if controller else 'no controller pin'}, "
                                     f"where the record names controller pin {channel.controller_pin}"))
        if channel.connector and not any(pin.ref == channel.connector and pin.pin == channel.connector_pin for pin in pins):
            landed = sorted(pin.describe() for pin in pins if pin.ref in connectors or re.fullmatch(r"J[0-9]+", pin.ref))
            found.append(fail(where, f"channel {channel.channel}: net {name} reaches "
                                     f"{'connector pin ' + ', '.join(landed) if landed else 'no connector pin'}, "
                                     f"where the record names connector pin {channel.connector} pin {channel.connector_pin}"))

    listed_controller = {channel.controller_pin for channel in channels}
    listed_connector = {(channel.connector, channel.connector_pin) for channel in channels if channel.connector}
    for name in sorted(nets):
        if name.startswith(UNCONNECTED_NET):
            continue
        for pin in nets[name]:
            if pin.ref in connectors:
                if (pin.ref, pin.pin) not in listed_connector:
                    found.append(fail(f"{design.schematic} {pin.describe()}",
                                      f"net {name} is on connector pin {pin.describe()}, which the record does not list; "
                                      "list the channel it carries, or take the connection off the pin"))
            elif pin.ports() and not listed_controller.intersection(pin.ports()):
                found.append(fail(f"{design.schematic} {pin.describe()}",
                                  f"net {name} is on controller pin {', '.join(pin.ports())} ({pin.describe()}), which the "
                                  "record does not list; list the channel it carries, or take the connection off the pin"))
    return found


# --- The parts specification record and the catalogue extract -------------------

PARTS_RECORD_NAME = "parts-specification.yaml"
CATALOGUE_NAME = "catalogue-extract.yaml"

#: The keys a position of the specification record holds; reference and lcsc are required, and class is
#: required of every position by the derated-voltage rule, which reports a position without it.
POSITION_KEYS = ("reference", "value", "package", "rating", "lcsc", "class")
#: The keys an entry of the catalogue extract holds, every one required.
ENTRY_KEYS = ("lcsc", "library_class", "stock", "unit_price")
#: The keys an entry may hold beside them: a lifecycle mapping, which holds all three of LIFECYCLE_KEYS when present.
OPTIONAL_ENTRY_KEYS = ("lifecycle",)
LIFECYCLE_KEYS = ("status", "source", "read_on")

DERATING_NAME = "derating-policy.yaml"
PIN_LIMITS_NAME = "pin-limits.yaml"
#: The keys of the derating policy record, of each class in it, and of the share each class states for a quantity.
DERATING_KEYS = ("source", "classes", "synthetic")
CLASS_KEYS = ("class", "voltage", "power", "temperature")
SHARE_KEYS = ("share", "source")
#: The keys of the pin-limit record, of each power domain, part, part source and pin in it.
PIN_LIMITS_KEYS = ("domains", "parts", "synthetic")
DOMAIN_KEYS = ("name", "rail", "highest_voltage_v")
LIMIT_PART_KEYS = ("lcsc", "source", "pins")
LIMIT_SOURCE_KEYS = ("document", "revision", "section", "read_on")
LIMIT_PIN_KEYS = ("pin", "domain", "absolute_max_v", "absolute_min_v", "tolerates_driven_unpowered")
#: The keys the catalogue extract states of itself that the check requires.
EXTRACT_KEYS = ("read_on", "max_age_days", "entries")

ABSENT = "(absent)"


def iso_date(value) -> Optional[datetime.date]:
    """A calendar date written as YYYY-MM-DD, or None for anything else."""
    if isinstance(value, datetime.datetime):
        return None
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def load_yaml_record(yaml, root: str, repository: Repository, design: Design, name: str, rule: str, what: str
                     ) -> Tuple[Optional[dict], Optional[str], List[Violation]]:
    """The mapping in the nearest file `name` at or above the design, with its path, or why it cannot be used."""
    record = find_record(root, design.directory, repository.tracked, name)

    def fail(location: str, message: str) -> Tuple[None, Optional[str], List[Violation]]:
        return None, record, [Violation(design.project, rule, location, message)]

    if record is None:
        return fail(os.path.join(design.directory, name),
                    f"there is no {name} in the design's folder or any folder above it, so there is no {what} "
                    "to hold the design's parts to; the design's parts must be specified and checked before it is ordered")
    if record not in repository.tracked:
        return fail(record, f"the {what} {repository.untracked(record) or 'is not tracked in the repository'}; "
                            "the check holds a design only to a file the repository holds, so commit it")
    try:
        with open(os.path.join(root, record), encoding="utf-8") as handle:
            data = strict_yaml(yaml, handle.read())
    except RecordForm as error:
        return fail(record, f"the {what} cannot be parsed as the check reads it: {error}")
    except Exception as error:  # a YAML error, or a file that cannot be read
        return fail(record, f"the {what} cannot be parsed ({' '.join(str(error).split())})")
    if not isinstance(data, dict):
        return fail(record, f"the {what} cannot be parsed: it is not a mapping of keys")
    return data, record, []


def synthetic_problem(design: Design, rule: str, record: str, data: dict, what: str, not_for_manufacture: bool
                      ) -> List[Violation]:
    synthetic = data.get("synthetic")
    if "synthetic" in data and not isinstance(synthetic, bool):
        return [Violation(design.project, rule, f"{record} synthetic",
                          f"synthetic is {synthetic!r}, where it is true on a {what} made only to prove the check "
                          "and false or absent otherwise; write true or false")]
    if synthetic is True and not not_for_manufacture:
        return [Violation(design.project, rule, f"{record} synthetic",
                          f"the {what} is marked synthetic, made only to prove the check, and the design is not "
                          "marked not for manufacture (NOT_FOR_MANUFACTURE=true), so a proof record cannot let it pass")]
    return []


def read_specification(yaml, root: str, repository: Repository, design: Design, not_for_manufacture: bool
                       ) -> Tuple[Optional[Dict[str, Dict[str, str]]], List[Violation]]:
    """The specification record's positions by reference, each its stated keys, or what stops it being usable."""
    what = "parts specification record"
    data, record, problems = load_yaml_record(yaml, root, repository, design, PARTS_RECORD_NAME, "parts_record", what)
    if data is None:
        return None, problems

    def bad(location: str, message: str) -> None:
        problems.append(Violation(design.project, "parts_record", f"{record} {location}".strip(), message))

    problems += synthetic_problem(design, "parts_record", record, data, what, not_for_manufacture)
    positions = data.get("positions")
    stated: Dict[str, Dict[str, str]] = {}
    if not isinstance(positions, list):
        bad("positions", f"the {what} lacks positions, the list holding one entry for each position the design places")
    elif not positions:
        bad("positions", f"the {what} lists no positions, so it would hold any design to nothing; list every "
                         "position the design places")
    else:
        for index, entry in enumerate(positions):
            where = f"positions[{index}]"
            if not isinstance(entry, dict):
                bad(where, f"{where} is not a mapping of the keys {', '.join(POSITION_KEYS)}")
                continue
            for key in sorted(set(map(str, entry)) - set(POSITION_KEYS)):
                bad(f"{where}.{key}", f"{where} holds the key '{key}', which is not one a position has: its keys are "
                                      f"{', '.join(POSITION_KEYS)}; correct the key's spelling, or remove it")
            for key in POSITION_KEYS:
                if key in entry and (not isinstance(entry[key], str) or not entry[key].strip()):
                    bad(f"{where}.{key}", f"{where}.{key} is {entry[key]!r}, where it is a non-empty string; quote a "
                                          "value that YAML would read as a number")
            for key in ("reference", "lcsc"):
                if key not in entry:
                    bad(f"{where}.{key}", f"{where} lacks {key}, which every position states")
            reference = entry.get("reference")
            if isinstance(reference, str) and reference.strip():
                if reference in stated:
                    bad(f"{where}.reference", f"the position {reference} is listed more than once")
                stated[reference] = {key: entry[key] for key in POSITION_KEYS[1:]
                                     if isinstance(entry.get(key), str) and entry[key].strip()}
    return (None if problems else stated), problems


def read_extract(yaml, root: str, repository: Repository, design: Design, today: datetime.date,
                 not_for_manufacture: bool) -> Tuple[Optional[Dict[str, object]], List[Violation]]:
    """The catalogue extract's entries by catalogue number, or what stops it being usable.

    An extract that states itself too old or dated later than today is still read, and the violation says so.
    """
    what = "catalogue extract"
    data, record, problems = load_yaml_record(yaml, root, repository, design, CATALOGUE_NAME, "parts_record", what)
    if data is None:
        return None, problems
    usable = True

    def bad(location: str, message: str, rule: str = "parts_record") -> None:
        nonlocal usable
        if rule == "parts_record":
            usable = False
        problems.append(Violation(design.project, rule, f"{record} {location}", message))

    unsynthetic = synthetic_problem(design, "parts_record", record, data, what, not_for_manufacture)
    if unsynthetic:
        usable = False
        problems += unsynthetic
    for key in EXTRACT_KEYS:
        if key not in data:
            bad(key, f"the {what} lacks {key}")
    read_on = None
    if "read_on" in data:
        read_on = iso_date(data["read_on"])
        if read_on is None:
            bad("read_on", f"read_on {data['read_on']!s} is not a valid calendar date written as YYYY-MM-DD")
        elif read_on > today:
            bad("read_on", f"the extract is dated {read_on.isoformat()}, later than today ({today.isoformat()}), "
                           "so its date cannot be trusted", "parts_catalogue")
    limit = data.get("max_age_days")
    if "max_age_days" in data and (isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0):
        bad("max_age_days", f"max_age_days is {limit!r}, where it is a whole number of days above zero")
    elif read_on is not None and isinstance(limit, int) and read_on <= today and (today - read_on).days > limit:
        bad("read_on", f"the extract was read on {read_on.isoformat()}, {(today - read_on).days} days before today "
                       f"({today.isoformat()}), past the {limit} days it allows itself; read the catalogue again and "
                       "date the extract", "parts_catalogue")
    entries = data.get("entries")
    found: Dict[str, object] = {}
    if "entries" in data:
        if not isinstance(entries, list):
            bad("entries", f"entries is not a list of catalogue entries")
        elif not entries:
            bad("entries", f"the {what} lists no entries, so it would show no part in stock")
        else:
            for index, entry in enumerate(entries):
                where = f"entries[{index}]"
                if not isinstance(entry, dict):
                    bad(where, f"{where} is not a mapping of the keys {', '.join(ENTRY_KEYS)}")
                    continue
                for key in sorted(set(map(str, entry)) - set(ENTRY_KEYS) - set(OPTIONAL_ENTRY_KEYS)):
                    bad(f"{where}.{key}", f"{where} holds the key '{key}', which is not one an entry has: its keys "
                                          f"are {', '.join(ENTRY_KEYS + OPTIONAL_ENTRY_KEYS)}")
                if "lifecycle" in entry:
                    reading = Reading(design, "parts_record", record, what)
                    life = f"{where}.lifecycle"
                    if reading.mapping(life, entry["lifecycle"], LIFECYCLE_KEYS, LIFECYCLE_KEYS, "a lifecycle"):
                        for key in ("status", "source"):
                            if key in entry["lifecycle"]:
                                reading.text(f"{life}.{key}", entry["lifecycle"][key])
                        if "read_on" in entry["lifecycle"]:
                            reading.date(f"{life}.read_on", entry["lifecycle"]["read_on"])
                    if reading.found:
                        usable = False
                        problems += reading.found
                for key in ENTRY_KEYS:
                    if key not in entry:
                        bad(f"{where}.{key}", f"{where} lacks {key}")
                number = entry.get("lcsc")
                if "lcsc" in entry and (not isinstance(number, str) or not number.strip()):
                    bad(f"{where}.lcsc", f"{where}.lcsc is {number!r}, where it is a non-empty string")
                    number = None
                klass = entry.get("library_class")
                if "library_class" in entry and (not isinstance(klass, str) or not klass.strip()):
                    bad(f"{where}.library_class", f"{where}.library_class is {klass!r}, where it is a non-empty string")
                price = entry.get("unit_price")
                if "unit_price" in entry and (isinstance(price, bool) or not isinstance(price, (int, float))
                                              or not math.isfinite(price) or price < 0):
                    bad(f"{where}.unit_price", f"{where}.unit_price is {price!r}, where it is a number of at least zero")
                stock = entry.get("stock")
                if "stock" in entry and (isinstance(stock, bool) or not isinstance(stock, int) or stock < 0):
                    bad(f"{where}.stock", f"{where}.stock is {stock!r}, which is not a whole number of zero or more, so the "
                                          "extract is malformed; write the stock as a whole number, and 0 for a part out of stock",
                        "parts_catalogue")
                    stock = None
                if isinstance(number, str):
                    key = number.strip()
                    if key in found:
                        bad(f"{where}.lcsc", f"{where}.lcsc is {key}, which another entry also carries, so the extract "
                                             "is malformed; keep one entry for each catalogue number", "parts_catalogue")
                    found[key] = stock if "stock" in entry else None
    return (found if usable else None), problems


def read_optional(yaml, root: str, repository: Repository, design: Design, name: str, rule: str, what: str,
                  keys: Sequence[str], not_for_manufacture: bool) -> Tuple[Optional[dict], Optional[Reading]]:
    """The record `name` the design's folders hold, read in its top-level form; nothing at all where they hold none.

    The record is a mapping with `keys` and no others, its violations in the Reading returned. A design whose
    folders hold no such record is not failed for it.
    """
    if find_record(root, design.directory, repository.tracked, name) is None:
        return None, None
    data, record, problems = load_yaml_record(yaml, root, repository, design, name, rule, what)
    reading = Reading(design, rule, record or name, what)
    reading.found += problems
    if data is None:
        return None, reading
    reading.found += synthetic_problem(design, rule, record, data, what, not_for_manufacture)
    reading.mapping("", data, keys, [key for key in keys if key != "synthetic"])
    return data, reading


def read_derating(yaml, root: str, repository: Repository, design: Design, not_for_manufacture: bool) -> List[Violation]:
    """The derating policy record's form where the design's folders hold one."""
    return load_derating(yaml, root, repository, design, not_for_manufacture)[1]


def load_derating(yaml, root: str, repository: Repository, design: Design, not_for_manufacture: bool
                  ) -> Tuple[Optional[dict], List[Violation]]:
    """The derating policy record's mapping and the violations of its form; no mapping where the design's
    folders hold none or the record is not in its form."""
    data, reading = read_optional(yaml, root, repository, design, DERATING_NAME, "derating_record",
                                  "derating policy record", DERATING_KEYS, not_for_manufacture)
    if data is None:
        return None, (reading.found if reading else [])
    if "source" in data:
        reading.text("source", data["source"])
    if "classes" in data and reading.listed("classes", data["classes"], "part classes"):
        for index, entry in enumerate(data["classes"]):
            where = f"classes[{index}]"
            if not reading.mapping(where, entry, CLASS_KEYS, CLASS_KEYS, "a part class"):
                continue
            if "class" in entry:
                reading.text(f"{where}.class", entry["class"])
            for quantity in CLASS_KEYS[1:]:
                if quantity not in entry:
                    continue
                share = entry[quantity]
                at = f"{where}.{quantity}"
                if not reading.mapping(at, share, SHARE_KEYS, SHARE_KEYS, "a share"):
                    continue
                if "share" in share:
                    value = share["share"]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
                        reading.bad(f"{at}.share", f"{at}.share is {value!r}, where it is a number above zero and at most "
                                                   "one, the fraction of the rating a part may use")
                if "source" in share:
                    reading.text(f"{at}.source", share["source"])
        reading.distinct("classes", [str(c["class"]).strip() for c in data["classes"]
                                     if isinstance(c, dict) and isinstance(c.get("class"), str)], "the class")
    return (None if reading.found else data), reading.found


def read_pin_limits(yaml, root: str, repository: Repository, design: Design, not_for_manufacture: bool) -> List[Violation]:
    """The pin-limit record's form where the design's folders hold one."""
    return load_pin_limits(yaml, root, repository, design, not_for_manufacture)[1]


def load_pin_limits(yaml, root: str, repository: Repository, design: Design, not_for_manufacture: bool
                    ) -> Tuple[Optional[dict], List[Violation]]:
    """The pin-limit record's mapping and the violations of its form; no mapping where the design's folders
    hold none or the record is not in its form."""
    data, reading = read_optional(yaml, root, repository, design, PIN_LIMITS_NAME, "pin_limits_record",
                                  "pin-limit record", PIN_LIMITS_KEYS, not_for_manufacture)
    if data is None:
        return None, (reading.found if reading else [])
    domains = set()
    if "domains" in data and reading.listed("domains", data["domains"], "power domains"):
        for index, entry in enumerate(data["domains"]):
            where = f"domains[{index}]"
            if not reading.mapping(where, entry, DOMAIN_KEYS, DOMAIN_KEYS, "a power domain"):
                continue
            if "name" in entry and reading.text(f"{where}.name", entry["name"]):
                domains.add(entry["name"])
            if "rail" in entry:
                reading.text(f"{where}.rail", entry["rail"])
            if "highest_voltage_v" in entry:
                reading.number(f"{where}.highest_voltage_v", entry["highest_voltage_v"])
        reading.distinct("domains", [d["name"] for d in data["domains"]
                                     if isinstance(d, dict) and isinstance(d.get("name"), str)], "the domain")
        reading.distinct("domains", [net_key(d["rail"].strip()) for d in data["domains"]
                                     if isinstance(d, dict) and isinstance(d.get("rail"), str)], "the rail")
    if "parts" in data and reading.listed("parts", data["parts"], "parts"):
        for index, entry in enumerate(data["parts"]):
            where = f"parts[{index}]"
            if not reading.mapping(where, entry, LIMIT_PART_KEYS, LIMIT_PART_KEYS, "a part"):
                continue
            if "lcsc" in entry:
                reading.text(f"{where}.lcsc", entry["lcsc"])
            source = entry.get("source")
            if "source" in entry and reading.mapping(f"{where}.source", source, LIMIT_SOURCE_KEYS, LIMIT_SOURCE_KEYS,
                                                     "a part's source"):
                for key in ("document", "revision", "section"):
                    if key in source:
                        reading.text(f"{where}.source.{key}", source[key])
                if "read_on" in source:
                    reading.date(f"{where}.source.read_on", source["read_on"])
            if "pins" in entry and reading.listed(f"{where}.pins", entry["pins"], "pins"):
                for position, pin in enumerate(entry["pins"]):
                    at = f"{where}.pins[{position}]"
                    if not reading.mapping(at, pin, LIMIT_PIN_KEYS, LIMIT_PIN_KEYS, "a pin"):
                        continue
                    if "pin" in pin and (isinstance(pin["pin"], bool) or not isinstance(pin["pin"], (str, int))
                                         or (isinstance(pin["pin"], str) and not pin["pin"].strip())):
                        reading.bad(f"{at}.pin", f"{at}.pin is {pin['pin']!r}, where it is the pin's name or number")
                    if "domain" in pin and reading.text(f"{at}.domain", pin["domain"]) and pin["domain"] not in domains:
                        reading.bad(f"{at}.domain", f"{at}.domain is '{pin['domain']}', which domains does not list; "
                                                    "name a power domain the record lists, or list it")
                    high, low = pin.get("absolute_max_v"), pin.get("absolute_min_v")
                    ok_high = "absolute_max_v" not in pin or reading.number(f"{at}.absolute_max_v", high)
                    ok_low = "absolute_min_v" not in pin or reading.number(f"{at}.absolute_min_v", low)
                    if ok_high and ok_low and "absolute_max_v" in pin and "absolute_min_v" in pin and low > high:
                        reading.bad(f"{at}.absolute_min_v", f"{at}.absolute_min_v is {low!r}, above absolute_max_v {high!r}; "
                                                            "a pin's lowest allowed voltage cannot exceed its highest")
                    if "tolerates_driven_unpowered" in pin:
                        reading.boolean(f"{at}.tolerates_driven_unpowered", pin["tolerates_driven_unpowered"])
        reading.distinct("parts", [p["lcsc"].strip() for p in data["parts"]
                                   if isinstance(p, dict) and isinstance(p.get("lcsc"), str)], "the catalogue number")
    return (None if reading.found else data), reading.found


def placed_positions(root: str, design: Design, repository: Repository
                     ) -> Tuple[Dict[str, Dict[str, Optional[str]]], List[str], List[Tuple[str, str, str, str]]]:
    """The positions the design places, by reference, each its Value, footprint library item name, LCSC and Rating,
    the references that more than one symbol carries, and the disagreements between units of one reference.

    Where a further unit of a reference carries a Value, footprint library item, LCSC or Rating that differs from the
    first unit's, the disagreement is listed as (reference, property, first unit's value, this unit's value), each
    property once for a reference; KiCad shares these across the units, so a difference is a hand edit.

    A position is a schematic symbol on the board, in the design's schematic or any sheet it reaches, counted once
    however many units it has; a symbol is a power symbol by its library symbol's power flag, never by how its
    reference is written, and a power symbol is no position. Two symbols carry one reference when they are the same
    unit of one library symbol or are different library symbols. Properties are None where the symbol has none. A
    sheet that cannot be read is skipped, since the design fails for it already.
    """
    placed: Dict[str, Dict[str, Optional[str]]] = {}
    seen: Dict[str, Tuple[str, set]] = {}
    repeated: List[str] = []
    disagreements: List[Tuple[str, str, str, str]] = []
    try:
        files = sorted(sheet_files(root, design.schematic, repository.tracked))
    except (OSError, sexpr.SexprError):
        return placed, repeated, disagreements
    for path in files:
        if not os.path.isfile(os.path.join(root, path)):
            continue
        try:
            with open(os.path.join(root, path), encoding="utf-8") as handle:
                tree = sexpr.parse_one(handle.read())
        except (OSError, sexpr.SexprError):
            continue
        library = sexpr.child(tree, "lib_symbols") or []
        power = {str(item[1]) for item in sexpr.children(library, "symbol") if len(item) > 1 and sexpr.child(item, "power")}
        for symbol in sexpr.children(tree, "symbol"):
            if sexpr.child(symbol, "lib_id") is None:
                continue
            identity = str((sexpr.child(symbol, "lib_name") or sexpr.child(symbol, "lib_id"))[1])
            on_board = sexpr.child(symbol, "on_board")
            if identity in power or (on_board is not None and len(on_board) > 1 and on_board[1] == "no"):
                continue
            fields = {str(prop[1]): str(prop[2]) for prop in sexpr.children(symbol, "property") if len(prop) > 2}
            references = []
            for project in sexpr.children(sexpr.child(symbol, "instances") or [], "project"):
                if len(project) > 1 and project[1] == design.name:
                    references += [str(ref[1]) for where in sexpr.children(project, "path")
                                   for ref in sexpr.children(where, "reference") if len(ref) > 1]
            if not references and fields.get("Reference"):
                references = [fields["Reference"]]
            unit_item = sexpr.child(symbol, "unit")
            unit = str(unit_item[1]) if unit_item is not None and len(unit_item) > 1 else "1"
            footprint = fields.get("Footprint", "")
            stated = {"value": fields.get("Value", ""),
                      "package": footprint.split(":", 1)[-1] if footprint else "",
                      "lcsc": fields.get("LCSC"), "rating": fields.get("Rating")}
            for reference in references:
                if reference in placed:
                    kind, units = seen[reference]
                    if (kind != identity or unit in units) and reference not in repeated:
                        repeated.append(reference)
                    elif kind == identity:
                        for key, name in (("value", "Value"), ("package", "Footprint"), ("lcsc", "LCSC"),
                                          ("rating", "Rating")):
                            if stated[key] != placed[reference][key] and not any(
                                    item[:2] == (reference, name) for item in disagreements):
                                disagreements.append((reference, name,
                                                      placed[reference][key] if placed[reference][key] is not None else ABSENT,
                                                      stated[key] if stated[key] is not None else ABSENT))
                    units.add(unit)
                    continue
                seen[reference] = (identity, {unit})
                placed[reference] = stated
    return placed, repeated, disagreements


def check_parts(yaml, root: str, design: Design, repository: Repository, today: datetime.date,
                not_for_manufacture: bool) -> List[Violation]:
    """The design's placed parts held to its specification record and to the catalogue extract. Reads files only."""
    stated, found = read_specification(yaml, root, repository, design, not_for_manufacture)
    catalogue, listed = read_extract(yaml, root, repository, design, today, not_for_manufacture)
    found += listed
    placed, repeated, disagreements = placed_positions(root, design, repository)
    for reference, name, first, other in sorted(disagreements):
        found.append(Violation(design.project, "parts_part", f"{reference} {name}",
                               f"the units of the position {reference} disagree on {name}: one unit has '{first}' and "
                               f"another has '{other}'; KiCad shares {name} across the units, so make them agree"))
    for reference in sorted(repeated):
        found.append(Violation(design.project, "parts_part", reference,
                               f"more than one symbol carries the reference {reference}, so the position cannot be "
                               "held to the record; give each symbol its own reference"))
    for reference in sorted(placed):
        part = placed[reference]
        if stated is not None:
            record = stated.get(reference)
            if record is None:
                found.append(Violation(design.project, "parts_part", reference,
                                       f"the design places the position {reference} and the parts specification record "
                                       "does not list it; list it in the record, or remove the part"))
            else:
                for key in ("value", "package", "rating", "lcsc"):
                    if key in record and record[key] != part[key]:
                        found.append(Violation(
                            design.project, "parts_part", f"{reference} {key}",
                            f"the position {reference} {key} differs: the record states '{record[key]}' and the design "
                            f"has '{part[key] if part[key] is not None else ABSENT}'"))
        number = part["lcsc"]
        if catalogue is not None and number is not None and number.strip():
            if number.strip() not in catalogue:
                found.append(Violation(design.project, "parts_catalogue", f"{reference} lcsc",
                                       f"the position {reference} has the catalogue number {number}, which the "
                                       "catalogue extract does not list"))
            elif catalogue[number.strip()] == 0:
                found.append(Violation(design.project, "parts_catalogue", f"{reference} lcsc",
                                       f"the position {reference} has the catalogue number {number}, which the "
                                       "catalogue extract shows with no stock"))
    return found


# --- The derated-voltage and pin-limit rules --------------------------------------

#: The slack, relative to the figure compared, that floating-point arithmetic on a peak may need.
VOLTAGE_SLACK = 1e-9
#: A figure written with unit V, VDC or VAC in any letter case, as a rating states it.
#: A number directly followed by a V unit, with an optional thousands separator or k or m prefix, in any letter case
#: and whatever follows the unit: a voltage as a rating writes it, whether or not the rule can read it.
VOLTAGE_SHAPED = re.compile(r"[0-9](?:[0-9,.]*[0-9])?\s*[km]?V", re.IGNORECASE)
RATING_FIGURE = re.compile(r"(?<![A-Za-z0-9.])([0-9]+(?:\.[0-9]+)?)\s*(VAC|VDC|V)(?![A-Za-z])", re.IGNORECASE)
#: A resistor value that is zero.
ZERO_OHMS = re.compile(r"0+(?:\.0+)?\s*(?:R|Ω|ohms?)?", re.IGNORECASE)
INTEGRATED_CIRCUIT = "integrated circuit"
SEMICONDUCTOR = "semiconductor"
JOINS_NETS = "joins nets"
PASSIVE = "passive or mechanical part"


LEADING_LETTERS = re.compile(r"[A-Za-z]*")


def part_kind(reference: str, value: Optional[str]) -> str:
    """A part's kind, read from the leading letters of its reference designator and, for a resistor, its value.

    The leading letters are matched whole and without regard to case: U is an integrated circuit, D, Q or
    LED a semiconductor, FB, L or F, or R with the value zero, a part that
    joins nets, and any other designator a passive or mechanical part. The
    part's class plays no part in it.
    """
    letters = LEADING_LETTERS.match(reference.strip()).group(0).upper()
    if letters == "U":
        return INTEGRATED_CIRCUIT
    if letters in ("D", "Q", "LED"):
        return SEMICONDUCTOR
    if letters in ("FB", "L", "F") or (letters == "R" and ZERO_OHMS.fullmatch((value or "").strip())):
        return JOINS_NETS
    return PASSIVE


def rating_peak(text: Optional[str]) -> Optional[float]:
    """The first figure with unit V, VDC or VAC a rating states, in volts, an AC figure at its peak; None where it states none."""
    found = RATING_FIGURE.search(text) if isinstance(text, str) else None
    if found is None or float(found.group(1)) <= 0:
        return None
    return float(found.group(1)) * (math.sqrt(2) if found.group(2).upper() == "VAC" else 1)


def voltage_shaped(text: Optional[str]) -> bool:
    """Whether a rating states a figure shaped like a voltage, readable by rating_peak or not."""
    return isinstance(text, str) and VOLTAGE_SHAPED.search(text) is not None


def net_key(name: str) -> str:
    """A net as a record names it: the name without the slash KiCad puts before a net of the top sheet."""
    return name[1:] if name.startswith("/") else name


def exceeds(figure: float, limit: float) -> bool:
    return figure > limit + VOLTAGE_SLACK * max(1.0, abs(limit))


class NetVoltages:
    """The highest and lowest voltage each net of a design can reach, worked out from the pin-limit record.

    A net takes its voltage from the power domain whose rail it is and from the
    domain of every listed pin on it, and shares it with every net joined to it,
    directly or in a chain, through a part that joins nets. A resistor or
    capacitor joins nothing. The highest is the largest highest_voltage_v of
    those domains, and the lowest the smallest of 0 V for a domain other than a
    mains domain and minus its highest_voltage_v for a mains domain, since mains
    alternates. A net no domain reaches has neither.
    """

    def __init__(self, nets: Dict[str, List[PinNode]], domains: Dict[str, Tuple[str, float]], mains_nets: Set[str],
                 joiners: Set[str], listed: Dict[str, Set[str]]):
        """`domains` maps a domain's name to its rail and highest voltage, `joiners` holds the references of the
        parts that join nets, and `listed` maps a net to the domains of the listed pins on it."""
        self.domains = domains
        self.names = [name for name in nets if not name.rsplit("/", 1)[-1].startswith(UNCONNECTED_NET)]
        mains_keys = {net_key(name) for name in mains_nets}
        rails = {net_key(rail): name for name, (rail, _) in domains.items()}
        self.mains = {name for name, (rail, _) in domains.items() if net_key(rail) in mains_keys}
        parent = {name: name for name in self.names}

        def find(name: str) -> str:
            while parent[name] != name:
                parent[name] = parent[parent[name]]
                name = parent[name]
            return name

        touched: Dict[str, List[str]] = {}
        for name in self.names:
            for pin in nets[name]:
                if pin.ref in joiners and name not in touched.setdefault(pin.ref, []):
                    touched[pin.ref].append(name)
        for reached in touched.values():
            for name in reached[1:]:
                parent[find(name)] = find(reached[0])

        self.known = set(self.names)
        self._root = {name: find(name) for name in self.names}
        self.sources: Dict[str, Set[str]] = {}
        for name in self.names:
            held = self.sources.setdefault(self._root[name], set())
            if net_key(name) in rails:
                held.add(rails[net_key(name)])
            held |= listed.get(name, set())

    def domains_of(self, net: str) -> Set[str]:
        return self.sources.get(self._root.get(net, ""), set())

    def highest(self, net: str) -> Optional[float]:
        held = self.domains_of(net)
        return max(self.domains[d][1] for d in held) if held else None

    def lowest(self, net: str) -> Optional[float]:
        held = self.domains_of(net)
        return min(-self.domains[d][1] if d in self.mains else 0.0 for d in held) if held else None

    def from_mains(self, net: str) -> bool:
        """Whether the net takes its highest voltage from a mains domain."""
        top = self.highest(net)
        return top is not None and any(d in self.mains and not exceeds(top, self.domains[d][1])
                                       for d in self.domains_of(net))


def working_voltage(volts: NetVoltages, nets: List[str]) -> float:
    """The largest, over every pair of the nets, of the difference between their highest voltages, where a pair both
    taking theirs from a mains domain counts as that domain's highest_voltage_v, since mains swings between them."""
    worst = 0.0
    for index, first in enumerate(nets):
        for second in nets[index + 1:]:
            if volts.from_mains(first) and volts.from_mains(second):
                mains = max(volts.domains[d][1] for d in volts.domains_of(first) & volts.mains)
                worst = max(worst, mains)
            else:
                worst = max(worst, abs(volts.highest(first) - volts.highest(second)))
    return worst


def voltage_rules(design: Design, yaml, root: str, repository: Repository, not_for_manufacture: bool, mains: Optional[str],
                  signed: Optional[Signed], nets: Dict[str, List[PinNode]], mains_nets: Set[str]) -> List[Violation]:
    """The derated-voltage rule and the pin-limit rule, which share one reading of each net's voltage.

    Both read the design's files and the records it is held to: the parts
    specification, the derating policy and the pin-limit record. A form the
    readers have already failed is not judged again.
    """
    found: List[Violation] = []
    schematic = design.schematic
    stated, _ = read_specification(yaml, root, repository, design, not_for_manufacture)
    placed, _, _ = placed_positions(root, design, repository)
    policy_path = find_record(root, design.directory, repository.tracked, DERATING_NAME)
    limits_path = find_record(root, design.directory, repository.tracked, PIN_LIMITS_NAME)
    policy, policy_form = load_derating(yaml, root, repository, design, not_for_manufacture)
    limits, limits_form = load_pin_limits(yaml, root, repository, design, not_for_manufacture)

    def fail(rule: str, location: str, message: str) -> None:
        found.append(Violation(design.project, rule, location, message))

    domains: Dict[str, Tuple[str, float]] = {}
    entries: Dict[str, dict] = {}
    if limits is not None:
        domains = {d["name"]: (d["rail"], d["highest_voltage_v"]) for d in limits["domains"]}
        entries = {str(p["lcsc"]).strip(): p for p in limits["parts"]}

    by_part: Dict[str, List[Tuple[str, PinNode]]] = {}
    for net, pins in nets.items():
        for pin in pins:
            by_part.setdefault(pin.ref, []).append((net, pin))

    def kind(ref: str) -> str:
        return part_kind(ref, (placed.get(ref) or {}).get("value"))

    def number(ref: str) -> str:
        return ((placed.get(ref) or {}).get("lcsc") or "").strip()

    listed: Dict[str, Set[str]] = {}
    listings: Dict[str, List[Tuple[str, PinNode, dict]]] = {}
    lacking: List[Tuple[str, str]] = []
    for ref in sorted(placed):
        entry = entries.get(number(ref))
        if entry is None:
            continue
        for pin in entry["pins"]:
            wanted = str(pin["pin"])
            matched = False
            for net, node in by_part.get(ref, []):
                if node.pin == wanted or wanted in node.names():
                    matched = True
                    listed.setdefault(net, set()).add(pin["domain"])
                    listings.setdefault(ref, []).append((net, node, pin))
            if not matched:
                lacking.append((ref, wanted))
    joiners = {ref for ref in by_part if kind(ref) == JOINS_NETS}
    volts = NetVoltages(nets, domains, mains_nets, joiners, listed)

    # The derated-voltage rule.
    if stated is not None:
        classes: Optional[Dict[str, float]] = None
        if policy_path is None:
            classes = {}
        elif policy is not None:
            classes = {c["class"].strip(): c["voltage"]["share"] for c in policy["classes"]}
        for ref in sorted(stated):
            where = f"{schematic} {ref}"
            record = stated[ref]
            named = record.get("class")
            if named is None:
                fail("derated_voltage", where, f"the position {ref} has no class in the parts specification record; "
                                               "name a class of the derating policy, or none for a part no class covers")
                continue
            if named == "none":
                stated_ratings = [(source, text) for source, text in (
                    ("the parts specification record", record.get("rating")),
                    ("the design's Rating field", (placed.get(ref) or {}).get("rating"))) if voltage_shaped(text)]
                for source, text in stated_ratings:
                    fail("derated_voltage", f"{where} rating",
                         f"the position {ref} names the class none and {source} gives {text!r}, a figure in a voltage unit; "
                         "none is for a part with no such rating, so name the class of the derating policy that covers it")
                continue
            if classes is None:
                continue
            if named not in classes:
                fail("derated_voltage", where, f"the position {ref} names the class '{named}', which "
                     + ("the derating policy does not list" if policy_path else "the design has no derating policy to list")
                     + "; name a class the policy lists, or none")
                continue
            peaks = []
            for source, text in (("the parts specification record", record.get("rating")),
                                 ("the design's Rating field", (placed.get(ref) or {}).get("rating"))):
                peak = rating_peak(text)
                if peak is None:
                    fail("derated_voltage", f"{where} rating",
                         f"the position {ref} is in the class '{named}' and {source} gives "
                         f"{'no rating' if text is None else repr(text)} with no figure in V, VDC or VAC; "
                         "write the voltage rating with its unit")
                else:
                    peaks.append(peak)
            if len(peaks) < 2 or limits_form:
                continue
            reached = []
            for net in dict.fromkeys(net for net, _ in by_part.get(ref, [])):
                if net in volts.known:
                    reached.append(net)
            unknown = [net for net in reached if volts.highest(net) is None]
            for net in unknown:
                fail("derated_voltage", f"{where} {net}",
                     f"the net {net} of {ref} has a voltage that cannot be worked out, reached only through resistors or "
                     "capacitors with no rail or listed pin; declare it as the rail of a power domain in the pin-limit record")
            if unknown:
                continue
            working = working_voltage(volts, reached)
            limit = classes[named] * peaks[0]
            if exceeds(working, limit):
                fail("derated_voltage", where,
                     f"the position {ref} sees a working voltage of {working:g} V across {', '.join(reached)}, above "
                     f"{limit:g} V, the class '{named}' voltage share {classes[named]:g} times its rating peak {peaks[0]:g} V")

    # The mains domain.
    if mains == "present" and not limits_form:
        peak = basis_voltage(signed.basis.get("working_voltage")) if signed is not None else None
        peak = peak * math.sqrt(2) if peak is not None else None
        if limits is None:
            fail("derated_voltage", os.path.join(design.directory, PIN_LIMITS_NAME),
                 "the design declares mains present and holds no pin-limit record, so there is no mains domain; "
                 "add the record with a domain whose rail is a net of the Mains class")
        elif not volts.mains:
            fail("derated_voltage", f"{limits_path} domains",
                 "the design declares mains present and no domain of the pin-limit record has a rail on a net of "
                 "the Mains class; add the mains domain, with its rail a net of that class")
        elif peak is not None:
            for name in sorted(volts.mains):
                if exceeds(peak, domains[name][1]):
                    fail("derated_voltage", f"{limits_path} domains {name}",
                         f"the mains domain {name} states highest_voltage_v {domains[name][1]:g}, below {peak:g} V, "
                         "the peak of the separation basis working_voltage; state at least the peak")

    # A domain's rail must be a net of the design.
    if limits is not None:
        present = {net_key(name) for name in nets}
        for name, (rail, _) in domains.items():
            if net_key(rail) not in present:
                fail("pin_limit", f"{limits_path} domains {name}",
                     f"the domain {name} names the rail {rail}, which is no net of the design; name a net of the design, "
                     "or remove the domain")

    # The pin-limit rule.
    for ref in sorted(placed):
        if kind(ref) not in (INTEGRATED_CIRCUIT, SEMICONDUCTOR) or limits_form:
            continue
        where = f"{schematic} {ref}"
        if limits is None:
            fail("pin_limit", where, f"the design places the {kind(ref)} {ref} and holds no pin-limit record to "
                                     "state its pins' limits; add the record")
        elif not number(ref):
            fail("pin_limit", where, f"the {kind(ref)} {ref} has no LCSC number, so the pin-limit record cannot be "
                                     "read for it; give the part its number")
        elif number(ref) not in entries:
            fail("pin_limit", where, f"the pin-limit record omits the {kind(ref)} {ref}, catalogue number {number(ref)}; "
                                     "add its entry")
    rails = {net_key(rail) for rail, _ in domains.values()}
    for ref in sorted(placed):
        entry = entries.get(number(ref))
        if entry is None or kind(ref) not in (INTEGRATED_CIRCUIT, SEMICONDUCTOR) or limits_form:
            continue
        for net, node in by_part.get(ref, []):
            if len(nets[net]) < 2 and net_key(net) not in rails:
                continue
            if not any(node.pin == str(listed["pin"]) or str(listed["pin"]) in node.names() for listed in entry["pins"]):
                fail("pin_limit", f"{schematic} {node.describe()}",
                     f"the pin-limit record entry for the {kind(ref)} {ref}, catalogue number {number(ref)}, omits {node.describe()}, "
                     f"which is connected on net {net}; add an entry for it, by its number or its name")
    for ref, wanted in lacking:
        fail("pin_limit", f"{schematic} {ref}",
             f"the pin-limit record lists pin {wanted} of catalogue number {number(ref)}, which the part {ref} does not have; "
             "name a pin the part's symbol has, by its number or its name")
    for ref in sorted(listings):
        for net, node, pin in listings[ref]:
            where = f"{schematic} {node.describe()}"
            own = pin["domain"]
            top, bottom = volts.highest(net), volts.lowest(net)
            if top is not None and exceeds(top, pin["absolute_max_v"]):
                fail("pin_limit", where, f"{node.describe()} is on net {net}, which can reach {top:g} V, above the pin's "
                                         f"absolute_max_v {pin['absolute_max_v']:g}")
            if bottom is not None and exceeds(pin["absolute_min_v"], bottom):
                fail("pin_limit", where, f"{node.describe()} is on net {net}, which can fall to {bottom:g} V, below the "
                                         f"pin's absolute_min_v {pin['absolute_min_v']:g}")
            others = sorted(d for d in volts.domains_of(net) if d != own and domains[d][1] > 0)
            if others and pin["tolerates_driven_unpowered"] is False:
                fail("pin_limit", where, f"{node.describe()} of domain {own} is on net {net}, driven from the domain "
                                         f"{', '.join(others)}, and the record states it does not tolerate being driven "
                                         "while its own domain is unpowered")
    return found


# --- The board rules record, the sensing clearance and the ground returns ---------

BOARD_RULES_NAME = "board-rules.yaml"
#: The keys of the board rules record, of the sensing mapping, of the ground-return mapping and of each signal class in it.
BOARD_RULES_KEYS = ("sensing", "ground_returns", "synthetic")
SENSING_KEYS = ("classes", "noisy_classes", "clearance_mm", "source")
GROUND_RETURN_KEYS = ("ground_classes", "non_signal_classes", "signal_classes")
SIGNAL_CLASS_KEYS = ("class", "signal_pins_per_return", "source")
#: What a mapping of the board rules record states when the design has nothing of its kind.
NOTHING = "none"
#: The rule each sensing and noisy class pair is held to is named with this and the two classes.
SENSING_RULE = f"{RESERVED}: sensing clearance"
#: The class a net falls in when no other class holds it.
DEFAULT_CLASS = "Default"


def read_board_rules(yaml, root: str, repository: Repository, design: Design, not_for_manufacture: bool) -> List[Violation]:
    """The board rules record's form, which every design needs."""
    return load_board_rules(yaml, root, repository, design, not_for_manufacture)[1]


def load_board_rules(yaml, root: str, repository: Repository, design: Design, not_for_manufacture: bool
                     ) -> Tuple[Optional[dict], List[Violation]]:
    """The board rules record's mapping and the violations of its form; no mapping where the record is missing or not in its form.

    The sensing-clearance and ground-return rules compare a figure the record
    holds, so a design whose folders hold none fails, and so does one whose
    record is silent on either mapping. Each mapping may instead be the word
    none, for a design with no sensing class or no connector signals to hold.
    """
    if find_record(root, design.directory, repository.tracked, BOARD_RULES_NAME) is None:
        return None, [Violation(design.project, "board_rules_record", os.path.join(design.directory, BOARD_RULES_NAME),
                                f"there is no {BOARD_RULES_NAME} in the design's folder or any folder above it, so the "
                                "sensing-clearance and ground-return rules have nothing to hold the design to; add the "
                                f"record, stating each of sensing and ground_returns, or {NOTHING} where the design has none")]
    data, reading = read_optional(yaml, root, repository, design, BOARD_RULES_NAME, "board_rules_record",
                                  "board rules record", BOARD_RULES_KEYS, not_for_manufacture)
    if data is None:
        return None, reading.found
    for key, read in (("sensing", read_sensing), ("ground_returns", read_ground_returns)):
        if key not in data or data[key] == NOTHING:
            continue
        if not isinstance(data[key], dict):
            reading.bad(key, f"{key} is {data[key]!r}, where it is a mapping or the word {NOTHING} for a design with none")
        else:
            read(reading, data[key])
    return (None if reading.found else data), reading.found


def class_names(reading: Reading, path: str, names, empty: bool = False) -> List[str]:
    """The net class names a list holds, each a non-empty string and each once."""
    if not reading.listed(path, names, "net classes", empty):
        return []
    for index, name in enumerate(names):
        reading.text(f"{path}[{index}]", name)
    held = [name for name in names if isinstance(name, str) and name.strip()]
    reading.distinct(path, held, "the class")
    return held


def read_sensing(reading: Reading, sensing: dict) -> None:
    if not reading.mapping("sensing", sensing, SENSING_KEYS, SENSING_KEYS, "a sensing declaration"):
        return
    held = {key: class_names(reading, f"sensing.{key}", sensing[key]) for key in SENSING_KEYS[:2] if key in sensing}
    if len(held) == 2:
        for name in sorted(set(held["classes"]) & set(held["noisy_classes"])):
            reading.bad("sensing", f"sensing lists the class '{name}' as both a sensing and a noisy class, so it would be held "
                                   "apart from itself; list it in one")
    if "clearance_mm" in sensing:
        reading.positive("sensing.clearance_mm", sensing["clearance_mm"], " of millimetres")
    if "source" in sensing:
        reading.text("sensing.source", sensing["source"])


def read_ground_returns(reading: Reading, returns: dict) -> None:
    if not reading.mapping("ground_returns", returns, GROUND_RETURN_KEYS, GROUND_RETURN_KEYS, "a ground-return declaration"):
        return
    names: List[str] = []
    for key, empty in (("ground_classes", False), ("non_signal_classes", True)):
        if key in returns:
            names += class_names(reading, f"ground_returns.{key}", returns[key], empty)
    if "signal_classes" in returns and reading.listed("ground_returns.signal_classes", returns["signal_classes"], "signal net classes"):
        for index, entry in enumerate(returns["signal_classes"]):
            where = f"ground_returns.signal_classes[{index}]"
            if not reading.mapping(where, entry, SIGNAL_CLASS_KEYS, SIGNAL_CLASS_KEYS, "a signal class"):
                continue
            if "class" in entry and reading.text(f"{where}.class", entry["class"]):
                names.append(entry["class"])
            if "signal_pins_per_return" in entry:
                figure = entry["signal_pins_per_return"]
                if isinstance(figure, bool) or not isinstance(figure, int) or figure < 1:
                    reading.bad(f"{where}.signal_pins_per_return",
                                f"{where}.signal_pins_per_return is {figure!r}, where it is a positive whole number, the most "
                                "signal pins one ground-return pin may serve")
            if "source" in entry:
                reading.text(f"{where}.source", entry["source"])
    reading.distinct("ground_returns", names, "the class")


def sensing_rules(sensing: dict, signed: Optional[Tuple[float, float]]) -> Tuple[str, str, Dict[str, Tuple[str, str, float]]]:
    """The rules holding each sensing and noisy class pair to the declared clearance, in KiCad's own form.

    Returns the rules that go ahead of the signed rule, those that go after it,
    and each rule's name with its two classes and figure. A pair without the
    Mains class goes ahead, at the declared clearance. The signed rule's
    condition already matches a pair with the Mains class and, being last, would
    decide its clearance, so that pair's rule goes after it, holds the clearance
    constraint alone and is set at the larger of the declared and signed
    clearances: it can only tighten, and the signed creepage stays with the
    signed rule.
    """
    ahead, after, named = "", "", {}
    for sensed in sensing["classes"]:
        for noisy in sensing["noisy_classes"]:
            name = f"{SENSING_RULE}: {sensed} against {noisy}"
            mains = signed is not None and "Mains" in (sensed, noisy)
            figure = max(sensing["clearance_mm"], signed[0]) if mains else sensing["clearance_mm"]
            text = (f'(rule "{name}"\n\t(condition "A.hasNetclass(\'{sensed}\') && B.hasNetclass(\'{noisy}\')")\n'
                    f'\t(constraint clearance (min {figure:g}mm)))\n')
            named[name] = (sensed, noisy, figure)
            if mains:
                after += text
            else:
                ahead += text
    return ahead, after, named


def sensing_classes(design: Design, record: str, sensing: dict, project_classes: Set[str], members: Dict[str, Set[str]]
                    ) -> List[Violation]:
    """Every class the sensing declaration names that the rules cannot be enforced against.

    A class the project does not define, or one that holds no net on the layout,
    would leave its pairs' rules applying to nothing, so a design cannot pass by
    how a class is spelt; a name KiCad's rule syntax cannot carry is refused too.
    """
    found = []
    for key in ("classes", "noisy_classes"):
        for name in sensing[key]:
            where = f"{record} sensing.{key}"
            if UNWRITABLE & set(name):
                found.append(Violation(design.project, "sensing_clearance", where,
                                       f"the class '{name}' holds a quote or backslash, which a rule's condition cannot carry, so "
                                       "the clearance cannot be enforced against it; rename the class"))
            elif name not in project_classes:
                found.append(Violation(design.project, "sensing_clearance", where,
                                       f"the class '{name}' is no net class of the design's project file, so its rules would "
                                       "apply to nothing; name a class the project defines"))
            elif not members.get(name):
                found.append(Violation(design.project, "sensing_clearance", where,
                                       f"the class '{name}' holds no net on the layout, so its rules would apply to nothing; "
                                       "assign the nets to the class, or take it out of the declaration"))
    return found


def sensing_clearance(kicad_cli: str, design: Design, copy: str, layout: str, rules_copy: str, existing: str,
                      signed: Optional[Signed], nonce: str, net: Optional[str], record: str, sensing: dict,
                      project_classes: Set[str], members: Dict[str, Set[str]]) -> List[Violation]:
    """Every sensing item the layout puts closer to a noisy item than the record's declared clearance.

    A second KiCad run on the temporary copy holds the rules sensing_rules
    writes, ahead of the signed rule and after it as that function says, so a
    finding is reported under the sensing rule's own name; only those rules'
    findings are read. The design's own rules stay as it wrote them in the first
    run, so a pair the design holds more strictly is still held to its own figure
    there.
    """
    problems = sensing_classes(design, record, sensing, project_classes, members)
    if problems:
        return problems
    ahead, after, named = sensing_rules(sensing, signed)
    with open(rules_copy, "w", encoding="utf-8") as handle:
        handle.write(existing + ahead + appended_rules(signed, nonce, net) + after)
    report, why = run_report([kicad_cli, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", layout], copy)

    def fail(message: str) -> List[Violation]:
        return [Violation(design.project, "sensing_clearance", design.layout, message)]

    if report is None:
        return fail(f"the clearance of the sensing classes from the noisy classes cannot be checked: {why}")
    if cut_short(report):
        return fail(f"KiCad's report was cut short at {REPORT_LIMIT} assertion failures, so a sensing item inside the "
                    "clearance may have been dropped from it; correct the design's own assertion failures first")
    if not fired(report, marker_rule(nonce)):
        return fail("KiCad did not load the rules that hold the sensing classes to the declared clearance, so no sensing item was checked")
    clearances = [entry for entry in report.get("violations") or [] if entry.get("type") == "clearance"]
    if len(clearances) >= REPORT_LIMIT:
        return fail(f"KiCad's report holds {len(clearances)} clearance failures, as many as it reports of one kind, so a sensing "
                    "item inside the declared clearance may have been dropped from it; correct the design's own clearance failures first")
    found, seen = [], set()
    for entry in clearances:
        description = entry.get("description", "")
        rule = next((name for name in named if f"(rule '{name}'" in description), None)
        if rule is None:
            continue
        sensed, noisy, figure = named[rule]
        items = entry.get("items") or []
        pair = (rule, frozenset(item_text(item) for item in items))
        if pair in seen:
            continue
        seen.add(pair)
        gap = DISTANCE_REPORTED.search(description)
        involving = (f", the larger of the declared {sensing['clearance_mm']:g} mm and the signed clearance {signed[0]:g} mm "
                     "since the pair involves Mains") if signed is not None and "Mains" in (sensed, noisy) and figure != sensing["clearance_mm"] else ""
        found.append(Violation(
            design.project, "sensing_clearance", "; ".join(item_text(item) for item in items) or design.layout,
            f"an item of the sensing class {sensed} stands {gap.group(1) + ' mm' if gap else 'too close'} from an item of the noisy "
            f"class {noisy}, inside the {figure:g} mm that {record} declares{involving}; move the two apart, or revise "
            "sensing.clearance_mm with its source"))
    return found


def sensing_overrides(design: Design, layout: list, record: str, figure: float, nets: Set[str]) -> List[Violation]:
    """Local clearance overrides below the declared sensing clearance on a sensing or noisy class net.

    KiCad ranks a pad's or a footprint's local clearance override above every
    custom rule, so one below the figure on either item of a pair would win over
    the rules sensing_rules writes. A footprint has no net of its own and is read
    as on one of `nets` when any of its pads is. A pad on no net is not counted.
    """
    found = []
    why = (f"below the {figure:g} mm that {record} declares for sensing; KiCad ranks a pad or footprint clearance override above "
           f"every custom rule, so it would let a sensing item pass closer than the declared clearance. Remove it, or raise "
           f"it to at least {figure:g} mm")
    for footprint in walk(layout, "footprint"):
        reference = board_geometry.reference(footprint) or "?"
        reached = [pad for pad in sexpr.children(footprint, "pad") if net_of(pad) in nets]
        if not reached:
            continue
        for item in footprint:
            value = numeric_clearance(item)
            if value is not None and value < figure - 1e-9:
                found.append(Violation(design.project, "sensing_override", f"footprint {reference} at {at_text(footprint)}",
                                       f"footprint {reference} has a pad on a sensing or noisy class net and sets a local "
                                       f"clearance override of {value:g} mm, {why}"))
        for pad in reached:
            number = str(pad[1]) if len(pad) > 1 else "?"
            for node in walk(pad, "clearance"):
                value = numeric_clearance(node)
                if value is not None and value < figure - 1e-9:
                    found.append(Violation(design.project, "sensing_override",
                                           f"pad {number} [{net_of(pad)}] of {reference} (footprint at {at_text(footprint)})",
                                           f"pad {number} of {reference} is on the sensing or noisy class net {net_of(pad)} and "
                                           f"sets a local clearance override of {value:g} mm, {why}"))
    return found


def ground_returns(design: Design, tree: list, record: str, returns: dict, members: Dict[str, Set[str]]) -> List[Violation]:
    """Every connector short of ground-return pins for its signal pins, and every connector pin on a class the record leaves undeclared.

    A connector is a part whose reference designator begins with J. Its pins are
    the numbered pads of its footprint that sit on a net, counted once however
    many pads carry the number; a pad on no net, or on a net nothing else joins
    (named unconnected-(...)), is no pin. A pin's classes are those of the
    layout's net classes the net is in, or Default where it is in none. A pin on
    a ground class is a ground-return pin and one on a signal class a signal
    pin; a pin on a non-signal class is counted for neither. A connector with
    signal pins fails when they exceed the smallest signal_pins_per_return of the
    signal classes it carries times its ground-return pins, compared on whole
    pins. A pin whose classes the record declares as none of the three, or as more
    than one of them, fails, since which it counts as cannot be told.
    """
    ground = set(returns["ground_classes"])
    non_signal = set(returns["non_signal_classes"])
    signal = {entry["class"]: entry["signal_pins_per_return"] for entry in returns["signal_classes"]}
    connectors: Dict[str, Dict[Tuple[str, str], str]] = {}
    for index, pad in enumerate(board_geometry.pads(tree)):
        if not pad.reference.upper().startswith("J") or not pad.net or pad.net.rsplit("/", 1)[-1].startswith(UNCONNECTED_NET):
            continue
        connectors.setdefault(pad.reference, {}).setdefault((pad.number or f"(pad {index})", pad.net), pad.net)
    found = []
    for reference in sorted(connectors):
        returning, signalling = [], []
        for number, net in sorted(connectors[reference]):
            held = {name for name, inside in members.items() if net in inside} or {DEFAULT_CLASS}
            kinds = {kind for kind, declared in (("ground", ground), ("non-signal", non_signal), ("signal", signal)) if held & set(declared)}
            where = f"{design.layout} connector {reference} pin {number} [{net}]"
            if not kinds:
                found.append(Violation(design.project, "ground_return", where,
                                       f"pin {number} of connector {reference} is on net {net}, in the net class {', '.join(sorted(held))}, "
                                       f"which {record} ground_returns declares as none of ground, signal or non-signal; list "
                                       "the class under ground_classes, non_signal_classes or signal_classes"))
            elif len(kinds) > 1:
                found.append(Violation(design.project, "ground_return", where,
                                       f"pin {number} of connector {reference} is on net {net}, in the net classes {', '.join(sorted(held))}, "
                                       f"which {record} ground_returns declares as {' and '.join(sorted(kinds))}, so whether it is "
                                       "a ground return or a signal cannot be told; put the net in one class"))
            elif "ground" in kinds:
                returning.append((number, net))
            elif "signal" in kinds:
                signalling.append((number, net, min(signal[name] for name in held & set(signal))))
        if not signalling:
            continue
        most = min(figure for _, _, figure in signalling)
        if len(signalling) > most * len(returning):
            needed = -(-len(signalling) // most)
            found.append(Violation(
                design.project, "ground_return", f"{design.layout} connector {reference}",
                f"connector {reference} has {len(signalling)} signal pins ({', '.join(f'{n} [{net}]' for n, net, _ in signalling)}) "
                f"and {len(returning)} ground-return pins ({', '.join(f'{n} [{net}]' for n, net in returning) or 'none'}); "
                f"{record} ground_returns lets one return serve {most} signal pins at most, so it needs at least {needed}; "
                "add ground-return pins to the connector, or revise signal_pins_per_return with its source"))
    return found


# --- The design's own rules ----------------------------------------------------


def declared_mm(constraint: list) -> Optional[float]:
    """The minimum of a (constraint <kind> (min <number>mm)), or None for any other form."""
    if len(constraint) != 3 or sexpr.head(constraint[2]) != "min" or len(constraint[2]) != 2:
        return None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)mm", str(constraint[2][1]))
    return float(match.group(1)) if match and not isinstance(constraint[2][1], sexpr.Quoted) else None


def one_line(node) -> str:
    """A form as KiCad's files write it, on one line, for quoting in a report."""
    return re.sub(r"\s*\)", ")", " ".join(sexpr.dump(node).split()))


def rule_name(rule: list) -> str:
    return str(rule[1]) if len(rule) > 1 and not isinstance(rule[1], list) else "(unnamed)"


class Rule(list):
    """One custom rule as parsed, with the line of the rules file it starts on (0 when not read from a file)."""

    line = 0


def rule_forms(text: str) -> List[Rule]:
    """Every (rule ...) form of a custom rules file's text, in order, each with its line."""
    spans: List[Tuple[int, int, int]] = []
    forms = sexpr.parse(text, comments=True, spans=spans)
    rules = []
    for form, (_, _, line) in zip(forms, spans):
        if sexpr.head(form) == "rule":
            rule = Rule(form)
            rule.line = line
            rules.append(rule)
    return rules


def rule_at(rule: list) -> str:
    """A rule as the report names it: its name, and its line when it was read from a file."""
    line = getattr(rule, "line", 0)
    return f"rule '{rule_name(rule)}'" + (f" at line {line}" if line else "")


#: The clauses KiCad takes once in a rule yet loads a rule holding twice, keeping
#: only one of them; a rule holding any other clause twice KiCad declines to
#: load at all, which the check finds through KiCad itself.
ONCE_ONLY_CLAUSES = ("condition", "severity")


def read_rules(root: str, design: Design, repository: Repository) -> Tuple[Optional[List[list]], List[Violation]]:
    """The design's custom rules, and any of them that hides what it finds or takes a name reserved for the check."""
    path = os.path.join(root, design.rules)
    untracked = repository.untracked(design.rules)
    if untracked is not None:
        return [], [Violation(design.project, "custom_rules", design.rules,
                              f"the custom rules file {untracked}, so the check, which reads a design only as the "
                              "repository holds it, would check the design without the rules KiCad applies to it "
                              "here; commit it, or remove it")]
    if design.rules not in repository.tracked or not os.path.isfile(path):
        return None, []
    try:
        with open(path, encoding="utf-8") as handle:
            rules: List[list] = list(rule_forms(handle.read()))
    except (OSError, sexpr.SexprError) as error:
        return [], [Violation(design.project, "custom_rules", design.rules,
                              f"the custom rules file cannot be read ({error}); KiCad drops a rules file it cannot "
                              "parse without saying so, so none of its rules would be checked")]
    found = []
    names: Dict[str, int] = {}
    for rule in rules:
        names[rule_name(rule)] = names.get(rule_name(rule), 0) + 1
    for name, count in sorted(names.items()):
        if count > 1:
            found.append(Violation(
                design.project, "custom_rules", f"{design.rules} rule '{name}'",
                f"{count} rules are named '{name}', and KiCad loads them all, so the report could not say which of "
                "them a finding comes from; give each rule a name of its own"))
    for rule in rules:
        for clause in ONCE_ONLY_CLAUSES:
            count = len(sexpr.children(rule, clause))
            if count > 1:
                found.append(Violation(
                    design.project, "custom_rules", f"{design.rules} rule '{rule_name(rule)}'",
                    f"the rule holds {count} ({clause} ...) clauses; KiCad loads it and keeps only one of them, so "
                    f"the rule would not mean what it reads as; give it one {clause}"))
        if RESERVED in rule_name(rule).lower():
            found.append(Violation(
                design.project, "custom_rules", f"{design.rules} rule '{rule_name(rule)}'",
                f"the rule's name contains '{RESERVED}', which is reserved for the rules the check adds to the "
                "copy it checks, so a finding of this rule would read in the report as the check's own; rename it"))
        for severity in sexpr.children(rule, "severity"):
            if len(severity) > 1 and severity[1] in ("ignore", "exclusion"):
                found.append(Violation(
                    design.project, "ignored_check", f"{design.rules} rule '{rule_name(rule)}'",
                    f"the custom rule sets its severity to {severity[1]}, which hides what it finds; a check "
                    "set to ignore or marked excluded fails rather than passing, so remove the severity "
                    "or set it to error or warning"))
    return rules, found


def mains_rule(design: Design, rules: Optional[List[list]], signed: Optional[Tuple[float, float]]) -> List[Violation]:
    """What is wrong with the design's own Mains separation rule, if anything.

    The rule is read in one form: a name, exactly one condition written exactly
    as MAINS_CONDITION, and exactly one (constraint clearance (min <n>mm)) and
    one (constraint creepage (min <n>mm)). Every other form fails by name rather
    than being read as near enough: whitespace inside a quoted net class name
    changes the class, a second condition is one KiCad would keep in place of
    the first, and a unit or a further limit KiCad reads differently from this
    check would make the declared figure a guess.
    """
    def fail(location: str, message: str) -> List[Violation]:
        return [Violation(design.project, "separation_rule", location, message)]

    if rules is None:
        return fail(design.rules,
                    "MAINS is present but the design has no custom rules file, so it states no separation "
                    f"rule; add one rule with condition {MAINS_CONDITION} holding both a clearance and a "
                    "creepage constraint")
    exact, narrowed = [], []
    for rule in rules:
        conditions = [str(condition[1]) if len(condition) > 1 else "" for condition in sexpr.children(rule, "condition")]
        if conditions == [MAINS_CONDITION]:
            exact.append(rule)
        elif any("hasNetclass" in text and "Mains" in text for text in conditions):
            narrowed.append(rule)
    if not exact:
        if narrowed:
            names = ", ".join(f"'{rule_name(rule)}'" for rule in narrowed)
            return fail(f"{design.rules} rule {names}",
                        f"the Mains separation rule is narrowed by its condition or not in the required form; "
                        f"its one condition must be exactly {MAINS_CONDITION}, written as shown, with nothing "
                        "narrowing it to a layer or an area")
        return fail(design.rules,
                    f"MAINS is present but no custom rule has the condition {MAINS_CONDITION}; add one holding "
                    "both a clearance and a creepage constraint")
    if len(exact) > 1:
        names = ", ".join(f"'{rule_name(rule)}'" for rule in exact)
        return fail(f"{design.rules} rule {names}",
                    "the Mains separation is split across more than one rule; state it as one rule holding "
                    "both the clearance and the creepage")
    rule = exact[0]
    where = f"{design.rules} rule '{rule_name(rule)}'"
    found = []
    if sexpr.child(rule, "layer") is not None:
        found += fail(where, "the Mains separation rule is narrowed by layer; it must hold on every layer, so remove its (layer ...)")
    constraints: Dict[str, List[list]] = {}
    for constraint in sexpr.children(rule, "constraint"):
        constraints.setdefault(str(constraint[1]) if len(constraint) > 1 else "", []).append(constraint)
    for kind in sorted(set(constraints) - {"clearance", "creepage"}):
        found += fail(where, f"the Mains separation rule holds a (constraint {kind or '...'} ...) "
                             "constraint, which the check does not read; the rule holds only its clearance and its "
                             "creepage, so state any other constraint in a rule of its own")
    for kind, index in (("clearance", 0), ("creepage", 1)):
        given = constraints.get(kind, [])
        if not given:
            found += fail(where, f"the Mains separation rule holds no {kind} constraint; it must hold both clearance and creepage")
            continue
        if len(given) > 1:
            found += fail(where, f"the Mains separation rule holds {len(given)} {kind} constraints, of which KiCad "
                                 f"applies only one; state the {kind} once")
            continue
        declared = declared_mm(given[0])
        if declared is None:
            found += fail(where, f"the Mains separation rule's {kind} is written {one_line(given[0])}, where the "
                                 f"check reads only (constraint {kind} (min <number>mm)): a minimum in millimetres "
                                 "and nothing else; write it in that form")
        elif signed is not None and declared < signed[index] - 1e-9:
            found += fail(where, f"the design declares a {kind} of {declared:g} mm, below the signed "
                                 f"{signed[index]:g} mm in its separation basis record")
    return found


# --- Local clearance overrides ------------------------------------------------


def numeric_clearance(node) -> Optional[float]:
    if sexpr.head(node) == "clearance" and len(node) > 1 and not isinstance(node[1], list):
        try:
            return float(node[1])
        except ValueError:
            return None
    return None


def walk(node, keyword: str):
    """Every list headed `keyword` anywhere below `node`."""
    if isinstance(node, list):
        if sexpr.head(node) == keyword:
            yield node
        for item in node:
            yield from walk(item, keyword)


def net_of(node) -> str:
    net = sexpr.child(node, "net")
    if net is not None and len(net) > 1:
        return str(net[-1])
    name = sexpr.child(node, "net_name")
    return str(name[1]) if name is not None and len(name) > 1 else ""


def at_text(node, keyword: str = "at") -> str:
    at = sexpr.child(node, keyword)
    if at is not None and len(at) > 2:
        return f"({at[1]}, {at[2]}) mm"
    return "(position not stated)"


def net_items(layout: list) -> Dict[str, List[str]]:
    """Every pad, track, arc, via and zone on the layout that carries a net, by net, each as a report names it."""
    found: Dict[str, List[str]] = {}
    for footprint in walk(layout, "footprint"):
        reference = next((str(prop[2]) for prop in sexpr.children(footprint, "property")
                          if len(prop) > 2 and prop[1] == "Reference"), "?")
        for pad in sexpr.children(footprint, "pad"):
            number = str(pad[1]) if len(pad) > 1 else "?"
            found.setdefault(net_of(pad), []).append(
                f"pad {number} [{net_of(pad)}] of {reference} (footprint at {at_text(footprint)})")
    for keyword, kind, where in (("segment", "track", "start"), ("arc", "arc", "start"), ("via", "via", "at")):
        for node in walk(layout, keyword):
            found.setdefault(net_of(node), []).append(f"{kind} [{net_of(node)}] at {at_text(node, where)}")
    for zone in walk(layout, "zone"):
        points = next(walk(zone, "xy"), None)
        corner = f" with a corner at ({points[1]}, {points[2]}) mm" if points is not None and len(points) > 2 else ""
        found.setdefault(net_of(zone), []).append(f"zone [{net_of(zone)}]{corner}")
    found.pop("", None)
    return found


def marker_net(items: Dict[str, List[str]]) -> Optional[str]:
    """The net carrying the fewest items on the layout whose name a rule's condition can hold, or None when there is none."""
    candidates = [(len(found), net) for net, found in items.items() if found and not UNWRITABLE & set(net)]
    return min(candidates)[1] if candidates else None


def overrides(design: Design, layout: list, signed_clearance: float, mains_nets: Set[str]) -> List[Violation]:
    """Clearance overrides that could let low-voltage copper sit closer to Mains copper than the signed figure.

    KiCad ranks a pad's or a footprint's local clearance override above every
    custom rule, taking the larger of the two items' overrides, so one below the
    signed figure on either side of a Mains/low-voltage pair would win over the
    appended signed rule; any such override fails, whatever net it is on. A
    zone's clearance does not outrank custom rules, and a Mains-class zone may
    still not declare one below the signed figure.
    """
    found = []
    why = (f"below the signed {signed_clearance:g} mm; KiCad ranks a pad or footprint clearance override above "
           "every custom rule, so it would let low-voltage copper pass closer than the signed figure. Remove it, "
           f"or raise it to at least {signed_clearance:g} mm and state any smaller clearance as a custom rule instead")
    for footprint in walk(layout, "footprint"):
        reference = "?"
        for prop in sexpr.children(footprint, "property"):
            if len(prop) > 2 and prop[1] == "Reference":
                reference = str(prop[2])
        for item in footprint:
            value = numeric_clearance(item)
            if value is not None and value < signed_clearance - 1e-9:
                found.append(Violation(design.project, "local_clearance_override",
                                       f"footprint {reference} at {at_text(footprint)}",
                                       f"footprint {reference} sets a local clearance override of {value:g} mm, {why}"))
        for pad in sexpr.children(footprint, "pad"):
            number = str(pad[1]) if len(pad) > 1 else "?"
            for node in walk(pad, "clearance"):
                value = numeric_clearance(node)
                if value is not None and value < signed_clearance - 1e-9:
                    found.append(Violation(design.project, "local_clearance_override",
                                           f"pad {number} [{net_of(pad)}] of {reference} (footprint at {at_text(footprint)})",
                                           f"pad {number} of {reference} sets a local clearance override of {value:g} mm, {why}"))
    for zone in walk(layout, "zone"):
        net = net_of(zone)
        if net not in mains_nets:
            continue
        connect = sexpr.child(zone, "connect_pads")
        for node in (connect or []):
            value = numeric_clearance(node)
            if value is not None and value < signed_clearance - 1e-9:
                corner = ""
                points = next(walk(zone, "xy"), None)
                if points is not None and len(points) > 2:
                    corner = f" with a corner at ({points[1]}, {points[2]}) mm"
                found.append(Violation(design.project, "local_clearance_override", f"zone [{net}]{corner}",
                                       f"a zone on Mains-class net {net} sets a clearance of {value:g} mm, below the signed "
                                       f"{signed_clearance:g} mm; a Mains-class zone may not declare a clearance below the "
                                       f"separation basis, so raise it to at least {signed_clearance:g} mm"))
    return found


def net_ties(design: Design, layout: list, mains_nets: Set[str]) -> List[Violation]:
    """Net-tie footprints joining a Mains-class net to a net outside the class.

    A net tie joins its nets in copper, which is what it is for, and KiCad 10.0.7
    checks no clearance between the pads it ties: a tie between a Mains-class
    net and any other would join low-voltage copper to mains outright, with the
    signed clearance unchecked where they meet. Each pad group is read as KiCad writes
    it, a string of pad numbers separated by commas; a group naming a pad the
    footprint does not have is not one whose nets can be told, and fails too.
    """
    found = []
    for footprint in walk(layout, "footprint"):
        groups = sexpr.child(footprint, "net_tie_pad_groups")
        if groups is None:
            continue
        reference = next((str(prop[2]) for prop in sexpr.children(footprint, "property")
                          if len(prop) > 2 and prop[1] == "Reference"), "?")
        where = f"footprint {reference} at {at_text(footprint)}"
        pads: Dict[str, Set[str]] = {}
        for pad in sexpr.children(footprint, "pad"):
            pads.setdefault(str(pad[1]) if len(pad) > 1 else "", set()).add(net_of(pad))
        for group in groups[1:]:
            numbers = [number.strip() for number in str(group).split(",")]
            unknown = [number for number in numbers if number not in pads]
            if isinstance(group, list) or unknown:
                found.append(Violation(design.project, "mains_net_tie", where,
                                       f"net tie group {one_line(group)} of {reference} names "
                                       f"{'pad' + ('s ' if len(unknown) > 1 else ' ') + ', '.join(unknown) + ', which the footprint does not have' if unknown else 'no pad numbers'}, "
                                       "so which nets it joins cannot be told; name the tied pads by number, separated by commas"))
                continue
            nets = set().union(*(pads[number] for number in numbers))
            inside, outside = sorted(nets & mains_nets), sorted(nets - mains_nets)
            if inside and outside:
                found.append(Violation(design.project, "mains_net_tie", where,
                                       f"net tie {reference} joins Mains-class {', '.join(inside)} to "
                                       f"{', '.join(name or '(no net)' for name in outside)}, outside the class, through "
                                       f"pads {', '.join(numbers)}; a net tie joins its nets in copper, so this joins low-voltage "
                                       "copper to mains, and KiCad checks no clearance between the pads it ties: a net tie may "
                                       "join only Mains-class nets to one another"))
    return found


# --- Workmanship --------------------------------------------------------------
#
# The workmanship area of the method's layout practice catalogue holds items of
# two kinds of rule. The angle at a joint, the length of a segment, and a
# track end or a via left unconnected are KiCad's to measure, through a custom
# rule in the design's rules file or, for the track end and the via, unaided;
# the check only requires that the rules are there. What KiCad does not
# measure, the check measures itself from the layout file, each against a
# figure the design sets, as a project text variable or, for two tracks
# meeting at a pad, as the corner rule's own minimum, so no figure is ever the
# check's own.


#: Each measured rule: the catalogue item it is, what it measures, the project
#: text variable its figure is set in, the figure's unit, and the least and
#: most the figure may be (a most of None is open-ended).
MEASURED = (
    ("WORK-2", "route length", "WORK_DETOUR_RATIO",
     "times the shortest straight-line tree joining the net's pads", 1.0, None),
    ("WORK-4", "branch at a pad", "WORK_PAD_ANGLE_DEG", "degrees at least between two of three or more tracks of a "
     "net that leave a pad on one layer", 0.0, 180.0),
    ("WORK-8", "narrowing", "WORK_NECK_MM", "mm off its net's pads that a track narrower than its net class's "
     "track width may run", 0.0, None),
    ("WORK-9", "direction", "WORK_ANGLE_TOLERANCE_DEG", "degrees off the board's edges or 45 degrees to them, "
     "and off a long pad's axis", 0.0, 22.5),
    ("WORK-10", "pad entry", "WORK_PAD_ENTRY_RATIO", "times as long as wide, beyond which a pad is entered only "
     "along its long axis", 1.0, None),
    ("MAINS-5", "barrier copper", "BARRIER_COPPER_MM2", "mm² of copper at most between the pad rows of a part that "
     "bridges the barrier", 0.0, None),
    ("MFG-4", "paste over a via", "PASTE_OVER_VIA_MM2", "mm² at most of a via's hole under a paste opening", 0.0, None),
    ("TEST-5", "test point to courtyard", "TEST_COURTYARD_MM", "mm at least from a test point's pad to the courtyard of "
     "any other part, on either side of the board", 1.0, None),
)

#: Each custom rule a design's rules file must hold, by the catalogue item it
#: is, the KiCad constraint, and how its minimum is written.
WORKMANSHIP_RULES = (
    ("WORK-4", "corner", "track_angle", r"[0-9]+(?:\.[0-9]+)?", "(min <angle>), a bare number of degrees"),
    ("WORK-5", "jog", "track_segment_length", r"[0-9]+(?:\.[0-9]+)?mm", "(min <length>mm)"),
)

#: The conditions a workmanship custom rule may carry: none, or one naming
#: every track, so that the rule holds on every track of the board.
EVERY_TRACK = ("A.Type == 'Track'",)

#: The catalogue item each of KiCad's own workmanship findings is, so the
#: report names the item whichever of them reports it.
KICAD_WORKMANSHIP = {
    "track_angle": "WORK-4 corners turned at 45 degrees or as arcs",
    "track_segment_length": "WORK-5 no jog",
    "track_dangling": "WORK-6 no stub",
    "via_dangling": "WORK-7 no via a route does not need",
}

#: How near two points must be to be read as one, in mm: well under anything
#: drawn, well over the nanometre KiCad rounds a coordinate to.
TOUCH = 1e-4

#: How far a straight piece standing in for part of an arc may lie off the
#: arc, in mm: a fifth of the 0.005 mm KiCad allows itself by default when it
#: draws an arc as straight pieces, so an arc of any radius is read as closely.
ARC_SAG = 1e-3


def workmanship_figures(design: Design, variables: dict) -> Tuple[Dict[str, float], List[Violation]]:
    """The figure each measured rule is held to, read from the project's text variables, and every one missing or malformed."""
    figures: Dict[str, float] = {}
    found = []
    for item, what, name, unit, least, most in MEASURED:
        where = f"{design.project} text_variables.{name}"
        value = variables.get(name)
        if value is None:
            found.append(Violation(design.project, "workmanship_figure", where,
                                   f"{item} ({what}) has no figure: the project text variable {name} is not set, so "
                                   f"the rule cannot be measured; set it to the figure the board's rules table gives "
                                   f"for {item}, a plain decimal number of {unit}"))
            continue
        number_ = float(value) if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", str(value).strip()) else None
        if number_ is None or number_ < least or (most is not None and number_ >= most):
            limits = f"no less than {least:g}" + (f" and less than {most:g}" if most is not None else "")
            found.append(Violation(design.project, "workmanship_figure", where,
                                   f"{item} ({what}) has a malformed figure: the project text variable {name} is "
                                   f"'{value}', where it is a plain decimal number of {unit}, {limits}; write the "
                                   f"figure the board's rules table gives for {item} in that form"))
            continue
        figures[name] = number_
    return figures, found


def written_minimum(rule: list, constraint: str, form: str) -> Optional[str]:
    """The minimum a rule writes for a workmanship constraint, as written, or None when it writes it in no other form than
    one (constraint <constraint> (min <figure>)) with the figure in `form`."""
    holding = [node for node in sexpr.children(rule, "constraint") if len(node) > 1 and str(node[1]) == constraint]
    minimum = holding[0][2] if len(holding) == 1 and len(holding[0]) == 3 else None
    if (sexpr.head(minimum) == "min" and len(minimum) == 2 and not isinstance(minimum[1], (list, sexpr.Quoted))
            and re.fullmatch(form, str(minimum[1]))):
        return str(minimum[1])
    return None


def held(rules: Optional[List[list]], constraint: str, form: str) -> Tuple[List[list], List[Tuple[list, str]]]:
    """Every rule holding a workmanship constraint, and those of them in force on every track, each with the minimum it writes."""
    candidates, good = [], []
    for rule in rules or []:
        if not any(len(node) > 1 and str(node[1]) == constraint for node in sexpr.children(rule, "constraint")):
            continue
        candidates.append(rule)
        conditions = tuple(str(condition[1]) if len(condition) > 1 else "" for condition in sexpr.children(rule, "condition"))
        minimum = written_minimum(rule, constraint, form)
        if minimum is not None and conditions in ((), EVERY_TRACK) and sexpr.child(rule, "layer") is None:
            good.append((rule, minimum))
    return candidates, good


def figure_of(minimum: str) -> float:
    """A workmanship rule's minimum as a number, in degrees or mm."""
    return float(minimum[:-2] if minimum.endswith("mm") else minimum)


def workmanship_rules(design: Design, rules: Optional[List[list]]) -> List[Violation]:
    """Every workmanship custom rule the design's rules file lacks, does not hold on every track, or loosens.

    The rule in force on every track is the last one with no condition, or
    the every-track condition, and no layer, since KiCad applies the last rule
    that matches; its minimum is the board's figure. Any other rule holding the
    constraint, before or after it, with or without a condition, fails unless
    it writes a minimum no looser than that figure: a later one would loosen the
    item wherever it matches, and an earlier one would state a figure the board
    is not held to.
    """
    found = []
    for item, what, constraint, form, written in WORKMANSHIP_RULES:
        candidates, good = held(rules, constraint, form)
        if good:
            in_force, figure = good[-1]
            unit = "mm" if figure.endswith("mm") else " degrees"
            for rule in candidates:
                if rule is in_force:
                    continue
                minimum = written_minimum(rule, constraint, form)
                if minimum is not None and figure_of(minimum) >= figure_of(figure):
                    continue
                writes = (f"writes {constraint} (min {minimum}), looser than" if minimum is not None
                          else f"writes {constraint} in no other form than (min ...) as {written}, so it cannot be "
                               "shown to be no looser than")
                found.append(Violation(design.project, "workmanship_rule", f"{design.rules} {rule_at(rule)}",
                                       f"{item} ({what}) is loosened: {rule_at(rule)} {writes} the board's figure of "
                                       f"{figure_of(figure):g}{unit} in {rule_at(in_force)}, so the tracks it matches "
                                       f"could break the item while KiCad's check passes; remove the rule, or write its "
                                       f"minimum as {written} at {figure_of(figure):g}{unit} or tighter"))
            continue
        if candidates:
            names = ", ".join(f"'{rule_name(rule)}'" for rule in candidates)
            found.append(Violation(design.project, "workmanship_rule", f"{design.rules} rule {names}",
                                   f"{item} ({what}) is not in force on every track: the rule holding its "
                                   f"{constraint} constraint is narrowed by its condition or its layer, or does not "
                                   f"write its minimum as {written}; write one rule with no condition, or the one "
                                   f"condition {EVERY_TRACK[0]}, no layer, and (constraint {constraint} {written})"))
        else:
            found.append(Violation(design.project, "workmanship_rule", design.rules,
                                   f"{item} ({what}) has no rule: the design's rules file holds no "
                                   f"(constraint {constraint} ...), so KiCad does not measure it; add a rule holding "
                                   f"(constraint {constraint} {written}) at the figure the board's rules table gives "
                                   f"for {item}"))
    return found


#: The least distance, in mm, the crystal keep-clear holds the parts unrelated to the oscillator from the crystal's courtyard.
KEEP_CLEAR_MM = 25.0

#: A footprint name that is a crystal or a ceramic resonator, as KiCad's own libraries name them.
CRYSTAL_FOOTPRINT = re.compile(r"(?i)(crystal|resonator)_")

#: The condition of the crystal keep-clear: the crystal, and each part exempt from it.
KEEP_CLEAR_CONDITION = re.compile(r"A\.Reference == '([^']+)'((?: && B\.Reference != '[^']+')*)")

#: The condition of the ground pad reliefs: pads of one net class, bar each exposed pad it names.
RELIEF_PAD = r"\(A\.Reference == '[^']+' && A\.Pad_Number == '[^']+'\)"
RELIEF_CONDITION = re.compile(r"A\.Type == 'Pad' && A\.hasNetclass\('([^']+)'\)((?: && !" + RELIEF_PAD + ")*)")


def sole_rule_form(rule: list) -> Optional[str]:
    """The text of a rule's one condition where its only other clause is one constraint, else None."""
    clauses = [node for node in rule[2:] if isinstance(node, list)]
    conditions = [node for node in clauses if sexpr.head(node) == "condition"]
    constraints = [node for node in clauses if sexpr.head(node) == "constraint"]
    if len(clauses) != 2 or len(conditions) != 1 or len(constraints) != 1 or len(conditions[0]) != 2:
        return None
    return str(conditions[0][1])


def board_footprints(tree: list) -> Dict[str, list]:
    """Every footprint of a layout by its reference."""
    return {board_geometry.reference(footprint): footprint for footprint in sexpr.children(tree, "footprint")
            if board_geometry.reference(footprint)}


def crystal_keep_clear(design: Design, rules: Optional[List[list]], tree: list) -> List[Violation]:
    """Every crystal on the layout the rules file does not hold KiCad to keeping unrelated parts clear of.

    A footprint named for a crystal or a resonator needs a rule holding
    (constraint courtyard_clearance (min <figure>mm)) with a figure of at least
    KEEP_CLEAR_MM, whose one condition names it as A and exempts parts from
    B only by reference, and which leaves at least one other footprint of the
    layout unexempted: a rule that exempts every part, or is written in any
    other form, holds nothing. Any other rule holding the constraint that names
    the crystal is a rule KiCad may apply after it, so it fails too.
    """
    footprints = board_footprints(tree)
    crystals = sorted(reference for reference, footprint in footprints.items()
                      if CRYSTAL_FOOTPRINT.match(str(footprint[1]).split(":")[-1]))
    found = []
    holding = [rule for rule in rules or [] if any(len(node) > 1 and str(node[1]) == "courtyard_clearance"
                                                  for node in sexpr.children(rule, "constraint"))]
    for crystal in crystals:
        others = set(footprints) - {crystal}
        forms = []
        for rule in holding:
            text = sole_rule_form(rule)
            matched = KEEP_CLEAR_CONDITION.fullmatch(text) if text is not None else None
            minimum = written_minimum(rule, "courtyard_clearance", r"[0-9]+(?:\.[0-9]+)?mm")
            if matched and matched.group(1) == crystal and minimum is not None:
                forms.append((rule, figure_of(minimum), set(re.findall(r"B\.Reference != '([^']+)'", matched.group(2)))))
        if not forms:
            found.append(Violation(design.project, "crystal_keepclear", f"{design.rules} crystal {crystal}",
                                   f"{crystal} is a crystal, and the rules file holds no rule keeping the parts unrelated "
                                   f"to the oscillator clear of it: add (rule \"Crystal keep-clear\" (condition "
                                   f"\"A.Reference == '{crystal}' && B.Reference != '<related part>'\") (constraint "
                                   f"courtyard_clearance (min {KEEP_CLEAR_MM:g}mm))), with one B.Reference != '<part>' "
                                   "for each part related to the oscillator"))
            continue
        for rule, figure, exempt in forms:
            if figure < KEEP_CLEAR_MM:
                found.append(Violation(design.project, "crystal_keepclear", f"{design.rules} {rule_at(rule)}",
                                       f"{rule_at(rule)} keeps parts {figure:g} mm from the courtyard of {crystal}, "
                                       f"under the {KEEP_CLEAR_MM:g} mm the crystal keep-clear holds; raise its minimum"))
            elif others and not others - exempt:
                found.append(Violation(design.project, "crystal_keepclear", f"{design.rules} {rule_at(rule)}",
                                       f"{rule_at(rule)} exempts every other part of the layout from the keep-clear of "
                                       f"{crystal}, so it holds nothing; exempt only the parts related to the oscillator"))
        formed = {id(rule) for rule, _, _ in forms}
        for rule in holding:
            if id(rule) in formed or f"'{crystal}'" not in " ".join(str(node[1]) for node in sexpr.children(rule, "condition") if len(node) > 1):
                continue
            found.append(Violation(design.project, "crystal_keepclear", f"{design.rules} {rule_at(rule)}",
                                   f"{rule_at(rule)} holds a courtyard_clearance constraint and names {crystal}, but not "
                                   "in the one form of the crystal keep-clear, so KiCad may apply it after the keep-clear "
                                   "and loosen it; remove it, or write it as the keep-clear"))
    return found


def exposed_pad(pads: Sequence[board_geometry.Pad], one: board_geometry.Pad) -> bool:
    """Whether a pad is its footprint's exposed pad: the footprint has more than two pads and this one is strictly the largest."""
    area = one.size[0] * one.size[1]
    return len(pads) > 2 and all(area > other.size[0] * other.size[1] for other in pads if other is not one)


#: A net class named ground or gnd in any case is a ground class (see ground_reliefs).
GROUND_CLASS = re.compile(r"(?i)ground|gnd")


def ground_reliefs(design: Design, rules: Optional[List[list]], tree: list, members: Dict[str, Set[str]]
                   ) -> List[Violation]:
    """Every ground net class of the board, with pads the relief applies to, that the rules file does not hold to thermal reliefs.

    A net class named ground or gnd in any case is a ground class. Where a
    pad of the layout on a net of one is not its footprint's exposed pad, the
    rules file needs a rule holding (constraint zone_connection thermal_reliefs)
    whose one condition is a pad of that class, bar each exposed pad it names as
    a reference and a pad number, and every pad it exempts must be an exposed
    pad on a net of the class, with at least one other pad of the class left
    under the rule. A rule in any other form holds nothing.
    """
    table = board_geometry.net_table(tree)
    placed = [board_geometry.footprint_pads(footprint, table) for footprint in sexpr.children(tree, "footprint")]
    found = []
    for ground in sorted(name for name in members if GROUND_CLASS.search(name)):
        pads = [(pad, exposed_pad(group, pad)) for group in placed for pad in group if pad.net in members[ground]]
        if not any(not exposed for _, exposed in pads):
            continue
        exposed = {(pad.reference, pad.number) for pad, is_exposed in pads if is_exposed}
        forms = []
        for rule in rules or []:
            constraints = [node for node in sexpr.children(rule, "constraint") if len(node) > 1 and str(node[1]) == "zone_connection"]
            if not constraints:
                continue
            text = sole_rule_form(rule)
            matched = RELIEF_CONDITION.fullmatch(text) if text is not None else None
            if matched and matched.group(1) == ground and constraints[0][2:] == ["thermal_reliefs"]:
                forms.append((rule, set(re.findall(r"A\.Reference == '([^']+)' && A\.Pad_Number == '([^']+)'", matched.group(2)))))
        where = f"{design.rules} ground class {ground}"
        if not forms:
            found.append(Violation(design.project, "ground_relief", where,
                                   f"the pads of net class {ground} are joined to a pour by the zone's own setting alone: "
                                   f"the rules file holds no rule giving them thermal reliefs; add (rule \"Ground pad "
                                   f"reliefs\" (condition \"A.Type == 'Pad' && A.hasNetclass('{ground}')\") (constraint "
                                   "zone_connection thermal_reliefs)), with && !(A.Reference == '<part>' && A.Pad_Number "
                                   "== '<n>') for each exposed thermal pad that is joined in full"))
            continue
        for rule, exempt in forms:
            stray = sorted(exempt - exposed)
            if stray:
                found.append(Violation(design.project, "ground_relief", f"{design.rules} {rule_at(rule)}",
                                       f"{rule_at(rule)} exempts {', '.join(f'{ref} pad {number}' for ref, number in stray)} "
                                       f"from the reliefs of net class {ground}, but it is not an exposed pad on a net of "
                                       "the class; exempt only an exposed thermal pad"))
    return found


def corner_minimum(rules: Optional[List[list]]) -> Optional[float]:
    """The least angle the design's corner rule allows at a joint, as KiCad applies it, or None when no corner rule is in force.

    Where several rules in force hold the constraint, KiCad applies the last
    one in the file, so its figure is the one read.
    """
    _, good = held(rules, "track_angle", WORKMANSHIP_RULES[0][3])
    return float(good[-1][1]) if good else None


class Copper:
    """One track or arc on the layout: its net, layer, ends, width and length, and for an arc its mid point."""

    def __init__(self, net: str, layer: str, start, end, width: float, mid=None):
        self.net, self.layer, self.start, self.end, self.width, self.mid = net, layer, start, end, width, mid
        self.centre = self.radius = None
        if mid is not None:
            circle = circumcircle(start, mid, end)
            if circle is not None:
                self.centre, self.radius = circle
        self.length = self.arc_length() if self.centre is not None else math.dist(start, end)

    def kind(self) -> str:
        return "arc" if self.mid is not None else "track"

    def place(self) -> str:
        return (f"{self.kind()} [{self.net}] on {self.layer} from ({coordinate(self.start[0])}, {coordinate(self.start[1])}) "
                f"to ({coordinate(self.end[0])}, {coordinate(self.end[1])}) mm")

    def sweep(self) -> float:
        """The angle the arc turns through from start to end, by way of its mid point, signed."""
        first, through, last = (math.atan2(p[1] - self.centre[1], p[0] - self.centre[0])
                                for p in (self.start, self.mid, self.end))
        sweep = (last - first) % (2 * math.pi)
        if (through - first) % (2 * math.pi) > sweep:
            sweep -= 2 * math.pi
        return sweep

    def arc_length(self) -> float:
        return abs(self.sweep()) * self.radius

    def heading(self, at) -> Tuple[float, float]:
        """The direction the copper runs at one of its ends, as a unit vector along the line it lies on there."""
        if self.centre is None:
            dx, dy = self.end[0] - self.start[0], self.end[1] - self.start[1]
        else:
            dx, dy = -(at[1] - self.centre[1]), at[0] - self.centre[0]
        size = math.hypot(dx, dy)
        return (dx / size, dy / size) if size else (0.0, 0.0)

    def points(self) -> List[Tuple[float, float]]:
        """Points along the copper's centre line, an arc's close enough together that no straight piece between two lies
        more than ARC_SAG off the arc, whatever its radius."""
        if self.centre is None:
            return [self.start, self.end]
        first = math.atan2(self.start[1] - self.centre[1], self.start[0] - self.centre[0])
        sweep = self.sweep()
        step = 2 * math.acos(max(-1.0, 1 - ARC_SAG / self.radius))
        pieces = max(32, math.ceil(abs(sweep) / step))
        return [(self.centre[0] + self.radius * math.cos(first + sweep * i / pieces),
                 self.centre[1] + self.radius * math.sin(first + sweep * i / pieces)) for i in range(pieces + 1)]


def circumcircle(a, b, c):
    """The centre and radius of the circle through three points, or None when they lie on one line."""
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return None
    ux = ((a[0] ** 2 + a[1] ** 2) * (b[1] - c[1]) + (b[0] ** 2 + b[1] ** 2) * (c[1] - a[1])
          + (c[0] ** 2 + c[1] ** 2) * (a[1] - b[1])) / d
    uy = ((a[0] ** 2 + a[1] ** 2) * (c[0] - b[0]) + (b[0] ** 2 + b[1] ** 2) * (a[0] - c[0])
          + (c[0] ** 2 + c[1] ** 2) * (b[0] - a[0])) / d
    return (ux, uy), math.hypot(a[0] - ux, a[1] - uy)


class Layout:
    """The copper of a layout the measured rules read: every track, arc and pad, by net.

    Whether a track meets a pad is judged from the copper by board_geometry's
    contact rule, and a pad whose copper that rule cannot size is never
    measured: it is listed in `unsized` when tracks of its net reach a layer it
    is on, and the measures fail the board naming it.
    """

    def __init__(self, tree: list):
        table = board_geometry.net_table(tree)
        self.copper: List[Copper] = []
        for node in tree[1:]:
            head = sexpr.head(node)
            if head not in ("segment", "arc"):
                continue
            what = f"a {'track' if head == 'segment' else 'arc'} of the layout"
            layer = sexpr.child(node, "layer")
            width = sexpr.child(node, "width")
            self.copper.append(Copper(
                board_geometry.item_net(node, table, what), str(layer[1]) if layer is not None and len(layer) > 1 else "",
                board_geometry.xy(sexpr.child(node, "start"), what), board_geometry.xy(sexpr.child(node, "end"), what),
                board_geometry.number(width, 1, what) if width is not None else 0.0,
                board_geometry.xy(sexpr.child(node, "mid"), what) if head == "arc" else None))
        self.pads = board_geometry.pads(tree)
        self.edges = edge_angle(tree)
        routed = {(copper.net, copper.layer) for copper in self.copper if copper.net}
        self.unsized = [pad for pad in self.pads if not pad.sized() and pad.net
                        and any(net == pad.net and pad.on(layer) for net, layer in routed)]

    def pads_of(self, net: str, layer: str) -> List[board_geometry.Pad]:
        """Every pad of a net on a layer whose copper the contact rule can size."""
        return [pad for pad in self.pads if pad.net == net and pad.on(layer) and pad.sized()]

    def reached(self, copper: Copper, end) -> List[board_geometry.Pad]:
        """Every pad of the copper's net and layer that its end at `end` reaches."""
        return [pad for pad in self.pads_of(copper.net, copper.layer)
                if board_geometry.end_reaches(pad, end, copper.width)]


def shape_sides(node: list, place) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Every straight side of one outline shape, each end carried to the board by `place`.

    A line is one side. A rectangle is four, each shortened at both ends by
    the radius its corners are rounded to, and none where that leaves nothing
    straight. A polygon has a side between each two corners its outline runs
    straight between, and none along a piece it writes as an arc. An arc, a
    circle and a curve turn all along their length, so none has a direction
    to give the edges and none is a side.
    """
    head = sexpr.head(node)[3:]
    what = "a board edge"
    if head == "line":
        return [(place(board_geometry.xy(sexpr.child(node, "start"), what)),
                 place(board_geometry.xy(sexpr.child(node, "end"), what)))]
    if head == "rect":
        (x0, y0), (x1, y1) = (board_geometry.xy(sexpr.child(node, key), what) for key in ("start", "end"))
        radius = sexpr.child(node, "radius")
        rounded = board_geometry.number(radius, 1, what) if radius is not None else 0.0
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        sides = []
        for a, b in zip(corners, corners[1:] + corners[:1]):
            length = math.dist(a, b)
            if length > 2 * rounded + TOUCH:
                step = (rounded * (b[0] - a[0]) / length, rounded * (b[1] - a[1]) / length)
                sides.append((place((a[0] + step[0], a[1] + step[1])), place((b[0] - step[0], b[1] - step[1]))))
        return sides
    if head == "poly":
        ring = []
        for part in (sexpr.child(node, "pts") or [])[1:]:
            if sexpr.head(part) == "xy":
                ring.append((board_geometry.xy(part, what), True))
            elif sexpr.head(part) == "arc":
                ring.append((board_geometry.xy(sexpr.child(part, "start"), what), False))
                ring.append((board_geometry.xy(sexpr.child(part, "end"), what), True))
        return [(place(a), place(ring[(index + 1) % len(ring)][0])) for index, (a, straight) in enumerate(ring)
                if straight and math.dist(a, ring[(index + 1) % len(ring)][0]) > TOUCH]
    return []


def on_edge(node: list) -> bool:
    layer = sexpr.child(node, "layer")
    return layer is not None and len(layer) > 1 and str(layer[1]) == "Edge.Cuts"


def edge_sides(tree: list) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Every straight side of the board's outline as drawn, its own shapes and its footprints', on the board."""
    sides = []
    for node in tree[1:]:
        if sexpr.head(node).startswith("gr_") and on_edge(node):
            sides += shape_sides(node, lambda point: point)
    for footprint in sexpr.children(tree, "footprint"):
        at = board_geometry.placement(footprint, f"the footprint {board_geometry.reference(footprint) or '?'}")
        for node in footprint[1:]:
            if sexpr.head(node).startswith("fp_") and on_edge(node):
                sides += shape_sides(node, lambda point, at=at: board_geometry.placed(point, at))
    return sides


def edge_angle(tree: list) -> float:
    """The direction of the board's edges, in degrees modulo 90: that of the longest straight side of its outline, or 0,
    the board's own axes, for an outline with none."""
    longest, angle = 0.0, 0.0
    for a, b in edge_sides(tree):
        if math.dist(a, b) > longest:
            longest, angle = math.dist(a, b), math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 90
    return angle


def off_45(angle: float) -> float:
    """How far an angle in degrees lies from the nearest multiple of 45 degrees."""
    rest = angle % 45
    return min(rest, 45 - rest)


def off_axis(heading, axis) -> float:
    """The angle in degrees between a direction and an axis, read as lines, so 0 to 90."""
    cosine = abs(heading[0] * axis[0] + heading[1] * axis[1])
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def pad_corners(design: Design, layout: Layout, corner: Optional[float], branch: float) -> List[Violation]:
    """WORK-4 at a pad: every two tracks of a net that leave one of its pads on one layer closer together than the item allows.

    KiCad's corner rule does not compare tracks that meet at a pad, so they
    are measured here, each track's direction taken as it leaves the pad. Two
    tracks meeting at a pad are one route turning there, held to `corner`,
    the corner rule's own minimum; a route branches at a pad only where three
    or more of its tracks leave it on one layer, and those are held to
    `branch`. With no corner rule in force, which the check already fails,
    two tracks meeting at a pad are not measured.
    """
    found = []
    for pad in layout.pads:
        if not pad.sized():
            continue
        for layer in sorted({copper.layer for copper in layout.copper if copper.net == pad.net and pad.on(copper.layer)}):
            leaving = []
            for copper in layout.copper:
                if copper.net != pad.net or copper.layer != layer:
                    continue
                for end, other in ((copper.start, copper.end), (copper.end, copper.start)):
                    if (board_geometry.end_reaches(pad, end, copper.width)
                            and not board_geometry.end_reaches(pad, other, copper.width)):
                        heading = copper.heading(end)
                        if copper.centre is None and end == copper.end:
                            heading = (-heading[0], -heading[1])
                        elif copper.centre is not None:
                            towards = (other[0] - end[0], other[1] - end[1])
                            if heading[0] * towards[0] + heading[1] * towards[1] < 0:
                                heading = (-heading[0], -heading[1])
                        leaving.append((copper, heading))
            if len(leaving) == 2:
                least, held = corner, "the corner rule's track_angle allows"
                said = f"{pad.net} turns through {pad.name()} on {layer}"
                remedy = "turn the route through the pad straight or at 45 degrees, as at any other joint"
            else:
                least, held = branch, "WORK_PAD_ANGLE_DEG allows"
                said = f"{pad.net} branches at {pad.name()} on {layer}, {len(leaving)} of its tracks leaving it"
                remedy = "turn its branches to leave the pad square to one another or wider"
            if least is None:
                continue
            for index, (first, a) in enumerate(leaving):
                for second, b in leaving[index + 1:]:
                    apart = math.degrees(math.acos(max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))))
                    if apart < least - 1e-6:
                        found.append(Violation(design.project, "workmanship_pad_corner",
                                               f"net {pad.net}: {pad.name()} at ({coordinate(pad.centre[0])}, "
                                               f"{coordinate(pad.centre[1])}) mm on {layer}: {first.place()}; {second.place()}",
                                               f"WORK-4 corners turned at 45 degrees or as arcs: {said}, and two tracks "
                                               f"leave it {apart:.2f} degrees apart, where {held} no less than {least:g} "
                                               f"degrees; KiCad's corner rule does not compare tracks that meet at a pad, "
                                               f"so {remedy}"))
    return found


def detours(design: Design, layout: Layout, ratio: float) -> List[Violation]:
    """WORK-2: every net routed in tracks whose track length exceeds `ratio` times the shortest tree joining all its pads.

    The tree joins the centres of every pad of the net, whatever joins them,
    so zones never enter the measure: a zone cannot shorten the tree, so it
    can neither exempt a net nor take a pad out of it, and a net whose
    connection a zone carries only gains room against it. A pad's centre is
    known whatever its copper, so every net is measured.
    """
    found = []
    nets = board_geometry.by_net(layout.pads)
    for net in sorted({copper.net for copper in layout.copper if copper.net}):
        pads_ = nets.get(net, [])
        if len(pads_) < 2:
            continue
        tree = board_geometry.pad_tree(pads_)
        length = sum(copper.length for copper in layout.copper if copper.net == net)
        if tree > 0 and length > ratio * tree + 1e-6:
            first = sorted(pads_, key=lambda pad: (pad.reference, pad.number))[0]
            found.append(Violation(design.project, "workmanship_detour",
                                   f"net {net}: {len(pads_)} pads, from {first.name()} at "
                                   f"({coordinate(first.centre[0])}, {coordinate(first.centre[1])}) mm",
                                   f"WORK-2 routes run direct: {net}'s tracks are {length:.2f} mm long, {length / tree:.2f} "
                                   f"times the {tree:.2f} mm of the shortest straight-line tree joining its pads, where "
                                   f"WORK_DETOUR_RATIO allows {ratio:g} times; route it the direct way, or move its parts "
                                   "together"))
    return found


def directions(design: Design, layout: Layout, tolerance: float) -> List[Violation]:
    """WORK-9: every track not parallel to the board's edges or at 45 degrees to them.

    A straight track runs one way along its length. An arc turns, so it is held
    by the way it runs at its two ends: a fillet joining two tracks that each
    run one of those ways leaves and meets them along those ways and passes,
    while a flat arc standing in for a track drawn at an odd angle runs that
    angle at its ends and fails.
    """
    found = []
    for copper in layout.copper:
        if copper.length <= TOUCH:
            continue
        ends = (copper.start,) if copper.centre is None else (copper.start, copper.end)
        off, end = max((off_45(math.degrees(math.atan2(*reversed(copper.heading(end)))) - layout.edges), end) for end in ends)
        if off > tolerance + 1e-9:
            how = ("track runs" if copper.centre is None else "arc runs") + f" {off:.2f} degrees off the nearest of those directions"
            if copper.centre is not None:
                how += (f" at its end at ({coordinate(end[0])}, {coordinate(end[1])}) mm, which is the way an arc leaves "
                        "or meets the route")
            found.append(Violation(design.project, "workmanship_direction", f"net {copper.net}: {copper.place()}",
                                   f"WORK-9 routing runs parallel to the board's edges or at 45 degrees to them: the "
                                   f"{how}, where WORK_ANGLE_TOLERANCE_DEG allows {tolerance:g} degrees; redraw it "
                                   "along one of them"))
    return found


def crossed(layout: Layout, copper: Copper) -> List[Tuple[Tuple[float, float], board_geometry.Pad]]:
    """Each pad of its net whose copper the track's copper runs over with neither end reaching it, with a point of the
    track's centre line where it does, at which its direction is read."""
    found = []
    line = copper.points()
    for pad in layout.pads_of(copper.net, copper.layer):
        if (not board_geometry.joins(pad, line, copper.width)
                or any(board_geometry.end_reaches(pad, end, copper.width) for end in (copper.start, copper.end))):
            continue
        over = [(a, b) for a, b in zip(line, line[1:]) if board_geometry.line_reaches(pad, a, b, copper.width)]
        if over:
            a, b = min(over, key=lambda piece: board_geometry.distance_to_segment(pad.centre, *piece))
            found.append((((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), pad))
    return found


def pad_entries(design: Design, layout: Layout, ratio: float, tolerance: float) -> List[Violation]:
    """WORK-10: every track entering, or running across, a pad more than `ratio` times as long as it is wide other than along its long axis."""
    found = []
    for copper in layout.copper:
        meetings = []
        for end, other_end in ((copper.start, copper.end), (copper.end, copper.start)):
            for pad in layout.reached(copper, end):
                if not board_geometry.end_reaches(pad, other_end, copper.width):
                    meetings.append((end, pad, "enters it"))
        meetings += [(point, pad, "runs across it") for point, pad in crossed(layout, copper)]
        for end, pad, how in meetings:
            axis = pad.long_axis()
            if axis is None or max(pad.size) <= ratio * min(pad.size) + 1e-9:
                continue
            off = off_axis(copper.heading(end), axis)
            if off > tolerance + 1e-9:
                found.append(Violation(design.project, "workmanship_pad_entry",
                                       f"net {copper.net}: {copper.place()}, "
                                       f"{'entering' if how == 'enters it' else 'running across'} {pad.name()} at "
                                       f"({coordinate(pad.centre[0])}, {coordinate(pad.centre[1])}) mm",
                                       f"WORK-10 tracks enter a pad along its long axis from its end: {pad.name()} is "
                                       f"{max(pad.size):g} by {min(pad.size):g} mm, more than the {ratio:g} times as long "
                                       f"as wide WORK_PAD_ENTRY_RATIO sets, and the {copper.kind()} {how} {off:.2f} "
                                       f"degrees off its long axis, where WORK_ANGLE_TOLERANCE_DEG allows "
                                       f"{tolerance:g} degrees; bring the track straight into the pad's end"))
    return found


def off_pads(layout: Layout, copper: Copper, steps: int = 200) -> float:
    """How much of a track's length lies off the copper of its net's pads on its layer."""
    line = copper.points()
    pads_ = layout.pads_of(copper.net, copper.layer)
    off = 0.0
    for a, b in zip(line, line[1:]):
        piece = math.dist(a, b) / steps
        for i in range(steps):
            t = (i + 0.5) / steps
            point = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            if not any(pad.distance(point) <= board_geometry.CONTACT for pad in pads_):
                off += piece
    return off


def narrowings(design: Design, layout: Layout, neck: float, widths: Dict[str, float]) -> List[Violation]:
    """WORK-8: every run of track narrower than its net class's track width other than where it necks down into a pad.

    `widths` is each net's class track width. A track narrower than that is
    allowed only as part of a run of such tracks that reaches a pad of its net
    and runs no more than `neck` in all off the copper of its net's pads. A track wider than its class's width,
    a power path widened where there is room, is never a narrowing.
    """
    narrow = [copper for copper in layout.copper if copper.net in widths and copper.width < widths[copper.net] - 1e-6]
    groups: List[List[Copper]] = []
    for copper in narrow:
        joined = [group for group in groups if any(
            other.net == copper.net and other.layer == copper.layer
            and min(math.dist(a, b) for a in (copper.start, copper.end) for b in (other.start, other.end)) <= TOUCH
            for other in group)]
        merged = [copper] + [item for group in joined for item in group]
        groups = [group for group in groups if group not in joined] + [merged]
    found = []
    for group in groups:
        length = sum(off_pads(layout, copper) for copper in group)
        at_pad = any(layout.reached(copper, end) for copper in group for end in (copper.start, copper.end))
        if at_pad and length <= neck + 1e-6:
            continue
        copper = min(group, key=lambda item: (item.start, item.end))
        width = widths[copper.net]
        found.append(Violation(design.project, "workmanship_width", f"net {copper.net}: {copper.place()}",
                               f"WORK-8 one track width for each net class along a route: the track is "
                               f"{min(item.width for item in group):g} mm wide, narrower than its net class's "
                               f"{width:g} mm, along {length:.2f} mm of route off its pads "
                               + ("that reaches no pad" if not at_pad else "from the pad it enters")
                               + f", where WORK_NECK_MM allows a narrower track only within {neck:g} mm of a pad; "
                                 "draw it at its class's width"))
    return found


def unsized_pads(design: Design, layout: Layout) -> List[Violation]:
    """Every pad tracks of its net reach a layer of, whose copper the contact rule cannot size, so the measures that ask
    whether a track meets it cannot be made."""
    return [Violation(design.project, "workmanship_pad_copper",
                      f"net {pad.net}: {pad.name()} at ({coordinate(pad.centre[0])}, {coordinate(pad.centre[1])}) mm",
                      f"WORK-4, WORK-8 and WORK-10 cannot be measured at {pad.name()}: {pad.unsized}, and the "
                      f"check sizes a pad's copper only as a circle, an oval, a rectangle or a rounded rectangle, so it "
                      f"cannot tell whether a track of {pad.net} meets it; give the pad one of those shapes")
            for pad in layout.unsized]


def measured(design: Design, layout: Layout, figures: Dict[str, float], corner: Optional[float]) -> List[Violation]:
    """Every measured workmanship rule but the width rule, which needs the nets' classes, each whose figure the design sets.

    `corner` is the corner rule's minimum, which two tracks meeting at a pad are held to.
    """
    found = unsized_pads(design, layout)
    if "WORK_PAD_ANGLE_DEG" in figures:
        found += pad_corners(design, layout, corner, figures["WORK_PAD_ANGLE_DEG"])
    if "WORK_DETOUR_RATIO" in figures:
        found += detours(design, layout, figures["WORK_DETOUR_RATIO"])
    if "WORK_ANGLE_TOLERANCE_DEG" in figures:
        found += directions(design, layout, figures["WORK_ANGLE_TOLERANCE_DEG"])
        if "WORK_PAD_ENTRY_RATIO" in figures:
            found += pad_entries(design, layout, figures["WORK_PAD_ENTRY_RATIO"], figures["WORK_ANGLE_TOLERANCE_DEG"])
    return found


def class_widths(project: dict) -> Tuple[Dict[str, Tuple[float, float]], List[str]]:
    """Each net class's (priority, track width) from the project file, and every class whose width cannot be read.

    A class that leaves its track width out, or writes it null, takes the
    Default class's, as KiCad gives it; one that writes anything but a positive
    number of millimetres is named, as is a Default class with no width. A
    class with no priority ranks below every class that has one.
    """
    given: Dict[str, Tuple[float, Optional[float]]] = {}
    unreadable = []
    for netclass in setting(project, "net_settings", "classes") or []:
        if not isinstance(netclass, dict) or not isinstance(netclass.get("name"), str):
            continue
        priority = netclass.get("priority")
        rank = float(priority) if isinstance(priority, (int, float)) and not isinstance(priority, bool) else math.inf
        width = netclass.get("track_width")
        if width is None:
            given[netclass["name"]] = (rank, None)
        elif positive_number(width):
            given[netclass["name"]] = (rank, float(width))
        else:
            unreadable.append(netclass["name"])
    default = given.get("Default", (math.inf, None))[1]
    if default is None and "Default" not in unreadable:
        unreadable.append("Default")
    widths = {name: (rank, width if width is not None else default) for name, (rank, width) in given.items()}
    return {name: (rank, width) for name, (rank, width) in widths.items() if width is not None}, unreadable


def net_widths(nets: Set[str], members: Dict[str, Set[str]], widths: Dict[str, Tuple[float, float]]) -> Dict[str, float]:
    """Each net's class track width, as KiCad resolves it.

    A net KiCad places in several classes takes the width of the one ranked
    first, the lowest priority number; a net in none takes the Default class's.
    """
    found = {}
    for net in nets:
        held = sorted((widths[name][0], name) for name, inside in members.items() if net in inside and name in widths)
        if held:
            found[net] = widths[held[0][1]][1]
        elif "Default" in widths:
            found[net] = widths["Default"][1]
    return found


# --- Barriers, paste and pours ---------------------------------------------------
#
# Three more rules KiCad does not measure, each read from the layout file as
# copper on the board. None is held to a figure of the check's own: the barrier
# and the paste are held to an area the design sets as a project text variable
# (see MEASURED), and the pour gap to the board's own minimum clearance. The
# barrier and the pour gap read the fills of the layout as KiCad has just
# refilled them, never as the file was committed, since a committed fill may be
# out of date.


#: How much more than its figure, in mm squared, an area may be measured to be and still meet it: far under
#: anything drawn, over the error of an area found by polygons.
AREA = 1e-6

#: How much a gap may fall short of the board's minimum clearance, in mm, and
#: still meet it: the nanometre KiCad rounds a coordinate to.
ROUNDING = 1e-6


def zone_fills(tree: list) -> List[Tuple[str, str, List[board_geometry.Point]]]:
    """Every fill a layout holds, as (the zone's net, the layer it is on, the corners of its outline).

    KiCad writes each fill as one outline per polygon, any holes joined into it
    by a bridge of no width, so a point is inside it by the even-odd rule. A
    zone with no net is a rule area and carries no fill. A fill written in any
    other form raises Unreadable.
    """
    table = board_geometry.net_table(tree)
    found = []
    for zone in sexpr.children(tree, "zone"):
        net = board_geometry.item_net(zone, table, "a zone of the layout")
        if not net:
            continue
        for fill in sexpr.children(zone, "filled_polygon"):
            layer, points = sexpr.child(fill, "layer"), sexpr.child(fill, "pts")
            what = f"a fill of the zone of {net}"
            if layer is None or len(layer) < 2 or points is None:
                raise board_geometry.Unreadable(f"{what} has no layer or no corners where KiCad writes them")
            if any(sexpr.head(corner) != "xy" for corner in points[1:]) or len(points) < 4:
                raise board_geometry.Unreadable(f"{what} is {sexpr.dump(points)[:60]}, not a run of (xy ...) corners")
            found.append((net, str(layer[1]), [board_geometry.xy(corner, what) for corner in points[1:]]))
    return found


def copper_layers(tree: list) -> List[str]:
    """The copper layers of a layout in the order KiCad stacks them, front to back; the two outer ones where it names none."""
    named = [str(entry[1]) for entry in (sexpr.child(tree, "layers") or [])[1:]
             if isinstance(entry, list) and len(entry) > 1 and str(entry[1]).endswith(".Cu")]
    if not named:
        return ["F.Cu", "B.Cu"]
    inner = sorted((name for name in named if name not in ("F.Cu", "B.Cu")), key=lambda name: (len(name), name))
    return [name for name in ["F.Cu"] if name in named] + inner + [name for name in ["B.Cu"] if name in named]


class Via:
    """One via on the layout: its net, centre, size and drill, and the copper layers its hole joins."""

    def __init__(self, net: str, centre, size: float, drill: float, layers: Sequence[str]):
        self.net, self.centre, self.size, self.drill, self.layers = net, centre, size, drill, tuple(layers)

    def place(self) -> str:
        return f"via at ({coordinate(self.centre[0])}, {coordinate(self.centre[1])}) mm"


def board_vias(tree: list, stack: Sequence[str]) -> List[Via]:
    """Every via on the layout, the copper layers of `stack` between the two it names as the ones it joins."""
    table = board_geometry.net_table(tree)
    found = []
    for node in sexpr.children(tree, "via"):
        what = "a via of the layout"
        size, drill = sexpr.child(node, "size"), sexpr.child(node, "drill")
        ends = [stack.index(str(name)) for name in (sexpr.child(node, "layers") or [])[1:] if str(name) in stack]
        found.append(Via(board_geometry.item_net(node, table, what), board_geometry.xy(sexpr.child(node, "at"), what),
                         board_geometry.number(size, 1, what) if size is not None else 0.0,
                         board_geometry.number(drill, 1, what) if drill is not None else 0.0,
                         stack[min(ends):max(ends) + 1] if ends else stack))
    return found


class Piece:
    """One piece of copper on the layout: what it is, its net, the layers it is on, and its outline as polygons."""

    def __init__(self, kind: str, net: str, layers: Sequence[str], polygons: List[board_geometry.Polygon]):
        self.kind, self.net, self.layers, self.polygons = kind, net, tuple(layers), polygons
        points = [point for polygon in polygons for point in polygon]
        self.bounds = (min(x for x, _ in points), min(y for _, y in points),
                       max(x for x, _ in points), max(y for _, y in points)) if points else (0.0, 0.0, 0.0, 0.0)


def copper_pieces(tree: list, stack: Sequence[str], pads: Sequence[board_geometry.Pad], fills) -> List[Piece]:
    """Every track, arc, via, pad and fill of a layout as a piece of copper with its outline on the board."""
    found = []
    for copper in Layout(tree).copper:
        found.append(Piece(copper.kind(), copper.net, [copper.layer], board_geometry.swept(copper.points(), copper.width)))
    for via in board_vias(tree, stack):
        found.append(Piece("via", via.net, via.layers, [board_geometry.disc(via.centre, via.size / 2)]))
    for pad in pads:
        found.append(Piece("pad", pad.net, [layer for layer in stack if pad.on(layer)], [pad.outline()]))
    for net, layer, polygon in fills:
        found.append(Piece("zone fill", net, [layer], [polygon]))
    return found


def barrier_strip(inside: Sequence[board_geometry.Pad], outside: Sequence[board_geometry.Pad]
                  ) -> Optional[Tuple[float, float, float, float]]:
    """The rectangle between two groups of pads, as (left, top, right, bottom), or None where their boxes overlap on both axes.

    Each group is the box about its pads' full sizes. Where the groups are
    apart along x the strip runs from the inner edge of one to the inner edge
    of the other over the extent of both along y; otherwise, where they are
    apart along y, the same turned the other way.
    """
    first = [pad.box() for pad in inside]
    second = [pad.box() for pad in outside]
    a = (min(b[0] for b in first), min(b[1] for b in first), max(b[2] for b in first), max(b[3] for b in first))
    b = (min(b[0] for b in second), min(b[1] for b in second), max(b[2] for b in second), max(b[3] for b in second))
    left, top, right, bottom = min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])
    if a[2] <= b[0]:
        return a[2], top, b[0], bottom
    if b[2] <= a[0]:
        return b[2], top, a[0], bottom
    if a[3] <= b[1]:
        return left, a[3], right, b[1]
    if b[3] <= a[1]:
        return left, b[3], right, a[1]
    return None


def pad_numbers(pads: Sequence[board_geometry.Pad]) -> str:
    numbers = ", ".join(pad.number or "(unnumbered)" for pad in pads)
    return f"pad{'s' if len(pads) > 1 else ''} {numbers}"


def mains_barrier(design: Design, tree: list, fills, mains: Set[str], allowed: float) -> List[Violation]:
    """Every piece of copper under a part that bridges the barrier between the Mains net class and the rest of the board.

    A part with a pad on a Mains-class net and a pad on another net crosses
    the barrier the separation rule holds, and under it, between the two
    groups of pads, no more than `allowed` mm squared of copper may lie, summed
    over its layers: a track, an arc, a via, a pad or a pour's fill, so no
    creepage path runs under the part. The strip between the groups is
    measured as board_check.barrier_strip gives it. A part whose copper in it
    is more than `allowed` fails once for each kind of copper of one net on one
    layer that has area in it, naming that area and the part's total. The
    copper of the pads that define the two groups is the strip's edges and is
    not in it. A part with Mains-class pads and pads of no Mains class that
    cannot be measured fails by name: one whose two groups' boxes overlap along
    both axes, so no strip lies between them, or whose pads off the class have
    no net, so it is not known to bridge. `fills` are the layout's fills as KiCad
    has refilled them.
    """
    table = board_geometry.net_table(tree)
    parts = []
    every = []
    found = []
    for footprint in sexpr.children(tree, "footprint"):
        placed = board_geometry.footprint_pads(footprint, table)
        every += placed
        inside = [pad for pad in placed if pad.net in mains]
        outside = [pad for pad in placed if pad.net and pad.net not in mains]
        unnetted = [pad for pad in placed if not pad.net]
        if not inside or not (outside or unnetted):
            continue
        reason, strip = "", None
        if not outside:
            outside = unnetted
            reason = (f"its only pads off the Mains class, {pad_numbers(unnetted)}, have no net, so whether it bridges "
                      "the barrier is not known")
        else:
            strip = barrier_strip(inside, outside)
            if strip is None:
                reason = "the boxes of its two groups of pads overlap along both axes, so no strip lies between them"
        if reason:
            name = board_geometry.reference(footprint) or "?"
            at = board_geometry.placement(footprint, f"the footprint {name}")
            found.append(Violation(
                design.project, "mains_barrier", f"{name} at ({coordinate(at[0])}, {coordinate(at[1])}) mm: barrier not measurable",
                f"{name} has Mains-class {', '.join(sorted({pad.net for pad in inside}))} ({pad_numbers(inside)}) and other "
                f"pads ({pad_numbers(outside)}), and the copper between them cannot be measured: {reason}; the barrier "
                "rule does not support such a part, so use a part whose Mains-class pads lie apart from its other pads "
                "along one axis, with every pad that is not Mains-class on a net"))
            continue
        parts.append((footprint, inside, outside, strip))
    if not parts:
        return found
    stack = copper_layers(tree)
    pieces = copper_pieces(tree, stack, every, fills)
    for footprint, inside, outside, strip in parts:
        name = board_geometry.reference(footprint) or "?"
        left, top, right, bottom = strip
        lying: Dict[Tuple[int, str, str, str], Tuple[float, int, Tuple[float, float]]] = {}
        for piece in pieces:
            if piece.bounds[2] <= left or piece.bounds[0] >= right or piece.bounds[3] <= top or piece.bounds[1] >= bottom:
                continue
            area, where = 0.0, None
            for polygon in piece.polygons:
                clipped = board_geometry.clip_to_box(polygon, strip)
                share = board_geometry.polygon_area(clipped) if len(clipped) > 2 else 0.0
                if share > 0 and where is None:
                    where = (sum(x for x, _ in clipped) / len(clipped), sum(y for _, y in clipped) / len(clipped))
                area += share
            if area <= AREA:
                continue
            for layer in piece.layers:
                key = (stack.index(layer) if layer in stack else len(stack), layer, piece.net, piece.kind)
                total, count, first = lying.get(key, (0.0, 0, where))
                lying[key] = (total + area, count + 1, first)
        total = sum(area for area, _, _ in lying.values())
        if total <= allowed + AREA:
            continue
        at = board_geometry.placement(footprint, f"the footprint {name}")
        for (_, layer, net, kind), (area, count, first) in sorted(lying.items()):
            what = f"{count} {kind}s" if count > 1 else f"a {kind}"
            found.append(Violation(
                design.project, "mains_barrier",
                f"{name} at ({coordinate(at[0])}, {coordinate(at[1])}) mm: {kind} of {net or '(no net)'} on {layer}",
                f"{name} joins Mains-class {', '.join(sorted({pad.net for pad in inside}))} ({pad_numbers(inside)}) to "
                f"{', '.join(sorted({pad.net for pad in outside}))} ({pad_numbers(outside)}), and {what} of "
                f"{('net ' + net) if net else 'no net'} on {layer} {'lie' if count > 1 else 'lies'} under it between them: {area:.3f} square mm inside "
                f"the strip from ({coordinate(left)}, {coordinate(top)}) to ({coordinate(right)}, {coordinate(bottom)}) mm, "
                f"near ({coordinate(first[0])}, {coordinate(first[1])}) mm; the part has {total:.3f} square mm of copper "
                f"between its Mains-class pads and its other pads, over all layers, where BARRIER_COPPER_MM2 allows "
                f"{allowed:g}, so move the copper, and cut any pour back, clear of that strip"))
    return found


def first_written(*values: Optional[float]) -> float:
    """The first of the values a layout writes, or 0 where it writes none."""
    return next((value for value in values if value is not None), 0.0)


def written_number(node, keyword: str, what: str) -> Optional[float]:
    """The number a node writes under `keyword`, or None where it writes none."""
    found = sexpr.child(node, keyword) if node is not None else None
    return board_geometry.number(found, 1, what) if found is not None else None


def paste_openings(tree: list) -> List[Tuple[board_geometry.Pad, float]]:
    """Every pad that has solder paste, with how far its paste opening reaches beyond its copper on every side, in mm.

    The reach is the paste margin, the pad's own else its footprint's else the
    board's, plus the margin ratio, resolved the same way, times the pad's
    shorter side, as the layout writes them; with neither written it is 0.
    """
    table = board_geometry.net_table(tree)
    setup = sexpr.child(tree, "setup")
    found = []
    for footprint in sexpr.children(tree, "footprint"):
        what = f"a pad of the footprint {board_geometry.reference(footprint) or '?'}"
        for node, pad in zip(sexpr.children(footprint, "pad"), board_geometry.footprint_pads(footprint, table)):
            if "F.Paste" not in pad.layers and "B.Paste" not in pad.layers:
                continue
            margin = first_written(written_number(node, "solder_paste_margin", what),
                                   written_number(footprint, "solder_paste_margin", what),
                                   written_number(setup, "pad_to_paste_clearance", what))
            ratio = first_written(written_number(node, "solder_paste_margin_ratio", what),
                                  written_number(footprint, "solder_paste_margin_ratio", what),
                                  written_number(setup, "pad_to_paste_clearance_ratio", what))
            found.append((pad, margin + ratio * min(pad.size)))
    return found


def paste_over_vias(design: Design, tree: list, allowed: float) -> List[Violation]:
    """Every via whose hole a pad's solder paste opening covers more than `allowed` mm squared of, once for each opening.

    Paste printed over a via's hole runs down it and starves the joint, on
    whichever side the paste is, since the hole goes through. A pad's opening
    is its copper's shape grown (shrunk, where the reach is negative) on every
    side by the reach paste_openings gives, never to a negative size, and
    paste on a pad with no copper counts as it does on any other. The area is
    that of the hole, a circle, inside the opening. A pad with
    paste whose shape is not sized here cannot be measured and fails by name
    wherever the board has a via, rather than being guessed.
    """
    vias = [via for via in board_vias(tree, copper_layers(tree)) if via.drill > 0]
    found = []
    for pad, reach in paste_openings(tree) if vias else []:
        side = " and ".join(layer for layer in ("F.Paste", "B.Paste") if layer in pad.layers)
        where = f"{pad.name()} at ({coordinate(pad.centre[0])}, {coordinate(pad.centre[1])}) mm"
        if pad.unsized:
            found.append(Violation(design.project, "paste_via", f"net {pad.net or '(no net)'}: {where}",
                                   f"whether the {side} opening of {pad.name()} reaches a via's hole cannot be measured: "
                                   f"{pad.unsized}, and the check sizes a paste opening only for a circle, an oval, a "
                                   f"rectangle or a rounded rectangle; give the pad one of those shapes, or take its paste "
                                   f"layer off"))
            continue
        margin = (f"grown by {reach:g} mm on every side" if reach > 0 else
                  f"shrunk by {-reach:g} mm on every side" if reach < 0 else "with no paste margin")
        opening = pad.resized((max(pad.size[0] + 2 * reach, 0.0), max(pad.size[1] + 2 * reach, 0.0)))
        if min(opening.size) <= 0:
            continue
        for via in vias:
            radius = via.drill / 2
            if math.dist(pad.centre, via.centre) > math.hypot(*opening.size) / 2 + radius:
                continue
            covered = (board_geometry.overlap_area(board_geometry.disc(via.centre, radius, 360), opening.outline(64))
                       if opening.distance(via.centre) < radius else 0.0)
            if covered > allowed + AREA:
                found.append(Violation(
                    design.project, "paste_via",
                    f"net {via.net or '(no net)'}: {via.place()}, under the paste of {where}",
                    f"solder paste is printed over the hole of the {via.drill:g} mm {via.place()} of "
                    f"{('net ' + via.net) if via.net else 'no net'}: the {side} opening of {pad.name()} at "
                    f"({coordinate(pad.centre[0])}, {coordinate(pad.centre[1])}) mm, the pad's shape "
                    f"{margin}, covers {covered:.4f} square mm of the hole of {math.pi * radius ** 2:.4f}, where "
                    f"PASTE_OVER_VIA_MM2 allows {allowed:g}; paste in a via's hole runs through it and starves the joint, "
                    f"so move the via out from under the opening, or shrink the pad's paste until it clears the hole, or "
                    f"take the pad's paste layer off"))
    return found


def pour_gap_figure(design: Design, project: dict) -> Tuple[Optional[float], List[Violation]]:
    """The narrowest gap a pour may leave, the board's minimum clearance from its design rules, or why the project states none."""
    value = setting(project, "board", "design_settings", "rules", "min_clearance")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        said = "states none" if value is None else f"states {json.dumps(value)}"
        return None, [Violation(design.project, "pour_gap", f"{design.project} board.design_settings.rules.min_clearance",
                                f"MFG-6 pour gap has no figure: the project's board design rules {said} for min_clearance, "
                                "so the narrowest gap a pour may leave between its fill and copper of its own net cannot "
                                "be measured; set the minimum clearance in Board Setup to the manufacturer's figure")]
    return float(value), []


def track_gap(line: Sequence[board_geometry.Point], radius: float):
    """How far a track's copper, its centre line swept by `radius`, passes from a straight line from a to b."""
    return lambda a, b: max(min(board_geometry.segment_distance(p, q, a, b) for p, q in zip(line, line[1:])) - radius, 0.0)


def via_gap(via: Via):
    """How far a via's copper passes from a straight line from a to b."""
    return lambda a, b: max(board_geometry.distance_to_segment(via.centre, a, b) - via.size / 2, 0.0)


def pour_gaps(design: Design, tree: list, fills, minimum: float) -> List[Violation]:
    """Every gap narrower than `minimum` between a pour's fill and copper of the pour's own net that the fill stops short of.

    KiCad's clearance check compares no copper of one net, so a pour whose
    fill stops a hair short of a track, via or pad of its own net, at the edge
    of a rule area or the board's outline, leaves a slot it never reports,
    which can close or leave a sliver when etched. Copper on the fill's net and
    layer, a via on every layer it joins, is touched by a fill when its centre
    is inside the outline by the even-odd rule or the nearest its copper comes
    to the outline is within TOUCH, and passes; otherwise the nearest it comes,
    its edge to the outline, must be at least `minimum`. A pad whose copper is
    not sized is taken as the box of its full size.
    """
    stack = copper_layers(tree)
    items = []
    for copper in Layout(tree).copper:
        items.append((copper.net, [copper.layer], copper.start, copper.points(), copper.width / 2,
                      track_gap(copper.points(), copper.width / 2),
                      f"{copper.kind()} from ({coordinate(copper.start[0])}, {coordinate(copper.start[1])}) to "
                      f"({coordinate(copper.end[0])}, {coordinate(copper.end[1])}) mm"))
    for via in board_vias(tree, stack):
        items.append((via.net, via.layers, via.centre, [via.centre], via.size / 2, via_gap(via), via.place()))
    for pad in board_geometry.pads(tree):
        if pad.net:
            solid = pad if pad.sized() else pad.resized(pad.size, "rect")
            items.append((pad.net, [layer for layer in stack if pad.on(layer)], pad.centre, solid.outline(), 0.0,
                          solid.distance_to_line,
                          f"{pad.name()} at ({coordinate(pad.centre[0])}, {coordinate(pad.centre[1])}) mm"))
    found = []
    for net, layer, outline in fills:
        edges = list(zip(outline, outline[1:] + outline[:1]))
        reach = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])) for a, b in edges]
        xs, ys = [point[0] for point in outline], [point[1] for point in outline]
        island = (f"({coordinate(min(xs))}, {coordinate(min(ys))}) to ({coordinate(max(xs))}, {coordinate(max(ys))}) mm")
        for item_net, layers, centre, line, radius, gap, place in items:
            if item_net != net or layer not in layers:
                continue
            near = (min(x for x, _ in line) - radius - minimum, min(y for _, y in line) - radius - minimum,
                    max(x for x, _ in line) + radius + minimum, max(y for _, y in line) + radius + minimum)
            close = [edge for edge, box in zip(edges, reach)
                     if box[0] <= near[2] and box[2] >= near[0] and box[1] <= near[3] and box[3] >= near[1]]
            if not close or board_geometry.within(centre, outline):
                continue
            narrowest = min(gap(a, b) for a, b in close)
            if TOUCH < narrowest < minimum - ROUNDING:
                found.append(Violation(
                    design.project, "pour_gap", f"net {net}: {place} on {layer}",
                    f"MFG-6 pour gap: the pour of {net} on {layer} (a fill spanning {island}) stops {narrowest:.3f} mm "
                    f"short of {place}, copper of its own net, narrower than the board's {minimum:g} mm minimum clearance; "
                    "KiCad's clearance check compares no copper of one net, so it never reports a gap this narrow, yet it "
                    "can close or leave a sliver when etched; draw the copper into the pour, or move it at least "
                    f"{minimum:g} mm clear of the fill's edge, or let the pour reach it by moving the rule area or the "
                    "outline edge that holds the fill back"))
    return found


# --- Running KiCad ------------------------------------------------------------


def appended_rules(signed: Optional[Tuple[float, float]], nonce: str, net: Optional[str] = None) -> str:
    """The rules added after the design's own on the temporary copy, the signed one after the marker.

    Rules the check writes after the signed one can only tighten it: they hold
    other constraint types, or a clearance no less than the signed figure.

    The marker matches the items of `net`, or every item when no net is given,
    so its absence from KiCad's report shows KiCad did not load the rules file
    at all. It is an assertion, which KiCad evaluates for every matching rule
    rather than letting a later one replace an earlier, so it changes nothing
    any other rule enforces. Matching one net's items keeps its failures few,
    since KiCad reports only REPORT_LIMIT assertion failures and drops the
    rest at random; a marker on every item of a large board would crowd the
    design's own assertion failures out of the report. It is named for this run
    alone, from `nonce`, so no rule a design writes can pass for it and have its
    own findings taken for the check's.
    """
    text = "\n" + marker(nonce, EVERY_ITEM if net is None else f"A.NetName == '{net}'")
    if signed is not None:
        text += (f'(rule "{SIGNED_RULE}"\n\t(condition "{MAINS_CONDITION}")\n'
                 f'\t(constraint clearance (min {signed[0]:g}mm))\n\t(constraint creepage (min {signed[1]:g}mm)))\n')
    return text


#: The marker's condition when it is to fire on every item.
EVERY_ITEM = "A.Type != ''"


def marker(nonce: str, condition: str = EVERY_ITEM) -> str:
    return f'(rule "{marker_rule(nonce)}"\n\t(condition "{condition}")\n\t(constraint assertion "false"))\n'


def class_probe(nonce: str, netclass: str) -> str:
    """The assertion KiCad fails for every item it places in `netclass`, however the class was given."""
    return (f'(rule "{probe_rule(nonce, netclass)}"\n\t(condition "A.hasNetclass(\'{netclass}\')")\n'
            '\t(constraint assertion "false"))\n')


def fired(report: dict, rule: str) -> List[dict]:
    """The assertion failures KiCad reports for one of the check's own rules."""
    return [entry for entry in assertions(report) if f"(rule '{rule}')" in entry.get("description", "")]


def assertions(report: dict) -> List[dict]:
    """Every assertion failure KiCad reports, whichever rule it is of."""
    return [entry for entry in report.get("violations") or [] if entry.get("type") == "assertion_failure"]


def cut_short(report: dict) -> bool:
    """Whether KiCad's report holds as many assertion failures as it reports, so it may be missing more."""
    return len(assertions(report)) >= REPORT_LIMIT


def run_kicad(command: List[str], cwd: str, output: str = "report.json") -> Tuple[Optional[str], str]:
    """The text of the report a KiCad command writes to `output`, or why there is none."""
    output = os.path.join(cwd, output)
    if os.path.exists(output):
        os.remove(output)
    try:
        result = subprocess.run(command + ["-o", output], cwd=cwd, capture_output=True, text=True,
                                timeout=KICAD_TIMEOUT_S, env=KICAD_ENVIRONMENT)
    except subprocess.TimeoutExpired:
        return None, f"KiCad did not finish within {KICAD_TIMEOUT_S} s"
    said = " ".join((result.stdout + " " + result.stderr).split())
    if result.returncode != 0 or not os.path.exists(output):
        return None, f"KiCad could not open it (exit {result.returncode}: {said[:300]})"
    with open(output, encoding="utf-8", errors="replace") as handle:
        return handle.read(), ""


def run_report(command: List[str], cwd: str) -> Tuple[Optional[dict], str]:
    """KiCad's JSON report for a rule check, or why there is none."""
    text, why = run_kicad(command, cwd)
    if text is None:
        return None, why
    try:
        return json.loads(text), ""
    except ValueError as error:
        return None, f"KiCad's report could not be read ({error})"


def coordinate(value: float) -> str:
    return ("%.4f" % value).rstrip("0").rstrip(".")


def item_text(item: dict) -> str:
    pos = item.get("pos") or {}
    where = ""
    if "x" in pos and "y" in pos:
        where = f" @ ({coordinate(pos['x'])}, {coordinate(pos['y'])}) mm"
    return f"{item.get('description', '?')}{where}"


def kicad_violation(design: Design, entry: dict, fallback: str, sheet: str = "") -> Violation:
    items = entry.get("items") or []
    location = "; ".join(item_text(item) for item in items) or fallback
    if sheet and sheet != "/":
        location = f"sheet {sheet}: {location}"
    message = entry.get("description", "")
    rule = entry.get("type", "unknown")
    if rule in ("lib_symbol_issues", "lib_footprint_issues") and "does not include" in message:
        rule = "design_library"
        message += ("; KiCad is run with the design's own library tables and the libraries it installs with itself, "
                    "and nothing else, so a library only one machine's own tables name is not one a reader has: "
                    "put the library in the repository and name it in the design's own table through ${KIPRJMOD}")
    if rule in KICAD_WORKMANSHIP:
        message += f" (workmanship item {KICAD_WORKMANSHIP[rule]})"
    if entry.get("severity") == "exclusion":
        message += " (the design marks this violation as excluded; an excluded violation still fails the check, so fix it)"
    return Violation(design.project, rule, location, message)


def ignored(design: Design, report: dict, setting: str) -> List[Violation]:
    return [Violation(design.project, "ignored_check", f"{design.project} {setting}.{entry.get('key', '?')}",
                      f"{entry.get('description', entry.get('key', '?'))}: the project sets this check to ignore, "
                      "whether or not that is KiCad's own default, so KiCad did not run it; set it to error or warning")
            for entry in report.get("ignored_checks") or []]


def exclusions(design: Design, project: dict) -> List[Violation]:
    """Violations the project file marks as excluded, each a failure whatever KiCad makes of the entry."""
    found = []
    lists = (
        setting(project, "board", "design_settings", "drc_exclusions") or [],
        setting(project, "erc", "erc_exclusions") or [],
    )
    for entries, file_, scale in ((lists[0], design.layout, 1e-6), (lists[1], design.schematic, 1e-4)):
        for entry in entries:
            key = entry[0] if isinstance(entry, list) and entry else entry
            parts = str(key).split("|")
            location = file_
            if len(parts) > 2:
                try:
                    location = f"{file_} @ ({coordinate(int(parts[1]) * scale)}, {coordinate(int(parts[2]) * scale)}) mm"
                except ValueError:
                    pass
            found.append(Violation(
                design.project, parts[0] or "unknown", location,
                "the design marks this violation as excluded in its project file; an excluded violation still "
                f"fails the check, so fix it and remove the exclusion ({key})"))
    return found


def layout_nets(layout: list) -> Set[str]:
    """Every net name the layout's items carry."""
    return {net_of(["item", node]) for node in walk(layout, "net") if len(node) > 1} - {""}


def probed_nets(probe: List[dict], names: Set[str]) -> Set[str]:
    """The nets of the items KiCad's probe reports, matched against the layout's own net names.

    KiCad writes an item's net between square brackets, and a net name may
    itself hold a bracket, so the name is found as the longest of the layout's
    names that the description carries in brackets rather than read up to the
    first closing one.
    """
    nets = set()
    for entry in probe:
        for item in entry.get("items") or []:
            description = item.get("description", "")
            carried = [name for name in names if f"[{name}]" in description]
            if carried:
                nets.add(max(carried, key=len))
            else:
                match = re.search(r"\[(.*)\]", description)
                if match:
                    nets.add(match.group(1))
    return nets


def schematic_nets(netlist: list) -> Dict[str, Tuple[List[str], List[str]]]:
    """Every net in KiCad's own netlist of the schematic: name -> (its net classes, the pins it joins)."""
    nets = {}
    for group in walk(netlist, "nets"):
        for net in sexpr.children(group, "net"):
            name, kind = sexpr.child(net, "name"), sexpr.child(net, "class")
            if name is None or len(name) < 2:
                continue
            classes = [part.strip() for part in str(kind[1]).split(",")] if kind is not None and len(kind) > 1 else []
            pins = []
            for node in sexpr.children(net, "node"):
                ref, pin = sexpr.child(node, "ref"), sexpr.child(node, "pin")
                if ref is not None and len(ref) > 1:
                    pins.append(f"{ref[1]} pin {pin[1]}" if pin is not None and len(pin) > 1 else str(ref[1]))
            nets[str(name[1])] = (classes, pins)
    return nets


def tool_named_nets(design: Design, nets: Dict[str, Tuple[List[str], List[str]]]) -> List[Violation]:
    """Every net KiCad named itself because the designer left it unnamed; a pin nothing joins is not a net and is exempt."""
    found = []
    for name in sorted(nets):
        if not GENERATED_NET.search(name) or name.rsplit("/", 1)[-1].startswith(UNCONNECTED_NET):
            continue
        found.append(Violation(
            design.project, "tool_named_net", design.schematic,
            f"the net {name} carries a name KiCad generated, so a reader following the schematic by its nets "
            f"is told nothing; name it with a net label that says what it carries ({', '.join(nets[name][1][:3]) or 'no pins'})"))
    return found


def schematic_mains(nets: Dict[str, Tuple[List[str], List[str]]]) -> Set[str]:
    """The nets KiCad's own netlist of the schematic puts in the Mains class, wherever the schematic says so."""
    return {name for name, (classes, _) in nets.items() if "Mains" in classes}


def quoted(text: str) -> str:
    """A string as KiCad's files write one between double quotes."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def project_mains(kicad_cli: str, scratch: str, project: str, names: Set[str], nonce: str,
                  version: str = "20260206") -> Tuple[Optional[Set[str]], str]:
    """The nets of `names` the project file's own net settings put in the Mains class, as KiCad resolves them.

    The project file assigns nets to classes by name and by pattern, and KiCad
    applies both to the layout, so the layout's membership alone cannot show
    what the project file says: the layout file can carry classes of its own,
    and a net the project names may have no copper. KiCad is therefore asked
    through class_members with the project file alone, carrying none of the
    layout's own classes, for every net name given. The boards are written in
    `version`, the file format of the design's own layout, which the installed
    KiCad has already opened.
    """
    members, why = class_members(kicad_cli, scratch, project, ["Mains"], names, nonce, version)
    if members is None:
        return None, why
    return members["Mains"], ""


#: Why class_members has no answer when KiCad ran but did not load its rules file.
PROBES_NOT_LOADED = "KiCad did not load the rules that ask it which nets are in which net class"


def layout_version(layout: list) -> str:
    """The file format a layout is written in, which the installed KiCad has opened it in."""
    version = sexpr.child(layout, "version")
    return str(version[1]) if version is not None and len(version) > 1 else "20260206"


def class_blocks(layout: list) -> List[list]:
    """The (net_class ...) blocks a layout file carries itself, which older KiCad versions wrote and KiCad 10 honours."""
    return sexpr.children(layout, "net_class")


def class_batches(names: Set[str], classes: Sequence[str]) -> List[List[str]]:
    """`names`, in batches small enough that one run's assertion failures stay below KiCad's report limit.

    One run reports the marker once and each net of its batch at most once per
    class, so a batch of n nets read for k classes reports at most 1 + n * k
    failures, and n is the most that keeps that below REPORT_LIMIT.
    """
    size = max(1, (REPORT_LIMIT - 2) // max(1, len(classes)))
    ordered = sorted(names)
    return [ordered[start:start + size] for start in range(0, len(ordered), size)]


def batch_members(report: dict, classes: Sequence[str], names: Set[str], nonce: str
                  ) -> Tuple[Optional[Dict[str, Set[str]]], str]:
    """The nets of `names` KiCad's report of one class run places in each of `classes`, or why it cannot be read.

    A report holding as many assertion failures as KiCad reports may have
    dropped any number more, the marker's or any class's, so it is refused
    rather than read as complete; a correct batching never reaches it.
    """
    if cut_short(report):
        return None, (f"KiCad's report while reading which nets are in {', '.join(classes)} reached its limit of "
                      f"{REPORT_LIMIT} failures of one kind, so it may leave out nets of "
                      f"{'that class' if len(classes) == 1 else 'those classes'} and is not read as complete")
    if not fired(report, marker_rule(nonce)):
        return None, PROBES_NOT_LOADED
    return {netclass: probed_nets(fired(report, probe_rule(nonce, netclass)), names) for netclass in classes}, ""


def merged(answers: List[Dict[str, Set[str]]], classes: Sequence[str]) -> Dict[str, Set[str]]:
    """Each class's nets across every batch's answer."""
    return {netclass: set().union(*(answer[netclass] for answer in answers)) for netclass in classes}


def class_members(kicad_cli: str, scratch: str, project: str, classes: Sequence[str], names: Set[str], nonce: str,
                  version: str, blocks: Sequence[list] = ()) -> Tuple[Optional[Dict[str, Set[str]]], str]:
    """The nets of `names` KiCad places in each of `classes`, opened with the project file `project`.

    KiCad is asked on boards of nothing but one track per net name, written in
    a folder of their own in `scratch` in the file format `version`, each opened
    with a copy of the project file and carrying `blocks`, the (net_class ...)
    blocks of the layout whose classes are wanted. So KiCad applies the project
    file's assignments and patterns and any class the layout file carries,
    exactly as it would on the layout itself. Each board's layout check runs
    with a marker and one probe per class: the marker fires on the one track
    laid on the back copper, showing the rules were loaded, so an empty answer
    means no net rather than an unread rules file; each probe fires on every
    track KiCad places in its class. A board of one track per net reports each
    net once per class however much copper the net carries on the layout, and
    the nets are split into batches small enough that no run reaches KiCad's
    report limit, so the answer is the whole of each class on every run, on a
    board of any size. The batches' answers are merged.
    """
    work = tempfile.mkdtemp(prefix="classes-", dir=scratch)
    shutil.copy2(project, os.path.join(work, "classes.kicad_pro"))
    with open(os.path.join(work, "classes.kicad_dru"), "w", encoding="utf-8") as handle:
        handle.write("(version 1)\n" + marker(nonce, "A.Layer == 'B.Cu'")
                     + "".join(class_probe(nonce, netclass) for netclass in classes))
    carried = "".join(f"\t{sexpr.dump(block)}\n" for block in blocks)
    answers = []
    for batch in class_batches(names, classes):
        tracks = "".join(
            f'\t(segment (start 0 {2 * index}) (end 1 {2 * index}) (width 0.1) '
            f'(layer "{"B.Cu" if index == 0 else "F.Cu"}") (net {quoted(name)}) '
            f'(uuid "00000000-0000-4000-8000-{index:012d}"))\n'
            for index, name in enumerate(batch))
        with open(os.path.join(work, "classes.kicad_pcb"), "w", encoding="utf-8") as handle:
            handle.write(f'(kicad_pcb\n\t(version {version})\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
                         '\t(general (thickness 1.6))\n\t(paper "A4")\n'
                         '\t(layers\n\t\t(0 "F.Cu" signal)\n\t\t(2 "B.Cu" signal)\n\t\t(25 "Edge.Cuts" user)\n\t)\n'
                         + carried + tracks + ")\n")
        report, why = run_report([kicad_cli, "pcb", "drc", "--format", "json", "--severity-all", "classes.kicad_pcb"],
                                 work)
        if report is None:
            return None, why
        answer, why = batch_members(report, classes, set(batch), nonce)
        if answer is None:
            return None, why
        answers.append(answer)
    return merged(answers, classes), ""


#: Where each of the three statements of Mains membership is read from, in the
#: order a disagreement names them.
ON_LAYOUT, IN_SCHEMATIC, IN_PROJECT = "on the layout", "in the schematic", "in the project file's net settings"


def mains_agreement(design: Design, mains: Optional[str], sources: Dict[str, Set[str]],
                    locate: Dict[str, Dict[str, str]]) -> List[Violation]:
    """Every net the three statements of Mains membership do not all agree on.

    The layout's membership is the one the separation rule is enforced
    against, so a net any other source puts in Mains while the layout does not
    would carry mains with nothing holding low-voltage copper away from it,
    and a net only the layout puts there is one the design's own record of its
    mains nets does not know about. Neither is read past by taking the union:
    every source must name exactly the nets the others name.
    """
    found = []
    for net in sorted(set().union(*sources.values())):
        having = [place for place in (ON_LAYOUT, IN_SCHEMATIC, IN_PROJECT) if net in sources[place]]
        lacking = [place for place in (ON_LAYOUT, IN_SCHEMATIC, IN_PROJECT) if net not in sources[place]]
        if not lacking:
            continue
        where = next((locate[place][net] for place in having if net in locate.get(place, {})), "")
        fix = ("take it out of Mains wherever it is, or set MAINS to present" if mains == "none" else
               "assign it to Mains in the schematic, save the schematic so the project file carries the "
               "assignment, and update the layout from the schematic; or take it out of Mains in all three")
        if having == [ON_LAYOUT]:
            fix += ("; a class only the layout gives a net comes from a (net_class ...) block in the layout file "
                    "itself, which older KiCad versions wrote, so remove that block")
        found.append(Violation(
            design.project, "mains_class", f"net {net}" + (f": {where}" if where else ""),
            f"net {net} is in the Mains net class {' and '.join(having)} but not {' or '.join(lacking)}; the "
            "layout's Mains nets are the ones the separation rule is enforced against, so the schematic, the "
            f"project file and the layout must name exactly the same Mains nets: {fix}"))
    return found


def rejected_form(kicad_cli: str, copy: str, layout: str, rules_copy: str, text: str, nonce: str
                  ) -> Tuple[str, str]:
    """Which part of a rules file KiCad declines to load, as (where, what), found with KiCad alone.

    The design's file is put back together a form at a time after its header,
    each candidate followed by the marker, and KiCad's layout check run on it:
    the first form whose addition stops the marker firing is the one KiCad
    rejects. A bisection over the forms finds it in a handful of runs. When no
    one form can be named, what is said is why: the file cannot be split into
    forms at all, or every form loads and what KiCad rejects lies between them.
    """
    spans: List[Tuple[int, int, int]] = []
    try:
        forms = sexpr.parse(text, comments=True, spans=spans)
    except sexpr.SexprError as error:
        line = re.search(r"line (\d+)", str(error))
        return (f"at line {line.group(1)}" if line else "at its end",
                f"the file is not well-formed ({error}), so it cannot be split into rules to find the one KiCad "
                "rejects; balance its parentheses and close its quoted strings at that point")
    header = forms[0] if forms and sexpr.head(forms[0]) == "version" else None
    items = list(zip(forms, spans))[1 if header is not None else 0:]
    head_text = text[spans[0][0]:spans[0][1]] + "\n" if header is not None else ""

    def loads(count: int) -> bool:
        body = "".join(text[start:end] + "\n" for _, (start, end, _) in items[:count])
        with open(rules_copy, "w", encoding="utf-8") as handle:
            handle.write(head_text + body + "\n" + marker(nonce))
        report, _ = run_report([kicad_cli, "pcb", "drc", "--format", "json", "--severity-all", layout], copy)
        return report is not None and bool(fired(report, marker_rule(nonce)))

    if not loads(0):
        if header is None:
            return "the start of the file", "the file does not begin with a (version 1) header, without which KiCad loads none of it; add (version 1) as its first line"
        return f"the header at line {spans[0][2]}", f"its header {text[spans[0][0]:spans[0][1]]} is not one KiCad accepts; make it (version 1)"
    if loads(len(items)):
        return ("between its rules",
                "KiCad loads every form of the file once the comments and spacing between them are left out, so what "
                "it rejects lies there rather than in any one rule; KiCad reads a comment from a '#' to the end of "
                "its line, so correct or remove the comments between the rules")
    good, bad = 0, len(items)
    while bad - good > 1:
        middle = (good + bad) // 2
        if loads(middle):
            good = middle
        else:
            bad = middle
    form, (_, _, line) = items[bad - 1]
    if sexpr.head(form) == "rule":
        return (f"rule '{rule_name(form)}' at line {line}",
                f"KiCad loads every form before rule '{rule_name(form)}' and none of the file once it is added, so "
                "this is the rule it rejects: check its constraint names, units and condition expression against "
                "KiCad's custom rules syntax (the Custom Design Rules section of KiCad's PCB Editor manual)")
    return (f"the {sexpr.head(form) or 'bare'} form at line {line}",
            f"KiCad loads every form before this one and none of the file once it is added; a rules file holds only "
            "its (version 1) header and (rule ...) forms, so correct or remove it")


# --- The project file ----------------------------------------------------------


class DuplicateKey(ValueError):
    """A JSON object gives one key twice."""


def unique_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateKey(key)
        seen[key] = value
    return seen


def setting(project: dict, *path: str):
    """The project file's setting at `path`, or None where any step of it is absent."""
    value = project
    for step in path:
        if not isinstance(value, dict):
            return None
        value = value.get(step)
    return value


#: Each project-file setting the check reads itself, and the JSON type KiCad writes it as.
PROJECT_SETTINGS = (
    (("text_variables",), dict, "an object of text variables"),
    (("board", "design_settings", "drc_exclusions"), list, "a list of exclusions"),
    (("erc", "erc_exclusions"), list, "a list of exclusions"),
    (("net_settings", "netclass_assignments"), dict, "an object assigning nets to classes"),
    (("net_settings", "classes"), list, "a list of net classes"),
)


def project_form(design: Design, project: dict) -> List[Violation]:
    """Every setting the check reads from the project file that is not in the form KiCad writes it in.

    The check reads the project file's text variables, its exclusion lists and
    the net names its class assignments give, and reads each only in the form
    KiCad writes: each setting absent, null or of KiCad's own type, every text
    variable a string, and NOT_FOR_MANUFACTURE true or false. Anything else
    fails by name rather than being taken as absent.
    """
    found = []
    for path, kind, said in PROJECT_SETTINGS:
        value = setting(project, *path)
        if value is not None and not isinstance(value, kind):
            found.append(Violation(design.project, "project_file", f"{design.project} {'.'.join(path)}",
                                   f"{'.'.join(path)} is {json.dumps(value)[:80]}, where KiCad writes {said}; "
                                   "correct it, or let KiCad rewrite the project file by saving the design"))
    variables = setting(project, "text_variables")
    if isinstance(variables, dict):
        for name, value in sorted(variables.items()):
            if not isinstance(value, str):
                found.append(Violation(design.project, "project_file", f"{design.project} text_variables.{name}",
                                       f"the text variable {name} is {json.dumps(value)[:80]}, where KiCad writes "
                                       "every text variable as a string; write it as one"))
        marked = variables.get("NOT_FOR_MANUFACTURE")
        if isinstance(marked, str) and marked not in ("true", "false"):
            found.append(Violation(design.project, "project_file", f"{design.project} text_variables.NOT_FOR_MANUFACTURE",
                                   f"the project text variable NOT_FOR_MANUFACTURE is '{marked}'; set it to true on a "
                                   "design that is never to be ordered, and to false or leave it out otherwise"))
    return found


# --- Decoupling and silkscreen -------------------------------------------------------
#
# Three more rules KiCad does not measure, each read from the layout file. None
# needs a project text variable of its own, so none adds a figure to the
# designs: DECOUPLE-6, MFG-7 and MFG-9 are held to an inherent zero: no via in the
# decoupling path, no reference off the silkscreen, no designator inside a courtyard
# or nearer another part than its own.


def ground_nets(members: Dict[str, Set[str]]) -> Set[str]:
    """Every net in a ground net class."""
    return set().union(set(), *(inside for name, inside in members.items() if GROUND_CLASS.search(name)))


def decoupling_vias(design: Design, tree: list, ground: Set[str]) -> List[Violation]:
    """Every via standing between a decoupling part's supply pad and the pin of its circuit it decouples.

    The circuits and their decoupling parts are those of the review views
    (board_views.circuits): a circuit is a footprint whose reference begins
    with U, its supply nets those of its pads typed power input or power
    output, and a decoupling part a two-pad part across two of them, kept with
    the nearest such circuit. A part's supply pad is its pad not on a net of a
    ground net class (both pads when neither is, or both are), and the pin it
    decouples is the circuit's pad on the same net nearest that pad. The space
    between them is the box about the two pads' copper; a via on the pad's
    net whose centre lies in the box, or whose copper reaches into it, is a
    violation (a via of another net standing in the box is not in the
    capacitor's path). A board whose pads carry no pin types has no
    decoupling parts.
    """
    vias = board_vias(tree, copper_layers(tree))
    found = []
    for circuit, name, pad, pin in decoupling_paths(tree, ground)[1] if vias else []:
        boxes = (pad.box(), pin.box())
        left, top = min(box[0] for box in boxes), min(box[1] for box in boxes)
        right, bottom = max(box[2] for box in boxes), max(box[3] for box in boxes)
        for via in vias:
            if via.net != pad.net:
                continue
            reach = math.hypot(max(left - via.centre[0], 0.0, via.centre[0] - right),
                               max(top - via.centre[1], 0.0, via.centre[1] - bottom))
            if reach > via.size / 2:
                continue
            where = "in" if reach == 0 else f"{reach:.2f} mm off, its copper reaching into,"
            found.append(Violation(
                design.project, "decoupling_via",
                f"net {via.net or '(no net)'}: {via.place()}, between {pad.name()} and {pin.name()}",
                f"DECOUPLE-6 no via sits between a decoupling capacitor's supply pad and the pin it decouples: "
                f"{via.place()} of {('net ' + via.net) if via.net else 'no net'} lies {where} the box from "
                f"({coordinate(left)}, {coordinate(top)}) to ({coordinate(right)}, {coordinate(bottom)}) mm about "
                f"{pad.name()} of {pad.net} and {pin.name()}, the pin of {circuit} that {name} "
                "decouples; the capacitor's current would pass through the via, so move the via out of the way "
                "and join the capacitor's pad to the pin on the surface layer"))
    return found


def untyped_circuits(design: Design, tree: list, not_for_manufacture: bool) -> List[Violation]:
    """Every integrated circuit of an orderable board that has netted pads and none typed as a power pin.

    A circuit is a footprint whose reference begins with U, as
    board_views.circuits has it. Without a pad typed power input or power
    output it has no supply nets, so the decoupling rule finds no decoupling
    part for it and measures nothing, and the board would pass on that. A
    design marked not for manufacture is not refused, since the gate's proof
    design is such a board; its coverage line shows the paths measured. A
    circuit none of whose pads is on a net is not refused: it has no supply pad
    to decouple.
    """
    if not_for_manufacture:
        return []
    import board_views
    table = board_geometry.net_table(tree)
    found = []
    for footprint in sexpr.children(tree, "footprint"):
        name = board_geometry.reference(footprint)
        if not name.startswith("U"):
            continue
        held = board_views.pads(footprint, table)
        if any(net for net, _ in held) and not any(kind in ("power_in", "power_out") for _, kind in held):
            at = board_geometry.placement(footprint, f"the footprint {name}")
            found.append(Violation(
                design.project, "decoupling_pintype", f"{name} at ({coordinate(at[0])}, {coordinate(at[1])}) mm",
                f"DECOUPLE-6 the decoupling rule measures every integrated circuit's decoupling: {name} has netted "
                "pads and none typed power input or power output (pintype in the layout file), so the rule finds no "
                f"supply nets for it and measures nothing; type {name}'s supply pads from its symbol's pin types, "
                "or mark the design not for manufacture (NOT_FOR_MANUFACTURE=true) if it is a proof board"))
    return found


def decoupling_paths(tree: list, ground: Set[str]) -> Tuple[int, list]:
    """The number of circuits with a supply pin, and each decoupling path as (circuit, part, supply pad, pin).

    A path is a decoupling part's supply pad with the pad of its circuit on
    the same net nearest it; the circuits and parts are those of
    board_views.circuits. The pin always exists: a part's net is one of the
    circuit's supply nets, which are the nets of its own pads.
    """
    import board_views
    table = board_geometry.net_table(tree)
    footprints: Dict[str, list] = {}
    for footprint in sexpr.children(tree, "footprint"):
        footprints.setdefault(board_geometry.reference(footprint), footprint)
    paths = []
    measured = [circuit for circuit in board_views.circuits(tree) if circuit["supply_nets"]]
    for circuit in measured:
        chip = board_geometry.footprint_pads(footprints[circuit["reference"]], table)
        for name in circuit["parts"]:
            held = board_geometry.footprint_pads(footprints[name], table)
            low = [pad for pad in held if pad.net in ground]
            for pad in held if len(low) != 1 else [pad for pad in held if pad.net not in ground]:
                pin = min((pin for pin in chip if pin.net == pad.net), key=lambda one: math.dist(one.centre, pad.centre))
                paths.append((circuit["reference"], name, pad, pin))
    return len(measured), paths


def references_off_silkscreen(design: Design, tree: list) -> List[Violation]:
    """Every footprint whose Reference text is hidden or on a layer other than the silkscreen of its side of the board.

    A hidden reference on the right silkscreen is allowed on a footprint that
    is excluded from the bill of materials, as a mounting hole is. A footprint
    with no Reference text at all is a violation, exempt or not.
    """
    found = []
    for footprint in sexpr.children(tree, "footprint"):
        side = sexpr.child(footprint, "layer")
        wanted = "B.SilkS" if side is not None and len(side) > 1 and str(side[1]) == "B.Cu" else "F.SilkS"
        node = next((item for item in sexpr.children(footprint, "property") if len(item) > 2 and str(item[1]) == "Reference"), None)
        if node is None:
            node = next((item for item in sexpr.children(footprint, "fp_text") if len(item) > 2 and str(item[1]) == "reference"), None)
        if node is None:
            name = str(footprint[1]) if len(footprint) > 1 else "?"
            at = board_geometry.placement(footprint, f"the footprint {name}")
            found.append(Violation(
                design.project, "reference_off_silkscreen", f"{name} at ({coordinate(at[0])}, {coordinate(at[1])}) mm",
                f"MFG-7 every part's reference designator is on a silkscreen layer: the footprint {name} has no "
                f"reference text; give it one on {wanted}, the silkscreen of the side it is on, and show it"))
            continue
        layer = sexpr.child(node, "layer")
        on = str(layer[1]) if layer is not None and len(layer) > 1 else "no layer"
        effects = sexpr.child(node, "effects") or []
        marks = sexpr.children(node, "hide") + sexpr.children(effects, "hide")
        hidden = "hide" in node or "hide" in effects or any(len(mark) > 1 and str(mark[1]) == "yes" for mark in marks)
        # A footprint that is not a part of the bill of materials (a mounting hole, a fiducial) may hide its reference.
        attributes = sexpr.child(footprint, "attr") or []
        if hidden and on == wanted and "exclude_from_bom" in attributes:
            continue
        if on == wanted and not hidden:
            continue
        name = board_geometry.reference(footprint) or "?"
        at = board_geometry.placement(footprint, f"the footprint {name}")
        found.append(Violation(
            design.project, "reference_off_silkscreen", f"{name} at ({coordinate(at[0])}, {coordinate(at[1])}) mm",
            f"MFG-7 every part's reference designator is on a silkscreen layer: the reference of {name} is "
            + (f"on {on}, not {wanted}" if on != wanted else f"on {wanted}") + (", and hidden" if hidden and on != wanted else ", but hidden" if hidden else "")
            + f"; put it on {wanted}, the silkscreen of the side {name} is on, and show it"))
    return found


#: How far one character of a reference designator's text advances, as a share of the font's width size. KiCad draws
#: designators in its stroke font, whose capitals and digits advance about 0.6 of the size; that is the figure the
#: text box is built on, so a long name's extent grows with its character count.
TEXT_ADVANCE = 0.6
#: How much nearer another part's courtyard than its own a designator's text must stand to count as nearer the other
#: part, in mm. The box is an estimate, so a gap that differs by less than this is a tie and is not judged.
TEXT_NEARER = 0.1
#: How far a text box may reach into a courtyard before the designator counts as inside it, in mm. A stroke that
#: touches the courtyard line, or stands over it by no more than the rounding of the box's estimate, is not inside.
TEXT_REACH = 0.05


def text_box(footprint: list, node: list, name: str) -> Optional[Tuple[list, str]]:
    """The box a reference designator's text covers on the board, as four corners, and the layer it is on.

    The box is estimated from the text, not drawn from the font: its length is
    the character count times TEXT_ADVANCE times the font's width size, and
    its height the font's height size, both widened by the stroke thickness.
    It is turned to the text's angle, which the file writes as the board's,
    and placed about the text's anchor by its justification (centred on the
    anchor when none is written; a mirrored text exchanges left and right),
    the justification measured along the text's own directions. The box
    returned is the axes-aligned box about that turned rectangle. The anchor is moved to the board
    as the footprint is, so a footprint turned on the board carries its text
    with it. None when the text has no position.
    """
    at = sexpr.child(node, "at")
    if at is None or len(at) < 3:
        return None
    effects = sexpr.child(node, "effects") or []
    font = sexpr.child(effects, "font") or []
    size = sexpr.child(font, "size")
    thickness = sexpr.child(font, "thickness")
    width_size = board_geometry.number(size, 1, f"the text of {name}") if size is not None and len(size) > 2 else 1.0
    height_size = board_geometry.number(size, 2, f"the text of {name}") if size is not None and len(size) > 2 else 1.0
    line = board_geometry.number(thickness, 1, f"the text of {name}") if thickness is not None and len(thickness) > 1 else 0.15
    length = len(str(footprint_text(node))) * TEXT_ADVANCE * width_size + line
    height = height_size + line
    angle = board_geometry.number(at, 3, f"the text of {name}") if len(at) > 3 else 0.0
    words = {str(word) for item in sexpr.children(effects, "justify") for word in item[1:]}
    before, after = ("right", "left") if "mirror" in words else ("left", "right")
    along = length / 2 if before in words else -length / 2 if after in words else 0.0
    across = height / 2 if "top" in words else -height / 2 if "bottom" in words else 0.0
    # The text's own directions on the board: along its line, and down its page. Positive angles turn it counter-clockwise
    # as the board is seen, which is the way the board's y axis (pointing down) makes (cos, -sin).
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    run, down = (cos, -sin), (sin, cos)
    place = board_geometry.placement(footprint, f"the footprint {name}")
    anchor = board_geometry.placed(board_geometry.xy(at, f"the text of {name}"), place)
    centre = (anchor[0] + along * run[0] + across * down[0], anchor[1] + along * run[1] + across * down[1])
    reach_x = (abs(run[0]) * length + abs(down[0]) * height) / 2
    reach_y = (abs(run[1]) * length + abs(down[1]) * height) / 2
    layer = sexpr.child(node, "layer")
    return ([(centre[0] - reach_x, centre[1] - reach_y), (centre[0] + reach_x, centre[1] - reach_y),
             (centre[0] + reach_x, centre[1] + reach_y), (centre[0] - reach_x, centre[1] + reach_y)],
            str(layer[1]) if layer is not None and len(layer) > 1 else "")


def footprint_text(node: list) -> str:
    return str(node[2]) if len(node) > 2 else ""


def arc_points(item: list, what: str) -> List[Tuple[float, float]]:
    """Points along an arc drawn by its start, mid and end points, from its start through its mid to its end.

    The arc is the circle through the three points, sampled every 5 degrees,
    so a box about the points reaches as far as the arc does. A straight
    arc (three points in a line) has none beyond its own.
    """
    a, m, e = (board_geometry.xy(sexpr.child(item, key), what) for key in ("start", "mid", "end"))
    d = 2 * (a[0] * (m[1] - e[1]) + m[0] * (e[1] - a[1]) + e[0] * (a[1] - m[1]))
    if abs(d) < 1e-9:
        return []
    ux = ((a[0] ** 2 + a[1] ** 2) * (m[1] - e[1]) + (m[0] ** 2 + m[1] ** 2) * (e[1] - a[1]) + (e[0] ** 2 + e[1] ** 2) * (a[1] - m[1])) / d
    uy = ((a[0] ** 2 + a[1] ** 2) * (e[0] - m[0]) + (m[0] ** 2 + m[1] ** 2) * (a[0] - e[0]) + (e[0] ** 2 + e[1] ** 2) * (m[0] - a[0])) / d
    radius = math.dist((ux, uy), a)
    start, mid, end = (math.atan2(p[1] - uy, p[0] - ux) for p in (a, m, e))
    sweep_mid, sweep_end = (mid - start) % (2 * math.pi), (end - start) % (2 * math.pi)
    sweep = sweep_end if sweep_mid <= sweep_end else sweep_end - 2 * math.pi
    steps = max(2, int(abs(sweep) / math.radians(5)) + 1)
    return [(ux + radius * math.cos(start + sweep * i / steps), uy + radius * math.sin(start + sweep * i / steps)) for i in range(steps + 1)]


def courtyard(footprint: list, side: str, name: str) -> Optional[List[Tuple[float, float]]]:
    """A part's courtyard on one side of the board, as the box about its courtyard drawing, placed as the part is.

    The box is the part's drawing on `side`'s courtyard layer, taken as the
    four corners of the smallest box about it in the footprint's own axes
    and carried to the board with the footprint. None when the part draws no
    courtyard on that layer.
    """
    layer = f"{side}.CrtYd"
    points: List[Tuple[float, float]] = []
    for item in footprint:
        if not isinstance(item, list) or not item or str(item[0]) not in ("fp_line", "fp_rect", "fp_poly", "fp_circle", "fp_arc"):
            continue
        on = sexpr.child(item, "layer")
        if on is None or len(on) < 2 or str(on[1]) != layer:
            continue
        for key in ("start", "end", "center", "mid"):
            node = sexpr.child(item, key)
            if node is not None:
                points.append(board_geometry.xy(node, f"the courtyard of {name}"))
        circle = sexpr.child(item, "center") if str(item[0]) == "fp_circle" else None
        if circle is not None and sexpr.child(item, "end") is not None:
            centre, edge = board_geometry.xy(circle, f"the courtyard of {name}"), board_geometry.xy(sexpr.child(item, "end"), f"the courtyard of {name}")
            reach = math.dist(centre, edge)
            points += [(centre[0] + dx * reach, centre[1] + dy * reach) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        if str(item[0]) == "fp_arc":
            points += arc_points(item, f"the courtyard of {name}")
        for group in sexpr.children(item, "pts"):
            points += [board_geometry.xy(point, f"the courtyard of {name}") for point in sexpr.children(group, "xy")]
    if not points:
        return None
    place = board_geometry.placement(footprint, f"the footprint {name}")
    left, right = min(p[0] for p in points), max(p[0] for p in points)
    top, bottom = min(p[1] for p in points), max(p[1] for p in points)
    return [board_geometry.placed(corner, place) for corner in ((left, top), (right, top), (right, bottom), (left, bottom))]


def polygon_gap(one: List[Tuple[float, float]], other: List[Tuple[float, float]]) -> float:
    """How far apart two convex polygons stand, 0 when they touch or overlap."""
    if board_geometry.overlap_area(one, other) > 0 or any(board_geometry.within(p, other) for p in one) \
            or any(board_geometry.within(p, one) for p in other):
        return 0.0
    return min(board_geometry.segment_distance(a, b, c, d)
               for a, b in zip(one, one[1:] + one[:1]) for c, d in zip(other, other[1:] + other[:1]))


def designators_astray(design: Design, tree: list) -> List[Violation]:
    """Every reference designator whose text stands inside a part's courtyard, or nearer another part than its own.

    The text is the box text_box estimates, for a reference shown on the
    silkscreen of its footprint's side of the board; a hidden reference, or
    one on another layer, is left to the silkscreen rule. The parts it is held
    against are those with a courtyard drawn on the courtyard layer of the
    same side, the part's own included. The text is inside a courtyard when
    its box reaches into it by more than TEXT_REACH on every side of the
    overlap; it is nearer another part when the gap from its box to another
    part's courtyard is less than the gap to its own part's courtyard, which
    is 0 when the text is inside its own, by more than TEXT_NEARER. A part
    that draws no courtyard of its own is held to the first test only: a
    missing courtyard is another defect, and there is no gap to compare with.
    """
    footprints = []
    for footprint in sexpr.children(tree, "footprint"):
        name = board_geometry.reference(footprint)
        if name:
            footprints.append((name, footprint))
    found = []
    for name, footprint in footprints:
        node = next((item for item in sexpr.children(footprint, "property") if len(item) > 2 and str(item[1]) == "Reference"), None)
        if node is None:
            node = next((item for item in sexpr.children(footprint, "fp_text") if len(item) > 2 and str(item[1]) == "reference"), None)
        if node is None:
            continue
        effects = sexpr.child(node, "effects") or []
        marks = sexpr.children(node, "hide") + sexpr.children(effects, "hide")
        if "hide" in node or "hide" in effects or any(len(mark) > 1 and str(mark[1]) == "yes" for mark in marks):
            continue
        text = text_box(footprint, node, name)
        if text is None or text[1] not in ("F.SilkS", "B.SilkS"):
            continue
        box, layer = text
        side = layer[0]
        shrunk_x = (min(p[0] for p in box) + TEXT_REACH, max(p[0] for p in box) - TEXT_REACH)
        shrunk_y = (min(p[1] for p in box) + TEXT_REACH, max(p[1] for p in box) - TEXT_REACH)
        core = [(shrunk_x[0], shrunk_y[0]), (shrunk_x[1], shrunk_y[0]), (shrunk_x[1], shrunk_y[1]), (shrunk_x[0], shrunk_y[1])]
        if shrunk_x[0] >= shrunk_x[1] or shrunk_y[0] >= shrunk_y[1]:
            core = box
        centre = (sum(p[0] for p in box) / 4, sum(p[1] for p in box) / 4)
        where = f"{name} at ({coordinate(centre[0])}, {coordinate(centre[1])}) mm"
        gaps = {}
        inside = []
        for other, held in footprints:
            yard = courtyard(held, side, other)
            if yard is None:
                continue
            gaps[other] = polygon_gap(box, yard)
            if board_geometry.overlap_area(core, yard) > 0 or any(board_geometry.within(p, yard) for p in core):
                inside.append(other)
        if inside:
            found.append(Violation(
                design.project, "designator_astray", where,
                f"MFG-9 each designator stands outside every part's courtyard, beside its own part: the text of {name} "
                f"stands inside the courtyard of {', '.join(inside)}; move it clear of every courtyard, beside {name}"))
            continue
        own = gaps.get(name)
        nearer = sorted((gap, other) for other, gap in gaps.items() if other != name and own is not None and gap < own - TEXT_NEARER)
        if nearer:
            found.append(Violation(
                design.project, "designator_astray", where,
                f"MFG-9 each designator stands outside every part's courtyard, beside its own part: the text of {name} "
                f"is {coordinate(nearer[0][0])} mm from the courtyard of {nearer[0][1]}, "
                f"nearer than the {coordinate(own)} mm from its own; move it beside {name}"))
    return found


def crowded_test_points(design: Design, tree: list, distance: float) -> List[Violation]:
    """Every test point whose pad stands nearer than `distance` to the courtyard of another part, on either side of the board.

    A test point is a part whose reference designator begins TP. The parts
    it is held against are every other footprint with a courtyard drawn on
    either side's courtyard layer; a part that draws none is skipped, as is
    the test point's own footprint. The pad is its copper's outline, and the
    courtyard the box courtyard() gives; a courtyard that is no box is
    over-covered, which can only fail a clean board too early.
    """
    table = board_geometry.net_table(tree)
    footprints = []
    for footprint in sexpr.children(tree, "footprint"):
        name = board_geometry.reference(footprint)
        if name:
            footprints.append((name, footprint))
    yards = []
    for other, held in footprints:
        for side in ("F", "B"):
            yard = courtyard(held, side, other)
            if yard is not None:
                yards.append((other, side, yard))
    found = []
    for name, footprint in footprints:
        if not name.startswith("TP"):
            continue
        for pad in board_geometry.footprint_pads(footprint, table):
            outline = pad.outline()
            nearest = [(polygon_gap(outline, yard), other, side) for other, side, yard in yards if other != name]
            if not nearest:
                continue
            gap, other, side = min(nearest)
            if gap < distance:
                found.append(Violation(
                    design.project, "test_point_courtyard", f"{pad.name()} at ({coordinate(pad.centre[0])}, {coordinate(pad.centre[1])}) mm",
                    f"TEST-5 a test pad stands at least TEST_COURTYARD_MM from the courtyard of any part: the pad of test "
                    f"point {name} is {coordinate(gap)} mm from the {side}.CrtYd courtyard of {other}, where "
                    f"TEST_COURTYARD_MM requires {coordinate(distance)} mm; move {name} or {other} until the gap is "
                    f"{coordinate(distance)} mm or more"))
    return found


#: How many fiducials each side of the board that carries assembled surface-mount parts needs.
FIDUCIALS_PER_SIDE = 3
#: How much nearer pad one a silkscreen graphic must stand than any other pad to count as marking it, and how far a
#: silkscreen drawing may differ from its image under a symmetry of the pads and still count as unchanged, in mm.
MARK_MARGIN = 0.05
#: How far apart two pads' centres and extents may be, in mm, and still be one pad's image under a symmetry.
PAD_MATCH = 0.01
#: The silkscreen graphics that can mark a pin; text, the designator included, is not one.
MARK_ITEMS = ("fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly")
#: Pin names that say a part has a direction: the pair a diode or an electrolytic capacitor is named for.
POLAR_PAIRS = (({"a", "anode"}, {"k", "cathode"}), ({"+", "plus", "pos"}, {"-", "−", "minus", "neg"}))
#: How a footprint's side is written on its own layer.
SILKSCREEN = {"F.Cu": "F.SilkS", "B.Cu": "B.SilkS"}


def fiducial_pads(footprint: list) -> int:
    """How many of a footprint's pads carry KiCad's global fiducial pad property."""
    return sum(1 for pad in sexpr.children(footprint, "pad")
               if any(len(prop) > 1 and str(prop[1]) == "pad_prop_fiducial_glob" for prop in sexpr.children(pad, "property")))


def missing_fiducials(design: Design, tree: list) -> List[Violation]:
    """Every side of the board that carries surface-mount parts and holds fewer than FIDUCIALS_PER_SIDE fiducials.

    A fiducial is a pad with the global fiducial pad property, counted on the
    side its footprint sits on. A side carries surface-mount parts when it
    holds a footprint with the surface-mount attribute that is not a fiducial
    and is not left out of the position file, which the assembler places from;
    a test point left out of it does not make a side count.
    """
    counts = {"F.Cu": 0, "B.Cu": 0}
    parts = {"F.Cu": 0, "B.Cu": 0}
    for footprint in sexpr.children(tree, "footprint"):
        layer = sexpr.child(footprint, "layer")
        side = str(layer[1]) if layer is not None and len(layer) > 1 else "F.Cu"
        if side not in counts:
            continue
        found = fiducial_pads(footprint)
        counts[side] += found
        attributes = sexpr.child(footprint, "attr") or []
        if not found and "smd" in attributes and "exclude_from_pos_files" not in attributes:
            parts[side] += 1
    violations = []
    for side, name in (("F.Cu", "front"), ("B.Cu", "back")):
        if parts[side] and counts[side] < FIDUCIALS_PER_SIDE:
            violations.append(Violation(
                design.project, "side_fiducials", f"the {name} side ({side})",
                f"MFG-10 each side with assembled surface-mount parts carries at least {FIDUCIALS_PER_SIDE} fiducials: the {name} side "
                f"has {parts[side]} surface-mount parts and {counts[side]} fiducials; add {FIDUCIALS_PER_SIDE - counts[side]} "
                f"or more footprints on {side} with a pad carrying the global fiducial property, so the machine can find the board"))
    return violations


def schematic_parts(netlist: list) -> Dict[str, Tuple[str, List[str]]]:
    """Each part of KiCad's netlist by reference: the library item name of its symbol, and the name of each pin it has."""
    symbols: Dict[str, str] = {}
    for group in walk(netlist, "components"):
        for comp in sexpr.children(group, "comp"):
            ref, source = sexpr.child(comp, "ref"), sexpr.child(comp, "libsource")
            part = sexpr.child(source, "part") if source is not None else None
            if ref is not None and len(ref) > 1:
                symbols[str(ref[1])] = str(part[1]) if part is not None and len(part) > 1 else ""
    names: Dict[str, List[str]] = {ref: [] for ref in symbols}
    for pins in schematic_pin_nodes(netlist).values():
        for pin in pins:
            names.setdefault(pin.ref, []).extend(name.lower() for name in pin.names())
    return {ref: (symbols.get(ref, ""), names[ref]) for ref in names}


def is_polarised(footprint: list, pads: List["board_geometry.Pad"], symbol: str, pin_names: List[str]) -> bool:
    """Whether a part has a direction: pins named for anode and cathode or plus and minus, a polarised capacitor's
    symbol, or three pads on distinct nets. A footprint of pads on one net, or of non-plated holes alone, is left out;
    a plated pad, through-hole or surface-mount, makes it a candidate."""
    if len({pad.net for pad in pads}) < 2:
        return False
    nodes = sexpr.children(footprint, "pad")
    if nodes and all(len(node) > 2 and str(node[2]) == "np_thru_hole" for node in nodes):
        return False
    if symbol.startswith("C_Polarized"):
        return True
    if any(first & set(pin_names) and second & set(pin_names) for first, second in POLAR_PAIRS):
        return True
    return len({pad.net for pad in pads if pad.net}) >= 3


def silkscreen_segments(footprint: list, layer: str, name: str) -> List[List[Tuple[float, float]]]:
    """The footprint's own graphics on `layer`, as polylines on the board; text is not among them."""
    place = board_geometry.placement(footprint, f"the footprint {name}")
    what = f"the silkscreen of {name}"
    lines = []
    for item in footprint:
        if not isinstance(item, list) or not item or str(item[0]) not in MARK_ITEMS:
            continue
        on = sexpr.child(item, "layer")
        if on is None or len(on) < 2 or str(on[1]) != layer:
            continue
        kind = str(item[0])
        if kind == "fp_line":
            line = [board_geometry.xy(sexpr.child(item, "start"), what), board_geometry.xy(sexpr.child(item, "end"), what)]
        elif kind == "fp_rect":
            (x1, y1), (x2, y2) = (board_geometry.xy(sexpr.child(item, key), what) for key in ("start", "end"))
            line = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
        elif kind == "fp_circle":
            centre, edge = (board_geometry.xy(sexpr.child(item, key), what) for key in ("center", "end"))
            radius = math.dist(centre, edge)
            line = [(centre[0] + radius * math.cos(2 * math.pi * i / 64), centre[1] + radius * math.sin(2 * math.pi * i / 64))
                    for i in range(65)]
        elif kind == "fp_arc":
            line = arc_points(item, what)
        else:
            line = [board_geometry.xy(point, what) for group in sexpr.children(item, "pts") for point in sexpr.children(group, "xy")]
            if line:
                line.append(line[0])
        if len(line) > 1:
            lines.append([board_geometry.placed(point, place) for point in line])
    return lines


def polyline_gap(line: List[Tuple[float, float]], outline: List[Tuple[float, float]]) -> float:
    """How far a polyline stands from a pad's convex outline, 0 where it touches or enters it."""
    if any(board_geometry.within(point, outline) for point in line):
        return 0.0
    return min(board_geometry.segment_distance(a, b, c, d)
               for a, b in zip(line, line[1:]) for c, d in zip(outline, outline[1:] + outline[:1]))


def along(lines: List[List[Tuple[float, float]]], step: float = 0.1) -> List[Tuple[float, float]]:
    """Points along the polylines no further than `step` mm apart, their ends included."""
    points = []
    for line in lines:
        for a, b in zip(line, line[1:]):
            pieces = max(1, int(math.dist(a, b) / step) + 1)
            points += [(a[0] + (b[0] - a[0]) * i / pieces, a[1] + (b[1] - a[1]) * i / pieces) for i in range(pieces)]
        points.append(line[-1])
    return points


def drawn_the_same(one: List[List[Tuple[float, float]]], other: List[List[Tuple[float, float]]]) -> bool:
    """Whether two drawings lie within MARK_MARGIN of each other, every point of each near some stroke of the other."""
    def covered(points, lines):
        return all(min(board_geometry.distance_to_segment(point, a, b) for line in lines for a, b in zip(line, line[1:]))
                   <= MARK_MARGIN for point in points)
    if not one or not other:
        return not one and not other
    return covered(along(one), other) and covered(along(other), one)


def pad_symmetries(pads: List["board_geometry.Pad"], firsts: List["board_geometry.Pad"]) -> list:
    """The turns and reflections about the pads' centre that map the pads onto themselves in position, size and shape
    while moving the pads `firsts` off themselves, each as a function of a board point. Only those fixing the centre can map a set onto itself,
    so each is found by sending the pad furthest from it to each pad as far from it, by rotation and by reflection."""
    cx = sum(pad.centre[0] for pad in pads) / len(pads)
    cy = sum(pad.centre[1] for pad in pads) / len(pads)
    anchor = max(pads, key=lambda pad: math.dist(pad.centre, (cx, cy)))
    reach = math.dist(anchor.centre, (cx, cy))
    if reach < PAD_MATCH:
        return []
    start = math.atan2(anchor.centre[1] - cy, anchor.centre[0] - cx)

    def make(kind: str, angle: float):
        cos, sin = math.cos(angle), math.sin(angle)
        if kind == "turn":
            return lambda p: (cx + (p[0] - cx) * cos - (p[1] - cy) * sin, cy + (p[0] - cx) * sin + (p[1] - cy) * cos)
        return lambda p: (cx + (p[0] - cx) * cos + (p[1] - cy) * sin, cy + (p[0] - cx) * sin - (p[1] - cy) * cos)

    found = []
    for target in pads:
        if abs(math.dist(target.centre, (cx, cy)) - reach) > PAD_MATCH:
            continue
        end = math.atan2(target.centre[1] - cy, target.centre[0] - cx)
        for kind, angle in (("turn", end - start), ("mirror", end + start)):
            image = make(kind, angle)
            if all(any(math.dist(image(pad.centre), other.centre) <= PAD_MATCH and pad.shape == other.shape
                       and all(abs(a - b) <= PAD_MATCH for a, b in zip(image_box(image, pad), other.box()))
                       for other in pads) for pad in pads) \
                    and not all(any(math.dist(image(one.centre), other.centre) <= PAD_MATCH for other in firsts) for one in firsts):
                found.append(image)
    return found


def image_box(image, pad: "board_geometry.Pad") -> Tuple[float, float, float, float]:
    """The box about a pad's outline once `image` has carried it: (left, top, right, bottom)."""
    corners = [image(point) for point in pad.outline()]
    return (min(p[0] for p in corners), min(p[1] for p in corners), max(p[0] for p in corners), max(p[1] for p in corners))


def unmarked_pins(design: Design, tree: list, parts: Dict[str, Tuple[str, List[str]]]) -> List[Violation]:
    """Every polarised part whose first pin is not marked on the silkscreen of its own side.

    The first pin is the pad numbered 1. It is marked when a graphic of the
    footprint on its side's silkscreen stands nearer its copper than every other
    pad's by more than MARK_MARGIN, and the footprint's silkscreen is not
    unchanged by any symmetry of its pads that moves that pad. A polarised
    part with no pad numbered 1 has no first pin to mark.
    """
    table = board_geometry.net_table(tree)
    found = []
    for footprint in sexpr.children(tree, "footprint"):
        name = board_geometry.reference(footprint)
        if not name:
            continue
        pads = board_geometry.footprint_pads(footprint, table)
        symbol, pin_names = parts.get(name, ("", []))
        if not is_polarised(footprint, pads, symbol, pin_names):
            continue
        layer = sexpr.child(footprint, "layer")
        side = str(layer[1]) if layer is not None and len(layer) > 1 else "F.Cu"
        silk = SILKSCREEN.get(side, "F.SilkS")
        firsts = [pad for pad in pads if pad.number == "1"]
        if not firsts:
            at = board_geometry.placement(footprint, f"the footprint {name}")
            found.append(Violation(
                design.project, "polarity_mark", f"{name} at ({coordinate(at[0])}, {coordinate(at[1])}) mm",
                f"a polarised part marks its first pin on the silkscreen: {name} has no pad numbered 1, so it has no first pin "
                "to mark; number its first pad 1 and mark it"))
            continue
        first = firsts[0]
        others = [pad for pad in pads if pad.number != "1"]
        lines = silkscreen_segments(footprint, silk, name)
        marked = False
        for line in lines:
            toward = min(polyline_gap(line, one.outline()) for one in firsts)
            away = min((polyline_gap(line, other.outline()) for other in others), default=math.inf)
            if toward < away - MARK_MARGIN:
                marked = True
                break
        where = f"{name} pad 1 at ({coordinate(first.centre[0])}, {coordinate(first.centre[1])}) mm"
        if not marked:
            why = (f"it has no graphic on {silk} nearer pad 1 than every other pad by more than {coordinate(MARK_MARGIN)} mm"
                   if lines else f"it draws nothing on {silk}")
            found.append(Violation(
                design.project, "polarity_mark", where,
                f"a polarised part marks its first pin on the silkscreen of its own side: {name} is not marked at pad 1, {why}; "
                f"draw a line, arc, circle or polygon on {silk} of {name}'s footprint that stands nearest pad 1 (text is no mark)"))
            continue
        for image in pad_symmetries(pads, firsts):
            moved = [[image(point) for point in line] for line in lines]
            if drawn_the_same(lines, moved):
                found.append(Violation(
                    design.project, "polarity_mark", where,
                    f"a polarised part marks its first pin on the silkscreen of its own side: the silkscreen of {name} looks the same "
                    "when its pads are turned or reflected onto themselves so that pad 1 moves, so it marks nothing; "
                    f"draw the mark of pad 1 on {silk} so that it breaks that symmetry"))
                break
    return found


# --- One design ----------------------------------------------------------------


def check_design(design: Design, repository: Repository, kicad_cli: str, yaml, today: datetime.date,
                 already: List[Violation], read: Optional[List[Tuple[str, str, str]]] = None) -> List[Violation]:
    """Every violation of one design. `read`, when given, receives each measured rule's figure as the design sets it,
    as (item and what it measures, the text variable, the figure with its unit)."""
    root = repository.root
    found = list(already)
    if any(v.rule == "design_discovery" for v in already):
        return found
    try:
        with open(os.path.join(root, design.project), encoding="utf-8") as handle:
            project = json.load(handle, object_pairs_hook=unique_keys)
        if not isinstance(project, dict):
            raise ValueError("it is not a JSON object")
    except DuplicateKey as error:
        found.append(Violation(design.project, "project_file", design.project,
                               f"the project file gives the key '{error}' more than once in one object, and KiCad "
                               "and the check could each take a different one; give it once"))
        return found
    except (OSError, ValueError) as error:
        found.append(Violation(design.project, "design_unreadable", design.project,
                               f"the project file cannot be read ({error}); correct the file at that point, or "
                               "restore it from the repository's history"))
        return found
    misread = project_form(design, project)
    if misread:
        return found + misread

    variables = project.get("text_variables") or {}
    mains = variables.get("MAINS")
    not_for_manufacture = variables.get("NOT_FOR_MANUFACTURE") == "true"
    if mains not in ("present", "none"):
        said = "is not set" if mains is None else f"is '{mains}'"
        found.append(Violation(design.project, "mains_declaration", f"{design.project} text_variables.MAINS",
                               f"the project text variable MAINS {said}; set it to present if the board carries "
                               "mains, or none if it does not, since silence is never read as compliance"))

    figures, unset = workmanship_figures(design, variables)
    found += unset
    for item, what, name, unit, _, _ in MEASURED:
        if name in figures and read is not None:
            read.append((f"{item} {what}", name, f"{figures[name]:g} {unit}"))
    pour_minimum, no_minimum = pour_gap_figure(design, project)
    if pour_minimum is not None and read is not None:
        read.append(("MFG-6 pour gap", "Board Setup min_clearance", f"{pour_minimum:g} mm, the narrowest gap a pour may "
                     "leave between its fill and copper of its own net that it stops short of"))

    if read is not None:
        read.append(("DECOUPLE-6 via in the decoupling path", "none, inherent zero", "0 vias between a decoupling capacitor's "
                     "supply pad and the pin it decouples"))
        read.append(("MFG-7 reference on silkscreen", "none, inherent zero", "0 references off a silkscreen layer or hidden"))
        read.append(("MFG-9 designator beside its part", "none, inherent zero", "0 designators inside a part's courtyard or "
                     "nearer another part than their own"))
        read.append(("MFG-10 fiducials on a side", "none, the item's own count", f"{FIDUCIALS_PER_SIDE} fiducials at least on each side "
                     "that carries assembled surface-mount parts"))

    found += exclusions(design, project)
    rules, hidden = read_rules(root, design, repository)
    found += hidden
    found += workmanship_rules(design, rules)
    corner = corner_minimum(rules)
    if corner is not None and read is not None:
        read.append(("WORK-4 corner at a pad", "the rules file's track_angle", f"{corner:g} degrees at least between "
                     "two tracks of a net that meet at a pad, as at any other joint"))

    signed = None
    if mains == "present":
        record = find_record(root, design.directory, repository.tracked)
        signed, problems = read_record(yaml, root, design, record, not_for_manufacture, today,
                                       repository.uncommitted(record) if record is not None else None)
        found += problems
        found += mains_rule(design, rules, signed)
        if signed is not None:
            found += separation_floor(design, record, signed)

    pin_record = find_record(root, design.directory, repository.tracked, PIN_RECORD_NAME)
    channels, pin_problems = read_pin_record(yaml, root, design, pin_record, not_for_manufacture)
    found += pin_problems

    found += check_parts(yaml, root, design, repository, today, not_for_manufacture)
    found += read_derating(yaml, root, repository, design, not_for_manufacture)
    found += read_pin_limits(yaml, root, repository, design, not_for_manufacture)
    board_rules, rules_problems = load_board_rules(yaml, root, repository, design, not_for_manufacture)
    rules_record = find_record(root, design.directory, repository.tracked, BOARD_RULES_NAME) or BOARD_RULES_NAME
    found += rules_problems
    sensing = board_rules["sensing"] if board_rules is not None and board_rules["sensing"] != NOTHING else None
    if sensing and read is not None:
        read.append(("SENSE-6 sensing clearance", f"{BOARD_RULES_NAME} sensing.clearance_mm",
                     f"{sensing['clearance_mm']:g} mm at least between a sensing item and an item of a noisy class"))
    found += unnamed_sheets(design, repository)

    if any(v.rule == "design_unreadable" for v in found):
        return found

    nonce = secrets.token_hex(8)
    files, unreachable = design_files(design, repository)
    found += unreachable
    with tempfile.TemporaryDirectory(prefix="board-check-") as scratch:
        # Only what git tracks is copied, so KiCad checks the design as the
        # repository holds it and nothing left lying beside it on this machine.
        # Each file keeps its place in the repository, so a sheet or a library
        # the design reaches above its own folder is where KiCad looks for it.
        replica = os.path.join(scratch, "repository")
        for path in files:
            if os.path.isfile(os.path.join(root, path)):
                target = os.path.join(replica, path)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(os.path.join(root, path), target)
        copy = os.path.join(replica, design.directory)
        os.makedirs(copy, exist_ok=True)
        schematic = os.path.basename(design.schematic)
        layout = os.path.basename(design.layout)
        try:
            with open(os.path.join(copy, layout), encoding="utf-8") as handle:
                tree: Optional[list] = sexpr.parse_one(handle.read())
            error = None
        except (OSError, sexpr.SexprError) as unread:
            tree, error = None, unread
        items = net_items(tree) if tree is not None else {}
        copper: Optional[Layout] = None
        if tree is not None:
            try:
                copper = Layout(tree)
                pasted = (paste_over_vias(design, tree, figures["PASTE_OVER_VIA_MM2"])
                          if "PASTE_OVER_VIA_MM2" in figures else [])
            except board_geometry.Unreadable as unread:
                found.append(Violation(design.project, "design_unreadable", design.layout,
                                       f"the layout's copper cannot be read for its workmanship rules ({unread})"))
                return found
            found += measured(design, copper, figures, corner)
            found += pasted
        rules_copy = os.path.join(copy, os.path.basename(design.rules))
        existing = "(version 1)\n"
        if rules is not None and os.path.exists(rules_copy):
            with open(rules_copy, encoding="utf-8", errors="replace") as handle:
                existing = handle.read()
        with open(rules_copy, "w", encoding="utf-8") as handle:
            handle.write(existing + appended_rules(signed, nonce, marker_net(items)))

        erc, why = run_report([kicad_cli, "sch", "erc", "--format", "json", "--severity-all", "--units", "mm", schematic], copy)
        netlist: Optional[Dict[str, Tuple[List[str], List[str]]]] = None
        parts: Dict[str, Tuple[str, List[str]]] = {}
        if erc is None:
            found.append(Violation(design.project, "design_unreadable", design.schematic,
                                   f"the schematic cannot be checked: {why}"))
        else:
            found += ignored(design, erc, "erc.rule_severities")
            for sheet in erc.get("sheets") or []:
                for entry in sheet.get("violations") or []:
                    found.append(kicad_violation(design, entry, design.schematic, sheet.get("path", "")))
            text, why = run_kicad([kicad_cli, "sch", "export", "netlist", "--format", "kicadsexpr", schematic],
                                  copy, "netlist.net")
            try:
                parsed = sexpr.parse_one(text) if text is not None else None
                netlist = schematic_nets(parsed) if parsed is not None else None
                parts = schematic_parts(parsed) if parsed is not None else {}
                if parsed is not None and channels is not None:
                    found += connectivity(design, pin_record, channels, schematic_pin_nodes(parsed))
            except sexpr.SexprError as error:
                why = f"KiCad's netlist could not be read ({error})"
            if netlist is not None:
                found += tool_named_nets(design, netlist)
                found += voltage_rules(design, yaml, root, repository, not_for_manufacture, mains, signed,
                                       schematic_pin_nodes(parsed), schematic_mains(netlist))
            if netlist is None:
                found.append(Violation(design.project, "design_unreadable", design.schematic,
                                       f"the schematic's net classes cannot be read from KiCad's netlist: {why}"))

        drc, why = run_report([kicad_cli, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm",
                               "--schematic-parity", "--refill-zones", "--save-board", "--all-track-errors", layout], copy)
        if drc is None:
            found.append(Violation(design.project, "design_unreadable", design.layout,
                                   f"the layout cannot be checked: {why}"))
            return found

        # KiCad saves the board it refilled over the copy, so the fills the
        # pour rules measure are the ones it has just made, never the committed ones.
        fills: List[Tuple[str, str, List[board_geometry.Point]]] = []
        refilled: Optional[list] = None
        if tree is not None:
            try:
                with open(os.path.join(copy, layout), encoding="utf-8") as handle:
                    refilled = sexpr.parse_one(handle.read())
                fills = zone_fills(refilled)
                if fills:
                    if pour_minimum is None:
                        found += no_minimum
                    else:
                        found += pour_gaps(design, refilled, fills, pour_minimum)
            except (OSError, sexpr.SexprError, board_geometry.Unreadable) as unread:
                found.append(Violation(design.project, "design_unreadable", design.layout,
                                       f"the layout KiCad refilled cannot be read for its pours ({unread})"))
                return found

        markers = fired(drc, marker_rule(nonce))
        own = {id(entry) for entry in markers}
        found += ignored(design, drc, "board.design_settings.rule_severities")
        for entry in drc.get("violations") or []:
            if id(entry) not in own:
                found.append(kicad_violation(design, entry, design.layout))
        for entry in (drc.get("unconnected_items") or []) + (drc.get("schematic_parity") or []):
            found.append(kicad_violation(design, entry, design.layout))

        # Assertions come only from a rules file, so a report full of them shows
        # the file was loaded even where the marker's own were among those dropped.
        if cut_short(drc):
            found.append(Violation(
                design.project, "custom_rules", design.rules,
                f"KiCad's report was cut short: it reports at most {REPORT_LIMIT} assertion failures, and this run "
                "reached that many, so any further failures were dropped from the report at random and the design "
                "cannot be passed on what is left; correct the items the design's own assertion rules fail on until "
                f"fewer than {REPORT_LIMIT} fail"))
        elif not markers:
            if rules is None:
                where, what = design.rules, ("the design has no custom rules file, and KiCad did not load the one "
                                             "the check writes in its place either, which holds only the check's own "
                                             "rules; run the check with KiCad 10.0 or newer")
            else:
                place, what = rejected_form(kicad_cli, copy, layout, rules_copy, existing, nonce)
                where = f"{design.rules} {place}"
            found.append(Violation(design.project, "custom_rules", where,
                                   "KiCad did not load the design's custom rules: it drops the whole file, without "
                                   "saying so, when any part of it is something it cannot parse, so neither the "
                                   f"design's own rules nor the signed separation rule were checked; {what}"))
            return found

        if netlist is None:
            return found
        if tree is None:
            found.append(Violation(design.project, "design_unreadable", design.layout,
                                   f"the layout cannot be read for its nets and clearance overrides ({error})"))
            return found

        # Three statements of which nets are in Mains, each as KiCad itself
        # resolves it: the layout's, which is what the separation rule is
        # enforced against; the schematic's; and the project file's net
        # settings, by name and by pattern. They must agree net for net.
        names = layout_nets(tree)
        project_copy = os.path.join(copy, os.path.basename(design.project))
        widths, unwidthed = class_widths(project)
        project_classes = {entry["name"] for entry in setting(project, "net_settings", "classes") or []
                           if isinstance(entry, dict) and isinstance(entry.get("name"), str)} | {"Mains"}
        declared = set()
        if board_rules is not None:
            declared |= set(sensing["classes"] + sensing["noisy_classes"]) if sensing else set()
            if board_rules["ground_returns"] != NOTHING:
                returns = board_rules["ground_returns"]
                declared |= set(returns["ground_classes"] + returns["non_signal_classes"]) | {e["class"] for e in returns["signal_classes"]}
        classes = sorted(((set(widths) | (declared & project_classes)) - {"Default"}) | {"Mains"})
        members, why = class_members(kicad_cli, scratch, project_copy, classes, names, nonce,
                                     layout_version(tree), class_blocks(tree))
        if members is None:
            found.append(Violation(design.project, "design_unreadable", design.layout,
                                   f"the layout's net classes cannot be resolved by KiCad: {why}"))
            return found
        on_layout = members["Mains"]
        if signed is not None and on_layout:
            found += mounting_holes(kicad_cli, design, copy, layout, rules_copy, existing, signed, nonce,
                                    marker_net(items), tree, on_layout, fills)
        if sensing:
            found += sensing_clearance(kicad_cli, design, copy, layout, rules_copy, existing, signed, nonce, marker_net(items),
                                       rules_record, sensing, project_classes, members)
        if "WORK_NECK_MM" in figures and copper.copper:
            for name in unwidthed:
                found.append(Violation(design.project, "project_file", f"{design.project} net_settings.classes '{name}'",
                                       f"the net class {name} gives no track width a positive number of millimetres "
                                       "can be read from, so WORK-8 cannot tell a track of the class narrower than it; "
                                       "give the class its track width"))
            found += narrowings(design, copper, figures["WORK_NECK_MM"], net_widths(names, members, widths))
        named = set(names) | set(netlist) | set(map(str, setting(project, "net_settings", "netclass_assignments") or {}))
        in_project, why = project_mains(kicad_cli, scratch, project_copy, named, nonce, layout_version(tree))
        if in_project is None:
            found.append(Violation(design.project, "design_unreadable", f"{design.project} net_settings",
                                   f"the project file's net classes cannot be resolved by KiCad: {why}"))
            return found

    locate: Dict[str, Dict[str, str]] = {ON_LAYOUT: {}, IN_SCHEMATIC: {}, IN_PROJECT: {}}
    for net in on_layout:
        if items.get(net):
            locate[ON_LAYOUT][net] = "on the layout at " + items[net][0]
    for net, (_, pins) in netlist.items():
        if pins:
            locate[IN_SCHEMATIC][net] = "in the schematic at " + ", ".join(pins[:4]) + (", ..." if len(pins) > 4 else "")
    for net in in_project:
        locate[IN_PROJECT][net] = f"{design.project} net_settings"
    sources = {ON_LAYOUT: on_layout, IN_SCHEMATIC: schematic_mains(netlist), IN_PROJECT: in_project}
    found += mains_agreement(design, mains, sources, locate)

    if mains == "present" and not on_layout:
        found.append(Violation(design.project, "mains_declaration", design.layout,
                               "MAINS is present but no net on the layout is in the Mains net class, so the "
                               "separation rule would apply to nothing; assign every mains-referenced net to Mains"))
    if mains == "none" and on_layout:
        found.append(Violation(design.project, "mains_declaration", f"{design.project} text_variables.MAINS",
                               f"MAINS is none but the layout puts {', '.join(sorted(on_layout))} in the Mains net "
                               "class; set MAINS to present, or take them out of Mains"))

    found += net_ties(design, tree, on_layout)
    found += crystal_keep_clear(design, rules, tree)
    found += ground_reliefs(design, rules, tree, members)
    try:
        found += decoupling_vias(design, tree, ground_nets(members))
        found += untyped_circuits(design, tree, not_for_manufacture)
        if read is not None:
            circuits, paths = decoupling_paths(tree, ground_nets(members))
            read.append(("DECOUPLE-6 decoupling paths measured", "the layout's pad pin types",
                         f"{len(paths)} paths of {circuits} circuits with a supply pin"))
        found += references_off_silkscreen(design, tree)
        found += designators_astray(design, tree)
        found += missing_fiducials(design, tree)
        found += unmarked_pins(design, tree, parts)
        if board_rules is not None and board_rules["ground_returns"] != NOTHING:
            found += ground_returns(design, tree, rules_record, board_rules["ground_returns"], members)
        if "TEST_COURTYARD_MM" in figures:
            found += crowded_test_points(design, tree, figures["TEST_COURTYARD_MM"])
    except board_geometry.Unreadable as unread:
        found.append(Violation(design.project, "design_unreadable", design.layout,
                               f"the layout cannot be read for its decoupling and references ({unread})"))
    if signed is not None:
        found += overrides(design, tree, signed[0], on_layout)
    if sensing:
        found += sensing_overrides(design, tree, rules_record, sensing["clearance_mm"],
                                   set().union(*(members.get(name, set()) for name in sensing["classes"] + sensing["noisy_classes"])))
    try:
        if "BARRIER_COPPER_MM2" in figures:
            found += mains_barrier(design, refilled, fills, on_layout, figures["BARRIER_COPPER_MM2"])
    except board_geometry.Unreadable as unread:
        found.append(Violation(design.project, "design_unreadable", design.layout,
                               f"the layout KiCad refilled cannot be read for the barrier under a part ({unread})"))
    return found


# --- The whole check ------------------------------------------------------------


def run(root: str, kicad_cli: str, git: str = "git", out=sys.stdout,
        today: Optional[datetime.date] = None) -> int:
    require_python()
    yaml = require_yaml()
    top = require_git(git, root)
    version = require_kicad(kicad_cli)
    today = today or datetime.date.today()
    global KICAD_ENVIRONMENT
    with tempfile.TemporaryDirectory(prefix="board-check-kicad-") as home:
        KICAD_ENVIRONMENT = isolate_kicad(kicad_cli, version, home)
        try:
            return report(top, kicad_cli, git, version, today, yaml, out)
        finally:
            KICAD_ENVIRONMENT = None


#: How the listing of what the designs read writes a folder read whole at the
#: top of the repository, which a bare slash would leave empty.
WHOLE_REPOSITORY = "./"


def design_reads(top: str, files: List[str], git: str = "git") -> List[str]:
    """Every file, and every folder read whole, that a board design the repository tracks reads.

    For each design that is its own folder, written with a trailing slash so a
    file deleted from it is still one the design read, every file its folder,
    its sheets and its libraries hold, and the separation basis, pin allocation, parts specification,
    catalogue extract, derating policy, pin-limit and board rules records it is held to, whether or not a record is committed. A design in the top folder reads
    the whole repository, written as WHOLE_REPOSITORY.
    """
    repository = Repository(top, files, git)
    designs, _, _ = discover(top, files)
    reads: Set[str] = set()
    for design in designs:
        reads.add(design.directory + "/" if design.directory else WHOLE_REPOSITORY)
        reads.update(design_files(design, repository)[0])
        for name in (RECORD_NAME, PIN_RECORD_NAME, PARTS_RECORD_NAME, CATALOGUE_NAME, DERATING_NAME, PIN_LIMITS_NAME,
                     BOARD_RULES_NAME):
            record = find_record(top, design.directory, repository.tracked, name)
            if record:
                reads.add(record)
    return sorted(reads)


def list_reads(root: str, git: str = "git", out=None) -> int:
    """Print what the designs read, one entry per line, to `out` or standard output; the exit status."""
    require_python()
    top = require_git(git, root)
    for entry in design_reads(top, tracked_files(git, top), git):
        print(entry, file=out)
    return 0


def report(top: str, kicad_cli: str, git: str, version: str, today: datetime.date, yaml, out) -> int:
    """Check every design under `top` and print the report; the exit status."""
    files = tracked_files(git, top)
    repository = Repository(top, files, git)
    designs, orphans, problems = discover(top, files)
    print(f"Checking board designs under {top} with KiCad {version}", file=out)

    results: List[Tuple[str, List[Violation]]] = []
    figures: Dict[str, List[Tuple[str, str, str]]] = {}
    for design in designs:
        read: List[Tuple[str, str, str]] = []
        results.append((design.project, check_design(design, repository, kicad_cli, yaml, today, problems[design.project],
                                                     read)))
        figures[design.project] = read
    for orphan in orphans:
        results.append((orphan.design, [orphan]))
    if not designs:
        results.append(("(repository)", [Violation(
            "(repository)", "design_discovery", top,
            "no board design was found: no project file (.kicad_pro) is tracked anywhere in the repository, "
            "and a check that finds nothing to inspect fails rather than reporting success")]))

    failed = 0
    for name, violations in results:
        if violations:
            failed += 1
            print(f"DESIGN | {clean(name)} | FAIL | {len(violations)} violation{'s' if len(violations) != 1 else ''}", file=out)
        else:
            print(f"DESIGN | {clean(name)} | PASS", file=out)
        for rule, variable, figure in figures.get(name, []):
            print(f"FIGURE | {clean(name)} | {clean(rule)} | {clean(variable)} | {clean(figure)}", file=out)
        for violation in violations:
            print(violation.line(), file=out)
    if failed:
        print(f"RESULT | FAIL | {failed} of {len(results)} designs failed", file=out)
        return 1
    print(f"RESULT | PASS | all {len(results)} designs passed", file=out)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=".", help="any folder inside the repository to check (default: here)")
    parser.add_argument("--kicad-cli", default="kicad-cli", help="KiCad's command-line tool (default: kicad-cli on the search path)")
    parser.add_argument("--git", default="git", help="git (default: git on the search path)")
    parser.add_argument("--list-reads", action="store_true",
                        help="list every file the board designs read, one per line, without running the check or needing KiCad")
    args = parser.parse_args(argv)
    try:
        if args.list_reads:
            return list_reads(args.root, args.git)
        return run(args.root, args.kicad_cli, args.git)
    except CannotRun as error:
        print(f"CANNOT RUN | {clean(str(error))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
