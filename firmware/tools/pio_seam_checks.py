"""Run the source-level seam checks as part of every build, in every environment.

Making these build steps rather than review steps is what turns the seams'
properties from things someone has to remember to look for into things the
toolchain asserts. They run before anything is compiled, so a violation stops
the build rather than being reported after an artefact exists.

Each is the standalone script the task runner invokes, so there is one
implementation of each check rather than two. The checks that need a linked
executable or a second environment cannot run here and belong to the gate.

Paths are resolved from PROJECT_DIR rather than the working directory, which is
not guaranteed.
"""

import os
import subprocess
import sys

Import("env")  # noqa: F821 -- injected by SCons

project_dir = env.subst("$PROJECT_DIR")  # noqa: F821
tools_dir = os.path.join(project_dir, "tools")
include_dir = os.path.join(project_dir, "include")
source_dir = os.path.join(project_dir, "src")
plant_root = os.path.join(source_dir, "plant")

# The filter this environment actually resolved to, rather than what the build
# file appears to say: interpolation and `extends` are what decide which
# directories are compiled, so the check has to see the result of both.
source_filter = env.subst("$SRC_FILTER")  # noqa: F821
environment_name = env.subst("$PIOENV")  # noqa: F821
if not source_filter.strip():
    # An unreadable filter must not read as "this environment compiles no plant
    # source". The selection check refuses an empty one for the same reason,
    # and this stops the build before it gets there.
    sys.stderr.write(
        f"pio_seam_checks: no source filter resolved for '{environment_name}', so which "
        "plant structure it selects cannot be established\n"
    )
    env.Exit(2)  # noqa: F821

CHECKS = (
    # The control logic reaches hardware only through the hardware seam.
    [os.path.join(tools_dir, "check_encapsulation.py"), os.path.join(source_dir, "control")],
    # The hardware seam itself names no vendor type and stands alone.
    [
        os.path.join(tools_dir, "check_header_neutral.py"),
        os.path.join(include_dir, "hw_interface.h"),
    ],
    # The plant seam names no structure and compiles against every one of them.
    [
        os.path.join(tools_dir, "check_plant_header.py"),
        os.path.join(include_dir, "plant_model.h"),
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
    ],
    # And so does the vocabulary it is expressed in. Inspecting only the header
    # that declares the operations would let this one clear itself of anything
    # it did, since the neutral vocabulary is read out of both.
    [
        os.path.join(tools_dir, "check_plant_header.py"),
        os.path.join(include_dir, "plant_types.h"),
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
        "--vocabulary-only",
    ],
    # And so does the vocabulary the machine's actuation channels are drawn
    # from. Both seams include it, so a structure name reaching it would reach
    # every consumer of either seam rather than of one.
    [
        os.path.join(tools_dir, "check_plant_header.py"),
        os.path.join(include_dir, "machine_actuation.h"),
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
        "--vocabulary-only",
    ],
    # Every structure in the tree states which of those channels it answers,
    # over the whole tree for the same reason the support status is: a structure
    # nobody compiles is exactly the one that would sit there unanswered.
    [
        os.path.join(tools_dir, "check_actuation_declaration.py"),
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
    ],
    # Nothing outside the structures reaches a structure's own symbols. The
    # tests are inspected alongside the sources: a test that reaches around the
    # seam is a test that would not survive a second structure either.
    [
        os.path.join(tools_dir, "check_plant_encapsulation.py"),
        source_dir,
        os.path.join(project_dir, "test"),
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
    ],
    # And so does the vocabulary the support status is drawn from. Every
    # structure header includes it, so a structure name reaching it would reach
    # every consumer of the seam, and the claim that it names none is the
    # toolchain's to establish rather than a reader's to take on trust.
    [
        os.path.join(tools_dir, "check_plant_header.py"),
        os.path.join(include_dir, "plant_support.h"),
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
        "--vocabulary-only",
    ],
    # Every structure in the tree says whether hardware has verified it, and
    # the documentation says the same thing its sources do. Over the whole
    # tree rather than the selected structure: one nobody compiles is exactly
    # the one that would otherwise sit there unanswered.
    [
        os.path.join(tools_dir, "check_support_status.py"),
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
        "--documentation",
        os.path.join(project_dir, "README.md"),
    ],
    # And so does the vocabulary a value's origin is recorded in. The loader
    # every structure's descriptions are read through includes it, so a
    # structure name reaching it would reach all of them at once.
    [
        os.path.join(tools_dir, "check_plant_header.py"),
        os.path.join(include_dir, "plant_origin.h"),
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
        "--vocabulary-only",
    ],
    # Every value in a description that claims a machine accounts for itself,
    # and the statement of what those values represent still names all of them.
    # Over every description in the tree rather than the one this environment
    # runs against: a description nothing runs is exactly the one whose
    # provenance would rot unnoticed.
    [
        os.path.join(tools_dir, "check_parameter_origins.py"),
        "--project",
        project_dir,
        "--plant-root",
        plant_root,
        "--include-dir",
        include_dir,
        "--params-dir",
        os.path.join(project_dir, "params"),
    ],
    # A build that compiles the plant model names exactly one structure.
    [
        os.path.join(tools_dir, "check_structure_selection.py"),
        "--filter",
        source_filter,
        "--plant-root",
        plant_root,
        "--env",
        environment_name,
    ],
)

for check in CHECKS:
    result = subprocess.run([sys.executable] + check, check=False)
    if result.returncode != 0:
        env.Exit(result.returncode)  # noqa: F821
