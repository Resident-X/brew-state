#!/usr/bin/env python3
"""Write the review folder of a committed schematic, for the schematic review to read, and add a view or a document to it.

The schematic review gives a reviewer the schematic, the netlist exported from it, the records the step reads, the drawing of
each sheet, the method, the hardware notes and the check's report, and nothing of the designer's reasoning. For a schematic
committed in a repository this command writes that, outside the repository: the schematic and its project files as the commit
holds them, the netlist as exported, every record the round reads as the commit holds it, the drawing of every sheet, the method
and the hardware notes, the check's report, the method's sections the review needs as an extract, and one round file that holds
the round's own fields, its number, the commit judged, the command the netlist was exported with and the records read. It holds
no session or notes file and no other file the commit does not hold. For a round after the first it also holds the earlier
rounds of the board's schematic review record as the commit holds them, since a fail's Why may cite a finding an earlier round
closed by a reason, and for a first round it holds no review record.

    schematic_review_folder.py --repo <repository> --commit <commit> --design <board folder from the root>
                               --out <new folder> --netlist <file> --netlist-command <text> --sheets <folder>
                               --check-report <file> --number N --record <file in the design's folder>...
                               [--documents-repo <repository> [--documents-commit <commit>]] [--json]
    schematic_review_folder.py --add-view <folder> --view <file> --view-command <text>
                               --cannot-judge-item <item> --cannot-judge-why <text> [--cannot-judge-target <name>] [--json]
    schematic_review_folder.py --add-document <folder> --document <text file> --source <where the figure comes from>
                               --cannot-judge-item <item> --cannot-judge-why <text> [--cannot-judge-target <name>] [--json]

The netlist is the file the round's first step exports, `kicad-cli sch export netlist`, and the sheets folder is the folder
`task hw:sheets` wrote the design's sheet drawings into; exporting the netlist, drawing the sheets and running the check are not
done here. The commit is an input: the netlist carries no record of the commit it came from, so the command holds it against the
committed schematic by what it names, and refuses one whose parts or sheets differ from the schematic's. Each --record names a
record by its path in the design's folder (a Markdown or YAML file the commit holds there); the round file lists it by its
path from the repository's root, and with the `accepted_on` the record gives when it has one.

The command refuses a folder inside the repository or the documents repository or inside a folder it is written from, a folder
that is a file or not empty, a commit the repository lacks, a design without one project file and its schematic, a schematic
that cannot be read, a missing, unreadable or unparseable netlist, a netlist whose parts or sheets differ from the committed
schematic's, a sheet with no drawing (or an empty one, or one that is a link), a missing check report, a record that is not a
Markdown or YAML file of the design at the commit, a record that is the schematic review record, a designer's notes or a
session record, a record given twice, a number that is not a whole number of one or more, a netlist command that is not one
line, no record, a method lacking a section the review needs, and, for a round after the first, a commit whose schematic review
record does not hold every earlier round.

--add-view and --add-document add a view or a text file holding a figure to a folder this command wrote, to resolve a cannot
judge, as the layout folder command does: the file goes to the added-views or added-documents folder and the item, the Why and
the view with its command or the document with its source are recorded in the resolutions file there; the round file is not
rewritten. --cannot-judge-target names the net, part or sheet the cannot judge was about, so that the merge marks that row alone
and not every row of the item. They refuse what the layout folder command's refuse, and a net, part or sheet the netlist and the
schematic do not name; --add-document also refuses an item the checklist does not hold, and the merge refuses a recorded item
that no unit judges, whichever mode recorded it.

Each cause is reported on one line beginning REFUSED, a RESULT line comes last, and the exit status is 0 when the folder is
written, 1 when the command refuses and 2 when git is missing. --json prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import board_check  # noqa: E402
import review_folder  # noqa: E402
import review_seed  # noqa: E402
import schematic_facts  # noqa: E402

Refused = review_folder.Refused
#: The review record the schematic review keeps, in the board's own folder.
RECORD = "schematic-review.md"
#: Where the folder holds the netlist, the sheet drawings and the check's report.
NETLIST = schematic_facts.NETLIST_FILE
SHEETS = "sheets"
CHECK_REPORT = review_folder.CHECK_REPORT
#: The method's sections the review needs, in the order its extract holds them.
SECTIONS = ("Schematic review", "Schematic drawing convention", "Circuit practice catalogue")
#: The files of the design the folder holds besides the records: the project and schematic files and the symbol libraries.
KICAD_FILES = (".kicad_pro", ".kicad_sch", ".kicad_sym")
#: A record is a Markdown or YAML file.
RECORD_SUFFIXES = (".md", ".yaml")
#: What a record may not be named: the review record, and the designer's reasoning, which the review never reads.
NOT_RECORDS = ("designer-notes*", "session*", "*-review.md")
ACCEPTED = re.compile(r"(?m)^accepted_on:[ \t]*['\"]?(\d{4}-\d{2}-\d{2})['\"]?[ \t]*$")


def method_extract(text: str) -> str:
    """The method's sections the schematic review needs, as the extract the shared context holds; a method that lacks one is a
    refusal naming it."""
    lacking = [heading for heading in SECTIONS if review_folder.method_section(text, heading) is None]
    if lacking:
        raise Refused([f"the method {review_folder.METHOD} has no `## {heading}` section, which the review's shared context holds; "
                       "give documents that hold it" for heading in lacking])
    return ("METHOD EXTRACT from " + review_folder.METHOD + ": the sections of the method that a schematic review needs, in this "
            "order.\n\n" + "\n".join(review_folder.method_section(text, heading) for heading in SECTIONS))


def extract_lacks(text: str) -> List[str]:
    """The sections of the review's extract that the text lacks."""
    return [heading for heading in SECTIONS if review_folder.method_section(text, heading) is None]


