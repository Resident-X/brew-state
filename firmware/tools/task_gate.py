"""Running one task as a step of a verification, and saying how it went.

The round gate and the complete verification both hand the task runner the
tasks they run rather than copying the commands behind them, and both report
each one the same way. What they share is here, so the two read alike and a
change to how a task is started reaches both.
"""

from __future__ import annotations

import subprocess
import sys


def say(line: str = "") -> None:
    print(line, flush=True)


def invoke(
    task: str, name: str, repo: str, label: str,
    arguments: tuple[str, ...] = (), env: dict | None = None,
) -> int:
    """Run one task and return its exit status, or 127 when it could not be started."""
    try:
        return subprocess.run([task, name, *arguments], cwd=repo, check=False, env=env).returncode
    except OSError as error:
        say(f"{label}: {name} could not be started ({error})")
        return 127


def run(task: str, name: str, repo: str, label: str, what: str) -> int:
    """Run one task, announcing it and its result, and return its exit status."""
    say(f"{label}: running {name} ({what})")
    status = invoke(task, name, repo, label)
    say(f"{label}: {name} {'passed' if status == 0 else f'FAILED with exit status {status}'}")
    return status


def capture(task: str, name: str, repo: str, label: str) -> tuple[int, str]:
    """Run one task and return its exit status and what it wrote to standard output.

    Its standard error passes through as it arrives. A task that could not be
    started has status 127 and no output.
    """
    try:
        done = subprocess.run(
            [task, name], cwd=repo, check=False, stdout=subprocess.PIPE, text=True, errors="replace"
        )
    except OSError as error:
        say(f"{label}: {name} could not be started ({error})")
        return 127, ""
    return done.returncode, done.stdout


def run_noting(
    task: str, name: str, repo: str, label: str, what: str, marker: str
) -> tuple[int, list[str]]:
    """Run one task as `run` does, and return its exit status and the lines it wrote to
    standard error that begin with the marker.

    Standard error is passed on line by line as it arrives, so a reader of the
    run sees what the task said while it says it; the lines noted are the ones
    the caller quotes in its own account of how the task ended.
    """
    say(f"{label}: running {name} ({what})")
    try:
        process = subprocess.Popen(
            [task, name], cwd=repo, stderr=subprocess.PIPE, text=True, errors="replace"
        )
    except OSError as error:
        say(f"{label}: {name} could not be started ({error})")
        say(f"{label}: {name} FAILED with exit status 127")
        return 127, []
    noted = []
    for line in process.stderr:
        sys.stderr.write(line)
        sys.stderr.flush()
        if line.startswith(marker):
            noted.append(line.strip())
    status = process.wait()
    say(f"{label}: {name} {'passed' if status == 0 else f'FAILED with exit status {status}'}")
    return status, noted
