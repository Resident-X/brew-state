#!/usr/bin/env python3
"""Build the target artefact, run it under emulation, and report what happened.

This module runs the check and gathers findings. It decides nothing: the
assertions live in the suite beside it, so that the thing producing the evidence
and the thing judging it are not the same thing. Run directly it prints the
findings and exits zero if the run completed, which is a different question from
whether the findings are the right ones.

The artefact is the target build's own output and nothing else. The path is
derived from the project rather than accepted as an argument, the build that
produces it is run here, and its digest is taken immediately afterwards and
again after the emulator has finished with it -- so a run against a stale copy,
a copy from another environment, or a file swapped mid-run is a run that fails
rather than one that quietly reports about the wrong binary.
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(EMULATION_DIR, ".."))

sys.path.insert(0, HERE)

import provision  # noqa: E402  (path is set immediately above)

# The environment whose artefact is the one that would be flashed, and the file
# that environment's build writes. Held here rather than passed in, because a
# check that can be pointed at another artefact is not a check about this one.
TARGET_ENVIRONMENT = "stm32"
TARGET_ARTEFACT = os.path.join(
    FIRMWARE_DIR, ".pio", "build", TARGET_ENVIRONMENT, "firmware.elf")

BUILD_DIR = os.path.join(FIRMWARE_DIR, ".pio", "build", TARGET_ENVIRONMENT, "emulation")

PLATFORM_TEMPLATE = os.path.join(EMULATION_DIR, "platform", "brew_state_stm32f407.repl.in")
SCRIPT_TEMPLATE = os.path.join(EMULATION_DIR, "scripts", "emulation_check.resc.in")
EXERCISE = os.path.join(EMULATION_DIR, "scripts", "exercise.py")
PERIPHERALS = os.path.join(EMULATION_DIR, "peripherals")

DEFAULT_PIO = os.path.expanduser(os.environ.get("PIO", "~/.platformio/penv/bin/pio"))


class EmulationError(RuntimeError):
    """The run did not get far enough to have findings."""


def digest_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_target(pio=DEFAULT_PIO):
    """Build the target environment and return the digest of what it wrote."""
    before = os.path.getmtime(TARGET_ARTEFACT) if os.path.exists(TARGET_ARTEFACT) else None
    completed = subprocess.run(
        [pio, "run", "-e", TARGET_ENVIRONMENT],
        cwd=FIRMWARE_DIR, capture_output=True, text=True)
    if completed.returncode != 0:
        raise EmulationError(
            "the target build failed, so there is no artefact to emulate:\n%s\n%s"
            % (completed.stdout[-4000:], completed.stderr[-4000:]))
    if not os.path.exists(TARGET_ARTEFACT):
        raise EmulationError(
            "the target build reported success but wrote no %s" % TARGET_ARTEFACT)
    return {
        "path": TARGET_ARTEFACT,
        "sha256": digest_of(TARGET_ARTEFACT),
        "rebuilt": before != os.path.getmtime(TARGET_ARTEFACT),
    }


def render(template_path, destination, substitutions):
    with open(template_path, encoding="utf-8") as handle:
        text = handle.read()
    for token, value in substitutions.items():
        text = text.replace("{{%s}}" % token, value)
    remaining = [t for t in ("{{",) if t in text]
    if remaining:
        raise EmulationError("%s still holds an unfilled placeholder" % template_path)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write(text)
    return destination


def image_of(elf_path, base, length):
    """The bytes the emulator will hold in `length` bytes of flash from `base`.

    Assembled from the artefact's own loadable segments, at the addresses the
    loader places them, so it can be compared against what the emulator reports
    having in memory. This is the host side of the binary-identity question:
    both sides are derived from the same file, by different routes.
    """
    image = bytearray(length)
    with open(elf_path, "rb") as handle:
        data = handle.read()
    if data[:4] != b"\x7fELF":
        raise EmulationError("%s is not an ELF file" % elf_path)
    if data[4] != 1 or data[5] != 1:
        raise EmulationError("%s is not a little-endian 32-bit ELF file" % elf_path)

    def word(offset, size):
        return int.from_bytes(data[offset:offset + size], "little")

    program_header_offset = word(0x1C, 4)
    program_header_size = word(0x2A, 2)
    program_header_count = word(0x2C, 2)
    for index in range(program_header_count):
        entry = program_header_offset + index * program_header_size
        if word(entry, 4) != 1:  # PT_LOAD
            continue
        file_offset = word(entry + 0x04, 4)
        physical = word(entry + 0x0C, 4)
        file_size = word(entry + 0x10, 4)
        if file_size == 0:
            continue
        start = physical - base
        if start < 0 or start + file_size > length:
            continue
        image[start:start + file_size] = data[file_offset:file_offset + file_size]
    return bytes(image)


def fnv1a64(data):
    digest = 0xCBF29CE484222325
    for byte in data:
        digest = ((digest ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return digest


#: How the emulator reports an access that no peripheral of this machine answers.
#
# Written as a pattern over the emulator's wording rather than matched exactly,
# because the wording is not ours; what has to be picked out of it is the
# address, since an address nothing answers is a command that reached nothing.
_UNANSWERED = re.compile(
    r"[Ww]rite.*?to non existing peripheral.*?0x([0-9A-Fa-f]+)")


def unanswered_writes(log_text):
    """Every address the run wrote to that no modelled peripheral answered."""
    return sorted(set(
        match.group(1).lower() for match in _UNANSWERED.finditer(log_text)))


def parse_findings(output):
    """Turn the emulator's `EMU ` lines into the record the suite reads."""
    findings = {
        "image": None,
        "injected": {},
        "startup": None,
        "init": None,
        "sensor": {},
        "failed": {},
        "restored": {},
        "conversions": {},
        "compare": [],
        "refusals": {},
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
        elif kind == "injected":
            findings["injected"][int(parts[1])] = int(parts[2])
        elif kind == "startup":
            findings["startup"] = int(parts[1])
        elif kind == "init":
            findings["init"] = int(parts[1])
        elif kind in ("sensor", "failed", "restored"):
            findings[kind][int(parts[1])] = {
                "status": int(parts[2]), "value_milli": int(parts[3])}
        elif kind == "conversions":
            findings["conversions"][int(parts[1])] = int(parts[2])
        elif kind == "output":
            findings["compare"].append({
                "label": parts[1],
                "level": int(parts[2]),
                "accepted": int(parts[3]) != 0,
                "values": [int(v) for v in parts[4].split(",")],
                "writes": [int(v) for v in parts[5].split(",")],
            })
        elif kind == "refusal":
            findings["refusals"][parts[1]] = int(parts[2]) != 0
        elif kind == "done":
            findings["completed"] = True
    return findings


def run(pio=DEFAULT_PIO, build=True):
    tooling = provision.ensure(quiet=True)
    artefact = build_target(pio) if build else {
        "path": TARGET_ARTEFACT, "sha256": digest_of(TARGET_ARTEFACT), "rebuilt": False}

    platform_file = render(
        PLATFORM_TEMPLATE, os.path.join(BUILD_DIR, "brew_state_stm32f407.repl"),
        {"PERIPHERALS": PERIPHERALS})
    log_file = os.path.join(BUILD_DIR, "emulation_check.log")
    if os.path.exists(log_file):
        os.unlink(log_file)
    script_file = render(
        SCRIPT_TEMPLATE, os.path.join(BUILD_DIR, "emulation_check.resc"),
        {"PLATFORM": platform_file, "ELF": artefact["path"], "LOG": log_file,
         "SVD": tooling["svd"], "EXERCISE": EXERCISE})

    completed = subprocess.run(
        [tooling["emulator"], "--disable-xwt", "--console", "--hide-log", "--plain",
         script_file],
        cwd=EMULATION_DIR, stdin=subprocess.DEVNULL, capture_output=True, text=True)

    findings = parse_findings(completed.stdout)
    findings["artefact"] = artefact
    findings["artefact"]["sha256_after_run"] = digest_of(artefact["path"])
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
    findings["unanswered_writes"] = unanswered_writes(findings["log_text"])
    findings["returncode"] = completed.returncode
    findings["stdout"] = completed.stdout
    findings["stderr"] = completed.stderr

    if not findings["completed"]:
        raise EmulationError(
            "the emulation run did not finish. Emulator output follows:\n%s\n%s"
            % (completed.stdout[-8000:], completed.stderr[-4000:]))

    expected = findings["image"]
    findings["expected_image_fnv1a64"] = fnv1a64(
        image_of(artefact["path"], expected["base"], expected["length"]))
    return findings


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pio", default=DEFAULT_PIO,
                        help="the PlatformIO executable that builds the target environment")
    parser.add_argument("--no-build", action="store_true",
                        help="emulate the artefact already in the build directory")
    arguments = parser.parse_args(argv)
    findings = run(pio=arguments.pio, build=not arguments.no_build)
    for line in findings["stdout"].splitlines():
        if line.strip().startswith("EMU "):
            print(line.strip())
    print("EMU artefact %s %s" % (findings["artefact"]["path"], findings["artefact"]["sha256"]))
    print("EMU expected-image %d" % findings["expected_image_fnv1a64"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
