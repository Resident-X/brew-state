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

Which sources are swept is read out of the tree rather than written down. The
population is what every structure shares plus the equations of every structure
declaring that they describe a machine, and that declaration is the structure's
own -- read here through the one gate that owns it, so there is no second
interpretation of what a structure claimed. A structure describing no machine is
left out because its arithmetic is arithmetic about nothing: a survivor there
reports no gap in the tests and a kill is no evidence against one, so including
it would pad the denominator with a subject no conclusion follows from.

It was a fixed pair of directories until a second machine-describing structure
arrived outside them, and nothing failed -- the sweep went on reporting a
percentage over part of the model. Three things now have to hold before a score
means what it says, and each is checked separately because each can be broken
while the others pass: every machine-describing structure is in the scope, an
environment compiled by the mutation toolchain exists to compile it, and mutants
actually came back from it. The first two are conclusions about configuration;
only the third is evidence that the population was really swept.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_environments  # noqa: E402
import check_machine_claim  # noqa: E402
import mull_toolchain  # noqa: E402
from check_support_status import Uninspectable  # noqa: E402
from structure_symbols import STRUCTURE_HEADER, Structure, discover  # noqa: E402

#: Exit codes. The distinction is the same one the other checks here draw, and
#: it is load-bearing: `mutate.py` treats "could not look" as a failure to
#: establish anything rather than as a catch, and a sweep that reported an
#: absent toolchain as a clean run would be the same mistake.
FOUND_THE_PROBLEM = 1
COULD_NOT_LOOK = 2

#: Where the judgement about each surviving mutant is written down.
TRIAGE_RECORD = "mutation_triage.yaml"

#: How many mutants the runner tries at once.
#:
#: Left at the runner's own default -- one -- every mutant in the population is
#: a full rebuild and a full run of whichever suite is being swept, one after
#: the other, on however many cores the host actually has. That is not a
#: correctness requirement of anything the sweep checks: two mutants running
#: at once do not interact, each gets its own compile and its own process, and
#: the report the runner writes is keyed by mutant either way. Read from the
#: host at call time rather than fixed at a number this file remembers, so a
#: runner with more or fewer cores than whatever wrote this gets a figure that
#: still fits it; one worker is kept in reserve for the process asking the
#: questions rather than answering them.
WORKER_COUNT = max(1, (os.cpu_count() or 2) - 1)

#: How long the unmutated suite is allowed before the runner calls it hung.
#:
#: This bounds only the warm-up and baseline runs, which the runner makes once
#: per suite with nothing mutated. Each mutant's own budget is derived from how
#: long the baseline actually took, so a generous figure here does not slow the
#: sweep down -- it only decides how patient the runner is with the suite it is
#: about to measure against.
#:
#: Stated rather than left to the runner's default, which is three seconds and
#: is documented nowhere -- it was established by handing the runner a one
#: millisecond timeout and watching the unmutated suite come back `Timedout`, and
#: by the plant suite passing at 2.4 seconds and failing at 2.9. That is a figure
#: sized for a unit test rather than for a suite that sweeps a sampled parameter
#: space, and it stopped being an idle setting the moment these suites grew
#: towards it: a baseline that overruns is reported as the original test failing,
#: which reads as a broken suite rather than as a clock, and it would arrive
#: first on whichever machine happened to be slowest rather than when somebody
#: made the suite slower. What is left of the protection is what it was for -- a
#: suite that genuinely hangs still stops the sweep, in a minute rather than in
#: three seconds.
BASELINE_TIMEOUT_MS = 60000

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


