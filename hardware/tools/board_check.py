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

Every finding is printed on one line of a fixed shape,

    VIOLATION | <design> | <rule> | <location> | <message>

after a verdict line for its design, and the exit status is the verdict: 0 when
every design passes, 1 when any fails, 2 when the check cannot run at all.
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


def probe_rule(nonce: str) -> str:
    """The rule reporting every item KiCad places in the Mains class."""
    return f"{RESERVED} {nonce}: Mains item"

#: A value standing in for a signature rather than being one.
PLACEHOLDERS = {"unsigned", "tbd", "todo", "none", "placeholder"}

#: Generous, because a dense board's zone refill takes real time; a run that
#: hangs past it fails the design rather than the check waiting forever.
KICAD_TIMEOUT_S = 900

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
                missing: Optional[List[Tuple[str, str]]] = None) -> Set[str]:
    """Every schematic file a root schematic reaches through its hierarchical sheets.

    A sheet git does not track is never read, since the check reads a design
    only as the repository holds it; it is added to `missing` as (the sheet,
    the schematic naming it) instead. Raises SexprError or OSError when a
    tracked sheet cannot be read.
    """
    seen = set() if seen is None else seen
    if schematic in seen:
        return seen
    seen.add(schematic)
    with open(os.path.join(root, schematic), encoding="utf-8") as handle:
        tree = sexpr.parse_one(handle.read())
    for sheet in sexpr.children(tree, "sheet"):
        for prop in sexpr.children(sheet, "property"):
            if len(prop) > 2 and prop[1] in ("Sheetfile", "Sheet file"):
                target = os.path.normpath(os.path.join(os.path.dirname(schematic), prop[2])).replace(os.sep, "/")
                if target not in tracked:
                    if missing is not None and target not in seen:
                        missing.append((target, schematic))
                    seen.add(target)
                    continue
                sheet_files(root, target, tracked, seen, missing)
    return seen


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
            try:
                owned.update(sheet_files(root, design.schematic, tracked, missing=missing))
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
                entries = sexpr.children(sexpr.parse_one(handle.read()), "lib")
        except (OSError, sexpr.SexprError) as error:
            found.append(Violation(design.project, "design_unreadable", path,
                                   f"the library table cannot be read ({error}); correct the file at that point, "
                                   "or restore it from the repository's history"))
            continue
        for entry in entries:
            name, uri = sexpr.child(entry, "name"), sexpr.child(entry, "uri")
            name = str(name[1]) if name is not None and len(name) > 1 else "(unnamed)"
            uri = str(uri[1]) if uri is not None and len(uri) > 1 else ""
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


def find_record(root: str, directory: str, tracked: Set[str] = frozenset()) -> Optional[str]:
    """The nearest separation basis record at or above a design's folder, repository-relative.

    One that is on disk or tracked counts, so an uncommitted record nearer the
    design than a committed one is the one found, and fails, rather than being
    passed over for the committed one above it.
    """
    current = directory
    while True:
        candidate = (os.path.join(current, RECORD_NAME) if current else RECORD_NAME).replace(os.sep, "/")
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


