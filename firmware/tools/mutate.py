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
    declared = build_environments.load(FIRMWARE)
    covered = build_environments.artefact_environments(declared)
    # The artefact a machine would run is inspected by the checks too, and it is
    # discarded by an edit to the build file on exactly the same terms.
    covered += build_environments.machine_environments(declared)
    return {environment.name: environment.artefact(FIRMWARE) for environment in covered}


def build(environment: str) -> int:
    return run([PIO, "run", "-e", environment])

#: What a check returns when it found the problem, as against when it could not
#: look. This project's checks use 1 for the former and 2 for the latter, and
#: the difference is the whole point here: a check that could not run has
#: established nothing, and counting its exit as a catch would be the failure
#: this tool exists to detect, committed by the tool itself.
FOUND_THE_PROBLEM = 1

PLANT_TESTS = [PIO, "test", "-e", "native_test", "-f", "test_plant"]
#: The single-boiler structure's own suite, which is a separate run rather than
#: a filter over the one above. `env:native_test` compiles only the coffee-block
#: structure's sources, so a defect introduced into the boiler's equations never
#: reaches a translation unit that build makes -- the mutation would be reported
#: as survived having never been compiled, which is precisely the unfalsifiable
#: check this tool exists to catch. A mutation aimed at a boiler source has to
#: name the environment that builds it.
BOILER_TESTS = [PIO, "test", "-e", "native_boiler_test", "-f", "test_plant_boiler"]
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
MACHINE_CLAIM = [
    sys.executable, "tools/check_machine_claim.py",
    "--plant-root", "src/plant", "--include-dir", "include",
]
#: The sweep's own derivation, stopped before it needs a compiler. Without
#: --population-only this would ask for a matching LLVM release and then spend
#: minutes mutating, to establish something decided before either.
MULL_POPULATION = [
    sys.executable, "tools/mull_sweep.py", "--project", ".",
    "--plant-root", "src/plant", "--include-dir", "include", "--population-only",
]
ORIGIN_HEADER = [
    sys.executable, "tools/check_plant_header.py", "include/plant_origin.h",
    "--plant-root", "src/plant", "--include-dir", "include", "--vocabulary-only",
]
ORIGINS = [
    sys.executable, "tools/check_parameter_origins.py", "--project", ".",
    "--plant-root", "src/plant", "--include-dir", "include", "--params-dir", "params",
]
ASSUMED_ERROR = [
    sys.executable, "tools/check_assumed_error.py",
    "--plant-root", "src/plant", "--include-dir", "include", "--params-dir", "params",
]
ROBUSTNESS_DECLARATION = [
    sys.executable, "tools/check_robustness_declaration.py",
    "--include-dir", "include", "--declaration", "params/robustness.declaration",
]
ESTIMATOR_LIMITS = [
    sys.executable, "tools/check_estimator_limits.py",
    "--include-dir", "include", "--plant-root", "src/plant", "--params-dir", "params",
]
CADENCE_DECLARATION = [
    sys.executable, "tools/check_cadence_declaration.py",
    "--include-dir", "include", "--source-dir", "src",
    "--declaration", "params/cadence.declaration",
]
CONTROL_DECLARATION = [
    sys.executable, "tools/check_control_declaration.py",
    "--include-dir", "include", "--source-dir", "src/control", "--source-dir", "src/delivery",
    "--source-header", "include/delivery_tolerance.h",
    "--source-header", "include/delivery_profile.h",
    "--declaration", "params/control.declaration",
    "--tolerance", "params/tolerance.declaration",
    "--tree-dir", "src", "--tree-dir", "include",
]
#: The control law's own suite, which is what holds trajectories to the declared
#: band. It is named here rather than left to the gate above because the two
#: answer different questions about the same figure: the gate asks whether the
#: band is declared and accounted for, and the suite asks whether the declared
#: band is the one the software actually holds a delivery to. A band that has
#: quietly stopped reaching the loop passes the first and fails the second, and
#: it is the second that the arrangement exists for.
CONTROL_TESTS = [PIO, "test", "-e", "native_test", "-f", "test_control"]
ANALYSIS = [
    sys.executable, "tools/check_sanitizers.py", "--project", ".",
]
MACHINE_SETTINGS = [
    sys.executable, "tools/check_machine_build_settings.py", "--project", ".",
    "--plant-root", "src/plant",
]
MACHINE_STRUCTURE = [
    sys.executable, "tools/check_machine_structure_selected.py", "--project", ".",
    "--plant-root", "src/plant", "--include-dir", "include",
]
EMBEDDED_DESCRIPTION = [
    sys.executable, "tools/check_embedded_description.py", "--project", ".",
]
CARRIES_MODEL = [
    sys.executable, "tools/check_target_carries_model.py", "--project", ".",
    "--include-dir", "include", "--params-dir", "params",
]
TESTS_RUN = [
    sys.executable, "tools/run_host_tests.py", "--project", ".", "--pio", PIO,
    "--plant-root", "src/plant", "--include-dir", "include",
]

