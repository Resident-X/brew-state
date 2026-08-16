"""Run the source-level seam checks as part of every build, in every environment.

Making these build steps rather than review steps is what turns the seam's
properties from things someone has to remember to look for into things the
toolchain asserts. They run before anything is compiled, so a violation stops
the build rather than being reported after an artefact exists.

Both are the standalone scripts the task runner invokes, so there is one
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

CHECKS = (
    # The control logic reaches hardware only through the seam.
    (os.path.join(tools_dir, "check_encapsulation.py"), os.path.join(project_dir, "src", "control")),
    # The seam itself names no vendor type and stands alone.
    (
        os.path.join(tools_dir, "check_header_neutral.py"),
        os.path.join(project_dir, "include", "hw_interface.h"),
    ),
)

for checker, subject in CHECKS:
    result = subprocess.run([sys.executable, checker, subject], check=False)
    if result.returncode != 0:
        env.Exit(result.returncode)  # noqa: F821
