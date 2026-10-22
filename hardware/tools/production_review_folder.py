#!/usr/bin/env python3
"""Write the review folder of a real order's production-files check, for the check to read.

The method's ordering step exports a committed board's production files, draws the layers and the footprints, renders the
design's own views and obtains the assembler's preview. This command takes those and the commit they were made from and
writes the folder the production-files check reads, outside the repository: the placement file, the parts list, the Gerber and
drill files, the image of every layer and of the drill file with its index, the footprint drawings with their index and the
rule for reading a rotation against them, the design's rendered views and placement view, the assembler's preview as supplied,
the design's parts specification record as the commit holds it, the method, the hardware notes and the manufacturer's record,
and one round file holding the commit judged, the tools, the commands and the line saying what the preview is. It holds no
check record, no session or notes file and no other file the commit does not hold. The folder is assembled by the function the
production-files seeding script writes its own folder with, so a real order's folder and the proof's are the same assembly.

    production_review_folder.py --repo <repository> --commit <commit> --design <board folder from the root>
                                --out <new folder> --work <folder the production files were exported and drawn into>
                                --views <views folder> --placement <placement view folder> --preview <preview folder>
                                --preview-note <text> --tools <text> --command <text>...
                                [--documents-repo <repository> [--documents-commit <commit>]] [--json]

The work folder holds placement.csv, parts-list.csv, gerbers/ (the Gerber and drill files), layers/ and footprints/ (each with
its index.txt and index.json), as the ordering step's first two steps write them. Exporting and drawing are not done here, and
neither is obtaining the preview. The commit is an input: the exported files carry no record of the commit they came from, so
the command records the one it is given and does not claim to detect a mismatch.

Each cause is reported on one line beginning REFUSED, a RESULT line comes last, and the exit status is 0 when the folder is
written, 1 when the command refuses and 2 when git is missing. --json prints the same facts as one JSON document.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS_DIR)

import production_files  # noqa: E402
import production_seed  # noqa: E402
import review_folder  # noqa: E402
import review_seed  # noqa: E402

Refused = review_folder.Refused
#: The check record the check writes, which a real order's folder must not hold.
CHECK_RECORD = "production-files-check.md"
#: The folder of the assembler's preview, as supplied.
PREVIEW = review_folder.PREVIEW
#: The inputs of the work folder: the files and the folders, each with the folders that carry an index.
WORK_FILES = (production_seed.PLACEMENT_FILE, production_seed.PARTS_FILE)
WORK_FOLDERS = (production_seed.GERBERS, production_seed.LAYERS, production_seed.FOOTPRINTS)
INDEXED = (production_seed.LAYERS, production_seed.FOOTPRINTS)
RECORD = production_seed.RECORD


def links_in(path: str) -> List[str]:
    """Every symbolic link at or under `path`; a link would carry a file from outside the folder given into the review folder."""
    found = []
    if os.path.islink(path):
        return [path]
    for directory, names, files in os.walk(path):
        found += [os.path.join(directory, name) for name in names + files if os.path.islink(os.path.join(directory, name))]
    return found


def files_in(path: str) -> List[str]:
    return [os.path.join(directory, name) for directory, _, names in os.walk(path) for name in names]


def documents_at(repo: Optional[str], commit: Optional[str]) -> Dict[str, bytes]:
    """The ordering step's documents, the method, the manufacturer's record and the hardware notes, as `commit` of `repo`
    holds them or, without a repository, as this repository's last commit does; a document the commit lacks is a refusal."""
    if repo is None:
        return production_seed.documents()
    found = {}
    for document in production_seed.DOCUMENTS:
        held = review_seed.archived(repo, commit or "HEAD", document)
        if document not in held:
            raise Refused([f"the documents repository {repo} at {commit or 'HEAD'} holds no {document}; give a repository and "
                           "commit that hold the method, the manufacturer's record and the hardware notes"])
        found[document] = held[document]
    return found


