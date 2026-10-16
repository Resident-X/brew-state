#!/usr/bin/env python3
"""Run the tests covering the build-time check tools, one process per test module.

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


def default_workers(cpus: int | None) -> int:
    """How many modules run at once unless asked: the CPU count, at most the cap, at least one."""
    return min(cpus or 1, DEFAULT_WORKER_CAP)


def discover(directory: str) -> list[str]:
    """The test modules in a directory, largest first so the slowest start earliest."""
    paths = glob.glob(os.path.join(directory, "test*.py"))
    paths.sort(key=lambda path: (-os.path.getsize(path), path))
    return [os.path.basename(path)[: -len(".py")] for path in paths]


def run_module(module: str, directory: str) -> dict:
    started = time.monotonic()
    try:
        done = subprocess.run(
            [sys.executable, "-m", "unittest", module],
            cwd=directory, capture_output=True, text=True, check=False,
        )
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
        "--workers", type=int, default=default_workers(os.cpu_count()),
        help="how many modules to run at once (default: the CPU count, at most %d)" % DEFAULT_WORKER_CAP,
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    directory = os.path.abspath(args.tests)
    modules = discover(directory)
    if not modules:
        print(f"run_tool_tests: FAILED: no test module found in {directory}", file=sys.stderr)
        return 1

    started = time.monotonic()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_module, module, directory) for module in modules]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
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
