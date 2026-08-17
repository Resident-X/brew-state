#!/usr/bin/env python3
"""Sweep the plant model's arithmetic for mutants the tests do not notice.

The hand-written mutations next door in `mutate.py` prove that named defects are
caught. They cannot prove anything about the defects nobody thought to name, and
a list of specific catches is the weakest possible evidence that a class of
defect is covered -- it establishes exactly the members of the list. This
generates the class instead: every comparison, every arithmetic operator, every
increment and decrement in the swept sources is altered in turn, and the test
suite is run against each alteration. A mutant no test notices is a change to
the model's behaviour that the suite would let through.

What the sweep reports is not a defect count, and the difference matters enough
to be built into the tool rather than left to whoever reads the output. Some
mutants cannot change any observable behaviour -- a comparison at a boundary
both sides of which evaluate alike, an operator on a value the caller has
already constrained. Those are equivalent mutants, and no test can kill them,
so counting them as gaps would be reporting a defect that does not exist and
inviting somebody to write a test asserting something untrue to make the number
go down. Deciding which is which is a judgement about what the code means, and
this tool does not make it.

So every survivor has to be accounted for by hand, once, in the triage record,
and the sweep compares what it found against what that record says. A survivor
nobody has judged is reported as exactly that -- an unreviewed count -- and
fails the run because it is unreviewed, not because it is a defect. A survivor
judged equivalent, with the reasoning written down, passes. A survivor judged a
real gap fails until the gap is closed. And a judgement about a mutant that no
longer exists fails too: the record going stale is how a triage decision quietly
outlives the code it was made about.

Suites are swept one at a time because the build produces one test program at a
time, and a mutant killed by any suite is killed: the sources swept here are
compiled into more than one runner, and asking only one of them would report a
gap that another suite covers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import mull_toolchain  # noqa: E402

#: Exit codes. The distinction is the same one the other checks here draw, and
#: it is load-bearing: `mutate.py` treats "could not look" as a failure to
#: establish anything rather than as a catch, and a sweep that reported an
#: absent toolchain as a clean run would be the same mistake.
FOUND_THE_PROBLEM = 1
COULD_NOT_LOOK = 2

#: Where the judgement about each surviving mutant is written down.
TRIAGE_RECORD = "mutation_triage.yaml"

#: What a survivor may be judged to be.
#:
#: `analysis` is the third answer because this project verifies in more than one
#: way, and the sweep is deliberately run with the other way switched off. A
#: mutant whose only effect is to read or write outside something is invisible
#: here however good the tests are -- no assertion can see it -- while being
#: exactly what the sanitized build aborts on. Calling that a gap would ask
#: somebody to write a test that cannot exist; calling it equivalent would be
#: untrue, because the mutant does change what the program does. It is recorded
#: as caught by the other tier, which is a claim with a condition attached: some
#: test has to actually reach the line, or nothing is watching it there either.
EQUIVALENT = "equivalent"
GAP = "gap"
ANALYSIS = "analysis"
VERDICTS = (EQUIVALENT, GAP, ANALYSIS)

#: The statuses the runner reports for a mutant the tests noticed. Anything else
#: -- survived, not covered, not run -- is a mutant nothing objected to, and is
#: counted as surviving rather than quietly dropped: a mutant on a line no test
#: reaches is exactly as unnoticed as one every test ran past.
KILLED_STATUSES = ("Killed", "Timeout", "Crashed")


class SweepError(Exception):
    """The sweep cannot be run, or cannot be trusted if it were."""


def load_yaml(path: str) -> object:
    """Read a YAML document, reporting the absence of the parser as a blocker.

    PyYAML is not in the standard library and is not guaranteed on a host that
    can otherwise run everything else here, so its absence is reported as being
    unable to look rather than as a stack trace.
    """
    try:
        import yaml
    except ImportError as error:  # pragma: no cover -- depends on the host
        raise SweepError(
            "PyYAML is needed to read the sweep's configuration and triage record, and is not "
            "installed. Install it (pip install pyyaml, or the python3-yaml package)."
        ) from error
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError as error:
        raise SweepError(f"{path} is not there") from error
    except Exception as error:
        raise SweepError(f"{path} cannot be read: {error}") from error


def scope_patterns(project: str) -> tuple[list[str], list[str]]:
    """The include and exclude patterns the sweep's configuration declares."""
    path = os.path.join(project, mull_toolchain.CONFIG_NAME)
    document = load_yaml(path)
    if not isinstance(document, dict):
        raise SweepError(f"{path} does not declare a mapping of settings")
    includes = document.get("includePaths") or []
    excludes = document.get("excludePaths") or []
    if not includes:
        raise SweepError(
            f"{path} declares no includePaths, so the sweep would draw mutants from every source "
            "compiled into the test runner rather than from the ones it is scoped to"
        )
    # Compiled here rather than where they are matched, so a pattern that is not
    # a pattern is reported against the file that declares it. Left to the match
    # site it would surface as an interpreter traceback naming neither.
    for group, patterns in (("includePaths", includes), ("excludePaths", excludes)):
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as error:
                raise SweepError(
                    f"{path}: {group} entry '{pattern}' is not a usable pattern: {error}"
                ) from error
    return list(includes), list(excludes)