def input_refusals(args: argparse.Namespace, work: str) -> List[str]:
    """Why the folders and files given are not what the check reads."""
    found = []
    if not os.path.isdir(work):
        return [f"the work folder {work} is not a folder; give the folder the production files were exported and drawn into"]
    for name in WORK_FILES:
        if not os.path.isfile(os.path.join(work, name)):
            found.append(f"the work folder {work} holds no {name}; export it with the ordering step's first step")
    for name in WORK_FOLDERS:
        folder = os.path.join(work, name)
        if not os.path.isdir(folder) or not files_in(folder):
            found.append(f"the work folder {work} holds no {name}/ with files in it; run the ordering step's first two steps")
    for name in INDEXED:
        for index in ("index.txt", "index.json"):
            if os.path.isdir(os.path.join(work, name)) and not os.path.isfile(os.path.join(work, name, index)):
                found.append(f"the work folder's {name}/ holds no {index}; draw it with the ordering step's second step")
    layers_index = os.path.join(work, production_seed.LAYERS, "index.json")
    if os.path.isdir(os.path.join(work, production_seed.GERBERS)) and os.path.isfile(layers_index):
        try:
            with open(layers_index, encoding="utf-8") as handle:
                images = json.load(handle).get("images")
        except (OSError, ValueError, RecursionError, AttributeError):
            images = None  # an index that cannot be read is the layer images index's own refusal, made when the check starts
        if isinstance(images, list):
            for name in review_folder.unlisted_fabrication_files(os.path.join(work, production_seed.GERBERS), images):
                found.append(f"{production_seed.GERBERS}/{name} in the work folder {work} is a file the layer images index lists as "
                             "no image's source, so no unit would judge it and no row could name it; draw the layers again with "
                             "the ordering step's second step, or leave the file out")
    if os.path.isfile(os.path.join(work, WORK_FILES[0])):
        try:
            production_files.read_placement_file(os.path.join(work, WORK_FILES[0]))
        except production_files.Refused as error:
            found.append(f"{error}; export it again with the ordering step's first step")
    for name, path in (("views", args.views), ("placement view", args.placement)):
        if not os.path.isfile(os.path.join(path, "index.txt")):
            found.append(f"the {name} folder {path} is missing or holds no index.txt; render it with the ordering step's "
                         "last command, and give that folder")
    preview = args.preview
    if not os.path.isdir(preview) or not files_in(preview):
        found.append(f"the preview folder {preview} is missing or holds no file; save the assembler's preview as images with "
                     "the ordering step's third step, and give that folder")
    given = [work, args.views, args.placement, preview]
    for path in given:
        for link in links_in(path) if os.path.exists(path) else []:
            found.append(f"{link} is a symbolic link, which would put a file from outside the folder given into the review "
                         "folder; give the files themselves")
        for held in files_in(path) if os.path.isdir(path) else []:
            if os.path.basename(held).casefold() == CHECK_RECORD.casefold():
                found.append(f"{held} is a check record, which the review folder must not hold; leave it out of the folders given")
    return found


def refusals(args: argparse.Namespace, out: str, repo: str, documents_repo: str, values: Dict[str, Any]) -> List[str]:
    found = []
    for name, where in (("repository", repo), ("documents repository", documents_repo)):
        if review_seed.inside(out, where):
            found.append(f"the review folder {out} is inside the {name} {where}; a reviewer working there could read the "
                         "design as committed and the earlier orders' records, so give a folder outside it")
    if os.path.isfile(out):
        found.append(f"the review folder {out} is a file; give a new or empty folder")
    elif os.path.isdir(out) and os.listdir(out):
        found.append(f"the review folder {out} already holds files; give a new or empty folder")
    found += review_folder.round_problems(values, review_folder.PRODUCTION_FIELDS)
    for path in (args.work, args.views, args.placement, args.preview):
        if path and os.path.exists(path) and review_seed.inside(out, os.path.abspath(path)):
            found.append(f"the review folder {out} is inside {path}, one of the folders it is written from; give a folder "
                         "outside every input")
    return found


