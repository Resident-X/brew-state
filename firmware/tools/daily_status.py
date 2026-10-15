#!/usr/bin/env python3
"""The latest nightly verification result for main, read before any work is offered.

The nightly workflow runs the complete verification against main with nobody
watching, so its conclusion is the report. This reads the workflow's run
history through the GitHub command-line tool (`gh`, signed in with `gh auth
login`) and says what the latest completed run concluded.

The first line of output is a fixed verdict word, so a caller can branch on it
without parsing the rest:

  green    the latest completed run succeeded
  red      it concluded anything else, a timed-out run or one that never started included
  none     no run has completed (a fork or a new repository)
  unknown  the history could not be read, with the reason on the next line

Runs that were cancelled, skipped or neutral, and runs still in progress, say
nothing about main and are passed over in favour of an older completed run.
The exit status is zero whenever a result was read, red and none included, and
non-zero only for unknown, so a red result is told from an unreadable one by
the verdict word and never by the status. Nothing here reports green for a
history it could not read.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import task_gate

PASSED_OVER = ("cancelled", "skipped", "neutral")
FIELDS = "conclusion,status,headSha,url,createdAt"
HISTORY = "50"
TIMEOUT_SECONDS = 60


class Unreadable(Exception):
    """The run history could not be read; the message is the reason."""


def read_runs(gh: str, workflow: str, branch: str, timeout: float = TIMEOUT_SECONDS) -> list[dict]:
    command = [gh, "run", "list", "--workflow", workflow, "--branch", branch,
               "--limit", HISTORY, "--json", FIELDS]
    try:
        done = subprocess.run(
            command, check=False, capture_output=True, text=True, errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        raise Unreadable(f"the GitHub command-line tool '{gh}' is not installed or not on PATH") from None
    except OSError as error:
        raise Unreadable(f"the GitHub command-line tool '{gh}' could not be started ({error})") from None
    except subprocess.TimeoutExpired:
        raise Unreadable(f"'{gh} run list' did not answer within {timeout:g} seconds") from None
    if done.returncode != 0:
        detail = " ".join(done.stderr.split()) or "no message"
        raise Unreadable(
            f"'{gh} run list' failed with exit status {done.returncode} ({detail}); "
            f"check that gh is signed in (gh auth status) and that workflow '{workflow}' exists"
        )
    try:
        runs = json.loads(done.stdout)
    except json.JSONDecodeError as error:
        raise Unreadable(f"'{gh} run list' wrote output that is not JSON ({error})") from None
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        raise Unreadable(f"'{gh} run list' wrote JSON that is not a list of runs")
    return runs


def classify(runs: list[dict]) -> dict:
    """The verdict for a run history, newest first by creation time."""
    for index, run in enumerate(runs):
        for field in ("status", "createdAt"):
            value = run.get(field)
            if not isinstance(value, str) or not value:
                raise Unreadable(f"run {index} carries no usable '{field}'")
    ordered = sorted(runs, key=lambda run: run["createdAt"], reverse=True)
    for run in ordered:
        if run.get("status") != "completed":
            continue
        conclusion = run.get("conclusion")
        if not isinstance(conclusion, str) or not conclusion:
            raise Unreadable("a completed run carries no conclusion")
        if conclusion in PASSED_OVER:
            continue
        commit, url = run.get("headSha"), run.get("url")
        if not isinstance(commit, str) or not isinstance(url, str) or not commit or not url:
            raise Unreadable("the latest completed run carries no commit or link")
        return {
            "verdict": "green" if conclusion == "success" else "red",
            "conclusion": conclusion, "commit": commit, "url": url,
        }
    return {"verdict": "none", "reason": "no run of the workflow has completed"}


def report(result: dict, as_json: bool) -> None:
    if as_json:
        task_gate.say(json.dumps(result))
        return
    task_gate.say(result["verdict"])
    if "reason" in result:
        task_gate.say(f"reason: {result['reason']}")
    else:
        task_gate.say(f"conclusion: {result['conclusion']}")
        task_gate.say(f"commit: {result['commit']}")
        task_gate.say(f"run: {result['url']}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workflow", required=True, help="the name the nightly workflow declares")
    parser.add_argument("--branch", required=True, help="the branch whose runs are read")
    parser.add_argument("--gh", default="gh", help="the GitHub command-line tool (default: gh)")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_SECONDS,
                        help=f"seconds to wait for the tool to answer (default: {TIMEOUT_SECONDS})")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of text")
    arguments = parser.parse_args(argv)
    try:
        result = classify(read_runs(arguments.gh, arguments.workflow, arguments.branch, arguments.timeout))
    except Unreadable as reason:
        report({"verdict": "unknown", "reason": str(reason)}, arguments.json)
        return 1
    report(result, arguments.json)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
