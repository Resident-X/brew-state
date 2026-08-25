#!/usr/bin/env python3
"""Build the target artefact, run the closed-loop check under emulation, and
report what happened.

Structured the same way run_emulation_check.py is, and reuses its build and
templating logic rather than restating it: what differs between the two runs
is which script the core is handed (closed_loop.py instead of exercise.py)
and that this run also builds and points at the plant model's shared
library, which exercise.py's channel-addressing run has no use for.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(EMULATION_DIR, ".."))

sys.path.insert(0, HERE)

import build_plant_library  # noqa: E402
import run_emulation_check as base  # noqa: E402

SCRIPT_TEMPLATE = os.path.join(EMULATION_DIR, "scripts", "closed_loop.resc.in")
EXERCISE = os.path.join(EMULATION_DIR, "scripts", "closed_loop.py")
PERIPHERALS = os.path.join(EMULATION_DIR, "peripherals")

PLANT_LIBRARY_BUILD_DIR = os.path.join(FIRMWARE_DIR, ".pio", "build", "plant_bridge")
PLANT_PARAMETERS = os.path.join(FIRMWARE_DIR, "params", "thermoblock.params")

_UNANSWERED = re.compile(r"[Ww]rite.*?to non existing peripheral.*?0x([0-9A-Fa-f]+)")


def parse_findings(output):
    """Turn closed_loop.py's `EMU ` lines into the record the suite reads."""
    findings = {
        "image": None,
        "baseline_brew_c": None,
        "final_brew_c": None,
        "startup": None,
        "init": None,
        "parameters_loaded": None,
        "limits_loaded": None,
        "tolerance_loaded": None,
        "control_init": None,
        "command": None,
        "checkpoints": [],
        "draw_steps": None,
        "draw_results": [],
        "draw_actuated_count": None,
        "plant_step_count": None,
        "plant_last_step_ok": None,
        "completed": False,
    }
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("EMU "):
            continue
        parts = line.split()[1:]
        kind = parts[0]
        if kind == "image":
            findings["image"] = {
                "base": int(parts[1]), "length": int(parts[2]), "fnv1a64": int(parts[3])}
        elif kind == "baseline-brew-c":
            findings["baseline_brew_c"] = float(parts[1])
        elif kind == "final-brew-c":
            findings["final_brew_c"] = float(parts[1])
        elif kind == "startup":
            findings["startup"] = int(parts[1])
        elif kind == "init":
            findings["init"] = int(parts[1])
        elif kind == "parameters-loaded":
            findings["parameters_loaded"] = int(parts[1]) != 0
        elif kind == "limits-loaded":
            findings["limits_loaded"] = int(parts[1]) != 0
        elif kind == "tolerance-loaded":
            findings["tolerance_loaded"] = int(parts[1]) != 0
        elif kind == "control-init":
            findings["control_init"] = int(parts[1]) != 0
        elif kind == "command":
            findings["command"] = int(parts[1]) != 0
        elif kind == "checkpoints":
            findings["checkpoints"] = [float(v) for v in parts[1].split(",")] if len(parts) > 1 else []
        elif kind == "draw-steps":
            findings["draw_steps"] = int(parts[1])
        elif kind == "draw-results":
            findings["draw_results"] = [int(v) for v in parts[1].split(",")]
        elif kind == "draw-actuated-count":
            findings["draw_actuated_count"] = int(parts[1])
        elif kind == "plant-step-count":
            findings["plant_step_count"] = int(parts[1])
        elif kind == "plant-last-step-ok":
            findings["plant_last_step_ok"] = int(parts[1]) != 0
        elif kind == "done":
            findings["completed"] = True
    return findings


def run(pio=base.DEFAULT_PIO, build=True):
    tooling = base.provision.ensure(quiet=True)
    artefact = base.build_target(pio) if build else {
        "path": base.TARGET_ARTEFACT, "sha256": base.digest_of(base.TARGET_ARTEFACT),
        "rebuilt": False}

    plant_library = build_plant_library.build(PLANT_LIBRARY_BUILD_DIR)

    platform_file = base.render(
        base.PLATFORM_TEMPLATE, os.path.join(base.BUILD_DIR, "brew_state_stm32f407.repl"),
        {"PERIPHERALS": PERIPHERALS})
    log_file = os.path.join(base.BUILD_DIR, "closed_loop.log")
    if os.path.exists(log_file):
        os.unlink(log_file)
    script_file = base.render(
        SCRIPT_TEMPLATE, os.path.join(base.BUILD_DIR, "closed_loop.resc"),
        {"PLATFORM": platform_file, "ELF": artefact["path"], "LOG": log_file,
         "SVD": tooling["svd"], "EXERCISE": EXERCISE})

    env = dict(os.environ)
    env["BREW_STATE_PLANT_LIBRARY"] = plant_library
    env["BREW_STATE_PLANT_PARAMETERS"] = PLANT_PARAMETERS
    env["BREW_STATE_EMULATION_PERIPHERALS_DIR"] = PERIPHERALS

    completed = base.subprocess.run(
        [tooling["emulator"], "--disable-xwt", "--console", "--hide-log", "--plain",
         script_file],
        cwd=EMULATION_DIR, stdin=base.subprocess.DEVNULL, capture_output=True, text=True,
        env=env)

    findings = parse_findings(completed.stdout)
    findings["artefact"] = artefact
    findings["artefact"]["sha256_after_run"] = base.digest_of(artefact["path"])
    findings["plant_library"] = plant_library
    findings["emulator"] = tooling["emulator"]
    findings["svd"] = tooling["svd"]
    findings["script"] = script_file
    findings["platform"] = platform_file
    findings["log"] = log_file
    if os.path.exists(log_file):
        with open(log_file, encoding="utf-8", errors="replace") as handle:
            findings["log_text"] = handle.read()
    else:
        findings["log_text"] = ""
    findings["unanswered_writes"] = sorted(set(
        match.group(1).lower() for match in _UNANSWERED.finditer(findings["log_text"])))
    findings["returncode"] = completed.returncode
    findings["stdout"] = completed.stdout
    findings["stderr"] = completed.stderr

    if not findings["completed"]:
        raise base.EmulationError(
            "the closed-loop run did not finish. Emulator output follows:\n%s\n%s"
            % (completed.stdout[-8000:], completed.stderr[-4000:]))

    expected = findings["image"]
    findings["expected_image_fnv1a64"] = base.fnv1a64(
        base.image_of(artefact["path"], expected["base"], expected["length"]))
    return findings


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pio", default=base.DEFAULT_PIO,
                        help="the PlatformIO executable that builds the target environment")
    parser.add_argument("--no-build", action="store_true",
                        help="emulate the artefact already in the build directory")
    arguments = parser.parse_args(argv)
    findings = run(pio=arguments.pio, build=not arguments.no_build)
    for line in findings["stdout"].splitlines():
        if line.strip().startswith("EMU "):
            print(line.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