def write_folder(args: argparse.Namespace, out: str, repo: str, documents_repo: Optional[str]) -> Dict[str, Any]:
    """The review folder, or a refusal naming every cause."""
    work = os.path.abspath(args.work)
    args.work, args.views, args.placement, args.preview = (work, os.path.abspath(args.views), os.path.abspath(args.placement),
                                                           os.path.abspath(args.preview))
    values: Dict[str, Any] = {"tools": args.tools, "commands": args.command or [], "preview": args.preview_note}
    causes: List[str] = []
    board: Dict[str, Any] = {}
    try:
        board = review_folder.committed_board(repo, args.commit, args.design)
        values["commit"] = board["sha"]
    except Refused as error:
        causes += error.causes
        values["commit"] = "0" * 7  # a commit that does not exist is the cause; the field itself is not reported twice
    causes += refusals(args, out, repo, documents_repo or review_seed.REPO, values)
    causes += input_refusals(args, work)
    record = None
    if board:
        held = review_seed.archived(repo, board["sha"], f"{args.design.rstrip('/')}/{RECORD}")
        record = next(iter(held.values()), None) if len(held) == 1 else None
        if record is None:
            causes.append(f"the commit holds no {RECORD} at {args.design}; the check compares the parts list with the design's "
                          "parts specification record, so commit it with the design")
    documents: Dict[str, bytes] = {}
    try:
        documents = documents_at(documents_repo, args.documents_commit)
    except Refused as error:
        causes += error.causes
    if causes:
        raise Refused(causes)

    def draw(folder: str, production: str) -> Tuple[bool, str]:
        for source, target in ((os.path.join(work, production_seed.LAYERS), os.path.join(production, production_seed.LAYERS)),
                               (os.path.join(work, production_seed.FOOTPRINTS),
                                os.path.join(production, production_seed.FOOTPRINTS)),
                               (args.views, os.path.join(folder, production_seed.VIEWS)),
                               (args.placement, os.path.join(folder, production_seed.PLACEMENT)),
                               (args.preview, os.path.join(folder, PREVIEW))):
            shutil.copytree(source, target, symlinks=True)
        with open(os.path.join(folder, review_folder.ROUND_FILE), "w", encoding="utf-8") as handle:
            handle.write(review_folder.settled(review_folder.round_content(review_folder.PRODUCTION_FIELDS, values)))
        return True, ""
    def text(name: str) -> str:
        with open(os.path.join(work, name), encoding="utf-8", newline="") as handle:
            return handle.read()
    try:
        os.makedirs(out, exist_ok=True)
        production_seed.write_folder(out, args.design.rstrip("/"), record, documents, text(production_seed.PLACEMENT_FILE),
                                     text(production_seed.PARTS_FILE), os.path.join(work, production_seed.GERBERS), draw)
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    return {"result": "WRITTEN", "folder": out, "commit": board["sha"], "design": args.design,
            "round": {key: values[key] for key in review_folder.PRODUCTION_FIELDS}}


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="the repository holding the board")
    parser.add_argument("--commit", help="the commit the production files were exported from, which the check judges")
    parser.add_argument("--design", help="the board's folder, by its path from the repository's root")
    parser.add_argument("--out", help="the review folder to write, new or empty, outside the repository")
    parser.add_argument("--work", help="the folder the production files were exported and drawn into")
    parser.add_argument("--views", help="the folder the views command rendered the design's views into")
    parser.add_argument("--placement", help="the folder the placement command rendered the placement view into")
    parser.add_argument("--preview", help="the folder holding the assembler's preview as saved")
    parser.add_argument("--preview-note", help="what the preview is, with its date and the assembler's name, as one line")
    parser.add_argument("--tools", help="the versions of kicad-cli, gerbonara and resvg, as one line")
    parser.add_argument("--command", action="append", help="a command of the ordering step's first two steps, as run; repeat for each")
    parser.add_argument("--documents-repo", help="the repository the method and the notes are taken from (default: this one)")
    parser.add_argument("--documents-commit", help="the commit of --documents-repo they are taken from (default: HEAD)")
    parser.add_argument("--json", action="store_true", help="print the report as one JSON document")
    args = parser.parse_args(argv)
    missing = [f"--{name.replace('_', '-')}" for name in ("repo", "commit", "design", "out", "work", "views", "placement", "preview")
               if not getattr(args, name)]
    if missing:
        parser.error(f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required")
    try:
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
