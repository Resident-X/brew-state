#!/usr/bin/env python3
"""Run a suite of tooling tests, one process per test module.

Both the firmware tooling's tests and the board tooling's tests run through this
one runner, so the handling of an empty run, a crash and an import failure lives
in one place.

The modules share nothing but the source tree they read, and most of their time
is spent waiting on child processes, so running them side by side finishes the
suite in about the time its slowest module takes rather than the sum of all of
them.

Each module is discovered by name (`test*.py` in the test directory) and run in
a process of its own with `python -m unittest`, so one module's import failure,
crash or stray global state cannot reach another. A line is printed as each
module finishes, the output of every module that did not pass follows, and the
closing line gives the totals.

Finding nothing to run is a failure: a directory with no test module, a module
that runs no test, or a count that cannot be read from a module's output all
fail, because a gate that finds nothing to run reports success without having
established anything.

By default a module runs as `python -m unittest <module>` from the test
directory. With `--cwd DIR` it runs as `python -m unittest discover -s <tests>
-p <module>.py` from DIR, the form of a serial `unittest discover` run from DIR,
with the environment the runner itself was given (git told not to sign), so a module sees what it sees
in that run.

A module that cannot run because a tool it needs is missing writes a line
beginning `CANNOT RUN |` to its error output. The runner writes each distinct
such line once to its own error output, at the start of a line, however many
modules report it, so whoever reads the run can tell a missing tool from a
finding.

Exit status is 0 only when at least one module was found, every module passed
and at least one test ran.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import glob
import os
import re
import subprocess
import sys
import time

TESTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests")

#: The most modules run at once unless asked otherwise. The modules are as much
#: waiting as working, so more than this only slows each of them.
DEFAULT_WORKER_CAP = 6


#: The start of the line a module writes when a tool it needs is missing.
MISSING_TOOL = "CANNOT RUN |"


def default_workers(cpus: int | None, cap: int = DEFAULT_WORKER_CAP) -> int:
    """How many modules run at once unless asked: the CPU count, at most the cap, at least one."""
    return min(cpus or 1, cap)


def missing_tool_lines(output: str) -> list[str]:
    """The lines of a module's output that report a missing tool, in order, as written."""
    return [line for line in output.splitlines() if line.startswith(MISSING_TOOL)]


def unsigned_environment(base: dict) -> dict:
    """The environment a module runs in: the runner's own, with git told not to sign commits or tags.

    A signing agent serialises the scratch commits modules make side by side, so
    they run unsigned, through git's environment config, appended to whatever
    count the environment already holds.
    """
    environment = dict(base)
    try:
        count = int(environment.get("GIT_CONFIG_COUNT", "0") or 0)
    except ValueError:
        count = 0
    for offset, key in enumerate(("commit.gpgsign", "tag.gpgsign")):
        environment[f"GIT_CONFIG_KEY_{count + offset}"] = key
        environment[f"GIT_CONFIG_VALUE_{count + offset}"] = "false"
    environment["GIT_CONFIG_COUNT"] = str(count + 2)
    return environment


def discover(directory: str) -> list[str]:
    """The test modules in a directory, largest first so the slowest start earliest."""
    paths = glob.glob(os.path.join(directory, "test*.py"))
    paths.sort(key=lambda path: (-os.path.getsize(path), path))
    return [os.path.basename(path)[: -len(".py")] for path in paths]


def run_module(module: str, directory: str, cwd: str | None = None) -> dict:
    started = time.monotonic()
    if cwd is None:
        command, where = [sys.executable, "-m", "unittest", module], directory
    else:
        command = [sys.executable, "-m", "unittest", "discover", "-s", directory, "-p", module + ".py"]
        where = cwd
    try:
        done = subprocess.run(command, cwd=where, capture_output=True, text=True, check=False,
                              env=unsigned_environment(os.environ))
        status, output = done.returncode, done.stdout + done.stderr
    except OSError as error:
        status, output = 1, f"could not start: {error}\n"
    counted = re.search(r"^Ran (\d+) tests? in ", output, re.MULTILINE)
    return {
        "module": module,
        "status": status,
        "tests": int(counted.group(1)) if counted else 0,
        "seconds": time.monotonic() - started,
        "output": output,
    }


def passed(result: dict) -> bool:
    return result["status"] == 0 and result["tests"] > 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tests", default=TESTS, help="the directory holding the test modules")
    parser.add_argument(
        "--workers", type=int, default=None,
        help="how many modules to run at once (default: the CPU count, at most the worker cap)",
    )
    parser.add_argument(
        "--worker-cap", type=int, default=DEFAULT_WORKER_CAP,
        help="the most modules run at once unless --workers asks (default: %d)" % DEFAULT_WORKER_CAP,
    )
    parser.add_argument(
        "--cwd", default=None,
        help="run each module by discovery from this directory, as a serial run from it does",
    )
    args = parser.parse_args(argv)
    if args.workers is None:
        args.workers = default_workers(os.cpu_count(), max(args.worker_cap, 1))
    if args.worker_cap < 1:
        parser.error("--worker-cap must be at least 1")
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    directory = os.path.abspath(args.tests)
    modules = discover(directory)
    if not modules:
        print(f"run_tool_tests: FAILED: no test module found in {directory}", file=sys.stderr)
        return 1

    cwd = os.path.abspath(args.cwd) if args.cwd else None
    started = time.monotonic()
    results = []
    reported = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_module, module, directory, cwd) for module in modules]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            for line in missing_tool_lines(result["output"]):
                if line not in reported:
                    reported.add(line)
                    print(line, file=sys.stderr, flush=True)
            verdict = "ok" if passed(result) else "FAILED"
            print(f"{verdict:6} {result['module']}: {result['tests']} tests in {result['seconds']:.1f}s", flush=True)

    failed = [result for result in results if not passed(result)]
    for result in sorted(failed, key=lambda result: result["module"]):
        print(f"\n--- {result['module']} (exit {result['status']}, {result['tests']} tests) ---")
        print(result["output"] or "(no output)")
        if result["status"] == 0 and result["tests"] == 0:
            print("the module ran no test")
    total = sum(result["tests"] for result in results)
    seconds = time.monotonic() - started
    summary = f"{len(results)} modules, {total} tests, {len(failed)} failed, {seconds:.1f}s on {args.workers} workers"
    if failed:
        print(f"run_tool_tests: FAILED: {summary}: " + ", ".join(sorted(r["module"] for r in failed)))
        return 1
    if total == 0:
        print(f"run_tool_tests: FAILED: {summary}: no test ran", file=sys.stderr)
        return 1
    print(f"run_tool_tests: PASSED: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
