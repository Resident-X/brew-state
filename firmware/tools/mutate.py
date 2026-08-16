#!/usr/bin/env python3
"""Break each property on purpose, and require the check that guards it to notice.

A check earns its place by failing when the thing it watches is wrong. Reading a
check and judging that it looks capable of failing is not the same as watching
it fail, and the difference is not academic: over this project's history, checks
that read as thorough have twice turned out to pass unconditionally -- once
because the subject set was empty, once because the flag being inspected was not
the flag that mattered.

So each entry below names a defect, the edit that introduces it, and the command
that must stop. The command is run twice: once before the edit, where it must
pass, and once after, where it must fail. Skipping the first run would let a
command that is already broken be mistaken for a check doing its job.

This is deliberately not part of the ordinary gate. It edits the working tree
and rebuilds, and it answers a question -- are these checks real -- that does not
change between commits the way the checks' own results do. Run it when a check is
added or reworked, and when a reviewer asks whether one can fail at all.

Usage:
  mutate.py                 every mutation
  mutate.py --list          name them without running
  mutate.py -k <substring>  only those whose name matches
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time

FIRMWARE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIO = os.environ.get("PIO", os.path.expanduser("~/.platformio/penv/bin/pio"))

#: The linked executables the checks inspect. Editing the build file makes the
#: build system discard every one of them, not only the one a mutation was
#: aimed at, so they are re-made rather than assumed. Restoring just the one
#: this tool happens to need would leave the ordinary gate unable to run.
ARTEFACTS = {
    "native": os.path.join(FIRMWARE, ".pio", "build", "native", "program"),
    "native_fixture": os.path.join(FIRMWARE, ".pio", "build", "native_fixture", "program"),
}
HOST_ARTEFACT = ARTEFACTS["native"]


def build(environment: str) -> int:
    return run([PIO, "run", "-e", environment])

#: What a check returns when it found the problem, as against when it could not
#: look. This project's checks use 1 for the former and 2 for the latter, and
#: the difference is the whole point here: a check that could not run has
#: established nothing, and counting its exit as a catch would be the failure
#: this tool exists to detect, committed by the tool itself.
FOUND_THE_PROBLEM = 1

PLANT_TESTS = [PIO, "test", "-e", "native_test", "-f", "test_plant"]
LABELS = {}
ENCAPSULATION = [
    sys.executable, "tools/check_plant_encapsulation.py", "src", "test",
    "--plant-root", "src/plant", "--include-dir", "include",
]
SEAM_HEADER = [
    sys.executable, "tools/check_plant_header.py", "include/plant_model.h",
    "--plant-root", "src/plant", "--include-dir", "include",
]
VOCABULARY_HEADER = [
    sys.executable, "tools/check_plant_header.py", "include/plant_types.h",
    "--plant-root", "src/plant", "--include-dir", "include", "--vocabulary-only",
]
SUPPORT_HEADER = [
    sys.executable, "tools/check_plant_header.py", "include/plant_support.h",
    "--plant-root", "src/plant", "--include-dir", "include", "--vocabulary-only",
]
SUPPORT_STATUS = [
    sys.executable, "tools/check_support_status.py",
    "--plant-root", "src/plant", "--include-dir", "include", "--documentation", "README.md",
]
ANALYSIS = [
    sys.executable, "tools/check_sanitizers.py", "--project", ".", "--env", "native",
    "--executable", ".pio/build/native/program",
]

#: Each entry: a name, the file to edit, the exact text to replace, what to put
#: in its place, and the command that has to stop because of it. `find` must
#: appear exactly once in the file, so a mutation cannot silently miss.
LABELS = {
    tuple(PLANT_TESTS): "the plant model's tests",
    tuple(ENCAPSULATION): "the encapsulation check",
    tuple(SEAM_HEADER): "the seam header check",
    tuple(VOCABULARY_HEADER): "the vocabulary header check",
    tuple(SUPPORT_HEADER): "the support vocabulary header check",
    tuple(SUPPORT_STATUS): "the support status check",
    tuple(ANALYSIS): "the host tier's analysis check",
}

#: Commands that inspect the linked artefact rather than the sources.
NEEDS_ARTEFACT = {tuple(ANALYSIS)}

MUTATIONS = (
    {
        "name": "cancelling-settled-fraction",
        "why": "the settled fraction is computed as one minus the exponential, which throws "
               "away its leading digits for a short step",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "    return -expm1f(-x);",
        "replace": "    return 1.0f - expf(-x);",
        "command": PLANT_TESTS,
    },
    {
        "name": "naive-temperature-step",
        "why": "the thermal masses advance as though the rate held constant across the step, "
               "which diverges at admissible coefficients",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "    return x > 0.0f ? settled_fraction(x) / x : 1.0f;",
        "replace": "    return 1.0f;",
        "command": PLANT_TESTS,
    },
    {
        "name": "naive-pressure-step",
        "why": "brew pressure advances the same way, which oscillates at the shortest "
               "admissible time constant",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "settled_fraction(seconds / p->brew_pressure_time_constant_s)",
        "replace": "(seconds / p->brew_pressure_time_constant_s)",
        "command": PLANT_TESTS,
    },
    {
        "name": "coefficient-compiled-in",
        "why": "a coefficient read from the record becomes a literal in the equations",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "parameters->steam_pressure_bar_per_k * above_saturation_k",
        "replace": "0.035f * above_saturation_k",
        "command": PLANT_TESTS,
    },
    {
        "name": "loss-coefficient-compiled-in",
        "why": "a second coefficient, in a different equation, becomes a literal",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "p->brew_loss_w_per_k,",
        "replace": "1.5f,",
        "command": PLANT_TESTS,
    },
    {
        "name": "time-constant-compiled-in",
        "why": "a coefficient that shapes only the transient becomes a literal, "
               "which comparing endpoints alone would miss",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "seconds / p->brew_pressure_time_constant_s",
        "replace": "seconds / 0.8f",
        "command": PLANT_TESTS,
    },
    {
        "name": "initial-state-not-an-equilibrium",
        "why": "an instance starts at a pressure its own equations would not produce",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "model->steam_pressure_bar = steam_pressure_at(parameters, model->steam_temperature_c);",
        "replace": "model->steam_pressure_bar = 0.0f;",
        "command": PLANT_TESTS,
    },
    {
        "name": "unrepresentable-value-accepted",
        "why": "a value arriving as zero or infinity is delivered rather than refused",
        "file": "src/plant/common/plant_parameters.c",
        "find": "if (errno == ERANGE && (parsed == 0.0f || isinf(parsed))) {",
        "replace": "if (0) {",
        "command": PLANT_TESTS,
    },
    {
        "name": "usable-value-refused",
        "why": "refusing on the range flag alone rejects values inside the declared range",
        "file": "src/plant/common/plant_parameters.c",
        "find": "if (errno == ERANGE && (parsed == 0.0f || isinf(parsed))) {",
        "replace": "if (errno == ERANGE) {",
        "command": PLANT_TESTS,
    },
    {
        "name": "consumer-reaches-a-structure",
        "why": "a model consumer names a field belonging to one structure",
        "file": "src/app/native/main.c",
        "find": "    plant_model_t model;\n",
        "replace": "    plant_model_t model;\n    (void)model.brew_temperature_c;\n",
        "command": ENCAPSULATION,
    },
    {
        "name": "seam-header-reaches-a-structure",
        "why": "the header declaring the operations names a quantity only one structure has",
        "file": "include/plant_model.h",
        "find": "#endif /* PLANT_MODEL_H */",
        "replace": "#define PLANT_BREW(m) ((m)->brew_temperature_c)\n#endif /* PLANT_MODEL_H */",
        "command": SEAM_HEADER,
    },
    {
        "name": "vocabulary-header-carries-an-equation",
        "why": "an equation is placed in the seam header that only the vocabulary check reads",
        "file": "include/plant_types.h",
        "find": "#endif /* PLANT_TYPES_H */",
        "replace": "static inline float plant_scale(float x) { return x * 2.0f; }\n#endif /* PLANT_TYPES_H */",
        "command": VOCABULARY_HEADER,
    },
    {
        "name": "structure-carries-no-support-status",
        "why": "the structure describing the reference machine's architecture reaches the seam "
               "without saying whether hardware has verified it",
        "file": "src/plant/thermoblock/plant_structure.h",
        "find": "#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED\n",
        "replace": "",
        "command": SUPPORT_STATUS,
    },
    {
        "name": "verification-claimed-without-a-citation",
        "why": "the status most likely to be set optimistically is set optimistically -- "
               "verified, with nothing cited and nothing on a bench",
        "file": "src/plant/thermoblock/plant_structure.h",
        "find": "#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED",
        "replace": "#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_HARDWARE_VERIFIED",
        "command": SUPPORT_STATUS,
    },
    {
        "name": "support-vocabulary-grows-a-distinction",
        "why": "the vocabulary gains a term for how thoroughly a structure was verified, which "
               "is evidence nobody has and a line drawn somewhere other than where the "
               "requirement draws it",
        "file": "include/plant_support.h",
        "find": "    PLANT_SUPPORT_HARDWARE_VERIFIED\n",
        "replace": "    PLANT_SUPPORT_PARTIALLY_VERIFIED,\n    PLANT_SUPPORT_HARDWARE_VERIFIED\n",
        "command": SUPPORT_STATUS,
    },
    {
        "name": "documented-status-drifts-from-the-sources",
        "why": "the table an adopter chooses a structure from publishes a status the structure's "
               "own header does not claim, which is the half that gets believed",
        "file": "README.md",
        "find": "| `thermoblock` | `PLANT_SUPPORT_UNVERIFIED` | — |",
        "replace": "| `thermoblock` | `PLANT_SUPPORT_HARDWARE_VERIFIED` | ran it, seemed fine |",
        "command": SUPPORT_STATUS,
    },
    {
        "name": "support-vocabulary-header-names-a-structure",
        "why": "the header every structure includes for the status vocabulary reaches into one "
               "structure, which would put those equations behind every consumer of the seam",
        "file": "include/plant_support.h",
        "find": "#endif /* PLANT_SUPPORT_H */",
        "replace": '#include "thermoblock/plant_structure.h"\n#endif /* PLANT_SUPPORT_H */',
        "command": SUPPORT_HEADER,
    },
    {
        "name": "strict-warnings-narrowed",
        "why": "a warning setting is dropped from the build this project's sources compile under",
        "file": "platformio.ini",
        "find": "strict_flags = -Werror -Wconversion -Wshadow -Wdouble-promotion",
        "replace": "strict_flags = -Werror -Wshadow -Wdouble-promotion",
        "command": ANALYSIS,
    },
    {
        "name": "promotion-check-dropped",
        "why": "the setting that keeps the model's arithmetic single precision is removed",
        "file": "platformio.ini",
        "find": "strict_flags = -Werror -Wconversion -Wshadow -Wdouble-promotion",
        "replace": "strict_flags = -Werror -Wconversion -Wshadow",
        "command": ANALYSIS,
    },
)


def run(command: list[str]) -> int:
    return subprocess.run(
        command, cwd=FIRMWARE, capture_output=True, text=True, check=False
    ).returncode


def label_for(command: list[str]) -> str:
    return LABELS.get(tuple(command), " ".join(command[:2]))


def ensure_artefact(command: list[str]) -> bool:
    """Re-make the linked artefact when the command about to run inspects it.

    Editing the build file makes the build system discard the executable, so a
    later check would report that it cannot find one -- a different exit code
    and a different meaning from the check failing. Left unhandled, the next
    mutation in the run reads as caught while establishing nothing, and the
    tree is left without an artefact for the ordinary gate to inspect.
    """
    if tuple(command) not in NEEDS_ARTEFACT or os.path.exists(HOST_ARTEFACT):
        return True
    return build("native") == 0


def restore_artefacts() -> list[str]:
    """Re-make every artefact the ordinary gate inspects. Returns what failed."""
    failed = []
    for environment, path in ARTEFACTS.items():
        if not os.path.exists(path) and build(environment) != 0:
            failed.append(environment)
    return failed


def write_atomic(path: str, content: str) -> None:
    """Replace a file in one step, so an interruption cannot truncate it."""
    directory = os.path.dirname(path)
    handle, temporary = tempfile.mkstemp(dir=directory, suffix=".mutate")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(content)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise


def working_tree_is_clean(paths: set[str]) -> tuple[bool, list[str]]:
    """Whether the files this would edit have no uncommitted changes.

    Refusing to run on a dirty tree is what makes the restore safe: the original
    is held in memory, so an edit that was never committed could not be told
    apart from one this made.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--"] + sorted(paths),
        cwd=FIRMWARE, capture_output=True, text=True, check=False,
    )
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    return not dirty, dirty


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="name the mutations without running")
    parser.add_argument("-k", default="", help="only mutations whose name contains this")
    args = parser.parse_args(argv)

    selected = [m for m in MUTATIONS if args.k in m["name"]]
    if not selected:
        print(f"mutate: no mutation matches '{args.k}'", file=sys.stderr)
        return 2

    if args.list:
        for mutation in selected:
            print(f"{mutation['name']}: {mutation['why']}")
        return 0

    clean, dirty = working_tree_is_clean({m["file"] for m in selected})
    if not clean:
        print(
            "mutate: these files have uncommitted changes, and this edits them in place:",
            file=sys.stderr,
        )
        for line in dirty:
            print(f"  {line}", file=sys.stderr)
        print("  commit or stash first", file=sys.stderr)
        return 2

    # Each distinct command is established as passing once, before anything is
    # broken. A command that already fails would make every mutation under it
    # look caught while proving nothing.
    baselines: dict[tuple[str, ...], int] = {}
    for mutation in selected:
        key = tuple(mutation["command"])
        if key not in baselines:
            print(f"baseline: {label_for(mutation['command'])} ... ", end="", flush=True)
            ensure_artefact(mutation["command"])
            baselines[key] = run(mutation["command"])
            print("passes" if baselines[key] == 0 else "FAILS")
    unusable = [k for k, code in baselines.items() if code != 0]
    if unusable:
        print(
            "mutate: a command fails before anything was mutated, so nothing it "
            "reports afterwards would mean anything",
            file=sys.stderr,
        )
        return 2

    survived: list[str] = []
    started = time.monotonic()

    for mutation in selected:
        path = os.path.join(FIRMWARE, mutation["file"])
        with open(path, "r", encoding="utf-8") as handle:
            original = handle.read()

        occurrences = original.count(mutation["find"])
        if occurrences != 1:
            print(
                f"mutate: {mutation['name']}: its subject appears {occurrences} times in "
                f"{mutation['file']}, so the mutation is not the one described",
                file=sys.stderr,
            )
            clean, dirty = working_tree_is_clean({m["file"] for m in selected})
            if not clean:
                print("mutate: and the working tree was not restored:", file=sys.stderr)
                for line in dirty:
                    print(f"  {line}", file=sys.stderr)
            return 2

        print(f"{mutation['name']} ... ", end="", flush=True)
        if not ensure_artefact(mutation["command"]):
            print("BUILD FAILED")
            return 2
        try:
            write_atomic(path, original.replace(mutation["find"], mutation["replace"]))
            code = run(mutation["command"])
        finally:
            write_atomic(path, original)

        expected = mutation.get("expect", FOUND_THE_PROBLEM)
        if code == expected:
            print(f"caught by {label_for(mutation['command'])}")
        elif code == 0:
            survived.append((mutation["name"], "nothing failed"))
            print("SURVIVED")
        else:
            survived.append(
                (mutation["name"], f"stopped with {code} rather than {expected}, so it stopped "
                                   "for some other reason")
            )
            print(f"INCONCLUSIVE (exit {code})")

    elapsed = time.monotonic() - started

    # Leave a usable tree: the ordinary gate inspects these, and a build-file
    # mutation will have caused all of them to be discarded.
    unbuilt = restore_artefacts()
    if unbuilt:
        print(f"mutate: could not re-make {', '.join(unbuilt)}", file=sys.stderr)
        return 2

    # The restore is verified rather than assumed: this edits real sources.
    clean, dirty = working_tree_is_clean({m["file"] for m in selected})
    if not clean:
        print("mutate: the working tree was not restored:", file=sys.stderr)
        for line in dirty:
            print(f"  {line}", file=sys.stderr)
        return 2

    if survived:
        print(
            f"\nmutate: {len(survived)} defect(s) not established, in {elapsed:.0f}s",
            file=sys.stderr,
        )
        for name, reason in survived:
            entry = next(m for m in selected if m["name"] == name)
            print(f"  {name}: {reason}", file=sys.stderr)
            print(f"    the defect was: {entry['why']}", file=sys.stderr)
        return 1

    print(f"\nmutate: {len(selected)} defect(s), each caught, in {elapsed:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