def declared_excludes(project: str) -> tuple[list[str], list[str]]:
    """The patterns the sweep's configuration refuses to draw mutants from.

    This is the only direction the configuration still states. The population is
    derived from the tree, so `includePaths` here would be a second answer to a
    question the structures already answer -- and, being read by the toolchain
    rather than by this tool, it would be the answer that won. It is refused
    outright rather than merged: a list nobody has to maintain cannot be kept in
    step with a tree, which is the arrangement that let a machine-describing
    structure sit outside the population unnoticed.

    Returns the exclusions and any problems found with the file. A list written
    back into it is a problem *found*, not this tool being unable to look, and the
    two are separate exit statuses here for a reason -- so it is returned rather
    than raised. Being unable to read the file at all is still raised.
    """
    path = os.path.join(project, mull_toolchain.CONFIG_NAME)
    document = load_yaml(path)
    if not isinstance(document, dict):
        raise SweepError(f"{path} does not declare a mapping of settings")

    problems: list[str] = []
    if document.get("includePaths"):
        problems.append(
            f"{path} declares includePaths. The population is read from the structures in the "
            "tree, and a list here would silently take that over -- the toolchain reads this "
            "file, not the derivation. Remove it; a structure joins the population by declaring "
            f"{check_machine_claim.CLAIM_MACRO} in its own header."
        )
    excludes = document.get("excludePaths") or []
    # Compiled here rather than where they are matched, so a pattern that is not
    # a pattern is reported against the file that declares it. Left to the match
    # site it would surface as an interpreter traceback naming neither.
    for pattern in excludes:
        try:
            re.compile(pattern)
        except re.error as error:
            raise SweepError(
                f"{path}: excludePaths entry '{pattern}' is not a usable pattern: {error}"
            ) from error
    return list(excludes), problems


def machine_describing_structures(
    structures: list[Structure], plant_root: str, include_dir: str
) -> tuple[list[Structure], list[str]]:
    """The structures whose equations describe a machine, and why the tree may not say.

    The claim is read through the gate that owns the declaration rather than
    re-read here, so the population cannot come to disagree with what that gate
    passes. A structure whose claim is unusable is returned as a problem and not
    as a structure describing no machine: an unreadable claim would otherwise
    drop equations out of the population, which is the failure this whole
    derivation exists to prevent, arrived at one step later.
    """
    vocabulary_path = os.path.join(include_dir, check_machine_claim.VOCABULARY_HEADER)
    values = check_machine_claim.vocabulary(vocabulary_path)
    problems = [
        f"{vocabulary_path}: {problem}"
        for problem in check_machine_claim.vocabulary_problems(values)
    ]

    if not structures:
        return [], problems + [
            f"no structures under {plant_root}, so there is nothing whose equations could be "
            "swept"
        ]

    claimed, faults = check_machine_claim.claims(structures, values)
    problems.extend(faults)

    describing = set(check_machine_claim.machine_describing(claimed))
    if not describing and not problems:
        # The emptiness case belonging to this step in particular. The sweep
        # already refuses when no mutation environment declares itself, when the
        # scope reaches no source, and when no mutant comes back -- and none of
        # those fires when the tree is full of structures and every one of them
        # says it describes nothing. That state yields no survivors, so it reads
        # exactly like a suite that killed everything.
        problems.append(
            "no structure declares that its equations describe a machine, so the population "
            "would be empty and the sweep would report a clean result having mutated no "
            f"arithmetic that means anything. A structure joins it by declaring "
            f"{check_machine_claim.CLAIM_MACRO} as "
            f"{check_machine_claim.DESCRIBES_A_MACHINE}."
        )

    return [structure for structure in structures if structure.name in describing], problems


def shared_directories(plant_root: str) -> list[str]:
    """The directories under the plant root that every structure shares.

    A directory that supplies no structure header is not a structure; it is the
    arithmetic the structures have in common -- the parameter loader, the step
    function -- and it is swept for the same reason theirs is. It is found the
    same way rather than named, so the population is drawn from the tree in both
    of its parts and not in one of them.
    """
    shared: list[str] = []
    for entry in sorted(os.listdir(plant_root)):
        directory = os.path.join(plant_root, entry)
        if not os.path.isdir(directory):
            continue
        if os.path.isfile(os.path.join(directory, STRUCTURE_HEADER)):
            continue
        if sources_under(directory):
            shared.append(directory)
    return shared


def scope_pattern(project: str, directory: str) -> str:
    """The pattern matching every source under one directory of the population.

    Matched against the path the compiler recorded, which is an absolute one: the
    leading `.*/` requires a separator ahead of the population's first directory,
    so anything matched against this has to be in absolute form. Kept in the
    shape the hand-written patterns had, because that shape is the one this
    project's toolchain is known to read the same way.
    """
    relative = os.path.relpath(directory, project).replace(os.sep, "/")
    return ".*/" + re.escape(relative) + "/.*"