def in_scope(path: str, includes: list[str], excludes: list[str]) -> bool:
    """Whether a source file is one the sweep would draw mutants from."""
    if not any(re.search(pattern, path) for pattern in includes):
        return False
    return not any(re.search(pattern, path) for pattern in excludes)


def sources_under(root: str) -> list[str]:
    """Every C source and header under a directory, as absolute paths."""
    found = []
    for directory, _, names in os.walk(root):
        for name in names:
            if name.endswith((".c", ".h")):
                found.append(os.path.join(directory, name))
    return sorted(found)


def scope_problems(project: str, includes: list[str], excludes: list[str]) -> list[str]:
    """Whether the declared scope is the one the sweep is supposed to have.

    The patterns are checked against the tree rather than read, because a
    pattern is only right or wrong with respect to the files it meets. Two
    things would make a sweep report a number that means nothing: taking in the
    tests, which are the oracle, and taking in nothing at all.
    """
    problems = []

    test_root = os.path.join(project, "test")
    if os.path.isdir(test_root):
        swept_tests = [
            os.path.relpath(path, project)
            for path in sources_under(test_root)
            if in_scope(path, includes, excludes)
        ]
        if swept_tests:
            problems.append(
                "the scope takes in test sources, which are what decides whether a mutant was "
                f"noticed: {', '.join(swept_tests)}"
            )

    source_root = os.path.join(project, "src")
    swept = [path for path in sources_under(source_root) if in_scope(path, includes, excludes)]
    if not swept:
        problems.append(
            "the scope takes in no source under src/, so the sweep would report a score over an "
            "empty population and pass without having mutated anything"
        )

    return problems


def suites(environment: build_environments.Environment) -> list[str]:
    """The test suites this environment runs, in the order it declares them."""
    declared = environment.get("test_filter")
    return [suite.strip() for suite in declared.split(",") if suite.strip()]


def build_and_run(project: str, pio: str, environment: str, suite: str) -> None:
    """Build one suite under the mutation toolchain and require it to pass unmutated.

    A suite that already fails would make every mutant under it look caught, for
    the same reason `mutate.py` runs each of its commands once before breaking
    anything. Nothing the sweep reported afterwards would mean anything.
    """
    result = subprocess.run(
        [pio, "test", "-e", environment, "-f", suite], cwd=project, check=False
    )
    if result.returncode != 0:
        raise SweepError(
            f"'{suite}' does not pass under the mutation build before anything is mutated, so "
            "every mutant under it would be indistinguishable from one the tests caught"
        )


def artefact(project: str, environment: str) -> str:
    """The test program the build just produced."""
    path = os.path.join(project, build_environments.BUILD_ROOT, environment, "program")
    if not os.path.isfile(path):
        raise SweepError(f"the mutation build left no test program at {path}")
    return path