def drawing_name(design: str, sheet: str) -> str:
    """The file `task hw:sheets` names the drawing of a sheet: the design, then the names leading to the sheet."""
    return "-".join([design, *([] if sheet == design else sheet.split("/"))]).replace("/", "_").replace("\\", "_") + ".svg"


def given(name: str) -> bool:
    """Whether the review gives a reviewer the design's file `name`, by its path inside the design's folder, besides the records:
    its project, schematic and symbol library files and its library tables."""
    base = os.path.basename(name)
    return base.endswith(KICAD_FILES) or base in board_check.LIBRARY_TABLES


def not_a_record(name: str) -> bool:
    """Whether any component of the record's path, a folder or the file, is named for the designer's reasoning or a review record,
    without regard to case."""
    return any(re.fullmatch(pattern.replace(".", r"\.").replace("*", ".*"), part, re.I)
               for part in name.split("/") for pattern in NOT_RECORDS)


def record_refusals(records: Sequence[str], held: Dict[str, bytes], design: str) -> List[str]:
    """Why the records named are not records of the design at the commit."""
    found: List[str] = []
    if not records:
        found.append("no record is named; name each record the round reads with --record, by its path in the design's folder")
    seen: set = set()
    for name in records:
        shown = name if isinstance(name, str) else repr(name)
        if not isinstance(name, str) or not name.strip() or name != os.path.normpath(name).replace(os.sep, "/") \
                or os.path.isabs(name) or name.startswith("../") or name == "..":
            found.append(f"the record {shown!r} is not a path in the design's folder; give the path from the design's folder, "
                         "with no `..` and no leading slash")
            continue
        if name in seen:
            found.append(f"the record {name} is named twice; name each record once")
        seen.add(name)
        base = os.path.basename(name)
        if not name.endswith(RECORD_SUFFIXES):
            found.append(f"the record {name} is not a Markdown or YAML file; a record is a .md or .yaml file of the design")
        elif base.lower() == RECORD:
            found.append(f"the record {name} is the schematic review record, which the folder holds only as its earlier rounds "
                         "for a round after the first; leave it out")
        elif not_a_record(name):
            found.append(f"the record {name} is the designer's reasoning or a review record, which the review never reads; leave "
                         "it out")
        elif name not in held:
            found.append(f"the record {name} is not a file of {design} at the commit; commit it, or give the path of one the "
                         "commit holds")
    return found


def link_causes(path: str) -> List[str]:
    """Every symbolic link at or under `path`, a link carrying a file from outside the folder given into the review folder."""
    if not os.path.exists(path) and not os.path.islink(path):
        return []
    found = [path] if os.path.islink(path) else []
    for directory, names, files in os.walk(path):
        found += [os.path.join(directory, name) for name in names + files if os.path.islink(os.path.join(directory, name))]
    return [f"{link} is a symbolic link, which would put a file from outside the folder given into the review folder; give the "
            "files themselves" for link in found]