def uncovered_structures(
    environments: list[build_environments.Environment],
    structures: list[Structure],
    described: list[Structure],
) -> list[str]:
    """The machine-describing structures no mutation environment compiles.

    Widening the population without a build to compile it is the failure this
    derivation replaced wearing different clothes: the patterns would name the
    structure, no build would reach it, and no mutant would come back -- and
    every other emptiness guard here would stay quiet, because the other
    structures' mutants would.

    The environments are matched to structures the way every other per-structure
    gate here matches them, through what each environment's source filter
    selects, so an environment added for a structure is taken up without being
    named.
    """
    available = [structure.name for structure in structures]
    swept_by = {
        environment.structure(available)
        for environment in environments
        if environment.structure(available) is not None
    }
    return sorted({structure.name for structure in described} - swept_by)


def _quoted(pattern: str) -> str:
    """One pattern as a single-quoted YAML scalar."""
    return "'" + pattern.replace("'", "''") + "'"


def write_scope(
    directory: str, includes: list[str], excludes: list[str], mutators: list[str] | None = None
) -> str:
    """Write the derived scope where the mutation toolchain will read it.

    Written somewhere of the sweep's own rather than over the project's own
    configuration, because a tool that rewrote a tracked file every run would
    leave the derivation showing up as a local edit -- and a stale one of those,
    committed, is the written-down list back again.

    Emitted directly rather than through PyYAML: the document is a mapping of two
    lists of strings, this is the only writer of it, and quoting each pattern
    outright means the file the toolchain reads is one a person debugging a scope
    can compare against the patterns printed here.

    Single quotes, not double, and that is not a style choice. A pattern is a
    regular expression, so it carries backslashes -- and a backslash inside a
    double-quoted YAML scalar starts an escape, so writing `\\.` back out that way
    produces a document the parser rejects or, worse, one it reads as a different
    pattern. A single-quoted scalar has no escapes at all beyond a doubled quote.

    `mutators`, when given, narrows which operator the plugin instruments rather
    than which sources it looks at -- a --shard-mutators split rather than a
    --shard-directory one. Omitted rather than written empty when there is no
    restriction, because an empty `mutators:` list is Mull's own way of asking
    for none at all, which is the opposite of every operator this sweep means by
    leaving the key out entirely.
    """
    path = os.path.join(directory, mull_toolchain.CONFIG_NAME)
    lines = [
        "# Derived by mull_sweep.py from the structures in the tree. Not tracked,",
        "# not edited: change what a structure declares, not this file.",
        "includePaths:",
    ]
    lines.extend(f"  - {_quoted(pattern)}" for pattern in includes)
    lines.append("excludePaths:")
    lines.extend(f"  - {_quoted(pattern)}" for pattern in excludes)
    if mutators:
        lines.append("mutators:")
        lines.extend(f"  - {_quoted(mutator)}" for mutator in mutators)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


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


def build_and_run(project: str, pio: str, environment: str, suite: str, config: str) -> None:
    """Build one suite under the mutation toolchain and require it to pass unmutated.

    A suite that already fails would make every mutant under it look caught, for
    the same reason `mutate.py` runs each of its commands once before breaking
    anything. Nothing the sweep reported afterwards would mean anything.

    The derived scope is handed down through the environment because the decision
    it governs is made during compilation: the plugin instruments what the scope
    takes in, and the build script picks this up in preference to the project's
    own configuration file.
    """
    result = subprocess.run(
        [pio, "test", "-e", environment, "-f", suite],
        cwd=project,
        env=dict(os.environ, MULL_CONFIG=config),
        check=False,
    )
    if result.returncode != 0:
        raise SweepError(
            f"'{suite}' does not pass under the mutation build before anything is mutated, so "
            "every mutant under it would be indistinguishable from one the tests caught"
        )


def discard_objects(environment: build_environments.Environment, project: str) -> None:
    """Remove one mutation environment's build directory, so it is compiled afresh.

    Only the environments built for the sweep are touched, and only ones whose
    objects exist to carry mutants -- nothing another gate or a developer's own
    build depends on is removed.
    """
    directory = environment.build_directory(project)
    if os.path.isdir(directory):
        shutil.rmtree(directory)


def artefact(project: str, environment: str) -> str:
    """The test program the build just produced."""
    path = os.path.join(project, build_environments.BUILD_ROOT, environment, "program")
    if not os.path.isfile(path):
        raise SweepError(f"the mutation build left no test program at {path}")
    return path


