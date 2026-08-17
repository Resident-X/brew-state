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

sys.path.insert(0, os.path.join(FIRMWARE, "tools"))

import build_environments  # noqa: E402


def artefacts() -> dict[str, str]:
    """The linked executables the checks inspect, as the build declares them.

    Editing the build file makes the build system discard every one of them,
    not only the one a mutation was aimed at, so they are re-made rather than
    assumed. Restoring just the one this tool happens to need would leave the
    ordinary gate unable to run -- and a hand-written list of them here would
    be the very thing the checks below no longer keep.

    Read afresh on each call, because a mutation edits the build file and the
    answer can change while this is running.
    """
    return {
        environment.name: environment.artefact(FIRMWARE)
        for environment in build_environments.artefact_environments(
            build_environments.load(FIRMWARE)
        )
    }


def build(environment: str) -> int:
    return run([PIO, "run", "-e", environment])

#: What a check returns when it found the problem, as against when it could not
#: look. This project's checks use 1 for the former and 2 for the latter, and
#: the difference is the whole point here: a check that could not run has
#: established nothing, and counting its exit as a catch would be the failure
#: this tool exists to detect, committed by the tool itself.
FOUND_THE_PROBLEM = 1

PLANT_TESTS = [PIO, "test", "-e", "native_test", "-f", "test_plant"]
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
NARROW_TESTS = [PIO, "test", "-e", "native_fixture_test", "-f", "test_plant_narrow"]
ACTUATION_HEADER = [
    sys.executable, "tools/check_plant_header.py", "include/machine_actuation.h",
    "--plant-root", "src/plant", "--include-dir", "include", "--vocabulary-only",
]
ACTUATION_DECLARATION = [
    sys.executable, "tools/check_actuation_declaration.py",
    "--plant-root", "src/plant", "--include-dir", "include",
]
SUPPORT_STATUS = [
    sys.executable, "tools/check_support_status.py",
    "--plant-root", "src/plant", "--include-dir", "include", "--documentation", "README.md",
]
ORIGIN_HEADER = [
    sys.executable, "tools/check_plant_header.py", "include/plant_origin.h",
    "--plant-root", "src/plant", "--include-dir", "include", "--vocabulary-only",
]
ORIGINS = [
    sys.executable, "tools/check_parameter_origins.py",
    "--plant-root", "src/plant", "--include-dir", "include", "--params-dir", "params",
]
ANALYSIS = [
    sys.executable, "tools/check_sanitizers.py", "--project", ".",
]
TESTS_RUN = [
    sys.executable, "tools/run_host_tests.py", "--project", ".", "--pio", PIO,
    "--plant-root", "src/plant", "--include-dir", "include",
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
    tuple(NARROW_TESTS): "the tests driving a narrowly-declared structure",
    tuple(ACTUATION_HEADER): "the actuation vocabulary header check",
    tuple(ACTUATION_DECLARATION): "the actuation declaration check",
    tuple(ORIGIN_HEADER): "the origin vocabulary header check",
    tuple(ORIGINS): "the parameter origins check",
    tuple(ANALYSIS): "the host tier's analysis check",
    tuple(TESTS_RUN): "the task that runs the tests",
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
    {
        "name": "one-environment-drops-the-warning-settings",
        "why": "a single environment overrides the settings its base gives it, which is the "
               "defect a gate verifying one named environment cannot see at all",
        "file": "platformio.ini",
        "find": "build_src_filter = ${native_base.build_src_filter} +<plant/fixture/> +<app/native/>\n"
                "build_flags = ${native_base.build_flags} -I $PROJECT_DIR/src/plant/fixture",
        "replace": "build_src_filter = ${native_base.build_src_filter} +<plant/fixture/> +<app/native/>\n"
                   "build_flags = ${native_base.build_flags} -I $PROJECT_DIR/src/plant/fixture\n"
                   "build_src_flags = -Wall",
        "command": ANALYSIS,
    },
    {
        "name": "an-exemption-where-the-settings-could-be-kept",
        "why": "an environment that compiles nothing but this project's sources claims the "
               "exemption meant for the one that cannot, which is how a recorded reason "
               "becomes a way of turning the settings off",
        "file": "platformio.ini",
        "find": "[env:native_fixture]",
        "replace": "[env:native_fixture]\ncustom_strict_flags_exemption = they are inconvenient",
        "command": ANALYSIS,
    },
    {
        "name": "the-tests-stop-being-run",
        "why": "the environment carrying the tests stops declaring it, and tests that never "
               "run leave nothing behind to notice",
        "file": "platformio.ini",
        "find": "test_build_src = yes\n; The test runner's own generated support file",
        "replace": "; The test runner's own generated support file",
        "command": TESTS_RUN,
    },
    {
        "name": "unanswered-channel-absorbed",
        "why": "a command on a channel the structure does not answer is taken rather than "
               "refused, which is indistinguishable to a caller from an actuator that is "
               "present and ineffective",
        "file": "src/plant/common/plant_step.c",
        "find": "        if (commanded && !answers) {",
        "replace": "        if (false && commanded && !answers) {",
        "command": NARROW_TESTS,
    },
    {
        "name": "unanswered-channel-zeroed",
        "why": "the level on an unanswered channel is dropped and the step taken anyway, so a "
               "refusal reads as the model having advanced with the command adjusted",
        "file": "src/plant/common/plant_step.c",
        "find": "        const bool commanded = actuation->level_permille[channel] != 0u;",
        "replace": "        const bool commanded = false;",
        "command": NARROW_TESTS,
    },
    {
        "name": "zero-on-an-unanswered-channel-refused",
        "why": "commanding nothing of an absent actuator is treated as a fault, which leaves a "
               "caller that zeroes every channel it does not use unable to step at all",
        "file": "src/plant/common/plant_step.c",
        "find": "        const bool commanded = actuation->level_permille[channel] != 0u;",
        "replace": "        const bool commanded = true;",
        "command": NARROW_TESTS,
    },
    {
        "name": "fault-order-left-to-the-implementation",
        "why": "the two channel faults are looked for in one pass, so which of them a command "
               "carrying both is refused for follows the channel it happens to be on",
        "file": "src/plant/common/plant_step.c",
        "find": "        if (actuation->level_permille[channel] > ACTUATION_FULL_SCALE) {",
        "replace": "        if (actuation->level_permille[channel] > ACTUATION_FULL_SCALE &&\n"
                   "            (answered & ACTUATION_CHANNEL_BIT(channel)) != 0u) {",
        "command": NARROW_TESTS,
    },
    {
        "name": "structure-states-no-channels",
        "why": "a structure reaches the seam without saying which channels it answers, which "
               "is the state every structure was in before this was required",
        "file": "src/plant/fixture/plant_structure.h",
        "find": "#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER)",
        "replace": "",
        "command": ACTUATION_DECLARATION,
    },
    {
        "name": "structure-claims-a-channel-the-machine-lacks",
        "why": "a structure claims to answer something nothing can command, which would "
               "otherwise be found by a caller whose command goes nowhere",
        "file": "src/plant/fixture/plant_structure.h",
        "find": "#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER)",
        "replace": "#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_GRINDER)",
        "command": ACTUATION_DECLARATION,
    },
    {
        "name": "actuation-vocabulary-header-names-a-structure",
        "why": "the header both seams draw the machine's channels from reaches into one "
               "structure, which would put those equations behind every consumer of either seam",
        "file": "include/machine_actuation.h",
        "find": "#endif /* MACHINE_ACTUATION_H */",
        "replace": '#include "thermoblock/plant_structure.h"\n#endif /* MACHINE_ACTUATION_H */',
        "command": ACTUATION_HEADER,
    },
    {
        "name": "a-suite-runs-nowhere",
        "why": "an environment stops taking in one of the suites it runs, which leaves that "
               "suite running in no environment at all and nothing behind to notice",
        "file": "platformio.ini",
        "find": "test_filter = test_plant, test_control",
        "replace": "test_filter = test_control",
        "command": TESTS_RUN,
    },
    {
        "name": "a-structure-claims-a-channel-bare",
        "why": "a structure names a channel without the operation that makes the set containing "
               "it, so its declaration is that channel's index and answers whichever channels "
               "that index has the bits of",
        "file": "src/plant/fixture/plant_structure.h",
        "find": "#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER)",
        "replace": "#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_STEAM_HEATER",
        "command": ACTUATION_DECLARATION,
    },
    {
        "name": "a-second-list-of-the-machines-channels",
        "why": "a seam header enumerates the machine's channels a second time, which is the "
               "state the shared vocabulary replaced and which agrees only by hand",
        "file": "include/hw_interface.h",
        "find": "typedef actuation_channel_t hw_output_channel_t;",
        "replace": "typedef enum {\n"
                   "    HW_OUTPUT_BREW_HEATER = ACTUATION_CHANNEL_BREW_HEATER,\n"
                   "    HW_OUTPUT_STEAM_HEATER = ACTUATION_CHANNEL_STEAM_HEATER,\n"
                   "    HW_OUTPUT_PUMP = ACTUATION_CHANNEL_PUMP\n"
                   "} hw_output_channel_t;",
        "command": ACTUATION_DECLARATION,
    },
    {
        "name": "the-narrow-structure's-tests-stop-being-run",
        "why": "the environment carrying the only tests that can exercise an unanswered channel "
               "stops declaring that it runs tests",
        "file": "platformio.ini",
        "find": "test_build_src = yes\ncustom_strict_flags_exemption",
        "replace": "custom_strict_flags_exemption",
        "command": TESTS_RUN,
    },
    {
        "name": "an-origin-with-no-account-accepted",
        "why": "an annotation carrying a kind and nothing behind it is accepted, so a value can "
               "be labelled without saying what it was arrived at from",
        "file": "src/plant/common/plant_parameters.c",
        "find": "    return account_begin != account_end;",
        "replace": "    return true;",
        "command": PLANT_TESTS,
    },
    {
        "name": "a-statement-the-description-cannot-make-ignored",
        "why": "a marker line the loader does not recognise is passed over instead of refused, "
               "which turns the annotation grammar into a second comment syntax",
        "file": "src/plant/common/plant_parameters.c",
        "find": "            if (!spans_word(statement_begin, statement_end,\n"
                "                            PLANT_ORIGIN_NO_MACHINE_DECLARATION)) {",
        "replace": "            if (false) {",
        "command": PLANT_TESTS,
    },
    {
        "name": "the-reference-description-exempts-itself",
        "why": "the description the design is reasoned against claims no machine, which would "
               "silence the origins check while leaving it passing",
        "file": "params/thermoblock.params",
        "find": "ambient_temperature_c = 20.0 @estimated",
        "replace": "@describes-no-machine\nambient_temperature_c = 20.0 @estimated",
        "command": PLANT_TESTS,
    },
    {
        "name": "a-value-loses-its-origin",
        "why": "a coefficient in the reference description carries no account of where its "
               "figure came from",
        "file": "params/thermoblock.params",
        "find": "brew.heater_power_w = 1000.0 @document Coffee thermoblock element, read off the "
                "circuit diagram on p.24 of the Sunbeam EM7000 service manual.",
        "replace": "brew.heater_power_w = 1000.0",
        "command": ORIGINS,
    },
    {
        "name": "an-estimate-labelled-with-a-word-nobody-declared",
        "why": "a value carries an origin kind outside the vocabulary, so what separates an "
               "estimate from a measurement stops being a fixed set of words",
        "file": "params/thermoblock.params",
        "find": "brew.pressure_time_constant_s = 0.8 @estimated",
        "replace": "brew.pressure_time_constant_s = 0.8 @approximately",
        "command": ORIGINS,
    },
    {
        "name": "origin-vocabulary-grows-a-distinction",
        "why": "the vocabulary gains a kind for a figure nobody established, which is a term "
               "for how much a value is trusted rather than for how it was arrived at",
        "file": "include/plant_origin.h",
        "find": "    PLANT_ORIGIN_KIND_COUNT",
        "replace": "    PLANT_ORIGIN_ASSUMED,\n    PLANT_ORIGIN_KIND_COUNT",
        "command": ORIGINS,
    },
    {
        "name": "the-statement-falls-behind-the-description",
        "why": "a coefficient the description carries is named nowhere in the statement of what "
               "the description represents, so it has no unit and enters no relation",
        "file": "params/thermoblock.md",
        "find": "| `brew.loss_w_per_k` / `steam.loss_w_per_k` |",
        "replace": "| the loss coefficients |",
        "command": ORIGINS,
    },
    {
        "name": "origin-vocabulary-header-names-a-structure",
        "why": "the vocabulary every structure's descriptions are read through reaches into one "
               "structure's record",
        "file": "include/plant_origin.h",
        "find": "#endif /* PLANT_ORIGIN_H */",
        "replace": "float brew_thermal_mass_j_per_k_of(const plant_model_t *model);\n"
                   "#endif /* PLANT_ORIGIN_H */",
        "command": ORIGIN_HEADER,
    },
)


def run(command: list[str]) -> int:
    return subprocess.run(
        command, cwd=FIRMWARE, capture_output=True, text=True, check=False
    ).returncode


def label_for(command: list[str]) -> str:
    return LABELS.get(tuple(command), " ".join(command[:2]))


def ensure_artefact(command: list[str]) -> bool:
    """Re-make the linked artefacts when the command about to run inspects them.

    Editing the build file makes the build system discard the executables, so a
    later check would report that it cannot find one -- a different exit code
    and a different meaning from the check failing. Left unhandled, the next
    mutation in the run reads as caught while establishing nothing, and the
    tree is left without an artefact for the ordinary gate to inspect.

    Every artefact is re-made rather than one of them, because the commands
    here now inspect every artefact the build declares.
    """
    if tuple(command) not in NEEDS_ARTEFACT:
        return True
    return not restore_artefacts()


def restore_artefacts() -> list[str]:
    """Re-make every artefact the ordinary gate inspects. Returns what failed."""
    failed = []
    for environment, path in artefacts().items():
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
