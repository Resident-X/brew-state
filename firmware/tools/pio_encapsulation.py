"""Run the encapsulation check as part of every build, in every environment.

Making the check a build step rather than a review step is what turns the
seam's encapsulation from something someone has to remember to look for into
something the toolchain asserts. It runs before anything is compiled, so a
violation stops the build rather than being reported after an artefact exists.

The check itself is a standalone script taking a path, so the same check runs
from the task runner without PlatformIO in the picture. Paths are resolved from
PROJECT_DIR rather than the working directory, which is not guaranteed.
"""

import os
import subprocess
import sys

Import("env")  # noqa: F821 -- injected by SCons

project_dir = env.subst("$PROJECT_DIR")  # noqa: F821
checker = os.path.join(project_dir, "tools", "check_encapsulation.py")
control_dir = os.path.join(project_dir, "src", "control")

result = subprocess.run([sys.executable, checker, control_dir], check=False)
if result.returncode != 0:
    env.Exit(result.returncode)  # noqa: F821