def read_record(yaml, root: str, design: Design, record: Optional[str], not_for_manufacture: bool,
                today: datetime.date, uncommitted: Optional[str] = None
                ) -> Tuple[Optional[Tuple[float, float]], List[Violation]]:
    """The signed mains-to-low-voltage (clearance, creepage) in mm, or what stops it being usable.

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
            data = yaml.safe_load(handle)
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
    if synthetic is not None and synthetic is not False and not not_for_manufacture:
        problems.append(Violation(design.project, "separation_basis", f"{record} synthetic",
                                  "the record is marked synthetic, made only to prove the check, and the design is not "
                                  "marked not for manufacture (NOT_FOR_MANUFACTURE=true), so a proof record cannot let it pass"))

    if problems:
        return None, problems
    return (figures[0], figures[1]), []


# --- The design's own rules ----------------------------------------------------


UNITS_MM = {"mm": 1.0, "": 1.0, "um": 0.001, "µm": 0.001, "nm": 1e-6, "mil": 0.0254, "mils": 0.0254, "in": 25.4}


def figure_mm(token: str) -> Optional[float]:
    match = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*([a-zµ]*)\s*", str(token))
    if not match or match.group(2) not in UNITS_MM:
        return None
    return float(match.group(1)) * UNITS_MM[match.group(2)]


def squash(text: str) -> str:
    return "".join(str(text).split())


def rule_name(rule: list) -> str:
    return str(rule[1]) if len(rule) > 1 and not isinstance(rule[1], list) else "(unnamed)"


def constraint_min(rule: list, kind: str):
    """The (min ...) token of the rule's `kind` constraint: None when absent, '' when it has no minimum."""
    for constraint in sexpr.children(rule, "constraint"):
        if len(constraint) > 1 and constraint[1] == kind:
            minimum = sexpr.child(constraint, "min")
            return minimum[1] if minimum is not None and len(minimum) > 1 else ""
    return None


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
            forms = sexpr.parse(handle.read(), comments=True)
    except (OSError, sexpr.SexprError) as error:
        return [], [Violation(design.project, "custom_rules", design.rules,
                              f"the custom rules file cannot be read ({error}); KiCad drops a rules file it cannot "
                              "parse without saying so, so none of its rules would be checked")]
    rules = [form for form in forms if sexpr.head(form) == "rule"]
    found = []
    for rule in rules:
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
    """What is wrong with the design's own Mains separation rule, if anything."""
    def fail(location: str, message: str) -> List[Violation]:
        return [Violation(design.project, "separation_rule", location, message)]

    form = squash(MAINS_CONDITION)
    if rules is None:
        return fail(design.rules,
                    "MAINS is present but the design has no custom rules file, so it states no separation "
                    f"rule; add one rule with condition {MAINS_CONDITION} holding both a clearance and a "
                    "creepage constraint")
    exact, narrowed = [], []
    for rule in rules:
        for condition in sexpr.children(rule, "condition"):
            text = squash(condition[1]) if len(condition) > 1 else ""
            if text == form:
                exact.append(rule)
            elif form in text or "hasNetclass('Mains')" in text:
                narrowed.append(rule)
    if not exact:
        if narrowed:
            names = ", ".join(f"'{rule_name(rule)}'" for rule in narrowed)
            return fail(f"{design.rules} rule {names}",
                        f"the Mains separation rule is narrowed by its condition or not in the required form; "
                        f"its condition must be exactly {MAINS_CONDITION}, with nothing narrowing it to a layer or an area")
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
    for kind, index in (("clearance", 0), ("creepage", 1)):
        token = constraint_min(rule, kind)
        if token is None:
            found += fail(where, f"the Mains separation rule holds no {kind} constraint; it must hold both clearance and creepage")
            continue
        declared = figure_mm(token) if token != "" else None
        if declared is None:
            found += fail(where, f"the Mains separation rule's {kind} minimum '{token}' cannot be read as a distance")
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


def at_text(node) -> str:
    at = sexpr.child(node, "at")
    if at is not None and len(at) > 2:
        return f"({at[1]}, {at[2]}) mm"
    return "(position not stated)"


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


# --- Running KiCad ------------------------------------------------------------


def appended_rules(signed: Optional[Tuple[float, float]], nonce: str) -> str:
    """The rules added after the design's own on the temporary copy, the signed one last of the design-facing ones.

    The marker matches every item, so its absence from KiCad's report shows
    KiCad did not load the rules file at all; the probe reports every item KiCad
    itself places in the Mains class. Both are assertions, which KiCad evaluates
    for every matching rule rather than letting a later one replace an earlier,
    so neither changes what any other rule enforces. Both are named for this run
    alone, from `nonce`, so no rule a design writes can pass for either and have
    its own findings taken for the check's.
    """
    text = "\n" + marker(nonce)
    text += f'(rule "{probe_rule(nonce)}"\n\t(condition "A.hasNetclass(\'Mains\')")\n\t(constraint assertion "false"))\n'
    if signed is not None:
        text += (f'(rule "{SIGNED_RULE}"\n\t(condition "{MAINS_CONDITION}")\n'
                 f'\t(constraint clearance (min {signed[0]:g}mm))\n\t(constraint creepage (min {signed[1]:g}mm)))\n')
    return text


