#!/usr/bin/env python3
"""The chain runner: a board built by ordered scripted steps, proven to be built the same way every time.

A board's copper is built from its placed board by a chain of steps -- a script
for each block, a refill, a silkscreen rebuild -- each reading the board the
step before wrote and writing the next. The chain is trusted only if running it
again gives the same board, so this runner runs the whole chain twice from the
board given, in two working folders of its own, records the sha256 of the board
every step writes, and compares the two runs step by step. It writes the final
board to `--output` only when the runs agree on every step, and when they do
not it fails naming the first step whose two outputs differ, which is where the
nondeterminism enters; the later steps differ as a consequence.

The steps are a JSON file, a list of {"name": ..., "command": [...]} or an object
holding that list under "steps". A command is an argument list run without a
shell, in the step's own folder, with these placeholders replaced in each argument:

    {input}        the board the step reads
    {output}       where the step writes the board
    {steps_dir}    the folder of the steps file, so a step names its scripts relative to it
    {kicad_python} KiCad's bundled Python, from KICAD_PYTHON or `--kicad-python`

A project file (`.kicad_pro`) and custom rules file (`.kicad_dru`) beside the
board with its name are copied beside every step's input and output, as KiCad
reads them from the board's folder. A step that exits non-zero or writes no board
fails the chain, naming the step. An empty list of steps is refused, since a chain
of nothing proves nothing.

    chain_runner.py --board B.kicad_pcb --steps STEPS.json --output OUT.kicad_pcb [--work DIR] [--kicad-python PATH] [--format text|json]

Exit status: 0 when the board is reproduced and written, 1 when a step fails, the
runs differ or an input is refused, 2 when the chain cannot run, for example
because a step names {kicad_python} and KICAD_PYTHON is unset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kicad_scripting  # noqa: E402
from board_check import CannotRun  # noqa: E402

#: The files beside a board, by the board's own name, that KiCad reads with it.
COMPANIONS = (".kicad_pro", ".kicad_dru")

#: The seconds one step may run.
STEP_TIMEOUT = 3600

PLACEHOLDERS = ("{input}", "{output}", "{steps_dir}", "{kicad_python}")


class Refused(Exception):
    """An input the chain will not run on, with the reason."""


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_steps(path: str) -> List[dict]:
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"the steps file {path} cannot be read ({error})") from error
    steps = document.get("steps") if isinstance(document, dict) else document
    if not isinstance(steps, list):
        raise Refused(f"the steps file {path} is not a list of steps, or an object holding one under \"steps\"")
    if not steps:
        raise Refused(f"the steps file {path} lists no steps; a chain of nothing proves nothing, so list the steps to run")
    names = set()
    for index, step in enumerate(steps, 1):
        name = step.get("name") if isinstance(step, dict) else None
        command = step.get("command") if isinstance(step, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise Refused(f"step {index} of {path} has no name")
        if name in names:
            raise Refused(f"the step name '{name}' is used twice in {path}; name each step once")
        names.add(name)
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            raise Refused(f"step '{name}' of {path} has no command as a non-empty list of strings")
    return steps


def uses_kicad_python(steps: List[dict]) -> bool:
    return any("{kicad_python}" in part for step in steps for part in step["command"])


def stage(board: str, folder: str, name: str) -> str:
    """Copy `board`, and its companion files, into `folder` under `name`; the board's new path."""
    os.makedirs(folder)
    stem = os.path.splitext(board)[0]
    for suffix in COMPANIONS:
        if os.path.isfile(stem + suffix):
            shutil.copyfile(stem + suffix, os.path.join(folder, os.path.splitext(name)[0] + suffix))
    target = os.path.join(folder, name)
    shutil.copyfile(board, target)
    return target


def run_step(step: dict, index: int, source: str, folder: str, steps_dir: str, python: str, name: str) -> Tuple[str, Optional[str]]:
    """Run one step on the board at `source`: (the board it wrote, why it failed or None)."""
    inputs = stage(source, os.path.join(folder, "in"), name)
    out_dir = os.path.join(folder, "out")
    os.makedirs(out_dir)
    for suffix in COMPANIONS:
        companion = os.path.splitext(inputs)[0] + suffix
        if os.path.isfile(companion):
            shutil.copyfile(companion, os.path.join(out_dir, os.path.splitext(name)[0] + suffix))
    output = os.path.join(out_dir, name)
    values = {"{input}": inputs, "{output}": output, "{steps_dir}": steps_dir, "{kicad_python}": python}
    command = []
    for part in step["command"]:
        for token, value in values.items():
            part = part.replace(token, value)
        command.append(part)
    try:
        done = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=STEP_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        return output, f"the command could not be run ({error})"
    if done.returncode != 0:
        tail = " ".join((done.stderr or done.stdout).split())[-300:]
        return output, f"exited {done.returncode}: {tail or 'no output'}"
    if not os.path.isfile(output):
        return output, f"exited 0 but wrote no board to {output}"
    return output, None


