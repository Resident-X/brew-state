#!/usr/bin/env python3
"""The complete verification: every declared gate, each run to completion, every failure named.

The complete verification is what a single machine runs to establish that main
holds: every build, every check, every test, every host executable, the target
artefact under emulation, every board design checked with KiCad's own rule
checks, the tests of the board tooling without those that run the seeded-fault
proof (which stays on demand), and the full sweep of the plant model's
arithmetic. It runs nightly, and nobody is watching it when it does, so a gate
that fails early must not hide what the gates after it would have found. Every
gate runs, in the order declared, whether or not an earlier one failed, and the
run fails naming each gate that did.

The gates are named by the task runner, which hands them to this script, so the
list exists in one place and a gate added later is added there. The task runner
and the gates come from that declaration alone: words added to the task's
command line arrive after a '--' that ends the declaration, and the only thing
they may ask for is a gate left out. The hosted
nightly leaves the sweep out by name and runs it in its sharded form instead;
leaving out a name that is not a declared gate is refused, because a misspelt
name would otherwise leave nothing out and say it had. A run with a gate left
out says so in its closing lines, so it never reads as the complete
verification passing.

Every gate is run afresh: nothing here reads an earlier run's verdict.
"""

from __future__ import annotations

import argparse
import os
import sys

import task_gate

LABEL = "verification"


def _duplicates(names: list[str]) -> list[str]:
    seen, repeated = set(), []
    for name in names:
        if name in seen and name not in repeated:
            repeated.append(name)
        seen.add(name)
    return repeated


def verify(task: str, gates: list[str], left_out: list[str], repo: str) -> int:
    """Run every declared gate not left out, print the account, and return the exit status."""
    running = [name for name in gates if name not in left_out]
    omitted = [name for name in gates if name in left_out]
    task_gate.say(
        f"{LABEL}: the complete verification declares {len(gates)} gate(s): {', '.join(gates)}. "
        "Every gate runs to completion, even after an earlier one fails."
    )
    if omitted:
        task_gate.say(f"{LABEL}: LEAVING OUT, as asked: {', '.join(omitted)}")

    results = []
    for position, name in enumerate(running, start=1):
        what = f"gate {position} of {len(running)}"
        results.append((name, task_gate.run(task, name, repo, LABEL, what)))

    failed = [(name, status) for name, status in results if status != 0]
    task_gate.say()
    if failed:
        task_gate.say(
            f"VERIFICATION FAILED: {len(failed)} of the {len(running)} gate(s) that ran failed: "
            + ", ".join(f"{name} (exit status {status})" for name, status in failed)
            + "."
        )
    elif omitted:
        task_gate.say(
            f"VERIFICATION PASSED WITH GATES LEFT OUT: every gate that ran passed, but "
            f"{len(omitted)} declared gate(s) did not run, so this is NOT the complete "
            "verification passing."
        )
    else:
        task_gate.say("COMPLETE VERIFICATION PASSED: every declared gate ran and passed.")
    task_gate.say(
        "Gates that ran: "
        + ", ".join(f"{name} ({'passed' if status == 0 else 'FAILED'})" for name, status in results)
        + "."
    )
    task_gate.say(
        f"Gates left out: {', '.join(omitted)}." if omitted else "Gates left out: none."
    )
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0], allow_abbrev=False,
        usage="%(prog)s --task TASK --gate GATE [--gate GATE ...] [--repo REPO] "
              "-- [--leave-out GATE ...]",
    )
    parser.add_argument("--task", required=True, help="the task runner executable")
    parser.add_argument(
        "--gate", action="append", required=True,
        help="a gate of the complete verification, in the order it runs",
    )
    parser.add_argument("--repo", default=os.getcwd(), help="the repository root (default: here)")
    # Whoever runs the task adds to its command line, and the task hands those
    # words on after its own. They are kept apart from the declaration rather
    # than parsed with it, so a forwarded --task or --gate cannot replace the
    # task runner or the declared gates: after the separator, leaving a gate out
    # is the one thing that can be asked for.
    forwarded_parser = argparse.ArgumentParser(
        prog=f"{parser.prog} ... --", allow_abbrev=False, add_help=False,
    )
    forwarded_parser.add_argument("--leave-out", action="append", default=[], metavar="GATE")

    if "--" not in argv:
        parser.error(
            "the declaration must end with '--', after which only --leave-out may follow"
        )
    separator = argv.index("--")
    arguments = parser.parse_args(argv[:separator])
    forwarded, refused = forwarded_parser.parse_known_args(argv[separator + 1:])
    if refused:
        parser.error(
            f"only --leave-out GATE may follow the declaration, not: {' '.join(refused)}"
        )

    repeated = _duplicates(arguments.gate)
    if repeated:
        parser.error(f"a gate is declared more than once: {', '.join(repeated)}")
    unknown = [name for name in forwarded.leave_out if name not in arguments.gate]
    if unknown:
        parser.error(
            f"--leave-out names no declared gate: {', '.join(unknown)} "
            f"(the declared gates are {', '.join(arguments.gate)})"
        )
    twice = _duplicates(forwarded.leave_out)
    if twice:
        parser.error(f"--leave-out names a gate more than once: {', '.join(twice)}")
    if all(name in forwarded.leave_out for name in arguments.gate):
        parser.error("--leave-out leaves out every declared gate, so nothing would be verified")
    return verify(arguments.task, arguments.gate, forwarded.leave_out, arguments.repo)


if __name__ == "__main__":
    sys.exit(main())