def marker(nonce: str) -> str:
    return f'(rule "{marker_rule(nonce)}"\n\t(condition "A.Type != \'\'")\n\t(constraint assertion "false"))\n'


def fired(report: dict, rule: str) -> List[dict]:
    """The assertion failures KiCad reports for one of the check's own rules."""
    return [entry for entry in report.get("violations") or []
            if entry.get("type") == "assertion_failure" and f"(rule '{rule}')" in entry.get("description", "")]


def run_kicad(command: List[str], cwd: str, output: str = "report.json") -> Tuple[Optional[str], str]:
    """The text of the report a KiCad command writes to `output`, or why there is none."""
    output = os.path.join(cwd, output)
    if os.path.exists(output):
        os.remove(output)
    try:
        result = subprocess.run(command + ["-o", output], cwd=cwd, capture_output=True, text=True,
                                timeout=KICAD_TIMEOUT_S)
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
    if entry.get("severity") == "exclusion":
        message += " (the design marks this violation as excluded; an excluded violation still fails the check, so fix it)"
    return Violation(design.project, entry.get("type", "unknown"), location, message)


def ignored(design: Design, report: dict, setting: str) -> List[Violation]:
    return [Violation(design.project, "ignored_check", f"{design.project} {setting}.{entry.get('key', '?')}",
                      f"{entry.get('description', entry.get('key', '?'))}: the project sets this check to ignore, "
                      "whether or not that is KiCad's own default, so KiCad did not run it; set it to error or warning")
            for entry in report.get("ignored_checks") or []]


