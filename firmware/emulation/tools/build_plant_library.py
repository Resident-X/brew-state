"""Build the plant model as a host-native shared library.

The closed-loop bridge (peripherals/plant_bridge.py) calls the plant model
through this library rather than re-deriving its equations in Python, per
DEC-EMULATION-TIER-RENODE. What is compiled here is exactly the seam
plant_model.h declares plus the parameter loader, over the thermoblock
structure -- the same structure env:stm32 links into the artefact this tier
emulates, so the model driven under emulation is the one the target build
actually carries. The sources are compiled directly with the host C compiler,
independent of PlatformIO, because they are freestanding C with no vendor
dependency and no build-environment selection to make beyond naming this one
structure's directory.

The library is a bridge for Python to call into, not a firmware artefact: it
carries no ABI surface of its own beyond the seam already declared in
plant_model.h, and its two opaque record types (plant_model_t,
plant_parameters_t) are never laid out in Python -- only ever handed back and
forth as untyped memory the C side owns.
"""

import hashlib
import os
import platform
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FIRMWARE_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))

PLANT_COMMON = os.path.join(FIRMWARE_DIR, "src", "plant", "common")
PLANT_STRUCTURE = os.path.join(FIRMWARE_DIR, "src", "plant", "thermoblock")
INCLUDE_DIR = os.path.join(FIRMWARE_DIR, "include")

SOURCES = [
    os.path.join(PLANT_COMMON, "plant_delivery.c"),
    os.path.join(PLANT_COMMON, "plant_parameters.c"),
    os.path.join(PLANT_COMMON, "plant_step.c"),
    os.path.join(PLANT_STRUCTURE, "plant_structure.c"),
]


def _library_extension():
    system = platform.system().lower()
    if system == "darwin":
        return ".dylib"
    if system == "linux":
        return ".so"
    raise SystemExit("no shared-library convention known for %s" % system)


def _digest_of_sources():
    digest = hashlib.sha256()
    for source in sorted(SOURCES):
        with open(source, "rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


def build(build_dir, cc=None):
    """Compile the plant model into build_dir, returning its path.

    Skipped when a library already there was built from the same source
    bytes -- recorded beside it as a digest file, since a shared library
    carries no digest of its own inputs the way the target artefact's ELF
    does.
    """
    cc = cc or os.environ.get("CC", "cc")
    library = os.path.join(build_dir, "libplant" + _library_extension())
    digest_marker = library + ".sources-sha256"

    digest = _digest_of_sources()
    if os.path.exists(library) and os.path.exists(digest_marker):
        with open(digest_marker, encoding="utf-8") as handle:
            if handle.read().strip() == digest:
                return library

    os.makedirs(build_dir, exist_ok=True)
    command = [
        cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-shared", "-fPIC", "-O1", "-g",
        "-I", INCLUDE_DIR, "-I", PLANT_STRUCTURE,
        "-o", library,
    ] + SOURCES
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise SystemExit(
            "building the plant model's shared library failed:\n%s\n%s"
            % (completed.stdout, completed.stderr))

    with open(digest_marker, "w", encoding="utf-8") as handle:
        handle.write(digest + "\n")
    return library


if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FIRMWARE_DIR, ".pio", "build", "plant_bridge")
    print(build(out_dir))