def chain(board: str, steps_path: str, output: str, work: str, python: str) -> dict:
    """Run the chain twice; the report."""
    steps = read_steps(steps_path)
    if not os.path.isfile(board):
        raise Refused(f"the board {board} cannot be read (no such file)")
    steps_dir = os.path.dirname(os.path.abspath(steps_path))
    name = os.path.basename(board)
    report: dict = {"board": board, "steps_file": steps_path, "input_sha256": sha256(board), "steps": [], "findings": []}
    current = [board, board]
    for index, step in enumerate(steps, 1):
        outputs = []
        for run in (1, 2):
            folder = os.path.join(work, f"run{run}", f"{index:02d}-{step['name']}")
            made, why = run_step(step, index, current[run - 1], folder, steps_dir, python, name)
            if why is not None:
                report["findings"].append({"finding": "FAILED", "item": f"step {index} {step['name']} (run {run})", "detail": why})
                report.update(result="FAIL", detail=f"step '{step['name']}' failed, so the board is not reproduced")
                return report
            outputs.append(made)
        first, second = sha256(outputs[0]), sha256(outputs[1])
        report["steps"].append({"index": index, "name": step["name"], "sha256_first": first, "sha256_second": second,
                                "identical": first == second})
        if first != second:
            report["findings"].append({"finding": "DIFFERS", "item": f"step {index} {step['name']}",
                                       "detail": f"the board it wrote differs between the two runs (sha256 {first[:12]} then "
                                                 f"{second[:12]}); this is the first such step, so the nondeterminism enters here"})
            report.update(result="FAIL", detail=f"step '{step['name']}' is the first whose output differs between two runs")
            return report
        current = outputs
    try:
        shutil.copyfile(current[0], output)
    except OSError as error:
        raise Refused(f"the board cannot be written to {output} ({error})") from error
    report.update(result="REPRODUCED", output=output, output_sha256=report["steps"][-1]["sha256_first"],
                  detail=f"{len(steps)} step{'s' if len(steps) != 1 else ''} run twice with identical output at every step; "
                         f"board sha256 {report['steps'][-1]['sha256_first']} written to {output}")
    return report


def emit(report: dict, out, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True), file=out)
        return
    for step in report["steps"]:
        print(f"STEP | {step['index']} {step['name']} | {step['sha256_first']} | "
              + ("identical on both runs" if step["identical"] else f"second run {step['sha256_second']}"), file=out)
    kicad_scripting.emit({"findings": report["findings"], "result": report["result"], "detail": report["detail"]}, out, False)


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--board", required=True, help="the placed board (.kicad_pcb) the chain starts from")
    parser.add_argument("--steps", required=True, help="the steps, a JSON file")
    parser.add_argument("--output", required=True, help="where the final board is written, only when the two runs agree")
    parser.add_argument("--work", default=None, help="a folder to run in and keep (default: a temporary folder, removed after)")
    parser.add_argument("--kicad-python", default=None,
                        help=f"KiCad's bundled Python for {{kicad_python}} (default: the environment variable {kicad_scripting.VARIABLE})")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    as_json = args.format == "json"
    try:
        python = ""
        try:
            if uses_kicad_python(read_steps(args.steps)):
                python = kicad_scripting.interpreter(args.kicad_python)
        except Refused:
            pass
        if args.work is not None:
            if os.path.isdir(args.work) and os.listdir(args.work):
                raise Refused(f"the work folder {args.work} is not empty; give a new or empty folder")
            os.makedirs(args.work, exist_ok=True)
            report = chain(args.board, args.steps, args.output, args.work, python)
        else:
            with tempfile.TemporaryDirectory(prefix="chain-runner-") as work:
                report = chain(args.board, args.steps, args.output, work, python)
    except Refused as error:
        report = {"board": args.board, "steps_file": args.steps, "steps": [], "result": "REFUSED",
                  "detail": "the chain was not run", "findings": [{"finding": "REFUSED", "item": args.steps, "detail": str(error)}]}
        emit(report, out, as_json)
        return 1
    except CannotRun as error:
        return kicad_scripting.cannot_run(error, out, as_json)
    emit(report, out, as_json)
    return 0 if report["result"] == "REPRODUCED" else 1


if __name__ == "__main__":
    sys.exit(main())