def exclusions(design: Design, project: dict) -> List[Violation]:
    """Violations the project file marks as excluded, each a failure whatever KiCad makes of the entry."""
    found = []
    lists = (
        ((project.get("board") or {}).get("design_settings") or {}).get("drc_exclusions") or [],
        (project.get("erc") or {}).get("erc_exclusions") or [],
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


def mains_nets_from(probe: List[dict], names: Set[str]) -> Set[str]:
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


def schematic_mains(netlist: list) -> Set[str]:
    """The nets KiCad's own netlist of the schematic puts in the Mains class, wherever the schematic says so."""
    return {name for name, (classes, _) in schematic_nets(netlist).items() if "Mains" in classes}


def quoted(text: str) -> str:
    """A string as KiCad's files write one between double quotes."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def project_mains(kicad_cli: str, scratch: str, project: str, names: Set[str], nonce: str,
                  version: str = "20260206") -> Tuple[Optional[Set[str]], str]:
    """The nets of `names` the project file's own net settings put in the Mains class, as KiCad resolves them.

    The project file assigns nets to classes by name and by pattern, and KiCad
    applies both to the layout, so the layout's membership alone cannot show
    what the project file says: the layout file can carry classes of its own,
    and a net the project names may have no copper. KiCad is therefore given
    the project file beside a board of nothing but one track per net name,
    holding no class of its own, and asked through the same probe which of
    those tracks it places in Mains. The marker shows the probe was loaded, so
    an empty answer means no net rather than an unread rules file. The board is
    written in `version`, the file format of the design's own layout, which the
    installed KiCad has already opened.
    """
    work = os.path.join(scratch, "net-settings")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(project, os.path.join(work, "nets.kicad_pro"))
    tracks = "".join(
        f'\t(segment (start 0 {2 * index}) (end 1 {2 * index}) (width 0.1) (layer "F.Cu") (net {quoted(name)}) '
        f'(uuid "00000000-0000-4000-8000-{index:012d}"))\n'
        for index, name in enumerate(sorted(names)))
    with open(os.path.join(work, "nets.kicad_pcb"), "w", encoding="utf-8") as handle:
        handle.write(f'(kicad_pcb\n\t(version {version})\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
                     '\t(general (thickness 1.6))\n\t(paper "A4")\n'
                     '\t(layers\n\t\t(0 "F.Cu" signal)\n\t\t(2 "B.Cu" signal)\n\t\t(25 "Edge.Cuts" user)\n\t)\n'
                     + tracks + ")\n")
    with open(os.path.join(work, "nets.kicad_dru"), "w", encoding="utf-8") as handle:
        handle.write("(version 1)\n" + appended_rules(None, nonce))
    report, why = run_report([kicad_cli, "pcb", "drc", "--format", "json", "--severity-all", "nets.kicad_pcb"], work)
    if report is None:
        return None, why
    if not fired(report, marker_rule(nonce)):
        return None, "KiCad did not load the rules that ask it which nets the project file puts in Mains"
    return mains_nets_from(fired(report, probe_rule(nonce)), names), ""


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


# --- One design ----------------------------------------------------------------


def check_design(design: Design, repository: Repository, kicad_cli: str, yaml, today: datetime.date,
                 already: List[Violation]) -> List[Violation]:
    root = repository.root
    found = list(already)
    if any(v.rule == "design_discovery" for v in already):
        return found
    try:
        with open(os.path.join(root, design.project), encoding="utf-8") as handle:
            project = json.load(handle)
        if not isinstance(project, dict):
            raise ValueError("it is not a JSON object")
    except (OSError, ValueError) as error:
        found.append(Violation(design.project, "design_unreadable", design.project,
                               f"the project file cannot be read ({error}); correct the file at that point, or "
                               "restore it from the repository's history"))
        return found

    variables = project.get("text_variables") or {}
    mains = variables.get("MAINS") if isinstance(variables, dict) else None
    not_for_manufacture = isinstance(variables, dict) and variables.get("NOT_FOR_MANUFACTURE") == "true"
    if mains not in ("present", "none"):
        said = "is not set" if mains is None else f"is '{mains}'"
        found.append(Violation(design.project, "mains_declaration", f"{design.project} text_variables.MAINS",
                               f"the project text variable MAINS {said}; set it to present if the board carries "
                               "mains, or none if it does not, since silence is never read as compliance"))

    found += exclusions(design, project)
    rules, hidden = read_rules(root, design, repository)
    found += hidden

    signed = None
    if mains == "present":
        record = find_record(root, design.directory, repository.tracked)
        signed, problems = read_record(yaml, root, design, record, not_for_manufacture, today,
                                       repository.uncommitted(record) if record is not None else None)
        found += problems
        found += mains_rule(design, rules, signed)

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
        rules_copy = os.path.join(copy, os.path.basename(design.rules))
        existing = "(version 1)\n"
        if rules is not None and os.path.exists(rules_copy):
            with open(rules_copy, encoding="utf-8", errors="replace") as handle:
                existing = handle.read()
        with open(rules_copy, "w", encoding="utf-8") as handle:
            handle.write(existing + appended_rules(signed, nonce))

        schematic = os.path.basename(design.schematic)
        layout = os.path.basename(design.layout)
        erc, why = run_report([kicad_cli, "sch", "erc", "--format", "json", "--severity-all", "--units", "mm", schematic], copy)
        netlist: Optional[Dict[str, Tuple[List[str], List[str]]]] = None
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
                netlist = schematic_nets(sexpr.parse_one(text)) if text is not None else None
            except sexpr.SexprError as error:
                why = f"KiCad's netlist could not be read ({error})"
            if netlist is None:
                found.append(Violation(design.project, "design_unreadable", design.schematic,
                                       f"the schematic's net classes cannot be read from KiCad's netlist: {why}"))

        drc, why = run_report([kicad_cli, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm",
                               "--schematic-parity", "--refill-zones", "--all-track-errors", layout], copy)
        if drc is None:
            found.append(Violation(design.project, "design_unreadable", design.layout,
                                   f"the layout cannot be checked: {why}"))
            return found

        markers, probe = fired(drc, marker_rule(nonce)), fired(drc, probe_rule(nonce))
        own = {id(entry) for entry in markers + probe}
        found += ignored(design, drc, "board.design_settings.rule_severities")
        for entry in drc.get("violations") or []:
            if id(entry) not in own:
                found.append(kicad_violation(design, entry, design.layout))
        for entry in (drc.get("unconnected_items") or []) + (drc.get("schematic_parity") or []):
            found.append(kicad_violation(design, entry, design.layout))

        if not markers:
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
        try:
            with open(os.path.join(copy, layout), encoding="utf-8") as handle:
                tree = sexpr.parse_one(handle.read())
        except (OSError, sexpr.SexprError) as error:
            found.append(Violation(design.project, "design_unreadable", design.layout,
                                   f"the layout cannot be read for its nets and clearance overrides ({error})"))
            return found

        # Three statements of which nets are in Mains, each as KiCad itself
        # resolves it: the layout's, which is what the separation rule is
        # enforced against; the schematic's; and the project file's net
        # settings, by name and by pattern. They must agree net for net.
        names = layout_nets(tree)
        on_layout = mains_nets_from(probe, names)
        assignments = (project.get("net_settings") or {}).get("netclass_assignments")
        named = set(names) | set(netlist) | (set(map(str, assignments)) if isinstance(assignments, dict) else set())
        version = sexpr.child(tree, "version")
        in_project, why = project_mains(kicad_cli, scratch, os.path.join(copy, os.path.basename(design.project)),
                                        named, nonce, str(version[1]) if version is not None and len(version) > 1 else "20260206")
        if in_project is None:
            found.append(Violation(design.project, "design_unreadable", f"{design.project} net_settings",
                                   f"the project file's net classes cannot be resolved by KiCad: {why}"))
            return found

    locate: Dict[str, Dict[str, str]] = {ON_LAYOUT: {}, IN_SCHEMATIC: {}, IN_PROJECT: {}}
    for entry in probe:
        for item in entry.get("items") or []:
            for net in mains_nets_from([{"items": [item]}], names):
                locate[ON_LAYOUT].setdefault(net, item_text(item))
    for net, (_, pins) in netlist.items():
        if pins:
            locate[IN_SCHEMATIC][net] = "in the schematic at " + ", ".join(pins[:4]) + (", ..." if len(pins) > 4 else "")
    for net in in_project:
        locate[IN_PROJECT][net] = f"{design.project} net_settings"
    sources = {ON_LAYOUT: on_layout, IN_SCHEMATIC: {net for net, (classes, _) in netlist.items() if "Mains" in classes},
               IN_PROJECT: in_project}
    found += mains_agreement(design, mains, sources, locate)

    if mains == "present" and not on_layout:
        found.append(Violation(design.project, "mains_declaration", design.layout,
                               "MAINS is present but no net on the layout is in the Mains net class, so the "
                               "separation rule would apply to nothing; assign every mains-referenced net to Mains"))
    if mains == "none" and on_layout:
        found.append(Violation(design.project, "mains_declaration", f"{design.project} text_variables.MAINS",
                               f"MAINS is none but the layout puts {', '.join(sorted(on_layout))} in the Mains net "
                               "class; set MAINS to present, or take them out of Mains"))

    if signed is not None:
        found += overrides(design, tree, signed[0], on_layout)
    return found


# --- The whole check ------------------------------------------------------------


def run(root: str, kicad_cli: str, git: str = "git", out=sys.stdout,
        today: Optional[datetime.date] = None) -> int:
    require_python()
    yaml = require_yaml()
    top = require_git(git, root)
    version = require_kicad(kicad_cli)
    today = today or datetime.date.today()

    files = tracked_files(git, top)
    repository = Repository(top, files, git)
    designs, orphans, problems = discover(top, files)
    print(f"Checking board designs under {top} with KiCad {version}", file=out)

    results: List[Tuple[str, List[Violation]]] = []
    for design in designs:
        results.append((design.project, check_design(design, repository, kicad_cli, yaml, today, problems[design.project])))
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
            for violation in violations:
                print(violation.line(), file=out)
        else:
            print(f"DESIGN | {clean(name)} | PASS", file=out)
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
    args = parser.parse_args(argv)
    try:
        return run(args.root, args.kicad_cli, args.git)
    except CannotRun as error:
        print(f"CANNOT RUN | {clean(str(error))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