def drawing_causes(sheets: str, names: Sequence[str], design: str) -> List[str]:
    """Why the folder of sheet drawings lacks a drawing a sheet needs."""
    if not os.path.isdir(sheets):
        return [f"the sheets folder {sheets} is not a folder; draw the sheets with `task hw:sheets` and give the design's folder "
                "in its output"]
    found = []
    for sheet in sorted(names):
        file = os.path.join(sheets, drawing_name(design, sheet))
        if os.path.islink(file):
            continue
        if not os.path.isfile(file):
            found.append(f"the sheet {sheet} has no drawing: {drawing_name(design, sheet)} is not in {sheets}; draw the sheets "
                         "with `task hw:sheets` and give the design's folder in its output")
        elif os.path.getsize(file) == 0:
            found.append(f"the drawing {drawing_name(design, sheet)} of the sheet {sheet} is empty; draw the sheets again with "
                         "`task hw:sheets`")
    return found + link_causes(sheets)


def netlist_causes(path: Optional[str], design: str, parts: Sequence[str], sheets: Sequence[str]) -> Tuple[List[str], str]:
    """Why the netlist given is no netlist of the committed schematic, and its text."""
    if not path or not os.path.isfile(path):
        return [f"the netlist {path} does not exist; export it with `kicad-cli sch export netlist` from the committed "
                "schematic, and give the file"], ""
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        named = schematic_facts.netlist_names(text, design, f"the netlist {path}")
    except (OSError, UnicodeDecodeError) as error:
        return [f"the netlist {path} cannot be read ({error}); export it again"], ""
    except schematic_facts.FactsProblem as error:
        return [f"{error}; export it again with `kicad-cli sch export netlist`"], ""
    found = []
    for what, netlist, schematic in (("parts", named.parts, set(parts)), ("sheets", named.sheets, set(sheets))):
        extra, lacking = sorted(netlist - schematic), sorted(schematic - netlist)
        if extra or lacking:
            found.append(f"the netlist's {what} differ from the committed schematic's"
                         + (f": it holds {', '.join(extra)} the schematic lacks" if extra else "")
                         + (f"{';' if extra else ':'} it lacks {', '.join(lacking)} the schematic holds" if lacking else "")
                         + "; it was not exported from this commit's schematic, so export it again from the commit")
    return found, text


def separate_causes(out: str, repo: str, documents_repo: str, inputs: Sequence[Optional[str]]) -> List[str]:
    found = []
    for name, where in (("repository", repo), ("documents repository", documents_repo)):
        if review_seed.inside(out, where):
            found.append(f"the review folder {out} is inside the {name} {where}; a reviewer working there could read the "
                         "design as committed and the earlier rounds' verdicts, so give a folder outside it")
    if os.path.isfile(out):
        found.append(f"the review folder {out} is a file; give a new or empty folder")
    elif os.path.isdir(out) and os.listdir(out):
        found.append(f"the review folder {out} already holds files; give a new or empty folder")
    for path in inputs:
        if path and os.path.exists(path) and review_seed.inside(out, os.path.abspath(path)):
            found.append(f"the review folder {out} is inside {path}, one of the files or folders it is written from; give a "
                         "folder outside every input")
    return found


def committed_schematic(repo: str, commit: str, design: str) -> Dict[str, Any]:
    """The commit's full id, the design's files and its name, or the causes the commit holds no schematic."""
    resolved = review_folder.git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
    if resolved.returncode != 0:
        raise Refused([f"the commit {commit} is not in the repository {repo}; give a commit it holds"])
    sha = resolved.stdout.strip()
    held = {name: content for name, content in review_seed.archived(repo, sha, design.rstrip("/")).items()}
    prefix = design.rstrip("/") + "/"
    files = {name[len(prefix):]: content for name, content in held.items() if name.startswith(prefix)}
    projects = [name for name in files if "/" not in name and name.endswith(".kicad_pro")]
    if len(projects) != 1 or f"{projects[0][:-len('.kicad_pro')]}.kicad_sch" not in files:
        raise Refused([f"the commit {commit} holds no schematic at {design}: it needs the design folder's one KiCad project and "
                       f"the schematic beside it, and holds {len(projects)} projects there"
                       + ("" if not projects else f" and no {projects[0][:-len('.kicad_pro')]}.kicad_sch")])
    return {"sha": sha, "files": files, "design": projects[0][:-len(".kicad_pro")]}