def run_mull(runner: str, program: str, config: str, project: str) -> dict:
    """Run every mutant the program carries, and read the report back."""
    with tempfile.TemporaryDirectory() as reports:
        environment = dict(os.environ, MULL_CONFIG=config)
        result = subprocess.run(
            [
                runner,
                program,
                "--reporters",
                "Elements",
                "--report-dir",
                reports,
                "--report-name",
                "sweep",
            ],
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        report = os.path.join(reports, "sweep.json")
        if not os.path.isfile(report):
            raise SweepError(
                f"the mutant runner produced no report ({runner} exited {result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        with open(report, "r", encoding="utf-8") as handle:
            return json.load(handle)


def identify(project: str, source: str, mutant: dict) -> str:
    """A name for one mutant that survives being run on another machine.

    The runner's own identifier carries the absolute path of the source, which
    would make a triage record valid only in the directory it was written in.
    The path is made relative to the project so the record travels with it.
    """
    start = mutant["location"]["start"]
    relative = os.path.relpath(source, project)
    return f"{mutant['mutatorName']}:{relative}:{start['line']}:{start['column']}"


def collect(project: str, report: dict, found: dict[str, dict]) -> None:
    """Fold one suite's report into what every suite has reported so far.

    A mutant killed by any suite is killed. The sources swept here are compiled
    into more than one test runner, so a mutant surviving the suite that does
    not exercise it is not evidence of anything until every suite has been
    asked.
    """
    for source, contents in report.get("files", {}).items():
        for mutant in contents.get("mutants", []):
            name = identify(project, source, mutant)
            status = mutant.get("status", "")
            existing = found.get(name)
            killed = status in KILLED_STATUSES or (existing or {}).get("killed", False)
            found[name] = {
                "id": name,
                "source": os.path.relpath(source, project),
                "line": mutant["location"]["start"]["line"],
                "column": mutant["location"]["start"]["column"],
                "mutator": mutant["mutatorName"],
                "replacement": mutant.get("replacement", ""),
                "status": status,
                "killed": killed,
            }


def read_triage(project: str) -> dict[str, dict]:
    """Every judgement recorded about a surviving mutant, by mutant."""
    path = os.path.join(project, TRIAGE_RECORD)
    if not os.path.isfile(path):
        return {}
    document = load_yaml(path)
    if document is None:
        return {}
    if not isinstance(document, dict):
        raise SweepError(f"{path} does not declare a mapping of mutants to judgements")
    entries = document.get("survivors")
    if entries is None:
        raise SweepError(f"{path} declares no 'survivors' mapping")
    if not isinstance(entries, dict):
        raise SweepError(f"{path}: 'survivors' is not a mapping of mutants to judgements")

    judgements = {}
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            raise SweepError(f"{path}: '{name}' does not record a verdict and a reason")
        verdict = str(entry.get("verdict", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        if verdict not in VERDICTS:
            raise SweepError(
                f"{path}: '{name}' is judged '{verdict}', which is not one of "
                f"{', '.join(VERDICTS)}"
            )
        if not reason:
            raise SweepError(
                f"{path}: '{name}' is judged '{verdict}' with no reason. The reason is the whole "
                "content of the judgement -- a verdict nobody has to justify is a way of marking "
                "a survivor read without reading it."
            )
        judgements[str(name)] = {"verdict": verdict, "reason": reason}
    return judgements


def classify(
    found: dict[str, dict], judgements: dict[str, dict]
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Split what the sweep found against what has been judged about it.

    Four answers, and the last two are separated for a reason worth stating. A
    judgement about a mutant that is still in the population but was killed this
    time is simply no longer needed -- some test now covers it -- and saying so
    is useful while failing over it would mean the record had to be edited every
    time the suite got better. A judgement about a mutant that is not in the
    population at all is the dangerous one: the code it was made about has moved
    or gone, so the decision has outlived its subject and reads like a statement
    about whatever is there now.

    That distinction is not academic. A mutant whose only effect is a read or
    write outside an object is killed or not according to whether the access
    happens to disturb something the tests observe, which is a property of how
    the compiler laid the frame out -- so the same mutant survives on one host
    and is killed on another. Judging staleness by survival alone made this
    record valid only on the machine it was written on.
    """
    survivors = {name: mutant for name, mutant in found.items() if not mutant["killed"]}
    unreviewed = sorted(name for name in survivors if name not in judgements)
    gaps = sorted(
        name for name in survivors if judgements.get(name, {}).get("verdict") == GAP
    )
    retired = sorted(name for name in judgements if name in found and found[name]["killed"])
    stale = sorted(name for name in judgements if name not in found)
    return unreviewed, gaps, stale, retired


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument(
        "--pio",
        default=os.environ.get("PIO", os.path.expanduser("~/.platformio/penv/bin/pio")),
        help="the PlatformIO executable",
    )
    parser.add_argument(
        "--survivors-only",
        action="store_true",
        help="report what survived without judging it against the triage record",
    )
    args = parser.parse_args(argv)

    project = os.path.realpath(args.project)

    try:
        declared = build_environments.load(project)
    except build_environments.ConfigurationError as error:
        print(f"mull_sweep: {error}", file=sys.stderr)
        return COULD_NOT_LOOK

    environments = build_environments.mutation_environments(declared)
    if not environments:
        # The same rule every discovering gate here follows. An environment
        # excused from the gates covering every host build, with nothing on the
        # other side of the exclusion driving it, would be a way out of both.
        print(
            "mull_sweep: no environment in "
            f"{build_environments.PROJECT_CONFIG} declares itself built for the mutation sweep, "
            "so this would report success over an empty population",
            file=sys.stderr,
        )
        return FOUND_THE_PROBLEM

    try:
        includes, excludes = scope_patterns(project)
        problems = scope_problems(project, includes, excludes)
        if problems:
            print("mull_sweep: the sweep's scope would not mean what it says", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return FOUND_THE_PROBLEM

        toolchain = mull_toolchain.resolved(
            warn=lambda note: print(f"mull_sweep: {note}", file=sys.stderr)
        )
        judgements = read_triage(project)
    except (SweepError, mull_toolchain.ToolchainError) as error:
        print(f"mull_sweep: {error}", file=sys.stderr)
        return COULD_NOT_LOOK

    config = os.path.join(project, mull_toolchain.CONFIG_NAME)
    found: dict[str, dict] = {}

    try:
        for environment in environments:
            for suite in suites(environment):
                print(f"mull_sweep: {environment.name}:{suite}", flush=True)
                build_and_run(project, args.pio, environment.name, suite)
                report = run_mull(toolchain["runner"], artefact(project, environment.name), config, project)
                collect(project, report, found)
    except SweepError as error:
        print(f"mull_sweep: {error}", file=sys.stderr)
        return COULD_NOT_LOOK

    if not found:
        print(
            "mull_sweep: the swept sources produced no mutants at all, which means the scope or "
            "the instrumentation is not doing what it says rather than that the code is perfect",
            file=sys.stderr,
        )
        return FOUND_THE_PROBLEM

    survivors = {name: mutant for name, mutant in found.items() if not mutant["killed"]}
    killed = len(found) - len(survivors)
    score = round(100 * killed / len(found))

    print(
        f"mull_sweep: {len(found)} mutants, {killed} killed by the tests, "
        f"{len(survivors)} survived ({score}% killed)"
    )

    if args.survivors_only:
        for mutant in sorted(survivors.values(), key=lambda m: (m["source"], m["line"], m["column"])):
            print(
                f"  {mutant['source']}:{mutant['line']}:{mutant['column']} "
                f"{mutant['mutator']} -> {mutant['replacement']}   [{mutant['id']}]"
            )
        return 0

    unreviewed, gaps, stale, retired = classify(found, judgements)

    if unreviewed:
        # Deliberately a count of survivors, not of defects. Which of these is a
        # gap and which cannot change any behaviour is exactly what nobody has
        # decided yet, and printing it as a defect count would be asserting the
        # thing this run cannot establish.
        print(
            f"mull_sweep: {len(unreviewed)} surviving mutant(s) have not been reviewed. This is a "
            "count of survivors and not a count of defects: until each is judged, whether it "
            f"could change any behaviour at all is undecided. Record each in {TRIAGE_RECORD}.",
            file=sys.stderr,
        )
        for name in unreviewed:
            mutant = survivors[name]
            print(
                f"  {mutant['source']}:{mutant['line']}:{mutant['column']} "
                f"{mutant['mutator']} -> {mutant['replacement']}\n    {name}",
                file=sys.stderr,
            )

    if gaps:
        print(
            f"mull_sweep: {len(gaps)} surviving mutant(s) are recorded as real gaps in what the "
            "tests catch",
            file=sys.stderr,
        )
        for name in gaps:
            print(f"  {name}\n    {judgements[name]['reason']}", file=sys.stderr)

    if stale:
        print(
            f"mull_sweep: {len(stale)} judgement(s) in {TRIAGE_RECORD} are about mutants this "
            "sweep did not produce at all. The code they were made about has moved or gone, so "
            "they have to be made again rather than carried forward.",
            file=sys.stderr,
        )
        for name in stale:
            print(f"  {name}", file=sys.stderr)

    if retired:
        # Not a failure. A test covering a mutant that once needed judging is
        # the sweep working, and a mutant whose only effect is an out-of-bounds
        # access changes sides between hosts according to how the frame was laid
        # out -- so failing here would make the record valid on one machine.
        print(
            f"mull_sweep: {len(retired)} judgement(s) in {TRIAGE_RECORD} are about mutants a test "
            "kills on this host, so they are no longer load-bearing here. Keep them if they are "
            "needed on another host; they cost nothing."
        )
        for name in retired:
            print(f"  {name}")

    if unreviewed or gaps or stale:
        return FOUND_THE_PROBLEM

    equivalent = sum(
        1 for name in survivors if judgements[name]["verdict"] == EQUIVALENT
    )
    analysed = len(survivors) - equivalent
    print(
        f"mull_sweep: every surviving mutant is accounted for with a reason -- {equivalent} that "
        f"cannot change what the program does, {analysed} that only the sanitized build could "
        "notice -- so nothing here is a gap in what the tests catch"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SweepError as error:  # pragma: no cover -- anything not caught nearer the cause
        print(f"mull_sweep: {error}", file=sys.stderr)
        sys.exit(COULD_NOT_LOOK)
