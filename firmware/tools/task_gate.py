"""Running one task as a step of a verification, and saying how it went.

The round gate and the complete verification both hand the task runner the
tasks they run rather than copying the commands behind them, and both report
each one the same way. What they share is here, so the two read alike and a
change to how a task is started reaches both.
"""

from __future__ import annotations

import subprocess


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