def schematic_of(committed: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    """The committed schematic's parts and sheets, and the causes it cannot be read for them."""
    files = committed["files"]

    def read(path: str) -> Optional[str]:
        if path not in files:
            return None
        try:
            return files[path].decode("utf-8")
        except UnicodeDecodeError:
            raise schematic_facts.FactsProblem(f"the schematic file {path} is not UTF-8 text")
    try:
        parts, sheets = schematic_facts.schematic_names(read, committed["design"])
    except schematic_facts.FactsProblem as error:
        return [], [], [f"{error}; commit a schematic KiCad wrote"]
    return sorted(parts), sorted(sheets), []


def record_line(design_path: str, name: str, content: bytes) -> str:
    """The round file's line for a record: its path from the repository's root, and the `accepted_on` it gives when it has one."""
    accepted = ACCEPTED.search(content.decode("utf-8", errors="replace"))
    return f"{design_path}/{name}" + (f" (accepted_on {accepted.group(1)})" if accepted else "")


def write_folder(args: argparse.Namespace, out: str, repo: str, documents_repo: Optional[str]) -> Dict[str, Any]:
    """The review folder, or a refusal naming every cause."""
    design = args.design.rstrip("/") if args.design else ""
    values: Dict[str, Any] = {"number": args.number, "netlist": args.netlist_command, "records": [],
                              "commit": "0" * 7}
    causes: List[str] = []
    committed: Dict[str, Any] = {}
    try:
        committed = committed_schematic(repo, args.commit, design)
        values["commit"] = committed["sha"]
    except Refused as error:
        causes += error.causes
    records = args.record or []
    parts: List[str] = []
    sheets: List[str] = []
    readable = False
    if committed:
        causes += record_refusals(records, committed["files"], design)
        values["records"] = [record_line(design, name, committed["files"].get(name, b"")) for name in records
                             if isinstance(name, str)]
        parts, sheets, problems = schematic_of(committed)
        causes += problems
        readable = not problems
    else:
        values["records"] = [f"{design}/{name}" for name in records]
    causes += separate_causes(out, repo, documents_repo or review_seed.REPO, [args.netlist, args.sheets, args.check_report])
    causes += review_folder.round_problems(values, review_folder.SCHEMATIC_FIELDS)
    netlist_text = ""
    if readable:
        found, netlist_text = netlist_causes(args.netlist, committed["design"], parts, sheets)
        causes += found
        causes += drawing_causes(args.sheets, sheets, committed["design"])
    elif not args.netlist or not os.path.isfile(args.netlist):
        causes.append(f"the netlist {args.netlist} does not exist; export it with `kicad-cli sch export netlist` from the committed "
                      "schematic, and give the file")
    for what, path in (("netlist", args.netlist), ("check report", args.check_report)):
        if path and os.path.islink(path):
            causes.append(f"the {what} {path} is a symbolic link, which would put a file from outside the files given into the "
                          "review folder; give the file itself")
    if not args.check_report or not os.path.isfile(args.check_report):
        causes.append(f"the check's report {args.check_report} does not exist; run the pre-order check on the committed design and "
                      "give its report")
    record = None
    if committed and isinstance(args.number, int) and not isinstance(args.number, bool) and args.number > 1:
        text = committed["files"].get(RECORD, b"").decode("utf-8", errors="replace")
        record = review_folder.earlier_rounds(text, args.number)
        if record is None:
            causes.append(f"round {args.number} cites the earlier rounds of the review record, and the commit's {RECORD} holds "
                          "none; commit the record with the earlier rounds before the round")
        else:
            missing = sorted(set(range(1, args.number)) - set(review_folder.earlier_numbers(text, args.number)))
            if missing:
                causes.append(f"round {args.number} cites the earlier rounds of the review record, which must hold rounds 1 to "
                              f"{args.number - 1}, and the commit's {RECORD} lacks round " + ", ".join(str(n) for n in missing)
                              + "; commit the record with every earlier round before the round")
    documents: Dict[str, bytes] = {}
    extract = ""
    try:
        documents = review_seed.documents(documents_repo, args.documents_commit)
    except review_seed.Refused as error:
        causes.append(str(error))
    if documents and review_folder.METHOD in documents:
        try:
            extract = method_extract(documents[review_folder.METHOD].decode("utf-8"))
        except Refused as error:
            causes += error.causes
        except UnicodeDecodeError:
            causes.append(f"the method {review_folder.METHOD} is not UTF-8 text; give documents that hold it")
    if causes:
        raise Refused(causes)
    os.makedirs(out, exist_ok=True)
    try:
        written = []
        for name, content in committed["files"].items():
            if given(name) or name in records:
                target = os.path.join(out, design, name)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as handle:
                    handle.write(content)
                written.append(name)
        if record is not None:
            with open(os.path.join(out, design, RECORD), "w", encoding="utf-8") as handle:
                handle.write(record)
        for document, content in documents.items():
            os.makedirs(os.path.dirname(os.path.join(out, document)), exist_ok=True)
            with open(os.path.join(out, document), "wb") as handle:
                handle.write(content)
        with open(os.path.join(out, NETLIST), "w", encoding="utf-8", newline="") as handle:
            handle.write(netlist_text)
        os.makedirs(os.path.join(out, SHEETS))
        for sheet in sheets:
            shutil.copyfile(os.path.join(args.sheets, drawing_name(committed["design"], sheet)),
                            os.path.join(out, SHEETS, drawing_name(committed["design"], sheet)))
        shutil.copyfile(args.check_report, os.path.join(out, CHECK_REPORT))
        with open(os.path.join(out, review_folder.METHOD_EXTRACT), "w", encoding="utf-8", newline="") as handle:
            handle.write(extract)
        content = review_folder.round_content(review_folder.SCHEMATIC_FIELDS, values)
        with open(os.path.join(out, review_folder.ROUND_FILE), "w", encoding="utf-8") as handle:
            handle.write(review_folder.settled(content))
        review_seed.same_time(out)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    return {"result": "WRITTEN", "folder": out, "commit": committed["sha"], "design": design, "design_files": sorted(written),
            "documents": sorted(documents), "sheets": sorted(drawing_name(committed["design"], sheet) for sheet in sheets),
            "round": {key: content.get(key) for key in review_folder.SCHEMATIC_FIELDS}}


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="the repository holding the schematic")
    parser.add_argument("--commit", help="the commit that holds the schematic, which the round judges")
    parser.add_argument("--design", help="the board's folder, by its path from the repository's root")
    parser.add_argument("--out", help="the review folder to write, new or empty, outside the repository")
    parser.add_argument("--netlist", help="the netlist exported from the committed schematic")
    parser.add_argument("--netlist-command", help="the command the netlist was exported with, as it was run, as one line")
    parser.add_argument("--sheets", help="the folder `task hw:sheets` wrote the design's sheet drawings into")
    parser.add_argument("--check-report", help="the pre-order check's report on the committed design")
    parser.add_argument("--record", action="append", help="a record the round reads, by its path in the design's folder; repeat for each")
    parser.add_argument("--number", type=int, help="the round's number")
    parser.add_argument("--documents-repo", help="the repository the method and the hardware notes are taken from (default: this one)")
    parser.add_argument("--documents-commit", help="the commit of --documents-repo they are taken from (default: HEAD)")
    parser.add_argument("--add-view", help="a review folder this command wrote, to add a rendered view to")
    parser.add_argument("--view", help="the rendered view file to add")
    parser.add_argument("--view-command", action="append", help="the command the view was rendered with, as run (once)")
    parser.add_argument("--add-document", help="a review folder this command wrote, to add a text file holding a figure to")
    parser.add_argument("--document", help="the text file to add, holding the figure or passage a cannot judge's Why asks for")
    parser.add_argument("--source", help="where the figure in the document comes from, as one line")
    parser.add_argument("--cannot-judge-item", help="the item whose cannot judge asked for the view or document")
    parser.add_argument("--cannot-judge-why", help="that cannot judge's Why")
    parser.add_argument("--cannot-judge-target", help="the net, part or sheet the cannot judge was about")
    parser.add_argument("--json", action="store_true", help="print the report as one JSON document")
    args = parser.parse_args(argv)
    try:
        if args.add_view and args.add_document:
            parser.error("--add-view and --add-document are separate modes; give one")
        if args.add_view:
            report = review_folder.add_view(args)
        elif args.add_document:
            report = review_folder.add_document(args)
        else:
            missing = [f"--{name.replace('_', '-')}" for name in ("repo", "commit", "design", "out", "netlist", "netlist_command",
                                                                 "sheets", "check_report", "number")
                       if getattr(args, name) in (None, "")]
            if missing:
                parser.error(f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required")
            report = write_folder(args, os.path.abspath(args.out), os.path.abspath(args.repo),
                                  os.path.abspath(args.documents_repo) if args.documents_repo else None)
    except Refused as error:
        report = {"result": "REFUSED", "refusals": error.causes, "detail": "nothing was written"}
    except FileNotFoundError as error:
        if error.filename == "git":
            report = {"result": "CANNOT RUN", "refusals": [], "detail": "git is not on the search path; install it"}
        else:
            raise
    return review_folder.finish(report, args.json, out)


if __name__ == "__main__":
    sys.exit(main())