def run_mull(runner: str, program: str, config: str, project: str, dry_run: bool = False) -> dict:
    """Run every mutant the program carries, and read the report back.

    `dry_run` asks the runner to discover and report the mutants a scope draws
    without executing a single one of them -- what a shard's own mutator axis
    is derived from, since which operators a directory's sources actually
    produce is a fact the compiler has to be asked, not one this tool could
    read out of Mull's documentation and have stay true of every mutation
    release. Timeout and worker count are the execution budget; discovery
    alone needs neither.
    """
    with tempfile.TemporaryDirectory() as reports:
        environment = dict(os.environ, MULL_CONFIG=config)
        command = [runner, program, "--reporters", "Elements", "--report-dir", reports,
                   "--report-name", "sweep"]
        # The timeout governs the warmup run against the unmutated program,
        # which --dry-run still makes -- discovering what a scope draws
        # presupposes the thing being discovered from is testable at all, so
        # skipping a single mutant's own execution does not skip this. Only
        # --workers is dry-run-specific: there is nothing to parallelise when
        # nothing is being executed.
        command.extend(["--timeout", str(BASELINE_TIMEOUT_MS)])
        if dry_run:
            command.append("--dry-run")
        else:
            command.extend(["--workers", str(WORKER_COUNT)])
        result = subprocess.run(
            command,
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        report = os.path.join(reports, "sweep.json")
        if not os.path.isfile(report):
            if result.returncode == 0:
                # The runner's own zero-mutants case: nothing in the scope it
                # was handed produced a mutant, so there is nothing to write a
                # report about. Legitimate on a shard whose --shard-directory
                # narrows the population to a directory this environment's
                # build does not reach -- an empty population is a fact about
                # the scope, not a failure of the run, and the caller folds an
                # empty result in exactly like any other.
                return {"files": {}}
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


def discovered_mutators(report: dict) -> list[str]:
    """Every distinct operator a dry-run's mutants actually belong to, sorted.

    Read from what the compiler produced rather than from Mull's own
    documentation, on the same reasoning the population itself is read from
    the tree: a name typed here from what a release happened to document
    would go stale the moment an operator is renamed, added, or dropped, and
    would go quietly stale -- a --shard-mutators axis built from such a list
    would silently stop drawing whatever it left out, exactly the failure a
    fixed group list already produced once.
    """
    found = set()
    for contents in report.get("files", {}).values():
        for mutant in contents.get("mutants", []):
            found.add(mutant["mutatorName"])
    return sorted(found)


def outside_the_population(
    project: str, found: dict[str, dict], includes: list[str], excludes: list[str]
) -> list[str]:
    """The sources mutants came back from that the derived scope does not take in.

    What the scope says and what the compiler instrumented are two different
    facts, and only the second decides the denominator. They come apart whenever
    the scope fails to reach the plugin -- and since the population is no longer
    written in the configuration the toolchain reads, the failure is not a
    narrower sweep but an unbounded one: the plugin with no included path
    instruments every source compiled into the runner, so the control logic and
    the simulated hardware arrive in the report. If those mutants are killed, and
    tests of the control logic largely would kill them, the run passes with a
    score inflated by sources this sweep makes no claim about.

    That is this tool's own failure mode wearing the other face -- a number
    meaning less than it appears to -- so it is checked against the report rather
    than argued from the plumbing being right.

    The report's paths are made absolute again before being matched, because the
    patterns are the ones handed to the toolchain and those require a separator
    ahead of the population's first directory. Matching the relative form the
    triage record uses would put every mutant outside the population.
    """
    return sorted(
        {
            mutant["source"]
            for mutant in found.values()
            if not in_scope(os.path.join(project, mutant["source"]), includes, excludes)
        }
    )


def unswept(project: str, found: dict[str, dict], structures: list[Structure]) -> list[str]:
    """The machine-describing structures no mutant came back from, in name order.

    The scope being right and an environment existing to compile it are both
    statements about configuration. This is the only one that is evidence: a
    structure in the population that produced no mutant at all was not swept,
    whatever the patterns said, and every reason for that -- an environment whose
    build does not reach it, instrumentation that skipped it, a pattern that
    matches nothing on this host's paths -- ends in a score computed over less
    than the model while reporting as though over all of it.
    """
    swept = {mutant["source"].replace(os.sep, "/") for mutant in found.values()}
    missing: list[str] = []
    for structure in structures:
        prefix = os.path.relpath(structure.directory, project).replace(os.sep, "/") + "/"
        if not any(source.startswith(prefix) for source in swept):
            missing.append(structure.name)
    return sorted(missing)


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


def judge(
    project: str,
    found: dict[str, dict],
    includes: list[str],
    excludes: list[str],
    described: list[Structure],
    judgements: dict[str, dict],
    survivors_only: bool,
) -> int:
    """Score what the sweep found and judge it against the triage record.

    The one path every complete population reaches, whether it was drawn by a
    single run over every suite or folded together from one shard per suite:
    what decides the score is the mutants found and what is recorded about
    them, not how many processes it took to find them.
    """
    if not found:
        print(
            "mull_sweep: the swept sources produced no mutants at all, which means the scope or "
            "the instrumentation is not doing what it says rather than that the code is perfect",
            file=sys.stderr,
        )
        return FOUND_THE_PROBLEM

    intruders = outside_the_population(project, found, includes, excludes)
    if intruders:
        print(
            "mull_sweep: mutants came back from sources the population does not take in, so the "
            "score below would be computed over more than the plant model's arithmetic: "
            f"{', '.join(intruders)}. The derived scope did not reach the compiler -- the "
            "instrumented population is whatever was compiled, not what was asked for.",
            file=sys.stderr,
        )
        return FOUND_THE_PROBLEM

    missing = unswept(project, found, described)
    if missing:
        print(
            f"mull_sweep: no mutant came back from {', '.join(missing)}, which the tree says "
            "describes a machine. The scope named it and an environment was built for it, so "
            "the population it should have contributed is missing rather than empty -- and the "
            "score below would be over the rest of the model while reading as over all of it.",
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

    if survivors_only:
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


def fold(found: dict[str, dict], shard: dict[str, dict]) -> None:
    """Fold one shard's already-collected mutants into the combined population.

    The same merge `collect` makes across suites within one process, made again
    across the separate processes a matrixed run splits the suites into: a
    mutant killed by any shard is killed, and every other field is a structural
    fact about the mutant itself that does not vary by which suite reached it.
    """
    for name, mutant in shard.items():
        existing = found.get(name)
        merged = dict(mutant)
        merged["killed"] = mutant["killed"] or (existing or {}).get("killed", False)
        found[name] = merged


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="the PlatformIO project directory")
    parser.add_argument(
        "--plant-root",
        default="src/plant",
        help="the directory the structures sit in, relative to the project",
    )
    parser.add_argument(
        "--include-dir",
        default="include",
        help="the directory the shared vocabulary sits in, relative to the project",
    )
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
    parser.add_argument(
        "--population-only",
        action="store_true",
        help="derive and report the population, and run the checks about it, without sweeping",
    )
    parser.add_argument(
        "--list-shards",
        action="store_true",
        help="print every environment:suite:directory triple as a JSON array and exit, "
        "building nothing",
    )
    parser.add_argument(
        "--list-mutators-in",
        help="build this ENVIRONMENT:DIRECTORY once and report the distinct operators a "
        "dry run finds there, as a JSON array, rather than sweeping",
    )
    parser.add_argument(
        "--list-mutators-out",
        help="write --list-mutators-in's result here instead of stdout, which the build it "
        "runs also writes to",
    )
    parser.add_argument(
        "--combine-shards",
        help="a directory of JSON files, each {environment, directory, mutators: [...]} from "
        "--list-mutators-in, one per environment:directory pair this sweep declares; cross "
        "them with --list-shards' own triples and print the fully-expanded shard list, "
        "building nothing",
    )
    parser.add_argument(
        "--shard",
        help="sweep only this ENVIRONMENT:SUITE pair, one shard of a matrixed run, and write "
        "its raw findings to --shard-report rather than judging them",
    )
    parser.add_argument(
        "--shard-report",
        help="where --shard writes this shard's raw findings, as JSON",
    )
    parser.add_argument(
        "--shard-directory",
        help="restrict --shard's mutants to this one directory from --list-shards, rather "
        "than the whole population",
    )
    parser.add_argument(
        "--shard-mutators",
        help="restrict --shard's mutants to this one operator from --list-mutators-in, "
        "rather than every operator the directory draws",
    )
    parser.add_argument(
        "--merge-reports",
        help="a directory of JSON files written by --shard-report; fold them together and judge "
        "the combined population in place of sweeping directly",
    )
    args = parser.parse_args(argv)

    project = os.path.realpath(args.project)
    plant_root = os.path.join(project, args.plant_root)
    include_dir = os.path.join(project, args.include_dir)

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

    if not os.path.isdir(plant_root):
        print(
            f"mull_sweep: no plant root at {plant_root}, so no population can be drawn from it",
            file=sys.stderr,
        )
        return COULD_NOT_LOOK

    try:
        excludes, problems = declared_excludes(project)
        # SystemExit is what the shared discovery raises when a seam header it
        # needs is absent. That is this tool being unable to look rather than
        # something it found, and the exit codes here are not interchangeable.
        structures = discover(plant_root, include_dir)
        described, faults = machine_describing_structures(structures, plant_root, include_dir)
        problems.extend(faults)
    except (SweepError, Uninspectable, SystemExit) as error:
        print(f"mull_sweep: {error}", file=sys.stderr)
        return COULD_NOT_LOOK

    if problems:
        print(
            "mull_sweep: the population cannot be drawn from the tree, so no score over it "
            "would mean anything",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return FOUND_THE_PROBLEM

    directories = shared_directories(plant_root) + [
        structure.directory for structure in described
    ]
    includes = [scope_pattern(project, directory) for directory in directories]

    uncovered = uncovered_structures(environments, structures, described)
    if uncovered:
        print(
            "mull_sweep: no environment built for the sweep compiles "
            f"{', '.join(uncovered)} -- a structure in the population that no mutation build "
            "reaches produces no mutants, and a score over the rest would read as a score over "
            f"all of it. Declare one in {build_environments.PROJECT_CONFIG} extending the test "
            "environment for that structure.",
            file=sys.stderr,
        )
        return FOUND_THE_PROBLEM

    problems = scope_problems(project, includes, excludes)
    if problems:
        print("mull_sweep: the sweep's scope would not mean what it says", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return FOUND_THE_PROBLEM

    if args.population_only:
        # Everything decided before a compiler is needed, reported and stopped.
        # The three checks above are what a reader has to be able to run to see
        # that the population is the tree's rather than a list's, and requiring a
        # matching LLVM release to see it would put that out of reach on most
        # hosts.
        print(
            f"mull_sweep: {len(directories)} directory(ies) in the population -- "
            f"{', '.join(os.path.relpath(directory, project) for directory in directories)}"
        )
        for structure in described:
            print(f"  {structure.name}: describes a machine")
        return 0

    if args.list_shards:
        # No compiler needed, on the same reasoning --population-only above
        # already stands on: everything a shard's identity depends on is
        # decided before one is built. Printed as one JSON array rather than
        # one shard per line so a caller can feed it straight to a matrix
        # strategy without a parsing step of its own.
        #
        # Each environment:suite pair is split once more, by directory, on the
        # same reasoning the pair split was made for: one suite's own runtime,
        # not the number of mutants alone, is what a single shard's wall time
        # is bounded by, and splitting the mutants a suite is asked about
        # across concurrent shards is what shortens that suite's own
        # contribution rather than only how many suites run at once. A
        # directory an environment's build does not reach contributes a shard
        # that reports no mutants at all, which costs a shard's worth of setup
        # and nothing else -- cheaper, on a host with room for more jobs at
        # once, than working out in advance which pairs would benefit and
        # keeping that list in step with the tree.
        shards = [
            {
                "environment": environment.name,
                "suite": suite,
                "directory": os.path.relpath(directory, project).replace(os.sep, "/"),
            }
            for environment in environments
            for suite in suites(environment)
            for directory in directories
        ]
        print(json.dumps(shards))
        return 0

    if args.combine_shards:
        # No compiler needed here either: everything this reads is either the
        # same tree-derived triples --list-shards already produces without
        # one, or a discover-mutators shard's own output, already run.
        discovered: dict[tuple[str, str], list[str]] = {}
        names = sorted(
            name for name in os.listdir(args.combine_shards) if name.endswith(".json")
        )
        for name in names:
            path = os.path.join(args.combine_shards, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    entry = json.load(handle)
                discovered[(entry["environment"], entry["directory"])] = entry["mutators"]
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                # A discover-mutators shard that failed to upload whole rather
                # than one that failed the job outright: the matrix's own
                # fail-fast: false already surfaces the latter, so a report
                # good enough to open but not to trust is the case worth a
                # message of its own here.
                print(f"mull_sweep: {path} is not a discovery report --shard-mutators can use: {error}", file=sys.stderr)
                return COULD_NOT_LOOK

        combined = [
            {
                "environment": environment.name,
                "suite": suite,
                "directory": os.path.relpath(directory, project).replace(os.sep, "/"),
                "mutators": mutator,
            }
            for environment in environments
            for suite in suites(environment)
            for directory in directories
            for mutator in discovered.get(
                (environment.name, os.path.relpath(directory, project).replace(os.sep, "/")), []
            )
        ]
        print(json.dumps(combined))
        return 0

    if args.list_mutators_in:
        if ":" not in args.list_mutators_in:
            print(
                f"mull_sweep: --list-mutators-in wants ENVIRONMENT:DIRECTORY, got "
                f"'{args.list_mutators_in}'",
                file=sys.stderr,
            )
            return COULD_NOT_LOOK
        probe_environment_name, probe_directory = args.list_mutators_in.split(":", 1)
        probe_environment = next(
            (e for e in environments if e.name == probe_environment_name), None
        )
        known_directories = {
            os.path.relpath(directory, project).replace(os.sep, "/") for directory in directories
        }
        if probe_environment is None or probe_directory not in known_directories:
            print(
                f"mull_sweep: '{args.list_mutators_in}' names no environment or no directory "
                "this sweep's population draws from",
                file=sys.stderr,
            )
            return COULD_NOT_LOOK

        try:
            toolchain = mull_toolchain.resolved(
                warn=lambda note: print(f"mull_sweep: {note}", file=sys.stderr)
            )
        except mull_toolchain.ToolchainError as error:
            print(f"mull_sweep: {error}", file=sys.stderr)
            return COULD_NOT_LOOK

        probe_includes = [scope_pattern(project, os.path.join(project, probe_directory))]
        try:
            with tempfile.TemporaryDirectory() as derived:
                # Any suite the environment declares does as well as another:
                # the operators a directory's sources compile to are a fact
                # about the sources, not about which suite later exercises
                # them, and --dry-run never runs a test either way.
                probe_suite = suites(probe_environment)[0]
                config = write_scope(derived, probe_includes, excludes)
                discard_objects(probe_environment, project)
                print(f"mull_sweep: {probe_environment.name}:{probe_directory}", flush=True)
                build_and_run(project, args.pio, probe_environment.name, probe_suite, config)
                report = run_mull(
                    toolchain["runner"],
                    artefact(project, probe_environment.name),
                    config,
                    project,
                    dry_run=True,
                )
        except SweepError as error:
            print(f"mull_sweep: {error}", file=sys.stderr)
            return COULD_NOT_LOOK

        mutators = json.dumps(discovered_mutators(report))
        if args.list_mutators_out:
            # Not stdout: build_and_run's own build and test output streams
            # there too, so a caller capturing stdout to parse would be
            # parsing the build alongside the result, exactly what corrupted
            # the first real dispatch of this path.
            with open(args.list_mutators_out, "w", encoding="utf-8") as handle:
                handle.write(mutators)
        else:
            print(mutators)
        return 0

    if args.shard:
        if ":" not in args.shard:
            print(
                f"mull_sweep: --shard wants ENVIRONMENT:SUITE, got '{args.shard}'",
                file=sys.stderr,
            )
            return COULD_NOT_LOOK
        shard_environment_name, shard_suite = args.shard.split(":", 1)
        shard_environment = next(
            (e for e in environments if e.name == shard_environment_name), None
        )
        if shard_environment is None or shard_suite not in suites(shard_environment):
            print(
                f"mull_sweep: '{args.shard}' names no environment:suite this sweep declares",
                file=sys.stderr,
            )
            return COULD_NOT_LOOK
        if not args.shard_report:
            print("mull_sweep: --shard needs --shard-report to write its result to", file=sys.stderr)
            return COULD_NOT_LOOK

        shard_includes = includes
        if args.shard_directory:
            known = {os.path.relpath(directory, project).replace(os.sep, "/") for directory in directories}
            if args.shard_directory not in known:
                print(
                    f"mull_sweep: --shard-directory '{args.shard_directory}' names no directory "
                    "this sweep's population draws from",
                    file=sys.stderr,
                )
                return COULD_NOT_LOOK
            shard_includes = [scope_pattern(project, os.path.join(project, args.shard_directory))]

        # Not checked against a known list the way --shard-directory is:
        # there is no such list any more, on purpose, and a value naming an
        # operator this scope does not produce is not a mistake worth
        # refusing over -- it draws nothing, which run_mull already reports
        # as the legitimate empty population it is.
        shard_mutators = [args.shard_mutators] if args.shard_mutators else None

        try:
            toolchain = mull_toolchain.resolved(
                warn=lambda note: print(f"mull_sweep: {note}", file=sys.stderr)
            )
        except mull_toolchain.ToolchainError as error:
            print(f"mull_sweep: {error}", file=sys.stderr)
            return COULD_NOT_LOOK

        shard_found: dict[str, dict] = {}
        try:
            with tempfile.TemporaryDirectory() as derived:
                # Re-derived rather than passed in from whatever listed the
                # shards: the scope is a pure function of the tree every shard
                # already checked out identically, so re-deriving it here costs
                # nothing and needs no artefact carrying it between jobs. A
                # --shard-directory narrows only the include side -- the
                # excludes still keep test code and vendored sources out,
                # exactly as they would for the whole population. A
                # --shard-mutators operator narrows which mutants the plugin
                # instruments, independently of which sources it looks at.
                config = write_scope(derived, shard_includes, excludes, shard_mutators)
                discard_objects(shard_environment, project)
                print(f"mull_sweep: {shard_environment.name}:{shard_suite}", flush=True)
                build_and_run(project, args.pio, shard_environment.name, shard_suite, config)
                report = run_mull(
                    toolchain["runner"], artefact(project, shard_environment.name), config, project
                )
                collect(project, report, shard_found)
        except SweepError as error:
            print(f"mull_sweep: {error}", file=sys.stderr)
            return COULD_NOT_LOOK

        os.makedirs(os.path.dirname(os.path.abspath(args.shard_report)) or ".", exist_ok=True)
        with open(args.shard_report, "w", encoding="utf-8") as handle:
            json.dump(shard_found, handle)
        return 0

    if args.merge_reports:
        names = sorted(
            name for name in os.listdir(args.merge_reports) if name.endswith(".json")
        )
        if not names:
            print(f"mull_sweep: no shard reports found under {args.merge_reports}", file=sys.stderr)
            return COULD_NOT_LOOK
        found: dict[str, dict] = {}
        for name in names:
            path = os.path.join(args.merge_reports, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    fold(found, json.load(handle))
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                # A sweep shard that failed to upload whole rather than one
                # that failed the job outright -- the matrix's own
                # fail-fast: false already surfaces the latter.
                print(f"mull_sweep: {path} is not a shard report --merge-reports can use: {error}", file=sys.stderr)
                return COULD_NOT_LOOK
        try:
            judgements = read_triage(project)
        except SweepError as error:
            print(f"mull_sweep: {error}", file=sys.stderr)
            return COULD_NOT_LOOK
        return judge(project, found, includes, excludes, described, judgements, args.survivors_only)

    try:
        toolchain = mull_toolchain.resolved(
            warn=lambda note: print(f"mull_sweep: {note}", file=sys.stderr)
        )
        judgements = read_triage(project)
    except (SweepError, mull_toolchain.ToolchainError) as error:
        print(f"mull_sweep: {error}", file=sys.stderr)
        return COULD_NOT_LOOK

    print(
        f"mull_sweep: drawing mutants from {len(directories)} directory(ies) -- "
        f"{', '.join(os.path.relpath(directory, project) for directory in directories)}"
    )

    found: dict[str, dict] = {}

    # The derived scope has to be in place before anything is compiled: the
    # plugin decides what to instrument while the compiler runs, so a scope
    # written only for the runner would mutate everything and then report over
    # part of it.
    try:
        with tempfile.TemporaryDirectory() as derived:
            config = write_scope(derived, includes, excludes)
            for environment in environments:
                # The instrumented population is baked into the objects, and the
                # build system's freshness check sees neither this file's contents
                # nor the variable naming it -- so a cached object carries
                # whichever scope was in force when it was compiled. Left alone,
                # a change to what a structure declares would move what the sweep
                # reports over without moving what was mutated.
                discard_objects(environment, project)
                for suite in suites(environment):
                    print(f"mull_sweep: {environment.name}:{suite}", flush=True)
                    build_and_run(project, args.pio, environment.name, suite, config)
                    report = run_mull(
                        toolchain["runner"], artefact(project, environment.name), config, project
                    )
                    collect(project, report, found)
    except SweepError as error:
        print(f"mull_sweep: {error}", file=sys.stderr)
        return COULD_NOT_LOOK

    return judge(project, found, includes, excludes, described, judgements, args.survivors_only)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SweepError as error:  # pragma: no cover -- anything not caught nearer the cause
        print(f"mull_sweep: {error}", file=sys.stderr)
        sys.exit(COULD_NOT_LOOK)
