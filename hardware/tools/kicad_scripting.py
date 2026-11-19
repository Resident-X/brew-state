#!/usr/bin/env python3
"""Running KiCad's scripting interface (`pcbnew`) for the layout tools.

`pcbnew` is importable only from the interpreter KiCad bundles, never from the
interpreter that runs the tooling. A layout tool that needs it therefore runs a
worker in a subprocess of that interpreter, found through the environment
variable KICAD_PYTHON (or the tool's `--kicad-python` argument, which wins), and
reads one line of JSON back. When the variable is unset or names nothing that
can import `pcbnew`, the tool cannot run and says so naming the variable.

A worker is a function in the tool's own file, run as `python -I FILE --worker
ARGS...`; in that mode it may import only `pcbnew` and the standard library,
and it prints exactly one JSON object as the last line of its standard output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board_check import CannotRun, clean  # noqa: E402

#: The environment variable naming KiCad's bundled Python interpreter.
VARIABLE = "KICAD_PYTHON"

#: The seconds a worker may run before it is taken as hung; a whole board refill takes a few minutes at most.
WORKER_TIMEOUT = 1800

WHERE = ("the interpreter KiCad bundles, the one that can `import pcbnew` (hardware/README.md gives its usual "
         "location on each operating system)")


def interpreter(given: Optional[str] = None) -> str:
    """The KiCad-bundled interpreter to run workers in: `given` (the tool's argument), else $KICAD_PYTHON.

    Raises CannotRun, naming KICAD_PYTHON, when neither is set or the one set
    names a file that is missing or cannot import `pcbnew`.
    """
    path = given if given else os.environ.get(VARIABLE, "")
    source = "the --kicad-python argument" if given else f"the environment variable {VARIABLE}"
    if not path:
        raise CannotRun(f"{VARIABLE} is not set, so KiCad's scripting interface cannot be run; set {VARIABLE} to "
                        f"{WHERE}, or give --kicad-python")
    if not os.path.isfile(path) or not os.access(path, os.X_OK):
        raise CannotRun(f"{source} names '{path}', which is not a runnable file; set {VARIABLE} to {WHERE}")
    try:
        probe = subprocess.run([path, "-I", "-c", "import pcbnew"], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CannotRun(f"{source} names '{path}', which could not be run ({error}); set {VARIABLE} to {WHERE}") from error
    if probe.returncode != 0:
        raise CannotRun(f"{source} names '{path}', which cannot import pcbnew; set {VARIABLE} to {WHERE}")
    return path


def run_worker(python: str, script: str, arguments: List[str]) -> dict:
    """Run `script --worker ARGUMENTS` in `python`; the JSON object it prints last.

    Raises CannotRun when the worker does not finish or prints no such object.
    """
    try:
        done = subprocess.run([python, "-I", script, "--worker"] + list(arguments), capture_output=True, text=True,
                              timeout=WORKER_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CannotRun(f"the KiCad scripting worker could not be run in {python} ({error})") from error
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    try:
        reply = json.loads(lines[-1])
    except (IndexError, ValueError):
        reply = None
    if done.returncode != 0 or not isinstance(reply, dict):
        tail = " ".join(done.stderr.split())[-400:]
        raise CannotRun(f"the KiCad scripting worker failed in {python} (exit {done.returncode}): {tail or 'no output'}")
    return reply


def emit(report: dict, out, as_json: bool) -> None:
    """Print a report, {"result", "detail", "findings": [{"finding", "item", "detail"}], ...}, as JSON or as lines.

    The text form is one `FINDING | item | detail` line for each finding and a
    `RESULT | result | detail` line last, as every board command writes its report.
    """
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True), file=out)
        return
    for finding in report["findings"]:
        print(f"{finding['finding']} | {clean(finding['item'])} | {clean(finding['detail'])}", file=out)
    print(f"RESULT | {report['result']} | {clean(report['detail'])}", file=out)


def cannot_run(error: CannotRun, out, as_json: bool) -> int:
    """Report that a tool cannot run, in the tool's format, and the exit status for it."""
    message = clean(str(error))
    if as_json:
        print(json.dumps({"result": "CANNOT RUN", "detail": message, "findings": []}, indent=2), file=out)
    print(f"CANNOT RUN | {message}", file=sys.stderr)
    return 2