#: Each entry: a name, the file to edit, the exact text to replace, what to put
#: in its place, and the command that has to stop because of it. `find` must
#: appear exactly once in the file, so a mutation cannot silently miss.
#:
#: An entry may also declare `remake`, for a mutation that changes how an
#: artefact is made rather than what it is made from. Those leave every source
#: as it was, so the artefacts have to be discarded and built again with the
#: mutation in place -- otherwise the check inspects one made the old way and
#: the defect reads as survived without ever having reached anything.
LABELS = {
    tuple(PLANT_TESTS): "the plant model's tests",
    tuple(BOILER_TESTS): "the single-boiler structure's tests",
    tuple(ENCAPSULATION): "the encapsulation check",
    tuple(SEAM_HEADER): "the seam header check",
    tuple(VOCABULARY_HEADER): "the vocabulary header check",
    tuple(SUPPORT_HEADER): "the support vocabulary header check",
    tuple(SUPPORT_STATUS): "the support status check",
    tuple(NARROW_TESTS): "the tests driving a narrowly-declared structure",
    tuple(ACTUATION_HEADER): "the actuation vocabulary header check",
    tuple(ACTUATION_DECLARATION): "the actuation declaration check",
    tuple(MACHINE_CLAIM): "the machine claim check",
    tuple(MULL_POPULATION): "the sweep's derivation of its population",
    tuple(ORIGIN_HEADER): "the origin vocabulary header check",
    tuple(ORIGINS): "the parameter origins check",
    tuple(ASSUMED_ERROR): "the assumed model error check",
    tuple(ROBUSTNESS_DECLARATION): "the robustness declaration check",
    tuple(ESTIMATOR_LIMITS): "the limits declaration check",
    tuple(CADENCE_DECLARATION): "the cadence declaration check",
    tuple(CONTROL_DECLARATION): "the control declaration check",
    tuple(CONTROL_TESTS): "the control law's tests",
    tuple(ANALYSIS): "the host tier's analysis check",
    tuple(MACHINE_SETTINGS): "the check that a machine build keeps its warning settings",
    tuple(MACHINE_STRUCTURE): "the check that a machine build carries a machine's equations",
    tuple(EMBEDDED_DESCRIPTION): "the check that a machine carries the verified description",
    tuple(CARRIES_MODEL): "the check that the artefact carries the model",
    tuple(TESTS_RUN): "the task that runs the tests",
}

#: Commands that inspect the linked artefact rather than the sources.
NEEDS_ARTEFACT = {tuple(ANALYSIS), tuple(EMBEDDED_DESCRIPTION), tuple(CARRIES_MODEL)}

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
        "name": "naive-coupled-step",
        "why": "the coupled pair advances as though each state's rate held constant across the "
               "step, which is first order in the step length and is exactly what a caller "
               "would then have to shorten the interval to hide",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "    *kappa = seconds * (carried + (decay + decay) * second_order);",
        "replace": "    *kappa = seconds;",
        "command": PLANT_TESTS,
    },
    {
        "name": "the-pair-carries-its-separation-by-the-settled-fraction",
        "why": "the separation between the pair's two modes is weighted by how far a relaxation "
               "travelled rather than by that fraction per time constant elapsed, which is the "
               "same confusion between the two expressions the single-mass step avoids",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "        carried = expf(-slow) * relaxation_factor(separation + separation);",
        "replace": "        carried = expf(-slow) * settled_fraction(separation + separation);",
        "command": PLANT_TESTS,
    },
    {
        "name": "the-outlet-is-the-casting-read-twice",
        "why": "the water on its way to the group is the casting, which is the model this "
               "structure had before it distinguished the two and leaves an estimator nothing "
               "to reconstruct",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "    *outlet_c = outlet_before_c + kappa * outlet_rate + sigma * outlet_curvature;",
        "replace": "    *outlet_c = *casting_c;",
        "command": PLANT_TESTS,
    },
    {
        "name": "the-drawn-loss-written-at-the-casting",
        "why": "the energy the drawn water carries away is reckoned at the casting's own "
               "temperature rather than at the water leaving, which leaves nothing the brew "
               "sensor reads depending on the state no sensor reports",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "         carried_w_per_k * (outlet_before_c - p->water_feed_temperature_c)) /",
        "replace": "         carried_w_per_k * (casting_before_c - p->water_feed_temperature_c)) /",
        "command": PLANT_TESTS,
    },
    {
        "name": "the-outlet-lag-does-not-move-with-the-draw",
        "why": "the water leaving approaches the casting at the no-draw conduction rate however "
               "hard the pump is driven, which is the fixed outlet time constant this structure "
               "carried before the drawn rate entered the relation",
        "file": "src/plant/thermoblock/plant_structure.c",
        "find": "    const float approach_per_s = outlet_approach_per_s(p, drawn_ml_per_s);",
        "replace": "    const float approach_per_s = 1.0f / p->brew_outlet_conduction_time_constant_s;",
        "command": PLANT_TESTS,
    },
    {
        "name": "the-feed-water-is-the-room",
        "why": "the temperature the drawn water arrives at is taken as ambient, which is the "
               "same number on this machine and a different quantity on any machine plumbed to "
               "a main",
        "file": "src/plant/boiler/plant_structure.c",
        "find": "                         drawn_w_per_k * (model->vessel_temperature_c -\n"
                "                                          p->water_feed_temperature_c);",
        "replace": "                         drawn_w_per_k * (model->vessel_temperature_c -\n"
                   "                                          p->ambient_temperature_c);",
        "command": BOILER_TESTS,
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
        "find": "p->brew_loss_w_per_k * (casting_before_c - p->ambient_temperature_c)",
        "replace": "1.5f * (casting_before_c - p->ambient_temperature_c)",
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
        "name": "structure-does-not-say-whether-it-describes-a-machine",
        "why": "the structure describing the reference machine's architecture reaches the seam "
               "without saying whether its equations describe a machine, which is what decides "
               "whether the mutation sweep draws mutants from them at all",
        "file": "src/plant/thermoblock/plant_structure.h",
        "find": "#define PLANT_STRUCTURE_MACHINE_CLAIM PLANT_DESCRIBES_A_MACHINE\n",
        "replace": "",
        "command": MACHINE_CLAIM,
    },
    {
        "name": "machine-claim-vocabulary-grows-a-distinction",
        "why": "the vocabulary gains a term for describing a machine in part, which is a "
               "judgement no build-time check can make and somewhere vague for an arriving "
               "structure to sit, from which whether the sweep draws mutants is undecided",
        "file": "include/plant_machine_claim.h",
        "find": "    PLANT_DESCRIBES_A_MACHINE\n",
        "replace": "    PLANT_DESCRIBES_PART_OF_A_MACHINE,\n    PLANT_DESCRIBES_A_MACHINE\n",
        "command": MACHINE_CLAIM,
    },
    {
        "name": "the-sweep-is-handed-a-population-again",
        "why": "the written-down list comes back in the configuration the toolchain reads, which "
               "would take the derivation over silently and is the arrangement that let a "
               "machine-describing structure sit outside the population unnoticed",
        "file": "mull.yml",
        "find": "excludePaths:",
        "replace": 'includePaths:\n  - ".*/src/plant/thermoblock/.*"\nexcludePaths:',
        "command": MULL_POPULATION,
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
        "name": "the-machine-build-drops-its-warning-settings",
        "why": "the settings the target applies to our own sources are emptied, so the model "
               "and the control logic beside it compile under whatever the platform defaults "
               "to -- on the one artefact that gets energised",
        "file": "platformio.ini",
        "find": "build_src_flags = -Werror\nextra_scripts =",
        "replace": "build_src_flags =\nextra_scripts =",
        "command": MACHINE_SETTINGS,
    },
    {
        "name": "the-machine-build-claims-a-host-exemption",
        "why": "the target claims the exemption meant for a build compiling sources that are "
               "not ours, which is how a recorded reason becomes a way of turning the "
               "settings off where they could be kept",
        "file": "platformio.ini",
        "find": "custom_embedded_description = params/thermoblock.params",
        "replace": "custom_embedded_description = params/thermoblock.params\n"
                   "custom_strict_flags_exemption = it would be convenient",
        "command": MACHINE_SETTINGS,
    },
    {
        "name": "the-machine-build-stops-compiling-the-model",
        "why": "the model is taken out of the target's source filter, so the machine is built "
               "carrying none -- which the settings check notices as the model no longer "
               "arriving under the settings at all",
        "file": "platformio.ini",
        "find": "build_src_filter = ${common.control_sources} ${common.delivery_sources} ${common.estimator_sources} ${common.plant_sources} +<hw/stm32/> +<app/stm32/>",
        "replace": "build_src_filter = ${common.control_sources} ${common.delivery_sources} ${common.estimator_sources} +<hw/stm32/> +<app/stm32/>",
        "command": MACHINE_SETTINGS,
    },
    {
        "name": "machine-built-against-equations-describing-nothing",
        "why": "the build that would be energised selects the structure whose own header says "
               "its equations describe no machine, which a count of one structure passes",
        "file": "platformio.ini",
        "find": "build_src_filter = ${stm32_base.build_src_filter} +<plant/thermoblock/>\n"
                "build_flags = ${stm32_base.build_flags} -I $PROJECT_DIR/src/plant/thermoblock",
        "replace": "build_src_filter = ${stm32_base.build_src_filter} +<plant/fixture/>\n"
                   "build_flags = ${stm32_base.build_flags} -I $PROJECT_DIR/src/plant/fixture",
        "command": MACHINE_STRUCTURE,
    },
    {
        "name": "carried-description-is-not-the-verified-one",
        "why": "the build declares it carries a variant description rather than the one the "
               "host verification tier is pinned to, which nothing on the machine could report",
        "file": "platformio.ini",
        "find": "custom_embedded_description = params/thermoblock.params",
        "replace": "custom_embedded_description = params/thermoblock-variant.params",
        "command": EMBEDDED_DESCRIPTION,
    },
    {
        "name": "carried-description-left-stale",
        "why": "the description moves on and the bytes rendered into the artefact do not, "
               "which is the divergence generating them was supposed to have closed",
        "file": "params/thermoblock.params",
        "find": "# The reference machine's description, for the thermoblock structure.",
        "replace": "# The reference machine's description, for the thermoblock structure.\n"
                   "# A line the rendered embedding does not carry.",
        "command": EMBEDDED_DESCRIPTION,
    },
    {
        "name": "model-discarded-from-the-artefact",
        "why": "the step that keeps the model's operations in the artefact is dropped, and the "
               "linker discards equations nothing on the machine drives yet -- which every "
               "check before the artefact passes",
        "file": "platformio.ini",
        "find": "    post:tools/pio_retain_plant_model.py\n",
        "replace": "",
        "command": CARRIES_MODEL,
        "remake": True,
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
        # Anchored on the line that selects the narrow structure, because the two
        # lines below it are what every test environment carries -- a third
        # structure's test environment made the pair ambiguous and left this
        # mutation reporting that its subject was not the one described.
        "find": "-I $PROJECT_DIR/src/plant/fixture\ntest_build_src = yes\n"
                "custom_strict_flags_exemption",
        "replace": "-I $PROJECT_DIR/src/plant/fixture\ncustom_strict_flags_exemption",
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
        "why": "the description the design is reasoned against claims no machine, so every value "
               "in it stops owing an account while the check goes on passing",
        "file": "params/thermoblock.params",
        "find": "ambient_temperature_c = 20.0 ~ 0.25 @estimated",
        "replace": "@describes-no-machine\nambient_temperature_c = 20.0 ~ 0.25 @estimated",
        "command": ORIGINS,
    },
    {
        # The same defect again, against the other thing that catches it. Two
        # defences are worth having here -- the build check reads the file, the
        # suite reads the file the build hands it -- and a defence nothing
        # demonstrates is one nobody would notice losing.
        "name": "the-reference-description-exempts-itself-from-the-suite",
        "why": "the description the model's own tests are exercised against claims no machine, "
               "so the suite is asserting about a placeholder",
        "file": "params/thermoblock.params",
        "find": "ambient_temperature_c = 20.0 ~ 0.25 @estimated",
        "replace": "@describes-no-machine\nambient_temperature_c = 20.0 ~ 0.25 @estimated",
        "command": PLANT_TESTS,
    },
    {
        "name": "a-value-loses-its-origin",
        "why": "a coefficient in the reference description carries no account of where its "
               "figure came from",
        "file": "params/thermoblock.params",
        "find": "brew.heater_power_w = 1000.0 ~ 0.25 @document Coffee thermoblock element, read off "
                "the circuit diagram on p.24 of the Sunbeam EM7000 service manual.",
        "replace": "brew.heater_power_w = 1000.0 ~ 0.25",
        "command": ORIGINS,
    },
    {
        "name": "an-estimate-labelled-with-a-word-nobody-declared",
        "why": "a value carries an origin kind outside the vocabulary, so what separates an "
               "estimate from a measurement stops being a fixed set of words",
        "file": "params/thermoblock.params",
        "find": "brew.pressure_time_constant_s = 0.8 ~ 0.5 @estimated",
        "replace": "brew.pressure_time_constant_s = 0.8 ~ 0.5 @approximately",
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
        "name": "a-value-loses-its-assumed-error",
        "why": "a coefficient in the reference description carries no account of how far out "
               "the design is entitled to assume it may be, so a margin sized against it is "
               "sized against an uncertainty that exists only in its author's head",
        "file": "params/thermoblock.params",
        "find": "brew.thermal_mass_j_per_k = 320.0 ~ 0.4 @estimated",
        "replace": "brew.thermal_mass_j_per_k = 320.0 @estimated",
        "command": ASSUMED_ERROR,
    },
    {
        "name": "an-assumed-error-the-machine-would-refuse",
        "why": "a figure this check reads as a number and the machine's own loader does not -- a "
               "digit separator is two digits here and nonsense there -- so the description "
               "passes the gate that exists to stop exactly this and is refused at run time by "
               "the loader it was cleared for",
        "file": "params/thermoblock.params",
        "find": "brew.thermal_mass_j_per_k = 320.0 ~ 0.4 @estimated",
        "replace": "brew.thermal_mass_j_per_k = 320.0 ~ 0_4 @estimated",
        "command": ASSUMED_ERROR,
    },
    {
        "name": "an-assumed-error-that-says-nothing",
        "why": "a value carries the marker with no figure behind it, which reads as declared to "
               "anyone skimming the file and states nothing at all -- the shape a half-finished "
               "edit leaves behind",
        "file": "params/thermoblock.params",
        "find": "pump.pressure_bar = 15.0 ~ 0.4 @estimated",
        "replace": "pump.pressure_bar = 15.0 ~ @estimated",
        "command": ASSUMED_ERROR,
    },
    {
        "name": "a-channel-carries-no-declared-bounds",
        "why": "a channel the estimator corrects against is left with no admissible span, so "
               "the machine goes on believing whatever that channel reports -- which is the "
               "one state nothing about the running machine distinguishes from a bound "
               "somebody chose, and the failure the declaration exists to prevent",
        "file": "params/thermoblock.limits",
        "find": "\nsteam-pressure = -1000 .. 20000",
        "replace": "\n#steam-pressure = -1000 .. 20000",
        "command": ESTIMATOR_LIMITS,
    },
    {
        "name": "a-tolerance-redeclared-away-from-its-single-site",
        "why": "a figure that varies with the machine is compiled in beside the vocabulary "
               "that names it, so it has stopped varying with the machine while going on "
               "reading as declared in every limits file the tree ships",
        "file": "include/estimator_limits.h",
        "find": "#define ESTIMATOR_LIMITS_RANGE_MARKER \"..\"",
        "replace": "#define ESTIMATOR_LIMITS_RANGE_MARKER \"..\"\n"
                   "#define ESTIMATOR_LOSS_TOLERANCE_WINDOW_MS 500",
        "command": CADENCE_DECLARATION,
    },
    {
        "name": "a-behaviour-carries-no-class",
        "why": "a behaviour the design commits to is declared without saying whether it must "
               "survive an arbitrarily wrong model, which is the one failure the declaration "
               "exists to prevent and the one nobody notices by reading",
        "file": "params/robustness.declaration",
        "find": "reaching-a-safe-state = invariant",
        "replace": "reaching-a-safe-state =",
        "command": ROBUSTNESS_DECLARATION,
    },
    {
        "name": "a-behaviour-classified-both-ways",
        "why": "a behaviour falls on both sides of the line the classification exists to draw, "
               "which is what an argument nobody settled leaves behind",
        "file": "params/robustness.declaration",
        "find": "respecting-the-supply-budget = invariant",
        "replace": "respecting-the-supply-budget = invariant degrading",
        "command": ROBUSTNESS_DECLARATION,
    },
    {
        "name": "the-declared-band-narrowed-past-what-the-loop-can-hold",
        "why": "the band trajectories are accepted against is narrowed in the declaration "
               "alone, with no edit to any source, and every delivery the suite drives is "
               "still accepted. That is the whole claim the band being data rather than a "
               "constant rests on, and it is the one a check watching for a macro name "
               "cannot make: rename the macro and the name scan is satisfied, while the "
               "figure the software holds deliveries to is whatever the last person "
               "compiled. What establishes it is the declaration alone deciding which "
               "trajectories stop being accepted",
        "file": "params/tolerance.declaration",
        "find": "brew-temperature-band-milli-c = 1000 @document",
        "replace": "brew-temperature-band-milli-c = 100 @document",
        "command": CONTROL_TESTS,
    },
    {
        "name": "a-band-of-nothing-declared",
        "why": "the band is declared as zero, which is not a tight tolerance but a criterion "
               "no delivery could ever meet -- and the loader refuses it, so this is a "
               "declaration the machine does not come up on while the gate goes on reporting "
               "the band as declared",
        "file": "params/tolerance.declaration",
        "find": "brew-temperature-band-milli-c = 1000 @document",
        "replace": "brew-temperature-band-milli-c = 0 @document",
        "command": CONTROL_DECLARATION,
    },
    {
        "name": "the-flow-departure-band-narrowed-past-what-deliveries-actually-hold-to",
        "why": "the band a delivery's flow is held against is narrowed in the declaration "
               "alone, with no edit to any source, and a reading the shipped suite plants "
               "as an ordinary in-band gap is still accepted. That is the whole claim the "
               "band being data rather than a constant rests on, and it is the one a check "
               "watching for a macro name cannot make: rename the macro and the name scan "
               "is satisfied, while the gap the software reports as departure is whatever "
               "the last person compiled. What establishes it is the declaration alone "
               "deciding which deliveries stop being accepted",
        "file": "params/tolerance.declaration",
        "find": "flow-departure-band-milli-ml-s = 300 @estimated",
        "replace": "flow-departure-band-milli-ml-s = 30 @estimated",
        "command": CONTROL_TESTS,
    },
    {
        "name": "a-negative-assumed-error-accepted",
        "why": "an error below zero is delivered rather than refused, so a figure that means "
               "nothing reaches whatever sizes a margin from it",
        "file": "src/plant/common/plant_parameters.c",
        "find": "    if (!(parsed >= 0.0f)) {",
        "replace": "    if (false) {",
        "command": PLANT_TESTS,
    },
    {
        "name": "the-value-token-runs-past-the-assumed-error",
        "why": "the value ends at the origin rather than at whichever annotation comes first, so "
               "a value and the error against it are parsed as one token -- which is how the "
               "refusal of a second number in a value would be lost to the extension",
        "file": "src/plant/common/plant_parameters.c",
        "find": "        const char *value_end = budget_begin;",
        "replace": "        const char *value_end = origin_begin;",
        "command": PLANT_TESTS,
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


def discard_artefacts() -> None:
    """Remove every artefact, so the next re-make builds rather than reuses.

    A mutation of how an artefact is made -- a build step dropped, a flag
    removed -- leaves the sources it was built from untouched, so a build system
    asked to build again has nothing to notice and the check goes on inspecting
    an artefact made the old way. That is the mutation reported as survived
    while never having been applied to anything.
    """
    for path in artefacts().values():
        if os.path.exists(path):
            os.remove(path)


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
            if mutation.get("remake"):
                # This one changes how the artefact is made rather than what it
                # is made from, so it has to be made again with the mutation in
                # place. Nothing else would differ.
                #
                # A re-make that fails leaves no artefact, and a check that
                # cannot find one stops with the same code as a check that found
                # the problem. Counting that as a catch would be this tool
                # committing the failure it exists to detect, so it stops here.
                discard_artefacts()
                unbuilt = restore_artefacts()
                if unbuilt:
                    print(f"BUILD FAILED ({', '.join(unbuilt)})")
                    return 2
            code = run(mutation["command"])
        finally:
            write_atomic(path, original)
            if mutation.get("remake"):
                # And discarded again, so what is left behind was not built
                # from a mutated build file. The re-make at the end rebuilds it.
                discard_artefacts()

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
